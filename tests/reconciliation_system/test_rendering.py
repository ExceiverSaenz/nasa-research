import tempfile,unittest,json,sys,types
from unittest.mock import patch
from pathlib import Path
class RegenerationTests(unittest.TestCase):
 def test_exact_regeneration_and_changed_pdf_rejected(self):
  import fitz, numpy, pypdfium2, PIL.Image
  from parsing.unified.inputs import collect_papers,render_page_job
  from integration.rendering import regenerate_png
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pdf=root/'paper.pdf'
   with fitz.open() as doc:
    doc.new_page(width=72,height=36).insert_text((3,12),'Fixture');doc.save(pdf)
   paper=collect_papers([pdf])[0]
   # Local runtime lacks pypdf; fixture has one standard UserUnit page.
   with patch.dict(sys.modules, pypdf=types.SimpleNamespace(PdfReader=lambda path: types.SimpleNamespace(pages=[{}]))):
    job=render_page_job(paper,1,root/'stage')
    self.assertEqual(regenerate_png(job['identity'],pdf),Path(job['render_path']).read_bytes())
   pdf.write_bytes(pdf.read_bytes()+b'changed')
   with patch.dict(sys.modules, pypdf=types.SimpleNamespace(PdfReader=lambda path: None)),self.assertRaisesRegex(ValueError,'PDF identity'):regenerate_png(job['identity'],pdf)

