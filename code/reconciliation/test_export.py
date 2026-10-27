import json
from pathlib import Path
import tempfile
import unittest
from reconciliation.export import export, render_html, encoded
from reconciliation.inputs import load_evaluation, digest
from reconciliation.engine import reconcile
from reconciliation.test_inputs import EVAL, ROOT
from reconciliation.test_engine import multi


class ExportTests(unittest.TestCase):
    def test_nonfinite_preserved_as_explicit_tag(self):
        p=multi();p['records'][0]['bbox'][0]=float('nan')
        value=json.loads(encoded(reconcile(p)))
        self.assertEqual(value['records'][0]['bbox'][0],{'$nonfinite':'nan'})
        self.assertIn('invalid_geometry',value['incidents'])
    def test_html_escaping_and_four_views(self):
        p=multi();p['records'][2]['text']='</script><script>alert(1)</script>'
        out=reconcile(p)
        html=render_html({'pages':[out]}, {1:'data:image/png;base64,AA=='})
        self.assertNotIn('</script><script>alert',html)
        self.assertIn('Automática',html);self.assertIn('MinerU',html)
        self.assertIn('LayoutLMv3',html);self.assertIn('TATR',html)

    def test_immutable_export_and_all_sources(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            dest=Path(folder)/'out'
            result=export(EVAL,dest)
            first=(dest/'document.json').read_bytes()
            export(EVAL,dest)
            self.assertEqual(first,(dest/'document.json').read_bytes())
            self.assertEqual(len(result['pages']),13)
            audit=json.loads((dest/'manifest.json').read_bytes())
            self.assertTrue(all(digest(Path(p).read_bytes())==sha for p,sha in audit['source_inputs'].items()))
            (dest/'document.json').write_text('corrupted')
            with self.assertRaises(ValueError):export(EVAL,dest)


if __name__=='__main__':unittest.main()
