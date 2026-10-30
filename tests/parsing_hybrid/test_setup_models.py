import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'new_code/setup_models.py'


def load():
    spec=importlib.util.spec_from_file_location('setup_models',SCRIPT)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data)
        self.status=status
        self.headers=headers or {}


class ModelSetupTests(unittest.TestCase):
    def setUp(self):
        self.module=load()
        self.temp=tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.data=b'abcdefghij'
        self.record={'bytes':10,'sha256':hashlib.sha256(self.data).hexdigest()}

    def fetch(self, opener):
        return self.module.fetch_file('https://huggingface.co/org/repo/resolve/'+'a'*40+'/file',
                                      self.root/'file',self.record,opener=opener)

    def test_publishes_only_verified_bytes_and_reuses_cache(self):
        self.fetch(lambda *a,**kw: Response(self.data))
        self.assertEqual((self.root/'file').read_bytes(),self.data)
        self.assertFalse((self.root/'file.part').exists())
        self.fetch(lambda *a,**kw: self.fail('must not download cached file'))

    def test_resume_validates_content_range(self):
        (self.root/'file.part').write_bytes(self.data[:4])
        def opener(request,**kwargs):
            self.assertEqual(request.get_header('Range'),'bytes=4-')
            return Response(self.data[4:],206,{'Content-Range':'bytes 4-9/10'})
        self.fetch(opener)
        self.assertEqual((self.root/'file').read_bytes(),self.data)

    def test_server_ignoring_range_restarts_partial(self):
        (self.root/'file.part').write_bytes(b'abcd')
        self.fetch(lambda *a,**kw:Response(self.data))
        self.assertEqual((self.root/'file').read_bytes(),self.data)

    def test_incorrect_range_never_appends(self):
        (self.root/'file.part').write_bytes(b'abcd')
        with self.assertRaises(ValueError):
            self.fetch(lambda *a,**kw:Response(self.data[4:],206,{'Content-Range':'bytes 2-7/10'}))
        self.assertEqual((self.root/'file.part').read_bytes(),b'abcd')
        self.assertFalse((self.root/'file').exists())

    def test_corrupt_download_is_not_published(self):
        with self.assertRaises(ValueError):
            self.fetch(lambda *a,**kw:Response(b'XXXXXXXXXX'))
        self.assertFalse((self.root/'file').exists())

    def test_corrupt_existing_file_is_preserved_and_rejected(self):
        (self.root/'file').write_bytes(b'XXXXXXXXXX')
        with self.assertRaises(ValueError):
            self.fetch(lambda *a,**kw:self.fail('must preserve corrupt cache for diagnosis'))
        self.assertEqual((self.root/'file').read_bytes(),b'XXXXXXXXXX')

    def test_partial_symlink_is_rejected_before_network_or_write(self):
        original=Path.is_symlink
        def is_symlink(path):
            return path.name=='file.part' or original(path)
        with patch.object(Path,'is_symlink',is_symlink):
            with self.assertRaisesRegex(ValueError,'symlink'):
                self.fetch(lambda *a,**kw:self.fail('must reject before network'))

    def test_silent_operation_shows_heartbeat(self):
        output=io.StringIO()
        with redirect_stdout(output), self.module.heartbeat('test transfer',interval=.02):
            time.sleep(.08)
        self.assertIn('Working: test transfer',output.getvalue())

    def test_complete_partial_is_verified_without_network(self):
        (self.root/'file.part').write_bytes(self.data)
        self.fetch(lambda *a,**kw:self.fail('already downloaded'))
        self.assertTrue((self.root/'file').is_file())

    def test_manifest_rejects_traversal_and_floating_revision(self):
        manifest={'model_id':'org/repo','revision':'a'*40,'files':{'../escape':self.record}}
        with self.assertRaises(ValueError): self.module.validate_manifest(manifest)
        manifest['files']={'file':self.record}
        manifest['revision']='main'
        with self.assertRaises(ValueError): self.module.validate_manifest(manifest)

    def test_configuration_contains_current_paths_and_does_not_overwrite(self):
        paths={name:self.root/name for name in ('layoutlmv3','table_transformer','mineru')}
        output=self.root/'config'
        target=self.module.write_configuration(output,paths,self.root/'environment.json',ROOT/'new_code')
        data=json.loads(target.read_text())
        self.assertEqual(data['model_dirs']['mineru'],str(paths['mineru']))
        self.assertEqual(data['env_manifest'],str(self.root/'environment.json'))
        with self.assertRaises(FileExistsError):
            self.module.write_configuration(output,paths,self.root/'environment.json',ROOT/'new_code')

    def test_plan_is_inert(self):
        cache=self.root/'absent'
        result=subprocess.run([sys.executable,'-B',str(SCRIPT),'--plan','--cache-dir',str(cache)],
                              capture_output=True,text=True,check=True)
        plan=json.loads(result.stdout)
        self.assertEqual(len(plan['models']),3)
        self.assertFalse(cache.exists())

    def test_full_preparation_creates_markers_and_configuration_after_verification(self):
        self.run_preparation(fail=False)

    def test_failed_preparation_does_not_create_completion_markers_or_config(self):
        self.run_preparation(fail=True)

    def run_preparation(self, fail):
        root=self.root/'new_code'
        (root/'model_manifests').mkdir(parents=True)
        (root/'parse_system/vendor/unilm').mkdir(parents=True)
        (root/'runtime').mkdir()
        env=root/'runtime/environment.json'
        env.write_text(json.dumps({'status':'imports-validated'}))
        for name in ('layoutlmv3','table_transformer','mineru'):
            files={'file':self.record} if name!='mineru' else {
                'Layout/PP-DocLayoutV2/file':self.record,'OCR/paddleocr/file':self.record}
            (root/'model_manifests'/f'{name}.json').write_text(json.dumps({
                'model_id':f'org/{name}','revision':'a'*40,'files':files}))
        real_fetch=self.module.fetch_file
        def fetch(url,target,record):
            if fail and '/mineru/' in url:
                raise OSError('fixture network interrupted')
            return real_fetch(url,target,record,opener=lambda *a,**kw:Response(self.data))
        cache=root/'runtime/cache'
        output=root/'runtime/config'
        fake_fcntl=SimpleNamespace(flock=lambda *args:None,LOCK_EX=1,LOCK_NB=2)
        with patch.object(self.module,'ROOT',root), patch.object(self.module.sys,'platform','linux'), \
             patch.object(self.module,'fetch_file',side_effect=fetch), \
             patch.dict(sys.modules,{'fcntl':fake_fcntl}):
            args=['--cache-dir',str(cache),'--env-manifest',str(env),'--output-dir',str(output)]
            if fail:
                with self.assertRaisesRegex(OSError,'interrupted'):self.module.main(args)
            else:self.assertEqual(self.module.main(args),0)
        model=cache/'mineru'/('a'*40)/'MinerU-4_models_torch'
        for marker in self.module.MINERU_MARKERS:
            self.assertEqual((model/marker).exists(),not fail)
        self.assertEqual(output.exists(),not fail)
        if not fail:
            config=json.loads((output/'hybrid-runtime.json').read_text())
            self.assertEqual(config['vendor_dir'],str(root/'parse_system/vendor/unilm'))


if __name__=='__main__': unittest.main()
