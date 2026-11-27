"""Tests of the result files a run writes (service/extraction/results.py; ADR-027): AC-X07 (files), AC-X15, BR-X11,
BR-X12. The files must pass the existing ingest and open in Review."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import schemas  # noqa: E402
from value_review.ingest import build_original  # noqa: E402
from value_review.service import workspace  # noqa: E402
from value_review.service.extraction import results  # noqa: E402
from value_review.tests.fake_provider import answer_for  # noqa: E402
from value_review.tests.test_extraction_runs import API, ExtractionBase  # noqa: E402
from value_review.tests.text_pdf import make_text_pdf  # noqa: E402

RUN = {'id': 'r_0000abcd', 'model': 'anthropic:claude-opus-5-5'}
LINES = [['Table 2. Tensile results', 'Material: FeCrAl', 'Yield strength 710 ± 25 MPa'], ['Discussion', 'Ultimate strength 845 MPa']]


class Mapping(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = Path(self.tmp.name) / '7.pdf'
        make_text_pdf(self.pdf, LINES)

    def tearDown(self):
        self.tmp.cleanup()

    def test_boxes_are_found_from_the_quotes(self):   # AC-X15, BR-X12
        answer = answer_for('x')
        answer['values'].append({'field_id': 'test_temperature', 'record_ids': ['r9'], 'value': '845', 'unit': '', 'page': 9,
                                 'quote': 'Ultimate strength 845', 'flags': [], 'notes': ''})
        result = results.to_result(answer, RUN, '7', self.pdf, 'tensile')
        ev = {e['evidence_id']: e for e in result['evidence']}
        regions = {g['region_id']: g for g in result['regions']}
        self.assertEqual((regions['g1']['page_number'], ev['e1']['location_quality']), (1, 'exact'))   # "Yield strength 710"
        x0, y0, x1, y1 = ev['e1']['bbox']
        self.assertTrue(0.1 < x0 < x1 < 0.6 and 0.1 < y0 < y1 < 0.2, ev['e1']['bbox'])   # third line from the top, left side
        self.assertEqual((ev['e2']['bbox'], ev['e2']['location_quality'], regions['g2']['page_number']), (None, 'not_found', 1))
        self.assertEqual((regions['g4']['page_number'], ev['e4']['location_quality']), (2, 'other_page'))   # page 9 does not exist
        obs = {o['observation_id']: o for o in result['observations']}
        self.assertEqual((obs['o1']['value_as_reported'], obs['o1']['unit_as_reported'], obs['o1']['record_ids'], obs['o1']['assignment_status']),
                         ('710 ± 25', 'MPa', ['r1'], 'established'))
        self.assertEqual((obs['o3']['record_ids'], obs['o4']['record_ids'], obs['o4']['assignment_status']), (['r1', 'r2'], [], 'unassigned'))
        self.assertEqual(result['feature_columns'], ['yield_strength', 'ultimate_tensile_strength', 'material', 'test_temperature'])
        self.assertEqual((result['mode'], result['run_id'], result['paper']['page_count']), ('api_pdf', RUN['id'], 2))

    def test_the_file_passes_the_ingest(self):   # AC-X07 (files)
        folder = Path(self.tmp.name) / 'results' / 'tensile' / 'run'
        results.write_result(folder, '7', results.to_result(answer_for('x'), RUN, '7', self.pdf, 'tensile'))
        original = build_original(folder / '7-pdf_with_feature_guide.json', self.pdf)
        self.assertEqual(schemas.errors('original', original), [])
        self.assertEqual(original['issues'], [])
        by_id = {o['observation_id']: o for o in original['observations']}
        self.assertEqual((by_id['o1']['evidence'][0]['page'], by_id['o1']['needs_check']), (1, False))
        self.assertTrue(by_id['o1']['evidence'][0]['bbox'])
        self.assertIsNone(by_id['o2']['evidence'][0]['bbox'])

    def test_the_manifest_is_checked(self):
        folder = Path(self.tmp.name) / 'out'
        manifest = {'schema': 'value-review-run-manifest/1', 'run_id': RUN['id'], 'name': 'Run', 'set': 'tensile',
                    'schema_ref': {'id': 'tensile-properties', 'version': 1}, 'schema_name': 'Tensile properties',
                    'prompt_version': 1, 'system_prompt_version': 1, 'model': RUN['model'], 'launched_at': '2026-11-26T10:00:00Z',
                    'finished_at': None, 'papers': {'7': {'extracted_at': '2026-11-26T10:01:00Z', 'input_tokens': 1, 'output_tokens': 2,
                                                          'usd': 0.1, 'seconds': 3.0}}}
        results.write_manifest(folder, manifest)
        self.assertEqual(json.loads((folder / 'run.json').read_text(encoding='utf-8')), manifest)
        with self.assertRaises(RuntimeError):
            results.write_manifest(folder, {**manifest, 'model': None})


class IntoReview(ExtractionBase):
    def test_a_written_paper_opens_in_review(self):   # AC-X07
        make_text_pdf(self.papers / '8.pdf', LINES)
        folder = self.root / 'results' / 'tensile' / 'sonnet-test'
        results.write_result(folder, '8', results.to_result(answer_for('x'), RUN, '8', self.papers / '8.pdf', 'tensile'))
        sid, rows = workspace.load_papers(self.c.app.state.config, 'tensile', 'sonnet-test', ['8'])
        self.assertEqual([r['outcome'] for r in rows], ['written'])
        papers = self.c.get(f'/api/v1/sources/{sid}/papers').json()
        self.assertEqual([(p['paper'], p['values']) for p in papers], [('8', 3)])
        self.assertIn(sid, [r['source_id'] for s in self.c.get('/api/v1/workspace').json()['sets'] for r in s['runs']])
        self.assertEqual(self.c.get(f'{API}/sets').json()['sets'][0]['runs'], ['sonnet-test'])


if __name__ == '__main__':
    unittest.main()
