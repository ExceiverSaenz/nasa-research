"""Offline acceptance tests for the approved single-page reconciliation."""
import copy
import json
from pathlib import Path
import unittest

from page_integration.reconciliation import build, validate, ROOT, PREPARED, ASSOCIATIONS, TABLE2, export
import tempfile


class ReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepared=json.loads((ROOT/PREPARED).read_bytes())
        cls.associations=json.loads((ROOT/ASSOCIATIONS).read_bytes())
        cls.table2=json.loads((ROOT/TABLE2).read_bytes())

    def result(self):
        return build(self.prepared,self.associations,self.table2)

    def test_all_sources_and_native_hierarchy_preserved(self):
        r=self.result()
        self.assertEqual(len(r['sources']),48)
        self.assertEqual([s['record'] for s in r['sources']],sorted(self.prepared['detections'],key=lambda d:(d['model'],str(d['source_region_id']))))
        self.assertEqual(r['native_relations'],self.prepared['relations'])
        self.assertEqual(len(r['regions']),19)
        self.assertEqual(len(r['containers']),4)
        validate(r)

    def test_selected_geometry_is_exact_mineru_not_union(self):
        r=self.result();sources={s['key']:s['record'] for s in r['sources']}
        for region in r['regions']:
            self.assertEqual(region['bbox'],sources[region['geometry_source']]['bbox_xyxy_px'])
            self.assertEqual(sources[region['geometry_source']]['model'],'mineru')
        for body in ('p0-b2-c1','p0-b4-c1'):
            region=next(x for x in r['regions'] if x['id']==body)
            self.assertEqual(region['boundary_status'],'unresolved')
            self.assertTrue(any(a['model']=='table_transformer' for a in region['alternatives']))

    def test_mixed_scope_is_evidence_not_duplicate_output(self):
        r=self.result()
        self.assertEqual(len({x['geometry_source'] for x in r['regions']}),19)
        mixed=[x for x in r['candidate_links'] if x['role']=='mixed_scope_candidate']
        self.assertTrue(mixed)
        self.assertTrue(all(x['decision']=='retain_mixed_evidence_do_not_split' for x in mixed))

    def test_lm_label_support_and_list_ambiguity_survive(self):
        r=self.result()
        labels=[x for x in r['candidate_links'] if x['role']=='caption_label_component']
        self.assertEqual(len(labels),2)
        self.assertTrue(all(x['status']=='pending' for x in labels))
        case=next(x for x in r['decisions'] if x['case_id']=='A02-11')
        self.assertEqual(case['status'],'unresolved_granularity')
        self.assertIn('r12',r['warnings']['list_continuity'])

    def test_table_statuses_immutable(self):
        r=self.result()
        self.assertFalse(r['tables']['p0-b2']['label_recovered'])
        self.assertFalse(r['tables']['p0-b2']['links_verified'])
        self.assertEqual(r['tables']['p0-b2']['status'],'pending_warning')
        self.assertEqual(r['tables']['p0-b4']['accepted_evidence'],self.table2)
        self.assertTrue(r['tables']['p0-b4']['links_verified'])
        label=r['recovered_components'][0]
        self.assertEqual(label['parent'],'p0-b4')
        self.assertEqual(label['bbox'],self.table2['proposal']['selected_candidate']['label_line']['bbox'])
        self.assertEqual(label['text_assignment'],'verified_by_existing_agent_visual_review')

    def test_export_native_content_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'analytics/results/sic12_page3/reconciliation-v1') as folder:
            output=Path(folder)/'new'
            r=export(output)
            for region in r['regions']:
                content=region['native_content_evidence']
                self.assertEqual(content['member'],'page/middle-native.json')
                self.assertTrue(content['pointer'].startswith('/pages/0/blocks/'))
                self.assertIn('content',content['record'])
            self.assertTrue((output/'review.html').exists())
            self.assertTrue((output/'manifest.json').exists())
            with self.assertRaises(FileExistsError):export(output)

    def test_order_and_score_do_not_choose_winner(self):
        baseline=self.result()
        p=copy.deepcopy(self.prepared);p['detections'].reverse()
        a=copy.deepcopy(self.associations);a['associations'].reverse()
        for c in a['associations']:c['members'].reverse()
        self.assertEqual(build(p,a,self.table2),baseline)
        for d in p['detections']:
            if d['model']=='layoutlmv3':d['score']=1.0
        result=build(p,a,self.table2)
        self.assertEqual(result['regions'],baseline['regions'])

    def test_no_missing_or_foreign_reference(self):
        p=copy.deepcopy(self.prepared);p['detections'].pop()
        with self.assertRaises(ValueError):build(p,self.associations,self.table2)
        p=copy.deepcopy(self.prepared);p['detections'][0]['render_sha256']='wrong'
        with self.assertRaises(ValueError):build(p,self.associations,self.table2)

    def test_unknown_duplicate_and_cycle_rejected(self):
        p=copy.deepcopy(self.prepared);p['detections'].append(p['detections'][0])
        with self.assertRaises(ValueError):build(p,self.associations,self.table2)
        r=self.result();r['relations'].append(dict(parent='p0-b2-c1',child='p0-b2',type='parent_child'))
        with self.assertRaises(ValueError):validate(r)
        r=self.result();r['regions'][0]['geometry_source']='unknown'
        with self.assertRaises(ValueError):validate(r)

    def test_geometry_tampering_and_table_swap_rejected(self):
        r=self.result();r['regions'][0]['bbox'][0]+=1
        with self.assertRaises(ValueError):validate(r)
        t=copy.deepcopy(self.table2);t['proposal']['object_id']='p0-b2'
        with self.assertRaises(ValueError):build(self.prepared,self.associations,t)
        t=copy.deepcopy(self.table2);t['tolerances']['iou_min']=.1
        with self.assertRaises(ValueError):build(self.prepared,self.associations,t)


if __name__=='__main__':unittest.main()
