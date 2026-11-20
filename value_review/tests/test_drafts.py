"""Tests of drafts (step 6): OP-04 save and delete, and how drafts meet versions.

Covers AC-09 (server side), BR-02 and BR-11 for drafts. Synthetic paper 7 from test_ingest.
"""
import json
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import schemas  # noqa: E402
from value_review.domain.state import empty_state  # noqa: E402
from value_review.tests.test_versions import AT, BY, Versions, d, three_decisions  # noqa: E402

URL = '/api/v1/papers/7/draft'


class Drafts(Versions):
    def put(self, state, base=0, trigger='manual', ui=None):
        body = {'base_version': base, 'trigger': trigger, 'state': state}
        if ui is not None:
            body['ui'] = ui
        return self.client.put(URL, json=body)

    def test_save_and_reopen(self):  # AC-09
        ui = {'mode': 'record', 'record_id': 'r1', 'observation_id': 'o2'}
        r = self.put(three_decisions(), ui=ui)
        self.assertEqual(r.status_code, 200, r.text)
        saved_at = r.json()['saved_at']
        draft = json.loads(self.store.draft_path('7').read_text(encoding='utf-8'))
        self.assertEqual(schemas.errors('draft', draft), [])
        self.assertEqual((draft['base_version'], draft['trigger'], draft['saved_at'], draft['ui'], draft['state']),
                         (0, 'manual', saved_at, ui, three_decisions()))
        body = self.client.get('/api/v1/papers/7').json()
        self.assertEqual((body['version'], body['draft']['state'], body['draft_stale']), (0, three_decisions(), False))
        self.assertEqual(self.files(), [])   # a draft is not a version (BR-02)
        row = self.client.get('/api/v1/papers').json()[0]
        self.assertEqual((row['draft_at'], row['reviewed'], row['status']), (saved_at, 3, 'in_progress'))

    def test_overwrites_the_previous_draft(self):
        self.put(empty_state(), trigger='auto')
        self.put(three_decisions(), trigger='pagehide')
        draft = json.loads(self.store.draft_path('7').read_text(encoding='utf-8'))
        self.assertEqual((draft['trigger'], draft['state']), ('pagehide', three_decisions()))
        self.assertEqual(sorted(p.name for p in self.store.draft_path('7').parent.iterdir()), ['7.draft.json'])

    def test_unfinished_reason_is_kept(self):  # drafts skip BR-04; submit does not
        s = empty_state()
        s['decisions'] = {'o1': d('rejected', '')}
        self.assertEqual(self.put(s).status_code, 200)
        r = self.client.post('/api/v1/papers/7/versions', json={'state': s}, headers={'If-Match': '0'})
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'rules_violation'))
        self.assertTrue(self.store.draft_path('7').exists())   # a failed submit keeps the draft

    def test_stale_base_version_is_refused(self):  # BR-11
        self.assertEqual(self.client.post('/api/v1/papers/7/versions', json={'state': three_decisions()},
                                          headers={'If-Match': '0'}).status_code, 201)
        r = self.put(three_decisions(), base=0)
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['details']), (409, 'version_conflict', {'current': 1}))
        self.assertFalse(self.store.draft_path('7').exists())
        self.assertEqual(self.put(three_decisions(), base=1).status_code, 200)

    def test_submit_deletes_the_draft(self):
        self.put(three_decisions())
        self.assertEqual(self.client.post('/api/v1/papers/7/versions', json={'state': three_decisions()},
                                          headers={'If-Match': '0'}).status_code, 201)
        self.assertFalse(self.store.draft_path('7').exists())
        self.assertIsNone(self.client.get('/api/v1/papers/7').json()['draft'])

    def test_draft_left_behind_by_another_submit_is_stale(self):
        self.put(three_decisions())   # base 0
        other = json.loads(self.store.draft_path('7').read_text(encoding='utf-8'))
        self.client.post('/api/v1/papers/7/versions', json={'state': three_decisions()}, headers={'If-Match': '0'})
        self.write_json(self.store.draft_path('7'), other)   # e.g. a second device saved before the submit landed
        body = self.client.get('/api/v1/papers/7').json()
        self.assertEqual((body['version'], body['draft']['base_version'], body['draft_stale']), (1, 0, True))

    def test_invalid_drafts(self):
        s = empty_state()
        s['decisions'] = {'o1': d('corrected')}
        self.assertEqual(self.put(s).status_code, 400)                                   # schema
        s = empty_state()
        s['decisions'] = {'o9': d('accepted')}
        r = self.put(s)
        self.assertEqual((r.status_code, r.json()['error']['details']['items']), (422, [{'ref': 'o9', 'rule': 'unknown_observation'}]))
        self.assertEqual(self.put(empty_state(), trigger='timer').status_code, 400)       # trigger
        self.assertEqual(self.put(empty_state(), ui={'colour': 'blue'}).status_code, 400)  # ui
        self.assertEqual(self.client.put('/api/v1/papers/8/draft', json={'base_version': 0, 'trigger': 'manual', 'state': empty_state()}).status_code, 404)
        self.assertFalse(self.store.draft_path('7').exists())

    def test_source_changed_blocks_drafts(self):
        self.res.write_text(self.res.read_text(encoding='utf-8').replace('710', '711'), encoding='utf-8')
        r = self.put(three_decisions())
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'source_changed'))

    def test_delete_is_idempotent(self):
        self.put(three_decisions())
        self.assertEqual(self.client.delete(URL).status_code, 204)
        self.assertFalse(self.store.draft_path('7').exists())
        self.assertEqual(self.client.delete(URL).status_code, 204)
        self.assertEqual(self.client.delete('/api/v1/papers/8/draft').status_code, 404)

    def test_storage_errors_reach_the_client_without_a_path(self):  # contract: no absolute path in error messages
        self.put(three_decisions())
        denied = PermissionError(13, 'Access is denied', str(self.store.draft_path('7')))   # as Windows raises it
        with mock.patch.object(Path, 'unlink', side_effect=denied):
            r = self.client.delete(URL)
        self.assertEqual((r.status_code, r.json()['error']['code']), (500, 'storage_error'))
        self.assertEqual(r.json()['error']['message'], 'Could not delete the draft: Access is denied')
        with mock.patch('value_review.storage.atomic.os.replace', side_effect=denied):
            r = self.put(three_decisions())
        self.assertEqual((r.status_code, r.json()['error']['message']), (500, 'Could not replace 7.draft.json: Access is denied'))
        self.assertNotIn(str(self.data), r.text)
        self.assertEqual(json.loads(self.store.draft_path('7').read_text(encoding='utf-8'))['state'], three_decisions())   # kept

    def test_by_and_at_are_kept_as_sent(self):
        s = empty_state()
        s['decisions'] = {'o1': {'verdict': 'accepted', 'note': '', 'by': BY, 'at': AT}}
        self.put(s)
        self.assertEqual(json.loads(self.store.draft_path('7').read_text(encoding='utf-8'))['state']['decisions']['o1']['at'], AT)


if __name__ == '__main__':
    unittest.main()
