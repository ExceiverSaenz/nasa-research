"""Offline tests for proposed line allocation; no text is attributed to lines as OCR fact."""
import copy
from pathlib import Path
import sys
import unittest
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from page_integration.localized_labels import compare_uo2, propose_caption_lines, verify_line_review
from page_integration.workflow import evaluate_table2_lines


class EquivalenceTests(unittest.TestCase):
    def test_only_explicit_equivalence_is_accepted_and_recorded(self):
        result=compare_uo2(r'Material properties for \mathrm{UO}_{2}.','Material properties for UO2.')
        self.assertTrue(result['equal']);self.assertEqual(result['applied_rules'],['latex_mathrm_UO_subscript_2'])
        self.assertEqual(result['left_literal'],r'Material properties for \mathrm{UO}_{2}.')
        for text in [r'Material properties for \mathrm{UO}_{3}.','Material properties for UO20.',
                     'Other properties for UO2.',r'Material properties for \text{UO}_{2}.',
                     r'Material properties for \mathrm{UO}_{2}']:
            self.assertFalse(compare_uo2(text,'Material properties for UO2.')['equal'])


class LineTests(unittest.TestCase):
    def target(self):
        return dict(object_id='p0-b4',caption_id='p0-b4-c0',body_id='p0-b4-c1',
                    description='Material properties for UO2.',caption_bbox=[10,50,100,70],body_bbox=[10,80,190,190],status='ready')

    def evidence(self):
        return dict(text=r'Table 2 Material properties for \mathrm{UO}_{2}.',
                    bbox=[10,20,100,70],source_pointer='/pages/0/0',source_member='model-native.json',
                    source_sha256='a'*64,roi_id='p0-b4',fragments=[{'text':r'Table 2 Material properties for \mathrm{UO}_{2}.','source_pointer':'/pages/0/0/content/0/content'}],
                    native_type='caption',lines=[{'bbox':[.05,.1,.3,.2]},{'bbox':[.05,.25,.5,.35]}])

    def test_two_lines_form_only_a_proposal_preserving_block_and_text(self):
        evidence=self.evidence();before=copy.deepcopy(evidence)
        result=propose_caption_lines(self.target(),[evidence],[0,0,200,200])
        self.assertEqual(result['status'],'proposed_pending_visual_review')
        c=result['candidates'][0]
        self.assertEqual(c['label_line']['bbox'],[10,20,60,40])
        self.assertEqual(c['label_line']['source_pointer'],'/pages/0/0/lines/0/bbox')
        self.assertEqual(c['original_block_bbox'],[10,20,100,70])
        self.assertFalse(result['links_verified']);self.assertEqual(evidence,before)

    def test_extra_overlap_reverse_missing_lines_or_wrong_caption_stays_ambiguous(self):
        for mutate in [lambda e:e['lines'].append({'bbox':[.1,.4,.2,.5]}),
                       lambda e:e['lines'].__setitem__(1,{'bbox':[.05,.15,.5,.35]}),
                       lambda e:e['lines'].reverse(),lambda e:e.pop('lines'),
                       lambda e:e.update(text='Table 2 Other description.'),
                       lambda e:e.update(text='Shown in Table 2 Material properties for UO2.'),
                       lambda e:e.update(native_type='text'),lambda e:e.update(roi_id='p0-b2')]:
            e=self.evidence();mutate(e)
            self.assertNotEqual(propose_caption_lines(self.target(),[e],[0,0,200,200])['status'],'proposed_pending_visual_review')

    def test_two_eligible_blocks_remain_ambiguous(self):
        e=self.evidence();other=copy.deepcopy(e);other['source_pointer']='/pages/0/1'
        r=propose_caption_lines(self.target(),[e,other],[0,0,200,200])
        self.assertEqual(r['status'],'ambiguous');self.assertEqual(len(r['candidates']),2)

    def test_wrong_column_or_intervening_block_is_rejected(self):
        e=self.evidence();e['lines'][0]['bbox']=[.7,.1,.9,.2]
        self.assertNotEqual(propose_caption_lines(self.target(),[e],[0,0,200,200])['status'],'proposed_pending_visual_review')
        e=self.evidence();extra=dict(e,text='Other text',bbox=[10,41,100,49],source_pointer='/pages/0/1',native_type='text')
        self.assertNotEqual(propose_caption_lines(self.target(),[e,extra],[0,0,200,200])['status'],'proposed_pending_visual_review')

    def test_geometry_alone_cannot_mark_link_verified_or_accept_other_source(self):
        r=propose_caption_lines(self.target(),[self.evidence()],[0,0,200,200]);c=r['candidates'][0]
        review=dict(method='visual',reviewer='test fixture',result_archive_sha256='b'*64,
                    candidate_source_sha256='a'*64,candidate_source_member='model-native.json',candidate_source_pointer='/pages/0/0',
                    object_id='p0-b4',label_line_pointer=c['label_line']['source_pointer'],
                    description_line_pointer=c['description_line']['source_pointer'],
                    label_line_contains_label=True,description_line_contains_description=True,correct_table=True)
        self.assertTrue(verify_line_review(c,review,'b'*64))
        self.assertFalse(verify_line_review(c,None,'b'*64))
        for key,value in [('candidate_source_sha256','c'*64),('correct_table',False),('correct_table',1),
                          ('object_id','p0-b2'),('reviewer',''),('reviewer',None)]:
            wrong=dict(review);wrong[key]=value
            self.assertFalse(verify_line_review(c,wrong,'b'*64))


class ExistingZipTests(unittest.TestCase):
    def test_existing_zip_proposes_correct_box_but_requires_separate_visual_review(self):
        from page_integration.workflow import ROOT,file_hash
        prep=ROOT/'code/packages/localized-labels-v1'
        archive=ROOT/'code/results/localized-labels-v1/20261024T221741Z/result.zip'
        before=file_hash(archive)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            r=evaluate_table2_lines(prep,archive,Path(temp)/'pending')
            self.assertTrue(r['automatic_acceptance_passed']);self.assertFalse(r['links_verified'])
            self.assertEqual(r['scope'],['p0-b4'])
            c=r['proposal']['selected_candidate']
            for got,want in zip(c['label_line']['bbox'],[114.824,1158.92,184.012,1177.82]):self.assertAlmostEqual(got,want,places=6)
            self.assertAlmostEqual(r['label_geometry']['iou'],.6637845569452254)
            self.assertAlmostEqual(r['label_geometry']['expanded_reference_coverage'],.99)
            self.assertEqual(r['unchanged_table1']['object_id'],'p0-b2')
            review=dict(method='visual',reviewer='synthetic test review only',result_archive_sha256=before,
                candidate_source_sha256=c['source_sha256'],candidate_source_member=c['source_member'],
                candidate_source_pointer=c['source_pointer'],object_id='p0-b4',
                label_line_pointer=c['label_line']['source_pointer'],description_line_pointer=c['description_line']['source_pointer'],
                label_line_contains_label=True,description_line_contains_description=True,correct_table=True)
            accepted=evaluate_table2_lines(prep,archive,Path(temp)/'reviewed',review)
            self.assertTrue(accepted['links_verified']);self.assertEqual(accepted['visual_review'],review)
            with self.assertRaises(FileExistsError):evaluate_table2_lines(prep,archive,Path(temp)/'reviewed',review)
        self.assertEqual(file_hash(archive),before)


if __name__=='__main__':unittest.main()
