#!/bin/bash
# Cloud sessions only: install the language server the pyright-lsp plugin
# (enabled in .claude/settings.json) spawns from PATH, in case the cloud image
# does not ship it; ~/.local/bin is on the Claude process PATH. Idempotent.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

if ! command -v pyright-langserver >/dev/null 2>&1; then
  npm install -g --prefix "$HOME/.local" pyright >/dev/null
fi

# The pre-push hook (.githooks/pre-push) runs the suite through .venv, so
# cloud pushes get the same check as local ones instead of skipping it.
cd "$CLAUDE_PROJECT_DIR"
git config core.hooksPath .githooks
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
