import json
import runpy
from pathlib import Path
from unittest.mock import patch

import pytest
from jwcrypto import jwe

from conftest import envelope
from infradeck.api import create_app
from infradeck.errors import Rejected
from infradeck.main import app as app_factory
from infradeck.migrate import main as migrate_main


def test_composition_and_cli(settings,db):
    with patch('infradeck.main.Settings',return_value=settings):
        assert app_factory().title=='InfraDeck API'
    with patch('infradeck.migrate.Settings',return_value=settings):
        migrate_main()
    with patch('infradeck.config.Settings',return_value=settings):
        runpy.run_module('infradeck.migrate',run_name='__main__')


def test_security_boundaries(logged,auth,db):
    client=logged.client
    assert client.get('/api/health').json()=={'status':'ok'}
    csrf=client.cookies.get('csrf')
    headers={'Origin':'http://localhost:5187','X-CSRF-Token':csrf}
    assert client.post('/api/projects',headers={**headers,'Content-Length':'70000'},content='{}').status_code==413
    assert client.post('/api/projects',headers={**headers,'Content-Length':'invalid'},content='{}').status_code==400
    client.cookies.set('csrf','forged')
    assert client.post('/api/projects',headers={**headers,'X-CSRF-Token':'forged'},json={'name':'X'}).status_code==403
    client.cookies.set('csrf',csrf)
    with db.transaction() as tx:tx.execute('UPDATE sessions SET expires_at=0')
    assert client.post('/api/projects',headers=headers,json={'name':'X'}).status_code==401


def test_webhook_ignores_non_start(browser):
    for event in ({'update_id':100},{'update_id':101,'message':{'message_id':1,'date':1,
        'chat':{'id':100,'type':'private'},'from':{'id':100,'is_bot':False,'first_name':'Test'},'text':'hello'}}):
        assert browser.client.post('/api/telegram/webhook',headers={
            'X-Telegram-Bot-Api-Secret-Token':'s'*32},json=event).status_code==200


def test_invalid_envelope_payloads(logged,vault,connection):
    project=logged.call('POST','/projects',{'name':'Test'}).json()['id']
    for value in ({'nonce':1,'connection':{}},{'nonce':'x','extra':{},'connection':{}}):
        message=jwe.JWE(json.dumps(value).encode(),protected={'alg':'RSA-OAEP-256','enc':'A256GCM','kid':vault.kid})
        message.add_recipient(vault.rsa)
        assert logged.call('POST',f'/projects/{project}/checks',{'jwe':message.serialize(compact=True)}).status_code==400
    key=logged.call('GET','/encryption-key').json()
    connection.host='!'
    assert logged.call('POST',f'/projects/{project}/checks',{'jwe':envelope(vault,key['nonce'],connection)}).status_code==400
