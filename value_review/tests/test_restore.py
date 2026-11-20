"""Tests of restore (step 8): OP-08. Covers AC-11 and BR-03 for restored versions."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import schemas  # noqa: E402
from value_review.domain.state import empty_state  # noqa: E402
from value_review.tests.test_versions import Versions, d, three_decisions  # noqa: E402

URL = '/api/v1/papers/7/versions'


class Restore(Versions):
    def setUp(self):
        super().setUp()
        self.s1 = three_decisions()
        self.s2 = empty_state()
        self.s2['decisions'] = {'o1': d('accepted')}
        self.assertEqual(self.submit(self.s1, '"0"').status_code, 201)
        self.assertEqual(self.submit(self.s2, '"1"').status_code, 201)

    def restore(self, k, match):
        headers = {} if match is None else {'If-Match': match}
        return self.client.post(f'{URL}/{k}/restore', headers=headers)

    def test_restore_writes_a_new_version_with_the_old_content(self):  # AC-11
        self.put_draft()
        r = self.restore(1, '"2"')
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual((r.json()['n'], r.json()['note'], r.headers['etag']), (3, 'Restored from v1', '"3"'))
        v3 = json.loads(self.store.version_path('7', 3).read_text(encoding='utf-8'))
        self.assertEqual(schemas.errors('version', v3), [])
        self.assertEqual((v3['state'], v3['restored_from'], v3['base_version'], v3['note']), (self.s1, 1, 2, 'Restored from v1'))
        self.assertEqual(v3['counts']['rejected'], 1)
        self.assertEqual(self.files(), ['v1.json', 'v2.json', 'v3.json'])   # nothing deleted
        self.assertFalse(self.store.draft_path('7').exists())               # the draft is discarded
        self.assertEqual([v['note'] for v in self.client.get(URL).json()], ['Restored from v1', 'Submitted', 'Submitted'])

    def test_version_checks(self):
        self.assertEqual(self.restore(1, None).status_code, 428)
        r = self.restore(1, '"1"')
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['details']), (409, 'version_conflict', {'current': 2}))
        r = self.restore(9, '"2"')
        self.assertEqual((r.status_code, r.json()['error']['code']), (404, 'version_not_found'))
        self.assertEqual(self.client.post('/api/v1/papers/8/versions/1/restore', headers={'If-Match': '"0"'}).status_code, 404)
        self.assertEqual(self.files(), ['v1.json', 'v2.json'])

    def test_restore_counts_toward_the_limit(self):  # BR-03
        self.client.put('/api/v1/settings', json={'reviewer_name': 'Expert reviewer', 'keep_versions': 2, 'autosave_minutes': 5})
        self.assertEqual(self.restore(1, '"2"').status_code, 201)
        self.assertEqual(self.files(), ['v2.json', 'v3.json'])
        self.assertEqual(self.restore(1, '"3"').status_code, 404)   # v1 was pruned

    def test_version_from_another_model_output_is_refused(self):  # OQ-02
        path = self.store.version_path('7', 1)
        v1 = json.loads(path.read_text(encoding='utf-8'))
        v1['source']['result_sha256'] = 'f' * 64
        path.write_text(json.dumps(v1), encoding='utf-8')
        r = self.restore(1, '"2"')
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'source_changed'))
        self.assertEqual(self.files(), ['v1.json', 'v2.json'])

    def put_draft(self):
        r = self.client.put('/api/v1/papers/7/draft', json={'base_version': 2, 'trigger': 'manual', 'state': self.s2})
        self.assertEqual(r.status_code, 200)


if __name__ == '__main__':
    unittest.main()
