"""Unit tests of the folder pair helpers in service/sources.py (11-white-box-coverage-review.md, WB-08).

Stored settings can be edited by hand or left by an older version: anything malformed is dropped, never fatal.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review.service import sources  # noqa: E402

RUN, PDF = 'C:/defaults/run-x', 'C:/defaults/pdfs'
DEFAULT = {'id': 'default', 'name': 'run-x', 'run_dir': RUN, 'pdf_dir': PDF}


def pair(sid, name='A', run='C:/a/run', pdf='C:/a/pdfs', **extra):
    return {'id': sid, 'name': name, 'run_dir': run, 'pdf_dir': pdf, **extra}


class Normalize(unittest.TestCase):  # WB-08
    def test_nothing_stored_gives_the_default_pair(self):
        self.assertEqual(sources.normalize({}, RUN, PDF), ([DEFAULT], 'default'))

    def test_valid_pairs_kept_in_order_without_extra_keys(self):
        stored = {'sources': [pair('b', 'B', note='x'), pair('a')], 'active_source': 'a'}
        self.assertEqual(sources.normalize(stored, RUN, PDF), ([pair('b', 'B'), pair('a')], 'a'))

    def test_each_invalid_condition_drops_only_that_entry(self):
        bad = [
            'not a dict',
            pair('UPPER'),                 # id must be lowercase
            pair('-start'),                # id must start with a letter or digit
            pair('x' * 41),                # id too long
            pair(7),                       # id not a string
            pair('noname', name=''),       # empty name
            pair('norun', run=None),       # folder missing
            {'id': 'nopdf', 'name': 'P', 'run_dir': 'C:/r'},
        ]
        for entry in bad:
            with self.subTest(entry=entry):
                got, _ = sources.normalize({'sources': [entry, pair('ok')]}, RUN, PDF)
                self.assertEqual(got, [pair('ok')])

    def test_repeated_id_keeps_the_first(self):
        got, _ = sources.normalize({'sources': [pair('a', 'First'), pair('a', 'Second')]}, RUN, PDF)
        self.assertEqual(got, [pair('a', 'First')])

    def test_all_invalid_or_not_a_list_falls_back_to_the_default_pair(self):
        for stored in ({'sources': [pair('BAD')]}, {'sources': 'a, b'}, {'sources': []}):
            with self.subTest(stored=stored):
                self.assertEqual(sources.normalize(stored, RUN, PDF), ([DEFAULT], 'default'))

    def test_active_pair_missing_falls_back_to_the_first(self):
        stored = {'sources': [pair('b', 'B'), pair('a')], 'active_source': 'gone'}
        self.assertEqual(sources.normalize(stored, RUN, PDF)[1], 'b')

    def test_settings_from_before_pairs(self):
        got, active = sources.normalize({'run_dir': 'C:/old/run-y', 'pdf_dir': 'C:/old/pdfs'}, RUN, PDF)
        self.assertEqual((got, active), ([{'id': 'default', 'name': 'run-y', 'run_dir': 'C:/old/run-y', 'pdf_dir': 'C:/old/pdfs'}], 'default'))
        got, _ = sources.normalize({'run_dir': '', 'pdf_dir': 5}, RUN, PDF)   # unusable old values: defaults
        self.assertEqual(got, [DEFAULT])


class Ids(unittest.TestCase):
    def test_slug_and_unique_ids(self):
        self.assertEqual(sources.slug('  GPT-6.1 low, PDF only! '), 'gpt-6-1-low-pdf-only')
        self.assertEqual(sources.slug('***'), 'source')
        self.assertEqual(sources.new_id('Run', {'run', 'run-2'}), 'run-3')
        self.assertEqual(len(sources.new_id('x' * 80, {'x' * 40})), 38)   # long names keep room for the suffix

    def test_source_dir(self):
        self.assertEqual(sources.source_dir('D', 'default'), Path('D'))
        self.assertEqual(sources.source_dir('D', 'run-b'), Path('D') / 'sources' / 'run-b')


if __name__ == '__main__':
    unittest.main()
