"""Local whitespace XY-cut proposals. No image processing or model imports."""
import hashlib
import json
import math

CONFIG={'vertical_gap':.025,'horizontal_gap':.012,'column_transition_dx':.15,'direction':'ltr_assumed'}


def valid_box(b,w,h):
    return (isinstance(b,list) and len(b)==4 and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in b)
            and 0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h)


def key(item):
    b=item.get('box')
    # IDs are only the final technical tie break for truly indistinguishable units.
    return (*(b or [float('inf')]*4)[1::-1],*(b or [float('inf')]*4)[2:],hashlib.sha256(item.get('text','').encode()).hexdigest(),item['id'])


def gaps(items,axis):
    ranges=sorted((x['box'][axis],x['box'][axis+2]) for x in items)
    end=ranges[0][1];result=[]
    for low,high in ranges[1:]:
        if low>end:result.append((low-end,(low+end)/2))
        end=max(end,high)
    return result


def xy_order(items):
    if not items:return dict(order=[],fallback_ids=[],alternatives=[],tree={'kind':'empty'})
    if len(items)==1:return dict(order=[items[0]['id']],fallback_ids=[],alternatives=[],tree={'kind':'leaf','units':[items[0]['id']]})
    invalid=[x for x in items if x.get('box') is None]
    if invalid:
        valid=[x for x in items if x.get('box') is not None];r=xy_order(valid)
        tail=sorted(invalid,key=key)
        r['order'] += [x['id'] for x in tail];r['fallback_ids'] += [x['id'] for x in tail]
        r['alternatives'].append(dict(reason='unlocated_units_at_page_end',unit_refs=[x['id'] for x in tail]))
        r['tree']=dict(kind='located_then_pending',located=r['tree'],pending=[x['id'] for x in tail]);return r
    for axis,threshold,name in [(0,CONFIG['vertical_gap'],'columns'),(1,CONFIG['horizontal_gap'],'bands')]:
        candidates=[g for g in gaps(items,axis) if g[0]>=threshold]
        if not candidates:continue
        _,cut=max(candidates,key=lambda g:(g[0],-g[1]))
        left=[x for x in items if x['box'][axis+2]<=cut];right=[x for x in items if x['box'][axis]>=cut]
        if not left or not right or len(left)+len(right)!=len(items):continue
        a,b=xy_order(left),xy_order(right)
        return dict(order=a['order']+b['order'],fallback_ids=a['fallback_ids']+b['fallback_ids'],
                    alternatives=a['alternatives']+b['alternatives'],tree=dict(kind=name,split=cut,first=a['tree'],second=b['tree']))
    ordered=sorted(items,key=key);alternative=sorted(items,key=lambda x:(x['box'][0],x['box'][1],key(x)))
    return dict(order=[x['id'] for x in ordered],fallback_ids=[x['id'] for x in ordered],
                alternatives=[dict(reason='no_clear_whitespace_cut',chosen=[x['id'] for x in ordered],alternative=[x['id'] for x in alternative])],
                tree=dict(kind='fallback_physical',units=[x['id'] for x in ordered]))


def graph_order(initial,constraints):
    """Prefer explicit retained constraints; suspend cycles, retain their evidence."""
    rank={x:i for i,x in enumerate(initial)};edges={x:set() for x in initial};active=[];suspended=[]
    def reaches(start,target):
        todo=[start];seen=set()
        while todo:
            x=todo.pop()
            if x==target:return True
            if x in seen:continue
            seen.add(x);todo.extend(edges[x])
        return False
    stable=sorted(constraints,key=lambda e:(rank.get(e['from'],float('inf')),rank.get(e['to'],float('inf')),json.dumps(e,sort_keys=True)))
    for edge in stable+[dict(**{'from':a,'to':b},basis='geometry_proposal') for a,b in zip(initial,initial[1:])]:
        a,b=edge['from'],edge['to']
        if a==b:continue
        if a not in rank or b not in rank:raise ValueError('constraint endpoint absent')
        if reaches(b,a):suspended.append(dict(edge=edge,reason='cycle_or_competing_precedence'));continue
        edges[a].add(b);active.append(edge)
    degree={x:0 for x in initial}
    for children in edges.values():
        for x in children:degree[x]+=1
    ordered=[]
    while len(ordered)<len(initial):
        available=[x for x in initial if degree[x]==0 and x not in ordered]
        if not available:raise ValueError('operational cycle')
        x=min(available,key=rank.get);ordered.append(x)
        for y in edges[x]:degree[y]-=1
    return ordered,active,suspended
