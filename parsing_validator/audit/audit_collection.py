"""Read-only coverage audit of the tensile_papers collection (no writes under the repository)."""
import hashlib, json, os, sys, time, traceback
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/code'))
from mineru_contracts import ObjectPointer, ReferenceResolver
from mineru_spatial import SpatialGraph
from mineru_observed_geometry import _EvidenceCache
from mineru_geometry_capture import read_geometry_links
from mineru_collection import CollectionRepository
import pypdfium2 as pdfium

COLL = ROOT / 'src/raw_results/code_results/tensile_papers'
PDFS = ROOT / 'papers/Tensile_Properties_of_Sub-sized_Specimens_papers'
OUT = Path(sys.argv[1])


def inventory(folder):
    h = hashlib.sha256(); n = 0
    for p in sorted(folder.rglob('*')):
        if p.is_file():
            st = p.stat(); h.update(f'{p.relative_to(folder).as_posix()}|{st.st_size}|{st.st_mtime_ns}\n'.encode()); n += 1
    return n, h.hexdigest()


before = (inventory(COLL), inventory(PDFS))
R = lambda v: v if isinstance(v, ObjectPointer) else ObjectPointer(**v)
coll = CollectionRepository(str(COLL))
results = {}
for n in coll.papers():
    t0 = time.time(); rec = {'paper': n, 'errors': []}
    try:
        bindings = coll.bindings(n)  # verifies seal, run, PDF identity
        rec['verified'] = True
    except Exception as e:
        rec['verified'] = False; rec['errors'].append('verify: %s: %s' % (type(e).__name__, str(e)[:160])); results[n] = rec; continue
    reader = _EvidenceCache(coll.store); resolve = ReferenceResolver(reader).resolve
    pages = defaultdict(lambda: Counter())
    try:
        nat = resolve(R(bindings['native_document'])); doc = nat.get('document', nat)
        mi = doc.get('extensions', {}).get('mineru', {})
        md = doc.get('metadata', {}).get('document', {})
        rec.update(parse_mode=mi.get('parse_mode'), tier=mi.get('tier'), title=bool(md.get('title')), page_count=len(doc['pages']))
        rec['has_native_page_dims'] = bool(doc.get('extensions', {}).get('docvortex_layout'))
        for pg in doc['pages']:
            i = pg['page_idx']
            for b in pg['blocks']:
                pages[i]['blocks'] += 1; pages[i]['type:' + b['type']] += 1
                if b['type'] == 'table': pages[i]['tables'] += 1
                if b['type'] in ('image', 'chart'): pages[i]['figures'] += 1
                if b['type'] == 'equation': pages[i]['display_equations'] += 1
    except Exception as e:
        rec['errors'].append('native: %s: %s' % (type(e).__name__, str(e)[:160]))
    objects = {}
    try:
        objects = {R(v).sha256: resolve(R(v)) for k, v in bindings.items() if k.startswith('capture_evidence/')}
        rec['capture_objects'] = len(objects)
    except Exception as e:
        rec['errors'].append('captures: %s: %s' % (type(e).__name__, str(e)[:160]))
    index = None
    try:
        index_h, index = next((h, v) for h, v in objects.items() if v.get('schema') == 'mineru-capture-index/1')
        events = {e['object']['sha256']: e for e in index['events']}
        links = read_geometry_links(reader, ObjectPointer(index_h))
    except Exception as e:
        events, links = {}, []; rec['errors'].append('index/links: %s: %s' % (type(e).__name__, str(e)[:160]))
    # layout -> page join, same rule as the reference viewer
    try:
        renders = [(h, v) for h, v in objects.items() if v.get('schema') == 'mineru-geometry-passive/1' and v.get('method') == 'render']
        batches = [(h, v) for h, v in objects.items() if v.get('schema') == 'mineru-layout-passive/1' and v.get('method') == 'batch_predict']
        parsed = [v for h, v in objects.items() if v.get('schema') == 'mineru-layout-passive/1' and v.get('method') == '_parse_prediction']
        rec['layout_windows'] = {'renders': len(renders), 'batches': len(batches), 'parsed': len(parsed)}
        if len(renders) == 1 and len(batches) == 1:
            rh, render = renders[0]; bh, batch = batches[0]
            if events[rh]['parent_call_id'] != events[bh]['parent_call_id']:
                raise ValueError('layout belongs to another render window')
            ps = render['pages']
            if len(ps) != len(parsed) or {v['input_index'] for v in parsed} != set(range(len(ps))):
                raise ValueError('incomplete or ambiguous layout page mapping (%d render pages, %d layout results)' % (len(ps), len(parsed)))
            for v in parsed:
                page = ps[v['input_index']]
                if v['image_size'] != list(reversed(page['size'])):
                    raise ValueError('layout/render dimensions differ on page %d' % page['page_index'])
                pg = page['page_index']
                pages[pg]['layout_items'] += len(v['objects'])
                pages[pg]['layout_tables'] += sum(1 for o in v['objects'] if o['label'] == 'table')
            rec['layout_join'] = 'ok'
        else:
            rec['layout_join'] = 'ambiguous_windows'
    except Exception as e:
        rec['layout_join'] = 'failed'; rec['errors'].append('layout join: %s' % str(e)[:200])
    # OCR line boxes after the detector, per page
    try:
        for h, v in objects.items():
            if v.get('schema') == 'mineru-geometry-passive/1' and v.get('method') == 'ocr_results':
                pages[v['page_index']]['ocr_lines'] += len(v['geometries'])
    except Exception as e:
        rec['errors'].append('ocr_results: %s' % str(e)[:160])
    # detector crops, recognized polygons, table branches per page (from capture links)
    try:
        for l in links:
            pg = l.get('page_index')
            pages[pg]['link:' + l['kind']] += 1
    except Exception as e:
        rec['errors'].append('links: %s' % str(e)[:160])
    # spatial graph: cells and geometry availability
    try:
        graph = SpatialGraph.load(reader, R(bindings['spatial_graph'])); record = graph.record()
        page_entities = {i: resolve(R(nd['data']))['page_index'] for i, nd in record['entities'].items() if nd['kind'] == 'page'}
        def entity_page(identity):
            c = identity
            while c not in page_entities: c = record['entities'][c]['parent']
            return page_entities[c]
        states = Counter(); reasons = Counter()
        for i, nd in record['entities'].items():
            if nd['kind'] == 'document' or nd['kind'] == 'page': continue
            pg = entity_page(i); kind = nd['kind']
            pages[pg]['graph:' + kind] += 1
            if nd['geometry'] is None:
                states[kind + ':unavailable'] += 1; reasons[nd.get('geometry_state')] += 1
                if kind == 'cell': pages[pg]['cells_no_geometry'] += 1
            else:
                states[kind + ':available'] += 1
                if kind == 'cell': pages[pg]['cells'] += 1
        frames = Counter((f['convention'], f['transform_state']) for f in record['frames'].values())
        rec['graph'] = {'entities': dict(states), 'unavailable_reasons': dict(reasons), 'frames': {'%s/%s' % k: v for k, v in frames.items()}}
    except Exception as e:
        rec['errors'].append('graph: %s: %s' % (type(e).__name__, str(e)[:200]))
    # PDF
    try:
        pdf_path = PDFS / (n + '.pdf'); rec['pdf_exists'] = pdf_path.exists()
        if pdf_path.exists():
            sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            rec['pdf_sha_matches'] = sha == coll.entry(n)['pdf_sha256']
            d = pdfium.PdfDocument(str(pdf_path)); rec['pdf_pages'] = len(d); d.close()
    except Exception as e:
        rec['errors'].append('pdf: %s' % str(e)[:160])
    rec['pages'] = {str(k): dict(v) for k, v in sorted(pages.items(), key=lambda kv: (kv[0] is None, kv[0]))}
    rec['seconds'] = round(time.time() - t0, 1)
    results[n] = rec
    print(n, 'ok' if not rec['errors'] else 'errors', rec['seconds'], flush=True)

after = (inventory(COLL), inventory(PDFS))
out = {'collection_sha256': coll.catalog_sha256, 'sealed_unchanged': before == after, 'inventory_files': {'collection': before[0][0], 'pdfs': before[1][0]}, 'papers': results}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf8')
print('done; sealed trees unchanged:', before == after)
