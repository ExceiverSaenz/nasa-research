"""Score a directed, explicitly agent-reviewed sample, not a population benchmark."""
import sys,json,csv,itertools
from pathlib import Path
from collections import Counter,defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deep_analysis'))
from run import SOURCE,BASE,TOOLS,PAIRS,readlines,csvout,jsonout,jsonlout,sha
from metrics import overlap,area,box_state
from targets import family,assess
OUT=BASE/'analysis/targets-20261101-v1'

def main():
    if (OUT/'agent_assessments.jsonl').exists():raise RuntimeError('Audit already exists')
    refs=Path(__file__).with_name('references.json');rr=json.loads(refs.read_text(encoding='utf-8'));cases=readlines(OUT/'visual_cases.jsonl');rows=readlines(SOURCE/'detections.jsonl');pages=defaultdict(list)
    inputs=[refs,Path(__file__),Path(__file__).with_name('targets.py'),SOURCE/'detections.jsonl',OUT/'visual_cases.jsonl'];hashes={str(p.resolve()):sha(p) for p in inputs}
    for r in rows:
        if box_state(r.get('bbox_normalized'))=='valid' and (r.get('native_level')=='block' or r['raw_label'] in ('image_caption','table_caption','chart_caption')):pages[r['paper_sha256'],r['page_idx']].append(r)
    scored=[];scored_refs=[]
    for c in cases:
        ref=rr['cases'][c['case_id']];eligible=ref['reference'] is not None and 'same_as' not in ref
        scored_refs.append(dict(**c,**ref,eligible=eligible,reviewer=rr['reviewer'],human_validation=False,plate=f"review_{(int(c['case_id'][1:])-1)//8+1:02}.png"))
        for t in TOOLS:
            own=[];parent=[];anyhits=[]
            for r in pages[c['paper_sha256'],c['page_idx']]:
                if r['tool']!=t:continue
                v=overlap(c['roi'],r['bbox_normalized'])
                if not v['intersection']:continue
                entry=dict(id=r['analysis_uid'],label=r['raw_label'],level=r.get('native_level'),bbox=r['bbox_normalized'],**v)
                anyhits.append(entry)
                if v['iou']>=.5 or (v['fraction_b']>=.9 and v['fraction_a']>=.5):own.append(entry)
                elif v['fraction_a']>=.9 and area(r['bbox_normalized'])>1.5*area(c['roi']):parent.append(entry)
            labels=sorted({r['label'] for r in own})
            result=assess(ref['reference'],labels) if eligible else dict(status='excluded_reference',error=None)
            if eligible and not own and parent:result=dict(status='group_coverage',error=None)
            subtype='not_evaluated'
            if eligible and ref['reference']=='heading' and result['status']=='adequate':
                subtype='document_as_section' if ref['subtype']=='document_heading' and labels==['section_header'] else 'section_as_document' if ref['subtype']=='section_heading' and labels==['doc_title'] else 'compatible_or_unspecified'
            if eligible and ref['reference']=='number' and labels==['page_number'] and ref['subtype']=='chapter_marker':subtype='chapter_as_page_number'
            scored.append(dict(case_id=c['case_id'],paper=c['paper'],page_idx=c['page_idx'],stratum=c['stratum'],tool=t,reference=ref['reference'],reference_subtype=ref['subtype'],confidence=ref['confidence'],eligible=eligible,labels=labels,predicted_families=sorted(str(family(x)) for x in labels),**result,subtype_status=subtype,own_matches=own,group_matches=parent,other_intersections=anyhits,reference_note=ref['note']))
    jsonlout(OUT/'agent_reference_cases.jsonl',scored_refs);jsonlout(OUT/'agent_assessments.jsonl',scored)
    summary=[];bytarget=[];confusions=[];direction=[]
    for t in TOOLS:
        v=[r for r in scored if r['tool']==t and r['eligible']];counts=Counter(r['status'] for r in v)
        summary.append(dict(tool=t,sampled_cases=len(v),own_correspondence_cases=sum(bool(r['own_matches']) for r in v),**dict(counts),errors=dict(Counter(r['error'] for r in v if r['error']))))
        for target in sorted({r['reference'] for r in v}):
            vv=[r for r in v if r['reference']==target]
            bytarget.append(dict(tool=t,target=target,cases=len(vv),papers=len({r['paper'] for r in vv}),**dict(Counter(r['status'] for r in vv)),case_ids=[r['case_id'] for r in vv]))
        for r in v:
            if r['error'] or r['status']=='wrong':direction.append(r)
        # One-class prediction only. Contradictory/general/group/absent remain separate, never rescued by best label.
        cc=Counter((r['reference'],r['predicted_families'][0]) for r in v if r['status'] in ('adequate','wrong','coarse_usable') and len(r['predicted_families'])==1)
        for (a,b),n in cc.items():confusions.append(dict(tool=t,reference=a,predicted=b,count=n,population='agent_directed_sample_single_family_only'))
    csvout(OUT/'agent_tool_summary.csv',summary);csvout(OUT/'agent_target_summary.csv',bytarget);csvout(OUT/'agent_confusion_counts.csv',confusions);jsonlout(OUT/'agent_error_cases.jsonl',direction)
    # Headings have an explicit cost asymmetry, without invented numerical weights.
    critical=[]
    for t in TOOLS:
        v=[r for r in scored if r['tool']==t and r['eligible']];heads=[r for r in v if r['reference']=='heading'];notheads=[r for r in v if r['reference']!='heading']
        critical.append(dict(tool=t,observed_headings=len(heads),heading_adequate=sum(r['status']=='adequate' for r in heads),heading_to_text=sum(r['error']=='heading_to_text' for r in heads),heading_conflicting=sum(r['status']=='contradictory' for r in heads),heading_no_own=sum(r['status'] in ('group_coverage','no_own_correspondence') for r in heads),nonheading_with_heading_label=sum('heading' in r['predicted_families'] for r in notheads),heading_errors_case_ids=[r['case_id'] for r in heads if r['status']!='adequate'],ordinal_priority='heading_to_text_higher_than_text_to_heading_no_numeric_weights'))
    csvout(OUT/'heading_asymmetric_costs.csv',critical)
    # Strict sample precision/recall for headings only; show ambiguity bounds instead of counting ambiguous output as clean correct.
    rates=[]
    for t in TOOLS:
        v=[r for r in scored if r['tool']==t and r['eligible']];real=[r for r in v if r['reference']=='heading'];pred=[r for r in v if 'heading' in r['predicted_families']];tp=sum(r['reference']=='heading' and r['status']=='adequate' for r in pred);possible=sum(r['reference']=='heading' for r in pred)
        rates.append(dict(tool=t,sample_heading_reference=len(real),sample_heading_predicted=len(pred),unambiguous_tp=tp,possible_tp_including_conflicts=possible,strict_precision_sample=tp/len(pred) if pred else None,strict_recall_sample=tp/len(real) if real else None,precision_with_conflicts_upper=possible/len(pred) if pred else None,recall_with_conflicts_upper=possible/len(real) if real else None,interpretation='directed_agent_review_sample_not_population_precision'))
    csvout(OUT/'heading_sample_rates.csv',rates)
    assert all(sha(p)==v for p,v in hashes.items())
    jsonout(OUT/'audit_verification.json',dict(input_hashes=hashes,unchanged=True,visual_cases=len(cases),independent_case_count=sum(c['eligible'] for c in scored_refs),reference_classes=dict(Counter(c['reference'] for c in scored_refs if c['eligible'])),assessments=len(scored),eligible_assessments=sum(r['eligible'] for r in scored),human_validation=False,source_truth='assistant_visual_review_of_existing_raster'))
    print(json.dumps(dict(summary=summary,heading=critical),indent=2))

if __name__=='__main__':main()
