# ops/

Machine-operations scripts for a wrtr install.

## weekly-deps-update.sh

Updates ALL dependencies on the machine, weekly: apt packages, npm global
packages, deno, and pip in both venvs (`.venv` and `sloptotal/.venv`), then
re-runs the test suite as post-update verification.

```bash
WRTR_DIR=/path/to/wrtr ./ops/weekly-deps-update.sh
```

`WRTR_DIR` defaults to `~/workspace/seo-tools`. Before/after snapshots
(`pip freeze`, apt upgradable list) go to `$WRTR_DIR/.deps-update-last/`
for pin/revert. The script prints explicit `APT_UPDATE_FAILED`,
`REBOOT REQUIRED`, and `SLOPTOTAL_BROKEN` signals — a report that says
"all current" when apt failed is a bug; the script is written not to do that.
