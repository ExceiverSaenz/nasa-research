import copy
import json
import tempfile
import unittest
from pathlib import Path
import fitz
from reading_order.test_engine import unit,doc
from reading_order.engine import order_document
from .native import inspect_pdf
from .align import align_native,compact
from .claims import reconcile_claims
from .structure import integrate
from .native_export import validate,export_native
from .native_view import build_view
from reading_order.export import digest,write


def native(rows,outlines=None,fields=None):
    evidence=[]
    for i,(text,box) in enumerate(rows):
        evidence.append(dict(id=f'n{i}',kind='text_block',page=1,source=dict(api='fixture',pointer=f'/blocks/{i}'),data=dict(bbox=box,text=text,lines=[dict(bbox=box,spans=[dict(text=text,bbox=box,font='fixture',size=10,flags=0)])])))
    for i,(title,level,parent) in enumerate(outlines or []):evidence.append(dict(id=f'o{i}',kind='outline',page=1,source=dict(api='fixture',pointer=f'/outline/{i}'),data=dict(title=title,level=level,parent_ref=parent)))
    for k,v in (fields or {}).items():evidence.append(dict(id='x:'+k,kind='xmp',page=None,source=dict(api='fixture',pointer=k),data=dict(field=k,values=v)))
    return dict(pdf_sha256='fixture',pages=[dict(page=1,width_pt=1000,height_pt=1000,rotation=0)],evidence=evidence,missing_information=[],metadata={})


class NativeTests(unittest.TestCase):
    def test_read_real_pdf_without_metadata_outlines(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t:
            p=Path(t)/'fixture.pdf';d=fitz.open();page=d.new_page();page.insert_text((50,50),'Some text');d.save(p);d.close()
            b=p.read_bytes();n=inspect_pdf(p)
            self.assertEqual(p.read_bytes(),b);self.assertEqual(n['pages'][0]['page'],1)
            self.assertTrue(any(e['kind']=='text_block' for e in n['evidence']))
            self.assertIn('outlines',n['missing_information'])

    def test_ligatures_and_many_to_many_alignment(self):
        self.assertEqual(compact('Proﬁle'),compact('Profile'))
        baseline=order_document(doc([unit('a',[100,100,450,200]),unit('b',[100,200,450,300])]))
        n=native([('one',[100,100,450,200]),('two',[100,200,450,300])]);links=align_native(n,baseline)
        self.assertEqual(next(x for x in links if x['unit_ref']=='a')['evidence_refs'],['n0'])
        self.assertEqual(next(x for x in links if x['unit_ref']=='b')['native_text'],'two')

    def test_deferred_child_not_localized(self):
        baseline=order_document(doc([unit('p',[100,100,450,500],kind='container',native='index'),unit('child',None,parent='p')],incident=True))
        links=align_native(native([('child',[100,100,450,500])]),baseline)
        child=next(x for x in links if x['unit_ref']=='child')
        self.assertEqual(child['status'],'deferred');self.assertEqual(child['evidence_refs'],[])

    def test_single_direct_source_and_conflict(self):
        prior=dict(value='main_body',strength='retained',evidence_refs=['prior'])
        direct=dict(value='metadata',strength='direct',evidence_refs=['xmp'])
        r=reconcile_claims([prior,direct]);self.assertEqual(r['status'],'conflict');self.assertEqual(r['operational_proposal'],'metadata')
        r=reconcile_claims([direct]);self.assertEqual(r['status'],'direct_supported')
        r=reconcile_claims([direct,dict(value='navigation',strength='direct',evidence_refs=['another'])]);self.assertIsNone(r['operational_proposal'])

    def test_outline_hierarchy_and_preservation(self):
        base=order_document(doc([unit('h',[100,100,450,140],text='4. Results',cat='title'),unit('h1',[100,180,450,220],text='4.1. Details',cat='title'),unit('p',[100,250,450,300],text='Some paragraph.')]))
        old=copy.deepcopy(base);n=native([('4. Results',[100,100,450,140]),('4.1. Details',[100,180,450,220]),('Some paragraph.',[100,250,450,300])],[('4. Results',1,None),('4.1. Details',2,'o0')])
        out=integrate(base,n)
        self.assertEqual(base,old);self.assertEqual(out['inventory'],base['inventory']);self.assertEqual(out['approved_routes'],base['routes'])
        nodes=out['document_structure']['sections'];self.assertEqual(nodes[1]['parent_section_ref'],nodes[0]['id'])
        self.assertEqual(nodes[1]['heading_candidates'],['h1'])

    def test_repeated_heading_keeps_candidates(self):
        b=order_document(doc([unit('a',[100,100,450,140],text='Results',cat='title'),unit('b',[550,100,900,140],text='Results',cat='title')]))
        n=native([('Results',[100,100,450,140]),('Results',[550,100,900,140])],[('Results',1,None)])
        out=integrate(b,n);s=out['document_structure']['sections'][0]
        self.assertEqual(len(s['heading_candidates']),2);self.assertEqual(s['status'],'ambiguous_alignment')

    def test_author_metadata_needs_front_context(self):
        a=unit('authors',[100,100,600,150],text='A. One, B. Two');h=unit('h',[100,300,450,340],text='1. Start',cat='title')
        cited=unit('ref',[100,600,450,660],text='A. One, B. Two',native='ref_text')
        b=order_document(doc([a,h,cited]));n=native([('A. One, B. Two',[100,100,600,150]),('1. Start',[100,300,450,340]),('A. One, B. Two',[100,600,450,660])],[('1. Start',1,None)],{'dc:creator':['A. One','B. Two']})
        out=integrate(b,n);r={x['unit_ref']:x for x in out['classification_proposals']}
        self.assertEqual(r['authors']['decisions']['document_role']['operational_proposal'],'authorship')
        self.assertNotEqual(r['ref']['decisions']['document_role']['operational_proposal'],'authorship')

    def test_missing_native_evidence_preserves_all(self):
        b=order_document(doc([unit('a',[100,100,450,200])]))
        out=integrate(b,native([]));self.assertEqual(out['inventory'],b['inventory'])
        self.assertEqual(out['document_structure']['sections'],[])

    def test_title_metadata_and_multiline_heading(self):
        b=order_document(doc([unit('title',[100,40,800,90],text='Generic paper title',cat='title'),unit('h',[100,200,450,280],text='1. Long\nheading',cat='title')]))
        n=native([('Generic paper title',[100,40,800,90]),('1. Long\nheading',[100,200,450,280])],[('Generic paper title',1,None),('1. Long heading',2,'o0')],{'dc:title':['Generic paper title']})
        out=integrate(b,n);self.assertEqual(len(out['document_structure']['sections']),1)
        title=next(p for p in out['classification_proposals'] if p['unit_ref']=='title')
        self.assertEqual(title['decisions']['document_role']['operational_proposal'],'article_title');validate(out,b)

    def test_rotation_abstains_and_separate_routes_unchanged(self):
        b=order_document(doc([unit('body',[100,100,450,200]),unit('meta',[100,500,450,600],fn='metadata')]))
        n=native([('body',[100,100,450,200])]);n['pages'][0]['rotation']=90
        out=integrate(b,n);self.assertEqual(out['evidence_links'][0]['status'],'unsupported_rotation_mapping')
        self.assertEqual(out['approved_routes'],b['routes']);self.assertGreaterEqual(len(out['approved_routes']),2)

    def test_invalid_and_missing_geometry_not_imputed(self):
        b=order_document(doc([unit('a',[-10,10,100,200]),unit('b',None)]))
        out=integrate(b,native([('text',[0,0,100,200])]))
        self.assertTrue(all(x['status']=='no_own_geometry' for x in out['evidence_links']));validate(out,b)

    def test_validation_rejects_dangling_evidence_and_hierarchy_cycle(self):
        b=order_document(doc([unit('h',[100,100,450,140],text='Results',cat='title')]))
        out=integrate(b,native([('Results',[100,100,450,140])],[('Results',1,None)]))
        bad=copy.deepcopy(out);bad['evidence_links'][0]['evidence_refs']=['absent']
        with self.assertRaisesRegex(ValueError,'dangling evidence'):validate(bad,b)
        bad=copy.deepcopy(out);s=bad['document_structure']['sections'][0];s['parent_section_ref']=s['id']
        with self.assertRaisesRegex(ValueError,'invalid hierarchy'):validate(bad,b)

    def test_unresolved_heading_does_not_invent_level(self):
        b=order_document(doc([unit('h',[100,100,450,140],text='Unnumbered heading',cat='title')]))
        out=integrate(b,native([('Unnumbered heading',[100,100,450,140])]))
        s=out['document_structure']['sections'][0];self.assertIsNone(s['declared_level']);self.assertIsNone(s['parent_section_ref'])

    def test_export_hashes_overwrite_guard_and_view_original_bytes(self):
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t:
            root=Path(t).resolve();pdf=root/'fixture.pdf';d=fitz.open();p=d.new_page(width=1000,height=1000);p.insert_text((100,120),'Fixture text');d.save(pdf);d.close()
            img=root/'original.png';Image.new('RGB',(1000,1000),'white').save(img);sha=digest(pdf)
            classified=doc([unit('a',[90,90,450,150],text='Fixture text')]);b=order_document(classified)
            cp=root/'classification.json';write(cp,classified)
            rec=dict(document_sha256=sha,pages=[dict(identity=dict(physical_page=1,width_px=1000,height_px=1000,render_sha256=digest(img)),render_path=str(img))]);rp=root/'reconciliation.json';write(rp,rec)
            b['classification_source']=dict(path=str(cp),sha256=digest(cp));b['reconciliation_source']=dict(path=str(rp),sha256=digest(rp));b['original_page_context'][0]['identity']['document_sha256']=sha
            bp=root/'base'/'document.json';write(bp,b);write(bp.parent/'manifest.json',dict(outputs={'document.json':digest(bp)}))
            before={p:digest(p) for p in (pdf,img,cp,rp,bp)};dest=root/'out';summary=export_native(pdf,bp,dest)
            self.assertEqual(summary['inventory_units'],1)
            with self.assertRaises(FileExistsError):export_native(pdf,bp,dest)
            view=build_view(dest/'document.json',bp,root/'view');self.assertEqual(view['pages'],1);self.assertEqual((root/'view/images/0001.png').read_bytes(),img.read_bytes())
            html=(root/'view/index.html').read_text(encoding='utf-8');self.assertNotIn('__DATA__',html);self.assertIn('width=device-width',html)
            for p,sha in before.items():self.assertEqual(digest(p),sha)
            cp.write_text('{}',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'classification_source hash mismatch'):export_native(pdf,bp,root/'bad')
            self.assertFalse((root/'bad').exists())

    def test_author_mention_is_not_authorship(self):
        rows=[unit('mention',[100,100,600,160],text='We compare with Jane Doe in this abstract.'),unit('h',[100,300,450,340],text='1. Start',cat='title')]
        out=integrate(order_document(doc(rows)),native([(r['original_record']['text'],r['bbox_xyxy']) for r in rows],[('1. Start',1,None)],{'dc:creator':['Jane Doe']}))
        p=out['classification_proposals'][0]
        self.assertNotEqual(p['decisions']['document_role']['operational_proposal'],'authorship')
        self.assertTrue(p.get('unapplied_native_candidates'))

    def test_metadata_without_outlines_and_cover_before_body(self):
        for later_body in (False,True):
            rows=[unit('title',[100,40,800,90],text='Generic paper title',cat='title'),unit('authors',[100,120,600,170],text='Jane Doe')]
            n=native([('Generic paper title',[100,40,800,90]),('Jane Doe',[100,120,600,170])],fields={'dc:title':['Generic paper title'],'dc:creator':['Jane Doe']})
            if later_body:
                h=unit('h',[100,100,450,140],text='1. Start',cat='title');h['page']=2;rows.append(h)
                n['pages'].append(dict(page=2,width_pt=1000,height_pt=1000,rotation=0));n['evidence'].append(dict(id='o1',kind='outline',page=2,source={},data=dict(title='1. Start',level=1,parent_ref=None)))
            out=integrate(order_document(doc(rows)),n);ps={p['unit_ref']:p for p in out['classification_proposals']}
            self.assertEqual(ps['title']['decisions']['document_role']['operational_proposal'],'article_title')
            self.assertEqual(ps['authors']['decisions']['document_role']['operational_proposal'],'authorship')
            self.assertFalse(any('title' in s['heading_candidates'] for s in out['document_structure']['sections']))

    def test_missing_native_page_is_preserved_as_unavailable(self):
        b=order_document(doc([unit('a',[100,100,450,200])]))
        n=native([]);n['pages']=[]
        self.assertEqual(integrate(b,n)['evidence_links'][0]['status'],'native_page_unavailable')


if __name__=='__main__':unittest.main()
