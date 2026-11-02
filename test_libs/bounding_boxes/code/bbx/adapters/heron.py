import time
from pathlib import Path
from ..contracts import sha256, write_json
from ..normalize import normalize


def run_heron(config,pdf,output):
    import torch
    from transformers import RTDetrV2ForObjectDetection, RTDetrImageProcessor
    import pypdfium2
    if not torch.cuda.is_available():raise RuntimeError('CUDA required; no CPU fallback')
    if not config.get('revision'):raise ValueError('Pinned model revision required')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    def loader():
        model_path=config.get('model_path',config['model'])
        processor=RTDetrImageProcessor.from_pretrained(model_path,revision=config['revision'],local_files_only=True)
        model=RTDetrV2ForObjectDetection.from_pretrained(model_path,revision=config['revision'],local_files_only=True).eval().to('cuda')
        torch.cuda.synchronize();return processor,model
    start=time.perf_counter();was_loaded='_loaded_model' in config
    processor,model=stage_model(config,loader)
    load_s=0 if was_loaded else time.perf_counter()-start
    detections=[];timings=[];paper_hash=sha256(pdf)
    with pypdfium2.PdfDocument(str(pdf)) as doc:
        for i,page in enumerate(doc):
            # Fixed view rasterization; model retains its own processor defaults.
            image=page.render(scale=config.get('render_dpi',200)/72).to_pil().convert('RGB')
            inputs=processor(images=[image],return_tensors='pt').to('cuda')
            torch.cuda.synchronize();start=time.perf_counter()
            with torch.inference_mode():raw=model(**inputs)
            torch.cuda.synchronize();elapsed=time.perf_counter()-start
            result=processor.post_process_object_detection(raw,target_sizes=torch.tensor([image.size[::-1]]),threshold=config['threshold'])[0]
            rows=[dict(bbox=b.tolist(),label=model.config.id2label[int(l)],label_id=int(l),score=float(s))
                  for b,l,s in zip(result['boxes'],result['labels'],result['scores'])]
            path=output/f'page-{i}.json';write_json(path,rows)
            source=dict(tool=config['id'],paper_sha256=paper_hash,page_idx=i,width=image.width,height=image.height,
                        coordinates='pixels_top_left',rotation=0,original_ref=str(path),original_sha256=sha256(path))
            detections.extend(normalize(row,source) for row in rows);timings.append(dict(page_idx=i,inference_s=elapsed))
    write_json(output/'normalized.json',detections)
    return dict(load_s=load_s,timings=timings,pages=len(timings),page_indices=list(range(len(timings))),normalized=str(output/'normalized.json'))


def stage_model(config,loader):
    """One immutable model instance per tool process, reused across papers."""
    if '_loaded_model' not in config:config['_loaded_model']=loader()
    return config['_loaded_model']
