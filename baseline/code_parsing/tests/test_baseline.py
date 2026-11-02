import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import contextmanager
import uuid
from unittest.mock import patch


@contextmanager
def workspace_temp():
    # Preserve test evidence outside the MVP; do not change TEMP permissions.
    root=Path(__file__).resolve().parents[3]/'history/baseline-tests'/uuid.uuid4().hex
    root.mkdir(parents=True)
    yield str(root)


class BaselineTests(unittest.TestCase):
    def test_catalog_csv_uses_canonical_records_and_quotes_names(self):
        from baseline.code_parsing.tests.catalog_export import CatalogExporter
        export_csv = CatalogExporter().export
        with workspace_temp() as tmp:
            root=Path(tmp)
            source=root/'collection.json'; target=root/'index.csv'
            source.write_text(json.dumps({'records':[{'name':'a,b.pdf','reused':False,
                'metrics':{'pages':2,'elements':3,'by_type':{'picture':1}},
                'result_directory':'results/run/papers/hash'}]}),encoding='utf8')
            export_csv(source,target)
            self.assertEqual(target.read_text(encoding='utf8'),
                'paper,reused,pages,elements,pictures,tables,formulas,result_directory\n'
                '"a,b.pdf",False,2,3,1,0,0,results/run/papers/hash\n')

    def test_figure_reuses_identical_native_asset(self):
        from baseline.code_parsing.parsing import AssetStore
        store_figure = AssetStore().store
        class Figure:
            def save(self, stream, format): stream.write(b'exact-png-payload')
        with workspace_temp() as tmp:
            root=Path(tmp); (root/'assets').mkdir()
            (root/'assets/image_native.png').write_bytes(b'exact-png-payload')
            name=store_figure(Figure(),root,'assets/figure-0001.png')
            self.assertEqual(name,'assets/image_native.png')
            self.assertEqual(len(list((root/'assets').iterdir())),1)
            self.assertEqual((root/name).read_bytes(),b'exact-png-payload')

    def test_distinct_figure_is_preserved(self):
        from baseline.code_parsing.parsing import AssetStore
        store_figure = AssetStore().store
        class Figure:
            def save(self, stream, format): stream.write(b'new-png-payload')
        with workspace_temp() as tmp:
            root=Path(tmp); (root/'assets').mkdir()
            (root/'assets/image_native.png').write_bytes(b'other-png-payload')
            name=store_figure(Figure(),root,'assets/figure-0001.png')
            self.assertEqual(name,'assets/figure-0001.png')
            self.assertEqual((root/name).read_bytes(),b'new-png-payload')
            self.assertEqual((root/'assets/image_native.png').read_bytes(),b'other-png-payload')

    def test_relocation_does_not_accept_external_uri_with_matching_path(self):
        from baseline.code_parsing.parsing import PortableExport
        portable_exports = PortableExport().relocate
        with workspace_temp() as tmp:
            root=Path(tmp);(root/'assets').mkdir();(root/'assets/image.png').write_bytes(b'fixture')
            (root/'document.json').write_text(json.dumps({'image':{'mimetype':'image/png',
                'uri':'https://example.com/content/old/assets/image.png'}}))
            (root/'document.md').write_text('fixture')
            with self.assertRaises(ValueError):portable_exports(root,'/content/old')
    def test_native_alias_references_are_checked(self):
        from baseline.code_parsing.parsing import ReferenceValidator
        validate_references = ReferenceValidator().validate
        with workspace_temp() as tmp:
            errors=validate_references({'self_ref':'#/body','children':[{'$ref':'#/texts/999'}]},Path(tmp))
            self.assertEqual(errors,['Unresolved reference: #/texts/999'])
    def test_absolute_local_image_is_not_portable(self):
        from baseline.code_parsing.parsing import ReferenceValidator
        validate_references = ReferenceValidator().validate
        with workspace_temp() as tmp:
            root=Path(tmp);p=root/'image.png';p.write_bytes(b'fixture')
            errors=validate_references({'image':{'mimetype':'image/png','uri':p.as_posix()}},root)
            self.assertTrue(errors)

    def test_export_paths_can_be_relocated_without_reconversion(self):
        from baseline.code_parsing.parsing import PortableExport, ReferenceValidator
        portable_exports = PortableExport().relocate
        validate_references = ReferenceValidator().validate
        with workspace_temp() as tmp:
            root=Path(tmp);(root/'assets').mkdir();(root/'assets/image.png').write_bytes(b'fixture')
            native={'image':{'mimetype':'image/png','uri':'/content/old-paper/assets/image.png'}}
            (root/'document.json').write_text(json.dumps(native))
            (root/'document.md').write_text('![Figure](/content/old-paper/assets/image.png)')
            portable_exports(root,'/content/old-paper')
            value=json.loads((root/'document.json').read_text())
            self.assertEqual(value['image']['uri'],'assets/image.png')
            self.assertEqual(validate_references(value,root),[])
            self.assertEqual((root/'document.md').read_text(),'![Figure](assets/image.png)')
    def test_bootstrap_uv_enforces_locked_wheel_without_system_venv(self):
        import baseline.code_parsing.worker as worker
        import hashlib, zipfile
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:z.writestr('uv.data/scripts/uv',b'ELF-fixture')
        wheel=data.getvalue(); sha=hashlib.sha256(wheel).hexdigest()
        with workspace_temp() as tmp:
            root=Path(tmp);runtime=root/'runtime';runtime.mkdir()
            (root/'bootstrap.lock').write_text('uv==0.12.21 --hash=sha256:'+sha)
            metadata=json.dumps({'urls':[{'filename':'uv.whl','digests':{'sha256':sha},'url':'https://example.com/uv.whl'}]}).encode()
            with patch.object(worker,'ROOT',root),patch.object(worker.urllib.request,'urlopen',
                    side_effect=[io.BytesIO(metadata),io.BytesIO(wheel)]):
                binary=worker.PythonProvisioner(root).bootstrap_uv(runtime)
            self.assertEqual(binary.read_bytes(),b'ELF-fixture')
            self.assertTrue((runtime/'bootstrap-receipt.json').exists())

    def test_plan_is_offline_and_keeps_r2_prefix(self):
        from baseline.code_parsing.colab_run import BaselinePlanner
        plan = BaselinePlanner().plan
        with workspace_temp() as tmp:
            root = Path(tmp)
            (root / 'a paper.pdf').write_bytes(b'%PDF-1.7\nfixture')
            with patch('subprocess.run', side_effect=AssertionError('remote action')):
                value = plan(root, ['a paper.pdf'], False)
            self.assertEqual(value['papers'][0]['key'], 'tensile_papers/a paper.pdf')
            self.assertEqual(value['gpu'], 'A100')
            self.assertEqual(value['install_command_flags'], ['--require-hashes', '--only-binary=:all:'])

    def test_selection_rejects_escape_duplicate_and_non_pdf(self):
        from baseline.code_parsing.r2 import PdfSelector
        select = PdfSelector().select
        with workspace_temp() as tmp:
            root = Path(tmp)
            (root / 'a.pdf').write_bytes(b'%PDF-1.7')
            for names in [['../a.pdf'], ['a.pdf', 'a.pdf'], ['missing.pdf']]:
                with self.assertRaises(ValueError):
                    select(root, names, False)

    def test_lock_is_verified(self):
        from baseline.code_parsing.common import IntegrityService
        verify_lock = IntegrityService().verify_lock
        self.assertEqual(verify_lock()['package_count'], 121)

    def test_normalization_preserves_native_order_and_all_regions(self):
        from baseline.code_parsing.parsing import DocumentNormalizer
        normalize = DocumentNormalizer().normalize
        class Item:
            def __init__(self, value): self.value = value
            def model_dump(self, **kw): return self.value
            def export_to_markdown(self, **kw): return '| value |'
        class Doc:
            pages = {}
            def iterate_items(self):
                yield Item({'self_ref':'#/pictures/0', 'label':'picture', 'captions':[{'cref':'#/texts/1'}], 'prov':[{'page_no':1}, {'page_no':2}]}), 1
                yield Item({'self_ref':'#/texts/1', 'label':'caption', 'text':'Caption'}), 1
                yield Item({'self_ref':'#/tables/0', 'label':'table', 'data':{'table_cells':[]}}), 1
        rows = normalize(Doc(), 'abc', {'#/pictures/0':'assets/figure.png'})
        self.assertEqual([r['type'] for r in rows], ['picture', 'caption', 'table'])
        self.assertEqual(len(rows[0]['provenance']), 2)
        self.assertEqual(rows[0]['caption_refs'], ['#/texts/1'])
        self.assertEqual(rows[2]['table_markdown'], '| value |')

    def test_transport_rejects_traversal(self):
        from baseline.code_parsing.common import IntegrityService
        extract = IntegrityService().extract
        with workspace_temp() as tmp:
            root = Path(tmp); archive = root/'bad.tar.gz'
            with tarfile.open(archive, 'w:gz') as tar:
                info=tarfile.TarInfo('../escape'); info.size=1
                tar.addfile(info, io.BytesIO(b'x'))
            with self.assertRaises(ValueError): extract(archive, root/'out')

    def test_marker_required(self):
        from baseline.code_parsing.colab_run import ColabSession
        require_marker = ColabSession.require_marker
        with self.assertRaises(RuntimeError): require_marker('exit code 0', 'id', 'parse')
        require_marker('BASELINE_COMPLETED:id:parse\n', 'id', 'parse')

    def test_download_hash_mismatch_is_private(self):
        from baseline.code_parsing.r2 import R2Client
        download = R2Client().download
        with workspace_temp() as tmp:
            root=Path(tmp)
            request={'files':[{'name':'a.pdf','key':'tensile_papers/a.pdf','bytes':8,'sha256':'0'*64,'url':'https://account.r2.cloudflarestorage.com/bucket/tensile_papers/a.pdf?X-Amz-Signature=SECRET'}]}
            with patch('urllib.request.urlopen', return_value=io.BytesIO(b'%PDF-bad')):
                with self.assertRaises(RuntimeError) as cm: download(request,root)
            self.assertNotIn('SECRET', str(cm.exception))
            self.assertFalse((root/'a.pdf').exists())

    def test_failed_conversion_is_preserved_and_not_reused(self):
        from baseline.code_parsing.parsing import PaperParser, DocumentExporter
        class Converter:
            def convert(self, *args, **kw): raise RuntimeError('conversion failed')
        with workspace_temp() as tmp:
            root=Path(tmp); pdf=root/'a.pdf'; pdf.write_bytes(b'%PDF-fixture')
            result=PaperParser(Converter()).parse(pdf,root/'results',{},'model-hash')
            self.assertEqual(result['status'],'failed')
            folder=next((root/'results').iterdir())
            self.assertTrue((folder/'files.json').is_file())
            with self.assertRaises(ValueError): PaperParser(Converter()).parse(pdf,root/'results',{},'model-hash')

    def test_partial_conversion_exports_available_document(self):
        from baseline.code_parsing.parsing import PaperParser, DocumentExporter
        from types import SimpleNamespace
        converter=SimpleNamespace(convert=lambda *a,**kw:SimpleNamespace(
            status=SimpleNamespace(value='partial_success'),errors=[],document=object()))
        with workspace_temp() as tmp:
            root=Path(tmp); pdf=root/'a.pdf'; pdf.write_bytes(b'%PDF-fixture')
            with patch.object(DocumentExporter,'export',return_value=({'pages':1},[])) as exported:
                result=PaperParser(converter).parse(pdf,root/'results',{},'model-hash')
            self.assertEqual(result['status'],'partial')
            self.assertEqual(result['metrics']['pages'],1)
            exported.assert_called_once()

    def test_completed_cache_rejects_different_model_identity(self):
        from baseline.code_parsing.parsing import PaperParser, DocumentExporter
        from types import SimpleNamespace
        calls=[]
        def convert(*a,**kw):
            calls.append(1)
            return SimpleNamespace(status=SimpleNamespace(value='success'),errors=[],document=object())
        converter=SimpleNamespace(convert=convert)
        with workspace_temp() as tmp:
            root=Path(tmp); pdf=root/'a.pdf'; pdf.write_bytes(b'%PDF-fixture')
            with patch.object(DocumentExporter,'export',return_value=({'pages':1},[])):
                PaperParser(converter).parse(pdf,root/'results',{},'models-one')
                result=PaperParser(converter).parse(pdf,root/'results',{},'models-one')
                with self.assertRaises(ValueError):PaperParser(converter).parse(pdf,root/'results',{},'models-two')
            self.assertEqual(result['status'],'completed')
            self.assertEqual(len(calls),1)

    def test_manifest_includes_nested_manifests(self):
        from baseline.code_parsing.common import file_manifest, write_json, IntegrityService
        verify_files = IntegrityService().verify_files
        with workspace_temp() as tmp:
            root=Path(tmp); child=root/'paper'; child.mkdir()
            write_json(child/'files.json', {'proof':True})
            write_json(root/'files.json',file_manifest(root))
            verify_files(root)
            (child/'files.json').write_text('{}')
            with self.assertRaises(ValueError): verify_files(root)

    def test_reference_validation_rejects_missing_and_external_images(self):
        from baseline.code_parsing.parsing import ReferenceValidator
        validate_references = ReferenceValidator().validate
        with workspace_temp() as tmp:
            errors=validate_references({'self_ref':'#/body','children':[{'cref':'#/missing'}],
                                       'image':{'mimetype':'image/png','uri':'https://example.com/a.png'}},Path(tmp))
            self.assertEqual(len(errors),2)

    def test_sigv4_keeps_secret_out_and_encodes_spaces(self):
        from baseline.code_parsing.r2 import R2Client
        url=R2Client({'R2_ENDPOINT_URL':'https://account.r2.cloudflarestorage.com',
                     'R2_BUCKET':'bucket','AWS_ACCESS_KEY_ID':'public-id','AWS_SECRET_ACCESS_KEY':'private-secret'}).presign(
                    'tensile_papers/a paper.pdf')
        self.assertIn('a%20paper.pdf?',url)
        self.assertNotIn('private-secret',url)
        self.assertIn('X-Amz-Signature=',url)

    def test_prepare_provisions_pinned_python_before_installing_lock(self):
        from baseline.code_parsing.worker import PythonProvisioner
        with workspace_temp() as tmp:
            root=Path(tmp)
            expected=root/'python'; expected.write_text('fixture')
            calls=[]
            def run(args, **kw):
                calls.append(list(map(str,args)))
                return subprocess.CompletedProcess(args,0,stdout=str(expected)+'\n')
            with patch('baseline.code_parsing.worker.subprocess.run',side_effect=run), \
                 patch.object(PythonProvisioner,'bootstrap_uv',return_value=root/'uv'):
                result=PythonProvisioner().provision(root)
            self.assertEqual(result,expected)
            self.assertTrue(any('3.11.16' in cmd and 'install' in cmd for cmd in calls))
            self.assertTrue(any('find' in cmd and '--managed-python' in cmd for cmd in calls))

    def test_full_controller_downloads_verified_results_before_closing(self):
        import baseline.code_parsing.colab_run as controller
        from baseline.code_parsing.common import digest, file_manifest, write_json
        import shutil
        with workspace_temp() as tmp:
            root=Path(tmp); source=root/'code'; source.mkdir()
            for name in controller.BaselineController.SOURCE_FILES:
                target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(controller.ROOT/name,target)
            pdf=root/'fixture.pdf'; pdf.write_bytes(b'%PDF-1.7\nfixture')
            value=controller.BaselinePlanner().plan(root,['fixture.pdf'],False)
            result=root/'result'; result.mkdir()
            write_json(result/'status.json',{'status':'completed','papers':[dict(value['papers'][0],status='completed')]})
            write_json(result/'files.json',file_manifest(result))
            transport=root/'results.tar.gz'
            with tarfile.open(transport,'w:gz') as tar:
                for p in result.iterdir(): tar.add(p,arcname=p.name)
            calls=[]
            def run(args,**kw):
                args=list(map(str,args)); calls.append(args)
                output=''
                if args[1]=='stop': output='[colab] Session terminated.\n'
                if args[1]=='exec' and args[args.index('-f')+1].endswith(('prepare.py','parse.py')):
                    script=Path(args[args.index('-f')+1]); phase=script.stem
                    output='BASELINE_COMPLETED:'+script.parent.name+':'+phase+'\n'
                if args[1]=='download':
                    target=Path(args[-1])
                    if args[-2].endswith('.tar.gz'): shutil.copyfile(transport,target)
                    else: target.write_text(digest(transport))
                return subprocess.CompletedProcess(args,0,stdout=output)
            config={'R2_ENDPOINT_URL':'https://account.r2.cloudflarestorage.com','R2_BUCKET':'bucket',
                    'AWS_ACCESS_KEY_ID':'public','AWS_SECRET_ACCESS_KEY':'secret'}
            with patch.object(controller,'ROOT',source), patch.object(controller.sys,'platform','linux'), \
                 patch.object(controller.shutil,'which',return_value='colab'), \
                 patch.object(controller.R2Credentials,'load',return_value=config), \
                 patch.object(controller.subprocess,'run',side_effect=run), \
                 patch.object(controller.tempfile,'TemporaryDirectory',side_effect=lambda **kw:workspace_temp()):
                status=controller.BaselineController(source).execute(value,root/'unused.env','python3')
            self.assertEqual(status['status'],'completed')
            self.assertTrue(status['session_closed'])
            self.assertEqual(calls[-1][1],'stop')
            self.assertNotIn('secret',(source/'runtime/colab-attempts'/status['id']/'cli.log').read_text())

    def test_preparation_failure_recovers_and_closes_only_owned_session(self):
        import baseline.code_parsing.colab_run as controller
        import shutil
        with workspace_temp() as tmp:
            root=Path(tmp); source=root/'code'; source.mkdir()
            for name in controller.BaselineController.SOURCE_FILES:
                target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(controller.ROOT/name,target)
            calls=[]
            def run(args,**kw):
                args=list(map(str,args));calls.append(args)
                failure=args[1]=='exec' and args[args.index('-f')+1].endswith('prepare.py')
                return subprocess.CompletedProcess(args,1 if failure else 0,
                    stdout='[colab] Session terminated.\n' if args[1]=='stop' else 'fixture failure')
            with patch.object(controller,'ROOT',source),patch.object(controller.sys,'platform','linux'), \
                 patch.object(controller.shutil,'which',return_value='colab'), \
                 patch.object(controller.R2Credentials,'load',return_value={}), \
                 patch.object(controller.subprocess,'run',side_effect=run):
                with self.assertRaises(RuntimeError):controller.BaselineController(source).execute({'papers':[]},root/'unused','python3')
            status=json.loads(next((source/'runtime/colab-attempts').glob('*/status.json')).read_text())
            self.assertTrue(status['session_closed'])
            self.assertEqual(calls[-1][1],'stop')
            self.assertTrue(all(args[args.index('-s')+1]==status['session'] for args in calls))

    def test_batch_failure_keeps_diagnostic_without_signed_url(self):
        import baseline.code_parsing.worker as worker
        from types import SimpleNamespace
        with workspace_temp() as tmp:
            root=Path(tmp)/'code'; root.mkdir()
            request=root/'request.json'; request.write_text('{}')
            with patch.object(worker,'ROOT',root), patch.object(worker.PlatformValidator,'validate',
                    side_effect=ValueError('model mismatch https://example.com/a?secret=TOKEN')):
                worker.BatchProcessor(root,integrity=SimpleNamespace(verify_lock=lambda:{})).parse(request)
            result=json.loads((root/'results/status.json').read_text())
            self.assertIn('model mismatch',result['error'])
            self.assertNotIn('TOKEN',result['error'])
            self.assertEqual(result['status'],'failed')
            self.assertFalse(request.exists())


if __name__ == '__main__': unittest.main()
