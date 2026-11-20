"""Bounded stdin/stdout exchange; inputs remain only in process memory."""
import json
import os
import queue
import subprocess
import threading
import time


def exchange(child, request, timeout, heartbeat, interval=5):
    events=queue.Queue()
    def transfer():
        try:
            child.stdin.write(json.dumps(request,allow_nan=False)+'\n')
            child.stdin.flush()
            while True:
                line=child.stdout.readline()
                if not line:raise EOFError('Worker exited without a result')
                if line.startswith('ORDER_RESULT:'):
                    events.put(('result',json.loads(line[len('ORDER_RESULT:'):])));return
        except Exception as error:
            events.put(('error',type(error).__name__))
    thread=threading.Thread(target=transfer,daemon=True)
    thread.start()
    deadline=time.monotonic()+timeout
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0:
            child.kill();child.wait(timeout=10);thread.join(timeout=2)
            raise TimeoutError('Worker deadline exceeded')
        try:
            kind,value=events.get(timeout=min(interval,remaining))
        except queue.Empty:
            heartbeat();continue
        if kind=='error':raise RuntimeError('Worker exchange failed: '+value)
        thread.join(timeout=2)
        return value


class KernelBridge:
    def __init__(self,code,environment):
        self.code,self.environment=code,environment
        self.child=None;self.candidate=None
        self.completed={}

    def close(self):
        if self.child is not None and self.child.poll() is None:
            self.child.kill();self.child.wait(timeout=10)

    def handle(self,request):
        request_id=request['request_id']
        if request_id in self.completed:return self.completed[request_id]
        candidate=request.get('candidate_id','metadata')
        if self.child is None or self.child.poll() is not None or self.candidate!=candidate:
            self.close()
            env=dict(os.environ,PYTHONPATH=self.code,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                     PYTHONDONTWRITEBYTECODE='1',HF_HUB_DISABLE_PROGRESS_BARS='1')
            self.child=subprocess.Popen([self.environment+'/venv/bin/python','-B','-u','-m','reading_order.worker',
                      '--environment',self.environment],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                      stderr=subprocess.DEVNULL,text=True,env=env)
            self.candidate=candidate
        started=time.monotonic()
        def heartbeat():
            print('ORDER_PROGRESS:'+json.dumps(dict(request_id=request_id,elapsed_s=round(time.monotonic()-started,1))),flush=True)
        try:
            result=exchange(self.child,request,request.get('timeout_s',300),heartbeat)
        except TimeoutError:
            result=dict(status='FAIL',ordered_ids=None,reason='WorkerTimeout',native={})
        response=dict(request_id=request_id,response=result)
        self.completed[request_id]=response
        if len(self.completed)>256:self.completed.pop(next(iter(self.completed)))
        return response
