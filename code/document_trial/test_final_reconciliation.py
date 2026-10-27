"""Offline integration and corruption tests on existing immutable evidence."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from . import final_reconciliation as final

ROOT = Path(__file__).resolve().parents[2]


class FinalTests(unittest.TestCase):
    def test_document_contract(self):
        out = final.build(ROOT)
        self.assertEqual(len(out['pages']), 13)
        self.assertEqual(len(out['accepted_groups']), 6)
        self.assertEqual(len(out['simple_controls']), 1)
        self.assertEqual(out['simple_controls'][0]['figure'], 'Fig. 5')
        self.assertEqual(len({g['id'] for g in out['accepted_groups']}), 6)
        fig6 = next(g for g in out['accepted_groups'] if g['figure'] == 'Fig. 6')
        self.assertEqual(len(fig6['acceptance_provenance']), 2)
        self.assertIn('overlapping', fig6['geometry_status'])
        self.assertTrue(all(g['transcription_status'] == 'not_validated' for g in out['accepted_groups']))
        self.assertTrue(all(not g['candidate']['captions'][0]['lm_text_support'] for g in out['accepted_groups']))
        self.assertEqual(out['pages'][2]['localized_enrichment']['table1'], 'pending_warning')
        self.assertIn('historical_table2_acceptance', out['pages'][2]['localized_enrichment'])
        self.assertEqual(set(out['parsers']), {'mineru', 'table_transformer', 'layoutlmv3'})
        self.assertEqual(out, final.build(ROOT))

    def mutated(self, suffix, mutate):
        original = final.read_json
        def altered(path):
            value = original(path)
            if str(path).replace('\\', '/').endswith(suffix):
                value = copy.deepcopy(value)
                mutate(value)
            return value
        return patch.object(final, 'read_json', side_effect=altered)

    def test_reject_corrupt_human_reference_and_missing_decision(self):
        for mutate in [lambda h: h['cases'][0].update(source_sha256='0'*64),
                       lambda h: h['cases'][0].update(decision='pending'),
                       lambda h: h['cases'][0].update(page=6),
                       lambda h: h['cases'][0]['members'][0].update(source_pointer='/bad'),
                       lambda h: h['cases'].append(copy.deepcopy(h['cases'][0]))]:
            with self.subTest(mutate=mutate), self.mutated('human-review.json', mutate):
                with self.assertRaises(ValueError): final.build(ROOT)

    def test_reject_identity_baseline_and_explicit_conflict(self):
        changes = [
            ('multipanel-candidates-v1/page-0005.json', lambda c: c['identity'].update(physical_page=6)),
            ('multipanel-candidates-v1/page-0005.json', lambda c: c['provenance'].update(baseline_sha256='0'*64)),
            ('fig6-explicit-association-v1/group.json', lambda g: g['panels'][0].update(id='foreign')),
            ('page-0005/M0-native.json', lambda n: n['pages'][0]['blocks'][11].update(content=[]))]
        for suffix, mutate in changes:
            with self.subTest(suffix=suffix), self.mutated(suffix, mutate):
                with self.assertRaises(ValueError): final.build(ROOT)

    def test_export_preserves_inputs_and_rejects_overwrite(self):
        before = final.protected_hashes(ROOT)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            dest = Path(folder)/'output'
            final.export(ROOT, dest)
            first = (dest/'document.json').read_bytes()
            final.export(ROOT, dest)
            self.assertEqual(first, (dest/'document.json').read_bytes())
            (dest/'review.html').write_text('incompatible')
            with self.assertRaises(ValueError): final.export(ROOT, dest)
            self.assertEqual(first, (dest/'document.json').read_bytes())
        self.assertEqual(before, final.protected_hashes(ROOT))

    def test_missing_source_rejected(self):
        original = final.read_json
        def missing(path):
            if str(path).endswith('human-review.json'): raise FileNotFoundError(path)
            return original(path)
        with patch.object(final, 'read_json', side_effect=missing):
            with self.assertRaises(FileNotFoundError): final.build(ROOT)
