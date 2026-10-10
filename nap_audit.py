"""nap_audit.py - canonical NAP consistency audit for a site.

The local SEO playbook's first rule: one canonical business identity, and
every public surface must match it exactly. This tool checks the site's
published identity (homepage + contact page HTML, JSON-LD business nodes)
against the canonical `local_seo:` block in sites/<slug>.yaml (nap, service
areas, address visibility) and reports field-by-field mismatches.

Companion to local_schema_check.py: that tool checks one page's JSON-LD
against the config (CI-friendly, exits 1 on red); this one crawls the
site's visible pages for NAP consistency (audit, always exits 0).

Usage: .venv/bin/python nap_audit.py --site <slug>
Exit code is always 0 - this is an audit, not a gate.
"""

import argparse
import html as html_mod
import json
import re
import sys
import urllib.request

import site_config

PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"
)
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)
CONTACT_HREF_RE = re.compile(
    r'href="((?:https?://[^"]*)?/contact/?)"', re.IGNORECASE
)
STREET_RE = re.compile(
    r"\d{1,5}\s+[A-Z][a-zA-Z.'\- ]+\s+"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|"
    r"Way|Court|Ct|Circle|Cir|Parkway|Pkwy|Trail|Plaza)",
)

BUSINESS_TYPES = {
    "LocalBusiness", "ProfessionalService", "Organization",
    "Store", "Restaurant", "MedicalBusiness",
}


def normalize_phone(raw):
    """Return the last 10 digits of a phone-like string, or ''."""
    digits = re.sub(r"\D", "", raw or "")
    return digits[-10:] if len(digits) >= 10 else ""


def extract_phones(html_text):
    """Find phone-like strings in HTML, normalized to 10 digits."""
    return {normalize_phone(m) for m in PHONE_RE.findall(html_text or "")} - {""}


def extract_emails(html_text):
    """Find email addresses in HTML, lowercased."""
    return {m.lower() for m in EMAIL_RE.findall(html_text or "")}


def extract_jsonld(html_text):
    """Parse all JSON-LD script blocks; return a list of dicts."""
    docs = []
    for m in re.finditer(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
        html_text or "", re.DOTALL | re.IGNORECASE):
        try:
            docs.append(json.loads(html_mod.unescape(m.group(1))))
        except (json.JSONDecodeError, ValueError):
            continue
    return docs


def business_nodes(doc):
    """Yield schema nodes that describe the business itself."""
    if isinstance(doc, dict) and "@graph" in doc:
        candidates = doc["@graph"]
    elif isinstance(doc, dict):
        candidates = [doc]
    elif isinstance(doc, list):
        candidates = doc
    else:
        return
    for node in candidates:
        if not isinstance(node, dict):
            continue
        types = node.get("@type", [])
        types = [types] if isinstance(types, str) else types
        if BUSINESS_TYPES.intersection(types):
            yield node


def node_field(node, *names):
    """First present value among candidate field names, as a string."""
    for name in names:
        value = node.get(name)
        if isinstance(value, dict):
            value = value.get("name") or value.get("@id")
        if value:
            return str(value)
    return ""


def fetch(url):
    """Fetch a URL; return text or '' on any failure."""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "wrtr-nap-audit/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except Exception:
        return ""


def audit_nap(cfg, pages):
    """Compare canonical NAP against fetched pages.

    cfg: site config dict. pages: {label: html}.
    Returns a list of (field, status, detail); status in ok/warn.
    """
    ls = cfg.get("local_seo") or {}
    nap = ls.get("nap") or {}
    out = []
    canonical_name = (nap.get("name") or cfg.get("name") or "").strip().lower()
    canonical_phone = normalize_phone(nap.get("phone", ""))
    canonical_email = (nap.get("email", "") or "").lower()
    address_hidden = site_config.hides_address(cfg)

    combined = "\n".join(pages.values())
    phones = set()
    emails = set()
    for text in pages.values():
        phones |= extract_phones(text)
        emails |= extract_emails(text)
    nodes = []
    for text in pages.values():
        for doc in extract_jsonld(text):
            nodes.extend(business_nodes(doc))

    # Business name in structured data
    node_names = {node_field(n, "name").lower() for n in nodes} - {""}
    if canonical_name and canonical_name in node_names:
        out.append(("business name (JSON-LD)", "ok",
                    f'"{cfg["name"]}" present in structured data'))
    elif canonical_name and nodes:
        out.append(("business name (JSON-LD)", "warn",
                    "business node exists but name does not match "
                    f'"{cfg.get("name")}"'))
    else:
        out.append(("business name (JSON-LD)", "warn",
                    "no LocalBusiness/Organization node found in JSON-LD"))

    # Phone consistency
    if canonical_phone:
        if canonical_phone in phones:
            out.append(("phone", "ok",
                        f"canonical phone present ({len(phones)} "
                        "distinct number(s) sitewide)"))
        else:
            out.append(("phone", "warn",
                        "canonical phone NOT found in site HTML; found: "
                        + (", ".join(sorted(phones)) or "none")))
        if len(phones - {canonical_phone}) > 0:
            out.append(("phone (extra numbers)", "warn",
                        "other numbers published: "
                        + ", ".join(sorted(phones - {canonical_phone}))))
    elif phones:
        out.append(("phone", "warn",
                    "phone(s) published but no canonical phone in YAML: "
                    + ", ".join(sorted(phones))))

    # Email consistency
    if canonical_email:
        if canonical_email in emails:
            out.append(("email", "ok", "canonical email present sitewide"))
        else:
            out.append(("email", "warn",
                        "canonical email NOT found in site HTML"))
    elif emails:
        out.append(("email", "warn",
                    "email(s) published but no canonical email in YAML"))

    # Address: a hidden-address business must not publish a street address.
    street_hits = {m.group(0) for m in STREET_RE.finditer(combined)}
    if address_hidden and street_hits:
        out.append(("address (hidden)", "warn",
                    "address is marked hidden but street-like text found: "
                    + "; ".join(sorted(street_hits)[:3])))
    elif address_hidden:
        out.append(("address (hidden)", "ok",
                    "no street address published, as configured"))

    # LocalBusiness schema presence
    lb_types = set()
    for n in nodes:
        types = n.get("@type", [])
        types = [types] if isinstance(types, str) else types
        lb_types.update(t for t in types if t != "Organization")
    if lb_types:
        out.append(("LocalBusiness schema", "ok",
                    "found: " + ", ".join(sorted(lb_types))))
    else:
        out.append(("LocalBusiness schema", "warn",
                    "no LocalBusiness/ProfessionalService node; "
                    "add one for local eligibility signals"))

    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Audit a site's published NAP against its canonical record.")
    parser.add_argument("--site", default=None)
    args = parser.parse_args(argv)
    cfg = site_config.load(args.site)
    base = (cfg.get("site_url") or "").rstrip("/")
    if not base:
        print("no site_url in config", file=sys.stderr)
        return 2

    pages = {"homepage": fetch(base + "/")}
    if not pages["homepage"]:
        print(f"could not fetch {base}/", file=sys.stderr)
        return 2
    m = CONTACT_HREF_RE.search(pages["homepage"])
    contact_url = None
    if m:
        href = m.group(1)
        contact_url = href if href.startswith("http") else base + href
    else:
        contact_url = base + "/contact/"
    contact_html = fetch(contact_url)
    if contact_html:
        pages["contact"] = contact_html

    ls = cfg.get("local_seo") or {}
    nap = ls.get("nap") or {}
    print(f"NAP audit - {cfg.get('name')} ({base})")
    print(f"canonical: phone={nap.get('phone') or '-'} "
          f"email={nap.get('email') or '-'} "
          f"address={'hidden' if site_config.hides_address(cfg) else 'shown'}")
    print()
    results = audit_nap(cfg, pages)
    warns = 0
    for field, status, detail in results:
        tag = "ok" if status == "ok" else "WARN"
        if status != "ok":
            warns += 1
        print(f"[{tag}] {field}: {detail}")
    print()
    print(f"SUMMARY: {len(results) - warns}/{len(results)} checks ok"
          + ("" if warns == 0 else f" - {warns} need attention"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
