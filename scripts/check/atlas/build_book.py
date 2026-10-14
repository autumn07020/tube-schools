# -*- coding: utf-8 -*-
"""写しを本（PDF）にする。巻ごとに、画面の番号・題・行き方・補足を添えて並べる。 python3 build_book.py <S> [巻…]"""
import base64, html, json, os, struct, subprocess, sys, time
S = sys.argv[1]; A = S + "/atlas"; ONLY = sys.argv[2:]
sys.path.insert(0, S + "/tube/scripts/check")
from cdp import Chrome
D = json.load(open(A + "/atlas.json")); ITEMS = D["items"]; VOLS = D["volumes"]
IMG = A + "/out/img"; PDF = A + "/out/本"; os.makedirs(IMG, exist_ok=True); os.makedirs(PDF, exist_ok=True)
def size(p):
    with open(p, "rb") as f: b = f.read(24)
    return struct.unpack(">II", b[16:24])
def jpg(f):
    src = A + "/shots/" + f; dst = IMG + "/" + f[:-4] + ".jpg"
    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src):
        w, h = size(src); z = max(w, h)
        if w >= 2000: z = 1600                       # パソコンの写し（2160 幅）は 1600 幅に
        elif w == 1230: z = 1416                     # iPad（1230×1770）
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "80", "-Z", str(z), src, "--out", dst], capture_output=True)
    return dst
def thumb(f):
    """早見のための小さな写し（長い辺 760px）。"""
    src = A + "/shots/" + f; dst = IMG + "/t-" + f[:-4] + ".jpg"
    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src):
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "78", "-Z", "760", src, "--out", dst], capture_output=True)
    return dst
def kind(f):
    w, h = size(A + "/shots/" + f)
    if w >= 2000 or (w > h and w >= 1100): return "D"            # 横長（パソコン・iPad よこ）
    if w in (780,): return "P"
    return "T"                                                    # たて長の中くらい（iPad たて・A4）
CSS = """
@page land { size: 1600px 1000px; margin: 0 } @page port { size: 1500px 2060px; margin: 0 }
html,body{margin:0;font-family:-apple-system,"Hiragino Sans","Hiragino Kaku Gothic ProN",sans-serif;color:#1d1d1f;background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.sheet{box-sizing:border-box;overflow:hidden;break-after:page;page-break-after:always}
.sheet.land{page:land;width:1600px;height:1000px;padding:16px 28px 0}
.sheet.port{page:port;width:1500px;height:2060px;padding:18px 30px 0}
.hd{font-size:12.5px;color:#6e6e73;display:flex;justify-content:space-between;margin-bottom:8px;white-space:nowrap}
.row{display:flex;gap:22px;align-items:flex-start}
.cell{flex:none}
.cap{overflow:hidden}
.cap b{font-size:14.5px;font-weight:600;line-height:1.35}
.id{display:inline-block;background:#005bac;color:#fff;border-radius:6px;padding:1px 7px;font-size:12px;font-weight:600;margin-right:6px;font-family:ui-monospace,Menlo,monospace}
.cap p{margin:3px 0 0;font-size:11.5px;line-height:1.45;color:#444}
.cap .nt{color:#7a5200}
.cell img{display:block;border-radius:10px;box-shadow:0 0 0 1px rgba(0,0,0,.10)}
.P .cap{height:122px;width:360px} .P img{width:360px;height:779px}
.T .cap{height:122px;width:549px} .T img{height:790px;max-width:700px}
.D{margin-bottom:16px} .D .cap{height:70px;width:1440px} .D img{max-width:1440px;max-height:900px}
h1{font-size:40px;letter-spacing:-.03em;margin:120px 0 10px} h2{font-size:20px;margin:26px 0 8px} .lead{font-size:17px;line-height:1.8;max-width:1100px} li{font-size:15px;line-height:1.9}
.th{display:flex;flex-wrap:wrap;gap:12px 14px} .th div{font-size:10.5px;line-height:1.3;color:#333;overflow:hidden} .th img{display:block;border-radius:6px;box-shadow:0 0 0 1px rgba(0,0,0,.12);margin-bottom:3px}
.th.P div{width:150px;height:372px} .th.P img{width:150px;height:325px;object-fit:cover;object-position:top}
.th.D div{width:372px;height:276px} .th.D img{width:372px;height:233px;object-fit:cover;object-position:top}
"""
def esc(s): return html.escape(s or "")
def cap_html(it, i, n):
    seg = " <span style='color:#6e6e73;font-weight:400'>（%d/%d）</span>" % (i + 1, n) if n > 1 else ""
    if i == 0:
        who = ("<p>見本：%s</p>" % esc(it["who"])) if it["who"] else ""
        return "<div class='cap'><b><span class='id'>%s</span>%s%s</b><p>行き方：%s</p>%s%s</div>" % (esc(it["id"]), esc(it["title"]), seg, esc(it["how"]), ("<p class='nt'>%s</p>" % esc(it["note"])) if it["note"] else "", who if not it["note"] else "")
    return "<div class='cap'><b><span class='id'>%s</span>%s%s</b><p>つづき（下へ巻いたところ）</p></div>" % (esc(it["id"]), esc(it["title"]), seg)
def volume(vol, name):
    its = [x for x in ITEMS if x["vol"] == vol]
    groups = []
    for x in its:
        if not groups or groups[-1][0] != x["group"]: groups.append((x["group"], []))
        groups[-1][1].append(x)
    h = ["<html><head><meta charset='utf-8'><style>%s</style></head><body>" % CSS]
    h.append("<div class='sheet land'><h1>TUBE study 現状の全画面</h1><div class='lead'><b>%s</b>（2026-10-04 に、動いている実物から撮った写し）</div><h2>この巻に入っているもの</h2><ul>%s</ul>"
             "<h2>読み方</h2><ul><li><span class='id'>S01</span> は画面の番号。同じ番号は、機械（iPhone・パソコン・iPad）や見本の生徒が違っても同じ画面。新しいデザインの画面にも、この番号を付けて返してください。</li>"
             "<li>「行き方」は、その画面・紙（重なって出る面）の出し方。「（1/3）」は、同じ画面を下へ巻いた続き。</li><li>見本のデータはすべて架空（デモの校舎）。氏名は、システムのどこにも無い。</li>"
             "<li>哲学・決まり・値は「01-デザイン哲学と現状.md」、全画面の表は「02-画面台帳.md」。</li></ul></div>" % (esc(name), "".join("<li>%s　（%d画面・%d枚）</li>" % (esc(g), len(xs), sum(len(x["files"]) for x in xs)) for g, xs in groups)))
    pages = 1
    for g, xs in groups:
        cells = [(it, i, len(it["files"]), f, kind(f)) for it in xs for i, f in enumerate(it["files"])]
        i = 0
        while i < len(cells):
            k = cells[i][4]; per = {"P": 4, "T": 2, "D": 2}[k]
            batch = []
            while i < len(cells) and cells[i][4] == k and len(batch) < per: batch.append(cells[i]); i += 1
            pages += 1
            body = "".join("<div class='cell %s'>%s<img src='file://%s'></div>" % (k, cap_html(it, si, n), jpg(f)) for it, si, n, f, _k in batch)
            if k == "D": h.append("<div class='sheet port'><div class='hd'><span>%s ｜ %s</span><span>%d</span></div>%s</div>" % (esc(name), esc(g), pages, body))
            else: h.append("<div class='sheet land'><div class='hd'><span>%s ｜ %s</span><span>%d</span></div><div class='row'>%s</div></div>" % (esc(name), esc(g), pages, body))
    h.append("</body></html>")
    return "".join(h), pages
def overview():
    h = ["<html><head><meta charset='utf-8'><style>%s</style></head><body>" % CSS, open(A + "/swatch.html", encoding="utf-8").read() if os.path.exists(A + "/swatch.html") else ""]
    pages = 0
    for vol, name in VOLS:
        its = [x for x in ITEMS if x["vol"] == vol]
        seen = set(); cells = []
        for x in its:
            f = x["files"][0]; k = "P" if kind(f) != "D" else "D"
            cells.append((x, f, k))
        i = 0
        while i < len(cells):
            k = cells[i][2]; per = 18 if k == "P" else 12; batch = []
            while i < len(cells) and cells[i][2] == k and len(batch) < per: batch.append(cells[i]); i += 1
            pages += 1
            h.append("<div class='sheet land'><div class='hd'><span>早見 ｜ %s</span><span>%d</span></div><div class='th %s'>%s</div></div>" % (esc(name), pages, k,
                     "".join("<div><img src='file://%s'><span class='id' style='font-size:10px;padding:0 5px'>%s</span>%s</div>" % (thumb(f), esc(x["id"]), esc(x["title"][:34] + ("・" + x["persona"] if x["persona"] and x["persona"] not in ("lj2r01", "lteacher1") else ""))) for x, f, _k in batch)))
    h.append("</body></html>")
    return "".join(h), pages
def to_pdf(c, html_text, out):
    p = A + "/out/_book.html"; open(p, "w", encoding="utf-8").write(html_text)
    c.goto("file://" + p, wait=2.5)
    c.wait_for("[].every.call(document.images, function(i){ return i.complete; })", 120)
    r = c.ws.call("Page.printToPDF", {"printBackground": True, "preferCSSPageSize": True, "marginTop": 0, "marginBottom": 0, "marginLeft": 0, "marginRight": 0, "transferMode": "ReturnAsStream"}, timeout=600)
    with open(out, "wb") as f:
        while True:
            ch = c.ws.call("IO.read", {"handle": r["stream"], "size": 1 << 20}, timeout=120)
            f.write(base64.b64decode(ch["data"]) if ch.get("base64Encoded") else ch["data"].encode("latin1"))
            if ch.get("eof"): break
    c.ws.call("IO.close", {"handle": r["stream"]})
with Chrome(width=1600, height=1000, scale=1, port=9894) as c:
    if not ONLY or "0" in ONLY:
        t, n = overview(); out = PDF + "/第0巻 見本帳と全画面の早見.pdf"; to_pdf(c, t, out); print("%s  %dページ  %.1fMB" % (os.path.basename(out), n, os.path.getsize(out) / 1e6), flush=True)
    for vol, name in VOLS:
        if ONLY and vol not in ONLY: continue
        t, n = volume(vol, name); out = PDF + "/%s.pdf" % name; to_pdf(c, t, out)
        print("%s  %dページ  %.1fMB" % (os.path.basename(out), n, os.path.getsize(out) / 1e6), flush=True)
