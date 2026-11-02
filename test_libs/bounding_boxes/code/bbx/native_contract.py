"""CPU-only gate for MinerU 4.0.12's DocVortex span-owner calling convention."""
import importlib.metadata
import json


def validate_owner(owner):
    # Preserve the single (start, end) range passed by MinerU 4.0.12. Calling
    # the real binding catches the incompatible plural-range ABI in >=0.6.8.
    result=owner.prepare_span_texts([],10.,[],[],.5,['\r','\n'],{},.5,(0xE000,0xF8FF),[])
    if result is not None and result!=[]:
        raise ValueError('Unexpected empty-span contract result')
    return {'schema':'mineru-native-contract/1','status':'PASS',
            'scope':'typed native argument conversion only; not parser/model inference'}


def probe():
    if importlib.metadata.version('mineru')!='4.0.12':
        raise ValueError('Review this version-specific native contract before changing MinerU')
    import pypdfium2 as pdfium
    from docvortex.document.pdf.snapshot_bridge import read_text_snapshot
    doc=pdfium.PdfDocument.new();page=None;textpage=None
    try:
        page=doc.new_page(100,100);textpage=page.get_textpage()
        owner=read_text_snapshot(textpage,[0.,0.,100.,100.],0,True)
        if owner is None:raise RuntimeError('Real native text snapshot unavailable')
        result=validate_owner(owner)
        result['versions']={n:importlib.metadata.version(n) for n in ('mineru','docvortex','pypdfium2')}
        return result
    finally:
        if textpage is not None:textpage.close()
        if page is not None:page.close()
        doc.close()


if __name__=='__main__':
    print(json.dumps(probe()))
