#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""写真（JPEG・PNG）を A4 の PDF にまとめる。**外の道具を入れない**（PIL も無い前提）。

用途：出された答案を講師が印刷して赤を入れ、また撮って返す。1枚ずつ画像を開いて
印刷するより、1つの PDF にした方が速い。

  JPEG … そのまま PDF に入れる（DCTDecode）。
  PNG  … 中身をほどいて RGB にし、Flate で入れる（8bit・非インターレースの
         グレー／RGB／RGBA／グレー＋α だけ。それ以外は飛ばす）。

ページは A4 たて（595×842pt）。画像は縦横比を保って余白の中に収める。
"""
import struct
import zlib

A4 = (595.0, 842.0)
MARGIN = 28.0


def _jpeg_size(data):
    """JPEG の幅・高さ・色の数。SOF マーカーを探す。"""
    i = 2
    n = len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker == 0xFF:                 # 詰め物の FF。次のバイトからマーカー
            i += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            comps = data[i + 9]
            return w, h, comps
        i += 2 + seg
    raise ValueError("JPEG の大きさが読めません")


def _png_rgb(data):
    """PNG を (幅, 高さ, 色の数, 生のバイト列) に。8bit・非インターレースだけ。"""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG ではありません")
    i = 8
    w = h = 0
    depth = ctype = interlace = 0
    idat = []
    while i + 8 <= len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        tag = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + ln]
        if tag == b"IHDR":
            w, h, depth, ctype, _c, _f, interlace = struct.unpack(">IIBBBBB", body)
        elif tag == b"IDAT":
            idat.append(body)
        elif tag == b"IEND":
            break
        i += 12 + ln
    if depth != 8 or interlace != 0 or ctype not in (0, 2, 4, 6):
        raise ValueError("この PNG の形（%dbit・型%d）は扱えません" % (depth, ctype))
    chans = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b"".join(idat))
    stride = w * chans
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    for _y in range(h):
        ft = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        if ft == 1:
            for x in range(chans, stride):
                line[x] = (line[x] + line[x - chans]) & 0xFF
        elif ft == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif ft == 3:
            for x in range(stride):
                a = line[x - chans] if x >= chans else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 0xFF
        elif ft == 4:
            for x in range(stride):
                a = line[x - chans] if x >= chans else 0
                b = prev[x]
                c = prev[x - chans] if x >= chans else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 0xFF
        elif ft != 0:
            raise ValueError("PNG のフィルタが読めません")
        prev = line
        if chans in (2, 4):                       # α を落とす（白と合成しない。答案は白地なので）
            keep = chans - 1
            out += bytes(line[x] for x in range(stride) if (x % chans) < keep)
        else:
            out += bytes(line)
    color = 1 if chans in (1, 2) else 3
    return w, h, color, bytes(out)


def build(images):
    """images … [(kind, bytes)]（kind は 'jpg' か 'png'）。読めない画像は飛ばす。
    1枚も無ければ ValueError。戻りは PDF のバイト列。"""
    pages = []
    for kind, data in images:
        try:
            if kind == "jpg":
                w, h, comps = _jpeg_size(data)
                cs = "/DeviceRGB" if comps == 3 else ("/DeviceGray" if comps == 1 else "/DeviceCMYK")
                pages.append({"w": w, "h": h, "cs": cs, "filter": "/DCTDecode", "data": data, "decode": comps == 4})
            elif kind == "png":
                w, h, color, raw = _png_rgb(data)
                pages.append({"w": w, "h": h, "cs": "/DeviceRGB" if color == 3 else "/DeviceGray",
                              "filter": "/FlateDecode", "data": zlib.compress(raw, 6), "decode": False})
        except (ValueError, struct.error, zlib.error, IndexError):
            continue
    if not pages:
        raise ValueError("PDF にできる画像がありません")

    objs = []                                     # 1始まりの番号 → バイト列

    def add(body):
        objs.append(body)
        return len(objs)

    page_ids = []
    add(b"")                                      # 1: カタログ（あとで入れる）
    add(b"")                                      # 2: ページの木（あとで入れる）
    pw, ph = A4
    for pg in pages:
        img_id = add(("<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace %s "
                      "/BitsPerComponent 8 /Filter %s %s/Length %d >>\nstream\n" %
                      (pg["w"], pg["h"], pg["cs"], pg["filter"],
                       ("/Decode [1 0 1 0 1 0 1 0] " if pg["decode"] else ""), len(pg["data"]))).encode("latin-1")
                     + pg["data"] + b"\nendstream")
        # 余白の中に、縦横比を保って収める
        aw, ah = pw - 2 * MARGIN, ph - 2 * MARGIN
        sc = min(aw / pg["w"], ah / pg["h"])
        dw, dh = pg["w"] * sc, pg["h"] * sc
        x, y = (pw - dw) / 2, (ph - dh) / 2
        content = ("q %.2f 0 0 %.2f %.2f %.2f cm /Im0 Do Q" % (dw, dh, x, y)).encode("latin-1")
        c_id = add(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
        p_id = add(("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.0f %.0f] /Resources << /XObject << /Im0 %d 0 R >> >> "
                    "/Contents %d 0 R >>" % (pw, ph, img_id, c_id)).encode("latin-1"))
        page_ids.append(p_id)
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = ("<< /Type /Pages /Kids [%s] /Count %d >>" %
               (" ".join("%d 0 R" % i for i in page_ids), len(page_ids))).encode("latin-1")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def page_count(pdf):
    """作った PDF のページ数（検査用）。"""
    import re
    m = re.search(rb"/Count (\d+)", pdf)
    return int(m.group(1)) if m else 0
