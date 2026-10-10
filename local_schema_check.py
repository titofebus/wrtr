"""Check a page's LocalBusiness-style JSON-LD against the site's local_seo
config (operating model, canonical NAP). Advisory audit tool.

Usage:
  .venv/bin/python local_schema_check.py <url-or-html-file> --site <slug>
Exit 0 = no red items, 1 = red items found, 2 = usage error.
"""
import argparse
import json
import os
import re
import sys
import urllib.request

import site_config

LOCAL_TYPES = {"localbusiness", "professionalservice", "homeandconstructionbusiness",
               "plumber", "electrician", "hvacbusiness", "roofingcontractor",
               "generalcontractor", "organization", "store"}


def extract_jsonld(html):
    nodes = []
    for raw in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>',
                          html, re.S | re.I):
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
            elif isinstance(d, dict):
                if "@graph" in d:
                    stack.extend(d["@graph"] if isinstance(d["@graph"], list) else [d["@graph"]])
                nodes.append(d)
    return nodes


def _types(n):
    t = n.get("@type", [])
    return {str(x).lower() for x in (t if isinstance(t, list) else [t])}


def _digits(s):
    return re.sub(r"\D", "", str(s or ""))[-10:]


def check(nodes, cfg):
    ls = cfg.get("local_seo") or {}
    nap = ls.get("nap") or {}
    hide = site_config.hides_address(cfg)
    biz = [n for n in nodes if _types(n) & LOCAL_TYPES]
    out = []
    if not biz:
        return [("business schema", "red", "no LocalBusiness/Organization JSON-LD found")]
    out.append(("business schema", "green", ", ".join(sorted(set().union(*map(_types, biz))))))
    phones = [n.get("telephone") for n in biz if n.get("telephone")]
    if not phones:
        out.append(("telephone", "red", "no telephone in business schema"))
    elif nap.get("phone") and any(_digits(p) != _digits(nap["phone"]) for p in phones):
        out.append(("telephone", "red", f"schema phone {phones} != canonical {nap['phone']}"))
    else:
        out.append(("telephone", "green", str(phones[0])))
    if nap.get("name"):
        bad = [n.get("name") for n in biz if n.get("name") and n["name"] != nap["name"]]
        out.append(("name", "yellow" if bad else "green",
                    f"schema names {bad} != canonical {nap['name']!r}" if bad else nap["name"]))
    if hide:
        leaks = []
        for n in biz:
            a = n.get("address")
            if isinstance(a, dict) and a.get("streetAddress"):
                leaks.append(f"streetAddress {a['streetAddress']!r}")
            elif isinstance(a, str) and re.search(r"\d", a):
                leaks.append(f"address {a!r}")
            if n.get("geo"):
                leaks.append("geo coordinates")
            if n.get("hasMap"):
                leaks.append("hasMap")
        out.append(("hidden address (SAB)", "red" if leaks else "green",
                    "remove " + ", ".join(leaks) if leaks else "no street address or geo"))
        if not any(n.get("areaServed") for n in biz):
            out.append(("areaServed", "yellow", "add areaServed matching the GBP service areas"))
        else:
            out.append(("areaServed", "green", "present"))
    elif ls.get("operating_model") in ("storefront", "hybrid"):
        has = any(isinstance(n.get("address"), dict) and n["address"].get("streetAddress") for n in biz)
        out.append(("address", "green" if has else "red",
                    "streetAddress present" if has else "storefront/hybrid needs its real staffed address"))
    for n in biz:
        if n.get("aggregateRating") or n.get("review"):
            out.append(("self-serving reviews", "yellow",
                        "business marks up its own rating/reviews; Google ignores self-serving review markup"))
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="URL or local HTML file")
    ap.add_argument("--site", default=None)
    a = ap.parse_args()
    cfg = site_config.load(a.site)
    if os.path.isfile(a.source):
        html = open(a.source, encoding="utf-8", errors="replace").read()
    else:
        req = urllib.request.Request(a.source, headers={"User-Agent": "wrtr-local-schema-check"})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    res = check(extract_jsonld(html), cfg)
    icon = {"green": "OK ", "yellow": "WARN", "red": "FAIL"}
    for name, lvl, msg in res:
        print(f"{icon[lvl]} {name}: {msg}")
    return 1 if any(l == "red" for _, l, _ in res) else 0


if __name__ == "__main__":
    sys.exit(main())
