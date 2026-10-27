"""Execute controller sequencing with inert model doubles, never real models."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import tempfile
import unittest
from unittest.mock import patch
from document_trial import worker, inventory
from document_trial.common import MODELS, save, sha, read


class StageSequenceTests(unittest.TestCase):
    def scenario(self,model,fail_second=False,repeat=False):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp,ExitStack() as stack:
            root=Path(temp);inputs=root/'inputs';state=root/'state'
            inputs.mkdir();state.mkdir();(inputs/'mineru').mkdir()
            (inputs/'mineru/config.yaml').write_bytes(b'original');(state/'config.yaml').write_bytes(b'original')
            spec=dict(python='3.9.25',cuda='11.1',packages={'packaging':'26.3'})
            (inputs/'document.pdf').write_bytes(b'synthetic PDF identity only')
            document_hash=sha(inputs/'document.pdf')
            save(inputs/'plan.json',dict(models={model:spec},physical_pages=[1],page_count=1,dpi=200,document_sha256=document_hash,regression=None))
            folder=state/'pages/0001';folder.mkdir(parents=True);(folder/'render.png').write_bytes(b'synthetic-image')
            save(folder/'identity.json',dict(document_sha256=document_hash,physical_page=1,render_sha256=sha(folder/'render.png'),geometry=dict(crop_box_pt=[0,0,10,10],rotation_deg=0),execution_id='offline-test'))
            events=[];calls=[]
            def logged(args,where,**kw):
                calls.append(list(args));version='24.2' if fail_second and len(calls)==2 else '26.3'
                save(args[-1],dict(pid=-1,torch_imported=False,executable=sys.executable,prefix=sys.prefix,
                    distributions=[dict(name='packaging',version=version,metadata_path='/env/packaging.dist-info',root_path='/env')]))
            class Detector:
                def __init__(self,*args):events.append('construct')
                def load(self):events.append('load');return {}
                def predict(self,image):events.append('predict');return ([],[]) if model=='table_transformer' else []
                def metadata(self):return {'synthetic':True}
            class Image:
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def convert(self,mode):return self
            def parse(path):
                events.append('parse')
                return NS(middle_json=NS(to_dict=lambda **kw:{'synthetic':True}),_model_output=None,save=lambda writer:None)
            def activate(*args):events.append('activate')
            config=NS(model=NS(source='local'),llm_aided=NS(features=NS(title_leveling=False,cross_page_table_cell_merge=False)))
            modules={
                'torch':NS(cuda=NS(is_available=lambda:True,get_device_name=lambda n:'Tesla T4'),version=NS(cuda='11.1')),
                'PIL':NS(Image=NS(open=lambda path:Image())), 'numpy':NS(asarray=lambda image:image),
                'inference.detector':NS(LayoutLMv3Detector=Detector),
                'inference.types':NS(RenderedPage=lambda *args:NS()),
                'inference.outputs':NS(save_regions=lambda pred,render,dest,**kw:save(dest/'regions.json',{'synthetic':True}),save_overlay=lambda *args:None),
                'table_transformer.detector':NS(TableTransformerDetector=Detector,validate_load_report=lambda report:None),
                'mineru.config':NS(config=config),
                'mineru.model.runtime.device':NS(get_device=lambda:'cuda',resolve_small_model_backend=lambda:'torch'),
                'mineru_probe.remote_job':NS(activate_verified_models=activate),
                'mineru_probe.run_image':NS(parse_native=parse),
                'mineru.parser.writer':NS(FileBasedDataWriter=lambda path:path),
                'mineru_probe.outputs':NS(export_regions=lambda image,native,dest:save(dest/'regions.json',{'synthetic':True}))}
            stack.enter_context(patch.dict(sys.modules,modules))
            stack.enter_context(patch.dict('os.environ',{'MINERU_TABLE_DEVICE':'cpu'}))
            stack.enter_context(patch.object(worker.platform,'python_version',return_value='3.9.25'))
            stack.enter_context(patch.object(worker,'collect',return_value={'distributions':[],'synthetic':True}))
            stack.enter_context(patch.object(inventory,'run_logged',side_effect=logged))
            worker.probe(model,inputs,state)
            before={p:p.read_bytes() for p in state.glob('*.json')}
            if repeat:
                with self.assertRaises(FileExistsError):worker.probe(model,inputs,state)
                self.assertEqual(len(calls),1)
            elif fail_second:
                with self.assertRaisesRegex(ValueError,'INCOMPATIBLE'):worker.infer(model,inputs,state)
                self.assertEqual(events,[])
                self.assertEqual(len(calls),2)
            else:
                worker.infer(model,inputs,state)
                self.assertEqual(read(folder/model/'status.json')['status'],'completed')
                self.assertEqual(events.count('parse' if model=='mineru' else 'predict'),1)
                self.assertEqual(len(calls),2)
                self.assertNotEqual(calls[0][-1],calls[1][-1])
                for stage in ('preflight','before-infer'):
                    runtime=read(state/('runtime-'+model+'-'+stage+'.json'))
                    self.assertEqual(runtime['stage'],stage)
                    self.assertTrue((state/runtime['inventory_clean']).is_file())
                    self.assertTrue((state/runtime['inventory_after_torch']).is_file())
            for path,data in before.items():self.assertEqual(path.read_bytes(),data)

    def test_preflight_then_entire_infer_branch_for_all_models(self):
        for model in MODELS:
            with self.subTest(model=model):self.scenario(model)

    def test_second_check_drift_blocks_before_model_load_for_all_models(self):
        for model in MODELS:
            with self.subTest(model=model):self.scenario(model,fail_second=True)

    def test_same_stage_repeat_still_rejected_for_all_models(self):
        for model in MODELS:
            with self.subTest(model=model):self.scenario(model,repeat=True)

if __name__=='__main__':unittest.main()
