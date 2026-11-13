"""Tests of the decision rules (OP-07, AC-09) and the blank state (AC-02). Synthetic original plus paper 7 if generated."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from parsing_validator.domain import DEFAULT_SETTINGS, DecisionRulesViolation, blank_state, check_state, validate_state  # noqa: E402

SHA = 'a' * 64


def original():
    def block(i, kind, parts=()):
        return {'id': f'k{i}', 'index': i, 'type': kind, 'bbox_pct': {'x': 1, 'y': 1, 'w': 10, 'h': 5},
                'parts': [{'key': k} for k in parts]}
    return {'pages': [
        {'index': 0, 'blocks': [block(0, 'text'), block(1, 'equation'), block(2, 'image', ['image_body']),
                                block(3, 'table', ['table_caption', 'table_body'])]},
        {'index': 1, 'blocks': [block(0, 'text')]},
    ]}


def cell(v='x'):
    return {'v': v, 'rs': 1, 'cs': 1, 'hidden': False}


class Base(unittest.TestCase):
    def setUp(self):
        self.original = original()
        self.settings = DEFAULT_SETTINGS
        self.state = blank_state(self.original)

    def block(self, bid='k0', page='0'):
        return self.state['pages'][page]['blocks'][bid]

    def codes(self, rule=None):
        return sorted(v['code'] for v in validate_state(self.state, self.original, self.settings) if rule is None or v['rule'] == rule)


class Blank(Base):
    def test_blank_state_matches_AC02_and_is_valid(self):
        self.assertEqual(validate_state(self.state, self.original, self.settings), [])
        page = self.state['pages']['0']
        self.assertEqual(page['reading_order'], ['k0', 'k1', 'k2', 'k3'])
        self.assertTrue(all(b['status'] == 'pending' and b['content']['text'] is None for b in page['blocks'].values()))
        self.assertEqual(page['blocks']['k3']['parts']['order'], ['table_caption', 'table_body'])
        self.assertEqual(self.state['next_new_id'], 1)

    def test_reading_order_follows_the_index_not_the_list_order(self):
        o = original()
        o['pages'][0]['blocks'].reverse()
        self.assertEqual(blank_state(o)['pages']['0']['reading_order'], ['k0', 'k1', 'k2', 'k3'])


class Rule1Identity(Base):
    def test_unknown_page_and_missing_page(self):
        del self.state['pages']['1']
        self.state['pages']['9'] = {'reading_order': [], 'blocks': {}}
        self.assertEqual(self.codes(1), ['page_missing', 'page_unknown'])

    def test_block_missing_and_unknown_without_origin(self):
        page = self.state['pages']['0']
        del page['blocks']['k2']
        page['reading_order'].remove('k2')
        page['blocks']['k9'] = copy.deepcopy(page['blocks']['k0'])
        page['reading_order'].append('k9')
        self.assertEqual(self.codes(1), ['block_missing', 'block_unknown'])

    def test_reading_order_must_list_every_live_block_once(self):
        page = self.state['pages']['0']
        page['reading_order'] = ['k0', 'k0', 'k1', 'k77']
        self.assertEqual(self.codes(1), ['reading_order_duplicate', 'reading_order_missing', 'reading_order_missing', 'reading_order_unknown'])

    def test_deleted_block_leaves_the_reading_order(self):
        self.block('k1')['status'] = 'deleted'
        self.block('k1')['delete_reasons'] = ['False detection']
        self.assertEqual(self.codes(1), ['reading_order_missing'][:0] + ['reading_order_deleted'])
        self.state['pages']['0']['reading_order'].remove('k1')
        self.assertEqual(self.codes(), [])

    def drawn(self, bid='n1', **over):
        block = copy.deepcopy(self.block('k0'))
        block['origin'] = {'kind': 'drawn', 'replaces': None, 'from_block': None, 'part_key': None,
                           'bbox_pct': {'x': 10, 'y': 10, 'w': 20, 'h': 5}, **over}
        self.state['pages']['0']['blocks'][bid] = block
        self.state['pages']['0']['reading_order'].append(bid)
        self.state['next_new_id'] = 2

    def test_a_drawn_block_with_origin_and_counter_is_valid(self):
        self.drawn()
        self.assertEqual(self.codes(), [])

    def test_new_block_ids_must_be_below_the_counter(self):
        self.drawn()
        self.state['next_new_id'] = 1
        self.assertEqual(self.codes(1), ['new_id_not_counted'])

    def test_new_block_id_format_box_and_references(self):
        self.drawn('x5', bbox_pct={'x': 99, 'y': 1, 'w': 5, 'h': 5}, replaces='k404')
        self.assertEqual(self.codes(1), ['new_id_malformed', 'origin_box', 'origin_reference'])

    def test_detached_block_needs_its_parent_and_part(self):
        self.drawn(kind='detached')
        self.assertEqual(self.codes(1), ['origin_detached'])
        self.state['pages']['0']['blocks']['n1']['origin'].update(from_block='k3', part_key='table_caption')
        self.assertEqual(self.codes(), [])

    def test_a_mineru_block_cannot_claim_an_origin(self):
        self.block('k0')['origin'] = {'kind': 'drawn'}
        self.assertEqual(self.codes(1), ['origin_on_original_block'])


class Rule2Tag(Base):
    def test_catalog_other_and_predicted(self):
        self.block('k0')['tag']['value'] = 'ref_text'
        self.assertEqual(self.codes(), [])
        self.block('k0')['tag']['value'] = 'nonsense'
        self.assertEqual(self.codes(2), ['tag_unknown'])
        self.block('k0')['tag'].update(value='Other', other_label='  ')
        self.assertEqual(self.codes(2), ['tag_other_label'])
        self.block('k0')['tag']['other_label'] = 'Algorithm'
        self.assertEqual(self.codes(), [])
        self.block('k0')['tag']['predicted'] = 'table'
        self.assertEqual(self.codes(2), ['tag_predicted'])


class Rule3ErrorTypes(Base):
    def test_wrong_needs_an_error_type_and_other_needs_text(self):
        c = self.block('k0')['content']
        c['status'] = 'wrong'
        self.assertEqual(self.codes(3), ['error_type_required'])
        c['error_types'] = ['Wrong characters']
        self.assertEqual(self.codes(), [])
        c['error_types'] = ['Other']
        self.assertEqual(self.codes(3), ['error_other_required'])
        c['error_other'] = 'Broken ligature'
        self.assertEqual(self.codes(), [])
        c['error_types'] = ['Invented']
        self.assertEqual(self.codes(3), ['error_type_unknown'])


class Rule4Delete(Base):
    def test_deleted_needs_reasons_and_other_needs_text(self):
        b = self.block('k2')
        b['status'] = 'deleted'
        self.state['pages']['0']['reading_order'].remove('k2')
        self.assertEqual(self.codes(4), ['delete_reason_required'])
        b['delete_reasons'] = ['Other']
        self.assertEqual(self.codes(4), ['delete_other_required'])
        b['delete_other'] = 'Scanner shadow'
        self.assertEqual(self.codes(), [])
        b['delete_reasons'] = ['Duplicate box', 'Made up']
        self.assertEqual(self.codes(4), ['delete_reason_unknown'])


class Rule5CapableContent(Base):
    def test_text_only_for_text_capable_tags(self):
        self.block('k0')['content']['text'] = 'corrected'
        self.assertEqual(self.codes(), [])
        self.block('k2')['content']['text'] = 'caption?'
        self.assertEqual(self.codes(5), ['text_not_allowed'])  # image: figure, no text

    def test_latex_follows_the_text_rule(self):
        self.block('k1')['content']['latex'] = [{'source': '\\sigma = F / A_0', 'tag': '1', 'mathml': None, 'error': None}]
        self.assertEqual(self.codes(), [])
        self.block('k3')['content']['latex'] = [{'source': 'x'}]
        self.assertEqual(self.codes(5), ['text_not_allowed'])

    def test_table_only_for_the_table_tag(self):
        table = {'cells': [[cell('A'), cell('B')], [cell(), cell()]], 'html': '<table></table>'}
        self.block('k3')['content']['table'] = table
        self.assertEqual(self.codes(), [])
        self.block('k0')['content']['table'] = table
        self.assertEqual(self.codes(5), ['table_not_allowed'])

    def test_a_retagged_block_is_judged_by_its_final_tag(self):
        self.block('k0')['tag']['value'] = 'image'
        self.block('k0')['content']['text'] = 'now a figure'
        self.assertEqual(self.codes(5), ['text_not_allowed'])
        self.block('k0')['tag'].update(value='Other', other_label='Algorithm')
        self.assertEqual(self.codes(), [])

    def test_table_shape_is_checked(self):
        self.block('k3')['content']['table'] = {'cells': [[cell(), cell()], [cell()]], 'html': ''}
        self.assertEqual(self.codes(0), ['table_shape'])


class Rule6DeadBlocks(Base):
    def test_rejected_or_deleted_blocks_carry_no_edits(self):
        self.block('k0')['status'] = 'rejected'
        self.block('k0')['content']['text'] = 'edit'
        self.assertEqual(self.codes(6), ['content_on_dead_block'])
        self.block('k0')['content']['text'] = None
        self.assertEqual(self.codes(), [])  # a rejected block with no replacement is allowed

    def test_deleted_block_with_latex(self):
        b = self.block('k1')
        b.update(status='deleted', delete_reasons=['False detection'])
        b['content']['latex'] = [{'source': 'x'}]
        self.state['pages']['0']['reading_order'].remove('k1')
        self.assertEqual(self.codes(6), ['content_on_dead_block'])


class Rule7LayerIssues(Base):
    def issue(self, **over):
        issue = {'layer': 'ocr', 'ref': {'sha256': SHA, 'pointer': '/geometries/3/bbox'}, 'kinds': ['Line missed'],
                 'other': None, 'text': '', 'correction_bbox_pct': None}
        issue.update(over)
        self.block('k0')['layer_issues'] = [issue]

    def test_valid_issue(self):
        self.issue()
        self.assertEqual(self.codes(), [])

    def test_kinds_other_and_layer(self):
        self.issue(kinds=[])
        self.assertEqual(self.codes(7), ['layer_kinds_required'])
        self.issue(kinds=['Other'])
        self.assertEqual(self.codes(7), ['layer_other_required'])
        self.issue(layer='skin')
        self.assertEqual(self.codes(7), ['layer_invalid'])

    def test_reference_is_required_except_for_missing_and_other(self):
        self.issue(ref=None)
        self.assertEqual(self.codes(7), ['layer_ref_required'])
        self.issue(layer='missing', ref=None, kinds=['OCR not captured'])
        self.assertEqual(self.codes(), [])
        self.issue(ref={'sha256': 'short', 'pointer': '/x'})
        self.assertEqual(self.codes(7), ['layer_ref_invalid'])


class Rule8Correct(Base):
    def test_correct_content_carries_no_edits(self):
        c = self.block('k0')['content']
        c['status'] = 'correct'
        self.assertEqual(self.codes(), [])
        c['text'] = 'edit'
        c['error_types'] = ['Punctuation']
        self.assertEqual(self.codes(8), ['content_correct_with_edits'])


class Everything(Base):
    def test_all_violations_are_listed_together_and_check_raises_them(self):
        self.block('k0')['tag']['value'] = 'nonsense'
        self.block('k0')['content']['status'] = 'wrong'
        self.block('k2')['status'] = 'deleted'
        with self.assertRaises(DecisionRulesViolation) as caught:
            check_state(self.state, self.original, self.settings)
        rules = {v['rule'] for v in caught.exception.violations}
        self.assertTrue({1, 2, 3, 4} <= rules)
        first = caught.exception.violations[0]
        self.assertEqual(set(first), {'rule', 'code', 'page', 'block', 'message'})

    def test_the_input_state_is_not_modified(self):
        self.block('k0')['content']['status'] = 'wrong'
        before = copy.deepcopy(self.state)
        validate_state(self.state, self.original, self.settings)
        self.assertEqual(self.state, before)


class RealPaper7(unittest.TestCase):
    path = ROOT / 'parsing_validator/originals/7.json'

    @unittest.skipUnless(path.exists(), 'run python -m parsing_validator.ingest first')
    def test_blank_state_of_the_real_original_is_valid(self):
        original = json.loads(self.path.read_text(encoding='utf8'))
        state = blank_state(original)
        self.assertEqual(validate_state(state, original, DEFAULT_SETTINGS), [])
        page = state['pages']['7']
        self.assertEqual(len(page['blocks']), 16)
        self.assertEqual(page['blocks']['k8']['parts']['order'], ['table_caption', 'table_body'])
        types = {b['type'] for p in original['pages'] for b in p['blocks']}
        self.assertTrue(types <= {t['name'] for t in DEFAULT_SETTINGS['tags']})


if __name__ == '__main__':
    unittest.main()
