import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from document_trial.common import ROOT, freeze_versions, check_runtime, validate_bundle, save
from document_trial.offline import reconcile, review_template, compare_reference
from document_trial.finalize import aggregate


class TrialTests(unittest.TestCase):
    def test_freeze_keeps_direct_wheels_and_editable_version(self):
        f='# Editable install with no version control (layoutlmv3==0.1)\n-e /content/nasa-layoutlm/layoutlmv3\ntorch @ https://x/torch.whl\nPillow==9.5.0\n'
        self.assertEqual(freeze_versions(f,{'torch':'1.10.0+cu111'}),{'layoutlmv3':'0.1','torch':'1.10.0+cu111','pillow':'9.5.0'})

    def test_wrong_runtime_stops_before_model(self):
        spec=dict(python='3.9.25',packages={'torch':'1.10.0+cu111'},cuda='11.1')
        obs=dict(python='3.9.25',packages={'torch':'1.10.0+cu111'},cuda='11.1',gpu='Tesla T4')
        check_runtime(obs,spec)
        for k in ('python','cuda','gpu','packages'):
            other=copy.deepcopy(obs);other[k]='wrong'
            with self.assertRaises(ValueError):check_runtime(other,spec)

    def page(self,n=1):return dict(document_sha256='doc',physical_page=n,render_sha256='render'+str(n),width_px=100,height_px=200)
    def native(self):return {'pages':[{'page_idx':0,'blocks':[{'type':'table','bbox':[.1,.1,.9,.5],'content':[
        {'type':'table_caption','bbox':[.1,.1,.9,.2],'content':[{'type':'text','content':'Description.'}]},
        {'type':'table_body','bbox':[.1,.2,.9,.5],'content':'<table></table>'}]}]}]}

    def test_hierarchy_and_all_candidates_kept_without_matching(self):
        alternatives={'table_transformer':[{'query_id':5,'bbox':[10,40,90,100],'score':.99}],
                      'layoutlmv3':[{'region_id':'mixed','bbox':[0,0,100,200],'type':'figure','score':.999}]}
        r=reconcile(self.page(),self.native(),alternatives)
        self.assertEqual(len(r['segments']),2);self.assertEqual(len(r['containers']),1)
        self.assertEqual(len(r['evidence']),2);self.assertEqual(len(r['relations']),2)
        self.assertEqual(r['accepted_external_content'],[])
        self.assertTrue(all(x['status']=='pending_unassociated_evidence' for x in r['evidence']))
        self.assertEqual(r['segments'][0]['native_content'],self.native()['pages'][0]['blocks'][0]['content'][0])

    def test_ids_include_page_and_table1_not_inferred(self):
        a=reconcile(self.page(1),self.native(),{});b=reconcile(self.page(2),self.native(),{})
        self.assertFalse({x['id'] for x in a['segments']}&{x['id'] for x in b['segments']})
        self.assertEqual(a['object_links'][0]['label_status'],'not_determined_requires_visual_reference')
        self.assertFalse(a['object_links'][0]['links_verified'])

    def test_invalid_boxes_and_unknown_children_fail_without_loss(self):
        native=self.native();native['pages'][0]['blocks'][0]['bbox']=[0,0,2,1]
        with self.assertRaises(ValueError):reconcile(self.page(),native,{})
        native=self.native();native['pages'].append(native['pages'][0])
        with self.assertRaises(ValueError):reconcile(self.page(),native,{})

    def test_recurrence_needs_manual_visible_denominator(self):
        template=review_template(self.page(),reconcile(self.page(),self.native(),{}))
        self.assertEqual(template['manual_units'],[])
        self.assertEqual(template['status'],'pending_agent_or_human_visual_inventory')
        self.assertIsNone(template['label_recurrence_rate'])

    def test_reference_compares_bbox_content_and_preserves_historical_acceptance(self):
        a=reconcile(self.page(3),self.native(),{});b=copy.deepcopy(a)
        result=compare_reference(a,b)
        self.assertTrue(result['selected_content_equal'])
        b['segments'][0]['bbox'][0]+=1
        self.assertFalse(compare_reference(a,b)['selected_content_equal'])

    def test_empty_or_partial_reviews_do_not_produce_acceptance(self):
        status={'pages':[{'page':1}]}
        template=review_template(self.page(),reconcile(self.page(),self.native(),{}))
        with self.assertRaises(ValueError):aggregate(status,{1:template})
        with self.assertRaises(ValueError):aggregate(status,{})

    def test_review_counts_have_explicit_denominators_and_attribution(self):
        observed={c:dict(presence='present',classification='correct',separation='correct',geometry='indeterminate',linkage='partial',duplicates='correct') for c in ('M0','M1','R')}
        review=dict(whole_page_inventory_complete=True,reviewer='agent pending human review',manual_units=[dict(id='v1',evidence=['render.png'],conditions=observed)],
            label_cases=[dict(visible=True,evidence=['render.png'],conditions={c:'not_located_in_inspected_fields' for c in observed})],
            changes=[dict(classification='equivalente',attribution='reconciliation',evidence=['native'])])
        x=aggregate({'pages':[{'page':1}]},{1:review})
        self.assertEqual(x['label_recurrence']['R']['visible_denominator'],1)
        self.assertEqual(x['totals']['R']['geometry']['indeterminate'],1)
        self.assertEqual(x['change_ledger'][0]['attribution'],'reconciliation')

    def test_numeric_array_and_boolean_serialization_without_score_imputation(self):
        import numpy as np
        with tempfile.TemporaryDirectory(dir=ROOT/'analytics/results/sic12_document/trial-v1-preparation') as folder:
            p=Path(folder)/'values.json';save(p,dict(raw=np.array([[1,2]]),flag=np.bool_(False),score=None))
            self.assertEqual(json.loads(p.read_bytes()),dict(raw=[[1,2]],flag=False,score=None))

    def test_native_line_and_span_text_is_searchable_without_association(self):
        from document_trial.offline import native_text_fields
        fields=native_text_fields({'pages':[{'lines':[{'spans':[{'text':'TABLE\n1'}]}]}]})
        self.assertEqual(fields,[dict(pointer='/pages/0/lines/0/spans/0/text',literal='TABLE\n1')])


if __name__=='__main__':unittest.main()
