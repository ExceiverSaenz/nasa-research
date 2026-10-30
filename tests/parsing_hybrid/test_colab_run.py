import tempfile,unittest
from pathlib import Path
import colab_run
class ColabRunTests(unittest.TestCase):
 def test_selection(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   for n in ('12.pdf','1.pdf','3.pdf'):(p/n).write_bytes(b'%PDF-fixture')
   self.assertEqual(colab_run.select_papers(p,['12','3.pdf'],False),['12.pdf','3.pdf'])
   self.assertEqual(set(colab_run.select_papers(p,[],True)),{'1.pdf','3.pdf','12.pdf'})
   for names in (['../12'],['99'],['12','12.pdf']):
    with self.assertRaises(ValueError):colab_run.select_papers(p,names,False)
 def test_code_snapshot_excludes_runtime_and_results(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);root=p/'code';root.mkdir()
   for name in ('run.py','requirements.in','runtime/secret','results/result','inputs/12.pdf','x/__pycache__/x.pyc'):
    f=root/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('fixture')
   files=colab_run.source_files(root)
   self.assertEqual({f.relative_to(root).as_posix() for f in files},{'run.py','requirements.in'})
 def test_environment_key_tracks_included_requirements(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'requirements.in').write_text('-r nested.in\n');(root/'nested.in').write_text('one==1\n')
   first=colab_run.environment_key(root)
   (root/'nested.in').write_text('one==2\n')
   self.assertNotEqual(first,colab_run.environment_key(root))

class ControllerTests(unittest.TestCase):
 def test_full_controller_then_reuse_without_real_colab(self):
  import hashlib,io,json,tarfile
  from unittest.mock import patch
  import prepare_papers
  with tempfile.TemporaryDirectory() as d:
   base=Path(d);root=base/'new_code';root.mkdir();(root/'requirements.in').write_text('fixture==1\n')
   req=root/'parse_system/parsing/unified/requirements.in';req.parent.mkdir(parents=True);req.write_text('fixture==1\n')
   pdfs=base/'papers/SiC_papers';pdfs.mkdir(parents=True);(pdfs/'12.pdf').write_bytes(b'%PDF-fixture')
   bundle=b'bundle transport fixture';commands=[]
   class Process:
    stdout=[]
    def wait(self):return 0
   def popen(argv,**kwargs):
    args=list(map(str,argv));commands.append(args)
    if args[1]=='download':
     destination=Path(args[-1]);remote=args[-2]
     if remote.endswith('export-bundle.tar.gz'):destination.write_bytes(bundle)
     elif remote.endswith('export-bundle.tar.gz.sha256'):destination.write_text(hashlib.sha256(bundle).hexdigest()+'  export-bundle.tar.gz')
     elif remote.endswith('results-transport.tar.gz'):
      status=json.dumps(dict(status='completed',metrics={'completed_pages':1})).encode()
      manifest=json.dumps(dict(schema='parsing-hybrid-files/2',outputs={'status.json':hashlib.sha256(status).hexdigest()})).encode()
      with tarfile.open(destination,'w:gz') as archive:
       for name,raw in [('parser-result/status.json',status),('parser-result/manifest.json',manifest)]:
        info=tarfile.TarInfo(name);info.size=len(raw);archive.addfile(info,io.BytesIO(raw))
     else:destination.write_text(colab_run.digest(destination.with_name('results-transport.tar.gz')))
    process=Process()
    if args[1]=='exec' and '-f' in args:
     import ast
     script=Path(args[args.index('-f')+1]).read_text()
     for node in ast.walk(ast.parse(script)):
      if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='print' and node.args and isinstance(node.args[0],ast.Constant) and str(node.args[0].value).startswith('SIC_PHASE_COMPLETED:'):process.stdout=[node.args[0].value+'\n']
    return process
   def sign(source,names,settings,output):output.write_text('{}')
   def find(root,key,**kwargs):
    path=root/'runtime/colab-bundles'/(key+'.tar.gz')
    return dict(path=path,sha256=colab_run.digest(path),bundle_root='export-bundle') if path.exists() else None
   with patch.object(colab_run,'inspect_bundle'),patch.object(colab_run,'find_bundle',side_effect=find),patch.object(colab_run,'ROOT',root),patch.object(colab_run.sys,'platform','linux'),patch.object(colab_run.shutil,'which',return_value='colab'),patch.object(colab_run.subprocess,'Popen',side_effect=popen),patch.object(prepare_papers,'read_settings',return_value={}),patch.object(prepare_papers,'sign_request',side_effect=sign):
    self.assertEqual(colab_run.main(['--papers','12']),0)
    self.assertEqual(colab_run.main(['--papers','12']),0)
   self.assertFalse((root/'results/colab_runs').exists())
   self.assertEqual(len(list((root/'results/parse_results').glob('*/manifest.json'))),2)
   self.assertEqual(sum(a[1]=='new' for a in commands),2)
   self.assertEqual(sum(a[1]=='stop' for a in commands),2)
   self.assertEqual(sum(a[1]=='upload' and a[-1]=='/content/environment-bundle.tar.gz' for a in commands),1)
   self.assertEqual(sum(a[1]=='download' and a[-2].endswith('export-bundle.tar.gz') for a in commands),1)

class IntegrityTests(unittest.TestCase):
 def test_result_tamper_is_rejected(self):
  import hashlib,json
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'status.json';p.write_text('{"status":"completed"}')
   (root/'manifest.json').write_text(json.dumps(dict(schema='parsing-hybrid-files/2',outputs={'status.json':colab_run.digest(p)})))
   self.assertEqual(colab_run.verify_result(root)['status'],'completed')
   p.write_text('{}')
   with self.assertRaisesRegex(ValueError,'hash'):colab_run.verify_result(root)
 def test_tar_traversal_rejected(self):
  import io,tarfile
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);archive=root/'unsafe.tar.gz'
   with tarfile.open(archive,'w:gz') as tar:
    info=tarfile.TarInfo('../outside');info.size=1;tar.addfile(info,io.BytesIO(b'x'))
   with self.assertRaises(ValueError):colab_run.extract_transport(archive,root/'output')
 def test_dependency_removal_changes_environment_key(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'requirements.in';p.write_text('one==1\ntwo==2\n')
   key=colab_run.environment_key(root);p.write_text('one==1\n')
   self.assertNotEqual(key,colab_run.environment_key(root))

class BundleDiscoveryTests(unittest.TestCase):
 def test_finds_existing_bundle_without_keyed_cache(self):
  root=colab_run.ROOT
  choice=colab_run.find_bundle(root,'not-a-cache-key')
  self.assertIsNotNone(choice)
  self.assertTrue(choice['path'].is_file())
 def test_changed_requirements_reject_existing_bundles(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'requirements.in').write_text('changed-dependency==999\n')
   folder=root/'runtime/environment-bundles';folder.mkdir(parents=True)
   actual=colab_run.ROOT/'runtime/environment-bundles/a100-v2.tar.gz'
   import shutil
   shutil.copy2(actual,folder/actual.name)
   shutil.copy2(actual.with_name(actual.name+'.sha256'),folder/(actual.name+'.sha256'))
   self.assertIsNone(colab_run.find_bundle(root,'new-key'))

class WorkerPrecheckTests(unittest.TestCase):
 def test_existing_environment_and_weights_are_checked_not_reinstalled(self):
  import importlib.util,json,sys,types,hashlib
  from unittest.mock import patch
  spec=importlib.util.spec_from_file_location('worker',colab_run.ROOT/'automation/colab_worker.py')
  worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);runtime=root/'runtime';env=runtime/'environment';env.mkdir(parents=True)
   (root/'requirements.in').write_text('fixture==1\n')
   (env/'requirements-candidate.in').write_text('fixture==1\n')
   (env/'environment.json').write_text('{}')
   (runtime/'export-bundle.tar.gz').write_bytes(b'existing')
   config=dict(env_manifest=str(env/'environment.json'),model_dirs={})
   for name in ('layoutlmv3','table_transformer','mineru'):
    models=runtime/name;models.mkdir();(models/'weights').write_bytes(b'fixture')
    config['model_dirs'][name]=str(models)
    manifests=root/'model_manifests';manifests.mkdir(exist_ok=True)
    (manifests/(name+'.json')).write_text(json.dumps(dict(files={'weights':dict(bytes=7,sha256=hashlib.sha256(b'fixture').hexdigest())})))
   folder=runtime/'models-config';folder.mkdir();(folder/'hybrid-runtime.json').write_text(json.dumps(config))
   commands=[]
   class Process:
    stdout=[]
    def wait(self):return 0
   def popen(args,**kw):commands.append(list(map(str,args)));return Process()
   fcntl=types.SimpleNamespace(flock=lambda *a:None,LOCK_EX=1,LOCK_NB=2)
   with patch.dict(sys.modules,fcntl=fcntl),patch.object(worker,'ROOT',root),patch.object(worker.subprocess,'Popen',side_effect=popen),patch.object(worker.subprocess,'check_output',return_value='A100'):
    worker.main(dict(phase='prepare',run_id='fixture',reuse=False))
   self.assertEqual(len(commands),1)
   self.assertIn('--check',commands[0])
   self.assertNotIn('setup_models.py',' '.join(commands[0]))

class HistoricalBundleTests(unittest.TestCase):
 def test_original_a100_v2_is_validated_with_its_original_root(self):
  path=colab_run.ROOT/'runtime/environment-bundles/a100-v2.tar.gz'
  if not path.exists():self.skipTest('Historical bundle not installed')
  choice=colab_run.inspect_bundle(path,colab_run.ROOT)
  self.assertEqual(choice['bundle_root'],'a100-v2')
 def test_tampered_archive_is_rejected_before_session(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'bad.tar.gz';path.write_bytes(b'changed')
   path.with_name(path.name+'.sha256').write_text('0'*64)
   with self.assertRaisesRegex(ValueError,'SHA256'):colab_run.inspect_bundle(path,colab_run.ROOT)

