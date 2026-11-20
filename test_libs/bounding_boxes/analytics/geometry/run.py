"""Offline extension. Run from repository root; new output directory required."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import argparse
import csv
import hashlib
import itertools
import json
import math
import statistics
import time
from collections import Counter,defaultdict
from pathlib import Path
from analytics.geometry.metrics import area,box_state,overlap,union_area,histogram,components,group_metrics,clusters,atoms,category

BASE=project_root(__file__)
SOURCE=BASE/'raw_results/analytics/auto-20261101T080056Z-r2'
TOOLS=['heron','heron101','basic','standard']
PAIRS=list(itertools.combinations(TOOLS,2))

def sha(path):
    h=hashlib.sha256()
    with resolve_path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def readlines(path):
    return [json.loads(s) for s in path.open(encoding='utf-8') if s.strip()]

def csvout(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list,tuple)) else v for k,v in r.items()} for r in rows)

def jsonout(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def jsonlout(path,rows):
    with path.open('w',encoding='utf-8') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')

def quant(v,p):
    if not v:return None
    v=sorted(v);z=(len(v)-1)*p;a=int(z);b=math.ceil(z)
    return v[a]+(v[b]-v[a])*(z-a)

def mean(v):return statistics.mean(v) if v else None
def ratio(n,d):return n/d if d else None
def entropy(labels):
    c=Counter(labels);n=sum(c.values())
    return -sum((v/n)*math.log2(v/n) for v in c.values()) if n else None

def histogram_rows(values,scope,a,b,paper='ALL'):
    bins=histogram(values);n=len(values)
    return [dict(scope=scope,tool_a=a,tool_b=b,paper=paper,lower=i/10,upper=(i+1)/10,
                 interval=f'[{i/10:.1f},{(i+1)/10:.1f}'+(']' if i==9 else ')'),count=k,denominator=n,fraction=ratio(k,n)) for i,k in enumerate(bins)]

def reciprocal(rows):
    aa=defaultdict(list);bb=defaultdict(list)
    for r in rows:aa[r['a']].append(r);bb[r['b']].append(r)
    def best(v,key):
        top=max(r['iou'] for r in v);hits=[r for r in v if abs(r['iou']-top)<1e-12]
        return hits[0][key] if len(hits)==1 else None
    ba={k:best(v,'b') for k,v in aa.items()};b_b={k:best(v,'a') for k,v in bb.items()}
    return [r for r in rows if ba[r['a']]==r['b'] and b_b[r['b']]==r['a']]

def main(out):
    started=time.time();out.mkdir(parents=True,exist_ok=False)
    inputs=[SOURCE/n for n in ['detections.jsonl','agreement_edges.jsonl','agreement_components.jsonl','label_map.csv','page_inventory.csv','native_patterns.jsonl','cost_by_stage.csv','failures.csv','input_manifest.json']]
    inputs += [Path(__file__),Path(__file__).with_name('metrics.py'),(BASE/'docs/methodology/geometry-protocol.md'),BASE/'docs'/'methodology'/'analysis-plan.md',BASE/'analytics/automatic/core.py']
    feedback=BASE/'raw_results/feedback/session-v1/feedback.json'
    if feedback.exists():inputs.append(feedback)
    before={str(p.resolve()):sha(p) for p in inputs}
    feedback_bytes=feedback.read_bytes() if feedback.exists() else None
    if feedback_bytes is not None and hashlib.sha256(feedback_bytes).hexdigest()!=before[str(feedback.resolve())]:raise RuntimeError('Feedback changed while taking snapshot; rerun')
    oldmanifest=json.loads((SOURCE/'input_manifest.json').read_text(encoding='utf-8'))
    # Verify original inputs once, then verify exact files consumed after; neither changes originals.
    bad=[r['path'] for r in oldmanifest if not Path(r['path']).exists() or sha(r['path'])!=r['sha256']]
    if bad:raise RuntimeError('Original input manifest mismatch: '+str(bad[:5]))
    rows=readlines(SOURCE/'detections.jsonl');edges=readlines(SOURCE/'agreement_edges.jsonl')
    valid=[r for r in rows if box_state(r.get('bbox_normalized'))=='valid']
    pages=defaultdict(list);byid={r['analysis_uid']:r for r in rows}
    paper_name={}
    for r in rows:pages[r['paper_sha256'],r['page_idx']].append(r)
    with (SOURCE/'page_inventory.csv').open(encoding='utf-8') as f:
        for r in csv.DictReader(f):
            paper_name[r['paper_sha256']]=r['paper']
            pages[r['paper_sha256'],int(r['page_idx'])]
    for r in rows:r['paper']=paper_name[r['paper_sha256']]
    ep=defaultdict(list)
    for e in edges:ep[e['paper_sha256'],e['page_idx'],e['tool_a'],e['tool_b']].append(e)
    pair_edges={}
    # Existing edge files use alphabetic tool order; normalize requested orientation without mutating inputs.
    for a,b in PAIRS:
        rr=[]
        for e in edges:
            if (e['tool_a'],e['tool_b'])==(a,b):rr.append(e)
            elif (e['tool_a'],e['tool_b'])==(b,a):
                r=dict(e,tool_a=a,tool_b=b,a=e['b'],b=e['a'],fraction_a=e['fraction_b'],fraction_b=e['fraction_a']);rr.append(r)
        pair_edges[a,b]=rr
    hist=[];pair_stats=[];contingency=[];matched=[]
    for (a,b),ee in pair_edges.items():
        rr=reciprocal(ee);vals=[r['iou'] for r in ee];rv=[r['iou'] for r in rr]
        pair_stats.append(dict(tool_a=a,tool_b=b,positive_pairs=len(ee),median_iou=quant(vals,.5),p10_iou=quant(vals,.1),p90_iou=quant(vals,.9),exact_one=sum(x==1 for x in vals),fraction_ge_05=ratio(sum(x>=.5 for x in vals),len(vals)),reciprocal_pairs=len(rr),reciprocal_median=quant(rv,.5),reciprocal_ge_09=ratio(sum(x>=.9 for x in rv),len(rv))))
        for scope,vs in [('all_positive',vals),('reciprocal_best',rv)]:hist+=histogram_rows(vs,scope,a,b)
        for paper in sorted(paper_name.values()):
            hist+=histogram_rows([r['iou'] for r in ee if r['paper']==paper],'all_positive',a,b,paper)
        cc=Counter()
        for e in rr:
            if e['iou']<.9:continue
            ar,br=byid[e['a']],byid[e['b']]
            cc[ar['raw_label'],br['raw_label'],category(ar['raw_label']),category(br['raw_label'])]+=1
            matched.append(dict(tool_a=a,tool_b=b,paper=e['paper'],page_idx=e['page_idx'],id_a=e['a'],id_b=e['b'],iou=e['iou'],label_a=ar['raw_label'],label_b=br['raw_label'],category_a=category(ar['raw_label']),category_b=category(br['raw_label']),area_ratio_a_b=area(ar['bbox_normalized'])/area(br['bbox_normalized'])))
        for k,n in cc.items():contingency.append(dict(tool_a=a,tool_b=b,label_a=k[0],label_b=k[1],category_a=k[2],category_b=k[3],count=n,meaning='agreement_not_precision'))
    csvout(out/'iou_histograms.csv',hist);csvout(out/'pair_summary.csv',pair_stats)
    csvout(out/'label_contingency.csv',contingency);csvout(out/'matched_boxes.csv',matched)
    sizes=[]
    for tool in TOOLS:
        for cat in ['ALL']+sorted({category(r['raw_label']) for r in valid if r['tool']==tool}):
            v=[area(r['bbox_normalized']) for r in valid if r['tool']==tool and (cat=='ALL' or category(r['raw_label'])==cat)]
            sizes.append(dict(tool=tool,category=cat,n=len(v),q25=quant(v,.25),median=quant(v,.5),q75=quant(v,.75),p95=quant(v,.95)))
    csvout(out/'box_size_by_category.csv',sizes)
    groups=[];sens=[];page_metrics=[];clrecords=[];cluster_sens=[];atomrecords=[];patterns=defaultdict(list);pageevents=defaultdict(set)
    print('inputs verified; pairs and histograms ready',flush=True)
    for no,((pdf,idx),pr) in enumerate(sorted(pages.items())):
        pageevents[pdf,idx]
        paper=paper_name[pdf];vr=[r for r in pr if box_state(r.get('bbox_normalized'))=='valid'];pt={t:[r for r in vr if r['tool']==t] for t in TOOLS}
        context=dict(paper=paper,paper_sha256=pdf,page_idx=idx)
        for tool in TOOLS:
            for cat in {category(r['raw_label']) for r in pt[tool]}:pageevents[pdf,idx].add(f'{tool}:has:{cat}')
        cs=atoms(vr);sigareas=Counter()
        for c in cs:
            signature=json.dumps(c['categories'],sort_keys=True);sigareas[signature]+=c['area']
        for sig,v in sigareas.items():atomrecords.append(dict(**context,area=v,categories=json.loads(sig)))
        for a,b in PAIRS:
            u_a=sum(c['area'] for c in cs if a in c['tools']);u_b=sum(c['area'] for c in cs if b in c['tools']);inter=sum(c['area'] for c in cs if a in c['tools'] and b in c['tools']);union=u_a+u_b-inter
            catagree=sum(c['area'] for c in cs if a in c['tools'] and b in c['tools'] and c['categories'][a]==c['categories'][b])
            basegroups=None
            for contain in (.85,.9,.95):
                gs=components(pt[a],pt[b],contain)
                for threshold in (.85,.9,.95):
                    stats=Counter(group_metrics(x,y,threshold)['geometry_status'] for x,y in gs)
                    sens.append(dict(**context,tool_a=a,tool_b=b,containment=contain,union_threshold=threshold,components=len(gs),**dict(stats)))
                if contain==.9:basegroups=gs
            gg=[dict(**context,tool_a=a,tool_b=b,group_id=f'{pdf}:{idx}:{a}:{b}:{j}',**group_metrics(x,y,.9)) for j,(x,y) in enumerate(basegroups)]
            groups+=gg;counts=Counter(g['geometry_status'] for g in gg)
            pm=dict(**context,tool_a=a,tool_b=b,n_a=len(pt[a]),n_b=len(pt[b]),area_a=u_a,area_b=u_b,intersection=inter,union_area=union,area_jaccard=ratio(inter,union),a_only_area=u_a-inter,b_only_area=u_b-inter,category_set_equal_area=catagree,category_agreement_on_shared_area=ratio(catagree,inter),**dict(counts))
            page_metrics.append(pm)
            if u_a-inter>.005:pageevents[pdf,idx].add(f'{a}>{b}:extra_area')
            if u_b-inter>.005:pageevents[pdf,idx].add(f'{b}>{a}:extra_area')
            if counts['granularity_candidate']:pageevents[pdf,idx].add(f'{a}|{b}:granularity')
        for threshold in (.8,.9,.95):
            cc=clusters(vr,threshold)
            cluster_sens.append(dict(**context,iou_threshold=threshold,clusters=len(cc),multi_tool=sum(len(c)>1 for c in cc),four_tool=sum(len(c)==4 for c in cc),category_disagreement=sum(len(c)>1 and len({category(r['raw_label']) for r in c})>1 for c in cc)))
            if threshold!=.9:continue
            for j,g in enumerate(cc):
                labels={r['tool']:r['raw_label'] for r in g};cats={r['tool']:category(r['raw_label']) for r in g};bb=[r['bbox_normalized'] for r in g]
                med=[statistics.median(b[k] for b in bb) for k in range(4)];yc=(med[1]+med[3])/2;w=med[2]-med[0]
                band='top' if yc<.2 else 'bottom' if yc>=.8 else 'middle';width='narrow' if w<.35 else 'wide' if w>=.7 else 'medium'
                rec=dict(**context,cluster_id=f'{pdf}:{idx}:c{j}',ids=[r['analysis_uid'] for r in g],tools=sorted(labels),labels=labels,categories=cats,representative_bbox=med,vertical_band=band,width_band=width,label_entropy=entropy(list(labels.values())),category_entropy=entropy(list(cats.values())),category_disagreement=len(set(cats.values()))>1,min_pair_iou=min((overlap(a['bbox_normalized'],b['bbox_normalized'])['iou'] for a,b in itertools.combinations(g,2)),default=None))
                clrecords.append(rec)
                if len(g)>1:
                    signature=json.dumps(dict(labels=labels,band=band,width=width),sort_keys=True)
                    patterns[signature].append(rec)
                    if rec['category_disagreement']:pageevents[pdf,idx].add('any:category_disagreement')
                    for a,b in PAIRS:
                        if a in cats and b in cats and cats[a]!=cats[b]:pageevents[pdf,idx].add(f'{a}|{b}:category_disagreement')
        if no%80==0:print(f'pages {no+1}/{len(pages)}',flush=True)
    jsonlout(out/'granularity_groups.jsonl',groups);csvout(out/'granularity_sensitivity.csv',sens)
    csvout(out/'page_metrics.csv',page_metrics);jsonlout(out/'spatial_clusters.jsonl',clrecords);csvout(out/'cluster_sensitivity.csv',cluster_sens)
    jsonlout(out/'atomic_area_signatures.jsonl',atomrecords)
    aggregate=[]
    for a,b in PAIRS:
        for paper in ['ALL']+sorted(paper_name.values()):
            rr=[r for r in page_metrics if r['tool_a']==a and r['tool_b']==b and (paper=='ALL' or r['paper']==paper)]
            gg=[g for g in groups if g['tool_a']==a and g['tool_b']==b and (paper=='ALL' or g['paper']==paper)]
            u=sum(r['union_area'] for r in rr);inter=sum(r['intersection'] for r in rr)
            aggregate.append(dict(tool_a=a,tool_b=b,paper=paper,pages=len(rr),area_jaccard_micro=ratio(inter,u),area_jaccard_mean_page=mean([r['area_jaccard'] for r in rr if r['area_jaccard'] is not None]),area_jaccard_p10=quant([r['area_jaccard'] for r in rr if r['area_jaccard'] is not None],.1),category_agreement_on_shared_area=ratio(sum(r['category_set_equal_area'] for r in rr),inter),a_only_page_area=sum(r['a_only_area'] for r in rr),b_only_page_area=sum(r['b_only_area'] for r in rr),**dict(Counter(g['geometry_status'] for g in gg)),**{'shape_'+k:v for k,v in Counter(g['shape'] for g in gg).items()}))
    csvout(out/'comparison_by_paper.csv',aggregate)
    recurring=[]
    for signature,rr in patterns.items():
        pc=Counter(r['paper'] for r in rr);unique_pages={(r['paper'],r['page_idx']) for r in rr}
        if len(unique_pages)<2:continue
        recurring.append(dict(signature=json.loads(signature),cases=len(rr),pages=len(unique_pages),papers=len(pc),support_pages=len(unique_pages)/len(pages),dominant_paper_fraction=max(pc.values())/len(rr),minimum_cases_leave_one_paper_out=len(rr)-max(pc.values()),category_disagreement=rr[0]['category_disagreement'],examples=[dict(paper=r['paper'],page_idx=r['page_idx'],cluster_id=r['cluster_id']) for r in rr[:8]],paper_counts=dict(pc)))
    recurring.sort(key=lambda r:(-r['papers'],-r['pages'],-r['cases']))
    jsonlout(out/'recurring_patterns.jsonl',recurring)
    # Predefined page-level antecedents, not exhaustive itemset fishing; preserve null/missing applicability.
    events=list(pageevents.values());eventcounts=Counter(x for e in events for x in e);rules=[]
    antecedents=[x for x,n in eventcounts.items() if ':has:' in x and n>=10]
    outcomes=[x for x,n in eventcounts.items() if (':category_disagreement' in x or ':granularity' in x or ':extra_area' in x) and n>=5]
    for x in sorted(antecedents):
        for y in sorted(outcomes):
            joint=sum(x in e and y in e for e in events)
            if joint<5:continue
            n=eventcounts[x];yn=eventcounts[y];paperstats=[]
            for pdf in paper_name:
                pe=[e for (p,i),e in pageevents.items() if p==pdf];nx=sum(x in e for e in pe);j=sum(x in e and y in e for e in pe)
                if nx:paperstats.append(dict(paper=paper_name[pdf],antecedent=nx,joint=j,confidence=j/nx))
            rules.append(dict(antecedent=x,consequent=y,n_pages=len(events),antecedent_pages=n,consequent_pages=yn,joint_pages=joint,support=joint/len(events),confidence=joint/n,lift=(joint/n)/(yn/len(events)),macro_paper_confidence=mean([p['confidence'] for p in paperstats]),paper_breakdown=paperstats,interpretation='exploratory_output_association_not_semantic_probability'))
    csvout(out/'page_association_rules.csv',rules)
    # Native categories without geometry remain explicitly unlocalizable.
    native=[]
    for (tool,label,level),count in Counter((r['tool'],r['raw_label'],r.get('native_level')) for r in rows if box_state(r.get('bbox_normalized'))!='valid').items():
        native.append(dict(tool=tool,label=label,level=level,count=count,spatial_evaluation='not_localized_no_parent_bbox_imputation'))
    csvout(out/'unlocalized_categories.csv',native)
    feedback_records=[]
    if feedback_bytes is not None:
        snapshot=json.loads(feedback_bytes);jsonout(out/'human_feedback_snapshot.json',snapshot)
        for ex in snapshot['examples']:
            if ex['archived']:continue
            for direction,s in [('negative',ex['negative'])]+[('preferred',s) for s in ex['positives']]:
                pr=pages[ex['paper_sha256'],ex['page_idx']];bb=s['rect'];hits=[];clipped=[]
                for r in pr:
                    if r['tool']!=s['tool'] or box_state(r.get('bbox_normalized'))!='valid':continue
                    v=overlap(bb,r['bbox_normalized'])
                    if v['intersection']:
                        b=r['bbox_normalized'];clipped.append([max(bb[0],b[0]),max(bb[1],b[1]),min(bb[2],b[2]),min(bb[3],b[3])]);hits.append(dict(id=r['analysis_uid'],label=r['raw_label'],region_fraction=v['fraction_a'],bbox_fraction=v['fraction_b']))
                feedback_records.append(dict(example_id=ex['id'],paper=ex['paper'],page_idx=ex['page_idx'],direction=direction,tool=s['tool'],reasons=ex['reasons'],note=ex['note'],roi=bb,roi_box_area_fraction=union_area(clipped)/area(bb),intersecting_detections=hits,interpretation='selected_preference_not_exhaustive_truth'))
    jsonlout(out/'human_feedback_context.jsonl',feedback_records)
    # Compact summary and a stratified review queue with concrete source identities.
    review=[]
    for status in sorted({g['geometry_status'] for g in groups}):
        candidates=[g for g in groups if g['geometry_status']==status]
        candidates.sort(key=lambda g:(g['tool_a'],g['tool_b'],g['paper'],g['page_idx']))
        chosen=set()
        for g in candidates:
            key=g['tool_a'],g['tool_b'],g['paper']
            if key in chosen:continue
            chosen.add(key);review.append(dict(**g,review_question='¿Mismo contenido y límites válidos? ¿Caption relacionado? Geometría sola no decide.'))
    jsonlout(out/'review_examples.jsonl',review)
    summary=dict(papers=len(paper_name),pages=len(pages),detections=len(rows),valid_boxes=len(valid),pairs=pair_stats,
                 comparisons=[r for r in aggregate if r['paper']=='ALL'],spatial_clusters=len(clrecords),multi_tool_clusters=sum(len(r['tools'])>1 for r in clrecords),
                 category_disagreement_clusters=sum(r['category_disagreement'] for r in clrecords),recurring_patterns=len(recurring),human_active_examples=len({r['example_id'] for r in feedback_records}),
                 semantic_precision=None,semantic_coverage=None,semantic_granularity_only=None)
    jsonout(out/'summary.json',summary)
    changed={p:dict(before=h,after=sha(p)) for p,h in before.items() if sha(p)!=h}
    feedback_changes={p:v for p,v in changed.items() if p==str(feedback.resolve())}
    changed={p:v for p,v in changed.items() if p!=str(feedback.resolve())}
    if changed:raise RuntimeError('Consumed input changed: '+str(changed))
    bad_after=[r['path'] for r in oldmanifest if sha(r['path'])!=r['sha256']]
    if bad_after:raise RuntimeError('Original inputs changed: '+str(bad_after[:5]))
    jsonout(out/'verification.json',dict(original_manifest_verified=len(oldmanifest),consumed_input_hashes=before,consumed_inputs_changed=changed,feedback_changed_during_run=feedback_changes,elapsed_seconds=time.time()-started,source=str(SOURCE),protocol=str((BASE/'docs/methodology/geometry-protocol.md')),invariants=dict(histogram_total=sum(r['count'] for r in hist if r['paper']=='ALL' and r['scope']=='all_positive'),expected_positive_pairs=len(edges),pages=len(pages),tool_page_outputs=len(pages)*4)))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('pairs','comparisons')},indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();main(args.output)
