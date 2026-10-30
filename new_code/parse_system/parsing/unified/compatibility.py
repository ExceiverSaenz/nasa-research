"""Guarded image-only LayoutLMv3 port; only a new runtime copy is modified.

No AutoConfig registration, tokenizer, trainer or language head is needed by the
PubLayNet image-only backbone. Legacy numerical attention-mask semantics remain
explicit rather than relying on removed Transformers internals.
"""
import json
from pathlib import Path
import shutil
from .environment import sha256, verify_files

SOURCE_HASHES={
'layoutlmv3/layoutlmft/__init__.py':'0b837d81726bee2b3bbb39ef41e7d0edd3a1973121769f3a2e087eee9d18fb4f',
'layoutlmv3/layoutlmft/models/__init__.py':'7796e6dd1c7e8d3ae07c90d6af30fbb7947909d1dfba0f5d08dbd4127788616e',
'layoutlmv3/layoutlmft/models/layoutlmv3/__init__.py':'d595eb07c99ae987011a049b291d2286a65d2ab7739bf05922392b4a31bbc33a',
'layoutlmv3/layoutlmft/models/layoutlmv3/modeling_layoutlmv3.py':'99da3cb4ef83ac972fd0b6e4f4fa7df27dcd41760e9c51725d05a353bb77e640',
'layoutlmv3/examples/object_detection/ditod/__init__.py':'3a374eae41d78b8565e77a5ef477a44b4a087914425bb007e7f7056cb89f8736',
'layoutlmv3/examples/object_detection/ditod/backbone.py':'1ec7432fcca553b7bd203c622f6c4b8badc95f3d811037d36b816ba744cffc5a'}


def legacy_head_mask(mask, layers):
    if mask is not None: raise ValueError('Head masking is outside the preserved image-only contract')
    return [None]*layers


def legacy_attention_mask(mask, dtype):
    """Transform the image-only 2-D keep mask as Transformers 4.12 did."""
    if mask.ndim!=2: raise ValueError('Image-only attention mask must be a matrix')
    return (1.0-mask[:,None,None,:].to(dtype=dtype))*-10000.0


def _replace(text, old, new):
    if text.count(old)!=1: raise ValueError('Compatibility source anchor changed: '+old[:80])
    return text.replace(old,new)


def prepare_vendor(source: Path, destination: Path):
    source=Path(source).resolve(strict=True); destination=Path(destination).absolute()
    if destination.exists() or destination.is_relative_to(source): raise ValueError('Vendor copy must be new and outside source')
    for name,digest in SOURCE_HASHES.items():
        if not (source/name).is_file() or sha256(source/name)!=digest:
            raise ValueError('Unsupported vendor source: '+name)
    replacements={
        'layoutlmv3/layoutlmft/__init__.py':'# Image-only runtime; language entry points intentionally excluded.\n',
        'layoutlmv3/layoutlmft/models/__init__.py':'# Image-only runtime.\n',
        'layoutlmv3/layoutlmft/models/layoutlmv3/__init__.py':
        'from .configuration_layoutlmv3 import LayoutLMv3Config\nfrom .modeling_layoutlmv3 import LayoutLMv3Model\n',
        'layoutlmv3/examples/object_detection/ditod/__init__.py':
        'from .config import add_vit_config\nfrom .backbone import build_vit_fpn_backbone\nfrom .rcnn_vl import VLGeneralizedRCNN\n'}
    name='layoutlmv3/examples/object_detection/ditod/backbone.py'
    text=(source/name).read_text(encoding='utf-8')
    text=_replace(text,'from transformers import AutoConfig','from layoutlmft.models.layoutlmv3 import LayoutLMv3Config')
    text=_replace(text,'config = AutoConfig.from_pretrained(config_path)',
                  'config = LayoutLMv3Config.from_pretrained(config_path, local_files_only=True)')
    replacements[name]=text
    name='layoutlmv3/layoutlmft/models/layoutlmv3/modeling_layoutlmv3.py'
    text=(source/name).read_text(encoding='utf-8')
    text=_replace(text,'from transformers import apply_chunking_to_forward',
                  'from parsing.unified.legacy_layers import apply_chunking_to_forward')
    text=_replace(text,'from transformers.modeling_utils import PreTrainedModel, find_pruneable_heads_and_indices, prune_linear_layer',
                  'from transformers.modeling_utils import PreTrainedModel\nfrom parsing.unified.legacy_layers import find_pruneable_heads_and_indices, prune_linear_layer')
    text=_replace(text,'from transformers.models.roberta.modeling_roberta import (',
                  'from parsing.unified.legacy_layers import (')
    text=_replace(text,'self.get_extended_attention_mask(attention_mask, None, device)',
                  'legacy_attention_mask(attention_mask, self.dtype)')
    text=_replace(text,'self.get_head_mask(head_mask, self.config.num_hidden_layers)',
                  'legacy_head_mask(head_mask, self.config.num_hidden_layers)')
    text=_replace(text,'self.init_weights()\n\n    def get_input_embeddings',
                  'self.post_init()\n\n    def get_input_embeddings')
    text=_replace(text,'from timm.models.layers import to_2tuple',
                  'from timm.layers import to_2tuple\nfrom parsing.unified.compatibility import legacy_attention_mask, legacy_head_mask')
    replacements[name]=text
    # Compute and validate every edit before creating anything.
    for name,text in replacements.items(): compile(text,name,'exec')
    temporary=destination.with_name(destination.name+'.preparing')
    if temporary.exists(): raise ValueError('Unfinished vendor preparation exists')
    shutil.copytree(source,temporary,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git'))
    try:
        for name,text in replacements.items(): (temporary/name).write_text(text,encoding='utf-8',newline='\n')
        files={p.relative_to(temporary).as_posix():{'bytes':p.stat().st_size,'sha256':sha256(p)}
               for p in temporary.rglob('*') if p.is_file()}
        receipt={'adaptation':'unified-image-only-v1','source':str(source),'guarded_sources':SOURCE_HASHES,
                 'changed_files':sorted(replacements),'files':files,
                 'runtime_import_validation':'pending','numerical_regression':'pending'}
        (temporary/'unified-vendor.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        temporary.rename(destination)
    except Exception:
        # Preserve partial evidence; never delete a source tree on failure.
        raise
    return destination


def verify_vendor(path):
    path=Path(path).resolve(strict=True)
    receipt=json.loads((path/'unified-vendor.json').read_text(encoding='utf-8'))
    if receipt['adaptation']!='unified-image-only-v1' or receipt['guarded_sources']!=SOURCE_HASHES:
        raise ValueError('Unsupported vendor adaptation')
    verify_files(path,receipt['files'])
    return path
