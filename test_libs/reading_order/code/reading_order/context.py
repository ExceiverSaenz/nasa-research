import hashlib
import random


def permute(ids, seed):
    items = sorted(ids, key=lambda value: hashlib.sha256(value.encode()).digest())
    if seed is not None:
        random.Random(seed).shuffle(items)
    return items


def project(order, members):
    return [item for item in order if item in members]


def validate_parents(parents):
    for start in parents:
        seen = set()
        current = start
        while current is not None:
            if current in seen or current not in parents:
                raise ValueError('Cyclic or unresolved parent hierarchy')
            seen.add(current)
            current = parents[current]


def validate_context(ids, routes=None, groups=None):
    known = set(ids)
    if routes and not set(routes).issubset(known):
        raise ValueError('Unknown routed IDs')
    for members in (groups or {}).values():
        if len(set(members)) != len(members) or not set(members).issubset(known):
            raise ValueError('Unknown or duplicate group members')


make_permutation = permute
