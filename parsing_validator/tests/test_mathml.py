"""MathML derivation (BR-17, AC-12, ADR-006): pinned KaTeX through a Node subprocess."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from parsing_validator.domain.mathml import KATEX_DIR, KATEX_SHA256, UNAVAILABLE, MathRenderer, split_tag

ORIGINAL_7 = Path(__file__).resolve().parent.parent / 'originals' / '7.json'
HAS_NODE = shutil.which('node') is not None


def paper7_equations():
    original = json.loads(ORIGINAL_7.read_text(encoding='utf-8'))
    page = next(p for p in original['pages'] if p['index'] == 7)
    return [b['content'] for b in page['blocks'] if b['type'] == 'equation']


class SplitTag(unittest.TestCase):
    def test_tag_is_removed_and_returned(self):
        self.assertEqual(split_tag(r'a = b \tag{12}'), ('a = b', '12'))
        self.assertEqual(split_tag(r'a = b\tag*{(A)}'), ('a = b', '(A)'))

    def test_without_tag(self):
        self.assertEqual(split_tag('a = b'), ('a = b', None))


@unittest.skipUnless(HAS_NODE, 'Node is not installed')
class WithNode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = MathRenderer()

    @classmethod
    def tearDownClass(cls):
        cls.renderer.close()

    def test_ac12_simple_segment(self):
        [seg] = self.renderer.derive([{'source': r'\sigma = F/A'}])
        self.assertIsNone(seg['error'])
        self.assertTrue(seg['mathml'].startswith('<math') and seg['mathml'].endswith('</math>'))
        self.assertIn('σ', seg['mathml'])
        self.assertEqual(self.renderer.renderer, 'katex@0.16.11')

    def test_invalid_source_has_error_and_no_mathml(self):
        [seg] = self.renderer.derive([{'source': r'\frac{1}{'}])
        self.assertIsNone(seg['mathml'])
        self.assertTrue(seg['error'])
        self.assertNotEqual(seg['error'], UNAVAILABLE)

    def test_tag_is_stored_and_not_rendered(self):
        [seg] = self.renderer.derive([{'source': r'a = b \tag{7}'}])
        self.assertEqual(seg['tag'], '7')
        self.assertEqual(seg['source'], r'a = b \tag{7}')   # the source stays as typed
        self.assertIsNone(seg['error'])
        self.assertNotIn('(7)', seg['mathml'])

    def test_client_mathml_is_never_trusted(self):
        [seg] = self.renderer.derive([{'source': 'x', 'mathml': '<math>tampered</math>'}])
        self.assertNotIn('tampered', seg['mathml'])

    def test_empty_source(self):
        [seg] = self.renderer.derive([{'source': '   '}])
        self.assertEqual((seg['mathml'], seg['error']), (None, 'empty_source'))

    def test_order_and_independence(self):
        out = self.renderer.derive([{'source': 'a'}, {'source': r'\frac{'}, {'source': 'c'}])
        self.assertEqual([bool(s['mathml']) for s in out], [True, False, True])

    @unittest.skipUnless(ORIGINAL_7.is_file(), 'originals/7.json not generated')
    def test_equations_of_paper_7_page_7(self):
        equations = paper7_equations()
        self.assertGreaterEqual(len(equations), 2)
        out = self.renderer.derive([{'source': e} for e in equations])
        for seg in out:
            self.assertIsNone(seg['error'], seg['source'])
            self.assertIn('<mfrac', seg['mathml']) if r'\frac' in seg['source'] else None
        self.assertTrue(any('<msqrt' in s['mathml'] for s in out), 'a root was expected on that page')
        self.assertEqual(out[0]['tag'], '1')

    def test_process_restarts_after_it_dies(self):
        self.renderer.derive([{'source': 'a'}])
        self.renderer._proc.kill()
        self.renderer._proc.wait()
        [seg] = self.renderer.derive([{'source': 'b'}])
        self.assertIsNone(seg['error'])
        self.assertTrue(seg['mathml'])

    def test_same_input_same_output(self):
        a = self.renderer.derive([{'source': r'\frac{1}{\sqrt{x}}'}])
        b = self.renderer.derive([{'source': r'\frac{1}{\sqrt{x}}'}])
        self.assertEqual(a, b)


class Unavailable(unittest.TestCase):
    def check(self, renderer):
        [seg] = renderer.derive([{'source': 'x'}])
        self.assertEqual((seg['mathml'], seg['error']), (None, UNAVAILABLE))
        self.assertFalse(renderer.available)
        self.assertTrue(renderer.problem)
        renderer.close()

    def test_node_absent(self):
        self.check(MathRenderer(node=''))

    def test_vendored_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.check(MathRenderer(katex_dir=tmp))

    @unittest.skipUnless(HAS_NODE, 'Node is not installed')
    def test_vendored_file_with_another_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('render.js', 'katex.min.js'):
                shutil.copy(KATEX_DIR / name, Path(tmp) / name)
            with open(Path(tmp) / 'katex.min.js', 'ab') as handle:
                handle.write(b'\n// changed')
            self.check(MathRenderer(katex_dir=tmp))

    def test_pinned_hash_matches_vendored_file(self):
        import hashlib
        self.assertEqual(hashlib.sha256((KATEX_DIR / 'katex.min.js').read_bytes()).hexdigest(), KATEX_SHA256)


if __name__ == '__main__':
    unittest.main()
