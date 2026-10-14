# -*- coding: utf-8 -*-
"""管理ページを Chrome で実際に押して確かめる（席を足す→合言葉が出る→その合言葉で生徒の入口から入れる、まで）。"""
import json, os, sys, time, urllib.request
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server")
from cdp import Chrome
import scram
def slogin(i, p, admin=False):
    return scram.login(BASE, i, p, admin=admin)
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots1"; os.makedirs(OUT, exist_ok=True)
ok = ng = 0
def check(name, cond, detail=""):
    global ok, ng
    if cond: ok += 1; print("  OK   " + name)
    else: ng += 1; print("  ×    %s  %s" % (name, detail))
def click(c, sel): return c.eval("(function(){var b=document.querySelector(%s); if(b){b.click(); return true;} return false;})()" % json.dumps(sel))
def text(c, sel): return c.eval("(function(){var b=document.querySelector(%s); return b ? b.innerText : null;})()" % json.dumps(sel))
def api(method, path, tok=None, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode())
    req.add_header("Content-Type", "application/json")
    if tok: req.add_header("Authorization", "Bearer " + tok)
    try:
        r = urllib.request.urlopen(req, timeout=30); return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")

with Chrome(width=1440, height=900, scale=2) as c:
    c.goto(BASE + "/admin", wait=1.0)
    c.eval("window.__errs=[]; window.addEventListener('error', function(e){ window.__errs.push(String(e.message)); }); window.addEventListener('unhandledrejection', function(e){ window.__errs.push(String(e.reason)); });")
    c.eval("document.querySelector('#gId').value='lteacher1'; document.querySelector('#gPw').value='lantern-4821'; document.querySelector('#gGo').click();")
    time.sleep(2.5)
    check("講師は管理ページに入れない（入口のまま・理由が出る）", c.eval("!!document.querySelector('#gId') && !!document.querySelector('.msg')"), text(c, ".msg"))
    c.eval("document.querySelector('#gId').value='wadmin99'; document.querySelector('#gPw').value='Kensa Kanri Kensa Kanri Kensa 0000'; document.querySelector('#gGo').click();")
    check("管理者は入れる（大文字・空白でも）", c.wait_for("!!document.querySelector('.tabs')", 20))
    check("合言葉は sessionStorage にだけある", c.eval("!!sessionStorage.getItem('tube.admin.token') && !localStorage.getItem('tube.admin.token') && !localStorage.getItem('tube.school.v1.token')"))
    click(c, '[data-act="tab"][data-v="seats"]'); time.sleep(0.5)
    c.shot(os.path.join(OUT, "b1-seats.png"))
    click(c, '[data-act="cls"][data-v="e4a"]'); time.sleep(0.6)
    check("席を足す道具は、もう無い（生徒は招待コードから登録する）", not c.eval("!!document.querySelector('[data-act=\"addseats\"]') || !!document.querySelector('#addN')"))
    rows = []
    for sid_ in ("we4a22", "we4a23"):
        click(c, '[data-act="more"][data-id="%s"]' % sid_); time.sleep(0.3)
        click(c, '[data-act="repw"][data-id="%s"]' % sid_)
        c.wait_for("!!document.querySelector('.fresh td.pw')", 40); time.sleep(0.3)
        r = json.loads(c.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('.fresh tr'), function(tr){ return Array.prototype.map.call(tr.children, function(td){ return td.innerText; }); }))"))
        rows.append(r[0])
        if sid_ == "we4a22":
            click(c, '[data-act="freshx"]'); time.sleep(0.5)
    check("合言葉を作り直すと、作った合言葉が1回だけ出る", len(rows) == 2 and c.eval("!!document.querySelector('.fresh td.pw')"))
    check("2席ぶん（ラベル・ID・合言葉）", len(rows) == 2 and rows[0][1] == "we4a22" and rows[1][1] == "we4a23", rows and [r[:2] for r in rows])
    ID_A, ID_B = rows[0][1], rows[1][1]
    import re
    check("合言葉は 3語＋4桁", all(re.match(r"^([a-z]{3,8}-){3}\d{4}$", r[2]) for r in rows), [len(r[2]) for r in rows])
    c.shot(os.path.join(OUT, "b2-fresh.png"))
    click(c, '[data-act="close"]'); time.sleep(0.3)
    check("合言葉を出したままでは閉じられない", c.eval("!!document.querySelector('.sheet') && !!document.querySelector('.fresh')"))
    click(c, '[data-act="tab"][data-v="now"]'); time.sleep(0.3)
    check("合言葉を出したままでは、よそへ移れない", c.eval("!!document.querySelector('.fresh')"))
    pw4, pw5 = rows[0][2], rows[1][2]
    s, d = slogin(ID_B, pw5.replace("-", "").upper())
    check("ブラウザで作った合言葉で、生徒の入口から入れる（線なし・大文字）", s == 200 and d["profile"]["role"] == "student", (s, d.get("error")))
    click(c, '[data-act="freshx"]'); time.sleep(0.4)
    check("閉じたら、画面のどこにも合言葉が残らない", c.eval("document.body.innerText.indexOf(%s) < 0 && JSON.stringify(window.TubeAdmin.state()).indexOf(%s) < 0" % (json.dumps(pw4), json.dumps(pw4))))
    click(c, '[data-act="tab"][data-v="seats"]'); time.sleep(0.3); click(c, '[data-act="cls"][data-v="e4a"]'); time.sleep(0.8)
    st5 = c.eval("(function(){ var r=Array.prototype.filter.call(document.querySelectorAll('.row'), function(x){ return x.innerText.indexOf('we4a23')>=0; })[0]; return r ? r.innerText : ''; })()")
    check("本人が入った席は「使っている」になり、最後に入った日が出る", "使っている" in st5 and "最後に入った日" in st5, st5)
    # 席は読むだけ（2026-10-08 本人）：「使う」「まとめて使う」「渡していないに戻す」「この席を消す」は管理ページに出さない
    ro = c.eval("""(function(){ return {
        use: document.querySelectorAll('.row [data-act="state"][data-v="live"]').length,
        upto: !!document.querySelector('#upto'), del_: document.querySelectorAll('[data-key^="del:"]').length,
        left: document.querySelectorAll('[data-key^="left:"], [data-act="more"]').length }; })()""")
    check("席は読むだけ：使う・まとめて使う・この席を消す の押し物が無い", ro["use"] == 0 and not ro["upto"] and ro["del_"] == 0, ro)
    click(c, '[data-act="more"][data-id="we4a20"]'); time.sleep(0.4)
    ro2 = c.eval("""(function(){ return { spare: document.querySelectorAll('[data-key="spare:we4a20"]').length,
        left: document.querySelectorAll('[data-key="left:we4a20"]').length, pw: document.querySelectorAll('[data-key="pw:we4a20"], [data-act="repw"][data-id="we4a20"]').length }; })()""")
    check("使っている席の「ほか」には、在籍終了と合言葉の作り直しだけがある", ro2["spare"] == 0 and ro2["left"] == 1 and ro2["pw"] >= 1, ro2)
    click(c, '[data-act="more"][data-id="we4a20"]'); time.sleep(0.3)
    click(c, '[data-act="more"][data-id="we4a22"]'); time.sleep(0.3)
    click(c, '[data-act="repw"][data-id="we4a22"]')
    check("合言葉を作り直すと、新しい合言葉が出る", c.wait_for("!!document.querySelector('.fresh td.pw')", 30))
    newpw = text(c, ".fresh td.pw")
    s, d = slogin(ID_A, pw4)
    check("前の合言葉では入れない", s == 401, s)
    s, d = slogin(ID_A, newpw)
    check("新しい合言葉で入れる", s == 200, s)
    click(c, '[data-act="freshx"]'); time.sleep(0.3)
    c.shot(os.path.join(OUT, "b3-class.png"))
    click(c, '[data-act="close"]'); time.sleep(0.3)

    # 講師と担当
    click(c, '[data-act="tab"][data-v="staff"]'); time.sleep(0.6)
    c.eval("(function(){ var s=document.querySelector('select[data-key=\"e4a:math\"]'); s.value='wt90'; s.dispatchEvent(new Event('change', {bubbles:true})); })()"); time.sleep(1.0)
    check("コースの行で講師を選ぶと、その場で付く", c.eval("!!document.querySelector('.chipx[data-key=\"e4a:math\"][data-id=\"wt90\"]')"))
    click(c, '[data-act="teacher"][data-v="wt90"]'); time.sleep(0.6)
    click(c, '.sheet [data-act="toggle"][data-key="e4b:japanese"]'); time.sleep(1.0)
    check("講師の紙でコースを押すと、その場で付く", c.eval("document.querySelector('.sheet [data-act=\"toggle\"][data-key=\"e4b:japanese\"]').getAttribute('aria-pressed') === 'true'"))
    c.shot(os.path.join(OUT, "b4-teacher.png"))
    click(c, '[data-act="close"]'); time.sleep(0.3)
    s, d = slogin("wt90", "kensa-sensei-kensa-sensei-0000")
    ttok = d.get("token")
    s, d = api("GET", "/api/me", ttok)
    keys = sorted(x["key"] for x in d["profile"]["assign"])
    check("その講師の画面に、付けた2コースが出る", keys == ["e4a:math", "e4b:japanese"], keys)
    s, d = api("PUT", "/api/lessons/use", ttok, {"keys": ["e4a:math"], "level": 2})
    check("講師が段階を「写真で提出」にできる", s == 200, (s, d))
    click(c, '[data-act="addteacher"]')
    check("講師を足すと、合言葉が出る（4語＋4桁）", c.wait_for("!!document.querySelector('.fresh td.pw')", 30) and bool(re.match(r"^([a-z]{3,8}-){4}\d{4}$", text(c, ".fresh td.pw") or "")))
    click(c, '[data-act="freshx"]'); time.sleep(0.3)
    click(c, '[data-act="csvopen"]'); time.sleep(0.8)
    check("コースの表が開く", c.eval("(document.querySelector('#csvText')||{value:''}).value.indexOf('e4a,算数') >= 0"))
    c.eval("document.querySelector('#csvText').value += 'x9,国語,こわれた行,e4,だれ,,,,,\\n'"); click(c, '[data-act="csvsave"]'); time.sleep(1.0)
    check("おかしな行があると入らず、理由が出る", c.eval("!!document.querySelector('.sheet .msg')"), text(c, ".sheet .msg"))
    click(c, '[data-act="close"]'); time.sleep(0.3)

    # 生徒に出ているもの
    click(c, '[data-act="tab"][data-v="out"]'); time.sleep(0.6)
    body = c.eval("document.querySelector('#main').innerText")
    check("出ているものに、段階と講師が出る", "写真で提出" in body and "wt90" in body and "紙のまま" in body)
    c.shot(os.path.join(OUT, "b5-out.png"))

    # 報告
    s, d = slogin(ID_B, pw5)
    stok = d.get("token")
    s, d = api("POST", "/api/report", stok, {"text": "しゃしんを えらんでも おくれません", "view": "宿題"})
    api("POST", "/api/report", ttok, {"kind": "error", "text": "TypeError: undefined is not an object (ui-desk.js:120)", "view": "check"})
    click(c, '[data-act="tab"][data-v="rep"]'); time.sleep(1.2)
    body = c.eval("document.querySelector('#main').innerText")
    check("報告が届く（だれかはクラスと番号まで）", "しゃしんを えらんでも" in body and "小4α-23" in body and "画面のエラー" in body, body[:200])
    c.shot(os.path.join(OUT, "b6-rep.png"))
    click(c, '[data-act="repdone"]'); time.sleep(1.2)
    check("済みにすると「まだ」から消える", c.eval("document.querySelectorAll('.rep').length") == 1)
    click(c, '[data-act="tab"][data-v="now"]'); time.sleep(0.8)
    c.shot(os.path.join(OUT, "b7-now.png"))
    check("いまの様子の「次にやること」が報告を指す", "報告" in (text(c, ".hero .t") or ""), text(c, ".hero .t"))
    # 死んだボタンと当たり判定
    dead = json.loads(c.eval("""JSON.stringify((function(){ var out=[]; ['now','seats','staff','out','rep'].forEach(function(t){ document.querySelector('[data-act="tab"][data-v="'+t+'"]').click();
      Array.prototype.forEach.call(document.querySelectorAll('button, select, a'), function(b){ var r=b.getBoundingClientRect(); if(!r.width) return;
        if(b.tagName==='BUTTON' && !b.getAttribute('data-act')) out.push(t+':no-act:'+b.innerText.slice(0,12));
        if(r.height < 43.5 && !b.closest('.seg')) out.push(t+':small:'+Math.round(r.height)+':'+b.innerText.slice(0,12)); }); }); return out; })())"""))
    check("押せないボタン・44px 未満のボタンが無い", not dead, dead[:6])
    check("横にはみ出していない", c.eval("document.documentElement.scrollWidth <= window.innerWidth + 1"))
    errs = json.loads(c.eval("JSON.stringify(window.__errs)"))
    check("JS のエラーが無い", not errs, errs[:3])
    click(c, '[data-act="out"]'); time.sleep(0.8)
    check("出ると入口に戻り、合言葉が消える", c.eval("!!document.querySelector('#gId') && !sessionStorage.getItem('tube.admin.token')"))
print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng else "通っていないものがある", ok, ng))
