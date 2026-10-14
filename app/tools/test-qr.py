#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QR（app/js/qr.js）が本当に読めるかを、作った側とは別の読み取り（macOS の CoreImage）で確かめる。

    python3 app/tools/test-qr.py        （リポジトリの一番上で。macOS だけ）

カードに刷る QR が読めなければ、オンラインでも紙でも入口が開かない。作った模様を画像にし、
macOS の読み取りに読ませて、もとの文字と同じかを見る。型番 1〜10 の境目と、実際にカードへ入れる形を通す。
"""
import json
import os
import struct
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
QR = os.path.join(os.path.dirname(HERE), "js", "qr.js")

SWIFT = r'''
import Foundation
import CoreImage
let det = CIDetector(ofType: CIDetectorTypeQRCode, context: nil, options: [CIDetectorAccuracy: CIDetectorAccuracyHigh])!
for p in CommandLine.arguments.dropFirst() {
  var out = ""
  if let img = CIImage(contentsOf: URL(fileURLWithPath: p)) {
    for f in det.features(in: img) { if let q = f as? CIQRCodeFeature { out = q.messageString ?? "" } }
  }
  print(out.data(using: .utf8)!.base64EncodedString())
}
'''


def png(matrix, scale=8, quiet=4):
    n = len(matrix)
    size = (n + quiet * 2) * scale
    rows = []
    for y in range(size):
        my = y // scale - quiet
        row = bytearray([0])
        for x in range(size):
            mx = x // scale - quiet
            dark = 0 <= mx < n and 0 <= my < n and matrix[my][mx]
            row.append(0 if dark else 255)
        rows.append(bytes(row))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


def main():
    if not os.path.exists(JSC) or sys.platform != "darwin":
        print("test-qr: macOS の jsc が無いので飛ばしました")
        return 0
    texts = ["A", "https://tube-study.uk/#k=we4a01.neko-yama-sora-4821",
             "https://tube-study.uk/#k=wt10.kotaeru-donguri-otedama-ayatori-4821",
             "https://tube-study.uk/#k=wj3r30.taberu-otedama-kotaeru-0000",
             "小4α 07番 日本語も入る"]
    # 型番の境目（M の容量：14,26,42,62,84,106,122,152,180,213 バイト）の前後
    for cap in (14, 26, 42, 62, 84, 106, 122, 152, 180, 213):
        texts.append("x" * cap)
        if cap < 213:
            texts.append("y" * (cap + 1))
    js = "load(%s); var T=%s; print(JSON.stringify(T.map(function(t){ return TubeQR.matrix(t); })));" % (
        json.dumps(QR), json.dumps(texts))
    out = subprocess.run([JSC, "-e", js], capture_output=True, text=True)
    if out.returncode != 0:
        print("× qr.js が落ちました: %s" % out.stderr[-300:])
        return 1
    mats = json.loads(out.stdout)
    d = tempfile.mkdtemp(prefix="tube-qr-")
    paths = []
    for i, m in enumerate(mats):
        p = os.path.join(d, "q%02d.png" % i)
        with open(p, "wb") as f:
            f.write(png(m))
        paths.append(p)
    sw = os.path.join(d, "read.swift")
    with open(sw, "w") as f:
        f.write(SWIFT)
    r = subprocess.run(["swift", sw] + paths, capture_output=True, text=True)
    if r.returncode != 0:
        print("× 読み取りの道具（swift）が動きません: %s" % r.stderr[-300:])
        return 1
    import base64
    got = [base64.b64decode(x).decode("utf-8", "replace") for x in r.stdout.split("\n") if x or True][:len(texts)]
    ng = 0
    sizes = set()
    for t, g, m in zip(texts, got, mats):
        sizes.add(len(m))
        if t != g:
            ng += 1
            print("  ×    %d マス・%d バイト：読めた文字が違う %r" % (len(m), len(t.encode("utf-8")), g[:40]))
    try:
        subprocess.run([JSC, "-e", "load(%s); TubeQR.matrix(new Array(215).join('z'));" % json.dumps(QR)], check=True, capture_output=True)
        ng += 1
        print("  ×    入りきらない長さで止まらない")
    except subprocess.CalledProcessError:
        pass
    if ng:
        print("test-qr: × %d件" % ng)
        return 1
    print("test-qr: すべて通った。（%d件。型番 1〜10 の %d 通りの大きさを、macOS の読み取りで読み直した）" % (len(texts) + 1, len(sizes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
