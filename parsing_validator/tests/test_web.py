"""The committed front-end build carries the same pinned KaTeX the service runs through Node (ADR-006)."""
import hashlib
import unittest
from pathlib import Path

from parsing_validator.domain.mathml import KATEX_SHA256

HOME = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PinnedKatex(unittest.TestCase):
    def test_three_copies_are_the_same_pinned_file(self):
        for path in (HOME / 'vendor/katex/katex.min.js', HOME / 'frontend/public/vendor/katex.min.js',
                     HOME / 'web/vendor/katex.min.js'):
            self.assertTrue(path.is_file(), f'{path} is missing')
            self.assertEqual(digest(path), KATEX_SHA256, f'{path} is not the pinned KaTeX')

    def test_the_build_has_its_entry_page(self):
        index = (HOME / 'web/index.html').read_text(encoding='utf-8')
        self.assertIn('Parsing Validator', index)
        self.assertTrue(list((HOME / 'web/assets').glob('*.js')))


if __name__ == '__main__':
    unittest.main()
