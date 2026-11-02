"""Offline tests for open-seo-crawler's Flask routing (no server, no network)."""
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "open-seo-crawler"))
import app as crawler  # noqa: E402


class CrawlerRoutes(unittest.TestCase):
    def test_every_view_takes_only_its_url_arguments(self):
        # A route decorator left above the wrong def (e.g. a helper inserted
        # between decorator and handler) binds a function Flask can't call.
        for rule in crawler.app.url_map.iter_rules():
            view = crawler.app.view_functions[rule.endpoint]
            required = {
                p.name for p in inspect.signature(view).parameters.values()
                if p.default is p.empty
                and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
            }
            self.assertEqual(
                required - set(rule.arguments), set(),
                f"{rule.rule} is bound to {view.__name__}, which needs "
                f"arguments the URL never supplies")

    def test_sitemap_analyse_is_routed(self):
        adapter = crawler.app.url_map.bind("localhost")
        endpoint, _ = adapter.match("/sitemap-analyse", method="POST")
        self.assertIs(crawler.app.view_functions[endpoint],
                      crawler.sitemap_analyse)


if __name__ == "__main__":
    unittest.main()
