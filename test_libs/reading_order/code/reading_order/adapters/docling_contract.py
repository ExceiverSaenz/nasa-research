"""Stable Docling CIDs preserve MinerU source adjacency, including gaps."""
import re


CID_CONTRACT='mineru_top_level_block_ordinal/v1'
_ROOT_BLOCK=re.compile(r'/pages/(0|[1-9][0-9]*)/blocks/(0|[1-9][0-9]*)')


def source_cids(blocks,page_idx):
    """Return source ordinals in presentation order, without sorting or I/O.

    Docling interprets cid+1 as source consecutivity. Compacting eligible
    elements or enumerating a permutation would change that prior. Original
    references have already been resolved and hashed by the ingestor.
    """
    if type(page_idx) is not int or page_idx<0:raise ValueError('Invalid Docling page')
    result=[];identities=set();locators=set()
    for block in blocks:
        reference=block.get('source_ref')
        if not isinstance(reference,str):raise ValueError('Docling requires a source reference')
        locator,separator,pointer=reference.partition('#')
        match=_ROOT_BLOCK.fullmatch(pointer)
        if (not separator or not locator or match is None or int(match[1])!=page_idx
                or type(block.get('page_idx')) is not int or block['page_idx']!=page_idx
                or block.get('parent_id') is not None):
            raise ValueError('Docling requires a resolved top-level source block on this page')
        identity=block.get('id')
        if not isinstance(identity,str) or not identity or identity in identities:
            raise ValueError('Ambiguous Docling block identity')
        identities.add(identity);locators.add(locator);result.append(int(match[2]))
    if len(set(result))!=len(result) or len(locators)>1:
        raise ValueError('Ambiguous Docling source ordinal')
    return result
