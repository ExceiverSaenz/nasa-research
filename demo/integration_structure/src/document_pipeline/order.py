"""Capsule-level local constraints, stable fallback and explicit suspended alternatives."""
import copy
from statistics import median
from .structure import CONFIG
from reading_order.layout import valid_box


def warning(code):return dict(code=code,message='Requiere validación humana',review_stage='after_full_mvp')
def overlap(a,b):return max(0,min(a[2],b[2])-max(a[0],b[0]))/max(1,min(a[2]-a[0],b[2]-b[0]))


def stable_topological(ids,edges):
    remaining=list(ids);result=[]
    while remaining:
        chosen=next((x for x in remaining if not any(b==x and a in remaining for a,b in edges)),None)
        if chosen is None:raise ValueError('cycle')
        result.append(chosen);remaining.remove(chosen)
    return result


def connect_order(baseline,structure,semantics,native):
    out=copy.deepcopy(baseline);steps={s['id']:s for s in out['steps']};units={i['unit_ref']:i['original_unit'] for i in out['inventory']};pages={p['identity']['physical_page']:p for p in out['original_page_context']};sm={s['unit_ref']:s for s in semantics};rootof={}
    for route in out['routes'].values():
        for root in route['sequence']:
            rootof[root]=root
            for child in steps[root]['children']:rootof[child]=root
    changes=[];zones=[];edges_trace=[];suspended=[]
    for rt,route in list(out['routes'].items()):
        for root in list(route['sequence']):
            content=[steps[x]['unit_ref'] for x in [root]+steps[root]['children'] if steps[x]['kind']=='content'];n=steps[root]['page'];p=pages[n]
            blocked=p.get('original_status')=='blocked' or 'invalid_geometry' in p.get('original_incidents',[])
            if rt=='main' and not blocked and content and all(sm[id]['routing_eligible'] for id in content):
                route['sequence'].remove(root);out['routes']['metadata']['sequence'].append(root)
                for id in [root]+steps[root]['children']:steps[id]['baseline_route']=steps[id]['route'];steps[id]['route']='metadata';steps[id]['warnings'].append(warning('native_front_matter_route_proposal'))
                changes.append(dict(root_ref=root,**{'from':rt,'to':'metadata'},reason='all capsule content has contextual native front-matter proposal',unit_refs=content))
    def extent(root,p):
        refs=[u for id in [root]+steps[root]['children'] for u in steps[id]['render_unit_refs']];boxes=[units[u].get('bbox_xyxy') for u in set(refs)];i=p['identity']
        if not boxes or not all(valid_box(b,i['width_px'],i['height_px']) for b in boxes):return None
        return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
    for rt,route in out['routes'].items():
        final=[]
        for n,p in sorted(pages.items()):
            ids=[id for id in route['sequence'] if steps[id]['page']==n];boxes={id:extent(id,p) for id in ids}
            if not ids:continue
            blocked=p.get('original_status')=='blocked' or 'invalid_geometry' in p.get('original_incidents',[]) or any(steps[id]['evidence_status']=='abstained' for id in ids)
            if blocked:final.extend(ids);zones.append(dict(page=n,route=rt,status='abstained_geometry',roots=ids));continue
            lineheights=[l['bbox'][3]-l['bbox'][1] for e in native['evidence'] if e['kind']=='text_block' and e['page']==n for l in e['data']['lines'] if l['bbox'][3]>l['bbox'][1]];tolerance=(median(lineheights)*p['identity']['height_px']/next((x['height_pt'] for x in native['pages'] if x['page']==n),p['identity']['height_px']) if lineheights else 0)*CONFIG['vertical_line_tolerance']
            widths=[b[2]-b[0] for b in boxes.values() if b];mw=median(widths) if widths else 0;w=p['identity']['width_px']
            full=[id for id,b in boxes.items() if b and b[2]-b[0]>=CONFIG['full_width_fraction']*w and (not mw or b[2]-b[0]>=CONFIG['full_width_median_factor']*mw)]
            separators=sorted(full,key=lambda id:boxes[id][1]);bands={}
            for id,b in boxes.items():
                if b is None:continue
                band=sum(boxes[f][3]<=b[1] for f in separators if f!=id);bands.setdefault(band,[]).append(id)
            edges=set()
            # Reference ownership and explicitly retained precedences dominate new geometry.
            for id in ids:
                for child in steps[id]['children']:
                    s=steps[child]
                    if s['kind']=='reference':
                        owner=rootof.get(s['content_appearance_ref'])
                        if owner in ids and owner!=id:edges.add((owner,id))
            for rel in baseline['relations']:
                if rel['type']=='precedes' and rel.get('basis')=='retained_precedence':
                    a,b=rootof.get(rel['from']),rootof.get(rel['to'])
                    if a in ids and b in ids and a!=b:edges.add((a,b))
            try:stable_topological(ids,edges)
            except ValueError:raise ValueError('Baseline hard constraints cyclic')
            candidates=[]
            # Structure participates before weaker local geometry: parent headings
            # precede their child headings only when physical evidence is compatible.
            sections={s['id']:s for s in structure['sections']}
            for section in structure['sections']:
                parent=sections.get(section['parent_ref']);child_step=next((s['id'] for s in steps.values() if s['unit_ref']==section['heading_ref'] and s['kind']=='content'),None)
                parent_step=next((s['id'] for s in steps.values() if parent and s['unit_ref']==parent['heading_ref'] and s['kind']=='content'),None)
                a,b=rootof.get(parent_step),rootof.get(child_step)
                if a not in ids or b not in ids or a==b or not boxes[a] or not boxes[b]:continue
                compatible=boxes[a][3]<=boxes[b][1]+tolerance if overlap(boxes[a],boxes[b])>=CONFIG['column_overlap'] else boxes[a][2]<=boxes[b][0]
                if compatible:candidates.append((a,b,'hierarchy_parent_before_heading'))
                else:suspended.append(dict(page=n,route=rt,**{'from':a,'to':b},basis='hierarchy_parent_before_heading',reason='hierarchy_geometry_contradiction',alternatives=['retain_Docling_order']))
            for band,roots in sorted(bands.items()):
                columns=[]
                for id in sorted(roots,key=lambda id:(boxes[id][0],boxes[id][1])):
                    if id in full:continue
                    matches=[c for c in columns if all(overlap(boxes[id],boxes[x])>=CONFIG['column_overlap'] for x in c)]
                    if len(matches)==1:matches[0].append(id)
                    else:columns.append([id])
                zones.append(dict(page=n,route=rt,band=band,columns=columns,full_width_roots=[x for x in roots if x in full],status='geometry_proposal',cross_column_order='Docling presentation retained; independent-flow alternative unresolved' if len(columns)>1 else 'single_column',extents_are_derived_not_regions=True))
                for col in columns:
                    col.sort(key=lambda id:(boxes[id][1],boxes[id][0]))
                    for a,b in zip(col,col[1:]):
                        if boxes[a][1]<boxes[b][1] and boxes[a][3]<=boxes[b][1]+tolerance:candidates.append((a,b,'local_column_vertical_geometry'))
            # Full-width separators only constrain clearly disjoint physical bands.
            for f in full:
                for id,b in boxes.items():
                    if id==f or not b:continue
                    if b[3]<=boxes[f][1]:candidates.append((id,f,'above_full_width_separator'))
                    elif boxes[f][3]<=b[1]:candidates.append((f,id,'below_full_width_separator'))
            for a,b,basis in candidates:
                edge=(a,b)
                try:stable_topological(ids,edges|{edge})
                except ValueError:suspended.append(dict(page=n,route=rt,**{'from':a,'to':b},basis=basis,reason='conflicts_with_existing_constraint',alternatives=['retain_Docling_order']));continue
                edges.add(edge);edges_trace.append(dict(page=n,route=rt,**{'from':a,'to':b},basis=basis,status='provisional_unvalidated'))
            chosen=stable_topological(ids,edges);final.extend(chosen)
            for id in ids:
                if chosen.index(id)!=ids.index(id):steps[id]['warnings'].append(warning('structure_geometry_order_proposal'));steps[id]['order_basis']='structure_geometry_proposal'
        route['sequence']=final;route['expanded_sequence']=[x for id in final for x in [id]+steps[id]['children']]
    retained=[copy.deepcopy(r) for r in out['relations'] if r['type'] not in ('next_in_route','paragraph_continues','precedes')]
    for rt,route in out['routes'].items():
        for a,b in zip(route['expanded_sequence'],route['expanded_sequence'][1:]):retained.append(dict(type='next_in_route',scope='steps',**{'from':a,'to':b},route=rt,status='provisional_unvalidated'))
    positions={id:(rt,i) for rt,r in out['routes'].items() for i,id in enumerate(r['expanded_sequence'])}
    for rel in baseline['relations']:
        if rel['type']=='precedes' and rel.get('basis')=='retained_precedence':
            a,b=positions[rel['from']],positions[rel['to']]
            if a[0]==b[0] and a[1]<b[1]:retained.append(copy.deepcopy(rel))
            else:suspended.append(dict(edge=copy.deepcopy(rel),reason='retained_constraint_conflicts_with_operational_flow',alternatives=['baseline_order_and_routes']))
    for e in edges_trace:retained.append(dict(type='precedes',scope='steps',**{'from':e['from'],'to':e['to']},basis=e['basis'],status=e['status']))
    out['relations']=retained;out['operational_connection']=dict(route_changes=changes,precedence_proposals=edges_trace,suspended=suspended,zones=zones,baseline_order_retained_as_alternative=True)
    return out
