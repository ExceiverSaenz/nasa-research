"""Replay the pinned Hantian greedy decoder from saved scores/tie order only."""
from collections import defaultdict


def replay(logits,candidates):
    n=len(logits)
    if len(candidates)!=n or any(len(row)!=n for row in logits):raise ValueError('Invalid saved logits')
    if any(sorted(row)!=list(range(n)) for row in candidates):raise ValueError('Invalid candidate order')
    orders=[list(row) for row in candidates]
    ret=[row.pop() for row in orders]
    conflicts=0;ties=0
    while True:
        grouped=defaultdict(list)
        for index,rank in enumerate(ret):grouped[rank].append(index)
        grouped={rank:indices for rank,indices in grouped.items() if len(indices)>1}
        if not grouped:break
        for rank,indices in grouped.items():
            conflicts+=1
            values=[logits[i][rank] for i in indices]
            ties+=len(values)-len(set(values))
            ranked=sorted(indices,key=lambda i:logits[i][rank],reverse=True)
            for index in ranked[1:]:
                if not orders[index]:raise ValueError('Decoder exhausted candidates')
                ret[index]=orders[index].pop()
    return dict(ranks=ret,conflict_groups=conflicts,exact_score_ties=ties)
