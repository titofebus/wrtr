# Start here — wrtr for first-time agents

If you've never touched this repo before, read this page first. It takes
about 15 minutes and leaves you able to run the whole loop yourself.

## What this is

**wrtr** is a local SEO content engine with a writing-quality gate. In plain
terms, it does two jobs:

1. **Finds what to write.** It reads your site's Google Search Console data,
   spots queries where you almost rank (page 2, rising impressions), and
   turns the best opportunity into a content brief.
2. **Makes sure it's good before it publishes.** Every draft is scored 0–100
   on readability, on-page SEO, and human-voice signals. Below 80 (or any
   hard failure like a missing H1), it **cannot publish** — the repo's
   validation enforces this mechanically, not as a suggestion.

Everything runs locally. No subscriptions, no hosted APIs in the core loop.
The only network calls are to Google's own APIs (Search Console, PageSpeed)
using keys you provide.

## The loop, in one paragraph

Once a week you run `weekly_scan.py --site <slug>`. It picks one target
query and tells you the exact command to generate a brief. You run
`content_brief.py`, write the draft from the brief, then run `draft_score.py`
on the draft until it scores 80+. Optionally you run `ai_check.py` for an
advisory second opinion. Then the site's normal validation + publish flow
takes over, and next week's scan watches how the new page performs.

## Install

```bash
git clone https://github.com/titofebus/wrtr.git
cd wrtr
./setup.sh
```

What `setup.sh` does, step by step:

1. **Creates `.venv`** — a Python virtual environment, so wrtr's dependencies
   never touch your system Python.
2. **Installs pinned dependencies** — `requests`, `pyyaml`, `textstat`,
   `scikit-learn`, and friends. If this fails, the script aborts loudly
   (a half-installed venv is worse than no venv).
3. **Fetches the syllable dictionary** — `draft_score.py` needs it for
   readability scoring. Stored once in `~/nltk_data`.
4. **Clones SlopTotal** (pinned commit) — the local AI-text detector used by
   `ai_check.py`. This is optional; everything else works without it.
5. **Runs the test suite** — 87 tests. If they don't all pass, stop and
   investigate before using the tools.

Expected end state: `setup.sh` prints "Done" and the tests say `OK`.

## Add your brand (no code changes)

Copy the template and fill it in:

```bash
cp skill/references/site-config-template.yaml sites/acme.yaml
```

Open `sites/acme.yaml` and set at minimum:

- `name` — the brand name, e.g. `Acme Plumbing`
- `site_url` — `https://acme.example/`
- `repo` — path to the website's git checkout
- `content_dir` — where markdown entries live, relative to the repo
- `geo_terms` — the markets you serve, e.g. `[orlando, "winter park"]`
- `banned_terms` — words/phrases that must never appear
- `voice_rules` — a few lines on how the brand sounds

Verify it loads:

```bash
.venv/bin/python -c "import site_config; print(site_config.load('acme')['name'])"
# → Acme Plumbing
```

Every multi-site script takes `--site acme` (or set `SEO_SITE=acme` once in
your shell and forget it). The shipped default site is `example`, which
exists so you can try every command without real data.

The full per-brand checklist — GSC service account, Bing key, cron jobs,
content workflow doc — is in `skill/references/site-onboarding.md`. Do the
YAML first; the rest can come later.

## Your first run (no credentials needed)

These three commands work with zero API keys, using the `example` site:

```bash
# 1. Generate a brief for any keyword
.venv/bin/python content_brief.py "emergency plumber" --type guide --site example

# 2. Score a draft (write one first, or point at any markdown file)
.venv/bin/python draft_score.py path/to/draft.md --site example --keyword "emergency plumber"

# 3. Advisory AI-sounding check (needs SlopTotal running; skips cleanly if not)
.venv/bin/python ai_check.py path/to/draft.md
```

## The quality gate, explained

`draft_score.py` is the heart of the repo. It scores a markdown draft 0–100:

| Area | What it checks |
|---|---|
| Readability | Flesch reading ease, sentence/paragraph length |
| On-page SEO | Keyword in title, H1, first 100 words, H2s, image alts; density 0.5–2.5% |
| Structure | Exactly one H1, sane heading hierarchy, enough length |
| Voice | AI-style tics ("delve", "tapestry", "furthermore…"), sentence variety, contractions |
| Human fingerprints | First-person experience, specific details, named places/people |
| Hygiene | Banned terms, meta title/description lengths |

**Hard failures** (score doesn't matter — the draft is blocked):

- No H1, or more than one H1
- Any banned term present

**Exit codes:** `0` = pass, `1` = blocked, `2` = usage error (bad args,
unreadable file, empty keyword).

The site's `draft_score_min` (default 80) lives in its YAML. There is an
owner-only `--min-score 0` override for emergencies — the repo's mechanical
gate never uses it.

### How to iterate a failing draft

Run the scorer, read the flagged items top to bottom, fix them, re-run.
Typical fixes:

- **Keyword density red** → you're stuffing or starving it; aim for natural
  use, roughly once per 100–200 words.
- **AI voice tics** → rewrite the flagged sentences in your own words;
  add a concrete detail only you would know.
- **Thin content** → the brief's H2 scaffolds tell you what's missing.
- **Missing H1 / hierarchy** → one `#` title, then `##` sections.

A strong real-world entry scores 87–97. If yours won't break 80, the draft
needs more substance — don't game the metric.

## The advisory check, explained

`ai_check.py` sends the draft to a **local** SlopTotal server
(`http://localhost:8000/api/quick-score`) and prints an AI-likelihood score.

- **Always exits 0.** It never blocks publishing — detectors false-positive
  on polished human writing, and we have the receipts to prove it.
- **Elevated (≥55)** → prints a human-fingerprints checklist: add a real
  name, place, or moment only you could write, then re-run.
- **Server down or text too short** → prints SKIPPED and exits 0.

Start SlopTotal with `cd sloptotal && ./start.sh`. Full setup is in
`docs/sloptotal-setup.md`.

## The weekly rhythm

| When | What |
|---|---|
| Weekly | `weekly_scan.py --site <slug>` → one target query + the exact brief command |
| After drafting | `draft_score.py` until 80+, `ai_check.py` for a second opinion |
| Publish | The site repo's own flow (`pnpm validate` etc.), which enforces the gate |
| Monthly | Competitor gaps, content decay, vitals (`psi_check.py`) |

`ops/weekly-deps-update.sh` keeps the whole machine's dependencies current
(weekly) and re-runs the test suite as proof nothing broke.

## Troubleshooting

- **`Unknown site 'x'`** → the YAML isn't in `sites/`, or `SEO_SITE` points
  at a slug with no file. `sites/` ships only `example.yaml`.
- **Tests fail after `pip install`** → a dependency moved; pin it in
  `requirements.txt` from the before-snapshot and re-run.
- **`ai_check.py` prints SKIPPED** → SlopTotal isn't running. `cd sloptotal
  && ./start.sh`, wait ~30s, retry.
- **`draft_score.py` crashes on NLTK** → run `./setup.sh` again; it fetches
  the syllable dictionary.
- **Gate blocks a good draft at 78–79** → read the yellow items; usually one
  more specific detail or a tightened intro gets it over the line. Don't
  lower the bar — fix the draft.

## Where to go next

- `skill/SKILL.md` — the full agent workflow (the weekly loop in detail)
- `skill/references/site-onboarding.md` — per-brand setup checklist
- `docs/sloptotal-setup.md` — SlopTotal deep-dive
- `ops/README.md` — machine maintenance scripts
