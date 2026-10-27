"""Generic partial structure from retained classifications, native text and typography."""
import copy
import re
from collections import Counter
from statistics import median
from document_structure.align import compact

CONFIG=dict(full_width_fraction=.62,full_width_median_factor=1.4,column_overlap=.65,vertical_line_tolerance=.5,max_heading_words=20,max_heading_lines=3)
FRONT={'article_title','authorship','affiliation_candidate','keywords','copyright','abstract_heading','abstract_body_candidate'}


def marker(text):
    token=(text or '').strip().split(maxsplit=1)
    if len(token)<2:return None
    first=token[0].rstrip('.)')
    if re.fullmatch(r'\d+(?:\.\d+){0,5}',first):return tuple(first.split('.'))
    if re.fullmatch(r'[IVXLCDM]{1,6}',first) and token[0].endswith(('.',')')):return (first,)
    return None


def build_structure(order,analysis,native):
    inventory=order['inventory'];units={i['unit_ref']:i['original_unit'] for i in inventory};links={l['unit_ref']:l for l in analysis['evidence_links']};proposals={p['unit_ref']:p for p in analysis['classification_proposals']}
    def text(id):return links[id]['native_text'] or units[id].get('original_record',{}).get('text','') or ''
    semantics=[]
    for i in inventory:
        id=i['unit_ref'];p=proposals[id];role=p['decisions']['document_role']['operational_proposal'];flow=p['decisions']['flow']['operational_proposal']
        semantics.append(dict(unit_ref=id,function=p['decisions']['function']['operational_proposal'],role=role,flow=flow,original_route=i.get('route'),routing_eligible=role in FRONT and flow=='front_matter',
            decisions=copy.deepcopy(p['decisions']),inherited_warnings=copy.deepcopy(p['inherited_warnings']),warning='Requiere validación humana',review_stage='after_full_mvp'))
    smap={s['unit_ref']:s for s in semantics};sections=[];roots=[];covered=set();native_id_map={}
    titles=[compact(v) for e in native['evidence'] if e['kind'] in ('xmp','pdf_metadata') and e['data'].get('field') in ('title','dc:title') for v in e['data']['values']]
    for s in analysis['document_structure']['sections']:
        title=s['title'];prefix=compact(title.rstrip('.… '));truncated=title.rstrip().endswith(('...','…'))
        if compact(title) in titles or truncated and len(prefix)>=32 and any(t.startswith(prefix) for t in titles):roots.append(copy.deepcopy(s));continue
        candidates=s['heading_candidates'];heading=candidates[0] if len(candidates)==1 else None
        if heading and smap[heading]['role'] in FRONT:continue
        id='section:'+s['id'];native_id_map[s['id']]=id
        sections.append(dict(id=id,title=title,page=s['page'],heading_ref=heading,heading_candidates=candidates,level=s.get('declared_level'),parent_ref=None,parent_candidates=[],status=s['status'],basis=s['hierarchy_status'],evidence_refs=s['evidence_refs'],marker=list(marker(title) or []),original_parent=s['parent_section_ref'],warning='Requiere validación humana'))
        covered.update(candidates)
    # Typography is local evidence; never a fixed title list or a paper-specific font.
    ev={e['id']:e for e in native['evidence']};styles={};body_sizes=[]
    for id,u in units.items():
        sizes=[];fonts=[]
        for ref in links[id]['span_refs']:
            val=ev[ref['evidence_ref']]
            for key in ref['pointer'].lstrip('/').split('/'):val=val[int(key)] if isinstance(val,list) else val[key]
            sizes.append(val['size']);fonts.append(val['font'])
        styles[id]=dict(size=median(sizes) if sizes else None,fonts=sorted(set(fonts)))
        if u['classification']['category']['value']=='text' and sizes:body_sizes.extend(sizes)
    body_size=median(body_sizes) if body_sizes else None
    body_fonts=Counter(f for id,u in units.items() if u['classification']['category']['value']=='text' for f in styles[id]['fonts']);dominant=body_fonts.most_common(1)[0][0] if body_fonts else None
    for i in inventory:
        id=i['unit_ref'];u=units[id];t=text(id);cat=u['classification']['category']['value'];sty=styles[id]
        if id in covered or smap[id]['role'] in FRONT or not u.get('bbox_xyxy') or links[id]['status'] in ('deferred','geometry_abstained','unsupported_rotation_mapping'):continue
        typography=sty['size'] is not None and body_size is not None and (sty['size']>body_size*1.08 or dominant not in sty['fonts'])
        extra=marker(t) and typography and len(t.split())<=CONFIG['max_heading_words'] and len(t.splitlines())<=CONFIG['max_heading_lines']
        if cat!='title' and not extra:continue
        sections.append(dict(id='section:unit:'+id,title=t,page=u['page'],heading_ref=id,heading_candidates=[id],level=None,parent_ref=None,parent_candidates=[],status='heading_proposal',basis='retained_title' if cat=='title' else 'numbering_and_typography',evidence_refs=links[id]['evidence_refs'],marker=list(marker(t) or []),original_parent=None,warning='Requiere validación humana'))
    counts=Counter(tuple(s['marker']) for s in sections if s['marker']);by_marker={tuple(s['marker']):s for s in sections if s['marker'] and counts[tuple(s['marker'])]==1}
    for s in sections:
        m=tuple(s['marker']);parent=native_id_map.get(s.pop('original_parent'))
        if parent:s['parent_ref']=parent
        if m and counts[m]>1:s['status']='ambiguous_numbering';s['parent_candidates']=[x['id'] for x in sections if x['marker']==s['marker'] and x['id']!=s['id']];continue
        if m:
            numeric_parent=by_marker.get(m[:-1]);s['numbering_level_candidate']=len(m)
            if s['level'] is None:s['level']=len(m);s['basis']+=' + numbering'
            if numeric_parent:
                if s['parent_ref'] and s['parent_ref']!=numeric_parent['id']:s['parent_candidates'].append(numeric_parent['id']);s['status']='hierarchy_conflict'
                else:s['parent_ref']=numeric_parent['id']
        if s['heading_ref'] and smap[s['heading_ref']]['role'] is None:smap[s['heading_ref']]['role']='section_heading_candidate'
        if s['heading_ref']:s['style_evidence']=styles.get(s['heading_ref'])
    structure=dict(sections=sections,document_root_candidates=roots,memberships=[],paragraph_fragments=[],continuity_candidates=[],warning='Requiere validación humana; estructura parcial automatizada')
    assign_memberships(structure,order,semantics,analysis)
    return structure,semantics


def assign_memberships(structure,reading,semantics,analysis):
    units={i['unit_ref']:i['original_unit'] for i in reading['inventory']};smap={s['unit_ref']:s for s in semantics};links={l['unit_ref']:l for l in analysis['evidence_links']};steps={s['id']:s for s in reading['steps']};headings={s['heading_ref']:s for s in structure['sections'] if s['heading_ref'] and s['status']!='ambiguous_numbering'}
    active=None;membership={};paragraphs=[];continuities=[];previous=None
    for sid in reading['routes'].get('main',{}).get('expanded_sequence',[]):
        step=steps[sid];id=step['unit_ref'];u=units[id]
        if id in headings and step['kind']=='content':active=headings[id]['id'];previous=None
        if id not in membership:membership[id]=dict(unit_ref=id,section_ref=active,physical_section_candidate=active,thematic_section_candidates=[],status='inferred_from_operational_order' if active else 'unknown',warning='Requiere validación humana')
        cat=u['classification']['category']['value'];visual=cat in ('figure','table','caption') or u['structural_kind']=='group'
        if visual:membership[id]['status']='physical_context_only';continue
        if step['kind']!='content' or cat!='text' or id in headings:previous=None;continue
        paragraphs.append(dict(id='fragment:'+id,fragment_refs=[id],text_concatenated=False))
        if previous:
            a=units[previous];ba=a.get('bbox_xyxy');bb=u.get('bbox_xyxy');ta=(links[previous]['native_text'] or a.get('original_record',{}).get('text','')).strip();tb=(links[id]['native_text'] or u.get('original_record',{}).get('text','')).strip()
            transition=a['page']!=u['page'] or ba and bb and bb[0]>ba[2] and ba[1]>bb[1]
            blocked=links[previous]['status']!='span_centers_supported' or links[id]['status']!='span_centers_supported'
            if transition:
                support=ta and tb and (ta.endswith('-') or ta[-1] not in '.!?:;' and tb[0].islower())
                continuities.append(dict(type='paragraph_continues',scope='units',**{'from':previous,'to':id},status='blocked_deferred' if blocked else 'candidate_supported' if support else 'candidate_ambiguous',evidence_refs=links[previous]['evidence_refs']+links[id]['evidence_refs'],text_concatenated=False,warning='Requiere validación humana'))
        previous=id
    for i in reading['inventory']:
        id=i['unit_ref']
        if id not in membership:membership[id]=dict(unit_ref=id,section_ref=None,physical_section_candidate=None,thematic_section_candidates=[],status='deferred' if i['disposition']=='deferred_child_reference' else 'outside_main_flow',warning='Requiere validación humana')
    structure.update(memberships=list(membership.values()),paragraph_fragments=paragraphs,continuity_candidates=continuities)
