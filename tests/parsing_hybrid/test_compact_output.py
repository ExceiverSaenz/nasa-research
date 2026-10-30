import tempfile,unittest,types
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from parsing.unified.adapters import Engine
class CompactOutputTests(unittest.TestCase):
 def test_mineru_exports_json_without_visual_or_duplicate_native(self):
  native=dict(schema='docvortex.middle',schema_version='2.0',pages=[dict(page_idx=0,blocks=[dict(type='text',bbox=[.1,.1,.9,.9],content='Text')])])
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);image=root/'input.png';Image.new('RGB',(20,10)).save(image)
   engine=Engine.__new__(Engine);engine.model='mineru'
   engine.parser=types.SimpleNamespace(parse=lambda path:types.SimpleNamespace(middle_json=types.SimpleNamespace(to_dict=lambda **kw:native),_model_output=None))
   job=dict(identity=dict(width_px=20,height_px=10))
   with patch('parsing.unified.adapters.validate_job',return_value=image):engine.process(job,root/'out')
   self.assertEqual({p.name for p in (root/'out').iterdir()},{'identity.json','middle-native.json','regions.json'})
