"""Adaptador LayoutLMv3/Detectron2 con imports pesados diferidos a load/predict.

Consume types.LoadReport y Predictions; run_page coordina carga y predicción.
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
    """Compara nombres y shapes de parámetros sin importar PyTorch.

    Args:
        expected: Mapping de parámetros esperados con atributo shape.
        found: Mapping de parámetros encontrados con atributo shape.
    Returns:
        LoadReport con claves faltantes, inesperadas y shapes incompatibles.
    Raises:
        AttributeError: Un valor comparado carece de shape.
    Notes:
        No carga pesos, no compara valores/dtypes ni modifica los mappings.
    """
    common = sorted(set(expected) & set(found))
    shapes = tuple((key, tuple(expected[key].shape), tuple(found[key].shape))
                   for key in common if tuple(expected[key].shape) != tuple(found[key].shape))
    return LoadReport(tuple(sorted(set(expected) - set(found))),
                      tuple(sorted(set(found) - set(expected))), shapes)


def file_sha256(path: Path) -> str:
    """Calcula SHA-256 leyendo bloques de 4 MiB.

    Args:
        path: Archivo local legible.
    Returns:
        Digest hexadecimal str.
    Raises:
        OSError: Fallo al abrir o leer el archivo.
    Notes:
        Solo lectura; no valida la procedencia del archivo.
    """
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class LayoutLMv3Detector:
    """Mantiene configuración, modelo evaluado y diagnóstico de carga.

    La construcción valida rutas; load verifica archivos y carga pesos. predict
    requiere carga exitosa. No renderiza PDFs ni escribe resultados de ejecución.
    El consumidor principal es run_page.run_page. Doc-Refs: INF-004, INF-008.
    """

    def __init__(self, config_path: Path, checkpoint_path: Path,
                 model_config_dir: Path, device: str = 'cuda') -> None:
        """Inicializa rutas locales y estado, sin construir el modelo.

        Args:
            config_path: Archivo YAML cascade junto al paquete ditod.
            checkpoint_path: Archivo del checkpoint local.
            model_config_dir: Directorio local de config.json y download-manifest.json.
            device: cuda o cpu; default cuda.
        Returns:
            None.
        Raises:
            OSError: Ruta inexistente o inaccesible.
            ValueError: Tipo de ruta o device no admitido.
        Notes:
            Guarda rutas absolutas y estado interno; no carga pesos.
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
        """Indica si el modelo fue asignado tras una carga exitosa.

        Returns:
            bool; no comprueba disponibilidad futura del device ni escribe archivos.
        """
        return self._model is not None

    @property
    def load_report(self) -> Optional[LoadReport]:
        """Devuelve el último diagnóstico de compatibilidad o None.

        Returns:
            LoadReport opcional; no implica por sí solo una carga exitosa.
        """
        return self._load_report

    def _build_config(self) -> Any:
        # config_path is the vendored cascade YAML alongside ditod/.
        """Construye y congela la configuración efectiva.

        Returns:
            Config de Detectron2 con rutas locales y device seleccionado.
        Raises:
            ValueError: Entrada distinta de 800/1333, no image-only, clases != 5 o no RGB.
            Exception: Fallos de imports o lectura/merge del YAML se propagan.
        Notes:
            Inserta el directorio del YAML al inicio de sys.path y no lo restaura.
            No descarga explícitamente archivos. Doc-Refs: INF-008.
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
        """Compara y carga un state_dict estrictamente.

        Args:
            model: Modelo construido con state_dict y load_state_dict.
        Returns:
            LoadReport compatible tras load_state_dict(strict=True).
        Raises:
            ValueError: Estructura del checkpoint o compatibilidad inválida.
            Exception: Fallos de torch.load o load_state_dict se propagan.
        Notes:
            Deserializa el checkpoint confiable con torch.load(map_location='cpu');
            actualiza load_report y los parámetros del modelo. No escribe load-report.json:
            esa escritura pertenece al coordinador.
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
        """Verifica identidad, tamaño/hash y carga el detector en modo eval.

        Returns:
            LoadReport; si ya está cargado, devuelve el informe almacenado.
        Raises:
            ValueError: Identidad, tamaño/hash, configuración o parámetros incompatibles.
            RuntimeError: CUDA solicitada pero no disponible.
            Exception: Fallos de archivos, JSON, imports o construcción se propagan.
        Notes:
            Lee manifest/config/pesos, modifica sys.path al configurar y asigna estado
            interno. Solo publica el modelo después de cargarlo y llamar eval.
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
        """Predice cajas postprocessed en dimensiones del render original.

        Args:
            image: RGB uint8 no vacío con shape (height, width, 3).
        Returns:
            Predictions con arrays CPU, cajas XYXY en píxeles y origen superior izquierdo.
        Raises:
            RuntimeError: No se completó load.
            ValueError: Imagen inválida o predicciones que violan sus contratos.
            Exception: Fallos de PyTorch/Detectron2 se propagan.
        Notes:
            Redimensiona con 800/1333, usa no_grad y entrega height/width originales al
            modelo. Actualiza el último tamaño de entrada; no aplica una segunda escala
            ni escribe archivos. Integración real no acreditada aquí. Doc-Refs: INF-004, INF-005.
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
        """Recupera configuración y procedencia para el manifest.

        Returns:
            dict con hashes, identidad, configuración efectiva y último tamaño de entrada.
        Raises:
            Exception: Lectura, hashing, JSON o serialización de config pueden fallar.
        Notes:
            Lee YAML, manifest y fuentes Python bajo vendor_root; no escribe archivos.
            Antes de load algunos campos son None.
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
