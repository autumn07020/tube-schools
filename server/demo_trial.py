#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ためし運用のデモ：本物の校舎（waseaca-london）の**今ある口座**に、架空の記録を作る。

    python3 server/demo_trial.py --school waseaca-london --me wt01            作る（前のためしのデータは先に消す）
    python3 server/demo_trial.py --school waseaca-london --clean              ためしのデータを消す（口座は席に戻す）
    python3 server/demo_trial.py --school waseaca-london --me wt01 --pick-classes j3r,e4b   入口の生徒に、このクラスの1人も足す（検査用）

何を作るか（2026-10-12 本人「全ての講師の各授業に対し、平均10人、最低5、最大15人の生徒を用意。特別にデモ版を作成する
のではなく、現状の生徒全てのデータを書き換えてください。試しに入れる生徒もデモ用の生徒ではなく、本番用の生徒の中から
無作為抽出して各学年ごと数名。ハリボテではなく、本当に動く、使える」）
  ・生徒は、クラスごとに今ある口座（まだ渡していない席を先に。足りなければ在籍の生徒）から **5〜15 人（平均 10）** を
    無作為に選ぶ（pick_students。種を固定しているので、何度流しても同じ人）。選んだ口座に demo の印。席だったものは
    在籍の生徒にし、席だった印（demoRole）を残す（--clean で席に戻る）。
  ・**全講師の全コース**（担当のあるもの）：授業計画（原本の単元）・学期のはじめからの宿題・写真と評価・毎日テストの記録。
    本人（--me）のコースは架空の宿題の文（KEN_COURSES）、ほかは原本の単元だけの計画。段階は全部 4（毎日テストまで）。
  ・講師ごとに 1 つ、きのう期限の提出箱に未評価の写真 → どの講師も今日、宿題チェック・ひとこと・添削を試せる。
  ・本人の担当の算数と国語のクラスには、返した添削・保護者のメッセージ・漢字テスト・作文。中3R 数学・小6α 算数・小6β 算数には過去問
    （その担当の講師の名で。小6K は高校受験に向けてゆっくり進む学年で過去問演習が無い。10-12 本人）。
  ・入口の「ためしに見る」の生徒は、選んだ生徒から**学年ごとに 2 人**を無作為に（trial_picks。school.json の trialPick に置き、
    サーバがそのまま一覧に出す。合言葉は要らない）。
  ・作り方は、デモ校（london）と同じ関数（demo_running.py）。**デモだけ別の道を通さない。**

本物の校舎の中に置くので、**見分けがつき、消せる**ことが先：
  ・選んだ口座に demo の印。作った宿題・提出箱に demo の印。計画に demo の印。段階は appBy=demo。
  ・--clean は、印のあるものと、選んだ生徒の記録（retire.erase_records）を消し、計画と段階を戻し、席だった口座は席に戻す。
    前の形のためし用の生徒（wd<クラス>91/92。deploy/デモ生徒.sh）は口座ごと消す。
  ・本番に切り替えるとき（deploy/本番切替.sh go-live）は、生徒の口座と記録がまるごと退避されるので、これも全部消える。
  ・何度流しても同じ結果（先に --clean と同じ片づけをしてから作る）。
  ・サーバは止めない（置き場の鍵 paths.GUARD を持って作る。数十秒〜数分、ほかの書き込みは待つ）。
"""

import argparse
import datetime
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                    # noqa: E402
import lessons as L                             # noqa: E402
import courses as C                             # noqa: E402
import exams as E                               # noqa: E402
import curriculum_source as SOURCE              # noqa: E402
import submissions as SUB                       # noqa: E402
import scores as SC                             # noqa: E402
import retire                                   # noqa: E402
import tube_server as T                         # noqa: E402
import demo_running as D                        # noqa: E402

DAY = 86400
SEED = 20261012                  # 無作為の種。固定なので、何度流しても同じ生徒が選ばれる
PER_CLASS = (5, 15)              # クラスごとの人数（この間で無作為。平均 10）
PICK_PER_GRADE = 2               # 入口の「ためしに見る」に出す生徒：学年ごとの人数

# 在籍クラスの無いコース（指名で受ける）に、どのクラスの生徒を指名するか。
NAMED_FROM = {"j3doku:math": ["j3r"], "j3rcatch:math": ["j3r"]}
# KEN_COURSES（デモ校の担当12コース）に無い本人のコースの、宿題の形。
EXTRA_DEFS = {
    "j3rcatch:math": {"key": "j3rcatch:math",
                      "hw": [("レギュラー 例題{lo}-{hi}（復習）", "joui-reg", 3)]},
}
QUIZ_TITLE = {"japanese": "漢字テスト 第1回", "math": "計算テスト 第1回", "english": "英単語テスト 第1回",
              "science": "一問一答 第1回", "social": "一問一答 第1回"}


def is_legacy(lid):
    """前の形のためし用の生徒（deploy/デモ生徒.sh の wd<クラス>91/92）。口座ごと消す。"""
    return str(lid).startswith("wd")


def is_demo_student(lid, a):
    """ためしの記録を持つ生徒か。印（demo）か、前の形（wd…）。"""
    return (a or {}).get("role") == "student" and bool(a.get("demo") or is_legacy(lid))


def demo_students(db):
    return {lid: a for lid, a in db.items() if is_demo_student(lid, a)}


def pick_students(school, extra_classes=(), seed=SEED, keep=()):
    """クラスごとに 5〜15 人を、今ある口座から無作為に選んで demo の印を付ける。
    席（まだ渡していない）を先に、足りなければ在籍の生徒で 5 人まで埋める。({クラス: [sid…]}, {クラス: [lid…]}) を返す。
    どのクラスでも先頭の 1 人が「見本」（添削・メッセージ・提出箱の相手。入口にも出る）。"""
    db = T.accounts(school)
    cand = {}
    for lid, a in db.items():
        if a.get("role") not in ("student", "seat") or a.get("leftAt") or a.get("claim") or a.get("pending"):
            continue
        if is_legacy(lid) or not a.get("classId") or not a.get("sid") or lid in keep:
            continue
        cand.setdefault(a["classId"], []).append(lid)
    by_sid, by_lid = {}, {}
    for cls in sorted(cand):
        rnd = random.Random("%s|%s" % (seed, cls))
        seats = sorted(l for l in cand[cls] if db[l].get("role") == "seat")
        stus = sorted(l for l in cand[cls] if db[l].get("role") == "student")
        n = rnd.randint(PER_CLASS[0], PER_CLASS[1])
        chosen = rnd.sample(seats, min(n, len(seats)))
        if len(chosen) < PER_CLASS[0] and stus:
            chosen += rnd.sample(stus, min(PER_CLASS[0] - len(chosen), len(stus)))
        for lid in sorted(chosen):
            a = db[lid]
            if a.get("role") != "student":
                a["demoRole"] = a["role"]
                a["role"] = "student"
            a["demo"] = True
            a.pop("leftAt", None)
            by_sid.setdefault(cls, []).append(a["sid"])
            by_lid.setdefault(cls, []).append(lid)
    T.save_accounts(school, db)
    return by_sid, by_lid


def trial_picks(school, by_lid, extra_classes=(), seed=SEED, per_grade=PICK_PER_GRADE):
    """入口の「ためしに見る」に出す生徒：学年ごとに per_grade クラスを無作為に選び、その見本（先頭）の 1 人。
    extra_classes のクラスの見本も足す（検査用）。school.json の trialPick に置く。"""
    grades = {}
    for cls in by_lid:
        grades.setdefault(T.gradeOfClass(school, cls) or "", []).append(cls)
    out = []
    for g in sorted(grades):
        rnd = random.Random("%s|pick|%s" % (seed, g))
        cl = sorted(grades[g])
        rnd.shuffle(cl)
        for cls in cl[:per_grade]:
            out.append(by_lid[cls][0])
    for cls in extra_classes:
        if cls in by_lid and by_lid[cls][0] not in out:
            out.append(by_lid[cls][0])
    meta = dict(T.school_meta(school))
    meta["trialPick"] = out
    paths.save(paths.school_file(school, "school.json"), meta)
    return out


def clean(school, accounts=False):
    """ためしのデータを消す。印のある宿題・提出箱・計画と、選んだ生徒の記録。席だった口座は席に戻す。
    前の形のためし用の生徒（wd…）は口座ごと消す（accounts は前との互換で受けるだけ）。"""
    db = T.accounts(school)
    demo = demo_students(db)
    sids = {a["sid"] for a in demo.values() if a.get("sid")}
    n = {"students": len(demo), "assignments": 0, "plans": 0, "accounts": 0, "kept": 0, "restored": 0}
    kept_keys = set()           # 本物の生徒の記録が付いた宿題のコース（計画は残す）
    with T.LOCK:
        # 印のある宿題・提出箱は、丸ごと（評価・写真も）。**ためしでない生徒の記録（写真・評価・アプリの達成）が
        # 付いたものは消さない**：ためしの生徒だけ外し、印を取って本物の宿題として残す。
        asg = T.assignments(school)
        rt = T.ratings(school)
        sdb = SUB.load(school)
        blobs = {}
        for aid in list(asg):
            x = asg[aid]
            if not (isinstance(x, dict) and x.get("demo")):
                continue
            real = [s for s in (x.get("students") or []) if s not in sids]
            has = any(s in (sdb.get(aid) or {}) or s in (rt.get(aid) or {}) for s in real)
            for s in real:
                if has:
                    break
                if s not in blobs:
                    blobs[s] = ((paths.load(T.progress_path(school, s), None) or {}).get("blob") or {}).get("hw") or {}
                if blobs[s].get(aid):
                    has = True
            if has:
                x["students"] = real
                x.pop("demo", None)
                kept_keys.add((x.get("lesson") or {}).get("key") or "")
                n["kept"] = n.get("kept", 0) + 1
                continue
            asg.pop(aid)
            n["assignments"] += 1
            rt.pop(aid, None)
            for sid2, got in (sdb.pop(aid, None) or {}).items():
                SUB._remove_files(school, sid2, SUB.all_files(got))
        T.save_assignments(school, asg)
        T.save_ratings(school, rt)
        SUB.save(school, sdb)
        # 選んだ生徒の記録（進捗・要約・写真・評価・点・連絡・落とした単元・受け取り手・指名）
        for lid, a in demo.items():
            if a.get("sid"):
                retire.erase_records(T, school, a["sid"])
        # 架空の塾内テスト（by demo）
        d = SC.load(school) or {}
        tests = d.get("tests") or {}
        keep = {k: v for k, v in tests.items() if (v or {}).get("by") != "demo"}
        if len(keep) != len(tests):
            d["tests"] = keep
            SC.save(school, d)
        # 計画と段階を戻す。指名からも外す（指名が1人だけのときは erase_records が残すので、ここで外す）
        data = L.load(school)
        for key, p in (data.get("plans") or {}).items():
            if not isinstance(p, dict):
                continue
            if p.get("demo") and key in kept_keys:
                # 本物の生徒の記録が付いた宿題のあるコース：計画も段階もそのまま（印だけ取る）。
                # 作り直すときは同じ開始日で入れ直すので、出した回の日付と印は動かない（lessons.set_plan）。
                p.pop("demo", None)
                continue
            if p.get("demo"):
                for f in ("lessons", "start", "skip", "weekly", "extra", "syllabus", "cycleStart", "weeklyAt", "demo"):
                    p.pop(f, None)
                p["lessons"] = []
                n["plans"] += 1
            if p.get("appBy") == "demo":
                p["use"], p["app"] = 0, False
                p["appAt"], p["appBy"] = int(time.time()), "demo-clean"
            st = p.get("students") or []
            if any(s in sids for s in st):
                p["students"] = [s for s in st if s not in sids]
        L.save(school, data)
        # 口座：前の形（wd…）は消す。無作為に選んだ本物の口座は印を外し、席だったものは席に戻す
        db = T.accounts(school)
        for lid in list(demo):
            a = db.get(lid)
            if not a:
                continue
            T.revoke_tokens(lid)
            if is_legacy(lid):
                db.pop(lid, None)
                paths.unbind_login(lid)
                n["accounts"] += 1
                continue
            a.pop("demo", None)
            if a.get("demoRole"):
                a["role"] = a.pop("demoRole")
                n["restored"] += 1
        T.save_accounts(school, db)
        meta = dict(T.school_meta(school))
        if meta.pop("trialPick", None) is not None:
            paths.save(paths.school_file(school, "school.json"), meta)
    return n


# 受験学年の過去問の見本（コース → 題）。中3 は高校受験、小6 の α・β は中学受験。小6K は高校受験に向けてゆっくり進む学年で
# 過去問演習が無い（カリキュラム/小5K6Kカリキュラム.pdf。10-12 本人）ので、ここに置かない。
KAKOMON = {
    "j3r:math": ["2025 都立共通 数学", "2024 都立共通 数学", "2025 早稲田実業 数学", "2024 慶應義塾 数学"],
    "e6a:math": ["2025 早稲田中 算数", "2024 早稲田中 算数", "2025 慶應普通部 算数", "2024 渋谷幕張 算数"],
    "e6b:math": ["2025 早稲田中 算数", "2024 早稲田中 算数", "2025 慶應普通部 算数", "2024 渋谷幕張 算数"],
}


def kakomon_boxes(school, me, by_class, mine):
    """過去問の見本：KAKOMON のコースに、過去問の提出箱を 4 本（そのコースの担当の講師の名で。担当が無ければ本人）。
    前の 2 本は期限ずみで、見本の生徒（先頭）は採点と赤入れが返っていて、ほかは出したまま未評価（講師の今日やることに出る）。
    あとの 2 本は期限前で、まだ出していない（生徒の「これから取り組む」）。
    本物の過去問は、講師が授業計画の「提出箱を作る」で種類「過去問の添削」・年度・学校を選んで出す（これと同じ make_quiz）。"""
    plans = C.all_courses(school)
    made = 0
    for key, titles in KAKOMON.items():
        p = plans.get(key)
        if not p:
            continue
        by = (p.get("teachers") or [me["sid"]])[0]
        cls = (p.get("classes") or [""])[0]
        sids = by_class.get(cls) or []
        kw, kh = D._dims(p.get("subject"))
        for i, title in enumerate(titles):
            days = (-10, -3, 7, 14)[i]
            try:
                rec = D._quiz_at(school, T.make_quiz(school, key, p, title, int((time.time() + days * DAY) * 1000), by, kind="過去問"), 4.0)
            except ValueError:
                continue
            made += 1
            if days > 0:
                continue
            rate = T.ratings(school)
            for j, sid in enumerate(D._only(rec.get("students") or [])):
                put_at = int(time.time() + (days + 1) * DAY)
                try:
                    SUB.put(school, rec["id"], sid, [{"kind": "png", "data": D._note_png(kw, kh, "%s|%s|kk" % (rec["id"], sid))}], now=put_at)
                except (ValueError, OSError):
                    continue
                if sids and sid == sids[0]:
                    rate.setdefault(rec["id"], {})[sid] = {"v": 4 if i else 5, "s": 5, "at": put_at + DAY, "by": by}
                    SUB.mark_seen(school, rec["id"], sid, by, "大問3の図形は、補助線を引いてから考えると早いです。", now=put_at + DAY)
                    SUB.put_return(school, rec["id"], sid, [{"kind": "png", "data": D._mark_png(kw, kh, "%s|%s|kk" % (rec["id"], sid))}],
                                   by, None, now=put_at + DAY)
                    # 点数（生徒の自己申告）の見本。古い方の 1 本だけ
                    if i == 0:
                        SUB.put_score(school, rec["id"], sid, 72, 100)
            T.save_ratings(school, rate)
    return made


def mark_demo(school, before, demo_sids, now=None):
    """この作業で新しくできた宿題・提出箱に demo の印。

    **期限の過ぎた回**の受け取り手は、ためしの生徒だけにする：出す関数（publish_courses・make_quiz）はクラスの
    在籍の生徒全員に出すので、ためしでない生徒（席を使い始めた子）が同じクラスにいると、学期のはじめからの架空の宿題が
    その子に「未提出」で山ほど付く。外して、0 人になる宿題は消す（students が空の宿題は「クラス全員」の意味に変わる）。
    **期限前の回（今の宿題）はためしでない生徒にも届ける。** 入った日から今の宿題が見えるのが本物の形で、ためし運用でも
    同じでなければならない（2026-10-10 本人：新しく作った中3R の口座に宿題が出なかった）。
    """
    nowms = (now or time.time()) * 1000
    asg = T.assignments(school)
    k = 0
    for aid in list(asg):
        x = asg[aid]
        if aid in before or not isinstance(x, dict) or x.get("demo"):
            continue
        if int(x.get("dueAt") or 0) < nowms:
            x["students"] = [s for s in (x.get("students") or []) if s in demo_sids]
            if not x["students"]:
                asg.pop(aid)
                continue
        x["demo"] = True
        k += 1
    T.save_assignments(school, asg)
    return k


def default_weeks():
    """学期が始まってからの週数（6以上）。demo_running と同じ決め方。"""
    ts = SOURCE.term_start()
    today = datetime.date.today()
    this_mon = today - datetime.timedelta(days=today.weekday())
    return max(6, (this_mon - datetime.date(*map(int, ts.split("-")))).days // 7) if ts else 8


def _needs_slots(p):
    return p.get("unit") != "week" and not p.get("slots")


def build(school, me_lid, weeks=None, out=print, extra_classes=(), keep=()):
    """作る。何度流しても同じ（先に clean）。要約の辞書を返す。"""
    db = T.accounts(school)
    me = db.get(me_lid)
    if not me or me.get("role") != "teacher" or not me.get("sid"):
        raise SystemExit("× 講師 %s が校舎 %s にいません" % (me_lid, school))
    if weeks is None:
        weeks = default_weeks()
    weeks = max(6, int(weeks))
    summary = {"notes": []}
    with T.LOCK:
        summary["cleaned"] = clean(school)
        plans = C.all_courses(school)
        mine = sorted(C.of_teacher(school, me["sid"]))
        if not mine:
            raise SystemExit("× %s の担当コースがありません（deploy/担当.sh で担当を入れてから）" % me_lid)
        # 全講師の全コース（担当があり、在籍クラスか指名の元があるもの）
        keys = sorted(k for k, p in plans.items() if p.get("teachers") and (p.get("classes") or NAMED_FROM.get(k)))
        summary["mine"] = mine
        summary["teachers"] = sorted({t for k in keys for t in (plans[k].get("teachers") or [])})

        # 生徒：クラスごとに 5〜15 人を今ある口座から
        by_class, by_lid = pick_students(school, extra_classes, keep=keep)
        if not by_class:
            raise SystemExit("× 生徒の口座（席）が 1 つもありません")
        demo_sids = {s for v in by_class.values() for s in v}
        db = T.accounts(school)
        summary["classes"] = sorted(by_class)
        summary["students_n"] = len(demo_sids)
        # 在籍クラスの無いコースは、指名で受ける
        data = L.load(school)
        for k in keys:
            p = data["plans"][k]
            if not p.get("classes"):
                want = [s for c in NAMED_FROM.get(k, []) for s in by_class.get(c, [])]
                p["students"] = sorted(set(p.get("students") or []) | set(want))
        L.save(school, data)

        # demo_running の絞り：記録はためしの生徒だけ。見本の生徒は各クラスの先頭
        D.ONLY = demo_sids
        D.TEACHER_LID = me_lid
        D.PHOTO_KEYS = set(keys)
        D.SAMPLE_SEATS = tuple(sorted({str(db[by_lid[c][0]].get("seat")) for c in by_lid}))
        D.SAMPLE_LIDS = [by_lid[c][0] for c in sorted(by_lid)]
        D.HIST_WEEKS = weeks
        try:
            today = datetime.date.today()
            mon = today - datetime.timedelta(days=today.weekday())
            monday = time.mktime(mon.timetuple())
            start = (mon - datetime.timedelta(days=7 * weeks)).isoformat()

            # 授業計画
            defs = {c["key"]: c for c in D.KEN_COURSES}
            defs.update(EXTRA_DEFS)
            planned, skipped = [], []
            for k in keys:
                p = C.all_courses(school)[k]
                if _needs_slots(p):
                    skipped.append(k)          # 時間割に無いコースは、日付を振れない（deploy/時間割.sh）
                    continue
                c = defs.get(k) if k in mine else None
                if c:
                    klass = (p.get("classes") or NAMED_FROM.get(k) or [""])[0]
                    top = by_class.get(klass, [])[:1] if c.get("top") else None
                    D.make_course_plan(school, k, c, me["sid"], start, weeks, top)
                else:
                    D.make_simple_plan(school, k, start, weeks)
                planned.append(k)
            data = L.load(school)
            for k in planned:
                data["plans"][k]["demo"] = True
            L.save(school, data)
            for k in planned:
                L.set_use(school, k, 4, "demo")
            # 毎日テストは、その教科のコースの段階が 4 のときだけ生徒に出る（useBySubject）。ためしの生徒のクラスが受ける
            # コースは、計画が無くても 4 にして、受講している全教科の毎日テストが出るようにする（印 appBy=demo）
            extra_on = []
            for k, p in sorted(C.all_courses(school).items()):
                if k in planned or not (set(p.get("classes") or []) & set(by_class)):
                    continue
                if C.use_level(p) < 4:
                    L.set_use(school, k, 4, "demo")
                    extra_on.append(k)
            summary["levels"] = extra_on
            summary["planned"], summary["skipped"] = planned, skipped
            if skipped:
                summary["notes"].append("時間割に無いので計画を入れていません: " + " ".join(skipped))

            # 組分けテストの日程（まだ無ければ、原本の日程表から。本物の日程なので --clean でも消さない）
            if not E.all_exams(school) and SOURCE.default_exams():
                E.save(school, {"exams": SOURCE.default_exams(), "prepDays": E.DEFAULT_PREP_DAYS})

            # 宿題（学期のはじめから今日まで。本番と同じ関数で）
            before = set(T.assignments(school))
            first = ""
            for k in planned:
                st = (L.plan(school, k) or {}).get("start") or ""
                if st and (not first or st < first):
                    first = st
            pub_from = monday - weeks * 7 * DAY
            if first:
                pub_from = min(pub_from, time.mktime(time.strptime(first, "%Y-%m-%d")) - DAY)
            summary["homework"] = D.publish_courses_past(school, pub_from)
            marked = mark_demo(school, before, demo_sids)

            # 記録
            summary["students"] = D.student_records(school, monday)
            summary["ratings"] = D.paper_ratings(school)
            summary["prep"] = D.prep_results(school)
            summary["photos"] = D.hw_submissions(school)
            summary["scores"] = D.demo_scores(school)
            D.align_notes(school)
            # 添削の見本と保護者のメッセージは、本人の担当のうち算数・数学と国語のクラスから 2 つ
            pairs = []
            for k in mine:
                p = plans[k]
                for cid in (p.get("classes") or []):
                    if p.get("subject") in ("math", "japanese") and cid in by_class and (cid, p["subject"]) not in pairs:
                        pairs.append((cid, p["subject"]))
            pairs = sorted(pairs, key=lambda x: (x[1] != "math", x[0]))[:2]
            summary["returned"] = D.returned_papers(school, pairs)
            summary["quiz"] = D.quiz_box(school)
            summary["essay"] = D.essay_box(school)
            summary["messages"] = D.demo_messages(school, pairs)

            # 講師ごとに 1 つ：きのう期限の提出箱に、未評価の写真（どの講師も今日チェックを試せる）。
            # 本人（--me）は担当コースに提出箱が十分あるので除く
            # 講師ごとに「ためしの生徒がいる」最初のコース（在籍クラスの無いコースは指名で）。生徒のいないコースは提出箱を作れない
            first_of = {}
            for k in planned:
                p_ = C.all_courses(school)[k]
                has = (set(p_.get("classes") or []) & set(by_class)) or (not p_.get("classes") and any(s in demo_sids for s in (L.plan(school, k) or {}).get("students") or []))
                if not has:
                    continue
                for tsid in (p_.get("teachers") or []):
                    first_of.setdefault(tsid, k)
            lid_of = {a.get("sid"): lid for lid, a in db.items() if a.get("role") == "teacher"}
            boxes, picked = 0, {}
            for tsid, k in sorted(first_of.items(), key=lambda kv: lid_of.get(kv[0], "")):
                if tsid == me["sid"] or not lid_of.get(tsid):
                    continue
                p = C.all_courses(school)[k]
                try:
                    rec = D._quiz_at(school, T.make_quiz(school, k, p, QUIZ_TITLE.get(p.get("subject"), "小テスト 第1回"),
                                                         int((time.time() - 1 * DAY) * 1000), tsid), 2.0)
                except ValueError:
                    continue
                picked[lid_of[tsid]] = k
                bw, bh = D._dims(p.get("subject"))         # 国語は横長、ほかは縦長
                for sid in D._only(rec.get("students") or []):
                    try:
                        SUB.put(school, rec["id"], sid,
                                [{"kind": "png", "data": D._note_png(bw, bh, "%s|%s|box" % (rec["id"], sid))}],
                                now=int(time.time() - 0.5 * DAY))
                        boxes += 1
                    except (ValueError, OSError):
                        continue
            summary["boxes"], summary["picked"] = boxes, picked
            # 過去問（中3・小6 の「過去問」のタブ）：やった 2 本（見本は添削と点数が返っている・ほかは未評価）＋これから 2 本
            summary["kakomon"] = kakomon_boxes(school, me, by_class, mine)
            summary["marked"] = marked + mark_demo(school, before, demo_sids)
            # ためしでない在籍の生徒（席を使い始めた子）に、今の宿題（期限前）を届ける（入るたびにも足されるが、待たせない）
            real = [lid for lid, a in T.accounts(school).items()
                    if a.get("role") == "student" and not a.get("leftAt") and not is_demo_student(lid, a)]
            summary["joined"] = T.join_open_homework(school, real) if real else 0
            # 入口の「ためしに見る」の生徒（学年ごとに 2 人）
            summary["trialPick"] = trial_picks(school, by_lid, extra_classes)
        finally:
            D.ONLY = None
            D.TEACHER_LID = None
            D.PHOTO_KEYS = None
            D.SAMPLE_SEATS = ("01", "1")
            D.SAMPLE_LIDS = None
    return summary


def main():
    ap = argparse.ArgumentParser(description="ためし運用のデモ（本物の校舎の今ある口座に、クラスごとに 5〜15 人ぶん）")
    ap.add_argument("--school", default="waseaca-london")
    ap.add_argument("--me", default="wt01", help="架空の宿題の文まで入れる講師のログインID（本人）")
    ap.add_argument("--weeks", type=int, default=None, help="学期が始まってからの週数（6以上）。既定は原本の日程表から")
    ap.add_argument("--clean", action="store_true", help="ためしのデータを消す（作らない）")
    ap.add_argument("--accounts", action="store_true", help="（前との互換。前の形のためし用の生徒 wd… は --clean でいつも消す）")
    ap.add_argument("--pick-classes", default="", help="入口の生徒に、このクラスの見本も足す（検査用。j3r,e4b のように）")
    ap.add_argument("--keep", default="", help="選ばない口座（検査の土台が決め打ちで使う席。we4a01,we4a02 のように）")
    a = ap.parse_args()
    school = paths.check_school(a.school)
    if T.is_demo_school(school):
        print("× %s は架空のデモの校舎です。ここは本物の校舎のためのものです（デモ校は demo_running.py）。" % school)
        return 1
    if a.clean:
        n = clean(school, accounts=a.accounts)
        print("ためしのデータを消しました: 宿題・提出箱 %d ／ 計画 %d ／ 生徒 %d 人の記録（席に戻した口座 %d・前の形の口座を消した %d）"
              % (n["assignments"], n["plans"], n["students"], n["restored"], n["accounts"]))
        if n.get("kept"):
            print("  ためしでない生徒の記録が付いた宿題 %d 件は、本物の宿題として残しました（計画も残しています）" % n["kept"])
        return 0
    extra = [c.strip() for c in a.pick_classes.split(",") if c.strip()]
    print("ためし運用のデモを作ります: %s（本人 %s。全講師の全コース、クラスごとに %d〜%d 人）\n" % (school, a.me, PER_CLASS[0], PER_CLASS[1]))
    s = build(school, a.me, a.weeks, extra_classes=extra, keep=[c.strip() for c in a.keep.split(",") if c.strip()])
    c = s["cleaned"]
    if c["assignments"] or c["plans"]:
        print("  前のためしのデータ  宿題・提出箱 %d ／ 計画 %d を消してから作りました" % (c["assignments"], c["plans"]))
    print("  生徒            %d 人（%d クラス。今ある口座から無作為に。席だったものは在籍の生徒に）" % (s["students_n"], len(s["classes"])))
    own = [k for k in s["planned"] if k in s["mine"]]
    print("  授業計画        %d コース（講師 %d 人。%s の担当 %d ＋ ほか %d）" % (len(s["planned"]), len(s["teachers"]), a.me, len(own), len(s["planned"]) - len(own)))
    print("  出した宿題      %d件（学期のはじめから今日まで。印 demo %d件）" % (s["homework"], s["marked"]))
    print("  生徒の記録      %d名（毎日テスト・連続日）" % s["students"])
    print("  紙の評価        %d件 ／ ノートの写真 %d件 ／ 塾内テスト %d本 ／ 対策テスト %d件" % (s["ratings"], s["photos"], s["scores"], s["prep"]))
    print("  返した添削      %d件 ／ 漢字テスト（提出箱）%d人ぶん ／ 作文 %d件 ／ 保護者のメッセージ %d件" % (s["returned"], s["quiz"], s["essay"], s["messages"]))
    print("  提出箱の写真    %d枚（講師ごとに 1 つ、きのう期限の提出箱に未評価：%s）" % (s["boxes"], "・".join("%s=%s" % kv for kv in sorted(s["picked"].items()))))
    print("  段階            %d コースを「毎日テストまで」に（計画のある %d ＋ 生徒のクラスが受けるコース %d）"
          % (len(s["planned"]) + len(s.get("levels") or []), len(s["planned"]), len(s.get("levels") or [])))
    print("  過去問          %d本（中3R 数学・小6α 算数・小6β 算数。やった 2 本＋これから 2 本）" % s.get("kakomon", 0))
    print("  入口の生徒      %s（学年ごとに 2 人。ID だけで入れる）" % " ".join(s["trialPick"]))
    if s.get("joined"):
        print("  ためしでない生徒  今の宿題（期限前）に %d 件 足しました（席を使い始めている生徒）" % s["joined"])
    if c.get("kept"):
        print("  残した宿題      %d件（ためしでない生徒の記録が付いていたもの）" % c["kept"])
    for m in s["notes"]:
        print("  ※ " + m)
    print("\n★ 消すときは --clean（席だった口座は席に戻ります）。本番に切り替えるとき（本番切替.sh）は生徒ごと退避されます。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
