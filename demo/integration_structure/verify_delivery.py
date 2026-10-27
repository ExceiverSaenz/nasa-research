"""Verify deliverables and provenance without running the 15-paper integration."""
import ast
import json
from pathlib import Path
import sys
import zipfile

DEMO = Path(__file__).resolve().parent
sys.path.insert(0, str(DEMO))
from integration_demo.common import digest, read_json, check_members, member_digest, write_json


def verify(demo=DEMO):
    demo = Path(demo).resolve()
    archive = demo / 'upload.zip'
    expected = (demo / 'upload.sha256').read_text(encoding='ascii').strip()
    if digest(archive) != expected:
        raise ValueError('Package SHA256 mismatch')
    with zipfile.ZipFile(archive) as z:
        names = check_members(z)
        manifest = json.loads(z.read('bundle-manifest.json'))
        if manifest != read_json(demo / 'bundle-manifest.json'):
            raise ValueError('Local/bundled manifest mismatch')
        if set(names) != set(manifest['files']) | {'bundle-manifest.json'}:
            raise ValueError('Unexpected package members')
        for name, meta in manifest['files'].items():
            if z.getinfo(name).file_size != meta['bytes'] or member_digest(z, name) != meta['sha256']:
                raise ValueError('Package member changed: ' + name)
        for rel, meta in read_json(demo / 'source-snapshot.json').items():
            if member_digest(z, 'code/' + rel) != meta['sha256'] or digest(demo / 'src' / rel) != meta['sha256']:
                raise ValueError('Frozen code snapshot changed')
        for file in sorted((demo / 'integration_demo').glob('*.py')):
            if member_digest(z, 'code/integration_demo/' + file.name) != digest(file):
                raise ValueError('Orchestrator differs from bundled source')
        spec = json.loads(z.read('package-spec.json'))
        if len([n for n in names if n.startswith('pdfs/') and n.endswith('.pdf')]) != 15:
            raise ValueError('Missing PDF inputs')
        if member_digest(z, 'inputs/native.zip') != spec['native_archive']['sha256']:
            raise ValueError('Native input archive differs')
    notebook = read_json(demo / 'integration_structure_pipeline.ipynb')
    if notebook['nbformat'] != 4 or notebook['metadata']['integration_demo']['target'] != 'A100':
        raise ValueError('Notebook format/target mismatch')
    if notebook['metadata']['integration_demo']['bundle_sha256'] != expected:
        raise ValueError('Notebook package pin mismatch')
    code_cells = []
    for i, cell in enumerate(notebook['cells']):
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])
            compile(source, f'notebook-cell-{i}', 'exec')
            if cell['outputs'] or cell['execution_count'] is not None:
                raise ValueError('Notebook has fabricated/stale execution outputs')
            code_cells.append(source)
    source = '\n'.join(code_cells)
    if f'EXPECTED_BUNDLE_SHA256 = {expected!r}' not in source:
        raise ValueError('Missing executable bundle pin')
    from integration_demo.runner import STAGES
    for stage in STAGES:
        if source.count(f'run_stage({stage!r})') != 1:
            raise ValueError('Missing or repeated notebook stage: ' + stage)
    files = list((demo / 'src').rglob('*.py')) + list((demo / 'integration_demo').glob('*.py'))
    files += [demo / name for name in ('build_package.py', 'make_notebook.py', 'verify_delivery.py')]
    for file in files:
        ast.parse(file.read_text(encoding='utf-8-sig'), filename=str(file))
    report = dict(delivery='integration-structure-demo/1', target='A100', package_sha256=expected,
                  package_bytes=archive.stat().st_size, members=len(names),
                  notebook_cells=len(notebook['cells']), code_cells=len(code_cells),
                  python_files_syntax_checked=len(files), all_member_hashes_verified=True,
                  scientific_snapshot_unchanged=True, tests='see audit/tests.txt',
                  real_A100_execution=False, canonical_collection_reexported=False,
                  semantic_validation='pending_after_full_mvp', browser_visual_QA=False)
    return report


if __name__ == '__main__':
    result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    path = DEMO / 'verification.json'
    if path.exists():
        if read_json(path) != result:
            raise ValueError('Previous verification differs; preserve it before changing artifacts')
    else:
        write_json(path, result)
