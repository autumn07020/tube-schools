---
name: routine
description: 雲（claude.ai/code の定期実行）で回す指示文。毎晩の巡回は検査だけ（2026-10-20 本人が再開を決めた）。週報と「拾う」はまだ作らない
updated: 2026-10-20
owner: ops
status: 準備中
---

# routine（雲で回す指示文）

前提：GitHub の私有リポジトリ `autumn07020/tube-schools` が claude.ai/code につながっていること。TUBE study 専用の環境（下の「環境」）があること。どの routine も本番は読むだけ。並列のエージェントを使わない。

## 1. 毎晩の巡回（検査だけ。2026-10-20 本人「雲で毎晩、検査だけ」）
- いつ：毎日 04:00 UTC（cron `0 4 * * *`。ロンドンの冬時間は 4:00、夏時間は 5:00）。本番の S3 の控え（毎日 3 時）と重ねない。
- モデル：claude-sonnet-5-5（検査だけなので軽いもの）。道具：Bash・Read・Write・Edit・Glob・Grep。
- 止める：リポジトリの直下に `巡回を止める.txt` を置く（iPhone の GitHub からでも置ける）。消すと再開する。

```
あなたは TUBE study の運用チーム（.claude/agents/ops.md）として、毎晩の巡回をする。直す作業はしない。本番は読むだけ。SSH しない。本番に書き込まない。並列のエージェントを使わない。3 万トークンほどで終える。
0. リポジトリの直下に 巡回を止める.txt があれば、何もせず「止める合図があるので巡回しなかった」とだけ書いて終える。
1. knowledge/INDEX.md と knowledge/10-現状.md を読む。講師の名字は書かない（ログインID で書く）。
2. 環境変数 TUBE_DEMO_ACCOUNTS_B64 があれば `printf '%s' "$TUBE_DEMO_ACCOUNTS_B64" | base64 -d > /tmp/demo-accounts.json`。無ければ `echo [] > /tmp/demo-accounts.json` とし、報告に「口座が無いので GET と門の検査だけ」と書く。口座の中身（ID と合言葉）は画面にも PR にも出さない。
3. `cp scripts/check/ledger-production.json /tmp/ledger.json` のあと
   `python3 scripts/check/expect.py --base https://tube-study.uk --accounts /tmp/demo-accounts.json --ledger /tmp/ledger.json > /tmp/expect.log 2>&1`。
   入るのは口座の表にあるデモ校の口座だけ。wt01 や本物の講師では入らない。
4. 結果（今日の日付 YYYY-MM-DD はロンドンの日付）：
   - すべて通り △ も無く、月曜でなければ、何も作らず「巡回 YYYY-MM-DD：N 件すべて通過」と最後に書いて終える。
   - × か △ があれば、`docs/巡回/YYYY-MM-DD.md` に、最後の行・× と △ の行・前回との差（/tmp/ledger.json と scripts/check/ledger-production.json の違い）を書き、枝 `claude/patrol-YYYY-MM-DD` で PR を出す。タイトル「巡回 YYYY-MM-DD：× N 件 △ M 件」。原因の推測は「推測」と書く。直さない。
   - 月曜は、すべて通っても、`docs/巡回/YYYY-MM-DD.md` と、`scripts/check/ledger-production.json`（今日の /tmp/ledger.json）と、`knowledge/10-現状.md` の「本番を読むだけの検査」の行（件数と日付）を直して、同じ枝の名前で PR を出す。タイトル「巡回 YYYY-MM-DD（週の控え）」。
   - PR を作れないときは、枝を送ったところで止め、最後の報告に枝の名前を書く。
5. merge はしない。main に直接送らない。
```

## 環境（本人が claude.ai/code で 1 度だけ作る）
- 名前：`TUBE study`。ほかの作品の環境は使わない（その環境の秘密が TUBE study の実行から見えてしまう）。
- 網：`tube-study.uk` へ出られること（許す先に足す、または全部許す）。GitHub は既定で出られる。
- 秘密：`TUBE_DEMO_ACCOUNTS_B64` に、手元の `deploy/demo-accounts.json` を base64 にした 1 行。中身は架空のデモ校 london の 9 口座（講師 4・生徒 5）だけ（10-20 に確かめた。本物の校舎の口座は入っていない）。本人が入れる（Claude は合言葉を写さない）。
- 作り方の 1 行（手元の Mac で。クリップボードに入るので、貼ったあと別の文字をコピーして消す）：`cd ~/Projects/tube-schools && base64 -i deploy/demo-accounts.json | tr -d '\n' | pbcopy`
- 環境ができたら Claude に「巡回の環境を作った」と言う。Claude が定期実行を作り、1 度だけ流して確かめる。

## 2. 週報（まだ作らない）
```
あなたは TUBE study の資料チーム（.claude/agents/docs.md）。
1. この 1 週間の PR・issue・knowledge/70-決定録 の新しいファイル・docs/巡回/ を読む。
2. Claude Docs に「週報 YYYY-MM-DD」を 1 枚作る：できたこと／見つかった不具合と直り具合／決めたこと／本人の手が要ること（期限つき）／来週の 3 つ。
   見出しは日本語だけ。数字には出典（PR 番号・検査名）。A4 1 枚に収まる量。
3. 決定録に写っていない決めごとがあれば、knowledge/70-決定録/ に 1 ファイル書いて PR を出す。
4. 本番には触らない。
```

## 3. 拾う（まだ作らない）
```
あなたは TUBE study のチームの 1 つ。ラベル claude-ok が付いていて、まだ担当のブランチが無い issue を 1 つだけ選ぶ（古い順）。
1. issue の本文から担当チームを決め（不具合・コードは code、見た目は design、データと deploy は ops、文面は legal、文書は docs）、.claude/agents/<チーム>.md の役割で動く。
2. ブランチ claude/issue-<番号> を作り、直し、検査（サーバの検査・check-source・secrets・画面を変えたら flows）を通し、PR の 5 欄を埋めて PR を出す。issue に PR の番号を書く。
3. 担当外の場所に触る必要があれば、直さずに issue にその旨を書いて止まる。
4. merge はしない。本番に触らない。10 万トークンを超えそうなら途中でも PR を出して止まる。
```
