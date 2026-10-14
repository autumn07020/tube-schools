#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管理ページの口 ―― 席・講師・担当・生徒に出ているもの・報告。

    /api/admin/…   役割が admin のアカウントだけ（tube_server.api の門を通ってから来る）
    /api/report    だれでも（うまく動かないときの報告）。置くのは add_report

考え方
------
1. **校舎は合言葉から。** ここに来る acc["school"] だけを使う。要求が名乗る校舎は見ない。
2. **管理者は、答案も記録も読めない。** 見えるのは「だれの席があるか・だれが担当か・
   何が出ているか（件数と名前）・報告」だけ。生徒の写真・評価・進捗を返す口は作らない。
3. **合言葉そのものは受け取らない。** 作るのは管理者の端末（ブラウザ）。届くのは
   ハッシュ（tube_server.clean_verifier の形）だけ。サーバは、作った合言葉を一度も見ない。
4. **操作は小さく、1回で完結させる。** 画面から「全体を書き戻す」口を作らない。
   「この席を使う」「このコースにこの講師を足す」のように、1つの操作を鍵の中で
   確かめてから書く ―― 2つの窓から同時に押しても、片方がもう片方を消さない。
5. 変えたら必ず監査の跡（audit）。

席（seat）
----------
まだ誰にも渡していない席は role が "seat"。名簿・宿題の受け取り手・成績のどこにも出ない。
はじめて入ったとき（tube_server のログイン）か、ここで「使う」にしたとき student になる。
記録のある席は消せない（在籍終了にする。入れなくなり、記録は残る）。

tube_server を T として受け取る（循環 import を避けるため。demo_running.py と同じ形）。
"""

import csv
import hashlib
import io
import json
import os
import re
import secrets
import time

import paths
import courses
import lessons as L
import join as JOIN
import retire as RETIRE
import exams as EX
import curriculum_source as SOURCE              # noqa: E402

class NotFound(Exception):
    """指された席・コース・報告が無い。404 にする。"""


STATE_MAX = 120          # 1回に状態を変えられる席
REPORT_KEEP = 800        # 残す報告の数
REPORT_TEXT = 1000
SAY_PER_HOUR = 6         # 1人が1時間に書ける報告
ERR_PER_HOUR = 30        # 1人の画面が1時間に送れるエラー


# ------------------------------------------------------------------
# 読む
# ------------------------------------------------------------------
def _records_of(T, school, login_id, a, asg=None, plans=None):
    """この口座に「消したら失われるもの」があるか。あれば、その名前の一覧。"""
    why = []
    sid = a.get("sid") or ""
    if a.get("lastLogin"):
        why.append("入ったことがある")
    if a.get("role") in ("student", "seat") and sid:
        try:
            if os.path.isfile(paths.progress_path(school, sid)):
                why.append("学習の記録")
            if os.path.isdir(paths.submit_dir(school, sid)):
                why.append("出した写真")
        except paths.BadPath:
            pass
        asg = T.assignments(school) if asg is None else asg
        if any(sid in (x.get("students") or []) for x in asg.values() if isinstance(x, dict)):
            why.append("出された宿題")
        if a.get("moves"):
            why.append("クラス替えの記録")
    plans = courses.all_courses(school) if plans is None else plans
    for p in plans.values():
        if sid and sid in (p.get("students") or []):
            why.append("コースの指名")
            break
    return why


def _unreceive(T, sid, asg, subs, rt):
    """「使う」の取り消し：この生徒を、宿題の受け取り手から外す。外せたら True（asg を直す。保存は呼ぶ側）。

    「使う」にすると、その場で期限前の宿題の受け取り手に入る（join_open_homework）。だから
    まちがえて「使う」にした席は、記録が1つも無くても「出された宿題がある」になり、戻せなかった
    （まとめて使う、を1回押しまちがえると、30人ぶんの幽霊が名簿と提出率に残った。2026-09-30、
    第三者の検査で見つかった）。

    その宿題に本人の記録（写真・評価）が1つでもあれば、外さない（False。在籍終了にしてもらう）。
    外して受け取り手が0人になる宿題は、宿題ごと消す ―― students が空の宿題は「クラス全員」に
    化ける（students_for）。0人の宿題は、もともと出さない決まり。ほかの人の記録が残っている
    宿題なら、消さずに止める（False）。
    """
    mine = [(aid, x) for aid, x in asg.items()
            if isinstance(x, dict) and sid in (x.get("students") or [])]
    for aid, x in mine:
        if T._has_record(subs, rt, None, aid, sid):
            return False
        if len(x["students"]) == 1 and (subs.get(aid) or rt.get(aid)):
            return False
    for aid, x in mine:
        x["students"].remove(sid)
        if x.get("joined"):
            x["joined"] = [j for j in x["joined"] if j.get("sid") != sid]
            if not x["joined"]:
                x.pop("joined")
        if not x["students"]:
            asg.pop(aid)
    return True


def _exams_view(T, school, db):
    """組分けテストの日程と、いま聞いている「クラスは？」の進み具合。"""
    w = EX.placement_window(school)
    ask = None
    if w:
        total = answered = 0
        dp = w["exam"].get("dept") or ""
        for a in db.values():
            if a.get("role") != "student" or a.get("leftAt") or int(a.get("created") or 0) >= w["from"]:
                continue
            if dp and SOURCE.dept_of(a.get("level"), a.get("classId")) != dp:
                continue                # その部のテストではない生徒には聞いていない
            total += 1
            if (a.get("placed") or {}).get("exam") == w["exam"]["date"]:
                answered += 1
        ask = {"exam": w["exam"]["date"], "fromDay": w["fromDay"], "toDay": w["toDay"], "answered": answered, "total": total}
    wait = len([1 for a in db.values() if a.get("role") == "student" and not a.get("leftAt") and a.get("needClass") and not a.get("classId")])
    return {"items": EX.all_exams(school), "resultDays": EX.result_days(school), "askDays": EX.ASK_DAYS, "ask": ask,
            # 新年度のはじまり（この日に全員の学年が1つ上がる）と、この前の繰り上げ・まだクラスを答えていない人数
            "yearStart": EX.year_start(school), "rolled": T.school_meta(school).get("rolled") or None, "yearWait": wait,
            "today": time.strftime("%Y-%m-%d")}


RECENT_ACTIONS = {"join_done": "登録", "placement": "変更", "placed": "組分けの答え", "admin_state": "在籍", "login_locked": "入口の見張り",
                  "admin_password": "合言葉の作り直し", "admin_claim": "合言葉を渡した", "go_live": "本番に切り替え",
                  "retired": "使われず破棄", "rolled": "学年の繰り上げ", "admin_year": "新年度の日付"}


def _recent(T, school, limit=40):
    """最近の動き（監査の記録の終わりから）。だれが見たか、ではなく、口座に起きたことだけ。"""
    path = paths.school_file(school, "audit.log")
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 160 * 1024))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except (IOError, OSError):
        return []
    out = []
    for ln in reversed(lines):
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        act = r.get("action")
        if act not in RECENT_ACTIONS:
            continue
        out.append({"at": int(r.get("ts") or 0), "kind": RECENT_ACTIONS[act], "id": str(r.get("target") or "")[:64],
                    "by": str(r.get("actor") or "")[:32], "text": str(r.get("extra") or "")[:120]})
        if len(out) >= limit:
            break
    return out


def _hw_by_course(T, school, now_ms):
    """コースごとの「いま出ている宿題」。件数と、いちばん新しいものの名前・期限だけ。"""
    out = {}
    for a in T.assignments(school).values():
        if not isinstance(a, dict):
            continue
        key = (a.get("lesson") or {}).get("key")
        if not key:
            continue
        o = out.setdefault(key, {"open": 0, "all": 0, "last": None})
        o["all"] += 1
        due = int(a.get("dueAt") or 0)
        if due >= now_ms:
            o["open"] += 1
        at = int(a.get("assignedAt") or 0)
        if o["last"] is None or at > o["last"]["at"]:
            o["last"] = {"at": at, "title": str(a.get("title") or "")[:60], "due": due}
    return out


def state(T, school, acc):
    """管理ページが1回で読む全部。名前・写真・点数は入らない。"""
    db = T.accounts(school)
    plans = courses.all_courses(school)
    tbl = T.class_table(school)
    by_sid = {a.get("sid"): lid for lid, a in db.items() if a.get("sid")}
    now = time.time()
    hw = _hw_by_course(T, school, int(now * 1000))

    classes = []
    for cid, c in tbl.items():
        seats = []
        for lid, a in db.items():
            if a.get("classId") != cid or a.get("role") not in ("student", "seat"):
                continue
            # pending … 初回登録の途中（ID を見せたが、まだ合言葉を作っていない。1時間で消える）
            st = "left" if a.get("leftAt") else (("pending" if a.get("pending") else "spare") if a["role"] == "seat" else "live")
            seats.append({"id": lid, "seat": T.seat_of(a), "st": st,
                          "last": a.get("lastLogin") or 0, "made": a.get("created") or 0,
                          "subjects": a.get("subjects") or [],
                          # 引き換え待ち（オンラインで渡した。まだ本人が引き換えていない）と、その期限・引き換えた日
                          "claim": int((a.get("claim") or {}).get("exp") or 0), "claimed": a.get("claimedAt") or 0})
        seats.sort(key=lambda s: (s["st"] == "left", s["seat"], s["id"]))
        classes.append({"id": cid, "name": c.get("name") or cid, "grade": c.get("grade") or "",
                        "seats": seats})

    # クラスの決まっていない生徒：卒業（grad）と、新しい学年のクラスをまだ答えていない生徒（ask）。クラスの紙には出ないので、別に並べる。
    loose = [{"id": lid, "grade": a.get("level") or "", "st": "grad" if a.get("grad") else "ask",
              "subjects": a.get("subjects") or [], "last": a.get("lastLogin") or 0}
             for lid, a in sorted(db.items())
             if a.get("role") == "student" and not a.get("leftAt") and a.get("classId") not in tbl]

    teachers, admins = [], []
    for lid, a in sorted(db.items()):
        if a.get("role") == "teacher":
            keys = sorted(k for k, p in plans.items() if a.get("sid") in (p.get("teachers") or []))
            teachers.append({"id": lid, "label": T.seat_of(a), "left": bool(a.get("leftAt")),
                             "claim": int((a.get("claim") or {}).get("exp") or 0), "claimed": a.get("claimedAt") or 0,
                             "last": a.get("lastLogin") or 0, "made": a.get("created") or 0,
                             "keys": keys, "all": "*" in (a.get("classes") or [])})
        elif a.get("role") == "admin":
            admins.append({"id": lid, "last": a.get("lastLogin") or 0, "left": bool(a.get("leftAt")),
                           "me": lid == acc.get("loginId")})

    rows = []
    for key, p in sorted(plans.items()):
        nx = None
        try:
            l = T.next_lesson_of(p)
            if l:
                nx = {"date": l.get("date") or "", "unit": L.unit_name(l) if hasattr(L, "unit_name") else (l.get("topic") or "")}
        except Exception:
            nx = None
        h = hw.get(key) or {"open": 0, "all": 0, "last": None}
        rows.append({
            "key": key, "name": p.get("name") or key, "grade": p.get("grade") or "",
            "grades": p.get("grades") or [p.get("grade") or ""], "subject": p.get("subject") or "",
            "teachers": [by_sid[s] for s in (p.get("teachers") or []) if s in by_sid],
            "classes": list(p.get("classes") or []), "named": len(p.get("students") or []),
            "slots": courses.slots_text(p.get("slots")), "use": courses.use_level(p),
            "active": bool(courses.active(p)), "to": p.get("to") or "",
            "n": len(courses.receivers(school, p, db)),
            # 受け取る生徒の ID（在籍の生徒だけ。渡していない席は入らない）。「どの講師が、どの生徒を受け持つか」を見せる。
            "ids": sorted(by_sid[x] for x in courses.receivers(school, p, db) if x in by_sid),
            "lessons": len(p.get("lessons") or []),
            "open": h["open"], "out": h["all"], "last": h["last"], "next": nx,
        })

    rep = load_reports(school)
    meta = T.school_meta(school)
    return {
        "school": {"id": school, "name": T.school_name(school), "code": T.school_code(school),
                   "demo": bool(meta.get("demo")), "trial": bool(meta.get("trial")), "live": bool(meta.get("live"))},
        # 招待コード（初回登録の入口の札）。まだ作っていなければ空。
        "join": {"code": (meta.get("join") or {}).get("code") or "", "at": int((meta.get("join") or {}).get("at") or 0)},
        "me": acc.get("loginId"),
        "classes": classes, "teachers": teachers, "admins": admins, "courses": rows,
        "useWords": courses.USE_WORDS if hasattr(courses, "USE_WORDS") else {},
        "reports": {"open": len([r for r in rep if r.get("state") != "done"]), "all": len(rep)},
        "recent": _recent(T, school),
        "exams": _exams_view(T, school, db),
        "idle": RETIRE.view(T, school, db),
        "loose": loose,
        "combos": {k: [list(c) for c in v] for k, v in JOIN.COMBOS.items()},
        "words": len(T.pw_words()),
        "now": int(now),
    }


# ------------------------------------------------------------------
# 席・講師を足す（届くのはハッシュだけ）
# ------------------------------------------------------------------
def _verifiers(T, d, cap):
    vs = d.get("verifiers")
    if not isinstance(vs, list) or not vs:
        raise ValueError("合言葉のハッシュがありません")
    if len(vs) > cap:
        raise ValueError("1回に足せるのは %d 件までです" % cap)
    out = [T.clean_verifier(v) for v in vs]
    if len({v["storedKey"] for v in out}) != len(out) or len({v["salt"] for v in out}) != len(out):
        raise ValueError("同じハッシュが2つ入っています")
    return out


def add_staff(T, school, acc, d, role):
    vs = _verifiers(T, d, 20)
    made = []
    with T.LOCK:
        # ID は、講師 t-001・開発者（管理者）d-001 の通し番号（校舎をまたいで一意。join.alloc_id）。
        # 呼び名（seat）も ID と同じ。前の wt01・wadmin01 の形の口座は、そのまま使える。
        taken = []
        for v in vs:
            lid = JOIN.alloc_id(T, role, taken)
            taken.append(lid)
            if role == "teacher":
                T.add_account(school, lid, None, lid, "teacher", "", "", classes=["-"], verifier=v)
            else:
                T.add_account(school, lid, None, lid, "admin", "", "", verifier=v)
            made.append({"id": lid, "label": lid})
    T.audit(school, acc["loginId"], "admin_" + role, "", "%d件" % len(made))
    return made


def set_password(T, school, acc, login_id, d):
    ver = T.clean_verifier(d.get("verifier"))
    with T.LOCK:
        db = T.accounts(school)
        a = db.get(login_id)
        if not a:
            raise NotFound(login_id)
        a.pop("hash", None)
        a.update(ver)
        a["pwAt"] = int(time.time())
        if d.get("claim") is True:
            # 「1回だけ使える言葉」として渡す（オンラインの生徒）。本人が引き換えるまで、ふつうには入れない。
            if a.get("role") == "admin":
                raise ValueError("管理者には使えません")
            a["claim"] = {"at": int(time.time()), "exp": int(time.time()) + T.CLAIM_DAYS * 86400, "by": acc["loginId"]}
        else:
            a.pop("claim", None)
        T.save_accounts(school, db)
        n = T.revoke_tokens(login_id)       # 前の合言葉で入ったままの画面を、同じ鍵の中で閉じる
    T.audit(school, acc["loginId"], "admin_claim" if d.get("claim") is True else "admin_password", login_id, "開いていた画面 %d" % n)
    return {"id": login_id, "closed": n, "claim": bool(d.get("claim") is True)}


def claim(T, school, acc, verifier):
    """引き換える。生徒の端末が作った本物の合言葉の値を置き、引き換えの言葉を使えなくする。

    acc は、引き換えの言葉で入った印の持ち主（tube_server.api の門を通ってから来る）。
    """
    ver = T.clean_verifier(verifier)
    lid = acc["loginId"]
    with T.LOCK:
        db = T.accounts(school)
        a = db.get(lid)
        if not a or a.get("leftAt") or not a.get("claim"):
            raise ValueError("もう引き換えてあります")
        if time.time() > int(a["claim"].get("exp") or 0):
            raise ValueError("期限が過ぎています。先生に、もう一度送ってもらってください")
        if ver["salt"] == a.get("salt") or ver["storedKey"] == a.get("storedKey"):
            raise ValueError("引き換えの言葉を、そのまま合言葉にはできません")
        a.update(ver)
        a.pop("claim", None)
        a["claimedAt"] = int(time.time())
        born = T.activate_seat(db, lid, by="claim")   # 引き換えた席は、在籍の生徒になる
        T.save_accounts(school, db)
        if born:
            T.join_open_homework(school, [lid])       # いま出ている宿題（期限前）に足す
        T.revoke_tokens(lid)                          # 引き換えの言葉で入った印も、ここで閉じる
    T.audit(school, lid, "claim_done", lid, "")
    return True


# ------------------------------------------------------------------
# 状態を変える・消す
# ------------------------------------------------------------------
def _drop_teacher_from_courses(school, sid):
    """その講師を、全部のコースの担当から外す。外したコースの鍵を返す。"""
    gone = []
    with L.paths_lock():
        data = L.load(school)
        for key, p in (data.get("plans") or {}).items():
            if isinstance(p, dict) and sid in (p.get("teachers") or []):
                p["teachers"] = [s for s in p["teachers"] if s != sid]
                gone.append(key)
        if gone:
            L.save(school, data)
    return gone


def set_state(T, school, acc, d):
    ids = d.get("ids")
    want = str(d.get("state") or "")
    if want not in ("live", "spare", "left"):
        raise ValueError("状態は live / spare / left")
    if not isinstance(ids, list) or not ids or len(ids) > STATE_MAX:
        raise ValueError("席を 1〜%d 件で指定してください" % STATE_MAX)
    ids = [str(x)[:32] for x in ids]
    done, skipped, dropped, born = [], [], {}, []
    with T.LOCK:
        db = T.accounts(school)
        asg = T.assignments(school)
        plans = courses.all_courses(school)
        now = int(time.time())
        subs = rt = None          # 「まだ」に戻すときだけ読む（写真・評価の台帳）
        asg_dirty = False
        for lid in ids:
            a = db.get(lid)
            if not a:
                skipped.append({"id": lid, "why": "そのIDはありません"})
                continue
            role = a.get("role")
            if lid == acc.get("loginId"):
                skipped.append({"id": lid, "why": "自分の口座は変えられません"})
                continue
            if want == "live":
                if role == "seat":
                    T.activate_seat(db, lid, by=acc["loginId"])
                    born.append(lid)
                elif a.get("leftAt"):
                    a.pop("leftAt", None)
                    if role == "student":
                        a["seat"] = T.free_seat(db, a.get("classId"), a.get("seat"), me=lid)
                        born.append(lid)       # 戻ってきた生徒にも、いま出ている宿題（期限前）を
                else:
                    skipped.append({"id": lid, "why": "もう使っています"})
                    continue
            elif want == "spare":
                if role != "student" or a.get("leftAt"):
                    skipped.append({"id": lid, "why": "使っている席だけ戻せます"})
                    continue
                why = _records_of(T, school, lid, a, asg, plans)
                if why == ["出された宿題"]:
                    # 受け取り手に入っているだけ（写真も評価も無い）なら、外して戻す。
                    if subs is None:
                        subs, rt = T.SUB.load(school), T.ratings(school)
                    if _unreceive(T, a.get("sid"), asg, subs, rt):
                        why, asg_dirty = [], True
                    else:
                        why = ["宿題の写真か評価"]
                if why:
                    skipped.append({"id": lid, "why": "記録があります（%s）。在籍終了にしてください" % "・".join(why)})
                    continue
                a["role"] = "seat"
                a.pop("usedAt", None)
                a.pop("usedBy", None)
                T.revoke_tokens(lid)
            else:   # left
                if role not in ("student", "teacher", "admin"):
                    skipped.append({"id": lid, "why": "まだ渡していない席は、消すだけでかまいません"})
                    continue
                if a.get("leftAt"):
                    skipped.append({"id": lid, "why": "すでに在籍終了です"})
                    continue
                a["leftAt"] = now
                T.revoke_tokens(lid)
            done.append(lid)
        if done:
            T.save_accounts(school, db)
        if asg_dirty:
            T.save_assignments(school, asg)
        if born:
            T.join_open_homework(school, born)        # 「使う」にした席を、いま出ている宿題（期限前）に足す
        if want == "left":
            for lid in done:
                if db[lid].get("role") == "teacher":
                    dropped[lid] = _drop_teacher_from_courses(school, db[lid]["sid"])
                elif db[lid].get("role") == "student":
                    # 退塾で即削除（2026-10-08）：答案の写真と返した添削、この生徒だけの宿題の決まりを消す。評価の記録は残る
                    try:
                        T.SUB.drop_student(school, db[lid]["sid"])
                        if getattr(T, "PERSONAL", None):
                            T.PERSONAL.drop_student(school, db[lid]["sid"])
                    except Exception:
                        pass
    for lid in done:
        T.audit(school, acc["loginId"], "admin_state", lid, want)
    return {"done": done, "skipped": skipped, "dropped": dropped}


def delete_account(T, school, acc, login_id):
    """消す。**記録のあるものは消さない**（在籍終了にしてもらう）。"""
    if login_id == acc.get("loginId"):
        raise ValueError("自分の口座は消せません")
    with T.LOCK:
        db = T.accounts(school)
        a = db.get(login_id)
        if not a:
            raise NotFound(login_id)
        why = _records_of(T, school, login_id, a)
        if why:
            raise ValueError("記録があります（%s）。消さずに、在籍終了にしてください" % "・".join(why))
        if a.get("role") == "admin" and len([x for x in db.values()
                                             if x.get("role") == "admin" and not x.get("leftAt")]) <= 1:
            raise ValueError("管理者が1人もいなくなります")
        gone = _drop_teacher_from_courses(school, a["sid"]) if a.get("role") == "teacher" else []
        db.pop(login_id)
        T.save_accounts(school, db)
        paths.unbind_login(login_id)
        T.revoke_tokens(login_id)
    T.audit(school, acc["loginId"], "admin_delete", login_id, a.get("role") or "")
    return {"id": login_id, "dropped": gone}


# ------------------------------------------------------------------
# 担当
# ------------------------------------------------------------------
def set_teacher(T, school, acc, d):
    """1つのコースに、1人の講師を足す／外す。"""
    key = str(d.get("key") or "")[:48]
    lid = str(d.get("id") or "")[:32]
    on = d.get("on") is True
    with L.paths_lock():
        # 口座は鍵の中で読む（読んだあとで消されたり在籍終了になったりした講師を、担当に残さない）。
        a = T.accounts(school).get(lid)
        if not a or a.get("role") != "teacher":
            raise ValueError("講師のIDが見つかりません: %s" % lid)
        if on and a.get("leftAt"):
            raise ValueError("在籍終了の講師は、担当にできません")
        data = L.load(school)
        p = (data.get("plans") or {}).get(key)
        if not courses.is_course(p):
            raise NotFound(key)
        cur = list(p.get("teachers") or [])
        if on and a["sid"] not in cur:
            cur.append(a["sid"])
        if not on:
            cur = [s for s in cur if s != a["sid"]]
        if cur != (p.get("teachers") or []):
            p["teachers"] = cur
            L.save(school, data)
    T.audit(school, acc["loginId"], "admin_teacher", key, ("+" if on else "-") + lid)
    return {"key": key, "id": lid, "on": on}


def set_course_student(T, school, acc, d):
    """指名のコース（土特・必勝・オンラインなど。在籍クラスを持たないコース）に、生徒を1人足す／外す。

    在籍クラスで受けるコース（小4α 算数など）は、クラスの生徒が自動で受け取るので、ここでは触らない
    （クラスを替えるのは「クラス替え」）。出したあとの宿題は書き換えない（外しても、出た宿題は残る）。
    """
    key = str(d.get("key") or "")[:48]
    lid = str(d.get("id") or "")[:32]
    on = d.get("on") is True
    with L.paths_lock():
        a = T.accounts(school).get(lid)               # 口座は鍵の中で読む
        if not a or a.get("role") != "student" or a.get("leftAt"):
            raise ValueError("在籍の生徒のIDが見つかりません: %s（まだ渡していない席は、先に「使う」にします）" % lid)
        data = L.load(school)
        p = (data.get("plans") or {}).get(key)
        if not courses.is_course(p):
            raise NotFound(key)
        if p.get("classes"):
            raise ValueError("このコースは、在籍クラスの生徒が受け取ります。指名はできません")
        grades = p.get("grades") or [p.get("grade") or ""]
        if on and a.get("level") not in grades:
            raise ValueError("学年が違います（このコースは %s）" % "・".join(grades))
        cur = list(p.get("students") or [])
        if on and a["sid"] not in cur:
            if len(cur) >= 120:
                raise ValueError("指名は 120 人までです")
            cur.append(a["sid"])
        if not on:
            cur = [x for x in cur if x != a["sid"]]
        if cur != (p.get("students") or []):
            p["students"] = cur
            L.save(school, data)
    T.audit(school, acc["loginId"], "admin_named", key, ("+" if on else "-") + lid)
    return {"key": key, "id": lid, "on": on}


def courses_csv(T, school):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(courses.HEAD)
    w.writerows(courses.export_rows(school, T.accounts(school)))
    return buf.getvalue()


def import_courses(T, school, acc, d):
    """コースの表（CSV の文字）を入れる。**1行でもおかしければ、何も入れない。**"""
    text = str(d.get("text") or "")
    if len(text) > 200000:
        raise ValueError("表が大きすぎます")
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    if not rows:
        raise ValueError("行がありません")
    if not all(h in rows[0] for h in courses.HEAD):
        raise ValueError("見出しが違います。必要な列: %s" % ",".join(courses.HEAD))
    db = T.accounts(school)
    known = set(T.class_table(school).keys())
    parsed, bad, seen = [], [], set()
    for i, r in enumerate(rows, 2):
        try:
            key, row = courses.parse_row(r, db, known)
        except ValueError as e:
            bad.append("%d行目: %s" % (i, e))
            continue
        if key in seen:
            bad.append("%d行目: 同じコースが2回あります: %s" % (i, key))
            continue
        seen.add(key)
        parsed.append((key, row))
    if bad:
        raise ValueError("直してから入れ直してください（何も入れていません）\n" + "\n".join(bad[:30]))
    made, changed = courses.upsert(school, parsed, new_app=False)
    T.audit(school, acc["loginId"], "admin_courses", "", "made=%d changed=%d" % (made, changed))
    return {"made": made, "changed": changed, "same": len(parsed) - made - changed}


# ------------------------------------------------------------------
# クラス替え（5週ごとの組み分け）。中身は tube_server の move_plan・move_apply・move_undo（コマンドと同じ道）
# ------------------------------------------------------------------
def _move_rows(T, school, d):
    """画面から届いた [{id, classId, seat?}] を、move_plan の行にする。

    番号（seat）を書かなければ、行き先のクラスで空いている番号を選ぶ（今の番号が空いていれば今の番号）。
    同じ回で同じクラスへ何人も移るときは、先に選んだ番号を避ける。
    """
    rows = d.get("rows")
    if not isinstance(rows, list) or not rows or len(rows) > 120:
        raise ValueError("移す生徒を 1〜120 人で指定してください")
    db = T.accounts(school)
    moving = {str(r.get("id") or "")[:32] for r in rows if isinstance(r, dict)}
    taken = {}
    for lid, a in db.items():
        # まだ渡していない席・在籍を終えた生徒の番号も避ける（カードに刷ってある番号を、先に取らない）
        if a.get("role") in ("student", "seat") and (lid not in moving or a.get("leftAt")):
            taken.setdefault(a.get("classId"), set()).add(T.seat_of(a))
    out = []
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            raise ValueError("%d件目の形が違います" % i)
        lid = str(r.get("id") or "")[:32]
        cid = str(r.get("classId") or "")[:24]
        a = db.get(lid) or {}
        seat = str(r.get("seat") or "")[:8]
        if not seat:
            used = taken.setdefault(cid, set())
            want = T.seat_of(a) if a else ""
            seat = want if (want and want not in used) else next(("%02d" % n for n in range(1, 100) if "%02d" % n not in used), want)
        taken.setdefault(cid, set()).add(seat)
        out.append((i, lid, cid, seat))
    return out


def move(T, school, acc, d):
    """クラス替え。dry なら確かめるだけ（何も変えない）。確かめてから移すまでを、1つの鍵の中で。"""
    now = time.time()
    with T.LOCK:
        rows = _move_rows(T, school, d)
        plan, errors = T.move_plan(school, rows, now)
        if errors:
            raise ValueError("直してから、もう一度（何も変えていません）\n" + "\n".join(e.strip() for e in errors[:30]))
        tr = {}
        for _aid, sid, op, _key in plan["transfers"]:
            tr.setdefault(sid, {"out": 0, "in": 0, "keep": 0})[op] += 1
        view = [{"id": m["id"], "from": {"classId": m["from"][0], "seat": m["from"][1]},
                 "to": {"classId": m["to"][0], "seat": m["to"][1]},
                 "hw": tr.get(m["sid"]) or {"out": 0, "in": 0, "keep": 0}} for m in plan["moves"]]
        out = {"moves": view, "same": plan["same"], "notes": [n.strip() for n in plan["notes"][:40]]}
        if d.get("dry") is not False:
            return out
        if not plan["moves"]:
            return out
        batch = "m" + time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
        have = T.move_batches(school)
        n = 2
        while batch in have:                       # 同じ秒に2回。番号を分ける（控えを上書きしない）
            batch = "m" + time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + "-%d" % n
            n += 1
        T.move_apply(school, plan, batch, now)
        out["batch"] = batch
    T.audit(school, acc["loginId"], "admin_move", batch, "%d名" % len(view))
    return out


def move_list(T, school):
    bs = T.move_batches(school)
    return [{"batch": b, "at": v["at"], "n": v["n"]} for b, v in sorted(bs.items(), key=lambda kv: -kv[1]["at"])][:30]


def move_undo(T, school, acc, d):
    batch = str(d.get("batch") or "")[:40]
    if not paths.SAFE_STAMP.match(batch):
        raise ValueError("番号が違います")
    dry = d.get("dry") is not False
    with T.LOCK:
        n, errors, notes = T.move_undo(school, batch, apply=not dry)
    if errors:
        raise ValueError("取り消せません（何も変えていません）\n" + "\n".join(e.strip() for e in errors[:30]))
    if not dry:
        T.audit(school, acc["loginId"], "admin_move_undo", batch, "%d名" % n)
    return {"batch": batch, "n": n, "notes": [x.strip() for x in (notes or [])][:40], "done": not dry}


# ------------------------------------------------------------------
# クラスを足す・消す（講習のクラスなど）
# ------------------------------------------------------------------
GRADES = ("e1", "e2", "e3", "e4", "e5", "e6", "j1", "j2", "j3")


def _class_rows(T, school, cur):
    """校舎のクラス表。まだ持っていなければ、既定（app/curriculum.js）を写して持つ。"""
    rows = [dict(c) for c in (cur.get("classes") or []) if isinstance(c, dict) and c.get("id")]
    if not rows:
        rows = [{"id": c["id"], "name": c.get("name") or c["id"], "grade": c.get("grade") or ""}
                for c in T.class_table(school).values()]
    return rows


def add_class(T, school, acc, d):
    cid = str(d.get("id") or "").strip().lower()
    name = _clean_text(d.get("name"), 16)
    # 学年に続けて英小文字だけ（e4s・j3z）。数字で終わる ID は、席の番号と見分けがつかなくなる。
    if not re.match(r"^[ej][1-9][a-z]{1,6}$", cid) or cid[:2] not in GRADES:
        raise ValueError("クラスのIDは、学年（e4・j2 など）に続けて英小文字（例 e4s、j3z）")
    if not name:
        raise ValueError("クラスの名前を入れてください（例 小4S）")
    with T.LOCK:
        cur = dict(T.curriculum(school) or {})
        rows = _class_rows(T, school, cur)
        if any(c["id"] == cid for c in rows):
            raise ValueError("そのIDのクラスは、もうあります: %s" % cid)
        if any((c.get("name") or "") == name for c in rows):
            raise ValueError("その名前のクラスは、もうあります: %s" % name)
        if len(rows) >= 60:
            raise ValueError("クラスは 60 までです")
        rows.append({"id": cid, "name": name, "grade": cid[:2]})
        cur["classes"] = rows
        cur.setdefault("v", 2)
        T.save_curriculum(school, cur)
    T.audit(school, acc["loginId"], "admin_class", cid, name)
    return {"id": cid, "name": name, "grade": cid[:2]}


def delete_class(T, school, acc, cid):
    """クラスを消す。**席のあるクラス・コースが受け持っているクラスは消さない。**"""
    with T.LOCK:
        cur = dict(T.curriculum(school) or {})
        rows = _class_rows(T, school, cur)
        if not any(c["id"] == cid for c in rows):
            raise NotFound(cid)
        db = T.accounts(school)
        if any(a.get("classId") == cid and a.get("role") in ("student", "seat") for a in db.values()):
            raise ValueError("席のあるクラスは消せません。先に、席を消すか移してください")
        if any(cid in (p.get("classes") or []) for p in courses.all_courses(school).values()):
            raise ValueError("このクラスを受け持つコースがあります。先に「コースの表を直す」で外してください")
        cur["classes"] = [c for c in rows if c["id"] != cid]
        cur.setdefault("v", 2)
        T.save_curriculum(school, cur)
    T.audit(school, acc["loginId"], "admin_class_delete", cid, "")
    return {"id": cid}


# ------------------------------------------------------------------
# 報告
# ------------------------------------------------------------------
def _reports_file(school):
    return paths.school_file(school, "reports.json")


def load_reports(school):
    got = paths.load(_reports_file(school), {}) or {}
    items = got.get("items")
    return items if isinstance(items, list) else []


def _clean_text(x, cap):
    t = str(x or "").replace("\r", "")
    t = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", t)
    return t.strip()[:cap]


GUARD_IDS = 30           # 1件の知らせに並べる ID の数


def _guard_text(ids, more):
    return ("まちがった合言葉が続けて届いた ID：%s%s。その ID は、まちがいが続いた所からは"
            "15分ほど入れません（「どこからも」と付いた ID は、どこからも入れません）。"
            "本人が合言葉をなくしていたら、「席と合言葉」で作り直せます。"
            % ("・".join(ids), "（ほか %d）" % more if more else ""))


def add_guard(T, school, target, login_id, everywhere=False):
    """入口の見張りからの知らせ：このIDに、まちがった合言葉が続いて、しばらく入れなくした。

    **校舎ごとに1件にまとめる**（済みにするまで・24時間）。ID ごとに1件ずつ置くと、規則的な ID を
    順にたたくだけで報告が埋まり、生徒や講師が書いた報告が押し出される。合言葉らしきものは入れない。
    """
    now = int(time.time())
    plain, login_id = login_id, (login_id + "（どこからも）" if everywhere else login_id)
    with T.LOCK:
        items = load_reports(school)
        for r in items:
            if r.get("kind") == "guard" and r.get("state") != "done" and now - int(r.get("at") or 0) < 86400:
                ids = [x for x in (r.get("ids") or []) if isinstance(x, str)]
                if everywhere and plain in ids:
                    ids[ids.index(plain)] = login_id      # 同じ所から → どこからも、に書き換える
                if login_id not in ids and not (not everywhere and plain + "（どこからも）" in ids):
                    if len(ids) < GUARD_IDS:
                        ids.append(login_id)
                    else:
                        r["more"] = int(r.get("more") or 0) + 1
                r["ids"] = ids
                r["n"] = int(r.get("n") or 1) + 1
                r["lastAt"] = now
                r["text"] = _guard_text(ids, int(r.get("more") or 0))
                paths.save(_reports_file(school), {"items": items})
                return r
        it = {"id": secrets.token_hex(5), "at": now, "kind": "guard", "sig": "guard",
              "sid": "", "role": "", "classId": "", "seat": "", "ids": [login_id],
              "view": "login", "text": _guard_text([login_id], 0), "ctx": {}, "ua": "",
              "n": 1, "state": "open"}
        items.append(it)
        if len(items) > REPORT_KEEP:
            done = [r for r in items if r.get("state") == "done"]
            drop = set(id(r) for r in sorted(done, key=lambda r: r.get("at") or 0)[:len(items) - REPORT_KEEP])
            items = [r for r in items if id(r) not in drop][-REPORT_KEEP:]
        paths.save(_reports_file(school), {"items": items})
    return it


def add_report(T, school, acc, d, ua=""):
    """うまく動かないときの報告を1件置く。

    kind  "say"   … 人が書いたもの（何が起きたかの文）
          "error" … 画面が拾ったエラー（同じものは1件にまとめ、回数を数える）
    名前は入れない。だれかは、役割とクラスと出席番号まで。
    """
    kind = "error" if d.get("kind") == "error" else "say"
    text = _clean_text(d.get("text"), REPORT_TEXT)
    if not text:
        raise ValueError("何が起きたかを書いてください")
    view = _clean_text(d.get("view"), 40)
    ctx = d.get("ctx") if isinstance(d.get("ctx"), dict) else {}
    ctx = {str(k)[:16]: _clean_text(v, 120) for k, v in list(ctx.items())[:8]}
    now = int(time.time())
    who = acc.get("sid") or ""
    sig = hashlib.sha1((kind + "|" + text[:200]).encode("utf-8")).hexdigest()[:12]
    with T.LOCK:
        items = load_reports(school)
        recent = [r for r in items if r.get("sid") == who and now - int(r.get("at") or 0) < 3600
                  and r.get("kind") == kind]
        cap = ERR_PER_HOUR if kind == "error" else SAY_PER_HOUR
        if kind == "error":
            # 同じエラーは、だれの画面で起きても1件にまとめる（24時間）。
            for r in items:
                if r.get("sig") == sig and r.get("state") != "done" and now - int(r.get("at") or 0) < 86400:
                    r["n"] = int(r.get("n") or 1) + 1
                    r["lastAt"] = now
                    paths.save(_reports_file(school), {"items": items})
                    return r
        if len(recent) >= cap:
            if kind == "error":
                return None                      # 黙って捨てる（画面には関係ない）
            raise ValueError("たくさん届いています。少し時間をおいてから送ってください")
        it = {"id": secrets.token_hex(5), "at": now, "kind": kind, "sig": sig,
              "sid": who, "role": acc.get("role") or "", "classId": acc.get("classId") or "",
              "seat": T.seat_of(acc) if acc.get("role") != "admin" else "",
              "view": view, "text": text, "ctx": ctx, "ua": _clean_text(ua, 200),
              "n": 1, "state": "open"}
        items.append(it)
        if len(items) > REPORT_KEEP:
            # 済んだものから古い順に捨てる。
            done = [r for r in items if r.get("state") == "done"]
            drop = set(id(r) for r in sorted(done, key=lambda r: r.get("at") or 0)[:len(items) - REPORT_KEEP])
            items = [r for r in items if id(r) not in drop][-REPORT_KEEP:]
        paths.save(_reports_file(school), {"items": items})
    if kind == "say":
        T.audit(school, who, "report", it["id"], view)
    return it


def mark_report(T, school, acc, rid, d):
    want = "done" if d.get("state") == "done" else "open"
    note = _clean_text(d.get("note"), 300)
    with T.LOCK:
        items = load_reports(school)
        for r in items:
            if r.get("id") == rid:
                r["state"] = want
                if want == "done":
                    r["doneAt"], r["doneBy"] = int(time.time()), acc["loginId"]
                else:
                    r.pop("doneAt", None)
                    r.pop("doneBy", None)
                if "note" in d:
                    r["note"] = note
                paths.save(_reports_file(school), {"items": items})
                T.audit(school, acc["loginId"], "admin_report", rid, want)
                return r
    raise NotFound(rid)


# ------------------------------------------------------------------
# 入口
# ------------------------------------------------------------------
def handle(T, h, method, parts, acc):
    school = acc["school"]
    try:
        if method == "GET" and parts in ([], ["state"]):
            return h.reply(200, state(T, school, acc))

        d = (h.body_json() or {}) if method in ("POST", "PUT") else {}

        if method == "POST" and parts == ["teachers"]:
            made = add_staff(T, school, acc, d, "teacher")
            return h.reply(200, {"made": made, "state": state(T, school, acc)})
        if method == "POST" and parts == ["admins"]:
            made = add_staff(T, school, acc, d, "admin")
            return h.reply(200, {"made": made, "state": state(T, school, acc)})

        if method == "POST" and parts == ["accounts", "state"]:
            got = set_state(T, school, acc, d)
            got["state"] = state(T, school, acc)
            return h.reply(200, got)
        if len(parts) == 3 and parts[0] == "accounts" and parts[2] == "password" and method == "POST":
            got = set_password(T, school, acc, parts[1][:32], d)
            return h.reply(200, got)
        if len(parts) == 3 and parts[0] == "accounts" and parts[2] == "placement" and method == "PUT":
            # 学年・クラス・受講科目を、管理者が直す（本人の設定と同じ道。回数の上限は無い）
            try:
                what = JOIN.set_placement(T, school, parts[1][:32], grade=d.get("grade"), class_id=d.get("classId"),
                                          subjects=d.get("subjects"), by=acc["loginId"])
            except JOIN.JoinError as e:
                return h.reply(e.status, {"error": str(e)})
            return h.reply(200, {"changed": what, "state": state(T, school, acc)})
        if method == "PUT" and parts == ["exams"]:
            # 組分けテストの日程（管理者が入れる。結果が出てから2週間、生徒にクラスを聞く）
            if "yearStart" in d:
                # 新年度のはじまり（学年の繰り上げ）。この口では日程に触らない。
                ys = EX.set_year_start(school, d.get("yearStart"))
                r = T.school_meta(school).get("rolled") or {}
                if ys and time.time() - int(r.get("at") or 0) < RETIRE.ROLL_GAP and \
                        time.mktime(time.strptime(ys, "%Y-%m-%d")) < int(r.get("at") or 0) + RETIRE.ROLL_GAP:
                    EX.set_year_start(school, "")
                    raise ValueError("この年度は、もう繰り上げました（%s）。次の年度の日付を入れてください。" % r.get("date"))
                T.audit(school, acc["loginId"], "admin_year", "", ys or "外した")
                return h.reply(200, {"state": state(T, school, acc)})
            EX.set_exams(school, d.get("exams"), d.get("resultDays"))
            T.audit(school, acc["loginId"], "admin_exams", "", "%d件" % len(EX.all_exams(school)))
            return h.reply(200, {"state": state(T, school, acc)})
        if method == "POST" and parts == ["join", "code"]:
            j = JOIN.new_code(T, school, acc["loginId"])
            return h.reply(200, {"join": {"code": j["code"], "at": j["at"]}, "state": state(T, school, acc)})
        if len(parts) == 2 and parts[0] == "accounts" and method == "DELETE":
            got = delete_account(T, school, acc, parts[1][:32])
            got["state"] = state(T, school, acc)
            return h.reply(200, got)

        if method == "PUT" and parts == ["courses", "teacher"]:
            got = set_teacher(T, school, acc, d)
            got["state"] = state(T, school, acc)
            return h.reply(200, got)
        if method == "PUT" and parts == ["courses", "student"]:
            got = set_course_student(T, school, acc, d)
            got["state"] = state(T, school, acc)
            return h.reply(200, got)
        if method == "GET" and parts == ["courses", "csv"]:
            return h.reply(200, {"text": courses_csv(T, school)})
        if method == "POST" and parts == ["courses", "csv"]:
            got = import_courses(T, school, acc, d)
            got["state"] = state(T, school, acc)
            return h.reply(200, got)

        if method == "POST" and parts == ["moves"]:
            got = move(T, school, acc, d)
            got["state"] = state(T, school, acc)
            return h.reply(200, got)
        if method == "GET" and parts == ["moves"]:
            return h.reply(200, {"items": move_list(T, school)})
        if method == "POST" and parts == ["moves", "undo"]:
            got = move_undo(T, school, acc, d)
            got["state"] = state(T, school, acc)
            return h.reply(200, got)

        if method == "POST" and parts == ["classes"]:
            got = add_class(T, school, acc, d)
            got["state"] = state(T, school, acc)
            return h.reply(200, got)
        if len(parts) == 2 and parts[0] == "classes" and method == "DELETE":
            got = delete_class(T, school, acc, parts[1][:24])
            got["state"] = state(T, school, acc)
            return h.reply(200, got)

        if method == "GET" and parts == ["reports"]:
            items = sorted(load_reports(school), key=lambda r: -(r.get("lastAt") or r.get("at") or 0))
            return h.reply(200, {"items": items[:400]})
        if len(parts) == 2 and parts[0] == "reports" and method == "PUT":
            return h.reply(200, {"item": mark_report(T, school, acc, parts[1][:16], d)})
    except NotFound:
        return h.reply(404, {"error": "見つかりません"})
    except (ValueError, paths.BadPath) as e:
        return h.reply(400, {"error": str(e)})
    return h.reply(404, {"error": "not-found"})


# ------------------------------------------------------------------
# 束（bundle）―― 手元で作った席・講師・管理者を、ハッシュだけで入れる
# ------------------------------------------------------------------
def _bundle_verifier(T, a):
    """束の1件を、いまの形（scram）にして返す。

    09-30 に作った束（v1）は alg "pbkdf2-600k" と hash を持つ。その hash は SCRAM の
    SaltedPassword そのものなので、合言葉なしで storedKey・serverKey に直せる。
    直したあとは hash を持たない（hash があれば、それだけで入れてしまうため）。
    """
    if not isinstance(a, dict):
        raise ValueError("束の口座の形が違います")
    a = dict(a)
    if a.get("alg") == "pbkdf2-600k" and "hash" in a:
        h, salt = str(a.get("hash") or ""), str(a.get("salt") or "")
        if not T.SCRAM.HEX64.match(h) or not T.SCRAM.HEX32.match(salt):
            raise ValueError("合言葉のハッシュの形が違います: %r" % (a.get("id"),))
        stored, server = T.SCRAM.keys_from_salted(bytes.fromhex(h))
        a.pop("hash")
        a.update({"alg": T.SCRAM.ALG, "iters": T.SCRAM.ITERS, "storedKey": stored, "serverKey": server})
    a.update(T.clean_verifier(a))
    return a


def import_bundle(T, bundle, yes=False, out=print):
    """scripts/accounts/make.py が作った束を入れる。**何度流しても同じ結果**（あるものは触らない）。

    入るもの：校舎（無ければ作る）・口座（IDが無いものだけ）・コースの枠（鍵が無いものだけ）・
    教材台帳（materials.json が無いときだけ）。**合言葉は入っていない**（ハッシュだけ）。
    """
    if not isinstance(bundle, dict) or bundle.get("kind") != "tubestudy-accounts":
        raise ValueError("束の形が違います")
    sc = bundle.get("school") or {}
    school = paths.check_school(str(sc.get("id") or ""))
    code = str(sc.get("code") or "")
    if not re.match(r"^[a-z]{1,2}$", code):
        raise ValueError("校舎コードは英小文字1〜2文字")
    accs = [_bundle_verifier(T, a) for a in (bundle.get("accounts") or [])]
    for a in accs:
        if a.get("role") not in T.ROLES:
            raise ValueError("役割が違います: %r" % (a.get("role"),))
        if not str(a.get("id") or "").startswith(code):
            raise ValueError("IDが校舎コードで始まっていません: %r" % (a.get("id"),))
    exists = os.path.isfile(paths.school_file(school, "school.json"))
    if exists and T.school_code(school) != code:
        raise ValueError("校舎 %s のコードは %s です（束は %s）" % (school, T.school_code(school), code))
    if not exists:
        for other in paths.list_schools():
            if T.school_code(other) == code:
                raise ValueError("その校舎コードは %s が使っています: %s" % (other, code))
    have = T.accounts(school) if exists else {}
    new_acc = [a for a in accs if a["id"] not in have]
    plans = courses.all_courses(school) if exists else {}
    new_courses = [(k, dd) for k, dd in (bundle.get("courses") or []) if k not in plans]
    out("校舎 %s（%s）%s" % (school, sc.get("name") or school, "" if exists else " ―― 新しく作ります"))
    out("  口座   足す %d ／ すでにある %d" % (len(new_acc), len(accs) - len(new_acc)))
    out("  コース 足す %d ／ すでにある %d" % (len(new_courses), len(bundle.get("courses") or []) - len(new_courses)))
    if not yes:
        out("実行するには --yes を付けてください。")
        return 0
    with T.LOCK:
        if not exists:
            paths.ensure_school(school)
            paths.save(paths.school_file(school, "school.json"), {
                "id": school, "name": sc.get("name") or school, "code": code,
                "tz": sc.get("tz") or "Europe/London", "created": int(time.time())})
    made = bad = 0
    for a in new_acc:
        role = a["role"]
        try:
            T.add_account(school, a["id"], None, a.get("seat") or "00", role,
                          a.get("level") or "", a.get("classId") or "",
                          classes=(["-"] if role == "teacher" else None), verifier=a)
            made += 1
        except ValueError as e:
            bad += 1
            out("  × %s: %s" % (a.get("id"), e))
    n_courses = 0
    if new_courses:
        known = set(T.class_table(school).keys())
        ok = []
        for k, dd in new_courses:
            if not isinstance(dd, dict) or not all(c in known for c in (dd.get("classes") or [])):
                bad += 1
                out("  × コース %s: 在籍クラスが見つかりません" % k)
                continue
            row = {kk: dd[kk] for kk in courses.DEF_KEYS if kk in dd}
            row["teachers"], row["students"] = [], []
            ok.append((k, row))
        courses.upsert(school, ok, new_app=False)      # 新しいコースは、講師が選ぶまで紙のまま
        n_courses = len(ok)
    mat = bundle.get("materials")
    if isinstance(mat, dict) and mat and not os.path.isfile(paths.school_file(school, "materials.json")):
        paths.save(paths.school_file(school, "materials.json"), {"items": mat})
    T.audit(school, "cli", "bundle_import", "", "accounts=%d courses=%d bad=%d" % (made, n_courses, bad))
    out("入れました：口座 %d ／ コース %d" % (made, n_courses))
    if bad:
        # 1件でも入らなければ、失敗として返す（反映の道具が、黙って先へ進まないように）。
        out("× 入らなかったものが %d 件あります（上の × を見てください）。" % bad)
        return 1
    return 0
