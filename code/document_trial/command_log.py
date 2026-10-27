"""Capture child stdout/stderr in the archive and forward via Python/Jupyter."""
from datetime import datetime,timezone
from pathlib import Path
import os
import signal
import subprocess
import time
from .common import save

def run_logged(arguments,state,env=None,cwd=None,stage='subprocess'):
    args=list(map(str,arguments));logs=Path(state)/'commands';logs.mkdir(parents=True,exist_ok=True)
    step='%04d'%(len(list(logs.glob('*.json')))+1)
    logfile=logs/(step+'-stdout-stderr.log');record=logs/(step+'.json')
    info=dict(command=args,stage=stage,cwd=str(cwd) if cwd else None,status='running',returncode=None,
              started_utc=datetime.now(timezone.utc).isoformat(),log=logfile.name,
              capture='stdout+stderr merged as original bytes; forwarded through Python stdout')
    save(record,info);started=time.monotonic();proc=None
    try:
        with logfile.open('xb') as output:
            proc=subprocess.Popen(args,env=env,cwd=cwd,stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=(os.name=='posix'))
            try:
                for line in iter(proc.stdout.readline,b''):
                    output.write(line);output.flush()
                    try:print(line.decode('utf-8',errors='replace'),end='',flush=True)
                    except OSError:pass  # Archive capture must survive a console transport failure.
            finally:proc.stdout.close()
            code=proc.wait();info['returncode']=code
        info['status']='completed' if code==0 else 'failed'
        if code:raise subprocess.CalledProcessError(code,args)
        return subprocess.CompletedProcess(args,code)
    except BaseException as exc:
        if proc is not None and proc.poll() is None:
            if os.name=='posix':
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            else:proc.kill()
            proc.wait(timeout=5)
        info['status']='failed';info['exception']=type(exc).__name__+': '+str(exc)
        raise
    finally:
        info['elapsed_seconds']=time.monotonic()-started
        info['finished_utc']=datetime.now(timezone.utc).isoformat();save(record,info)
