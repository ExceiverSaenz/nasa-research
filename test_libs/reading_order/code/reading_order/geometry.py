import math


def _check(box, width, height, rotation):
    if (box is None or len(box) != 4 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in box)
            or width is None or height is None or width <= 1 or height <= 1
            or rotation not in (0, 90, 180, 270) or box[2] <= box[0] or box[3] <= box[1]):
        raise ValueError('Invalid or unresolved geometry')


def _rotate(x, y, width, height, rotation):
    return {0: (x, y), 90: (height-y, x), 180: (width-x, height-y), 270: (y, width-x)}[rotation]


def convert_box(box, width, height, *, scale='normalized', origin='top_left', rotation=0):
    _check(box, width, height, rotation)
    if scale not in ('normalized', 'points', 'pixels') or origin not in ('top_left', 'bottom_left'):
        raise ValueError('Unknown coordinate system')
    if scale == 'normalized' and (min(box) < 0 or max(box) > 1):
        raise ValueError('Normalized box outside page')
    xs = [box[0], box[2]]
    ys = [box[1], box[3]]
    if scale == 'normalized':
        xs = [x*width for x in xs]
        ys = [y*height for y in ys]
    corners = [_rotate(x, height-y if origin == 'bottom_left' else y, width, height, rotation) for x in xs for y in ys]
    return [min(p[0] for p in corners), min(p[1] for p in corners), max(p[0] for p in corners), max(p[1] for p in corners)]


def inverse_box(box, width, height, *, scale='normalized', origin='top_left', rotation=0):
    rw, rh = (height, width) if rotation in (90, 270) else (width, height)
    result = convert_box(box, rw, rh, scale='points', rotation=(360-rotation) % 360)
    if origin == 'bottom_left':
        result = [result[0], height-result[3], result[2], height-result[1]]
    if scale == 'normalized':
        return [result[0]/width, result[1]/height, result[2]/width, result[3]/height]
    return result


def to_points(block, page):
    return convert_box(block.bbox, page['width'], page['height'], rotation=0), {
        'source': 'normalized_top_left', 'rotation_applied': 0,
        'pdf_rotation': page['rotation'], 'reason': 'MinerU coordinates already refer to displayed page'}
