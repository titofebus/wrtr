"""Competitor SERP checks via free-tier search APIs.

Supports (first available wins): Brave Search API ($5/mo free, own index,
official MCP), Serper (2,500 free queries, Google SERPs), Exa ($10/mo free,
returns page contents — best for content-gap analysis).

Keys live in 0600 files next to this script: .brave-key, .serper-key, .exa-key
(one per line, raw key). With no keys it prints setup pointers and exits.

Usage: .venv/bin/python serp_check.py "best running shoes"
"""
import os
import sys

import requests

os.environ.setdefault("REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt")
HERE = os.path.dirname(os.path.abspath(__file__))


def _key(name):
    p = os.path.join(HERE, name)
    return open(p).read().strip() if os.path.exists(p) else None


def via_brave(query, key):
    r = requests.get("https://api.search.brave.com/res/v1/web/search",
                     headers={"X-Subscription-Token": key},
                     params={"q": query, "count": 10, "text_decorations": 0,
                             "country": "US"},
                     timeout=30)
    r.raise_for_status()
    out = []
    for w in r.json().get("web", {}).get("results", []):
        out.append({"title": w.get("title"), "url": w.get("url"),
                    "desc": (w.get("description") or "")[:160]})
    return "Brave", out


def via_serper(query, key):
    r = requests.post("https://google.serper.dev/search",
                      headers={"X-API-KEY": key, "Content-Type": "application/json"},
                      json={"q": query, "num": 10, "gl": "us"}, timeout=30)
    r.raise_for_status()
    out = [{"title": o.get("title"), "url": o.get("link"),
            "desc": (o.get("snippet") or "")[:160]}
           for o in r.json().get("organic", [])]
    return "Serper (Google)", out


def via_exa(query, key):
    r = requests.post("https://api.exa.ai/search",
                      headers={"x-api-key": key, "Content-Type": "application/json"},
                      json={"query": query, "numResults": 10,
                            "contents": {"text": {"maxCharacters": 1500}}},
                      timeout=60)
    r.raise_for_status()
    out = [{"title": o.get("title"), "url": o.get("url"),
            "desc": ((o.get("text") or "")[:160]).replace("\n", " ")}
           for o in r.json().get("results", [])]
    return "Exa", out


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print('Usage: serp_check.py ["<query>"] — checks SERP via Brave/Serper/Exa keys.')
        print("Without a query it uses the default seed. Keys are optional; "
              "without any key it prints where to get free ones.")
        return
    query = sys.argv[1] if len(sys.argv) > 1 else "best running shoes"
    brave, serper, exa = _key(".brave-key"), _key(".serper-key"), _key(".exa-key")
    if not any([brave, serper, exa]):
        print("No SERP API keys found. Free tiers (2-minute signups):")
        print("- Brave Search API: $5/mo free → save key to .brave-key "
              "(https://brave.com/search/api/)")
        print("- Serper: 2,500 free Google queries → .serper-key (https://serper.dev)")
        print("- Exa: $10/mo free, returns page text → .exa-key (https://exa.ai)")
        return
    for name, key, fn in (("Brave", brave, via_brave), ("Serper", serper, via_serper),
                          ("Exa", exa, via_exa)):
        if not key:
            continue
        try:
            src, results = fn(query, key)
        except Exception as e:  # noqa: BLE001
            print(f"[{name}] error: {e}")
            continue
        print(f"# Top 10 for '{query}' (via {src})\n")
        for i, o in enumerate(results, 1):
            print(f"{i}. {o['title']}\n   {o['url']}\n   {o['desc']}\n")
        break  # first working provider wins


if __name__ == "__main__":
    main()
