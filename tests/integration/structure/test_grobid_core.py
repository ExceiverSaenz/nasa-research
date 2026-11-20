"""Synthetic TEI is test data, never a simulated result for the real paper."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from .test_native_structure import native
from tests.integration.reading_order.test_engine import unit,doc
from integration.reading_order.engine import order_document
from integration.structure.structure import integrate
from integration.structure.grobid_adapter import parse_tei
from integration.structure.grobid_align import align_tei
from integration.structure.grobid_reconcile import integrate_grobid,load_mapping
from integration.structure.grobid_evaluation import compare_B_C,validate_C


def baseline(rows=None):
    rows=rows or [unit('a',[100,100,450,150],text='Alpha beta')]
    old=order_document(doc(rows));native_rows=[r for r in rows if r.get('bbox_xyxy')];n=native([(r['original_record']['text'],r['bbox_xyxy']) for r in native_rows])
    for e,r in zip(n['evidence'],native_rows):e['page']=r['page']
    n['pages']=[dict(page=p,width_pt=1000,height_pt=1000,rotation=0) for p in sorted({r['page'] for r in rows})]
    return integrate(old,n)


def tei(body='<p coords="1,100,100,350,50">Alpha beta</p>',header='',surfaces=None):
    surfaces=surfaces or '<surface n="1" ulx="0" uly="0" lrx="1000" lry="1000"/>'
    return ('<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader>'+header+'</teiHeader><facsimile>'+surfaces+'</facsimile><text><body>'+body+'</body></text></TEI>').encode()


def evidence(raw=None):return parse_tei(raw or tei(),dict(run_id='fixture',pdf_sha256='fixture',models_ref='models-fixture',config_ref='config-fixture'))


class AdapterTests(unittest.TestCase):
    def test_namespace_paths_raw_and_stable_ids(self):
        raw=tei();e=evidence(raw);self.assertEqual(e,evidence(raw));self.assertEqual(e['nodes'][0]['tag'],'p')
        self.assertIn('{http://www.tei-c.org/ns/1.0}',e['nodes'][0]['xpath']);self.assertEqual(e['nodes'][0]['text'],'Alpha beta');self.assertEqual(e['nodes'][0]['coords'][0]['bbox'],[100,100,450,150])
    def test_rejects_dtd_encoding_and_invalid_xml(self):
        for raw in [b'<!DOCTYPE TEI [<!ENTITY x "bad">]><TEI/>','<!DOCTYPE TEI><TEI/>'.encode('utf-16'),b'<TEI>']:
            with self.assertRaises(ValueError):evidence(raw)
    def test_multiple_boxes_and_unknown_nodes_accounted(self):
        e=evidence(tei('<p coords="1,100,100,100,50;1,300,100,100,50">Alpha beta</p><weird>retained</weird>'))
        self.assertEqual(len(e['nodes'][0]['coords']),2);self.assertTrue(any(n['tag']=='weird' for n in e['unmapped_nodes']))
    def test_bad_coordinates_are_not_clipped(self):
        e=evidence(tei('<p coords="1,-10,10,50,50">Alpha beta</p>'));self.assertEqual(align_tei(e,baseline())[0]['status'],'unusable_geometry')


class AlignmentTests(unittest.TestCase):
    def test_multipage_paragraph_keeps_fragments_and_candidate_continuity(self):
        rows=[unit('a',[100,100,450,150],text='Alpha'),unit('b',[100,100,450,150],text='beta')];rows[1]['page']=2;b=baseline(rows)
        e=evidence(tei('<p coords="1,100,100,350,50;2,100,100,350,50">Alpha beta</p>',surfaces='<surface n="1" lrx="1000" lry="1000"/><surface n="2" lrx="1000" lry="1000"/>'))
        links=align_tei(e,b);self.assertEqual(links[0]['status'],'aligned_fragment_set')
        c=integrate_grobid(b,e,links,load_mapping());self.assertEqual(len(c['grobid_structure']['continuity_candidates']),1);self.assertFalse(c['grobid_structure']['continuity_candidates'][0]['applied']);validate_C(b,c)
    def test_only_spans_participating_in_exact_occurrence(self):
        b=baseline([unit('extra',[100,100,450,150],text='Alpha'),unit('actual',[100,200,450,250],text='Alpha beta')])
        a=align_tei(evidence(tei('<p coords="1,100,100,350,150">Alpha beta</p>')),b)[0]
        self.assertEqual([m['unit_ref'] for m in a['matches']],['actual'])
    def test_exact_and_partial_fragment(self):
        b=baseline();a=align_tei(evidence(),b)[0];self.assertEqual(a['status'],'aligned_unique');self.assertEqual(a['matches'][0]['scope'],'whole_region')
        a=align_tei(evidence(tei('<p coords="1,100,100,350,50">Alpha</p>')),b)[0]
        self.assertEqual(a['status'],'aligned_unique');self.assertEqual(a['matches'][0]['scope'],'fragment')
    def test_no_coordinates_exact_unique_or_repeated(self):
        e=evidence(tei('<p>Alpha beta</p>'));self.assertEqual(align_tei(e,baseline())[0]['status'],'aligned_unique')
        b=baseline([unit('a',[100,100,450,150],text='Alpha beta'),unit('b',[550,100,900,150],text='Alpha beta')]);self.assertEqual(align_tei(e,b)[0]['status'],'ambiguous_alignment')
    def test_fragment_set_and_missing_coordinates(self):
        b=baseline([unit('a',[100,100,450,150],text='Alpha'),unit('b',[550,100,900,150],text='beta')])
        e=evidence(tei('<p coords="1,100,100,350,50;1,550,100,350,50">Alpha beta</p>'))
        a=align_tei(e,b)[0];self.assertEqual(a['status'],'aligned_fragment_set');self.assertEqual({m['unit_ref'] for m in a['matches']},{'a','b'})
        self.assertEqual(align_tei(evidence(tei('<p>Missing</p>')),b)[0]['status'],'unlocated')
    def test_fuzzy_remains_candidate_and_rotation_abstains(self):
        b=baseline();e=evidence(tei('<p coords="1,100,100,350,50">Alpha gamma</p>'))
        self.assertNotIn(align_tei(e,b)[0]['status'],('aligned_unique','aligned_fragment_set'))
        b['native_pages'][0]['rotation']=90;self.assertEqual(align_tei(e,b)[0]['status'],'unusable_geometry')
    def test_deferred_child_never_gets_location(self):
        b=baseline([unit('p',[100,100,450,150],text='Alpha beta',kind='container',native='index'),unit('c',None,text='Alpha beta',parent='p')]);a=align_tei(evidence(),b)[0]
        self.assertFalse(any(m['unit_ref']=='c' for m in a['matches']));self.assertEqual(b['inventory'][1]['original_unit']['bbox_xyxy'],None)


class ReconciliationTests(unittest.TestCase):
    def test_header_source_description_is_article_not_citation(self):
        h='<fileDesc><sourceDesc><biblStruct><analytic><title coords="1,100,100,350,50">Alpha beta</title><author><persName coords="1,100,100,350,50">Alpha beta</persName></author></analytic></biblStruct></sourceDesc></fileDesc>'
        b,c=self.result(raw=tei(body='',header=h));claims=c['grobid_proposals'][0]['dimensions']['document_role']['grobid_claims'];values={x['value'] for x in claims}
        self.assertIn('article_title',values);self.assertIn('authorship',values);self.assertFalse(values & {'cited_author','reference_title','bibliographic_entry'})
    def result(self,b=None,raw=None):
        b=b or baseline();e=evidence(raw);return b,integrate_grobid(b,e,align_tei(e,b),load_mapping())
    def test_unknown_filled_and_originals_preserved(self):
        b,c=self.result();self.assertEqual(c['inventory'],b['inventory']);self.assertEqual(c['approved_routes'],b['approved_routes']);self.assertEqual(c['classification_proposals'],b['classification_proposals'])
        p=c['grobid_proposals'][0]['dimensions']['document_role'];self.assertEqual(p['C_decision']['operational_proposal'],'body_paragraph');self.assertEqual(p['C_decision']['status'],'model_inferred')
        validate_C(b,c)
    def test_conflict_preserves_direct_B_and_alternatives(self):
        b=baseline();d=b['classification_proposals'][0]['decisions']['document_role'];d.update(operational_proposal='article_title',status='direct_supported',alternatives=['article_title'])
        _,c=self.result(b);d=c['grobid_proposals'][0]['dimensions']['document_role'];self.assertEqual(d['C_decision']['operational_proposal'],'article_title');self.assertEqual(d['C_decision']['status'],'unresolved_conflict');self.assertIn('body_paragraph',d['C_decision']['alternatives'])
    def test_partial_region_does_not_fill_unknown(self):
        b,c=self.result(raw=tei('<p coords="1,100,100,350,50">Alpha</p>'));d=c['grobid_proposals'][0]['dimensions']['document_role'];self.assertIsNone(d['C_decision']['operational_proposal']);self.assertEqual(d['grobid_claims'][0]['scope'],'fragment')
    def test_author_in_reference_and_table_mapping(self):
        for xml,role in [('<biblStruct><persName coords="1,100,100,350,50">Alpha beta</persName></biblStruct>','cited_author'),('<figure type="table" coords="1,100,100,350,50">Alpha beta</figure>','table_object')]:
            b,c=self.result(raw=tei(xml));claims=c['grobid_proposals'][0]['dimensions']['document_role']['grobid_claims'];self.assertIn(role,[x['value'] for x in claims])
    def test_figdesc_caption_is_retained_as_candidate_relation(self):
        b,c=self.result(raw=tei('<figure xml:id="f"><figDesc coords="1,100,100,350,50">Alpha beta</figDesc><graphic/></figure>'))
        self.assertTrue(any(r['type']=='caption_of' for r in c['grobid_structure']['association_candidates']))
        self.assertIn('caption',[x['value'] for x in c['grobid_proposals'][0]['dimensions']['document_role']['grobid_claims']])
    def test_agreement_is_not_independent_confirmation(self):
        b=baseline();b['classification_proposals'][0]['decisions']['document_role']['operational_proposal']='body_paragraph';_,c=self.result(b)
        d=c['grobid_proposals'][0]['dimensions']['document_role']['C_decision'];self.assertEqual(d['status'],'agreement_unvalidated');self.assertIsNone(d['probability']);self.assertFalse(d['independent_confirmation'])
    def test_missing_evidence_retains_B_and_metrics_not_accuracy(self):
        b,c=self.result(raw=tei('<p>Absent content</p>'));self.assertEqual(c['grobid_proposals'][0]['observation'],'not_observed_by_grobid')
        m=compare_B_C(b,c);self.assertIsNone(m['quality']['semantic_accuracy']);self.assertEqual(m['quality']['status'],'not_evaluated');self.assertFalse(m['order_changed'])
    def test_dangling_ref_and_order_mutation_rejected(self):
        b,c=self.result();bad=copy.deepcopy(c);bad['approved_steps']=[]
        with self.assertRaises(ValueError):validate_C(b,bad)
        bad=copy.deepcopy(c);bad['grobid_alignment'][0]['native_span_refs'][0]['pointer']='/data/lines/999/spans/0'
        with self.assertRaises(ValueError):validate_C(b,bad)
        bad=copy.deepcopy(c);bad['grobid_alignment'][0]['evidence_ref']='absent'
        with self.assertRaises(ValueError):validate_C(b,bad)
    def test_incompatible_model_values_abstain(self):
        b,c=self.result(raw=tei('<p coords="1,100,100,350,50">Alpha beta</p><head coords="1,100,100,350,50">Alpha beta</head>'))
        self.assertIsNone(c['grobid_proposals'][0]['dimensions']['document_role']['C_decision']['operational_proposal'])
    def test_crop_mismatch_abstains(self):
        b=baseline();b['native_pages'][0].update(crop_box=[10,10,1010,1010],media_box=[0,0,1100,1100])
        self.assertEqual(align_tei(evidence(),b)[0]['status'],'unusable_geometry')


if __name__=='__main__':unittest.main()
