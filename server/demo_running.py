#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「正常に運営できている校舎」のデモを作る。

なぜ要るか
----------
デモで「15週の遅れ」「⚠出てない」が並ぶと、見た人は
**このシステムを入れると自分の教室がこう見える**と受け取る。
稟議に出す資料としては逆効果でしかない。

見せるべきは、**まわっている状態**である。

    * 授業計画が学期ぶん入っている
    * 今週ぶんの宿題はもう出ている（格子が埋まっている）
    * 本部カリキュラムとのズレがほぼ無い
    * 生徒には毎週の宿題が届き、やった記録が残っている
    * 紙の宿題にも評価が付いている
    * 気にかけたい生徒が「1〜2名だけ」挙がる（0名では嘘くさい）

最後の1行が肝である。全員が完璧なデモは、見た人に信用されない。
実際の教室には必ず何人か気になる生徒がいる。それが写っていて初めて
「これはうちの教室の話だ」と思える。

    python3 server/demo_running.py --school london

**このスクリプトは架空のデータしか作らない。** 実在の生徒は入れない。
"""

import argparse
import io
import json
import os
import hashlib
import math
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                    # noqa: E402
import lessons as L                             # noqa: E402
import syllabus as SY                           # noqa: E402
import exams as E                              # noqa: E402
import reference_curriculum as refcur           # noqa: E402
import datetime as _dt_mod                      # noqa: E402
import curriculum_source as SOURCE              # noqa: E402
import tube_server as T
import ratescale                         # noqa: E402
import courses as C                             # noqa: E402
import submissions as SUBM                       # noqa: E402
import presets as PS                            # noqa: E402

DAY = 86400

# ------------------------------------------------------------------
# ロンドン校の実データ（Claude outputs/SEED-ロンドン校.md の写し）
#
# **直すときは SEED のほうも直すこと。** SEED は人が読む記録で、
# ここは機械が読む写しである。表の形は SEED の章と同じ並びにしてある。
# ------------------------------------------------------------------

# 1章 教材台帳。id → (名前, 教科, 学年, 採点するか)。どれも紙で解く。
SEED_MATERIALS = {
    "yos-e4-math":   ("予習シリーズ 小4下 算数", "math", ["e4"], True),
    "yos-e4-jpn":    ("予習シリーズ 小4下 国語", "japanese", ["e4"], True),
    "yos-e5-math":   ("予習シリーズ 小5下 算数", "math", ["e5"], True),
    "enshu-e4-math": ("演習問題集 小4下 算数", "math", ["e4"], True),
    "enshu-e4-jpn":  ("演習問題集 小4下 国語", "japanese", ["e4"], True),
    "enshu-e5-math": ("演習問題集 小5下 算数", "math", ["e5"], True),
    "keisan-yos":    ("計算テキスト（予習シリーズ）", "math", ["e4", "e5"], False),
    "kiso-print":    ("基礎力強化プリント", "math", ["e4", "e5"], True),
    "kanji-kotoba":  ("漢字とことば", "japanese", ["e4"], True),
    "shin-e6-math":  ("新小学問題集 小6 算数", "math", ["e6"], True),
    "pyramid":       ("計算ピラミッド", "math", ["e6"], False),
    "shin-j1-jpn":   ("新中学問題集 中1 国語", "japanese", ["j1"], True),
    "shin-j1-sci":   ("新中学問題集 中1 理科", "science", ["j1"], True),
    "shin-j2-jpn":   ("新中学問題集 中2 国語", "japanese", ["j2"], True),
    "shin-j2-sci":   ("新中学問題集 中2 理科", "science", ["j2"], True),
    "shin-j2-math":  ("新中学問題集 中2 数学", "math", ["j2"], True),
    "enshu-j2-math": ("演習問題集 中2 数学", "math", ["j2"], True),
    "kanji-note":    ("漢字練習帳", "japanese", ["j1", "j2"], False),
    "sirius-j2":     ("Sirius21 中2", "english", ["j2"], True),
    "jack21":        ("Jack21", "english", ["j2"], True),
    "grit2500":      ("Vocabulary GRIT 2500", "english", ["j1", "j2", "j3"], False),
    "joui-reg":      ("上位校の数学 レギュラー", "math", ["j3"], True),
    "joui-adv":      ("上位校の数学 アドバンス", "math", ["j3"], True),
    "joui-reg-test": ("上位校の数学 レギュラー 確認テスト", "math", ["j3"], True),
}

# 3章 コース（全部の枠）。(コースID, 教科, 名前, 学年, 在籍クラス)。
# 在籍クラスが None のコースは指名（土特・必勝・難プロ・特講・オンライン・動画）。
FRAMES = [
    ("e1j", "japanese", "小1J 国語", ["e1"], ["e1j"]),
    ("e1j", "math", "小1J 算数", ["e1"], ["e1j"]),
    ("e2j", "japanese", "小2J 国語", ["e2"], ["e2j"]),
    ("e2j", "math", "小2J 算数", ["e2"], ["e2j"]),
    ("e3j", "japanese", "小3J 国語", ["e3"], ["e3j"]),
    ("e3j", "math", "小3J 算数", ["e3"], ["e3j"]),
    ("e3j", "science", "小3J 理科", ["e3"], ["e3j"]),
    ("e3j", "social", "小3J 社会", ["e3"], ["e3j"]),
    ("e4a", "japanese", "小4α 国語", ["e4"], ["e4a"]),
    ("e4a", "math", "小4α 算数", ["e4"], ["e4a"]),
    ("e4b", "japanese", "小4β 国語", ["e4"], ["e4b"]),
    ("e4b", "math", "小4β 算数", ["e4"], ["e4b"]),
    ("e4", "english", "小4 英語", ["e4"], ["e4a", "e4b", "e4k"]),
    ("e4", "science", "小4 理科", ["e4"], ["e4a", "e4b", "e4k"]),
    ("e4", "social", "小4 社会", ["e4"], ["e4a", "e4b", "e4k"]),
    ("e4o", "math", "小4 オンライン 算数", ["e4"], None),
    ("e5a", "japanese", "小5α 国語", ["e5"], ["e5a"]),
    ("e5a", "math", "小5α 算数", ["e5"], ["e5a"]),
    ("e5b", "japanese", "小5β 国語", ["e5"], ["e5b"]),
    ("e5b", "math", "小5β 算数", ["e5"], ["e5b"]),
    ("e5k", "japanese", "小5K 国語", ["e5"], ["e5k"]),
    ("e5", "english", "小5 英語", ["e5"], ["e5a", "e5b", "e5k"]),
    ("e5", "science", "小5 理科", ["e5"], ["e5a", "e5b", "e5k"]),
    ("e5", "social", "小5 社会", ["e5"], ["e5a", "e5b", "e5k"]),
    ("e5o", "japanese", "小5 オンライン 国語", ["e5"], None),
    ("e5o", "social", "小5 オンライン 社会", ["e5"], None),
    ("e6a", "japanese", "小6α 国語", ["e6"], ["e6a"]),
    ("e6a", "math", "小6α 算数", ["e6"], ["e6a"]),
    ("e6b", "japanese", "小6β 国語", ["e6"], ["e6b"]),
    ("e6b", "math", "小6β 算数", ["e6"], ["e6b"]),
    ("e6k", "japanese", "小6K 国語", ["e6"], ["e6k"]),
    ("e6k", "math", "小6K 算数", ["e6"], ["e6k"]),
    ("e6", "english", "小6 英語", ["e6"], ["e6a", "e6b", "e6k"]),
    ("e6", "science", "小6 理科", ["e6"], ["e6a", "e6b", "e6k"]),
    ("e6", "social", "小6 社会", ["e6"], ["e6a", "e6b", "e6k"]),
    ("e6nanpro", "japanese", "小6 難プロ 国語", ["e6"], None),
    ("e6nanpro", "math", "小6 難プロ 算数", ["e6"], None),
    ("e6nanpro", "science", "小6 難プロ 理科", ["e6"], None),
    ("e6nanpro", "social", "小6 難プロ 社会", ["e6"], None),
    ("e6doku", "japanese", "小6 土特 国語", ["e6"], None),
    ("e6doku", "math", "小6 土特 算数", ["e6"], None),
    ("e56bunpo", "english", "中受英語 文法特講（5・6年）", ["e5", "e6"], None),
    ("e56chobun", "english", "中受英語 長文特講（5・6年）", ["e5", "e6"], None),
    ("edoga", "math", "小学 算数動画", ["e1", "e2", "e3", "e4", "e5", "e6"], None),
    ("j1t", "math", "中1T 数学", ["j1"], ["j1t"]),
    ("j1r", "math", "中1R 数学", ["j1"], ["j1r"]),
    ("j1tr", "japanese", "中1TR 国語", ["j1"], ["j1t", "j1r"]),
    ("j1tr", "english", "中1TR 英語", ["j1"], ["j1t", "j1r", "j1d"]),
    ("j1", "science", "中1 理科", ["j1"], ["j1t", "j1r", "j1d"]),
    ("j1", "social", "中1 社会", ["j1"], ["j1t", "j1r", "j1d"]),
    ("j1d", "japanese", "中1D 国語", ["j1"], ["j1d"]),
    ("j1d", "math", "中1D 数学", ["j1"], ["j1d"]),
    ("j2t", "japanese", "中2T 国語", ["j2"], ["j2t"]),
    ("j2t", "math", "中2T 数学", ["j2"], ["j2t"]),
    ("j2r", "japanese", "中2R 国語", ["j2"], ["j2r"]),
    ("j2r", "math", "中2R 数学", ["j2"], ["j2r"]),
    ("j2tr", "english", "中2TR 英語", ["j2"], ["j2t", "j2r", "j2d"]),
    ("j2", "science", "中2 理科", ["j2"], ["j2t", "j2r", "j2d"]),
    ("j2", "social", "中2 社会", ["j2"], ["j2t", "j2r", "j2d"]),
    ("j2d", "japanese", "中2D 国語", ["j2"], ["j2d"]),
    ("j2d", "math", "中2D 数学", ["j2"], ["j2d"]),
    ("j2ttoku", "math", "中2T 数学特講", ["j2"], None),
    ("jdoga", "math", "中学 数学動画", ["j1", "j2", "j3"], None),
    ("j3t", "japanese", "中3T 国語", ["j3"], ["j3t"]),
    ("j3t", "math", "中3T 数学", ["j3"], ["j3t"]),
    ("j3t", "english", "中3T 英語", ["j3"], ["j3t"]),
    ("j3r", "japanese", "中3R 国語", ["j3"], ["j3r"]),
    ("j3r", "math", "中3R 数学", ["j3"], ["j3r"]),
    ("j3r", "english", "中3R 英語", ["j3"], ["j3r"]),
    ("j3tr", "english", "中3TR 英語", ["j3"], ["j3t", "j3r"]),
    ("j3", "science", "中3 理科", ["j3"], ["j3t", "j3r"]),
    ("j3", "social", "中3 社会", ["j3"], ["j3t", "j3r"]),
    ("j3doku", "math", "中3 土特（RD特） 数学", ["j3"], None),
    ("j3doku", "japanese", "中3 土特 国語", ["j3"], None),
    ("j3sokei", "japanese", "中3 早慶必勝 国語", ["j3"], None),
    ("j3sokei", "math", "中3 早慶必勝 数学", ["j3"], None),
    ("j3sokei", "english", "中3 早慶必勝 英語", ["j3"], None),
    ("j3o", "english", "中3 オンライン 英語", ["j3"], None),
]

# 4章 担当講師の12コース（週14コマ）。
#   hw    1回ぶんのブロック (文, 教材, 分量)。文の {lo}{hi} に範囲が入る
#   weekly 毎週固定 (id, 文, 教材, 1週の量, いまの位置, 周回)
#   top   上位の生徒への上乗せ（在籍クラスの 01〜03 番）
#   named 指名 (在籍クラス, 人数)。01 番から
DEMO_TEACHER = "teacher1"

# ---- 本物の校舎で「ためし用の生徒のぶんだけ」作るときの絞り（demo_trial.py が入れる）。london では None のまま ----
ONLY = None             # 記録を作ってよい生徒の sid の集合。None なら校舎の生徒全員（デモ校）
TEACHER_LID = None      # 「担当講師」のログインID。None なら code + DEMO_TEACHER（lteacher1）
PHOTO_KEYS = None       # 写真（ノート）を作るコースの鍵。None なら KEN_COURSES
SAMPLE_SEATS = ("01", "1")   # 見本の生徒（添削・提出箱・メッセージの相手）の出席番号
SAMPLE_LIDS = None      # 見本の生徒のログインID。None なら DEMO_LOGINS の生徒


def _only(sids):
    """ONLY があれば、その生徒だけに絞る。"""
    return list(sids) if ONLY is None else [s for s in sids if s in ONLY]


def _ken(db, code):
    """担当講師の口座。"""
    return db.get(TEACHER_LID) if TEACHER_LID else db.get(code + DEMO_TEACHER)


def _keep_others(r):
    """評価の台帳のうち、ONLY の生徒以外のぶん（本物の生徒の評価）を残す。ONLY が無ければ空から作る。"""
    if ONLY is None:
        return {}
    out = {}
    for aid, per in (r or {}).items():
        keep = {sid: v for sid, v in (per or {}).items() if sid not in ONLY}
        if keep:
            out[aid] = keep
    return out
# ほかの3人の講師（講師2〜4）。ほかの講師の枠（週1回の架空の宿題が入るコース）を持ち、
# 導入の段階（courses.use_level）の見本にする。(コースの鍵, 段階)
OTHER_TEACHERS = {
    "teacher2": [("e4a:japanese", 1), ("e4b:math", 2), ("e5b:japanese", 3)],
    "teacher3": [("j1r:math", 0), ("j1tr:english", 2), ("j2r:japanese", 4)],
    "teacher4": [("j3r:english", 3), ("j3:social", 1)],
}
# 講師2〜4のコースの時間割（枠だけのコースに時刻を入れ、時間割に出す）。宿題の週1回（OTHER_DAY）とは別。
OTHER_TIMES = {"e4a:japanese": "月16:40-18:10", "e4b:math": "火16:40-18:10", "e5b:japanese": "木16:40-18:10",
               "j1r:math": "水18:20-19:50", "j1tr:english": "火18:20-19:50", "j2r:japanese": "月20:10-21:40",
               "j3r:english": "水20:10-21:40", "j3:social": "金19:30-20:30"}
# ほかの講師のコース（枠だけ）に入れる、デモの架空の宿題。**生徒の画面が、秋の担当の
# 教科（中3なら数学だけ）にならないように。** 週1回、曜日は教科で決める。
# 講師（teachers）は空のまま ―― 秋の講師画面には出ない。
OTHER_DAY = {"japanese": "月", "english": "火", "math": "水", "science": "木", "social": "金"}
OTHER_HW = {
    ("e", "japanese"): "予習シリーズ 国語 p.{lo}-{hi}",
    ("e", "math"): "予習シリーズ 算数 p.{lo}-{hi}",
    ("e", "english"): "英語プリント p.{lo}-{hi}",
    ("e", "science"): "予習シリーズ 理科 p.{lo}-{hi}",
    ("e", "social"): "予習シリーズ 社会 p.{lo}-{hi}",
    ("j", "japanese"): "新中学問題集 国語 p.{lo}-{hi}",
    ("j", "math"): "新中学問題集 数学 p.{lo}-{hi}",
    ("j", "english"): "新中学問題集 英語 p.{lo}-{hi}",
    ("j", "science"): "新中学問題集 理科 p.{lo}-{hi}",
    ("j", "social"): "新中学問題集 社会 p.{lo}-{hi}",
}
KEN_COURSES = [
    {"key": "e4a:math", "time": "水18:20-19:50",
     "hw": [("予習シリーズ 基本問題 p.{lo}-{hi}", "yos-e4-math", 2),
            ("演習問題集 基本問題＋トレーニング p.{lo}-{hi}", "enshu-e4-math", 4)],
     "weekly": [("keisan", "計算テキスト", "keisan-yos", 7, 0, 0)],
     "top": [("基礎力強化プリント p.{lo}-{hi}", "kiso-print", 4)]},
    {"key": "e4b:japanese", "time": "水16:40-18:10",
     "hw": [("予習シリーズ 基本問題 p.{lo}-{hi}", "yos-e4-jpn", 2),
            ("演習問題集 基本問題＋トレーニング p.{lo}-{hi}", "enshu-e4-jpn", 4)],
     "weekly": [("kanji", "漢字とことば 漢字", "kanji-kotoba", 10, 0, 0),
                ("bunpo", "漢字とことば 文法", "kanji-kotoba", 1, 0, 0)]},
    {"key": "e5b:math", "time": "月16:40-18:10 木16:40-18:10", "unit": "月",
     "hw": [("予習シリーズ 基本問題 p.{lo}-{hi}", "yos-e5-math", 2),
            ("演習問題集 基本問題＋トレーニング p.{lo}-{hi}", "enshu-e5-math", 4)],
     "weekly": [("keisan", "計算テキスト", "keisan-yos", 7, 0, 0)],
     "top": [("基礎力強化プリント p.{lo}-{hi}", "kiso-print", 4)]},
    {"key": "e6k:math", "time": "月18:20-19:20",
     "hw": [("新小学問題集 標準問題 p.{lo}-{hi}", "shin-e6-math", 2)],
     "weekly": [("pyramid", "計算ピラミッド", "pyramid", 3, 0, 0)]},
    {"key": "j1:science", "time": "木20:40-21:40",
     "hw": [("新中学問題集 基本問題＋練習問題 p.{lo}-{hi}", "shin-j1-sci", 4)]},
    {"key": "j1d:japanese", "time": "土14:20-15:50",
     "hw": [("新中学問題集 大問2 p.{lo}-{hi}", "shin-j1-jpn", 3)],
     "weekly": [("kanji", "漢字練習帳", "kanji-note", 50, 0, 0)]},
    {"key": "j2d:japanese", "time": "土12:40-14:10",
     "hw": [("新中学問題集 大問2 p.{lo}-{hi}", "shin-j2-jpn", 3)],
     "weekly": [("kanji", "漢字練習帳", "kanji-note", 50, 0, 0)]},
    {"key": "j2:science", "time": "月19:30-20:30",
     "hw": [("新中学問題集 基本問題＋練習問題 p.{lo}-{hi}", "shin-j2-sci", 4)]},
    {"key": "j2tr:english", "time": "火16:40-18:10",
     "hw": [("Sirius21 練成問題・発展問題 p.{lo}-{hi}", "sirius-j2", 3),
            ("Jack21 練成問題・発展問題 p.{lo}-{hi}", "jack21", 4)],
     "weekly": [("grit", "GRIT 100単語＋連語25語", "grit2500", 125, 999, 2500)]},
    {"key": "j2r:math", "time": "火20:10-21:40",
     "hw": [("新中学問題集 p.{lo}-{hi}", "shin-j2-math", 4)],
     "top": [("演習問題集 p.{lo}-{hi}", "enshu-j2-math", 4)]},
    {"key": "j3r:math", "time": "火18:20-19:50 木18:20-19:50",
     "hw": [("レギュラー 例題{lo}-{hi}（予習）", "joui-reg", 3),
            ("アドバンス p.{lo}", "joui-adv", 1),
            ("レギュラー 確認テスト p.{lo}-{hi}", "joui-reg-test", 2)]},
    {"key": "j3doku:math", "time": "土16:00-17:10",
     "hw": [("レギュラー 例題{lo}-{hi}（復習）", "joui-reg", 3)],
     "named": ("j3r", 10)},
]

# 5章 生徒。在籍クラスごとに、01番から受講科目を並べる。
# コースごとの人数が SEED 5章の表と合うようにしてある。
DEMO_STUDENTS = [
    ("e4a", ["国数英理社"] * 12 + ["国数"] * 3),
    ("e4b", ["国数英理社"] * 12 + ["国数"] * 3),
    ("e5b", ["国数英理社"] * 12 + ["国数"] * 3),
    ("e6k", ["国数"] * 6 + ["国数英"] * 4),
    ("j1t", ["国数英理社"] * 3),
    ("j1r", ["国数英理社"] * 3),
    ("j1d", ["国数英理社"] * 2 + ["国数"] * 3),
    ("j2t", ["国数英理社"] * 2),
    ("j2r", ["国数英理社"] * 5 + ["国数英"] * 10 + ["国数"] * 5),
    ("j2d", ["国数英理社"] + ["国数英"] * 2),
    ("j3r", ["国数英理社"] * 9 + ["国数英"] * 6),
]

# 「ためしに見る」の入口。(ログインIDの後ろ, 見出し, 役割, 合言葉)。
# IDの頭には校舎のコード（ロンドン校は l）が付く。**架空のアカウントだけ。**
# 入口のボタンに添える一言（note）。生徒には学年・クラス・受講教科も付く（demo_list）。
DEMO_LOGINS = [
    # 講師は4人（09-23 本人：初期導入を願う講師が実際にいじれるように）。段階の見本を分ける。
    ("teacher1", "講師1（担当12コース）", "teacher", "lantern-4821", "12コース・毎日テストまで"),
    ("teacher2", "講師2（小4・小5 3コース）", "teacher", "quarry-6203", "宿題を出す／写真で提出／添削まで"),
    ("teacher3", "講師3（中1・中2 3コース）", "teacher", "hollow-9174", "紙のまま／写真で提出／毎日テストまで"),
    ("teacher4", "講師4（中3 2コース）", "teacher", "timber-2846", "添削まで／宿題を出す"),
    ("j2r01", "中2R-01（国数英理社）", "student", "harbor-3157", ""),
    ("e4b01", "小4β-01（漢字テスト）", "student", "meadow-2640", "漢字テスト・記述を写真で。添削つき"),
    ("e5b01", "小5β-01（上位）", "student", "willow-5913", "上位の宿題あり"),
    ("j3r01", "中3R-01（土特）", "student", "pebble-7385", "土特あり"),
    ("j1d03", "中1D-03（国数）", "student", "cedar-1478", "組み分けテスト対策の見本"),
]
# 組み分けテスト対策の画面の見本を出す生徒。いつ開いても本番9日前の画面になる
# （tube_server.demo_exam_window）。ほかの生徒は本物の日程どおり。
PREP_SAMPLE = "j1d03"
PREP_SAMPLE_DAYS = 9
# 次の組み分けテスト。講師から「10月中旬」と聞いた日を**仮に**10/17（土）に置く。
# 本物の日付が決まったらここを直し、デモを作り直す。前後は5週ごと。
EXAM_NEXT = "2026-10-17"

# 教材の項目IDを、実際のファイルから作る。
#
# **架空のIDで記録を作ると、講師の個票が空になる。**
# 一覧の「理解度」はIDを見ない集計なので数字が出るが、
# 個票は実際の教材と突き合わせるので0件になり、
# 「押しても更新されていない」という形で見える（実際にそうなった）。
#
# ID の作り方は app/js/content.js と同じにする。
#   <科目コード>:t:<表のslug>   用語
#   <科目コード>:q:<問題文のslug> 選択
CODE = {"english": "en", "science": "sci", "social": "soc",
        "math": "mat", "japanese": "jpn"}


def _slug(t):
    out = []
    for ch in t.lower():
        if ch.isalnum() or "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff":
            out.append(ch)
        else:
            out.append("-")
    return re.sub(r"-+", "-", "".join(out)).strip("-")


def item_ids(grade):
    """その学年で使う教材の項目IDを集める。"""
    import glob
    cur_dir = os.path.join(os.path.dirname(HERE), "app", "content")
    ids = []
    for sub, code in CODE.items():
        for path in glob.glob(os.path.join(cur_dir, sub, "*.js")):
            base = os.path.basename(path)[:-3]
            # その学年のものだけ（e4 / j1n / kanji-j1 のように学年が入る）
            if grade not in base:
                continue
            src = io.open(path, encoding="utf-8").read()
            for kind, letter in (("var T = [", "t"), ("var Q = [", "q")):
                if kind not in src:
                    continue
                body = src.split(kind)[1].split("];")[0]
                for m in re.finditer(r'^\["([^"]*)"', body, re.M):
                    ids.append("%s:%s:%s" % (code, letter, _slug(m.group(1))))
    return ids

def content_units(grade, subject):
    """教材の中に実際にある単元名を、出てくる順に集める。

    Q（選択問題）の5列目が単元名になっている（app/content/*/*.js）。
    **予定の単元名を、教材の単元名と同じにしておく。** そうすると
    「今週やったところ」から問題を引くときに、名前で引ける。
    名前が食い違っていると、範囲を絞れず、学年ぜんぶから出すことになる。

    単元の入っていない教材（漢字・英単語・数学）は空を返す。
    """
    import glob
    cur_dir = os.path.join(os.path.dirname(HERE), "app", "content")
    out = []
    for path in sorted(glob.glob(os.path.join(cur_dir, subject, "*.js"))):
        base = os.path.basename(path)[:-3]
        if grade not in base:
            continue
        src = io.open(path, encoding="utf-8").read()
        if "var Q = [" not in src:
            continue
        body = src.split("var Q = [")[1].split("];")[0]
        for m in re.finditer(r'^\[.*,"([^"]*)"\],?\s*$', body, re.M):
            u = m.group(1)
            if u and u not in out:
                out.append(u)
    return out


# 学年 × 教科ごとの、単元と宿題。
# 宿題は **黒板に書く言葉のまま**にしてある（アプリ用に言い換えない）。
PLANS = {
    "j1": {
        "english": [("be動詞", "My英単語帳 No.1-50 と テキストp.8-11"),
                    ("一般動詞", "My英単語帳 No.51-100 と 基本問題1-3"),
                    ("疑問文", "My英単語帳 No.101-150 と テキストp.16-19"),
                    ("複数形", "My英単語帳 No.151-200 と 基本問題4-6"),
                    ("代名詞", "My英単語帳 No.201-250 と テキストp.24-27"),
                    ("命令文", "My英単語帳 No.251-300 と 基本問題7-9"),
                    ("canの文", "My英単語帳 No.301-350 と テキストp.32-35"),
                    ("現在進行形", "My英単語帳 No.351-400 と 基本問題10-12")],
        "math": [("正負の数", "トレーニング1-3 と 基本問題p.6-9"),
                 ("加減", "トレーニング4-6 と 基本問題p.10-13"),
                 ("乗除", "トレーニング7-9 と 基本問題p.14-17"),
                 ("文字式", "トレーニング10-12 と 基本問題p.20-23"),
                 ("1次方程式", "トレーニング13-15 と 基本問題p.26-29"),
                 ("方程式の利用", "章末問題1-8"),
                 ("比例", "トレーニング16-18 と 基本問題p.34-37"),
                 ("反比例", "トレーニング19-21 と 章末問題9-14")],
        "science": [("植物のなかま", "一問一答1-20 と ノートまとめ"),
                    ("植物のからだ", "一問一答21-40 と 図のかきこみ"),
                    ("身のまわりの物質", "一問一答41-60"),
                    ("気体の性質", "一問一答61-80 と 実験プリント"),
                    ("水よう液", "一問一答81-100 と 計算問題1-6"),
                    ("状態変化", "一問一答101-120"),
                    ("光の性質", "作図プリント1-4"),
                    ("音の性質", "一問一答121-140")],
        "social": [("世界のすがた", "白地図1-2 と 一問一答1-20"),
                   ("世界各地の生活", "一問一答21-40"),
                   ("アジア州", "白地図3 と 一問一答41-60"),
                   ("ヨーロッパ州", "白地図4 と 一問一答61-80"),
                   ("アフリカ州", "白地図5 と 一問一答81-100"),
                   ("北アメリカ州", "白地図6 と 一問一答101-120"),
                   ("南アメリカ州", "白地図7"),
                   ("オセアニア州", "白地図8 と 章末問題")],
        # 漢字と計算は紙の教材にする（source を付けると経路が paper になる）。
        # 紙の宿題が1件も無いデモでは、4段階評価の画面を見せられない。
        "japanese": [("漢字の読み", "漢字ドリル1-4 と 書き取り20字"),
                     ("漢字の書き", "漢字ドリル5-8 と 書き取り20字"),
                     ("言葉の単位", "文法プリント1-2"),
                     ("文の成分", "文法プリント3-4"),
                     ("語句の意味", "漢字ドリル9-12"),
                     ("敬語のきほん", "文法プリント5-6"),
                     ("漢字の総復習", "漢字ドリル13-16"),
                     ("文法の総復習", "文法プリント7-8")],
    },
}
# 小4〜小6・中2・中3は中1と同じ形で、単元名だけ差し替える。
# **基準（本部カリキュラム）がある学年は全部やること。**
# 1学年でも抜けると、その学年だけ「15週遅れ」と出て、
# デモを見た人はそこだけを覚えて帰る。
for g, base in (("e4", "j1"), ("e5", "j1"), ("e6", "j1"),
                ("j2", "j1"), ("j3", "j1")):
    PLANS[g] = {}
    for sub, rows in PLANS[base].items():
        PLANS[g][sub] = [(t + "（" + g[-1] + "年）", hw) for t, hw in rows]


# ------------------------------------------------------------------
# 5週の周期に組み直す
# ------------------------------------------------------------------
# 組み分けテストが5週ごとにあるので、授業も5回で1周する。
#   1〜4回目 … 新しい単元
#   5回目    … その4回の総復習
#
# **単元名は、できるかぎり教材の中の名前に合わせる。** 合っていれば
# 「今週やったところ」から問題を名前で引ける。合っていなければ
# 学年ぜんぶから引くしかなくなる（それでも動くが、範囲が広くなる）。
CYCLE = 5


# 1学期に何回ぶんの予定を作るか。
#
# **足りないと時間割が空白になる。** 単元が5つしかない教科は
# 第6回・第7回のコマが真っ白になり、その週の宿題も出ない。
# 実際そうなった ―― 算数だけ単元が少なく、中2Rと小6αのコマが
# 空欄で表示された。予定は必ずここまで作る。
WEEKS = 12


def to_cycle(grade, subject, rows):
    """素の並びを、4回＋総復習1回 の周期に組み直す。"""
    units = content_units(grade, subject)
    if units:
        # 教材に単元があるなら、そちらを使う。宿題の文は元の並びから借りる。
        src = [(u, rows[i % len(rows)][1]) for i, u in enumerate(units)]
    else:
        src = list(rows)
    if not src:
        return []
    # 単元が足りないぶんは、2周目として「〜（2）」を付けて続ける。
    # 教材の単元をそのまま2度出すより、**何周目かが分かるほうがよい** ――
    # 講師が「先週と同じ表示だ」と迷わずに済む。
    base = list(src)
    lap = 1
    while len(src) < WEEKS:
        lap += 1
        for topic, hw in base:
            if len(src) >= WEEKS:
                break
            src.append(("%s（%d）" % (topic, lap), hw))
    out, block = [], []
    for topic, hw in src:
        block.append((topic, hw))
        out.append({"topic": topic, "hw": hw, "review": False})
        if len(block) == CYCLE - 1:
            names = "・".join(t for t, _ in block)
            out.append({
                "topic": "総復習（" + names[:40] + "）",
                # 総復習の回は、範囲を広く取り直す ―― 4回ぶんをまとめて。
                "hw": block[0][1],
                "review": True,
            })
            block = []
    return out


PLANS_CYCLE = {}
for g, subs in PLANS.items():
    PLANS_CYCLE[g] = {}
    for sub, rows in subs.items():
        PLANS_CYCLE[g][sub] = to_cycle(g, sub, rows)


def example_range(fmt, src, rows, i):
    """「例題{lo}-{hi}」の宿題を、教材の呼び名（例題56-57）にそろえる。

      （予習）… 次の回の例題。次の回が総復習なら、この回の予習は出さない（None）
      （復習）… その回の例題
    """
    k = i + 1 if "予習" in fmt else i
    if k >= len(rows):
        return None
    m = re.match(r"^例題(\d+)-(\d+)$", rows[k].get("label") or "")
    if not m:
        return None
    lo, hi = int(m.group(1)), int(m.group(2))
    return {"text": fmt.format(lo=lo, hi=hi), "source": src, "from": lo, "to": hi}


def make_course_plan(school, key, c, teacher_sid, start, weeks_back, top_sids=None):
    """担当講師のコース1つに授業計画を入れる（KEN_COURSES の形：hw・weekly・top）。

    build_london（デモ校）と demo_trial（本物の校舎の、ためし用の生徒）が同じ道を通る。
    top_sids は上乗せ（上位）を受ける生徒の sid。
    """
    p = L.plan(school, key)
    view = dict(p, start=start)
    per_week = 1 if p.get("unit") == "week" else len(p.get("slots") or [])
    dates = C.dates(view, start, (weeks_back + 12) * per_week)
    topics = [r["topic"] for r in PLANS_CYCLE.get(p["grade"], {}).get(p["subject"], [])
              if not r.get("review")] or ["演習"]
    pos, rows, extra, ti = {}, [], {}, 0

    def block(fmt, src, qty, base, pos=pos):
        lo = pos.get(fmt, base)
        hi = lo + qty - 1
        pos[fmt] = hi + 1
        return {"text": fmt.format(lo=lo, hi=hi), "source": src, "from": lo, "to": hi}

    # 教材の並び（シラバス）があるコースは、そこから組み立てる（server/syllabus/<id>.json）。
    # 今週やった単元（anchor）が今週の授業に乗り、前後は授業1回に単元1つずつ。
    # 総復習の回も教材が決める（行の review）。宿題の文と教材はコースの決まり（c["hw"]）のまま。
    syl = SY.load(SY.default_id(key) or key.replace(":", "-"))
    skip_w = SOURCE.skip_dates(key)
    sched = SY.schedule(syl, lambda st, count, view=view: C.dates(dict(view, start=st), st, count, skip_w)) if syl else []
    plan_start = start
    plan_skip = None
    if sched:
        # 授業日ごとの行。その週の単元を、その週の授業に当てる（週2コマなら2回とも同じ単元）。
        first_day = sched[0][0]
        last_week_end = (_dt_mod.date(*map(int, sched[-1][0].split("-"))) + _dt_mod.timedelta(days=6)).isoformat()
        lds = [x for x in C.dates(dict(view, start=first_day), first_day, 4 * len(sched) + 8, skip_w)
               if x <= last_week_end]
        srows = SY.lesson_rows(syl, sched, lds)
        used = {r["date"] for r in srows}
        plan_skip = sorted(set(skip_w) | {x for x in lds if x not in used})
        plan_start = srows[0]["date"]
        has_ex = any(re.match(r"^例題\d+-\d+$", r["label"]) for r in srows)
        for i, r in enumerate(srows):
            items = []
            for f, sc, q in c["hw"]:
                if has_ex and "例題{lo}-{hi}" in f:
                    ex = example_range(f, sc, srows, i)
                    if ex:
                        items.append(ex)
                    continue
                items.append(block(f, sc, q, 10))
            rows.append({"topic": r["topic"], "label": r["label"], "unit": r["unit"],
                         "review": r["review"], "hw": {"items": items}})
            if c.get("top"):
                extra[i + 1] = {"top": {"items": [block(f, sc, q, 1) for f, sc, q in c["top"]]}}
    else:
        for i, d in enumerate(dates):
            review = C.is_review(view, d)
            topic = "総復習" if review else topics[ti % len(topics)]
            ti += 0 if review else 1
            rows.append({"topic": topic, "review": review,
                         "hw": {"items": [block(f, sc, q, 10) for f, sc, q in c["hw"]]}})
            if c.get("top"):
                extra[i + 1] = {"top": {"items": [block(f, sc, q, 1) for f, sc, q in c["top"]]}}
    L.set_plan(school, key, teacher_sid, "", 0, plan_start, rows, skip=plan_skip)
    with L.paths_lock():
        data = L.load(school)
        pl = data["plans"][key]
        if sched:
            pl["syllabus"] = syl["id"]
            cs = SY.cycle_start(syl, sched)
            if cs:
                pl["cycleStart"] = cs
        for l in (pl.get("lessons") or []):
            if l["n"] in extra:
                l["extraHw"] = extra[l["n"]]
        if c.get("weekly"):
            pl["weekly"] = [{"id": w[0], "text": w[1], "source": w[2], "step": w[3],
                             "at": w[4], "wrap": w[5]} for w in c["weekly"]]
        if c.get("top"):
            pl["extra"] = [{"id": "top", "name": "上位", "students": list(top_sids or [])}]
        L.save(school, data)


def make_simple_plan(school, key, start, weeks_back, fmt=None):
    """枠だけのコースに、週どおりの計画と1行の宿題を入れる（講師の画面には出ない架空の宿題）。
    原本（カリキュラム/カリキュラム.json）に表があればその単元、無ければアプリの教材の単元を回す。"""
    p = L.plan(school, key)
    view = dict(p, start=start)
    fmt = fmt or OTHER_HW.get((p["grade"][0], p["subject"]), "宿題 p.{lo}-{hi}")
    if p["grade"] == "e6":
        fmt = fmt.replace("予習シリーズ", "新小学問題集")
    # 合同の枠（中3TR 英語など）は、在籍クラスの枠（中3R 英語）と同じ生徒に届く。
    # 同じ文・同じ範囲が2件並ばないように、教材を変える。
    if key.split(":")[0].endswith("tr"):
        fmt = {"english": "英語長文プリント p.{lo}-{hi}",
               "japanese": "国語読解プリント p.{lo}-{hi}"}.get(p["subject"], fmt)
    # 原本（カリキュラム/カリキュラム.json）に表のあるコースは、その単元を週どおりに置く。
    syl_o = SY.load(SY.default_id(key))
    skip_o = SOURCE.skip_dates(key)
    sch_o = SY.schedule(syl_o, lambda st, count, view=view: C.dates(dict(view, start=st), st, count, skip_o)) if syl_o else []
    if sch_o:
        first_day = sch_o[0][0]
        end_o = (_dt_mod.date(*map(int, sch_o[-1][0].split("-"))) + _dt_mod.timedelta(days=6)).isoformat()
        lds = [x for x in C.dates(dict(view, start=first_day), first_day, 4 * len(sch_o) + 8, skip_o) if x <= end_o]
        srows = SY.lesson_rows(syl_o, sch_o, lds)
        used = {r["date"] for r in srows}
        rows, lo = [], 10
        for r in srows:
            rows.append({"topic": r["topic"], "label": r["label"], "unit": r["unit"], "review": r["review"],
                         "hw": {"text": fmt.format(lo=lo, hi=lo + 2), "from": lo, "to": lo + 2}})
            lo += 3
        L.set_plan(school, key, "", "", 0, srows[0]["date"], rows,
                   skip=sorted(set(skip_o) | {x for x in lds if x not in used}))
        with L.paths_lock():
            data = L.load(school)
            data["plans"][key]["syllabus"] = syl_o["id"]
            L.save(school, data)
        return
    # 原本に表の無いコース（小4〜小6の英語・Dクラス・講座など）は、アプリの教材の単元を回す（架空）。
    topics = [r["topic"] for r in PLANS_CYCLE.get(p["grade"], {}).get(p["subject"], [])
              if not r.get("review")] or ["演習"]
    rows, lo, ti = [], 10, 0
    for d in C.dates(view, start, weeks_back + 12):
        review = C.is_review(view, d)
        rows.append({"topic": "総復習" if review else topics[ti % len(topics)],
                     "review": review,
                     "hw": {"text": fmt.format(lo=lo, hi=lo + 2), "from": lo, "to": lo + 2}})
        ti += 0 if review else 1
        lo += 3
    L.set_plan(school, key, "", "", 0, start, rows)



def build_london(school, weeks_back=6):
    """生徒・講師・コース・授業計画を、SEED のとおりに作る。

    **アカウントもここで作る。** seed の検査用アカウント（teacher1〜8・
    旧クラス）は検査のためのもので、実際の校舎の形をしていない。
    ほかの講師のコースは講師・時間割なし。デモの生徒がいる枠には、週1回の架空の宿題を入れる。
    """
    import datetime as _dt
    today = _dt.date.today()
    mon = today - _dt.timedelta(days=today.weekday())
    monday = time.mktime(mon.timetuple())
    start = (mon - _dt.timedelta(days=7 * weeks_back)).isoformat()

    code = T.school_code(school)
    for cid, pattern in DEMO_STUDENTS:
        grade = T.gradeOfClass(school, cid)
        for i, subs in enumerate(pattern, 1):
            lid = "%s%s%02d" % (code, cid, i)
            if lid in T.accounts(school):
                # seed が先に作った口座（中2R-01・小4β-01）には受講科目が無く、5科の扱いになっていた
                # （09-23 に意味の検査 expect.py で発覚）。無ければここで入れる。
                db0 = T.accounts(school)
                if "subjects" not in db0[lid]:
                    db0[lid]["subjects"] = C.parse_subjects(subs)
                    T.save_accounts(school, db0)
                continue
            T.add_account(school, lid, T.make_password(), "%02d" % i, "student",
                          grade, cid, subjects=C.parse_subjects(subs))
    # 講師。担当はコースで持つので assign は空の配列（courses.pairs_of の説明）。
    tid = code + DEMO_TEACHER
    if tid not in T.accounts(school):
        T.add_account(school, tid, T.make_password(), "T1", "teacher", "j2", "j2r",
                      classes=["j2r"])
    for tail in OTHER_TEACHERS:
        lid2 = code + tail
        if lid2 not in T.accounts(school):
            T.add_account(school, lid2, T.make_password(), tail.replace("teacher", "T"), "teacher", "j2", "j2r",
                          classes=["j2r"])
    db = T.accounts(school)
    db[tid]["assign"] = []
    for tail in OTHER_TEACHERS:
        db[code + tail]["assign"] = []
    # **sid はログインIDから決める。** 戻すたびに同じ sid になり、「あの生徒」を追える。
    import hashlib
    for lid, acc in db.items():
        if acc.get("role") in ("student", "teacher"):
            h = hashlib.sha1(("demo|%s|%s" % (school, lid)).encode("utf-8")).digest()
            acc["sid"] = "".join("23456789ABCDEFGHJKLMNPQRSTUVWXYZ"[b % 32] for b in h[:8])
    T.save_accounts(school, db)
    ken = db[tid]["sid"]
    by_seat = {(a.get("classId"), a.get("seat")): a["sid"]
               for a in db.values() if a.get("role") == "student"}

    # コース（3章の枠に、4章の担当を重ねる）
    defs, others = {}, []
    ken_keys = {c["key"] for c in KEN_COURSES}
    demo_classes = {cid for cid, _ in DEMO_STUDENTS}
    for cid, sub, name, grades, classes in FRAMES:
        d = {"name": name, "grade": grades[0], "subject": sub, "teachers": [],
             "slots": [], "classes": list(classes or []), "students": [],
             "unit": "lesson", "weekday": 0, "from": "", "to": ""}
        if len(grades) > 1:
            d["grades"] = list(grades)
        key = "%s:%s" % (cid, sub)
        # ほかの講師のコースで、デモの生徒がいるもの。週1回の架空の宿題を入れる（下）。
        if key not in ken_keys and classes and set(classes) & demo_classes:
            d["unit"], d["weekday"] = "week", C.DAY[OTHER_DAY[sub]]
            others.append(key)
        defs[key] = d
    for c in KEN_COURSES:
        d = defs[c["key"]]
        d["teachers"] = [ken]
        d["slots"] = C.parse_slots(c["time"])
        if c.get("unit"):
            d["unit"], d["weekday"] = "week", C.DAY[c["unit"]]
        if c.get("named"):
            ncid, count = c["named"]
            d["students"] = [by_seat[(ncid, "%02d" % i)] for i in range(1, count + 1)
                             if (ncid, "%02d" % i) in by_seat]
    # 講師2〜4の担当。ほかの講師の枠に名前だけ入れる（週1回の架空の宿題はそのまま）。
    for tail, lst in OTHER_TEACHERS.items():
        sid2 = db[code + tail]["sid"]
        for key, _lv in lst:
            if key in defs and sid2 not in defs[key]["teachers"]:
                defs[key]["teachers"].append(sid2)
                if key in OTHER_TIMES:
                    defs[key]["slots"] = C.parse_slots(OTHER_TIMES[key])
    C.upsert(school, sorted(defs.items()))

    # 授業計画（担当の12コースだけ）
    for c in KEN_COURSES:
        klass = (defs[c["key"]].get("classes") or [""])[0]
        top = [by_seat[(klass, "%02d" % i)] for i in (1, 2, 3) if (klass, "%02d" % i) in by_seat]
        make_course_plan(school, c["key"], c, ken, start, weeks_back, top)

    # ほかの講師のコース（枠だけ）。週1回の架空の宿題（OTHER_HW の説明）。
    for key in others:
        make_simple_plan(school, key, start, weeks_back)

    # 毎日テストに出す教科（学年:教科）。生徒ごとには受講科目で絞られる。
    cur = T.curriculum(school)
    plans = cur.setdefault("plans", {})
    for grade, subs in PLANS.items():
        for sub in subs:
            plans.setdefault("%s:%s" % (grade, sub), {}).update({"enabled": True})
    T.save_curriculum(school, cur)
    return sorted(defs), monday


# 混在の見本：この2コースは「紙のまま」（アプリを使わない）。時間割に薄く残り、生徒の画面には教科が出ない。
PAPER_DEMO = ("j2:science", "j1:science")


def mark_app(school, keys):
    """コースごとに導入の段階を明示する。PAPER_DEMO は 0（紙のまま）、ほかは 4（毎日テストまで）。
    講師2〜4のコースは OTHER_TEACHERS の段階（部分導入の見本）。"""
    n = 0
    levels = {key: lv for lst in OTHER_TEACHERS.values() for key, lv in lst}
    for key in keys:
        lv = 0 if key in PAPER_DEMO else levels.get(key, 4)
        if L.set_use(school, key, lv, "demo") and lv > 0:
            n += 1
    return n


def publish_courses_past(school, start):
    """学期のはじめから今日までの宿題を、本番と同じ関数（publish_courses）で出す。

    **デモだけ別の道を通さない。** 別の道にすると、デモで見えない不具合が
    本番で出る（実際、前はデモだけ番号なしでもアプリ扱いになっていた）。
    3日ずつ時計を進めて呼び、出す時が来た回を順に出す。
    出した時刻（assignedAt）だけは、授業日に戻しておく。
    """
    now = time.time()
    t, n = start, 0
    while t < now:
        n += sum(x.get("count", 1) for x in T.publish_courses(school, "demo", now=t))
        t += 3 * DAY
    n += sum(x.get("count", 1) for x in T.publish_courses(school, "demo", now=now))
    dates = {}
    for key, p in C.all_courses(school).items():
        for l in (p.get("lessons") or []):
            dates[(key, l.get("n"))] = l.get("date")
    db = T.assignments(school)
    for a in db.values():
        les = a.get("lesson") or {}
        d = dates.get((les.get("key"), les.get("n")))
        if d and a.get("createdBy") == "plan":
            a["assignedAt"] = int(time.mktime(time.strptime(d, "%Y-%m-%d")) * 1000)
    T.save_assignments(school, db)
    return n


def make_exams(school, monday, weeks_back):
    """組み分けテストの日程を入れる。

    **本物は本部から来る。** ここで入れるのは、講師から聞いた次の1本
    （EXAM_NEXT）から、前後へ5週ごとに並べた日程（土曜）。
    いまが対策の時期でなければ対策の画面は出ない ―― 本番と同じ。
    対策の画面の見本は、見本の生徒（PREP_SAMPLE）にだけ出す。
    """
    import datetime as _dt
    floor = _dt.date.fromtimestamp(monday - weeks_back * 7 * DAY) - _dt.timedelta(days=7)
    d = _dt.date(*map(int, EXAM_NEXT.split("-")))
    step = _dt.timedelta(days=35)
    while d - step >= floor:                  # 学期のはじめの1本まで戻る
        d -= step
    today = _dt.date.today().isoformat()
    rows = []
    # 原本の日程表（小学部の組分け・月例）があれば、それをそのまま使う。
    real = SOURCE.default_exams()
    if real:
        E.save(school, {"exams": real, "prepDays": E.DEFAULT_PREP_DAYS})
        return real
    for _ in range(11):
        # 今日から EXAM_NEXT までの間には置かない。5週の並びは目安で、本物の
        # 間隔はそろっていない ―― 並びどおりに置くと、講師が「次は10月中旬」と
        # 言っているのに、9月に本番が来て対策の画面が出てしまう。
        if not (today <= d.isoformat() < EXAM_NEXT):
            rows.append({"date": d.isoformat(), "name": "組み分けテスト"})
        d += step
    E.save(school, {"exams": rows, "prepDays": E.DEFAULT_PREP_DAYS})
    return rows


def make_materials(school):
    """教材台帳（SEED 1章）。名前・教科・学年・解く場所・採点するか だけを持つ。

    **中身は持たない**（IP.md）。市販教材は名前と範囲だけを扱う。
    """
    items = {}
    for mid, (name, subject, grades, graded) in SEED_MATERIALS.items():
        m = {"name": name, "subject": subject, "grades": list(grades), "mode": "paper"}
        if not graded:
            m["graded"] = False
        items[mid] = m
    paths.save(paths.school_file(school, "materials.json"), {"items": items})
    return len(items)


def make_reference(monday, weeks_back):
    """**仮の**本部カリキュラムを置く。

    本物は本部から受け取るもので、こちらでは作らない。だが基準が
    まったく無いと、進度の画面は「判定できません」しか出せず、
    何を見せる画面なのかが分からない。仮のものを置いて、
    **仮であることを必ず画面に出す**（provisional）。

    中身は PLANS と同じ単元を1週1つずつ。学期のはじめから並べる。
    """
    start = monday - weeks_back * 7 * DAY
    made = 0
    for grade, subs in PLANS_CYCLE.items():
        if SOURCE.reference(grade):           # 原本から出る学年には仮を置かない
            continue
        weeks = []
        n = max(len(rows) for rows in subs.values())
        for i in range(n):
            units = []
            for sub, rows in sorted(subs.items()):
                if i < len(rows):
                    units.append({"subject": sub, "unit": rows[i]["topic"]})
            weeks.append({
                "w": i + 1,
                "from": time.strftime("%Y-%m-%d",
                                      time.localtime(start + i * 7 * DAY)),
                "units": units,
            })
        refcur.save_reference(grade, {
            "grade": grade,
            "name": grade,
            "source": "仮の基準（本部の表が入るまで）",
            "provisional": True,
            "year": time.localtime(start).tm_year,
            "weeks": weeks,
        })
        made += 1
    return made


# 教科ごとに、どれだけ進んでいる／遅れていることにするか（単元の数）。
# ぜんぶ 0 にすると、画面が「同じペース」だけになって何も分からない。
# 現場では教科によってばらつく ―― 行事で潰れる教科、先に進む教科がある。
DRIFT_BY_SUBJECT = {"math": 1, "english": 0, "science": 0,
                    "japanese": -1, "social": -2}


def clear_drift(school):
    """本部カリキュラムとのズレを、ほぼ無い状態にする。

    予定に入れた単元のうち、今週までの回を「実施した」ことにする。
    ズレを 0 に固定はしない ―― 1単元だけ残す。
    完璧に揃ったデモは、見た人に信用されない。
    """
    cur = T.curriculum(school)
    plans = cur.setdefault("plans", {})
    for grade in PLANS:
        ref = refcur.load_reference(grade)
        if not ref:
            continue
        wk = refcur.week_of(ref) or 0
        for w in ref.get("weeks") or []:
            if (w.get("w") or 0) > wk:
                continue
            for u in (w.get("units") or []):
                key = "%s:%s" % (grade, u.get("subject"))
                done = plans.setdefault(key, {}).setdefault("done", [])
                if u.get("unit") not in done:
                    done.append(u["unit"])
    # 教科ごとに、進み・遅れを付ける。
    #   マイナス … 未実施に戻す（遅れている）
    #   プラス   … 先の単元まで実施ずみにする（先に進んでいる）
    for grade, subs in PLANS_CYCLE.items():
        for sub, rows in subs.items():
            key = "%s:%s" % (grade, sub)
            d = plans.setdefault(key, {}).setdefault("done", [])
            n = DRIFT_BY_SUBJECT.get(sub, 0)
            if n < 0:
                for _ in range(-n):
                    if d:
                        d.pop()
            elif n > 0:
                ref = refcur.load_reference(grade) or {}
                names = [u.get("unit") for w in (ref.get("weeks") or []) for u in (w.get("units") or [])
                         if u.get("subject") == sub] or [r["topic"] for r in PLANS_CYCLE[grade][sub]]
                for u in names:
                    if n <= 0:
                        break
                    if u not in d:
                        d.append(u)
                        n -= 1
    T.save_curriculum(school, cur)


HIST_WEEKS = 8            # 生徒の記録をさかのぼる週数（6週以上。宿題の週数（--weeks）と合わせる）


def student_records(school, monday):
    """生徒に「やった記録」を持たせる。

    全員が完璧では信用されない。3つの型を混ぜる。
      よくやる子 … ほぼ毎日、宿題も終わっている
      ふつうの子 … 週3〜4日、宿題は半分ほど
      気になる子 … 週1日、期限切れがある（1クラスに1〜2名）
    """
    random.seed(20260817)
    db = T.accounts(school)
    # **理解度は、クラスの中でばらけていなければならない。**
    #
    # 前は reps と lapse を同じ乱数で振っていたので、誰を見ても
    # だいたい 70% になった。「全員が同じくらい分かっている」
    # クラスは実在しない ―― デモとして最初に嘘に見える所である。
    #
    # 4つの帯に、この割合で分ける（クラスごとに同じ形で並べる）。
    #   25% あたり … 2割   ついていけていない
    #   60% あたり … 3割   half わかる
    #   80% あたり … 3割   だいたい できる
    #  100% あたり … 2割   ほぼ完璧
    # 講師1人が100名近くを持つと、2割の帯は「要注意 20名」になる。
    # デモで見せたいのは「気にかけたい生徒が1〜2名だけ」の教室なので、
    # いちばん下の帯は薄くする（0名にはしない ―― それは嘘くさい）。
    BANDS = [(0.25, 0.04), (0.60, 0.36), (0.80, 0.35), (1.00, 0.25)]
    # 学年ごとに、その学年で使う項目IDをそろえておく
    ids_by_grade = {}
    for g in PLANS:
        got = item_ids(g)
        random.shuffle(got)
        ids_by_grade[g] = got
    asg = list(T.assignments(school).values())
    students = [(lid, a) for lid, a in sorted(db.items())
                if a.get("role") == "student" and not a.get("leftAt")
                and (ONLY is None or a.get("sid") in ONLY)]
    # クラスごとに帯を配る。並び順で切ると、どのクラスも同じ形になる。
    by_class = {}
    for lid, a in students:
        by_class.setdefault(a.get("classId"), []).append(lid)
    band_of = {}
    for cid, lids in by_class.items():
        m = len(lids)
        edges, acc = [], 0.0
        for u, share in BANDS:
            acc += share
            edges.append((u, int(round(m * acc))))
        # **出席番号と成績を結びつけない。**
        # 並び順のまま帯を配ると、01が25%、10が100%と、番号順に
        # きれいに上がっていく。番号は識別のために振ったものなので、
        # 「成績順に並んでいる」と読まれてしまう。配る前に混ぜる。
        order = list(lids)
        random.Random("band:" + str(cid)).shuffle(order)
        prev = 0
        for u, upto in edges:
            for lid in order[prev:upto]:
                band_of[lid] = u
            prev = upto
        for lid in order[prev:]:           # 端数は上の帯に入れる
            band_of[lid] = BANDS[-1][0]

    n = 0
    for i, (lid, a) in enumerate(students):
        # 理解度の帯が、そのまま「どれくらい続けているか」にも効く。
        # よく分かっている子が週1しか開かない、という組み合わせは不自然。
        u = band_of.get(lid, 0.6)
        kind = ("slow" if u <= 0.35 else "good" if u >= 0.95 else "mid")
        sid = a["sid"]
        mine = [x for x in asg if sid in T.students_for(school, x)]
        cards, hw, hist = {}, {}, {}

        # まず、いまも続いている連続日をつくる。
        #
        # ここを乱数まかせにすると直近の数日が空き、画面のいちばん大きな
        # 数字が「0 日つづいている」になる（実際そうなった）。
        # 続けている子が続けているように見えないデモは、
        # やる気の仕掛けを見せる場でいちばん見せてはいけない画面である。
        #
        # きょうの分はわざと入れない ―― まだ1日が終わっていない。
        # アプリ側も「きょう未実施」では連続を切らない作りにしてある。
        run = {"good": 11, "mid": 3, "slow": 0}[kind]
        for d in range(1, run + 1):
            key = time.strftime("%Y-%m-%d", time.localtime(monday - d * DAY))
            did = random.randint(12, 26)
            hist[key] = {"n": did, "ok": max(0, min(did, int(round(did * min(1.0, max(0.1, u + random.uniform(-0.12, 0.08))))))), "done": 1}   # 正解は出題を超えない
        # **学期のはじめ（6週以上前）から**、毎日「開いたか」を決めていく（2026-09-12 本人：
        # 3週間ぶんしか無い生徒が多い。全員に6週以上の記録を、ばらつきを持たせて）。
        #   よくやる子 … 週6日ほど、ふつう … 週3〜4日、気になる子 … 週1〜2日
        #   始めた日は学期のはじめから0〜9日ずれる（全員が同じ日に始めない）
        #   ふつう・気になる子の3割は、途中に1週間の空き（旅行・部活）がある
        #   正解の割合はその子の理解度（u）に寄せ、量は日によって揺れる
        rnd = random.Random("hist:" + sid)
        prob = {"good": 0.86, "mid": 0.52, "slow": 0.24}[kind]
        first = monday - HIST_WEEKS * 7 * DAY + rnd.randint(0, 6) * DAY
        gap_at = None
        if kind != "good" and rnd.random() < 0.3:
            gap_at = monday - rnd.randint(2, HIST_WEEKS - 1) * 7 * DAY   # その週の月曜から7日休む
        # **日ごとの乱数で決めない。** 1日おきに空く「飛び飛び」の暦は、本物の子の暦に見えない
        # （10-10 本人）。週ごとに「何日やるか」を決め、月曜から続けて埋める。
        #   よくやる子 … 月〜土（1割の週で1日だけ休む）／ふつう … 月〜木か火〜金／気になる子 … 火と木、か 水だけ
        ws = first - ((int(time.localtime(first).tm_wday)) * DAY)       # first の週の月曜
        while ws < monday - run * DAY:
            skip = gap_at is not None and gap_at <= ws < gap_at + 7 * DAY
            if kind == "good":
                days = list(range(0, 6))
                if rnd.random() < 0.1:
                    days.remove(rnd.choice(days))
            elif kind == "mid":
                s0 = rnd.choice([0, 0, 1]); days = list(range(s0, s0 + rnd.choice([3, 4, 4])))
            else:
                days = rnd.choice([[1, 3], [2], [1, 3], [0, 2]])
            for d in days:
                t = ws + d * DAY
                if skip or t < first or t >= monday - run * DAY:
                    continue
                key = time.strftime("%Y-%m-%d", time.localtime(t))
                if key in hist:
                    continue
                did = rnd.randint(12, 28) if kind == "good" else rnd.randint(8, 22)
                ok = int(round(did * min(1.0, max(0.1, u + rnd.uniform(-0.15, 0.1)))))
                hist[key] = {"n": did, "ok": max(0, min(did, ok)),
                             "done": 1 if rnd.random() < {"good": 0.92, "mid": 0.6, "slow": 0.25}[kind] else 0}
            ws += 7 * DAY
        # **どの週にも最低1日はある**（空きの週と今週を除く）。気になる子でも「6週間ぶんの記録」は見える。
        for w in range(1, HIST_WEEKS + 1):
            wk_start = monday - w * 7 * DAY
            if gap_at is not None and wk_start == gap_at:
                continue
            if wk_start < first - 6 * DAY:
                continue
            if not any(time.strftime("%Y-%m-%d", time.localtime(wk_start + k * DAY)) in hist for k in range(7)):
                k = rnd.randint(0, 6)
                key = time.strftime("%Y-%m-%d", time.localtime(wk_start + k * DAY))
                did = rnd.randint(6, 20)
                hist[key] = {"n": did, "ok": max(0, min(did, int(round(did * min(1.0, max(0.1, u)))))), "done": 0}

        # --- 今週（月曜から きょうまで）---
        #
        # **ここを空けてはいけない。** 上の連続日は monday から遡って
        # 作るので、月曜から先が丸ごと空く。土曜に開くと、直近6日が
        # まっさらな画面になる（実際そうなった）。
        #
        # 今週は「やりかけ」の週である。1日ぶんを 0〜80% の範囲で
        # ばらけさせる ―― まだ週の途中なので、やりきった日ばかりでは
        # かえって嘘になる。
        DAILY = 20                       # 1日ぶんの目安（問）
        today_end = time.time()
        for d in range(0, 7):
            t = monday + d * DAY
            if t > today_end:
                break                    # 未来の日は作らない
            key = time.strftime("%Y-%m-%d", time.localtime(t))
            if key in hist:
                continue
            # 今週も週の型で（10-10）：よくやる子は毎日やりきり、きょうだけ途中。ふつうは月〜木。気になる子は火だけ
            is_today = (today_end - t) < DAY
            if kind == "good":
                ratio = random.uniform(0.3, 0.6) if is_today else random.uniform(0.8, 1.0)
            elif kind == "mid":
                if d >= 4 and not is_today:
                    continue
                ratio = random.uniform(0.3, 0.6) if is_today else random.uniform(0.5, 1.0)
            else:
                if d != 1:
                    continue
                ratio = random.uniform(0.2, 0.5)
            # **変数名に n を使わない。** 外側で数えている n を
            # 上書きしてしまい、「生徒の記録 10名」と出た（本当は168名）。
            # 書き出したファイルは168個あるのに、報告だけが嘘になる。
            did = max(1, int(round(DAILY * ratio)))
            hist[key] = {
                "n": did,
                # 正解数はその子の理解度に寄せる。全員同じにしない。
                "ok": max(0, min(did, int(round(did * min(1.0, max(0.1, u)))))),
                # 8割まで進めた日だけ「やりきった」。それ未満は途中まで。
                "done": 1 if ratio >= 0.75 else 0,
            }
        # **実在の項目IDを使う。** 架空のIDだと個票が空になる。
        pool = ids_by_grade.get(a.get("level")) or []
        want = {"good": 0.55, "mid": 0.28, "slow": 0.08}[kind]
        take = pool[:int(len(pool) * want)]
        for iid in take:
            # 「よくやる子」は定着（間隔21日以上）が多め、
            # 「気になる子」は短い間隔にとどまる
            # 上限は5週（35日）。単元確認テストの周期を超えた札は
            # テストの前に出てこないので、デモにも置かない。
            iv = random.choice({"good": [21, 28, 35, 14, 7],
                                "mid":  [7, 14, 21, 3],
                                "slow": [1, 3, 7]}[kind])
            # **正答率がその子の帯になるように lapse を決める。**
            # 理解度 ＝ (reps − lapse) / reps なので、
            # lapse ＝ reps × (1 − 理解度)。少しゆらして、
            # 「ちょうど25%が並ぶ」不自然さを避ける。
            reps = random.randint(3, 10)
            ui = min(1.0, max(0.05, u + random.uniform(-0.06, 0.06)))
            lapse = int(round(reps * (1.0 - ui)))
            lapse = max(0, min(reps, lapse))
            cards[iid] = [iv, 2.5, 0, reps, lapse,
                          int(monday - random.randint(0, HIST_WEEKS * 7) * DAY), 1]

        # 提出のわりあいが 50〜100% に収まるようにする。
        # デモで 11% と出ると「うちの教室はこうなるのか」と読まれる。
        # 実際の教室でも、出ている宿題の半分以上は返ってくる。
        # 1人ずつ「出したか」を決める。kind ごとに確率を変えると、
        # クラス全体では 50〜100% のあいだに散る。
        # **回っている教室の提出率。**
        # 前は 0.97 / 0.82 / 0.60 で、クラス全体が73%あたりに落ちた。
        # よく回している教室は9割前後 ―― 声をかける相手が1〜2名という形。
        # 10割にはしない。全員が毎回出す教室は実在しない。
        rate = {"good": 0.99, "mid": 0.92, "slow": 0.74}[kind]
        for x in mine:
            if x["dueAt"] / 1000 > monday + 7 * DAY:
                continue
            # **やった番号は、その宿題の範囲の中でなければならない。**
            # 範囲外の番号を入れても進捗は 0% のまま出る
            # （実際、No.1200-1250 の宿題に 0〜49 を書いていて全教科0%だった）。
            lo, hi = int(x.get("from") or 0), int(x.get("to") or 0)
            if x.get("route") == "paper" or not (lo and hi):
                continue                      # 紙の宿題。アプリ側の記録は持たない
            nums = list(range(lo, hi + 1))
            if random.random() < rate:
                hw[x["id"]] = {"done": {str(v): 1 for v in nums},
                               "startedAt": x["assignedAt"],
                               "completedAt": x["assignedAt"] + 2 * DAY * 1000}
            else:
                # 途中まで。「気になる子」ほど手前で止まる
                far = {"good": 0.9, "mid": 0.7, "slow": 0.5}[kind]
                cut = max(1, int(len(nums) * random.uniform(far * 0.5, far)))
                hw[x["id"]] = {"done": {str(v): 1 for v in nums[:cut]},
                               "startedAt": x["assignedAt"], "completedAt": None}

        blob = {"cards": cards, "hw": hw, "hist": hist,
                "grade": a.get("level"), "classId": a.get("classId"),
                "streak": {"good": 12, "mid": 4, "slow": 0}[kind]}
        paths.save(T.progress_path(school, sid),
                   {"sid": sid, "rev": 3, "savedAt": int(monday * 1000), "blob": blob})
        T.update_summary(school, sid, blob, mine)
        n += 1
    return n


# 生徒の力と単元のむずかしさで、評価を決める（架空）。**ばらばらの乱数にしない。**
# 乱数だけだと、どのコースも理解度70〜80%に平らになり、講師の画面に
# 「テコ入れ候補」も「気にかけたい生徒」も出ない ―― 画面の使いみちが見えない。
# 実際のクラスも、力のある子はどの単元もよく、むずかしい単元はクラス全体が下がる。
HARD_UNITS = {("j2r:math", 4): -1.2, ("e5b:math", 6): -1.1, ("j2tr:english", 6): -0.8}


def demo_mark(key, n, sid):
    ability = random.Random("ability|%s" % sid).gauss(3.9, 0.8)
    # 1割ほどは、どの単元でも苦戦している子（成績の画面で「気にかけたい生徒」に出る）
    if random.Random("weak|%s" % sid).random() < 0.12:
        ability -= 1.3
    ability = max(1.3, min(5.3, ability))
    diff = random.Random("unit|%s|%s" % (key, n)).gauss(0, 0.3) + HARD_UNITS.get((key, n), 0.0)
    x = ability + diff + random.gauss(0, 0.45)
    return int(max(1, min(5, int(x + 0.5))))


def paper_ratings(school):
    """紙の宿題に評価を付ける。ただし全員には付けない。

    全員に付いているデモは、かえって嘘くさい。
    「つけた分だけ記録に残る」という設計がそのまま見える状態にする。
    """
    # **期限が来ていない宿題には付けない。** ノートを集めるのは締切のあと。
    # 付けてしまうと、生徒の画面に「来週まで／みてもらいました」と並び、
    # 見た講師がまず「これは何だ」と止まる。
    now = time.time() * 1000
    asg = [a for a in T.assignments(school).values()
           if (a.get("route") or "app") == "paper"
           and a.get("dueAt") and a["dueAt"] < now]
    # 新しいものから。学期はじめの宿題に評価だけ付いている状態は不自然。
    asg.sort(key=lambda x: -(x.get("dueAt") or 0))
    # **前回の評価を持ち越さない。** 持ち越すと、作り直したあとも
    # 消えた宿題の評価が残り、期限前の宿題に評価が付いて見える。
    r = _keep_others(T.ratings(school))      # 本物の校舎では、本物の生徒の評価は残す
    random.seed(7)
    n = 0
    same = {}          # 同じ回の紙（束）には、同じ子に同じ印
    # **クラス × 教科**ごとに、直近の紙の宿題4件に付ける。
    #
    # 前はクラスだけで束ねていた。1つのクラスが算数と国語を持つと、
    # 直近4件が算数に偏り、国語の提出率が 0/10 と並んだ。
    # 講師が見るのは自分の教科の列なので、そこで切る。
    # 学期のはじめから今週まで、期限の来たものは全部つける（最大8件）。
    # 4件で切ると、いちばん古い回だけ 0/10 のまま残る。それは
    # 「誰もやらなかった」と読まれる ―― 実際には記録していないだけ。
    by_pair = {}
    for a in asg:
        by_pair.setdefault((a.get("classId"), T.subject_of_assignment(a)),
                           []).append(a)
    # **回している先生を基準にする。**
    #
    # 前は毎回 40〜100% にだけ付けていた。すると、どの回も
    # 「評価 7/10」で終わり、**期限の過ぎた宿題がぜんぶ「採点待ち」に
    # 残る**（採点待ち 60件と出た）。1学期ぶん採点をためている先生は、
    # 見習うべき姿ではない。
    #
    # よく回している先生は、**先週までのぶんは付け終えている。**
    # 残っているのは今週の1回だけ。だから期限からの日数で分ける。
    #
    #   10日より前  … 全員に付いている（出していない子には 0）
    #   10日以内    … まだ途中。ここが「採点待ち」になる
    # 手元に残っている仕事は、**枠の3割ぶんだけ**。
    #
    # 「全部の枠の最新回が途中」にすると、担当12枠の講師で
    # 採点待ちが12件になる。それは回している姿ではない。
    # ふつうは、今週すでに手を付けた枠と、まだの枠が混ざっている。
    now_s = time.time()
    for k, rows in by_pair.items():
        busy = random.Random("busy|%s|%s" % k).random() < 0.3
        # 今日チェックを終えた枠（「今日おわったもの」に出る）。忙しい枠は除く。
        done_today = (not busy) and random.Random("today|%s|%s" % k).random() < 0.25
        for i, a in enumerate(rows):          # 学期のはじめから全部（8週ぶんの推移が図に出る）
            per = r.setdefault(a["id"], {})
            sids = _only(T.students_for(school, a))
            if not sids:
                continue
            if i == 0 and busy:
                # 今週の分で、まだ手を付けていない枠。ここが採点待ち。
                share = random.uniform(0.0, 0.6)
            else:
                # それ以外は **全員ぶん付け終えている。**
                share = 1.0
            take = int(len(sids) * share + 0.5)
            for i, sid in enumerate(sids):
                if i >= take:
                    break
                # 出していない子には 0（出ていない）。**これも評価である。**
                # 付けないままにすると、その回は永久に「採点待ち」に残る。
                bk = ((a.get("lesson") or {}).get("key"), (a.get("lesson") or {}).get("n"), sid)
                if bk[0] and bk in same:
                    v = same[bk]
                else:
                    # 5段階（ratescale.py）。よくできた・できたが多く、もう少し以下が3割ほど。
                    v = 0 if random.random() < 0.06 else demo_mark(bk[0], bk[1], sid)
                    same[bk] = v
                # **付けた時刻は期限のあと。** 全部を「いま」にすると、講師の画面が
                # 「今日つけた評価 378人」になり、今日やったことが読めない。
                due_s = (a.get("dueAt") or 0) / 1000.0
                if a is rows[0] and done_today:
                    at = now_s - random.uniform(0.5, 3) * 3600
                else:
                    at = min(now_s - 6 * 3600, due_s + random.uniform(0.3, 3.0) * 86400)
                per[sid] = {"v": v, "s": 5, "at": int(at), "by": "demo"}
                n += 1
    T.save_ratings(school, r)
    # 評価は要約に効くので、作り直す
    for lid, a in T.accounts(school).items():
        if a.get("role") != "student" or (ONLY is not None and a.get("sid") not in ONLY):
            continue
        blob = (paths.load(T.progress_path(school, a["sid"]), None) or {}).get("blob") or {}
        mine = [x for x in T.assignments(school).values()
                if a["sid"] in T.students_for(school, x)]
        T.update_summary(school, a["sid"], blob, mine)
    return n


def demo_scores(school):
    """塾内テストの点（架空）。担当講師のコースに、単元確認テストを入れる。

    総復習の回（5回ごと）が過ぎたブロックごとに1本。列はそのブロックの4つの単元。
    **名前は入れない。** 席番号から sid に合わせたあとの形（scores.json）で書く。
    点は、その生徒の紙の評価と同じ向きにそろえる（評価がよい子はテストもよい）。
    """
    import scores as SC
    code = T.school_code(school)
    ken = _ken(T.accounts(school), code)
    if not ken:
        return 0
    rt = T.ratings(school)
    asg = list(T.assignments(school).values())
    today = time.strftime("%Y-%m-%d")
    # 本物の校舎では、講師が入れた点はそのまま。架空の点（by demo）だけ作り直す。
    data = SC.load(school) or {}
    data["tests"] = {k: v for k, v in (data.get("tests") or {}).items() if (v or {}).get("by") != "demo"}
    for key, p in sorted(C.of_teacher(school, ken["sid"]).items()):
        mine = [a for a in asg if (a.get("lesson") or {}).get("key") == key]
        sids = _only(sorted({x for a in mine for x in (a.get("students") or [])}))
        if not sids:
            continue
        pct = {}
        for a in mine:
            n = (a.get("lesson") or {}).get("n")
            for sid, r in (rt.get(a["id"]) or {}).items():
                v = ratescale.pct(r)
                if v is not None:
                    pct[(n, sid)] = v
        lessons_ = {int(l["n"]): l for l in (p.get("lessons") or []) if str(l.get("n") or "").isdigit()}
        # 総復習の回は行の review で決める（回の数では決めない）。週2回のコースは同じ週に2回あるので、はじめの1回。
        revs = sorted(n for n, l in lessons_.items() if l.get("review"))
        for rv in [n for n in revs if n - 1 not in revs]:
            l = lessons_[rv]
            if not l.get("date") or not l.get("published"):
                continue
            date = time.strftime("%Y-%m-%d", time.localtime(
                time.mktime(time.strptime(l["date"], "%Y-%m-%d")) + 2 * 86400))
            if date >= today:
                continue
            prev = max([n for n in revs if n < rv] or [0])
            units = [lessons_[n] for n in range(prev + 1, rv)
                     if n in lessons_ and lessons_[n].get("topic") and not lessons_[n].get("review")][-8:]
            if not units:
                continue
            rnd = random.Random("score|%s|%d" % (key, rv))
            hard = {u["n"]: rnd.uniform(-12, 8) for u in units}
            rows = {}
            for sid in sids:
                base = [pct[(u["n"], sid)] for u in units if (u["n"], sid) in pct]
                me = (sum(base) / len(base)) if base else 72
                if rnd.random() < 0.05:
                    continue                  # 欠席
                vals = []
                for u in units:
                    x = me + hard[u["n"]] + rnd.gauss(0, 11)
                    vals.append(float(max(0, min(25, int(round(x / 4.0))))))
                rows[sid] = vals
            tid = "t" + hashlib.sha1(("%s|%d" % (key, rv)).encode("utf-8")).hexdigest()[:8]
            data["tests"][tid] = {
                "key": key, "name": "単元確認テスト（第%d〜%d回）" % (rv - 4, rv - 1),
                "date": date, "kind": "units",
                "cols": [{"label": u["topic"], "max": 25.0, "lessons": [int(u["n"])]} for u in units],
                "rows": rows, "by": "demo", "at": int(time.time())}
    SC.save(school, data)
    return len(data["tests"])


def demo_personal(school):
    """生徒ごとの宿題の決まり（架空）を少しだけ置く。講師の画面で「こう使う」が見えるように。

      小4α 算数   … 1人だけ、毎週の計算テキストを半分に（次に変えるまでずっと）
      中2R 数学   … 理解度の低い単元がある1人に、解き直しを次の回に足す（この回だけ）
    """
    import personal as PR
    code = T.school_code(school)
    ken = T.accounts(school).get(code + "teacher1")
    if not ken:
        return 0
    mine = C.of_teacher(school, ken["sid"])
    asg = list(T.assignments(school).values())
    data = PR.load(school)
    data["rules"] = {}
    PR.save(school, data)
    n = 0
    p = mine.get("e4a:math")
    if p and p.get("weekly"):
        sids = sorted({x for a in asg if (a.get("lesson") or {}).get("key") == "e4a:math"
                       for x in (a.get("students") or [])})
        if len(sids) > 2:
            w = p["weekly"][0]
            PR.put_rule(school, "e4a:math", sids[2], {
                "kind": "scale", "factor": 0.5, "until": None,
                "match": {"source": w.get("source") or "", "text": w.get("text") or ""},
                "note": "提出が続くように量を半分に"}, ken["sid"], T.next_n_of(p))
            n += 1
    p = mine.get("j2r:math")
    if p:
        rt = T.ratings(school)
        mine_a = [a for a in asg if (a.get("lesson") or {}).get("key") == "j2r:math"
                  and (a.get("route") or "") == "paper" and not a.get("extra")
                  and a.get("graded") is not False]
        low = []
        for a in mine_a:
            for sid, r in (rt.get(a["id"]) or {}).items():
                v = ratescale.value(r)
                if v and v <= 2:
                    low.append(((a.get("lesson") or {}).get("n") or 0, sid, a))
        # 講師が登録した「足す宿題の型」（プリセット）。解き直しは決め打ちしない（本人の指示）。
        # 見本は3つ：同じ教材の発展問題（同じ回）・別の教材の総合問題（決まった範囲）・アプリの復習。
        pd = PS.load(school)
        pd["presets"].pop("j2r:math", None)
        PS.save(school, pd)
        base = mine_a[-1] if mine_a else None
        ps1 = PS.put(school, "j2r:math", {
            "name": "発展問題", "text": "%s 発展問題" % (PR.base_text(base.get("title")).split(" ")[0] if base else "新中学問題集"),
            "source": (base or {}).get("source") or "", "range": "same"}, ken["sid"])
        ps2 = PS.put(school, "j2r:math", {
            "name": "総合問題", "text": "基礎力強化プリント 総合問題", "range": "pages", "pages": "p.40-43"}, ken["sid"])
        PS.put(school, "j2r:math", {"name": "アプリで復習", "range": "app", "count": 10}, ken["sid"])
        if low:
            low.sort(key=lambda x: -x[0])
            seen = set()
            for k, (ln, sid, a) in enumerate(low):
                if sid in seen:
                    continue
                seen.add(sid)
                if len(seen) > 2:
                    break
                PR.put_rule(school, "j2r:math", sid,
                            PS.rule_of(ps1 if len(seen) == 1 else ps2, "once" if len(seen) == 1 else None,
                                       T.next_n_of(p)),
                            ken["sid"], T.next_n_of(p))
                n += 1
    
    # 見本のお知らせ：デモの生徒（中2R-01）に、ひとこと付きの決まり。生徒の「先生から」に
    # 「わかった／質問する」の札が出て、講師の受信箱に返事が届く流れを見せる
    demo_j2r = [a["sid"] for a in T.accounts(school).values() if a.get("role") == "student"
                and a.get("classId") == "j2r" and str(a.get("seat")) in SAMPLE_SEATS]
    p2 = mine.get("j2r:math")
    if demo_j2r and p2:
        try:
            PR.put_rule(school, "j2r:math", demo_j2r[0], {
                "kind": "add", "with": {"text": "5章-2 定理の逆と反例 の復習", "app": {"unit": "定理の逆と反例", "count": 10}},
                "until": None, "note": "苦手な単元の復習", "origin": {"kind": "app", "n": 7},
                "msg": "定理の逆と反例が少し弱いので、その復習をアプリで10問だけ足します。無理のない量にしてあります。"},
                ken["sid"], T.next_n_of(p2), now=time.time() - 2 * DAY)
            n += 1
        except ValueError:
            pass
    # 講師側の見本：受信箱の「宿題の変更のお知らせ」に、もう「わかった」を押した生徒と、
    # 質問が来て止まっている生徒を1人ずつ（中2R-01 以外の中2R の生徒）
    others = sorted([a for a in T.accounts(school).values() if a.get("role") == "student"
                     and a.get("classId") == "j2r" and not a.get("leftAt")
                     and str(a.get("seat")) not in ("01", "1")],
                    key=lambda a: str(a.get("seat")))
    if p2 and len(others) >= 2:
        import messages as M
        nn2 = T.next_n_of(p2)
        try:
            d_ok = PS.rule_of(ps2, None, nn2)
            d_ok["msg"] = "比の計算が安定してきたので、総合問題を少し足します。難しければ授業で言ってください。"
            r_ok = PR.put_rule(school, "j2r:math", others[0]["sid"], d_ok, ken["sid"], nn2, now=time.time() - 3 * DAY)
            PR.ack_rule(school, "j2r:math", others[0]["sid"], r_ok["id"], "ok", now=time.time() - 1 * DAY)
            n += 1
        except ValueError:
            pass
        try:
            d_ask = PS.rule_of(ps1, "once", nn2)
            d_ask["msg"] = "次の回だけ、同じ回の発展問題を足します。時間がかかりそうなら途中まででも大丈夫です。"
            r_ask = PR.put_rule(school, "j2r:math", others[1]["sid"], d_ask, ken["sid"], nn2, now=time.time() - 2 * DAY)
            q = "発展問題は全部やりますか？ それとも奇数番だけでもいいですか？"
            it = M.post(school, others[1]["sid"], "math", "j2r:math", "【宿題の変更について質問】" + q,
                        now=time.time() - 1 * DAY, sender="student")
            PR.ack_rule(school, "j2r:math", others[1]["sid"], r_ask["id"], "ask", q, now=time.time() - 1 * DAY, msg_id=it["id"])
            n += 1
        except (ValueError, PermissionError):
            pass
    # 仮の評価の見本：中2R-01 の英語で、期限から8日以上たった写真ありの回の評価を1つ外す
    # → 生徒の画面に「できました（仮）」が出る（講師の一覧では未評価のまま）
    if demo_j2r:
        sub_db = SUBM.load(school)
        rt2 = T.ratings(school)
        cands = []
        for a in asg:
            if (a.get("lesson") or {}).get("key") != "j2tr:english" or (a.get("route") or "") != "paper":
                continue
            if (a.get("dueAt") or 0) > (time.time() - 9 * DAY) * 1000 or (a.get("dueAt") or 0) < (time.time() - 40 * DAY) * 1000:
                continue
            if (sub_db.get(a["id"]) or {}).get(demo_j2r[0]) and (rt2.get(a["id"]) or {}).get(demo_j2r[0]):
                cands.append(a)
        if cands:
            cands.sort(key=lambda a: -(a.get("dueAt") or 0))
            pick = cands[0]
            les = pick.get("lesson") or {}
            for a in asg:
                if (a.get("lesson") or {}) == les and (a.get("route") or "") == "paper":
                    (rt2.get(a["id"]) or {}).pop(demo_j2r[0], None)
            T.save_ratings(school, rt2)
            sub_db = SUBM.load(school)
            g = (sub_db.get(pick["id"]) or {}).get(demo_j2r[0])
            if g:
                g["seen"] = 0; g["note"] = ""            # 見てもいない（付け忘れ）
                SUBM.save(school, sub_db)
    return n
def essay_box(school):
    """提出箱の見本 その2：小4β 国語の「記述問題」（明日のプレゼンの練習用）。

    「宿題チェック → 添削（印刷して赤を入れる／この画面でペンで赤を入れる）→ 返す → 生徒が見る」を
    講師と生徒を行き来しながら何度でも通せるように：
      小4β-01（デモの生徒）は**まだ出していない** → 生徒側で写真を撮って出す所から見せられる
      写真で出したまま未評価が3人 → 講師側で添削をすぐ試せる
      1人は評価・ひとこと・赤を入れた紙まで返してある → 「返した添削」の見本
    """
    import submissions as SUB
    db = T.accounts(school)
    code = T.school_code(school)
    ken = _ken(db, code) or {}
    if not ken.get("sid"):
        return 0
    plans = C.all_courses(school)
    key = "e4b:japanese"
    if key not in plans:
        return 0
    demo = {a["sid"] for a in db.values() if a.get("role") == "student" and a.get("classId") == "e4b"
            and str(a.get("seat")) in SAMPLE_SEATS}
    rate = T.ratings(school)
    try:
        r = _quiz_at(school, T.make_quiz(school, key, plans[key], "記述問題 説明文の最終問（100字）",
                        int((time.time() - 1 * DAY) * 1000), ken["sid"]), 2.0)
    except ValueError:
        return 0
    others = _only(sorted(x for x in (r.get("students") or []) if x not in demo))
    made = 0
    for i, sid in enumerate(others[:4]):
        page = [{"kind": "png", "data": _genko_png(800, 600, "%s|%s" % (r["id"], sid), fill=(0.30, 0.42))}]
        try:
            SUB.put(school, r["id"], sid, page)
            if i == 3:                                   # 返した見本
                rate.setdefault(r["id"], {})[sid] = {"v": 4, "s": 5, "at": int(time.time() - 3600), "by": ken["sid"]}
                SUB.mark_seen(school, r["id"], sid, ken["sid"], "理由が本文の言葉で書けています。「〜から。」で結ぶと満点です。")
                SUB.put_return(school, r["id"], sid,
                               [{"kind": "png", "data": _mark_png(800, 600, "%s|%s" % (r["id"], sid), base=lambda w, h, s: _genko_png(w, h, s, fill=(0.30, 0.42)))}],
                               ken["sid"], None)
        except (ValueError, OSError):
            continue
        made += 1
    T.save_ratings(school, rate)
    # デモの生徒（小4β-01）の、ほかの期限切れの紙の宿題（担当外のコースの分）は出したことにする。
    # 出していない古いものが残っていると、ホームの「いまやるなら これ」がそちらになり、
    # 作文が主役にならない（プレゼンで最初に押す札は作文にしたい）。
    nowms = time.time() * 1000
    sub_db = SUB.load(school)
    for d_sid in demo:
        for a in T.assignments(school).values():
            if (a.get("route") or "") != "paper" or a["id"] == r["id"] or a.get("graded") is False:
                continue
            if not (0 < (a.get("dueAt") or 0) < nowms):
                continue
            if d_sid not in T.students_for(school, a):
                continue
            if (sub_db.get(a["id"]) or {}).get(d_sid):
                continue
            # 出した時刻は期限の少し前（「いま」だと、学期ぶんの宿題が「返ってきたもの」に今日の新着で並ぶ。10-09）
            put_at = int(min(time.time() - 3600, (a.get("dueAt") or 0) / 1000.0 - random.Random("put|%s|%s" % (a["id"], d_sid)).uniform(0.2, 1.5) * 86400))
            try:
                ew, eh = _dims(T.subject_of_assignment(a))
                SUB.put(school, a["id"], d_sid, [{"kind": "png", "data": _note_png(ew, eh, "%s|%s|done" % (a["id"], d_sid))}], now=put_at)
            except (ValueError, OSError):
                continue
            # 写真を出したことにした回に「未提出（0）」の評価が残ると、講師の宿題チェックに
            # 「期限が来た未評価」として古い回が残る（10-10 expect.py で発覚）。評価と見た印も付ける。
            r0 = (rate.get(a["id"]) or {}).get(d_sid)
            if not r0 or not r0.get("v"):
                les = a.get("lesson") or {}
                seen_at = int(min(time.time() - 3600, put_at + 86400))
                rate.setdefault(a["id"], {})[d_sid] = {"v": demo_mark(les.get("key"), les.get("n"), d_sid) or 4, "s": 5, "at": seen_at, "by": "demo"}
                SUB.mark_seen(school, a["id"], d_sid, "demo", "", now=seen_at)
    T.save_ratings(school, rate)
    return made



def _quiz_at(school, rec, days_before):
    """提出箱（漢字テスト・作文）の「出した日」を期限の少し前にする。make_quiz は「いま」で作るので、
    先週のテストが「今日の宿題」と出ていた（10-09）。"""
    if not rec:
        return rec
    at = int((rec.get("dueAt") or 0) - days_before * DAY * 1000)
    asg = T.assignments(school)
    if rec.get("id") in asg:
        asg[rec["id"]]["assignedAt"] = at
        T.save_assignments(school, asg)
    rec["assignedAt"] = at
    return rec

MESSAGE_TEXTS = (
    ("いつもありがとうございます。家では計算問題を急いで解いて、途中の式を飛ばしがちです。授業でも一言いただけると助かります。",
     "ご連絡ありがとうございます。授業でも「1行ずつ書く」と声をかけていきます。宿題の評価にも書き添えますね。"),
    ("習い事で木曜の宿題が遅れがちです。金曜までにまとめて出しても大丈夫でしょうか。", None),
)


def demo_messages(school, pairs=None):
    """保護者からのメッセージの見本（中2R-01：返事つき／小5β-01：未読）。
    pairs は (在籍クラス, 教科) の並び（2つまで。1つ目は返事つき、2つ目は未読）。"""
    import messages as M
    db = T.accounts(school)
    code = T.school_code(school)
    ken = _ken(db, code) or {}
    n = 0
    for (cid, sub), (text, ans) in zip(pairs or RETURN_PAIRS, MESSAGE_TEXTS):
        stu = [a for a in db.values() if a.get("role") == "student" and a.get("classId") == cid and str(a.get("seat")) in SAMPLE_SEATS]
        if not stu:
            continue
        key = C.key_for(school, cid, sub, stu[0].get("level") or "")
        try:
            it = M.post(school, stu[0]["sid"], sub, key, text, now=time.time() - 2 * DAY)
            n += 1
            if ans and ken.get("sid"):
                M.reply(school, it["id"], ken["sid"], ans, None, now=time.time() - 1.5 * DAY)
        except (ValueError, PermissionError):
            continue
    return n


def restore_demo_passwords(school):
    """「ためしに見る」の合言葉を DEMO_LOGINS のとおりにし、一覧を書き出す。

    作り直すと全員の合言葉が新しくなる。ログイン画面のボタンは
    demo-accounts.json の合言葉で入るので、戻さないと入れなくなる。
    一覧は <ROOT>/demo-accounts.json に書く（手元のサーバの --demo が読む。
    検査 expect.py --accounts も、この合言葉で入る）。
    **本番の入口の一覧は、これではない。** deploy/ためしに見る.json（ID だけ。本物の講師と
    ためし用の生徒）を 更新.sh が置き、ボタンは POST /api/demo/enter に ID だけを送る
    （2026-10-10）。demo-swap は、本番の一覧がこの校舎の口座だけのときにしか上書きしない。
    """
    code = T.school_code(school)
    db = T.accounts(school)
    rows = []
    for tail, label, role, pw, note in DEMO_LOGINS:
        lid = code + tail
        if lid not in db:
            continue
        T._set_password(db, lid, pw)
        rows.append({"id": lid, "password": pw, "label": label, "role": role, "note": note})
        if tail == PREP_SAMPLE:
            db[lid]["examDemoDays"] = PREP_SAMPLE_DAYS
        else:
            db[lid].pop("examDemoDays", None)
    T.save_accounts(school, db)
    paths.save(os.path.join(paths.ROOT, "demo-accounts.json"), rows)
    return len(rows)



def _dims(subject):
    """写真の向き（幅, 高さ）。**国語は横長、ほかの教科は縦長**（2026-10-11 本人：国語以外は全て縦長、国語のみ全て横長。
    過去問も縦）。縦書きの紙（原稿用紙・漢字テスト）は横長の紙に書く。"""
    return (760, 560) if subject == "japanese" else (560, 760)


def _note_png(w, h, seed):
    """ノートらしい絵を1枚つくる。**写真は用意できないので描く。**

    デモに実物の答案は置けない（実在の生徒の字を使うわけにいかない）。
    かといって真っ白だと、講師の画面で「見る」を試せない。
    罫線と、鉛筆らしい線だけを描いた紙を作る。
    """
    import struct
    import zlib
    rnd = random.Random(seed)
    bg = (250, 249, 245)
    line = (206, 214, 226)
    ink = (44, 48, 58)
    px = [[bg] * w for _ in range(h)]
    for y in range(28, h - 10, 26):                 # 罫線
        for x in range(14, w - 14):
            px[y][x] = line
    # 書いた線は太く・多く（縮めた札（約 90px）でも鉛筆の跡が見えるように。10-10 本人「写真が真っ白」）
    for _ in range(rnd.randint(18, 30)):
        y = rnd.randrange(30, h - 16)
        x0 = rnd.randrange(20, w // 2)
        x1 = min(w - 16, x0 + rnd.randrange(60, w // 2 + 60))
        for x in range(x0, x1):
            for dy in (0, 1, 2, 3):
                if 0 <= y + dy < h:
                    px[y + dy][x] = ink

    def chunk(tag, data):
        c = tag + data
        return (struct.pack(">I", len(data)) + c +
                struct.pack(">I", zlib.crc32(c) & 0xffffffff))

    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in px)
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw, 6)) +
            chunk(b"IEND", b""))


def _genko_png(w, h, seed, fill=(0.55, 0.72)):
    """原稿用紙に書いた作文らしい絵。**実物の字は使えないので描く。**

    縦書きのマス目（20字×20行）に、鉛筆らしい短い線の集まりを字のかわりに置く。
    右端の列が題名（3マス下げ）、次の列は名前の欄で**空けておく**（名前は写さない）。
    本文は3列目から、6〜7割まで埋める。
    **紙は横長（800×600）で、マスは正方形。** 本物の原稿用紙（B4 横）と同じ向き。前は縦長の紙に縦長のマスを
    描いていて、講師の画面で「縦になっている」と見えた（2026-10-11 本人）。"""
    import struct
    import zlib
    rnd = random.Random("genko|%s" % seed)
    bg = (252, 251, 247)
    grid = (212, 204, 188)
    ink = (56, 58, 66)
    px = [[bg] * w for _ in range(h)]
    cols, rows = 20, 20
    mx, my = 44, 44
    cw = ch = min((w - 2 * mx) // cols, (h - 2 * my) // rows)      # 正方形のマス。紙の真ん中に置く
    gx0 = (w - cols * cw) // 2
    my = (h - rows * ch) // 2

    def dot(x, y, c=ink):
        if 0 <= x < w and 0 <= y < h:
            px[y][x] = c

    for c in range(cols + 1):                         # 縦のけい
        x = gx0 + c * cw
        for y in range(my, my + rows * ch + 1):
            dot(x, y, grid)
    for r in range(rows + 1):                         # 横のけい
        y = my + r * ch
        for x in range(gx0, gx0 + cols * cw + 1):
            dot(x, y, grid)
    for x in range(gx0, gx0 + cols * cw + 1):         # 真ん中の折り目（原稿用紙らしさ）
        if x % 6 < 3:
            dot(x, my + rows * ch // 2, grid)

    def glyph(cx, cy):                                # マスの中に2〜4本の短い線
        for _ in range(rnd.randint(2, 4)):
            kind = rnd.random()
            x0 = cx + rnd.randint(5, max(6, cw - 9))
            y0 = cy + rnd.randint(5, max(6, ch - 9))
            L = rnd.randint(max(4, cw // 3), max(5, cw - 9))
            if kind < .45:                            # 横
                for x in range(x0, min(cx + cw - 4, x0 + L)):
                    dot(x, y0); dot(x, y0 + 1)
            elif kind < .8:                           # 縦
                for y in range(y0, min(cy + ch - 4, y0 + L)):
                    dot(x0, y); dot(x0 + 1, y)
            else:                                     # 斜め
                for k in range(L):
                    dot(x0 + k * 2 // 3, min(cy + ch - 4, y0 + k))

    filled = int(cols * rows * rnd.uniform(fill[0], fill[1]))
    k = 0
    for c in range(cols):                             # 右の列から
        cx = gx0 + (cols - 1 - c) * cw
        for r in range(rows):
            cy = my + r * ch
            if c == 0:
                if r < 3 or r > 12:                   # 題名：3マス下げて10字ほど
                    continue
            elif c == 1:
                continue                              # 名前の欄は空ける
            else:
                if k >= filled:
                    break
                if rnd.random() < 0.08:               # 句読点・改行のあき
                    continue
                k += 1
            glyph(cx, cy)
        if c >= 2 and k >= filled:
            break

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)

    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in px)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def _mark_png(w, h, seed, base=None):
    """赤を入れた答案。_note_png の紙に、赤丸・赤の下線・欄外の赤い書き込みを重ねる。

    デモの「添削を返す」で生徒が開く紙。本物の添削は講師が印刷して赤を入れ、撮り直して返す。
    """
    import struct
    import zlib
    rnd = random.Random("mark|%s" % seed)
    src = (base or _note_png)(w, h, seed)
    # _note_png の画素を戻す（IDAT を解いて行ごとに）
    i = 8
    raw = b""
    while i < len(src):
        ln = struct.unpack(">I", src[i:i + 4])[0]
        tag = src[i + 4:i + 8]
        if tag == b"IDAT":
            raw += src[i + 8:i + 8 + ln]
        i += 12 + ln
    flat = zlib.decompress(raw)
    stride = w * 3 + 1
    px = [[tuple(flat[y * stride + 1 + x * 3: y * stride + 4 + x * 3]) for x in range(w)] for y in range(h)]
    red = (214, 40, 40)

    def dot(x, y):
        if 0 <= x < w and 0 <= y < h:
            px[y][x] = red

    def circle(cx, cy, r):
        for t in range(0, 360, 2):
            a = math.radians(t)
            for k in (0, 1):
                dot(int(cx + (r + k) * math.cos(a)), int(cy + (r + k) * math.sin(a)))

    def stroke(x0, y0, x1, y1):
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        for k in range(n + 1):
            x = x0 + (x1 - x0) * k // n
            y = y0 + (y1 - y0) * k // n
            for dy in (0, 1, 2):
                dot(x, y + dy)

    for _ in range(rnd.randint(3, 5)):               # 赤丸（できている所）
        circle(rnd.randrange(60, w - 60), rnd.randrange(60, h - 60), rnd.randint(14, 22))
    for _ in range(rnd.randint(2, 3)):               # 赤の下線（直す所）
        y = rnd.randrange(40, h - 40)
        x0 = rnd.randrange(20, w // 2)
        stroke(x0, y, min(w - 20, x0 + rnd.randrange(60, 200)), y)
    for _ in range(rnd.randint(2, 4)):               # 欄外の書き込み（波線）
        y = rnd.randrange(40, h - 40)
        x0 = rnd.randrange(w // 2, w - 120)
        for x in range(x0, x0 + 100):
            dot(x, y + int(3 * math.sin(x / 4.0)))
    stroke(w - 90, 40, w - 60, 70)                   # 右上のチェック
    stroke(w - 60, 70, w - 30, 30)

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)

    out = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in px)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(out, 6)) + chunk(b"IEND", b""))


RETURN_PAIRS = (("j2r", "math"), ("e5b", "math"))


def returned_papers(school, pairs=None):
    """添削を返した見本：デモの生徒（中2R-01 数学・小5β-01 算数）の最新の写真に、赤を入れた紙を返す。

    生徒の「先生から」に「添削された答案を見る」が出て、講師の宿題チェックには「返した添削」が出る。
    pairs は (在籍クラス, 教科) の並び。本物の校舎（demo_trial）は担当コースから渡す。
    """
    import submissions as SUB
    db = T.accounts(school)
    code = T.school_code(school)
    ken = _ken(db, code) or {}
    n = 0
    for cid, sub in (pairs or RETURN_PAIRS):
        stu = [a for a in db.values() if a.get("role") == "student" and a.get("classId") == cid
               and str(a.get("seat")) in SAMPLE_SEATS]
        if not stu:
            continue
        sid = stu[0]["sid"]
        mine = SUB.of_student(school, sid)
        asg = T.assignments(school)
        cands = [(aid, got) for aid, got in mine.items()
                 if got.get("files") and T.subject_of_assignment(asg.get(aid) or {}) == sub and asg.get(aid)]
        cands.sort(key=lambda x: (asg[x[0]].get("dueAt") or 0), reverse=True)
        for aid, got in cands[:1]:
            rw, rh = _dims(sub)
            pages = [{"kind": "png", "data": _mark_png(rw, rh, "%s|%s|%d" % (aid, sid, k))}
                     for k in range(len(got["files"]))]
            try:
                SUB.put_return(school, aid, sid, pages, ken.get("sid") or "demo",
                               "赤で直した所を見て、もう一度解いてみましょう。")
                n += 1
            except (ValueError, OSError):
                continue
    return n


KANJI_SAY = {5: "とめ・はね・はらいまで丁寧です。この調子。", 4: "とめ・はねが丁寧です。「候」の点を忘れずに。",
             3: "はらいが短くなりがちです。赤を見て、もう一度書きましょう。"}


def quiz_box(school):
    """提出箱の見本：小4β 国語の「漢字テスト」（講師 T1 の担当コース）。

    第2回（先週）は全員ぶん済み ―― 評価とひとこと、2人には赤を入れた紙も返してある（履歴の見本）。
    第3回（今週。期限は昨日）は練習用：
      小4β-01（デモの生徒）は評価・ひとこと・添削まで返してある → 生徒側で「添削された答案」を見せられる
      写真で出したまま未評価の子が3人、先生が取り込んだ紙が2人 → 講師側で「印刷 → 赤を入れて撮る → 返す」を何度でも試せる
      残りは出していない
    """
    import submissions as SUB
    db = T.accounts(school)
    code = T.school_code(school)
    ken = _ken(db, code) or {}
    if not ken.get("sid"):
        return 0
    plans = C.all_courses(school)
    key = "e4b:japanese"
    if key not in plans:
        return 0
    demo = [a["sid"] for a in db.values() if a.get("role") == "student" and a.get("classId") == "e4b"
            and str(a.get("seat")) in SAMPLE_SEATS]
    rate = T.ratings(school)
    made = 0

    qw, qh = _dims(plans[key].get("subject"))

    def pages(rec, sid, tag="q"):
        return [{"kind": "png", "data": _note_png(qw, qh, "%s|%s|%s" % (rec["id"], sid, tag))}]

    def marked(rec, sid):
        return [{"kind": "png", "data": _mark_png(qw, qh, "%s|%s|q" % (rec["id"], sid))}]

    # 第2回：先週。全員済み
    try:
        r2 = _quiz_at(school, T.make_quiz(school, key, plans[key], "漢字テスト 第2回", int((time.time() - 8 * DAY) * 1000), ken["sid"]), 2.0)
    except ValueError:
        r2 = None
    if r2:
        sids = demo + _only(sorted(x for x in (r2.get("students") or []) if x not in demo))
        for i, sid in enumerate(sids):
            if i % 5 == 4:
                continue                                   # 出していない子も少し
            try:
                if i % 2 == 0:
                    SUB.put(school, r2["id"], sid, pages(r2, sid), now=int(time.time() - 7.5 * DAY))
                else:
                    SUB.put_by_teacher(school, r2["id"], sid, pages(r2, sid), ken["sid"])
            except (ValueError, OSError):
                continue
            v = 3 + (i % 3)
            rate.setdefault(r2["id"], {})[sid] = {"v": v, "s": 5, "at": int(time.time() - 6 * DAY), "by": ken["sid"]}
            SUB.mark_seen(school, r2["id"], sid, ken["sid"], KANJI_SAY[v], now=int(time.time() - 6 * DAY))
            if i in (0, 1):
                SUB.put_return(school, r2["id"], sid, marked(r2, sid), ken["sid"], None, now=int(time.time() - 6 * DAY))
            made += 1
    # 第3回：今週（期限は昨日）。練習用
    try:
        r3 = _quiz_at(school, T.make_quiz(school, key, plans[key], "漢字テスト 第3回", int((time.time() - 1 * DAY) * 1000), ken["sid"]), 2.0)
    except ValueError:
        r3 = None
    if r3:
        sids = demo + _only(sorted(x for x in (r3.get("students") or []) if x not in demo))
        for i, sid in enumerate(sids):
            try:
                if i == 0:                                     # デモの生徒：添削まで返っている
                    SUB.put(school, r3["id"], sid, pages(r3, sid))
                    rate.setdefault(r3["id"], {})[sid] = {"v": 4, "s": 5, "at": int(time.time() - 3600), "by": ken["sid"]}
                    SUB.mark_seen(school, r3["id"], sid, ken["sid"], KANJI_SAY[4])
                    SUB.put_return(school, r3["id"], sid, marked(r3, sid), ken["sid"], None)
                elif i <= 3:                                   # 写真で出したまま（未評価）
                    SUB.put(school, r3["id"], sid, pages(r3, sid))
                elif i <= 5:                                   # 先生が取り込んだ紙（未評価）
                    SUB.put_by_teacher(school, r3["id"], sid, pages(r3, sid), ken["sid"])
                else:
                    continue
            except (ValueError, OSError):
                continue
            made += 1
    T.save_ratings(school, rate)
    return made


# 写真に添える講師のひとこと。**評価にそろえる**：4以上（できました・よくできました）はほめ、
# 3以下は直す所を言う。生徒の「先生のことば」は前向きなひとことを大きく出すので、
# 「よくできました」に「字をもう少し大きく」が付いていると嘘になる。
SAY = [
    "式のとちゅうがていねいです。8番だけ符号に注意。",
    "よく書けています。次は答えに単位を付けましょう。",
    "とちゅうの式がとんでいます。1行ずつ書くと見つけやすい。",
    "計算はあっています。字をもう少し大きく。",
    "見直しの跡があってよいです。この調子。",
]
SAY_GOOD = [SAY[0], SAY[1], SAY[4], "計算も式も正確です。この調子で。"]
SAY_FIX = [SAY[2], SAY[3], "問題文をもう一度読んでから解きましょう。"]
# 教科ごとのひとこと（数学・算数以外）。数学のひとこと（式・符号・単位）を国語や英語に付けない
SAY_SUBJECT = {
    "japanese": {"good": ["字がていねいで読みやすいです。この調子。", "段落の初めの1字下げができています。", "漢字のとめ・はねが丁寧です。"],
                 "fix": ["はらいが短くなりがちです。赤を見て書き直しましょう。", "答えは文の終わりまで書きましょう。", "問いの言葉をもう一度読んでから答えましょう。"]},
    "english": {"good": ["つづりが正確です。この調子。", "文の最初の大文字とピリオドができています。", "音読の跡があってよいです。"],
                "fix": ["三単現の s を忘れずに。", "疑問文の語順をもう一度確かめましょう。", "単語のつづりを声に出して覚えましょう。"]},
    "science": {"good": ["図がきれいに描けています。", "用語が正確です。この調子。"],
                "fix": ["単位を書き忘れています。", "実験の結果と考察を分けて書きましょう。"]},
    "social": {"good": ["地名・人名の漢字が正確です。", "資料の読み取りができています。"],
               "fix": ["年号は前後の出来事とセットで覚えましょう。", "地図で場所を確かめながら解きましょう。"]},
}


def say_pool(subject, good):
    """教科に合ったひとことの候補。数学・算数（と分からない教科）は従来の SAY_GOOD / SAY_FIX"""
    t = SAY_SUBJECT.get(subject or "")
    if t:
        return t["good"] if good else t["fix"]
    return SAY_GOOD if good else SAY_FIX


def align_notes(school):
    """ひとことを**最終的な評価**にそろえる（最後の段で呼ぶ）。

    写真の段（hw_submissions）でそろえても、評価を付けない8%の写真には
    紙の評価の段で付いた値が残っていて、ほめことばに「やり直してみよう」が付くことがあった。
    見本の生徒（DEMO_LOGINS）は、4以上の評価の写真があるのにほめことばが無ければ、
    いちばん新しいものに1つ添える ―― 生徒の画面の「先生のことば」を見せるため。
    """
    import submissions as SUB
    rnd = random.Random("align-notes")
    rate = T.ratings(school)
    asg = T.assignments(school)
    db = SUB.load(school)
    n = 0
    for aid, per in db.items():
        a = asg.get(aid) or {}
        for sid, sub in (per or {}).items():
            note = (sub or {}).get("note")
            if not note or (ONLY is not None and sid not in ONLY):
                continue
            v = ((rate.get(aid) or {}).get(sid) or {}).get("v")
            if not v:                       # 評価なし・未提出（0）はそのまま
                continue
            pool = say_pool(T.subject_of_assignment(a), v >= 4)
            if note not in pool:
                sub["note"] = rnd.choice(pool)
                n += 1
    code = T.school_code(school)
    acc = T.accounts(school)
    samples = SAMPLE_LIDS if SAMPLE_LIDS is not None else [
        code + tail for tail, label, role, pw, note0 in DEMO_LOGINS if role == "student"]
    for lid in samples:
        sid = (acc.get(lid) or {}).get("sid")
        if not sid:
            continue
        mine = [(sub.get("seen") or 0, aid, sub) for aid, per in db.items()
                for s2, sub in (per or {}).items() if s2 == sid and sub and sub.get("seen")]
        if any(sub.get("note") in SAY_GOOD for _t, _a, sub in mine):
            continue
        good = [x for x in mine if (((rate.get(x[1]) or {}).get(sid) or {}).get("v") or 0) >= 4]
        if good:
            good.sort(reverse=True)
            good[0][2]["note"] = rnd.choice(say_pool(T.subject_of_assignment(asg.get(good[0][1]) or {}), True))
            n += 1
    SUB.save(school, db)
    return n


def hw_submissions(school):
    """ノートの宿題を、写真で出した状態をつくる。

    出し方は3通り混ぜる。
      出して、先生が見て、ひとことも返っている
      出したが、まだ見てもらっていない
      出していない

    **全員が出しているデモは嘘になる。** 出していない子がいるからこそ、
    講師の画面の「◯名が出しています」に意味が出る。
    """
    import submissions as SUB

    rnd = random.Random(20260822)
    db = T.accounts(school)
    asg = T.assignments(school)
    rate = T.ratings(school)
    # **クラス×教科ごとに、直近の2回ぶん。**
    #
    # 日付だけで上から14件取ると、たまたま同じ週に並んだ教科
    # （理科と社会）に全部集まり、算数の講師が開いても1件も出ない
    # ―― 実際そうなった。枠ごとに取れば、どの講師が開いても何かある。
    now = time.time() * 1000
    by_slot = {}
    ken = PHOTO_KEYS or {c["key"] for c in KEN_COURSES}
    for a in asg.values():
        if a.get("route") != "paper":
            continue
        # 写真は講師の画面で見るもの。ほかの講師の枠（架空の宿題）には作らない。
        if (a.get("lesson") or {}).get("key") not in ken:
            continue
        if not (0 < (a.get("dueAt") or 0) <= now):
            continue
        k = (a.get("classId"), T.subject_of_assignment(a))
        by_slot.setdefault(k, []).append(a)
    recent = []
    for k, rows in by_slot.items():
        # **件数ではなく、期限で2回ぶん。** 1回に2〜3件出るので、件数で2件取ると
        # 同じ回のもう1件（上位の上乗せなど）だけ写真が無い、ということが起きる。
        dues = sorted({a.get("dueAt") or 0 for a in rows}, reverse=True)[:2]
        recent += [a for a in rows if (a.get("dueAt") or 0) in dues]

    # **写真は授業1回に1回。** 同じ回の紙（2〜3件）は1つの束で、写真は代表の1件に出す
    # （生徒の画面 homework.js head と同じ決まり：上乗せでない件のうち ID のいちばん小さいもの）。
    heads = {}
    for a in asg.values():
        ls = a.get("lesson") or {}
        if a.get("route") != "paper" or a.get("graded") is False or not ls.get("key"):
            continue
        k = (ls["key"], ls.get("n"))
        rank = (1 if a.get("extra") else 0, a["id"])
        if k not in heads or rank < heads[k]:
            heads[k] = rank
    head_ids = {v[1] for v in heads.values()}
    recent = [a for a in recent if a["id"] in head_ids]
    # 同じ回の紙の束（評価を束の全件にそろえるため）
    bundles = {}
    for x in T.assignments(school).values():
        ls = x.get("lesson") or {}
        if ls.get("key") and (x.get("route") or "") == "paper" and x.get("graded") is not False:
            bundles.setdefault((ls.get("key"), ls.get("n")), []).append(x)

    n = 0
    newest = {}
    for a in recent:
        k = (a.get("classId"), T.subject_of_assignment(a))
        if (a.get("dueAt") or 0) > (newest.get(k) or 0):
            newest[k] = a.get("dueAt") or 0
    for a in recent:
        k = (a.get("classId"), T.subject_of_assignment(a))
        # その枠の最新回で、かつ「まだ手を付けていない枠」だけが未確認になる。
        fresh_slot = ((a.get("dueAt") or 0) == newest.get(k)
                      and random.Random("busy|%s|%s" % k).random() < 0.3)
        # 受け取った生徒だけ。合同や指名のコースは classId が在籍クラスではない。
        sids = _only(T.students_for(school, a))
        # **回している先生を基準にする。**
        # 先週までに出された写真は、もう見て返してある。
        # まだ見ていないのは今週の分だけ ―― そこが手元の仕事になる。
        # 前は4割しか見ておらず、未確認が65件たまっていた。
        # 1学期ぶん写真をためている先生は、見習うべき姿ではない。
        for sid in sids:
            r = rnd.random()
            if r > 0.88:
                continue                       # 出していない（1割ほど）
            pages = 1 if rnd.random() < 0.7 else 2
            dw, dh = _dims(T.subject_of_assignment(a))
            files = [{"kind": "png",
                      "data": _note_png(dw, dh, "%s|%s|%d" % (a["id"], sid, k))}
                     for k in range(pages)]
            # 出した時刻は期限の少し前（「いま」にすると、生徒の「返ってきたもの」に学期ぶんの宿題が今日の新着で並ぶ。10-09）
            put_at = int(min(time.time() - 3600, (a.get("dueAt") or 0) / 1000.0 - rnd.uniform(0.2, 1.5) * 86400))
            try:
                SUB.put(school, a["id"], sid, files, now=put_at)
            except (ValueError, OSError):
                continue
            n += 1
            # まだ見ていないのは、**手を付けていない枠の最新回だけ。**
            # 全部の枠の最新回を未確認にすると、担当12枠の講師で
            # 60件たまる。それは回している姿ではない。
            if fresh_slot and rnd.random() < 0.45:
                continue
            note = rnd.choice(say_pool(T.subject_of_assignment(a), True)) if rnd.random() < 0.10 else ""     # ひとことは週に 0〜2 件（10-10 本人）
            # 見たなら評価も付いているのが自然。**束の評価は1つ**（束の全件に同じ値）。
            # 紙の評価（paper_ratings）が付けた値があればそれを使い、無ければ力と単元から決める。
            # 付けた時刻は期限のあと（「いま」にすると、今日つけた評価が何百人にもなる）。
            v = None
            at = int(min(time.time() - 3600, put_at + rnd.uniform(0.5, 2.5) * 86400))
            if rnd.random() < 0.92:
                les = a.get("lesson") or {}
                mates = [x for x in bundles.get((les.get("key"), les.get("n")), [a])
                         if sid in (x.get("students") or [])] or [a]
                have = None
                for x in mates:
                    r0 = (rate.get(x["id"]) or {}).get(sid)
                    if r0 and r0.get("s") == 5 and r0.get("v"):
                        have = r0
                        break
                if have:
                    v, at = have["v"], have["at"]
                else:
                    v = demo_mark(les.get("key"), les.get("n"), sid)
                    at = int(min(time.time() - 6 * 3600,
                                 (a.get("dueAt") or 0) / 1000.0 + rnd.uniform(0.3, 2.0) * 86400))
                for x in mates:
                    rate.setdefault(x["id"], {})[sid] = {"v": v, "s": 5, "at": at, "by": "demo"}
            if note and v is not None:
                note = rnd.choice(say_pool(T.subject_of_assignment(a), v >= 4))
            SUB.mark_seen(school, a["id"], sid, "demo", note, now=at)
    T.save_ratings(school, rate)
    return n


def prep_results(school):
    """対策テストを **2教科だけ**解き終わったことにする。

    なぜ全教科にしないか ―― 解いた教科と まだの教科が
    ならんでいないと、「解くと何が変わるのか」が見えない。
    デモで見せたいのはその差である。

    落とし方も作り込む。**全単元をまんべんなく落とすと苦手が出ない。**
    ある単元だけ集中して落としているほうが、実際の答案に近いし、
    「ここをやり直せ」という指示にも意味が出る。
    """
    import examprep
    import weak as W

    done = 0
    for lid, a in sorted(T.accounts(school).items()):
        if a.get("role") != "student" or a.get("leftAt") or (ONLY is not None and a.get("sid") not in ONLY):
            continue
        grade = a.get("level") or ""
        sid = a["sid"]
        # 生徒ごとに、どの2教科を解き終えたかを変える。
        # 全員が同じ2教科だと、クラス一覧が不自然に揃う。
        rnd = random.Random("prep|" + sid)
        subs = rnd.sample(["english", "japanese", "math", "science", "social"], 2)
        for sub in subs:
            items = examprep.pack_items(sub, grade)
            items = [x for x in items if x.get("dis")]
            if len(items) < 12:
                continue
            rnd.shuffle(items)
            take = items[:rnd.randint(24, 36)]
            # 苦手にする単元を1〜2つ選ぶ。そこは7〜9割落とす。
            units = sorted({x.get("unit") or "" for x in take if x.get("unit")})
            bad = set(rnd.sample(units, min(len(units), rnd.randint(1, 2)))) \
                if units else set()
            rows = []
            for x in take:
                u = x.get("unit") or ""
                miss = rnd.random() < (0.8 if u in bad else 0.12)
                rows.append({"unit": u, "right": not miss, "blank": False})
            W.record(school, sid, sub, rows)
            done += 1
    return done


def main():
    ap = argparse.ArgumentParser(description="まわっている状態のデモを作る")
    ap.add_argument("--school", default="london")
    ap.add_argument("--weeks", type=int, default=None,
                    help="学期が始まってからの週数（6以上）。既定は原本の後期の始まり（最初の授業の週）から今週まで")
    a = ap.parse_args()
    school = a.school
    if a.weeks is None:
        # 原本の日程表の後期の始まりから数える。決め打ち（前は8）だと、夏休み中に架空の授業と記録ができる。
        import datetime as _d
        ts = SOURCE.term_start()
        this_mon = _d.date.today() - _d.timedelta(days=_d.date.today().weekday())
        a.weeks = max(6, (this_mon - _d.date(*map(int, ts.split("-")))).days // 7) if ts else 8

    print("「正常に運営できている」デモを作ります: %s\n" % school)

    global HIST_WEEKS
    HIST_WEEKS = max(6, a.weeks)
    keys, monday = build_london(school, a.weeks)
    # この校舎は架空のデモだという目印。反映のたびに保存時の状態へ戻すとき、
    # 本物の名簿が入った校舎を消さないために確かめる（deploy/デモを作り直す.sh）。
    sj = paths.school_file(school, "school.json")
    info = paths.load(sj, None) or {}
    info["demo"] = True
    paths.save(sj, info)
    print("  コース        %d件（担当講師の %d件に授業計画。ほかは生徒がいる枠に週1回の架空の宿題）"
          % (len(keys), len(KEN_COURSES)))

    rows = make_exams(school, monday, a.weeks)
    nxt = E.next_exam(school)
    print("  組み分けテスト %d本（%s。次は %s）"
          % (len(rows), "原本の日程表" if SOURCE.default_exams() else "**仮**", (nxt or {}).get("date", "―")))

    n = make_materials(school)
    print("  教材台帳      %d件（SEED 1章。名前と範囲だけ）" % n)

    n = make_reference(monday, a.weeks)
    print("  本部の基準    原本から %d学年、仮 %d学年" % (len(refcur.list_references()) - n, n))

    n = mark_app(school, keys)
    print("  アプリを使う   %d コース（%s は紙のまま ―― 混在の見本）" % (n, "・".join(PAPER_DEMO)))

    # 教材の予定（シラバス）で計画が学期の始まりより前から組まれたコースは、その日から出す。
    # 学期の始まりから出すと、前の回が出ないまま残り、成績の単元が減って見える（09-23 に発覚）。
    first = None
    for c in KEN_COURSES:
        st = (L.plan(school, c["key"]) or {}).get("start") or ""
        if st and (first is None or st < first):
            first = st
    pub_from = monday - a.weeks * 7 * DAY
    if first:
        pub_from = min(pub_from, time.mktime(time.strptime(first, "%Y-%m-%d")) - DAY)
    n = publish_courses_past(school, pub_from)
    print("  出した宿題    %d件（学期のはじめから今日まで。本番と同じ関数で）" % n)

    clear_drift(school)
    print("  本部とのズレ  今週までの単元を実施済みに（社会だけ1単元残す）")

    n = student_records(school, monday)
    print("  生徒の記録    %d名（よくやる子／ふつう／気になる子を混ぜる）" % n)

    n = paper_ratings(school)
    print("  紙の評価      %d件（対象の6割だけ。全員に付けない）" % n)

    n = prep_results(school)
    print("  対策テスト    %d件（1人2教科ぶん。にがて単元も作る）" % n)

    n = hw_submissions(school)
    print("  ノートの写真  %d件（見てもらった分・まちの分・出していない分）" % n)
    n = demo_scores(school)
    print("  塾内テスト    %d本（単元確認テスト。点は紙の評価と同じ向き）" % n)
    n = demo_personal(school)
    print("  個別の決まり  %d件（小4α 計算テキストを半分に／中2R プリセットで足す）＋ プリセット3つ" % n)
    n = align_notes(school)
    print("  ひとことの調整  %d件（評価にそろえた）" % n) if False else None
    # 添削と提出箱は、ひとことの調整（align_notes）のあと。先に作ると、漢字テストのひとことが
    # 「式のとちゅうが…」に書き換わる（実際そうなった）。
    n = returned_papers(school)
    print("  返した添削    %d件（中2R-01 数学・小5β-01 算数。赤を入れた紙）" % n)
    n = quiz_box(school)
    n_e = essay_box(school)
    print("  作文の提出箱   %d件（小4β 国語。デモの生徒は未提出・3人が未評価・1人は返した見本）" % n_e)
    print("  提出箱        漢字テスト 第2回・第3回（小4β 国語）%d人ぶん（第2回は済み。第3回は未評価3人＋取り込み2人＝練習用、小4β-01 は添削まで）" % n)
    n = demo_messages(school)
    print("  保護者のメッセージ %d件（見本。返事つき1・未読1）" % n)
    print("  ひとこと      %d件を評価にそろえた（4以上はほめ、3以下は直す所）" % n)

    n = restore_demo_passwords(school)
    if n:
        print("  デモの合言葉  %d人ぶん 書き戻しました" % n)

    print("\n確かめる:")
    print("  python3 server/tube_server.py drift --school %s" % school)
    print("  python3 server/tube_server.py hw --school %s list | head -20" % school)
    print("\n★ 架空のデータだけです。実在の生徒は入っていません。")


if __name__ == "__main__":
    main()
