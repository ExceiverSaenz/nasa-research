"""Offline receipt-order regression: production integration must see a receipt."""
import json
import os
from contextlib import nullcontext
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from parsing.unified import environment as env


class FinalizeTests(unittest.TestCase):
    def test_manifest_is_staged_before_strict_integration_and_published_after(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            wheel = root/'detectron2.whl'
            for name in ('requirements.lock','requirements-complete.lock','requirements-candidate.in',wheel.name):
                (root/name).write_text('fixture')
            events = []
            def probe(argv, **kwargs):
                if argv[-1] == '_observe':
                    return json.dumps({'prefix':'fixture','versions':{'fixture':'1'}})
                code = argv[-1]
                if 'require_shared_environment=False' in code:
                    events.append('diagnostic')
                    return json.dumps({'profile':'diagnostic'})
                pending = next(root.glob('environment.pending-*.json'))
                self.assertTrue(pending.is_file())
                self.assertFalse((root/'environment.json').exists())
                self.assertIn('manifest=', code)
                self.assertNotIn('require_shared_environment=False', code)
                events.append('strict')
                return '{}'
            def publish_fixture(source,target):
                # Windows sandbox disallows hardlinks; exercise ordering with an
                # exclusive copy. Production seal runs on Linux and uses os.link.
                with Path(target).open('xb') as stream: stream.write(Path(source).read_bytes())
            publication=patch.object(env.os,'link',side_effect=publish_fixture) if os.name=='nt' else nullcontext()
            with patch.object(env.subprocess,'check_output',side_effect=probe), publication:
                manifest=env.seal_environment(root,Path('python'),{},'a'*40,'compiler','toolkit',wheel,True)
            self.assertEqual(events,['diagnostic','strict'])
            self.assertTrue(manifest.is_file())
            self.assertFalse(list(root.glob('environment.pending-*.json')))
            value=json.loads(manifest.read_text())
            env.verify_files(root,value['artifacts'])

    def test_strict_failure_does_not_publish_environment(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root=Path(temp)
            wheel=root/'detectron2.whl'
            for name in ('requirements.lock','requirements-complete.lock','requirements-candidate.in',wheel.name):
                (root/name).write_text('fixture')
            def probe(argv,**kwargs):
                if argv[-1]=='_observe': return '{}'
                if 'require_shared_environment=False' in argv[-1]: return '{}'
                raise RuntimeError('strict integration failed')
            with patch.object(env.subprocess,'check_output',side_effect=probe):
                with self.assertRaisesRegex(RuntimeError,'strict integration'):
                    env.seal_environment(root,Path('python'),{},'a'*40,'compiler','toolkit',wheel,True)
            self.assertFalse((root/'environment.json').exists())

    def test_finalize_rejects_unrelated_interpreter_before_observing(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            with self.assertRaises(ValueError):
                env.finalize(Path(temp))


if __name__=='__main__': unittest.main()
