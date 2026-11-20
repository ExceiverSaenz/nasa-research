"""Full collection target profiles and descriptive native-score alternatives."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import sys,json,csv
from pathlib import Path
from collections import Counter,defaultdict
from analytics.geometry.run import SOURCE,BASE,TOOLS,PAIRS,readlines,csvout,jsonout,sha
from analytics.geometry.metrics import box_state
from analytics.targets.targets import family
OUT=BASE/'raw_results/analytics/targets-20261101-v1'

def main():
    if (OUT/'target_pair_conditionals.csv').exists():raise RuntimeError('Profiles already exist')
    paths=[SOURCE/'detections.jsonl',SOURCE/'source_map.json',OUT/'agent_assessments.jsonl',OUT/'target_correspondences.csv',Path(__file__),Path(__file__).with_name('targets.py')]
    hashes={str(p.resolve()):sha(p) for p in paths};rows=readlines(SOURCE/'detections.jsonl');ids={r['analysis_uid']:r for r in rows}
    profiles=[];conflicts=[]
    for t in TOOLS:
        rr=[r for r in rows if r['tool']==t];unique=defaultdict(list)
        for r in rr:
            if box_state(r.get('bbox_normalized'))=='valid':unique[r['paper_sha256'],r['page_idx'],tuple(r['bbox_normalized'])].append(r)
        for target in sorted({family(r['raw_label']) for r in rr if family(r['raw_label'])}):
            tr=[r for r in rr if family(r['raw_label'])==target];u=[g for g in unique.values() if any(family(r['raw_label'])==target for r in g)]
            contradictory=[g for g in u if ({family(r['raw_label']) for r in g}>={target,'text'} and target in ('heading','caption','visual'))]
            profiles.append(dict(tool=t,target=target,records=len(tr),localized=sum(box_state(r.get('bbox_normalized'))=='valid' for r in tr),unlocalized=sum(box_state(r.get('bbox_normalized'))!='valid' for r in tr),unique_geometries=len(u),same_geometry_with_text=len(contradictory),pages=len({(r['paper_sha256'],r['page_idx']) for r in tr}),papers=len({r['paper_sha256'] for r in tr})))
        for k,g in unique.items():
            fs={family(r['raw_label']) for r in g}
            for target in ('heading','caption','visual'):
                if {target,'text'}<=fs:conflicts.append(dict(tool=t,target=target,paper_sha256=k[0],page_idx=k[1],bbox=k[2],labels=[r['raw_label'] for r in g],ids=[r['analysis_uid'] for r in g],meaning='simultaneous_general_specific_targets_not_automatic_false_positive'))
    csvout(OUT/'target_profiles.csv',profiles);csvout(OUT/'strict_same_box_target_alternatives.csv',conflicts)
    with (OUT/'target_correspondences.csv').open(encoding='utf-8') as f:rr=list(csv.DictReader(f))
    conditional=[]
    for a,b in PAIRS:
        pair=[r for r in rr if r['tool_a']==a and r['tool_b']==b]
        for direction in ('a','b'):
            other='b' if direction=='a' else 'a'
            for target in sorted({r['family_'+direction] for r in pair if r['family_'+direction]}):
                tr=[r for r in pair if r['family_'+direction]==target];cnt=Counter(r['family_'+other] or 'unmapped' for r in tr)
                for ot,n in cnt.items():conditional.append(dict(source_tool=a if direction=='a' else b,destination_tool=b if direction=='a' else a,source_target=target,destination_target=ot,count=n,source_target_matched_cases=len(tr),conditional_fraction=n/len(tr),scope='equivalent_blocks_not_recall_or_precision'))
    csvout(OUT/'target_pair_conditionals.csv',conditional)
    sm=json.loads((SOURCE/'source_map.json').read_text(encoding='utf-8'));sourcepaths={r['original_ref'].split('#')[0]:r['local_path'] for r in sm};cache={};scores=[]
    audits=readlines(OUT/'agent_assessments.jsonl')
    for r in audits:
        if not r['eligible'] or r['tool'] not in ('heron','heron101') or not r['own_matches']:continue
        entries=[]
        for m in r['own_matches']:
            d=ids[m['id']];path=Path(sourcepaths[d['original_ref'].split('#')[0]])
            if str(path) not in cache:
                hashes[str(path.resolve())]=sha(path);cache[str(path)]=json.loads(path.read_text(encoding='utf-8'))
            native=cache[str(path)]
            if not isinstance(native,list):continue
            for n in native:
                if n.get('label')==d['raw_label'] and n.get('bbox')==d['bbox_raw'] and isinstance(n.get('score'),(float,int)):
                    entries.append(dict(label=d['raw_label'],score=n['score'],id=d['analysis_uid']))
        if not entries:continue
        maximum=max(e['score'] for e in entries);winners=[e for e in entries if e['score']==maximum]
        scores.append(dict(case_id=r['case_id'],tool=r['tool'],reference=r['reference'],output_status=r['status'],native_alternatives=entries,max_native_score=maximum,max_score_labels=sorted({e['label'] for e in winners}),meaning='descriptive_score_order_not_calibrated_probability_or_modified_prediction'))
    from analytics.geometry.run import jsonlout
    jsonlout(OUT/'native_score_alternatives.jsonl',scores)
    assert all(sha(p)==h for p,h in hashes.items());jsonout(OUT/'profiles_verification.json',dict(input_hashes=hashes,unchanged=True,profile_rows=len(profiles),native_score_cases=len(scores)))
    print('Target profiles and native score alternatives generated')

if __name__=='__main__':main()
