#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紙の宿題の評価 ―― 5段階。

講師はノートを見て、数字キーの 1〜5 で付ける（5 がいちばん良い）。
**生徒の画面には数字を出さず、言葉だけを出す**（app/js/ui-student.js の rateWord）。
1 や 2 が数字で並ぶと、下の子ほど見るのをやめるため。

保存の形（ratings.json）
------------------------
    {"<宿題ID>": {"<sid>": {"v": 0〜5, "s": 5, "at": 秒, "by": 講師のsid}}}

    s は段階の数。**s の無いものは、前の4段階（0〜3）で付けた評価**として読み替える。
    前に付けた評価を書き換えずに残すため（書き換えると、いつ誰が付けたかが消える）。

    0 は「出ていない」。理解度には数えない ―― 出していない子の理解度は分からない。

理解度に直すとき（insight.py）
------------------------------
    5 → 100%   4 → 80%   3 → 60%   2 → 40%   1 → 20%

    3（もう少し）は 70% を下回る。成績のページで単元が黄色になる線と合わせてある。
"""

import time

SCALE = 5

# 講師の画面に出す言葉。生徒の言葉は画面側（学年でかな・漢字を出し分ける）。
LEVELS = {5: "よくできた", 4: "できた", 3: "もう少し",
          2: "がんばろう", 1: "やり直し", 0: "出ていない"}

PCT = {5: 100, 4: 80, 3: 60, 2: 40, 1: 20}

# これ以下を「気にかける合図」とする（がんばろう・やり直し）。
LOW = 2

# 前の4段階（0 出ていない／1 もうすこし／2 できた／3 よくできた）の読み替え。
LEGACY = {3: 5, 2: 4, 1: 2, 0: 0}


def valid(v):
    """保存してよい値か（0〜5 の整数）。bool は数に見えるが弾く。"""
    return isinstance(v, int) and not isinstance(v, bool) and v in LEVELS


def value(r):
    """保存された1件から、5段階の値（0〜5）を返す。読めなければ None。"""
    if not isinstance(r, dict):
        return None
    v = r.get("v")
    if not isinstance(v, int) or isinstance(v, bool):
        return None
    if r.get("s") == SCALE:
        return v if v in LEVELS else None
    return LEGACY.get(v)


def pct(r):
    """理解度（%）。0（出ていない）と読めないものは None。"""
    return PCT.get(value(r))


def is_low(r):
    """気にかける合図か。**0（出ていない）も含める** ―― 出していないのは、いちばん手が要る。"""
    v = value(r)
    return v is not None and v <= LOW


def record(v, by, now=None):
    """保存する1件。**必ず s を付ける**（付けないと4段階として読み替えられる）。"""
    return {"v": int(v), "s": SCALE, "at": int(now or time.time()), "by": by}
