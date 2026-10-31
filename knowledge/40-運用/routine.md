---
name: routine
description: クラウドの 6 つのチャット（claude.ai/code の routine）。リーダー 1 本（本人の唯一の窓口。2 時間ごと＋PR の出来事で板を見て、分割・点検・催促・本人の手の一覧）と 5 チーム（issue のラベルで起きる）。それぞれ 1 つの会話が続き、Mac・iPad・iPhone のどれからでも読める・書ける。指示文の原本は .claude/routines/。毎晩の巡回は GitHub Actions（patrol.yml）
updated: 2026-10-31
owner: ops
status: 有効
---

# routine（クラウドの 6 つのチャット：リーダー＋5 チーム）

2026-10-20 に分野ごとの 5 つ＋全般を作り、2026-10-31 に「全般」を**リーダー**にした（本人「私が指示をするのは彼のみで、彼がそれを全てに分割していく形」「24 時間止まらずに」。決定録 `70-決定録/2026-10-31-リーダー役.md`）。

## 形
- **本人が書くのはリーダーのチャットだけ**（「TUBE リーダー」。直接 issue を立ててもよい）。リーダーが分野ごとの issue（雛形の 3 欄＋分野ラベル）に分ける。
- **チームは issue のラベルで起きる**（webhook。立てる・ラベルを付ける・閉じる）。自分のラベルの issue を古い順に 1 つ拾い、枝 `<チーム>/issue-N` で直して PR を出し、issue に link を書く。issue が無い実行は数秒で終わる。
- **リーダーは 2 時間ごと（UTC の偶数時）と PR の出来事（開いた・更新した・閉じた）で起きる**。毎回：本人の指示の分割 → 板（issue・PR・検査・巡回）を読む → PR の点検（検査・5 欄・範囲・触ってはいけない所・知識）→「merge 可」か「<分野>：PR #N の直し」の issue → 停滞の催促（24 時間更新なしで 1 日 1 回、ラベルの付け直しでチームが起きる）→ 本人の手の一覧（merge・決める・Mac）→ 仕事の無い分野には `90-種.md` から 1 日 1 つ。変化が無ければ「HH:MM 変化なし」の 1 行だけ。
- **merge は本人**（リーダーが「merge 可」と番号で出す）。任せる範囲は未決（`90-種.md`）。本番への反映も本人（Mac で `sh deploy/更新.sh`）。
- **記憶**：6 本とも 1 つの会話が続く（`persist_session`）。仕事の前に `CLAUDE.md`・`knowledge/INDEX.md`・自分の定義を読む。会話が長くなるとクラウドが自動で要約する。
- **止める**：リポジトリの直下に `チームを止める.txt`（iPhone の GitHub からでも置ける）。リーダーも 5 チームも何もせずに終わる。消すと再開。1 本だけ止めるなら https://claude.ai/code/routines で切る。
- **指示文の原本は `.claude/routines/`**（共通.md＋分野ごとの 1 枚。リーダーは `リーダー.md` 1 枚）。routine の指示文そのものは「main のそのファイルを読んで従う」という短い指し示しだけ（2026-10-31 から。`python3 scripts/brain/routines.py --json` が組む。全文を見るのは `--full`）。だから直すのはファイルだけでよく、main に入れば次の実行から効く。指し示しを変えたときだけ、Claude（Mac のセッション）に「routine の指示文を API に当て直して」と言う（RemoteTrigger の update）。

## トークンの線（2026-10-21 の事故から）
- 10-21〜10-27 にチームが「PR の見回り」の一度きりの routine（reminder）を 12 本作り、10-21 にはアカウントの利用の上限に 6 回当たった（`limit_wake`）。**チームもリーダーも routine を作らない。** PR の行方はリーダーが見る。
- 1 回の実行：チーム 10 万トークン以内、リーダー 5 万以内。空振りは REST で板を読むだけ（knowledge を読まない）。リーダーが新しく立てる issue は 1 回に 3 つまで、催促は 1 日 1 回まで。
- 周期は月末の利用の数で調整（重ければ夜を飛ばす cron、軽ければ 1 時間ごと。`90-種.md`）。

## 6 本（環境「TUBE study」env_01RpZH7znTGF1MmDzFhDNe3N）
| チャット | 役割 | routine の id | 続く会話（セッション） | いつ（UTC） | 出来事 | モデル |
| --- | --- | --- | --- | --- | --- | --- |
| TUBE リーダー | 本人の唯一の窓口。分割・点検・催促・本人の手の一覧 | trig_01FYmJNSmZgrhaUXbhd8QQkH | session_01QeU6wefBYoTAeFavAeosHC | 2 時間ごと（偶数時） | PR（開く・更新・閉じる） | opus 5.5 |
| TUBE コード・仕様 | サーバ・画面の論理・API・検査・仕様 | trig_01ErHPGBHN1cPV9DrzRahkhZ | session_01EhH4ZkjvtMG5gScWpFLLjx | 毎日 05:00 | issue | opus 5.5 |
| TUBE デザイン | 見た目・動き・言葉 | trig_01N88LA3ypyczknGUur5ScrG | session_014BxN9Ww1abhWrMsE1EehSu | 毎日 05:30 | issue | opus 5.5 |
| TUBE 運用・データ・デバッグ | 巡回の結果・データ・切り分け。定例：巡回の失敗の切り分け、月曜に現状の数を PR | trig_01BEqgKVtU5YCaen5c2QGm2i | session_01UPypEj5W1bBGh1Z5rKAneZ | 毎日 06:00 | issue | sonnet 5.5 |
| TUBE 法務・申請 | DPIA・通知・規約・契約・ICO・申請。定例：14 日以内の期限を issue「法務：今週の期限」 | trig_0128Z8oDxhJZtmBouP9bFwNw | session_013fLnDsnkKKfEz4UCEmM1Zh | 月曜 08:00 | issue | opus 5.5 |
| TUBE 資料 | 稟議・提案・説明書・週報。定例：月曜に週報を PR | trig_01NYDG3kzwvYdWBGpgi6H2U3 | session_01TYaZKMJdjts5LWtFFQCGFB | 月曜 07:00 | issue | opus 5.5 |

- 開き方：routine が作ったセッションは、ふつうのセッションの一覧でなく「スケジュール済みタスク」の区画に載る。Mac のアプリではこの区画が 10-14 の更新から表示できない（アプリの不具合。設定にも道具にも切り替えが無い）。左の「スケジュール済みタスク」の頁から task → 実行（セッション）と辿って開く。実行のセッションは普通のセッションと同じで、名前を変えられ、会話を続けられる（10-20 に法務のチャットで確かめた）。どの端末でも直接開けるのは `https://claude.ai/code/<上の session_…>`（iPhone・iPad は Safari で開いてホーム画面に置くのが早い）。
- ラベル：コード・デザイン・運用・法務・資料（チームが拾う）、対応中・PR あり（チームが付ける）、保留・本人（チームは拾わない）、決定・不具合・改良・巡回。一覧は `.github/labels.json`、作るのは Actions「ラベル」。
- **クラウドのセッションでは GitHub の GraphQL が使えない**（`gh issue list`・`gh pr list`・`gh pr create`・`gh pr checks` は 403）。REST（`gh api repos/autumn07020/tube-schools/…`）で読む・書く。`gh run list`・`gh run download` は使える。指示文は REST の形で書いてある。
- セッションには本人の claude.ai の道具（Claude Docs・Google Drive・Claude Code Remote・GitHub の connector `mcp__github__*`（10-31 に確認。REST の `gh api` と同じことができる））がつながる。Claude Code Remote で routine を作れてしまうので、作らない決まりを指示文に書いた。文書の原本は Git の `docs/`、Docs は写し。本番の鍵・合言葉は環境に置かない。
- issue の出来事 1 つで 5 チームが起き（担当でないチームは数秒で終わる）、PR の出来事 1 つでリーダーが起きる。

## 毎晩の巡回 ―― GitHub Actions（2026-10-20 夜）
- `.github/workflows/patrol.yml`：04:00 UTC に本番を読むだけの検査（`scripts/check/expect.py`）。失敗は issue「巡回 YYYY-MM-DD：失敗」、月曜は控えの PR。止めるのは `巡回を止める.txt`。中身は `40-運用/反映と巡回.md`。
- 口座は GitHub の Secrets `TUBE_DEMO_ACCOUNTS_B64`（架空のデモ校 london の 9 口座）。運用チームの routine が翌朝読み、リーダーが板で追う。

## 環境（本人が claude.ai/code で作った。2026-10-20）
- 名前 `TUBE study`。秘密も網も空（巡回の口座は GitHub の Secrets にあるので要らない）。ほかの作品の環境は使わない。
- Mac の Claude Code のチャットは、Mac が起きている間だけ Remote Control で iPhone から続けられる。routine の作り直し・引き金・写しの当て直しは Mac のセッション（RemoteTrigger）だけができる。
