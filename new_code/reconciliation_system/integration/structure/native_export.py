"""One-shot, source-verified additive export. No parser/order/model execution."""
import argparse
import copy
import json
import importlib.metadata
import platform
from collections import Counter
from pathlib import Path
from integration.reading_order.export import digest,write
from .native import inspect_pdf
from .structure import integrate


def resolve_pointer(value,pointer):
    for token in pointer.lstrip('/').split('/'):
        token=token.replace('~1','/').replace('~0','~')
        value=value[int(token)] if isinstance(value,list) else value[token]
    return value


def validate(result,baseline):
    if result['inventory']!=baseline['inventory']:raise ValueError('inventory changed')
    if result['approved_routes']!=baseline['routes'] or result['approved_steps']!=baseline['steps']:raise ValueError('approved traversal changed')
    ids=[i['unit_ref'] for i in baseline['inventory']];known=set(ids)
    if len(known)!=len(ids):raise ValueError('duplicate unit IDs')
    for field in ('evidence_links','classification_proposals'):
        refs=[x['unit_ref'] for x in result[field]]
        if len(refs)!=len(ids) or set(refs)!=known:raise ValueError('incomplete '+field)
    evidence={e['id']:e for e in result['native_evidence']}
    if len(evidence)!=len(result['native_evidence']):raise ValueError('duplicate evidence IDs')
    def checkrefs(refs):
        for ref in refs:
            if ref.startswith('baseline:'):resolve_pointer(baseline,ref[len('baseline:'):])
            elif ref not in evidence:raise ValueError('dangling evidence '+ref)
    for link in result['evidence_links']:
        checkrefs(link['evidence_refs'])
        for s in link['span_refs']:resolve_pointer(evidence[s['evidence_ref']],s['pointer'])
        original=next(i for i in baseline['inventory'] if i['unit_ref']==link['unit_ref'])
        if original['disposition']=='deferred_child_reference' and (link['status']!='deferred' or link['evidence_refs']):raise ValueError('deferred child localized')
    for p in result['classification_proposals']:
        for claim in p.get('unapplied_native_candidates',[]):checkrefs(claim['evidence_refs'])
        for decision in p['decisions'].values():
            if decision['probability'] is not None:raise ValueError('unvalidated probability')
            for claim in decision['claims']:checkrefs(claim['evidence_refs'])
    sections={s['id']:s for s in result['document_structure']['sections']}
    if len(sections)!=len(result['document_structure']['sections']):raise ValueError('duplicate sections')
    for id,s in sections.items():
        checkrefs(s['evidence_refs'])
        if any(h not in known for h in s['heading_candidates']):raise ValueError('unknown heading')
        seen={id};parent=s['parent_section_ref']
        while parent:
            if parent not in sections or parent in seen:raise ValueError('invalid hierarchy')
            seen.add(parent);parent=sections[parent]['parent_section_ref']
    for m in result['document_structure']['memberships']:
        if m['unit_ref'] not in known or m['spatial_section_candidate'] and m['spatial_section_candidate'] not in sections:raise ValueError('invalid section membership')
    for p in result['document_structure']['paragraph_fragments']:
        if any(r not in known for r in p['fragment_refs']) or p['text_concatenated']:raise ValueError('invalid paragraph')
    for rel in result['document_structure']['continuity_candidates']:
        if rel['from'] not in known or rel['to'] not in known or rel['applied']:raise ValueError('invalid continuity')
        checkrefs(rel['evidence_refs'])
    return dict(inventory_preserved=True,approved_order_preserved=True,all_unit_and_evidence_references_resolved=True,hierarchy_acyclic=True,deferred_policy_preserved=True)


def summarize(result):
    ps=result['classification_proposals'];ss=result['document_structure']['sections']
    return dict(inventory_units=len(result['inventory']),native_evidence_records=len(result['native_evidence']),
        native_evidence_by_kind=dict(Counter(e['kind'] for e in result['native_evidence'])),
        alignment_status=dict(Counter(e['status'] for e in result['evidence_links'])),
        document_roles=dict(Counter(p['decisions']['document_role']['operational_proposal'] or 'unresolved' for p in ps)),
        decision_status_by_dimension={d:dict(Counter(p['decisions'][d]['status'] for p in ps)) for d in ('category','function','document_role','flow')},
        units_with_native_role_proposal=sum(p['decisions']['document_role']['operational_proposal'] is not None for p in ps),
        conflict_dimensions=len(result['contradictions']),units_with_conflicts=len({c['unit_ref'] for c in result['contradictions']}),
        sections=len(ss),section_alignment=dict(Counter(s['status'] for s in ss)),
        memberships_by_status=dict(Counter(m['status'] for m in result['document_structure']['memberships'])),
        paragraph_fragments=len(result['document_structure']['paragraph_fragments']),continuity_candidates=len(result['document_structure']['continuity_candidates']),
        units_preserved_for_final_validation=len(ps),coverage_is_not_accuracy=True,semantic_accuracy=None,
        missing_native_information=result['missing_native_information'],baseline_order_changed=False,OCR_executed=False,neural_models_executed=False)


def export_native(pdf_path,baseline_path,destination):
    path=Path(baseline_path).resolve();dest=Path(destination).resolve();pdf=Path(pdf_path).resolve()
    if dest.exists():raise FileExistsError(dest)
    base=json.loads(path.read_text(encoding='utf-8'));protected={str(path):digest(path),str(pdf):digest(pdf)}
    manifest=path.parent/'manifest.json';m=json.loads(manifest.read_text(encoding='utf-8'))
    if m['outputs'].get(path.name)!=digest(path):raise ValueError('approved baseline manifest mismatch')
    for key in ('classification_source','reconciliation_source'):
        ref=base[key];p=Path(ref['path'])
        if digest(p)!=ref['sha256']:raise ValueError(key+' hash mismatch')
        protected[str(p)]=digest(p)
    # Authoritative document identity occurs in reconciled page identities.
    expected={p['identity'].get('pdf_sha256') or p['identity'].get('document_sha256') for p in base['original_page_context']}
    expected.discard(None)
    if expected and expected!={digest(pdf)}:raise ValueError('PDF identity mismatch')
    source=json.loads(Path(base['reconciliation_source']['path']).read_text(encoding='utf-8'))
    if source.get('document_sha256')!=digest(pdf):raise ValueError('PDF hash differs from reconciled provenance')
    native=inspect_pdf(pdf);result=integrate(base,native);checks=validate(result,base);summary=summarize(result)
    if len(native['pages'])!=len(base['original_page_context']):raise ValueError('page count mismatch')
    review=dict(stage='after_full_mvp',blocking=False,warning='Requiere validación humana',
        units=[dict(unit_ref=p['unit_ref'],dimensions={d:x['status'] for d,x in p['decisions'].items()},conflicts=[d for d,x in p['decisions'].items() if x['status']=='conflict'],unapplied_native_candidates=p['unapplied_native_candidates'],inherited_warnings=p['inherited_warnings']) for p in result['classification_proposals']],
        sections=result['document_structure']['sections'],continuity_candidates=result['document_structure']['continuity_candidates'])
    for name,data in (('native-evidence.json',native),('document.json',result),('summary.json',summary),('review-queue.json',review)):write(dest/name,data)
    if any(digest(p)!=h for p,h in protected.items()):raise ValueError('source mutation')
    write(dest/'manifest.json',dict(sources=protected,outputs={p.name:digest(p) for p in dest.glob('*.json')},verification=checks,
        runtime=dict(python=platform.python_version(),pymupdf_binding=native['extractor_version'],pymupdf_distribution=importlib.metadata.version('PyMuPDF')),code={str(p):digest(p) for p in Path(__file__).parent.glob('*.py') if p.name in ('native.py','align.py','claims.py','structure.py','native_export.py')},
        OCR_executed=False,neural_models_executed=False,docling_executed=False,GROBID_executed=False))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pdf');p.add_argument('baseline');p.add_argument('destination');a=p.parse_args()
    print(json.dumps(export_native(a.pdf,a.baseline,a.destination),ensure_ascii=False,indent=2))
