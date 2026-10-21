#!/usr/bin/env python3
"""wrtr_ops.py - the mechanical wrtr routines as one plain script.

AI only looks when this script says so. Subcommands:

  health            .venv + sloptotal/.venv importable, SlopTotal API up.
                    --fix rebuilds a missing venv (setup.sh) and starts SlopTotal.
  bundle KEYWORD    research bundle -> one JSON: GSC rows + content_brief + aeo_map.
  gate EN [ES]      combined publish gate: draft_score, ai_check, frontmatter,
                    internal/outbound links, hero image not reused (EN/ES twins
                    may share one image).
  prices            competitor price diff vs the last saved snapshot.
  striking          monthly: GSC queries at positions 4-15 with high impressions
                    -> page picks, plus before/after metrics per picked page.
                    Loops every active client in agency.db that has sites/<slug>.yaml.

Exit codes: 0 = clean, nothing for AI; 10 = needs AI judgment (items printed
as JSON); 1 = failed (gate failure, broken env, script error); 2 = usage.
gate (fixed interface for Web Designer's publish step):
  .venv/bin/python scripts/wrtr_ops.py gate EN_FILE [ES_FILE] --site febuslabs [--json]
  0 = pass, 1 = fail (one reason per line), 10 = needs judgment,
  2 = tool/setup error (venv or SlopTotal down, missing file).
With --wake-root DIR, a 10 also appends to DIR/logs/wake/<date>-wrtr_<cmd>.json
(the febuslabs automation format). Never prints credentials.
"""
import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # wrtr root
sys.path.insert(0, HERE)
os.environ.setdefault("SLOPTOTAL_URL", "http://localhost:8001")

import site_config  # noqa: E402

OK, FAIL, USAGE, WAKE = 0, 1, 2, 10
STATE_DIR = os.path.join(HERE, ".ops-state")
AGENCY_DB = os.environ.get("WRTR_AGENCY_DB", "/workspace/febuslabs/data/agency.db")
UA = "Mozilla/5.0 (wrtr_ops; +https://febuslabs.com)"


def emit(obj):
    print(json.dumps(obj, indent=1, ensure_ascii=False, default=str))


def _wake_file(root, name, items):
    d = os.path.join(root, "logs", "wake")
    os.makedirs(d, exist_ok=True)
    now = dt.datetime.now().astimezone()
    p = os.path.join(d, f"{now.date().isoformat()}-{name}.json")
    prev = []
    if os.path.exists(p):
        try:
            prev = json.load(open(p))
        except ValueError:
            prev = []
    prev.append({"at": now.isoformat(timespec="seconds"), "name": name, "items": items})
    with open(p, "w") as f:
        json.dump(prev, f, indent=1, default=str)
    return p


def _state(name):
    p = os.path.join(STATE_DIR, name)
    try:
        with open(p) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def _save_state(name, data):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = os.path.join(STATE_DIR, f".{name}.tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False, default=str)
    os.replace(tmp, os.path.join(STATE_DIR, name))


# --------------------------------------------------------------------- health

VENVS = {
    "wrtr": (os.path.join(HERE, ".venv"), "import yaml, textstat, requests, google.auth"),
    "sloptotal": (os.path.join(HERE, "sloptotal", ".venv"), "import fastapi, uvicorn"),
}


def check_venv(path, imports):
    py = os.path.join(path, "bin", "python")
    if not os.path.exists(py):
        return "missing"
    r = subprocess.run([py, "-c", imports], capture_output=True, timeout=120)
    return "ok" if r.returncode == 0 else "broken"


def sloptotal_up(url=None, timeout=5):
    url = (url or os.environ["SLOPTOTAL_URL"]).rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.load(r).get("status") == "healthy"
    except Exception:
        return False


def cmd_health(args):
    res = {name: check_venv(p, imp) for name, (p, imp) in VENVS.items()}
    res["sloptotal_api"] = "up" if sloptotal_up() else "down"
    fixed = []
    if args.fix:
        if res["wrtr"] != "ok" or res["sloptotal"] != "ok":
            for name in ("wrtr", "sloptotal"):
                if res[name] == "broken":  # setup.sh only creates what's missing
                    subprocess.run(["rm", "-rf", VENVS[name][0]])
            if res["sloptotal"] != "ok" and os.path.isdir(os.path.join(HERE, "sloptotal")):
                sp = VENVS["sloptotal"][0]
                subprocess.run([sys.executable, "-m", "venv", sp], check=False)
                subprocess.run([os.path.join(sp, "bin", "pip"), "install", "-q", "-r",
                                os.path.join(HERE, "sloptotal", "requirements.txt")],
                               check=False)
            subprocess.run(["bash", os.path.join(HERE, "setup.sh")],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            fixed.append("venvs")
        if res["sloptotal_api"] == "down" and check_venv(*VENVS["sloptotal"]) == "ok":
            port = os.environ["SLOPTOTAL_URL"].rsplit(":", 1)[-1].strip("/")
            log = open(os.path.join(HERE, "sloptotal", "uvicorn.log"), "a")
            subprocess.Popen([".venv/bin/python", "-m", "uvicorn", "app.main:app",
                              "--host", "127.0.0.1", "--port", port],
                             cwd=os.path.join(HERE, "sloptotal"), stdout=log,
                             stderr=log, start_new_session=True)
            import time
            for _ in range(60):  # engines take a while to load
                if sloptotal_up():
                    break
                time.sleep(5)
            fixed.append("sloptotal_api")
        res = {name: check_venv(p, imp) for name, (p, imp) in VENVS.items()}
        res["sloptotal_api"] = "up" if sloptotal_up() else "down"
    healthy = res["wrtr"] == "ok" and res["sloptotal"] == "ok" and res["sloptotal_api"] == "up"
    emit({"result": "ok" if healthy else "fail", "fixed": fixed, **res})
    return OK if healthy else FAIL


# --------------------------------------------------------------------- bundle

def gsc_rows(cfg, days=90, dims=("query", "page")):
    import gsc
    end = dt.date.today() - dt.timedelta(days=3)  # GSC data lags ~2-3 days
    start = end - dt.timedelta(days=days)
    rows = gsc.search_analytics(cfg["gsc_property"], start.isoformat(),
                                end.isoformat(), dimensions=dims)
    return [dict(zip(dims, r.get("keys", [])), clicks=r.get("clicks", 0),
                 impressions=r.get("impressions", 0),
                 ctr=round(r.get("ctr", 0), 4), position=round(r.get("position", 0), 1))
            for r in rows]


def cmd_bundle(args):
    import aeo_map
    import content_brief
    cfg = site_config.load(args.site)
    out = {"site": cfg.get("slug"), "keyword": args.keyword,
           "generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
           "errors": {}}
    try:
        rows = gsc_rows(cfg, days=args.days)
        kw = set(args.keyword.lower().split())
        out["gsc_related"] = [r for r in rows if kw & set(r["query"].lower().split())]
        out["gsc_total_rows"] = len(rows)
    except Exception as e:  # message only; never the key
        out["errors"]["gsc"] = type(e).__name__
    for name, fn in (("brief", lambda: content_brief.build_brief(cfg, args.keyword, args.type)),
                     ("aeo_map", lambda: aeo_map.build_map(cfg, cfg.get("proactive_seeds", []) or [args.keyword]))):
        try:
            out[name] = fn()
        except Exception as e:
            out["errors"][name] = f"{type(e).__name__}: {e}"[:200]
    path = args.out or os.path.join(STATE_DIR, f"bundle-{cfg.get('slug')}-{content_brief.slugify(args.keyword)}.json")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False, default=str)
    emit({"result": "ok" if not out["errors"] else "partial", "file": path,
          "gsc_related": len(out.get("gsc_related", [])), "errors": out["errors"]})
    return OK if not out["errors"] else FAIL


# ----------------------------------------------------------------------- gate

FM_REQUIRED = ("title", "description", "pubDate", "heroImage", "heroAlt")
FM_MAX = {"title": 100, "description": 200}
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")


def site_root_for(path):
    """Walk up from a post to the Astro app root (the dir holding src/pages)."""
    d = os.path.dirname(os.path.abspath(path))
    while d != "/":
        if os.path.isdir(os.path.join(d, "src", "pages")):
            return d
        d = os.path.dirname(d)
    return None


def blog_dir(root):
    return os.path.join(root, "src", "content", "blog")


def post_lang(path, fm):
    return fm.get("lang") or ("es" if os.sep + "es" + os.sep in path else "en")


def check_frontmatter(fm):
    probs = [f"missing {k}" for k in FM_REQUIRED if not fm.get(k)]
    probs += [f"{k} over {n} chars" for k, n in FM_MAX.items() if len(str(fm.get(k, ""))) > n]
    if str(fm.get("draft", "false")).lower() == "true":
        probs.append("draft: true")
    return probs


def route_exists(root, url):
    path = url.split("#")[0].split("?")[0].rstrip("/") or "/"
    pages = os.path.join(root, "src", "pages")
    if path == "/":
        return True
    m = re.fullmatch(r"(/es)?/blog/([a-z0-9-]+)", path)
    if m:
        sub = "es" if m.group(1) else ""
        return os.path.exists(os.path.join(blog_dir(root), sub, m.group(2) + ".md"))
    rel = path.lstrip("/")
    for cand in (rel + ".astro", os.path.join(rel, "index.astro"), rel + ".md"):
        if os.path.exists(os.path.join(pages, cand)):
            return True
    return os.path.exists(os.path.join(root, "public", rel))


BOT_WALL = {401, 403, 405, 429}  # page exists, the host just blocks scripts


def url_ok(url, timeout=15):
    import urllib.error
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status < 400:
                    return True
        except urllib.error.HTTPError as e:
            if e.code in BOT_WALL:
                return True
        except Exception:
            continue
    return False


def normalize_fm(fm):
    """Astro blog frontmatter -> what draft_score expects (inline lists parsed,
    pubDate/updatedDate/heroAlt aliased to date/updated/imageAlt)."""
    import yaml
    out = dict(fm)
    for k, v in fm.items():
        if isinstance(v, str) and v.strip().startswith("["):
            try:
                out[k] = yaml.safe_load(v)
            except yaml.YAMLError:
                pass
    for src, dst in (("pubDate", "date"), ("updatedDate", "updated"), ("heroAlt", "imageAlt")):
        if out.get(src) and not out.get(dst):
            out[dst] = out[src]
    return out


def check_links(body, root, online=True):
    bad, internal, outbound = [], 0, 0
    for url in dict.fromkeys(LINK_RE.findall(body)):
        if url.startswith("/"):
            internal += 1
            if root and not route_exists(root, url):
                bad.append(f"internal 404: {url}")
        elif url.startswith("http"):
            outbound += 1
            if online and not url_ok(url):
                bad.append(f"outbound unreachable: {url}")
    probs = list(bad)
    if internal < 2:
        probs.append(f"only {internal} internal links (need 2+)")
    return probs, internal, outbound


def _twin_key(path, fm):
    """EN posts key on their slug; ES posts key on translationOf's slug."""
    if fm.get("translationOf"):
        return fm["translationOf"].rsplit("/", 1)[-1]
    return os.path.splitext(os.path.basename(path))[0]


def hero_reuse(path, fm, root):
    """Other posts using the same hero image, excluding the EN/ES twin."""
    import draft_score
    img = os.path.basename(str(fm.get("heroImage", "")))
    if not img or not root:
        return []
    me, key, lang = os.path.abspath(path), _twin_key(path, fm), post_lang(path, fm)
    clashes = []
    for dirpath, _, files in os.walk(blog_dir(root)):
        for f in files:
            p = os.path.abspath(os.path.join(dirpath, f))
            if not f.endswith(".md") or p == me:
                continue
            ofm, _ = draft_score.parse_draft(p)
            if os.path.basename(str(ofm.get("heroImage", ""))) != img:
                continue
            if _twin_key(p, ofm) == key and post_lang(p, ofm) != lang:
                continue  # the twin may share it
            clashes.append(os.path.relpath(p, blog_dir(root)))
    return sorted(clashes)


def ai_score(path):
    import ai_check
    text = ai_check.draft_text(path)
    if len(text.split()) < 80:
        return None
    try:
        data = ai_check.post("/api/quick-score", {"text": text})
    except Exception:
        return "unavailable"
    return data.get("score", data.get("ai_score"))


class SetupError(Exception):
    pass


def gate_one(path, cfg, keyword=None, offline=False, no_ai=False):
    import ai_check
    import draft_score
    if not os.path.isfile(path):
        raise SetupError(f"no such file: {path}")
    fm, body = draft_score.parse_draft(path)
    fm = normalize_fm(fm)
    kw = keyword or (fm.get("keywords") or fm.get("tags") or [""])[0]
    if not kw:
        raise SetupError(f"{path}: no keywords/tags in frontmatter")
    root = site_root_for(path)
    checks, total, hard = draft_score.evaluate(fm, body, kw, cfg)
    min_score = cfg.get("draft_score_min", 80)
    name = os.path.relpath(path, blog_dir(root)) if root else os.path.basename(path)
    fails, judge = [], []
    fails += [f"{name}: draft_score HARD: {n} - {d}" for n, _, d in hard]
    if total < min_score:
        fails.append(f"{name}: draft_score {total} < {min_score}")
    fails += [f"{name}: frontmatter: {p}" for p in check_frontmatter(fm)]
    link_probs, n_int, n_out = check_links(body, root, online=not offline)
    fails += [f"{name}: links: {p}" for p in link_probs]
    clashes = hero_reuse(path, fm, root)
    if clashes:
        fails.append(f"{name}: hero image reused by: {', '.join(clashes)}")
    ai = None if no_ai else ai_score(path)
    if ai == "unavailable":
        raise SetupError("SlopTotal unreachable - run `scripts/wrtr_ops.py health --fix`")
    if isinstance(ai, (int, float)) and ai >= ai_check.ELEVATED_AT:
        judge.append(f"{name}: ai_check {ai} >= {ai_check.ELEVATED_AT}: human re-read for voice")
    return {"file": path, "fm": fm, "keyword": kw, "score": total, "min_score": min_score,
            "ai_score": ai, "internal_links": n_int, "outbound_links": n_out,
            "fail": fails, "judge": judge,
            "yellow_red": [f"{s}: {n} - {d}" for n, s, d in checks if s != "green"]}


def pair_problems(en, es):
    """EN/ES twins: ES must point at EN and share the same hero image."""
    probs = []
    slug = os.path.splitext(os.path.basename(en["file"]))[0]
    if es["fm"].get("translationOf") != f"/blog/{slug}":
        probs.append(f"pair: ES translationOf is {es['fm'].get('translationOf')!r}, expected '/blog/{slug}'")
    if post_lang(es["file"], es["fm"]) != "es":
        probs.append("pair: second file is not lang: es")
    a, b = (os.path.basename(str(x["fm"].get("heroImage", ""))) for x in (en, es))
    if a != b:
        probs.append(f"pair: EN/ES hero images differ ({a} vs {b})")
    return probs


def cmd_gate(args):
    try:
        if check_venv(*VENVS["wrtr"]) != "ok":
            raise SetupError("wrtr .venv missing/broken - run `scripts/wrtr_ops.py health --fix`")
        if not args.no_ai and not sloptotal_up():
            raise SetupError("SlopTotal down - run `scripts/wrtr_ops.py health --fix`")
        cfg = site_config.load(args.site)
        res = [gate_one(f, cfg, args.keyword if i == 0 else None, args.offline, args.no_ai)
               for i, f in enumerate([args.en] + ([args.es] if args.es else []))]
    except (SetupError, SystemExit) as e:
        if args.json:
            emit({"result": "error", "error": str(e)})
        else:
            print(f"ERROR: {e}")
        return USAGE
    fails = [f for r in res for f in r["fail"]]
    judge = [j for r in res for j in r["judge"]]
    if len(res) == 2:
        fails += pair_problems(*res)
    result = "fail" if fails else ("wake" if judge else "pass")
    if args.json:
        emit({"result": result, "fail": fails, "judge": judge, "items": fails or judge,
              "posts": [{k: v for k, v in r.items() if k != "fm"} for r in res]})
    else:
        for f in fails:
            print(f"FAIL: {f}")
        for j in judge:
            print(f"JUDGE: {j}")
        if not fails and not judge:
            print("PASS: " + ", ".join(f"{os.path.basename(r['file'])} score {r['score']}"
                                       f" ai {r['ai_score']}" for r in res))
    return FAIL if fails else (WAKE if judge else OK)


# --------------------------------------------------------------------- prices

PRICE_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?(?:\s?(?:/|per\s)\s?(?:month|mo|year|yr))?", re.I)


def page_text(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        html = r.read().decode("utf-8", "replace")
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def extract_prices(text):
    return sorted({re.sub(r"\s+", "", m).lower() for m in PRICE_RE.findall(text)})


def diff_prices(old, new):
    o, n = set(old), set(new)
    return {"added": sorted(n - o), "removed": sorted(o - n)}


def cmd_prices(args, fetch=page_text):
    cfg = site_config.load(args.site)
    comps = cfg.get("competitor_price_pages") or []
    if not comps:
        emit({"result": "wake", "items": [{"reason": "no competitor_price_pages in site yaml"}]})
        return WAKE
    name = f"prices-{cfg.get('slug')}.json"
    snap = _state(name)
    new_snap, items = {}, []
    for c in comps:
        url = c["url"]
        try:
            prices = extract_prices(fetch(url))
        except Exception as e:
            items.append({"competitor": c.get("name", url), "url": url,
                          "reason": f"fetch failed: {type(e).__name__}"})
            if url in snap:
                new_snap[url] = snap[url]
            continue
        new_snap[url] = {"name": c.get("name", url), "prices": prices,
                         "checked": dt.date.today().isoformat()}
        if url not in snap:
            continue  # first sighting is the baseline, not a change
        d = diff_prices(snap[url]["prices"], prices)
        if d["added"] or d["removed"]:
            items.append({"competitor": c.get("name", url), "url": url,
                          "reason": "prices changed", **d})
    _save_state(name, new_snap)
    emit({"result": "wake" if items else "ok", "checked": len(comps), "items": items})
    return WAKE if items else OK


# ------------------------------------------------------------------- striking

def active_client_slugs(db=AGENCY_DB):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return [r[0] for r in con.execute(
            "select slug from clients where status in ('active','grace') order by slug")]
    finally:
        con.close()


def striking_picks(rows, brand_terms, min_impr=50, lo=4, hi=15, n=3):
    """rows: query+page dicts. Group qualifying queries by page, rank pages by
    qualifying impressions."""
    pages = {}
    for r in rows:
        q = r["query"].lower()
        if any(b.lower() in q for b in brand_terms):
            continue
        if not (lo <= r["position"] <= hi) or r["impressions"] < min_impr:
            continue
        p = pages.setdefault(r["page"], {"page": r["page"], "impressions": 0, "queries": []})
        p["impressions"] += r["impressions"]
        p["queries"].append({k: r[k] for k in ("query", "impressions", "position", "ctr", "clicks")})
    ranked = sorted(pages.values(), key=lambda p: -p["impressions"])
    for p in ranked:
        p["queries"].sort(key=lambda q: -q["impressions"])
        p["queries"] = p["queries"][:8]
    return ranked[:n]


def page_metrics(rows, page):
    rs = [r for r in rows if r.get("page") == page]
    impr = sum(r["impressions"] for r in rs)
    clicks = sum(r["clicks"] for r in rs)
    pos = round(sum(r["position"] * r["impressions"] for r in rs) / impr, 1) if impr else None
    return {"clicks": clicks, "impressions": impr,
            "ctr": round(clicks / impr, 4) if impr else 0, "position": pos}


def run_striking(slug, rows, cfg, state, today, min_impr, n):
    """Pure: update state with after-metrics and new picks. Returns items."""
    site = state.setdefault(slug, {})
    items = []
    for page, rec in site.items():  # before/after for every page picked earlier
        rec.setdefault("history", []).append({"date": today, **page_metrics(rows, page)})
    taken = set(site)
    for p in striking_picks(rows, cfg.get("brand_terms", []), min_impr=min_impr, n=n + len(taken)):
        if p["page"] in taken or len(items) >= n:
            continue
        site[p["page"]] = {"picked": today, "baseline": page_metrics(rows, p["page"]),
                           "queries": [q["query"] for q in p["queries"]], "history": []}
        items.append({"site": slug, "page": p["page"], "impressions": p["impressions"],
                      "queries": p["queries"],
                      "todo": "tighten title, add the missing section, add internal links"})
    return items


def cmd_striking(args):
    slugs = args.sites.split(",") if args.sites else active_client_slugs()
    if "febuslabs" not in slugs:
        slugs.insert(0, "febuslabs")
    state = _state("striking.json")
    today = dt.date.today().isoformat()
    items, report = [], {}
    for slug in slugs:
        if not os.path.exists(os.path.join(site_config.SITES_DIR, f"{slug}.yaml")):
            items.append({"site": slug, "reason": "no sites/<slug>.yaml - onboard in wrtr"})
            continue
        cfg = site_config.load(slug)
        try:
            rows = gsc_rows(cfg, days=28)
        except Exception as e:
            items.append({"site": slug, "reason": f"GSC pull failed: {type(e).__name__}"})
            continue
        new = run_striking(slug, rows, cfg, state, today, args.min_impressions, args.n)
        items += new
        report[slug] = {"gsc_rows": len(rows), "new_picks": len(new),
                        "tracked": {p: {"baseline": r["baseline"],
                                        "latest": (r["history"] or [{}])[-1]}
                                    for p, r in state.get(slug, {}).items()}}
    _save_state("striking.json", state)
    emit({"result": "wake" if items else "ok", "sites": report, "items": items})
    return WAKE if items else OK


# ----------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--wake-root", default=None, help="write febuslabs wake file on exit 10")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("health"); h.add_argument("--fix", action="store_true")
    b = sub.add_parser("bundle"); b.add_argument("keyword")
    b.add_argument("--site", default="febuslabs"); b.add_argument("--type", default=None)
    b.add_argument("--days", type=int, default=90); b.add_argument("--out", default=None)
    g = sub.add_parser("gate"); g.add_argument("en", help="EN post (or any single post)")
    g.add_argument("es", nargs="?", help="ES twin"); g.add_argument("--json", action="store_true")
    g.add_argument("--site", default="febuslabs"); g.add_argument("--keyword", default=None)
    g.add_argument("--offline", action="store_true", help="skip outbound link fetches")
    g.add_argument("--no-ai", action="store_true", help="skip SlopTotal")
    p = sub.add_parser("prices"); p.add_argument("--site", default="febuslabs")
    s = sub.add_parser("striking"); s.add_argument("--sites", default=None)
    s.add_argument("--min-impressions", type=int, default=50); s.add_argument("--n", type=int, default=3)
    args = ap.parse_args(argv)
    cmds = {"health": cmd_health, "bundle": cmd_bundle, "gate": cmd_gate,
            "prices": cmd_prices, "striking": cmd_striking}
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cmds[args.cmd](args)
    out = buf.getvalue()
    sys.stdout.write(out)
    if rc == WAKE and args.wake_root:
        try:
            items = json.loads(out[out.index("{"):]).get("items")
        except ValueError:
            items = [{"reason": "see stdout"}]
        _wake_file(args.wake_root, f"wrtr_{args.cmd}", items)
    return rc


if __name__ == "__main__":
    sys.exit(main())
