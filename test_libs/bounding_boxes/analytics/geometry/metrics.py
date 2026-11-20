"""Geometry-only exploratory measures. No semantic correctness inference."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import sys
import heapq
from pathlib import Path
from collections import defaultdict
from analytics.automatic.core import area, overlap, union_area, box_state

def category(label):
    mapping={
        'text':'text','list_item':'list_item','section_header':'section_heading',
        'paragraph_title':'section_heading','doc_title':'document_title',
        'caption':'caption','image_caption':'caption','chart_caption':'caption','table_caption':'caption',
        'picture':'visual','image':'visual','chart':'visual','table':'table',
        'formula':'equation','equation':'equation','equation_inline':'inline_equation',
        'header':'running_header','page_header':'running_header','footer':'running_footer',
        'page_footer':'running_footer','page_number':'page_number','document_index':'page_number',
        'index':'index','footnote':'footnote','page_footnote':'footnote','ref_text':'reference'}
    # Native document_index has uncertain semantics; preserve rather than merge with page_number.
    mapping['document_index']='document_index'
    return mapping.get(label,'unmapped:'+str(label))

def histogram(values):
    result=[0]*10
    for x in values:result[min(9,int(x*10))]+=1
    return result

def group_metrics(left,right,threshold):
    na,nb=len(left),len(right)
    ba=[r['bbox_normalized'] for r in left];bb=[r['bbox_normalized'] for r in right]
    ua,ub=union_area(ba),union_area(bb);u=union_area(ba+bb);i=max(0,ua+ub-u)
    shape='unmatched_b' if not na else 'unmatched_a' if not nb else '1:1' if na==nb==1 else '1:n' if na==1 else 'n:1' if nb==1 else 'n:m'
    out=dict(n_a=na,n_b=nb,shape=shape,area_a=ua,area_b=ub,union_iou=min(1,i/u) if u else None,
             covered_a=min(1,i/ua) if ua else None,covered_b=min(1,i/ub) if ub else None,
             ids_a=[r['analysis_uid'] for r in left],ids_b=[r['analysis_uid'] for r in right],
             categories_a=sorted({category(r['raw_label']) for r in left}),
             categories_b=sorted({category(r['raw_label']) for r in right}),semantic_status='not_determined')
    if not na or not nb:status='no_strong_correspondence'
    elif shape=='1:1':status='equivalent_box' if out['union_iou']>=threshold else 'boundary_or_extent_difference'
    elif shape=='n:m':status='complex_many_many'
    else:
        big=ba[0] if na==1 else bb[0];small=bb if na==1 else ba
        us=union_area(small);redundancy=(sum(map(area,small))-us)/us if us else 0
        out.update(small_side_redundancy=max(0,redundancy),largest_small_to_big=max(map(area,small))/area(big))
        status='granularity_candidate' if out['union_iou']>=threshold and redundancy<=.01 and out['largest_small_to_big']<.98 else 'split_merge_extent_or_redundancy'
    out['geometry_status']=status
    return out

def components(left,right,containment=.9):
    rows={r['analysis_uid']:r for r in left+right};parent={i:i for i in rows}
    def root(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    for a in left:
        for b in right:
            v=overlap(a['bbox_normalized'],b['bbox_normalized'])
            if v['iou']>=.5 or max(v['fraction_a'],v['fraction_b'])>=containment:
                parent[root(a['analysis_uid'])]=root(b['analysis_uid'])
    groups=defaultdict(list)
    for uid in rows:groups[root(uid)].append(rows[uid])
    lt={r['analysis_uid'] for r in left}
    return [([r for r in g if r['analysis_uid'] in lt],[r for r in g if r['analysis_uid'] not in lt]) for g in groups.values()]

def clusters(rows,threshold=.9):
    """Constrained complete-link, greedy best admissible merge, labels excluded."""
    groups={i:[r] for i,r in enumerate(rows)};edges=[]
    sims={}
    for i,a in enumerate(rows):
        for j in range(i+1,len(rows)):
            b=rows[j]
            if a['tool']==b['tool']:continue
            v=overlap(a['bbox_normalized'],b['bbox_normalized'])['iou'];sims[i,j]=v
            if v>=threshold:edges.append((-v,i,j))
    members={i:[i] for i in groups};heapq.heapify(edges);next_id=len(rows)
    while edges:
        _,x,y=heapq.heappop(edges)
        if x not in groups or y not in groups:continue
        merged=groups.pop(x)+groups.pop(y);mm=members.pop(x)+members.pop(y)
        z=next_id;next_id+=1;zt={r['tool'] for r in merged}
        for v,other in groups.items():
            if zt & {r['tool'] for r in other}:continue
            score=min(sims.get(tuple(sorted((u,w))),0) for u in mm for w in members[v])
            if score>=threshold:heapq.heappush(edges,(-score,v,z))
        groups[z]=merged;members[z]=mm
    return list(groups.values())

def atoms(rows):
    """Exact rectangle overlay; emits disjoint covered cells only."""
    xs=sorted({x for r in rows for x in (r['bbox_normalized'][0],r['bbox_normalized'][2])})
    cells=[]
    for x0,x1 in zip(xs,xs[1:]):
        active=[r for r in rows if r['bbox_normalized'][0]<x1 and r['bbox_normalized'][2]>x0]
        ys=sorted({y for r in active for y in (r['bbox_normalized'][1],r['bbox_normalized'][3])})
        for y0,y1 in zip(ys,ys[1:]):
            hit=[r for r in active if r['bbox_normalized'][1]<y1 and r['bbox_normalized'][3]>y0]
            if not hit:continue
            cats=defaultdict(set)
            for r in hit:cats[r['tool']].add(category(r['raw_label']))
            cells.append(dict(area=(x1-x0)*(y1-y0),tools=tuple(sorted(cats)),categories={k:tuple(sorted(v)) for k,v in cats.items()}))
    return cells
