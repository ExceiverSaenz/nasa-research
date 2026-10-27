"""Offline batch sequencing; callbacks never import or run a model."""
from pathlib import Path
import tempfile
import json
import zipfile
import unittest
from unittest.mock import patch
from document_trial.common import MODELS, read, save, sha, verify_terminal
from document_trial.batch import batch_digest, validate_batch, run_documents, account_missing


class BatchTests(unittest.TestCase):
    def setUp(self):
        # Windows tests emulate only the Linux directory symlink, not model work.
        def link(path,target,target_is_directory=False):
            self.assertEqual(target.name,'models');self.assertTrue(target_is_directory)
            self.assertTrue(target.is_dir());path.mkdir()
        self.link=patch.object(Path,'symlink_to',link);self.link.start()
        self.addCleanup(self.link.stop)

    def fixture(self, root):
        inputs=root/'inputs';state=root/'state';state.mkdir()
        save(state/'execution.json',{'execution_id':'test','attempt_id':'test'})
        (state/'models').mkdir();(state/'config.yaml').write_text('unchanged')
        for model in MODELS:
            (inputs/model).mkdir(parents=True)
        entries=[]
        for i in (1,2):
            folder=inputs/'documents'/str(i);folder.mkdir(parents=True)
            (folder/'document.pdf').write_bytes(str(i).encode())
            digest=sha(folder/'document.pdf')
            plan=dict(document_sha256=digest,document=str(i)+'.pdf',page_count=2,
                physical_pages=[1,2],dpi=200,regression=None,models={},
                execution_policy='USER_ONLY_COLAB_CLI_T4',automatic_retries=False,
                automatic_recovery=False,postprocessing='native_outputs_only_no_reconciliation')
            save(folder/'plan.json',plan)
            entries.append(dict(key=digest,input_path='documents/'+str(i),plan=plan))
        plan=dict(documents=entries,models={},batch_sha256=batch_digest(entries))
        save(inputs/'plan.json',plan)
        return inputs,state,plan

    def test_all_three_per_document_and_isolated_outputs(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            inputs,state,plan=self.fixture(Path(temp));calls=[]
            def work(model,stage,source,dest):
                calls.append((dest.name,model,stage))
                self.assertEqual(read(source/'plan.json')['document_sha256'],dest.name)
                self.assertTrue((dest/'models').is_dir())
                self.assertEqual((dest/'config.yaml').read_text(),'unchanged')
            run_documents(inputs,state,work)
            self.assertEqual([(m,s) for _,m,s in calls],
                [('layoutlmv3','render')]+[(m,'infer') for m in MODELS]+
                [('layoutlmv3','render')]+[(m,'infer') for m in MODELS])
            for entry in plan['documents']:
                self.assertEqual(read(state/'documents'/entry['key']/'execution-status.json')['status'],'completed')

    def test_branch_failure_continues_other_models_and_next_document(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            inputs,state,plan=self.fixture(Path(temp));calls=[]
            def work(model,stage,source,dest):
                calls.append((dest.name,model,stage))
                if dest.name==plan['documents'][0]['key'] and model=='table_transformer':
                    raise RuntimeError('synthetic failure')
            with self.assertRaisesRegex(RuntimeError,'documents failed'):
                run_documents(inputs,state,work)
            self.assertEqual(len(calls),8)
            first=state/'documents'/plan['documents'][0]['key']
            self.assertEqual(read(first/'execution-status.json')['status'],'failed')
            self.assertIn('table_transformer',read(first/'branch-failures.json'))

    def test_preflight_rejects_changed_pdf_duplicate_and_config_drift(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            inputs,state,plan=self.fixture(Path(temp));validate_batch(inputs,plan)
            entry=plan['documents'][0]
            plan['documents'].append(entry);plan['batch_sha256']=batch_digest(plan['documents'])
            with self.assertRaises(ValueError):validate_batch(inputs,plan)
            plan['documents'].pop();entry['plan']['models']={'changed':True}
            plan['batch_sha256']=batch_digest(plan['documents'])
            with self.assertRaises(ValueError):validate_batch(inputs,plan)
            entry['plan']['models']={};plan['batch_sha256']=batch_digest(plan['documents'])
            (inputs/entry['input_path']/'document.pdf').write_bytes(b'changed')
            with self.assertRaises(ValueError):validate_batch(inputs,plan)

    def test_missing_statuses_accounted_even_when_setup_fails(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            inputs,state,plan=self.fixture(Path(temp))
            account_missing(plan,state)
            self.assertEqual(len(list(state.rglob('status.json'))),12)
            for entry in plan['documents']:
                self.assertEqual(read(state/'documents'/entry['key']/'execution-status.json')['status'],'failed')

    def test_terminal_backup_rejects_missing_accounting_and_false_completion(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root=Path(temp);inputs,state,plan=self.fixture(root)
            account_missing(plan,state)
            save(state/'plan.json',plan);save(state/'execution-status.json',dict(status='failed'))
            def check(name):
                archive=root/(name+'.zip')
                with zipfile.ZipFile(archive,'w') as z:
                    for p in state.rglob('*.json'):z.write(p,p.relative_to(state).as_posix())
                sidecar=root/(name+'.sha256');sidecar.write_text(sha(archive))
                return verify_terminal(archive,sidecar,(inputs/'plan.json').read_bytes())
            self.assertEqual(check('valid')['status'],'failed')
            save(state/'execution-status.json',dict(status='completed'))
            with self.assertRaises(ValueError):check('false-completion')
            save(state/'execution-status.json',dict(status='failed'))
            next(state.rglob('status.json')).unlink()
            with self.assertRaises(KeyError):check('missing-page')

    def test_render_failure_does_not_infer_affected_document(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            inputs,state,plan=self.fixture(Path(temp));calls=[]
            def work(model,stage,source,dest):
                calls.append((dest.name,stage))
                if dest.name==plan['documents'][0]['key']:raise ValueError('bad render')
            with self.assertRaises(RuntimeError):run_documents(inputs,state,work)
            self.assertEqual(len(calls),5)

if __name__=='__main__':unittest.main()
