"""Minimal Bing Webmaster Tools API client.

Key in .bing-key (0600). Free. Gives a second opinion on top of Google:
top search queries and instant URL submission (handy after publishing a
new content entry). `pages()` and `crawl_stats()` are importable helpers;
the CLI exposes `queries` and `submit` only.

Usage: .venv/bin/python bing.py [--site <slug>] [submit <url>]
Site config lives in sites/<slug>.yaml (default: example).
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import requests

import site_config

os.environ.setdefault("REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt")
BASE = "https://ssl.bing.com/webmaster/api.svc/json"


def _site(slug=None):
    return site_config.load(slug)["site_url"]


def _key():
    with open(os.path.join(HERE, ".bing-key")) as f:
        return f.read().strip()


def _safe_error(e):
    """Redact the API key from an exception message (it rides in the URL)."""
    return re.sub(r"apikey=[^&\s]*", "apikey=REDACTED", str(e))


def _call(op, params=None, retries=2):
    """GET with two retries (exponential backoff) on 429/5xx."""
    import time
    last = None
    for attempt in range(retries + 1):
        r = requests.get(f"{BASE}/{op}", params={"apikey": _key(), **(params or {})},
                         timeout=60)
        if r.status_code < 500 and r.status_code != 429:
            try:
                r.raise_for_status()
            except requests.HTTPError as e:
                # Never let the raw URL (with key) escape in the message.
                raise requests.HTTPError(_safe_error(e), response=e.response)
            return r.json()
        last = r
        time.sleep(2 ** attempt)
    try:
        last.raise_for_status()  # always raises - no return after this
    except requests.HTTPError as e:
        raise requests.HTTPError(_safe_error(e), response=e.response)


def _post_with_retry(op, payload, retries=2):
    """POST with two retries (exponential backoff) on 429/5xx."""
    import time
    last = None
    for attempt in range(retries + 1):
        r = requests.post(f"{BASE}/{op}?apikey={_key()}", json=payload,
                          timeout=60)
        if r.status_code < 500 and r.status_code != 429:
            try:
                r.raise_for_status()
            except requests.HTTPError as e:
                raise requests.HTTPError(_safe_error(e), response=e.response)
            return r.json()
        last = r
        time.sleep(2 ** attempt)
    try:
        last.raise_for_status()  # always raises - no return after this
    except requests.HTTPError as e:
        raise requests.HTTPError(_safe_error(e), response=e.response)


def queries(limit=25, site=None):
    """Top search queries (impressions, clicks) - Bing's keyword data."""
    d = _call("GetQueryStats", {"siteUrl": _site(site)})
    rows = d.get("d", [])
    return rows[:limit]


def pages(limit=25, site=None):
    d = _call("GetPageStats", {"siteUrl": _site(site)})
    rows = d.get("d", [])
    return rows[:limit]


def submit_url(url, site=None):
    return _post_with_retry("SubmitUrlbatch",
                            {"siteUrl": _site(site), "urlList": [url]})


def crawl_stats(site=None):
    return _call("GetCrawlStats", {"siteUrl": _site(site)})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=None, help="site slug from sites/ (default: example)")
    ap.add_argument("action", nargs="?", default="queries", choices=["queries", "submit"],
                    help="queries = print top queries; submit = submit a URL for indexing")
    ap.add_argument("url", nargs="?", default=None, help="URL to submit (with 'submit')")
    args = ap.parse_args()
    try:
        if args.action == "submit":
            if not args.url:
                ap.error("'submit' requires a URL")
            print(submit_url(args.url, args.site))
        else:
            if args.url:
                print(f"Note: ignoring URL '{args.url}' - "
                      f"'url' is only used with 'submit'.", file=sys.stderr)
            qs = queries(site=args.site)
            print(f"Bing: top queries: {len(qs)}")
            for q in qs[:10]:
                print(f"- {q.get('Query', '')[:55]:55} | impr {q.get('Impressions', 0):6} | clicks {q.get('Clicks', 0)}")
    except FileNotFoundError:
        print("BING_UNAVAILABLE: .bing-key is missing - regenerate the API key "
              "in Bing Webmaster Tools and save it (0600).", file=sys.stderr)
        raise SystemExit(2)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        hint = " - key revoked or expired?" if status in (401, 403) else ""
        print(f"BING_UNAVAILABLE: Bing API error {status}{hint}",
              file=sys.stderr)
        raise SystemExit(2)
