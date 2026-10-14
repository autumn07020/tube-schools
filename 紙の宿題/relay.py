#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紙の宿題 ―― 画面を配り、tubestudy の口を取り次ぐだけの中継（Python 標準ライブラリだけ）。

    python3 relay.py                                   # 手元のデモ（127.0.0.1:8932）へつなぐ
    python3 relay.py --tube https://tube-study.uk      # 本番の tubestudy へつなぐ
    python3 relay.py --host 0.0.0.0 --port 8940        # 同じ Wi-Fi の iPad から開く（下の注意）

なぜ中継が要るか
----------------
tubestudy は、別の住所の画面からの呼び出しを許す返事（CORS）を出さない。tubestudy に一切手を入れずに
その口を使うには、画面と同じ住所に「取り次ぐだけの口」を置くしかない。

決めごと（tubestudy の良さを崩さないために）
------------------------------------------
* **決まった口だけを通す**（ROUTES）。それ以外は 404。講師の画面が使う口と同じもので、新しい権限は作らない。
  誰が何を見てよいかは、今までどおり tubestudy が合言葉から決める。
* **何も保存しない。** 答案も合言葉も、この中継のディスクには書かない。ログには口の名前と結果の番号だけ。
* 合言葉は画面が持ち、1回ごとに Authorization の見出しで渡す。中継は覚えない。
* tubestudy からの転送（リダイレクト）には従わない。行き先は --tube の1か所だけ。
* 画面のファイルは web/ の中の決まった形だけを配る。一覧も隠しファイルも出さない。

注意
----
--host 0.0.0.0 は、同じ Wi-Fi の端末から http:// で開くためのもの。**合言葉が暗号化されずに流れる。**
家の Wi-Fi で試すときだけにし、校舎では HTTPS の置き場（README の「置き方」）を使う。
"""

import argparse
import json
import mimetypes
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")

SEG = r"[A-Za-z0-9_-]{1,40}"
# (方法, 道の形, 名前（ログに出すのはこれだけ）, 問い合わせを通すか)
ROUTES = [
    # 入る手順（合言葉そのものは送らない。tubestudy の server/scram.py・web/js/scram.js）
    ("POST", r"^/api/login/start$", "login", False),
    ("POST", r"^/api/login/finish$", "login", False),
    ("POST", r"^/api/logout$", "logout", False),
    ("GET", r"^/api/me$", "me", False),
    ("GET", r"^/api/today$", "today", False),
    ("GET", r"^/api/check$", "check", True),
    ("PUT", r"^/api/check/rate$", "rate", False),
    ("GET", r"^/api/rev$", "rev", False),
    ("POST", r"^/api/quiz$", "quiz", False),
    ("GET", r"^/api/submissions/%s/%s/(?!print$|pdf$|scan$|return$|seen$)[A-Za-z0-9_.-]{1,80}$" % (SEG, SEG), "image", False),
    ("POST", r"^/api/submissions/%s/%s/scan$" % (SEG, SEG), "scan", False),
    ("POST", r"^/api/submissions/%s/%s/return$" % (SEG, SEG), "return", False),
]
ROUTES = [(m, re.compile(p), n, q) for m, p, n, q in ROUTES]
QUERY_OK = re.compile(r"^[A-Za-z0-9_=&:%.-]{0,200}$")
MAX_BODY = 12 * 1024 * 1024 + 64 * 1024           # tubestudy の上限（12MB）より少しだけ大きく
PASS_TYPES = ("application/json", "image/jpeg", "image/png", "application/pdf")
STATIC_EXT = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
              ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
              ".ico": "image/x-icon", ".json": "application/json"}

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; worker-src 'self' blob:; "
       "form-action 'none'; base-uri 'none'; frame-ancestors 'none'")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


class Relay(BaseHTTPRequestHandler):
    server_version = "tube-paper-relay/1"
    sys_version = ""
    tube = "http://127.0.0.1:8932"
    quiet = False

    # --- ログ：口の名前と結果だけ。道（sid が入る）・問い合わせ・合言葉・中身は書かない ---
    def log_message(self, fmt, *args):
        pass

    def note(self, name, code):
        if not self.quiet:
            sys.stderr.write("%s %s %s %d\n" % (time.strftime("%H:%M:%S"), self.command, name, code))

    def head(self, code, ctype, n, api=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(n))
        self.send_header("Cache-Control", "no-store" if api else "no-cache")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def reply(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.head(code, "application/json; charset=utf-8", len(raw), api=True)
        self.wfile.write(raw)

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def do_DELETE(self):
        self.route("DELETE")

    def route(self, method):
        raw = self.path or "/"
        path, _, query = raw.partition("?")
        if path.startswith("/api/"):
            return self.relay(method, path, query)
        if path == "/health" and method == "GET":
            return self.reply(200, {"ok": True, "tube": urllib.parse.urlparse(self.tube).netloc})
        if method != "GET":
            return self.reply(405, {"error": "method"})
        return self.static(path)

    # --- 画面のファイル ---
    def static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        rel = urllib.parse.unquote(path).lstrip("/")
        if (".." in rel or "\\" in rel or rel.startswith(".") or "/." in rel
                or os.path.splitext(rel)[1] not in STATIC_EXT):
            return self.reply(404, {"error": "not-found"})
        p = os.path.abspath(os.path.join(WEB, rel))
        if os.path.commonpath([p, WEB]) != WEB or not os.path.isfile(p):
            return self.reply(404, {"error": "not-found"})
        with open(p, "rb") as f:
            data = f.read()
        self.head(200, STATIC_EXT[os.path.splitext(rel)[1]], len(data))
        self.wfile.write(data)

    # --- tubestudy の口を取り次ぐ ---
    def relay(self, method, path, query):
        hit = None
        for m, pat, name, q_ok in ROUTES:
            if m == method and pat.match(path):
                hit = (name, q_ok)
                break
        if not hit:
            self.note("blocked", 404)
            return self.reply(404, {"error": "この口は中継していません"})
        name, q_ok = hit
        if query and not (q_ok and QUERY_OK.match(query)):
            query = ""
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            # 読み捨ててから断る。読まずに断ると、送り手には「回線が切れた」に見える（本当の理由が伝わらない）。
            left = min(n, 64 * 1024 * 1024)
            while left > 0:
                chunk = self.rfile.read(min(left, 1024 * 1024))
                if not chunk:
                    break
                left -= len(chunk)
            self.note(name, 413)
            self.close_connection = True
            return self.reply(413, {"error": "大きすぎます。枚数を減らして送ってください"})
        body = self.rfile.read(n) if n > 0 else None
        url = self.tube.rstrip("/") + path + ("?" + query if query else "")
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("User-Agent", "tube-paper-relay/1")
        req.add_header("Accept", "application/json, image/*")
        auth = self.headers.get("Authorization") or ""
        if auth.startswith("Bearer ") and len(auth) < 300:
            req.add_header("Authorization", auth)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with OPENER.open(req, timeout=90) as r:
                code, data, ctype = r.status, r.read(), r.headers.get("Content-Type") or ""
        except urllib.error.HTTPError as e:
            code, data, ctype = e.code, e.read(), e.headers.get("Content-Type") or ""
        except (urllib.error.URLError, OSError, ValueError) as e:
            why = getattr(e, "reason", e)
            if isinstance(why, ssl.SSLError) or "CERTIFICATE" in str(why).upper():
                self.note(name + " ssl", 502)
                return self.reply(502, {"error": "tubestudy の証明書を確かめられません（中継の置き場の設定。README の「つながらないとき」）"})
            self.note(name, 502)
            return self.reply(502, {"error": "tubestudy につながりません。回線を確かめて、もう一度"})
        base = ctype.split(";")[0].strip().lower()
        if base not in PASS_TYPES:
            self.note(name, 502)
            return self.reply(502, {"error": "tubestudy から思わない返事が来ました（%d）" % code})
        self.note(name, code)
        self.head(code, ctype, len(data), api=True)
        self.wfile.write(data)


def main(argv=None):
    ap = argparse.ArgumentParser(description="紙の宿題の中継")
    ap.add_argument("--tube", default=os.environ.get("TUBE_BASE") or "http://127.0.0.1:8932",
                    help="つなぐ tubestudy（既定は手元のデモ 127.0.0.1:8932）")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8940)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    u = urllib.parse.urlparse(a.tube)
    if u.scheme not in ("http", "https") or not u.netloc or u.path not in ("", "/"):
        print("--tube は https://tube-study.uk の形で指定してください")
        return 2
    Relay.tube = "%s://%s" % (u.scheme, u.netloc)
    Relay.quiet = a.quiet
    ThreadingHTTPServer.request_queue_size = 128
    ThreadingHTTPServer.daemon_threads = True
    srv = ThreadingHTTPServer((a.host, a.port), Relay)
    print("紙の宿題: http://%s:%d/  →  %s" % ("127.0.0.1" if a.host == "127.0.0.1" else a.host, a.port, Relay.tube))
    if a.host not in ("127.0.0.1", "localhost", "::1"):
        print("  注意: 外の端末から http:// で開けます。合言葉が暗号化されずに流れます。家の Wi-Fi で試すときだけに。")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
