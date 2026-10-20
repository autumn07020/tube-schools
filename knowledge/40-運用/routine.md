---
name: routine
description: クラウドの 6 つのチャット（claude.ai/code の routine。5 つのチーム＋全般）。それぞれ 1 つの会話が続き、Mac・iPad・iPhone のどれからでも読める・書ける。時刻と GitHub の issue の出来事で起きる。指示文の原本は .claude/routines/。毎晩の巡回は GitHub Actions（patrol.yml）
updated: 2026-10-20
owner: ops
status: 有効
---

# routine（クラウドの 6 つのチャット）

2026-10-20 本人「別々の独立したチャットを開設し、自律的に動いてもらいつつ、私自身も各分野でやって欲しいことを指示できる基盤」「Mac でも iPad でも iPhone でも同様の 5＋1（このチャット）の 6 チャットを閲覧、追記できるのが大切」。その形は次のとおり。

## 形
- **チャットは 6 つ**：分野ごとの 5 つ（コード・仕様／デザイン／運用・データ・デバッグ／法務・申請／資料）と、全般（Mac の Claude Code のチャットに当たる、相談と調整の役）。それぞれが claude.ai/code の routine 1 本で、**1 つの会話が続く**（`persist_session`。実行のたびに新しくならない）。Claude のアプリ（iPhone・iPad）や claude.ai/code（Mac）のセッションの一覧に、この 6 つが並ぶ。
- **指示の入口は 2 つ**：(1) そのチャットに直接書く（その会話の指示が最優先）。(2) GitHub の issue を分野の雛形で立てる（`.github/ISSUE_TEMPLATE/`。分野のラベルが付く）。チームは自分のラベルの issue を古い順に 1 つ拾い、枝 `<チーム>/issue-N` で直して PR を出し、issue に link を書く。
- **起きるとき**：決まった時刻（下の表）と、GitHub の issue の出来事（立てる・ラベルを付ける・閉じる など。webhook）。issue が無いチームは knowledge を読まずに数秒で終える。
- **記憶**：会話そのものが続くうえ、仕事の前に `CLAUDE.md`・`knowledge/INDEX.md`・自分のチームの定義を読む。会話が長くなるとクラウドが自動で要約する。
- **ぶつからない**：担当外の場所は触らず、issue に担当チームのラベルを足して渡す。main には PR と検査を通してしか入らない。merge は本人が ✓ を見て押す（1 タップ）。
- **止める**：リポジトリの直下に `チームを止める.txt` を置く（iPhone の GitHub からでも置ける）。6 つとも何もせずに終わる。消すと再開。1 本だけ止めるなら https://claude.ai/code/routines で切る。
- **指示文の原本は `.claude/routines/`**（共通.md＋分野ごとの 1 枚。全般は `全般.md` 1 枚）。routine にはその写しが入っているが、routine は main のファイルを先に読んで優先するので、直すのはファイルだけでよい（PR → merge）。`python3 scripts/brain/routines.py` が写しの文を組む。大きく変えたら Claude に「routine の写しを当て直して」と言う（RemoteTrigger の update）。

## 6 つ（2026-10-20 に Claude が API で作った。環境「TUBE study」env_01RpZH7znTGF1MmDzFhDNe3N）
| チャット | 役割 | routine の id | 続く会話（セッション） | いつ（UTC） | モデル | 定例（issue が無いとき） |
| --- | --- | --- | --- | --- | --- | --- |
| TUBE 全般 | 相談・調整・分野の決まらない頼みごと。Mac のチャットの続き | trig_01FYmJNSmZgrhaUXbhd8QQkH | session_01QeU6wefBYoTAeFavAeosHC | 月曜 09:00 | opus 5.5 | 本人の手が要るもの（issue「本人」・開いた PR）を 5 行で |
| TUBE コード・仕様 | サーバ・画面の論理・API・検査・仕様 | trig_01ErHPGBHN1cPV9DrzRahkhZ | session_01EhH4ZkjvtMG5gScWpFLLjx | 毎日 05:00 | opus 5.5 | 何もしない |
| TUBE デザイン | 見た目・動き・言葉 | trig_01N88LA3ypyczknGUur5ScrG | session_014BxN9Ww1abhWrMsE1EehSu | 毎日 05:30 | opus 5.5 | 何もしない |
| TUBE 運用・データ・デバッグ | 巡回の結果・データ・切り分け | trig_01BEqgKVtU5YCaen5c2QGm2i | session_01UPypEj5W1bBGh1Z5rKAneZ | 毎日 06:00 | sonnet 5.5 | 巡回（Actions）の結果と失敗の issue を読み、切り分けて渡す。月曜は現状の数を PR |
| TUBE 法務・申請 | DPIA・通知・規約・契約・ICO・申請 | trig_0128Z8oDxhJZtmBouP9bFwNw | session_013fLnDsnkKKfEz4UCEmM1Zh | 月曜 08:00 | opus 5.5 | `50-法務` 15 章の期限を照らし、14 日以内のものを issue「法務：今週の期限」（ラベル「本人」） |
| TUBE 資料 | 稟議・提案・説明書・週報 | trig_01NYDG3kzwvYdWBGpgi6H2U3 | session_01TYaZKMJdjts5LWtFFQCGFB | 月曜 07:00 | opus 5.5 | 週報 `docs/週報/YYYY-MM-DD.md` を PR |

- 開き方：Mac は https://claude.ai/code/ の一覧（セッションの link は `https://claude.ai/code/<上の session_…>`）。iPhone・iPad は Claude のアプリ → Code → `tube-schools` の一覧。名前で見分ける。
- ラベル：コード・デザイン・運用・法務・資料（チームが拾う）、対応中・PR あり（チームが付ける）、保留・本人（チームは拾わない）、決定・不具合・改良・巡回。一覧は `.github/labels.json`、作るのは Actions「ラベル」（main に入ると自動。10-20 に流れた）。
- **クラウドのセッションでは GitHub の GraphQL が使えない**（`gh issue list`・`gh pr list`・`gh pr create` は 403）。REST（`gh api repos/autumn07020/tube-schools/…`）で読む・書く。`gh run list`・`gh run download` は使える。指示文は REST の形で書いてある。
- セッションには本人の claude.ai の道具（Claude Docs・Google Drive）がつながる。文書の原本は Git の `docs/`、Docs は写し。本番の鍵・合言葉は環境に置かない（毎晩の巡回は Actions の Secrets で動く）。
- 1 回の実行は 10 万トークン以内。issue が無い日の実行は読むだけで終わる（10-20 の試し：運用が 3 手・13 秒）。issue の出来事 1 つで 5 本が起きる（担当でないチームは数秒で終わる）。重く感じたら、毎日のものを週 1 に下げる（本人の判断）。
- 本番への反映は本人（Mac で `sh deploy/更新.sh`）。チームは命令文を用意するまで。

## 毎晩の巡回 ―― GitHub Actions（2026-10-20 夜）
- `.github/workflows/patrol.yml`：04:00 UTC に本番を読むだけの検査（`scripts/check/expect.py`）。失敗は issue「巡回 YYYY-MM-DD：失敗」、月曜は控えの PR。止めるのは `巡回を止める.txt`。中身は `40-運用/反映と巡回.md`。
- 口座は GitHub の Secrets `TUBE_DEMO_ACCOUNTS_B64`（架空のデモ校 london の 9 口座）。運用チームの routine は、この結果を翌朝読む。

## 環境（本人が claude.ai/code で作った。2026-10-20）
- 名前 `TUBE study`。秘密も網も空（巡回の口座は GitHub の Secrets にあるので要らない）。ほかの作品の環境は使わない。
- Mac の Claude Code のチャットは、Mac が起きている間だけ Remote Control で iPhone から続けられる。端末を問わず続けるのはクラウドの 6 つ。
