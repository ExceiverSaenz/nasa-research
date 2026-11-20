import json, sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / 'src/code'))
from mineru_contracts import ObjectPointer, ReferenceResolver
from mineru_observed_geometry import _EvidenceCache
from mineru_collection import CollectionRepository
R = lambda v: v if isinstance(v, ObjectPointer) else ObjectPointer(**v)
coll = CollectionRepository(str(ROOT / 'src/raw_results/code_results/tensile_papers'))


def texts(c):
    out = []
    for x in c or []:
        if isinstance(x, str): out.append(x)
        elif isinstance(x, dict):
            if isinstance(x.get('content'), list): out.extend(texts(x['content']))
            elif isinstance(x.get('content'), str): out.append(x['content'])
    return out


def kind(ch):
    o = ord(ch)
    if o == 0xFFFD: return 'U+FFFD'
    if o < 32 and ch not in '\n\t\r': return 'control'
    if 0x7F <= o <= 0x9F: return 'c1-control'
    if 0xE000 <= o <= 0xF8FF: return 'private-use'
    return None


tot = collections.Counter(); chars = collections.Counter(); per = {}; examples = []
for n in coll.papers():
    b = coll.bindings(n); resolve = ReferenceResolver(_EvidenceCache(coll.store)).resolve
    nat = resolve(R(b['native_document'])); doc = nat.get('document', nat)
    c = collections.Counter()
    for pg in doc['pages']:
        for blk in pg['blocks']:
            body = blk.get('content')
            ts = texts(body) if isinstance(body, list) else ([body] if isinstance(body, str) and blk['type'] == 'equation' else [])
            bad = False
            for t in ts:
                for ch in t:
                    k = kind(ch)
                    if k: bad = True; chars[(k, hex(ord(ch)))] += 1
            c['text_blocks'] += 1
            if bad:
                c['blocks_with_odd_chars'] += 1
                if len(examples) < 3: examples.append((n, pg['page_idx'], blk['type'], ''.join(ts)[:70]))
    per[n] = dict(c); tot.update(c)
print('total:', dict(tot))
print('top chars:', chars.most_common(12))
print('papers with odd chars:', sorted((int(k), v.get('blocks_with_odd_chars', 0)) for k, v in per.items() if v.get('blocks_with_odd_chars')))
print('examples:', [(a, b, c, repr(d)) for a, b, c, d in examples])
