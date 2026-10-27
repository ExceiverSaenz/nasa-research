import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code'))


class TransferTests(unittest.TestCase):
    def test_local_receipt_rejects_modified_model_before_activation(self):
        from mineru_probe.remote_job import verify_receipt
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'model.bin').write_bytes(b'bad')
            receipt={'files':{'model.bin':{'bytes':4,'sha256':hashlib.sha256(b'good').hexdigest()}}}
            with self.assertRaises(ValueError):verify_receipt(receipt,root)
            (root/'model.bin').write_bytes(b'good')
            verify_receipt(receipt,root)

    def test_bundle_contains_only_fixed_input_and_code(self):
        from mineru_probe.prepare import prepare_bundle, unpack_bundle
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bundle=root/'input.zip'
            prepare_bundle(bundle)
            unpack_bundle(bundle,bundle.with_suffix('.sha256'),root/'unpacked')
            self.assertTrue((root/'unpacked/render.png').exists())
            self.assertFalse(list((root/'unpacked').rglob('*.pdf')))
            self.assertLess(bundle.stat().st_size,2*1024*1024)
            with self.assertRaises(FileExistsError):unpack_bundle(bundle,bundle.with_suffix('.sha256'),root/'unpacked')

    def test_unsafe_bundle_never_extracts(self):
        from mineru_probe.prepare import unpack_bundle
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bundle=root/'bad.zip'
            with zipfile.ZipFile(bundle,'w') as z:z.writestr('../escape','x')
            sidecar=bundle.with_suffix('.sha256');sidecar.write_text(hashlib.sha256(bundle.read_bytes()).hexdigest())
            with self.assertRaises(ValueError):unpack_bundle(bundle,sidecar,root/'out')
            self.assertFalse((root/'out').exists())

    def test_download_rejects_corruption_and_removes_partial(self):
        from mineru_probe.remote_job import download_models
        manifest={'model_id':'org/model','revision':'a'*40,'files':{'nested/model.bin':{
            'bytes':4,'digest_type':'sha256','source_digest':hashlib.sha256(b'good').hexdigest()}}}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(RuntimeError):download_models(manifest,root,opener=lambda *a,**k:io.BytesIO(b'evil'))
            self.assertFalse((root/'nested/model.bin').exists())
            self.assertFalse((root/'nested/model.bin.part').exists())
            receipt=download_models(manifest,root,opener=lambda *a,**k:io.BytesIO(b'good'))
            self.assertEqual(receipt['files']['nested/model.bin']['sha256'],hashlib.sha256(b'good').hexdigest())

    def test_second_job_cannot_overwrite_evidence(self):
        from mineru_probe.remote_job import execute_archived_job
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);job=root/'job.py';job.write_text('print("probe")')
            archive=root/'result.zip';state=root/'state'
            helper=ROOT/'code/layoutlmv3/cli_job.py'
            self.assertEqual(execute_archived_job(helper,job,state,archive),0)
            original=archive.read_bytes()
            with self.assertRaises(FileExistsError):execute_archived_job(helper,job,state,archive)
            self.assertEqual(archive.read_bytes(),original)


if __name__=='__main__':unittest.main()
