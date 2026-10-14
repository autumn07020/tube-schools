#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中継（relay.py）の決めごとを確かめる。偽の tubestudy を立て、そこへ取り次がせる。

  ・決まった口だけを通す（講師の画面が使う口）。ほかは 404。印刷の紙・PDF・見た印・名簿は通さない
  ・合言葉（Authorization）は Bearer だけを渡す。Cookie や X-Forwarded-For は渡さない
  ・問い合わせ（?key=）は宿題チェックの一覧にだけ渡す
  ・中身は渡すが、ログには口の名前と結果の番号しか書かない（道・sid・合言葉・中身を書かない）
  ・tubestudy からの転送（リダイレクト）には従わない
  ・画面のファイルは web/ の中の決まった形だけ。隠しファイル・道の外・一覧は出さない。CSP を付ける
  ・大きすぎる本文は 413、つながらなければ 502

    python3 紙の宿題/検査/test_relay.py
"""
import io
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import relay  # noqa: E402

ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   %s" % name)
    else:
        ng_n += 1
        print("  ×    %s  %s" % (name, detail))


SEEN = []


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def any(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        SEEN.append({"method": self.command, "path": self.path, "headers": dict(self.headers), "body": body})
        if self.path.startswith("/api/redirect"):
            self.send_response(302)
            self.send_header("Location", "http://example.com/")
            self.end_headers()
            return
        if self.path.startswith("/api/submissions/A1/S1/p1.jpg"):
            data = b"\xff\xd8\xff\xd9"
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path.startswith("/api/weird"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html>")
            return
        raw = json.dumps({"ok": True, "path": self.path}).encode()
        self.send_response(401 if self.headers.get("Authorization") != "Bearer good" and not self.path.startswith("/api/login/") else 200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    do_GET = do_POST = do_PUT = do_DELETE = any


def serve(handler, port):
    s = ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    return s


def req(method, url, body=None, headers=None):
    r = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(r, timeout=10) as res:
            return res.status, res.read(), dict(res.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def main():
    fake = serve(Fake, 8971)
    relay.Relay.tube = "http://127.0.0.1:8971"
    relay.Relay.quiet = False
    err = io.StringIO()
    old = sys.stderr
    sys.stderr = err
    rs = serve(relay.Relay, 8972)
    B = "http://127.0.0.1:8972"
    try:
        print("\n通す口")
        code, body, h = req("POST", B + "/api/login/start", json.dumps({"id": "t", "cnonce": "c" * 24}).encode(), {"Content-Type": "application/json"})
        check("入る手順（始め）を通す", code == 200 and SEEN[-1]["path"] == "/api/login/start", code)
        check("本文をそのまま渡す", json.loads(SEEN[-1]["body"]) == {"id": "t", "cnonce": "c" * 24})
        code, body, h = req("POST", B + "/api/login/finish", json.dumps({"id": "t", "nonce": "n", "proof": "0" * 64}).encode(), {"Content-Type": "application/json"})
        check("入る手順（続き）を通す", code == 200 and SEEN[-1]["path"] == "/api/login/finish", code)
        code, body, h = req("POST", B + "/api/login", json.dumps({"id": "t", "password": "p"}).encode(), {"Content-Type": "application/json"})
        check("前の口（合言葉そのものを送る形）は通さない", code == 404, code)
        code, body, h = req("GET", B + "/api/check?key=e4b:japanese&n=12", headers={"Authorization": "Bearer good"})
        check("宿題チェックの一覧に問い合わせを渡す", SEEN[-1]["path"] == "/api/check?key=e4b:japanese&n=12", SEEN[-1]["path"])
        check("返事は no-store", h.get("Cache-Control") == "no-store", h.get("Cache-Control"))
        code, body, h = req("GET", B + "/api/me?x=1", headers={"Authorization": "Bearer good", "Cookie": "a=b", "X-Forwarded-For": "1.2.3.4"})
        check("ほかの口には問い合わせを渡さない", SEEN[-1]["path"] == "/api/me", SEEN[-1]["path"])
        hd = {k.lower(): v for k, v in SEEN[-1]["headers"].items()}
        check("合言葉は渡す", hd.get("authorization") == "Bearer good")
        check("Cookie と X-Forwarded-For は渡さない", "cookie" not in hd and "x-forwarded-for" not in hd, hd)
        code, body, h = req("GET", B + "/api/submissions/A1/S1/p1.jpg", headers={"Authorization": "Bearer good"})
        check("答案の画像を通す（image/jpeg）", code == 200 and body == b"\xff\xd8\xff\xd9" and h.get("Content-Type") == "image/jpeg", (code, h.get("Content-Type")))
        for m, p in [("POST", "/api/submissions/A1/S1/scan"), ("POST", "/api/submissions/A1/S1/return"),
                     ("PUT", "/api/check/rate"), ("GET", "/api/today"), ("POST", "/api/quiz"), ("POST", "/api/logout")]:
            n0 = len(SEEN)
            req(m, B + p, b"{}", {"Authorization": "Bearer good", "Content-Type": "application/json"})
            check("%s %s を通す" % (m, p), len(SEEN) == n0 + 1 and SEEN[-1]["path"] == p)

        print("\n通さない口")
        for m, p in [("GET", "/api/submissions/A1/S1/print"), ("GET", "/api/submissions/A1/S1/pdf"),
                     ("PUT", "/api/submissions/A1/S1/seen"), ("GET", "/api/roster"), ("POST", "/api/roster/bulk"),
                     ("GET", "/api/p/S1"), ("PUT", "/api/lessons/use"), ("DELETE", "/api/scores/x"),
                     ("GET", "/api/submissions/A1"), ("POST", "/api/submissions/A1"), ("GET", "/api/hw/outbox"),
                     ("GET", "/api/check/../roster"), ("GET", "/api/redirect")]:
            n0 = len(SEEN)
            code, body, h = req(m, B + p, b"{}" if m != "GET" else None, {"Authorization": "Bearer good"})
            check("%s %s は 404（tubestudy に届かない）" % (m, p), code == 404 and len(SEEN) == n0, (code, len(SEEN) - n0))

        print("\n画面のファイル")
        code, body, h = req("GET", B + "/")
        check("入口を配る", code == 200 and b"<title>" in body)
        check("CSP を付ける", "default-src 'self'" in (h.get("Content-Security-Policy") or ""), h.get("Content-Security-Policy"))
        check("枠の中に置かせない", h.get("X-Frame-Options") == "DENY")
        for p in ["/.git/config", "/../relay.py", "/js/", "/js", "/%2e%2e/relay.py", "/relay.py", "/web/index.html"]:
            code, body, h = req("GET", B + p)
            check("%s は出さない" % p, code == 404, code)

        print("\n困ったとき")
        code, body, h = req("POST", B + "/api/submissions/A1/S1/scan", b"x" * (relay.MAX_BODY + 10),
                            {"Authorization": "Bearer good", "Content-Type": "application/json"})
        check("大きすぎる本文は 413", code == 413, code)
        code, body, h = req("GET", B + "/api/rev", headers={"Authorization": "Bearer good"})
        check("通した口の返事はそのまま（401 も）", code == 200)
        code, body, h = req("GET", B + "/api/me", headers={"Authorization": "Bearer bad"})
        check("tubestudy の 401 をそのまま返す", code == 401, code)
        fake.shutdown()
        fake.server_close()
        time.sleep(0.2)
        code, body, h = req("GET", B + "/api/me", headers={"Authorization": "Bearer good"})
        check("つながらなければ 502", code == 502 and "つながりません" in body.decode(), code)
    finally:
        sys.stderr = old
        rs.shutdown()
    log = err.getvalue()
    print("\nログ")
    check("ログに合言葉・sid・答案の名前・中身が無い",
          "good" not in log and "S1" not in log and "p1.jpg" not in log and "e4b" not in log and "password" not in log, log[:300])
    check("ログは口の名前と番号だけ", all(len(l.split()) == 4 for l in log.strip().splitlines()), log[:300])
    print("\n%s。（%d件）" % ("すべて通った" if not ng_n else "× %d件" % ng_n, ok_n + ng_n))
    return 1 if ng_n else 0


if __name__ == "__main__":
    sys.exit(main())
