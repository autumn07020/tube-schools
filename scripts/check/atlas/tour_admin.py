# -*- coding: utf-8 -*-
"""管理ページ（/admin）を撮る。タブごとに撮り、押せる部品を1種類ずつ押して、出てきた紙も撮る。 python3 tour_admin.py <S> <dev> [pages]"""
import hashlib, json, os, sys, time, urllib.request
from atlaslib import *
import scram
DV = sys.argv[2]; PAGES_ONLY = len(sys.argv) > 3 and sys.argv[3] == "pages"
ADMIN, APW = "wadmin99", "kensa-kanri-kensa-kanri-kensa-0000"
def api(method, path, tok=None, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode())
    req.add_header("Content-Type", "application/json")
    if tok: req.add_header("Authorization", "Bearer " + tok)
    try:
        r = urllib.request.urlopen(req, timeout=60); return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {}
# 下ごしらえ：報告を2件・入口の見張りを1件・組分けテストの日程（管理ページに中身があるように）
if not PAGES_ONLY:
    st, d = scram.login(BASE, "we4a20", "kensa-seito-kensa-0000")
    if st == 200:
        api("POST", "/api/report", d["token"], {"text": "写真を送るボタンを押しても、ずっと「送信しています」のままです。", "view": "homework", "ctx": {"w": "390"}})
        api("POST", "/api/report", d["token"], {"text": "毎日テストの3問目で、選択肢が画面からはみ出します。", "view": "daily", "ctx": {"w": "390"}})
    for i in range(9): scram.login(BASE, "we4a21", "chigau-aikotoba-%d" % i)
    st, d = scram.login(BASE, ADMIN, APW, admin=True)
    day = lambda n: time.strftime("%Y-%m-%d", time.localtime(time.time() + n * 86400))
    api("PUT", "/api/admin/exams", d["token"], {"exams": [{"date": day(-30)}, {"date": day(5)}, {"date": day(40)}], "resultDays": 7})
SKIP = {"tab", "close", "out", "del", "classdel", "state", "arm", "unassign", "cardclear", "joinnew", "yeardel", "yearset", "examadd", "examdel", "examdays", "psave",
        "csvsave", "repdone", "movego", "moveundo", "copy", "copymsg", "csvcopy", "movecopy", "joincopy", "login", "upto", "find", "pback", "moveback", "", "1"}
SIG = """(function(){ function vis(e){ var r=e.getBoundingClientRect(); return r.width>0&&r.height>0; } function t(e){ return (e.innerText||'').replace(/\\s+/g,' ').trim(); }
  var sh = [].filter.call(document.querySelectorAll('.sheet'), vis).map(function(e){ return t(e).slice(0,90); });
  var m = document.querySelector('main') || document.body; return JSON.stringify({n: t(m).length, sheet: sh, tab: (document.querySelector('.tabs .on')||{}).innerText||''}); })()"""
ACTS = """(function(scope){ var out = {}; var root = document.querySelector(scope) || document.body;
  [].forEach.call(root.querySelectorAll('[data-act]'), function(e){ var r=e.getBoundingClientRect(); if(!(r.width>0&&r.height>0)) return; if(e.closest('.tabs')) return;
    var a = e.getAttribute('data-act'); if(!out[a]) out[a] = (e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,24); });
  return JSON.stringify(out); })"""
with Chrome(port=int(os.environ.get("ATLAS_PORT", "9895")), **DEV[DV]) as c:
    t = Tour(c, DV, "管理", ADMIN, "管理者")
    def opn(tab=None):
        c.goto(BASE + "/admin", wait=0.9)
        t.wait("!!document.querySelector('#gId') || !!document.querySelector('.tabs')", 20)
        if t.has("#gId"):
            c.eval("document.querySelector('#gId').value=%s; document.querySelector('#gPw').value=%s; document.querySelector('#gGo').click();" % (json.dumps(ADMIN), json.dumps(APW)))
            t.wait("!!document.querySelector('.tabs')", 30)
        time.sleep(0.9)
        if tab: t.click('[data-act="tab"][data-v="%s"]' % tab, wait=1.0)
    def sig(): return json.loads(c.eval(SIG))
    def keyof(s): return hashlib.md5(json.dumps([s["tab"], s["n"] // 60, s["sheet"]], ensure_ascii=False).encode()).hexdigest()[:8]
    # 入口
    c.goto(BASE + "/admin", wait=1.2)
    if t.has("#gId"): t.cap("00入口", "管理ページの入口", "https://…/admin", "ふつうの入口とは別。管理者の ID と合言葉。さわらないと30分で切れる", segs=1)
    TABS = [("now", "いまの様子"), ("seats", "生徒"), ("staff", "講師と担当"), ("out", "生徒に出ているもの"), ("cards", "カード"), ("rep", "報告")]
    n = 0
    for v, name in TABS:
        opn(v); n += 1
        t.cap("%d0%s" % (n, name), "管理ページ：" + name, "上のタブ「%s」" % name, segs=6)
        if PAGES_ONLY: continue
        base = sig(); seen = {keyof(base)}
        acts = json.loads(c.eval(ACTS + "('body')"))
        print("  [%s] acts: %s" % (name, " ".join(sorted(acts))), flush=True)
        k = 0
        for a in sorted(acts):
            if a in SKIP: continue
            opn(v)
            if not t.click('[data-act="%s"]' % a, wait=1.2): continue
            s = sig(); h = keyof(s)
            if h in seen: continue
            seen.add(h); k += 1
            lay = bool(s["sheet"])
            t.cap("%d%d%s-%s" % (n, k, name, a), "管理ページ：%s →「%s」" % (name, acts[a] or a), "「%s」のタブで「%s」を押す" % (name, acts[a] or a), layer=lay, segs=3 if lay else 4)
            if not lay: continue
            a2s = json.loads(c.eval(ACTS + "('.sheet')"))
            k2 = 0
            for a2 in sorted(a2s):
                if a2 in SKIP or a2 == a: continue
                opn(v); t.click('[data-act="%s"]' % a, wait=1.1)
                if not t.click('.sheet [data-act="%s"]' % a2, wait=1.2): continue
                s2 = sig(); h2 = keyof(s2)
                if h2 in seen: continue
                seen.add(h2); k2 += 1
                t.cap("%d%d%s-%s-%s" % (n, k, name, a, a2), "管理ページ：%s →「%s」→「%s」" % (name, acts[a] or a, a2s[a2] or a2), "紙の中で「%s」を押す" % (a2s[a2] or a2), layer=bool(s2["sheet"]), segs=3)
    t.save("admin-%s" % DV)
