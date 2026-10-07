"""Minimal Google Search Console API client.

Works around two VM quirks:
- The egress proxy uses a self-signed CA: requests needs
  REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
- googleapiclient's httplib2 transport mishandles the proxy, so we use
  plain REST via `requests` instead of the discovery client.

Auth: service-account key at .sa-key.json (0600). That service account must
be added once under GSC Settings -> Users and permissions on each property
the toolkit queries. Its email can be set via the GSC_SERVICE_ACCOUNT env
var (used only for the SETUP_PENDING hint); the key file is what
authenticates.
"""
import os
import urllib.parse

import requests

os.environ.setdefault("REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt")

BASE = "https://www.googleapis.com/webmasters/v3"

# Search Console API page-size cap (used for both the request and the
# "last page" check — keep them in sync via this constant).
MAX_PAGE_SIZE = 25000


# Displayed in the SETUP_PENDING hint; the key file does the auth.
SA = os.environ.get("GSC_SERVICE_ACCOUNT",
                    "the service account in .sa-key.json")
SA_KEY = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".sa-key.json")
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

_creds = None


def _token():
    global _creds
    if _creds is None or not _creds.valid:
        from google.oauth2 import service_account
        import google.auth.transport.requests
        _creds = service_account.Credentials.from_service_account_file(SA_KEY, scopes=SCOPES)
        _creds.refresh(google.auth.transport.requests.Request())
    return _creds.token


def _with_retry(fn, what):
    """Two retries (exponential backoff) on 429/5xx, mirroring bing.py."""
    import time
    last = None
    for attempt in range(3):
        try:
            return fn()
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status != 429 and status < 500:
                raise
            last = e
            time.sleep(2 ** attempt)
    raise last


def _get(path, **params):
    def do():
        r = requests.get(BASE + path, params=params,
                         headers={"Authorization": "Bearer " + _token()}, timeout=60)
        r.raise_for_status()
        return r.json()
    return _with_retry(do, "GET " + path)


def _post(path, body):
    def do():
        r = requests.post(BASE + path, json=body,
                          headers={"Authorization": "Bearer " + _token()}, timeout=120)
        r.raise_for_status()
        return r.json()
    return _with_retry(do, "POST " + path)


def list_sites():
    return _get("/sites").get("siteEntry", [])


def search_analytics(site_url, start_date, end_date, dimensions=("query",),
                     row_limit=MAX_PAGE_SIZE, search_type="web"):
    """Paginated searchAnalytics.query. Returns list of rows."""
    rows, start_row = [], 0
    while True:
        body = {
            "startDate": start_date, "endDate": end_date,
            "dimensions": list(dimensions), "searchType": search_type,
            "rowLimit": min(row_limit, MAX_PAGE_SIZE), "startRow": start_row,
        }
        data = _post(f"/sites/{urllib.parse.quote(site_url, safe='')}/searchAnalytics/query", body)
        batch = data.get("rows", [])
        rows.extend(batch)
        # Break on a short page, on hitting row_limit, or when the batch is
        # smaller than what we asked for (avoids a wasted trailing call when
        # the total is an exact multiple of the page size).
        if len(batch) < min(row_limit, MAX_PAGE_SIZE) or len(rows) >= row_limit:
            break
        start_row += len(batch)
    return rows[:row_limit]


if __name__ == "__main__":
    for s in list_sites():
        print(s["siteUrl"], "|", s["permissionLevel"])
