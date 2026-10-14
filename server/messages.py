#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""保護者から講師へのメッセージ（要望など）と、講師の返事。

置き場所  <ROOT>/schools/<校舎>/messages.json   {"items": [メッセージ, …]}
1件       {"id": "m1a2b3c4d5", "sid": 生徒, "subject": 教科, "key": コースの鍵,
           "text": 本文, "at": 秒, "from": "parent",
           "replies": [{"by": 講師のsid, "text": 本文, "at": 秒}],
           "seen": {"teacher": 真偽, "parent": 真偽}}

宛先は**教科を選んで、その教科の担当講師**（本人の判断）。コースの鍵で持つので、
講師の画面は「自分のコースの生徒のメッセージ」だけを引く（担当の境界は courses.of_teacher）。
氏名は持たない（席番号の生徒IDだけ）。本文は 600 字まで、1人 40 件まで。
"""
import secrets
import threading
import time

import paths

MAX_TEXT = 600
MAX_PER_STUDENT = 40
_LOCK = paths.GUARD          # 置き場にひとつだけの鍵（スレッドにもプロセスにも効く。paths.Guard）


def _file(school):
    return paths.school_file(school, "messages.json")


def load(school):
    return paths.load(_file(school), {}) or {}


def save(school, d):
    paths.save(_file(school), d)


def clean_text(t):
    t = str(t or "").strip()
    if not t:
        raise ValueError("本文が空です")
    return t[:MAX_TEXT]


def post(school, sid, subject, key, text, now=None, sender="parent"):
    """保護者（生徒のアプリの中の「保護者の方へ」）からのメッセージを1件足す。
    sender="student" は、宿題の変更への生徒の質問（personal の ack から）。"""
    text = clean_text(text)
    with _LOCK:
        d = load(school)
        items = d.setdefault("items", [])
        if len([x for x in items if x.get("sid") == sid]) >= MAX_PER_STUDENT:
            raise ValueError("メッセージが多すぎます。先生の返事をお待ちください")
        it = {"id": "m" + secrets.token_hex(5), "sid": sid, "subject": str(subject or "")[:24],
              "key": str(key or "")[:48], "text": text, "at": int(now or time.time()),
              "from": str(sender or "parent")[:12], "replies": [], "seen": {"teacher": False, "parent": True}}
        items.append(it)
        save(school, d)
    return it


def of_student(school, sid):
    """その生徒（の保護者）のメッセージ。新しい順。"""
    return sorted([x for x in load(school).get("items") or [] if x.get("sid") == sid],
                  key=lambda x: -(x.get("at") or 0))


def inbox(school, keys):
    """講師の受信箱。keys は担当コースの鍵の集まり（None は全部）。未読を先に、あとは新しい順。"""
    out = [x for x in load(school).get("items") or []
           if keys is None or x.get("key") in keys]
    out.sort(key=lambda x: (bool((x.get("seen") or {}).get("teacher")),
                            -max([x.get("at") or 0] + [r.get("at") or 0 for r in x.get("replies") or []])))
    return out


def unread(school, keys):
    return len([x for x in inbox(school, keys) if not (x.get("seen") or {}).get("teacher")])


def reply(school, mid, by, text, keys, now=None):
    """講師の返事。担当外のコースのメッセージには返せない（PermissionError）。"""
    text = clean_text(text)
    with _LOCK:
        d = load(school)
        for x in d.get("items") or []:
            if x.get("id") == mid:
                if keys is not None and x.get("key") not in keys:
                    raise PermissionError("担当外のコースのメッセージです")
                x.setdefault("replies", []).append({"by": str(by or "")[:40], "text": text,
                                                    "at": int(now or time.time())})
                x["seen"] = {"teacher": True, "parent": False}
                save(school, d)
                return x
    return None


def mark_seen(school, mid, who, keys=None, sid=None):
    """既読にする。who は 'teacher'（担当コースだけ）か 'parent'（自分の生徒だけ）。"""
    with _LOCK:
        d = load(school)
        for x in d.get("items") or []:
            if x.get("id") != mid:
                continue
            if who == "teacher" and keys is not None and x.get("key") not in keys:
                raise PermissionError("担当外のコースのメッセージです")
            if who == "parent" and sid is not None and x.get("sid") != sid:
                raise PermissionError("ほかの生徒のメッセージです")
            x.setdefault("seen", {})[who] = True
            save(school, d)
            return x
    return None


def drop_student(school, sid):
    with _LOCK:
        d = load(school)
        items = d.get("items") or []
        keep = [x for x in items if x.get("sid") != sid]
        if len(keep) != len(items):
            d["items"] = keep
            save(school, d)
