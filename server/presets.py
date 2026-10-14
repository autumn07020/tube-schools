#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宿題プリセット ―― 講師がコースごとに登録する「足す宿題の型」。

なぜ要るか
----------
成績タブで理解度の低い生徒に足す宿題を、**「解き直し」に決め打ちしない**（2026-09-11 本人）。
講師が、そのコースの教材から「教材＋段（総合問題・発展問題など）＋範囲の決め方」を
1度だけ登録し、以後は選んで出すだけにする。

文で毎回書くと、誰に何を出したかが追えなくなる。プリセットは**名前**を持つので、
生徒の宿題にも、講師の「個別の宿題」の一覧にも、同じ名前で残る。

置き場所
--------
    <ROOT>/schools/<校舎>/presets.json
    {"presets": {"<コースの鍵>": [プリセット, …]}}

プリセット1つ
-------------
    {"id": "p1a2b3c4",
     "name": "発展問題",                  講師が付ける短い名前（画面と生徒の宿題に出る）
     "source": "shin-j2-math",           教材ID（校舎の教材台帳）。分からなければ空
     "text": "新中学問題集 発展問題",     宿題の文の頭（教材名＋段）
     "range": "same" | "pages" | "app", 範囲の決め方
         same  … その教材の同じ回の範囲を写す（授業計画にその教材の範囲があるとき）。
                 無ければ回の名前を添えて出す（「新中学問題集 発展問題（第4回 相似の利用）」）
         pages … 決まった範囲（pages に「p.40-43」「43-49」のように書く）
         app   … アプリの問題（その単元から count 問）
     "pages": "p.40-43",                 pages のとき
     "count": 10,                        app のとき
     "by": "<講師のsid>", "at": 秒}

決まり（personal.py）への写し方は rule_of()。**ここで作った決まりは origin に
プリセットの id と名前を持つ**ので、あとから「このプリセットで出した生徒」が引ける。
"""

import re
import secrets
import threading
import time

import paths

RANGES = ("same", "pages", "app")
RANGE_WORD = {"same": "同じ回の範囲", "pages": "決まった範囲", "app": "アプリの問題"}
MAX_PRESETS = 12            # 1コースあたり。増えすぎると講師が選べない
PID = re.compile(r"^p[0-9a-f]{8}$")
PAGES = re.compile(r"^(p\.|No\.|no\.)?\s*\d{1,4}\s*[-‐－–〜~ー]\s*\d{1,4}$")

_LOCK = paths.GUARD          # 置き場にひとつだけの鍵（スレッドにもプロセスにも効く。paths.Guard）


def _file(school):
    return paths.school_file(school, "presets.json")


def load(school):
    d = paths.load(_file(school), {}) or {}
    if not isinstance(d.get("presets"), dict):
        d["presets"] = {}
    return d


def save(school, d):
    paths.save(_file(school), d)


def list_of(school, key, data=None):
    """コースのプリセット。並びは作った順（押すたびに入れ替えない）。"""
    d = data or load(school)
    return [p for p in (d["presets"].get(key) or []) if isinstance(p, dict) and p.get("id")]


def clean(d, by, now=None):
    """画面から来たプリセットを確かめて、保存してよい形にする。"""
    if not isinstance(d, dict):
        raise ValueError("形式が違います")
    name = str(d.get("name") or "").strip()[:30]
    text = str(d.get("text") or "").strip()[:60]
    rng = str(d.get("range") or "same")
    if rng not in RANGES:
        raise ValueError("範囲の決め方（同じ回・決まった範囲・アプリ）を選んでください")
    if rng == "app":
        text = text or name
        if not name:
            raise ValueError("名前を書いてください")
    else:
        if not text:
            raise ValueError("教材と段（例：新中学問題集 発展問題）を書いてください")
        name = name or text
    pid = str(d.get("id") or "")
    out = {"id": pid if PID.match(pid) else "p" + secrets.token_hex(4),
           "name": name, "text": text, "range": rng,
           "source": str(d.get("source") or "").strip()[:40]}
    if rng == "pages":
        pg = str(d.get("pages") or "").strip().replace(" ", "")[:20]
        if not PAGES.match(pg):
            raise ValueError("範囲は「p.40-43」か「43-49」の形で書いてください")
        out["pages"] = pg
    if rng == "app":
        try:
            cnt = int(d.get("count") or 10)
        except (TypeError, ValueError):
            cnt = 10
        out["count"] = max(3, min(30, cnt))
    out.update({"by": str(by or "")[:40], "at": int(now or time.time())})
    return out


def put(school, key, d, by, now=None):
    """プリセットを1つ保存する（同じ ID なら差し替え）。保存したものを返す。"""
    p = clean(d, by, now)
    with _LOCK:
        data = load(school)
        lst = [x for x in list_of(school, key, data) if x.get("id") != p["id"]]
        if len(lst) >= MAX_PRESETS:
            raise ValueError("このコースのプリセットが多すぎます（%d件まで）。使わないものを消してください" % MAX_PRESETS)
        lst.append(p)
        data["presets"][key] = lst
        save(school, data)
    return p


def remove(school, key, pid):
    with _LOCK:
        data = load(school)
        lst = list_of(school, key, data)
        keep = [x for x in lst if x.get("id") != pid]
        if len(keep) == len(lst):
            return False
        if keep:
            data["presets"][key] = keep
        else:
            data["presets"].pop(key, None)
        save(school, data)
    return True


def find(school, key, pid):
    for p in list_of(school, key):
        if p.get("id") == pid:
            return p
    return None


def rule_of(preset, until, next_n, unit_topic=""):
    """プリセットから、生徒1人の決まり（personal.clean_rule に渡す形）を作る。

    until       "once"（次の回だけ）か None（次に変えるまで）
    unit_topic  アプリの問題を集める単元名（その生徒の弱い単元）。app のときだけ要る
    """
    rng = preset.get("range") or "same"
    text = str(preset.get("text") or "").strip()
    with_ = {"text": text}
    if rng == "same":
        if preset.get("source"):
            with_["copy"] = {"source": preset["source"], "n": None}
    elif rng == "pages":
        with_["text"] = ("%s %s" % (text, preset.get("pages") or "")).strip()
    else:
        topic = str(unit_topic or "").strip()
        if not topic:
            raise ValueError("アプリの問題を集める単元が分かりません")
        with_ = {"text": "%s（%s）" % (preset.get("name") or "復習", topic),
                 "app": {"unit": topic, "count": int(preset.get("count") or 10)}}
    return {"kind": "add", "until": "once" if until == "once" else None, "from": next_n,
            "with": with_,
            "origin": {"kind": "preset", "n": None,
                       "preset": preset.get("id"), "name": preset.get("name")}}


def describe(preset):
    """一覧に出す1行（教材と段 ・ 範囲の決め方）。"""
    rng = preset.get("range") or "same"
    if rng == "pages":
        how = preset.get("pages") or ""
    elif rng == "app":
        how = "アプリ %d問" % int(preset.get("count") or 10)
    else:
        how = RANGE_WORD["same"]
    body = preset.get("text") if rng != "app" else ""
    return " ・ ".join(x for x in (body, how) if x)
