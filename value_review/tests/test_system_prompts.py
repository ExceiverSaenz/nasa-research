"""Tests of the System prompts (42-settings-interface-contract.md, OP-T02): AC-T07 to AC-T10, BR-T06, on temporary
data folders, plus the store on its own."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import schemas  # noqa: E402
from value_review.storage import StorageError  # noqa: E402
from value_review.storage.system_prompts import SEED_TEXT, SystemPromptStore  # noqa: E402
from value_review.tests.test_service import Base  # noqa: E402

API = '/api/v1/system-prompts'


class SystemPrompts(Base):
    def save(self, kind, text, match, note=''):
        return self.client.post(f'{API}/{kind}/versions', json={'text': text, 'note': note}, headers={'If-Match': match})

    @property
    def folder(self):
        return self.client.app.state.system_prompts.folder

    def test_seeded_with_the_canvas_texts(self):   # AC-T07
        body = self.client.get(API).json()
        self.assertEqual([(p['kind'], p['n'], p['saved_by'], p['text']) for p in body['prompts']],
                         [('extraction', 1, 'value_review', SEED_TEXT['extraction']),
                          ('normalization', 1, 'value_review', SEED_TEXT['normalization'])])
        self.assertIn('710 ± 25', SEED_TEXT['extraction'])
        r = self.client.get(f'{API}/extraction')
        self.assertEqual((r.headers['etag'], r.json()['n']), ('"1"', 1))
        for kind in ('extraction', 'normalization'):
            data = json.loads((self.folder / kind / 'v1.json').read_text(encoding='utf-8'))
            self.assertEqual(schemas.errors('system-prompt-version', data), [])

    def test_save_makes_a_new_version_by_the_display_name(self):   # AC-T08, BR-T06
        self.client.put('/api/v1/settings', json={'reviewer_name': 'Ana López'})
        self.client.get(API)
        v1 = (self.folder / 'extraction' / 'v1.json').read_bytes()
        r = self.save('extraction', 'Write a short prompt.', '"1"', note='  Shorter  ')
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual((r.json()['n'], r.json()['saved_by'], r.json()['note'], r.headers['etag']), (2, 'Ana López', 'Shorter', '"2"'))
        self.assertEqual((self.folder / 'extraction' / 'v1.json').read_bytes(), v1)   # never changed
        self.assertEqual(self.client.get(f'{API}/extraction').json()['text'], 'Write a short prompt.')
        self.assertEqual(self.client.get(f'{API}/normalization').json()['n'], 1)   # the other kind is its own
        listed = self.client.get(f'{API}/extraction/versions').json()['versions']
        self.assertEqual([(v['n'], v['used_by']) for v in listed], [(2, 0), (1, 0)])

    def test_a_stale_version_is_refused(self):   # AC-T09
        self.save('extraction', 'Second.', '1')
        r = self.save('extraction', 'Third.', '"1"')
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['details'], r.headers['etag']),
                         (409, 'version_conflict', {'current': 2}, '"2"'))
        r = self.client.post(f'{API}/extraction/versions', json={'text': 'x'})
        self.assertEqual((r.status_code, r.json()['error']['code']), (428, 'precondition_required'))
        self.assertEqual(sorted(p.name for p in (self.folder / 'extraction').iterdir()), ['v1.json', 'v2.json'])

    def test_restore_makes_a_new_version(self):   # AC-T10
        self.save('extraction', 'Second.', '"1"')
        r = self.client.post(f'{API}/extraction/versions/1/restore', headers={'If-Match': '"2"'})
        self.assertEqual((r.status_code, r.json()['n'], r.json()['note']), (201, 3, 'Restored from v1'))
        v3 = self.client.get(f'{API}/extraction/versions/3').json()
        self.assertEqual((v3['text'], v3['restored_from']), (SEED_TEXT['extraction'], 1))
        self.assertEqual(self.client.get(f'{API}/extraction/versions').json()['versions'][0]['restored_from'], 1)
        r = self.client.post(f'{API}/extraction/versions/9/restore', headers={'If-Match': '"3"'})
        self.assertEqual((r.status_code, r.json()['error']['code']), (404, 'version_not_found'))

    def test_invalid_requests(self):
        for body in ({'text': ''}, {'text': 'x' * 20001}, {'text': 'x', 'extra': 1}, {'note': 'x'}):
            r = self.client.post(f'{API}/extraction/versions', json=body, headers={'If-Match': '"1"'})
            self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'invalid_request'), body)
        r = self.save('extraction', '   \n ', '"1"')
        self.assertEqual((r.status_code, r.json()['error']['details']['pointers'][0]['pointer']), (400, '/body/text'))
        for path in (f'{API}/other', f'{API}/other/versions', f'{API}/other/versions/1'):
            r = self.client.get(path)
            self.assertEqual((r.status_code, r.json()['error']['code']), (404, 'system_prompt_not_found'), path)
        self.assertEqual(self.client.get(f'{API}/extraction/versions/0').status_code, 404)
        self.assertEqual(self.client.get(f'{API}/extraction/versions').json()['versions'][0]['n'], 1)

    def test_numbers_are_never_reused_and_damaged_files_reported(self):   # BR-T06
        self.save('extraction', 'Second.', '"1"')
        (self.folder / 'extraction' / 'v2.json').write_text('{ not json', encoding='utf-8')
        body = self.client.get(f'{API}/extraction').json()
        self.assertEqual((body['n'], body['problems']), (1, ['v2.json: JSONDecodeError']))
        r = self.save('extraction', 'Third.', '"1"')
        self.assertEqual(r.json()['n'], 3)
        self.assertEqual(self.client.get(f'{API}/extraction/versions').json()['problems'], ['v2.json: JSONDecodeError'])
        self.assertEqual((self.folder / 'extraction' / 'v2.json').read_text(encoding='utf-8'), '{ not json')

    def test_disk_errors(self):   # AC-T12
        self.client.get(API)
        with mock.patch.object(SystemPromptStore, 'write_version', side_effect=StorageError('Could not write v2.json: Access is denied')):
            r = self.save('extraction', 'Second.', '"1"')
        self.assertEqual((r.status_code, r.json()['error']['code']), (500, 'storage_error'))
        self.assertEqual(self.client.get(f'{API}/extraction').json()['n'], 1)


class Store(unittest.TestCase):
    def test_seed_is_made_once_and_versions_written_once(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            store = SystemPromptStore(Path(tmp) / 'system-prompts')
            store.seed('normalization', '2026-11-26T10:00:00Z')
            store.seed('normalization', '2026-11-27T10:00:00Z')
            self.assertEqual(store.current('normalization')[1]['saved_at'], '2026-11-26T10:00:00Z')
            with self.assertRaises(StorageError):
                store.write_version('normalization', store.current('normalization')[1])
            self.assertFalse(store.exists('extraction'))
            self.assertEqual([p.name for p in Path(tmp, 'system-prompts').iterdir()], ['normalization'])


if __name__ == '__main__':
    unittest.main()
