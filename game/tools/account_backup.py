"""Offline-consistent account backup and isolated restore. No active tickets restored."""
import argparse
import gzip
import hashlib
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bson import json_util
from pymongo import MongoClient
from services.api.migrations import SCHEMA_VERSION, migrate

def backup(database, destination):
    # Stop account writes while taking a production backup. This local tool
    # intentionally excludes sessions, match requests and live server leases.
    content = json_util.dumps({'schema': SCHEMA_VERSION,
                              'accounts': list(database.accounts.find())}).encode('utf-8')
    path = Path(destination)
    with path.open('xb') as output:
        output.write(gzip.compress(content))
    path.with_suffix(path.suffix+'.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest(), encoding='ascii')
    return len(json_util.loads(content)['accounts'])

def restore(database, source):
    # Restores only into an entirely empty database; no overwrite switch.
    if database.list_collection_names():
        raise ValueError('Restore requires an empty, separate database.')
    path = Path(source)
    expected = path.with_suffix(path.suffix+'.sha256').read_text(encoding='ascii').strip()
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Backup checksum does not match.')
    data = json_util.loads(gzip.decompress(path.read_bytes()))
    if data['schema'] > SCHEMA_VERSION: raise ValueError('Backup schema is newer than this release.')
    if data['accounts']: database.accounts.insert_many(data['accounts'])
    migrate(database)
    database.accounts.create_index('username_key',unique=True)
    database.accounts.create_index('display_key',unique=True)
    return len(data['accounts'])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['backup','restore'])
    parser.add_argument('--uri',default='mongodb://127.0.0.1:27017')
    parser.add_argument('--database',required=True)
    parser.add_argument('--file',required=True)
    args = parser.parse_args()
    with MongoClient(args.uri,serverSelectionTimeoutMS=3000) as client:
        count = (backup if args.operation=='backup' else restore)(client[args.database],args.file)
    print(f'{args.operation}: {count} accounts')

if __name__ == '__main__': main()
