"""Build library-comparison figures from preserved evidence, without engines."""
import json
from pathlib import Path
from collections import Counter, defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

from pairwise_analysis import sha, write_csv
from reading_order.ingest import portable_reference, resolve_reference

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/assets'
OUTPUT = ROOT / 'raw_results/analytics_results/library-comparison-20261102'
NAMES = {'hantian': 'Hantian', 'docling': 'Docling', 'xycut_plus_plus': 'XY-Cut++*',
         'xycut': 'XY-Cut', 'pp_doclayout_v2': 'PP-DocLayoutV2', 'doctr': 'docTR'}
CASES = [('1', 0, 'First page, title and metadata'), ('2', 2, 'Columns and interleaved figures'),
         ('5', 2, 'Tables, text and charts'), ('9', 10, 'Closing text and references'),
         ('2', 10, 'Two-column references'), ('8', 18, 'Dense body text'),
         ('17', 21, 'Single column, image and heading')]
FAMILIES = {
    'Title/section': {'doc_title', 'paragraph_title'}, 'Text': {'text'},
    'Visual/table': {'image', 'chart', 'table'}, 'References': {'ref_text'},
    'Header': {'header'}, 'Footer/number': {'footer', 'page_number', 'page_footnote'}}


def generate():
    run_path = ROOT / 'raw_results/code_results/collection-20261102-delivery/canonical/manifest.json'
    base_path = ROOT / 'raw_results/analytics_results/collection-all-pairs-20261102/analysis.json'
    run = json.loads(run_path.read_text())
    base = json.loads(base_path.read_text())
    refs = [dict(r,path=portable_reference(r['path'])) for r in base['provenance']['sources']]
    refs.append(dict(path=portable_reference(base_path), sha256=sha(base_path)))
    if not all(sha(r['path']) == r['sha256'] for r in refs):
        raise ValueError('Preserved source changed')
    ASSETS.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    candidates = run['candidate_ids']
    names = [NAMES[c] for c in candidates]
    source_root = resolve_reference(base['provenance']['source_root_override'])
    documents = {d['paper_id']: d for d in run['input_reference']['documents']}
    raw = {paper: json.loads((source_root / paper / 'normalized.json').read_text()) for paper in documents}
    by_id = {x['id']: x for rows in raw.values() for x in rows}
    predictions = {(p['scope']['paper_id'], p['scope']['page_idx'], p['candidate_id']): p for p in run['predictions']}
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    generated = []

    def save(fig, name, vector=True):
        for suffix in (['png', 'svg'] if vector else ['png']):
            target = ASSETS / f'{name}.{suffix}'
            fig.savefig(target, dpi=180, bbox_inches='tight')
            generated.append(dict(path=portable_reference(target), sha256=sha(target)))
        plt.close(fig)

    costs = {x['candidate_id']: x for x in base['saved_costs']}
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), layout='constrained')
    for ax, metric, factor, title in zip(axes,
        ['adapter_total_s', 'peak_sampled_rss_bytes', 'peak_sampled_gpu_bytes'],
        [1000, 1 / 2**20, 1 / 2**20],
        ['Adapter time: median and IQR (ms)', 'Process/tree RAM: median (MiB)', 'GPU attributed to PID: median (MiB)']):
        for i, c in enumerate(candidates):
            value = costs[c][metric]
            if value['median'] is None:
                ax.text(.02, i, 'Not measured / not attributed', va='center', fontsize=8,
                        transform=ax.get_yaxis_transform())
            else:
                median = value['median'] * factor
                ax.barh(i, median, color='#386b86')
                if metric == 'adapter_total_s':
                    ax.errorbar(median, i, xerr=[[median-value['q1']*factor], [value['q3']*factor-median]],
                                color='black', capsize=3)
                ax.text(median, i, f' {median:.2f} (n={value["n"]})', va='center', fontsize=8)
        ax.set(yticks=range(6), yticklabels=names, title=title)
        ax.set_ylim(5.6, -.6)
        ax.set_xlim(0, ax.get_xlim()[1] * 1.4)
    fig.suptitle('Observed cost by library | A100, shared environment; not minimum requirements')
    save(fig, 'library_costs')

    historical_path = ROOT / 'raw_results/analytics_results/stability-12-completed-20261102/stability.json'
    corrected_path = ROOT / 'raw_results/analytics_results/docling-hantian-validation-20261102/analysis.json'
    historical = json.loads(historical_path.read_text())
    corrected = json.loads(corrected_path.read_text())
    stability = {x['candidate_id']: x['changed_orders'] for x in historical['per_candidate']}
    stability['docling'] = corrected['docling']['changed_permutations']
    fig, ax = plt.subplots(figsize=(10, 4), layout='constrained')
    bars = ax.bar(names, [stability[c] for c in candidates], color='#386b86')
    ax.bar_label(bars, labels=[f'{stability[c]}/26' for c in candidates], padding=3)
    ax.set(ylim=(0, 30), ylabel='Orders changed after input permutation',
           title='Observed stability by library: 12.pdf only, two permutations of 13 pages')
    ax.tick_params(axis='x', rotation=15)
    save(fig, 'library_stability')

    positions = defaultdict(list)
    eligible_counts = Counter()
    for p in run['predictions']:
        order = p['ordered_ids']
        if len(order) < 2:
            continue
        for rank, entity in enumerate(order):
            label = by_id[entity]['raw_label']
            for family, labels in FAMILIES.items():
                if label in labels:
                    positions[(p['candidate_id'], family)].append(rank / (len(order) - 1))
            if p['candidate_id'] == candidates[0]:
                eligible_counts[label] += 1
    fig, ax = plt.subplots(figsize=(11, 4.5), layout='constrained')
    values = [[float(np.median(positions[(c, f)])) if positions[(c, f)] else np.nan for f in FAMILIES] for c in candidates]
    im = ax.imshow(values, vmin=0, vmax=1, cmap='viridis', aspect='auto')
    for i, row in enumerate(values):
        for j, value in enumerate(row):
            ax.text(j, i, 'N/A' if np.isnan(value) else f'{value:.2f}', ha='center', va='center',
                    color='white' if value < .5 else 'black')
    ax.set(yticks=range(6), yticklabels=names, xticks=range(6), xticklabels=list(FAMILIES),
           title='Median relative position of each family by library (0=start; 1=end)')
    fig.colorbar(im, ax=ax)
    save(fig, 'library_category_positions')
    from pairwise_analysis import write_heatmaps
    write_heatmaps(base, ASSETS)
    for filename in ['matrices.png', 'matrices.svg']:
        generated.append(dict(path=portable_reference(ASSETS / filename), sha256=sha(ASSETS / filename)))
    fig, ax = plt.subplots(figsize=(11, 4.5), layout='constrained')
    for pair in base['pair_summaries']:
        if 'docling' not in (pair['candidate_a'], pair['candidate_b']):
            continue
        c = pair['candidate_b'] if pair['candidate_a'] == 'docling' else pair['candidate_a']
        docs = sorted(pair['document_means'], key=lambda x: int(x['paper_id']))
        ax.plot([d['paper_id'] for d in docs], [d['precedence_disagreement'] for d in docs], marker='o', label=NAMES[c])
    ax.set(ylabel='Mean precedence disagreement', xlabel='Paper ID (not chronological)', ylim=(0, .65),
           title='Per-document behavior against the Docling control; not an error rate')
    ax.legend(ncol=3)
    save(fig, 'library_document_comparison')

    cases = []
    for number, (paper, page, topic) in enumerate(CASES, 1):
        image = source_root.parents[1] / 'viewer_source/pages' / documents[paper]['paper_sha256'] / f'{page}.png'
        background = plt.imread(image)
        fig, axes = plt.subplots(2, 3, figsize=(15, 15))
        fig.subplots_adjust(left=.01, right=.99, bottom=.02, top=.92, wspace=.05, hspace=.12)
        orders = {}
        for ax, c in zip(axes.flat, candidates):
            ax.imshow(background, extent=(0, 1, 1, 0))
            order = predictions[(paper, page, c)]['ordered_ids']
            orders[c] = order
            for rank, entity in enumerate(order):
                x1, y1, x2, y2 = by_id[entity]['bbox_normalized']
                ax.add_patch(Rectangle((x1, y1), x2-x1, y2-y1, ec='#00759b', fill=False, lw=.6))
                ax.text(x1, y1, str(rank+1), fontsize=8, color='#ae1710',
                        bbox=dict(facecolor='white', edgecolor='none', alpha=.9, pad=.4))
                if rank:
                    prev = by_id[order[rank-1]]['bbox_normalized']
                    ax.annotate('', xy=((x1+x2)/2, (y1+y2)/2),
                                xytext=((prev[0]+prev[2])/2, (prev[1]+prev[3])/2),
                                arrowprops=dict(arrowstyle='->', lw=.7, color='#b34017', alpha=.65))
            ax.set(xlim=(0, 1), ylim=(1, 0));ax.axis('off')
            ax.set_title(NAMES[c], fontsize=12, fontweight='bold', pad=8)
        fig.suptitle(f'C{number:02}: {paper}.pdf / page {page+1} — {topic}\n'
                     'Agent visual comparison; same content and boxes. Numbering = saved order.')
        save(fig, f'case_{number:02}', vector=False)
        cases.append(dict(case_id=f'C{number:02}', paper_id=paper, page_number=page+1, purpose=topic,
                          background=dict(path=portable_reference(image), sha256=sha(image)), orders=orders,
                          units=[dict(id=x, raw_label=by_id[x]['raw_label'], bbox=by_id[x]['bbox_normalized'],
                                      source_ref=by_id[x]['original_ref']) for x in orders[candidates[0]]]))
    evidence = dict(schema='reading-order-library-comparison/1', candidates=candidates,
                    observed_costs=base['saved_costs'], stability_changed=stability, stability_denominator=26,
                    family_positions=[dict(candidate=c, family=f, n=len(positions[(c, f)]),
                                           median=float(np.median(positions[(c, f)])) if positions[(c, f)] else None)
                                      for c in candidates for f in FAMILIES],
                    eligible_labels=dict(eligible_counts), cases=cases,
                    provenance=dict(sources=refs+[dict(path=portable_reference(p), sha256=sha(p)) for p in [historical_path, corrected_path]],
                                    code_sha256=sha(__file__), figures=generated,
                                    models_executed=False, human_reviews_written=False))
    if not all(sha(r['path']) == r['sha256'] for r in refs):
        raise ValueError('Source changed during export')
    (OUTPUT / 'evidence.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding='utf-8')
    write_csv(OUTPUT / 'category_positions.csv', evidence['family_positions'], ['candidate', 'family', 'n', 'median'])
    print(json.dumps(dict(output=str(OUTPUT), assets=str(ASSETS), figures=sum(Path(f['path']).suffix == '.png' for f in generated), cases=len(cases))))


if __name__ == '__main__':
    generate()
