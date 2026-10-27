"""T0 metadata checks only: no tensor data, model imports or inference."""
import re


def validate_execution_lock(item):
    """A server-declared digest alone does not prove a local weights file."""
    if not re.fullmatch(r'[0-9a-f]{40}',item.get('revision') or ''):
        raise ValueError('immutable revision required')
    if not re.fullmatch(r'[0-9a-f]{64}',item.get('sha256') or ''):
        raise ValueError('SHA256 required')
    if item.get('locally_verified') is not True:
        raise ValueError('local artifact verification required before loading')


def expected_shapes(config):
    """Static shapes from the pinned original LayoutlmForSeq2SeqDecoder source.

    Includes pooler and relationship head: no missing-parameter waiver is applied.
    A change to that acceptance contract needs a separate explicit decision.
    """
    h=config['hidden_size'];f=config['intermediate_size'];out={}
    prefix='bert.embeddings.'
    for name,count in [('word',config['vocab_size']),('position',config['max_position_embeddings']),
                       ('token_type',config['type_vocab_size']),
                       *[(k+'_position',config['max_2d_position_embeddings']) for k in ('x','y','h','w')]]:
        out[prefix+name+'_embeddings.weight']=[count,h]
    for suffix in ('weight','bias'):out[prefix+'LayerNorm.'+suffix]=[h]
    for i in range(config['num_hidden_layers']):
        p=f'bert.encoder.layer.{i}.'
        for name in ('query','key','value'):
            out[p+'attention.self.'+name+'.weight']=[h,h]
            out[p+'attention.self.'+name+'.bias']=[h]
        for name in ('attention.output','output'):
            out[p+name+'.dense.weight']=[h,h if name=='attention.output' else f]
            out[p+name+'.dense.bias']=[h]
            for suffix in ('weight','bias'):out[p+name+'.LayerNorm.'+suffix]=[h]
        out[p+'intermediate.dense.weight']=[f,h]
        out[p+'intermediate.dense.bias']=[f]
    out['bert.pooler.dense.weight']=[h,h];out['bert.pooler.dense.bias']=[h]
    out['cls.seq_relationship.weight']=[2,h];out['cls.seq_relationship.bias']=[2]
    out['cls.predictions.bias']=[config['max_source_length']]
    out['cls.predictions.transform.dense.weight']=[h,h]
    for name in ('dense.bias','LayerNorm.weight','LayerNorm.bias'):
        out['cls.predictions.transform.'+name]=[h]
    return out


def check_header(header,config):
    expected=expected_shapes(config);actual={k:v for k,v in header.items() if k!='__metadata__'}
    missing=sorted(set(expected)-set(actual));extra=sorted(set(actual)-set(expected));mismatches=[]
    for k in sorted(set(expected)&set(actual)):
        if actual[k].get('shape')!=expected[k] or actual[k].get('dtype')!='F32':
            mismatches.append(dict(key=k,expected_shape=expected[k],actual=actual[k]))
    return dict(strict_compatible=not missing and not mismatches and not extra,expected_tensors=len(expected),
                actual_tensors=len(actual),missing=missing,extra=extra,mismatches=mismatches,
                weight_bytes_read=False,model_instantiated=False)
