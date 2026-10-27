"""Coordinación de una página y CLI; sin creación explícita de sesiones remotas.

Integra render, detector y outputs. README.md explica ejecución y evidencia histórica.
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
    """Procesa una página en un directorio nuevo y registra etapas/resultados.

    Args:
        pdf_path: PDF legible; se calcula SHA-256 antes del render.
        page_number: Página física desde 1; el renderer normal exige entero positivo.
        output_dir: Directorio nuevo; se crean padres si faltan.
        dpi: Resolución positiva del render; default 200.
        config_path: YAML requerido cuando no hay detector_factory.
        checkpoint_path: Pesos requeridos cuando no hay detector_factory.
        model_config_dir: Directorio de config/manifest requerido por el detector real.
        device: cuda o cpu para el detector real; default cuda.
        detector_factory: Callable sin argumentos que devuelve load, predict,
            load_report y metadata; reservado para inyección explícita.
        renderer: Callable (pdf_path, page_number, dpi=...) que devuelve RenderedPage.
    Returns:
        RunResult completed o failed; cero regiones difiere de conteo None.
    Raises:
        FileExistsError: output_dir ya existe.
        Exception: Preparación anterior al try o persistencia de diagnósticos puede fallar.
    Notes:
        Crea y escribe archivos; el detector real puede usar GPU y modificar sys.path.
        Captura Exception en inputs/render/load/predict/export dentro del try y escribe
        error.log. La preparación inicial y los fallos durante except/finally no tienen
        garantía de estado persistido. No crea sesiones. Doc-Refs: INF-002, INF-006.
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
    """Define y procesa la interfaz CLI sin iniciar inferencia.

    Args:
        argv: Lista de argumentos; None utiliza sys.argv.
    Returns:
        argparse.Namespace con PDF, página, salida, dpi, rutas y device.
    Raises:
        SystemExit: Help (0) o argumentos inválidos (normalmente 2).
    Notes:
        Los defaults de vendor/modelos parten de code/, no del working directory.
        argparse puede escribir ayuda o errores; no valida existencia de archivos.
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
    """Ejecuta el CLI y comunica el resultado en stdout/stderr.

    Args:
        argv: Argumentos opcionales entregados a parse_args.
    Returns:
        0 ante RunResult exitoso; 1 ante fallo o OSError/ValueError capturados.
    Raises:
        SystemExit: Help o error de argparse, antes del try.
        Exception: Otros errores no capturados de run_page se propagan.
    Notes:
        Tiene los efectos de run_page. La invocación como módulo transforma el retorno
        en SystemExit. No modifica configuraciones ni crea sesiones remotas.
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
