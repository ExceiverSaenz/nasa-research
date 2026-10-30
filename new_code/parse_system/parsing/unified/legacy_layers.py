"""Legacy parameter names/math used by the isolated image-only backbone.

These blocks retain the 4.12 Linear/LayerNorm/dropout ordering and state names.
Language heads and head-pruning are excluded by the image-only runtime contract.
Heavy imports occur only when the actual runtime loads the copied vendor.
"""
import torch
from torch import nn
from transformers.activations import ACT2FN

class RobertaSelfOutput(nn.Module):
    def __init__(self,config):
        super().__init__(); self.dense=nn.Linear(config.hidden_size,config.hidden_size)
        self.LayerNorm=nn.LayerNorm(config.hidden_size,eps=config.layer_norm_eps)
        self.dropout=nn.Dropout(config.hidden_dropout_prob)
    def forward(self, hidden_states, input_tensor):
        return self.LayerNorm(self.dropout(self.dense(hidden_states))+input_tensor)

class RobertaIntermediate(nn.Module):
    def __init__(self,config):
        super().__init__(); self.dense=nn.Linear(config.hidden_size,config.intermediate_size)
        self.intermediate_act_fn=ACT2FN[config.hidden_act] if isinstance(config.hidden_act,str) else config.hidden_act
    def forward(self,hidden_states): return self.intermediate_act_fn(self.dense(hidden_states))

class RobertaOutput(nn.Module):
    def __init__(self,config):
        super().__init__(); self.dense=nn.Linear(config.intermediate_size,config.hidden_size)
        self.LayerNorm=nn.LayerNorm(config.hidden_size,eps=config.layer_norm_eps)
        self.dropout=nn.Dropout(config.hidden_dropout_prob)
    def forward(self,hidden_states,input_tensor):
        return self.LayerNorm(self.dropout(self.dense(hidden_states))+input_tensor)

class RobertaLMHead(nn.Module):
    def __init__(self,*args,**kwargs):
        raise RuntimeError('Language heads are outside the unified image-only contract')

def find_pruneable_heads_and_indices(*args,**kwargs):
    raise RuntimeError('Head pruning is outside the preserved image-only contract')

def prune_linear_layer(*args,**kwargs):
    raise RuntimeError('Head pruning is outside the preserved image-only contract')

def apply_chunking_to_forward(forward_fn,chunk_size,chunk_dim,*input_tensors):
    if not input_tensors: raise ValueError('Input tensors required')
    size=input_tensors[0].shape[chunk_dim]
    if any(t.shape[chunk_dim]!=size for t in input_tensors): raise ValueError('Chunk dimensions differ')
    if chunk_size>0:
        if size%chunk_size: raise ValueError('Chunk size must divide tensor dimension')
        chunks=[t.chunk(size//chunk_size,dim=chunk_dim) for t in input_tensors]
        return torch.cat(tuple(forward_fn(*parts) for parts in zip(*chunks)),dim=chunk_dim)
    return forward_fn(*input_tensors)
