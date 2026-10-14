# pptx → html（pptx2html.py）→ Chrome で 1600×900 に撮る → 一覧 jpg
import os, sys, re, types, time, base64, subprocess, glob, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pptx2html
pptx = sys.argv[1]
outdir = os.path.join(HERE, "prev")
for f in glob.glob(os.path.join(outdir, "*")): os.remove(f)
pptx2html.convert(pptx, outdir)
_src = open("/private/tmp/claude-501/-Users-aki-Library-Mobile-Documents-com-apple-CloudDocs-myenglish/3d2a4aa5-591a-4716-a73c-1d6dfbc4381f/scratchpad/shots/cdp_shot.py", encoding="utf-8").read()
_src = re.sub(r"^main\(\)\s*$", "", _src, flags=re.M)
C = types.ModuleType("cdp_shot"); exec(compile(_src, "cdp_shot.py", "exec"), C.__dict__)
proc, prof, ws = C.start()
try:
    ws.call("Emulation.setDeviceMetricsOverride", {"width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False})
    pages = sorted(glob.glob(os.path.join(outdir, "slide*.html")))
    for p in pages:
        ws.call("Page.navigate", {"url": "file://" + p})
        for _ in range(50):
            r = ws.call("Runtime.evaluate", {"expression": "document.readyState === 'complete'", "returnByValue": True})
            if r.get("result", {}).get("value"): break
            time.sleep(0.1)
        time.sleep(0.4)
        shot = ws.call("Page.captureScreenshot", {"format": "png"})
        open(p.replace(".html", ".png"), "wb").write(base64.b64decode(shot["data"]))
finally:
    proc.terminate()
    try: proc.wait(timeout=10)
    except Exception: proc.kill()
    import shutil; shutil.rmtree(prof, ignore_errors=True)
from PIL import Image
fs = sorted(glob.glob(os.path.join(outdir, "slide*.png")))
W, H, cols = 800, 450, 3
sheet = Image.new("RGB", (cols * W, math.ceil(len(fs) / cols) * H), "white")
for i, f in enumerate(fs): sheet.paste(Image.open(f).convert("RGB").resize((W, H)), ((i % cols) * W, (i // cols) * H))
sheet.save(os.path.join(HERE, "preview.jpg"), quality=82)
print("preview", len(fs))
