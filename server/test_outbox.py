#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""保護者への連絡の書き出し・特筆事項・上位の指名を確かめる。

なぜこの検査が要るか
--------------------
書き出しは校舎の外（保護者へのメール）につながる。**名前や点数が
紛れ込んでも、画面では気づけない**ので、鍵の名前で機械的に確かめる。

  ・その週（月〜日）に出した、その講師のコースの宿題だけが並ぶ
  ・退塾した生徒は出さず、人数だけ残す（dropped）
  ・上乗せ（上位）の宿題には extra が付く
  ・名前・メール・パスワード・点数・評価・ひとことの鍵が、どこにも無い
  ・特筆事項は200字まで。空にすると消える。退塾の記録と一緒に消せる
  ・予定の「上位:」は上乗せの宿題になる。1行の直しで書かなければ消えない
  ・上位の指名は置き換え。ほかの上乗せは残す

    python3 server/test_outbox.py
"""

import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/test-outbox"
os.environ["MYACADY_ROOT"] = ROOT
os.environ["TZ"] = "Europe/London"
time.tzset()
sys.path.insert(0, HERE)
shutil.rmtree(ROOT, ignore_errors=True)

import paths                                     # noqa: E402
import lessons as L                              # noqa: E402
import notes as N                                # noqa: E402
import outbox as O                               # noqa: E402

SCHOOL = "london"
FORBIDDEN_KEYS = {"name", "label", "email", "guardianEmail", "password", "pw",
                  "hash", "score", "scores", "rating", "rated", "rate",
                  "note", "notes", "comment", "loginId", "by"}
ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   %s" % name)
    else:
        ng_n += 1
        print("  ×    %s  %s" % (name, detail))


def ms(text):
    return int(time.mktime(time.strptime(text, "%Y-%m-%d %H:%M")) * 1000)


def keys_in(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from keys_in(v)
    elif isinstance(x, list):
        for v in x:
            yield from keys_in(v)


def test_outbox():
    print("書き出し")
    plans = {"j2tr:english": {"name": "中2TR 英語", "teachers": ["T1"]},
             "e5b:math": {"name": "小5β 算数", "teachers": ["T1"]}}
    accounts = {
        "lj2r01": {"role": "student", "sid": "S1", "classId": "j2r", "seat": "01",
                   "name": "本名が入っていても出ない"},
        "lj2t02": {"role": "student", "sid": "S2", "classId": "j2t", "seat": "02"},
        "lj2r03": {"role": "student", "sid": "S3", "classId": "j2r", "seat": "03",
                   "leftAt": 1},
        "lteacher1": {"role": "teacher", "sid": "T1", "name": "講師"},
    }
    asg = {
        "a1": {"title": "Sirius21 p.25-27", "lesson": {"key": "j2tr:english", "n": 3},
               "students": ["S1", "S2", "S3"], "assignedAt": ms("2026-09-07 17:00"),
               "dueAt": ms("2026-09-14 17:00"), "note": "第3回", "rating": 3},
        "a2": {"title": "発展 p.30", "lesson": {"key": "j2tr:english", "n": 3},
               "students": ["S1"], "assignedAt": ms("2026-09-13 23:00"),
               "dueAt": ms("2026-09-14 17:00"), "extra": "top"},
        "a3": {"title": "先週の分", "lesson": {"key": "j2tr:english", "n": 2},
               "students": ["S1"], "assignedAt": ms("2026-09-06 23:30")},
        "a4": {"title": "ほかの講師のコース", "lesson": {"key": "j3r:math", "n": 1},
               "students": ["S1"], "assignedAt": ms("2026-09-08 10:00")},
        "a5": {"title": "手で出した宿題", "classId": "j2r", "students": ["S1"],
               "assignedAt": ms("2026-09-08 10:00")},
    }
    out = O.build("2026-W37", "T1", plans, asg, accounts, now=0)
    check("週は月曜〜日曜", (out["from"], out["to"]) == ("2026-09-07", "2026-09-13"),
          (out["from"], out["to"]))
    check("生徒はクラス・席の順（退塾した生徒は出ない）",
          [s["sid"] for s in out["students"]] == ["S1", "S2"],
          [s["sid"] for s in out["students"]])
    s1 = out["students"][0]
    check("S1 は2件（先週の分・ほかの講師・手で出した分は入らない）",
          [x["task"] for x in s1["lines"]] == ["Sirius21 p.25-27", "発展 p.30"],
          s1["lines"])
    check("上乗せにだけ extra", [x["extra"] for x in s1["lines"]] == [False, True])
    check("期限は日付で", s1["lines"][0]["due"] == "2026-09-14", s1["lines"][0])
    check("席と在籍クラス", (s1["classId"], s1["seat"]) == ("j2r", "01"))
    check("退塾した生徒は人数だけ", out["dropped"] == 1, out["dropped"])
    check("使ったコースだけ並ぶ",
          out["courses"] == [{"key": "j2tr:english", "title": "中2TR 英語"}],
          out["courses"])
    bad = sorted(set(keys_in(out)) & FORBIDDEN_KEYS)
    check("名前・点数・評価・ひとことの鍵が無い", not bad, bad)
    empty = O.build("2026-W30", "T1", plans, asg, accounts)
    check("出していない週は空の一覧（失敗にしない）",
          empty["students"] == [] and empty["courses"] == [])
    for w in ("2026-37", "2026-W60", ""):
        try:
            O.week_days(w)
            check("形の違う週は断る: %r" % w, False)
        except ValueError:
            check("形の違う週は断る: %r" % w, True)
    check("今の週", O.week_of(ms("2026-09-10 12:00") / 1000) == "2026-W37")


def test_notes():
    print("特筆事項")
    got = N.put(SCHOOL, "S1", "math", "比の文章題で\n  式が立てられない", "T1")
    check("書ける（改行と空白は1つに）",
          got.get("math", {}).get("text") == "比の文章題で 式が立てられない", got)
    check("書いた講師は返さない", "by" not in got["math"])
    got = N.put(SCHOOL, "S1", "english", "あ" * 300, "T1")
    check("200字まで", len(got["english"]["text"]) == 200)
    try:
        N.put(SCHOOL, "S1", "art", "x", "T1")
        check("知らない教科は断る", False)
    except ValueError:
        check("知らない教科は断る", True)
    got = N.put(SCHOOL, "S1", "english", "", "T1")
    check("空にすると消える", "english" not in got and "math" in got, got)
    N.drop_student(SCHOOL, "S1")
    check("退塾の記録と一緒に消える", N.of_student(SCHOOL, "S1") == {}
          and "S1" not in N.load(SCHOOL))


def test_top():
    print("上位の指名と「上位:」")
    data = L.load(SCHOOL)
    data.setdefault("plans", {})["e5b:math"] = {
        "teachers": ["T1"],
        "extra": [{"id": "sat", "name": "土特", "students": ["S8"]},
                  {"id": "top", "name": "上位", "students": ["S9"]}],
        "lessons": [{"n": 1, "date": "2026-09-07", "topic": "比", "hw": {"text": "p.1-3"},
                     "extraHw": {"top": {"text": "発展 p.9"}}}]}
    L.save(SCHOOL, data)
    l = L.edit(SCHOOL, "e5b:math", 1, hw_text="p.1-4")
    check("1行の直しで「上位:」を書かなければ、上乗せは残る",
          (l.get("extraHw") or {}).get("top", {}).get("text") == "発展 p.9", l)
    l = L.edit(SCHOOL, "e5b:math", 1, hw_text="p.1-4｜上位:発展 p.10-11")
    top = (l.get("extraHw") or {}).get("top") or {}
    want = {"text": "発展 p.10-11"}
    rng = L.parse_range("発展 p.10-11")
    if rng:
        want["from"], want["to"] = rng
    want = L._clean_item(want)
    check("「上位:」は上乗せに入る（範囲の読み方は通常の分と同じ）", top == want, (top, want))
    check("通常の分に「上位:」は混ざらない", l["hw"].get("text") == "p.1-4", l["hw"])
    ex = L.set_extra(SCHOOL, "e5b:math", "top", "上位", ["S1", "S2"])
    check("指名は置き換え、ほかの上乗せは残る",
          [(e["id"], e["students"]) for e in ex] == [("sat", ["S8"]), ("top", ["S1", "S2"])], ex)
    l = L.edit(SCHOOL, "e5b:math", 1, hw_text="", stop=True)
    check("止めた回は宿題も上乗せも空で、印（stopped）が付く",
          l.get("stopped") is True and not l.get("hw") and "extraHw" not in l, l)
    l = L.edit(SCHOOL, "e5b:math", 1, hw_text="p.5")
    check("宿題を入れ直すと、止めた印は外れる", "stopped" not in l, l)
    ls = L.set_plan(SCHOOL, "e5:math", "T1", "e5b", 1, "2026-09-07",
                    [{"topic": "比", "hw": {"text": "p.1"},
                      "extraHw": {"top": {"text": "発展 p.2"}, "BAD KEY": {"text": "x"}}},
                     {"topic": "速さ", "hw": {"text": "p.3"}}])
    check("学期ぶんの予定でも上乗せが残る（形の違う鍵は捨てる）",
          list((ls[0].get("extraHw") or {}).keys()) == ["top"], ls[0])
    check("上乗せの無い回には鍵を置かない", "extraHw" not in ls[1], ls[1])
    data = L.load(SCHOOL)
    data["plans"]["e5:math"]["lessons"][1]["date"] = "2026-09-21"   # 「ずらす」で1週後ろへ
    L.save(SCHOOL, data)
    ls = L.set_plan(SCHOOL, "e5:math", "T1", "e5b", 1, "2026-09-07",
                    [{"topic": "比"}, {"topic": "速さ"}, {"topic": "図形"}])
    check("開始日が同じなら入れ直しても日付は動かない（増えた回は最後の次から）",
          [x["date"] for x in ls] == ["2026-09-07", "2026-09-21", "2026-09-28"],
          [x["date"] for x in ls])


def main():
    paths.ensure_school(SCHOOL)
    paths.save(paths.school_file(SCHOOL, "school.json"),
               {"id": SCHOOL, "name": "検査校", "code": "l", "tz": "Europe/London"})
    test_outbox()
    test_notes()
    test_top()
    print("\n%d 件 OK / %d 件 ×" % (ok_n, ng_n))
    if ng_n:
        sys.exit(1)
    print("すべて通った。")


if __name__ == "__main__":
    main()
