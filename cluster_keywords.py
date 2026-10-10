"""Cluster a keyword list into topic groups (TF-IDF + agglomerative clustering).

Turns the flat output of keyword_miner.py (or GSC queries) into themed
clusters - each cluster is one content entry / page angle.

Usage:
  .venv/bin/python keyword_miner.py "best running shoes" | grep '^- ' | sed 's/^- //' > kws.txt
  .venv/bin/python cluster_keywords.py kws.txt [--n 12]
"""
import re
import sys

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer


def clean(kw):
    return re.sub(r"[^a-z0-9 ]", "", kw.lower()).strip()


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: cluster_keywords.py <keywords-file> [--n K] - TF-IDF topic clusters.")
        print("  <keywords-file>: one keyword per line (e.g. mined output).")
        raise SystemExit(0 if len(sys.argv) > 1 else 2)
    path = sys.argv[1]
    n = 12
    args = sys.argv[2:]
    for i, a in enumerate(args):
        if a == "--n" and i + 1 < len(args):
            n = int(args[i + 1])
        elif a.startswith("--n="):
            n = int(a.split("=", 1)[1])
    kws = []
    for l in open(path):
        l = l.strip()
        if not l or l.startswith("#"):
            continue  # tolerate miner markdown: skip headers/blanks
        if l.startswith("- "):
            l = l[2:].strip()  # strip bullet prefix from mined output
        if l and clean(l):
            kws.append(l)
    if not kws:
        print("(no keywords found in file)")
        return
    docs = [clean(k) for k in kws]
    vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    X = vec.fit_transform(docs).toarray()
    n = min(n, len(kws))
    labels = AgglomerativeClustering(n_clusters=n, metric="cosine",
                                     linkage="average").fit_predict(X)
    clusters = {}
    for kw, lab in zip(kws, labels):
        clusters.setdefault(int(lab), []).append(kw)
    # order clusters by size, show centroid keyword as the label
    for lab in sorted(clusters, key=lambda l: -len(clusters[l])):
        members = clusters[lab]
        centroid = X[[kws.index(m) for m in members]].mean(axis=0)
        terms = vec.get_feature_names_out()
        top = ", ".join(terms[i] for i in centroid.argsort()[-3:][::-1])
        print(f"\n## Cluster: {top} ({len(members)})")
        for m in members[:15]:
            print(f"- {m}")
        if len(members) > 15:
            print(f"  … +{len(members) - 15} more")


if __name__ == "__main__":
    main()
