"""Keyword miner: Google Autocomplete fan-out (the AnswerThePublic technique).

Free, no API key, no login. Expands a seed keyword through Google's own
suggest API, then fans out with question/modifier prefixes to surface the
long-tail questions people actually type.

Usage: .venv/bin/python keyword_miner.py "best running shoes"
"""
import os
import re
import sys
import urllib.parse

import requests

os.environ.setdefault("REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt")

SUGGEST = "https://suggestqueries.google.com/complete/search"

QUESTION_PREFIXES = ["who", "what", "where", "when", "why", "how", "which",
                     "can", "should", "do", "is", "are", "best", "top"]
MODIFIERS = ["cost", "price", "prices", "pricing", "packages", "reviews",
             "near me", "2026", "2027", "affordable", "luxury", "best"]


def suggest(query):
    """Autocomplete suggestions for query. Returns None on request failure
    (so callers can tell "endpoint down" from "no suggestions"), [] when
    the endpoint answers but has nothing."""
    import time
    time.sleep(0.3)  # politeness: don't hammer the suggest endpoint
    try:
        r = requests.get(SUGGEST, params={"client": "firefox", "q": query},
                         timeout=20)
        r.raise_for_status()
        return r.json()[1] or []
    except Exception:  # noqa: BLE001
        return None


def _cache_path(seed):
    import datetime
    day = datetime.date.today().isoformat()
    safe = re.sub(r"[^a-z0-9]+", "-", seed.lower()).strip("-")[:60]
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        f".miner-cache-{safe}-{day}.json")


def mine(seed, depth=2):
    import json
    cp = _cache_path(seed)
    try:
        with open(cp) as f:
            return json.load(f)
    except (OSError, ValueError):
        pass
    seen, frontier = set(), [seed]
    results = set()
    # Consecutive suggest failures - if the endpoint is down, bail out of
    # the fan-out instead of burning ~9 minutes on timeouts (F4).
    fails = 0
    dead = False

    def fanout(q):
        nonlocal fails, dead
        s = suggest(q)
        if s is None:
            fails += 1
            if fails >= 3:
                dead = True
            return []
        fails = 0
        return s

    for _ in range(depth):
        nxt = []
        for q in frontier:
            if q in seen or dead:
                continue
            seen.add(q)
            for s in fanout(q):
                if s not in results:
                    results.add(s)
                    nxt.append(s)
        frontier = nxt
    # question fan-out on the seed
    for p in QUESTION_PREFIXES:
        if dead:
            break
        for s in fanout(f"{p} {seed}"):
            results.add(s)
    for m in MODIFIERS:
        if dead:
            break
        for s in fanout(f"{seed} {m}"):
            results.add(s)
    # drop near-duplicates that differ only by punctuation/case
    deduped, seen_norm = [], set()
    for k in sorted(results):
        nk = re.sub(r"[^a-z0-9 ]", "", k.lower()).strip()
        if nk and nk not in seen_norm:
            seen_norm.add(nk)
            deduped.append(k)
    try:
        with open(cp, "w") as f:
            json.dump(deduped, f)
        os.chmod(cp, 0o600)
    except OSError:
        pass
    return deduped


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("Usage: keyword_miner.py [seed query ...]")
        print("Fan-out over Google Autocomplete; prints keyword ideas.")
        print("Default seed: 'best running shoes'")
        return
    seed = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
        "best running shoes"
    kws = mine(seed)
    questions = [k for k in kws if k.split()[0].lower() in
                 {"who", "what", "where", "when", "why", "how", "which", "can",
                  "should", "do", "is", "are"}]
    print(f"# {len(kws)} keyword ideas for '{seed}'\n")
    print("## Questions (Journal entry fuel)")
    for k in questions[:30]:
        print(f"- {k}")
    print(f"\n## All non-question ideas ({len(kws) - len(questions)})")
    qset = set(questions)
    for k in kws:
        if k not in qset:
            print(f"- {k}")


if __name__ == "__main__":
    main()
