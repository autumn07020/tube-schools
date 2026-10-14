# -*- coding: utf-8 -*-
"""③ 組分けの申告を Chrome で押す：管理者が日程を入れる → 生徒のホームに「クラスは どちらに？」→ 答える。"""
import json, os, re, sys, time, subprocess, urllib.request, urllib.error
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server")
from cdp import Chrome
import scram
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots8"; os.makedirs(OUT, exist_ok=True)
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
def day(n): return time.strftime("%Y-%m-%d", time.localtime(time.time() + n * 86400))
HOME = "!document.querySelector('.jn') && !document.querySelector('#welcome:not(.out)') && !!document.querySelector('[data-tab]')"
st, d = scram.login(BASE, "wadmin99", "kensa-kanri-kensa-kanri-kensa-0000", admin=True); adm = d["token"]
code = api("POST", "/api/admin/join/code", adm, {})[1]["join"]["code"]
PW = "kumiwake no kensa 2026"
kid2 = [{"grade": "e4", "classId": "e4a", "subjects": ["japanese", "math"]}] * 2
c_, j = api("POST", "/api/join", None, {"code": code, "agree": True, "students": kid2})
ids = [m["id"] for m in j["made"]]
api("POST", "/api/join/finish", None, {"items": [{"id": m["id"], "setup": m["setup"], "verifier": scram.make_verifier(PW)} for m in j["made"]]})
# 登録を10日前のことにする（結果が出る前からいた生徒）
subprocess.run([sys.executable, "-c", """
import sys, time
sys.path.insert(0, %r)
import tube_server as T
with T.LOCK:
    db = T.accounts('waseaca-london')
    for i in %r:
        db[i]['created'] = int(time.time()) - 10 * 86400
    T.save_accounts('waseaca-london', db)
""" % (S + "/tube/server", ids)], env=dict(os.environ, MYACADY_ROOT=S + "/real", MYACADY_FSYNC="0"), check=True)

def enter(kid, sid):
    kid.goto(BASE + "/", wait=0.6); kid.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');"); kid.goto("about:blank", wait=0.2); kid.goto(BASE + "/", wait=0.6); watch(kid)
    kid.wait_for("!!document.querySelector('#lId')")
    kid.eval("document.querySelector('#lId').value=%s; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();" % (json.dumps(sid), json.dumps(PW)))
    return kid.wait_for(HOME, 40)

# 原本（カリキュラム/カリキュラム.json）の組分け・月例が、日程の既定として入っている（小学部の印つき）。
# この流れは「空から入れる」を確かめるので、先に管理者が全部外す。外したら空のまま（原本で埋め戻さない）。
print("\n原本の日程（既定）")
_, st0 = api("GET", "/api/admin/state", adm)
it0 = (st0.get("exams") or {}).get("items") or []
check("原本の組分け・月例が既定で入っていて、小学部の印がある",
      len(it0) >= 5 and all(e.get("dept") == "elementary" for e in it0), str(it0)[:160])
_, d0 = api("PUT", "/api/admin/exams", adm, {"exams": [], "resultDays": 7})
check("管理者が全部外すと、空のまま", ((d0.get("state") or {}).get("exams") or {}).get("items") == [], str(d0)[:160])

with Chrome(width=430, height=900, scale=2, mobile=True, port=9836) as kid, Chrome(width=1440, height=900, scale=2, port=9837) as c:
    print("\n日程が無いあいだ")
    check("生徒のホームに、何も聞くものは出ない", enter(kid, ids[0]) and not kid.eval("!!document.querySelector('#paCard')"))

    print("\n管理者が日程を入れる")
    c.goto(BASE + "/admin", wait=1.0); watch(c)
    c.wait_for("!!document.querySelector('#gId')")
    c.eval("document.querySelector('#gId').value='wadmin99'; document.querySelector('#gPw').value='kensa-kanri-kensa-kanri-kensa-0000'; document.querySelector('#gGo').click();")
    assert c.wait_for("!!document.querySelector('.tabs')", 25); time.sleep(0.8)
    check("いまの様子に「組分けテストの日程」がある（まだ入っていない）", "まだ入っていません" in (text(c, ".card.exams") or ""), (text(c, ".card.exams") or "")[:80])
    click(c, '[data-act="examadd"]'); time.sleep(0.4)
    check("日を選ばずに「足す」は、わけを言う", "テストの日を選んでください" in (text(c, "#toast") or ""))
    c.eval("document.querySelector('#exDate').value=%s" % json.dumps(day(-9))); click(c, '[data-act="examadd"]'); time.sleep(1.2)
    card = text(c, ".card.exams") or ""
    check("9日前のテストを入れると「いま聞いています」と人数が出る", "いま聞いています" in card and day(-9).replace("-", "/") in card and re.search(r"答えた\s*0\s*／", card), card[:200])
    c.shot(os.path.join(OUT, "i1-admin-exams.png"))

    print("\n生徒が答える")
    check("ホームのいちばん上に「クラスはどちらになりましたか」", enter(kid, ids[0]) and kid.wait_for("!!document.querySelector('#paCard')", 10))
    tiles = kid.eval("Array.prototype.map.call(document.querySelectorAll('[data-pa]'), function(b){ return b.innerText.replace(/\\s+/g,' ').trim(); }).join('|')")
    check("その学年のクラス（α・β・K）が並び、いまのクラスに印。選ぶまで決められない", tiles.startswith("α") and "β" in tiles and "K" in tiles and "いま" in tiles and kid.eval("document.querySelector('#paGo').disabled"), tiles)
    time.sleep(1.0); kid.shot(os.path.join(OUT, "i2-ask.png"))
    click(kid, '[data-pa="e4b"]'); time.sleep(0.4)
    check("べつのクラスを選ぶと「このクラスに変える」", "変える" in (text(kid, "#paGo") or "") or "かえる" in (text(kid, "#paGo") or ""), text(kid, "#paGo"))
    kid.shot(os.path.join(OUT, "i3-ask-picked.png"))
    check("横にはみ出さない", kid.eval("document.documentElement.scrollWidth <= window.innerWidth"))
    click(kid, "#paGo")
    check("答えると札が消え、呼び名が新しいクラスになる（幕は出ない）", kid.wait_for("!document.querySelector('#paCard') && !!document.querySelector('[data-tab]')", 30) and ("小4β " + ids[0]) in kid.eval("(document.querySelector('header')||{}).innerText || ''").replace("\n", " "), kid.eval("(document.querySelector('header')||{}).innerText"))
    kid.goto("about:blank", wait=0.2); kid.goto(BASE + "/", wait=1.0)
    check("開き直しても、もう聞かれない", kid.wait_for(HOME, 30) and not kid.eval("!!document.querySelector('#paCard')"))
    check("2人目：同じクラスを選ぶと「変わらない」", enter(kid, ids[1]) and kid.wait_for("!!document.querySelector('#paCard')", 10) and click(kid, '[data-pa="e4a"]') and (time.sleep(0.4) or True) and ("かわらない" in (text(kid, "#paGo") or "") or "変わらない" in (text(kid, "#paGo") or "")), text(kid, "#paGo"))
    click(kid, "#paGo")
    check("答えると札が消え、クラスはそのまま", kid.wait_for("!document.querySelector('#paCard') && !!document.querySelector('[data-tab]')", 30) and scram.login(BASE, ids[1], PW)[1]["profile"]["classId"] == "e4a")
    check("生徒の画面に JS のエラーが無い", not errs(kid), errs(kid)[:3])

    print("\n管理ページ")
    click(c, '[data-act="tab"][data-v="seats"]'); time.sleep(0.4); click(c, '[data-act="tab"][data-v="now"]'); time.sleep(1.2)
    card = text(c, ".card.exams") or ""
    check("「答えた 2／…人」になる", bool(re.search(r"答えた\s*2\s*／", card)), card[:160])
    rec = text(c, ".card.recent") or ""
    check("最近の動きに「組分けの答え」「変更」が出る", "組分けの答え" in rec and "変更" in rec, rec[:160])
    click(c, '[data-act="examdel"][data-v="%s"]' % day(-9)); time.sleep(1.2)
    check("日程を外すと、聞くのをやめる", "いま聞いています" not in (text(c, ".card.exams") or "") and "placeAsk" not in scram.login(BASE, ids[0], PW)[1]["profile"])
    check("管理ページに JS のエラーが無い", not errs(c), errs(c)[:3])
print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng else "通っていないものがある", ok, ng))
