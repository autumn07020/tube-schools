// crop.swift <pdf> <page> <x0> <y0> <x1> <y1> <scale> <out.png>  (座標は 0..1、上が 0)
import AppKit
import PDFKit
let a = CommandLine.arguments
let doc = PDFDocument(url: URL(fileURLWithPath: a[1]))!
let page = doc.page(at: Int(a[2])! - 1)!
let b = page.bounds(for: .mediaBox)
let x0 = CGFloat(Double(a[3])!), y0 = CGFloat(Double(a[4])!), x1 = CGFloat(Double(a[5])!), y1 = CGFloat(Double(a[6])!), s = CGFloat(Double(a[7])!)
let w = (x1 - x0) * b.width * s, h = (y1 - y0) * b.height * s
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(w), pixelsHigh: Int(h), bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
let ctx = NSGraphicsContext(bitmapImageRep: rep)!
NSGraphicsContext.current = ctx
ctx.cgContext.setFillColor(.white); ctx.cgContext.fill(CGRect(x: 0, y: 0, width: w, height: h))
ctx.cgContext.scaleBy(x: s, y: s)
// PDF の原点は左下。見たい矩形の左下 (x0, 1-y1) を原点へ
ctx.cgContext.translateBy(x: -x0 * b.width, y: -(1 - y1) * b.height)
page.draw(with: .mediaBox, to: ctx.cgContext)
NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: a[8]))
print("\(Int(w))x\(Int(h))")
