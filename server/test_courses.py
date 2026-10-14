#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""コースが決めたとおりに効いているかを確かめる。

なぜこの検査が要るか
--------------------
コースは「講師の担当」「受け取る生徒」「授業日」を1件で決める。
どれか1つが静かにずれると、画面には何も出ないまま
**担当外の生徒が見える／受け取るべき生徒に宿題が届かない** という形で壊れる。
目で見ても分からない種類の性質なので、決めごとをそのまま確かめる。

  ・合同の担当者に、各クラスの生徒が見える
  ・指名の生徒だけが見える（在籍クラスが別でも）
  ・受け取り手は受講科目で絞られる。指名は指名どおり
  ・担当外の講師は、計画を保存できない（別の講師の計画を上書きできない）
  ・週2回のコースは火→木と並び、1コマずらすと火→木に動く
  ・総復習は週で数える（5週に1週）
  ・夏時間の終わりをまたいでも日付がずれない
  ・CSV を出して入れ直すと元に戻る。1行でもおかしければ何も入れない
  ・期間の外のコースは時間割に出ない
  ・時間割（courses-slots）は時間だけを入れ替える。講師・クラス・指名・授業計画・使う印は変えない。
    無いコースは講師なし・紙のままで作る。--yes が無ければ何もしない。1行でもおかしければ何も入れない

    python3 server/test_courses.py
"""

import io
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/test-courses"
os.environ["MYACADY_ROOT"] = ROOT
os.environ["TZ"] = "Europe/London"      # 期限の時刻を、どの機械でも同じに数える
time.tzset()
sys.path.insert(0, HERE)
shutil.rmtree(ROOT, ignore_errors=True)

import paths                                     # noqa: E402
import lessons as L                              # noqa: E402
import courses as C                              # noqa: E402
import tube_server as T                          # noqa: E402

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


def setup():
    paths.ensure_school(SCHOOL)
    paths.save(paths.school_file(SCHOOL, "school.json"),
               {"id": SCHOOL, "name": "検査校", "code": "l", "tz": "Europe/London"})
    paths.save(paths.school_file(SCHOOL, "curriculum.json"), {"v": 2, "classes": [
        {"id": "j2t", "name": "中2T", "grade": "j2"},
        {"id": "j2r", "name": "中2R", "grade": "j2"},
        {"id": "j2d", "name": "中2D", "grade": "j2"},
        {"id": "j3r", "name": "中3R", "grade": "j3"}]})
    mk = T.add_account
    for lid, seat, cid, subs in [
            ("lj2t01", "01", "j2t", "国数英理社"), ("lj2t02", "02", "j2t", "国英"),
            ("lj2r01", "01", "j2r", "国数英"), ("lj2r02", "02", "j2r", "国数英理社"),
            ("lj2r03", "03", "j2r", ""),
            ("lj2d01", "01", "j2d", "国数"), ("lj2d02", "02", "j2d", "国数英理社"),
            ("lj3r01", "01", "j3r", "国数英"), ("lj3r02", "02", "j3r", "国数英"),
            ("lj3r03", "03", "j3r", "国数英")]:
        mk(SCHOOL, lid, "student-pass", seat, "student", cid[:2], cid)
        if subs:
            db = T.accounts(SCHOOL)
            db[lid]["subjects"] = C.parse_subjects(subs)
            T.save_accounts(SCHOOL, db)
    # コースだけを持つ講師（assign は空の配列）と、旧 assign の講師
    for lid, cls, assign in [("t-a", ["j2t"], []), ("t-b", ["j2r"], []),
                             ("l-a", ["j2t"], [["j2t", "math", 1, 1]]),
                             ("l-b", ["j2d"], [["j2d", "math", 2, 1]])]:
        mk(SCHOOL, lid, lid + "-pass", "T1", "teacher", "j2", cls[0], classes=cls)
        db = T.accounts(SCHOOL)
        db[lid]["assign"] = assign
        T.save_accounts(SCHOOL, db)


CSV = """id,教科,名前,学年,講師,時間,クラス,指名,単位,期間
j2tr,英語,中2TR 英語,j2,t-a,火16:40-18:10,j2t j2r j2d,,授業,
j2,理科,中2 理科,j2,t-a,月19:30-20:30,j2t j2r j2d,,授業,
j3doku,数学,中3 土特（RD特） 数学,j3,t-a,土16:00-17:10,,j3r-01 j3r-02,授業,
j2r,数学,中2R 数学,j2,t-b,火20:10-21:40 木20:10-21:40,j2r,,授業,
kaki-j2,数学,夏期講習 中2 数学,j2,t-a,月10:00-12:00,j2r,,授業,2020-07-20〜2020-08-25
"""


def write(path, text):
    with io.open(path, "w", encoding="utf-8-sig") as f:
        f.write(text)


def acc_of(lid):
    a = dict(T.accounts(SCHOOL)[lid])
    a["school"] = SCHOOL
    return a


def sid_of(lid):
    return T.accounts(SCHOOL)[lid]["sid"]


def unit_checks():
    print("\nCSV を入れる")
    db = T.accounts(SCHOOL)
    known = set(T.class_table(SCHOOL).keys())
    bad_rows = [
        ("知らない在籍クラスは弾く", "j9x,英語,x,j2,t-a,火16:40-18:10,j9x,,授業,"),
        ("知らない講師は弾く", "j2x,英語,x,j2,nobody,火16:40-18:10,j2r,,授業,"),
        ("クラスと指名を両方書くと弾く", "j2x,英語,x,j2,t-a,火16:40-18:10,j2r,j3r-01,授業,"),
        ("時刻の書き間違いを弾く", "j2x,英語,x,j2,t-a,火25:00-26:00,j2r,,授業,"),
        ("知らない教科を弾く", "j2x,音楽,x,j2,t-a,火16:40-18:10,j2r,,授業,"),
    ]
    for name, line in bad_rows:
        path = os.path.join(ROOT, "bad.csv")
        write(path, C.HEAD and ",".join(C.HEAD) + "\n" + line + "\n")
        row = C.read_csv(path)[0]
        try:
            C.parse_row(row, db, known)
            check(name, False, "通ってしまった")
        except ValueError:
            check(name, True)

    path = os.path.join(ROOT, "courses.csv")
    write(path, CSV)
    parsed = [C.parse_row(r, db, known) for r in C.read_csv(path)]
    made, changed = C.upsert(SCHOOL, parsed)
    check("5件が入る", made == 5, (made, changed))
    allc = C.all_courses(SCHOOL)
    check("鍵は <ID>:<教科>", set(allc) == {"j2tr:english", "j2:science",
                                          "j3doku:math", "j2r:math", "kaki-j2:math"},
          sorted(allc))
    made, changed = C.upsert(SCHOOL, parsed)
    check("同じ CSV を入れ直しても変わらない", (made, changed) == (0, 0), (made, changed))

    # 出して入れ直すと元に戻る
    out = os.path.join(ROOT, "export.csv")
    C.write_csv(SCHOOL, out)
    again = dict(C.parse_row(r, db, known) for r in C.read_csv(out))
    same = all({k: again[key].get(k) for k in C.DEF_KEYS} ==
               {k: allc[key].get(k) for k in C.DEF_KEYS} for key in allc)
    check("CSV を出して入れ直すと元に戻る", same)

    print("\n講師の担当")
    ta = acc_of("t-a")
    pairs = T.teacher_pairs(ta)
    check("合同の担当者は、各クラスの英語を持つ",
          all(p in pairs for p in [("j2t", "english"), ("j2r", "english"), ("j2d", "english")]),
          pairs)
    check("コースID自身も持つ（出した宿題の classId）",
          ("j2tr", "english") in pairs and ("j3doku", "math") in pairs, pairs)
    # 指名のコース（土特）は、在籍クラス（中3R）全体の数学を見せる理由にならない
    check("指名のコースは、在籍クラス全体の教科を持たせない", ("j3r", "math") not in pairs, pairs)
    # 期間の外のコース（終わった講習）も担当に残す ―― 講習の宿題を後から採点するため
    check("終わった講習も担当に残る（後から採点できる）", ("kaki-j2", "math") in pairs, pairs)
    check("コースだけの講師に、在籍クラスの全教科が見えない",
          ("j2t", "japanese") not in pairs, pairs)
    check("can_see: 合同の担当で中2D の英語が見える", T.can_see(ta, "j2d", "english"))
    check("can_see: 担当外の中3R 数学は見えない", not T.can_see(ta, "j3r", "math"))

    may_read = T.Handler.may_read
    check("指名の生徒は、在籍クラスが別でも記録が読める",
          may_read(None, ta, sid_of("lj3r01")))
    check("指名していない生徒の記録は読めない",
          not may_read(None, ta, sid_of("lj3r03")))
    la = acc_of("l-a")
    check("旧 assign の講師はそのまま（中2T 数学）",
          T.teacher_pairs(la) == [("j2t", "math")], T.teacher_pairs(la))

    print("\n時間割")
    slots = T.teacher_slots(ta)
    keys = [s.get("key") for s in slots]
    check("期間の外のコース（過去の講習）は出ない", "kaki-j2:math" not in keys, keys)
    check("曜日と時刻の順に並ぶ",
          keys == ["j2:science", "j2tr:english", "j3doku:math"], keys)
    check("コマに時刻とコース名がある",
          slots and slots[0].get("start") == "19:30" and slots[0].get("name") == "中2 理科",
          slots[:1])
    tb = T.teacher_slots(acc_of("t-b"))
    check("週2回のコースは2コマ", [s["day"] for s in tb] == [2, 4], tb)

    print("\n受け取る生徒")
    sci = C.receivers(SCHOOL, allc["j2:science"])
    want = sorted(sid_of(x) for x in ["lj2t01", "lj2r02", "lj2r03", "lj2d02"])
    check("理科は、理科を受講している生徒（受講科目の無い生徒は全教科）", sci == want,
          (len(sci), len(want)))
    eng = C.receivers(SCHOOL, allc["j2tr:english"])
    check("中2D の国数の生徒は英語を受け取らない", sid_of("lj2d01") not in eng)
    check("中2D の国数英理社の生徒は英語を受け取る", sid_of("lj2d02") in eng)
    doku = C.receivers(SCHOOL, allc["j3doku:math"])
    check("指名のコースは指名どおり", doku == sorted([sid_of("lj3r01"), sid_of("lj3r02")]),
          doku)
    db = T.accounts(SCHOOL)
    db["lj2t01"]["leftAt"] = int(time.time())
    T.save_accounts(SCHOOL, db)
    check("在籍が終わった生徒は受け取らない",
          sid_of("lj2t01") not in C.receivers(SCHOOL, allc["j2:science"]))
    db = T.accounts(SCHOOL)
    db["lj2t01"].pop("leftAt", None)
    T.save_accounts(SCHOOL, db)
    check("生徒の教科から引く計画: 中2R の英語は合同コース",
          C.key_for(SCHOOL, "j2r", "english", "j2") == "j2tr:english")
    check("コースが無い教科は旧来の 学年:教科",
          C.key_for(SCHOOL, "j2r", "social", "j2") == "j2:social")

    print("\n日付")
    twice = {"slots": [{"day": 2, "start": "18:20", "end": "19:50"},
                       {"day": 4, "start": "18:20", "end": "19:50"}]}
    ds = C.dates(twice, "2026-09-14", 4)
    check("週2回は火・木と並ぶ",
          ds == ["2026-09-15", "2026-09-17", "2026-09-22", "2026-09-24"], ds)
    check("1コマずらすと火→木", C.step(twice, "2026-09-15", 1) == "2026-09-17")
    check("1コマ戻すと木→火", C.step(twice, "2026-09-17", -1) == "2026-09-15")
    weekly = {"unit": "week", "weekday": 1,
              "slots": [{"day": 1, "start": "16:40", "end": "18:10"},
                        {"day": 4, "start": "16:40", "end": "18:10"}]}
    ds = C.dates(weekly, "2026-09-14", 3)
    check("1回＝1週のコースは月曜に週1行", ds == ["2026-09-14", "2026-09-21", "2026-09-28"], ds)
    ds = C.dates({"slots": [{"day": 2}]}, "2026-10-20", 3)
    check("夏時間の終わり（10/25）をまたいでも火曜のまま",
          ds == ["2026-10-20", "2026-10-27", "2026-11-03"], ds)
    ds = L.build_dates("2026-10-20", 2, 3)
    check("旧来の計画も夏時間でずれない（2=火）",
          ds == ["2026-10-20", "2026-10-27", "2026-11-03"], ds)
    check("旧来の計画で「月」(1) を選ぶと月曜に入る",
          L.build_dates("2026-09-09", 1, 1) == ["2026-09-14"], L.build_dates("2026-09-09", 1, 1))
    p = dict(weekly, start="2026-09-14")
    check("総復習は5週目の週（10/12 の週）",
          C.is_review(p, "2026-10-12") and C.is_review(p, "2026-10-15")
          and not C.is_review(p, "2026-10-05"))

    def hm(ms):
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ms / 1000))

    rows = [{"n": 1, "date": "2026-09-15"}, {"n": 2, "date": "2026-09-17"}]
    check("期限: 中3（火の回）は次の授業（木 18:20）",
          hm(C.due_ms(twice, rows, rows[0])) == "2026-09-17 18:20", hm(C.due_ms(twice, rows, rows[0])))
    check("期限: 最後の回は7日後の授業開始",
          hm(C.due_ms(twice, rows, rows[1])) == "2026-09-24 18:20", hm(C.due_ms(twice, rows, rows[1])))
    rows = [{"n": 1, "date": "2026-09-14"}, {"n": 2, "date": "2026-09-21"}]
    check("期限: 小5β（月曜にまとめて出す）は次の月曜 16:40",
          hm(C.due_ms(weekly, rows, rows[0])) == "2026-09-21 16:40", hm(C.due_ms(weekly, rows, rows[0])))
    check("毎週固定: 2500 の手前で止まる",
          C.weekly_range({"step": 125, "at": 2400, "wrap": 2500}) == (2401, 2500))
    check("毎週固定: 2500 の次は 1 に戻る",
          C.weekly_range({"step": 125, "at": 2500, "wrap": 2500}) == (1, 125))
    check("受講科目の書き方: 国数英理社", C.parse_subjects("国数英理社") ==
          ["japanese", "math", "english", "science", "social"])
    try:
        C.parse_subjects("国音")
        check("受講科目の知らない字を弾く", False)
    except ValueError:
        check("受講科目の知らない字を弾く", True)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    n = s.getsockname()[1]
    s.close()
    return n


def server_checks():
    print("\n計画を保存できるのは担当の講師だけ")
    port = free_port()
    base = "http://127.0.0.1:%d" % port

    def call(method, path, token=None, body=None):
        req = urllib.request.Request(base + path, method=method)
        if token:
            req.add_header("Authorization", "Bearer " + token)
        if body is not None:
            req.add_header("Content-Type", "application/json")
            req.data = json.dumps(body).encode()
        try:
            r = urllib.request.urlopen(req, timeout=10)
            return r.status, json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode() or "{}")
            except ValueError:
                return e.code, {}

    env = dict(os.environ, MYACADY_ROOT=ROOT)
    srv = subprocess.Popen([sys.executable, os.path.join(HERE, "tube_server.py"),
                            "serve", "--port", str(port)],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=1)
                break
            except Exception:
                time.sleep(0.25)

        def login(lid):
            import scram
            st, b = scram.login(base, lid, lid + "-pass")
            return b.get("token")

        ta, tb, la, lb = login("t-a"), login("t-b"), login("l-a"), login("l-b")
        check("4人の講師が入れる", all([ta, tb, la, lb]))

        rows = [{"topic": "第%d回" % i, "hw": {"items": [
            {"text": "Sirius21 p.%d-%d" % (i, i + 2)}, {"text": "Jack21 p.%d-%d" % (i, i + 3)}]}}
            for i in range(1, 5)]
        body = {"start": "2026-09-14", "weekday": 0, "dueDays": 7, "classId": "", "rows": rows}
        st, b = call("PUT", "/api/lessons/j2tr:english", ta, body)
        check("担当の講師はコースの計画を保存できる", st == 200, (st, b))
        got = (b.get("lessons") or [])
        check("日付はコースの曜日（火）で振られる",
              [l.get("date") for l in got] == ["2026-09-15", "2026-09-22", "2026-09-29", "2026-10-06"],
              [l.get("date") for l in got])
        check("1回に2ブロックが保存で消えない",
              got and len((got[0].get("hw") or {}).get("items") or []) == 2, got[:1])
        p = L.plan(SCHOOL, "j2tr:english")
        check("保存してもコースの定義（講師・時間割）は変わらない",
              p.get("teachers") == [sid_of("t-a")] and p.get("slots") ==
              [{"day": 2, "start": "16:40", "end": "18:10"}], p.get("slots"))

        st, _ = call("PUT", "/api/lessons/j2tr:english", tb, body)
        check("担当していない講師は保存できない", st in (403, 409), st)
        st, _ = call("POST", "/api/lessons/j2tr:english/shift", tb, {"at": 1, "by": 1})
        check("担当していない講師はずらせない", st in (403, 409), st)

        legacy = {"start": "2026-09-14", "weekday": 1, "dueDays": 7, "classId": "j2t",
                  "rows": [{"topic": "連立方程式", "hw": {"text": "問題集 p.10-12"}}]}
        st, _ = call("PUT", "/api/lessons/j2:math", la, legacy)
        check("旧来の計画: 中2T 数学の講師が保存できる", st == 200, st)
        st, b = call("PUT", "/api/lessons/j2:math", lb, dict(legacy, classId="j2d"))
        check("旧来の計画: 同じ学年・教科の別の講師は上書きできない（409）", st == 409, (st, b))
        check("上書きされていない", (L.plan(SCHOOL, "j2:math").get("classId") == "j2t"))

        st, b = call("GET", "/api/me", ta)
        slots = (b.get("profile") or {}).get("assign") or []
        check("講師の画面に、コースのコマが時刻つきで届く",
              [s.get("start") for s in slots] == ["19:30", "16:40", "16:00"], slots)
    finally:
        srv.terminate()
        srv.wait(timeout=5)


def cli_checks():
    print("\nCSV の取り込み（コマンド）")
    env = dict(os.environ, MYACADY_ROOT=ROOT)
    bad = os.path.join(ROOT, "bad-many.csv")
    write(bad, ",".join(C.HEAD) + "\n"
          "newc,英語,新しいコース,j2,t-a,水16:40-18:10,j2r,,授業,\n"
          "oops,英語,まちがい,j2,t-a,水16:40-18:10,j9z,,授業,\n")
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"),
                        "courses-import", bad, "--school", SCHOOL, "--yes"],
                       env=env, capture_output=True, text=True)
    check("1行でもおかしければ失敗で終わる", r.returncode == 1, r.stdout[-200:])
    check("何も入っていない（正しい行も入れない）",
          "newc:english" not in C.all_courses(SCHOOL))


def slots_checks():
    print("\n時間割（時間だけを入れ替える）")
    env = dict(os.environ, MYACADY_ROOT=ROOT)
    run = lambda *a: subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "courses-slots", *a,
                                     "--school", SCHOOL], env=env, capture_output=True, text=True)
    keep = ("teachers", "classes", "students", "lessons", "app", "unit", "weekday", "from", "to", "name")
    before = {k: json.dumps(C.all_courses(SCHOOL)["j2r:math"].get(k), sort_keys=True) for k in keep}
    good = os.path.join(ROOT, "slots.csv")
    write(good, ",".join(C.SLOT_HEAD) + "\n"
          "j2r,数学,別の名前,j2,水20:10-21:40,j2t\n"
          "j3doku,数学,中3 土特（RD特） 数学,j3,土16:00-17:10,\n"
          "j3rc,数学,中3R キャッチアップ講座,j3,水20:10-21:40,\n")
    r = run(good)
    check("--yes が無ければ何もしない（予告だけ）", r.returncode == 0 and "j3rc:math" not in C.all_courses(SCHOOL)
          and "時間が変わる 1件・新しいコース 1件" in r.stdout, r.stdout[-300:])
    r = run(good, "--yes")
    cs = C.all_courses(SCHOOL)
    check("入った（作った1・直した1・変わらない1）", r.returncode == 0 and "作った 1件 / 時間を直した 1件 / 変わらない 1件" in r.stdout, r.stdout[-300:])
    check("時間だけが変わる", cs["j2r:math"].get("slots") == [{"day": 3, "start": "20:10", "end": "21:40"}], cs["j2r:math"].get("slots"))
    after = {k: json.dumps(cs["j2r:math"].get(k), sort_keys=True) for k in keep}
    check("講師・クラス・指名・授業計画・使う印・名前は変わらない", before == after,
          str([k for k in keep if before[k] != after[k]]))
    n = cs.get("j3rc:math") or {}
    check("無いコースは講師なし・紙のまま・計画なしで作る",
          n.get("teachers") == [] and n.get("app") is False and n.get("lessons") == [] and n.get("students") == []
          and n.get("name") == "中3R キャッチアップ講座" and n.get("grade") == "j3", str(n)[:200])
    bad = os.path.join(ROOT, "slots-bad.csv")
    write(bad, ",".join(C.SLOT_HEAD) + "\n"
          "j2r,数学,中2R 数学,j2,月16:40-18:10,j2r\n"
          "j9q,数学,まちがい,j2,水25:00-26:00,j2r\n")
    r = run(bad, "--yes")
    check("1行でもおかしければ失敗で終わり、何も入れない", r.returncode == 1 and
          C.all_courses(SCHOOL)["j2r:math"].get("slots") == [{"day": 3, "start": "20:10", "end": "21:40"}], r.stdout[-200:])
    with L.paths_lock():
        data = L.load(SCHOOL)
        data["plans"]["oldp:math"] = {"lessons": []}
        L.save(SCHOOL, data)
    legacy = os.path.join(ROOT, "slots-legacy.csv")
    write(legacy, ",".join(C.SLOT_HEAD) + "\n"
          "j2r,数学,中2R 数学,j2,月16:40-18:10,j2r\n"
          "oldp,数学,古い計画,j2,月16:40-18:10,\n")
    r = run(legacy, "--yes")
    check("コースでない計画に当たれば、何も書かない", r.returncode == 1 and
          C.all_courses(SCHOOL)["j2r:math"].get("slots") == [{"day": 3, "start": "20:10", "end": "21:40"}]
          and "teachers" not in L.load(SCHOOL)["plans"]["oldp:math"], r.stdout[-200:])


def teachers_checks():
    print("\n担当（講師だけを入れ替える）")
    env = dict(os.environ, MYACADY_ROOT=ROOT)
    run = lambda *a: subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "courses-teachers", *a,
                                     "--school", SCHOOL], env=env, capture_output=True, text=True)
    # 出発点をそろえる（j2r:math は t-b だけ、j2tr:english は t-a だけ、j3rc:math は講師なし）
    base = os.path.join(ROOT, "teachers-base.csv")
    write(base, ",".join(C.TEACHER_HEAD) + "\n" "j2r,数学,t-b\n" "j2tr,英語,t-a\n" "j3rc,数学,-\n")
    run(base, "--yes")
    keep = ("slots", "classes", "students", "lessons", "app", "unit", "weekday", "from", "to", "name")
    cs0 = C.all_courses(SCHOOL)
    before = {k: json.dumps(cs0["j2r:math"].get(k), sort_keys=True) for k in keep}
    good = os.path.join(ROOT, "teachers.csv")
    write(good, ",".join(C.TEACHER_HEAD) + "\n"
          "j2r,数学,t-a t-b\n"       # 足す（2人）
          "j3doku,数学,\n"            # 空：触らない
          "j2tr,英語,-\n"             # 講師なしにする
          "j3rc,数学,t-b\n")          # 時間割で作ったコース（講師なし）に付ける
    r = run(good)
    check("--yes が無ければ何もしない（予告だけ）", r.returncode == 0 and "担当が変わる 3件・変わらない 0件" in r.stdout
          and C.all_courses(SCHOOL)["j2r:math"].get("teachers") == [sid_of("t-b")], r.stdout[-300:])
    r = run(good, "--yes")
    cs = C.all_courses(SCHOOL)
    check("入った（直した3・変わらない0）", r.returncode == 0 and "担当を直した 3件 / 変わらない 0件" in r.stdout, r.stdout[-300:])
    check("講師だけが変わる（足す・外す・付ける。空の行は触らない）",
          cs["j2r:math"].get("teachers") == [sid_of("t-a"), sid_of("t-b")] and cs["j2tr:english"].get("teachers") == []
          and cs["j3rc:math"].get("teachers") == [sid_of("t-b")]
          and cs["j3doku:math"].get("teachers") == cs0["j3doku:math"].get("teachers"),
          {k: cs[k].get("teachers") for k in ("j2r:math", "j2tr:english", "j3rc:math", "j3doku:math")})
    after = {k: json.dumps(cs["j2r:math"].get(k), sort_keys=True) for k in keep}
    check("時間・クラス・指名・授業計画・使う印・名前は変わらない", before == after,
          str([k for k in keep if before[k] != after[k]]))
    r = run(good, "--yes")
    check("もう一度流しても同じ（変わらない 3件）", r.returncode == 0 and "担当を直した 0件 / 変わらない 3件" in r.stdout, r.stdout[-200:])
    db = T.accounts(SCHOOL)
    db["l-b"]["leftAt"] = 1
    T.save_accounts(SCHOOL, db)
    for name, body in (("講師でない口座", "j2tr,英語,lj2t01\n"), ("無い ID", "j2tr,英語,nobody\n"),
                       ("在籍終了の講師", "j2tr,英語,l-b\n"), ("無いコース", "nope,数学,t-b\n")):
        bad = os.path.join(ROOT, "teachers-bad.csv")
        write(bad, ",".join(C.TEACHER_HEAD) + "\n" "j2r,数学,t-b\n" + body)
        r = run(bad, "--yes")
        check("%sがあれば失敗で終わり、何も入れない" % name, r.returncode == 1 and
              C.all_courses(SCHOOL)["j2r:math"].get("teachers") == [sid_of("t-a"), sid_of("t-b")], r.stdout[-200:])
    db = T.accounts(SCHOOL)
    db["l-b"].pop("leftAt", None)
    T.save_accounts(SCHOOL, db)


def main():
    setup()
    unit_checks()
    server_checks()
    cli_checks()
    slots_checks()
    teachers_checks()
    print()
    if ng_n:
        print("× %d件おちた" % ng_n)
        return 1
    print("すべて通った。（%d件）" % ok_n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
