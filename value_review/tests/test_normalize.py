"""Tests of Normalize (90-normalize-specification.md, 92-normalize-interface-contract.md): AC-N01 to AC-N13, against the
local fake provider (no real key, no real call)."""
import hashlib
import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import schemas  # noqa: E402
from value_review.domain import normalize as nz  # noqa: E402
from value_review.domain.state import empty_state  # noqa: E402
from value_review.service import sources as pairs  # noqa: E402
from value_review.tests.test_extraction_runs import SONNET, ExtractionBase  # noqa: E402

API = '/api/v1/normalize'
SID = pairs.DEFAULT_ID
YS = 'yield_strength'


def digest(folder):
    """sha256 of every file under a folder (Review's files must never change, AC-N13)."""
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob('*')) if p.is_file()}


class Pure(unittest.TestCase):
    """BR-N02, BR-N05, BR-N07: the reviewed input, formats, patterns, the draft and Outdated."""
    FIELD = {'field_id': YS, 'label': 'Yield strength', 'type': 'number', 'unit': 'MPa', 'allowed': []}

    def values(self, *pairs_):
        return [{'id': f'p~o{i}', 'paper': 'p', 'value': v, 'unit': u} for i, (v, u) in enumerate(pairs_)]

    def test_reviewed_values_leave_out_rejected_and_empty(self):   # BR-N02
        version = {'n': 2, 'values': [
            {'observation_id': 'o1', 'feature_id': YS, 'record_ids': ['r1'], 'record_labels': ['SS-J'], 'value': '710', 'unit': 'MPa', 'status': 'accepted'},
            {'observation_id': 'o2', 'feature_id': YS, 'record_ids': ['r1'], 'record_labels': ['SS-J'], 'value': '1', 'unit': 'MPa', 'status': 'rejected'},
            {'observation_id': 'o3', 'feature_id': YS, 'record_ids': ['r1'], 'record_labels': ['SS-J'], 'value': ' ', 'unit': '', 'status': 'pending'}]}
        got = nz.reviewed_values({'7': version, '8': None})
        self.assertEqual([(v['id'], v['version_n']) for v in got], [('7~o1', 2)])

    def test_formats_and_patterns(self):   # BR-N05, AC-N03
        vals = self.values(('710 ± 25', 'MPa'), ('455', 'MPa'), ('103', 'ksi'), ('600–650', 'MPa'), ('> 700', 'MPa'), ('about 0.7', 'GPa'))
        self.assertEqual([(f['name'], f['n']) for f in nz.formats(self.FIELD, vals)], [('MPa', 4), ('GPa', 1), ('ksi', 1)])
        found = {p['key']: p['example'] for p in nz.patterns(self.FIELD, vals)}
        self.assertEqual(found, {'pm': '710 ± 25 MPa', 'plain': '455 MPa', 'unit': '103 ksi', 'range': '600–650 MPa',
                                 'ineq': '> 700 MPa', 'words': 'about 0.7 GPa'})
        text = nz.draft_rule(self.FIELD, nz.patterns(self.FIELD, vals))
        self.assertTrue(text.startswith('Normalize Yield strength to MPa.'))
        for line in ('- Value ± uncertainty (e.g. 710 ± 25 MPa): Split into value and uncertainty.',
                     '- Another unit (e.g. 103 ksi): Convert to MPa and say so.', '- Range (e.g. 600–650 MPa): Keep lower and upper bound.',
                     '- Anything else: flag it for me and leave the value as reviewed.'):
            self.assertIn(line, text)

    def test_categories_and_text(self):
        cat = {'field_id': 'g', 'label': 'Group', 'type': 'category', 'unit': '', 'allowed': ['SS316', 'RPVS']}
        vals = self.values(('ss316', ''), ('JFMS', ''), ('JFMS', ''))
        self.assertEqual([(f['name'], f['n']) for f in nz.formats(cat, vals)], [('JFMS', 2), ('ss316', 1)])
        self.assertEqual([(p['key'], p['n']) for p in nz.patterns(cat, vals)], [('other', 2), ('allowed', 1)])
        self.assertEqual(nz.patterns({**cat, 'type': 'text'}, vals), [])

    def test_outdated_and_missing_answers(self):   # BR-N07, BR-N06
        s = {'paper': '7', 'version_n': 1, 'rule_version': 2}
        self.assertFalse(nz.is_outdated(s, {'7': 1}, 2))
        self.assertTrue(nz.is_outdated(s, {'7': 2}, 2))
        self.assertTrue(nz.is_outdated(s, {'7': 1}, 3))
        batch = [{'id': 'a', 'value': '1'}, {'id': 'b', 'value': 'x'}]
        got = nz.answer_by_id(batch, {'results': [{'id': 'a', 'case': 'Plain value', 'fields': [], 'unit': 'MPa', 'display': '1 MPa', 'flag': False,
                                                   'note': ''}, {'id': 'zzz', 'case': 'Plain value', 'fields': [], 'unit': None, 'display': '',
                                                                 'flag': False, 'note': ''}]})
        self.assertEqual(sorted(got), ['a', 'b'])
        self.assertEqual((got['b']['case'], got['b']['flag'], got['b']['display']), ('Not normalized', True, 'x'))


class Service(ExtractionBase):
    """The first workflow and its failures on the default folder pair, paper 7 submitted once."""
    def setUp(self):
        super().setUp()
        self.c.app.state.extraction.backoff = 0
        self.fake.requests.clear()
        self.fake.failures.clear()
        self.fake.delay = 2.0
        self.fake.normalize = __import__('value_review.tests.fake_provider', fromlist=['x']).normalize_for
        r = self.c.post('/api/v1/sources/default/papers/7/versions', json={'state': empty_state()}, headers={'If-Match': '"0"'})
        assert r.status_code == 201, r.text
        self.review = self.data / 'annotations'

    def feature(self, fid=YS):
        return next(f for f in self.c.get(f'{API}/{SID}/features').json()['features'] if f['field_id'] == fid)

    def save(self, text='Normalize Yield strength to MPa.\n- Value ± uncertainty: split it.', match='"0"', decision='norm', **extra):
        body = {'decision': decision, 'text': text, **extra}
        return self.c.post(f'{API}/{SID}/rules/{YS}/versions', json=body, headers={'If-Match': match})

    def apply(self, **extra):
        return self.c.post(f'{API}/{SID}/apply', json={'model': SONNET, **extra})

    def idle(self):
        self.assertTrue(self.c.app.state.normalize.wait_idle(20))
        return self.c.get(f'{API}/{SID}/apply').json()

    def test_first_workflow(self):   # AC-N01, N02, N04, N05, N10, N11, N13
        before = digest(self.review / 'versions') | digest(self.data / 'originals')
        row = next(x for x in self.c.get(f'{API}/extractions').json()['extractions'] if x['sid'] == SID)
        self.assertEqual((row['papers'], row['reviewed'], row['schema_ref']['id']), (1, 1, 'tensile-properties'))
        f = self.feature()
        self.assertEqual((f['status'], f['decision'], f['count'], f['formats'][0]['name']), ('none', 'none', 1, 'MPa'))
        self.assertEqual(self.c.post(f'{API}/{SID}/rules/{YS}/draft').json()['text'].splitlines()[1],
                         '- Value ± uncertainty (e.g. 710 ± 25 MPa): Split into value and uncertainty.')
        r = self.save()
        self.assertEqual((r.status_code, r.json()['n'], r.headers['etag']), (201, 1, '"1"'))
        self.assertEqual(self.feature()['status'], 'ready')
        est = self.c.get(f'{API}/{SID}/estimate', params={'model': SONNET}).json()
        self.assertEqual((est['values'], est['batches'], est['blocked'], est['price_known']), (1, 1, [], True))
        self.assertEqual(self.apply().status_code, 202)
        st = self.idle()
        self.assertEqual((st['status'], st['features'][YS]['status'], st['features'][YS]['batches_done']), ('complete', 'done', 1))
        self.assertGreater(self.c.app.state.extraction.spending.spent(self.anthropic, self.c.app.state.extraction.month()), 0)
        body = self.c.get(f'{API}/{SID}/features/{YS}/values').json()
        v = body['cases'][0]['values'][0]
        self.assertEqual((body['cases'][0]['case'], v['fields'], v['rule_version'], v['model'], v['status'], v['outdated']),
                         ('Value ± uncertainty', [{'name': 'Value', 'value': '710'}, {'name': 'Uncertainty (±)', 'value': '25'}], 1, SONNET,
                          'to_validate', False))
        stored = json.loads((self.data / 'normalize' / SID / 'values' / f'{YS}.json').read_text(encoding='utf-8'))
        self.assertEqual(schemas.errors('normalized-values', stored), [])
        self.assertEqual(stored['values'][v['id']]['system_prompt_version'], 1)
        prompt = self.fake.requests[-1]['prompt']
        self.assertIn('# Rule\nNormalize Yield strength to MPa.', prompt)
        self.assertIn('"value": "710 ± 25"', prompt)
        # validate: a rejection needs a reason, then results and the CSV hold only validated values
        r = self.c.patch(f'{API}/{SID}/values/{v["id"]}', json={'status': 'rejected'})
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'reason_required'))
        r = self.c.patch(f'{API}/{SID}/values/{v["id"]}', json={'status': 'unsure'})
        self.assertEqual(r.json()['by'], 'Expert reviewer')
        self.assertEqual(self.c.get(f'{API}/{SID}/results').json()['left_out']['to_validate'], 1)
        self.assertEqual(self.c.post(f'{API}/{SID}/features/{YS}/accept-case', json={'case': 'Value ± uncertainty'}).json(), {'accepted': 0})
        self.c.patch(f'{API}/{SID}/values/{v["id"]}', json={'status': 'to_validate'})
        self.assertEqual(self.c.post(f'{API}/{SID}/features/{YS}/accept-case', json={'case': 'Value ± uncertainty'}).json(), {'accepted': 1})
        self.assertEqual(self.feature()['status'], 'done')
        res = self.c.get(f'{API}/{SID}/results').json()
        col = next(i for i, c in enumerate(res['columns']) if c['id'] == YS)
        cell = next(r['cells'][col] for r in res['rows'] if r['cells'][col]['status'] != 'empty')
        self.assertEqual((cell, res['left_out']['to_validate']), ({'value': '710 · ± 25 MPa', 'status': 'ok'}, 0))
        self.c.put('/api/v1/settings', json={'csv_delimiter': ';', 'csv_encoding': 'utf8'})
        csv_text = self.c.get(f'{API}/{SID}/results.csv').content.decode('utf-8')
        header = csv_text.splitlines()[0]
        self.assertIn('Yield strength · Value;Yield strength · Uncertainty (±);', header)
        self.assertIn(';710;25;', csv_text)
        self.assertEqual(digest(self.review / 'versions') | digest(self.data / 'originals'), before)   # AC-N13

    def test_rule_versions_conflict_and_restore(self):   # AC-N04
        self.save(text='first')
        self.assertEqual(self.save(text='second', match='"1"').json()['n'], 2)
        r = self.save(text='late', match='"1"')
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['details']), (409, 'version_conflict', {'current': 2}))
        r = self.c.post(f'{API}/{SID}/rules/{YS}/versions/1/restore', headers={'If-Match': '"2"'})
        self.assertEqual((r.status_code, r.json()['n'], r.json()['text']), (201, 3, 'first'))
        self.assertEqual([v['n'] for v in self.c.get(f'{API}/{SID}/rules/{YS}/versions').json()['versions']], [3, 2, 1])
        self.c.put('/api/v1/settings', json={'keep_rule_versions': 2})
        self.save(text='fourth', match='"3"')
        self.assertEqual([v['n'] for v in self.c.get(f'{API}/{SID}/rules/{YS}/versions').json()['versions']], [4, 3])

    def test_blocked_and_nothing_to_do(self):   # AC-N06
        self.save()
        self.c.patch(f'/api/v1/keys/{self.anthropic}', json={'monthly_limit_usd': 0})
        r = self.apply()
        self.assertEqual((r.status_code, r.json()['error']['code']), (409, 'key_at_limit'))
        self.assertEqual(self.c.get(f'{API}/{SID}/estimate', params={'model': SONNET}).json()['blocked'][0]['code'], 'key_at_limit')
        self.assertEqual(self.c.get(f'{API}/{SID}/apply').json()['status'], 'idle')
        r = self.c.post(f'{API}/{SID}/apply', json={'model': 'anthropic:not-enabled'})
        self.assertEqual(r.json()['error']['code'], 'model_unavailable')
        self.c.patch(f'/api/v1/keys/{self.anthropic}', json={'monthly_limit_usd': None})
        self.save(text='', match='"1"')
        r = self.apply(features=[YS])
        self.assertEqual((r.status_code, r.json()['error']['code']), (409, 'rule_empty'))

    def test_a_failed_batch_and_retry(self):   # AC-N07
        self.save()
        self.c.put('/api/v1/settings', json={'extraction': {'parallel': 1, 'retries': 1, 'minutes': 10, 'warn_usd': 5}})
        self.fake.failures.extend([500, 500])
        self.apply()
        st = self.idle()
        self.assertEqual((st['features'][YS]['status'], self.feature()['status']), ('failed', 'failed'))
        self.assertIn('error', st['features'][YS]['error'])
        r = self.c.post(f'{API}/{SID}/apply/features/{YS}/retry')
        self.assertEqual(r.status_code, 202)
        self.assertEqual(self.idle()['features'][YS]['status'], 'done')

    def test_pause_and_restart_resume(self):   # AC-N08
        self.save()
        self.c.put('/api/v1/settings', json={'extraction': {'parallel': 1, 'retries': 0, 'minutes': 10, 'warn_usd': 5}})
        state = {'status': 'running', 'model': SONNET, 'key_id': self.anthropic, 'started_at': '2026-11-27T10:00:00Z', 'finished_at': None,
                 'usd': 0, 'features': {YS: {'status': 'normalizing', 'values': 1, 'batches': 1, 'batches_done': 0, 'rule_version': 1,
                                             'error': None, 'usd': 0}}}
        path = self.data / 'normalize' / SID / 'apply.json'
        path.write_text(json.dumps(state), encoding='utf-8')
        st = self.c.get(f'{API}/{SID}/apply').json()   # as after a restart: nothing is running in this process
        self.assertEqual((st['status'], st['features'][YS]['status']), ('paused', 'queued'))
        self.assertEqual(self.c.post(f'{API}/{SID}/apply/resume').status_code, 202)
        self.assertEqual(self.idle()['features'][YS]['status'], 'done')
        self.assertEqual(len([r for r in self.fake.requests if r.get('prompt')]), 1)

    def test_outdated_after_a_new_rule_or_a_new_review(self):   # AC-N09
        self.save()
        self.apply()
        self.idle()
        vid = self.c.get(f'{API}/{SID}/features/{YS}/values').json()['cases'][0]['values'][0]['id']
        self.save(text='Another rule.', match='"1"')
        self.assertEqual(self.feature()['status'], 'outdated')
        r = self.c.patch(f'{API}/{SID}/values/{vid}', json={'status': 'accepted'})
        self.assertEqual((r.status_code, r.json()['error']['code']), (409, 'value_outdated'))
        self.assertEqual(self.c.get(f'{API}/{SID}/results').json()['left_out']['outdated'], 1)
        self.assertEqual(self.c.get(f'{API}/{SID}/estimate', params={'model': SONNET}).json()['values'], 1)
        self.apply()
        self.idle()
        self.assertEqual(self.c.patch(f'{API}/{SID}/values/{vid}', json={'status': 'accepted'}).status_code, 200)
        # the paper submitted again in Review: its values are Outdated
        r = self.c.post('/api/v1/sources/default/papers/7/versions', json={'state': empty_state()}, headers={'If-Match': '"1"'})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(self.feature()['status'], 'outdated')
        self.assertEqual(self.c.get(f'{API}/{SID}/apply').json()['status'], 'complete')

    def test_try_writes_nothing(self):   # AC-N12
        rule = {'decision': 'norm', 'text': 'Split it.'}
        r = self.c.post(f'{API}/{SID}/rules/{YS}/try', json={'rule': rule, 'model': SONNET})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual([(x['reviewed'], x['display']) for x in r.json()['results']], [('710 ± 25 MPa', '710 · ± 25 MPa')])
        self.assertFalse((self.data / 'normalize' / SID / 'values').exists())
        self.assertFalse((self.data / 'normalize' / SID / 'rules').exists())

    def test_keep_as_is_exports_the_reviewed_value(self):   # BR-N09
        self.save(decision='keep', text='')
        self.assertEqual(self.feature()['status'], 'kept')
        res = self.c.get(f'{API}/{SID}/results').json()
        col = next(i for i, c in enumerate(res['columns']) if c['id'] == YS)
        self.assertIn({'value': '710 ± 25 MPa', 'status': 'ok'}, [r['cells'][col] for r in res['rows']])
        self.assertEqual(self.c.get(f'{API}/{SID}/estimate', params={'model': SONNET}).json()['values'], 0)
        self.assertEqual(self.apply().json()['error']['code'], 'nothing_to_normalize')

    def test_unknown_feature_and_source(self):
        self.assertEqual(self.c.get(f'{API}/{SID}/rules/nope').status_code, 404)
        self.assertEqual(self.c.get(f'{API}/nope/features').json()['error']['code'], 'source_not_found')
        time.sleep(0)


if __name__ == '__main__':
    unittest.main()
