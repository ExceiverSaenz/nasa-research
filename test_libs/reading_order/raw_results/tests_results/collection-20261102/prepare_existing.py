"""Prepare the owned connection-diagnostic A100 once, using the sealed lock."""
import sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from reading_order.preflight import require_test_receipt
from reading_order.deployment import ColabController
from colab_cli.state import StateStore
base=Path(__file__).parent
require_test_receipt(root,base/'offline-client-session/test-receipt.json')
session='order-collection-20261102-r3'
class OwnedExistingController(ColabController):
    def command(self,args,phase,timeout=2400):
        if phase=='create':
            state=StateStore().get(self.session)
            assert state and state.accelerator=='A100'
            (self.output/'create.log').write_text('Reused owned A100 created solely for connection diagnostics; environment not yet prepared.\n')
            return 'Owned A100 exists'
        return super().command(args,phase,timeout)
receipt=OwnedExistingController(root.parents[1],base/'environment-r3',session).prepare()
print(json.dumps(dict(status=receipt['status'],lock_sha256=receipt['lock_sha256'],session=receipt['session'])))
