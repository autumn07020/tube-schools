#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「ためしに見る」の一覧が決めたとおりに読めて、合言葉が外に出ないことを確かめる。

なぜこの検査が要るか
--------------------
入口の一覧には、本物の校舎の講師（wt01〜）が並ぶ（2026-10-10）。ボタンは ID だけで入る
（POST /api/demo/enter）ので、一覧の読み方と出し方が静かにずれると
**本物の合言葉が /api/demo に出る／デモを作り直すたびに本物の一覧が消える** という形で壊れる。

  ・password の欄が無い行も読める。あっても覚えない（/api/demo に出ない）
  ・ID は小文字に揃え、重複は畳み、12件で止める。role は teacher か student だけ
  ・demo_list は講師に担当クラスの名前とコースの数を添え、生徒にクラス名と教科を添える
  ・demo-swap が入口の一覧を写してよいのは、その一覧がデモの校舎の口座だけのとき

    python3 server/test_demo.py
"""

import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/test-demo-entrance"
os.environ["MYACADY_ROOT"] = ROOT
os.environ["TZ"] = "Europe/London"
time.tzset()
sys.path.insert(0, HERE)
shutil.rmtree(ROOT, ignore_errors=True)

import paths                                     # noqa: E402
import lessons as L                              # noqa: E402
import tube_server as T                          # noqa: E402

ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   %s" % name)
    else:
        ng_n += 1
        print("  ×    %s  %s" % (name, detail))


def setup():
    for sc, code, demo in (("london", "l", True), ("waseaca-london", "w", False)):
        paths.ensure_school(sc)
        meta = {"id": sc, "name": sc, "code": code, "tz": "Europe/London"}
        if demo:
            meta["demo"] = True
        paths.save(paths.school_file(sc, "school.json"), meta)
        paths.save(paths.school_file(sc, "curriculum.json"), {"v": 2, "classes": [
            {"id": "e4a", "name": "小4α", "grade": "e4"},
            {"id": "j3r", "name": "中3R", "grade": "j3"}]})
    T.add_account("london", "lteacher1", "kensa-kensa-kensa-0000", "T1", "teacher", "", "", classes=["*"])
    T.add_account("london", "lj3r01", "kensa-kensa-kensa-0001", "01", "student", "j3", "j3r")
    T.add_account("waseaca-london", "wt01", "kensa-kensa-kensa-0002", "T01", "teacher", "", "", classes=["-"])
    T.add_account("waseaca-london", "wdj3r91", "kensa-kensa-kensa-0003", "91", "student", "j3", "j3r")
    T.add_account("waseaca-london", "wadmin01", "kensa-kensa-kensa-0004", "A01", "admin", "", "")
    # wt01 に、コースを 2 つ持たせる（中3R 数学・小4α 算数）
    sid = T.accounts("waseaca-london")["wt01"]["sid"]
    data = L.load("waseaca-london")
    data["plans"] = {}
    for key, cls, sub in (("j3r:math", "j3r", "math"), ("e4a:math", "e4a", "math")):
        data["plans"][key] = {"name": key, "grade": cls[:2], "subject": sub, "teachers": [sid],
                              "slots": [], "classes": [cls], "students": [], "lessons": []}
    L.save("waseaca-london", data)


def main():
    setup()
    f = os.path.join(ROOT, "demo-accounts.json")
    rows = [{"id": "WT01", "role": "teacher", "label": "講師 wt01"},
            {"id": "wt01", "role": "teacher"},                                      # 重複は畳む
            {"id": "wdj3r91", "role": "student", "note": "ためし用"},
            {"id": "lteacher1", "role": "teacher", "password": "kensa-kensa-kensa-0000"},   # 古い形
            {"id": "wadmin01", "role": "admin"},
            {"role": "student"}, "junk", None]
    rows += [{"id": "x%02d" % i, "role": "student"} for i in range(20)]
    paths.save(f, rows)
    acc = T.load_demo_accounts(f)
    check("合言葉の無い行も読める。ID は小文字。重複は畳む",
          [a["id"] for a in acc][:4] == ["wt01", "wdj3r91", "lteacher1", "wadmin01"], [a["id"] for a in acc])
    check("16件で止める", len(acc) == 16, len(acc))
    check("合言葉は覚えない", all("password" not in a for a in acc))
    check("role は teacher か student だけ（admin は student に落ちるが、入る口は口座の役割で断る）",
          [a["role"] for a in acc[:4]] == ["teacher", "student", "teacher", "student"], [a["role"] for a in acc[:4]])

    T.DEMO["accounts"] = acc
    T.DEMO["on"] = True
    out = T.demo_list()
    by = {a["id"]: a for a in out}
    check("/api/demo の一覧に合言葉が無い", all("password" not in a for a in out))
    check("講師 wt01 に担当クラスの名前とコースの数が付く",
          by["wt01"].get("classes") == ["小4α", "中3R"] and by["wt01"].get("courses") == 2,
          (by["wt01"].get("classes"), by["wt01"].get("courses")))
    check("全部を見る講師は classes が ['*']", by["lteacher1"].get("classes") == ["*"], by["lteacher1"].get("classes"))
    check("生徒 wdj3r91 にクラス名が付く", by["wdj3r91"].get("className") == "中3R", by["wdj3r91"])
    check("無い口座（x00）は、ID と見出しだけ", "className" not in by["x00"] and "classes" not in by["x00"])

    # demo-swap が入口の一覧を写してよいか
    check("本物の校舎の口座（wt01）が並ぶ一覧は、london の作り直しで写さない", T.demo_list_is_only("london") is False)
    paths.save(f, [{"id": "lteacher1", "role": "teacher"}, {"id": "lj3r01", "role": "student"}, {"id": "nobody", "role": "student"}])
    check("london の口座だけ（知らない ID は数えない）の一覧は写してよい", T.demo_list_is_only("london") is True)
    paths.save(f, [])
    check("空の一覧も写してよい", T.demo_list_is_only("london") is True)
    os.remove(f)
    check("一覧が無くても写してよい", T.demo_list_is_only("london") is True)

    print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng_n else "通っていないものがある", ok_n, ng_n))
    return 1 if ng_n else 0


if __name__ == "__main__":
    sys.exit(main())
