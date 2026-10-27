#!/usr/bin/env python3
"""Tests for intake.py. Run: python3 automation/test_intake.py"""
import pathlib
import tempfile
import unittest
from datetime import date

from intake import to_listing
from check_listing import check

BODY = """### 作品名

こんだてAI

### 一言説明

冷蔵庫の写真から、今夜の献立を3つ提案

### 説明

冷蔵庫の中を撮ると献立を出します。

### 使える場所

Web

### リンク

https://example.com/kondate

### 分類

暮らし

### つくるのに使ったAI（1つ以上）

- [x] Claude Code
- [ ] Cursor
- [x] その他

### 作り手の表示名

ゆう

### 確認

- [x] 自分（または自分のチーム）がつくった作品です
"""


class IntakeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.apps = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_form_becomes_a_passing_listing(self):
        listing = to_listing(42, BODY, date(2026, 10, 26), self.apps)
        self.assertEqual(listing["id"], "issue-42")
        self.assertEqual(listing["platform"], "web")
        self.assertEqual(listing["category"], "lifestyle")
        self.assertEqual(listing["ai_tools"], ["Claude Code", "その他"])
        self.assertEqual(listing["launch_date"], "2026-10-27")
        self.assertEqual(check(listing)[0], [])

    def test_full_day_moves_to_the_next_day(self):
        for i in range(10):
            (self.apps / f"x{i}.json").write_text('{"launch_date": "2026-10-27"}')
        self.assertEqual(to_listing(1, BODY, date(2026, 10, 26), self.apps)["launch_date"], "2026-10-28")

    def test_unsafe_link_and_markup_are_rejected(self):
        body = BODY.replace("https://example.com/kondate", "https://bit.ly/x").replace("こんだてAI", "<img src=x>")
        errors = check(to_listing(7, body, date(2026, 10, 26), self.apps))[0]
        self.assertTrue(any("短縮" in e for e in errors))
        self.assertTrue(any("<" in e for e in errors))

    def test_unknown_values_are_dropped_not_trusted(self):
        body = BODY.replace("Web\n", "Windows\n").replace("- [x] Claude Code", "- [x] EvilTool")
        listing = to_listing(8, body, date(2026, 10, 26), self.apps)
        self.assertEqual(listing["platform"], "")
        self.assertNotIn("EvilTool", listing["ai_tools"])


if __name__ == "__main__":
    unittest.main()
