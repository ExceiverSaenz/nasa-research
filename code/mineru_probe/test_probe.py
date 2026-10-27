"""Contracts only: these tests do not demonstrate MinerU/T4 inference."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'code'))
IMAGE = ROOT/'code/results/layoutlmv3-page/20261023T153938Z/review/render.png'


def native():
    return {'schema':'docvortex.middle', 'schema_version':'2.0', 'pages':[
        {'page_idx':0, 'blocks':[{'type':'table', 'index':0, 'bbox':[.1,.2,.9,.6],
            'content':[{'type':'table_body','index':0,'bbox':[.1,.2,.9,.6],'content':'<table></table>'},
                       {'type':'table_caption','bbox':[.1,.1,.9,.2],'content':[]}]}]}]}


class ProbeTests(unittest.TestCase):
    def test_normalized_coordinates_preserve_hierarchy_and_source(self):
        from mineru_probe.outputs import convert_regions
        document = native(); before=copy.deepcopy(document)
        result=convert_regions(document, 100, 200)
        self.assertEqual(result['regions'][0]['bbox'],[10.,40.,90.,120.])
        self.assertEqual(len(result['regions']),3)
        self.assertEqual(result['regions'][2]['parent_id'],'p0-b0')
        self.assertEqual(result['regions'][2]['native_label'],'table_caption')
        self.assertIsNone(result['regions'][0]['score'])
        self.assertEqual(document,before)

    def test_schema_geometry_and_page_mismatches_fail(self):
        from mineru_probe.outputs import convert_regions
        for mutate in (lambda d:d.update(schema='old'),
                       lambda d:d['pages'].append({'page_idx':1,'blocks':[]}),
                       lambda d:d['pages'][0]['blocks'][0].update(bbox=[0,0,100,100]),
                       lambda d:d['pages'][0]['blocks'][0].update(bbox=[0,0,0,.5])):
            doc=native(); mutate(doc)
            with self.assertRaises(ValueError): convert_regions(doc,100,200)

    def test_missing_geometry_is_reported_without_inventing_box(self):
        from mineru_probe.outputs import convert_regions
        doc=native();doc['pages'][0]['blocks'][0]['content'][1].pop('bbox')
        result=convert_regions(doc,100,200)
        self.assertIsNone(result['regions'][2]['bbox'])
        self.assertEqual(result['geometry_warnings'],['p0-b0-c1'])

    def test_run_preserves_native_before_derived_export_failure(self):
        from mineru_probe.run_image import run_image
        class Fake:
            _model_output=None
            @property
            def middle_json(self): return self
            def to_dict(self,**kwargs): return native()
            def save(self,writer): raise OSError('later resource export failed')
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'run'
            status=run_image(IMAGE,output,parser=lambda path:Fake())
            self.assertEqual(status['stage'],'native_assets')
            self.assertEqual(status['status'],'failed')
            self.assertEqual(json.loads((output/'middle-native.json').read_text()),native())
            with self.assertRaises(FileExistsError): run_image(IMAGE,output,parser=lambda p:Fake())

    def test_changed_input_rejected_before_parser(self):
        from mineru_probe.run_image import run_image
        with tempfile.TemporaryDirectory() as directory:
            image=Path(directory)/'input.png';Image.new('RGB',(10,10)).save(image)
            status=run_image(image,Path(directory)/'run',parser=lambda p:self.fail('must not parse'))
            self.assertEqual(status['stage'],'input')
            self.assertEqual(status['status'],'failed')

    def test_export_retains_json_on_image_failure(self):
        from mineru_probe.outputs import export_regions
        with tempfile.TemporaryDirectory() as directory:
            with patch('PIL.Image.Image.save',side_effect=OSError('disk')):
                with self.assertRaises(OSError): export_regions(Image.new('RGB',(100,200)),native(),Path(directory))
            self.assertEqual(len(json.loads((Path(directory)/'regions.json').read_text())['regions']),3)

    def test_empty_page_is_valid_not_accuracy(self):
        from mineru_probe.outputs import convert_regions
        doc=native();doc['pages'][0]['blocks']=[]
        self.assertEqual(convert_regions(doc,100,200)['regions'],[])


if __name__=='__main__':unittest.main()
