# -*- coding: utf-8 -*-
"""初回登録の 2 つを、3 つの幅で確かめる（10-12 本人の写し：登録コードの字が枠の右に寄って 6 文字目が切れていた／動画が窓だった）。
   ・登録コードの枠：6 文字が 1 文字ずつ枠の真ん中にある（横のずれ 1.5px 以内・枠からはみ出さない）。入力欄は枠の上に重なっている。
     打った字は大文字で枠に入り、記号は入らず、次の枠が青い縁になる。
   ・できることの動画：画面占有率 100%（覆いと動画が画面と同じ大きさ・object-fit:cover・画面の真ん中を押すのは動画）。帯は画面の中。
     選ばれる動画は画面の比に最も近いもの（電話 9:19.5・iPad 3:4・PC 16:9）。
   幅：電話 390×844（mobile）・iPad 768×1024・PC 1440×900。TUBE_BROWSER=webkit でも同じに流せる。
   土台：reset.sh（ためし運用の印がある校舎なので、登録コードは trial-join-code.js が先に入れる）。"""
import json, os, sys, time, urllib.request, urllib.error
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server")
from cdp import Chrome
import scram
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots16"; os.makedirs(OUT, exist_ok=True)
def api(method, path, tok=None, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode())
    req.add_header("Content-Type", "application/json")
    if tok: req.add_header("Authorization", "Bearer " + tok)
    try:
        r = urllib.request.urlopen(req, timeout=60); return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")
ok = ng = 0
def check(name, cond, detail=""):
    global ok, ng
    if cond: ok += 1; print("  OK   " + name)
    else: ng += 1; print("  ×    %s  %s" % (name, detail))
def errs(c): return json.loads(c.eval("JSON.stringify(window.__errs||[])"))
def watch(c): c.eval("window.__errs=[]; window.addEventListener('error', function(e){ window.__errs.push(String(e.message)); }); window.addEventListener('unhandledrejection', function(e){ window.__errs.push(String(e.reason && e.reason.stack || e.reason)); });")
def fresh(c, url="/"):
    c.goto(BASE + "/", wait=0.6); c.eval("localStorage.clear(); sessionStorage.clear();"); c.goto("about:blank", wait=0.2); c.goto(BASE + url, wait=0.8); watch(c)

COVER_JS = """(function(){ var b=document.querySelector('#jnCodeBox'), i=document.querySelector('#jnCode'); if(!b||!i) return false;
  var r=b.getBoundingClientRect(), q=i.getBoundingClientRect();
  return Math.abs(r.left-q.left)<=1 && Math.abs(r.top-q.top)<=1 && Math.abs(r.width-q.width)<=1 && Math.abs(r.height-q.height)<=1 && getComputedStyle(i).opacity==='0'; })()"""
CENTER_JS = """(function(){ var cells=document.querySelectorAll('#jnCodeBox .jn-cell'), n=0, maxdx=0, inside=true, ws=[];
  for(var k=0;k<cells.length;k++){ var e=cells[k], cr=e.getBoundingClientRect(); ws.push(Math.round(cr.width));
    if(!e.firstChild || !e.textContent) continue; n++;
    var rg=document.createRange(); rg.selectNodeContents(e); var tr=rg.getBoundingClientRect();
    var dx=Math.abs((tr.left+tr.right)/2-(cr.left+cr.right)/2); if(dx>maxdx) maxdx=dx;
    if(tr.left<cr.left-0.5 || tr.right>cr.right+0.5 || tr.top<cr.top-0.5 || tr.bottom>cr.bottom+0.5) inside=false; }
  var same=Math.max.apply(null,ws)-Math.min.apply(null,ws)<=1;
  return JSON.stringify({n:n, maxdx:Math.round(maxdx*100)/100, inside:inside, widths:ws, same:same, wide:document.documentElement.scrollWidth<=window.innerWidth}); })()"""
FULL_JS = """(function(){ var W=window.innerWidth, H=window.innerHeight;
  var r=function(e){ var b=e.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)]; };
  var full=document.querySelector('#jnFull'), v=document.querySelector('#jnVideo'), bar=document.querySelector('.jn-fullbar');
  if(!full||!v||!bar) return JSON.stringify({ok:false, why:'no elements'});
  var fr=r(full), vr=r(v), br=bar.getBoundingClientRect(); var hit=document.elementFromPoint(W/2, H/2);
  var okr=function(a){ return a[0]===0 && a[1]===0 && Math.abs(a[2]-W)<=1 && Math.abs(a[3]-H)<=1; };
  var fit=getComputedStyle(v).objectFit;
  return JSON.stringify({ok: okr(fr) && okr(vr) && fit==='cover' && (hit===v || hit===full), full:fr, video:vr, W:W, H:H, fit:fit, hit:(hit&&(hit.id||hit.className))||null,
    share: Math.round(100*vr[2]*vr[3]/(W*H)), bar: br.left>=0 && br.right<=W+0.5 && br.top>=0 && br.bottom<=H+0.5 && br.width>0, src:v.getAttribute('src')}); })()"""

# 登録コードを作る（土台には無い。管理者の口で作ると、ためし運用の校舎なので /api/demo の joinCode に出て、trial-join-code.js が先に入れる）
st, d = scram.login(BASE, "wadmin99", "kensa-kanri-kensa-kanri-kensa-0000", admin=True); adm = d["token"]
made = api("POST", "/api/admin/join/code", adm, {})[1]["join"]["code"]
demo = api("GET", "/api/demo")[1]
print("登録コード %s ／ /api/demo の joinCode %s" % (made, demo.get("joinCode")))
assert demo.get("joinCode") == made, "ためし運用の校舎の joinCode が出ていない"

SIZES = [("phone", 390, 844, 3, True), ("ipad", 768, 1024, 2, False), ("pc", 1440, 900, 1, False)]
for i, (name, w, h, scale, mobile) in enumerate(SIZES):
    print("\n%s %d×%d" % (name, w, h))
    with Chrome(width=w, height=h, scale=scale, mobile=mobile, port=9861 + i) as c:
        try: c.ws.call("Emulation.setFocusEmulationEnabled", {"enabled": True})      # 裏の Chrome は窓に焦点が無く、focus の出来事が起きない。WebKit には無い口
        except Exception: pass
        fresh(c, "/#join")
        check("ようこそが出る", c.wait_for("!!document.querySelector('#jnGo')", 15))
        c.eval("document.querySelector('#jnGo').click()")
        check("登録コードの欄：1 文字ずつの枠が 6 つ、入力欄が上に重なる（透明）", c.wait_for("document.querySelectorAll('#jnCodeBox .jn-cell').length === 6", 10) and c.eval(COVER_JS))
        check("コードが先に 6 文字入る（ためし運用）", c.wait_for("!!(document.querySelector('#jnCode')||{}).value && document.querySelector('#jnCode').value.length === 6", 10))
        code = c.eval("document.querySelector('#jnCode').value")
        time.sleep(0.5)
        m = json.loads(c.eval(CENTER_JS))
        check("6 文字とも枠の真ん中（横のずれ 1.5px 以内）・枠からはみ出さない・枠は同じ幅・横にはみ出さない", m["n"] == 6 and m["maxdx"] <= 1.5 and m["inside"] and m["same"] and m["wide"], m)
        c.shot(os.path.join(OUT, name + "-code.png"))
        c.eval("(function(){ var i=document.querySelector('#jnCode'); i.focus(); i.value='ab-3'; i.dispatchEvent(new Event('input',{bubbles:true})); })()")
        time.sleep(0.3)
        t = json.loads(c.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('#jnCodeBox .jn-cell'), function(e){ return [e.textContent, e.classList.contains('cur')]; }))"))
        check("打った字は大文字で枠に入り、記号は入らず、次の枠が今の枠（青い縁）", [x[0] for x in t] == ["A", "B", "3", "", "", ""] and [x[1] for x in t] == [False, False, False, True, False, False] and c.eval("document.activeElement === document.querySelector('#jnCode') && (document.querySelector('#jnCodeBox').classList.contains('focus') || !document.hasFocus())"), t)
        c.shot(os.path.join(OUT, name + "-code-typing.png"))
        c.eval("(function(){ var i=document.querySelector('#jnCode'); i.value=%s; i.dispatchEvent(new Event('input',{bubbles:true})); })()" % json.dumps(code))
        c.eval("document.querySelector('#jnCodeGo').click()")
        if not c.wait_for("!!document.querySelector('#jnFull') && !!document.querySelector('#jnVideo')", 15):
            check("次へ → できることの動画", False, c.eval("(document.querySelector('#jnMsg')||{}).innerText")); continue
        check("次へ → できることの動画", True)
        time.sleep(1.5)
        f = json.loads(c.eval(FULL_JS))
        check("動画が画面を 100% 覆う（覆い・動画とも画面と同じ大きさ、object-fit:cover、画面の真ん中を押すのは動画）", f.get("ok") and f.get("share") == 100, f)
        check("帯（約45秒・音を出す・スキップ）は画面の中", f.get("bar"), f)
        check("選んだ動画は画面の比に最も近い（intro-%s.mp4）" % name, (f.get("src") or "").endswith("intro-%s.mp4" % name), f.get("src"))
        v = json.loads(c.eval("JSON.stringify({rs:document.querySelector('#jnVideo').readyState, err:!!document.querySelector('#jnVideo').error})"))
        check("動画が読める", v["rs"] >= 1 and not v["err"], v)
        c.shot(os.path.join(OUT, name + "-video.png"))
        c.eval("document.querySelector('#jnSkip').click()")
        check("スキップで覆いが消えて、学年を選ぶ画面へ", c.wait_for("!document.querySelector('#jnFull') && !!document.querySelector('[data-act=\"grade\"]')", 10))
        check("JS のエラー無し", errs(c) == [], errs(c))

print("\nすべて通った（%d）" % ok if ng == 0 else "\n× %d 件（OK %d）" % (ng, ok))
sys.exit(1 if ng else 0)
