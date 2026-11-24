"""Tests of the Schema section's service (22-schema-interface-contract.md, OP-S01 to OP-S09 and OP-S12).

Covers AC-S01 to AC-S09, AC-S12 to AC-S14, BR-S02 to BR-S06, BR-S09 and BR-S10 on temporary data folders, plus the
rules module and the store on their own.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import schemas  # noqa: E402
from value_review.domain.schema_rules import check_schema  # noqa: E402
from value_review.ingest import features  # noqa: E402
from value_review.storage import StorageError  # noqa: E402
from value_review.storage.schemas import SchemaStore, empty_content  # noqa: E402
from value_review.tests.test_service import Base  # noqa: E402

API = '/api/v1/schemas'


def field(field_id, name, **extra):
    return {'field_id': field_id, 'name': name, 'description': '', 'type': 'text', 'unit': '', 'allowed': [],
            'multiple': False, 'formula': '', 'inputs': [], 'family': None, **extra}


def content(*groups):
    return {'schema': 'value-review-schema/1', 'description': '', 'groups': list(groups)}


def group(group_id, name, *fields):
    return {'group_id': group_id, 'name': name, 'fields': list(fields)}


ONE = content(group('g_1', 'Tensile properties', field('f_1', 'Yield strength', type='number', unit='MPa')))


class Rules(unittest.TestCase):   # BR-S03, BR-S04
    def test_valid_content_has_no_problems(self):
        self.assertEqual(check_schema(ONE), [])

    def test_names(self):
        c = content(group('g_1', 'Props', field('f_1', 'Yield  strength'), field('f_2', 'yield strength'), field('f_3', '  ')),
                    group('g_2', 'props'))
        self.assertEqual(check_schema(c), [
            {'ref': '/groups/0/fields/1/name', 'rule': 'duplicate_name'},
            {'ref': '/groups/0/fields/2/name', 'rule': 'empty_name'},
            {'ref': '/groups/1/name', 'rule': 'duplicate_name'}])

    def test_same_field_name_in_two_groups_is_allowed(self):
        c = content(group('g_1', 'A', field('f_1', 'Width')), group('g_2', 'B', field('f_2', 'Width')))
        self.assertEqual(check_schema(c), [])

    def test_ids(self):
        c = content(group('g_1', 'A', field('f_1', 'x'), field('f_1', 'y')), group('f_1', 'B'))
        self.assertEqual([p['rule'] for p in check_schema(c)], ['duplicate_id', 'duplicate_id'])

    def test_type_rules(self):
        c = content(group('g_1', 'A',
                          field('f_1', 'Material', unit='mm'),
                          field('f_2', 'Group', allowed=['SS316']),
                          field('f_3', 'Ratio', type='calculated', inputs=['f_1', 'f_3', 'gone']),
                          field('f_4', 'Plain', inputs=['f_1'])))
        self.assertEqual(check_schema(c), [
            {'ref': '/groups/0/fields/0/unit', 'rule': 'unit_not_allowed'},
            {'ref': '/groups/0/fields/1/allowed', 'rule': 'allowed_not_allowed'},
            {'ref': '/groups/0/fields/2/formula', 'rule': 'formula_required'},
            {'ref': '/groups/0/fields/2/inputs/1', 'rule': 'self_reference'},
            {'ref': '/groups/0/fields/2/inputs/2', 'rule': 'unknown_input'},
            {'ref': '/groups/0/fields/3/inputs', 'rule': 'inputs_not_allowed'}])

    def test_category_and_calculated_are_fine_when_complete(self):
        c = content(group('g_1', 'A', field('f_1', 'Width', type='number', unit='mm'), field('f_2', 'Length', type='number', unit='mm'),
                          field('f_3', 'Aspect ratio', type='calculated', formula='Length ÷ Width', inputs=['f_2', 'f_1']),
                          field('f_4', 'Treatment', type='category', allowed=['Solution Annealed', 'Stress Relieved'], multiple=True)))
        self.assertEqual(check_schema(c), [])


class Store(unittest.TestCase):   # BR-S05, BR-S06, BR-S09
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SchemaStore(Path(self.tmp.name) / 'schemas')

    def tearDown(self):
        self.tmp.cleanup()

    def version(self, n):
        return {'schema': 'value-review-schema-version/1', 'schema_id': 'a', 'n': n, 'saved_at': '2026-11-23T10:00:00Z',
                'saved_by': 'R', 'note': '', 'content': ONE}

    def test_numbers_are_never_reused_and_versions_never_replaced(self):
        for n in (1, 2, 3):
            self.store.write_version('a', self.version(n))
        self.store.version_path('a', 3).write_text('{', encoding='utf-8')   # unreadable newest
        k, latest, nxt, problems = self.store.current('a')
        self.assertEqual((k, latest['n'], nxt, len(problems)), (2, 2, 4, 1))
        with self.assertRaises(StorageError):
            self.store.write_version('a', self.version(2))

    def test_prune_keeps_the_newest(self):
        for n in range(1, 6):
            self.store.write_version('a', self.version(n))
        self.assertEqual(self.store.prune('a', 3), [2, 1])
        self.assertEqual(self.store.version_numbers('a'), [5, 4, 3])

    def test_trash_keeps_the_id_taken(self):
        self.store.write_version('sic', self.version(1))
        self.store.trash('sic', '20261123T100000Z')
        self.assertFalse(self.store.schema_dir('sic').exists())
        self.assertTrue((self.store.folder / '.trash' / 'sic.20261123T100000Z' / 'versions' / 'v1.json').exists())
        self.assertEqual(self.store.new_id('SiC'), 'sic-2')


class SchemasApi(Base):
    def create(self, name='SiC composites', **body):
        r = self.client.post(API, json={'name': name, **body})
        self.assertEqual(r.status_code, 201, r.text)
        return r

    def save(self, sid, c, version, note=''):
        return self.client.post(f'{API}/{sid}/versions', json={'content': c, 'note': note}, headers={'If-Match': f'"{version}"'})

    @property
    def folder(self):
        return self.config.annotations / 'schemas'

    # --- OP-S01 and the seed -------------------------------------------------------
    def test_seed_from_features(self):   # AC-S01, BR-S10
        rows = self.client.get(API).json()['schemas']
        self.assertEqual([(r['schema_id'], r['name'], r['version'], r['status'], r['fields'], r['groups']) for r in rows],
                         [('tensile-properties', 'Tensile properties', 1, 'saved', 54, 4)])
        v1 = self.client.get(f'{API}/tensile-properties/versions/1').json()
        self.assertEqual(schemas.errors('schema-version', v1), [])
        ids = [f['field_id'] for g in v1['content']['groups'] for f in g['fields']]
        self.assertEqual(ids, [f for f, _ in features.FEATURES])
        family = [f['family']['member'] for g in v1['content']['groups'] for f in g['fields'] if f['family']]
        self.assertEqual(family, [sym for _, sym in features.ELEMENTS])
        self.assertTrue(all(f['type'] == 'text' and f['unit'] == '' for g in v1['content']['groups'] for f in g['fields']))

    def test_seed_runs_once(self):   # BR-S10: deleting the seed does not bring it back
        self.client.get(API)
        self.assertEqual(self.client.delete(f'{API}/tensile-properties').status_code, 204)
        self.assertEqual(self.client.get(API).json()['schemas'], [])

    def test_seed_failure_leaves_no_folder(self):
        with mock.patch('value_review.storage.schemas.SchemaStore.write_version', side_effect=StorageError('disk full')):
            r = self.client.get(API)
        self.assertEqual((r.status_code, r.json()['error']['code']), (500, 'storage_error'))
        self.assertFalse(self.folder.exists())
        self.assertEqual(len(self.client.get(API).json()['schemas']), 1)   # tried again

    # --- the first workflow: create, draft, save v1 ------------------------------------------
    def test_create_blank_then_save_v1(self):   # AC-S02, AC-S03, AC-S14
        r = self.create()
        self.assertEqual(r.headers['Location'], f'{API}/sic-composites')
        self.assertEqual(r.headers['ETag'], '"0"')
        body = r.json()
        self.assertEqual((body['version'], body['content'], body['draft']['base_version'], body['draft']['content']),
                         (0, empty_content(), 0, empty_content()))
        row = next(x for x in self.client.get(API).json()['schemas'] if x['schema_id'] == 'sic-composites')
        self.assertEqual((row['status'], row['version']), ('new', 0))
        self.assertFalse((self.folder / 'sic-composites' / 'versions').exists())

        put = self.client.put(f'{API}/sic-composites/draft', json={'base_version': 0, 'content': ONE})
        self.assertEqual(put.status_code, 200)
        reopened = self.client.get(f'{API}/sic-composites').json()
        self.assertEqual(reopened['draft']['content'], ONE)   # AC-S14: the draft survives a reload

        self.client.put('/api/v1/settings', json={'reviewer_name': 'Dr. R', 'keep_versions': 20, 'autosave_minutes': 5})
        saved = self.save('sic-composites', ONE, 0)
        self.assertEqual((saved.status_code, saved.json()['n'], saved.json()['saved_by'], saved.headers['ETag']), (201, 1, 'Dr. R', '"1"'))
        self.assertEqual(saved.headers['Location'], f'{API}/sic-composites/versions/1')
        v1 = json.loads((self.folder / 'sic-composites' / 'versions' / 'v1.json').read_text(encoding='utf-8'))
        self.assertEqual(schemas.errors('schema-version', v1), [])
        self.assertFalse((self.folder / 'sic-composites' / 'draft.json').exists())
        row = next(x for x in self.client.get(API).json()['schemas'] if x['schema_id'] == 'sic-composites')
        self.assertEqual((row['status'], row['version'], row['fields'], row['modified_by']), ('saved', 1, 1, 'Dr. R'))

    def test_rules_violation_writes_nothing(self):   # AC-S04
        self.create()
        self.client.put(f'{API}/sic-composites/draft', json={'base_version': 0, 'content': ONE})
        bad = content(group('g_1', 'Tensile properties', field('f_1', 'Yield strength'), field('f_2', 'Yield strength')))
        r = self.save('sic-composites', bad, 0)
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'rules_violation'))
        self.assertEqual(r.json()['error']['details']['items'], [{'ref': '/groups/0/fields/1/name', 'rule': 'duplicate_name'}])
        self.assertFalse((self.folder / 'sic-composites' / 'versions').exists())
        self.assertTrue((self.folder / 'sic-composites' / 'draft.json').exists())   # the draft is kept

    def test_stale_or_missing_if_match(self):   # AC-S05
        self.create()
        self.assertEqual(self.save('sic-composites', ONE, 0).status_code, 201)
        self.client.put(f'{API}/sic-composites/draft', json={'base_version': 1, 'content': ONE})
        r = self.save('sic-composites', ONE, 0)
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['details'], r.headers['ETag']),
                         (409, 'version_conflict', {'current': 1}, '"1"'))
        self.assertTrue((self.folder / 'sic-composites' / 'draft.json').exists())
        r = self.client.post(f'{API}/sic-composites/versions', json={'content': ONE})
        self.assertEqual(r.status_code, 428)
        r = self.client.put(f'{API}/sic-composites/draft', json={'base_version': 0, 'content': ONE})
        self.assertEqual((r.status_code, r.json()['error']['details']), (409, {'current': 1}))

    def test_bad_shape(self):
        self.create()
        broken = content(group('g_1', 'A', {**field('f_1', 'x'), 'type': 'float'}))
        for r in (self.client.put(f'{API}/sic-composites/draft', json={'base_version': 0, 'content': broken}),
                  self.save('sic-composites', broken, 0)):
            self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'invalid_request'))
            self.assertTrue(r.json()['error']['details']['pointers'][0]['pointer'].startswith('/content/groups/0/fields/0'))

    def test_rename_keeps_the_id_and_reorder_keeps_ids(self):   # AC-S06, AC-S07, BR-S02
        self.create()
        a, b, c = field('f_1', 'A'), field('f_2', 'B'), field('f_3', 'C')
        self.save('sic-composites', content(group('g_1', 'G1', a, b), group('g_2', 'G2', c)), 0)
        moved = content(group('g_2', 'G2', {**b, 'name': 'B renamed'}, c), group('g_1', 'G1', a))
        self.assertEqual(self.save('sic-composites', moved, 1).status_code, 201)
        v2 = self.client.get(f'{API}/sic-composites/versions/2').json()['content']
        self.assertEqual([(g['group_id'], [f['field_id'] for f in g['fields']]) for g in v2['groups']],
                         [('g_2', ['f_2', 'f_3']), ('g_1', ['f_1'])])
        self.assertEqual(v2['groups'][0]['fields'][0]['name'], 'B renamed')

    def test_deleted_field_stays_in_earlier_versions(self):   # BR-S07
        self.create()
        self.save('sic-composites', ONE, 0)
        self.save('sic-composites', content(group('g_1', 'Tensile properties')), 1)
        v1 = self.client.get(f'{API}/sic-composites/versions/1').json()['content']
        self.assertEqual(v1, ONE)

    def test_calculated_with_a_deleted_input(self):   # AC-S12
        self.create()
        c = content(group('g_1', 'A', field('f_2', 'Ratio', type='calculated', formula='Length ÷ Width', inputs=['f_1'])))
        r = self.save('sic-composites', c, 0)
        self.assertEqual(r.json()['error']['details']['items'], [{'ref': '/groups/0/fields/0/inputs/0', 'rule': 'unknown_input'}])

    # --- versions, restore, pruning --------------------------------------------------------
    def test_versions_and_restore(self):   # AC-S08, OP-S06, OP-S07
        self.create()
        contents = [ONE, content(group('g_1', 'Second')), content(group('g_1', 'Third'))]
        for i, c in enumerate(contents):
            self.save('sic-composites', c, i)
        self.client.put(f'{API}/sic-composites/draft', json={'base_version': 3, 'content': ONE})
        r = self.client.post(f'{API}/sic-composites/versions/1/restore', headers={'If-Match': '"3"'})
        self.assertEqual((r.status_code, r.json()['n'], r.json()['note']), (201, 4, 'Restored from v1'))
        listed = self.client.get(f'{API}/sic-composites/versions').json()
        self.assertEqual([v['n'] for v in listed['versions']], [4, 3, 2, 1])
        self.assertEqual(self.client.get(f'{API}/sic-composites/versions/4').json()['content'], ONE)
        self.assertFalse((self.folder / 'sic-composites' / 'draft.json').exists())
        r = self.client.post(f'{API}/sic-composites/versions/1/restore', headers={'If-Match': '"3"'})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.client.get(f'{API}/sic-composites/versions/9').status_code, 404)

    def test_keep_schema_versions(self):   # AC-S09, OP-S12
        self.client.put('/api/v1/settings', json={'reviewer_name': 'R', 'keep_versions': 20, 'autosave_minutes': 5, 'keep_schema_versions': 3})
        self.assertEqual(self.client.get('/api/v1/settings').json()['keep_schema_versions'], 3)
        self.create()
        for k in range(4):
            self.assertEqual(self.save('sic-composites', content(group('g_1', f'G{k}')), k).status_code, 201)
        self.assertEqual([v['n'] for v in self.client.get(f'{API}/sic-composites/versions').json()['versions']], [4, 3, 2])
        self.assertEqual(self.save('sic-composites', ONE, 4).json()['n'], 5)   # numbers are not reused after pruning
        # Settings saved without the field keep it (the settings dialog of Review does not send it).
        self.client.put('/api/v1/settings', json={'reviewer_name': 'R', 'keep_versions': 20, 'autosave_minutes': 5})
        self.assertEqual(self.client.get('/api/v1/settings').json()['keep_schema_versions'], 3)

    # --- create variants, rename, delete -----------------------------------------------------
    def test_copy_and_import_content(self):   # OP-S02
        self.create()
        self.save('sic-composites', ONE, 0)
        copy = self.create('SiC copy', **{'from': {'schema_id': 'sic-composites', 'version': 1}}).json()
        self.assertEqual((copy['schema_id'], copy['draft']['content'], copy['version']), ('sic-copy', ONE, 0))
        imported = self.create('Imported', content=ONE).json()
        self.assertEqual(imported['draft']['content'], ONE)
        r = self.client.post(API, json={'name': 'x', 'from': {'schema_id': 'nope', 'version': 1}})
        self.assertEqual((r.status_code, r.json()['error']['code']), (404, 'schema_not_found'))
        r = self.client.post(API, json={'name': 'x', 'from': {'schema_id': 'sic-composites', 'version': 1}, 'content': ONE})
        self.assertEqual(r.status_code, 400)

    def test_names_of_schemas(self):
        for name in ('', '   ', 'x' * 121):
            r = self.client.post(API, json={'name': name})
            self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'rules_violation'), name)
        self.create('SiC composites')
        self.assertEqual(self.create('SiC composites').json()['schema_id'], 'sic-composites-2')

    def test_rename_is_not_a_version(self):   # OP-S08
        self.create()
        r = self.client.patch(f'{API}/sic-composites', json={'name': '  SiC fibres '})
        self.assertEqual(r.json(), {'schema_id': 'sic-composites', 'name': 'SiC fibres'})
        opened = self.client.get(f'{API}/sic-composites').json()
        self.assertEqual((opened['name'], opened['version']), ('SiC fibres', 0))
        self.assertEqual(self.client.patch(f'{API}/sic-composites', json={'name': ''}).status_code, 422)

    def test_delete_moves_to_trash(self):   # AC-S13, BR-S09
        self.create()
        self.save('sic-composites', ONE, 0)
        self.assertEqual(self.client.delete(f'{API}/sic-composites').status_code, 204)
        self.assertNotIn('sic-composites', [r['schema_id'] for r in self.client.get(API).json()['schemas']])
        trashed = list((self.folder / '.trash').iterdir())
        self.assertEqual(len(trashed), 1)
        self.assertTrue((trashed[0] / 'versions' / 'v1.json').exists())
        self.assertEqual(self.client.get(f'{API}/sic-composites').status_code, 404)
        self.assertEqual(self.create().json()['schema_id'], 'sic-composites-2')

    def test_unknown_schema(self):
        for r in (self.client.get(f'{API}/nope'), self.client.get(f'{API}/Bad%20Id'), self.client.delete(f'{API}/nope'),
                  self.client.put(f'{API}/nope/draft', json={'base_version': 0, 'content': ONE}),
                  self.client.post(f'{API}/nope/versions', json={'content': ONE}, headers={'If-Match': '"0"'})):
            self.assertEqual((r.status_code, r.json()['error']['code']), (404, 'schema_not_found'))

    def test_storage_failure_on_save_keeps_the_draft(self):
        self.create()
        self.client.put(f'{API}/sic-composites/draft', json={'base_version': 0, 'content': ONE})
        with mock.patch('value_review.storage.schemas.SchemaStore.write_version', side_effect=StorageError('disk full')):
            r = self.save('sic-composites', ONE, 0)
        self.assertEqual((r.status_code, r.json()['error']['code']), (500, 'storage_error'))
        self.assertTrue((self.folder / 'sic-composites' / 'draft.json').exists())
        self.assertEqual(self.save('sic-composites', ONE, 0).status_code, 201)

    def test_review_is_unchanged(self):   # ADR-012: Review still reads features.py
        self.client.get(API)
        paper = self.client.get('/api/v1/papers/7').json()
        self.assertEqual(paper['feature_catalog'][0], {'feature_id': 'material', 'label': 'Material'})


if __name__ == '__main__':
    unittest.main()
