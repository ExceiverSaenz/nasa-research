import os,pathlib,shutil,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
class DetachedTests(unittest.TestCase):
 def test_both_cli_entries_work_in_detached_copy_with_isolated_python(self):
  with tempfile.TemporaryDirectory() as folder:
   copy=pathlib.Path(folder)/'portable'
   shutil.copytree(ROOT/'new_code',copy,ignore=shutil.ignore_patterns('*.pth','__pycache__','results'))
   for system in ('parse_system','reconciliation_system'):
    result=subprocess.run([sys.executable,'-I','-B',str(copy/system/'run.py'),'--help'],cwd=folder,capture_output=True,text=True)
    self.assertEqual(result.returncode,0,result.stderr)
   self.assertFalse((copy.parent/'code').exists())
   self.assertFalse((copy.parent/'history').exists())
