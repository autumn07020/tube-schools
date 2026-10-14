# -*- coding: utf-8 -*-
"""刷る紙（組み分けテスト対策の A4）を撮る。生徒の「紙にする」が開く、いまの本物の紙面。 python3 tour_print.py <S>"""
import glob, json, os, sys, time
from atlaslib import *
for f in glob.glob(OUT + "/紙面-*.png"): os.remove(f)
items = []
with Chrome(port=9893, width=390, height=844, scale=1, mobile=True) as c:
    t = Tour(c, "P", "紙面"); t.login("lj2r01"); t.tab("daily")
    c.eval("window.__opened = []; window.open = function(u){ window.__opened.push(String(u)); return null; };")
    labels = json.loads(c.eval("JSON.stringify([].map.call(document.querySelectorAll('[data-prepsheet]'), function(b){ return b.getAttribute('data-prepsheet'); }))"))
    t.click("[data-prepsheet]", wait=1.5)
    urls = json.loads(c.eval("JSON.stringify(window.__opened)"))
    print("  紙にする:", labels[:5], [u[:60] for u in urls])
    assert urls, "紙の番地が取れない"
    url = urls[0] if urls[0].startswith("http") else BASE + urls[0]
    c.ws.call("Emulation.setDeviceMetricsOverride", {"width": 794, "height": 1123, "deviceScaleFactor": 1.5, "mobile": False})
    c.goto(url, wait=2.0)
    c.ws.call("Emulation.setEmulatedMedia", {"media": "print"}); time.sleep(0.8)
    w = int(c.eval("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)") or 794); total = int(c.eval("document.documentElement.scrollHeight"))
    print("  紙面の幅 %d 全長 %d" % (w, total))
    n = max(1, min(6, int(round(total / 1123.0)))); files = []
    for i in range(n):
        c.eval("window.scrollTo(0,%d)" % (i * 1123)); time.sleep(0.4)
        p = os.path.join(OUT, "紙面-対策テスト_%d.png" % (i + 1)); c.shot(p); files.append(os.path.basename(p))
    title = (c.eval("document.title") or "").strip()
    items.append({"section": "紙面", "key": "対策テスト", "dev": "A4", "files": files, "title": "組み分けテスト対策の紙（A4たて）：問題 → 解答らん（カメラで読む紙）→ 解答と解説",
                  "how": "生徒の毎日テスト → 対策の札の「紙にする」（刷るときの紙面）", "note": "1教科ずつ。解答らんは四すみに位置合わせの黒い四角。マスの位置は変えない（カメラで丸つけが読む）。先頭 %d ページぶん" % n, "persona": "中2R の生徒が刷る紙"})
json.dump(items, open(S + "/atlas/manifest-print.json", "w"), ensure_ascii=False, indent=1); print("  cap 紙面", len(items[0]["files"]))
