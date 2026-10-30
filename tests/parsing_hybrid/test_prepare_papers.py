import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'new_code'))
import prepare_papers as p


class PaperPreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.config={'R2_ENDPOINT_URL':'https://fixture.r2.cloudflarestorage.com','R2_BUCKET':'papers',
                     'R2_PREFIX':'sic_papers/','AWS_ACCESS_KEY_ID':'public-id','AWS_SECRET_ACCESS_KEY':'PRIVATE-SECRET'}
        (self.root/'12.pdf').write_bytes(b'%PDF-1.7\nfixture')

    def request(self):
        target=self.root/'request.json'
        with redirect_stdout(io.StringIO()):p.sign_request(self.root,['12.pdf'],self.config,target)
        return target

    def test_sign_uses_original_hash_without_secret_in_request(self):
        target=self.request();raw=target.read_text();item=json.loads(raw)['files'][0]
        self.assertNotIn('PRIVATE-SECRET',raw)
        self.assertEqual(item['sha256'],p.digest(self.root/'12.pdf'))
        self.assertEqual(item['key'],'sic_papers/12.pdf')
        self.assertIn('X-Amz-Signature=',item['url'])

    def test_verified_cache_and_receipt_do_not_expose_signed_urls(self):
        request=self.request();out=self.root/'inputs';out.mkdir()
        (out/'12.pdf').write_bytes((self.root/'12.pdf').read_bytes())
        output=io.StringIO()
        with redirect_stdout(output):
            p.download_request(request,out)
            p.download_request(request,out)
        self.assertNotIn('X-Amz-',output.getvalue())
        self.assertNotIn('X-Amz-',(out/'r2-download-receipt.json').read_text())

    def test_network_errors_do_not_leak_bearer_urls(self):
        request=self.request()
        with patch.object(p,'fetch_file',side_effect=RuntimeError('https://secret?signature=PRIVATE')):
            with self.assertRaises(RuntimeError) as error:p.download_request(request,self.root/'inputs')
        self.assertNotIn('PRIVATE',str(error.exception))

    def test_path_escape_and_bad_hash_rejected_before_network(self):
        request=self.request();value=json.loads(request.read_text())
        for field,bad in [('name','../escape.pdf'),('sha256','bad')]:
            changed=json.loads(json.dumps(value));changed['files'][0][field]=bad
            request.write_text(json.dumps(changed))
            with patch.object(p,'fetch_file') as fetch:
                with self.assertRaises(ValueError):p.download_request(request,self.root/'inputs')
                fetch.assert_not_called()

    def test_sign_rejects_overwrite_and_missing_selection(self):
        self.request()
        with self.assertRaises(FileExistsError):self.request()
        with self.assertRaises(ValueError):p.sign_request(self.root,['../12.pdf'],self.config,self.root/'other.json')
