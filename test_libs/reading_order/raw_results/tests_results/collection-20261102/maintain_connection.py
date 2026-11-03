"""Use Colab CLI's existing-session refresh while the owned collection runs."""
import json,time,contextlib,io
from datetime import datetime,timezone
from pathlib import Path
from colab_cli.common import State
base=Path(__file__).parent
session='order-collection-20261102-r6';client=State()
original=client.store.get(session);kernel_id=original.kernel_id;endpoint=original.endpoint
run=base.parents[1]/'code_results/collection-20261102-delivery'
log=base/'connection-refresh.jsonl'
while not (run/'session-status.json').exists():
    try:
        before=client.store.get(session)
        if before is None:break
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            current=client.get_session(session,ignore_missing_session=True)
        if current is None:break
        assert current.kernel_id==kernel_id and current.endpoint==endpoint and current.accelerator=='A100'
        record=dict(time=datetime.now(timezone.utc).isoformat(),status='PASS',same_kernel=True,
            refreshed=before.token!=current.token,
            remaining_s=round((current.token_expires_at-datetime.now(timezone.utc)).total_seconds()))
    except Exception as error:record=dict(time=datetime.now(timezone.utc).isoformat(),status='FAIL',error_type=type(error).__name__)
    with log.open('a') as stream:stream.write(json.dumps(record)+'\n')
    print(json.dumps(record),flush=True)
    time.sleep(30)
print('CONNECTION_MAINTENANCE_FINISHED',flush=True)
