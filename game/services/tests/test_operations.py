import secrets
import os
import mongomock
import pytest
from services.api.migrations import migrate
from tools.account_backup import backup, restore

@pytest.fixture
def database():
    from pymongo import MongoClient
    client = MongoClient(os.environ['MONGO_TEST_URI']) if os.getenv('MONGO_TEST_URI') else mongomock.MongoClient()
    db = client['kylr_ops_test_'+secrets.token_hex(6)]
    yield db
    client.drop_database(db.name)
    client.close()

def test_migration_preserves_customisation_and_can_run_twice(database):
    database.accounts.insert_one({'_id':'pilot','username_key':'pilot','display_key':'pilot',
                                 'loadout':{'head':'raptor','primary':'red'}})
    migrate(database)
    migrate(database)
    account = database.accounts.find_one()
    assert account['loadout']['head']=='raptor' and account['loadout']['primary']=='red'
    assert account['loadout']['secondary']=='white' and account['schema_version']==1
    database.schema.update_one({'_id':'accounts'},{'$set':{'version':100}})
    with pytest.raises(RuntimeError): migrate(database)

def test_backup_restore_keeps_accounts_and_rejects_overwrite_and_corruption(database,tmp_path):
    database.accounts.insert_one({'_id':'pilot','username_key':'pilot','display_key':'pilot',
                                 'password_hash':'argon2-hash','loadout':{'head':'raptor'}})
    database.sessions.insert_one({'_id':'secret-session'})
    archive=tmp_path/'accounts.gz'
    assert backup(database,archive)==1
    target=database.client[database.name+'_restored']
    try:
        assert restore(target,archive)==1
        assert target.accounts.find_one()['password_hash']=='argon2-hash'
        assert target.accounts.find_one()['loadout']['head']=='raptor'
        assert target.sessions.count_documents({})==0
        with pytest.raises(ValueError): restore(target,archive)
        archive.write_bytes(b'corrupted')
        empty=database.client[database.name+'_empty']
        with pytest.raises(ValueError): restore(empty,archive)
    finally: database.client.drop_database(target.name)
