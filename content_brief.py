"""Content brief generator: opportunity -> full drafting brief.

Takes a target keyword/query and produces a markdown brief an agent can
execute: titles, slug, categories, keywords, questions to answer (as H2s),
internal links, image guidance, front matter, brand-voice guardrails.

Usage: .venv/bin/python content_brief.py "<target query>" [--type <kind>] [--site <slug>]
<kind> is one of the site's type_category_map keys (see its sites/<slug>.yaml).
Site config lives in sites/<slug>.yaml (default: example).
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

# Fallback title templates ({title} = the target query, title-cased).
# Brands override title_templates in their YAML for tailored suggestions.
DEFAULT_TITLE_TEMPLATES = [
    "{title}: A Professional's Guide",
    "Real Talk on {title}",
    "{title} — What to Know Before You Book",
]

STOP_WORDS = {"the", "a", "an", "in", "of", "for", "and", "or", "to", "at",
              "near", "best", "top"}


def slugify(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:70].strip("-")


def _render_template(template, label, **kwargs):
    """Render a brand YAML template, with a clean error naming the offender."""
    if not isinstance(template, str):
        raise SystemExit(
            f"Site config error: {label} must be a string, got "
            f"{type(template).__name__}.")
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError) as e:
        raise SystemExit(
            f"Site config error: {label} {template!r} has a bad placeholder: {e}. "
            f"Available placeholders: {', '.join(sorted(kwargs))}.")


def existing_entries(cfg):
    out = []
    journal_dir = os.path.join(os.path.expanduser(cfg["repo"]), cfg["content_dir"])
    if os.path.isdir(journal_dir):
        for f in sorted(os.listdir(journal_dir)):
            if f.endswith(".md"):
                out.append(f[:-3])
    return out


def _venue_named_queries(related, target, geo_terms, brand_terms=()):
    """GSC queries that name a specific venue (demand signal for guides)."""
    generic = set(target.lower().split()) | {"wedding", "weddings", "venue",
                                             "venues", "photographer",
                                             "photography", "photo", "photos"}
    brand_lc = [b.lower() for b in brand_terms]
    out = []
    for r in related:
        q = r["query"].lower()
        if q == target.lower() or r["query"].startswith("(GSC"):
            continue
        if any(b in q for b in brand_lc):
            continue  # brand query, not a venue
        words = [w for w in q.split() if w not in generic]
        # A named venue: geo-adjacent and has 2+ distinctive words left
        # (e.g. "lake nona wave hotel weddings" -> wave, hotel).
        if len(q.split()) >= 4 and len(words) >= 2 and any(
                g in q for g in [t.lower() for t in geo_terms]):
            out.append(r)
    return out[:6]


def gsc_related(cfg, target):
    """Queries from GSC that share core terms with the target (last 28d)."""
    try:
        import gsc
        end = datetime.date.today() - datetime.timedelta(days=3)
        start = (end - datetime.timedelta(days=27)).isoformat()
        rows = gsc.search_analytics(cfg["gsc_property"],
                                    start, end.isoformat(), ("query",))
        core = {w for w in target.lower().split() if w not in STOP_WORDS}
        anchors = _anchors(target)
        hits = []
        for r in rows:
            q = r["keys"][0].lower()
            qw = set(q.split())
            shared = len(core & qw)
            # Keep queries about THIS topic: 2+ shared words plus an anchor
            # (the target's distinctive term), or 3+ shared words.
            if shared >= 2 and ((anchors & qw) or shared >= 3):
                hits.append({"query": r["keys"][0],
                             "impressions": r["impressions"],
                             "position": r["position"]})
        hits.sort(key=lambda d: -d["impressions"])
        return hits[:15]
    except Exception as e:  # noqa: BLE001
        return [{"query": f"(GSC unavailable: {e})", "impressions": 0,
                 "position": 0}]


def overlap(entries, target):
    core = {w for w in target.lower().split() if w not in STOP_WORDS}
    return [e for e in entries
            if len(core & {w for w in e.replace("-", " ").split()}) >= 2]


# Question-leading words for classifying mined keywords. Derived from the
# miner's prefix list (single source of truth) minus its non-question
# modifiers.
QUESTION_WORDS = set(keyword_miner.QUESTION_PREFIXES) - {"best", "top"}

# Words too generic to count as topical "anchors" for relevance scoring.
# (Single source of truth: site_config.NICHE_GENERIC_WORDS.)
GENERIC_WORDS = site_config.NICHE_GENERIC_WORDS


def _anchors(target):
    """The target's distinctive words — what makes it *this* topic."""
    return {w for w in target.lower().split()
            if w not in STOP_WORDS and w not in GENERIC_WORDS}


_US_STATES = [
    ("alabama", "al"), ("alaska", "ak"), ("arizona", "az"), ("arkansas", "ar"),
    ("california", "ca"), ("colorado", "co"), ("connecticut", "ct"),
    ("delaware", "de"), ("florida", "fl"), ("georgia", "ga"), ("hawaii", "hi"),
    ("idaho", "id"), ("illinois", "il"), ("indiana", "in"), ("iowa", "ia"),
    ("kansas", "ks"), ("kentucky", "ky"), ("louisiana", "la"), ("maine", "me"),
    ("maryland", "md"), ("massachusetts", "ma"), ("michigan", "mi"),
    ("minnesota", "mn"), ("mississippi", "ms"), ("missouri", "mo"),
    ("montana", "mt"), ("nebraska", "ne"), ("nevada", "nv"),
    ("new hampshire", "nh"), ("new jersey", "nj"), ("new mexico", "nm"),
    ("new york", "ny"), ("north carolina", "nc"), ("north dakota", "nd"),
    ("ohio", "oh"), ("oklahoma", "ok"), ("oregon", "or"),
    ("pennsylvania", "pa"), ("rhode island", "ri"), ("south carolina", "sc"),
    ("south dakota", "sd"), ("tennessee", "tn"), ("texas", "tx"),
    ("utah", "ut"), ("vermont", "vt"), ("virginia", "va"),
    ("washington", "wa"), ("west virginia", "wv"), ("wisconsin", "wi"),
    ("wyoming", "wy"),
]
# Abbreviations that are also ordinary English words — never treat as states.
_AMBIGUOUS_ABBR = {"in", "or", "me", "hi", "ok", "pa", "ma", "la"}


def _states_in(text):
    """US states mentioned in text (names, or unambiguous abbreviations)."""
    tl = text.lower()
    toks = set(re.findall(r"[a-z]+", tl))
    found = set()
    for name, abbr in _US_STATES:
        # Name match (substring for multi-word names like "new hampshire").
        if " " in name:
            if name in tl:
                found.add(name)
        elif name in toks:
            found.add(name)
        # Abbreviation match is independent of the space check above.
        if abbr in toks and abbr not in _AMBIGUOUS_ABBR:
            found.add(name)
    return found


def _brand_states(geo_terms):
    states = set()
    for g in geo_terms:
        states |= _states_in(g)
    return states


def _norm_kw(k):
    """Normalize for near-duplicate detection (case/punct/plurals)."""
    k = re.sub(r"[^a-z0-9 ]", "", k.lower()).strip()
    return re.sub(r"\b(\w{4,})s\b", r"\1", k)


def _dedupe_key(s, geo_terms):
    """Key that collapses near-duplicates like 'austin tx plumbers'
    vs 'plumber austin texas' (geo/state tokens ignored)."""
    geo = [g.lower() for g in geo_terms]
    toks = [t for t in _norm_kw(s).split()
            if t not in STOP_WORDS and len(t) > 2
            and not any(g == t or g in t for g in geo)]
    return tuple(sorted(toks)) or (_norm_kw(s),)


def filter_secondaries(secondaries, target, geo_terms):
    """Keep only secondaries worth targeting.

    Drops: the primary itself, near-duplicates, and geo-mismatches
    (autocomplete loves suggesting other states' lakes). A keeper shares
    2+ words with the target AND (mentions a geo term OR shares 3+ words),
    and must not name a US state outside the brand's geo scope.
    """
    twords = {w for w in target.lower().split() if w not in STOP_WORDS}
    geo_terms = [g.lower() for g in geo_terms]
    brand_states = _brand_states(geo_terms)
    seen, out = set(), []
    for s in secondaries:
        sl = s.lower()
        if sl == target.lower():
            continue
        key = _dedupe_key(s, geo_terms)
        if key in seen:
            continue
        seen.add(key)
        qstates = _states_in(s)
        if brand_states and (qstates - brand_states):
            continue  # names a different state — wrong market
        if not brand_states and qstates:
            continue  # no geo scope configured — stay conservative
        swords = {w for w in sl.split() if w not in STOP_WORDS}
        shared = len(twords & swords)
        geo = any(g in sl for g in geo_terms)
        if shared >= 2 and (geo or shared >= 3):
            out.append(s)
        if len(out) >= 8:
            break
    return out


def related_entries(entries, target, n=2):
    """The n existing entries most topically related to the target.

    Anchor words (the target's distinctive terms) score 3x; entries with
    no anchor overlap aren't named — generic matches are worse than none.
    """
    anchors = _anchors(target)
    core = {w for w in target.lower().split() if w not in STOP_WORDS}
    scored = []
    for e in entries:
        ew = set(e.replace("-", " ").split())
        s = 3 * len(anchors & ew) + len((core - anchors) & ew)
        if s and (anchors & ew):
            scored.append((s, e))
    scored.sort(reverse=True)
    return [e for _, e in scored[:n]]


def _question_in_scope(question, target, geo_terms):
    """Mined questions must be about THIS topic, not another market."""
    qw = {w for w in question.lower().split() if w not in STOP_WORDS}
    core = {w for w in target.lower().split() if w not in STOP_WORDS}
    if len(core & qw) >= 2:
        return True
    return any(g.lower() in question.lower() for g in geo_terms)


def _as_list(cfg, key):
    """Optional list config that degrades cleanly on wrong types."""
    v = cfg.get(key)
    return v if isinstance(v, list) else []


def _as_dict(cfg, key):
    v = cfg.get(key)
    return v if isinstance(v, dict) else {}


def build_brief(cfg, target, kind=None):
    mined = keyword_miner.mine(target)
    geo_terms = cfg.get("geo_terms", [])
    questions = [k for k in mined
                 if k.split()[0].lower() in QUESTION_WORDS
                 and _question_in_scope(k, target, geo_terms)][:12]
    others = [k for k in mined if k not in questions][:15]
    secondaries = filter_secondaries(others, target, geo_terms)
    # Banned from copy => banned as a target keyword too. Normalize
    # separators so "e-bike"/"ebike" also catches "e bike".
    # NOTE: short banned terms over-match ("ai" hits "said"); keep banned
    # terms distinctive phrases.
    def _flat(s):
        return re.sub(r"[^a-z0-9]", "", str(s).lower())
    banned_flat = [_flat(b) for b in cfg.get("banned_terms", [])]
    banned_flat = [b for b in banned_flat if b]  # empty bans everything
    if banned_flat:
        secondaries = [k for k in secondaries
                       if not any(b in _flat(k) for b in banned_flat)]
    related = gsc_related(cfg, target)
    entries = existing_entries(cfg)
    dupes = overlap(entries, target)
    link_targets = [e for e in related_entries(entries, target)
                    if e not in dupes][:2]
    categories = cfg.get("categories", {})
    type_map = site_config.need_dict(cfg, "type_category_map")
    kind = kind or next(iter(type_map), "guide")
    category = type_map.get(kind) or next(iter(categories), "uncategorized")
    kind_name = cfg.get("content_kind", "Journal")
    suffix_map = site_config.need_dict(cfg, "type_slug_suffix")
    slug = slugify(target + suffix_map.get(kind, ""))
    voice_rules = cfg.get("voice_rules", [])
    services_note = cfg.get("services_note", "")
    hub_strategy = cfg.get("hub_strategy", "")

    title_words = target.title()
    templates = site_config.need_list(cfg, "title_templates", non_empty=True,
                                       default=DEFAULT_TITLE_TEMPLATES)
    titles = [_render_template(t, "title_templates entry",
                               title=title_words) for t in templates]
    image_alt = _render_template(cfg.get("image_alt_template", "{title} — {name}"),
                                 "image_alt_template",
                                 title=title_words, name=cfg["name"])

    L = [f"# {kind_name} brief: {target} ({cfg['name']})", "",
         f"Type: {kind} | Category: `{category}` | Suggested slug: `{slug}`",
         f"Date: {datetime.date.today()}", ""]
    angle = _as_dict(cfg, "type_angles").get(kind)
    if angle:
        L.append(f"Angle: {angle}")
        L.append("")
    length = cfg.get("length_targets", {}).get(kind)
    if length:
        L.append(f"Target length: ~{length}")
        L.append("")
    L.append("## Overlap check — existing entries on this topic")
    if dupes:
        for d in dupes:
            L.append(f"- ⚠ `{d}` — differentiate or refresh instead of duplicating")
    else:
        L.append("- none found — clear to draft")
    L.append("")
    L += ["## Working titles (pick one, keep under 60 chars)",
          *[f"- {t}" for t in titles], "",
          "## Keywords",
          f"- Primary: `{target}` (in title, H1, first 100 words, one H2, image alt)",
          "- Secondary (filtered for geo relevance — verify before targeting):"]
    core_words = {w for w in target.lower().split() if w not in STOP_WORDS}
    # Strictly tighter than filter_secondaries' own >=2 gate (which these
    # already passed): a secondary must share 3+ content words or name the
    # brand's geo, otherwise it's a neighboring-topic leak (e.g. Lake Mary
    # keywords in a Lake Nona brief).
    usable = [k for k in secondaries
              if len(core_words & {w for w in k.lower().split()
                                   if w not in STOP_WORDS}) >= 3
              or any(g.lower() in k.lower() for g in geo_terms)]
    if usable:
        L += [f"  - `{k}`" for k in usable]
    elif secondaries:
        # Survivors share <2 content words with the primary (e.g. a
        # neighboring city) — listing them invites keyword stuffing.
        L.append("  - (none usable — survivors don't match this topic closely "
                 "enough; write to the primary only)")
    else:
        L.append("  - (none survived filtering)")
    L += ["", "## Questions to answer (use as H2s)"]
    if questions:
        L.append("_(mined from real searches — keep the strong ones; "
                 "a weak one can fold into the intro)_")
        L += [f"- {q.capitalize()}?" if not q.endswith("?") else f"- {q}"
              for q in questions]
    scaffold = cfg.get("h2_scaffolds", {}).get(kind, [])
    if len(questions) < 3 and scaffold:
        # Plain-text note, NOT a bullet: a bullet here reads as an H2.
        L += ["", "_(mining was thin — type-based scaffolds below; "
              "treat as starting points, not mandates)_"]
        L += [f"- {h}" for h in scaffold]
    if not questions and not scaffold:
        L.append("- (none mined — draft from experience)")
    if any("cost" in q.lower() for q in questions + scaffold):
        L.append("- _For any cost H2: use only published/sourced ranges or "
                 "describe what drives cost — never state a specific price._")
    L += ["", "## What Google already shows us for (GSC, 28d)"]
    shown = False
    for r in related:
        if r["impressions"]:
            shown = True
            L.append(f"- `{r['query']}` — {r['impressions']:.0f} impr, "
                     f"pos {r['position']:.1f}")
    if not shown:
        failed = next((r["query"] for r in related
                       if r["query"].startswith("(GSC unavailable")), None)
        L.append(f"- {failed}" if failed else
                 "- (no matching queries in the last 28d)")
    named = _venue_named_queries(related, target, geo_terms,
                                 cfg.get("brand_terms", []))
    shot = _as_list(cfg, "shot_venues")
    if named or shot or kind == "venue-guide":
        L += ["", "## Venues to cover"]
        if named:
            L.append("Real demand from GSC — cover the ones you've actually shot:")
            L += [f"- `{r['query']}` — {r['impressions']:.0f} impr, "
                  f"pos {r['position']:.1f}" for r in named]
        if shot:
            L.append("Venues the studio has shot (safe to recommend by name):")
            L += [f"- {v}" for v in shot]
        if not named and not shot:
            L.append("- (no venue-named queries in GSC yet — research the area's "
                     "venues and list the ones you've shot before drafting)")
        L.append("- Never present a venue you haven't shot as a recommendation.")
    L += ["", "## Internal links to include"]
    if hub_strategy:
        L.append(f"- Hub strategy: {hub_strategy}")
    if link_targets:
        L.append("- Link these existing entries (most topically related):")
        L += [f"  - `{e}`" for e in link_targets]
    else:
        L.append("- (no related entries found — skip this step)")
    L += ["- Soft CTA: link the site's contact page (and pricing/booking page where natural).",
          "", "## Images",
          f"- Hero: pick a real brand photo from `{cfg.get('image_library', 'the site’s image library')}`; "
          "add per the site's image workflow. "
          "Do NOT invent a filename — verify it exists. "
          "Tip: filenames are keyword-rich — search the library for the area/venue name first. "
          "Better: run `assign_images.py --site <slug> --topic \"<keyword>\"` — "
          "it picks the most relevant images never used before. ",
          "RULE: never reuse an image already used in another entry until the "
          "whole library has been cycled once (the script enforces this). "
          "Use 1 hero + 2 inline images per entry.",
          "- Alt text: descriptive, includes the primary keyword once.",
          "", "## Front matter",
          "```md", "---",
          f'title: "{titles[0]}"',
          f"categorySlug: {category}",
          f'image: "<chosen hero filename — must exist in {cfg.get("image_library", "the image library")}>\"',
          f'imageAlt: "{image_alt}"',
          "keywords:",
          # Quoted: an unquoted keyword containing ":" parses as a dict and
          # breaks Astro's z.array(z.string()) validation.
          *[f'  - "{k.replace(chr(34), chr(92) + chr(34))}"'
            for k in [target] + usable],
          "---", "```",
          "", "## Brand voice (non-negotiable)"]
    if services_note:
        L.append(f"- {services_note}")
    L += [f"- {r}" for r in voice_rules]
    proof = _as_list(cfg, "proof_points")
    if proof:
        L += ["", "Experience proof points (authorized claims — use naturally):"]
        L += [f"- {p}" for p in proof]
    phrases = _as_list(cfg, "preferred_phrases")
    if phrases:
        L += ["", "Preferred vocabulary (the brand's own texture — reach for these):"]
        L += [f"- {p}" for p in phrases]
    banned = cfg.get("banned_terms", [])
    if banned:
        L += ["", "## Banned terms (never use in copy)"]
        L += [f"- `{b}`" for b in banned]
    donts = cfg.get("brief_donts", [])
    if donts:
        L += ["", "## What NOT to write"]
        L += [f"- {d}" for d in donts]
    site_url = cfg.get("site_url", "").rstrip("/")
    route = cfg.get("content_route", "/").strip("/")
    entry_url = (f"{site_url}/{route}/{slug}/" if route
                 else f"{site_url}/{slug}/") if site_url else "<published-url>"
    site_slug = cfg.get("slug", "<slug>")
    repo = cfg.get("repo", "<repo>")
    content_dir = cfg.get("content_dir", "src/content/<collection>")
    draft_path = f"{repo}/{content_dir}/{slug}.md"
    gate_cmd = cfg.get("repo_gate",
                       "the repo's content gate (see its docs)")
    L += ["", "## Publish checklist",
          f"- [ ] Write the entry to `{draft_path}` (one H1 from the title; "
          "body starts at H2)",
          f"- [ ] Quality gate (HARD — must pass to publish; also enforced by "
          f"`{gate_cmd}` in the repo): from `~/workspace/seo-tools`, "
          f"`.venv/bin/python draft_score.py <draft.md> --site {site_slug} "
          f"--keyword \"{target}\"` — fix the 🟡/🔴 items and re-run until PASS",
          "- [ ] AI-sounding check (advisory only, never blocks): "
          "`.venv/bin/python ai_check.py <draft.md>`",
          "- [ ] The repo's validate passes (lint + content checks)",
          "- [ ] Social/OG image per the site's workflow (if it has one)",
          f"- [ ] Submit URL to Bing: `.venv/bin/python bing.py submit {entry_url} --site {site_slug}`",
          "- [ ] Owner: request GSC indexing (URL Inspection in the web UI)",
          "- [ ] Next weekly scan watches the target query's position"]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="target keyword/query")
    ap.add_argument("--type", dest="kind", default=None,
                    help="one of the site's type_category_map keys "
                         "(default: the first key)")
    ap.add_argument("--site", default=None, help="site slug from sites/ (default: example)")
    args = ap.parse_args()
    if not args.target:
        print(__doc__)
        return
    cfg = site_config.load(args.site)
    type_map = site_config.need_dict(cfg, "type_category_map")
    valid_kinds = sorted(type_map)
    # Insertion order, not sorted: matches build_brief's own fallback and the
    # documented "first key of type_category_map" default.
    kind = args.kind or (next(iter(type_map), "guide") if type_map else "guide")
    if args.kind and args.kind not in valid_kinds:
        ap.error(f"--type must be one of: {', '.join(valid_kinds)}")
    print(build_brief(cfg, args.target, kind))


if __name__ == "__main__":
    main()
