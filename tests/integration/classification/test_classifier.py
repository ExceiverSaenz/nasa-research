"""Offline contract and failure-mode tests; no models or external services."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from integration.classification.classifier import classify_document
from integration.classification.export import export_collection


def region(id='a', native='text', text='A scientific paragraph.', box=None, parser='mineru', **kw):
    return dict(id=id, parser=parser, native_type=native, text=text,
                bbox=box if box is not None else [100, 400, 450, 500],
                role='segment', parent=None, source={}, **kw)


def document(records, pages=1):
    return dict(document='example.pdf', document_sha256='a'*64, pages=[dict(
        identity=dict(physical_page=n+1, width_px=1000, height_px=1000),
        records=copy.deepcopy(records), parsers={'mineru':'completed', 'layoutlmv3':'completed', 'table_transformer':'completed'},
        status='completed', incidents=[], groups=[], relations=[], decisions=[])
        for n in range(pages)])


def decision(result, id='a'):
    return next(r['classification'] for r in result['regions'] if r['id']==id)


class ClassifierTests(unittest.TestCase):
    def test_preservation_and_no_input_mutation(self):
        d=document([region()]); before=copy.deepcopy(d)
        out=classify_document(d)
        self.assertEqual(d,before)
        self.assertEqual(out['regions'][0]['original_record'],d['pages'][0]['records'][0])
        self.assertIsNone(out['reading_order']['resolved_sequence'])

    def test_native_caption(self):
        c=decision(classify_document(document([region(native='table_caption', text='Table 1. Results') ])))
        self.assertEqual(c['category']['value'],'caption')
        self.assertEqual(c['function']['value'],'associated_content')

    def test_internal_mention_not_caption(self):
        c=decision(classify_document(document([region(text='We show in Figure 1 the results.') ])))
        self.assertEqual(c['category']['value'],'text')
        self.assertNotIn('caption',c['category']['candidates'])

    def test_caption_pattern_needs_context_and_conflicts_with_title(self):
        records=[region(native='paragraph_title',text='Figure 1. Results',box=[100,620,450,660]),
                 region('f','image_body','',box=[100,200,450,600])]
        c=decision(classify_document(document(records)))
        self.assertIsNone(c['category']['value'])
        self.assertEqual(set(c['category']['candidates']),{'title','caption'})
        self.assertTrue(c['requires_human_validation'])

    def test_metadata_and_reference_doi(self):
        records=[region(text='DOI: 10.1234/example',box=[100,100,450,130]),
                 region('b','ref_text','DOI: 10.1234/example',box=[100,150,450,180])]
        out=classify_document(document(records))
        self.assertEqual(decision(out)['function']['value'],'metadata')
        self.assertEqual(decision(out,'b')['subtype']['value'],'bibliographic_reference')
        self.assertEqual(decision(out,'b')['function']['value'],'main_body')

    def test_footnote_not_margin(self):
        c=decision(classify_document(document([region(native='page_footnote',box=[100,940,450,980]) ])))
        self.assertEqual(c['category']['value'],'text')
        self.assertEqual(c['function']['value'],'associated_content')

    def test_recurrence_counts_pages_not_duplicates(self):
        d=document([region(text='Journal of testing',box=[100,20,600,50])],3)
        for i,p in enumerate(d['pages']): p['records'][0]['id']=str(i)
        out=classify_document(d)
        self.assertEqual(decision(out,'0')['function']['value'],'navigation')
        d=document([region(str(i),text='Journal of testing',box=[100,20,600,50]) for i in range(3)])
        self.assertNotEqual(decision(classify_document(d),'0')['function']['value'],'navigation')

    def test_native_title_not_automatically_metadata(self):
        c=decision(classify_document(document([region(native='title',parser='layoutlmv3',text='') ])))
        self.assertIsNone(c['function']['value'])
        self.assertTrue(c['requires_human_validation'])

    def test_missing_box_deferred_and_page_abstention_preserved(self):
        d=document([region(native='index')]); d['pages'][0]['records'][0].update(bbox=None,parent='parent')
        d['pages'][0]['incidents']=['invalid_geometry']; d['pages'][0]['status']='partial'
        out=classify_document(d); c=decision(out)
        self.assertEqual(out['pages'][0]['original_status'],'partial')
        self.assertIn('geometry_deferred', [w['code'] for w in c['warnings']])
        self.assertIsNone(out['regions'][0]['bbox_xyxy'])

    def test_geometry_abstention_applies_to_valid_siblings_too(self):
        d=document([region(),region('child')])
        d['pages'][0]['records'][1].update(bbox=None,parent='parent')
        d['pages'][0].update(status='partial',incidents=['invalid_geometry'])
        c=decision(classify_document(d))
        self.assertEqual(c['function']['status'],'abstained')
        self.assertIsNone(c['function']['value'])
        self.assertIn('main_body',c['function']['candidates'])

    def test_mutually_comparable_conflict_and_coarse_support(self):
        d=document([region(native='image_body',text=''),region('b','table','',parser='table_transformer')])
        self.assertIsNone(decision(classify_document(d))['category']['value'])
        d=document([region(native='image_caption'),region('b','text','',parser='layoutlmv3')])
        self.assertEqual(decision(classify_document(d))['category']['value'],'caption')

    def test_unknown_class_and_logo_remain_reviewable(self):
        out=classify_document(document([region(native='new_class'),region('f','image_body','',box=[100,30,200,100])]))
        self.assertTrue(decision(out)['requires_human_validation'])
        self.assertIsNone(decision(out,'f')['function']['value'])
        self.assertIn('editorial',decision(out,'f')['function']['candidates'])

    def test_order_id_and_scale_invariance(self):
        d=document([region(native='paragraph_title',text='1 Introduction',box=[100,300,450,340]),
                    region('b',box=[100,350,450,500])])
        out=classify_document(d)
        self.assertEqual(decision(out)['function']['value'],'main_body')
        d2=copy.deepcopy(d); d2['pages'][0]['records'].reverse()
        self.assertEqual(out,classify_document(d2))
        for p in d2['pages']:
            p['identity']['width_px']*=2; p['identity']['height_px']*=2
            for r in p['records']: r['bbox']=[x*2 for x in r['bbox']]; r['id']='new-'+r['id']
        c=decision(classify_document(d2),'new-a')
        self.assertEqual(c['function'],decision(out)['function'])

    def test_export_integrity_and_no_overwrite(self):
        import hashlib
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp); src=root/'input'; (src/'papers'/'1').mkdir(parents=True)
            native=root/'native.json'; native.write_text('{}')
            r=region(); r['source']={'path':str(native),'sha256':hashlib.sha256(native.read_bytes()).hexdigest(),'pointer':'/0'}
            (src/'papers'/'1'/'document.json').write_text(json.dumps(document([r])),encoding='utf-8')
            (src/'summary.json').write_text(json.dumps({'documents':[{'paper':1,'data':'papers/1/document.json'}]}))
            result=export_collection(src,root/'out')
            self.assertEqual(result['records'],1)
            self.assertTrue((root/'out'/'review-queue.json').exists())
            with self.assertRaises(FileExistsError):export_collection(src,root/'out')
            native.write_text('changed')
            with self.assertRaises(ValueError):export_collection(src,root/'bad')
            self.assertFalse((root/'bad').exists())

    def test_export_rejects_duplicate_or_escaping_paper_before_write(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp); src=root/'input'; src.mkdir()
            for i in (1,2):
                d=document([]); d['document_sha256']=str(i)*64
                (src/f'{i}.json').write_text(json.dumps(d),encoding='utf-8')
            for papers in ((1,1),(1,'../../escape')):
                (src/'summary.json').write_text(json.dumps({'documents':[{'paper':p,'data':f'{i}.json'} for i,p in enumerate(papers,1)]}))
                with self.assertRaises(ValueError):export_collection(src,root/'out')
                self.assertFalse((root/'out').exists())


if __name__=='__main__': unittest.main()
