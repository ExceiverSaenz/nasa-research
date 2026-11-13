"""Read endpoints of the service against the real sealed collection (AC-01 to AC-04, AC-07, AC-13)."""
import copy
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from parsing_validator.domain import blank_state
from parsing_validator.service.app import create_app
from parsing_validator.service.config import HOME, Config

REAL_ORIGINALS = HOME / 'originals'
API = '/api/v1'


def client_for(**overrides):
    return TestClient(create_app(Config(prepare=False, prefetch=False, **overrides)), base_url='http://127.0.0.1')


class Base(unittest.TestCase):
    """Fresh annotations and cache folders per test; the originals are the real, already generated ones."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.client = client_for(originals=REAL_ORIGINALS, annotations=self.tmp / 'annotations', cache=self.tmp / '.cache',
                                 settings_file=self.tmp / 'settings.json')
        services = self.client.app.state.services
        self.addCleanup(services.renderer.close)
        services.library.state['7']['verification'] = 'ok'   # the seal check (4 s) has its own test: Verification
        self.store = services.store
        self.original = json.loads((REAL_ORIGINALS / '7.json').read_text(encoding='utf-8'))

    def get(self, url, **kw):
        return self.client.get(API + url, **kw)


class HostAndErrors(Base):
    def test_foreign_host_is_refused(self):
        r = self.get('/health', headers={'host': 'example.com'})
        self.assertEqual((r.status_code, r.json()['error']['code']), (403, 'forbidden_host'))

    def test_foreign_origin_is_refused(self):
        r = self.get('/health', headers={'origin': 'http://evil.example'})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.get('/health', headers={'origin': 'http://localhost:8000'}).status_code, 200)

    def test_error_shape_and_unknown_paper(self):
        r = self.get('/papers/6')            # paper 6 is not in the collection
        self.assertEqual(r.status_code, 404)
        self.assertEqual(set(r.json()['error']), {'code', 'message', 'details'})
        self.assertEqual(r.json()['error']['code'], 'paper_not_found')
        self.assertEqual(self.get('/papers/..%2f..%2fsecret').status_code, 404)

    def test_bad_page_type_is_invalid_request(self):
        r = self.get('/papers/7/pages/abc')
        self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'invalid_request'))


class Health(Base):
    def test_health(self):
        body = self.get('/health').json()
        self.assertEqual(body['status'], 'ok')
        self.assertEqual(body['collection']['papers'], 23)
        self.assertEqual(body['collection']['unavailable'], [])
        self.assertTrue(body['review_folder']['writable'])
        self.assertEqual(body['mathml']['renderer'], 'katex@0.16.11')


class Listing(Base):
    def test_ac01_all_papers_ordered_with_original_source(self):
        body = self.get('/papers').json()
        ids = [p['id'] for p in body['papers']]
        self.assertEqual(len(ids), 23)
        self.assertEqual(ids, sorted(ids, key=int))
        self.assertNotIn('6', ids)
        self.assertTrue(all(p['source'] == 'original' for p in body['papers']))
        seven = next(p for p in body['papers'] if p['id'] == '7')
        self.assertEqual((seven['pages'], seven['parse_mode']), (9, 'txt'))
        self.assertEqual(seven['counts'], {'blocks': sum(len(p['blocks']) for p in self.original['pages']),
                                           'decided': 0, 'rejected': 0, 'notes': 0})
        self.assertEqual(seven['draft'], {'exists': False, 'stale': False})

    def test_paper_with_a_draft_reports_it(self):
        state = blank_state(self.original)
        state['pages']['7']['blocks']['k11']['status'] = 'accepted'
        self.store.save_draft('7', base_revision=0, trigger='manual', state=state)
        body = self.get('/papers').json()
        seven = next(p for p in body['papers'] if p['id'] == '7')
        self.assertEqual(seven['source'], 'draft')
        self.assertEqual(seven['counts']['decided'], 1)
        self.assertEqual(seven['draft'], {'exists': True, 'stale': False})
        self.assertTrue(all(p['source'] == 'original' for p in body['papers'] if p['id'] != '7'))


class Detail(Base):
    def test_ac02_ac03_detail_of_paper_7(self):
        body = self.get('/papers/7').json()
        self.assertEqual((body['page_count'], body['parse_mode']), (9, 'txt'))
        page7 = next(p for p in body['pages'] if p['index'] == 7)
        self.assertFalse(page7['layers']['cells'])
        self.assertTrue(page7['layers']['layout'] and page7['layers']['ocr'])
        self.assertEqual(body['files'], {'original': True, 'review': False, 'draft': False})


class WorkingState(Base):
    def test_original_when_nothing_is_saved(self):
        r = self.get('/papers/7/state')
        body = r.json()
        self.assertEqual((body['source'], body['revision'], r.headers['etag']), ('original', 0, '"0"'))
        self.assertEqual(body['state'], blank_state(self.original))
        self.assertNotIn('versions', body)

    def test_ac07_stale_draft_is_reported_not_restored(self):
        state = blank_state(self.original)
        self.store.save_draft('7', base_revision=0, trigger='auto', state=state, new_versions=[])
        reviewed = copy.deepcopy(state)
        reviewed['pages']['7']['blocks']['k11']['status'] = 'accepted'
        self.store.save_review('7', reviewed, if_match=0, source={'original_file': 'originals/7.json', 'original_sha256': 'x' * 64})
        # a draft written before the review was committed (the removal of the draft is what a real save does)
        self.store.save_draft('7', base_revision=0, trigger='auto', state=state)
        body = self.get('/papers/7/state').json()
        self.assertEqual((body['source'], body['revision']), ('review', 1))
        self.assertTrue(body['draft']['stale'])
        self.assertNotIn('versions', body)
        self.assertEqual(body['state']['pages']['7']['blocks']['k11']['status'], 'accepted')
        self.assertTrue(self.store.draft_path('7').is_file(), 'a stale draft is never deleted')

    def test_usable_draft_wins_and_lists_versions_without_states(self):
        first = blank_state(self.original)
        second = copy.deepcopy(first)
        second['pages']['7']['blocks']['k11']['note'] = 'hello'
        self.store.save_draft('7', base_revision=0, trigger='manual', state=second,
                              new_versions=[{'label': 'start', 'at': '2026-11-13T10:00:00Z', 'state': first}])
        body = self.get('/papers/7/state').json()
        self.assertEqual(body['source'], 'draft')
        self.assertEqual([v['label'] for v in body['versions']], ['start'])
        self.assertNotIn('state', body['versions'][0])
        self.assertEqual(self.get('/papers/7/state?source=saved').json()['source'], 'original')
        self.assertEqual(self.get('/papers/7/state?source=original').json()['source'], 'original')
        version = self.get('/papers/7/draft/versions/0').json()
        self.assertEqual(version['state'], first)

    def test_version_errors(self):
        self.assertEqual(self.get('/papers/7/draft/versions/0').json()['error']['code'], 'version_not_found')
        state = blank_state(self.original)
        self.store.save_draft('7', base_revision=0, trigger='manual', state=state,
                              new_versions=[{'label': 'a', 'at': '2026-11-13T10:00:00Z', 'state': state}])
        self.assertEqual(self.get('/papers/7/draft/versions/5').status_code, 404)
        path = self.store.draft_path('7')
        draft = json.loads(path.read_text(encoding='utf-8'))
        draft['versions'][0]['sha256'] = '0' * 64
        path.write_text(json.dumps(draft), encoding='utf-8')
        r = self.get('/papers/7/draft/versions/0')
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'version_corrupt'))

    def test_invalid_review_file_opens_from_original_and_is_left_alone(self):
        self.store.folder.mkdir(parents=True, exist_ok=True)
        bad = self.store.review_path('7')
        bad.write_text('{not json', encoding='utf-8')
        body = self.get('/papers/7/state').json()
        self.assertEqual(body['source'], 'original')
        self.assertEqual(body['warnings'], [{'code': 'file_invalid', 'file': '7.review.json'}])
        self.assertEqual(bad.read_text(encoding='utf-8'), '{not json')

    def test_bad_source_value(self):
        self.assertEqual(self.get('/papers/7/state?source=bogus').status_code, 400)


class Pages(Base):
    def test_ac03_page_content_with_layers(self):
        body = self.get('/papers/7/pages/7?layers=layout,ocr,cells').json()
        self.assertEqual(len(body['blocks']), 16)
        self.assertEqual(len(body['layers']['layout']['items']), 34)
        self.assertEqual(len(body['layers']['ocr']['items']), 49)
        self.assertEqual((body['layers']['cells']['available'], body['layers']['cells']['reason']), (False, 'not_captured'))

    def test_layers_are_opt_in(self):
        body = self.get('/papers/7/pages/7').json()
        self.assertTrue(body['layers']['layout']['available'])
        self.assertEqual(body['layers']['layout']['items'], [])
        self.assertEqual(body['layers']['ocr']['items'], [])

    def test_unknown_layer_and_page(self):
        self.assertEqual(self.get('/papers/7/pages/7?layers=bogus').json()['error']['code'], 'invalid_request')
        self.assertEqual(self.get('/papers/7/pages/99').json()['error']['code'], 'page_not_found')
        self.assertEqual(self.get('/papers/7/pages/-1').status_code, 404)

    def test_etag_and_not_modified(self):
        first = self.get('/papers/7/pages/7?layers=layout')
        again = self.get('/papers/7/pages/7?layers=layout', headers={'if-none-match': first.headers['etag']})
        self.assertEqual(again.status_code, 304)
        self.assertNotEqual(first.headers['etag'], self.get('/papers/7/pages/7?layers=ocr').headers['etag'])
        self.assertEqual(first.content, self.get('/papers/7/pages/7?layers=layout').content)


class Images(Base):
    def test_ac04_size_and_identical_bytes(self):
        from PIL import Image
        first = self.get('/papers/7/pages/7/image')
        self.assertEqual((first.status_code, first.headers['content-type']), (200, 'image/png'))
        self.assertIn('immutable', first.headers['cache-control'])
        render = next(p for p in self.original['pages'] if p['index'] == 7)['render']
        self.assertEqual(Image.open(io.BytesIO(first.content)).size, (render['width_px'], render['height_px']))
        self.assertEqual(first.content, self.get('/papers/7/pages/7/image').content)
        self.assertEqual(len(list((self.tmp / '.cache' / 'pages').glob('*.png'))), 1)
        again = self.get('/papers/7/pages/7/image', headers={'if-none-match': first.headers['etag']})
        self.assertEqual(again.status_code, 304)

    def test_scale_range_and_page(self):
        self.assertEqual(self.get('/papers/7/pages/7/image?scale=5').json()['error']['code'], 'invalid_request')
        self.assertEqual(self.get('/papers/7/pages/7/image?scale=0.5').status_code, 400)
        self.assertEqual(self.get('/papers/7/pages/99/image').status_code, 404)

    def test_clear_cache_removes_only_pngs(self):
        self.get('/papers/7/pages/7/image')
        keep = self.tmp / '.cache' / 'keep.txt'
        keep.write_text('x')
        self.assertEqual(self.client.app.state.services.library.clear_cache(), 1)
        self.assertTrue(keep.is_file())


class Settings(Base):
    def test_defaults_when_no_file(self):
        body = self.get('/settings').json()
        self.assertEqual(len(body['tags']), 13)
        self.assertEqual(body['draft_interval_minutes'], 30)
        self.assertTrue(self.get('/settings').headers['etag'])

    def test_foreign_file_is_reported_and_untouched(self):
        (self.tmp / 'settings.json').write_text('{"schema": "other/9"}', encoding='utf-8')
        body = self.get('/settings').json()
        self.assertEqual(body['warnings'], [{'code': 'file_invalid', 'file': 'settings.json'}])
        self.assertEqual((self.tmp / 'settings.json').read_text(encoding='utf-8'), '{"schema": "other/9"}')


class Writes(Base):
    def valid_state(self):
        state = blank_state(self.original)
        block = state['pages']['7']['blocks']['k11']
        block['status'] = 'accepted'
        block['content'].update(status='wrong', error_types=['Math / LaTeX'],
                                latex=[{'source': r'\sigma = F/A_0 \tag{1}', 'mathml': '<math>tampered</math>'}])
        return state

    def put_review(self, state, revision='0', **kw):
        headers = {} if revision is None else {'If-Match': f'"{revision}"'}
        return self.client.put(API + '/papers/7/review', json={'state': state}, headers=headers, **kw)

    def put_draft(self, state, base_revision=0, trigger='manual', versions=()):
        return self.client.put(API + '/papers/7/draft', json={'base_revision': base_revision, 'trigger': trigger,
                                                              'state': state, 'new_versions': list(versions)})

    # --- OP-06 ---
    def test_ac06_draft_does_not_touch_the_review(self):
        self.put_review(self.valid_state())
        review = self.store.review_path('7').read_bytes()
        state = self.valid_state()
        state['pages']['7']['blocks']['k11']['note'] = 'unsaved'
        r = self.put_draft(state, base_revision=1)
        self.assertEqual((r.status_code, r.json()['versions']), (200, 0))
        self.assertEqual(self.store.review_path('7').read_bytes(), review)
        self.assertEqual(json.loads(self.store.draft_path('7').read_text(encoding='utf-8'))['base_revision'], 1)

    def test_draft_accepts_a_state_that_breaks_decision_rules(self):
        state = blank_state(self.original)
        state['pages']['7']['blocks']['k11']['status'] = 'deleted'      # no delete reason: fine for a draft
        self.assertEqual(self.put_draft(state, trigger='auto').status_code, 200)

    def test_pagehide_beacon_posts_plain_text(self):
        body = json.dumps({'base_revision': 0, 'trigger': 'pagehide', 'state': blank_state(self.original), 'new_versions': []})
        r = self.client.post(API + '/papers/7/draft', content=body, headers={'content-type': 'text/plain'})
        self.assertEqual(r.status_code, 200)

    def test_invalid_draft_body_leaves_the_previous_draft(self):
        state = blank_state(self.original)
        self.put_draft(state)
        before = self.store.draft_path('7').read_bytes()
        for bad in ({'base_revision': 0, 'trigger': 'weird', 'state': state, 'new_versions': []},
                    {'base_revision': 0, 'trigger': 'manual', 'state': {'pages': 1}, 'new_versions': []},
                    {'base_revision': 0, 'trigger': 'manual', 'state': state, 'new_versions': [{'label': 'x'}]}):
            r = self.client.put(API + '/papers/7/draft', json=bad)
            self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'invalid_request'))
        self.assertEqual(self.client.put(API + '/papers/7/draft', content='{oops').status_code, 400)
        self.assertEqual(self.store.draft_path('7').read_bytes(), before)

    def test_draft_versions_accumulate(self):
        first = blank_state(self.original)
        second = copy.deepcopy(first)
        second['pages']['7']['blocks']['k11']['note'] = 'a'
        self.put_draft(first)
        r = self.put_draft(second, versions=[{'label': 'one', 'at': '2026-11-13T10:00:00Z', 'state': first}])
        self.assertEqual(r.json()['versions'], 1)
        self.assertEqual(self.get('/papers/7/draft/versions/0').json()['state'], first)

    def test_discard_is_explicit_and_leaves_the_review(self):
        self.put_review(self.valid_state())
        self.put_draft(blank_state(self.original), base_revision=1)
        review = self.store.review_path('7').read_bytes()
        self.assertEqual(self.client.delete(API + '/papers/7/draft').status_code, 204)
        self.assertFalse(self.store.draft_path('7').exists())
        self.assertEqual(self.store.review_path('7').read_bytes(), review)
        self.assertEqual(self.client.delete(API + '/papers/7/draft').status_code, 204)   # idempotent

    # --- OP-07 ---
    def test_ac12_save_changes_stores_mathml_and_removes_the_draft(self):
        self.put_draft(blank_state(self.original))
        r = self.put_review(self.valid_state())
        self.assertEqual((r.status_code, r.json()['revision'], r.headers['etag']), (200, 1, '"1"'))
        self.assertFalse(self.store.draft_path('7').exists())
        review = json.loads(self.store.review_path('7').read_text(encoding='utf-8'))
        segment = review['pages']['7']['blocks']['k11']['content']['latex'][0]
        self.assertTrue(segment['mathml'].startswith('<math') and 'tampered' not in segment['mathml'])
        self.assertEqual((segment['tag'], segment['error']), ('1', None))
        self.assertEqual(review['source']['original_file'], 'originals/7.json')
        self.assertEqual(len(review['source']['original_sha256']), 64)
        self.assertEqual(self.get('/papers/7/state').json()['source'], 'review')

    def test_invalid_latex_is_stored_with_an_error_and_no_mathml(self):
        state = self.valid_state()
        state['pages']['7']['blocks']['k11']['content']['latex'] = [{'source': r'\frac{1}{'}]
        self.assertEqual(self.put_review(state).status_code, 200)
        review = json.loads(self.store.review_path('7').read_text(encoding='utf-8'))
        segment = review['pages']['7']['blocks']['k11']['content']['latex'][0]
        self.assertIsNone(segment['mathml'])
        self.assertTrue(segment['error'])

    def test_precondition_and_conflict(self):
        r = self.put_review(self.valid_state(), revision=None)
        self.assertEqual((r.status_code, r.json()['error']['code']), (428, 'precondition_required'))
        self.assertEqual(self.put_review(self.valid_state()).status_code, 200)
        before = self.store.review_path('7').read_bytes()
        self.put_draft(blank_state(self.original), base_revision=1)
        r = self.put_review(self.valid_state(), revision='0')       # a resend after a lost response
        self.assertEqual((r.status_code, r.json()['error']['code']), (409, 'revision_conflict'))
        self.assertEqual(r.json()['error']['details'], {'expected': 0, 'stored': 1})
        self.assertEqual(self.store.review_path('7').read_bytes(), before)
        self.assertTrue(self.store.draft_path('7').exists(), 'a conflict leaves the draft')
        self.assertEqual(self.put_review(self.valid_state(), revision='1').json()['revision'], 2)

    def test_ac09_rule_violations_are_listed_together_and_nothing_is_written(self):
        state = self.valid_state()
        blocks = state['pages']['7']['blocks']
        blocks['k11']['content']['error_types'] = []                    # rule 3
        blocks['k12']['status'] = 'deleted'                             # rule 4, and it must leave the reading order
        self.put_draft(state)
        r = self.put_review(state)
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'decision_rules_violation'))
        found = {(v['rule'], v['block']) for v in r.json()['error']['details']['violations']}
        self.assertTrue({(3, 'k11'), (4, 'k12'), (1, 'k12')} <= found, found)
        self.assertFalse(self.store.review_path('7').exists())
        self.assertTrue(self.store.draft_path('7').exists())

    def test_malformed_requests(self):
        self.assertEqual(self.client.put(API + '/papers/7/review', json={'state': {'pages': 1}},
                                         headers={'If-Match': '"0"'}).status_code, 400)
        self.assertEqual(self.client.put(API + '/papers/7/review', json={'state': self.valid_state()},
                                         headers={'If-Match': 'abc'}).status_code, 400)
        self.assertEqual(self.client.put(API + '/papers/6/review', json={'state': {}}, headers={'If-Match': '"0"'}).status_code, 404)

    def test_catalog_comes_from_the_settings_file(self):
        stored = self.get('/settings').json()
        stored['tags'] = [t for t in stored['tags'] if t['name'] != 'equation']
        (self.tmp / 'settings.json').write_text(json.dumps(stored), encoding='utf-8')
        r = self.put_review(self.valid_state())
        self.assertEqual(r.status_code, 422)
        self.assertIn('tag_unknown', {v['code'] for v in r.json()['error']['details']['violations']})


class Verification(unittest.TestCase):
    """AC-02 (generated on first request) and the identity checks of an existing original."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def client(self):
        return client_for(originals=self.tmp / 'originals', annotations=self.tmp / 'a', cache=self.tmp / 'c',
                          settings_file=self.tmp / 's.json')

    def test_original_is_generated_on_first_request_and_equals_the_stored_one(self):
        client = self.client()
        self.addCleanup(client.app.state.services.renderer.close)
        r = client.get(f'{API}/papers/7')
        self.assertEqual((r.status_code, r.json()['page_count']), (200, 9))
        made = (self.tmp / 'originals' / '7.json').read_bytes()
        self.assertEqual(made, (REAL_ORIGINALS / '7.json').read_bytes())
        self.assertEqual(client.get(f'{API}/health').json()['collection']['verified'], 1)

    def test_original_with_another_identity_makes_the_paper_unavailable(self):
        folder = self.tmp / 'originals'
        folder.mkdir()
        original = json.loads((REAL_ORIGINALS / '7.json').read_text(encoding='utf-8'))
        original['source']['manifest_sha256'] = '0' * 64
        (folder / '7.json').write_text(json.dumps(original), encoding='utf-8')
        before = (folder / '7.json').read_bytes()
        client = self.client()
        self.addCleanup(client.app.state.services.renderer.close)
        r = client.get(f'{API}/papers/7')
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'source_changed'))
        listed = next(p for p in client.get(f'{API}/papers').json()['papers'] if p['id'] == '7')
        self.assertEqual((listed['verified'], listed['verification']), (False, 'failed'))
        self.assertIsNone(listed['counts'])
        self.assertEqual((folder / '7.json').read_bytes(), before, 'the original is left as it was')
        self.assertEqual(client.get(f'{API}/health').json()['collection']['unavailable'][0]['paper'], '7')


if __name__ == '__main__':
    unittest.main()
