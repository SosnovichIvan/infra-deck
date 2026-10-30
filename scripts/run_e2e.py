"""Start isolated fixtures and terminate their complete process groups on every exit."""
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
processes=[]
try:
    for command,cwd,name in [
        ([str(ROOT/'.venv/bin/python'),'services/control-plane/tests/e2e_harness.py'],ROOT,'api'),
        (['node','node_modules/vite/bin/vite.js','--host','127.0.0.1'],ROOT/'apps/web','web')]:
        with (ROOT/f'.runtime/e2e-{name}.log').open('w') as log:
            processes.append(subprocess.Popen(command,cwd=cwd,stdout=log,stderr=log,
                                               start_new_session=True))
    for url in ('http://127.0.0.1:8187/api/health','http://localhost:5187'):
        deadline=time.monotonic()+60
        while True:
            if any(p.poll() is not None for p in processes):
                raise SystemExit('E2E fixture exited; inspect .runtime/e2e-*.log')
            try:
                with urllib.request.urlopen(url,timeout=2) as response:
                    if response.status==200:break
            except OSError:
                if time.monotonic()>deadline:raise SystemExit('E2E readiness failed: '+url)
                time.sleep(.2)
    subprocess.run(['npm','--prefix','apps/web','run','e2e','--',*sys.argv[1:]],cwd=ROOT,check=True)
finally:
    for process in processes:
        if process.poll() is None:os.killpg(process.pid,signal.SIGTERM)
    for process in processes:
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait()
