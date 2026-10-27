"""Build the portable demo from preserved inputs; never executes integration."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

DEMO = Path(__file__).resolve().parent
sys.path.insert(0, str(DEMO))
from integration_demo.common import digest, write_json, member_digest, check_members

NATIVE = 'code/results/sic-colab-web-a100/consolidated-native-v1/sic-15-papers-3-parsers-native-v1.zip'
NATIVE_SHA = '2c9227257d3c79d8aa9477e80786a3f0e393c18fd29b6ef913f7907d6f917894'


def build(repository, destination):
    repository, destination = Path(repository).resolve(), Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / 'upload.zip'
    if archive.exists() or archive.with_suffix('.sha256').exists():
        raise FileExistsError('Package already exists; preserve previous builds')
    native = repository / NATIVE
    if digest(native) != NATIVE_SHA or native.with_suffix('.sha256').read_text().strip() != NATIVE_SHA:
        raise ValueError('Original native archive SHA256 mismatch')
    with zipfile.ZipFile(native) as z:
        index = json.loads(z.read('index.json'))
    canonical = repository / 'analytics/results/sic_collection/parsing-operational-v1'
    summary = json.loads((canonical / 'summary.json').read_text(encoding='utf-8'))
    expected = {k: summary[k] for k in ('papers', 'pages', 'inventory_units', 'content_appearances',
                                      'deferred_children', 'abstained_pages')}
    expected['parser_records'] = 11467
    if expected != dict(papers=15, pages=397, inventory_units=5374, content_appearances=4512,
                        deferred_children=374, abstained_pages=17, parser_records=11467):
        raise ValueError('Inspected canonical scope changed')
    assets = {}
    def add(name, path, source=None):
        if name in assets:
            raise ValueError('Duplicate build member')
        assets[name] = (Path(path), source or str(Path(path).relative_to(repository)).replace('\\', '/'))
    for relative, meta in json.loads((DEMO / 'source-snapshot.json').read_text()).items():
        p = DEMO / 'src' / relative
        if digest(p) != meta['sha256'] or digest(repository / meta['original']) != meta['sha256']:
            raise ValueError('Scientific source changed since snapshot: ' + relative)
        add('code/' + relative, p, meta['original'])
    for p in sorted((DEMO / 'integration_demo').glob('*.py')):
        add('code/integration_demo/' + p.name, p)
    for p in sorted((DEMO / 'tests').glob('test_*.py')):
        add('tests/' + p.name, p)
    for entry in index:
        document = repository / entry['document']
        if digest(document) != entry['document_sha256']:
            raise ValueError('Original PDF differs from native archive')
        add('pdfs/' + document.name, document)
    add('inputs/native.zip', native)
    add('inputs/native.sha256', native.with_suffix('.sha256'))
    for name in ('requirements-runtime.lock', 'requirements-docling.txt', 'README.md', 'PLAN.md', 'source-snapshot.json'):
        add(name, DEMO / name)
    add('documentation/architecture.md', repository / 'docs/arquitectura/02-arquitectura-del-parsing.md')
    add('documentation/output-contract.md', repository / 'docs/arquitectura/parsing-operativo-contrato.md')
    spec = dict(schema='integration-demo-spec/1', target='Linux x86_64 / A100',
                actual_compute='CPU', expected=expected,
                native_archive=dict(path='inputs/native.zip', sha256=NATIVE_SHA),
                baseline=dict(path='analytics/results/sic_collection/parsing-operational-v1/manifest.json',
                              sha256=digest(canonical / 'manifest.json')),
                cache_policy='recompute_all_no_historical_caches',
                semantic_validation='pending_after_full_mvp', automatic_retries=False,
                input_papers=[dict(document=e['document'], sha256=e['document_sha256'], pages=e['pages']) for e in index])
    # Generated metadata lives beside the package for inspection as well as inside it.
    write_json(destination / 'package-spec.json', spec)
    add('package-spec.json', destination / 'package-spec.json', 'generated from frozen inputs')
    manifest = dict(schema='integration-demo-bundle/1', excludes_self=True,
                    files={name: dict(bytes=p.stat().st_size, sha256=digest(p), source=source)
                           for name, (p, source) in sorted(assets.items())})
    partial = archive.with_name(archive.name + '.partial')
    with zipfile.ZipFile(partial, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for name, (path, _) in sorted(assets.items()):
            print('Package:', name, flush=True)
            z.write(path, name)
        z.writestr('bundle-manifest.json', json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    partial.rename(archive)
    with archive.with_suffix('.sha256').open('x', encoding='ascii') as f:
        f.write(digest(archive) + '\n')
    with zipfile.ZipFile(archive) as z:
        check_members(z)
        for name, meta in manifest['files'].items():
            if member_digest(z, name) != meta['sha256']:
                raise ValueError('Built package integrity mismatch: ' + name)
    write_json(destination / 'bundle-manifest.json', manifest)
    result = dict(package_sha256=digest(archive), bytes=archive.stat().st_size,
                  members=len(manifest['files']) + 1, all_member_hashes_verified=True,
                  scientific_files_copied_unchanged=len(json.loads((DEMO / 'source-snapshot.json').read_text())),
                  native_archive_preserved=True, native_archive_sha256=NATIVE_SHA,
                  baseline_manifest_sha256=spec['baseline']['sha256'],
                  models_executed=False, canonical_collection_reexported=False, A100_executed=False)
    write_json(destination / 'package-verification.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository', type=Path, default=DEMO.parents[1])
    p.add_argument('--destination', type=Path, default=DEMO)
    a = p.parse_args()
    print(json.dumps(build(a.repository, a.destination), indent=2))
