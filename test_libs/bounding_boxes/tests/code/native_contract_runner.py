"""CPU characterization against real published binaries, without installing ML stacks."""
import ast
import ctypes as ct
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import zipfile

import pypdfium2 as pdfium
import pypdfium2.raw as raw


def run(wheel, scratch, pdf=None, use_gate=False):
    wheel=Path(wheel);scratch=Path(scratch);scratch.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(wheel) as z:
        for name in z.namelist():
            if name.startswith('docvortex/') and not name.endswith('/'):
                target=(scratch/name).resolve()
                assert target.is_relative_to(scratch.resolve())
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
        binary=scratch/'docvortex/_native.pyd'
        source=z.read('docvortex/document/pdf/snapshot_bridge.py').decode()
    # The binary imports its own real Bbox types. Namespace packages avoid
    # importing unrelated Office/ML converters during this narrow ABI test.
    for name in ('docvortex','docvortex.document','docvortex.document.pdf','docvortex.document.pdf.text'):
        module=types.ModuleType(name);module.__path__=[str(scratch/Path(*name.split('.')))];sys.modules[name]=module
    spec=importlib.util.spec_from_file_location('docvortex._native',binary)
    native=importlib.util.module_from_spec(spec);sys.modules[spec.name]=native;spec.loader.exec_module(native)
    # Use the wheel's own ABI validation and symbol ordering, not guessed C pointers.
    functions=[n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name in ('_standard_character_symbols','_color_symbols')]
    assert len(functions)==2
    namespace={'ct':ct,'raw':raw}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(wheel)+'#snapshot_bridge','exec'),namespace)
    chars,reason=namespace['_standard_character_symbols']();assert chars is not None,reason
    colors,reason=namespace['_color_symbols']();assert colors is not None,reason
    doc=pdfium.PdfDocument(str(pdf)) if pdf else pdfium.PdfDocument.new()
    page=doc[0] if pdf else doc.new_page(100,100)
    textpage=page.get_textpage()
    try:
        w,h=page.get_size()
        owner=native.read_pdfium_text_snapshot(chars[1],colors[1],ct.cast(textpage.raw,ct.c_void_p).value,textpage.count_chars(),True,[0.,0.,float(w),float(h)],0,None)
        assert owner is not None
        # Exact single-range calling convention of MinerU 4.0.12. Empty spans
        # have a literal empty output; argument conversion still occurs in Rust.
        if use_gate:
            sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())/'code'))
            from bbx.native_contract import validate_owner
            proof=validate_owner(owner)
            assert proof['status']=='PASS'
            result=None
        else:
            result=owner.prepare_span_texts([],10.,[],[],.5,['\r','\n'],{},.5,(0xE000,0xF8FF),[])
        # Unprepared optional geometry may select the Python-reference path.
        # This probe checks typed ABI acceptance, not end-to-end text parsing.
        assert result is None or result==[],result
        return {'status':'PASS','native_signature':native.NativeTextSnapshot.prepare_span_texts.__text_signature__,'raw_char_count':textpage.count_chars(),'snapshot_bridge_sha256':hashlib.sha256(source.encode()).hexdigest()}
    finally:
        textpage.close();page.close();doc.close()


if __name__=='__main__':
    print(json.dumps(run(sys.argv[1],sys.argv[2],sys.argv[3] if len(sys.argv)>3 else None,'--gate' in sys.argv)))
