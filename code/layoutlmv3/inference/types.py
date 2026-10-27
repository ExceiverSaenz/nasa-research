"""NumPy data contracts independent of PyTorch/Detectron2.

Producers: render and detector; consumers: outputs and run_page. Python 3.9 syntax.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional, Tuple

import numpy as np
from numpy.typing import NDArray


def _positive_int(value: int, name: str) -> None:
    """Requires a positive int, excluding bool.

    Args:
        value: Value to validate.
        name: Name used in the diagnostic.
    Returns:
        None.
    Raises:
        ValueError: Non-int type or value <= 0.
    Notes:
        Does not modify the value.
    """
    if type(value) is not int or value <= 0:
        raise ValueError(name + ' must be a positive integer')


@dataclass(frozen=True, eq=False)
class RenderedPage:
    """RGB render with CropBox in PDF points and applied rotation.

    Attributes:
        pdf_path: Provenance path; existence is not checked here.
        page_number: Positive physical page starting at 1.
        dpi: Positive resolution in dots per inch.
        image: NumPy uint8 (height, width, 3), copied and marked read-only.
        crop_box_pt: Finite (x0, y0, x1, y1) with positive extent.
        rotation_deg: 0, 90, 180 or 270 degrees.
    Notes:
        Top-left render origin. Freezing the dataclass does not imply
        absolute immutability of any NumPy object. Doc-Refs: INF-003.
    """
    pdf_path: Path
    page_number: int
    dpi: int
    image: NDArray[np.uint8] = field(repr=False)
    crop_box_pt: Tuple[float, float, float, float]
    rotation_deg: int

    def __post_init__(self) -> None:
        """Validates image geometry/type and preserves a read-only copy.

        Returns:
            None.
        Raises:
            TypeError: image is not NumPy uint8.
            ValueError: Invalid dimensions, page, dpi, box or rotation.
        Notes:
            Normalizes pdf_path to Path; does not read the PDF.
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
        """Returns image width as an int, in pixels; no external effects."""
        return int(self.image.shape[1])

    @property
    def height_px(self) -> int:
        """Returns image height as an int, in pixels; no external effects."""
        return int(self.image.shape[0])


@dataclass(frozen=True, eq=False)
class Predictions:
    """Postprocessed detections in original-render coordinates.

    Attributes:
        boxes_xyxy: float32 (N, 4), finite boxes inside the image with positive area.
        class_ids: int64 (N,), valid class_names indices.
        scores: float32 (N,), finite values in [0, 1].
        class_names: Unique names; the collection cannot be empty.
        image_width_px: Positive width in pixels.
        image_height_px: Positive height in pixels.
    Notes:
        N may be zero. The three arrays are copied and marked read-only.
        Does not establish reading order or detection quality. Doc-Refs: INF-005.
    """
    boxes_xyxy: NDArray[np.float32] = field(repr=False)
    class_ids: NDArray[np.int64] = field(repr=False)
    scores: NDArray[np.float32] = field(repr=False)
    class_names: Tuple[str, ...]
    image_width_px: int
    image_height_px: int

    def __post_init__(self) -> None:
        """Validates array shapes, dtypes, ranges and alignment.

        Returns:
            None.
        Raises:
            TypeError: Arrays with unsupported types/dtypes.
            ValueError: Invalid shapes, sizes, names, boxes, IDs or scores.
        Notes:
            Copies boxes_xyxy, class_ids and scores and enables read-only.
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
        """Returns N as an int from scores; zero is a valid empty prediction."""
        return len(self.scores)


@dataclass(frozen=True)
class LoadReport:
    """Parameter name/shape diagnostics, not model quality diagnostics.

    Attributes:
        missing_keys: Missing expected keys.
        unexpected_keys: Unexpected found keys.
        shape_mismatches: Tuples (key, expected shape, found shape).
    Notes:
        The detector blocks loading if any collection is nonempty.
    """
    missing_keys: Tuple[str, ...] = ()
    unexpected_keys: Tuple[str, ...] = ()
    shape_mismatches: Tuple[Tuple[str, Tuple[int, ...], Tuple[int, ...]], ...] = ()

    @property
    def is_exact_match(self) -> bool:
        """Returns bool indicating no key/shape differences; does not compare values."""
        return not (self.missing_keys or self.unexpected_keys or self.shape_mismatches)


@dataclass(frozen=True)
class RunResult:
    """Coordinator terminal result, with time in seconds.

    Attributes:
        run_id: Run ID.
        status: completed or failed.
        stage: Last recorded stage; not a list validated by this dataclass.
        output_dir: Results directory.
        region_count: Nonnegative count; None if predict did not complete.
        elapsed_seconds: Finite nonnegative time.
        error: Required text for failed and absent for completed.
    Notes:
        completed allows zero regions and does not establish quality or real integration.
    """
    run_id: str
    status: Literal['completed', 'failed']
    stage: str
    output_dir: Path
    region_count: Optional[int]
    elapsed_seconds: float
    error: Optional[str] = None

    def __post_init__(self) -> None:
        """Validates status, time, count and error consistency.

        Returns:
            None.
        Raises:
            ValueError: A validated field violates its constraints.
        Notes:
            Does not verify file existence or directory contents.
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
        """Returns bool when status is completed; does not inspect files or quality."""
        return self.status == 'completed'
