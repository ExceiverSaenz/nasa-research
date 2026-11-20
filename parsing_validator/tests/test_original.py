"""Tests of the original generator against the real sealed collection (read-only).

Run from the repository root:
    python -B -m unittest discover -s parsing_validator/tests -p "test_*.py"
"""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from parsing_validator.ingest.original import SCHEMA, build_original, dumps, write_original  # noqa: E402

COLLECTION = ROOT / 'src/raw_results/code_results/tensile_papers'
PDFS = ROOT / 'papers/Tensile_Properties_of_Sub-sized_Specimens_papers'


def inventory(folder):
    h = hashlib.sha256()
    for p in sorted(folder.rglob('*')):
        if p.is_file():
            st = p.stat()
            h.update(f'{p.relative_to(folder).as_posix()}|{st.st_size}|{st.st_mtime_ns}\n'.encode())
    return h.hexdigest()


class Paper7(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = (inventory(COLLECTION), inventory(PDFS))
        cls.original = build_original(COLLECTION, PDFS, '7')
        cls.page = next(p for p in cls.original['pages'] if p['index'] == 7)

    def test_golden_page_7(self):  # ADR-004: 16 blocks, 34 layout, 49 OCR lines, cells not captured
        page = self.page
        self.assertEqual(len(page['blocks']), 16)
        self.assertEqual(len(page['layers']['layout']['items']), 34)
        self.assertEqual(len(page['layers']['ocr']['items']), 49)
        self.assertFalse(page['layers']['cells']['available'])
        self.assertEqual(page['layers']['cells']['reason'], 'not_captured')
        self.assertEqual(page['render'], {'scale': 1.9, 'width_px': 1132, 'height_px': 1509})

    def test_table_box_matches_contract_example(self):
        table = next(b for b in self.page['blocks'] if b['id'] == 'k8')
        self.assertEqual(table['type'], 'table')
        self.assertEqual(table['bbox_pct'], {'x': 7.1, 'y': 47.0, 'w': 42.2, 'h': 9.9})
        self.assertIsNone(table['content'])
        self.assertTrue(table['html'].startswith('<table>'))
        self.assertEqual([p['key'] for p in table['parts']], ['table_caption', 'table_body'])

    def test_header_and_provenance(self):
        o = self.original
        self.assertEqual(o['schema'], SCHEMA)
        self.assertEqual(o['paper'], '7')
        self.assertEqual(o['document']['page_count'], 9)
        self.assertEqual(o['document']['parse_mode'], 'txt')
        self.assertEqual(len(o['source']['pdf_sha256']), 64)
        self.assertNotIn('generated_at', o)  # BR-03: no clock, same input same bytes

    def test_layout_match_reports_weak_blocks(self):
        weak = [b['id'] for b in self.page['blocks'] if b['layout_match']['weak']]
        self.assertEqual(weak, ['k11'])  # the single-line equation: IoU 0.345 with its nearest detection
        for b in self.page['blocks']:
            self.assertIn('iou', b['layout_match'])

    def test_deterministic_bytes(self):
        self.assertEqual(dumps(build_original(COLLECTION, PDFS, '7')), dumps(self.original))

    def test_every_shown_item_has_geometry(self):  # OQ-14: nothing visible lacks a box
        for page in self.original['pages']:
            for item in page['layers']['layout']['items']:
                self.assertIsNotNone(item['bbox_pct'])
            for item in page['layers']['ocr']['items']:
                self.assertEqual(len(item['poly_pct']), 4)

    def test_no_model_runtime_and_sealed_data_untouched(self):
        self.assertNotIn('mineru', sys.modules)
        self.assertNotIn('torch', sys.modules)
        self.assertEqual((inventory(COLLECTION), inventory(PDFS)), self.before)


class WriteOnce(unittest.TestCase):
    def test_second_write_is_identical_and_a_different_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as out:
            first = write_original(COLLECTION, PDFS, '7', out)
            stamp = first.stat().st_mtime_ns
            again = write_original(COLLECTION, PDFS, '7', out)
            self.assertEqual(again, first)
            self.assertEqual(again.stat().st_mtime_ns, stamp)  # not rewritten
            first.write_bytes(b'{}\n')
            with self.assertRaises(ValueError):
                write_original(COLLECTION, PDFS, '7', out)
            self.assertEqual(first.read_bytes(), b'{}\n')  # never overwritten


if __name__ == '__main__':
    unittest.main()
