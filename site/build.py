#!/usr/bin/env python3
"""Build the static launch board from site/apps/*.json into site/dist/.

No server, no database, no JavaScript (requirements SEC-1, SEC-5).

    python3 site/build.py                     # today = system date
    python3 site/build.py --today 2026-10-19  # fixed date (reproducible)
    python3 site/build.py --artifact          # index.html without <head>, for a claude.ai preview
"""
import argparse
import hashlib
import html
import json
import pathlib
import shutil
import sys
from urllib.parse import urlencode
from datetime import date, timedelta

from check_listing import AI_TOOLS, CATEGORIES, PLATFORMS, load_all

HERE = pathlib.Path(__file__).resolve().parent
SITE_NAME = "Shipyard"
TAGLINE = "AIでつくったアプリの、デビューの場所"
DAILY_FREE_SLOTS = 10
SHOW_PROTO_BANNER = True  # turned off by --production

e = html.escape


def week_id(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_label(wid: str) -> str:
    y, w = wid.split("-W")
    monday = date.fromisocalendar(int(y), int(w), 1)
    sunday = monday + timedelta(days=6)
    return f"{monday.month}月{monday.day}日〜{sunday.month}月{sunday.day}日"


def jdate(d: date) -> str:
    return f"{d.month}月{d.day}日"


def tile_class(text: str) -> str:
    # One of 12 colour classes in style.css (inline styles are blocked by the CSP).
    return f"h{int(hashlib.sha256(text.encode()).hexdigest()[:4], 16) % 12}"


def page(title: str, body: str, *, artifact_index: bool = False, desc: str = TAGLINE) -> str:
    head = (
        f"<title>{e(title)}</title>\n"
        f'<meta name="description" content="{e(desc)}">\n'
        '<link rel="stylesheet" href="style.css">\n'
    )
    nav = (
        '<header class="top"><div class="in">'
        f'<a class="brand" href="index.html"><span class="mark" aria-hidden="true"></span>{SITE_NAME}</a>'
        '<nav aria-label="メイン"><a href="index.html">新着</a><a href="weeks.html">週ごと</a>'
        '<a class="cta" href="submit.html">掲載する</a></nav></div></header>'
        + ('<div class="proto"><div class="in">試作版 · 掲載されている作品はすべて架空のサンプルです</div></div>'
           if SHOW_PROTO_BANNER else "")
    )
    foot = (
        '<footer class="foot"><div class="in">'
        f'<p>{SITE_NAME}（仮称） · {e(TAGLINE)}</p>'
        '<p><a href="about.html">この場所について・規約</a> · <a href="feed.xml">RSS</a></p>'
        "</div></footer>"
    )
    if artifact_index:
        return head + nav + body + foot
    return (
        '<!doctype html>\n<html lang="ja"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        + head + "</head><body>\n" + nav + body + foot + "\n</body></html>\n"
    )


def tile(app: dict) -> str:
    return f'<span class="tile {tile_class(app["id"])}" aria-hidden="true">{e(app["name"][0])}</span>'


def tags(app: dict) -> str:
    items = [PLATFORMS[app["platform"]], CATEGORIES[app["category"]], *app["ai_tools"]]
    return "".join(f'<span class="tag">{e(t)}</span>' for t in items)


def row(app: dict, *, pr: bool = False) -> str:
    badge = '<span class="pr">PR</span>' if pr else ""
    sample = '<span class="sample">サンプル</span>' if app.get("sample") else ""
    return (
        f'<li><a class="row" href="app-{e(app["id"])}.html">{tile(app)}'
        f'<span class="txt"><span class="name">{e(app["name"])}{badge}{sample}</span>'
        f'<span class="line">{e(app["tagline"])}</span>'
        f'<span class="tags">{tags(app)}</span></span>'
        f'<span class="by">{e(app["maker_name"])}</span></a></li>'
    )


def section(title: str, apps: list[dict], *, empty: str, note: str = "", sid: str = "", eyebrow: str = "") -> str:
    idattr = f' id="{sid}"' if sid else ""
    eb = f'<span class="eyebrow">{e(eyebrow)}</span>' if eyebrow else ""
    head = f'<div class="sec-h"><h2>{eb}{e(title)}</h2>{f"<p>{e(note)}</p>" if note else ""}</div>'
    if not apps:
        return f'<section class="sec"{idattr}>{head}<p class="empty">{e(empty)}</p></section>'
    return f'<section class="sec"{idattr}>{head}<ol class="rows">{"".join(row(a) for a in apps)}</ol></section>'


def board(apps: list[dict], today: date, total: int) -> str:
    """The departure board in the hero: today's debuts (or the latest ones)."""
    showing_today = bool(apps)
    title = f"本日の出航　{jdate(today)}" if showing_today else "最近の出航"
    rows = "".join(
        f'<li><a href="app-{e(a["id"])}.html">'
        f'<span class="b-no">{i:02d}</span>'
        f'<span class="b-name">{e(a["name"])}</span>'
        f'<span class="b-to">{e(PLATFORMS[a["platform"]])}</span>'
        f'<span class="b-st">{"本日" if a["launch_date"] == today.isoformat() else e(jdate(date.fromisoformat(a["launch_date"])))}</span>'
        "</a></li>"
        for i, a in enumerate(apps, 1)
    )
    return (
        '<aside class="board" aria-label="今日のデビュー一覧">'
        f'<div class="b-head"><span>{e(title)}</span><span class="b-live">運航中</span></div>'
        '<div class="b-cols" aria-hidden="true"><span>便</span><span>作品</span><span>行き先</span><span>状況</span></div>'
        + (f'<ol class="b-rows">{rows}</ol>' if rows else '<p class="b-empty">まもなく最初の作品が出航します</p>')
        + f'<div class="b-foot">掲載 {total} 件 · 毎朝更新</div>'
        "</aside>"
    )


def share_link(app: dict, site_url: str) -> str:
    """A plain link to X's post composer, pre-filled for the maker. No script, no API, no cost."""
    text = f"{app['name']}を Shipyard でデビューさせました！\n{app['tagline']}"
    url = f"{site_url.rstrip('/')}/app-{app['id']}.html"
    return "https://x.com/intent/post?" + urlencode({"text": text, "url": url, "hashtags": "AI個人開発"})


def build(today: date, artifact: bool, site_url: str | None = None, *, production: bool = False,
          submit_url: str | None = None, contact_url: str | None = None, paid: bool = False) -> None:
    global SHOW_PROTO_BANNER
    SHOW_PROTO_BANNER = not production
    listings, problems = load_all(HERE / "apps")
    blocking = {k: v for k, v in problems.items() if v[0]}
    if blocking:
        for name, (errs, _) in blocking.items():
            print(f"[NG] {name}: {'; '.join(errs)}", file=sys.stderr)
        sys.exit("自動チェックを通らない掲載があるため、公開をやめました")
    if production:
        samples = [a["id"] for a in listings if a.get("sample")]
        if samples:
            sys.exit(f"本番にサンプルが残っているため、公開をやめました: {', '.join(samples)}")
        for flag, value in (("--site-url", site_url), ("--submit-url", submit_url), ("--contact-url", contact_url)):
            if not value or not value.startswith("https://"):
                sys.exit(f"本番では {flag} に https の URL が必要です")

    live = sorted(
        (a for a in listings if date.fromisoformat(a["launch_date"]) <= today),
        key=lambda a: (a["launch_date"], a["name"]),
        reverse=True,
    )
    out = HERE / "dist"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    shutil.copy(HERE / "static" / "style.css", out / "style.css")
    shutil.copy(HERE / "_headers", out / "_headers")

    this_week = week_id(today)
    featured = [a for a in live if a.get("featured_week") == this_week]
    todays = [a for a in live if a["launch_date"] == today.isoformat()]
    recent = [a for a in live if today - timedelta(days=6) <= date.fromisoformat(a["launch_date"]) < today]

    pr_block = ""
    if featured:
        pr_block = (
            '<section class="sec feat"><div class="sec-h"><h2><span class="eyebrow">PR</span>今週の注目</h2>'
            "<p>作り手が購入した掲載枠です</p></div>"
            f'<ol class="rows">{"".join(row(a, pr=True) for a in featured)}</ol></section>'
        )
    hero = (
        '<section class="hero"><div class="in hero-grid">'
        '<div class="hero-copy">'
        '<p class="kicker">AI個人開発のローンチ掲示板</p>'
        "<h1><span>AIでつくった</span><span>アプリの、</span><br><span>デビューの場所。</span></h1>"
        "<p>個人がAIを使ってつくったアプリやWebサービスが、毎朝ここから出航します。"
        "気になったら使ってみて、作り手に感想を届けてください。</p>"
        '<div class="hero-cta"><a class="btn primary" href="#today">今日の新作を見る</a>'
        '<a class="btn" href="submit.html">作品を載せる（無料）</a></div>'
        '<p class="meta">掲載はすべて、公式ストアか公式サイトへのリンクです</p>'
        "</div>"
        + board(todays[:6] or live[:6], today, len(live))
        + "</div></section>"
    )
    body = (
        hero + '<main class="in main">' + pr_block
        + section(f"今日のデビュー", todays, empty="今日の新作はまだありません。", sid="today", eyebrow=jdate(today), note=f"{len(todays)} 件")
        + section("この1週間", recent, empty="この1週間の新作はありません。", sid="week", eyebrow="過去7日", note=f"{len(recent)} 件")
        + "</main>"
    )
    (out / "index.html").write_text(page(f"{SITE_NAME} — {TAGLINE}", body, artifact_index=artifact), encoding="utf-8")

    for a in live:
        d = date.fromisoformat(a["launch_date"])
        is_pr = a.get("featured_week") == this_week
        if a.get("sample"):
            go = '<p class="go-note">これは架空のサンプルなので、リンク先はありません。</p>'
        else:
            go = (
                f'<a class="go" href="{e(a["url"])}" rel="noopener noreferrer nofollow ugc" target="_blank">'
                f'{e(PLATFORMS[a["platform"]])}で開く（外部サイト）</a>'
                '<p class="go-note">Shipyard の外のサイトに移動します。掲載は公式ストアか公式サイトのリンクだけです。'
                "ファイルを直接ダウンロードさせるリンクは載せていません。</p>"
            )
        detail = (
            '<main class="in main detail">'
            f'<p class="crumb"><a href="index.html">新着</a> / <a href="week-{e(week_id(d))}.html">{e(week_label(week_id(d)))}</a></p>'
            f'<div class="d-head">{tile(a)}<div><h1>{e(a["name"])}'
            f'{"<span class=pr>PR</span>" if is_pr else ""}{"<span class=sample>サンプル</span>" if a.get("sample") else ""}</h1>'
            f'<p class="line">{e(a["tagline"])}</p></div></div>'
            f'<p class="desc">{e(a["description"])}</p>'
            '<section class="pass" aria-label="作品の情報">'
            f'<div class="pass-top"><span>出航記録</span><span class="pass-id">{e(a["id"].upper())}</span></div>'
            '<dl class="facts">'
            f"<div><dt>出航日</dt><dd>{jdate(d)}</dd></div>"
            f"<div><dt>行き先</dt><dd>{e(PLATFORMS[a['platform']])}</dd></div>"
            f"<div><dt>作り手</dt><dd>{e(a['maker_name'])}</dd></div>"
            f"<div><dt>分類</dt><dd>{e(CATEGORIES[a['category']])}</dd></div>"
            f"<div class=\"wide\"><dt>つくるのに使ったAI</dt><dd>{e('、'.join(a['ai_tools']))}</dd></div>"
            "</dl></section>"
            f'<div class="go-box">{go}</div>'
            + (
                '<div class="share"><p>この作品の作り手ですか？ 掲載ページをシェアして、最初の利用者を集めましょう。</p>'
                f'<a class="btn" href="{e(share_link(a, site_url))}" target="_blank" rel="noopener noreferrer">Xでシェアする</a></div>'
                if site_url and not a.get("sample") else ""
            )
            + '<p class="report">問題のある掲載を見つけたら、<a href="about.html#report">通報の方法</a>をご覧ください。</p>'
            "</main>"
        )
        (out / f"app-{a['id']}.html").write_text(page(f"{a['name']} — {SITE_NAME}", detail, desc=a["tagline"]), encoding="utf-8")

    weeks: dict[str, list[dict]] = {}
    for a in live:
        weeks.setdefault(week_id(date.fromisoformat(a["launch_date"])), []).append(a)
    for wid, apps in weeks.items():
        body = '<main class="in main">' + section(f"{week_label(wid)}のデビュー", apps, empty="", note=f"{len(apps)} 件") + "</main>"
        (out / f"week-{wid}.html").write_text(page(f"{week_label(wid)} — {SITE_NAME}", body), encoding="utf-8")
    week_list = "".join(
        f'<li><a class="wk" href="week-{e(w)}.html"><span>{e(week_label(w))}</span><span class="n">{len(weeks[w])} 件</span></a></li>'
        for w in sorted(weeks, reverse=True)
    )
    (out / "weeks.html").write_text(
        page(f"週ごと — {SITE_NAME}", f'<main class="in main"><section class="sec"><div class="sec-h"><h2>週ごとの新作</h2></div><ol class="weeks">{week_list}</ol></section></main>'),
        encoding="utf-8",
    )

    tools = "、".join(sorted(AI_TOOLS - {"その他"})) + "、その他"
    if paid:
        paid_rows = (
            '<tr><td>優先掲載</td><td class="n">¥3,000</td><td>希望の日に公開されます</td></tr>'
            '<tr><td>注目枠</td><td class="n">¥8,000／週</td><td>1週間、トップの「今週の注目」に「PR」つきで表示されます</td></tr>'
        )
        paid_note = "お支払いは決済会社の画面で行い、カード情報は Shipyard に届きません。"
    else:
        paid_rows = ""
        paid_note = "希望の日に公開できる有料の掲載は、準備ができしだいご案内します。"
    if submit_url:
        form_box = (
            '<div class="go-box">'
            f'<a class="go" href="{e(submit_url)}" target="_blank" rel="noopener noreferrer">申請フォームを開く（GitHub）</a>'
            '<p class="go-note">申請には GitHub のアカウントが必要です。入力した内容は公開されるので、'
            "メールアドレスなどの個人情報は書かないでください。送信すると自動チェックの結果がすぐに返ってきます。</p></div>"
        )
    else:
        form_box = '<div class="go-box"><p class="go-note">申請フォームは準備中です（試作版）。</p></div>'
    contact = (
        f'<a href="{e(contact_url)}" target="_blank" rel="noopener noreferrer">運営の窓口</a>' if contact_url else "運営の窓口（準備中）"
    )
    submit = f"""<main class="in main prose">
<h1>作品を掲載する</h1>
<p>AIを使ってつくったアプリやWebサービスを、無料で掲載できます。公開日の朝に「今日のデビュー」に並び、その後も週ごとのページに残ります。</p>
<h2>掲載の流れ</h2>
<ol class="steps">
<li><b>申請フォームに記入</b><span>名前、一言説明（40文字まで）、説明（600文字まで）、リンク、つくるのに使ったAI（{e(tools)}）</span></li>
<li><b>自動チェック</b><span>リンクが公式ストアか https の公式サイトか、短縮URLやファイルの直接ダウンロードでないかを確かめます</span></li>
<li><b>運営の確認</b><span>内容を確認して承認します。通常1〜2日です</span></li>
<li><b>デビュー</b><span>無料の掲載は、1日{DAILY_FREE_SLOTS}件までの順番待ちで公開されます</span></li>
</ol>
<h2>料金</h2>
<div class="tbl"><table>
<thead><tr><th>掲載の種類</th><th>料金</th><th>内容</th></tr></thead>
<tbody>
<tr><td>通常</td><td class="n">無料</td><td>順番待ちで公開されます</td></tr>
{paid_rows}
</tbody></table></div>
<p class="small">{paid_note}</p>
<h2>掲載できないもの</h2>
<ul>
<li>ほかの人がつくった作品</li>
<li>ファイルを直接ダウンロードさせるもの（APK、ZIP など）。公式ストアか公式サイトのリンクに限ります</li>
<li>「稼げる」「副業で月◯万」などをうたうもの、成人向け、ギャンブル</li>
<li>個人情報を不正に集めるもの、法律に反するもの</li>
</ul>
{form_box}
</main>"""
    (out / "submit.html").write_text(page(f"掲載する — {SITE_NAME}", submit), encoding="utf-8")

    about = f"""<main class="in main prose">
<h1>この場所について</h1>
<p>{SITE_NAME}（仮称）は、AIを使って個人がつくったアプリやWebサービスを紹介する掲示板です。作品をつくるのは作り手で、私たちは場所を用意しているだけです。</p>
<h2>安全のために決めていること</h2>
<ul>
<li>掲載するのは、公式ストア（App Store、Google Play）か https の公式サイトへのリンクだけです。ファイルの配布はしません</li>
<li>このサイトは会員登録やログインがなく、あなたの個人情報を預かりません</li>
<li>広告や解析のための外部のプログラムを読み込みません</li>
<li>有料の掲載には「PR」と表示します</li>
</ul>
<h2 id="report">通報・お問い合わせ</h2>
<p>問題のある掲載を見つけたら、{contact}までお知らせください。確認のうえ、すぐに掲載を取り下げます。</p>
<h2 id="terms">掲載規約</h2>
<ol>
<li>掲載できるのは、申請者（または申請者のチーム）がつくった作品だけです。</li>
<li>次のものは掲載できません。ほかの人の作品、ファイルを直接ダウンロードさせるもの、「稼げる」などをうたうもの、成人向け、ギャンブル、個人情報を不正に集めるもの、法律や各ストアの規約に反するもの。</li>
<li>掲載の可否は運営が判断します。理由を詳しくお伝えできない場合があります。</li>
<li>掲載後でも、問題が見つかった場合や申請者から依頼があった場合は、運営の判断で取り下げます。</li>
<li>掲載された作品の内容や安全性は、作り手が責任を持ちます。運営はリンク先を自動と目視で確認していますが、作品の安全や品質を保証するものではありません。作品を使うときは、ご自身でも確かめてください。</li>
<li>申請された文章は、このサイトと運営の X アカウントでの紹介に使います。</li>
<li>この規約は変更することがあります。変更したときはこのページでお知らせします。</li>
</ol>
<h2 id="privacy">プライバシーポリシー</h2>
<ul>
<li>このサイトには会員登録やログインがなく、利用者の個人情報を集めていません。Cookie や広告・解析のためのプログラムも使っていません。</li>
<li>サイトの配信を担うサービスが、安全のためにアクセスの記録（IPアドレスなど）を一時的に残すことがあります。</li>
<li>掲載の申請は GitHub で受け付けています。申請に書かれた内容と GitHub の公開プロフィールは、GitHub 上で公開されます。GitHub での情報の扱いは GitHub のプライバシーポリシーに従います。</li>
<li>お問い合わせへの対応に必要な範囲を超えて、情報を使ったり第三者に渡したりしません。</li>
</ul>
<h2>特定商取引法に基づく表記</h2>
<p>現在、有料のサービスは提供していません。有料の掲載を始める前に、このページに掲載します。</p>
</main>"""
    (out / "about.html").write_text(page(f"この場所について — {SITE_NAME}", about), encoding="utf-8")

    items = "".join(
        f"<item><title>{e(a['name'])} — {e(a['tagline'])}</title>"
        f"<link>app-{e(a['id'])}.html</link><guid isPermaLink=\"false\">{e(a['id'])}</guid>"
        f"<pubDate>{date.fromisoformat(a['launch_date']).strftime('%a, %d %b %Y')} 00:00:00 +0900</pubDate>"
        f"<description>{e(a['description'])}</description></item>"
        for a in live[:30]
    )
    (out / "feed.xml").write_text(
        f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>{SITE_NAME}</title>'
        f"<description>{e(TAGLINE)}</description><link>index.html</link>{items}</channel></rss>\n",
        encoding="utf-8",
    )
    print(f"built {len(live)} listings, {len(weeks)} weeks -> {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", type=date.fromisoformat, default=date.today())
    ap.add_argument("--artifact", action="store_true")
    ap.add_argument("--site-url", help="公開する URL（例: https://example.jp）。指定したときだけシェアボタンを出す")
    ap.add_argument("--production", action="store_true", help="本番: サンプルがあれば止める。試作版の帯を消す")
    ap.add_argument("--submit-url", help="申請フォームの URL（GitHub の新規 issue のページ）")
    ap.add_argument("--contact-url", help="通報・お問い合わせの窓口の URL")
    ap.add_argument("--paid", action="store_true", help="有料の掲載の料金を表示する（特定商取引法の表記を用意してから）")
    args = ap.parse_args()
    build(args.today, args.artifact, args.site_url, production=args.production,
          submit_url=args.submit_url, contact_url=args.contact_url, paid=args.paid)
