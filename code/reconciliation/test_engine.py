import copy
import unittest
from reconciliation.engine import normalize, reconcile


def record(key, kind, bbox, parser='mineru', parent=None, text=''):
    return dict(id=key, parser=parser, native_type=kind, bbox=bbox, parent=parent,
                role='segment', native={'type':kind,'content':text},
                source={'path':'fixture.json','sha256':'a'*64,'pointer':'/'+key},
                transform=[1,0,0,1,0,0], text=text)


def page(records):
    return dict(identity=dict(document_sha256='b'*64,physical_page=1,
                width_px=100,height_px=100,render_sha256='c'*64),
                records=records,parsers={p:'completed' for p in ('mineru','layoutlmv3','table_transformer')},
                adapter='canonical-v1',incidents=[])


def multi():
    return page([record('a','chart_body',[10,10,30,30],parent='pa'),
                 record('b','chart_body',[30,10,50,30],parent='pb'),
                 record('c','chart_caption',[10,32,50,38],parent='pb',text='Fig. 6 caption'),
                 record('lm','figure',[10,10,50,30],'layoutlmv3')])


class NormalizeTests(unittest.TestCase):
    def test_categories_and_preservation(self):
        types=['text','paragraph_title','chart_body','table_body','image_caption','equation','header','unknown','page_footnote']
        p=page([record(str(i),t,[1,1,2,2]) for i,t in enumerate(types)])
        before=copy.deepcopy(p); out=normalize(p)
        self.assertEqual(p,before)
        self.assertEqual([r['category'] for r in out['records']],['Texto','Títulos','Figuras','Tablas','Captions','Ecuaciones','Márgenes','Otros','Texto'])
        self.assertEqual([r['native'] for r in out['records']],[r['native'] for r in p['records']])

    def test_invalid_geometry_blocks_relations_not_records(self):
        for box in [None,[0,0,0,3],[-1,0,5,5],[0,0,float('nan'),3]]:
            p=multi();p['records'][0]['bbox']=box
            out=reconcile(p)
            self.assertFalse(out['groups']);self.assertEqual(len(out['records']),4)
            self.assertIn('invalid_geometry',out['incidents'])

    def test_duplicate_ids_block(self):
        p=multi();p['records'][1]['id']='a'
        self.assertEqual(reconcile(p)['status'],'blocked')

    def test_partial_no_mineru_and_unknown_adapter(self):
        p=page([record('lm','figure',[1,1,2,2],'layoutlmv3')]);p['parsers']['mineru']='failed'
        out=reconcile(p);self.assertEqual(out['status'],'partial');self.assertFalse(out['objects'])
        p['adapter']='unknown';self.assertEqual(reconcile(p)['status'],'blocked')

    def test_failed_parser_is_not_used_as_support(self):
        p=multi();p['parsers']['layoutlmv3']='failed'
        out=reconcile(p);self.assertFalse(out['groups']);self.assertEqual(len(out['records']),4)
        p['parsers']['mineru']='failed';self.assertFalse(reconcile(p)['objects'])

    def test_missing_transform_or_source_blocks_decisions(self):
        p=multi();del p['records'][0]['transform']
        self.assertFalse(reconcile(p)['groups'])
        p=multi();p['records'][0]['source']={}
        self.assertEqual(reconcile(p)['status'],'blocked')


class CorrespondenceTests(unittest.TestCase):
    def test_triple_agreement_and_order(self):
        p=page([record('m','table_body',[10,10,40,40]),record('l','table',[10,10,40,40],'layoutlmv3'),record('t','table',[10,10,40,40],'table_transformer')])
        out=reconcile(p);self.assertEqual(len(out['correspondences']),3)
        p['records'].reverse();self.assertEqual(out,reconcile(p))

    def test_tie_and_no_transitive_identity(self):
        p=page([record('m','table_body',[10,10,40,40]),record('l','table',[10,10,40,40],'layoutlmv3'),record('l2','table',[10,10,40,40],'layoutlmv3')])
        out=reconcile(p);self.assertFalse(out['correspondences'])
        self.assertTrue(any(d['reason']=='non_unique' for d in out['decisions']))

    def test_coarse_and_conflict(self):
        p=page([record('m','chart_caption',[10,10,40,40]),record('l','text',[10,10,40,40],'layoutlmv3')])
        self.assertTrue(any(d['reason']=='coarse_class_support' for d in reconcile(p)['decisions']))
        p['records'][1]['native_type']='title'
        self.assertTrue(any(d['reason']=='class_conflict' for d in reconcile(p)['decisions']))


class GroupTests(unittest.TestCase):
    def test_group_and_id_invariance(self):
        p=multi();out=reconcile(p)
        self.assertEqual(len(out['groups']),1)
        self.assertEqual(out['groups'][0]['members'],['a','b'])
        self.assertEqual(out['groups'][0]['caption'],'c')
        p['identity']['physical_page']=9;p['identity']['document_sha256']='d'*64
        for r in p['records']:r['id']='new-'+r['id']
        self.assertEqual(len(reconcile(p)['groups']),1)

    def test_caption_conflicts_even_without_label(self):
        p=multi();p['records'].append(record('c2','chart_caption',[10,40,50,45],parent='pa',text='description'))
        self.assertFalse(reconcile(p)['groups'])
        p=multi();p['records'][2]['text']='no recognized label';self.assertFalse(reconcile(p)['groups'])

    def test_context_border_and_external_conflict(self):
        for r in [record('x','text',[12,12,15,15]),record('x','chart_body',[45,10,60,30],parent='px'),record('x','table',[10,10,50,30],'table_transformer')]:
            p=multi();p['records'].append(r);self.assertFalse(reconcile(p)['groups'])

    def test_duplicate_anchors_and_overlap(self):
        p=multi();p['records'].append(record('lm2','figure',[10,10,50,30],'layoutlmv3'))
        p['records'][1]['bbox']=[25,10,50,30]
        g=reconcile(p)['groups'];self.assertEqual(len(g),1)
        self.assertEqual(g[0]['anchors'],['lm','lm2']);self.assertIn('member_overlap',g[0]['warnings'])

    def test_native_parents_and_simple(self):
        p=multi();p['records']= [r for r in p['records'] if r['id']!='a']
        out=reconcile(p);self.assertFalse(out['groups'])
        self.assertTrue(any(d['reason']=='single_body_no_group' for d in out['decisions']))


if __name__=='__main__':unittest.main()
