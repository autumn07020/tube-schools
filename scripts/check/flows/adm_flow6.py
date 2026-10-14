# -*- coding: utf-8 -*-
"""初回登録を Chrome で通す：ようこそ → コード → 動画 → 学年・クラス・科目 → 確かめる → ID と合言葉 → 完了 → ホーム。"""
import json, os, re, sys, time, urllib.request, urllib.error
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server")
from cdp import Chrome
import scram
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots6"; os.makedirs(OUT, exist_ok=True)
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
def fresh(c, url="/"):
    c.goto(BASE + "/", wait=0.6); c.eval("localStorage.clear(); sessionStorage.clear();"); c.goto("about:blank", wait=0.2); c.goto(BASE + url, wait=0.6); watch(c)
def nowide(c): return c.eval("document.documentElement.scrollWidth <= window.innerWidth")
HOME = "!document.querySelector('.jn') && !document.querySelector('#welcome:not(.out)') && !!document.querySelector('[data-tab]')"

st, d = scram.login(BASE, "wadmin99", "kensa-kanri-kensa-kanri-kensa-0000", admin=True); adm = d["token"]
code = api("POST", "/api/admin/join/code", adm, {})[1]["join"]["code"]

with Chrome(width=430, height=900, scale=2, mobile=True, port=9832) as kid, Chrome(width=1440, height=900, scale=2, port=9833) as c:
    print("\nようこそ")
    fresh(kid)
    check("はじめての端末では「ようこそ」が出る（登録する・ログイン）", kid.wait_for("!!document.querySelector('.jn-welcome #jnGo') && !!document.querySelector('#jnLogin')", 15) and "にようこそ" in (text(kid, ".jn-hello") or ""))
    check("上の帯と下のタブは出ない・横にはみ出さない", kid.eval("getComputedStyle(document.querySelector('#chrome')).display === 'none'") and nowide(kid))
    click(kid, "#jnLogin")
    check("「ログイン」で、いつもの入口へ", kid.wait_for("!!document.querySelector('#lId')", 10))
    check("入口の下に小さく「初回登録する」がある", (text(kid, "#lJoin") or "") == "初回登録する")
    kid.goto("about:blank", wait=0.2); kid.goto(BASE + "/", wait=0.8)
    check("2度目からは、ようこそを出さずに入口", kid.wait_for("!!document.querySelector('#lId')", 10) and not kid.eval("!!document.querySelector('.jn-welcome')"))
    click(kid, "#lJoin")
    check("「初回登録する」は、ようこその動きを見せずに登録コードへ", kid.wait_for("!!document.querySelector('#jnCode')", 10))
    kid.eval("document.querySelector('#jnCode').value='ZZZZZZ'"); click(kid, "#jnCodeGo")
    check("違うコードは、わけを言って止まる", kid.wait_for("!!document.querySelector('#jnMsg.on')", 10) and "登録コードが違います" in (text(kid, "#jnMsg") or ""), text(kid, "#jnMsg"))
    click(kid, "#jnBack")
    check("「戻る」で入口へ戻れる", kid.wait_for("!!document.querySelector('#lId')", 10))

    print("\n招待の QR から（1人）")
    fresh(kid, "/#join=" + code)
    check("QR の番地で開くと、ようこそ。番地からコードは消える", kid.wait_for("!!document.querySelector('.jn-welcome')", 15) and kid.eval("location.hash") == "")
    click(kid, "#jnGo")
    check("コードを打たずに「できること」の動画へ", kid.wait_for("!!document.querySelector('#jnVideo')", 15))
    time.sleep(2.0)
    v = json.loads(kid.eval("JSON.stringify({rs:document.querySelector('#jnVideo').readyState, err:!!document.querySelector('#jnVideo').error, t:document.querySelector('#jnVideo').currentTime, muted:document.querySelector('#jnVideo').muted})"))
    check("動画が読めて、音なしで流れている。右下に「スキップ」", v["rs"] >= 2 and not v["err"] and v["t"] > 0.3 and v["muted"] and (text(kid, "#jnSkip") or "") == "スキップ", v)
    click(kid, "#jnSkip")
    check("スキップで、学年を選ぶ画面へ", kid.wait_for("!!document.querySelector('[data-act=\"grade\"]')", 10) and "登録する生徒様の学年を選んでください" in (text(kid, ".jn-q h1") or ""))
    gl = kid.eval("Array.prototype.map.call(document.querySelectorAll('[data-act=\"grade\"]'), function(b){ return b.innerText; }).join(',')")
    check("学年は小4〜中3", gl == "小4,小5,小6,中1,中2,中3", gl)
    check("学年を選ぶまで、クラスも「次へ」も出ない／押せない", not kid.eval("!!document.querySelector('[data-act=\"class\"]')") and kid.eval("(function(){ var b=document.querySelector('[data-act=\"next\"]'); return !b || b.disabled; })()"))   # 10-09 見本 E13：次へは選び終えるまで出さない
    click(kid, '[data-act="grade"][data-v="j1"]'); time.sleep(0.8)
    cl = kid.eval("Array.prototype.map.call(document.querySelectorAll('[data-act=\"class\"] .jn-letter'), function(b){ return b.innerText; }).join(',')")
    check("中学生のクラスは T・R・D", cl == "T,R,D", cl)
    click(kid, '[data-act="class"][data-v="j1r"]'); time.sleep(0.8)
    sl = kid.eval("Array.prototype.map.call(document.querySelectorAll('[data-act=\"subj\"] span:first-child'), function(b){ return b.innerText; }).join('|')")
    check("中学生の科目は 数学 の4つの組", sl == "国語・数学|国語・数学・英語|国語・数学・理科・社会|国語・数学・理科・社会・英語", sl)
    click(kid, '[data-act="grade"][data-v="e4"]'); time.sleep(0.8)
    check("学年を選び直すと、クラスと科目は選び直しになる", kid.eval("!document.querySelector('[data-act=\"class\"][aria-pressed=\"true\"]') && !document.querySelector('[data-act=\"subj\"]')"))
    click(kid, '[data-act="class"][data-v="e4b"]'); time.sleep(0.8); click(kid, '[data-act="subj"][data-v="1"]'); time.sleep(0.9)
    check("入れ終わると「2人目を登録する」と「次へ」が出る", "2人目を登録する" in (text(kid, '[data-act="add"]') or "") and not kid.eval("document.querySelector('[data-act=\"next\"]').disabled") and nowide(kid))
    click(kid, '[data-act="next"]'); time.sleep(0.9)
    body = kid.eval("document.querySelector('#main').innerText")
    check("確かめる：生徒の内容・大事なこと4つ・利用規約のボタン", "小4β" in body and "国語・算数・理科・社会" in body and kid.eval("document.querySelectorAll('.jn-point').length") == 4 and "利用規約（全文）を読む" in body, body[:120])
    click(kid, '[data-act="terms"]'); time.sleep(0.4)
    check("押すと利用規約の全文が開く（個人情報を「保存しない」とは書かない）", kid.eval("!!document.querySelector('.jn-terms')") and "個人データにあたります" in (text(kid, ".jn-terms") or ""))
    click(kid, '[data-act="fix"]'); time.sleep(0.8)
    check("「修正する」で、選んだまま戻れる", kid.eval("(document.querySelector('[data-act=\"class\"][aria-pressed=\"true\"]')||{}).getAttribute && document.querySelector('[data-act=\"class\"][aria-pressed=\"true\"]').getAttribute('data-v')") == "e4b")
    click(kid, '[data-act="next"]'); time.sleep(0.8); click(kid, '[data-act="create"]')
    check("アカウントを作成すると、ID が大きく出る", kid.wait_for("!!document.querySelector('.jn-idone')", 20))
    sid1 = (text(kid, ".jn-idone") or "").strip()
    body = kid.eval("document.querySelector('#main').innerText")
    check("ID は s-000 の形。「あなたの生徒IDは…です」「ID は必ずメモを」", bool(re.match(r"^s-\d{3}$", sid1)) and "あなたの生徒IDは" in body and "ID は必ずメモをとってください" in body, sid1)
    st_, db = api("GET", "/api/admin/state", adm)
    seat = [x for k in db["classes"] if k["id"] == "e4b" for x in k["seats"] if x["id"] == sid1]
    check("この時点では、まだ名簿に出ない（仮の口座。管理ページには「登録の途中」）", bool(seat) and seat[0]["st"] == "pending", seat)
    f = json.loads(kid.eval("JSON.stringify({u:document.querySelector('#jnForm [autocomplete=\"username\"]').value, p:document.querySelector('#jnPw').getAttribute('autocomplete'), t:document.querySelector('#jnPw').type})"))
    check("端末のパスワード保存が効く形（username と new-password の欄）", f == {"u": sid1, "p": "new-password", "t": "password"}, f)
    kid.eval("document.querySelector('#jnPw').value='mijikai'"); click(kid, "#jnPwGo"); time.sleep(0.5)
    check("短い合言葉は断る", "8文字以上" in (text(kid, "#jnMsg") or ""), text(kid, "#jnMsg"))
    kid.eval("window.__sent=[]; (function(){ var f = window.fetch; window.fetch = function(u, o){ window.__sent.push(String(u) + ' ' + String((o||{}).body||'')); return f.apply(this, arguments); }; })();")
    PW = "Wagaya no Aikotoba 2026"
    kid.eval("document.querySelector('#jnPw').value=%s" % json.dumps(PW)); click(kid, "#jnPwGo")
    check("合言葉を決めると「登録が完了しました！」", kid.wait_for("!!document.querySelector('.jn-done')", 40) and "登録が完了しました！" in (text(kid, ".jn-hello") or ""))
    sent = " ".join(json.loads(kid.eval("JSON.stringify(window.__sent)")))
    check("送った本文に合言葉は無い（確かめる値だけ）", "/join/finish" in sent and "storedKey" in sent and "Wagaya" not in sent and "wagayanoaikotoba2026" not in sent)
    kid.shot(os.path.join(OUT, "g1-done-one.png"))
    click(kid, '[data-act="begin"][data-i="0"]')
    check("「はじめる」で、いつもの幕のあとホームへ", kid.wait_for(HOME, 40)); time.sleep(1.2)
    head = kid.eval("(document.querySelector('header')||{}).innerText || ''")
    check("画面の呼び名は「小4β s-000」", ("小4β " + sid1) in head.replace("\n", " "), head)
    check("入ったあとの画面に、合言葉が残っていない", kid.eval("JSON.stringify(localStorage).indexOf('Wagaya') < 0 && !TubeJoin.state()"))
    stt, dd = scram.login(BASE, sid1, "wagaya-no-aikotoba-2026")
    check("ほかの端末からも、同じ ID と合言葉で入れる（大文字・空白のちがいは気にしない）", stt == 200 and dd["profile"]["classId"] == "e4b" and dd["profile"]["subjects"] == ["japanese", "math", "science", "social"], (stt, dd.get("error")))
    kid.goto("about:blank", wait=0.2); kid.goto(BASE + "/", wait=1.0)
    check("開き直すと、そのままホーム（ようこそも質問も出ない）", kid.wait_for(HOME, 30) and not kid.eval("!!document.querySelector('.dc-card')"))
    check("生徒の画面に JS のエラーが無い", not errs(kid), errs(kid)[:3])
    # 登録したその日に、今の宿題が見える（10-10 本人：新しく作った口座に「宿題はありません」と出た。ためし運用のデモの
    # 宿題に本物の生徒を足さない決まりを私が入れていたため）。小4β 国語（wt01 の担当。段階 4）の期限前の回が届く。
    st2, d2 = api("GET", "/api/assignments", dd.get("token") or "")
    rows2 = (d2 or {}).get("assignments") or []
    nowms2 = time.time() * 1000
    check("登録したその日に、今週の宿題（小4β 国語。期限前）が届いている。過ぎた回の「未提出」は付かない",
          any(a.get("subject") == "japanese" and int(a.get("dueAt") or 0) >= nowms2 for a in rows2)
          and not any(int(a.get("dueAt") or 0) < nowms2 for a in rows2), (st2, len(rows2)))
    home2 = kid.eval("document.querySelector('#main').innerText")
    check("ホームに「宿題はありません」と出ない", "宿題はありません" not in home2, home2[:120])

    print("\nふたご（同じクラス）")
    fresh(kid, "/#join=" + code); kid.wait_for("!!document.querySelector('#jnGo')", 15); click(kid, "#jnGo")
    kid.wait_for("!!document.querySelector('#jnSkip')", 15); click(kid, "#jnSkip"); kid.wait_for("!!document.querySelector('[data-act=\"grade\"]')", 10)
    for i in (0, 1):
        click(kid, '[data-act="grade"][data-i="%d"][data-v="e6"]' % i); time.sleep(0.6)
        click(kid, '[data-act="class"][data-i="%d"][data-v="e6k"]' % i); time.sleep(0.6)
        click(kid, '[data-act="subj"][data-i="%d"][data-v="0"]' % i); time.sleep(0.7)
        if i == 0:
            click(kid, '[data-act="add"]'); time.sleep(0.7)
    check("2人目まで入れると「3人目を登録する」が出る", "3人目を登録する" in (text(kid, '[data-act="add"]') or ""))
    click(kid, '[data-act="next"]'); time.sleep(0.8)
    check("確かめる画面に2人ぶん並ぶ", kid.eval("document.querySelectorAll('.jn-item').length") == 2)
    click(kid, '[data-act="create"]'); kid.wait_for("!!document.querySelector('.jn-idrow')", 20)
    ids = json.loads(kid.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('.jn-idrow .jn-id'), function(x){ return x.innerText.trim(); }))"))
    check("ID が2つ（クラスと科目つきで）。同じクラスなので「どちらがどの ID か決めてください」", len(ids) == 2 and ids[0] != ids[1] and "いま ご家庭で 決めてください" in (text(kid, ".jn-twin") or ""), ids)
    kid.eval("document.querySelector('#jnPw').value=%s" % json.dumps(PW)); click(kid, "#jnPwGo")
    kid.wait_for("!!document.querySelector('.jn-done')", 40); time.sleep(0.5)
    check("完了の画面に「はじめる」が2つ、それぞれの上に ID", kid.eval("document.querySelectorAll('[data-act=\"begin\"]').length") == 2 and json.loads(kid.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('.jn-start .jn-id'), function(x){ return x.innerText.trim(); }))")) == ids and nowide(kid))
    click(kid, '[data-act="begin"][data-i="1"]')
    check("2人目のほうで はじめられる", kid.wait_for(HOME, 40) and kid.eval("localStorage.getItem('tube.school.v1.who')") == ids[1], kid.eval("localStorage.getItem('tube.school.v1.who')"))
    check("同じ合言葉で、1人目も入れる", scram.login(BASE, ids[0], PW)[0] == 200)

    print("\nデモの入口・管理ページ")
    fresh(kid, "/demo")
    check("デモの入口（/demo）では、ようこそを出さない", kid.wait_for("!!document.querySelector('#lId')", 15) and not kid.eval("!!document.querySelector('.jn-welcome')") and not kid.eval("!!document.querySelector('#lJoin')"))
    c.goto(BASE + "/admin", wait=1.0); watch(c)
    c.wait_for("!!document.querySelector('#gId')")
    c.eval("document.querySelector('#gId').value='wadmin99'; document.querySelector('#gPw').value='kensa-kanri-kensa-kanri-kensa-0000'; document.querySelector('#gGo').click();")
    assert c.wait_for("!!document.querySelector('.tabs')", 25); time.sleep(0.8)
    check("管理ページの「いまの様子」に、登録コードと QR が出る", (text(c, ".join-code") or "").strip() == code and c.eval("!!document.querySelector('.join-qr svg')"))
    same = c.eval("(function(){ var t=document.createElement('div'); t.innerHTML = TubeQR.svg(%s, 148); return document.querySelector('.join-qr svg path').getAttribute('d') === t.querySelector('path').getAttribute('d'); })()" % json.dumps(BASE + "/#join=" + code))
    check("QR の中身は 入口＋#join=コード", same)
    c.shot(os.path.join(OUT, "g2-admin-join.png"))
    click(c, '[data-act="tab"][data-v="seats"]'); time.sleep(0.4); click(c, '[data-act="cls"][data-v="e4b"]'); time.sleep(1.0)
    row = c.eval("(function(){ var r=Array.prototype.filter.call(document.querySelectorAll('.row'), function(x){ return x.innerText.indexOf(%s)>=0; })[0]; return r ? r.innerText : ''; })()" % json.dumps(sid1))
    check("登録した生徒は、クラスの一覧に「使っている」と出る", "使っている" in row, row[:80])
    click(c, '[data-act="close"]'); time.sleep(0.3); click(c, '[data-act="tab"][data-v="now"]'); time.sleep(0.5)
    click(c, '[data-key="joinnew"]'); time.sleep(0.4)
    check("作り直すは2度押し", "本当に作り直す" in (text(c, '[data-key="joinnew"]') or ""))
    click(c, '[data-key="joinnew"]'); time.sleep(1.2)
    code2 = (text(c, ".join-code") or "").strip()
    check("作り直すと、コードが変わり、前のコードは使えない", code2 and code2 != code and api("POST", "/api/join/check", None, {"code": code})[0] == 403 and api("POST", "/api/join/check", None, {"code": code2})[0] == 200, code2)
    check("管理ページに JS のエラーが無い", not errs(c), errs(c)[:3])
print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng else "通っていないものがある", ok, ng))
