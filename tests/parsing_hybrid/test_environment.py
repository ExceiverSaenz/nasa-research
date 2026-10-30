import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from parsing.unified import environment as env

class EnvironmentTests(unittest.TestCase):
    def test_candidate_is_not_a_resolved_lock(self):
        self.assertEqual(env.CANDIDATE['torch'], '2.7.1+cu126')
        self.assertEqual(env.CANDIDATE['transformers'], '5.10.1')
        self.assertEqual(env.PYTHON_VERSION, '3.11.16')

    def test_rejects_unresolved_manifest_before_imports(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            path=Path(temp)/'manifest.json'
            path.write_text(json.dumps({'status':'candidate'}))
            with self.assertRaisesRegex(ValueError, 'validated'):
                env.check_runtime(path, require_cuda=False)

    def test_hash_mismatch_and_path_escape_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root=Path(temp); (root/'file').write_bytes(b'abc')
            env.verify_files(root, {'file':{'bytes':3,'sha256':hashlib.sha256(b'abc').hexdigest()}})
            with self.assertRaises(ValueError):
                env.verify_files(root, {'file':{'bytes':3,'sha256':'0'*64}})
            with self.assertRaises(ValueError):
                env.verify_files(root, {'../file':{'bytes':3,'sha256':'0'*64}})
            with self.assertRaises(ValueError): env.verify_files(root,{})

    def test_prepare_rejects_existing_destination(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            with self.assertRaises((ValueError,RuntimeError)):
                env.prepare(Path(temp), Path('python'), Path('source'), 'a'*40)

    def test_prepare_rejects_destination_inside_baseline_environment(self):
        with self.assertRaisesRegex(ValueError,'baseline'):
            env.prepare(Path.cwd()/'nasa-sic12-document-v1-env-mineru'/'unified-new',Path('python'))
