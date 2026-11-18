"""Skills stay evergreen: rules and run-time lookups, never snapshots.

A skill is a procedure every future run follows. A tracker issue id, a PR
number, a calendar date, a commit hash or an "open items" list is true for a
few days and then steers later runs at stale work. Point-in-time facts belong
in the tracker, a dated report file, or git log. The same check runs in gloam
(`skill-evergreen` gate) and trygloam (`tests/skill-evergreen.test.ts`).
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("skill", ".claude/skills", ".claude/agents")
SCAN_SUFFIXES = {".md", ".yaml", ".yml"}

MONTHS = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?"
    r"|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
STANDARD_ID_PREFIXES = {
    "AES", "CVE", "ES", "HS", "ISO", "PS", "RFC", "RS", "SHA", "UTF", "WCAG",
}

SNAPSHOT_PATTERNS = (
    ("tracker issue id", re.compile(r"\b([A-Z][A-Z0-9]{1,5})-\d{2,}\b"),
     lambda m: m.group(1) not in STANDARD_ID_PREFIXES),
    ("pull request or issue number",
     re.compile(r"\b(?:PR|pull request|issue)\s+#\d+\b", re.I), None),
    ("calendar date", re.compile(r"\b20\d{2}-[01]\d-[0-3]\d\b"), None),
    ("calendar date",
     re.compile(rf"\b{MONTHS}\.? (?:[0-3]?\d(?:st|nd|rd|th)?\b|20\d{{2}}\b)"),
     None),
    ("commit hash",
     re.compile(r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b"), None),
    ("point-in-time status",
     re.compile(r"\b(?:known open items|currently open|open items:"
                r"|as of (?:today|now|this (?:week|month))"
                r"|remaining (?:bugs|issues|findings):)", re.I), None),
)


def snapshot_lines(source):
    hits = []
    for number, line in enumerate(source.split("\n"), start=1):
        for label, pattern, keep in SNAPSHOT_PATTERNS:
            if any(keep is None or keep(m) for m in pattern.finditer(line)):
                hits.append(f"{number} [{label}] {line.strip()}")
                break
    return hits


def skill_files():
    for scan_dir in SCAN_DIRS:
        base = ROOT / scan_dir
        if base.is_dir():
            yield from (p for p in sorted(base.rglob("*"))
                        if p.is_file() and p.suffix in SCAN_SUFFIXES)


class TestSkillEvergreen(unittest.TestCase):
    def test_skills_hold_no_snapshots(self):
        files = list(skill_files())
        self.assertTrue(files, "expected at least one skill file to scan")
        violations = [
            f"{path.relative_to(ROOT)}:{hit}"
            for path in files
            for hit in snapshot_lines(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(violations, [])

    def test_fires_on_each_stale_shape(self):
        for line in (
            "Ignore the legacy issues BCK-251 and BCK-253.",
            "The owner switched to auto-publish on Oct 13, 2026.",
            "Findings from the 2026-11-18 end-to-end test.",
            "The fix landed in ab03edf5.",
            "See PR #482 for the details.",
            "Known open items: the retry sweep fails.",
        ):
            self.assertEqual(len(snapshot_lines(line)), 1, line)

    def test_passes_rules_placeholders_and_standards(self):
        evergreen = "\n".join((
            "Only issues labeled Bug are in scope; list them live.",
            "Write the report to `reviews/audit-YYYY-MM-DD/`.",
            "Name the issue BCK-<number> in the commit message.",
            "Hash tokens with SHA-256 and encode them as UTF-8.",
            "Report what's still open and why.",
        ))
        self.assertEqual(snapshot_lines(evergreen), [])


if __name__ == "__main__":
    unittest.main()
