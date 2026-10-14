# -*- coding: utf-8 -*-
"""確かめ用のべた焼き：写しを小さく並べて1枚にする。 python3 contact.py <S> <manifest名> <1枚あたりの数> <列>"""
import json, os, sys, html
S = sys.argv[1]; NAME = sys.argv[2]; PER = int(sys.argv[3]) if len(sys.argv) > 3 else 12; COLS = int(sys.argv[4]) if len(sys.argv) > 4 else 6
sys.path.insert(0, S + "/tube/scripts/check")
from cdp import Chrome
items = json.load(open(S + "/atlas/manifest-%s.json" % NAME))
cells = []
for it in items:
    for i, f in enumerate(it["files"]):
        cells.append((f, "%s %s" % (it["key"], ("(%d)" % (i + 1)) if len(it["files"]) > 1 else "")))
os.makedirs(S + "/atlas/contact", exist_ok=True)
W = 1560
with Chrome(width=W, height=900, scale=1, port=9899) as c:
    for n in range(0, len(cells), PER):
        part = cells[n:n + PER]
        h = "<html><body style='margin:0;background:#888;font:12px -apple-system'><div style='display:grid;grid-template-columns:repeat(%d,1fr);gap:8px;padding:8px'>" % COLS
        for f, cap in part:
            h += "<div><div style='color:#fff;padding:2px 0'>%s</div><img src='file://%s/atlas/shots/%s' style='width:100%%;display:block'></div>" % (html.escape(cap), S, f)
        h += "</div></body></html>"
        p = S + "/atlas/contact/%s-%d.html" % (NAME, n // PER + 1)
        open(p, "w").write(h)
        c.goto("file://" + p, wait=1.2)
        c.shot(p.replace(".html", ".png"), full=True)
        print(p.replace(".html", ".png"))
