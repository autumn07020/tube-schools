# -*- coding: utf-8 -*-
"""⑥ 宿題の往復を Chrome で通す（2026-10-10 本人「生徒が出す→講師が見る→採点→生徒に返る、を本当に実演できるか」）。

  場面A  デモの校舎 london：講師 lteacher1 が 中3R 数学 の提出箱を出す → 生徒 lj3r01 が写真2枚を出す
         → 講師の「今日やること」に出る → 宿題チェックで 4 と ひとこと → 生徒の「先生から」に新着 → 見た → 教科の返事に残る
  場面B  本物の形の校舎 waseaca-london：管理者が講師 wt90 を 小4α 算数 の担当に → wt90 が段階を「写真で提出」に
         → 提出箱 → 生徒 we4a20 が写真を出す → wt90 が採点 → 生徒に返る（本番で wt01 がやる手順そのもの）

  どちらも、画面を押して進め、API とサーバの記録で確かめる。
"""
import glob, json, os, sys, time, urllib.request, urllib.error, urllib.parse
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server"); sys.path.insert(0, S + "/tube/scripts/check/atlas")
from cdp import Chrome
from atlaslib import attach_files
import scram
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots12"; os.makedirs(OUT, exist_ok=True)
ok = ng = 0
def check(name, cond, detail=""):
    global ok, ng
    if cond: ok += 1; print("  OK   " + name)
    else: ng += 1; print("  ×    %s  %s" % (name, detail))
def click(c, sel): return c.eval("(function(){var b=document.querySelector(%s); if(b){b.click(); return true;} return false;})()" % json.dumps(sel))
def text(c, sel): return c.eval("(function(){var b=document.querySelector(%s); return b ? b.innerText : null;})()" % json.dumps(sel))
def errs(c): return json.loads(c.eval("JSON.stringify(window.__errs||[])"))
def watch(c): c.eval("window.__errs=[]; window.__net=[]; window.addEventListener('error', function(e){ window.__errs.push(String(e.message)); }); window.addEventListener('unhandledrejection', function(e){ window.__errs.push('rejection: '+String(e.reason)); }); if(!window.__fw){ window.__fw=window.fetch; window.fetch=function(u,o){ return window.__fw(u,o).then(function(r){ try{ if(String(u).indexOf('/check/rate')>=0||String(u).indexOf('/submissions')>=0){ r.clone().text().then(function(b){ window.__net.push([String(u), r.status, b.slice(0,160)]); }); } }catch(e){} return r; }); }; }")
def net(c): return json.loads(c.eval("JSON.stringify(window.__net||[])"))
demo = {x["id"]: x["password"] for x in json.load(open(S + "/real/demo-accounts.json")) if x.get("password")}   # 入口の一覧の ID だけの行（ためしの入口）は合言葉を持たない
def api(method, path, tok, body=None):
    req = urllib.request.Request(BASE + "/api" + path, method=method, data=(json.dumps(body).encode() if body is not None else None))
    req.add_header("Authorization", "Bearer " + tok); req.add_header("Content-Type", "application/json")
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
    except urllib.error.HTTPError as e:
        return {"error": "HTTP %d %s" % (e.code, e.read().decode()[:200])}
def login_ui(c, lid, pw):
    c.goto(BASE + "/", wait=0.6); c.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');")
    c.goto("about:blank", wait=0.2); c.goto(BASE + "/", wait=0.8); watch(c)
    c.wait_for("!!document.querySelector('#lId')", 20)
    c.eval("document.querySelector('#lId').value=%s; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();" % (json.dumps(lid), json.dumps(pw)))
    assert c.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)')", 40), "login " + lid
    time.sleep(1.5)
    return c.eval("localStorage.getItem('tube.school.v1.token')")
def tab(c, t):
    c.eval("TubeUI.go(%s)" % json.dumps(t)); time.sleep(1.2)
def login_api(lid, pw):
    sys.path.insert(0, S + "/tube/scripts/check")
    import expect
    return expect.Api(BASE).login(lid, pw)
# 写真の見本：デモの提出から2枚を、検査の置き場に写して使う（提出の置き場は場面Aの提出・返却で中身が変わる。
# 別の場面で「存在しない道」を選ぶと Chrome は黙って何も選ばず、「ためる」が出なかった。10-10）
import shutil
_src = sorted(glob.glob(S + "/real/schools/london/submissions/*/*.png"))[:2]
assert len(_src) == 2, "写真の見本が要ります（london の提出から2枚）"
PICS = []
for i, f in enumerate(_src):
    dst = os.path.join(OUT, "pic%d.png" % (i + 1)); shutil.copyfile(f, dst); PICS.append(dst)

def roundtrip(label, teacher, tpw, student, spw, key, course_name, port):
    """1往復。講師が提出箱 → 生徒が出す → 講師が見て採点 → 生徒に返る。"""
    print("\n== %s：%s（%s → %s）" % (label, course_name, student, teacher))
    with Chrome(width=1280, height=900, scale=2, port=port) as t, Chrome(width=430, height=900, scale=2, mobile=True, port=port + 1) as s:
        # --- 講師：提出箱を出す（時間割のコマ → 授業の紙 → 提出箱を出す） ---
        ttok = login_ui(t, teacher, tpw)
        tab(t, "hw")
        opened = t.wait_for("!!document.querySelector('.slot[data-slot$=%s]')" % json.dumps("|" + key), 15)
        check("講師の時間割に「%s」のコマがある" % course_name, opened)
        click(t, '.slot[data-slot$=%s]' % json.dumps("|" + key)); time.sleep(1.2)
        has_quiz = t.wait_for("!!document.querySelector('[data-quiz]')", 10)
        check("コマを押すと授業の紙が開き「提出箱を出す」がある", has_quiz, t.eval("(document.querySelector('.sheet')||{innerText:'(紙が開いていない)'}).innerText.slice(0,160)"))
        if not has_quiz:
            t.shot(os.path.join(OUT, label + "-0-no-quiz.png")); return
        title = "計算テスト 往復の確かめ"
        t.eval("var q=document.querySelector('#qzTitle'); q.value=%s; q.dispatchEvent(new Event('input'));" % json.dumps(title))
        click(t, '[data-quiz=%s]' % json.dumps(key)); time.sleep(2.5)
        t.shot(os.path.join(OUT, label + "-1-teacher-quiz.png"))
        # 出た提出箱を API で探す（生徒の宿題の id）
        asg_s = None; aid = None; stok = login_api(student, spw)
        for _ in range(10):
            asg_s = api("GET", "/assignments", stok) or {}
            for a in (asg_s.get("assignments") or []):
                if a.get("title") == title: aid = a.get("id")
            if aid: break
            time.sleep(1)
        check("提出箱が生徒の宿題として届く（%s）" % title, bool(aid), str(asg_s)[:200])
        if not aid: return
        # --- 生徒：写真2枚をためて送る ---
        login_ui(s, student, spw); tab(s, "homework")
        has_up = s.wait_for("!!document.querySelector('[data-up=%s]')" % json.dumps(aid), 15)
        if not has_up:
            click(s, '[data-hmore]'); time.sleep(0.8); has_up = s.wait_for("!!document.querySelector('[data-up=%s]')" % json.dumps(aid), 5)
        check("生徒の宿題タブに提出箱の行と「出す」がある", has_up)
        time.sleep(2.5)                                     # 読み込みの描き直し（返事・お知らせ）が落ち着いてから選ぶ
        staged = False
        for _try in range(3):
            assert attach_files(s, '[data-up=%s]' % json.dumps(aid), PICS), "写真を選べない"
            staged = s.wait_for("document.querySelectorAll('[data-stage=%s] .up-th').length >= 2" % json.dumps(aid), 6)
            if staged: break
        check("写真を選ぶと「ためる」札に2枚並ぶ", staged, "" if staged else ("errs=%s inputs=%s files=%s stage=%s pics=%s" % (errs(s)[:3], s.eval("document.querySelectorAll('[data-up]').length"), s.eval("(document.querySelector('[data-up=%s]')||{files:[]}).files.length" % json.dumps(aid)), s.eval("document.querySelectorAll('[data-stage]').length"), [(os.path.basename(x), os.path.exists(x)) for x in PICS])))
        if not staged: s.shot(os.path.join(OUT, label + "-2-stage-fail.png"))
        s.shot(os.path.join(OUT, label + "-2-student-stage.png"))
        click(s, '[data-upsend=%s]' % json.dumps(aid))
        check("「2枚を送る」で送られ、行から消える", s.wait_for("!document.querySelector('[data-upsend=%s]') && !document.querySelector('[data-up=%s]')" % (json.dumps(aid), json.dumps(aid)), 30))
        subs = api("GET", "/submissions/mine", stok) or {}
        got = (subs.get("mine") or {}).get(aid)
        check("サーバに写真2枚が保存される", bool(got) and len(got.get("files") or []) == 2, str(subs)[:200])
        s.shot(os.path.join(OUT, label + "-3-student-sent.png"))
        # --- 講師：今日やることに出る → 宿題チェック → 4 と ひとこと ---
        t.goto(BASE + "/", wait=1.5); watch(t); tab(t, "hw"); time.sleep(1.5)
        today = api("GET", "/today", ttok) or {}
        task = sorted([x for x in (today.get("tasks") or []) if x.get("key") == key and (x.get("todo") or 0) >= 1], key=lambda x: -(x.get("n") or 0))
        check("講師の「今日やること」に未評価1人として出る", bool(task), str([(x.get("key"), x.get("n"), x.get("todo")) for x in today.get("tasks") or []])[:300])
        if not task: return
        n = task[0]["n"]
        t.eval("TubeDesk.openCheck(%s, %d)" % (json.dumps(key), n)); time.sleep(1.5)
        cell = t.wait_for("!!document.querySelector('.dk-cell.s-todo')", 15)
        check("宿題チェックに、出した生徒の写真の札（未評価）がある", cell)
        t.eval("document.querySelector('.dk-cell.s-todo').click()"); time.sleep(1.0)
        sid = t.eval("document.querySelector('.dk-cell.focus') && document.querySelector('.dk-cell.focus').getAttribute('data-dksid')")
        check("札を押すと右に写真が大きく出る", t.wait_for("!!document.querySelector('.dk-view img') || !!document.querySelector('.dk-vimg')", 10))
        t.shot(os.path.join(OUT, label + "-4-teacher-check.png"))
        t.wait_for("!!document.querySelector('[data-dkrate=\"4\"]')", 10)
        for _try in range(3):
            click(t, '[data-dkrate="4"]')
            if t.wait_for("!!document.querySelector('.dk-rb.v4.on')", 4): break
            time.sleep(1.0)
        check("「4 できた」を押すと、その札に 4 が付く", t.eval("!!document.querySelector('.dk-rb.v4.on')"))
        time.sleep(1.0)
        note = "途中の式がきれいに書けています。次は見直しも。"
        t.eval("var n=document.querySelector('#dkNote'); n.value=%s; n.dispatchEvent(new Event('change'));" % json.dumps(note)); time.sleep(1.5)
        ck = api("GET", "/check?key=%s&n=%d" % (urllib.parse.quote(key), n), ttok) or {}
        row = None
        for r in ck.get("rows") or []:
            if r.get("sid") == sid: row = r
        check("サーバの記録：評価 4 と ひとことが付く", bool(row) and row.get("v") == 4 and row.get("note") == note, str(row)[:200] + " | net=" + str(net(t))[:300])
        t.shot(os.path.join(OUT, label + "-5-teacher-rated.png"))
        # --- 生徒：先生から に新着 → 見た → 教科の返事 ---
        s.goto(BASE + "/", wait=1.5); watch(s); tab(s, "record"); time.sleep(1.5)
        card = s.wait_for("Array.prototype.some.call(document.querySelectorAll('.ch-in'), function(e){ return e.innerText.indexOf(%s) >= 0; })" % json.dumps(note[:10]), 15)
        check("生徒の「先生から」に、ひとこと付きの新着が出る", card)
        chip = s.eval("(function(){ var e=[].filter.call(document.querySelectorAll('.ch-in'), function(e){ return e.innerText.indexOf(%s) >= 0; })[0]; return e ? e.innerText : ''; })()" % json.dumps(note[:10]))
        check("評価の語「よくできました」が付いている", "よくできました" in (chip or ""), (chip or "")[:120])
        s.shot(os.path.join(OUT, label + "-6-student-inbox.png"))
        s.eval("(function(){ var e=[].filter.call(document.querySelectorAll('.ch-in'), function(e){ return e.innerText.indexOf(%s) >= 0; })[0]; var b=e && e.querySelector('[data-fbseen]'); if(b) b.click(); })()" % json.dumps(note[:10])); time.sleep(1.2)
        check("「ことばを見た」で新着から消える", not s.eval("Array.prototype.some.call(document.querySelectorAll('.ch-in'), function(e){ return e.innerText.indexOf(%s) >= 0; })" % json.dumps(note[:10])))
        sub_id = key.split(":")[1]
        click(s, '[data-fbsub=%s]' % json.dumps(sub_id)); time.sleep(1.5)
        inpage = s.wait_for("document.body.innerText.indexOf(%s) >= 0" % json.dumps(title), 10)
        check("教科の返事に、その提出箱が評価つきで残る", inpage and s.eval("document.body.innerText.indexOf('よくできました') >= 0"))
        s.shot(os.path.join(OUT, label + "-7-student-subject.png"))
        check("生徒・講師の画面に JS のエラーが無い", not errs(s) and not errs(t), (errs(s) + errs(t))[:3])

ONLY = (sys.argv[2] if len(sys.argv) > 2 else "AB")
if ONLY == "AB":
    # 場面ごとに別のプロセスで（同じプロセスで続けると、2つ目の Chrome で写真を選んでも「ためる」が出ないことがあった。10-10）
    import subprocess
    rc = 0
    for scene in ("A", "B"):
        r = subprocess.run([sys.executable, os.path.abspath(__file__), S, scene])
        rc = rc or r.returncode
    print(); print("すべて通った（2つの場面）" if rc == 0 else "通っていない場面がある")
    sys.exit(rc)
# ---------- 場面A：デモの校舎 ----------
if "A" in ONLY: roundtrip("A", "lteacher1", demo["lteacher1"], "lj3r01", demo["lj3r01"], "j3r:math", "中3R 数学", 9840)
if "B" not in ONLY:
    print(); print("すべて通った（OK %d ／ × %d）" % (ok, ng) if ng == 0 else "通っていないものがある（OK %d ／ × %d）" % (ok, ng)); sys.exit(0 if ng == 0 else 1)

# ---------- 場面B：本物の形の校舎（担当→段階→提出箱→往復） ----------
print("\n== 場面B の下ごしらえ：管理者が wt90 を 小4α 算数 の担当にし、wt90 が段階を「写真で提出」にする")
with Chrome(width=1280, height=900, scale=2, port=9846) as a:
    a.goto(BASE + "/admin", wait=1.0); a.wait_for("!!document.querySelector('#gId')", 20)
    a.eval("document.querySelector('#gId').value='wadmin99'; document.querySelector('#gPw').value='kensa-kanri-kensa-kanri-kensa-0000'; document.querySelector('#gGo').click();")
    a.wait_for("!!document.querySelector('.tabs')", 20); time.sleep(0.5)
    atok = a.eval("sessionStorage.getItem('tube.admin.token')")
r = api("PUT", "/admin/courses/teacher", atok, {"key": "e4a:math", "id": "wt90", "on": True})
check("管理ページの API で担当が入る", r.get("on") is True and r.get("id") == "wt90", str(r)[:200])
wtok = login_api("wt90", "kensa-sensei-kensa-sensei-0000")
r2 = api("PUT", "/lessons/use", wtok, {"keys": ["e4a:math"], "level": 2})
check("講師が段階を 2（写真で提出）にできる", isinstance(r2, dict) and not r2.get("error") and r2.get("level") == 2, str(r2)[:200])
roundtrip("B", "wt90", "kensa-sensei-kensa-sensei-0000", "we4a20", "kensa-seito-kensa-0000", "e4a:math", "小4α 算数", 9842)

print()
print("すべて通った（OK %d ／ × %d）" % (ok, ng) if ng == 0 else "通っていないものがある（OK %d ／ × %d）" % (ok, ng))
sys.exit(0 if ng == 0 else 1)
