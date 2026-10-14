# -*- coding: utf-8 -*-
"""管理ページの紙の続き（席の行・合言葉・リンク・カード・配る紙）と、時期で出る札（組分けの申告・学年の繰り上げ・卒業・使われていない口座）。"""
import json, os, re, subprocess, sys, time, urllib.request
os.environ["MYACADY_ROOT"] = os.environ["ATLAS_S"] + "/real"; os.environ["MYACADY_FSYNC"] = "0"
from atlaslib import *
import scram, paths
import tube_server as T
import retire as R
SC = "waseaca-london"; ADMIN, APW = "wadmin99", "kensa-kanri-kensa-kanri-kensa-0000"
def api(method, path, tok=None, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode())
    req.add_header("Content-Type", "application/json")
    if tok: req.add_header("Authorization", "Bearer " + tok)
    try:
        r = urllib.request.urlopen(req, timeout=60); return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {}
day = lambda n: time.strftime("%Y-%m-%d", time.localtime(time.time() + n * 86400))
def adm_tok(): return scram.login(BASE, ADMIN, APW, admin=True)[1]["token"]
def printed(t, key, title, how, note=""):
    """刷るときの見た目（@media print）で撮る。"""
    t.c.ws.call("Emulation.setEmulatedMedia", {"media": "print"}); time.sleep(0.6)
    p = os.path.join(OUT, "%s-%s-%s.png" % (t.section, key, t.dev)); t.c.shot(p, full=True)
    t.c.ws.call("Emulation.setEmulatedMedia", {"media": ""}); time.sleep(0.3)
    t.items.append({"section": t.section, "key": key, "dev": t.dev, "files": [os.path.basename(p)], "title": title, "how": how, "note": note, "persona": t.who})
    print("  cap(print)", key, flush=True)
with Chrome(port=9897, **DEV["D"]) as c, Chrome(port=9898, **DEV["P"]) as k:
    t = Tour(c, "D", "管理", ADMIN, "管理者"); s = Tour(k, "P", "時期の札", "", "")
    def opn(tab=None):
        c.goto(BASE + "/admin", wait=0.9); t.wait("!!document.querySelector('#gId') || !!document.querySelector('.tabs')", 20)
        if t.has("#gId"):
            c.eval("document.querySelector('#gId').value=%s; document.querySelector('#gPw').value=%s; document.querySelector('#gGo').click();" % (json.dumps(ADMIN), json.dumps(APW)))
            t.wait("!!document.querySelector('.tabs')", 30)
        time.sleep(0.9)
        if tab: t.click('[data-act="tab"][data-v="%s"]' % tab, wait=1.0)
    # ---- 1. 席の行・合言葉・リンク・カード・配る紙（試し運用のまま）
    opn("seats"); t.click('[data-act="cls"][data-v="e4a"]')
    t.click('[data-act="more"][data-id="we4a22"]', wait=0.6)
    t.cap("24生徒-席の行を開く", "管理ページ：クラスの紙で、席の行を開いたところ", "生徒 → クラスの札 → 行の「ほか」", "オンラインで渡す／合言葉を作り直す／学年・クラス・科目を変える／この席を消す", layer=True, segs=2)
    t.click('[data-act="repw"][data-id="we4a22"]', wait=1.5)
    t.cap("25生徒-合言葉を作り直した", "管理ページ：合言葉を作り直した（新しい合言葉が、この1回だけ出る）", "行の「合言葉を作り直す」", "写しの合言葉は、検査用の土台の中でしか通らないもの。「カードにする」でカードのタブへ", layer=True, segs=2)
    if t.click('[data-act="tocards"]', wait=1.2):
        t.cap("51カード-並んだ", "管理ページ：カード（切って配るカード。QR つき）", "合言葉の紙 →「カードにする」（か、カードのタブに表の行を貼る）", "A4 に 10枚。タブを離れると、合言葉は画面から消える", segs=3)
        printed(t, "52カード-刷る", "カードを刷るときの紙面（A4 に10枚・点線）", "カード →「刷る」", "QR は 入口＋ID＋合言葉。読むとそのまま入れる")
    opn("seats"); t.click('[data-act="cls"][data-v="e4b"]'); t.click('[data-act="more"][data-id="we4b01"]', wait=0.6)
    t.click('[data-act="online"][data-id="we4b01"]', wait=1.5)
    t.cap("26生徒-オンラインで渡す", "管理ページ：オンラインで渡す（1回だけ使えるリンク）", "行の「オンラインで渡す」", "リンクと、そのまま送れる文面。48時間・1回だけ", layer=True, segs=2)
    link = c.eval("(function(){ var m=(document.querySelector('.sheet')||document.body).innerText.match(/https?:\\/\\/[^\\s]+#k=[^\\s]+/); return m ? m[0] : ''; })()")
    if link:
        k.goto(BASE + "/", wait=0.5); k.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');"); k.goto("about:blank", wait=0.2); k.goto(link, wait=1.5)
        s.section = "入口"; s.who = "リンクを受け取った生徒"
        s.cap("30リンクから引き換える", "1回だけ使えるリンクを開いたところ（自分の合言葉に引き換える）", "講師・管理者から届いたリンクを開く", segs=2)
        if s.click("#cGo, [data-claim], .btn", wait=3.0): s.cap("31引き換えた合言葉", "引き換えた直後（自分の合言葉が、この1回だけ出る）", "「引き換える」", "メモする・端末に保存する → はじめる", segs=2)
    # 登録した生徒の行（ID が s-）→ 学年・クラス・科目を変える
    sid = sorted(x for x, a in T.accounts(SC).items() if x.startswith("s-") and a.get("role") == "student")[:1]
    if sid:
        cid = T.accounts(SC)[sid[0]]["classId"]
        opn("seats"); t.click('[data-act="cls"][data-v="%s"]' % cid); t.click('[data-act="more"][data-id="%s"]' % sid[0], wait=0.6)
        if t.click('[data-act="place"][data-id="%s"]' % sid[0], wait=1.0):
            t.cap("27生徒-学年クラス科目を変える", "管理ページ：学年・クラス・科目を変える紙", "行の「学年・クラス・科目を変える」", "本人（保護者）も設定から同じことができる", layer=True, segs=2)
    opn("now")
    c.eval("window.print = function(){};"); t.click('[data-act="joinprint"]', wait=1.2)     # 刷る紙面は、押したときに組まれる
    printed(t, "11いまの様子-配る紙", "保護者に配る紙（登録コードと QR）", "いまの様子 → 登録コード →「配る紙を刷る」", "刷るときの紙面")
    # ---- 2. 組分けの申告（テストの9日後＝聞いている時期にする）
    tok = adm_tok()
    api("PUT", "/api/admin/exams", tok, {"exams": [{"date": day(-44)}, {"date": day(-9)}, {"date": day(26)}], "resultDays": 7})
    with T.LOCK:
        db = T.accounts(SC)
        for lid in ("we4a20", "we4a21"): db[lid]["created"] = int(time.time()) - 30 * 86400
        T.save_accounts(SC, db)
    opn("now"); t.cap("12いまの様子-組分けを聞いている", "管理ページ：組分けテストの日程（いま聞いています・答えた人数）", "いまの様子 → 組分けテストの日程", "テストの7日後から14日のあいだ、生徒のホームに聞く札が出る", focus=".card.exams")
    s.section = "時期の札"; s.who = "小4α の生徒（組分けテストの結果が出たあと）"
    s.login("we4a20", "kensa-seito-kensa-0000")
    s.cap("01組分けの申告", "組分けの申告：「クラスは どちらに なりましたか」", "テストの結果が出てから2週間、ホームのいちばん上に出る", "いまのクラスに印。選ぶまでボタンは押せない", segs=2)
    if s.click("#paCard [data-pa]", nth=1, wait=0.6): s.cap("02組分けの申告-選んだ", "組分けの申告：クラスを選んだところ", "クラスの札を押す", "「このクラスに変える」／いまのクラスなら「変わらない（これで決める）」", segs=1)
    # ---- 3. 本番に切り替えて、学年の繰り上げ・卒業・使われていない口座
    r = subprocess.run([sys.executable, S + "/tube/server/tube_server.py", "go-live", "--school", SC, "--yes"], env=dict(os.environ), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-300:] + r.stderr[-300:]
    code = T.school_meta(SC)["join"]["code"]; tbl = T.class_table(SC)
    first = lambda g: sorted(cid for cid, cc in tbl.items() if cc.get("grade") == g)[0]
    PW = "atlas no aikotoba 2026"
    kids = [{"grade": g, "classId": first(g), "subjects": ["japanese", "math"]} for g in ("e6", "j3", "e4", "e5")]
    _c, j = api("POST", "/api/join", None, {"code": code, "agree": True, "students": kids})
    made = j["made"]
    api("POST", "/api/join/finish", None, {"items": [{"id": m["id"], "setup": m["setup"], "verifier": scram.make_verifier(PW)} for m in made]})
    k6, k3, k4, k5 = [m["id"] for m in made]
    tok = adm_tok(); api("PUT", "/api/admin/exams", tok, {"exams": [{"date": day(26)}]}); api("PUT", "/api/admin/exams", tok, {"yearStart": day(1)})
    opn("now"); t.cap("13いまの様子-新年度のはじまり", "管理ページ：新年度のはじまり（日付が入っている）", "いまの様子 → 新年度のはじまり", "この日の朝に全員の学年が1つ上がる。きょうと過去の日は入らない", focus=".card.year")
    R.roll(T, SC, now=time.time() + 86400 + 3600)
    now = int(time.time())
    with T.LOCK:
        db = T.accounts(SC); db[k5]["used"] = now - 86 * 86400; db[k5]["created"] = now - 200 * 86400; T.save_accounts(SC, db)
        meta = dict(T.school_meta(SC)); meta["liveAt"] = now - 300 * 86400; paths.save(paths.school_file(SC, "school.json"), meta)
    s.who = "小6 → 中1 に上がった生徒"; s.login(k6, PW)
    s.cap("03新しい学年のクラス", "学年の繰り上げ：「中1のクラスを教えてください」", "新年度のはじまりの日から、答えるまでホームのいちばん上に出る", "小6→中1 はクラスの記号が変わる（α・β・K → T・R・D）ので本人に聞く", segs=2)
    s.who = "卒業した中3の生徒"; s.login(k3, PW)
    s.cap("04卒業", "卒業：「卒業おめでとうございます」", "新年度のはじまりの日に、中3はクラスから外れる", "記録は見られる。新しい宿題は届かない。3か月使わなければ記録は自動で消える", segs=2)
    opn("now"); t.cap("14いまの様子-繰り上げのあと", "管理ページ：新年度のはじまり（この前の繰り上げの人数）", "繰り上げのあと", focus=".card.year")
    t.cap("15いまの様子-使われていない口座", "管理ページ：使われていない口座（もうすぐ消える ID と残りの日数）", "いまの様子 → 使われていない口座", "本番に切り替えた校舎だけ。3か月使われない ID は記録ごと自動で消える", focus=".card.idle")
    t.cap("16いまの様子-本番", "管理ページ：いまの様子（本番に切り替えたあと・全体）", "本番に切り替えたあと", segs=6)
    opn("seats"); t.cap("28生徒-本番", "管理ページ：生徒（保護者が登録した ID が並ぶ・クラスの決まっていない生徒）", "本番に切り替えたあと", segs=4)
    if t.has(".card.loose"): t.cap("29生徒-クラスの決まっていない生徒", "管理ページ：クラスの決まっていない生徒（卒業・クラスを聞いている）", "生徒のタブの下", focus=".card.loose")
    t.save("special-D"); s.save("special-P")
