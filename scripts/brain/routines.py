#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""routine（claude.ai/code の定期実行。リーダー 1 本＋チーム 5 本）の指示文を組み立てる。

    python3 scripts/brain/routines.py --json        … API に入れる「指し示し」{routine: 文}（main のファイルを読んで従え、の短い文）
    python3 scripts/brain/routines.py --full        … 全文（共通の頭＋チームのファイル。リーダーは 1 枚）を順に印字
    python3 scripts/brain/routines.py --full コード  … 1 つだけ

原本は `.claude/routines/共通.md`（1 行目の（…）は注なので外す）と `.claude/routines/<チーム>.md`、リーダーは `リーダー.md`。
routine に入っているのは「指し示し」だけ（2026-10-31 から）。ファイルを直して main に入れば、次の実行から効く。
指し示しそのものを変えたとき（この script を変えたとき）だけ、Claude（Mac のセッション）に「routine の指示文を API に当て直して」と言う
（API（RemoteTrigger）には Claude のセッションからしか届かない。knowledge/40-運用/routine.md）。
"""
import io
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DIR = os.path.join(ROOT, ".claude", "routines")
TEAMS = ["コード", "デザイン", "運用", "法務", "資料"]
ALONE = ["リーダー"]      # 共通の頭を付けない（1 枚で完結する指示文）
NAMES = {"コード": "コード・仕様", "デザイン": "デザイン", "運用": "運用・データ・デバッグ",
         "法務": "法務・申請", "資料": "資料", "リーダー": "リーダー"}
# merge の前にリーダーを動かすための逃げ道。main に入ったら空にして、指し示しを当て直す
LEADER_FALLBACK_BRANCH = "general/leader"
LINE = ("本番（https://tube-study.uk）は読むだけ・SSH/scp/rsync しない・`deploy/*.sh` を流さない・"
        "本番の鍵と合言葉と講師の名字を書かない・main に直接 push しない・`--force` しない・merge しない・"
        "routine（scheduled task・reminder）を作らない・サブエージェントや並列を使わない")


def _strip_note(s):
    lines = s.strip().split("\n")
    if lines and lines[0].startswith("（"):
        lines = lines[1:]
    return "\n".join(lines).strip()


def common():
    return _strip_note(io.open(os.path.join(DIR, "共通.md"), encoding="utf-8").read())


def full(team):
    body = io.open(os.path.join(DIR, team + ".md"), encoding="utf-8").read()
    if team in ALONE:
        return _strip_note(body) + "\n"
    return common() + "\n\n" + body.strip() + "\n"


def pointer(team):
    name = NAMES[team]
    if team in ALONE:
        head = ("（この文は claude.ai/code の routine「TUBE リーダー」の指示文。中身の原本はリポジトリ main の "
                "`.claude/routines/リーダー.md`。`python3 scripts/brain/routines.py --json` が組む）\n\n"
                "あなたは TUBE study（GitHub の私有リポジトリ `autumn07020/tube-schools`）のリーダーの routine。"
                "最初にクローンした main の `.claude/routines/リーダー.md`（1 行目の注は飛ばす）を読み、そのとおりに動く。")
        if LEADER_FALLBACK_BRANCH:
            head += ("main に無ければ `git fetch origin %s && git show origin/%s:.claude/routines/リーダー.md` で読む。"
                     % (LEADER_FALLBACK_BRANCH, LEADER_FALLBACK_BRANCH))
        budget = "5 万"
    else:
        head = ("（この文は claude.ai/code の routine「TUBE %s」の指示文。中身の原本はリポジトリ main の "
                "`.claude/routines/共通.md` と `.claude/routines/%s.md`。`python3 scripts/brain/routines.py --json` が組む）\n\n"
                "あなたは TUBE study（GitHub の私有リポジトリ `autumn07020/tube-schools`）のチーム「%s」の routine。"
                "最初にクローンした main の `.claude/routines/共通.md`（1 行目の注は飛ばす）と `.claude/routines/%s.md` を読み、そのとおりに動く。"
                % (name, team, name, team))
        budget = "10 万"
    return (head + "読めなければ「指示文が読めないので何もしなかった」と 1 行書いて止まる。"
            "ファイルが読めても読めなくても守る線：" + (LINE.replace("・merge しない", "・merge は指示文の 3 条件を満たしたときだけ") if team in ALONE else LINE) + "・1 回の実行は " + budget + "トークン以内。"
            "返答は日本語、見出しは日本語だけ。本人がこの会話に書いた指示は最優先。\n")


def main(argv):
    if argv[:1] == ["--json"]:
        print(json.dumps({t: pointer(t) for t in TEAMS + ALONE}, ensure_ascii=False, indent=1))
        return 0
    if argv[:1] == ["--full"]:
        teams = [a for a in argv[1:] if a in TEAMS + ALONE] or TEAMS + ALONE
        for t in teams:
            print("=" * 20, t, "=" * 20)
            print(full(t))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
