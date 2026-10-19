import concurrent.futures
import time
import os
import secrets
import mongomock
import pytest
from services.api.app import create_app

class NoScheduler:
    def ensure(self,_kind): pass

@pytest.fixture
def app():
    uri=os.getenv('MONGO_TEST_URI')
    if uri:
        from pymongo import MongoClient
        client=MongoClient(uri,serverSelectionTimeoutMS=3000)
        database=client['kylr_api_test_'+secrets.token_hex(4)]
    else:
        client=mongomock.MongoClient()
        database=client.kylr
    application=create_app(database,
        {'JWT_SECRET':'test-access-signing-key-'+('x'*32),'CONTROL_TOKEN':'test-control-'+('y'*32),
         'MATCH_TIMEOUT':0.2},NoScheduler())
    yield application
    for worker in application.extensions['match_workers']: worker.join(timeout=2)
    client.drop_database(database.name)
    client.close()

def register(client,index=0):
    response=client.post('/v1/accounts',json={'username':f'user{index}','display_name':f'Pilot{index}',
                                            'password':'a-long-test-password'})
    assert response.status_code==201
    return response.json

def headers(session): return {'Authorization':'Bearer '+session['access_token']}

def ready_server(app):
    store=app.extensions['store']
    store.db.servers.insert_one({'_id':'test-server','match_id':'generation-1','type':'CTF',
        'host':'127.0.0.1','port':25000,'phase':'Active','ready':True,'slots':[],
        'lease_until':time.time()+100,'last_occupied':time.time()})
    return store

def test_registration_names_password_hashing_and_case_insensitive_uniqueness(app):
    client=app.test_client()
    session=register(client)
    account=app.extensions['store'].db.accounts.find_one()
    assert account['password_hash'].startswith('$argon2id$')
    assert 'password' not in account and 'password_hash' not in session['player']
    assert client.post('/v1/accounts',json={'username':'other','display_name':'pilot0',
        'password':'a-long-test-password'}).status_code==409
    assert client.post('/v1/accounts',json={'username':'third','display_name':'bad-name',
        'password':'a-long-test-password'}).status_code==400
    assert client.get('/v1/me').status_code==401
    assert client.get('/v1/me',headers=headers(session)).json['player']['display_name']=='Pilot0'

def test_refresh_rotation_logout_and_authentication(app):
    client=app.test_client()
    session=register(client)
    rotated=client.post('/v1/sessions/refresh',json={'refresh_token':session['refresh_token']})
    assert rotated.status_code==200
    assert client.post('/v1/sessions/refresh',json={'refresh_token':session['refresh_token']}).status_code==401
    assert client.delete('/v1/sessions',headers=headers(rotated.json)).status_code==200
    assert client.get('/v1/me',headers=headers(session)).status_code==401
    assert client.post('/v1/sessions/refresh',json={'refresh_token':rotated.json['refresh_token']}).status_code==401


def test_logout_cancels_pending_matchmaking(app):
    client=app.test_client()
    session=register(client)
    response=client.post('/v1/matches',json={'type':'DM'},headers=headers(session))
    assert response.status_code==202
    assert response.json['timeout_seconds']==app.config['MATCH_TIMEOUT']
    assert client.delete('/v1/sessions',headers=headers(session)).status_code==200
    record=app.extensions['store'].db.match_requests.find_one({'_id':response.json['request_id']})
    assert record['state']=='Canceled'


def test_atlas_connection_string_can_omit_a_database(monkeypatch):
    client=mongomock.MongoClient()
    monkeypatch.setattr('services.api.app.MongoClient',lambda *_args,**_kwargs:client)
    app=create_app(configuration={'JWT_SECRET':'access-'+'x'*40,'CONTROL_TOKEN':'control-'+'y'*40,
        'MONGO_URI':'mongodb+srv://example.invalid/'},scheduler=NoScheduler())
    assert app.extensions['store'].db.name=='kylr'

def test_loadout_catalog_is_validated_and_saved(app):
    client=app.test_client()
    session=register(client)
    value={'head':'raptor','emote':'victory_gangnam_style','primary':'red','secondary':'cyan'}
    response=client.put('/v1/me/loadout',json=value,headers=headers(session))
    assert response.json['player']['loadout']==value
    value['head']='invented-head'
    assert client.put('/v1/me/loadout',json=value,headers=headers(session)).status_code==400
    value['head']='raptor'
    value['primary']=[]
    assert client.put('/v1/me/loadout',json=value,headers=headers(session)).status_code==400

def test_heartbeat_revokes_departed_sessions_and_clears_old_generation_tickets(app):
    store=ready_server(app)
    session=register(app.test_client())
    account=session['player']['id']
    sid=store.db.sessions.find_one({'account':account})['_id']
    ticket=store.reserve(account,sid,'CTF')
    store.consume(ticket['server_id'],ticket['match_id'],ticket['ticket'])
    store.db.sessions.update_one({'_id':sid},{'$set':{'revoked':True}})
    response=store.heartbeat('test-server',{'match_id':'generation-1','phase':'Active','accounts':[account]})
    assert response['revoked_accounts']==[account]
    store.release('test-server',ticket['reservation_id'])
    store.db.sessions.update_one({'_id':sid},{'$set':{'revoked':False}})
    old=store.reserve(account,sid,'CTF')
    store.heartbeat('test-server',{'match_id':'generation-2','phase':'Waiting','accounts':[]})
    assert store.server('test-server')['slots']==[]
    assert store.server('test-server')['match_id']=='generation-2'

def test_unhealthy_server_and_empty_instance_are_retired(app):
    store=ready_server(app)
    store.db.servers.update_one({'_id':'test-server'},{'$set':{'lease_until':time.time()-1}})
    store.expire()
    assert not store.server('test-server')['ready']
    store.db.servers.update_one({'_id':'test-server'},{'$set':{'last_occupied':time.time()-61}})
    assert store.heartbeat('test-server',{'match_id':'generation-1','phase':'Waiting','accounts':[]})['retire']
    assert not store.server('test-server')['ready']

def test_atomic_capacity_ticket_binding_replay_and_revoked_session(app):
    store=ready_server(app)
    # Directly provision identities to keep a concurrency test independent of rate limits/hash cost.
    for index in range(24):
        store.db.accounts.insert_one({'_id':str(index),'username':f'user{index}',
            'username_key':f'user{index}','display_name':f'Pilot{index}','display_key':f'pilot{index}',
            'loadout':{'head':'projector','emote':'victory_chicken_dance','primary':'silver','secondary':'white'}})
        store.db.sessions.insert_one({'_id':str(index),'account':str(index),'credential_hash':str(index),
                                     'revoked':False,'expires':time.time()+100})
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
        results=list(pool.map(lambda i:store.reserve(str(i),str(i),'CTF'),range(24)))
    assignments=[item for item in results if item]
    assert len(assignments)==10
    assert len(store.server('test-server')['slots'])==10
    admission=assignments[0]
    with pytest.raises(Exception): store.consume('wrong-server','generation-1',admission['ticket'])
    with pytest.raises(Exception): store.consume('test-server','wrong-generation',admission['ticket'])
    assert store.consume('test-server','generation-1',admission['ticket'])['player']['display_name'].startswith('Pilot')
    with pytest.raises(Exception): store.consume('test-server','generation-1',admission['ticket'])
    revoked=assignments[1]
    slot=next(item for item in store.server('test-server')['slots'] if item['id']==revoked['reservation_id'])
    store.db.sessions.update_one({'_id':slot['session']},{'$set':{'revoked':True}})
    with pytest.raises(Exception): store.consume('test-server','generation-1',revoked['ticket'])
    assert len(store.server('test-server')['slots'])==9

def test_expiry_cancel_and_finished_servers(app):
    store=ready_server(app)
    session=register(app.test_client())
    slot=store.reserve(session['player']['id'],'missing-session','CTF')
    store.db.servers.update_one({'_id':'test-server'},{'$set':{'slots.0.expires':time.time()-1}})
    with pytest.raises(Exception): store.consume('test-server','generation-1',slot['ticket'])
    store.expire()
    assert not store.server('test-server')['slots']
    store.db.servers.update_one({'_id':'test-server'},{'$set':{'phase':'Finished'}})
    assert store.reserve('other','session','CTF') is None

def test_match_request_forbids_client_rules_and_control_requires_private_credentials(app):
    client=app.test_client()
    session=register(client)
    assert client.post('/v1/matches',json={'type':'DM','map':'faceoff'},headers=headers(session)).status_code==400
    assert client.post('/internal/servers/unknown/admit',json={'match_id':'a','ticket':'forged'}).status_code==403
    response=client.post('/v1/matches',json={'type':'DM'},headers=headers(session))
    assert response.status_code==202
    assert client.delete('/v1/matches/'+response.json['request_id'],headers=headers(session)).json['state']=='Canceled'

def test_released_admission_is_removed_on_the_next_heartbeat(app):
    store=ready_server(app)
    session=register(app.test_client())
    account=session['player']['id']
    sid=store.db.sessions.find_one({'account':account})['_id']
    assignment=store.reserve(account,sid,'CTF')
    store.consume('test-server','generation-1',assignment['ticket'])
    store.release('test-server',assignment['reservation_id'])
    response=store.heartbeat('test-server',{'match_id':'generation-1','phase':'Active','accounts':[account]})
    assert response['revoked_accounts']==[account]


def test_delayed_pre_admission_heartbeat_cannot_remove_loading_player(app):
    store=ready_server(app)
    session=register(app.test_client())
    account=session['player']['id']
    sid=store.db.sessions.find_one({'account':account})['_id']
    assignment=store.reserve(account,sid,'CTF')
    store.consume('test-server','generation-1',assignment['ticket'])
    store.db.servers.update_one({'_id':'test-server'},{'$set':{'slots.0.claimed_at':time.time()-8}})
    store.heartbeat('test-server',{'match_id':'generation-1','phase':'Countdown','accounts':[]})
    assert len(store.server('test-server')['slots'])==1
    response=store.heartbeat('test-server',{'match_id':'generation-1','phase':'Countdown','accounts':[account]})
    assert not response['revoked_accounts']
    assert store.server('test-server')['slots'][0]['seen']
    store.heartbeat('test-server',{'match_id':'generation-1','phase':'Countdown','accounts':[]})
    assert not store.server('test-server')['slots']


@pytest.mark.skipif(not os.getenv('MONGO_TEST_URI'),reason='MongoDB positional multi-slot updates require the real database')
def test_each_ticket_consumes_its_own_slot(app):
    store=ready_server(app)
    accounts=[]
    for index in range(3):
        session=register(app.test_client(),index)
        account=session['player']['id']
        accounts.append(account)
        sid=store.db.sessions.find_one({'account':account})['_id']
        ticket=store.reserve(account,sid,'CTF')
        assert store.consume('test-server','generation-1',ticket['ticket'])['player']['id']==account
    assert all(slot['state']=='admitted' for slot in store.server('test-server')['slots'])
    assert not store.heartbeat('test-server',{'match_id':'generation-1','phase':'Active','accounts':accounts})['revoked_accounts']
