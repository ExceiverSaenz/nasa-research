"""Ingest against the real LLM run (read-only). Skipped when the sources are not present.

The sources live in the main checkout; from a worktree set VALUE_REVIEW_SOURCE_ROOT to it.
Covers AC-16 (needs-a-check counts) and BR-01 (sources untouched).
"""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import config, schemas  # noqa: E402
from value_review.ingest import find_papers, ingest_run  # noqa: E402

RUN, PDFS = config.default_run_dir(), config.default_pdf_dir()
HAVE_SOURCES = RUN.is_dir() and PDFS.is_dir()

# ADR-006: needs-a-check per paper with BR-06, and the number of values per paper.
EXPECTED = {
    '1': (255, 6), '2': (57, 0), '3': (264, 5), '4': (157, 0), '5': (200, 1), '7': (52, 5), '8': (400, 49),
    '9': (93, 2), '10': (414, 4), '11': (193, 33), '12': (222, 25), '13': (108, 1), '14': (68, 37), '15': (98, 0),
}


def inventory(folder, names):
    h = hashlib.sha256()
    for name in names:
        p = Path(folder) / name
        st = p.stat()
        h.update(f'{name}|{st.st_size}|{st.st_mtime_ns}|'.encode() + hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


@unittest.skipUnless(HAVE_SOURCES, 'LLM run or PDFs not found; set VALUE_REVIEW_SOURCE_ROOT')
class RealRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = find_papers(RUN)
        cls.results = [f'{p}{config.RESULT_SUFFIX}' for p in cls.ids]
        cls.pdf_names = [f'{p}.pdf' for p in cls.ids]
        cls.before = (inventory(RUN, cls.results), inventory(PDFS, cls.pdf_names))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.rows = {r['paper']: r for r in ingest_run(RUN, PDFS, cls.out)}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_fourteen_papers_written_without_issues(self):
        self.assertEqual(self.ids, list(EXPECTED))
        self.assertEqual({p: r['outcome'] for p, r in self.rows.items()}, {p: 'written' for p in EXPECTED})
        self.assertEqual({p: r['issues'] for p, r in self.rows.items()}, {p: 0 for p in EXPECTED})

    def test_counts_per_paper(self):  # AC-16
        self.assertEqual({p: (r['values'], r['needs_check']) for p, r in self.rows.items()}, EXPECTED)
        self.assertEqual(sum(v for v, _ in EXPECTED.values()), 2581)
        self.assertEqual(sum(n for _, n in EXPECTED.values()), 168)

    def test_originals_validate(self):
        import json
        for pid in self.ids:
            original = json.loads((self.out / f'{pid}.json').read_text(encoding='utf-8'))
            self.assertEqual(schemas.errors('original', original), [], pid)

    def test_sources_untouched(self):  # BR-01
        self.assertEqual((inventory(RUN, self.results), inventory(PDFS, self.pdf_names)), self.before)


if __name__ == '__main__':
    unittest.main()
