"""Conservative, offline reconciliation of the approved sic12 physical page 3.

This is an explicit page decision recipe, not a matcher trained on A03 groups.
No OCR, network, subprocesses, score ranking or new geometry are used.
"""
import argparse
import copy
import hashlib
import html
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[2]
PREPARED=Path('analytics/data/prepared/sic12_page3/p03-20261024/prepared.json')
ASSOCIATIONS=Path('analytics/results/sic12_page3/a03-20261024/associations.json')
TABLE2=Path('analytics/results/sic12_page3/table2-lines-v1/accepted/table2-lines.json')
RENDER=Path('code/results/layoutlmv3-page/20261023T153938Z/review/render.png')
RENDER_SHA='6f46d8ff2d05eee785739ec1c34716db14135411c731e7aa6433e27ca06d00b9'
DOCUMENT='9cea2fa5ad94c6a31031c72a9c3f698d571c85c810af644304c3b9f0d306f660'
TOLERANCES=dict(iou_min=.5,expanded_reference_coverage_min=.9,reference_expansion_px=2,roundtrip_max_px=1)
# Explicit decisions from A04/A05, not a conversion of every A03 group to identity.
# Each list gives separate output segments; 11 deliberately remains one-to-many.
TARGETS={
 'A02-01':['p0-b2-c1'],'A02-02':['p0-b4-c1'],
 'A02-03':['p0-b3-c0'],'A02-04':['p0-b9-c0'],
 'A02-05':['p0-b2-c0'],'A02-06':['p0-b4-c0'],
 'A02-07':['p0-b3-c1'],'A02-08':['p0-b9-c1'],
 'A02-09':['p0-b5'],'A02-10':['p0-b6'],
 'A02-11':['p0-b7','p0-b8'],'A02-12':['p0-b10'],
 'A02-13':['p0-b11'],'A02-14':['p0-b12'],'A02-15':['p0-b13'],
 'A02-16':['p0-b14'],'A02-17':['p0-b0'],'A02-18':['p0-b1']}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def key(d):return d['run_id']+'::'+str(d['source_region_id'])
def read(path):return json.loads(Path(path).read_bytes())
def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def pointer(value,location):
    for part in location.lstrip('/').split('/'):
        part=part.replace('~1','/').replace('~0','~')
        value=value[int(part)] if isinstance(value,list) else value[part]
    return value


def check_table2(t):
    if (t['page']['document_id']!=DOCUMENT or t['page']['render_sha256']!=RENDER_SHA
        or t['page']['physical_page']!=3 or t['scope']!=['p0-b4']
        or t['proposal']['object_id']!='p0-b4' or t['proposal']['caption_id']!='p0-b4-c0'
        or t['proposal']['body_id']!='p0-b4-c1' or not t['links_verified']
        or not t['labels_recovered'] or not t['visual_review_valid']
        or not t['parentage_verified'] or t['tolerances']!=TOLERANCES
        or not t['label_geometry']['passed']):
        raise ValueError('Table2 accepted identity, review or tolerances changed')


def build(prepared,associations,table2):
    check_table2(table2)
    p=copy.deepcopy(prepared)
    if len(p['rendered_pages'])!=1:raise ValueError('Single page only')
    page=p['rendered_pages'][0]
    if (page['document_id'],page['physical_page'],page['render_sha256'],page['width_px'],page['height_px'])!=(DOCUMENT,3,RENDER_SHA,1654,2205):
        raise ValueError('This recipe is approved only for sic12 page3')
    records=sorted(p['detections'],key=lambda d:(d['model'],str(d['source_region_id'])))
    lookup={key(d):d for d in records}
    if len(records)!=48 or len(lookup)!=48:raise ValueError('Missing or duplicated source')
    for d in records:
        if any(d[k]!=page[k] for k in ('document_id','physical_page','render_sha256')):
            raise ValueError('Source uses another document/page/frame')
    mineru={d['source_region_id']:d for d in records if d['model']=='mineru'}
    selected={d['source_region_id'] for d in mineru.values() if d['selected_for_analysis']}
    if selected!={v for values in TARGETS.values() for v in values}:raise ValueError('Page recipe/source mismatch')
    cases={c['case_id']:c for c in associations['associations']}
    if set(cases)!=set(TARGETS) or len(associations['associations'])!=18:raise ValueError('Case mismatch')
    sources=[dict(key=key(d),record=d,disposition='context_container' if not d['selected_for_analysis'] else
                  ('selected_structure' if d['model']=='mineru' else 'alternative_or_support')) for d in records]
    regions={rid:dict(id=rid,type=d['analysis_label'],bbox=copy.deepcopy(d['bbox_xyxy_px']),
                    geometry_source=key(d),status='selected_provisional',alternatives=[],
                    reason='Approved MinerU structural priority; exact source geometry, not a completeness claim',
                    boundary_status='not_certified') for rid,d in sorted(mineru.items()) if rid in selected}
    links=[];decisions=[]
    for cid,targets in sorted(TARGETS.items()):
        c=cases[cid]
        historical=copy.deepcopy(c)
        historical['members']=sorted(historical['members'],key=lambda m:(m['model'],str(m['source_region_id'])))
        native_targets=sorted(m['source_region_id'] for m in c['members'] if m['model']=='mineru' and m['role']=='region_candidate')
        if native_targets!=sorted(targets):raise ValueError('Case membership differs from explicit page decision')
        decisions.append(dict(case_id=cid,targets=targets,description=c['description'],
            status='unresolved_granularity' if cid=='A02-11' else 'selected_with_retained_alternatives',
            historical_ambiguous=c['ambiguous'],historical_evidence=historical,
            rule='Explicit page decision: select separate MinerU components; never union the A03 group',
            evidence_reports=['analytics/reports/sic12_page3-a04-completeness.md','analytics/reports/sic12_page3-a05-complementarity.md']))
        for m in sorted(c['members'],key=lambda m:(m['model'],str(m['source_region_id']))):
            k=key(m)
            if k not in lookup or m['bbox_xyxy_px']!=lookup[k]['bbox_xyxy_px']:raise ValueError('Case source mismatch')
            if m['model']=='mineru':continue
            role=m['role']
            if role=='mixed_scope_candidate':decision='retain_mixed_evidence_do_not_split'
            elif role=='caption_label_component':decision='retain_complementary_label_candidate_no_recovery_claim'
            elif role=='caption_description_component':decision='retain_description_component_not_whole_caption_duplicate'
            elif cid in ('A02-11','A02-12'):decision='retain_list_structure_hypothesis_not_verified_order'
            elif role=='partial_candidate':decision='retain_partial_alternative'
            elif role=='region_candidate':decision='retain_same_content_candidate_not_geometry_winner'
            else:raise ValueError('Unknown candidate role: '+role)
            item=dict(source=k,model=m['model'],role=role,case_id=cid,targets=targets,
                      decision=decision,status='pending',bbox=copy.deepcopy(m['bbox_xyxy_px']))
            links.append(item)
            for rid in targets:regions[rid]['alternatives'].append(copy.deepcopy(item))
    for rid in ('p0-b2-c1','p0-b4-c1'):regions[rid]['boundary_status']='unresolved'
    regions['p0-b12']['content_warning']='Original box includes preceding direction fragment; no clipping or text correction'
    containers=[dict(id=rid,source=key(d),bbox=copy.deepcopy(d['bbox_xyxy_px']),type=d['analysis_label'],
                     status='native_container_not_duplicate') for rid,d in sorted(mineru.items()) if rid not in selected]
    relations=[dict(parent=r['parent_source_region_id'],child=r['child_source_region_id'],
                    type='parent_child',status='native_preserved') for r in p['relations']]
    payload=dict(schema_version='reconciliation-page/1.0',page=page,scope='sic12 physical page3 only',
        policy=dict(priority=['mineru','table_transformer','layoutlmv3_support'],
                    automatic_matching=False,score_comparison=False,new_geometry=False,
                    unresolved_allowed=True,reading_order_verified=False),
        sources=sources,runs=p['runs'],incidents=p['incidents'],regions=list(regions.values()),containers=containers,
        native_relations=p['relations'],relations=relations,candidate_links=links,decisions=decisions,
        recovered_components=[dict(id='accepted-table2-label',parent='p0-b4',type='label',
            bbox=copy.deepcopy(table2['proposal']['selected_candidate']['label_line']['bbox']),
            text=table2['proposal']['selected_candidate']['label_text'],
            geometry_evidence=copy.deepcopy(table2['proposal']['selected_candidate']['label_line']),
            text_assignment='verified_by_existing_agent_visual_review',
            acceptance_source=TABLE2.as_posix(),status='accepted')],
        tables={'p0-b2':dict(status='pending_warning',description='p0-b2-c0',body='p0-b2-c1',
                            label_recovered=False,links_verified=False,
                            warning='Table1 not recovered in inspected outputs; recurrence unknown; no retry authorized'),
                'p0-b4':dict(status='accepted_with_agent_visual_review',description='p0-b4-c0',body='p0-b4-c1',
                            label_recovered=True,links_verified=True,accepted_evidence=copy.deepcopy(table2))},
        warnings=dict(list_continuity='LM r12 may continue item2 across columns; not a confirmed class error. A02 historical judgment is superseded here; continuity remains unresolved.',
                      table_bounds='TATR cuts outer borders; MinerU upper rule cut and lower strict boundary indeterminate. No complete table crop certified.',
                      captions='Native figure parentage preserved, not independent verification of OCR or caption assignment.',
                      generalization='No GT, global winner, full omission audit or validated ensemble benefit.'),
        status='reconciled_with_explicit_pending_items',mechanism_implemented=True,accuracy_validated=False,
        new_ocr_executed=False)
    validate(payload)
    return payload


def validate(r):
    sources={s['key']:s['record'] for s in r['sources']}
    if len(sources)!=48:raise ValueError('Source accounting incomplete')
    objects=r['regions']+r['containers'];ids={o['id'] for o in objects}
    if len(ids)!=len(objects):raise ValueError('Duplicate reconciled object')
    selected=[]
    for o in r['regions']:
        k=o['geometry_source']
        if k not in sources or o['bbox']!=sources[k]['bbox_xyxy_px']:raise ValueError('Invented or unknown geometry')
        selected.append(k)
    if len(set(selected))!=len(selected):raise ValueError('Duplicate selected source')
    for link in r['candidate_links']:
        if link['source'] not in sources or not set(link['targets'])<=ids:raise ValueError('Dangling candidate')
    graph={i:[] for i in ids}
    for edge in r['relations']:
        if edge['parent'] not in ids or edge['child'] not in ids:raise ValueError('Dangling hierarchy')
        graph[edge['parent']].append(edge['child'])
    def visit(node,trail):
        if node in trail:raise ValueError('Hierarchy cycle')
        for child in graph[node]:visit(child,trail|{node})
    for node in graph:visit(node,set())
    if r['tables']['p0-b2']['label_recovered'] or r['tables']['p0-b2']['links_verified']:raise ValueError('Table1 cannot be accepted')
    check_table2(r['tables']['p0-b4']['accepted_evidence'])
    accepted=r['tables']['p0-b4']['accepted_evidence']['proposal']['selected_candidate']
    component=r['recovered_components']
    if (len(component)!=1 or component[0]['parent']!='p0-b4'
        or component[0]['bbox']!=accepted['label_line']['bbox']
        or component[0]['text']!=accepted['label_text']):raise ValueError('Recovered label changed or wrong table')


def verify_inputs(prepared):
    """Read sources without extracting or running any model."""
    for run in prepared['runs']:
        path=ROOT/run['source_archive']
        if sha(path)!=run['source_archive_sha256']:raise ValueError('Archive changed: '+str(path))
        with zipfile.ZipFile(path) as z:
            for d in prepared['detections']:
                if d['run_id']!=run['run_id']:continue
                raw=z.read(d['source_member'])
                if hashlib.sha256(raw).hexdigest()!=d['source_member_sha256']:raise ValueError('Member hash changed')
                if pointer(json.loads(raw),d['source_pointer'])!=d['original_record']:raise ValueError('Native record differs')
    if sha(ROOT/RENDER)!=RENDER_SHA:raise ValueError('Render changed')


def write_view(r,destination):
    """Static local HTML, all candidate details and a selected-only PNG overlay."""
    from PIL import Image,ImageDraw
    dest=Path(destination);im=Image.open(ROOT/RENDER).convert('RGB');draw=ImageDraw.Draw(im)
    svg=[]
    for o in r['regions']+r['recovered_components']:
        color='green' if o.get('status')=='accepted' else 'blue'
        x1,y1,x2,y2=o['bbox'];draw.rectangle(o['bbox'],outline=color,width=2);draw.text((x1,y1),o['id'],fill=color)
        svg.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" fill="none" stroke="{color}" stroke-width="2"><title>{html.escape(o["id"])}</title></rect>')
    for c in r['candidate_links']:
        x1,y1,x2,y2=c['bbox']
        svg.append(f'<rect class="candidate" x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" fill="none" stroke="orange" stroke-width="2" stroke-dasharray="6 6"><title>{html.escape(c["source"]+": "+c["decision"])}</title></rect>')
    im.save(dest/'selected-overlay.png');(dest/'render.png').write_bytes((ROOT/RENDER).read_bytes())
    details=''.join('<details><summary>'+html.escape(d['case_id']+' '+d['description'])+'</summary><pre>'+html.escape(json.dumps(d,ensure_ascii=False,indent=2))+'</pre></details>' for d in r['decisions'])
    registry=''.join('<tr><td>'+html.escape(s['key'])+'</td><td>'+html.escape(s['disposition'])+'</td><td><pre>'+html.escape(json.dumps(s['record'],ensure_ascii=False,indent=2))+'</pre></td></tr>' for s in r['sources'])
    content='''<!doctype html><html lang="es"><meta charset="utf-8"><title>Reconciliación sic12 página3</title>
<style>body{font-family:system-ui;margin:24px}svg{width:100%;max-width:830px}pre{white-space:pre-wrap;overflow-wrap:anywhere}td{vertical-align:top;border:1px solid #aaa} .candidate{display:none}body:has(#alternatives:checked) .candidate{display:block}</style>
<h1>Reconciliación de página3: pendientes explícitos</h1><p>MinerU: estructura provisional azul. TATR: contraste de tablas. LayoutLMv3: apoyo. Naranja: candidatos, no objetos adicionales aceptados.</p>
<p>Table1 pendiente; rótulo Table2 aceptado en verde, con revisión visual del agente. Bordes tabulares y continuidad de lista sin resolver. No se certifican exactitud OCR, orden de lectura ni beneficio de ensemble.</p>
<label><input id="alternatives" type="checkbox">Mostrar candidatos alternativos</label><br>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1654 2205"><image href="render.png" width="1654" height="2205"/>'''+''.join(svg)+'''</svg><h2>Decisiones y evidencia histórica</h2>'''+details+'<h2>Registro íntegro de fuentes</h2><table>'+registry+'</table></html>'
    (dest/'review.html').write_text(content,encoding='utf-8')


def export(destination):
    dest=Path(destination)
    if dest.exists():raise FileExistsError('Output must be new')
    p=read(ROOT/PREPARED);verify_inputs(p)
    t=read(ROOT/TABLE2);r=build(p,read(ROOT/ASSOCIATIONS),t)
    mineru=next(run for run in p['runs'] if run['model']=='mineru')
    with zipfile.ZipFile(ROOT/mineru['source_archive']) as z:
        raw=z.read('page/middle-native.json');native=json.loads(raw)
        source_records={s['key']:s['record'] for s in r['sources']}
        for region in r['regions']:
            location=source_records[region['geometry_source']]['original_record']['source_pointer']
            region['native_content_evidence']=dict(archive=mineru['source_archive'],
                archive_sha256=mineru['source_archive_sha256'],member='page/middle-native.json',
                member_sha256=hashlib.sha256(raw).hexdigest(),pointer=location,
                record=copy.deepcopy(pointer(native,location)),recognition_validated=False)
    inputs=[PREPARED,ASSOCIATIONS,TABLE2,RENDER,Path('analytics/reports/sic12_page3-a04-completeness.md'),Path('analytics/reports/sic12_page3-a05-complementarity.md')]
    inputs+=[Path(run['source_archive']) for run in p['runs']]
    # Verify accepted Table2 source archive and review image, keeping its payload intact.
    table2archive=ROOT/'code/results/localized-labels-v1/20261024T221741Z/result.zip'
    if sha(table2archive)!=t['result_archive_sha256']:raise ValueError('Table2 OCR source changed')
    review=ROOT/'analytics/results/sic12_page3/table2-lines-v1'/t['visual_review']['review_image']
    if sha(review)!=t['visual_review']['review_image_sha256']:raise ValueError('Table2 review image changed')
    inputs.extend([table2archive.relative_to(ROOT),review.relative_to(ROOT)])
    manifest={path.as_posix():sha(ROOT/path) for path in inputs}
    manifest['code/page_integration/reconciliation.py']=sha(Path(__file__))
    r['input_manifest']=manifest
    dest.mkdir(parents=True);save(dest/'reconciled-page.json',r);write_view(r,dest)
    # Input files must still match after export.
    if any(sha(ROOT/path)!=digest for path,digest in manifest.items()):raise ValueError('Input changed during export')
    save(dest/'manifest.json',dict(inputs=manifest,outputs={p.name:sha(p) for p in sorted(dest.iterdir()) if p.is_file()},
        checks=dict(native_source_hashes_and_pointers=True,accounted_sources=48,selected_segments=19,
                    preserved_containers=4,table1_pending=True,table2_accepted=True,inputs_unchanged=True),
        review_status='technical_checks_passed_visual_review_pending',no_new_ocr=True))
    return r


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();result=export(args.output)
    print('Offline reconciliation exported:',len(result['regions']),'segments; pending items retained')
