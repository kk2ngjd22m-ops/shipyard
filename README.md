# Shipyard（仮称）

AIを使って個人がつくったアプリやWebサービスを紹介する、ローンチ掲示板のサイトです。

## 作品を掲載したい方
このリポジトリの [Issues](../../issues/new/choose) から「作品を掲載する」を選んで申請してください。
自動チェックの結果がすぐにコメントで返り、運営が確認したあと公開されます。入力した内容は公開されるので、個人情報は書かないでください。

## 安全のために決めていること
- サイトは静的なページだけです。サーバ、データベース、ログイン、JavaScript はありません
- 掲載は、公式ストアか https の公式サイトへのリンクだけです。ファイルは配布しません
- 外部のスクリプト、フォント、解析タグを読み込みません（`site/_headers` の CSP で禁止しています）

## 構成
| パス | 内容 |
|---|---|
| `site/apps/*.json` | 掲載 1 件につき 1 ファイル |
| `site/check_listing.py` | 掲載の自動チェック |
| `site/build.py` | サイトを `site/dist/` に作る |
| `automation/intake.py` | 申請フォームの内容を掲載ファイルにする |
| `automation/x_daily_post.py` | 毎朝の X 投稿 |
| `.github/` | 申請フォームと自動化のワークフロー |

## テスト
```sh
python3 site/test_check_listing.py
PYTHONPATH=site python3 automation/test_intake.py
python3 automation/test_x_daily_post.py
```
