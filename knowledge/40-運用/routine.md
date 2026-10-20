---
name: routine
description: チームごとのクラウドのチャット（claude.ai/code の routine）5 本。分野ごとに独立して動き、本人は iPhone・iPad・Mac から、そのチャットか GitHub の issue で指示する。指示文の原本は .claude/routines/。毎晩の巡回は GitHub Actions（patrol.yml）
updated: 2026-10-20
owner: ops
status: 有効
---

# routine（チームごとのクラウドのチャット）

2026-10-20 本人「別々の独立したチャットを開設し、自律的に動いてもらいつつ、私自身も各分野でやって欲しいことを指示できる基盤」。その形は次のとおり。

## 形
- **分野ごとに 1 本の routine**（claude.ai/code の定期実行）。実行のたびにクラウドのセッションが 1 つ開き、そのチームの役で動く。本人はそのセッションを Claude のアプリ（iPhone・iPad・Mac）で開いて、続けて指示できる（開いた会話の指示は issue より優先）。
- **指示の入口は 2 つ**：(1) そのチームのセッションに直接書く。(2) GitHub の issue を分野の雛形で立てる（`.github/ISSUE_TEMPLATE/`。分野のラベルが付く）。チームは自分のラベルの issue を古い順に 1 つ拾い、枝 `<チーム>/issue-N` で直して PR を出し、issue に link を書く。
- **記憶は knowledge と issue と PR**。セッションは実行ごとに新しいが、最初に `CLAUDE.md`・`knowledge/INDEX.md`・自分のチームの定義を読むので、続きになる。
- **ぶつからない**：担当外の場所は触らず、issue に担当チームのラベルを足して渡す。main には PR と検査を通してしか入らない。merge は本人が ✓ を見て押す（1 タップ）。
- **止める**：リポジトリの直下に `チームを止める.txt` を置く（iPhone の GitHub からでも置ける）。全チームが何もせずに終わる。消すと再開。1 本だけ止めるなら https://claude.ai/code/routines で切る。
- **指示文の原本は `.claude/routines/共通.md` と `.claude/routines/<チーム>.md`**。routine にはその写しが入っているが、routine は main のファイルを先に読んで優先するので、直すのはファイルだけでよい（PR → merge）。`python3 scripts/brain/routines.py` が写しの文を組む。大きく変えたら Claude に「routine の写しを当て直して」と言う（RemoteTrigger の update）。

## 5 本（2026-10-20 に Claude が API で作った。環境「TUBE study」env_01RpZH7znTGF1MmDzFhDNe3N）
| routine | id | いつ（UTC） | モデル | 定例（issue が無いとき） |
| --- | --- | --- | --- | --- |
| TUBE コード | trig_01ErHPGBHN1cPV9DrzRahkhZ | 毎日 05:00 | opus 5.5 | 何もしない |
| TUBE デザイン | trig_01N88LA3ypyczknGUur5ScrG | 毎日 05:30 | opus 5.5 | 何もしない |
| TUBE 運用 | trig_01BEqgKVtU5YCaen5c2QGm2i | 毎日 06:00 | sonnet 5.5 | 巡回（Actions）の結果と失敗の issue を読み、切り分けて渡す。月曜は現状の数を PR |
| TUBE 資料 | trig_01NYDG3kzwvYdWBGpgi6H2U3 | 月曜 07:00 | opus 5.5 | 週報 `docs/週報/YYYY-MM-DD.md` を PR |
| TUBE 法務 | trig_0128Z8oDxhJZtmBouP9bFwNw | 月曜 08:00 | opus 5.5 | `50-法務` 15 章の期限を照らし、14 日以内のものを issue「法務：今週の期限」（ラベル「本人」） |

- ラベル：コード・デザイン・運用・法務・資料（チームが拾う）、対応中・PR あり（チームが付ける）、保留・本人（チームは拾わない）、決定・不具合・改良・巡回。一覧は `.github/labels.json`、作るのは Actions「ラベル」（main に入ると自動）。チームも自分のラベルが無ければ作る。
- **クラウドのセッションでは GitHub の GraphQL が使えない**（2026-10-20 の試しの実行で分かった。`gh issue list`・`gh pr list`・`gh pr create` は 403）。REST（`gh api repos/autumn07020/tube-schools/…`）で読む・書く。`gh run list`・`gh run download` は使える。指示文（共通.md）は REST の形で書いてある。
- routine のセッションには本人の claude.ai の道具（Claude Docs・Google Drive）がつながる。文書の原本は Git の `docs/`、Docs は写し。本番の鍵・合言葉は環境に置かない（毎晩の巡回は Actions の Secrets で動く）。
- 1 回の実行は 10 万トークン以内。issue が無い日の実行は、読むだけで終わる（10-20 の試し：運用が 4 手・24 秒）。毎日の 3 本が重く感じたら、週 1 に下げる（本人の判断）。
- 本番への反映は本人（`sh deploy/更新.sh`）。チームは命令文を用意するまで。

## 毎晩の巡回 ―― GitHub Actions（2026-10-20 夜）
- `.github/workflows/patrol.yml`：04:00 UTC に本番を読むだけの検査（`scripts/check/expect.py`）。失敗は issue「巡回 YYYY-MM-DD：失敗」、月曜は控えの PR。止めるのは `巡回を止める.txt`。中身は `40-運用/反映と巡回.md`。
- 口座は GitHub の Secrets `TUBE_DEMO_ACCOUNTS_B64`（架空のデモ校 london の 9 口座）。運用チームの routine は、この結果を翌朝読む。

## 環境（本人が claude.ai/code で作った。2026-10-20）
- 名前 `TUBE study`。秘密も網も空（巡回の口座は GitHub の Secrets にあるので要らない）。ほかの作品の環境は使わない。
- 使い方：iPhone の Claude アプリ → Code → `tube-schools` → セッションを開く（routine の実行がセッションとして並ぶ）。新しく始めるときは `/team-code 題` のように書くと、そのチームの役で動く。
