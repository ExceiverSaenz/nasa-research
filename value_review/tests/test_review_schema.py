"""Review bound to the schema version of its extraction (80-review-schema-specification.md; ADR-030 to ADR-032):
AC-R01 to AC-R09 and BR-R01 to BR-R09."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import schemas  # noqa: E402
from value_review.domain import review_schema as rs  # noqa: E402
from value_review.domain.state import empty_state  # noqa: E402
from value_review.ingest.seed_schema import seed_content  # noqa: E402
from value_review.service import workspace  # noqa: E402
from value_review.service.extraction import results  # noqa: E402
from value_review.tests.test_extraction_results import LINES, RUN  # noqa: E402
from value_review.tests.test_extraction_runs import ExtractionBase  # noqa: E402
from value_review.tests.text_pdf import make_text_pdf  # noqa: E402

AT = '2026-11-27T10:00:00Z'


def field(type_='text', allowed=(), multiple=False):
    return {'field_id': 'f', 'label': 'F', 'type': type_, 'allowed': list(allowed), 'multiple': multiple, 'calculated': False}


class Fit(unittest.TestCase):   # BR-R06
    def test_a_number_field_only_asks_for_a_digit(self):
        for text in ('710 ± 26', '10⁻³', '< 0.01', '700–720', '1.2e3'):
            self.assertEqual(rs.fit(field('number'), text), [], text)
        self.assertEqual(rs.fit(field('number'), 'not reported'), ['not_a_number'])
        self.assertEqual(rs.fit(field('number'), '  '), [])

    def test_a_category_takes_its_allowed_values(self):
        f = field('category', ['Annealed', 'Irradiated'])
        self.assertEqual(rs.fit(f, 'annealed'), [])
        self.assertEqual(rs.fit(f, 'cold worked'), ['not_allowed'])
        self.assertEqual(rs.fit(f, 'annealed; irradiated'), ['not_allowed'])   # one value only
        self.assertEqual(rs.fit({**f, 'multiple': True}, 'annealed; irradiated'), [])
        self.assertEqual(rs.fit(field('category'), 'anything'), [])   # no list: nothing to check
        self.assertEqual(rs.fit(field('text'), 'abc'), [])
        self.assertEqual(rs.fit(None, 'abc'), [])

    def test_fields_follow_group_and_field_order(self):   # BR-R02
        fields = rs.fields_of(seed_content())
        self.assertEqual([f['field_id'] for f in fields[:3]], ['material', 'material_group', 'composition_c'])
        self.assertEqual(fields[0]['group'], 'Material and chemical composition')
        self.assertEqual(len(fields), 54)


class ModelChecks(unittest.TestCase):   # BR-R04
    def original(self, mode, evidence):
        return {'source': {'mode': mode}, 'features': [{'feature_id': 'yield_strength', 'label': 'Yield strength'}],
                'observations': [{'observation_id': 'o1', 'feature_id': 'yield_strength', 'value': '710', 'needs_check': False,
                                  'evidence': evidence}]}

    def test_a_value_without_a_box_needs_a_check_only_when_extraction_wrote_it(self):
        fields = rs.fields_of(seed_content())
        self.assertEqual(rs.model_checks(self.original('api_pdf', []), fields), {'o1': [rs.QUOTE_NOT_FOUND]})
        self.assertEqual(rs.model_checks(self.original('api_pdf', [{'bbox': [1, 2, 3, 4]}]), fields), {})
        self.assertEqual(rs.model_checks(self.original(None, []), fields), {})   # the LLM run: derived values have no box

    def test_an_unbound_paper_keeps_only_the_evidence_rule(self):   # BR-R09
        original = self.original('api_pdf', [])
        original['observations'][0]['feature_id'] = 'hardness'
        fields = rs.fallback_fields(original)
        self.assertEqual(rs.model_checks(original, fields, bound=False), {'o1': [rs.QUOTE_NOT_FOUND]})


def answer():
    """Paper 8 as the fake model would answer it on schema v2: a value whose quote is in no page, a field the schema does
    not have, and a category value outside the allowed ones."""
    return {'records': [{'record_id': 'r1', 'label': 'SS-J', 'condition': ''}],
            'values': [{'field_id': 'yield_strength', 'record_ids': ['r1'], 'value': '710 ± 25', 'unit': 'MPa', 'page': 1,
                        'quote': 'Yield strength 710', 'flags': [], 'notes': ''},
                       {'field_id': 'ultimate_tensile_strength', 'record_ids': ['r1'], 'value': '845', 'unit': 'MPa', 'page': 1,
                        'quote': 'not in the paper', 'flags': [], 'notes': ''},
                       {'field_id': 'hardness', 'record_ids': ['r1'], 'value': '220', 'unit': 'HV', 'page': 1,
                        'quote': 'Material: FeCrAl', 'flags': [], 'notes': ''},
                       {'field_id': 'treatment_three_categories', 'record_ids': ['r1'], 'value': 'cold worked', 'unit': '', 'page': 1,
                        'quote': 'Material: FeCrAl', 'flags': [], 'notes': ''}],
            'completion': {'status': 'complete', 'notes': ''}}


class BoundReview(ExtractionBase):
    def setUp(self):
        super().setUp()
        content = copy.deepcopy(seed_content())
        for g in content['groups']:
            for f in g['fields']:
                if f['field_id'] == 'yield_strength':
                    f.update(name='Yield strength (0.2 %)', type='number', unit='MPa')
                if f['field_id'] == 'treatment_three_categories':
                    f.update(type='category', allowed=['annealed', 'irradiated', 'aged'])
        r = self.c.post('/api/v1/schemas/tensile-properties/versions', json={'content': content, 'note': 'v2'}, headers={'If-Match': '"1"'})
        self.assertEqual(r.status_code, 201, r.text)
        make_text_pdf(self.papers / '8.pdf', LINES)
        self.folder = self.root / 'results' / 'tensile' / 'v2-run'
        results.write_result(self.folder, '8', results.to_result(answer(), RUN, '8', self.papers / '8.pdf', 'tensile'))
        results.write_manifest(self.folder, {
            'schema': 'value-review-run-manifest/1', 'run_id': RUN['id'], 'name': 'v2 run', 'set': 'tensile',
            'schema_ref': {'id': 'tensile-properties', 'version': 2}, 'schema_name': 'Tensile properties', 'prompt_version': 1,
            'system_prompt_version': 1, 'model': RUN['model'], 'launched_at': AT, 'finished_at': AT, 'papers': {}})
        self.sid, rows = workspace.load_papers(self.c.app.state.config, 'tensile', 'v2-run', ['8'])
        self.assertEqual([r['outcome'] for r in rows], ['written'])
        self.url = f'/api/v1/sources/{self.sid}/papers'

    def paper(self):
        r = self.c.get(f'{self.url}/8')
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def oid(self, body, feature):
        return next(o['observation_id'] for o in body['original']['observations'] if o['feature_id'] == feature)

    def submit(self, state, match='"0"'):
        return self.c.post(f'{self.url}/8/versions', json={'state': state}, headers={'If-Match': match})

    def test_columns_and_checks_follow_the_runs_schema_version(self):   # AC-R01, AC-R03, AC-R04, AC-R05
        body = self.paper()
        self.assertEqual(body['schema_ref'], {'id': 'tensile-properties', 'version': 2, 'name': 'Tensile properties'})
        self.assertIsNone(body['schema_problem'])
        by_id = {f['field_id']: f for f in body['fields']}
        self.assertEqual((by_id['yield_strength']['label'], by_id['yield_strength']['unit']), ('Yield strength (0.2 %)', 'MPa'))
        self.assertEqual([f['field_id'] for f in body['fields']][:2], ['material', 'material_group'])
        checks = {o['feature_id']: body['checks'].get(o['observation_id'], {}).get('action') for o in body['original']['observations']}
        self.assertEqual(checks, {'yield_strength': None, 'ultimate_tensile_strength': [rs.QUOTE_NOT_FOUND],
                                  'hardness': [rs.NOT_IN_SCHEMA], 'treatment_three_categories': [rs.NOT_ALLOWED]})
        self.assertNotIn('hardness', [f['feature_id'] for f in body['feature_catalog']])
        listed = self.c.get(self.url).json()
        self.assertEqual((listed[0]['needs_check'], listed[0]['schema_ref']['version']), (3, 2))

    def test_moves_and_additions_must_target_the_schemas_fields(self):   # AC-R04, AC-R06, BR-R03
        body = self.paper()
        hardness = self.oid(body, 'hardness')
        state = empty_state()
        state['column_moves'][hardness] = {'feature_id': 'vickers', 'by': 'T', 'at': AT}
        r = self.c.put(f'{self.url}/8/draft', json={'base_version': 0, 'state': state, 'trigger': 'manual'})
        self.assertEqual((r.status_code, r.json()['error']['details']['items']), (422, [{'ref': hardness, 'rule': 'unknown_feature'}]))
        state['column_moves'][hardness] = {'feature_id': 'yield_strength', 'by': 'T', 'at': AT}
        self.assertEqual(self.submit(state).status_code, 201)
        state = copy.deepcopy(state)
        state['column_moves'][hardness] = {'feature_id': 'hardness', 'by': 'T', 'at': AT}   # back to its own column
        self.assertEqual(self.submit(state, '"1"').status_code, 201)

    def test_a_correction_that_does_not_fit_warns_and_is_kept(self):   # AC-R07, AC-R08, BR-R06, BR-R07
        body = self.paper()
        ys, cat = self.oid(body, 'yield_strength'), self.oid(body, 'treatment_three_categories')
        state = empty_state()
        state['decisions'][ys] = {'verdict': 'corrected', 'value': 'abc', 'unit': 'MPa', 'note': '', 'by': 'T', 'at': AT}
        state['decisions'][cat] = {'verdict': 'corrected', 'value': 'Aged', 'unit': '', 'note': '', 'by': 'T', 'at': AT}
        r = self.submit(state)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()['counts']['mismatched'], 1)
        version = self.c.get(f'{self.url}/8/versions/1').json()
        self.assertEqual(schemas.errors('version', version), [])
        self.assertEqual(version['schema_ref'], {'id': 'tensile-properties', 'version': 2, 'name': 'Tensile properties'})
        rows = {v['feature_id']: v for v in version['values']}
        self.assertEqual((rows['yield_strength']['value'], rows['yield_strength']['warnings']), ('abc', ['not_a_number']))
        self.assertEqual(rows['treatment_three_categories']['warnings'], [])
        self.assertTrue(rows['hardness']['needs_check'])
        exported = self.c.get(f'{self.url}/8/versions/1/export.json').json()
        self.assertEqual((exported['schema_ref']['version'], schemas.errors('export', exported)), (2, []))
        csv = self.c.get(f'{self.url}/8/versions/1/export.csv').content.decode('utf-8-sig')
        self.assertIn('Yield strength (0.2 %)', csv)
        self.assertIn(',Hardness,hardness,', csv)   # not in the schema: the readable form of its id

    def test_a_deleted_schema_still_opens_the_paper(self):   # AC-R09, BR-R09
        self.assertEqual(self.c.delete('/api/v1/schemas/tensile-properties').status_code, 204)
        body = self.paper()
        self.assertIsNone(body['schema_ref'])
        self.assertEqual(body['schema_problem']['code'], 'schema_missing')
        self.assertEqual({f['field_id'] for f in body['fields']}, {o['feature_id'] for o in body['original']['observations']})
        self.assertEqual(body['checks'], {self.oid(body, 'ultimate_tensile_strength'): {'action': [rs.QUOTE_NOT_FOUND]}})
        r = self.submit(empty_state())
        self.assertEqual(r.status_code, 201, r.text)
        self.assertIsNone(self.c.get(f'{self.url}/8/versions/1').json()['schema_ref'])

    def test_an_unreadable_manifest_falls_back_to_the_seeded_schema(self):   # BR-R01
        (self.folder / 'run.json').write_text('{', encoding='utf-8')
        body = self.paper()
        self.assertEqual(body['schema_ref']['version'], 1)
        self.assertEqual(body['schema_problem']['code'], 'run_manifest_unreadable')
        self.assertEqual(json.loads(json.dumps(body['fields']))[0]['field_id'], 'material')


if __name__ == '__main__':
    unittest.main()
