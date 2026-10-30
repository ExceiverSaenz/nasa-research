"""Canonical collection entrypoint: saved parsers + native PDF + rule-based order."""
import argparse
import copy
import inspect
import json
import platform
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from integration.reading_order.export import digest,write,validate_result
from integration.structure.docling_trial import apply_docling,PIN
from integration.structure.native import inspect_pdf
from integration.structure.structure import integrate
from .structure import CONFIG,build_structure,assign_memberships
from .order import connect_order


def metrics(result,baseline):
    struct=result['structure'];old={s['id']:(rt,j) for rt,r in baseline['routes'].items() for j,id in enumerate(r['expanded_sequence']) for s in baseline['steps'] if s['id']==id}
    new={id:(rt,j) for rt,r in result['routes'].items() for j,id in enumerate(r['expanded_sequence'])};content=[s for s in result['steps'] if s['kind']=='content']
    inv=result['inventory'];sections=struct['sections'];sem=result['operational_semantics']
    return dict(inventory_units=len(inv),pages=len(result['original_page_context']),content_appearances=len(content),deferred_children=sum(i['disposition']=='deferred_child_reference' for i in inv),
        abstained_pages=sum(p.get('original_status')=='blocked' or 'invalid_geometry' in p.get('original_incidents',[]) for p in result['original_page_context']),
        changed_content_positions_vs_Docling=sum(old[s['id']]!=new[s['id']] for s in content),route_changes=len(result['operational_connection']['route_changes']),
        sections=len(sections),sections_with_parent=sum(s['parent_ref'] is not None for s in sections),sections_unknown_level=sum(s['level'] is None for s in sections),
        memberships_with_context=sum(m['section_ref'] is not None for m in struct['memberships']),paragraph_fragments=len(struct['paragraph_fragments']),continuity_candidates=dict(Counter(c['status'] for c in struct['continuity_candidates'])),
        local_precedence_proposals=len(result['operational_connection']['precedence_proposals']),suspended_proposals=len(result['operational_connection']['suspended']),units_with_warnings=len(sem),
        roles=dict(Counter(s['role'] or 'unknown' for s in sem)),category_strata={str(cat):dict(N=sum(i['original_unit']['classification']['category']['value']==cat for i in inv),abstained_role=sum(s['role'] is None for s,i in zip(sem,inv) if i['original_unit']['classification']['category']['value']==cat),warning_units=sum(i['original_unit']['classification']['category']['value']==cat for i in inv)) for cat in {i['original_unit']['classification']['category']['value'] for i in inv}},
        accounting_coverage=1.0,semantic_accuracy=None,quality_status='pending_after_full_mvp',models_executed=False,OCR_executed=False)


def assemble(baseline,native,analysis=None):
    analysis=analysis or integrate(baseline,native);structure,semantics=build_structure(baseline,analysis,native);out=connect_order(baseline,structure,semantics,native)
    assign_memberships(structure,out,semantics,analysis)
    positions={s['id']:s['route'] for s in out['steps']}
    for s,i in zip(semantics,out['inventory']):s['effective_route']=positions.get(i.get('appearance_ref'),i.get('route'))
    out.update(schema_version='parsing-operational/1',canonical_stage='parsing',status='automated_complete_with_pending_validation',structure=structure,operational_semantics=semantics,native_links=copy.deepcopy(analysis['evidence_links']),operational_config=copy.deepcopy(CONFIG))
    out['relations'].extend(copy.deepcopy(structure['continuity_candidates']));out['metrics']=metrics(out,baseline)
    out['validation'].update(semantic='pending_after_full_mvp',human_action_required_now=False,original_classification_unchanged=True)
    return out


def validate(result,baseline):
    if result['inventory']!=baseline['inventory']:raise ValueError('inventory/source changed')
    old={s['id']:s for s in baseline['steps']};new={s['id']:s for s in result['steps']}
    if set(old)!=set(new):raise ValueError('steps lost/duplicated')
    for id,s in new.items():
        for key in ('children','unit_ref','kind','render_unit_refs','content_appearance_ref','deferred_child_refs'):
            if s.get(key)!=old[id].get(key):raise ValueError('capsule or deferred reference changed')
    # Reuse the established traversal contract without requiring another classifier run.
    classified=dict(regions=[i['original_unit'] for i in baseline['inventory'] if i['original_unit']['structural_kind']!='group'],logical_units=[i['original_unit'] for i in baseline['inventory'] if i['original_unit']['structural_kind']=='group'])
    validate_result(result,classified)
    ids={i['unit_ref'] for i in result['inventory']};nodes={s['id']:s for s in result['structure']['sections']}
    if len(nodes)!=len(result['structure']['sections']):raise ValueError('duplicate sections')
    for id,s in nodes.items():
        if any(h not in ids for h in s['heading_candidates']):raise ValueError('unknown heading')
        parent=s['parent_ref'];seen={id}
        while parent:
            if parent not in nodes or parent in seen:raise ValueError('invalid/cyclic section hierarchy')
            seen.add(parent);parent=nodes[parent]['parent_ref']
    memberships=result['structure']['memberships']
    if len(memberships)!=len(ids) or {m['unit_ref'] for m in memberships}!=ids:raise ValueError('membership accounting incomplete')
    for m in memberships:
        if m['section_ref'] is not None and m['section_ref'] not in nodes:raise ValueError('unknown membership section')
    # Abstained pages must retain their route and sequence exactly.
    for p in baseline['original_page_context']:
        if p.get('original_status')=='blocked' or 'invalid_geometry' in p.get('original_incidents',[]):
            n=p['identity']['physical_page']
            for rt,r in baseline['routes'].items():
                a=[id for id in r['expanded_sequence'] if old[id]['page']==n];b=[id for id in result['routes'][rt]['expanded_sequence'] if new[id]['page']==n]
                if a!=b:raise ValueError('abstained page altered')
    return dict(original_inventory_preserved=True,capsules_and_references_preserved=True,all_units_accounted=True,hierarchy_acyclic=True,abstentions_preserved=True)


def verified_cache(path):
    p=Path(path).resolve()
    for mp in (p.parent/'manifest.json',p.parents[2]/'manifest.json'):
        if mp.exists():
            m=json.loads(mp.read_text(encoding='utf-8'))
            try:key=p.relative_to(mp.parent).as_posix()
            except ValueError:continue
            if m.get('outputs',{}).get(key)==digest(p):return json.loads(p.read_text(encoding='utf-8'))
    raise ValueError('cache not verified: '+str(p))


def export_collection(source,destination,approved_orders=(),native_caches=(),prediction_fn=None,*,runtime_profile="historical",build_views=True):
    if runtime_profile not in ("historical","shared","integrator"):raise ValueError("Unknown runtime profile")
    source=Path(source).resolve();dest=Path(destination).resolve()
    if dest.exists():raise FileExistsError(dest)
    if dest==source or source in dest.parents or dest in source.parents:raise ValueError('separate output required')
    source_manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'));summary=json.loads((source/'summary.json').read_text(encoding='utf-8'));guard={}
    for rel,h in source_manifest['outputs'].items():
        p=(source/rel).resolve()
        if source not in p.parents or digest(p)!=h:raise ValueError('reading manifest mismatch')
        guard[str(p)]=h
    orders={};caches={}
    for path in approved_orders:
        p=Path(path).resolve();value=verified_cache(p)
        if value['paper_id'] in orders:raise ValueError('duplicate approved order identity')
        orders[value['paper_id']]=(p,value);guard[str(p)]=digest(p)
    for path in native_caches:
        p=Path(path).resolve();value=verified_cache(p);sha=value['pdf_sha256']
        if sha in caches:raise ValueError('duplicate native cache')
        caches[sha]=(p,value);guard[str(p)]=digest(p)
    if prediction_fn is None:
        import docling.models.postprocessing.reading_order_rb as rb
        if platform.python_version()!=('3.11.16' if runtime_profile in ('shared','integrator') else '3.13.5') or version('PyMuPDF')!='1.27.2.3' or version('docling')!='2.123.1' or version('docling-core')!='2.92.0' or digest(inspect.getfile(rb))!=PIN:raise ValueError('environment differs from frozen baseline')
    entries=sorted(summary['documents'],key=lambda e:(0 if json.loads((source/e['data']).read_text(encoding='utf-8'))['paper_id'] in orders else 1,e['paper']))
    papers=[e['paper'] for e in entries]
    if len(set(papers))!=len(papers):raise ValueError('duplicate paper id')
    from .view import build_view,build_index
    dest.mkdir(parents=True,exist_ok=False);reports=[]
    here=Path(__file__).parent;dependencies=[here.parent/'structure'/name for name in ('native.py','align.py','claims.py','structure.py','docling_trial.py')]+[here.parent/'reading_order'/name for name in ('export.py','layout.py','viewer.html','viewer.js','viewer.css')]
    code_hashes={str(p):digest(p) for p in list(here.iterdir())+dependencies if p.is_file() and p.suffix in ('.py','.js','.css','.html')}
    runtime=dict(profile=runtime_profile,python=platform.python_version(),PyMuPDF=version('PyMuPDF'),Docling=version('docling') if prediction_fn is None else 'fixture_predictor',Docling_core=version('docling-core') if prediction_fn is None else 'fixture_predictor')
    for item in entries:
        basepath=source/item['data'];base=json.loads(basepath.read_text(encoding='utf-8'));rec=base['reconciliation_source'];classified=base['classification_source']
        for ref in (rec,classified):
            if digest(ref['path'])!=ref['sha256']:raise ValueError('source reference changed')
            guard[ref['path']]=ref['sha256']
        reconciled=json.loads(Path(rec['path']).read_text(encoding='utf-8'));pdf=Path(reconciled['document']).resolve();pdfsha=digest(pdf)
        if pdfsha!=reconciled['document_sha256']:raise ValueError('PDF identity mismatch')
        guard[str(pdf)]=pdfsha;folder=dest/f"papers/{item['paper']}"
        cached=orders.get(base['paper_id']);baseline=copy.deepcopy(cached[1]) if cached else apply_docling(base,prediction_fn)
        if baseline['inventory']!=base['inventory'] or baseline['original_page_context']!=base['original_page_context']:raise ValueError('approved baseline identity mismatch')
        if cached:
            cm=json.loads((cached[0].parent/'manifest.json').read_text(encoding='utf-8'))
            if cm['baseline_source']['sha256']!=digest(basepath):raise ValueError('approved order references a different baseline')
        nc=caches.get(pdfsha);analysis=None
        if nc:
            native=copy.deepcopy(nc[1]);analysispath=nc[0].parent/'document.json'
            if native.get('extractor_version')!=version('PyMuPDF'):raise ValueError('native cache extractor differs from frozen version')
            if analysispath.exists():
                possible=verified_cache(analysispath)
                if possible.get('inventory')==baseline['inventory'] and possible.get('approved_steps')==baseline['steps'] and possible.get('approved_routes')==baseline['routes']:analysis=possible;guard[str(analysispath)]=digest(analysispath)
        else:
            try:native=inspect_pdf(pdf)
            except Exception as exc:native=dict(pdf_path=str(pdf),pdf_sha256=pdfsha,pages=[],evidence=[],missing_information=['native_extraction_failed'],error=type(exc).__name__+': '+str(exc))
        analysis=analysis or integrate(baseline,native);result=assemble(baseline,native,analysis);checks=validate(result,baseline)
        result['canonical_sources']=dict(reading_v1=dict(path=str(basepath),sha256=digest(basepath)),Docling_baseline='baseline-docling.json',native='native-evidence.json',native_analysis='native-analysis.json',approved_order_cache=str(cached[0]) if cached else None,native_cache=str(nc[0]) if nc else None)
        for name,data in [('baseline-docling.json',baseline),('native-evidence.json',native),('native-analysis.json',analysis),('document.json',result),('verification.json',checks)]:write(folder/name,data)
        write(folder/'review-queue.json',dict(stage='after_full_mvp',blocking=False,warning='Requiere validación humana',units=result['operational_semantics'],structure=result['structure'],connection=result['operational_connection']))
        if build_views:
            view=build_view(folder/'document.json',folder/'view');guard.update(view['source_images'])
        reports.append(dict(paper=item['paper'],paper_id=base['paper_id'],data=f"papers/{item['paper']}/document.json",view=f"papers/{item['paper']}/view/index.html" if build_views else None,metrics=result['metrics'],approved_order_reused=bool(cached),native_cache_reused=bool(nc)))
        write(folder/'manifest.json',dict(sources={str(basepath):digest(basepath),classified['path']:classified['sha256'],rec['path']:rec['sha256'],str(pdf):pdfsha},outputs={p.relative_to(folder).as_posix():digest(p) for p in folder.rglob('*') if p.is_file()},config=CONFIG,code=code_hashes,verification=checks))
    for p,h in guard.items():
        if digest(p)!=h:raise ValueError('protected source changed: '+p)
    if any(digest(p)!=h for p,h in code_hashes.items()):raise ValueError('code changed during collection run')
    totals=Counter()
    for report in reports:
        for k,v in report['metrics'].items():
            if isinstance(v,int) and not isinstance(v,bool):totals[k]+=v
    result=dict(schema_version='parsing-operational-collection/1',papers=len(reports),**dict(totals),documents=reports,config=CONFIG,code_hashes=code_hashes,runtime=runtime,semantic_accuracy=None,models_executed=False,OCR_executed=False,manual_overrides=0,configuration_frozen=True)
    write(dest/'summary.json',result);write(dest/'review-queue.json',dict(stage='after_full_mvp',blocking=False,papers=[dict(paper=r['paper'],queue=f"papers/{r['paper']}/review-queue.json") for r in reports]));build_index(result,dest/'index.html')
    write(dest/'manifest.json',dict(protected_inputs=guard,outputs={p.relative_to(dest).as_posix():digest(p) for p in dest.rglob('*') if p.is_file()},code=code_hashes,config=CONFIG,runtime=runtime,originals_unchanged=True,models_executed=False))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');p.add_argument('--approved-order',action='append',default=[]);p.add_argument('--native-cache',action='append',default=[]);a=p.parse_args()
    result=export_collection(a.source,a.destination,a.approved_order,a.native_cache);print(json.dumps({k:v for k,v in result.items() if k not in ('documents','code_hashes')},ensure_ascii=False,indent=2))
