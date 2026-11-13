"""Exports and statistics (OP-09, OP-10, OP-11; AC-11, BR-10, BR-11, BR-21)."""
import copy
import csv
import io
import json
import unittest
import zipfile

from parsing_validator.domain import blank_state
from parsing_validator.domain.state import blank_block
from parsing_validator.service import exports
from parsing_validator.tests.test_service import API, REAL_ORIGINALS, Base


class Pure(unittest.TestCase):
    def test_control_characters_become_symbols(self):
        self.assertEqual(exports.symbols('a\x00b\x01c\x1fd\te\nf\rg'), 'a␀b␁c␟d\te\nf\rg')

    def test_auto_accept_does_not_change_the_input(self):
        review = {'pages': {'1': {'blocks': {'k1': {'status': 'pending'}, 'k2': {'status': 'rejected'}}}}}
        out = exports.auto_accept(review)
        self.assertEqual(out['pages']['1']['blocks']['k1'], {'status': 'accepted', 'auto_accepted': True})
        self.assertEqual(out['pages']['1']['blocks']['k2'], {'status': 'rejected'})
        self.assertEqual(review['pages']['1']['blocks']['k1'], {'status': 'pending'})

    def test_moved_blocks_are_the_fewest_that_explain_the_order(self):
        page = {'blocks': [{'id': f'k{i}', 'index': i} for i in range(6)]}
        self.assertEqual(exports._moved({'reading_order': ['k0', 'k1', 'k2', 'k3', 'k4', 'k5']}, page), [])
        swapped = exports._moved({'reading_order': ['k0', 'k1', 'k3', 'k2', 'k4', 'k5']}, page)
        self.assertEqual(len(swapped), 1)                  # either of the two explains it; the choice is deterministic
        self.assertIn(swapped[0], ('k2', 'k3'))
        self.assertEqual(exports._moved({'reading_order': ['k5', 'k0', 'k1', 'k2', 'k3', 'k4']}, page), ['k5'])
        self.assertEqual(exports._moved({'reading_order': ['k1', 'k2', 'k3', 'k4', 'k5', 'k0']}, page), ['k0'])
        self.assertEqual(exports._moved({'reading_order': ['k0', 'n1', 'k1']}, page), [])   # new blocks have no MinerU place

    def test_csv_quotes_everything_and_defuses_formulas(self):
        data = exports._csv(('a', 'b'), [['=1+1', 'x,"y"\n'], ['-5', 'ok']])
        self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
        rows = list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
        self.assertEqual(rows, [['a', 'b'], ["'=1+1", 'x,"y"\n'], ["'-5", 'ok']])
        self.assertNotIn(b',x', data.split(b'\r\n')[1][:3])   # every field is quoted, even the first


class Exports(Base):
    def blocks(self, original=None, page=7):
        original = original or self.original
        return [b['id'] for b in sorted(next(p for p in original['pages'] if p['index'] == page)['blocks'],
                                        key=lambda b: b['index'])]

    def save(self, state, paper='7', revision='0'):
        r = self.client.put(f'{API}/papers/{paper}/review', json={'state': state}, headers={'If-Match': f'"{revision}"'})
        self.assertEqual(r.status_code, 200, r.text)

    def decisions_state(self):
        """Page 7 with one example of every reason."""
        ids = self.blocks()
        state = blank_state(self.original)
        page = state['pages']['7']
        b = page['blocks']
        b[ids[0]]['status'] = 'rejected'
        b[ids[1]].update(status='accepted')
        b[ids[1]]['content'].update(status='wrong', error_types=['Wrong characters'])
        b[ids[2]]['tag']['value'] = 'footer' if b[ids[2]]['tag']['predicted'] != 'footer' else 'header'
        b[ids[3]].update(status='deleted', delete_reasons=['Scan noise'])
        page['reading_order'].remove(ids[3])
        b[ids[4]]['note'] = 'check | this\n=1+1 \x01'
        b[ids[5]]['layer_issues'] = [{'layer': 'missing', 'kinds': ['Line missed'], 'other': None, 'text': '', 'correction_bbox_pct': None, 'ref': None}]
        order = page['reading_order']
        i, j = order.index(ids[6]), order.index(ids[7])
        order[i], order[j] = order[j], order[i]                        # one block out of place
        new = blank_block({'type': 'text', 'parts': []})
        new['origin'] = {'kind': 'detached', 'replaces': None, 'from_block': ids[8], 'part_key': 'table_caption',
                         'bbox_pct': {'x': 1, 'y': 1, 'w': 5, 'h': 5}}
        b['n1'] = new
        order.append('n1')
        state['next_new_id'] = 2
        return state, ids

    # --- OP-09 ---
    def test_ac11_zip_marks_pending_as_accepted_and_the_file_keeps_pending(self):
        self.save(blank_state(self.original))
        pending = sum(len(p['blocks']) for p in blank_state(self.original)['pages'].values())
        r = self.client.get(API + '/export/papers.zip')
        self.assertEqual((r.status_code, r.headers['content-type']), (200, 'application/zip'))
        archive = zipfile.ZipFile(io.BytesIO(r.content))
        self.assertEqual(archive.namelist(), ['7.original.json', '7.review.json'])
        self.assertEqual(archive.read('7.original.json'), (REAL_ORIGINALS / '7.json').read_bytes())
        exported = json.loads(archive.read('7.review.json'))
        blocks = [b for p in exported['pages'].values() for b in p['blocks'].values()]
        self.assertEqual(len(blocks), pending)
        self.assertTrue(all(b['status'] == 'accepted' and b['auto_accepted'] for b in blocks))
        saved = json.loads(self.store.review_path('7').read_text(encoding='utf-8'))
        self.assertTrue(all(b['status'] == 'pending' for p in saved['pages'].values() for b in p['blocks'].values()))
        self.assertEqual(r.content, self.client.get(API + '/export/papers.zip').content)      # deterministic

    def test_zip_ignores_the_draft_and_reports_omissions(self):
        self.save(blank_state(self.original))
        draft = blank_state(self.original)
        draft['pages']['7']['blocks'][self.blocks()[0]]['note'] = 'only in the draft'
        self.client.put(API + '/papers/7/draft', json={'base_revision': 1, 'trigger': 'manual', 'state': draft, 'new_versions': []})
        r = self.client.get(API + '/export/papers.zip?papers=7,8')
        self.assertEqual((r.headers['x-drafts-ignored'], r.headers['x-papers-omitted']), ('7', '8'))
        self.assertNotIn(b'only in the draft', zipfile.ZipFile(io.BytesIO(r.content)).read('7.review.json'))

    def test_zip_errors_and_empty_export(self):
        self.assertEqual(self.client.get(API + '/export/papers.zip?papers=6').json()['error']['code'], 'paper_not_found')
        r = self.client.get(API + '/export/papers.zip')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(zipfile.ZipFile(io.BytesIO(r.content)).namelist(), [])
        self.assertEqual(len(r.headers['x-papers-omitted'].split(',')), 23)

    # --- OP-10 ---
    def test_summary_has_one_row_per_decision(self):
        state, ids = self.decisions_state()
        self.save(state)
        r = self.client.get(API + '/export/summary.csv')
        self.assertTrue(r.content.startswith(b'\xef\xbb\xbf'))
        rows = list(csv.DictReader(io.StringIO(r.content.decode('utf-8-sig'))))
        self.assertEqual(list(rows[0]), list(exports.COLUMNS))
        by_reason = {row['reason']: row for row in rows}
        self.assertEqual(set(by_reason), set(exports.REASONS))
        self.assertEqual(len(rows), len(exports.REASONS))
        self.assertEqual(by_reason['rejected']['box'], ids[0])
        self.assertEqual(by_reason['content wrong']['error_types'], 'Wrong characters')
        self.assertEqual(by_reason['wrong tag']['box'], ids[2])
        self.assertNotEqual(by_reason['wrong tag']['tag_final'], by_reason['wrong tag']['tag_predicted'])
        self.assertEqual(by_reason['deleted']['delete_reasons'], 'Scan noise')
        self.assertEqual(by_reason['part moved out']['box'], ids[8])
        self.assertEqual(by_reason['layer issue']['layer_issue'], 'missing: Line missed')
        self.assertEqual(by_reason['reading order changed']['paper'], '7')
        self.assertEqual(by_reason['note']['auto_accepted'], 'true')
        self.assertEqual(by_reason['rejected']['auto_accepted'], 'false')
        self.assertEqual(by_reason['rejected']['page'], '8')                 # shown 1-based, like the interface
        note = by_reason['note']['note']
        self.assertIn('␁', note)                                        # BR-21
        self.assertNotIn('\x01', r.content.decode('utf-8'))

    def test_markdown_matches_the_csv_and_escapes(self):
        state, _ = self.decisions_state()
        self.save(state)
        md = self.client.get(API + '/export/summary.md').content.decode('utf-8')
        self.assertIn('## Paper 7 · ', md)
        table = [line for line in md.splitlines() if '](/#/papers/7/pages/' in line]
        self.assertEqual(len(table), len(exports.REASONS))
        self.assertTrue(all('(/#/papers/7/pages/7)' in line for line in table))
        self.assertIn('check \\| this<br>=1+1 ␁', md)
        self.assertNotIn('\x01', md)

    def test_summary_of_a_paper_with_nothing_to_report(self):
        self.save(blank_state(self.original))
        md = self.client.get(API + '/export/summary.md?papers=7').content.decode('utf-8')
        self.assertIn('No decisions to report.', md)
        csv_rows = list(csv.reader(io.StringIO(self.client.get(API + '/export/summary.csv').content.decode('utf-8-sig'))))
        self.assertEqual(len(csv_rows), 1)                                    # header only
        self.assertEqual(self.client.get(API + '/export/summary.csv?papers=6').status_code, 404)

    # --- OP-11 ---
    def test_stats_count_saved_reviews_only(self):
        state, ids = self.decisions_state()
        block = state['pages']['7']['blocks'][ids[1]]
        block['content']['error_types'] = ['Wrong characters', 'Other']
        block['content']['error_other'] = 'Odd glyph'
        self.save(state)
        draft = copy.deepcopy(state)
        draft['pages']['7']['blocks'][ids[0]]['status'] = 'deleted'
        self.client.put(API + '/papers/7/draft', json={'base_revision': 1, 'trigger': 'manual', 'state': draft, 'new_versions': []})
        body = self.client.get(API + '/stats').json()
        self.assertEqual(body['reviews_counted'], 1)
        self.assertEqual(body['kpis'], {'wrong_or_deleted': 2, 'tags_corrected': 1, 'boxes_drawn': 0, 'tables_edited': 0,
                                        'layer_issues': 1})
        counts = {e['label']: e['count'] for e in body['error_types']}
        self.assertEqual((counts['Wrong characters'], counts['Other'], counts['Punctuation']), (1, 1, 0))
        self.assertEqual({e['label']: e['count'] for e in body['delete_reasons']}['Scan noise'], 1)
        self.assertEqual({e['label']: e['count'] for e in body['layer_issues_by_layer']}['missing'], 1)
        self.assertEqual(len(body['tag_corrections']), 1)
        self.assertEqual(body['tag_corrections'][0]['count'], 1)
        self.assertEqual(body['other_classifications'], [{'kind': 'error_type', 'label': 'Odd glyph', 'count': 1}])
        self.assertEqual(body['warnings'], [])

    def test_stats_pair_counts_and_invalid_files(self):
        state = blank_state(self.original)
        changed = 0
        for page in state['pages'].values():
            for block in page['blocks'].values():
                if block['tag']['predicted'] == 'text':
                    block['tag']['value'] = 'ref_text'
                    changed += 1
        self.save(state)
        self.store.review_path('8').write_text('{bad', encoding='utf-8')
        body = self.client.get(API + '/stats').json()
        self.assertEqual(body['tag_corrections'], [{'from': 'text', 'to': 'ref_text', 'count': changed}])
        self.assertEqual(body['warnings'], [{'code': 'file_invalid', 'file': '8.review.json'}])
        self.assertEqual(self.store.review_path('8').read_text(encoding='utf-8'), '{bad')

    def test_stats_csv(self):
        self.save(blank_state(self.original))
        r = self.client.get(API + '/export/stats.csv')
        rows = list(csv.DictReader(io.StringIO(r.content.decode('utf-8-sig'))))
        self.assertEqual(list(rows[0]), ['section', 'label', 'from', 'to', 'count'])
        self.assertIn(('kpi', 'layer_issues', '0'), {(x['section'], x['label'], x['count']) for x in rows})


if __name__ == '__main__':
    unittest.main()
