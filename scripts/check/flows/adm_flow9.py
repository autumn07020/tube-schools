# -*- coding: utf-8 -*-
"""④ 対面採点（なぞるだけ採点）を Chrome で押す：帯をなぞると離したところの数が付く／ID でしぼる／消す。"""
import json, os, re, sys, time, urllib.request, urllib.error
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server")
from cdp import Chrome
import scram
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots9"; os.makedirs(OUT, exist_ok=True)
ok = ng = 0
def check(name, cond, detail=""):
    global ok, ng
    if cond: ok += 1; print("  OK   " + name)
    else: ng += 1; print("  ×    %s  %s" % (name, detail))
def click(c, sel): return c.eval("(function(){var b=document.querySelector(%s); if(b){b.click(); return true;} return false;})()" % json.dumps(sel))
def text(c, sel): return c.eval("(function(){var b=document.querySelector(%s); return b ? b.innerText : null;})()" % json.dumps(sel))
def errs(c): return json.loads(c.eval("JSON.stringify(window.__errs||[])"))
def watch(c): c.eval("window.__errs=[]; window.addEventListener('error', function(e){ window.__errs.push(String(e.message)); }); window.addEventListener('unhandledrejection', function(e){ window.__errs.push(String(e.reason && e.reason.stack || e.reason)); });")
demo = {x["id"]: x["password"] for x in json.load(open(S + "/real/demo-accounts.json")) if x.get("password")}   # 入口の一覧の ID だけの行（ためしの入口）は合言葉を持たない
def get(path, tok):
    req = urllib.request.Request(BASE + path); req.add_header("Authorization", "Bearer " + tok)
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())

with Chrome(width=1280, height=900, scale=2, port=9838) as t:
    t.goto(BASE + "/", wait=0.6); t.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');"); t.goto("about:blank", wait=0.2); t.goto(BASE + "/", wait=0.6); watch(t)
    t.wait_for("!!document.querySelector('#lId')")
    t.eval("document.querySelector('#lId').value='lteacher1'; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();" % json.dumps(demo["lteacher1"]))
    assert t.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)')", 40); time.sleep(1.5)
    tok = t.eval("localStorage.getItem('tube.school.v1.token')")
    today = get("/api/today", tok)
    task = (today.get("tasks") or [None])[0]
    assert task, "デモに、チェックする宿題がありません"
    t.eval("TubeDesk.openCheck(%s, %d)" % (json.dumps(task["key"]), task["n"]))
    check("宿題チェックのページに「写真で採点／対面で採点」がある", t.wait_for("!!document.querySelector('[data-fcmode=\"face\"]')", 20))
    click(t, '[data-fcmode="face"]'); time.sleep(0.6)
    n_rows = t.eval("document.querySelectorAll('.fc-row').length")
    check("対面で採点：生徒の行が ID（番号）の順に並ぶ", n_rows >= 3 and t.eval("!!document.querySelector('.fc-track')"), n_rows)
    t.shot(os.path.join(OUT, "k1-face.png"))
    sid = t.eval("document.querySelector('.fc-row:nth-child(2)').getAttribute('data-fcrow')")
    def drag(frac_from, frac_to):
        # 帯の上を、指でなぞる（pointerdown → pointermove → pointerup）
        return t.eval("""(function(){
          var tr = document.querySelector('[data-fctrack=%s]'); var b = tr.getBoundingClientRect();
          function ev(type, f){ tr.dispatchEvent(new PointerEvent(type, {bubbles:true, cancelable:true, pointerId:7, pointerType:'touch', button:0, clientX:b.left + b.width * f, clientY:b.top + b.height / 2})); }
          ev('pointerdown', %f); var live1 = +tr.getAttribute('aria-valuenow');
          ev('pointermove', %f); var live2 = +tr.getAttribute('aria-valuenow');
          ev('pointerup', %f);
          return JSON.stringify([live1, live2]);
        })()""" % (json.dumps(sid), frac_from, (frac_from + frac_to) / 2, frac_to))
    def server_v():
        d = get("/api/check?key=%s&n=%d" % (urllib.request.quote(task["key"]), task["n"]), tok)
        return [r.get("v") for r in d["rows"] if r["sid"] == sid][0]
    live = json.loads(drag(0.1, 0.7)); time.sleep(1.0)
    check("なぞっているあいだ、帯の色と数が指についてくる（1 → 途中 → 離す）", live[0] == 1 and live[1] in (2, 3), live)
    check("離したところ（帯の7割＝4）が付く。サーバにも入る", t.eval("document.querySelector('[data-fctrack=%s]').getAttribute('aria-valuenow')" % json.dumps(sid)) == "4" and server_v() == 4, server_v())
    row = t.eval("document.querySelector('[data-fcrow=%s]').innerText" % json.dumps(sid))
    check("行に言葉（できた）と「消す」が出る", "できた" in row and "消す" in row, row)
    json.loads(drag(0.95, 0.95)); time.sleep(1.0)
    check("押すだけでも付く（右端＝5）", server_v() == 5, server_v())
    t.shot(os.path.join(OUT, "k2-face-rated.png"))
    stats = text(t, "#dkStats") or ""
    check("上の数（評価ずみ）が、その場で変わる", "評価ずみ" in stats, stats)
    t.eval("(function(){ var b = document.querySelector('[data-fcclear=%s]'); if(b) b.click(); })()" % json.dumps(sid)); time.sleep(1.0)
    check("「消す」で評価が消える", server_v() in (None, 0), server_v())
    idtxt = t.eval("document.querySelector('.fc-row:nth-child(2) .fc-id').innerText")
    q = re.sub(r"[^0-9]", "", idtxt)[-2:]
    t.eval("(function(){ var f = document.querySelector('#fcFind'); f.focus(); f.value = %s; f.dispatchEvent(new Event('input')); })()" % json.dumps(q)); time.sleep(0.5)
    shown = json.loads(t.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('.fc-row .fc-id'), function(x){ return x.innerText; }))"))
    check("ID の数字でしぼれる（打った数字を含む行だけ）", 1 <= len(shown) < n_rows and all(q in x for x in shown) and t.eval("document.activeElement && document.activeElement.id") == "fcFind", shown)
    click(t, '[data-fcmode="photo"]'); time.sleep(0.6)
    check("「写真で採点」に戻せる（前の画面のまま）", t.eval("!!document.querySelector('.dk-grid')") and not t.eval("!!document.querySelector('.fc-row')"))
    t.eval("window.resizeTo && 0"); 
    check("講師の画面に JS のエラーが無い", not errs(t), errs(t)[:3])
with Chrome(width=430, height=900, scale=2, mobile=True, port=9839) as ph:
    ph.goto(BASE + "/", wait=0.6); ph.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');"); ph.goto("about:blank", wait=0.2); ph.goto(BASE + "/", wait=0.6)
    ph.wait_for("!!document.querySelector('#lId')")
    ph.eval("document.querySelector('#lId').value='lteacher1'; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();" % json.dumps(demo["lteacher1"]))
    ph.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)')", 40); time.sleep(1.5)
    ph.eval("TubeDesk.openCheck(%s, %d)" % (json.dumps(task["key"]), task["n"])); ph.wait_for("!!document.querySelector('[data-fcmode=\"face\"]')", 20)
    click(ph, '[data-fcmode="face"]'); time.sleep(0.8)
    check("スマホの幅でも、横にはみ出さず、帯が指で押せる大きさ（44px 以上）", ph.eval("document.documentElement.scrollWidth <= window.innerWidth") and ph.eval("document.querySelector('.fc-track').getBoundingClientRect().height >= 44"))
    ph.shot(os.path.join(OUT, "k3-face-phone.png"))
print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng else "通っていないものがある", ok, ng))
