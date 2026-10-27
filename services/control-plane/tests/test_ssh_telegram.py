import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import AsyncMock,patch

import asyncssh
import dns.resolver
import dns.exception
import pytest
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendMessage
from aiohttp_socks import ProxyConnectionError

from infradeck.errors import Rejected
from infradeck.schemas import Connection
from infradeck.ssh import SSH
from infradeck.telegram import Telegram,TelegramSession


@pytest.mark.parametrize('host', ['127.0.0.1','169.254.169.254','0.0.0.0','224.0.0.1','10.0.0.1','::1','::ffff:127.0.0.1'])
def test_ssrf_denied(host):
    with pytest.raises(Rejected):SSH().address(host,22)


def test_network_policy(monkeypatch):
    monkeypatch.setattr(dns.resolver,'resolve',lambda *a,**kw:['10.42.1.1'])
    assert SSH('10.42.0.0/16').address('private-vm',22)=='10.42.1.1'
    monkeypatch.setattr(dns.resolver,'resolve',lambda *a,**kw:['8.8.8.8'])
    assert SSH().address('public-vm',22)=='8.8.8.8'
    monkeypatch.setattr(dns.resolver,'resolve',lambda *a,**kw:[])
    with pytest.raises(Rejected):SSH().address('empty',22)
    def failed(*a,**kw):raise dns.exception.Timeout('private-address')
    monkeypatch.setattr(dns.resolver,'resolve',failed)
    with pytest.raises(Rejected):SSH().address('missing',22)
    def no_answer(*a,**kw):raise dns.resolver.NoAnswer()
    monkeypatch.setattr(dns.resolver,'resolve',no_answer)
    with pytest.raises(Rejected):SSH().address('missing',22)
    with pytest.raises(Rejected):SSH().address('168.63.129.16',22)


@pytest.fixture(scope='module')
def ssh_server():
    loop=asyncio.new_event_loop();ready=threading.Event();state={}
    hostkey=asyncssh.generate_private_key('ssh-ed25519')
    clientkey=asyncssh.generate_private_key('ssh-ed25519')
    ca=asyncssh.generate_private_key('ssh-ed25519')
    class Server(asyncssh.SSHServer):
        def begin_auth(self,username):return True
        def password_auth_supported(self):return True
        def public_key_auth_supported(self):return True
        def validate_password(self,username,password):return username=='deploy' and password=='test-password'
        def validate_public_key(self,username,key):return username=='deploy' and key==clientkey.convert_to_public()
        def validate_ca_key(self,username,key):return username=='deploy' and key==ca.convert_to_public()
    async def start():
        state['server']=await asyncssh.create_server(Server,'127.0.0.1',0,server_host_keys=[hostkey])
        state['port']=state['server'].get_port();ready.set()
    def run():
        asyncio.set_event_loop(loop);loop.run_until_complete(start());loop.run_forever()
        state['server'].close();loop.run_until_complete(state['server'].wait_closed());loop.close()
    thread=threading.Thread(target=run,daemon=True);thread.start();assert ready.wait(10)
    yield state['port'],hostkey,clientkey,ca
    loop.call_soon_threadsafe(loop.stop);thread.join(10)


def test_ssh_real_password_key_certificate(ssh_server,monkeypatch):
    port,hostkey,clientkey,ca=ssh_server
    ssh=SSH();monkeypatch.setattr(ssh,'address',lambda *args:'127.0.0.1')
    fingerprint=ssh.probe('synthetic-vm',port)
    assert fingerprint==hostkey.get_fingerprint()
    values={'host':'synthetic-vm','port':port,'username':'deploy','method':'password',
        'password':'test-password','fingerprint':fingerprint}
    assert ssh.verify(Connection(**values))==fingerprint
    for changes in ({'password':'incorrect-secret'},{'fingerprint':'SHA256:wrong'},
        {'password':''},{'method':'key','private_key':'invalid-secret-key'}):
        with pytest.raises(Rejected) as err:ssh.verify(Connection(**{**values,**changes}))
        assert 'incorrect-secret' not in str(err.value)
    key=clientkey.export_private_key().decode()
    assert ssh.verify(Connection(**{**values,'method':'key','private_key':key}))==fingerprint
    cert=ca.generate_user_certificate(clientkey,'test',principals=['deploy'])
    assert ssh.verify(Connection(**{**values,'method':'certificate','private_key':key,
        'certificate':cert.export_certificate().decode()}))==fingerprint


def test_ssh_missing_key(monkeypatch):
    monkeypatch.setattr(asyncssh,'get_server_host_key',AsyncMock(return_value=None))
    with pytest.raises(Rejected):asyncio.run(SSH()._key('8.8.8.8',22))


@pytest.fixture
def bot_server():
    state={'messages':[],'status':200}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            state['messages'].append(self.path)
            self.send_response(state['status']);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps({'ok':True,'result':{'message_id':1,'date':1,
                'chat':{'id':1234,'type':'private'},'text':'Synthetic'}} if state['status']==200
                else {'ok':False,'error_code':state['status'],'description':'Test rejection'}).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    state['url']=f'http://127.0.0.1:{server.server_port}'
    yield state
    server.shutdown();server.server_close();thread.join(5)


def test_telegram_real_transport(settings,bot_server):
    original=TelegramSession
    def session(**kwargs):
        return original(api=TelegramAPIServer.from_base(bot_server['url']),**kwargs)
    telegram=Telegram(settings)
    with patch('infradeck.telegram.TelegramSession',side_effect=session):
        telegram.send(1234,'Synthetic message')
        assert len(bot_server['messages'])==1
        for status in (400,403,429,500):
            bot_server['status']=status
            with pytest.raises(Rejected):telegram.send(1234,'Synthetic message')


def test_telegram_proxy_failure_is_sanitized(settings):
    async def fail():
        session=TelegramSession(proxy='http://localhost:19999')
        try:
            with patch.object(AiohttpSession,'make_request',side_effect=ProxyConnectionError('private-address')):
                with pytest.raises(TelegramNetworkError) as err:
                    await session.make_request(Bot('123456789:TEST_ONLY'),SendMessage(chat_id=1,text='test'))
                assert 'private-address' not in str(err.value)
                assert err.value.__suppress_context__
        finally:await session.close()
    asyncio.run(fail())
