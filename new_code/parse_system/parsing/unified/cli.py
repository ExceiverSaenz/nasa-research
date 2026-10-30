"""Explicit local hybrid execution; help and configuration creation are inert."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import uuid
from .storage import resolve_output, results_root


def runtime_template():
    root = Path(__file__).resolve().parents[2]
    return {'schema': 'parsing-hybrid-runtime/1', 'package_root': str(root),
            'env_manifest': '/ABSOLUTE/PATH/TO/environment.json',
            'vendor_dir': str(root / 'vendor/unilm'),
            'model_dirs': {
                'layoutlmv3': '/ABSOLUTE/PATH/TO/layoutlmv3/model',
                'table_transformer': '/ABSOLUTE/PATH/TO/table_transformer',
                'mineru': '/ABSOLUTE/PATH/TO/MinerU-4_models_torch'},
            'mineru_receipt': '/ABSOLUTE/PATH/TO/model-download-receipt.json',
            'mineru_config': '/ABSOLUTE/PATH/TO/hybrid-mineru.yaml'}


def read_runtime(path):
    path = Path(path).resolve(strict=True)
    runtime = json.loads(path.read_text(encoding='utf-8-sig'))
    if runtime.get('schema') != 'parsing-hybrid-runtime/1':
        raise ValueError('Unsupported runtime configuration schema')
    models = runtime.get('model_dirs', {})
    if set(models) != {'layoutlmv3', 'table_transformer', 'mineru'}:
        raise ValueError('Exactly the three model directories are required')
    for key in ('vendor_dir', 'env_manifest', 'mineru_receipt', 'mineru_config'):
        if not isinstance(runtime.get(key), str) or not runtime[key]:
            raise ValueError('Missing runtime path: ' + key)
        runtime[key] = str((path.parent / runtime[key]).resolve(strict=True))
    if not Path(runtime['vendor_dir']).is_dir():
        raise ValueError('Vendor path must be a directory')
    for key in ('env_manifest', 'mineru_receipt', 'mineru_config'):
        if not Path(runtime[key]).is_file():
            raise ValueError('Runtime manifest/receipt must be files')
    for name, value in models.items():
        target = (path.parent / value).resolve(strict=True)
        if not target.is_dir():
            raise ValueError('Model path must be a directory: ' + name)
        models[name] = str(target)
    return runtime


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    template = actions.add_parser('template', help='Write a runtime configuration template; no model calls')
    template.add_argument('--output', required=True, type=Path)
    check = actions.add_parser('check', help='Verify the current common environment and CUDA')
    check.add_argument('--runtime', required=True, type=Path)
    run = actions.add_parser('run', help='Stream n PDFs through three persistent concurrent engines')
    run.add_argument('--runtime', required=True, type=Path)
    run.add_argument('--paper', type=Path, action='append', default=[])
    run.add_argument('--input-dir', type=Path)
    run.add_argument('--output', type=Path,
                     help='Optional run name/absolute child;default unique run inside ' + str(results_root()))
    run.add_argument('--max-inflight', type=int, default=2)
    run.add_argument('--load-timeout', type=float, default=300)
    run.add_argument('--task-timeout', type=float, default=600)
    run.add_argument('--user-run', action='store_true')
    env = actions.add_parser('environment', help='Prepare/check a new common virtual environment explicitly')
    env.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.action == 'template':
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(runtime_template(), stream, indent=2)
        print(str(args.output.resolve()))
        return 0
    if args.action == 'environment':
        from .environment import main as environment_main
        return environment_main(args.arguments)
    if args.action == 'run':
        if not args.user_run:
            parser.error('Explicit --user-run is required; no inference started')
        if sys.platform != 'linux':
            parser.error('Local hybrid inference requires Linux/WSL Python')
        if (args.max_inflight < 1 or not math.isfinite(args.load_timeout)
                or not math.isfinite(args.task_timeout)
                or args.load_timeout <= 0 or args.task_timeout <= 0):
            parser.error('Queue bound and timeouts must be positive')
        try:
            args.output = resolve_output(args.output)
        except ValueError as exc:
            parser.error(str(exc))
        if args.output.exists():
            raise FileExistsError('Attempt directory must be new')
    runtime = read_runtime(args.runtime)
    if args.action == 'check':
        from .environment import check_runtime
        environment = check_runtime(Path(runtime['env_manifest']), require_cuda=True)
        print(json.dumps(environment, indent=2))
        return 0
    # Import/ABI checks run in a temporary process using this same interpreter.
    # The coordinator never creates a CUDA context before spawning its workers.
    child_env = dict(os.environ)
    child_env['PYTHONPATH'] = str(Path(__file__).resolve().parents[2])
    child_env['PYTHONNOUSERSITE'] = '1'
    subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('environment.py')),
                    'check', '--manifest', runtime['env_manifest'], '--no-cuda'],
                   env=child_env, check=True, capture_output=True, text=True)
    from .inputs import collect_papers, render_page_job
    from .adapters import load_engine
    from .scheduler import run_pipeline
    papers = collect_papers(args.paper, args.input_dir)
    runtime['execution_id'] = 'hybrid-' + uuid.uuid4().hex
    for paper in papers:
        paper['execution_id'] = runtime['execution_id']
    result = run_pipeline(papers, args.output, runtime, renderer=render_page_job,
                          engine_factory=load_engine, max_inflight=args.max_inflight,
                          load_timeout=args.load_timeout, task_timeout=args.task_timeout)
    print(json.dumps({key: result[key] for key in
                      ('status', 'error', 'metrics', 'archive', 'archive_sha256')
                      if key in result}, indent=2))
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
