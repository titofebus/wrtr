#!/usr/bin/env bash
# setup.sh - one-command wrtr install.
# Creates .venv, installs pinned deps, fetches textstat's syllable dictionary,
# and clones SlopTotal (pinned commit) for the advisory AI check.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# pip stages wheels in $TMPDIR - /tmp is a tiny tmpfs on some machines.
export TMPDIR="$HERE/.tmp"
mkdir -p "$TMPDIR"
trap 'rm -rf "$TMPDIR"' EXIT

echo "== python"
if ! command -v python3 >/dev/null; then
  echo "setup.sh: python3 not found - install Python 3.10+ first." >&2
  exit 1
fi
python3 --version

echo "== venv"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip || {
  echo "setup.sh: pip upgrade failed - aborting." >&2; exit 1; }
.venv/bin/pip install -q -r requirements.txt || {
  echo "setup.sh: dependency install failed - aborting. Check disk space and network." >&2; exit 1; }
echo "dependencies installed"

echo "== textstat syllable dictionary"
if [ ! -f "$HOME/nltk_data/corpora/cmudict/cmudict" ]; then
  mkdir -p "$HOME/nltk_data/corpora" /tmp
  curl -sL -o /tmp/cmudict.zip \
    https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/cmudict.zip
  unzip -o -q /tmp/cmudict.zip -d "$HOME/nltk_data/corpora"
  rm -f /tmp/cmudict.zip
  echo "cmudict installed to ~/nltk_data"
else
  echo "cmudict already present"
fi

echo "== SlopTotal (advisory AI check, optional)"
if [ ! -d sloptotal ]; then
  # Pinned to the commit verified 2026-10-07; update deliberately, not blindly.
  git clone -q https://github.com/pablocaeg/sloptotal sloptotal
  (cd sloptotal && git checkout -q 8b69796d7060278d8ecda8770e71888cf59a23fa || true)
  if [ -f sloptotal/requirements.txt ]; then
    python3 -m venv sloptotal/.venv
    sloptotal/.venv/bin/pip install -q --upgrade pip
    sloptotal/.venv/bin/pip install -q -r sloptotal/requirements.txt
  fi
  echo "SlopTotal cloned - see docs/sloptotal-setup.md to start the API"
else
  echo "sloptotal/ already present"
fi

echo "== tests"
.venv/bin/python -m unittest discover -s tests 2>&1 | tail -2

cat <<'NEXT'

Done. Next steps (per brand):
  1. cp skill/references/site-config-template.yaml sites/<slug>.yaml  # fill it in
  2. .venv/bin/python -c "import site_config; print(site_config.load('<slug>')['name'])"
  3. Add API keys as needed (all gitignored, 0600):
       .sa-key.json    Google service-account key (Search Console)
       .psi-key        PageSpeed + CrUX restricted key
       .bing-key       Bing Webmaster API key
  4. .venv/bin/python weekly_scan.py --site <slug>

See skill/SKILL.md for the full agent workflow.
NEXT
