#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDF から写真を取り出す部品（pdf.js・img.fromPdfPage）を、形の違う PDF で確かめる。Chrome を裏で動かす。

作る PDF（中身はすべて合成の絵。赤い四角が絵の左上、青い四角が右下）
  a  複合機ふう（tubestudy の pdfout と同じ作り。JPEG・A4 の余白つき）3ページ → 順番・向き
  b  ページの /Rotate 90                        → 見た目は右に90°（赤が右上）
  c  中身の命令で左に90°回して貼る（cm）         → 赤が左下
  d  ページの木とカタログを圧縮オブジェクト（/ObjStm）に入れ、xref もストリーム → 読める
  e  生の画素（Flate・予測子 15）と、1ビットの白黒                → 読める
  f  1ページに写真2枚（上下の帯）                → 1枚に組む（赤は上、青は下）
  g  macOS の PDFKit・CoreGraphics で作ったもの（iPad の「書類をスキャン」に近い）
  h  JBIG2（白黒の高圧縮）                        → 読めないと言う（黙って捨てない）

    python3 紙の宿題/検査/pdf_test.py    （先に sh 紙の宿題/検査/デモ.sh start。画面は中継 8941 から読む）
"""
import base64
import json
import os
import struct
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(HERE, "作業.nosync")
os.makedirs(os.path.join(W, "tmp"), exist_ok=True)
os.environ["TMPDIR"] = os.path.join(W, "tmp")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(W, "tube", "server"))
from cdp import Chrome  # noqa: E402
import pdfout  # noqa: E402

RELAY = os.environ.get("RELAY", "http://127.0.0.1:8941")
ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   %s" % name)
    else:
        ng_n += 1
        print("  ×    %s  %s" % (name, detail))


# ---------- 小さな PDF 書き ----------
class PDF:
    def __init__(self):
        self.objs = []

    def add(self, body):
        self.objs.append(body)
        return len(self.objs)

    def stream(self, d, data):
        return ("<< %s /Length %d >>\nstream\n" % (d, len(data))).encode() + data + b"\nendstream"

    def build(self, root, objstm=None):
        out = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n"
        offs = []
        for i, body in enumerate(self.objs, 1):
            if objstm and i in objstm:
                offs.append(None)
                continue
            offs.append(len(out))
            b = body if isinstance(body, bytes) else body.encode()
            out += ("%d 0 obj\n" % i).encode() + b + b"\nendobj\n"
        if objstm:
            # 圧縮オブジェクト（/ObjStm）と xref ストリーム
            nums = sorted(objstm)
            parts, head, pos = [], [], 0
            for n in nums:
                b = self.objs[n - 1] if isinstance(self.objs[n - 1], bytes) else self.objs[n - 1].encode()
                head.append("%d %d" % (n, pos))
                parts.append(b)
                pos += len(b) + 1
            hdr = (" ".join(head) + "\n").encode()
            data = zlib.compress(hdr + b"\n".join(parts) + b"\n")
            sn = len(self.objs) + 1
            offs.append(len(out))
            out += ("%d 0 obj\n" % sn).encode() + ("<< /Type /ObjStm /N %d /First %d /Filter /FlateDecode /Length %d >>\nstream\n" % (len(nums), len(hdr), len(data))).encode() + data + b"\nendstream\nendobj\n"
            xn = sn + 1
            rows = [b"\x00\x00\x00\x00\xff\xff"]
            for i in range(1, sn + 1):
                if i in objstm:
                    rows.append(struct.pack(">BIB", 2, sn, nums.index(i)))
                else:
                    rows.append(struct.pack(">BIB", 1, offs[i - 1], 0))
            xoff = len(out)
            rows.append(struct.pack(">BIB", 1, xoff, 0))
            xd = zlib.compress(b"".join(rows))
            out += ("%d 0 obj\n<< /Type /XRef /Size %d /W [1 4 1] /Root %d 0 R /Filter /FlateDecode /Length %d >>\nstream\n" % (xn, xn + 1, root, len(xd))).encode() + xd + b"\nendstream\nendobj\n"
            out += ("startxref\n%d\n%%%%EOF\n" % xoff).encode()
            return out
        x = len(out)
        out += ("xref\n0 %d\n0000000000 65535 f \n" % (len(self.objs) + 1)).encode()
        for o in offs:
            out += ("%010d 00000 n \n" % o).encode()
        out += ("trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(self.objs) + 1, root, x)).encode()
        return out


def jpeg_size(data):
    w, h, c = pdfout._jpeg_size(data)
    return w, h


def one_page(img_objs, content, box="0 0 595 842", rotate=0, objstm=False, pdf=None):
    """img_objs = [(name, 画像オブジェクトの本文)]"""
    p = pdf or PDF()
    refs = []
    for name, body in img_objs:
        refs.append((name, p.add(body)))
    cs = p.add(p.stream("", content.encode()))
    xo = " ".join("/%s %d 0 R" % (n, r) for n, r in refs)
    page = p.add("<< /Type /Page /Parent %d 0 R /MediaBox [%s] /Resources << /XObject << %s >> >> /Contents %d 0 R%s >>"
                 % (len(p.objs) + 2, box, xo, cs, (" /Rotate %d" % rotate) if rotate else ""))
    pages = p.add("<< /Type /Pages /Kids [%d 0 R] /Count 1 >>" % page)
    root = p.add("<< /Type /Catalog /Pages %d 0 R >>" % pages)
    return p.build(root, objstm={page, pages, root} if objstm else None)


def jimg(data):
    w, h = jpeg_size(data)
    return PDF().stream("/Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode" % (w, h), data)


def main():
    with Chrome(width=1100, height=900, scale=1) as c:
        c.goto(RELAY + "/", wait=1.5)
        # 合成の絵：赤い四角（左上）・青い四角（右下）・大きな数字
        jp = c.eval("""(function(){
          function mk(w, h, n, only){
            var cv = document.createElement('canvas'); cv.width = w; cv.height = h;
            var x = cv.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, w, h);
            if(only !== 'blue'){ x.fillStyle = '#e00'; x.fillRect(0, 0, w * .2, h * .15); }
            if(only !== 'red'){ x.fillStyle = '#00e'; x.fillRect(w * .8, h * .85, w * .2, h * .15); }
            x.fillStyle = '#000'; x.font = (h * .3 | 0) + 'px sans-serif'; x.fillText(String(n), w * .35, h * .6);
            return cv.toDataURL('image/jpeg', .9).split(',')[1];
          }
          window.__mk = mk;
          return [mk(600, 800, 1), mk(600, 800, 2), mk(600, 800, 3), mk(600, 400, 4, 'red'), mk(600, 400, 5, 'blue')];
        })()""")
        J = [base64.b64decode(x) for x in jp]
        raw = c.eval("""(function(){
          var cv = document.createElement('canvas'); cv.width = 300; cv.height = 400;
          var x = cv.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, 300, 400);
          x.fillStyle = '#e00'; x.fillRect(0, 0, 60, 60); x.fillStyle = '#00e'; x.fillRect(240, 340, 60, 60);
          var d = x.getImageData(0, 0, 300, 400).data, rgb = [];
          for(var i = 0; i < d.length; i += 4){ rgb.push(d[i], d[i+1], d[i+2]); }
          return rgb;
        })()""")
        rgb = bytes(raw)
        pdfs = {}
        pdfs["a"] = pdfout.build([("jpg", J[0]), ("jpg", J[1]), ("jpg", J[2])])
        pdfs["b"] = one_page([("Im0", jimg(J[0]))], "q 595 0 0 842 0 0 cm /Im0 Do Q", rotate=90)
        pdfs["c"] = one_page([("Im0", jimg(J[0]))], "q 0 600 -800 0 800 0 cm /Im0 Do Q", box="0 0 800 600")
        pdfs["d"] = one_page([("Im0", jimg(J[1]))], "q 595 0 0 842 0 0 cm /Im0 Do Q", objstm=True)
        # 生の画素：予測子 15（PNG の Up）で並べて Flate
        rows = b"".join(b"\x02" + (bytes(a - b & 255 for a, b in zip(rgb[y * 900:(y + 1) * 900], rgb[(y - 1) * 900:y * 900])) if y else rgb[:900]) for y in range(400))
        flate = PDF().stream("/Type /XObject /Subtype /Image /Width 300 /Height 400 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /DecodeParms << /Predictor 15 /Colors 3 /Columns 300 >>", zlib.compress(rows))
        pdfs["e1"] = one_page([("Im0", flate)], "q 595 0 0 842 0 0 cm /Im0 Do Q")
        bits = bytearray()
        for y in range(400):
            row = 0
            line = bytearray()
            for xx in range(304):
                v = 1 if xx >= 300 or not (xx < 60 and y < 60) else 0
                row = (row << 1) | v
                if xx % 8 == 7:
                    line.append(row & 255)
                    row = 0
            bits += line
        mono = PDF().stream("/Type /XObject /Subtype /Image /Width 300 /Height 400 /ColorSpace /DeviceGray /BitsPerComponent 1 /Filter /FlateDecode", zlib.compress(bytes(bits)))
        pdfs["e2"] = one_page([("Im0", mono)], "q 595 0 0 842 0 0 cm /Im0 Do Q")
        pdfs["f"] = one_page([("Im0", jimg(J[3])), ("Im1", jimg(J[4]))], "q 595 0 0 421 0 421 cm /Im0 Do Q q 595 0 0 421 0 0 cm /Im1 Do Q")
        jb = PDF().stream("/Type /XObject /Subtype /Image /Width 600 /Height 800 /ColorSpace /DeviceGray /BitsPerComponent 1 /Filter /JBIG2Decode", b"\x00" * 64)
        pdfs["h"] = one_page([("Im0", jb)], "q 595 0 0 842 0 0 cm /Im0 Do Q")
        tmp = os.path.join(W, "tmp")
        for i, j in enumerate(J[:3]):
            open(os.path.join(tmp, "src%d.jpg" % i), "wb").write(j)
        # swift は日本語のパスで黙って失敗するので、作業場に入り ASCII の相対パスで作る（一時ファイルも作業場の中）
        os.makedirs(os.path.join(tmp, "t"), exist_ok=True)
        open(os.path.join(tmp, "pk.swift"), "w", encoding="utf-8").write(open(os.path.join(HERE, "pdfkit.swift"), encoding="utf-8").read())
        env = dict(os.environ, TMPDIR="./t")
        subprocess.run(["swiftc", "-o", "pkbin", "pk.swift"], cwd=tmp, env=env, capture_output=True, text=True, timeout=600)
        for mode in ("pdfkit", "cg"):
            outp = os.path.join(tmp, "g-%s.pdf" % mode)
            if os.path.exists(outp):
                os.remove(outp)
            r = subprocess.run(["./pkbin", mode, "g-%s.pdf" % mode, "src0.jpg", "src1.jpg", "src2.jpg"], cwd=tmp, env=env,
                               capture_output=True, text=True, timeout=300)
            if os.path.exists(outp):
                pdfs["g-" + mode] = open(outp, "rb").read()
            else:
                print("  （%s の PDF を作れませんでした：%s）" % (mode, r.stderr[:200]))

        def run(key):
            b64 = base64.b64encode(pdfs[key]).decode()
            return c.eval("""(async function(){
              var bytes = Uint8Array.from(atob('%s'), function(ch){ return ch.charCodeAt(0); });
              var ex = await PaperPDF.extract(bytes), out = [];
              for(var i = 0; i < ex.pages.length; i++){
                var cv = await Paper.img.fromPdfPage(ex.pages[i]);
                var w = cv.width, h = cv.height, d = cv.getContext('2d').getImageData(0, 0, w, h).data;
                var rx = 0, ry = 0, rn = 0, bx = 0, by = 0, bn = 0;
                for(var y = 0; y < h; y += 2) for(var x = 0; x < w; x += 2){
                  var k = (y * w + x) * 4;
                  if(d[k] > 180 && d[k+1] < 90 && d[k+2] < 90){ rx += x; ry += y; rn++; }
                  if(d[k+2] > 180 && d[k] < 90 && d[k+1] < 90){ bx += x; by += y; bn++; }
                }
                out.push({w:w, h:h, parts:ex.pages[i].parts.map(function(p){ return p.kind; }),
                          red: rn ? [rx / rn / w, ry / rn / h] : null, blue: bn ? [bx / bn / w, by / bn / h] : null, dark:(function(){
                            var n = 0; for(var y = 0; y < 60; y++) for(var x = 0; x < 60; x++){ var k = (y * w + x) * 4; if(d[k] < 80) n++; } return n; })()});
              }
              return {pages:out, errors:ex.errors, count:ex.count};
            })()""" % b64, wait_promise=True)

        def quad(p):
            return None if not p else ("上" if p[1] < .5 else "下") + ("左" if p[0] < .5 else "右")

        print("\na 複合機ふう（3ページ）")
        r = run("a")
        check("3ページ・順番どおり", r["count"] == 3 and len(r["pages"]) == 3, r)
        check("どのページも赤が左上・青が右下", all(quad(p["red"]) == "上左" and quad(p["blue"]) == "下右" for p in r["pages"]),
              [(quad(p["red"]), quad(p["blue"])) for p in r["pages"]])
        print("\nb ページの /Rotate 90")
        r = run("b")
        check("右に90°（赤が右上・青が左下）", r["pages"] and quad(r["pages"][0]["red"]) == "上右" and quad(r["pages"][0]["blue"]) == "下左",
              r["pages"] and (quad(r["pages"][0]["red"]), quad(r["pages"][0]["blue"])))
        print("\nc 命令（cm）で左に90°")
        r = run("c")
        check("赤が左下・青が右上", r["pages"] and quad(r["pages"][0]["red"]) == "下左" and quad(r["pages"][0]["blue"]) == "上右",
              r["pages"] and (quad(r["pages"][0]["red"]), quad(r["pages"][0]["blue"])))
        check("横長のページになる", r["pages"] and r["pages"][0]["w"] > r["pages"][0]["h"], r["pages"] and (r["pages"][0]["w"], r["pages"][0]["h"]))
        print("\nd 圧縮オブジェクト（/ObjStm）と xref ストリーム")
        r = run("d")
        check("読める・向きどおり", len(r["pages"]) == 1 and quad(r["pages"][0]["red"]) == "上左", r)
        print("\ne 生の画素")
        r = run("e1")
        check("Flate＋予測子15：赤が左上・青が右下", r["pages"] and r["pages"][0]["parts"] == ["raw"] and quad(r["pages"][0]["red"]) == "上左" and quad(r["pages"][0]["blue"]) == "下右", r)
        r = run("e2")
        check("1ビットの白黒：左上が黒い", r["pages"] and r["pages"][0]["dark"] > 2000, r)
        print("\nf 1ページに写真2枚")
        r = run("f")
        check("1枚に組む（上の帯の赤は上、下の帯の青は下）", r["pages"] and r["pages"][0]["parts"] == ["jpeg", "jpeg"] and r["pages"][0]["red"][1] < .1 and r["pages"][0]["blue"][1] > .9, r)
        for k in ("g-pdfkit", "g-cg"):
            if k not in pdfs:
                check("%s を作れた" % k, False)
                continue
            print("\n%s（macOS の仕組みで作った PDF）" % k)
            r = run(k)
            check("3ページ・赤が左上", len(r["pages"]) == 3 and all(quad(p["red"]) == "上左" for p in r["pages"]),
                  [(p["parts"], quad(p["red"])) for p in r["pages"]] + r["errors"])
        print("\nh JBIG2")
        r = run("h")
        check("読めないと言う（黙って捨てない）", not r["pages"] and r["errors"] and "読めません" in r["errors"][0]["error"], r)
    print("\n%s。（%d件）" % ("すべて通った" if not ng_n else "× %d件" % ng_n, ok_n + ng_n))
    return 1 if ng_n else 0


if __name__ == "__main__":
    sys.exit(main())
