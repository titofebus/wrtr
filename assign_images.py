#!/usr/bin/env python3
"""Assign real, never-duplicated images to a new entry.

Scans the site's image library and all existing entries, then picks the
most topic-relevant images that haven't been used yet. Stateless: usage is
derived from entry frontmatter (`image:`) and markdown image references,
so there's no state file to lose.

Usage:
    .venv/bin/python assign_images.py --site febusfilms \\
        --topic "lake nona wedding venues" --count 3

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
STOPWORDS = {
    "orlando", "wedding", "photography", "photographer", "photographers",
    "the", "a", "an", "and", "of", "in", "for", "with", "to",
}


def library_images(lib_dir):
    out = []
    for root, _dirs, files in os.walk(lib_dir):
        for f in sorted(files):
            if f.lower().endswith(IMG_EXTS):
                out.append(os.path.join(root, f))
    return out


def used_images(repo, content_dirs):
    """Filenames (basenames) already referenced by any entry."""
    used = set()
    img_ref = re.compile(r"[\"'\(](/[^\"'\)]*?\.(?:webp|jpg|jpeg|png|avif))", re.I)
    for d in content_dirs:
        full = os.path.join(repo, d)
        if not os.path.isdir(full):
            continue
        for root, _dirs, files in os.walk(full):
            for f in files:
                if not f.endswith(".md"):
                    continue
                try:
                    text = open(os.path.join(root, f), encoding="utf-8").read()
                except (OSError, UnicodeDecodeError):
                    continue
                for m in img_ref.finditer(text):
                    used.add(os.path.basename(m.group(1)))
                fm = re.match(r"^---\n(.*?)\n---", text, re.S)
                if fm:
                    m = re.search(r"^image:\s*[\"']?([^\"'\n]+)[\"']?\s*$",
                                  fm.group(1), re.M)
                    if m:
                        used.add(os.path.basename(m.group(1).strip()))
    return used


def topic_words(topic):
    return {w for w in re.findall(r"[a-z]+", topic.lower())
            if w not in STOPWORDS and len(w) > 2}


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

    content_dirs = [cfg.get("content_dir", "src/content/journal")]
    # Also scan the future guides collection if the site has one.
    guides = cfg.get("guides_dir")
    if guides:
        content_dirs.append(guides)

    all_imgs = library_images(lib)
    if not all_imgs:
        print("assign_images: no images in library", file=sys.stderr)
        return 2

    used = used_images(repo, content_dirs)
    pool = [p for p in all_imgs if os.path.basename(p) not in used]
    recycled = False
    if not pool:
        pool = all_imgs
        recycled = True

    words = topic_words(args.topic)
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
          f"{'; pool recycled — all images were used once' if recycled else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
