"""Idempotent forward migrations. Unknown schemas fail closed before serving."""
from .contracts import DEFAULT_LOADOUT

SCHEMA_VERSION = 1

def migrate(database):
    state = database.schema.find_one({'_id': 'accounts'}) or {'version': 0}
    if state['version'] > SCHEMA_VERSION:
        raise RuntimeError('Database schema is newer than this API; use the matching release.')
    if state['version'] < 1:
        for key, value in DEFAULT_LOADOUT.items():
            database.accounts.update_many({f'loadout.{key}': {'$exists': False}},
                                          {'$set': {f'loadout.{key}': value}})
        database.accounts.update_many({'schema_version': {'$exists': False}},
                                      {'$set': {'schema_version': 1}})
        database.schema.update_one({'_id': 'accounts'}, {'$set': {'version': 1}}, upsert=True)
