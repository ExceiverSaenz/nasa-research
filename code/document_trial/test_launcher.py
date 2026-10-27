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
SCRIPT=ROOT/'code/document_trial/run_document.sh'


class DocumentBootstrapTests(unittest.TestCase):
    def bootstrap(self):
        return re.search(r"bounded_cli[^\n]*exec -s[^\n]*<<'PY'[^\n]*\n(.*?)\nPY",SCRIPT.read_text(encoding='utf-8'),re.S).group(1)

    def namespace(self,folder,status='completed',main=None,verified=True):
        prefix=Path(folder)/'remote'
        inputs=prefix.with_name(prefix.name+'-inputs');inputs.mkdir()
        (inputs/'plan.json').write_text('{}')
        prefix.with_name(prefix.name+'-upload.zip').write_bytes(b'fake-upload')
        prefix.with_name(prefix.name+'-attempt.json').write_text('{"attempt_id":"test-attempt"}')
        def verify(*args):
            if not verified:raise FileNotFoundError('no verified backup')
            return {'status':status}
        return dict(PREFIX=prefix,verify_terminal=verify,main=main or (lambda:0))

    def test_kernel_arguments_and_old_experiment_modules_are_isolated(self):
        old_args=sys.argv;old_path=sys.path[:]
        stale=types.ModuleType('document_trial.old_experiment');sys.modules[stale.__name__]=stale
        def inert_main():
            argparse.ArgumentParser().parse_args()
            self.assertNotIn(stale.__name__,sys.modules)
            return 0
        try:
            sys.argv=['kernel','-f','kernel.json']
            with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as folder:
                ns=self.namespace(folder,main=inert_main)
                with patch('runpy.run_module',return_value=ns),contextlib.redirect_stdout(io.StringIO()) as out:exec(self.bootstrap(),{})
                self.assertIn('DOCUMENT_ARCHIVE_READY completed',out.getvalue())
            self.assertEqual(sys.argv,['kernel','-f','kernel.json']);self.assertEqual(sys.path,old_path)
            self.assertIs(sys.modules[stale.__name__],stale)
        finally:sys.argv=old_args;sys.modules.pop(stale.__name__,None)

    def test_failed_main_returns_normally_to_kernel_with_verified_failed_marker(self):
        with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as folder:
            ns=self.namespace(folder,status='failed',main=lambda:1)
            with patch('runpy.run_module',return_value=ns),contextlib.redirect_stdout(io.StringIO()) as out:exec(self.bootstrap(),{})
            self.assertIn('DOCUMENT_ARCHIVE_READY failed',out.getvalue())

    def test_systemexit_is_not_propagated_and_unverified_backup_has_no_terminal_marker(self):
        def exit_main():raise SystemExit(1)
        argv=sys.argv[:];paths=sys.path[:]
        with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as folder:
            ns=self.namespace(folder,main=exit_main,verified=False)
            with patch('runpy.run_module',return_value=ns),contextlib.redirect_stdout(io.StringIO()) as out,contextlib.redirect_stderr(io.StringIO()):exec(self.bootstrap(),{})
            self.assertIn('DOCUMENT_NO_VERIFIED_ARCHIVE',out.getvalue());self.assertNotIn('DOCUMENT_ARCHIVE_READY',out.getvalue())
        self.assertEqual(sys.argv,argv);self.assertEqual(sys.path,paths)


@unittest.skipUnless(os.environ.get('HEADER_TEST_BASH'),'Requires explicitly selected Bash; fake CLI only')
class DocumentShellTests(unittest.TestCase):
    def run_case(self,mode,package=None):
        package=package or "code/packages/sic-parsing-v1/3"
        with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as temp:
            temp=Path(temp);shim=temp/'bin';shim.mkdir()
            python=sys.executable.replace('\\','/')
            (shim/'python3').write_text('#!/usr/bin/env bash\nexec "'+python+'" "$@"\n',encoding='utf-8')
            fake=temp/'fake_colab.py'
            fake.write_text('''import os,sys,json,zipfile,hashlib,time
from pathlib import Path
root=Path(os.environ['HEADER_FAKE_ROOT']);log=Path(os.environ['HEADER_FAKE_LOG']);mode=os.environ['HEADER_FAKE_MODE']
with log.open('a') as f:f.write(sys.argv[1]+'\\n')
command=sys.argv[1]
if command=='status':print('Hardware: T4 | Status: IDLE')
elif command=='upload':
    if mode=='part-failed' and sys.argv[-1].endswith('part-0001'):raise SystemExit(1)
    if '/sic-transfer-' in sys.argv[-1]:
        dest=root/'remote'/Path(sys.argv[-1]).name;dest.parent.mkdir(exist_ok=True);dest.write_bytes(Path(sys.argv[-2]).read_bytes())
    if mode=='upload-failed':print('Upload failed: 400 Bad Request');raise SystemExit(1)
    if sys.argv[-1].endswith('-attempt.json'):(root/'attempt.json').write_bytes(Path(sys.argv[-2]).read_bytes())
    if sys.argv[-1].endswith('-upload.zip'):(root/'selected-upload.zip').write_bytes(Path(sys.argv[-2]).read_bytes())
elif command=='exec':
    if '-f' in sys.argv:
        if mode=='assembly-unverified':raise SystemExit(0)
        source=Path(sys.argv[sys.argv.index('-f')+1]).read_text()
        source=source.replace('/content/',(root/'remote').as_posix()+'/')
        exec(source,{})
        (root/'selected-upload.zip').write_bytes((root/'remote/nasa-sic12-document-v1-upload.zip').read_bytes())
        raise SystemExit(0)
    sys.stdin.read()
    if mode in ('timeout','timeout-valid'):print('timeout');raise SystemExit(124)
    if mode in ('hang-valid','hang-no-backup'):print('fake-cli-stalled',flush=True);time.sleep(30)
    print('DOCUMENT_ARCHIVE_READY '+('failed' if mode=='failed' else 'completed'))
elif command=='download':
    if mode in ('timeout','hang-no-backup'):raise SystemExit('No terminal archive')
    destination=Path(sys.argv[-1]);source=root/'returned.zip'
    if not source.exists():
        with zipfile.ZipFile(source,'w') as z:
            with zipfile.ZipFile(root/'selected-upload.zip') as upload:
                z.writestr('plan.json',upload.read('plan.json'))
                plan=json.loads(upload.read('plan.json'))
                for entry in plan.get('documents',[]):
                    prefix='documents/'+entry['key']+'/'
                    z.writestr(prefix+'plan.json',json.dumps(entry['plan']))
                    z.writestr(prefix+'execution-status.json',json.dumps({'status':'failed' if mode=='failed' else 'completed'}))
                    for page in entry['plan']['physical_pages']:
                        folder=prefix+'pages/'+('%04d'%page)+'/'
                        z.writestr(folder+'identity.json',json.dumps({'document_sha256':entry['key'],'physical_page':page}))
                        for model,files in {'layoutlmv3':['regions.json','detector.json'],'table_transformer':['regions-raw.json','regions.json','detector.json'],'mineru':['middle-native.json','regions.json']}.items():
                            z.writestr(folder+model+'/status.json',json.dumps({'status':'not_run' if mode=='failed' else 'completed','page':page,'model':model}))
                            for name in files:z.writestr(folder+model+'/'+name,'{}')
            z.writestr('execution.json',json.dumps({'bundle_sha256':hashlib.sha256((root/'selected-upload.zip').read_bytes()).hexdigest(),'attempt_id':'old-attempt' if mode=='stale' else json.loads((root/'attempt.json').read_text())['attempt_id']}))
            z.writestr('execution-status.json',json.dumps({'status':'failed' if mode=='failed' else 'completed'}))
    if sys.argv[-2].endswith('.sha256'):
        destination.write_text(('0'*64 if mode=='corrupt' else hashlib.sha256(source.read_bytes()).hexdigest())+'\\n')
    else:destination.write_bytes(source.read_bytes())
elif command=='stop':
    if mode=='hang-stop':time.sleep(30)
    if mode=='stop-failed':raise SystemExit(3)
    print('fake own session stopped')
else:raise SystemExit('Unexpected fake command')
''',encoding='utf-8')
            driver=temp/'python_driver.py'
            driver.write_text("import os,sys,subprocess\nargs=sys.argv[1:]\nif args[:3]==['-B','-m','document_trial.cli']:\n i=args.index('--')+1\n assert args[i]=='colab'\n args[i:i+1]=[sys.executable,"+repr(str(fake))+"]\nraise SystemExit(subprocess.run([sys.executable]+args).returncode)\n",encoding='utf-8')
            (shim/'python3').write_text('#!/usr/bin/env bash\nexec "'+python+'" "'+driver.as_posix()+'" "$@"\n',encoding='utf-8')
            (shim/'colab').write_text('#!/usr/bin/env bash\nexec "'+python+'" "'+fake.as_posix()+'" "$@"\n',encoding='utf-8')
            # Recreate a tiny workspace with actual source/package files for the launcher's checks.
            import shutil
            (temp/'code/document_trial').mkdir(parents=True)
            shutil.copyfile(SCRIPT,temp/'code/document_trial/run_document.sh')
            with zipfile.ZipFile(ROOT/'code/packages/sic12-document-v5/upload.zip') as z:
                for name in z.namelist():
                    if name.startswith(('document_trial/',)):
                        target=temp/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
            shutil.copyfile(ROOT/'code/document_trial/common.py',temp/'code/document_trial/common.py')
            shutil.copyfile(ROOT/'code/document_trial/transfer.py',temp/'code/document_trial/transfer.py')
            shutil.copytree(ROOT/'code/packages/sic12-document-v5',temp/'code/packages/sic12-document-v5')
            if package:shutil.copytree(ROOT/package,temp/package)
            env=os.environ.copy();env.update(HEADER_FAKE_ROOT=str(temp),HEADER_FAKE_LOG=str(temp/'calls.log'),HEADER_FAKE_MODE=mode,DOC_EXEC_TIMEOUT='1.5',DOC_CALL_TIMEOUT='1.5' if mode=='hang-stop' else '10')
            # Convert shim prefix to Unix form inside Bash before invoking the launcher.
            command='export PATH="$(cygpath -u "$HEADER_FAKE_ROOT")/bin:$PATH"; bash "$(cygpath -u "$HEADER_FAKE_ROOT")/code/document_trial/run_document.sh" fake-own-session --own-session'
            command+=' '+(package or 'code/packages/sic12-document-v5')
            result=subprocess.run([env['HEADER_TEST_BASH'],'-c',command],capture_output=True,text=True,env=env,cwd=temp,timeout=600)
            self.assertTrue((temp/'calls.log').exists(),result.stdout+result.stderr)
            calls=(temp/'calls.log').read_text().splitlines()
            return result,calls

    def test_batch_one_parsing_exec_after_verified_assembly_one_stop(self):
        result,calls=self.run_case('completed','code/packages/sic-parsing-all-v1')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(calls,['status']+['upload']*92+['exec','upload','upload','exec','download','download','stop'])

    def test_batch_fragment_failure_stops_without_assembly_or_parsing(self):
        result,calls=self.run_case('part-failed','code/packages/sic-parsing-all-v1')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(calls,['status','upload','upload'])

    def test_batch_missing_assembly_marker_prevents_parsing_and_stop(self):
        result,calls=self.run_case('assembly-unverified','code/packages/sic-parsing-all-v1')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(calls,['status']+['upload']*92+['exec'])

    def test_other_document_package_uses_same_three_branch_workflow(self):
        result,calls=self.run_case('completed','code/packages/sic-parsing-v1/3')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(calls,['status','upload','upload','upload','exec','download','download','stop'])

    def test_paper_one_uses_direct_upload_even_above_fragment_limit(self):
        self.assertGreater((ROOT/'code/packages/sic-parsing-v1/1/upload.zip').stat().st_size,1048576)
        result,calls=self.run_case('completed','code/packages/sic-parsing-v1/1')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(calls,['status','upload','upload','upload','exec','download','download','stop'])
        self.assertNotIn('Transferencia fragmentada',result.stdout)

    def test_upload_failure_is_visible_without_exec_retry_or_stop(self):
        result,calls=self.run_case('upload-failed')
        self.assertEqual(result.returncode,1)
        self.assertEqual(calls,['status','upload'])
        self.assertIn('Fallo en colab upload (codigo 1)',result.stderr)
        self.assertIn('upload-zip.log',result.stderr)

    def test_success_downloads_verifies_then_stops_only_own_session(self):
        result,calls=self.run_case('completed')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(calls,['status','upload','upload','upload','exec','download','download','stop'])

    def test_terminal_failure_archives_before_stop_and_does_not_retry(self):
        result,calls=self.run_case('failed')
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertEqual(calls,['status','upload','upload','upload','exec','download','download','stop'])

    def test_timeout_never_restarts_downloads_or_stops_running_session(self):
        result,calls=self.run_case('timeout')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(calls,['status','upload','upload','upload','exec','download'])

    def test_stale_matching_plan_backup_never_stops_session(self):
        result,calls=self.run_case('stale')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Terminal attempt identity differs',result.stderr)
        self.assertNotIn('stop',calls)

    def test_corrupt_backup_never_stops_session(self):
        result,calls=self.run_case('corrupt')
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn('stop',calls)

    def test_actual_stalled_cli_with_valid_backup_finishes_then_closes(self):
        result,calls=self.run_case('hang-valid')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(calls,['status','upload','upload','upload','exec','download','download','stop'])

    def test_actual_stalled_cli_without_backup_finishes_without_stop(self):
        result,calls=self.run_case('hang-no-backup')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(calls,['status','upload','upload','upload','exec','download'])

    def test_stalled_stop_returns_error_without_claiming_closed(self):
        result,calls=self.run_case('hang-stop')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('cierre no confirmado',result.stdout+result.stderr)
        self.assertNotIn('Sesion propia cerrada',result.stdout)
        self.assertEqual(calls.count('exec'),1);self.assertEqual(calls.count('stop'),1)

    def test_failed_stop_is_reported_without_claiming_closed(self):
        result,calls=self.run_case('stop-failed')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('cierre no confirmado',result.stdout+result.stderr)
        self.assertEqual(calls.count('exec'),1);self.assertEqual(calls.count('stop'),1)


if __name__=='__main__':unittest.main()
