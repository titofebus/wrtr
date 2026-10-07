"""Weekly Core Web Vitals monitor.

- CrUX API: real-user field data for the origin (preferred by Google).
- PSI API v5: lab Lighthouse scores for key templates.
Both free, key-restricted to those two APIs. Run weekly; alert on regression.

Page list: override with the PSI_URLS env var (comma-separated). The
default below is one site's key templates, kept as a working example.
"""
import os
import urllib.parse

import requests

os.environ.setdefault("REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt")
HERE = os.path.dirname(os.path.abspath(__file__))

# Lab performance score below this triggers an alert line in the report.
ALERT_PERF_THRESHOLD = 70

TEMPLATES = [u.strip() for u in
             os.environ.get("PSI_URLS", "").split(",") if u.strip()] or [
    "https://www.febusfilms.com/",
    "https://www.febusfilms.com/about/",
    "https://www.febusfilms.com/services/",
    "https://www.febusfilms.com/portfolio/",
    "https://www.febusfilms.com/contact/",
    "https://www.febusfilms.com/journal/",
    "https://www.febusfilms.com/journal/finding-the-right-wedding-photographer-for-you/",
]


def _key():
    with open(os.path.join(HERE, ".psi-key")) as f:
        return f.read().strip()


def crux_origin():
    key = _key()
    r = requests.post(
        f"https://chromeuxreport.googleapis.com/v1/records:queryRecord?key={key}",
        json={"origin": "https://www.febusfilms.com"},
        timeout=60,
    )
    if r.status_code == 404:
        return None  # not enough traffic for field data
    r.raise_for_status()
    return r.json().get("record", {}).get("metrics", {})


def psi_score(url):
    key = _key()
    r = requests.get(
        "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
        params={"url": url, "strategy": "mobile", "category": "performance",
                "key": key},
        timeout=120,
    )
    r.raise_for_status()
    lh = r.json()["lighthouseResult"]
    cats = lh["categories"]["performance"]["score"]
    audits = lh.get("audits", {})
    def num(aid):
        a = audits.get(aid, {})
        return a.get("numericValue"), a.get("displayValue")
    lcp, lcp_d = num("largest-contentful-paint")
    inp, inp_d = num("interaction-to-next-paint")
    cls, cls_d = num("cumulative-layout-shift")
    return {"score": round(cats * 100), "lcp": lcp_d, "inp": inp_d, "cls": cls_d}


def main():
    out = ["# CWV check — febusfilms.com", ""]
    # CrUX is a nicety — a 429/500 here must not nuke the PSI lab scores.
    try:
        m = crux_origin()
    except Exception as e:  # noqa: BLE001
        m = None
        out.append(f"_CrUX unavailable ({type(e).__name__}) — lab scores only._")
        out.append("")
    if m:
        out.append("## CrUX field data (real users, 28d)")
        for k in ("largest_contentful_paint", "interaction_to_next_paint",
                  "cumulative_layout_shift"):
            if k in m:
                p75 = m[k]["percentiles"]["p75"]
                out.append(f"- {k}: p75 = {p75}")
        out.append("")
    else:
        out.append("_CrUX: not enough traffic for field data — using lab scores only._\n")
    out.append("## PSI lab (mobile)")
    out.append("| page | perf | LCP | INP | CLS |")
    out.append("|---|---|---|---|---|")
    alerts = []
    for url in TEMPLATES:
        try:
            s = psi_score(url)
            path = urllib.parse.urlparse(url).path or "/"
            out.append(f"| {path} | {s['score']} | {s['lcp']} | {s['inp']} | {s['cls']} |")
            if s["score"] < ALERT_PERF_THRESHOLD:
                alerts.append(f"{path}: perf {s['score']} < {ALERT_PERF_THRESHOLD}")
        except Exception as e:  # noqa: BLE001
            # Never print the raw exception: requests embeds the request URL,
            # which carries the API key as a query param.
            out.append(f"| {url} | ERROR | {type(e).__name__} | | |")
    if alerts:
        out += ["", "## Alerts"] + [f"- {a}" for a in alerts]
    print("\n".join(out))


if __name__ == "__main__":
    main()
