#!/usr/bin/env python3
"""aeo_map.py - answer engine question map.

"What do people ask AI assistants in this space, and where does our site
give them nothing to cite?"

Collects question-shaped queries from two sources and gap-checks them
against the site's existing entries:

1. Autocomplete mining - keyword_miner fans out each seed topic and keeps
   the question-shaped queries (the same questions buyers type into
   ChatGPT, Perplexity, and Google AI Mode).
2. Search Console - the site's own question queries from the last 28 days
   (degrades gracefully when GSC is unavailable).

Each question is then matched against existing journal/resources entries
by content-word overlap. Questions with no covering entry are citation
gaps: brief them (content_brief.py) with the AEO section and they become
quotable answers.

Usage:
    .venv/bin/python aeo_map.py --site <slug> [--seeds "seed one,seed two"]
    .venv/bin/python aeo_map.py --site febusfilms --no-gsc

Seeds default to the site's proactive_seeds. No network beyond what
keyword_miner and gsc already use.
"""
import argparse
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import keyword_miner  # noqa: E402
import site_config  # noqa: E402

# Reuse the brief's question definition: single source of truth is the
# miner's prefix list, minus its non-question modifiers.
QUESTION_WORDS = set(keyword_miner.QUESTION_PREFIXES) - {"best", "top"}
STOP = {"the", "a", "an", "in", "of", "for", "and", "or", "to", "at",
        "near", "is", "are", "do", "does", "can", "what", "how", "why",
        "when", "where", "which", "who"}


def is_question(q):
    return q.strip().split()[0].lower() in QUESTION_WORDS if q.strip() else False


def content_words(s):
    return {w for w in re.findall(r"[a-z]+", s.lower())
            if w not in STOP and len(w) > 2}


def mine_questions(seeds):
    """Question-shaped queries from autocomplete fan-out, per seed."""
    out = []
    for seed in seeds:
        try:
            mined = keyword_miner.mine(seed)
        except Exception as e:  # noqa: BLE001
            out.append({"question": f"(mining failed for {seed!r}: {e})",
                        "source": "miner", "seed": seed})
            continue
        for k in mined:
            if is_question(k):
                out.append({"question": k, "source": "miner", "seed": seed})
    return out


def gsc_questions(cfg):
    """Question-shaped queries from GSC search analytics (28d)."""
    try:
        import gsc
        end = datetime.date.today() - datetime.timedelta(days=3)
        start = (end - datetime.timedelta(days=27)).isoformat()
        rows = gsc.search_analytics(cfg["gsc_property"],
                                    start, end.isoformat(), ("query",))
    except Exception as e:  # noqa: BLE001
        return [{"question": f"(GSC unavailable: {e})",
                 "source": "gsc", "seed": ""}]
    out = []
    for r in rows:
        q = r["keys"][0]
        if is_question(q):
            out.append({"question": q, "source": "gsc",
                        "seed": "", "impressions": r["impressions"],
                        "position": r["position"]})
    out.sort(key=lambda d: -d.get("impressions", 0))
    return out


def existing_entries(cfg):
    """(slug, title-words) for every journal/resources entry on disk."""
    out = []
    repo = os.path.expanduser(cfg.get("repo", ""))
    for key in ("content_dir", "resources_dir"):
        d = os.path.join(repo, cfg.get(key, "")) if cfg.get(key) else ""
        if d and os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith(".md"):
                    slug = f[:-3]
                    out.append((slug, content_words(slug.replace("-", " "))))
    return out


def covering_entry(question, entries):
    """Best-overlapping existing entry, or None when nothing covers it."""
    qw = content_words(question)
    best, best_n = None, 0
    for slug, ew in entries:
        n = len(qw & ew)
        if n > best_n:
            best, best_n = slug, n
    # Needs real topical overlap: 2+ shared content words.
    return best if best_n >= 2 else None


def build_map(cfg, seeds, use_gsc=True):
    questions = mine_questions(seeds)
    if use_gsc and cfg.get("gsc_property"):
        questions += gsc_questions(cfg)
    # Dedupe: same question from miner + GSC counts once (GSC wins).
    seen = {}
    for q in questions:
        key = q["question"].lower().strip()
        if key not in seen or q["source"] == "gsc":
            seen[key] = q
    questions = list(seen.values())

    entries = existing_entries(cfg)
    gaps, covered = [], []
    for q in questions:
        if q["question"].startswith("("):
            continue  # error placeholder, not a real question
        cover = covering_entry(q["question"], entries)
        q["covered_by"] = cover
        (covered if cover else gaps).append(q)

    # Rank gaps: GSC questions with impressions first (proven demand),
    # then miner questions.
    gaps.sort(key=lambda d: (-d.get("impressions", 0),
                             d["question"]))

    L = [f"# Answer engine question map - {cfg['name']}",
         f"Date: {datetime.date.today()}",
         "",
         f"{len(questions)} questions collected "
         f"({len(gaps)} gaps, {len(covered)} covered).",
         "",
         "Questions are what buyers ask AI assistants (ChatGPT, Perplexity, "
         "Gemini, Google AI Mode). A gap means the site has no entry an "
         "answer engine could cite - brief it with content_brief.py and the "
         "AEO section writes the quotable answer.",
         ""]
    if gaps:
        L += ["## Gaps - no citable entry (brief these first)", ""]
        for q in gaps[:25]:
            src = q["source"]
            extra = ""
            if src == "gsc":
                extra = (f" - {q.get('impressions', 0):.0f} impressions, "
                         f"pos {q.get('position', 0):.1f} (demand is real)")
            elif q.get("seed"):
                extra = f" (from: {q['seed']})"
            L.append(f"- {q['question']}{extra}")
        if len(gaps) > 25:
            L.append(f"- ...and {len(gaps) - 25} more")
        L += ["",
              "Next step per gap: `.venv/bin/python content_brief.py "
              "\"<question>\" --type=<type> --site <slug>` - the brief's "
              "AEO section turns it into a quotable answer.",
              ""]
    else:
        L += ["## Gaps", "", "- none found - every collected question has a covering entry.", ""]
    if covered:
        L += ["## Covered - verify these are citable", ""]
        L += [f"- {q['question']} → `{q['covered_by']}`" for q in covered[:20]]
        if len(covered) > 20:
            L.append(f"- ...and {len(covered) - 20} more")
        L += ["",
              "Run draft_score.py on the covering entries: the AEO checks "
              "(question H2s, answer blocks, FAQ, citable numbers) say "
              "whether an answer engine would actually quote them.",
              ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site", default=None,
                    help="site slug from sites/ (default: example)")
    ap.add_argument("--seeds", default=None,
                    help="comma-separated seed topics (default: the site's "
                         "proactive_seeds)")
    ap.add_argument("--no-gsc", action="store_true",
                    help="skip the Search Console question pull")
    args = ap.parse_args()
    try:
        cfg = site_config.load(args.site)
    except SystemExit:
        return 2
    seeds = ([s.strip() for s in args.seeds.split(",") if s.strip()]
             if args.seeds else cfg.get("proactive_seeds", []))
    if not seeds:
        print("aeo_map: no seeds - pass --seeds or set proactive_seeds "
              "in the site YAML.", file=sys.stderr)
        return 2
    print(build_map(cfg, seeds, use_gsc=not args.no_gsc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
