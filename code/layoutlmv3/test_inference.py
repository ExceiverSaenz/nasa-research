"""Local contracts and orchestration tests; no detector inference or network."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[2]


class InferenceTests(unittest.TestCase):
    def modules(self):
        self.assertIsNotNone(importlib.util.find_spec('inference'), 'Inference MVP is missing')
        from inference.types import RenderedPage, Predictions, LoadReport, RunResult
        from inference.render import render_page
        from inference.run_page import run_page
        return RenderedPage, Predictions, LoadReport, RunResult, render_page, run_page

    def test_render_physical_page_rotation_crop_and_readonly_rgb(self):
        _, _, _, _, render, _ = self.modules()
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / 'page.pdf'
            writer = PdfWriter()
            writer.add_blank_page(width=72, height=72)
            page = writer.add_blank_page(width=144, height=216)
            page.cropbox.lower_left = (0, 0)
            page.cropbox.upper_right = (72, 144)
            page.rotate(90)
            with pdf.open('wb') as output:
                writer.write(output)
            rendered = render(pdf, 2, dpi=72)
            self.assertEqual((rendered.width_px, rendered.height_px), (144, 72))
            self.assertEqual(rendered.rotation_deg, 90)
            self.assertEqual(rendered.crop_box_pt, (0., 0., 72., 144.))
            self.assertEqual(rendered.image.dtype, np.uint8)
            self.assertEqual(rendered.image.shape[2], 3)
            self.assertFalse(rendered.image.flags.writeable)
            for number in (0, 3):
                with self.assertRaises(ValueError):
                    render(pdf, number)

    def test_selected_page_is_rendered_at_200_dpi(self):
        _, _, _, _, render, _ = self.modules()
        page = render(ROOT / 'SiC_papers/12.pdf', 3)
        self.assertEqual(page.dpi, 200)
        self.assertEqual(page.page_number, 3)
        width_pt = page.crop_box_pt[2] - page.crop_box_pt[0]
        self.assertLessEqual(abs(page.width_px - width_pt * 200 / 72), 1)

    def test_predictions_reject_invalid_arrays_and_accept_empty(self):
        _, Predictions, _, _, _, _ = self.modules()
        def make(boxes, ids, scores):
            return Predictions(np.array(boxes, dtype=np.float32).reshape(-1, 4),
                               np.array(ids, dtype=np.int64), np.array(scores, dtype=np.float32),
                               ('text', 'title', 'list', 'table', 'figure'), 100, 200)
        self.assertEqual(make([], [], []).count, 0)
        cases = [([[0, 0, 101, 20]], [0], [.5]),
                 ([[0, 0, 10, 20]], [5], [.5]),
                 ([[0, 0, 10, 20]], [0], [float('nan')]),
                 ([[0, 0, 0, 20]], [0], [.5]),
                 ([[0, 0, 10, 20]], [], [.5])]
        for boxes, ids, scores in cases:
            with self.subTest(boxes=boxes, ids=ids, scores=scores):
                with self.assertRaises(ValueError):
                    make(boxes, ids, scores)

    def test_checkpoint_diagnostics_identify_missing_unexpected_and_shapes(self):
        self.modules()
        from inference.detector import compare_state_dicts
        expected = {'ok': np.zeros((2,)), 'missing': np.zeros((3,)), 'shape': np.zeros((2, 3))}
        found = {'ok': np.ones((2,)), 'extra': np.zeros((1,)), 'shape': np.zeros((3, 2))}
        report = compare_state_dicts(expected, found)
        self.assertEqual(report.missing_keys, ('missing',))
        self.assertEqual(report.unexpected_keys, ('extra',))
        self.assertEqual(report.shape_mismatches, (('shape', (2, 3), (3, 2)),))
        self.assertFalse(report.is_exact_match)

    def test_detector_import_and_preload_validation_need_no_torch(self):
        self.modules()
        result = subprocess.run([sys.executable, '-c',
            'import sys; from inference.detector import LayoutLMv3Detector; '
            'assert "torch" not in sys.modules; assert "detectron2" not in sys.modules'],
            cwd=Path(__file__).parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        from inference.detector import LayoutLMv3Detector
        detector = LayoutLMv3Detector(
            ROOT / 'code/vendor/unilm/layoutlmv3/examples/object_detection/cascade_layoutlmv3.yaml',
            ROOT / 'code/models/layoutlmv3-publaynet/model_final.pth',
            ROOT / 'code/models/layoutlmv3-publaynet')
        self.assertFalse(detector.is_loaded)
        with self.assertRaises(RuntimeError):
            detector.predict(np.zeros((10, 10, 3), dtype=np.uint8))

    def test_success_exports_original_coordinates_and_does_not_mutate_render(self):
        RenderedPage, Predictions, LoadReport, _, _, run = self.modules()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            image = np.full((200, 100, 3), 255, dtype=np.uint8)
            image.setflags(write=False)
            rendered = RenderedPage(ROOT / 'SiC_papers/12.pdf', 3, 200, image, (0., 0., 36., 72.), 0)
            class Detector:
                load_report = LoadReport()
                def load(self):
                    return self.load_report
                def predict(self, image):
                    return Predictions(np.array([[10, 20, 70, 120]], dtype=np.float32),
                        np.array([3], dtype=np.int64), np.array([.9], dtype=np.float32),
                        ('text', 'title', 'list', 'table', 'figure'), 100, 200)
                def metadata(self):
                    return {'input': {'min_size_test': 800, 'max_size_test': 1333}}
            result = run(ROOT / 'SiC_papers/12.pdf', 3, output,
                         detector_factory=Detector, renderer=lambda *a, **k: rendered)
            self.assertTrue(result.succeeded)
            regions = json.loads((output / 'regions.json').read_text())
            self.assertEqual(regions['regions'][0]['bbox'], [10., 20., 70., 120.])
            self.assertEqual(regions['regions'][0]['native_label'], 'table')
            self.assertEqual(regions['page'], 3)
            self.assertTrue((image == 255).all())
            with Image.open(output / 'overlay.png') as overlay:
                self.assertEqual(overlay.size, (100, 200))
            manifest = json.loads((output / 'run-manifest.json').read_text())
            self.assertEqual(manifest['render']['dpi'], 200)
            self.assertEqual(manifest['detector']['input']['max_size_test'], 1333)
            self.assertEqual(manifest['document']['sha256'], '9cea2fa5ad94c6a31031c72a9c3f698d571c85c810af644304c3b9f0d306f660')
            self.assertTrue((output / 'regions-raw.json').exists())
            self.assertTrue((output / 'load-report.json').exists())
            with self.assertRaises(FileExistsError):
                run(ROOT / 'SiC_papers/12.pdf', 3, output, detector_factory=Detector)

    def test_failed_load_preserves_diagnostics_and_never_runs_predict(self):
        _, _, LoadReport, _, render, run = self.modules()
        class BrokenDetector:
            load_report = LoadReport(missing_keys=('backbone.weight',))
            def load(self):
                raise ValueError('Checkpoint incompatible')
            def predict(self, image):
                raise AssertionError('Must not infer')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'failed'
            result = run(ROOT / 'SiC_papers/12.pdf', 3, output,
                         detector_factory=BrokenDetector, renderer=render)
            self.assertFalse(result.succeeded)
            self.assertIsNone(result.region_count)
            status = json.loads((output / 'page-status.json').read_text())
            self.assertEqual(status['stage'], 'load')
            self.assertEqual(status['status'], 'failed')
            report = json.loads((output / 'load-report.json').read_text())
            self.assertEqual(report['missing_keys'], ['backbone.weight'])
            self.assertFalse((output / 'regions.json').exists())
            self.assertTrue((output / 'run-manifest.json').exists())

    def test_failed_render_preserves_status_and_does_not_construct_detector(self):
        _, _, _, _, _, run = self.modules()
        def forbidden():
            raise AssertionError('Detector must not be constructed')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'failed'
            result = run(ROOT / 'SiC_papers/12.pdf', 999, output, detector_factory=forbidden)
            self.assertFalse(result.succeeded)
            self.assertEqual(result.stage, 'render')
            self.assertTrue((output / 'page-status.json').exists())

    def test_render_transform_maps_pdf_corners_for_all_rotations(self):
        RenderedPage, _, _, _, _, _ = self.modules()
        from inference.outputs import render_geometry
        # PDF top-left (10, 90) on a 40 x 60 pt CropBox, rendered at 2 px/pt.
        for rotation, size, expected in [(0, (80, 120), [0, 0]),
                                         (90, (120, 80), [120, 0]),
                                         (180, (80, 120), [80, 120]),
                                         (270, (120, 80), [0, 80])]:
            with self.subTest(rotation=rotation):
                width, height = size
                page = RenderedPage(Path('unused.pdf'), 1, 144,
                    np.zeros((height, width, 3), dtype=np.uint8), (10., 30., 50., 90.), rotation)
                geometry = render_geometry(page)
                matrix = np.array(geometry['pdf_to_render_matrix'])
                inverse = np.array(geometry['render_to_pdf_matrix'])
                point = matrix @ np.array([10., 90., 1.])
                np.testing.assert_allclose(point[:2], expected)
                np.testing.assert_allclose(inverse @ point, [10., 90., 1.])

    def test_zero_detections_is_completed_with_empty_exports(self):
        RenderedPage, Predictions, LoadReport, _, _, run = self.modules()
        class EmptyDetector:
            load_report = LoadReport()
            def load(self):
                return self.load_report
            def predict(self, image):
                return Predictions(np.empty((0, 4), dtype=np.float32), np.empty(0, dtype=np.int64),
                    np.empty(0, dtype=np.float32), ('text',), image.shape[1], image.shape[0])
            def metadata(self):
                return {'test_double': True}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            def render(pdf, page, dpi):
                return RenderedPage(pdf, page, dpi, np.zeros((10, 10, 3), dtype=np.uint8),
                                    (0., 0., 10., 10.), 0)
            result = run(ROOT / 'SiC_papers/12.pdf', 3, output,
                         detector_factory=EmptyDetector, renderer=render)
            self.assertTrue(result.succeeded)
            self.assertEqual(result.region_count, 0)
            self.assertEqual(json.loads((output / 'regions.json').read_text())['regions'], [])

    def test_missing_model_manifest_still_preserves_failure_status(self):
        _, _, _, _, _, run = self.modules()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.yaml'
            weights = root / 'weights.pth'
            config.write_text('unused')
            weights.write_bytes(b'unused')
            output = root / 'run'
            result = run(ROOT / 'SiC_papers/12.pdf', 3, output,
                         config_path=config, checkpoint_path=weights, model_config_dir=root)
            self.assertFalse(result.succeeded)
            self.assertEqual(json.loads((output / 'page-status.json').read_text())['stage'], 'load')


if __name__ == '__main__':
    unittest.main()
