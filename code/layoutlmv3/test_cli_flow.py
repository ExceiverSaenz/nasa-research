import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecoveryTests(unittest.TestCase):
    def test_failed_setup_still_archives_log_and_failure_status(self):
        job = load('cli_job')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            setup = root / 'fail.py'
            setup.write_text("print('diagnostico de instalacion', flush=True)\nraise SystemExit(7)\n")
            state = root / 'state'
            archive = root / 'recovery.zip'
            self.assertEqual(job.run_job(setup, state, archive), 7)
            with zipfile.ZipFile(archive) as zipped:
                self.assertIn(b'diagnostico de instalacion', zipped.read('setup-console.log'))
                self.assertIn(b'"returncode": 7', zipped.read('job-status.json'))
            self.assertEqual(archive.with_suffix('.sha256').read_text().split()[0],
                             hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_corrupted_download_is_rejected(self):
        verifier = load('verify_download')
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'result.zip'
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr('job-status.json', '{"returncode": 0}')
            archive.with_suffix('.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest())
            archive.write_bytes(archive.read_bytes() + b'corruption')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                verifier.verify(archive)

    def test_good_archive_with_failed_job_is_not_reported_as_success(self):
        verifier = load('verify_download')
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'result.zip'
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr('job-status.json', '{"returncode": 7}')
            archive.with_suffix('.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest())
            with self.assertRaisesRegex(RuntimeError, '7'):
                verifier.verify(archive)


if __name__ == '__main__':
    unittest.main()
