import copy
import unittest
from tests.integration.reading_order.test_engine import unit,doc,group
from integration.reading_order.engine import order_document
from tests.integration.structure.test_native_structure import native
from integration.structure.structure import integrate
from integration.operational.structure import build_structure


def fixture(rows,groups=None,outlines=None):
    order=order_document(doc(rows,groups));n=native([(r['original_record']['text'],r['bbox_xyxy']) for r in rows if r.get('bbox_xyxy')],outlines)
    return order,integrate(order,n),n


class StructureTests(unittest.TestCase):
    def test_numbering_hierarchy_without_named_sections(self):
        o,a,n=fixture([unit('h',[100,100,450,140],text='7. Unusual heading',cat='title'),unit('s',[100,200,450,240],text='7.2. Another topic',cat='title'),unit('p',[100,260,450,340],text='Some body.')])
        old=copy.deepcopy(o);s,sem=build_structure(o,a,n);by={x['heading_ref']:x for x in s['sections'] if x['heading_ref']}
        self.assertEqual(by['s']['parent_ref'],by['h']['id']);self.assertEqual(by['s']['level'],2);self.assertEqual(o,old)
    def test_unknown_heading_level_and_ambiguous_repeated_marker(self):
        o,a,n=fixture([unit('h',[100,100,450,140],text='Discussion',cat='title'),unit('x',[100,200,450,240],text='2. Same',cat='title'),unit('y',[100,300,450,340],text='2. Repeated',cat='title')]);s,_=build_structure(o,a,n)
        self.assertIsNone(s['sections'][0]['level']);self.assertTrue(any(x['status']=='ambiguous_numbering' for x in s['sections']))
    def test_numbered_body_is_not_heading_without_other_support(self):
        o,a,n=fixture([unit('p',[100,100,450,170],text='1. This is an ordinary enumerated item.')]);s,_=build_structure(o,a,n);self.assertEqual(s['sections'],[])
    def test_all_units_have_membership_and_visual_theme_separate(self):
        rows=[unit('h',[100,100,450,140],text='1. Start',cat='title'),unit('f',[100,200,450,500],cat='figure',fn='associated_content'),unit('c',[100,510,450,550],text='A caption.',cat='caption',fn='associated_content')]
        o,a,n=fixture(rows,[group('g',['f'],'c')]);s,_=build_structure(o,a,n)
        self.assertEqual(len(s['memberships']),len(o['inventory']));self.assertEqual(next(x for x in s['memberships'] if x['unit_ref']=='f')['thematic_section_candidates'],[])


if __name__=='__main__':unittest.main()
