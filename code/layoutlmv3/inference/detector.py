"""LayoutLMv3/Detectron2 adapter with heavy imports deferred to load/predict.

Consumes types.LoadReport and Predictions; run_page coordinates loading and prediction.
"""
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Optional

import numpy as np
from numpy.typing import NDArray

from .types import LoadReport, Predictions

CLASS_NAMES = ('text', 'title', 'list', 'table', 'figure')


def compare_state_dicts(expected: Mapping[str, Any], found: Mapping[str, Any]) -> LoadReport:
    """Compares parameter names and shapes without importing PyTorch.

    Args:
        expected: Mapping of expected parameters with a shape attribute.
        found: Mapping of found parameters with a shape attribute.
    Returns:
        LoadReport with missing and unexpected keys and incompatible shapes.
    Raises:
        AttributeError: A compared value lacks shape.
    Notes:
        Does not load weights, compare values/dtypes or modify mappings.
    """
    common = sorted(set(expected) & set(found))
    shapes = tuple((key, tuple(expected[key].shape), tuple(found[key].shape))
                   for key in common if tuple(expected[key].shape) != tuple(found[key].shape))
    return LoadReport(tuple(sorted(set(expected) - set(found))),
                      tuple(sorted(set(found) - set(expected))), shapes)


def file_sha256(path: Path) -> str:
    """Computes SHA-256 by reading 4 MiB blocks.

    Args:
        path: Readable local file.
    Returns:
        Hexadecimal digest str.
    Raises:
        OSError: File open or read failure.
    Notes:
        Read-only; does not validate file provenance.
    """
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class LayoutLMv3Detector:
    """Maintains configuration, evaluated model and loading diagnostics.

    Construction validates paths; load verifies files and loads weights. predict
    requires successful loading. Does not render PDFs or write run results.
    The main consumer is run_page.run_page. Doc-Refs: INF-004, INF-008.
    """

    def __init__(self, config_path: Path, checkpoint_path: Path,
                 model_config_dir: Path, device: str = 'cuda') -> None:
        """Initializes local paths and state, without building the model.

        Args:
            config_path: Cascade YAML file beside the ditod package.
            checkpoint_path: Local checkpoint file.
            model_config_dir: Local directory for config.json and download-manifest.json.
            device: cuda or cpu; default cuda.
        Returns:
            None.
        Raises:
            OSError: Missing or inaccessible path.
            ValueError: Unsupported path type or device.
        Notes:
            Saves absolute paths and internal state; does not load weights.
        """
        self._config_path = Path(config_path).resolve(strict=True)
        self._checkpoint_path = Path(checkpoint_path).resolve(strict=True)
        self._model_config_dir = Path(model_config_dir).resolve(strict=True)
        if not self._config_path.is_file() or not self._checkpoint_path.is_file():
            raise ValueError('Configuration and checkpoint must be files')
        if not self._model_config_dir.is_dir():
            raise ValueError('model_config_dir must be a directory')
        if device not in ('cuda', 'cpu'):
            raise ValueError('device must be cuda or cpu')
        self._device = device
        self._model: Any = None
        self._cfg: Any = None
        self._load_report: Optional[LoadReport] = None
        self._checkpoint_hash: Optional[str] = None
        self._last_input_size: Optional[tuple] = None

    @property
    def is_loaded(self) -> bool:
        """Indicates whether the model was assigned after successful loading.

        Returns:
            bool; does not check future device availability or write files.
        """
        return self._model is not None

    @property
    def load_report(self) -> Optional[LoadReport]:
        """Returns the latest compatibility diagnostics or None.

        Returns:
            Optional LoadReport; does not by itself imply successful loading.
        """
        return self._load_report

    def _build_config(self) -> Any:
        # config_path is the vendored cascade YAML alongside ditod/.
        """Builds and freezes the effective configuration.

        Returns:
            Detectron2 config with local paths and selected device.
        Raises:
            ValueError: Input other than 800/1333, not image-only, classes != 5 or not RGB.
            Exception: Import or YAML read/merge failures propagate.
        Notes:
            Inserts the YAML directory at the start of sys.path and does not restore it.
            Does not explicitly download files. Doc-Refs: INF-008.
        """
        sys.path.insert(0, str(self._config_path.parent))
        from ditod import add_vit_config
        from detectron2.config import get_cfg
        cfg = get_cfg()
        add_vit_config(cfg)
        cfg.merge_from_file(str(self._config_path))
        cfg.MODEL.CONFIG_PATH = str(self._model_config_dir)
        cfg.MODEL.WEIGHTS = str(self._checkpoint_path)
        cfg.MODEL.DEVICE = self._device
        if cfg.INPUT.MIN_SIZE_TEST != 800 or cfg.INPUT.MAX_SIZE_TEST != 1333:
            raise ValueError('First trial requires input MIN_SIZE_TEST=800, MAX_SIZE_TEST=1333')
        if not cfg.MODEL.IMAGE_ONLY or cfg.MODEL.ROI_HEADS.NUM_CLASSES != len(CLASS_NAMES):
            raise ValueError('Expected image-only, five-class PubLayNet detector')
        if cfg.INPUT.FORMAT != 'RGB':
            raise ValueError('Expected RGB detector configuration')
        cfg.freeze()
        return cfg

    def _load_checkpoint(self, model: Any) -> LoadReport:
        """Strictly compares and loads a state_dict.

        Args:
            model: Constructed model with state_dict and load_state_dict.
        Returns:
            Compatible LoadReport after load_state_dict(strict=True).
        Raises:
            ValueError: Invalid checkpoint structure or compatibility.
            Exception: torch.load or load_state_dict failures propagate.
        Notes:
            Deserializes the trusted checkpoint with torch.load(map_location='cpu');
            updates load_report and model parameters. Does not write load-report.json:
            that write belongs to the coordinator.
        """
        import torch
        # Only the locally verified, trusted checkpoint is loaded. No torch hub.
        checkpoint = torch.load(str(self._checkpoint_path), map_location='cpu')
        if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get('model'), dict):
            raise ValueError('Expected Detectron2 checkpoint with a model state dictionary')
        state = checkpoint['model']
        self._load_report = compare_state_dicts(model.state_dict(), state)
        if not self._load_report.is_exact_match:
            raise ValueError('Checkpoint incompatible; see load-report.json')
        model.load_state_dict(state, strict=True)
        return self._load_report

    def load(self) -> LoadReport:
        """Verifies identity, size/hash and loads the detector in eval mode.

        Returns:
            LoadReport; if already loaded, returns the stored report.
        Raises:
            ValueError: Incompatible identity, size/hash, configuration or parameters.
            RuntimeError: CUDA requested but unavailable.
            Exception: File, JSON, import or construction failures propagate.
        Notes:
            Reads manifest/config/weights, modifies sys.path when configuring and assigns
            internal state. Publishes the model only after loading it and calling eval.
            Doc-Refs: INF-004.
        """
        if self.is_loaded:
            return self._load_report
        manifest = json.loads((self._model_config_dir / 'download-manifest.json').read_text())
        if (manifest['repository'] != 'HYPJUDY/layoutlmv3-base-finetuned-publaynet'
                or manifest['revision'] != '1c4d2cf657feafac1f53b6f92afe23b279d4f45b'):
            raise ValueError('Unexpected checkpoint identity')
        for name in ('config.json', 'model_final.pth'):
            path = self._checkpoint_path if name == 'model_final.pth' else self._model_config_dir / name
            expected = manifest['files'][name]
            digest = file_sha256(path)
            if path.stat().st_size != expected['bytes'] or digest != expected['sha256']:
                raise ValueError('Local model file does not match manifest: ' + name)
            if name == 'model_final.pth':
                self._checkpoint_hash = digest
        import torch
        if self._device == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA is unavailable')
        self._cfg = self._build_config()
        from detectron2.modeling import build_model
        model = build_model(self._cfg)
        self._load_checkpoint(model)
        model.eval()
        self._model = model
        return self._load_report

    def predict(self, image: NDArray[np.uint8]) -> Predictions:
        """Predicts postprocessed boxes in original-render dimensions.

        Args:
            image: Nonempty RGB uint8 with shape (height, width, 3).
        Returns:
            Predictions with CPU arrays, XYXY pixel boxes and top-left origin.
        Raises:
            RuntimeError: load did not complete.
            ValueError: Invalid image or predictions violating their contracts.
            Exception: PyTorch/Detectron2 failures propagate.
        Notes:
            Resizes with 800/1333, uses no_grad and passes original height/width to the
            model. Updates the latest input size; does not apply a second scale
            or write files. Real integration not established here. Doc-Refs: INF-004, INF-005.
        """
        if not self.is_loaded:
            raise RuntimeError('Call load successfully before predict')
        if (not isinstance(image, np.ndarray) or image.dtype != np.uint8
                or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) <= 0):
            raise ValueError('Expected nonempty RGB uint8 image')
        import torch
        from detectron2.data.transforms import ResizeShortestEdge
        height, width = image.shape[:2]
        resize = ResizeShortestEdge([self._cfg.INPUT.MIN_SIZE_TEST] * 2, self._cfg.INPUT.MAX_SIZE_TEST)
        resized = resize.get_transform(image).apply_image(image)
        self._last_input_size = (int(resized.shape[1]), int(resized.shape[0]))
        tensor = torch.as_tensor(np.ascontiguousarray(resized.astype('float32').transpose(2, 0, 1)))
        with torch.no_grad():
            instances = self._model([{'image': tensor, 'height': height, 'width': width}])[0]['instances'].to('cpu')
        return Predictions(instances.pred_boxes.tensor.numpy().astype(np.float32),
                           instances.pred_classes.numpy().astype(np.int64),
                           instances.scores.numpy().astype(np.float32), CLASS_NAMES, width, height)

    def metadata(self) -> dict:
        """Retrieves configuration and provenance for the manifest.

        Returns:
            dict with hashes, identity, effective configuration and latest input size.
        Raises:
            Exception: Reading, hashing, JSON or config serialization may fail.
        Notes:
            Reads YAML, manifest and Python sources under vendor_root; writes no files.
            Some fields are None before load.
        """
        cfg = self._cfg
        vendor_root = self._config_path.parent.parent.parent
        return {
            'device': self._device, 'class_names': CLASS_NAMES,
            'checkpoint_path': str(self._checkpoint_path), 'checkpoint_sha256': self._checkpoint_hash,
            'config_path': str(self._config_path), 'config_sha256': file_sha256(self._config_path),
            'model_manifest': json.loads((self._model_config_dir / 'download-manifest.json').read_text()),
            'vendor_source_sha256': {p.relative_to(vendor_root).as_posix(): file_sha256(p)
                                     for p in sorted(vendor_root.rglob('*.py'))},
            'effective_config_yaml': cfg.dump() if cfg is not None else None,
            'input': {'min_size_test': cfg.INPUT.MIN_SIZE_TEST if cfg else None,
                      'max_size_test': cfg.INPUT.MAX_SIZE_TEST if cfg else None,
                      'format': 'RGB', 'resized_width_height': self._last_input_size},
            'box_postprocessing': 'Detectron2 restores boxes to original render dimensions',
            'score_threshold': cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST if cfg else None,
            'max_detections': cfg.TEST.DETECTIONS_PER_IMAGE if cfg else None,
        }
