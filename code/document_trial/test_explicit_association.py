"""Offline contract checks; no inference or subprocesses."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from .explicit_association import build, export
from .explicit_association import digest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'analytics/results/sic12_document/evaluation-v1-20261025/page-0005'


class ExplicitTests(unittest.TestCase):
    def setUp(self):
        self.r = json.loads((BASE/'R-reconciled.json').read_bytes())
        self.d = dict(identity=self.r['identity'], panels=['p0-b11-c0','p0-b12-c0'],
                      caption='p0-b12-c1', group_id='fig6-explicit-v1',
                      baseline_sha256=digest((BASE/'R-reconciled.json').read_bytes()))

    def test_real_case_preserves_input(self):
        before=copy.deepcopy(self.r)
        result=build(self.r,self.d)
        self.assertEqual(before,self.r)
        self.assertEqual(len(result['panels']),2)
        self.assertEqual(result['review_status'],'agent_reviewed_pending_human_validation')
        self.assertNotIn('bbox',result)
        self.assertTrue(all(x['id'].startswith(self.r['identity']['document_sha256']) for x in result['panels']))

    def test_invalid_declarations(self):
        cases=[dict(panels=['absent','p0-b12-c0']),dict(panels=['p0-b11-c0']*2),
               dict(caption='p0-b11-c0'),dict(panels=['p0-b12-c1','p0-b11-c0']),
               dict(conflicts=['other-group'])]
        for change in cases:
            with self.subTest(change=change),self.assertRaises(ValueError):
                build(self.r,dict(self.d,**change))
        wrong=copy.deepcopy(self.d);wrong['identity']['physical_page']=6
        with self.assertRaises(ValueError):build(self.r,wrong)

    def test_export_idempotent_and_conflict_protected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            dest=Path(folder)/'output'
            export(BASE/'R-reconciled.json',self.d,dest)
            first=(dest/'group.json').read_bytes()
            export(BASE/'R-reconciled.json',self.d,dest)
            self.assertEqual(first,(dest/'group.json').read_bytes())
            changed=dict(self.d,group_id='another')
            with self.assertRaises(ValueError):export(BASE/'R-reconciled.json',changed,dest)
            self.assertEqual(first,(dest/'group.json').read_bytes())

    def test_failure_has_diagnostic_no_group(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            dest=Path(folder)/'bad'
            with self.assertRaises(ValueError):export(BASE/'R-reconciled.json',dict(self.d,caption='bad'),dest)
            self.assertTrue((dest/'diagnostic.json').exists())
            self.assertFalse((dest/'group.json').exists())

    def test_wrong_baseline_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            with self.assertRaises(ValueError):
                export(BASE/'R-reconciled.json',dict(self.d,baseline_sha256='0'*64),Path(folder)/'bad')
