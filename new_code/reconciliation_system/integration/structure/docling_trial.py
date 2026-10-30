"""Bounded rule-based Docling trial; no converters, OCR or neural imports."""
import argparse
import copy
import hashlib
import inspect
import json
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from integration.reading_order.export import digest,write,validate_result
from integration.reading_order.layout import valid_box

PIN='688402b548726963fa65c8af3647626ddfb70e42ece07c05893574c15bb05964'


def warn(code,reason=None):
    return dict(code=code,message='Requiere validación humana',reason=reason or code,review_stage='after_full_mvp')


def predict(items):
    import docling.models.postprocessing.reading_order_rb as rb
    from docling_core.types.doc.base import CoordOrigin,Size
    from docling_core.types.doc.document import RefItem
    from docling_core.types.doc.labels import DocItemLabel
    if version('docling')!='2.123.1' or digest(inspect.getfile(rb))!=PIN:raise ValueError('Docling version/source pin mismatch')
    labels={'text':DocItemLabel.TEXT,'title':DocItemLabel.SECTION_HEADER,'figure':DocItemLabel.PICTURE,
            'table':DocItemLabel.TABLE,'caption':DocItemLabel.CAPTION,'equation':DocItemLabel.FORMULA}
    elements=[];ids={}
    for i,x in enumerate(items):
        ids[i]=x['id'];l,t,r,b=x['bbox'];w,h=x['page_size']
        elements.append(rb.PageElement(cid=i,ref=RefItem(cref=f'#/texts/{i}'),text=x['text'],page_no=x['page'],
                        page_size=Size(width=w,height=h),label=labels.get(x['category'],DocItemLabel.TEXT),
                        l=l,t=h-t,r=r,b=h-b,coord_origin=CoordOrigin.BOTTOMLEFT))
    ordered=rb.ReadingOrderPredictor().predict_reading_order(elements)
    return [ids[e.cid] for e in ordered]


def reference_safe(order,steps):
    """Keep shared content appearance before reference, preserving capsule interiors."""
    roots={x:x for x in order}
    for x in order:
        for child in steps[x]['children']:roots[child]=x
    edges=set()
    for x in order:
        for child in steps[x]['children']:
            s=steps[child]
            if s['kind']=='reference':
                a=roots.get(s['content_appearance_ref'])
                if a is not None and a!=x:edges.add((a,x))
    result=[];remaining=list(order)
    while remaining:
        chosen=next((x for x in remaining if not any(b==x and a in remaining for a,b in edges)),None)
        if chosen is None:raise ValueError('cyclic shared reference ownership')
        result.append(chosen);remaining.remove(chosen)
    return result


def apply_docling(baseline,predict_fn=None):
    run=predict_fn or predict;out=copy.deepcopy(baseline);steps={s['id']:s for s in out['steps']}
    units={u['unit_ref']:u['original_unit'] for u in out['inventory']};pages={p['identity']['physical_page']:p for p in out['original_page_context']}
    out['baseline_evidence_relations']=copy.deepcopy(baseline['relations']);out['relations']=[]
    out['baseline_layouts']=out.pop('layouts',[]);out['baseline_decisions']=out.pop('decisions',[]);out['decisions']=[]
    out['baseline_metrics']=out.pop('metrics');out['baseline_config']=out.pop('config');out['config']=dict(component='Docling ReadingOrderPredictor',version='2.123.1',defaults_unchanged=True)
    batches=[]
    for rt,route in out['routes'].items():
        original=baseline['routes'][rt]['sequence'];new=[]
        for n in sorted({steps[x]['page'] for x in original}):
            ids=[x for x in original if steps[x]['page']==n];page=pages[n];ident=page['identity'];w,h=ident['width_px'],ident['height_px']
            crop=ident.get('geometry',{}).get('crop_box_pt',[0,0,w,h]);pw,ph=crop[2]-crop[0],crop[3]-crop[1]
            trace=dict(route=rt,page=n,baseline_order=ids,inputs=[],fallback=False);chosen=list(ids)
            try:
                if page.get('original_status')=='blocked' or 'invalid_geometry' in page.get('original_incidents',[]) or any(steps[x]['evidence_status']=='abstained' for x in ids):raise ValueError('geometry abstention preserved')
                for id in ids:
                    s=steps[id];refs=s.get('anchor_refs') or s['render_unit_refs'] or [s['unit_ref']]
                    boxes=[units[r].get('bbox_xyxy') for r in refs]
                    if not boxes or not all(valid_box(b,w,h) for b in boxes):raise ValueError('unlocated or invalid capsule anchor')
                    box=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
                    u=units[s['unit_ref']];c=u['classification']['category']['value']
                    trace['inputs'].append(dict(id=id,unit_ref=s['unit_ref'],anchor_refs=refs,
                        bbox=[box[0]*pw/w,box[1]*ph/h,box[2]*pw/w,box[3]*ph/h],page_size=[pw,ph],page=n,
                        category=c,text=u.get('original_record',{}).get('text',''),extent_is_ordering_only=True))
                neutral=sorted(trace['inputs'],key=lambda x:(x['bbox'][1],x['bbox'][0],x['id']))
                trace['input_order']=[x['id'] for x in neutral];raw=run(neutral);trace['docling_raw_order']=raw
                if len(raw)!=len(ids) or set(raw)!=set(ids):raise ValueError('invalid component permutation')
                chosen=reference_safe(raw,steps)
                if chosen!=raw:trace['warning']='shared_reference_precedence_override'
            except Exception as e:
                trace.update(fallback=True,error=f'{type(e).__name__}: {e}');chosen=list(ids)
            trace['chosen_order']=chosen;batches.append(trace);new.extend(chosen)
            for id in ids:
                s=steps[id];s['baseline_order_basis']=s['order_basis']
                s['order_basis']='fallback' if trace['fallback'] else 'docling_rule_based_proposal'
                if trace['fallback']:s['warnings'].append(warn('docling_batch_fallback',trace['error']))
                elif trace.get('warning'):s['warnings'].append(warn(trace['warning']))
        route['sequence']=new;route['expanded_sequence']=[s for id in new for s in [id]+steps[id]['children']]
        for a,b in zip(route['expanded_sequence'],route['expanded_sequence'][1:]):
            out['relations'].append(dict(type='next_in_route',scope='steps',**{'from':a,'to':b},route=rt,status='provisional_unvalidated'))
    positions={s:(rt,i) for rt,r in out['routes'].items() for i,s in enumerate(r['expanded_sequence'])}
    for rel in baseline['relations']:
        if rel['type']=='precedes' and rel.get('basis')=='retained_precedence':
            a,b=positions[rel['from']],positions[rel['to']]
            if a[0]!=b[0] or a[1]>=b[1]:
                out['suspended_constraints'].append(dict(edge=copy.deepcopy(rel),reason='docling_trial_conflicts_with_retained_precedence'))
                out['warnings'].append(warn('retained_precedence_conflict'))
            else:out['relations'].append(copy.deepcopy(rel))
    for s in out['steps']:s['warnings'].append(warn('docling_trial_unvalidated'))
    comparison=[]
    for rt,r in out['routes'].items():
        for n in sorted(pages):
            a=[x for x in baseline['routes'][rt]['expanded_sequence'] if steps[x]['page']==n and steps[x]['kind']=='content']
            b=[x for x in r['expanded_sequence'] if steps[x]['page']==n and steps[x]['kind']=='content'];rank={x:i for i,x in enumerate(b)}
            comparison.append(dict(route=rt,page=n,content=len(a),changed_positions=sum(x!=y for x,y in zip(a,b)),
                                   reversed_pairs=sum(rank[a[i]]>rank[a[j]] for i in range(len(a)) for j in range(i+1,len(a))),
                                   comparable_pairs=len(a)*(len(a)-1)//2))
    out['trial']=dict(component='Docling rule-based order only',batches=batches,comparison=comparison,
        baseline_classification_routes_groups_and_child_order_preserved=True,paragraph_continuation_recomputed=False,
        neural_models_executed=False,OCR_executed=False,semantic_improvement='not established; no adjudicated reference')
    out['metrics']=dict(inventory_units=len(out['inventory']),content_appearances=sum(s['kind']=='content' for s in out['steps']),
                        changed_content_positions=sum(r['changed_positions'] for r in comparison),reversed_pairs_vs_baseline=sum(r['reversed_pairs'] for r in comparison),
                        fallback_batches=sum(b['fallback'] for b in batches),steps_with_warnings=sum(bool(s['warnings']) for s in out['steps']))
    out['status']='docling_trial_provisional_unvalidated';out['schema_version']='docling-order-trial/1'
    out['warnings'].append(warn('classification_and_internal_orders_inherited_not_repaired'))
    return out


def export_trial(baseline_path,destination):
    path=Path(baseline_path).resolve();dest=Path(destination).resolve()
    if dest.exists():raise FileExistsError(dest)
    base=json.loads(path.read_text(encoding='utf-8'));protected={str(path):digest(path)}
    mpath=path.parents[2]/'manifest.json';m=json.loads(mpath.read_text(encoding='utf-8'))
    if m['outputs'].get(path.relative_to(mpath.parent).as_posix())!=digest(path):raise ValueError('baseline manifest mismatch')
    for key in ('classification_source','reconciliation_source'):
        ref=base[key];p=Path(ref['path']);protected[str(p)]=digest(p)
        if digest(p)!=ref['sha256']:raise ValueError(key+' hash mismatch')
    source=json.loads(Path(base['classification_source']['path']).read_text(encoding='utf-8'))
    result=apply_docling(base);validate_result(result,source)
    if result['inventory']!=base['inventory']:raise ValueError('inventory mutation')
    write(dest/'document.json',result);write(dest/'summary.json',dict(metrics=result['metrics'],comparison=result['trial']['comparison']))
    write(dest/'review-queue.json',dict(stage='after_full_mvp',steps=[dict(step_ref=s['id'],unit_ref=s['unit_ref'],warnings=s['warnings']) for s in result['steps']]))
    if any(digest(p)!=h for p,h in protected.items()):raise ValueError('source mutation')
    write(dest/'manifest.json',dict(protected=protected,outputs={p.name:digest(p) for p in dest.glob('*.json')},
          baseline_source=dict(path=str(path),sha256=digest(path)),docling_source_sha256=PIN,
          code={str(p):digest(p) for p in Path(__file__).parent.glob('docling*.py')},neural_models_executed=False,OCR_executed=False))
    return result['metrics']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('baseline');p.add_argument('destination');a=p.parse_args();print(json.dumps(export_trial(a.baseline,a.destination),indent=2))
