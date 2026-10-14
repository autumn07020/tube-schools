// PDF の決まったページを PNG にする（確かめ用）。 pdfpage <pdf> <ページ(0〜)> <out.png> [幅]
import Quartz
let a = CommandLine.arguments
guard let doc = PDFDocument(url: URL(fileURLWithPath: a[1])) else { print("開けません"); exit(1) }
var sizes: [String: Int] = [:]
for i in 0..<doc.pageCount { let b = doc.page(at: i)!.bounds(for: .mediaBox); sizes["\(Int(b.width))x\(Int(b.height))", default: 0] += 1 }
print("ページ \(doc.pageCount)  大きさ \(sizes)")
if a.count > 3, let n = Int(a[2]), let page = doc.page(at: n) {
    let b = page.bounds(for: .mediaBox); let w = a.count > 4 ? CGFloat(Double(a[4])!) : b.width
    let img = page.thumbnail(of: NSSize(width: w, height: w * b.height / b.width), for: .mediaBox)
    let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
    try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: a[3]))
}
