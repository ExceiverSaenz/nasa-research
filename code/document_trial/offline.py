"""Local evaluation scaffolding. Never imports a model or calls Colab."""
import argparse
import copy
import hashlib
import html
import json
from pathlib import Path
import re
import zipfile
from .common import DOCUMENT,PAGE3,MODELS,ROOT,box,read,save,sha,validate_bundle

CONTAINERS={'table','chart','image','code','list','index'}
LABELS={'table_body':'table','chart_body':'figure','image_body':'figure',
        'table_caption':'caption','chart_caption':'caption','image_caption':'caption','paragraph_title':'title'}

def reconcile(identity,native,alternatives):
    if len(native.get('pages',[]))!=1 or native['pages'][0]['page_idx']!=0:raise ValueError('One image-page expected')
    prefix=identity['document_sha256']+':'+identity.get('execution_id','offline-reference')+':p'+str(identity['physical_page'])+':'
    segments=[];containers=[];relations=[];object_links=[]
    def visit(block,rid,pointer,parent=None):
        native_type=block['type'];container=native_type in CONTAINERS
        # Null geometry is preserved as an incident, not silently discarded.
        bbox=None if block.get('bbox') is None else box(block['bbox'],identity['width_px'],identity['height_px'])
        item=dict(id=prefix+rid,local_id=rid,type=LABELS.get(native_type,native_type),bbox=bbox,
            native_content=copy.deepcopy(block),source_pointer=pointer,
            geometry_status='missing_native_geometry' if bbox is None else 'native_unchanged',
            native_index=block.get('index'),status='selected_provisional' if not container else 'native_container_not_duplicate')
        (containers if container else segments).append(item)
        if parent:relations.append(dict(parent=prefix+parent,child=item['id'],type='native_parent_child',status='native_not_independently_verified'))
        if container:
            children=block.get('content',[])
            if not isinstance(children,list):raise ValueError('Container has no valid native child list')
            for i,child in enumerate(children):visit(child,rid+'-c'+str(i),pointer+'/content/'+str(i),rid)
            object_links.append(dict(object=item['id'],components=[prefix+rid+'-c'+str(i) for i in range(len(children))],
                label_status='not_determined_requires_visual_reference',links_verified=False))
    for i,block in enumerate(native['pages'][0]['blocks']):visit(block,'p0-b'+str(i),'/pages/0/blocks/'+str(i))
    evidence=[]
    for model,records in sorted(alternatives.items()):
        for i,record in enumerate(records):
            evidence.append(dict(id=prefix+model+':'+str(i),model=model,native_record=copy.deepcopy(record),
                status='pending_unassociated_evidence',reason='Same page evidence only; no identity implied by overlap, class, proximity or score'))
    return dict(schema_version='document-reconciliation/1',identity=identity,segments=segments,containers=containers,
        relations=relations,object_links=object_links,evidence=evidence,accepted_external_content=[],
        native_reading_indices_preserved=True,reading_order_verified=False,
        policy='MinerU structure; TATR table evidence; LM support; abstain until explicit evidence-based adjudication',
        improvements_claimed=False)

def compare_reference(reference,observed):
    def material(result):return {x['local_id']:(x['bbox'],x['type'],x['native_content']) for x in result['segments']+result['containers']}
    a=material(reference);b=material(observed)
    return dict(selected_content_equal=a==b,missing_local_ids=sorted(set(a)-set(b)),new_local_ids=sorted(set(b)-set(a)),
        changed_local_ids=sorted(k for k in set(a)&set(b) if a[k]!=b[k]),
        note='Exact representation regression, not GT or OCR accuracy. Historical Table2 acceptance is immutable and source-specific.')

def review_template(identity,reconciled):
    return dict(identity=identity,status='pending_agent_or_human_visual_inventory',manual_units=[],
        whole_page_inventory_complete=False,reviewer=None,page_is_blank=False,
        unit_contract={'id':'page-local manual reference ID','evidence':['render region / native member+pointer'],
            'conditions':{c:{'presence':'present|partial|missing|indeterminate',
                **{d:'correct|incorrect|partial|indeterminate|not_applicable' for d in ('classification','separation','geometry','linkage','duplicates')}} for c in ('M0','M1','R')}},
        annotation_kind='manual_reference_pending_human_review_not_independent_GT',
        review_dimensions=['coverage_omissions','duplicates','classification_separation','geometry_cuts',
                           'body_label_description_links','reading_order_continuity','changed_transcription_table_structure'],
        label_cases=[],label_recurrence_rate=None,
        label_case_fields=['kind','visible_literal','render_bbox','native_members_and_pointers_inspected','recognized_literal',
                           'recognition_status','association_status','ambiguity','failure_stage_known_or_unknown','evidence_class'],
        label_statuses=['recognized_linked','recognized_unlinked','ambiguous','not_located_in_inspected_fields','not_evaluated'],
        conditions=['M0_original_mineru','M1_only_previously_accepted_localized_enrichment','R_reconciliation'],
        adjudications=[],changes=[],reading_cases=[],continuity_cases=[],transcription_table_cases=[],limitations=[],
        warnings=['No recovery or numerical label inference by order/proximity',
            'No recurrence denominator until visible labels are inventoried; raw search hits are not correctness or omissions'])

def native_text_fields(value,pointer=''):
    result=[]
    if isinstance(value,dict):
        for key in ('text','content','latex'):
            literal=value.get(key)
            if isinstance(literal,str) and not literal.startswith('data:image'):
                result.append(dict(pointer=pointer+'/'+key,literal=literal))
        for k,v in value.items():
            if k not in ('image_base64','image_path','image_url') and isinstance(v,(dict,list)):result+=native_text_fields(v,pointer+'/'+k)
    elif isinstance(value,list):
        for i,v in enumerate(value):result+=native_text_fields(v,pointer+'/'+str(i))
    return result

def evaluate(package,result,sidecar,output):
    output=Path(output)
    if output.exists():raise FileExistsError('New evaluation directory required')
    package=Path(package);plan=validate_bundle(package/'upload.zip',package/'upload.sha256')
    result_digest=sha(result)
    if result_digest!=Path(sidecar).read_text().strip():raise ValueError('Downloaded result hash mismatch')
    with zipfile.ZipFile(result) as z,zipfile.ZipFile(package/'upload.zip') as p:
        if z.testzip() is not None or len(z.namelist())!=len(set(z.namelist())):raise ValueError('Invalid result ZIP')
        if z.read('plan.json')!=p.read('plan.json'):raise ValueError('Returned plan differs')
        terminal=json.loads(z.read('execution-status.json'))
        if terminal['status'] not in ('completed','failed'):raise ValueError('Not terminal')
        output.mkdir(parents=True)
        summary=[]
        index=[]
        for page in plan['physical_pages']:
            prefix='pages/%04d/'%page;destination=output/('page-%04d'%page)
            statuses={m:json.loads(z.read(prefix+m+'/status.json')) for m in MODELS}
            names=set(z.namelist())
            if prefix+'identity.json' not in names or prefix+'mineru/middle-native.json' not in names:
                reason='Missing canonical render identity or MinerU native output; execution failure is not an omission verdict'
                template=review_template(dict(document_sha256=DOCUMENT,physical_page=page),None)
                template['not_evaluable_reason']=reason
                save(destination/'review-template.json',template)
                save(destination/'execution-statuses.json',statuses)
                (destination/'review.html').write_text('<!doctype html><meta charset="utf-8"><h1>Página '+str(page)+'</h1><p>'+reason+'</p>',encoding='utf-8')
                index.append('<li><a href="page-%04d/review.html">Página %d: no evaluable</a></li>'%(page,page))
                summary.append(dict(page=page,status='not_evaluable_missing_render_or_native',branches=statuses));continue
            identity=json.loads(z.read(prefix+'identity.json'));render=z.read(prefix+'render.png')
            if identity['physical_page']!=page or identity['document_sha256']!=DOCUMENT or hashlib.sha256(render).hexdigest()!=identity['render_sha256']:raise ValueError('Page/render identity mismatch')
            import io
            from PIL import Image
            with Image.open(io.BytesIO(render)) as image:
                if image.size!=(identity['width_px'],identity['height_px']):raise ValueError('Declared render dimensions differ')
            alternatives={}
            for model in ('table_transformer','layoutlmv3'):
                name=prefix+model+'/regions.json'
                alternatives[model]=json.loads(z.read(name))['regions'] if name in names else []
            native=json.loads(z.read(prefix+'mineru/middle-native.json'))
            reconciled=reconcile(identity,native,alternatives)
            save(destination/'M0-native.json',native)
            save(destination/'source-manifest.json',dict(identity=identity,result_archive_sha256=result_digest,
                members={name:hashlib.sha256(z.read(name)).hexdigest() for name in sorted(names) if name.startswith(prefix) and name.endswith(('.json','.md'))},
                note='Pointers in R are relative to the corresponding MinerU middle-native member; preserve member hash and archive identity.'))
            # This sidecar never changes historical acceptance or infers new labels.
            enrichment=dict(status='no_accepted_localized_enrichment_for_this_page',accepted_components=[])
            regression=None
            if page==3:
                historical=json.loads(p.read('regression/original-middle.json'))
                baseline=reconcile(identity,historical,{})
                regression=compare_reference(baseline,reconciled)
                regression['render_matches']=identity['render_sha256']==PAGE3
                accepted=json.loads(p.read('regression/accepted-table2.json'))
                save(destination/'historical-table2-acceptance.json',accepted)
                eligible=regression['selected_content_equal'] and regression['render_matches']
                enrichment=dict(status='historical_enrichment_carried_with_exact_regression' if eligible else 'pending_new_run_regression_review_historical_acceptance_unchanged',
                    table1='pending_warning',historical_table2_acceptance='historical-table2-acceptance.json',
                    accepted_components=[accepted] if eligible else [],source_specific_not_new_recovery=True)
                save(destination/'regression.json',regression)
            reconciled['localized_enrichment']=copy.deepcopy(enrichment)
            save(destination/'M1-enrichment.json',enrichment);save(destination/'R-reconciled.json',reconciled)
            save(destination/'review-template.json',review_template(identity,reconciled))
            # Inspect existing native exports, including nested lines/spans where present.
            scans=[];inspected_fields=[]
            for name in sorted(names):
                if name.startswith(prefix+'mineru/') and name.endswith(('.json','.md')):
                    raw=z.read(name)
                    if name.endswith('.json'):
                        fields=native_text_fields(json.loads(raw))
                        inspected_fields.append(dict(member=name,json_pointers=[f['pointer'] for f in fields],text_keys=['content','text','latex']))
                        for f in fields:
                            if re.search(r'\b(?:table|fig(?:ure)?\.?)\s*\d+',f['literal'],re.I):scans.append(dict(member=name,member_sha256=hashlib.sha256(raw).hexdigest(),**f))
                        # Split native spans/lines may carry Table and 1 separately.
                        # Preserve joined hits as ambiguous search evidence, never associations.
                        combined='';spans=[]
                        for f in fields:
                            start=len(combined);combined+=f['literal']+'\n';spans.append((start,len(combined),f['pointer']))
                        for hit in re.finditer(r'\b(?:table|fig(?:ure)?\.?)\s*\d+',combined,re.I):
                            pointers=[ptr for start,end,ptr in spans if start<hit.end() and end>hit.start()]
                            if len(pointers)>1:scans.append(dict(member=name,pointers=pointers,literal=hit.group(),status='ambiguous_joined_native_fields_not_an_association'))
                    else:
                        lines=raw.decode('utf-8').splitlines();inspected_fields.append(dict(member=name,line_count=len(lines)))
                        for i,line in enumerate(lines,1):
                            if re.search(r'\b(?:table|fig(?:ure)?\.?)\s*\d+',line,re.I):scans.append(dict(member=name,line=i,literal=line))
            save(destination/'label-search-evidence.json',dict(status='search_candidates_not_label_correctness',hits=scans,
                inspected_fields=inspected_fields,
                inspected_members=[name for name in sorted(names) if name.startswith(prefix+'mineru/') and name.endswith(('.json','.md'))],
                absence_claim='No missing-label conclusion without visual inventory; no search hit is automatically associated'))
            (destination/'render.png').write_bytes(render)
            rows=''.join('<tr><td>'+html.escape(s['local_id'])+'</td><td>'+html.escape(s['type'])+'</td><td>'+html.escape(str(s['bbox']))+'</td></tr>' for s in reconciled['segments'])
            (destination/'review.html').write_text('<!doctype html><meta charset="utf-8"><h1>Página '+str(page)+'</h1><p>Revisión visual pendiente. MinerU base; alternativas no aceptadas automáticamente. Table1 página3 pendiente; aceptación Table2 conservada con procedencia.</p><img src="render.png" style="max-width:100%"><table>'+rows+'</table>',encoding='utf-8')
            summary.append(dict(page=page,status='offline_prepared_visual_evaluation_pending',branches=statuses,
                selected_segments=len(reconciled['segments']),containers=len(reconciled['containers']),pending_external_evidence=len(reconciled['evidence']),
                original_vs_reconciled_content='same_base_plus_only_eligible_historical_enrichment',regression=regression))
            index.append('<li><a href="page-%04d/review.html">Página %d</a></li>'%(page,page))
        (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><h1>SiC12: evaluación visual pendiente</h1><p>Sin aceptación automática ni recuperación adicional. Ver document-status.json para páginas fallidas/no evaluables.</p><ul>'+''.join(index)+'</ul>',encoding='utf-8')
        save(output/'document-status.json',dict(status='pending_manual_evaluation_not_quality_accepted',pages=summary,
            accounted_pages=len(summary),expected_pages=plan['page_count'],terminal_execution=terminal,
            automatic_recovery_executed=False,recurrence={'rate':None,'reason':'Visible label inventory not yet reviewed'},
            next='Complete review templates, adjudicate explicitly, compute per-page and document comparisons; no new OCR'))
        save(output/'manifest.json',dict(plan=plan,result_sha256=result_digest,bundle_sha256=sha(package/'upload.zip'),
            outputs={x.relative_to(output).as_posix():sha(x) for x in output.rglob('*') if x.is_file()}))
    return summary

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--package',required=True);a.add_argument('--result',required=True);a.add_argument('--sidecar',required=True);a.add_argument('--output',required=True);args=a.parse_args()
    print('Pages accounted:',len(evaluate(args.package,args.result,args.sidecar,args.output)))
