import json
import uuid
from pathlib import Path
from .contracts import write_json


def aggregate(attempt,papers,config,run_id,*,render=False,pdf_dir=None):
    attempt=Path(attempt);pages=[];tools=[t['id'] for t in config['tools']]
    for paper in papers:
        tool_rows={};tool_status={}
        for tool in tools:
            file=attempt/tool/Path(paper['name']).stem/'normalized.json'
            rows=json.loads(file.read_text()) if file.exists() else []
            if any(d.get('paper_sha256')!=paper['sha256'] or not 0<=d.get('page_idx',-1)<paper['pages'] for d in rows):
                raise ValueError('Detection outside frozen inventory')
            tool_rows[tool]=rows
            # A normalized file alone does not prove a complete parse.
            receipt=attempt/tool/'receipt.json'
            status='failed'
            if receipt.exists():
                records=json.loads(receipt.read_text()).get('results',[])
                status=next((r['status'] for r in records if r['paper']==paper['name']),'failed')
            tool_status[tool]=status
        doc=None
        if render:
            import pypdfium2
            doc=pypdfium2.PdfDocument(str(Path(pdf_dir)/paper['name']))
        try:
            for i in range(paper['pages']):
                image=None
                if doc is not None:
                    image=f'pages/{paper["sha256"]}/{i}.png';out=attempt/image;out.parent.mkdir(parents=True,exist_ok=True)
                    # A page may already be a shared cache reference. Replace it,
                    # rather than writing through the link into another attempt.
                    temp=out.with_name('.'+uuid.uuid4().hex+'.png')
                    try:
                        doc[i].render(scale=200/72).to_pil().save(temp)
                        temp.replace(out)
                    finally:
                        temp.unlink(missing_ok=True)
                pages.append(dict(paper=paper['name'],paper_sha256=paper['sha256'],page_idx=i,image=image,
                    detections=[d for t in tools for d in tool_rows[t] if d['page_idx']==i],tool_status=tool_status.copy(),
                    status='complete' if all(s=='complete' for s in tool_status.values()) else 'failed'))
        finally:
            if doc is not None:doc.close()
    data=dict(run_id=run_id,tools=tools,pages=pages);write_json(attempt/'viewer.json',data);return data
