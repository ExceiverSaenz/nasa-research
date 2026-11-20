"""Subtype assessment supplements, never replaces, family assessment."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
def subtype_check(reference_subtype,labels):
    labels=set(labels)
    if reference_subtype=='figure_caption' and 'table_caption' in labels:return 'figure_as_table_caption'
    if reference_subtype=='table_caption' and labels & {'chart_caption','image_caption'}:return 'table_as_figure_caption'
    if reference_subtype=='document_heading' and labels=={'section_header'}:return 'document_as_section'
    if reference_subtype=='section_heading' and labels=={'doc_title'}:return 'section_as_document'
    if reference_subtype=='chapter_marker' and labels=={'page_number'}:return 'chapter_as_page_number'
    return 'generic_or_compatible'

if __name__=='__main__':
    import sys
    from pathlib import Path
    from analytics.geometry.run import BASE,readlines,csvout,jsonout,sha
    out=BASE/'raw_results/analytics/targets-20261101-v1';source=out/'agent_assessments.jsonl';before=sha(source)
    records=[dict(case_id=r['case_id'],tool=r['tool'],reference=r['reference'],reference_subtype=r['reference_subtype'],labels=r['labels'],family_status=r['status'],subtype_status=subtype_check(r['reference_subtype'],r['labels'])) for r in readlines(source) if r['eligible'] and r['own_matches']]
    csvout(out/'agent_subtype_assessments.csv',records);assert sha(source)==before
    jsonout(out/'subtypes_verification.json',dict(input_hashes={str(source):before,str(Path(__file__)):sha(__file__)},unchanged=True))
