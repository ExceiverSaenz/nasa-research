"""Additional strata: native blocks, exact duplicates, macro/LOO recurrence."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import sys
import csv
import json
import itertools
from collections import Counter,defaultdict
from pathlib import Path
from analytics.geometry.metrics import area,overlap,union_area,box_state,atoms,clusters,components,group_metrics,category
from analytics.geometry.run import BASE,SOURCE,TOOLS,PAIRS,readlines,csvout,jsonout,jsonlout,sha,mean,ratio

def main(out):
    if (out/'supplement_verification.json').exists():raise RuntimeError('Supplement already exists')
    files=[SOURCE/'detections.jsonl',SOURCE/'label_map.csv',SOURCE/'page_inventory.csv',out/'spatial_clusters.jsonl',Path(__file__),Path(__file__).with_name('metrics.py'),BASE/'analytics/automatic/core.py']
    before={str(p.resolve()):sha(p) for p in files}
    rows=readlines(SOURCE/'detections.jsonl');valid=[r for r in rows if box_state(r.get('bbox_normalized'))=='valid'];pages=defaultdict(list);names={};paperpages=defaultdict(set)
    with (SOURCE/'page_inventory.csv').open(encoding='utf-8') as f:
        for r in csv.DictReader(f):
            names[r['paper_sha256']]=r['paper'];pages[r['paper_sha256'],int(r['page_idx'])];paperpages[r['paper']].add(int(r['page_idx']))
    for r in valid:pages[r['paper_sha256'],r['page_idx']].append(r)
    with (SOURCE/'label_map.csv').open(encoding='utf-8') as f:
        lm={(r['tool'],r['raw_label'],r['native_level']):r['category_candidate'] for r in csv.DictReader(f)}
    def coarse(r):return lm.get((r['tool'],r['raw_label'],r.get('native_level')),'unmapped')
    duplicate=[];dupstats=[]
    for t in TOOLS:
        exact=defaultdict(list)
        for r in valid:
            if r['tool']==t:exact[r['paper_sha256'],r['page_idx'],tuple(r['bbox_normalized'])].append(r)
        for (pdf,idx,bb),g in exact.items():
            if len(g)>1:duplicate.append(dict(tool=t,paper=names[pdf],page_idx=idx,bbox=bb,ids=[r['analysis_uid'] for r in g],labels=[r['raw_label'] for r in g],levels=[r.get('native_level') for r in g],categories=[coarse(r) for r in g],meaning='coincident_geometry_not_automatically_error'))
        dupstats.append(dict(tool=t,records=sum(len(g) for g in exact.values()),unique_geometries=len(exact),coincident_groups=sum(len(g)>1 for g in exact.values()),extra_coincident_records=sum(len(g)-1 for g in exact.values())))
    csvout(out/'coincident_boxes_summary.csv',dupstats);jsonlout(out/'coincident_boxes.jsonl',duplicate)
    blockgroups=[];blockmetrics=[];blockclusters=[];boundary=[]
    for (pdf,idx),pr in sorted(pages.items()):
        block=[r for r in pr if r.get('native_level')=='block'];ctx=dict(paper=names[pdf],paper_sha256=pdf,page_idx=idx)
        ar=atoms(block)
        for a,b in PAIRS:
            aa=[r for r in block if r['tool']==a];bb=[r for r in block if r['tool']==b]
            gs=[dict(**ctx,tool_a=a,tool_b=b,**group_metrics(x,y,.9)) for x,y in components(aa,bb,.9)];blockgroups+=gs
            inter=sum(c['area'] for c in ar if a in c['tools'] and b in c['tools']);u=sum(c['area'] for c in ar if a in c['tools'] or b in c['tools'])
            blockmetrics.append(dict(**ctx,tool_a=a,tool_b=b,intersection=inter,union=u,area_jaccard=ratio(inter,u),**dict(Counter(g['geometry_status'] for g in gs))))
        for j,g in enumerate(clusters(block,.9)):
            if len(g)<2:continue
            cats={r['tool']:coarse(r) for r in g};labs={r['tool']:r['raw_label'] for r in g}
            blockclusters.append(dict(**ctx,cluster_id=f'{pdf}:{idx}:block{j}',labels=labs,categories=cats,ids=[r['analysis_uid'] for r in g],mapped_all=all(c!='unmapped' for c in cats.values()),category_disagreement=len({c for c in cats.values() if c!='unmapped'})>1))
        # Candidate absorbed headings and text/visual overlap. Labels are hypotheses, not PDF reference.
        for r in block:
            if coarse(r)!='text_general':continue
            for h in block:
                if h['tool']==r['tool'] or coarse(h) not in ('heading_candidate','visual_candidate','table_candidate'):continue
                v=overlap(r['bbox_normalized'],h['bbox_normalized'])
                if v['fraction_b']>=.9 and area(r['bbox_normalized'])>1.5*area(h['bbox_normalized']):
                    boundary.append(dict(**ctx,text_tool=r['tool'],other_tool=h['tool'],text_id=r['analysis_uid'],other_id=h['analysis_uid'],other_label=h['raw_label'],other_category=coarse(h),containment=v['fraction_b'],area_ratio=area(r['bbox_normalized'])/area(h['bbox_normalized']),status='cross_tool_candidate_not_confirmed_mixing'))
    jsonlout(out/'block_granularity_groups.jsonl',blockgroups);csvout(out/'block_page_metrics.csv',blockmetrics);jsonlout(out/'block_spatial_clusters.jsonl',blockclusters);csvout(out/'structural_boundary_candidates.csv',boundary)
    blocksummary=[];blockcat=[]
    for a,b in PAIRS:
        rr=[r for r in blockmetrics if r['tool_a']==a and r['tool_b']==b];gg=[r for r in blockgroups if r['tool_a']==a and r['tool_b']==b]
        cc=[r for r in blockclusters if a in r['labels'] and b in r['labels']];evals=[r for r in cc if r['categories'][a]!='unmapped' and r['categories'][b]!='unmapped'];equal=sum(r['categories'][a]==r['categories'][b] for r in evals)
        blocksummary.append(dict(tool_a=a,tool_b=b,pages=len(rr),area_jaccard=ratio(sum(r['intersection'] for r in rr),sum(r['union'] for r in rr)),equivalent_spatial_clusters=len(cc),category_evaluable_clusters=len(evals),category_equal_clusters=equal,category_agreement=ratio(equal,len(evals)),**dict(Counter(g['geometry_status'] for g in gg)),**{'shape_'+k:v for k,v in Counter(g['shape'] for g in gg).items()}))
        cnt=Counter((r['labels'][a],r['labels'][b],r['categories'][a],r['categories'][b]) for r in cc)
        for (la,lb,ca,cb),n in cnt.items():blockcat.append(dict(tool_a=a,tool_b=b,label_a=la,label_b=lb,category_a=ca,category_b=cb,count=n,evaluable=ca!='unmapped' and cb!='unmapped',meaning='partial_schema_agreement_not_accuracy'))
    csvout(out/'block_pair_summary.csv',blocksummary);csvout(out/'block_label_contingency.csv',blockcat)
    cl=readlines(out/'spatial_clusters.jsonl');pat=defaultdict(list)
    for r in cl:
        if len(r['tools'])>1:pat[json.dumps(dict(labels=r['labels'],band=r['vertical_band'],width=r['width_band']),sort_keys=True)].append(r)
    pp=[]
    for signature,rr in pat.items():
        hit=defaultdict(set)
        for r in rr:hit[r['paper']].add(r['page_idx'])
        np=sum(map(len,hit.values()))
        if np<2:continue
        macro=mean([len(hit[p])/len(v) for p,v in paperpages.items()]);loo=[(np-len(hit[p]))/(len(pages)-len(v)) for p,v in paperpages.items()]
        pp.append(dict(signature=json.loads(signature),cases=len(rr),pages=np,papers=sum(bool(v) for v in hit.values()),micro_page_support=np/len(pages),macro_paper_page_support=macro,leave_one_paper_out_support_min=min(loo),leave_one_paper_out_support_max=max(loo),category_disagreement=rr[0]['category_disagreement'],per_paper={p:dict(pages=len(hit[p]),total_pages=len(v),page_support=len(hit[p])/len(v)) for p,v in paperpages.items()},meaning='descriptive_leave_one_paper_out_not_validation'))
    pp.sort(key=lambda r:(-r['papers'],-r['pages'],-r['cases']));csvout(out/'pattern_macro_and_loo.csv',pp)
    # Worst relative coverage pages and geometric split candidates are independently reviewable.
    jsonlout(out/'strict_granularity_examples.jsonl',[g for g in blockgroups if g['geometry_status']=='granularity_candidate'])
    headline=defaultdict(list)
    for r in blockclusters:
        mapped=set(r['categories'].values())
        if 'heading_candidate' in mapped and 'text_general' in mapped:headline['heading_vs_text'].append(r)
        if 'caption_candidate' in mapped and 'text_general' in mapped:headline['caption_vs_text'].append(r)
        if 'visual_candidate' in mapped and 'text_general' in mapped:headline['visual_vs_text'].append(r)
    for k,v in headline.items():jsonlout(out/(k+'_examples.jsonl'),v)
    jsonout(out/'supplement_summary.json',dict(block_pairs=blocksummary,duplicates=dupstats,block_multi_tool_clusters=len(blockclusters),boundary_candidate_edges=len(boundary),boundary_candidate_text_boxes=len({r['text_id'] for r in boundary}),priority_category_disagreements={k:dict(clusters=len(v),pages=len({(r['paper'],r['page_idx']) for r in v}),papers=len({r['paper'] for r in v})) for k,v in headline.items()}))
    after={p:sha(p) for p in before};assert before==after
    jsonout(out/'supplement_verification.json',dict(input_hashes=before,unchanged=True,pages=len(pages),tool_page_outputs=len(pages)*4,block_group_partition_checks={f'{a}|{b}':sum(r['n_a']+r['n_b'] for r in blockgroups if r['tool_a']==a and r['tool_b']==b)==sum(r.get('native_level')=='block' and r['tool'] in (a,b) for r in valid) for a,b in PAIRS}))
    print(json.dumps(dict(pages=len(pages),block_clusters=len(blockclusters),boundary_edges=len(boundary)),indent=2))

if __name__=='__main__':main(Path(sys.argv[1]))
