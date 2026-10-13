#!/usr/bin/env python3
"""Assign real, never-duplicated images to a new entry.

Scans the site's image library and all existing entries, then picks the
most topic-relevant images that haven't been used yet. Stateless: usage is
derived from entry frontmatter (`image:`) and markdown image references,
so there's no state file to lose.

Usage:
    .venv/bin/python assign_images.py --site example \\
        --topic "austin bike tours" --count 3

Prints the assigned image paths (site-relative URLs) plus suggested alt
text derived from the keyword-rich filenames. The agent writes the first
as the entry's `image:` frontmatter and the rest as inline images.

When every library image has been used, the pool resets (all images become
eligible again) and the output says so.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import site_config

IMG_EXTS = (".webp", ".jpg", ".jpeg", ".png", ".avif")
# Universal filler only. The site's own ubiquitous terms (its niche
# words and geo terms) are merged in from the site config at runtime -
# they are what make topic words too common to be distinctive THERE.
BASE_STOPWORDS = {"the", "a", "an", "and", "of", "in", "for", "with", "to"}


def stopwords_for(cfg):
    """Topic-matching stopwords for a site: universal filler + the
    site's generic words + the words of its geo terms."""
    words = set(BASE_STOPWORDS) | site_config.generic_words(cfg)
    for g in cfg.get("geo_terms", []) or []:
        words |= set(re.findall(r"[a-z]+", str(g).lower()))
    return words


def library_images(lib_dir):
    out = []
    for root, _dirs, files in os.walk(lib_dir):
        for f in sorted(files):
            if f.lower().endswith(IMG_EXTS):
                out.append(os.path.join(root, f))
    return out


def used_images(repo, content_dirs, cfg=None):
    """Filenames (basenames) already referenced anywhere on the site.

    Site-specific reference schemes are config-driven: `image_scan_dirs`
    lists extra repo dirs to scan (e.g. a data/components tree),
    `image_number_map` is a repo-relative JSON file mapping numbers to
    filenames, and `image_number_pattern` is the regex (one capture
    group: the number) that references an image by number in source
    files. All optional; unset means plain markdown/frontmatter refs.
    """
    cfg = cfg or {}
    used = set()
    img_ref = re.compile(r"[\"'\(](/[^\"'\)]*?\.(?:webp|jpg|jpeg|png|avif))", re.I)
    num_ref = None
    num_to_file = {}
    map_rel = cfg.get("image_number_map")
    pattern = cfg.get("image_number_pattern")
    if map_rel and pattern:
        num_ref = re.compile(pattern)
        try:
            import json
            with open(os.path.join(repo, map_rel), encoding="utf-8") as f:
                num_to_file = json.load(f)
        except (OSError, ValueError):
            pass
    skip_files = set(cfg.get("image_scan_skip_files", []) or [])
    if map_rel:
        skip_files.add(os.path.basename(map_rel))
    # Scan content collections (frontmatter + markdown references).
    scan_dirs = [os.path.join(repo, d) for d in content_dirs
                 if os.path.isdir(os.path.join(repo, d))]
    # Plus any site-configured extra trees (data/components and the like) -
    # images referenced there count as used too.
    for extra in cfg.get("image_scan_dirs", []) or []:
        full = os.path.join(repo, extra)
        if os.path.isdir(full):
            scan_dirs.append(full)
    for scan in scan_dirs:
        for root, _dirs, files in os.walk(scan):
            for f in files:
                if not f.endswith((".md", ".ts", ".astro", ".tsx")):
                    continue
                if f in skip_files:
                    continue
                try:
                    text = open(os.path.join(root, f), encoding="utf-8").read()
                except (OSError, UnicodeDecodeError):
                    continue
                for m in img_ref.finditer(text):
                    used.add(os.path.basename(m.group(1)))
                if num_ref is not None:
                    for m in num_ref.finditer(text):
                        fn = num_to_file.get(m.group(1))
                        if fn:
                            used.add(os.path.basename(fn))
    return used


def topic_words(topic, stopwords=None):
    stops = stopwords if stopwords is not None else BASE_STOPWORDS
    return {w for w in re.findall(r"[a-z]+", topic.lower())
            if w not in stops and len(w) > 2}


def relevance(path, words):
    name = os.path.basename(path).lower().replace("-", " ").replace("_", " ")
    return sum(1 for w in words if w in name)


def main():
    ap = argparse.ArgumentParser(description="Assign unused library images.")
    ap.add_argument("--site", default=None, help="site slug (default: example)")
    ap.add_argument("--topic", required=True, help="entry topic/keyword")
    ap.add_argument("--count", type=int, default=3, help="images to assign")
    args = ap.parse_args()

    cfg = site_config.load(args.site)
    repo = os.path.expanduser(cfg["repo"])
    lib = os.path.join(repo, cfg.get("image_library", "public/images/"))
    if not os.path.isdir(lib):
        print(f"assign_images: image library not found: {lib}", file=sys.stderr)
        return 2

    content_dirs = [cfg["content_dir"]]
    # Also scan secondary collections (SEO hub etc.) for used images.
    for key in ("guides_dir", "resources_dir"):
        extra = cfg.get(key)
        if extra:
            content_dirs.append(extra)

    all_imgs = library_images(lib)
    if not all_imgs:
        print("assign_images: no images in library", file=sys.stderr)
        return 2

    used = used_images(repo, content_dirs, cfg)
    pool = [p for p in all_imgs if os.path.basename(p) not in used]
    recycled = False
    if not pool:
        pool = all_imgs
        recycled = True

    words = topic_words(args.topic, stopwords_for(cfg))
    ranked = sorted(pool, key=lambda p: (-relevance(p, words), p))
    picked = ranked[:args.count]

    site_root = repo
    for p in picked:
        rel = os.path.relpath(p, os.path.join(site_root, "public"))
        url = "/" + rel.replace(os.sep, "/")
        alt = (os.path.basename(p).rsplit(".", 1)[0]
               .replace("-", " ").replace("_", " "))
        print(f"{url}\n  alt: {alt}")

    unused_left = len(pool) - len(picked)
    print(f"\n# {len(picked)} assigned ({unused_left} still unused"
          f"{'; pool recycled - all images were used once' if recycled else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
