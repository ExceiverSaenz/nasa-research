from collections import Counter
from itertools import combinations


def overlap(a,b):
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    aa=(a[2]-a[0])*(a[3]-a[1]);bb=(b[2]-b[0])*(b[3]-b[1])
    return intersection/(aa+bb-intersection),intersection/min(aa,bb)


def compare(detections,config):
    edges=[]
    for a,b in combinations(detections,2):
        if a['tool']==b['tool'] or (a['paper_sha256'],a['page_idx'])!=(b['paper_sha256'],b['page_idx']):continue
        if not a.get('bbox_normalized') or not b.get('bbox_normalized'):continue
        iou,containment=overlap(a['bbox_normalized'],b['bbox_normalized'])
        if iou>0:edges.append(dict(a=a['id'],b=b['id'],iou=iou,containment=containment,
            threshold_match=iou>=config['iou_threshold'],literal_label_match=a['raw_label']==b['raw_label']))
    counts=Counter((d['tool'],d['raw_label']) for d in detections)
    return {'edges':edges,'counts':[{'tool':k[0],'label':k[1],'count':v} for k,v in counts.items()],
            'iou_threshold':config['iou_threshold'],'meaning':'prediction agreement, not accuracy'}
