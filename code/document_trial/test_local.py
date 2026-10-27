import ast
import hashlib
import io
import runpy
from pathlib import Path
import tempfile
import types
import unittest
import zipfile
from unittest.mock import patch, Mock
from document_trial.local import derive, verify_inputs, GPU, execution_record, runtime
from document_trial.common import save, read
from document_trial.worker import render
from document_trial.local_download import download
from document_trial.local_install import verify_wheel, install
from document_trial.common import sha

BASE = Path(__file__).resolve().parents[1]/'packages/sic-parsing-v1/10'


class LocalPreparationTests(unittest.TestCase):
    def test_ready_or_started_runtime_cannot_be_reinstalled(self):
        for marker in ('ready.json', 'pilot-started.json'):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root/marker).write_text('{}')
                with patch('document_trial.local_install.run_logged') as command:
                    with self.assertRaises(ValueError):
                        install(root, root/'state')
                    command.assert_not_called()

    def test_preparation_and_run_share_exclusive_lock(self):
        import fcntl
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (root/'installation.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                for preparing in (True, False):
                    with self.assertRaises(BlockingIOError):
                        runtime(root, root, root/'output', preparing)
                self.assertFalse((root/'pilot-started.json').exists())

    def test_official_hash_cannot_substitute_a_different_frozen_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp)/'scipy.whl'
            with zipfile.ZipFile(wheel, 'w') as archive:
                archive.writestr('scipy-1.13.1.dist-info/METADATA', 'Name: scipy\nVersion: 1.13.1\n')
            receipt = {'package':'scipy', 'sha256':sha(wheel)}
            with self.assertRaisesRegex(ValueError, 'version differs'):
                verify_wheel(wheel, receipt, {'scipy':'1.10.1'})
            verify_wheel(wheel, receipt, {'scipy':'1.13.1'})

    def test_download_resumes_and_rejects_wrong_hash(self):
        class Response(io.BytesIO):
            status = 206
            def __init__(self, data, start):
                super().__init__(data)
                self.headers = {'Content-Range':'bytes '+str(start)+'-5/6'}
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'wheel.whl'
            target.with_suffix('.whl.part').write_bytes(b'abc')
            requests = []
            def opener(request, **kwargs):
                requests.append(request.get_header('Range'))
                return Response(b'def', 3)
            download('https://example.test/wheel', hashlib.sha256(b'abcdef').hexdigest(), target, opener)
            self.assertEqual(requests, ['bytes=3-'])
            self.assertEqual(target.read_bytes(), b'abcdef')
            with self.assertRaises(ValueError):
                download('https://example.test/wheel', '0'*64, target, opener)

    def test_failure_stops_following_models_and_archives_accounting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'runtime'
            inputs = derive(BASE, root)
            save(root/'ready.json', {'status':'prepared_without_inference'})
            for model in ('layoutlmv3', 'table_transformer'):
                save(inputs/model/'models.json', {'files':{}})
                (root/'preparation/models'/model).mkdir(parents=True)
            stages = []
            def command(args, state, **kwargs):
                stages.append(kwargs['stage'])
                self.assertIn('execution_id', read(state/'execution.json'))
                if kwargs['stage'] == 'layoutlmv3:infer':
                    raise RuntimeError('simulated OOM')
            output = Path(tmp)/'outputs'
            with patch('document_trial.local.verify_inputs'), patch('document_trial.local.verify_vendor'), \
                 patch('mineru_probe.remote_job.verify_receipt'), \
                 patch('document_trial.command_log.run_logged', side_effect=command):
                with self.assertRaisesRegex(RuntimeError, 'simulated OOM'):
                    runtime(root, Path(tmp), output, False)
            self.assertEqual(stages, ['layoutlmv3:probe', 'table_transformer:probe',
                                     'mineru:probe', 'layoutlmv3:render', 'layoutlmv3:infer'])
            state = next(p for p in output.iterdir() if p.is_dir())
            self.assertEqual(read(state/'execution-status.json')['status'], 'failed')
            self.assertEqual(len(list((state/'pages').glob('*/*/status.json'))), 27)
            self.assertTrue(state.with_suffix('.zip').is_file())
            self.assertTrue(state.with_suffix('.sha256').is_file())

    def test_worker_render_accepts_local_execution_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'runtime'
            inputs = derive(BASE, root)
            state = Path(tmp)/'run'
            record = execution_record(root, 'a'*32)
            save(state/'execution.json', record)
            rendered = types.SimpleNamespace(image=None, width_px=100, height_px=200)
            render_module = types.ModuleType('inference.render')
            render_module.render_page = Mock(return_value=rendered)
            outputs = types.ModuleType('inference.outputs')
            outputs.render_geometry = Mock(return_value={})
            pil = types.ModuleType('PIL')
            image = Mock()
            image.save.side_effect = lambda path, **kw: path.write_bytes(b'fake-render')
            pil.Image = Mock()
            pil.Image.fromarray.return_value = image
            with patch.dict('sys.modules', {'inference':types.ModuleType('inference'),
                    'inference.render':render_module, 'inference.outputs':outputs, 'PIL':pil}):
                render(inputs, state)
            identities = list((state/'pages').glob('*/identity.json'))
            self.assertEqual(len(identities), read(inputs/'plan.json')['page_count'])
            for identity in identities:
                self.assertEqual(read(identity)['execution_id'], record['execution_id'])

    def test_derived_installer_cannot_render_or_infer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'local'
            inputs = derive(BASE, root)
            tree = ast.parse((inputs/'document_trial/remote.py').read_text())
            setup = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'setup')
            self.assertIsInstance(setup.body[-1], ast.Return)
            text = ast.unparse(tree)
            for forbidden in ('def work(', "'infer'", "'render'", 'def main('):
                self.assertNotIn(forbidden, text)
            self.assertIn(GPU, (inputs/'document_trial/common.py').read_text())
            self.assertIn(GPU, (inputs/'mineru_probe/run_image.py').read_text())
            self.assertIn('LOCAL_WSL_RTX3050', (inputs/'document_trial/worker.py').read_text())
            checker = runpy.run_path(str(inputs/'document_trial/common.py'))['check_runtime']
            spec = read(inputs/'plan.json')['models']['layoutlmv3']
            observed = dict(python=spec['python'], cuda=spec['cuda'], packages=spec['packages'], gpu=GPU)
            checker(observed, spec)
            with self.assertRaises(ValueError):
                checker(dict(observed, gpu='Tesla T4'), spec)
            with self.assertRaises(ValueError):
                checker(dict(observed, packages={}), spec)
            verify_inputs(root)
            with self.assertRaises(FileExistsError):
                derive(BASE, root)
            (inputs/'document.pdf').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                verify_inputs(root)


if __name__ == '__main__':
    unittest.main()
