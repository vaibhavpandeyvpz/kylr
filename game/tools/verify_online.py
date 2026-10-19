"""Separate Godot processes against real HTTP/MongoDB; no client state shortcuts."""
import argparse, json, os, secrets, subprocess, sys, threading, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import requests
from waitress import create_server
from pymongo import MongoClient
from services.api.app import create_app

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mongo',default=os.getenv('MONGO_TEST_URI','mongodb://127.0.0.1:27017'))
    parser.add_argument('--type',choices=('DM','TDM','CTF'),default='DM')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    reports=root/'reports'/'online'/('probe-'+args.type.lower())
    reports.mkdir(parents=True,exist_ok=True)
    mongo=MongoClient(args.mongo,serverSelectionTimeoutMS=3000)
    db=mongo['kylr_probe_'+secrets.token_hex(4)]
    db.command('ping')
    control=secrets.token_urlsafe(40)
    class ExistingServer:
        def ensure(self,_mode): pass
    app=create_app(db,{'JWT_SECRET':secrets.token_urlsafe(40),'CONTROL_TOKEN':control},ExistingServer())
    http=create_server(app,host='127.0.0.1',port=18080,threads=8)
    thread=threading.Thread(target=http.run,daemon=True)
    thread.start()
    profiles=[]
    processes=[]
    server=None
    try:
        for index in range(3):
            response=requests.post('http://127.0.0.1:18080/v1/accounts',json={'username':f'Probe{index}','display_name':f'Pilot{index}','password':'LocalProbePassword1'},timeout=8)
            response.raise_for_status()
            profiles.append(response.json())
        server_id,generation=secrets.token_hex(16),secrets.token_hex(16)
        db.servers.insert_one({'_id':server_id,'match_id':generation,'type':args.type,'phase':'Waiting','host':'127.0.0.1','port':25150,'slots':[],'ready':False,'lease_until':time.time()+60,'last_occupied':time.time()})
        env=dict(os.environ,KYLR_SERVER_ID=server_id,KYLR_MATCH_ID=generation,KYLR_MATCH_TYPE=args.type,KYLR_PORT='25150',KYLR_API_URL='http://127.0.0.1:18080',KYLR_CONTROL_TOKEN=control)
        godot=os.getenv('GODOT',str(root.parent/'engine'/'bin'/'godot.windows.editor.x86_64.console.exe'))
        server_log=(reports/'server-probe.log').open('w',encoding='utf-8')
        server=subprocess.Popen([godot,'--headless','--path',str(root),'-s','res://tools/probe_online_server.gd'],env=env,stdout=server_log,stderr=subprocess.STDOUT)
        deadline=time.time()+20
        while time.time()<deadline:
            if db.servers.find_one({'_id':server_id})['ready']: break
            if server.poll() is not None: raise RuntimeError('Server stopped; inspect reports/online/server-probe.log')
            time.sleep(.1)
        assert db.servers.find_one({'_id':server_id})['ready'],'Server did not become ready'
        for index,profile in enumerate(profiles):
            if index==2: time.sleep(21)  # An active-match late join, not another countdown entrant.
            sid=db.sessions.find_one({'account':profile['player']['id']})['_id']
            assignment=app.extensions['store'].reserve(profile['player']['id'],sid,args.type)
            assert assignment,'Reservation failed'
            client_env=dict(os.environ,KYLR_PROBE_ASSIGNMENT=json.dumps(assignment),KYLR_PROBE_SECONDS='90',KYLR_PROBE_EXPECT_CONTINUATION='1',KYLR_PROBE_FIRE='1' if index==0 else '0',KYLR_PROBE_REPORT=str(reports/f'client-{index}.json'))
            log=(reports/f'client-{index}.log').open('w',encoding='utf-8')
            processes.append(subprocess.Popen([godot,'--headless','--path',str(root),'-s','res://tools/probe_online_client.gd'],env=client_env,stdout=log,stderr=subprocess.STDOUT))
            time.sleep(1)
        for process in processes: assert process.wait(timeout=110)==0,'Client failed; inspect its log'
        server.wait(timeout=40)
        rows=[json.loads((reports/f'client-{i}.json').read_text()) for i in range(3)]
        assert all(row['joined'] and row['max_roster']==3 and row['generations']>=2 for row in rows),rows
        assert all(row['finished'] for row in rows),rows
        assert rows[0]['moved'] and rows[0]['damaged'],rows
        for file in reports.glob('*-probe.log'):
            assert 'SCRIPT ERROR' not in file.read_text(encoding='utf-8'),file
        for i in range(3): assert 'SCRIPT ERROR' not in (reports/f'client-{i}.log').read_text(encoding='utf-8')
        print(json.dumps({'database':'MongoDB','type':args.type,'clients':rows},indent=2))
    finally:
        for process in [*processes,server]:
            if process and process.poll() is None: process.terminate(); process.wait(timeout=5)
        http.close()
        mongo.drop_database(db.name)
        mongo.close()

if __name__=='__main__': main()
