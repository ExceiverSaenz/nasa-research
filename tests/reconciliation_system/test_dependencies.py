import contextlib
import json
import pathlib
import tempfile
import types
import unittest
from unittest.mock import patch

from integration import dependencies


class DependencyTests(unittest.TestCase):
    def fake_runtime(self, root):
        source = root / 'site-packages' / 'docling' / 'reading_order_rb.py'
        source.parent.mkdir(parents=True)
        source.write_text('fixture rule-based module', encoding='utf-8')
        fitz = root / 'site-packages' / 'fitz' / '__init__.py'
        fitz.parent.mkdir()
        fitz.write_text('fixture native module', encoding='utf-8')
        rb = types.ModuleType('docling.models.postprocessing.reading_order_rb')
        rb.__file__ = str(source)
        native = types.ModuleType('fitz')
        native.__file__ = str(fitz)
        native.VersionBind = dependencies.PINS['PyMuPDF']
        modules = {'fitz': native, rb.__name__: rb}
        return source, modules

    def runtime_patches(self, root, source, modules):
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(dependencies.platform, 'python_version', return_value=dependencies.SHARED_PYTHON))
        stack.enter_context(patch.object(dependencies.sys, 'prefix', str(root)))
        stack.enter_context(patch.object(dependencies.sys, 'base_prefix', str(root.parent / 'base-python')))
        stack.enter_context(patch.object(dependencies, 'version', side_effect=lambda name: dependencies.PINS[name]))
        stack.enter_context(patch.object(dependencies.importlib, 'import_module', side_effect=modules.__getitem__))
        stack.enter_context(patch.object(dependencies, 'DOCLING_RB_SHA256', dependencies.digest(source)))
        stack.enter_context(patch.object(dependencies, 'validate_shared_receipt', return_value={'manifest_path': 'fixture-receipt', 'manifest_sha256': 'a'*64}))
        return stack

    def test_shared_runtime_reports_versions_source_and_same_interpreter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source, modules = self.fake_runtime(root)
            with self.runtime_patches(root, source, modules):
                report = dependencies.preflight()
            self.assertEqual(report['packages'], dependencies.PINS)
            self.assertEqual(report['profile'], 'shared')
            self.assertEqual(report['docling_rb_sha256'], dependencies.digest(source))
            self.assertFalse(report['models_executed'])

    def test_wrong_python_fails_before_imports(self):
        with patch.object(dependencies.platform, 'python_version', return_value='3.13.5'), patch.object(dependencies.importlib, 'import_module') as load:
            with self.assertRaisesRegex(ValueError, '3.11.16'):
                dependencies.preflight()
            load.assert_not_called()


    def test_missing_or_changed_dependency_is_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source, modules = self.fake_runtime(root)
            with self.runtime_patches(root, source, modules):
                with patch.object(dependencies, 'version', return_value='unexpected'):
                    with self.assertRaisesRegex(ValueError, 'package version'):
                        dependencies.preflight()
                with patch.object(dependencies, 'version', side_effect=dependencies.PackageNotFoundError('PyMuPDF')):
                    with self.assertRaisesRegex(ValueError, 'Missing integration dependency'):
                        dependencies.preflight()

    def test_altered_rule_source_and_external_native_module_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / 'venv'
            source, modules = self.fake_runtime(root)
            with self.runtime_patches(root, source, modules):
                with patch.object(dependencies, 'DOCLING_RB_SHA256', '0' * 64):
                    with self.assertRaisesRegex(ValueError, 'source hash'):
                        dependencies.preflight()
                outside = root.parent / 'outside.py'
                outside.write_text('external module', encoding='utf-8')
                modules['fitz'].__file__ = str(outside)
                with self.assertRaisesRegex(ValueError, 'outside shared'):
                    dependencies.preflight()


class SharedReceiptTests(unittest.TestCase):
    def receipt(self, root):
        prefix = root/'environment'/'.venv'
        package = prefix/'site-packages'/'package.py'
        package.parent.mkdir(parents=True)
        package.write_bytes(b'actual package file')
        lock = prefix.parent/'requirements.lock'
        lock.write_bytes(b'fixture==1.2.3\n')
        executable = prefix/'bin'/'python'
        imports = {name: {'path': str(package), 'sha256': dependencies.digest(package)}
                   for name in ('torch','torchvision','transformers','mineru','detectron2','detectron2._C')}
        value = dict(status='imports-validated', prefix=str(prefix.resolve()), executable=str(executable.absolute()),
                     python=dependencies.SHARED_PYTHON, versions={'fixture': '1.2.3'}, imports=imports,
                     artifacts={'requirements.lock': {'bytes': lock.stat().st_size, 'sha256': dependencies.digest(lock)}})
        manifest = prefix.parent/'environment.json'
        manifest.write_text(json.dumps(value),encoding='utf-8')
        return prefix, executable, manifest, package, lock, value

    def patches(self, prefix, executable):
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(dependencies.sys, 'prefix', str(prefix)))
        stack.enter_context(patch.object(dependencies.sys, 'executable', str(executable)))
        stack.enter_context(patch.object(dependencies.platform, 'python_version', return_value=dependencies.SHARED_PYTHON))
        distribution = types.SimpleNamespace(metadata={'Name': 'fixture'}, version='1.2.3')
        stack.enter_context(patch.object(dependencies.metadata, 'distributions', return_value=[distribution]))
        return stack

    def test_actual_receipt_files_and_default_location_are_verified_without_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix, executable, manifest, package, lock, value = self.receipt(pathlib.Path(directory))
            with self.patches(prefix, executable), patch.object(dependencies.importlib, 'import_module') as imports:
                result = dependencies.validate_shared_receipt()
                self.assertEqual(result['manifest_sha256'], dependencies.digest(manifest))
                imports.assert_not_called()

    def test_wrong_prefix_versions_and_changed_artifacts_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix, executable, manifest, package, lock, value = self.receipt(pathlib.Path(directory))
            with self.patches(prefix, executable):
                for change, expected in (({'prefix': str(prefix.parent)}, 'prefix/executable'),
                                         ({'versions': {'fixture': 'old'}}, 'package fingerprint'),
                                         ({'imports': {}}, 'lacks parser imports')):
                    with self.subTest(change=change), self.assertRaisesRegex(ValueError, expected):
                        manifest.write_text(json.dumps(dict(value, **change)),encoding='utf-8')
                        dependencies.validate_shared_receipt(manifest)
                manifest.write_text(json.dumps(value),encoding='utf-8')
                lock.write_bytes(b'changed lock')
                with self.assertRaisesRegex(ValueError, 'artifact changed'):
                    dependencies.validate_shared_receipt(manifest)

    def test_changed_import_or_outside_artifact_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix, executable, manifest, package, lock, value = self.receipt(pathlib.Path(directory))
            with self.patches(prefix, executable):
                package.write_bytes(b'modified package')
                with self.assertRaisesRegex(ValueError, 'package import changed'):
                    dependencies.validate_shared_receipt(manifest)
                package.write_bytes(b'actual package file')
                outside = prefix.parent.parent/'outside.lock'
                outside.write_bytes(b'external')
                value['artifacts'] = {'../outside.lock': {'bytes': outside.stat().st_size, 'sha256': dependencies.digest(outside)}}
                manifest.write_text(json.dumps(value),encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'outside receipt'):
                    dependencies.validate_shared_receipt(manifest)


if __name__ == '__main__':
    unittest.main()
