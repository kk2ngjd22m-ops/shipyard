#!/usr/bin/env python3
"""Post today's debuts to the Shipyard X account (requirement FR-AUTO2).

Only our own account, only our own listings, one post per run: allowed under
X's automation rules (the account must carry X's "Automated" label). It never
searches, replies, likes, follows or sends DMs (prohibited for unsolicited use).

Default is a dry run that prints the post. Posting needs --post and these
environment variables (an X app with OAuth 1.0a user context, "Read and write"):
    X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
Set a monthly spending cap in the X developer console (COST-1).

    python3 automation/x_daily_post.py --today 2026-10-19 --site-url https://example.jp
    python3 automation/x_daily_post.py --post --site-url https://<domain>
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import sys
import time
import unicodedata
import urllib.request
from datetime import date
from urllib.parse import quote

APPS = pathlib.Path(__file__).resolve().parent.parent / "site" / "apps"
ENDPOINT = "https://api.x.com/2/tweets"
MAX_WEIGHT = 280      # X counts most CJK characters as 2 and every URL as 23
URL_WEIGHT = 23


def weight(text: str) -> int:
    """Approximate X's weighted length (CJK and other wide characters count 2)."""
    total = 0
    for word in text.split(" "):
        if word.startswith("https://"):
            total += URL_WEIGHT
        else:
            total += sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in word)
    return total + text.count(" ")


def compose(apps: list[dict], day: date, site_url: str) -> str | None:
    """One post listing today's debuts; trims the list to fit the length limit."""
    todays = sorted((a for a in apps if a["launch_date"] == day.isoformat() and not a.get("sample")),
                    key=lambda a: a["name"])
    if not todays:
        return None
    head = f"本日のデビュー（{day.month}/{day.day}）"
    tail = f"\n\n一覧 {site_url.rstrip('/')}/ #AI個人開発"
    lines: list[str] = []
    for a in todays:
        candidate = "\n".join([head, *lines, f"・{a['name']} — {a['tagline']}"]) + tail
        if weight(candidate) > MAX_WEIGHT:
            rest = len(todays) - len(lines)
            lines.append(f"ほか{rest}件")
            break
        lines.append(f"・{a['name']} — {a['tagline']}")
    text = "\n".join([head, *lines]) + tail
    while weight(text) > MAX_WEIGHT and len(lines) > 1:  # "ほか◯件" may still overflow
        lines.pop(-2)
        text = "\n".join([head, *lines]) + tail
    return text


def oauth1_header(method: str, url: str, keys: dict) -> str:
    params = {
        "oauth_consumer_key": keys["X_API_KEY"],
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": keys["X_ACCESS_TOKEN"],
        "oauth_version": "1.0",
    }
    enc = lambda s: quote(str(s), safe="~-._")
    base = "&".join([method, enc(url), enc("&".join(f"{enc(k)}={enc(v)}" for k, v in sorted(params.items())))])
    signing_key = f"{enc(keys['X_API_SECRET'])}&{enc(keys['X_ACCESS_SECRET'])}"
    params["oauth_signature"] = base64.b64encode(hmac.new(signing_key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{enc(k)}="{enc(v)}"' for k, v in sorted(params.items()))


def post(text: str) -> None:
    names = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"環境変数がない: {', '.join(missing)}")
    keys = {n: os.environ[n] for n in names}
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps({"text": text}).encode(), method="POST",
        headers={"Authorization": oauth1_header("POST", ENDPOINT, keys), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        print(f"投稿しました（HTTP {resp.status}）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", type=date.fromisoformat, default=date.today())
    ap.add_argument("--site-url", required=True)
    ap.add_argument("--post", action="store_true", help="実際に投稿する（指定しなければ表示だけ）")
    ap.add_argument("--include-samples", action="store_true", help="試験用: サンプルも対象にする（投稿はしない）")
    args = ap.parse_args()
    apps = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(APPS.glob("*.json"))]
    if args.include_samples:
        if args.post:
            sys.exit("サンプルは投稿しない")
        apps = [{**a, "sample": False} for a in apps]
    text = compose(apps, args.today, args.site_url)
    if text is None:
        print("今日のデビューはないので、投稿しない")
        sys.exit(0)
    print(text)
    print(f"\n（長さ {weight(text)} / {MAX_WEIGHT}）")
    if args.post:
        post(text)
