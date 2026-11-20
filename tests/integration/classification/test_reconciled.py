"""Offline tests for reconciled units, not parser-layer classification."""
import copy
import unittest
import hashlib
import json
import tempfile
from pathlib import Path
from tests.integration.classification.test_classifier import document, region
from integration.classification.reconciled import classify_reconciled_document
from integration.classification.export_reconciled import export_collection


def fixture(records,objects=None,containers=None,groups=None):
    d=document(records)
    p=d['pages'][0]; p['objects']=objects if objects is not None else [records[0]['id']]
    p['containers']=containers or []; p['groups']=groups or []
    p['correspondences']=[]
    for r in p['records']:
        r.setdefault('category','Texto');r.setdefault('classification_status','native_preserved')
        r.setdefault('classification_reason','native_mapping')
    return d


class ReconciledTests(unittest.TestCase):
    def test_selected_units_only_and_no_input_mutation(self):
        d=fixture([region(),region('alternative',parser='layoutlmv3')]); before=copy.deepcopy(d)
        out=classify_reconciled_document(d)
        self.assertEqual([r['id'] for r in out['regions']],['a'])
        self.assertEqual([r['id'] for r in out['evidence_records']],['alternative'])
        self.assertEqual(d,before)
        self.assertEqual(out['regions'][0]['original_record'],d['pages'][0]['records'][0])

    def test_retained_category_is_seed_not_native_remapping(self):
        d=fixture([region(native='image_body',text='')])
        d['pages'][0]['records'][0]['category']='Tablas'
        out=classify_reconciled_document(d);c=out['regions'][0]['classification']
        self.assertEqual(c['retained_classification']['category'],'Tablas')
        self.assertIn('table',c['category']['candidates'])
        self.assertIn('figure',c['category']['candidates'])
        self.assertIsNone(c['category']['value'])
        self.assertIn('retained_category_seed-v2',c['rule_refs'])

    def test_unknown_retained_category_not_silently_replaced(self):
        d=fixture([region()]);d['pages'][0]['records'][0]['category']='future-category'
        c=classify_reconciled_document(d)['regions'][0]['classification']
        self.assertEqual(c['retained_classification']['category'],'future-category')
        self.assertIn('other',c['category']['candidates'])
        self.assertTrue(c['requires_human_validation'])

    def test_external_evidence_conflicts_but_is_not_classified(self):
        d=fixture([region(native='image_body'),region('t','table',parser='table_transformer')])
        d['pages'][0]['records'][0]['category']='Figuras';d['pages'][0]['records'][1]['category']='Tablas'
        out=classify_reconciled_document(d)
        self.assertEqual(len(out['regions']),1)
        self.assertIsNone(out['regions'][0]['classification']['category']['value'])
        self.assertIn('t',out['regions'][0]['classification']['evidence_refs'])
        self.assertNotIn('classification',out['evidence_records'][0])

    def test_failed_external_parser_does_not_vote(self):
        d=fixture([region(native='image_body'),region('t','table',parser='table_transformer')])
        d['pages'][0]['records'][0]['category']='Figuras'; d['pages'][0]['records'][1]['category']='Tablas'
        d['pages'][0]['parsers']['table_transformer']='failed'
        c=classify_reconciled_document(d)['regions'][0]['classification']
        self.assertEqual(c['category']['value'],'figure')

    def test_failed_selected_source_does_not_influence_eligible_neighbor(self):
        d=fixture([region(),region('t','table',parser='table_transformer')],objects=['a','t'])
        d['pages'][0]['records'][1]['category']='Tablas'
        d['pages'][0]['parsers']['table_transformer']='failed'
        out=classify_reconciled_document(d)
        self.assertEqual(next(r for r in out['regions'] if r['id']=='a')['classification']['category']['value'],'text')

    def test_abstained_group_not_promoted(self):
        d=fixture([region('f','image_body',''),region('cap','image_caption','')],objects=['f','cap'],groups=[dict(id='g',members=['f'],caption='cap',status='abstained',anchors=[],warnings=[])])
        d['pages'][0]['records'][0]['category']='Figuras';d['pages'][0]['records'][1]['category']='Captions'
        c=classify_reconciled_document(d)['logical_units'][0]['classification']
        self.assertEqual(c['category']['status'],'abstained')
        self.assertEqual(c['function']['status'],'abstained')

    def test_external_text_coarse_support(self):
        d=fixture([region(native='image_caption'),region('lm','text',parser='layoutlmv3')])
        d['pages'][0]['records'][0]['category']='Captions'
        c=classify_reconciled_document(d)['regions'][0]['classification']
        self.assertEqual(c['category']['value'],'caption')

    def test_external_neighbors_do_not_trigger_geometry_nlp(self):
        d=fixture([region(text='Figure 1. Results',box=[100,620,450,660]),region('f','image_body','',box=[100,200,450,600],parser='layoutlmv3')])
        c=classify_reconciled_document(d)['regions'][0]['classification']
        self.assertNotIn('caption_geometry_lexical-v1',c['rule_refs'])

    def test_group_and_caption_relation_used_without_new_boxes(self):
        recs=[region('f1','image_body',''),region('f2','image_body',''),region('cap',text='Description')]
        group=dict(id='g',members=['f1','f2'],caption='cap',anchors=[],status='automatic_rule',warnings=['member_overlap'])
        d=fixture(recs,objects=['f1','f2','cap'],groups=[group])
        for r in d['pages'][0]['records'][:2]:r['category']='Figuras'
        d['pages'][0]['relations']=[dict(type='has_caption',parent='g',child='cap',status='automatic_rule')]
        out=classify_reconciled_document(d)
        self.assertEqual(len(out['logical_units']),1)
        g=out['logical_units'][0]
        self.assertEqual(g['original_group'],group)
        self.assertNotIn('bbox_xyxy',g)
        self.assertEqual(g['classification']['category']['value'],'figure')
        cap=next(r for r in out['regions'] if r['id']=='cap')
        self.assertEqual(cap['classification']['function']['value'],'associated_content')
        self.assertEqual(out['pages'][0]['original_relations'],d['pages'][0]['relations'])
        self.assertEqual(out['pages'][0]['original_decisions'],d['pages'][0]['decisions'])

    def test_null_bbox_child_and_page_abstention_retained(self):
        d=fixture([region(),region('parent','index')],objects=['a'],containers=['parent'])
        d['pages'][0]['records'][0].update(bbox=None,parent='parent')
        d['pages'][0]['records'][1]['role']='container'
        d['pages'][0].update(status='partial',incidents=['invalid_geometry'])
        out=classify_reconciled_document(d)
        self.assertEqual(len(out['regions']),2)
        self.assertTrue(all(r['classification']['function']['status']=='abstained' for r in out['regions']))
        self.assertIsNone(next(r for r in out['regions'] if r['id']=='a')['bbox_xyxy'])

    def test_missing_or_repeated_selection_rejected(self):
        for refs in (['missing'],['a','a']):
            with self.assertRaises(ValueError):classify_reconciled_document(fixture([region()],objects=refs))

    def test_export_counts_only_reconciled_units_and_preserves_evidence(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp); src=root/'input';src.mkdir()
            native=root/'native.json';native.write_text('{}')
            d=fixture([region(),region('alternative',parser='layoutlmv3')])
            for r in d['pages'][0]['records']:
                r['source']=dict(path=str(native),sha256=hashlib.sha256(native.read_bytes()).hexdigest(),pointer='/0')
            (src/'document.json').write_text(json.dumps(d),encoding='utf-8')
            (src/'summary.json').write_text(json.dumps(dict(documents=[dict(paper=12,data='document.json')])) )
            summary=export_collection(src,root/'out')
            self.assertEqual(summary['classified_regions'],1)
            self.assertEqual(summary['parser_evidence_records'],1)
            exported=json.loads((root/'out/papers/12/document.json').read_text(encoding='utf-8'))
            self.assertEqual([r['id'] for r in exported['regions']],['a'])
            with self.assertRaises(FileExistsError):export_collection(src,root/'out')


if __name__=='__main__':unittest.main()
