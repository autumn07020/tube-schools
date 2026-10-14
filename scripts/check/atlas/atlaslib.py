# -*- coding: utf-8 -*-
"""全画面の写し（アトラス）を撮る道具。道筋を決めて撮り、台帳（manifest）に「何の画面か・どう行くか」を残す。"""
import json, os, sys, time
S = os.environ.get("ATLAS_S") or sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server")
from cdp import Chrome
BASE = "http://127.0.0.1:8949"
OUT = S + "/atlas/shots"; os.makedirs(OUT, exist_ok=True)
ACC = {r["id"]: r for r in json.load(open(S + "/real/demo-accounts.json"))}
DEV = {"P": dict(width=390, height=844, scale=2, mobile=True), "D": dict(width=1440, height=900, scale=1.5), "T": dict(width=820, height=1180, scale=1.5, mobile=True)}
DEVNAME = {"P": "iPhone（幅390）", "D": "パソコン（幅1440）", "T": "iPad（幅820）"}
HOME = "typeof TubeUI !== 'undefined' && !document.querySelector('#welcome:not(.out)') && !!document.querySelector('[data-tab]')"

class Tour:
    def __init__(self, c, dev, section, persona="", who=""):
        self.c, self.dev, self.section, self.persona, self.who = c, dev, section, persona, who
        self.items = []
    # --- 動かす
    def ev(self, js): return self.c.eval(js)
    def wait(self, js, t=15): return self.c.wait_for(js, t)
    def sleep(self, s): time.sleep(s)
    def click(self, sel, nth=0, wait=1.1):
        ok = self.c.eval("(function(){ var e=document.querySelectorAll(%s)[%d]; if(!e) return false; e.scrollIntoView({block:'center'}); e.click(); return true; })()" % (json.dumps(sel), nth))
        time.sleep(wait); return ok
    def click_text(self, sel, text, wait=1.1):
        ok = self.c.eval("(function(){ var es=document.querySelectorAll(%s); for(var i=0;i<es.length;i++){ if((es[i].innerText||'').replace(/\\s+/g,'').indexOf(%s) >= 0){ es[i].scrollIntoView({block:'center'}); es[i].click(); return true; } } return false; })()" % (json.dumps(sel), json.dumps(text.replace(" ", ""))))
        time.sleep(wait); return ok
    def fresh(self, path="/", welcomed=True):
        self.c.goto(BASE + "/", wait=0.6)
        self.c.eval("localStorage.clear(); sessionStorage.clear();" + ("localStorage.setItem('tube.welcomed.v1','1');" if welcomed else ""))
        self.c.goto("about:blank", wait=0.2); self.c.goto(BASE + path, wait=0.8)
    def login(self, lid, pw=None):
        self.fresh("/"); self.c.wait_for("!!document.querySelector('#lId')")
        self.c.eval("document.querySelector('#lId').value=%s; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();" % (json.dumps(lid), json.dumps(pw or ACC[lid]["password"])))
        ok = self.c.wait_for(HOME, 40); time.sleep(1.8); return ok
    def reload(self):
        self.c.goto(BASE + "/", wait=0.6); self.c.wait_for(HOME, 25); time.sleep(1.0)
    def tab(self, t, wait=1.5):
        self.c.eval("(function(){ var b=document.querySelector('[data-tab=%s]'); if(b) b.click(); })()" % t); time.sleep(wait)
    def go(self, v, wait=1.5):
        self.c.eval("TubeUI.go(%s)" % json.dumps(v)); time.sleep(wait)
    def text(self, sel="#main"):
        return self.c.eval("(function(){ var e=document.querySelector(%s); return e ? e.innerText : ''; })()" % json.dumps(sel)) or ""
    def has(self, sel): return bool(self.c.eval("!!document.querySelector(%s)" % json.dumps(sel)))
    # --- 撮る
    def cap(self, key, title, how, note="", segs=4, layer=False, pause=0.6, focus=None):
        only = [x for x in (os.environ.get("ATLAS_ONLY") or "").split(",") if x]
        if only and not any(key.startswith(x) for x in only): return     # この道筋では撮らない番号
        time.sleep(pause)
        if focus:
            # ページの途中にある部品（開いた返事の欄など）：その場所へ巻いて、見えている所だけを撮る
            self.c.eval("(function(){ var e=document.querySelector(%s); if(e) e.scrollIntoView({block:'center'}); })()" % json.dumps(focus)); time.sleep(0.45)
            p = os.path.join(OUT, "%s-%s-%s.png" % (self.section, key, self.dev)); self.c.shot(p)
            self.items.append({"section": self.section, "key": key, "dev": self.dev, "files": [os.path.basename(p)], "title": title, "how": how, "note": note, "persona": self.who})
            print("  cap %-28s 1枚  %s" % (os.path.basename(p)[:-4], title), flush=True); return
        base = "%s-%s-%s" % (self.section, key, self.dev)
        files = []
        vh = self.c.eval("window.innerHeight"); 
        if layer:
            p = os.path.join(OUT, base + ".png"); self.c.shot(p); files.append(os.path.basename(p))
            more = self.c.eval("""(function(){ var els = [].filter.call(document.querySelectorAll('[data-sk], [data-sk] *, .sheet, .sheet *, .dk-draw, .cam, .menu'), function(e){ var cs=getComputedStyle(e); return /(auto|scroll)/.test(cs.overflowY) && e.scrollHeight > e.clientHeight + 70 && e.getBoundingClientRect().height > 160; });
                if(!els.length){ window.__lay = null; return 0; } window.__lay = els[0]; return els[0].scrollHeight - els[0].clientHeight; })()""") or 0
            n = 1
            while more > 70 and n < segs:
                step = int(self.c.eval("window.__lay.clientHeight") * 0.82)
                at = self.c.eval("(function(){ var e=window.__lay; var b=e.scrollTop; e.scrollTop = b + %d; return e.scrollTop - b; })()" % step)
                if not at or at < 40: break
                time.sleep(0.4); n += 1
                p = os.path.join(OUT, "%s_%d.png" % (base, n)); self.c.shot(p); files.append(os.path.basename(p))
                more -= at
        else:
            self.c.eval("window.scrollTo(0,0)"); time.sleep(0.25)
            total = self.c.eval("Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)")
            step = vh - (150 if self.dev == "P" else 110)
            ys = [0]
            while ys[-1] + vh < total - 24 and len(ys) < segs:
                ys.append(min(ys[-1] + step, total - vh))
            for i, y in enumerate(ys):
                self.c.eval("window.scrollTo(0,%d)" % y); time.sleep(0.4)
                p = os.path.join(OUT, base + ("" if i == 0 else "_%d" % (i + 1)) + ".png"); self.c.shot(p); files.append(os.path.basename(p))
            self.c.eval("window.scrollTo(0,0)")
            if ys[-1] + vh < total - 24: note = (note + " " if note else "") + "（この下にも続く。全長 %dpx）" % total
        self.items.append({"section": self.section, "key": key, "dev": self.dev, "files": files, "title": title, "how": how, "note": note, "persona": self.who})
        print("  cap %-28s %d枚  %s" % (base, len(files), title), flush=True)
    def save(self, name):
        json.dump(self.items, open(os.path.join(S, "atlas", "manifest-%s.json" % name), "w"), ensure_ascii=False, indent=1)
        print("saved manifest-%s.json  %d項目 / %d枚" % (name, len(self.items), sum(len(x["files"]) for x in self.items)))

def attach_files(c, selector, paths):
    """<input type=file> に、手元のファイルを選ばせる（写真をためる画面を出すため）。"""
    doc = c.ws.call("DOM.getDocument", {})
    node = c.ws.call("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": selector})
    if not node.get("nodeId"): return False
    c.ws.call("DOM.setFileInputFiles", {"nodeId": node["nodeId"], "files": paths})
    return True
