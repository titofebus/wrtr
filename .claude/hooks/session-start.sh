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
