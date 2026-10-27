"""JSON, overlay and no-padding crops. Keep original model boxes separate from clipped pixels."""
import json
import math
from pathlib import Path

from PIL import ImageDraw, ImageFont


def save_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.part')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def save_outputs(image, raw, regions, output_dir):
    output_dir = Path(output_dir)
    # Preserve expensive inference outputs before any derivative image operation.
    save_json(output_dir/'regions-raw.json', raw)
    save_json(output_dir/'regions.json', {
        'coordinate_system': {'width_px': image.width, 'height_px': image.height,
                              'unit': 'pixel', 'origin': 'top-left', 'bbox_format': 'xyxy'},
        'regions': [dict(region) for region in regions]})
    (output_dir/'crops').mkdir()
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 20)
    except OSError:
        font = ImageFont.load_default()
    output = []
    for region in regions:
        item = dict(region)
        x1, y1, x2, y2 = item['bbox']
        crop = [max(0, min(image.width, math.floor(x1))), max(0, min(image.height, math.floor(y1))),
                max(0, min(image.width, math.ceil(x2))), max(0, min(image.height, math.ceil(y2)))]
        item['crop_bbox'] = crop
        item['crop_clipped'] = bool(x1 < 0 or y1 < 0 or x2 > image.width or y2 > image.height)
        item['crop_rounding'] = 'floor top-left, ceil bottom-right; zero padding'
        item['crop_path'] = None
        if crop[0] < crop[2] and crop[1] < crop[3]:
            item['crop_path'] = 'crops/query-{}.png'.format(item['query_id'])
            image.crop(tuple(crop)).save(output_dir/item['crop_path'])
        draw.rectangle((x1, y1, x2, y2), outline='green', width=3)
        label = 'q{} {} {:.3f}'.format(item['query_id'], item['native_label'], item['score'])
        draw.text((max(0,x1), max(0,y1-24)), label, font=font, fill='green', stroke_width=1, stroke_fill='white')
        output.append(item)
    overlay.save(output_dir/'overlay.png', dpi=(200, 200))
    document = {'coordinate_system': {'width_px': image.width, 'height_px': image.height,
                                     'unit': 'pixel', 'origin': 'top-left', 'bbox_format': 'xyxy'},
                'regions': output}
    save_json(output_dir/'regions.json', document)
    return document
