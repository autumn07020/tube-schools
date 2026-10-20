---
name: routine
description: クラウド（claude.ai/code の定期実行）で回す指示文。毎晩の巡回は 2026-10-20 夜に GitHub Actions（patrol.yml）へ移した。ここに残るのは、routine を使うときの環境と、週報・「拾う」（まだ作らない）
updated: 2026-10-20
owner: ops
status: 準備中
---

# routine（クラウドで回す指示文）

前提：GitHub の私有リポジトリ `autumn07020/tube-schools` が claude.ai/code につながっていること（Claude の GitHub App）。TUBE study 専用の環境（下の「環境」）があること。どの routine も本番は読むだけ。並列のエージェントを使わない。

## 1. 毎晩の巡回 ―― GitHub Actions に移した（2026-10-20 夜）
- 本人の決定「クラウドで毎晩、検査だけ」は、Claude の routine ではなく **GitHub Actions の `.github/workflows/patrol.yml`** で動かす。routine は本人が専用の環境を作らないと使えないが、Actions なら本人の手は「秘密を 1 つ貼る」と「1 回手で流す」だけ。中身は `40-運用/反映と巡回.md` の「巡回」。
- 止める：リポジトリの直下に `巡回を止める.txt` を置く（iPhone の GitHub からでも置ける）。消すと再開する。
- 口座：GitHub の Secrets `TUBE_DEMO_ACCOUNTS_B64`（手元の `deploy/demo-accounts.json` を base64 にした 1 行。架空のデモ校 london の 9 口座だけ）。無ければ門の検査だけ。
- 10-20 の昼に書いた Claude の巡回の指示文は使わない（`70-決定録/2026-10-20-巡回の再開と置き場の整理.md`）。巡回に「考える仕事」（週報・拾う）を戻すときは、下の形で routine を作る。

## 環境（本人が claude.ai/code で 1 度だけ作る。routine を使うときだけ）
- 名前：`TUBE study`。ほかの作品の環境は使わない（その環境の秘密が TUBE study の実行から見えてしまう）。
- 網：`tube-study.uk` へ出られること（許す先に足す、または全部許す）。GitHub は既定で出られる。
- 秘密：routine から本番を読むなら `TUBE_DEMO_ACCOUNTS_B64`（GitHub の Secrets と同じ値。手元の `deploy/demo-accounts.json` を base64 にした 1 行。中身は架空のデモ校 london の 9 口座（講師 4・生徒 5）だけ。10-20 に確かめた。本物の校舎の口座は入っていない）。本人が入れる（Claude は合言葉を写さない）。
- 作り方の 1 行（手元の Mac で。クリップボードに入るので、貼ったあと別の文字をコピーして消す）：`cd ~/Projects/tube-schools && base64 -i deploy/demo-accounts.json | tr -d '\n' | pbcopy`
- 環境ができたら Claude に「routine の環境を作った」と言う。Claude が定期実行を作り、1 度だけ流して確かめる。

## 2. 週報（まだ作らない）
```
あなたは TUBE study の資料チーム（.claude/agents/docs.md）。
1. この 1 週間の PR・issue（Actions の「巡回」が作った issue を含む）・knowledge/70-決定録 の新しいファイル・Actions「巡回」の結果を読む。
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
