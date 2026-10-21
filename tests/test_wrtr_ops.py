"""Offline tests for scripts/wrtr_ops.py (no network, tmp files only)."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, ROOT)
import wrtr_ops as ops  # noqa: E402


def post(d, rel, hero, extra=""):
    p = os.path.join(d, "src", "content", "blog", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(f'---\ntitle: "T"\ndescription: "D"\npubDate: 2026-10-20\n'
                f'heroImage: "../../assets/blog/{hero}"\nheroAlt: "a"\n{extra}---\nbody\n')
    return p


class Site(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.d, "src", "pages", "blog"))
        open(os.path.join(self.d, "src", "pages", "faq.astro"), "w").close()

    def test_twin_may_share_hero(self):
        en = post(self.d, "a.md", "x.jpg")
        post(self.d, "es/a-es.md", "x.jpg", 'lang: es\ntranslationOf: "/blog/a"\n')
        self.assertEqual(ops.hero_reuse(en, {"heroImage": "x.jpg"}, self.d), [])

    def test_other_post_reusing_hero_fails(self):
        en = post(self.d, "a.md", "x.jpg")
        post(self.d, "b.md", "x.jpg")
        post(self.d, "es/c.md", "x.jpg", 'lang: es\ntranslationOf: "/blog/c"\n')
        self.assertEqual(ops.hero_reuse(en, {"heroImage": "x.jpg"}, self.d),
                         ["b.md", "es/c.md"])

    def test_routes(self):
        post(self.d, "a.md", "x.jpg")
        self.assertTrue(ops.route_exists(self.d, "/faq"))
        self.assertTrue(ops.route_exists(self.d, "/blog/a#top"))
        self.assertFalse(ops.route_exists(self.d, "/blog/nope"))
        self.assertFalse(ops.route_exists(self.d, "/es/blog/a"))

    def test_links_offline(self):
        probs, n_int, n_out = ops.check_links("[x](/faq) [y](/nope) ![i](/img.png) [o](https://e.com)",
                                              self.d, online=False)
        self.assertEqual((n_int, n_out), (2, 1))
        self.assertEqual(probs, ["internal 404: /nope"])

    def test_site_root(self):
        p = post(self.d, "es/a.md", "x.jpg")
        self.assertEqual(ops.site_root_for(p), self.d)


class Frontmatter(unittest.TestCase):
    def test_required_and_lengths(self):
        probs = ops.check_frontmatter({"title": "x" * 101, "description": "d",
                                       "pubDate": "2026-10-20", "draft": "true"})
        self.assertIn("missing heroImage", probs)
        self.assertIn("title over 100 chars", probs)
        self.assertIn("draft: true", probs)

    def test_normalize(self):
        fm = ops.normalize_fm({"tags": '["a b", "c"]', "pubDate": "2026-10-20", "heroAlt": "h"})
        self.assertEqual(fm["tags"], ["a b", "c"])
        self.assertEqual((fm["date"], fm["imageAlt"]), ("2026-10-20", "h"))

    def test_pair(self):
        en = {"file": "/x/blog/a.md", "fm": {"heroImage": "../../assets/blog/h.jpg"}}
        es = {"file": "/x/blog/es/b.md", "fm": {"lang": "es", "translationOf": "/blog/a",
                                                  "heroImage": "../../../assets/blog/h.jpg"}}
        self.assertEqual(ops.pair_problems(en, es), [])
        es["fm"]["translationOf"] = "/blog/z"
        es["fm"]["heroImage"] = "o.jpg"
        self.assertEqual(len(ops.pair_problems(en, es)), 2)


class Prices(unittest.TestCase):
    def test_extract_and_diff(self):
        p = ops.extract_prices("Starter $97/mo, Growth $297 per month, setup $1,000")
        self.assertEqual(p, ["$1,000", "$297permonth", "$97/mo"])
        self.assertEqual(ops.diff_prices(["$97/mo"], ["$99/mo"]),
                         {"added": ["$99/mo"], "removed": ["$97/mo"]})


def row(q, page, impr, pos, clicks=0):
    return {"query": q, "page": page, "impressions": impr, "position": pos,
            "clicks": clicks, "ctr": clicks / impr if impr else 0}


class Striking(unittest.TestCase):
    rows = [row("plumber website", "/p", 300, 7), row("plumber site cost", "/p", 100, 12),
            row("hvac website", "/h", 200, 5), row("febuslabs", "/", 900, 4),
            row("roofer website", "/r", 400, 2), row("electric site", "/e", 500, 30),
            row("tiny", "/t", 10, 6)]

    def test_picks_filter_and_rank(self):
        picks = ops.striking_picks(self.rows, ["febuslabs"], min_impr=50)
        self.assertEqual([p["page"] for p in picks], ["/p", "/h"])
        self.assertEqual(picks[0]["impressions"], 400)

    def test_before_after(self):
        state = {}
        items = ops.run_striking("s", self.rows, {"brand_terms": ["febuslabs"]}, state,
                                 "2026-10-01", 50, 3)
        self.assertEqual(len(items), 2)
        self.assertEqual(state["s"]["/p"]["baseline"]["impressions"], 400)
        later = [row("plumber website", "/p", 500, 3, 40)]
        items = ops.run_striking("s", later, {}, state, "2026-11-01", 50, 3)
        self.assertEqual(items, [])  # already tracked, no re-pick
        h = state["s"]["/p"]["history"][-1]
        self.assertEqual((h["date"], h["clicks"], h["position"]), ("2026-11-01", 40, 3.0))


class Clients(unittest.TestCase):
    def test_active_clients(self):
        import sqlite3
        db = os.path.join(tempfile.mkdtemp(), "a.db")
        con = sqlite3.connect(db)
        con.execute("create table clients (slug text, status text)")
        con.executemany("insert into clients values (?,?)",
                        [("b", "active"), ("a", "grace"), ("c", "canceled")])
        con.commit(); con.close()
        self.assertEqual(ops.active_client_slugs(db), ["a", "b"])


class Wake(unittest.TestCase):
    def test_wake_file_appends(self):
        d = tempfile.mkdtemp()
        p = ops._wake_file(d, "wrtr_x", [{"reason": "r"}])
        ops._wake_file(d, "wrtr_x", [{"reason": "s"}])
        import json
        self.assertEqual(len(json.load(open(p))), 2)


if __name__ == "__main__":
    unittest.main()
