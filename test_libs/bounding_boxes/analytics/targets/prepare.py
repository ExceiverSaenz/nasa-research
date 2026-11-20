"""Census and directed visual sample. Uses existing PNGs, no PDF render."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import sys,json,csv,statistics
from pathlib import Path
from collections import defaultdict,Counter
from analytics.geometry.run import SOURCE,BASE,TOOLS,PAIRS,readlines,csvout,jsonout,jsonlout,sha
from analytics.geometry.metrics import box_state,overlap
from analytics.targets.targets import family,pair_agreement
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

DEEP=BASE/'raw_results/analytics/deep-20261101-v2'
OUT=BASE/'raw_results/analytics/targets-20261101-v1'

def main():
    OUT.mkdir(exist_ok=False)
    files=[SOURCE/'detections.jsonl',SOURCE/'page_inventory.csv',DEEP/'block_spatial_clusters.jsonl',DEEP/'coincident_boxes.jsonl',BASE/'raw_results/feedback/session-v1/feedback.json',Path(__file__),Path(__file__).with_name('targets.py'),(BASE/'docs/methodology/targets-protocol.md')]
    hashes={str(p.resolve()):sha(p) for p in files};rows=readlines(SOURCE/'detections.jsonl');byid={r['analysis_uid']:r for r in rows}
    names={};pagecount=defaultdict(set)
    with (SOURCE/'page_inventory.csv').open(encoding='utf-8') as f:
        for r in csv.DictReader(f):names[r['paper_sha256']]=r['paper'];pagecount[r['paper']].add(int(r['page_idx']))
    for r in rows:r['paper']=names[r['paper_sha256']]
    census=Counter((r['tool'],r['paper'],r['raw_label'],family(r['raw_label']),r.get('native_level'),box_state(r.get('bbox_normalized'))) for r in rows)
    csvout(OUT/'target_census.csv',[dict(tool=t,paper=p,label=l,family=f,level=v,geometry=g,count=n) for (t,p,l,f,v,g),n in sorted(census.items(),key=str)])
    cs=readlines(DEEP/'block_spatial_clusters.jsonl');pairrows=[]
    for a,b in PAIRS:
        for c in cs:
            if a not in c['labels'] or b not in c['labels']:continue
            la,lb=c['labels'][a],c['labels'][b]
            pairrows.append(dict(tool_a=a,tool_b=b,paper=c['paper'],page_idx=c['page_idx'],cluster_id=c['cluster_id'],label_a=la,label_b=lb,family_a=family(la),family_b=family(lb),agreement=pair_agreement([la],[lb]),ids=c['ids']))
    csvout(OUT/'target_correspondences.csv',pairrows)
    patterns=[]
    for (a,b,la,lb),n in Counter((r['tool_a'],r['tool_b'],r['label_a'],r['label_b']) for r in pairrows).items():
        rr=[r for r in pairrows if (r['tool_a'],r['tool_b'],r['label_a'],r['label_b'])==(a,b,la,lb)];ps=Counter(r['paper'] for r in rr)
        patterns.append(dict(tool_a=a,tool_b=b,label_a=la,label_b=lb,family_a=family(la),family_b=family(lb),cases=n,pages=len({(r['paper'],r['page_idx']) for r in rr}),papers=len(ps),dominant_paper_share=max(ps.values())/n,macro_page_support=sum(len({r['page_idx'] for r in rr if r['paper']==p})/len(v) for p,v in pagecount.items())/len(pagecount),examples=[dict(paper=r['paper'],page_idx=r['page_idx'],cluster_id=r['cluster_id']) for r in rr[:6]]))
    csvout(OUT/'target_patterns.csv',sorted(patterns,key=lambda r:(-r['papers'],-r['cases'])))
    duplicates=readlines(DEEP/'coincident_boxes.jsonl');amb=[]
    for g in duplicates:
        fs={family(x) for x in g['labels']}
        if len(fs-{None})>1:amb.append(dict(**g,families=sorted(str(x) for x in fs),status='same_geometry_multiple_targets_not_automatically_error'))
    jsonlout(OUT/'same_box_target_conflicts.jsonl',amb)
    selected=[];keys=set()
    def add(pdf,idx,bb,stratum,source):
        k=(pdf,idx,tuple(round(v,4) for v in bb))
        if k in keys:return False
        keys.add(k);selected.append(dict(case_id=f'T{len(selected)+1:03}',paper=names[pdf],paper_sha256=pdf,page_idx=idx,roi=bb,stratum=stratum,source=source));return True
    for c in cs:
        fs={family(x) for x in c['labels'].values()}
        if ('heading' in fs and 'text' in fs) or ('caption' in fs and 'text' in fs) or ('visual' in fs and 'text' in fs):
            bb=[byid[i]['bbox_normalized'] for i in c['ids']];roi=[statistics.median(b[k] for b in bb) for k in range(4)];add(c['paper_sha256'],c['page_idx'],roi,'priority_disagreement',c['cluster_id'])
    for desired in ('heading','text','caption','visual','table','equation','reference','list'):
        seen=set()
        for c in cs:
            fs={family(x) for x in c['labels'].values()}
            if fs!={desired} or c['paper'] in seen:continue
            bb=[byid[i]['bbox_normalized'] for i in c['ids']];roi=[statistics.median(b[k] for b in bb) for k in range(4)]
            if add(c['paper_sha256'],c['page_idx'],roi,'control_'+desired,c['cluster_id']):seen.add(c['paper'])
            if len(seen)==3:break
    logos=[c for c in cs if 'picture' in c['labels'].values() and 'header' in c['labels'].values()]
    for c in logos:
        bb=[byid[i]['bbox_normalized'] for i in c['ids']];add(c['paper_sha256'],c['page_idx'],[statistics.median(b[k] for b in bb) for k in range(4)],'logo_header_pattern',c['cluster_id'])
    fb=json.loads((BASE/'raw_results/feedback/session-v1/feedback.json').read_text(encoding='utf-8'));jsonout(OUT/'feedback_snapshot.json',fb)
    for e in fb['examples']:
        if not e['archived']:add(e['paper_sha256'],e['page_idx'],e['negative']['rect'],'human_selected',e['id'])
    jsonlout(OUT/'visual_cases.jsonl',selected)
    for offset in range(0,len(selected),8):
        fig,axes=plt.subplots(4,2,figsize=(15,14));imagehashes={}
        for ax,c in zip(axes.flat,selected[offset:offset+8]):
            path=BASE/'raw_results/code/mineru-nativefix-20261101T034122Z/viewer_source/pages'/c['paper_sha256']/f"{c['page_idx']}.png";imagehashes[str(path.resolve())]=sha(path);img=plt.imread(path);b=c['roi'];padx=.035;pady=.025
            ax.imshow(img,extent=(0,1,1,0));ax.set_xlim(max(0,b[0]-padx),min(1,b[2]+padx));ax.set_ylim(min(1,b[3]+pady),max(0,b[1]-pady));ax.set_title(f"{c['case_id']} · {c['paper']} p{c['page_idx']+1}",fontsize=12);ax.axis('off')
        for ax in list(axes.flat)[len(selected[offset:offset+8]):]:ax.axis('off')
        fig.suptitle('Referencia visual del agente · etiquetas de herramientas ocultas',fontsize=14);fig.tight_layout();fig.savefig(OUT/f'contact_{offset//8+1:02}.png',dpi=120);plt.close(fig);hashes.update(imagehashes)
    assert all(sha(p)==h for p,h in hashes.items())
    jsonout(OUT/'prepare_verification.json',dict(input_hashes=hashes,unchanged=True,cases=len(selected),sample_strata=dict(Counter(c['stratum'] for c in selected)),pages=len({(c['paper'],c['page_idx']) for c in selected}),papers=len({c['paper'] for c in selected})))
    print(json.dumps(dict(cases=len(selected),strata=dict(Counter(c['stratum'] for c in selected))),indent=2))

if __name__=='__main__':main()
