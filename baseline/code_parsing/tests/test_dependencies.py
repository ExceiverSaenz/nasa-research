"""Behavioral contracts for independent roots and injected dependencies."""
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_baseline import workspace_temp


class DependencyTests(unittest.TestCase):
    def test_recovery_write_failure_still_closes_owned_session(self):
        self._check_recovery_closure('write')

    def test_recovery_interrupt_still_closes_owned_session(self):
        self._check_recovery_closure('interrupt')

    def _check_recovery_closure(self, failure):
        from baseline.code_parsing.colab_run import BaselineController
        from baseline.code_parsing.common import ROOT
        import shutil
        calls=[]
        class Session:
            def __init__(self,name,local):pass
            def command(self,args):
                calls.append(args)
                if failure=='interrupt' and args[1]=='exec' and str(args[args.index('-f')+1]).endswith('recover.py'):
                    raise KeyboardInterrupt('interrupted recovery')
                return '[colab] Session terminated.\n' if args[1]=='stop' else ''
            def run_phase(self,*args):raise RuntimeError('preparation failed')
        original_write=Path.write_text
        def write(path,*args,**kwargs):
            if failure=='write' and path.name=='recover.py':raise OSError('recovery storage unavailable')
            return original_write(path,*args,**kwargs)
        with workspace_temp() as tmp:
            root=Path(tmp)/'code';root.mkdir()
            for name in BaselineController.SOURCE_FILES:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/name,target)
            controller=BaselineController(root,session_factory=Session,
                credentials=SimpleNamespace(load=lambda _:{}))
            with patch('baseline.code_parsing.colab_run.sys.platform','linux'), \
                 patch('baseline.code_parsing.colab_run.shutil.which',return_value='colab'),patch.object(Path,'write_text',write):
                try:controller.execute({'papers':[]},root/'unused','python3')
                except (RuntimeError,OSError,KeyboardInterrupt):pass
            self.assertEqual(calls[-1][1],'stop')
            status=json.loads(next((root/'runtime/colab-attempts').glob('*/status.json')).read_text())
            self.assertTrue(status['session_closed'])

    def test_platform_validation_uses_injected_runner_for_driver_and_pip(self):
        from baseline.code_parsing.worker import PlatformValidator
        calls=[]
        def runner(args,**kwargs):
            calls.append(args)
            return SimpleNamespace(stdout='580.82.07\n')
        cuda=SimpleNamespace(is_available=lambda:True,get_device_name=lambda _: 'A100',
            get_device_properties=lambda _:SimpleNamespace(total_memory=40*1024**3))
        torch=SimpleNamespace(__version__='2.7.1+cu126',version=SimpleNamespace(cuda='12.6'),cuda=cuda)
        onnx=SimpleNamespace(get_available_providers=lambda:['CPUExecutionProvider'])
        distribution=SimpleNamespace(metadata={'Name':'torchvision'},version='0.22.1+cu126')
        with workspace_temp() as tmp:
            root=Path(tmp);(root/'requirements.lock').write_text('torchvision==0.22.1+cu126\n')
            with patch.dict('sys.modules',{'torch':torch,'onnxruntime':onnx}), \
                 patch('baseline.code_parsing.worker.sys.platform','linux'), \
                 patch('baseline.code_parsing.worker.platform.machine',return_value='x86_64'), \
                 patch('baseline.code_parsing.worker.platform.python_version',return_value='3.11.16'), \
                 patch('baseline.code_parsing.worker.platform.platform',return_value='Linux'), \
                 patch('baseline.code_parsing.worker.platform.libc_ver',return_value=('glibc','2.35')), \
                 patch('baseline.code_parsing.worker.importlib.metadata.distributions',return_value=[distribution]), \
                 patch('baseline.code_parsing.worker.subprocess.check_output',side_effect=AssertionError('Use injected runner')):
                result=PlatformValidator(root,runner=runner).validate()
            self.assertEqual(result['driver'],'580.82.07')
            self.assertEqual(calls[0][0],'nvidia-smi')
            self.assertEqual(calls[1][-3:],['-m','pip','check'])

    def test_batch_completes_with_injected_downloader_converter_and_exporter(self):
        from baseline.code_parsing.worker import BatchProcessor
        from baseline.code_parsing.parsing import PaperParser
        from baseline.code_parsing.common import IntegrityService, digest, file_manifest, write_json
        with workspace_temp() as tmp:
            root=Path(tmp)/'baseline';root.mkdir();runtime=root/'runtime';runtime.mkdir()
            models=runtime/'models';models.mkdir();(models/'weights').write_bytes(b'fixture')
            write_json(runtime/'models.json',file_manifest(models))
            environment={'python':'fixture','packages':{},'driver':'fixture','gpu':'fixture',
                'lock_sha256':'sealed','models_manifest_sha256':digest(runtime/'models.json')}
            write_json(runtime/'environment.json',environment)
            request=root/'request.json';request.write_text('{"files":[]}')
            class Downloader:
                def download(self,request,destination):
                    destination.mkdir();pdf=destination/'a.pdf';pdf.write_bytes(b'%PDF-fixture')
                    return [{'name':'a.pdf','sha256':digest(pdf)}]
            class Exporter:
                def export(self,document,output,paper_id):
                    (output/'document.json').write_text('{"content":"fixture"}')
                    return {'pages':1,'elements':0,'by_type':{}},[]
            converter=SimpleNamespace(convert=lambda *a,**kw:SimpleNamespace(
                status=SimpleNamespace(value='success'),errors=[],document='fixture'))
            integrity=IntegrityService(root)
            with patch.object(integrity,'verify_lock',return_value={'lock_sha256':'sealed'}),patch.dict('os.environ',{}):
                BatchProcessor(root,integrity=integrity,platform_validator=SimpleNamespace(validate=lambda:environment),
                    downloader=Downloader(),converter_factory=lambda _:converter,
                    parser_factory=lambda c:PaperParser(c,integrity=integrity,exporter=Exporter())).parse(request)
            status=json.loads((root/'results/status.json').read_text())
            self.assertEqual(status['status'],'completed')
            self.assertEqual(len(status['papers']),1)
            self.assertFalse(request.exists())
            integrity.verify_files(root/'results')
            self.assertTrue((root.parent/'baseline-results.tar.gz').is_file())

    def test_generated_remote_script_executes_without_local_session_object(self):
        from baseline.code_parsing.colab_run import ColabSession
        import subprocess
        calls=[]
        with workspace_temp() as tmp:
            root=Path(tmp)
            runner=lambda *a,**kw: SimpleNamespace(returncode=0,stdout='BASELINE_COMPLETED:run:prepare\n')
            ColabSession('owned',root,runner=runner).run_phase('prepare','python3','run')
            def remote_run(args,**kwargs):
                calls.append(args)
                kwargs['stdout'].write('remote work completed\n')
                return SimpleNamespace(check_returncode=lambda:None)
            remote_subprocess=SimpleNamespace(run=remote_run,STDOUT=subprocess.STDOUT)
            remote_pathlib=SimpleNamespace(Path=lambda _:root/'remote.log')
            with patch.dict('sys.modules',{'subprocess':remote_subprocess,'pathlib':remote_pathlib}):
                exec(compile((root/'prepare.py').read_text(),'prepare.py','exec'),{})
            self.assertEqual(calls,[['python3','-B','-m','baseline.code_parsing.worker','prepare','--run-id','run']])

    def test_session_rejects_command_addressing_another_session(self):
        from baseline.code_parsing.colab_run import ColabSession
        def forbidden(*a,**kw):raise AssertionError('Must not run a foreign command')
        with workspace_temp() as tmp:
            session=ColabSession('owned',Path(tmp),runner=forbidden)
            with self.assertRaises(ValueError):session.command(['colab','stop','-s','foreign'])
            with self.assertRaises(ValueError):session.command(['colab','stop','-s','owned','-s','foreign'])

    def test_controller_blocks_new_session_after_unconfirmed_closure(self):
        from baseline.code_parsing.colab_run import BaselineController
        with workspace_temp() as tmp:
            root=Path(tmp); old=root/'runtime/colab-attempts/old';old.mkdir(parents=True)
            (old/'status.json').write_text(json.dumps({'session_creation_attempted':True,'session_closed':False}))
            with patch('baseline.code_parsing.colab_run.sys.platform','linux'),patch('baseline.code_parsing.colab_run.shutil.which',return_value='colab'):
                with self.assertRaisesRegex(RuntimeError,'closure unconfirmed'):
                    BaselineController(root).execute({},root/'unused','python3')

    def test_planner_uses_injected_selection_and_integrity_without_external_io(self):
        from baseline.code_parsing.colab_run import BaselinePlanner
        calls=[]
        integrity=SimpleNamespace(verify_lock=lambda: {'lock_sha256':'lock','input_sha256':'input'})
        class Selector:
            def select(self,directory,names,all_papers):
                calls.append((directory,names,all_papers))
                return [{'name':'chosen.pdf','sha256':'identity'}]
        result=BaselinePlanner(integrity=integrity,selector=Selector()).plan('folder',['chosen.pdf'],False)
        self.assertEqual(result['papers'],[{'name':'chosen.pdf','sha256':'identity'}])
        self.assertEqual(result['lock_sha256'],'lock')
        self.assertEqual(calls,[('folder',['chosen.pdf'],False)])

    def test_integrity_instances_verify_their_own_root(self):
        from baseline.code_parsing.common import IntegrityService,digest
        with workspace_temp() as tmp:
            base=Path(tmp)
            for name in ['a','b']:
                root=base/name;root.mkdir()
                (root/'requirements.in').write_text(name)
                (root/'requirements.lock').write_text(name+'lock')
                (root/'lock-verification.json').write_text(json.dumps({
                    'input_sha256':digest(root/'requirements.in'),
                    'lock_sha256':digest(root/'requirements.lock')}))
            a=IntegrityService(base/'a');b=IntegrityService(base/'b')
            self.assertNotEqual(a.verify_lock()['input_sha256'],b.verify_lock()['input_sha256'])
            (base/'b/requirements.lock').write_text('changed')
            a.verify_lock()
            with self.assertRaises(ValueError):b.verify_lock()

    def test_r2_download_uses_injected_opener_and_checks_identity(self):
        from baseline.code_parsing.r2 import R2Client
        import hashlib
        data=b'%PDF-fixture';calls=[]
        def open_pdf(url,timeout):
            calls.append((url,timeout));return io.BytesIO(data)
        item={'name':'a.pdf','key':'tensile_papers/a.pdf','bytes':len(data),
            'sha256':hashlib.sha256(data).hexdigest(),
            'url':'https://account.r2.cloudflarestorage.com/b/tensile_papers/a.pdf?signature=test'}
        with workspace_temp() as tmp:
            result=R2Client(opener=open_pdf).download({'files':[item]},Path(tmp))
            self.assertEqual((Path(tmp)/'a.pdf').read_bytes(),data)
            self.assertNotIn('url',result[0]);self.assertEqual(len(calls),1)

    def test_paper_parser_uses_injected_exporter_and_converter(self):
        from baseline.code_parsing.parsing import PaperParser
        calls=[]
        class Converter:
            def convert(self,pdf,raises_on_error=False):
                calls.append(('convert',raises_on_error))
                return SimpleNamespace(status=SimpleNamespace(value='success'),errors=[],document='document')
        class Exporter:
            def export(self,document,output,paper_id):
                calls.append(('export',document))
                return {'pages':1,'elements':0,'by_type':{}},[]
        with workspace_temp() as tmp:
            root=Path(tmp);pdf=root/'a.pdf';pdf.write_bytes(b'%PDF-fixture')
            result=PaperParser(Converter(),exporter=Exporter()).parse(pdf,root/'results',{},'models')
            self.assertEqual(result['status'],'completed')
            self.assertEqual(calls,[('convert',False),('export','document')])

    def test_session_uses_injected_command_runner_and_requires_success_marker(self):
        from baseline.code_parsing.colab_run import ColabSession
        calls=[]
        def runner(args,**kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=0,stdout='BASELINE_COMPLETED:run:prepare\n')
        with workspace_temp() as tmp:
            session=ColabSession('owned',Path(tmp),runner=runner)
            session.run_phase('prepare','python3','run')
            self.assertEqual(calls[0][:4],['colab','exec','-s','owned'])
            self.assertTrue((Path(tmp)/'prepare.py').exists())


if __name__=='__main__':unittest.main()
