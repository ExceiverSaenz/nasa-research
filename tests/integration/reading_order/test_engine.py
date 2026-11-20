import copy
import unittest
from integration.reading_order.engine import order_document
from integration.reading_order.layout import xy_order


def unit(id, box, text='Some scientific text.', cat='text', fn='main_body', kind='region', native='text', parent=None):
    dim=lambda x:dict(value=x,candidates=[x] if x else [],status='automatic_rule' if x else 'abstained')
    return dict(id=id,page=1,structural_kind=kind,bbox_xyxy=box,original_record=dict(id=id,text=text,native_type=native,parent=parent,bbox=box),classification=dict(category=dim(cat),function=dim(fn),subtype=dim('paragraph_candidate'),warnings=[],semantic_validation='pending_after_full_mvp'))


def doc(rows,groups=None,relations=None,incident=False):
    pages=[]
    for n in sorted({r['page'] for r in rows}):
        pages.append(dict(identity=dict(physical_page=n,width_px=1000,height_px=1000),original_status='partial' if incident else 'completed',original_incidents=['invalid_geometry'] if incident else [],original_relations=relations or [],original_groups=[],original_decisions=[]))
    return dict(paper_id='example',document='example.pdf',classification_scope='reconciled_units_only',regions=rows,logical_units=groups or [],pages=pages,evidence_records=[])


def group(id,members,caption,status='automatic_rule'):
    return dict(id=id,page=1,structural_kind='group',members=members,caption_ref=caption,original_group=dict(id=id,members=members,caption=caption,status=status),classification=copy.deepcopy(unit('x',None,cat='figure',fn='associated_content')['classification']))


def content(out,route='main'):
    byid={s['id']:s for s in out['steps']}
    return [byid[x]['unit_ref'] for x in out['routes'][route]['expanded_sequence'] if byid[x]['kind']=='content']


class OrderTests(unittest.TestCase):
    def test_columns_and_full_width_heading(self):
        items=[dict(id='h',box=[.1,.05,.9,.1]),dict(id='l1',box=[.1,.2,.45,.4]),dict(id='r1',box=[.55,.2,.9,.4]),dict(id='l2',box=[.1,.5,.45,.8]),dict(id='r2',box=[.55,.5,.9,.8])]
        result=xy_order(items)
        self.assertEqual(result['order'],['h','l1','l2','r1','r2'])

    def test_input_preserved_and_only_reconciled_units(self):
        d=doc([unit('a',[100,100,450,200])]);old=copy.deepcopy(d);out=order_document(d)
        self.assertEqual(d,old);self.assertEqual(content(out),['a'])
        self.assertEqual(out['inventory'][0]['original_unit'],d['regions'][0])

    def test_caption_below_read_first(self):
        rows=[unit('fig',[100,200,450,500],cat='figure',fn='associated_content'),unit('cap',[100,510,450,560],cat='caption',fn='associated_content')]
        out=order_document(doc(rows,[group('g',['fig'],'cap')]))
        self.assertEqual(content(out),['cap','fig'])
        self.assertNotIn('bbox_xyxy',next(s for s in out['steps'] if s['unit_ref']=='g'))

    def test_shared_caption_content_once(self):
        rows=[unit('a',[100,200,450,500],cat='figure'),unit('b',[550,200,900,500],cat='figure'),unit('cap',[100,510,900,560],cat='caption')]
        out=order_document(doc(rows,[group('g1',['a'],'cap'),group('g2',['b'],'cap')]))
        self.assertEqual(content(out).count('cap'),1)
        self.assertEqual(set(content(out)),{'cap','a','b'})

    def test_candidate_group_not_expanded(self):
        rows=[unit('fig',[100,200,450,500],cat='figure'),unit('cap',[100,510,450,560],cat='caption')]
        out=order_document(doc(rows,[group('g',['fig'],'cap','abstained')]))
        self.assertEqual(content(out),['fig','cap'])

    def test_deferred_children_parent_not_duplicated(self):
        rows=[unit('p',[100,100,450,500],kind='container',native='index'),unit('child',None,parent='p')]
        out=order_document(doc(rows,incident=True))
        self.assertEqual(content(out),[])
        child=next(x for x in out['inventory'] if x['unit_ref']=='child')
        self.assertEqual(child['disposition'],'deferred_child_reference')
        self.assertTrue(all(s['evidence_status']=='abstained' for s in out['steps']))
        self.assertIsNone(child['original_unit']['bbox_xyxy'])

    def test_valid_text_container_is_reference_only(self):
        rows=[unit('p',[100,100,450,500],kind='container',native='index'),unit('child',[100,100,450,200],parent='p')]
        out=order_document(doc(rows))
        self.assertEqual(content(out),['child'])

    def test_continuity_distinct_from_adjacency_across_visual(self):
        rows=[unit('a',[100,700,450,900],text='We measured the'),unit('fig',[100,920,450,970],cat='figure'),unit('cap',[100,972,450,990],cat='caption'),unit('b',[550,100,900,400],text='result of the experiment.')]
        out=order_document(doc(rows,[group('g',['fig'],'cap')]));rels=[r for r in out['relations'] if r['type']=='paragraph_continues']
        self.assertTrue(any(r['from']=='a' and r['to']=='b' and r['status']=='candidate_supported' for r in rels))
        self.assertEqual(content(out),['a','cap','fig','b'])

    def test_unassociated_visual_cannot_support_continuity(self):
        rows=[unit('a',[100,700,450,900],text='We measured the'),unit('fig',[100,920,450,970],cat='figure'),unit('b',[550,100,900,400],text='result.')]
        rels=[r for r in order_document(doc(rows))['relations'] if r['type']=='paragraph_continues']
        self.assertNotEqual(rels[0]['status'],'candidate_supported')

    def test_cycle_resolution_independent_of_relation_serialization(self):
        rels=[dict(type='precedes',**{'from':'a','to':'b'},status='native_preserved'),dict(type='precedes',**{'from':'b','to':'a'},status='native_preserved')]
        rows=[unit('a',[100,100,450,200]),unit('b',[100,300,450,400])]
        self.assertEqual(content(order_document(doc(rows,relations=rels))),content(order_document(doc(rows,relations=list(reversed(rels))))))

    def test_shared_body_ownership_is_explicit_fallback(self):
        rows=[unit('a',[100,200,450,500],cat='figure'),unit('cap',[100,510,450,560],cat='caption')]
        out=order_document(doc(rows,[group('g1',['a'],'cap'),group('g2',['a'],'cap')]))
        appearance=next(s for s in out['steps'] if s['kind']=='content' and s['unit_ref']=='a')
        self.assertEqual(appearance['order_basis'],'fallback')
        self.assertTrue(any(d['status']=='shared_body_ownership_fallback' for d in out['decisions']))

    def test_period_does_not_prove_separate_paragraph(self):
        a=unit('a',[100,700,450,900],text='The experiment ended.');b=unit('b',[550,100,900,400],text='Another sentence.')
        rels=[r for r in order_document(doc([a,b]))['relations'] if r['type']=='paragraph_continues']
        self.assertEqual(rels[0]['status'],'candidate_ambiguous')

    def test_routes_preserved(self):
        rows=[unit('a',[100,300,450,400]),unit('meta',[100,50,450,100],fn='metadata'),unit('note',[100,900,450,950],native='page_footnote'),unit('ref',[100,700,450,800],native='ref_text')]
        out=order_document(doc(rows))
        self.assertEqual(content(out),['a']);self.assertEqual(content(out,'notes'),['note']);self.assertEqual(content(out,'bibliography'),['ref']);self.assertEqual(content(out,'metadata'),['meta'])

    def test_cycles_warn_without_losing_original_relations(self):
        rels=[dict(type='precedes',**{'from':'a','to':'b'},status='native_preserved'),dict(type='precedes',**{'from':'b','to':'a'},status='native_preserved')]
        out=order_document(doc([unit('a',[100,100,450,200]),unit('b',[100,300,450,400])],relations=rels))
        self.assertTrue(out['suspended_constraints'])
        self.assertEqual(out['original_page_context'][0]['original_relations'],rels)

    def test_order_and_scale_invariance(self):
        rows=[unit('a',[100,700,450,900]),unit('b',[550,100,900,400])]
        d=doc(rows);out=order_document(d);d['regions'].reverse()
        self.assertEqual(content(out),content(order_document(d)))
        for r in d['regions']:r['bbox_xyxy']=[v*2 for v in r['bbox_xyxy']]
        d['pages'][0]['identity'].update(width_px=2000,height_px=2000)
        self.assertEqual(content(out),content(order_document(d)))

    def test_missing_group_geometry_is_pending_not_crash(self):
        rows=[unit('fig',None,cat='figure'),unit('cap',[100,510,450,560],cat='caption')]
        out=order_document(doc(rows,[group('g',['fig'],'cap')]))
        self.assertEqual(next(x for x in out['inventory'] if x['unit_ref']=='g')['disposition'],'pending_group_reference')

    def test_page_abstention_next_edges_are_fallback(self):
        rows=[unit('fig',[100,200,450,500],cat='figure'),unit('cap',[100,510,450,560],cat='caption')]
        out=order_document(doc(rows,[group('g',['fig'],'cap')],incident=True))
        self.assertTrue(all(r['status']=='fallback' for r in out['relations'] if r['type']=='next_in_route'))

    def test_overlapping_geometry_not_supported_precedence(self):
        out=order_document(doc([unit('a',[100,100,450,400]),unit('b',[100,200,450,500])]))
        self.assertTrue(all(r['status']=='fallback' for r in out['relations'] if r['type']=='precedes'))

    def test_rtl_page_not_silently_ordered_as_ltr(self):
        out=order_document(doc([unit('a',[100,100,450,400],text='مرحبا')]))
        self.assertEqual(out['steps'][0]['evidence_status'],'abstained')


if __name__=='__main__':unittest.main()
