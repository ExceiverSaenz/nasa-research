"""Conservative correspondence from TEI to native spans and reconciled units."""
import math
import re
import unicodedata
from collections import Counter


def normalize(text):return ' '.join(unicodedata.normalize('NFKC',text or '').casefold().split())
def tokens(text):return normalize(text).split()
def intersects(a,b):return max(a[0],b[0])<min(a[2],b[2]) and max(a[1],b[1])<min(a[3],b[3])


def matching_view(spans,separator):
    """Map normalized matching characters to source spans, never invent character bbox."""
    chars=[];sources=[]
    for i,s in enumerate(spans):
        if i:
            for c in separator:chars.append(c);sources.append(None)
        value=unicodedata.normalize('NFKC',s['text']).casefold()
        for c in value:chars.append(c);sources.append(s['key'])
    out=[];refs=[]
    for c,key in zip(chars,sources):
        if c.isspace():
            if out and out[-1]!=' ':out.append(' ');refs.append(key)
        else:out.append(c);refs.append(key)
    if out and out[-1]==' ':out.pop();refs.pop()
    view=''.join(out)
    if view!=normalize(separator.join(s['text'] for s in spans)):return '',[]
    return view,refs


def exact_span_occurrence(spans,text):
    variants=[matching_view(spans,sep) for sep in (' ','')]
    found=[]
    for view,refs in variants:
        positions=[m.start() for m in re.finditer('(?='+re.escape(text)+')',view)]
        if len(positions)>1:return None
        if positions:
            start=positions[0];keys={k for k in refs[start:start+len(text)] if k is not None}
            found.append((view,keys,start,start+len(text)))
    if not found:return None
    if any(f[1]!=found[0][1] for f in found):return None
    return found[0]


def align_tei(evidence,baseline_B):
    B=baseline_B;pages={p['page']:p for p in B['native_pages']};surfaces={p['page']:p for p in evidence['pages'] if 'page' in p};spans=[]
    for e in B['native_evidence']:
        if e['kind']!='text_block':continue
        for li,line in enumerate(e['data']['lines']):
            for si,s in enumerate(line['spans']):spans.append(dict(key=(e['id'],f'/data/lines/{li}/spans/{si}'),page=e['page'],bbox=s['bbox'],text=s['text']))
    native_links={x['unit_ref']:x for x in B['evidence_links']};eligible={i['unit_ref']:i for i in B['inventory'] if i['disposition'] not in ('deferred_child_reference','structural_reference') and i['original_unit'].get('bbox_xyxy')}
    owners={s['key']:[] for s in spans}
    for id,i in eligible.items():
        if native_links[id]['status']!='span_centers_supported':continue
        for ref in native_links[id]['span_refs']:
            key=(ref['evidence_ref'],ref['pointer'])
            if key in owners:owners[key].append(id)
    result=[]
    for node in evidence['nodes']:
        link=dict(evidence_ref=node['id'],status='unlocated',matches=[],candidates=[],native_span_refs=[],matching_text='',warning='Requiere validación humana',source_family='grobid',probability=None)
        result.append(link);text=normalize(node['text'])
        if node['coordinate_errors']:link['status']='unusable_geometry';continue
        areas=node['coords'];bad=False
        for a in areas:
            p=pages.get(a['page']);s=surfaces.get(a['page'])
            if not p or not s or p.get('rotation',0)!=0 or p.get('crop_box')!=p.get('media_box') or s['origin']!=[0,0] or abs(p['width_pt']-s['width'])>.01 or abs(p['height_pt']-s['height'])>.01 or a['bbox'][2]>s['width'] or a['bbox'][3]>s['height']:bad=True
        if bad:link['status']='unusable_geometry';continue
        if not text:continue
        selected=[]
        if areas:
            for a in areas:
                group=[s for s in spans if s['page']==a['page'] and a['bbox'][0]<=(s['bbox'][0]+s['bbox'][2])/2<=a['bbox'][2] and a['bbox'][1]<=(s['bbox'][1]+s['bbox'][3])/2<=a['bbox'][3]]
                group.sort(key=lambda s:(s['bbox'][1],s['bbox'][0]))
                selected.extend(s for s in group if s['key'] not in {x['key'] for x in selected})
            hit=exact_span_occurrence(selected,text);exact_ok=hit is not None
            link['matching_text']=hit[0] if hit else normalize(' '.join(s['text'] for s in selected))
            if hit:
                selected=[s for s in selected if s['key'] in hit[1]]
                link['matching_offsets']=dict(start=hit[2],end=hit[3],unit='normalized_matching_view_codepoints')
        else:
            # No inherited parent bbox: only exact unique native text anchors qualify.
            byblock={}
            for s in spans:byblock.setdefault(s['key'][0],[]).append(s)
            hits=[]
            for ss in byblock.values():
                hit=exact_span_occurrence(ss,text)
                if hit:hits.append(([s for s in ss if s['key'] in hit[1]],hit[0],hit[2],hit[3]))
                elif any(text in matching_view(ss,sep)[0] for sep in (' ','')):hits.extend([(ss,'',0,0),(ss,'',0,0)])
            exact_ok=len(hits)==1
            if exact_ok:selected=hits[0][0];link['matching_text']=hits[0][1];link['matching_offsets']=dict(start=hits[0][2],end=hits[0][3],unit='normalized_matching_view_codepoints')
            elif hits:
                link['status']='ambiguous_alignment'
                for ss,_,_,_ in hits:
                    for s in ss:
                        for id in owners[s['key']]:link['candidates'].append(dict(unit_ref=id,reason='repeated_text_anchor'))
                continue
        selected_keys={s['key'] for s in selected};found={id for key in selected_keys for id in owners[key]}
        # Exact native occurrence must also be localized to each mapped region's text.
        matching=[]
        for id in found:
            nt=normalize(native_links[id]['native_text']);ntjoined=normalize(''.join(native_links[id]['native_text'].splitlines()))
            related=bool(nt and (text in nt or nt in text or ntjoined in text))
            if exact_ok and related:
                scope='whole_region' if nt==text or nt and nt in text else 'fragment'
                matching.append(dict(unit_ref=id,scope=scope,native_text=nt,text_exact=True))
            else:
                shared=sum((Counter(tokens(text)) & Counter(tokens(nt))).values());den=max(1,len(tokens(text)))
                link['candidates'].append(dict(unit_ref=id,text_token_coverage=shared/den,reason='geometry_or_fuzzy_only'))
        if matching:
            # Two regions using the same spans cannot be claimed as an unambiguous fragment set.
            collision=any(len({id for id in owners[k] if id in {m['unit_ref'] for m in matching}})>1 for k in selected_keys)
            if collision:link['status']='ambiguous_alignment';link['candidates'].extend(matching)
            else:link['status']='aligned_unique' if len(matching)==1 else 'aligned_fragment_set';link['matches']=sorted(matching,key=lambda m:next((j for j,s in enumerate(selected) if m['unit_ref'] in owners[s['key']]),0))
        elif link['candidates']:link['status']='ambiguous_alignment'
        link['native_span_refs']=[dict(evidence_ref=k[0],pointer=k[1]) for k in sorted(selected_keys)]
    return result
