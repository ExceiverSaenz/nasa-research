"""JSON/overlay export and PDF-render geometry without GPU dependencies.

Consumes Predictions and RenderedPage; run_page determines the directory and final status.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .types import Predictions, RenderedPage


def save_json(path: Path, data: dict) -> None:
    """Serializes strict JSON using a temporary file and replace.

    Args:
        path: Destination whose parent directory must exist.
        data: Mapping serializable by json.dumps.
    Returns:
        None.
    Raises:
        ValueError: NaN/Infinity not allowed.
        TypeError: Nonserializable content.
        OSError: Write or replace failure.
    Notes:
        Writes path + '.part' and replaces the destination if present. Does not create parents,
        use fsync or guarantee recovery from storage failures.
    """
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.part')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def render_geometry(page: RenderedPage) -> dict:
    """Computes homogeneous PDF-render matrices and their inverse.

    Args:
        page: RenderedPage with PDF box in points and rotation applied.
    Returns:
        dict of dimensions, units, origin and 3x3 matrices.
    Raises:
        numpy.linalg.LinAlgError: If the matrix cannot be inverted.
    Notes:
        PDF: bottom-left origin; render: top-left, pixels.
        Uses actual dimensions to account for rounding. No writing or mutation.
        Doc-Refs: INF-005.
    """
    x0, y0, x1, y1 = page.crop_box_pt
    rotated = page.rotation_deg in (90, 270)
    sx = page.width_px / ((y1 - y0) if rotated else (x1 - x0))
    sy = page.height_px / ((x1 - x0) if rotated else (y1 - y0))
    matrices = {
        0: [[sx, 0, -sx * x0], [0, -sy, sy * y1], [0, 0, 1]],
        90: [[0, sx, -sx * y0], [sy, 0, -sy * x0], [0, 0, 1]],
        180: [[-sx, 0, sx * x1], [0, sy, -sy * y0], [0, 0, 1]],
        270: [[0, -sx, sx * y1], [-sy, 0, sy * x1], [0, 0, 1]],
    }
    matrix = np.array(matrices[page.rotation_deg], dtype=float)
    return {'dpi': page.dpi, 'width_px': page.width_px, 'height_px': page.height_px,
            'color': 'RGB', 'crop_box_pt': page.crop_box_pt, 'rotation_deg': page.rotation_deg,
            'coordinate_system': {'unit': 'pixel', 'origin': 'top-left', 'bbox_format': 'xyxy'},
            'pdf_to_render_matrix': matrix.tolist(),
            'render_to_pdf_matrix': np.linalg.inv(matrix).tolist()}


def save_regions(predictions: Predictions, rendered_page: RenderedPage,
                 output_dir: Path, *, document_id: str, run_id: str) -> None:
    """Saves common regions and postprocessed arrays without remapping categories.

    Args:
        predictions: Valid predictions in render coordinates.
        rendered_page: Page whose size must match the predictions.
        output_dir: Existing directory for regions.json and regions-raw.json.
        document_id: Document identity; the coordinator uses its SHA-256.
        run_id: Run identifier used in region IDs.
    Returns:
        None.
    Raises:
        ValueError: Prediction and render dimensions differ.
        Exception: Geometry or save_json errors propagate.
    Notes:
        Writes two JSON files sequentially; export may remain partial.
        Raw means output after filtering/NMS and postprocessing. Doc-Refs: INF-005.
    """
    if (predictions.image_width_px, predictions.image_height_px) != (rendered_page.width_px, rendered_page.height_px):
        raise ValueError('Prediction and render dimensions differ')
    regions = []
    for index, (box, class_id, score) in enumerate(zip(
            predictions.boxes_xyxy, predictions.class_ids, predictions.scores), 1):
        label = predictions.class_names[int(class_id)]
        regions.append({'region_id': '{}-p{}-r{}'.format(run_id, rendered_page.page_number, index),
                        'bbox': box.tolist(), 'class_id': int(class_id),
                        'type': label, 'native_label': label, 'score': float(score)})
    common = {'document_id': document_id, 'run_id': run_id, 'page': rendered_page.page_number,
              'coordinate_system': render_geometry(rendered_page)}
    save_json(Path(output_dir) / 'regions.json', dict(common, regions=regions))
    # Raw means unmodified detector output after its normal filtering/NMS and
    # coordinate postprocessing, not proposals or logits before NMS.
    save_json(Path(output_dir) / 'regions-raw.json', dict(common,
              stage='detector_postprocessed', class_names=predictions.class_names,
              boxes_xyxy=predictions.boxes_xyxy.tolist(), class_ids=predictions.class_ids.tolist(),
              scores=predictions.scores.tolist()))


def save_overlay(predictions: Predictions, rendered_page: RenderedPage, output_dir: Path) -> None:
    """Draws boxes, IDs, categories and scores on a copy of the render.

    Args:
        predictions: XYXY boxes in original-render pixels.
        rendered_page: Original RGB image and dpi for drawing and PNG metadata.
        output_dir: Existing directory in which to write overlay.png.
    Returns:
        None.
    Raises:
        Exception: Pillow drawing and writing errors propagate.
    Notes:
        Does not modify the original image. Tries DejaVuSans and uses fallback if missing.
        The coordinator saves regions first, where it checks dimensions.
    """
    image = Image.fromarray(rendered_page.image.copy())
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', max(12, rendered_page.dpi // 12))
    except OSError:
        font = ImageFont.load_default()
    colors = ('#0066cc', '#8b008b', '#b45f06', '#008000', '#cc0000')
    for index, (box, class_id, score) in enumerate(zip(
            predictions.boxes_xyxy, predictions.class_ids, predictions.scores), 1):
        color = colors[int(class_id) % len(colors)]
        draw.rectangle(tuple(float(v) for v in box), outline=color, width=max(2, rendered_page.dpi // 75))
        label = '{} {} {:.2f}'.format(index, predictions.class_names[int(class_id)], float(score))
        bounds = draw.textbbox((0, 0), label, font=font)
        w, h = bounds[2] - bounds[0] + 6, bounds[3] - bounds[1] + 6
        x = max(0, min(float(box[0]), rendered_page.width_px - w))
        y = max(0, float(box[1]) - h)
        draw.rectangle((x, y, x + w, y + h), fill='white')
        draw.text((x + 3, y + 3 - bounds[1]), label, fill=color, font=font)
    image.save(Path(output_dir) / 'overlay.png', dpi=(rendered_page.dpi, rendered_page.dpi))


def save_manifest(run_metadata: dict, output_dir: Path) -> None:
    """Saves run-manifest.json through save_json.

    Args:
        run_metadata: Serializable run metadata.
        output_dir: Existing directory.
    Returns:
        None.
    Raises:
        Exception: Serialization or write errors propagate.
    Notes:
        May replace the previous manifest from the same run.
    """
    save_json(Path(output_dir) / 'run-manifest.json', run_metadata)
