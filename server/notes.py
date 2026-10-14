# -*- coding: utf-8 -*-
"""特筆事項。講師だけが読む、生徒×教科の短いメモ。

  notes.json = {"<sid>": {"<教科>": {"text": "...", "at": ミリ秒, "by": "<講師のsid>"}}}

どの問題が苦手かは毎日テストの正誤が持つ。ここは**数字に出ないこと**を
1行で残す欄である（「比の文章題で式が立てられない」）。

  ・名前は入れない（誰のことかは sid でしか分からない）
  ・生徒には返さない。書いた講師（by）も画面には返さない
  ・空の文にすると消える。退塾した生徒の記録を消すとき（purge）に一緒に消す
"""

import threading
import time

import paths

MAX_TEXT = 200
SUBJECTS = ("english", "japanese", "math", "science", "social")
_LOCK = paths.GUARD          # 置き場にひとつだけの鍵（スレッドにもプロセスにも効く。paths.Guard）


def _file(school):
    return paths.school_file(school, "notes.json")


def load(school):
    return paths.load(_file(school), None) or {}


def of_student(school, sid):
    """{教科: {"text", "at"}}。"""
    got = load(school).get(sid) or {}
    return {s: {"text": v.get("text", ""), "at": v.get("at", 0)}
            for s, v in got.items() if isinstance(v, dict)}


def put(school, sid, subject, text, by):
    """1教科ぶんを書く。空の文なら消す。書いたあとの、その生徒の分を返す。"""
    if subject not in SUBJECTS:
        raise ValueError("教科が不正です")
    # 改行や連続した空白は1つにまとめる。1行のメモとして扱う。
    text = " ".join(str(text or "").split())[:MAX_TEXT]
    with _LOCK:
        db = load(school)
        mine = db.get(sid) or {}
        if text:
            mine[subject] = {"text": text, "at": int(time.time() * 1000), "by": by}
        else:
            mine.pop(subject, None)
        if mine:
            db[sid] = mine
        else:
            db.pop(sid, None)
        paths.save(_file(school), db)
    return of_student(school, sid)


def drop_student(school, sid):
    with _LOCK:
        db = load(school)
        if db.pop(sid, None) is not None:
            paths.save(_file(school), db)
