"""All capacity and ticket transitions are conditional single-document writes."""
import secrets
import time
from pymongo import ASCENDING, ReturnDocument
from .contracts import ADMIT_PHASES, ApiError, digest, identifier, profile
from .migrations import migrate

class Store:
    def __init__(self, database, clock=time.time):
        self.db, self.clock = database, clock
        migrate(database)
        database.accounts.create_index('username_key', unique=True)
        database.accounts.create_index('display_key', unique=True)
        database.sessions.create_index('credential_hash', unique=True)
        database.servers.create_index([('type', ASCENDING), ('lease_until', ASCENDING)])

    def server(self, server_id):
        return self.db.servers.find_one({'_id':server_id})

    def expire(self):
        now = self.clock()
        self.db.servers.update_many({}, {'$pull':{'slots':{'state':'reserved','expires':{'$lte':now}}}})
        self.db.servers.update_many({'lease_until':{'$lte':now}}, {'$set':{'ready':False}})

    def reserve(self, account_id, session_id, match_type):
        self.expire()
        token = secrets.token_urlsafe(32)
        slot = {'id':identifier(), 'account':account_id, 'session':session_id, 'ticket_hash':digest(token),
                'state':'reserved', 'expires':self.clock()+30.0}
        server = self.db.servers.find_one_and_update(
            {'type':match_type, 'ready':True, 'phase':{'$in':ADMIT_PHASES},
             'lease_until':{'$gt':self.clock()}, 'slots.account':{'$ne':account_id},
             '$expr':{'$lt':[{'$size':'$slots'},10]}},
            {'$push':{'slots':slot}}, return_document=ReturnDocument.AFTER)
        if not server: return None
        return {'server_id':server['_id'], 'match_id':server['match_id'], 'reservation_id':slot['id'],
                'host':server['host'], 'port':server['port'], 'ticket':token, 'expires_at':slot['expires']}

    def consume(self, server_id, match_id, ticket):
        if not isinstance(ticket,str) or not 20 <= len(ticket) <= 128:
            raise ApiError('INVALID_TICKET','The join ticket is invalid.',403)
        now = self.clock()
        slot_filter = {'ticket_hash':digest(ticket),'state':'reserved','expires':{'$gt':now}}
        before = self.db.servers.find_one_and_update(
            {'_id':server_id,'match_id':match_id,'ready':True,'phase':{'$in':ADMIT_PHASES},
             'lease_until':{'$gt':now}, 'slots':{'$elemMatch':slot_filter}},
            {'$set':{'slots.$.state':'admitted','slots.$.claimed_at':now}},
            return_document=ReturnDocument.BEFORE)
        if not before: raise ApiError('INVALID_TICKET','Ticket expired, was used, or belongs to another match.',403)
        slot = next(item for item in before['slots'] if item['ticket_hash']==digest(ticket))
        session = self.db.sessions.find_one({'_id':slot['session'],'revoked':False,'expires':{'$gt':now}})
        account = self.db.accounts.find_one({'_id':slot['account']})
        if not session or not account:
            self.release(server_id,slot['id'])
            raise ApiError('SESSION_EXPIRED','Sign in again before joining.',401)
        return {'player':profile(account),'reservation_id':slot['id']}

    def release(self, server_id, reservation_id):
        self.db.servers.update_one({'_id':server_id},{'$pull':{'slots':{'id':reservation_id}}})

    def heartbeat(self, server_id, body):
        now = self.clock()
        server = self.server(server_id)
        if not server: raise ApiError('UNKNOWN_SERVER','Server registration is missing.',404)
        accounts = body['accounts']
        admitted={slot['account'] for slot in server['slots'] if slot['state']=='admitted'}
        revoked=[account for account in accounts if account not in admitted]
        for slot in server['slots']:
            if slot['state']=='admitted' and slot['account'] in accounts:
                if not self.db.sessions.find_one({'_id':slot['session'],'revoked':False,'expires':{'$gt':now}}):
                    revoked.append(slot['account'])
        if server['match_id']!=body['match_id']:
            self.db.servers.update_one({'_id':server_id},{'$pull':{'slots':{'state':'reserved'}}})
        self.db.servers.update_one({'_id':server_id}, {'$set':{
            'ready':body['phase'] in ADMIT_PHASES,'phase':body['phase'],'match_id':body['match_id'],
            'lease_until':now+15,'last_occupied':now if accounts else server.get('last_occupied',now)}})
        self.db.port_leases.update_one({'_id':server['port'],'server':server_id},{'$set':{'until':now+15}})
        if body['phase'] in ADMIT_PHASES:
            self.db.launch_leases.update_one({'_id':server['type'],'server':server_id},{'$set':{'until':0}})
        self.db.servers.update_one({'_id':server_id}, {'$pull':{'slots':{
            'state':'admitted','account':{'$nin':accounts},'claimed_at':{'$lt':now-5}}}})
        self.expire()
        return {'retire':not accounts and not self.server(server_id)['slots'] and now-server.get('last_occupied',now)>60,
                'revoked_accounts':revoked}
