# SlopTotal — local AI-text detection setup (wrtr)

Self-hosted AI-text detection ("VirusTotal for AI slop"), used by
`../ai_check.py` as an **advisory-only** pre-publish check. MIT licensed.

> `sloptotal/` itself is gitignored (models + venv are local-only), so this
> tracked guide is the canonical setup doc. `setup.sh` clones it for you.

## Quick setup

```bash
cd ~/workspace/seo-tools
./setup.sh              # clones SlopTotal at the pinned commit, builds its venv
cd sloptotal
./start.sh              # detached; logs to /tmp/sloptotal.log
curl -s http://localhost:8000/   # 200 when up (~30s: classifiers preload)
```

To stop: `pkill -f "sloptotal/.venv/bin/python"`.

## Details

- **Pinned commit:** `8b69796d7060278d8ecda8770e71888cf59a23fa`
  (latest upstream as of 2026-10-07)
- **Repo:** https://github.com/pablocaeg/sloptotal (cloned, not a submodule)
- **Venv:** `./.venv` (dedicated; Python 3.12) — `pip install -r requirements.txt`
- **Models:** ~3.1 GB in `~/.cache/huggingface/hub` (classifiers for
  `/api/quick-score`; downloaded once, cached)
- **Hardware:** CPU-only. 4 GB RAM is enough for the lite profile.
- **Persistence:** the weekly dependency-update script smoke-tests the API
  and auto-restarts it via `start.sh` if it's down. If the VM was just
  replaced, run `./start.sh` manually — `ai_check.py` prints SKIPPED
  (exit 0) until the server is back.

## API (used by ai_check.py)

- `POST /api/quick-score` — `{"text": "..."}` (min 50 chars) → ML
  classifiers + heuristics, calibrated 0–100 score, `verdict` clean/mixed/ai.
  ~1–3 s on CPU once warm; ~30 s for a full ~1300-word draft on modest CPUs
  (the server chunks long text). This is the endpoint the toolkit uses.
- `POST /api/paragraph-score` — same input → per-paragraph heat map
  (`paragraphs[]` with score/verdict/text, plus `overall_score`).
- `POST /api/analyze` — full 23-engine analysis (slower; not used by the toolkit).

## Local patches (documented, minimal)

1. **`app/main.py` `_preload_models()`** — trimmed to the quick-score
   classifiers. Preloading all 23 engines stalls startup 30+ min on slow
   networks and starves the event loop; the rest lazy-load on demand.
2. **Proxy quirk:** a stock `no_proxy` containing bracketed IPv6 literals
   (`[::1]`) crashes httpx inside `huggingface_hub`
   (`InvalidURL: Invalid port: ':1]'`), breaking model downloads.
   `start.sh` exports a cleaned `no_proxy` without brackets.

## Notes

- Scores are advisory, never a publish gate: detectors false-positive on
  polished human prose. See `../ai_check.py`.
- `ai_check.py` uses a 120 s timeout — full drafts are slow on small CPUs.
