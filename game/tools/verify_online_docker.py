"""Verify the deployed API's scheduler and actual container-hosted ENet games."""
import argparse, json, os, secrets, subprocess, time
from pathlib import Path
import requests
import docker
from udp_impairment import ImpairedLink

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--type',choices=['DM','TDM','CTF'])
    parser.add_argument('--clients',type=int,choices=range(3,11),default=3)
    parser.add_argument('--seconds',type=int,default=50)
    parser.add_argument('--network-only',action='store_true',help='Disable client cosmetic callbacks; preserve transport, colliders and prediction.')
    parser.add_argument('--latency-ms',type=float,default=0)
    parser.add_argument('--loss',type=float,default=0)
    args=parser.parse_args()
    if not 0<=args.loss<.5 or args.latency_ms<0: parser.error('Use loss between 0 and 0.5, and nonnegative latency.')
    root=Path(__file__).resolve().parents[1]
    reports=root/'reports'/'online'
    profiles=[]
    session=requests.Session()
    for index in range(args.clients):
        identity='Dock'+secrets.token_hex(5)
        response=session.post('http://127.0.0.1:8080/v1/accounts',json={'username':identity,'display_name':identity,'password':'LocalProbePassword1'},timeout=8)
        if response.status_code==429:
            time.sleep(61)
            response=session.post('http://127.0.0.1:8080/v1/accounts',json={'username':identity,'display_name':identity,'password':'LocalProbePassword1'},timeout=8)
        response.raise_for_status()
        profiles.append(response.json())
    results={}
    network_metrics={}
    processes=[]
    assignments=[]
    links=[]
    try:
        for mode in [args.type] if args.type else ['DM','TDM','CTF']:
            processes=[]
            links=[]
            assignments=[]
            request_ids=[]
            started=time.time()
            for index,profile in enumerate(profiles):
                if index==2: time.sleep(21)
                headers={'Authorization':'Bearer '+profile['access_token']}
                response=session.post('http://127.0.0.1:8080/v1/matches',json={'type':mode},headers=headers,timeout=8)
                response.raise_for_status()
                request_id=response.json()['request_id']
                request_ids.append(request_id)
                deadline=time.time()+45
                while time.time()<deadline:
                    status=session.get('http://127.0.0.1:8080/v1/matches/'+request_id,headers=headers,timeout=8).json()
                    if 'error' in status: raise RuntimeError(status['error']['message'])
                    if status['state']=='Ready': break
                    time.sleep(.2)
                else: raise RuntimeError('Docker matchmaking did not finish')
                assignments.append(status['assignment'])
                path=reports/f'docker-{mode}-{index}.json'
                log=(reports/f'docker-{mode}-{index}.log').open('w',encoding='utf-8')
                duration=max(22,started+args.seconds+(10 if index==args.clients-1 else 0)-time.time())
                assignment=dict(status['assignment'])
                if args.latency_ms or args.loss:
                    link=ImpairedLink((assignment['host'],assignment['port']),args.latency_ms,args.loss,index)
                    links.append(link)
                    assignment.update(host='127.0.0.1',port=link.port)
                env=dict(os.environ,KYLR_PROBE_NETWORK_ONLY='1' if args.network_only else '0',KYLR_PROBE_ASSIGNMENT=json.dumps(assignment),KYLR_PROBE_SECONDS=str(duration),KYLR_PROBE_FIRE='1' if index==0 else '0',KYLR_PROBE_REPORT=str(path))
                processes.append(subprocess.Popen([os.getenv('GODOT',str(root.parent/'engine'/'bin'/'godot.windows.editor.x86_64.console.exe')),'--headless','--path',str(root),'-s','res://tools/probe_online_client.gd'],env=env,stdout=log,stderr=subprocess.STDOUT))
                time.sleep(1)
            assert len({item['server_id'] for item in assignments})==1,'Roster split into different servers'
            for index,process in enumerate(processes):
                if process.wait(timeout=args.seconds+30)!=0:
                    logs=docker.from_env(timeout=5).containers.get('kylr-'+assignments[0]['server_id']).logs().decode('utf-8')
                    (reports/f'docker-{mode}-server.log').write_text(logs,encoding='utf-8')
                    raise RuntimeError('Docker client failed; inspect reports')
                session.delete('http://127.0.0.1:8080/v1/matches/'+request_ids[index],headers={'Authorization':'Bearer '+profiles[index]['access_token']},timeout=30).raise_for_status()
            rows=[json.loads((reports/f'docker-{mode}-{i}.json').read_text()) for i in range(args.clients)]
            assert all(row['joined'] and row['max_roster']==args.clients and row['error']=='' for row in rows),rows
            assert rows[0]['shots']>0,'Server did not accept fire inputs'
            assert rows[-1]['canceled'],'Final occupant did not observe roster cancellation'
            for i in range(args.clients): assert 'SCRIPT ERROR' not in (reports/f'docker-{mode}-{i}.log').read_text(encoding='utf-8')
            results[mode]=rows
            network_metrics[mode]={'network_only':args.network_only,'clients':args.clients,'rtt_ms':args.latency_ms,'loss':args.loss,'wall_seconds':time.time()-started,'datagrams':sum(link.count for link in links),'dropped':sum(link.dropped for link in links),'udp_bytes':sum(link.bytes for link in links)}
            (reports/'docker-network.json').write_text(json.dumps(network_metrics,indent=2),encoding='utf-8')
            for link in links: link.close()
            links=[]
            (reports/'docker-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
            client=docker.from_env(timeout=5)
            logs=client.containers.get('kylr-'+assignments[0]['server_id']).logs().decode('utf-8')
            (reports/f'docker-{mode}-server.log').write_text(logs,encoding='utf-8')
            assert 'ERROR:' not in logs,logs[-2000:]
            # These are test-created empty servers; normal deployment retirement is 60s.
            client.containers.get('kylr-'+assignments[0]['server_id']).stop(timeout=3)
        print(json.dumps(results,indent=2))
    finally:
        if assignments:
            try:
                logs=docker.from_env(timeout=5).containers.get('kylr-'+assignments[0]['server_id']).logs().decode('utf-8')
                (reports/f'docker-{mode}-server.log').write_text(logs,encoding='utf-8')
            except docker.errors.NotFound:
                pass
        for process in processes:
            if process.poll() is None: process.terminate(); process.wait(timeout=5)
        for profile in profiles:
            try:
                session.delete('http://127.0.0.1:8080/v1/sessions',headers={'Authorization':'Bearer '+profile['access_token']},timeout=30)
            except requests.RequestException:
                pass
        for link in links: link.close()

if __name__=='__main__': main()
