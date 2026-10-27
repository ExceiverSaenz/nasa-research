"""Offline tests: fake methods/tensors only, never import an OCR runtime."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from page_integration.square_roi import square_image, square_original_box, prepare_square, unpack_square
from page_integration.trace_observer import TraceRecorder,snapshot


class PaddingTests(unittest.TestCase):
    def test_square_keeps_pixels_and_maps_normalized_boxes_without_double_scaling(self):
        from PIL import Image
        image=Image.new('RGB',(831,76),(1,2,3));canvas,padding=square_image(image)
        self.assertEqual(canvas.size,(831,831));self.assertEqual(padding,[0,377,0,378])
        self.assertEqual(canvas.crop((0,377,831,453)).tobytes(),image.tobytes())
        self.assertEqual(canvas.getpixel((0,0)),(255,255,255))
        transform=dict(roi_xyxy_px=[112,154,943,230],canvas_size_px=[831,831],padding_ltrb_px=padding)
        result=square_original_box([6/831,407/831,66/831,421/831],transform)
        for actual,expected in zip(result['bbox'],[118,184,178,198]):self.assertAlmostEqual(actual,expected)
        self.assertTrue(result['inside_content'])
        self.assertFalse(square_original_box([0,0,.1,.1],transform)['inside_content'])
        with self.assertRaises(ValueError):square_original_box([6,407,66,421],transform)

    def test_new_package_keeps_original_settings_and_reference_outside(self):
        import zipfile
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            p=Path(temp)/'package';plan=prepare_square(p)
            self.assertEqual(len(plan['targets']),1)
            self.assertEqual(plan['targets'][0]['transform']['size_px'],[831,831])
            self.assertEqual(plan['targets'][0]['transform']['padding_ltrb_px'],[0,377,0,378])
            with zipfile.ZipFile(p/'upload.zip') as z,zipfile.ZipFile('code/packages/table1-header-v1/upload.zip') as old:
                for n in ['config.yaml','requirements.lock','requirements-freeze.txt','model-manifest.json','model-download-receipt.json']:
                    self.assertEqual(z.read(n),old.read(n))
                self.assertEqual(z.read('plan.json'),(p/'plan.json').read_bytes())
                self.assertFalse(any('reference' in n for n in z.namelist()))
            unpack_square(p/'upload.zip',p/'upload.sha256',Path(temp)/'unpacked')
            with self.assertRaises(FileExistsError):prepare_square(p)


class TraceTests(unittest.TestCase):
    def test_numpy_like_nonfinite_data_is_preserved_as_explicit_tokens(self):
        class Scalar:
            __module__='numpy'
            def item(self):return float('nan')
        class Array:
            __module__='numpy';shape=(2,);dtype='float32';size=2
            def tobytes(self):return b'fixture'
            def tolist(self):return [float('inf'),.2]
        self.assertEqual(snapshot(Scalar()),{'nonfinite':'nan'})
        self.assertEqual(snapshot(Array())['values'],[{'nonfinite':'inf'},.2])

    def test_model_output_records_raw_queries_without_order_tensor_expansion(self):
        class Tensor:
            shape=(1,2,2);dtype='float32';device='fake'
            def detach(self):return self
            def cpu(self):return self
            def tolist(self):return [[[.1,.2],[.3,float('-inf')]]]
        class Output(dict):
            pred_boxes=Tensor();logits=Tensor();order_logits=Tensor()
        output=Output(irrelevant_large_field=Tensor())
        data=snapshot(output)
        self.assertEqual(set(data),{'pred_boxes','logits','order_logits_shape'})
        self.assertEqual(data['logits']['values'][0][1][1],{'nonfinite':'-inf'})

    def test_descriptor_wrappers_call_once_keep_identity_and_restore(self):
        class Detector:
            calls=0
            def predict(self,boxes):self.calls+=1;return boxes
            @classmethod
            def filter(cls,boxes):return boxes
            @staticmethod
            def normalize(boxes):return boxes
        original=dict(Detector.__dict__);data=[{'score':.2,'bbox':[1,2,3,4]}];before=copy.deepcopy(data)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            with TraceRecorder(Path(temp)/'traces') as trace:
                for name in ['predict','filter','normalize']:trace.hook_method(Detector,name)
                instance=Detector()
                self.assertIs(instance.predict(data),data);self.assertIs(instance.filter(data),data)
                self.assertIs(instance.normalize(data),data);self.assertEqual(instance.calls,1)
            for name in ['predict','filter','normalize']:self.assertIs(Detector.__dict__[name],original[name])
            self.assertEqual(data,before)
            events=[json.loads(p.read_bytes()) for p in (Path(temp)/'traces').glob('*-after.json')]
            self.assertEqual(len(events),3)
            self.assertEqual(events[0]['result'][0]['score'],.2)

    def test_mutation_is_observed_not_changed_and_original_exception_propagates(self):
        failure=RuntimeError('original failure')
        class Detector:
            def mutate(self,value):value.pop('image');value['text']='Table 1'
            def fail(self):raise failure
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            with TraceRecorder(Path(temp)/'traces') as trace:
                trace.hook_method(Detector,'mutate');trace.hook_method(Detector,'fail')
                data={'image':'fixture'};Detector().mutate(data)
                self.assertEqual(data,{'text':'Table 1'})
                with self.assertRaises(RuntimeError) as caught:Detector().fail()
                self.assertIs(caught.exception,failure)
            files=list((Path(temp)/'traces').glob('*-before.json'))
            self.assertEqual(json.loads(files[0].read_bytes())['args'],[{'image':'fixture'}])

    def test_module_aliases_are_traced_once_and_restored_even_for_late_imports(self):
        module=types.ModuleType('fake_mineru.ocr');alias=types.ModuleType('fake_mineru.pipeline');late=types.ModuleType('fake_mineru.late')
        def normalize(value):return value
        module.normalize=normalize;alias.normalize=normalize
        sys.modules[module.__name__]=module;sys.modules[alias.__name__]=alias
        try:
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
                with TraceRecorder(Path(temp)/'traces') as trace:
                    trace.hook_function(module,'normalize')
                    self.assertEqual(alias.normalize(7),7)
                    late.normalize=module.normalize;sys.modules[late.__name__]=late
                self.assertIs(alias.normalize,normalize);self.assertIs(module.normalize,normalize)
                self.assertIs(late.normalize,normalize)
        finally:
            for m in [module,alias,late]:sys.modules.pop(m.__name__,None)


if __name__=='__main__':unittest.main()
