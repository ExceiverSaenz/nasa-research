"""Run only the automatic phases of docs/methodology/analysis-plan.md. No parser imports/network."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path, authored_report_path
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from itertools import combinations
import json
from pathlib import Path
import re
import sys
import time

from analytics.automatic import core
TOOLS = ('heron', 'heron101', 'basic', 'standard')
PROTOCOL = dict(version='bbox-offline-analysis/1', iou_threshold=.5,
                candidate_edges='all_positive_intersections_same_page',
                quantiles='linear_index_(n-1)*p', iqr_multiplier=1.5, iqr_min_n=20,
                geometry_strata=['tool', 'raw_label', 'native_level'],
                review_order='all_pages_by_paper; diagnostic_alerts_listed_not_quality_ranked',
                templates=['G1', 'G2', 'G3', 'G4', 'G5'],
                label_comparison='literal_only; cross_schema_candidates_partial_not_equivalences',
                human_review='pending', accuracy_metrics='unavailable_without_reference',
                new_parsing=False, network=False, new_renders=False)


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def write_csv(path, rows, fields):
    with Path(path).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def json_line(f, data):
    f.write(json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n')


class Sources:
    def __init__(self, project):
        self.project = Path(project).resolve()
        self.hashes = {}
        self.purposes = defaultdict(set)

    def track(self, path, purpose, expected=None):
        p = resolve_path(path).resolve()
        if not p.is_relative_to(self.project):
            raise ValueError('Input escapes project: '+str(p))
        if p not in self.hashes:
            self.hashes[p] = core.sha256(p)
        self.purposes[p].add(purpose)
        if expected and self.hashes[p] != expected:
            raise ValueError('Input SHA256 mismatch: '+str(p))
        return p

    def load(self, path, purpose, expected=None):
        return json.loads(self.track(path, purpose, expected).read_text(encoding='utf-8-sig'))

    def records(self):
        return [dict(path=str(p), sha256=sha, bytes=p.stat().st_size,
                     purposes=sorted(self.purposes[p])) for p, sha in sorted(self.hashes.items())]


def native_level(row):
    if row['raw_label'] in ('equation_inline', 'hyperlink'):
        return 'inline'
    return 'child' if '/content/' in row['original_ref'].partition('#')[2] else 'block'


def label_category(label):
    groups = {'heading_candidate': {'title', 'section_header', 'doc_title', 'paragraph_title'},
              'caption_candidate': {'caption', 'image_caption', 'chart_caption', 'table_caption'},
              'visual_candidate': {'image', 'chart', 'picture'},
              'text_general': {'text'}, 'equation_candidate': {'equation', 'formula', 'equation_inline'},
              'table_candidate': {'table'}, 'list_item_candidate': {'list_item'}}
    return next((name for name, labels in groups.items() if label in labels), 'unmapped')


def environment_versions(sources, run_root):
    path = run_root/'download'/'provenance'/'runtime'/'environment-receipt.json'
    if not path.exists():
        return {}
    env = sources.load(path, 'attempt_environment_versions')
    versions = {}
    for name in ('a', 'b'):
        packages = {}
        for check in env.get(name, {}).get('checks', []):
            packages.update(check.get('evidence', {}).get('packages', {}))
        versions[name] = {k: packages.get(k) for k in ('docvortex','mineru','torch','vllm')}
        versions[name]['evidence'] = str(path)
    return versions


def failure_history(sources, source, provenance, receipts, expected):
    failures, rates, seen = [], [], set()
    selected_env = environment_versions(sources, source)
    for tool in TOOLS:
        run_id = provenance[tool]['run_id']
        versions = selected_env.get('b' if tool=='standard' else 'a', {}) if not provenance[tool].get('reused_not_executed') else {}
        if provenance[tool].get('docvortex'):
            versions = {**versions, 'docvortex': provenance[tool]['docvortex'], 'evidence': str(source/'tool-provenance.json')}
        fs, rate = core.attempt_failures(receipts[tool], tool, run_id, versions, expected)
        failures.extend(fs); rates.append(rate); seen.add((run_id, tool))
    for run_id in sorted({p['run_id'] for p in provenance.values()}-{source.name}):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
            raise ValueError('Invalid attempt identity')
        prior = source.parent/run_id
        archive = prior/'download'
        manifest = sources.load(archive/'manifest.json', 'historical_archive_manifest')
        env = environment_versions(sources, prior)
        for tool in TOOLS:
            if (run_id, tool) in seen:
                continue
            rel = 'results/assembled-v1/'+tool+'/receipt.json'
            identity = manifest[rel]
            receipt = sources.load(archive/rel, 'historical_assembled_receipt', identity['sha256'])
            fs, rate = core.attempt_failures(receipt, tool, run_id, env.get('b' if tool=='standard' else 'a', {}), expected)
            for entry in fs:
                entry['receipt_path'] = str(archive/rel)
            failures.extend(fs); rates.append(rate); seen.add((run_id, tool))
    return failures, rates


def execute(source, inventory_path, project, plan, experiment, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    project = Path(project).resolve()
    if output.exists():
        raise FileExistsError('Analysis destination already exists; never overwrite: '+str(output))
    if not output.is_relative_to(project) or output == project:
        raise ValueError('Output must be a new directory inside project')
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Output and preserved inputs must be separate')
    started = time.perf_counter()
    sources = Sources(project)
    for code in Path(__file__).resolve().parent.glob('*.py'):
        # Protect implementation files located inside the selected project.
        if code.is_relative_to(project):
            sources.track(code, 'analysis_implementation')
    sources.track(plan, 'analysis_plan')
    inventory = sources.load(inventory_path, 'pdf_inventory')
    config = sources.load(experiment, 'experiment_configuration')
    if config.get('iou_threshold') != .5 or config.get('resource_interval_s') != 1:
        raise ValueError('Configuration differs from frozen plan')
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(analysis_id=output.name, created_utc=datetime.now(timezone.utc).isoformat(),
                    plan_path=str(Path(plan).resolve()), plan_sha256=core.sha256(plan),
                    source_root=str(source), protocol=PROTOCOL, status='running',
                    authorization='automatic_only; visual_review_deferred', phases={'F0': 'complete'})
    write_json(output/'analysis_manifest.json', manifest)
    write_json(output/'label_map_spec.json', dict(policy=PROTOCOL['label_comparison'],
               source='frozen analysis implementation and plan section 3.3',
               candidates={name: label_category(name) for name in (
                   'title','section_header','doc_title','paragraph_title','caption','image_caption',
                   'chart_caption','table_caption','image','chart','picture','text','equation',
                   'formula','equation_inline','table','list_item')}, default='unmapped',
               correspondence_status='partial; no semantic correctness inferred'))
    try:
        return _execute(source, output, project, sources, inventory, manifest, started)
    except Exception as exc:
        manifest.update(status='failed_preserving_partial_evidence', failure_type=type(exc).__name__, failure=str(exc))
        write_json(output/'analysis_manifest.json', manifest)
        raise


def _execute(source, output, project, sources, inventory, manifest, started):
    final = sources.load(source/'final-status.json', 'source_status')
    provenance = sources.load(source/'tool-provenance.json', 'tool_provenance')
    metrics = sources.load(source/'metrics.json', 'preserved_metrics')
    sources.load(source/'verification.json', 'preserved_verification')
    lineage = sources.load(source/'background-lineage.json', 'background_identity')
    viewer = sources.load(source/'viewer_source'/'viewer.json', 'existing_background_index')
    prior_review = source/'viewer'/'reviews.json'
    if prior_review.exists():
        sources.track(prior_review, 'protected_existing_reviews_not_imported')
    if set(provenance) != set(TOOLS) or len({p['name'] for p in inventory}) != len(inventory):
        raise ValueError('Invalid tools or duplicate paper inventory')
    expected_pages = sum(p['pages'] for p in inventory)
    if (len(inventory), expected_pages, expected_pages*4) != (final['papers'], final['pages'], final['successful_tool_page_outputs']):
        raise ValueError('Source metadata and inventory coverage disagree')
    page_assets = {(p['paper_sha256'], p['page_idx']): p for p in viewer['pages']}
    if len(page_assets) != expected_pages or len(viewer['pages']) != expected_pages:
        raise ValueError('Missing or duplicate viewer pages')
    print('F0 frozen; F1 verifying receipts, native files, PDFs and existing backgrounds.', flush=True)
    receipts, by_paper = {}, {}
    for tool in TOOLS:
        receipt = sources.load(source/'assembled'/tool/'receipt.json', 'tool_receipt', provenance[tool]['receipt_sha256'])
        receipts[tool] = receipt
        entries = {e['paper']: e for e in receipt['results']}
        if len(entries) != len(receipt['results']) or set(entries) != {p['name'] for p in inventory}:
            raise ValueError('Incomplete or duplicate receipt papers: '+tool)
        by_paper[tool] = entries
        for paper in inventory:
            entry = entries[paper['name']]
            if entry['status'] != 'complete' or entry['result']['page_indices'] != list(range(paper['pages'])):
                raise ValueError('Technical page coverage mismatch: '+tool+'/'+paper['name'])
            folder = (source/'assembled'/tool/Path(paper['name']).stem).resolve()
            for rel, identity in entry['files'].items():
                path = (folder/rel).resolve()
                if not path.is_relative_to(folder):
                    raise ValueError('Receipt file escapes paper folder')
                sources.track(path, 'receipt_native_file', identity['sha256'])
                if path.stat().st_size != identity['bytes']:
                    raise ValueError('Receipt size mismatch: '+str(path))
        print('  verified '+tool, flush=True)
    for paper in inventory:
        pdf = sources.track(project/'papers'/'SiC_papers'/paper['name'], 'original_pdf', paper['sha256'])
        if pdf.stat().st_size != paper['bytes']:
            raise ValueError('PDF size mismatch')
        for idx in range(paper['pages']):
            asset = page_assets[(paper['sha256'], idx)]
            rel = asset['image']
            p = (source/'viewer_source'/rel).resolve()
            if not p.is_relative_to((source/'viewer_source').resolve()):
                raise ValueError('Background path escapes viewer')
            sources.track(p, 'existing_background', lineage['sha256'][rel])
    # Historic configurations are separate observations, never pooled with corrected results.
    failures, attempt_rates = failure_history(sources, source, provenance, receipts, len(inventory))
    manifest['phases']['F1'] = 'complete'
    manifest.update(papers=len(inventory), pages=expected_pages, tool_page_outputs=expected_pages*4,
                    source_run_by_tool={t: provenance[t]['run_id'] for t in TOOLS})
    write_json(output/'analysis_manifest.json', manifest)
    write_json(output/'input_manifest.json', sources.records())
    print('F1 complete; F2 computing per-page agreements and descriptors.', flush=True)
    counts, totals = Counter(), {t: Counter() for t in TOOLS}
    geometries = defaultdict(list)
    page_info, patterns, page_stats = [], [], {}
    source_map, native_cache, ref_file_cache = {}, {}, {}
    edge_count, component_count = 0, 0
    agreement_values = defaultdict(lambda: dict(ious=[], label_matches=0, label_evaluable=0,
                                               component_types=Counter()))
    geometry_rows = []
    with (output/'detections.jsonl').open('w', encoding='utf-8') as detected, \
         (output/'agreement_edges.jsonl').open('w', encoding='utf-8') as edge_file, \
         (output/'agreement_components.jsonl').open('w', encoding='utf-8') as group_file, \
         (output/'native_patterns.jsonl').open('w', encoding='utf-8') as pattern_file, \
         (output/'native_edges.jsonl').open('w', encoding='utf-8') as parent_file:
        for paper in inventory:
            page_rows = {i: {} for i in range(paper['pages'])}
            for tool in TOOLS:
                rows = sources.load(source/'assembled'/tool/Path(paper['name']).stem/'normalized.json', 'normalized_predictions')
                for ordinal, original in enumerate(rows):
                    row = dict(original)
                    if row['tool'] != tool or row['paper_sha256'] != paper['sha256'] or row['page_idx'] not in page_rows:
                        raise ValueError('Detection identity mismatch')
                    native_ref, _, fragment = row['original_ref'].replace('\\', '/').partition('#')
                    file_key = (native_ref, row['original_sha256'])
                    if file_key not in ref_file_cache:
                        path, _ = core.resolve_ref(source/'assembled', row['original_ref'], row['original_sha256'], sources.hashes)
                        sources.track(path, 'resolved_native_reference', row['original_sha256'])
                        ref_file_cache[file_key] = path
                    path = ref_file_cache[file_key]
                    if path not in native_cache:
                        native_cache[path] = json.loads(path.read_text(encoding='utf-8-sig'))
                    core.pointer(native_cache[path], fragment)
                    source_map[row['original_ref']] = dict(original_ref=row['original_ref'], local_path=str(path),
                                                          fragment=fragment, expected_sha256=row['original_sha256'],
                                                          verified_sha256=sources.hashes[path], status='verified')
                    uid = f"{provenance[tool]['run_id']}:{tool}:{paper['sha256']}:{row['page_idx']}:{row['id']}:{ordinal}"
                    row.update(analysis_uid=uid, source_run_id=provenance[tool]['run_id'], native_level=native_level(row))
                    state = core.box_state(row.get('bbox_normalized'))
                    row['analysis_geometry_state'] = state
                    json_line(detected, row)
                    counts[(tool, paper['name'], row['raw_label'], row['native_level'], state)] += 1
                    totals[tool]['rows'] += 1
                    totals[tool][state] += 1
                    totals[tool]['label:'+str(row['raw_label'])] += 1
                    page_rows[row['page_idx']].setdefault(tool, []).append(row)
                    if state == 'valid':
                        b = row['bbox_normalized']
                        features = dict(relative_width=b[2]-b[0], relative_height=b[3]-b[1], relative_area=core.area(b))
                        for feature, value in features.items():
                            geometries[(tool, row['raw_label'], row['native_level'], feature)].append((row, value, paper['name']))
            for idx, tools in page_rows.items():
                context = dict(paper=paper['name'], paper_sha256=paper['sha256'], page_idx=idx)
                stats = dict(context, tools={}, positive_overlap_edges=0, candidate_components=0, geometry_alerts=0,
                             page_case_inventory_complete=False, visual_review_status='not_reviewed')
                for tool in TOOLS:
                    rows = tools.get(tool, [])
                    native = core.native_patterns(rows)
                    item = dict(context, tool=tool, source_run_id=provenance[tool]['run_id'], **native)
                    json_line(pattern_file, item); patterns.append(item)
                    refs = {r['original_ref'] for r in rows}
                    for row in rows:
                        if row.get('native_parent_ref'):
                            json_line(parent_file, dict(context, tool=tool, child_uid=row['analysis_uid'],
                                      child_native_ref=row['original_ref'], parent_native_ref=row['native_parent_ref'],
                                      relation='native_content_membership', resolution='resolved' if row['native_parent_ref'] in refs else 'dangling',
                                      evidence_level='native_declared_not_semantically_reviewed'))
                    states = Counter(core.box_state(r.get('bbox_normalized')) for r in rows)
                    labels = Counter(r['raw_label'] for r in rows)
                    stats['tools'][tool] = dict(rows=len(rows), valid_bbox=states['valid'], missing_bbox=states['missing'],
                                              invalid_bbox=states['invalid'], raw_labels=dict(labels),
                                              native_parent_edges=native['parent_edges'], native_visual_caption_parents=native['visual_caption_parents'])
                    page_info.append(dict(context, tool=tool, source_run_id=provenance[tool]['run_id'], technical_status='complete',
                                          row_count=len(rows), valid_bbox=states['valid'], missing_bbox=states['missing'], invalid_bbox=states['invalid'],
                                          page_case_inventory_complete=False, visual_review_status='not_reviewed'))
                for ta, tb in combinations(TOOLS, 2):
                    left = [dict(r, id=r['analysis_uid']) for r in tools.get(ta, [])]
                    right = [dict(r, id=r['analysis_uid']) for r in tools.get(tb, [])]
                    edges, components = core.compare_page(left, right)
                    for edge in edges:
                        json_line(edge_file, dict(context, tool_a=ta, tool_b=tb, **edge))
                    for component in components:
                        json_line(group_file, dict(context, tool_a=ta, tool_b=tb, **component))
                    for key in ((paper['name'], ta, tb), ('ALL', ta, tb)):
                        acc = agreement_values[key]
                        acc['ious'].extend(e['iou'] for e in edges)
                        acc['label_matches'] += sum(e['literal_label_match'] is True for e in edges)
                        acc['label_evaluable'] += sum(e['literal_label_evaluable'] for e in edges)
                        for c in components:
                            acc['component_types'][('1' if c['n_a']==1 else 'n')+':'+('1' if c['n_b']==1 else 'm')] += 1
                    stats['positive_overlap_edges'] += len(edges); edge_count += len(edges)
                    stats['candidate_components'] += len(components); component_count += len(components)
                page_stats[(paper['sha256'], idx)] = stats
            native_cache.clear()
            print('  analyzed '+paper['name']+' ('+str(paper['pages'])+' pages)', flush=True)
    for tool in TOOLS:
        old = metrics['summary'][tool]
        actual_labels = {k[6:]: v for k, v in totals[tool].items() if k.startswith('label:')}
        if (totals[tool]['valid'], totals[tool]['missing']+totals[tool]['invalid'], actual_labels) != (old['bbox_rows'], old['rows_without_bbox'], old['raw_labels']):
            raise ValueError('Preserved metrics reconciliation failed: '+tool)
    geom_summary = []
    for (tool, label, level, feature), values in sorted(geometries.items()):
        summary = core.describe([v for _, v, _ in values])
        geom_summary.append(dict(tool=tool, raw_label=label, native_level=level, feature=feature, **summary))
        for row, value, paper_name in values:
            flagged = summary['iqr_rule_evaluable'] and (value < summary['lower_fence'] or value > summary['upper_fence'])
            if flagged:
                page_stats[(row['paper_sha256'], row['page_idx'])]['geometry_alerts'] += 1
            geometry_rows.append(dict(tool=tool, paper=paper_name, paper_sha256=row['paper_sha256'], page_idx=row['page_idx'],
                                      analysis_uid=row['analysis_uid'], raw_label=label, native_level=level, feature=feature, value=value,
                                      stratum_n=summary['n'], iqr_rule_evaluable=summary['iqr_rule_evaluable'],
                                      lower_fence=summary['lower_fence'], upper_fence=summary['upper_fence'],
                                      candidate_outlier=flagged, evidence_level='signal_not_error'))
    write_json(output/'source_map.json', list(source_map.values()))
    write_csv(output/'page_inventory.csv', page_info, list(page_info[0]))
    descriptive = [dict(tool=t, paper=p, raw_label=l, native_level=n, geometry_state=s, count=c)
                   for (t, p, l, n, s), c in sorted(counts.items())]
    write_csv(output/'descriptive_tables.csv', descriptive, ['tool', 'paper', 'raw_label', 'native_level', 'geometry_state', 'count'])
    write_csv(output/'geometry_summary.csv', geom_summary, list(geom_summary[0]) if geom_summary else ['tool','feature','n'])
    write_csv(output/'geometry_diagnostics.csv', geometry_rows, list(geometry_rows[0]) if geometry_rows else ['tool','feature','value'])
    agreement_summary = []
    for (paper_name, ta, tb), acc in sorted(agreement_values.items()):
        d = core.describe(acc['ious']); n = d['n']
        agreement_summary.append(dict(paper=paper_name, tool_a=ta, tool_b=tb, positive_overlap_edges=n,
            iou_median=d['median'], iou_p95=d['p95'],
            edges_iou_ge_05=sum(v >= .5 for v in acc['ious']),
            fraction_iou_ge_05_given_positive=sum(v >= .5 for v in acc['ious'])/n if n else None,
            literal_label_evaluable_edges=acc['label_evaluable'], literal_label_matching_edges=acc['label_matches'],
            literal_label_agreement_given_evaluable_overlap=acc['label_matches']/acc['label_evaluable'] if acc['label_evaluable'] else None,
            components_1_1=acc['component_types']['1:1'], components_1_m=acc['component_types']['1:m'],
            components_n_1=acc['component_types']['n:1'], components_n_m=acc['component_types']['n:m'],
            meaning='prediction_overlap_and_literal_labels_not_accuracy_or_semantic_equivalence'))
    write_csv(output/'agreement_summary.csv', agreement_summary, list(agreement_summary[0]))
    label_rows = [dict(tool=t, raw_label=l, native_level=n, category_candidate=label_category(l),
                       correspondence_status='partial' if label_category(l) != 'unmapped' else 'unmapped',
                       source='docs/methodology/analysis-plan.md section 3.3; native declared label',
                       semantic_correctness='not_reviewed; no_cross_schema_equivalence_claim')
                  for t, l, n in sorted({(t, l, n) for t, _, l, n, _ in counts})]
    write_csv(output/'label_map.csv', label_rows, list(label_rows[0]))
    manifest['phases']['F2'] = 'complete_automatic_signals_only'
    costs_paper, costs_stage, timings_page = [], [], []
    for tool in TOOLS:
        pc, sc = core.extract_cost(receipts[tool], tool, provenance[tool]['run_id'])
        costs_paper.extend(pc); costs_stage.append(sc)
        timings_page.extend(core.page_timing_observations(receipts[tool], tool, provenance[tool]['run_id']))
    write_csv(output/'cost_by_paper.csv', costs_paper, list(costs_paper[0]))
    write_csv(output/'cost_by_stage.csv', costs_stage, list(costs_stage[0]))
    write_csv(output/'failures.csv', failures, ['source_run_id','tool','paper','phase','status','cause','cause_detail',
              'traceback_file','docvortex','mineru','version_evidence','attempted_denominator','receipt_path'])
    write_csv(output/'attempt_failure_summary.csv', attempt_rates, list(attempt_rates[0]))
    write_csv(output/'detector_page_timings.csv', timings_page, ['tool','source_run_id','paper','page_idx','inference_s','scope'])
    timing_summary = []
    for tool in TOOLS:
        for metric, values, scope in (
            ('recorded_s_by_paper', [p['recorded_s'] for p in costs_paper if p['tool']==tool], 'observed_papers_not_run_repetitions'),
            ('recorded_s_per_completed_page_ratio', [p['recorded_s_per_completed_page'] for p in costs_paper if p['tool']==tool], 'per_paper_ratio_not_individual_SDK_pages'),
            ('detector_page_inference_s', [p['inference_s'] for p in timings_page if p['tool']==tool], 'recorded_detector_pages_only')):
            timing_summary.append(dict(tool=tool, metric=metric, scope=scope, **core.describe(values)))
    write_csv(output/'timing_distributions.csv', timing_summary, list(timing_summary[0]))
    manifest['phases']['F5'] = 'recorded_cost_extraction_complete; quality_cost_valuation_pending'
    prepare_review(output, source, inventory, page_stats, page_assets)
    manifest['phases']['F3'] = 'batches_prepared; PDF_case_inventory_and_visual_review_pending'
    manifest['phases']['F4'] = 'not_run_visual_review_deferred'
    for name in ('case_registry.jsonl', 'case_assessments.jsonl'):
        (output/name).write_text('', encoding='utf-8')
    write_csv(output/'reviewed_metrics.csv', [], ['metric','tool','paper','case_type','numerator','denominator','pending','scope'])
    write_json(output/'review_status.json', dict(expected_pages=expected_pages, human_reviewed_pages=0,
               agent_visually_reviewed_pages=0, case_inventory_complete_pages=0, semantic_metrics_status='pending_not_zero',
               unknowns=['omissions_shared_by_all_tools','actual_titles_captions_body_inventory','crop_errors','semantic_relationship_correctness']))
    summary = dict(papers=len(inventory), pages=expected_pages, tool_page_outputs=expected_pages*4,
                   tools={t: {k: totals[t][k] for k in ('rows','valid','missing','invalid')} for t in TOOLS},
                   positive_overlap_edges=edge_count, candidate_components=component_count,
                   geometry_candidate_rows=sum(r['candidate_outlier'] for r in geometry_rows),
                   human_reviewed_pages=0, automatic_semantic_errors=0,
                   semantic_error_count_meaning='not_computed; zero_is_not_zero_errors',
                   native_pattern_totals={t: {key: sum(p[key] for p in patterns if p['tool'] == t)
                       for key in ('parent_edges','dangling_parent_refs','visual_parent_nodes','visual_caption_parents','explicit_panel_nodes','list_item_nodes','list_groups_with_items','opaque_relation_fields')} for t in TOOLS})
    # Do not publish a misleading numeric zero for unknown semantic error totals.
    summary['automatic_semantic_errors'] = None
    write_json(output/'automatic_summary.json', summary)
    from analytics.automatic.reporting import write_report
    write_report(output, source, summary, costs_paper, costs_stage, attempt_rates)
    print('F2 and review preparation complete; verifying protected inputs again.', flush=True)
    changed = [str(p) for p, before in sources.hashes.items() if core.sha256(p) != before]
    records = sources.records()
    write_json(output/'input_manifest.json', records)
    verification = dict(status='PASS' if not changed else 'FAIL', all_inputs_unchanged=not changed,
                        changed_inputs=changed, verified_input_files=len(records),
                        expected_papers=len(inventory), expected_pages=expected_pages,
                        tool_page_outputs=len(page_info), metrics_reconciled=True,
                        human_reviewed_pages=0, no_reparse=True, no_colab=True, no_renders=True,
                        scope='technical_identity_and_automatic_output_consistency_not_semantic_validation',
                        analysis_process_memory=process_memory(),
                        elapsed_s=time.perf_counter()-started)
    write_json(output/'analysis_verification.json', verification)
    if changed:
        raise ValueError('Protected input changed during analysis')
    manifest.update(status='automatic_complete_visual_review_pending', inputs=records,
                    elapsed_s=time.perf_counter()-started, completed_utc=datetime.now(timezone.utc).isoformat())
    manifest['phases']['F6'] = 'automatic_technical_verification_complete; semantic_completion_pending'
    write_json(output/'analysis_manifest.json', manifest)
    return summary


def process_memory():
    """Read this process's OS peak RSS, with no GPU calls or optional dependency."""
    try:
        if sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes
            class Counters(ctypes.Structure):
                _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)]+[
                    (name, ctypes.c_size_t) for name in ('peak_rss','rss','peak_pool','pool','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            api = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
            api.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            api.restype = wintypes.BOOL
            counters = Counters(); counters.cb = ctypes.sizeof(counters)
            if not api(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                raise OSError(ctypes.get_last_error())
            peak = counters.peak_rss
        else:
            import resource
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            peak *= 1 if sys.platform == 'darwin' else 1024
        return dict(peak_rss_bytes=peak, scope='offline_analysis_process_os_peak_not_parser_memory')
    except (ImportError, OSError) as exc:
        return dict(peak_rss_bytes=None, unavailable_reason=type(exc).__name__)


def prepare_review(output, source, inventory, stats, assets):
    papers = []
    review = authored_report_path(output).parent/'review'; review.mkdir(parents=True)
    for paper in inventory:
        pages = []
        lines = [f"# Revisión pendiente: {paper['name']}", '',
                 'Inventariar el PDF completo, incluidas regiones sin detecciones. Ninguna página está revisada.', '',
                 '| Página PDF | Índice JSON | Alertas geométricas exploratorias | Fondo existente |',
                 '| --- | --- | --- | --- |']
        for idx in range(paper['pages']):
            p = dict(stats[(paper['sha256'], idx)])
            image = source/'viewer_source'/assets[(paper['sha256'], idx)]['image']
            p.update(pdf_page=idx+1, image_path=str(image),
                     normalized_paths={t: str(source/'assembled'/t/Path(paper['name']).stem/'normalized.json') for t in TOOLS},
                     review_expected_axes=['coverage','structural_boundaries','granularity','native_relations','tagging','crop'],
                     priority_types=['titles','captions','body'],
                     selection='full_inventory_includes_pages_without_alerts')
            pages.append(p)
            import os
            relative = Path(os.path.relpath(image, review)).as_posix()
            lines.append(f"| {idx+1} | {idx} | {p['geometry_alerts']} | [Fondo]({relative}) |")
        paper_file = Path(paper['name']).stem+'.md'
        (review/paper_file).write_text('\n'.join(lines)+'\n', encoding='utf-8')
        papers.append(dict(paper=paper['name'], paper_sha256=paper['sha256'], pages=pages,
                           status='not_reviewed', review_guide=Path(os.path.relpath(review/paper_file,output)).as_posix()))
    write_json(output/'review_batches.json', dict(status='prepared_not_reviewed', expected_pages=sum(p['pages'] for p in inventory), papers=papers))
    index = ['# Revisión visual preparada y pendiente', '',
             'Los fondos y predicciones se reutilizan por referencia. No se inició servidor, navegador, OCR ni render.',
             'El visor original se conserva; su disponibilidad HTTP depende de un servidor existente y no se comprobó en esta ejecución.',
             'No escribir en el reviews.json original: registrar la revisión futura en case_registry.jsonl y case_assessments.jsonl del análisis.', '',
             '## Cómo revisar', '',
             '1. Inventariar primero el contenido visible de toda la página, incluyendo contenido omitido por todas las herramientas.',
             '2. Asignar casos comunes a las cuatro herramientas; distinguir caja propia, varias cajas y caja de grupo.',
             '3. Registrar cobertura y separación por separado; conservar desconocidos y sin revisar.',
             '4. Revisar título→texto, relación figura–caption y límites de columnas/secciones. No inferir errores de las alertas.',
             '5. Marcar explícitamente autor, evidencia y aprobación humana; no importar revisiones del smoke.', '',
             '## Lotes completos por paper', '']
    index.extend(f"- [{p['paper']}]({Path(p['paper']).stem}.md): {len(p['pages'])} páginas pendientes." for p in papers)
    (review/'index.md').write_text('\n'.join(index)+'\n', encoding='utf-8')
    write_json(output/'review_entry_templates.json', dict(
        instruction='Templates only; not observations. Create case IDs from PDF inventory, not predicted rows.',
        case_template=dict(case_id=None, paper_sha256=None, page_idx=None, observed_type=None, visual_locator=None, created_at=None,
                           page_case_inventory_complete=False, evidence_level=None, author=None),
        assessment_template=dict(case_id=None, tool=None, detection_uids=[], evidence_refs=[], evidence_level=None,
                                 reviewed_at=None, author=None, coverage_status='not_reviewed',
                                 coverage_support=[], segmentation_status='not_reviewed', relation_status='undetermined',
                                 tag_status='not_reviewed', issues=[], human_approved=False)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    folder = project_root(__file__)
    result = execute(folder/'raw_results'/'code'/'mineru-nativefix-20261101T034122Z',
                     folder/'runtime'/'attempts'/'mineru-nativefix-20261101T034122Z'/'inventory.json',
                     folder.parents[1], folder/'docs'/'methodology'/'analysis-plan.md', folder/'config'/'experiment.json', args.output)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
