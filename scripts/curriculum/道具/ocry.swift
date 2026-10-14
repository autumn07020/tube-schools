// PDF の各ページを絵にして（2倍）、Vision で日本語の文字を読む。行ごと（上から下、左から右）に並べて書き出す。
//   ocr <pdf> <出力dir>   → <出力dir>/p01.png と p01.txt …
import Quartz
import Vision
let a = CommandLine.arguments
guard let doc = PDFDocument(url: URL(fileURLWithPath: a[1])) else { print("開けません"); exit(1) }
let out = a[2]; try? FileManager.default.createDirectory(atPath: out, withIntermediateDirectories: true)
for i in 0..<doc.pageCount {
    guard let page = doc.page(at: i) else { continue }
    let b = page.bounds(for: .mediaBox); let scale: CGFloat = 2.0
    let img = page.thumbnail(of: NSSize(width: b.width * scale, height: b.height * scale), for: .mediaBox)
    guard let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff), let cg = rep.cgImage else { continue }
    let name = String(format: "p%02d", i + 1)
    try? rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: "\(out)/\(name).png"))
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate; req.recognitionLanguages = ["ja-JP", "en-US"]; req.usesLanguageCorrection = false
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    try? handler.perform([req])
    var items: [(y: CGFloat, x: CGFloat, h: CGFloat, s: String)] = []
    for o in req.results ?? [] { if let c = o.topCandidates(1).first { let r = o.boundingBox; items.append((y: 1 - r.midY, x: r.minX, h: r.height, s: c.string)) } }
    items.sort { $0.y < $1.y }
    // 同じ高さの行にまとめる
    var lines: [[(x: CGFloat, s: String)]] = []; var lastY: CGFloat = -1
    for it in items { if lastY < 0 || abs(it.y - lastY) > max(0.006, it.h * 0.6) { lines.append([]); lastY = it.y } ; lines[lines.count - 1].append((x: it.x, s: it.s)) }
    var text = ""
    for l in lines { text += String(format: "{%.3f}", l[0].y) + l.sorted { $0.x < $1.x }.map { String(format: "[%.2f]%@", $0.x, $0.s) }.joined(separator: "  ") + "\n" }
    try? text.write(toFile: "\(out)/\(name).txt", atomically: true, encoding: .utf8)
    print("\(name) \(Int(b.width * scale))x\(Int(b.height * scale)) 文字 \(items.count)")
}
