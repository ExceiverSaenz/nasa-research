"""Tests of a run's prompt (72-extraction-interface-contract.md, OP-X03): AC-X03, AC-X04, BR-X02."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import schemas  # noqa: E402
from value_review.service.extraction.prompt import field_line, template  # noqa: E402
from value_review.tests.test_extraction_runs import API, ExtractionBase  # noqa: E402


class Template(unittest.TestCase):
    def test_fields_in_order_with_their_details(self):   # AC-X03
        content = {'description': 'Sub-size specimens.', 'groups': [
            {'group_id': 'g_1', 'name': 'Results', 'fields': [
                {'field_id': 'f_ys', 'name': 'Yield strength', 'type': 'number', 'unit': 'MPa', 'allowed': [], 'multiple': False, 'description': 'At 0.2 % offset.'},
                {'field_id': 'f_ratio', 'name': 'Ratio', 'type': 'calculated', 'unit': '', 'allowed': [], 'multiple': False, 'description': ''}]},
            {'group_id': 'g_2', 'name': 'Material', 'fields': [
                {'field_id': 'f_cls', 'name': 'Class', 'type': 'category', 'unit': '', 'allowed': ['steel', 'alloy'], 'multiple': True, 'description': ''}]}]}
        text = template('You read papers.', 'Tensile', 3, content)
        self.assertTrue(text.startswith('You read papers.\n\n# Task'))
        self.assertIn('the schema "Tensile" (version 3)', text)
        self.assertIn('Sub-size specimens.', text)
        self.assertLess(text.index('### Results'), text.index('### Material'))
        self.assertIn('- **Yield strength** (`f_ys`) · number; unit MPa. At 0.2 % offset.', text)
        self.assertIn('- **Class** (`f_cls`) · category; one or more of: steel, alloy', text)
        self.assertNotIn('(`f_ratio`)', text)
        self.assertIn('Do not extract these calculated fields; they are computed later: Ratio.', text)
        self.assertEqual(field_line({'field_id': 'x', 'name': 'X', 'type': 'text', 'unit': '', 'allowed': [], 'multiple': False, 'description': ' '}),
                         '- **X** (`x`) · text')


class Prompt(ExtractionBase):
    def setUp(self):
        super().setUp()
        self.rid = self.new_run()['id']
        self.base = f'{API}/runs/{self.rid}/prompt'

    def save(self, text, match, **extra):
        return self.c.post(f'{self.base}/versions', json={'text': text, **extra}, headers={'If-Match': match})

    def test_the_template_lists_every_field_of_the_schema(self):   # AC-X03
        body = self.c.post(f'{self.base}/template').json()
        system = self.c.get('/api/v1/system-prompts/extraction').json()
        version = self.c.get('/api/v1/schemas/tensile-properties/versions/1').json()['content']
        fields = [f for g in version['groups'] for f in g['fields']]
        self.assertTrue(body['text'].startswith(system['text'].strip()))
        self.assertEqual((body['system_prompt_version'], body['schema_ref']), (1, {'id': 'tensile-properties', 'version': 1}))
        positions = [body['text'].index(f'(`{f["field_id"]}`)') for f in fields]
        self.assertEqual(positions, sorted(positions))   # schema order
        self.assertFalse((self.data / 'extraction' / 'runs' / self.rid / 'prompt').exists())   # not saved

    def test_versions_restore_conflict_and_export(self):   # AC-X04
        self.assertEqual(self.c.get(self.base).json()['n'], 0)
        r = self.save('First.', '"0"', system_prompt_version=1, note=' mine ')
        self.assertEqual((r.status_code, r.json()['n'], r.json()['note'], r.headers['etag']), (201, 1, 'mine', '"1"'))
        self.assertEqual(self.save('Second.', '"1"').json()['n'], 2)
        r = self.save('Late.', '"1"')
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['details']), (409, 'version_conflict', {'current': 2}))
        self.assertEqual(self.c.post(f'{self.base}/versions', json={'text': 'x'}).status_code, 428)
        r = self.c.post(f'{self.base}/versions/1/restore', headers={'If-Match': '"2"'})
        self.assertEqual((r.status_code, r.json()['n'], r.json()['note'], r.json()['system_prompt_version']), (201, 3, 'Restored from v1', 1))
        current = self.c.get(self.base)
        self.assertEqual((current.json()['text'], current.headers['etag'], current.json()['stale_schema']), ('First.', '"3"', False))
        listed = self.c.get(f'{self.base}/versions').json()['versions']
        self.assertEqual([(v['n'], v.get('restored_from')) for v in listed], [(3, 1), (2, None), (1, None)])
        stored = json.loads((self.data / 'extraction' / 'runs' / self.rid / 'prompt' / 'v3.json').read_text(encoding='utf-8'))
        self.assertEqual(schemas.errors('prompt-version', stored), [])
        r = self.c.get(f'{API}/runs/{self.rid}/prompt.md')
        self.assertEqual((r.text, r.headers['content-disposition']), ('First.', 'attachment; filename="sonnet-test-prompt.md"'))
        self.assertEqual(self.c.get(f'{self.base}/versions/9').status_code, 404)

    def test_the_20_latest_are_kept_and_numbers_never_reused(self):   # BR-X02
        for n in range(22):
            self.assertEqual(self.save(f'Text {n}.', f'"{n}"').status_code, 201)
        nums = [v['n'] for v in self.c.get(f'{self.base}/versions').json()['versions']]
        self.assertEqual((nums[0], nums[-1], len(nums)), (22, 3, 20))
        self.assertEqual(self.save('Next.', '"22"').json()['n'], 23)

    def test_a_prompt_for_another_schema_version_is_flagged(self):
        self.save('First.', '"0"')
        store = self.c.app.state.extraction.runs
        run, _ = store.read(self.rid)
        store.write({**run, 'schema_ref': {'id': 'tensile-properties', 'version': 2}})
        self.assertTrue(self.c.get(self.base).json()['stale_schema'])   # nothing rewritten by itself

    def test_empty_text_and_a_locked_run(self):
        self.assertEqual(self.save('  \n', '"0"').status_code, 400)
        self.save('First.', '"0"')
        store = self.c.app.state.extraction.runs
        run, _ = store.read(self.rid)
        store.write({**run, 'status': 'complete', 'launched_at': '2026-11-26T10:00:00Z', 'prompt_version': 1})
        r = self.save('Changed.', '"1"')
        self.assertEqual((r.status_code, r.json()['error']['code']), (409, 'run_locked'))
        self.assertEqual(self.c.get(self.base).json()['text'], 'First.')


if __name__ == '__main__':
    unittest.main()
