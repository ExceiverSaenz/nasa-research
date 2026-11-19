"""Tests of submit, versions and exports (step 4): OP-05, OP-06, OP-07, OP-09.

Covers AC-03 to AC-08, BR-01, BR-03, BR-04, BR-05, BR-11, BR-12. Synthetic paper 7 from test_ingest:
values o1 (710 ± 25 MPa, r1), o2 (ambiguous), o3 (derived, r2), o4 (candidate only, r2).
"""
import csv
import io
import json
import sys
import unittest
import zipfile
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient  # noqa: E402

from value_review import schemas  # noqa: E402
from value_review.domain.materialize import values as materialize  # noqa: E402
from value_review.domain.rules import check_state  # noqa: E402
from value_review.domain.state import empty_state  # noqa: E402
from value_review.service.app import create_app  # noqa: E402
from value_review.storage import StorageError  # noqa: E402
from value_review.storage.files import AnnotationStore  # noqa: E402
from value_review.tests.test_ingest import sha  # noqa: E402
from value_review.tests.test_service import Base  # noqa: E402

BY, AT = 'Expert reviewer', '2026-11-16T10:00:00Z'
URL = '/api/v1/papers/7/versions'


def d(verdict, note='', **extra):
    return {'verdict': verdict, 'note': note, 'by': BY, 'at': AT, **extra}


def three_decisions():
    s = empty_state()
    s['decisions'] = {'o1': d('corrected', value='710 ± 26', unit='MPa'),
                      'o2': d('rejected', 'It belongs to another record'),
                      'o3': d('accepted')}
    return s


def full_state():
    """Every kind of reviewer edit (AC-14, AC-15 data side)."""
    s = three_decisions()
    s['column_moves'] = {'o4': {'feature_id': 'strain_rate', 'by': BY, 'at': AT}}
    s['record_moves'] = {'o3': {'record_ids': ['u_1'], 'by': BY, 'at': AT}}
    s['record_edits'] = {'r1': {'label': 'SS-J (FeCrAl)', 'summary': 'FeCrAl, RT, 0.75 mm', 'by': BY, 'at': AT}}
    s['added_records'] = [{'record_id': 'u_1', 'label': 'SS-Mini 2E-0.4', 'summary': 'Long gauge', 'by': BY, 'at': AT}]
    s['added_values'] = [{'observation_id': 'u_2', 'record_ids': ['u_1'], 'feature_id': 'yield_strength', 'value': '705 ± 50',
                          'unit': 'MPa', 'note': 'Table 2, row 2E-0.4', 'by': BY, 'at': AT}]
    s['boxes'] = {'o1': {'removed': ['e2'], 'redrawn': {'e1': {'page': 1, 'bbox': [0.5, 0.38, 0.58, 0.4], 'by': BY, 'at': AT}},
                         'added': [{'page': 2, 'bbox': [0.1, 0.1, 0.2, 0.2], 'by': BY, 'at': AT}]}}
    return s


class Versions(Base):
    def setUp(self):
        super().setUp()
        ticks = iter(range(10 ** 6))
        self.client.close()
        self.client = TestClient(create_app(self.config, web_dir=None, clock=lambda: f'2026-11-16T12:{next(ticks) // 60 % 60:02d}:{next(ticks) % 60:02d}Z'),
                                 base_url='http://127.0.0.1')

    def submit(self, state, match='"0"'):
        headers = {} if match is None else {'If-Match': match}
        return self.client.post(URL, json={'state': state}, headers=headers)

    def files(self):
        return sorted(p.name for p in self.store.versions_dir('7').glob('*.json')) if self.store.versions_dir('7').is_dir() else []


class Submit(Versions):  # OP-05, AC-03, AC-05
    def test_first_submit_writes_v1(self):
        self.write_json(self.store.draft_path('7'), {'schema': 'value-review-draft/1', 'paper': '7', 'base_version': 0,
                                                     'trigger': 'manual', 'saved_at': AT, 'state': three_decisions()})
        before = (sha(self.res), sha(self.pdf), sha(self.data / 'originals' / '7.json'))
        r = self.submit(three_decisions())
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual((r.headers['etag'], r.headers['location']), ('"1"', '/api/v1/sources/default/papers/7/versions/1'))
        body = r.json()
        self.assertEqual((body['n'], body['by']), (1, BY))
        self.assertEqual(body['counts'], {'total': 4, 'pending': 1, 'accepted': 1, 'corrected': 1, 'rejected': 1, 'unsure': 0,
                                          'added_values': 0, 'added_records': 0, 'edited_records': 0})
        v1 = json.loads(self.store.version_path('7', 1).read_text(encoding='utf-8'))
        self.assertEqual(schemas.errors('version', v1), [])
        self.assertEqual((v1['base_version'], v1['note'], v1['state']), (0, 'Submitted', three_decisions()))
        self.assertEqual(v1['source']['original_sha256'], before[2])
        o1 = v1['values'][0]
        self.assertEqual((o1['status'], o1['value'], o1['unit'], o1['original_value']), ('corrected', '710 ± 26', 'MPa', '710 ± 25'))  # BR-05
        self.assertFalse(self.store.draft_path('7').exists())
        self.assertEqual((sha(self.res), sha(self.pdf), sha(self.data / 'originals' / '7.json')), before)  # BR-01
        paper = self.client.get('/api/v1/papers').json()[0]
        self.assertEqual((paper['version'], paper['latest']['n'], paper['reviewed'], paper['status']), (1, 1, 3, 'in_progress'))

    def test_reviewer_name_comes_from_settings(self):
        self.client.put('/api/v1/settings', json={'reviewer_name': 'Dr. Reviewer', 'keep_versions': 20, 'autosave_minutes': 5})
        self.assertEqual(self.submit(three_decisions()).json()['by'], 'Dr. Reviewer')

    def test_stale_or_missing_if_match(self):  # AC-06, BR-11
        self.assertEqual(self.submit(three_decisions()).status_code, 201)
        r = self.submit(three_decisions(), '"0"')
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['details'], r.headers['etag']),
                         (409, 'version_conflict', {'current': 1}, '"1"'))
        r = self.submit(three_decisions(), None)
        self.assertEqual((r.status_code, r.json()['error']['code']), (428, 'precondition_required'))
        self.assertEqual(self.submit(three_decisions(), 'abc').status_code, 400)
        self.assertEqual(self.files(), ['v1.json'])
        self.assertEqual(self.submit(three_decisions(), 'W/"1"').status_code, 201)
        self.assertEqual(self.files(), ['v1.json', 'v2.json'])

    def test_reason_required_for_reject_and_unsure(self):  # AC-04, BR-04
        for verdict in ('rejected', 'unsure'):
            s = empty_state()
            s['decisions'] = {'o1': d(verdict, '   ')}
            r = self.submit(s)
            self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'rules_violation'))
            self.assertEqual(r.json()['error']['details']['items'], [{'ref': 'o1', 'rule': 'reason_required'}])
        self.assertEqual(self.files(), [])

    def test_schema_violation(self):
        s = empty_state()
        s['decisions'] = {'o1': d('corrected')}   # no value
        r = self.submit(s)
        self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'invalid_request'))
        self.assertEqual(self.client.post(URL, json={'state': {}, 'extra': 1}, headers={'If-Match': '0'}).status_code, 400)
        self.assertEqual(self.files(), [])

    def test_unknown_references(self):
        s = empty_state()
        s['decisions'] = {'o9': d('accepted')}
        s['column_moves'] = {'o1': {'feature_id': 'not_a_feature', 'by': BY, 'at': AT}}
        s['record_moves'] = {'o1': {'record_ids': ['r9'], 'by': BY, 'at': AT}}
        s['boxes'] = {'o1': {'removed': ['e9'], 'redrawn': {}, 'added': [{'page': 5, 'bbox': [0.3, 0.3, 0.2, 0.4], 'by': BY, 'at': AT}]}}
        s['added_records'] = [{'record_id': 'u_1', 'label': 'a', 'summary': '', 'by': BY, 'at': AT}]
        s['added_values'] = [{'observation_id': 'u_1', 'record_ids': ['r1'], 'feature_id': 'yield_strength', 'value': '1', 'unit': '',
                              'note': '', 'by': BY, 'at': AT}]
        r = self.submit(s)
        self.assertEqual(r.status_code, 422)
        rules = {(i['ref'], i['rule']) for i in r.json()['error']['details']['items']}
        self.assertEqual(rules, {('u_1', 'duplicate_id'), ('o9', 'unknown_observation'), ('o1', 'unknown_feature'),
                                 ('o1:r9', 'unknown_record'), ('o1:e9', 'unknown_evidence'), ('o1:page 5', 'page_out_of_range'),
                                 ('o1:box 0', 'empty_box')})

    def test_unknown_references_in_every_part_of_the_working_copy(self):  # check_state, one bad reference per kind
        s = empty_state()
        s['column_moves'] = {'o9': {'feature_id': 'strain_rate', 'by': BY, 'at': AT}}       # value not in the paper
        s['record_moves'] = {'o8': {'record_ids': ['r1'], 'by': BY, 'at': AT}}              # value not in the paper
        s['record_edits'] = {'r9': {'label': 'x', 'summary': '', 'by': BY, 'at': AT}}       # record not in the paper
        s['added_values'] = [{'observation_id': 'u_2', 'record_ids': ['r9'], 'feature_id': 'not_a_feature', 'value': '1',
                              'unit': '', 'note': '', 'by': BY, 'at': AT}]
        s['boxes'] = {
            # unknown value: reported once; its boxes are not checked further (no evidence or page problems for o7)
            'o7': {'removed': ['e9'], 'redrawn': {}, 'added': [{'page': 9, 'bbox': [0.3, 0.3, 0.2, 0.4], 'by': BY, 'at': AT}]},
            # a value the reviewer added has no model evidence to remove or redraw
            'u_2': {'removed': ['e1'], 'redrawn': {}, 'added': []},
        }
        before = self.files()
        r = self.submit(s)
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'rules_violation'))
        rules = sorted((i['ref'], i['rule']) for i in r.json()['error']['details']['items'])
        self.assertEqual(rules, sorted([('o9', 'unknown_observation'), ('o8', 'unknown_observation'), ('r9', 'unknown_record'),
                                        ('u_2', 'unknown_feature'), ('u_2:r9', 'unknown_record'),
                                        ('o7', 'unknown_observation'), ('u_2:e1', 'unknown_evidence')]))
        self.assertEqual(self.files(), before)   # nothing written
        r = self.client.put('/api/v1/papers/7/draft', json={'base_version': 0, 'trigger': 'manual', 'state': s})
        self.assertEqual((r.status_code, len(r.json()['error']['details']['items'])), (422, 7))   # drafts are checked too

    def test_source_changed_blocks_submit(self):  # AC-18
        self.res.write_text(self.res.read_text(encoding='utf-8').replace('710', '711'), encoding='utf-8')
        r = self.submit(three_decisions())
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'source_changed'))
        self.assertEqual(self.files(), [])

    def test_unknown_paper(self):
        self.assertEqual(self.client.post('/api/v1/papers/8/versions', json={'state': empty_state()}, headers={'If-Match': '0'}).status_code, 404)


class StorageFailures(Versions):  # WB-12, WB-13 (11-white-box-coverage-review.md)
    def save_draft(self):
        r = self.client.put('/api/v1/papers/7/draft', json={'base_version': 0, 'trigger': 'manual', 'state': three_decisions()})
        self.assertEqual(r.status_code, 200, r.text)
        return self.store.draft_path('7').read_bytes()

    def test_wb12_version_write_fails(self):
        draft = self.save_draft()
        with mock.patch.object(AnnotationStore, 'write_version', side_effect=StorageError('disk full')):
            r = self.submit(three_decisions())
        self.assertEqual((r.status_code, r.json()['error']['code']), (500, 'storage_error'))
        self.assertEqual(self.files(), [])
        self.assertEqual(self.store.draft_path('7').read_bytes(), draft)   # the reviewer's work is kept
        self.assertEqual(self.submit(three_decisions()).status_code, 201)  # and the next try works, as v1

    def test_wb13_prune_fails_after_the_version_is_written(self):
        self.save_draft()
        with mock.patch.object(AnnotationStore, 'prune', side_effect=StorageError('locked')), \
                self.assertLogs('value_review', 'WARNING') as logs:
            r = self.submit(three_decisions())
        self.assertEqual((r.status_code, r.json()['n']), (201, 1))
        self.assertEqual(self.files(), ['v1.json'])
        self.assertIn('locked', logs.output[0])
        opened = self.client.get('/api/v1/papers/7').json()
        self.assertEqual((opened['version'], opened['draft'], opened['draft_stale']), (1, None, False))   # draft still deleted

    def test_wb13_draft_delete_fails_after_the_version_is_written(self):
        self.save_draft()
        with mock.patch.object(AnnotationStore, 'delete_draft', side_effect=StorageError('locked')), \
                self.assertLogs('value_review', 'WARNING'):
            r = self.submit(three_decisions())
        self.assertEqual((r.status_code, self.files()), (201, ['v1.json']))
        self.assertTrue(self.client.get('/api/v1/papers/7').json()['draft_stale'])   # left behind, offered only to discard


class Pruning(Versions):  # AC-07, BR-03
    def test_twenty_one_versions_keep_twenty(self):
        for k in range(21):
            self.assertEqual(self.submit(three_decisions(), f'"{k}"').status_code, 201)
        self.assertEqual(sorted(int(n[1:-5]) for n in self.files()), list(range(2, 22)))
        listed = self.client.get(URL).json()
        self.assertEqual([v['n'] for v in listed], list(range(21, 1, -1)))
        self.assertEqual(self.client.get(f'{URL}/1').status_code, 404)

    def test_lower_limit_prunes_on_next_write(self):
        for k in range(4):
            self.submit(three_decisions(), f'"{k}"')
        self.client.put('/api/v1/settings', json={'reviewer_name': BY, 'keep_versions': 2, 'autosave_minutes': 5})
        self.assertEqual(len(self.files()), 4)   # not immediately
        self.submit(three_decisions(), '"4"')
        self.assertEqual(self.files(), ['v4.json', 'v5.json'])

    def test_numbers_never_reused_after_an_unreadable_file(self):
        self.submit(three_decisions())
        (self.store.version_path('7', 2)).write_text('{broken', encoding='utf-8')
        self.assertEqual(self.client.get('/api/v1/papers/7').headers['etag'], '"1"')
        r = self.submit(three_decisions(), '"1"')
        self.assertEqual(r.json()['n'], 3)
        self.assertEqual(self.store.version_path('7', 2).read_text(encoding='utf-8'), '{broken')
        self.assertEqual(self.client.get(f'{URL}/2').json()['error']['code'], 'storage_error')


class ReadVersions(Versions):  # OP-06, OP-07
    def test_list_and_read(self):
        self.assertEqual(self.client.get(URL).json(), [])
        self.submit(three_decisions())
        listed = self.client.get(URL).json()
        self.assertEqual([(v['n'], v['note'], v['by']) for v in listed], [(1, 'Submitted', BY)])
        v1 = self.client.get(f'{URL}/1').json()
        self.assertEqual(v1['state'], three_decisions())
        self.assertEqual(self.client.get(f'{URL}/9').json()['error']['code'], 'version_not_found')
        self.assertEqual(self.client.get('/api/v1/papers/8/versions').status_code, 404)


class Exports(Versions):  # OP-09, AC-08, BR-12
    def setUp(self):
        super().setUp()
        r = self.submit(full_state())
        self.assertEqual(r.status_code, 201, r.text)

    def test_csv(self):
        r = self.client.get(f'{URL}/1/export.csv')
        self.assertEqual(r.headers['content-disposition'], 'attachment; filename="paper-7-v1.csv"')
        self.assertTrue(r.content.startswith('﻿'.encode('utf-8')))
        rows = list(csv.DictReader(io.StringIO(r.content.decode('utf-8-sig'))))
        self.assertEqual([x['observation_id'] for x in rows], ['o1', 'o2', 'o3', 'o4', 'u_2'])
        o1, o3, o4, u2 = rows[0], rows[2], rows[3], rows[4]
        self.assertEqual((o1['value'], o1['original_value'], o1['status'], o1['record'], o1['column']),
                         ('710 ± 26', '710 ± 25', 'corrected', 'SS-J (FeCrAl)', 'Yield strength'))
        self.assertEqual((o3['record'], o3['record_id'], o3['status']), ('SS-Mini 2E-0.4', 'u_1', 'accepted'))
        self.assertEqual((o4['feature_id'], o4['column'], o4['status'], o4['needs_check']), ('strain_rate', 'Strain rate', 'pending', 'yes'))
        self.assertEqual((u2['origin'], u2['value'], u2['original_value'], u2['note']), ('reviewer', '705 ± 50', '', 'Table 2, row 2E-0.4'))

    def test_json_validates_and_matches_csv(self):
        r = self.client.get(f'{URL}/1/export.json')
        self.assertEqual(r.headers['content-disposition'], 'attachment; filename="paper-7-v1.json"')
        data = r.json()
        self.assertEqual(schemas.errors('export', data), [])
        rows = list(csv.DictReader(io.StringIO(self.client.get(f'{URL}/1/export.csv').content.decode('utf-8-sig'))))
        for obs, row in zip(data['observations'], rows):
            self.assertEqual((obs['observation_id'], obs['review']['status'], obs['review']['value'] or ''),
                             (row['observation_id'], row['status'], row['value']))
        o1 = data['observations'][0]
        self.assertEqual((o1['value_as_reported'], o1['flags'], o1['evidence_ids']), ('710 ± 25', ['reported_aggregate'], ['e1', 'e2']))
        recs = {x['record_id']: x for x in data['records']}
        self.assertEqual((recs['r1']['source_label'], recs['r1']['model_label'], recs['r1']['origin']), ('SS-J (FeCrAl)', 'SS-J', 'model'))
        self.assertEqual(recs['u_1']['origin'], 'reviewer')
        ev = [e for e in data['evidence'] if e['observation_ids'] == ['o1']]
        self.assertEqual([(e['evidence_id'], e['origin'], e['removed'], e['bbox'], e['model_bbox']) for e in ev], [
            ('e1', 'model', False, [0.5, 0.38, 0.58, 0.4], [0.5262, 0.3837, 0.5763, 0.3932]),
            ('e2', 'model', True, None, None),
            ('o1#added1', 'reviewer', False, [0.1, 0.1, 0.2, 0.2], None)])
        self.assertEqual(data['observations'][-1]['review']['origin'], 'reviewer')

    def test_latest_zip(self):
        r = self.client.get('/api/v1/export/latest.zip')
        z = zipfile.ZipFile(io.BytesIO(r.content))
        self.assertEqual(sorted(z.namelist()), ['paper-7-v1.csv', 'paper-7-v1.json', 'summary.csv'])
        summary = list(csv.DictReader(io.StringIO(z.read('summary.csv').decode('utf-8-sig'))))
        self.assertEqual((summary[0]['paper'], summary[0]['version'], summary[0]['corrected'], summary[0]['added_values']), ('7', '1', '1', '1'))

    def test_missing_version_export(self):
        self.assertEqual(self.client.get(f'{URL}/4/export.csv').status_code, 404)


class Domain(Versions):  # pure functions
    def test_correction_without_unit_keeps_the_model_unit(self):
        s = empty_state()
        s['decisions'] = {'o1': d('corrected', value='711')}
        row = materialize(self.original, s)[0]
        self.assertEqual((row['value'], row['unit'], row['original_unit']), ('711', 'MPa', 'MPa'))

    def test_moves_are_traced_to_the_model(self):
        rows = {r['observation_id']: r for r in materialize(self.original, full_state())}
        self.assertEqual((rows['o4']['feature_id'], rows['o4']['original_feature_id']), ('strain_rate', 'some_new_feature'))
        self.assertEqual((rows['o3']['record_ids'], rows['o3']['original_record_ids']), (['u_1'], ['r2', 'r_missing']))
        self.assertIsNone(rows['o1']['original_feature_id'])

    def test_drafts_may_hold_an_unfinished_reason(self):
        s = empty_state()
        s['decisions'] = {'o1': d('rejected', '')}
        self.assertEqual(check_state(self.original, s, submit=False), [])
        self.assertEqual(check_state(self.original, s, submit=True), [{'ref': 'o1', 'rule': 'reason_required'}])

    def test_correction_needs_a_value_even_without_the_schema(self):
        # Through the API the schema refuses this first (400, test_schema_violation); check_state is the second line.
        s = empty_state()
        s['decisions'] = {'o1': d('corrected'), 'o3': d('corrected', value='   ')}
        for submit in (True, False):
            self.assertEqual(check_state(self.original, s, submit=submit),
                             [{'ref': 'o1', 'rule': 'value_required'}, {'ref': 'o3', 'rule': 'value_required'}])


if __name__ == '__main__':
    unittest.main()
