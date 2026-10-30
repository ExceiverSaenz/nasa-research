"""Build a static stage viewer from saved artifacts; no scientific execution."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_RUN = '20261030T040105Z-4215756a'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(root):
    entries = read(root / 'manifest.json')['outputs']
    for name, expected in entries.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or digest(path) != expected:
            raise ValueError(f'Source manifest mismatch: {name}')
    return entries


def make_data(parse_run, integration_run):
    if parse_run.name != integration_run.name:
        raise ValueError('Both stages must belong to the same attempt')
    if read(parse_run / 'status.json')['status'] != 'completed':
        raise ValueError('Parser run is incomplete')
    summary = read(integration_run / 'summary.json')
    if summary['status'] != 'completed' or summary['failed']:
        raise ValueError('Integration run is incomplete')
    inputs = read(parse_run / 'inputs.json')
    if len(inputs) != 1 or len(summary['documents']) != 1:
        raise ValueError('This viewer expects exactly one paper')
    paper = inputs[0]
    base = integration_run / summary['documents'][0]['directory']
    reconciliation = read(base / 'reconciliation/papers/1/document.json')
    classified = read(base / 'classification/papers/1/document.json')
    if reconciliation['document_sha256'] != paper['sha256'] or classified['paper_id'] != paper['sha256']:
        raise ValueError('Document identity differs between stages')
    pages, records, links, correspondences = [], [], [], []
    for p in reconciliation['pages']:
        identity = p['identity']
        n = identity['physical_page']
        saved = read(parse_run / 'renders' / paper['id'] / str(n) / 'identity.json')
        if identity != saved:
            raise ValueError(f'Page identity mismatch: {n}')
        pages.append(dict(n=n, w=identity['width_px'], h=identity['height_px'],
                          image=f'images/{n:04d}.png', render_sha256=identity['render_sha256'],
                          status=p['status'], incidents=p['incidents'], capabilities=p['capabilities']))
        for r in p['records']:
            record = dict(id=r['id'], page=n, bbox=r.get('bbox'), parser=r['parser'],
                          category=r.get('category'), subtype=r.get('subtype', r.get('native_type')),
                          native_type=r.get('native_type'), native_label=r.get('native', {}).get('native_label', r.get('native_type')),
                          kind=r.get('role', 'segment'), text=r.get('text', ''),
                          source=r.get('source'), parent=r.get('parent'),
                          geometry_status=r.get('geometry_status'), native_bbox=r.get('native_bbox'),
                          transform=r.get('transform'))
            if 'score' in r:
                record['score'] = r['score']
            records.append(record)
        for g in p['groups']:
            if g.get('caption'):
                links.extend(dict(page=n, member=m, caption=g['caption'], status=g['status'], group=g['id'])
                             for m in g['members'])
        correspondences.extend(dict(c, page=n) for c in p['correspondences'])
    regions = []
    for r in classified['regions'] + classified['logical_units']:
        original = r.get('original_record', {})
        region = dict(id=r['id'], page=r['page'], bbox=r.get('bbox_xyxy'),
                      kind=r['structural_kind'], classification=r['classification'],
                      text=original.get('text', ''), source=original.get('source'),
                      native_type=original.get('native_type'), member_of=r.get('member_of', []))
        if r['structural_kind'] == 'group':
            region.update(members=r['members'], caption_ref=r.get('caption_ref'),
                          source=r.get('original_group'), geometry_refs=r.get('geometry_refs', []))
        regions.append(region)
    orders = {}
    source_files = {'baseline': 'capsules/papers/1/document.json',
                    'docling': 'operational/papers/1/baseline-docling.json',
                    'operational': 'operational/papers/1/document.json'}
    for key, path in source_files.items():
        source = read(base / path)
        orders[key] = dict(steps=source['steps'], routes=source['routes'],
                           relations=[r for r in source['relations'] if r['type'] == 'next_in_route'])
    return dict(id='12', run=parse_run.name, sha256=paper['sha256'], pages=pages,
                records=records, regions=regions, links=links, orders=orders,
                correspondences=correspondences,
                sources=dict(parser=str(parse_run), integration=str(integration_run),
                             classification=str(base / 'classification/papers/1/document.json'),
                             orders={k: str(base / v) for k, v in source_files.items()}))


def build(parse_run, integration_run, image_source, output=HERE):
    source_hashes = {str(root): verify_manifest(root) for root in (parse_run, integration_run)}
    manifests = {str(root): digest(root / 'manifest.json') for root in (parse_run, integration_run)}
    data = make_data(parse_run, integration_run)
    for p in data['pages']:
        if digest(image_source / f"{p['n']:04d}.png") != p['render_sha256']:
            raise ValueError(f"Image is not the recorded model input: page {p['n']}")
    (output / 'data').mkdir(parents=True, exist_ok=True)
    (output / 'images').mkdir(parents=True, exist_ok=True)
    for p in data['pages']:
        src, dst = image_source / f"{p['n']:04d}.png", output / p['image']
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
    serialized = json.dumps(data, ensure_ascii=True, separators=(',', ':')).replace('<', '\\u003c')
    (output / 'data/12.js').write_text('window.receivePaper(' + serialized + ');\n', encoding='utf-8')
    template = (HERE / 'viewer.html').read_text(encoding='utf-8')
    for mode in ('comparison', 'classification', 'order', 'operational'):
        (output / f'{mode}.html').write_text(template.replace('__MODE__', mode), encoding='utf-8')
    (output / 'index.html').write_text(template.replace('__MODE__', 'comparison'), encoding='utf-8')
    for root in (parse_run, integration_run):
        if verify_manifest(root) != source_hashes[str(root)] or digest(root / 'manifest.json') != manifests[str(root)]:
            raise ValueError('Source results changed during the build')
    report = dict(run=parse_run.name, pages=len(data['pages']), parser_records=len(data['records']),
                  reconciled_units=len(data['regions']), exact_render_hashes=len(data['pages']),
                  source_manifests_verified=True, source_unchanged=True,
                  source_manifest_sha256=manifests, scientific_stages_executed=False,
                  semantic_validation='pending_after_full_mvp', visual_QA=False,
                  files={str(p.relative_to(output)).replace('\\', '/'): digest(p)
                         for p in sorted(output.rglob('*')) if p.is_file() and p.suffix in ('.html', '.css', '.js', '.png')})
    (output / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'files'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', default=DEFAULT_RUN)
    parser.add_argument('--image-source', type=Path, default=HERE / 'images')
    args = parser.parse_args()
    build(ROOT / 'results/parse_results' / args.run,
          ROOT / 'results/reconciliation_results' / args.run, args.image_source.resolve())
