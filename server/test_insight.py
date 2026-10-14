#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""理解度と提案（insight.py）・5段階の評価（ratescale.py）を確かめる。

確かめる決めごと
  ・s の無い評価は前の4段階として読み替える。0（出ていない）は理解度に数えない
  ・束の代表（写真を出す先）は生徒ごと。上位でない紙で ID が最小
  ・提出は、写真を出したか評価が1以上。出すだけの宿題しかない回は数えない
  ・根拠は、あるものだけを重みで割り直す
  ・単元の理解度は根拠のある生徒の平均。70% 未満は黄
  ・度数分布は 0〜100 を10区切り（100 は最後の区切り）
  ・提案は理解度の低い単元にだけ出し、見送ったものは21日出さない

    python3 server/test_insight.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ratescale as RS                           # noqa: E402
import insight as IN                             # noqa: E402

ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   " + name)
    else:
        ng_n += 1
        print("  ×    %s | %s" % (name, detail))


NOW = 2000000000 * 1000
DUE = NOW - 86400 * 1000


def asg(i, n, title, sids, route="paper", graded=True, extra=None, source="src", due=DUE, personal=None):
    a = {"id": i, "title": title, "source": source, "from": 1, "to": 4, "route": route, "graded": graded,
         "students": list(sids), "dueAt": due, "lesson": {"key": "j2r:math", "n": n}}
    if extra:
        a["extra"] = extra
    if personal:
        a["personal"] = personal
    return a


def main():
    print("5段階の評価")
    check("s の無い 3 は 5（よくできた）", RS.value({"v": 3}) == 5)
    check("s の無い 1 は 2（気にかける）", RS.value({"v": 1}) == 2 and RS.is_low({"v": 1}))
    check("s:5 はそのまま", RS.value({"v": 4, "s": 5}) == 4)
    check("範囲の外は読まない", RS.value({"v": 9, "s": 5}) is None)
    check("真偽値は読まない", RS.value({"v": True, "s": 5}) is None and not RS.valid(True))
    check("0 は気にかける（出ていない）", RS.is_low({"v": 0, "s": 5}))
    check("0 は理解度にしない", RS.pct({"v": 0, "s": 5}) is None)
    check("3（もう少し）は70%未満", RS.pct({"v": 3, "s": 5}) < IN.YELLOW)
    rec = RS.record(5, "T1", now=10)
    check("保存する形に s を付ける", rec == {"v": 5, "s": 5, "at": 10, "by": "T1"}, rec)

    print("\n束の代表と状態")
    items = [asg("a5", 7, "新中学問題集 p.34-37", ["S1", "S2"]),
             asg("a9", 7, "演習問題集 p.25-28", ["S1"], extra="top"),
             asg("a2", 7, "新中学問題集（第6回の解き直し） p.30-33", ["S2"], personal=["r1"]),
             asg("a7", 7, "計算 1-10", ["S1", "S2"], graded=False)]
    b1 = IN.student_bundle(items, "S1")
    b2 = IN.student_bundle(items, "S2")
    check("S1 の代表は上位でない最小の ID", b1["head"]["id"] == "a5", b1["head"])
    check("S2 の代表は生徒だけの宿題（ID が小さい）", b2["head"]["id"] == "a2", b2["head"])
    check("出すだけの宿題は束に入れない", "a7" not in [a["id"] for a in b1["paper"]])
    subs = {"a5": {"S1": {"files": [{"name": "1.jpg"}], "at": 5, "seen": False}}}
    rt = {"a5": {"S1": {"v": 4, "s": 5, "at": 6}}, "a9": {"S1": {"v": 4, "s": 5, "at": 6}},
          "a2": {"S2": {"v": 0, "s": 5, "at": 6}}}
    s1 = IN.student_state(b1, "S1", rt, subs, {})
    s2 = IN.student_state(b2, "S2", rt, subs, {})
    check("写真と評価を読む", s1["files"] == ["1.jpg"] and s1["v"] == 4 and s1["submitted"], s1)
    check("評価の対象は束の全件", s1["targets"] == ["a5", "a9"], s1["targets"])
    check("評価0（出ていない）は提出にしない", s2["submitted"] is False and s2["v"] == 0, s2)
    check("生徒だけの宿題があることが分かる", s2["personal"] and not s1["personal"])
    only_plain = IN.student_bundle([asg("b1", 8, "計算 1-10", ["S1"], graded=False)], "S1")
    check("出すだけしかない回は提出を数えない",
          IN.student_state(only_plain, "S1", {}, {}, {})["submitted"] is None)

    print("\n根拠の重ね方")
    check("宿題だけならその値", IN.combine({"hw": 80}) == 80)
    check("あるものだけで割り直す", IN.combine({"hw": 80, "test": 50}) == 67, IN.combine({"hw": 80, "test": 50}))
    check("何も無ければ None", IN.combine({}) is None)
    cards = {"mat:q:1": [0, 2.5, 0, 3, 1, 0, 0], "mat:q:2": [0, 2.5, 0, 2, 0, 0, 0],
             "mat:q:3": [0, 2.5, 0, 5, 5, 0, 0]}
    unit_of = {"mat:q:1": "一次関数", "mat:q:2": "一次関数のグラフ", "mat:q:3": "連立方程式"}
    d = IN.daily_by_topic(cards, unit_of, {7: "一次関数", 6: "連立方程式", 5: "平方根"})
    check("単元名の合う問題をまとめる（5回中4回できた）", d.get(7) == 80, d)
    check("まったくできていない単元は 0%", d.get(6) == 0, d)
    check("答えていない単元は根拠にしない", 5 not in d, d)
    check("3回未満は根拠にしない", IN.daily_by_topic({"mat:q:1": [0, 2.5, 0, 2, 0, 0, 0]}, unit_of, {7: "一次関数"}) == {})
    pr = IN.prep_by_topic({"一次関数": {"w": 1, "n": 4}}, {7: "一次関数"})
    check("対策の丸つけ（4問中1問落とした）", pr == {7: 75}, pr)
    check("度数分布（100 は最後の区切り）", IN.histogram([0, 9, 10, 55, 99, 100, None]) == [2, 1, 0, 0, 0, 1, 0, 0, 0, 2])

    print("\nコース × 生徒 × 単元")
    plan = {"lessons": [{"n": 6, "date": "2026-09-01", "topic": "連立方程式"},
                        {"n": 7, "date": "2026-09-08", "topic": "一次関数"},
                        {"n": 8, "date": "2026-09-15", "topic": "角度"}]}
    asgs = [asg("c6", 6, "新中学問題集 p.30-33", ["S1", "S2", "S3"]),
            asg("c7", 7, "新中学問題集 p.34-37", ["S1", "S2", "S3"]),
            asg("c8", 8, "新中学問題集 p.38-41", ["S1", "S2", "S3"], due=NOW + 86400 * 1000)]
    ratings = {"c6": {"S1": {"v": 5, "s": 5}, "S2": {"v": 3, "s": 5}, "S3": {"v": 2, "s": 5}},
               "c7": {"S1": {"v": 4, "s": 5}, "S2": {"v": 2, "s": 5}}}
    subs2 = {"c7": {"S3": {"files": [{"name": "x.jpg"}]}}}
    tests = [{"date": "2026-09-09", "cols": [{"label": "一次関数", "max": 20, "lessons": [7]}],
              "rows": {"S3": [5]}}]
    ctx = {"plan": plan, "asgs": asgs, "ratings": ratings, "subs": subs2, "tests": tests,
           "blobs": {}, "unit_of": {}, "weak": {},
           "roster": [{"sid": "S1", "label": "中2R-01"}, {"sid": "S2", "label": "中2R-02"},
                      {"sid": "S3", "label": "中2R-03"}]}
    m = IN.course_matrix(ctx, now_ms=NOW)
    check("期限の来た回だけ", [u["n"] for u in m["units"]] == [6, 7], m["units"])
    u6, u7 = m["units"]
    check("単元の理解度は生徒の平均（100・60・40）", u6["und"] == 67 and u6["yellow"], u6)
    check("テストだけの生徒も根拠に入る（80・40・25）", u7["und"] == 48 and u7["undN"] == 3, u7)
    check("提出（評価・写真）", (u7["subDone"], u7["subN"]) == (3, 3), u7)
    st = {s["sid"]: s for s in m["students"]}
    check("生徒の理解度は直近の単元の平均", st["S1"]["avg"] == 90 and st["S3"]["avg"] == 33, st)
    check("根拠が分かる", st["S3"]["cells"][7]["ev"] == {"hw": None, "test": 25, "daily": None, "prep": None},
          st["S3"]["cells"][7])
    blind = dict(ctx, asgs=asgs + [asg("c5", 5, "新中学問題集 p.26-29", ["S1", "S2", "S3"])],
                 plan={"lessons": plan["lessons"] + [{"n": 5, "date": "2026-08-25", "topic": "総復習"}]})
    mb = IN.course_matrix(blind, now_ms=NOW)
    u5 = [u for u in mb["units"] if u["n"] == 5][0]
    check("写真も評価も1件も無い回は、提出を数えない（0%にしない）", u5["sub"] is None and u5["subN"] == 0, u5)
    check("観測していない回は、生徒の提出率にも入れない",
          [s["subRate"] for s in mb["students"]] == [s["subRate"] for s in m["students"]],
          ([s["subRate"] for s in mb["students"]], [s["subRate"] for s in m["students"]]))
    ov = IN.overview_row({"key": "j2r:math", "name": "中2R 数学"}, m)
    check("札：最新の単元と理由", ov["latest"]["n"] == 7 and ov["flag"] and ov["reasons"], ov)
    check("札：50%以下の人数", ov["low50"] == 2, ov)
    tr = IN.student_trend(m, "S2", plan["lessons"])
    check("生徒の月ごとの推移", tr["months"] == [{"month": "2026-09", "u": 50, "n": 2}], tr["months"])

    print("\n宿題チェックの行")
    rows, stats = IN.check_rows(asgs[1:2], ctx["roster"], ratings, subs2, {})
    check("数（提出・評価ずみ・評価まだ・未提出）",
          stats == {"n": 3, "submitted": 1, "rated": 2, "todo": 1, "missing": 0}, stats)
    check("席の順に並ぶ", [r["label"] for r in rows] == ["中2R-01", "中2R-02", "中2R-03"])

    print("\n提案")
    sg = IN.suggest(ctx, m, "S2", 7, 8, "T1", log=[], weekly=[{"text": "計算テキスト", "source": "keisan"}],
                    unit_items=12, now=NOW / 1000)
    kinds = [x["kind"] for x in sg]
    check("解き直しは提案しない（足す宿題はプリセットから）。アプリの復習は出る",
          "redo" not in kinds and "basic" not in kinds and "app" in kinds, kinds)
    app = [x for x in sg if x["kind"] == "app"][0]
    check("アプリの復習は次の回に足す（この回だけ）",
          app["rule"]["kind"] == "add" and app["rule"]["until"] == "once" and app["rule"]["from"] == 8, app)
    check("アプリの復習はその単元の問題を集める",
          app["rule"]["with"]["app"]["unit"] and app["rule"]["with"]["app"]["count"] == 10, app)
    check("理由に根拠を添える", "宿題" in app["why"], app["why"])
    none_ = IN.suggest(ctx, m, "S1", 7, 8, "T1", log=[], unit_items=12, now=NOW / 1000)
    check("理解度の高い単元には出さない", none_ == [], none_)
    log = [{"by": "T1", "sid": "S2", "n": 7, "kind": "app", "action": "dismiss", "at": NOW / 1000 - 86400}]
    sg2 = IN.suggest(ctx, m, "S2", 7, 8, "T1", log=log, unit_items=12, now=NOW / 1000)
    check("見送った提案は出さない", "app" not in [x["kind"] for x in sg2], sg2)
    old = [dict(log[0], at=NOW / 1000 - 86400 * 30)]
    sg3 = IN.suggest(ctx, m, "S2", 7, 8, "T1", log=old, unit_items=12, now=NOW / 1000)
    check("21日たてば出し直す", "app" in [x["kind"] for x in sg3], sg3)
    likes = [{"by": "T1", "kind": "app", "action": "accept"}] * 6 + [{"by": "T1", "kind": "redo", "action": "dismiss", "sid": "X"}] * 6
    sg4 = IN.suggest(ctx, m, "S2", 7, 8, "T1", log=likes, unit_items=12, now=NOW / 1000)
    check("講師がよく出す種類を上にする", sg4 and sg4[0]["kind"] == "app", [x["kind"] for x in sg4])

    print()
    if ng_n:
        print("× %d件おちた" % ng_n)
        return 1
    print("すべて通った。（%d件）" % ok_n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
