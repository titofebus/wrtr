# Onboarding a new brand/site to the SEO content engine

Checklist. Most steps are one-time; the site owner does the UI clicks,
the agent does everything else.

## 1. Site config (agent)
1. Copy `references/site-config-template.yaml` to
   `<wrtr>/sites/<slug>.yaml`.
2. Fill in: `name`, `site_url` (`gsc_property` defaults to this — set it
   separately only if the GSC property differs), `repo`, `content_dir`,
   `content_route`, `content_kind`, `banned_terms`, `categories`, `brand_terms`,
   `venue_intent_words` (or equivalent intent words for the niche),
   `hub_strategy`, `services_note`, `voice_rules` (from the brand's
   AGENTS.md or brand doc — never invent voice),
   `type_category_map`, `title_templates`, `image_alt_template`,
   `scan_thresholds` (copy the defaults from the template and adjust).
   Type-name semantics: the `type_category_map` keys ARE the `--type` values
   for `content_brief.py` — rename them per brand (e.g. a bike-tour brand
   wants `trail-guide`, not `venue-guide`). Optional `type_slug_suffix`
   appends a slug suffix per type. No type name has magic behavior in code;
   if you find one, that's a bug — report it, don't work around it.
   Brief-quality keys (all optional, all documented in the template):
   `geo_terms` (filters brief secondaries to the brand's market — without it,
   autocomplete will suggest other states' keywords), `length_targets`,
   `h2_scaffolds`, `brief_donts`, `image_library`, `venue_pick_brief_type`,
   `draft_score_min` (the hard pre-publish quality bar, 0–100, default 80 —
   drafts below it cannot ship).
4. Wire the quality gate into the repo's validate chain (like Febus's
   `pnpm gate:journal` → `tasks/journal-gate.mjs`): score changed entries
   with `draft_score.py` using each draft's first `keywords:` front-matter
   entry as the target keyword, and fail the build when the gate fails.
   A documented gate nobody enforces is decoration.
5. Verify (from `<wrtr>`):
   ```bash
   cd <wrtr> && .venv/bin/python -c "import site_config; print(site_config.load('<slug>')['name'])"
   cd <wrtr> && .venv/bin/python weekly_scan.py --site <slug>
   ```
   Expect SETUP_PENDING until step 2 is done — that's normal.

## 2. Google Search Console (owner in the UI, agent verifies)
1. Owner: GSC → Settings → Users and permissions → add
   the service account (the email in `.sa-key.json`) as Viewer on the property.
2. Agent verifies:
   ```bash
   cd <wrtr> && REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt .venv/bin/python -c "import gsc; print([s['siteUrl'] for s in gsc.list_sites()])"
   ```
   Expect the property listed (permission `siteFullUser` or similar).
3. Optional but recommended — owner: GSC → Settings → Bulk data export →
   enable to your BigQuery dataset (forward-only history; every week
   delayed is history lost). Note: the monthly freshness query reads the
   whole dataset, so if several properties share it, `MAX(data_date)` is
   dataset-wide, not per-brand — filter by property when that matters.

## 3. Bing Webmaster Tools (owner in the UI, agent verifies)
1. Owner: add + verify the site at bing.com/webmasters under your account.
2. Agent verifies: `cd <wrtr> && .venv/bin/python bing.py --site <slug>`
   returns query rows. (The existing `.bing-key` covers all sites on the account.)

## 4. Repo docs (agent)
1. Copy `references/content-workflow-template.md` into the site repo's docs
   (e.g. `docs/seo-content-workflow.md`), customized with the repo's real
   validate/build/publish commands.
2. Confirm the repo has (or add) the publishing mechanics doc: where markdown
   entries live, front matter fields, image workflow, category slugs, and the
   terminology lint (e.g. Journal-vs-blog).

## 5. Recurring crons (agent)
1. Weekly scan: `cron.add` id `<slug>-weekly-seo-scan`, weekly Monday ~9am
   America/New_York (flexible_time: true). Clone the Febus
   `febus-weekly-seo-scan` body and swap the site — it already handles all
   pick kinds (venue/striking/lowctr/declining), the do-not-brief rule,
   RESTORE-OR-REDIRECT, and the BigQuery landing check.
   Swap checklist: every `--site febusfilms` → `--site <slug>`, the cron id
   and title, the chat delivery target, and the workflow-doc path.
2. Monthly layer: `cron.add` id `<slug>-monthly-seo-layer`, monthly on the
   1st ~9am America/New_York — competitor gap crawl, venue-hub proposal,
   BigQuery freshness check, vitals, GBP status.
   (Clone the reference monthly-layer body and swap the site —
   same swap checklist.)
   NOTE: `psi_check.py` reads its URLs from `PSI_URLS` (comma-separated);
   set that env var per brand, or it falls back to the example URLs.
3. Owner reviews the brief before any draft is written (standing rule).

## 6. First run
Run the scan + brief manually once to prove the pipeline end to end, then
let the cron take over. Note the new site in the daily log
(`~/memory/YYYY-MM-DD.md`) under the brand's section.


## Local SEO setup (for local businesses; follow references/local-seo-playbook.md)
1. Decide the operating model with the owner (storefront, service_area, hybrid)
   and fill the `local_seo` block. A service-area business hides its address:
   no street address, map pin or geo on the site or in schema.
2. Canonical NAP record: one exact name, phone, website and email used everywhere
   (site, schema, GBP, Bing, Apple, citations). Never invent a phone or address.
3. GBP website link uses `gbp_utm` so GBP traffic is separable in GA4.
4. Check schema after every deploy:
   `.venv/bin/python local_schema_check.py https://<site>/ --site <slug>`
   (phone present and matching, SAB has no address/geo, areaServed present).
5. Area/city pages: content_brief adds a doorway guard when the target names
   a place. No mass city or ZIP pages.
6. Review asks: draft_score HARD-fails incentivized, star-conditioned, gated or
   Yelp review solicitations (FTC rule, Google and Yelp policy).
7. First wave order: GBP, site and domain, GSC, GA4/GTM, Bing Places, Apple
   Business, core citations, review system, Central Florida orgs. Report each
   item as done, gap, or needs the owner.
