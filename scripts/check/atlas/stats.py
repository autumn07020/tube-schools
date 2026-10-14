# -*- coding: utf-8 -*-
"""画面に実際に出ている形を数える：文字（大きさ／太さ）・角・影・字の色・面の色。"""
import json, sys, time, collections
from atlaslib import *
JS = """(function(){
  var F={}, R={}, SH={}, C={}, B={}, H={};
  function add(m,k){ m[k]=(m[k]||0)+1; }
  [].forEach.call(document.querySelectorAll('body *'), function(e){
    var r=e.getBoundingClientRect(); if(!(r.width>0&&r.height>0)) return; var cs=getComputedStyle(e);
    var own=[].some.call(e.childNodes,function(n){return n.nodeType===3 && n.textContent.trim();});
    if(own){ add(F, parseFloat(cs.fontSize)+'/'+cs.fontWeight); add(C, cs.color); }
    if(cs.borderTopLeftRadius!=='0px' && r.width>24) add(R, cs.borderTopLeftRadius);
    if(cs.boxShadow!=='none') add(SH, cs.boxShadow);
    if(cs.backgroundColor!=='rgba(0, 0, 0, 0)') add(B, cs.backgroundColor);
    if(/^(BUTTON|A|INPUT|SELECT)$/.test(e.tagName)) add(H, Math.round(r.height));
  });
  return JSON.stringify({F:F,R:R,SH:SH,C:C,B:B,H:H});
})()"""
tot = {k: collections.Counter() for k in "F R SH C B H".split()}
def take(t):
    d = json.loads(t.ev(JS))
    for k in tot: tot[k].update(d[k])
with Chrome(port=9871, **DEV["P"]) as c:
    t = Tour(c, "P", "x"); t.login("lj2r01")
    for tb in ("today", "homework", "daily", "record"): t.tab(tb); take(t)
    t.go("parent"); take(t); t.go("settings"); take(t)
with Chrome(port=9872, **DEV["D"]) as c:
    t = Tour(c, "D", "x"); t.login("lteacher1")
    for tb in ("hw", "roster", "progress"): t.tab(tb); take(t)
    t.tab("hw"); t.click("[data-dkcheck]", wait=1.8); take(t)
    t.tab("roster"); t.click("[data-ikcourse]", wait=1.8); take(t)
json.dump({k: tot[k].most_common() for k in tot}, open(S + "/atlas/stats.json", "w"), ensure_ascii=False, indent=0)
def show(name, k, n=40): print("%s（%d種）: %s" % (name, len(tot[k]), "  ".join("%s×%d" % (a, b) for a, b in tot[k].most_common(n))))
show("文字 大きさ/太さ", "F", 44); show("角の丸み", "R", 30); show("字の色", "C", 16); show("面の色", "B", 24); show("押せる部品の高さ", "H", 24)
print("影（%d種）" % len(tot["SH"]));
for a, b in tot["SH"].most_common(8): print("   ×%d  %s" % (b, a[:150]))
