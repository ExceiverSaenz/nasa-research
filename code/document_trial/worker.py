"""USER ONLY: subprocess worker in each original environment. Import is inert."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import traceback
from .common import DOCUMENT,PAGE3,canonical,check_runtime,read,save,sha
from .inventory import clean_inventory, collect, package_map


def validate_document_plan(plan,pdf):
    count=plan.get('page_count')
    if type(count) is not int or count<1 or plan.get('physical_pages')!=list(range(1,count+1)) or plan.get('dpi')!=200:
        raise ValueError('Invalid page range or original DPI')
    digest=plan.get('document_sha256','')
    if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest) or sha(pdf)!=digest:
        raise ValueError('Document changed')
    regression_render_check(plan,0,None)


def regression_render_check(plan,page,render_hash):
    regression=plan.get('regression')
    if plan['document_sha256']==DOCUMENT:
        if not isinstance(regression,dict) or regression.get('page')!=3 or regression.get('render_sha256')!=PAGE3:
            raise ValueError('Original document requires its page3 regression')
        if page==3 and render_hash!=PAGE3:raise ValueError('Page3 render regression failed; no model inference started')
    elif regression is not None:
        raise ValueError('Historical regression cannot be transferred to another document')

def probe(model,inputs,state,stage="preflight"):
    spec=read(inputs/'plan.json')['models'][model]
    clean=clean_inventory(state,model,stage)
    packages=package_map(clean)
    import torch
    # Diagnostic only: retain vendor entries exposed by Torch without overwriting
    # or conflating them with the separately collected installed inventory.
    save(state/('inventory-'+model+'-'+stage+'-after-torch.json'),collect())
    observed=dict(stage=stage,python=platform.python_version(),packages=packages,
        inventory_clean='inventory-'+model+'-'+stage+'-clean.json',
        inventory_after_torch='inventory-'+model+'-'+stage+'-after-torch.json',
        gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,cuda=torch.version.cuda)
    save(state/('runtime-'+model+'-'+stage+'.json'),observed);check_runtime(observed,spec)
    if model=='mineru':
        from mineru.config import config
        from mineru.model.runtime.device import get_device,resolve_small_model_backend
        observed.update(device=get_device(),backend=resolve_small_model_backend(),table_device=os.environ.get('MINERU_TABLE_DEVICE'),
            config_sha256=sha(state/'config.yaml'),original_config_sha256=sha(inputs/'mineru/config.yaml'))
        save(state/('runtime-'+model+'-'+stage+'.json'),observed)
        if (observed['device']!='cuda' or observed['backend']!='torch' or observed['table_device']!='cpu'
            or observed['config_sha256']!=observed['original_config_sha256'] or config.model.source!='local'
            or config.llm_aided.features.title_leveling or config.llm_aided.features.cross_page_table_cell_merge):
            raise ValueError('INCOMPATIBLE original MinerU configuration; no inference')
    return observed

def render(inputs,state):
    from inference.render import render_page
    from inference.outputs import render_geometry
    from PIL import Image
    plan=read(inputs/'plan.json')
    validate_document_plan(plan,inputs/'document.pdf')
    for page in plan['physical_pages']:
        destination=state/'pages'/('%04d'%page);destination.mkdir(parents=True,exist_ok=False)
        rendered=render_page(inputs/'document.pdf',page,plan['dpi'])
        Image.fromarray(rendered.image).save(destination/'render.png',dpi=(plan['dpi'],plan['dpi']))
        identity=dict(document_sha256=plan['document_sha256'],physical_page=page,render_sha256=sha(destination/'render.png'),
            width_px=rendered.width_px,height_px=rendered.height_px,dpi=plan['dpi'],geometry=render_geometry(rendered),
            execution_id=read(state/'execution.json')['execution_id'])
        save(destination/'identity.json',identity)
        regression_render_check(plan,page,identity['render_sha256'])

def infer(model,inputs,state):
    from PIL import Image
    plan=read(inputs/'plan.json');validate_document_plan(plan,inputs/'document.pdf')
    probe(model,inputs,state,stage='before-infer')
    if model=='layoutlmv3':
        from inference.detector import LayoutLMv3Detector
        detector=LayoutLMv3Detector('/content/nasa-layoutlm/layoutlmv3/examples/object_detection/cascade_layoutlmv3.yaml',
            state/'models/layoutlmv3/model_final.pth',state/'models/layoutlmv3')
        detector.load()
    elif model=='table_transformer':
        from table_transformer.detector import TableTransformerDetector,validate_load_report
        detector=TableTransformerDetector(state/'models/table_transformer')
        validate_load_report(detector.load())
    else:
        from mineru_probe.remote_job import activate_verified_models
        from mineru_probe.run_image import parse_native
        activate_verified_models(inputs/'mineru/model-download-receipt.json')
    errors=[]
    for page in plan['physical_pages']:
        folder=state/'pages'/('%04d'%page);dest=folder/model
        dest.mkdir(exist_ok=False);status=dict(status='failed',page=page,model=model,error=None,inference_calls=0)
        try:
            identity=read(folder/'identity.json')
            if identity['document_sha256']!=plan['document_sha256'] or identity['physical_page']!=page:
                raise ValueError('Page identity differs from plan')
            if sha(folder/'render.png')!=identity['render_sha256']:raise ValueError('Render changed')
            with Image.open(folder/'render.png') as source:image=source.convert('RGB')
            status['inference_calls']=1
            if model=='mineru':
                result=parse_native(folder/'render.png')
                save(dest/'middle-native.json',result.middle_json.to_dict(skip_defaults=False))
                if result._model_output is not None:save(dest/'model-native.json',result._model_output.to_dict(skip_defaults=False))
                from mineru.parser.writer import FileBasedDataWriter
                result.save(FileBasedDataWriter(str(dest/'native')))
                from mineru_probe.outputs import export_regions
                export_regions(image,read(dest/'middle-native.json'),dest)
            elif model=='table_transformer':
                raw,regions=detector.predict(image)
                save(dest/'regions-raw.json',raw)
                # Preserve native bbox/score/query IDs before any derived drawing.
                save(dest/'regions.json',dict(regions=regions,coordinate_system=identity))
                save(dest/'detector.json',detector.metadata())
            else:
                import numpy as np
                predictions=detector.predict(np.asarray(image))
                from inference.types import RenderedPage
                from inference.outputs import save_regions,save_overlay
                rendered=RenderedPage(inputs/'document.pdf',page,plan['dpi'],np.asarray(image),
                    tuple(identity['geometry']['crop_box_pt']),identity['geometry']['rotation_deg'])
                save_regions(predictions,rendered,dest,document_id=plan['document_sha256'],run_id=identity['execution_id'])
                save_overlay(predictions,rendered,dest);save(dest/'detector.json',detector.metadata())
            status['status']='completed'
        except Exception:
            status['error']=traceback.format_exc();errors.append(page)
        finally:save(dest/'status.json',status)
    if errors:raise RuntimeError('Failed pages without retry: '+str(errors))

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--stage',choices=['probe','render','infer'],required=True)
    p.add_argument('--inputs',type=Path,required=True);p.add_argument('--state',type=Path,required=True);a=p.parse_args()
    if platform.system()!='Linux' or not Path('/content').is_dir() or os.environ.get('NASA_DOCUMENT_USER_RUN')!='COLAB_CLI_T4':
        raise RuntimeError('User Colab CLI execution only; local inference forbidden')
    if a.stage=='probe':probe(a.model,a.inputs,a.state)
    elif a.stage=='render':render(a.inputs,a.state)
    else:infer(a.model,a.inputs,a.state)

if __name__=='__main__':main()
