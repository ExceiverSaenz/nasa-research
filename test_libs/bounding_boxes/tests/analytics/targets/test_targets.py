
import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import unittest
from analytics.targets.targets import family, assess, pair_agreement

class TargetTests(unittest.TestCase):
    def test_synonyms_are_not_errors(self):
        self.assertEqual(family('picture'),family('chart'))
        self.assertEqual(family('section_header'),family('paragraph_title'))
    def test_directional_title_errors(self):
        self.assertEqual(assess('heading',['text'])['error'],'heading_to_text')
        self.assertEqual(assess('text',['section_header'])['error'],'text_to_heading')
    def test_conflicting_predictions_not_best_label_selected(self):
        self.assertEqual(assess('text',['text','section_header'])['status'],'contradictory')
    def test_reference_list_compatible_and_margin_coarse(self):
        self.assertEqual(assess('reference',['list_item'])['status'],'coarse_usable')
        self.assertEqual(assess('visual',['header'])['status'],'coarse_usable')
    def test_no_spatial_match_is_not_tag_error(self):
        self.assertEqual(assess('caption',[])['status'],'no_own_correspondence')
    def test_unmapped_excluded_not_counted_as_agreement(self):
        self.assertEqual(pair_agreement(['unknown'],['unknown']),None)
    def test_metadata_and_author_affiliation_are_not_section_titles(self):
        self.assertEqual(assess('metadata',['text'])['status'],'coarse_usable')
        self.assertEqual(assess('author',['list_item'])['status'],'coarse_usable')
        self.assertEqual(assess('metadata',['section_header'])['status'],'wrong')
    def test_affiliation_has_compatible_structural_labels(self):
        self.assertEqual(assess('author',['footnote','list_item'],subtype='affiliation')['status'],'coarse_usable')

if __name__=='__main__':unittest.main()
