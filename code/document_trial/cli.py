"""Bound a local CLI call; timeout never means the remote job stopped."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from .common import save

def terminate_local_tree(proc):
    if os.name=='posix':
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    else:
        # Only the local CLI process tree created here; never a remote worker.
        try:subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)
        except (OSError,subprocess.TimeoutExpired):pass
        if proc.poll() is None:proc.kill()

def bounded_call(arguments,log_path,timeout,stream=True):
    if timeout<=0:raise ValueError('Positive CLI timeout required')
    args=list(map(str,arguments));log_path=Path(log_path);log_path.parent.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();timed_out=False;proc=None;code=125
    try:
        with log_path.open('xb') as output,log_path.open('rb') as reader:
            options={'start_new_session':True} if os.name=='posix' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
            proc=subprocess.Popen(args,stdin=sys.stdin,stdout=output,stderr=subprocess.STDOUT,**options)
            while proc.poll() is None:
                if stream:
                    data=reader.read()
                    if data:print(data.decode('utf-8',errors='replace'),end='',flush=True)
                if time.monotonic()-started>=timeout:
                    timed_out=True;terminate_local_tree(proc);break
                time.sleep(.05)
            if timed_out:
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:proc.kill()
                code=124
            else:code=proc.returncode
            if stream:
                data=reader.read()
                if data:print(data.decode('utf-8',errors='replace'),end='',flush=True)
    finally:
        save(str(log_path)+'.status.json',dict(command=args,returncode=code,timed_out=timed_out,
            elapsed_seconds=time.monotonic()-started,remote_job_stopped_by_this_wrapper=False))
    return code

def main():
    p=argparse.ArgumentParser();p.add_argument('--log',required=True);p.add_argument('--timeout',type=float,required=True)
    p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args();args=a.command
    if args and args[0]=='--':args=args[1:]
    if not args:p.error('CLI command required')
    return bounded_call(args,a.log,a.timeout,stream=False)

if __name__=='__main__':raise SystemExit(main())
