"""Bounded resource sampling; GPU memory is attributed by owned PID only."""
import os
import subprocess
import threading
import time


class ResourceSampler:
    def __init__(self, interval_s=1):
        self.interval = interval_s
        self.stop_event = threading.Event()
        self.rss = None
        self.gpu = None
        self.samples = 0

    def sample(self):
        import psutil
        processes = [psutil.Process(os.getpid())]
        processes += processes[0].children(recursive=True)
        pids = {p.pid for p in processes}
        rss = sum(p.memory_info().rss for p in processes if p.is_running())
        self.rss = max(self.rss or 0,rss)
        self.samples += 1
        result = subprocess.run(['nvidia-smi','--query-compute-apps=pid,used_gpu_memory','--format=csv,noheader,nounits'],
                                capture_output=True,text=True,timeout=5)
        values = []
        for line in result.stdout.splitlines():
            fields = [f.strip() for f in line.split(',')]
            if len(fields) == 2 and fields[0].isdigit() and int(fields[0]) in pids and fields[1].isdigit():
                values.append(int(fields[1])*1024*1024)
        if values:
            self.gpu = max(self.gpu or 0,sum(values))

    def __enter__(self):
        def loop():
            while not self.stop_event.is_set():
                try:
                    self.sample()
                except Exception:
                    pass  # Missing samples remain unknown, not zero or device totals.
                self.stop_event.wait(self.interval)
        self.thread = threading.Thread(target=loop,daemon=True)
        self.thread.start()
        return self

    def __exit__(self,*args):
        self.stop_event.set()
        self.thread.join(timeout=6)

    def result(self):
        return dict(peak_sampled_rss_bytes=self.rss,peak_sampled_gpu_bytes=self.gpu,samples=self.samples,
                    interval_s=self.interval,load_s=None,inference_s=None,decode_s=None,
                    limitation='sampled process-tree RSS may double-count shared pages; short peaks may be missed')
