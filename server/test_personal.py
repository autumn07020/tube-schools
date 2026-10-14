#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生徒ごとの宿題の決まり（personal.py）が、決めたとおりに当てはまるかを確かめる。

確かめる決めごと
  ・drop（出さない）・scale（減らす）・swap（置き換える）・add（足す）
  ・この回だけ／次に変えるまでずっと
  ・出した回には効かない（決まりは次の回から）
  ・受け取り手が0人になった既定の宿題は落とす（空の students は全員に化ける）
  ・既定の宿題（入力）を書き換えない
  ・発行（tube_server.publish_courses）に組み込んでも、生徒だけの宿題が束に入る

    python3 server/test_personal.py
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/test-personal"
os.environ["MYACADY_ROOT"] = ROOT
sys.path.insert(0, HERE)
shutil.rmtree(ROOT, ignore_errors=True)

import paths                                     # noqa: E402
import personal as PR                            # noqa: E402

ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   " + name)
    else:
        ng_n += 1
        print("  ×    %s | %s" % (name, detail))


def recs():
    return [
        {"id": "a1", "title": "予習シリーズ 基本問題 p.22-23", "source": "yos", "from": 22, "to": 23,
         "students": ["S1", "S2", "S3"], "route": "paper", "graded": True},
        {"id": "a2", "title": "演習問題集 基本問題＋トレーニング p.34-37", "source": "enshu", "from": 34, "to": 37,
         "students": ["S1", "S2", "S3"], "route": "paper", "graded": True},
        {"id": "a3", "title": "計算テキスト 43-49", "source": "keisan", "from": 43, "to": 49,
         "students": ["S1", "S2", "S3"], "route": "paper", "graded": False},
        {"id": "a4", "title": "基礎力強化プリント p.25-28", "source": "kiso", "from": 25, "to": 28,
         "students": ["S1"], "route": "paper", "graded": True, "extra": "top"},
    ]


TABLE = {("yos", 7): (22, 23, "予習シリーズ 基本問題 p.22-23"),
         ("yos", 6): (20, 21, "予習シリーズ 基本問題 p.20-21"),
         ("keisan", 7): (43, 49, "計算テキスト 43-49")}


def lookup(source, n):
    return TABLE.get((source, n))


def make(item, sid, rule_ids):
    return {"id": "p-%s-%s" % (sid, item.get("title")), "title": item.get("title"),
            "source": item.get("source", ""), "from": item.get("from"), "to": item.get("to"),
            "app": item.get("app"), "students": [sid], "personal": list(rule_ids),
            "extra": item.get("extra")}


def rule(kind, **kw):
    r = {"id": "r%08x" % (abs(hash((kind, str(kw)))) % (1 << 32)), "kind": kind, "from": 7,
         "until": None, "at": 1}
    r.update(kw)
    return r


def by_title(out, sid):
    return sorted(r["title"] for r in out if sid in r["students"])


def main():
    print("文を読む")
    check("範囲を外した呼び名", PR.base_text("計算テキスト 43-49") == "計算テキスト")
    check("ページ記号も外す", PR.base_text("予習シリーズ 基本問題 p.22-23") == "予習シリーズ 基本問題")
    check("末尾の（7もん）も外す", PR.base_text("計算テキスト 43–49（7もん）") == "計算テキスト")
    s = PR.scaled({"title": "計算テキスト 43-49", "from": 43, "to": 49}, 0.5)
    check("番号の範囲を半分に（切り上げ）", (s["from"], s["to"], s["title"]) == (43, 46, "計算テキスト 43-46"), s)
    s2 = PR.scaled({"title": "演習問題集 p.30-33", "from": 30, "to": 33}, 0.5)
    check("ページの範囲を半分に", s2["title"] == "演習問題集 p.30-31", s2)
    s3 = PR.scaled({"title": "漢字練習帳 50語", "from": 0, "to": 0}, 0.5)
    check("範囲の無い宿題は割合を添える", s3["title"] == "漢字練習帳 50語（半分）", s3)
    check("ページか番号か", PR.is_page("演習問題集 p.30-33") and not PR.is_page("計算テキスト 43-49"))

    print("\n出さない・減らす・置き換える")
    base = recs()
    rules = {
        "S2": [rule("drop", match={"source": "keisan", "text": "計算テキスト"})],
        "S3": [rule("scale", factor=0.5, match={"source": "keisan"})],
        "S1": [rule("swap", match={"source": "keisan"},
                    **{"with": {"text": "予習シリーズ 練習問題", "copy": {"source": "yos", "n": None}}})],
    }
    out = PR.apply(base, rules, 7, lookup, make)
    check("入力を書き換えない", base == recs(), base)
    check("3人とも計算テキストを変えると、既定の計算テキストは落ちる",
          not [r for r in out if r["id"] == "a3"], [r["id"] for r in out])
    check("S2 は計算テキストなし",
          by_title(out, "S2") == sorted(["予習シリーズ 基本問題 p.22-23", "演習問題集 基本問題＋トレーニング p.34-37"]),
          by_title(out, "S2"))
    check("S3 は計算テキストを半分に", "計算テキスト 43-46" in by_title(out, "S3"), by_title(out, "S3"))
    check("S1 は代わりに同じページの練習問題", "予習シリーズ 練習問題 p.22-23" in by_title(out, "S1"),
          by_title(out, "S1"))
    check("S1 の上位の宿題はそのまま", "基礎力強化プリント p.25-28" in by_title(out, "S1"))
    mine = [r for r in out if r.get("personal")]
    check("生徒だけの宿題は students が1人で、決まりの ID を持つ",
          all(len(r["students"]) == 1 and r["personal"] for r in mine), mine)
    check("空の students の宿題が1件も無い", all(r["students"] for r in out), out)

    print("\n足す（この回だけ）・効く回")
    once = {"S2": [rule("add", until=7, **{"with": {"text": "予習シリーズ 基本問題（第6回の解き直し）",
                                                     "copy": {"source": "yos", "n": 6}}})]}
    out7 = PR.apply(recs(), once, 7, lookup, make)
    check("前の回と同じページで足す", "予習シリーズ 基本問題（第6回の解き直し） p.20-21" in by_title(out7, "S2"),
          by_title(out7, "S2"))
    check("ほかの生徒には足さない", "予習シリーズ 基本問題（第6回の解き直し） p.20-21" not in by_title(out7, "S1"))
    out8 = PR.apply(recs(), once, 8, lookup, make)
    check("この回だけの決まりは次の回に効かない", not [r for r in out8 if r.get("personal")], out8)
    later = {"S2": [rule("drop", **{"from": 8, "match": {"source": "keisan"}})]}
    out7b = PR.apply(recs(), later, 7, lookup, make)
    check("まだ始まっていない決まりは効かない", "計算テキスト 43-49" in by_title(out7b, "S2"))
    check("ずっとの決まりは先の回にも効く", PR.active(rules["S2"][0], 30))

    print("\n対象が無いとき・手がかりの合わせ方")
    none_ = {"S1": [rule("swap", match={"source": "nothing"}, **{"with": {"text": "X"}})]}
    out_n = PR.apply(recs(), none_, 7, lookup, make)
    check("置き換える対象が無ければ、何も足さない", not [r for r in out_n if r.get("personal")], out_n)
    both = {"S1": [rule("drop", match={"source": "yos", "text": "予習シリーズ練習"})]}
    out_b = PR.apply(recs(), both, 7, lookup, make)
    check("source と text の両方が合うものだけ", "予習シリーズ 基本問題 p.22-23" in by_title(out_b, "S1"))
    app = {"S3": [rule("add", until=7, **{"with": {"text": "", "app": {"unit": "単位量あたり", "count": 10}}})]}
    out_a = PR.apply(recs(), app, 7, lookup, make)
    got = [r for r in out_a if r.get("app")]
    check("アプリの問題を足す（単元と数を渡す）",
          got and got[0]["app"] == {"unit": "単位量あたり", "count": 10} and got[0]["students"] == ["S3"], got)
    out_x = PR.apply(recs(), {"S9": [rule("drop", match={"source": "keisan"})]}, 7, lookup, make)
    check("この回の宿題を受け取らない生徒の決まりは何もしない", out_x == recs(), out_x)

    print("\n決まりを確かめる")
    r1 = PR.clean_rule({"kind": "drop", "match": {"source": "keisan", "text": "計算テキスト"}, "from": 3}, 8, "T1")
    check("出した回を指しても、次の回からにする", r1["from"] == 8 and r1["until"] is None, r1)
    r2 = PR.clean_rule({"kind": "add", "with": {"text": "解き直し"}, "until": "once"}, 8, "T1")
    check("この回だけ ＝ until が from と同じ", r2["until"] == 8, r2)
    for bad, msg in [({"kind": "zzz"}, "変え方"), ({"kind": "drop", "match": {}}, "どの宿題"),
                     ({"kind": "scale", "match": {"source": "k"}, "factor": 1.5}, "割合"),
                     ({"kind": "swap", "match": {"source": "k"}, "with": {}}, "代わり")]:
        try:
            PR.clean_rule(bad, 8, "T1")
            check("弾く: " + msg, False)
        except ValueError as e:
            check("弾く: " + msg, msg in str(e), e)
    s_, span = PR.describe(PR.clean_rule({"kind": "scale", "match": {"text": "計算テキスト"}, "factor": 0.5}, 8, "T1"))
    check("言葉にする", s_ == "計算テキスト を5割に減らす" and span == "第8回から、次に変えるまで", (s_, span))

    print("\n保存・止める")
    os.makedirs(paths.school_dir("t1"), exist_ok=True)
    a = PR.put_rule("t1", "e4a:math", "STU00001", {"kind": "drop", "match": {"source": "keisan"}}, "T1", 8)
    b = PR.put_rule("t1", "e4a:math", "STU00001", {"kind": "add", "with": {"text": "X"}, "from": 10}, "T1", 8)
    check("生徒ごとに並ぶ", [x["id"] for x in PR.rules_of("t1", "e4a:math", "STU00001")] == [a["id"], b["id"]])
    PR.put_rule("t1", "e4a:math", "STU00001", dict(a, factor=None, note="直した"), "T1", 8)
    check("同じ ID は差し替え", len(PR.rules_of("t1", "e4a:math", "STU00001")) == 2 and
          [x for x in PR.rules_of("t1", "e4a:math", "STU00001") if x["id"] == a["id"]][0]["note"] == "直した")
    check("まだ効いていない決まりを止めると消える", PR.stop_rule("t1", "e4a:math", "STU00001", b["id"], 9) and
          len(PR.rules_of("t1", "e4a:math", "STU00001")) == 1)
    check("効いたことのある決まりは、記録を残して終わる", PR.stop_rule("t1", "e4a:math", "STU00001", a["id"], 12) and
          PR.rules_of("t1", "e4a:math", "STU00001")[0]["until"] == 11)
    check("止めた決まりは先の回に効かない", not PR.active(PR.rules_of("t1", "e4a:math", "STU00001")[0], 12))
    PR.drop_student("t1", "STU00001")
    check("退塾した生徒の決まりを消す", PR.rules_of("t1", "e4a:math") == {})

    print("\n発行に組み込む（tube_server.publish_courses）")
    publish_check()

    print()
    if ng_n:
        print("× %d件おちた" % ng_n)
        return 1
    print("すべて通った。（%d件）" % ok_n)
    return 0


def publish_check():
    """本物の発行で、生徒ごとの宿題が出るか。コース・計画・名簿を小さく作って確かめる。"""
    import time
    os.environ["TZ"] = "Europe/London"
    time.tzset()
    import courses as C
    import insight as IN
    import lessons as L
    import tube_server as T
    school = "london"
    paths.ensure_school(school)
    paths.save(paths.school_file(school, "school.json"),
               {"id": school, "name": "検査校", "code": "l", "tz": "Europe/London"})
    paths.save(paths.school_file(school, "curriculum.json"),
               {"v": 2, "classes": [{"id": "e5b", "name": "小5β", "grade": "e5"}]})
    paths.save(paths.school_file(school, "materials.json"), {"items": {
        "yos-e5-math": {"name": "予習シリーズ 小5下 算数", "subject": "math", "mode": "paper"},
        "enshu-e5-math": {"name": "演習問題集 小5下 算数", "subject": "math", "mode": "paper"},
        "kiso-print": {"name": "基礎力強化プリント", "subject": "math", "mode": "paper"},
        "keisan-yos": {"name": "計算テキスト（予習シリーズ）", "subject": "math",
                       "mode": "paper", "graded": False}}})
    for lid, seat in [("le5b01", "01"), ("le5b02", "02"), ("le5b03", "03")]:
        T.add_account(school, lid, "student-pass", seat, "student", "e5", "e5b")
    T.add_account(school, "t-a", "t-a-pass", "T1", "teacher", "e5", "e5b", classes=["e5b"])
    db = T.accounts(school)
    db["t-a"]["assign"] = []
    T.save_accounts(school, db)

    def sidof(lid):
        return T.accounts(school)[lid]["sid"]
    ta = sidof("t-a")
    C.upsert(school, [("e5b:math", {"teachers": [ta], "unit": "lesson", "weekday": 0, "from": "", "to": "",
                                    "classes": ["e5b"], "students": [], "name": "小5β 算数",
                                    "grade": "e5", "subject": "math",
                                    "slots": [{"day": 1, "start": "16:40", "end": "18:10"}]})])
    rows = [{"topic": "第%d回" % i, "hw": {"items": [
        {"text": "予習シリーズ 基本問題", "source": "yos-e5-math", "from": 10 + 2 * i, "to": 11 + 2 * i},
        {"text": "演習問題集 基本問題＋トレーニング", "source": "enshu-e5-math",
         "from": 20 + 4 * i, "to": 23 + 4 * i}]}} for i in range(1, 4)]
    L.set_plan(school, "e5b:math", ta, "", 0, "2026-09-14", rows)
    with L.paths_lock():
        data = L.load(school)
        e5 = data["plans"]["e5b:math"]
        e5["extra"] = [{"id": "top", "name": "上位", "students": [sidof("le5b01")]}]
        e5["weekly"] = [{"id": "keisan", "text": "計算テキスト", "source": "keisan-yos",
                         "step": 7, "at": 0, "wrap": 0}]
        for l in e5["lessons"]:
            l["extraHw"] = {"top": {"items": [
                {"text": "基礎力強化プリント", "source": "kiso-print", "from": 1, "to": 4}]}}
        L.save(school, data)
    s1, s2, s3 = sidof("le5b01"), sidof("le5b02"), sidof("le5b03")
    PR.put_rule(school, "e5b:math", s2, {"kind": "drop",
                                        "match": {"source": "keisan-yos", "text": "計算テキスト"}}, ta, 1)
    PR.put_rule(school, "e5b:math", s3, {"kind": "swap", "match": {"source": "keisan-yos"},
                                        "with": {"text": "予習シリーズ 練習問題",
                                                 "copy": {"source": "yos-e5-math", "n": None}}}, ta, 1)
    PR.put_rule(school, "e5b:math", s1, {"kind": "add", "from": 2, "until": 2,
                                        "with": {"text": "予習シリーズ 基本問題（第1回の解き直し）",
                                                 "copy": {"source": "yos-e5-math", "n": 1}}}, ta, 1)

    def at(t):
        return time.mktime(time.strptime(t, "%Y-%m-%d %H:%M"))

    def hw(n):
        return [a for a in T.assignments(school).values()
                if (a.get("lesson") or {}).get("key") == "e5b:math" and (a.get("lesson") or {}).get("n") == n]

    def titles(items, s):
        return sorted(a["title"] for a in items if s in (a.get("students") or []))

    T.publish_courses(school, "test", now=at("2026-09-17 20:00"))
    h1 = hw(1)
    check("発行した（第1回）", len(h1) >= 4, [a["title"] for a in h1])
    check("S2 には計算テキストが出ない", not [t for t in titles(h1, s2) if t.startswith("計算テキスト")],
          titles(h1, s2))
    check("S3 には計算テキストの代わりに練習問題",
          [t for t in titles(h1, s3) if t.startswith("予習シリーズ 練習問題")] and
          not [t for t in titles(h1, s3) if t.startswith("計算テキスト")], titles(h1, s3))
    check("S1 は既定のまま（計算テキスト・上位あり）",
          [t for t in titles(h1, s1) if t.startswith("計算テキスト")] and "基礎力強化プリント" in titles(h1, s1),
          titles(h1, s1))
    keisan = [a for a in h1 if a.get("source") == "keisan-yos" and not a.get("personal")]
    check("既定の計算テキストは S1 だけに", keisan and keisan[0]["students"] == [s1], keisan)
    check("受け取り手が空の宿題は無い", all(a.get("students") for a in h1))
    mine3 = [a for a in h1 if a.get("personal")]
    check("生徒だけの宿題は personal と lesson を持つ",
          mine3 and all(a["students"] == [s3] and a["lesson"] == {"key": "e5b:math", "n": 1} for a in mine3), mine3)
    b3 = IN.student_bundle(h1, s3)
    check("生徒だけの宿題も束に入る（写真1回・評価1つ）",
          any(a.get("personal") for a in b3["paper"]) and b3["head"] is not None, b3["paper"])
    check("S1 の解き直しは第2回からの決まりなので、第1回には出ない",
          not [t for t in titles(h1, s1) if "解き直し" in t])

    PR.put_rule(school, "e5b:math", s1, {"kind": "drop", "match": {"source": "kiso-print"}}, ta, 2)
    T.publish_courses(school, "test", now=at("2026-09-24 20:00"))
    check("出したあとの宿題（第1回）は変わらない", "基礎力強化プリント" in titles(hw(1), s1), titles(hw(1), s1))
    h2 = hw(2)
    check("第2回に解き直しが出る（第1回と同じページ）",
          [t for t in titles(h2, s1) if t.startswith("予習シリーズ 基本問題（第1回の解き直し）")], titles(h2, s1))
    check("第2回から上位のプリントを出さない決まりが効く", "基礎力強化プリント" not in titles(h2, s1), titles(h2, s1))
    T.publish_courses(school, "test", now=at("2026-10-01 20:00"))
    check("この回だけの解き直しは第3回に出ない", not [t for t in titles(hw(3), s1) if "解き直し" in t],
          titles(hw(3), s1))
    ids1 = sorted(a["id"] for a in hw(1))
    check("生徒だけの宿題の ID は生徒ごとに違う", len(set(ids1)) == len(ids1))

    print("\nプリセット（presets.py）")
    import presets as PS
    pr = PS.put(school, "e5b:math", {"name": "発展問題", "text": "予習シリーズ 発展問題",
                                     "source": "yos-e5-math", "range": "same"}, ta)
    check("保存したプリセットに id が付く", PS.PID.match(pr["id"]) and pr["name"] == "発展問題", pr)
    check("一覧に出る", [x["id"] for x in PS.list_of(school, "e5b:math")] == [pr["id"]])
    try:
        PS.put(school, "e5b:math", {"name": "x", "text": "y", "range": "pages", "pages": "四十"}, ta)
        bad = False
    except ValueError:
        bad = True
    check("範囲の形が違えば保存しない", bad)
    pg = PS.put(school, "e5b:math", {"name": "総合", "text": "演習問題集 総合問題", "range": "pages", "pages": "p.40-43"}, ta)
    r1 = PS.rule_of(pr, "once", 2)
    check("同じ回の範囲を写す決まりになる",
          r1["kind"] == "add" and r1["with"]["copy"] == {"source": "yos-e5-math", "n": None}
          and r1["until"] == "once" and r1["origin"]["preset"] == pr["id"], r1)
    r2 = PS.rule_of(pg, None, 2)
    check("決まった範囲は文に添える", r2["with"]["text"] == "演習問題集 総合問題 p.40-43" and r2["until"] is None, r2)
    ap = PS.put(school, "e5b:math", {"name": "アプリで復習", "range": "app", "count": 8}, ta)
    r3 = PS.rule_of(ap, "once", 2, "比の利用")
    check("アプリの問題は単元と数を持つ", r3["with"]["app"] == {"unit": "比の利用", "count": 8}, r3)
    try:
        PS.rule_of(ap, "once", 2, "")
        bad = False
    except ValueError:
        bad = True
    check("単元の無いアプリの決まりは作れない", bad)
    saved = PR.clean_rule(r1, 2, ta)
    check("決まりに保存してもプリセットの id と名前が残る",
          saved["origin"]["preset"] == pr["id"] and saved["origin"]["name"] == "発展問題", saved)
    check("消せる", PS.remove(school, "e5b:math", pg["id"]) and len(PS.list_of(school, "e5b:math")) == 2)
    check("無いものは消せない", not PS.remove(school, "e5b:math", "p00000000"))
    it = PR.made_item({"text": "新中学問題集 発展問題", "copy": {"source": "none", "n": None}},
                      lambda s_, n_: None, 4, "第4回 相似の利用")
    check("範囲を写せないときは回の名前を添える", it["title"] == "新中学問題集 発展問題（第4回 相似の利用）", it)
    it2 = PR.made_item({"text": "演習問題集 p.40-43"}, lambda s_, n_: None, 4, "第4回")
    check("範囲のある文には添えない", it2["title"] == "演習問題集 p.40-43", it2)
    board = T.desk_board(school, "e5b:math", T.lessons.plan(school, "e5b:math"))
    check("個別の宿題の一覧に、決まりを持つ生徒が名前つきで出る",
          board and all(x["label"] and x["rules"] for x in board), board)

    print("\nアプリを使うクラス（courses.app_on / lessons.set_app）")
    _lid_t, acc_t = T.find_by_sid(school, ta)
    _lid_s, acc_s = T.find_by_sid(school, s1)
    acc_t = dict(acc_t, school=school)
    acc_s = dict(acc_s, school=school, subjects=["math"])       # 受講科目：算数
    # 4回目の予定を足す（3回まで出してあるので、まだ出していない回を1つ作る。出した回の日付は動かない）
    rows4 = [{"topic": "第%d回" % i, "hw": {"items": [
        {"text": "予習シリーズ 基本問題", "source": "yos-e5-math", "from": 10 + 2 * i, "to": 11 + 2 * i}]}}
             for i in range(1, 5)]
    T.lessons.set_plan(school, "e5b:math", ta, "", 0, "2026-09-14", rows4)
    ls_all = sorted(T.lessons.plan(school, "e5b:math").get("lessons") or [], key=lambda x: x.get("n") or 0)
    nx = [l for l in ls_all if not l.get("published")][0]     # まだ出していない いちばん早い回
    nn_, nd_ = int(nx["n"]), nx["date"]
    def n_hw(n):
        return len([a for a in T.assignments(school).values()
                    if (a.get("lesson") or {}).get("key") == "e5b:math" and (a.get("lesson") or {}).get("n") == n])
    check("印の無いコースは使う扱い", T.courses.app_on(T.lessons.plan(school, "e5b:math")))
    check("担当コース（机）に入っている", "e5b:math" in T.desk_courses(school, acc_t))
    pf = T.profile_of(acc_s)
    check("生徒の profile：算数はアプリの教科", "math" in pf["appSubjects"] and "math" not in pf["paperSubjects"], pf)
    T.lessons.set_app(school, "e5b:math", False, ta)
    check("使わないにすると、机から消える", "e5b:math" not in T.desk_courses(school, acc_t))
    check("時間割の担当には app:false で残る",
          any(r.get("key") == "e5b:math" and r.get("app") is False for r in T.teacher_slots(acc_t)))
    pf2 = T.profile_of(acc_s)
    check("生徒の profile：算数は紙の教科に", "math" in pf2["paperSubjects"] and "math" not in pf2["appSubjects"], pf2)
    n4 = n_hw(nn_)
    T.publish_courses(school, "test", now=at(nd_ + " 20:00"))
    n4b = n_hw(nn_)
    check("使わないコースの宿題は出ない", n4 == 0 and n4b == 0, (nn_, nd_, n4, n4b))
    T.lessons.set_app(school, "e5b:math", True, ta)
    check("使うに戻すと机に戻る", "e5b:math" in T.desk_courses(school, acc_t))
    T.publish_courses(school, "test", now=at(nd_ + " 20:00"))
    check("使い始めると、次の授業日の宿題が出る", n_hw(nn_) > 0, (nn_, nd_, n_hw(nn_)))

    print("\n保護者から講師へのメッセージ（messages.py）")
    import messages as M
    it = M.post(school, s1, "math", "e5b:math", "  木曜の宿題が遅れがちです。  ")
    check("出せる（本文は前後の空白を落とす）", it["id"].startswith("m") and it["text"] == "木曜の宿題が遅れがちです。", it)
    check("生徒（保護者）の一覧に出る", [x["id"] for x in M.of_student(school, s1)] == [it["id"]])
    check("担当講師の受信箱に未読で出る", M.unread(school, {"e5b:math"}) == 1 and M.inbox(school, {"e5b:math"})[0]["id"] == it["id"])
    check("担当外の講師の受信箱には出ない", M.inbox(school, {"j2r:math"}) == [])
    bad = None
    try:
        M.reply(school, it["id"], "other", "返事", {"j2r:math"})
    except PermissionError as e:
        bad = e
    check("担当外の講師は返せない", bad is not None)
    r = M.reply(school, it["id"], ta, "承知しました。金曜でも大丈夫です。", {"e5b:math"})
    check("返事が付き、講師は既読・保護者は未読に", r and len(r["replies"]) == 1 and r["seen"] == {"teacher": True, "parent": False}, r)
    bad = None
    try:
        M.post(school, s1, "math", "e5b:math", "   ")
    except ValueError as e:
        bad = e
    check("空の本文は出せない", bad is not None)
    M.mark_seen(school, it["id"], "parent", sid=s1)
    check("保護者が読むと既読", M.of_student(school, s1)[0]["seen"]["parent"] is True)


if __name__ == "__main__":
    sys.exit(main())
