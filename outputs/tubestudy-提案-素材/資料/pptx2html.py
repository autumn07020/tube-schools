# -*- coding: utf-8 -*-
"""pptx（python-pptx で組んだ単純なもの）を HTML に写して、Chrome で撮るための下ごしらえ。
   四角・角丸・楕円・写真（切り抜き・角丸）・文字（段落・run の大きさ/太字/色/揃え/上下の寄せ）だけ。"""
import os, sys, zipfile, base64
from lxml import etree
NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
PX = 1600 / 12192000.0   # EMU → px（幅 13.333in = 1600px）

def color_of(el):
    c = el.find(".//a:srgbClr", NS)
    return "#" + c.get("val") if c is not None else None

def convert(pptx, outdir):
    z = zipfile.ZipFile(pptx)
    pres = etree.fromstring(z.read("ppt/presentation.xml"))
    rels = etree.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
    rid2t = {r.get("Id"): r.get("Target") for r in rels}
    order = [rid2t[s.get("{%s}id" % NS["r"])] for s in pres.findall(".//p:sldId", NS)]
    os.makedirs(outdir, exist_ok=True)
    pages = []
    for i, target in enumerate(order):
        path = "ppt/" + target
        sx = etree.fromstring(z.read(path))
        srels = etree.fromstring(z.read("ppt/slides/_rels/" + os.path.basename(path) + ".rels"))
        srid = {r.get("Id"): r.get("Target") for r in srels}
        bgc = "#ffffff"
        bg = sx.find(".//p:bg//a:srgbClr", NS)
        if bg is not None: bgc = "#" + bg.get("val")
        html = ['<div class="slide" style="background:%s">' % bgc]
        for sp in sx.find(".//p:spTree", NS):
            tag = etree.QName(sp).localname
            if tag not in ("sp", "pic"): continue
            xfrm = sp.find(".//a:xfrm", NS)
            off = xfrm.find("a:off", NS); ext = xfrm.find("a:ext", NS)
            x, y = int(off.get("x")) * PX, int(off.get("y")) * PX
            w, h = int(ext.get("cx")) * PX, int(ext.get("cy")) * PX
            geom = sp.find(".//a:prstGeom", NS)
            prst = geom.get("prst") if geom is not None else "rect"
            radius = 0
            if prst == "roundRect":
                gd = geom.find(".//a:gd", NS)
                adj = int(gd.get("fmla").split()[1]) / 100000.0 if gd is not None else 0.1667
                radius = min(w, h) * adj
            elif prst == "ellipse":
                radius = max(w, h)
            st = "left:%.1fpx;top:%.1fpx;width:%.1fpx;height:%.1fpx;border-radius:%.1fpx;" % (x, y, w, h, radius)
            if tag == "pic":
                blip = sp.find(".//a:blip", NS)
                media = srid[blip.get("{%s}embed" % NS["r"])]
                data = z.read("ppt/" + media.replace("../", ""))
                ext_ = media.split(".")[-1].lower()
                src = "data:image/%s;base64,%s" % ("jpeg" if ext_ in ("jpg", "jpeg") else "png", base64.b64encode(data).decode())
                srcRect = sp.find(".//a:srcRect", NS)
                b = int(srcRect.get("b", "0")) / 100000.0 if srcRect is not None else 0.0
                t = int(srcRect.get("t", "0")) / 100000.0 if srcRect is not None else 0.0
                ln = sp.find("p:spPr/a:ln", NS)
                border = "outline:1px solid %s;" % (color_of(ln) or "#ddd") if ln is not None and ln.find("a:noFill", NS) is None else ""
                H = 100 / (1 - t - b)
                html.append('<div class="pic" style="%s%soverflow:hidden"><img src="%s" style="position:absolute;left:0;top:%.2f%%;width:100%%;height:%.2f%%"></div>' % (st, border, src, -t * H, H))
                continue
            spPr = sp.find("p:spPr", NS)
            fill = spPr.find("a:solidFill", NS)
            fillc = color_of(fill) if fill is not None else "transparent"
            ln = spPr.find("a:ln", NS)
            border = ""
            if ln is not None and ln.find("a:noFill", NS) is None and ln.find("a:solidFill", NS) is not None:
                wpt = int(ln.get("w", "9525")) / 12700.0
                border = "border:%.1fpx solid %s;" % (wpt * 1.6, color_of(ln))
            body = sp.find("p:txBody", NS)
            inner = ""
            if body is not None:
                bp = body.find("a:bodyPr", NS)
                anchor = {"t": "flex-start", "ctr": "center", "b": "flex-end"}.get(bp.get("anchor", "t"), "flex-start")
                m = lambda k, d: int(bp.get(k, d)) * PX
                pad = "padding:%.1fpx %.1fpx %.1fpx %.1fpx;" % (m("tIns", 45720), max(12, m("rIns", 91440)), m("bIns", 45720), max(12, m("lIns", 91440)))
                paras = []
                for p in body.findall("a:p", NS):
                    pPr = p.find("a:pPr", NS)
                    algn = {"l": "left", "ctr": "center", "r": "right"}.get(pPr.get("algn", "l") if pPr is not None else "l", "left")
                    lnsp = pPr.find("a:lnSpc/a:spcPct", NS) if pPr is not None else None
                    lh = int(lnsp.get("val")) / 100000.0 if lnsp is not None else 1.2
                    runs = []
                    for r in p.findall("a:r", NS):
                        rPr = r.find("a:rPr", NS)
                        sz = int(rPr.get("sz", "1800")) / 100.0 * 1.6 if rPr is not None else 28.8
                        bold = rPr is not None and rPr.get("b") == "1"
                        col = color_of(rPr) if rPr is not None else None
                        t = r.find("a:t", NS).text or ""
                        runs.append('<span style="font-size:%.1fpx;font-weight:%s;color:%s">%s</span>' % (sz, 700 if bold else 400, col or "#000", t.replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")))
                    paras.append('<div style="text-align:%s;line-height:%.2f;min-height:1em">%s</div>' % (algn, lh, "".join(runs) or "&nbsp;"))
                inner = '<div class="tx" style="%sjustify-content:%s">%s</div>' % (pad, anchor, "".join(paras))
            html.append('<div class="sp" style="%sbackground:%s;%s">%s</div>' % (st, fillc, border, inner))
        html.append("</div>")
        pages.append("\n".join(html))
    css = """<style>body{margin:0;background:#888;font-family:"Noto Sans JP","Hiragino Sans",sans-serif;-webkit-font-smoothing:antialiased}
.slide{position:relative;width:1600px;height:900px;overflow:hidden;margin:0}
.sp,.pic{position:absolute;box-sizing:border-box}
.tx{width:100%;height:100%;display:flex;flex-direction:column;box-sizing:border-box;overflow:visible;word-break:break-word}</style>"""
    for i, pg in enumerate(pages):
        open(os.path.join(outdir, "slide%02d.html" % (i + 1)), "w", encoding="utf-8").write("<!doctype html><meta charset='utf-8'>" + css + pg)
    print("pages", len(pages))

if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
