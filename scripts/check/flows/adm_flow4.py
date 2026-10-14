# -*- coding: utf-8 -*-
"""2回目の第三者の検査で直した所を、Chrome で押す：管理者が自分の合言葉を作り直す／裏の取り直しは「さわった」に数えない。"""
import json, os, sys, time
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check"); sys.path.insert(0, S + "/tube/server")
from cdp import Chrome
import scram
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots3"
ok = ng = 0
def check(name, cond, detail=""):
    global ok, ng
    if cond: ok += 1; print("  OK   " + name)
    else: ng += 1; print("  ×    %s  %s" % (name, detail))
def click(c, sel): return c.eval("(function(){var b=document.querySelector(%s); if(b){b.click(); return true;} return false;})()" % json.dumps(sel))
def text(c, sel): return c.eval("(function(){var b=document.querySelector(%s); return b ? b.innerText : null;})()" % json.dumps(sel))
PW = "kensa-kanri-kensa-kanri-kensa-0000"
with Chrome(width=1440, height=900, scale=2, port=9817) as c:
    c.goto(BASE + "/admin", wait=1.0)
    c.eval("window.__errs=[]; window.addEventListener('error', function(e){ window.__errs.push(String(e.message)); });")
    c.wait_for("!!document.querySelector('#gId')")
    c.eval("document.querySelector('#gId').value='wadmin99'; document.querySelector('#gPw').value=%s; document.querySelector('#gGo').click();" % json.dumps(PW))
    assert c.wait_for("!!document.querySelector('.tabs')", 25)
    # 裏の取り直しに、印の見出しが付くか（fetch をのぞく）
    c.eval("window.__q=[]; (function(){ var f = window.fetch; window.fetch = function(u, o){ window.__q.push([String(u), ((o||{}).headers||{})['X-Tube-Quiet'] || '']); return f.apply(this, arguments); }; })();")
    click(c, '[data-act="tab"][data-v="staff"]'); time.sleep(1.0)
    q1 = json.loads(c.eval("JSON.stringify(window.__q)"))
    check("人が押した取り直しには、印を付けない（さわったことになる）", any("/admin/state" in u and not h for u, h in q1), q1[:3])
    c.eval("window.__q=[]"); print("    （裏の取り直しを待っています。95秒）"); time.sleep(95)
    q2 = json.loads(c.eval("JSON.stringify(window.__q)"))
    quiet = [h for u, h in q2 if "/admin/state" in u]
    check("押さずに1分たったあとの、裏の取り直しには印が付く（さわったことにしない）", len(quiet) >= 2 and quiet[-1] == "1", q2)
    # 自分の合言葉を作り直す
    click(c, '[data-act="adminopen"][data-v="wadmin99"]'); time.sleep(0.6)
    btns = json.loads(c.eval("JSON.stringify(Array.prototype.map.call(document.querySelectorAll('.sheet [data-act], .sheet button'), function(b){ return [b.getAttribute('data-act'), b.innerText.slice(0, 20)]; }))"))
    first = c.eval("(function(){ var b = Array.prototype.filter.call(document.querySelectorAll('[data-id=\"wadmin99\"]'), function(x){ return x.innerText.indexOf('作り直す') >= 0; })[0]; if(!b) return 'なし'; b.click(); return b.getAttribute('data-act'); })()")
    time.sleep(0.5)
    if first == "arm":
        c.eval("(function(){ var b = Array.prototype.filter.call(document.querySelectorAll('[data-id=\"wadmin99\"]'), function(x){ return x.getAttribute('data-act') === 'repw'; })[0]; if(b) b.click(); })()")
    got = c.wait_for("!!document.querySelector('.fresh td.pw')", 40)
    check("自分の合言葉を作り直すと、新しい合言葉が出る", got, (first, btns[:8]))
    newpw = text(c, ".fresh td.pw") or ""
    tools = c.eval("Array.prototype.map.call(document.querySelectorAll('.fresh .tool [data-act]'), function(b){ return b.getAttribute('data-act'); }).join(',')")
    check("自分のときは「カードにする」を出さない（押すと、入り直しの画面に変わって合言葉を失う）", "tocards" not in tools and "copy" in tools, tools)
    c.shot(os.path.join(OUT, "d6-selfreset.png"))
    time.sleep(35)
    check("合言葉を出しているあいだは、画面が入口に変わらない", c.eval("!!document.querySelector('.fresh td.pw')") and (text(c, ".fresh td.pw") or "") == newpw)
    click(c, '[data-act="freshx"]'); time.sleep(0.5)
    click(c, '[data-act="tab"][data-v="now"]')
    check("閉じたあとは、入り直しの画面になり、わけが出る", c.wait_for("!!document.querySelector('#gId')", 40) and "作り直しました" in (c.eval("document.body.innerText") or ""), (c.eval("document.body.innerText") or "")[:80])
    check("前の合言葉では入れない・新しい合言葉で入れる", scram.login(BASE, "wadmin99", PW, admin=True)[0] == 401 and scram.login(BASE, "wadmin99", newpw, admin=True)[0] == 200)
    check("JS のエラーが無い", not json.loads(c.eval("JSON.stringify(window.__errs||[])")))
print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng else "通っていないものがある", ok, ng))
