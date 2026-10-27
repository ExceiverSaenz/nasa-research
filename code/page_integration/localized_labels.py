"""Pure geometry and evidence association; deliberately no OCR dependencies."""
import copy
import math
import re

LABEL = re.compile(r'^\s*table\s*(\d+)\b[.:]?\s*', re.I)


def normalized_text(text):
    return ' '.join(text.split()).casefold()


def compare_uo2(left,right):
    """Only the approved explicit chemical representation; never generic TeX stripping."""
    pattern=re.compile(r'(?<![\w\\])\\mathrm\{UO\}_\{2\}(?!\w)')
    rules=[]
    def convert(text):
        value,count=pattern.subn('UO2',text)
        if count and 'latex_mathrm_UO_subscript_2' not in rules:rules.append('latex_mathrm_UO_subscript_2')
        return normalized_text(value)
    a,b=convert(left),convert(right)
    return dict(left_literal=left,right_literal=right,left_compared=a,right_compared=b,
                applied_rules=rules,equal=a==b)


def propose_caption_lines(target,evidence,roi):
    """A two-line layout hypothesis, NEVER line-level OCR text or visual verification."""
    candidates=[]
    for block in evidence:
        # Keep leading table references as rejected evidence, rather than invent a match.
        if not re.search(r'table\s*\d+',block['text'],re.I):continue
        c=copy.deepcopy(block);c.update(object_id=target['object_id'],reasons=[],eligible=False,
            original_block_bbox=copy.deepcopy(block['bbox']),line_text_status='not_provided_by_parser',
            links_verified=False,method='two_native_lines_hypothesis_v1')
        match=LABEL.match(block['text'])
        if not match:c['reasons'].append('not_leading_label')
        else:
            c['label_text']=block['text'][:match.end()].strip()
            c['description_literal']=block['text'][match.end():]
            c['description_comparison']=compare_uo2(c['description_literal'],target['description'])
            if not c['description_comparison']['equal']:c['reasons'].append('description_mismatch')
        if target['object_id']!='p0-b4' or block.get('roi_id')!=target['object_id']:c['reasons'].append('outside_approved_target')
        if block.get('native_type')!='caption':c['reasons'].append('not_caption')
        if target.get('status')!='ready':c['reasons'].append('roi_ambiguous')
        lines=block.get('lines',[])
        if len(lines)!=2:c['reasons'].append('line_count_not_two')
        else:
            try:
                boxes=[original_box(line['bbox'],roi) for line in lines]
                for i,box in enumerate(boxes):
                    if not (block['bbox'][0]<=box[0]<box[2]<=block['bbox'][2] and
                            block['bbox'][1]<=box[1]<box[3]<=block['bbox'][3]):
                        c['reasons'].append('line_outside_caption')
                if boxes[0][3]>boxes[1][1]:c['reasons'].append('lines_overlap_or_reversed')
                if horizontal(boxes[0],target['caption_bbox'])<.5 or horizontal(boxes[1],target['caption_bbox'])<.5:
                    c['reasons'].append('column_mismatch')
                if boxes[1][3]>target['body_bbox'][1]:c['reasons'].append('description_after_body_start')
                for i,role in enumerate(('label_line','description_line')):
                    box=boxes[i]
                    inverse=[(box[0]-roi[0])/(roi[2]-roi[0]),(box[1]-roi[1])/(roi[3]-roi[1]),
                             (box[2]-roi[0])/(roi[2]-roi[0]),(box[3]-roi[1])/(roi[3]-roi[1])]
                    error=max(abs(a-b)*scale for a,b,scale in zip(lines[i]['bbox'],inverse,(roi[2]-roi[0],roi[3]-roi[1])*2))
                    c[role]=dict(bbox=box,bbox_native=copy.deepcopy(lines[i]['bbox']),
                        source_pointer=block['source_pointer']+'/lines/'+str(i)+'/bbox',
                        source_member=block['source_member'],source_sha256=block['source_sha256'],
                        roundtrip_error_px=error,text_assignment='hypothesis_pending_visual_review')
                    if error>1:c['reasons'].append('roundtrip_over_1px')
                if any(other is not block and other.get('text','').strip() and
                    other['bbox'][1]>=boxes[0][3] and other['bbox'][3]<=boxes[1][1] and
                    horizontal(other['bbox'],target['caption_bbox'])>=.5 for other in evidence):
                    c['reasons'].append('intervening_text')
            except (ValueError,KeyError,TypeError):c['reasons'].append('invalid_line_geometry')
        c['eligible']=not c['reasons'];candidates.append(c)
    viable=[c for c in candidates if c['eligible']]
    return dict(object_id=target['object_id'],caption_id=target['caption_id'],body_id=target['body_id'],
        status='proposed_pending_visual_review' if len(viable)==1 else 'ambiguous',
        candidates=candidates,selected_candidate=viable[0] if len(viable)==1 else None,links_verified=False)


def verify_line_review(candidate,review,result_sha256):
    """Review is a separate, source-bound assertion, never inferred from geometry."""
    if not candidate.get('eligible') or not isinstance(review,dict):return False
    expected=dict(method='visual',result_archive_sha256=result_sha256,
        candidate_source_sha256=candidate['source_sha256'],candidate_source_member=candidate['source_member'],
        candidate_source_pointer=candidate['source_pointer'],object_id=candidate['object_id'],
        label_line_pointer=candidate['label_line']['source_pointer'],
        description_line_pointer=candidate['description_line']['source_pointer'],
        label_line_contains_label=True,description_line_contains_description=True,correct_table=True)
    return (isinstance(review.get('reviewer'),str) and bool(review['reviewer'].strip()) and
            all(type(review.get(k)) is type(v) and review.get(k)==v for k,v in expected.items()))


def checked_box(box, width=None, height=None):
    if (not isinstance(box,(list,tuple)) or len(box)!=4 or
        any(type(v) not in (int,float) or not math.isfinite(v) for v in box) or
        box[0]<0 or box[1]<0 or box[2]<=box[0] or box[3]<=box[1] or
        (width is not None and box[2]>width) or (height is not None and box[3]>height)):
        raise ValueError('Invalid or incompatible box: '+repr(box))
    return list(box)


def horizontal(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0]))/min(a[2]-a[0],b[2]-b[0])


def select_rois(regions,width,height):
    result=[]
    for table in regions:
        if table['native_label']!='table' or table.get('parent_id') is not None: continue
        children=[r for r in regions if r.get('parent_id')==table['region_id']]
        caps=[r for r in children if r['native_label']=='table_caption']
        bodies=[r for r in children if r['native_label']=='table_body']
        if len(caps)!=1 or len(bodies)!=1: raise ValueError('Expected one caption and body per table')
        cap,body=caps[0],bodies[0]
        cb=checked_box(cap['bbox'],width,height);bb=checked_box(body['bbox'],width,height)
        tb=checked_box(table['bbox'],width,height)
        band=[min(tb[0],cb[0],bb[0]),0,max(tb[2],cb[2],bb[2]),max(tb[3],cb[3],bb[3])]
        excluded={r['region_id'] for r in children}|{table['region_id']}
        preceding=[];conflicts=[]
        for r in regions:
            if r['region_id'] in excluded or r.get('bbox') is None:continue
            # Parent containers duplicate body geometry. Use their leaf descendants instead.
            if any(x.get('parent_id')==r['region_id'] for x in regions):continue
            box=checked_box(r['bbox'],width,height)
            if horizontal(box,band)<.5:continue
            if box[3]<=cb[1]:preceding.append(r)
            elif box[1]<cb[1]<box[3]:conflicts.append(r['region_id'])
        top=max((r['bbox'][3] for r in preceding),default=0)
        barriers=[r['region_id'] for r in preceding if r['bbox'][3]==top]
        band[1]=top
        crop=[max(0,math.floor(band[0])),max(0,math.floor(band[1])),
              min(width,math.ceil(band[2])),min(height,math.ceil(band[3]))]
        checked_box(crop,width,height)
        result.append(dict(roi_id=table['region_id'],object_id=table['region_id'],
            caption_id=cap['region_id'],body_id=body['region_id'],bbox=crop,
            caption_bbox=cb,body_bbox=bb,caption_source_pointer=cap['source_pointer'],
            body_source_pointer=body['source_pointer'],status='roi_ambiguous' if conflicts else 'ready',
            barrier_ids=barriers,preceding_ids=[r['region_id'] for r in preceding],conflict_ids=conflicts,
            transform=dict(operation='crop_only',origin_px=crop[:2],size_px=[crop[2]-crop[0],crop[3]-crop[1]],
                           inverse='original=roi_origin+normalized*roi_size')))
    return result


def original_box(normalized,roi):
    b=checked_box(normalized,1,1);r=checked_box(roi)
    return [r[0]+b[0]*(r[2]-r[0]),r[1]+b[1]*(r[3]-r[1]),
            r[0]+b[2]*(r[2]-r[0]),r[1]+b[3]*(r[3]-r[1])]


def geometry_acceptance(candidate,reference):
    a=checked_box(candidate);b=checked_box(reference)
    def area(x):return (x[2]-x[0])*(x[3]-x[1])
    def intersection(x,y):return max(0,min(x[2],y[2])-max(x[0],y[0]))*max(0,min(x[3],y[3])-max(x[1],y[1]))
    inter=intersection(a,b);iou=inter/(area(a)+area(b)-inter)
    expanded=[max(0,b[0]-2),max(0,b[1]-2),b[2]+2,b[3]+2]
    coverage=intersection(a,expanded)/area(expanded)
    return dict(iou=iou,expanded_reference_coverage=coverage,passed=iou>=.5 and coverage>=.9)


def associate(targets,texts):
    """Preserve every label candidate, reasons and sources; no reference access."""
    results=[]
    for target in targets:
        expected=normalized_text(target['description']);candidates=[]
        for text in texts:
            match=LABEL.match(text['text'])
            # Body references remain in inspection output, never promoted to candidates.
            if not match:continue
            c=copy.deepcopy(text);c['label_text']=text['text'][:match.end()].strip()
            c['number']=match.group(1);c['reasons']=[]
            remainder=normalized_text(text['text'][match.end():])
            combined=bool(remainder)
            compatible=[]
            if combined and remainder==expected:compatible=[text]
            elif not combined:
                compatible=[d for d in texts if normalized_text(d['text'])==expected and
                    horizontal(d['bbox'],target['caption_bbox'])>=.5 and
                    d['bbox'][1]>=text['bbox'][3] and d['bbox'][3]<=target['body_bbox'][1]]
            if len(compatible)!=1:c['reasons'].append('description_missing_or_ambiguous')
            if horizontal(text['bbox'],target['caption_bbox'])<.5:c['reasons'].append('column_mismatch')
            if (not combined and text['bbox'][3]>target['caption_bbox'][1]) or text['bbox'][1]>=target['body_bbox'][1]:
                c['reasons'].append('not_before_description')
            if target.get('status')=='roi_ambiguous':c['reasons'].append('roi_ambiguous')
            if compatible:
                desc=compatible[0]
                if not combined and any(d is not text and d is not desc and
                    d['bbox'][1]>=text['bbox'][3] and d['bbox'][3]<=desc['bbox'][1] and
                    horizontal(d['bbox'],target['caption_bbox'])>=.5 for d in texts):
                    c['reasons'].append('intervening_text')
                c['description_evidence']=copy.deepcopy(desc)
            c['label_bbox_precision']='combined_block' if combined else 'recognized_block'
            c['eligible']=not c['reasons'];candidates.append(c)
        viable=[c for c in candidates if c['eligible']]
        selected=viable[0] if len(viable)==1 else None
        results.append(dict(object_id=target['object_id'],caption_id=target['caption_id'],body_id=target['body_id'],
            description=target['description'],state='both_linked' if selected else ('ambiguous' if candidates else 'description_only'),
            candidates=candidates,selected_label=selected,links_verified=False,
            native_evidence=dict(source=copy.deepcopy(target.get('native_source')),
                caption_pointer=target.get('caption_source_pointer'),body_pointer=target.get('body_source_pointer')),
            label_recovered=bool(viable),method='native_parentage_plus_localized_ocr_v1'))
    # The same physical candidate cannot silently attach to multiple objects.
    for result in results:
        selected=result['selected_label']
        if selected and any(other is not result and any(c['eligible'] and
            (c['source_member'],c['source_pointer'])==
            (selected['source_member'],selected['source_pointer']) for c in other['candidates']) for other in results):
            selected['reasons'].append('multiple_destinations')
    for result in results:
        if result['selected_label'] and result['selected_label']['reasons']:
            result['state']='ambiguous';result['selected_label']=None
    return results
