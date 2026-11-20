"""Second read-only pass: bbox completeness, layout/final-block overlap, table HTML, text defects."""
import json, re, sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / 'src/code'))
from mineru_contracts import ObjectPointer, ReferenceResolver
from mineru_observed_geometry import _EvidenceCache
from mineru_collection import CollectionRepository
COLL = ROOT / 'src/raw_results/code_results/tensile_papers'
R = lambda v: v if isinstance(v, ObjectPointer) else ObjectPointer(**v)
coll = CollectionRepository(str(COLL))
audit = json.load(open(sys.argv[1], encoding='utf8'))


def iou(a, b):
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw = max(0, min(ax2, bx2) - max(a[0], b[0])); ih = max(0, min(ay2, by2) - max(a[1], b[1]))
    i = iw * ih; u = a[2] * a[3] + b[2] * b[3] - i
    return i / u if u else 0


def spans_text(c):
    out = []
    for x in c or []:
        if isinstance(x, str): out.append(x)
        elif isinstance(x, dict):
            if isinstance(x.get('content'), list): out.append(spans_text(x['content']))
            elif isinstance(x.get('content'), str): out.append(x['content'])
    return ''.join(out)


tot = collections.Counter(); per = {}
for n in coll.papers():
    b = coll.bindings(n); reader = _EvidenceCache(coll.store); resolve = ReferenceResolver(reader).resolve
    nat = resolve(R(b['native_document'])); doc = nat.get('document', nat)
    objects = {R(v).sha256: resolve(R(v)) for k, v in b.items() if k.startswith('capture_evidence/')}
    render = next(v for v in objects.values() if v.get('schema') == 'mineru-geometry-passive/1' and v.get('method') == 'render')
    parsed = [v for v in objects.values() if v.get('schema') == 'mineru-layout-passive/1' and v.get('method') == '_parse_prediction']
    layout = {}
    for v in parsed:
        page = render['pages'][v['input_index']]; H, W = v['image_size']
        layout[page['page_index']] = [(o['label'], o['bbox'][0] / W * 100, o['bbox'][1] / H * 100, (o['bbox'][2] - o['bbox'][0]) / W * 100, (o['bbox'][3] - o['bbox'][1]) / H * 100) for o in v['objects']]
    c = collections.Counter()
    for pg in doc['pages']:
        i = pg['page_idx']
        for blk in pg['blocks']:
            c['blocks'] += 1
            bb = blk.get('bbox')
            if not bb: c['blocks_no_bbox'] += 1; continue
            box = (bb[0] * 100, bb[1] * 100, (bb[2] - bb[0]) * 100, (bb[3] - bb[1]) * 100)
            best = max((iou(box, l[1:]) for l in layout.get(i, []) if l[0] != 'inline_formula'), default=0)
            c['match_ge_0.5' if best >= 0.5 else ('match_0.3_0.5' if best >= 0.3 else 'match_lt_0.3')] += 1
            if blk.get('continues_prev'): c['continues_prev'] += 1
            t = blk['type']
            if t in ('image', 'chart', 'table') and isinstance(blk.get('content'), list):
                for part in blk['content']:
                    c['parts'] += 1
                    if not part.get('bbox'): c['parts_no_bbox'] += 1
                    c['part:' + part['type']] += 1
                    if part['type'] == 'table_body' and isinstance(part.get('content'), str):
                        h = part['content']; c['tables_html'] += 1
                        if not h.strip(): c['tables_html_empty'] += 1
                        if re.search(r'(row|col)span="[2-9]', h): c['tables_with_merged_cells'] += 1
                        c['table_cells_html'] += len(re.findall(r'<t[dh][ >]', h))
            text = spans_text(blk.get('content')) if isinstance(blk.get('content'), list) else (blk.get('content') if isinstance(blk.get('content'), str) else '')
            if '\ufffd' in text: c['blocks_with_replacement_char'] += 1
            if t == 'equation' and not text.strip(): c['equation_empty'] += 1
    per[n] = dict(c); tot.update(c)
    print(n, 'done', flush=True)
json.dump({'per_paper': per, 'total': dict(tot)}, open(sys.argv[2], 'w'), indent=1)
print(dict(tot))
