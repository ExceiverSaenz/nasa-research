"""Deterministic, standard-library-only analysis of preserved predictions."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
from collections import defaultdict
import hashlib
import math
from pathlib import Path
import statistics


def sha256(path):
    h = hashlib.sha256()
    with resolve_path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def box_state(b):
    if b is None:
        return 'missing'
    if not isinstance(b, (list, tuple)) or len(b) != 4 or not all(number(v) for v in b):
        return 'invalid'
    return 'valid' if 0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1 else 'invalid'


def area(b):
    return (b[2]-b[0])*(b[3]-b[1])


def overlap(a, b):
    i = max(0, min(a[2], b[2])-max(a[0], b[0]))*max(0, min(a[3], b[3])-max(a[1], b[1]))
    aa, ab = area(a), area(b)
    return dict(intersection=i, iou=i/(aa+ab-i), fraction_a=i/aa, fraction_b=i/ab)


def union_area(boxes):
    """Exact rectangle union by an x sweep; does not count whitespace in an envelope."""
    boxes = [b for b in boxes if box_state(b) == 'valid']
    xs = sorted({v for b in boxes for v in (b[0], b[2])})
    total = 0.0
    for x0, x1 in zip(xs, xs[1:]):
        intervals = sorted((b[1], b[3]) for b in boxes if b[0] < x1 and b[2] > x0)
        length, end = 0.0, -math.inf
        for y0, y1 in intervals:
            length += max(0, y1-max(y0, end))
            end = max(end, y1)
        total += (x1-x0)*length
    return total


def compare_page(left, right):
    """All positive cross-tool overlaps, including 1:n matches below 0.5 IoU."""
    left = [x for x in left if box_state(x.get('bbox_normalized')) == 'valid']
    right = [x for x in right if box_state(x.get('bbox_normalized')) == 'valid']
    nodes = {('a', x['id']): x for x in left}
    nodes.update({('b', x['id']): x for x in right})
    parents = {}
    def find(x):
        parents.setdefault(x, x)
        while parents[x] != x:
            parents[x] = parents[parents[x]]
            x = parents[x]
        return x
    edges = []
    for a in left:
        for b in right:
            values = overlap(a['bbox_normalized'], b['bbox_normalized'])
            if values['intersection'] <= 0:
                continue
            evaluable = bool(a.get('raw_label')) and bool(b.get('raw_label'))
            edges.append(dict(a=a['id'], b=b['id'], **values,
                              threshold_match=values['iou'] >= .5,
                              literal_label_evaluable=evaluable,
                              literal_label_match=a['raw_label'] == b['raw_label'] if evaluable else None))
            parents[find(('a', a['id']))] = find(('b', b['id']))
    components = defaultdict(list)
    for node in list(parents):
        components[find(node)].append(node)
    groups = []
    for component in components.values():
        a = [nodes[n] for n in component if n[0] == 'a']
        b = [nodes[n] for n in component if n[0] == 'b']
        ba, bb = [x['bbox_normalized'] for x in a], [x['bbox_normalized'] for x in b]
        ua, ub, together = union_area(ba), union_area(bb), union_area(ba+bb)
        intersection = max(0.0, ua+ub-together)
        groups.append(dict(ids_a=[x['id'] for x in a], ids_b=[x['id'] for x in b],
                           n_a=len(a), n_b=len(b), union_area_a=ua, union_area_b=ub,
                           union_iou=min(1.0, intersection/together),
                           interpretation='candidate_correspondence_not_semantic_unit'))
    return edges, groups


def quantile(values, p):
    if not values:
        return None
    r = (len(values)-1)*p
    lo, hi = math.floor(r), math.ceil(r)
    return values[lo]+(values[hi]-values[lo])*(r-lo)


def describe(values):
    clean = sorted(x for x in values if number(x))
    n = len(clean)
    result = dict(n=n, missing=len(values)-n, minimum=None, p05=None, median=None,
                  p95=None, maximum=None, q1=None, q3=None, iqr=None, mad=None,
                  lower_fence=None, upper_fence=None, iqr_rule_evaluable=False)
    if not clean:
        return result
    median = quantile(clean, .5)
    q1, q3 = quantile(clean, .25), quantile(clean, .75)
    result.update(minimum=clean[0], p05=quantile(clean, .05), median=median,
                  p95=quantile(clean, .95), maximum=clean[-1], q1=q1, q3=q3,
                  iqr=q3-q1, mad=statistics.median(abs(x-median) for x in clean))
    if n >= 20 and q3 > q1:
        result.update(iqr_rule_evaluable=True, lower_fence=q1-1.5*(q3-q1),
                      upper_fence=q3+1.5*(q3-q1))
    return result


VISUAL = {'image', 'chart', 'picture', 'figure'}
CAPTION = {'image_caption', 'chart_caption', 'caption'}
PANELS = {'panel', 'subfigure', 'figure_panel'}
LISTS = {'list', 'ordered_list', 'unordered_list'}


def native_patterns(rows):
    """Describe declared parentage only; never interpret geometry as hierarchy."""
    by_ref = {r['original_ref']: r for r in rows}
    children = defaultdict(list)
    dangling = 0
    for row in rows:
        parent = row.get('native_parent_ref')
        if parent:
            if parent in by_ref:
                children[parent].append(row)
            else:
                dangling += 1
    visual_caption, visual_panel, full = 0, 0, 0
    list_groups = 0
    for ref, kids in children.items():
        label = by_ref[ref]['raw_label']
        labels = {k['raw_label'] for k in kids}
        if label in VISUAL:
            cap = bool(labels & CAPTION)
            panel = bool(labels & PANELS)
            visual_caption += cap
            visual_panel += panel
            full += cap and panel
        if label in LISTS and 'list_item' in labels:
            list_groups += 1
    return dict(parent_edges=sum(map(len, children.values())), dangling_parent_refs=dangling,
                visual_parent_nodes=sum(r['raw_label'] in VISUAL for r in rows),
                visual_caption_parents=visual_caption, visual_parents_with_explicit_panels=visual_panel,
                visual_parents_with_panels_and_caption=full,
                explicit_panel_nodes=sum(r['raw_label'] in PANELS for r in rows),
                list_item_nodes=sum(r['raw_label'] == 'list_item' for r in rows),
                list_groups_with_items=list_groups,
                opaque_relation_fields=sum(bool(r.get('relations')) for r in rows),
                G4='requires_pdf_marker_inventory_and_native_identifier_review',
                semantic_review_status='not_reviewed',
                meaning='availability_in_projected_native_schema_not_correctness_or_recall')


def pointer(data, fragment):
    if not fragment:
        return data
    if not fragment.startswith('/'):
        raise ValueError('Invalid JSON pointer')
    for item in fragment[1:].split('/'):
        item = item.replace('~1', '/').replace('~0', '~')
        data = data[int(item)] if isinstance(data, list) else data[item]
    return data


def resolve_ref(assembled, ref, expected_sha, cache=None):
    native_ref, _, fragment = ref.replace('\\', '/').partition('#')
    marker = '/results/execute/'
    if marker not in native_ref:
        raise ValueError('Unrecognized native reference namespace: '+ref)
    suffix = native_ref.split(marker, 1)[1]
    if any(p in ('', '.', '..') for p in suffix.split('/')):
        raise ValueError('Invalid native reference path')
    root = Path(assembled).resolve()
    path = (root/suffix).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Native path escapes assembled root')
    if cache is not None and path in cache:
        actual = cache[path]
    else:
        actual = sha256(path)
        if cache is not None:
            cache[path] = actual
    if actual != expected_sha:
        raise ValueError('Native SHA256 mismatch: '+str(path))
    return path, fragment


def extract_cost(receipt, tool, source_run):
    papers = []
    for entry in receipt['results']:
        result = entry.get('result') or {}
        timings = [t.get('inference_s') for t in result.get('timings', [])]
        if tool in ('heron', 'heron101'):
            recorded = sum(timings) if timings and all(number(v) for v in timings) else None
            scope = 'detector_page_inference_sum'
        else:
            recorded = result.get('total_parse_export_excluded_s')
            scope = 'sdk_parse_excluding_export'
        pages = len(result.get('page_indices', []))
        papers.append(dict(tool=tool, source_run_id=source_run, paper=entry['paper'],
                           status=entry['status'], completed_pages=pages, recorded_s=recorded,
                           recorded_scope=scope, recorded_load_s=result.get('load_s'),
                           isolated_inference_s=result.get('inference_s'),
                           recorded_s_per_completed_page=recorded/pages if number(recorded) and pages else None,
                           per_page_value_meaning='ratio_not_individual_page_observation',
                           unknown_timing_reason=result.get('unknown_timing_reason')))
    samples = receipt.get('resources', [])
    ram = [s.get('ram_bytes') for s in samples]
    gpu = [g.get('used_mib') for s in samples for g in (s.get('gpu') or [])]
    rs, gs = describe(ram), describe(gpu)
    stage = dict(tool=tool, source_run_id=source_run, sample_count=len(samples),
                 ram_peak_bytes=rs['maximum'], ram_median_bytes=rs['median'], ram_p95_bytes=rs['p95'],
                 ram_missing_samples=rs['missing'], gpu_peak_mib=gs['maximum'],
                 gpu_median_mib=gs['median'], gpu_p95_mib=gs['p95'],
                 gpu_missing_samples=sum(not s.get('gpu') for s in samples),
                 monitor_error_samples=sum(bool(s.get('ram_error') or s.get('gpu_error')) for s in samples),
                 gpu_device_count_max=max((len(s.get('gpu') or []) for s in samples), default=0),
                 sampled_elapsed_span_s=max((s.get('elapsed_s', 0) for s in samples), default=None),
                 stage_wall_s=None, nominal_interval_s=1,
                 scope='stage_process_tree_rss_and_device_gpu_sampled_not_exclusive_not_per_paper')
    return papers, stage


def attempt_failures(receipt, tool, source_run, versions, expected):
    entries = receipt['results']
    names = [e['paper'] for e in entries]
    if len(set(names)) != len(names) or len(entries) > expected:
        raise ValueError('Duplicate or excessive attempted papers')
    failures = [dict(source_run_id=source_run, tool=tool, paper=e['paper'], phase='collection_execute',
                     status=e['status'], cause=e.get('error'), cause_detail=e.get('error_detail'),
                     traceback_file=e.get('traceback_file'), docvortex=versions.get('docvortex'),
                     mineru=versions.get('mineru'), version_evidence=versions.get('evidence'),
                     attempted_denominator=len(entries)) for e in entries if e['status'] == 'failed']
    rate = dict(source_run_id=source_run, tool=tool, expected=expected, attempted=len(entries),
                complete=sum(e['status']=='complete' for e in entries), failed=len(failures),
                other_statuses=sum(e['status'] not in ('complete','failed') for e in entries),
                not_attempted=expected-len(entries), failure_fraction=len(failures)/len(entries) if entries else None,
                docvortex=versions.get('docvortex'), mineru=versions.get('mineru'),
                version_evidence=versions.get('evidence'), scope='one_attempt_and_configuration_not_pooled')
    return failures, rate


def page_timing_observations(receipt, tool, source_run):
    return [dict(tool=tool, source_run_id=source_run, paper=e['paper'], page_idx=t['page_idx'],
                 inference_s=t['inference_s'], scope='recorded_detector_page_observation')
            for e in receipt['results'] for t in (e.get('result') or {}).get('timings', [])
            if number(t.get('inference_s'))]
