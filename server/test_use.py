#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""コースの導入の段階（courses.use_level）が決めたとおりに効いているかを確かめる。

なぜこの検査が要るか
--------------------
スロースタート・部分導入では、コースごとに「紙のまま／宿題を出す／写真で提出／添削まで／毎日テストまで」が
混ざる。段階が静かにずれると、**写真を使わないはずのコースに写真が届く／添削を使わないのに返せる／
生徒の画面に毎日テストが出る** という形で壊れ、見た目では分からない。決めごとをそのまま確かめる。

  ・段階は 0〜4。印の無い古いコースは 4（動いているものを止めない）、app False は 0
  ・set_app（前からの口）は段階と食い違わない（使う＝前の段階か 4、使わない＝0）
  ・PUT /api/lessons/use は担当のコースだけ。まとめて（keys）も1件（key）も同じ
  ・生徒の /api/me に useBySubject が届く
  ・段階 1 のコースに写真を出すと 400。段階 2 なら通る
  ・段階 2 のコースに添削を返すと 400。段階 3 なら通る
  ・時間割（assign）のコマに use が乗る

    python3 server/test_use.py
"""
import base64
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
ROOT = "/tmp/test-use"
os.environ["MYACADY_ROOT"] = ROOT
os.environ["TZ"] = "Europe/London"
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


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def png():
    """1×1 の PNG。"""
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def setup():
    paths.ensure_school(SCHOOL)
    paths.save(paths.school_file(SCHOOL, "school.json"),
               {"id": SCHOOL, "name": "検査校", "code": "l", "tz": "Europe/London"})
    paths.save(paths.school_file(SCHOOL, "curriculum.json"), {"v": 2, "classes": [
        {"id": "j2r", "name": "中2R", "grade": "j2"}, {"id": "j3r", "name": "中3R", "grade": "j3"}]})
    mk = T.add_account
    mk(SCHOOL, "lj2r01", "student-pass", "01", "student", "j2", "j2r")
    db = T.accounts(SCHOOL)
    db["lj2r01"]["subjects"] = C.parse_subjects("国数英")
    T.save_accounts(SCHOOL, db)
    for lid in ("t-a", "t-b"):
        mk(SCHOOL, lid, lid + "-pass", "T1", "teacher", "j2", "j2r", classes=["j2r"])
        db = T.accounts(SCHOOL)
        db[lid]["assign"] = []
        T.save_accounts(SCHOOL, db)
    ta = T.accounts(SCHOOL)["t-a"]["sid"]
    rows = []
    for cid, sub, name in (("j2r", "math", "中2R 数学"), ("j2r", "japanese", "中2R 国語"), ("j2r", "english", "中2R 英語")):
        rows.append(("%s:%s" % (cid, sub), {"name": name, "grade": "j2", "subject": sub, "teachers": [ta],
                                             "slots": [{"day": 2, "start": "16:40", "end": "18:10"}],
                                             "classes": [cid], "students": [], "unit": "lesson", "weekday": 0,
                                             "from": "", "to": ""}))
    C.upsert(SCHOOL, rows)


def unit_checks():
    print("段階の読み方")
    check("印の無いコースは 4", C.use_level({"teachers": []}) == 4)
    check("app False は 0（段階が書いてあっても）", C.use_level({"teachers": [], "app": False, "use": 3}) == 0)
    check("use 2 は 2", C.use_level({"teachers": [], "app": True, "use": 2}) == 2)
    check("True は段階ではない（bool を弾く）", C.use_level({"teachers": [], "app": True, "use": True}) == 4)
    f = C.use_flags({"teachers": [], "app": True, "use": 2})
    check("段階 2 の印：宿題○ 写真○ 添削× 毎日テスト×", f == {"hw": True, "photo": True, "correct": False, "quiz": False}, f)
    L.set_use(SCHOOL, "j2r:math", 1, "test")
    p = L.plan(SCHOOL, "j2r:math")
    check("set_use 1 → use 1・app True", p.get("use") == 1 and p.get("app") is True, (p.get("use"), p.get("app")))
    L.set_app(SCHOOL, "j2r:math", False, "test")
    p = L.plan(SCHOOL, "j2r:math")
    check("set_app 使わない → 0", C.use_level(p) == 0 and p.get("app") is False)
    L.set_app(SCHOOL, "j2r:math", True, "test")
    p = L.plan(SCHOOL, "j2r:math")
    check("set_app 使う → 前の段階（1）に戻る", C.use_level(p) == 1, C.use_level(p))
    L.set_use(SCHOOL, "j2r:math", 2, "test")
    L.set_app(SCHOOL, "j2r:math", False, "test")
    L.set_app(SCHOOL, "j2r:math", True, "test")
    check("段階 2 → 使わない → 使う で 2 に戻る", C.use_level(L.plan(SCHOOL, "j2r:math")) == 2)
    try:
        L.set_use(SCHOOL, "j2r:math", 5, "test")
        check("5 は弾く", False)
    except ValueError:
        check("5 は弾く", True)
    ta = dict(T.accounts(SCHOOL)["t-a"], school=SCHOOL)
    slots = T.teacher_slots(ta)
    check("時間割のコマに use が乗る", all(isinstance(s.get("use"), int) for s in slots), slots[:1])


def server_checks():
    print("\nサーバ")
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
    srv = subprocess.Popen([sys.executable, os.path.join(HERE, "tube_server.py"), "serve", "--port", str(port)],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=1)
                break
            except Exception:
                time.sleep(0.25)

        def login(lid, pw):
            import scram
            st, b = scram.login(base, lid, pw)
            return b.get("token")

        ta, tb, stu = login("t-a", "t-a-pass"), login("t-b", "t-b-pass"), login("lj2r01", "student-pass")
        check("講師2人と生徒が入れる", all([ta, tb, stu]))

        st, b = call("PUT", "/api/lessons/use", ta, {"keys": ["j2r:math", "j2r:japanese"], "level": 1})
        check("まとめて段階 1 にできる", st == 200 and b.get("use") == {"j2r:math": 1, "j2r:japanese": 1}, (st, b))
        check("返事の assign に use が乗る", any(s.get("use") == 1 for s in (b.get("assign") or [])), b.get("assign"))
        st, b = call("PUT", "/api/lessons/use", ta, {"key": "j2r:english", "level": 3})
        check("1件でも同じ口", st == 200 and b.get("use") == {"j2r:english": 3}, (st, b))
        st, b = call("PUT", "/api/lessons/use", tb, {"key": "j2r:math", "level": 4})
        check("担当していない講師は変えられない", st == 403, st)
        st, b = call("PUT", "/api/lessons/use", ta, {"key": "j2r:math", "level": 9})
        check("段階の範囲外は 400", st == 400, st)
        st, b = call("PUT", "/api/lessons/use", ta, {"keys": ["j2r:math", "j9x:math"], "level": 2})
        check("知らないコースが混ざると何も変えない", st == 403 and C.use_level(L.plan(SCHOOL, "j2r:math")) == 1, (st, C.use_level(L.plan(SCHOOL, "j2r:math"))))

        st, b = call("GET", "/api/me", stu)
        prof = b.get("profile") or {}
        check("生徒の /api/me に useBySubject", prof.get("useBySubject") == {"japanese": 1, "math": 1, "english": 3}, prof.get("useBySubject"))
        check("appSubjects は段階 1 以上の教科", sorted(prof.get("appSubjects") or []) == ["english", "japanese", "math"], prof.get("appSubjects"))

        # 宿題を1件、コースから出た形で置く（lesson.key で段階を引く）
        sid = T.accounts(SCHOOL)["lj2r01"]["sid"]
        asg = T.assignments(SCHOOL)
        now = int(time.time() * 1000)
        for aid, key in (("hw-math", "j2r:math"), ("hw-eng", "j2r:english")):
            asg[aid] = {"id": aid, "title": "p.1-2", "classId": "j2r", "subject": key.split(":")[1], "route": "paper",
                        "graded": True, "students": [sid], "assignedAt": now, "dueAt": now + 86400000,
                        "lesson": {"key": key, "n": 1}}
        T.save_assignments(SCHOOL, asg)
        body = {"files": [{"type": "image/png", "b64": base64.b64encode(png()).decode()}]}
        st, b = call("POST", "/api/submissions/hw-math", stu, body)
        check("段階 1 のコースに写真は出せない（400）", st == 400, (st, b))
        st, b = call("POST", "/api/submissions/hw-eng", stu, body)
        check("段階 3 のコースには出せる", st == 200, (st, b))
        st, b = call("PUT", "/api/lessons/use", ta, {"key": "j2r:math", "level": 2})
        st, b = call("POST", "/api/submissions/hw-math", stu, body)
        check("段階 2 に上げると出せる", st == 200, (st, b))
        st, b = call("POST", "/api/submissions/hw-math/%s/return" % sid, ta, dict(body, note="よく書けています"))
        check("段階 2 のコースに添削は返せない（400）", st == 400, (st, b))
        st, b = call("POST", "/api/submissions/hw-math/%s/scan" % sid, ta, body)
        check("取り込み（scan）は段階 2 でも通る", st == 200, (st, b))
        st, b = call("POST", "/api/submissions/hw-eng/%s/return" % sid, ta, dict(body, note="よく書けています"))
        check("段階 3 のコースには添削を返せる", st == 200, (st, b))
        st, b = call("GET", "/api/me", stu)
        check("段階を上げた分が生徒に届く", ((b.get("profile") or {}).get("useBySubject") or {}).get("math") == 2, b.get("profile"))
    finally:
        srv.terminate()
        srv.wait(timeout=5)


def main():
    setup()
    unit_checks()
    server_checks()
    print()
    if ng_n:
        print("× %d件 失敗（%d件 通過）" % (ng_n, ok_n))
        sys.exit(1)
    print("すべて通った。（%d件）" % ok_n)


if __name__ == "__main__":
    main()
