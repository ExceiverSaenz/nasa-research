#!/usr/bin/env python3
"""Download exact parser weights with original hashes; never install or infer.

Run on the Colab host. --cache-dir may point to mounted persistent storage.
The default cache in /content is ephemeral. Re-run to resume partial downloads.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import threading
import time
from urllib.parse import quote
from urllib.request import Request, urlopen
import uuid

ROOT = Path(__file__).resolve().parent
NAMES = ('layoutlmv3', 'table_transformer', 'mineru')
MINERU_MARKERS = ('Layout/PP-DocLayoutV2/.mineru_complete', 'OCR/paddleocr/.mineru_complete')


@contextmanager
def heartbeat(label, interval=10):
    stop = threading.Event()
    start = time.monotonic()
    def report():
        while not stop.wait(interval):
            print(f'[Working: {label}; elapsed {int(time.monotonic()-start)}s]', flush=True)
    worker = threading.Thread(target=report, daemon=True)
    worker.start()
    try:
        yield
    finally:
        stop.set()
        worker.join()


def validate_manifest(value):
    repository = value.get('model_id', value.get('repository', ''))
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repository):
        raise ValueError('Invalid repository identity')
    if not re.fullmatch('[0-9a-f]{40}', value.get('revision', '')):
        raise ValueError('Immutable full revision required')
    if not isinstance(value.get('files'), dict) or not value['files']:
        raise ValueError('Empty model receipt')
    for name, record in value['files'].items():
        path = PurePosixPath(name)
        if (path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name
                or str(path) != name or not path.parts):
            raise ValueError('Unsafe receipt path: '+name)
        if type(record.get('bytes')) is not int or record['bytes'] < 0:
            raise ValueError('Invalid byte count: '+name)
        if not re.fullmatch('[0-9a-f]{64}', record.get('sha256', '')):
            raise ValueError('Invalid SHA256: '+name)
    return repository


def verify(path, record):
    if path.stat().st_size != record['bytes']:
        raise ValueError('Size mismatch: '+str(path))
    print('Verifying SHA256: '+str(path), flush=True)
    digest = hashlib.sha256()
    with heartbeat('SHA256 '+path.name), path.open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b''):
            digest.update(block)
    if digest.hexdigest() != record['sha256']:
        raise ValueError('SHA256 mismatch: '+str(path))


def fetch_file(url, target, record, *, opener=urlopen):
    """One attempt; preserve interrupted bytes. Caller serializes cache access."""
    target = Path(target)
    if target.exists():
        verify(target, record)
        print('Verified cache: '+str(target), flush=True)
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name+'.part')
    if partial.is_symlink():
        raise ValueError('Refusing partial symlink: '+str(partial))
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > record['bytes']:
        raise ValueError('Oversized partial file; inspect before retrying: '+str(partial))
    if offset != record['bytes'] or not partial.exists():
        headers = {'User-Agent': 'new-code-model-setup/1', 'Accept-Encoding': 'identity'}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        print(f'Downloading {target.name}: {offset}/{record["bytes"]} bytes', flush=True)
        with heartbeat('download '+target.name):
            with opener(Request(url, headers=headers), timeout=60) as response:
                if response.status == 206:
                    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                    if (not match or int(match[1]) != offset or int(match[3]) != record['bytes']
                            or int(match[2]) != record['bytes']-1):
                        raise ValueError('Unexpected Content-Range; partial preserved')
                    mode = 'ab'
                elif response.status == 200:
                    offset, mode = 0, 'wb'
                else:
                    raise ValueError('Unexpected HTTP status: '+str(response.status))
                last = time.monotonic()
                flags = os.O_WRONLY | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
                flags |= os.O_APPEND if mode == 'ab' else os.O_TRUNC
                with os.fdopen(os.open(partial, flags, 0o600), mode) as output:
                    while True:
                        block = response.read(1024*1024)
                        if not block:
                            break
                        if offset+len(block) > record['bytes']:
                            raise ValueError('Server sent more bytes than receipt permits')
                        output.write(block)
                        offset += len(block)
                        if time.monotonic()-last >= 2:
                            print(f'  {offset/1048576:.1f}/{record["bytes"]/1048576:.1f} MiB '
                                  f'({100*offset/max(record["bytes"],1):.1f}%)', flush=True)
                            last = time.monotonic()
    # A short transfer remains resumable. A full corrupt transfer is preserved
    # separately, allowing the next explicit invocation to download afresh.
    try:
        verify(partial, record)
    except ValueError:
        if partial.stat().st_size == record['bytes']:
            invalid = partial.with_name(partial.name+'.invalid-'+uuid.uuid4().hex[:8])
            partial.rename(invalid)
            print('Corrupt download preserved: '+str(invalid), flush=True)
        raise
    if target.exists():
        raise FileExistsError('Target appeared during download: '+str(target))
    partial.replace(target)
    print('Downloaded and verified: '+str(target), flush=True)
    return target


def save_exact(path, content):
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError('Existing metadata differs: '+str(path))
    else:
        with path.open('xb') as stream:
            stream.write(content)


def write_configuration(output, paths, manifest, root=ROOT):
    output.mkdir(parents=True, exist_ok=False)
    yaml = output/'hybrid-mineru.yaml'
    yaml.write_text('model:\n  source: local\n  small_backend: torch\n  base_dir: '
                    +json.dumps(str(paths['mineru'].parent))+'\nllm_aided:\n  features:\n'
                    '    title_leveling: false\n    cross_page_table_cell_merge: false\n', encoding='utf-8')
    runtime = {'schema': 'parsing-hybrid-runtime/1', 'package_root': str(root/'parse_system'),
               'env_manifest': str(manifest), 'vendor_dir': str(root/'parse_system/vendor/unilm'),
               'model_dirs': {name: str(path) for name, path in paths.items()},
               'mineru_receipt': str(paths['mineru']/'model-download-receipt.json'),
               'mineru_config': str(yaml)}
    target = output/'hybrid-runtime.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(runtime, stream, indent=2)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true', help='No writes, network or imports of model packages')
    parser.add_argument('--cache-dir', type=Path, default=ROOT/'runtime/model-cache')
    parser.add_argument('--env-manifest', type=Path, default=ROOT/'runtime/environment/environment.json')
    parser.add_argument('--output-dir', type=Path, help='New directory for this VM configuration')
    args = parser.parse_args(argv)
    cache = (ROOT/args.cache_dir).resolve()
    manifest = (ROOT/args.env_manifest).resolve()
    output = (ROOT/args.output_dir).resolve() if args.output_dir else ROOT/'runtime'/('model-config-'+uuid.uuid4().hex[:12])
    receipts = {}
    paths = {}
    models = []
    for name in NAMES:
        raw = (ROOT/'model_manifests'/f'{name}.json').read_bytes()
        value = json.loads(raw)
        repository = validate_manifest(value)
        receipts[name] = (raw, value, repository)
        parent = cache/name/value['revision']
        paths[name] = parent/('MinerU-4_models_torch' if name == 'mineru' else 'model')
        models.append({'name': name, 'repository': repository, 'revision': value['revision'],
                       'bytes': sum(item['bytes'] for item in value['files'].values()), 'path': str(paths[name])})
    if args.plan:
        print(json.dumps({'cache': str(cache), 'output': str(output), 'models': models,
                          'persistence': 'Depends on backing storage; /content is ephemeral'}, indent=2))
        return 0
    if sys.platform != 'linux':
        raise RuntimeError('Run download preparation inside the Linux Colab VM')
    if output.exists():
        raise FileExistsError('Configuration destination exists; choose a new --output-dir')
    if not manifest.is_file() or json.loads(manifest.read_text()).get('status') != 'imports-validated':
        raise ValueError('Provide the existing imports-validated environment.json')
    if not (ROOT/'parse_system/vendor/unilm').is_dir():
        raise ValueError('Missing parser vendor tree; upload the code package first')
    if not cache.parent.is_dir():
        raise ValueError('Cache parent missing: mount persistent storage first or create its parent')
    cache.mkdir(exist_ok=True)
    import fcntl
    with (cache/'.setup-models.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print('Cache: '+str(cache)+' (persistence depends on its backing storage)', flush=True)
        for name in NAMES:
            raw, value, repository = receipts[name]
            print('\n=== '+name+' @ '+value['revision']+' ===', flush=True)
            for relative, record in value['files'].items():
                target = paths[name]/relative
                if not target.resolve().is_relative_to(paths[name].resolve()):
                    raise ValueError('Model file escapes cache directory')
                url = 'https://huggingface.co/'+repository+'/resolve/'+value['revision']+'/'+quote(relative, safe='/')
                fetch_file(url, target, record)
            receipt_name = 'model-download-receipt.json' if name == 'mineru' else 'download-manifest.json'
            save_exact(paths[name]/receipt_name, raw)
            if name == 'mineru':
                # All 12 original receipt files are verified before marking this
                # new download complete. Inference never creates/repairs markers.
                for relative in MINERU_MARKERS:
                    save_exact(paths[name]/relative, b'')
        target = write_configuration(output, paths, manifest, ROOT)
    print('\nModels downloaded and SHA256-verified. No model loading/inference performed.', flush=True)
    print('Runtime configuration: '+str(target), flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('MODEL SETUP FAILED: '+str(exc), file=sys.stderr, flush=True)
        raise SystemExit(1)
