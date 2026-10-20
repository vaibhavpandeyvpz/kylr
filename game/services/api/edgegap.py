"""Persisted Edgegap deployments; only the backend holds the provider credential."""
import ipaddress
import os
import re
import secrets
import threading
from urllib.parse import urlparse

import requests
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from .contracts import ApiError, digest, identifier
from .scheduler import Scheduler


class EdgegapScheduler(Scheduler):
    def __init__(self, store, control_token):
        super().__init__(store, control_token)
        self.key = os.environ.get('EDGEGAP_API_KEY', '').removeprefix('token ').strip()
        self.application = os.environ.get('EDGEGAP_APPLICATION', '').strip()
        self.version = os.environ.get('EDGEGAP_VERSION', '').strip()
        self.api_url = (os.environ.get('GAME_API_URL') or os.environ.get('RENDER_EXTERNAL_URL','')).rstrip('/')
        parsed = urlparse(self.api_url)
        if not all((self.key, self.application, self.version)) or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise RuntimeError('Configure EDGEGAP_API_KEY, EDGEGAP_APPLICATION, EDGEGAP_VERSION and an HTTPS GAME_API_URL.')
        self.port = int(os.environ.get('EDGEGAP_GAME_PORT', '25000'))
        self.port_name = os.environ.get('EDGEGAP_PORT_NAME', 'gameport')
        self.maximum = int(os.environ.get('EDGEGAP_MAX_DEPLOYMENTS', '1'))
        self.startup = int(os.environ.get('SERVER_START_SECONDS', '180'))
        self.latitude = float(os.environ.get('EDGEGAP_LATITUDE', '19.0760'))
        self.longitude = float(os.environ.get('EDGEGAP_LONGITUDE', '72.8777'))
        if not 1 <= self.port <= 65535 or not 1 <= self.maximum <= 100 or not 30 <= self.startup <= 600 or not -90 <= self.latitude <= 90 or not -180 <= self.longitude <= 180:
            raise RuntimeError('Invalid Edgegap capacity, port, startup deadline or coordinates.')
        self.poll_lock = threading.Lock()
        self.next_poll = 0

    def call(self, method, route, payload=None, missing_ok=False):
        # Never retry a creation POST: a timeout can still have allocated an instance.
        try:
            response = requests.request(method, 'https://api.edgegap.com'+route,
                headers={'Authorization': 'token '+self.key}, json=payload,
                timeout=(5, 15), allow_redirects=False)
            if missing_ok and response.status_code == 404:
                return None
            if response.status_code not in (200, 201, 202, 204):
                code = 'SERVER_CAPACITY' if response.status_code in (409, 422, 429) else 'HOSTING_UNAVAILABLE'
                raise ApiError(code, 'Game hosting is unavailable or at capacity. Retry shortly.', 503)
            value = response.json() if response.content else {}
            if not isinstance(value, dict):
                raise ValueError('Invalid provider response')
            return value
        except (requests.RequestException, ValueError):
            raise ApiError('HOSTING_UNAVAILABLE', 'Game hosting did not respond. Retry shortly.', 503) from None

    def ensure(self, match_type):
        self.reap()
        now = self.store.clock()
        # A single persisted capacity lock covers all match types and API workers.
        try:
            lock = self.store.db.launch_leases.find_one_and_update(
                {'_id': 'edgegap-capacity', 'until': {'$lte': now}},
                {'$set': {'until': now+30}}, upsert=True, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError:
            return
        if not lock:
            return
        try:
            live = list(self.store.db.servers.find({'provider': 'edgegap', 'stopped': {'$ne': True}}))
            if any(row['type'] == match_type and (not row.get('endpoint_ready') or (not row.get('ready') and row['phase'] in ('Waiting','Countdown'))) for row in live):
                return
            # Another worker may have reserved the last slot since the caller checked.
            if any(row['type'] == match_type and row.get('ready') and row['phase'] in ('Waiting', 'Countdown', 'Active') and len(row['slots']) < 10 for row in live):
                return
            if len(live) >= self.maximum:
                raise ApiError('SERVER_CAPACITY', 'All game servers are occupied. Try again after a match ends.', 503)
            server_id, match_id = identifier(), identifier()
            token = secrets.token_urlsafe(48)
            record = {'_id': server_id, 'match_id': match_id, 'type': match_type, 'provider': 'edgegap',
                'host': '', 'port': 0, 'slots': [], 'phase': 'Waiting', 'ready': False,
                'endpoint_ready': False, 'lease_until': now+self.startup,
                'startup_until': now+self.startup, 'last_occupied': now,
                'control_hash': digest(token), 'stopped': False}
            self.store.db.servers.insert_one(record)
            environment = {'KYLR_SERVER_ID': server_id, 'KYLR_MATCH_ID': match_id,
                'KYLR_MATCH_TYPE': match_type, 'KYLR_PORT': str(self.port),
                'KYLR_API_URL': self.api_url, 'KYLR_CONTROL_TOKEN': token}
            try:
                created = self.call('POST', '/v2/deployments', {
                    'application': self.application, 'version': self.version,
                    'users': [{'user_type': 'geo_coordinates', 'user_data': {
                        'latitude': self.latitude, 'longitude': self.longitude}}],
                    'environment_variables': [{'key': key, 'value': value,
                        'is_hidden': key == 'KYLR_CONTROL_TOKEN'} for key, value in environment.items()],
                    'tags': ['kylr-managed', server_id]})
                deployment = created.get('request_id', '')
                if not isinstance(deployment, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,128}', deployment):
                    raise ApiError('HOSTING_UNAVAILABLE', 'Game hosting returned an invalid deployment.', 503)
                self.store.db.servers.update_one({'_id': server_id}, {'$set': {'deployment_id': deployment}})
            except ApiError:
                # Keep the capacity record until its startup deadline on ambiguous failure.
                self.store.db.servers.update_one({'_id': server_id}, {'$set': {'launch_uncertain': True}})
                raise
        finally:
            self.store.db.launch_leases.update_one({'_id': 'edgegap-capacity'}, {'$set': {'until': 0}})

    def reap(self):
        now = self.store.clock()
        if now < self.next_poll or not self.poll_lock.acquire(blocking=False):
            return
        try:
            self.next_poll = now+5
            self.store.expire()
            for record in self.store.db.servers.find({'provider': 'edgegap', 'stopped': {'$ne': True}}):
                deployment = record.get('deployment_id')
                expired = record['lease_until'] <= now
                if not deployment:
                    if record.get('launch_uncertain') or now > record['startup_until']-self.startup+30:
                        deployment = self.recover(record['_id'])
                        if deployment:
                            self.store.db.servers.update_one({'_id':record['_id']},
                                {'$set':{'deployment_id':deployment}})
                        elif record['startup_until'] <= now:
                            self.stopped(record['_id'])
                    if not deployment:
                        continue
                if expired:
                    status = self.call('GET', '/v1/status/'+deployment, missing_ok=True)
                    # Expired instances can already have exited or reached their
                    # provider duration limit. Do not stop a terminated instance
                    # again: the provider can reject that request with HTTP 400.
                    if status is not None and status.get('current_status') != 'Status.TERMINATED':
                        self.call('DELETE', '/v1/stop/'+deployment, missing_ok=True)
                    self.stopped(record['_id'])
                    continue
                if record.get('endpoint_ready'):
                    continue  # Authenticated game heartbeats own liveness after startup.
                status = self.call('GET', '/v1/status/'+deployment, missing_ok=True)
                if status is None:
                    continue  # Allow eventual visibility until the startup deadline.
                if status.get('error') or status.get('current_status') in ('Status.TERMINATED', 'Status.ERROR'):
                    if status.get('current_status') != 'Status.TERMINATED':
                        self.call('DELETE', '/v1/stop/'+deployment, missing_ok=True)
                    self.stopped(record['_id'])
                    continue
                if not status.get('running') or status.get('current_status') != 'Status.READY':
                    continue
                port = status.get('ports', {}).get(self.port_name, {})
                external = port.get('external')
                host = status.get('public_ip', '')
                try:
                    address = ipaddress.ip_address(host)
                    valid = address.is_global
                except ValueError:
                    valid = False
                if not valid or type(external) is not int or not 1 <= external <= 65535 or port.get('protocol', '').upper() != 'UDP' or port.get('internal') != self.port:
                    self.call('DELETE', '/v1/stop/'+deployment, missing_ok=True)
                    self.stopped(record['_id'])
                    continue
                self.store.db.servers.update_one({'_id': record['_id'], 'stopped': False},
                    {'$set': {'host': host, 'port': external, 'endpoint_ready': True}})
        finally:
            self.poll_lock.release()

    def recover(self, server_id):
        """Recover an accepted POST whose response was lost, without allocating twice."""
        for page in range(1, 11):
            result = self.call('GET', f'/v1/deployments?page={page}&limit=100')
            for row in result.get('data', []):
                if server_id in row.get('tags', []) and 'kylr-managed' in row.get('tags', []):
                    deployment = row.get('request_id', '')
                    if isinstance(deployment,str) and re.fullmatch(r'[A-Za-z0-9-]{1,128}',deployment):
                        return deployment
            if not result.get('pagination', {}).get('has_next', False):
                return None
        raise ApiError('HOSTING_UNAVAILABLE','Could not reconcile hosting capacity. Retry shortly.',503)

    def stopped(self, server_id):
        self.store.db.servers.update_one({'_id': server_id},
            {'$set': {'stopped': True, 'ready': False, 'lease_until': 0, 'slots': []}})
