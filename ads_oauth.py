"""One-time OAuth dance for the Google Ads API (real keyword volumes).

Flow: this script listens on 127.0.0.1:8765, prints an auth URL, you
open it in a browser signed in as a test user on the consent screen
and approve, Google redirects back to localhost with a code, and
we exchange it for a refresh token saved to .google-ads.yaml (0600).

Usage:
  1. .venv/bin/python ads_oauth.py --serve   # prints URL, waits for callback
  2. (browser approves)
  3. script exchanges code, writes .google-ads.yaml, exits
"""
import http.server
import os
import socketserver
import sys
import threading
import urllib.parse

import requests

os.environ.setdefault("REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt")
HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}/callback"
SCOPES = ["https://www.googleapis.com/auth/adwords"]

# Manager account holding the Ads API access (dashes stripped for the API).
LOGIN_CUSTOMER_ID = "7121367015"


def _oauth():
    vals = {}
    for line in open(os.path.join(HERE, ".google-ads-oauth")):
        k, v = line.strip().split("=", 1)
        vals[k] = v
    return vals["client_id"], vals["client_secret"]


def auth_url(client_id):
    q = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    })
    return f"https://accounts.google.com/o/oauth2/v2/auth?{q}"


_code_holder = {}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in qs:
            _code_holder["code"] = qs["code"][0]
            body = b"OK - authorization received, you can close this tab."
        else:
            body = b"Missing code: " + self.path.encode()[:200]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main():
    client_id, client_secret = _oauth()
    url = auth_url(client_id)
    print("AUTH_URL=" + url)
    sys.stdout.flush()
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        httpd.timeout = 300
        t = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.5})
        t.daemon = True
        t.start()
        t.join(timeout=300)
        httpd.shutdown()
    code = _code_holder.get("code")
    if not code:
        print("TIMEOUT waiting for the OAuth callback.", file=sys.stderr)
        sys.exit(2)
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code, "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": REDIRECT, "grant_type": "authorization_code",
    }, timeout=60)
    r.raise_for_status()
    tok = r.json()
    cfg = (
        f"# Google Ads API config — generated {__import__('datetime').date.today()}\n"
        f"developer_token: \n"  # 2026: managed in Cloud Console; leave blank, fill if API demands it
        f"client_id: {client_id}\n"
        f"client_secret: {client_secret}\n"
        f"refresh_token: {tok['refresh_token']}\n"
        f"login_customer_id: {LOGIN_CUSTOMER_ID}\n"
        f"use_proto_plus: true\n"
    )
    p = os.path.join(HERE, ".google-ads.yaml")
    with open(p, "w") as f:
        f.write(cfg)
    os.chmod(p, 0o600)
    print("WROTE " + p)


if __name__ == "__main__":
    main()
