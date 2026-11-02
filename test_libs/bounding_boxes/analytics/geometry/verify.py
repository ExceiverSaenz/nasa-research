"""Independent output invariants and read-only original integrity checks."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import sys,json,csv,itertools
from collections import Counter,defaultdict
from pathlib import Path
from analytics.geometry.run import SOURCE,PAIRS,readlines,sha,jsonout
from analytics.geometry.metrics import box_state,overlap,union_area

def main(out):
    rows=readlines(SOURCE/'detections.jsonl');valid={r['analysis_uid']:r for r in rows if box_state(r.get('bbox_normalized'))=='valid'}
    checks={};counts={}
    with (out/'iou_histograms.csv').open(encoding='utf-8') as f:h=list(csv.DictReader(f))
    groups=defaultdict(list)
    for r in h:groups[r['scope'],r['tool_a'],r['tool_b'],r['paper']].append(r)
    checks['all_histograms_partition_denominator']=all(sum(int(r['count']) for r in g)==int(g[0]['denominator']) and len(g)==10 for g in groups.values())
    checks['positive_overlap_total']=sum(int(r['count']) for r in h if r['scope']=='all_positive' and r['paper']=='ALL')==len(readlines(SOURCE/'agreement_edges.jsonl'))
    with (out/'page_metrics.csv').open(encoding='utf-8') as f:pm=list(csv.DictReader(f))
    checks['six_pairs_397_pages']=all(sum(r['tool_a']==a and r['tool_b']==b for r in pm)==397 for a,b in PAIRS)
    counts['empty_pair_pages']=sum(not r['area_jaccard'] for r in pm)
    for filename,onlyblock in [('granularity_groups.jsonl',False),('block_granularity_groups.jsonl',True)]:
        gg=readlines(out/filename);ok=True
        for a,b in PAIRS:
            used=[uid for g in gg if g['tool_a']==a and g['tool_b']==b for uid in g['ids_a']+g['ids_b']]
            expected=[uid for uid,r in valid.items() if r['tool'] in (a,b) and (not onlyblock or r.get('native_level')=='block')]
            ok &= Counter(used)==Counter(expected)
        checks[filename+'_partition']=ok
    cs=readlines(out/'spatial_clusters.jsonl');used=[uid for c in cs for uid in c['ids']]
    checks['clusters_partition_all_valid_boxes']=Counter(used)==Counter(valid.keys())
    checks['clusters_unique_tools']=all(len(c['tools'])==len(c['ids']) for c in cs)
    checks['clusters_complete_link_iou']=all(overlap(valid[a]['bbox_normalized'],valid[b]['bbox_normalized'])['iou']>=.9 for c in cs for a,b in itertools.combinations(c['ids'],2))
    actual=defaultdict(float)
    for r in readlines(out/'atomic_area_signatures.jsonl'):actual[r['paper_sha256'],r['page_idx']]+=r['area']
    expected=defaultdict(list)
    for r in valid.values():expected[r['paper_sha256'],r['page_idx']].append(r['bbox_normalized'])
    checks['atomic_area_equals_exact_union']=all(abs(actual[k]-union_area(v))<1e-9 for k,v in expected.items())
    manifest=json.loads((SOURCE/'input_manifest.json').read_text(encoding='utf-8'))
    bad=[r['path'] for r in manifest if sha(r['path'])!=r['sha256']]
    checks['original_2452_hashes_unchanged']=not bad;counts['original_files']=len(manifest)
    mainv=json.loads((out/'verification.json').read_text(encoding='utf-8'))
    checks['main_consumed_files_still_match']=all(sha(p)==v for p,v in mainv['consumed_input_hashes'].items())
    # User may keep adding feedback; report it separately instead of invalidating original results.
    feedbackpaths=[p for p in mainv['consumed_input_hashes'] if 'feedback_data' in p or '/raw_results/feedback/' in p.replace('\\','/')]
    counts['feedback_current_matches_snapshot']=all(sha(p)==mainv['consumed_input_hashes'][p] for p in feedbackpaths)
    checks['main_consumed_files_still_match']=all(sha(p)==v for p,v in mainv['consumed_input_hashes'].items() if p not in feedbackpaths)
    output=dict(checks=checks,counts=counts,all_pass=all(checks.values()),semantic_validation=False,output_hashes={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='final_checks.json'})
    jsonout(out/'final_checks.json',output);print(json.dumps(dict(checks=checks,counts=counts,all_pass=output['all_pass']),indent=2))
    if not output['all_pass']:raise SystemExit(1)

if __name__=='__main__':main(Path(sys.argv[1]))
