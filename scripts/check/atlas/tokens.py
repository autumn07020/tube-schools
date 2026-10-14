# -*- coding: utf-8 -*-
"""実物の値を取り出す：:root の変数（明るい・暗い、color-mix は計算後の色）と、主な部品の計算後の形。"""
import json, sys, time
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check")
from cdp import Chrome
BASE = "http://127.0.0.1:8949"
ACC = {r["id"]: r for r in json.load(open(S + "/real/demo-accounts.json"))}
def login(c, lid):
    c.goto(BASE + "/", wait=0.8); c.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');")
    c.goto("about:blank", wait=0.2); c.goto(BASE + "/", wait=0.8)
    c.wait_for("!!document.querySelector('#lId')")
    c.eval("document.querySelector('#lId').value=%s; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();" % (json.dumps(lid), json.dumps(ACC[lid]["password"])))
    c.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)')", 30); time.sleep(1.6)
VARS = """(function(){
  var defs = [];
  function walk(r){ if(r.style && r.selectorText){ for(var i=0;i<r.style.length;i++){ var p=r.style[i]; if(p.indexOf('--')===0) defs.push([r.selectorText.slice(0,80), p, r.style.getPropertyValue(p).trim().slice(0,220)]); } }
    if(r.cssRules) [].forEach.call(r.cssRules, walk); }
  [].forEach.call(document.styleSheets, function(ss){ try{ [].forEach.call(ss.cssRules, walk); }catch(e){} });
  var names = {}; defs.forEach(function(d){ if(/^:root|^html|^body/.test(d[0])) names[d[1]] = 1; });
  function resolve(){ var cs = getComputedStyle(document.documentElement), out = {};
    var probe = document.createElement('div'); document.body.appendChild(probe);
    Object.keys(names).sort().forEach(function(n){ var v = cs.getPropertyValue(n).trim(); var col = '';
      if(/^(#|rgb|hsl|color-mix|oklch|var\\()/.test(v)){ probe.style.backgroundColor = 'var(' + n + ')'; col = getComputedStyle(probe).backgroundColor; }
      out[n] = [v.slice(0,200), col]; });
    probe.remove(); return out; }
  var root = document.documentElement, was = root.getAttribute('data-theme');
  root.removeAttribute('data-theme'); var light = resolve();   /* 既定（印なし）＝明るい */
  var bodyBg = {bg: getComputedStyle(document.body).backgroundColor, before: getComputedStyle(document.body, '::before').backgroundImage, beforeBg: getComputedStyle(document.body, '::before').backgroundColor, theme: (document.querySelector('meta[name=theme-color]')||{}).content};
  root.setAttribute('data-theme', 'dark'); var dark = resolve();
  if(was) root.setAttribute('data-theme', was); else root.removeAttribute('data-theme');
  return JSON.stringify({light: light, dark: dark, body: bodyBg, scoped: defs.filter(function(d){ return !/^:root|^html|^body/.test(d[0]); })});
})()"""
PROBE = """(function(sels){
  var out = {};
  sels.forEach(function(s){ var e = document.querySelector(s); if(!e) return; var c = getComputedStyle(e), r = e.getBoundingClientRect();
    out[s] = {font: c.fontSize + '/' + c.lineHeight + ' ' + c.fontWeight, ls: c.letterSpacing, color: c.color, bg: c.backgroundColor, bgi: c.backgroundImage.slice(0,160),
      radius: c.borderRadius, pad: c.padding, shadow: c.boxShadow.slice(0,220), border: c.borderTopWidth + ' ' + c.borderTopColor, size: Math.round(r.width) + 'x' + Math.round(r.height),
      backdrop: (c.backdropFilter || c.webkitBackdropFilter || ''), family: c.fontFamily.slice(0,90)}; });
  return JSON.stringify(out);
})"""
res = {}
with Chrome(width=390, height=844, scale=1, mobile=True, port=9856) as c:
    login(c, "lj2r01")
    res["vars"] = json.loads(c.eval(VARS))
    res["student_phone"] = json.loads(c.eval(PROBE + "(%s)" % json.dumps(
        ["body", "#top", ".brand", "#main", ".sect h1", ".sect-h", "h1", "h2", ".panel", ".next", ".w-marble", ".wtile", ".w-blue", ".w-warm", ".w-plain", ".btn", ".btn.ghost", ".lnk", ".tabs", ".tabs button", ".tabs button.on",
         "nav", "nav button", ".lbl", ".tiny", ".num", ".today-n", ".duetag", ".chip", ".hw-row", ".bar", "#hMenu"])))
    c.eval("document.querySelector('[data-tab=homework]').click()"); time.sleep(1.5)
    res["student_hw"] = json.loads(c.eval(PROBE + "(%s)" % json.dumps([".hw-sec", ".hw-sec h3", ".hwrow", ".hw", ".hw .t", ".duetag", ".week", ".wk-dot", ".btn", ".lnk", ".sjt"])))
with Chrome(width=1440, height=900, scale=1, port=9857) as c:
    login(c, "lteacher1")
    res["teacher_desktop"] = json.loads(c.eval(PROBE + "(%s)" % json.dumps(
        ["body", "#top", ".brand", ".side", ".side button", ".side button.on", ".sect h1", "h1", ".dk-hero", ".dk-task", ".dk-task .dk-big", ".dk-done", ".week", ".week .slot", ".daycol", ".mg-card", ".btn", ".lnk", "#hMenu", ".who"])))
json.dump(res, open(S + "/atlas/tokens-raw.json", "w"), ensure_ascii=False, indent=1)
L, D = res["vars"]["light"], res["vars"]["dark"]
print("root vars:", len(L), " scoped defs:", len(res["vars"]["scoped"])); print("body:", json.dumps(res["vars"]["body"], ensure_ascii=False)[:600])
for d in res["vars"]["scoped"]: print("  scoped", d)
for n in sorted(L):
    print("%-22s L %-46s %-22s | D %-40s %s" % (n, L[n][0][:46], L[n][1], D[n][0][:40], D[n][1]))
