import hashlib
import copy
import json
from pathlib import Path
import tempfile
import unittest
from tests.integration.reading_order.test_engine import doc,unit
from integration.reading_order.export import export_collection,validate_result
from integration.reading_order.engine import order_document
from integration.reading_order.view import build_view


class IOTests(unittest.TestCase):
    def test_validator_rejects_orphans_duplicates_and_bad_references(self):
        source=doc([unit('a',[100,100,450,400])]);result=order_document(source)
        for case in ('orphan','duplicate_inventory','invalid_appearance','invalid_edge','duplicate_route'):
            broken=copy.deepcopy(result)
            if case=='orphan':broken['routes']['main'].update(sequence=[],expanded_sequence=[])
            if case=='duplicate_inventory':broken['inventory'].append(copy.deepcopy(broken['inventory'][0]))
            if case=='invalid_appearance':broken['inventory'][0]['appearance_ref']='missing'
            if case=='invalid_edge':broken['relations'].append(dict(type='precedes',scope='steps',**{'from':'missing','to':broken['steps'][0]['id']}))
            if case=='duplicate_route':broken['routes']['notes']=copy.deepcopy(broken['routes']['main'])
            with self.subTest(case=case),self.assertRaises(ValueError):validate_result(broken,source)

    def fixture(self,root):
        source=root/'source';source.mkdir();img=root/'render.png';img.write_bytes(b'original-render-bytes')
        baseline=root/'baseline.json';baseline.write_text(json.dumps(dict(pages=[dict(identity=dict(physical_page=1,width_px=1000,height_px=1000,render_sha256=hashlib.sha256(img.read_bytes()).hexdigest()),render_path=str(img))])))
        d=doc([unit('a',[100,100,450,400])]);d['source']=dict(path=str(baseline),sha256=hashlib.sha256(baseline.read_bytes()).hexdigest())
        p=source/'papers/12/document.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(d),encoding='utf-8')
        summary=source/'summary.json';summary.write_text(json.dumps(dict(documents=[dict(paper=12,data='papers/12/document.json')])) )
        (source/'manifest.json').write_text(json.dumps(dict(outputs={str(x.relative_to(source)).replace('\\','/'):hashlib.sha256(x.read_bytes()).hexdigest() for x in (p,summary)})))
        return source,img

    def test_verified_export_and_view_original_bytes(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp);source,img=self.fixture(root)
            result=export_collection(source,root/'out')
            self.assertEqual(result['inventory_units'],1)
            p=root/'out/papers/12/document.json';d=json.loads(p.read_text(encoding='utf-8'))
            self.assertEqual(d['metrics']['duplicate_content'],0)
            view=build_view(p,root/'view')
            self.assertEqual((root/'view/images/0001.png').read_bytes(),img.read_bytes())
            self.assertEqual(view['pages'],1)
            self.assertIn('data-model',(root/'view/index.html').read_text(encoding='utf-8'))
            with self.assertRaises(FileExistsError):export_collection(source,root/'out')
            with self.assertRaises(FileExistsError):build_view(p,root/'view')

    def test_hash_failure_before_output(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp);source,_=self.fixture(root)
            (source/'papers/12/document.json').write_text('{}')
            with self.assertRaises(ValueError):export_collection(source,root/'out')
            self.assertFalse((root/'out').exists())

    def test_duplicate_paper_ids_rejected_before_output(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp);source,_=self.fixture(root)
            p=source/'summary.json';s=json.loads(p.read_text());s['documents']*=2;p.write_text(json.dumps(s))
            m=source/'manifest.json';manifest=json.loads(m.read_text());manifest['outputs']['summary.json']=hashlib.sha256(p.read_bytes()).hexdigest();m.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):export_collection(source,root/'out')
            self.assertFalse((root/'out').exists())


if __name__=='__main__':unittest.main()
