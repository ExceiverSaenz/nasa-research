from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import urlsplit,parse_qs
from .reviews import ReviewStore
from .viewer import ViewerData


def authorized(client, host, origin, token, expected, port, writing=False):
    allowed = {f'127.0.0.1:{port}',f'localhost:{port}'}
    return (client in ('127.0.0.1','::1') and host in allowed
            and (not writing or (origin=='http://'+host and bool(token) and secrets.compare_digest(token,expected))))


def make_server(run_path, port=8765):
    store = ReviewStore(run_path)
    viewer = ViewerData(run_path)
    token = secrets.token_urlsafe(32)
    assets = Path(__file__).parent/'viewer'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def send(self, value, status=200, kind='application/json'):
            raw = json.dumps(value).encode() if kind=='application/json' else value
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; style-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def permitted(self,writing=False):
            return authorized(self.client_address[0],self.headers.get('Host'),self.headers.get('Origin'),
                              self.headers.get('X-Review-Token'),token,self.server.server_port,writing)

        def do_GET(self):
            if not self.permitted():
                return self.send({'error':'forbidden'},403)
            parsed = urlsplit(self.path)
            try:
                if parsed.path=='/api/state':
                    return self.send(dict(run=viewer.run,reviews=store.load(),token=token,run_sha256=store.run_sha256))
                if parsed.path=='/api/page':
                    query = parse_qs(parsed.query)
                    return self.send(viewer.page(query['paper'][0],int(query['page'][0])))
                if parsed.path.startswith('/asset/'):
                    _,_,paper,index = parsed.path.split('/')
                    return self.send(viewer.asset(paper,int(index)).read_bytes(),kind='image/png')
                name = {'/':'index.html','/app.js':'app.js','/style.css':'style.css'}.get(parsed.path)
                if name:
                    return self.send((assets/name).read_bytes(),kind={'index.html':'text/html; charset=utf-8','app.js':'text/javascript','style.css':'text/css'}[name])
                return self.send({'error':'not_found'},404)
            except (KeyError,ValueError,FileNotFoundError):
                return self.send({'error':'unavailable_registered_resource'},404)

        def do_PUT(self):
            if not self.permitted(True):
                return self.send({'error':'forbidden'},403)
            try:
                if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    raise ValueError('JSON body required')
                length = int(self.headers.get('Content-Length','0'))
                if not 0<length<=1024*1024:
                    return self.send({'error':'body_limit'},413)
                value = json.loads(self.rfile.read(length))
                if self.path=='/api/reviews':
                    result = store.save(value['observation'],value['expected_revision'])
                elif self.path=='/api/import':
                    result = store.import_data(value['data'],value['expected_revision'])
                else:
                    return self.send({'error':'not_found'},404)
                return self.send(result)
            except (KeyError,ValueError,TypeError,json.JSONDecodeError):
                return self.send({'error':'identity_validation_or_revision_conflict'},409)
            except OSError:
                return self.send({'error':'storage_failure'},500)
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def serve(run_path,host='127.0.0.1',port=8765):
    if host!='127.0.0.1':
        raise ValueError('Only loopback is allowed')
    server = make_server(run_path,port)
    print(f'http://127.0.0.1:{server.server_port}',flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
