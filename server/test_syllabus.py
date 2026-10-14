#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""シラバス（server/syllabus.py）と原本（curriculum_source.py）の検査。
    python3 server/test_syllabus.py
  - 原本（カリキュラム/カリキュラム.json）が読め、43本以上のシラバスがすべて形を満たす
  - 小4の算数：日程表どおり 第2回＝9/2 … 第7回＝10/7、ハーフタームの週に授業が無い、第10回＝11/4、第17回＝1/6
  - 中学：2学期①＝9/2、冬期①＝12/2、3学期①＝1/6（仮定どおりに並ぶ）。数学3T は1週に2回
  - コース→シラバス：対応のあるコースは原本、無いコースは None。計画の syllabus は原本より優先
  - shared に取り込んだ同じ id が原本より優先される
  - 組分けの既定（exams.json が空のとき）は日程表の組分け・月例 5本
  - 本部基準（reference）が原本から出て、10/8 は第6週
  - 進み具合（pace）：10/8 時点の予定は第2〜7回（総合を除いて5つ）
  - 形の誤りを見逃さない（単元なし・月曜でない週・anchor が重なる）
"""
import datetime as dt
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="syllabus-test-")
os.environ["MYACADY_ROOT"] = TMP
sys.path.insert(0, HERE)
import paths                    # noqa: E402
import syllabus as SY           # noqa: E402
import courses as C             # noqa: E402
import curriculum_source as S   # noqa: E402
import exams as EX              # noqa: E402
import reference_curriculum as RC  # noqa: E402

N = [0]
BAD = []


def ok(cond, name, detail=""):
    N[0] += 1
    if not cond:
        BAD.append("%s %s" % (name, detail))
        print("  ×", name, detail)


def wed(key):
    p = {"unit": "lesson", "slots": [{"day": 3}]}
    skip = S.skip_dates(key)
    return lambda st, count: C.dates(p, st, count, skip)


def main():
    doc = S.load()
    ok(doc is not None, "原本が読める", S.PATH)
    ids = S.syllabus_ids()
    ok(len(ids) >= 43, "原本のシラバスが43本以上", str(len(ids)))
    for sid in ids:
        d = SY.load(sid)
        ok(d is not None and not SY.problems(d), "形を満たす: " + sid, "; ".join(SY.problems(d or {})))
        ok(d and d.get("provisional") is False and d.get("perWeek") is True, "原本の印（provisional=false, perWeek）: " + sid)
    ok(all(x in SY.seeds() for x in ids), "seeds() に原本の id が入る")
    ok(not [f for f in os.listdir(os.path.join(HERE, "syllabus")) if f.endswith(".json")], "server/syllabus に仮置きの JSON が残っていない")

    # 小4 算数
    d = SY.of_course("e4a:math", {})
    ok(d and d["id"] == "e4a-math-2026b", "e4a:math は原本の対応で引ける")
    sch = SY.schedule(d, wed("e4a:math"))
    by = {d["units"][j]["label"]: day for day, j in sch}
    ok(len(sch) == 18, "小4算数の18単元に授業日", str(len(sch)))
    ok(by.get("第2回") == "2026-09-02" and by.get("第7回") == "2026-10-07", "第2回＝9/2・第7回＝10/7", str((by.get("第2回"), by.get("第7回"))))
    ok(not [x for x, j in sch if "2026-10-26" <= x <= "2026-11-01"], "ハーフタームの週に授業が無い")
    ok(by.get("第10回") == "2026-11-04" and by.get("第17回") == "2027-01-06", "第10回＝11/4・第17回＝1/6（冬休みを飛ぶ）", str((by.get("第10回"), by.get("第17回"))))
    ok([u["label"] for u in d["units"] if u.get("review")] == ["第5回", "第10回", "第15回", "第19回"], "総合の回は教材どおり（5・10・15・19）")

    # 中学
    j = SY.of_course("j1t:math", {})
    sch = SY.schedule(j, wed("j1t:math"))
    by = {j["units"][k]["label"]: day for day, k in sch}
    ok(by.get("2学期①") == "2026-09-02" and by.get("冬期①") == "2026-12-02" and by.get("3学期①") == "2027-01-06",
       "中1数学：2学期①＝9/2・冬期①＝12/2・3学期①＝1/6", str((by.get("2学期①"), by.get("冬期①"), by.get("3学期①"))))
    ok(j.get("timing") and not j.get("alignment"), "中学部の週の決まりは確定（timing。仮の印は無い）")
    k6, k5 = SY.of_course("e6k:math", {}), SY.of_course("e5k:japanese", {})
    s6 = SY.schedule(k6, lambda st, c: C.dates({"unit": "lesson", "slots": [{"day": 1}]}, st, c, S.skip_dates("e6k:math")))
    ok(k6["units"][0]["label"] == "第17回" and k6["units"][0]["topic"] == "比①" and s6[0][0] == "2026-08-31" and not k6.get("alignment"),
       "6K 算数は 8/31 の週に第17回「比①」から（本人に確認・仮の印なし）", str(s6[:1]))
    ok(k5.get("alignment") and k5["units"][0]["label"] == "第17回", "5K は第17回から、仮の印つき")
    dm = SY.of_course("j1d:math", {})
    ok(dm and dm["id"] == "j1d-math-2026b" and "1R" in dm["source"], "中1D 数学は 1R の表", str((dm or {}).get("source")))
    m3 = SY.of_course("j3t:math", {})
    sch3 = SY.schedule(m3, lambda st, c: C.dates({"unit": "lesson", "slots": [{"day": 1}, {"day": 4}]}, st, c, S.skip_dates("j3t:math")))
    ok(len(sch3) == 36 and sch3[0][0] == "2026-08-31" and sch3[1][0] == "2026-09-03", "数学3T は1週に2回（月・木）", str(sch3[:2]))

    # コースの対応
    ok(SY.of_course("e4:english", {}) is None, "対応の無いコース（e4:english）は None")
    ok(SY.of_course("e6nanpro:math", {}) is None, "難プロは原本に表が無い → None")
    ok(S.course_note("e6nanpro:math"), "対応の無い理由が書いてある")
    sh = dict(d, id="e4a-math-2026b", name="手で直した", units=d["units"][:5], anchor={"unit": "第2回", "week": "2026-08-31"})
    SY.save(sh)
    ok(SY.load("e4a-math-2026b")["name"] == "手で直した", "shared に取り込んだ同じ id が原本より優先")
    os.remove(paths.shared_file("syllabus", "e4a-math-2026b.json"))
    ok(SY.of_course("e4a:math", {"syllabus": "e5a-math-2026b"})["id"] == "e5a-math-2026b", "計画の syllabus は原本の対応より優先")
    ok(SY.of_course("e4a:math", {"syllabus": "e4a-math"})["id"] == "e4a-math-2026b", "外した仮置きの id を持つ計画は原本へ戻る")
    # 週2コマのコース：1週1単元を2コマに当て、2つ先へ詰めない
    r3 = SY.of_course("j3r:math", {})
    two = {"unit": "lesson", "slots": [{"day": 2}, {"day": 4}]}
    sk = S.skip_dates("j3r:math")
    s3 = SY.schedule(r3, lambda st, c: C.dates(two, st, c, sk))
    lds = C.dates(two, s3[0][0], 80, sk)
    lr = SY.lesson_rows(r3, s3, lds)
    wk = [x for x in lr if "2026-09-07" <= x["date"] <= "2026-09-13"]
    ok(len(s3) == len(r3["units"]) and [x[0] for x in s3[:2]] == ["2026-09-01", "2026-09-08"], "週2コマでも単元は1週に1つ（9/1・9/8）", str(s3[:2]))
    ok(len(wk) == 2 and wk[0]["unit"] == wk[1]["unit"] == 1, "その週の2コマは同じ単元", str(wk))
    # 結びついていない計画は差を数えない
    sch = SY.schedule(d, wed("e4a:math"))
    un = SY.pace(d, sch, [{"n": 1, "date": "2026-09-02", "topic": "講師が書いた題"}], "2026-10-08", linked=False)
    ok(un["status"] == "unlinked" and un["current"]["label"] == "第7回", "結びついていない計画は unlinked（今週の本部の予定だけ）", str(un))
    mt = SY.pace(d, sch, [{"n": 1, "date": "2026-09-02", "topic": "分配とやりとりの問題"}], "2026-10-08", linked=False)
    ok(mt["status"] == "ok" and mt["done"] == 1, "単元名が合う行は数える", str((mt["status"], mt.get("done"))))
    # 仮の基準が shared に残っていても原本を隠さない
    RC.save_reference("e4", {"grade": "e4", "provisional": True, "weeks": [{"w": 1, "from": "2026-09-01", "units": []}]})
    ok(RC.load_reference("e4").get("provisional") is False, "shared の仮の基準より原本")
    os.remove(RC.reference_path("e4"))

    # 組分けの既定・本部基準・進み具合
    paths.ensure_school("testschool")
    ex = EX.all_exams("testschool")
    ok([e["date"] for e in ex] == ["2026-08-29", "2026-10-03", "2026-11-07", "2026-12-12", "2027-01-23"], "組分け・月例の既定5本", str(ex))
    ok(S.dept_of("e4", "e4a") == "elementary" and S.dept_of("e5", "e5k") == "junior" and S.dept_of("j1", "j1t") == "junior"
       and S.dept_of("e4", "e4k") == "", "部：小4A は小学部、5K と中1 は中学部、小4K は日程表に無いので分からない")
    ok(EX.all_exams("testschool", "junior") == [] and len(EX.all_exams("testschool", "elementary")) == 5,
       "原本の組分け・月例は小学部だけに当たる")
    t1012 = dt.datetime(2026, 10, 12, 12).timestamp()
    we, wj = EX.placement_window("testschool", t1012, "elementary"), EX.placement_window("testschool", t1012, "junior")
    ok(we and we["exam"]["date"] == "2026-10-03" and wj is None, "10/12：小学部には 10/3 の組分けを聞き、中学部には聞かない", str((we, wj)))
    ok(EX.window("testschool", dt.datetime(2026, 10, 30, 12).timestamp(), "junior") is None
       and EX.window("testschool", dt.datetime(2026, 10, 30, 12).timestamp(), "elementary"), "10/30：対策は小学部だけ")
    EX.set_exams("testschool", EX.all_exams("testschool") + [{"date": "2027-02-20", "name": "管理ページで足した"}])
    got = EX.all_exams("testschool")
    ok(len([e for e in got if e.get("dept") == "elementary"]) == 5 and [e for e in got if e["date"] == "2027-02-20" and not e.get("dept")],
       "保存し直しても部の印は残り、足した日は全員に当たる")
    ok([e["date"] for e in EX.all_exams("testschool", "junior")] == ["2027-02-20"], "中学部には足した日だけ")
    EX.set_exams("testschool", [])
    ok(EX.all_exams("testschool") == [], "管理ページで全部外した日程は空のまま（原本で埋め戻さない）")
    ref = RC.load_reference("e4")
    ok(ref and len(ref["weeks"]) == 18 and ref.get("provisional") is False, "小4の本部基準が原本から出る")
    when = dt.datetime(2026, 10, 8, 12).timestamp()
    ok(RC.week_of(ref, when) == 6, "10/8 は第6週", str(RC.week_of(ref, when)))
    pace = SY.pace(d, SY.schedule(d, wed("e4a:math")), [], "2026-10-08")
    ok(pace["expected"] == 5 and pace["current"]["label"] == "第7回" and pace["next"]["label"] == "第8回",
       "10/8 の進み具合：予定5（総合を除く）・今週は第7回・次は第8回", str((pace["expected"], pace["current"], pace["next"])))

    # 形の誤り
    bad = dict(d, units=[{"label": "a", "topic": ""}])
    ok(SY.problems(bad), "単元名の無い行を見逃さない")
    bad = dict(d, anchor={"unit": "第2回", "week": "2026-09-01"})
    ok(SY.problems(bad), "月曜でない週を見逃さない")
    bad = dict(d, units=d["units"] + [dict(d["units"][0])])
    ok(SY.problems(bad), "anchor と同じ呼び名の重なりを見逃さない")

    shutil.rmtree(TMP, ignore_errors=True)
    print("syllabus: %d 項目、問題 %d" % (N[0], len(BAD)))
    return 1 if BAD else 0


if __name__ == "__main__":
    sys.exit(main())
