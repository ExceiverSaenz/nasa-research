"""Transfer package integrity tests; no Colab, network or package installation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


class PageTransferTests(unittest.TestCase):
    def load(self, name):
        path = Path(__file__).with_name(name + '.py')
        self.assertTrue(path.exists(), 'Page transfer helper missing')
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_package_has_only_selected_pdf_modules_and_requirements(self):
        builder = self.load('prepare_page')
        remote = self.load('page_remote')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / 'page.zip'
            builder.prepare_bundle(bundle)
            self.assertEqual(hashlib.sha256(bundle.read_bytes()).hexdigest(),
                             bundle.with_suffix('.sha256').read_text().strip())
            remote.unpack_bundle(bundle, bundle.with_suffix('.sha256'), root / 'unpacked')
            with zipfile.ZipFile(bundle) as zipped:
                self.assertEqual(set(zipped.namelist()), {
                    'manifest.json', 'SiC-12.pdf', 'requirements-page.txt',
                    'inference/__init__.py', 'inference/types.py', 'inference/render.py',
                    'inference/detector.py', 'inference/outputs.py', 'inference/run_page.py'})
            manifest = json.loads((root / 'unpacked/manifest.json').read_text())
            self.assertEqual(manifest['page'], 3)
            self.assertEqual(manifest['files']['SiC-12.pdf']['sha256'],
                             '9cea2fa5ad94c6a31031c72a9c3f698d571c85c810af644304c3b9f0d306f660')

    def test_corrupt_bundle_rejected_before_extraction(self):
        remote = self.load('page_remote')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / 'bad.zip'
            bundle.write_bytes(b'corrupt')
            sidecar = root / 'bad.sha256'
            sidecar.write_text('0' * 64)
            with self.assertRaises(ValueError):
                remote.unpack_bundle(bundle, sidecar, root / 'unpacked')
            self.assertFalse((root / 'unpacked').exists())


if __name__ == '__main__':
    unittest.main()
