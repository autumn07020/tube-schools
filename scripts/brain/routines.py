#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""チームごとの routine（claude.ai/code の定期実行）の指示文を組み立てる。

    python3 scripts/brain/routines.py            … 5 つの指示文を順に印字（共通の頭＋チームのファイル）
    python3 scripts/brain/routines.py コード     … 1 つだけ
    python3 scripts/brain/routines.py --json     … {チーム: 指示文} の JSON（API に渡す形）

原本は `.claude/routines/共通.md`（1 行目の（…）は注なので外す）と `.claude/routines/<チーム>.md`。
API（RemoteTrigger）には Claude のセッションからしか届かないので、このスクリプトは文を組むだけ。
直したあとは、Claude に「routine の指示文を API に当て直して」と言う（knowledge/40-運用/routine.md）。
"""
import io
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DIR = os.path.join(ROOT, ".claude", "routines")
TEAMS = ["コード", "デザイン", "運用", "法務", "資料"]
ALONE = ["全般"]      # 共通の頭を付けない（1 枚で完結する指示文）


def common():
    s = io.open(os.path.join(DIR, "共通.md"), encoding="utf-8").read()
    lines = s.split("\n")
    if lines and lines[0].startswith("（"):
        lines = lines[1:]
    return "\n".join(lines).strip()


def prompt(team):
    body = io.open(os.path.join(DIR, team + ".md"), encoding="utf-8").read().strip()
    if team in ALONE:
        lines = body.split("\n")
        if lines and lines[0].startswith("（"):
            lines = lines[1:]
        return "\n".join(lines).strip() + "\n"
    return common() + "\n\n" + body + "\n"


def main(argv):
    if argv[:1] == ["--json"]:
        print(json.dumps({t: prompt(t) for t in TEAMS + ALONE}, ensure_ascii=False, indent=1))
        return 0
    teams = [a for a in argv if a in TEAMS + ALONE] or TEAMS + ALONE
    for t in teams:
        print("=" * 20, t, "=" * 20)
        print(prompt(t))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
