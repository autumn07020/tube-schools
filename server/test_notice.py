#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仮の評価（未評価の紙の宿題）と、宿題の変更のお知らせ（ひとこと・わかった・質問する）を確かめる。

なぜこの検査が要るか
--------------------
  ・講師が評価を付け忘れた紙の宿題が、生徒の画面で「最低評価」に見えてはいけない。
    期限から7日過ぎて写真があれば仮に4（できた）。講師の一覧では未評価のまま。出していなければ仮も無し
  ・理解度は仮の4を 80% として重ねる（重み 0.45。ほかの根拠が無ければ 80）
  ・ひとこと付きの決まりには ack ができ、「わかった」で ok、「質問する」で asked。asked の決まりは効かない（active）
  ・講師が返事すると answered（再び効く）。1週間で自動的に ok
  ・生徒に見せるお知らせは open / asked / answered だけ。講師に知らせるのは最近の ok と asked

    python3 server/test_notice.py
"""
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/test-notice"
os.environ["MYACADY_ROOT"] = ROOT
os.environ["TZ"] = "Europe/London"
time.tzset()
sys.path.insert(0, HERE)
shutil.rmtree(ROOT, ignore_errors=True)

import paths                                     # noqa: E402
import insight as INSIGHT                        # noqa: E402
import personal as PR                            # noqa: E402
import messages as M                             # noqa: E402

SCHOOL = "london"
ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   %s" % name)
    else:
        ng_n += 1
        print("  ×    %s  %s" % (name, detail))


DAY = 86400


def test_provisional():
    print("仮の評価")
    now = time.time() * 1000
    a = {"id": "a1", "route": "paper", "graded": True, "students": ["STU00001", "STU00002"], "lesson": {"key": "k", "n": 3},
         "dueAt": int(now - 8 * DAY * 1000)}
    subs = {"a1": {"STU00001": {"at": 1, "files": [{"name": "a1-1.jpg", "kind": "jpg"}], "seen": 0}}}
    b = INSIGHT.student_bundle([a], "STU00001")
    st = INSIGHT.student_state(b, "STU00001", {}, subs, {}, now)
    check("写真あり・未評価・期限から8日 → 仮の4", st["v"] is None and st["prov"] is True, st)
    st2 = INSIGHT.student_state(b, "STU00002", {}, subs, {}, now)
    check("出していない生徒には仮も付かない", st2["prov"] is False)
    a6 = dict(a, dueAt=int(now - 6 * DAY * 1000))
    st3 = INSIGHT.student_state(INSIGHT.student_bundle([a6], "STU00001"), "STU00001", {}, subs, {}, now)
    check("期限から6日ならまだ仮にしない", st3["prov"] is False)
    st4 = INSIGHT.student_state(b, "STU00001", {"a1": {"STU00001": {"v": 2, "s": 5}}}, subs, {}, now)
    check("評価が付いていれば仮ではなく本物", st4["v"] == 2 and st4["prov"] is False)
    subs_t = {"a1": {"STU00001": {"at": 1, "files": [{"name": "a1-1.jpg", "kind": "jpg"}], "seen": 5, "origin": "teacher"}}}
    st5 = INSIGHT.student_state(b, "STU00001", {}, subs_t, {}, now)
    check("先生が取り込んだ紙でも仮になる", st5["prov"] is True)
    subs_p = {"a1": {"STU00001": {"at": 1, "files": [], "pruned": 5, "seen": 0}}}
    st6 = INSIGHT.student_state(b, "STU00001", {}, subs_p, {}, now)
    check("写真が保存期間を過ぎて消えていても、出した記録があれば仮になる", st6["prov"] is True)
    # 理解度：仮の4 は 80 として重ねる
    check("仮の4 = 80%（ほかの根拠が無いとき）", INSIGHT.combine({"hw": 80}) == 80)
    check("紙とアプリの重みづけ平均（紙 0.45・毎日テスト 0.15）", INSIGHT.combine({"hw": 80, "daily": 40}) == 70)
    rows, stat = INSIGHT.check_rows([a], [{"sid": "STU00001", "label": "1"}, {"sid": "STU00002", "label": "2"}], {}, subs, {})
    check("講師の一覧では未評価のまま（todo 1）で、prov の印だけ", stat["todo"] == 1 and rows[0]["v"] is None and rows[0]["prov"] is True, stat)


def test_ack():
    print("お知らせ（ひとこと・わかった・質問する）")
    paths.ensure_school(SCHOOL)
    now = int(time.time())
    r = PR.put_rule(SCHOOL, "k:math", "STU00001", {"kind": "scale", "match": {"text": "計算テキスト"}, "factor": 0.5,
                                            "msg": "提出が続くように、量を半分にします"}, "T1", 5, now)
    check("ひとこと付きの決まりに ack（open）ができる", r.get("msg") and (r.get("ack") or {}).get("state") == "open", r)
    r0 = PR.put_rule(SCHOOL, "k:math", "STU00001", {"kind": "drop", "match": {"text": "漢字"}}, "T1", 5, now)
    check("ひとこと無しの決まりには ack が無い", not r0.get("ack"))
    check("open の決まりは効く", PR.active(r, 6))
    nts = PR.notices_of(SCHOOL, "STU00001", now)
    check("生徒のお知らせは、ひとこと付きの1件だけ", len(nts) == 1 and nts[0][1]["id"] == r["id"], nts)
    check("ほかの生徒には無い", PR.notices_of(SCHOOL, "STU00002", now) == [])
    # 質問する → 止まる
    q = PR.ack_rule(SCHOOL, "k:math", "STU00001", r["id"], "ask", "どのページを減らしますか", now + 60, msg_id="m1")
    check("質問する → asked・質問文・メッセージID", q["ack"]["state"] == "asked" and q["ack"]["question"] == "どのページを減らしますか" and q["ack"]["msgId"] == "m1", q["ack"])
    check("asked の決まりは効かない（変更は止まる）", not PR.active(q, 6))
    check("生徒のお知らせにはまだ出る（asked）", PR.notices_of(SCHOOL, "STU00001", now)[0][1]["ack"]["state"] == "asked")
    acks = PR.acks_recent(SCHOOL, {"k:math"}, now)
    check("講師への知らせに「質問あり」", len(acks) == 1 and acks[0][2]["ack"]["state"] == "asked", acks)
    check("担当外のコースの分は出ない", PR.acks_recent(SCHOOL, {"other"}, now) == [])
    # 先生の返事 → answered（再び効く）
    ans = PR.answer_by_msg(SCHOOL, "m1", "p.20 までにします", "T1", now + 120)
    check("返事で answered・返事の文", ans and ans["ack"]["state"] == "answered" and ans["ack"]["answer"] == "p.20 までにします", ans)
    check("answered の決まりは再び効く", PR.active(ans, 6))
    check("知らない msgId には何もしない", PR.answer_by_msg(SCHOOL, "zzz", "x", "T1") is None)
    # わかった → ok（講師に知らせる）
    okr = PR.ack_rule(SCHOOL, "k:math", "STU00001", r["id"], "ok", "", now + 200)
    check("わかった → ok", okr["ack"]["state"] == "ok" and okr["ack"]["okAt"] == now + 200 and okr["ack"]["auto"] is False)
    check("ok になったお知らせは生徒に出ない", PR.notices_of(SCHOOL, "STU00001", now + 200) == [])
    acks = PR.acks_recent(SCHOOL, {"k:math"}, now + 300)
    check("講師への知らせに「わかった」が出る（7日以内）", len(acks) == 1 and acks[0][2]["ack"]["state"] == "ok")
    check("8日たてば講師への知らせから消える", PR.acks_recent(SCHOOL, {"k:math"}, now + 8 * DAY + 300) == [])
    check("ok の決まりに質問はできない", PR.ack_rule(SCHOOL, "k:math", "STU00001", r["id"], "ask", "x", now) is None)
    check("ひとこと無しの決まりには返事できない", PR.ack_rule(SCHOOL, "k:math", "STU00001", r0["id"], "ok", "", now) is None)
    # 1週間で自動
    r2 = PR.put_rule(SCHOOL, "k:math", "STU00002", {"kind": "add", "with": {"text": "練習問題"}, "msg": "復習しましょう"}, "T1", 5, now)
    check("出したては生徒に出る", len(PR.notices_of(SCHOOL, "STU00002", now + DAY)) == 1)
    check("7日過ぎると自動で ok になり、生徒には出ない", PR.notices_of(SCHOOL, "STU00002", now + 7 * DAY + 1) == [])
    a2 = [x for x in PR.acks_recent(SCHOOL, {"k:math"}, now + 7 * DAY + 2) if x[1] == "STU00002"]
    check("自動の ok は講師に auto として知らされる", len(a2) == 1 and a2[0][2]["ack"]["auto"] is True, a2)
    # 生徒からの質問のメッセージ
    it = M.post(SCHOOL, "STU00001", "math", "k:math", "【宿題の変更について質問】どのページ？", sender="student")
    check("生徒からのメッセージは from=student", it["from"] == "student")
    check("保護者からは from=parent のまま", M.post(SCHOOL, "STU00001", "math", "k:math", "こんにちは")["from"] == "parent")


def main():
    test_provisional()
    test_ack()
    print()
    if ng_n:
        print("test_notice: %d件 だめ" % ng_n)
        sys.exit(1)
    print("test_notice: すべて通った。（%d件）" % ok_n)


if __name__ == "__main__":
    main()
