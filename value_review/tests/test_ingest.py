"""Tests of ingest (step 2): LLM result + PDF -> immutable original.

Covers BR-01, BR-06 (AC-16) and the ingest side of AC-18. Synthetic sources in temporary folders;
the tests against the real run are in test_ingest_real.py.

Run from the repository root:
    python -B -m unittest discover -s value_review/tests -p "test_*.py"
"""
import contextlib
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import schemas  # noqa: E402
from value_review.domain.checks import action_codes, info_codes, needs_check  # noqa: E402
from value_review.ingest import IngestError, OriginalChanged, build_original, dumps, find_papers, ingest_run, write_original  # noqa: E402
from value_review.ingest.__main__ import main as ingest_main  # noqa: E402


def make_pdf(path, sizes, rotate_last=False):
    doc = pdfium.PdfDocument.new()
    pages = [doc.new_page(w, h) for w, h in sizes]
    if rotate_last:
        pages[-1].set_rotation(90)
    doc.save(str(path))
    doc.close()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def result(pdf_sha=None):
    """A small extraction result in the LLM output format (extraction_prompt.md, Output contract)."""
    return {
        'schema_version': '1.0', 'run_id': 'run-test', 'mode': 'pdf_with_feature_guide',
        'paper': {'paper_id': '7', 'pdf_path': 'C:/somewhere/7.pdf', 'sha256': pdf_sha, 'title': 'A test paper', 'page_count': 2, 'workbook_reference_id': None},
        'completion': {'status': 'partial', 'pages_reviewed': [1], 'pages_unreviewed': [2], 'summary': 'Page 2 unreadable.'},
        'feature_columns': [],
        'records': [
            {'record_id': 'r1', 'source_label': 'SS-J', 'condition_summary': 'FeCrAl, RT', 'identity_evidence_ids': [], 'record_kind': 'aggregate', 'statistic_as_reported': 'mean', 'replicate_count': None, 'notes': ''},
            {'record_id': 'r2', 'source_label': None, 'condition_summary': None, 'identity_evidence_ids': [], 'record_kind': 'individual', 'statistic_as_reported': None, 'replicate_count': 3, 'notes': None},
        ],
        'regions': [
            {'region_id': 'g1', 'page_number': 1, 'kind': 'table_row', 'source_label': 'SS-J', 'bbox': [0, 0, 1, 1], 'location_quality': 'measured'},
            {'region_id': 'g9', 'page_number': 9, 'kind': 'table', 'source_label': 'Beyond', 'bbox': None, 'location_quality': 'unlocated'},
        ],
        'evidence': [
            {'evidence_id': 'e1', 'region_id': 'g1', 'role': 'datum', 'literal_text': '710 ± 25', 'bbox': [0.52621, 0.38369, 0.57634, 0.39321], 'location_quality': 'measured', 'notes': ''},
            {'evidence_id': 'e2', 'region_id': 'g1', 'role': 'row_label', 'literal_text': 'SS-J', 'bbox': None, 'location_quality': 'unlocated', 'notes': ''},
            {'evidence_id': 'e3', 'region_id': 'g9', 'role': 'datum', 'literal_text': 'x', 'bbox': None, 'location_quality': 'unlocated', 'notes': ''},
            {'evidence_id': 'e4', 'region_id': 'gX', 'role': 'datum', 'literal_text': 'y', 'bbox': None, 'location_quality': 'unlocated', 'notes': ''},
        ],
        'observations': [
            {'observation_id': 'o1', 'feature_id': 'yield_strength', 'record_ids': ['r1'], 'candidate_record_ids': [], 'assignment_status': 'established', 'scope': 'specimen',
             'source_status': 'explicit', 'value_as_reported': '710 ± 25', 'unit_as_reported': 'MPa', 'evidence_ids': ['e1', 'e2'], 'derivation': None, 'flags': ['reported_aggregate'], 'notes': ''},
            {'observation_id': 'o2', 'feature_id': 'composition_al', 'record_ids': [], 'candidate_record_ids': ['r1', 'r2'], 'assignment_status': 'ambiguous', 'scope': 'material_or_heat',
             'source_status': 'explicit', 'value_as_reported': '5.0', 'unit_as_reported': 'wt.%', 'evidence_ids': ['e3', 'e4', 'e_missing'], 'derivation': None, 'flags': [], 'notes': 'n'},
            {'observation_id': 'o3', 'feature_id': 'aspect_ratio_l_w', 'record_ids': ['r2', 'r_missing'], 'candidate_record_ids': [], 'assignment_status': 'established', 'scope': 'specimen',
             'source_status': 'derived_inputs', 'value_as_reported': None, 'unit_as_reported': None, 'evidence_ids': [], 'derivation': {'status': 'unconfirmed', 'relationship': 'L/W', 'operand_evidence_ids': [], 'missing_operands': []},
             'flags': ['fracture_stress_not_yield'], 'notes': ''},
            {'observation_id': 'o4', 'feature_id': 'some_new_feature', 'record_ids': ['r2'], 'candidate_record_ids': [], 'assignment_status': 'established', 'scope': 'paper',
             'source_status': 'candidate_only', 'value_as_reported': '10⁻³ s⁻¹', 'unit_as_reported': None, 'evidence_ids': [], 'derivation': None, 'flags': [], 'notes': ''},
        ],
        'workbook_targets': [], 'tool_notes': [], 'limitations': [],
    }


class Checks(unittest.TestCase):  # BR-06, ADR-006
    def test_ambiguous_flags_need_a_check(self):
        self.assertTrue(needs_check(['fracture_stress_not_yield'], 'explicit', 'established'))
        self.assertTrue(needs_check(['yield_fracture_criterion_ambiguous'], 'explicit', 'established'))

    def test_candidate_source_or_unestablished_assignment_need_a_check(self):
        self.assertTrue(needs_check([], 'candidate_only', 'established'))
        self.assertTrue(needs_check([], 'explicit', 'ambiguous'))
        self.assertTrue(needs_check([], 'explicit', 'unassigned'))
        self.assertTrue(needs_check([], 'explicit', None))

    def test_information_only(self):
        for flags, src in ((['reported_aggregate'], 'explicit'), ([], 'derived_inputs'), ([], 'not_explicitly_reported'), (['plastic_component_only'], 'explicit')):
            self.assertFalse(needs_check(flags, src, 'established'), (flags, src))

    def test_codes(self):
        self.assertEqual(action_codes(['reported_aggregate', 'fracture_stress_not_yield'], 'candidate_only', 'ambiguous'),
                         ['fracture_stress_not_yield', 'source:candidate_only', 'assignment:ambiguous'])
        self.assertEqual(info_codes(['reported_aggregate', 'fracture_stress_not_yield'], 'derived_inputs'),
                         ['reported_aggregate', 'source:derived_inputs'])


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.run, self.pdfs, self.out = d / 'run', d / 'pdfs', d / 'originals'
        self.run.mkdir(); self.pdfs.mkdir()
        self.pdf = self.pdfs / '7.pdf'
        make_pdf(self.pdf, [(612, 792), (612, 792)], rotate_last=True)
        self.data = result(sha(self.pdf))
        self.res = self.run / '7-pdf_with_feature_guide.json'
        self.res.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def build(self):
        return build_original(self.res, self.pdf)

    def test_valid_against_the_schema(self):
        self.assertEqual(schemas.errors('original', self.build()), [])

    def test_deterministic_and_no_absolute_paths(self):  # BR-01
        a, b = dumps(self.build()), dumps(self.build())
        self.assertEqual(a, b)
        text = a.decode('utf-8')
        self.assertNotIn('somewhere', text)
        self.assertNotIn(str(self.pdfs), text)
        self.assertNotIn('generated_at', text)

    def test_source_hashes_and_document(self):
        o = self.build()
        self.assertEqual(o['paper'], '7')
        self.assertEqual(o['source']['result_sha256'], sha(self.res))
        self.assertEqual(o['source']['pdf_sha256'], sha(self.pdf))
        self.assertEqual(o['document']['page_count'], 2)
        self.assertEqual(o['document']['completion'], {'status': 'partial', 'pages_unreviewed': [2], 'summary': 'Page 2 unreadable.'})

    def test_page_sizes_apply_rotation(self):
        self.assertEqual([(p['width_pt'], p['height_pt']) for p in self.build()['pages']], [(612, 792), (792, 612)])

    def test_values_keep_symbols_and_boxes_keep_the_source_format(self):  # BR-05, ADR-007
        o1 = self.build()['observations'][0]
        self.assertEqual((o1['value'], o1['unit']), ('710 ± 25', 'MPa'))
        self.assertEqual(o1['evidence'][0]['bbox'], [0.5262, 0.3837, 0.5763, 0.3932])
        self.assertEqual(o1['evidence'][0]['page'], 1)
        self.assertIsNone(o1['evidence'][1]['bbox'])
        self.assertEqual(self.build()['observations'][3]['value'], '10⁻³ s⁻¹')

    def test_needs_check_and_counts(self):  # BR-06
        o = self.build()
        self.assertEqual([x['needs_check'] for x in o['observations']], [False, True, True, True])
        self.assertEqual(o['observations'][0]['info'], ['reported_aggregate'])
        self.assertEqual(o['observations'][2]['info'], ['source:derived_inputs'])
        self.assertEqual(o['counts'], {'records': 2, 'values': 4, 'needs_check': 3})

    def test_unresolved_references_become_issues(self):
        o = self.build()
        self.assertEqual(o['issues'], [
            {'code': 'page_out_of_range', 'ref': 'e3:9'},
            {'code': 'unknown_region', 'ref': 'e4:gX'},
            {'code': 'unknown_evidence', 'ref': 'o2:e_missing'},
            {'code': 'unknown_record', 'ref': 'o3:r_missing'},
        ])
        self.assertEqual(o['observations'][1]['evidence'], [])

    def test_pdf_hash_mismatch_is_reported(self):
        self.data['paper']['sha256'] = '0' * 64
        self.res.write_text(json.dumps(self.data), encoding='utf-8')
        self.assertIn({'code': 'pdf_hash_mismatch', 'ref': '7.pdf'}, self.build()['issues'])

    def test_records_and_features(self):
        o = self.build()
        self.assertEqual(o['records'][1], {'record_id': 'r2', 'label': 'r2', 'summary': '', 'kind': 'individual', 'statistic': None, 'replicate_count': 3, 'notes': ''})
        self.assertEqual([f['feature_id'] for f in o['features']], ['composition_al', 'aspect_ratio_l_w', 'yield_strength', 'some_new_feature'])
        self.assertEqual([f['label'] for f in o['features']], ['Al content', 'Aspect ratio (L/W)', 'Yield strength', 'Some new feature'])

    def test_missing_or_malformed_source(self):
        with self.assertRaises(IngestError):
            build_original(self.run / 'nope.json', self.pdf)
        bad = self.run / '8-pdf_with_feature_guide.json'
        bad.write_text('{"paper": {}}', encoding='utf-8')
        with self.assertRaises(IngestError):
            build_original(bad, self.pdf)

    def test_sources_are_not_modified(self):  # BR-01
        before = (sha(self.res), sha(self.pdf), self.res.stat().st_mtime_ns, self.pdf.stat().st_mtime_ns)
        ingest_run(self.run, self.pdfs, self.out)
        self.assertEqual(before, (sha(self.res), sha(self.pdf), self.res.stat().st_mtime_ns, self.pdf.stat().st_mtime_ns))


class WriteOnce(Build):  # BR-01, OQ-02
    def test_written_then_unchanged(self):
        o = self.build()
        self.assertEqual(write_original(o, self.out), 'written')
        mtime = (self.out / '7.json').stat().st_mtime_ns
        self.assertEqual(write_original(o, self.out), 'unchanged')
        self.assertEqual((self.out / '7.json').stat().st_mtime_ns, mtime)

    def test_different_content_is_refused_and_left_intact(self):
        o = self.build()
        write_original(o, self.out)
        before = (self.out / '7.json').read_bytes()
        other = copy.deepcopy(o)
        other['observations'][0]['value'] = '711'
        with self.assertRaises(OriginalChanged):
            write_original(other, self.out)
        self.assertEqual((self.out / '7.json').read_bytes(), before)

    def test_run_report_and_exit_codes(self):
        rows = ingest_run(self.run, self.pdfs, self.out)
        self.assertEqual([(r['paper'], r['outcome'], r['values'], r['needs_check']) for r in rows], [('7', 'written', 4, 3)])
        args = ['--run', str(self.run), '--pdfs', str(self.pdfs), '--out', str(self.out)]
        quiet = lambda: contextlib.redirect_stdout(io.StringIO())  # noqa: E731
        with quiet():
            self.assertEqual(ingest_main(args), 0)  # unchanged
        self.data['observations'][0]['value_as_reported'] = '711'
        self.res.write_text(json.dumps(self.data), encoding='utf-8')
        with quiet():
            self.assertEqual(ingest_main(args), 2)  # changed source: original left as it is
        (self.pdfs / '7.pdf').unlink()
        with quiet():
            self.assertEqual(ingest_main(args), 1)  # missing PDF

    def test_find_papers_numeric_order(self):
        for pid in ('10', '2'):
            (self.run / f'{pid}-pdf_with_feature_guide.json').write_text('{}', encoding='utf-8')
        (self.run / 'x-pdf_with_feature_guide.json').write_text('{}', encoding='utf-8')
        self.assertEqual(find_papers(self.run), ['2', '7', '10'])


if __name__ == '__main__':
    unittest.main()
