"""Presentation contract tests against the independent, saved run artifacts."""
import hashlib
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = '20261030T040105Z-4215756a'
RESULT = HERE.parent / 'results' / 'reconciliation_results' / RUN / 'papers/p000001'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


class ArtifactContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = (HERE / 'data/12.js').read_text(encoding='utf-8')
        cls.data = json.loads(script[script.index('(') + 1:script.rindex(')')])
        cls.recon = read(RESULT / 'reconciliation/papers/1/document.json')
        cls.classified = read(RESULT / 'classification/papers/1/document.json')

    def test_current_run_and_all_native_records_preserved(self):
        self.assertEqual(self.data['run'], RUN)
        self.assertEqual(len(self.data['pages']), 13)
        actual = {r['id']: r for r in self.data['records']}
        expected = [r for p in self.recon['pages'] for r in p['records']]
        self.assertEqual(len(actual), 536)
        self.assertEqual(set(actual), {r['id'] for r in expected})
        for r in expected:
            with self.subTest(record=r['id']):
                for key in ('bbox', 'source', 'text', 'score'):
                    self.assertEqual(actual[r['id']].get(key), r.get(key))
                self.assertNotIn('classification', actual[r['id']])

    def test_classifications_and_group_geometry_not_invented(self):
        actual = {r['id']: r for r in self.data['regions']}
        self.assertEqual(len(actual), 293)
        for r in self.classified['regions'] + self.classified['logical_units']:
            self.assertEqual(actual[r['id']]['classification'], r['classification'])
            self.assertEqual(actual[r['id']]['bbox'], r.get('bbox_xyxy'))

    def test_all_saved_routes_steps_and_only_saved_edges(self):
        for key, path in [('baseline', 'capsules/papers/1/document.json'),
                          ('docling', 'operational/papers/1/baseline-docling.json'),
                          ('operational', 'operational/papers/1/document.json')]:
            source = read(RESULT / path)
            actual = self.data['orders'][key]
            self.assertEqual(actual['steps'], source['steps'])
            self.assertEqual(actual['routes'], source['routes'])
            self.assertEqual(actual['relations'], [r for r in source['relations'] if r['type'] == 'next_in_route'])

    def test_images_match_model_input_hashes(self):
        for page, original in zip(self.data['pages'], self.recon['pages']):
            self.assertEqual(page['n'], original['identity']['physical_page'])
            image = HERE / page['image']
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), original['identity']['render_sha256'])

    def test_caption_links_are_saved_group_references(self):
        expected = {(p['identity']['physical_page'], member, g['caption'], g['id'])
                    for p in self.recon['pages'] for g in p['groups']
                    if g.get('caption') for member in g['members']}
        actual = {(a['page'], a['member'], a['caption'], a['group']) for a in self.data['links']}
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
