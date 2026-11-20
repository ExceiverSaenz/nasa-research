"""Synthetic data bigger than the real run, to see where time and memory grow (13-performance-report.md).

    python -B -m value_review.perf.stress_data --out <empty folder> [--papers 50] [--values 2000] [--pages 60] [--versions 20]

Builds ``<out>/run`` (LLM results), ``<out>/pdfs`` (blank PDFs: page rendering is measured on the real PDFs instead),
``<out>/data`` (originals and settings) and, with ``--versions``, that many full snapshot versions of the biggest paper,
written through the real service so they are exactly what Submit writes.
"""
import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review.ingest import features, ingest_run  # noqa: E402
from value_review.tests.test_ingest import make_pdf, sha  # noqa: E402

RESULT = '-pdf_with_feature_guide.json'
FEATURES = [f for f, _ in features.FEATURES]


def result_for(pid, values, pages, pdf_sha, rnd):
    """An extraction result with ``values`` observations spread over ``pages`` pages and values/10 records."""
    n_rec = max(1, values // 10)
    records = [{'record_id': f'r{i}', 'source_label': f'SS-{i}', 'condition_summary': f'Condition {i}', 'identity_evidence_ids': [],
                'record_kind': 'individual', 'statistic_as_reported': None, 'replicate_count': None, 'notes': ''} for i in range(n_rec)]
    regions = [{'region_id': f'g{p}', 'page_number': p, 'kind': 'table', 'source_label': f'Table {p}', 'bbox': [0, 0, 1, 1],
                'location_quality': 'measured'} for p in range(1, pages + 1)]
    evidence, observations = [], []
    for i in range(values):
        page = 1 + i % pages
        x, y = rnd.uniform(0.05, 0.8), rnd.uniform(0.05, 0.9)
        evidence.append({'evidence_id': f'e{i}', 'region_id': f'g{page}', 'role': 'datum', 'literal_text': f'{100 + i} ± {i % 30}',
                         'bbox': [round(x, 4), round(y, 4), round(x + 0.06, 4), round(y + 0.012, 4)], 'location_quality': 'measured', 'notes': ''})
        flags = ['yield_fracture_criterion_ambiguous'] if i % 13 == 0 else []
        observations.append({'observation_id': f'o{i}', 'feature_id': FEATURES[i % len(FEATURES)], 'record_ids': [f'r{i % n_rec}'],
                             'candidate_record_ids': [], 'assignment_status': 'established', 'scope': 'specimen',
                             'source_status': 'explicit', 'value_as_reported': f'{100 + i} ± {i % 30}', 'unit_as_reported': 'MPa',
                             'evidence_ids': [f'e{i}'], 'derivation': None, 'flags': flags, 'notes': ''})
    return {'schema_version': '1.0', 'run_id': 'stress', 'mode': 'pdf_with_feature_guide',
            'paper': {'paper_id': pid, 'pdf_path': f'{pid}.pdf', 'sha256': pdf_sha, 'title': f'Stress paper {pid}', 'page_count': pages,
                      'workbook_reference_id': None},
            'completion': {'status': 'complete', 'pages_reviewed': list(range(1, pages + 1)), 'pages_unreviewed': [], 'summary': ''},
            'feature_columns': [], 'records': records, 'regions': regions, 'evidence': evidence, 'observations': observations,
            'workbook_targets': [], 'tool_notes': [], 'limitations': []}


def build(out, papers=50, values=2000, pages=60, small_values=300, small_pages=12, seed=7):
    """Paper 1 is the big one (``values``, ``pages``); the others have ``small_values`` values on ``small_pages`` pages."""
    rnd = random.Random(seed)   # noqa: S311  (synthetic positions, not security)
    out = Path(out)
    run, pdfs, data = out / 'run', out / 'pdfs', out / 'data'
    for folder in (run, pdfs, data / 'annotations'):
        folder.mkdir(parents=True, exist_ok=True)
    for n in range(1, papers + 1):
        v, p = (values, pages) if n == 1 else (small_values, small_pages)
        pdf = pdfs / f'{n}.pdf'
        make_pdf(pdf, [(612, 792)] * p)
        (run / f'{n}{RESULT}').write_text(json.dumps(result_for(str(n), v, p, sha(pdf), rnd)), encoding='utf-8')
    rows = ingest_run(run, pdfs, data / 'originals')
    failed = [r for r in rows if r['outcome'] != 'written']
    if failed:
        raise SystemExit(f'stress ingest failed: {failed[:2]}')
    settings = {'reviewer_name': 'Expert reviewer', 'keep_versions': 20, 'autosave_minutes': 5, 'active_source': 'default',
                'sources': [{'id': 'default', 'name': 'Stress', 'run_dir': str(run), 'pdf_dir': str(pdfs)}]}
    (data / 'annotations' / 'settings.json').write_text(json.dumps(settings), encoding='utf-8')
    return data


def add_versions(data, paper, count):
    """``count`` submits of ``paper`` through the real service, each deciding every value (full snapshots)."""
    from fastapi.testclient import TestClient
    from value_review.service.app import create_app
    from value_review.service.config import Config
    with TestClient(create_app(Config(data=data), web_dir=None), base_url='http://127.0.0.1') as client:
        original = client.get(f'/api/v1/papers/{paper}').json()['original']
        for k in range(count):
            verdicts = ['accepted', 'rejected', 'unsure']
            decisions = {o['observation_id']: {'verdict': verdicts[(i + k) % 3], 'note': '' if (i + k) % 3 == 0 else 'Stress reason',
                                               'by': 'Expert reviewer', 'at': '2026-11-19T10:00:00Z'}
                         for i, o in enumerate(original['observations'])}
            state = {'schema': 'value-review-state/1', 'decisions': decisions, 'column_moves': {}, 'record_moves': {},
                     'record_edits': {}, 'added_records': [], 'added_values': [], 'boxes': {}}
            r = client.post(f'/api/v1/papers/{paper}/versions', json={'state': state}, headers={'If-Match': f'"{k}"'})
            if r.status_code != 201:
                raise SystemExit(f'submit {k + 1} failed: {r.status_code} {r.text[:200]}')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -B -m value_review.perf.stress_data')
    parser.add_argument('--out', required=True)
    parser.add_argument('--papers', type=int, default=50)
    parser.add_argument('--values', type=int, default=2000)
    parser.add_argument('--pages', type=int, default=60)
    parser.add_argument('--versions', type=int, default=20)
    args = parser.parse_args(argv)
    data = build(args.out, args.papers, args.values, args.pages)
    if args.versions:
        add_versions(data, '1', args.versions)
    print(data)
    return 0


if __name__ == '__main__':
    sys.exit(main())
