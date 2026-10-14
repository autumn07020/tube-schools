#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""初回登録 ―― 招待コードから来た保護者が、生徒の口座を自分で作る（匿名・自己申告）。

設計は `Claude outputs/設計-初回登録と匿名の口座.md`。要点だけ：

* 塾は ID と名前を結ばない。学年・クラス・受講科目は自己申告（あとで設定から変えられる）。
* ID は `s-042` の形（無作為）。画面の呼び名（seat）も ID と同じ。
* **ID を先に見せて、合言葉はあとで作ってもらう**ので、口座は2段で作る：
    POST /api/join          仮の口座（role "seat"・pending。名簿にも宿題にも出ない）と、1回きりの鍵 setup
    POST /api/join/finish   合言葉を確かめる値（verifier）を置き、在籍の生徒にする
  仮の口座は1時間で消える（ID は戻る）。合言葉そのものは、ここでもサーバへ来ない。
* 入る前の口（だれでも呼べる）なので、回数を限る。数えるのはメモリの中だけ（起こし直せば消える。それでよい）。

tube_server を import しない（循環を避ける）。呼ぶ側が T を渡す（admin.py と同じ作法）。
"""

import hashlib
import hmac
import re
import secrets
import threading
import time

import paths
import exams as EX
import curriculum_source as SOURCE              # noqa: E402

CODE_ABC = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"     # 紛らわしい 0/O/1/I を外す
CODE_LEN = 6
JOIN_MAX_STUDENTS = 4          # 1回の登録で作れる人数（きょうだい）
PENDING_TTL = 3600             # 合言葉を作らなかった仮の口座が残る秒数
CHECK_PER_15MIN = 20           # 同じ相手が、コードを確かめられる回数
JOIN_PER_HOUR = 6              # 同じ相手が、登録を始められる回数
GRADES = ("e4", "e5", "e6", "j1", "j2", "j3")
# 受講科目の組（設計 4章）。小学生は算数、中学生は数学（どちらも math）。
COMBOS = {
    "e": (("japanese", "math"), ("japanese", "math", "science", "social"),
          ("japanese", "math", "english"), ("japanese", "math", "science", "social", "english")),
    "j": (("japanese", "math"), ("japanese", "math", "english"),
          ("japanese", "math", "science", "social"), ("japanese", "math", "science", "social", "english")),
}
ID_PREFIX = {"student": "s-", "teacher": "t-", "admin": "d-"}

_HITS = {}
_HITS_LOCK = threading.Lock()


class JoinError(ValueError):
    """登録の口のまちがい。status を持つ（400・403・429）。"""
    def __init__(self, msg, status=400):
        ValueError.__init__(self, msg)
        self.status = status


def _allow(kind, who, cap, window):
    """回数の上限。越えていたら False。数えるのは、確かめたその場で（隙間を作らない）。"""
    now = time.time()
    key = kind + ":" + who
    with _HITS_LOCK:
        if len(_HITS) > 5000:
            for k in [k for k, v in _HITS.items() if not v or now - v[-1] > 3600]:
                _HITS.pop(k, None)
        hits = [t for t in _HITS.get(key, []) if now - t < window]
        if len(hits) >= cap:
            _HITS[key] = hits
            return False
        hits.append(now)
        _HITS[key] = hits
    return True


def norm_code(code):
    return re.sub(r"[^A-Z0-9]", "", str(code or "").upper())[:16]


def code_of(T, school):
    j = T.school_meta(school).get("join") or {}
    return j.get("code") or ""


def new_code(T, school, by=""):
    """招待コードを作る（作り直す）。前のコードは、その場で使えなくなる。"""
    code = "".join(secrets.choice(CODE_ABC) for _ in range(CODE_LEN))
    with T.LOCK:
        meta = dict(T.school_meta(school))
        meta["join"] = {"code": code, "at": int(time.time()), "by": by}
        paths.save(paths.school_file(school, "school.json"), meta)
    T.audit(school, by, "join_code", "", "")
    return meta["join"]


def school_for_code(T, code):
    code = norm_code(code)
    if len(code) != CODE_LEN:
        return None
    hit = None
    for sc in paths.list_schools():
        try:
            have = code_of(T, sc)
        except (paths.BadPath, IOError, OSError, ValueError):
            continue
        if have and hmac.compare_digest(have, code):
            hit = sc
    return hit


def _class_rows(T, school):
    tbl = T.class_table(school)
    return [{"id": cid, "name": c.get("name") or cid, "grade": c.get("grade") or ""}
            for cid, c in tbl.items() if (c.get("grade") or "") in GRADES]


def check(T, code, ip):
    """コードを確かめる。合っていれば、選べる学年・クラス・科目の組を返す。"""
    if not _allow("chk", ip, CHECK_PER_15MIN, 900):
        raise JoinError("試した回数が多すぎます。15分ほど待ってから、もう一度お試しください。", 429)
    school = school_for_code(T, code)
    if not school:
        raise JoinError("登録コードが違います。塾からのお知らせを、もう一度ご確認ください。", 403)
    return {"ok": True, "school": {"name": T.school_name(school)}, "classes": _class_rows(T, school),
            "grades": list(GRADES), "combos": {k: [list(c) for c in v] for k, v in COMBOS.items()},
            "max": JOIN_MAX_STUDENTS}


def alloc_id(T, role, taken):
    """使われていない ID を1つ。生徒は無作為（000〜999。9割を超えたら4桁）、講師と開発者は通し番号。"""
    pre = ID_PREFIX[role]
    used = set(k for k in paths.read_index().keys() if k.startswith(pre)) | set(taken)
    if role == "student":
        for width in (3, 4, 5):
            space = 10 ** width
            n_used = len([k for k in used if re.match(r"^%s\d{%d}$" % (re.escape(pre), width), k)])
            if n_used >= space * 9 // 10:
                continue
            for _ in range(200):
                lid = pre + ("%0" + str(width) + "d") % secrets.randbelow(space)
                if lid not in used:
                    return lid
        raise JoinError("ID が足りません。塾にお知らせください。", 500)
    n = 1
    while "%s%03d" % (pre, n) in used:
        n += 1
        if n > 99999:
            raise JoinError("ID が足りません", 500)
    return "%s%03d" % (pre, n)


def sweep(T, school):
    """合言葉を作らないまま1時間たった仮の口座を消す（ID は戻る）。消した数を返す。**呼ぶ側で LOCK を持つこと。**"""
    now = time.time()
    db = T.accounts(school)
    gone = [lid for lid, a in db.items()
            if a.get("role") == "seat" and a.get("pending") and now > int((a.get("pending") or {}).get("exp") or 0)]
    for lid in gone:
        db.pop(lid, None)
    if gone:
        T.save_accounts(school, db)
        for lid in gone:
            paths.unbind_login(lid)
    return len(gone)


def create(T, d, ip):
    """仮の口座を作る。返す {made:[{id, setup, grade, classId, subjects}]}。"""
    if not _allow("new", ip, JOIN_PER_HOUR, 3600):
        raise JoinError("登録の回数が多すぎます。1時間ほど待ってから、もう一度お試しください。", 429)
    school = school_for_code(T, d.get("code"))
    if not school:
        raise JoinError("登録コードが違います。塾からのお知らせを、もう一度ご確認ください。", 403)
    if d.get("agree") is not True:
        raise JoinError("利用規約への同意が必要です。")
    rows = d.get("students")
    if not isinstance(rows, list) or not (1 <= len(rows) <= JOIN_MAX_STUDENTS):
        raise JoinError("登録できるのは、1回に 1〜%d 人です。" % JOIN_MAX_STUDENTS)
    tbl = T.class_table(school)
    want = []
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            raise JoinError("%d人目の形が違います。" % i)
        grade = str(r.get("grade") or "")
        cid = str(r.get("classId") or "")[:24]
        subs = r.get("subjects")
        c = tbl.get(cid)
        if grade not in GRADES:
            raise JoinError("%d人目の学年を選んでください。" % i)
        if not c or (c.get("grade") or "") != grade:
            raise JoinError("%d人目のクラスを選んでください。" % i)
        if not isinstance(subs, list) or tuple(subs) not in COMBOS[grade[0]]:
            raise JoinError("%d人目の受講科目を選んでください。" % i)
        want.append((grade, cid, list(subs)))
    made = []
    now = int(time.time())
    with T.LOCK:
        sweep(T, school)
        taken = []
        for grade, cid, subs in want:
            lid = alloc_id(T, "student", taken)
            taken.append(lid)
            setup = secrets.token_urlsafe(24)
            # だれも合言葉を知らない値を置く（PBKDF2 は回さない。合言葉は finish で本人の端末が作る）。
            dummy = {"alg": T.SCRAM.ALG, "salt": secrets.token_hex(16), "iters": T.SCRAM.ITERS,
                     "storedKey": secrets.token_hex(32), "serverKey": secrets.token_hex(32)}
            T.add_account(school, lid, None, lid, "seat", grade, cid, subjects=subs, verifier=dummy)
            db = T.accounts(school)
            db[lid]["via"] = "join"
            db[lid]["pending"] = {"exp": now + PENDING_TTL, "key": hashlib.sha256(setup.encode("utf-8")).hexdigest()}
            T.save_accounts(school, db)
            made.append({"id": lid, "setup": setup, "grade": grade, "classId": cid, "subjects": subs})
    T.audit(school, "", "join_new", ",".join(m["id"] for m in made), T.ip_bucket(ip))
    return {"made": made}


PLACEMENT_PER_DAY = 6          # 本人が、1日に変えられる回数


def set_placement(T, school, lid, grade=None, class_id=None, subjects=None, by="self", exam=None):
    """学年・クラス・受講科目を変える（本人の設定から／管理者から）。変えた欄の名前の一覧を返す。

    自己申告なので、まちがえたらすぐ直せるようにしておく（設計 0章）。変えたら、期限前の宿題の受け取り手を
    いまのクラスと科目に合わせる（記録のある宿題からは外さない）。ID と呼び名は変わらない。
    本人は1日に 6回まで（まちがいの直しには足りて、いたずらには足りない）。管理者には上限が無い。
    """
    tbl = T.class_table(school)
    now = int(time.time())
    with T.LOCK:
        db = T.accounts(school)
        a = db.get(lid)
        if not a or a.get("role") != "student" or a.get("leftAt"):
            raise JoinError("生徒の口座がありません。", 404)
        g = str(grade) if grade else (a.get("level") or "")
        if g not in GRADES:
            raise JoinError("学年を選んでください。")
        cid = str(class_id)[:24] if class_id else (a.get("classId") or "")
        c = tbl.get(cid)
        if not c or (c.get("grade") or "") != g:
            raise JoinError("その学年のクラスを選んでください。")
        if subjects is not None:
            if not isinstance(subjects, list) or tuple(subjects) not in COMBOS[g[0]]:
                raise JoinError("受講科目を選んでください。")
            subs = list(subjects)
        else:
            subs = list(a.get("subjects") or [])
        what = []
        if g != (a.get("level") or ""):
            what.append("grade")
        if cid != (a.get("classId") or ""):
            what.append("classId")
        if sorted(subs) != sorted(a.get("subjects") or []):
            what.append("subjects")
        # 組分けの申告への答え（exam＝そのテストの日）。クラスが変わらなくても「答えた」と覚える。
        w = EX.placement_window(school, now, SOURCE.dept_of(a.get("level"), a.get("classId"))) if exam else None
        answered = bool(w and str(exam) == w["exam"]["date"])
        if not what:
            if answered and (a.get("placed") or {}).get("exam") != w["exam"]["date"]:
                a["placed"] = {"exam": w["exam"]["date"], "at": now, "same": True}
                T.save_accounts(school, db)
                T.audit(school, lid, "placed", lid, "%s 変わらない" % cid_name(tbl, cid))
            return []
        log = [x for x in (a.get("placements") or []) if isinstance(x, dict)]
        if by == "self" and len([x for x in log if x.get("by") == "self" and now - int(x.get("at") or 0) < 86400]) >= PLACEMENT_PER_DAY:
            raise JoinError("きょうは変更が多すぎます。あした、もう一度お願いします。", 429)
        was = "%s %s" % (cid_name(tbl, a.get("classId")), subj_text(a.get("subjects"), a.get("level")))
        if cid != (a.get("classId") or ""):
            # 前のクラスを残す（クラス替えと同じ形）。前のクラスの成績の表からは、出ていった生徒として外れる。
            seat0 = T.seat_of(a)
            a.setdefault("moves", []).append({"at": now, "by": by, "from": {"classId": a.get("classId") or "", "seat": seat0},
                                              "to": {"classId": cid, "seat": seat0}})
            a["moves"] = a["moves"][-40:]
        a["level"], a["classId"], a["subjects"] = g, cid, subs
        a.pop("needClass", None)                 # 新しい学年のクラスに答えた
        a.pop("grad", None)                      # 卒業の印は、クラスを選び直したら外れる（まちがいの直し）
        if not re.match(r"^[a-z]-\d+$", str(a.get("seat") or "")):
            # 前の形の口座（呼び名が番号）は、行き先のクラスで空いている番号にする
            a["seat"] = T.free_seat(db, cid, a.get("seat"), me=lid)
        log.append({"at": now, "by": by, "what": what})
        a["placements"] = log[-20:]
        a.pop("declared", None)
        if answered:
            a["placed"] = {"exam": w["exam"]["date"], "at": now, "same": False}
        T.save_accounts(school, db)
        T.leave_open_homework(school, [lid], now)
        T.join_open_homework(school, [lid], now)
        now_txt = "%s %s" % (cid_name(tbl, cid), subj_text(subs, g))
    T.audit(school, lid if by == "self" else by, "placement", lid, "%s → %s" % (was, now_txt))
    return what


def place_ask(T, school, a, now=None):
    """この生徒に、いま「組分けの結果、クラスは？」を聞くか。聞くなら {exam, name, toDay}、聞かないなら None。

    聞かないのは：聞く時期でない／もう答えた／結果が出たあとに登録した（登録のときに選んでいる）／
    その学年にクラスが1つしかない。
    """
    if a.get("role") != "student" or a.get("leftAt") or a.get("grad"):
        return None
    if a.get("needClass") and not a.get("classId"):
        # 学年が上がって、行き先のクラスが決まらなかった（小6→中1）。答えるまで聞く。
        return {"year": str(a["needClass"]), "exam": "", "name": "", "toDay": ""}
    w = EX.placement_window(school, now, SOURCE.dept_of(a.get("level"), a.get("classId")))
    if not w:
        return None
    if (a.get("placed") or {}).get("exam") == w["exam"]["date"]:
        return None
    if int(a.get("created") or 0) >= w["from"]:
        return None
    g = a.get("level") or ""
    if len([c for c in T.class_table(school).values() if (c.get("grade") or "") == g]) < 2:
        return None
    return {"exam": w["exam"]["date"], "name": w["exam"]["name"], "toDay": w["toDay"]}


def cid_name(tbl, cid):
    return (tbl.get(cid) or {}).get("name") or (cid or "")


def subj_text(subs, grade=""):
    jp = {"japanese": "国", "math": "算" if str(grade).startswith("e") else "数", "english": "英", "science": "理", "social": "社"}
    return "".join(jp.get(x, "") for x in (subs or []))


def finish(T, d, ip):
    """合言葉を確かめる値を置き、在籍の生徒にする。1つでもおかしければ何も変えない。"""
    items = d.get("items")
    if not isinstance(items, list) or not (1 <= len(items) <= JOIN_MAX_STUDENTS):
        raise JoinError("形が違います。")
    if not _allow("fin", ip, 30, 900):
        raise JoinError("回数が多すぎます。少し待ってから、もう一度お試しください。", 429)
    plan = []
    for it in items:
        if not isinstance(it, dict):
            raise JoinError("形が違います。")
        lid = str(it.get("id") or "").strip().lower()[:32]
        school = paths.school_of_login(lid) if T.SAFE_ID.match(lid) else None
        if not school:
            raise JoinError("登録の途中で時間がたちました。はじめから、もう一度お願いします。", 410)
        try:
            ver = T.clean_verifier(it.get("verifier"))
        except ValueError as e:
            raise JoinError(str(e))
        plan.append((school, lid, str(it.get("setup") or ""), ver))
    schools = sorted(set(p[0] for p in plan))
    if len(schools) != 1:
        raise JoinError("形が違います。")
    school = schools[0]
    now = time.time()
    with T.LOCK:
        db = T.accounts(school)
        for _sc, lid, setup, _ver in plan:
            a = db.get(lid) or {}
            pend = a.get("pending") or {}
            key = hashlib.sha256(setup.encode("utf-8")).hexdigest()
            if a.get("role") != "seat" or not pend or now > int(pend.get("exp") or 0) \
                    or not hmac.compare_digest(str(pend.get("key") or ""), key):
                raise JoinError("登録の途中で時間がたちました。はじめから、もう一度お願いします。", 410)
        for _sc, lid, _setup, ver in plan:
            a = db[lid]
            a.update(ver)
            a.pop("pending", None)
            a["pwAt"] = int(now)
            T.activate_seat(db, lid, by="join")
            a["seat"] = lid                              # 呼び名は ID そのもの（番号を振り直さない）
        T.save_accounts(school, db)
        ids = [p[1] for p in plan]
        T.join_open_homework(school, ids)                # いま出ている宿題（期限前）に足す
    tbl = T.class_table(school)
    for lid in ids:
        a = db[lid]
        T.audit(school, lid, "join_done", lid, "%s %s" % (cid_name(tbl, a.get("classId")), subj_text(a.get("subjects"), a.get("level"))))
    return {"ok": True, "ids": ids}
