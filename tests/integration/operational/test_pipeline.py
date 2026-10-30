import copy
import tempfile
import unittest
import json
import subprocess
import fitz
from PIL import Image
from pathlib import Path
from integration.reading_order.export import write,digest
from tests.integration.reading_order.test_engine import unit,doc
from integration.reading_order.engine import order_document
from tests.integration.structure.test_native_structure import native
from integration.operational.pipeline import assemble,validate,metrics,export_collection
from .test_structure import fixture


class PipelineTests(unittest.TestCase):
    def test_end_to_end_pure_contract_and_pending_quality(self):
        o,a,n=fixture([unit('h',[100,100,450,140],text='3. Heading',cat='title'),unit('p',[100,200,450,280])]);old=copy.deepcopy(o);c=assemble(o,n,a);validate(c,o);self.assertEqual(o,old);self.assertEqual(c['inventory'],o['inventory']);self.assertIsNone(c['metrics']['semantic_accuracy']);self.assertEqual(len(c['structure']['memberships']),len(o['inventory']))
    def test_deferred_children_parent_and_page_abstention_preserved(self):
        rows=[unit('parent',[100,100,450,600],kind='container',native='index'),unit('child',None,parent='parent')];o=order_document(doc(rows,incident=True));n=native([]);c=assemble(o,n);validate(c,o);self.assertEqual(c['inventory'],o['inventory']);self.assertEqual(c['routes'],o['routes']);self.assertEqual(c['metrics']['deferred_children'],1)
    def test_validator_rejects_loss_or_broken_parent(self):
        o,a,n=fixture([unit('h',[100,100,450,140],text='4. Heading',cat='title')]);c=assemble(o,n,a);bad=copy.deepcopy(c);bad['inventory']=[]
        with self.assertRaises(ValueError):validate(bad,o)
        bad=copy.deepcopy(c);bad['structure']['sections'][0]['parent_ref']='missing'
        with self.assertRaises(ValueError):validate(bad,o)
    def test_existing_destination_is_never_reused(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t:
            with self.assertRaises(FileExistsError):export_collection('missing',t)
    def test_collection_export_automated_same_configuration_no_overwrites(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t:
            root=Path(t).resolve();source=root/'source';entries=[]
            for paper in (1,2):
                pdf=root/f'{paper}.pdf';d=fitz.open();p=d.new_page(width=1000,height=1000);p.insert_text((100,120),f'Paper {paper}');d.save(pdf);d.close();img=root/f'{paper}.png';Image.new('RGB',(1000,1000),'white').save(img)
                c=doc([unit('p',[90,90,450,200],text=f'Paper {paper}')]);c.update(paper_id=digest(pdf),document=str(pdf));c['pages'][0]['identity'].update(document_sha256=digest(pdf),render_sha256=digest(img));cp=root/f'class-{paper}.json';write(cp,c)
                rec=dict(document=str(pdf),document_sha256=digest(pdf),pages=[dict(identity=c['pages'][0]['identity'],render_path=str(img))]);rp=root/f'rec-{paper}.json';write(rp,rec)
                b=order_document(c);b.update(classification_source=dict(path=str(cp),sha256=digest(cp)),reconciliation_source=dict(path=str(rp),sha256=digest(rp)));rel=f'papers/{paper}/document.json';write(source/rel,b);entries.append(dict(paper=paper,data=rel))
            write(source/'summary.json',dict(documents=entries));write(source/'manifest.json',dict(outputs={p.relative_to(source).as_posix():digest(p) for p in source.rglob('*.json')}))
            out=root/'out';report=export_collection(source,out,prediction_fn=lambda items:[i['id'] for i in items]);self.assertEqual(report['papers'],2);self.assertEqual(report['manual_overrides'],0)
            self.assertEqual(report['configuration_frozen'],True);self.assertEqual((out/'papers/1/view/images/0001.png').read_bytes(),(root/'1.png').read_bytes())
            self.assertTrue(any(p.endswith('reading_order\\viewer.js') or p.endswith('reading_order/viewer.js') for p in report['code_hashes']))
            first=json.loads((out/'papers/1/document.json').read_text(encoding='utf-8'));second=json.loads((out/'papers/2/document.json').read_text(encoding='utf-8'));self.assertEqual(first['operational_config'],second['operational_config'])
            checked=subprocess.run(['node',str(Path(__file__).with_name('test_view.js')),str(out/'papers/1/view/index.html')],capture_output=True,text=True);self.assertEqual(checked.returncode,0,checked.stderr);self.assertIn('page_route_version_cases',checked.stdout)
            with self.assertRaises(FileExistsError):export_collection(source,out)


if __name__=='__main__':unittest.main()
