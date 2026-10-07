# ops/

Machine-operations scripts for a wrtr install.

## weekly-deps-update.sh

Updates ALL dependencies on the machine, weekly: apt packages, npm global
packages, deno, and pip in both venvs (`.venv` and `sloptotal/.venv`), then
re-runs the test suite as post-update verification. Also smoke-tests the
local SlopTotal API and auto-restarts it via `sloptotal/start.sh` if down.

```bash
WRTR_DIR=/path/to/wrtr ./ops/weekly-deps-update.sh
```

`WRTR_DIR` defaults to `~/workspace/seo-tools`. Before/after snapshots
(`pip freeze`, apt upgradable list) go to `$WRTR_DIR/.deps-update-last/`
for pin/revert. The script prints explicit `APT_UPDATE_FAILED`,
`REBOOT REQUIRED`, and `SLOPTOTAL_BROKEN`/`SLOPTOTAL_STILL_DOWN` signals —
a report that says "all current" when apt failed is a bug; the script is
written not to do that.

> **Two copies:** this portable script is the packaged version. The machine
> it was built on runs a local copy at `~/workspace/bin/weekly-deps-update.sh`
> with the same coverage but hardcoded paths (`~/workspace/seo-tools`,
> snapshots in `~/workspace/bin/.deps-update-last/`). They are maintained in
> parallel — when you change one, port the change to the other.
