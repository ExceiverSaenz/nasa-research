"""Every CLI attempt is discoverable under the shared parse_results root."""
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class StorageTests(unittest.TestCase):
    def test_default_shared_results_root_is_sibling_of_parse_system(self):
        from parsing.unified.storage import results_root
        self.assertEqual(results_root(), ROOT / 'new_code/results/parse_results')

    def test_auto_attempts_are_unique_children_and_do_not_create_outputs(self):
        from parsing.unified.storage import resolve_output
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            base = Path(folder) / 'parse_results'
            first, second = resolve_output(None, base=base), resolve_output(None, base=base)
            self.assertEqual(first.parent, base)
            self.assertEqual(second.parent, base)
            self.assertNotEqual(first, second)
            self.assertFalse(base.exists())

    def test_explicit_run_name_and_absolute_child_have_same_destination(self):
        from parsing.unified.storage import resolve_output
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            base = Path(folder) / 'parse_results'
            self.assertEqual(resolve_output(Path('attempt-1'), base=base), base / 'attempt-1')
            self.assertEqual(resolve_output(base / 'attempt-1', base=base), base / 'attempt-1')

    def test_other_system_and_traversal_paths_are_rejected(self):
        from parsing.unified.storage import resolve_output
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            base = Path(folder) / 'parse_results'
            for value in (Path('..'), Path('../reconciliation_results/run'), Path('nested/run'),
                          Path(folder) / 'reconciliation_results/run', base):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    resolve_output(value, base=base)


if __name__ == '__main__':
    unittest.main()
