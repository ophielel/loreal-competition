"""Local competition demo server; binds loopback only and serves an explicit file allowlist."""
import argparse
import json
import mimetypes
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from src.engine import analyze, snapshot
from src.model import configured, enhance
from src.store import list_tasks, create_task, complete_task

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / 'data/dataset.json').read_text(encoding='utf-8'))
SESSIONS = {s['id']: s for s in DATA['sessions']}


class Handler(BaseHTTPRequestHandler):
    def response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        super().end_headers()

    def valid_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def get_session(self, sid, cursor):
        if sid not in SESSIONS:
            raise KeyError('会话不存在')
        s = SESSIONS[sid]
        if cursor < 0 or cursor > len(s['messages']) + 1:
            raise ValueError('回放位置越界')
        return s

    def do_GET(self):
        if not self.valid_host():
            return self.response({'error': '无效主机'}, 403)
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == '/api/overview':
                listing = []
                for s in SESSIONS.values():
                    # Reception list uses first-message analysis, never later customer text.
                    a = analyze(s, 1)
                    listing.append({'id': s['id'], 'buyer': s['buyer'], 'count': len(s['messages']),
                                    'first': s['messages'][0]['text'], 'time': s['messages'][0]['time'],
                                    'intent': a['intent'], 'priority': a['priority']})
                return self.response({'meta': DATA['meta'], 'sessions': listing, 'model_configured': configured()})
            if parsed.path == '/api/session':
                sid = query.get('id', [''])[0]
                cursor = int(query.get('cursor', ['1'])[0])
                s = self.get_session(sid, cursor)
                return self.response({'session': snapshot(s, cursor), 'analysis': analyze(s, cursor), 'total': len(s['messages'])})
            if parsed.path == '/api/tasks':
                return self.response({'tasks': list_tasks()})
            if parsed.path == '/api/evaluation':
                path = ROOT / 'data/evaluation.json'
                return self.response(json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'pending': True})
            files = {'/': 'index.html', '/index.html': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
            if parsed.path not in files:
                return self.response({'error': '页面不存在'}, 404)
            file = ROOT / 'web' / files[parsed.path]
            content = file.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', (mimetypes.guess_type(file.name)[0] or 'text/plain') + '; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except (ValueError, KeyError):
            self.response({'error': '会话或回放参数无效'}, 400)

    def do_POST(self):
        origin = self.headers.get('Origin')
        if not self.valid_host() or (origin and origin not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}')):
            return self.response({'error': '拒绝跨站请求'}, 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 16000 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('无效请求')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('请求必须为对象')
            if self.path == '/api/analyze':
                cursor = int(body.get('cursor', 1))
                s = self.get_session(body.get('id'), cursor)
                return self.response(enhance(s, cursor, analyze(s, cursor)))
            if self.path == '/api/tasks':
                cursor = int(body.get('cursor', 1))
                s = self.get_session(body.get('id'), cursor)
                title, note = body.get('title', ''), body.get('note', '')
                if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100 or not isinstance(note, str) or len(note) > 2000:
                    raise ValueError('任务字段无效')
                return self.response(create_task(s['id'], cursor, title.strip(), note), 201)
            if self.path == '/api/tasks/complete':
                task = complete_task(int(body.get('task_id', 0)))
                return self.response(task if task else {'error': '任务不存在'}, 200 if task else 404)
            return self.response({'error': '接口不存在'}, 404)
        except (ValueError, TypeError, KeyError):
            self.response({'error': '请求参数无效'}, 400)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Beauty Care Copilot: http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()
