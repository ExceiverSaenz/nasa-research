"""Synthetic fixture server for real browser tests. No PDFs or external services."""
import argparse
import base64
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code'))
sys.path.insert(0,str(ROOT/'analytics'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8876)
    args = parser.parse_args()
    args.root.mkdir(parents=True,exist_ok=False)
    from test_integration import synthetic_run
    from reading_order.server import serve
    run = synthetic_run(args.root)
    # A synthetic white pixel, generated only for this test fixture.
    pages = args.root/'source/viewer_source/pages'/('a'*64)
    pages.mkdir(parents=True)
    image = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jH2kAAAAASUVORK5CYII=')
    for index in (0,1):
        (pages/(str(index)+'.png')).write_bytes(image)
    serve(run,port=args.port)


if __name__=='__main__':
    main()
