"""Read-only checks for the integration part of the shared parsing environment.

No installation, model construction, CUDA call or inference occurs here. The
requirements file is a candidate input to the common resolver, never a lock.
Historical A100 controllers retain their original separate runtime contract.
"""
import hashlib
import importlib
from importlib import metadata
from importlib.metadata import PackageNotFoundError, version
import inspect
import json
from pathlib import Path
import platform
import sys


SHARED_PYTHON = '3.11.16'
DOCLING_RB_SHA256 = '688402b548726963fa65c8af3647626ddfb70e42ece07c05893574c15bb05964'
PINS = {'PyMuPDF': '1.27.2.3', 'docling': '2.123.1',
        'docling-slim': '2.123.1', 'docling-core': '2.92.0', 'rtree': '1.4.1'}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def validate_shared_receipt(manifest=None, *, require_parser=True):
    """Check the parser installer's receipt without importing any model package.

    Inspecting distributions and recorded package files establishes this is the
    same installed environment; the parser retains its separate CUDA/load gates.
    """
    receipt = Path(manifest if manifest is not None else Path(sys.prefix).parent / 'environment.json').resolve(strict=True)
    raw = receipt.read_bytes()
    value = json.loads(raw)
    prefix = Path(sys.prefix).resolve()
    executable = str(Path(sys.executable).absolute())
    if value.get('status') != 'imports-validated':
        raise ValueError('Shared environment receipt is not imports-validated')
    if value.get('prefix') != str(prefix) or value.get('executable') != executable:
        raise ValueError('Shared environment receipt prefix/executable differs from current interpreter')
    if value.get('python') != SHARED_PYTHON or platform.python_version() != SHARED_PYTHON:
        raise ValueError('Shared environment receipt requires Python ' + SHARED_PYTHON)
    observed = {distribution.metadata['Name'].lower().replace('_', '-'): distribution.version
                for distribution in metadata.distributions()}
    if not value.get('versions') or value['versions'] != observed:
        raise ValueError('Shared environment package fingerprint changed')
    imports = value.get('imports')
    required = ({'torch', 'torchvision', 'transformers', 'mineru', 'detectron2', 'detectron2._C'}
                if require_parser else {'fitz','docling.models.postprocessing.reading_order_rb'})
    if not require_parser and value.get('schema')!='integration-environment/1':
        raise ValueError('Integrator environment receipt schema required')
    if not isinstance(imports, dict) or not required.issubset(imports):
        raise ValueError('Shared environment receipt lacks parser imports')
    for name, recorded in imports.items():
        path = Path(recorded['path']).resolve(strict=True)
        if not path.is_relative_to(prefix) or not path.is_file() or digest(path) != recorded['sha256']:
            raise ValueError('Shared environment package import changed or outside prefix: ' + name)
    artifacts = value.get('artifacts')
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError('Shared environment receipt lacks install artifacts')
    for name, recorded in artifacts.items():
        path = (receipt.parent / name).resolve(strict=True)
        if (not path.is_relative_to(receipt.parent) or not path.is_file()
                or path.stat().st_size != recorded['bytes'] or digest(path) != recorded['sha256']):
            raise ValueError('Shared environment install artifact changed or outside receipt: ' + name)
    if receipt.read_bytes() != raw:
        raise ValueError('Shared environment receipt changed during verification')
    return {'manifest_path': str(receipt), 'manifest_sha256': hashlib.sha256(raw).hexdigest()}


def preflight(require_shared_environment=True, *, manifest=None, profile='shared'):
    """Verify installed integration dependencies in the current interpreter.

    This is only the integration gate. The parser's own environment fingerprint,
    strict checkpoints and CUDA gates still apply when running the three engines.
    ``require_shared_environment=False`` is intended for diagnostic inspection;
    production execution must use the default shared profile.
    """
    if profile not in ('shared','integrator'):raise ValueError('Unknown integration runtime profile')
    observed_python = platform.python_version()
    if require_shared_environment:
        if observed_python != SHARED_PYTHON:
            raise ValueError('Shared environment requires Python ' + SHARED_PYTHON)
        if sys.prefix == sys.base_prefix:
            raise ValueError('Dedicated shared virtual environment required')
    packages = {}
    for name, expected in PINS.items():
        try:
            observed = version(name)
        except PackageNotFoundError as error:
            raise ValueError('Missing integration dependency ' + name +
                             '; resolve reconciliation_system/requirements.in together '
                             'with the parser before creating its environment receipt') from error
        if observed != expected:
            raise ValueError('Wrong package version for ' + name + ': expected ' +
                             expected + ', observed ' + observed)
        packages[name] = observed
    imports = {}
    for name in ('fitz', 'docling.models.postprocessing.reading_order_rb'):
        module = importlib.import_module(name)
        path = Path(inspect.getfile(module)).resolve(strict=True)
        if require_shared_environment and not path.is_relative_to(Path(sys.prefix).resolve()):
            raise ValueError('Integration module outside shared environment: ' + str(path))
        imports[name] = {'path': str(path), 'sha256': digest(path)}
        if name == 'fitz' and module.VersionBind != PINS['PyMuPDF']:
            raise ValueError('PyMuPDF binding version differs from distribution metadata')
    observed_hash = imports['docling.models.postprocessing.reading_order_rb']['sha256']
    if observed_hash != DOCLING_RB_SHA256:
        raise ValueError('Docling rule-based source hash mismatch; no predictor fallback')
    receipt = ((validate_shared_receipt(manifest,require_parser=False) if profile=='integrator' else validate_shared_receipt(manifest))
               if require_shared_environment else {})
    return dict({'profile': profile if require_shared_environment else 'diagnostic',
            'python': observed_python, 'prefix': str(Path(sys.prefix).resolve()),
            'executable': str(Path(sys.executable).absolute()), 'packages': packages,
            'imports': imports, 'docling_rb_sha256': observed_hash,
            'models_executed': False, 'OCR_executed': False}, **receipt)
