---
name: "seo-content-engine"
description: "Run the reusable local-SEO content engine for any brand/site: weekly opportunity scans, content briefs, drafting, optimization, publishing, and monitoring. Triggers on SEO content requests, rank-my-site asks, or setting up the content workflow for a new brand."
---

# SEO Content Engine

## Purpose
A brand-agnostic, data-driven content loop: mine real search data → pick one
topic per week → generate a full drafting brief → write, score, validate,
publish, submit, monitor. Febus Films is the reference implementation; any new
brand onboards by copying a config file, no code changes.

## Multi-site model
- Toolkit: `<wrtr>/` (venv `.venv`, scripts run as `.venv/bin/python <script>`).
- Site configs: `<wrtr>/sites/<slug>.yaml`. The multi-site-aware
  scripts (`weekly_scan.py`, `content_brief.py`, `bing.py`, `draft_score.py`)
  take `--site <slug>` (or `SEO_SITE` env); default is `example`. Helpers
  `gsc.py` and `keyword_miner.py` take explicit arguments;
  `psi_check.py` reads comma-separated `PSI_URLS` from the environment
  (falls back to the site config's URLs).
- `site_config.py` loads the YAML. Never hardcode a brand's URLs, voice, or
  rules in a script — put them in the site's YAML.
- Reference implementation: `sites/example.yaml` (filled-in example).

## The weekly loop
1. **Discover** — `weekly_scan.py [--site]` mines GSC (28d): striking distance
   (pos 8–20), low-CTR rewrites, venue-intent hub candidates, decliners → one
   pick, labeled by kind. Kind drives the action: `striking` → refresh the
   ranking page (never brief a new entry — cannibalization), `venue` → brief
   a new hub/entry, `declining` → diagnose, `lowctr` → rewrite title/meta.
   The pick's URL is liveness-checked: a dead-but-ranking URL gets
   RESTORE-OR-REDIRECT (301 to the closest live equivalent + GSC reindexing);
   a URL that now redirects elsewhere is reclassified as a venue-hub
   candidate (nothing to refresh). Dead/redirected URLs never count as hub
   coverage.
   Cron `febus-weekly-seo-scan` does this Mondays ~9:45am ET for Febus.
2. **Brief** — `content_brief.py "<query>" --type=<one of the site's type_category_map keys — e.g. venue-guide for Febus> [--site]`
   → titles, slug, keywords, H2s from real autocomplete questions, live GSC
   data, overlap check vs existing entries, internal links, images, front
   matter, brand voice rules.
3. **Draft** — write the markdown entry in the site's `content_dir` per its
   workflow doc and voice rules.
4. **Optimize** — run the hard quality gate: `draft_score.py <draft.md>
   --site <slug> --keyword "<target>"` must PASS (score ≥ the site's
   `draft_score_min`, default 80; no hard failures). Iterate on the flagged
   items until it passes. The advisory `ai_check.py` never blocks.
5. **Validate** — run the repo's validate (`pnpm validate`); fix causes, never
   weaken gates. The repo's validate should include the journal gate so the
   80-point bar is mechanically enforced, not just documented.
6. **Publish** — PR → merge → confirm live URL + OG image.
7. **Submit** — `bing.py submit <url> [--site]`; request GSC indexing in the UI.
8. **Monitor** — next scan watches the target query; the monthly layer
   (cron `<slug>-monthly-seo-layer`, 1st ~9am ET) covers competitor gaps,
   venue-hub proposals, `psi_check.py` vitals, and GBP
   status. See `references/site-onboarding.md` step 5.

Supporting tools: `keyword_miner.py` (autocomplete fan-out),
`cluster_keywords.py` (topic clusters), `serp_check.py` (needs a free SERP key),
`open-seo-crawler` (competitor content gaps), `ads_volumes.py` (parked —
needs Google brand verification).

## Tooling
| Script | What it does |
|---|---|
| `site_config.py` | Loads `sites/<slug>.yaml`; `load()` / `list_sites()` |
| `weekly_scan.py` | GSC opportunity scan → weekly pick |
| `content_brief.py` | Query → full drafting brief |
| `bing.py` | Bing top queries; `submit <url>` for instant indexing |
| `gsc.py` | Raw Search Console REST client |
| `keyword_miner.py` | Autocomplete fan-out keyword ideas |
| `psi_check.py` | CrUX + PageSpeed lab vitals |
| `draft_score.py` | **Pre-publish quality gate (HARD):** draft scores 0–100, must reach the site's `draft_score_min` (default 80). Covers readability, on-page SEO, AEO (advisory: question H2s, answer blocks, FAQ, brand entity, citable numbers, freshness), and voice |
| `ai_check.py` | Advisory AI-sounding check (local SlopTotal, see `docs/sloptotal-setup.md`); never blocks |
| `aeo_map.py` | Answer engine question map: what buyers ask AI assistants vs what the site can cite — ranked gaps to brief |
| `nap_audit.py` | NAP consistency audit: published business identity vs the canonical `local_seo:` block in the site YAML |

## Auth
- GSC: a service account (key at `<wrtr>/.sa-key.json`, 0600). Each new
  property needs the SA added once under GSC Settings → Users and
  permissions (owner does this in the UI).
- Bing: one API key at `<wrtr>/.bing-key` (0600) covers all sites
  under the owner's account; each new site must be added + verified in Bing
  Webmaster Tools (owner, one-time).
- Bulk export (optional per site): GSC → BigQuery dataset.

## Operating Rules
1. One topic per week per site. Depth beats volume.
2. Every brief and draft obeys the site's `voice_rules`, `banned_terms`, and
   `services_note` from its YAML — read the config before writing a word.
3. Never invent stats, testimonials, or claims; the site's own standing claims
   (in its repo AGENTS.md or equivalent) are the only facts.
4. New entries must be content-only (markdown + optional image); no route,
   component, or data-map edits for a single post.
5. Owner reviews the brief before any draft is written.
6. Onboarding a new brand: follow `references/site-onboarding.md`; copy
   `references/site-config-template.yaml`; drop
   `references/content-workflow-template.md` into the site repo's docs.
7. Local businesses: follow `references/local-seo-playbook.md` (operating
   model, canonical NAP, GBP/Bing/Apple, schema, reviews, citations). Fill the
   `local_seo` config block and run `local_schema_check.py` after deploys.
