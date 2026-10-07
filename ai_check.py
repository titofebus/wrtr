#!/usr/bin/env python3
"""ai_check.py — advisory AI-sounding check for a draft via local SlopTotal.

Posts the draft text to a locally running SlopTotal instance
(http://localhost:8000/api/quick-score) and prints the score plus the
human-fingerprints reminder when the score is elevated.

This is ADVISORY ONLY and always exits 0: detectors false-positive on
polished human writing, so it must never gate publishing. The hard gate
is draft_score.py. If SlopTotal isn't running, this prints SKIPPED.

Usage:
    .venv/bin/python ai_check.py <draft.md> [--heatmap]

Setup (one time): see sloptotal/SETUP.md.
"""

import argparse
import json
import os
import re
import sys
import urllib.request

SLOPTOTAL = os.environ.get("SLOPTOTAL_URL", "http://localhost:8000")
ELEVATED_AT = 55  # SlopTotal calibration: <2 in 100 human texts score this high

FINGERPRINTS = """HUMAN-FINGERPRINTS checklist (the real defense):
- a real name, place, or moment only you could write
- first person ("I"/"we") somewhere natural
- one opinionated sentence (a detector can't fake taste)
- contractions and varied sentence lengths"""


def draft_text(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    # strip markdown scaffolding, keep prose
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.M)
    return re.sub(r"\s+", " ", text).strip()


# Timeout raised 30 -> 120 (2026-10-07): a full ~1300-word draft takes ~30s
# on this VM's CPU (server chunks long text); 30s timed out on real drafts.
def post(endpoint, payload, timeout=120):
    req = urllib.request.Request(
        SLOPTOTAL + endpoint,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("draft", help="markdown draft file")
    ap.add_argument("--heatmap", action="store_true",
                    help="per-paragraph scores (slower, pinpoints AI-ish sections)")
    args = ap.parse_args()

    if not os.path.isfile(args.draft):
        print(f"ai_check: no such file: {args.draft}", file=sys.stderr)
        return 2

    try:
        text = draft_text(args.draft)
    except (OSError, UnicodeDecodeError) as e:
        print(f"AI-CHECK SKIPPED (cannot read draft: {type(e).__name__}).")
        return 0
    if len(text.split()) < 80:
        print("AI-CHECK SKIPPED: draft under ~80 words — detectors are "
              "unreliable on short text.")
        return 0

    try:
        if args.heatmap:
            data = post("/api/paragraph-score", {"text": text}, timeout=120)
            print("# Per-paragraph AI scores (higher = more AI-like)")
            paras = data.get("paragraphs", data.get("scores", []))
            for p in paras:
                if isinstance(p, dict):
                    print(f"{p.get('score', '?'):>6}  "
                          f"{p.get('text', '')[:80]}")
                else:
                    print(f"  {p}")
        else:
            data = post("/api/quick-score", {"text": text})
            score = data.get("score", data.get("ai_score", "?"))
            verdict = data.get("verdict", data.get("label", ""))
            print(f"AI score: {score} {verdict}".strip())
            engines = data.get("engines", data.get("top_engines", []))
            for e in (engines or [])[:3]:
                if isinstance(e, dict):
                    print(f"  - {e.get('name', e.get('engine', '?'))}: {e.get('score', '?')}")
            try:
                if isinstance(score, (int, float)) and score >= ELEVATED_AT:
                    print()
                    print("Elevated — worth a human re-read. This is advisory; "
                          "it does not block publishing.")
                    print(FINGERPRINTS)
            except TypeError:
                pass
    except Exception as e:  # noqa: BLE001 — service down, timeout, bad JSON
        print(f"AI-CHECK SKIPPED (SlopTotal not reachable at {SLOPTOTAL}: "
              f"{type(e).__name__}). Start it per sloptotal/SETUP.md.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
