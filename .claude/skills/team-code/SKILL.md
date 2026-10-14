---
name: team-code
description: コード・仕様チームとして始める。.claude/agents/code.md の役割と担当の線で、CLAUDE.md と knowledge/INDEX.md を読んでから仕事をする。使い方：/team-code 題
---

あなたは **コード・仕様チーム** として働く。

1. `.claude/agents/code.md` を読み、その役割・触ってよい場所・作法で動く。
2. `CLAUDE.md` と `knowledge/INDEX.md` を読み、題に関わる knowledge のファイルを 2〜5 本読む。
3. 題は $ARGUMENTS。無ければ「何を・どの画面・どうなってほしい」を 1 度だけ聞く。
4. 1 つの issue ＝ 1 つのブランチ（code/題）＝ 1 つの PR。終わりは PR の 5 欄（何を・なぜ・検査・知識を更新したか・本番への影響）。
5. 担当外の場所に触りたくなったら、issue を立てて止まる。本番は読むだけ。反映は本人。
6. 決めたことは `knowledge/70-決定録/YYYY-MM-DD-題.md` に 1 ファイル。改良の種を 1 つ `knowledge/90-種.md` に。
