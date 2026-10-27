"""Isolated E2E composition. Never import from production or deploy this harness."""
import asyncio
import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import asyncssh
import uvicorn
from aiogram.client.telegram import TelegramAPIServer

from infradeck.api import create_app
from infradeck.config import Settings
from infradeck.crypto import Vault
from infradeck.db import Database
from infradeck.identity import Identity
from infradeck.inventory import Inventory
from infradeck.migrate import migrate
from infradeck.ssh import SSH
from infradeck.telegram import Telegram

ROOT=Path(__file__).resolve().parents[3]
messages=[]
ssh_port=0


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass

    def respond(self,data):
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        code=''
        for value in reversed(messages):
            match=re.search(r'\b\d{8}\b',value)
            if match:code=match[0];break
        self.respond({'code':code,'ssh_port':ssh_port,'sent_count':len(messages)})

    def do_POST(self):
        content=self.rfile.read(int(self.headers['Content-Length'])).decode()
        text=parse_qs(content).get('text',[''])[0]
        messages.append(text)
        self.respond({'ok':True,'result':{'message_id':len(messages),'date':1,
            'chat':{'id':1234,'type':'private'},'text':text}})


def serve_ssh(ready):
    global ssh_port
    class Server(asyncssh.SSHServer):
        def begin_auth(self,username):return True
        def password_auth_supported(self):return True
        def validate_password(self,username,password):
            return username=='deploy' and password=='synthetic-ssh-password'
    async def run():
        global ssh_port
        server=await asyncssh.create_server(Server,'127.0.0.1',0,
            server_host_keys=[asyncssh.generate_private_key('ssh-ed25519')])
        ssh_port=server.get_port();ready.set()
        await server.wait_closed()
    asyncio.run(run())


class TestSSH(SSH):
    def address(self,host,port):
        # Test-only strict allowlist; no config flag disables production network policy.
        if host!='synthetic-vm' or port!=ssh_port:
            return super().address(host,port)
        return '127.0.0.1'


def main():
    settings=Settings(database_url=os.environ.get('E2E_DATABASE_URL',
        'postgresql://infradeck:local-only@localhost:25432/infradeck_e2e'),
        origin='http://localhost:5187',kek_file=ROOT/'.runtime/kek',
        rsa_file=ROOT/'.runtime/rsa.pem',otp_key_file=ROOT/'.runtime/otp',
        telegram_token='123456789:TEST_ONLY_NOT_REAL',telegram_username='infradeck_test',
        telegram_webhook_secret='s'*32)
    db=Database(settings.database_url.get_secret_value())
    migrate(db,ROOT/'services/control-plane/src/infradeck/migrations')
    with db.transaction() as tx:tx.execute('TRUNCATE users,rate_limits,telegram_updates CASCADE')
    stub=ThreadingHTTPServer(('127.0.0.1',8188),Handler)
    threading.Thread(target=stub.serve_forever,daemon=True).start()
    ready=threading.Event();threading.Thread(target=serve_ssh,args=(ready,),daemon=True).start()
    if not ready.wait(10):raise RuntimeError('SSH fixture not ready')
    vault=Vault(settings.kek_file.read_bytes(),settings.rsa_file.read_bytes(),settings.otp_key_file.read_bytes())
    telegram=Telegram(settings,TelegramAPIServer.from_base('http://127.0.0.1:8188'))
    auth=Identity(db,vault,telegram,settings.telegram_username)
    app=create_app(settings,auth,Inventory(db,vault,TestSSH()))
    uvicorn.run(app,host='127.0.0.1',port=8187,access_log=False,log_level='warning')


if __name__=='__main__':main()
