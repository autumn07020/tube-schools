# -*- coding: utf-8 -*-
"""⑨ ずれの検査 ―― 講師と生徒の全画面を 6 つの幅で開き、DOM の箱の位置から機械的に拾う（2026-10-11 本人
「スマホ版でレイアウトずれが多い…各ボタンの上下スペースがおかしい。少し被っている…px単位での調整になっていないか？
各スマホで適切に表示されなければいけません。iphone16plus以外でも…このようなずれがpc,ipad版含め非常に多い。全て再確認せよ」）。

  拾うもの（1画面につき 0 件でなければ ×）：
    横はみ出し   … ページが窓より横に広い（横スクロールが出る）
    窓の外       … 見えている部品が窓の右か左の外に出ている（横に流す入れ物の中は除く）
    親からはみ出し … flex／grid の子が親の箱から 2px 以上出ている（最小 44px の札が 38px の溝から出る、など）
    重なり       … 同じ親の兄弟どうしが 3px 以上重なっている（絶対位置の部品と負の余白は除く）
    小さい       … 電話の幅で、押せる部品が 36px より小さい

  幅：390（iPhone 15/16）・430（16 Plus）・768（iPad）・1024（PC の細い窓）・1280・1600
  画面：講師 wt01 ＝ 今日やること・宿題チェック・成績・導入と進度・導入の段階・教材・メッセージ、生徒（中3R の ためしの生徒）＝ 今日・提出・毎日テスト・過去問・先生から・保護者の方へ・設定
  写し：作業の場所/shots15/<役>-<画面>-<幅>.png
"""
import json, os, sys, time
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check")
from cdp import Chrome
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots15"; os.makedirs(OUT, exist_ok=True)
ok = ng = 0
def check(name, cond, detail=""):
    global ok, ng
    if cond: ok += 1; print("  OK   " + name)
    else: ng += 1; print("  ×    %s  %s" % (name, detail))
def click(c, sel): return c.eval("(function(){var b=document.querySelector(%s); if(b){b.click(); return true;} return false;})()" % json.dumps(sel))

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
def enter_ui(c, lid):
    c.goto(BASE + "/demo", wait=0.8); c.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');")
    c.goto("about:blank", wait=0.2); c.goto(BASE + "/demo", wait=1.0)
    assert c.wait_for("!!document.querySelector('#demoOpen')", 20), "demoOpen " + lid
    click(c, "#demoOpen"); time.sleep(0.8)
    assert click(c, '[data-demoid=%s]' % json.dumps(lid)), "no card " + lid
    assert c.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)')", 40), "enter " + lid
    time.sleep(1.5)

SCAN = r"""JSON.stringify((function(){
  var W = innerWidth, out = [];
  function vis(el){ var cs = getComputedStyle(el); if(cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) return false;
    var r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; }
  function path(el){ var p = []; while(el && el !== document.body && p.length < 4){
      var cl = (typeof el.className === 'string' && el.className.trim()) ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
      p.unshift(el.tagName.toLowerCase() + cl); el = el.parentElement; } return p.join(' > '); }
  function inScroller(el){ var a = el.parentElement; while(a && a !== document.body){ var o = getComputedStyle(a); if(/auto|scroll/.test(o.overflowX + o.overflow)) return true; a = a.parentElement; } return false; }
  if(document.documentElement.scrollWidth > W + 1) out.push({k:'横はみ出し', w:document.documentElement.scrollWidth, win:W});
  var all = [].slice.call(document.querySelectorAll('#main *, header *, #foot *')).filter(function(el){ return !el.closest('svg'); });   /* svg の中の線や丸は絵（重なって当然） */
  all.forEach(function(el){
    if(!vis(el)) return;
    var cs = getComputedStyle(el), r = el.getBoundingClientRect();
    if(cs.position === 'fixed' || cs.position === 'absolute') return;
    if((r.right > W + 1 || r.left < -1) && !inScroller(el)) out.push({k:'窓の外', p:path(el), l:Math.round(r.left), r:Math.round(r.right)});
    var par = el.parentElement; if(!par) return;
    var pc = getComputedStyle(par);
    if(/flex|grid/.test(pc.display) && pc.display !== 'contents' && !/auto|scroll|hidden/.test(pc.overflow + pc.overflowX + pc.overflowY)){
      var pr = par.getBoundingClientRect();
      var ox = Math.max(pr.left - r.left, r.right - pr.right), oy = Math.max(pr.top - r.top, r.bottom - pr.bottom);
      if(ox > 1.5 || oy > 1.5) out.push({k:'親からはみ出し', p:path(el), x:Math.round(Math.max(0, ox)), y:Math.round(Math.max(0, oy))});
    }
  });
  var seen = {};
  all.forEach(function(el){
    var par = el.parentElement; if(!par || seen[par.__k]) return;
    par.__k = par.__k || Math.random(); seen[par.__k] = 1;
    var kids = [].slice.call(par.children).filter(function(k){ if(!vis(k)) return false; var cs = getComputedStyle(k);
      return (cs.position === 'static' || cs.position === 'relative') && !(parseFloat(cs.marginLeft) < 0 || parseFloat(cs.marginTop) < 0 || parseFloat(cs.marginRight) < 0 || parseFloat(cs.marginBottom) < 0); });
    for(var i = 0; i < kids.length; i++) for(var j = i + 1; j < kids.length; j++){
      var a = kids[i].getBoundingClientRect(), b = kids[j].getBoundingClientRect();
      var ix = Math.min(a.right, b.right) - Math.max(a.left, b.left), iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if(ix > 2.5 && iy > 2.5) out.push({k:'重なり', p:path(kids[i]), q:path(kids[j]), x:Math.round(ix), y:Math.round(iy)});
    }
  });
  if(W < 700) [].slice.call(document.querySelectorAll('#main button, #main a, #main input, #main select, #foot button')).forEach(function(b){
    if(!vis(b)) return; var r = b.getBoundingClientRect(); if(r.height < 36 || r.width < 36) out.push({k:'小さい', p:path(b), w:Math.round(r.width), h:Math.round(r.height)}); });
  return out;
})())"""

def scan(c, tag, w):
    # 数字の増える動き・ふわっと出る動きの途中は測らない（動きを止め、少し待つ）
    c.eval("(function(){ if(!document.getElementById('zureNoAnim')){ var s=document.createElement('style'); s.id='zureNoAnim'; s.textContent='*,*::before,*::after{animation:none !important; transition:none !important}'; document.head.appendChild(s); } })()")
    time.sleep(1.4)
    found = json.loads(c.eval(SCAN))
    c.shot(os.path.join(OUT, "%s-%d.png" % (tag, w)))
    # 同じ種類・同じ場所は 1 件に
    uniq = {}; [uniq.setdefault((f["k"], f.get("p"), f.get("q")), f) for f in found]
    items = list(uniq.values())
    check("%s（%dpx）にずれが無い" % (tag, w), not items, "%d件 " % len(items) + json.dumps(items[:6], ensure_ascii=False))
    return items

TEACHER = [("hw", "講師-今日やること"), ("roster", "講師-成績"), ("progress", "講師-導入と進度"), ("apps", "講師-導入の段階"), ("mats", "講師-教材"), ("msgs", "講師-メッセージ")]
STUDENT = [("today", "生徒-今日"), ("homework", "生徒-提出"), ("daily", "生徒-毎日テスト"), ("kakomon", "生徒-過去問"), ("record", "生徒-先生から"), ("parent", "生徒-保護者の方へ"), ("settings", "生徒-設定")]
WIDTHS = ((390, 844, True), (430, 932, True), (768, 1024, False), (1024, 768, False), (1280, 900, False), (1600, 900, False))
total = []
for i, (w, h, mob) in enumerate(WIDTHS):
    with Chrome(width=w, height=h, scale=1, mobile=mob, port=9351 + i) as c:
        enter_ui(c, "wt01")
        for v, tag in TEACHER:
            c.eval("TubeUI.go(%s)" % json.dumps(v)); time.sleep(1.6)
            total += scan(c, tag, w)
            if v == "hw":
                # 宿題チェック（最初の札を押す）と、時間割の下まで
                if click(c, "[data-dkcheck]"):
                    c.wait_for("!!document.querySelector('.dk-view')", 15); time.sleep(1.2)
                    total += scan(c, "講師-宿題チェック", w)
                    c.eval("TubeUI.go('hw')"); time.sleep(1.2)
        enter_ui(c, pick_lid("j3r"))
        for v, tag in STUDENT:
            c.eval("TubeUI.go(%s)" % json.dumps(v)); time.sleep(1.6)
            total += scan(c, tag, w)
kinds = {}
for f in total: kinds[f["k"]] = kinds.get(f["k"], 0) + 1
print("  種類ごと: " + json.dumps(kinds, ensure_ascii=False))
print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng else "通っていないものがある", ok, ng))
