#!/usr/bin/env python3
"""Tests for x_daily_post.py. Run: python3 automation/test_x_daily_post.py"""
import unittest
from datetime import date

from x_daily_post import MAX_WEIGHT, compose, weight

DAY = date(2026, 10, 19)


def app(i, sample=False):
    return {"id": f"a{i}", "name": f"アプリ{i}号", "tagline": "冷蔵庫の写真から今夜の献立を三つ提案するアプリ",
            "launch_date": DAY.isoformat(), "sample": sample}


class ComposeTest(unittest.TestCase):
    def test_nothing_to_post(self):
        self.assertIsNone(compose([], DAY, "https://example.jp"))

    def test_samples_are_never_posted(self):
        self.assertIsNone(compose([app(1, sample=True)], DAY, "https://example.jp"))

    def test_fits_the_length_limit_even_with_many_debuts(self):
        for n in (1, 3, 10, 40):
            with self.subTest(n=n):
                text = compose([app(i) for i in range(n)], DAY, "https://example.jp")
                self.assertLessEqual(weight(text), MAX_WEIGHT)
                self.assertIn("https://example.jp/", text)

    def test_weight_counts_cjk_double_and_urls_as_23(self):
        self.assertEqual(weight("あい"), 4)
        self.assertEqual(weight("x https://example.jp/very/long/path"), 1 + 1 + 23)


if __name__ == "__main__":
    unittest.main()
