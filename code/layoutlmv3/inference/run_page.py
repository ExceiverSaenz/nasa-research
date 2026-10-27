"""Single-page coordination and CLI; no explicit creation of remote sessions.

Integrates render, detector and outputs. README.md explains execution and historical evidence.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
import platform
import sys
import time
import traceback
import uuid
from typing import Callable, Optional

from PIL import Image

from .detector import LayoutLMv3Detector, file_sha256
from .outputs import render_geometry, save_json, save_manifest, save_overlay, save_regions
from .render import render_page
from .types import RunResult


def run_page(pdf_path: Path, page_number: int, output_dir: Path, *, dpi: int = 200,
             config_path: Optional[Path] = None, checkpoint_path: Optional[Path] = None,
             model_config_dir: Optional[Path] = None, device: str = 'cuda',
             detector_factory: Optional[Callable] = None, renderer: Callable = render_page) -> RunResult:
    """Processes a page in a new directory and records stages/results.

    Args:
        pdf_path: Readable PDF; SHA-256 is computed before rendering.
        page_number: Physical page starting at 1; the normal renderer requires a positive integer.
        output_dir: New directory; missing parents are created.
        dpi: Positive render resolution; default 200.
        config_path: YAML required when detector_factory is absent.
        checkpoint_path: Weights required when detector_factory is absent.
        model_config_dir: Config/manifest directory required by the real detector.
        device: cuda or cpu for the real detector; default cuda.
        detector_factory: Argument-free callable returning load, predict,
            load_report and metadata; reserved for explicit injection.
        renderer: Callable (pdf_path, page_number, dpi=...) returning RenderedPage.
    Returns:
        RunResult completed or failed; zero regions differs from a None count.
    Raises:
        FileExistsError: output_dir already exists.
        Exception: Preparation before try or diagnostic persistence may fail.
    Notes:
        Creates and writes files; the real detector may use GPU and modify sys.path.
        Catches Exception in inputs/render/load/predict/export inside try and writes
        error.log. Initial preparation and failures during except/finally have no
        persisted-state guarantee. Does not create sessions. Doc-Refs: INF-002, INF-006.
    """
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    pdf_path = Path(pdf_path).resolve()
    stage, count, error, detector = 'inputs', None, None, None
    timings = {}
    manifest = {'schema_version': 1, 'run_id': run_id,
                'started_utc': datetime.now(timezone.utc).isoformat(),
                'document': {'path': str(pdf_path), 'page': page_number},
                'requested': {'dpi': dpi, 'device': device},
                'environment': {'python': platform.python_version(), 'platform': platform.platform()},
                'code_sha256': {p.name: file_sha256(p) for p in sorted(Path(__file__).parent.glob('*.py'))}}
    for package in ('numpy', 'Pillow', 'pypdf', 'pypdfium2', 'torch', 'torchvision', 'detectron2', 'transformers'):
        try:
            manifest['environment'][package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            manifest['environment'][package] = None
    save_manifest(manifest, output_dir)
    try:
        manifest['document']['sha256'] = file_sha256(pdf_path)
        document_id = manifest['document']['sha256']
        stage = 'render'
        step = time.perf_counter()
        rendered = renderer(pdf_path, page_number, dpi=dpi)
        timings['render_seconds'] = time.perf_counter() - step
        manifest['render'] = render_geometry(rendered)
        Image.fromarray(rendered.image).save(output_dir / 'render.png', dpi=(dpi, dpi))
        manifest['render']['png_sha256'] = file_sha256(output_dir / 'render.png')
        save_manifest(manifest, output_dir)
        stage = 'load'
        step = time.perf_counter()
        if detector_factory is None:
            if config_path is None or checkpoint_path is None or model_config_dir is None:
                raise ValueError('config_path, checkpoint_path and model_config_dir are required')
            detector = LayoutLMv3Detector(config_path, checkpoint_path, model_config_dir, device)
        else:
            detector = detector_factory()
        report = detector.load()
        save_json(output_dir / 'load-report.json', asdict(report))
        if not report.is_exact_match:
            raise ValueError('Checkpoint incompatible; see load-report.json')
        timings['load_seconds'] = time.perf_counter() - step
        stage = 'predict'
        step = time.perf_counter()
        predictions = detector.predict(rendered.image)
        timings['predict_seconds'] = time.perf_counter() - step
        count = predictions.count
        manifest['detector'] = detector.metadata()
        stage = 'export'
        step = time.perf_counter()
        save_regions(predictions, rendered, output_dir, document_id=document_id, run_id=run_id)
        save_overlay(predictions, rendered, output_dir)
        timings['export_seconds'] = time.perf_counter() - step
    except Exception as exception:
        if stage in ('render', 'load', 'predict', 'export'):
            timings[stage + '_seconds'] = time.perf_counter() - step
        error = '{}: {}'.format(type(exception).__name__, exception)
        (output_dir / 'error.log').write_text(traceback.format_exc(), encoding='utf-8')
    finally:
        if detector is not None and detector.load_report is not None:
            save_json(output_dir / 'load-report.json', asdict(detector.load_report))
        if detector is not None and hasattr(detector, 'metadata'):
            try:
                manifest['detector'] = detector.metadata()
            except Exception as metadata_error:
                # Diagnostic collection must not hide the original stage failure.
                manifest['detector_metadata_error'] = '{}: {}'.format(type(metadata_error).__name__, metadata_error)
        result = RunResult(run_id, 'failed' if error else 'completed', stage,
                           output_dir, count, time.perf_counter() - started, error)
        status = asdict(result)
        status['output_dir'] = str(output_dir)
        status['page'] = page_number
        status['timings'] = timings
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        manifest['status'] = result.status
        manifest['timings'] = timings
        save_manifest(manifest, output_dir)
        save_json(output_dir / 'page-status.json', status)
    return result


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    """Defines and parses the CLI interface without starting inference.

    Args:
        argv: Argument list; None uses sys.argv.
    Returns:
        argparse.Namespace with PDF, page, output, dpi, paths and device.
    Raises:
        SystemExit: Help (0) or invalid arguments (usually 2).
    Notes:
        Vendor/model defaults start from code/, not the working directory.
        argparse may write help or errors; it does not validate file existence.
    """
    code = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description='Infer one PDF page; never creates a Colab session.')
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--page', type=int, required=True, help='Physical page, starting at 1')
    parser.add_argument('--output', type=Path, required=True, help='New directory, must not exist')
    parser.add_argument('--dpi', type=int, default=200)
    parser.add_argument('--config', type=Path, default=code / 'vendor/unilm/layoutlmv3/examples/object_detection/cascade_layoutlmv3.yaml')
    parser.add_argument('--model-config-dir', type=Path, default=code / 'models/layoutlmv3-publaynet')
    parser.add_argument('--checkpoint', type=Path, default=code / 'models/layoutlmv3-publaynet/model_final.pth')
    parser.add_argument('--device', choices=('cuda', 'cpu'), default='cuda')
    return parser.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    """Runs the CLI and reports the result on stdout/stderr.

    Args:
        argv: Optional arguments passed to parse_args.
    Returns:
        0 for successful RunResult; 1 for failure or caught OSError/ValueError.
    Raises:
        SystemExit: Help or argparse error, before try.
        Exception: Other uncaught run_page errors propagate.
    Notes:
        Has the effects of run_page. Invocation as a module turns the return value
        into SystemExit. Does not modify configurations or create remote sessions.
    """
    args = parse_args(argv)
    try:
        result = run_page(args.pdf, args.page, args.output, dpi=args.dpi,
                          config_path=args.config, checkpoint_path=args.checkpoint,
                          model_config_dir=args.model_config_dir, device=args.device)
    except (OSError, ValueError) as exception:
        print('{}: {}'.format(type(exception).__name__, exception), file=sys.stderr)
        return 1
    print('{}: {} (stage={})'.format(result.status, result.output_dir, result.stage))
    if result.error:
        print(result.error, file=sys.stderr)
    return 0 if result.succeeded else 1


if __name__ == '__main__':
    raise SystemExit(main())
