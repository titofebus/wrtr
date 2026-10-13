"""Regression tests for the SEO toolkit's pure functions.

Run: .venv/bin/python -m unittest discover -s tests -v
No network, no credentials, no real files (tmp files only).

Note: fixtures use example.com URLs and queries - they exercise URL/query
handling, not brand behavior.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import site_config
import weekly_scan as scan
import content_brief as brief
import draft_score
import assign_images


class TestVenueIntent(unittest.TestCase):
    def test_venue_word_matches(self):
        self.assertTrue(scan._has_venue_intent("austin bike tour locations",
                                               ["location", "locations"]))

    def test_avenue_trap(self):
        # "avenue" must NOT match venue-word "venue" (word-boundary bug)
        self.assertFalse(scan._has_venue_intent("fifth avenue photos",
                                                ["venue"]))

    def test_plural_stemming(self):
        self.assertTrue(scan._has_venue_intent("austin bike tours",
                                               ["tour"]))

    def test_empty_venue_words(self):
        self.assertFalse(scan._has_venue_intent("austin bike tour locations",
                                                []))


class TestLooksLikeHub(unittest.TestCase):
    def test_entry_under_content_route_is_not_hub(self):
        self.assertFalse(scan._looks_like_hub(
            "austin bike tours",
            "https://www.example.com/journal/austin-bike-tours/",
            "/journal/"))

    def test_dedicated_hub_page(self):
        self.assertTrue(scan._looks_like_hub(
            "austin bike tours",
            "https://www.example.com/tours/austin-bike-tours/",
            "/journal/"))

    def test_query_string_stripped(self):
        self.assertTrue(scan._looks_like_hub(
            "austin bike tours",
            "https://www.example.com/tours/austin-bike-tours/?x=1",
            "/journal/"))

    def test_all_generic_query_assumes_covered(self):
        self.assertTrue(scan._looks_like_hub(
            "bike tours", "https://www.example.com/about/",
            "/journal/", generic_words={"bike", "tours"}))


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
        self.assertEqual(brief.slugify("Austin: Top Bike Tours!"), "austin-top-bike-tours")

    def test_collection_resources(self):
        cfg = {
            "name": "Test Brand",
            "slug": "test",
            "repo": "/tmp/x",
            "site_url": "https://test.example/",
            "content_dir": "src/content/guide",
            "content_route": "/guide/",
            "content_kind": "Guide",
            "resources_dir": "src/content/handbook",
            "resources_route": "/handbook/",
            "resources_kind": "Handbook",
            "type_category_map": {"guide": "tips"},
            "categories": {"tips": "Tips"},
        }
        out = brief.build_brief(cfg, "austin bike tours", "guide", "resources")
        self.assertIn("# Handbook brief:", out)
        self.assertIn("src/content/handbook/austin-bike-tours.md", out)
        self.assertIn("https://test.example/handbook/austin-bike-tours/", out)

    def test_collection_fallback(self):
        cfg = {
            "name": "Test Brand",
            "slug": "test",
            "repo": "/tmp/x",
            "site_url": "https://test.example/",
            "content_dir": "src/content/guide",
            "content_route": "/guide/",
            "content_kind": "Guide",
            "type_category_map": {"guide": "tips"},
            "categories": {"tips": "Tips"},
        }
        out = brief.build_brief(cfg, "austin bike tours", "guide", "resources")
        self.assertIn("falling back to the main collection", out)
        self.assertIn("src/content/guide/austin-bike-tours.md", out)

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
        # True is an int subclass - must not pass as a position
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
        cfg = self._cfg(brand_terms="acme")
        scan._validate_scan_config(cfg)
        self.assertEqual(cfg["brand_terms"], ["acme"])


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
        # the error names a known site so the user sees what's available
        self.assertIn("example", str(cm.exception))

    def test_bad_chars(self):
        with self.assertRaises(SystemExit):
            site_config.load("../secret")

    def test_env_override(self):
        # hermetic: write a temp site dir, don't rely on a shipped config
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        with open(os.path.join(d, "acme.yaml"), "w") as f:
            f.write("name: Acme\nsite_url: https://acme.example/\n"
                    "repo: /tmp/x\ncontent_dir: c\n")
        orig = site_config.SITES_DIR
        site_config.SITES_DIR = d
        os.environ["SEO_SITE"] = "acme"
        try:
            cfg = site_config.load()
            self.assertEqual(cfg["slug"], "acme")
        finally:
            del os.environ["SEO_SITE"]
            site_config.SITES_DIR = orig

    def test_default_site(self):
        # the shipped default resolves without env vars
        if "SEO_SITE" in os.environ:
            del os.environ["SEO_SITE"]
        cfg = site_config.load()
        self.assertEqual(cfg["slug"], "example")


class TestClassifyPick(unittest.TestCase):
    def setUp(self):
        self._orig = scan._liveness

    def tearDown(self):
        scan._liveness = self._orig

    def test_redirected_striking_becomes_venue(self):
        scan._liveness = lambda page: (200, "https://www.example.com/journal/")
        kind, status, final, redir = scan.classify_pick(
            "striking", "https://www.example.com/blog/old/")
        self.assertEqual(kind, "venue")
        self.assertTrue(redir)

    def test_live_striking_stays(self):
        scan._liveness = lambda page: (200, page)
        kind, status, final, redir = scan.classify_pick(
            "striking", "https://www.example.com/about/")
        self.assertEqual(kind, "striking")
        self.assertFalse(redir)

    def test_dead_url_keeps_kind_but_flags(self):
        scan._liveness = lambda page: (404, page)
        kind, status, final, redir = scan.classify_pick(
            "striking", "https://www.example.com/blog/dead/")
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
    GEO = ["austin", "texas", "round rock"]
    TARGET = "austin bike tours"

    def test_drops_primary_itself(self):
        out = brief.filter_secondaries([self.TARGET, "texas bike tours"],
                                       self.TARGET, self.GEO)
        self.assertNotIn(self.TARGET, out)

    def test_collapses_near_dupes(self):
        cands = ["round rock tx bike tours",
                 "round rock bike tour texas",
                 "round rock bike tours"]
        out = brief.filter_secondaries(cands, self.TARGET, self.GEO)
        self.assertEqual(len(out), 1)

    def test_rejects_out_of_state(self):
        cands = ["best northern ca bike tours", "austin va address",
                 "lakes region bike tours"]
        out = brief.filter_secondaries(cands, self.TARGET, self.GEO)
        self.assertEqual(out, [])

    def test_rejects_multiword_state_abbr(self):
        out = brief.filter_secondaries(["lake travis bike tours ny"],
                                       self.TARGET, self.GEO)
        self.assertEqual(out, [])

    def test_keeps_in_geo(self):
        out = brief.filter_secondaries(["austin riverwalk bike tours"],
                                       self.TARGET, self.GEO)
        self.assertEqual(out, ["austin riverwalk bike tours"])

    def test_conservative_without_brand_states(self):
        # No state in geo_terms -> any state mention is dropped.
        out = brief.filter_secondaries(["austin tx bike tours"],
                                       self.TARGET, ["austin"])
        self.assertEqual(out, [])

    def test_caps_at_eight(self):
        cands = [f"austin bike tour option {i}" for i in range(20)]
        out = brief.filter_secondaries(cands, self.TARGET, self.GEO)
        self.assertLessEqual(len(out), 8)


class TestStatesIn(unittest.TestCase):
    def test_single_word_abbr(self):
        self.assertEqual(brief._states_in("tours ca"), {"california"})

    def test_multiword_abbr(self):
        # Regression: abbreviations of multi-word states were never matched.
        self.assertEqual(brief._states_in("tours nh"), {"new hampshire"})
        self.assertEqual(brief._states_in("tours ny"), {"new york"})

    def test_ambiguous_abbr_ignored(self):
        self.assertEqual(brief._states_in("bike tours in austin"), set())

    def test_brand_states(self):
        self.assertEqual(brief._brand_states(["austin", "texas"]),
                         {"texas"})


class TestRelatedEntries(unittest.TestCase):
    ENTRIES = ["austin-zilker-park-bike-tour",
               "finding-the-right-bike-tour-for-you",
               "a-bike-tour-checklist-that-helps-you-enjoy-the-ride"]
    GENERIC = {"bike", "tour", "tours"}

    def test_names_anchor_match(self):
        out = brief.related_entries(self.ENTRIES, "austin bike tours",
                                    generic_words=self.GENERIC)
        self.assertEqual(out, ["austin-zilker-park-bike-tour"])

    def test_no_anchor_no_names(self):
        out = brief.related_entries(self.ENTRIES, "denver bike tours",
                                    generic_words=self.GENERIC)
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
    GEO = ["austin", "texas"]

    def test_other_market_dropped(self):
        self.assertFalse(brief._question_in_scope(
            "is atlanta bike friendly?", "austin bike tours", self.GEO))

    def test_geo_question_kept(self):
        self.assertTrue(brief._question_in_scope(
            "where can i rent a bike in austin?", "austin bike tours",
            self.GEO))

    def test_topical_question_kept(self):
        self.assertTrue(brief._question_in_scope(
            "where do austin bike tours start?", "austin bike tours",
            ["austin", "texas"]))


class TestSecondariesBanned(unittest.TestCase):
    def test_banned_term_filtered(self):
        cfg = {"name": "T", "slug": "t", "site_url": "https://x.com/",
               "content_route": "/guide/",
               "repo": tempfile.gettempdir(), "content_dir": "nope",
               "type_category_map": {"guide": "tips"},
               "title_templates": ["{title}"],
               "geo_terms": ["austin", "texas"],
               "banned_terms": ["ebike", "e-bike"],
               "categories": {"tips": "tips"}}
        import keyword_miner
        orig = keyword_miner.mine
        keyword_miner.mine = lambda t: ["austin e bike rideout",
                                        "austin bike tours",
                                        "best austin bike trails"]
        try:
            out = brief.build_brief(cfg, "austin bike tours", "guide")
        finally:
            keyword_miner.mine = orig
        self.assertNotIn("e bike rideout", out)


class TestLooksNamedVenue(unittest.TestCase):
    GEO = ["austin", "texas"]
    GENERIC = {"bike", "tour", "tours"}

    def test_named_venue(self):
        self.assertTrue(scan._looks_named_venue(
            "austin riverwalk hill country bike tours", self.GEO,
            self.GENERIC))

    def test_generic_topic(self):
        self.assertFalse(scan._looks_named_venue(
            "austin bike tours", self.GEO, self.GENERIC))

    def test_no_geo(self):
        self.assertFalse(scan._looks_named_venue(
            "riverwalk hill country bike tours", self.GEO, self.GENERIC))


class TestVenueNamedQueries(unittest.TestCase):
    GEO = ["austin", "texas"]
    BRAND = ["acme bike tours", "acme"]
    GENERIC = {"bike", "tour", "tours", "rental", "rentals"}

    def _r(self, q, imp=5, pos=8.0):
        return {"query": q, "impressions": imp, "position": pos}

    def test_names_venue(self):
        out = brief._venue_named_queries(
            [self._r("austin riverwalk hill country bike tours")],
            "austin bike tours", self.GEO, self.BRAND, self.GENERIC)
        self.assertEqual(len(out), 1)

    def test_brand_query_excluded(self):
        out = brief._venue_named_queries(
            [self._r("acme bike tours austin rides")],
            "austin bike tours", self.GEO, self.BRAND, self.GENERIC)
        self.assertEqual(out, [])

    def test_target_itself_excluded(self):
        out = brief._venue_named_queries(
            [self._r("austin bike tours")],
            "austin bike tours", self.GEO, self.BRAND, self.GENERIC)
        self.assertEqual(out, [])


class TestKeywordsYaml(unittest.TestCase):
    def test_keywords_render_valid_yaml_list(self):
        import yaml
        cfg = {"name": "T", "slug": "t", "site_url": "https://x.com/",
               "content_route": "/guide/",
               "repo": tempfile.gettempdir(), "content_dir": "nope",
               "type_category_map": {"guide": "tips"},
               "title_templates": ["{title}"],
               "geo_terms": ["austin"],
               "categories": {"tips": "tips"}}
        import keyword_miner
        orig = keyword_miner.mine
        keyword_miner.mine = lambda t: []
        try:
            out = brief.build_brief(cfg, "best tours: austin", "guide")
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
        self.assertEqual(parsed, {"keywords": ["best tours: austin"]})


class TestBingSubmitUrl(unittest.TestCase):
    def _cfg(self, route):
        return {"name": "T", "slug": "t", "site_url": "https://x.com/",
                "content_route": route,
                "repo": tempfile.gettempdir(), "content_dir": "nope",
                "type_category_map": {"guide": "tips"},
                "title_templates": ["{title}"],
                "geo_terms": ["austin"],
                "categories": {"tips": "tips"}}

    def _url_line(self, cfg):
        import keyword_miner
        orig = keyword_miner.mine
        keyword_miner.mine = lambda t: []
        try:
            out = brief.build_brief(cfg, "austin bike tours", "guide")
        finally:
            keyword_miner.mine = orig
        return next(l for l in out.split("\n") if "bing.py submit" in l)

    def test_guide_route(self):
        self.assertIn("https://x.com/guide/austin-bike-tours/",
                      self._url_line(self._cfg("/guide/")))

    def test_root_route_no_double_slash(self):
        line = self._url_line(self._cfg("/"))
        self.assertIn("https://x.com/austin-bike-tours/", line)
        self.assertNotIn("//austin", line)


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
            "austin bike tour guide", "austin bike tour"), 1)
        # "austin bike tours" should NOT match "austin bike tour"
        self.assertEqual(draft_score.keyword_hits(
            "best austin bike tours", "austin bike tour"), 0)

    def test_banned_term_blocks(self):
        cfg = {"slug": "t", "banned_terms": ["blog"], "draft_score_min": 70}
        p = self._draft('title: "T"', "# T\n\nThis blog post is great. " * 20)
        fm, body = draft_score.parse_draft(p)
        checks = draft_score.check_seo(
            fm, draft_score.plain_text(body), body,
            draft_score.headings(body), "bike tour", cfg)
        banned = [c for c in checks if c[0] == "banned terms"][0]
        self.assertEqual(banned[1], "red")
        self.assertIn("HARD", banned[2])

    def test_title_counts_as_h1(self):
        cfg = {"slug": "t", "banned_terms": [], "draft_score_min": 70}
        p = self._draft('title: "My Title"',
                        "## Section\n\nBody. " * 30)
        fm, body = draft_score.parse_draft(p)
        checks = draft_score.check_seo(
            fm, draft_score.plain_text(body), body,
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

    def test_voice_tics_no_duplicates(self):
        self.assertEqual(len(draft_score.VOICE_TICS),
                         len(set(draft_score.VOICE_TICS)))

    def test_em_dash_prohibited(self):
        # owner rule 2026-10-07: ANY em/en dash is a hard failure
        text = "Word " * 300 + "— just one."
        checks = dict((c[0], c[1:]) for c in draft_score.check_voice(text))
        status, detail = checks["em dashes"]
        self.assertEqual(status, "red")
        self.assertIn("HARD", detail)

    def test_em_dash_clean(self):
        text = "Word " * 300 + "plain text, no dashes."
        checks = dict((c[0], c[1:]) for c in draft_score.check_voice(text))
        self.assertEqual(checks["em dashes"][0], "green")

    def test_structural_tells_flagged(self):
        text = "It is not just a tour, it is an experience. " * 3 + "Word " * 300
        checks = dict((c[0], c[1:]) for c in draft_score.check_voice(text))
        self.assertEqual(checks["AI structural patterns"][0], "yellow")
        self.assertIn("negative parallelism", checks["AI structural patterns"][1])

    def test_structural_tells_clean(self):
        text = "Word " * 400 + "plain human text here."
        checks = dict((c[0], c[1:]) for c in draft_score.check_voice(text))
        self.assertEqual(checks["AI structural patterns"][0], "green")

    def test_2026_tics_present(self):
        # spot-check 2026-era additions from the Graphite study
        for tic in ["this matters", "quietly powerful", "indelible mark",
                    "another dimension", "unwavering commitment"]:
            self.assertIn(tic, draft_score.VOICE_TICS, tic)

    def test_h2_keyword_variety(self):
        heads = [(2, "Austin bike tours guide"),
                 (2, "Austin bike tours pricing"),
                 (2, "Austin bike tours photos")]
        checks = dict((c[0], c[1:]) for c in
                      draft_score.check_seo({}, "x " * 500, "x " * 500, heads,
                                            "austin bike tours", {}))
        self.assertEqual(checks["H2 keyword variety"][0], "yellow")

    def test_h2_keyword_variety_ok(self):
        heads = [(2, "Austin bike tours guide"),
                 (2, "Best photo spots at sunset")]
        checks = dict((c[0], c[1:]) for c in
                      draft_score.check_seo({}, "x " * 500, "x " * 500, heads,
                                            "austin bike tours", {}))
        self.assertEqual(checks["H2 keyword variety"][0], "green")

    def test_intent_transactional(self):
        from content_brief import classify_intent
        label, _ = classify_intent("best bike tour austin")
        self.assertEqual(label, "TRANSACTIONAL")
        label, _ = classify_intent("austin bike tour pricing")
        self.assertEqual(label, "TRANSACTIONAL")

    def test_intent_informational(self):
        from content_brief import classify_intent
        label, _ = classify_intent("how to plan a bike tour route")
        self.assertEqual(label, "INFORMATIONAL")

    def test_intent_navigational(self):
        from content_brief import classify_intent
        label, _ = classify_intent("acme bike tours reviews", ["acme bike tours"])
        self.assertEqual(label, "NAVIGATIONAL")

    def test_internal_links(self):
        text = ("See [tours](/tours/) and [stories](/stories/). " * 60)
        checks = dict((c[0], c[1:]) for c in
                      draft_score.check_seo({}, text, text, [], "tours", {}))
        self.assertEqual(checks["internal links"][0], "green")

    def test_internal_links_missing(self):
        checks = dict((c[0], c[1:]) for c in
                      draft_score.check_seo({}, "Word " * 500, "Word " * 500, [], "tours", {}))
        self.assertEqual(checks["internal links"][0], "yellow")

    def test_answer_first_h2s(self):
        text = ("## Best sunset photo spots\n"
                "The best sunset photo spots in Austin are Zilker Park and Mount Bonnell. More text here.\n"
                "## What to wear\n"
                "Completely unrelated opening sentence about something else entirely.\n") + "Word " * 400
        heads = [(2, "Best sunset photo spots"), (2, "What to wear")]
        checks = dict((c[0], c[1:]) for c in
                      draft_score.check_seo({}, text, text, heads, "austin", {}))
        # 1 of 2 direct -> 50% meets the bar
        self.assertEqual(checks["answer-first H2s"][0], "green")

    def test_bold_label_bullets_flagged(self):
        # Muse house style (leaked Jul 2026 prompt): "- **Label**: explanation"
        text = ("- **Guide**: a local expert.\n" * 3) + "Word " * 300
        checks = dict((c[0], c[1:]) for c in draft_score.check_voice(text))
        status, detail = checks["AI structural patterns"]
        self.assertEqual(status, "yellow")
        self.assertIn("bold-label bullets", detail)

    def test_empty_keyword_rejected(self):
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "draft_score.py"),
             "/dev/null", "--keyword", " ", "--site", "example"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--keyword must not be empty", r.stderr)


class TestAEO(unittest.TestCase):
    def _aeo(self, fm, body, heads, cfg=None):
        cfg = cfg if cfg is not None else {"name": "Acme Bike Tours"}
        return dict((c[0], c[1:]) for c in
                    draft_score.check_aeo(fm, body, heads, cfg))

    def test_question_h2s_green(self):
        heads = [(2, "How much does it cost?"),
                 (2, "What is included?")]
        body = "## How much does it cost?\n\n" + "word " * 50
        self.assertEqual(
            self._aeo({}, body, heads)["question H2s"][0], "green")

    def test_question_h2s_none(self):
        heads = [(2, "Pricing details"), (2, "Our approach")]
        self.assertEqual(
            self._aeo({}, "x", heads)["question H2s"][0], "yellow")

    def test_answer_blocks_green(self):
        body = ("## How much?\n\n" + "word " * 50 + "\n\n"
                "## When?\n\n" + "word " * 55 + "\n")
        heads = [(2, "How much?"), (2, "When?")]
        self.assertEqual(
            self._aeo({}, body, heads)["answer blocks"][0], "green")

    def test_answer_blocks_thin(self):
        body = "## How much?\n\nToo short.\n"
        self.assertEqual(
            self._aeo({}, body, [(2, "How much?")])["answer blocks"][0],
            "yellow")

    def test_faq_present(self):
        body = "## FAQ\n\n**Q: How much?**\n\nA: Plenty.\n"
        self.assertEqual(
            self._aeo({}, body, [(2, "FAQ")])["FAQ section"][0], "green")

    def test_faq_missing(self):
        body = "## Pricing\n\nWords here.\n"
        self.assertEqual(
            self._aeo({}, body, [(2, "Pricing")])["FAQ section"][0],
            "yellow")

    def test_brand_entity_green(self):
        body = "Acme Bike Tours led this ride. Acme Bike Tours again.\n"
        self.assertEqual(
            self._aeo({}, body, [])["brand entity"][0], "green")

    def test_brand_entity_missing(self):
        body = "A guide led this ride.\n"
        self.assertEqual(
            self._aeo({}, body, [])["brand entity"][0], "yellow")

    def test_citable_numbers_green(self):
        body = "14 years, 400 tours, 3 routes.\n"
        self.assertEqual(
            self._aeo({}, body, [])["citable numbers"][0], "green")

    def test_citable_numbers_thin(self):
        body = "One tour was lovely.\n"
        self.assertEqual(
            self._aeo({}, body, [])["citable numbers"][0], "yellow")

    def test_freshness_recent(self):
        import datetime
        today = datetime.date.today().isoformat()
        self.assertEqual(
            self._aeo({"updated": today}, "x", [])["freshness"][0],
            "green")

    def test_freshness_stale(self):
        self.assertEqual(
            self._aeo({"updated": "2020-01-01"}, "x", [])["freshness"][0],
            "yellow")

    def test_freshness_missing(self):
        self.assertEqual(
            self._aeo({}, "x", [])["freshness"][0], "yellow")

    def test_brief_has_aeo_section(self):
        import keyword_miner
        orig_mine, orig_gsc = keyword_miner.mine, brief.gsc_related
        keyword_miner.mine = lambda seed, depth=2: []
        brief.gsc_related = lambda cfg, target: []
        try:
            cfg = {"name": "Test Brand", "repo": "/nonexistent",
                   "content_dir": "x", "content_route": "/guide/",
                   "site_url": "https://example.com",
                   "type_category_map": {"guide": "tips"},
                   "categories": {"tips": "Tips"}}
            out = brief.build_brief(cfg, "test topic", "guide")
        finally:
            keyword_miner.mine, brief.gsc_related = orig_mine, orig_gsc
        self.assertIn("## AEO", out)
        self.assertIn("updated:", out)


class TestAEOMap(unittest.TestCase):
    def test_is_question(self):
        import aeo_map
        self.assertTrue(aeo_map.is_question("how much does it cost"))
        self.assertTrue(aeo_map.is_question("what is included"))
        self.assertFalse(aeo_map.is_question("best bike tours"))
        self.assertFalse(aeo_map.is_question("austin bike tour guide"))

    def test_covering_entry_found(self):
        import aeo_map
        entries = [("austin-bike-tours",
                    {"austin", "bike", "tours"})]
        self.assertEqual(
            aeo_map.covering_entry(
                "what are the best austin bike tours?", entries),
            "austin-bike-tours")

    def test_covering_entry_gap(self):
        import aeo_map
        entries = [("austin-bike-tours",
                    {"austin", "bike", "tours"})]
        self.assertIsNone(
            aeo_map.covering_entry("how to choose a helmet?", entries))


class TestNapAudit(unittest.TestCase):
    def setUp(self):
        import nap_audit
        self.nap = nap_audit

    def test_normalize_phone(self):
        self.assertEqual(self.nap.normalize_phone("+1 (407) 555-0123"),
                         "4075550123")
        self.assertEqual(self.nap.normalize_phone("407.555.0123"),
                         "4075550123")
        self.assertEqual(self.nap.normalize_phone("not a phone"), "")

    def test_extract_phones_ignores_long_digit_runs(self):
        html = ('<form action="https://assets.mailerlite.com/jsonp/319759/'
                'forms/191180898656322832/subscribe"></form>'
                '<a href="tel:+14075550123">Call us</a>')
        self.assertEqual(self.nap.extract_phones(html), {"4075550123"})

    def test_extract_emails(self):
        html = '<a href="mailto:Hello@Example.com">mail</a>'
        self.assertEqual(self.nap.extract_emails(html), {"hello@example.com"})

    def test_business_nodes_from_graph(self):
        html = ('<script type="application/ld+json">{"@context": '
                '"https://schema.org", "@graph": ['
                '{"@type": "ProfessionalService", "name": "Acme"}, '
                '{"@type": "WebSite", "name": "Acme site"}]}</script>')
        docs = self.nap.extract_jsonld(html)
        nodes = list(self.nap.business_nodes(docs[0]))
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "Acme")

    def test_audit_all_ok(self):
        cfg = {"name": "Acme Studio",
               "local_seo": {"operating_model": "service_area",
                             "hide_address": True,
                             "service_areas": ["Orlando"],
                             "nap": {"phone": "+1 407-555-0123",
                                     "email": "hello@acme.test"}}}
        html = ('<script type="application/ld+json">{"@context": '
                '"https://schema.org", "@type": "ProfessionalService", '
                '"name": "Acme Studio"}</script>'
                '<a href="tel:4075550123">call</a> '
                '<a href="mailto:hello@acme.test">mail</a>')
        results = self.nap.audit_nap(cfg, {"homepage": html})
        self.assertTrue(all(s == "ok" for _, s, _ in results))

    def test_audit_phone_mismatch_warns(self):
        cfg = {"name": "Acme Studio",
               "local_seo": {"operating_model": "service_area",
                             "hide_address": True,
                             "service_areas": ["Orlando"],
                             "nap": {"phone": "+1 407-555-0123"}}}
        html = '<a href="tel:3215559999">call</a>'
        results = dict((f, s) for f, s, _ in
                       self.nap.audit_nap(cfg, {"homepage": html}))
        self.assertEqual(results["phone"], "warn")

    def test_audit_sab_street_address_warns(self):
        cfg = {"name": "Acme Studio",
               "local_seo": {"operating_model": "service_area",
                             "hide_address": True,
                             "service_areas": ["Orlando"]}}
        html = "<p>Visit us at 123 Main Street, Orlando FL</p>"
        results = dict((f, s) for f, s, _ in
                       self.nap.audit_nap(cfg, {"homepage": html}))
        self.assertEqual(results["address (hidden)"], "warn")

    def test_audit_missing_localbusiness_warns(self):
        cfg = {"name": "Acme Studio",
               "local_seo": {"operating_model": "service_area",
                             "hide_address": True,
                             "service_areas": ["Orlando"]}}
        html = "<p>hello</p>"
        results = dict((f, s) for f, s, _ in
                       self.nap.audit_nap(cfg, {"homepage": html}))
        self.assertEqual(results["LocalBusiness schema"], "warn")


class TestAssignImages(unittest.TestCase):
    CFG = {"image_scan_dirs": ["src/data"],
           "image_number_map": "src/data/photo-files.json",
           "image_number_pattern": r"photo\((\d+)\)"}

    def _repo_with_number_ref(self):
        repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, repo)
        os.makedirs(os.path.join(repo, "src", "data"))
        os.makedirs(os.path.join(repo, "src", "content", "guide"))
        with open(os.path.join(repo, "src", "data",
                               "photo-files.json"), "w") as f:
            json.dump({"47": "austin-bike-tour-test.webp"}, f)
        with open(os.path.join(repo, "src", "data", "photos.ts"), "w") as f:
            f.write("hero: photo(47),\n")
        return repo

    def test_photo_number_reference_counts_as_used(self):
        repo = self._repo_with_number_ref()
        used = assign_images.used_images(repo, ["src/content/guide"],
                                         self.CFG)
        self.assertIn("austin-bike-tour-test.webp", used)

    def test_number_refs_off_without_config(self):
        # No image_number_* config: by-number references are a site
        # opt-in, never a hardcoded scheme.
        repo = self._repo_with_number_ref()
        used = assign_images.used_images(repo, ["src/content/guide"])
        self.assertNotIn("austin-bike-tour-test.webp", used)

    def test_frontmatter_image_counts_as_used(self):
        repo = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(repo, "src", "content", "guide"))
            with open(os.path.join(
                    repo, "src", "content", "guide", "entry.md"), "w") as f:
                f.write('---\nimage: "/images/acme/website-photos/'
                        'austin-bike-tour-used.webp"\n---\n')
            used = assign_images.used_images(repo, ["src/content/guide"])
            self.assertIn("austin-bike-tour-used.webp", used)
        finally:
            shutil.rmtree(repo)

    def test_stopwords_come_from_config(self):
        cfg = {"niche_generic_words": ["tour", "tours"],
               "geo_terms": ["austin", "lake travis"]}
        stops = assign_images.stopwords_for(cfg)
        self.assertIn("austin", stops)       # geo term
        self.assertIn("travis", stops)       # geo term word
        self.assertIn("tours", stops)        # niche word
        self.assertIn("the", stops)          # universal filler
        self.assertNotIn("sunset", stops)
        words = assign_images.topic_words("austin sunset bike tours", stops)
        self.assertEqual(words, {"sunset", "bike"})


class TestGenericWords(unittest.TestCase):
    def test_universal_has_no_niche_words(self):
        for w in ("wedding", "venue", "photographer", "plumber", "tour"):
            self.assertNotIn(w, site_config.UNIVERSAL_GENERIC_WORDS)

    def test_default_is_universal_only(self):
        self.assertEqual(site_config.generic_words({}),
                         site_config.UNIVERSAL_GENERIC_WORDS)

    def test_site_words_merge_and_lowercase(self):
        cfg = {"niche_generic_words": ["Plumber", "PLUMBING"]}
        self.assertEqual(site_config.generic_words(cfg),
                         site_config.UNIVERSAL_GENERIC_WORDS
                         | {"plumber", "plumbing"})

    def test_bad_type_fails_loud(self):
        with self.assertRaises(SystemExit):
            site_config.generic_words({"niche_generic_words": "plumber"})

    def test_full_niche_set_merges_to_expected(self):
        # A niche's declared words + the universal base must reproduce
        # the set the engine historically used for that niche.
        cfg = {"niche_generic_words": [
            "wedding", "weddings", "venue", "venues", "photographer",
            "photographers", "photography", "video", "videographer",
            "videography", "planning", "planner"]}
        self.assertEqual(site_config.generic_words(cfg), {
            "wedding", "weddings", "venue", "venues", "photographer",
            "photographers", "photography", "photo", "photos", "video",
            "videographer", "videography", "planning", "planner",
            "guide", "guides", "tips", "ideas"})


if __name__ == "__main__":
    unittest.main()


class PlaybookUpdatesTest(unittest.TestCase):
    CFG = {"name": "acme", "site_url": "https://acme.com/", "geo_terms": ["Austin"],
           "local_seo": {"operating_model": "service_area", "hide_address": True,
                         "nap": {"name": "acme", "phone": "(512) 555-0100"},
                         "service_areas": ["Austin", "Round Rock"]}}

    def test_internal_links_counted_from_body(self):
        body = "See [services](/services/) and [contact](/contact/) and [x](https://acme.com/faq)."
        text = draft_score.plain_text(body)
        res = {c[0]: c for c in draft_score.check_seo({}, text, body, [], "kw", self.CFG)}
        self.assertEqual(res["internal links"][1], "green")
        self.assertIn("3 internal", res["internal links"][2])

    def test_image_links_not_internal(self):
        body = "![a](/img/a.jpg) [one](/one/)"
        res = {c[0]: c for c in draft_score.check_seo({}, "", body, [], "kw", self.CFG)}
        self.assertIn("only 1", res["internal links"][2])

    def test_review_compliance(self):
        for bad in ["Get 10% off your next visit for a five-star review.",
                    "Leave us a 5-star review on Google!",
                    "If you were happy, please leave a review.",
                    "Leave a review on Yelp to help us."]:
            self.assertEqual(draft_score.check_review_compliance(bad)[0][1], "red", bad)
        ok = "Would you be willing to share an honest review of your experience?"
        self.assertEqual(draft_score.check_review_compliance(ok)[0][1], "green")

    def test_validate_local_seo(self):
        v = site_config.validate_local_seo
        self.assertEqual(v(None), [])
        self.assertEqual(v(self.CFG["local_seo"]), [])
        self.assertTrue(v({"operating_model": "office"}))
        self.assertTrue(v({"operating_model": "service_area", "hide_address": True,
                           "service_areas": [f"c{i}" for i in range(21)]}))
        self.assertTrue(v({"operating_model": "service_area", "hide_address": False,
                           "service_areas": ["a"]}))
        self.assertTrue(v({"operating_model": "storefront", "hide_address": True}))

    def test_shipped_configs_valid_and_dashless(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for slug in site_config.list_sites():
            site_config.load(slug)
        paths = [os.path.join("sites", f"{slug}.yaml")
                 for slug in site_config.list_sites()]
        paths.append("skill/references/site-config-template.yaml")
        for p in paths:
            with open(os.path.join(root, p)) as f:
                s = f.read()
            self.assertNotIn("\u2014", s, p)
            self.assertNotIn("\u2013", s, p)

    def test_doorway_guard(self):
        self.assertTrue(brief.local_page_guard(self.CFG, "plumber websites round rock"))
        self.assertEqual(brief.local_page_guard(self.CFG, "plumber website cost"), [])
        self.assertTrue(any("geo" in l for l in brief.local_page_guard(self.CFG, "austin plumber")))

    def test_local_schema_check(self):
        import local_schema_check as lsc
        html = ('<script type="application/ld+json">{"@type":"ProfessionalService","name":"acme",'
                '"telephone":"+1-512-555-0100","address":{"streetAddress":"1 Main St"},'
                '"geo":{"latitude":1}}</script>')
        res = {c[0]: c[1] for c in lsc.check(lsc.extract_jsonld(html), self.CFG)}
        self.assertEqual(res["telephone"], "green")
        self.assertEqual(res["hidden address (SAB)"], "red")
        html2 = '<script type="application/ld+json">{"@graph":[{"@type":"Organization","name":"acme","areaServed":"Austin"}]}</script>'
        res2 = {c[0]: c[1] for c in lsc.check(lsc.extract_jsonld(html2), self.CFG)}
        self.assertEqual(res2["telephone"], "red")
        self.assertEqual(res2["hidden address (SAB)"], "green")


def _brief_front_matter(cfg, target="wedding inquiry reply time", kind=None):
    """Build a brief offline and return its front-matter block, parsed."""
    import yaml
    import keyword_miner
    orig = keyword_miner.mine
    keyword_miner.mine = lambda t: []
    try:
        out = brief.build_brief(cfg, target, kind or next(iter(
            cfg["type_category_map"])))
    finally:
        keyword_miner.mine = orig
    block = out.split("## Front matter\n```md\n---\n", 1)[1].split(
        "\n---\n```", 1)[0]
    return yaml.safe_load(block)


class TestFrontMatterTemplate(unittest.TestCase):
    CFG = {"name": "T", "slug": "t", "site_url": "https://x.com/",
           "content_route": "/blog/", "repo": tempfile.gettempdir(),
           "content_dir": "nope", "type_category_map": {"guide": "Pricing"},
           "title_templates": ["{title}"], "categories": {"Pricing": "p"}}

    def test_default_keeps_keywords_and_category(self):
        fm = _brief_front_matter(dict(self.CFG))
        self.assertEqual(fm["categorySlug"], "Pricing")
        self.assertEqual(fm["keywords"], ["wedding inquiry reply time"])

    def test_site_template_replaces_fields(self):
        cfg = dict(self.CFG, front_matter_template=(
            'title: "{title}"\ndate: "{date}"\n'
            "image: /blog/{slug}/cover.webp\n"
            'imageAlt: "{image_alt}"\ntags: [{category}]'))
        fm = _brief_front_matter(cfg)
        self.assertEqual(set(fm), {"title", "date", "image", "imageAlt",
                                   "tags"})
        self.assertEqual(fm["image"],
                         "/blog/wedding-inquiry-reply-time/cover.webp")
        self.assertEqual(fm["tags"], ["Pricing"])

    def test_bad_placeholder_names_the_key(self):
        cfg = dict(self.CFG, front_matter_template="x: {nope}")
        with self.assertRaises(SystemExit) as cm:
            _brief_front_matter(cfg)
        self.assertIn("front_matter_template", str(cm.exception))


class TestExistingEntries(unittest.TestCase):
    def test_readme_is_not_an_entry(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        for name in ("README.md", "a-post.md"):
            open(os.path.join(d, name), "w").close()
        cfg = {"repo": d, "content_dir": "."}
        self.assertEqual(brief.existing_entries(cfg), ["a-post"])


class TestFrontMatterFaq(unittest.TestCase):
    def test_faq_list_in_front_matter_counts(self):
        path = os.path.join(tempfile.mkdtemp(), "d.md")
        self.addCleanup(shutil.rmtree, os.path.dirname(path))
        with open(path, "w") as f:
            f.write("---\ntitle: T\nfaq:\n  - question: Why?\n"
                    "    answer: Because.\n---\n\n## Intro\n\nText.\n")
        fm, body = draft_score.parse_draft(path)
        checks = dict((c[0], c[1]) for c in draft_score.check_aeo(
            fm, body, draft_score.headings(body), {"name": "T"}))
        self.assertEqual(checks["FAQ section"], "green")

