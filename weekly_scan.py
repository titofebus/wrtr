"""Weekly content-opportunity scan (the engine's discovery step).

Mines Google Search Console query data and produces a markdown brief:
1. Striking distance - positions 8-20, optimize the existing page
2. High impressions + low CTR - rewrite title/meta
3. Venue-intent queries with no dedicated hub page - new hub candidate
4. Declining queries - diagnose
5. One recommended pick for the week, labeled by kind with the correct
   action (striking->refresh, venue->brief a new hub/entry,
   declining->diagnose, lowctr->rewrite). The pick's URL is liveness-checked:
   a dead-but-ranking URL gets RESTORE-OR-REDIRECT; a URL that now redirects
   elsewhere is reclassified as a venue-hub candidate (nothing to refresh).
   Dead/redirected URLs never count as hub coverage in bucket 3.

The pick persists to .weekly-pick-<slug>.json so the next run reports
movement vs last week.

Usage: .venv/bin/python weekly_scan.py [--site <slug>]
Site config lives in sites/<slug>.yaml.
Requires: the service account in .sa-key.json added as a user
on the GSC property (one-time, in the GSC web UI).
"""
import argparse
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gsc  # noqa: E402
import site_config  # noqa: E402

# Words too generic to identify a dedicated hub page.
_HUB_GENERIC = {"the", "a", "an", "in", "of", "for", "and", "or", "to", "at",
                "near"} | site_config.NICHE_GENERIC_WORDS


def _stem(w):
    """Crude singularization so 'venues' matches venue-word 'venue'."""
    return w[:-1] if w.endswith("s") and len(w) > 3 else w


def _has_venue_intent(query, venue_words):
    """Word-boundary match so 'venue' doesn't fire on 'avenue'."""
    words = {_stem(w.strip("-,.")) for w in query.lower().split()}
    return any(_stem(w) in words for w in venue_words)


def _looks_like_hub(query, page, content_route="/journal/"):
    """True if the page URL already looks like a dedicated hub for the query.

    Content entries (under content_route) are never hubs - the hub strategy
    wants dedicated pages distinct from entries, so an entry whose slug
    happens to match the query must NOT suppress the hub candidate.
    """
    path = page.split("?")[0].rstrip("/")
    route = content_route.rstrip("/")
    if route + "/" in path + "/":
        return False
    slug = path.rsplit("/", 1)[-1].lower()
    terms = [w.strip("-,.") for w in query.lower().split()
             if w.strip("-,.") not in _HUB_GENERIC]
    if not terms:
        return True  # nothing distinctive - assume covered
    hits = sum(1 for w in terms if w in slug)
    return hits >= 2 or "-".join(terms) in slug


def is_brand(q, brand_terms):
    ql = q.lower()
    return any(b in ql for b in brand_terms)


def _q(q):
    """Render a GSC query safely inside a markdown code span."""
    return q.replace("`", "'")


def rows_to_dict(rows, dims):
    out = []
    for r in rows:
        d = dict(zip(dims, r["keys"]))
        d.update({k: r.get(k, 0) for k in ("clicks", "impressions", "ctr", "position")})
        out.append(d)
    return out


def _gsc_call(fn, *args, **kwargs):
    """Run a GSC API call with a clean failure message.

    A traceback can't tell the cron worker "Google is down, retry next
    week" from "our key is dead, needs the owner" - this prints GSC_UNAVAILABLE
    with a one-line reason, flagging auth failures as owner action.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        name = type(e).__name__.lower()
        msg = str(e).lower()
        auth = any(k in name or k in msg for k in
                   ("refresh", "credential", "auth", "permission", "forbidden",
                    "unauthorized", "invalid_grant"))
        owner = (" - owner action: check the service-account grant/key"
                 if auth else " - likely transient; retry next run")
        print(f"GSC_UNAVAILABLE: {type(e).__name__}: {e}{owner}")
        raise SystemExit(2)


def classify_pick(kind_pick, page):
    """Liveness-check the pick's page and reclassify if needed.

    Returns (kind, status, final_url, redirected). A striking pick whose
    URL is now a redirect becomes a venue pick - there is no page left to
    refresh, so the cron briefs the dedicated hub instead.
    """
    status, final_url = _liveness(page)
    redirected = _norm_url(final_url) != _norm_url(page)
    if redirected and kind_pick == "striking":
        kind_pick = "venue"
    return kind_pick, status, final_url, redirected


def _looks_named_venue(query, geo_terms):
    """Query names a specific venue rather than a generic topic."""
    generic = {"wedding", "weddings", "venue", "venues", "photographer",
               "photography", "photo", "photos", "the", "a", "an", "in",
               "of", "for", "and", "or", "to", "at", "best", "top", "near",
               "me", "my"}
    # Strip punctuation so "st. augustine" matches "st augustine".
    norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower())
    geo_words = {w for g in geo_terms for w in norm(g).split()}
    words = norm(query).split()
    distinctive = [w for w in words
                   if w not in generic and w not in geo_words]
    return (len(words) >= 4 and len(distinctive) >= 2
            and bool(geo_words & set(words)))


def main(site_slug=None, save_pick=True):
    global _HUB_VERIFY_COUNT
    _HUB_VERIFY_COUNT = 0  # module counter must not leak across main() calls
    cfg = site_config.load(site_slug)
    _validate_scan_config(cfg)
    site = cfg["gsc_property"]
    brand_terms = cfg.get("brand_terms", [])
    venue_words = cfg.get("venue_intent_words", [])
    geo_terms = cfg.get("geo_terms", [])
    kind = cfg.get("content_kind", "Journal")

    sites = {s["siteUrl"] for s in _gsc_call(gsc.list_sites)}
    if site not in sites:
        print(f"SETUP_PENDING: add {gsc.SA} "
              "under GSC Settings -> Users and permissions, then re-run.")
        return

    today = datetime.date.today()
    # GSC data finalizes after ~3 days; end the window 3 days back.
    # Both windows are 28 days (27 + the end date itself) so the
    # "declining" comparison is apples-to-apples.
    end = today - datetime.timedelta(days=3)
    cur_s, cur_e = (end - datetime.timedelta(days=27)).isoformat(), end.isoformat()
    prev_e = end - datetime.timedelta(days=28)
    prev_s = (prev_e - datetime.timedelta(days=27)).isoformat()

    dims = ("query", "page")
    cur = rows_to_dict(_gsc_call(gsc.search_analytics, site, cur_s, cur_e, dims), dims)
    prev = {(d["query"], d["page"]): d
            for d in rows_to_dict(_gsc_call(gsc.search_analytics, site, prev_s, prev_e.isoformat(), dims), dims)}

    nb = [d for d in cur if not is_brand(d["query"], brand_terms)]
    th = cfg.get("scan_thresholds", {})
    s_imp = th.get("striking_min_impressions", 10)
    s_lo, s_hi = th.get("striking_min_position", 8), th.get("striking_max_position", 20)
    l_imp = th.get("lowctr_min_impressions", 50)
    l_pos = th.get("lowctr_max_position", 10)
    l_ctr = th.get("lowctr_max_ctr", 0.03)
    v_imp = th.get("venue_min_impressions", 10)
    d_imp = th.get("declining_min_impressions", 30)
    d_ratio = th.get("declining_ratio", 0.7)
    striking, lowctr, venue, declining = [], [], [], []
    for d in nb:
        q, pos, imp, ctr = d["query"], d["position"], d["impressions"], d["ctr"]
        key = (d["query"], d["page"])
        p = prev.get(key)
        if s_lo <= pos <= s_hi and imp >= s_imp:
            striking.append(d)
        if imp >= l_imp and pos <= l_pos and ctr < l_ctr:
            lowctr.append(d)
        # Venue-intent query with no dedicated hub page yet -> hub candidate,
        # regardless of what page currently ranks for it. Dead/redirected
        # URLs never count as hub coverage (verified via _hub_coverage).
        if imp >= v_imp and _has_venue_intent(q, venue_words) \
                and not _hub_coverage(q, d["page"],
                                      cfg.get("content_route", "/journal/")):
            venue.append(d)
        if p and p["impressions"] >= d_imp and imp < p["impressions"] * d_ratio:
            declining.append((d, p))

    # Declining, part 2: (query, page) pairs that vanished entirely.
    # The loop above only sees current-window rows, so a full drop-off
    # (deindexed page, broken redirect) or a page change (redirect added,
    # slug renamed) would otherwise be invisible - the current (query,
    # new_page) row has no prev match to compare against.
    cur_keys = {(d["query"], d["page"]) for d in cur}
    cur_pages_by_query = {}
    for d in cur:
        cur_pages_by_query.setdefault(d["query"], []).append(d["page"])
    for (q, page), p in prev.items():
        if (q, page) in cur_keys:
            continue
        if p["impressions"] < d_imp or is_brand(q, brand_terms):
            continue
        now_pages = [u for u in cur_pages_by_query.get(q, []) if u != page]
        # Valuable disappeared (in-geo, commercial, or high volume) vs expected
        # disappeared (legacy off-topic spillover): only the former deserves
        # a diagnosis.
        in_geo = any(g.lower() in q.lower() for g in geo_terms)
        valuable = (in_geo or p["impressions"] >= 100) and not now_pages
        if now_pages:
            note = f"now ranks {now_pages[0]}"
        elif valuable:
            note = "gone from the index - valuable query, diagnose if still gone next week"
        else:
            note = "legacy off-topic spillover - let go"
        d = {"query": q, "page": page, "position": 0.0, "impressions": 0,
             "ctr": 0.0, "disappeared_note": note,
             "disappeared_valuable": valuable}
        declining.append((d, p))

    striking.sort(key=lambda d: -d["impressions"])
    lowctr.sort(key=lambda d: -d["impressions"])
    venue.sort(key=lambda d: -d["impressions"])
    declining.sort(key=lambda t: t[1]["impressions"] - t[0]["impressions"])

    ranked = ([("striking", d) for d in striking] +
              [("venue", d) for d in venue] +
              [("declining", d) for d, _ in declining] +
              [("lowctr", d) for d in lowctr])
    pick_query = ranked[0][1]["query"] if ranked else None

    def _mark(q):
        return " ← this week's pick" if q == pick_query else ""

    L = [f"# {kind} opportunity scan - {site} - {cur_s} to {cur_e}", ""]
    L.append(f"Non-brand queries analyzed: {len(nb)}")
    L.append("")
    L.append(f"## 1. Striking distance (positions {s_lo}-{s_hi}) - optimize the page")
    for d in striking[:10]:
        L.append(f"- `{_q(d['query'])}` - pos {d['position']:.1f}, {d['impressions']:.0f} impr "
                 f"-> {d['page']}{_mark(d['query'])}")
    if not striking:
        L.append("- (none this week)")
    L.append("")
    L.append("## 2. High impressions, low CTR - rewrite title/meta")
    for d in lowctr[:10]:
        L.append(f"- `{_q(d['query'])}` - pos {d['position']:.1f}, {d['impressions']:.0f} impr, "
                 f"CTR {d['ctr']*100:.1f}% -> {d['page']}{_mark(d['query'])}")
    if not lowctr:
        L.append("- (none this week)")
    L.append("")
    L.append("## 3. Venue-intent queries with no dedicated hub page - venue page candidates")
    for d in venue[:10]:
        lock = (" - LOCK IN: named venue at page 1, a dedicated page secures it"
                if d["position"] <= 10 and _looks_named_venue(d["query"], geo_terms)
                else "")
        L.append(f"- `{_q(d['query'])}` - {d['impressions']:.0f} impr -> {d['page']}{_mark(d['query'])}{lock}")
    if not venue:
        L.append("- (none this week)")
    L.append("")
    L.append("## 4. Declining (vs prior 28d)")
    steepest = None
    if declining:
        steepest = max(declining,
                       key=lambda t: (t[1]["impressions"] - t[0]["impressions"]) /
                       max(t[1]["impressions"], 1))[0]["query"]
    for d, p in declining[:10]:
        pct = (p["impressions"] - d["impressions"]) / max(p["impressions"], 1) * 100
        # Tripwire: a ≥90% wipeout to near-zero is not a "watch" - it needs
        # a diagnosis or a hub brief next week, not passive monitoring.
        # Skipped for disappeared rows classified "let go" (expected
        # off-topic spillover); uses the flag, not the note prose.
        valuable = d.get("disappeared_valuable", True)
        if pct >= 90 and d["impressions"] <= 5 and valuable:
            flag = " - TRIPWIRE: diagnose next week or brief the hub, don't just watch"
        elif d["query"] == steepest:
            flag = " - steepest drop, watch"
        else:
            flag = ""
        note = f" - {d['disappeared_note']}" if d.get("disappeared_note") else ""
        L.append(f"- `{_q(d['query'])}` - {p['impressions']:.0f} -> {d['impressions']:.0f} impr "
                 f"(-{pct:.0f}%) ({d['page']}){_mark(d['query'])}{flag}{note}")
    if not declining:
        L.append("- (none this week)")
    L.append("")
    L.append("## 5. This week's pick")
    # Pick order: striking (refresh page) > venue (new hub/entry) >
    # declining (diagnose) > lowctr (rewrite title/meta). A striking-distance
    # pick must NOT become a new entry brief - that would cannibalize the
    # page already ranking.
    brief_type = cfg.get("venue_pick_brief_type") or next(iter(cfg.get("type_category_map", {}) or {}), "venue-guide")
    brief_cmd = (f"`.venv/bin/python content_brief.py "
                 f"\"{{q}}\" --type={brief_type} --site {cfg['slug']}`")
    ACTIONS = {
        "striking": "REFRESH the existing page for this query (do not brief a new entry).",
        "venue": f"NEW hub page or entry - run {brief_cmd.format(q=ranked[0][1]['query']) if ranked else brief_cmd}.",
        "declining": "DIAGNOSE the drop (competition? content decay? SERP change?), then fix.",
        "lowctr": "REWRITE the title/meta of the existing page.",
    }
    pick = ranked[0] if ranked else None
    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              f".weekly-pick-{cfg['slug']}.json")
    if pick:
        kind_pick, d = pick
        orig_kind = kind_pick
        kind_pick, status, final_url, redirected = classify_pick(kind_pick,
                                                                d["page"])
        if redirected and orig_kind == "striking":
            L.append("Kind: venue (redirected - was striking)")
        else:
            L.append(f"Kind: {kind_pick}")
        L.append(f"Target: `{_q(d['query'])}` (pos {d['position']:.1f}, "
                 f"{d['impressions']:.0f} impressions/28d)")
        if redirected:
            L.append(f"Page: {d['page']} (301 → {final_url})")
        else:
            L.append(f"Page: {d['page']}")
        if status in (404, 410, "LOOP"):
            L.append(f"Action: RESTORE-OR-REDIRECT - this URL returns HTTP "
                     f"{status} but still earns impressions. 301-redirect it "
                     f"to the closest live equivalent (or restore the content), "
                     f"then request reindexing in GSC.")
        elif redirected:
            L.append(f"Action: REDIRECTED - this URL 301s to {final_url}, so "
                     f"there is no page to refresh. Brief the dedicated hub: "
                     f"run {brief_cmd.format(q=d['query'])}.")
            L.append("Note: you're capturing demand currently attributed to a "
                     "redirecting legacy URL - expect position volatility for "
                     "2-4 weeks post-publish as Google consolidates. Build at "
                     "the brief's clean slug; do NOT resurrect the legacy slug.")
        else:
            L.append(f"Action: {ACTIONS[kind_pick]}")
        prev_pick = _load_pick(state_path)
        if prev_pick and prev_pick["query"] == d["query"]:
            dp = d["position"] - prev_pick["position"]
            di = d["impressions"] - prev_pick["impressions"]
            trend = (f"vs last pick ({prev_pick['date']}): "
                     f"position {prev_pick['position']:.1f} -> {d['position']:.1f} "
                     f"({dp:+.2f}), impressions {prev_pick['impressions']:.0f} -> "
                     f"{d['impressions']:.0f} ({di:+.0f})")
            L.append(trend)
            if prev_pick.get("kind") in (orig_kind, kind_pick):
                L.append(f"Note: same pick as last week - if the action was "
                         f"already taken, keep tracking the trend; if not, "
                         f"say so explicitly in the chat report so the owner can decide.")
        elif prev_pick:
            L.append(f"Last week's pick was `{prev_pick['query']}` "
                     f"(pos {prev_pick['position']:.1f} on {prev_pick['date']}) - "
                     f"rotated to a new target this week.")
        if save_pick:
            _save_pick(state_path, {"date": cur_e, "query": d["query"],
                                    "page": d["page"], "position": d["position"],
                                    "impressions": d["impressions"], "kind": kind_pick,
                                    "http_status": status,
                                    "final_url": final_url if redirected else None})
    else:
        L.append("Not enough non-brand data yet - check again next week.")
    # Proactive bucket: miner suggestions with zero GSC presence. Every other
    # bucket is reactive (it optimizes queries that already have impressions);
    # this one finds net-new hub/entry topics the site doesn't rank for at all.
    L.append("")
    L.append("## 6. Proactive opportunities (zero GSC presence - net-new topics)")
    seeds = cfg.get("proactive_seeds", [])
    if seeds:
        import keyword_miner
        import content_brief as _brief
        gsc_queries = {d["query"].lower() for d in cur}
        seen, fresh = set(), []
        for seed in seeds[:3]:
            try:
                for kw in keyword_miner.mine(seed, depth=1):
                    kl = kw.lower()
                    if kl not in gsc_queries and kl not in seen:
                        seen.add(kl)
                        fresh.append(kw)
            except Exception:
                pass  # miner failure must not kill the scan
        # Same filters the brief applies: geo, banned terms. Unfiltered
        # miner output is where other-market junk comes from.
        fresh = _brief.filter_secondaries(fresh, seeds[0], geo_terms)
        banned_flat = [re.sub(r"[^a-z0-9]", "", str(b).lower())
                       for b in cfg.get("banned_terms", [])]
        banned_flat = [b for b in banned_flat if b]
        if banned_flat:
            fresh = [k for k in fresh
                     if not any(b in re.sub(r"[^a-z0-9]", "", k.lower())
                                for b in banned_flat)]
        for kw in fresh[:8]:
            L.append(f"- `{_q(kw)}` - no GSC presence; candidate for a new entry/hub")
        if not fresh:
            L.append("- (miner found nothing new this week)")
    else:
        L.append("- (no proactive_seeds in site config - add 2-3 seed queries to enable)")
    print("\n".join(L))


_LIVE = {}
_HUB_VERIFY_COUNT = 0
_HUB_VERIFY_MAX = 8  # cap sequential HTTP checks in the venue bucket (N3)


def _norm_url(u):
    """Scheme-insensitive URL comparison (http→https isn't a real redirect)."""
    return re.sub(r"^https?://", "", u, flags=re.IGNORECASE).rstrip("/")


def _liveness(url, timeout=15):
    """(HTTP status, final URL) following redirects; (None, url) if uncheckable.

    A redirect loop reports status "LOOP" (effectively dead). Results are
    cached so bucket checks and the pick check share one request.
    """
    import requests
    if url in _LIVE:
        return _LIVE[url]
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True)
        res = (r.status_code, r.url)
    except requests.TooManyRedirects:
        res = ("LOOP", url)
    except Exception:  # noqa: BLE001
        res = (None, url)
    _LIVE[url] = res
    return res


def _hub_coverage(query, page, content_route):
    """Does a real, live hub page cover this query?

    A dead, looping, or redirected-away URL is not coverage. When the page
    redirects, the *destination* is tested instead (a legacy slug 301ing to
    a real hub still counts as covered).
    """
    global _HUB_VERIFY_COUNT
    if not _looks_like_hub(query, page, content_route):
        return False
    if _HUB_VERIFY_COUNT >= _HUB_VERIFY_MAX:
        return True  # unverified: assume covered, avoid duplicate proposals
    _HUB_VERIFY_COUNT += 1
    status, final = _liveness(page, timeout=8)
    if status in (404, 410, "LOOP"):
        return False
    if _norm_url(final) != _norm_url(page):
        return _looks_like_hub(query, final, content_route)
    return True


def _validate_scan_config(cfg):
    """Fail fast with a clean error on wrong-typed config values.

    Catches the hostile shapes an adversarial audit found: scan_thresholds
    as a string, non-numeric threshold values, content_route as int/null/
    empty, brand/venue word lists as bare strings or with non-string items.
    """
    site_config.need_number_mapping(cfg, "scan_thresholds")
    site_config.need_str(cfg, "content_route", non_empty=True,
                         default="/journal/")
    for key in ("brand_terms", "venue_intent_words"):
        v = cfg.get(key, [])
        if isinstance(v, str):
            v = [v]  # bare string -> single term (else chars get iterated)
        if not isinstance(v, list):
            raise SystemExit(f"Site config error: '{key}' must be a list of "
                             f"strings, got {type(v).__name__}.")
        cfg[key] = [str(t) for t in v]


def _load_pick(path):
    import json
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    # Guard against valid JSON with the wrong shape OR wrong value types
    # (hand-edited / partially-written state) - "no prior pick", never crash.
    if not isinstance(data, dict):
        return None
    req = {"date": str, "query": str, "page": str, "kind": str,
           "position": (int, float), "impressions": (int, float)}
    for k, t in req.items():
        v = data.get(k)
        if isinstance(v, bool) or not isinstance(v, t):
            return None
    return data


def _save_pick(path, pick):
    import json
    try:
        with open(path, "w") as f:
            json.dump(pick, f)
        os.chmod(path, 0o600)
    except OSError:
        pass  # state is a nicety; the printed report is the deliverable


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=None, help="site slug from sites/ (default: example)")
    ap.add_argument("--no-save", action="store_true",
                    help="don't write the weekly-pick state file (for the "
                         "monthly cron's fresh-data re-run, which must not "
                         "clobber the weekly trend state)")
    args = ap.parse_args()
    main(args.site, save_pick=not args.no_save)