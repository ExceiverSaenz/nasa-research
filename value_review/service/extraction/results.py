"""From the model's answer to the result file Review reads (ADR-027, BR-X11, BR-X12).

The answer (``extraction-answer``) is mapped to the format of the existing LLM results
(``<paper>-pdf_with_feature_guide.json``, llm_baseline/extraction_prompt.md "Output contract"), so the ingest and Review
work as they do today. Each value's quote is looked for in the PDF's text layer: first on the page the model gave, then on
the other pages, then the value itself. Found: its box, normalised with the origin at the top left. Not found: the
evidence keeps its page and has no box. The model's own text is kept as returned.
"""
import json
import re
import threading

import pypdfium2 as pdfium

from ...ingest import sha256_file
from ...storage import atomic_write_bytes

PDFIUM = threading.Lock()   # pdfium is not thread-safe: one search at a time
MODE = 'api_pdf'


def _norm(text):
    return re.sub(r'\s+', ' ', text or '').strip()


def _box(textpage, start, count, width, height):
    """The union of the boxes of ``count`` characters from ``start``, normalised, origin top left (CropBox at 0, 0)."""
    boxes = [textpage.get_charbox(i) for i in range(start, start + count)]
    boxes = [b for b in boxes if b[2] > b[0] or b[3] > b[1]] or boxes
    left, bottom = min(b[0] for b in boxes), min(b[1] for b in boxes)
    right, top = max(b[2] for b in boxes), max(b[3] for b in boxes)
    clamp = lambda v: round(min(1.0, max(0.0, v)), 4)   # noqa: E731
    return [clamp(left / width), clamp((height - top) / height), clamp(right / width), clamp((height - bottom) / height)]


class PdfText:
    """The text pages of one PDF, opened once while one answer is mapped."""
    def __init__(self, path):
        self.doc = pdfium.PdfDocument(str(path))
        self.count = len(self.doc)
        self._pages = {}

    def close(self):
        for page, textpage in self._pages.values():
            textpage.close()
            page.close()
        self.doc.close()

    def find(self, page_no, text):
        """The box of ``text`` on page ``page_no`` (1-based), or None."""
        needle = _norm(text)
        if not needle or not 1 <= page_no <= self.count:
            return None
        if page_no not in self._pages:
            page = self.doc[page_no - 1]
            self._pages[page_no] = (page, page.get_textpage())
        page, textpage = self._pages[page_no]
        searcher = textpage.search(needle, match_case=False)
        try:
            hit = searcher.get_next()
        finally:
            searcher.close()
        if not hit:
            return None
        width, height = page.get_size()
        return _box(textpage, hit[0], hit[1], width, height)

    def locate(self, page_no, quote, value):
        """(page, box, quality): ``exact`` on the given page, ``other_page``, ``value_only``, or ``not_found``."""
        others = [p for p in range(1, self.count + 1) if p != page_no]
        for text, quality in ((quote, 'exact'), (value, 'value_only')):
            box = self.find(page_no, text)
            if box:
                return page_no, box, quality
            if quality == 'exact':
                for p in others:
                    box = self.find(p, text)
                    if box:
                        return p, box, 'other_page'
        return (page_no if 1 <= page_no <= self.count else None), None, 'not_found'


def to_result(answer, run, paper, pdf_path, set_name):
    """The result file for one paper, as a dict (the baseline format)."""
    with PDFIUM:
        text = PdfText(pdf_path)
        try:
            return _build(answer, run, paper, pdf_path, set_name, text)
        finally:
            text.close()


def _build(answer, run, paper, pdf_path, set_name, text):
    records = []
    known = {}
    for i, r in enumerate(answer['records'], 1):
        rid = f'r{i}'
        known[r['record_id']] = rid
        records.append({'record_id': rid, 'source_label': r['label'], 'condition_summary': r['condition'] or None,
                        'identity_evidence_ids': [], 'record_kind': 'specimen', 'statistic_as_reported': None,
                        'replicate_count': None, 'notes': ''})
    regions, evidence, observations, used = [], [], [], []
    for i, v in enumerate(answer['values'], 1):
        page, box, quality = text.locate(v['page'], v['quote'], v['value'])
        ids = []
        if page is not None:
            regions.append({'region_id': f'g{i}', 'page_number': page, 'printed_page_label': None, 'kind': 'text',
                            'source_label': None, 'bbox': box, 'location_quality': quality})
            evidence.append({'evidence_id': f'e{i}', 'region_id': f'g{i}', 'role': 'value', 'literal_text': v['quote'],
                             'bbox': box, 'location_quality': quality, 'notes': ''})
            ids = [f'e{i}']
        records_of = [known[r] for r in v['record_ids'] if r in known]
        if v['field_id'] not in used:
            used.append(v['field_id'])
        observations.append({
            'observation_id': f'o{i}', 'feature_id': v['field_id'], 'record_ids': records_of, 'candidate_record_ids': [],
            'assignment_status': 'established' if records_of else 'unassigned', 'scope': 'record',
            'source_status': 'reported', 'value_as_reported': v['value'], 'unit_as_reported': v['unit'] or None,
            'evidence_ids': ids, 'derivation': None, 'flags': list(v['flags']), 'notes': v['notes'] or ''})
    completion = answer['completion']
    return {
        'schema_version': '1.0', 'run_id': run['id'], 'mode': MODE,
        'paper': {'paper_id': str(paper), 'pdf_path': f'papers/{set_name}/{paper}.pdf', 'sha256': sha256_file(pdf_path),
                  'title': None, 'page_count': text.count, 'workbook_reference_id': None},
        'completion': {'status': completion['status'], 'pages_reviewed': [], 'pages_unreviewed': [], 'summary': completion['notes']},
        'feature_columns': used, 'records': records, 'regions': regions, 'evidence': evidence, 'observations': observations,
        'workbook_targets': [], 'tool_notes': [f'Model {run["model"]}; boxes placed by searching the quoted text in the PDF.'],
        'limitations': [],
    }


def write_manifest(folder, manifest):
    """``run.json`` in the run's results folder (run-manifest.schema.json; ADR-028)."""
    from ... import schemas
    errs = schemas.errors('run-manifest', manifest)
    if errs:   # a bug, not a client error
        raise RuntimeError(f'manifest would not validate: {errs[:3]}')
    atomic_write_bytes(folder / 'run.json', (json.dumps(manifest, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))


def write_result(folder, paper, result):
    """Write ``<paper>-pdf_with_feature_guide.json`` atomically into the run's results folder."""
    from ...config import RESULT_SUFFIX
    atomic_write_bytes(folder / f'{paper}{RESULT_SUFFIX}', (json.dumps(result, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))
