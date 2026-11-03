"""All-pairs descriptive analysis of saved predictions. Never imports engines."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
from reading_order.contracts import CANDIDATES, identity
from reading_order.ingest import Ingestor, LocalReferences, portable_reference, resolve_reference
from compare_orders import compare_pair

METRICS = ('precedence_disagreement', 'successor_jaccard', 'exact_match')


def sha(path):
    return hashlib.sha256(resolve_reference(path).read_bytes()).hexdigest()


def load_saved_inventory(run, source_root):
    """Resolve existing JSON, check frozen identity, SHA256s and exclusions."""
    frozen = run['input_reference']
    payload = {k: v for k, v in frozen.items() if k != 'input_profile_id'}
    if identity(payload) != frozen['input_profile_id'] or run['input_profile_id'] != frozen['input_profile_id']:
        raise ValueError('Frozen input identity mismatch')
    source_root = resolve_reference(source_root)
    reader = Ingestor(LocalReferences(source_root))
    inventory, references = {}, []
    seen = set()
    for row in frozen['documents']:
        paper = row['paper_id']
        if paper in seen:
            raise ValueError('Duplicate input document')
        seen.add(paper)
        metadata = [dict(width=p.get('pdf_width', p['width']), height=p.get('pdf_height', p['height']),
                         rotation=p['rotation']) for p in row['pages']]
        doc = reader.read(paper, metadata if all(p['rotation'] is not None for p in row['pages']) else None,
                          expected=row)
        exclusions = [{'id': b.id, 'reason': b.exclusion} for b in doc.blocks if b.exclusion]
        if doc.paper_sha256 != row['paper_sha256'] or doc.pages != row['pages'] or exclusions != row['exclusions']:
            raise ValueError('Frozen document inventory mismatch')
        for name, key in [('normalized.json', 'normalized_sha256'), ('middle.json', 'middle_sha256')]:
            references.append(dict(path=portable_reference(Path(source_root) / paper / name), sha256=row[key]))
        for page in doc.pages:
            key = (paper, page['page_idx'])
            if key in inventory:
                raise ValueError('Duplicate input page')
            blocks = [b for b in doc.blocks if b.page_idx == page['page_idx'] and b.exclusion is None]
            inventory[key] = dict(ids=[b.id for b in blocks], raw_labels=[b.raw_label for b in blocks],
                                  layout='unknown', route='unknown')
    return inventory, references


def distribution(values):
    values = list(values)
    if not values:
        return dict(n=0, mean=None, median=None, q1=None, q3=None, min=None, max=None)
    quartiles = statistics.quantiles(values, n=4, method='inclusive') if len(values) > 1 else values * 3
    return dict(n=len(values), mean=statistics.mean(values), median=statistics.median(values),
                q1=quartiles[0], q3=quartiles[2], min=min(values), max=max(values))


def summarize(rows, expected_documents):
    valid = [r for r in rows if r['precedence_disagreement'] is not None]
    by_document = defaultdict(list)
    for row in valid:
        by_document[row['paper_id']].append(row)
    documents = []
    for paper, group in sorted(by_document.items()):
        documents.append(dict(paper_id=paper, evaluated=len(group), **{
            key: statistics.mean(r[key] for r in group) for key in METRICS}))
    totals = {key: sum(r[key] for r in valid) for key in
              ('pairs_inverted', 'pairs_evaluated', 'successor_intersection', 'successor_union')}
    return dict(
        coverage=dict(expected=len(rows), comparable=sum(r['status'] == 'comparable' for r in rows),
                      evaluated=len(valid), degenerate=sum(r['reason'] == 'fewer_than_two_blocks' for r in rows),
                      not_comparable=sum(r['status'] != 'comparable' for r in rows),
                      documents_expected=expected_documents, documents_evaluated=len(documents)),
        macro={key: statistics.mean(d[key] for d in documents) if documents else None for key in METRICS},
        micro=dict(precedence_disagreement=totals['pairs_inverted'] / totals['pairs_evaluated']
                   if totals['pairs_evaluated'] else None,
                   successor_jaccard=totals['successor_intersection'] / totals['successor_union']
                   if totals['successor_union'] else None,
                   exact_match=sum(r['exact_match'] for r in valid) / len(valid) if valid else None),
        totals=dict(**totals, exact_matches=sum(r['exact_match'] for r in valid), exact_evaluated=len(valid)),
        document_means=documents,
        distributions={key: dict(scope=distribution(r[key] for r in valid),
                                 document=distribution(d[key] for d in documents)) for key in METRICS})


def validate_saved_prediction(pred, ids, run):
    if pred is None:
        return ['missing_prediction']
    if pred['status'] != 'PASS':
        return [pred['status']]
    errors = []
    scope = pred['scope']
    if scope['input_profile_id'] != run['input_profile_id'] or scope['eligible_ids_hash'] != identity(sorted(ids)):
        errors.append('scope_identity_mismatch')
    if scope.get('route') is not None or scope.get('permutation_seed') is not None:
        errors.append('not_primary_full_page_scope')
    order = pred.get('ordered_ids')
    if not isinstance(order, list) or not all(isinstance(x, str) for x in order):
        return errors + ['invalid_order_type']
    if len(set(order)) != len(order):
        errors.append('duplicate_ids')
    if set(order) != set(ids):
        errors.append('eligible_ids_mismatch')
    return errors


def analyze_predictions(run, inventory):
    """Pure analysis: every expected page remains in each pair's denominator."""
    candidates = run['candidate_ids']
    if len(candidates) != 6 or set(candidates) != set(CANDIDATES):
        raise ValueError('Expected the six registered candidates')
    index = {}
    for pred in run['predictions']:
        key = (pred['scope']['paper_id'], pred['scope']['page_idx'])
        if key not in inventory or pred['candidate_id'] not in candidates:
            raise ValueError('Unknown candidate or page scope')
        item = (pred['candidate_id'], *key)
        if item in index:
            raise ValueError('Duplicate candidate/page prediction')
        index[item] = pred
    contracts = {p.get('transformations', {}).get('cid_contract') for p in run['predictions']
                 if p['candidate_id'] == 'docling' and p['status'] == 'PASS' and p.get('ordered_ids')}
    if len(contracts) > 1 or (contracts and None in contracts):
        raise ValueError('Missing or mixed Docling CID contracts')
    validation = {}
    integrity_rows = []
    for (paper, page), source in inventory.items():
        for candidate in candidates:
            pred = index.get((candidate, paper, page))
            errors = validate_saved_prediction(pred, source['ids'], run)
            validation[(candidate, paper, page)] = errors
            order = pred.get('ordered_ids') if pred else None
            seq = order if isinstance(order, list) and all(isinstance(x, str) for x in order) else []
            integrity_rows.append(dict(candidate_id=candidate, paper_id=paper, page_idx=page,
                                       status=pred['status'] if pred else 'MISSING', errors=errors,
                                       expected_ids=len(source['ids']),
                                       missing_ids=sorted(set(source['ids']) - set(seq)),
                                       extra_ids=sorted(set(seq) - set(source['ids'])),
                                       duplicate_ids=sorted(x for x, n in Counter(seq).items() if n > 1)))
    common = {key for key in inventory if all(not validation[(c, *key)] for c in candidates)}
    comparisons = []
    for a, b in combinations(candidates, 2):
        for (paper, page), source in sorted(inventory.items()):
            left, right = index.get((a, paper, page)), index.get((b, paper, page))
            errors = {c: validation[(c, paper, page)] for c in (a, b) if validation[(c, paper, page)]}
            metric = compare_pair(left, right) if not errors else dict(
                status='not_comparable', metric_kind='agreement', precedence_disagreement=None,
                successor_jaccard=None, pairs_inverted=0, pairs_evaluated=0,
                successor_intersection=0, successor_union=0)
            n = len(source['ids'])
            valid = metric['status'] == 'comparable' and n >= 2
            ea = set(zip(left['ordered_ids'], left['ordered_ids'][1:])) if valid else set()
            eb = set(zip(right['ordered_ids'], right['ordered_ids'][1:])) if valid else set()
            comparisons.append(dict(
                **metric, candidate_a=a, candidate_b=b, paper_id=paper, page_idx=page, n_blocks=n,
                reason='invalid_prediction' if errors else ('fewer_than_two_blocks' if n < 2 else None),
                validation_errors=errors, common_six=(paper, page) in common,
                exact_match=(left['ordered_ids'] == right['ordered_ids']) if valid else None,
                successors_only_a=[list(e) for e in sorted(ea - eb)],
                successors_only_b=[list(e) for e in sorted(eb - ea)],
                layout=source.get('layout', 'unknown'), route=source.get('route', 'unknown'),
                visual_elements=any(label in ('image', 'chart', 'table') for label in source['raw_labels'])))
    papers = {key[0] for key in inventory}
    pairs = []
    strata = []
    for a, b in combinations(candidates, 2):
        rows = [r for r in comparisons if (r['candidate_a'], r['candidate_b']) == (a, b)]
        pairs.append(dict(candidate_a=a, candidate_b=b, **summarize(rows, len(papers)),
                          common_scopes=summarize([r for r in rows if r['common_six']], len(papers))))
        for attribute in ('n_blocks', 'visual_elements', 'layout', 'route'):
            for value in sorted({r[attribute] for r in rows}, key=str):
                group = [r for r in rows if r[attribute] == value]
                strata.append(dict(candidate_a=a, candidate_b=b, attribute=attribute, value=value,
                                   **summarize(group, len({r['paper_id'] for r in group}))))
    matrices = {key: [[None] * 6 for _ in candidates] for key in METRICS}
    for i in range(6):
        for key in METRICS:
            matrices[key][i][i] = 0 if key == 'precedence_disagreement' else 1
    for row in pairs:
        i, j = candidates.index(row['candidate_a']), candidates.index(row['candidate_b'])
        for key in METRICS:
            matrices[key][i][j] = matrices[key][j][i] = row['macro'][key]
    costs = []
    for c in candidates:
        saved = [p.get('costs', {}) for p in run['predictions'] if p['candidate_id'] == c and p['status'] == 'PASS']
        costs.append(dict(candidate_id=c, recorded_predictions=len(saved), **{
            key: distribution(x[key] for x in saved if isinstance(x.get(key), (int, float)))
            for key in ('adapter_total_s', 'peak_sampled_rss_bytes', 'peak_sampled_gpu_bytes',
                        'load_s', 'inference_s', 'decode_s')}))
    return dict(schema='reading-order-all-pairs/1', metric_kind='agreement',
                candidates=candidates, docling_cid_contract=next(iter(contracts), None),
                scope_kind='saved_primary_full_page', selection='selection_pending', human_review='pending',
                integrity=dict(expected=len(inventory) * 6, saved=len(run['predictions']),
                               invalid=sum(bool(r['errors']) for r in integrity_rows),
                               statuses=dict(Counter(r['status'] for r in integrity_rows)), cases=integrity_rows),
                common_scope_coverage=dict(expected=len(inventory), comparable=len(common),
                                           evaluated=sum(len(inventory[k]['ids']) >= 2 for k in common)),
                comparisons=comparisons, pair_summaries=pairs, matrices=matrices, strata=strata,
                saved_costs=costs, limitations=[
                    'Agreement is not semantic accuracy; no ground truth or winner.',
                    'No explicit route/group/column annotations: only saved full-page sequences are compared.',
                    'visual_elements means raw image/chart/table labels, not validated layout complexity.',
                    'Costs are saved adapter totals and sampled process-tree memory, not pure inference or guaranteed peaks.',
                    'No new stability experiment; previously saved stability audits retain their own scope and CID contract.'])


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                             for k, v in row.items() if k in fields})


def write_heatmaps(report, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    labels = ['Hantian', 'Docling', 'XY-Cut++*', 'XY-Cut', 'PP-DocLayoutV2', 'docTR']
    labels = [dict(zip(CANDIDATES, labels))[c] for c in report['candidates']]
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), layout='constrained')
    for ax, key, title in zip(axes, METRICS[:2], ['Precedence disagreement D', 'Successor Jaccard J']):
        values = np.array(report['matrices'][key], dtype=float)
        plot = ax.imshow(values, vmin=0, vmax=1, cmap='viridis')
        ax.set(xticks=range(6), yticks=range(6), xticklabels=labels, yticklabels=labels, title=title)
        plt.setp(ax.get_xticklabels(), rotation=40, ha='right')
        for i in range(6):
            for j in range(6):
                text = 'NA' if np.isnan(values[i, j]) else f'{values[i, j]:.3f}'
                ax.text(j, i, text, ha='center', va='center', color='black' if values[i, j] > .55 else 'white')
        fig.colorbar(plot, ax=ax, shrink=.75)
    fig.suptitle('Saved reading orders: equal document weight; agreement is not accuracy\n'
                 '* XY-Cut++ home-still variant. Diagonal is identity, not a measurement.')
    fig.savefig(output / 'matrices.png', dpi=180)
    fig.savefig(output / 'matrices.svg')
    plt.close(fig)


def analyze_saved_run(run_path, output, source_root):
    run_path, output = Path(run_path).resolve(), Path(output).resolve()
    source_root = resolve_reference(source_root, relative_to=Path.cwd())
    if output == run_path or output.is_relative_to(run_path) or output == source_root or output.is_relative_to(source_root):
        raise ValueError('Output must be outside source directories')
    manifest_path = run_path / 'manifest.json'
    manifest_hash = sha(manifest_path)
    run = json.loads(manifest_path.read_text(encoding='utf-8'))
    inventory, references = load_saved_inventory(run, source_root)
    report = analyze_predictions(run, inventory)
    protected = [dict(path=portable_reference(manifest_path), sha256=manifest_hash), *references]
    report['provenance'] = dict(run_id=run['run_id'], input_profile_id=run['input_profile_id'],
                                created_utc=datetime.now(timezone.utc).isoformat(),
                                sources=protected, code=[dict(path=portable_reference(__file__), sha256=sha(__file__)),
                                dict(path=portable_reference(ROOT / 'analytics/compare_orders.py'), sha256=sha(ROOT / 'analytics/compare_orders.py'))],
                                source_root_override=portable_reference(source_root),
                                frozen_source_root=run['input_reference']['source_root'],
                                models_executed=False, human_reviews_written=False,
                                quartiles='linear interpolation, inclusive endpoints')
    # Verify again before publishing. No writes inside any input/result source folder.
    if any(sha(row['path']) != row['sha256'] for row in protected):
        raise ValueError('Source changed during analysis')
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / 'comparisons.csv', report['comparisons'],
              ['candidate_a', 'candidate_b', 'paper_id', 'page_idx', 'status', 'reason', 'n_blocks',
               *METRICS, 'pairs_inverted', 'pairs_evaluated', 'successor_intersection', 'successor_union',
               'common_six', 'layout', 'route', 'visual_elements', 'successors_only_a', 'successors_only_b'])
    summaries = [dict(candidate_a=p['candidate_a'], candidate_b=p['candidate_b'],
                      **{f'macro_{k}': v for k, v in p['macro'].items()},
                      **{f'micro_{k}': v for k, v in p['micro'].items()}, **p['coverage'], **p['totals'])
                 for p in report['pair_summaries']]
    write_csv(output / 'pair_summaries.csv', summaries, list(summaries[0]))
    docs = [dict(candidate_a=p['candidate_a'], candidate_b=p['candidate_b'], **d)
            for p in report['pair_summaries'] for d in p['document_means']]
    write_csv(output / 'document_means.csv', docs, ['candidate_a', 'candidate_b', 'paper_id', 'evaluated', *METRICS])
    for metric in METRICS:
        write_csv(output / f'matrix_{metric}.csv',
                  [dict(candidate_id=c, **dict(zip(report['candidates'], values)))
                   for c, values in zip(report['candidates'], report['matrices'][metric])],
                  ['candidate_id', *report['candidates']])
    write_heatmaps(report, output)
    report['provenance']['sources_unchanged'] = all(sha(r['path']) == r['sha256'] for r in protected)
    if not report['provenance']['sources_unchanged']:
        raise ValueError('Source changed during export')
    (output / 'analysis.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze_saved_run(args.run, args.output, args.source_root)
    print(json.dumps(dict(output=str(args.output), pairs=len(result['pair_summaries']),
                          coverage=result['common_scope_coverage'], integrity_invalid=result['integrity']['invalid'],
                          sources_unchanged=result['provenance']['sources_unchanged'], selection=result['selection'])))
