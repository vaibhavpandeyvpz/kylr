"""Single-process game instances, with MongoDB launch leases across API workers."""
import os
import subprocess
import time
import threading
import logging
from pathlib import Path
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from .contracts import ApiError, identifier

class Scheduler:
    def __init__(self,store,control_token):
        self.store,self.control_token = store,control_token
        self.processes = {}

    def start_monitor(self):
        def monitor():
            while True:
                time.sleep(5)
                try: self.reap()
                except Exception as error:
                    # Database/control outages never authorize destructive cleanup.
                    logging.getLogger('kylr.scheduler').warning('cleanup_unavailable type=%s',type(error).__name__)
        threading.Thread(target=monitor,daemon=True,name='kylr-instance-monitor').start()

    def reap(self):
        """Release failed instances, including containers left after API restart."""
        now = self.store.clock()
        self.store.expire()
        if os.getenv('SCHEDULER','docker') == 'local':
            for server_id, process in list(self.processes.items()):
                record = self.store.server(server_id)
                if process.poll() is not None or (record and record['lease_until'] <= now):
                    if process.poll() is None: process.terminate()
                    self.processes.pop(server_id, None)
                    self.store.db.servers.update_one({'_id':server_id},{'$set':{'ready':False,'lease_until':0}})
        else:
            import docker
            client = docker.from_env(timeout=5)
            for instance in client.containers.list(filters={'label':'kylr.managed=true'}):
                server_id = instance.labels.get('kylr.server')
                record = self.store.server(server_id) if server_id else None
                if record and record['lease_until'] <= now:
                    try: instance.stop(timeout=3)
                    except docker.errors.NotFound: pass
                    self.processes.pop(server_id, None)
            for server_id in list(self.processes):
                record = self.store.server(server_id)
                if record and record['lease_until'] <= now: self.processes.pop(server_id,None)

    def ensure(self,match_type):
        self.reap()
        now = self.store.clock()
        # Only one worker launches a candidate of each type during a readiness window.
        try:
            lease = self.store.db.launch_leases.find_one_and_update(
                {'_id':match_type,'until':{'$lte':now}},
                {'$set':{'until':now+45}},upsert=True,return_document=ReturnDocument.AFTER)
        except DuplicateKeyError: return
        if not lease: return
        server_id,match_id = identifier(),identifier()
        minimum = int(os.getenv('GAME_PORT_MIN','25000'))
        port=None
        for candidate in range(minimum,minimum+100):
            try:
                claimed=self.store.db.port_leases.find_one_and_update(
                    {'_id':candidate,'until':{'$lte':now}},
                    {'$set':{'until':now+45,'server':server_id}},upsert=True,return_document=ReturnDocument.AFTER)
                if claimed: port=candidate; break
            except DuplicateKeyError: continue
        if port is None: raise ApiError('SERVER_CAPACITY','No game-server port is available.',503)
        record = {'_id':server_id,'match_id':match_id,'type':match_type,'phase':'Waiting',
                  'host':os.getenv('PUBLIC_GAME_HOST','127.0.0.1'),'port':port,'slots':[],
                  'ready':False,'lease_until':now+45,'last_occupied':now}
        self.store.db.servers.insert_one(record)
        self.store.db.launch_leases.update_one({'_id':match_type},{'$set':{'server':server_id}})
        environment = {'KYLR_SERVER_ID':server_id,'KYLR_MATCH_ID':match_id,
                       'KYLR_MATCH_TYPE':match_type,'KYLR_PORT':str(port),
                       'KYLR_CONTROL_TOKEN':self.control_token,
                       'KYLR_API_URL':os.getenv('GAME_API_URL','http://127.0.0.1:8080')}
        try:
            if os.getenv('SCHEDULER','docker') == 'local':
                root = Path(__file__).resolve().parents[2]
                executable = os.getenv('GODOT','godot')
                env = dict(os.environ,**environment)
                logdir = root/'reports'/'online'
                logdir.mkdir(parents=True,exist_ok=True)
                with (logdir/f'server-{server_id}.log').open('w',encoding='utf-8') as output:
                    process = subprocess.Popen([executable,'--headless','--path',str(root),
                        '-s','res://scripts/network/server_main.gd'],env=env,cwd=root,stdout=output,
                        stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                self.processes[server_id]=process
            else:
                import docker
                client = docker.from_env(timeout=5)
                instance = client.containers.run(os.getenv('GAME_IMAGE','kylr-game-server:local'),
                    detach=True,auto_remove=True,name='kylr-'+server_id,
                    environment=environment,network=os.getenv('GAME_NETWORK','kylr-online'),
                    ports={f'{port}/udp':(os.getenv('GAME_BIND','127.0.0.1'),port)},
                    labels={'kylr.managed':'true','kylr.server':server_id},
                    mem_limit='2g',cap_drop=['ALL'],security_opt=['no-new-privileges:true'])
                self.processes[server_id]=instance
        except Exception:
            self.store.db.servers.update_one({'_id':server_id},{'$set':{'ready':False,'lease_until':0}})
            self.store.db.launch_leases.update_one({'_id':match_type},{'$set':{'until':0}})
            raise ApiError('SERVER_START_FAILED','The game-server process could not start.',503)
