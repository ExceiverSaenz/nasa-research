"""One verified offline export; no classification, models, OCR, or network."""
import argparse
import hashlib
import json
from pathlib import Path
from collections import Counter,defaultdict
from .engine import order_document,VERSION


def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()


def write(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as stream:json.dump(data,stream,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')


def validate_result(result,source):
    original={u['id']:u for u in source['regions']+source.get('logical_units',[])}
    inv={u['unit_ref']:u for u in result['inventory']};steps={s['id']:s for s in result['steps']}
    if len(inv)!=len(result['inventory']):raise ValueError('duplicate inventory ids')
    if set(inv)!=set(original) or any(inv[id]['original_unit']!=u for id,u in original.items()):raise ValueError('inventory/source mutation')
    if len(steps)!=len(result['steps']):raise ValueError('duplicate step ids')
    reachable=[];positions={}
    for name,route in result['routes'].items():
        def expand(id,path):
            if id not in steps or id in path:raise ValueError('invalid/cyclic expansion')
            return [id]+[x for child in steps[id]['children'] for x in expand(child,path|{id})]
        expected=[x for root in route['sequence'] for x in expand(root,set())]
        if expected!=route['expanded_sequence']:raise ValueError('inconsistent route expansion')
        refs=route['expanded_sequence']
        if len(set(refs))!=len(refs) or not set(refs)<=set(steps):raise ValueError('invalid route references')
        rank={s:i for i,s in enumerate(refs)}
        positions.update({s:(name,i) for s,i in rank.items()});reachable.extend(refs)
        if not set(route.get('unit_refs',[]))<=set(inv):raise ValueError('unknown pending unit')
        for rel in result['relations']:
            if rel['type']=='precedes' and rel['from'] in rank and rel['to'] in rank and rank[rel['from']]>=rank[rel['to']]:raise ValueError('operational precedence violated')
    for s in steps.values():
        if s['unit_ref'] not in inv or not set(s['children'])<=set(steps) or not set(s['render_unit_refs'])<=set(inv):raise ValueError('step reference unresolved')
        if s['kind']=='reference' and (s.get('content_appearance_ref') not in steps or steps[s['content_appearance_ref']]['kind']!='content' or steps[s['content_appearance_ref']]['unit_ref']!=s['unit_ref']):raise ValueError('invalid shared appearance')
    if set(reachable)!=set(steps) or len(set(reachable))!=len(reachable):raise ValueError('orphan or multiply reachable step')
    for u in inv.values():
        appearance=u.get('appearance_ref')
        if appearance is not None and (appearance not in steps or steps[appearance]['unit_ref']!=u['unit_ref']):raise ValueError('invalid inventory appearance')
        if u['disposition'] is None:raise ValueError('missing disposition')
        if u['disposition'] in ('content','structural_step','structural_placeholder','unlocated_reference') and appearance is None:raise ValueError('required appearance missing')
        for ref in u.get('reference_visits',[]):
            if ref not in steps or steps[ref]['kind']!='reference' or steps[ref]['unit_ref']!=u['unit_ref']:raise ValueError('invalid reference visit')
        if u['disposition']=='deferred_child_reference':
            parent=steps.get(u.get('parent_step_ref'))
            if not parent or parent['kind']!='deferred_structure' or u['unit_ref'] not in parent['deferred_child_refs'] or appearance is not None:raise ValueError('invalid deferred child')
    for edge in result['relations']:
        ids=steps if edge.get('scope')=='steps' else inv
        if edge['from'] not in ids or edge['to'] not in ids:raise ValueError('unknown edge endpoint')
        if edge['type']=='precedes':
            a,b=positions[edge['from']],positions[edge['to']]
            if a[0]!=b[0] or a[1]>=b[1]:raise ValueError('invalid operational precedence')
        if edge['type']=='next_in_route':
            route=result['routes'][edge['route']]['expanded_sequence'];i=route.index(edge['from'])
            if i+1>=len(route) or route[i+1]!=edge['to']:raise ValueError('invalid adjacency')
    appearances=[s['unit_ref'] for s in steps.values() if s['kind']=='content']
    if len(set(appearances))!=len(appearances):raise ValueError('duplicate content')
    return True


def export_collection(source,destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError(destination)
    if source in destination.parents or destination in source.parents or source==destination:raise ValueError('separate destination required')
    protected={str(p):digest(p) for p in source.rglob('*') if p.is_file()}
    manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    for name,sha in manifest['outputs'].items():
        p=(source/name).resolve()
        if source not in p.parents or digest(p)!=sha:raise ValueError('classification manifest integrity failed')
    summary=json.loads((source/'summary.json').read_text(encoding='utf-8'));docs=[];papers=set();identities=set()
    for item in summary['documents']:
        paper=item['paper'];p=(source/item['data']).resolve()
        if not isinstance(paper,int) or isinstance(paper,bool) or paper<1 or paper in papers or source not in p.parents:raise ValueError('invalid paper id or path')
        papers.add(paper)
        if item['data'] not in manifest['outputs']:raise ValueError('unmanifested input')
        d=json.loads(p.read_text(encoding='utf-8'))
        if d['paper_id'] in identities:raise ValueError('duplicate paper identity')
        identities.add(d['paper_id']);baseline=Path(d['source']['path'])
        if digest(baseline)!=d['source']['sha256']:raise ValueError('reconciliation changed')
        protected[str(baseline)]=d['source']['sha256'];docs.append((item,p,d))
    destination.mkdir(parents=True);totals=Counter();entries=[];warnings=defaultdict(list);continuity=Counter()
    for item,path,doc in docs:
        result=order_document(doc);validate_result(result,doc)
        result['classification_source']=dict(path=str(path),sha256=protected[str(path)],pointer='/')
        result['reconciliation_source']=doc['source'].copy()
        relative=f"papers/{item['paper']}/document.json";write(destination/relative,result)
        m=result['metrics'];totals.update({k:v for k,v in m.items() if isinstance(v,int)});totals['papers']+=1;totals['pages']+=len(doc['pages'])
        continuity.update(m['continuity_candidates'])
        for s in result['steps']:
            for w in s['warnings']:warnings[w['code']].append(dict(paper=item['paper'],step_ref=s['id'],unit_ref=s['unit_ref']))
        strata=defaultdict(Counter)
        for u in result['inventory']:
            c=u['original_unit']['classification'];cat=c['category']['value'] or 'unresolved';st=next((s for s in result['steps'] if s['id']==u.get('appearance_ref')),None)
            for key in ('category:'+cat,'kind:'+u['kind']):
                strata[key]['N']+=1;strata[key]['accounted']+=1
                strata[key]['pending_reference']+=u['disposition'] in ('deferred_child_reference','pending_group_reference','structural_reference','unlocated_reference')
                strata[key]['appearance_fallback']+=bool(st and st['order_basis']=='fallback')
        entries.append(dict(paper=item['paper'],data=relative,metrics=m,strata={k:dict(v) for k,v in strata.items()}))
    if any(digest(p)!=sha for p,sha in protected.items()):raise ValueError('protected sources modified')
    result=dict(schema_version=VERSION,**dict(totals),continuity_candidates=dict(continuity),documents=entries,
                semantic_validation='pending_after_full_mvp',accounting_coverage=1.0,models_executed=False,classification_executed=False)
    write(destination/'summary.json',result);write(destination/'review-queue.json',dict(review_stage='after_full_mvp',by_warning=dict(warnings)))
    write(destination/'manifest.json',dict(version=VERSION,protected_inputs=protected,protected_unchanged=True,
          outputs={p.relative_to(destination).as_posix():digest(p) for p in destination.rglob('*.json')},
          code={str(p):digest(p) for p in Path(__file__).parent.glob('*.py')}))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('destination');a=p.parse_args()
    result=export_collection(a.source,a.destination);print(json.dumps({k:v for k,v in result.items() if k!='documents'},ensure_ascii=False,indent=2))
