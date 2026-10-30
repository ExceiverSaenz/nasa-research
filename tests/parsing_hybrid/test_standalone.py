"""Test a relocated distribution with isolated Python and no code/history nearby."""
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class StandaloneTests(unittest.TestCase):
    def detached(self, temp):
        package = Path(temp) / 'portable'
        shutil.copytree(ROOT / 'new_code/parse_system', package,
                        ignore=shutil.ignore_patterns('models', 'resources', 'tests', '__pycache__'))
        self.assertFalse((package.parent / 'code').exists())
        self.assertFalse((package.parent / 'history').exists())
        return package

    def call(self, package, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        env.pop('PYTHONPATH', None)
        return subprocess.run([sys.executable, '-I', '-B', str(package / 'run.py'), *args],
                              cwd=package.parent, env=env, capture_output=True, text=True, timeout=30)

    def test_detached_launcher_help_has_no_project_dependency(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            package = self.detached(temp)
            result = self.call(package, '--help')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('environment', result.stdout)
            self.assertIn('run', result.stdout)

    def test_detached_template_keeps_vendor_local_and_external_weights_explicit(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            package = self.detached(temp)
            target = package / 'runtime.json'
            result = self.call(package, 'template', '--output', str(target))
            self.assertEqual(result.returncode, 0, result.stderr)
            runtime = json.loads(target.read_text())
            self.assertEqual(Path(runtime['vendor_dir']), package / 'vendor/unilm')
            self.assertEqual(runtime['model_dirs']['layoutlmv3'], '/ABSOLUTE/PATH/TO/layoutlmv3/model')
            self.assertFalse((package / 'models').exists())
            self.assertTrue(Path(runtime['vendor_dir']).is_dir())

    def test_detached_install_entry_help_does_not_install(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            package = self.detached(temp)
            result = self.call(package, 'environment', 'prepare', '--help')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('--destination', result.stdout)

    def test_detached_core_imports_are_inert_without_project_helpers(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            package = self.detached(temp)
            script = ("import sys,importlib;sys.path.insert(0," + repr(str(package)) + ");"
                      "mods=['cli','inputs','scheduler','environment','compatibility','adapters'];"
                      "[importlib.import_module('parsing.unified.'+m) for m in mods];"
                      "assert 'compatibility' not in sys.modules;"
                      "assert 'notebook_support' not in sys.modules;print('portable imports OK')")
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script], cwd=package.parent,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('portable imports OK', result.stdout)

    def test_detached_output_root_is_resolved_from_package_not_working_directory(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            package = self.detached(temp)
            script = ("import sys;sys.path.insert(0," + repr(str(package)) + ");"
                      "from parsing.unified.storage import results_root;print(results_root())")
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script], cwd=ROOT,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Path(result.stdout.strip()), package.parent / 'results/parse_results')

    def test_runtime_imports_cannot_reach_legacy_packages(self):
        forbidden = {'compatibility', 'notebook_support', 'document_trial', 'integration',
                     'parsing.execution', 'parsing.notebook', 'parsing.tests'}
        paths = list((ROOT / 'new_code/parse_system/parsing').rglob('*.py'))
        self.assertGreater(len(paths), 0)
        for path in paths:
            if any(name in path.parts for name in ('execution', 'tests')) or path.name == 'notebook.py':
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [n.name for n in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module or '']
                else:
                    continue
                for name in names:
                    self.assertFalse(any(name == bad or name.startswith(bad + '.') for bad in forbidden),
                                     f'{path}: legacy import {name}')

    def test_detached_spawn_uses_only_copied_package_and_test_fixture(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            package = self.detached(temp)
            shutil.copyfile(ROOT / 'tests/parsing_hybrid/fixtures.py', package / 'probe_engine.py')
            probe = package / 'spawn_probe.py'
            probe.write_text(
                "from pathlib import Path\nimport sys,json\n"
                "sys.path.insert(0,str(Path(__file__).resolve().parent))\n"
                "from parsing.unified.scheduler import run_pipeline\n"
                "from probe_engine import factory,render\n"
                "if __name__=='__main__':\n"
                "    papers=[dict(id=str(i),path='fixture.pdf',sha256=str(i),page_count=1) for i in range(20)]\n"
                "    result=run_pipeline(papers,Path(__file__).parent/'out',{},renderer=render,engine_factory=factory,load_timeout=30)\n"
                "    print(json.dumps(dict(status=result['status'],workers=len(result['workers']),pages=result['metrics']['completed_pages'],error=result['error'])))\n",
                encoding='utf-8')
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            env.pop('PYTHONPATH', None)
            result = subprocess.run([sys.executable, '-I', '-B', str(probe)], cwd=package.parent,
                                    env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary['status'], 'completed', summary['error'])
            self.assertEqual(summary, {'status': 'completed', 'workers': 3, 'pages': 20, 'error': None})


if __name__ == '__main__':
    unittest.main()
