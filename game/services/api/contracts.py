"""Validation shared by account, loadout, matchmaking and server control routes."""
import hashlib
import re
import uuid

HEADS = ('projector', 'sentinel', 'porthole', 'raptor', 'arachne')
UPPER_BODIES = ('default', 'aegis', 'lamellar', 'vesper', 'conduit', 'reactor')
EMOTES = ('victory_chicken_dance', 'victory_gangnam_style', 'victory_hip_hop_dancing',
          'victory_macarena_dance', 'victory_wave_hip_hop_dance')
PALETTE = {'graphite':'333f48', 'silver':'aab5bd', 'white':'edf2f4', 'yellow':'ecb846',
           'orange':'d97b32', 'red':'b74740', 'magenta':'be438e', 'violet':'855ab5',
           'blue':'3878b4', 'cyan':'46bac8', 'teal':'398c82', 'green':'689649'}
DEFAULT_LOADOUT = {'head':'projector', 'upper_body':'default', 'emote':EMOTES[0], 'primary':'silver', 'secondary':'white'}
TYPES = ('DM', 'TDM', 'CTF', 'ELIMINATION', 'GUNGAME')
ADMIT_PHASES = ('Waiting', 'Countdown', 'Active')

class ApiError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status

def identifier():
    return str(uuid.uuid4())

def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def fields(body, allowed, required=()):
    if not isinstance(body, dict) or set(body) - set(allowed) or not set(required) <= set(body):
        raise ApiError('INVALID_REQUEST', 'The request has missing or unsupported fields.')
    return body

def name(value, username=False):
    pattern = r'[A-Za-z0-9._]{3,24}' if username else r'[A-Za-z0-9._]{1,20}'
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ApiError('INVALID_USERNAME' if username else 'INVALID_DISPLAY_NAME',
                       'Use ASCII letters, digits, dots or underscores within the displayed length limit.')
    return value

def password(value):
    if not isinstance(value, str) or not 12 <= len(value) <= 256:
        raise ApiError('INVALID_PASSWORD', 'Use a password containing 12–256 characters.')
    return value

def loadout(value):
    fields(value, DEFAULT_LOADOUT, set(DEFAULT_LOADOUT) - {'upper_body'})
    value = {'upper_body': 'default', **value}
    if any(not isinstance(item,str) for item in value.values()):
        raise ApiError('INVALID_LOADOUT', 'Choose available appearance IDs.')
    if value['head'] not in HEADS or value['emote'] not in EMOTES:
        raise ApiError('INVALID_LOADOUT', 'Choose an available head and authored victory emote.')
    if value['upper_body'] not in UPPER_BODIES:
        raise ApiError('INVALID_LOADOUT', 'Choose an available upper body.')
    if value['primary'] not in PALETTE or value['secondary'] not in PALETTE:
        raise ApiError('INVALID_LOADOUT', 'Choose colors from the available palette.')
    return dict(value)

def profile(account):
    return {'id':account['_id'], 'username':account['username'], 'display_name':account['display_name'],
            'loadout':{'upper_body':'default', **account['loadout']}}
