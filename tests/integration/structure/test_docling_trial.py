import copy
import unittest
import json
import tempfile
import hashlib
import re
from pathlib import Path
from tests.integration.reading_order.test_engine import unit,doc,group,content
from integration.reading_order.engine import order_document
from integration.structure.docling_trial import apply_docling
from integration.structure.docling_comparison import build_comparison


def reverse(items):return [x['id'] for x in reversed(items)]


class TrialTests(unittest.TestCase):
    def test_comparison_site_original_images_and_no_overwrite(self):
        from tests.integration.reading_order.test_io import IOTests
        from integration.reading_order.export import export_collection
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp);source,img=IOTests().fixture(root)
            sp=source/'papers/12/document.json';sd=json.loads(sp.read_text(encoding='utf-8'))
            marker='Literal </script><img> text'
            sd['regions'][0]['original_record']['text']=marker;sp.write_text(json.dumps(sd),encoding='utf-8')
            mp=source/'manifest.json';md=json.loads(mp.read_text());md['outputs']['papers/12/document.json']=hashlib.sha256(sp.read_bytes()).hexdigest();mp.write_text(json.dumps(md))
            export_collection(source,root/'baseline')
            bp=root/'baseline/papers/12/document.json';base=json.loads(bp.read_text(encoding='utf-8'))
            cp=root/'candidate.json';cp.write_text(json.dumps(apply_docling(base,reverse)),encoding='utf-8')
            result=build_comparison(bp,cp,root/'site')
            self.assertEqual(result['pages'],1)
            self.assertEqual((root/'site/images/0001.png').read_bytes(),img.read_bytes())
            self.assertTrue((root/'site/baseline.html').exists())
            self.assertIn('trial-control',(root/'site/docling.html').read_text(encoding='utf-8'))
            html=(root/'site/docling.html').read_text(encoding='utf-8')
            embedded=json.loads(re.search(r'<script id="data-model" type="application/json">(.*?)</script>',html,re.S).group(1))
            self.assertEqual(embedded['units'][0]['text'],marker)
            with self.assertRaises(FileExistsError):build_comparison(bp,cp,root/'site')

    def test_preserve_inventory_input_routes_and_internal_order(self):
        source=doc([unit('a',[100,100,450,200]),unit('fig',[100,300,450,500],cat='figure'),unit('cap',[100,510,450,560],cat='caption')],[group('g',['fig'],'cap')])
        base=order_document(source);old=copy.deepcopy(base);out=apply_docling(base,reverse)
        self.assertEqual(base,old);self.assertEqual(out['inventory'],base['inventory'])
        self.assertEqual(set(content(out)),set(content(base)))
        self.assertEqual(content(out)[:2],['cap','fig'])
        self.assertEqual([s['children'] for s in out['steps']],[s['children'] for s in base['steps']])

    @unittest.expectedFailure
    def test_known_docling_limitation_columns_and_full_width_heading(self):
        base=order_document(doc([unit('h',[100,30,900,80],cat='title'),unit('l1',[100,150,450,300]),unit('l2',[100,400,450,600]),unit('r1',[550,150,900,300]),unit('r2',[550,400,900,600])]))
        self.assertEqual(content(apply_docling(base)),['h','l1','l2','r1','r2'])

    def test_real_predictor_has_no_interface_fallback(self):
        base=order_document(doc([unit('a',[100,100,450,200]),unit('b',[100,300,450,400])]))
        out=apply_docling(base)
        self.assertFalse(out['trial']['batches'][0]['fallback'])
        self.assertEqual(set(content(out)),{'a','b'})

    def test_abstention_not_processed(self):
        base=order_document(doc([unit('p',[100,100,450,500],kind='container',native='index'),unit('c',None,parent='p')],incident=True))
        out=apply_docling(base,lambda x:self.fail('blocked page passed to predictor'))
        self.assertEqual(out['routes'],base['routes']);self.assertEqual(out['inventory'],base['inventory'])

    def test_bad_permutation_keeps_baseline_and_warning(self):
        base=order_document(doc([unit('a',[100,100,450,200]),unit('b',[100,300,450,400])]))
        out=apply_docling(base,lambda x:[x[0]['id']]*len(x))
        self.assertEqual(out['routes'],base['routes'])
        self.assertTrue(out['trial']['batches'][0]['fallback'])

    def test_unknown_coordinates_keep_route(self):
        base=order_document(doc([unit('a',None),unit('b',[100,300,450,400])]))
        out=apply_docling(base,lambda x:self.fail('unknown box batch processed'))
        self.assertEqual(out['routes'],base['routes'])

    def test_continuity_is_historical_not_reused(self):
        base=order_document(doc([unit('a',[100,800,450,900],text='continued'),unit('b',[550,100,900,200],text='onward')]))
        out=apply_docling(base,reverse)
        self.assertFalse(any(r['type']=='paragraph_continues' for r in out['relations']))
        self.assertEqual(out['baseline_evidence_relations'],base['relations'])

    def test_shared_reference_cannot_precede_content(self):
        base=order_document(doc([unit('a',[100,100,450,300],cat='figure'),unit('b',[550,100,900,300],cat='figure'),unit('cap',[100,320,900,370],cat='caption')],[group('g1',['a'],'cap'),group('g2',['b'],'cap')]))
        out=apply_docling(base,reverse);steps={s['id']:s for s in out['steps']};rank={s:i for i,s in enumerate(out['routes']['main']['expanded_sequence'])}
        for s in steps.values():
            if s['kind']=='reference':self.assertLess(rank[s['content_appearance_ref']],rank[s['id']])
        self.assertEqual(content(out).count('cap'),1)

    def test_frozen_classification_not_corrected(self):
        base=order_document(doc([unit('author',[100,100,450,200],text='An author'),unit('meta',[100,300,450,400],fn='metadata')]))
        out=apply_docling(base,reverse)
        self.assertEqual(out['routes']['metadata'],base['routes']['metadata'])
        self.assertEqual(out['inventory'],base['inventory'])


if __name__=='__main__':unittest.main()
