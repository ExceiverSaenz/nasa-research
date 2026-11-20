import hashlib,json,tempfile,unittest
from pathlib import Path
from tests.reconciliation_system.test_hybrid_inputs import fixture,write,digest
from integration.hybrid_inputs import load_run
class CompactInputTests(unittest.TestCase):
 def make(self,root):
  run=fixture(root)
  for p in run.rglob('render.png'):p.unlink()
  write(run/'configuration.json',dict(schema='parsing-hybrid-runtime/1'))
  write(run/'manifest.json',dict(schema='parsing-hybrid-files/2',outputs={p.relative_to(run).as_posix():digest(p) for p in run.rglob('*') if p.is_file()}))
  run.with_name(run.name+'.zip').unlink();run.with_name(run.name+'.zip.sha256').unlink()
  return run
 def test_renderless_manifest_and_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.make(Path(d));c=load_run(run)
   self.assertIsNone(c['documents'][0]['pages'][0]['render_path'])
   p=next(run.rglob('regions.json'));p.write_text('{}')
   with self.assertRaises(ValueError):load_run(run)
 def test_unlisted_file_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.make(Path(d));(run/'extra.json').write_text('{}')
   with self.assertRaises(ValueError):load_run(run)
