#!/usr/bin/env python3
"""Serve the fault fixture site, adding the faults that are HTTP behaviour
rather than markup: a 301 and a 404.

    python3 serve.py [port]

Binds 127.0.0.1 only. Used by tests/test_fixture_site.py, which starts and
stops it, but it runs standalone too if you want to click around it.
"""
import functools
import os
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')

# path -> (status, location). These are the faults a static file cannot carry.
REDIRECTS = {'/old-url/': (301, '/redirect-target/'),
             '/old-url': (301, '/redirect-target/')}
GONE = {'/gone/', '/gone'}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITE, **kw)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in REDIRECTS:
            status, location = REDIRECTS[path]
            self.send_response(status)
            self.send_header('Location', location)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if path in GONE:
            self.send_error(404, 'Not Found')
            return
        # /search/?q=x must serve the search page whatever the query string is.
        super().do_GET()

    def do_HEAD(self):
        path = self.path.split('?')[0]
        if path in REDIRECTS:
            status, location = REDIRECTS[path]
            self.send_response(status)
            self.send_header('Location', location)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if path in GONE:
            self.send_error(404, 'Not Found')
            return
        super().do_HEAD()

    def log_message(self, *a):
        pass  # keep the test output readable


def start(port=8099):
    """Start the server on a background thread. Returns (server, base_url)."""
    if not os.path.isdir(SITE):
        from build import build
        build(f'http://127.0.0.1:{port}')
    httpd = HTTPServer(('127.0.0.1', port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f'http://127.0.0.1:{port}'


if __name__ == '__main__':
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    srv, base = start(p)
    print(f'serving the fixture site at {base}  (ctrl-c to stop)')
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
