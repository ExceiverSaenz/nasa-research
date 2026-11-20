"""The only module that calls private project code (ADR-004).

Everything underscore-private from ``src/code`` is used here and nowhere else.
Read-only: no write method of the stores is called, nothing is repaired; what
cannot be placed is reported with a reason.
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/code'))
from mineru_collection import CollectionRepository  # noqa: E402
from mineru_contracts import ContractError, ObjectPointer, ReferenceResolver  # noqa: E402
from mineru_observed_geometry import _EvidenceCache  # noqa: E402
from mineru_pdf_coordinates import _facts, find_evidence, matrix_from_evidence  # noqa: E402
from mineru_spatial import Matrix3, SpatialGraph, _points  # noqa: E402

__all__ = ['ContractError', 'CollectionRepository', 'SealedPaper', 'display_matrix']


def _ptr(value):
    return value if isinstance(value, ObjectPointer) else ObjectPointer(**value)


def _ref(value):
    p = _ptr(value)
    return {'sha256': p.sha256, 'pointer': p.pointer}


def display_matrix(samples):
    """PDF user space -> display pixels, from four observed viewport samples (as the reference viewer)."""
    if len(samples) != 4:
        raise ContractError('Four observed viewport samples required')
    w, h = samples[1]['device'][0], samples[2]['device'][1]
    if w <= 0 or h <= 0 or [s['device'] for s in samples] != [[0, 0], [w, 0], [0, h], [w, h]]:
        raise ContractError('Invalid display viewport samples')
    p, a, b, c = [s['page'] for s in samples]
    matrix = Matrix3([[(a[0] - p[0]) / w, (b[0] - p[0]) / h, p[0]],
                      [(a[1] - p[1]) / w, (b[1] - p[1]) / h, p[1]], [0, 0, 1]])
    if any(abs(x - y) > 1e-6 for x, y in zip(matrix.apply([(w, h)])[0], c)):
        raise ContractError('Inconsistent display coordinate samples')
    return matrix.inverse()


class SealedPaper:
    """One verified paper of a sealed collection, with geometry helpers."""

    def __init__(self, collection_root, paper):
        self.paper = str(paper)
        self.collection = CollectionRepository(str(collection_root))
        self.catalog_sha256 = self.collection.catalog_sha256
        self.entry = self.collection.entry(self.paper)
        self.bindings = self.collection.bindings(self.paper)  # verifies seal, run and PDF identity
        self.reader = _EvidenceCache(self.collection.store)
        self.resolve = ReferenceResolver(self.reader).resolve
        self.native_ref = _ptr(self.bindings['native_document'])
        native = self.resolve(self.native_ref)
        self.native = native['document'] if 'document' in native else native
        self.graph = SpatialGraph.load(self.reader, _ptr(self.bindings['spatial_graph']))
        self.record = self.graph.record()
        self.objects = {_ptr(v).sha256: self.resolve(_ptr(v))
                        for k, v in self.bindings.items() if k.startswith('capture_evidence/')}
        self._frames = {}
        self._pages = {i: self.resolve(_ptr(n['data']))['page_index']
                       for i, n in self.record['entities'].items() if n['kind'] == 'page'}
        self._native_ids = {n['data']['pointer']: i for i, n in self.record['entities'].items()
                            if n['data']['sha256'] == self.native_ref.sha256}
        self._render = None

    # --- native document -------------------------------------------------
    def native_pages(self):
        return self.native['pages']

    def source_pointer(self, pointer):
        return {'sha256': self.native_ref.sha256, 'pointer': pointer}

    # --- geometry ----------------------------------------------------------
    def frame_to_pdf(self, identity):
        if identity not in self._frames:
            frame = self.record['frames'][identity]
            if frame['parent'] is None:
                if frame['convention'] != 'pdf_user_space':
                    raise ContractError('Unknown root convention')
                self._frames[identity] = Matrix3.identity()
            else:
                if frame['transform_state'] != 'available':
                    raise ContractError('Unavailable frame mapping')
                _, edge = self.graph._matrix(_ptr(frame['transform']))
                self._frames[identity] = self.frame_to_pdf(frame['parent']) @ edge
        return self._frames[identity]

    def entity_page(self, identity):
        cursor = identity
        while cursor not in self._pages:
            cursor = self.record['entities'][cursor]['parent']
        return self._pages[cursor]

    def entity_geometry(self, identity):
        """(points in PDF user space, source ref) of an entity, or (None, reason)."""
        node = self.record['entities'][identity]
        geometry = node['geometry']
        if geometry is None:
            return None, node.get('geometry_state') or 'not_exposed'
        points = _points(self.resolve(_ptr(geometry['source'])), geometry['encoding'])
        return self.frame_to_pdf(geometry['frame']).apply(points), _ref(geometry['source'])

    def native_entity(self, pointer):
        return self._native_ids.get(pointer)

    def ignored_without_geometry(self):
        """Count, per page, entities that are not native blocks and have no geometry (OQ-14)."""
        counts = {}
        for i, n in self.record['entities'].items():
            if n['kind'] in ('document', 'page') or n['geometry'] is not None:
                continue
            if n['data']['sha256'] == self.native_ref.sha256 and n['kind'] != 'cell':
                continue  # native blocks without a box are reported on the block itself
            page = self.entity_page(i)
            counts[page] = counts.get(page, 0) + 1
        return counts

    # --- layers ------------------------------------------------------------
    def _render_windows(self):
        if self._render is not None:
            return self._render
        renders = [(h, v) for h, v in self.objects.items()
                   if v.get('schema') == 'mineru-geometry-passive/1' and v.get('method') == 'render']
        batches = [(h, v) for h, v in self.objects.items()
                   if v.get('schema') == 'mineru-layout-passive/1' and v.get('method') == 'batch_predict']
        parsed = [(h, v) for h, v in self.objects.items()
                  if v.get('schema') == 'mineru-layout-passive/1' and v.get('method') == '_parse_prediction']
        index_h, index = next((h, v) for h, v in self.objects.items() if v.get('schema') == 'mineru-capture-index/1')
        events = {e['object']['sha256']: e for e in index['events']}
        out = {'matrices': {}, 'layout': {}, 'ok': False, 'reason': None}
        self._render = out
        if len(renders) != 1 or len(batches) != 1:
            out['reason'] = 'ambiguous_windows'
            return out
        render_h, render = renders[0]
        batch_h, _ = batches[0]
        if events[render_h]['parent_call_id'] != events[batch_h]['parent_call_id']:
            out['reason'] = 'layout_in_another_window'
            return out
        pages = render['pages']
        if len(pages) != len(parsed) or {v['input_index'] for _, v in parsed} != set(range(len(pages))):
            out['reason'] = 'ambiguous_layout_mapping'
            return out
        index_ref = ObjectPointer(index_h)
        for j, original in enumerate(pages):
            rr = ObjectPointer(render_h, f'/pages/{j}')
            evidence = find_evidence(self.reader, _ptr(self.bindings['pdf_coordinates']), rr)
            if evidence is None:
                continue
            visual = matrix_from_evidence(self.reader, evidence, source_ref=_ptr(self.bindings['source']),
                                          index_ref=index_ref, render_ref=rr)
            scale = original['scale']
            out['matrices'][original['page_index']] = visual @ Matrix3([[1 / scale, 0, 0], [0, 1 / scale, 0], [0, 0, 1]])
        for h, value in parsed:
            page = pages[value['input_index']]
            if value['image_size'] != list(reversed(page['size'])):
                continue
            out['layout'].setdefault(page['page_index'], []).append((h, value))
        out['ok'] = True
        return out

    def layers_reason(self):
        return self._render_windows()['reason']

    def layout_items(self, page):
        """[(label, score, points_in_pdf, ref)] of the returned layout detections of a page."""
        w = self._render_windows()
        matrix = w['matrices'].get(page)
        items = []
        if matrix is None:
            return items
        for h, value in w['layout'].get(page, []):
            for i, obj in enumerate(value['objects']):
                items.append((obj['label'], obj.get('score'), matrix.apply(_points(obj['bbox'], 'bbox_xyxy')),
                              {'sha256': h, 'pointer': f'/objects/{i}/bbox'}))
        return items

    def ocr_lines(self, page):
        """[(points_in_pdf, ref)] of the OCR line boxes after the detector (geometry only)."""
        w = self._render_windows()
        matrix = w['matrices'].get(page)
        lines = []
        if matrix is None:
            return lines
        for h, value in sorted(self.objects.items()):
            if value.get('schema') == 'mineru-geometry-passive/1' and value.get('method') == 'ocr_results' \
                    and value['page_index'] == page:
                for i, g in enumerate(value['geometries']):
                    lines.append((matrix.apply(_points(g['bbox'], 'bbox_xyxy')),
                                  {'sha256': h, 'pointer': f'/geometries/{i}/bbox'}))
        return lines

    def cells(self, page):
        """[(branch, points_in_pdf, ref)] of cells with geometry on a page."""
        out = []
        for i, n in sorted(self.record['entities'].items()):
            if n['kind'] != 'cell' or n['geometry'] is None or self.entity_page(i) != page:
                continue
            points, ref = self.entity_geometry(i)
            out.append((n['branch'], points, ref))
        return out

    # --- display raster -----------------------------------------------------
    def pdf_path(self, pdf_dir):
        path = Path(pdf_dir) / f'{self.paper}.pdf'
        if hashlib.sha256(path.read_bytes()).hexdigest() != self.entry['pdf_sha256']:
            raise ContractError('Original PDF changed')
        return path

    @staticmethod
    def render_display(pdf_path, scale):
        """[(width_px, height_px, pdf->display Matrix3)] per page, rendered without inference."""
        import pypdfium2 as pdfium
        out = []
        doc = pdfium.PdfDocument(str(pdf_path))
        try:
            for i in range(len(doc)):
                page = doc[i]
                bitmap = None
                try:
                    bitmap = page.render(scale=scale)
                    image = bitmap.to_pil()
                    w, h = image.size
                    image.close()
                    out.append((w, h, display_matrix(_facts(page, [0, 0, w, h, 0], pdfium.raw)['samples'])))
                finally:
                    if bitmap is not None:
                        bitmap.close()
                    page.close()
        finally:
            doc.close()
        return out
