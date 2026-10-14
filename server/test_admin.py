#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""席・管理者・管理の口・報告と、「隙間」（同時に来たとき・途中で変わったとき）を確かめる。

なぜこの検査が要るか
--------------------
お金をいただいて運用する。ID と合言葉を配り、管理ページから足し引きする。ここが張りぼてだと、
  ・渡していない30席が名簿や提出率に幽霊として並ぶ
  ・合言葉を作り直したのに、前の合言葉で入ったままの画面が生きている
  ・同時に押した2つの操作の片方が、もう片方を消す
  ・管理者が答案を読める／講師が席を消せる
という形で壊れる。決めごとを1つずつ確かめる。

  1. 合言葉のそろえ方（大文字・全角・線なしでも同じ）と作り方（3語・4語・5語＋4桁）
  2. サーバに届くのはハッシュだけ（accounts.json に合言葉が無い）
  3. 席（seat）は名簿にも宿題の受け取り手にも出ない。はじめて入ると生徒になる
  4. 管理の口は管理者だけ。管理者は講師・生徒の口に入れない
  5. 合言葉の作り直し・在籍終了は、開いていた画面をその場で閉じる
  6. 隙間：同時のログイン（上限が効く）・照合の途中の作り直し（古いほうが勝たない）・
     同時に足す（消えない）・コマンドとサーバ（消えない）
  7. 報告が届き、まとまり、済みにできる
  8. http で来た人は https へ

    python3 server/test_admin.py
"""
import functools
import hashlib
import importlib.util
import json
import re
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/test-admin"
os.environ["MYACADY_ROOT"] = ROOT
os.environ["MYACADY_FSYNC"] = "0"
os.environ["TZ"] = "Europe/London"
time.tzset()
sys.path.insert(0, HERE)
shutil.rmtree(ROOT, ignore_errors=True)

import paths                                     # noqa: E402
import lessons as L                              # noqa: E402
import courses as C                              # noqa: E402
import admin as A                                # noqa: E402
import scram                                     # noqa: E402
import tube_server as T                          # noqa: E402

SCHOOL, OTHER = "real", "other"
ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   %s" % name)
    else:
        ng_n += 1
        print("  ×    %s  %s" % (name, detail))


def verifier(pw):
    """管理ページや手元の道具が作って届ける値（合言葉そのものは入らない）。"""
    return scram.make_verifier(pw)


def old_verifier(pw):
    """09-30 の束（v1）の形。hash は SaltedPassword。"""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", T.norm_pw(pw).encode("utf-8"), bytes.fromhex(salt), 600000)
    return {"alg": "pbkdf2-600k", "salt": salt, "hash": dk.hex()}


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def setup():
    for sc, code in ((SCHOOL, "w"), (OTHER, "x")):
        paths.ensure_school(sc)
        paths.save(paths.school_file(sc, "school.json"),
                   {"id": sc, "name": "検査校" + code, "code": code, "tz": "Europe/London"})
        paths.save(paths.school_file(sc, "curriculum.json"), {"v": 2, "classes": [
            {"id": "e4a", "name": "小4α", "grade": "e4"}, {"id": "e4b", "name": "小4β", "grade": "e4"}]})
    T.add_account(SCHOOL, "wadmin01", "kanri-kanri-kanri-0001", "A01", "admin", "", "")
    T.add_account(OTHER, "xadmin01", "yoso-yoso-yoso-0002", "A01", "admin", "", "")
    T.add_account(SCHOOL, "wt01", "sensei-pass-0001", "T01", "teacher", "", "", classes=["-"])
    T.add_account(SCHOOL, "we4a01", "neko-yama-sora-4821", "01", "student", "e4", "e4a")
    T.add_account(SCHOOL, "we4a02", None, "02", "seat", "e4", "e4a", verifier=verifier("kame-tori-umi-0002"))
    T.add_account(SCHOOL, "we4a03", None, "03", "seat", "e4", "e4a", verifier=verifier("inu-saru-kawa-0003"))
    T.add_account(OTHER, "xe4a01", "yoso-no-ko-0001", "01", "student", "e4", "e4a")
    ta = T.accounts(SCHOOL)["wt01"]["sid"]
    C.upsert(SCHOOL, [("e4a:math", {"name": "小4α 算数", "grade": "e4", "subject": "math", "teachers": [ta],
                                    "slots": [{"day": 3, "start": "18:20", "end": "19:50"}],
                                    "classes": ["e4a"], "students": [], "unit": "lesson", "weekday": 0,
                                    "from": "", "to": ""}),
                      ("e4b:japanese", {"name": "小4β 国語", "grade": "e4", "subject": "japanese", "teachers": [],
                                        "slots": [], "classes": ["e4b"], "students": [], "unit": "lesson",
                                        "weekday": 0, "from": "", "to": ""})])


def unit_checks():
    print("合言葉")
    same = ["neko-yama-sora-4821", "Neko-Yama-Sora-4821", "nekoyamasora4821", " neko yama sora 4821 ",
            "ｎｅｋｏ－ｙａｍａ－ｓｏｒａ－４８２１", "neko‐yama–sora—4821", "NEKO_YAMA_SORA_4821", "nekoーyamaーsoraー4821"]
    got = {T.norm_pw(x) for x in same}
    check("大文字・全角・線なし・空白でも同じ形にそろう", got == {"nekoyamasora4821"}, got)
    spec = importlib.util.spec_from_file_location("mk", os.path.join(os.path.dirname(HERE), "scripts", "accounts", "make.py"))
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    check("手元の道具（make.py）は、サーバと同じ計算（scram.py）を使う", mk.scram.make_verifier is scram.make_verifier and mk.scram.norm_pw is T.norm_pw)
    ws = T.pw_words()
    check("ことばは 256語・重なり無し・英小文字だけ", len(ws) == 256 and len(set(ws)) == 256 and all(w.isalpha() and w.islower() for w in ws), len(ws))
    import re
    for role, n in (("student", 3), ("teacher", 4), ("admin", 5)):
        pw = T.make_password(role)
        check("%s の合言葉は %d語＋4桁" % (role, n), bool(re.match(r"^([a-z]{3,8}-){%d}\d{4}$" % n, pw)), pw)
    check("毎回ちがう", len({T.make_password() for _ in range(50)}) == 50)
    print("\n入る手順の計算（合言葉そのものは送らない）")
    check("PBKDF2 の既知の値（RFC 6070 の SHA-256 版）",
          hashlib.pbkdf2_hmac("sha256", b"password", b"salt", 4096).hex() == "c5e478d59288c841aa530db6845c4c8d962893a001ce4e11a4963873aa98134a")
    v = verifier("Abc-Def 1234")
    au = scram.auth_message("we4a01", "nonce-1", v["salt"], v["iters"])
    pr = scram.client_proof(scram.salted("abcdef1234", v["salt"]), au)
    check("そろえた合言葉から作った証明が通る", scram.verify_proof(v["storedKey"], au, pr))
    check("違う合言葉の証明は通らない", not scram.verify_proof(v["storedKey"], au, scram.client_proof(scram.salted("abcdef1235", v["salt"]), au)))
    check("別の nonce には使えない（同じ証明をもう一度使えない）", not scram.verify_proof(v["storedKey"], scram.auth_message("we4a01", "nonce-2", v["salt"], v["iters"]), pr))
    check("別のIDには使えない", not scram.verify_proof(v["storedKey"], scram.auth_message("we4a02", "nonce-1", v["salt"], v["iters"]), pr))
    check("保存の値（storedKey）を証明として出しても通らない", not scram.verify_proof(v["storedKey"], au, v["storedKey"]))
    check("保存の値に、合言葉も SaltedPassword も入っていない", set(v) == {"alg", "salt", "iters", "storedKey", "serverKey"}
          and scram.salted("abcdef1234", v["salt"]).hex() not in json.dumps(v))
    ok = dict(v)
    for bad in ({}, dict(ok, salt="zz"), dict(ok, storedKey="0" * 63), dict(ok, alg="plain"), "x", None,
                dict(ok, serverKey="G" * 64), dict(ok, iters=1), dict(ok, iters=True), {k: ok[k] for k in ok if k != "iters"},
                {"alg": "pbkdf2-600k", "salt": "0" * 32, "hash": "0" * 64}):
        try:
            T.clean_verifier(bad)
            check("おかしなハッシュは弾く %r" % (bad,), False)
        except ValueError:
            check("おかしなハッシュは弾く", True)

    print("\n保存されているもの")
    raw = open(paths.school_file(SCHOOL, "accounts.json"), encoding="utf-8").read()
    check("accounts.json に合言葉が無い", not any(x in raw for x in ("neko", "kame-tori", "kanri", "sensei-pass", "password")))
    db = T.accounts(SCHOOL)
    check("口座にあるのは alg・salt・iters・storedKey・serverKey（hash は無い）",
          all(set(("alg", "salt", "iters", "storedKey", "serverKey")) <= set(a) and "hash" not in a and a["alg"] == "scram-sha256" for a in db.values()))

    print("\n席（まだ渡していない）")
    p = C.all_courses(SCHOOL)["e4a:math"]
    live = {a["sid"] for a in db.values() if a["role"] == "student"}
    check("宿題の受け取り手に、渡していない席は入らない", set(C.receivers(SCHOOL, p, db)) == live, C.receivers(SCHOOL, p, db))
    db2 = json.loads(json.dumps(db))
    check("使うと生徒になる", T.activate_seat(db2, "we4a02", "test") and db2["we4a02"]["role"] == "student" and db2["we4a02"]["usedAt"])
    check("使った席は受け取り手に入る", db2["we4a02"]["sid"] in C.receivers(SCHOOL, p, db2))
    check("生徒をもう一度「使う」にしても何も起きない", T.activate_seat(db2, "we4a01") is False)
    db3 = json.loads(json.dumps(db))
    db3["we4a01"]["seat"] = "03"       # クラス替えで来た子が、先に 03 番を使っている
    T.activate_seat(db3, "we4a03")
    seats3 = [a["seat"] for a in db3.values() if a["role"] == "student" and a["classId"] == "e4a"]
    check("番号が重なる席は、空いている番号になる（同じ番号が2人にならない）", db3["we4a03"]["seat"] != "03" and len(seats3) == len(set(seats3)), seats3)

    print("\n鍵（スレッドとプロセス）")
    with T.LOCK:
        with T.LOCK:
            check("同じスレッドは重ねて入れる", True)
    code = ("import os,sys,time;os.environ['MYACADY_ROOT']=%r;sys.path.insert(0,%r);import paths\n"
            "with paths.GUARD:\n print('in',flush=True);time.sleep(0.8)\n" % (ROOT, HERE))
    pr = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE)
    pr.stdout.readline()
    t0 = time.time()
    with T.LOCK:
        waited = time.time() - t0
    pr.wait()
    check("別のプロセスが持っているあいだは待つ", waited > 0.4, "%.2f秒" % waited)

    errs = []

    def adder(i):
        try:
            T.add_account(SCHOOL, "wrace%02d" % i, "race-pass-%04d" % i, "%02d" % (40 + i), "seat", "e4", "e4b")
        except Exception as e:                      # noqa: BLE001
            errs.append(e)
    ths = [threading.Thread(target=adder, args=(i,)) for i in range(16)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    db = T.accounts(SCHOOL)
    check("16本が同時に足しても、1件も消えない", not errs and all("wrace%02d" % i in db for i in range(16)), errs[:1])
    check("索引にも全部ある", all(paths.school_of_login("wrace%02d" % i) == SCHOOL for i in range(16)))
    check("sid は重ならない", len({a["sid"] for a in db.values()}) == len(db))
    try:
        T.add_account(OTHER, "we4a01", "yoso-yoso-0009", "09", "student", "e4", "e4a")
        check("ほかの校舎で使っているIDは作れない", False)
    except ValueError:
        check("ほかの校舎で使っているIDは作れない", True)
    with T.LOCK:
        db = T.accounts(SCHOOL)
        for i in range(16):
            db.pop("wrace%02d" % i, None)
            paths.unbind_login("wrace%02d" % i)
        T.save_accounts(SCHOOL, db)

    print("\n束（手元で作ったものを入れる）")
    accs = [dict(verifier("taba-no-seki-%04d" % i), id="we4b%02d" % i, role="seat", seat="%02d" % i, classId="e4b", level="e4")
            for i in (1, 2)]
    accs.append(dict(old_verifier("taba-no-sensei-0001"), id="wt02", role="teacher", seat="T02", classId="", level=""))
    bundle = {"kind": "tubestudy-accounts", "v": 1, "school": {"id": SCHOOL, "name": "検査校w", "code": "w"},
              "accounts": accs,
              "courses": [["e4b:math", {"name": "小4β 算数", "grade": "e4", "subject": "math", "teachers": [], "slots": [],
                                        "classes": ["e4b"], "students": [], "unit": "lesson", "weekday": 0, "from": "", "to": ""}],
                          ["e4a:math", {"name": "上書きしてはいけない", "grade": "e4", "subject": "math", "teachers": [],
                                        "slots": [], "classes": ["e4a"], "students": [], "unit": "lesson", "weekday": 0,
                                        "from": "", "to": ""}]]}
    lines = []
    A.import_bundle(T, bundle, yes=False, out=lines.append)
    check("--yes が無ければ何も入れない", "we4b01" not in T.accounts(SCHOOL))
    rc0 = A.import_bundle(T, bundle, yes=True, out=lines.append)
    db = T.accounts(SCHOOL)
    check("ぜんぶ入れば 0 を返す", rc0 == 0, rc0)
    rc1 = A.import_bundle(T, dict(bundle, courses=[["e9z:math", dict(bundle["courses"][0][1], classes=["e9z"])]]), yes=True, out=lines.append)
    check("入らないものが1つでもあれば、失敗として返す（反映の道具が気づける）", rc1 == 1 and "e9z:math" not in C.all_courses(SCHOOL) and any("入らなかったもの" in x for x in lines), (rc1, lines[-2:]))
    check("束の席と講師が入る", db.get("we4b01", {}).get("role") == "seat" and db.get("wt02", {}).get("role") == "teacher")
    check("束の講師はコースだけを持つ（assign が空の配列）", db["wt02"].get("assign") == [] and db["wt02"].get("classes") == [])
    check("09-30 の束の形（hash つき）で届いても、新しい形に直して入れる（hash は残さない）",
          db["wt02"]["alg"] == "scram-sha256" and "hash" not in db["wt02"] and db["wt02"]["storedKey"]
          and scram.verify_proof(db["wt02"]["storedKey"], b"m", scram.client_proof(scram.salted("taba-no-sensei-0001", db["wt02"]["salt"]), b"m")))
    pl = C.all_courses(SCHOOL)
    check("無いコースだけ足す（紙のまま）", "e4b:math" in pl and C.use_level(pl["e4b:math"]) == 0)
    check("あるコースには触らない（講師も名前も）", pl["e4a:math"]["name"] == "小4α 算数" and len(pl["e4a:math"]["teachers"]) == 1)
    before = json.dumps(T.accounts(SCHOOL), sort_keys=True)
    A.import_bundle(T, bundle, yes=True, out=lines.append)
    check("もう一度流しても変わらない", json.dumps(T.accounts(SCHOOL), sort_keys=True) == before)
    try:
        A.import_bundle(T, dict(bundle, school={"id": "third", "name": "x", "code": "w"}), yes=True, out=lines.append)
        check("使われている校舎コードの束は入れない", False)
    except ValueError:
        check("使われている校舎コードの束は入れない", True)
    try:
        A.import_bundle(T, dict(bundle, accounts=[dict(accs[0], id="zz01")]), yes=True, out=lines.append)
        check("校舎コードで始まらないIDは入れない", False)
    except ValueError:
        check("校舎コードで始まらないIDは入れない", True)
    check("デモの目印が無い校舎は本物", T.is_demo_school(SCHOOL) is False)


def server_checks():
    port = free_port()
    base = "http://127.0.0.1:%d" % port
    class Srv(T.ThreadingHTTPServer):
        request_queue_size = 128
        daemon_threads = True
    httpd = Srv(("127.0.0.1", port), functools.partial(T.Handler, directory=T.APP_DIR))
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()

    def call(method, path, token=None, body=None, headers=None, raw=False):
        req = urllib.request.Request(base + path, method=method,
                                     data=None if body is None else json.dumps(body).encode("utf-8"))
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", "Bearer " + token)
        for k, v in (headers or {}).items():
            req.add_header(k, v)

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        op = urllib.request.build_opener(NoRedirect)
        try:
            r = op.open(req, timeout=30)
            data, code, hd = r.read(), r.status, r.headers
        except urllib.error.HTTPError as e:
            data, code, hd = e.read(), e.code, e.headers
        if raw:
            return code, data, hd
        try:
            return code, json.loads(data.decode("utf-8") or "{}")
        except ValueError:
            return code, {}

    def login2(lid, pw, admin=False, headers=None):
        """(状態の数字, 返事)。合言葉そのものは送らない（scram.py の手順）。"""
        return scram.login(base, lid, pw, admin=admin, headers=headers)

    def login(lid, pw, admin=False):
        c, d = login2(lid, pw, admin)
        return d.get("token") if c == 200 else None

    def dummy_v():
        return {"alg": "scram-sha256", "iters": 600000, "salt": secrets.token_hex(16), "storedKey": secrets.token_hex(32), "serverKey": secrets.token_hex(32)}

    def mkseats(cid, items):
        """前の形の席（まだ渡していない口座。we4a04…）を直に作る。**席を先に作る口は 10-01 に引退した**ので、
        検査の下ごしらえとして。items は合言葉（文字列）か、確かめる値（dict）。返す形は、前の口と同じ。"""
        made = []
        with T.LOCK:
            for it in items:
                db = T.accounts(SCHOOL)
                nums = [int(k[len("w" + cid):]) for k in db if re.match(r"^w%s\d{2,3}$" % re.escape(cid), k)]
                busy = {a.get("seat") for a in db.values() if a.get("classId") == cid and a.get("role") in ("student", "seat")}
                n = (max(nums) if nums else 0) + 1
                while "%02d" % n in busy:
                    n += 1
                lid = "w%s%02d" % (cid, n)
                T.add_account(SCHOOL, lid, None, "%02d" % n, "seat", cid[:2], cid, verifier=it if isinstance(it, dict) else verifier(it))
                made.append({"id": lid, "seat": "%02d" % n, "classId": cid})
        return 200, {"made": made}

    def forget():
        with T.FAIL_LOCK:
            T.FAILS.clear()
            T.USED.clear()
            T.ALERTED.clear()

    print("\n入る")
    check("カードのとおり", bool(login("we4a01", "neko-yama-sora-4821")))
    check("線なし・大文字でも入れる", bool(login("WE4A01", "NekoYamaSora4821")))
    check("全角でも入れる", bool(login("we4a01", "ｎｅｋｏ－ｙａｍａ－ｓｏｒａ－４８２１")))
    check("違う合言葉は入れない", login("we4a01", "neko-yama-sora-4822") is None)
    forget()
    print("\n合言葉は、線の上を流れない")
    seen = []
    real_json = T.Handler.body_json

    def spy(self, limit=None):
        d = real_json(self, limit)
        seen.append(json.dumps(d, ensure_ascii=False))
        return d
    T.Handler.body_json = spy
    ok_tok = login("we4a01", "neko-yama-sora-4821")
    T.Handler.body_json = real_json
    sent = " ".join(seen)
    check("入るときにサーバへ届く本文に、合言葉が無い（そろえた形も）", bool(ok_tok) and "neko" not in sent and "nekoyamasora4821" not in sent and "password" not in sent, sent[:120])
    check("届くのは ID・nonce・証明だけ", len(seen) == 2 and set(json.loads(seen[0])) == {"id", "cnonce"} and set(json.loads(seen[1])) == {"id", "nonce", "proof"}, [sorted(json.loads(x)) for x in seen])
    c, d = call("POST", "/api/login", body={"id": "we4a01", "password": "neko-yama-sora-4821"})
    check("前の口（合言葉そのものを送る形）は閉じている", c == 400 and "token" not in d, (c, d))
    forget()
    # 同じ証明を、もう一度使う
    cn = secrets.token_urlsafe(18)
    c, st1 = call("POST", "/api/login/start", body={"id": "we4a01", "cnonce": cn})
    sp = scram.salted("neko-yama-sora-4821", st1["salt"], st1["iters"])
    au = scram.auth_message("we4a01", st1["nonce"], st1["salt"], st1["iters"])
    fin = {"id": "we4a01", "nonce": st1["nonce"], "proof": scram.client_proof(sp, au)}
    c1, d1 = call("POST", "/api/login/finish", body=fin)
    c2, d2 = call("POST", "/api/login/finish", body=fin)
    check("証明で入れる。サーバの印が付いてくる", c1 == 200 and d1.get("serverSig") == scram.server_signature(scram.keys_from_salted(sp)[1], au), c1)
    check("同じ証明は、2度目には使えない", c2 == 401, c2)
    # 途中で見た人が、返事を書き換える（サーバの印を確かめる）
    def bad_post(path, body):
        c, d = call("POST", "/api" + path, body=body)
        if path == "/login/finish" and c == 200:
            d = dict(d, serverSig="0" * 64)
        return c, d
    c, d = scram.login(base, "we4a01", "neko-yama-sora-4821", post=bad_post)
    check("サーバの印が合わなければ、端末は入ったことにしない", c == 0, (c, d))
    # 無いID・古い形の口座にも、同じ形の返事
    c, a1 = call("POST", "/api/login/start", body={"id": "nai-no-hito", "cnonce": cn})
    c, a2 = call("POST", "/api/login/start", body={"id": "nai-no-hito", "cnonce": cn + "x"})
    c, a3 = call("POST", "/api/login/start", body={"id": "we4a01", "cnonce": cn})
    check("無いIDにも同じ形の返事（塩は毎回同じ・あるIDの塩とは違う）", set(a1) == set(a3) == {"salt", "iters", "nonce"} and a1["salt"] == a2["salt"] != a3["salt"] and a1["iters"] == a3["iters"], (a1, a3))
    c, d = call("POST", "/api/login/finish", body={"id": "nai-no-hito", "nonce": a1["nonce"], "proof": "0" * 64})
    check("無いIDは、どんな証明でも入れない（返事は同じ文）", c == 401 and d.get("error") == "IDかパスワードが違います", (c, d))
    c, d = call("POST", "/api/login/finish", body={"id": "we4a01", "nonce": a1["nonce"], "proof": "0" * 64})
    check("他人の nonce では続けられない", c == 401, c)
    c, d = call("POST", "/api/login/start", body={"id": "we4a01", "cnonce": "mijikai"})
    check("形のおかしい cnonce は 400", c == 400, c)
    c, st2 = call("POST", "/api/login/start", body={"id": "we4a01", "cnonce": cn})
    sp = scram.salted("neko-yama-sora-4821", st2["salt"], st2["iters"])
    fin2 = {"id": "we4a01", "nonce": st2["nonce"],
            "proof": scram.client_proof(sp, scram.auth_message("we4a01", st2["nonce"], st2["salt"], st2["iters"]))}
    forget()
    ttl = T.NONCE_TTL
    T.NONCE_TTL = -1                       # 時計を進める代わりに、期限を過去にする
    c, d = call("POST", "/api/login/finish", body=fin2)
    T.NONCE_TTL = ttl
    check("2分たった nonce は使えない（正しい証明でも）", c == 401 and "token" not in d, c)
    check("期限切れは、まちがいに数えない", not T.FAILS, dict(T.FAILS))
    c, d = call("POST", "/api/login/finish", body=fin2)
    check("同じ nonce でも、期限の内なら入れる（サーバは始めた分を覚えていない）", c == 200 and not hasattr(T, "PENDING"), c)
    # 印を書き換えた nonce・時刻を書き換えた nonce
    cnx, tsx, macx = st2["nonce"].split(".")
    for label, bad in (("印", "%s.%s.%s" % (cnx, tsx, "0" * 40)), ("時刻", "%s.%x.%s" % (cnx, int(time.time()) + 50, macx)),
                       ("cnonce", "%s.%s.%s" % (cnx[::-1], tsx, macx))):
        c, d = call("POST", "/api/login/finish", body=dict(fin2, nonce=bad))
        check("nonce の%sを書き換えると通らない" % label, c == 401, c)
    # 通った証明を控えておき、サーバが起き直した直後に もう一度送る
    c, st3 = call("POST", "/api/login/start", body={"id": "we4a01", "cnonce": cn})
    sp3 = scram.salted("neko-yama-sora-4821", st3["salt"], st3["iters"])
    fin3 = {"id": "we4a01", "nonce": st3["nonce"],
            "proof": scram.client_proof(sp3, scram.auth_message("we4a01", st3["nonce"], st3["salt"], st3["iters"]))}
    T.BOOT = secrets.token_hex(8)              # 起き直した（覚えていた「通った nonce」も消える）
    with T.FAIL_LOCK:
        T.USED.clear()
    c, d = call("POST", "/api/login/finish", body=fin3)
    check("サーバが起き直したら、前に出した nonce は通らない（正しい証明でも）", c == 401 and "token" not in d, c)
    check("起き直したあとも、ふつうに入れる", bool(login("we4a01", "neko-yama-sora-4821")))
    # あるID・無いIDで、読むファイルが同じ
    seen_acc = []
    real_accounts = T.accounts
    T.accounts = lambda sc: (seen_acc.append(sc), real_accounts(sc))[1]
    T._CODES["at"] = 0
    T.login_account("we4a01"); T.login_account("we9z99"); T.login_account("xe9z99"); T.login_account("xe4a01")
    T.accounts = real_accounts
    check("無いIDでも、そのIDが入るはずの校舎の表を読む（返事の速さで、あるかどうかを教えない）", seen_acc == [SCHOOL, SCHOOL, OTHER, OTHER], seen_acc)
    # 始めるだけを大量に送る（前は、覚える数の上限まで埋めると、ほかの人が入れなくなった）
    forget()
    for i in range(400):
        call("POST", "/api/login/start", body={"id": "we4a%02d" % (i % 30), "cnonce": secrets.token_urlsafe(18)})
    check("始めるだけを 400本送っても、サーバは何も覚えない", not T.FAILS and not T.USED, (len(T.FAILS), len(T.USED)))
    check("そのあとも、ふつうに入れる", bool(login("we4a01", "neko-yama-sora-4821")))
    check("置き場の秘密は、持ち主だけが読める", oct(os.stat(os.path.join(ROOT, ".secret")).st_mode & 0o777) == "0o600")
    forget()
    # 古い形の口座（合言葉そのもののハッシュを持つ）
    with T.LOCK:
        db = T.accounts(SCHOOL)
        db["wold01"] = dict(old_verifier("furui-kouza-0001"), sid="OLDSID01", seat="09", role="student", level="e4", classId="e4a", classes=[], created=1)
        db["wold02"] = {"alg": "scrypt", "salt": "0" * 32, "hash": "0" * 64, "sid": "OLDSID02", "seat": "10", "role": "student", "level": "e4", "classId": "e4a", "classes": [], "created": 1}
        T.save_accounts(SCHOOL, db)
        paths.bind_login("wold01", SCHOOL)
        paths.bind_login("wold02", SCHOOL)
    check("古い形の口座は、そのままでは入れない", login("wold01", "furui-kouza-0001") is None)
    fixed, left = T.upgrade_legacy(SCHOOL)
    a = T.accounts(SCHOOL)["wold01"]
    check("09-30 の形（pbkdf2-600k）は、合言葉なしで新しい形に直せる", fixed == 1 and left == 1 and a["alg"] == "scram-sha256" and "hash" not in a, (fixed, left))
    forget()
    check("直したあとは、同じ合言葉で入れる", bool(login("wold01", "Furui Kouza 0001")))
    check("それより古い形（scrypt）は直せず、入れない（作り直す）", login("wold02", "x") is None and "hash" in T.accounts(SCHOOL)["wold02"])
    forget()

    print("\n席に、カードを持った本人が入る")
    check("入る前は seat", T.accounts(SCHOOL)["we4a02"]["role"] == "seat")
    tok = login("we4a02", "kame-tori-umi-0002")
    a = T.accounts(SCHOOL)["we4a02"]
    check("入れる。入った瞬間に生徒になる", bool(tok) and a["role"] == "student" and a.get("usedBy") == "login", a.get("role"))
    c, d = call("GET", "/api/me", tok)
    check("自分の役割は student（seat は外に出ない）", c == 200 and d["profile"]["role"] == "student", d)
    check("入ったあとも、保存にあるのは証明を確かめる値だけ", a["alg"] == "scram-sha256" and "hash" not in a)
    check("最後に入った時刻が残る", int(a.get("lastLogin") or 0) > time.time() - 60)

    print("\n管理者")
    check("ふつうの入口からは入れない", login("wadmin01", "kanri-kanri-kanri-0001") is None)
    adm = login("wadmin01", "kanri-kanri-kanri-0001", admin=True)
    check("管理ページからは入れる", bool(adm))
    forget()
    tea = login("wt01", "sensei-pass-0001")
    stu = login("we4a01", "neko-yama-sora-4821")
    c, st = call("GET", "/api/admin/state", adm)
    check("管理の口が読める", c == 200 and st["school"]["id"] == SCHOOL and st["me"] == "wadmin01", c)
    cl = {x["id"]: x for x in st["classes"]}
    seats = {s["id"]: s for s in cl["e4a"]["seats"]}
    check("席の状態：使っている／まだ", seats["we4a01"]["st"] == "live" and seats["we4a02"]["st"] == "live" and seats["we4a03"]["st"] == "spare", seats)
    body = json.dumps(st)
    check("返事に salt・storedKey・serverKey・sid が入っていない", '"salt"' not in body and '"hash"' not in body and "storedKey" not in body and "serverKey" not in body and T.accounts(SCHOOL)["we4a01"]["sid"] not in body)
    check("ほかの校舎のIDが入っていない", "xe4a01" not in body and "xadmin01" not in body)
    for who, t in (("講師", tea), ("生徒", stu), ("合言葉なし", None)):
        c, _ = call("GET", "/api/admin/state", t)
        check("%sは管理の口に入れない" % who, c == (401 if t is None else 403), c)
        c, _ = call("POST", "/api/admin/join/code", t, {})
        check("%sは登録コードを作れない" % who, c == (401 if t is None else 403), c)
    for path in ("/api/today", "/api/lessons/grid", "/api/check?key=e4a:math", "/api/p/" + T.accounts(SCHOOL)["we4a01"]["sid"],
                 "/api/submissions/mine", "/api/messages", "/api/growth", "/api/class/e4a"):
        c, _ = call("GET", path, adm)
        check("管理者は %s に入れない" % path.split("?")[0], c == 403, c)
    c, d = call("GET", "/api/me", adm)
    check("管理者の /api/me は役割だけ", c == 200 and d["profile"]["role"] == "admin")

    print("\n席（前の形）。席を先に作る口は引退した")
    pws = ["tasu-seki-ichi-1111", "tasu-seki-ni-2222"]
    c, d = call("POST", "/api/admin/seats", adm, {"classId": "e4a", "verifiers": [verifier("mou-tsukurenai-0000")]})
    check("席を先に作る口は、もう無い（生徒は招待コードから自分で登録する）", c == 404 and "we4a04" not in T.accounts(SCHOOL), c)
    c, d = mkseats("e4a", pws)
    made = [m["id"] for m in d.get("made", [])]
    check("前の形の席（we4a04・05）は、置いてあれば今までどおり動く", made == ["we4a04", "we4a05"] and all(T.accounts(SCHOOL)[m]["role"] == "seat" for m in made) and bool(login("we4a05", pws[1])), made)
    mkseats("e4b", [dummy_v() for _ in range(15)])

    print("\n合言葉を作り直す")
    old = login("we4a01", "neko-yama-sora-4821")
    c, d = call("POST", "/api/admin/accounts/we4a01/password", adm, {"verifier": verifier("atarashii-aikotoba-9999")})
    check("作り直せる", c == 200 and d.get("closed", 0) >= 1, (c, d))
    c, _ = call("GET", "/api/me", old)
    check("前の合言葉で開いていた画面は、その場で閉じる", c == 401, c)
    check("前の合言葉では入れない", login("we4a01", "neko-yama-sora-4821") is None)
    check("新しい合言葉で入れる", bool(login("we4a01", "atarashii-aikotoba-9999")))
    forget()
    c, _ = call("POST", "/api/admin/accounts/xe4a01/password", adm, {"verifier": verifier("yoso-0000-yoso")})
    check("ほかの校舎の席は作り直せない", c == 404, c)
    check("ほかの校舎の合言葉は変わっていない", bool(login("xe4a01", "yoso-no-ko-0001")))

    print("\n隙間：照合の途中で作り直された")
    hook = {"n": 0}
    real_verify = T.SCRAM.verify_proof

    def slow_verify(stored, auth, proof):
        ok = real_verify(stored, auth, proof)
        if ok and hook.get("do"):
            fn, hook["do"] = hook["do"], None
            fn()
        return ok
    T.SCRAM.verify_proof = slow_verify
    newv = verifier("tochuu-de-kaeta-7777")
    hook["do"] = lambda: call("POST", "/api/admin/accounts/we4a03/password", adm, {"verifier": newv})
    t = login("we4a03", "inu-saru-kawa-0003")
    a = T.accounts(SCHOOL)["we4a03"]
    check("照合のあとで作り直されたら、古い合言葉では入れない", t is None)
    check("作り直した値が、古いもので上書きされていない", a["salt"] == newv["salt"] and a["storedKey"] == newv["storedKey"])
    check("席は seat のまま（入れていないので）", a["role"] == "seat")
    hook["do"] = lambda: call("POST", "/api/admin/accounts/state", adm, {"ids": ["we4a05"], "state": "left"})
    t = login("we4a05", pws[1])
    check("照合のあとで在籍終了になったら入れない", t is None and T.accounts(SCHOOL)["we4a05"].get("leftAt"))
    T.SCRAM.verify_proof = real_verify
    # 始めたあと・続ける前に作り直された（塩が変わった）
    cn2 = secrets.token_urlsafe(18)
    c, s0 = call("POST", "/api/login/start", body={"id": "we4a03", "cnonce": cn2})
    sp0 = scram.salted("tochuu-de-kaeta-7777", s0["salt"], s0["iters"])
    newv2 = verifier("mou-ichido-kaeta-8888")
    call("POST", "/api/admin/accounts/we4a03/password", adm, {"verifier": newv2})
    c, d = call("POST", "/api/login/finish", body={"id": "we4a03", "nonce": s0["nonce"], "proof": scram.client_proof(sp0, scram.auth_message("we4a03", s0["nonce"], s0["salt"], s0["iters"]))})
    check("始めたあとで作り直されたら、前の合言葉の証明は通らない", c == 401, c)
    call("POST", "/api/admin/accounts/we4a03/password", adm, {"verifier": newv})
    forget()
    check("新しい合言葉では入れる", bool(login("we4a03", "tochuu-de-kaeta-7777")))

    print("\n隙間：同じIDに同時に試す")
    forget()
    codes = []

    def guess(i):
        c, _ = login2("we4a01", "machigai-%04d" % i)
        codes.append(c)
    ths = [threading.Thread(target=guess, args=(i,)) for i in range(30)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    n401, n429 = codes.count(401), codes.count(429)
    check("30本を同時に送っても、照合まで進むのは上限（8本）まで", n401 == T.MAX_PER_ID and n429 == 30 - T.MAX_PER_ID, (n401, n429))
    check("締め出しのあいだは、同じ相手からは正しい合言葉でも待たされる", login("we4a01", "atarashii-aikotoba-9999") is None)
    forget()
    # よその人が何度まちがえても、本人は入れる（前は、8回で本人まで 15分締め出された）
    yoso = {"CF-Connecting-IP": "203.0.113.9"}
    with T.LOCK:      # ここまでの知らせを消しておく（1本ずつ順に送ったときにも、知らせが出ることを見る）
        paths.save(A._reports_file(SCHOOL), {"items": [r for r in A.load_reports(SCHOOL) if r.get("kind") != "guard"]})
    cs = [login2("we4a01", "yoso-no-hito-%04d" % i, headers=yoso)[0] for i in range(T.MAX_PER_ID + 2)]
    check("よその相手は 8回で止まる", cs.count(401) == T.MAX_PER_ID and cs[-1] == 429, cs)
    check("そのあいだも、本人は入れる", bool(login("we4a01", "atarashii-aikotoba-9999")))
    gs = [r for r in A.load_reports(SCHOOL) if r.get("kind") == "guard"]
    check("締め出したことが、管理ページの報告に1件出る（どの席か分かる・合言葉らしきものは無い）", len(gs) == 1 and "we4a01" in gs[0]["text"] and gs[0]["n"] == 1 and gs[0]["ids"] == ["we4a01"] and "yoso" not in json.dumps(gs[0]) and "machigai" not in json.dumps(gs[0]), gs)
    login2("nai-no-hito", "x" * 12, headers=yoso)
    check("無いIDでは知らせない", len([r for r in A.load_reports(SCHOOL) if r.get("kind") == "guard"]) == 1)
    junk = [T.login_alert("wnai%02d" % i, "idip") for i in range(25)]
    check("無いIDを何個たたいても、知らせの枠は減らない", not any(junk) and all(k[2] == "we4a01" for k in T.ALERTED), list(T.ALERTED)[:3])
    check("そのあとの本物の知らせは出る", T.login_alert("we4a02", "idip") is True)
    check("相手（IP）の上限に当たっただけでは、知らせない（止まったのは ID ではない）", T.login_alert("we4a03", "ip") is False)
    with T.FAIL_LOCK:
        for i in range(T.ALERT_MAX):
            T.ALERTED[(SCHOOL, "idip", "umeru%02d" % i)] = time.time()
    check("「同じ所から」の枠を使い切っても、「どこからも入れない」の知らせは出る", T.login_alert("we4a03", "idip") is False and T.login_alert("we4a03", "id") is True)
    gs = [r for r in A.load_reports(SCHOOL) if r.get("kind") == "guard"]
    check("知らせは1件にまとまる（ID の数だけ札を増やさない）", len(gs) == 1 and gs[0]["ids"] == ["we4a01", "we4a02", "we4a03（どこからも）"] and gs[0]["n"] == 3 and "we4a03（どこからも）" in gs[0]["text"], gs)
    k = T._fail_keys
    check("IPv6 は先頭の 64ビットで1人と数える（番地を変えても上限を越えられない）", k("x", "2001:db8:1:2::1")[0][0] == k("x", "2001:db8:1:2:ffff::9")[0][0] != k("x", "2001:db8:1:3::1")[0][0] and k("x", "192.0.2.7")[2][0] == "ip:192.0.2.7", k("x", "2001:db8:1:2::1"))
    c, d = login2("wadmin01", "kanri-kanri-kanri-0001", admin=True)
    check("管理者も、よその人のまちがいでは締め出されない", c == 200, c)
    call("POST", "/api/logout", d.get("token"))
    with T.FAIL_LOCK:
        T.FAILS["id:we4a01"] = [time.time()] * T.MAX_PER_ID_ALL
    check("相手を変えながら当て続けても、1つのIDには上限がある", login2("we4a01", "atarashii-aikotoba-9999")[0] == 429)
    forget()
    for i in range(3):
        login2("x" * 500 + str(i), "p")
    check("形のおかしいIDは1つの枠にまとまる", len([k for k in T.FAILS if k.startswith("id:")]) == 1, list(T.FAILS)[:4])
    forget()
    # 自分の席に入り直しても、相手（IP）の失敗の数は消えない
    for i in range(3):
        login2("we4a04", "chigau-%d" % i)
    login("we4a01", "atarashii-aikotoba-9999")
    check("1つ入れても、ほかのIDへの失敗は数えたまま", len(T.FAILS.get("ip:127.0.0.1", [])) == 3, T.FAILS.get("ip:127.0.0.1"))
    forget()

    print("\n状態を変える・消す")
    c, d = call("POST", "/api/admin/accounts/state", adm, {"ids": ["we4a04"], "state": "live"})
    check("「使う」で生徒になる（紙だけの生徒）", c == 200 and T.accounts(SCHOOL)["we4a04"]["role"] == "student" and d["done"] == ["we4a04"], (c, d.get("skipped")))
    p = C.all_courses(SCHOOL)["e4a:math"]
    check("使った席は宿題の受け取り手に入る", T.accounts(SCHOOL)["we4a04"]["sid"] in C.receivers(SCHOOL, p))
    c, d = call("POST", "/api/admin/accounts/state", adm, {"ids": ["we4a04"], "state": "spare"})
    check("記録が無ければ「まだ」に戻せる", c == 200 and T.accounts(SCHOOL)["we4a04"]["role"] == "seat", d.get("skipped"))
    c, d = call("POST", "/api/admin/accounts/state", adm, {"ids": ["we4a02"], "state": "spare"})
    check("入ったことのある席は戻せない（理由を言う）", c == 200 and d["done"] == [] and "在籍終了" in d["skipped"][0]["why"], d)
    tok2 = login("we4a02", "kame-tori-umi-0002")
    c, d = call("POST", "/api/admin/accounts/state", adm, {"ids": ["we4a02"], "state": "left"})
    check("在籍終了にできる", c == 200 and T.accounts(SCHOOL)["we4a02"].get("leftAt"))
    c, _ = call("GET", "/api/me", tok2)
    check("在籍終了で、開いていた画面は閉じる", c == 401, c)
    check("在籍終了の席は入れない", login("we4a02", "kame-tori-umi-0002") is None)
    forget()
    c, d = call("POST", "/api/admin/accounts/state", adm, {"ids": ["we4a02"], "state": "live"})
    check("在籍終了を取り消せる", c == 200 and not T.accounts(SCHOOL)["we4a02"].get("leftAt") and bool(login("we4a02", "kame-tori-umi-0002")))
    c, d = call("POST", "/api/admin/accounts/state", adm, {"ids": ["wadmin01"], "state": "left"})
    check("自分の口座は変えられない", c == 200 and d["done"] == [] and not T.accounts(SCHOOL)["wadmin01"].get("leftAt"))
    c, d = call("POST", "/api/admin/accounts/state", adm, {"ids": ["xe4a01"], "state": "left"})
    check("ほかの校舎の席は変えられない", c == 200 and d["done"] == [] and not T.accounts(OTHER)["xe4a01"].get("leftAt"))
    c, d = call("DELETE", "/api/admin/accounts/we4a04", adm)
    check("渡していない席は消せる", c == 200 and "we4a04" not in T.accounts(SCHOOL) and paths.school_of_login("we4a04") is None, (c, d.get("error")))
    c, d = call("DELETE", "/api/admin/accounts/we4a02", adm)
    check("記録のある席は消せない（在籍終了を案内する）", c == 400 and "在籍終了" in d.get("error", "") and "we4a02" in T.accounts(SCHOOL), (c, d))
    c, d = call("DELETE", "/api/admin/accounts/wadmin01", adm)
    check("自分は消せない", c == 400, c)
    c, d = call("DELETE", "/api/admin/accounts/xe4a01", adm)
    check("ほかの校舎の席は消せない", c == 404 and "xe4a01" in T.accounts(OTHER), c)
    c, d = call("DELETE", "/api/admin/accounts/nai99", adm)
    check("無い席は 404", c == 404, c)

    print("\n講師と担当")
    c, d = call("POST", "/api/admin/teachers", adm, {"verifiers": [verifier("atarashii-sensei-tasu-yo-3333")]})
    tid = (d.get("made") or [{}])[0].get("id")
    check("講師を足せる（ID は t-001 からの通し番号。呼び名も同じ）", c == 200 and tid == "t-001" and T.accounts(SCHOOL)[tid]["seat"] == "t-001", (c, d.get("error"), tid))
    c, d = call("PUT", "/api/admin/courses/teacher", adm, {"key": "e4b:japanese", "id": tid, "on": True})
    check("コースに講師を足せる", c == 200 and T.accounts(SCHOOL)[tid]["sid"] in C.all_courses(SCHOOL)["e4b:japanese"]["teachers"], (c, d.get("error")))
    ttok = login(tid, "atarashii-sensei-tasu-yo-3333")
    c, d = call("GET", "/api/me", ttok)
    keys = [x.get("key") for x in d.get("profile", {}).get("assign", [])]
    check("その講師の画面に、そのコースだけが出る", c == 200 and keys == ["e4b:japanese"], keys)
    c, d = call("GET", "/api/today", ttok)
    check("足した講師で「今日やること」が開く", c == 200, (c, d.get("error")))
    c, d = call("PUT", "/api/lessons/use", ttok, {"key": "e4b:japanese", "level": 2})
    check("足した講師が、担当コースの段階を変えられる", c == 200, (c, d.get("error")))
    c, d = call("PUT", "/api/lessons/use", ttok, {"key": "e4a:math", "level": 2})
    check("担当でないコースは変えられない", c == 403, c)
    c, d = call("PUT", "/api/admin/courses/teacher", adm, {"key": "e4b:japanese", "id": tid, "on": True})
    check("同じ講師を2度足しても1人", C.all_courses(SCHOOL)["e4b:japanese"]["teachers"].count(T.accounts(SCHOOL)[tid]["sid"]) == 1)
    c, d = call("PUT", "/api/admin/courses/teacher", adm, {"key": "e4b:japanese", "id": "we4a01", "on": True})
    check("生徒を担当にはできない", c == 400, c)
    c, d = call("PUT", "/api/admin/courses/teacher", adm, {"key": "nai:math", "id": tid, "on": True})
    check("無いコースは 404", c == 404, c)
    c, d = call("POST", "/api/admin/accounts/state", adm, {"ids": [tid], "state": "left"})
    check("講師を在籍終了にすると、担当から外れる", c == 200 and d["dropped"].get(tid) == ["e4b:japanese"] and T.accounts(SCHOOL)[tid]["sid"] not in C.all_courses(SCHOOL)["e4b:japanese"]["teachers"], d.get("dropped"))
    c, _ = call("GET", "/api/me", ttok)
    check("在籍終了の講師の画面は閉じる", c == 401, c)
    c, d = call("PUT", "/api/admin/courses/teacher", adm, {"key": "e4b:japanese", "id": tid, "on": True})
    check("在籍終了の講師は担当にできない", c == 400, c)
    c, d = call("GET", "/api/admin/courses/csv", adm)
    text = d.get("text", "")
    check("コースの表を書き出せる", c == 200 and "e4a" in text and "小4α 算数" in text and "wt01" in text, text[:120])
    c, d = call("POST", "/api/admin/courses/csv", adm, {"text": text})
    check("そのまま入れ直しても変わらない", c == 200 and d["made"] == 0 and d["changed"] == 0, d)
    more = text + "e4k,国語,小4K 国語,e4,nai-sensei,月16:40-18:10,e4a,,授業,\r\n"
    c, d = call("POST", "/api/admin/courses/csv", adm, {"text": more})
    check("1行でもおかしければ、何も入れない", c == 400 and "e4k:japanese" not in C.all_courses(SCHOOL), (c, str(d)[:80]))
    more = text + "e4k,国語,小4K 国語,e4,wt01,月16:40-18:10,e4a,,授業,\r\n"
    c, d = call("POST", "/api/admin/courses/csv", adm, {"text": more})
    check("正しい行は入る（紙のまま）", c == 200 and d["made"] == 1 and C.use_level(C.all_courses(SCHOOL)["e4k:japanese"]) == 0, d)

    print("\n報告")
    c, d = call("POST", "/api/report", stu if call("GET", "/api/me", stu)[0] == 200 else login("we4a01", "atarashii-aikotoba-9999"),
                {"text": "しゃしんが おくれません", "view": "hw", "ctx": {"w": "390"}})
    check("生徒が書ける", c == 200 and d.get("id"), (c, d))
    c, d = call("POST", "/api/report", None, {"text": "x"})
    check("入っていない人は書けない", c == 401, c)
    c, d = call("POST", "/api/report", tea, {"text": ""})
    check("空は 400", c == 400, c)
    for i in range(3):
        call("POST", "/api/report", tea, {"kind": "error", "text": "TypeError: x is undefined at ui-desk.js:10", "view": "check"})
    c, d = call("GET", "/api/admin/reports", adm)
    items = d.get("items", [])
    errs = [r for r in items if r["kind"] == "error"]
    says = [r for r in items if r["kind"] == "say"]
    check("管理者に届く（役割・クラス・番号まで。名前は無い）", c == 200 and says and says[0]["role"] == "student" and says[0]["classId"] == "e4a" and "name" not in says[0], items[:1])
    check("同じエラーは1件にまとまり、回数を数える", len(errs) == 1 and errs[0]["n"] == 3, [(r["n"]) for r in errs])
    c, d = call("GET", "/api/admin/reports", tea)
    check("講師は報告の一覧を読めない", c == 403, c)
    rid = says[0]["id"]
    c, d = call("PUT", "/api/admin/reports/" + rid, adm, {"state": "done", "note": "直した"})
    check("済みにできる", c == 200 and d["item"]["state"] == "done" and d["item"]["note"] == "直した")
    c, st = call("GET", "/api/admin/state", adm)
    check("まだの報告の数が1つ減る", st["reports"]["open"] == len([r for r in items if r["state"] != "done"]) - 1, st["reports"])
    check("入口の見張りの知らせも、同じ所に出ている", any(r["kind"] == "guard" for r in items), [r["kind"] for r in items])
    n = 0
    for i in range(10):
        c, d = call("POST", "/api/report", tea, {"text": "たくさん送る %d" % i})
        n += c == 200
    check("1時間に書けるのは %d 件まで" % A.SAY_PER_HOUR, n == A.SAY_PER_HOUR, n)
    c, d = call("POST", "/api/report", tea, {"text": "x" * 5000})
    rep = A.load_reports(SCHOOL)
    check("長い文は %d 字で切る" % A.REPORT_TEXT, all(len(r["text"]) <= A.REPORT_TEXT for r in rep))
    check("ほかの校舎には届かない", A.load_reports(OTHER) == [])

    print("\nオンラインで渡す（1回だけ使える言葉。本物の合言葉は、生徒の端末が作る）")
    code = "hiki-kae-no-kotoba-1234"
    c, d = call("POST", "/api/admin/accounts/we4b01/password", adm, {"verifier": verifier(code), "claim": True})
    a = T.accounts(SCHOOL)["we4b01"]
    check("引き換えの言葉を置ける（席は、まだ渡していないまま）", c == 200 and d.get("claim") is True and a["role"] == "seat" and a["claim"]["exp"] > time.time() + 6 * 86400, (c, d))
    c, st = call("GET", "/api/admin/state", adm)
    s1 = [x for x in [k for k in st["classes"] if k["id"] == "e4b"][0]["seats"] if x["id"] == "we4b01"][0]
    check("管理ページに「引き換え待ち」と期限が出る", s1["claim"] > time.time() and s1["st"] == "spare", s1)
    c, d = login2("we4b01", code)
    tokc = d.get("token")
    check("引き換えの言葉で入ると、引き換えの印だけが返る（役割もクラスも返らない）", c == 200 and d.get("claim") is True and "profile" not in d and bool(tokc), (c, sorted(d)))
    check("まだ生徒になっていない・入った日も付かない", T.accounts(SCHOOL)["we4b01"]["role"] == "seat" and not T.accounts(SCHOOL)["we4b01"].get("lastLogin"))
    for path in ("/api/me", "/api/assignments", "/api/today", "/api/admin/state", "/api/submissions/mine", "/api/curriculum"):
        c, _ = call("GET", path, tokc)
        check("引き換えの印では %s に入れない" % path, c == 403, c)
    c, d = call("POST", "/api/report", tokc, {"text": "x"})
    check("引き換えの印では報告も書けない", c == 403, c)
    c, d = call("POST", "/api/claim", tokc, {"verifier": {"alg": "scram-sha256"}})
    check("形のおかしい値では引き換えられない", c == 400, c)
    cur = T.accounts(SCHOOL)["we4b01"]
    c, d = call("POST", "/api/claim", tokc, {"verifier": {k: cur[k] for k in ("alg", "salt", "iters", "storedKey", "serverKey")}})
    check("引き換えの言葉を、そのまま合言葉にはできない", c == 400, (c, d))
    newpw = "jibun-no-tanmatsu-de-7777"
    c, d = call("POST", "/api/claim", tokc, {"verifier": verifier(newpw)})
    a = T.accounts(SCHOOL)["we4b01"]
    check("引き換えられる。席は在籍の生徒になる", c == 200 and a["role"] == "student" and "claim" not in a and a.get("claimedAt"), (c, d))
    c, _ = call("POST", "/api/claim", tokc, {"verifier": verifier("mou-ichido-0000")})
    check("引き換えの印は、1回で使えなくなる", c == 401, c)
    check("引き換えの言葉では、もう入れない", login("we4b01", code) is None)
    forget()
    tn = login("we4b01", newpw)
    c, d = call("GET", "/api/me", tn)
    check("端末が作った合言葉で入れる（ふつうの生徒として）", c == 200 and d["profile"]["role"] == "student", c)
    c, d = call("POST", "/api/claim", tn, {"verifier": verifier("futsuu-no-shirushi-0000")})
    check("ふつうの印では、引き換える口は使えない", c != 200 and T.accounts(SCHOOL)["we4b01"]["storedKey"] == a["storedKey"], c)
    # 横取り：2人が同じ言葉で入った。先に引き換えたほうだけが通る
    code2 = "yoko-dori-no-kensa-5678"
    call("POST", "/api/admin/accounts/we4b02/password", adm, {"verifier": verifier(code2), "claim": True})
    t_a, t_b = login2("we4b02", code2)[1].get("token"), login2("we4b02", code2)[1].get("token")
    c1, _ = call("POST", "/api/claim", t_a, {"verifier": verifier("saki-ni-hikikaeta-1111")})
    c2, _ = call("POST", "/api/claim", t_b, {"verifier": verifier("ato-kara-kita-hito-2222")})
    check("同じ言葉で2人が入っても、引き換えられるのは先の1人だけ", c1 == 200 and c2 == 401, (c1, c2))
    # 本人が引き換えられなかった → 管理者が渡し直すと、横取りした人の合言葉も画面も止まる
    thief = login("we4b02", "saki-ni-hikikaeta-1111")
    call("POST", "/api/admin/accounts/we4b02/password", adm, {"verifier": verifier("watashi-naoshi-3333"), "claim": True})
    c, _ = call("GET", "/api/me", thief)
    check("渡し直すと、先に引き換えた人の画面は閉じ、その合言葉でも入れない", c == 401 and login("we4b02", "saki-ni-hikikaeta-1111") is None, c)
    forget()
    # 期限
    with T.LOCK:
        db = T.accounts(SCHOOL)
        db["we4b02"]["claim"]["exp"] = int(time.time()) - 10
        T.save_accounts(SCHOOL, db)
    c, d = login2("we4b02", "watashi-naoshi-3333")
    check("期限を過ぎた引き換えの言葉では入れない", c == 401, c)
    forget()
    c, d = call("POST", "/api/admin/accounts/wadmin01/password", adm, {"verifier": verifier("kanri-wa-dame-0000"), "claim": True})
    check("管理者には、引き換えの言葉を使えない（作り直されてもいない）", c == 400 and "claim" not in T.accounts(SCHOOL)["wadmin01"], c)
    c, _ = call("GET", "/api/admin/state", adm)
    check("断られた操作のあとも、管理者の画面は続く", c == 200, c)
    raw = open(paths.school_file(SCHOOL, "accounts.json"), encoding="utf-8").read()
    check("引き換えの言葉も、端末が作った合言葉も、保存に無い", not any(x in raw for x in ("hiki-kae", "hikikae", "jibun-no", "jibunno", "yoko-dori", "watashi-naoshi")))

    print("\nクラス替え（管理ページから）")
    forget()
    pw_a1 = "atarashii-aikotoba-9999"
    before = dict(T.accounts(SCHOOL)["we4a01"])
    c, d = call("POST", "/api/admin/moves", adm, {"rows": [{"id": "we4a01", "classId": "e4b"}]})
    check("確かめるだけでは何も変わらない", c == 200 and d["moves"][0]["to"]["classId"] == "e4b" and "batch" not in d and T.accounts(SCHOOL)["we4a01"]["classId"] == "e4a", (c, d.get("error")))
    c, d = call("POST", "/api/admin/moves", adm, {"rows": [{"id": "we4a01", "classId": "e4b"}], "dry": False})
    after = T.accounts(SCHOOL)["we4a01"]
    batch = d.get("batch")
    check("移せる（ID・sid・合言葉の値は変わらない）", c == 200 and bool(batch) and after["classId"] == "e4b" and after["sid"] == before["sid"] and after["storedKey"] == before["storedKey"], (c, d.get("error")))
    live_b = [x["seat"] for x in T.accounts(SCHOOL).values() if x["role"] == "student" and not x.get("leftAt") and x["classId"] == "e4b"]
    check("行き先で、同じ番号が2人にならない", len(live_b) == len(set(live_b)), live_b)
    check("移ったあとも、同じ合言葉で入れる", bool(login("we4a01", pw_a1)))
    c, d = call("GET", "/api/admin/moves", adm)
    check("これまでのクラス替えに出る", c == 200 and any(b["batch"] == batch for b in d["items"]), d)
    c, d = call("POST", "/api/admin/moves/undo", adm, {"batch": batch, "dry": False})
    check("取り消せる（前のクラスと番号に戻る）", c == 200 and T.accounts(SCHOOL)["we4a01"]["classId"] == "e4a" and T.accounts(SCHOOL)["we4a01"]["seat"] == before["seat"], (c, d.get("error")))
    c, d = call("POST", "/api/admin/moves", adm, {"rows": [{"id": "xe4a01", "classId": "e4b"}], "dry": False})
    check("ほかの校舎の生徒は移せない", c == 400 and T.accounts(OTHER)["xe4a01"]["classId"] == "e4a", c)
    c, d = call("POST", "/api/admin/moves", adm, {"rows": [{"id": "we4a01", "classId": "nai"}], "dry": False})
    check("無いクラスへは移せない", c == 400, c)
    c, d = call("POST", "/api/admin/moves", tea, {"rows": [{"id": "we4a01", "classId": "e4b"}], "dry": False})
    check("講師はクラス替えできない", c in (401, 403), c)
    # まだ渡していない席の番号は、クラス替えで先に取らない（カードに刷った番号＝画面の番号）
    dbm = T.accounts(SCHOOL)
    held_b = {a["seat"] for a in dbm.values() if a["role"] == "seat" and not a.get("leftAt") and a["classId"] == "e4b"}
    c, d = call("POST", "/api/admin/moves", adm, {"rows": [{"id": "we4a01", "classId": "e4b"}]})
    check("行き先の番号は、まだ渡していない席の番号を避ける", c == 200 and bool(held_b) and d["moves"][0]["to"]["seat"] not in held_b, (held_b, d.get("moves")))
    c, d = call("POST", "/api/admin/moves", adm, {"rows": [{"id": "we4a01", "classId": "e4b", "seat": sorted(held_b)[0]}], "dry": False})
    check("まだ渡していない席の番号を名指ししても移さない（わけを言う）", c == 400 and "まだ渡していない席" in (d.get("error") or "") and T.accounts(SCHOOL)["we4a01"]["classId"] == "e4a", (c, d.get("error")))
    c, d = call("POST", "/api/admin/moves", adm, {"rows": [{"id": "we4a01", "classId": "e4b"}], "dry": False})
    b2, got = d.get("batch"), T.accounts(SCHOOL)["we4a01"]["seat"]
    dbx = T.accounts(SCHOOL)
    for lid in sorted(k for k, a in dbx.items() if a["role"] == "seat" and a["classId"] == "e4b"):
        T.activate_seat(dbx, lid)
    check("クラスの席を全部使っても、カードの番号と画面の番号がそろう", all(k.endswith(a["seat"]) for k, a in dbx.items() if k.startswith("we4b") and a["role"] == "student" and not a.get("leftAt")), [(k, a["seat"]) for k, a in dbx.items() if k.startswith("we4b")])
    c, d = call("POST", "/api/admin/moves/undo", adm, {"batch": b2, "dry": False})
    check("取り消して元に戻す", c == 200 and T.accounts(SCHOOL)["we4a01"]["classId"] == "e4a", (c, d.get("error")))
    # 在籍を終えた生徒の番号も取らない（戻ってきたとき、カードの番号のまま）
    num_b1 = T.accounts(SCHOOL)["we4b01"]["seat"]
    call("POST", "/api/admin/accounts/state", adm, {"ids": ["we4b01"], "state": "left"})
    c, d = call("POST", "/api/admin/moves", adm, {"rows": [{"id": "we4a01", "classId": "e4b"}]})
    check("行き先の番号は、在籍を終えた生徒の番号も避ける", c == 200 and d["moves"][0]["to"]["seat"] != num_b1, d.get("moves"))
    c, d = call("POST", "/api/admin/moves", adm, {"rows": [{"id": "we4a01", "classId": "e4b", "seat": num_b1}], "dry": False})
    check("在籍を終えた生徒の番号を名指ししても移さない", c == 400 and T.accounts(SCHOOL)["we4a01"]["classId"] == "e4a", (c, d.get("error")))
    c, d = call("POST", "/api/admin/accounts/state", adm, {"ids": ["we4b01"], "state": "live"})
    check("戻ってきた生徒の番号は、前のまま", c == 200 and T.accounts(SCHOOL)["we4b01"]["seat"] == num_b1 and not T.accounts(SCHOOL)["we4b01"].get("leftAt"), T.accounts(SCHOOL)["we4b01"]["seat"])

    print("\nクラスを足す・消す")
    c, d = call("POST", "/api/admin/classes", adm, {"id": "e4s", "name": "小4S"})
    cls_now = [k["id"] for k in T.curriculum(SCHOOL).get("classes") or []]
    check("クラスを足せる（今までのクラスは残る）", c == 200 and cls_now == ["e4a", "e4b", "e4s"], (c, d.get("error"), cls_now))
    for bad in ({"id": "e4s", "name": "べつ"}, {"id": "e4t", "name": "小4S"}, {"id": "e4s1", "name": "x"}, {"id": "x9a", "name": "x"},
                {"id": "e4", "name": "x"}, {"id": "e4u", "name": ""}, {"id": "E4 V", "name": "x"}):
        c, d = call("POST", "/api/admin/classes", adm, bad)
        check("足せないクラスは 400 %s" % bad["id"], c == 400, c)
    c, d = mkseats("e4s", ["atarashii-kurasu-0001"])
    check("足したクラスに席を作れる", c == 200 and d["made"][0]["id"] == "we4s01", (c, d.get("error")))
    check("足したクラスの席で入れる（学年は ID から）", bool(login("we4s01", "atarashii-kurasu-0001")) and T.accounts(SCHOOL)["we4s01"]["level"] == "e4")
    c, d = call("DELETE", "/api/admin/classes/e4s", adm)
    check("席のあるクラスは消せない", c == 400 and "e4s" in [k["id"] for k in T.curriculum(SCHOOL)["classes"]], c)
    c, d = call("DELETE", "/api/admin/classes/e4a", adm)
    check("コースが受け持つクラスは消せない", c == 400, c)
    c, d = call("POST", "/api/admin/classes", adm, {"id": "e4z", "name": "小4Z"})
    c, d = call("DELETE", "/api/admin/classes/e4z", adm)
    check("席もコースも無いクラスは消せる", c == 200 and "e4z" not in [k["id"] for k in T.curriculum(SCHOOL)["classes"]], c)
    c, d = call("POST", "/api/admin/classes", tea, {"id": "e4y", "name": "小4Y"})
    check("講師はクラスを足せない", c in (401, 403), c)

    print("\nあとから入った子にも、いま出ている宿題が届く")
    now_ms = int(time.time() * 1000)
    a_live = [a["sid"] for a in T.accounts(SCHOOL).values() if a["role"] == "student" and not a.get("leftAt") and a["classId"] == "e4a"]
    with T.LOCK:
        asg = T.assignments(SCHOOL)
        base_hw = {"title": "検査の宿題", "classId": "e4a", "kind": "hw", "route": "paper", "graded": True, "subject": "math", "createdBy": "plan"}
        asg["hw-open"] = dict(base_hw, id="hw-open", students=list(a_live), dueAt=now_ms + 3 * 86400000, lesson={"key": "e4a:math", "n": 1})
        asg["hw-past"] = dict(base_hw, id="hw-past", students=list(a_live), dueAt=now_ms - 3600000, lesson={"key": "e4a:math", "n": 2})
        asg["hw-box"] = dict(base_hw, id="hw-box", students=list(a_live), dueAt=now_ms + 3 * 86400000, lesson={"key": "e4a:math", "n": 901, "quiz": True}, quiz=True)
        asg["hw-box-picked"] = dict(base_hw, id="hw-box-picked", students=list(a_live[:1]), dueAt=now_ms + 3 * 86400000, lesson={"key": "e4a:math", "n": 902, "quiz": True}, quiz=True, picked=True)
        asg["hw-named"] = dict(base_hw, id="hw-named", students=list(a_live[:1]), dueAt=now_ms + 3 * 86400000, lesson={"key": "e4o:math", "n": 1})
        T.save_assignments(SCHOOL, asg)
    c, d = mkseats("e4a", ["ato-kara-kita-ko-0001", "ato-kara-kita-ko-0002", "ato-kara-kita-ko-0003"])
    late = [m["id"] for m in d["made"]]
    check("足しただけの席（渡していない）は、宿題の受け取り手に入らない", all(T.accounts(SCHOOL)[i]["sid"] not in T.assignments(SCHOOL)["hw-open"]["students"] for i in late))
    call("POST", "/api/admin/accounts/state", adm, {"ids": [late[0]], "state": "live"})
    s0 = T.accounts(SCHOOL)[late[0]]["sid"]
    asg = T.assignments(SCHOOL)
    check("「使う」にした席は、期限前の宿題に足される", s0 in asg["hw-open"]["students"] and any(j["sid"] == s0 for j in asg["hw-open"].get("joined", [])), asg["hw-open"].get("joined"))
    check("クラス全員への提出箱（期限前）にも足される（10-12 本人：新しい中3R の口座に過去問が無かった）", s0 in asg["hw-box"]["students"], asg["hw-box"]["students"])
    check("期限の過ぎた宿題・選んだ生徒だけの提出箱・指名のコースの宿題には足さない", s0 not in asg["hw-past"]["students"] and s0 not in asg["hw-box-picked"]["students"] and s0 not in asg["hw-named"]["students"])
    # まちがえて「使う」にした席は、戻せる（前は「出された宿題がある」で戻せず、幽霊の生徒が残った）
    c, d = call("POST", "/api/admin/accounts/state", adm, {"ids": [late[0]], "state": "spare"})
    asg = T.assignments(SCHOOL)
    check("まちがえて「使う」にした席は、宿題が出ていても「まだ」に戻せる（受け取り手からも外れる）",
          c == 200 and d["done"] == [late[0]] and T.accounts(SCHOOL)[late[0]]["role"] == "seat" and s0 not in asg["hw-open"]["students"]
          and not any(j["sid"] == s0 for j in asg["hw-open"].get("joined", [])), (d, asg["hw-open"].get("joined")))
    check("ほかの受け取り手は、そのまま", set(a_live) <= set(asg["hw-open"]["students"]), asg["hw-open"]["students"])
    call("POST", "/api/admin/accounts/state", adm, {"ids": [late[0]], "state": "live"})
    with T.LOCK:
        rt = T.ratings(SCHOOL)
        rt.setdefault("hw-open", {})[s0] = {"r": "A", "at": 1}
        T.save_ratings(SCHOOL, rt)
    c, d = call("POST", "/api/admin/accounts/state", adm, {"ids": [late[0]], "state": "spare"})
    check("評価の付いた宿題があれば、戻さない（受け取り手にも残る）", c == 200 and d["done"] == [] and "評価" in d["skipped"][0]["why"] and s0 in T.assignments(SCHOOL)["hw-open"]["students"], d)
    with T.LOCK:
        rt = T.ratings(SCHOOL)
        rt.get("hw-open", {}).pop(s0, None)
        T.save_ratings(SCHOOL, rt)
        asg = T.assignments(SCHOOL)
        asg["hw-solo"] = dict(base_hw, id="hw-solo", students=[s0], dueAt=now_ms + 3 * 86400000, lesson={"key": "e4a:math", "n": 3})
        T.save_assignments(SCHOOL, asg)
    c, d = call("POST", "/api/admin/accounts/state", adm, {"ids": [late[0]], "state": "spare"})
    asg = T.assignments(SCHOOL)
    check("その席だけが受け取っていた宿題は、宿題ごと消える（空の受け取り手は「クラス全員」に化けるため）", c == 200 and d["done"] == [late[0]] and "hw-solo" not in asg and s0 not in asg["hw-open"]["students"], (d, list(asg)))
    tl = login(late[1], "ato-kara-kita-ko-0002")
    s1 = T.accounts(SCHOOL)[late[1]]["sid"]
    check("カードで初めて入った子も、期限前の宿題に足される", bool(tl) and s1 in T.assignments(SCHOOL)["hw-open"]["students"])
    c, d = call("GET", "/api/assignments", tl)
    check("その子の画面に、その宿題が出る", c == 200 and any(x.get("id") == "hw-open" for x in d.get("assignments") or []), [x.get("id") for x in (d.get("assignments") or [])][:5])
    call("POST", "/api/admin/accounts/" + late[2] + "/password", adm, {"verifier": verifier("hikikae-de-hairu-0003"), "claim": True})
    tk = login2(late[2], "hikikae-de-hairu-0003")[1].get("token")
    call("POST", "/api/claim", tk, {"verifier": verifier("hikikaeta-ato-no-0003")})
    s2 = T.accounts(SCHOOL)[late[2]]["sid"]
    check("リンクを引き換えた子も、期限前の宿題に足される", s2 in T.assignments(SCHOOL)["hw-open"]["students"])
    n_before = T.assignments(SCHOOL)["hw-open"]["students"].count(s1)
    login(late[1], "ato-kara-kita-ko-0002")
    check("2度目に入っても、2重には足さない", T.assignments(SCHOOL)["hw-open"]["students"].count(s1) == n_before == 1)
    forget()
    with T.LOCK:
        asg = T.assignments(SCHOOL)
        for k in ("hw-open", "hw-past", "hw-box", "hw-named"):
            asg.pop(k, None)
        T.save_assignments(SCHOOL, asg)

    print("\n指名のコース（オンライン・土特など）に、生徒を入れる")
    c, d = call("GET", "/api/admin/courses/csv", adm)
    c, d = call("POST", "/api/admin/courses/csv", adm, {"text": d["text"] + "e4o,算数,小4 オンライン 算数,e4,wt01,,,,授業,\r\n"})
    check("指名のコースを作れる", c == 200 and "e4o:math" in C.all_courses(SCHOOL), (c, d.get("error")))
    c, d = call("PUT", "/api/admin/courses/student", adm, {"key": "e4o:math", "id": "we4a01", "on": True})
    sid1 = T.accounts(SCHOOL)["we4a01"]["sid"]
    check("生徒を1人入れられる（受け取り手になる）", c == 200 and C.receivers(SCHOOL, C.all_courses(SCHOOL)["e4o:math"]) == [sid1], (c, d.get("error")))
    c, st = call("GET", "/api/admin/state", adm)
    row = [x for x in st["courses"] if x["key"] == "e4o:math"][0]
    check("管理ページに、そのコースを受け持つ講師と、受け取る生徒の ID が出る", row["teachers"] == ["wt01"] and row["ids"] == ["we4a01"] and row["n"] == 1, row)
    rowc = [x for x in st["courses"] if x["key"] == "e4a:math"][0]
    live_a = sorted(i for i, a in T.accounts(SCHOOL).items() if a["role"] == "student" and not a.get("leftAt") and a["classId"] == "e4a")
    check("クラスのコースの「受け取る生徒」は、在籍の生徒だけ（渡していない席は入らない）", rowc["ids"] == live_a and rowc["n"] == len(live_a), (rowc["ids"], live_a))
    c, d = call("PUT", "/api/admin/courses/student", adm, {"key": "e4o:math", "id": "we4a01", "on": True})
    check("2度入れても1人", C.all_courses(SCHOOL)["e4o:math"]["students"] == [sid1])
    spare = [i for i, a in T.accounts(SCHOOL).items() if a["role"] == "seat"][0]
    c, d = call("PUT", "/api/admin/courses/student", adm, {"key": "e4o:math", "id": spare, "on": True})
    check("まだ渡していない席は入れられない（理由を言う）", c == 400 and "使う" in d.get("error", ""), (c, d))
    c, d = call("PUT", "/api/admin/courses/student", adm, {"key": "e4a:math", "id": "we4a01", "on": True})
    check("クラスで受けるコースには、指名できない", c == 400, c)
    c, d = call("PUT", "/api/admin/courses/student", adm, {"key": "e4o:math", "id": "xe4a01", "on": True})
    check("ほかの校舎の生徒は入れられない", c == 400, c)
    c, d = call("PUT", "/api/admin/courses/student", tea, {"key": "e4o:math", "id": "we4a02", "on": True})
    check("講師は指名を変えられない", c in (401, 403), c)
    c, d = call("PUT", "/api/admin/courses/student", adm, {"key": "e4o:math", "id": "we4a01", "on": False})
    check("外せる", c == 200 and C.all_courses(SCHOOL)["e4o:math"]["students"] == [], c)

    print("\n管理者を足す")
    c, d = call("POST", "/api/admin/admins", adm, {"verifiers": [verifier("futari-me-no-kanri-sha-desu-4444")]})
    aid = (d.get("made") or [{}])[0].get("id")
    check("管理者（開発者）を足せる（ID は d-001 から）", c == 200 and aid == "d-001" and T.accounts(SCHOOL)[aid]["role"] == "admin", (c, d.get("error"), aid))
    adm_b = login(aid, "futari-me-no-kanri-sha-desu-4444", admin=True)
    c, _ = call("GET", "/api/admin/state", adm_b)
    check("足した管理者で入れる", c == 200, c)
    c, d = call("POST", "/api/admin/accounts/state", adm_b, {"ids": [aid], "state": "left"})
    check("自分を在籍終了にはできない", d.get("done") == [], d)

    print("\nデモの入口と、止めない入れ替え")
    T.DEMO["on"] = True
    c, d = call("GET", "/api/health")
    check("本物の校舎があるときは、ふつうの入口に「ためしに見る」を出さない（/demo では出す）", c == 200 and d["demo"] is False and d["demoPage"] is True, d)
    c, data, hd = call("GET", "/demo", raw=True)
    check("デモの入口（/demo）が開く", c == 200 and b"js/ui-core.js?v=" in data, c)
    T.DEMO["on"] = False
    build = os.path.join(ROOT, ".demo-build")
    shutil.rmtree(build, ignore_errors=True)
    env = dict(os.environ, MYACADY_ROOT=build, MYACADY_FSYNC="0")
    subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "seed", "--reset", "--empty", "--school", "london", "--name", "デモ校"], env=env, capture_output=True)
    subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "add", "lj2r01", "01", "--school", "london", "--class", "j2r", "--level", "j2", "--password", "demo-no-seito-0001"], env=env, capture_output=True)
    env0 = dict(os.environ, MYACADY_ROOT=ROOT, MYACADY_FSYNC="0")
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "demo-swap", "--from", build, "--school", "london", "--yes"], env=env0, capture_output=True, text=True)
    check("デモの目印の無い校舎は、入れ替えの元にしない", r.returncode == 1 and not os.path.isdir(paths.school_dir("london")), r.stdout[-120:])
    sj = os.path.join(build, "schools", "london", "school.json")
    meta = json.load(open(sj, encoding="utf-8"))
    meta["demo"] = True
    json.dump(meta, open(sj, "w", encoding="utf-8"))
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "demo-swap", "--from", build, "--school", SCHOOL, "--yes"], env=env0, capture_output=True, text=True)
    check("本物の校舎は、入れ替えの行き先にしない", r.returncode == 1 and "wadmin01" in T.accounts(SCHOOL), r.stdout[-120:])
    n_real = len(T.accounts(SCHOOL))
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "demo-swap", "--from", build, "--school", "london", "--yes"], env=env0, capture_output=True, text=True)
    check("デモを、動いているサーバの横で入れ替えられる", r.returncode == 0 and os.path.isfile(paths.school_file("london", "school.json")) and paths.school_of_login("lj2r01") == "london", (r.stdout[-200:], r.stderr[-200:]))
    check("入れ替えたデモに、そのまま入れる（サーバは止めていない）", bool(login("lj2r01", "demo-no-seito-0001")))
    check("本物の校舎には触っていない", len(T.accounts(SCHOOL)) == n_real and paths.school_of_login("we4a01") == SCHOOL and bool(login("we4a01", pw_a1)))
    check("入れ替えの残りが無い", not [n for n in os.listdir(paths.SCHOOLS) if n.startswith(".old-")] and not os.path.isdir(os.path.join(build, "schools", "london")))
    # もう一度（2回目は、いまのデモを押しのけて入れ替える）
    subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "seed", "--reset", "--empty", "--school", "london", "--name", "デモ校2"], env=env, capture_output=True)
    subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "add", "lj2r02", "02", "--school", "london", "--class", "j2r", "--level", "j2", "--password", "demo-no-seito-0002"], env=env, capture_output=True)
    meta = json.load(open(sj, encoding="utf-8"))
    meta["demo"] = True
    json.dump(meta, open(sj, "w", encoding="utf-8"))
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "demo-swap", "--from", build, "--school", "london", "--yes"], env=env0, capture_output=True, text=True)
    check("2回目の入れ替え：前のデモの ID は索引から消え、新しい ID で入れる", r.returncode == 0 and paths.school_of_login("lj2r01") is None and bool(login("lj2r02", "demo-no-seito-0002")), (r.stdout[-200:], r.stderr[-200:]))
    check("デモの校舎はデモ・本物は本物", T.is_demo_school("london") and not T.is_demo_school(SCHOOL))
    forget()

    print("\n講師の名簿づくり（管理者のいない校舎）も、合言葉を受け取らない")
    T.add_account("london", "lt09", "demo-no-sensei-0009", "T09", "teacher", "", "", classes=["j2r"])
    lt = login("lt09", "demo-no-sensei-0009")
    c, d = call("POST", "/api/roster/bulk", lt, {"rows": [{"classId": "j2r", "seat": "31", "grade": "j2"}]})
    check("確かめるための値が無い行は作らない", c == 200 and d["made"] == [] and len(d["skipped"]) == 1 and paths.school_of_login("lj2r31") is None, d)
    c, d = call("POST", "/api/roster/bulk", lt, {"rows": [{"classId": "j2r", "seat": "31", "grade": "j2", "password": "okuttemo-yomanai-0031"}]})
    check("合言葉そのものを送っても読まない", c == 200 and d["made"] == [] and paths.school_of_login("lj2r31") is None, d)
    c, d = call("POST", "/api/roster/bulk", lt, {"rows": [{"classId": "j2r", "seat": "31", "grade": "j2", "verifier": verifier("tanmatsu-de-tsukutta-0031")}]})
    check("値が届けば作る。返事に合言葉は無い", c == 200 and [m["id"] for m in d["made"]] == ["lj2r31"] and "password" not in json.dumps(d), d)
    check("端末が作った合言葉で入れる", bool(login("lj2r31", "tanmatsu-de-tsukutta-0031")))
    c, d = call("POST", "/api/roster/bulk", login("wt01", "sensei-pass-0001"), {"rows": [{"classId": "e4a", "seat": "29", "verifier": verifier("kanri-no-kousha-0029")}]})
    check("管理者のいる校舎では、講師は席を作れない", c == 400 and "we4a29" not in T.accounts(SCHOOL), c)
    forget()

    print("\nおかしな本文")
    def raw_post(path, blob, token=None):
        req = urllib.request.Request(base + path, method="POST", data=blob)
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", "Bearer " + token)
        try:
            return urllib.request.urlopen(req, timeout=30).status
        except urllib.error.HTTPError as e:
            return e.code
    deep = b"[" * 200000
    check("深すぎる入れ子でも落ちない（入口）", raw_post("/api/login/start", deep) == 400)
    check("辞書でない本文（配列・文字列・数）でも落ちない", [raw_post("/api/login/start", b) for b in (b"[1]", b'"x"', b"7")] == [400, 400, 400] and raw_post("/api/login/finish", b"[1]") in (400, 401))
    seen_len = []
    real_read = T.Handler.body_json
    def spy_len(self, limit=None):
        seen_len.append(limit)
        return real_read(self, limit)
    T.Handler.body_json = spy_len
    big = raw_post("/api/login/start", b'{"id":"' + b"a" * 6000 + b'","cnonce":"' + b"c" * 24 + b'"}')
    T.Handler.body_json = real_read
    check("入る前の口は、4KB を超える本文を読まない", big == 400 and seen_len == [T.LOGIN_BODY_MAX] and T.LOGIN_BODY_MAX <= 4096, (big, seen_len))
    check("深すぎる入れ子でも落ちない（入ったあと）", raw_post("/api/report", deep, lt) in (400, 413))
    check("そのあとも動いている", call("GET", "/api/health")[0] == 200)
    forget()

    print("\n初回登録（招待コードから、保護者が口座を作る。join.py）")
    import join as J
    J._HITS.clear()
    forget()
    now_ms = int(time.time() * 1000)
    base_hw = {"title": "登録の宿題", "classId": "e4a", "kind": "hw", "route": "paper", "graded": True, "subject": "math", "createdBy": "plan"}
    c, d = call("PUT", "/api/admin/roster", adm, {"rows": []})
    check("Excel からの同期の口は引退した（404）", c == 404, c)
    c, d = call("PUT", "/api/me/declare", login("we4a01", pw_a1), {"subjects": ["math"]})
    check("初回の申告の口も引退した（設定で変える、に作り替えた）", c == 404, c)
    def jpost(path, body, ip=None):
        return call("POST", path, body=body, headers=({"CF-Connecting-IP": ip} if ip else None))
    c, d = jpost("/api/join/check", {"code": "AAAAAA"})
    check("コードが無い校舎では、どのコードも通らない", c == 403, (c, d))
    c, st = call("POST", "/api/admin/join/code", adm, {})
    code = st["join"]["code"]
    check("管理者が登録コードを作れる（6文字・紛らわしい字なし）", c == 200 and re.match(r"^[2-9A-HJ-NP-Z]{6}$", code) and st["state"]["join"]["code"] == code, (c, code))
    c, d = call("POST", "/api/admin/join/code", tea, {})
    check("講師はコードを作れない", c in (401, 403), c)
    c, d = jpost("/api/join/check", {"code": code.lower()[:3] + " " + code.lower()[3:]})
    check("コードを確かめると、選べる学年・クラス・科目の組が返る（小文字・空白でも）", c == 200 and d["school"]["name"] and any(k["id"] == "e4a" for k in d["classes"]) and len(d["combos"]["e"]) == 4 and len(d["combos"]["j"]) == 4 and d["max"] == 4, (c, d))
    c, d = jpost("/api/join/check", {"code": "ZZZZZZ"})
    check("違うコードは 403（校舎の名前も返さない）", c == 403 and "school" not in d, (c, d))
    kid = {"grade": "e4", "classId": "e4a", "subjects": ["japanese", "math"]}
    c, d = jpost("/api/join", {"code": code, "students": [kid]})
    check("同意が無ければ作らない", c == 400, (c, d))
    for label, bad in (("学年とクラスが合わない", dict(kid, grade="e5")), ("無いクラス", dict(kid, classId="e9z")),
                       ("決まった組でない科目", dict(kid, subjects=["math"])), ("小1（登録できない学年）", dict(kid, grade="e1"))):
        c, d = jpost("/api/join", {"code": code, "agree": True, "students": [bad]})
        check("%s は作らない" % label, c == 400, (c, d))
    c, d = jpost("/api/join", {"code": code, "agree": True, "students": [kid] * 5})
    check("1回に作れるのは 4人まで", c == 400, (c, d))
    J._HITS.clear()
    c, d = jpost("/api/join", {"code": "ZZZZZZ", "agree": True, "students": [kid]})
    check("違うコードでは作れない", c == 403, (c, d))
    J._HITS.clear()
    with T.LOCK:
        asg = T.assignments(SCHOOL)
        live_a = [a["sid"] for a in T.accounts(SCHOOL).values() if a["role"] == "student" and not a.get("leftAt") and a["classId"] == "e4a"]
        asg["hw-j1"] = dict(base_hw, id="hw-j1", students=list(live_a), dueAt=now_ms + 3 * 86400000, lesson={"key": "e4a:math", "n": 1})
        T.save_assignments(SCHOOL, asg)
    twin = [kid, dict(kid)]
    c, d = jpost("/api/join", {"code": code, "agree": True, "students": twin})
    made = d.get("made") or []
    ids = [m["id"] for m in made]
    dbj = T.accounts(SCHOOL)
    check("ふたご（同じクラス）を2人ぶん作れる。ID は s-000 の形で、別々", c == 200 and len(ids) == 2 and ids[0] != ids[1] and all(re.match(r"^s-\d{3}$", i) for i in ids), (c, d))
    check("この時点では仮の口座（名簿にも宿題にも出ない・入れない）", all(dbj[i]["role"] == "seat" and dbj[i].get("pending") for i in ids) and not any(dbj[i]["sid"] in T.assignments(SCHOOL)["hw-j1"]["students"] for i in ids))
    check("仮の口座の鍵は、サーバにはハッシュだけ", all(made[k]["setup"] not in json.dumps(dbj[ids[k]]) for k in range(2)))
    raw = open(paths.school_file(SCHOOL, "accounts.json"), encoding="utf-8").read()
    pwj = "kazoku no aikotoba 2026"
    c, d = jpost("/api/join/finish", {"items": [{"id": ids[0], "setup": "chigau-kagi", "verifier": verifier(pwj)}]})
    check("鍵が違えば、合言葉を置けない", c == 410 and T.accounts(SCHOOL)[ids[0]]["role"] == "seat", (c, d))
    c, d = jpost("/api/join/finish", {"items": [{"id": ids[0], "setup": made[0]["setup"], "verifier": verifier(pwj)},
                                              {"id": ids[1], "setup": "chigau", "verifier": verifier(pwj)}]})
    check("1つでもおかしければ、どちらも変えない", c == 410 and open(paths.school_file(SCHOOL, "accounts.json"), encoding="utf-8").read() == raw, (c, d))
    c, d = jpost("/api/join/finish", {"items": [{"id": ids[k], "setup": made[k]["setup"], "verifier": verifier(pwj)} for k in range(2)]})
    dbj = T.accounts(SCHOOL)
    check("合言葉を置くと、在籍の生徒になる（呼び名は ID そのもの・科目は選んだもの）", c == 200 and all(dbj[i]["role"] == "student" and dbj[i]["seat"] == i and dbj[i]["subjects"] == ["japanese", "math"] and "pending" not in dbj[i] and dbj[i].get("via") == "join" for i in ids), (c, d))
    check("同じ合言葉でも、ID ごとに別の値（塩）", dbj[ids[0]]["salt"] != dbj[ids[1]]["salt"] and dbj[ids[0]]["storedKey"] != dbj[ids[1]]["storedKey"])
    check("いま出ている宿題（期限前）の受け取り手に入る", all(dbj[i]["sid"] in T.assignments(SCHOOL)["hw-j1"]["students"] for i in ids))
    tj = login(ids[0], pwj)
    c, d = call("GET", "/api/me", tj)
    check("作った合言葉で、2人とも入れる。画面に質問は出ない", bool(tj) and bool(login(ids[1], pwj)) and c == 200 and "ask" not in d["profile"] and d["profile"]["seat"] == ids[0], d.get("profile", {}).get("ask"))
    check("講師の名簿の呼び名は「クラス名 ID」", T.seat_label("小4α", ids[0]) == "小4α " + ids[0] and T.seat_label("小4α", "07") == "小4α-07")
    c, d = jpost("/api/join/finish", {"items": [{"id": ids[0], "setup": made[0]["setup"], "verifier": verifier("nottori-0000")}]})
    check("できあがった口座の合言葉は、同じ鍵でもう変えられない", c == 410 and bool(login(ids[0], pwj)), (c, d))
    c, d = jpost("/api/join/finish", {"items": [{"id": "we4a01", "setup": "x", "verifier": verifier("nottori-0000")}]})
    check("ふつうの口座には、登録の口から触れない", c == 410, (c, d))
    # 合言葉を作らなかった仮の口座は、1時間で消える（ID は戻る）
    c, d = jpost("/api/join", {"code": code, "agree": True, "students": [kid]})
    ghost = d["made"][0]["id"]
    with T.LOCK:
        dbj = T.accounts(SCHOOL)
        dbj[ghost]["pending"]["exp"] = int(time.time()) - 5
        T.save_accounts(SCHOOL, dbj)
    c, d = jpost("/api/join/finish", {"items": [{"id": ghost, "setup": d["made"][0]["setup"], "verifier": verifier(pwj)}]})
    check("1時間たった仮の口座には、合言葉を置けない", c == 410, (c, d))
    c, d = jpost("/api/join", {"code": code, "agree": True, "students": [kid]})
    check("次の登録のときに、古い仮の口座は消える（索引からも）", ghost not in T.accounts(SCHOOL) and paths.school_of_login(ghost) is None, ghost)
    # 回数の上限（同じ相手）
    J._HITS.clear()
    cs = [jpost("/api/join", {"code": code, "agree": True, "students": [kid]}, ip="203.0.113.60")[0] for _ in range(J.JOIN_PER_HOUR + 1)]
    check("同じ相手からの登録は、1時間に %d 回まで" % J.JOIN_PER_HOUR, cs.count(200) == J.JOIN_PER_HOUR and cs[-1] == 429, cs)
    check("よその相手は、その上限に巻き込まれない", jpost("/api/join/check", {"code": code}, ip="203.0.113.61")[0] == 200)
    cs = [jpost("/api/join/check", {"code": "ZZZZZ%d" % (i % 8 + 2)}, ip="203.0.113.62")[0] for i in range(J.CHECK_PER_15MIN + 1)]
    check("コードの総当たりは、15分に %d 回で止まる" % J.CHECK_PER_15MIN, cs.count(403) == J.CHECK_PER_15MIN and cs[-1] == 429, cs[-3:])
    old = code
    c, st = call("POST", "/api/admin/join/code", adm, {})
    J._HITS.clear()
    check("コードを作り直すと、前のコードは使えない（登録ずみの ID はそのまま）", st["join"]["code"] != old and jpost("/api/join/check", {"code": old})[0] == 403 and bool(login(ids[0], pwj)))
    check("ID の割り当て：生徒は無作為・講師と開発者は通し番号", J.alloc_id(T, "teacher", ["t-001", "t-002"]) in ("t-002", "t-003") and re.match(r"^d-\d{3}$", J.alloc_id(T, "admin", [])) and re.match(r"^s-\d{3}$", J.alloc_id(T, "student", [])))
    demo_on = T.DEMO["on"]
    T.DEMO["on"] = True
    c, h0 = call("GET", "/api/health")
    with T.LOCK:
        meta = dict(T.school_meta(SCHOOL)); meta["trial"] = True
        paths.save(paths.school_file(SCHOOL, "school.json"), meta)
        meta2 = dict(T.school_meta(OTHER)); meta2["trial"] = True
        paths.save(paths.school_file(OTHER, "school.json"), meta2)
    c, h1 = call("GET", "/api/health")
    T.DEMO["on"] = demo_on
    check("試し運用中の校舎だけなら、ふつうの入口に「ためしに見る」を出す（本物があるときは出さない）", h0["demo"] is False and h1["demo"] is True, (h0, h1))
    with T.LOCK:
        for sc in (SCHOOL, OTHER):
            m3 = dict(T.school_meta(sc)); m3.pop("trial", None)
            paths.save(paths.school_file(sc, "school.json"), m3)
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "school-trial", "--school", SCHOOL, "--on"], env=dict(os.environ, MYACADY_ROOT=ROOT), capture_output=True, text=True)
    check("コマンドで試し運用の印を付けられる", r.returncode == 0 and T.school_meta(SCHOOL).get("trial") is True, r.stdout[-80:])
    subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "school-trial", "--school", SCHOOL, "--off"], env=dict(os.environ, MYACADY_ROOT=ROOT), capture_output=True, text=True)
    c, data, hd = call("GET", "/media/intro.mp4", headers={"Range": "bytes=0-99"}, raw=True)
    check("動画は範囲つきの求めに 206 で答える（iPhone の Safari が要る）", c == 206 and len(data) == 100 and (hd.get("Content-Range") or "").startswith("bytes 0-99/") and hd.get("Accept-Ranges") == "bytes", (c, len(data), hd.get("Content-Range")))
    c, data, hd = call("GET", "/media/intro.mp4", headers={"Range": "bytes=999999999-"}, raw=True)
    check("範囲が外なら 416", c == 416, c)
    print("\n設定：学年・クラス・受講科目を、本人が変える（自己申告。情報は ID に集まる）")
    J._HITS.clear()
    forget()
    tj = login(ids[0], pwj)
    sid0 = T.accounts(SCHOOL)[ids[0]]["sid"]
    c, d = call("PUT", "/api/me/placement", tj, {"classId": "e4b"})
    a0 = T.accounts(SCHOOL)[ids[0]]
    check("クラスを変えられる（ID も呼び名も変わらない）", c == 200 and d["changed"] == ["classId"] and a0["classId"] == "e4b" and a0["seat"] == ids[0] and d["profile"]["classId"] == "e4b", (c, d))
    check("前のクラスの・期限前の宿題からは外れる", sid0 not in T.assignments(SCHOOL)["hw-j1"]["students"])
    c, d = call("PUT", "/api/me/placement", tj, {"classId": "e4a", "subjects": ["japanese", "math", "science", "social"]})
    a0 = T.accounts(SCHOOL)[ids[0]]
    check("クラスを戻し、科目を増やせる。宿題にも戻る", c == 200 and sorted(d["changed"]) == ["classId", "subjects"] and a0["subjects"] == ["japanese", "math", "science", "social"] and sid0 in T.assignments(SCHOOL)["hw-j1"]["students"], (c, d))
    c, d = call("GET", "/api/me", login(ids[0], pwj))
    check("ほかの端末で入っても、同じ内容（端末でなく ID に集まる）", d["profile"]["classId"] == "e4a" and d["profile"]["subjects"] == ["japanese", "math", "science", "social"])
    c, d = call("PUT", "/api/me/placement", tj, {"classId": "e4a", "subjects": ["japanese", "math", "science", "social"]})
    check("同じ内容なら、何も変えない（回数にも数えない）", c == 200 and d["changed"] == [] and len(T.accounts(SCHOOL)[ids[0]]["placements"]) == 2, d)
    for label, body in (("決まった組でない科目", {"subjects": ["math"]}), ("学年の合わないクラス", {"classId": "e9z"}), ("無い学年", {"grade": "e9"})):
        c, d = call("PUT", "/api/me/placement", tj, body)
        check("%s は受けない" % label, c == 400, (c, d))
    with T.LOCK:
        rt = T.ratings(SCHOOL)
        rt.setdefault("hw-j1", {})[sid0] = {"r": "A", "at": 1}
        T.save_ratings(SCHOOL, rt)
    c, d = call("PUT", "/api/me/placement", tj, {"subjects": ["japanese", "math"], "classId": "e4b"})
    check("評価の付いた宿題からは、クラスを変えても外さない（記録を消さない）", c == 200 and sid0 in T.assignments(SCHOOL)["hw-j1"]["students"], (c, d))
    with T.LOCK:
        rt = T.ratings(SCHOOL)
        rt.get("hw-j1", {}).pop(sid0, None)
        T.save_ratings(SCHOOL, rt)
    c, d = call("PUT", "/api/me/placement", tea, {"classId": "e4b"})
    check("講師は使えない（自分の口座を変える口）", c in (401, 403), c)
    cs = []
    for i in range(J.PLACEMENT_PER_DAY):
        cs.append(call("PUT", "/api/me/placement", tj, {"classId": "e4a" if i % 2 == 0 else "e4b"})[0])
    check("本人が変えられるのは、1日に %d 回まで（ここまでに3回。あと3回で止まる。同じ内容は数えない）" % J.PLACEMENT_PER_DAY, cs[:4] == [200, 200, 200, 429] and cs[-1] == 429, cs)
    c, d = call("POST", "/api/admin/classes", adm, {"id": "e5a", "name": "小5α"})
    c, d = call("PUT", "/api/admin/accounts/%s/placement" % ids[0], adm, {"grade": "e5", "classId": "e5a", "subjects": ["japanese", "math"]})
    a0 = T.accounts(SCHOOL)[ids[0]]
    check("管理者は、学年ごと直せる（回数の上限なし）", c == 200 and sorted(d["changed"]) == ["classId", "grade"] and a0["level"] == "e5" and a0["classId"] == "e5a" and a0["seat"] == ids[0], (c, d.get("error")))
    c, d = call("PUT", "/api/admin/accounts/%s/placement" % ids[0], tea, {"classId": "e4a", "grade": "e4"})
    check("講師は、人の口座を直せない", c in (401, 403), c)
    c, d = call("PUT", "/api/admin/accounts/wt01/placement", adm, {"classId": "e4a", "grade": "e4"})
    check("講師の口座には、学年やクラスを付けられない", c == 404, (c, d))
    call("PUT", "/api/admin/accounts/%s/placement" % ids[0], adm, {"grade": "e4", "classId": "e4a", "subjects": ["japanese", "math"]})
    c, st = call("GET", "/api/admin/state", adm)
    kinds = [(r["kind"], r["id"]) for r in st.get("recent", [])]
    check("管理ページの「最近の動き」に、登録と変更が出る（だれの・何から何へ）", ("登録", ids[0]) in kinds and ("変更", ids[0]) in kinds and any("→" in r["text"] for r in st["recent"] if r["kind"] == "変更"), kinds[:6])
    check("最近の動きに、合言葉や内部の ID（sid）は出ない", sid0 not in json.dumps(st["recent"]) and "kazoku" not in json.dumps(st["recent"]))
    row = [x for k in st["classes"] if k["id"] == "e4a" for x in k["seats"] if x["id"] == ids[0]]
    check("クラスの一覧に、その生徒の科目が出る", bool(row) and row[0]["subjects"] == ["japanese", "math"] and row[0]["st"] == "live", row)
    c, d = jpost("/api/join", {"code": st["join"]["code"], "agree": True, "students": [kid]})
    c, st = call("GET", "/api/admin/state", adm)
    prow = [x for k in st["classes"] if k["id"] == "e4a" for x in k["seats"] if x["id"] == d["made"][0]["id"]]
    check("登録の途中の口座は「途中」と出る（渡していない席とは分ける）", bool(prow) and prow[0]["st"] == "pending", prow)
    with T.LOCK:
        asg = T.assignments(SCHOOL)
        asg.pop("hw-j1", None)
        T.save_assignments(SCHOOL, asg)
    forget()

    print("\n組分けの申告（テストの結果が出てから2週間、「クラスは どちらに？」を本人に聞く）")
    import exams as EX
    def day(n):
        return time.strftime("%Y-%m-%d", time.localtime(time.time() + n * 86400))
    tj = login(ids[0], pwj)
    c, d = call("GET", "/api/me", tj)
    check("日程が無いあいだは、何も聞かない", c == 200 and "placeAsk" not in d["profile"], d["profile"].get("placeAsk"))
    c, d = call("PUT", "/api/admin/exams", tea, {"exams": [{"date": day(-9)}]})
    check("講師は日程を入れられない", c in (401, 403), c)
    c, d = call("PUT", "/api/admin/exams", adm, {"exams": [{"date": "2026/10/17"}]})
    check("形のおかしい日付は 400", c == 400, (c, d))
    c, d = call("PUT", "/api/admin/exams", adm, {"exams": [{"date": day(-40)}, {"date": day(3)}, {"date": day(3)}], "resultDays": 7})
    check("日程を入れられる（同じ日は1つに・早い順）", c == 200 and [e["date"] for e in d["state"]["exams"]["items"]] == [day(-40), day(3)] and d["state"]["exams"]["ask"] is None, d["state"].get("exams"))
    c, d = call("GET", "/api/me", tj)
    check("結果が出る前（テストの3日前）・聞く時期を過ぎたテスト（40日前）では、聞かない", "placeAsk" not in d["profile"])
    with T.LOCK:                                   # 登録を10日前のことにする（結果が出る前からいた生徒）
        dbp = T.accounts(SCHOOL)
        for i in ids:
            dbp[i]["created"] = int(time.time()) - 10 * 86400
        T.save_accounts(SCHOOL, dbp)
    c, d = call("PUT", "/api/admin/exams", adm, {"exams": [{"date": day(-40)}, {"date": day(-9)}, {"date": day(26)}]})
    ask = d["state"]["exams"]["ask"]
    check("テストの9日後（結果の2日後）は聞く時期。管理ページに「いま聞いています」と人数", c == 200 and ask and ask["exam"] == day(-9) and ask["fromDay"] == day(-2) and ask["toDay"] == day(11) and ask["answered"] == 0 and ask["total"] >= 2, ask)
    c, d = call("GET", "/api/me", tj)
    pa = d["profile"].get("placeAsk")
    check("生徒の画面に聞くものが届く（どのテスト・いつまで）", bool(pa) and pa["exam"] == day(-9) and pa["toDay"] == day(11), pa)
    c, d = jpost("/api/join", {"code": T.school_meta(SCHOOL)["join"]["code"], "agree": True, "students": [kid]})
    c2, d2 = jpost("/api/join/finish", {"items": [{"id": d["made"][0]["id"], "setup": d["made"][0]["setup"], "verifier": verifier(pwj)}]})
    c, dn = call("GET", "/api/me", login(d["made"][0]["id"], pwj))
    check("結果が出たあとに登録した生徒には、聞かない（登録のときに選んでいる）", c == 200 and "placeAsk" not in dn["profile"], dn["profile"].get("placeAsk"))
    cls0 = T.accounts(SCHOOL)[ids[0]]["classId"]
    c, d = call("PUT", "/api/me/placement", tj, {"classId": cls0, "exam": day(-9)})
    a0 = T.accounts(SCHOOL)[ids[0]]
    check("「変わらない」と答えると、クラスはそのままで、もう聞かれない", c == 200 and d["changed"] == [] and a0["placed"]["exam"] == day(-9) and a0["placed"]["same"] is True and "placeAsk" not in d["profile"], (c, d.get("changed"), a0.get("placed")))
    t1 = login(ids[1], pwj)
    cls1 = T.accounts(SCHOOL)[ids[1]]["classId"]
    other = "e4b" if cls1 == "e4a" else "e4a"
    c, d = call("PUT", "/api/me/placement", t1, {"classId": other, "exam": day(-9)})
    a1 = T.accounts(SCHOOL)[ids[1]]
    check("新しいクラスを答えると、クラスが変わり、もう聞かれない（ID はそのまま）", c == 200 and d["changed"] == ["classId"] and a1["classId"] == other and a1["placed"]["same"] is False and a1["seat"] == ids[1] and "placeAsk" not in d["profile"], (c, d.get("changed")))
    c, d = call("PUT", "/api/me/placement", t1, {"classId": cls1, "exam": "2020-01-01"})
    check("聞いていないテストの日を付けても、ふつうの変更として扱う（答えの印は変わらない）", c == 200 and T.accounts(SCHOOL)[ids[1]]["placed"]["exam"] == day(-9))
    c, st = call("GET", "/api/admin/state", adm)
    check("管理ページの「答えた」が増える。最近の動きに「組分けの答え」", st["exams"]["ask"]["answered"] == 2 and any(r["kind"] == "組分けの答え" for r in st["recent"]), st["exams"]["ask"])
    c, d = call("PUT", "/api/admin/exams", adm, {"exams": [{"date": day(-9)}], "resultDays": 12})
    c, dm = call("GET", "/api/me", login(d["state"] and ids[0], pwj))
    check("結果が出るまでの日数を変えられる（12日なら、9日後はまだ聞かない）", d["state"]["exams"]["resultDays"] == 12 and d["state"]["exams"]["ask"] is None, d["state"]["exams"])
    c, d = call("PUT", "/api/admin/exams", adm, {"exams": [], "resultDays": 7})
    check("日程を全部外せる", c == 200 and d["state"]["exams"]["items"] == [])
    forget()

    print("\n隙間：コマンドとサーバを同時に")
    stop = {"go": True}
    made_http = []

    def hammer():
        while stop["go"]:
            c, d = call("POST", "/api/admin/teachers", adm, {"verifiers": [dummy_v()]})
            if c == 200:
                made_http.extend(m["id"] for m in d["made"])
    th2 = threading.Thread(target=hammer)
    th2.start()
    env = dict(os.environ, MYACADY_ROOT=ROOT)
    cli_ids = []
    for i in range(6):
        lid = "wcli%02d" % i
        r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "add", lid, "C%d" % i,
                            "--school", SCHOOL, "--class", "e4b", "--level", "e4", "--password", "cli-pass-%04d" % i],
                           env=env, capture_output=True, text=True)
        if r.returncode == 0:
            cli_ids.append(lid)
    stop["go"] = False
    th2.join()
    try:
        db = json.load(open(paths.school_file(SCHOOL, "accounts.json"), encoding="utf-8"))
    except ValueError:
        db = None
    check("accounts.json は壊れていない", isinstance(db, dict))
    check("コマンドで足した %d 件が全部残っている" % len(cli_ids), db is not None and len(cli_ids) >= 5 and all(i in db for i in cli_ids), (cli_ids, r.stdout[-200:], r.stderr[-300:]))
    check("画面から足した %d 件も全部残っている" % len(made_http), db is not None and len(made_http) > 0 and all(i in db for i in made_http))
    idx = paths.read_index()
    check("索引にも全部ある", all(idx.get(i) == SCHOOL for i in cli_ids + made_http))
    check("一時ファイルが残っていない", not [f for f in os.listdir(paths.school_dir(SCHOOL)) if f.endswith(".tmp")])

    print("\nコマンドで合言葉を付け替える")
    raw0 = open(paths.school_file(SCHOOL, "accounts.json"), encoding="utf-8").read()
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "passwd", "--all", "--school", SCHOOL], env=env, capture_output=True, text=True)
    check("管理者のいる校舎では、全員ぶんの作り直しをしない（配ったカードを無効にしない）", r.returncode == 1 and open(paths.school_file(SCHOOL, "accounts.json"), encoding="utf-8").read() == raw0, r.stdout[-200:])
    with T.LOCK:
        dbc = T.accounts(SCHOOL)
        dbc["wcli00"]["claim"] = {"at": 1, "exp": int(time.time()) + 999, "by": "wadmin01"}
        T.save_accounts(SCHOOL, dbc)
    tok_c = login("wcli01", "cli-pass-0001")
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "passwd", "wcli00", "tsukekae-mashita-0000", "--school", SCHOOL], env=env, capture_output=True, text=True)
    r2 = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "passwd", "wcli01", "--school", SCHOOL], env=env, capture_output=True, text=True)
    a0 = T.accounts(SCHOOL)["wcli00"]
    check("1人ぶんの付け替えはできる（引き換え待ちの印も外れ、そのまま入れる）", r.returncode == 0 and "claim" not in a0 and "hash" not in a0 and bool(login("wcli00", "tsukekae-mashita-0000")), (r.stdout[-200:], r.stderr[-200:]))
    made_pw = (r2.stdout.strip().split("/ ")[-1] if r2.returncode == 0 else "")
    check("合言葉を書かなければ、3語＋4桁で作る", bool(re.match(r"^[a-z]+-[a-z]+-[a-z]+-\d{4}$", made_pw)) and bool(login("wcli01", made_pw)), r2.stdout[-80:])
    check("付け替えたら、前の合言葉で入ったままの画面は閉じる", call("GET", "/api/me", tok_c)[0] == 401)
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "seed", "--reset", "--empty", "--school", SCHOOL], env=env, capture_output=True, text=True)
    check("本物の校舎は、seed --reset で消さない", r.returncode == 1 and "wadmin01" in T.accounts(SCHOOL) and paths.school_of_login("we4a01") == SCHOOL, r.stdout[-120:])
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "passwd", "--all", "--school", "london"], env=env, capture_output=True, text=True)
    check("デモの校舎では、全員ぶんを作り直せる", r.returncode == 0 and "lj2r02" in r.stdout and login("lj2r02", "demo-no-seito-0002") is None, r.stdout[-200:])
    forget()

    print("\n待機時間：管理者は、触らないと切れる")
    adm2 = login("wadmin01", "kanri-kanri-kanri-0001", admin=True)
    keep = T.ADMIN_IDLE
    with T.LOCK:
        store = T.tokens()
        store[T.token_key(adm2)]["seen"] = int(time.time()) - keep - 5
        T.save_tokens(store)
    c, _ = call("GET", "/api/admin/state", adm2)
    check("30分さわらなかった管理者の画面は閉じる", c == 401, c)
    c, _ = call("GET", "/api/admin/state", adm)
    check("さわっている管理者は続く", c == 200, c)
    adm3 = login("wadmin01", "kanri-kanri-kanri-0001", admin=True)
    old = int(time.time()) - keep + 120
    with T.LOCK:
        store = T.tokens()
        store[T.token_key(adm3)]["seen"] = old
        T.save_tokens(store)
    c, _ = call("GET", "/api/admin/state", adm3, headers={"X-Tube-Quiet": "1"})
    check("画面が裏で回す取り直しは、さわったことにしない（開いたままの画面も30分で切れる）", c == 200 and T.tokens()[T.token_key(adm3)]["seen"] == old, (c, T.tokens()[T.token_key(adm3)]["seen"] - old))
    c, _ = call("GET", "/api/admin/state", adm3)
    check("人が押したときは、さわったことになる", c == 200 and T.tokens()[T.token_key(adm3)]["seen"] > old)
    call("POST", "/api/logout", adm3)
    check("役割ごとの寿命：管理者 ≤ 講師 ＜ 生徒", T.TOKEN_TTL["admin"] <= T.TOKEN_TTL["teacher"] < T.TOKEN_TTL["student"])
    c, _ = call("POST", "/api/logout", adm)
    c, _ = call("GET", "/api/admin/state", adm)
    check("出たあとの合言葉は使えない", c == 401, c)

    print("\n通信：http で来た人は https へ")
    c, data, hd = call("GET", "/", headers={"CF-Visitor": '{"scheme":"http"}', "Host": "tube-study.uk"}, raw=True)
    check("入口は https へ送る", c == 301 and hd.get("Location") == "https://tube-study.uk/", (c, hd.get("Location")))
    c, data, hd = call("GET", "/admin", headers={"X-Forwarded-Proto": "http", "Host": "tube-study.uk"}, raw=True)
    check("管理ページも https へ送る", c == 301 and hd.get("Location") == "https://tube-study.uk/admin", (c, hd.get("Location")))
    c, d = login2("we4a01", "atarashii-aikotoba-9999", headers={"CF-Visitor": '{"scheme":"http"}'})
    check("http では、入る手順を始めさせない", c == 400, c)
    c, data, hd = call("GET", "/", headers={"CF-Visitor": '{"scheme":"http"}', "Host": "evil.example/x?y"}, raw=True)
    check("おかしな Host では送り先を作らない", c == 400, c)
    c, data, hd = call("GET", "/", headers={"CF-Visitor": '{"scheme":"http"}', "Host": "tube-study.uk", "X-Forwarded-Host": "evil.example"}, raw=True)
    check("X-Forwarded-Host は送り先に使わない", c == 301 and hd.get("Location") == "https://tube-study.uk/", hd.get("Location"))
    c, data, hd = call("GET", "/", headers={"X-Forwarded-Proto": "https", "CF-Visitor": '{"scheme":"https"}'}, raw=True)
    check("https なら入口が出て、以後も https（1年）", c == 200 and "max-age=31536000" in (hd.get("Strict-Transport-Security") or ""), hd.get("Strict-Transport-Security"))
    c, data, hd = call("GET", "/", raw=True)
    check("手元（中継なし）の http はそのまま開く", c == 200, c)
    c, data, hd = call("GET", "/admin", raw=True)
    page = data.decode("utf-8", "replace")
    check("管理ページが出る（版つきの js・css）", c == 200 and "js/admin.js?v=" in page and "js/scram.js?v=" in page and "css/admin.css?v=" in page, c)
    check("管理ページにも CSP が付く", "script-src 'self'" in (hd.get("Content-Security-Policy") or ""))
    check("管理ページは外の部品を読まない", "http://" not in page.replace("http://www.w3.org", "") and "https://" not in page)
    c, d = call("GET", "/words.json")
    check("ことばの表が読める（管理ページが使う）", c == 200 and len(d.get("words", [])) == 256, c)

    print("\n本番に切り替える（go-live）：試し運用の生徒を退避して、名簿を空にする。講師・管理者・コース・授業計画は残す")
    forget()
    tok_t = login("wt01", "sensei-pass-0001")
    adm4 = login("wadmin01", "kanri-kanri-kanri-0001", admin=True)
    old_db = T.accounts(SCHOOL)
    staff_sids = {k: v["sid"] for k, v in old_db.items() if v["role"] in ("teacher", "admin")}
    n_students = len([a for a in old_db.values() if a["role"] in ("student", "seat")])
    old_code = T.school_meta(SCHOOL)["join"]["code"]
    with T.LOCK:
        meta = dict(T.school_meta(SCHOOL)); meta["trial"] = True
        paths.save(paths.school_file(SCHOOL, "school.json"), meta)
        ls = json.load(open(paths.school_file(SCHOOL, "lessons.json"), encoding="utf-8"))
        pl = ls["plans"]["e4a:math"]
        pl["students"] = [old_db["we4a01"]["sid"]]
        if not pl.get("lessons"):
            pl["lessons"] = [{"n": 1, "date": "2026-09-01"}]
        pl["lessons"][0]["published"] = "a-old"
        json.dump(ls, open(paths.school_file(SCHOOL, "lessons.json"), "w", encoding="utf-8"))
    def golive(*args, **kw):
        return subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "go-live", "--school", kw.get("school", SCHOOL)] + list(args), env=env, capture_output=True, text=True)
    r = golive()
    check("--yes が無ければ何もしない（何をするかを言う）", r.returncode == 0 and "we4a01" in T.accounts(SCHOOL) and ("%d" % n_students) in r.stdout, r.stdout[-200:])
    r = golive("--yes", school="london")
    check("架空のデモの校舎は切り替えない", r.returncode == 1, r.stdout[-120:])
    r = golive("--yes")
    db = T.accounts(SCHOOL)
    check("切り替わる：生徒と席は1人もいない", r.returncode == 0 and not [k for k, v in db.items() if v["role"] in ("student", "seat")], (r.returncode, r.stdout[-300:], r.stderr[-300:]))
    check("講師と管理者は同じ sid のまま（担当も続く）", all(db.get(k, {}).get("sid") == sid for k, sid in staff_sids.items()), [k for k in staff_sids if k not in db])
    check("入ったままの講師・管理者は続けて使える", call("GET", "/api/me", tok_t)[0] == 200 and call("GET", "/api/admin/state", adm4)[0] == 200)
    check("前の生徒は入れない・索引からも消えている", login("we4a01", pw_a1) is None and paths.school_of_login("we4a01") is None and paths.school_of_login(ids[0]) is None)
    meta = T.school_meta(SCHOOL)
    check("試し運用の印が外れ、本番の印が付き、招待コードが新しくなる", not meta.get("trial") and meta.get("live") is True and meta["join"]["code"] != old_code, meta.get("join"))
    ls2 = json.load(open(paths.school_file(SCHOOL, "lessons.json"), encoding="utf-8"))
    pl2 = ls2["plans"]["e4a:math"]
    check("コースは残り、指名の生徒と「出した印」は外れている（担当の講師は残る）", pl2["students"] == [] and not any(l.get("published") for l in pl2.get("lessons") or []) and pl2.get("teachers") == pl.get("teachers"), (pl2.get("students"), pl2.get("teachers")))
    olds = [n for n in os.listdir(paths.SCHOOLS) if n.startswith(".old-%s-" % SCHOOL)]
    check("前の校舎は退避して残る（消えない）", len(olds) == 1 and "we4a01" in json.load(open(os.path.join(paths.SCHOOLS, olds[0], "accounts.json"), encoding="utf-8")), olds)
    check("前の生徒の記録は新しい校舎に無い・作業場所も残っていない", not os.path.isfile(paths.school_file(SCHOOL, "assignments.json")) and not os.path.isfile(paths.school_file(SCHOOL, "ratings.json")) and not os.path.isdir(os.path.join(ROOT, ".replace-build")))
    J._HITS.clear()
    c, d = call("POST", "/api/join/check", body={"code": old_code})
    c2, d2 = call("POST", "/api/join", body={"code": meta["join"]["code"], "agree": True, "students": [{"grade": "e4", "classId": "e4a", "subjects": ["japanese", "math"]}]})
    check("前の招待コードは使えず、新しいコードで登録が始められる", c == 403 and c2 == 200 and re.match(r"^s-\d{3}$", d2["made"][0]["id"]), (c, c2, d2))
    r = golive("--yes")
    check("もう一度流しても、切り替えずみなら何もしない（--again が要る）", r.returncode == 1 and d2["made"][0]["id"] in T.accounts(SCHOOL), r.stdout[-160:])
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "school-trial", "--school", SCHOOL, "--on"], env=env, capture_output=True, text=True)
    check("本番に切り替えた校舎は、試し運用に戻らない", not T.school_meta(SCHOOL).get("trial"), r.stdout[-120:])
    forget()

    print("\n3か月使われない口座の破棄（ID は空きに戻る・残るのは ID を外した数字だけ）")
    import retire as R
    J._HITS.clear()
    now = int(time.time())
    kid2 = {"grade": "e4", "classId": "e4a", "subjects": ["japanese", "math"]}
    c, d = jpost("/api/join", {"code": T.school_meta(SCHOOL)["join"]["code"], "agree": True, "students": [kid2, kid2, kid2]})
    made = d["made"]
    jpost("/api/join/finish", {"items": [{"id": m["id"], "setup": m["setup"], "verifier": verifier(pwj)} for m in made]})
    old, near, fresh = [m["id"] for m in made]
    tok_old = login(old, pwj)
    c, d = call("GET", "/api/me", tok_old)
    a_old = T.accounts(SCHOOL)[old]
    check("入って何かを開くと、口座に「使った日」が付く", c == 200 and abs(int(a_old.get("used") or 0) - time.time()) < 120, a_old.get("used"))
    sid_old, sid_fresh = a_old["sid"], T.accounts(SCHOOL)[fresh]["sid"]
    with T.LOCK:                                   # この生徒の記録を、置き場という置き場に置く
        asg = T.assignments(SCHOOL)
        asg["hw-r1"] = {"id": "hw-r1", "title": "t", "classId": "e4a", "subject": "math", "students": [sid_old, sid_fresh],
                        "dueAt": (now + 86400) * 1000, "lesson": {"key": "e4a:math", "n": 3}}
        asg["hw-r2"] = {"id": "hw-r2", "title": "t", "classId": "e4a", "subject": "math", "students": [sid_old],
                        "dueAt": (now + 86400) * 1000, "lesson": {"key": "e4a:math", "n": 4}}
        T.save_assignments(SCHOOL, asg)
        rdb = T.ratings(SCHOOL)
        rdb["hw-r1"] = {sid_old: {"v": 4, "s": 5, "at": now, "by": "x"}, sid_fresh: {"v": 3, "s": 3, "at": now, "by": "x"}}
        rdb["hw-r2"] = {sid_old: {"v": 2, "s": 2, "at": now, "by": "x"}}
        T.save_ratings(SCHOOL, rdb)
        paths.save(paths.progress_path(SCHOOL, sid_old), {"sid": sid_old, "rev": 1, "blob": {}})
        paths.save(paths.summary_path(SCHOOL, sid_old), {"n": 10, "answered": 40, "correct": 30, "last": now})
        wdb = T.weak.load(SCHOOL)
        wdb[sid_old] = {"math": {"units": {"比": {"w": 2, "n": 3, "at": now}}}}
        T.weak.save(SCHOOL, wdb)
        T.NOTES.put(SCHOOL, sid_old, "math", "メモ", "t")
        paths.save(paths.school_file(SCHOOL, "messages.json"), {"items": [{"id": "m1", "sid": sid_old, "text": "x"}, {"id": "m2", "sid": sid_fresh, "text": "y"}]})
        paths.save(paths.school_file(SCHOOL, "scores.json"), {"tests": {"t1": {"key": "e4a:math", "kind": "units", "cols": [{"label": "a", "max": 25}],
                                                                              "rows": {sid_old: [20], sid_fresh: [10]}}}})
        os.makedirs(paths.submit_dir(SCHOOL, sid_old), exist_ok=True)
        open(os.path.join(paths.submit_dir(SCHOOL, sid_old), "hw-r1-1.png"), "wb").write(b"png")
        sdb = T.SUB.load(SCHOOL)
        sdb["hw-r1"] = {sid_old: {"at": now, "files": [{"name": "hw-r1-1.png", "kind": "png", "bytes": 3}], "seen": 0, "by": "", "note": ""}}
        T.SUB.save(SCHOOL, sdb)

    def set_used(lid, days, **more):
        with T.LOCK:
            dbu = T.accounts(SCHOOL)
            dbu[lid]["used"] = now - days * 86400
            dbu[lid]["created"] = now - 200 * 86400
            dbu[lid].update(more)
            T.save_accounts(SCHOOL, dbu)
    set_used(old, 93)
    set_used(near, 85)
    check("本番に切り替える前の日は数えない（切り替えた直後は、だれも消えない）", R.run(T, SCHOOL, dry=True) == [])
    meta = dict(T.school_meta(SCHOOL))
    meta["liveAt"] = now - 300 * 86400
    paths.save(paths.school_file(SCHOOL, "school.json"), meta)
    check("93日使われていない口座だけが対象（85日・きょう登録は残る）。見るだけなら消えない", R.run(T, SCHOOL, dry=True) == [old] and old in T.accounts(SCHOOL))
    c, st = call("GET", "/api/admin/state", adm4)
    soon = st["idle"]["soon"]
    check("管理ページ：もうすぐ消える口座と、あと何日", c == 200 and [x["id"] for x in soon] == [old, near] and soon[0]["left"] == 0 and soon[1]["left"] == 7 and st["school"]["live"] is True, st.get("idle"))
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "housekeep", "--dry"], env=env, capture_output=True, text=True)
    check("コマンド housekeep --dry は、消すはずの ID を見せるだけ", r.returncode == 0 and old in r.stdout and old in T.accounts(SCHOOL), r.stdout[-200:] + r.stderr[-200:])
    T.add_account(OTHER, "xs01", "yoso-no-seito-0001", "01", "student", "e4", "e4a")
    with T.LOCK:
        dbo = T.accounts(OTHER)
        dbo["xs01"]["used"] = dbo["xs01"]["created"] = now - 400 * 86400
        T.save_accounts(OTHER, dbo)
    res = T.housekeep_once()
    dbn = T.accounts(SCHOOL)
    check("片づけで破棄される：口座が消え、ID は空きに戻る。ほかの生徒は残る", res[SCHOOL]["retired"] == [old] and old not in dbn and near in dbn and fresh in dbn and paths.school_of_login(old) is None, res)
    check("本番に切り替えていない校舎では、何も消さない", res[OTHER]["retired"] == [] and "xs01" in T.accounts(OTHER), res.get(OTHER))
    check("入ったままだった画面は、そこで止まる", call("GET", "/api/me", tok_old)[0] == 401)
    asg, rdb = T.assignments(SCHOOL), T.ratings(SCHOOL)
    check("宿題の受け取り手から外れる。1人だけの宿題は宿題ごと消える。ほかの生徒の評価は残る",
          asg["hw-r1"]["students"] == [sid_fresh] and "hw-r2" not in asg and rdb["hw-r1"] == {sid_fresh: rdb["hw-r1"][sid_fresh]} and "hw-r2" not in rdb, (asg.get("hw-r1"), list(rdb)))
    msgs = paths.load(paths.school_file(SCHOOL, "messages.json"), {})["items"]
    check("アプリの記録・要約・写真・点・落とした単元・特筆事項・連絡が消える（ほかの生徒のものは残る）",
          not os.path.isfile(paths.progress_path(SCHOOL, sid_old)) and not os.path.isfile(paths.summary_path(SCHOOL, sid_old))
          and not os.path.isdir(paths.submit_dir(SCHOOL, sid_old)) and "hw-r1" not in T.SUB.load(SCHOOL)
          and T.SCORES.load(SCHOOL)["tests"]["t1"]["rows"] == {sid_fresh: [10]} and sid_old not in T.weak.load(SCHOOL)
          and T.NOTES.of_student(SCHOOL, sid_old) == {} and [m["id"] for m in msgs] == ["m2"])
    raw = open(os.path.join(paths.school_dir(SCHOOL), "retired.jsonl"), encoding="utf-8").read()
    kept = [json.loads(x) for x in raw.splitlines() if x.strip()]
    check("残るのは1行の数字だけ：学年・クラスの記号・受講科目・評価・点・落とした単元・アプリの数",
          len(kept) == 1 and kept[0]["grade"] == "e4" and kept[0]["cls"] == "a" and kept[0]["subjects"] == ["japanese", "math"]
          and sorted(kept[0]["hw"]) == [["math", 3, 4, 5], ["math", 4, 2, 2]] and kept[0]["tests"][0]["got"] == [20]
          and kept[0]["weak"] == {"math": [["比", 2, 3]]} and kept[0]["app"] == {"n": 10, "answered": 40, "correct": 30}, kept)
    check("残す数字に、ID も内部の番号も時刻も入っていない", old not in raw and sid_old not in raw and str(now)[:6] not in raw and set(kept[0]) == {"month", "grade", "cls", "subjects", "weeks", "hw", "tests", "weak", "app"}, raw[:200])
    c, st = call("GET", "/api/admin/state", adm4)
    check("管理ページ：これまでに消えた数と、最近の動きに「使われず破棄」", st["idle"]["gone"] == 1 and [x["id"] for x in st["idle"]["soon"]] == [near] and any(x["kind"] == "使われず破棄" and x["id"] == old for x in st["recent"]), st.get("idle"))
    check("もう一度流しても、何も起きない", T.housekeep_once()[SCHOOL]["retired"] == [] and len(open(os.path.join(paths.school_dir(SCHOOL), "retired.jsonl")).read().splitlines()) == 1)
    tok_near = login(near, pwj)
    call("GET", "/api/me", tok_near)
    check("消える前に一度入れば、消えない（使った日が今日になる）", [x["id"] for x in R.view(T, SCHOOL)["soon"]] == [])
    # 退塾から6か月の整理（purge）も、同じ消し方を通る
    set_used(fresh, 1, leftAt=now - 200 * 86400)
    r = subprocess.run([sys.executable, os.path.join(HERE, "tube_server.py"), "purge", "--school", SCHOOL, "--yes"], env=env, capture_output=True, text=True)
    asg = T.assignments(SCHOOL)
    # hw-r1 は期限前なので、入った生徒（near）が受け取り手に足される（入るたびに join_open_homework。10-10）。
    # 消えるのは fresh の受け取り。受け取り手が 0 人になれば宿題ごと消える。
    check("在籍終了から6か月の整理（purge）も、連絡・宿題の受け取り手まで消す", r.returncode == 0 and fresh not in T.accounts(SCHOOL)
          and sid_fresh not in ((asg.get("hw-r1") or {}).get("students") or [])
          and paths.load(paths.school_file(SCHOOL, "messages.json"), {})["items"] == [] and paths.school_of_login(fresh) is None,
          (r.stdout[-200:] + r.stderr[-200:], (asg.get("hw-r1") or {}).get("students")))
    forget()

    print("\n学年の繰り上げ（新年度のはじまりの日に、1回だけ。中3は卒業・小6→中1 は本人に聞く）")
    paths.save(paths.school_file(SCHOOL, "curriculum.json"), {"v": 2, "classes": [
        {"id": "e4a", "name": "小4α", "grade": "e4"}, {"id": "e4b", "name": "小4β", "grade": "e4"},
        {"id": "e5a", "name": "小5α", "grade": "e5"}, {"id": "e5b", "name": "小5β", "grade": "e5"},
        {"id": "e6a", "name": "小6α", "grade": "e6"},
        {"id": "j1t", "name": "中1T", "grade": "j1"}, {"id": "j1r", "name": "中1R", "grade": "j1"},
        {"id": "j2t", "name": "中2T", "grade": "j2"}, {"id": "j3t", "name": "中3T", "grade": "j3"}]})
    pwr = "kuriage-no-kensa-0001"
    rows = [("wr4a", "e4", "e4a"), ("wr4b", "e4", "e4b"), ("wr5a", "e5", "e5a"), ("wr5b", "e5", "e5b"), ("wr6a", "e6", "e6a"),
            ("wr1t", "j1", "j1t"), ("wr2t", "j2", "j2t"), ("wr3t", "j3", "j3t"), ("wrleft", "e4", "e4a")]
    for i, (lid, lv, cid) in enumerate(rows):
        T.add_account(SCHOOL, lid, pwr, "%02d" % (i + 40), "student", lv, cid, subjects=["japanese", "math"])
    with T.LOCK:
        dby = T.accounts(SCHOOL)
        dby["wrleft"]["leftAt"] = now - 86400
        T.save_accounts(SCHOOL, dby)
        asg = T.assignments(SCHOOL)
        asg["hw-y1"] = {"id": "hw-y1", "title": "t", "classId": "e4a", "subject": "math", "students": [dby["wr4a"]["sid"]],
                        "dueAt": (now + 5 * 86400) * 1000, "lesson": {"key": "e4a:math", "n": 9}}
        T.save_assignments(SCHOOL, asg)
    def acc(lid):
        return T.accounts(SCHOOL)[lid]
    def yday(n):
        return time.strftime("%Y-%m-%d", time.localtime(time.time() + n * 86400))
    call("PUT", "/api/admin/exams", adm4, {"exams": [{"date": yday(30)}]})
    c, d = call("PUT", "/api/admin/exams", tok_t, {"yearStart": yday(1)})
    check("講師は、新年度の日付を入れられない", c in (401, 403), c)
    bad = [call("PUT", "/api/admin/exams", adm4, {"yearStart": v})[0] for v in (yday(0), yday(-3), "2027/02/06", "あした")]
    check("きょう・過去・形のおかしい日付は入らない（押しまちがいで全員が上がらない）", bad == [400, 400, 400, 400] and EX.year_start(SCHOOL) == "", bad)
    c, d = call("PUT", "/api/admin/exams", adm4, {"yearStart": yday(1)})
    check("あした以降の日なら入る。組分けテストの日程はそのまま", c == 200 and d["state"]["exams"]["yearStart"] == yday(1) and [e["date"] for e in d["state"]["exams"]["items"]] == [yday(30)], (c, d.get("error")))
    res = T.housekeep_once()
    check("その日までは、何も変わらない", res[SCHOOL]["rolled"] is None and acc("wr4a")["level"] == "e4" and not T.school_meta(SCHOOL).get("rolled"), res.get(SCHOOL))
    tomorrow = time.time() + 86400 + 3600
    got = R.roll(T, SCHOOL, now=tomorrow)
    n_up = len([1 for a in T.accounts(SCHOOL).values() if a.get("role") == "student" and not a.get("leftAt")]) - 1
    check("その日になると繰り上がる：上がった人数・卒業・クラスを聞く人数", got and got["date"] == yday(1) and got["grad"] == 1 and got["ask"] == 1 and got["up"] == n_up, got)
    lv = {lid: (acc(lid)["level"], acc(lid)["classId"]) for lid, _l, _c in rows}
    check("同じ記号のクラスへ上がる（小4α→小5α・小4β→小5β・中1T→中2T・中2T→中3T）",
          lv["wr4a"] == ("e5", "e5a") and lv["wr4b"] == ("e5", "e5b") and lv["wr1t"] == ("j2", "j2t") and lv["wr2t"] == ("j3", "j3t"), lv)
    check("行き先の学年にクラスが1つなら、そこへ（小5α・小5β → 小6α）", lv["wr5a"] == ("e6", "e6a") and lv["wr5b"] == ("e6", "e6a"), lv)
    check("小6→中1 は、クラスを空にして本人に聞く", lv["wr6a"] == ("j1", "") and acc("wr6a").get("needClass") == yday(1), acc("wr6a").get("needClass"))
    check("中3は卒業：クラスから外れる（学年はそのまま・入れる）", lv["wr3t"] == ("j3", "") and acc("wr3t").get("grad") == yday(1) and not acc("wr3t").get("leftAt"))
    check("在籍を終えた生徒は動かさない", lv["wrleft"] == ("e4", "e4a"))
    check("登録で入った生徒（ID が s-）も同じように上がる", acc(near)["level"] == "e5" and acc(near)["classId"] == "e5a" and acc(near)["seat"] == near)
    check("前のクラスが残る（前のクラスの成績の表からは、出ていった生徒として外れる）", T.moved_out(acc("wr4a"), ["e4a"]) and not T.moved_out(acc("wr4a"), ["e5a"]) and T.moved_out(acc("wr3t"), ["j3t"]))
    check("出してあった宿題の受け取り手は、そのまま", T.assignments(SCHOOL)["hw-y1"]["students"] == [acc("wr4a")["sid"]])
    check("もう一度流しても、同じ年には繰り上がらない", R.roll(T, SCHOOL, now=tomorrow + 7200) is None and T.housekeep_once()[SCHOOL]["rolled"] is None and acc("wr4a")["level"] == "e5")
    c, st = call("GET", "/api/admin/state", adm4)
    ex = st["exams"]
    check("管理ページ：この前の繰り上げ・まだ答えていない人数・クラスの決まっていない生徒・最近の動き",
          ex["rolled"]["date"] == yday(1) and ex["yearWait"] == 1 and sorted((x["id"], x["st"]) for x in st["loose"]) == [("wr3t", "grad"), ("wr6a", "ask")]
          and any(x["kind"] == "学年の繰り上げ" for x in st["recent"]), (ex.get("rolled"), st.get("loose")))
    c, d = call("PUT", "/api/admin/exams", adm4, {"yearStart": yday(40)})
    check("繰り上げた年に、別の日付は入らない（1年に1回）", c == 400 and EX.year_start(SCHOOL) == "", (c, d.get("error")))
    t6 = login("wr6a", pwr)
    c, d = call("GET", "/api/me", t6)
    pa = d["profile"].get("placeAsk")
    check("小6→中1 の生徒のホームに「中1のクラスは？」が届く", c == 200 and d["profile"]["level"] == "j1" and d["profile"]["classId"] == "" and pa and pa.get("year") == yday(1), d.get("profile"))
    c, d = call("PUT", "/api/me/placement", t6, {"classId": "e6a"})
    check("前の学年のクラスは選べない", c == 400, (c, d.get("error")))
    c, d = call("PUT", "/api/me/placement", t6, {"classId": "j1r"})
    a6 = acc("wr6a")
    check("答えると、新しいクラスに入り、もう聞かれない", c == 200 and a6["classId"] == "j1r" and "needClass" not in a6 and "placeAsk" not in d["profile"] and a6["moves"][-1]["to"]["classId"] == "j1r", (c, d.get("error")))
    t3 = login("wr3t", pwr)
    c, d = call("GET", "/api/me", t3)
    check("卒業した生徒は入れる。卒業の印が届き、クラスは聞かれない", c == 200 and d["profile"].get("grad") is True and "placeAsk" not in d["profile"], d.get("profile"))
    c, d = call("PUT", "/api/admin/accounts/wr3t/placement", adm4, {"grade": "j3", "classId": "j3t", "subjects": ["japanese", "math"]})
    check("まちがいなら、管理者（本人も）がクラスを選び直せる。卒業の印が外れる", c == 200 and acc("wr3t")["classId"] == "j3t" and "grad" not in acc("wr3t"), (c, d.get("error")))
    EX.set_year_start(SCHOOL, yday(400))
    got = R.roll(T, SCHOOL, now=time.time() + 401 * 86400)
    check("次の年は、また繰り上がる（中2T→中3T だった生徒は卒業）", got and got["date"] == yday(400) and acc("wr2t").get("grad") == yday(400) and acc("wr4a")["level"] == "e6" and acc("wr4a")["classId"] == "e6a", got)
    forget()

    httpd.shutdown()


def main():
    setup()
    unit_checks()
    server_checks()
    print()
    if ng_n:
        print("× %d件 通っていません（%d件は通過）" % (ng_n, ok_n))
        return 1
    print("test_admin: すべて通った。（%d件）" % ok_n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
