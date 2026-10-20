"""Cloud lifecycle tests use provider responses, never real paid deployments."""
import concurrent.futures
import os
import secrets
import time

import mongomock
import pytest
import requests

from services.api.app import create_app
from services.api.contracts import ApiError
from services.api.edgegap import EdgegapScheduler
from services.api.store import Store


@pytest.fixture
def cloud(monkeypatch):
    for key, value in {'EDGEGAP_API_KEY':'provider-secret-for-test', 'EDGEGAP_APPLICATION':'kylr',
        'EDGEGAP_VERSION':'build-test', 'GAME_API_URL':'https://accounts.example.com',
        'EDGEGAP_MAX_DEPLOYMENTS':'1'}.items():
        monkeypatch.setenv(key,value)
    from pymongo import MongoClient
    mongo = MongoClient(os.environ['MONGO_TEST_URI']) if os.getenv('MONGO_TEST_URI') else mongomock.MongoClient()
    database = mongo['kylr_cloud_test_'+secrets.token_hex(4)]
    store = Store(database)
    scheduler = EdgegapScheduler(store,'control-test-'+'x'*32)
    calls = []
    def provider(method, route, payload=None, missing_ok=False):
        calls.append((method,route,payload))
        if method == 'POST': return {'request_id':'deployment-1'}
        if method == 'GET':
            return {'running':True,'current_status':'Status.READY','error':False,
                'public_ip':'8.8.8.8','ports':{'gameport':{'internal':25000,'external':31234,'protocol':'UDP'}}}
        return {}
    monkeypatch.setattr(scheduler,'call',provider)
    yield store,scheduler,calls
    mongo.drop_database(database.name)
    mongo.close()


def pulse(store, record):
    return store.heartbeat(record['_id'],{'match_id':record['match_id'],'phase':'Waiting','accounts':[]})


def test_active_closed_elimination_round_does_not_block_another_launch(cloud):
    store,scheduler,calls=cloud
    scheduler.maximum=2
    scheduler.ensure('ELIMINATION')
    record=store.db.servers.find_one()
    store.db.servers.update_one({'_id':record['_id']},{'$set':{
        'phase':'Active','ready':False,'endpoint_ready':True,'port':31234,'host':'8.8.8.8'}})
    scheduler.ensure('ELIMINATION')
    assert store.db.servers.count_documents({'type':'ELIMINATION'})==2


def test_deployment_uses_v2_hidden_scoped_control_and_public_udp_mapping(cloud):
    store,scheduler,calls = cloud
    scheduler.ensure('DM')
    record = store.db.servers.find_one()
    assert not record['ready'] and record['port'] == 0
    route,payload = calls[0][1:]
    assert route == '/v2/deployments' and payload['version'] == 'build-test'
    variables = {row['key']:row for row in payload['environment_variables']}
    assert variables['KYLR_CONTROL_TOKEN']['is_hidden']
    assert variables['KYLR_CONTROL_TOKEN']['value'] != scheduler.control_token
    assert not any(row['key'] == 'EDGEGAP_API_KEY' for row in payload['environment_variables'])
    pulse(store,record)
    assert not store.server(record['_id'])['ready'], 'Heartbeat alone cannot expose an unmapped endpoint'
    scheduler.next_poll = 0
    scheduler.reap()
    assert not store.server(record['_id'])['ready'], 'Provider readiness alone cannot authorize admission'
    pulse(store,record)
    ready = store.server(record['_id'])
    assert ready['ready'] and ready['port'] == 31234 and ready['host'] == '8.8.8.8'


def test_capacity_is_global_across_modes_and_concurrent_api_workers(cloud):
    store,scheduler,calls = cloud
    def launch(mode):
        try: scheduler.ensure(mode)
        except ApiError as error: assert error.code == 'SERVER_CAPACITY'
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(launch,['DM','TDM','CTF']*4))
    assert store.db.servers.count_documents({}) == 1
    assert len([row for row in calls if row[0] == 'POST']) == 1


def test_restart_recovers_mapping_and_stale_deployment_is_stopped(cloud,monkeypatch):
    store,scheduler,calls = cloud
    scheduler.ensure('CTF')
    resumed = EdgegapScheduler(store,scheduler.control_token)
    monkeypatch.setattr(resumed,'call',scheduler.call)
    resumed.reap()
    record = store.db.servers.find_one()
    assert record['endpoint_ready']
    store.db.servers.update_one({'_id':record['_id']},{'$set':{'lease_until':time.time()-1}})
    resumed.next_poll = 0
    resumed.reap()
    assert store.server(record['_id'])['stopped']
    assert ('DELETE','/v1/stop/deployment-1',None) in calls
    assert pulse(store,record)['retire'], 'A stopped server cannot resurrect its readiness'


@pytest.mark.parametrize("expired", [True, False])
def test_already_terminated_instance_does_not_block_the_next_match(cloud,monkeypatch,expired):
    store,scheduler,calls = cloud
    scheduler.ensure('DM')
    record = store.db.servers.find_one()
    if expired:
        store.db.servers.update_one({'_id':record['_id']},{'$set':{'lease_until':0}})
    original = scheduler.call
    def terminated(method,route,payload=None,missing_ok=False):
        if method == 'GET' and '/status/' in route:
            return {'current_status':'Status.TERMINATED','running':False}
        if method == 'DELETE':
            pytest.fail('Provider rejects stopping an already terminated instance')
        return original(method,route,payload,missing_ok)
    monkeypatch.setattr(scheduler,'call',terminated)
    scheduler.next_poll = 0
    scheduler.ensure('TDM')
    assert store.server(record['_id'])['stopped']
    assert store.db.servers.count_documents({'stopped':False,'type':'TDM'}) == 1


@pytest.mark.parametrize('field,value', [('public_ip','127.0.0.1'),('public_ip','attacker.invalid')])
def test_invalid_provider_endpoint_is_never_assigned(cloud,monkeypatch,field,value):
    store,scheduler,calls = cloud
    scheduler.ensure('DM')
    original = scheduler.call
    def invalid(method,route,payload=None,missing_ok=False):
        response = original(method,route,payload,missing_ok)
        if method == 'GET': response[field] = value
        return response
    monkeypatch.setattr(scheduler,'call',invalid)
    scheduler.next_poll = 0
    scheduler.reap()
    assert store.db.servers.find_one()['stopped']


def test_provider_timeout_is_not_retried_and_does_not_leak_secret(cloud,monkeypatch):
    store,scheduler,_ = cloud
    def timeout(*args,**kwargs): raise requests.Timeout('secret provider response')
    monkeypatch.setattr(requests,'request',timeout)
    monkeypatch.setattr(scheduler,'call',EdgegapScheduler.call.__get__(scheduler))
    with pytest.raises(ApiError) as caught: scheduler.ensure('DM')
    assert caught.value.code == 'HOSTING_UNAVAILABLE'
    assert 'secret' not in caught.value.message
    scheduler.ensure('DM')
    assert store.db.servers.count_documents({}) == 1
    assert store.db.servers.find_one()['launch_uncertain']


def test_server_credentials_cannot_control_a_different_deployment(cloud):
    store,scheduler,calls = cloud
    scheduler.ensure('DM')
    record = store.db.servers.find_one()
    token = next(row['value'] for row in calls[0][2]['environment_variables'] if row['key'] == 'KYLR_CONTROL_TOKEN')
    class NoMonitor:
        def ensure(self,_mode): pass
    app = create_app(store.db,{'JWT_SECRET':'jwt-'+'z'*40,'CONTROL_TOKEN':scheduler.control_token},NoMonitor())
    client = app.test_client()
    data = {'match_id':record['match_id'],'phase':'Waiting','accounts':[]}
    route = '/internal/servers/'+record['_id']+'/heartbeat'
    assert client.post(route,json=data,headers={'X-Control-Token':scheduler.control_token}).status_code == 403
    assert client.post(route,json=data,headers={'X-Control-Token':token}).status_code == 200
    store.db.servers.insert_one(dict(record,_id='other-server',control_hash='different'))
    assert client.post('/internal/servers/other-server/heartbeat',json=data,headers={'X-Control-Token':token}).status_code == 403


def test_cloud_configuration_rejects_insecure_callback(cloud,monkeypatch):
    store,scheduler,_ = cloud
    monkeypatch.setenv('GAME_API_URL','http://accounts.example.com')
    with pytest.raises(RuntimeError): EdgegapScheduler(store,scheduler.control_token)


def test_lost_creation_response_recovers_owned_deployment_by_tag(cloud,monkeypatch):
    store,scheduler,calls = cloud
    original = scheduler.call
    def lost(method,route,payload=None,missing_ok=False):
        if method == 'POST': raise ApiError('HOSTING_UNAVAILABLE','Response lost',503)
        if route.startswith('/v1/deployments?'):
            record = store.db.servers.find_one()
            return {'data':[{'request_id':'recovered-1','tags':['kylr-managed',record['_id']]}],
                'pagination':{'has_next':False}}
        return original(method,route,payload,missing_ok)
    monkeypatch.setattr(scheduler,'call',lost)
    with pytest.raises(ApiError): scheduler.ensure('DM')
    scheduler.next_poll = 0
    scheduler.reap()
    record = store.db.servers.find_one()
    assert record['deployment_id'] == 'recovered-1'
    assert record['endpoint_ready']
    assert store.db.servers.count_documents({}) == 1


def test_slow_first_boot_does_not_consume_empty_server_idle_window(cloud):
    store,scheduler,_ = cloud
    scheduler.ensure('DM')
    record = store.db.servers.find_one()
    store.db.servers.update_one({'_id':record['_id']},{'$set':{'last_occupied':time.time()-120}})
    assert not pulse(store,record)['retire']


def test_render_supplies_its_callback_origin_on_first_deployment(cloud,monkeypatch):
    store,scheduler,_ = cloud
    monkeypatch.delenv('GAME_API_URL')
    monkeypatch.setenv('RENDER_EXTERNAL_URL','https://kylr-test.onrender.com')
    assert EdgegapScheduler(store,scheduler.control_token).api_url == 'https://kylr-test.onrender.com'
