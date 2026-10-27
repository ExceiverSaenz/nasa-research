"""Contract tests with synthetic sources; never process the canonical collection."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

DEMO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(DEMO), str(DEMO / ('src' if (DEMO / 'src').is_dir() else 'code'))]

from integration_demo.common import digest, write_json, extract_bundle, make_archive, verify_archive
from integration_demo.reconcile_collection import export_collection
from integration_demo.runner import execute_stage


def fixture(root):
    import fitz
    from PIL import Image
    from reconciliation.consolidated_inputs import VERSION

    pdf = root / 'pdfs' / '1.pdf'
    pdf.parent.mkdir()
    d = fitz.open()
    for n in (1, 2):
        p = d.new_page(width=1000, height=1000)
        p.insert_text((100, 120), '1. Introduction' if n == 1 else 'Scientific content.')
    d.save(pdf)
    d.close()
    key = digest(pdf)
    source = root / 'prepared' / 'sources' / 'native.json'
    write_json(source, {'fixture': True})
    image = source.with_suffix('.png')
    Image.new('RGB', (1000, 1000), 'white').save(image)
    def record(id, kind, bbox, parent=None, role='segment'):
        return dict(id=id, parser='mineru', native_type=kind, bbox=bbox,
                    parent=parent, role=role, native={'type': kind}, text='Scientific content.',
                    source=dict(path=str(source), sha256=digest(source), pointer='/fixture'),
                    transform=[1, 0, 0, 1, 0, 0])
    rows = [
        [record('p1-text', 'text', [90, 90, 450, 200])],
        [record('p2-parent', 'index', [100, 100, 450, 600], role='container'),
         record('p2-child', 'text', None, parent='p2-parent')]
    ]
    pages = [dict(adapter='canonical-v1', identity=dict(document_sha256=key,
                  physical_page=n, width_px=1000, height_px=1000, render_sha256=digest(image)),
                  parsers={p: 'completed' for p in ('mineru', 'layoutlmv3', 'table_transformer')},
                  records=records, incidents=[], render_path=str(image), missing_sources=[])
             for n, records in enumerate(rows, 1)]
    data = dict(adapter=VERSION, pages=pages, parser_configuration={},
                source_inputs={str(source): digest(source), str(image): digest(image)})
    prepared = root / 'prepared'
    inp = prepared / 'documents' / key / 'input.json'
    write_json(inp, data)
    write_json(prepared / 'adaptation-manifest.json', dict(adapter=VERSION,
               documents=[dict(document='SiC_papers/1.pdf', document_sha256=key, pages=2)],
               outputs={inp.relative_to(prepared).as_posix(): digest(inp)}))
    return prepared, pdf, data


class DemoTests(unittest.TestCase):
    def test_runtime_setup_uses_managed_python_exact_locks_and_no_retry(self):
        from integration_demo.runtime import installation_commands
        commands, env, python = installation_commands(Path('/work/runtime'), Path('/payload'))
        text = json.dumps(commands)
        self.assertIn('uv==0.12.21', text)
        self.assertIn('3.13.5', text)
        self.assertIn('--managed-python', text)
        self.assertIn('--no-deps', text)
        self.assertIn('requirements-runtime.lock', text)
        self.assertIn('requirements-docling.txt', text)
        self.assertEqual(env['UV_HTTP_RETRIES'], '0')
        self.assertEqual(str(python).replace('\\', '/'), '/work/runtime/venv/bin/python')

    def test_bundle_verifies_all_members_before_extracting(self):
        with tempfile.TemporaryDirectory(dir=DEMO) as t:
            root = Path(t)
            raw = b'original'
            manifest = dict(schema='integration-demo-bundle/1', files={
                'code/ok.py': dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())})
            for name, content in [('valid', raw), ('corrupt', b'changed')]:
                archive = root / (name + '.zip')
                with zipfile.ZipFile(archive, 'x') as z:
                    z.writestr('bundle-manifest.json', json.dumps(manifest))
                    z.writestr('code/ok.py', content)
                if name == 'valid':
                    extract_bundle(archive, root / name, digest(archive))
                    self.assertEqual((root / name / 'code/ok.py').read_bytes(), raw)
                else:
                    with self.assertRaises(ValueError):
                        extract_bundle(archive, root / name, digest(archive))
                    self.assertFalse((root / name).exists())

    def test_unsafe_duplicate_and_symlink_members_rejected(self):
        with tempfile.TemporaryDirectory(dir=DEMO) as t:
            root = Path(t)
            for i, name in enumerate(['../escape', '/absolute', 'C:/windows', 'code\\bad', 'x/../y']):
                archive = root / f'{i}.zip'
                with zipfile.ZipFile(archive, 'x') as z:
                    z.writestr('bundle-manifest.json', json.dumps(dict(schema='integration-demo-bundle/1', files={})))
                    z.writestr(name, b'bad')
                with self.assertRaises(ValueError):
                    extract_bundle(archive, root / f'out{i}', digest(archive))
                self.assertFalse((root / f'out{i}').exists())
            for mode in ('duplicate', 'symlink'):
                archive = root / (mode + '.zip')
                with zipfile.ZipFile(archive, 'x') as z:
                    z.writestr('bundle-manifest.json', json.dumps(dict(schema='integration-demo-bundle/1', files={})))
                    if mode == 'duplicate':
                        z.writestr('Code/a.py', b'a')
                        z.writestr('code/a.py', b'b')
                    else:
                        info = zipfile.ZipInfo('link')
                        info.create_system = 3
                        info.external_attr = 0o120777 << 16
                        z.writestr(info, b'outside')
                with self.assertRaises(ValueError):
                    extract_bundle(archive, root / mode, digest(archive))

    def test_reconciliation_to_real_classification_and_operational_export(self):
        from functional_classification.export_reconciled import export_collection as classify
        from reading_order.export import export_collection as capsules
        from document_pipeline.pipeline import export_collection as integrate
        with tempfile.TemporaryDirectory(dir=DEMO) as t:
            root = Path(t).resolve()
            prepared, pdf, data = fixture(root)
            before = copy.deepcopy(data)
            report = export_collection(prepared, root / 'pdfs', root / 'rec')
            self.assertEqual(report['physical_pages'], 2)
            self.assertEqual(data, before)
            rec = json.loads((root / 'rec/papers/1/document.json').read_text(encoding='utf-8'))
            self.assertEqual(rec['document'], str(pdf))
            self.assertIn('invalid_geometry', rec['pages'][1]['incidents'])
            self.assertFalse(rec['pages'][1]['groups'])
            self.assertIsNone(next(r for r in rec['pages'][1]['records'] if r['id'] == 'p2-child')['bbox'])
            classify(root / 'rec', root / 'classified')
            capsules(root / 'classified', root / 'capsules')
            # Real pinned Docling geometry and native PDF extraction, synthetic PDFs only.
            result = integrate(root / 'capsules', root / 'operational')
            self.assertEqual(result['papers'], 1)
            self.assertEqual(result['deferred_children'], 1)
            self.assertEqual(result['abstained_pages'], 1)
            self.assertIsNone(result['semantic_accuracy'])
            self.assertTrue((root / 'operational/index.html').is_file())
            self.assertEqual((root / 'operational/papers/1/view/images/0001.png').read_bytes(),
                             (prepared / 'sources/native.png').read_bytes())
            with self.assertRaises(FileExistsError):
                export_collection(prepared, root / 'pdfs', root / 'rec')

    def test_frozen_runtime_probe_with_real_docling(self):
        from integration_demo.runtime import probe
        with tempfile.TemporaryDirectory(dir=DEMO) as t:
            receipt = Path(t) / 'probe.json'
            result = probe(DEMO, receipt)
            self.assertEqual(result['geometric_probe'], 'passed')
            self.assertFalse(result['neural_modules_imported'])

    def test_subprocess_controller_verifies_and_archives_full_synthetic_run(self):
        with tempfile.TemporaryDirectory(dir=DEMO) as t:
            state = Path(t).resolve() / 'run'
            state.mkdir()
            fixture(state)
            shutil.copytree(DEMO / 'src', state / 'source-code')
            shutil.copytree(DEMO / 'integration_demo', state / 'source-code/integration_demo',
                            ignore=shutil.ignore_patterns('__pycache__'))
            expected = dict(papers=1, pages=2, inventory_units=3, content_appearances=1,
                            deferred_children=1, abstained_pages=1, parser_records=3)
            write_json(state / 'package-spec.json', dict(expected=expected))
            write_json(state / 'execution-profile.json', dict(input_payload=str(state), expected=expected))
            files = {}
            for p in (state / 'source-code').rglob('*'):
                if p.is_file():
                    files['code/' + p.relative_to(state / 'source-code').as_posix()] = dict(sha256=digest(p))
            files['pdfs/1.pdf'] = dict(sha256=digest(state / 'pdfs/1.pdf'))
            write_json(state / 'bundle-manifest.json', dict(files=files))
            write_json(state / 'status.json', dict(status='prepared'))
            write_json(state / 'stages/setup.json', dict(status='completed'))
            write_json(state / 'runtime-probe.json', dict(geometric_probe='passed'))
            write_json(state / 'stages/prepare.json', dict(status='completed'))
            env = dict(os.environ, PYTHONPATH=str(state / 'source-code'), PYTHONIOENCODING='utf-8')
            script = "import sys; from integration_demo.runner import main; "
            script += "\nfor stage in ('reconcile','classify','capsules','integrate','verify'):\n"
            script += " sys.argv=['runner',stage,sys.argv[-1]]; main()\n"
            result = subprocess.run([sys.executable, '-B', '-c', script, str(state)], env=env,
                                    capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads((state / 'status.json').read_text())['status'], 'completed')
            make_archive(state, Path(t) / 'result.zip')
            self.assertEqual(verify_archive(Path(t) / 'result.zip', Path(t) / 'result.sha256')['status'], 'completed')

    def test_pdf_mismatch_and_source_corruption_rejected(self):
        for corruption in ('pdf', 'source'):
            with tempfile.TemporaryDirectory(dir=DEMO) as t:
                root = Path(t).resolve()
                prepared, pdf, data = fixture(root)
                target = pdf if corruption == 'pdf' else prepared / 'sources/native.json'
                target.write_bytes(b'corrupted')
                with self.assertRaises(ValueError):
                    export_collection(prepared, root / 'pdfs', root / 'rec')

    def test_failed_stage_preserved_and_never_retried(self):
        with tempfile.TemporaryDirectory(dir=DEMO) as t:
            root = Path(t)
            def broken():
                (root / 'partial.txt').write_text('kept')
                raise RuntimeError('fixture failure')
            with self.assertRaises(RuntimeError):
                execute_stage(root, 'prepare', broken)
            status = json.loads((root / 'stages/prepare.json').read_text())
            self.assertEqual(status['status'], 'failed')
            self.assertIn('fixture failure', status['error'])
            self.assertTrue((root / 'partial.txt').exists())
            with self.assertRaises(FileExistsError):
                execute_stage(root, 'prepare', lambda: None)

    def test_backup_contains_sources_and_detects_changed_sidecar(self):
        with tempfile.TemporaryDirectory(dir=DEMO) as t:
            root = Path(t)
            state = root / 'run'
            write_json(state / 'status.json', dict(status='failed'))
            write_json(state / 'prepared/sources/native.json', dict(original=True))
            archive = root / 'result.zip'
            make_archive(state, archive)
            info = verify_archive(archive, archive.with_suffix('.sha256'))
            self.assertEqual(info['status'], 'failed')
            with zipfile.ZipFile(archive) as z:
                self.assertIn('prepared/sources/native.json', z.namelist())
            archive.with_suffix('.sha256').write_text('0' * 64)
            with self.assertRaises(ValueError):
                verify_archive(archive, archive.with_suffix('.sha256'))


if __name__ == '__main__':
    unittest.main()

