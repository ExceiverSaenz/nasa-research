"""Start the tool: python -B -m value_review [--port N] [--no-browser] [--data DIR].

One process, one uvicorn worker, bound to 127.0.0.1 only (AC-20). A second instance on the same data
folder, or a taken port, stops with a clear message. The browser opens once the service is ready.
Mirrors parsing_validator/__main__.py (ADR-001).
"""
import argparse
import os
import socket
import sys
import threading
import time
import webbrowser

DEFAULT_PORT = 8766
PORT_VARIABLE = 'VALUE_REVIEW_PORT'
HOST = '127.0.0.1'


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex((HOST, port)) != 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -B -m value_review')
    parser.add_argument('--port', type=int, default=int(os.environ.get(PORT_VARIABLE, DEFAULT_PORT)))
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--data', help='data folder holding originals/, annotations/ and cache/ (default value_review/)')
    args = parser.parse_args(argv)

    import uvicorn
    from .service.app import create_app
    from .service.config import Config
    from .storage import InstanceLock, StorageError, remove_leftover_temporaries
    from .storage.files import AnnotationStore

    config = Config(port=args.port, **({'data': args.data} if args.data else {}))
    store = AnnotationStore(config.annotations)
    try:
        lock = InstanceLock(store.lock_path).acquire()
    except StorageError as error:
        print(f'Tensile Value Review is already running on this data folder ({error}). Close it first.', file=sys.stderr)
        return 2
    try:
        for folder in (store.folder / 'drafts', store.folder, *store.folder.glob('versions/*')):
            if folder.is_dir():
                remove_leftover_temporaries(folder)
        if not port_is_free(args.port):
            print(f'Port {args.port} is in use. Close what uses it, or choose another with --port or {PORT_VARIABLE}.', file=sys.stderr)
            return 2
        server = uvicorn.Server(uvicorn.Config(create_app(config), host=HOST, port=args.port, workers=1,
                                               log_level='warning', access_log=False))
        url = f'http://{HOST}:{args.port}/'
        print(f'Tensile Value Review on {url}  (Ctrl+C to stop)', flush=True)
        if not args.no_browser:
            def open_when_ready():
                while not server.started and not server.should_exit:
                    time.sleep(0.1)
                if server.started:
                    webbrowser.open(url)
            threading.Thread(target=open_when_ready, daemon=True).start()
        server.run()
        return 0
    finally:
        lock.release()


if __name__ == '__main__':
    sys.exit(main())
