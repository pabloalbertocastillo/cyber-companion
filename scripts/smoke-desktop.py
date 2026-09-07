#!/usr/bin/env python3
"""Real daemon lifecycle gate. Requires Linux Unix sockets; uses isolated XDG dirs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cyber_companion.ipc import call


def main():
    with tempfile.TemporaryDirectory(prefix='wisp-smoke-') as directory:
        root=Path(directory)
        runtime=root/'run';runtime.mkdir(mode=0o700)
        config=root/'config';config.mkdir()
        (config/'cyber-companion').mkdir()
        (config/'cyber-companion/desktop.json').write_text(json.dumps({'sensors':['system','storage','network'],'notifications':False}))
        env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime),XDG_STATE_HOME=str(root/'state'),XDG_CONFIG_HOME=str(config))
        socket_path=runtime/'cyber-companion/control.sock'
        def start():
            log=open(root/'daemon.log','ab')
            p=subprocess.Popen([sys.executable,'-m','cyber_companion.daemon'],cwd=ROOT,env=env,stdout=log,stderr=log)
            log.close()
            deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                try:
                    result=call('status.get',path=socket_path,timeout=.5)
                    if result['domains'].get('system',{}).get('fresh'): return p,result
                except (OSError,ValueError): pass
                if p.poll() is not None: break
                time.sleep(.1)
            p.terminate();p.wait(timeout=5)
            raise RuntimeError((root/'daemon.log').read_text())
        p,first=start()
        try:
            call('preferences.set',{'reduced_motion':True},path=socket_path)
            call('attention.mute',{'seconds':3600},path=socket_path)
            second=subprocess.run([sys.executable,'-m','cyber_companion.daemon'],cwd=ROOT,env=env,capture_output=True,timeout=5)
            assert second.returncode==1,second.stderr
            assert call('status.get',path=socket_path)['generation']==first['generation']
            call('daemon.stop',path=socket_path);p.wait(timeout=6)
            assert p.returncode==0
            p,restarted=start()
            assert restarted['generation']!=first['generation']
            assert restarted['store_id']==first['store_id']
            assert restarted['preferences']['reduced_motion'] is True
            assert restarted['preferences']['muted_until']>time.time()
            assert socket_path.stat().st_mode & 0o777 == 0o600
            call('daemon.stop',path=socket_path);p.wait(timeout=6)
            assert p.returncode==0
            print('PASS · fresh Linux readings, singleton, owner socket, stop, restart, durable preferences')
        finally:
            if p.poll() is None: p.terminate();p.wait(timeout=6)


if __name__=='__main__': main()
