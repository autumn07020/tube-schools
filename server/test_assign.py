#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""担当（クラス × 教科）が正しく効いているかを確かめる。

なぜこの検査が要るか
--------------------
講師は学年をまるごと持たない。**あるクラスのある1教科だけ**を持つ。
たとえば「中2R 英語」の講師に、中2R の数学の宿題や、
中2（合同）の記録が見えてはいけない。

権限は画面ではなくサーバで決まる。画面を直しても、APIが緩ければ
意味がない。ここではAPIだけを直接叩いて確かめる。

    python3 server/test_assign.py
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/test-assign"


def free_port():
    """空いている口を借りる。

    番号を決め打ちにしていたら、**前の検査の残りが居座っていて**、
    別のサーバに話しかけていた。返ってきた 501 を「実装漏れ」と
    読み違えるところだった。毎回OSに空きを聞く。
    """
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    n = s.getsockname()[1]
    s.close()
    return n


PORT = free_port()
BASE = "http://127.0.0.1:%d" % PORT
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scram                                     # noqa: E402  入る手順（合言葉そのものは送らない）

ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   %s" % name)
    else:
        ng_n += 1
        print("  ×    %s  %s" % (name, detail))


def call(method, path, token=None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
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


def main():
    import shutil
    shutil.rmtree(ROOT, ignore_errors=True)
    env = dict(os.environ, MYACADY_ROOT=ROOT)
    subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"),
                    "seed", "--school", "london", "--name", "ロンドン校"],
                   env=env, capture_output=True, check=True)

    # 担当のはっきりした講師を2人作る
    subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"),
                    "add", "eigo", "T90", "--teacher", "--school", "london",
                    "--assign", "j2r:english", "--password", "eigo-pass"],
                   env=env, capture_output=True, check=True)
    subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"),
                    "add", "suugaku", "T91", "--teacher", "--school", "london",
                    "--assign", "j2r:math", "--password", "suugaku-pass"],
                   env=env, capture_output=True, check=True)

    srv = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "tube_server.py"), "serve",
         "--port", str(PORT)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        up = False
        for _ in range(60):
            if srv.poll() is not None:
                break                       # 落ちた
            try:
                urllib.request.urlopen(BASE + "/api/health", timeout=1)
                up = True
                break
            except Exception:
                time.sleep(0.25)
        if not up:
            print("  ×    サーバが起動しませんでした（port %d）" % PORT)
            return 1

        st, b = scram.login(BASE, "eigo", "eigo-pass")
        eigo = b.get("token")
        st, b = scram.login(BASE, "suugaku", "suugaku-pass")
        suugaku = b.get("token")
        check("担当を指定した講師が入れる", bool(eigo and suugaku))

        print("\n担当のとおりに宿題が分かれるか")
        # 英語の先生が中2Rに英語の宿題を出す
        st, b = call("POST", "/api/assignments", eigo, {
            "title": "英語の宿題", "source": "myvocab", "from": 1, "to": 10,
            "classId": "j2r", "students": [],
            "dueAt": int((time.time() + 7 * 86400) * 1000),
            "lesson": {"key": "j2:english", "n": 1}})
        check("英語の先生が英語の宿題を出せる", st == 200, st)
        eigo_id = (b.get("assignment") or {}).get("id") or b.get("id")

        # 数学の先生が同じクラスに数学の宿題を出す
        st, b = call("POST", "/api/assignments", suugaku, {
            "title": "数学の宿題", "source": "keisan", "from": 1, "to": 10,
            "classId": "j2r", "students": [],
            "dueAt": int((time.time() + 7 * 86400) * 1000),
            "lesson": {"key": "j2:math", "n": 1}})
        check("数学の先生が数学の宿題を出せる", st == 200, st)

        # 一覧に、自分の教科だけが出るか
        st, b = call("GET", "/api/assignments", eigo)
        titles = [a["title"] for a in (b.get("assignments") or [])]
        check("英語の先生に英語の宿題が見える", "英語の宿題" in titles, titles)
        check("英語の先生に**数学の宿題は見えない**",
              "数学の宿題" not in titles, titles)

        st, b = call("GET", "/api/assignments", suugaku)
        titles = [a["title"] for a in (b.get("assignments") or [])]
        check("数学の先生に数学の宿題が見える", "数学の宿題" in titles, titles)
        check("数学の先生に**英語の宿題は見えない**",
              "英語の宿題" not in titles, titles)

        print("\n担当外は書き換えられないか")
        if eigo_id:
            st, _ = call("DELETE", "/api/assignments/" + eigo_id, suugaku)
            check("数学の先生は英語の宿題を消せない", st in (403, 404), st)

        print("\n格子に担当だけが出るか")
        st, b = call("GET", "/api/lessons/grid", eigo)
        keys = []
        for row in (b.get("grid") or {}).get("grid", []):
            for c in row.get("cells", []):
                if c.get("state") != "off":
                    keys.append(c.get("key"))
        check("格子に英語だけが出る",
              all(k.endswith(":english") for k in keys) if keys else True, keys)

        print("\n成績・今日やることは、過ぎた回を出してから読むか")
        # 出すのが格子だけだと、成績の「次の授業」が過ぎた日を指した（2026-10-07）
        today = time.strftime("%Y-%m-%d")
        st, _ = call("GET", "/api/today", eigo)
        check("今日やることが読める", st == 200, st)
        st, b = call("GET", "/api/insight/overview", eigo)
        check("成績の一覧が読める", st == 200, st)
        for c in (b.get("courses") or []):
            st, d = call("GET", "/api/insight/course?key=" + c.get("key", ""), eigo)
            nd = (d.get("next") or {}).get("date") or ""
            check("%s：次の授業は今日以降（%s）" % (c.get("key"), nd or "―"),
                  st == 200 and (not nd or nd >= today), (st, nd))

        print("\n担当外の学年は触れないか")
        st, _ = call("PUT", "/api/curriculum/done", eigo,
                     {"key": "j3:english", "unit": "テスト"})
        check("担当していない学年は弾かれる", st == 403, st)
        st, _ = call("PUT", "/api/curriculum/done", eigo,
                     {"key": "j2:math", "unit": "テスト"})
        check("同じ学年でも担当外の教科は弾かれる", st == 403, st)

        print("\n名簿は担当クラスだけか")
        st, b = call("GET", "/api/class", eigo)
        cls = {r["profile"]["classId"] for r in (b.get("students") or [])}
        check("担当クラスの生徒だけが返る", cls <= {"j2r"}, cls)

    finally:
        srv.terminate()
        srv.wait(timeout=5)

    print()
    if ng_n:
        print("× %d件おちた" % ng_n)
        return 1
    print("すべて通った。（%d件）" % ok_n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
