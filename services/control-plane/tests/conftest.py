import os
import re
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from jwcrypto import jwe

from infradeck.api import create_app
from infradeck.config import Settings
from infradeck.crypto import Vault
from infradeck.db import Database
from infradeck.identity import Identity
from infradeck.inventory import Inventory
from infradeck.migrate import migrate
from infradeck.schemas import Connection
from infradeck.ssh import SSH
from infradeck.telegram import Telegram

ROOT = Path(__file__).resolve().parents[3]
PASSWORD = 'Correct-password-2026!'


@pytest.fixture(scope='session')
def settings():
    return Settings(database_url=os.environ.get('TEST_DATABASE_URL',
        'postgresql://infradeck:local-only@localhost:25432/infradeck_test'),
        kek_file=ROOT/'.runtime/kek',rsa_file=ROOT/'.runtime/rsa.pem',
        otp_key_file=ROOT/'.runtime/otp',telegram_token='123456789:TEST_ONLY_NOT_REAL',
        telegram_username='infradeck_test',telegram_webhook_secret='s'*32)


@pytest.fixture(scope='session')
def vault(settings):
    return Vault(settings.kek_file.read_bytes(),settings.rsa_file.read_bytes(),
                 settings.otp_key_file.read_bytes())


@pytest.fixture
def db(settings):
    database=Database(settings.database_url.get_secret_value())
    migrate(database,ROOT/'services/control-plane/src/infradeck/migrations')
    with database.transaction() as tx:
        tx.execute('TRUNCATE users,rate_limits,telegram_updates CASCADE')
    return database


@pytest.fixture
def telegram():
    return Mock(spec=Telegram)


@pytest.fixture
def ssh():
    instance=Mock(spec=SSH)
    instance.probe.return_value='SHA256:trusted-test-fingerprint'
    instance.verify.return_value='SHA256:trusted-test-fingerprint'
    return instance


@pytest.fixture
def auth(db,vault,telegram):
    return Identity(db,vault,telegram,'infradeck_test')


@pytest.fixture
def inventory(db,vault,ssh):
    return Inventory(db,vault,ssh)


class Browser:
    def __init__(self, client):
        self.client=client

    def call(self,method,path,data=None):
        self.client.get('/api/auth/csrf')
        return self.client.request(method,'/api'+path,json=data,headers={
            'Origin':'http://localhost:5187','X-CSRF-Token':self.client.cookies.get('csrf','')})

    def register(self,login='tester'):
        return self.call('POST','/auth/register',{'login':login,'password':PASSWORD,
                                                'confirmation':PASSWORD})

    def bind(self,link,chat=1234,update=1):
        binding=link.split('=')[-1]
        return self.client.post('/api/telegram/webhook',headers={
            'X-Telegram-Bot-Api-Secret-Token':'s'*32},json={
            'update_id':update,'message':{'message_id':1,'date':1,
                'chat':{'id':chat,'type':'private'},'from':{'id':chat,'is_bot':False,
                'first_name':'Synthetic'},'text':'/start '+binding}})


@pytest.fixture
def browser(settings,auth,inventory):
    with TestClient(create_app(settings,auth,inventory),raise_server_exceptions=True) as client:
        yield Browser(client)


@pytest.fixture
def logged(browser,telegram):
    result=browser.register()
    assert result.status_code==200,result.text
    assert browser.bind(result.json()['telegram_url']).status_code==200
    assert browser.call('POST','/auth/send-code').status_code==200
    code=re.search(r'\b\d{8}\b',telegram.send.call_args.args[1])[0]
    result=browser.call('POST','/auth/verify',{'code':code})
    assert result.status_code==200,result.text
    return browser


@pytest.fixture
def connection():
    return Connection(host='example.com',username='deploy',method='password',
                      password='ssh-secret-never-return',fingerprint='SHA256:trusted-test-fingerprint')


def envelope(vault,nonce,connection):
    from infradeck.inventory import plaintext
    import json
    value=json.dumps({'nonce':nonce,'connection':json.loads(plaintext(connection))})
    encrypted=jwe.JWE(value.encode(),protected={'alg':'RSA-OAEP-256','enc':'A256GCM','kid':vault.kid})
    encrypted.add_recipient(vault.rsa)
    return encrypted.serialize(compact=True)
