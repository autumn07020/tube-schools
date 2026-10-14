# -*- coding: utf-8 -*-
"""管理ページの新しい所を Chrome で実際に押す：オンラインで渡す→生徒が引き換える／カード／クラス替え／クラスを足す／管理者／デモの入口。"""
import json, os, re, sys, time, urllib.error, urllib.request
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server")
from cdp import Chrome
import scram
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots2"; os.makedirs(OUT, exist_ok=True)
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
def adm_login(c):
    c.goto(BASE + "/admin", wait=1.0); watch(c)
    c.wait_for("!!document.querySelector('#gId')")
    c.eval("document.querySelector('#gId').value='wadmin99'; document.querySelector('#gPw').value='kensa-kanri-kensa-kanri-kensa-0000'; document.querySelector('#gGo').click();")
    assert c.wait_for("!!document.querySelector('.tabs')", 25), text(c, ".msg")

with Chrome(width=1440, height=900, scale=2, port=9811) as c, Chrome(width=430, height=900, scale=2, mobile=True, port=9812) as kid:
    # 講師に担当を付け、段階を 2 にしておく（API。画面の検査は adm_flow.py）
    st, d = scram.login(BASE, "wadmin99", "kensa-kanri-kensa-kanri-kensa-0000", admin=True); adm = d["token"]
    post = lambda m, p, tok, b=None: scram._post(BASE + p, b, {"Authorization": "Bearer " + tok}) if m == "POST" else None
    import urllib.request
    def api(method, path, tok, body=None):
        req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode())
        req.add_header("Content-Type", "application/json"); req.add_header("Authorization", "Bearer " + tok)
        try:
            r = urllib.request.urlopen(req, timeout=60); return r.status, json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode() or "{}")
    api("PUT", "/api/admin/courses/teacher", adm, {"key": "e4a:math", "id": "wt90", "on": True})
    st, d = scram.login(BASE, "wt90", "kensa-sensei-kensa-sensei-0000"); tt = d["token"]
    api("PUT", "/api/lessons/use", tt, {"keys": ["e4a:math"], "level": 2})

    adm_login(c)
    # --- オンラインで渡す ---
    click(c, '[data-act="tab"][data-v="seats"]'); time.sleep(0.5)
    click(c, '[data-act="cls"][data-v="e4b"]'); time.sleep(0.8)
    click(c, '[data-act="more"][data-id="we4b01"]'); time.sleep(0.3)
    click(c, '[data-act="online"][data-id="we4b01"]')
    check("「オンラインで渡す」で、リンクが1回だけ出る", c.wait_for("!!document.querySelector('.fresh td.lk')", 30))
    link = text(c, ".fresh td.lk")
    check("リンクは 入口＋#k=ID.言葉 の形", bool(re.match(r"^http://127\.0\.0\.1:8949/#k=we4b01\.([a-z]{3,8}-){3}\d{4}$", link or "")), link and link[:40])
    c.shot(os.path.join(OUT, "c1-link.png"))
    click(c, '[data-act="freshx"]'); time.sleep(0.6)
    row = c.eval("(function(){ var r=Array.prototype.filter.call(document.querySelectorAll('.row'), function(x){ return x.innerText.indexOf('we4b01')>=0; })[0]; return r ? r.innerText : ''; })()")
    check("席に「引き換え待ち」と期限が出る", "引き換え待ち" in row, row)
    # --- 生徒が、リンクを開く（別の端末のつもり） ---
    kid.goto(BASE + "/", wait=0.8); kid.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');")
    kid.goto(link, wait=1.0); watch(kid)
    check("リンクを開くと、番地から言葉が消える", kid.wait_for("location.hash === ''", 10), kid.eval("location.href"))
    check("開いただけでは引き換えない（「はじめる」を待つ）", kid.wait_for("!!document.querySelector('#clGo')", 30) and not kid.eval("!!document.querySelector('.np-pw')"), kid.eval("document.body.innerText.slice(0,200)"))
    st0, d0 = scram.login(BASE, "we4b01", link.split(".", 3)[-1] if False else link.split("#k=we4b01.")[1])
    check("押す前なら、リンクの言葉はまだ生きている（別の人が開いただけでは使い切らない）", st0 == 200 and d0.get("claim") is True, st0)
    kid.shot(os.path.join(OUT, "c2a-claim.png"))
    click(kid, "#clGo")
    check("押すと、この端末が作った合言葉が1回だけ出る", kid.wait_for("!!document.querySelector('.np-pw')", 40), kid.eval("document.body.innerText.slice(0,200)"))
    newpw = text(kid, ".np-pw")
    check("合言葉は 3語＋4桁（リンクの言葉とは別）", bool(re.match(r"^([a-z]{3,8}-){3}\d{4}$", newpw or "")) and newpw not in link, newpw and len(newpw))
    kid.shot(os.path.join(OUT, "c2-newpw.png"))
    click(kid, "#npGo"); time.sleep(0.4)
    check("「書きとめた」は2度押し（1度目は確かめの言葉に変わる）", "はい" in (text(kid, "#npGo") or "") and kid.eval("!!document.querySelector('.np-pw')"), text(kid, "#npGo"))
    click(kid, "#npGo"); pass_ask(kid)
    check("2度目で、そのままホームに入る", kid.wait_for("!document.querySelector('.np-card') && !document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)') && !document.querySelector('.dc-card')", 25))
    time.sleep(1.2); kid.shot(os.path.join(OUT, "c3-kid-home.png"))
    check("生徒の画面に JS のエラーが無い", not errs(kid), errs(kid)[:3])
    st, d = scram.login(BASE, "we4b01", newpw)
    check("端末が作った合言葉で、ほかの端末からも入れる", st == 200 and d["profile"]["role"] == "student", st)
    # 同じリンクを、もう一度開く
    kid.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');")
    kid.goto(BASE + "/", wait=0.5); kid.goto(link, wait=1.0)
    check("同じリンクは2度使えない（入口に理由が出て、ID は入っている）", kid.wait_for("!!document.querySelector('#lMsg.on')", 25) and kid.eval("document.querySelector('#lId').value") == "we4b01", text(kid, "#lMsg"))
    click(c, '[data-act="close"]'); time.sleep(0.2); click(c, '[data-act="cls"][data-v="e4b"]'); time.sleep(1.0)
    row = c.eval("(function(){ var r=Array.prototype.filter.call(document.querySelectorAll('.row'), function(x){ return x.innerText.indexOf('we4b01')>=0; })[0]; return r ? r.innerText : ''; })()")
    check("管理ページで「使っている」「引き換えた日」になる", "使っている" in row and "引き換えた日" in row and "引き換え待ち" not in row, row)
    click(c, '[data-act="close"]'); time.sleep(0.3)

    # --- カード ---
    click(c, '[data-act="cls"][data-v="e4a"]'); time.sleep(0.6)
    click(c, '[data-act="more"][data-id="we4a22"]'); time.sleep(0.3); click(c, '[data-act="repw"][data-id="we4a22"]')
    c.wait_for("!!document.querySelector('.fresh td.pw')", 40)
    rows = json.loads(c.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('.fresh tr'), function(tr){ return Array.prototype.map.call(tr.children, function(td){ return td.innerText; }); }))"))
    click(c, '[data-act="tocards"]'); time.sleep(0.8)
    check("「カードにする」で、カードのタブに並ぶ", c.eval("document.querySelectorAll('.cprev .pcard').length") == 1 and c.eval("document.querySelectorAll('#print .pcard').length") == 1)
    card = c.eval("document.querySelector('.cprev .pcard').innerText")
    check("カードに ID・あいことば・クラスと番号が出る", rows[0][1] in card and rows[0][2] in card and "小4α" in card, card)
    same = c.eval("(function(){ var t=document.createElement('div'); t.innerHTML = TubeQR.svg(%s, 110); return document.querySelector('.cprev .pcard svg path').getAttribute('d') === t.querySelector('path').getAttribute('d'); })()" % json.dumps(BASE + "/#k=" + rows[0][1] + "." + rows[0][2]))
    check("カードの QR は「入口＋#k=ID.合言葉」", same)
    c.shot(os.path.join(OUT, "c4-cards.png"))
    # QR と同じ番地を開く → そのまま入れる
    kid.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');"); kid.goto(BASE + "/", wait=0.5)
    kid.goto(BASE + "/#k=" + rows[0][1] + "." + rows[0][2], wait=1.0)
    check("カードの QR の番地を開くと、そのまま入れる（合言葉は番地から消える）", kid.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)') && location.hash === ''", 30), kid.eval("location.href + ' ' + ((document.querySelector('#lMsg')||{}).innerText||'')"))
    # 表から貼る
    click(c, '[data-act="cardclear"]'); time.sleep(0.3)
    paste = "番号\\tID\\t合言葉\\n01\\twe4a01\\tneko-yama-sora-4821\\n\\n講師,wt01,kotaeru-donguri-otedama-ayatori-0001\\nごみ\\tgomi\\n"
    c.eval("document.querySelector('#cardText').value = %s" % json.dumps(paste.replace("\\t", "\t").replace("\\n", "\n")))
    click(c, '[data-act="cardmake"]'); time.sleep(0.6)
    labs = json.loads(c.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('.cprev .pcard .pc-lab'), function(x){ return x.innerText; }))"))
    check("表から貼った行（タブ区切り・カンマ区切り）がカードになる", labs == ["小4α 01番", "講師"], labs)
    click(c, '[data-act="tab"][data-v="now"]'); time.sleep(0.5)
    check("カードのタブを離れると、貼った合言葉が画面に残らない", c.eval("document.body.innerText.indexOf('neko-yama-sora') < 0 && document.querySelector('#print').innerHTML === '' && !window.TubeAdmin.state().cards"))

    # --- クラス替え ---
    click(c, '[data-act="tab"][data-v="seats"]'); time.sleep(0.5)
    click(c, '[data-act="moveopen"][data-v="e4"]'); time.sleep(1.0)
    check("クラス替えの紙が開く（在籍の生徒だけ）", c.eval("!!document.querySelector('select[data-act=\"movepick\"][data-id=\"we4a20\"]') && !document.querySelector('select[data-id=\"we4a01\"]')"))
    c.eval("(function(){ var s=document.querySelector('select[data-act=\"movepick\"][data-id=\"we4a20\"]'); s.value='e4b'; s.dispatchEvent(new Event('change', {bubbles:true})); })()"); time.sleep(0.4)
    click(c, '[data-act="movecheck"]'); time.sleep(1.0)
    pv = c.eval("(document.querySelector('.sheet .rows')||{}).innerText || ''")
    check("確かめると、行き先と宿題の付け替えが出る（まだ移していない）", "小4α-20" in pv and "小4β-" in pv, pv)
    c.shot(os.path.join(OUT, "c5-move.png"))
    click(c, '[data-act="movego"]'); time.sleep(1.2)
    done = c.eval("(document.querySelector('.sheet .fresh')||{}).innerText || ''")
    check("移すと、結果の表が出る", "移しました" in done and "we4a20" in done, done[:80])
    st, d = scram.login(BASE, "we4a20", "kensa-seito-kensa-0000")
    check("移った生徒は、同じ ID と合言葉で入れる（クラスだけ変わる）", st == 200 and d["profile"]["classId"] == "e4b", (st, d.get("profile", {}).get("classId")))
    click(c, '[data-act="moveback"]'); time.sleep(0.8)
    click(c, '[data-act="arm"][data-key^="undo:"]'); time.sleep(0.3); click(c, '[data-act="moveundo"]'); time.sleep(1.2)
    st, d = scram.login(BASE, "we4a20", "kensa-seito-kensa-0000")
    check("取り消すと、前のクラスに戻る", st == 200 and d["profile"]["classId"] == "e4a" and d["profile"]["seat"] == "20", d.get("profile", {}).get("classId"))
    click(c, '[data-act="close"]'); time.sleep(0.3)

    # --- クラスを足す ---
    click(c, '[data-act="classopen"]'); time.sleep(0.5)
    c.eval("document.querySelector('#ncGrade').value='e5'; document.querySelector('#ncTail').value='s'; document.querySelector('#ncName').value='小5S';")
    click(c, '[data-act="classadd"]'); time.sleep(1.0)
    check("クラスを足すと、そのクラスの紙が開く（まだ生徒がいない）", "小5S" in (text(c, ".sheet .hd h2") or "") and "まだ生徒がいません" in (text(c, ".sheet") or ""), text(c, ".sheet .hd"))
    click(c, '[data-act="arm"][data-key="cdel:e5s"]'); time.sleep(0.3); click(c, '[data-act="classdel"]'); time.sleep(1.0)
    check("席の無いクラスは消せる", c.eval("document.body.innerText.indexOf('小5S') < 0"))

    # --- 指名のコースと、講師が受け持つ生徒 ---
    click(c, '[data-act="tab"][data-v="staff"]'); time.sleep(0.6)
    click(c, '[data-act="named"][data-key="e4o:math"]'); time.sleep(0.8)
    check("指名のコースの紙に、在籍の生徒だけが並ぶ", c.eval("!!document.querySelector('[data-act=\"namedtoggle\"][data-id=\"we4a20\"]') && !document.querySelector('[data-act=\"namedtoggle\"][data-id=\"we4a02\"]')"))
    click(c, '[data-act="namedtoggle"][data-id="we4a20"]'); time.sleep(1.0)
    check("押すと、その場で指名に入る", c.eval("document.querySelector('[data-act=\"namedtoggle\"][data-id=\"we4a20\"]').getAttribute('aria-pressed') === 'true'") and "指名 1人" in (text(c, ".sheet .hd") or ""), text(c, ".sheet .hd"))
    c.shot(os.path.join(OUT, "c9-named.png"))
    click(c, '[data-act="close"]'); time.sleep(0.3)
    api("PUT", "/api/admin/courses/teacher", adm, {"key": "e4o:math", "id": "wt90", "on": True})
    click(c, '[data-act="teacher"][data-v="wt90"]'); time.sleep(1.0)
    sheet = text(c, ".sheet") or ""
    check("講師の紙に、受け持つ生徒の ID がコースごとに出る", "受け持つ生徒" in sheet and "小4 オンライン 算数" in sheet and "we4a20" in sheet and "we4a21" in sheet, sheet[:200])
    c.shot(os.path.join(OUT, "c10-teacher.png"))
    click(c, '[data-act="close"]'); time.sleep(0.3)

    # --- 管理者 ---
    click(c, '[data-act="tab"][data-v="staff"]'); time.sleep(0.6)
    click(c, '[data-act="addadmin"]')
    check("管理者を足すと、合言葉が出る（5語＋4桁）", c.wait_for("!!document.querySelector('.fresh td.pw')", 30) and bool(re.match(r"^([a-z]{3,8}-){5}\d{4}$", text(c, ".fresh td.pw") or "")))
    click(c, '[data-act="freshx"]'); time.sleep(0.4)
    c.shot(os.path.join(OUT, "c6-staff.png"))
    # 押せないボタン・小さいボタン
    dead = json.loads(c.eval("""JSON.stringify((function(){ var out=[]; ['now','seats','staff','out','rep'].forEach(function(t){ document.querySelector('[data-act="tab"][data-v="'+t+'"]').click();
      window.scrollTo(0,0);
      Array.prototype.forEach.call(document.querySelectorAll('button, select, a'), function(b){ var r=b.getBoundingClientRect(); if(!r.width || getComputedStyle(b).visibility==='hidden') return;
        if(b.tagName==='BUTTON' && !b.getAttribute('data-act')) out.push(t+':no-act:'+b.innerText.slice(0,12));
        if(r.height < 43.5 && !b.closest('.seg')) out.push(t+':small:'+Math.round(r.height)+':'+b.innerText.slice(0,12));
        /* 覆われていないか：まん中の点にあるのが自分（か自分の中身）でなければ、浮いている札の下にある（10-08 右上の管理者の札が「講師を足す」を覆っていた） */
        b.scrollIntoView({block:'center'}); var r2=b.getBoundingClientRect(); var h=document.elementFromPoint(r2.left+r2.width/2, r2.top+r2.height/2);
        if(h && h!==b && !b.contains(h) && !h.contains(b)) out.push(t+':covered:'+b.innerText.slice(0,12)+' by '+(h.id||h.className||h.tagName).toString().slice(0,20)); }); }); return out; })())"""))
    check("押せないボタン・44px 未満のボタン・ほかの物に覆われたボタンが無い（5つのタブ。カードのタブは 2026-10-08 に外した）", not dead, dead[:6])
    check("管理ページに JS のエラーが無い", not errs(c), errs(c)[:3])

    # --- 毎日テストを使っていない生徒 ---
    kid.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');"); kid.goto(BASE + "/", wait=0.8); watch(kid)
    kid.wait_for("!!document.querySelector('#lId')")
    # 小3J の生徒（ためしのデモが段階 4 にするクラスの外。小4α は全教科 4 になったので、毎日テストが出る）
    kid.eval("document.querySelector('#lId').value='we3j21'; document.querySelector('#lPw').value='kensa seito kensa 0321'; document.querySelector('#lGo').click();")
    pass_ask(kid)
    kid.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)') && !!document.querySelector('[data-tab]')", 25); time.sleep(1.5)
    tabs = json.loads(kid.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('[data-tab]'), function(b){ return b.getAttribute('data-tab'); }))"))
    body = kid.eval("document.querySelector('#main').innerText")
    check("毎日テストを使っていない生徒には、毎日テストのタブも札も出ない", tabs == ["today", "homework", "record"] and "毎日テスト" not in body.replace("先生の 評価・テスト・毎日テストから", ""), (tabs, body[:160]))
    kid.shot(os.path.join(OUT, "c7-kid-nodaily.png"))
    check("その画面に JS のエラーが無い", not errs(kid), errs(kid)[:3])

    # --- デモの入口 ---
    kid.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');"); kid.goto(BASE + "/", wait=1.2)
    check("試し運用中は、ふつうの入口にも「ためしに見る」が出る", kid.wait_for("!!document.querySelector('#lId')") and kid.wait_for("!!document.querySelector('#demoOpen')", 10))
    demo = json.load(urllib.request.urlopen(BASE + "/api/demo", timeout=10)).get("accounts") or []
    check("入口の一覧（/api/demo）に合言葉が無い", bool(demo) and all("password" not in a for a in demo), [sorted(a.keys()) for a in demo[:2]])
    wt = next((a for a in demo if a.get("id") == "wt90"), None)
    check("本物の形の校舎の講師 wt90 が一覧にいて、担当（classes・courses）が付く", bool(wt) and "classes" in wt and "courses" in wt, wt)
    kid.goto(BASE + "/demo", wait=1.5)
    check("デモの入口（/demo）には出る", kid.wait_for("!!document.querySelector('#demoOpen')", 10))
    click(kid, "#demoOpen"); time.sleep(0.8)
    kid.shot(os.path.join(OUT, "c8-demo-sheet.png"))
    check("一覧の札に、講師 wt90 と ためし用の生徒 we4a20 が出る",
          kid.eval("!!document.querySelector('[data-demoid=\"wt90\"]') && !!document.querySelector('[data-demoid=\"we4a20\"]')"))
    click(kid, '[data-demoid="wt90"]')
    check("講師 wt90 に、ためしの入口から合言葉なしで入れる", kid.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)')", 30))
    time.sleep(1.0)
    who = kid.eval("localStorage.getItem('tube.school.v1.who')")
    check("入ったのは wt90（講師の画面）", who == "wt90" and kid.eval("!!document.querySelector('.dk-head, .dk-hero, .t-today, [data-tab]')"), (who, kid.eval("document.title")))
    kid.shot(os.path.join(OUT, "c8-demo-wt90.png"))
    check("その画面に JS のエラーが無い", not errs(kid), errs(kid)[:3])
    kid.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');"); kid.goto(BASE + "/demo", wait=1.5)
    kid.wait_for("!!document.querySelector('#demoOpen')", 10); click(kid, "#demoOpen"); time.sleep(0.8)
    click(kid, '[data-demoid="we4a20"]')
    check("ためし用の生徒 we4a20 にも、同じ入口から入れる", kid.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)') && !!document.querySelector('[data-tab]')", 30))
    check("入ったのは we4a20", kid.eval("localStorage.getItem('tube.school.v1.who')") == "we4a20")
    try:
        urllib.request.urlopen(urllib.request.Request(BASE + "/api/demo/enter", data=json.dumps({"id": "wadmin99"}).encode(),
                                                      headers={"Content-Type": "application/json"}), timeout=10)
        code = 200
    except urllib.error.HTTPError as e:
        code = e.code
    check("一覧に無い口座（管理者 wadmin99）は、ID を送っても入れない（404）", code == 404, code)
print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng else "通っていないものがある", ok, ng))
