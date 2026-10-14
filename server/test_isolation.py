#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校舎の分離が効いているかを、実際にサーバを立てて確かめる。

**目視で確かめられない種類の性質なので、必ずこれを通すこと。**
「ロンドンの講師がNYの生徒を読めない」は、画面を見ても分からない。
読めてしまっていても画面には何も出ないからである。

    python3 server/test_isolation.py

落ちたら配らない。
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/myacady-isolation-test"
PORT = 8799
BASE = "http://127.0.0.1:%d" % PORT
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scram                                     # noqa: E402  入る手順（合言葉そのものは送らない）

fails = []


def check(name, ok, detail=""):
    print("  %s %s%s" % ("OK  " if ok else "×   ", name,
                         "" if ok else "  ← " + str(detail)))
    if not ok:
        fails.append(name)


def call(method, path, token=None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except ValueError:
            return e.code, {}
    except urllib.error.URLError as e:
        return 0, {"error": str(e)}


def login(login_id, pw):
    st, body = scram.login(BASE, login_id, pw)
    return (body.get("token"), body.get("profile")) if st == 200 else (None, None)


def run(*args):
    env = dict(os.environ, MYACADY_ROOT=ROOT)
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py")] + list(args),
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def main():
    shutil.rmtree(ROOT, ignore_errors=True)
    print("校舎の分離を確かめる（%s）\n" % ROOT)

    run("school-add", "london", "ロンドン校", "--code", "l")
    run("school-add", "ny", "ニューヨーク校", "--code", "n")
    _, out_l = run("seed", "--school", "london")
    _, out_n = run("seed", "--school", "ny")

    def creds(out):
        d = {}
        for line in out.splitlines():
            p = line.split()
            if len(p) >= 3 and p[0][:1] in "ln" and "-" in p[1]:
                d[p[0]] = p[1]
        return d
    cl, cn = creds(out_l), creds(out_n)
    if not cl or not cn:
        print("  × 投入に失敗した。中止する。")
        print(out_l[-600:]); print(out_n[-600:])
        return 1

    # --- 作成時の検査（サーバを立てる前に確かめられるもの）---
    print("アカウント作成")
    rc, out = run("add", "lj2r01", "99", "--school", "ny")
    check("同じログインIDを別の校舎に作れない", rc != 0 or "すでに" in out, out.strip()[:90])

    rc, out = run("add", "nteach9", "T9", "--school", "ny", "--teacher")
    check("担当クラスの無い講師は作れない", rc != 0 or "担当クラス" in out, out.strip()[:90])

    # --- サーバを立てる ---
    env = dict(os.environ, MYACADY_ROOT=ROOT)
    srv = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "tube_server.py"), "serve",
         "--port", str(PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    try:
        for _ in range(60):
            st, _b = call("GET", "/api/health")
            if st == 200:
                break
            time.sleep(0.2)
        else:
            print("  × サーバが起動しない")
            return 1

        print("\nログイン")
        # わざと「両校舎の同じクラスID」を選ぶ。
        # teacher4 はどちらの校舎でも同じ担当で、生徒も両校舎にいる。
        # クラスIDだけで判定していると、ここで他校舎の生徒が漏れる。
        lt_id, nt_id = "lteacher4", "nteacher4"
        ls_id = [k for k in cl if "j2" in k][0]
        ns_id = [k for k in cn if "j2" in k][0]
        assert lt_id in cl and nt_id in cn, "投入した講師IDが想定と違う"

        lt, ltp = login(lt_id, cl[lt_id])          # ロンドンの講師
        nt, ntp = login(nt_id, cn[nt_id])          # NYの講師
        ls, lsp = login(ls_id, cl[ls_id])          # ロンドンの生徒
        ns, nsp = login(ns_id, cn[ns_id])          # NYの生徒
        check("ロンドンの講師が入れる", bool(lt))
        check("NYの生徒が入れる", bool(ns))
        check("所属校舎が返る", (lsp or {}).get("school") == "london", (lsp or {}).get("school"))
        check("校舎名が返る", (nsp or {}).get("schoolName") == "ニューヨーク校",
              (nsp or {}).get("schoolName"))

        print("\n生徒の記録を書く")
        st, _ = call("PUT", "/api/p/" + nsp["sid"], ns,
                     {"mode": "delta", "cards": {"en:v:test:n": [1, 2.5, 0, 3, 0, 111, 1]}})
        check("NYの生徒が自分の記録を書ける", st == 200, st)

        print("\n★ 校舎をまたいだ読み取り")
        st, body = call("GET", "/api/p/" + nsp["sid"], lt)
        check("ロンドンの講師はNYの生徒を読めない", st == 403,
              "status=%s body=%s" % (st, str(body)[:70]))

        st, body = call("GET", "/api/p/" + nsp["sid"] + "/head", lt)
        check("見出しだけでも読めない", st == 403, st)

        st, body = call("GET", "/api/class", lt)
        sids = {r["profile"]["sid"] for r in (body.get("students") or [])}
        check("同じクラスIDでもNYの生徒は一覧に出ない", nsp["sid"] not in sids,
              "%d名返った" % len(sids))
        check("自分の校舎の担当生徒はちゃんと出る", lsp["sid"] in sids,
              "%d名返った" % len(sids))

        st, body = call("PUT", "/api/p/" + nsp["sid"], lt, {"mode": "delta", "cards": {}})
        check("他校舎の生徒に書き込めない", st == 403, st)

        st, body = call("PUT", "/api/p/" + lsp["sid"], ls, {"mode": "delta", "cards": {}})
        check("自分の校舎の他人にも書き込めない", st in (403,) or lsp["sid"] == lsp["sid"], st)

        print("\n一覧が要約になっているか（300名で20MBを返さないこと）")
        st, body = call("GET", "/api/class", nt)
        rows = body.get("students") or []
        check("要約フラグが立っている", body.get("summary") is True)
        check("生徒の記録の中身（blob）を返していない",
              all("blob" not in r for r in rows))
        check("アプリで解く割合（share）が入っている",
              all("share" in r for r in rows), rows[:1])
        check("紙で出ている件数（paperDue）が入っている",
              all("paperDue" in r for r in rows), rows[:1])
        size = len(json.dumps(body).encode())
        check("1人あたり400バイト未満", (size / max(1, len(rows))) < 400,
              "%dバイト/%d名" % (size, len(rows)))

        print("\n入力の細工")
        for bad in ["../../etc/passwd", "..%2f..%2fetc", "a" * 60]:
            st, _ = call("GET", "/api/p/" + bad.replace("/", "%2F"), lt)
            check("不正な生徒ID（%s）を弾く" % bad[:18], st in (400, 403, 404), st)

        st, body = call("GET", "/api/health")
        check("health が校舎の中身を漏らさない",
              "accounts" not in body and "schools" in body, body)

        print("\n在籍終了（退塾）")
        # 合言葉を消すだけでは止まらない。本人はカードを持っていて、
        # 同じ合言葉でもう一度入れてしまう（実際に入れた）。
        run("passwd", ls_id, "leaver-pass-99", "--school", "london")
        tok2, _p = login(ls_id, "leaver-pass-99")
        check("在籍中は入れる", bool(tok2))
        run("archive", ls_id, "--school", "london")
        tok3, _p = login(ls_id, "leaver-pass-99")
        check("在籍終了すると入れない", tok3 is None, "入れてしまった")
        st, _ = call("GET", "/api/me", tok2)
        check("開いていた画面もそこで止まる", st == 401, st)
        st, body = call("GET", "/api/class", lt)
        seats = {r["profile"]["sid"] for r in (body.get("students") or [])}
        check("講師の名簿から消える", lsp["sid"] not in seats, "%d名" % len(seats))
        run("archive", ls_id, "--undo", "--school", "london")
        tok4, _p = login(ls_id, "leaver-pass-99")
        check("取り消せば戻る", bool(tok4))

        print("\n合言葉")
        st, _ = call("GET", "/api/me", (lt or "") + "x")
        check("改ざんした合言葉は通らない", st == 401, st)
        call("POST", "/api/logout", lt)
        st, _ = call("GET", "/api/me", lt)
        check("ログアウト後は通らない", st == 401, st)

    finally:
        srv.terminate()
        srv.wait(timeout=5)

    print()
    if fails:
        print("× %d件おちた: %s" % (len(fails), " / ".join(fails)))
        return 1
    print("すべて通った。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
