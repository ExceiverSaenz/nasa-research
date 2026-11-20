import json
import os
import subprocess
import time
from pathlib import Path
from ..contracts import sha256, write_json
from ..normalize import normalize


def project_middle(path,source):
    path=Path(path);data=json.loads(path.read_text(encoding='utf-8-sig'));detections=[]
    def visit(block,context,pointer,parent=None):
        if not isinstance(block,dict):return
        origin={**context,'original_ref':str(path)+'#'+pointer}
        detection=normalize(block,origin)
        detection['native_parent_ref']=str(path)+'#'+parent if parent else None
        detections.append(detection)
        if isinstance(block.get('content'),list):
            for i,child in enumerate(block['content']):visit(child,context,pointer+f'/content/{i}',pointer)
    for i,page in enumerate(data.get('pages',[])):
        context={**source,'page_idx':page['page_idx'],'width':1,'height':1,'coordinates':'normalized_top_left',
                 'rotation':0,'original_sha256':sha256(path)}
        for j,block in enumerate(page.get('blocks',[])):visit(block,context,f'/pages/{i}/blocks/{j}')
    return detections


def run_mineru(config,pdf,output):
    import torch
    if not torch.cuda.is_available():raise RuntimeError('CUDA required')
    if config['tier']=='standard' and config.get('engine')!='vllm':raise ValueError('vLLM required')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    os.environ['MINERU_MODEL_SMALL_BACKEND']='torch'
    os.environ['MINERU_MODEL_SOURCE']='local'
    os.environ['MINERU_DEVICE_MODE']='cuda'
    if config['tier']=='standard':os.environ['MINERU_MODEL_VLM_ENGINE']='vllm'
    # MinerU 4.0.12 exposes a module-level config; get_config belongs to newer revisions.
    from mineru.config import config as settings
    if settings.model.vlm.server_url:raise ValueError('Remote VLM configuration forbidden')
    if config['tier']=='standard':
        from mineru.model.vlm.selector import resolve_vlm_engine
        if resolve_vlm_engine()!='vllm':raise ValueError('Effective engine must be vllm')
    # Version-specific public SDK, checked by the remote smoke gate before the collection.
    from mineru.parser import parse
    start=time.perf_counter();result=parse(str(pdf),tier=config['tier']);torch.cuda.synchronize()
    elapsed=time.perf_counter()-start
    middle=output/'middle.json';middle.write_text(result.to_json(),encoding='utf-8')
    from mineru.parser.writer import FileBasedDataWriter
    result.save(FileBasedDataWriter(str(output/'native')))
    detections=project_middle(middle,dict(tool=config['id'],paper_sha256=sha256(pdf)))
    write_json(output/'normalized.json',detections)
    return dict(total_parse_export_excluded_s=elapsed,inference_s=None,load_s=None,
                page_indices=[p['page_idx'] for p in json.loads(middle.read_text())['pages']],
                unknown_timing_reason='Public SDK does not expose isolated inference timing',normalized=str(output/'normalized.json'))
