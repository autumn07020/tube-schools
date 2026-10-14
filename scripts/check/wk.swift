// Safari と同じ WebKit を、画面の外で動かす最小の道具（wk.py から使う）。
//
// なぜ要るか：Safari のアプリは「リモートオートメーションを許可」が切だと機械から動かせない。
// 設定を変えずに確かめるため、この Mac の WebKit（Safari と同じエンジン）を WKWebView で直に動かす。
// 本人の Safari・その履歴・クッキーには触れない（保存しないデータ置き場を使う）。窓は画面の外に置く。
//
// 使い方：1行に1つの JSON を標準入力で受け、1行の JSON を返す。
//   {"op":"goto","url":…}  {"op":"eval","js":…,"await":false}  {"op":"shot","path":…}  {"op":"size","w":…,"h":…}  {"op":"quit"}
import Cocoa
import WebKit

final class Driver: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
    var web: WKWebView!
    var win: NSWindow!
    var navDone: (() -> Void)?

    func start(w: CGFloat, h: CGFloat, ua: String?) {
        let conf = WKWebViewConfiguration()
        conf.websiteDataStore = .nonPersistent()
        conf.mediaTypesRequiringUserActionForPlayback = [.audio]      // Safari と同じ：音の出る再生は、押してから
        let ucc = conf.userContentController
        ucc.add(self, name: "tubeLog")
        let js = """
        window.__wkerrs = [];
        (function(){
          function put(s){ window.__wkerrs.push(s); try{ webkit.messageHandlers.tubeLog.postMessage(s); }catch(x){} }
          window.addEventListener('error', function(e){ put(String(e.message) + ' @' + (e.filename || '') + ':' + (e.lineno || 0)); });
          window.addEventListener('unhandledrejection', function(e){ put('unhandled: ' + String(e.reason && e.reason.stack || e.reason)); });
          document.addEventListener('securitypolicyviolation', function(e){ put('CSP: ' + e.violatedDirective + ' ' + e.blockedURI); });
        })();
        """
        ucc.addUserScript(WKUserScript(source: js, injectionTime: .atDocumentStart, forMainFrameOnly: false))
        web = WKWebView(frame: NSRect(x: 0, y: 0, width: w, height: h), configuration: conf)
        web.navigationDelegate = self
        if let ua = ua, !ua.isEmpty { web.customUserAgent = ua }
        // 窓が隠れていると、WebKit はタイマーとアニメーションを絞る。検査では絞らせない。
        let sel = Selector(("_setWindowOcclusionDetectionEnabled:"))
        if web.responds(to: sel) {
            typealias Fn = @convention(c) (AnyObject, Selector, Bool) -> Void
            unsafeBitCast(web.method(for: sel), to: Fn.self)(web, sel, false)
        }
        win = NSWindow(contentRect: NSRect(x: -20000, y: -20000, width: w, height: h), styleMask: [.borderless], backing: .buffered, defer: false)
        win.contentView = web
        win.ignoresMouseEvents = true
        win.orderBack(nil)
    }

    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        FileHandle.standardError.write(("[page] " + String(describing: m.body) + "\n").data(using: .utf8)!)
    }
    func webView(_ w: WKWebView, didFinish n: WKNavigation!) { let f = navDone; navDone = nil; f?() }
    func webView(_ w: WKWebView, didFail n: WKNavigation!, withError e: Error) { let f = navDone; navDone = nil; f?() }
    func webView(_ w: WKWebView, didFailProvisionalNavigation n: WKNavigation!, withError e: Error) { let f = navDone; navDone = nil; f?() }

    func handle(_ c: [String: Any], reply: @escaping ([String: Any]) -> Void) {
        let op = c["op"] as? String ?? ""
        switch op {
        case "goto":
            guard let u = URL(string: c["url"] as? String ?? "") else { return reply(["ok": false, "error": "bad url"]) }
            var done = false
            navDone = { if !done { done = true; reply(["ok": true]) } }
            web.load(URLRequest(url: u))
            // # だけが変わる移動は didFinish が来ない。5秒で先へ進む（wk.py が readyState を見る）。
            DispatchQueue.main.asyncAfter(deadline: .now() + 5) { if !done { done = true; self.navDone = nil; reply(["ok": true, "note": "timeout"]) } }
        case "eval":
            let js = c["js"] as? String ?? ""
            let fin: (Any?, Error?) -> Void = { val, err in
                if let e = err as NSError? {
                    if e.domain == WKErrorDomain && e.code == WKError.javaScriptResultTypeIsUnsupported.rawValue { return reply(["ok": true, "value": NSNull()]) }
                    let msg = (e.userInfo["WKJavaScriptExceptionMessage"] as? String) ?? e.localizedDescription
                    return reply(["ok": false, "error": msg])
                }
                reply(["ok": true, "value": val ?? NSNull()])
            }
            if (c["await"] as? Bool) == true {
                web.callAsyncJavaScript("return await (" + js + ");", arguments: [:], in: nil, in: .page) { r in
                    switch r { case .success(let v): fin(v, nil); case .failure(let e): fin(nil, e) }
                }
            } else {
                web.evaluateJavaScript(js, completionHandler: fin)
            }
        case "shot":
            let path = c["path"] as? String ?? ""
            web.takeSnapshot(with: nil) { img, err in
                guard let img = img, let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
                      let png = rep.representation(using: .png, properties: [:]) else {
                    return reply(["ok": false, "error": err?.localizedDescription ?? "no image"])
                }
                do { try png.write(to: URL(fileURLWithPath: path)); reply(["ok": true]) }
                catch { reply(["ok": false, "error": error.localizedDescription]) }
            }
        case "size":
            let w = CGFloat((c["w"] as? NSNumber)?.doubleValue ?? 1440), h = CGFloat((c["h"] as? NSNumber)?.doubleValue ?? 900)
            win.setFrame(NSRect(x: -20000, y: -20000, width: w, height: h), display: true)
            web.frame = NSRect(x: 0, y: 0, width: w, height: h)
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { reply(["ok": true]) }
        case "quit":
            reply(["ok": true]); exit(0)
        default:
            reply(["ok": false, "error": "unknown op"])
        }
    }
}

let args = CommandLine.arguments
let W = CGFloat(Double(args.count > 1 ? args[1] : "1440") ?? 1440)
let H = CGFloat(Double(args.count > 2 ? args[2] : "900") ?? 900)
let UA: String? = args.count > 3 ? args[3] : nil
let app = NSApplication.shared
app.setActivationPolicy(.accessory)                    // Dock に出ない・前に出ない
let drv = Driver()
drv.start(w: W, h: H, ua: UA)

func out(_ d: [String: Any]) {
    var d2 = d
    if let v = d2["value"], !JSONSerialization.isValidJSONObject(["v": v]) { d2["value"] = String(describing: v) }
    let data = (try? JSONSerialization.data(withJSONObject: d2, options: [])) ?? "{\"ok\":false,\"error\":\"encode\"}".data(using: .utf8)!
    FileHandle.standardOutput.write(data); FileHandle.standardOutput.write("\n".data(using: .utf8)!)
}
Thread.detachNewThread {
    while let line = readLine(strippingNewline: true) {
        guard let data = line.data(using: .utf8), let c = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { out(["ok": false, "error": "bad json"]); continue }
        let sem = DispatchSemaphore(value: 0)
        DispatchQueue.main.async { drv.handle(c) { r in out(r); sem.signal() } }
        sem.wait()
    }
    exit(0)
}
app.run()
