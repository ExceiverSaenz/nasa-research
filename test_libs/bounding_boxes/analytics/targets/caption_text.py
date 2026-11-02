"""Describe existing native caption strings; no OCR and no semantic relabeling."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import sys,json,re
from pathlib import Path
from collections import Counter
from analytics.geometry.run import SOURCE,BASE,readlines,csvout,jsonout,sha
OUT=BASE/'raw_results/analytics/targets-20261101-v1'

def flatten(node):
    if isinstance(node,str):return node
    if isinstance(node,list):return ' '.join(flatten(x) for x in node)
    if isinstance(node,dict):return flatten(node.get('content',''))
    return ''

def main():
    if (OUT/'native_caption_text.csv').exists():raise RuntimeError('Caption profiles exist')
    rows=readlines(SOURCE/'detections.jsonl');sm=json.loads((SOURCE/'source_map.json').read_text(encoding='utf-8'));paths={r['original_ref'].split('#')[0]:r['local_path'] for r in sm};cache={};hashes={};out=[]
    for r in rows:
        if r['tool'] not in ('basic','standard') or r['raw_label'] not in ('image_caption','chart_caption','table_caption'):continue
        path=str(resolve_path(paths[r['original_ref'].split('#')[0]]))
        if path not in cache:hashes[path]=sha(path);cache[path]=json.loads(Path(path).read_text(encoding='utf-8'))
        node=cache[path]
        for key in r['original_ref'].split('#',1)[1].split('/')[1:]:node=node[int(key)] if isinstance(node,list) else node[key.replace('~1','/').replace('~0','~')]
        text=flatten(node).strip()
        kind='bare_panel_marker' if re.fullmatch(r'\(?[a-zA-Z]\)?[.:]?',text) else 'figure_prefix' if re.match(r'^(Figure|Fig\.?)[\s\d]',text,re.I) else 'table_prefix' if re.match(r'^Table\s',text,re.I) else 'other_caption_string'
        out.append(dict(tool=r['tool'],paper_sha256=r['paper_sha256'],page_idx=r['page_idx'],label=r['raw_label'],bbox=r['bbox_normalized'],native_ref=r['original_ref'],text=text,lexical_pattern=kind,meaning='existing_text_pattern_not_independent_semantic_class'))
    csvout(OUT/'native_caption_text.csv',out);counts=Counter((r['tool'],r['lexical_pattern']) for r in out)
    jsonout(OUT/'native_caption_text_summary.json',[dict(tool=t,pattern=p,count=n) for (t,p),n in sorted(counts.items())])
    assert all(sha(p)==h for p,h in hashes.items());jsonout(OUT/'caption_text_verification.json',dict(input_hashes=hashes,code_hash=sha(__file__),unchanged=True,ocr_executed=False))
    print(json.dumps([dict(tool=t,pattern=p,count=n) for (t,p),n in sorted(counts.items())],indent=2))

if __name__=='__main__':main()
