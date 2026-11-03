"""Agreement and coverage only; no inference or claims of accuracy."""
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path


def compare_pair(a, b):
    result = {'metric_kind': 'agreement', 'status': 'not_comparable',
              'precedence_disagreement': None, 'successor_jaccard': None,
              'pairs_inverted': 0, 'pairs_evaluated': 0, 'successor_intersection': 0, 'successor_union': 0}
    if a['status'] != 'PASS' or b['status'] != 'PASS' or a['scope'] != b['scope']:
        return result
    x, y = a['ordered_ids'], b['ordered_ids']
    if len(x) != len(set(x)) or len(y) != len(set(y)) or set(x) != set(y):
        return result
    result['status'] = 'comparable'
    result['scope'] = a['scope']
    n = len(x)
    if n < 2:
        return result
    positions = {value: i for i, value in enumerate(y)}
    inverted = sum(positions[x[i]] > positions[x[j]] for i in range(n) for j in range(i+1, n))
    left, right = set(zip(x, x[1:])), set(zip(y, y[1:]))
    pairs = n*(n-1)//2
    result.update(pairs_inverted=inverted, pairs_evaluated=pairs, precedence_disagreement=inverted/pairs,
                  successor_intersection=len(left & right), successor_union=len(left | right),
                  successor_jaccard=len(left & right)/len(left | right))
    return result


def summarize_coverage(predictions):
    counts = Counter(p['status'] for p in predictions)
    return dict(expected=len(predictions), produced_valid=counts['PASS'], failed=counts['FAIL'],
                unsupported=counts['UNSUPPORTED'], not_run=counts['NOT_RUN'])


def analyze_run(run_path, output):
    run_path, output = Path(run_path), Path(output)
    run = json.loads((run_path/'manifest.json').read_text())
    control = {json.dumps(p['scope'], sort_keys=True): p for p in run['predictions'] if p['candidate_id'] == 'docling'}
    rows = []
    for pred in run['predictions']:
        if pred['candidate_id'] == 'docling':
            continue
        baseline = control.get(json.dumps(pred['scope'], sort_keys=True))
        metric = compare_pair(pred, baseline) if baseline else {'status': 'not_comparable', 'metric_kind': 'agreement'}
        rows.append(dict(candidate_id=pred['candidate_id'], paper_id=pred['scope']['paper_id'], **metric))
    per_doc = defaultdict(list)
    for row in rows:
        if row.get('precedence_disagreement') is not None:
            per_doc[(row['candidate_id'], row['paper_id'])].append(row['precedence_disagreement'])
    report = dict(schema='reading-order-agreement/1', run_id=run['run_id'], input_profile_id=run['input_profile_id'],
                  coverage=summarize_coverage(run['predictions']), comparisons=rows,
                  document_means=[dict(candidate_id=c, paper_id=p, mean_disagreement=sum(v)/len(v), measured_scopes=len(v))
                                  for (c,p),v in per_doc.items()], selection='selection_pending')
    output.mkdir(parents=True, exist_ok=False)
    (output/'agreement.json').write_text(json.dumps(report, indent=2))
    fields = ['candidate_id','paper_id','status','precedence_disagreement','successor_jaccard','pairs_evaluated']
    with (output/'agreement.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    return report
