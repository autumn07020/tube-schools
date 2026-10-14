// ocrpng.swift <png> [lang=ja]  → 行ごとに {y}[x]文字 …（y は上が 0）
import AppKit
import Vision
let a = CommandLine.arguments
let img = NSImage(contentsOfFile: a[1])!
var rect = CGRect(origin: .zero, size: img.size)
let cg = img.cgImage(forProposedRect: &rect, context: nil, hints: nil)!
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.recognitionLanguages = ["ja-JP", "en-US"]
req.usesLanguageCorrection = (a.count > 2 && a[2] == "corr")
try! VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
var items: [(x: CGFloat, y: CGFloat, h: CGFloat, s: String)] = []
for o in req.results ?? [] {
    guard let c = o.topCandidates(1).first else { continue }
    let b = o.boundingBox
    items.append((x: b.minX, y: 1 - b.maxY, h: b.height, s: c.string))
}
items.sort { $0.y < $1.y }
var lines: [[(x: CGFloat, s: String)]] = []; var ys: [CGFloat] = []; var lastY: CGFloat = -1
for it in items {
    if lastY < 0 || abs(it.y - lastY) > max(0.006, it.h * 0.6) { lines.append([]); ys.append(it.y); lastY = it.y }
    lines[lines.count - 1].append((x: it.x, s: it.s))
}
for (i, l) in lines.enumerated() {
    print(String(format: "{%.3f}", ys[i]) + l.sorted { $0.x < $1.x }.map { String(format: "[%.2f]%@", $0.x, $0.s) }.joined(separator: "  "))
}
