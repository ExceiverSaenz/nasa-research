"""Coordinate the fixed image, saving native inference output before derivatives."""
import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import time
import traceback

from PIL import Image
from .outputs import export_regions, save_json

IMAGE_SHA256='6f46d8ff2d05eee785739ec1c34716db14135411c731e7aa6433e27ca06d00b9'


def parse_native(path):
    import torch
    from mineru.config import config
    from mineru.model.runtime.device import get_device, resolve_small_model_backend
    from mineru.parser import parse
    if (not torch.cuda.is_available() or 'T4' not in torch.cuda.get_device_name(0)
            or get_device()!='cuda' or resolve_small_model_backend()!='torch'
            or config.model.source!='local' or config.llm_aided.features.title_leveling
            or config.llm_aided.features.cross_page_table_cell_merge):
        raise RuntimeError('Expected local Basic/Torch/CUDA T4 with LLM features disabled')
    return parse(path,tier='basic',ocr_mode='ocr',image_analysis=True)


def run_image(image_path, output, parser=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    stage='input';started=time.perf_counter();error=None;timings={};count=None
    manifest={'scope':'SiC 12.pdf physical page3; same original PNG; no fusion',
              'tier':'basic','small_backend':'torch','device_requested':'cuda','ocr_mode':'ocr',
              'python':platform.python_version(), 'versions':{},
              'code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}}
    for name in ('mineru','docvortex','torch','torchvision','transformers','onnxruntime','Pillow'):
        try:manifest['versions'][name]=metadata.version(name)
        except metadata.PackageNotFoundError:manifest['versions'][name]=None
    try:
        digest=hashlib.sha256(Path(image_path).read_bytes()).hexdigest()
        manifest['input_sha256']=digest
        if digest!=IMAGE_SHA256:raise ValueError('Input differs from original render')
        with Image.open(image_path) as original:image=original.convert('RGB')
        if image.size!=(1654,2205):raise ValueError('Unexpected image dimensions')
        stage='parse';step=time.perf_counter()
        if parser is None:
            import torch
            from mineru.model.runtime.device import get_device, resolve_small_model_backend
            manifest['runtime']={'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                                 'cuda_runtime':torch.version.cuda,'resolved_device':get_device(),
                                 'resolved_small_backend':resolve_small_model_backend(),
                                 'table_device':'cpu',
                                 'internal_input_conversion':'MinerU converts PNG to PDF internally'}
        result=(parser or parse_native)(Path(image_path))
        timings['parse_seconds']=time.perf_counter()-step
        stage='native_json'
        document=result.middle_json.to_dict(skip_defaults=False)
        save_json(output/'middle-native.json',document)
        if result._model_output is not None:
            save_json(output/'model-native.json',result._model_output.to_dict(skip_defaults=False))
        stage='native_assets'
        # Native JSON already persisted even if materialization/Markdown fails.
        if parser is None:
            from mineru.parser.writer import FileBasedDataWriter
            result.save(FileBasedDataWriter(str(output/'native')))
        else: result.save(None)
        stage='export'
        converted=export_regions(image,document,output)
        count=len(converted['regions'])
    except Exception as exc:
        error=type(exc).__name__+': '+str(exc)
        (output/'error.log').write_text(traceback.format_exc(),encoding='utf-8')
    status={'status':'failed' if error else 'completed','stage':stage,'error':error,
            'region_count_including_children':count,'timings':timings,'elapsed_seconds':time.perf_counter()-started}
    save_json(output/'run-manifest.json',manifest)
    save_json(output/'page-status.json',status)
    return status


def main():
    parser=argparse.ArgumentParser(description='Fixed-image MinerU Basic/Torch diagnostic')
    parser.add_argument('--image',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();status=run_image(args.image,args.output)
    print(json.dumps(status,indent=2));return int(status['status']!='completed')


if __name__=='__main__':raise SystemExit(main())
