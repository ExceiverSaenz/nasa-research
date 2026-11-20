"""Hand-derived controls for the offline analysis; never run a parser."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import hashlib
import importlib
import json
from pathlib import Path
import sys
import unittest
import uuid
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class AnalysisControls(unittest.TestCase):
    def setUp(self):
        try:
            self.a = importlib.import_module('analytics.automatic.core')
        except ModuleNotFoundError:
            self.fail('Offline analysis core is not implemented')

    def test_invalid_geometry_is_distinct_from_missing(self):
        self.assertEqual(self.a.box_state(None), 'missing')
        for b in ([0, 0, 0, 1], [-.1, 0, 1, 1], [False, 0, 1, 1], [0, 0, float('nan'), 1]):
            self.assertEqual(self.a.box_state(b), 'invalid')
        self.assertEqual(self.a.box_state([0, 0, 1, 1]), 'valid')

    def test_directional_containment_preserves_small_inside_large(self):
        s = self.a.overlap([0, 0, 1, 1], [0, 0, .25, 1])
        self.assertEqual(s, {'intersection': .25, 'iou': .25, 'fraction_a': .25, 'fraction_b': 1.0})

    def test_union_is_not_enclosing_rectangle_or_sum(self):
        self.assertEqual(self.a.union_area([[0, 0, 1, .5], [0, .5, .5, 1], [0, 0, 1, .5]]), .75)

    def test_many_to_one_edges_survive_below_iou_threshold(self):
        left = [{'id': 'a', 'bbox_normalized': [0, 0, .9, 1], 'raw_label': 'text'}]
        right = [{'id': str(i), 'bbox_normalized': [i*.3, 0, (i+1)*.3, 1], 'raw_label': 'text'} for i in range(3)]
        edges, groups = self.a.compare_page(left, right)
        self.assertEqual(len(edges), 3)
        self.assertTrue(all(not e['threshold_match'] for e in edges))
        self.assertEqual((groups[0]['n_a'], groups[0]['n_b']), (1, 3))
        self.assertAlmostEqual(groups[0]['union_iou'], 1)

    def test_two_missing_labels_are_not_label_agreement(self):
        row = {'id': 'a', 'bbox_normalized': [0, 0, 1, 1], 'raw_label': None}
        edges, _ = self.a.compare_page([row], [{**row, 'id': 'b'}])
        self.assertIsNone(edges[0]['literal_label_match'])
        self.assertFalse(edges[0]['literal_label_evaluable'])

    def test_joint_caption_geometry_does_not_create_relationship(self):
        rows = [{'id': 'f', 'raw_label': 'image', 'original_ref': 'f', 'native_parent_ref': None,
                 'bbox_normalized': [0, 0, 1, 1], 'relations': None},
                {'id': 'c', 'raw_label': 'image_caption', 'original_ref': 'c', 'native_parent_ref': None,
                 'bbox_normalized': None, 'relations': None}]
        p = self.a.native_patterns(rows)
        self.assertEqual(p['parent_edges'], 0)
        self.assertEqual(p['visual_caption_parents'], 0)
        self.assertEqual(p['semantic_review_status'], 'not_reviewed')

    def test_native_image_body_is_not_a_panel_and_child_bbox_stays_null(self):
        rows = [{'id': 'f', 'raw_label': 'image', 'original_ref': 'f', 'native_parent_ref': None, 'relations': None},
                {'id': 'b', 'raw_label': 'image_body', 'original_ref': 'b', 'native_parent_ref': 'f', 'bbox_normalized': None, 'relations': None},
                {'id': 'c', 'raw_label': 'image_caption', 'original_ref': 'c', 'native_parent_ref': 'f', 'relations': None}]
        p = self.a.native_patterns(rows)
        self.assertEqual(p['parent_edges'], 2)
        self.assertEqual(p['visual_caption_parents'], 1)
        self.assertEqual(p['explicit_panel_nodes'], 0)
        self.assertIsNone(rows[1]['bbox_normalized'])

    def test_dangling_parent_and_isolated_list_item_not_fabricated(self):
        p = self.a.native_patterns([{'id': 'x', 'raw_label': 'list_item', 'original_ref': 'x',
                                    'native_parent_ref': 'absent', 'relations': None}])
        self.assertEqual(p['dangling_parent_refs'], 1)
        self.assertEqual(p['list_item_nodes'], 1)
        self.assertEqual(p['list_groups_with_items'], 0)

    def test_quantiles_and_mad_are_hand_checked(self):
        s = self.a.describe(list(range(20)))
        self.assertEqual(s['median'], 9.5)
        self.assertEqual(s['iqr'], 9.5)
        self.assertEqual(s['mad'], 5)
        self.assertAlmostEqual(s['p05'], .95)
        self.assertAlmostEqual(s['p95'], 18.05)

    def test_zero_spread_or_small_group_does_not_impute_outlier_score(self):
        self.assertFalse(self.a.describe([1]*30)['iqr_rule_evaluable'])
        self.assertFalse(self.a.describe([1, 9])['iqr_rule_evaluable'])
        self.assertIsNone(self.a.describe([])['median'])

    def test_cost_null_inference_and_device_memory_not_imputed_per_paper(self):
        r = {'results': [{'paper': '1.pdf', 'status': 'complete', 'result': {
            'total_parse_export_excluded_s': 20, 'inference_s': None, 'load_s': None, 'page_indices': [0, 1]}}],
            'resources': [{'elapsed_s': 0, 'ram_bytes': None, 'gpu': None},
                          {'elapsed_s': 1, 'ram_bytes': 1048576, 'gpu': [{'used_mib': 10}]}]}
        papers, stage = self.a.extract_cost(r, 'basic', 'source')
        self.assertIsNone(papers[0]['isolated_inference_s'])
        self.assertEqual(papers[0]['recorded_s_per_completed_page'], 10)
        self.assertNotIn('ram_peak_bytes', papers[0])
        self.assertEqual(stage['ram_peak_bytes'], 1048576)
        self.assertIsNone(stage['stage_wall_s'])
        self.assertEqual(stage['ram_missing_samples'], 1)

    def test_failures_keep_attempt_denominators_and_versions_separate(self):
        old = {'results': [{'paper': '1.pdf', 'status': 'complete'},
                           {'paper': '2.pdf', 'status': 'failed', 'error': 'TypeError', 'error_detail': 'private_ranges'}]}
        new = {'results': [{'paper': '1.pdf', 'status': 'complete'}, {'paper': '2.pdf', 'status': 'complete'}]}
        failures, rate = self.a.attempt_failures(old, 'basic', 'old', {'docvortex': '0.6.9'}, 2)
        _, corrected = self.a.attempt_failures(new, 'basic', 'new', {'docvortex': '0.6.7'}, 2)
        self.assertEqual((rate['attempted'], rate['failed'], rate['failure_fraction']), (2, 1, .5))
        self.assertEqual(corrected['failure_fraction'], 0)
        self.assertEqual(failures[0]['source_run_id'], 'old')
        self.assertEqual(failures[0]['docvortex'], '0.6.9')
        self.assertEqual(failures[0]['cause_detail'], 'private_ranges')

    def test_detector_timings_publish_observations_not_fabricated_sdk_pages(self):
        r = {'results': [{'paper': '1.pdf', 'status': 'complete', 'result': {'timings': [
            {'page_idx': 0, 'inference_s': .2}, {'page_idx': 1, 'inference_s': .4}]}}]}
        samples = self.a.page_timing_observations(r, 'heron', 'old')
        self.assertEqual([v['inference_s'] for v in samples], [.2, .4])
        self.assertEqual(self.a.page_timing_observations({'results': [{'paper': '1.pdf', 'result': {
            'total_parse_export_excluded_s': 9, 'page_indices': [0, 1]}}]}, 'basic', 'new'), [])

    def test_resolve_remote_path_checks_hash_and_containment(self):
        root = Path(os.environ.get('BBX_TEST_ARTIFACT_ROOT',str(_BBX_ROOT/'raw_results/tests/analytics/fixtures')))/'analytics'/uuid.uuid4().hex
        f = root/'basic'/'1'/'middle.json'; f.parent.mkdir(parents=True); f.write_text('{}')
        digest = hashlib.sha256(b'{}').hexdigest()
        p, fragment = self.a.resolve_ref(root, '/content/session/results/execute/basic/1/middle.json#/pages/0', digest)
        self.assertEqual(p, f.resolve()); self.assertEqual(fragment, '/pages/0')
        with self.assertRaises(ValueError): self.a.resolve_ref(root, '/content/results/execute/basic/1/middle.json', 'wrong')
        with self.assertRaises(ValueError): self.a.resolve_ref(root, '/content/results/execute/../../outside.json', digest)

    def test_json_pointer_does_not_silently_accept_absent_native_node(self):
        self.assertEqual(self.a.pointer({'pages': [{'blocks': [3]}]}, '/pages/0/blocks/0'), 3)
        with self.assertRaises((KeyError, IndexError, ValueError)):
            self.a.pointer({'pages': []}, '/pages/0/blocks/0')


class RunnerControls(unittest.TestCase):
    def test_offline_execution_verifies_sources_and_prepares_unreviewed_pages(self):
        try:
            runner = importlib.import_module('analytics.automatic.run_analysis')
        except ModuleNotFoundError:
            self.fail('Offline runner is not implemented')
        base = Path(os.environ.get('BBX_TEST_ARTIFACT_ROOT',str(_BBX_ROOT/'raw_results/tests/analytics/fixtures')))/'analytics'/uuid.uuid4().hex
        project = base/'project'; source = project/'source'; out = project/'analysis'/'fixture-run'
        source.mkdir(parents=True)
        def write(path, data):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        def digest(path):
            return hashlib.sha256(path.read_bytes()).hexdigest()
        pdf = project/'papers'/'SiC_papers'/'1.pdf'; pdf.parent.mkdir(parents=True); pdf.write_bytes(b'fixture-not-a-real-PDF')
        pdfsha = digest(pdf)
        inventory = project/'inventory.json'; write(inventory, [{'name': '1.pdf', 'bytes': pdf.stat().st_size, 'sha256': pdfsha, 'pages': 1}])
        plan = project/'plan.md'; plan.write_text('Fixture plan. No parser or visual inspection.', encoding='utf-8')
        write(project/'experiment.json', {'iou_threshold': .5, 'resource_interval_s': 1, 'measured_passes': 1})
        provenance, summary = {}, {}
        for tool in ('heron', 'heron101', 'basic', 'standard'):
            folder = source/'assembled'/tool/'1'; folder.mkdir(parents=True)
            native = folder/('page-0.json' if tool.startswith('heron') else 'middle.json')
            if tool.startswith('heron'):
                write(native, [{'bbox': [0, 0, 1, 1], 'label': 'picture'}])
                fragments = ['', None]
            else:
                write(native, {'pages': [{'page_idx': 0, 'blocks': [{'type': 'image', 'bbox': [0, 0, 1, 1],
                       'content': [{'type': 'image_caption', 'content': 'Caption fixture'}]}]}]})
                fragments = ['/pages/0/blocks/0', '/pages/0/blocks/0/content/0']
            rawref = '/content/fixture/results/execute/'+tool+'/1/'+native.name
            rows = [dict(id='box', tool=tool, paper_sha256=pdfsha, page_idx=0,
                         raw_label='picture' if tool.startswith('heron') else 'image',
                         bbox_raw=[0, 0, 1, 1], bbox_normalized=[0, 0, 1, 1], coordinate_system='normalized_top_left',
                         page_dimensions=[1, 1], original_ref=rawref+('#'+fragments[0] if fragments[0] else ''),
                         original_sha256=digest(native), relations=None, native_parent_ref=None, geometry_error=None)]
            if not tool.startswith('heron'):
                rows.append({**rows[0], 'id': 'caption', 'raw_label': 'image_caption', 'bbox_raw': None,
                             'bbox_normalized': None, 'original_ref': rawref+'#'+fragments[1],
                             'native_parent_ref': rawref+'#'+fragments[0]})
            normalized = folder/'normalized.json'; write(normalized, rows)
            files = {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size} for p in (native, normalized)}
            result = {'page_indices': [0], 'inference_s': None, 'load_s': None}
            result.update({'timings': [{'page_idx': 0, 'inference_s': .1}]} if tool.startswith('heron')
                          else {'total_parse_export_excluded_s': 2})
            receipt = source/'assembled'/tool/'receipt.json'
            write(receipt, {'tool': tool, 'results': [{'paper': '1.pdf', 'status': 'complete', 'files': files, 'result': result}], 'resources': []})
            provenance[tool] = {'run_id': source.name, 'receipt_sha256': digest(receipt), 'reused_not_executed': False}
            summary[tool] = {'papers': 1, 'pages': 1, 'bbox_rows': 1, 'rows_without_bbox': len(rows)-1,
                             'raw_labels': {'picture': 1} if tool.startswith('heron') else {'image': 1, 'image_caption': 1}}
        prior = project/'previous-fixture'/'download'
        prior_manifest = {}
        for tool in ('basic', 'standard'):
            rel = 'results/assembled-v1/'+tool+'/receipt.json'
            write(prior/rel, {'tool': tool, 'results': [{'paper': '1.pdf', 'status': 'failed', 'error': 'TypeError'}]})
            prior_manifest[rel] = {'sha256': digest(prior/rel), 'bytes': (prior/rel).stat().st_size}
        write(prior/'manifest.json', prior_manifest)
        write(prior/'provenance'/'runtime'/'environment-receipt.json', {
            'a': {'checks': [{'evidence': {'packages': {'docvortex': '0.6.9', 'mineru': '4.0.12'}}}]},
            'b': {'checks': [{'evidence': {'packages': {'docvortex': '0.6.9', 'mineru': '4.0.12'}}}]}})
        for tool in ('heron', 'heron101'):
            provenance[tool].update(run_id='previous-fixture', reused_not_executed=True)
        write(source/'tool-provenance.json', provenance)
        write(source/'metrics.json', {'summary': summary, 'papers': [], 'timing_limit': 'fixture'})
        write(source/'verification.json', {'status': 'fixture-only'})
        write(source/'final-status.json', {'papers': 1, 'pages': 1, 'successful_tool_page_outputs': 4})
        image = source/'viewer_source'/'pages'/pdfsha/'0.png'; image.parent.mkdir(parents=True); image.write_bytes(b'image-fixture-only')
        write(source/'background-lineage.json', {'sha256': {'pages/'+pdfsha+'/0.png': digest(image)}})
        write(source/'viewer_source'/'viewer.json', {'run_id': 'fixture', 'tools': list(provenance),
              'pages': [{'paper_sha256': pdfsha, 'page_idx': 0, 'image': 'pages/'+pdfsha+'/0.png'}]})
        before = {str(p): digest(p) for p in project.rglob('*') if p.is_file()}
        result = runner.execute(source, inventory, project, plan, project/'experiment.json', out)
        self.assertEqual(result['tool_page_outputs'], 4)
        verification = json.loads((out/'analysis_verification.json').read_text(encoding='utf-8'))
        self.assertTrue(verification['all_inputs_unchanged'])
        self.assertEqual(verification['human_reviewed_pages'], 0)
        batches = json.loads((out/'review_batches.json').read_text(encoding='utf-8'))
        self.assertEqual(len(batches['papers'][0]['pages']), 1)
        self.assertFalse(batches['papers'][0]['pages'][0]['page_case_inventory_complete'])
        self.assertEqual((out/'case_registry.jsonl').read_text(), '')
        import csv
        with (out/'attempt_failure_summary.csv').open(encoding='utf-8') as rate_file:
            rates = list(csv.DictReader(rate_file))
        self.assertEqual(len(rates), 6)
        old_basic = next(r for r in rates if r['source_run_id']=='previous-fixture' and r['tool']=='basic')
        self.assertEqual((old_basic['failed'], old_basic['attempted'], old_basic['docvortex']), ('1','1','0.6.9'))
        self.assertEqual(before, {name: digest(Path(name)) for name in before})
        with self.assertRaises(FileExistsError):
            runner.execute(source, inventory, project, plan, project/'experiment.json', out)


if __name__ == '__main__':
    unittest.main()
