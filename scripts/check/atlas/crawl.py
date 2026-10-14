# -*- coding: utf-8 -*-
"""探索：土台の画面ごとに、押せる部品を1種類ずつ押して、変わった画面・出てきた紙を記録する（道筋つき）。
   python3 crawl.py <S> <role: teacher|student> [persona]"""
import json, os, sys, time, hashlib
S = sys.argv[1]; ROLE = sys.argv[2]
sys.path.insert(0, S + "/tube/scripts/check")
from cdp import Chrome
BASE = "http://127.0.0.1:8949"
ACC = {r["id"]: r for r in json.load(open(S + "/real/demo-accounts.json"))}
PERSONA = sys.argv[3] if len(sys.argv) > 3 else ("lteacher1" if ROLE == "teacher" else "lj2r01")
OUT = S + "/atlas/crawl-%s-%s" % (ROLE, PERSONA); os.makedirs(OUT, exist_ok=True)
SKIP = ("ntok", "mgseen", "use", "appon", "dkundo", "dkclear", "fcclear", "ikdel", "ikpe-del", "ikas-go", "ikpe-save", "iksave", "dkreturn",
        "dkdrawsend", "lstop", "ntsend", "mgsend", "upsend", "sk", "tab", "sid", "name", "fcrow", "fctrack", "dkcv", "dkn")
def login(c, lid):
    c.goto(BASE + "/", wait=0.8); c.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');")
    c.goto("about:blank", wait=0.2); c.goto(BASE + "/", wait=0.8)
    c.wait_for("!!document.querySelector('#lId')")
    c.eval("document.querySelector('#lId').value=%s; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();" % (json.dumps(lid), json.dumps(ACC[lid]["password"])))
    c.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)')", 30); time.sleep(1.6)
def reload(c):
    c.goto(BASE + "/", wait=0.6)
    c.wait_for("typeof TubeUI !== 'undefined' && !document.querySelector('#welcome:not(.out)') && !!document.querySelector('[data-tab]')", 20); time.sleep(0.9)
def click(c, sel, nth=0):
    return c.eval("(function(){ var e=document.querySelectorAll(%s)[%d]; if(!e) return false; e.scrollIntoView({block:'center'}); e.click(); return true; })()" % (json.dumps(sel), nth))
SIG = """(function(){
  function vis(e){ var r=e.getBoundingClientRect(); return r.width>0 && r.height>0; }
  function t(e){ return (e.innerText||'').replace(/\\s+/g,' ').trim(); }
  var m = document.querySelector('#main');
  var layers = [].filter.call(document.querySelectorAll('[data-sk], .sheet, .shade, .cam, .dk-draw, .menu, #toast.on, .toast.on'), vis);
  var lt = layers.map(function(e){ return (e.getAttribute('data-sk')||e.className||'').toString().slice(0,40) + '::' + t(e).slice(0,70); });
  var heads = [].map.call(document.querySelectorAll('#main h1, #main h2'), function(e){ return t(e).slice(0,24); }).filter(Boolean).slice(0,8);
  return JSON.stringify({view:(window.TubeUI&&TubeUI.state&&TubeUI.state().view)||'', n:t(m).length, head:t(m).slice(0,60), heads:heads, layers:lt, url:location.pathname+location.hash});
})()"""
CAND = """(function(scope){
  var out = {}; var root = scope ? document.querySelector(scope) : document.querySelector('#main');
  if(!root) return '{}';
  [].forEach.call(root.querySelectorAll('*'), function(e){
    var r = e.getBoundingClientRect(); if(!(r.width>0 && r.height>0)) return;
    [].forEach.call(e.attributes, function(a){ if(a.name.indexOf('data-')===0){ var k=a.name.slice(5); if(!out[k]) out[k] = (e.innerText||e.value||'').replace(/\\s+/g,' ').trim().slice(0,22); } });
    if(e.id && /^(BUTTON|A|SELECT|SUMMARY)$/.test(e.tagName)) { if(!out['#'+e.id]) out['#'+e.id] = (e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,22); }
  });
  return JSON.stringify(out);
})"""
def sel_of(k): return k if k.startswith("#") else "[data-%s]" % k
def sig(c): return json.loads(c.eval(SIG))
def key_of(s): return hashlib.md5(json.dumps([s["view"], s["n"] // 40, s["layers"], s["heads"]], ensure_ascii=False).encode()).hexdigest()[:8]
LOG = []
def explore(c, base_name, setup, depth2=True):
    setup(); b = sig(c)
    c.shot(os.path.join(OUT, base_name + ".png"))
    cands = json.loads(c.eval(CAND + "(null)"))
    print("\n## %s  view=%s heads=%s\n   cands: %s" % (base_name, b["view"], b["heads"], " ".join(sorted(cands))), flush=True)
    LOG.append({"id": base_name, "base": base_name, "clicks": [], "sig": b})
    seen = {key_of(b)}
    for k in sorted(cands):
        kk = k.lstrip("#")
        if kk in SKIP: continue
        setup()
        if not click(c, sel_of(k)): continue
        time.sleep(1.3)
        try: s = sig(c)
        except Exception as e: print("   !", k, e); continue
        h = key_of(s)
        if h in seen: continue
        seen.add(h)
        name = "%s__%s" % (base_name, kk)
        c.shot(os.path.join(OUT, name + ".png"))
        LOG.append({"id": name, "base": base_name, "clicks": [sel_of(k)], "label": cands[k], "sig": s})
        print("   + %-14s 「%s」→ view=%s layers=%s heads=%s" % (k, cands[k], s["view"], [x[:46] for x in s["layers"]][:3], s["heads"][:4]), flush=True)
        if depth2 and (s["layers"] or s["view"] != b["view"]):
            scope = "[data-sk], .sheet, .cam, .dk-draw" if s["layers"] else "#main"
            c2 = json.loads(c.eval(CAND + "(%s)" % json.dumps(scope.split(",")[0])))
            if not s["layers"]: c2 = {a: v for a, v in c2.items() if a not in cands}
            for k2 in sorted(c2):
                kk2 = k2.lstrip("#")
                if kk2 in SKIP or k2 == k: continue
                setup(); click(c, sel_of(k)); time.sleep(1.1)
                if not click(c, sel_of(k2)): continue
                time.sleep(1.2)
                try: s2 = sig(c)
                except Exception as e: continue
                h2 = key_of(s2)
                if h2 in seen: continue
                seen.add(h2)
                n2 = "%s__%s__%s" % (base_name, kk, kk2)
                c.shot(os.path.join(OUT, n2 + ".png"))
                LOG.append({"id": n2, "base": base_name, "clicks": [sel_of(k), sel_of(k2)], "label": cands[k] + " → " + c2[k2], "sig": s2})
                print("       ++ %-14s 「%s」→ view=%s layers=%s" % (k2, c2[k2], s2["view"], [x[:46] for x in s2["layers"]][:2]), flush=True)

dev = dict(width=1440, height=900, scale=1) if ROLE == "teacher" else dict(width=390, height=844, scale=1, mobile=True)
with Chrome(port=int(os.environ.get('CRAWL_PORT', '9853')), **dev) as c:
    login(c, PERSONA)
    def tab(t):
        def f():
            reload(c); click(c, "[data-tab=%s]" % t); time.sleep(1.4)
        return f
    def govia(v):
        def f():
            reload(c); c.eval("TubeUI.go(%s)" % json.dumps(v)); time.sleep(1.4)
        return f
    def chain(first, *sels):
        def f():
            first()
            for s_ in sels:
                click(c, s_); time.sleep(1.5)
        return f
    if ROLE == "teacher":
        bases = [("hw", tab("hw")), ("check", chain(tab("hw"), "[data-dkcheck]")), ("check-face", chain(tab("hw"), "[data-dkcheck]", "[data-fcmode=face]")),
                 ("roster", tab("roster")), ("course", chain(tab("roster"), "[data-ikcourse]")),
                 ("progress", tab("progress")), ("pgcourse", chain(tab("progress"), "[data-pgcourse]")),
                 ("apps", govia("apps")), ("mats", govia("mats")), ("admin", govia("admin")), ("report", govia("report")), ("menu", chain(tab("hw"), "#hMenu"))]
    else:
        bases = [("today", tab("today")), ("homework", tab("homework")), ("daily", tab("daily")), ("record", tab("record")),
                 ("fb", chain(tab("record"), "[data-fbsub]")), ("parent", govia("parent")), ("settings", govia("settings")),
                 ("report", govia("report")), ("menu", chain(tab("today"), "#hMenu")), ("session", chain(tab("daily"), "[data-start]"))]
    only = sys.argv[4].split(",") if len(sys.argv) > 4 else None
    for name, setup in bases:
        if only and name not in only: continue
        try: explore(c, name, setup)
        except Exception as e: print("   !! base", name, e, flush=True)
json.dump(LOG, open(os.path.join(OUT, "log.json"), "w"), ensure_ascii=False, indent=1)
print("\npaths:", len(LOG))
