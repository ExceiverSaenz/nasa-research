"""Builds ``originals/<n>.json`` (schema ``parsing-validator-original/1``) from sealed evidence.

Deterministic: the same sealed input produces the same bytes (no clock, no random ids).
Nothing is repaired: a block, detection or entity that cannot be placed is recorded
with a reason (ADR-004). Percent coordinates are relative to the displayed raster
(scale ``RENDER_SCALE``) and rounded to three decimals.
"""
import json
import sys
from pathlib import Path

from .adapter import SealedPaper

SCHEMA = 'parsing-validator-original/1'
RENDER_SCALE = 1.9
PART_TYPES = ('table_caption', 'table_body', 'table_footnote', 'image_body', 'image_caption',
              'image_footnote', 'chart_body', 'chart_caption', 'chart_footnote', 'code_body', 'code_caption')
WEAK_IOU = 0.5


def _bbox_pct(points, size):
    """Axis-aligned box of projected points as percent of the raster size."""
    w, h = size
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    return {'x': round(x0 / w * 100, 3), 'y': round(y0 / h * 100, 3),
            'w': round((x1 - x0) / w * 100, 3), 'h': round((y1 - y0) / h * 100, 3)}


def _poly_pct(points, size):
    w, h = size
    return [[round(p[0] / w * 100, 3), round(p[1] / h * 100, 3)] for p in points]


def _iou(a, b):
    ax1, ay1, bx1, by1 = a['x'] + a['w'], a['y'] + a['h'], b['x'] + b['w'], b['y'] + b['h']
    iw = max(0.0, min(ax1, bx1) - max(a['x'], b['x']))
    ih = max(0.0, min(ay1, by1) - max(a['y'], b['y']))
    inter = iw * ih
    union = a['w'] * a['h'] + b['w'] * b['h'] - inter
    return inter / union if union > 0 else 0.0


def _layout_match(box, items):
    best, best_iou = None, 0.0
    for item in items:
        value = _iou(box, item['bbox_pct'])
        if value > best_iou:
            best, best_iou = item, value
    return {'item_id': best['id'] if best else None, 'iou': round(best_iou, 3), 'weak': best_iou < WEAK_IOU}


def _parts(paper, block, base_pointer, project, size):
    parts, seen = [], {}
    content = block.get('content')
    if not isinstance(content, list):
        return parts, None
    html = None
    for ci, sub in enumerate(content):
        if not isinstance(sub, dict) or sub.get('type') not in PART_TYPES:
            continue
        key = sub['type']
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key = f'{key}_{seen[key]}'
        part = {'key': key, 'part_index': sub.get('index'), 'bbox_pct': None}
        pointer = f'{base_pointer}/content/{ci}'
        identity = paper.native_entity(pointer)
        if identity is not None:
            points, ref = paper.entity_geometry(identity)
            if points is not None:
                part['bbox_pct'] = _bbox_pct(project(points), size)
            else:
                part['bbox_unavailable'] = ref
        if sub['type'] == 'table_body':
            html = sub.get('content')
        elif isinstance(sub.get('content'), (list, str)) and sub.get('content'):
            part['content'] = sub['content']
        part['source'] = paper.source_pointer(pointer)
        parts.append(part)
    return parts, html


def build_original(collection_root, pdf_dir, paper_id, scale=RENDER_SCALE):
    """Return the original of one paper as a JSON-serializable dict."""
    paper = SealedPaper(collection_root, paper_id)
    pdf = paper.pdf_path(pdf_dir)
    raster = SealedPaper.render_display(pdf, scale)
    pages_native = paper.native_pages()
    meta = paper.native.get('metadata', {}).get('document', {})
    extensions = paper.native.get('extensions', {})
    dims = {p['page_idx']: p for p in extensions.get('docvortex_layout', {}).get('pages', [])}
    ignored = paper.ignored_without_geometry()
    if len(raster) != len(pages_native):
        raise ValueError(f'Paper {paper_id}: {len(raster)} rendered pages but {len(pages_native)} native pages')
    pages = []
    for ai, native_page in enumerate(pages_native):
        page = native_page['page_idx']
        width_px, height_px, display = raster[page]
        size = (width_px, height_px)

        def project(points, display=display):
            return display.apply(points)

        layout = [{'id': f'L{i}', 'label': label, 'score': score, 'bbox_pct': _bbox_pct(project(pts), size), 'source': ref}
                  for i, (label, score, pts, ref) in enumerate(paper.layout_items(page))]
        lines = [{'id': f'O{i}', 'poly_pct': _poly_pct(project(pts), size), 'text': None, 'source': ref}
                 for i, (pts, ref) in enumerate(paper.ocr_lines(page))]
        cells = [{'id': f'C{i}', 'branch': branch, 'poly_pct': _poly_pct(project(pts), size), 'source': ref}
                 for i, (branch, pts, ref) in enumerate(paper.cells(page))]
        blocks = []
        for bi, block in enumerate(native_page['blocks']):
            pointer = f'/document/pages/{ai}/blocks/{bi}'
            identity = paper.native_entity(pointer)
            bbox, unavailable = None, None
            if identity is None:
                unavailable = 'no_entity'
            else:
                points, ref = paper.entity_geometry(identity)
                if points is None:
                    unavailable = ref
                else:
                    bbox = _bbox_pct(project(points), size)
            parts, html = _parts(paper, block, pointer, project, size)
            kind = block['type']
            content = block.get('content')
            if kind == 'table':
                content = None
            entry = {'id': f'k{block["index"]}', 'index': block['index'], 'type': kind, 'bbox_pct': bbox,
                     'continues_prev': bool(block.get('continues_prev', False)),
                     'layout_match': _layout_match(bbox, layout) if bbox else {'item_id': None, 'iou': 0.0, 'weak': True},
                     'content': content}
            if unavailable:
                entry['bbox_unavailable'] = unavailable
            if kind == 'table':
                entry['html'] = html
            if parts:
                entry['parts'] = parts
            entry['source'] = paper.source_pointer(pointer)
            blocks.append(entry)
        reason = paper.layers_reason()
        pages.append({
            'index': page,
            'width_pt': dims.get(page, {}).get('width_pt'), 'height_pt': dims.get(page, {}).get('height_pt'),
            'render': {'scale': scale, 'width_px': width_px, 'height_px': height_px},
            'ignored_without_geometry': ignored.get(page, 0),
            'blocks': blocks,
            'layers': {
                'layout': {'available': bool(layout), **({} if layout else {'reason': reason or 'not_captured'}), 'items': layout},
                'ocr': {'available': bool(lines), **({} if lines else {'reason': reason or 'not_captured'}), 'items': lines},
                'cells': {'available': bool(cells), **({} if cells else {'reason': 'not_captured'}), 'items': cells},
            },
        })
    return {
        'schema': SCHEMA,
        'paper': str(paper_id),
        'source': {'collection_sha256': paper.catalog_sha256, 'run_id': paper.entry['run_id'],
                   'manifest_sha256': paper.entry['manifest_sha256'], 'pdf_file': f'{paper_id}.pdf',
                   'pdf_sha256': paper.entry['pdf_sha256']},
        'document': {'title': meta.get('title'), 'authors': meta.get('authors', []),
                     'identifiers': meta.get('identifiers', []), 'page_count': len(pages_native),
                     'parse_mode': extensions.get('mineru', {}).get('parse_mode')},
        'pages': pages,
    }


def dumps(original):
    """Canonical bytes: same input, same bytes."""
    return json.dumps(original, ensure_ascii=False, indent=1, sort_keys=False, allow_nan=False).encode('utf-8') + b'\n'


def write_original(collection_root, pdf_dir, paper_id, out_dir):
    """Generate ``<out_dir>/<n>.json`` once; if it exists and differs, that is an error, not an overwrite (BR-03)."""
    data = dumps(build_original(collection_root, pdf_dir, paper_id))
    target = Path(out_dir) / f'{paper_id}.json'
    if target.exists():
        if target.read_bytes() != data:
            raise ValueError(f'{target} exists and differs from what would be generated')
        return target
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix('.json.tmp')
    temp.write_bytes(data)
    temp.replace(target)
    return target


if __name__ == '__main__':
    sys.exit('Use: python -m parsing_validator.ingest <collection> <pdf_dir> <out_dir> [paper ...]')
