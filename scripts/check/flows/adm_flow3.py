# -*- coding: utf-8 -*-
"""第三者の検査のあとで直した所を、Chrome で実際に押す：
届いたリンクで ID がすりかわらない（聞いてから）／あいことばを見せる・かくす／講師の名簿づくり（端末が合言葉を作る）。"""
import json, os, re, sys, time, urllib.request, urllib.error
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server")
from cdp import Chrome
import scram
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots3"; os.makedirs(OUT, exist_ok=True)
ok = ng = 0
def check(name, cond, detail=""):
    global ok, ng
    if cond: ok += 1; print("  OK   " + name)
    else: ng += 1; print("  ×    %s  %s" % (name, detail))
def click(c, sel): return c.eval("(function(){var b=document.querySelector(%s); if(b){b.click(); return true;} return false;})()" % json.dumps(sel))
def text(c, sel): return c.eval("(function(){var b=document.querySelector(%s); return b ? b.innerText : null;})()" % json.dumps(sel))
def errs(c): return json.loads(c.eval("JSON.stringify(window.__errs||[])"))
def watch(c): c.eval("window.__errs=[]; window.addEventListener('error', function(e){ window.__errs.push(String(e.message)); }); window.addEventListener('unhandledrejection', function(e){ window.__errs.push(String(e.reason)); });")

def pass_ask(kid):
    """初回の申告（教科は？）が出たら「あとで」を押す（デモの席は科目が無いので出る）。"""
    if kid.wait_for("!!document.querySelector('#dcLater') || !!document.querySelector('[data-tab]')", 25) and kid.eval("!!document.querySelector('#dcLater')"):
        kid.eval("document.querySelector('#dcLater').click()"); time.sleep(0.8)
def me(tok):
    req = urllib.request.Request(BASE + "/api/me"); req.add_header("Authorization", "Bearer " + (tok or "x"))
    try:
        r = urllib.request.urlopen(req, timeout=30); return r.status, json.loads(r.read().decode()).get("profile", {})
    except urllib.error.HTTPError as e:
        return e.code, {}
TOK = "localStorage.getItem('tube.school.v1.token')"
WHO = "localStorage.getItem('tube.school.v1.who')"
IN = "!document.querySelector('#lId') && !document.querySelector('#caGo') && !document.querySelector('#welcome:not(.out)')"
A, PA = "we4a20", "kensa-seito-kensa-0000"
B, PB = "we4a21", "kensa-seito-kensa-0021"

with Chrome(width=430, height=900, scale=2, mobile=True, port=9813) as kid, Chrome(width=1280, height=900, scale=2, port=9814) as t:
    print("\n入口")
    kid.goto(BASE + "/", wait=0.8); kid.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');"); kid.goto("about:blank", wait=0.2); kid.goto(BASE + "/", wait=0.8); watch(kid)
    kid.wait_for("!!document.querySelector('#lId')")
    labels = kid.eval("Array.prototype.map.call(document.querySelectorAll('.lg-card .lbl'), function(x){ return x.innerText; }).join('|')")
    check("入口の欄の名前は ID と あいことば", "ID" in labels and "あいことば" in labels, labels)
    t0 = kid.eval("document.querySelector('#lPw').type"); click(kid, "#lShow"); t1 = kid.eval("document.querySelector('#lPw').type"); click(kid, "#lShow"); t2 = kid.eval("document.querySelector('#lPw').type")
    check("あいことばを 見えるようにする・かくす", (t0, t1, t2) == ("password", "text", "password"), (t0, t1, t2))
    kid.shot(os.path.join(OUT, "d1-login.png"))
    kid.eval("document.querySelector('#lId').value=%s; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();" % (json.dumps(A), json.dumps(PA)))
    pass_ask(kid)
    check("A で入れる", kid.wait_for(IN, 30)); time.sleep(1.0)
    tokA = kid.eval(TOK)
    check("いま入っている ID を端末が覚える（合言葉は覚えない）", kid.eval(WHO) == A and PA.replace("-", "") not in kid.eval("JSON.stringify(localStorage)").replace("-", ""), kid.eval(WHO))

    print("\n届いたリンク・カード（入っている画面に）")
    kid.eval("location.hash = %s" % json.dumps("#k=%s.%s" % (A, PA))); time.sleep(2.5)
    check("同じ ID のカードを読んでも、何も起きない（入りなおさない・聞かない）", kid.eval(IN) and kid.eval(TOK) == tokA and kid.eval("location.hash") == "", (kid.eval("location.href"), kid.eval(TOK) == tokA))
    kid.eval("location.hash = %s" % json.dumps("#k=%s.%s" % (B, PB)))
    check("べつの ID のリンクが来たら、聞く", kid.wait_for("!!document.querySelector('#caGo')", 15))
    body = kid.eval("document.querySelector('#main').innerText")
    check("いまの ID と とどいた ID の両方が出る。合言葉は画面にも番地にも無い", A in body and B in body and PB not in body and kid.eval("location.hash") == "", body[:120])
    check("聞いているあいだは、まだ A のまま", kid.eval(TOK) == tokA and me(tokA)[1].get("seat") == "20")
    kid.shot(os.path.join(OUT, "d2-cardask.png"))
    wide = kid.eval("document.documentElement.scrollWidth <= window.innerWidth")
    check("聞く画面が横にはみ出さない", wide)
    click(kid, "#caNo"); time.sleep(1.0); pass_ask(kid)
    check("「いまのまま つづける」で、A のまま ふつうの画面に戻る", kid.wait_for(IN + " && !!document.querySelector('[data-tab]')", 30) and kid.eval(TOK) == tokA and kid.eval(WHO) == A, kid.eval(WHO))
    # QR を読んだとき（ページを開くところから）
    kid.goto("about:blank", wait=0.2); kid.goto(BASE + "/#k=%s.%s" % (B, PB), wait=1.0); watch(kid)
    check("開くところからでも、聞く（番地から合言葉は消える）", kid.wait_for("!!document.querySelector('#caGo')", 20) and kid.eval("location.hash") == "" and kid.eval(TOK) == tokA)
    click(kid, "#caGo")
    pass_ask(kid)
    check("「とどいた ID で 入りなおす」で、B になる", kid.wait_for(IN + " && %s === %s" % (WHO, json.dumps(B)), 40), kid.eval(WHO))
    time.sleep(1.0)
    tokB = kid.eval(TOK)
    check("B の印は B のもの・A の印は もう使えない", me(tokB)[1].get("seat") == "21" and me(tokA)[0] == 401, (me(tokB), me(tokA)[0]))
    # まちがった合言葉のリンク
    kid.eval("location.hash = %s" % json.dumps("#k=%s.%s" % (A, "chigau-chigau-chigau-0000")))
    kid.wait_for("!!document.querySelector('#caGo')", 15); click(kid, "#caGo")
    check("まちがったリンクは、入口に戻って わけを言う（ID は入れてある）", kid.wait_for("!!document.querySelector('#lId') && document.querySelector('#lId').value === %s && !!document.querySelector('.loginmsg.on')" % json.dumps(A), 30), text(kid, ".loginmsg"))
    check("生徒の画面に JS のエラーが無い", not errs(kid), errs(kid)[:3])

    print("\n講師の名簿づくり（管理者のいない校舎＝デモ）")
    demo = {x["id"]: x["password"] for x in json.load(open(S + "/real/demo-accounts.json")) if x.get("password")}   # 入口の一覧の ID だけの行（ためしの入口）は合言葉を持たない
    t.goto(BASE + "/", wait=0.8); t.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');"); t.goto("about:blank", wait=0.2); t.goto(BASE + "/", wait=0.8); watch(t)
    t.wait_for("!!document.querySelector('#lId')")
    t.eval("document.querySelector('#lId').value='lteacher1'; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();" % json.dumps(demo["lteacher1"]))
    check("デモの講師で入れる", t.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)')", 30)); time.sleep(1.5)
    t.eval("window.__sent=[]; (function(){ var f = window.fetch; window.fetch = function(u, o){ if(String(u).indexOf('/roster/bulk') >= 0) window.__sent.push(String((o||{}).body||'')); return f.apply(this, arguments); }; })();")
    t.eval("TubeUI.go('people')"); time.sleep(0.8)
    check("名簿を登録する画面が開く", t.wait_for("!!document.querySelector('#bGo')", 10))
    cls = t.eval("document.querySelector('#bCls').value")
    t.eval("(function(){ var a=document.querySelector('#bFrom'), b=document.querySelector('#bTo'); a.value='41'; a.dispatchEvent(new Event('input')); b.value='42'; b.dispatchEvent(new Event('input')); })()")
    click(t, "#bGo")
    check("2人ぶん できる", t.wait_for("document.querySelectorAll('.ratelist .raterow').length === 2", 40), text(t, "#main")[:200])
    rows = json.loads(t.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('.ratelist .raterow .num'), function(x){ return x.innerText; }))"))
    pairs = [re.split(r"\s+", r.strip()) for r in rows]
    check("ID と あいことば（3語＋4桁）が画面に出る", all(len(p) == 2 and re.match(r"^([a-z]+-){3}\d{4}$", p[1]) for p in pairs), rows)
    sent = " ".join(json.loads(t.eval("JSON.stringify(window.__sent)")))
    check("サーバへ送った本文に、合言葉は無い（確かめるための値だけ）", bool(sent) and "storedKey" in sent and all(p[1] not in sent and p[1].replace("-", "") not in sent for p in pairs) and "password" not in sent, sent[:120])
    st, d = scram.login(BASE, pairs[0][0], pairs[0][1])
    check("画面に出た合言葉で、その生徒が入れる", st == 200 and d.get("profile", {}).get("seat") == "41" and d["profile"].get("classId") == cls, (st, d.get("error")))
    t.shot(os.path.join(OUT, "d3-roster-bulk.png"))
    tt = t.eval("localStorage.getItem('tube.school.v1.token')")
    req = urllib.request.Request(BASE + "/api/class"); req.add_header("Authorization", "Bearer " + tt)
    ros = urllib.request.urlopen(req, timeout=30).read().decode()
    check("作った生徒が、講師の名簿（サーバ）に出る", d["profile"]["sid"] in ros, ros[:120])
    check("講師の画面に JS のエラーが無い", not errs(t), errs(t)[:3])
print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng else "通っていないものがある", ok, ng))
