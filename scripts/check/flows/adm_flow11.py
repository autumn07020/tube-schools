# -*- coding: utf-8 -*-
"""⑤ 学年の繰り上げを通す：管理ページで日付を入れる → その日になる → 小6→中1 は聞かれる・中3 は卒業・ほかは同じ記号で上がる。"""
import json, os, subprocess, sys, time, urllib.request, urllib.error
S = sys.argv[1]
os.environ["MYACADY_ROOT"] = S + "/real"; os.environ["MYACADY_FSYNC"] = "0"
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server")
from cdp import Chrome
import scram, paths
import tube_server as T
import retire as R
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots11"; os.makedirs(OUT, exist_ok=True); SC = "waseaca-london"
ok = ng = 0
def check(name, cond, detail=""):
    global ok, ng
    if cond: ok += 1; print("  OK   " + name)
    else: ng += 1; print("  ×    %s  %s" % (name, detail))
def errs(c): return json.loads(c.eval("JSON.stringify(window.__errs||[])"))
def watch(c): c.eval("window.__errs=[]; window.addEventListener('error', function(e){ window.__errs.push(String(e.message)); }); window.addEventListener('unhandledrejection', function(e){ window.__errs.push(String(e.reason && e.reason.stack || e.reason)); });")
def click(c, sel): return c.eval("(function(){var b=document.querySelector(%s); if(b){b.click(); return true;} return false;})()" % json.dumps(sel))
def api(method, path, tok=None, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode())
    req.add_header("Content-Type", "application/json")
    if tok: req.add_header("Authorization", "Bearer " + tok)
    try:
        r = urllib.request.urlopen(req, timeout=60); return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")
HOME = "!document.querySelector('.jn') && !document.querySelector('#welcome:not(.out)') && !!document.querySelector('[data-tab]')"
def day(n): return time.strftime("%Y-%m-%d", time.localtime(time.time() + n * 86400))

r = subprocess.run([sys.executable, S + "/tube/server/tube_server.py", "go-live", "--school", SC, "--yes"], env=dict(os.environ), capture_output=True, text=True)
assert r.returncode == 0, r.stdout[-300:] + r.stderr[-300:]
code = T.school_meta(SC)["join"]["code"]
tbl = T.class_table(SC)
def first(g): return sorted(cid for cid, c in tbl.items() if c.get("grade") == g)[0]
PW = "kuriage no kensa 2026"
kids = [{"grade": "e6", "classId": first("e6"), "subjects": ["japanese", "math"]}, {"grade": "j3", "classId": first("j3"), "subjects": ["japanese", "math"]},
        {"grade": "e4", "classId": first("e4"), "subjects": ["japanese", "math"]}]
c_, j = api("POST", "/api/join", None, {"code": code, "agree": True, "students": kids})
made = j["made"]
api("POST", "/api/join/finish", None, {"items": [{"id": m["id"], "setup": m["setup"], "verifier": scram.make_verifier(PW)} for m in made]})
k6, k3, k4 = [m["id"] for m in made]
n_j1 = len([1 for c in tbl.values() if c.get("grade") == "j1"])

def enter(b, lid):
    b.goto(BASE + "/", wait=0.6); b.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');"); b.goto("about:blank", wait=0.2); b.goto(BASE + "/", wait=0.6); watch(b)
    b.wait_for("!!document.querySelector('#lId')")
    b.eval("document.querySelector('#lId').value=%s; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();" % (json.dumps(lid), json.dumps(PW)))
    return b.wait_for(HOME, 40)

with Chrome(width=1440, height=900, scale=2, port=9842) as c, Chrome(width=430, height=900, scale=2, mobile=True, port=9843) as kid:
    print("\n管理ページ：新年度のはじまり")
    c.goto(BASE + "/admin", wait=1.0); watch(c)
    c.wait_for("!!document.querySelector('#gId')")
    c.eval("document.querySelector('#gId').value='wadmin99'; document.querySelector('#gPw').value='kensa-kanri-kensa-kanri-kensa-0000'; document.querySelector('#gGo').click();")
    assert c.wait_for("!!document.querySelector('.tabs')", 25); time.sleep(0.8)
    card = c.eval("(document.querySelector('.card.year')||{}).innerText || ''")
    check("「新年度のはじまり」の札：何が起きるかが書いてある。まだ入っていない", "学年が1つ上がります" in card and "中3は卒業" in card and "まだ入っていません" in card, card[:200])
    c.eval("document.querySelector('#yrDate').value=%s; document.querySelector('[data-act=\"yearset\"]').click();" % json.dumps(day(0)))
    time.sleep(1.0)
    toast = c.eval("(document.querySelector('#toast')||{}).innerText || ''") or ""
    import exams as EX
    check("きょうの日付は入らない（わけが出る）", "あした以降" in toast and EX.year_start(SC) == "", toast)
    c.eval("document.querySelector('#yrDate').value=%s; document.querySelector('[data-act=\"yearset\"]').click();" % json.dumps(day(1)))
    c.wait_for("/入っています/.test((document.querySelector('.card.year')||{}).innerText || '')", 15)
    card = c.eval("(document.querySelector('.card.year')||{}).innerText || ''")
    check("あしたの日付を入れると「入っています　あと 1日」", "入っています" in card and day(1).replace("-", "/") in card and "あと 1日" in card, card[:260])
    c.eval("document.querySelector('.card.year').scrollIntoView({block:'center'})"); time.sleep(0.4)
    c.shot(os.path.join(OUT, "y1-year-set.png"))

    got = R.roll(T, SC, now=time.time() + 86400 + 3600)        # その日の朝になった
    check("その日になると、繰り上がる（上がった 2・卒業 1・聞く %d）" % (1 if n_j1 > 1 else 0), got and got["up"] == 2 and got["grad"] == 1 and got["ask"] == (1 if n_j1 > 1 else 0), got)

    print("\n小6 → 中1 の生徒")
    check("入れる（ホームが出る）", enter(kid, k6))
    time.sleep(1.2)
    txt = kid.eval("(document.querySelector('#paCard')||{}).innerText || ''")
    check("ホームのいちばん上に「新しい学年　中1のクラスを教えてください」", "新しい学年" in txt and "中1のクラスを教えてください" in txt, txt[:160])
    n_tiles = kid.eval("document.querySelectorAll('#paCard [data-pa]').length")
    check("中1のクラスが並ぶ。選ぶまで押せない", n_tiles == n_j1 and kid.eval("document.querySelector('#paGo').disabled") is True, n_tiles)
    kid.shot(os.path.join(OUT, "y2-ask-j1.png"))
    kid.eval("document.querySelector('#paCard [data-pa]').click()"); time.sleep(0.4)
    check("選ぶと「このクラスにする」", "このクラスにする" in (kid.eval("document.querySelector('#paGo').innerText") or ""))
    click(kid, "#paGo")
    check("答えると札が消え、中1のクラスに入っている", kid.wait_for("!document.querySelector('#paCard') && !!document.querySelector('[data-tab]')", 30) and T.accounts(SC)[k6]["classId"].startswith("j1") and T.accounts(SC)[k6]["level"] == "j1", T.accounts(SC)[k6].get("classId"))
    time.sleep(1.0); kid.eval("TubeUI.go('settings')"); time.sleep(0.8)
    body = kid.eval("document.querySelector('#main').innerText")
    check("設定のクラスが 中1 になっている", "中1" in body, body[:200])
    check("JS のエラーが無い", not errs(kid), errs(kid)[:3])

    print("\n中3 の生徒（卒業）")
    check("入れる（ホームが出る）", enter(kid, k3))
    time.sleep(1.2)
    txt = kid.eval("(document.querySelector('#gradCard')||{}).innerText || ''")
    check("ホームに「卒業おめでとうございます」。クラスは聞かれない", "卒業おめでとうございます" in txt and "3か月" in txt and not kid.eval("!!document.querySelector('#paCard')"), txt[:160])
    kid.shot(os.path.join(OUT, "y3-grad.png"))
    kid.eval("TubeUI.go('settings')"); time.sleep(0.8)
    check("設定も開ける（クラスが無くても崩れない）", kid.eval("!!document.querySelector('#mPlace')") and not errs(kid), errs(kid)[:3])
    kid.shot(os.path.join(OUT, "y4-grad-settings.png"))

    print("\n小4 の生徒（同じ記号で上がる）")
    check("入れる（ホームが出る）", enter(kid, k4))
    time.sleep(1.0); kid.eval("TubeUI.go('settings')"); time.sleep(0.8)
    body = kid.eval("document.querySelector('#main').innerText")
    check("設定のクラスが 小5 になっている。何も聞かれない", "小5" in body and T.accounts(SC)[k4]["classId"] == first("e4").replace("e4", "e5", 1), body[:200])
    check("JS のエラーが無い", not errs(kid), errs(kid)[:3])

    print("\n管理ページ：繰り上げのあと")
    c.goto(BASE + "/admin", wait=1.0); watch(c)
    c.wait_for("!!document.querySelector('.card.year') || !!document.querySelector('#gId')", 20)
    if c.eval("!!document.querySelector('#gId')"):
        c.eval("document.querySelector('#gId').value='wadmin99'; document.querySelector('#gPw').value='kensa-kanri-kensa-kanri-kensa-0000'; document.querySelector('#gGo').click();")
        c.wait_for("!!document.querySelector('.card.year')", 25)
    time.sleep(0.8)
    card = c.eval("(document.querySelector('.card.year')||{}).innerText || ''")
    check("札に「この前の繰り上げ　上がった 2人・卒業 1人」", "この前の繰り上げ" in card and "上がった 2人" in card and "卒業 1人" in card, card[:300])
    rec = c.eval("(document.querySelector('.card.recent')||{}).innerText || ''")
    check("最近の動きに「学年の繰り上げ」", "学年の繰り上げ" in rec, rec[:200])
    c.eval("(function(){ var t=document.querySelectorAll('.tabs [data-act=\"tab\"]'); for(var i=0;i<t.length;i++){ if(t[i].innerText.replace(/\\s+/g,'') === '生徒') t[i].click(); } })()"); time.sleep(0.8)
    loose = c.eval("(document.querySelector('.card.loose')||{}).innerText || ''")
    check("生徒のタブに「クラスの決まっていない生徒」：卒業した ID", k3 in loose and "卒業" in loose and k6 not in loose, loose[:200])
    c.eval("document.querySelector('.card.loose').scrollIntoView({block:'center'})"); time.sleep(0.4)
    c.shot(os.path.join(OUT, "y5-loose.png"))
    c.eval("document.querySelector('.card.loose [data-act=\"place\"]').click()"); time.sleep(0.6)
    sheet = c.eval("(document.querySelector('.sheet')||{}).innerText || ''")
    check("「変える」で、学年・クラス・科目の紙が開く（中3が選ばれている）", k3 in sheet and "学年" in sheet and c.eval("!!document.querySelector('[data-act=\"pgrade\"][aria-pressed=\"true\"]')"), sheet[:120])
    c.eval("document.querySelector('[data-act=\"pback\"]').click()"); time.sleep(0.5)
    check("「もどる」で、生徒の一覧に戻る（崩れない）", c.eval("!document.querySelector('.sheet') || getComputedStyle(document.querySelector('.sheet')).display === 'none' || !document.querySelector('[data-act=\"psave\"]')") and c.eval("!!document.querySelector('.card.loose')"))
    c.eval("document.querySelector('#findId').value=%s; document.querySelector('[data-act=\"find\"]').click()" % json.dumps(k3)); time.sleep(0.6)
    check("ID でさがすと、その行が見つかる（紙は開かない）", c.eval("!!document.getElementById('row-' + %s)" % json.dumps(k3)) and "いません" not in (c.eval("(document.querySelector('#toast.on')||{}).innerText || ''") or ""))
    check("管理ページに JS のエラーが無い", not errs(c), errs(c)[:3])
print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng else "通っていないものがある", ok, ng))
