#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""総復習テスト対策の結果から、生徒ごとの苦手をためる。

何のためか
----------
対策の紙を解いて、カメラで丸つけをする。そこで分かるのは
「何問できたか」だけではない ―― **どの単元で落としたか**が分かる。

本番までまだ数日ある。落とした単元が分かっているのに、
点数だけ見せて終わるのはもったいない。

    「英語 20/36。to不定詞で 5問中4問 落としています。
     第4回『不定詞』トレーニング10-12 をやり直してください。
     苦手単元の再テスト（12問・6分）を出しました。」

ここまで言えて、はじめて次の行動につながる。

置き場所
--------
    <ROOT>/schools/<校舎>/weak.json

    {"<sid>": {"english": {"units": {"不定詞": {"w": 4, "n": 5, "at": …,
                                                "fixed": 0}},
                           "score": {"ok": 20, "n": 36, "at": …}}}}

    w      落とした数
    n      出た数
    fixed  そのあと再テストで直せたか（0/1）

**答案の画像は置かない。** 置くのは「単元ごとに何問落としたか」だけ。
カメラの読み取りは端末の中で終わり、送るのはこの集計だけである。
"""

import time

import paths

# 苦手と呼ぶ下限。**1問落としただけでは苦手と言わない。**
# 4択なので、まぐれ当たりもまぐれ外しもある。
MIN_ASKED = 2
MIN_RATE = 0.34        # その単元で3分の1以上落としていたら苦手
# 直せたと見なす正答率。再テストでここを越えたら「対策ずみ」。
FIXED_RATE = 0.8


def _file(school):
    return paths.school_file(school, "weak.json")


def load(school):
    try:
        return paths.load(_file(school), {}) or {}
    except paths.BadPath:
        return {}


def save(school, data):
    paths.save(_file(school), data)


def record(school, sid, subject, rows, when=None):
    """1回ぶんの結果をためる。

    rows は [{"unit": …, "right": True/False, "blank": True/False}, …]。
    **塗り忘れ（blank）は落としたことにしない。** 読めなかっただけで、
    分かっていなかったとは限らない。そこを苦手に数えると、
    写真の写りが悪い日に、できている単元まで苦手になる。
    """
    now = int(when or time.time())
    db = load(school)
    me = db.setdefault(sid, {})
    sub = me.setdefault(subject, {})
    units = sub.setdefault("units", {})

    ok = n = 0
    for r in rows or []:
        if r.get("blank"):
            continue
        n += 1
        if r.get("right"):
            ok += 1
        u = (r.get("unit") or "").strip()
        if not u:
            continue
        cell = units.setdefault(u, {"w": 0, "n": 0, "at": now, "fixed": 0})
        cell["n"] += 1
        cell["at"] = now
        if not r.get("right"):
            cell["w"] += 1
            # もう一度落としたら、直したことにしない。
            cell["fixed"] = 0
    sub["score"] = {"ok": ok, "n": n, "at": now}
    save(school, db)
    return sub


def weak_units(school, sid, subject):
    """苦手な単元。落とした割合の高い順。

    返す1件 {"unit", "w", "n", "fixed"}
    """
    sub = (load(school).get(sid) or {}).get(subject) or {}
    out = []
    for u, c in (sub.get("units") or {}).items():
        n, w = int(c.get("n") or 0), int(c.get("w") or 0)
        if n < MIN_ASKED or not w:
            continue
        if w / float(n) < MIN_RATE:
            continue
        out.append({"unit": u, "w": w, "n": n, "fixed": int(c.get("fixed") or 0)})
    out.sort(key=lambda x: (-(x["w"] / float(x["n"])), -x["w"]))
    return out


def score(school, sid, subject):
    """その教科の対策テストの点。まだ解いていなければ None。"""
    sub = (load(school).get(sid) or {}).get(subject) or {}
    s = sub.get("score")
    return s if s and s.get("n") else None


def mark_fixed(school, sid, subject, units, ok_rate):
    """再テストの結果。よくできていれば「対策ずみ」にする。"""
    if ok_rate < FIXED_RATE:
        return 0
    db = load(school)
    cells = ((db.get(sid) or {}).get(subject) or {}).get("units") or {}
    n = 0
    for u in units or []:
        if u in cells:
            cells[u]["fixed"] = 1
            n += 1
    if n:
        save(school, db)
    return n


def advice(lessons_plan, units):
    """やり直す所を、**授業計画の言葉のまま**返す。

    「教科書のここからここ」を、こちらで作らない。
    講師が黒板に書いた宿題の文（トレーニング10-12 と 基本問題p.14-17）が
    そのまま残っているので、それを引く。**言い換えると別のものになる。**
    """
    out = []
    for u in units:
        for l in (lessons_plan or {}).get("lessons") or []:
            if (l.get("topic") or "") != u:
                continue
            hw = ((l.get("hw") or {}).get("text") or "").strip()
            out.append({"unit": u, "n": l.get("n"), "hw": hw})
            break
        else:
            out.append({"unit": u, "n": None, "hw": ""})
    return out
