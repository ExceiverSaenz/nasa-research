
import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import unittest
from analytics.geometry.metrics import histogram, group_metrics, clusters, atoms, category

def row(uid,tool,box,label='text'):
    return dict(analysis_uid=uid,tool=tool,bbox_normalized=box,raw_label=label)

class MetricsTests(unittest.TestCase):
    def test_histogram_boundaries(self):
        self.assertEqual(histogram([0,.1,.9,1]),[1,1,0,0,0,0,0,0,0,2])
    def test_split_is_geometrically_equivalent_not_semantically_confirmed(self):
        a=[row('a','a',[0,0,1,1])]
        b=[row('b','b',[0,0,.5,1]),row('c','b',[.5,0,1,1])]
        m=group_metrics(a,b,.9)
        self.assertEqual(m['geometry_status'],'granularity_candidate')
        self.assertEqual(m['union_iou'],1)
        self.assertEqual(m['semantic_status'],'not_determined')
    def test_gap_and_duplicate_are_not_pure_granularity(self):
        a=[row('a','a',[0,0,1,1])]
        for bb in ([[0,0,.1,1],[.9,0,1,1]],[[0,0,1,1],[0,0,1,1]]):
            self.assertNotEqual(group_metrics(a,[row(str(i),'b',b) for i,b in enumerate(bb)],.9)['geometry_status'],'granularity_candidate')
    def test_complete_link_rejects_bridge_and_same_tool(self):
        rows=[row('a','a',[0,0,.5,1]),row('b','b',[.02,0,.52,1]),row('c','c',[.04,0,.54,1]),row('d','a',[0,0,.5,1])]
        cs=clusters(rows,.9)
        self.assertFalse(any(len(c)>2 for c in cs))
        self.assertTrue(all(len({r['tool'] for r in c})==len(c) for c in cs))
    def test_category_does_not_determine_spatial_clusters(self):
        cs=clusters([row('a','a',[0,0,1,1],'text'),row('b','b',[0,0,1,1],'image')],.9)
        self.assertEqual(len(cs),1)
        self.assertNotEqual(category('text'),category('image'))
    def test_complete_link_recomputes_cluster_priority(self):
        rows=[row(t,t,[x,0,x+.5,1]) for t,x in zip('ABCD',[0,.005,.023,.0425])]
        self.assertEqual({frozenset(r['tool'] for r in c) for c in clusters(rows,.9)}, {frozenset('AB'),frozenset('CD')})
    def test_atoms_do_not_double_count_nested_boxes(self):
        rows=[row('a','a',[0,0,1,1]),row('a2','a',[0,0,.5,1]),row('b','b',[0,0,.5,1],'image')]
        cells=atoms(rows)
        self.assertAlmostEqual(sum(c['area'] for c in cells),1)
        self.assertAlmostEqual(sum(c['area'] for c in cells if len(c['tools'])==2),.5)

if __name__=='__main__':unittest.main()
