"""No real CLI: bootstrap tests and optional shell tests with a fake colab executable."""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'code/page_integration/test_square.sh'


class SquareBootstrapTests(unittest.TestCase):
    def bootstrap(self):
        return re.search(r"colab exec[^\n]*<<'PY'[^\n]*\n(.*?)\nPY",SCRIPT.read_text(encoding='utf-8'),re.S).group(1)

    def test_kernel_arguments_and_old_experiment_modules_are_isolated(self):
        old_args=sys.argv;old_path=sys.path[:]
        stale=types.ModuleType('page_integration.old_experiment')
        sys.modules[stale.__name__]=stale
        def inert_entry(*args,**kwargs):
            argparse.ArgumentParser().parse_args()
            self.assertNotIn(stale.__name__,sys.modules)
            self.assertEqual(args[0],'page_integration.remote_square')
        try:
            sys.argv=['kernel','-f','kernel.json']
            with patch('runpy.run_module',side_effect=inert_entry):exec(self.bootstrap(),{})
            self.assertEqual(sys.argv,['kernel','-f','kernel.json'])
            self.assertEqual(sys.path,old_path);self.assertIs(sys.modules[stale.__name__],stale)
        finally:
            sys.argv=old_args;sys.modules.pop(stale.__name__,None)

    def test_failure_restores_kernel_state_without_success_message(self):
        argv=sys.argv[:];paths=sys.path[:];output=io.StringIO()
        with patch('runpy.run_module',side_effect=SystemExit(1)),contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit):exec(self.bootstrap(),{})
        self.assertEqual(sys.argv,argv);self.assertEqual(sys.path,paths)
        self.assertEqual(output.getvalue(),'')


@unittest.skipUnless(os.environ.get('HEADER_TEST_BASH'),'Requires explicitly selected Bash; fake CLI only')
class SquareShellTests(unittest.TestCase):
    def run_case(self,mode):
        with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as temp:
            temp=Path(temp);shim=temp/'bin';shim.mkdir()
            python=sys.executable.replace('\\','/')
            (shim/'python3').write_text('#!/usr/bin/env bash\nexec "'+python+'" "$@"\n',encoding='utf-8')
            fake=temp/'fake_colab.py'
            fake.write_text('''import os,sys,json,zipfile,hashlib
from pathlib import Path
root=Path(os.environ['HEADER_FAKE_ROOT']);log=Path(os.environ['HEADER_FAKE_LOG']);mode=os.environ['HEADER_FAKE_MODE']
with log.open('a') as f:f.write(sys.argv[1]+'\\n')
command=sys.argv[1]
if command=='status':print('Hardware: T4 | Status: IDLE')
elif command=='upload':pass
elif command=='exec':
    sys.stdin.read()
    if mode=='timeout':print('timeout');raise SystemExit(124)
    print('SQUARE_ARCHIVE_READY '+('failed' if mode=='failed' else 'completed'))
elif command=='download':
    destination=Path(sys.argv[-1]);source=root/'returned.zip'
    if not source.exists():
        with zipfile.ZipFile(source,'w') as z:
            with zipfile.ZipFile(root/'code/packages/table1-square-v1/upload.zip') as upload:
                z.writestr('plan.json',upload.read('plan.json'))
            z.writestr('execution-status.json',json.dumps({'status':'failed' if mode=='failed' else 'completed'}))
    if sys.argv[-2].endswith('.sha256'):
        destination.write_text(('0'*64 if mode=='corrupt' else hashlib.sha256(source.read_bytes()).hexdigest())+'\\n')
    else:destination.write_bytes(source.read_bytes())
elif command=='stop':print('fake own session stopped')
else:raise SystemExit('Unexpected fake command')
''',encoding='utf-8')
            (shim/'colab').write_text('#!/usr/bin/env bash\nexec "'+python+'" "'+fake.as_posix()+'" "$@"\n',encoding='utf-8')
            # Recreate a tiny workspace with actual source/package files for the launcher's checks.
            import shutil
            (temp/'code/page_integration').mkdir(parents=True)
            shutil.copyfile(SCRIPT,temp/'code/page_integration/test_square.sh')
            with zipfile.ZipFile(ROOT/'code/packages/table1-square-v1/upload.zip') as z:
                for name in z.namelist():
                    if name.startswith(('page_integration/','mineru_probe/')):
                        target=temp/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
            shutil.copytree(ROOT/'code/packages/table1-square-v1',temp/'code/packages/table1-square-v1')
            env=os.environ.copy();env.update(HEADER_FAKE_ROOT=str(temp),HEADER_FAKE_LOG=str(temp/'calls.log'),HEADER_FAKE_MODE=mode)
            # Convert shim prefix to Unix form inside Bash before invoking the launcher.
            command='export PATH="$(cygpath -u "$HEADER_FAKE_ROOT")/bin:$PATH"; bash "$(cygpath -u "$HEADER_FAKE_ROOT")/code/page_integration/test_square.sh" fake-own-session --own-session'
            result=subprocess.run([env['HEADER_TEST_BASH'],'-c',command],capture_output=True,text=True,env=env)
            calls=(temp/'calls.log').read_text().splitlines()
            return result,calls

    def test_success_downloads_verifies_then_stops_only_own_session(self):
        result,calls=self.run_case('completed')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(calls,['status','upload','upload','exec','download','download','stop'])

    def test_terminal_failure_archives_before_stop_and_does_not_retry(self):
        result,calls=self.run_case('failed')
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertEqual(calls,['status','upload','upload','exec','download','download','stop'])

    def test_timeout_never_restarts_downloads_or_stops_running_session(self):
        result,calls=self.run_case('timeout')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(calls,['status','upload','upload','exec'])

    def test_corrupt_backup_never_stops_session(self):
        result,calls=self.run_case('corrupt')
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn('stop',calls)


if __name__=='__main__':unittest.main()
