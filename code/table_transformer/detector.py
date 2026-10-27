"""HF adapter with deferred heavy imports and locally testable decoding."""
import hashlib
import json
from pathlib import Path

import numpy as np

MODEL_ID = 'microsoft/table-transformer-detection'
REVISION = '2357cbe2b5a5d1c03e54f32764f06058933b65ab'
IMAGE_SHA256 = '6f46d8ff2d05eee785739ec1c34716db14135411c731e7aa6433e27ca06d00b9'
CLASSES = ('table', 'table rotated')
ALLOWED_UNUSED_COUNTERS = frozenset(
    'model.backbone.conv_encoder.model.layer{}.0.downsample.1.num_batches_tracked'.format(layer)
    for layer in (2, 3, 4))


def validate_load_report(report):
    """Only the three observed FrozenBatchNorm training counters may be unused.

    Transformers v4.49.0 TableTransformerFrozenBatchNorm2d explicitly removes
    num_batches_tracked in _load_from_state_dict; forward uses only weight,
    bias, running_mean and running_var. Keep the original report unchanged.
    """
    if (any(report[key] for key in ('missing_keys', 'mismatched_keys', 'error_msgs'))
            or set(report['unexpected_keys']) - ALLOWED_UNUSED_COUNTERS):
        raise ValueError('Incompatible checkpoint; see load-report.json')


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def decode_queries(logits, boxes, width, height, threshold):
    """Decode DETR cxcywh to original PNG pixels, without clipping or NMS.

    The three logits are table/table rotated/no object. All queries remain in the
    raw output; only foreground argmax queries with score >= threshold are returned.
    """
    if (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
            or not np.isfinite(threshold) or not 0 <= threshold <= 1):
        raise ValueError('Invalid threshold')
    if any(type(value) is not int or value <= 0 for value in (width, height)):
        raise ValueError('Invalid original image dimensions')
    logits, boxes = np.asarray(logits, dtype=np.float64), np.asarray(boxes, dtype=np.float64)
    if (logits.ndim != 2 or logits.shape[1] != 3 or boxes.shape != (len(logits), 4)
            or not np.isfinite(logits).all() or not np.isfinite(boxes).all()
            or (boxes[:, 2:] <= 0).any()):
        raise ValueError('Invalid DETR queries')
    probabilities = np.exp(logits - logits.max(axis=1, keepdims=True))
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    regions = []
    for index, (probability, box) in enumerate(zip(probabilities, boxes)):
        label = int(probability.argmax())
        score = float(probability[label])
        if label == 2 or score < threshold:
            continue
        cx, cy, w, h = box
        bbox = [(cx-w/2)*width, (cy-h/2)*height, (cx+w/2)*width, (cy+h/2)*height]
        regions.append({'query_id': index, 'native_label': CLASSES[label], 'class_id': label,
                        'score': score, 'bbox': bbox})
    return regions


class TableTransformerDetector:
    """Load one verified safetensors checkpoint; never download additional backbone weights."""
    def __init__(self, model_dir, device='cuda', threshold=.5):
        self.model_dir = Path(model_dir)
        self.device, self.threshold = device, threshold
        self.load_report = None
        self._model = self._processor = None
        self._input_shape = None
        self._gpu_name = self._cuda_version = None

    def load(self):
        if self._model is not None:
            return self.load_report
        manifest = json.loads((self.model_dir/'download-manifest.json').read_text())
        if manifest['model_id'] != MODEL_ID or manifest['revision'] != REVISION:
            raise ValueError('Unexpected model identity')
        for name in ('config.json', 'preprocessor_config.json', 'model.safetensors'):
            expected = manifest['files'][name]
            path = self.model_dir/name
            if path.stat().st_size != expected['bytes'] or file_sha256(path) != expected['sha256']:
                raise ValueError('Model file mismatch: '+name)
        import torch
        from transformers import DetrImageProcessor, TableTransformerConfig, TableTransformerForObjectDetection
        if self.device != 'cuda' or not torch.cuda.is_available():
            raise RuntimeError('This approved trial requires CUDA')
        self._gpu_name = torch.cuda.get_device_name(0)
        self._cuda_version = torch.version.cuda
        cfg = TableTransformerConfig.from_pretrained(self.model_dir, local_files_only=True)
        if tuple(cfg.id2label[i] for i in range(2)) != CLASSES:
            raise ValueError('Unexpected detector classes')
        cfg.use_pretrained_backbone = False
        processor = DetrImageProcessor.from_pretrained(self.model_dir, local_files_only=True)
        if processor.size != {'shortest_edge': 800, 'longest_edge': 800}:
            raise ValueError('Expected checkpoint preprocessing with maximum side 800')
        model, info = TableTransformerForObjectDetection.from_pretrained(
            self.model_dir, config=cfg, local_files_only=True, use_safetensors=True,
            output_loading_info=True)
        self.load_report = {key: info.get(key, []) for key in
                            ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')}
        validate_load_report(self.load_report)
        model.eval().to(self.device)
        self._model, self._processor = model, processor
        return self.load_report

    def predict(self, image):
        if self._model is None:
            raise RuntimeError('Load the model before predict')
        import torch
        inputs = self._processor(images=image, return_tensors='pt').to(self.device)
        self._input_shape = list(inputs['pixel_values'].shape)
        if max(self._input_shape[-2:]) > 800:
            raise ValueError('Processor exceeded max side 800')
        with torch.inference_mode():
            result = self._model(**inputs)
        logits = result.logits[0].cpu().numpy()
        boxes = result.pred_boxes[0].cpu().numpy()
        raw = {'logits': logits.tolist(), 'boxes_cxcywh_normalized': boxes.tolist(),
               'logit_classes': list(CLASSES)+['no object'], 'stage': 'all_decoder_queries_before_threshold'}
        return raw, decode_queries(logits, boxes, *image.size, self.threshold)

    def metadata(self):
        return {'model_id': MODEL_ID, 'revision': REVISION, 'device': self.device,
                'gpu_name': self._gpu_name, 'cuda_runtime': self._cuda_version,
                'threshold': self.threshold, 'threshold_comparison': '>=', 'classes': list(CLASSES),
                'input_tensor_shape': self._input_shape,
                'processor': self._processor.to_dict() if self._processor else None,
                'model_manifest': json.loads((self.model_dir/'download-manifest.json').read_text()),
                'use_pretrained_backbone': False}
