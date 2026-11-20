"""Independent artifact checks, without recomputing the scientific analysis."""
import csv
import hashlib
import json
from pathlib import Path
import re

project = Path(__file__).resolve().parents[4]
root = project/'test_libs/bounding_boxes/analysis/auto-20261101T080056Z-r2'
def read(name):
    return json.loads((root/name).read_text(encoding='utf-8'))
summary, verification, manifest = read('automatic_summary.json'), read('analysis_verification.json'), read('analysis_manifest.json')
assert verification['status'] == 'PASS' and verification['all_inputs_unchanged']
assert manifest['status'] == 'automatic_complete_visual_review_pending'
counts = {}
geometry_errors = 0
for name, expected in [('detections.jsonl',35240), ('agreement_edges.jsonl',35778),
                       ('agreement_components.jsonl',24878), ('native_patterns.jsonl',1588)]:
    n = 0
    with (root/name).open(encoding='utf-8') as f:
        for line in f:
            row = json.loads(line); n += 1
            if name == 'detections.jsonl':
                geometry_errors += bool(row.get('geometry_error'))
            if name == 'native_patterns.jsonl':
                assert row['semantic_review_status'] == 'not_reviewed'
    assert n == expected, (name,n,expected)
    counts[name] = n
batch = read('review_batches.json')
pages = [p for paper in batch['papers'] for p in paper['pages']]
assert len(batch['papers']) == 15 and len(pages) == 397
assert len({(p['paper_sha256'],p['page_idx']) for p in pages}) == 397
assert all(not p['page_case_inventory_complete'] and p['visual_review_status']=='not_reviewed' for p in pages)
assert all(Path(p['image_path']).is_file() for p in pages)
assert not (root/'case_registry.jsonl').read_text() and not (root/'case_assessments.jsonl').read_text()
with (root/'reviewed_metrics.csv').open(encoding='utf-8') as f:
    assert not list(csv.DictReader(f))
with (root/'attempt_failure_summary.csv').open(encoding='utf-8') as f:
    attempts = list(csv.DictReader(f))
assert len(attempts) == 6 and sum(int(r['failed']) for r in attempts) == 22
with (root/'detector_page_timings.csv').open(encoding='utf-8') as f:
    assert len(list(csv.DictReader(f))) == 794
broken = []
for md in [root/'report.md', *sorted((root/'review').glob('*.md'))]:
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', md.read_text(encoding='utf-8')):
        if not target.startswith(('http:','https:','#')) and not (md.parent/target).resolve().exists():
            broken.append((str(md),target))
assert not broken, broken
checked = []
for item in read('input_manifest.json'):
    if item['path'].endswith(('.py','plan_analisis.md')):
        actual = hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()
        assert actual == item['sha256'], item['path']
        checked.append(item['path'])
result = dict(status='PASS', parsed_output_counts=counts, review_batches=15, review_pages=397,
              unique_pages=397, human_reviewed_pages=0, broken_review_links=broken,
              source_geometry_errors_observed=geometry_errors, detector_page_timing_observations=794,
              separate_attempt_tool_rows=6, historical_failure_records=22,
              frozen_implementation_and_plan_current_hashes_match=True,
              checked_frozen_files=checked, semantic_validation='not_performed')
(root/'output_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
