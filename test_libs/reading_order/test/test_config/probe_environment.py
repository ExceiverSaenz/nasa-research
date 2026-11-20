"""Explicit remote configuration probe. Imports are inert until main is called.

Run inside the isolated order-modern interpreter, never the Colab kernel Python.
No paper data is used for ordering; the only real PDF is read in memory from R2.
"""
import argparse
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from validation import CheckResult, ConfigReport, FunctionCheck, fingerprint, verify_pdf, validate_checkpoint_keys

REQUIRED = {'prepared_identity', 'environment', 'cuda', 'docling', 'doctr', 'xycut', 'xycut_plus_plus',
            'hantian', 'pp_doclayout_v2', 'r2_pdf'}
PACKAGES = ('torch', 'torchvision', 'transformers', 'docling-slim', 'docling-core',
            'python-doctr', 'numpy', 'scipy', 'opencv-python', 'pypdf', 'psutil',
            'huggingface-hub', 'safetensors', 'rtree', 'pytest')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def environment():
    if sys.version_info[:2] != (3, 11) or sys.prefix == sys.base_prefix:
        raise ValueError('Expected isolated Python 3.11')
    check = subprocess.run([sys.executable, '-m', 'pip', 'check'], capture_output=True, timeout=90)
    if check.returncode:
        raise ValueError('Dependency consistency check failed')
    for module in ('torchvision', 'cv2', 'scipy', 'rtree', 'pypdf', 'psutil', 'pytest'):
        importlib.import_module(module)
    versions = {name: importlib.metadata.version(name) for name in PACKAGES}
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'interpreter': sys.executable, 'versions': versions,
            'gpu_driver': subprocess.check_output(['nvidia-smi', '--query-gpu=driver_version',
                                                  '--format=csv,noheader'], text=True).strip()}


def cuda():
    import torch
    if not torch.cuda.is_available() or 'A100' not in torch.cuda.get_device_name(0):
        raise ValueError('A100 CUDA device required')
    x = torch.eye(16, device='cuda')
    if not torch.equal(x @ x, x):
        raise ValueError('CUDA operation failed')
    torch.cuda.synchronize()
    return {'device': torch.cuda.get_device_name(0), 'cuda_runtime': torch.version.cuda,
            'vram_bytes': torch.cuda.get_device_properties(0).total_memory,
            'capability': list(torch.cuda.get_device_capability(0))}


def docling():
    from docling.models.postprocessing.reading_order_rb import ReadingOrderPredictor, PageElement
    from docling_core.types.doc import BoundingBox, CoordOrigin, DocItemLabel, Size
    elements = [PageElement(cid=i, ref={'cref': '#/texts/' + str(i)}, l=10, t=y,
                            r=100, b=y + 10, coord_origin=CoordOrigin.TOPLEFT,
                            page_no=1, page_size=Size(width=600, height=800),
                            label=DocItemLabel.TEXT, text='synthetic') for i, y in [(0, 50), (1, 10)]]
    result = ReadingOrderPredictor().predict_reading_order(elements)
    if [e.cid for e in result] != [1, 0]:
        raise ValueError('Unexpected simple vertical order')
    return {'synthetic_ids': [e.cid for e in result], 'pdf_or_detector_called': False}


def doctr():
    import numpy as np
    from doctr.models.reading_order import ReadingOrderPredictor
    result = ReadingOrderPredictor(direction='ltr')(np.array([[.1, .5, .9, .6], [.1, .1, .9, .2]]))
    if list(result) != [1, 0]:
        raise ValueError('Unexpected simple vertical order')
    return {'synthetic_indices': list(map(int, result)), 'ocr_called': False}


def xycut(root):
    import numpy as np
    module = load_module('xycut_candidate', root / 'xycut.py')
    result = []
    module.recursive_xy_cut(np.array([[10, 50, 100, 60], [10, 10, 100, 20]], dtype=int),
                            np.array([0, 1]), result)
    if list(result) != [1, 0]:
        raise ValueError('Unexpected simple vertical order')
    return {'synthetic_indices': list(map(int, result)),
            'source_sha256': hashlib.sha256((root / 'xycut.py').read_bytes()).hexdigest()}


def xycut_plus_plus(root):
    result = subprocess.run([str(root / 'xy-smoke' / 'target' / 'release' / 'order-config-smoke')],
                            capture_output=True, text=True, timeout=30, check=True)
    indices = json.loads(result.stdout)
    if sorted(indices) != [0, 1] or len(indices) != 2:
        raise ValueError('XY-Cut++ did not preserve synthetic IDs')
    return {'synthetic_indices': indices, 'implementation': 'home-still/xycut-plus-plus',
            'license': 'GPL-3.0', 'paper_fidelity': 'unverified'}


def hantian(root, sources):
    import torch
    from transformers import LayoutLMv3ForTokenClassification
    helpers = load_module('hantian_helpers', root / 'hantian_helpers.py')
    path = root / 'models' / 'hantian'
    model, info = LayoutLMv3ForTokenClassification.from_pretrained(
        path, local_files_only=True, use_safetensors=True, output_loading_info=True)
    if any(info.get(key) for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')):
        raise ValueError('Checkpoint load was not exact')
    model = model.eval().to('cuda')
    inputs = helpers.prepare_inputs(helpers.boxes2inputs([[10, 50, 100, 60], [10, 10, 100, 20]]), model)
    with torch.inference_mode():
        logits = model(**inputs).logits.cpu().squeeze(0)
    ranks = helpers.parse_logits(logits, 2)
    if sorted(ranks) != [0, 1] or not torch.isfinite(logits).all():
        raise ValueError('Invalid rank output')
    return {'revision': sources['models']['hantian/layoutreader'], 'rank_count': len(ranks),
            'checkpoint_sha256': hashlib.sha256((path / 'model.safetensors').read_bytes()).hexdigest(),
            'scope': 'synthetic_two_boxes_only'}


def pp_doclayout(root, sources):
    import torch
    from safetensors.torch import load_file
    from transformers import AutoConfig, PPDocLayoutV2ReadingOrder, PPDocLayoutV2ForObjectDetection
    path = root / 'models' / 'pp_doclayout_v2'
    config = AutoConfig.from_pretrained(path, local_files_only=True)
    model = PPDocLayoutV2ReadingOrder(config.reading_order_config)
    state = load_file(str(path / 'model.safetensors'), device='cpu')
    expected = set(model.state_dict())
    suffix = 'relative_head.dense.weight'
    prefixes = [key[:-len(suffix)] for key in state if key.endswith(suffix)]
    if len(prefixes) != 1:
        raise ValueError('Cannot identify unique reading-order checkpoint prefix')
    prefix = prefixes[0]
    selected = {key[len(prefix):]: value for key, value in state.items() if key.startswith(prefix)}
    # The official full-model loader explicitly ignores these two keys. Its encoder
    # uses rel_bias_module instead. Do not extend this allowlist to active parameters.
    allowed = {'encoder.rel_pos_x_bias.weight', 'encoder.rel_pos_y_bias.weight'}
    official = PPDocLayoutV2ForObjectDetection._keys_to_ignore_on_load_missing
    if not all(any(name in key for name in official) for key in allowed):
        raise ValueError('Installed upstream loader no longer documents these missing keys')
    missing = validate_checkpoint_keys(expected, set(selected), allowed)
    loaded = model.load_state_dict(selected, strict=False)
    if set(loaded.missing_keys) != set(missing) or loaded.unexpected_keys:
        raise ValueError('Checkpoint loading differs from inspected key policy')
    model = model.eval().to('cuda')
    # Some published configs have empty label2id: derive the ID only from id2label.
    text_ids = [int(key) for key, value in config.id2label.items() if value == 'text']
    if not text_ids or not config.class_order:
        raise ValueError('Text class mapping is unavailable')
    label = config.class_order[text_ids[0]]
    with torch.inference_mode():
        result = model(boxes=torch.tensor([[[10, 50, 100, 60], [10, 10, 100, 20]]], device='cuda'),
                       labels=torch.tensor([[label, label]], device='cuda'),
                       mask=torch.ones((1, 2), dtype=torch.bool, device='cuda'))
    if tuple(result.shape) != (1, 2, 2) or not torch.isfinite(result).all():
        raise ValueError('Invalid pair-logit output')
    with torch.inference_mode():
        # Characterize the upstream unused-parameter assumption without editing
        # installed code or checkpoint files. Any output dependence fails the check.
        model.encoder.rel_pos_x_bias.weight.fill_(12345)
        model.encoder.rel_pos_y_bias.weight.fill_(-12345)
        repeated = model(boxes=torch.tensor([[[10, 50, 100, 60], [10, 10, 100, 20]]], device='cuda'),
                         labels=torch.tensor([[label, label]], device='cuda'),
                         mask=torch.ones((1, 2), dtype=torch.bool, device='cuda'))
    if not torch.equal(result, repeated):
        raise ValueError('Documented missing parameters affect the reading-order output')
    return {'revision': sources['models']['PaddlePaddle/PP-DocLayoutV2_safetensors'],
            'checkpoint_sha256': hashlib.sha256((path / 'model.safetensors').read_bytes()).hexdigest(),
            'weight_prefix': prefix, 'loaded_tensors': len(selected),
            'documented_unused_missing_keys': missing, 'unused_parameter_invariance': True,
            'output_shape': list(result.shape), 'detector_called': False,
            'decoder_and_mineru_class_mapping': 'NOT_RUN'}


def r2_pdf(request_path):
    import io
    import urllib.request
    from pypdf import PdfReader
    request = json.loads(request_path.read_text())
    rows = []
    for item in request['files']:
        with urllib.request.urlopen(item['url'], timeout=90) as response:
            content = response.read(128 * 1024 * 1024 + 1)
        if len(content) > 128 * 1024 * 1024:
            raise ValueError('PDF exceeds configuration-test limit')
        row = verify_pdf(content, item['sha256'])
        pdf = PdfReader(io.BytesIO(content))
        row.update(paper=item['name'], pages=len(pdf.pages),
                   first_page_points=[float(pdf.pages[0].mediabox.width), float(pdf.pages[0].mediabox.height)],
                   rotation=int(pdf.pages[0].rotation))
        rows.append(row)
    if not rows:
        raise ValueError('Expected explicit PDF selection')
    return {'files': rows, 'storage': 'R2', 'persistence': 'memory_only'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--r2-request', type=Path)
    args = parser.parse_args(argv)
    root = args.root
    sources = json.loads((root / 'sources.json').read_text())
    from environment_identity import verify
    identity = FunctionCheck('prepared_identity', lambda: verify(root)).run()
    if identity.status != 'PASS':
        report = ConfigReport(args.run_id, [identity] + [CheckResult(name, 'NOT_RUN',
            {'reason': 'prepared_environment_identity_not_verified'}) for name in sorted(REQUIRED - {'prepared_identity'})])
        value = report.to_dict()
        value.update(configuration_checks_passed=False, pipeline_ready=False,
                     probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        (root / 'config-report.json').write_text(json.dumps(value, indent=2))
        print('ORDER_CONFIG_COMPLETED:' + args.run_id, flush=True)
        return 1
    operations = [('environment', environment), ('cuda', cuda), ('docling', docling), ('doctr', doctr),
                  ('xycut', lambda: xycut(root)), ('xycut_plus_plus', lambda: xycut_plus_plus(root)),
                  ('hantian', lambda: hantian(root, sources)),
                  ('pp_doclayout_v2', lambda: pp_doclayout(root, sources))]
    if args.r2_request:
        operations.append(('r2_pdf', lambda: r2_pdf(args.r2_request)))
    results = [identity]
    for name, operation in operations:
        started = time.monotonic()
        result = FunctionCheck(name, operation).run()
        results.append(result)
        print(json.dumps({'check': name, 'status': result.status, 'details': result.details,
                          'elapsed_s': round(time.monotonic() - started, 3)}), flush=True)
        if 'torch' in sys.modules:
            import gc
            gc.collect()
            sys.modules['torch'].cuda.empty_cache()
    report = ConfigReport(args.run_id, results)
    if not args.r2_request:
        results.append(CheckResult('r2_pdf', 'NOT_RUN', {'reason': 'remote_pdf_access_not_authorized'}))
    value = report.to_dict()
    value['configuration_checks_passed'] = report.ready(REQUIRED)
    value['pipeline_ready'] = False  # No adapters, full length/label checks or MinerU remote access yet.
    value['probe_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    value['sources_sha256'] = hashlib.sha256((root / 'sources.json').read_bytes()).hexdigest()
    value['lock_sha256'] = hashlib.sha256((root / 'requirements.lock').read_bytes()).hexdigest()
    value['environment_fingerprint'] = fingerprint(
        {'environment': next(item.details for item in results if item.name == 'environment'),
         'identity': identity.details, 'lock': value['lock_sha256'], 'sources': value['sources_sha256']},
        value['probe_sha256'])
    value['pending'] = ['MinerU remote reference transport without persistent copies',
                        'full candidate length/category/decoder contracts', 'XY-Cut++ paper fidelity',
                        'pipeline implementation and semantic/visual validation']
    (root / 'config-report.json').write_text(json.dumps(value, indent=2))
    if args.r2_request:
        args.r2_request.unlink(missing_ok=True)
    print('ORDER_CONFIG_COMPLETED:' + args.run_id, flush=True)
    return 0 if value['configuration_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
