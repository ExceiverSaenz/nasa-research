import argparse
import json
from pathlib import Path
from .contracts import load_experiment,write_json,sha256
from .resources import gpu_snapshot,ResourceMonitor


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--tool',required=True)
    p.add_argument('--inventory',required=True);p.add_argument('--pdf-dir',required=True);p.add_argument('--output',required=True)
    p.add_argument('--smoke',action='store_true')
    args=p.parse_args();config=load_experiment(args.config)
    gpus=gpu_snapshot()
    if len(gpus)!=1 or not gpus[0]['a100']:raise RuntimeError('One A100 required')
    tool=next(t for t in config['tools'] if t['id']==args.tool)
    if config.get('mineru_config'):
        import os
        os.environ['MINERU_CONFIG']=config['mineru_config']
        os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    from .adapters.heron import run_heron
    from .adapters.mineru import run_mineru
    results=[];inventory=load_experiment(args.inventory)
    out=Path(args.output)
    if args.smoke:
        # One explicit page; a derived PDF identity belongs only to smoke, never the benchmark.
        import pypdfium2
        paper=inventory[0];source=Path(args.pdf_dir)/paper['name']
        if sha256(source)!=paper['sha256']:raise ValueError('PDF identity mismatch')
        out.mkdir(parents=True,exist_ok=False);destination=out/'smoke-input.pdf'
        with pypdfium2.PdfDocument(str(source)) as doc:
            new=pypdfium2.PdfDocument.new();new.import_pages(doc,[0]);new.save(str(destination));new.close()
        inventory=[{'name':'smoke-input.pdf','sha256':sha256(destination),'pages':1}];args.pdf_dir=str(out)
    with ResourceMonitor(config['resource_interval_s']) as monitor:
        try:
            for paper in inventory:
                pdf=Path(args.pdf_dir)/paper['name']
                try:
                    if sha256(pdf)!=paper['sha256']:raise ValueError('PDF identity mismatch')
                    fn=run_heron if args.tool in ('heron','heron101') else run_mineru
                    result=fn(tool,pdf,out/pdf.stem)
                    if sorted(result.get('page_indices',[]))!=list(range(paper['pages'])):raise ValueError('Native page coverage incomplete')
                    files={str(p.relative_to(out/pdf.stem)):{'bytes':p.stat().st_size,'sha256':sha256(p)} for p in (out/pdf.stem).rglob('*') if p.is_file()}
                    results.append(dict(paper=paper['name'],status='complete',result=result,files=files))
                except Exception as e:
                    results.append(dict(paper=paper['name'],status='failed',error=type(e).__name__))
                    raise
                finally:write_json(out/'receipt.json',dict(tool=args.tool,results=results,resources=monitor.samples))
        finally:write_json(out/'receipt.json',dict(tool=args.tool,results=results,resources=monitor.samples))
    print('BBX_STAGE_COMPLETED:'+args.tool,flush=True)


if __name__=='__main__':main()
