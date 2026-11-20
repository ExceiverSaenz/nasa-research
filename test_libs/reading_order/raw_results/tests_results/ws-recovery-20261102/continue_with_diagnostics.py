"""Observe protocol metadata only; never record input bodies or output text."""
import json,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from colab_cli.runtime import ColabRuntime
original=ColabRuntime.execute_code
events=Path(__file__).parent/'protocol-events.jsonl'
def record(value):
    with events.open('a') as stream:stream.write(json.dumps(value)+'\n')
def observed(self,*args,**kwargs):
    started=time.monotonic()
    def progress(output):
        text=output.get('text','')
        record(dict(event='progress',elapsed_s=time.monotonic()-started,
                    result_marker='ORDER_RESULT:' in text,progress_messages=text.count('ORDER_PROGRESS:')))
    kwargs['output_hook']=progress
    try:
        outputs=original(self,*args,**kwargs)
        texts=[o.get('text','') for o in outputs]
        record(dict(elapsed_s=time.monotonic()-started,output_types=[o.get('output_type') for o in outputs],
            error_types=[o.get('ename') for o in outputs if o.get('output_type')=='error'],
            result_marker_in_chunk=any('ORDER_RESULT:' in t for t in texts),
            result_marker_in_joined='ORDER_RESULT:' in ''.join(texts),
            progress_messages=sum(t.count('ORDER_PROGRESS:') for t in texts)))
        return outputs
    except Exception as error:
        record(dict(elapsed_s=time.monotonic()-started,error_type=type(error).__name__))
        raise
ColabRuntime.execute_code=observed
from reading_order.cli import main
base=root/'raw_results/tests_results/ws-recovery-20261102'
sys.exit(main(['resume-stability','--session','order-stability-20261102',
    '--environment-receipt',str(base/'code-comm/environment.json'),
    '--test-receipt',str(base/'offline-comm/test-receipt.json'),
    '--run',str(root/'raw_results/code_results/pilot-12-20261102'),
    '--resume-attempt',str(root/'raw_results/code_results/stability-12-recovery-20261102-final'),
    '--output',str(root/'raw_results/code_results/stability-12-recovery-20261102-comm')]))
