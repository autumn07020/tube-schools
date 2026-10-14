# -*- coding: utf-8 -*-
"""⑤ 3か月使われない口座の破棄を、本番に切り替えた校舎で通す：管理ページの「使われていない口座」・片づけ・入り直し。
あわせて、Safari で小さくなっていた <select> の高さを見る。"""
import json, os, subprocess, sys, time, urllib.request, urllib.error
S = sys.argv[1]
os.environ["MYACADY_ROOT"] = S + "/real"; os.environ["MYACADY_FSYNC"] = "0"
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server")
from cdp import Chrome
import scram, paths
import tube_server as T
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots10"; os.makedirs(OUT, exist_ok=True); SC = "waseaca-london"
ok = ng = 0
def check(name, cond, detail=""):
    global ok, ng
    if cond: ok += 1; print("  OK   " + name)
    else: ng += 1; print("  ×    %s  %s" % (name, detail))
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
def cli(*a):
    return subprocess.run([sys.executable, S + "/tube/server/tube_server.py"] + list(a), env=dict(os.environ), capture_output=True, text=True)

r = cli("go-live", "--school", SC, "--yes")
assert r.returncode == 0, r.stdout[-300:] + r.stderr[-300:]
code = T.school_meta(SC)["join"]["code"]
PW = "katazuke no kensa 2026"
c_, j = api("POST", "/api/join", None, {"code": code, "agree": True, "students": [{"grade": "e4", "classId": "e4a", "subjects": ["japanese", "math"]}] * 2})
made = j["made"]
api("POST", "/api/join/finish", None, {"items": [{"id": m["id"], "setup": m["setup"], "verifier": scram.make_verifier(PW)} for m in made]})
old, near = made[0]["id"], made[1]["id"]
now = int(time.time())
with T.LOCK:
    db = T.accounts(SC)
    db[old]["used"] = now - 95 * 86400; db[near]["used"] = now - 85 * 86400
    db[old]["created"] = db[near]["created"] = now - 200 * 86400
    T.save_accounts(SC, db)
    meta = dict(T.school_meta(SC)); meta["liveAt"] = now - 300 * 86400
    paths.save(paths.school_file(SC, "school.json"), meta)

with Chrome(width=1440, height=900, scale=2, port=9840) as c:
    c.goto(BASE + "/admin", wait=1.0); watch(c)
    c.wait_for("!!document.querySelector('#gId')")
    c.eval("document.querySelector('#gId').value='wadmin99'; document.querySelector('#gPw').value='kensa-kanri-kensa-kanri-kensa-0000'; document.querySelector('#gGo').click();")
    assert c.wait_for("!!document.querySelector('.tabs')", 25); time.sleep(0.8)
    card = c.eval("(document.querySelector('.card.idle')||{}).innerText || ''")
    check("いまの様子に「使われていない口座」：3か月の決まりと、もうすぐ消える ID（あと何日）", "3か月" in card and old in card and near in card and "あと 0日" in card and "あと 7日" in card, card[:300])
    c.eval("document.querySelector('.card.idle').scrollIntoView({block:'center'})"); time.sleep(0.4)
    c.shot(os.path.join(OUT, "m1-idle.png"))
    r = cli("housekeep", "--dry")
    check("housekeep --dry：消すはずの ID を見せるだけ", r.returncode == 0 and old in r.stdout and near not in r.stdout and old in T.accounts(SC), r.stdout[-300:])
    r = cli("housekeep")
    check("housekeep：破棄する。口座が消え、ID は空きに戻る", r.returncode == 0 and old in r.stdout and old not in T.accounts(SC) and near in T.accounts(SC) and paths.school_of_login(old) is None, r.stdout[-300:])
    st, d = scram.login(BASE, old, PW)
    check("消えた ID では、もう入れない", st in (401, 403), st)
    st, d = scram.login(BASE, near, PW)
    api("GET", "/api/me", d.get("token"))
    c.goto(BASE + "/admin", wait=1.0); watch(c)
    c.wait_for("!!document.querySelector('.card.idle') || !!document.querySelector('#gId')", 20)
    if c.eval("!!document.querySelector('#gId')"):
        c.eval("document.querySelector('#gId').value='wadmin99'; document.querySelector('#gPw').value='kensa-kanri-kensa-kanri-kensa-0000'; document.querySelector('#gGo').click();")
        c.wait_for("!!document.querySelector('.card.idle')", 25)
    time.sleep(0.8)
    card = c.eval("(document.querySelector('.card.idle')||{}).innerText || ''")
    rec = c.eval("(document.querySelector('.card.recent')||{}).innerText || ''")
    check("もう1人は、一度入ったので消えない。「これまでに消えた口座 1」。最近の動きに「使われず破棄」", "ありません" in card and near not in card and "1" in card and "使われず破棄" in rec and old in rec, (card[:200], rec[:200]))
    c.eval("document.querySelector('.card.idle').scrollIntoView({block:'center'})"); time.sleep(0.4)
    c.shot(os.path.join(OUT, "m2-idle-after.png"))
    check("JS のエラーが無い", not errs(c), errs(c)[:3])
print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng else "通っていないものがある", ok, ng))
