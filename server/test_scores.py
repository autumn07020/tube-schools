#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""塾内テストの取り込み（scores.py）が、決めたとおりに読むかを確かめる。

確かめる決めごと
  ・大問（単元）ごとの点・合計点だけ・設問ごとの正誤 の3つを見分ける
  ・満点は見出し「比例(20)」か「満点」の行から読む。無ければ確かめる画面で入れる
  ・席番号（中2R-01）で合わせる。数字だけなら、そのコースで一意のときだけ
  ・名前や連絡先の列があれば取り込まない
  ・列は、見出しと授業の topic が合えばその回、合わなければテストの前5週間の回
  ・残すのは sid と点数だけ

    python3 server/test_scores.py
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/test-scores"
os.environ["MYACADY_ROOT"] = ROOT
sys.path.insert(0, HERE)
shutil.rmtree(ROOT, ignore_errors=True)

import paths                                     # noqa: E402
import scores as SC                              # noqa: E402

ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   " + name)
    else:
        ng_n += 1
        print("  ×    %s | %s" % (name, detail))


ROSTER = [{"sid": "S1", "label": "中2R-01", "seat": "01"},
          {"sid": "S2", "label": "中2R-02", "seat": "02"},
          {"sid": "S3", "label": "中2R-03", "seat": "03"}]
LESSONS = [{"n": i, "date": "2026-08-%02d" % (i * 4), "topic": t}
           for i, t in enumerate(["式の計算", "連立方程式", "1次方程式の応用", "一次関数", "総復習"], start=1)]


def main():
    print("大問（単元）ごとの点")
    p = SC.parse("席番号,連立方程式(20),1次関数/30,合計\n中2R-01,18,21,39\n中2R-02,10,,10\n中2R-99,5,5,10\n")
    check("形は units", p["kind"] == "units", p["kind"])
    check("列は2本（合計は読み飛ばす）", [c["label"] for c in p["cols"]] == ["連立方程式", "1次関数"], p["cols"])
    check("満点を見出しから読む", [c["max"] for c in p["cols"]] == [20.0, 30.0], p["cols"])
    check("合計を読み飛ばしたことを言う", any("合計" in w for w in p["warnings"]), p["warnings"])
    got, miss = SC.match_seats(p, ROSTER)
    check("席番号で合う", got.get("中2R-01") == "S1" and got.get("中2R-02") == "S2", got)
    check("合わない席を返す", miss == ["中2R-99"], miss)
    mp = SC.auto_map(p, LESSONS, "2026-08-22")
    check("見出しと topic が合う回に割り当てる", mp == [[2], [4]], mp)
    rec = SC.build("j2r:math", "単元確認テスト", "2026-08-22", p, got, mp, None, "T1", now=1)
    check("合った生徒だけ残す", sorted(rec["rows"].keys()) == ["S1", "S2"], rec["rows"])
    check("空欄は None のまま", rec["rows"]["S2"] == [10.0, None], rec["rows"]["S2"])
    check("表の文字（席番号）を残さない", "中2R-01" not in str(rec), rec)
    up = SC.unit_pcts([rec], "S1")
    check("単元ごとの出来（%）", up.get(2, {}).get("pct") == 90 and up.get(4, {}).get("pct") == 70, up)

    print("\n満点の行・数字だけの席番号")
    p2 = SC.parse("席,比例,関数\n満点,20,30\n01,10,15\n")
    check("満点の行を読む", [c["max"] for c in p2["cols"]] == [20.0, 30.0], p2["cols"])
    g2, m2 = SC.match_seats(p2, ROSTER)
    check("数字だけでも一意なら合う", g2.get("01") == "S1", (g2, m2))
    two = ROSTER + [{"sid": "X1", "label": "中2T-01", "seat": "01"}]
    g3, m3 = SC.match_seats(p2, two)
    check("数字だけで2人に当たるなら合わせない", not g3 and m3 == ["01"], (g3, m3))

    print("\n合計点だけ")
    p3 = SC.parse("席番号,合計,偏差値\n中2R-01,72,55\n中2R-03,40,41\n")
    check("形は total", p3["kind"] == "total", p3["kind"])
    check("偏差値は読まない", len(p3["cols"]) == 1 and p3["cols"][0]["label"] == "合計", p3["cols"])
    check("満点が分からないと言う", any("満点" in w for w in p3["warnings"]), p3["warnings"])
    g4, _ = SC.match_seats(p3, ROSTER)
    mp3 = SC.auto_map(p3, LESSONS, "2026-08-22")
    check("合計は範囲の回すべて（総復習の回は外す）", mp3 == [[1, 2, 3, 4]], mp3)
    try:
        SC.build("j2r:math", "組分けテスト", "2026-08-22", p3, g4, mp3, None, "T1")
        check("満点が無ければ取り込まない", False)
    except ValueError as e:
        check("満点が無ければ取り込まない", "満点" in str(e), e)
    rec3 = SC.build("j2r:math", "組分けテスト", "2026-08-22", p3, g4, mp3, [100], "T1")
    up3 = SC.unit_pcts([rec3], "S3")
    check("合計点を範囲の単元すべてに入れる", all(up3.get(n, {}).get("pct") == 40 for n in (1, 2, 3, 4)), up3)

    print("\n設問ごとの正誤")
    p4 = SC.parse("席番号\t1-(1)\t1-(2)\t2-(1)\t2-(2)\t2-(3)\n中2R-01\t○\t×\t○\t○\t×\n中2R-02\t1\t1\t0\t\t1\n")
    check("タブ区切りを読む・形は questions", p4["kind"] == "questions", p4)
    check("大問ごとにまとめる", [(c["label"], c["max"]) for c in p4["cols"]] == [("大問1", 2.0), ("大問2", 3.0)],
          p4["cols"])
    rows = {r["seat"]: r["vals"] for r in p4["rows"]}
    check("○の数を点にする", rows["中2R-01"] == [1.0, 2.0], rows)
    check("空欄は数えない", rows["中2R-02"] == [2.0, 1.0], rows)

    print("\n名前の列")
    p5 = SC.parse("席番号,氏名,比例(20)\n中2R-01,山田,10\n")
    check("名前の列があれば取り込まない", p5["errors"] and not p5["rows"], p5)
    p6 = SC.parse("席番号,保護者メール,合計\n中2R-01,a@b,10\n")
    check("連絡先の列も弾く", bool(p6["errors"]), p6)

    print("\n保存・一覧・消す")
    os.makedirs(paths.school_dir("t1"), exist_ok=True)
    tid = SC.put("t1", rec)
    SC.put("t1", dict(rec3, date="2026-09-01"))
    lst = SC.tests_of("t1", "j2r:math")
    check("新しい順に並ぶ", [t["date"] for t in lst] == ["2026-09-01", "2026-08-22"], lst)
    check("ほかのコースは出ない", SC.tests_of("t1", "e4a:math") == [])
    SC.drop_student("t1", "S1")
    check("退塾した生徒の点を消す", all("S1" not in t["rows"] for t in SC.tests_of("t1", "j2r:math")))
    check("消す", SC.remove("t1", tid) is not None and len(SC.tests_of("t1", "j2r:math")) == 1)

    print("\n単元名の近さ")
    check("同じ", SC.similar("一次関数", "一次関数") == 1.0)
    check("含む", SC.similar("比例", "比例と反比例") >= 0.9)
    check("数字と漢数字のゆれ", SC.similar("1次関数", "一次関数") >= 0.5)
    check("別の単元は合わない", SC.similar("連立方程式", "一次関数") < 0.5)

    print()
    if ng_n:
        print("× %d件おちた" % ng_n)
        return 1
    print("すべて通った。（%d件）" % ok_n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
