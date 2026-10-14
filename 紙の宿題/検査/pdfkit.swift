// 検査用：写真（JPEG）から、macOS の仕組みで PDF を作る（iPad の「書類をスキャン」に近い作り）。
//   swift pdfkit.swift <mode> out.pdf in1.jpg in2.jpg …   mode = pdfkit | cg
import Foundation
import PDFKit
import AppKit
import CoreGraphics
import ImageIO
let a = CommandLine.arguments
let mode = a[1]
let out = URL(fileURLWithPath: a[2])
let ins = Array(a.dropFirst(3))
if mode == "pdfkit" {
    let doc = PDFDocument()
    for (i, p) in ins.enumerated() {
        if let img = NSImage(contentsOfFile: p), let page = PDFPage(image: img) { doc.insert(page, at: i) }
    }
    doc.write(to: out)
} else {
    var box = CGRect(x: 0, y: 0, width: 595, height: 842)
    guard let ctx = CGContext(out as CFURL, mediaBox: &box, nil) else { exit(1) }
    for p in ins {
        guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: p) as CFURL, nil),
              let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else { continue }
        ctx.beginPDFPage(nil)
        ctx.draw(img, in: box)
        ctx.endPDFPage()
    }
    ctx.closePDF()
}
