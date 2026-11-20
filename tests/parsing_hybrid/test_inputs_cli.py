"""Input identity and CLI safety; no PDF/model inference or installation."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


class InputTests(unittest.TestCase):
    def test_multiple_pdfs_have_stable_unique_identity_and_counts(self):
        from parsing.unified.inputs import collect_papers
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            (root / 'b.pdf').write_bytes(b'%PDF-1.4\nb')
            (root / 'a.pdf').write_bytes(b'%PDF-1.4\na')
            papers = collect_papers([], root, page_counter=lambda path: 3 if path.name == 'a.pdf' else 1)
            self.assertEqual([Path(p['path']).name for p in papers], ['a.pdf', 'b.pdf'])
            self.assertEqual([p['page_count'] for p in papers], [3, 1])
            self.assertEqual(papers[0]['sha256'], hashlib.sha256(b'%PDF-1.4\na').hexdigest())
            self.assertNotEqual(papers[0]['id'], papers[1]['id'])
            self.assertEqual(papers, collect_papers([], root, page_counter=lambda path: 3 if path.name == 'a.pdf' else 1))

    def test_duplicate_content_is_rejected_even_with_different_names(self):
        from parsing.unified.inputs import collect_papers
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            for name in ('a.pdf', 'b.pdf'):
                (root / name).write_bytes(b'%PDF-1.4\nsame')
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                collect_papers([], root, page_counter=lambda path: 1)

    def test_invalid_or_empty_input_is_rejected(self):
        from parsing.unified.inputs import collect_papers
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                collect_papers([], root, page_counter=lambda path: 1)
            fake = root / 'fake.pdf'
            fake.write_bytes(b'not a PDF')
            with self.assertRaises(ValueError):
                collect_papers([fake], page_counter=lambda path: 1)
            fake.write_bytes(b'%PDF-1.4\nx')
            with self.assertRaises(ValueError):
                collect_papers([fake], page_counter=lambda path: 0)

    def test_changed_pdf_stops_render_before_creating_page(self):
        from parsing.unified.inputs import collect_papers, render_page_job
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            pdf = root / 'a.pdf'
            pdf.write_bytes(b'%PDF-1.4\na')
            paper = collect_papers([pdf], page_counter=lambda path: 1)[0]
            pdf.write_bytes(b'%PDF-1.4\nchanged')
            with self.assertRaisesRegex(ValueError, 'changed'):
                render_page_job(paper, 1, root / 'page')
            self.assertFalse((root / 'page').exists())

    def test_shared_render_preserves_source_and_execution_provenance(self):
        import numpy as np
        from parsing.unified.inputs import collect_papers, render_page_job, digest
        from parsing.adapters.layoutlmv3.inference.types import RenderedPage
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            pdf = root / 'original.pdf'
            pdf.write_bytes(b'%PDF-1.4\nsynthetic input')
            paper = collect_papers([pdf], page_counter=lambda path: 1)[0]
            paper['execution_id'] = 'fixture-attempt'
            rendered = RenderedPage(pdf, 1, 200, np.zeros((2, 2, 3), dtype=np.uint8),
                                    (0, 0, .72, .72), 0)
            with patch('parsing.adapters.layoutlmv3.inference.render.render_page', return_value=rendered):
                job = render_page_job(paper, 1, root / 'page')
            self.assertEqual(job['pdf_path'], str(pdf))
            self.assertEqual(job['identity']['execution_id'], 'fixture-attempt')
            self.assertEqual(job['identity']['render_sha256'], digest(job['render_path']))
            self.assertEqual(json.loads((root / 'page/identity.json').read_text()), job['identity'])


class CliTests(unittest.TestCase):
    def test_run_without_output_reaches_runtime_validation(self):
        from parsing.unified.cli import main
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch('sys.platform', 'linux'):
            with self.assertRaises(FileNotFoundError):
                main(['run', '--runtime', str(Path(folder) / 'missing.json'),
                      '--input-dir', folder, '--user-run'])

    def test_cli_rejects_output_outside_parse_results_before_reading_runtime(self):
        from parsing.unified.cli import main
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch('sys.platform', 'linux'):
            stderr = io.StringIO()
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(stderr):
                main(['run', '--runtime', str(Path(folder) / 'missing.json'),
                      '--output', str(Path(folder) / 'wrong-system'), '--user-run'])
            self.assertIn('parse_results', stderr.getvalue())

    def test_missing_mineru_config_rejected_during_configuration_validation(self):
        from parsing.unified.cli import read_runtime
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            for name in ('vendor', 'layoutlmv3', 'table_transformer', 'mineru'):
                (root / name).mkdir()
            for name in ('environment.json', 'receipt.json'):
                (root / name).write_text('{}')
            runtime = {'schema': 'parsing-hybrid-runtime/1', 'vendor_dir': 'vendor',
                       'env_manifest': 'environment.json', 'mineru_receipt': 'receipt.json',
                       'model_dirs': {name: name for name in ('layoutlmv3', 'table_transformer', 'mineru')}}
            path = root / 'runtime.json'
            path.write_text(json.dumps(runtime))
            with self.assertRaisesRegex(ValueError, 'mineru_config'):
                read_runtime(path)

    def test_template_does_not_overwrite_existing_configuration(self):
        from parsing.unified.cli import main
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            target = Path(folder) / 'runtime.json'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['template', '--output', str(target)]), 0)
            config = json.loads(target.read_text())
            self.assertEqual(set(config['model_dirs']), {'layoutlmv3', 'table_transformer', 'mineru'})
            self.assertEqual(Path(config['package_root']), ROOT / 'new_code/parse_system')
            self.assertTrue(Path(config['vendor_dir']).is_dir())
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                main(['template', '--output', str(target)])
            self.assertEqual(target.read_bytes(), original)

    def test_run_requires_explicit_user_flag_before_any_processing(self):
        from parsing.unified.cli import main
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            output = Path(folder) / 'attempt'
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                main(['run', '--runtime', str(Path(folder) / 'missing.json'),
                      '--input-dir', folder, '--output', str(output)])
            self.assertFalse(output.exists())

    def test_nonfinite_deadlines_are_rejected_before_runtime_access(self):
        from parsing.unified.cli import main
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            for value in ('nan', 'inf', '-inf'):
                with self.subTest(value=value), patch('sys.platform', 'linux'):
                    with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                        main(['run', '--runtime', str(Path(folder) / 'missing.json'),
                              '--output', str(Path(folder) / 'attempt'), '--user-run',
                              '--task-timeout=' + value])


if __name__ == '__main__':
    unittest.main()
