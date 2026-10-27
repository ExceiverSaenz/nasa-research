import unittest
import json
import tempfile
from pathlib import Path
from PIL import Image
from reading_order.export import write,digest
from .test_grobid_core import baseline,evidence
from .grobid_align import align_tei
from .grobid_reconcile import integrate_grobid,load_mapping
from .grobid_view import build_model,build_view


class ViewTests(unittest.TestCase):
    def test_fixture_export_embeds_comparison_and_copies_original_bytes(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t:
            r=Path(t).resolve();B=baseline();ev=evidence();C=integrate_grobid(B,ev,align_tei(ev,B),load_mapping());bp=r/'B/document.json';cp=r/'C/document.json';write(bp,B);write(cp,C)
            img=r/'source.png';Image.new('RGB',(1000,1000),'white').save(img);catalog=r/'catalog.json';write(catalog,dict(pages=[dict(identity=dict(physical_page=1,width_px=1000,height_px=1000,render_sha256=digest(img)),render_path=str(img))]))
            write(bp.parent/'manifest.json',dict(outputs={'document.json':digest(bp)},sources={str(catalog):digest(catalog)}));write(cp.parent/'manifest.json',dict(outputs={'document.json':digest(cp)},sources={str(bp):digest(bp)}))
            v=build_view(bp,cp,catalog,r/'view');self.assertEqual(v['images_copied'],1);self.assertEqual((r/'view/images/0001.png').read_bytes(),img.read_bytes())
            h=(r/'view/index.html').read_text(encoding='utf-8');self.assertIn('width=device-width',h);self.assertNotIn('__DATA__',h)
            with self.assertRaises(FileExistsError):build_view(bp,cp,catalog,r/'view')
    def test_model_exposes_B_C_conflicts_and_unlocated(self):
        B=baseline();e=evidence();C=integrate_grobid(B,e,align_tei(e,B),load_mapping());m=build_model(B,C,[])
        self.assertEqual(m['units'][0]['comparison']['dimensions']['document_role']['C_decision']['operational_proposal'],'body_paragraph');self.assertEqual(m['paper'],B['document'])


if __name__=='__main__':unittest.main()
