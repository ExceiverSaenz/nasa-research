import pathlib, subprocess, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'new_code/reconciliation_system'
class MigrationTests(unittest.TestCase):
    def test_canonical_modules_import_without_project_compatibility(self):
        script = "import sys;sys.path.insert(0,"+repr(str(PACKAGE))+ ");import integration.classification.reconciled,integration.reading_order.engine,integration.operational.structure;assert 'compatibility' not in sys.modules"
        result = subprocess.run([sys.executable, '-I', '-B', '-c', script], capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
    def test_generic_paper_ids_are_safe_and_preserve_integer_baseline(self):
        sys.path.insert(0,str(PACKAGE))
        from integration.identifiers import valid_paper_id
        for value in [1,15,'some-paper-'+ 'a'*64]: self.assertTrue(valid_paper_id(value))
        for value in [True,0,-1,'../escape','a/b','a\\b','.','..','']: self.assertFalse(valid_paper_id(value))
