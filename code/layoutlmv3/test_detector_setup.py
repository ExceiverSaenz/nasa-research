import importlib.util
from pathlib import Path
import tempfile
import unittest
import tarfile
import io
import hashlib
from unittest.mock import patch


class InputTests(unittest.TestCase):
    def load(self):
        spec = importlib.util.spec_from_file_location('installer', Path(__file__).with_name('install_detector.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_archive_cannot_write_outside_destination(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'bad.tar.gz'
            with tarfile.open(archive, 'w:gz') as output:
                member = tarfile.TarInfo('../outside.txt')
                member.size = 1
                output.addfile(member, io.BytesIO(b'x'))
            with self.assertRaises(ValueError):
                module.extract_archive(archive, root / 'output')
            self.assertFalse((root / 'outside.txt').exists())

    def test_corrupted_weights_fail_verification(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'model.pth'
            path.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                module.check_file(path, {'bytes': 7, 'sha256': '0' * 64})

    def test_download_publishes_only_verified_file_from_fixed_revision(self):
        module = self.load()
        self.assertTrue(callable(getattr(module, 'download_model', None)))
        payload = b'verified weights'
        manifest = self.manifest(payload)
        def serve(url, timeout):
            self.assertEqual(url, 'https://huggingface.co/HYPJUDY/layoutlmv3-base-finetuned-publaynet/resolve/' + '1' * 40 + '/model_final.pth')
            self.assertGreater(timeout, 0)
            return io.BytesIO(payload)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(module, 'urlopen', side_effect=serve):
                module.download_model(manifest, Path(directory))
            self.assertEqual((Path(directory) / 'model_final.pth').read_bytes(), payload)
            self.assertFalse((Path(directory) / 'model_final.pth.part').exists())

    def manifest(self, payload):
        return {'repository': 'HYPJUDY/layoutlmv3-base-finetuned-publaynet',
                'revision': '1' * 40,
                'files': {'model_final.pth': {'bytes': len(payload),
                           'sha256': hashlib.sha256(payload).hexdigest()}}}

    def test_incomplete_corrupt_and_oversized_downloads_are_not_published(self):
        module = self.load()
        self.assertTrue(callable(getattr(module, 'download_model', None)))
        for payload in [b'abc', b'xxxxxx', b'abcdefg']:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with patch.object(module, 'urlopen', return_value=io.BytesIO(payload)):
                    with self.assertRaises(RuntimeError):
                        module.download_model(self.manifest(b'abcdef'), root)
                self.assertFalse((root / 'model_final.pth').exists())
                self.assertFalse((root / 'model_final.pth.part').exists())

    def test_download_error_does_not_expose_temporary_url(self):
        module = self.load()
        self.assertTrue(callable(getattr(module, 'download_model', None)))
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(module, 'urlopen', side_effect=OSError('https://example.org/?token=SECRET')):
                with self.assertRaises(RuntimeError) as caught:
                    module.download_model(self.manifest(b'abcdef'), Path(directory))
            self.assertNotIn('SECRET', str(caught.exception))
            self.assertTrue(caught.exception.__suppress_context__)

    def test_unsafe_names_and_unpinned_revisions_rejected_before_network(self):
        module = self.load()
        self.assertTrue(callable(getattr(module, 'download_model', None)))
        for name, revision in [('../outside', '1' * 40), ('..', '1' * 40), ('model_final.pth', 'main')]:
            with self.subTest(name=name, revision=revision), tempfile.TemporaryDirectory() as directory:
                manifest = self.manifest(b'x')
                manifest['files'][name] = manifest['files'].pop('model_final.pth')
                manifest['revision'] = revision
                with patch.object(module, 'urlopen', side_effect=AssertionError('Network must not be used')):
                    with self.assertRaises(ValueError):
                        module.download_model(manifest, Path(directory))


if __name__ == '__main__':
    unittest.main()
