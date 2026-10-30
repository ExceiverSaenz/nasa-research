import pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'new_code/parse_system'))
from parsing.unified import environment
class SharedRequirementsTests(unittest.TestCase):
 def test_combined_candidate_contains_both_systems_before_lock(self):
  content=environment.candidate_text(ROOT/'new_code/requirements.in')
  for pin in ['mineru[torch]==4.0.12','PyMuPDF==1.27.2.3','docling==2.123.1','docling-core==2.92.0']:
   self.assertIn(pin,content)
  self.assertRegex(content,r'(?m)^torch @ https://download-r2\.pytorch\.org/whl/cu126/torch-2\.7\.1%2Bcu126[^\s]+#sha256=[0-9a-f]{64}$')
  self.assertNotIn('-r ',content)
 def test_cyclic_candidate_includes_rejected(self):
  with tempfile.TemporaryDirectory() as folder:
   path=pathlib.Path(folder)/'requirements.in';path.write_text('-r requirements.in')
   with self.assertRaisesRegex(ValueError,'cycle'):environment.candidate_text(path)
