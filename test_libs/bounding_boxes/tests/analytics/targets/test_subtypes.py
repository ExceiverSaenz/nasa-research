
import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import unittest
from analytics.targets.subtypes import subtype_check

class SubtypeTests(unittest.TestCase):
    def test_figure_caption_is_not_table_caption(self):
        self.assertEqual(subtype_check('figure_caption',['table_caption']),'figure_as_table_caption')
        self.assertEqual(subtype_check('figure_caption',['caption']),'generic_or_compatible')
    def test_heading_and_number_subtypes(self):
        self.assertEqual(subtype_check('document_heading',['section_header']),'document_as_section')
        self.assertEqual(subtype_check('chapter_marker',['page_number']),'chapter_as_page_number')

if __name__=='__main__':unittest.main()
