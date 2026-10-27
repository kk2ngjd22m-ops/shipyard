#!/usr/bin/env python3
"""Turn a listing request (GitHub issue form) into site/apps/<id>.json (FR-AUTO1).

The issue body is untrusted text. It is read from a file or stdin, parsed as
plain text, checked with site/check_listing.py, and written as JSON only if it
passes. It is never executed, evaluated or pasted into a shell command.

    python3 automation/intake.py --issue 123 --body-file body.md [--write]
Exit codes: 0 = OK (file written with --write), 1 = errors (message on stdout).
"""
import argparse
import json
import pathlib
import re
import sys
from datetime import date, timedelta

SITE = pathlib.Path(__file__).resolve().parent.parent / "site"
sys.path.insert(0, str(SITE))
from check_listing import AI_TOOLS, CATEGORIES, PLATFORMS, check  # noqa: E402

DAILY_FREE_SLOTS = 10
PLATFORM_BY_LABEL = {v: k for k, v in PLATFORMS.items()}
CATEGORY_BY_LABEL = {v: k for k, v in CATEGORIES.items()}
FIELDS = {
    "作品名": "name", "一言説明": "tagline", "説明": "description", "使える場所": "platform",
    "リンク": "url", "分類": "category", "つくるのに使ったAI（1つ以上）": "ai_tools", "作り手の表示名": "maker_name",
}


def parse_sections(body: str) -> dict[str, str]:
    """GitHub issue forms render as '### Label' followed by the answer."""
    sections, current = {}, None
    for line in body.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            current = m.group(1)
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def next_free_day(start: date, apps_dir: pathlib.Path) -> date:
    counts: dict[str, int] = {}
    for p in apps_dir.glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8")).get("launch_date", "")
        counts[d] = counts.get(d, 0) + 1
    day = start
    while counts.get(day.isoformat(), 0) >= DAILY_FREE_SLOTS:
        day += timedelta(days=1)
    return day


def to_listing(issue: int, body: str, today: date, apps_dir: pathlib.Path) -> dict:
    s = {FIELDS[k]: v for k, v in parse_sections(body).items() if k in FIELDS}
    tools = [t for t in re.findall(r"^- \[[xX]\] (.+)$", s.get("ai_tools", ""), re.M) if t.strip() in AI_TOOLS]
    return {
        "id": f"issue-{issue}",
        "name": s.get("name", "").strip(),
        "tagline": s.get("tagline", "").strip(),
        "description": s.get("description", "").strip(),
        "platform": PLATFORM_BY_LABEL.get(s.get("platform", "").strip(), ""),
        "category": CATEGORY_BY_LABEL.get(s.get("category", "").strip(), ""),
        "ai_tools": [t.strip() for t in tools],
        "maker_name": s.get("maker_name", "").strip(),
        "url": s.get("url", "").strip(),
        "launch_date": next_free_day(today + timedelta(days=1), apps_dir).isoformat(),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", type=int, required=True)
    ap.add_argument("--body-file", help="issue body (default: stdin)")
    ap.add_argument("--today", type=date.fromisoformat, default=date.today())
    ap.add_argument("--write", action="store_true", help="write site/apps/issue-<n>.json when the checks pass")
    args = ap.parse_args()
    body = pathlib.Path(args.body_file).read_text(encoding="utf-8") if args.body_file else sys.stdin.read()
    if len(body) > 20_000:
        print("申請の本文が長すぎます"); sys.exit(1)
    listing = to_listing(args.issue, body, args.today, SITE / "apps")
    path = SITE / "apps" / f"{listing['id']}.json"
    errors, warnings = check(listing, str(path))
    if errors:
        print("自動チェックで直してほしい点があります:\n" + "\n".join(f"- {e}" for e in errors))
        sys.exit(1)
    print(f"自動チェックを通りました。公開予定日: {listing['launch_date']}（運営の承認後）")
    for w in warnings:
        print(f"- 運営が確認: {w}")
    if args.write:
        path.write_text(json.dumps(listing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
