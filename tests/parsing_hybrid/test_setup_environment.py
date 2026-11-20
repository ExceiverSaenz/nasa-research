"""Offline checks for the root installer; never install packages or call GPUs."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import io
from contextlib import redirect_stdout
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'new_code/setup_environment.py'


class SetupTests(unittest.TestCase):
    def load(self):
        spec = importlib.util.spec_from_file_location('setup_environment', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_bootstrap_uses_ubuntu_interpreter_not_colab_default(self):
        module = self.load()
        for ubuntu, expected in [('24.04', '/usr/bin/python3.12'), ('22.04', '/usr/bin/python3.10')]:
            with self.subTest(ubuntu=ubuntu):
                commands = []
                class Recorder:
                    def run(self, argv, **kwargs):
                        commands.append(list(map(str, argv)))
                module.create_bootstrap(Path('/tmp/setup-attempt'), Recorder(), ubuntu)
                self.assertEqual(commands[0][0], str(Path(expected)))
                self.assertEqual(commands[1][:3], [str(Path(expected)), '-m', 'venv'])
                self.assertIn('ensurepip', commands[0][-1])

    def test_bootstrap_rejects_unsupported_ubuntu(self):
        module = self.load()
        with self.assertRaises(ValueError):
            module.bootstrap_interpreter('26.04')

    def test_plan_is_inert_and_reports_pinned_environment(self):
        self.assertTrue(SCRIPT.is_file(), 'Root environment installer is missing')
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            target = Path(temp) / 'not-created'
            result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--plan',
                                     '--destination', str(target)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data['python'], '3.11.16')
            self.assertEqual(data['cuda_toolkit'], '12.6')
            self.assertFalse(data['installs_driver'])
            self.assertFalse(data['runs_inference'])
            self.assertFalse(target.exists())

    def test_rejects_existing_environment_instead_of_overwriting(self):
        module = self.load()
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            with self.assertRaisesRegex(ValueError, 'exists'):
                module.validate_destination(Path(temp), ROOT)

    def test_rejects_destination_outside_new_code(self):
        module = self.load()
        with self.assertRaisesRegex(ValueError, 'inside'):
            module.validate_destination(ROOT / 'outside-environment', ROOT / 'new_code')

    def test_rejects_setup_and_cache_destinations_before_installation(self):
        module = self.load()
        for suffix in ('runtime', 'runtime/python', 'runtime/setup-attempt', 'parse_system/env'):
            with self.subTest(suffix=suffix):
                with self.assertRaises(ValueError):
                    module.validate_destination(ROOT / 'new_code' / suffix)

    def test_runtime_apt_uses_existing_official_ubuntu_sources_only(self):
        module=self.load()
        for ubuntu,source in (('24.04','/etc/apt/sources.list.d/ubuntu.sources'),('22.04','/etc/apt/sources.list')):
            options=module.ubuntu_apt_options(ubuntu)
            self.assertIn('Dir::Etc::sourcelist='+source,options)
            self.assertIn('Dir::Etc::sourceparts=-',options)
            self.assertFalse(any('AllowInsecure' in x or 'Trusted' in x for x in options))

    def test_apt_transaction_rejects_driver_install_or_removal(self):
        module = self.load()
        for transaction in ('Inst nvidia-driver-560 (560 repo)',
                            'Inst cuda-drivers (560 repo)',
                            'Remv libc6 [2.35]'):
            with self.subTest(transaction=transaction):
                with self.assertRaises(RuntimeError):
                    module.validate_apt_transaction(transaction)
        module.validate_apt_transaction('Inst cuda-nvcc-12-6 (12.6 repo)')

    def test_silent_process_has_heartbeat_and_nested_log_is_streamed(self):
        module = self.load()
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            temp = Path(temp)
            nested = temp / 'install.log'
            code = ('import time;from pathlib import Path;'
                    'time.sleep(.2);Path(' + repr(str(nested)) + ').write_text("building extension\\n");'
                    'time.sleep(.2);print("finished",flush=True)')
            output = io.StringIO()
            runner = module.Runner(temp / 'setup.log', dict(__import__('os').environ), heartbeat=.05)
            with redirect_stdout(output):
                result = runner.run([sys.executable, '-u', '-c', code], watch_log=nested)
            self.assertIn('building extension', output.getvalue())
            self.assertIn('Still running', output.getvalue())
            self.assertIn('finished', result)
            self.assertIn('building extension', (temp / 'setup.log').read_text())

    def test_child_failure_is_not_reported_as_success(self):
        module = self.load()
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            runner = module.Runner(Path(temp) / 'setup.log', dict(__import__('os').environ))
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(subprocess.CalledProcessError):
                    runner.run([sys.executable, '-c', 'raise SystemExit(7)'])

    def test_heartbeat_continues_after_child_closes_stdout(self):
        module = self.load()
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            output = io.StringIO()
            runner = module.Runner(Path(temp) / 'setup.log', dict(__import__('os').environ), heartbeat=.05)
            with redirect_stdout(output):
                runner.run([sys.executable, '-u', '-c',
                            'import os,time;os.close(1);os.close(2);time.sleep(.3)'])
            self.assertIn('Still running', output.getvalue())

    def test_reuse_skips_toolkit_and_routes_to_frozen_installer(self):
        module=self.load()
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            root=Path(temp);python=root/'managed-python';python.touch()
            commands=[]
            class Recorder:
                env={}
                def run(self,argv,**kwargs):
                    command=list(map(str,argv));commands.append(command)
                    if 'find' in command:return str(python)
                    return ''
            with patch.object(module,'ROOT',root), \
                 patch.object(module.os,'geteuid',return_value=0,create=True), \
                 patch.object(module,'create_bootstrap',return_value=root/'bootstrap'):
                module.install(root/'runtime/new',root/'attempt',Recorder(),'24.04',root/'bundle')
            self.assertFalse(any('nvcc' in ' '.join(cmd) or 'cuda-toolkit' in ' '.join(cmd) for cmd in commands))
            reuse=[cmd for cmd in commands if 'reuse' in cmd]
            self.assertEqual(len(reuse),1)
            self.assertIn('--bundle',reuse[0])
            self.assertFalse(any('prepare' in cmd for cmd in commands))


if __name__ == '__main__':
    unittest.main()
