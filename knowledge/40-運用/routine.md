---
name: routine
description: 雲（claude.ai/code の定期実行）で回す 3 本の指示文：毎晩の巡回（読むだけ）・週 1 の週報・issue のラベルで拾う。GitHub に原本がある前提。作るのは本人が push したあと
updated: 2026-10-14
owner: ops
status: 準備中
---

# routine（雲で回す指示文）

前提：GitHub の私有リポジトリ `tube-schools` が claude.ai/code に接続されていること。どの routine も最初に `CLAUDE.md` と `knowledge/INDEX.md` を読む。本番は読むだけ。1 回 10 万トークン以内。並列のエージェントを使わない。

## 1. 巡回（毎晩 3:00 ロンドン）
```
あなたは TUBE study の運用・データ・デバッグチーム（.claude/agents/ops.md）。
1. knowledge/INDEX.md と knowledge/10-現状.md を読む。
2. 本番 https://tube-study.uk を読むだけで確かめる：python3 scripts/check/expect.py（GET と、デモの入口で選んだ生徒だけ。wt01 や本物の講師では入らない）。
   デモの口座が無い環境では GET だけの項目を流し、入れなかった項目は「未確認」と書く。
3. 前回（scripts/check/ledger-production.json）との差を出す。減った数があれば、理由を言えるまで「減った」とだけ書き、直さない。
4. knowledge/10-現状.md の「検査の数」と「直近」を今日の値に更新し、ブランチ ops/巡回-YYYY-MM-DD で PR を出す（タイトル「巡回 YYYY-MM-DD」、本文に差と未確認）。
5. 不具合らしいものは issue（不具合の雛形。再現手順付き。ラベル 不具合）。直すのはコードチーム。
6. 10 万トークンを超えそうなら途中でも PR を出して止まる。本番に書き込まない。SSH しない。
```

## 2. 週報（毎週月曜 7:00 ロンドン）
```
あなたは TUBE study の資料チーム（.claude/agents/docs.md）。
1. この 1 週間の PR・issue・knowledge/70-決定録 の新しいファイル・巡回の PR を読む。
2. Claude Docs に「週報 YYYY-MM-DD」を 1 枚作る：できたこと／見つかった不具合と直り具合／決めたこと／本人の手が要ること（期限つき）／来週の 3 つ。
   見出しは日本語だけ。数字には出典（PR 番号・検査名）。A4 1 枚に収まる量。
3. 決定録に写っていない決めごと（決定ラベルの issue や PR の本文にある）があれば、knowledge/70-決定録/ に 1 ファイル書いて PR を出す。
4. 本番には触らない。
```

## 3. 拾う（1 時間ごと、または issue のラベルで）
```
あなたは TUBE study のチームの 1 つ。ラベル claude-ok が付いていて、まだ担当のブランチが無い issue を 1 つだけ選ぶ（古い順）。
1. issue の本文から担当チームを決め（不具合・コードは code、見た目は design、データと deploy は ops、文面は legal、文書は docs）、.claude/agents/<チーム>.md の役割で動く。
2. ブランチ <チーム>/issue-<番号> を作り、直し、検査（サーバの検査・check-source・secrets・画面を変えたら flows）を通し、PR の 5 欄を埋めて PR を出す。issue に PR の番号を書く。
3. 担当外の場所に触る必要があれば、直さずに issue にその旨を書いて止まる。
4. merge はしない。本番に触らない。10 万トークンを超えそうなら途中でも PR を出して止まる。
```

作り方（本人が push したあと）：claude.ai/code の「定期実行」で上の 3 本をそれぞれ作る。雲の環境にデモの口座を置くかは本人の判断（`40-運用/鍵の在りか.md`）。
