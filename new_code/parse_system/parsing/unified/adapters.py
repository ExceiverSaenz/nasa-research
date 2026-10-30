"""Persistent unified worker engines. All model loading occurs in spawned workers.

Runtime additionally requires mineru_config (a new YAML with local model source,
small_backend torch, base_dir parent of model_dirs.mineru and both LLM features
false). MinerU's existing completion markers must be present; no downloads,
marker repairs, services, engine fallback or baseline modifications occur here.
"""
import json
import math
import os
from pathlib import Path
import re
import sys
from .environment import check_runtime, sha256, verify_files
from .compatibility import prepare_vendor, verify_vendor

MODELS=('layoutlmv3','table_transformer','mineru')
MINERU_REVISION='2b3afb86f4d23fa623f6b2f4b2279ed4ef93a89d'
MINERU_HYBRID_SHA256='ac6b34a6584c668e7e6bba28be98722faf4acc443ff93ff788bfcb2fd9c2ce1a'


def validate_job(job):
    identity=job['identity']; path=Path(job['render_path'])
    if not isinstance(job['paper_id'],str) or not job['paper_id']: raise ValueError('Paper identity required')
    if type(job['page']) is not int or job['page']<1 or identity['physical_page']!=job['page']:
        raise ValueError('Page identity differs')
    for key in ('document_sha256','render_sha256'):
        if not isinstance(identity.get(key),str) or not re.fullmatch('[a-f0-9]{64}',identity[key]):
            raise ValueError('SHA256 identity required: '+key)
    if identity['dpi']!=200 or any(type(identity[k]) is not int or identity[k]<=0 for k in ('width_px','height_px')):
        raise ValueError('Expected positive 200 DPI render geometry')
    geometry=identity['geometry']; box=geometry['crop_box_pt']
    if (len(box)!=4 or not all(isinstance(v,(float,int)) and math.isfinite(v) for v in box)
            or box[2]<=box[0] or box[3]<=box[1] or geometry['rotation_deg'] not in (0,90,180,270)):
        raise ValueError('Invalid PDF geometry')
    if sha256(path)!=identity['render_sha256']: raise ValueError('Render hash changed')
    return path


def _save(path,value):
    with Path(path).open('x',encoding='utf-8') as stream: json.dump(value,stream,indent=2,allow_nan=False)


def _vendor(runtime):
    source=Path(runtime['vendor_dir']).resolve(strict=True)
    if (source/'unified-vendor.json').exists(): return verify_vendor(source)
    destination=Path(runtime['env_manifest']).resolve().parent/'vendor-unified'
    if not destination.exists(): prepare_vendor(source,destination)
    return verify_vendor(destination)


def _layout_detector(runtime):
    vendor=_vendor(runtime); root=vendor/'layoutlmv3'
    for name in ('layoutlmft','ditod'):
        module=sys.modules.get(name)
        if module is not None and not Path(module.__file__).resolve().is_relative_to(vendor):
            raise RuntimeError('Baseline vendor already imported: '+name)
    sys.path.insert(0,str(root))
    from parsing.adapters.layoutlmv3.inference.detector import LayoutLMv3Detector, compare_state_dicts
    class StrictUnifiedDetector(LayoutLMv3Detector):
        def _load_checkpoint(self,model):
            import torch
            checkpoint=torch.load(str(self._checkpoint_path),map_location='cpu',weights_only=False)
            if not isinstance(checkpoint,dict) or not isinstance(checkpoint.get('model'),dict):
                raise ValueError('Expected verified Detectron2 model dictionary')
            state=checkpoint['model']; self._load_report=compare_state_dicts(model.state_dict(),state)
            if not self._load_report.is_exact_match: raise ValueError('LayoutLM checkpoint keys/shapes differ')
            model.load_state_dict(state,strict=True)
            return self._load_report
    models=Path(runtime['model_dirs']['layoutlmv3'])
    detector=StrictUnifiedDetector(root/'examples/object_detection/cascade_layoutlmv3.yaml',
                                  models/'model_final.pth',models,device='cuda')
    detector.load()
    return detector


def _mineru_parser(runtime):
    config_path=Path(runtime['mineru_config']).resolve(strict=True)
    os.environ.update(MINERU_CONFIG=str(config_path),MINERU_DEVICE_MODE='cuda',MINERU_TABLE_DEVICE='cpu',
                      HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    from mineru.config import config
    from mineru.model.runtime.device import get_device,resolve_small_model_backend
    from mineru.model.registry import MINERU_4_MODELS_TORCH as repo
    from mineru.model.download import verify_model_repo
    if (get_device()!='cuda' or resolve_small_model_backend()!='torch'
            or config.model.source!='local' or config.model.small_backend!='torch'
            or os.environ.get('MINERU_TABLE_DEVICE')!='cpu'
            or config.llm_aided.features.title_leveling or config.llm_aided.features.cross_page_table_cell_merge):
        raise RuntimeError('Expected local Basic/Torch/CUDA, table CPU and disabled LLM features')
    model_root=Path(runtime['model_dirs']['mineru']).resolve(strict=True)
    if repo.local_dir().resolve()!=model_root: raise ValueError('MinerU config model root differs')
    receipt=json.loads(Path(runtime['mineru_receipt']).read_text(encoding='utf-8'))
    if receipt['model_id']!='opendatalab/MinerU-4_models_torch' or receipt['revision']!=MINERU_REVISION:
        raise ValueError('Unexpected MinerU snapshot identity')
    verify_files(model_root,receipt['files'])
    if not verify_model_repo(repo).ready: raise ValueError('MinerU local completion markers missing; no repair/download')
    from mineru.model.runtime import hybrid
    if sha256(hybrid.__file__)!=MINERU_HYBRID_SHA256: raise ValueError('MinerU4.0.12 preload source changed')
    # Same singleton/cache keys used by Basic parsing, all lazy models loaded
    # before READY. This is construction/weight loading, not a warmup inference.
    context=hybrid.HybridLocalModelContextSingleton().get_model()
    for name in ('mfr_model','wireless_table_model','wired_table_model','table_cls_model',
                 'table_orientation_cls_model','seal_model'):
        if getattr(context,name) is None: raise RuntimeError('MinerU model failed to preload: '+name)
    if context.small_backend!='torch' or context.device!='cuda': raise RuntimeError('MinerU context device differs')
    from mineru.parser import MinerUParser
    return MinerUParser(tier='basic',parse_mode='ocr',image_analysis=True),context


class Engine:
    def __init__(self,model,runtime):
        self.model=model; self.runtime=runtime; self.context=None
        self.fingerprint=check_runtime(Path(runtime['env_manifest']),require_cuda=True)
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        if model=='layoutlmv3': self.detector=_layout_detector(runtime)
        elif model=='table_transformer':
            from parsing.adapters.table_transformer.detector import TableTransformerDetector
            self.detector=TableTransformerDetector(runtime['model_dirs'][model]); self.detector.load()
        else: self.parser,self.context=_mineru_parser(runtime)

    def process(self,job,destination: Path):
        path=validate_job(job)
        from PIL import Image
        with Image.open(path) as source:
            if source.mode!='RGB' or source.size!=(job['identity']['width_px'],job['identity']['height_px']):
                raise ValueError('Image dimensions/mode differ from shared identity')
            image=source.copy()
        destination=Path(destination); destination.mkdir(parents=True,exist_ok=False)
        _save(destination/'identity.json',job['identity'])
        if self.model=='layoutlmv3':
            import numpy as np
            from parsing.adapters.layoutlmv3.inference.types import RenderedPage
            from parsing.adapters.layoutlmv3.inference.outputs import save_regions
            predictions=self.detector.predict(np.asarray(image))
            identity=job['identity']; geometry=identity['geometry']
            rendered=RenderedPage(Path(job.get('pdf_path',job['paper_id']+'.pdf')),job['page'],200,np.asarray(image),
                                  tuple(geometry['crop_box_pt']),geometry['rotation_deg'])
            save_regions(predictions,rendered,destination,document_id=identity['document_sha256'],
                         run_id=identity.get('execution_id',job['paper_id']+':'+str(job['page'])))
            _save(destination/'detector.json',self.detector.metadata())
        elif self.model=='table_transformer':
            raw,regions=self.detector.predict(image)
            _save(destination/'regions-raw.json',raw)
            _save(destination/'regions.json',{'regions':regions,'coordinate_system':job['identity']})
            _save(destination/'detector.json',self.detector.metadata())
        else:
            result=self.parser.parse(path)
            document=result.middle_json.to_dict(skip_defaults=False)
            _save(destination/'middle-native.json',document)
            if result._model_output is not None:
                _save(destination/'model-native.json',result._model_output.to_dict(skip_defaults=False))
            from parsing.adapters.mineru.outputs import convert_regions
            _save(destination/'regions.json',convert_regions(document,*image.size))
        return {'status':'completed','model':self.model,'identity':job['identity']}

    def close(self):
        self.context=None
        for name in ('detector','parser'):
            if hasattr(self,name): delattr(self,name)


def load_engine(model: str, runtime: dict):
    if model not in MODELS: raise ValueError('Unknown unified engine: '+str(model))
    return Engine(model,runtime)
