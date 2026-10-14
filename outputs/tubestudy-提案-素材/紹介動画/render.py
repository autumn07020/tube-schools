# promo.html を 30fps で 900 コマ撮り、frames/ に PNG で置く（Chrome の DevTools を使う）
import base64, os, sys, time
import re, types
_src = open("/private/tmp/claude-501/-Users-aki-Library-Mobile-Documents-com-apple-CloudDocs-myenglish/3d2a4aa5-591a-4716-a73c-1d6dfbc4381f/scratchpad/shots/cdp_shot.py", encoding="utf-8").read()
_src = re.sub(r"^main\(\)\s*$", "", _src, flags=re.M)      # 取り込むときに main() を走らせない
C = types.ModuleType("cdp_shot"); exec(compile(_src, "cdp_shot.py", "exec"), C.__dict__)
HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30; DUR = 30.0
frames_dir = os.path.join(HERE, "frames")
os.makedirs(frames_dir, exist_ok=True)
for f in os.listdir(frames_dir):
    os.remove(os.path.join(frames_dir, f))
only = [float(x) for x in sys.argv[1:]]   # 引数に秒を並べると、そのコマだけ（確認用）
proc, prof, ws = C.start()
try:
    ws.call("Emulation.setDeviceMetricsOverride", {"width": 1920, "height": 1080, "deviceScaleFactor": 1, "mobile": False})
    ws.call("Page.navigate", {"url": "file://" + os.path.join(HERE, "promo.html")})
    for _ in range(100):
        r = ws.call("Runtime.evaluate", {"expression": "typeof seek === 'function' && document.readyState === 'complete'", "returnByValue": True})
        if r.get("result", {}).get("value"): break
        time.sleep(0.2)
    ws.call("Runtime.evaluate", {"expression": "window.ready", "awaitPromise": True})
    ts = only if only else [i / FPS for i in range(int(DUR * FPS))]
    t0 = time.time()
    for i, t in enumerate(ts):
        ws.call("Runtime.evaluate", {"expression": "seek(%f); new Promise(function(r){ requestAnimationFrame(function(){ requestAnimationFrame(r); }); })" % t, "awaitPromise": True})
        shot = ws.call("Page.captureScreenshot", {"format": "png"})
        name = ("check-%05.2f.png" % t) if only else ("f%04d.png" % i)
        with open(os.path.join(frames_dir, name), "wb") as fh:
            fh.write(base64.b64decode(shot["data"]))
        if i % 100 == 0: print("frame", i, "%.0fs" % (time.time() - t0)); sys.stdout.flush()
    print("done", len(ts), "frames in %.0fs" % (time.time() - t0))
finally:
    proc.terminate()
    try: proc.wait(timeout=10)
    except Exception: proc.kill()
    import shutil; shutil.rmtree(prof, ignore_errors=True)
