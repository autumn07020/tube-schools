#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""こわれ方の検査 ―― 実データで起きることを、実際に起こして確かめる。

    python3 app/tools/こわれ方の検査.py

規模の監査（規模の監査.py）が「量」を見るのに対し、こちらは「形」を見る。

  1. 欠けているデータ   まっさらな校舎・空の学年・0人のクラス・日程なし
  2. 教材の差し替え     項目IDの作り方が画面とサーバで一致しているか
  3. 同時に書く         2人が同時に採点したら、片方が消えないか
  4. 5週の周期          回の境目・テストの延期・当日・過去だけ
  5. 権限と分離         他人の記録・担当外のクラス・退塾者

**落ちないこと**だけでなく、**黙って嘘を返さないこと**まで見る。
例外で止まるのは気づける。空を返すのは気づけない。

使い捨ての校舎で測り、終わったら消す。london には触れない。
"""

import io
import json
import os
import shutil
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TMP = os.path.join("/tmp", "tube-brk-%d" % os.getpid())
os.environ["MYACADY_ROOT"] = TMP
sys.path.insert(0, os.path.join(ROOT, "server"))

import paths                                    # noqa: E402
import tube_server as T                         # noqa: E402
import examprep                                 # noqa: E402
import lessons as L                             # noqa: E402
import exams as E                               # noqa: E402
import weak as W                                # noqa: E402
import prepsheet                                # noqa: E402

OK = 0
NG = []


def check(name, cond, detail=""):
    global OK
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        NG.append((name, detail))
        print("  ×    %s   %s" % (name, detail))


def safe(name, fn, *a, **kw):
    """落ちないことを確かめ、返り値も渡す。"""
    try:
        out = fn(*a, **kw)
        check(name, True)
        return out
    except Exception as e:                       # noqa: BLE001
        check(name, False, "%s: %s" % (type(e).__name__, e))
        return None


# ==================================================================
def s1_empty():
    """1. 欠けているデータ。**新しい校舎はここから始まる。**"""
    print("\n1. 欠けているデータ ―― まっさらな校舎")
    sch = "blank"
    os.makedirs(paths.school_dir(sch), exist_ok=True)
    paths.save(paths.school_file(sch, "school.json"), {"name": "空", "code": "b"})

    safe("名簿を読む", T.accounts, sch)
    safe("要約を読む", T.summary, sch)
    safe("宿題を読む", T.assignments, sch)
    safe("授業計画を読む", L.load, sch)
    safe("日程を読む", E.all_exams, sch)

    got = safe("対策の窓（日程なし）", E.window, sch)
    check("日程が無ければ対策を出さない", got is None, repr(got))

    got = safe("毎日テスト（授業なし）", T.daily_sets, sch, "none", "math", None)
    check("授業が無くても落ちない", got is not None, repr(got))

    got = safe("その学年の教材（無い学年）", examprep.pack_items, "math", "zz")
    check("無い学年は空で返る", got == [], "%d件" % len(got or []))

    got = safe("対策を組む（記録なし）", examprep.build, sch, "zz", "math",
               "advanced", [], "2026-08-22", units=[], materials={}, hard=None)
    check("組めなければ None", got is None, repr(got)[:40])

    # 0人のクラス・進捗のない生徒
    db = {"t1": {"sid": "T1", "role": "teacher", "level": "e4",
                 "classId": "c0", "classes": [], "assign": [["c0", "math", 1, 1]],
                 "alg": "scram-sha256", "salt": "0" * 32, "iters": 600000, "storedKey": "0" * 64, "serverKey": "0" * 64},
          "s1": {"sid": "S1", "role": "student", "level": "e4",
                 "classId": "c0", "classes": [], "seat": "01",
                 "alg": "scram-sha256", "salt": "0" * 32, "iters": 600000, "storedKey": "0" * 64, "serverKey": "0" * 64}}
    paths.save(paths.school_file(sch, "accounts.json"), db)
    paths.save(paths.school_file(sch, "roster.json"),
               {"classes": {"c0": {"grade": "e4", "name": "小4"},
                            "c1": {"grade": "e4", "name": "空クラス"}}})
    now = time.time() * 1000
    a = {"id": "a1", "title": "宿題", "source": "keisan", "from": 0, "to": 0,
         "classId": "c1", "students": [], "dueAt": int(now - 86400000),
         "kind": "hw", "route": "app", "lesson": {"key": "e4:math", "n": 1}}
    paths.save(paths.school_file(sch, "assignments.json"), {"a1": a})

    got = safe("0人クラスの宿題を集計", T.hw_summary, sch, a)
    check("0人でも 0除算しない", (got or {}).get("assigned") == 0, repr(got)[:60])

    got = safe("進捗が無い生徒の苦手", T.weak_for_student, sch, "S1", "math", 8)
    check("進捗が無くても空で返る", got == [], repr(got)[:40])

    got = safe("要約の書き直し（進捗なし）", T.update_summary, sch, "S1", {}, [])
    got = safe("1人だけのクラスの順位", T.summary, sch)

    # 期限のない宿題・番号のない宿題
    a2 = dict(a, id="a2", dueAt=0, classId="c0")
    paths.save(paths.school_file(sch, "assignments.json"), {"a1": a, "a2": a2})
    got = safe("期限のない宿題を集計", T.hw_summary, sch, a2)
    return sch


def s2_slug():
    """2. 教材の差し替え。**IDの作り方が食い違うと、全部が静かに0件になる。**"""
    print("\n2. 教材の差し替え ―― IDの作り方")

    # 画面側（app/js/content.js の slug）と同じ規則で作れているか。
    # 実際に content.js から規則を取り出して突き合わせる。
    js = io.open(os.path.join(ROOT, "app/js/content.js"), encoding="utf-8").read()
    has = "replace(/[^a-z0-9" in js
    check("画面側に slug の規則がある", has)

    samples = ["afford", "Hello World", "「疫病」の読みは？", "2x + 3y = 13",
               "a-b_c", "ＡＢＣ", "  空白  ", "  ", "＠＠", "！？",
               "(−2)²", "(−2)³", "同じ", "同じ"]
    py = [examprep._slug(x) for x in samples]
    check("空文字にならない", all(py), repr([p for p in py if not p]))
    check("同じ入力は同じID", py[-1] == py[-2])
    check("記号だけ違う式は別のID", py[10] != py[11], "%s / %s" % (py[10], py[11]))

    # **画面側と一文字までそろっているか。**
    # ここが食い違うと、サーバの言う項目IDと画面の項目IDが別物になり、
    # 「にがて」も「対策」も静かに0件になる。JavaScript を実際に走らせて比べる。
    js_fn = ("function slug(s){var t=String(s).normalize('NFKC').toLowerCase();"
             "var out=t.replace(/[^a-z0-9\u3040-\u30ff\u4e00-\u9fff]+/g,'-')"
             ".replace(/^-|-$/g,'');"
             "if(out) return out;var h=0;"
             "for(var i=0;i<t.length;i++){h=((h<<5)-h+t.charCodeAt(i))|0;}"
             "return 'x'+(h>>>0).toString(16);}")
    src = io.open(os.path.join(ROOT, "app/js/content.js"), encoding="utf-8").read()
    check("画面側の slug が NFKC でそろえている", "normalize('NFKC')" in src)
    check("画面側に指紋の逃げ道がある", "toString(16)" in src)

    import subprocess
    expr = js_fn + "JSON.stringify(%s.map(slug))" % json.dumps(
        samples, ensure_ascii=False)
    try:
        got = subprocess.run(["osascript", "-l", "JavaScript", "-e", expr],
                             capture_output=True, text=True, timeout=30)
        jsout = json.loads(got.stdout.strip() or "[]")
        check("画面とサーバでIDが一致する", jsout == py,
              "js=%s py=%s" % (jsout[:3], py[:3]))
    except Exception as e:                       # noqa: BLE001
        check("画面とサーバでIDが一致する", False, "確かめられない: %s" % e)

    # 実教材で、IDがぶつかっていないか（全教科・全学年）
    dup = {}
    for sub in ("japanese", "math", "science", "social"):
        for g in ("e4", "e5", "e6", "j1", "j2", "j3"):
            ids = [x["id"] for x in examprep.pack_items(sub, g)]
            seen = {}
            for i in ids:
                seen[i] = seen.get(i, 0) + 1
            bad = {k: v for k, v in seen.items() if v > 1}
            if bad:
                dup["%s/%s" % (sub, g)] = len(bad)
    check("実教材でIDがぶつからない", not dup, repr(dup)[:120])

    # 単元名が入っているか（5週の反復はここに乗っている）
    noun = {}
    for sub in ("japanese", "math", "science", "social"):
        for g in ("e4", "e5", "e6", "j1", "j2", "j3"):
            items = examprep.pack_items(sub, g)
            q = [x for x in items if x["t"] == "quiz"]
            if q and not any(x.get("unit") for x in q):
                noun["%s/%s" % (sub, g)] = len(q)
    check("選択問題に単元名が付いている", not noun, repr(noun)[:140])

    # 単元で絞れるか（絞れなければ5週の反復が効かない）
    items = examprep.pack_items("math", "j2")
    units = sorted({x.get("unit") for x in items if x.get("unit")})
    got = examprep.in_scope(items, units[:1]) if units else []
    check("単元で絞れる", 0 < len(got) < len(items),
          "%d / %d（単元 %s）" % (len(got), len(items), units[:1]))
    got2 = examprep.in_scope(items, ["ありえない単元"])
    check("知らない単元では絞らない（0件にしない）", len(got2) == len(items),
          "%d件" % len(got2))


def s3_race(sch):
    """3. 同時に書く。**片方が消えたら、講師は気づけない。**"""
    print("\n3. 同時に書く ―― 2人が同時に採点する")

    aid = "a1"
    sids = ["S%03d" % i for i in range(40)]

    def rate(sid):
        with T.LOCK:
            db = T.ratings(sch)
            db.setdefault(aid, {})[sid] = {"v": 3, "at": int(time.time())}
            T.save_ratings(sch, db)

    ts = [threading.Thread(target=rate, args=(s,)) for s in sids]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    got = T.ratings(sch).get(aid) or {}
    check("40人ぶんの評価が全部残る（LOCKあり）", len(got) == 40, "%d件" % len(got))

    # LOCK を使わない書き方だとどうなるかも見ておく（比較のため）
    T.save_ratings(sch, {})

    def rate_nolock(sid):
        db = T.ratings(sch)
        db.setdefault(aid, {})[sid] = {"v": 3, "at": int(time.time())}
        T.save_ratings(sch, db)

    ts = [threading.Thread(target=rate_nolock, args=(s,)) for s in sids]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    lost = 40 - len(T.ratings(sch).get(aid) or {})
    print("       （参考）LOCKなしだと %d件 消える" % lost)

    # 書き込みの途中で落ちてもファイルが壊れないか
    p = paths.school_file(sch, "ratings.json")
    T.save_ratings(sch, {"x": {"y": {"v": 1}}})
    raw = io.open(p, encoding="utf-8").read()
    ok = True
    try:
        json.loads(raw)
    except ValueError:
        ok = False
    check("保存したファイルが読み直せる", ok)
    check("一時ファイルが残らない", not os.path.exists(p + ".tmp"))


def s4_cycle():
    """4. 5週の周期。**単元確認テストの日程がこの塾の背骨。**"""
    print("\n4. 5週の周期と日程")

    check("第0回は総復習でない", not L.is_review(0))
    check("第5回が総復習", L.is_review(5))
    check("第10回が総復習", L.is_review(10))
    check("第4回は総復習でない", not L.is_review(4))
    check("第1回の周期は1", L.cycle_of(1) == 1)
    check("第5回の周期は1", L.cycle_of(5) == 1)
    check("第6回の周期は2", L.cycle_of(6) == 2, str(L.cycle_of(6)))
    check("周期1の範囲は1〜5", L.block_of(3) == (1, 5), str(L.block_of(3)))

    sch = "cyc"
    os.makedirs(paths.school_dir(sch), exist_ok=True)
    paths.save(paths.school_file(sch, "school.json"), {"name": "周期", "code": "c"})

    day = 86400
    now = time.time()

    def ymd(t):
        return time.strftime("%Y-%m-%d", time.localtime(t))

    # 未来だけ
    paths.save(paths.school_file(sch, "exams.json"),
               {"exams": [{"date": ymd(now + 20 * day), "name": "組み分け"}],
                "prepDays": 14})
    check("20日後なら まだ対策を出さない", E.window(sch, now) is None)

    paths.save(paths.school_file(sch, "exams.json"),
               {"exams": [{"date": ymd(now + 5 * day), "name": "組み分け"}],
                "prepDays": 14})
    w = E.window(sch, now)
    check("5日後なら対策が出る", w is not None)
    check("残り日数が5", (w or {}).get("left") == 5, str((w or {}).get("left")))

    # 当日
    paths.save(paths.school_file(sch, "exams.json"),
               {"exams": [{"date": ymd(now), "name": "組み分け"}], "prepDays": 14})
    w = E.window(sch, now)
    check("当日は「あと0日」で出る", (w or {}).get("left") == 0,
          str((w or {}).get("left")))

    # 過去だけ
    paths.save(paths.school_file(sch, "exams.json"),
               {"exams": [{"date": ymd(now - 5 * day), "name": "組み分け"}],
                "prepDays": 14})
    check("過去だけなら出さない", E.window(sch, now) is None)

    # 同じ日に2つ・壊れた日付が混ざる
    paths.save(paths.school_file(sch, "exams.json"),
               {"exams": [{"date": "2026-13-45", "name": "壊れ"},
                          {"date": ymd(now + 3 * day), "name": "A"},
                          {"date": ymd(now + 3 * day), "name": "B"}],
                "prepDays": 14})
    got = safe("壊れた日付が混ざっても読める", E.all_exams, sch)
    check("壊れた日付は落とす", len(got or []) == 2, "%d件" % len(got or []))
    w = E.window(sch, now)
    check("同じ日が2つでも出る", (w or {}).get("left") == 3, str(w and w.get("left")))

    # 深夜（23:59に見たときと 00:01に見たときで1日ずれないか）
    paths.save(paths.school_file(sch, "exams.json"),
               {"exams": [{"date": ymd(now + 3 * day), "name": "A"}],
                "prepDays": 14})
    late = time.mktime(time.strptime(ymd(now) + " 23:59", "%Y-%m-%d %H:%M"))
    early = time.mktime(time.strptime(ymd(now) + " 00:01", "%Y-%m-%d %H:%M"))
    check("同じ日なら夜でも朝でも残り日数が同じ",
          E.window(sch, late)["left"] == E.window(sch, early)["left"],
          "%s vs %s" % (E.window(sch, late)["left"], E.window(sch, early)["left"]))


def s5_perm(sch):
    """5. 権限と分離。**ここだけは、通ってはいけないことを確かめる。**"""
    print("\n5. 権限と分離")

    teach = {"sid": "T1", "role": "teacher", "school": sch,
             "assign": [["c0", "math", 1, 1]], "classes": []}
    check("担当クラス・担当教科は見える", T.can_see(teach, "c0", "math"))
    check("担当クラス・別教科は見えない", not T.can_see(teach, "c0", "english"))
    check("担当外のクラスは見えない", not T.can_see(teach, "c1", "math"))
    check("担当外は教科を問わず見えない", not T.can_see(teach, "c1", None))

    # パスの検査
    for bad in ("../etc/passwd", "..", "a/b", "", "S1/../../x", "S1\x00"):
        try:
            paths.progress_path(sch, bad)
            check("進捗パスが抜けない: %r" % bad, False, "通ってしまった")
        except Exception:                        # noqa: BLE001
            check("進捗パスが抜けない: %r" % bad, True)

    for bad in ("../x.json", "a.exe", "x.jpg.php", "..%2Fx.png"):
        try:
            paths.submit_file(sch, "S1", bad)
            check("答案パスが抜けない: %r" % bad, False, "通ってしまった")
        except Exception:                        # noqa: BLE001
            check("答案パスが抜けない: %r" % bad, True)

    for bad in ("../../etc/hosts", "secrets.json", "accounts.json.bak"):
        try:
            paths.school_file(sch, bad)
            check("校舎ファイル名が抜けない: %r" % bad, False, "通ってしまった")
        except Exception:                        # noqa: BLE001
            check("校舎ファイル名が抜けない: %r" % bad, True)

    # 苦手の記録は、生徒ごとに分かれているか
    W.record(sch, "S1", "math", [{"unit": "分数", "right": False, "blank": False},
                                 {"unit": "分数", "right": False, "blank": False}])
    check("本人の苦手は出る", len(W.weak_units(sch, "S1", "math")) == 1)
    check("他人の苦手は出ない", W.weak_units(sch, "S2", "math") == [])
    check("塗り忘れは苦手に数えない",
          (W.record(sch, "S3", "math",
                    [{"unit": "比", "right": False, "blank": True}])
           .get("score") or {}).get("n") == 0)


# ==================================================================
def s6_sheet():
    """6. 刷った紙と、読む紙。**紙が先。読むときに組み直さない。**

    パソコンで刷って、スマホで撮る。そのあいだに世の中は動く ――
    日付が変わる、本人がアプリで1問答える、同級生が答えて校舎全体の
    難しさが動く。examprep.build の並びはそのどれでも変わるので、
    撮るときに組み直すと紙とかみ合わない。

    かみ合わないと、点数が狂うだけでは済まない。読み取り結果は
    問題IDごとに送られるので、**見てもいない単元に「まちがえた」が
    積もる**。苦手の蓄積そのものが汚れる ―― デモでは絶対に出ない。
    """
    print("\n6. 刷った紙と、読む紙")
    sch = "sheetbrk"
    os.makedirs(paths.school_dir(sch), exist_ok=True)
    paths.save(paths.school_file(sch, "school.json"), {"name": "紙", "code": "p"})

    def mk(day, wrong, tier="advanced"):
        return examprep.build(sch, "j3", "math", tier, wrong, day,
                              units=[], materials={}, hard=None)

    # ---- 刷る ----
    g1 = mk("2026-08-25", [])
    printed = [i["id"] for i in prepsheet.paper_items([g1])]
    check("紙に問題が載る", len(printed) > 10, "%d問" % len(printed))
    T.remember_sheet(sch, "S1", "math", "advanced", printed)

    # ---- 撮る（翌日・本人が1問まちがえた あと）----
    g2 = mk("2026-08-26", [printed[3]])
    got = {"sets": [g2], "minutes": g2["minutes"]}
    fresh = [i["id"] for i in prepsheet.paper_items([g2])]

    # まず、**組み直すと本当にずれること**を見せる。
    # ずれないなら、この検査そのものに意味がない。
    same = sum(1 for a, b in zip(printed, fresh) if a == b)
    check("組み直すと並びがずれる（＝直す価値がある）",
          fresh != printed, "%d/%d問しか合わない" % (same, len(printed)))

    paper = T.apply_sheet_memo(sch, "S1", "j3", got, {"math": fresh})
    check("刷った並びで採点する", paper["math"] == printed,
          "%d/%d問" % (sum(1 for a, b in zip(paper["math"], printed)
                           if a == b), len(printed)))

    # 画面側は set.items から id を引く。引けない問題があると
    # そこだけ落ちて、以降がぜんぶ1つずつずれる。
    have = {x["id"] for x in got["sets"][0]["items"]}
    lost = [i for i in printed if i not in have]
    check("紙の問題がぜんぶ引ける", not lost, "%d問 引けない" % len(lost))
    check("問数と時間が合っている",
          got["sets"][0]["n"] == len(got["sets"][0]["items"]))

    # ---- 教材が入れ替わったら、あきらめる ----
    T.remember_sheet(sch, "S2", "math", "advanced", printed + ["mat:q:もう無い"])
    g3 = mk("2026-08-26", [])
    keep = [i["id"] for i in prepsheet.paper_items([g3])]
    paper = T.apply_sheet_memo(sch, "S2", "j3", {"sets": [g3]}, {"math": keep})
    check("見つからない問題があれば手を出さない", paper["math"] == keep)

    # ---- 6時間より前の紙は「今のではない」----
    T.remember_sheet(sch, "S3", "math", "advanced", printed)
    with T.LOCK:
        db = paths.load(T.sheet_memo_path(sch), {})
        db["S3"]["at"] = int(time.time()) - T.SHEET_TTL - 60
        paths.save(T.sheet_memo_path(sch), db)
    paper = T.apply_sheet_memo(sch, "S3", "j3", {"sets": [g3]}, {"math": keep})
    check("古い紙は使わない", paper["math"] == keep)

    # ---- 一度も刷っていない生徒 ----
    paper = T.apply_sheet_memo(sch, "S9", "j3", {"sets": [g3]}, {"math": keep})
    check("刷っていなければ今の組み立て", paper["math"] == keep)

    # ---- 別の教科を撮ろうとした ----
    T.remember_sheet(sch, "S4", "science", "advanced", ["sci:q:x"])
    paper = T.apply_sheet_memo(sch, "S4", "j3", {"sets": [g3]}, {"math": keep})
    check("刷った教科とちがえば触らない", paper["math"] == keep)


# ==================================================================
def s7_summary():
    """7. 要約の置き場。**1ファイルから、生徒ごとへ。**

    もとは summary.json 1つに全員ぶんを入れていた。生徒が1問答えるたび
    全員ぶんを読んで書き直していたので、2,000名では同期1回が36ms、
    40人が同時なら LOCK が1.4秒ふさがった。

    分けたぶん、新しい壊れ方が2つ生まれる ――
      ・古い置き場からの引っ越しに失敗して、講師画面が空になる
      ・控えが古いままで、書いたはずの数字が講師に見えない
    どちらも「落ちない」ので、起こして確かめる。
    """
    print("\n7. 要約の置き場")
    sch = "summbrk"
    os.makedirs(paths.school_dir(sch), exist_ok=True)
    paths.save(paths.school_file(sch, "school.json"), {"name": "要", "code": "y"})

    # ---- 引っ越し前の校舎（summary.json しかない）----
    old = {"S1": {"n": 10, "ok": 8}, "S2": {"n": 5, "ok": 5},
           "../わるいID": {"n": 1}}
    paths.save(paths.school_file(sch, "summary.json"), old)
    T._SUMM.pop(sch, None)
    got = safe("古い置き場から読む", T.summary, sch)
    check("引っ越しても中身が残る", (got or {}).get("S1", {}).get("ok") == 8,
          repr(got)[:60])
    check("あぶないIDは持ち込まない", "../わるいID" not in (got or {}))
    check("生徒ごとのファイルになった",
          os.path.isdir(paths.summary_dir(sch)))
    check("途中の置き場が残らない",
          not os.path.exists(paths.summary_dir(sch) + ".new"))

    # ---- 二度目の起動で、やり直さない ----
    paths.save(paths.summary_path(sch, "S1"), {"n": 99, "ok": 99})
    T._SUMM.pop(sch, None)
    got = T.summary(sch)
    check("引っ越しは一度きり", (got or {}).get("S1", {}).get("ok") == 99,
          repr((got or {}).get("S1")))

    # ---- 書いたものが、すぐ講師に見える ----
    # ここが効かないと「同期したのに講師画面が古い」になる。
    # 控えの作り直しは日付と大きさで決めるので、**同じ秒に書いても**
    # 気づけることを確かめる。
    for k in range(3):
        paths.save(paths.summary_path(sch, "S1"), {"n": k, "ok": k, "pad": "x" * k})
        got = T.summary(sch)
        if (got or {}).get("S1", {}).get("ok") != k:
            break
    check("書いたらすぐ見える", (got or {}).get("S1", {}).get("ok") == k,
          repr((got or {}).get("S1")))

    # ---- 消したら、消えて見える ----
    T.drop_summary(sch, "S2")
    got = T.summary(sch)
    check("消したら一覧から消える", "S2" not in (got or {}), repr(sorted(got or {})))
    safe("いない生徒を消しても落ちない", T.drop_summary, sch, "S404")
    safe("あぶないIDを消しても落ちない", T.drop_summary, sch, "../etc")

    # ---- 1人ぶんの書き込みが、他人を巻き込まない ----
    paths.save(paths.summary_path(sch, "S3"), {"n": 1, "ok": 1})
    T.update_summary(sch, "S1", {"cards": {}, "hw": {}, "hist": {}}, [])
    got = T.summary(sch)
    check("他人の要約を消さない", (got or {}).get("S3", {}).get("ok") == 1,
          repr(sorted(got or {})))

    # ---- まっさらな校舎でも読める ----
    os.makedirs(paths.school_dir("summ2"), exist_ok=True)
    paths.save(paths.school_file("summ2", "school.json"), {"name": "空", "code": "z"})
    got = safe("要約が一度も無い校舎", T.summary, "summ2")
    check("空で返る（落ちない）", got == {}, repr(got)[:40])


# ==================================================================
def s8_dose():
    """8. 1日の量。**学年で変える。5週の周期に乗せる。**

    ここが狂うと、落ちも間違いも起きないまま、生徒が続かなくなる。
    前は全学年ほぼ同じ量で、上限まで出ると小4で149分、中3で222分。
    間隔の上限も前身プロジェクト（IELTS の単語帳）のまま400日で、
    「むずかしい 3.8ヶ月」「わかった 5ヶ月」と出ていた ――
    どちらも単元確認テストを何回も飛び越える。

    量と間隔の表は画面（app/js/）とサーバ（server/）の両方にある。
    オフラインでも量が決まる必要があるため。**食い違わせない。**
    """
    print("\n8. 1日の量と、間隔の上限")
    import subprocess

    # ---- 間隔の上限が、単元確認テストの周期に収まっているか ----
    src = io.open(os.path.join(ROOT, "app/js/srs.js"), encoding="utf-8").read()
    core = src[src.index("var DAY"):src.index("function dayKey(")]
    js = (core + "function bumpXp(){} function dayKey(){return 'x';}\n"
          "var q={cards:{},hist:{}};"
          "for(var i=0;i<12;i++) grade(q,'a',3);"
          "var r={hard:nextIv(q,'a',2), good:nextIv(q,'a',3), easy:nextIv(q,'a',4),"
          " iv:q.cards['a'].iv, cycle:CYCLE_DAYS,"
          " max:[MAX_IV[2],MAX_IV[3],MAX_IV[4]]};"
          "var old={x:{iv:400,ef:2.5,due:Date.now()+400*864e5,reps:9,lapse:0,seen:0}};"
          "r.moved=fitToCycle(old);"
          "r.after=Math.round((old.x.due-Date.now())/864e5);"
          "JSON.stringify(r)")
    r = json.loads(subprocess.run(["osascript", "-l", "JavaScript", "-e", js],
                                  capture_output=True, text=True,
                                  timeout=60).stdout.strip() or "{}")
    check("間隔が周期（5週）を超えない", r.get("iv", 999) <= 35, repr(r.get("iv")))
    check("周期の日数が lessons.CYCLE と合う", r.get("cycle") == L.CYCLE * 7,
          "js=%s py=%s週" % (r.get("cycle"), L.CYCLE))
    # 上限で3つのボタンが同じ数字にならないこと。
    # 同じになると「むずかしい」と「わかった」を選ぶ意味が消える。
    labels = [r.get("hard"), r.get("good"), r.get("easy")]
    check("3つのボタンが押し分けられる", len(set(labels)) == 3, " / ".join(map(str, labels)))
    check("月や年で出さない",
          not any("ヶ月" in str(x) or "年" in str(x) for x in labels),
          " / ".join(map(str, labels)))
    check("古い札を周期の中に連れ戻す",
          r.get("moved") == 1 and 0 < (r.get("after") or 999) <= 35,
          "%s日後" % r.get("after"))

    # ---- 量の表が、画面とサーバで一致しているか ----
    cfg = io.open(os.path.join(ROOT, "app/js/config.js"), encoding="utf-8").read()
    js2 = (cfg[cfg.index("var DAILY_MIN ="):cfg.index("function secOf(")] +
           "JSON.stringify({min:DAILY_MIN, share:NEW_SHARE,"
           " sec:SEC_PER, sub:SUBJECT_SEC, def:DEFAULT_SEC})")
    g = json.loads(subprocess.run(["osascript", "-l", "JavaScript", "-e", js2],
                                  capture_output=True, text=True,
                                  timeout=60).stdout.strip() or "{}")
    check("1日の分数が画面とサーバで同じ", g.get("min") == examprep.DAILY_MIN,
          "js=%s py=%s" % (g.get("min"), examprep.DAILY_MIN))
    check("新出の割合が同じ", abs((g.get("share") or 0) - examprep.NEW_SHARE) < 1e-9)
    # 画面が持つのは **アプリで解く時間**（1日の量を決めるのに使う）。
    # 紙で解く時間（SUBJECT_SEC）はサーバ側だけが使う。混同しないこと。
    check("1問の秒数が同じ（アプリ）",
          g.get("sec") == examprep.SEC_PER and g.get("sub") == examprep.APP_SEC,
          "js=%s py=%s" % (g.get("sub"), examprep.APP_SEC))
    check("紙の時間は アプリより長い",
          all(examprep.SUBJECT_SEC[k]["quiz"] >= examprep.APP_SEC.get(k, {}).get(
              "quiz", examprep.SEC_PER["quiz"]) for k in examprep.SUBJECT_SEC),
          repr(examprep.SUBJECT_SEC))

    # ---- 学年で増えているか。上限を超えていないか ----
    mins = examprep.DAILY_MIN
    order = ["e4", "e5", "e6", "j1", "j2", "j3"]
    ups = all(mins[a] < mins[b] for a, b in zip(order, order[1:]))
    check("学年が上がるほど増える", ups, repr(mins))
    check("小学生は45分まで", max(mins[g2] for g2 in ("e4", "e5", "e6")) <= 45)
    check("中3は60分", mins["j3"] == 60)

    # ---- 教科を増やしても1日の合計は増えない ----
    # ここが効かないと、講師が理科を「使う」にした日に、
    # 生徒の1日が黙って長くなる。
    for n in (2, 5, 8):
        tot = sum(examprep.daily_sec("j3", n)) * n / 60.0
        check("教科%d科でも合計%d分のまま" % (n, mins["j3"]),
              abs(tot - mins["j3"]) < 0.01, "%.1f分" % tot)


# ==================================================================
def s9_csv():
    """9. 教材の入れ替え。**出して、直して、入れる。**

    いま入っている教材は仮のもので、本物が入ったら丸ごと入れ替える。
    そのとき「Python の生成スクリプトを教科ごとに書き直す」のでは、
    入れ替えのたびに人手が要る。だから口を1つ（CSV）にしてある。

    ここで見るのは **出した形と入れる形が同じかどうか** だけ。
    ここがずれると、出したものをそのまま戻せない ――
    毎回 手で列をそろえることになり、「入れ替えやすい」が嘘になる。
    """
    print("\n9. 教材の入れ替え ―― CSV の往復")
    import importlib.util

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    tools = os.path.join(ROOT, "app", "tools")
    out = load("dasu", os.path.join(tools, "教材を出す.py"))
    inn = load("ireru", os.path.join(tools, "教材を入れる.py"))

    # 出す側の列が、入れる側で読めるか。**ここが一番ずれる。**
    unread = [h for h in out.HEAD
              if not any(h in names for names in inn.COL.values())]
    check("出した列を ぜんぶ読める", not unread, "読めない列: %s" % unread)

    # 実教材で往復してみる。図つき・単元つきのものを選ぶ。
    path = os.path.join(ROOT, "app", "content", "science", "zu-e4.js")
    rows = out.rows_of(path)
    check("出せる", len(rows) > 5, "%d行" % len(rows))

    back = []
    for r in rows:
        d = dict(zip(out.HEAD, r))
        kind = inn.pick(d, "kind")
        dis = [x for x in inn.pick(d, "dis").split("|") if x]
        k = "T" if kind in inn.TERM else ("Q" if kind in inn.QUIZ
                                          else ("Q" if dis else "T"))
        back.append((k, inn.pick(d, "q"), inn.pick(d, "a"), tuple(dis),
                     inn.pick(d, "unit"), inn.pick(d, "fig"),
                     inn.pick(d, "band")))

    src = [("Q", x["q"], x["ans"], tuple(x["dis"]), x["unit"], x["fig"], x["band"])
           for x in examprep.pack_items("science", "e4") if x["pack"] == "zu-e4"]
    check("往復しても同じ", sorted(back) == sorted(src),
          "出%d 戻%d / 最初のちがい %s"
          % (len(src), len(back),
             next((a for a, b in zip(sorted(back), sorted(src)) if a != b),
                  "なし")))
    check("図の名前が残る", all(x[5] for x in back), "図の無い行がある")
    check("単元が残る", all(x[4] for x in back), "単元の無い行がある")

    # 既定の進度を、サーバ側が正しく読めているか。
    #
    # 進度の既定は app/curriculum.js（JavaScript）にしか無い。
    # サーバは Linux で動くので JavaScript を走らせられず、
    # 正規表現で必要な欄だけ取り出している。**読みちがえると、
    # デモや架空データの学年×教科が丸ごとずれる。**
    # ここでは実際に JavaScript を走らせて突き合わせる。
    import subprocess
    sys.path.insert(0, os.path.join(ROOT, "server"))
    import demo_seed                                   # noqa: E402
    py = demo_seed.default_plans()
    check("既定の進度を読めている", len(py) > 20, "%d件" % len(py))

    cur = io.open(os.path.join(ROOT, "app", "curriculum.js"),
                  encoding="utf-8").read()
    expr = ("var window={};" + cur +
            "var p=window.TubeCurriculum.plans, o={};"
            "Object.keys(p).forEach(function(k){"
            " if(p[k].enabled===false) return;"
            " o[k]={packs:p[k].packs||[], bands:p[k].bands||[]}; });"
            "JSON.stringify(o)")
    try:
        got = subprocess.run(["osascript", "-l", "JavaScript", "-e", expr],
                             capture_output=True, text=True, timeout=60)
        js = json.loads(got.stdout.strip() or "{}")
        same = (sorted(js) == sorted(py) and
                all(js[k]["packs"] == py[k]["packs"] and
                    js[k]["bands"] == py[k]["bands"] for k in js))
        bad = [k for k in js if k not in py or js[k]["packs"] != py[k]["packs"]]
        check("画面とサーバで既定の進度が一致する", same,
              "食いちがい %s" % (bad[:3] or sorted(set(py) ^ set(js))[:3]))
    except Exception as e:                              # noqa: BLE001
        check("画面とサーバで既定の進度が一致する", False, "確かめられない: %s" % e)

    # 長文が紙に載るか。**範囲で絞った状態で確かめる。**
    #
    # 読解の単元（「長文を読む」）は授業で習う単元ではないので、
    # 範囲（units）で絞ると消える。範囲なしで試すと出るので、
    # 検査が通ったまま 実機の紙から読解が丸ごと落ちていた ――
    # 漢字の読みばかり27問が並んだ紙が刷られた。
    sch2 = "bunchk"
    os.makedirs(paths.school_dir(sch2), exist_ok=True)
    paths.save(paths.school_file(sch2, "school.json"), {"name": "長", "code": "b"})
    for sub in ("japanese", "english"):
        miss = []
        for g in ("e4", "e5", "e6", "j1", "j2", "j3"):
            items = examprep.pack_items(sub, g)
            if not any(x.get("bun") for x in items):
                continue
            # 授業で習う単元だけに絞る（読解の単元は入らない）
            taught = [u for u in sorted({x.get("unit") for x in items
                                         if x.get("unit")})
                      if "読む" not in u][:6]
            for day in ("2026-09-01", "2026-09-04", "2026-09-07"):
                got = examprep.build(sch2, g, sub, "advanced", [], day,
                                     units=taught, materials={}, hard=None)
                pi = prepsheet.paper_items([got]) if got else []
                if not any(x.get("bun") for x in pi):
                    miss.append("%s/%s" % (g, day))
        check("範囲で絞っても長文が紙に載る（%s）" % sub, not miss, repr(miss[:4]))

    # 紙の割りつけ。**ここが外れると、刷ったとき1枚が2ページに割れる。**
    #
    # 実際に起きたのは2つ。
    #   ・CSS の columns にページの切れ目をまかせていた
    #     → 画面が694mm（A4 2.3枚分）の1本の長い紙になっていた
    #   ・紙の指定で .sheet.page の min-height:297mm が残っていた
    #     → 1枚がページ枠（273mm）に収まらず、5枚が9ページになった
    # どちらも「落ちない」ので、刷るまで気づけない。
    css = io.open(os.path.join(ROOT, "server", "prepsheet.py"),
                  encoding="utf-8").read()
    js = io.open(os.path.join(ROOT, "app", "js", "sheet-print.js"),
                 encoding="utf-8").read()
    # CSS の columns は残してよい ―― **JS が読めなかったときの逃げ道**である。
    # ただし、ふだんの割りつけは JS がやること（.cols2 に組み直す）。
    check("JS が組み直す段組みがある", ".cols2" in css and ".cols2 .col" in css)
    check("割りつけの道具がある", "function paginate" in js and ".cols2" in js)
    check("組み直したら もとの1枚ものを消している",
          "parent.removeChild(sheet)" in js)
    # **画面と紙で寸法を変えない。** 変えると、
    #   ・割りつけを決めた寸法と刷る寸法がずれ、縮めて刷られる
    #   ・解答らん（中身がすべて絶対配置）が高さ0にたたまれ、重なる
    #   ・位置合わせ四角形の位置がずれ、カメラが読めなくなる
    check("紙の余白は @page ではなく .sheet が作る",
          "@page{ size:A4 portrait; margin:0 }" in css)
    check("紙でも .sheet の大きさを外していない",
          ".sheet{ margin:0; box-shadow:none" in css
          and "width:auto" not in css.split("@media print")[1])
    check("解答らんの箱に大きさが指定してある",
          "width:210mm; height:297mm; min-height:297mm" in css)
    check("1枚ごとに改ページする指定がある",
          ".sheet + .sheet{ break-before:page" in css)
    check("1枚の大きさが A4 ちょうど",
          ".sheet.page{ height:297mm; min-height:297mm" in css)
    # 国語は A4よこ・縦書き。**紙の向きまで指定していないと、
    # よこ向きの中身が たて紙に刷られて 右側が切れる。**
    check("国語の紙は A4よこ",
          ".sheet.page.tate{ width:297mm; height:210mm" in css
          and "@page yoko{ size:A4 landscape" in css)
    # 段の高さを「ページ全体」にしない。**flex の残りに広げる。**
    # 100% はページ全体を指すので、見出しのぶん下にはみ出す
    # （実際、縦書きの本文が紙を突き抜けて 次の紙に重なった）。
    check("段は 残りの高さに広がる",
          ".sheet.page .cols2{ flex:1 1 auto; min-height:0 }" in css)
    check("丸めのはみ出しを止めている",
          "overflow:hidden }" in css.split("@media print")[1])

    # ---- 縦書きの組版 ----
    # **CSS に「詰めた数字」を書かない。** 教材ごとに長さが違うので、
    # 1つの数字は必ず外れる（短い本文では無意味に小さくなる）。
    # 紙は読める組版から始め、入らないときだけ JS が測って落とす。
    check("本文の組版が 読める標準になっている",
          ".cols2.tate .bun{ margin:0 2.4mm 0 2mm; font-size:10.5pt;"
          " line-height:1.9 }" in css)
    # 青空文庫の本文は段落の頭に全角空白が入っている。CSS の1字下げと
    # 合わさって **2マス下がる**。紙と画面の両方で落とすこと。
    ui = io.open(os.path.join(ROOT, "app/js/ui-student.js"),
                 encoding="utf-8").read()
    check("段落頭の空白を落としている",
          "lstrip(" in css and "u3000" in ui and "replace(/^[" in ui)
    check("入らないときだけ 測って詰める", "function shrink(" in js
          and "STEPS" in js and "data-toolong" in js)
    check("詰める下限がある", "8.5pt" in js and "9pt" in js)
    check("紙の検査が置いてある",
          os.path.isfile(os.path.join(ROOT, "app/tools/紙の検査.js")))

    # 目録に足す道具が、目録の形を壊さないか（読めるJSのまま残るか）
    man = io.open(os.path.join(ROOT, "app", "content", "manifest.js"),
                  encoding="utf-8").read()
    check("目録に packs がある", "  packs: [" in man)
    check("目録の書き足し口がある", hasattr(inn, "upsert_manifest"))


def main():
    if os.path.isdir(TMP):
        shutil.rmtree(TMP)
    print("こわれ方の検査 ―― 実際に壊れる条件を作って通す")
    print("保管先 %s（終わったら消す）" % TMP)

    sch = s1_empty()
    s2_slug()
    s3_race(sch)
    s4_cycle()
    s5_perm(sch)
    s6_sheet()
    s7_summary()
    s8_dose()
    s9_csv()

    shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "=" * 56)
    if NG:
        print("×  %d件 ひっかかった（通ったのは %d件）" % (len(NG), OK))
        for name, detail in NG:
            print("     %s   %s" % (name, detail))
        return 1
    print("すべて通った。（%d件）" % OK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
