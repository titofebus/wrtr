#!/usr/bin/env bash
# weekly-deps-update.sh — update ALL dependencies on the whole machine.
# Runs from the weekly cron (Sundays ~6:44am ET). Prints a summary for chat.
# If the SEO toolkit tests fail after pip upgrades, the report says so
# loudly — that's the signal to pin/revert, not to skip updates.
#
# Rollback info: before/after snapshots go to
# ~/workspace/bin/.deps-update-last/ (pip freeze per venv, apt upgradable
# list). If something breaks, `pip install <pkg>==<old-version>` from the
# "before" freeze restores it.
set -u
export DEBIAN_FRONTEND=noninteractive
export PATH="$HOME/.npm-global/bin:$HOME/.deno/bin:/opt/hatch-image/bin:$PATH"

# Location of the wrtr checkout. Defaults to ~/workspace/seo-tools.
WRTR_DIR="${WRTR_DIR:-$HOME/workspace/seo-tools}"

SNAP="$WRTR_DIR/.deps-update-last"
mkdir -p "$SNAP"

say() { echo "== $*"; }

# --- apt ---
say "apt update + upgrade"
apt list --upgradable 2>/dev/null | tail -n +2 > "$SNAP/apt-upgradable-before.txt"
UPGRADABLE=$(wc -l < "$SNAP/apt-upgradable-before.txt")
echo "packages with upgrades available: $UPGRADABLE"
if apt-get update 2>&1 | grep -iE "err|fail" | head -3; then
  echo "APT_UPDATE_FAILED — see above; continuing with the rest"
else
  echo "apt update ok"
fi
if ! apt-get upgrade -y --with-new-pkgs 2>&1 | tail -2; then
  echo "APT_UPGRADE_FAILED — continuing with the rest"
fi
if [ -f /var/run/reboot-required ]; then
  echo "REBOOT REQUIRED: $(cat /var/run/reboot-required.pkgs 2>/dev/null | tr '\n' ' ')"
else
  echo "no reboot required"
fi

# --- npm globals ---
say "npm global update"
NPM_BEFORE=$(npm ls -g --depth=0 --parseable 2>/dev/null)
npm update -g 2>&1 | tail -2
NPM_AFTER=$(npm ls -g --depth=0 --parseable 2>/dev/null)
if [ "$NPM_BEFORE" = "$NPM_AFTER" ]; then
  echo "npm globals: already current"
else
  echo "npm globals changed:"
  diff <(echo "$NPM_BEFORE") <(echo "$NPM_AFTER") | grep "^[<>]" || true
fi

# --- deno ---
say "deno upgrade"
if command -v deno >/dev/null; then deno upgrade 2>&1 | tail -1; fi

# --- pip venvs ---
for VENV in "$WRTR_DIR/.venv" \
            "$WRTR_DIR/sloptotal/.venv"; do
  [ -d "$VENV" ] || continue
  TAG=$(basename "$(dirname "$VENV")")
  say "pip update: $VENV"
  "$VENV/bin/pip" install -q --upgrade pip 2>&1 | tail -1
  "$VENV/bin/pip" freeze > "$SNAP/pip-freeze-$TAG-before.txt" 2>/dev/null
  OUTDATED=$("$VENV/bin/pip" list --outdated --format=json 2>/dev/null \
    | python3 -c "import json,sys; print(' '.join(p['name'] for p in json.load(sys.stdin)))")
  if [ -n "$OUTDATED" ]; then
    echo "upgrading: $OUTDATED"
    # shellcheck disable=SC2086
    if ! "$VENV/bin/pip" install -q --upgrade $OUTDATED 2>&1 | tail -3; then
      echo "PIP_UPGRADE_FAILED for: $OUTDATED"
    fi
  else
    echo "already current"
  fi
  "$VENV/bin/pip" freeze > "$SNAP/pip-freeze-$TAG-after.txt" 2>/dev/null
  diff "$SNAP/pip-freeze-$TAG-before.txt" "$SNAP/pip-freeze-$TAG-after.txt" \
    | grep "^[<>]" || echo "(no version changes)"
done

# --- SlopTotal smoke test (its venv was just upgraded) ---
say "slopTotal smoke test"
SMOKE=$(curl -s -m 15 -X POST http://localhost:8000/api/quick-score \
  -H "Content-Type: application/json" \
  -d '{"text":"The garden was quiet that morning. I remember the light coming through the kitchen window while we waited for the coffee to brew, and thinking this was exactly the kind of ordinary moment worth keeping."}' \
  2>/dev/null)
if echo "$SMOKE" | grep -q "score"; then
  echo "SLOPTOTAL_OK"
else
  echo "SLOPTOTAL_BROKEN — attempting restart"
  (cd "$WRTR_DIR/sloptotal" && ./start.sh) 2>/dev/null
  sleep 45
  SMOKE2=$(curl -s -m 15 -X POST http://localhost:8000/api/quick-score \
    -H "Content-Type: application/json" \
    -d '{"text":"The garden was quiet that morning."}' 2>/dev/null)
  if echo "$SMOKE2" | grep -q "score"; then
    echo "SLOPTOTAL_RESTARTED_OK"
  else
    echo "SLOPTOTAL_STILL_DOWN — ai_check.py will print SKIPPED until it's restarted (see sloptotal/SETUP.md)"
  fi
fi

# --- verify: SEO toolkit tests must still pass ---
say "post-update verification"
cd "$WRTR_DIR" || exit 1
.venv/bin/python -m unittest discover -s tests 2>&1 | tail -3

say "done — snapshots in $SNAP"
