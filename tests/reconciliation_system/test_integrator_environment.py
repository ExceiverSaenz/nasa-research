"""Integrator environment contracts without real package installation."""
import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from integration import environment as env
from integration import dependencies
from tests.reconciliation_system import test_dependencies as receipts

class IntegratorEnvironmentTests(unittest.TestCase):
    def test_integrator_receipt_does_not_require_parser_imports(self):
        helper=receipts.SharedReceiptTests()
        with tempfile.TemporaryDirectory() as d:
            prefix,executable,manifest,package,lock,value=helper.receipt(Path(d))
            value['schema']='integration-environment/1'
            value['imports']={n:dict(path=str(package),sha256=dependencies.digest(package)) for n in ('fitz','docling.models.postprocessing.reading_order_rb')}
            manifest.write_text(json.dumps(value))
            with helper.patches(prefix,executable):
                result=dependencies.validate_shared_receipt(manifest,require_parser=False)
                self.assertEqual(result['manifest_sha256'],dependencies.digest(manifest))
                with self.assertRaisesRegex(ValueError,'lacks parser imports'):dependencies.validate_shared_receipt(manifest)
                lock.write_text('tamper')
                with self.assertRaisesRegex(ValueError,'artifact changed'):dependencies.validate_shared_receipt(manifest,require_parser=False)

    def make_bundle(self,root):
        root.mkdir()
        (root/'requirements-candidate.in').write_text(env.candidate())
        (root/'requirements-complete.lock').write_text('fixture==1 --hash=sha256:'+'a'*64+'\n')
        source=dict(schema='integration-environment/1',status='imports-validated',python=dependencies.SHARED_PYTHON,
                    versions={n.lower():v for n,v in dependencies.PINS.items()},
                    artifacts={n:dict(bytes=(root/n).stat().st_size,sha256=env.digest(root/n)) for n in ('requirements-candidate.in','requirements-complete.lock')})
        (root/'source-environment.json').write_text(json.dumps(source))
        data=dict(schema='integration-environment-bundle/1',host={'fixture':True},source_receipt='source-environment.json',
                  files={n:dict(bytes=(root/n).stat().st_size,sha256=env.digest(root/n)) for n in ('requirements-candidate.in','requirements-complete.lock','source-environment.json')})
        (root/'bundle.json').write_text(json.dumps(data));return data

    def test_bundle_candidate_host_and_hashes_verified(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'bundle';data=self.make_bundle(root)
            with patch.object(env,'host',return_value={'fixture':True}):self.assertEqual(env.validate_bundle(root),data)
            with patch.object(env,'host',return_value={'fixture':False}):
                with self.assertRaisesRegex(ValueError,'host differs'):env.validate_bundle(root)
            (root/'requirements-complete.lock').write_text('tampered')
            with self.assertRaisesRegex(ValueError,'artifact differs'):env.validate_bundle(root,check_host=False)

    def test_reuse_installs_frozen_lock_without_resolver_or_model_build(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'bundle';self.make_bundle(source);commands=[]
            with patch.object(env,'validate_bundle'),patch.object(env.platform,'system',return_value='Linux'),patch.object(env.subprocess,'run',side_effect=lambda argv,**kw:commands.append(list(map(str,argv)))):
                env.prepare(root/'environment',Path('python'),source)
            installs=[c for c in commands if 'install' in c]
            self.assertEqual(len(installs),1)
            self.assertIn('--no-deps',installs[0]);self.assertIn('--require-hashes',installs[0])
            text=' '.join(' '.join(c) for c in commands)
            self.assertNotIn('piptools',text);self.assertNotIn('git',text);self.assertNotIn('detectron2',text)

    def test_integrator_profile_reaches_spawned_scientific_stages(self):
        from integration.runner import run_collection
        from tests.reconciliation_system.test_runner import document_fixture, fixture_prediction
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);document=document_fixture(root)
            # Compact evidence does not require persisted images.
            document['pages'][0]['render_path']=None
            source=root/'source';source.mkdir()
            collection=dict(source_run=str(source),documents=[document],source_inputs=document['source_inputs'])
            out=root/'out'
            result=run_collection(collection,out,prediction_fn=fixture_prediction,runtime={'profile':'integrator'})
            self.assertEqual(result['status'],'completed')
            summary=json.loads((out/'papers/p000001/operational/summary.json').read_text())
            self.assertEqual(summary['runtime']['profile'],'integrator')
