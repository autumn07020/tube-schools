# -*- coding: utf-8 -*-
"""入口と初回登録を撮る。 python3 tour_entry.py <S> <dev>"""
import json, os, sys, time, urllib.request
from atlaslib import *
import scram
DV = sys.argv[2]
def api(method, path, tok=None, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode())
    req.add_header("Content-Type", "application/json")
    if tok: req.add_header("Authorization", "Bearer " + tok)
    r = urllib.request.urlopen(req, timeout=60); return json.loads(r.read().decode() or "{}")
st, d = scram.login(BASE, "wadmin99", "kensa-kanri-kensa-kanri-kensa-0000", admin=True)
code = api("POST", "/api/admin/join/code", d["token"], {})["join"]["code"]
PW = "atlas no aikotoba 2026"
def shot(t, key, title, how, note=""):
    p = os.path.join(OUT, "%s-%s-%s.png" % (t.section, key, t.dev)); t.c.shot(p)
    t.items.append({"section": t.section, "key": key, "dev": t.dev, "files": [os.path.basename(p)], "title": title, "how": how, "note": note, "persona": t.who})
    print("  cap", key, flush=True)
with Chrome(port=int(os.environ.get("ATLAS_PORT", "9890")), **DEV[DV]) as c:
    t = Tour(c, DV, "入口", "", "はじめて開く人（保護者・生徒）")
    # はじめての端末：ようこそ
    c.goto(BASE + "/", wait=0.5); c.eval("localStorage.clear(); sessionStorage.clear();"); c.goto("about:blank", wait=0.2)
    c.goto(BASE + "/", wait=0.0); time.sleep(0.75)
    shot(t, "01ようこそ-動きの途中", "ようこそ（印が弾んで出る動きの途中）", "はじめての端末で開く", "印（アイコン）が弾み、輪が広がり、文字が1つずつ出る。約1.8秒")
    t.wait("!!document.querySelector('.jn-welcome #jnGo')", 15); time.sleep(2.6)
    t.cap("02ようこそ", "ようこそ（Welcome to tube study!）", "はじめての端末で開く。動きが終わったところ", "「登録する」と「ログイン」。2度目からは出ない", segs=1)
    # ログイン
    t.click("#jnLogin", wait=0.9)
    shot(t, "03ログイン-動きの途中", "ログイン（銘の動きの途中）", "「ログイン」。端末で1日に1回だけ動く", "印と銘が画面の真ん中で出て、元の場所へ滑り、札が浮かぶ（約1.5秒）")
    t.wait("(function(){ var e=document.querySelector('#lId'); if(!e) return false; var o=1,n=e; while(n&&n.nodeType===1){ o*=parseFloat(getComputedStyle(n).opacity); n=n.parentNode; } return o>0.98; })()", 12); time.sleep(0.5)
    t.cap("04ログイン", "ログイン", "「ログイン」（2度目からは最初にこの画面）", "中央1列：印（92px）と銘 → ログインの札 → ためしに見る（試し運用とデモのときだけ）→ 初回登録する", segs=1)
    c.eval("document.querySelector('#lId').value='s-000'; document.querySelector('#lPw').value='chigau aikotoba';"); t.click("#lGo", wait=3.5)
    t.cap("05ログイン-まちがい", "ログイン（ID か合言葉が違うとき）", "違う合言葉で「はいる」", segs=1)
    if t.click("#lShow", wait=0.5): pass
    if t.click("#demoOpen", wait=1.2): t.cap("06ためしに見る", "ためしに見る（役を選ぶ紙）", "ログイン →「ためしに見る」", "講師4人・生徒5人の見本。合言葉は画面に出さない", layer=True, segs=2)
    # 幕（All aboard!）
    t.fresh("/"); t.wait("!!document.querySelector('#lId')")
    c.eval("document.querySelector('#lId').value=%s; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();" % (json.dumps("lj2r01"), json.dumps(ACC["lj2r01"]["password"])))
    t.wait("!!document.querySelector('#welcome')", 20); time.sleep(0.95)
    shot(t, "07幕", "ログインのあとの幕（All aboard!）", "ログインに成功した直後", "印が弾んで出て、銘と呼び名が続く。白い輪がほどけて右へ消え、約3秒でホームが明ける")
    time.sleep(0.75); shot(t, "08幕-輪がほどける", "幕（輪がほどけて消えるところ）", "幕の 1.5秒あたり")
    t.wait(HOME, 30)
    # 初回登録
    t.fresh("/"); t.wait("!!document.querySelector('#lJoin')"); t.click("#lJoin", wait=1.0)
    t.cap("10登録コード", "初回登録：登録コードを入れる", "ログイン →「初回登録する」（QR から来た人は飛ばす）", segs=1)
    c.eval("document.querySelector('#jnCode').value='ZZZZZZ'"); t.click("#jnCodeGo", wait=1.5)
    t.cap("11登録コード-ちがう", "初回登録：コードが違うとき", "違うコードで進む", segs=1)
    c.goto(BASE + "/", wait=0.4); c.eval("localStorage.clear(); sessionStorage.clear();"); c.goto("about:blank", wait=0.2); c.goto(BASE + "/#join=" + code, wait=0.8)
    t.wait("!!document.querySelector('#jnGo')", 15); time.sleep(2.6); t.click("#jnGo", wait=1.0)
    t.wait("!!document.querySelector('#jnVideo')", 15); time.sleep(2.5)
    t.cap("12できることの動画", "初回登録：tube study で出来ること（約30秒の動画）", "ようこそ →「登録する」", "右下に「スキップ」。音は押してから。動画は仮（差し替え予定）", segs=1)
    t.click("#jnSkip", wait=1.2)
    t.cap("13学年を選ぶ", "初回登録：学年を選ぶ", "動画のあと（かスキップ）", "学年を選ぶまで、クラスも「次へ」も出ない", segs=1)
    t.click('[data-act="grade"][data-v="e4"]', wait=0.9)
    t.cap("14クラスを選ぶ", "初回登録：クラスを選ぶ（同じページで下に続く）", "学年を押す", "小学生は α・β・K、中学生は T・R・D", segs=1)
    t.click('[data-act="class"][data-v="e4a"]', wait=0.9)
    t.cap("15受講科目を選ぶ", "初回登録：受講科目を選ぶ", "クラスを押す", "小：国算／国算理社／国算英／国算理社英　中：国数／国数英／国数理社／国数理社英", segs=2)
    t.click('[data-act="subj"][data-v="1"]', wait=1.0)
    t.cap("16入れ終わり", "初回登録：1人ぶん入れ終わったところ", "受講科目を押す", "「戻る」「2人目を登録する」「次へ」", focus="#jnFoot")
    t.click('[data-act="add"]', wait=1.0)
    t.click('[data-act="grade"][data-i="1"][data-v="e4"]', wait=0.7); t.click('[data-act="class"][data-i="1"][data-v="e4a"]', wait=0.7); t.click('[data-act="subj"][data-i="1"][data-v="1"]', wait=1.0)
    t.cap("17二人目", "初回登録：2人目を入れたところ", "「2人目を登録する」", "4人まで。外すのは「この生徒を外す」", segs=3)
    t.click('[data-act="next"]', wait=1.1)
    t.cap("18確かめる", "初回登録：確かめる（登録する内容・大事なこと4つ・利用規約）", "「次へ」", "「修正する」と「アカウントを作成する」", segs=3)
    t.click('[data-act="terms"]', wait=0.6)
    t.cap("19利用規約", "初回登録：利用規約を開いたところ", "「利用規約をすべて読む」", "事業者名と連絡先は仮のまま", segs=5)
    t.click('[data-act="create"]', wait=0.5); t.wait("!!document.querySelector('.jn-idone, .jn-idrow')", 25); time.sleep(1.0)
    t.cap("20IDと合言葉", "初回登録：生徒 ID ができた・合言葉を作る", "「アカウントを作成する」", "ID は s-000 の形。同じクラスのきょうだいには「どちらがどの ID か決めてください」。ID は必ずメモ", segs=3)
    c.eval("document.querySelector('#jnPw').value='mijikai'"); t.click("#jnPwGo", wait=0.9)
    t.cap("21合言葉-短い", "初回登録：合言葉が短いとき", "8文字未満で進む", focus="#jnMsg")
    c.eval("document.querySelector('#jnPw').value=%s" % json.dumps(PW)); t.click("#jnPwGo", wait=0.5)
    t.wait("!!document.querySelector('.jn-done')", 60); time.sleep(0.9)
    shot(t, "22完了-動きの途中", "初回登録：登録が完了しました！（動きの途中）", "合言葉を決める", "印が弾んで出て、紙ふぶきのような点が広がる")
    time.sleep(2.2)
    t.cap("23完了", "初回登録：登録が完了しました！", "合言葉を決める", "2人なら左右に「はじめる」が2つ、上にそれぞれの ID", segs=1)
    ids = json.loads(c.eval("JSON.stringify([].map.call(document.querySelectorAll('[data-act=\"begin\"]'), function(b){ return b.getAttribute('data-i'); }))"))
    t.click('[data-act="begin"]', wait=0.5); t.wait(HOME, 40); time.sleep(1.8)
    t.section = "入口"; t.cap("24はじめてのホーム", "登録した直後のホーム（宿題がまだ無いとき）", "「はじめる」→ 幕 → ホーム", "空の状態の見本。先生が宿題を出すと、ここに届く", segs=3)
    t.tab("homework"); t.cap("25はじめての宿題", "登録した直後の宿題のタブ", "タブ「宿題」", segs=2)
    t.tab("daily"); t.cap("26はじめての毎日テスト", "登録した直後の毎日テストのタブ", "タブ「毎日テスト」", segs=2)
    t.tab("record"); t.cap("27はじめての先生から", "登録した直後の「先生から」", "タブ「先生から」", segs=2)
    t.save("entry-%s" % DV)
