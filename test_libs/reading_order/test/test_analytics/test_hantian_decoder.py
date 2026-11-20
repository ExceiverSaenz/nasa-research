def test_greedy_decoder_keeps_highest_score_for_conflicting_rank():
    from hantian_decoder_audit import replay
    result=replay([[4.,3.],[5.,1.]],[[1,0],[1,0]])
    assert result['ranks']==[1,0]
    assert result['exact_score_ties']==0


def test_exact_tie_retains_first_input_entity():
    from hantian_decoder_audit import replay
    result=replay([[4.,3.],[4.,1.]],[[1,0],[1,0]])
    assert result['ranks']==[0,1]
    assert result['exact_score_ties']==1


def test_conflict_free_scores_do_not_invent_conflicts():
    from hantian_decoder_audit import replay
    assert replay([[4.,1.],[1.,4.]],[[1,0],[0,1]])==dict(ranks=[0,1],conflict_groups=0,exact_score_ties=0)
