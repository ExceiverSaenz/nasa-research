"""Final invariants, transitive input identities and original-file integrity."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import sys,json,csv,importlib.util
from pathlib import Path
from collections import Counter
from analytics.geometry.run import SOURCE,BASE,TOOLS,readlines,sha,jsonout
from analytics.targets.targets import family
OUT=BASE/'raw_results/analytics/targets-20261101-v1'

def main():
    refs=readlines(OUT/'agent_reference_cases.jsonl');a=readlines(OUT/'agent_assessments.jsonl');checks={}
    checks['unique_eligible_objects_59']=sum(r['eligible'] for r in refs)==59
    checks['headings_19']=sum(r['eligible'] and r['reference']=='heading' for r in refs)==19
    checks['eligible_assessments_236']=sum(r['eligible'] for r in a)==236
    checks['four_tools_per_case']=all({r['tool'] for r in a if r['case_id']==c['case_id']}==set(TOOLS) for c in refs)
    checks['duplicates_excluded']=all(not r['eligible'] for r in refs if r.get('same_as'))
    checks['references_are_agent_not_human']=all(r['human_validation'] is False for r in refs)
    checks['affiliation_compatibility']=all(r['status']=='coarse_usable' for r in a if r['eligible'] and r['reference_subtype']=='affiliation' and r['own_matches'])
    with (OUT/'agent_tool_summary.csv').open(encoding='utf-8') as f:summ=list(csv.DictReader(f))
    statuses=['adequate','coarse_usable','contradictory','wrong','no_own_correspondence','group_coverage','undetermined']
    checks['tool_status_sums_59']=all(sum(int(r.get(k) or 0) for k in statuses)==59 for r in summ)
    with (OUT/'agent_subtype_assessments.csv').open(encoding='utf-8') as f:sub=list(csv.DictReader(f))
    checks['figure_caption_table_subtype_preserved']=all(any(r['case_id']=='T018' and r['tool']==t and r['subtype_status']=='figure_as_table_caption' for r in sub) for t in ('basic','standard'))
    unchanged={};exceptions=[]
    for vp in OUT.glob('*verification.json'):
        d=json.loads(vp.read_text(encoding='utf-8'))
        for p,h in d.get('input_hashes',{}).items():
            if sha(p)==h:unchanged[p]=h;continue
            snapshot=OUT/'code_snapshot/targets_at_prepare.py'
            if vp.name=='prepare_verification.json' and Path(p).name=='targets.py' and sha(snapshot)==h:
                exceptions.append(dict(original_path=p,verified_snapshot=str(snapshot),hash=h,reason='assessment function extended after preparation; family mapping unchanged'))
            else:raise RuntimeError('Input changed: '+p+' referenced by '+str(vp))
    spec=importlib.util.spec_from_file_location('targets_prepare',OUT/'code_snapshot/targets_at_prepare.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    labels={r['raw_label'] for r in readlines(SOURCE/'detections.jsonl')}
    checks['family_mapping_same_as_prepare']=all(family(l)==m.family(l) for l in labels)
    manifest=json.loads((SOURCE/'input_manifest.json').read_text(encoding='utf-8'));bad=[r['path'] for r in manifest if sha(r['path'])!=r['sha256']]
    checks['original_2452_files_unchanged']=not bad
    deep=BASE/'raw_results/analytics/deep-20261101-v2';old=json.loads((deep/'final_checks.json').read_text(encoding='utf-8'))
    checks['previous_deep_analysis_outputs_unchanged']=all(sha(deep/name)==h for name,h in old['output_hashes'].items())
    checks['consumed_input_hashes_valid']=True
    jsonout(OUT/'final_checks.json',dict(checks=checks,all_pass=all(checks.values()),original_files_checked=len(manifest),verified_consumed_inputs=len(unchanged),code_snapshot_exceptions=exceptions,output_hashes={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='final_checks.json'},human_validation=False,population_precision_estimated=False))
    print(json.dumps(dict(checks=checks,all_pass=all(checks.values()),original_files=len(manifest)),indent=2))
    if not all(checks.values()):raise SystemExit(1)

if __name__=='__main__':main()
