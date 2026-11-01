import os, unittest
from unittest import mock
import site_config


class ExpandPathTest(unittest.TestCase):
    def test_env_var_set(self):
        with mock.patch.dict(os.environ, {"SITE_CHECKOUT": "/tmp/x"}):
            self.assertEqual(site_config.expand_path("${SITE_CHECKOUT:-/d}/apps/site"), "/tmp/x/apps/site")
            self.assertEqual(site_config.expand_path("$SITE_CHECKOUT/a"), "/tmp/x/a")

    def test_default_when_unset(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SITE_CHECKOUT", None)
            self.assertEqual(site_config.expand_path("${SITE_CHECKOUT:-/d}/apps/site"), "/d/apps/site")

    def test_unset_without_default_fails_clearly(self):
        os.environ.pop("WRTR_NOPE", None)
        with self.assertRaises(SystemExit) as cm:
            site_config.expand_path("$WRTR_NOPE/x", "repo")
        self.assertIn("WRTR_NOPE", str(cm.exception))

    def test_febuslabs_repo_expanded(self):
        with mock.patch.dict(os.environ, {"SITE_CHECKOUT": "/tmp/mono"}):
            self.assertEqual(site_config.load("febuslabs")["repo"], "/tmp/mono/apps/site")
