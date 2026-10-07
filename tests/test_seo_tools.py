"""Regression tests for the SEO toolkit's pure functions.

Run: .venv/bin/python -m unittest discover -s tests -v
No network, no credentials, no real files (tmp files only).

Note: fixtures use febusfilms.com URLs and queries because Febus Films is
the reference brand — they exercise URL/query handling, not brand behavior.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import site_config
import weekly_scan as scan
import content_brief as brief
import draft_score


class TestVenueIntent(unittest.TestCase):
    def test_venue_word_matches(self):
        self.assertTrue(scan._has_venue_intent("lake nona wedding venues",
                                               ["venue", "venues"]))

    def test_avenue_trap(self):
        # "avenue" must NOT match venue-word "venue" (word-boundary bug)
        self.assertFalse(scan._has_venue_intent("fifth avenue photos",
                                                ["venue"]))

    def test_plural_stemming(self):
        self.assertTrue(scan._has_venue_intent("orlando wedding venues",
                                               ["venue"]))

    def test_empty_venue_words(self):
        self.assertFalse(scan._has_venue_intent("lake nona wedding venues",
                                                []))


class TestLooksLikeHub(unittest.TestCase):
    def test_entry_under_content_route_is_not_hub(self):
        self.assertFalse(scan._looks_like_hub(
            "lake nona wedding venues",
            "https://www.febusfilms.com/journal/lake-nona-wedding-venues/",
            "/journal/"))

    def test_dedicated_hub_page(self):
        self.assertTrue(scan._looks_like_hub(
            "lake nona wedding venues",
            "https://www.febusfilms.com/venues/lake-nona-wedding-venues/",
            "/journal/"))

    def test_query_string_stripped(self):
        self.assertTrue(scan._looks_like_hub(
            "lake nona wedding venues",
            "https://www.febusfilms.com/venues/lake-nona-wedding-venues/?x=1",
            "/journal/"))

    def test_all_generic_query_assumes_covered(self):
        self.assertTrue(scan._looks_like_hub(
            "wedding venues", "https://www.febusfilms.com/about/",
            "/journal/"))


class TestStem(unittest.TestCase):
    def test_plural(self):
        self.assertEqual(scan._stem("venues"), "venue")

    def test_no_false_strip(self):
        self.assertEqual(scan._stem("avenue"), "avenue")

    def test_short_untouched(self):
        self.assertEqual(scan._stem("spa"), "spa")


class TestNormUrl(unittest.TestCase):
    def test_scheme_insensitive(self):
        self.assertEqual(scan._norm_url("http://x.com/a"),
                         scan._norm_url("https://x.com/a"))

    def test_trailing_slash(self):
        self.assertEqual(scan._norm_url("https://x.com/a/"),
                         scan._norm_url("https://x.com/a"))

    def test_different_path(self):
        self.assertNotEqual(scan._norm_url("https://x.com/a"),
                            scan._norm_url("https://x.com/b"))


class TestSlugify(unittest.TestCase):
    def test_punctuation(self):
        self.assertEqual(brief.slugify("Lake Nona: Top Venues!"), "lake-nona-top-venues")

    def test_length_cap(self):
        self.assertLessEqual(len(brief.slugify("x" * 200)), 70)

    def test_lowercase(self):
        self.assertEqual(brief.slugify("ABC"), "abc")


class TestLoadPick(unittest.TestCase):
    def _write(self, obj):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        if isinstance(obj, str):
            f.write(obj)
        else:
            json.dump(obj, f)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_valid(self):
        p = self._write({"date": "2026-10-04", "query": "q",
                         "page": "https://x.com/", "position": 17.5,
                         "impressions": 25, "kind": "venue"})
        self.assertEqual(scan._load_pick(p)["query"], "q")

    def test_malformed_json(self):
        self.assertIsNone(scan._load_pick(self._write("{not json")))

    def test_wrong_shape(self):
        self.assertIsNone(scan._load_pick(self._write([1, 2, 3])))

    def test_missing_keys(self):
        self.assertIsNone(scan._load_pick(self._write({"query": "q"})))

    def test_bool_position_rejected(self):
        # True is an int subclass — must not pass as a position
        p = self._write({"date": "d", "query": "q", "page": "u",
                         "position": True, "impressions": 1, "kind": "k"})
        self.assertIsNone(scan._load_pick(p))


class TestValidateScanConfig(unittest.TestCase):
    def _cfg(self, **kw):
        base = {"slug": "t", "scan_thresholds": {}, "content_route": "/j/",
                "brand_terms": [], "venue_intent_words": []}
        base.update(kw)
        return base

    def test_str_thresholds(self):
        with self.assertRaises(SystemExit):
            scan._validate_scan_config(self._cfg(scan_thresholds="x"))

    def test_non_numeric_threshold(self):
        with self.assertRaises(SystemExit):
            scan._validate_scan_config(self._cfg(
                scan_thresholds={"striking_min_impressions": "many"}))

    def test_bool_threshold_rejected(self):
        with self.assertRaises(SystemExit):
            scan._validate_scan_config(self._cfg(
                scan_thresholds={"striking_min_impressions": True}))

    def test_bad_content_route(self):
        for bad in (123, None, "   "):
            with self.assertRaises(SystemExit):
                scan._validate_scan_config(self._cfg(content_route=bad))

    def test_bare_string_list_ok(self):
        cfg = self._cfg(brand_terms="febus")
        scan._validate_scan_config(cfg)
        self.assertEqual(cfg["brand_terms"], ["febus"])


class TestRenderTemplate(unittest.TestCase):
    def test_unknown_placeholder(self):
        with self.assertRaises(SystemExit) as cm:
            brief._render_template("{bogus}", "t", title="T")
        self.assertIn("title", str(cm.exception))

    def test_non_string_template(self):
        with self.assertRaises(SystemExit):
            brief._render_template(123, "t", title="T")

    def test_ok(self):
        self.assertEqual(brief._render_template("{title}!", "t", title="Hi"),
                         "Hi!")


class TestSiteConfigLoad(unittest.TestCase):
    def test_unknown_slug(self):
        with self.assertRaises(SystemExit) as cm:
            site_config.load("no-such-site-xyz")
        self.assertIn("febusfilms", str(cm.exception))

    def test_bad_chars(self):
        with self.assertRaises(SystemExit):
            site_config.load("../secret")

    def test_env_override(self):
        os.environ["SEO_SITE"] = "febusfilms"
        try:
            cfg = site_config.load()
            self.assertEqual(cfg["slug"], "febusfilms")
        finally:
            del os.environ["SEO_SITE"]


class TestClassifyPick(unittest.TestCase):
    def setUp(self):
        self._orig = scan._liveness

    def tearDown(self):
        scan._liveness = self._orig

    def test_redirected_striking_becomes_venue(self):
        scan._liveness = lambda page: (200, "https://www.febusfilms.com/journal/")
        kind, status, final, redir = scan.classify_pick(
            "striking", "https://www.febusfilms.com/blog/old/")
        self.assertEqual(kind, "venue")
        self.assertTrue(redir)

    def test_live_striking_stays(self):
        scan._liveness = lambda page: (200, page)
        kind, status, final, redir = scan.classify_pick(
            "striking", "https://www.febusfilms.com/about/")
        self.assertEqual(kind, "striking")
        self.assertFalse(redir)

    def test_dead_url_keeps_kind_but_flags(self):
        scan._liveness = lambda page: (404, page)
        kind, status, final, redir = scan.classify_pick(
            "striking", "https://www.febusfilms.com/blog/dead/")
        self.assertEqual(status, 404)
        self.assertFalse(redir)


class TestNeedHelpers(unittest.TestCase):
    def test_need_dict_bad(self):
        with self.assertRaises(SystemExit):
            site_config.need_dict({"slug": "t", "k": "x"}, "k")

    def test_need_dict_ok(self):
        self.assertEqual(site_config.need_dict({"slug": "t", "k": {"a": 1}},
                                               "k"),
                         {"a": 1})

    def test_need_dict_missing_default(self):
        self.assertEqual(site_config.need_dict({"slug": "t"}, "k"), {})

    def test_need_list_non_empty(self):
        with self.assertRaises(SystemExit):
            site_config.need_list({"slug": "t", "k": []}, "k", non_empty=True)

    def test_need_list_ok(self):
        self.assertEqual(site_config.need_list({"slug": "t", "k": ["a"]},
                                               "k", non_empty=True),
                         ["a"])

    def test_need_str_default(self):
        self.assertEqual(site_config.need_str({"slug": "t"}, "missing"), "")

    def test_need_str_ok(self):
        self.assertEqual(site_config.need_str({"slug": "t", "k": "v"}, "k"),
                         "v")

    def test_need_number_mapping_bool(self):
        with self.assertRaises(SystemExit):
            site_config.need_number_mapping({"slug": "t", "k": {"a": True}},
                                            "k")

    def test_need_number_mapping_ok(self):
        self.assertEqual(
            site_config.need_number_mapping({"slug": "t", "k": {"a": 1.5}},
                                            "k"),
            {"a": 1.5})


class TestFilterSecondaries(unittest.TestCase):
    GEO = ["orlando", "lake nona", "central florida", "florida",
           "winter park"]
    TARGET = "lake nona wedding venues"

    def test_drops_primary_itself(self):
        out = brief.filter_secondaries([self.TARGET, "orlando wedding venues"],
                                       self.TARGET, self.GEO)
        self.assertNotIn(self.TARGET, out)

    def test_collapses_near_dupes(self):
        cands = ["lake mary fl wedding venues",
                 "lake mary wedding venue florida",
                 "lake mary wedding venues"]
        out = brief.filter_secondaries(cands, self.TARGET, self.GEO)
        self.assertEqual(len(out), 1)

    def test_rejects_out_of_state(self):
        cands = ["best northern ca wedding venues", "lake nona va address",
                 "lakes region wedding venues"]
        out = brief.filter_secondaries(cands, self.TARGET, self.GEO)
        self.assertEqual(out, [])

    def test_rejects_multiword_state_abbr(self):
        out = brief.filter_secondaries(["lake george wedding venues ny"],
                                       self.TARGET, self.GEO)
        self.assertEqual(out, [])

    def test_keeps_in_geo(self):
        out = brief.filter_secondaries(["lake nona wave hotel weddings"],
                                       self.TARGET, self.GEO)
        self.assertEqual(out, ["lake nona wave hotel weddings"])

    def test_conservative_without_brand_states(self):
        # No state in geo_terms -> any state mention is dropped.
        out = brief.filter_secondaries(["austin tx wedding venues"],
                                       self.TARGET, ["austin"])
        self.assertEqual(out, [])

    def test_caps_at_eight(self):
        cands = [f"lake nona wedding venue option {i}" for i in range(20)]
        out = brief.filter_secondaries(cands, self.TARGET, self.GEO)
        self.assertLessEqual(len(out), 8)


class TestStatesIn(unittest.TestCase):
    def test_single_word_abbr(self):
        self.assertEqual(brief._states_in("venues ca"), {"california"})

    def test_multiword_abbr(self):
        # Regression: abbreviations of multi-word states were never matched.
        self.assertEqual(brief._states_in("venues nh"), {"new hampshire"})
        self.assertEqual(brief._states_in("venues ny"), {"new york"})

    def test_ambiguous_abbr_ignored(self):
        self.assertEqual(brief._states_in("wedding venues in orlando"), set())

    def test_brand_states(self):
        self.assertEqual(brief._brand_states(["orlando", "florida"]),
                         {"florida"})


class TestRelatedEntries(unittest.TestCase):
    ENTRIES = ["lake-nona-country-club-wedding",
               "finding-the-right-wedding-photographer-for-you",
               "a-wedding-timeline-that-lets-you-enjoy-the-day"]

    def test_names_anchor_match(self):
        out = brief.related_entries(self.ENTRIES, "lake nona wedding venues")
        self.assertEqual(out, ["lake-nona-country-club-wedding"])

    def test_no_anchor_no_names(self):
        out = brief.related_entries(self.ENTRIES, "miami wedding venues")
        self.assertEqual(out, [])


class TestSavePickMode(unittest.TestCase):
    def test_state_file_is_0600(self):
        # Round-4 security fix: pick state must not be world-readable.
        import stat
        f = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        f.close()
        self.addCleanup(os.unlink, f.name)
        scan._save_pick(f.name, {"query": "q"})
        mode = stat.S_IMODE(os.stat(f.name).st_mode)
        self.assertEqual(mode, 0o600)


class TestGscCall(unittest.TestCase):
    def test_passthrough(self):
        self.assertEqual(scan._gsc_call(lambda: 42), 42)

    def test_auth_error_flags_owner(self):
        import io
        from contextlib import redirect_stdout
        def bad():
            raise Exception("RefreshError: invalid_grant")
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
            scan._gsc_call(bad)
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("owner action", buf.getvalue())

    def test_transient_error_says_retry(self):
        import io
        from contextlib import redirect_stdout
        import requests
        def bad():
            r = requests.Response()
            r.status_code = 500
            raise requests.HTTPError("boom", response=r)
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
            scan._gsc_call(bad)
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("retry next run", buf.getvalue())


class TestMinerBailout(unittest.TestCase):
    def test_bails_on_dead_endpoint(self):
        # Round-5 resilience fix: 3 consecutive suggest failures must bail
        # instead of burning ~9 minutes on timeouts.
        import time
        import keyword_miner as km
        orig_suggest, orig_cache = km.suggest, km._cache_path
        km.suggest = lambda q: None
        km._cache_path = lambda seed: os.path.join(
            tempfile.gettempdir(), f".test-miner-{os.getpid()}.json")
        try:
            t = time.time()
            out = km.mine("test seed xyzzy")
            elapsed = time.time() - t
        finally:
            km.suggest, km._cache_path = orig_suggest, orig_cache
        self.assertEqual(out, [])
        self.assertLess(elapsed, 5)


class TestGscPagination(unittest.TestCase):
    def test_trailing_call_skipped(self):
        # Round-6 fix: no wasted empty call when total is an exact
        # multiple of the page size.
        import gsc
        calls = []

        def fake_post(path, body):
            calls.append(body["startRow"])
            # Exactly 2 full pages, then nothing.
            if body["startRow"] < 2 * gsc.MAX_PAGE_SIZE:
                return {"rows": [{"keys": ["q"], "clicks": 1,
                                  "impressions": 1, "ctr": 0.1,
                                  "position": 5.0}] * gsc.MAX_PAGE_SIZE}
            return {"rows": []}

        orig = gsc._post
        gsc._post = fake_post
        try:
            rows = gsc.search_analytics("https://x.com/", "2026-01-01",
                                        "2026-01-28",
                                        row_limit=2 * gsc.MAX_PAGE_SIZE)
        finally:
            gsc._post = orig
        self.assertEqual(len(rows), 2 * gsc.MAX_PAGE_SIZE)
        self.assertEqual(calls, [0, gsc.MAX_PAGE_SIZE])


class TestQuestionScope(unittest.TestCase):
    GEO = ["orlando", "florida"]

    def test_other_market_dropped(self):
        self.assertFalse(brief._question_in_scope(
            "is atlanta bike friendly?", "orlando bike tours", self.GEO))

    def test_geo_question_kept(self):
        self.assertTrue(brief._question_in_scope(
            "where can i rent a bike in orlando?", "orlando bike tours",
            self.GEO))

    def test_topical_question_kept(self):
        self.assertTrue(brief._question_in_scope(
            "where is lake nona?", "lake nona wedding venues",
            ["orlando", "lake nona", "florida"]))


class TestSecondariesBanned(unittest.TestCase):
    def test_banned_term_filtered(self):
        cfg = {"name": "T", "slug": "t", "site_url": "https://x.com/",
               "content_route": "/journal/",
               "repo": tempfile.gettempdir(), "content_dir": "nope",
               "type_category_map": {"guide": "tips"},
               "title_templates": ["{title}"],
               "geo_terms": ["orlando", "florida"],
               "banned_terms": ["ebike", "e-bike"],
               "categories": {"tips": "tips"}}
        import keyword_miner
        orig = keyword_miner.mine
        keyword_miner.mine = lambda t: ["orlando e bike rideout",
                                        "orlando bike tours",
                                        "best orlando bike trails"]
        try:
            out = brief.build_brief(cfg, "orlando bike tours", "guide")
        finally:
            keyword_miner.mine = orig
        self.assertNotIn("e bike rideout", out)


class TestLooksNamedVenue(unittest.TestCase):
    GEO = ["orlando", "lake nona", "florida"]

    def test_named_venue(self):
        self.assertTrue(scan._looks_named_venue(
            "lake nona wave hotel weddings", self.GEO))

    def test_generic_topic(self):
        self.assertFalse(scan._looks_named_venue(
            "lake nona wedding venues", self.GEO))

    def test_no_geo(self):
        self.assertFalse(scan._looks_named_venue(
            "wave hotel weddings", self.GEO))


class TestVenueNamedQueries(unittest.TestCase):
    GEO = ["orlando", "lake nona", "florida"]
    BRAND = ["febus films", "febus"]

    def _r(self, q, imp=5, pos=8.0):
        return {"query": q, "impressions": imp, "position": pos}

    def test_names_venue(self):
        out = brief._venue_named_queries(
            [self._r("lake nona wave hotel weddings")],
            "lake nona wedding venues", self.GEO, self.BRAND)
        self.assertEqual(len(out), 1)

    def test_brand_query_excluded(self):
        out = brief._venue_named_queries(
            [self._r("febus films wedding photos lake nona")],
            "lake nona wedding venues", self.GEO, self.BRAND)
        self.assertEqual(out, [])

    def test_target_itself_excluded(self):
        out = brief._venue_named_queries(
            [self._r("lake nona wedding venues")],
            "lake nona wedding venues", self.GEO, self.BRAND)
        self.assertEqual(out, [])


class TestKeywordsYaml(unittest.TestCase):
    def test_keywords_render_valid_yaml_list(self):
        import yaml
        cfg = {"name": "T", "slug": "t", "site_url": "https://x.com/",
               "content_route": "/journal/",
               "repo": tempfile.gettempdir(), "content_dir": "nope",
               "type_category_map": {"guide": "tips"},
               "title_templates": ["{title}"],
               "geo_terms": ["orlando"],
               "categories": {"tips": "tips"}}
        import keyword_miner
        orig = keyword_miner.mine
        keyword_miner.mine = lambda t: []
        try:
            out = brief.build_brief(cfg, "best venues: lake nona", "guide")
        finally:
            keyword_miner.mine = orig
        m = None
        lines = out.split("\n")
        for i, l in enumerate(lines):
            if l == "keywords:":
                block = []
                for bl in lines[i:]:
                    if bl == "---":
                        break
                    block.append(bl)
                m = "\n".join(block)
        self.assertIsNotNone(m)
        parsed = yaml.safe_load(m)
        self.assertEqual(parsed, {"keywords": ["best venues: lake nona"]})


class TestBingSubmitUrl(unittest.TestCase):
    def _cfg(self, route):
        return {"name": "T", "slug": "t", "site_url": "https://x.com/",
                "content_route": route,
                "repo": tempfile.gettempdir(), "content_dir": "nope",
                "type_category_map": {"guide": "tips"},
                "title_templates": ["{title}"],
                "geo_terms": ["orlando"],
                "categories": {"tips": "tips"}}

    def _url_line(self, cfg):
        import keyword_miner
        orig = keyword_miner.mine
        keyword_miner.mine = lambda t: []
        try:
            out = brief.build_brief(cfg, "orlando bike tours", "guide")
        finally:
            keyword_miner.mine = orig
        return next(l for l in out.split("\n") if "bing.py submit" in l)

    def test_journal_route(self):
        self.assertIn("https://x.com/journal/orlando-bike-tours/",
                      self._url_line(self._cfg("/journal/")))

    def test_root_route_no_double_slash(self):
        line = self._url_line(self._cfg("/"))
        self.assertIn("https://x.com/orlando-bike-tours/", line)
        self.assertNotIn("//orlando", line)


class TestDraftScore(unittest.TestCase):
    def _draft(self, fm, body):
        f = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
        f.write("---\n" + fm + "\n---\n" + body)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_parse_front_matter(self):
        p = self._draft('title: "Hello"\nkeywords:\n  - a\n  - b',
                        "# Hi\n\nBody text here.")
        fm, body = draft_score.parse_draft(p)
        self.assertEqual(fm["title"], "Hello")
        self.assertEqual(fm["keywords"], ["a", "b"])
        self.assertIn("# Hi", body)

    def test_headings(self):
        hs = draft_score.headings("# T\n\n## A\n\n### B\n\n## C")
        self.assertEqual(hs, [(1, "T"), (2, "A"), (3, "B"), (2, "C")])

    def test_keyword_hits_word_boundary(self):
        self.assertEqual(draft_score.keyword_hits(
            "orlando wedding photographer", "orlando wedding"), 1)
        # "orlando weddings" should NOT match "orlando wedding"
        self.assertEqual(draft_score.keyword_hits(
            "best orlando weddings", "orlando wedding"), 0)

    def test_banned_term_blocks(self):
        cfg = {"slug": "t", "banned_terms": ["blog"], "draft_score_min": 70}
        p = self._draft('title: "T"', "# T\n\nThis blog post is great. " * 20)
        fm, body = draft_score.parse_draft(p)
        checks = draft_score.check_seo(
            fm, draft_score.plain_text(body),
            draft_score.headings(body), "wedding", cfg)
        banned = [c for c in checks if c[0] == "banned terms"][0]
        self.assertEqual(banned[1], "red")
        self.assertIn("HARD", banned[2])

    def test_title_counts_as_h1(self):
        cfg = {"slug": "t", "banned_terms": [], "draft_score_min": 70}
        p = self._draft('title: "My Title"',
                        "## Section\n\nBody. " * 30)
        fm, body = draft_score.parse_draft(p)
        checks = draft_score.check_seo(
            fm, draft_score.plain_text(body),
            draft_score.headings(body), "title", cfg)
        h1 = [c for c in checks if c[0] == "single H1"][0]
        self.assertEqual(h1[1], "green")

    def test_score_math(self):
        checks = [("a", "green", ""), ("b", "yellow", ""), ("c", "red", "")]
        self.assertEqual(draft_score.score(checks), 50)

    def test_voice_tics_flagged(self):
        checks = draft_score.check_voice(
            "Furthermore, it is important to note the tapestry of options. " * 5)
        tics = [c for c in checks if c[0] == "AI voice tics"][0]
        self.assertEqual(tics[1], "yellow")
        self.assertIn("furthermore", tics[2])


if __name__ == "__main__":
    unittest.main()
