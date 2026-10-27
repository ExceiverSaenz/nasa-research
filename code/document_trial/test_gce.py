"""Offline contracts. Never imports models or contacts GCE."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import os
import subprocess
import sys
from unittest.mock import patch
import zipfile

from document_trial.common import save, sha, MODELS


class GCEContracts(unittest.TestCase):
    def test_derived_package_changes_only_declared_members_and_preserves_original(self):
        from document_trial.gce_package import prepare_gce
        root=Path(__file__).resolve().parents[2]
        base=root/'code/packages/sic-parsing-v1/10'
        before=sha(base/'upload.zip')
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'package';prepare_gce(base,target)
            with zipfile.ZipFile(base/'upload.zip') as old,zipfile.ZipFile(target/'upload.zip') as new:
                changed={n for n in old.namelist() if old.read(n)!=new.read(n)}
                self.assertEqual(changed,{'plan.json','bundle-manifest.json','document_trial/remote.py','document_trial/worker.py'})
                self.assertEqual(set(new.namelist())-set(old.namelist()),{'document_trial/gce_entry.py'})
            self.assertEqual(sha(base/'upload.zip'),before)
            with self.assertRaises(FileExistsError):prepare_gce(base,target)

    def test_external_plan_mismatch_blocks_package(self):
        from document_trial.gce_package import prepare_gce
        root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'base';base.mkdir()
            original=root/'code/packages/sic-parsing-v1/10'
            for n in ('upload.zip','upload.sha256'):(base/n).write_bytes((original/n).read_bytes())
            (base/'plan.json').write_text('{}')
            with self.assertRaises(ValueError):prepare_gce(base,Path(tmp)/'out')

    def test_host_mismatch_or_non_t4_or_driver_blocks(self):
        from document_trial.gce_entry import validate_host
        good=dict(project='nasa-512810',instance='nasa-parsing-t4',zone='us-central1-a',instance_id='123456',gpu='Tesla T4',driver='570.124.06',free_bytes=80*1024**3)
        expected={k:good[k] for k in ('project','instance','zone','instance_id')}
        validate_host(good,expected)
        for key,value in [('project','elsewhere'),('instance_id','654321'),('gpu','NVIDIA L4'),('driver','535.1'),('free_bytes',1)]:
            with self.subTest(key=key),self.assertRaises(ValueError):validate_host(dict(good,**{key:value}),expected)

    def test_no_user_authorization_blocks_before_metadata_or_coordinator(self):
        from document_trial.gce_entry import user_run
        with patch('document_trial.gce_entry.collect_host') as host:
            with self.assertRaises(RuntimeError):user_run({},False)
            host.assert_not_called()

    def test_transformed_controller_retains_failed_backup_without_models(self):
        from document_trial.gce_package import prepare_gce
        root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'package';prepare_gce(root/'code/packages/sic-parsing-v1/10',target)
            # Isolated subprocess loads actual transformed controller from its ZIP.
            script=r'''
import sys,os,json,uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
from document_trial import remote
from document_trial.common import save,verify_terminal,sha
root=Path(sys.argv[2]);prefix=root/'nasa-sic12-document-v1'
bundle=prefix.with_name(prefix.name+'-upload.zip');bundle.write_bytes(Path(sys.argv[1]).read_bytes())
bundle.with_suffix('.sha256').write_text(sha(bundle))
save(prefix.with_name(prefix.name+'-attempt.json'),dict(attempt_id='a'*32))
def fail(inputs,state):
    assert os.environ['NASA_DOCUMENT_USER_RUN']=='GCE_SSH_T4'
    raise RuntimeError('synthetic setup failure; no models')
actual_read=remote.read
def read(path):
    if str(path)=='/content/gce-host.json':return dict(project='nasa-512810')
    return actual_read(path)
with patch.object(remote,'PREFIX',prefix),patch.object(remote.platform,'system',return_value='Linux'),patch.object(remote.Path,'is_dir',return_value=True),patch.dict(os.environ,NASA_DOCUMENT_USER_RUN='GCE_SSH_T4'),patch.object(remote,'setup',side_effect=fail),patch.object(remote,'read',side_effect=read):
    assert remote.main()==1
with __import__('zipfile').ZipFile(prefix.with_suffix('.zip')) as z:
    execution=json.loads(z.read('execution.json'));assert execution['initiator']=='human_gce_ssh'
    assert json.loads(z.read('gce-host.json'))['project']=='nasa-512810'
    for p in range(1,10):
        for m in ('layoutlmv3','table_transformer','mineru'):
            assert json.loads(z.read('pages/%04d/%s/status.json'%(p,m)))['status']=='not_run'
assert verify_terminal(prefix.with_suffix('.zip'),prefix.with_suffix('.sha256'),(prefix.with_name(prefix.name+'-inputs')/'plan.json').read_bytes(),sha(bundle),'a'*32)['status']=='failed'
'''
            result=subprocess.run([sys.executable,'-B','-c',script,str(target/'upload.zip'),tmp],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    @unittest.skipUnless(os.name=='posix','Bash orchestration tested on Linux/WSL')
    def test_shell_failure_never_submits_or_stops_and_create_has_limit(self):
        root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);fake=d/'gcloud'
            fake.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$FAKE_LOG"\nexit "${FAKE_EXIT:-0}"\n');fake.chmod(0o755)
            env=dict(os.environ,PATH=str(d)+':'+os.environ['PATH'],FAKE_LOG=str(d/'calls'))
            command=['bash',str(root/'code/document_trial/gce.sh')]
            result=subprocess.run(command+['create'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            calls=(d/'calls').read_text()
            for item in ('--max-run-duration=4h','--instance-termination-action=STOP','--no-restart-on-failure','--no-service-account','--no-scopes','nvidia-tesla-t4'):
                self.assertIn(item,calls)
            (d/'calls').write_text('')
            # Original Colab policy must fail local validation before any cloud call.
            result=subprocess.run(command+['submit',str(root/'code/packages/sic-parsing-v1/10'),str(d/'attempt')],env=dict(env,FAKE_EXIT='1'),capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((d/'calls').read_text(),'')

    @unittest.skipUnless(os.name=='posix','Bash orchestration tested on Linux/WSL')
    def test_shell_submit_collect_stop_and_corrupt_backup_guard(self):
        from document_trial.gce_package import prepare_gce
        root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);package=d/'package';run=d/'attempt'
            prepare_gce(root/'code/packages/sic-parsing-v1/10',package)
            fake=d/'gcloud'
            fake.write_text('''#!/usr/bin/env python3
import os,sys,json,pathlib,zipfile,hashlib,subprocess
a=sys.argv[1:]
with open(os.environ['FAKE_LOG'],'a') as out:out.write(json.dumps(a)+'\\n')
if os.environ.get('FAIL_MATCH') and os.environ['FAIL_MATCH'] in ' '.join(a):sys.exit(7)
if a[0:3]==['compute','instances','describe']:print(os.environ.get('FAKE_VM_ID','123456'))
if a[0:2]==['compute','ssh'] and os.environ.get('TRY_STOP_SHELL'):
    cmd=next(v.split('=',1)[1] for v in a if v.startswith('--command='))
    if cmd.startswith('load='):sys.exit(subprocess.run(['bash','-c',cmd]).returncode)
if len(a)>2 and a[0:2]==['compute','scp'] and ':/content/' in a[2]:
    target=pathlib.Path(a[3]);run=pathlib.Path(os.environ['RUN']);package=pathlib.Path(os.environ['PACKAGE'])
    if a[2].endswith('.zip'):
        plan=json.loads((package/'plan.json').read_bytes());attempt=json.loads((run/'attempt.json').read_text())
        with zipfile.ZipFile(target,'w') as z:
            z.writestr('plan.json',(package/'plan.json').read_bytes())
            z.writestr('execution.json',json.dumps(dict(bundle_sha256=attempt['bundle_sha256'],attempt_id=attempt['attempt_id'],initiator='human_gce_ssh')))
            z.writestr('execution-status.json',json.dumps(dict(status='failed')))
            z.writestr('gce-host.json',json.dumps(attempt))
            for p in plan['physical_pages']:
                for m in ('layoutlmv3','table_transformer','mineru'):
                    z.writestr('pages/%04d/%s/status.json'%(p,m),json.dumps(dict(status='not_run',page=p,model=m)))
    else:target.write_text(hashlib.sha256((run/'result.zip').read_bytes()).hexdigest())
''');fake.chmod(0o755)
            ctl=d/'systemctl'
            ctl.write_text('#!/bin/bash\nif [[ "${CTL_FAIL:-0}" == 1 ]]; then exit 1; fi\nif [[ "$*" == *LoadState* ]]; then echo "${CTL_LOAD:-loaded}"; elif [[ "$*" == *SubState* ]]; then echo "${CTL_SUB:-dead}"; else echo "${CTL_STATE:-inactive}"; fi\n');ctl.chmod(0o755)
            env=dict(os.environ,PATH=str(d)+':'+os.environ['PATH'],FAKE_LOG=str(d/'calls'),RUN=str(run),PACKAGE=str(package))
            command=['bash',str(root/'code/document_trial/gce.sh')]
            def call(action,**extra):
                return subprocess.run(command+[action,str(package),str(run)],env=dict(env,**extra),capture_output=True,text=True)
            result=call('submit');self.assertEqual(result.returncode,0,result.stderr)
            calls=(d/'calls').read_text()
            self.assertIn('launch.sh',calls);self.assertNotIn('instances", "stop',calls)
            count=len(calls)
            self.assertNotEqual(call('submit').returncode,0)
            self.assertEqual(len((d/'calls').read_text()),count)
            result=call('collect');self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads((run/'backup-verified.json').read_text())['status'],'failed')
            self.assertNotIn('instances", "stop',(d/'calls').read_text())
            for options in (dict(CTL_LOAD='not-found'),dict(CTL_STATE='active'),dict(CTL_FAIL='1')):
                (d/'calls').write_text('')
                self.assertNotEqual(call('stop',TRY_STOP_SHELL='1',**options).returncode,0)
                self.assertNotIn('instances", "stop',(d/'calls').read_text())
            result=call('stop',TRY_STOP_SHELL='1');self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('instances", "stop',(d/'calls').read_text())
            result=call('stop',TRY_STOP_SHELL='1',CTL_STATE='active',CTL_SUB='exited');self.assertEqual(result.returncode,0,result.stderr)
            (d/'calls').write_text('')
            self.assertNotEqual(call('stop',FAKE_VM_ID='654321').returncode,0)
            self.assertNotIn('instances", "stop',(d/'calls').read_text())
            (d/'calls').write_text('');(run/'result.zip').write_bytes(b'corrupt')
            self.assertNotEqual(call('stop').returncode,0)
            self.assertNotIn('instances", "stop',(d/'calls').read_text())

    @unittest.skipUnless(os.name=='posix','Bash orchestration tested on Linux/WSL')
    def test_real_gce_package_transfer_failure_does_not_launch_or_stop(self):
        from document_trial.gce_package import prepare_gce
        root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);package=d/'package';prepare_gce(root/'code/packages/sic-parsing-v1/10',package)
            fake=d/'gcloud'
            fake.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$FAKE_LOG"\nif [[ "$2" == instances && "$3" == describe ]]; then echo 123456; fi\nif [[ "$2" == scp ]]; then exit 7; fi\n');fake.chmod(0o755)
            env=dict(os.environ,PATH=str(d)+':'+os.environ['PATH'],FAKE_LOG=str(d/'calls'))
            result=subprocess.run(['bash',str(root/'code/document_trial/gce.sh'),'submit',str(package),str(d/'attempt')],env=env,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            calls=(d/'calls').read_text().splitlines()
            self.assertEqual(len(calls),3)  # instance identity, preflight, one scp
            self.assertTrue(calls[2].startswith('compute scp '))
            self.assertFalse(any('instances stop' in s for s in calls))

    def test_launch_script_uses_one_nonrestarting_service_and_refuses_reuse(self):
        from document_trial.gce_entry import remote_launch_script
        script=remote_launch_script('a'*32,dict(project='nasa-512810',instance='nasa-parsing-t4',zone='us-central1-a',instance_id='123456'))
        self.assertIn('Restart=no',script)
        self.assertIn('RemainAfterExit=yes',script)
        self.assertIn('systemd-run',script)
        self.assertIn('mkdir /content/gce-claimed',script)
        self.assertNotIn('colab ',script)
        self.assertNotIn('shutdown',script)
        with self.assertRaises(ValueError):remote_launch_script('bad; rm',{})

    def terminal(self,directory,missing=None,status='completed',attempt='a'*32):
        plan=dict(document_sha256='b'*64,physical_pages=[1],page_count=1,dpi=200)
        raw=(json.dumps(plan)+'\n').encode()
        files={'plan.json':raw,'execution.json':json.dumps(dict(bundle_sha256='c'*64,attempt_id=attempt,initiator='human_gce_ssh')).encode(),
               'execution-status.json':json.dumps(dict(status=status)).encode(),'gce-host.json':json.dumps(dict(project='nasa-512810',instance='nasa-parsing-t4',zone='us-central1-a',instance_id='123456')).encode()}
        folder='pages/0001/'
        files[folder+'identity.json']=json.dumps(dict(document_sha256='b'*64,physical_page=1,render_sha256=hashlib.sha256(b'png').hexdigest())).encode()
        files[folder+'render.png']=b'png'
        required={'layoutlmv3':['regions.json','detector.json'],'table_transformer':['regions-raw.json','regions.json','detector.json'],'mineru':['middle-native.json','regions.json']}
        for model in MODELS:
            files[folder+model+'/status.json']=json.dumps(dict(status='completed' if status=='completed' else 'not_run',page=1,model=model)).encode()
            for name in required[model]:files[folder+model+'/'+name]=b'{}'
        with zipfile.ZipFile(directory/'result.zip','w') as z:
            for name,data in files.items():
                if name!=missing:z.writestr(name,data)
        (directory/'result.sha256').write_text(sha(directory/'result.zip'))
        return raw

    def test_terminal_intake_checks_identity_members_and_failed_states(self):
        from document_trial.gce_entry import verify_gce_terminal
        expected=dict(project='nasa-512810',instance='nasa-parsing-t4',zone='us-central1-a',instance_id='123456')
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            for missing in [None,'pages/0001/mineru/middle-native.json','pages/0001/layoutlmv3/status.json','pages/0001/render.png']:
                raw=self.terminal(d,missing=missing)
                if missing:
                    with self.assertRaises((ValueError,KeyError)):verify_gce_terminal(d/'result.zip',d/'result.sha256',raw,'c'*64,'a'*32,expected)
                else:
                    self.assertEqual(verify_gce_terminal(d/'result.zip',d/'result.sha256',raw,'c'*64,'a'*32,expected)['status'],'completed')
                    with self.assertRaises(ValueError):verify_gce_terminal(d/'result.zip',d/'result.sha256',raw,'c'*64,'a'*32,dict(expected,instance_id='654321'))
                    with self.assertRaises(ValueError):verify_gce_terminal(d/'result.zip',d/'result.sha256',raw,'c'*64,'d'*32,expected)
            raw=self.terminal(d,status='failed')
            self.assertEqual(verify_gce_terminal(d/'result.zip',d/'result.sha256',raw,'c'*64,'a'*32,expected)['status'],'failed')

if __name__=='__main__':unittest.main()
