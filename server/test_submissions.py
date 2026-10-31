#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""写真の提出・講師の取り込み・添削の返却・PDF・提出箱を確かめる。

なぜこの検査が要るか
--------------------
写真の道は、生徒のスマホ → サーバ → 講師のパソコン → 印刷 → 赤を入れる → 撮る → 生徒のスマホ、
と端末をまたぐ。**どこか1か所が欠けても画面には「送信しています」しか出ない**（実際そうなった）。
台帳の決まりを機械的に確かめる。

  ・出す：10枚まで、6MB まで、jpg/png/pdf だけ。出し直すと前の写真は消え、見た印も消える
  ・出し直しても、先生が返した添削は残る（先生の仕事は生徒の出し直しで消えない）
  ・講師の取り込み：見た印が付く。origin=teacher。返した添削は残る
  ・添削を返す：出していない生徒にも返せる（空の提出ができる）。返し直すと前の紙は消える
  ・all_files は出した紙＋返した紙。退塾で全部消える
  ・PDF：JPEG と PNG が A4 のページになる。壊れた画像は飛ばす。1枚も無ければ ValueError
  ・提出箱：授業計画の回とぶつからない番号（900〜）。コースの生徒全員に紙で・採点あり。
    2つ目は 901。担当外のコースには作れない（サーバの口が見る）。回の行の名前は「提出箱」＋題名

    python3 server/test_submissions.py
"""

import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/test-submissions"
os.environ["MYACADY_ROOT"] = ROOT
os.environ["TZ"] = "Europe/London"
time.tzset()
sys.path.insert(0, HERE)
shutil.rmtree(ROOT, ignore_errors=True)

import paths                                     # noqa: E402
import courses as C                              # noqa: E402
import submissions as SUB                        # noqa: E402
import pdfout                                    # noqa: E402
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


def sid(lid):
    return T.accounts(SCHOOL)[lid]["sid"]


def png(w=8, h=8, color=(200, 30, 30)):
    import struct
    import zlib

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    raw = b"".join(b"\x00" + bytes(color) * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def jpg(w=16, h=12):
    # SOF0 だけ本物の、最小の JPEG（PDF に貼るには寸法が読めれば足りる）
    import struct
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, h, w, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + sof + b"\xff\xd9"


def setup():
    paths.ensure_school(SCHOOL)
    paths.save(paths.school_file(SCHOOL, "school.json"),
               {"id": SCHOOL, "name": "検査校", "code": "l", "tz": "Europe/London"})
    paths.save(paths.school_file(SCHOOL, "curriculum.json"), {"v": 2, "classes": [
        {"id": c, "name": c, "grade": c[:2]} for c in ("j2d", "j2r")]})
    paths.save(paths.school_file(SCHOOL, "materials.json"), {"items": {}})
    for lid, seat, cid in [("lj2d01", "01", "j2d"), ("lj2d02", "02", "j2d"), ("lj2d03", "03", "j2d"),
                           ("lj2r01", "01", "j2r")]:
        T.add_account(SCHOOL, lid, "student-pass", seat, "student", "j2", cid,
                      subjects=C.parse_subjects("国数英"))
    T.add_account(SCHOOL, "t-a", "t-a-pass", "T1", "teacher", "j2", "j2d", classes=["j2d"])
    T.add_account(SCHOOL, "t-b", "t-b-pass", "T2", "teacher", "j2", "j2r", classes=["j2r"])
    ta = sid("t-a")
    base = {"teachers": [ta], "unit": "lesson", "weekday": 0, "from": "", "to": "",
            "classes": ["j2d"], "students": [], "lessons": [
                {"n": 1, "topic": "第1回", "date": "2026-09-01", "hw": {"items": []}},
                {"n": 2, "topic": "第2回", "date": "2026-09-08", "hw": {"items": []}}]}
    C.upsert(SCHOOL, [
        ("j2d:japanese", dict(base, name="中2D 国語", grade="j2", subject="japanese",
                              slots=[{"day": 2, "start": "16:40", "end": "18:10"}])),
    ])
    # 検査用の宿題（紙・採点）を1件
    d = {"title": "ノート p.10", "source": "", "classId": "j2d", "students": [sid("lj2d01"), sid("lj2d02")],
         "dueAt": int((time.time() - 3600) * 1000), "note": "", "subject": "japanese",
         "lesson": {"key": "j2d:japanese", "n": 1}}
    rec = T.valid_assignment(SCHOOL, d, paper_ok=True)
    rec.update({"id": "atest01", "createdBy": ta, "assignedAt": int(time.time() * 1000) - 86400000,
                "route": "paper", "graded": True})
    db = T.assignments(SCHOOL)
    db[rec["id"]] = rec
    T.save_assignments(SCHOOL, db)
    return rec


def test_put():
    print("出す")
    s1 = sid("lj2d01")
    got = SUB.put(SCHOOL, "atest01", s1, [{"kind": "png", "data": png()}, {"kind": "jpg", "data": jpg()}])
    check("2枚が台帳に入る", len(got["files"]) == 2 and got["seen"] == 0, got)
    check("ファイルが実在する", all(os.path.exists(paths.submit_file(SCHOOL, s1, f["name"])) for f in got["files"]))
    names1 = [f["name"] for f in got["files"]]
    try:
        SUB.put(SCHOOL, "atest01", s1, [{"kind": "gif", "data": b"x"}])
        check("gif は受け取らない", False)
    except ValueError:
        check("gif は受け取らない", True)
    try:
        SUB.put(SCHOOL, "atest01", s1, [{"kind": "png", "data": b"x" * (SUB.MAX_BYTES + 1)}])
        check("6MB を超える1枚は受け取らない", False)
    except ValueError:
        check("6MB を超える1枚は受け取らない", True)
    got = SUB.put(SCHOOL, "atest01", s1, [{"kind": "png", "data": png()}] * 11)
    check("11枚出しても 10枚まで（2026-10-08 の見本）", len(got["files"]) == SUB.MAX_FILES == 10)
    check("出し直すと前の写真は消える", not any(os.path.exists(paths.submit_file(SCHOOL, s1, n)) for n in names1[1:]))
    SUB.mark_seen(SCHOOL, "atest01", s1, sid("t-a"), "よく書けています")
    got = SUB.put(SCHOOL, "atest01", s1, [{"kind": "png", "data": png()}])
    check("出し直すと見た印とひとことは消える", got["seen"] == 0 and got["note"] == "", got)


def test_teacher():
    print("講師の取り込み・添削の返却")
    s1, s2, s3 = sid("lj2d01"), sid("lj2d02"), sid("lj2d03")
    ta = sid("t-a")
    got = SUB.put_by_teacher(SCHOOL, "atest01", s2, [{"kind": "jpg", "data": jpg()}], ta)
    check("取り込んだ紙は見た印つき・origin=teacher", got["seen"] > 0 and got["origin"] == "teacher" and got["by"] == ta, got)
    check("取り込んだ紙の名前", got["files"][0]["name"] == "atest01-1.jpg", got["files"])
    got = SUB.put_return(SCHOOL, "atest01", s1, [{"kind": "png", "data": png()}, {"kind": "png", "data": png()}], ta,
                         "赤の所を直そう")
    check("返した紙は returned に・r の名前", len(got["returned"]["files"]) == 2 and
          got["returned"]["files"][0]["name"] == "atest01-r1.png", got.get("returned"))
    check("ひとことも一緒に", got["note"] == "赤の所を直そう" and got["seen"] > 0)
    check("出した紙は残る", len(got["files"]) == 1)
    check("all_files は出した紙＋返した紙", len(SUB.all_files(got)) == 3)
    rn = [f["name"] for f in got["returned"]["files"]]
    got = SUB.put_return(SCHOOL, "atest01", s1, [{"kind": "pdf", "data": b"%PDF-1.4 x"}], ta)
    check("返し直すと前の紙は消える", not any(os.path.exists(paths.submit_file(SCHOOL, s1, n)) for n in rn)
          and got["returned"]["files"][0]["name"] == "atest01-r1.pdf")
    check("返し直してもひとことは残る", got["note"] == "赤の所を直そう")
    got = SUB.put(SCHOOL, "atest01", s1, [{"kind": "png", "data": png()}])
    check("生徒が出し直しても返した添削は残る", bool(got.get("returned")) and got["returned"]["files"][0]["name"] == "atest01-r1.pdf")
    got = SUB.put_return(SCHOOL, "atest01", s3, [{"kind": "png", "data": png()}], ta)
    check("出していない生徒にも返せる（空の提出）", got["files"] == [] and len(got["returned"]["files"]) == 1)
    check("of_student にも返した紙が見える", "atest01" in SUB.of_student(SCHOOL, s3))
    # 退塾
    SUB.drop_student(SCHOOL, s1)
    d = paths.submit_dir(SCHOOL, s1)
    check("退塾で出した紙も返した紙も消える", not os.path.isdir(d) or not os.listdir(d))
    check("台帳からも消える", s1 not in SUB.of_assignment(SCHOOL, "atest01"))


def test_prune():
    print("写真の保存期間")
    ta = sid("t-a")
    s2 = sid("lj2d02")
    SUB.put(SCHOOL, "atest01", s2, [{"kind": "png", "data": png()}])
    SUB.put_return(SCHOOL, "atest01", s2, [{"kind": "png", "data": png()}], ta, "古い分")
    names = [f["name"] for f in SUB.all_files(SUB.of_assignment(SCHOOL, "atest01")[s2])]
    r = SUB.prune(SCHOOL, days=180, dry=True)
    check("今日の分は消えない（数えるだけでも 0）", r == {"rows": 0, "files": 0}, r)
    r = SUB.prune(SCHOOL, days=180, dry=True, now=time.time() + 200 * 86400)
    check("200日後に数えると対象になる（消さない）", r["rows"] >= 1 and r["files"] >= 2 and
          all(os.path.exists(paths.submit_file(SCHOOL, s2, n)) for n in names), r)
    r = SUB.prune(SCHOOL, days=180, now=time.time() + 200 * 86400)
    got = SUB.of_assignment(SCHOOL, "atest01")[s2]
    check("消すと写真は無くなり、行は残る（pruned・ひとこと）", got["files"] == [] and got["pruned"] > 0 and got["note"] == "古い分"
          and got["returned"]["files"] == [] and not any(os.path.exists(paths.submit_file(SCHOOL, s2, n)) for n in names), got)
    import insight as INSIGHT
    items = [a for a in T.assignments(SCHOOL).values() if a["id"] == "atest01"]
    rows, st = INSIGHT.check_rows(items, [{"sid": s2, "label": "中2D-02"}], {}, SUB.load(SCHOOL), {})
    mine = [r for r in rows if r["sid"] == s2][0]
    # 未提出の1人は lj2d01（上で退塾の整理をして写真が無い）。s2 は写真が無くても「出した」のまま
    check("講師の一覧では「出した」のまま（未提出にならない）",
          st["submitted"] == 1 and st["missing"] == 1 and mine["pruned"] and mine["files"] == [], st)
    r = SUB.prune(SCHOOL, days=180, now=time.time() + 200 * 86400)
    check("二度目は何もしない", r == {"rows": 0, "files": 0}, r)


def test_graded_and_erase():
    """採点から1週間で答案の写真だけ消える（返した添削は残る）。返した添削は本人が消せる（2026-10-08）。"""
    print("採点から1週間・添削を消す")
    ta = sid("t-a")
    s3 = sid("lj2d03")
    SUB.put(SCHOOL, "atest01", s3, [{"kind": "png", "data": png()}])
    SUB.put_return(SCHOOL, "atest01", s3, [{"kind": "png", "data": png()}], ta, "よく書けています")
    SUB.mark_seen(SCHOOL, "atest01", s3, ta, "よく書けています")
    r = SUB.prune(SCHOOL, days=180, dry=True, graded_days=7)
    check("採点したばかりの分は数えない", r == {"rows": 0, "files": 0}, r)
    r = SUB.prune(SCHOOL, days=180, graded_days=7, now=time.time() + 8 * 86400)
    got = SUB.of_assignment(SCHOOL, "atest01")[s3]
    rnames = [f["name"] for f in got["returned"]["files"]]
    check("8日後：答案の写真だけ消え、返した添削とひとことは残る",
          r["rows"] == 1 and got["files"] == [] and got["pruned"] > 0 and len(rnames) == 1 and got["note"] == "よく書けています"
          and all(os.path.exists(paths.submit_file(SCHOOL, s3, n)) for n in rnames), got)
    n = SUB.erase_returned(SCHOOL, s3)
    got = SUB.of_assignment(SCHOOL, "atest01")[s3]
    check("本人が添削を消すと、返した写真だけ無くなる（評価・ひとことは残る）",
          n == 1 and got["returned"]["files"] == [] and got["returned"].get("erased") and got["note"] == "よく書けています"
          and not any(os.path.exists(paths.submit_file(SCHOOL, s3, x)) for x in rnames), got)
    check("二度目は 0 件", SUB.erase_returned(SCHOOL, s3) == 0)


def test_pdf():
    print("PDF")
    pdf = pdfout.build([("png", png()), ("jpg", jpg()), ("png", b"broken")])
    check("PNG と JPEG が 2ページの PDF に（壊れた画像は飛ばす）", pdf.startswith(b"%PDF-1.4") and pdfout.page_count(pdf) == 2,
          pdfout.page_count(pdf))
    check("A4（595x842）のページ", b"/MediaBox [0 0 595 842]" in pdf)
    try:
        pdfout.build([("png", b"broken")])
        check("1枚も無ければ ValueError", False)
    except ValueError:
        check("1枚も無ければ ValueError", True)


def test_quiz():
    print("提出箱")
    ta, tb = sid("t-a"), sid("t-b")
    plans = C.all_courses(SCHOOL)
    p = plans["j2d:japanese"]
    rec = T.make_quiz(SCHOOL, "j2d:japanese", p, "漢字テスト 第3回", int((time.time() + 5 * 86400) * 1000), ta)
    check("紙・採点・quiz の印", rec["route"] == "paper" and rec["graded"] is True and rec["quiz"] is True, rec)
    check("番号は 900（授業計画の回とぶつからない）", rec["lesson"]["n"] == T.QUIZ_N0 and rec["lesson"]["quiz"] is True, rec["lesson"])
    check("コースの生徒全員に", sorted(rec["students"]) == sorted([sid("lj2d01"), sid("lj2d02"), sid("lj2d03")]), rec["students"])
    rec2 = T.make_quiz(SCHOOL, "j2d:japanese", p, "計算テスト", int((time.time() + 5 * 86400) * 1000), ta)
    check("2つ目は 901", rec2["lesson"]["n"] == T.QUIZ_N0 + 1)
    check("空の題名は「小テスト」", T.make_quiz(SCHOOL, "j2d:japanese", p, "  ", 0, ta)["title"] == "小テスト")
    by = T.course_asgs(T.assignments(SCHOOL), "j2d:japanese")
    items = [a for a in by if (a.get("lesson") or {}).get("n") == T.QUIZ_N0]
    row = T._lesson_row(p, T.QUIZ_N0, items)
    check("回の行は「提出箱」＋題名", row.get("label") == "提出箱" and row.get("topic") == "漢字テスト 第3回" and row.get("quiz"), row)
    plan = {"lessons": [{"n": 1, "topic": "第1回 説明文"}]}
    check("授業計画の回はそのまま", T._lesson_row(plan, 1, items).get("topic") == "第1回 説明文")
    check("無い回は空", T._lesson_row(plan, 77, items) == {})
    # 種類と相手（2026-10-11 本人：追加の宿題・漢字テスト・計算テスト・作文・過去問を別々に）
    s1 = sid("lj2d01")
    rec3 = T.make_quiz(SCHOOL, "j2d:japanese", p, "第3回", int((time.time() + 5 * 86400) * 1000), ta, kind="漢字テスト", students=[s1])
    check("種類と相手：題は「漢字テスト 第3回」。選んだ 1 人だけ。印 picked",
          rec3["title"] == "漢字テスト 第3回" and rec3["students"] == [s1] and rec3.get("kind") == "漢字テスト" and rec3.get("picked") is True, rec3)
    items3 = [a for a in T.course_asgs(T.assignments(SCHOOL), "j2d:japanese") if (a.get("lesson") or {}).get("n") == rec3["lesson"]["n"]]
    row3 = T._lesson_row(p, rec3["lesson"]["n"], items3)
    check("回の行の名札は種類、題はその後ろ（「第3回」）。選んだ生徒だけの印",
          row3.get("label") == "漢字テスト" and row3.get("topic") == "第3回" and row3.get("kind") == "漢字テスト" and row3.get("picked") is True, row3)
    rec4 = T.make_quiz(SCHOOL, "j2d:japanese", p, "", 0, ta, kind="作文")
    check("題が空でも種類があれば、題は種類。全員に", rec4["title"] == "作文" and len(rec4["students"]) == 3 and not rec4.get("picked"), rec4["title"])
    try:
        T.make_quiz(SCHOOL, "j2d:japanese", p, "x", 0, ta, students=["nobody"]); bad = False
    except ValueError:
        bad = True
    check("コースにいない生徒だけを選ぶと作れない", bad)
    try:
        T.make_quiz(SCHOOL, "j2d:japanese", p, "x", 0, ta, kind="抜き打ち"); bad = False
    except ValueError:
        bad = True
    check("知らない種類は断る", bad)
    # 提出箱に出す → 講師の一覧（check_rows）に返した紙も出る
    import insight as INSIGHT
    s2 = sid("lj2d02")
    SUB.put(SCHOOL, rec["id"], s2, [{"kind": "png", "data": png()}])
    SUB.put_return(SCHOOL, rec["id"], s2, [{"kind": "png", "data": png()}], ta, "はねを丁寧に")
    subs = SUB.load(SCHOOL)
    st = INSIGHT.student_state(INSIGHT.student_bundle(items, s2), s2, {}, subs, {})
    check("生徒の状態に返した紙が出る", st["returned"] == [rec["id"] + "-r1.png"] and st["origin"] == "student" and st["note"] == "はねを丁寧に", st)
    st3 = INSIGHT.student_state(INSIGHT.student_bundle(items, sid("lj2d03")), sid("lj2d03"), {}, subs, {})
    check("出していない生徒は空", st3["files"] == [] and st3["returned"] == [], st3)
    # 担当外（t-b は j2r 担当）はサーバの口で弾く：may_touch で確かめる
    check("担当外の講師は触れない", not T.may_touch(SCHOOL, T.accounts(SCHOOL)["t-b"], rec, "japanese"))
    check("担当の講師は触れる", bool(T.may_touch(SCHOOL, T.accounts(SCHOOL)["t-a"], rec, "japanese")))


def test_score():
    print("過去問の点数（生徒の自己申告）")
    s1 = sid("lj2d01")
    SUB.put(SCHOOL, "atest01", s1, [{"kind": "png", "data": png()}])
    got = SUB.put_score(SCHOOL, "atest01", s1, 72, 100)
    check("点数と満点が出したものに残る", got and got.get("score") == 72 and got.get("max") == 100, got)
    check("読み直しても残る", SUB.of_student(SCHOOL, s1)["atest01"].get("score") == 72)
    got = SUB.put_score(SCHOOL, "atest01", s1, 80, None)
    check("満点なしなら max は消える", got.get("score") == 80 and "max" not in got, got)
    got = SUB.put_score(SCHOOL, "atest01", s1, None)
    check("空で点数が消える", "score" not in got and "max" not in got, got)
    check("出していない宿題には付かない", SUB.put_score(SCHOOL, "atest-none", s1, 50) is None)


def test_race():
    """同時に届いた 2 本の書き込みが、互いを消さない（10-26 #13：評価の PUT が、同時に届いたひとことを消した）。
    台帳の書き戻しを遅らせて、2 本を必ず重ねる。"""
    print("同時の書き込み")
    import threading
    s1, s3 = sid("lj2d01"), sid("lj2d03")
    got = SUB.mark_seen(SCHOOL, "atest01", s1, sid("t-a"), "字がていねいです")
    got = SUB.mark_seen(SCHOOL, "atest01", s1, sid("t-a"), None)
    check("ひとことを渡さない「見た」は、ひとことに触らない", got["note"] == "字がていねいです", got)
    real = SUB.save

    def slow(school, db):
        time.sleep(0.2)
        real(school, db)
    SUB.save = slow
    try:
        a = threading.Thread(target=SUB.mark_seen, args=(SCHOOL, "atest01", s1, sid("t-a"), "図がわかりやすい"))
        b = threading.Thread(target=SUB.mark_seen, args=(SCHOOL, "atest01", s1, sid("t-a"), None))
        a.start(); time.sleep(0.05); b.start(); a.join(); b.join()
        check("ひとこと → 評価だけ が重なっても、ひとことが残る",
              SUB.of_assignment(SCHOOL, "atest01")[s1]["note"] == "図がわかりやすい", SUB.of_assignment(SCHOOL, "atest01")[s1])
        a = threading.Thread(target=SUB.put, args=(SCHOOL, "atest-race", s1, [{"kind": "png", "data": png()}]))
        b = threading.Thread(target=SUB.put, args=(SCHOOL, "atest-race", s3, [{"kind": "png", "data": png()}]))
        a.start(); time.sleep(0.05); b.start(); a.join(); b.join()
        check("2 人が同時に出しても、2 人とも残る", set(SUB.of_assignment(SCHOOL, "atest-race")) >= {s1, s3},
              sorted(SUB.of_assignment(SCHOOL, "atest-race")))
    finally:
        SUB.save = real


def main():
    setup()
    test_put()
    test_teacher()
    test_prune()
    test_graded_and_erase()
    test_pdf()
    test_quiz()
    test_score()
    test_race()
    print()
    if ng_n:
        print("test_submissions: %d件 だめ" % ng_n)
        sys.exit(1)
    print("test_submissions: すべて通った。（%d件）" % ok_n)


if __name__ == "__main__":
    main()
