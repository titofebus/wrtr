# <Brand> SEO Content Workflow

The full loop for turning search data into published content entries that
rank. One loop per week, one entry (or one page refresh) per loop.

Customize the `<angle>`-style placeholders per repo. The seo-content-engine skill owns the
toolkit; this doc owns the repo-specific mechanics.

## The weekly loop

### 1. Discover - Monday ~9:45 AM ET (automated)

The `<slug>-weekly-seo-scan` cron runs `<wrtr>/weekly_scan.py
--site <slug>` and delivers the report: striking-distance queries, low-CTR
rewrites, hub-page candidates, decliners, and **one weekly pick**.
First run prints `SETUP_PENDING` until the service-account grant (onboarding
step 2) is done - that's normal.

### 2. Brief - agent (venue picks only)

```bash
cd <wrtr>
.venv/bin/python content_brief.py "<pick query>" --type=<a key from the site's type_category_map> --site <slug>
```

The brief includes: working titles, slug, category, primary + secondary
keywords, questions to answer as H2s, live GSC data, overlap warnings,
internal-link plan, image guidance, front matter, brand-voice guardrails,
banned terms, and what-not-to-write guardrails.
**Owner reviews the brief before any draft is written.**

### 2b. Refresh / rewrite / diagnose - agent (striking, lowctr, declining picks)

Only **venue** picks get briefs. For the other pick kinds, no new entry is
drafted - that would cannibalize the page already ranking:

- **Striking (REFRESH)**: strengthen the ranking page - answer the query more
  completely, tighten the H1/title, add missing subtopics, improve internal
  links, refresh images/alt text.
- **Lowctr (REWRITE)**: rewrite the title tag and meta description - lead
  with the query, add the differentiator.
- **Declining (DIAGNOSE)**: check for a SERP change, new competitor, content
  decay, or a technical issue; fix the cause. A "disappeared" row means the
  query's page vanished from the index or moved.
- **RESTORE-OR-REDIRECT**: the URL is dead but still earns impressions -
  301-redirect it to the closest live equivalent (owner approves first).
- **REDIRECTED**: the ranking URL now 301s elsewhere - brief it like a venue
  pick (dedicated hub candidate).

### 3. Draft - agent

Write `<content_dir>/<slug>.md` following the brief, the repo's publishing
doc, and the voice rules in `sites/<slug>.yaml`.

Structure: primary keyword in title, H1, first 100 words, one H2, and image
alt. Answer the brief's questions as H2 sections. Link hub pages, 1-2 related
entries, and a soft CTA. New entries must be content-only: markdown + optional
image, no route/component/data edits.

### 4. Optimize - agent

Run the toolkit quality gate (HARD - the draft cannot publish until
this passes):

```bash
.venv/bin/python draft_score.py <draft.md> --site <slug> --keyword "<target keyword>"
```

Fix the 🟡/🔴 items and re-run until PASS (score ≥ the site's
`draft_score_min`, default 80; no hard failures). The owner can override
with `--min-score 0` - owner's call only.

Then the advisory AI-sounding check (never blocks publishing):

```bash
.venv/bin/python ai_check.py <draft.md>
```

Requires the local SlopTotal service (see the toolkit README). If the
score is elevated (≥ 55), do a human re-read against the
human-fingerprints checklist - then publish anyway if the writing is
genuinely the brand's.

### 5. Validate - agent

```bash
<validate-command, e.g. pnpm validate>
```

Fix everything it flags. Never weaken a gate - fix the cause.

### 6. Publish - agent, then deploy

<publish-flow: PR → merge → deploy> Confirm the live URL renders and
the social preview image exists.

### 7. Submit - agent

```bash
cd <wrtr>
.venv/bin/python bing.py submit https://www.example.com/<route>/<slug>/ --site <slug>
```

Then request indexing in Google Search Console (web UI, URL Inspection).

### 7b. Reindexing - owner

Requesting indexing needs the GSC web UI as the site owner - the toolkit's
service account is Viewer-only and can't do it, so this step is always the
owner's click (~10 URLs/day quota). Inspect redirect destinations too, so
Google recrawls them promptly.

### 8. Monitor - automated

The next weekly scan watches the target query's position/impressions.
`psi_check.py` tracks Core Web Vitals (Febus-only - clone and adapt the URL
list per brand, or use PageSpeed Insights manually until a multi-site version
exists). Refresh or extend the entry when the
scan flags it as striking-distance or declining.

## Monthly layer

- **Competitor gap**: crawl 3-5 outranking competitors with
  `open-seo-crawler`; feed gaps into the brief backlog.
- **Hub pages**: propose the hub page (URL, target query, why it wins) -
  owner approves before any build.
- **Vitals + data freshness**: `psi_check.py` vitals (Febus-only - see §8);
  GSC→BigQuery bulk export is optional per brand - if enabled, name the
  dataset (`<gcp-project>.<dataset>`) here and mirror the freshness check
  (latest `data_date` + `ExportLog` completeness).
- **Redirect recovery**: after any URL change/redirect, confirm 301s still
  hold and impressions migrate from old URLs to destinations (mapping lives
  in `<redirect-config, e.g. vercel.json redirects>`).
- **<brand-specific recurring work, e.g. GBP + review engine for local>**
