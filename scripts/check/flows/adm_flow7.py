# -*- coding: utf-8 -*-
"""② を Chrome で押す：生徒の設定からクラス・受講科目を変える／管理ページで ID をさがす・直す・最近の動き。"""
import json, os, re, sys, time, urllib.request, urllib.error
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server")
from cdp import Chrome
import scram
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots7"; os.makedirs(OUT, exist_ok=True)
ok = ng = 0
def check(name, cond, detail=""):
    global ok, ng
    if cond: ok += 1; print("  OK   " + name)
    else: ng += 1; print("  ×    %s  %s" % (name, detail))
def click(c, sel): return c.eval("(function(){var b=document.querySelector(%s); if(b){b.click(); return true;} return false;})()" % json.dumps(sel))
def text(c, sel): return c.eval("(function(){var b=document.querySelector(%s); return b ? b.innerText : null;})()" % json.dumps(sel))
def errs(c): return json.loads(c.eval("JSON.stringify(window.__errs||[])"))
def watch(c): c.eval("window.__errs=[]; window.addEventListener('error', function(e){ window.__errs.push(String(e.message)); }); window.addEventListener('unhandledrejection', function(e){ window.__errs.push(String(e.reason && e.reason.stack || e.reason)); });")
def api(method, path, tok=None, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode())
    req.add_header("Content-Type", "application/json")
    if tok: req.add_header("Authorization", "Bearer " + tok)
    try:
        r = urllib.request.urlopen(req, timeout=60); return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")
HOME = "!document.querySelector('.jn') && !document.querySelector('#welcome:not(.out)') && !!document.querySelector('[data-tab]')"
st, d = scram.login(BASE, "wadmin99", "kensa-kanri-kensa-kanri-kensa-0000", admin=True); adm = d["token"]
code = api("POST", "/api/admin/join/code", adm, {})[1]["join"]["code"]
PW = "settei no kensa 2026"
c_, j = api("POST", "/api/join", None, {"code": code, "agree": True, "students": [{"grade": "e4", "classId": "e4a", "subjects": ["japanese", "math"]}]})
sid = j["made"][0]["id"]
api("POST", "/api/join/finish", None, {"items": [{"id": sid, "setup": j["made"][0]["setup"], "verifier": scram.make_verifier(PW)}]})

with Chrome(width=430, height=900, scale=2, mobile=True, port=9834) as kid, Chrome(width=1440, height=900, scale=2, port=9835) as c:
    print("\n生徒の設定から変える")
    kid.goto(BASE + "/", wait=0.6); kid.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');"); kid.goto("about:blank", wait=0.2); kid.goto(BASE + "/", wait=0.6); watch(kid)
    kid.wait_for("!!document.querySelector('#lId')")
    kid.eval("document.querySelector('#lId').value=%s; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();" % (json.dumps(sid), json.dumps(PW)))
    check("登録した ID で入ると、質問なしでホーム", kid.wait_for(HOME, 40) and not kid.eval("!!document.querySelector('.dc-card')"))
    time.sleep(1.0); kid.eval("TubeUI.go('settings')"); time.sleep(0.8)
    body = kid.eval("document.querySelector('#main').innerText")
    check("設定に、いまのクラスと受講科目、変えるボタンが出る", "小4α" in body and "国語" in body and "算数" in body and kid.eval("!!document.querySelector('#mPlace')"), body[:160])
    kid.shot(os.path.join(OUT, "h1-settings.png"))
    click(kid, "#mPlace")
    check("変える画面：いまの学年・クラス・科目が選ばれている。変えるまで「この内容に変える」は押せない", kid.wait_for("!!document.querySelector('.jn-place')", 15) and kid.eval("document.querySelector('[data-act=\"grade\"][aria-pressed=\"true\"]').getAttribute('data-v')") == "e4" and kid.eval("document.querySelector('[data-act=\"class\"][aria-pressed=\"true\"]').getAttribute('data-v')") == "e4a" and kid.eval("document.querySelector('#plGo').disabled"))
    click(kid, '[data-act="class"][data-v="e4b"]'); time.sleep(0.3); click(kid, '[data-act="subj"][data-v="1"]'); time.sleep(0.3)
    kid.shot(os.path.join(OUT, "h2-place.png"))
    check("横にはみ出さない", kid.eval("document.documentElement.scrollWidth <= window.innerWidth"))
    click(kid, "#plGo")
    check("変えると、幕を出さずに設定へ戻り、新しいクラスと科目が出る", kid.wait_for("!document.querySelector('.jn-place') && !!document.querySelector('#mPlace')", 30) and "小4β" in kid.eval("document.querySelector('#main').innerText") and "理科" in kid.eval("document.querySelector('#main').innerText"), kid.eval("document.querySelector('#main').innerText")[:160])
    head = kid.eval("(document.querySelector('header')||{}).innerText || ''").replace("\n", " ")
    check("上の呼び名も「小4β ID」に変わる（ID は同じ）", ("小4β " + sid) in head, head)
    stt, dd = scram.login(BASE, sid, PW)
    check("ほかの端末で入っても同じ（ID に集まる）", stt == 200 and dd["profile"]["classId"] == "e4b" and dd["profile"]["subjects"] == ["japanese", "math", "science", "social"])
    click(kid, "#mPlace"); kid.wait_for("!!document.querySelector('.jn-place')", 15); click(kid, "#plNo")
    check("「やめる」で、何も変えずに設定へ戻る", kid.wait_for("!!document.querySelector('#mPlace') && !document.querySelector('.jn-place')", 10) and scram.login(BASE, sid, PW)[1]["profile"]["classId"] == "e4b")
    check("生徒の画面に JS のエラーが無い", not errs(kid), errs(kid)[:3])

    print("\n管理ページ：生徒")
    c.goto(BASE + "/admin", wait=1.0); watch(c)
    c.wait_for("!!document.querySelector('#gId')")
    c.eval("document.querySelector('#gId').value='wadmin99'; document.querySelector('#gPw').value='kensa-kanri-kensa-kanri-kensa-0000'; document.querySelector('#gGo').click();")
    assert c.wait_for("!!document.querySelector('.tabs')", 25); time.sleep(0.8)
    rec = c.eval("(document.querySelector('.card.recent')||{}).innerText || ''")
    check("いまの様子に「最近の動き」：登録と変更（何から何へ）", "登録" in rec and "変更" in rec and sid in rec and "→" in rec, rec[:200])
    c.shot(os.path.join(OUT, "h3-recent.png"))
    tabs = c.eval("Array.prototype.map.call(document.querySelectorAll('.tabs [data-act=\"tab\"]'), function(b){ return b.innerText.replace(/\\s+/g,''); }).join('|')")
    check("タブの名前は「生徒」", "|生徒|" in ("|" + tabs + "|"), tabs)
    click(c, '[data-act="tab"][data-v="seats"]'); time.sleep(0.5)
    c.eval("document.querySelector('#findId').value=%s" % json.dumps(sid.upper())); click(c, '[data-act="find"]'); time.sleep(0.8)
    row = c.eval("(document.querySelector('.row.hit')||{}).innerText || ''")
    check("ID でさがすと、その生徒のクラスが開き、行に科目が出る（大文字でも）", sid in row and "国算理社" in row and "使っている" in row and (text(c, ".sheet h2") or "").strip() == "小4β", row[:120])
    check("席を足す道具は無い", not c.eval("!!document.querySelector('#addN')"))
    c.shot(os.path.join(OUT, "h4-class.png"))
    click(c, '[data-act="place"][data-id="%s"]' % sid); time.sleep(0.5)
    check("「学年・クラス・科目を変える」の紙が開く（いまの内容が選ばれている）", (text(c, ".sheet h2") or "").startswith(sid) and c.eval("document.querySelector('[data-act=\"pclass\"][aria-pressed=\"true\"]').getAttribute('data-v')") == "e4b")
    click(c, '[data-act="pclass"][data-v="e4a"]'); time.sleep(0.2); click(c, '[data-act="psubj"][data-v="0"]'); time.sleep(0.2)
    c.shot(os.path.join(OUT, "h5-admin-place.png"))
    click(c, '[data-act="psave"]'); time.sleep(1.5)
    row = c.eval("(document.querySelector('.row.hit')||{}).innerText || ''")
    check("管理者が直すと、行き先のクラスの紙に移り、科目も変わる", (text(c, ".sheet h2") or "").strip() == "小4α" and sid in row and "国算" in row and "理" not in row, row[:120])
    c.eval("document.querySelector('[data-act=\"close\"]').click()"); time.sleep(0.3)
    c.eval("document.querySelector('#findId').value='s-nai'"); click(c, '[data-act="find"]'); time.sleep(0.6)
    check("無い ID は、わけを言う", "いません" in (text(c, "#toast") or ""), text(c, "#toast"))
    check("管理ページに JS のエラーが無い", not errs(c), errs(c)[:3])
print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng else "通っていないものがある", ok, ng))
