"""Offline regressions for setup diagnostics and command routing."""
import io
import json
from contextlib import redirect_stderr
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from parsing.unified import environment as env


class AuditTests(unittest.TestCase):
    def test_cuda_accepts_detectron2_format_but_rejects_other_backends(self):
        for value in ('CUDA 12.6', '12.6', 12060):
            env.validate_cuda_build(value)
        for value in ('CUDA 12.8', 'HIP 12.6', 'not available', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                env.validate_cuda_build(value)

    def test_probe_failure_exposes_both_diagnostic_streams(self):
        failure=subprocess.CalledProcessError(1,['probe'],output='import message',stderr='root cause')
        output=io.StringIO()
        with patch.object(env.subprocess,'check_output',side_effect=failure), redirect_stderr(output):
            with self.assertRaises(subprocess.CalledProcessError): env._probe_json(['probe'],{})
        self.assertIn('import message',output.getvalue())
        self.assertIn('root cause',output.getvalue())

    def test_invalid_probe_json_includes_actual_output(self):
        with patch.object(env.subprocess,'check_output',return_value='unexpected import output'):
            with self.assertRaisesRegex(ValueError,'unexpected import output'):
                env._probe_json(['probe'],{})

    def test_resolver_uses_requested_python_and_preserves_hash_requirement(self):
        commands=[]
        env.resolve_lock(Path('target-python'),Path('candidate.in'),Path('output.lock'),commands.append)
        command=list(map(str,commands[0]))
        self.assertEqual(command[:4],['target-python','-m','piptools','compile'])
        self.assertIn('--generate-hashes',command)
        self.assertIn('--quiet',command)

    def test_finalize_checks_existing_attempt_without_installing(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            root=Path(temporary)
            (root/'.venv').mkdir()
            (root/'wheels').mkdir()
            wheel=root/'wheels/detectron2-0.6.whl'
            wheel.write_bytes(b'preserved wheel')
            candidate=env.candidate_text(Path(env.__file__).resolve().parents[3]/'requirements.in')
            (root/'requirements-candidate.in').write_text(candidate,encoding='utf-8')
            (root/'requirements.lock').write_text('preserved')
            (root/'requirements-complete.in').write_text('preserved')
            (root/'requirements-complete.lock').write_text('--hash=sha256:'+env.sha256(wheel))
            with patch.object(env.sys,'prefix',str(root/'.venv')), \
                 patch.object(env.platform,'system',return_value='Linux'), \
                 patch.object(env.subprocess,'check_output',side_effect=[env.D2_COMMIT,'compiler','release 12.6']), \
                 patch.object(env.subprocess,'run') as run, \
                 patch.object(env,'seal_environment',return_value=root/'environment.json') as seal:
                self.assertEqual(env.finalize(root),root/'environment.json')
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0][-3:],['-m','pip','check'])
            seal.assert_called_once()

    def test_relative_destination_and_finalize_plan_from_other_directory(self):
        root=Path(__file__).resolve().parents[2]/'new_code'
        result=subprocess.run([sys.executable,'-B',str(root/'setup_environment.py'),
                               '--plan','--finalize','--destination','runtime/environment-trial2'],
                              cwd=root.parent,capture_output=True,text=True,check=True)
        value=json.loads(result.stdout)
        self.assertEqual(Path(value['destination']),root/'runtime/environment-trial2')
        self.assertEqual(value['mode'],'finalize')
        self.assertFalse(any('Install' in step for step in value['steps']))


if __name__=='__main__': unittest.main()
