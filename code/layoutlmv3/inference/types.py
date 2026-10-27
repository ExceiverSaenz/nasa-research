"""Contratos de datos NumPy independientes de PyTorch/Detectron2.

Productores: render y detector; consumidores: outputs y run_page. Python 3.9 syntax.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional, Tuple

import numpy as np
from numpy.typing import NDArray


def _positive_int(value: int, name: str) -> None:
    """Exige un int positivo, excluyendo bool.

    Args:
        value: Valor por validar.
        name: Nombre usado en el diagnóstico.
    Returns:
        None.
    Raises:
        ValueError: Tipo no int o valor <= 0.
    Notes:
        No modifica el valor.
    """
    if type(value) is not int or value <= 0:
        raise ValueError(name + ' must be a positive integer')


@dataclass(frozen=True, eq=False)
class RenderedPage:
    """Render RGB con CropBox en puntos PDF y rotación aplicada.

    Attributes:
        pdf_path: Ruta de procedencia; no se comprueba aquí que exista.
        page_number: Página física positiva desde 1.
        dpi: Resolución positiva en puntos por pulgada.
        image: NumPy uint8 (height, width, 3), copiado y marcado read-only.
        crop_box_pt: (x0, y0, x1, y1) finitos con extensión positiva.
        rotation_deg: 0, 90, 180 o 270 grados.
    Notes:
        Origen del render superior izquierdo. Congelar la dataclass no implica
        inmutabilidad absoluta de cualquier objeto NumPy. Doc-Refs: INF-003.
    """
    pdf_path: Path
    page_number: int
    dpi: int
    image: NDArray[np.uint8] = field(repr=False)
    crop_box_pt: Tuple[float, float, float, float]
    rotation_deg: int

    def __post_init__(self) -> None:
        """Valida geometría/tipo de imagen y conserva una copia read-only.

        Returns:
            None.
        Raises:
            TypeError: image no es NumPy uint8.
            ValueError: Dimensiones, página, dpi, caja o rotación inválidos.
        Notes:
            Normaliza pdf_path a Path; no lee el PDF.
        """
        for name in ('page_number', 'dpi'):
            _positive_int(getattr(self, name), name)
        if not isinstance(self.image, np.ndarray) or self.image.dtype != np.uint8:
            raise TypeError('image must be a uint8 NumPy array')
        if self.image.ndim != 3 or self.image.shape[2] != 3 or min(self.image.shape[:2]) <= 0:
            raise ValueError('image must have shape (height, width, 3)')
        if (len(self.crop_box_pt) != 4 or not np.isfinite(self.crop_box_pt).all()
                or self.crop_box_pt[0] >= self.crop_box_pt[2]
                or self.crop_box_pt[1] >= self.crop_box_pt[3]):
            raise ValueError('Invalid visible PDF box')
        if self.rotation_deg not in (0, 90, 180, 270):
            raise ValueError('Invalid PDF rotation')
        image = self.image.copy()
        image.setflags(write=False)
        object.__setattr__(self, 'image', image)
        object.__setattr__(self, 'pdf_path', Path(self.pdf_path))

    @property
    def width_px(self) -> int:
        """Devuelve el ancho de image como int, en píxeles; sin efectos externos."""
        return int(self.image.shape[1])

    @property
    def height_px(self) -> int:
        """Devuelve el alto de image como int, en píxeles; sin efectos externos."""
        return int(self.image.shape[0])


@dataclass(frozen=True, eq=False)
class Predictions:
    """Detecciones postprocessed en coordenadas del render original.

    Attributes:
        boxes_xyxy: float32 (N, 4), cajas finitas dentro de la imagen y área positiva.
        class_ids: int64 (N,), índices válidos de class_names.
        scores: float32 (N,), valores finitos en [0, 1].
        class_names: Nombres únicos; la colección no puede estar vacía.
        image_width_px: Ancho positivo en píxeles.
        image_height_px: Alto positivo en píxeles.
    Notes:
        N puede ser cero. Los tres arrays se copian y marcan read-only.
        No establece orden de lectura ni calidad de detección. Doc-Refs: INF-005.
    """
    boxes_xyxy: NDArray[np.float32] = field(repr=False)
    class_ids: NDArray[np.int64] = field(repr=False)
    scores: NDArray[np.float32] = field(repr=False)
    class_names: Tuple[str, ...]
    image_width_px: int
    image_height_px: int

    def __post_init__(self) -> None:
        """Valida shapes, dtypes, rangos y alineación de arrays.

        Returns:
            None.
        Raises:
            TypeError: Arrays con tipos/dtypes no admitidos.
            ValueError: Shapes, tamaños, nombres, cajas, IDs o scores inválidos.
        Notes:
            Copia boxes_xyxy, class_ids y scores y activa read-only.
        """
        _positive_int(self.image_width_px, 'image_width_px')
        _positive_int(self.image_height_px, 'image_height_px')
        for name, dtype in [('boxes_xyxy', np.float32), ('class_ids', np.int64), ('scores', np.float32)]:
            array = getattr(self, name)
            if not isinstance(array, np.ndarray) or array.dtype != dtype:
                raise TypeError(name + ' has an invalid array dtype')
        boxes, ids, scores = self.boxes_xyxy, self.class_ids, self.scores
        if boxes.ndim != 2 or boxes.shape[1] != 4:
            raise ValueError('boxes_xyxy must have shape (N, 4)')
        if ids.shape != (len(boxes),) or scores.shape != (len(boxes),):
            raise ValueError('Predictions must have aligned lengths')
        if not self.class_names or len(set(self.class_names)) != len(self.class_names):
            raise ValueError('Class names must be nonempty and unique')
        if not np.isfinite(boxes).all() or not np.isfinite(scores).all():
            raise ValueError('Nonfinite predictions')
        if ((ids < 0) | (ids >= len(self.class_names))).any() or ((scores < 0) | (scores > 1)).any():
            raise ValueError('Invalid class IDs or scores')
        if ((boxes[:, 0] < 0).any() or (boxes[:, 1] < 0).any()
                or (boxes[:, 2] > self.image_width_px).any()
                or (boxes[:, 3] > self.image_height_px).any()
                or (boxes[:, 0] >= boxes[:, 2]).any()
                or (boxes[:, 1] >= boxes[:, 3]).any()):
            raise ValueError('Invalid or out-of-bounds boxes')
        for name in ('boxes_xyxy', 'class_ids', 'scores'):
            array = getattr(self, name).copy()
            array.setflags(write=False)
            object.__setattr__(self, name, array)

    @property
    def count(self) -> int:
        """Devuelve N como int desde scores; cero es una predicción vacía válida."""
        return len(self.scores)


@dataclass(frozen=True)
class LoadReport:
    """Diagnóstico de nombres/shapes de parámetros, no de calidad del modelo.

    Attributes:
        missing_keys: Claves esperadas ausentes.
        unexpected_keys: Claves encontradas no esperadas.
        shape_mismatches: Tuplas (clave, shape esperado, shape encontrado).
    Notes:
        El detector bloquea la carga si alguna colección no está vacía.
    """
    missing_keys: Tuple[str, ...] = ()
    unexpected_keys: Tuple[str, ...] = ()
    shape_mismatches: Tuple[Tuple[str, Tuple[int, ...], Tuple[int, ...]], ...] = ()

    @property
    def is_exact_match(self) -> bool:
        """Devuelve bool si no hay diferencias de claves/shapes; no compara valores."""
        return not (self.missing_keys or self.unexpected_keys or self.shape_mismatches)


@dataclass(frozen=True)
class RunResult:
    """Resultado terminal del coordinador, con tiempo en segundos.

    Attributes:
        run_id: ID de ejecución.
        status: completed o failed.
        stage: Última etapa registrada; no es una lista validada por esta dataclass.
        output_dir: Directorio de resultados.
        region_count: Cantidad no negativa; None si predict no completó.
        elapsed_seconds: Tiempo finito no negativo.
        error: Texto obligatorio para failed y ausente para completed.
    Notes:
        completed admite cero regiones y no acredita calidad ni integración real.
    """
    run_id: str
    status: Literal['completed', 'failed']
    stage: str
    output_dir: Path
    region_count: Optional[int]
    elapsed_seconds: float
    error: Optional[str] = None

    def __post_init__(self) -> None:
        """Valida estado, tiempo, conteo y coherencia del error.

        Returns:
            None.
        Raises:
            ValueError: Algún campo validado incumple sus restricciones.
        Notes:
            No verifica existencia de archivos ni contenido del directorio.
        """
        if self.status not in ('completed', 'failed'):
            raise ValueError('Unknown run status')
        if not np.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError('Invalid elapsed time')
        if self.region_count is not None and (type(self.region_count) is not int or self.region_count < 0):
            raise ValueError('Invalid region count')
        if self.status == 'completed' and (self.region_count is None or self.error is not None):
            raise ValueError('Completed run requires detections count and no error')
        if self.status == 'failed' and not self.error:
            raise ValueError('Failed run requires an error')

    @property
    def succeeded(self) -> bool:
        """Devuelve bool cuando status es completed; no revisa archivos ni calidad."""
        return self.status == 'completed'
