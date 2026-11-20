"""Explicit analytical vocabulary and assessment of visually reviewed cases."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
def family(label):
    return {'text':'text','title':'heading','doc_title':'heading','section_header':'heading','paragraph_title':'heading',
            'caption':'caption','image_caption':'caption','chart_caption':'caption','table_caption':'caption',
            'picture':'visual','image':'visual','chart':'visual','table':'table','formula':'equation','equation':'equation',
            'list_item':'list','ref_text':'reference','header':'margin_header','page_header':'margin_header',
            'footer':'margin_footer','page_footer':'margin_footer','page_number':'number','document_index':'index','index':'index',
            'footnote':'note','page_footnote':'note','key_value_region':'key_value'}.get(label)

def pair_agreement(a,b):
    aa={family(x) for x in a};bb={family(x) for x in b}
    if None in aa or None in bb or not aa or not bb:return None
    return aa==bb

def assess(reference,labels,subtype=None):
    if not labels:return dict(status='no_own_correspondence',error=None)
    fs={family(x) for x in labels};known=fs-{None}
    if not known:return dict(status='undetermined',error=None)
    acceptable={reference}
    # Reference is an independent visual role; generic labels can be useful without exact subtype.
    coarse={'reference':{'list','text'},'list':{'text'},'visual':{'margin_header'},'number':{'text','margin_header','margin_footer'},'author':{'text','list'},'metadata':{'text','margin_header','margin_footer'},'note':{'text','margin_footer'},'heading':set(),'text':set(),'caption':set()}
    accepted=acceptable|coarse.get(reference,set())
    if reference=='author' and subtype=='affiliation':accepted.add('note')
    if len(known)>1 and not known<=accepted:return dict(status='contradictory',error='conflicting_targets')
    if known<={reference}:return dict(status='adequate',error=None)
    if known<=accepted:return dict(status='coarse_usable',error=None)
    err='heading_to_text' if reference=='heading' and 'text' in known else 'text_to_heading' if reference in ('text','author') and 'heading' in known else 'caption_to_text' if reference=='caption' and 'text' in known else 'wrong_target'
    return dict(status='wrong',error=err)
