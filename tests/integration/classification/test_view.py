"""Presentation tests: original PNG bytes, reconciled data only, responsive shell."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from integration.classification.view import build_view


class ViewTests(unittest.TestCase):
    def test_original_images_and_selected_data_without_reclassification(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp); image=root/'render.png';image.write_bytes(b'original-png-fixture')
            baseline=dict(pages=[dict(identity=dict(physical_page=1,width_px=1000,height_px=1400,render_sha256=hashlib.sha256(image.read_bytes()).hexdigest()),render_path=str(image))])
            bp=root/'baseline.json';bp.write_text(json.dumps(baseline))
            classified=dict(schema_version='functional-classification-reconciled/2',classification_scope='reconciled_units_only',
                            source=dict(path=str(bp),sha256=hashlib.sha256(bp.read_bytes()).hexdigest()),regions=[],logical_units=[],evidence_records=[])
            cp=root/'classified.json';cp.write_text(json.dumps(classified))
            result=build_view(cp,root/'view')
            self.assertEqual((root/'view/images/0001.png').read_bytes(),image.read_bytes())
            text=(root/'view/index.html').read_text(encoding='utf-8')
            self.assertIn('data-model',text);self.assertIn('width=device-width',text)
            self.assertNotIn('data-parser',text)
            self.assertIn('@media',text);self.assertEqual(result['pages'],1)
            with self.assertRaises(FileExistsError):build_view(cp,root/'view')

    def test_wrong_source_scope_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp);p=root/'input.json';p.write_text(json.dumps(dict(classification_scope='parser_records')))
            with self.assertRaises(ValueError):build_view(p,root/'view')
            self.assertFalse((root/'view').exists())


if __name__=='__main__':unittest.main()
