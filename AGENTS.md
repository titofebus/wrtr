# AGENTS.md - wrtr operator manual

Read this file first. It is the complete operating manual for wrtr: what it
is, how every tool works, the exact commands, the quality gate, the owner
rules you must never break, and how to onboard a new brand. `docs/start-here.md`
is the gentler 15-minute walkthrough; this file is the reference.

## 1. What wrtr is

wrtr is a local, Google-native SEO content engine. No subscriptions, no hosted
APIs for the core loop. It runs one loop per brand, per week:

**Scan** (your own Search Console data) → **Brief** (a full drafting brief for
one topic) → **Draft** (a human or agent writes the markdown entry) →
**Gate** (`draft_score.py` must PASS) → **Publish** → **Submit** (Bing + GSC
indexing) → **Monitor** (next scan watches the target query).

It also covers AEO (Answer Engine Optimization): getting cited by ChatGPT,
Perplexity, Gemini, Copilot, Claude, and Google AI Overviews/Mode. SEO gets
you ranked; AEO gets you quoted. wrtr does both.

Public repo: `https://github.com/titofebus/wrtr`
Reference brand: Febus Films (`sites/febusfilms.yaml`), a wedding photography
studio. Any new brand onboards by copying a YAML file. No code changes.

## 2. Setup (first 15 minutes)

```bash
git clone https://github.com/titofebus/wrtr.git
cd wrtr
./setup.sh        # creates .venv, installs deps, fetches the textstat dictionary
```

All scripts run through the venv: `.venv/bin/python <script>.py`.
Multi-site scripts take `--site <slug>` (or the `SEO_SITE` env var).
Default site is `example`.

```bash
.venv/bin/python -m unittest discover -s tests   # 122 tests, must all pass
```

## 3. The weekly content loop (the job)

1. **Scan** - `.venv/bin/python weekly_scan.py --site <slug>` mines GSC (28d
   window) and prints one pick labeled by kind:
   - `venue` → brief a NEW entry (`content_brief.py`). These are hub candidates.
   - `striking` (ranking pos 8-20) → do NOT brief new content (cannibalization).
     Refresh the ranking page instead.
   - `lowctr` (pos ≤10, CTR ≤3%) → rewrite title/meta.
   - `declining` → diagnose first (SERP change? competitor? content decay?
     technical?), then act.
   - `RESTORE-OR-REDIRECT` → the ranking URL is dead: 301 it to the closest
     live equivalent, then request reindexing. Needs the owner's go.
   - `REDIRECTED` → the ranking URL now 301s elsewhere: treat as a venue-hub
     candidate, brief it like `venue`.
   The pick's URL is liveness-checked. Dead/redirected URLs never count as
   hub coverage.
2. **Brief** - `.venv/bin/python content_brief.py "<query>" --type=<brief-type>
   --site <slug>` → titles, slug, keyword map, H2s from real autocomplete
   questions, live GSC data, overlap check vs existing entries, internal
   links, images, front matter, voice rules, AEO section. The writer executes
   this brief. Do NOT draft the entry yourself unless asked; the owner
   reviews the brief first.
3. **Draft** - the entry is written as markdown in the site repo's
   `content_dir` (or `resources_dir`), following the brief and the brand's
   voice rules.
4. **Gate (HARD)** - `.venv/bin/python draft_score.py <draft.md> --site
   <slug> --keyword "<target>"` must print PASS: score ≥ the site's
   `draft_score_min` (default 80) AND zero hard failures. Fix the flagged
   items and re-run until it passes. See §5 for every check.
5. **Advisory** - `.venv/bin/python ai_check.py <draft.md>` (local SlopTotal;
   always exits 0, never blocks). Human re-read if elevated.
6. **Validate** - run the site repo's validate/lint. Fix causes, never weaken
   gates. The repo should mechanically enforce the 80-point bar (e.g. a
   journal gate in its test chain), not just document it.
7. **Publish** - merge, confirm the live URL and OG/social image.
8. **Submit** - `.venv/bin/python bing.py submit <url> --site <slug>`;
   request GSC indexing in the web UI.
9. **Monitor** - the next scan watches the target query's position.

## 4. Tool reference

| Script | What it does | Command |
|---|---|---|
| `weekly_scan.py` | Weekly opportunity scan → one labeled pick | `.venv/bin/python weekly_scan.py --site <slug>` |
| `content_brief.py` | Query → full drafting brief | `.venv/bin/python content_brief.py "<query>" --type=<type> --site <slug> [--collection journal\|resources]` |
| `draft_score.py` | Pre-publish quality gate (HARD) | `.venv/bin/python draft_score.py <draft.md> --site <slug> --keyword "<kw>" [--min-score N]` |
| `ai_check.py` | Advisory AI-sounding check (never blocks) | `.venv/bin/python ai_check.py <draft.md> [--heatmap]` |
| `aeo_map.py` | Answer engine question map: what buyers ask AI assistants vs what the site can cite | `.venv/bin/python aeo_map.py --site <slug> [--seeds "a,b"] [--no-gsc]` |
| `keyword_miner.py` | Autocomplete fan-out (the AnswerThePublic technique) | `.venv/bin/python keyword_miner.py "seed query"` |
| `cluster_keywords.py` | TF-IDF topic clusters; one cluster = one angle | `.venv/bin/python cluster_keywords.py kws.txt --n 8` |
| `assign_images.py` | Picks the most relevant never-used image from the site's library | `.venv/bin/python assign_images.py --site <slug> --topic "<keyword>"` |
| `bing.py` | Bing Webmaster: top queries, instant URL submit | `.venv/bin/python bing.py submit <url> --site <slug>` |
| `nap_audit.py` | NAP consistency audit: published business identity (homepage + contact page, JSON-LD) vs the canonical `nap:` block — phone, email, address visibility, LocalBusiness schema | `.venv/bin/python nap_audit.py --site <slug>` |
| `gsc.py` | Search Console API client (sites, searchAnalytics) | `.venv/bin/python gsc.py` |
| `serp_check.py` | Competitor SERP snapshots (needs free Brave/Serper/Exa key) | see `--help` |
| `psi_check.py` | Core Web Vitals: CrUX field + PSI lab scores | `.venv/bin/python psi_check.py` (env `PSI_URLS`, key in `.psi-key`) |
| `ads_volumes.py` | Real keyword volumes via Google Ads API (parked: needs API token) | `.venv/bin/python ads_volumes.py "seed"` |
| `open-seo-crawler/` | Self-hosted crawler (Screaming Frog replacement): titles, metas, H1s, canonicals, redirects, broken links, duplicates, schema detection, XLSX export | `.venv/bin/python open-seo-crawler/app.py`, POST to `http://localhost:5002/crawl` |

Exit codes for `draft_score.py`: 0 = PASS, 1 = blocked (fix and re-run),
2 = usage/config error.

## 5. The quality gate (`draft_score.py`) in detail

Four check groups, Yoast-traffic-light style (green = full point, yellow =
half, red = zero). Score = points / checks × 100.

**Readability** (textstat; degrades to yellow if the dictionary is missing):
reading grade 7-11, ≤25% of sentences over 20 words, no paragraph over 150
words, Flesch ease ≥ 60.

**On-page SEO:**
- Keyword in title, in H1 (front-matter title counts as the H1), in first
  100 words, in an H2, in image alt.
- Density 0.5-2.5% (red above = stuffing).
- Single H1 (missing or multiple = HARD red).
- No skipped heading levels; 600+ words.
- Banned terms (per site YAML) = HARD red.
- Title ≤ 60 chars; meta description 120-160 chars.
- 2+ internal links (advisory yellow).
- H2 keyword variety: 3+ H2s repeating the primary verbatim = yellow.
- Answer-first H2s: the first sentence under each H2 should echo the H2's
  key terms (what snippets and AI Overviews lift).

**AEO (all advisory, yellow at worst - citation is probabilistic):**
- Question H2s: ≥50% of H2s phrased as questions.
- Answer blocks: each H2 opens with a 40-80 word self-contained answer.
- FAQ section present (pair with FAQPage schema, site side).
- Brand entity: the canonical brand name appears 2+ times.
- Citable numbers: 3+ distinct numbers/stats only the brand can provide.
- Freshness: front-matter `date`/`updated` within 12 months.

**Voice (human, not AI):**
- 87 AI-tic phrases + 7 structural patterns (negative parallelism,
  corrective framing, "more than X" framing, false inclusivity,
  faux-conversational pivots, paired adjectives, bold-label bullets).
- Contractions, burstiness (varied sentence lengths), human fingerprints
  (first person, specific numbers, named people/places).
- **Em/en dashes are HARD failures.** Any `—` or `-` anywhere in the draft
  blocks publishing. Rewrite with commas, colons, periods, or hyphens.
  This is an owner rule (2026-10-07), not a suggestion.

`--min-score 0` is the owner-only escape hatch. Lowering a site's
`draft_score_min` in YAML needs the owner's explicit go.

## 6. AEO: how wrtr covers answer engines

Three touchpoints, all in the normal loop:

1. **Brief** - every `content_brief.py` output has an `## AEO` section:
   question-shaped H2s, 40-60 word answer-first openings, FAQ block,
   2-3 citable facts from the brand's proof points, canonical brand name,
   schema notes for the site dev (Article; FAQPage with FAQ blocks).
   Front matter includes `updated:` (refresh quarterly).
2. **Gate** - `check_aeo()` in `draft_score.py` verifies the above
   mechanically (advisory).
3. **Map** - `aeo_map.py --site <slug>` collects question-shaped queries
   from autocomplete mining (what buyers ask AI assistants) plus the
   site's own GSC question queries, then gap-checks them against existing
   entries by content-word overlap. Output: ranked gaps to brief first,
   then covered questions to verify for citability. Run it monthly or
   when entering a new topic area.

What wrtr deliberately does NOT do for AEO: `llms.txt` generation. The
2026 evidence says published llms.txt files are near-never requested by AI
crawlers and show no measurable citation lift. It is a 30-minute,
low-cost site-side bet, not a content strategy. Don't sell it as one.

## 7. Site config (`sites/<slug>.yaml`) - every key

`site_config.py` loads the YAML. Never hardcode brand URLs, voice, or rules
in a script; put them in the YAML. Copy `sites/example.yaml` to onboard.

- `name` - canonical brand name (also the AEO entity check target).
- `nap` - canonical business identity: `phone`, `email`, `address_hidden`
  (true for service-area businesses: no street address published anywhere),
  `address` (public storefronts only), `service_areas`. `nap_audit.py`
  verifies the site publishes exactly this. Omit unpublished fields.
- `site_url`, `repo` (local path), `content_dir`, `content_route`,
  `content_kind` - main collection (e.g. Journal at `/journal/`).
- `resources_dir`, `resources_route`, `resources_kind` - optional second
  collection for SEO-generated content (Febus: Resources at `/resources/`,
  kept out of nav; `--collection resources` in the brief).
- `banned_terms` - HARD gate failures (also blocks them as brief keywords).
- `categories`, `type_category_map`, `type_slug_suffix`, `type_angles` -
  brief types → categories, slug suffixes, one-line angles.
- `title_templates`, `image_alt_template` - `{title}`/`{name}` placeholders.
- `brand_terms` - brand queries excluded from scans; force NAVIGATIONAL intent.
- `venue_intent_words` - hub-page candidate signals for the scan.
- `scan_thresholds` - striking/lowctr/venue/declining cutoffs. Small sites
  need lower impression minimums or every bucket comes back empty.
- `hub_strategy` - one paragraph: how hubs and spokes relate for this brand.
- `services_note` - hard service boundaries (e.g. "photography only, never
  imply video").
- `voice_rules` - non-negotiable brand voice, baked into every brief.
- `proof_points` - authorized experience claims (doubles as AEO citable facts).
- `preferred_phrases` - the brand's own texture/vocabulary.
- `brief_donts` - "What NOT to write" per brand.
- `h2_scaffolds` - fallback H2s per brief type when mining is thin.
- `length_targets` - per-type word counts.
- `gsc_property` - the Search Console property URL.
- `proactive_seeds` - 2-3 broad seeds for net-new topic mining and aeo_map.
- `geo_terms` - the brand's markets; filters out-of-market keyword leaks.
- `image_library` - where real brand photos live for briefs.
- `draft_score_min` - publish bar (default 80).
- `repo_gate` - the site repo's mechanical gate command, named in briefs.
- `venue_pick_brief_type` - which `--type` a `venue` scan pick gets.

Helpers: `site_config.need_dict`, `need_list`, `need_str` fail loud with
the key name on bad config. `NICHE_GENERIC_WORDS` is the shared
too-generic-to-be-an-anchor word set.

## 8. Owner rules (never break these)

1. **No em/en dashes, ever.** `—` and `-` are HARD gate failures in drafts.
   Keep them out of wrtr's own docs, briefs, and code comments too.
2. **Score floor 80.** `draft_score_min` stays 80 unless the owner says
   otherwise, per site, explicitly.
3. **AI detection never blocks.** `ai_check.py` is advisory-only by design
   (detectors false-positive on polished human writing).
4. **Public-copy terminology is per-brand and lint-enforced.** Febus:
   "Journal", never "blog". The gate enforces it via `banned_terms`.
5. **Most effective things only; don't overload the project.** Every new
   check must earn its place: deterministic, high-leverage, cheap to run.
   When in doubt, leave it out or make it advisory.
6. **Fix causes, never weaken gates.** Publication stays blocked until the
   gate passes for real.
7. **wrtr stays brand-agnostic.** Brand specifics live in `sites/*.yaml`,
   never in scripts.

## 9. Git workflow

- Local branch is `master`; the GitHub default is `main`.
  Push with `git push origin master:main`.
- Commit messages: short imperative prefix (`seo:`, `aeo:`, `voice:`,
  `intent:`, `structural:`) + what changed.
- Run the full suite before every push: `.venv/bin/python -m unittest
  discover -s tests`.

## 10. Tests

`tests/test_seo_tools.py` - pure-function unit tests. No network, no
credentials, no real files (tmp files only). Fixtures use example.com URLs
and queries.

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Conventions: one `Test*` class per area; stub network with monkeypatching
(never hit real APIs); restore stubs in `finally`. Every new check or brief
section gets green-path and failing-path tests.

## 11. Credentials (never commit these)

All credential files are gitignored, 0600, and live in the repo root:

- `.sa-key.json` - GSC service-account key (`gsc.py`, `weekly_scan.py`).
- `.psi-key` - PageSpeed/CrUX restricted key (`psi_check.py`).
- `.bing-key` - Bing Webmaster key (`bing.py`).
- `.brave-key` / `.serper-key` / `.exa-key` - SERP snapshot keys.
- `.google-ads.yaml` + `.google-ads-oauth` - Ads API (volumes, parked).

Missing credentials degrade gracefully: the scan prints SETUP_PENDING or
GSC_UNAVAILABLE with a one-line reason instead of crashing.

## 12. The skill

`skill/` holds the reusable `seo-content-engine` skill (SKILL.md +
references/): site onboarding checklist, site-config template,
content-workflow template. Onboard a brand by following
`skill/references/site-onboarding.md`; the config template is
`skill/references/site-config-template.yaml`.

## 13. Docs map

- `AGENTS.md` (this file) - the operator manual.
- `docs/start-here.md` - 15-minute first-run walkthrough.
- `docs/sloptotal-setup.md` - local SlopTotal setup for `ai_check.py`.
- `README.md` - public-facing overview and tool table.
