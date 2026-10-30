import hashlib
from pathlib import Path
import tempfile
import unittest
from parsing.unified import adapters, compatibility

class AdapterTests(unittest.TestCase):
    def test_unknown_engine_rejected_without_runtime_imports(self):
        with self.assertRaisesRegex(ValueError,'Unknown'): adapters.load_engine('other',{})

    def test_identity_requires_exact_page_and_render(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            path=Path(temp)/'render.png'; path.write_bytes(b'png')
            job={'paper_id':'x','page':1,'render_path':str(path),'identity':{
                'document_sha256':'a'*64,'render_sha256':hashlib.sha256(b'png').hexdigest(),
                'physical_page':1,'width_px':10,'height_px':20,'dpi':200,
                'geometry':{'crop_box_pt':[0,0,3.6,7.2],'rotation_deg':0}}}
            self.assertEqual(adapters.validate_job(job),path)
            job['identity']['physical_page']=2
            with self.assertRaises(ValueError): adapters.validate_job(job)
            job['identity']['physical_page']=1; path.write_bytes(b'changed')
            with self.assertRaises(ValueError): adapters.validate_job(job)

    def test_vendor_guard_is_atomic_and_baseline_unchanged(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root=Path(temp)/'source'; root.mkdir(); (root/'bad.py').write_text('bad')
            destination=Path(temp)/'copy'
            with self.assertRaises(ValueError): compatibility.prepare_vendor(root,destination)
            self.assertFalse(destination.exists())
            self.assertEqual((root/'bad.py').read_text(),'bad')

    def test_attention_mask_rejects_non_matrix(self):
        class Mask: ndim=3
        with self.assertRaises(ValueError): compatibility.legacy_attention_mask(Mask(),None)

    def test_real_vendor_copy_preserves_original_and_guards_reuse(self):
        source=Path(__file__).resolve().parents[2]/'new_code'/'parse_system'/'vendor'/'unilm'
        before={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in compatibility.SOURCE_HASHES}
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            destination=Path(temp)/'vendor'
            compatibility.prepare_vendor(source,destination)
            compatibility.verify_vendor(destination)
            for path in destination.rglob('*.py'): compile(path.read_text(encoding='utf-8'),str(path),'exec')
            text=(destination/'layoutlmv3/layoutlmft/models/layoutlmv3/modeling_layoutlmv3.py').read_text()
            self.assertIn('legacy_attention_mask(attention_mask, self.dtype)',text)
            self.assertIn('self.post_init()\n\n    def get_input_embeddings',text)
            self.assertNotIn('self.get_head_mask(',text)
            self.assertNotIn('AutoConfig.register',(destination/'layoutlmv3/layoutlmft/models/layoutlmv3/__init__.py').read_text())
            with self.assertRaises(ValueError): compatibility.prepare_vendor(source,destination)
        self.assertEqual(before,{n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in before})


    def test_image_only_head_mask_preserves_unmasked_layers(self):
        self.assertEqual(compatibility.legacy_head_mask(None,3),[None,None,None])
        with self.assertRaises(ValueError): compatibility.legacy_head_mask([1],3)

    def test_persistent_table_process_preserves_native_scores_and_refuses_overwrite(self):
        import json
        from PIL import Image
        class Detector:
            calls=0
            def predict(self,image):
                self.calls+=1
                return {'logits':[[1,2,3]]},[{'bbox':[1.25,2.5,7.5,9.0],'score':0.75,'native_label':'table','query_id':4}]
            def metadata(self): return {'calls':self.calls}
        engine=adapters.Engine.__new__(adapters.Engine);engine.model='table_transformer';engine.detector=Detector()
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root=Path(temp);render=root/'render.png';Image.new('RGB',(10,20)).save(render)
            identity={'document_sha256':'a'*64,'render_sha256':hashlib.sha256(render.read_bytes()).hexdigest(),
                      'physical_page':1,'width_px':10,'height_px':20,'dpi':200,
                      'geometry':{'crop_box_pt':[0,0,3.6,7.2],'rotation_deg':0}}
            job={'paper_id':'paper','page':1,'render_path':str(render),'identity':identity}
            engine.process(job,root/'first');engine.process(job,root/'second')
            self.assertEqual(engine.detector.calls,2)
            saved=json.loads((root/'second'/'regions.json').read_text())
            self.assertEqual(saved['regions'][0]['score'],0.75)
            self.assertEqual(saved['regions'][0]['bbox'],[1.25,2.5,7.5,9.0])
            self.assertEqual(saved['coordinate_system'],identity)
            with self.assertRaises(FileExistsError): engine.process(job,root/'first')
            self.assertEqual(engine.detector.calls,2)

    def test_legacy_attention_mask_math(self):
        import numpy as np
        class Mask(np.ndarray):
            def to(self,dtype): return np.asarray(self,dtype=dtype)
        mask=np.array([[1,0]],dtype=np.float32).view(Mask)
        result=compatibility.legacy_attention_mask(mask,np.float32)
        np.testing.assert_array_equal(result,np.array([[[[0,-10000]]]],dtype=np.float32))
