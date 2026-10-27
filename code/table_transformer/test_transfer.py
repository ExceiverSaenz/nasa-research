"""No-network tests of bundle and pinned model downloads."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'code'))


class TransferTests(unittest.TestCase):
    def helpers(self):
        self.assertIsNotNone(importlib.util.find_spec('table_transformer.prepare'), 'Transfer helpers missing')
        from table_transformer.prepare import prepare_bundle, unpack_bundle
        from table_transformer.remote_job import download_model
        return prepare_bundle, unpack_bundle, download_model

    def test_bundle_is_small_has_original_png_and_no_pdf_or_weights(self):
        prepare, unpack, _ = self.helpers()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); bundle=root/'input.zip'
            prepare(bundle)
            unpack(bundle, bundle.with_suffix('.sha256'), root/'input')
            self.assertEqual(hashlib.sha256((root/'input/render.png').read_bytes()).hexdigest(),
                             '6f46d8ff2d05eee785739ec1c34716db14135411c731e7aa6433e27ca06d00b9')
            with zipfile.ZipFile(bundle) as z:
                self.assertFalse(any(n.endswith(('.pdf','.pth','.bin','.safetensors')) for n in z.namelist()))
            self.assertLess(bundle.stat().st_size, 2*1024*1024)

    def test_corrupt_or_unsafe_bundle_is_rejected_before_writing(self):
        _, unpack, _ = self.helpers()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); bundle=root/'bad.zip'; sidecar=root/'bad.sha256'
            with zipfile.ZipFile(bundle,'w') as z:
                z.writestr('../outside.txt','bad');z.writestr('bundle-manifest.json',json.dumps({'files':{}}))
            sidecar.write_text(hashlib.sha256(bundle.read_bytes()).hexdigest())
            with self.assertRaises(ValueError): unpack(bundle,sidecar,root/'out')
            self.assertFalse((root/'out').exists())
            sidecar.write_text('0'*64)
            with self.assertRaises(ValueError): unpack(bundle,sidecar,root/'out')

    def fixture(self):
        files={'config.json':b'{}','preprocessor_config.json':b'{"size":800}', 'model.safetensors':b'weights'}
        siblings=[]
        for name,data in files.items():
            entry={'rfilename':name,'size':len(data),'blobId':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()}
            if name.endswith('safetensors'): entry['lfs']={'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}
            siblings.append(entry)
        return files,{'sha':'2357cbe2b5a5d1c03e54f32764f06058933b65ab','siblings':siblings}

    def test_download_checks_revision_size_git_blob_and_lfs_hash(self):
        _, _, download = self.helpers(); files,meta=self.fixture()
        def serve(url,timeout):
            if '/api/' in url: return io.BytesIO(json.dumps(meta).encode())
            self.assertIn('/2357cbe2b5a5d1c03e54f32764f06058933b65ab/',url)
            return io.BytesIO(files[url.rsplit('/',1)[-1]])
        with tempfile.TemporaryDirectory() as directory:
            manifest=download(Path(directory),opener=serve)
            self.assertEqual(manifest['files']['model.safetensors']['sha256'],hashlib.sha256(b'weights').hexdigest())
            self.assertEqual((Path(directory)/'model.safetensors').read_bytes(),b'weights')

    def test_corrupted_model_is_not_published_and_error_has_no_url(self):
        _, _, download = self.helpers(); files,meta=self.fixture()
        def serve(url,timeout):
            if '/api/' in url: return io.BytesIO(json.dumps(meta).encode())
            name=url.rsplit('/',1)[-1]
            return io.BytesIO(b'corrupt' if name.endswith('safetensors') else files[name])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError): download(Path(directory),opener=serve)
            self.assertFalse((Path(directory)/'model.safetensors').exists())
            self.assertFalse((Path(directory)/'model.safetensors.part').exists())
        def broken(url,timeout): raise OSError('https://example.org/?token=SECRET')
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError) as caught: download(Path(directory),opener=broken)
            self.assertNotIn('SECRET',str(caught.exception))
            self.assertTrue(caught.exception.__suppress_context__)

    def test_wrong_revision_rejected_without_fetching_files(self):
        _, _, download = self.helpers(); _,meta=self.fixture();meta['sha']='main'
        def serve(url,timeout):
            if '/api/' not in url: raise AssertionError('Must not fetch weights')
            return io.BytesIO(json.dumps(meta).encode())
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError): download(Path(directory),opener=serve)

    def test_second_remote_invocation_preserves_previous_evidence(self):
        self.helpers()
        from table_transformer.remote_job import execute_archived_job
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);job=root/'job.py';job.write_text('print("original execution")')
            state=root/'state';archive=root/'result.zip'
            helper=ROOT/'code/layoutlmv3/cli_job.py'
            self.assertEqual(execute_archived_job(helper,job,state,archive),0)
            before_archive=archive.read_bytes();before_log=(state/'setup-console.log').read_bytes()
            with self.assertRaises(FileExistsError): execute_archived_job(helper,job,state,archive)
            self.assertEqual(archive.read_bytes(),before_archive)
            self.assertEqual((state/'setup-console.log').read_bytes(),before_log)

    def test_retry_reuses_environment_and_writes_separate_outputs(self):
        from unittest.mock import patch
        from table_transformer.retry_job import main
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'tatr-state/page').mkdir(parents=True)
            (root/'tatr-state/page/page-status.json').write_text(json.dumps({'status':'failed','stage':'load'}))
            (root/'tatr-probe/env/bin').mkdir(parents=True)
            (root/'tatr-probe/env/bin/python').touch()
            (root/'tatr-state/requirements-freeze.txt').write_text('saved versions')
            marker=root/'tatr-state/original'; marker.write_text('preserve')
            calls=[]
            def record(command, **kwargs): calls.append((command,kwargs))
            with patch('table_transformer.retry_job.subprocess.run',side_effect=record), \
                 patch('table_transformer.retry_job.unpack_bundle',return_value={'verified':True}):
                main(root)
            self.assertEqual(len(calls),2)
            self.assertEqual(calls[1][0][0],str(root/'tatr-probe/env/bin/python'))
            self.assertEqual(calls[1][0][-1],str(root/'tatr-retry-state/page'))
            self.assertEqual(calls[1][1]['env']['PYTHONPATH'],str(root/'tatr-retry-inputs'))
            self.assertEqual(marker.read_text(),'preserve')
            self.assertEqual((root/'tatr-retry-state/requirements-freeze.txt').read_text(),'saved versions')


if __name__ == '__main__': unittest.main()
