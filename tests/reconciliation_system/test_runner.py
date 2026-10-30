import json
from functools import partial
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from integration.storage import results_root, resolve_output
from integration.runner import main, process_document, run_collection


def fixture_worker(document, destination, prediction_fn=None):
    start = time.monotonic()
    time.sleep(.15)
    if document.get('fail'):
        raise ValueError('fixture paper failure')
    return dict(paper_id=document['paper_id'], started=start, ended=time.monotonic(),
                pid=os.getpid(), python=__import__('sys').executable, stages=['reconcile', 'classify', 'capsules', 'integrate'])


def fixture_prediction(items):
    return [item['id'] for item in items]


def document_fixture(root):
    import fitz
    from PIL import Image
    from integration.common import digest
    pdf=root/'arbitrary paper name.pdf'
    with fitz.open() as document:
        page=document.new_page(width=1000,height=1000)
        page.insert_text((100,120),'Scientific fixture')
        document.save(pdf)
    render=root/'render.png';Image.new('RGB',(1000,1000),'white').save(render)
    native=root/'native.json';native.write_text('{"fixture":"original native source"}')
    source=dict(path=str(native),sha256=digest(native),pointer='/fixture')
    record=dict(id=digest(pdf)+':p1:mineru:/pages/0/blocks/0',parser='mineru',
                native_type='text',bbox=[100,100,450,200],native_bbox=[.1,.1,.45,.2],
                parent=None,role='segment',native=dict(type='text',content='Scientific fixture',bbox=[.1,.1,.45,.2]),
                source=source,transform=[1000,0,0,1000,0,0],text='Scientific fixture')
    page=dict(identity=dict(document_sha256=digest(pdf),physical_page=1,width_px=1000,height_px=1000,render_sha256=digest(render)),
              records=[record],parsers={x:'completed' for x in ('mineru','layoutlmv3','table_transformer')},
              adapter='canonical-v1',incidents=[],render_path=str(render),missing_sources=[])
    return dict(paper_id='arbitrary-name',id='arbitrary-name',document=str(pdf),document_sha256=digest(pdf),
                pages=[page],source_inputs={str(p):digest(p) for p in (native,render,pdf)},parser_configuration={'fixture':True})


class StorageTests(unittest.TestCase):
    def test_shared_root_and_scoped_unique_outputs(self):
        self.assertEqual(results_root().name, 'reconciliation_results')
        self.assertEqual(results_root().parent.name, 'results')
        self.assertNotEqual(resolve_output(None), resolve_output(None))
        self.assertEqual(resolve_output('attempt').parent, results_root().resolve())
        for path in ('../escape', 'nested/run', results_root(), results_root().parent/'parse_results'/'run'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                resolve_output(path)


class CoordinatorTests(unittest.TestCase):
    def test_cli_rejects_different_or_missing_shared_environment_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'out'
            for source in ('b'*64,None):
                collection={'parser_configuration':{'env_manifest_sha256':source}}
                with self.subTest(source=source),patch('integration.runner.resolve_output',return_value=output), \
                     patch('integration.dependencies.preflight',return_value={'manifest_sha256':'a'*64}), \
                     patch('integration.hybrid_inputs.load_run',return_value=collection), \
                     patch('integration.runner.run_collection') as run:
                    with self.assertRaises(SystemExit):main(['run','--parse-run','fixture'])
                    run.assert_not_called()
                    self.assertFalse(output.exists())

    def test_cli_matching_shared_environment_receipt_reaches_coordinator(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'out'
            collection={'parser_configuration':{'env_manifest_sha256':'a'*64}}
            runtime={'manifest_sha256':'a'*64}
            with patch('integration.runner.resolve_output',return_value=output), \
                 patch('integration.dependencies.preflight',return_value=runtime), \
                 patch('integration.hybrid_inputs.load_run',return_value=collection), \
                 patch('integration.runner.run_collection',return_value={'status':'completed'}) as run:
                self.assertEqual(main(['run','--parse-run','fixture','--workers','3']),0)
                run.assert_called_once_with(collection,output,max_workers=3,runtime=runtime)

    def test_manifest_run_does_not_call_optional_archiver(self):
        from integration.runner import verify_manifests
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);collection=self.collection(root,1)
            with patch('integration.runner.archive_run',side_effect=OSError('archive must not be called')):
                report=run_collection(collection,root/'out',max_workers=1,worker=fixture_worker)
            self.assertEqual(report['status'],'completed')
            self.assertFalse((root/'out.zip').exists())
            self.assertGreater(verify_manifests(root/'out'),0)

    def test_native_parser_formats_through_all_stages_in_spawned_workers(self):
        from tests.reconciliation_system.test_hybrid_inputs import fixture, seal_run
        from integration.hybrid_inputs import load_run
        from integration.common import digest
        from integration.dependencies import preflight
        import fitz
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=fixture(root,count=2)
            # Replace adapter-only synthetic PDF bytes with readable native PDFs.
            # The native parser payloads remain in their actual on-disk schemas.
            for pdf in root.glob('*.pdf'):
                old=digest(pdf)
                with fitz.open() as native:
                    native.new_page(width=72,height=36).insert_text((3,12),pdf.stem)
                    raw=native.tobytes()
                pdf.write_bytes(raw);new=digest(pdf)
                def update(value):
                    if isinstance(value,dict):return {key:update(item) for key,item in value.items()}
                    if isinstance(value,list):return [update(item) for item in value]
                    return new if value==old else value
                for path in source.rglob('*.json'):
                    path.write_text(json.dumps(update(json.loads(path.read_text()))),encoding='utf-8')
            seal_run(source)
            collection=load_run(source)
            runtime=preflight(require_shared_environment=False)
            report=run_collection(collection,root/'integrated',max_workers=2,
                                  worker=partial(process_document,runtime_profile='historical'),runtime=runtime)
            self.assertEqual(report['status'],'completed',report)
            self.assertEqual(len(report['papers']),2)
            for paper in report['papers']:
                self.assertEqual(paper['result']['stages'],['reconcile','classify','capsules','integrate'])
                self.assertEqual(paper['result']['metrics']['inventory_units'],1)
            self.assertTrue(all(digest(name)==sha for name,sha in collection['source_inputs'].items()))
            self.assertFalse(json.loads((root/'integrated/execution-profile.json').read_text())['fixture_predictor'])

    def test_existing_scientific_stages_full_export_and_conservation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);document=document_fixture(root)
            report=process_document(document,root/'paper-output',fixture_prediction)
            self.assertEqual(report['stages'],['reconcile','classify','capsules','integrate'])
            self.assertEqual(report['status'],'completed')
            output=root/'paper-output'
            rec=json.loads((output/'reconciliation/papers/1/document.json').read_text())
            self.assertEqual(rec['pages'][0]['records'][0]['native'],document['pages'][0]['records'][0]['native'])
            result=json.loads((output/'operational/papers/1/document.json').read_text())
            self.assertEqual(len(result['inventory']),1)
            self.assertIsNone(result['metrics']['semantic_accuracy'])
            self.assertEqual((output/'operational/papers/1/view/images/0001.png').read_bytes(),(root/'render.png').read_bytes())

    def collection(self, root, count=4):
        source = root/'input.json'; source.write_text('{}')
        from integration.common import digest
        return dict(source_run=str(root/'parse-attempt'), adapter='fixture',
                    source_inputs={str(source):digest(source)},
                    documents=[dict(paper_id='named-paper-'+str(i), id='named-paper-'+str(i)) for i in range(count)])

    def test_spawn_concurrency_same_interpreter_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); collection=self.collection(root)
            report=run_collection(collection, root/'out', max_workers=2, worker=fixture_worker)
            self.assertEqual(report['status'], 'completed')
            rows=[x['result'] for x in report['papers']]
            self.assertTrue(any(a['started']<b['ended'] and b['started']<a['ended'] for i,a in enumerate(rows) for b in rows[i+1:] if a['pid']!=b['pid']))
            self.assertTrue(all(Path(x['python']).resolve()==Path(__import__('sys').executable).resolve() for x in rows))
            self.assertFalse((root/'out.zip').exists())
            self.assertFalse((root/'out.zip.sha256').exists())
            self.assertTrue((root/'out'/'manifest.json').is_file())
            self.assertEqual(json.loads((root/'out/summary.json').read_text())['completed'],4)
            self.assertTrue((root/'out/index.html').is_file())
            with self.assertRaises(FileExistsError): run_collection(collection,root/'out',worker=fixture_worker)

    def test_failure_is_terminal_and_other_papers_accounted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); collection=self.collection(root,3); collection['documents'][1]['fail']=True
            report=run_collection(collection,root/'out',max_workers=2,worker=fixture_worker)
            self.assertEqual(report['status'],'failed')
            self.assertEqual(len(report['papers']),3)
            self.assertEqual(sum(x['status']=='failed' for x in report['papers']),1)
            saved=json.loads((root/'out/status.json').read_text())
            self.assertTrue(saved['outputs_may_be_partial'])

    def test_changed_sources_and_duplicate_ids_fail_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);collection=self.collection(root,2)
            collection['documents'][1]['paper_id']=collection['documents'][0]['paper_id']
            with self.assertRaises(ValueError):run_collection(collection,root/'out',worker=fixture_worker)
            self.assertFalse((root/'out').exists())
            collection=self.collection(root,1);(root/'input.json').write_text('changed')
            with self.assertRaises(ValueError):run_collection(collection,root/'out',worker=fixture_worker)
            self.assertFalse((root/'out').exists())

class RenderlessStageTests(unittest.TestCase):
    def test_all_stages_without_render_or_view(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); document=document_fixture(root)
            document['pages'][0]['render_path']=None
            render=root/'render.png';document['source_inputs'].pop(str(render));render.unlink()
            report=process_document(document,root/'out',fixture_prediction)
            self.assertEqual(report['status'],'completed')
            self.assertFalse(list((root/'out').rglob('*.png')))
            self.assertNotIn('href="None"',(root/'out/operational/index.html').read_text())
