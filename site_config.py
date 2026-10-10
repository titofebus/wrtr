"""Per-site configuration for the SEO toolkit.

Each brand/site gets a YAML file in <wrtr>/sites/<slug>.yaml.
Scripts accept --site <slug> (or the SEO_SITE env var); default is example.

This is what makes the whole engine reusable across brands: adding a new
site is copying the template config, filling in its URLs/voice/rules, and
pointing the scripts at it. No code changes.
"""
import os

import yaml

SITES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sites")
DEFAULT_SITE = "example"

REQUIRED_KEYS = ["name", "site_url", "repo", "content_dir"]

# Generic fallback mapping for brands that omit type_category_map.
# Deliberately brand-neutral — a default must never silently impose one
# brand's taxonomy (e.g. wedding types) on another.
DEFAULT_TYPE_CATEGORY_MAP = {
    "guide": "guides",
    "story": "stories",
    "tip": "tips",
}


def load(slug=None):
    import re
    slug = slug or os.environ.get("SEO_SITE") or DEFAULT_SITE
    if not re.fullmatch(r"[a-z0-9_-]+", slug):
        raise SystemExit(f"Invalid site slug '{slug}': use lowercase "
                         f"letters, digits, '-' or '_'.")
    path = os.path.join(SITES_DIR, f"{slug}.yaml")
    if not os.path.isdir(SITES_DIR):
        raise SystemExit(f"No sites directory at {SITES_DIR}.")
    if os.path.isdir(path):
        raise SystemExit(f"Site config '{slug}' is a directory, not a file: "
                         f"{path}")
    if not os.path.isfile(path):
        known = sorted(f[:-5] for f in os.listdir(SITES_DIR) if f.endswith(".yaml"))
        raise SystemExit(f"Unknown site '{slug}'. Known sites: {', '.join(known)}")
    try:
        with open(path) as f:
            cfg = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise SystemExit(f"Site config '{slug}' is not valid YAML: {e}")
    if not isinstance(cfg, dict):
        raise SystemExit(f"Site config '{slug}' is empty or not a key: value mapping.")
    missing = [k for k in REQUIRED_KEYS if not cfg.get(k)]
    if missing:
        raise SystemExit(
            f"Site config '{slug}' is missing required keys: {', '.join(missing)}")
    cfg["slug"] = slug
    # gsc_property defaults to site_url so scan and brief can never diverge
    # onto different properties by accident.
    cfg.setdefault("gsc_property", cfg["site_url"])
    cfg.setdefault("type_category_map", DEFAULT_TYPE_CATEGORY_MAP)
    errs = validate_local_seo(cfg.get("local_seo"))
    if errs:
        raise SystemExit(f"Site config '{slug}' local_seo: " + "; ".join(errs))
    return cfg


OPERATING_MODELS = ("storefront", "service_area", "hybrid")
MAX_SERVICE_AREAS = 20  # Google Business Profile limit


def validate_local_seo(ls):
    """Validate the optional local_seo block (Central Florida local SEO
    playbook, skill/references/local-seo-playbook.md). Returns error strings."""
    if ls is None:
        return []
    if not isinstance(ls, dict):
        return ["must be a mapping"]
    errs = []
    model = ls.get("operating_model")
    if model not in OPERATING_MODELS:
        errs.append(f"operating_model must be one of {', '.join(OPERATING_MODELS)}")
    areas = ls.get("service_areas", []) or []
    if not isinstance(areas, list):
        errs.append("service_areas must be a list")
    else:
        if len(areas) > MAX_SERVICE_AREAS:
            errs.append(f"{len(areas)} service_areas; GBP allows at most {MAX_SERVICE_AREAS}")
        if len({str(a).lower() for a in areas}) != len(areas):
            errs.append("service_areas has duplicates")
    if model == "service_area":
        if ls.get("hide_address") is False:
            errs.append("a service-area business must hide its address (hide_address: true)")
        if not areas:
            errs.append("a service-area business needs at least one service area")
    if model in ("storefront", "hybrid") and ls.get("hide_address"):
        errs.append(f"a {model} shows its staffed address (hide_address: false)")
    nap = ls.get("nap", {}) or {}
    if not isinstance(nap, dict):
        errs.append("nap must be a mapping")
    utm = ls.get("gbp_utm", "")
    if utm and "utm_source" not in str(utm):
        errs.append("gbp_utm should contain utm_source (e.g. ?utm_source=google&utm_medium=organic&utm_campaign=gbp)")
    return errs


def hides_address(cfg):
    ls = cfg.get("local_seo") or {}
    return ls.get("operating_model") == "service_area" or bool(ls.get("hide_address"))


def list_sites():
    return sorted(f[:-5] for f in os.listdir(SITES_DIR) if f.endswith(".yaml"))


# Niche-generic words: too common within a service niche to identify a topic.
# Shared by hub detection (weekly_scan._HUB_GENERIC) and brief anchor
# scoring (content_brief.GENERIC_WORDS) so the two never drift apart.
NICHE_GENERIC_WORDS = {"wedding", "weddings", "venue", "venues",
                       "photographer", "photographers", "photography",
                       "photo", "photos", "video", "videographer",
                       "videography", "planning", "planner", "guide",
                       "guides", "tips", "ideas"}


def need_dict(cfg, key, default=None):
    """cfg[key] as a dict, or a clean SystemExit naming the offender."""
    v = cfg.get(key, default if default is not None else {})
    if not isinstance(v, dict):
        raise SystemExit(f"Site config error: '{key}' must be a mapping, "
                         f"got {type(v).__name__} (site '{cfg.get('slug')}').")
    return v


def need_list(cfg, key, non_empty=False, default=None):
    """cfg[key] as a list, or a clean SystemExit naming the offender."""
    v = cfg.get(key, default if default is not None else [])
    if not isinstance(v, list) or (non_empty and not v):
        need = "a non-empty list" if non_empty else "a list"
        raise SystemExit(f"Site config error: '{key}' must be {need}, "
                         f"got {type(v).__name__} (site '{cfg.get('slug')}').")
    return v


def need_str(cfg, key, non_empty=False, default=""):
    """cfg[key] as a string, or a clean SystemExit naming the offender."""
    v = cfg.get(key, default)
    if not isinstance(v, str) or (non_empty and not v.strip()):
        need = "a non-empty string" if non_empty else "a string"
        raise SystemExit(f"Site config error: '{key}' must be {need}, "
                         f"got {type(v).__name__} (site '{cfg.get('slug')}').")
    return v


def need_number_mapping(cfg, key):
    """cfg[key] as a {str: number} mapping, or a clean SystemExit."""
    th = need_dict(cfg, key)
    for k, v in th.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise SystemExit(f"Site config error: '{key}.{k}' must be a "
                             f"number, got {v!r} (site '{cfg.get('slug')}').")
    return th
