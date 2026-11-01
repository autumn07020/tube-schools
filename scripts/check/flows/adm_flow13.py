# -*- coding: utf-8 -*-
"""⑦ ためし運用のデモ（demo_trial.py）を、本物の形の校舎で画面から確かめる（2026-10-10 本人「少なくとも私の生徒に対しては
全てデモ版でも成績や宿題など、全てのデモを作成せよ。各講師もそれぞれ一科目だけずつ、サンプルを作り、宿題チェックとフィードバックが
それぞれできるように」）。

  講師 wt01（本人・PC）   … 入口の「ためしに見る」から入る → 今日やることに未評価がある → 宿題チェック（小4β 国語 漢字テスト 第3回）で
                            4 と ひとこと → サーバの記録に残る
  生徒（小4β の ためしの生徒。iPhone） … 先生から に、その ひとことが新着で出る（フィードバックが届く）
  生徒（中3R の ためしの生徒。iPhone）  … 宿題が並ぶ・成績に数字がある・記録の暦に日がある（本人の生徒の「全部のデモ」）
  講師 wt02（PC）         … 見本 1 教科（小5β 国語）の提出箱が今日やることに出る → 採点できる
  講師 wt05（API）        … 見本（小4 理科）の提出箱に未評価 2 人
  本物の席               … 役割も記録も変わっていない
"""
import json, os, re, sys, time, urllib.parse, urllib.request, urllib.error
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server")
from cdp import Chrome
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots13"; os.makedirs(OUT, exist_ok=True)
ok = ng = 0
def check(name, cond, detail=""):
    global ok, ng
    if cond: ok += 1; print("  OK   " + name)
    else: ng += 1; print("  ×    %s  %s" % (name, detail))
def click(c, sel): return c.eval("(function(){var b=document.querySelector(%s); if(b){b.click(); return true;} return false;})()" % json.dumps(sel))
def errs(c): return json.loads(c.eval("JSON.stringify(window.__errs||[])"))
def watch(c): c.eval("window.__errs=[]; window.addEventListener('error', function(e){ window.__errs.push(String(e.message)); });")
def api(method, path, tok, body=None):
    req = urllib.request.Request(BASE + "/api" + path, method=method, data=(json.dumps(body).encode() if body is not None else None))
    req.add_header("Authorization", "Bearer " + tok); req.add_header("Content-Type", "application/json")
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
    except urllib.error.HTTPError as e:
        return {"error": "HTTP %d %s" % (e.code, e.read().decode()[:200])}
def enter_api(lid):
    req = urllib.request.Request(BASE + "/api/demo/enter", data=json.dumps({"id": lid}).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode()).get("token")

def _school_files():
    acc = json.load(open(S + "/real/schools/waseaca-london/accounts.json"))
    meta = json.load(open(S + "/real/schools/waseaca-london/school.json"))
    return acc, meta
def pick_lid(cls):
    """入口に出ている ためしの生徒のうち、そのクラスの 1 人（demo_trial.py の trialPick）。"""
    acc, meta = _school_files()
    return next((lid for lid in (meta.get("trialPick") or []) if (acc.get(lid) or {}).get("classId") == cls), None)
def demo_lids(cls):
    """そのクラスの ためしの生徒（demo の印）。先頭が見本。"""
    acc, _ = _school_files()
    return sorted(lid for lid, a in acc.items() if a.get("classId") == cls and a.get("role") == "student" and a.get("demo"))
def set_pw(lid, pw):
    """検査のあいだだけ、その口座の合言葉を付け替える（入口の一覧に無い ためしの生徒で入るため）。"""
    import subprocess
    env = dict(os.environ, MYACADY_ROOT=S + "/real", MYACADY_FSYNC="0")
    r = subprocess.run([sys.executable, S + "/tube/server/tube_server.py", "passwd", lid, pw, "--school", "waseaca-london"], env=env, capture_output=True, text=True)
    return r.returncode == 0
def enter_ui(c, lid):
    """入口の「ためしに見る」から、ID だけで入る。"""
    c.goto(BASE + "/demo", wait=0.8); c.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');")
    c.goto("about:blank", wait=0.2); c.goto(BASE + "/demo", wait=1.0); watch(c)
    assert c.wait_for("!!document.querySelector('#demoOpen')", 20), "demoOpen " + lid
    click(c, "#demoOpen"); time.sleep(0.8)
    assert click(c, '[data-demoid=%s]' % json.dumps(lid)), "no card " + lid
    assert c.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)')", 40), "enter " + lid
    time.sleep(1.5)
    return c.eval("localStorage.getItem('tube.school.v1.token')")
def login_ui(c, lid, pw):
    c.goto(BASE + "/", wait=0.6); c.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');")
    c.goto("about:blank", wait=0.2); c.goto(BASE + "/", wait=0.8); watch(c)
    c.wait_for("!!document.querySelector('#lId')", 20)
    c.eval("document.querySelector('#lId').value=%s; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();" % (json.dumps(lid), json.dumps(pw)))
    assert c.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)')", 40), "login " + lid
    time.sleep(1.5)
    return c.eval("localStorage.getItem('tube.school.v1.token')")
def tab(c, t):
    c.eval("TubeUI.go(%s)" % json.dumps(t)); time.sleep(1.5)
sys.path.insert(0, S + "/tube/scripts/check")
import expect
# ためし用の生徒の合言葉は、作ったときの画面（reset.sh が trial.log に残す）から
PW = {}
for line in open(S + "/trial.log", encoding="utf-8"):
    m = re.match(r"\s+(wd\w+)\s+\S+\s+(\S+)\s*$", line)
    if m: PW[m.group(1)] = m.group(2)

with Chrome(width=1280, height=900, scale=2, port=9323) as t, Chrome(width=430, height=900, scale=2, mobile=True, port=9324) as s:
    # ---- 講師 wt01：今日やること → 宿題チェック → 採点 ----
    ttok = enter_ui(t, "wt01")
    check("講師 wt01 に、ためしの入口から入れる", bool(ttok))
    today = api("GET", "/today", ttok) or {}
    tasks = today.get("tasks") or []
    todo = [x for x in tasks if (x.get("todo") or 0) >= 1]
    check("今日やることに、未評価のある回が 1 つ以上（今日つけた評価もある）", bool(todo) and (today.get("ratedToday") or 0) >= 1,
          (len(tasks), today.get("ratedToday")))
    t.shot(os.path.join(OUT, "a1-wt01-today.png"))
    check("今日やることの画面に JS のエラーが無い", not errs(t), errs(t)[:3])
    # 今日やることの札の密度（10-11 本人：4段は多い。横長は 7 件以上で半分の札・3 段以内）。PC 1280px・wt01 は 6〜8 件（作るたびに変わる）
    MEAS = """JSON.stringify((function(){ var cs=[].slice.call(document.querySelectorAll('.t-cards > .t-check')); var tops={};
      cs.forEach(function(c){ tops[Math.round(c.getBoundingClientRect().top)]=1; });
      var h=document.querySelector('.t-hero').getBoundingClientRect(), k=document.querySelector('.t-cards').getBoundingClientRect();
      var top0=cs.length?Math.round(cs[0].getBoundingClientRect().top):0, cols=cs.filter(function(c){ return Math.round(c.getBoundingClientRect().top)===top0; }).length;
      var last=cs.length?cs[cs.length-1].getBoundingClientRect():k;
      return {n:cs.length, rows:Object.keys(tops).length, cols:cols, cardH:cs.length?Math.round(cs[0].getBoundingClientRect().height):0,
              heroH:Math.round(h.height), cardsH:Math.round(k.height), sameRow:Math.abs(h.top-k.top)<2, fills:Math.abs(last.right-k.right)<2}; })())"""
    # ためしのデモは作るたびに中身が変わる（sid と宿題の ID は secrets で作る。#13：GitHub で 6 件、手元で 8 件）。
    # 決まりは「7 件以上」の形なので、7 件に届かないときは adm_flow14 と同じやり方で札を複製して 7 枚にしてから測る。
    PAD = """(function(n){ var k=document.querySelector('.t-cards'); var cs=[].slice.call(k.querySelectorAll('.t-check')); var had=cs.length;
      while(cs.length && k.querySelectorAll('.t-check').length < n){ var x=cs[k.querySelectorAll('.t-check').length % cs.length].cloneNode(true); x.setAttribute('data-pad','1'); k.appendChild(x); }
      k.setAttribute('data-cls', k.className); if(had < n) k.className = 't-cards' + (n>3?' n3':'') + (n>6?' n6':'') + (n>9?' n9':''); return had; })(7)"""
    def meas(c):
        had = c.eval(PAD); time.sleep(0.3)
        d = json.loads(c.eval(MEAS)); d["data"] = had; return d
    dm = meas(t)
    # 7〜9 枚は 3 列（輪の札と同じ行・同じ高さ）、10 枚以上は 4 列（輪の札は上に横長）。どちらも 3 段以内・札は 150px 以下
    cols_ok = (dm["cols"] == 4 and not dm["sameRow"]) if dm["n"] >= 10 else (dm["cols"] == 3 and dm["sameRow"] and abs(dm["heroH"] - dm["cardsH"]) <= 2)
    check("PC の細い窓（1280px）：7 件以上の今日やることは半分の札で 3 段以内（7〜9 枚は 3 列で輪の札と同じ行、10 枚以上は 4 列で輪の札は上）",
          dm["n"] >= 7 and dm["rows"] <= 3 and cols_ok and dm["cardH"] <= 150, dm)
    check("PC の細い窓：余った札は横に広がって最後の段を埋める（右端が塊の右端）", dm["n"] % dm["cols"] == 0 or dm["fills"], dm)
    if dm["data"] < 7:
        t.eval("(function(){ var k=document.querySelector('.t-cards'); [].slice.call(k.querySelectorAll('[data-pad]')).forEach(function(x){ k.removeChild(x); }); k.className=k.getAttribute('data-cls'); })()")   # 複製した札を外して、データのとおりに戻す
    with Chrome(width=1600, height=900, scale=1, port=9325) as wide:
        enter_ui(wide, "wt01"); wide.eval("TubeUI.go('hw')"); time.sleep(2.0)
        wide.eval("document.querySelector('.t-cards').scrollIntoView({block:'start'})"); time.sleep(0.3)
        dw = meas(wide)
    check("広い PC（1600px）：7 件以上は 4 列、3 段以内、余った札は段を埋める", dw["n"] >= 7 and dw["cols"] == 4 and dw["rows"] <= 3 and dw["cardH"] <= 150 and (dw["n"] % 4 == 0 or dw["fills"]), dw)
    # 時間割：同じ段（その日の何コマ目か）の札は、どの曜日でも上端と高さが同じ（10-11 本人「ガタガタ」）
    rows_ = json.loads(t.eval("""JSON.stringify((function(){ var by={}; document.querySelectorAll('.tt-week .slot').forEach(function(s){ var r=s.style.getPropertyValue('--r'); var b=s.getBoundingClientRect();
      (by[r]=by[r]||[]).push([Math.round(b.top), Math.round(b.height)]); }); return by; })())"""))
    uneven = {r: v for r, v in rows_.items() if len({x[0] for x in v}) > 1 or len({x[1] for x in v}) > 1}
    check("時間割の同じ段の札は、曜日をまたいで上端と高さがそろう（%d 段）" % len(rows_), bool(rows_) and not uneven, uneven)
    kanji = [x for x in tasks if x.get("key") == "e4b:japanese" and x.get("label") == "提出箱" and "漢字テスト 第3回" in (x.get("topic") or "")]
    check("小4β 国語の提出箱「漢字テスト 第3回」が今日やることに出て、未評価が残っている", bool(kanji) and kanji[0].get("todo") >= 1, kanji[:1])
    n = kanji[0]["n"] if kanji else 901
    t.eval("TubeDesk.openCheck(%s, %d)" % (json.dumps("e4b:japanese"), n)); time.sleep(1.5)
    cell = t.wait_for("!!document.querySelector('.dk-cell.s-todo')", 15)
    check("宿題チェックに、未評価の生徒の札がある", cell)
    t.eval("document.querySelector('.dk-cell.s-todo').click()"); time.sleep(1.0)
    sid = t.eval("document.querySelector('.dk-cell.focus') && document.querySelector('.dk-cell.focus').getAttribute('data-dksid')")
    check("札を押すと写真が大きく出る", t.wait_for("!!document.querySelector('.dk-view img') || !!document.querySelector('.dk-vimg')", 10))
    t.shot(os.path.join(OUT, "a2-wt01-check.png"))
    # 1画面に収まる（10-11 本人：下にスクロールや拡大をしなくても採点できること。写真は大きく、評価・ひとこと・添削・PDF が見えている）
    fit = json.loads(t.eval("""JSON.stringify((function(){ var img=document.querySelector('.dk-vimg img'); var r=img?img.getBoundingClientRect():null;
      var vis=function(s){ var e=document.querySelector(s); if(!e) return false; var b=e.getBoundingClientRect(); return b.top>=0 && b.bottom<=innerHeight; };
      return {doc:document.documentElement.scrollHeight, win:innerHeight, imgH:r?Math.round(r.height):0,
              rate:vis('[data-dkrate="4"]'), note:vis('#dkNote'), pdf:vis('.dk-fix-acts a[href*="pdf"], .dk-fix-acts .dk-mini'), scan:vis('[data-dkscan]')}; })())"""))
    check("宿題チェックは 1 画面に収まる（ページが縦にスクロールしない）", fit["doc"] <= fit["win"], fit)
    check("写真は画面の高さの 4 割以上。評価・ひとこと・添削（PDF・取り込み）がスクロールせずに見えている",
          fit["imgH"] >= fit["win"] * 0.4 and fit["rate"] and fit["note"] and fit["pdf"] and fit["scan"], fit)
    t.wait_for("!!document.querySelector('[data-dkrate=\"4\"]')", 10)
    for _ in range(3):
        click(t, '[data-dkrate="4"]')
        if t.wait_for("!!document.querySelector('.dk-rb.v4.on')", 4): break
        time.sleep(1.0)
    note = "とめ・はねが丁寧です。次は「候」の点も忘れずに。"
    t.eval("var n=document.querySelector('#dkNote'); n.focus(); n.value=%s; n.dispatchEvent(new Event('input')); n.dispatchEvent(new Event('change')); n.blur();" % json.dumps(note))
    row = None
    for _ in range(8):
        time.sleep(1.0)
        ck = api("GET", "/check?key=%s&n=%d" % (urllib.parse.quote("e4b:japanese"), n), ttok) or {}
        row = next((r for r in (ck.get("rows") or []) if r.get("sid") == sid), None)
        if row and row.get("v") == 4 and row.get("note") == note: break
    check("サーバの記録：評価 4 と ひとことが付く", bool(row) and row.get("v") == 4 and row.get("note") == note, str(row)[:200])
    t.shot(os.path.join(OUT, "a3-wt01-rated.png"))
    # 成績（本人の担当コース全部に数字がある）
    ins = api("GET", "/insight/overview", ttok) or {}
    check("講師の成績の一覧（insight/overview）が答える", "error" not in ins and bool(ins), str(ins)[:120])
    # 回の札を種類でしぼる（小4β 国語には 提出箱 と 第N回 の両方がある）
    t.eval("TubeDesk.openCheck(%s, %d)" % (json.dumps("e4b:japanese"), n)); time.sleep(1.5)
    kch = json.loads(t.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('.dk-kinds .dk-kind'), function(b){ return b.innerText; }))")) if t.wait_for("document.querySelectorAll('.dk-kinds .dk-kind').length >= 3", 8) else []
    check("回の札に「種類でしぼる」が、すべて／提出箱／宿題 の 3 つで出る（教材の呼び名「第6回」は種類にしない）", kch == ["すべて", "提出箱", "宿題"], kch)
    click(t, '.dk-kind[data-dkkind="提出箱"]'); time.sleep(1.2)
    labs = json.loads(t.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('.dk-segb b'), function(b){ return b.innerText; }))"))
    check("「提出箱」でしぼると、回の札は提出箱だけ（普段の宿題の回は消える）", bool(labs) and all(x.startswith("提出箱") for x in labs), labs)
    click(t, '.dk-kind[data-dkkind=""]'); time.sleep(0.8)
    t.shot(os.path.join(OUT, "a5-wt01-kinds.png"))

    # ---- 提出箱を「種類」と「選んだ生徒だけ」で出す（10-11 本人：追加の宿題・漢字テスト・計算テスト・作文・過去問を別々に） ----
    t.goto(BASE + "/", wait=1.5); watch(t); tab(t, "hw"); time.sleep(1.5)
    check("講師の時間割に 中3R 数学 のコマがある", t.wait_for("!!document.querySelector('.slot[data-slot$=\"|j3r:math\"]')", 15))
    click(t, '.slot[data-slot$="|j3r:math"]'); time.sleep(1.5)
    check("授業の紙の提出箱に、種類と「選んだ生徒だけ」がある",
          t.wait_for("!!document.querySelector('#qzKind') && !!document.querySelector('[name=\"qzWho\"][value=\"pick\"]')", 10))
    t.eval("document.querySelector('#qzKind').value='計算テスト'; document.querySelector('#qzKind').dispatchEvent(new Event('change')); "
           "document.querySelector('#qzTitle').value='第1回'; document.querySelector('#qzTitle').dispatchEvent(new Event('input'));")
    t.eval("var r=document.querySelector('[name=\"qzWho\"][value=\"pick\"]'); r.checked=true; r.dispatchEvent(new Event('change'));")
    check("「選んだ生徒だけ」にすると、このコースの生徒が札に並ぶ", t.wait_for("document.querySelectorAll('#qzPick input[type=checkbox]').length >= 2", 15),
          t.eval("document.querySelectorAll('#qzPick input').length"))
    acc_ = json.load(open(S + "/real/schools/waseaca-london/accounts.json")); l91, l92 = demo_lids("j3r")[0], demo_lids("j3r")[1]; s91 = acc_[l91]["sid"]; s92 = acc_[l92]["sid"]
    PW[l92] = "kensa-seito-kensa-9292"; check("検査のあいだ、2 人目の ためしの生徒（%s）の合言葉を付け替えられる" % l92, set_pw(l92, PW[l92]))
    t.eval("var c=document.querySelector('#qzPick input[value=%s]'); if(c) c.checked = true;" % json.dumps(s91))
    click(t, '[data-quiz="j3r:math"]'); time.sleep(3.0)
    a91 = (api("GET", "/assignments", enter_api(l91)) or {}).get("assignments") or []
    a92 = (api("GET", "/assignments", expect.Api(BASE).login(l92, PW.get(l92, ""))) or {}).get("assignments") or []   # 入口の一覧に無い生徒は合言葉で
    has91 = [a for a in a91 if a.get("title") == "計算テスト 第1回"]; has92 = [a for a in a92 if a.get("title") == "計算テスト 第1回"]
    check("「計算テスト 第1回」は選んだ %s にだけ届く（%s には届かない）" % (l91, l92), len(has91) == 1 and not has92, (len(has91), len(has92)))
    srv = json.load(open(S + "/real/schools/waseaca-london/assignments.json"))
    mine_q = [x for x in srv.values() if x.get("title") == "計算テスト 第1回" and (x.get("lesson") or {}).get("key") == "j3r:math" and x.get("picked")]
    check("サーバの記録：種類は計算テスト、選んだ生徒だけの印、受け取り手は 1 人",
          len(mine_q) == 1 and mine_q[0].get("kind") == "計算テスト" and mine_q[0].get("picked") is True and mine_q[0].get("students") == [s91], mine_q[:1])
    t.shot(os.path.join(OUT, "a6-wt01-quiz-picked.png"))

    tab(t, "roster"); time.sleep(2.5)
    t.shot(os.path.join(OUT, "a4-wt01-roster.png"))
    ros = t.eval("document.querySelector('#main').innerText")
    check("講師の成績の画面が開き、担当コース（小4α 算数・中3R 数学・キャッチアップ）が並び、テコ入れ候補が出る。JS のエラーが無い",
          all(w in ros for w in ("小4α 算数", "中3R 数学", "キャッチアップ", "テコ入れ候補")) and not errs(t), (ros[:160], errs(t)[:3]))

    # ---- 生徒 wde4b92：先生から に新着 ----
    who = next((lid for lid, a in json.load(open(S + "/real/schools/waseaca-london/accounts.json")).items() if a.get("sid") == sid), None)
    acc_w = json.load(open(S + "/real/schools/waseaca-london/accounts.json"))
    check("採点した札は、ためしの生徒（demo の印）のもの", bool(who) and bool((acc_w.get(who) or {}).get("demo")), who)
    if who and who not in PW:
        PW[who] = "kensa-seito-kensa-9393"
        if not set_pw(who, PW[who]): PW.pop(who, None)
    if who and who in PW:
        login_ui(s, who, PW[who]); tab(s, "record"); time.sleep(1.5)
        card = s.wait_for("Array.prototype.some.call(document.querySelectorAll('.ch-in'), function(e){ return e.innerText.indexOf(%s) >= 0; })" % json.dumps(note[:8]), 15)
        check("生徒 %s の「先生から」に、ひとこと付きの新着が出る" % who, card)
        s.shot(os.path.join(OUT, "b1-student-inbox.png"))
        check("生徒の画面に JS のエラーが無い", not errs(s), errs(s)[:3])
    else:
        check("ためしの生徒の合言葉を付け替えられる", False, (who, sorted(PW)[:3]))

    # 小4 の生徒には 過去問 のタブが無い。宿題のタブは「提出」
    tabs4 = json.loads(s.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('#foot [data-tab]'), function(b){ return b.getAttribute('data-tab') + ':' + b.innerText.trim(); }))"))
    check("小4 の生徒のタブは ホーム・提出（かなで「ていしゅつ」）・毎日テスト・先生から（過去問は無い）",
          any(x.startswith("homework:ていしゅつ") or x.startswith("homework:提出") for x in tabs4) and not any(x.startswith("kakomon") for x in tabs4), tabs4)

    # ---- 生徒 wdj3r91（入口から）：宿題・成績・記録 ----
    stok = enter_ui(s, pick_lid("j3r"))
    asg = api("GET", "/assignments", stok) or {}
    rows = asg.get("assignments") or []
    check("中3R のためし用の生徒に宿題が届いている（数学の宿題が 3 件以上）", len([a for a in rows if a.get("subject") == "math"]) >= 3, len(rows))
    tab(s, "homework"); time.sleep(1.0)
    s.shot(os.path.join(OUT, "c1-j3r-homework.png"))
    body = s.eval("document.querySelector('#main').innerText")
    check("提出タブに、宿題の札が出る（レギュラー／アドバンス）", "レギュラー" in body or "アドバンス" in body, body[:160])
    tests_txt = s.eval("(document.querySelector('.hw-tests')||{innerText:''}).innerText")
    check("提出タブの上に「テストの提出」があり、wt01 が 1 人に出した 計算テスト 第1回 がそこに出る（宿題の一覧とは別）",
          "テストの提出" in body and "計算テスト" in tests_txt and "第1回" in tests_txt, tests_txt[:160])
    # 過去問のタブ（中3）
    tabs3 = json.loads(s.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('#foot [data-tab]'), function(b){ return b.getAttribute('data-tab'); }))"))
    check("中3 の生徒には 過去問 のタブがある", "kakomon" in tabs3, tabs3)
    tab(s, "kakomon"); s.wait_for("document.querySelectorAll('.kk-list').length >= 2", 10); time.sleep(0.8)
    kk = s.eval("document.querySelector('#main').innerText")
    check("過去問のタブは学校ごとの一覧（都立共通・早稲田実業）で、出した 2 本（点数の欄）と これから 2 本（出す口）が年度で並ぶ",
          "学校ごと" in kk and "都立共通" in kk and "早稲田実業" in kk and s.eval("document.querySelectorAll('.kk-school').length") >= 2
          and s.eval("document.querySelectorAll('.kk-row.done [data-kkscore]').length") >= 2 and s.eval("document.querySelectorAll('.kk-row.todo [data-up]').length") >= 2, kk[:200])
    check("出した過去問に、評価の札と「添削を見る」がある", s.eval("!!document.querySelector('.kk-row.done .rt') && !!document.querySelector('.kk-row.done [data-ret]')"), kk[:200])
    # 点数を書くと その場で保存され、開き直しても残る（生徒の自己申告。PUT /submissions/<id>/score）
    s.eval("(function(){ var i=document.querySelector('.kk-row.done [data-kkscore]'); i.value='72'; i.dispatchEvent(new Event('change')); })()"); time.sleep(1.2)
    s.eval("(function(){ var i=document.querySelector('.kk-row.done [data-kkmax]'); i.value='100'; i.dispatchEvent(new Event('change')); })()"); time.sleep(1.2)
    tab(s, "today"); time.sleep(0.6); tab(s, "kakomon"); s.wait_for("document.querySelectorAll('.kk-school').length >= 2", 10); time.sleep(0.8)
    check("過去問の点数 72/100 が保存され、開き直しても残る",
          s.eval("document.querySelector('.kk-row.done [data-kkscore]').value") == "72" and s.eval("document.querySelector('.kk-row.done [data-kkmax]').value") == "100")
    s.shot(os.path.join(OUT, "c4-j3r-kakomon.png"))
    check("過去問の画面に JS のエラーが無い", not errs(s), errs(s)[:3])
    tab(s, "daily"); time.sleep(1.5)
    dtxt = s.eval("document.querySelector('#main').innerText")
    subs_on = [w for w in ("国語", "数学", "英語", "理科", "社会") if w in dtxt]
    check("中3R のためし用の生徒の毎日テストに、受講している教科が全部出る（10-11 本人：数学しか無かった）", len(subs_on) >= 4, subs_on)
    s.shot(os.path.join(OUT, "c3-j3r-daily.png"))
    tab(s, "record"); time.sleep(1.5)
    s.shot(os.path.join(OUT, "c2-j3r-record.png"))
    rec = s.eval("document.querySelector('#main').innerText")
    rings = s.eval("document.querySelectorAll('.h-ringv').length")
    check("先生から に、返ってきたもの（評価つき）と達成の輪（終わった宿題・続けた日）が出る",
          rings >= 2 and "返ってきたもの" in rec and "終わった宿題" in rec, (rings, rec[:120]))
    check("記録に「日」（連続・暦）がある", "続けた日" in rec or "日" in rec, rec[:80])
    check("生徒の画面に JS のエラーが無い（宿題・成績）", not errs(s), errs(s)[:3])

    # ---- 講師 wt02：見本 1 教科の提出箱 ----
    ttok2 = enter_ui(t, "wt02")
    today2 = api("GET", "/today", ttok2) or {}
    # 見本の提出箱は、その講師の「ためしの生徒がいる最初のコース」（demo_trial.py）。サーバの記録から引く
    titles = ("漢字テスト 第1回", "計算テスト 第1回", "英単語テスト 第1回", "一問一答 第1回", "小テスト 第1回")   # demo_trial.QUIZ_TITLE
    box = [x for x in (today2.get("tasks") or []) if x.get("label") == "提出箱" and (x.get("topic") or "") in titles and (x.get("todo") or 0) >= 1]
    check("講師 wt02 の今日やることに、見本の提出箱（きのう期限・未評価が 2 人以上）が出る", bool(box) and (box[0].get("todo") or 0) >= 2, [(x.get("key"), x.get("topic"), x.get("todo")) for x in today2.get("tasks") or []])
    t.shot(os.path.join(OUT, "d1-wt02-today.png"))
    if box:
        t.eval("TubeDesk.openCheck(%s, %d)" % (json.dumps("e5b:japanese"), box[0]["n"])); time.sleep(1.5)
        check("wt02 の宿題チェックに未評価の札が 2 つ", t.wait_for("document.querySelectorAll('.dk-cell.s-todo').length >= 2", 15))
        t.eval("document.querySelector('.dk-cell.s-todo').click()"); time.sleep(1.0)
        for _ in range(3):
            click(t, '[data-dkrate="5"]')
            if t.wait_for("!!document.querySelector('.dk-rb.v5.on')", 4): break
            time.sleep(1.0)
        time.sleep(1.2)
        ck2 = api("GET", "/check?key=%s&n=%d" % (urllib.parse.quote("e5b:japanese"), box[0]["n"]), ttok2) or {}
        check("wt02 が採点でき、サーバに 5 が残る", any(r.get("v") == 5 for r in (ck2.get("rows") or [])), str(ck2.get("rows"))[:200])
        t.shot(os.path.join(OUT, "d2-wt02-check.png"))

    # ---- 講師 wt05（API）：見本 小4 理科 ----
    sys.path.insert(0, S + "/tube/scripts/check")
    import expect
    ttok5 = expect.Api(BASE).login("wt05", "kensa-sensei-kensa-sensei-0000")
    today5 = api("GET", "/today", ttok5) or {}
    box5 = [x for x in (today5.get("tasks") or []) if x.get("key") == "e4:science" and x.get("label") == "提出箱"]
    check("講師 wt05 の今日やることに、小4 理科の提出箱（未評価 2 人以上）", bool(box5) and (box5[0].get("todo") or 0) >= 2, [(x.get("key"), x.get("todo")) for x in today5.get("tasks") or []])

    # ---- 新しい本物の口座（中3R）に、その日のうちに今の宿題が見える（10-10 本人：新規の口座に宿題が出なかった） ----
    import subprocess
    # 出席番号 77（51〜60 は reset.sh がためしのデモ用に足した席）
    subprocess.run([sys.executable, S + "/tube/server/tube_server.py", "add", "wsj3r77", "77", "--class", "j3r", "--level", "j3",
                    "--password", "kensa-seito-kensa-0077", "--school", "waseaca-london"],
                   env=dict(os.environ, MYACADY_ROOT=S + "/real", MYACADY_FSYNC="0"), capture_output=True)
    ntok = expect.Api(BASE).login("wsj3r77", "kensa-seito-kensa-0077")
    check("新しい口座（wsj3r77）を作って入れる", bool(ntok))
    if not ntok: ntok = ""

    nrows = (api("GET", "/assignments", ntok) or {}).get("assignments") or []
    now_ms = time.time() * 1000
    mine_open = [a for a in nrows if a.get("subject") == "math" and int(a.get("dueAt") or 0) >= now_ms]
    check("新しく作った中3R の口座に、今週の数学の宿題（期限前）が届いている。過ぎた回の「未提出」は付かない",
          bool(mine_open) and not any(int(a.get("dueAt") or 0) < now_ms for a in nrows), (len(nrows), len(mine_open)))
    login_ui(s, "wsj3r77", "kensa-seito-kensa-0077"); time.sleep(1.0)
    home = s.eval("document.querySelector('#main').innerText")
    check("その口座のホームの大きな札が宿題（提出する）で、「宿題はありません」と出ない",
          "宿題はありません" not in home and "提出する" in home, home[:160])
    s.shot(os.path.join(OUT, "e1-new-account-home.png"))

    # ---- 電話（430px）の今日やること：4 件以上は 2 列の小さな札、輪の札は上 ----
    enter_ui(s, "wt01"); s.eval("TubeUI.go('hw')"); time.sleep(2.0)
    s.eval("document.querySelector('.t-cards').scrollIntoView({block:'start'})"); time.sleep(0.3)
    dp = json.loads(s.eval(MEAS))
    check("電話：4 件以上の今日やることは 2 列の小さな札（1 枚 130px 以下）。輪の札は上に", dp["n"] >= 4 and dp["cols"] == 2 and dp["cardH"] <= 130 and not dp["sameRow"], dp)
    check("電話：余った札は横に広がって最後の段を埋める", dp["n"] % 2 == 0 or dp["fills"], dp)
    s.shot(os.path.join(OUT, "f1-phone-today-dense.png"))

    # ---- 本物の席は触られていない ----
    acc = json.load(open(S + "/real/schools/waseaca-london/accounts.json"))
    seats = [lid for lid, a in acc.items() if a.get("role") == "seat"]
    demo = [lid for lid, a in acc.items() if a.get("demo")]
    asg_all = json.load(open(S + "/real/schools/waseaca-london/assignments.json"))
    dsids = {acc[l]["sid"] for l in demo}
    leak = [aid for aid, x in asg_all.items() if x.get("demo") and int(x.get("dueAt") or 0) < time.time() * 1000
            and not set(x.get("students") or []) <= dsids]
    prog_dir = S + "/real/schools/waseaca-london/progress"
    seat_prog = [lid for lid in seats if os.path.exists(os.path.join(prog_dir, acc[lid]["sid"] + ".json"))]
    check("本物の席（%d）は席のまま（記録も無い）。ためし用の生徒（%d）に demo の印" % (len(seats), len(demo)),
          len(seats) >= 10 and len(demo) >= 20 and not seat_prog, (len(seats), len(demo), seat_prog[:3]))
    check("期限の過ぎた demo の宿題の受け取り手は、ためし用の生徒だけ（期限前の回は本物の生徒にも届く）", not leak, leak[:3])
print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng else "通っていないものがある", ok, ng))
