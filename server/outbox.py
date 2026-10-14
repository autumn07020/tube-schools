# -*- coding: utf-8 -*-
"""保護者に「今週の宿題」を知らせるための書き出し（講師×週）。

学習サーバは名前もメールアドレスも持たない。ここで出すのは
「どの席の生徒に、どのコースの、どの宿題が、いつまでか」だけで、
名前と宛先は校舎の対応表（roster-tool/対応表.html）が手元で重ねる。

  入れないもの: 名前・メール・パスワード・点数・評価・先生のひとこと
  （test_outbox.py が、鍵の名前で確かめる）

その講師が teachers にいるコースの宿題のうち、**その週（月〜日）に
出したもの**を、受け取った生徒ごとに並べる。受け取り手は出した時点で
宿題に書き込んであるので、それをそのまま使う（あとで名簿を直しても
「出した相手」は変わらない）。
"""

import datetime as _dt
import re
import time

WEEK = re.compile(r"^(\d{4})-W(\d{2})$")


def week_of(when=None):
    """時刻（秒）→ "2026-W37"（ISO週）。"""
    d = _dt.date.fromtimestamp(time.time() if when is None else when)
    y, w, _ = d.isocalendar()
    return "%d-W%02d" % (y, w)


def week_days(week):
    """"2026-W37" → (月曜, 日曜)。形が違えば ValueError。"""
    m = WEEK.match(week or "")
    if not m:
        raise ValueError("週は 2026-W37 の形で指定してください")
    mon = _dt.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    return mon, mon + _dt.timedelta(days=6)


def _day(ms):
    return _dt.date.fromtimestamp((ms or 0) / 1000.0)


def build(week, teacher_sid, plans, asg, accounts, seat_of=None, now=None):
    """書き出す中身を作る。

    plans    その講師のコース {鍵: 計画}
    asg      宿題の台帳 {id: 宿題}
    accounts 名簿 {ログインID: アカウント}
    退塾した生徒・名簿に無い生徒は出さず、人数だけ残す（dropped）。
    """
    seat_of = seat_of or (lambda a: a.get("seat") or "")
    mon, sun = week_days(week)
    by_sid = {a.get("sid"): a for a in accounts.values()
              if a.get("role") == "student"}
    lines, used, dropped = {}, {}, set()
    for a in asg.values():
        key = (a.get("lesson") or {}).get("key")
        p = plans.get(key)
        if p is None or not (mon <= _day(a.get("assignedAt")) <= sun):
            continue
        used[key] = p.get("name") or key
        line = {"course": used[key], "task": a.get("title") or "",
                "due": _day(a["dueAt"]).isoformat() if a.get("dueAt") else "",
                "extra": bool(a.get("extra"))}
        for sid in a.get("students") or []:
            acc = by_sid.get(sid)
            if not acc or acc.get("leftAt"):
                dropped.add(sid)
                continue
            lines.setdefault(sid, []).append(line)
    students = [{"sid": sid, "classId": by_sid[sid].get("classId") or "",
                 "seat": seat_of(by_sid[sid]),
                 "lines": sorted(ls, key=lambda x: (x["course"], x["due"], x["task"]))}
                for sid, ls in lines.items()]
    students.sort(key=lambda s: (s["classId"], s["seat"], s["sid"]))
    return {"kind": "tube-outbox", "v": 1, "week": week,
            "from": mon.isoformat(), "to": sun.isoformat(),
            "generatedAt": int((time.time() if now is None else now) * 1000),
            "teacher": teacher_sid, "dropped": len(dropped),
            "courses": [{"key": k, "title": t} for k, t in sorted(used.items())],
            "students": students}
