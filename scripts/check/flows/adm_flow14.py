# -*- coding: utf-8 -*-
"""⑧ 講師の今日やること：札の密度と余った札の広がり（2026-10-11 本人「宿題チェック4段は多い。4段以上になりそうな場合は、
横長画面の場合に各教科を今のカードの半分にして、3段以内に収まるようにせよ。スマホ版は多い場合に2列にして長くなりすぎないように。
スマホ,ipad,pcほそウィンドウ,pc全画面のしっかり全てを確認せよ」「最後の1つが余ったとき、適切に横に広がるいつも通りの設定にせよ。
普遍的にプログラムすること」）。

  wt01 で入り、今日やることの札の塊（.t-cards）の枚数を DOM の上で増減して（複製・削除。JS が付ける n3/n6/n9 も同じ決まりで付ける）、
  幅ごとに 列の数・段の数・1枚の高さ・余った札が行を埋めるか・輪の札が同じ行で同じ高さか を測る。CSS の決まりそのものの検査。

    電話 430       … 3枚まで1列、4枚以上は2列の小さな札（130px 以下）。奇数なら最後の1枚が2列ぶんに広がる。輪の札は上
    iPad 768       … 6枚まで2列、7枚以上は3列の小さな札。余りは行を埋める
    PC の細い窓 1024・1280 … 6枚まで2列（輪の札と同じ行・同じ高さ）、7〜9枚は3列、10枚以上は4列で3段以内（細い窓では輪の札を上に）
    PC 全画面 1600 … 7枚以上は4列、3段以内。余りは行を埋める
"""
import json, os, sys, time
S = sys.argv[1]
sys.path.insert(0, S + "/tube/scripts/check")
from cdp import Chrome
BASE = "http://127.0.0.1:8949"; OUT = S + "/shots14"; os.makedirs(OUT, exist_ok=True)
ok = ng = 0
def check(name, cond, detail=""):
    global ok, ng
    if cond: ok += 1; print("  OK   " + name)
    else: ng += 1; print("  ×    %s  %s" % (name, detail))
def click(c, sel): return c.eval("(function(){var b=document.querySelector(%s); if(b){b.click(); return true;} return false;})()" % json.dumps(sel))
def enter_ui(c, lid):
    c.goto(BASE + "/demo", wait=0.8); c.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');")
    c.goto("about:blank", wait=0.2); c.goto(BASE + "/demo", wait=1.0)
    assert c.wait_for("!!document.querySelector('#demoOpen')", 20), "demoOpen " + lid
    click(c, "#demoOpen"); time.sleep(0.8)
    assert click(c, '[data-demoid=%s]' % json.dumps(lid)), "no card " + lid
    assert c.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)')", 40), "enter " + lid
    time.sleep(1.5)
# 枚数を n にする（足りなければ複製、多ければ末尾を消す）。塊の印は ui-desk.js の todayCard と同じ決まり（tiles > 3 / 6 / 9）
SET = """(function(n){ var k=document.querySelector('.t-cards'); var cs=[].slice.call(k.querySelectorAll('.t-check'));
  while(k.querySelectorAll('.t-check').length < n){ k.appendChild(cs[k.querySelectorAll('.t-check').length %% cs.length].cloneNode(true)); }
  while(k.querySelectorAll('.t-check').length > n){ k.removeChild(k.lastElementChild); }
  k.className = 't-cards' + (n>3?' n3':'') + (n>6?' n6':'') + (n>9?' n9':''); return k.className; })(%d)"""
MEAS = """JSON.stringify((function(){ var cs=[].slice.call(document.querySelectorAll('.t-cards > .t-check')); var tops={};
  cs.forEach(function(c){ tops[Math.round(c.getBoundingClientRect().top)]=1; });
  var h=document.querySelector('.t-hero').getBoundingClientRect(), k=document.querySelector('.t-cards').getBoundingClientRect();
  var top0=cs.length?Math.round(cs[0].getBoundingClientRect().top):0, cols=cs.filter(function(c){ return Math.round(c.getBoundingClientRect().top)===top0; }).length;
  var last=cs.length?cs[cs.length-1].getBoundingClientRect():k; var hs=cs.map(function(c){ return Math.round(c.getBoundingClientRect().height); });
  /* 短い名前（「中3R 数学」など 8 字まで）が切れていたら ×。長い名前（「中3R キャッチアップ講座」）は省略記号で切れてよい */
  var clipped=cs.filter(function(c){ var t=c.querySelector('.t-cktx'); return t && t.textContent.length <= 8 && t.scrollWidth > t.clientWidth + 1; }).length;
  return {n:cs.length, rows:Object.keys(tops).length, cols:cols, cardH:Math.max.apply(null, hs), heroH:Math.round(h.height), cardsH:Math.round(k.height),
          sameRow:Math.abs(h.top-k.top)<2, fills:Math.abs(last.right-k.right)<2, clipped:clipped}; })())"""
def measure(c, n):
    c.eval(SET % n); time.sleep(0.3); c.eval("document.querySelector('.t-cards').scrollIntoView({block:'start'})"); time.sleep(0.2)
    d = json.loads(c.eval(MEAS)); assert d["n"] == n, (n, d); return d
def shot(c, name): c.shot(os.path.join(OUT, name + ".png"))

with Chrome(width=430, height=900, scale=2, mobile=True, port=9341) as c:
    enter_ui(c, "wt01"); c.eval("TubeUI.go('hw')"); time.sleep(2.0)
    base = json.loads(c.eval(MEAS)); check("wt01 の今日やることに 7 枚以上の札（ためしのデモ）", base["n"] >= 7, base)
    d = measure(c, 3); check("電話：3 枚は 1 列。輪の札は上", d["cols"] == 1 and d["rows"] == 3 and not d["sameRow"], d)
    d = measure(c, 5); check("電話：5 枚は 2 列の小さな札（130px 以下）、余った 1 枚は 2 列ぶんに広がる", d["cols"] == 2 and d["rows"] == 3 and d["cardH"] <= 130 and d["fills"], d); shot(c, "phone-5")
    d = measure(c, 12); check("電話：12 枚は 2 列 6 段", d["cols"] == 2 and d["rows"] == 6 and d["cardH"] <= 130, d)
with Chrome(width=768, height=1024, scale=1, port=9342) as c:
    enter_ui(c, "wt01"); c.eval("TubeUI.go('hw')"); time.sleep(2.0)
    d = measure(c, 5); check("iPad：5 枚は 2 列、余った 1 枚は行を埋める", d["cols"] == 2 and d["rows"] == 3 and d["fills"], d)
    d = measure(c, 7); check("iPad：7 枚は 3 列の小さな札（150px 以下）3 段、余った 1 枚は行を埋める", d["cols"] == 3 and d["rows"] == 3 and d["cardH"] <= 150 and d["fills"], d); shot(c, "ipad-7")
    d = measure(c, 12); check("iPad：12 枚は 3 列 4 段、短い名前は切れていない", d["cols"] == 3 and d["rows"] == 4 and d["clipped"] == 0, d)
for (w, port, tag) in ((1024, 9343, "PC の細い窓 1024"), (1280, 9344, "PC の細い窓 1280")):
    with Chrome(width=w, height=900, scale=1, port=port) as c:
        enter_ui(c, "wt01"); c.eval("TubeUI.go('hw')"); time.sleep(2.0)
        d = measure(c, 5); check(tag + "：5 枚は 2 列の大きな札、輪の札は同じ行で同じ高さ、余った 1 枚は行を埋める", d["cols"] == 2 and d["rows"] == 3 and d["sameRow"] and abs(d["heroH"] - d["cardsH"]) <= 2 and d["fills"], d)
        d = measure(c, 7); check(tag + "：7 枚は 3 列の小さな札（150px 以下）3 段以内、輪の札は同じ行で同じ高さ、余りは行を埋める", d["cols"] == 3 and d["rows"] <= 3 and d["cardH"] <= 150 and d["sameRow"] and abs(d["heroH"] - d["cardsH"]) <= 2 and d["fills"], d); shot(c, "pc%d-7" % w)
        d = measure(c, 9); check(tag + "：9 枚は 3 列 3 段", d["cols"] == 3 and d["rows"] == 3 and d["cardH"] <= 150, d)
        d = measure(c, 10); check(tag + "：10 枚は 4 列 3 段以内（輪の札は上に横長）、余りは行を埋める", d["cols"] == 4 and d["rows"] <= 3 and d["cardH"] <= 150 and not d["sameRow"] and d["fills"], d); shot(c, "pc%d-10" % w)
        d = measure(c, 12); check(tag + "：12 枚は 4 列 3 段、短い名前は切れていない", d["cols"] == 4 and d["rows"] == 3 and d["clipped"] == 0, d)
with Chrome(width=1600, height=900, scale=1, port=9345) as c:
    enter_ui(c, "wt01"); c.eval("TubeUI.go('hw')"); time.sleep(2.0)
    d = measure(c, 6); check("PC 全画面：6 枚は 2 列の大きな札 3 段、輪の札は同じ行で同じ高さ", d["cols"] == 2 and d["rows"] == 3 and d["sameRow"] and abs(d["heroH"] - d["cardsH"]) <= 2, d)
    d = measure(c, 7); check("PC 全画面：7 枚は 4 列の小さな札（150px 以下）2 段、余った 3 枚は行を埋める、輪の札は同じ行で同じ高さ", d["cols"] == 4 and d["rows"] == 2 and d["cardH"] <= 150 and d["fills"] and d["sameRow"] and abs(d["heroH"] - d["cardsH"]) <= 2, d); shot(c, "pc1600-7")
    d = measure(c, 12); check("PC 全画面：12 枚は 4 列 3 段、短い名前は切れていない", d["cols"] == 4 and d["rows"] == 3 and d["clipped"] == 0, d); shot(c, "pc1600-12")
print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng else "通っていないものがある", ok, ng))
