"""Local contracts only; fake detector tests do not prove model/GPU inference."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'code'))
IMAGE = ROOT / 'code/results/layoutlmv3-page/20261023T153938Z/review/render.png'


class DetectionTests(unittest.TestCase):
    def test_real_decoder_boxes_export_json_native_clipping_flag(self):
        decode, save, _ = self.modules()
        regions = decode([[10, 0, -10]], [[.5, .5, .4, .2]], 100, 200, .5)
        with tempfile.TemporaryDirectory() as directory:
            document = save(Image.new('RGB', (100, 200)), {}, regions, Path(directory))
            self.assertIs(document['regions'][0]['crop_clipped'], False)
            self.assertIs(json.loads((Path(directory)/'regions.json').read_text())['regions'][0]['crop_clipped'], False)

    def test_observed_batchnorm_counters_allow_inference_and_remain_in_report(self):
        _, _, run = self.modules()
        class Counters:
            load_report = {'missing_keys': [], 'unexpected_keys': [
                'model.backbone.conv_encoder.model.layer2.0.downsample.1.num_batches_tracked',
                'model.backbone.conv_encoder.model.layer3.0.downsample.1.num_batches_tracked',
                'model.backbone.conv_encoder.model.layer4.0.downsample.1.num_batches_tracked'],
                'mismatched_keys': [], 'error_msgs': []}
            def load(self): return self.load_report
            def predict(self, image): return {'logits': [], 'boxes_cxcywh_normalized': []}, []
            def metadata(self): return {'test_double': True}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'run'
            result = run(IMAGE, output, directory, detector_factory=Counters)
            self.assertEqual(result['status'], 'completed', result)
            self.assertEqual(json.loads((output/'load-report.json').read_text()), Counters.load_report)

    def test_load_policy_rejects_all_other_incompatibilities(self):
        from table_transformer.detector import validate_load_report
        for key, value in [('missing_keys', ['weight']), ('mismatched_keys', [['weight', [2], [3]]]),
                           ('error_msgs', ['error']), ('unexpected_keys', ['other.num_batches_tracked']),
                           ('unexpected_keys', ['model.backbone.conv_encoder.model.layer2.0.downsample.1.weight'])]:
            report = dict(missing_keys=[], unexpected_keys=[], mismatched_keys=[], error_msgs=[])
            report[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_load_report(report)

    def modules(self):
        self.assertIsNotNone(importlib.util.find_spec('table_transformer'), 'TATR package missing')
        from table_transformer.detector import decode_queries
        from table_transformer.outputs import save_outputs
        from table_transformer.run_image import run_image
        return decode_queries, save_outputs, run_image

    def test_decodes_to_original_pixels_and_excludes_background(self):
        decode, _, _ = self.modules()
        regions = decode([[10, 0, -10], [0, 10, -10], [0, 0, 10]],
                         [[.5, .5, .4, .2], [.5, .5, .2, .4], [.5, .5, 1, 1]], 100, 200, .5)
        self.assertEqual(len(regions), 2)
        np.testing.assert_allclose(regions[0]['bbox'], [30, 80, 70, 120])
        self.assertEqual(regions[1]['native_label'], 'table rotated')
        self.assertEqual(regions[1]['query_id'], 1)

    def test_threshold_inclusive_and_no_clipping_of_predictions(self):
        decode, _, _ = self.modules()
        # Softmax of [0,0,-inf] is approximated exactly with underflow.
        result = decode([[0, 0, -1000]], [[0, .5, 1, 1]], 100, 200, .5)
        self.assertEqual(result[0]['score'], .5)
        self.assertEqual(result[0]['bbox'], [-50., 0., 50., 200.])
        self.assertEqual(decode([[0, 0, -1000]], [[0, .5, 1, 1]], 100, 200, .51), [])

    def test_invalid_queries_and_parameters_rejected(self):
        decode, _, _ = self.modules()
        for logits, boxes in [([[1, 2]], [[.5]*4]), ([[0, 1, 2]], []),
                              ([[0, 1, float('nan')]], [[.5]*4]),
                              ([[0, 1, 2]], [[.5, .5, -1, .3]])]:
            with self.subTest(logits=logits), self.assertRaises(ValueError):
                decode(logits, boxes, 100, 200, .5)
        for threshold in [-.1, 1.1, float('nan'), True]:
            with self.assertRaises(ValueError):
                decode([[1, 0, 0]], [[.5]*4], 100, 200, threshold)

    def test_crop_records_clipping_and_preserves_raw_box(self):
        _, save, _ = self.modules()
        image = Image.new('RGB', (100, 200), 'white')
        regions = [{'query_id': 0, 'native_label': 'table', 'class_id': 0, 'score': .9,
                    'bbox': [-10., 20., 50., 250.]}]
        with tempfile.TemporaryDirectory() as directory:
            result = save(image, {'logits': [[1, 0, 0]], 'boxes_cxcywh_normalized': [[.2,.5,.6,1.15]]},
                          regions, Path(directory))
            self.assertEqual(result['regions'][0]['bbox'], [-10., 20., 50., 250.])
            self.assertEqual(result['regions'][0]['crop_bbox'], [0, 20, 50, 200])
            self.assertTrue(result['regions'][0]['crop_clipped'])
            with Image.open(Path(directory)/'crops/query-0.png') as crop:
                self.assertEqual(crop.size, (50, 180))
            self.assertEqual(image.getpixel((0, 20)), (255, 255, 255))

    def test_empty_detection_exports_are_not_failure(self):
        _, _, run = self.modules()
        class Empty:
            load_report = {'missing_keys': [], 'unexpected_keys': [], 'mismatched_keys': [], 'error_msgs': []}
            def load(self): return self.load_report
            def predict(self, image): return {'logits': [[0, 0, 10]], 'boxes_cxcywh_normalized': [[.5]*4]}, []
            def metadata(self): return {'test_double': True}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'run'
            result = run(IMAGE, output, Path(directory), detector_factory=Empty)
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['region_count'], 0)
            self.assertEqual(json.loads((output/'regions.json').read_text())['regions'], [])
            self.assertTrue((output/'regions-raw.json').exists())
            with self.assertRaises(FileExistsError): run(IMAGE, output, Path(directory), detector_factory=Empty)

    def test_failed_load_retains_report_and_status(self):
        _, _, run = self.modules()
        class Broken:
            load_report = {'missing_keys': ['weight'], 'unexpected_keys': [], 'mismatched_keys': [], 'error_msgs': []}
            def load(self): raise ValueError('Incompatible checkpoint')
            def metadata(self): raise RuntimeError('Unavailable metadata')
            def predict(self, image): raise AssertionError('Must not infer')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'run'
            result = run(IMAGE, output, Path(directory), detector_factory=Broken)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['stage'], 'load')
            self.assertEqual(json.loads((output/'load-report.json').read_text())['missing_keys'], ['weight'])
            self.assertTrue((output/'error.log').exists())

    def test_changed_image_rejected_before_loading_model(self):
        _, _, run = self.modules()
        def forbidden(): raise AssertionError('Do not construct detector')
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/'changed.png'; Image.new('RGB',(20, 20)).save(image)
            result = run(image, Path(directory)/'run', Path(directory), detector_factory=forbidden)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['stage'], 'input')

    def test_image_export_failure_preserves_raw_queries_and_filtered_boxes(self):
        _, save, _ = self.modules()
        raw={'logits':[[10,0,0]],'boxes_cxcywh_normalized':[[.5,.5,.5,.5]]}
        regions=[{'query_id':0,'native_label':'table','class_id':0,'score':.9,'bbox':[1.,2.,8.,9.]}]
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)
            with patch('PIL.Image.Image.save',side_effect=OSError('Image export failed')):
                with self.assertRaises(OSError): save(Image.new('RGB',(10,10)),raw,regions,output)
            self.assertEqual(json.loads((output/'regions-raw.json').read_text()),raw)
            self.assertEqual(json.loads((output/'regions.json').read_text())['regions'][0]['bbox'],[1.,2.,8.,9.])


if __name__ == '__main__': unittest.main()
