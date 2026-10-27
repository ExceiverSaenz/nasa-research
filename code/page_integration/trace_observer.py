"""Transparent observers. No model imports until the USER enters observe_mineru()."""
from contextlib import contextmanager
import functools
import hashlib
import importlib
from importlib import metadata
import inspect
import json
import math
from pathlib import Path
import sys

SOURCE_HASHES={
    'mineru/model/layout/pp_doclayoutv2.py':'b8ff66180f8efe1d481c01fc744fe7a622026416b75f158551acfb0c9a1c342b',
    'mineru/backend/analysis/pdf/ocr.py':'c25c4b88258e7b9774395598aa71227edda71b3baa84d883f6a7b8fa563195a6',
    'mineru/backend/analysis/pdf/normalization.py':'4a914e4c980ff01c7bf968e3f83e2bd272a7c00ed9888f5968cd6a09f3ac8323',
}
METHODS=('_preprocess_single_image','_post_process_object_detection','_parse_prediction',
    '_apply_paddlex_filter_boxes','_deduplicate_boxes_by_iou','_merge_nested_formula_boxes',
    '_relabel_formula_boxes','_filter_formula_boxes_inside_page_marginals',
    '_relabel_header_footer_boundary_blocks','_filter_internal_visual_caption_boxes','_apply_layout_post_process')
OCR_FUNCTIONS=('_collect_ocr_det_crops','_ocr_det','_normalize_batch_ocr_det_boxes',
               '_should_remove_low_confidence_ocr_text','_apply_ocr_rec_results')
POLICY=dict(version='1.0',mineru_version='4.0.12',source_sha256=SOURCE_HASHES,
    methods=list(METHODS),ocr_functions=list(OCR_FUNCTIONS),normalization='_normalize_pdf_model_list',
    wheel_sha256='a3ff8582a4608eb1f4dde55800ac156d59b01ceabd2ab4002bdf8e86306b1eab',
    semantics='observe_only_no_threshold_or_result_changes_no_extra_inference')


def snapshot(value,full_tensors=True):
    """Convert without mutating; keep raw scores, summarize image buffers only."""
    if type(value) is float and not math.isfinite(value):return dict(nonfinite=str(value))
    if value is None or type(value) in (bool,int,float,str):return value
    if hasattr(value,'pred_boxes') and hasattr(value,'logits'):
        return dict(pred_boxes=snapshot(value.pred_boxes),logits=snapshot(value.logits),
                    order_logits_shape=list(value.order_logits.shape) if getattr(value,'order_logits',None) is not None else None)
    if isinstance(value,(list,tuple)):return [snapshot(v,full_tensors) for v in value]
    if isinstance(value,dict):return {str(k):snapshot(v,full_tensors) for k,v in value.items()}
    if hasattr(value,'detach') and hasattr(value,'shape'):
        info=dict(kind='tensor',shape=list(value.shape),dtype=str(value.dtype),device=str(value.device))
        if full_tensors:info['values']=snapshot(value.detach().cpu().tolist())
        return info
    if type(value).__module__.startswith('numpy'):
        if hasattr(value,'shape') and hasattr(value,'tobytes'):
            info=dict(kind='ndarray',shape=list(value.shape),dtype=str(value.dtype),sha256=hashlib.sha256(value.tobytes()).hexdigest())
            if len(value.shape)<3 and value.size<=10000:info['values']=snapshot(value.tolist())
            return info
        if hasattr(value,'item'):return snapshot(value.item())
    if hasattr(value,'size') and hasattr(value,'mode') and hasattr(value,'tobytes'):
        return dict(kind='image',size=list(value.size),mode=value.mode,sha256=hashlib.sha256(value.tobytes()).hexdigest())
    if hasattr(value,'__dataclass_fields__'):
        return {name:snapshot(getattr(value,name),full_tensors) for name in value.__dataclass_fields__}
    return dict(kind=type(value).__module__+'.'+type(value).__qualname__,unsupported=True)


class TraceRecorder:
    def __init__(self,directory):
        self.directory=Path(directory);self.count=0;self.restorers=[];self.aliases=[];self.calls={};self.files=[]

    def __enter__(self):
        self.directory.mkdir(parents=True,exist_ok=False)
        return self

    def write(self,number,phase,event):
        path=self.directory/(str(number).zfill(5)+'-'+phase+'.json')
        with path.open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(event,stream,ensure_ascii=False,allow_nan=False);stream.write('\n')
        self.files.append(dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))

    def wrap(self,function,name,drop_owner=False):
        self.calls.setdefault(name,0)
        @functools.wraps(function)
        def observed(*args,**kwargs):
            self.count+=1;number=self.count;self.calls[name]+=1
            values=args[1:] if drop_owner else args
            before=dict(stage=name,args=snapshot(values),kwargs=snapshot(kwargs))
            if name.endswith('._post_process_object_detection') and args:
                before['class_thresholds']=snapshot(args[0].config.class_thresholds)
            self.write(number,'before',before)
            try:result=function(*args,**kwargs)
            except BaseException as exc:
                try:self.write(number,'error',dict(stage=name,error_type=type(exc).__name__,error=str(exc)))
                except Exception:pass  # Never replace the original exception.
                raise
            self.write(number,'after',dict(stage=name,result=snapshot(result,not name.endswith('._preprocess_single_image')),
                args_after=snapshot(values),kwargs_after=snapshot(kwargs)))
            return result
        return observed

    def hook_method(self,cls,name):
        owned=name in cls.__dict__;descriptor=inspect.getattr_static(cls,name)
        special=isinstance(descriptor,(classmethod,staticmethod))
        function=descriptor.__func__ if special else descriptor
        wrapped=self.wrap(function,cls.__name__+'.'+name,not isinstance(descriptor,staticmethod))
        replacement=type(descriptor)(wrapped) if special else wrapped
        setattr(cls,name,replacement)
        def restore():
            if owned:setattr(cls,name,descriptor)
            else:delattr(cls,name)
        self.restorers.append(restore)

    def hook_function(self,module,name):
        original=getattr(module,name);wrapped=self.wrap(original,module.__name__+'.'+name)
        prefix=module.__name__.split('.')[0]
        for n,m in tuple(sys.modules.items()):
            if m is not None and (n==prefix or n.startswith(prefix+'.')):
                for key,value in tuple(vars(m).items()):
                    if value is original:setattr(m,key,wrapped)
        self.aliases.append((prefix,original,wrapped))

    def __exit__(self,kind,error,tb):
        for prefix,original,wrapped in reversed(self.aliases):
            for n,m in tuple(sys.modules.items()):
                if m is not None and (n==prefix or n.startswith(prefix+'.')):
                    for key,value in tuple(vars(m).items()):
                        if value is wrapped:setattr(m,key,original)
        for restore in reversed(self.restorers):restore()
        summary=dict(status='failed' if error else 'completed',calls=self.calls,events=self.files,
            original_exception=type(error).__name__ if error else None,observers_restored=True,
            note='Zero calls means stage was not reached; no inference is invoked by observers.')
        with (self.directory/'summary.json').open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(summary,stream,indent=2);stream.write('\n')


@contextmanager
def observe_mineru(directory,policy):
    """Only called in user-run pinned worker, immediately around original parse_native."""
    if policy!=POLICY:raise ValueError('Unknown trace policy; no inference allowed')
    distribution=metadata.distribution('mineru')
    if distribution.version!='4.0.12':raise ValueError('Trace instrumentation requires original MinerU version')
    for name,expected in SOURCE_HASHES.items():
        path=Path(distribution.locate_file(name))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Incompatible observer source: '+name)
    layout=importlib.import_module('mineru.model.layout.pp_doclayoutv2')
    ocr=importlib.import_module('mineru.backend.analysis.pdf.ocr')
    normalization=importlib.import_module('mineru.backend.analysis.pdf.normalization')
    with TraceRecorder(directory) as trace:
        for name in METHODS:trace.hook_method(layout.PPDocLayoutV2LayoutModel,name)
        for name in OCR_FUNCTIONS:trace.hook_function(ocr,name)
        trace.hook_function(normalization,'_normalize_pdf_model_list')
        yield trace
