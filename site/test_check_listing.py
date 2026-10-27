#!/usr/bin/env python3
"""Tests for check_listing.py. Run: python3 site/test_check_listing.py"""
import unittest

from check_listing import check

BASE = dict(
    id="test-app", name="テスト", tagline="t", description="d", platform="web",
    category="fun", ai_tools=["Cursor"], maker_name="m",
    url="https://example.com/x", launch_date="2026-10-19", sample=True,
)


def errors(**override):
    return check({**BASE, **override})[0]


class CheckListingTest(unittest.TestCase):
    def test_valid_listing_passes(self):
        self.assertEqual(errors(), [])

    def test_blocks_unsafe_links(self):
        for url in [
            "http://example.com",            # not https
            "https://bit.ly/abc",            # shortener hides the destination
            "https://example.com/app.apk",   # direct file download
            "https://192.168.0.1/x",         # IP address
            "https://user:pw@example.com/",  # credentials in URL
        ]:
            with self.subTest(url=url):
                self.assertTrue(errors(url=url))

    def test_store_apps_must_link_to_official_store(self):
        self.assertTrue(errors(platform="ios", url="https://example.com/app"))
        self.assertEqual(errors(platform="ios", url="https://apps.apple.com/jp/app/id1"), [])
        self.assertTrue(errors(platform="android", url="https://example.com/app"))

    def test_rejects_markup_and_unknown_values(self):
        self.assertTrue(errors(name="<script>"))
        self.assertTrue(errors(ai_tools=["ChatGPT"]))
        self.assertTrue(errors(category="casino"))

    def test_out_of_scope_words_go_to_review(self):
        errs, warns = check({**BASE, "tagline": "副業で月30万稼げる"})
        self.assertEqual(errs, [])
        self.assertTrue(warns)


if __name__ == "__main__":
    unittest.main()
