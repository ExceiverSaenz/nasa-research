"""Geometric span alignment without assigning new reconciled coordinates."""
import unicodedata
from integration.reading_order.layout import valid_box


def compact(text):return ''.join(c for c in unicodedata.normalize('NFKC',text or '').casefold() if c.isalnum())


def align_native(native,baseline):
    pages={p['page']:p for p in native['pages']};render={p['identity']['physical_page']:p for p in baseline['original_page_context']};result=[]
    for item in baseline['inventory']:
        id=item['unit_ref'];u=item['original_unit'];n=u['page'];r=render[n];i=r['identity'];box=u.get('bbox_xyxy');link=dict(unit_ref=id,page=n,evidence_refs=[],span_refs=[],native_text='',status='unmatched')
        if item['disposition']=='deferred_child_reference' or not valid_box(box,i['width_px'],i['height_px']):link['status']='deferred' if item['disposition']=='deferred_child_reference' else 'no_own_geometry';result.append(link);continue
        if r.get('original_status')=='blocked' or 'invalid_geometry' in r.get('original_incidents',[]):link['status']='geometry_abstained';result.append(link);continue
        if n not in pages:link['status']='native_page_unavailable';result.append(link);continue
        p=pages[n];b=[box[0]*p['width_pt']/i['width_px'],box[1]*p['height_pt']/i['height_px'],box[2]*p['width_pt']/i['width_px'],box[3]*p['height_pt']/i['height_px']]
        link.update(native_extent_for_matching=b,transform=dict(source='render_top_left_pixels',target='PyMuPDF_unrotated_top_left_points',scale=[p['width_pt']/i['width_px'],p['height_pt']/i['height_px']],rotation=p['rotation']))
        if p['rotation']!=0:link['status']='unsupported_rotation_mapping';result.append(link);continue
        chunks=[]
        for e in native['evidence']:
            if e['kind']!='text_block' or e['page']!=n:continue
            found=False
            for li,line in enumerate(e['data']['lines']):
                spans=[]
                for si,s in enumerate(line['spans']):
                    bb=s['bbox'];x=(bb[0]+bb[2])/2;y=(bb[1]+bb[3])/2
                    if b[0]<=x<=b[2] and b[1]<=y<=b[3]:
                        spans.append(s['text']);link['span_refs'].append(dict(evidence_ref=e['id'],pointer=f'/data/lines/{li}/spans/{si}'));found=True
                if spans:chunks.append(''.join(spans))
            if found:link['evidence_refs'].append(e['id'])
        link['native_text']='\n'.join(chunks);link['status']='span_centers_supported' if chunks else 'unmatched'
        link['text_is_matching_view_not_replacement']=True;result.append(link)
    return result
