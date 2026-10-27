"""Reference-free audit of a page, using only the standard library.

Does not modify regions, discard predictions or estimate precision/recall. Format
failures are technical errors; duplication, conflict and nesting are alerts.
"""
from collections import Counter
from itertools import combinations
import math
from typing import Any, Dict, Mapping


NATIVE_CLASSES = ('text', 'title', 'list', 'table', 'figure')


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _validate_document(document: Mapping[str, Any]) -> tuple:
    """Requires a page with unambiguous dimensions and interpretation; does not guess units."""
    if not isinstance(document, Mapping) or not isinstance(document.get('regions'), list):
        raise ValueError('Se requiere un documento con regions como lista')
    for name in ('document_id', 'run_id'):
        if not isinstance(document.get(name), str) or not document[name].strip():
            raise ValueError(name + ' debe ser un identificador no vacío')
    if type(document.get('page')) is not int or document['page'] <= 0:
        raise ValueError('page debe ser un entero positivo desde 1')
    geometry = document.get('coordinate_system')
    if not isinstance(geometry, Mapping):
        raise ValueError('Falta la geometría coordinate_system del render')
    width, height = geometry.get('width_px'), geometry.get('height_px')
    for value in (width, height):
        if type(value) is not int or not _finite_number(value) or value <= 0:
            raise ValueError('Las dimensiones del render deben ser enteros positivos finitos')
    system = geometry.get('coordinate_system')
    if not isinstance(system, Mapping) or any(system.get(k) != v for k, v in
            [('unit', 'pixel'), ('origin', 'top-left'), ('bbox_format', 'xyxy')]):
        raise ValueError('Se requieren coordenadas XYXY en píxeles con origen superior izquierdo')
    return width, height


def _region_errors(region: Any, index: int, repeated_ids: set,
                   width: int, height: int, page: int) -> list:
    """Collects region errors without including non-JSON values in the report."""
    errors = []
    identifier = region.get('region_id') if isinstance(region, Mapping) else None
    identifier = identifier if isinstance(identifier, str) else None

    def add(code: str, detail: str) -> None:
        errors.append({'region_index': index, 'region_id': identifier, 'code': code, 'detail': detail})

    if not isinstance(region, Mapping):
        add('invalid_region', 'La región debe ser un objeto JSON')
        return errors
    if not identifier or not identifier.strip():
        add('invalid_region_id', 'region_id debe ser un string no vacío')
    elif identifier in repeated_ids:
        add('duplicate_region_id', 'El identificador aparece en más de una región')
    if 'page' in region and (type(region['page']) is not int or region['page'] != page):
        add('page_mismatch', 'La región declara una página distinta de la auditada')
    label = region.get('native_label')
    if not isinstance(label, str) or label not in NATIVE_CLASSES:
        add('unknown_class', 'native_label no pertenece a las cinco clases PubLayNet')
    else:
        class_id = region.get('class_id')
        if (region.get('type') != label or type(class_id) is not int
                or class_id != NATIVE_CLASSES.index(label)):
            add('class_mismatch', 'type, native_label y class_id no corresponden')
    score = region.get('score')
    if not _finite_number(score) or not 0 <= score <= 1:
        add('invalid_score', 'score debe ser finito y estar entre 0 y 1')
    box = region.get('bbox')
    if not isinstance(box, (list, tuple)) or len(box) != 4 or not all(_finite_number(x) for x in box):
        add('invalid_bbox', 'bbox debe contener cuatro números finitos XYXY')
    else:
        x1, y1, x2, y2 = box
        if x1 >= x2 or y1 >= y2 or not _finite_number((x2 - x1) * (y2 - y1)):
            add('invalid_bbox', 'bbox debe tener ancho, alto y área positivos finitos')
        elif (x2 - x1) * (y2 - y1) == 0:
            add('invalid_bbox', 'El área no puede reducirse a cero por precisión numérica')
        elif not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            add('out_of_bounds', 'bbox excede el render original')
    return errors


def _pair_alert(first: Mapping[str, Any], second: Mapping[str, Any], indices: tuple,
                iou_threshold: float, containment_threshold: float) -> Any:
    """Returns one alert per pair: similarity first, containment second."""
    a, b = first['bbox'], second['bbox']
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    if intersection <= 0:
        return None
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    # Scaling avoids overflow when summing areas of extreme numeric inputs.
    scale = max(area_a, area_b)
    iou = (intersection / scale) / (area_a / scale + area_b / scale - intersection / scale)
    inclusion = intersection / min(area_a, area_b)
    if iou >= iou_threshold:
        kind = 'possible_duplicate' if first['native_label'] == second['native_label'] else 'class_conflict'
    elif inclusion >= containment_threshold:
        kind = 'possible_containment'
    else:
        return None
    alert = {'kind': kind, 'region_indices': list(indices),
             'region_ids': [first['region_id'], second['region_id']],
             'classes': [first['native_label'], second['native_label']],
             'scores': [first['score'], second['score']], 'iou': iou,
             'intersection_over_smaller': inclusion,
             'first_coverage': intersection / area_a, 'second_coverage': intersection / area_b}
    if kind == 'possible_containment':
        inner, outer = (first, second) if area_a <= area_b else (second, first)
        alert.update(inner_region_id=inner['region_id'], outer_region_id=outer['region_id'])
    return alert


def audit_regions(regions_document: Mapping[str, Any], *, iou_threshold: float,
                  containment_threshold: float) -> Dict[str, Any]:
    """Audits a regions.json without reference, mutation, I/O or inference dependencies.

    Args:
        regions_document: Single-page document produced by save_regions.
        iou_threshold: Inclusive threshold (0,1] for duplication/class conflict.
        containment_threshold: Inclusive threshold (0,1] for intersection/smaller area.
    Returns:
        Serializable report with technical errors and pairwise alerts. quality_score
        is always None; an empty or alert-free output does not establish good quality.
    Raises:
        ValueError: Invalid thresholds or global schema; no reliable comparison frame.
    Notes:
        All regions are inspected, without score filtering. Regions with any
        technical error are excluded only from pairwise comparisons;
        their indices/errors are preserved and never deleted from the original document.
        A box is not compared with itself. Each unordered pair is visited once.
        A high-IoU pair is not counted again as nesting. Indices start at 0.
        O(N²) complexity, suitable for the current output limited to 100 detections.
    """
    for name, value in [('iou_threshold', iou_threshold), ('containment_threshold', containment_threshold)]:
        if not _finite_number(value) or not 0 < value <= 1:
            raise ValueError(name + ' debe estar en (0,1] y ser finito')
    width, height = _validate_document(regions_document)
    regions = regions_document['regions']
    counts = Counter(region['region_id'] for region in regions if isinstance(region, Mapping)
                     and isinstance(region.get('region_id'), str))
    repeated_ids = {identifier for identifier, count in counts.items() if count > 1}
    errors, eligible = [], []
    for index, region in enumerate(regions):
        found = _region_errors(region, index, repeated_ids, width, height, regions_document['page'])
        errors.extend(found)
        if not found:
            eligible.append((index, region))
    alerts = []
    for (index_a, first), (index_b, second) in combinations(eligible, 2):
        alert = _pair_alert(first, second, (index_a, index_b), iou_threshold, containment_threshold)
        if alert is not None:
            alerts.append(alert)
    alert_counts = {kind: sum(alert['kind'] == kind for alert in alerts)
                    for kind in ('possible_duplicate', 'class_conflict', 'possible_containment')}
    return {
        'schema_version': 1, 'scope': 'reference_free_audit',
        'document_id': regions_document['document_id'], 'run_id': regions_document['run_id'],
        'page': regions_document['page'], 'quality_score': None,
        'parameters': {'iou_threshold': iou_threshold, 'containment_threshold': containment_threshold,
                       'threshold_comparison': '>=', 'native_classes': list(NATIVE_CLASSES),
                       'score_filter': None},
        'summary': {'input_region_count': len(regions), 'valid_region_count': len(eligible),
                    'invalid_region_count': len(regions) - len(eligible),
                    'validation_error_count': len(errors),
                    'compared_pair_count': len(eligible) * (len(eligible) - 1) // 2,
                    'alert_count': len(alerts), 'alerts_by_kind': alert_counts,
                    'alerted_region_count': len({index for alert in alerts for index in alert['region_indices']})},
        'validation_errors': errors, 'alerts': alerts,
        'interpretation': 'Errores de formato son técnicos; alertas geométricas requieren revisión. '
                          'No estima precisión, recall ni exactitud. Sin alertas no significa sin errores.'}
