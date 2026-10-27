"""Offline tests only: no OCR imports, model loading or network calls."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from page_integration.localized_labels import select_rois, original_box, associate, geometry_acceptance


def region(rid, kind, box, parent=None):
    return dict(region_id=rid, native_label=kind, bbox=box, parent_id=parent,
                source_pointer='/blocks/'+rid)


def fixture():
    return [region('header','header',[10,5,190,15]),
            region('t','table',[10,50,190,100]),
            region('c','table_caption',[10,30,150,40],'t'),
            region('b','table_body',[10,50,190,100],'t')]


class GeometryTests(unittest.TestCase):
    def test_roi_uses_preceding_barrier_and_whole_body_without_mutation(self):
        data=fixture(); before=copy.deepcopy(data)
        roi=select_rois(data,200,200)[0]
        self.assertEqual(roi['bbox'],[10,15,190,100])
        self.assertEqual(roi['barrier_ids'],['header'])
        self.assertEqual(data,before)

    def test_mixed_region_crossing_caption_marks_roi_ambiguous(self):
        data=fixture()+[region('mixed','text',[10,20,190,45])]
        self.assertEqual(select_rois(data,200,200)[0]['status'],'roi_ambiguous')

    def test_normalized_inverse_is_crop_then_translation(self):
        self.assertEqual(original_box([.1,.2,.5,.6],[100,200,300,400]),[120,240,200,320])
        for box in ([10,20,30,40],[0,0,0,.1],[0,0,float('nan'),1]):
            with self.assertRaises(ValueError): original_box(box,[100,200,300,400])

    def test_geometry_tolerance_rejects_wrong_location_and_oversized_box(self):
        self.assertTrue(geometry_acceptance([8,8,72,32],[10,10,70,30])['passed'])
        # The approved expanded-reference rule is strict even for identical tight boxes.
        self.assertFalse(geometry_acceptance([10,10,70,30],[10,10,70,30])['passed'])
        self.assertFalse(geometry_acceptance([100,100,160,120],[10,10,70,30])['passed'])
        self.assertFalse(geometry_acceptance([0,0,200,200],[10,10,70,30])['passed'])


class AssociationTests(unittest.TestCase):
    def target(self):
        return dict(object_id='t', caption_id='c', body_id='b', description='Properties of material.',
                    caption_bbox=[10,30,150,40],body_bbox=[10,50,190,100])

    def text(self,text,box,pointer):
        return dict(text=text,bbox=box,source_pointer=pointer,source_member='middle-native.json',
                    source_sha256='a'*64,roi_id='t')

    def test_links_separate_label_and_description_with_provenance(self):
        texts=[self.text('TABLE\n1',[10,20,60,28],'/l'),
               self.text('Properties of material.',[10,30,150,40],'/d')]
        result=associate([self.target()],texts)[0]
        self.assertEqual(result['state'],'both_linked')
        self.assertEqual(result['selected_label']['text'],'TABLE\n1')
        self.assertEqual(result['selected_label']['source_pointer'],'/l')
        self.assertFalse(result['links_verified'])

    def test_duplicate_candidates_remain_ambiguous(self):
        texts=[self.text('Table 1',[10,20,60,28],'/l'),self.text('Table1',[10,20,60,28],'/l2'),
               self.text('Properties of material.',[10,30,150,40],'/d')]
        r=associate([self.target()],texts)[0]
        self.assertEqual(r['state'],'ambiguous');self.assertEqual(len(r['candidates']),2)

    def test_wrong_description_or_body_reference_never_links(self):
        for text,box in [('Table 1',[10,20,60,28]),('shown in Table 1.',[10,60,150,70])]:
            r=associate([self.target()],[self.text(text,box,'/l'),self.text('Other caption',[10,30,150,40],'/d')])[0]
            self.assertNotEqual(r['state'],'both_linked')

    def test_intervening_text_or_other_column_rejects_candidate(self):
        desc=self.text('Properties of material.',[10,30,150,40],'/d')
        for label,extra in [(self.text('Table 1',[160,20,190,28],'/l'),[]),
                            (self.text('Table 1',[10,16,60,20],'/l'),[self.text('unrelated',[10,22,90,26],'/x')])]:
            self.assertNotEqual(associate([self.target()],[label,desc]+extra)[0]['state'],'both_linked')

    def test_shared_candidate_across_targets_is_ambiguous(self):
        t=self.target();t2=dict(t,object_id='other')
        texts=[self.text('Table 1',[10,20,60,28],'/l'),self.text(t['description'],[10,30,150,40],'/d')]
        self.assertTrue(all(x['state']=='ambiguous' for x in associate([t,t2],texts)))

    def test_candidate_competing_with_already_ambiguous_target_is_not_selected_elsewhere(self):
        t=self.target();t2=dict(t,object_id='other',caption_bbox=[10,30,50,40])
        texts=[self.text('Table 1',[10,20,40,28],'/a'),
               self.text('Table 2',[100,20,140,28],'/b'),
               self.text(t['description'],[10,30,150,40],'/d')]
        self.assertTrue(all(x['state']=='ambiguous' for x in associate([t,t2],texts)))


if __name__=='__main__':unittest.main()
