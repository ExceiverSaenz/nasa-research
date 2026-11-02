"""Docling conversion and portable exports. Docling imports are intentionally lazy."""
from collections import Counter
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import time

from .common import ROOT, digest, file_manifest, IntegrityService, write_json

CONFIG = dict(schema='docling-baseline/1', device='cuda:0', do_ocr=True,
              ocr_backend='onnxruntime', ocr_language='en', ocr_device='cpu',
              do_table_structure=True, table_mode='accurate', images_scale=2.0,
              generate_page_images=True, generate_picture_images=True,
              do_formula_enrichment=True, do_code_enrichment=False,
              do_picture_classification=False, do_picture_description=False)


from .contracts import Converter, Exporter, Integrity


class DoclingConverterFactory:
    def __init__(self, models):
        self.models = Path(models)

    def create(self):
        models = self.models
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions, TableFormerMode
        from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
        from docling.document_converter import DocumentConverter, PdfFormatOption
        options = PdfPipelineOptions(artifacts_path=models, do_ocr=True, do_table_structure=True,
            generate_page_images=True, generate_picture_images=True, images_scale=2.0,
            do_formula_enrichment=True, do_code_enrichment=False,
            do_picture_classification=False, do_picture_description=False)
        options.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CUDA)
        options.table_structure_options.mode = TableFormerMode.ACCURATE
        options.ocr_options = RapidOcrOptions(backend='onnxruntime', lang=['en'], force_full_page_ocr=False,
            rapidocr_params={f'{stage}.{option}':False for stage in ('Det','Cls','Rec') for option in ('use_cuda','use_dml')})
        return DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=options)})

class DocumentNormalizer:
    def normalize(self, document, paper_id, images):
        rows = []
        # The native traversal is authoritative; never concatenate typed collections.
        for item, depth in document.iterate_items():
            native = item.model_dump(mode='json', exclude_none=True)
            ref = native['self_ref']; label = native.get('label', 'group')
            # Image transport is explicit in image_path; keep embedded data out of JSONL.
            native.pop('image', None)
            provenance = []
            for prov in native.get('prov', []):
                page = document.pages.get(prov.get('page_no'))
                provenance.append(dict(prov, page_size=page.size.model_dump(mode='json') if page else None))
            row = dict(element_id=paper_id+':'+ref, docling_ref=ref, order_index=len(rows),
                       type=label, text=native.get('text'), image_path=images.get(ref),
                       caption_refs=[r['cref'] for r in native.get('captions', [])],
                       parent_ref=(native.get('parent') or {}).get('cref'), depth=depth,
                       provenance=provenance, native=native)
            if label == 'table':
                row['table_data'] = native.get('data')
                row['table_markdown'] = item.export_to_markdown(doc=document)
            rows.append(row)
        return rows

class ReferenceValidator:
    def validate(self, native, output):
        refs, links, images = set(), [], []
        def visit(value):
            if isinstance(value, dict):
                if 'self_ref' in value: refs.add(value['self_ref'])
                if 'cref' in value: links.append(value['cref'])
                if '$ref' in value: links.append(value['$ref'])
                if 'uri' in value and 'mimetype' in value: images.append(value['uri'])
                for v in value.values(): visit(v)
            elif isinstance(value, list):
                for v in value: visit(v)
        visit(native)
        problems = ['Unresolved reference: '+r for r in links if r not in refs]
        for uri in images:
            from urllib.parse import unquote, urlsplit
            parsed = urlsplit(uri)
            p = (output/unquote(parsed.path)).resolve()
            if (parsed.scheme or PurePosixPath(parsed.path).is_absolute()
                    or not p.is_relative_to(output.resolve()) or not p.is_file()):
                problems.append('Nonportable or missing image reference')
        return problems

class PortableExport:
    def relocate(self, output, source_root=None):
        """Relocate Docling's referenced exports without changing document content."""
        from urllib.parse import unquote, urlsplit, quote
        output=Path(output); source_root=(source_root or output.resolve().as_posix()).rstrip('/')
        native=json.loads((output/'document.json').read_text(encoding='utf-8'))
        def visit(value):
            if isinstance(value,dict):
                if 'uri' in value and 'mimetype' in value:
                    parsed=urlsplit(value['uri']); path=unquote(parsed.path)
                    if parsed.scheme not in ('','file') or parsed.netloc or parsed.query or parsed.fragment:
                        raise ValueError('External image URI is not an exported local asset')
                    if path.startswith(source_root+'/'): relative=path[len(source_root)+1:]
                    elif not parsed.scheme and not PurePosixPath(path).is_absolute(): relative=path
                    else: raise ValueError('Image reference is outside the exported document')
                    target=(output/relative).resolve()
                    if '..' in PurePosixPath(relative).parts or not target.is_relative_to(output.resolve()) or not target.is_file():
                        raise ValueError('Unsafe or missing exported image')
                    value['uri']=quote(relative,safe='/._-')
                for child in value.values():visit(child)
            elif isinstance(value,list):
                for child in value:visit(child)
        visit(native)
        write_json(output/'document.json',native)
        markdown=(output/'document.md').read_text(encoding='utf-8')
        for prefix in ('file://'+source_root+'/',source_root+'/',quote(source_root,safe='/')+'/'):
            markdown=markdown.replace(prefix,'')
        (output/'document.md').write_text(markdown,encoding='utf-8')

class AssetStore:
    def store(self, image, output, name):
        """Reference an identical existing PNG, preserving every distinct payload."""
        buffer = io.BytesIO()
        image.save(buffer, 'PNG')
        payload = buffer.getvalue()
        identity = hashlib.sha256(payload).hexdigest()
        output = Path(output)
        for candidate in sorted((output/'assets').glob('*.png')):
            if candidate.stat().st_size == len(payload) and digest(candidate) == identity:
                return candidate.relative_to(output).as_posix()
        with (output/name).open('xb') as stream:
            stream.write(payload)
        return name

class DocumentExporter:
    def __init__(self, *, normalizer=None, validator=None, portable=None, assets=None):
        self.normalizer = normalizer if normalizer is not None else DocumentNormalizer()
        self.validator = validator if validator is not None else ReferenceValidator()
        self.portable = portable if portable is not None else PortableExport()
        self.assets = assets if assets is not None else AssetStore()

    def export(self, document, output, paper_id):
        from docling_core.types.doc import ImageRefMode
        output = Path(output); assets = output/'assets'; assets.mkdir()
        document.save_as_json(output/'document.json', artifacts_dir=assets, image_mode=ImageRefMode.REFERENCED)
        document.save_as_markdown(output/'document.md', artifacts_dir=assets, image_mode=ImageRefMode.REFERENCED)
        self.portable.relocate(output)
        images, problems = {}, []
        for item, _ in document.iterate_items():
            native = item.model_dump(mode='json')
            if native.get('label') != 'picture': continue
            image = item.get_image(document)
            if image is None:
                problems.append('Figure without image: '+native['self_ref']); continue
            name = 'assets/figure-'+str(len(images)+1).zfill(4)+'.png'
            images[native['self_ref']] = self.assets.store(image, output, name)
        rows = self.normalizer.normalize(document, paper_id, images)
        with (output/'elements.jsonl').open('w', encoding='utf-8') as stream:
            for row in rows: stream.write(json.dumps(row, ensure_ascii=False)+'\n')
        native = json.loads((output/'document.json').read_text(encoding='utf-8'))
        problems += self.validator.validate(native, output)
        write_json(output/'manifest.json', dict(schema='baseline-assets/1', paper_id=paper_id,
            elements=[{k:r[k] for k in ('element_id','docling_ref','image_path','caption_refs')} for r in rows],
            assets=file_manifest(assets), problems=problems))
        return dict(pages=len(document.pages), elements=len(rows), by_type=dict(Counter(r['type'] for r in rows))), problems

class PaperParser:
    def __init__(self, converter: Converter, *, exporter: Exporter | None = None,
                 integrity: Integrity | None = None, clock=None):
        self.converter = converter
        self.exporter = exporter if exporter is not None else DocumentExporter()
        self.integrity = integrity if integrity is not None else IntegrityService()
        self.clock = clock if clock is not None else time.perf_counter

    def parse(self, pdf, output_root, environment, models_identity):
        pdf = Path(pdf); paper_id = digest(pdf)
        key = hashlib.sha256(json.dumps(dict(pdf=paper_id, config=CONFIG,
            lock=self.integrity.verify_lock()['lock_sha256'], models=models_identity,
            environment=environment), sort_keys=True).encode()).hexdigest()
        output = Path(output_root)/paper_id
        if output.exists():
            self.integrity.verify_files(output)
            old = json.loads((output/'run.json').read_text(encoding='utf-8'))
            if old.get('cache_key') != key or old.get('status') != 'completed':
                raise ValueError('Existing result is incompatible or incomplete; preserve it')
            return old
        output.mkdir(parents=True)
        run = dict(schema='baseline-paper/1', input_sha256=paper_id, input_name=pdf.name,
            cache_key=key, status='running', configuration=CONFIG, environment=environment,
            models_identity=models_identity, lock_sha256=self.integrity.verify_lock()['lock_sha256'], errors=[])
        write_json(output/'run.json', run); start=self.clock()
        try:
            result = self.converter.convert(pdf, raises_on_error=False)
            run['conversion_status'] = result.status.value
            run['conversion_seconds'] = self.clock()-start
            run['errors'] = [e.model_dump(mode='json') for e in result.errors]
            start_export=self.clock()
            if result.document is not None:
                run['metrics'], problems = self.exporter.export(result.document, output, paper_id)
                run['errors'].extend(problems)
            else: run['errors'].append('No document returned')
            run['export_seconds']=self.clock()-start_export
            run['status'] = 'completed' if run['conversion_status']=='success' and not run['errors'] else 'partial'
        except Exception as exc:
            run['status']='failed'; run['errors'].append(type(exc).__name__+': '+str(exc))
        run['total_seconds']=self.clock()-start
        write_json(output/'run.json', run)
        write_json(output/'files.json', file_manifest(output))
        return run

