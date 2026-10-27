"""Exercise the launcher's Python bootstrap with an inert argparse entrypoint."""
import argparse
import contextlib
import io
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch


class LauncherTests(unittest.TestCase):
    def bootstrap(self):
        text=Path(__file__).with_name('test_labels.sh').read_text(encoding='utf-8')
        return re.search(r"colab exec[^\n]*<<'PY'[^\n]*\n(.*?)\nPY",text,re.S).group(1)

    def test_kernel_arguments_are_isolated_and_success_is_explicit(self):
        argv=sys.argv;paths=sys.path[:];output=io.StringIO()
        def inert_entry(*args,**kwargs):
            parser=argparse.ArgumentParser();parser.add_argument('--worker',nargs=2)
            self.assertIsNone(parser.parse_args().worker)
        try:
            sys.argv=['colab_kernel_launcher.py','-f','kernel.json']
            with patch('runpy.run_module',side_effect=inert_entry),contextlib.redirect_stdout(output):
                exec(self.bootstrap(),{})
            self.assertEqual(sys.argv,['colab_kernel_launcher.py','-f','kernel.json'])
            self.assertEqual(sys.path,paths)
            self.assertEqual(output.getvalue().strip(),'LOCALIZED_LABELS_COMPLETED')
        finally:sys.argv=argv

    def test_failure_restores_kernel_and_never_prints_success(self):
        argv=sys.argv[:];paths=sys.path[:];output=io.StringIO()
        with patch('runpy.run_module',side_effect=SystemExit(2)),contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit):exec(self.bootstrap(),{})
        self.assertEqual(output.getvalue(),'')
        self.assertEqual(sys.argv,argv);self.assertEqual(sys.path,paths)


if __name__=='__main__':unittest.main()
