"""Verify persistent accounts and recovery of a test-owned local game instance."""
import json
import secrets
import time
from pathlib import Path
import requests
import docker
from pymongo import MongoClient

BASE='http://127.0.0.1:8080'
def ready():
    deadline=time.time()+40
    while time.time()<deadline:
        try:
            if requests.get(BASE+'/healthz',timeout=2).status_code==200: return
        except requests.RequestException: pass
        time.sleep(.5)
    raise RuntimeError('Local API did not recover.')

def assignment(session,headers):
    response=session.post(BASE+'/v1/matches',json={'type':'DM'},headers=headers,timeout=8)
    response.raise_for_status()
    request_id=response.json()['request_id']
    deadline=time.time()+45
    while time.time()<deadline:
        result=session.get(BASE+'/v1/matches/'+request_id,headers=headers,timeout=8)
        result.raise_for_status()
        state=result.json()
        if state['state']=='Ready': return request_id,state['assignment']
        if state.get('error'): raise RuntimeError(state['error']['code'])
        time.sleep(.2)
    raise RuntimeError('Replacement game did not become ready.')

def main():
    client=docker.from_env(timeout=10)
    session=requests.Session()
    identity='Recovery'+secrets.token_hex(5)
    body={'username':identity,'display_name':identity,'password':'LocalRecoveryProbePassword1'}
    response=session.post(BASE+'/v1/accounts',json=body,timeout=8)
    if response.status_code==429:
        time.sleep(61)
        response=session.post(BASE+'/v1/accounts',json=body,timeout=8)
    response.raise_for_status()
    profile=response.json()
    headers={'Authorization':'Bearer '+profile['access_token']}
    appearance={'head':'raptor','emote':'victory_gangnam_style','primary':'red','secondary':'cyan'}
    session.put(BASE+'/v1/me/loadout',json=appearance,headers=headers,timeout=8).raise_for_status()
    result={}
    for component in ['api','mongo']:
        client.containers.get('kylr-online-'+component+'-1').restart(timeout=5)
        ready()
        restored=session.get(BASE+'/v1/me',headers=headers,timeout=8)
        restored.raise_for_status()
        assert restored.json()['player']['loadout']==appearance
        result[component+'_restart_preserved_account']=True
    request_id,old=assignment(session,headers)
    mongo=MongoClient('mongodb://127.0.0.1:27017',serverSelectionTimeoutMS=3000)
    record=mongo.kylr.servers.find_one({'_id':old['server_id']})
    assert record['phase']=='Waiting' and {slot['account'] for slot in record['slots']}=={profile['player']['id']},'Refusing to interrupt a shared game.'
    container=client.containers.get('kylr-'+old['server_id'])
    assert container.labels.get('kylr.server')==old['server_id']
    container.kill()
    deadline=time.time()+25
    while time.time()<deadline:
        if mongo.kylr.servers.find_one({'_id':old['server_id']})['lease_until']<=time.time(): break
        time.sleep(.5)
    else: raise RuntimeError('Crashed server lease did not expire.')
    session.delete(BASE+'/v1/matches/'+request_id,headers=headers,timeout=8).raise_for_status()
    request_id,new=assignment(session,headers)
    assert new['server_id']!=old['server_id']
    result['crashed_game_replaced']=True
    session.delete(BASE+'/v1/matches/'+request_id,headers=headers,timeout=8).raise_for_status()
    session.delete(BASE+'/v1/sessions',headers=headers,timeout=8).raise_for_status()
    client.containers.get('kylr-'+new['server_id']).stop(timeout=3)
    mongo.close()
    path=Path(__file__).resolve().parents[1]/'reports/online/service-recovery.json'
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__': main()
