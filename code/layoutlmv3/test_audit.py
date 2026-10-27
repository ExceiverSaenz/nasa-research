"""Behavior tests for a reference-free audit. No GPU or inference dependencies."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
import zipfile


def region(identifier, box, label='table', score=.8):
    return {'region_id': identifier, 'bbox': box, 'type': label, 'native_label': label,
            'class_id': ('text', 'title', 'list', 'table', 'figure').index(label), 'score': score}


def document(regions):
    return {'document_id': 'pdf-hash', 'run_id': 'run-1', 'page': 3,
            'coordinate_system': {'width_px': 100, 'height_px': 200,
                'coordinate_system': {'unit': 'pixel', 'origin': 'top-left', 'bbox_format': 'xyxy'}},
            'regions': regions}


class AuditTests(unittest.TestCase):
    def audit(self, data, **parameters):
        self.assertIsNotNone(importlib.util.find_spec('evaluation'), 'Audit package is missing')
        from evaluation.audit import audit_regions
        return audit_regions(data, **dict({'iou_threshold': .9, 'containment_threshold': .95}, **parameters))

    def test_clean_and_empty_results_are_valid_without_quality_claim(self):
        for regions in [[], [region('one', [1, 2, 10, 20]), region('two', [30, 40, 50, 60])]]:
            with self.subTest(count=len(regions)):
                report = self.audit(document(regions))
                self.assertEqual(report['summary']['valid_region_count'], len(regions))
                self.assertEqual(report['summary']['invalid_region_count'], 0)
                self.assertEqual(report['summary']['compared_pair_count'], len(regions) * (len(regions)-1)//2)
                self.assertEqual(report['validation_errors'], [])
                self.assertEqual(report['alerts'], [])
                self.assertIsNone(report['quality_score'])

    def test_same_class_identical_boxes_are_one_possible_duplicate_not_two_alerts(self):
        report = self.audit(document([region('a', [0, 0, 10, 10]), region('b', [0, 0, 10, 10])]))
        self.assertEqual(len(report['alerts']), 1)
        alert = report['alerts'][0]
        self.assertEqual(alert['kind'], 'possible_duplicate')
        self.assertEqual(alert['region_ids'], ['a', 'b'])
        self.assertEqual(alert['iou'], 1)
        self.assertEqual(report['summary']['alerted_region_count'], 2)

    def test_cross_class_similar_boxes_are_conflict(self):
        report = self.audit(document([region('a', [0, 0, 10, 10], 'table'),
                                      region('b', [0, 0, 10, 10], 'figure')]))
        self.assertEqual(report['alerts'][0]['kind'], 'class_conflict')
        self.assertEqual(report['alerts'][0]['classes'], ['table', 'figure'])

    def test_containment_detects_low_iou_pair_and_names_inner_outer(self):
        report = self.audit(document([region('outer', [0, 0, 100, 100], 'figure'),
                                      region('inner', [10, 10, 20, 20], 'table')]))
        self.assertEqual(len(report['alerts']), 1)
        alert = report['alerts'][0]
        self.assertEqual(alert['kind'], 'possible_containment')
        self.assertAlmostEqual(alert['iou'], .01)
        self.assertEqual(alert['intersection_over_smaller'], 1)
        self.assertEqual(alert['inner_region_id'], 'inner')
        self.assertEqual(alert['outer_region_id'], 'outer')

    def test_touching_boxes_and_partial_overlap_below_threshold_are_not_alerts(self):
        report = self.audit(document([region('a', [0, 0, 10, 10]),
            region('b', [10, 0, 20, 10]), region('c', [5, 5, 15, 15])]))
        self.assertEqual(report['alerts'], [])

    def test_threshold_is_inclusive_and_not_a_score_filter(self):
        data = document([region('a', [0, 0, 10, 10], score=.01),
                         region('b', [0, 0, 5, 10], score=.99)])
        self.assertEqual(self.audit(data, iou_threshold=.5)['alerts'][0]['kind'], 'possible_duplicate')
        self.assertEqual(self.audit(data, iou_threshold=.6)['alerts'][0]['kind'], 'possible_containment')

    def test_invalid_boxes_are_reported_and_excluded_from_pair_comparison(self):
        cases = [([-1, 0, 10, 10], 'out_of_bounds'), ([0, 0, 101, 10], 'out_of_bounds'),
                 ([5, 0, 5, 10], 'invalid_bbox'), ([10, 0, 5, 10], 'invalid_bbox'),
                 ([0, 0, float('nan'), 10], 'invalid_bbox'),
                 ([0, 0, float('inf'), 10], 'invalid_bbox'),
                 ([0, 0, True, 10], 'invalid_bbox'), ([0, 0, 10], 'invalid_bbox')]
        for box, code in cases:
            with self.subTest(box=box):
                report = self.audit(document([region('bad', box), region('good', [0, 0, 10, 10])]))
                self.assertEqual(report['summary']['invalid_region_count'], 1)
                self.assertEqual(report['summary']['compared_pair_count'], 0)
                self.assertIn(code, [item['code'] for item in report['validation_errors']])
                # The audit itself must remain serializable even for NaN input.
                json.dumps(report, allow_nan=False)

    def test_duplicate_ids_and_unknown_classes_are_not_silently_accepted(self):
        unknown = region('unknown', [0, 0, 10, 10])
        unknown.update(type='caption', native_label='caption', class_id=9)
        report = self.audit(document([region('repeat', [0, 0, 10, 10]),
                                      region('repeat', [0, 0, 10, 10]), unknown]))
        self.assertEqual(report['summary']['invalid_region_count'], 3)
        self.assertEqual(report['summary']['compared_pair_count'], 0)
        codes = [item['code'] for item in report['validation_errors']]
        self.assertEqual(codes.count('duplicate_region_id'), 2)
        self.assertIn('unknown_class', codes)

    def test_bad_scores_labels_missing_ids_and_non_objects_are_reported(self):
        data = document([region('score', [0, 0, 10, 10], score=1.1),
                         region('mismatch', [0, 0, 10, 10]), region('', [0, 0, 10, 10]), None])
        data['regions'][1]['class_id'] = 4
        report = self.audit(data)
        self.assertEqual(report['summary']['invalid_region_count'], 4)
        codes = {item['code'] for item in report['validation_errors']}
        self.assertTrue({'invalid_score', 'class_mismatch', 'invalid_region_id', 'invalid_region'}.issubset(codes))

    def test_bad_parameters_or_document_schema_raise_before_audit(self):
        for value in [0, -1, 1.1, True, float('nan'), float('inf'), '0.9']:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.audit(document([]), iou_threshold=value)
        for value in [0, 1.1, float('nan')]:
            with self.assertRaises(ValueError):
                self.audit(document([]), containment_threshold=value)
        malformed = [None, {}, document(None)]
        for key, value in [('width_px', 0), ('height_px', True)]:
            item = document([]); item['coordinate_system'][key] = value; malformed.append(item)
        item = document([]); item['coordinate_system']['coordinate_system']['unit'] = 'point'; malformed.append(item)
        for data in malformed:
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.audit(data)

    def test_deterministic_report_does_not_modify_input(self):
        data = document([region('a', [0, 0, 10, 10]), region('b', [0, 0, 10, 10])])
        before = copy.deepcopy(data)
        first = self.audit(data)
        self.assertEqual(first, self.audit(data))
        self.assertEqual(data, before)

    def test_real_saved_result_is_consumed_without_loading_detector(self):
        root = Path(__file__).resolve().parents[2]
        archive = root / 'code/results/layoutlmv3-page/20261023T153938Z/result.zip'
        with zipfile.ZipFile(archive) as zipped:
            data = json.loads(zipped.read('page/regions.json'))
        report = self.audit(data)
        self.assertEqual(report['summary']['input_region_count'], 23)
        self.assertEqual(report['validation_errors'], [])
        pairs = {frozenset(a['region_ids']): a['kind'] for a in report['alerts']}
        prefix = '20261023T153944Z-ad54e9f6-p3-r'
        self.assertEqual(pairs[frozenset([prefix+'16', prefix+'19'])], 'class_conflict')
        self.assertEqual(pairs[frozenset([prefix+'15', prefix+'17'])], 'possible_containment')


if __name__ == '__main__':
    unittest.main()
