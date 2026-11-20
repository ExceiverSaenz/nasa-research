import pytest


def test_native_ranks_and_indices_have_different_contracts():
    from investigate_sensitivity import decode_native
    ids=['a','b','c']
    assert decode_native('hantian',{'ranks':[2,0,1]},ids)==['b','c','a']
    assert decode_native('docling',{'indices':[2,0,1]},ids)==['c','a','b']
    with pytest.raises(ValueError):decode_native('hantian',{'ranks':[0,0,1]},ids)


def test_pp_replay_is_equivariant_if_pair_preferences_are_preserved():
    from investigate_sensitivity import pp_votes,pp_order,reindex_pairs
    ids=['a','b','c'];matrix=[[-10000,4,5],[-10000,-10000,3],[-10000,-10000,-10000]]
    assert pp_order(matrix,ids)==ids
    other=['c','a','b']
    transformed=reindex_pairs(matrix,ids,other)
    assert pp_order(transformed,other)==ids
    assert len(pp_votes(matrix))==3


def test_docling_adjacency_prior_changes_without_geometry_change():
    from investigate_sensitivity import docling_prior_edges
    boxes={'left':[0,0,40,90],'right':[60,0,100,90],'elsewhere':[0,110,30,120]}
    assert ['left','right'] in docling_prior_edges(['left','right','elsewhere'],boxes)['horizontal']
    assert ['left','right'] not in docling_prior_edges(['left','elsewhere','right'],boxes)['horizontal']
