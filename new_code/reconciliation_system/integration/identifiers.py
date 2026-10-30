"""Safe collection path identities; original PDF hashes remain scientific identity."""
import re

def valid_paper_id(value):
    return (type(value) is int and value > 0) or (isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',value) is not None)
