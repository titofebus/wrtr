/**
 * The four-part wiring behind every page_checks finding, tested for real.
 *
 * A finding is silently useless unless all of these line up:
 *   1. sevOf            gives it a severity, or it defaults to info
 *   2. normalize        collapses a counted issue to one summary card
 *   3. matchesCategory  selects the pages that card stands for
 *   4. titleMap         gives the drill-in a heading
 *
 * The functions are lifted out of static/script.js and run here, so this fails
 * if the wiring drifts from the strings page_checks.py actually emits.
 *
 *     node test_ui_wiring.js
 */
const fs = require("fs");
const path = require("path");

const SRC = fs.readFileSync(path.join(__dirname, "static", "script.js"), "utf8");

// issue string, expected severity, expected summary slug
const CASES = [
  ["Lorem ipsum placeholder text in the page copy", "error", "Lorem ipsum placeholder text in the page copy"],
  ["2 link(s) to a local or staging host (localhost, staging.example.com)", "error", "local staging links"],
  ["1 form(s) submit over HTTP (browsers warn the visitor)", "error", "insecure forms"],
  ["No <head> element (head tags land in the body)", "error", "No <head> element"],
  ["Canonical points to a non-200 URL (HTTP 404)", "error", "Canonical points to a non-200 URL"],
  ["Canonical points to a non-indexable URL", "error", "Canonical points to a non-indexable URL"],
  ["Canonical contains a fragment (Google drops everything after the #)", "warn", "Canonical contains a fragment"],
  ["Canonical points to a URL that redirects", "warn", "Canonical points to a URL that redirects"],
  ["No <body> element", "warn", "No <body> element"],
  ["HTML document over 2MB (3.1MB)", "warn", "HTML document over 2MB"],
  ["No internal outlinks (dead end for crawling and link equity)", "warn", "No internal outlinks"],
  ["Inbound internal links come only from non-indexable pages (no link equity reaches it)", "warn",
   "Inbound internal links come only from non-indexable pages"],
  ["3 pagination URL(s) declared by rel but not linked in an anchor tag (crawlers cannot follow them)",
   "warn", "pagination not linked"],
  ["2 hreflang alternate(s) do not link back (https://example.com/fr/)", "warn", "hreflang no return"],
  ["4 image(s) with no width or height (causes layout shift)", "info", "image dimensions"],
  ["URL: uppercase", "warn", "URL:"],
  ["URL: internal search result page", "warn", "URL:"],
];

function grab(header, endNeedle) {
  const start = SRC.indexOf(header);
  if (start < 0) throw new Error("not found in script.js: " + header);
  const end = SRC.indexOf(endNeedle, start);
  if (end < 0) throw new Error("end not found for " + header);
  return SRC.slice(start, end + endNeedle.length);
}

const errRe = grab("const _PAGE_CHECK_ERR_RE", ";\n");
const warnRe = grab("const _PAGE_CHECK_WARN_RE", ";\n");
const sevOf = new Function(errRe + warnRe + grab("function sevOf(issue)", "\n}\n") + "\nreturn sevOf;")();
const matchesCategory = new Function(
  errRe + warnRe + grab("function matchesCategory(page, cat)", "\n}\n") + "\nreturn matchesCategory;")();

// Both normalisers must carry every rule, or the two panels disagree.
const normalizers = [];
for (let i = 0, at = 0; (at = SRC.indexOf("  const normalize = (issue) => {", at)) >= 0; i++) {
  const end = SRC.indexOf("\n  };\n", at);
  normalizers.push(new Function(
    SRC.slice(at, end + 6).replace("  const normalize", "const normalize") + "\nreturn normalize;")());
  at = end;
}

let passed = 0;
const failures = [];
const check = (name, cond) => { cond ? passed++ : failures.push(name); };

check("both summary panels have a normalize map", normalizers.length >= 2);

for (const [issue, severity, slug] of CASES) {
  check(`sevOf("${issue.slice(0, 46)}") is ${severity}`, sevOf(issue) === severity);
  normalizers.forEach((normalize, n) => {
    const [label, got] = normalize(issue);
    check(`normalize #${n} groups "${issue.slice(0, 40)}" as ${slug}`, got === slug);
    check(`normalize #${n} gives "${slug}" a label`, !!label);
  });
  const page = { url: "https://example.com/x", issues: [issue], status_code: 200, depth: 1 };
  const unrelated = { url: "https://example.com/y", issues: ["Missing title"], status_code: 200, depth: 1 };
  check(`"${slug}" selects the page its issue is on`, matchesCategory(page, slug) === true);
  check(`"${slug}" leaves an unrelated page out`, matchesCategory(unrelated, slug) !== true);
}

// Counted issues differ per page. They must still land in one card.
const a = normalizers[0]("2 link(s) to a local or staging host (localhost)")[1];
const b = normalizers[0]("7 link(s) to a local or staging host (10.0.0.5)")[1];
check("a counted issue is one card whatever the count", a === b);

// Every slug needs a drill-in heading.
for (const [, , slug] of CASES) {
  check(`titleMap has a heading for "${slug}"`, SRC.includes(`'${slug}':`) || slug === "URL:");
}

if (failures.length) {
  failures.forEach((f) => console.log("FAIL: " + f));
  console.log(`${passed}/${passed + failures.length} UI wiring checks passed`);
  process.exit(1);
}
console.log(`${passed}/${passed} UI wiring checks passed`);
