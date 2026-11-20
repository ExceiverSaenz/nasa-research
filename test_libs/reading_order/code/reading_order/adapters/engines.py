"""Lazy adapters over the exact libraries/checkpoints validated in configuration."""
import importlib.util
import json
from pathlib import Path
import subprocess
import time
from .base import validate_length
from ..contracts import require_permutation, ranks_to_ids

LABELS = {'text':'text', 'doc_title':'title', 'paragraph_title':'heading', 'header':'header',
          'footer':'footer', 'page_number':'number', 'page_footnote':'footnote', 'ref_text':'reference',
          'image':'image', 'chart':'chart', 'table':'table', 'equation':'formula',
          'image_caption':'caption','table_caption':'caption','caption':'caption','index':'index'}

DOCLING_LABELS={'text':'TEXT','title':'TITLE','heading':'SECTION_HEADER','header':'PAGE_HEADER',
    'footer':'PAGE_FOOTER','number':'PAGE_FOOTER','footnote':'FOOTNOTE','reference':'TEXT',
    'image':'PICTURE','chart':'PICTURE','table':'TABLE','formula':'FORMULA','caption':'CAPTION','index':'DOCUMENT_INDEX'}
DOCTR_LABELS={'heading':'text','title':'text','number':'footer','formula':'text','reference':'text','chart':'image','index':'text'}
PP_CATEGORY_NAMES={'title':'doc_title','heading':'paragraph_title','reference':'reference_content',
    'formula':'formula','footnote':'footnote','number':'number','index':'content'}


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hantian_diagnostics(logits,length):
    scores=logits[1:length+1,:length]
    return dict(rank_logits=scores.tolist(),rank_candidates=scores.argsort(descending=False).tolist())


class EngineAdapter:
    def __init__(self, candidate, environment, language='en',capture_diagnostics=False):
        self.candidate, self.environment, self.language = candidate, Path(environment), language
        self.model = None
        self.helper = None
        self.capture_diagnostics=capture_diagnostics

    def predict(self, blocks, page):
        ids = [b['id'] for b in blocks]
        if not ids:
            return dict(ordered_ids=[], native={'empty_scope':True}, transformations={})
        from numpy import array
        boxes = array([b['bbox'] for b in blocks], dtype=float)
        if any(b['bbox'] is None for b in blocks) or not ((boxes >= 0).all() and (boxes <= 1).all()):
            raise ValueError('Invalid eligible geometry')
        method = getattr(self, '_' + self.candidate)
        start = time.monotonic()
        result = method(blocks, page, boxes)
        result.setdefault('costs', {})['adapter_total_s'] = time.monotonic()-start
        if result.get('status', 'PASS') == 'PASS':
            require_permutation(result['ordered_ids'], ids)
        return result

    def _labels(self, blocks):
        if any(b['raw_label'] not in LABELS for b in blocks):
            raise ValueError('Unknown input label; no silent text fallback')
        return [LABELS[b['raw_label']] for b in blocks]

    def _xycut(self, blocks, page, boxes):
        import numpy as np
        quantized = np.rint(boxes*1000).astype(int)
        if (quantized[:,2:] <= quantized[:,:2]).any():
            raise ValueError('Quantization degenerates a source box')
        if self.helper is None:
            self.helper = _module(self.environment/'xycut.py', 'xycut_original')
        indices = []
        self.helper.recursive_xy_cut(quantized, np.arange(len(blocks)), indices)
        require_permutation(indices, list(range(len(blocks))))
        return dict(ordered_ids=[blocks[i]['id'] for i in indices], native={'indices':list(map(int,indices))},
                    transformations={'coordinates':'normalized*1000 rounded to integer', 'rounding':'numpy.rint'})

    def _doctr(self, blocks, page, boxes):
        from doctr.models.reading_order import ReadingOrderPredictor
        labels = self._labels(blocks)
        mapping = DOCTR_LABELS
        direction = 'ltr' if self.language == 'en' else 'auto'
        indices = ReadingOrderPredictor(direction=direction)(boxes, labels=[mapping.get(x,x) for x in labels],
                    texts=[b['text'] or '' for b in blocks], language=self.language,
                    page_shape=(page['height'],page['width']))
        require_permutation(indices, list(range(len(blocks))))
        return dict(ordered_ids=[blocks[i]['id'] for i in indices], native={'indices':indices},
                    transformations={'direction':direction,'category_map':mapping})

    def _docling(self, blocks, page, boxes):
        from .docling_contract import source_cids,CID_CONTRACT
        cids=source_cids(blocks,page['page_idx'])
        cid_to_id={cid:block['id'] for cid,block in zip(cids,blocks)}
        cid_to_index={cid:i for i,cid in enumerate(cids)}
        from docling.models.postprocessing.reading_order_rb import ReadingOrderPredictor, PageElement
        from docling_core.types.doc import CoordOrigin, DocItemLabel, Size
        labels = self._labels(blocks)
        names = DOCLING_LABELS
        elements = [PageElement(cid=cids[i],ref={'cref':'#/texts/'+str(cids[i])},l=float(box[0]*page['width']),
                    t=float(box[1]*page['height']),r=float(box[2]*page['width']),b=float(box[3]*page['height']),
                    coord_origin=CoordOrigin.TOPLEFT,page_no=page['page_idx']+1,
                    page_size=Size(width=page['width'],height=page['height']),text=b['text'] or '',
                    label=getattr(DocItemLabel,names[labels[i]])) for i,(b,box) in enumerate(zip(blocks,boxes))]
        ordered = ReadingOrderPredictor().predict_reading_order(elements)
        ordered_cids = [e.cid for e in ordered]
        require_permutation(ordered_cids,cids)
        indices=[cid_to_index[cid] for cid in ordered_cids]
        return dict(ordered_ids=[cid_to_id[cid] for cid in ordered_cids],native={'indices':indices,
                    'cids':ordered_cids,'cid_to_id':{str(cid):identity for cid,identity in cid_to_id.items()},
                    'temporary_ref_to_id':{'#/texts/'+str(cid):identity for cid,identity in cid_to_id.items()}},
                    transformations={'coordinates':'page points top-left','category_map':names,
                                     'cid_contract':CID_CONTRACT,'cid_prior':'MinerU source adjacency; not semantic ground truth',
                                     'caption_association_or_merge':False})

    def _hantian(self, blocks, page, boxes):
        import torch
        from transformers import LayoutLMv3ForTokenClassification
        if self.model is None:
            self.model, loading = LayoutLMv3ForTokenClassification.from_pretrained(
                self.environment/'models/hantian',local_files_only=True,use_safetensors=True,output_loading_info=True)
            if any(loading.get(k) for k in ('missing_keys','unexpected_keys','mismatched_keys','error_msgs')):
                raise ValueError('Checkpoint loading was not exact')
            self.model = self.model.eval().to('cuda')
            self.helper = _module(self.environment/'hantian_helpers.py','hantian_original')
        validate_length(len(blocks), min(510,self.model.config.max_position_embeddings-2))
        integer_boxes = (boxes*1000).round().astype(int).tolist()
        inputs = self.helper.prepare_inputs(self.helper.boxes2inputs(integer_boxes),self.model)
        with torch.inference_mode():
            logits = self.model(**inputs).logits.cpu().squeeze(0)
        if not torch.isfinite(logits).all():
            raise ValueError('Non-finite logits')
        ranks = self.helper.parse_logits(logits,len(blocks))
        native={'ranks':ranks}
        if self.capture_diagnostics:native.update(hantian_diagnostics(logits,len(blocks)))
        return dict(ordered_ids=ranks_to_ids(ranks,[b['id'] for b in blocks]),native=native,
                    transformations={'coordinates':'0..1000 rounded','decoder':'published hantian parse_logits'})

    def _pp_doclayout_v2(self, blocks, page, boxes):
        import torch
        from safetensors.torch import load_file
        from transformers import AutoConfig, PPDocLayoutV2ReadingOrder, PPDocLayoutV2ImageProcessor
        labels = self._labels(blocks)
        if self.model is None:
            self.config = AutoConfig.from_pretrained(self.environment/'models/pp_doclayout_v2',local_files_only=True)
            self.model = PPDocLayoutV2ReadingOrder(self.config.reading_order_config)
            state = load_file(str(self.environment/'models/pp_doclayout_v2/model.safetensors'))
            state = {k.removeprefix('reading_order.'):v for k,v in state.items() if k.startswith('reading_order.')}
            expected = set(self.model.state_dict())
            missing = expected-set(state)
            if set(state)-expected or missing-{'encoder.rel_pos_x_bias.weight','encoder.rel_pos_y_bias.weight'}:
                raise ValueError('Unexpected checkpoint key mismatch')
            self.model.load_state_dict(state,strict=False)
            self.model = self.model.eval().to('cuda')
        validate_length(len(blocks),self.config.reading_order_config.max_position_embeddings-2)
        categories = PP_CATEGORY_NAMES
        class_ids = []
        for label in labels:
            name = categories.get(label,label)
            options = [int(k) for k,v in self.config.id2label.items() if v == name]
            if not options:
                return dict(status='UNSUPPORTED', ordered_ids=None, reason='unmapped_category:'+name,
                            native={'category':name})
            class_ids.append(self.config.class_order[min(options)])
        with torch.inference_mode():
            logits = self.model(boxes=torch.tensor((boxes*1000).round().astype(int),device='cuda').unsqueeze(0),
                       labels=torch.tensor([class_ids],device='cuda'),
                       mask=torch.ones((1,len(blocks)),dtype=torch.bool,device='cuda'))
        if not torch.isfinite(logits).all():
            raise ValueError('Non-finite pair logits')
        # Upstream helper returns a rank for every input element, not ordered IDs.
        ranks = PPDocLayoutV2ImageProcessor()._get_order_seqs(logits).cpu().tolist()[0]
        return dict(ordered_ids=ranks_to_ids(ranks,[b['id'] for b in blocks]),
                    native={'pair_logits':logits.cpu().tolist()[0],'ranks':ranks},
                    transformations={'coordinates':'0..1000 rounded','mapped_class_ids':class_ids,
                                     'decoder':'Transformers PPDocLayoutV2ImageProcessor._get_order_seqs'})

    def _xycut_plus_plus(self, blocks, page, boxes):
        labels = self._labels(blocks)
        semantic = {'title':1,'heading':1,'image':2,'chart':2,'table':2,'index':0}
        lines = []
        for index,(b,box,label) in enumerate(zip(blocks,boxes,labels)):
            values = [box[0]*page['width'],box[1]*page['height'],box[2]*page['width'],box[3]*page['height']]
            lines.append(' '.join(map(str,[index,*values,semantic.get(label,0)])))
        request = str(page['width'])+' '+str(page['height'])+'\n'+'\n'.join(lines)
        output = subprocess.run([str(self.environment/'xy-worker/target/release/order-memory-worker')],
                                input=request,capture_output=True,text=True,timeout=120,check=True)
        indices = json.loads(output.stdout)
        require_permutation(indices,list(range(len(blocks))))
        return dict(ordered_ids=[blocks[i]['id'] for i in indices],native={'indices':indices},
                    transformations={'coordinates':'page points','semantic_labels':semantic,
                                     'implementation':'home-still/xycut-plus-plus','paper_fidelity':'diverges_from_paper_v1'})
