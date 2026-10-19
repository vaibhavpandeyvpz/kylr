"""Flask accounts, rotating sessions, matchmaking and private admission control."""
import os
import secrets
import threading
import time
import logging
import json
from datetime import datetime, timezone
from functools import wraps
from contextlib import contextmanager
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from flask import Flask, g, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError
from pymongo.errors import PyMongoError
from .contracts import (ApiError, DEFAULT_LOADOUT, TYPES, digest, fields, identifier,
                        loadout, name, password, profile)
from .store import Store

def create_app(database=None, configuration=None, scheduler=None, clock=time.time):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=8192, JWT_SECRET=os.getenv('JWT_SECRET',''),
                      CONTROL_TOKEN=os.getenv('CONTROL_TOKEN',''), ACCESS_SECONDS=900,
                      SESSION_SECONDS=30*86400, MATCH_TIMEOUT=int(os.getenv('MATCH_TIMEOUT_SECONDS','180')),
                      MONGO_URI=os.getenv('MONGO_URI','mongodb://127.0.0.1:27017/kylr'))
    app.config.update(configuration or {})
    if not 0 < float(app.config['MATCH_TIMEOUT']) <= 600:
        raise RuntimeError('MATCH_TIMEOUT_SECONDS must be between 1 and 600 seconds.')
    proxy_hops = int(os.getenv('TRUST_PROXY_HOPS','0'))
    if proxy_hops not in (0,1):
        raise RuntimeError('TRUST_PROXY_HOPS must be 0 or 1.')
    if proxy_hops:
        # Enable only behind the single managed Render ingress, never a direct listener.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    if len(app.config['JWT_SECRET'])<32 or len(app.config['CONTROL_TOKEN'])<32 or app.config['JWT_SECRET']==app.config['CONTROL_TOKEN']:
        raise RuntimeError('Provide independent JWT_SECRET and CONTROL_TOKEN values of at least 32 characters.')
    if database is None:
        database = MongoClient(app.config['MONGO_URI'],serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000, socketTimeoutMS=10000, maxPoolSize=20).get_default_database('kylr')
    store = Store(database,clock)
    app.extensions['store'] = store
    hasher = PasswordHasher(time_cost=3,memory_cost=65536,parallelism=4)
    dummy_hash = hasher.hash(secrets.token_urlsafe(32))
    password_slots = threading.BoundedSemaphore(2)
    match_slots = threading.BoundedSemaphore(16)

    @contextmanager
    def password_work():
        if not password_slots.acquire(blocking=False):
            raise ApiError('SERVICE_BUSY','Account service is busy. Retry shortly.',429)
        try:
            yield
        finally:
            password_slots.release()
    if scheduler is None:
        if os.getenv('SCHEDULER','docker') == 'edgegap':
            from .edgegap import EdgegapScheduler
            scheduler = EdgegapScheduler(store,app.config['CONTROL_TOKEN'])
        else:
            if os.getenv('SCHEDULER','docker') not in ('docker','local'):
                raise RuntimeError('SCHEDULER must be docker, local or edgegap.')
            from .scheduler import Scheduler
            scheduler = Scheduler(store,app.config['CONTROL_TOKEN'])
    app.extensions['scheduler'] = scheduler
    app.extensions['match_workers'] = []
    if hasattr(scheduler, 'start_monitor'): scheduler.start_monitor()

    @app.before_request
    def begin_request():
        g.request_id = secrets.token_hex(8)
        g.started = time.perf_counter()

    @app.after_request
    def finish_request(response):
        response.headers['X-Request-ID'] = g.request_id
        # Route templates never contain account IDs, tickets, or credentials.
        logging.getLogger('kylr.requests').info(json.dumps({
            'request_id': g.request_id, 'method': request.method,
            'route': str(request.url_rule) if request.url_rule else 'unmatched',
            'status': response.status_code,
            'duration_ms': round((time.perf_counter()-g.started)*1000, 2)}))
        return response

    @app.errorhandler(ApiError)
    def api_error(error):
        return jsonify(error={'code':error.code,'message':error.message}),error.status

    @app.errorhandler(413)
    def too_large(_error): return api_error(ApiError('INVALID_REQUEST','Request is too large.',413))

    @app.errorhandler(400)
    def malformed(_error): return api_error(ApiError('INVALID_REQUEST','Send a valid JSON object.'))

    @app.errorhandler(PyMongoError)
    def unavailable(_error): return api_error(ApiError('SERVICE_UNAVAILABLE','The account database is unavailable. Retry shortly.',503))

    def body(allowed,required=()):
        return fields(request.get_json(silent=True),allowed,required)

    def rate(scope,limit):
        # Atomic database counters work across API workers. Never use client-supplied forwarded IPs.
        identity = g.account['_id'] if hasattr(g,'account') else request.remote_addr
        key = digest(f'{scope}:{identity}:{int(clock()//60)}')
        entry = database.rate_limits.find_one_and_update({'_id':key},
            {'$inc':{'count':1},'$setOnInsert':{'expires':clock()+120,
                'delete_at':datetime.fromtimestamp(clock()+120,timezone.utc)}},upsert=True,
            return_document=ReturnDocument.AFTER)
        if entry['count']>limit: raise ApiError('RATE_LIMITED','Please wait before trying again.',429)

    def authenticated(function):
        @wraps(function)
        def guarded(*args,**kwargs):
            bearer = request.headers.get('Authorization','')
            if not bearer.startswith('Bearer '): raise ApiError('UNAUTHENTICATED','Sign in to continue.',401)
            try:
                claims = jwt.decode(bearer[7:],app.config['JWT_SECRET'],algorithms=['HS256'],
                    audience='kylr-client',issuer='kylr',options={'require':['sub','sid','exp','iat']})
            except jwt.InvalidTokenError:
                raise ApiError('SESSION_EXPIRED','Your session expired. Sign in again.',401)
            session = database.sessions.find_one({'_id':claims['sid'],'account':claims['sub'],
                                                 'revoked':False,'expires':{'$gt':clock()}})
            account = database.accounts.find_one({'_id':claims['sub']})
            if not session or not account: raise ApiError('SESSION_EXPIRED','Sign in again.',401)
            g.account,g.session = account,session
            return function(*args,**kwargs)
        return guarded

    def controlled(function):
        @wraps(function)
        def guarded(*args,**kwargs):
            supplied = request.headers.get('X-Control-Token','')
            server = store.server(kwargs['server_id']) if 'server_id' in kwargs else None
            accepted = secrets.compare_digest(digest(supplied),server['control_hash']) if server and server.get('control_hash') else secrets.compare_digest(supplied,app.config['CONTROL_TOKEN'])
            if not accepted:
                raise ApiError('FORBIDDEN','Server credentials are required.',403)
            return function(*args,**kwargs)
        return guarded

    def envelope(account,session,refresh):
        expires = int(clock())+int(app.config['ACCESS_SECONDS'])
        access = jwt.encode({'sub':account['_id'],'sid':session['_id'],'iat':int(clock()),
                             'exp':expires,'iss':'kylr','aud':'kylr-client'},
                             app.config['JWT_SECRET'],algorithm='HS256')
        return {'access_token':access,'refresh_token':refresh,'expires_at':expires,'player':profile(account)}

    def new_session(account):
        refresh = secrets.token_urlsafe(48)
        session = {'_id':identifier(),'account':account['_id'],'credential_hash':digest(refresh),
                   'expires':clock()+app.config['SESSION_SECONDS'],'revoked':False,
                   'delete_at':datetime.fromtimestamp(clock()+app.config['SESSION_SECONDS'],timezone.utc)}
        database.sessions.insert_one(session)
        return envelope(account,session,refresh)

    @app.get('/healthz')
    def health():
        database.command('ping')
        return {'ready':True,'protocol':1}

    @app.get('/internal/status')
    @controlled
    def service_status():
        store.expire()
        now = clock()
        return {'schema': database.schema.find_one({'_id':'accounts'})['version'],
                'servers_live': database.servers.count_documents({'lease_until':{'$gt':now}}),
                'servers_ready': database.servers.count_documents({'ready':True}),
                'servers_stale': database.servers.count_documents({'lease_until':{'$lte':now}}),
                'requests_searching': database.match_requests.count_documents({'state':{'$in':['Searching','Starting server']}})}

    @app.post('/v1/accounts')
    def register():
        rate('registration',5)
        data = body(('username','password','display_name'),('username','password','display_name'))
        username,display = name(data['username'],True),name(data['display_name'])
        supplied = password(data['password'])
        with password_work():
            password_hash = hasher.hash(supplied)
        account = {'_id':identifier(),'username':username,'username_key':username.lower(),
                   'display_name':display,'display_key':display.lower(),
                   'password_hash':password_hash,
                   'loadout':dict(DEFAULT_LOADOUT),'schema_version':1,'created':clock()}
        try: database.accounts.insert_one(account)
        except DuplicateKeyError: raise ApiError('NAME_TAKEN','That username or display name is already taken.',409)
        return new_session(account),201

    @app.post('/v1/sessions')
    def login():
        rate('login',10)
        data = body(('username','password'),('username','password'))
        username = name(data['username'],True)
        supplied = password(data['password'])
        account = database.accounts.find_one({'username_key':username.lower()})
        with password_work():
            try: hasher.verify(account['password_hash'] if account else dummy_hash,supplied)
            except VerificationError: account = None
            if not account: raise ApiError('LOGIN_FAILED','Username or password was not accepted.',401)
            if hasher.check_needs_rehash(account['password_hash']):
                database.accounts.update_one({'_id':account['_id']},{'$set':{'password_hash':hasher.hash(supplied)}})
        return new_session(account)

    @app.post('/v1/sessions/refresh')
    def refresh():
        rate('refresh',30)
        data = body(('refresh_token',),('refresh_token',))
        token = data['refresh_token']
        if not isinstance(token,str) or not 20<=len(token)<=128: raise ApiError('SESSION_EXPIRED','Sign in again.',401)
        replacement = secrets.token_urlsafe(48)
        session = database.sessions.find_one_and_update(
            {'credential_hash':digest(token),'revoked':False,'expires':{'$gt':clock()}},
            {'$set':{'credential_hash':digest(replacement)}},return_document=ReturnDocument.AFTER)
        if not session: raise ApiError('SESSION_EXPIRED','Sign in again.',401)
        account = database.accounts.find_one({'_id':session['account']})
        if not account: raise ApiError('SESSION_EXPIRED','Sign in again.',401)
        return envelope(account,session,replacement)

    @app.delete('/v1/sessions')
    @authenticated
    def logout():
        database.sessions.update_one({'_id':g.session['_id']},{'$set':{'revoked':True}})
        database.match_requests.update_many({'session':g.session['_id'],
            'state':{'$in':['Searching','Starting server','Ready']}},{'$set':{'state':'Canceled'}})
        database.servers.update_many({}, {'$pull':{'slots':{'session':g.session['_id'],'state':'reserved'}}})
        return {'revoked':True}

    @app.get('/v1/me')
    @authenticated
    def me(): return {'player':profile(g.account)}

    @app.put('/v1/me/loadout')
    @authenticated
    def save_loadout():
        value = loadout(body(DEFAULT_LOADOUT,DEFAULT_LOADOUT))
        database.accounts.update_one({'_id':g.account['_id']},{'$set':{'loadout':value}})
        g.account['loadout']=value
        return {'player':profile(g.account)}

    def find_match(request_id):
        item = database.match_requests.find_one({'_id':request_id,'account':g.account['_id'],'session':g.session['_id']})
        if not item: raise ApiError('NOT_FOUND','Match request was not found.',404)
        return item

    def run_match(request_id,account_id,session_id,match_type):
        deadline = clock()+app.config['MATCH_TIMEOUT']
        next_launch = 0
        assignment = None
        try:
            while clock()<deadline:
                record = database.match_requests.find_one({'_id':request_id})
                if not record or record['state']=='Canceled': return
                assignment = store.reserve(account_id,session_id,match_type)
                if assignment:
                    accepted = database.match_requests.update_one({'_id':request_id,'state':{'$ne':'Canceled'}},
                        {'$set':{'state':'Ready','assignment':assignment}})
                    if not accepted.modified_count: store.release(assignment['server_id'],assignment['reservation_id'])
                    return
                if clock()>=next_launch:
                    database.match_requests.update_one({'_id':request_id,'state':{'$ne':'Canceled'}},{'$set':{'state':'Starting server'}})
                    scheduler.ensure(match_type)
                    next_launch=clock()+2
                time.sleep(1)
            raise ApiError('MATCH_TIMEOUT','No server became ready in time. Retry from the lobby.',503)
        except Exception as error:
            # No exception body, password, bearer token or ticket enters logs/responses.
            code = error.code if isinstance(error,ApiError) else 'SERVER_START_FAILED'
            message = error.message if isinstance(error,ApiError) else 'The server could not start. Retry from the lobby.'
            database.match_requests.update_one({'_id':request_id,'state':{'$ne':'Canceled'}},
                {'$set':{'state':'Failed','error':{'code':code,'message':message}}})
        finally:
            match_slots.release()

    @app.post('/v1/matches')
    @authenticated
    def matchmaking():
        rate('play',20)
        data = body(('type',),('type',))
        if data['type'] not in TYPES: raise ApiError('INVALID_MATCH_TYPE','Choose DM, TDM or CTF.')
        pending = database.match_requests.find_one({'account':g.account['_id'], 'session':g.session['_id'],
            'state':{'$in':['Searching','Starting server']}, 'deadline':{'$gt':clock()}})
        if pending:
            return {'request_id':pending['_id'],'state':pending['state'],
                'timeout_seconds':max(1,pending['deadline']-clock())},202
        if not match_slots.acquire(blocking=False):
            raise ApiError('SERVICE_BUSY','Matchmaking is busy. Retry shortly.',429)
        record = {'_id':identifier(),'account':g.account['_id'],'session':g.session['_id'],
                  'type':data['type'],'state':'Searching','created':clock(),
                  'deadline':clock()+app.config['MATCH_TIMEOUT'],
                  'delete_at':datetime.fromtimestamp(clock()+86400,timezone.utc)}
        try:
            database.match_requests.insert_one(record)
        except Exception:
            match_slots.release()
            raise
        worker=threading.Thread(target=run_match,args=(record['_id'],record['account'],record['session'],record['type']),daemon=True)
        app.extensions['match_workers']=[item for item in app.extensions['match_workers'] if item.is_alive()]
        app.extensions['match_workers'].append(worker)
        worker.start()
        return {'request_id':record['_id'],'state':'Searching',
                'timeout_seconds':app.config['MATCH_TIMEOUT']},202

    @app.get('/v1/matches/<request_id>')
    @authenticated
    def match_status(request_id):
        item = find_match(request_id)
        if item['state'] in ('Searching','Starting server') and item.get('deadline',item['created']+app.config['MATCH_TIMEOUT']) <= clock():
            database.match_requests.update_one({'_id':item['_id'],'state':item['state']},
                {'$set':{'state':'Failed','error':{'code':'MATCH_TIMEOUT','message':'Server startup timed out. Retry for a fresh request.'}}})
            item = find_match(request_id)
        response = {'request_id':item['_id'],'state':item['state']}
        if item.get('assignment'):
            if item['assignment']['expires_at']<=clock() and item['state']=='Ready':
                store.release(item['assignment']['server_id'],item['assignment']['reservation_id'])
                return {'request_id':item['_id'],'state':'Failed','error':{'code':'TICKET_EXPIRED','message':'Join ticket expired. Retry for a fresh ticket.'}}
            response['assignment']=item['assignment']
        if item.get('error'): response['error']=item['error']
        return response

    @app.delete('/v1/matches/<request_id>')
    @authenticated
    def cancel(request_id):
        item = database.match_requests.find_one_and_update({'_id':find_match(request_id)['_id']},
            {'$set':{'state':'Canceled'}},return_document=ReturnDocument.BEFORE)
        if item.get('assignment'): store.release(item['assignment']['server_id'],item['assignment']['reservation_id'])
        return {'state':'Canceled'}

    @app.post('/internal/servers/<server_id>/heartbeat')
    @controlled
    def heartbeat(server_id):
        data = body(('match_id','phase','accounts'),('match_id','phase','accounts'))
        if data['phase'] not in ('Waiting','Countdown','Active','Finished','Canceled') or not isinstance(data['accounts'],list) or len(data['accounts'])>10 or any(not isinstance(item,str) for item in data['accounts']) or not isinstance(data['match_id'],str):
            raise ApiError('INVALID_REQUEST','Invalid server heartbeat.')
        return store.heartbeat(server_id,data)

    @app.post('/internal/servers/<server_id>/admit')
    @controlled
    def admit(server_id):
        data = body(('match_id','ticket'),('match_id','ticket'))
        return store.consume(server_id,data['match_id'],data['ticket'])

    @app.post('/internal/servers/<server_id>/release')
    @controlled
    def release(server_id):
        data = body(('reservation_id',),('reservation_id',))
        store.release(server_id,data['reservation_id'])
        return {'released':True}

    return app

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,format='%(message)s')
    from waitress import serve
    serve(create_app(),host=os.getenv('KYLR_API_BIND','0.0.0.0'),port=int(os.getenv('PORT','8080')))
