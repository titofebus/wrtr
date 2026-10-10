# wrtr — local SEO content engine + writing quality gate

Open-source, Google-native SEO stack. No subscriptions, no hosted APIs for
the core loop: weekly opportunity scans from your own Search Console data,
content briefs, a hard pre-publish quality gate, and monitoring.

Built 2026-10-07. Extracted from a production wedding-photography site's
SEO program.

> **New here?** Start with [`docs/start-here.md`](docs/start-here.md) —
> a 15-minute walkthrough for first-time agents: what this is, how to
> install it, and your first end-to-end run.

## Quick start

```bash
git clone https://github.com/titofebus/wrtr.git
cd wrtr
./setup.sh        # creates .venv, installs deps, fetches the textstat dictionary
```

Then onboard your brand (no code changes):

```bash
cp skill/references/site-config-template.yaml sites/<slug>.yaml
# fill in name, site_url, repo, content_dir, geo_terms, banned_terms, voice_rules...
.venv/bin/python -c "import site_config; print(site_config.load('<slug>')['name'])"
```

`weekly_scan.py`, `content_brief.py`, `bing.py`, and `draft_score.py` take
`--site <slug>` (or the `SEO_SITE` env var). A full onboarding checklist is
in `skill/references/site-onboarding.md`.

## What's inside

| Tool | What it does | How to use it |
|---|---|---|
| `open-seo-crawler/` | Self-hosted site crawler (Screaming Frog replacement): titles, metas, H1s, canonicals, redirects, broken links, duplicates, schema detection, XLSX export | Flask app with headless `/crawl` POST API. Start: `.venv/bin/python open-seo-crawler/app.py`, then POST `{"url": "https://example.com", "max_pages": 60}` to `http://localhost:5002/crawl` |
| `gsc.py` | Search Console API client (sites, searchAnalytics with pagination) | `.venv/bin/python gsc.py`. Auth: service-account key in `.sa-key.json` (0600, never committed) |
| `weekly_scan.py` | Weekly content-opportunity scan: striking distance, low CTR, venue candidates, decliners → one weekly pick labeled by kind; liveness-checks the pick URL; tracks trend vs last week | `.venv/bin/python weekly_scan.py --site <slug>` → markdown brief |
| `content_brief.py` | Turns a target keyword into a full drafting brief: titles, slug, keywords, H2s from real questions, live GSC data, overlap check, internal links, images, front matter, voice rules, AEO (AI-citation) section | `.venv/bin/python content_brief.py "your keyword" --type=<brief-type> --site <slug>` |
| `aeo_map.py` | Answer engine question map: what buyers ask AI assistants vs what the site can cite — ranked gaps to brief first | `.venv/bin/python aeo_map.py --site <slug> [--seeds "a,b"]` |
| `draft_score.py` | **Pre-publish quality gate (HARD):** scores a markdown draft 0–100 on readability (textstat), on-page SEO (keyword placement, density 0.5–2.5%, headings, meta lengths, banned terms), AEO checks (advisory: question H2s, answer blocks, FAQ, brand entity, citable numbers, freshness), and human-voice signals. Must reach the site's `draft_score_min` (default 80) with no hard failures to publish. Readability needs textstat's syllable dictionary at `~/nltk_data` (setup.sh fetches it; without it readability checks degrade to yellow) | `.venv/bin/python draft_score.py <draft.md> --site <slug> --keyword "..."`. Exit 0 = PASS, 1 = blocked, 2 = usage error. Owner override: `--min-score 0` |
| `ai_check.py` | Advisory AI-sounding check via local SlopTotal (`/api/quick-score`). **Always exits 0 — never gates publishing** (detectors false-positive on polished human writing). Prints the human-fingerprints checklist when elevated (≥55) | `.venv/bin/python ai_check.py <draft.md> [--heatmap]`. Needs SlopTotal on localhost:8000 (see `docs/sloptotal-setup.md`); prints SKIPPED if down |
| `psi_check.py` | Core Web Vitals monitor: CrUX field data + PSI lab scores for key templates | `.venv/bin/python psi_check.py`. Key in `.psi-key` (0600), restricted to PSI + CrUX APIs. Note: error rows never print raw exceptions (the key rides in request URLs) |
| `keyword_miner.py` | Autocomplete fan-out keyword research (the AnswerThePublic technique): seed → Google Suggest → question/modifier expansion | `.venv/bin/python keyword_miner.py "best running shoes"` — free, no key |
| `cluster_keywords.py` | Groups a keyword list into topic clusters (TF-IDF) — each cluster = one content angle | `.venv/bin/python cluster_keywords.py kws.txt --n 8` |
| `serp_check.py` | Competitor SERP snapshots via free-tier APIs: Brave ($5/mo free), Serper (2,500 free Google queries), Exa ($10/mo free, returns page text for content-gap) | needs a 2-min signup key in `.brave-key` / `.serper-key` / `.exa-key` (0600) |
| `bing.py` | Bing Webmaster API client: top queries (a second keyword source), instant URL submission after publishing (`submit <url>`); `pages()`/`crawl_stats()` exist as Python functions only | `.venv/bin/python bing.py`; key in `.bing-key` (0600) |
| `nap_audit.py` | NAP consistency audit: checks the site's published business identity (homepage + contact page, JSON-LD business nodes) against the canonical `local_seo:` block in the site YAML - phone, email, address visibility, LocalBusiness schema | `.venv/bin/python nap_audit.py --site <slug>` |
| `ads_volumes.py` | REAL keyword volumes via Google Ads API Keyword Planner (GenerateKeywordIdeas), geo-targeted | `.venv/bin/python ads_volumes.py "seed"`. Config `.google-ads.yaml` (0600). Needs a Google Ads API token with Basic/Standard access |
| `ads_oauth.py` | One-time OAuth dance (localhost listener) that mints the Ads refresh token | credentials in `.google-ads-oauth` (0600) |
| `pytrends-modern` | Google Trends wrapper (pytrends is archived — use this) | ad-hoc trend checks only; don't schedule (429-prone) |
| `skill/` | The reusable `seo-content-engine` skill: site onboarding, config template, content-workflow template | For AI agents; see `skill/SKILL.md` |
| `ops/` | Machine-ops scripts (weekly dependency updates) | See `ops/README.md` |

## The content loop

1. **Scan** (weekly): `weekly_scan.py --site <slug>` → one content pick from your GSC data.
2. **Brief**: `content_brief.py "<pick>" --type=<type> --site <slug>` → full drafting brief.
3. **Draft**: write the markdown entry per the brief and the site's voice rules.
4. **Gate (HARD)**: `draft_score.py <draft.md> --site <slug> --keyword "<target>"` must PASS (≥ `draft_score_min`, default 80). Wire it into the site repo's validate/publish chain so it's mechanical, not advisory — see `skill/references/content-workflow-template.md` §4.
5. **Advisory**: `ai_check.py <draft.md>` — human re-read if elevated; never blocks.
6. **Publish & submit**: `bing.py submit <url>`, request GSC indexing.
7. **Monitor**: next scan watches the target query.

## Connecting Google services (one-time, per brand)

- **Search Console**: create a service account, download its JSON key as `.sa-key.json` (0600), add the account under GSC Settings → Users and permissions. Optionally set `GSC_SERVICE_ACCOUNT` to its email for clearer setup hints.
- **PageSpeed/CrUX**: create a restricted API key (PSI + CrUX only) as `.psi-key` (0600).
- **Bing Webmaster**: verify the site, create an API key as `.bing-key` (0600).
- **Google Ads API** (optional, real volumes): run `ads_oauth.py` once; needs Basic/Standard API access.

All credential files are gitignored. Never commit them.

## Tests

`tests/test_seo_tools.py` — 122 unittest cases covering the pure functions. No network, no credentials.

Run: `.venv/bin/python -m unittest discover -s tests`

## Deliberately NOT included

- Hosted AI-detector APIs (privacy/cost/reliability) — SlopTotal runs locally.
- Docker-based tools — the reference VM can't run containers.
- `sentence-transformers`/torch — too heavy; the TF-IDF clusterer covers the need.
- Geotagging EXIF — zero measured ranking impact.
