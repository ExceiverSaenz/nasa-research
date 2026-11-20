import csv
import io
import subprocess
import threading
import time


def parse_gpu(text):
    return [dict(name=r[0].strip(),total_mib=float(r[1]),used_mib=float(r[2]),a100='A100' in r[0])
            for r in csv.reader(io.StringIO(text)) if len(r)>=3]


def gpu_snapshot():
    p=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.used','--format=csv,noheader,nounits'],
                     capture_output=True,text=True,timeout=10,check=True)
    return parse_gpu(p.stdout)


class ResourceMonitor:
    def __init__(self,interval=1):self.interval=interval;self.samples=[];self.stop_event=threading.Event()
    def __enter__(self):
        self.start=time.perf_counter();self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start();return self
    def run(self):
        while not self.stop_event.is_set():
            row={'elapsed_s':time.perf_counter()-self.start,'ram_bytes':None,'gpu':None}
            try:
                import psutil
                process=psutil.Process();row['ram_bytes']=sum(p.memory_info().rss for p in [process]+process.children(recursive=True) if p.is_running())
            except Exception as e:row['ram_error']=type(e).__name__
            try:row['gpu']=gpu_snapshot()
            except Exception as e:row['gpu_error']=type(e).__name__
            self.samples.append(row);self.stop_event.wait(self.interval)
    def __exit__(self,*args):self.stop_event.set();self.thread.join(timeout=15)
