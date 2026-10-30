"""Exportación JSON/overlay y geometría PDF-render sin dependencias GPU.

Consume Predictions y RenderedPage; run_page decide el directorio y el estado final.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .types import Predictions, RenderedPage


def save_json(path: Path, data: dict) -> None:
    """Serializa JSON estricto mediante archivo temporal y replace.

    Args:
        path: Destino cuyo directorio padre debe existir.
        data: Mapping serializable por json.dumps.
    Returns:
        None.
    Raises:
        ValueError: NaN/Infinity no admitidos.
        TypeError: Contenido no serializable.
        OSError: Fallo de escritura o replace.
    Notes:
        Escribe path + '.part' y reemplaza el destino si existe. No crea padres,
        no usa fsync y no garantiza recuperación ante fallos de almacenamiento.
    """
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.part')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def render_geometry(page: RenderedPage) -> dict:
    """Calcula matrices homogéneas PDF-render y su inversa.

    Args:
        page: RenderedPage con caja PDF en puntos y rotación aplicada.
    Returns:
        dict de dimensiones, unidades, origen y matrices 3x3.
    Raises:
        numpy.linalg.LinAlgError: Si la matriz no pudiera invertirse.
    Notes:
        PDF: origen inferior izquierdo; render: superior izquierdo, píxeles.
        Usa dimensiones reales para considerar redondeo. Sin escritura ni mutación.
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
    """Guarda regiones comunes y arrays postprocessed sin remapear categorías.

    Args:
        predictions: Predicciones válidas en coordenadas del render.
        rendered_page: Página cuyo tamaño debe coincidir con las predicciones.
        output_dir: Directorio existente para regions.json y regions-raw.json.
        document_id: Identidad del documento; el coordinador utiliza su SHA-256.
        run_id: Identificador de la ejecución usado en IDs de región.
    Returns:
        None.
    Raises:
        ValueError: Dimensiones de predicción y render distintas.
        Exception: Errores de geometría o save_json se propagan.
    Notes:
        Escribe dos JSON secuencialmente; puede quedar exportación parcial.
        Raw significa salida tras filtering/NMS y postprocessing. Doc-Refs: INF-005.
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
    """Dibuja cajas, IDs, categorías y scores sobre una copia del render.

    Args:
        predictions: Cajas XYXY en píxeles del render original.
        rendered_page: Imagen RGB original y dpi para dibujo y metadatos PNG.
        output_dir: Directorio existente donde escribir overlay.png.
    Returns:
        None.
    Raises:
        Exception: Errores de dibujo y escritura Pillow se propagan.
    Notes:
        No modifica la imagen original. Intenta DejaVuSans y usa fallback si falta.
        El coordinador guarda regiones antes, donde comprueba dimensiones.
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
    """Guarda run-manifest.json mediante save_json.

    Args:
        run_metadata: Metadatos serializables de la ejecución.
        output_dir: Directorio existente.
    Returns:
        None.
    Raises:
        Exception: Errores de serialización o escritura se propagan.
    Notes:
        Puede reemplazar el manifest previo de la misma ejecución.
    """
    save_json(Path(output_dir) / 'run-manifest.json', run_metadata)
