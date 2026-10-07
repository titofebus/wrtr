#!/usr/bin/env python3
"""draft_score.py — pre-publish quality gate for Journal drafts.

Scores a markdown draft (front matter + body) on readability, on-page SEO,
and human-voice signals, Yoast-traffic-light style. This is the publishing
gate: a draft must reach the minimum score (default 80, configurable per
site via `draft_score_min`) with no hard failures to publish.

Usage:
    .venv/bin/python draft_score.py <draft.md> --site <slug> --keyword "..."
    [--min-score 80]

Exit codes: 0 = pass (publish), 1 = failed gate (fix and re-run),
2 = usage/config error.

The AI-sounding check (SlopTotal) is intentionally NOT part of this gate —
detectors false-positive on polished human writing, so `ai_check.py` stays
advisory-only. This scorer checks things that are deterministically true
about the text.

Note: the voice checks (contractions, AI tics, textstat language) assume
English copy. Non-English drafts will get misleading voice yellows.
"""

import argparse
import os
import re
import sys

import site_config

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_draft(path):
    """Split a markdown file into (front_matter dict, body string)."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fm = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            raw = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            fm = _parse_simple_yaml(raw)
    return fm, body


def _parse_simple_yaml(raw):
    """Minimal YAML-subset parser for front matter (scalars, lists, quotes)."""
    out, cur_key, cur_list = {}, None, None
    for line in raw.split("\n"):
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            if cur_key and cur_list is not None:
                out[cur_key] = cur_list
            cur_key, cur_list = m.group(1), None
            val = m.group(2).strip()
            if val == "":
                cur_list = []
            elif val in ("[]",):
                out[cur_key] = []
                cur_key = None
            else:
                out[cur_key] = _unquote(val)
                cur_key = None
        elif line.strip().startswith("- ") and cur_list is not None:
            cur_list.append(_unquote(line.strip()[2:].strip()))
    if cur_key and cur_list is not None:
        out[cur_key] = cur_list
    return out


def _unquote(s):
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def headings(body):
    """[(level, text)] for ATX headings in reading order."""
    out = []
    for line in body.split("\n"):
        m = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip()))
    return out


def plain_text(body):
    """Body with markdown scaffolding stripped (links keep their text)."""
    t = body
    t = re.sub(r"```.*?```", " ", t, flags=re.S)      # fenced code
    t = re.sub(r"`[^`]*`", " ", t)                     # inline code
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)        # images
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)      # links keep text
    t = re.sub(r"^#{1,6}\s+", "", t, flags=re.M)       # heading marks
    t = re.sub(r"^>\s?", "", t, flags=re.M)            # quotes
    t = re.sub(r"^[-*+]\s+", "", t, flags=re.M)        # bullets
    t = re.sub(r"^\d+\.\s+", "", t, flags=re.M)        # numbered lists
    t = re.sub(r"[*_~]+", "", t)                       # emphasis
    t = re.sub(r"\|", " ", t)                          # tables
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def words(text):
    return re.findall(r"[A-Za-z0-9']+", text.lower())


def keyword_hits(text, keyword):
    """Case-insensitive whole-phrase occurrences of the keyword."""
    pat = r"(?<![a-z0-9])" + re.escape(keyword.lower()) + r"(?![a-z0-9])"
    return len(re.findall(pat, text.lower()))

# ---------------------------------------------------------------------------
# Checks — each returns (name, status, detail); status in green/yellow/red
# ---------------------------------------------------------------------------

VOICE_TICS = ["furthermore", "additionally", "moreover", "in conclusion",
              "delve", "tapestry", "landscape", "leverage",
              "it's important to note", "in today's fast-paced"]


def check_readability(text):
    """textstat readability. Returns list of checks."""
    out = []
    try:
        import textstat
        textstat.set_lang("en_US")
        grade = textstat.flesch_kincaid_grade(text)
        ease = textstat.flesch_reading_ease(text)
    except ImportError:
        return [("readability", "yellow",
                 "textstat not installed — skipping readability")]
    except LookupError:
        # Missing NLTK corpus (~/nltk_data) — the gate must degrade, not crash.
        return [("readability", "yellow",
                 "syllable dictionary missing (~/nltk_data) — skipping readability")]
    if 7 <= grade <= 11:
        out.append(("reading grade", "green", f"grade {grade:.1f} (target 7–11)"))
    elif 5 <= grade <= 13:
        out.append(("reading grade", "yellow", f"grade {grade:.1f} (target 7–11)"))
    else:
        out.append(("reading grade", "red", f"grade {grade:.1f} — too hard or too simple (target 7–11)"))
    sents = sentences(text)
    long_s = [s for s in sents if len(s.split()) > 20]
    if not sents:
        out.append(("sentence length", "red", "no sentences found"))
    elif len(long_s) / len(sents) <= 0.25:
        out.append(("sentence length", "green",
                    f"{len(long_s)}/{len(sents)} over 20 words"))
    else:
        out.append(("sentence length", "yellow",
                    f"{len(long_s)}/{len(sents)} over 20 words — shorten some"))
    paras = [p for p in text.split("\n\n") if p.strip()]
    long_p = [p for p in paras if len(p.split()) > 150]
    if long_p:
        out.append(("paragraph length", "yellow",
                    f"{len(long_p)} paragraph(s) over 150 words — break up"))
    else:
        out.append(("paragraph length", "green", "paragraphs are scannable"))
    out.append(("reading ease", "green" if ease >= 60 else "yellow",
                f"Flesch ease {ease:.0f}"))
    return out


def check_seo(fm, text, heads, keyword, cfg):
    out = []
    title = str(fm.get("title", ""))
    desc = str(fm.get("description", fm.get("excerpt", "")))

    def has_kw(s):
        return keyword_hits(s, keyword) > 0

    # Keyword placement
    out.append(("keyword in title", "green" if has_kw(title) else "red",
                "present" if has_kw(title) else "missing from title"))
    # H1 = body `#` headings, falling back to the front-matter title (the
    # layout renders it as the H1).
    h1s = [t for lvl, t in heads if lvl == 1]
    h1_from_title = False
    if not h1s and title:
        h1s = [title]
        h1_from_title = True
    out.append(("keyword in H1", "green" if any(has_kw(t) for t in h1s) else "red",
                "present" if any(has_kw(t) for t in h1s) else "missing from H1"))
    first100 = " ".join(text.split()[:100])
    out.append(("keyword in first 100 words",
                "green" if has_kw(first100) else "yellow",
                "present" if has_kw(first100) else "missing — move it up"))
    h2s = [t for lvl, t in heads if lvl == 2]
    out.append(("keyword in an H2",
                "green" if any(has_kw(t) for t in h2s) else "yellow",
                "present" if any(has_kw(t) for t in h2s) else "missing"))
    alt = str(fm.get("imageAlt", fm.get("image_alt", "")))
    out.append(("keyword in image alt",
                "green" if has_kw(alt) else "yellow",
                "present" if has_kw(alt) else "missing from imageAlt"))

    # Density 0.5–2.5%
    wc = words(text)
    dens = keyword_hits(text, keyword) / max(len(wc), 1) * 100
    if 0.5 <= dens <= 2.5:
        out.append(("keyword density", "green", f"{dens:.2f}% (band 0.5–2.5%)"))
    elif dens < 0.5:
        out.append(("keyword density", "yellow", f"{dens:.2f}% — thin, use it more naturally"))
    else:
        out.append(("keyword density", "red", f"{dens:.2f}% — stuffing risk, trim"))

    # Heading structure (h1s already includes the title fallback above).
    if len(h1s) == 1:
        out.append(("single H1", "green",
                    "front-matter title acts as H1" if h1_from_title else "one H1"))
    elif not h1s:
        out.append(("single H1", "red", "HARD: no H1 found"))
    else:
        out.append(("single H1", "red", f"HARD: {len(h1s)} H1s — keep one"))
    levels = [lvl for lvl, _ in heads]
    skipped = any(b - a > 1 for a, b in zip(levels, levels[1:]))
    out.append(("heading order", "green" if not skipped else "yellow",
                "no skipped levels" if not skipped else "skipped a level (H2→H4 etc.)"))

    # Length sanity: 600+ words for SEO (the brief's per-type target is the
    # real goal; this gate just catches thin drafts).
    if len(wc) >= 600:
        out.append(("length", "green", f"{len(wc)} words"))
    else:
        out.append(("length", "yellow", f"{len(wc)} words — thin for SEO (600+ better)"))

    # Banned terms — HARD failure
    banned = [b for b in cfg.get("banned_terms", []) if str(b).strip()]
    found = [b for b in banned if str(b).lower() in text.lower()
             or str(b).lower() in title.lower()]
    if found:
        out.append(("banned terms", "red",
                    f"HARD: found {', '.join(repr(b) for b in found)}"))
    else:
        out.append(("banned terms", "green", "clean"))

    # Meta lengths
    if title and len(title) <= 60:
        out.append(("title length", "green", f"{len(title)} chars"))
    elif title:
        out.append(("title length", "yellow", f"{len(title)} chars — over 60"))
    if desc:
        if 120 <= len(desc) <= 160:
            out.append(("meta description", "green", f"{len(desc)} chars"))
        else:
            out.append(("meta description", "yellow",
                        f"{len(desc)} chars (target 120–160)"))
    return out


def check_voice(text):
    out = []
    tl = text.lower()
    tics = sorted({t for t in VOICE_TICS if t in tl})
    if tics:
        out.append(("AI voice tics", "yellow",
                    f"formal tics: {', '.join(tics)} — rewrite in your own words"))
    else:
        out.append(("AI voice tics", "green", "none of the usual formal tics"))
    sents = sentences(text)
    contr = len(re.findall(r"\b\w+'(re|ve|ll|d|s|m|t)\b", tl))
    if sents and contr / len(sents) >= 0.15:
        out.append(("contractions", "green",
                    f"{contr} contractions — sounds human"))
    elif sents:
        out.append(("contractions", "yellow",
                    "few contractions — stiff copy reads as AI"))
    else:
        out.append(("contractions", "yellow", "no sentences found"))
    # Burstiness: uniform sentence lengths read as AI
    if len(sents) >= 5:
        lens = [len(s.split()) for s in sents]
        mean = sum(lens) / len(lens)
        var = sum((x - mean) ** 2 for x in lens) / len(lens)
        cv = (var ** 0.5) / max(mean, 1)
        if cv >= 0.5:
            out.append(("burstiness", "green",
                        f"sentence lengths vary (CV {cv:.2f})"))
        else:
            out.append(("burstiness", "yellow",
                        f"sentences are uniform (CV {cv:.2f}) — vary the rhythm"))
    # Human fingerprints (light heuristics)
    fps = []
    if re.search(r"\b(I|we|my|our)\b", text):
        fps.append("first person")
    if re.search(r"\b\d+\b", text):
        fps.append("specific numbers")
    if len(re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", text)) >= 1:
        fps.append("named people/places")
    if fps:
        out.append(("human fingerprints", "green", ", ".join(fps)))
    else:
        out.append(("human fingerprints", "yellow",
                    "no first person, numbers, or named people — add something only you could write"))
    return out


def score(checks):
    """0–100 from Yoast-style traffic lights: green=full, yellow=half, red=0."""
    if not checks:
        return 0
    pts = {"green": 1.0, "yellow": 0.5, "red": 0.0}
    return round(sum(pts.get(s, 0) for _, s, _ in checks) / len(checks) * 100)


DOT = {"green": "🟢", "yellow": "🟡", "red": "🔴"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("draft", help="markdown draft file")
    ap.add_argument("--site", default=None,
                    help="site slug from sites/ (default: example)")
    ap.add_argument("--keyword", required=True, help="target keyword")
    ap.add_argument("--min-score", type=int, default=None,
                    help="minimum score to pass (default: site's "
                         "draft_score_min or 80)")
    args = ap.parse_args()
    if not args.keyword.strip():
        ap.error("--keyword must not be empty")

    if not os.path.isfile(args.draft):
        print(f"draft_score: no such file: {args.draft}", file=sys.stderr)
        return 2
    try:
        cfg = site_config.load(args.site)
    except SystemExit:
        return 2

    min_score = (args.min_score if args.min_score is not None
                 else cfg.get("draft_score_min", 80))

    try:
        fm, body = parse_draft(args.draft)
    except UnicodeDecodeError:
        print(f"draft_score: {args.draft} is not valid UTF-8 — save it as UTF-8 and re-run.",
              file=sys.stderr)
        return 2
    heads = headings(body)
    text = plain_text(body)

    checks = []
    checks += check_readability(text)
    checks += check_seo(fm, text, heads, args.keyword, cfg)
    checks += check_voice(text)

    total = score(checks)
    hard = [c for c in checks if c[1] == "red" and "HARD" in c[2]]

    print(f"# Draft score: {args.draft}")
    print(f"# Keyword: {args.keyword} | Site: {cfg.get('slug')}")
    print("")
    for name, status, detail in checks:
        print(f"{DOT[status]} {name}: {detail}")
    print("")
    print(f"Score: {total}/100 (minimum to publish: {min_score})")

    if hard:
        print("BLOCKED: hard failures must be fixed: "
              + "; ".join(f"{n} — {d}" for n, _, d in hard))
        return 1
    if total < min_score:
        print(f"BLOCKED: score {total} is below the minimum {min_score}. "
              f"Fix the 🟡/🔴 items above and re-run.")
        return 1
    print("PASS — ready for the next step (ai_check.py, then validate).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
