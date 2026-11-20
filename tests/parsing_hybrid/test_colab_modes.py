"""Offline contracts for mode profiles and immutable selected parser inputs."""
import hashlib, json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import colab_run
from tests.reconciliation_system.test_hybrid_inputs import fixture, write, digest
from integration.hybrid_inputs import load_run

class ModeTests(unittest.TestCase):
    def test_profile_candidates_are_separate(self):
        root=colab_run.ROOT
        parser=colab_run.candidate(root,profile='parser')
        integrator=colab_run.candidate(root,profile='integrator')
        both=colab_run.candidate(root,profile='both')
        self.assertIn('mineru[torch]',parser);self.assertNotIn('docling==',parser)
        self.assertIn('docling==',integrator);self.assertNotIn('mineru',integrator)
        self.assertIn('mineru[torch]',both);self.assertIn('docling==',both)
        self.assertNotEqual(colab_run.environment_key(root,profile='parser'),colab_run.environment_key(root,profile='both'))

    def test_integration_install_plan_has_no_cuda_or_model_build(self):
        import setup_environment
        plan=setup_environment.plan(Path('/content/new_code/runtime/environment'),profile='integrator')
        self.assertIsNone(plan['cuda_toolkit'])
        self.assertFalse(plan['downloads_model_weights'])
        self.assertNotIn('Detectron2',' '.join(plan['steps']))
        self.assertTrue(Path(plan['requirements']).parts[-2:]==('reconciliation_system','requirements.in'))

    def test_selected_transport_preserves_original_metadata_and_native_files(self):
        from automation.selection import select_run, package_selection
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=fixture(root,count=2)
            for p in run.rglob('render.png'):p.unlink()
            write(run/'configuration.json',{'schema':'parsing-hybrid-runtime/1'})
            write(run/'manifest.json',{'schema':'parsing-hybrid-files/2','outputs':{p.relative_to(run).as_posix():digest(p) for p in run.rglob('*') if p.is_file()}})
            inputs=json.loads((run/'inputs.json').read_bytes());chosen=inputs[1]
            before={str(p):digest(p) for p in run.rglob('*') if p.is_file()}
            selection=select_run(run,[chosen['id']],False)
            self.assertEqual(selection['paper_ids'],[chosen['id']])
            self.assertFalse(any(inputs[0]['id'] in name for name in selection['files']))
            tar=root/'selection.tar.gz';package_selection(run,selection,tar)
            colab_run.extract_transport(tar,root/'remote')
            extracted=root/'remote/parser-source'
            self.assertEqual((extracted/'inputs.json').read_bytes(),(run/'inputs.json').read_bytes())
            self.assertEqual((extracted/'manifest.json').read_bytes(),(run/'manifest.json').read_bytes())
            local_pdfs=root/'downloaded';local_pdfs.mkdir()
            import shutil
            shutil.copy2(chosen['path'],local_pdfs/Path(chosen['path']).name)
            c=load_run(extracted,paper_ids=selection['paper_ids'],pdf_directory=local_pdfs)
            self.assertEqual([x['paper_id'] for x in c['documents']],[chosen['id']])
            self.assertEqual(c['documents'][0]['document_source']['original_path'],chosen['path'])
            self.assertEqual(before,{str(p):digest(p) for p in run.rglob('*') if p.is_file()})
            with self.assertRaises(ValueError):load_run(extracted,paper_ids=[inputs[0]['id']],pdf_directory=local_pdfs)

    def test_integrator_plan_does_not_allocate_session(self):
        with patch.object(colab_run.subprocess,'Popen') as spawn:
            with self.assertRaises(SystemExit):colab_run.main(['--mode','integrator','--plan'])
            spawn.assert_not_called()

class ProfileExecutionTests(unittest.TestCase):
    def test_integrator_install_does_not_install_cuda_build_tools_or_parser(self):
        import setup_environment as setup
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);python=root/'managed-python';python.touch();commands=[]
            class Recorder:
                env={'NASA_ENV_PROFILE':'integrator'}
                def run(self,argv,**kwargs):
                    argv=list(map(str,argv));commands.append(argv)
                    return str(python) if 'find' in argv else ''
            with patch.object(setup,'ROOT',root),patch.object(setup.os,'geteuid',return_value=0,create=True),patch.object(setup,'create_bootstrap',return_value=root/'bootstrap'):
                setup.install(root/'runtime/env',root/'attempt',Recorder(),'24.04')
            text=' '.join(' '.join(c) for c in commands)
            for unnecessary in ('cuda-toolkit','nvcc','build-essential','ninja-build','parse_system/run.py','setup_models.py'):
                self.assertNotIn(unnecessary,text)
            self.assertIn('integration.environment',text)
            self.assertIn('prepare',text)

    def test_integrator_existing_environment_skips_weights_and_gpu(self):
        from automation import colab_worker as worker
        import types,sys
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env=root/'runtime/environment';env.mkdir(parents=True)
            (env/'environment.json').write_text('{}')
            (env/'requirements-candidate.in').write_text('fixture==1\n')
            req=root/'reconciliation_system/requirements.in';req.parent.mkdir();req.write_text('fixture==1\n')
            (root/'runtime/export-bundle.tar.gz').write_bytes(b'cached')
            commands=[]
            class Process:
                stdout=[]
                def wait(self):return 0
            fcntl=types.SimpleNamespace(flock=lambda *a:None,LOCK_EX=1,LOCK_NB=2)
            with patch.dict(sys.modules,fcntl=fcntl),patch.object(worker,'ROOT',root),patch.object(worker.subprocess,'Popen',side_effect=lambda argv,**kw:commands.append(list(map(str,argv))) or Process()),patch.object(worker.subprocess,'check_output') as gpu:
                worker.main(dict(phase='prepare',mode='integrator',run_id='fixture',reuse=False))
            gpu.assert_not_called()
            self.assertEqual(len(commands),1)
            self.assertIn('--check',commands[0]);self.assertEqual(commands[0][-1],'integrator')

class ControllerModeTests(unittest.TestCase):
    def run_controller(self, mode, *, fail_integrator=False):
        import ast, io, tarfile, shutil
        import prepare_papers
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);root=base/'new_code';root.mkdir()
            for name in ('requirements.in','parse_system/parsing/unified/requirements.in','reconciliation_system/requirements.in'):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture==1\n')
            pdfs=base/'papers/SiC_papers';pdfs.mkdir(parents=True)
            (pdfs/'12.pdf').write_bytes(b'%PDF-fixture');(pdfs/'13.pdf').write_bytes(b'%PDF-other')
            if mode=='integrator':
                run=root/'results/parse_results/original';run.mkdir(parents=True)
                inputs=[dict(id=str(n),path='/content/new_code/inputs/sic_papers/'+str(n)+'.pdf',sha256=digest(pdfs/(str(n)+'.pdf')),page_count=1) for n in (12,13)]
                write(run/'inputs.json',inputs);write(run/'configuration.json',{})
                write(run/'status.json',dict(status='completed'))
                for n in (12,13):write(run/'results'/str(n)/'1/mineru/middle-native.json',{'original':n})
                write(run/'manifest.json',dict(schema='parsing-hybrid-files/2',outputs={p.relative_to(run).as_posix():digest(p) for p in run.rglob('*') if p.is_file()}))
            commands=[];phases=[];bundle=b'fake verified environment';request_names=[]
            class Process:
                stdout=[]
                def wait(self):return 0
            def popen(argv,**kw):
                argv=list(map(str,argv));commands.append(argv)
                if argv[1]=='exec' and '-f' in argv:
                    tree=ast.parse(Path(argv[argv.index('-f')+1]).read_text())
                    for node in ast.walk(tree):
                        if isinstance(node,ast.Assign) and isinstance(node.value,ast.List) and len(node.value.elts)==2 and isinstance(node.value.elts[0],ast.Constant) and node.value.elts[0].value=='driver':
                            phases.append(json.loads(node.value.elts[1].value))
                if argv[1]=='download':
                    target=Path(argv[-1]);name=argv[-2]
                    if name.endswith('export-bundle.tar.gz'):target.write_bytes(bundle)
                    elif name.endswith('export-bundle.tar.gz.sha256'):target.write_text(hashlib.sha256(bundle).hexdigest())
                    elif name.endswith('-transport.tar.gz'):
                        kind='integration' if 'integration-transport' in name else 'parser'
                        status=json.dumps(dict(status='failed' if fail_integrator and kind=='integration' else 'completed',metrics={})).encode()
                        manifest=json.dumps(dict(schema='hybrid-integration-files/1' if kind=='integration' else 'parsing-hybrid-files/2',outputs={'status.json':hashlib.sha256(status).hexdigest()})).encode()
                        with tarfile.open(target,'w:gz') as archive:
                            for n,raw in [('status.json',status),('manifest.json',manifest)]:
                                info=tarfile.TarInfo(kind+'-result/'+n);info.size=len(raw);archive.addfile(info,io.BytesIO(raw))
                    else:target.write_text(digest(target.with_name(target.name.replace('.sha256','.tar.gz'))))
                process=Process()
                if argv[1]=='exec' and '-f' in argv:
                    for node in ast.walk(ast.parse(Path(argv[argv.index('-f')+1]).read_text())):
                        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='print' and node.args and isinstance(node.args[0],ast.Constant) and str(node.args[0].value).startswith('SIC_PHASE_COMPLETED:'):process.stdout=[node.args[0].value+'\n']
                return process
            def sign(source,names,settings,output):request_names.append(names);output.write_text('{}')
            args=['--mode',mode,'--papers','12']+(['--parse-run','original'] if mode=='integrator' else [])
            with patch.object(colab_run,'ROOT',root),patch.object(colab_run,'find_bundle',return_value=None),patch.object(colab_run,'inspect_bundle'),patch.object(colab_run.sys,'platform','linux'),patch.object(colab_run.shutil,'which',return_value='colab'),patch.object(colab_run.subprocess,'Popen',side_effect=popen),patch.object(prepare_papers,'read_settings',return_value={}),patch.object(prepare_papers,'sign_request',side_effect=sign):
                if fail_integrator:
                    with self.assertRaisesRegex(ValueError,'incomplete'):colab_run.main(args)
                else:self.assertEqual(colab_run.main(args),0)
            self.assertEqual([p['phase'] for p in phases],['prepare']+(['parse'] if mode in ('parser','both') else [])+(['integrate'] if mode in ('integrator','both') else []))
            self.assertTrue(all(p['mode']==mode for p in phases))
            self.assertEqual(request_names,[['12.pdf']])
            self.assertEqual(sum(c[1]=='stop' for c in commands),0 if fail_integrator else 1)
            if mode=='integrator':
                selection=phases[-1]['selection'];self.assertEqual(selection['paper_ids'],['12'])
                self.assertFalse(any('/13/' in n for n in selection['files']))
                self.assertFalse(any(c[1]=='download' and 'results-transport' in c[-2] for c in commands))
            if mode=='both':self.assertTrue(list((root/'results/parse_results').glob('*/manifest.json')))
            if fail_integrator:
                state=json.loads(next((root/'runtime/colab-attempts').glob('*/status.json')).read_text())
                self.assertTrue(state['parser_backup_verified']);self.assertFalse(state['session_closed'])

    def test_integrator_selected_transport_and_r2_only(self):self.run_controller('integrator')
    def test_both_integrates_after_verified_parser_backup(self):self.run_controller('both')
    def test_failure_keeps_parser_backup_and_session_for_review(self):self.run_controller('both',fail_integrator=True)

class CachedBuildTests(unittest.TestCase):
    def test_parser_build_reuse_skips_compiler_and_toolkit(self):
        import setup_environment as setup
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);python=root/'managed-python';python.touch();commands=[]
            class Recorder:
                env={'NASA_ENV_PROFILE':'parser'}
                def run(self,argv,**kwargs):
                    argv=list(map(str,argv));commands.append(argv)
                    return str(python) if 'find' in argv else ''
            with patch.object(setup,'ROOT',root),patch.object(setup.os,'geteuid',return_value=0,create=True),patch.object(setup,'create_bootstrap',return_value=root/'bootstrap'):
                setup.install(root/'runtime/env',root/'attempt',Recorder(),'24.04',build_bundle=root/'verified-bundle')
            text=' '.join(' '.join(c) for c in commands)
            self.assertNotIn('cuda-toolkit',text);self.assertNotIn('build-essential',text)
            self.assertIn('--build-bundle',text)

class SelectionAndWorkerTests(unittest.TestCase):
    def make_compact(self,root,count=3):
        run=fixture(root,count=count)
        for p in run.rglob('render.png'):p.unlink()
        write(run/'configuration.json',{})
        write(run/'manifest.json',dict(schema='parsing-hybrid-files/2',outputs={p.relative_to(run).as_posix():digest(p) for p in run.rglob('*') if p.is_file()}))
        return run

    def test_one_group_all_and_unknown_selection(self):
        from automation.selection import select_run
        with tempfile.TemporaryDirectory() as d:
            run=self.make_compact(Path(d));inputs=json.loads((run/'inputs.json').read_text())
            group=select_run(run,[inputs[2]['id'],inputs[0]['id']],False)
            self.assertEqual(group['paper_ids'],[inputs[2]['id'],inputs[0]['id']])
            self.assertFalse(any(inputs[1]['id'] in name for name in group['files']))
            all_papers=select_run(run,[],True)
            self.assertEqual(set(all_papers['files']),set(json.loads((run/'manifest.json').read_text())['outputs']))
            for names in (['unknown'],[inputs[0]['id'],inputs[0]['id']]):
                with self.assertRaises(ValueError):select_run(run,names,False)
            native=next(run.rglob('middle-native.json'));native.write_text('{}')
            with self.assertRaisesRegex(ValueError,'hash differs'):select_run(run,[],True)

    def test_integrate_worker_uses_selected_source_and_r2_hashes_without_parser(self):
        from automation import colab_worker as worker
        from automation.selection import select_run, package_selection
        import sys,types,tarfile
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);root=base/'new_code';root.mkdir();run=self.make_compact(base)
            inputs=json.loads((run/'inputs.json').read_text());selection=select_run(run,[inputs[0]['id']],False)
            package_selection(run,selection,base/'parser-source.tar.gz')
            # Synthetic request contains only the selected identity, no network URL.
            paper=selection['papers'][0]
            write(base/'papers-request.json',dict(files=[dict(name=paper['name'],sha256=paper['sha256'])]))
            env=root/'runtime/environment';env.mkdir(parents=True);(env/'environment.json').write_text('{}')
            commands=[]
            class Process:
                stdout=[]
                def wait(self):return 0
            def popen(argv,**kw):
                argv=list(map(str,argv));commands.append(argv)
                if 'prepare_papers.py' in argv:
                    folder=root/'inputs/sic_papers';folder.mkdir(parents=True)
                    (folder/paper['name']).write_bytes(Path(inputs[0]['path']).read_bytes())
                    write(folder/'r2-download-receipt.json',{})
                if 'reconciliation_system/run.py' in argv:
                    source=Path(argv[argv.index('--parse-run')+1]);chosen=argv[argv.index('--paper-id')+1]
                    c=load_run(source,paper_ids=[chosen],pdf_directory=root/'inputs/sic_papers')
                    self.assertEqual(len(c['documents']),1)
                    write(root/'results/reconciliation_results/test/status.json',{'status':'completed'})
                return Process()
            fcntl=types.SimpleNamespace(flock=lambda *a:None,LOCK_EX=1,LOCK_NB=2)
            with patch.dict(sys.modules,fcntl=fcntl),patch.object(worker,'ROOT',root),patch.object(worker.subprocess,'Popen',side_effect=popen):
                worker.main(dict(phase='integrate',mode='integrator',run_id='test',papers=[paper['name']],workers=2,selection=selection,source_sha256=digest(base/'parser-source.tar.gz')))
            self.assertEqual(len(commands),2)
            self.assertFalse((base/'papers-request.json').exists())
            self.assertNotIn('parse_system/run.py',' '.join(' '.join(c) for c in commands))
            with tarfile.open(base/'integration-transport.tar.gz') as saved:self.assertIn('integration-result/status.json',saved.getnames())

    def test_adapter_selects_one_paper_from_complete_or_reduced_inventory(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=self.make_compact(root,count=2)
            inputs=json.loads((run/'inputs.json').read_text())
            c=load_run(run,paper_ids=[inputs[0]['id']],pdf_directory=root)
            self.assertEqual([x['paper_id'] for x in c['documents']],[inputs[0]['id']])
            self.assertFalse(any(inputs[1]['id'] in p for p in c['source_inputs']))
            (run/'unlisted.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'inventory differs'):load_run(run,paper_ids=[inputs[0]['id']],pdf_directory=root)

class ExportCollisionTests(unittest.TestCase):
    def test_build_input_and_new_export_have_separate_directories(self):
        from automation import colab_worker
        import inspect
        self.assertNotEqual(colab_worker.bundle_input_root(Path('/runtime'),'export-bundle'),Path('/runtime/export-bundle'))

    def test_cli_exit_zero_is_not_remote_success(self):
        marker='SIC_PHASE_COMPLETED:test:prepare'
        for output in ('', 'RuntimeError: export failed\n', 'prefix '+marker):
            with self.assertRaisesRegex(RuntimeError,'did not confirm'):colab_run.require_remote_success(output,marker)
        colab_run.require_remote_success('logs\n'+marker+'\n',marker)

    def test_cached_build_extraction_does_not_occupy_export_destination(self):
        from automation import colab_worker as worker
        import io,sys,tarfile,types
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'new_code';root.mkdir();runtime=root/'runtime';runtime.mkdir()
            archive=root.parent/'environment-bundle.tar.gz'
            with tarfile.open(archive,'w:gz') as tar:
                raw=b'{}';info=tarfile.TarInfo('export-bundle/bundle.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
            commands=[]
            class Process:
                stdout=[]
                def wait(self):return 0
            def popen(argv,**kw):
                argv=list(map(str,argv));commands.append(argv)
                if '--reuse-build-bundle' in argv:
                    location=Path(argv[argv.index('--reuse-build-bundle')+1])
                    self.assertTrue((location/'bundle.json').is_file())
                    self.assertEqual(location.parent,runtime/'bundle-inputs')
                if '--export-bundle' in argv:
                    output=Path(argv[argv.index('--export-bundle')+1])
                    self.assertFalse(output.exists())
                return Process()
            fcntl=types.SimpleNamespace(flock=lambda *a:None,LOCK_EX=1,LOCK_NB=2)
            with patch.dict(sys.modules,fcntl=fcntl),patch.object(worker,'ROOT',root),patch.object(worker.subprocess,'Popen',side_effect=popen),patch.object(worker.subprocess,'check_output',return_value='A100'):
                worker.main(dict(phase='prepare',mode='parser',run_id='test',reuse=False,build_only=True,bundle_root='export-bundle',bundle_sha256=digest(archive)))
            self.assertEqual(len(commands),3)
