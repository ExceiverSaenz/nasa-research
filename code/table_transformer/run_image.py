"""One image coordinator. No PDF parsing, session management or model fusion."""
import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
from pathlib import Path
import platform
import time
import traceback

from PIL import Image

from .detector import IMAGE_SHA256, TableTransformerDetector, file_sha256, validate_load_report
from .outputs import save_json, save_outputs


def run_image(image_path, output_dir, model_dir, detector_factory=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    stage, error, count, detector = 'input', None, None, None
    timings = {}
    manifest = {'started_utc': datetime.now(timezone.utc).isoformat(), 'input_path': str(image_path),
                'source_pdf': 'SiC_papers/12.pdf', 'physical_page': 3, 'render_dpi': 200,
                'environment': {'python': platform.python_version()},
                'code_sha256': {p.name: file_sha256(p) for p in sorted(Path(__file__).parent.glob('*.py'))}}
    for package in ('torch','torchvision','transformers','timm','Pillow','numpy','safetensors'):
        try: manifest['environment'][package] = metadata.version(package)
        except metadata.PackageNotFoundError: manifest['environment'][package] = None
    try:
        digest = file_sha256(image_path)
        manifest['input_sha256'] = digest
        if digest != IMAGE_SHA256:
            raise ValueError('Input differs from original LayoutLMv3 render')
        with Image.open(image_path) as source:
            image = source.convert('RGB')
        if image.size != (1654, 2205):
            raise ValueError('Unexpected original render dimensions')
        stage = 'load'; step = time.perf_counter()
        detector = detector_factory() if detector_factory else TableTransformerDetector(model_dir)
        info = detector.load()
        save_json(output_dir/'load-report.json', info)
        validate_load_report(info)
        manifest['load_compatibility'] = {
            'accepted': True, 'policy': 'exact-weights-with-three-allowed-frozen-batchnorm-counters',
            'allowed_unused_counters_present': list(info['unexpected_keys'])}
        timings['load_seconds'] = time.perf_counter()-step
        stage = 'predict'; step = time.perf_counter()
        raw, regions = detector.predict(image)
        timings['predict_seconds'] = time.perf_counter()-step
        count = len(regions)
        stage = 'export'; step = time.perf_counter()
        save_outputs(image, raw, regions, output_dir)
        timings['export_seconds'] = time.perf_counter()-step
    except Exception as exception:
        error = '{}: {}'.format(type(exception).__name__, exception)
        (output_dir/'error.log').write_text(traceback.format_exc(), encoding='utf-8')
    finally:
        if detector is not None:
            if detector.load_report is not None: save_json(output_dir/'load-report.json', detector.load_report)
            try: manifest['detector'] = detector.metadata()
            except Exception as exception: manifest['detector_metadata_error'] = type(exception).__name__
        status = {'status': 'failed' if error else 'completed', 'stage': stage, 'error': error,
                  'region_count': count, 'timings': timings, 'elapsed_seconds': time.perf_counter()-started}
        manifest.update(status=status['status'], finished_utc=datetime.now(timezone.utc).isoformat(), timings=timings)
        save_json(output_dir/'run-manifest.json', manifest)
        save_json(output_dir/'page-status.json', status)
    return status


def main():
    parser = argparse.ArgumentParser(description='Independent TATR detection on the fixed full-page render')
    parser.add_argument('--image', required=True, type=Path)
    parser.add_argument('--model-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    status = run_image(args.image, args.output, args.model_dir)
    print(json.dumps(status, indent=2))
    return 0 if status['status']=='completed' else 1


if __name__ == '__main__': raise SystemExit(main())
