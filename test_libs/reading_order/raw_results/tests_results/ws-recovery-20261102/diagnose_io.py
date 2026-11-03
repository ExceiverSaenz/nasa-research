"""Synthetic reproduction of the original pipe timeout hole, without data."""
import json,select,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'code'))
from reading_order.memory_bridge import exchange
script="import sys,time;sys.stdin.readline();sys.stdout.write('partial');sys.stdout.flush();time.sleep(1)"
def child():return subprocess.Popen([sys.executable,'-u','-c',script],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
old=child();old.stdin.write('{}\n');old.stdin.flush();start=time.monotonic()
assert select.select([old.stdout],[],[],.2)[0]
old.stdout.readline();old.wait()
old_elapsed=time.monotonic()-start
new=child();start=time.monotonic()
try:exchange(new,{},.2,lambda:None,interval=.05)
except TimeoutError:pass
else:raise AssertionError('Deadline not enforced')
new_elapsed=time.monotonic()-start
assert old_elapsed>.8 and new_elapsed<.8
receipt=dict(synthetic_only=True,old_readline_elapsed_s=old_elapsed,new_exchange_elapsed_s=new_elapsed,
             deadline_s=.2,old_timeout_hole_reproduced=True,new_timeout_enforced=True,
             original_network_close_reason='not captured by original transport; external cause not proven')
(Path(__file__).parent/'io-diagnosis.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
