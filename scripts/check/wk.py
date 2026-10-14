# -*- coding: utf-8 -*-
"""Safari と同じ WebKit を裏で動かす道具（cdp.Chrome と同じ形で使える）。

    TUBE_BROWSER=webkit python3 scripts/check/expect.py …      # cdp.py が Chrome の代わりにこれを使う

Safari のアプリそのものは「リモートオートメーションを許可」が切だと機械から動かせない。ここでは
この Mac の WebKit（Safari と同じエンジン）を wk.swift で直に動かす。本人の Safari には触れない。
**確かめられるもの**：JS のエラー・CSP・レイアウト・WebKit だけの挙動（日付の読み方・動画の自動再生の決まり）。
**確かめられないもの**：Safari のアプリの部品（合言葉を保存する吹き出し・Face ID の自動入力・タブバー）と、iPhone の指。

はじめの1回だけ swiftc で組み立てる（数十秒。置き場は一時領域）。
"""
import hashlib, json, os, subprocess, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "wk.swift")
IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")


def _binary():
    h = hashlib.sha256(open(SRC, "rb").read()).hexdigest()[:12]
    out = os.path.join(tempfile.gettempdir(), "tube-wk-%s" % h)
    if not os.path.isfile(out):
        r = subprocess.run(["swiftc", "-O", SRC, "-o", out], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("wk.swift を組み立てられません:\n" + r.stderr[-2000:])
    return out


class WebKit:
    def __init__(self, width=1440, height=900, scale=2, port=None, mobile=False):
        self.width, self.height, self.mobile = width, height, mobile
        self.proc = None
        self.log = None

    def __enter__(self):
        self.log = tempfile.TemporaryFile()
        self.proc = subprocess.Popen([_binary(), str(self.width), str(self.height), IPHONE_UA if self.mobile else ""],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log)
        self._call({"op": "eval", "js": "1"})
        return self

    def __exit__(self, *a):
        try:
            self.proc.stdin.write(b'{"op":"quit"}\n'); self.proc.stdin.flush(); self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()

    def _call(self, cmd):
        self.proc.stdin.write((json.dumps(cmd) + "\n").encode("utf-8")); self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("WebKit の道具が止まりました")
        return json.loads(line.decode("utf-8"))

    def page_errors(self):
        """ページで起きた JS のエラー・CSP 違反（wk.swift がページのはじめに仕込む）。"""
        return self.eval("JSON.stringify(window.__wkerrs || [])") and json.loads(self.eval("JSON.stringify(window.__wkerrs || [])"))

    def goto(self, url, wait=1.5):
        self._call({"op": "goto", "url": url})
        for _ in range(100):
            try:
                if self.eval("document.readyState") == "complete":
                    break
            except RuntimeError:
                pass
            time.sleep(0.1)
        time.sleep(wait)

    def eval(self, expr, wait_promise=False):
        r = self._call({"op": "eval", "js": expr, "await": bool(wait_promise)})
        if not r.get("ok"):
            raise RuntimeError(r.get("error") or "eval")
        return r.get("value")

    def shot(self, path, full=False):
        if full:
            h = int(self.eval("document.documentElement.scrollHeight") or self.height)
            self._call({"op": "size", "w": self.width, "h": min(h, 12000)})
        r = self._call({"op": "shot", "path": path})
        if full:
            self._call({"op": "size", "w": self.width, "h": self.height})
        if not r.get("ok"):
            raise RuntimeError(r.get("error") or "shot")
        return path

    def wait_for(self, expr, timeout=15):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.eval(expr):
                    return True
            except RuntimeError:
                pass
            time.sleep(0.2)
        return False
