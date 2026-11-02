import hashlib
import json
import math


def normalize_box(box,width,height,system,rotation=0):
    if len(box)!=4 or not all(isinstance(n,(float,int)) and not isinstance(n,bool) and math.isfinite(n) for n in box):raise ValueError('Invalid box')
    if width<=0 or height<=0:raise ValueError('Invalid page')
    x0,y0,x1,y1=box
    if system in ('pixels_top_left','points_top_left','points_bottom_left'):
        x0,x1=x0/width,x1/width;y0,y1=y0/height,y1/height
    elif system!='normalized_top_left':raise ValueError('Unknown coordinate system')
    if system=='points_bottom_left':y0,y1=1-y1,1-y0
    if not (0<=x0<x1<=1 and 0<=y0<y1<=1):raise ValueError('Out of bounds or degenerate box')
    if rotation==90:return [1-y1,x0,1-y0,x1]
    if rotation==180:return [1-x1,1-y1,1-x0,1-y0]
    if rotation==270:return [y0,1-x1,y1,1-x0]
    if rotation!=0:raise ValueError('Invalid rotation')
    return [x0,y0,x1,y1]


def normalize(raw,source):
    box=raw.get('bbox');error=None;normalized=None
    if box is not None:
        try:normalized=normalize_box(box,source['width'],source['height'],source['coordinates'],source.get('rotation',0))
        except ValueError as e:error=str(e)
    identity=json.dumps([source,raw],sort_keys=True,ensure_ascii=False)
    return dict(id=hashlib.sha256(identity.encode()).hexdigest()[:24],tool=source['tool'],
                paper_sha256=source['paper_sha256'],page_idx=source['page_idx'],raw_label=raw.get('label',raw.get('type')),
                bbox_raw=box,bbox_normalized=normalized,coordinate_system=source['coordinates'],
                page_dimensions=[source['width'],source['height']],original_ref=source['original_ref'],
                original_sha256=source['original_sha256'],relations=raw.get('relations'),geometry_error=error)
