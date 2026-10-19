---
name: verify
description: How to check a wrtr change before pushing. Use after editing any wrtr script, check, site config or test, and before every push.
---

# Verify a wrtr change

wrtr is public and other repos (trygloam's content gate) run it, so every
push must leave the suite green.

## One-time setup

```bash
./setup.sh                 # creates .venv, installs pinned deps, textstat dictionary, SlopTotal
```

All commands run through the venv: `.venv/bin/python`.

## Every change

```bash
.venv/bin/python -m unittest discover -s tests   # full suite, must all pass
```

Tests are pure-function and offline: no network, no credentials, tmp files
only. A new check or brief section gets a test in `tests/test_seo_tools.py`
in the same change (see AGENTS.md section 10).

## Changes to the quality gate (`draft_score.py`) or a site config

Score a real draft before and after the change and compare:

```bash
.venv/bin/python draft_score.py <draft.md> --site <slug> --keyword "<kw>"
```

Exit codes: 0 = PASS, 1 = blocked, anything else = tool error (AGENTS.md
section 5). For Gloam, the draft is a trygloam `content/blog/*.md` post and
the site is `gloam` (its config lives in trygloam `seo/gloam.yaml`, linked
into `sites/`). From the trygloam checkout, `npm run gate:content` runs the
same gate over every post.

## Done means

The unit suite passes, any gate change was scored on a real draft, and the
reply says which checks ran and which were not run.
