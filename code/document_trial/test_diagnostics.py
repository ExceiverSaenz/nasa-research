import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from document_trial.common import ROOT
from document_trial.command_log import run_logged
from document_trial.cli import bounded_call

TEMP=ROOT/'analytics/results/sic12_document/launcher-diagnostics-v2'

class DiagnosticsTests(unittest.TestCase):
    def test_real_local_child_stdout_stderr_and_original_failure_preserved(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as folder:
            with self.assertRaises(subprocess.CalledProcessError) as error:
                run_logged([sys.executable,'-c','import sys; print("stdout-original",flush=True); print("uv-error-original",file=sys.stderr,flush=True); sys.exit(7)'],Path(folder),env=os.environ.copy())
            self.assertEqual(error.exception.returncode,7)
            logs=list((Path(folder)/'commands').glob('*.log'))
            self.assertEqual(len(logs),1)
            self.assertIn(b'stdout-original',logs[0].read_bytes());self.assertIn(b'uv-error-original',logs[0].read_bytes())
            metadata=json.loads(next((Path(folder)/'commands').glob('*.json')).read_bytes())
            self.assertEqual(metadata['returncode'],7);self.assertEqual(metadata['status'],'failed')
            from document_trial.remote import archive_state
            state=Path(folder)
            # Archive outside its source tree, uniquely within this test workspace.
            archive=state.parent/(state.name+'-captured.zip')
            try:
                archive_state(state,archive)
                with zipfile.ZipFile(archive) as z:
                    member=next(n for n in z.namelist() if n.endswith('.log'))
                    self.assertIn(b'uv-error-original',z.read(member))
            finally:
                archive.unlink(missing_ok=True);archive.with_suffix('.sha256').unlink(missing_ok=True)

    def test_local_cli_wait_is_bounded_without_models(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as folder:
            result=bounded_call([sys.executable,'-c','import time; print("fake-cli-start",flush=True); time.sleep(30)'],Path(folder)/'cli.log',.3,stream=False)
            self.assertEqual(result,124)
            meta=json.loads((Path(folder)/'cli.log.status.json').read_bytes())
            self.assertTrue(meta['timed_out']);self.assertLess(meta['elapsed_seconds'],10)

    def test_failed_cli_return_is_not_silently_successful(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as folder:
            result=bounded_call([sys.executable,'-c','import sys;print("fake-stderr",file=sys.stderr);sys.exit(9)'],Path(folder)/'cli.log',5,stream=False)
            self.assertEqual(result,9);self.assertIn('fake-stderr',(Path(folder)/'cli.log').read_text())

if __name__=='__main__':unittest.main()
