# -*- coding: utf-8 -*-
"""Chrome を裏で動かして、画面を撮る・JS を走らせる最小の道具（外部ライブラリなし）。

    from cdp import Chrome
    with Chrome(width=1440, height=900) as c:
        c.goto("http://127.0.0.1:8932/")
        c.eval("document.title")
        c.shot("out.png")
"""
import base64, json, os, socket, shutil, struct, subprocess, tempfile, time, urllib.request

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class WS:
    def __init__(self, url):
        host, rest = url[5:].split("/", 1)
        h, p = host.split(":")
        self.s = socket.create_connection((h, int(p)), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        req = ("GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (rest, host, key))
        self.s.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.s.recv(4096)
        self.buf = buf.split(b"\r\n\r\n", 1)[1]
        self.n = 0
        self.events = []

    def send(self, obj):
        data = json.dumps(obj).encode()
        head = bytearray([0x81])
        L = len(data)
        if L < 126: head.append(0x80 | L)
        elif L < 65536: head.append(0x80 | 126); head += struct.pack(">H", L)
        else: head.append(0x80 | 127); head += struct.pack(">Q", L)
        mask = os.urandom(4)
        head += mask
        self.s.sendall(bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(65536)
            if not chunk:
                raise IOError("closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        while True:
            b1, b2 = self._read(2)
            op = b1 & 0x0F
            L = b2 & 0x7F
            if L == 126: L = struct.unpack(">H", self._read(2))[0]
            elif L == 127: L = struct.unpack(">Q", self._read(8))[0]
            if b2 & 0x80: self._read(4)
            payload = self._read(L)
            if op == 1:
                return json.loads(payload.decode("utf-8"))
            if op == 8:
                raise IOError("closed")

    def call(self, method, params=None, timeout=60):
        self.n += 1
        mid = self.n
        self.send({"id": mid, "method": method, "params": params or {}})
        t0 = time.time()
        while True:
            m = self.recv()
            if "method" in m:
                self.events.append(m)
                if len(self.events) > 500: self.events = self.events[-300:]
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})
            if time.time() - t0 > timeout:
                raise TimeoutError(method)


class Chrome:
    def __init__(self, width=1440, height=900, scale=2, port=None, mobile=False):
        self.width, self.height, self.scale, self.mobile = width, height, scale, mobile
        self.port = port or (9300 + os.getpid() % 500)
        self.prof = tempfile.mkdtemp(prefix="cdp-")
        self.proc = None
        self.ws = None

    def __enter__(self):
        self.proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                                      "--remote-debugging-port=%d" % self.port, "--user-data-dir=%s" % self.prof,
                                      "--window-size=%d,%d" % (self.width, self.height), "--hide-scrollbars",
                                      "--disable-features=TranslateUI", "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % self.port, timeout=2))
                page = [t for t in tabs if t.get("type") == "page"][0]
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("chrome did not start")
        self.ws = WS(page["webSocketDebuggerUrl"])
        self.ws.call("Page.enable"); self.ws.call("Runtime.enable")
        self.ws.call("Emulation.setDeviceMetricsOverride", {"width": self.width, "height": self.height,
                                                             "deviceScaleFactor": self.scale, "mobile": self.mobile})
        if self.mobile:
            self.ws.call("Emulation.setTouchEmulationEnabled", {"enabled": True})
        return self

    def __exit__(self, *a):
        try: self.proc.terminate(); self.proc.wait(timeout=10)
        except Exception: self.proc.kill()
        shutil.rmtree(self.prof, ignore_errors=True)

    def goto(self, url, wait=1.5):
        self.ws.call("Page.navigate", {"url": url})
        for _ in range(100):
            r = self.ws.call("Runtime.evaluate", {"expression": "document.readyState", "returnByValue": True})
            if r.get("result", {}).get("value") == "complete":
                break
            time.sleep(0.1)
        time.sleep(wait)

    def eval(self, expr, wait_promise=False):
        r = self.ws.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": wait_promise})
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description") or r["exceptionDetails"].get("text"))
        return r.get("result", {}).get("value")

    def shot(self, path, full=False):
        params = {"format": "png"}
        if full:
            h = self.eval("document.documentElement.scrollHeight")
            params["clip"] = {"x": 0, "y": 0, "width": self.width, "height": h, "scale": 1}
            params["captureBeyondViewport"] = True
        data = self.ws.call("Page.captureScreenshot", params, timeout=120)["data"]
        open(path, "wb").write(base64.b64decode(data))
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
