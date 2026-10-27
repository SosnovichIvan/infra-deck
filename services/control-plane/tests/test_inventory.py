import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID,uuid4

import pytest

from conftest import envelope
from infradeck.crypto import token_hash
from infradeck.errors import Rejected
from infradeck.schemas import ProjectInput,ServerInput


def project(browser):
    result=browser.call('POST','/projects',{'name':'Platform','description':'Test project'})
    assert result.status_code==201,result.text
    return result.json()['id']


def check(browser,project_id,vault,connection,server_id=None):
    key=browser.call('GET','/encryption-key').json()
    return browser.call('POST',f'/projects/{project_id}/checks',{
        'jwe':envelope(vault,key['nonce'],connection),'server_id':server_id})


def server(browser,project_id,vault,connection):
    result=check(browser,project_id,vault,connection)
    assert result.status_code==200,result.text
    response=browser.call('POST',f'/projects/{project_id}/servers',
        {'name':'Web','kind':'VPS','proof':result.json()['proof']})
    assert response.status_code==201,response.text
    return response.json()


def test_projects_crud(logged,db):
    id=project(logged)
    assert len(logged.call('GET','/projects').json())==1
    assert logged.call('GET','/projects?offset=100').json()==[]
    assert logged.call('GET','/projects/'+id).json()['name']=='Platform'
    assert logged.call('PUT','/projects/'+id,{'name':'Renamed','description':''}).json()['name']=='Renamed'
    assert logged.call('PUT','/projects/'+id,{'name':'  '}).status_code==422
    assert logged.call('DELETE','/projects/'+id).status_code==204
    assert logged.call('GET','/projects/'+id).status_code==404
    assert logged.call('DELETE','/projects/'+id).status_code==404
    assert logged.call('PUT','/projects/'+id,{'name':'missing'}).status_code==404


def test_server_full_lifecycle(logged,vault,connection,db):
    id=project(logged)
    assert logged.call('POST',f'/projects/{id}/probe',{'host':'example.com','port':22}).json()['fingerprint']==connection.fingerprint
    assert logged.call('POST',f'/projects/{id}/servers',{'name':'Web','kind':'VM'}).status_code==400
    created=server(logged,id,vault,connection)
    assert connection.password.get_secret_value() not in json.dumps(created)
    assert len(logged.call('GET',f'/projects/{id}/servers').json())==1
    assert logged.call('GET',f'/projects/{id}/servers?offset=100').json()==[]
    with db.transaction() as tx:
        raw=tx.execute('SELECT encrypted FROM servers').fetchone()
        assert connection.password.get_secret_value() not in str(raw)
    path=f'/projects/{id}/servers/'+created['id']
    assert logged.call('PUT',path,{'name':'Metadata','kind':'VM'}).json()['kind']=='VM'
    result=check(logged,id,vault,connection,created['id'])
    assert result.status_code==200,result.text
    assert logged.call('PUT',path,{'name':'Reconnected','kind':'VPS','proof':result.json()['proof']}).status_code==200
    assert logged.call('POST',path+'/recheck').status_code==200
    assert logged.call('DELETE',path).status_code==204
    assert logged.call('DELETE',path).status_code==404
    assert logged.call('POST',path+'/recheck').status_code==404
    assert logged.call('PUT',path,{'name':'Missing','kind':'VM'}).status_code==404


def test_owner_scope_and_cascade(logged,vault,connection,db,inventory):
    id=project(logged);created=server(logged,id,vault,connection)
    other=uuid4()
    for action in (lambda:inventory.project(other,UUID(id)),
        lambda:inventory.servers(other,UUID(id),0),
        lambda:inventory.server(other,UUID(id),UUID(created['id'])),
        lambda:inventory.delete_server(other,UUID(id),UUID(created['id']))):
        with pytest.raises(Rejected):action()
    assert logged.call('DELETE','/projects/'+id).status_code==204
    with db.transaction() as tx:
        assert not tx.execute('SELECT 1 FROM servers').fetchone()
        assert not tx.execute('SELECT 1 FROM connection_checks').fetchone()


def test_nonce_expiry_session_binding_and_replay(logged,vault,connection,db):
    id=project(logged);key=logged.call('GET','/encryption-key').json()
    data={'jwe':envelope(vault,key['nonce'],connection)}
    assert logged.call('POST',f'/projects/{id}/checks',data).status_code==200
    assert logged.call('POST',f'/projects/{id}/checks',data).status_code==409
    key=logged.call('GET','/encryption-key').json()
    with db.transaction() as tx:tx.execute('UPDATE encryption_nonces SET expires_at=0')
    assert logged.call('POST',f'/projects/{id}/checks',{'jwe':envelope(vault,key['nonce'],connection)}).status_code==409
    assert logged.call('POST',f'/projects/{id}/checks',{'jwe':'x'*100}).status_code==400


def test_proof_scope_expiry_one_use(logged,vault,connection,db):
    id=project(logged);other=project(logged)
    result=check(logged,id,vault,connection).json();proof=result['proof']
    data={'name':'Test','kind':'VM','proof':proof}
    assert logged.call('POST',f'/projects/{other}/servers',data).status_code==409
    assert logged.call('POST',f'/projects/{id}/servers',data).status_code==201
    assert logged.call('POST',f'/projects/{id}/servers',data).status_code==409
    result=check(logged,id,vault,connection).json()
    with db.transaction() as tx:tx.execute('UPDATE connection_checks SET expires_at=0')
    assert logged.call('POST',f'/projects/{id}/servers',{**data,'proof':result['proof']}).status_code==409


def test_connection_validation_and_failed_check(logged,vault,connection,ssh):
    id=project(logged)
    connection.fingerprint=''
    assert check(logged,id,vault,connection).status_code==400
    connection.fingerprint='SHA256:trusted-test-fingerprint'
    ssh.verify.side_effect=Rejected('SSH unavailable')
    assert check(logged,id,vault,connection).status_code==400
    assert logged.call('GET',f'/projects/{id}/servers').json()==[]


def test_parallel_proof_consumption(logged,vault,connection,auth,inventory):
    id=project(logged);result=check(logged,id,vault,connection).json()
    owner=auth.session(logged.client.cookies.get('session'))['user_id']
    def save():
        try:inventory.save_server(owner,UUID(id),ServerInput(name='Test',kind='VM',proof=result['proof']));return True
        except Rejected:return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _:save(),range(2)))==[False,True]
