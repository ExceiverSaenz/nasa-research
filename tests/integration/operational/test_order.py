import copy
import unittest
from tests.integration.reading_order.test_engine import unit,group
from .test_structure import fixture
from integration.operational.structure import build_structure
from integration.operational.order import connect_order


class OrderTests(unittest.TestCase):
    def test_local_geometry_corrects_same_column_inversion(self):
        o,a,n=fixture([unit('a',[100,100,450,200],text='First.'),unit('b',[100,198,450,300],text='Second.')]);r=o['routes']['main'];r['sequence']=list(reversed(r['sequence']));r['expanded_sequence']=r['sequence'][:]
        s,sem=build_structure(o,a,n);result=connect_order(o,s,sem,n)
        by={x['id']:x for x in result['steps']};ids=[by[x]['unit_ref'] for x in result['routes']['main']['expanded_sequence'] if by[x]['kind']=='content'];self.assertEqual(ids,['a','b']);self.assertEqual(result['inventory'],o['inventory'])
    def test_capsule_caption_first_and_shared_reference_preserved(self):
        o,a,n=fixture([unit('f',[100,200,450,450],cat='figure',fn='associated_content'),unit('c',[100,460,450,500],text='Caption',cat='caption',fn='associated_content')],[group('g',['f'],'c')]);s,sem=build_structure(o,a,n);old=copy.deepcopy(o);result=connect_order(o,s,sem,n)
        self.assertEqual(result['inventory'],old['inventory']);self.assertEqual({x['id']:x['children'] for x in result['steps']},{x['id']:x['children'] for x in old['steps']})
    def test_blocked_page_is_not_reordered(self):
        o,a,n=fixture([unit('a',[100,100,450,200]),unit('b',[100,300,450,400])]);o['original_page_context'][0]['original_incidents']=['invalid_geometry'];s,sem=build_structure(o,a,n);result=connect_order(o,s,sem,n);self.assertEqual(result['routes'],o['routes'])
    def test_metadata_moves_only_whole_capsule(self):
        o,a,n=fixture([unit('h',[100,300,450,340],text='1. Start',cat='title'),unit('title',[100,100,450,150],text='Article',cat='title')]);s,sem=build_structure(o,a,n)
        for x in sem:
            if x['unit_ref']=='title':x['flow']='front_matter';x['routing_eligible']=True
        result=connect_order(o,s,sem,n);self.assertTrue(result['routes']['metadata']['sequence']);self.assertEqual(len(result['steps']),len(o['steps']))


if __name__=='__main__':unittest.main()
