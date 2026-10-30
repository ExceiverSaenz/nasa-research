"""DocVortex 0.6 MiddleJson normalized geometry to original PNG pixels."""
import json
import math
from pathlib import Path

from PIL import ImageDraw

CONTAINERS = {'image','table','chart','code','list','index'}


def save_json(path, value):
    path=Path(path); temporary=path.with_suffix(path.suffix+'.part')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    temporary.replace(path)


def convert_regions(document, width, height):
    if (document.get('schema')!='docvortex.middle' or document.get('schema_version')!='2.0'
            or len(document.get('pages',[]))!=1 or document['pages'][0]['page_idx']!=0):
        raise ValueError('Expected one-page DocVortex MiddleJson 2.0')
    if any(type(v) is not int or v<=0 for v in (width,height)):
        raise ValueError('Invalid image dimensions')
    regions=[]; warnings=[]
    def visit(block, identifier, pointer, parent=None):
        box=block.get('bbox'); pixel_box=None
        if box is None: warnings.append(identifier)
        else:
            if (not isinstance(box,(list,tuple)) or len(box)!=4
                    or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)
                           or not 0<=v<=1 for v in box) or box[2]<=box[0] or box[3]<=box[1]):
                raise ValueError('Invalid normalized bbox at '+pointer)
            pixel_box=[float(v)*scale for v,scale in zip(box,(width,height,width,height))]
        regions.append({'region_id':identifier,'parent_id':parent,'source_pointer':pointer,
                        'native_label':block['type'],'native_index':block.get('index'),
                        'bbox_normalized':box,'bbox':pixel_box,'score':None})
        if block['type'] in CONTAINERS:
            for index,child in enumerate(block.get('content',[])):
                visit(child,identifier+'-c'+str(index),pointer+'/content/'+str(index),identifier)
    for index,block in enumerate(document['pages'][0]['blocks']):
        visit(block,'p0-b'+str(index),'/pages/0/blocks/'+str(index))
    return {'coordinate_system':{'width_px':width,'height_px':height,'unit':'pixel',
                                'origin':'top-left','bbox_format':'xyxy','native_bbox':'normalized [0,1]'},
            'regions':regions,'geometry_warnings':warnings,
            'note':'Parent and child boxes coexist; region count is not object count.'}


def export_regions(image, document, output):
    output=Path(output)
    result=convert_regions(document,*image.size)
    save_json(output/'regions.json',result)
    (output/'crops').mkdir(exist_ok=False)
    overlay=image.copy();draw=ImageDraw.Draw(overlay)
    for region in result['regions']:
        box=region['bbox']
        if box is None: continue
        crop=[math.floor(box[0]),math.floor(box[1]),math.ceil(box[2]),math.ceil(box[3])]
        region.update(crop_bbox=crop,crop_clipped=False,crop_path='crops/'+region['region_id']+'.png')
        image.crop(tuple(crop)).save(output/region['crop_path'])
        color='green' if region['parent_id'] is None else 'blue'
        draw.rectangle(box,outline=color,width=2)
        draw.text((box[0],max(0,box[1]-14)),region['region_id']+' '+region['native_label'],fill=color)
    overlay.save(output/'overlay.png',dpi=(200,200))
    save_json(output/'regions.json',result)
    return result
