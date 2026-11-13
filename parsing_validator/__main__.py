"""Start the tool: ``python -m parsing_validator [--port N] [--no-browser]`` (OQ-10, ADR-001).

One process, one uvicorn worker, bound to 127.0.0.1 only. A second instance, or a taken port, stops with a clear
message instead of choosing another port. The browser tab opens once the service is ready.
"""
import argparse
import os
import socket
import sys
import threading
import time
import webbrowser

DEFAULT_PORT = 8765
PORT_VARIABLE = 'PARSING_VALIDATOR_PORT'
HOST = '127.0.0.1'


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex((HOST, port)) != 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m parsing_validator')
    parser.add_argument('--port', type=int, default=int(os.environ.get(PORT_VARIABLE, DEFAULT_PORT)))
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)

    import uvicorn
    from .service.app import create_app
    from .service.config import Config
    from .storage.atomic import InstanceLock, StorageError

    from .service import settings as settings_module
    config = Config(port=args.port)
    stored, _ = settings_module.load(config)          # folders saved in Settings apply from this start on
    for name, key in (('collection', 'results'), ('pdfs', 'pdfs'), ('originals', 'originals'), ('annotations', 'annotations')):
        setattr(config, name, type(config.pdfs)(stored['paths'][key]))
    try:
        lock = InstanceLock(config.annotations / 'parsing-validator.lock').acquire()
    except StorageError as error:
        print(f'Parsing Validator is already running ({error}). Close it first.', file=sys.stderr)
        return 2
    try:
        if not port_is_free(args.port):
            print(f'Port {args.port} is in use. Close what uses it, or choose another with --port or {PORT_VARIABLE}.',
                  file=sys.stderr)
            return 2
        server = uvicorn.Server(uvicorn.Config(create_app(config), host=HOST, port=args.port, workers=1,
                                               log_level='warning', access_log=False))
        url = f'http://{HOST}:{args.port}/'
        print(f'Parsing Validator on {url}  (Ctrl+C to stop)', flush=True)
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
