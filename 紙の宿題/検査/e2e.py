#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紙の宿題を、画面から一通り動かして確かめる（Chrome を裏で動かす。相手は手元の tubestudy のデモ）。

    sh 紙の宿題/検査/デモ.sh start       # 先に。tubestudy のデモ 8935・中継 8941
    python3 紙の宿題/検査/e2e.py

確かめること（画面の目的から決めた不変条件）
  取り込む
    ・表紙の印の次のページから、次の表紙の前までが、その生徒の紙になる。表紙は送らない
    ・印より前のページは「だれ？」（推測で誰かに付けない）。この回にいない生徒の印は送らない
    ・白紙は外す。同じページの二度撮りは印を付けるだけ（黙って消さない）
    ・生徒が自分で出した写真は、既定では上書きしない。置き換えるときは前のものを端末に控える
    ・送ったあと tubestudy の枚数と合う（講師の取り込みとして入る）
  採点する
    ・赤と◯✕を入れて 4 を押す → 赤の入った答案が返り、評価 4 とひとことが付き、次の子へ進む
    ・「前に戻す」で評価が前に戻る
    ・キー 5 で評価だけ（赤が無ければ返さない）
  答案用紙
    ・順番ばらばら・1枚は逆さでも、生徒ごとに入る。刷った名前の欄は白で消えて届く
    ・問題ごとに ✕ を付け、残りは◯ → 点数を見て 5 を押す → 返る・評価が付く
  名前
    ・この端末で入れた名前は、tubestudy のどのファイルにも、中継のログにも出ない
"""
import base64
import glob
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(HERE, "作業.nosync")
os.makedirs(os.path.join(W, "tmp"), exist_ok=True)
os.makedirs(os.path.join(W, "shots"), exist_ok=True)
os.environ["TMPDIR"] = os.path.join(W, "tmp")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(W, "tube", "server"))
from cdp import Chrome  # noqa: E402
import pdfout  # noqa: E402

RELAY = "http://127.0.0.1:8941"
TUBE = "http://127.0.0.1:8935"
ROOT = os.path.join(W, "demo")
NAME = "テスト花子"
ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   %s" % name)
    else:
        ng_n += 1
        print("  ×    %s  %s" % (name, str(detail)[:400]))


def slogin(login_id, password):
    """入る（合言葉そのものは送らない。tubestudy の server/scram.py の手順）。返事の dict を返す。"""
    import scram
    st, d = scram.login(TUBE, login_id, password)
    return d


def api(method, path, body=None, tok=None):
    r = urllib.request.Request(TUBE + path, data=json.dumps(body).encode() if body is not None else None, method=method)
    if tok:
        r.add_header("Authorization", "Bearer " + tok)
    if body is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=30) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as e:
        return {"_status": e.code, "_body": e.read().decode("utf-8", "replace")}


def accounts():
    return json.load(open(os.path.join(ROOT, "demo-accounts.json"), encoding="utf-8"))


def set_files(c, selector, paths):
    doc = c.ws.call("DOM.getDocument", {"depth": 1})
    node = c.ws.call("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": selector})
    c.ws.call("DOM.setFileInputFiles", {"nodeId": node["nodeId"], "files": paths})


def shot(c, name):
    try:
        c.shot(os.path.join(W, "shots", name + ".png"))
    except Exception:
        pass


GEN = r"""
window.__gen = function(){
  var W = 1240, H = 1754;
  function cv(){ var c = document.createElement('canvas'); c.width = W; c.height = H; return c; }
  function jpg(c){ return c.toDataURL('image/jpeg', .88).split(',')[1]; }
  function code(x, sid, px, py, s){
    var m = PaperCode.matrix({type:1, sid:sid}), k = s / 15;
    x.fillStyle = '#fff'; x.fillRect(px - 40, py - 40, s + 80, s + 80);
    x.fillStyle = '#000';
    for(var r = 0; r < 13; r++) for(var q = 0; q < 13; q++) if(m[r][q]) x.fillRect(px + (q + 1) * k, py + (r + 1) * k, Math.ceil(k), Math.ceil(k));
  }
  var seed = 7; function rnd(){ seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
  return {
    cover: function(sid, tint){
      var c = cv(), x = c.getContext('2d');
      x.fillStyle = tint || '#9CC3E6'; x.fillRect(0, 0, W, H);
      x.fillStyle = '#123'; x.font = '120px sans-serif'; x.fillText('山田', 420, 900);
      code(x, sid, 880, 140, 230);
      return jpg(c);
    },
    page: function(n){
      var c = cv(), x = c.getContext('2d');
      x.fillStyle = '#FBFAF4'; x.fillRect(0, 0, W, H);
      x.strokeStyle = '#B7CBE3'; x.lineWidth = 2;
      for(var y = 160; y < H - 80; y += 56){ x.beginPath(); x.moveTo(60, y); x.lineTo(W - 60, y); x.stroke(); }
      x.strokeStyle = '#333'; x.lineWidth = 4;
      for(var k = 0; k < 90; k++){
        var sx = 90 + rnd() * (W - 260), sy = 170 + Math.floor(rnd() * 26) * 56;
        x.beginPath(); x.moveTo(sx, sy); x.bezierCurveTo(sx + 20, sy - 40, sx + 50, sy + 10, sx + 70 + rnd() * 40, sy - 20); x.stroke();
      }
      x.fillStyle = '#222'; x.font = '220px sans-serif'; x.fillText(String(n), 480, 1000);
      return jpg(c);
    },
    blank: function(){ var c = cv(), x = c.getContext('2d'); x.fillStyle = '#FAFAF7'; x.fillRect(0, 0, W, H); return jpg(c); }
  };
};
"""


def build_pdf(name, jpegs):
    p = os.path.join(W, "tmp", name)
    open(p, "wb").write(pdfout.build([("jpg", base64.b64decode(j)) for j in jpegs]))
    return p


def rows_of(tok, key, n):
    d = api("GET", "/api/check?key=%s&n=%d" % (key, n), tok=tok)
    return {r["sid"]: r for r in d.get("rows") or []}, d


def main():
    acc = {a["id"]: a for a in accounts()}
    t = slogin("lteacher1", acc["lteacher1"]["password"])
    tok = t.get("token")
    check("講師でデモに入れる（直接）", bool(tok), t)
    key = "e4b:japanese"
    now = int(time.time() * 1000)
    q1 = api("POST", "/api/quiz", {"key": key, "title": "検査の宿題（ノート）", "dueAt": now - 60000}, tok=tok)["assignment"]
    n1 = q1["lesson"]["n"]
    rows, d = rows_of(tok, key, n1)
    order = sorted(rows.values(), key=lambda r: r["label"])
    stu = slogin("le4b01", acc["le4b01"]["password"])
    s1 = stu["profile"]["sid"]
    S2, S3 = [r["sid"] for r in order if r["sid"] != s1][:2]
    other = [a for a in accounts() if a["id"] == "lj2r01"][0]
    so = slogin("lj2r01", other["password"])["profile"]["sid"]
    # 生徒 S1 が自分で写真を出しておく（置き換えない既定を確かめる）
    tiny = base64.b64encode(open(glob.glob(os.path.join(W, "tmp", "src0.jpg"))[0], "rb").read()).decode() if glob.glob(os.path.join(W, "tmp", "src0.jpg")) else None
    if not tiny:
        print("先に pdf_test.py を1回流してください（試しの写真を作ります）")
        return 1
    r = api("POST", "/api/submissions/%s" % rows[s1]["head"], {"files": [{"type": "image/jpeg", "b64": tiny}]}, tok=stu["token"])
    check("生徒 S1 が自分で写真を出した", r.get("ok"), r)

    with Chrome(width=1366, height=1024, scale=1) as c:
        c.goto(RELAY + "/", wait=1.5)
        c.eval("document.getElementById('lid').value='lteacher1';document.getElementById('lpw').value='%s';document.getElementById('lgo').click();"
               % acc["lteacher1"]["password"])
        check("画面から講師で入れる", c.wait_for("document.querySelector('h1') && document.querySelector('h1').textContent==='今日やること'", 20))
        check("ホームに取り込む・採点するがある", c.eval("document.querySelectorAll('.act').length") == 2)
        c.eval("Paper.names.map['%s']='%s'; Paper.names.save();" % (S2, NAME))
        c.eval(GEN)
        g = c.eval("""(function(){ var G = __gen(); return {
            stray:G.page(90), c1:G.cover('%s'), p1:G.page(11), c2:G.cover('%s', '#E6B8B8'), p2a:G.page(21), p2b:G.page(22), bl:G.blank(),
            c3:G.cover('%s', '#C9E6B8'), p3:G.page(31), co:G.cover('%s', '#DDD'), po:G.page(41)}; })()""" % (s1, S2, S3, so))
        pdf1 = build_pdf("scan-notebooks.pdf", [g["stray"], g["c1"], g["p1"], g["c2"], g["p2a"], g["p2b"], g["bl"], g["c3"], g["p3"], g["p3"], g["co"], g["po"]])

        print("\n取り込む（ノート 12ページ）")
        c.eval("Paper.show('intake', {key:'%s'})" % key)
        check("回の一覧に、いま作った回が出る", c.wait_for("!!document.querySelector('.lrow[data-n=\"%d\"]')" % n1, 20))
        c.eval("document.querySelector('.lrow[data-n=\"%d\"]').click()" % n1)
        check("PDF を選ぶ画面", c.wait_for("!!document.getElementById('files')", 20))
        set_files(c, "#files", [pdf1])
        check("確かめる画面になる", c.wait_for("!!document.querySelector('.sumline')", 120))
        shot(c, "1-review")
        s = c.eval("document.querySelector('.sumline .big').textContent")
        check("送るのは S2（2ページ）と S3（2ページ）＝2人に4ページ（S1 は生徒の写真があるので送らない）", s == "2人に 4ページ", s)
        check("印より前のページは「だれ？」", c.eval("!!document.querySelector('.rrow.who') && document.querySelector('.rrow.who').textContent.indexOf('だれ？')>=0"))
        check("この回にいない生徒の印は、別に分けて送らない", c.eval("document.body.textContent.indexOf('この回にいない生徒の印')>=0"))
        check("白紙は外す", c.eval("document.body.textContent.indexOf('外したページ（白紙・外したもの）1')>=0"))
        check("二度撮りに印（黙って消さない）", c.eval("document.querySelectorAll('.th .tag.y').length") == 1)
        check("表紙は「送らない」と出る", c.eval("document.querySelectorAll('.th.cover').length") >= 3)
        check("名前は画面にだけ出る", c.eval("document.body.textContent.indexOf('%s')>=0" % NAME))
        # だれ？の1枚を S2 にする
        c.eval("document.querySelector('.rrow.who .th').click()")
        c.wait_for("!!document.querySelector('[data-a=\"who\"]')", 10)
        c.eval("document.querySelector('[data-a=\"who\"]').click()")
        c.wait_for("!!document.querySelector('#whoList [data-sid=\"%s\"]')" % S2, 10)
        c.eval("document.querySelector('#whoList [data-sid=\"%s\"]').click()" % S2)
        check("だれ？の1枚を手で S2 にすると 2人に5ページ", c.wait_for("document.querySelector('.sumline .big') && document.querySelector('.sumline .big').textContent==='2人に 5ページ'", 15),
              c.eval("document.querySelector('.sumline .big') && document.querySelector('.sumline .big').textContent"))
        c.eval("document.querySelector('[data-replace=\"%s\"]').click()" % s1)
        check("S1 を置き換えると 3人に6ページ", c.wait_for("document.querySelector('.sumline .big').textContent==='3人に 6ページ'", 15))
        c.eval("document.getElementById('send').click()")
        check("送り終わる", c.wait_for("document.querySelector('h1') && /送りました|送れなかった/.test(document.querySelector('h1').textContent)", 120))
        shot(c, "2-sent")
        check("tubestudy から読み直して枚数が合った", c.eval("document.body.textContent.indexOf('全員の枚数が合っていることを確かめました')>=0"),
              c.eval("document.querySelector('.card').textContent"))
        rows, d = rows_of(tok, key, n1)
        check("S1：講師の取り込み1枚（生徒の写真を置き換えた）", len(rows[s1]["files"]) == 1 and rows[s1]["origin"] == "teacher", rows[s1])
        check("S2：3枚", len(rows[S2]["files"]) == 3 and rows[S2]["origin"] == "teacher", rows[S2]["files"])
        check("S3：2枚（二度撮りも講師が外さなければ送る）", len(rows[S3]["files"]) == 2, rows[S3]["files"])
        others = [r for sid, r in rows.items() if sid not in (s1, S2, S3) and r["files"]]
        check("ほかの生徒には何も入らない", not others, [r["label"] for r in others])
        hist = c.eval("Paper.store.all('history').then(function(h){ return h.map(function(x){ return [x.kind, x.sid, x.files.length]; }); })", wait_promise=True)
        check("置き換える前の生徒の写真を、端末に控えた", ["scan", s1, 1] in hist, hist)

        print("\n控えから戻す")
        c.eval("window.confirm = function(){ return true; }; Paper.show('history')")
        check("控えの一覧に S1 の写真がある", c.wait_for("document.querySelectorAll('[data-back]').length>=1 && document.body.textContent.indexOf('生徒が出した写真 1枚')>=0", 20))
        c.eval("document.querySelector('[data-back]').click()")
        time.sleep(3)
        rows, d = rows_of(tok, key, n1)
        size = c.eval("Paper.api.image('%s', '%s', '%s').then(function(b){ return b.size; })" % (rows[s1]["head"], s1, rows[s1]["files"][0]), wait_promise=True)
        orig = len(open(os.path.join(W, "tmp", "src0.jpg"), "rb").read())
        check("S1 の写真が、生徒の出したものに戻る（同じバイト数）", len(rows[s1]["files"]) == 1 and size == orig, (size, orig))
        check("戻した控えは一覧から消える", c.wait_for("document.body.textContent.indexOf('控えはありません')>=0 || document.querySelectorAll('[data-back]').length===0", 10))

        print("\n採点する")
        c.eval("Paper.show('grade', {key:'%s', n:%d})" % (key, n1))
        check("答案が出る", c.wait_for("!!document.querySelector('#stage canvas') && Paper.grade.state().pages.length>0", 30))
        cur = c.eval("Paper.grade.state().rows[Paper.grade.state().i].sid")
        check("最初は、まだ評価の無い出した子（名前の順で最初）", cur in (s1, S2, S3), cur)
        c.eval("Paper.grade.go(Paper.grade.state().i)")
        c.wait_for("Paper.grade.state().pages.length>0", 20)
        c.eval("""(function(){ var G = Paper.grade.state(), pg = G.pages[G.page];
            G.items[pg.key] = [{t:'pen', c:'#D0021B', w:6, p:[[100,200],[400,260],[700,240]]},
                               {t:'stamp', k:'maru', x:300, y:400, s:60}, {t:'stamp', k:'maru', x:300, y:600, s:60},
                               {t:'stamp', k:'batsu', x:300, y:800, s:60}];
            document.getElementById('note').value = 'よくできました'; })()""")
        tally = c.eval("(function(){ var G = Paper.grade.state(); var n=0; Object.keys(G.items).forEach(function(k){ n += G.items[k].length; }); return n; })()")
        check("赤とスタンプが入った", tally == 4, tally)
        c.eval("Paper.grade.rate(4)")
        check("4 を押すと次の子へ進む", c.wait_for("Paper.grade.state().rows[Paper.grade.state().i].sid !== '%s'" % cur, 60))
        rows, d = rows_of(tok, key, n1)
        r0 = rows[cur]
        check("tubestudy：評価 4・ひとこと・返した答案", r0["v"] == 4 and r0["note"] == "よくできました" and len(r0["returned"]) >= 1, r0)
        red = c.eval("""(async function(){
            var b = await Paper.api.image('%s', '%s', '%s'), cv = await Paper.img.blobToCanvas(b);
            var d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data, n = 0;
            for(var i = 0; i < d.length; i += 16) if(d[i] > 170 && d[i+1] < 80 && d[i+2] < 80) n++;
            return n; })()""" % (r0["head"], cur, r0["returned"][0]), wait_promise=True)
        check("返した答案に赤が焼き込まれている", red > 200, red)
        # 前に戻す
        c.eval("window.confirm = function(){ return true; }")
        idx = c.eval("Paper.grade.state().rows.findIndex(function(r){ return r.sid==='%s'; })" % cur)
        c.eval("Paper.grade.go(%d)" % idx)
        c.wait_for("!document.getElementById('back').hidden", 20)
        c.eval("document.getElementById('back').click()")
        time.sleep(3)
        rows, d = rows_of(tok, key, n1)
        check("前に戻すと、評価が前（なし）に戻る", rows[cur]["v"] in (None, 0), rows[cur]["v"])
        # キー 5：評価だけ（赤を入れていない子へ移ってから）
        nxt = S3 if cur != S3 else S2
        c.eval("Paper.grade.go(Paper.grade.state().rows.findIndex(function(r){ return r.sid==='%s'; }))" % nxt)
        c.wait_for("Paper.grade.state().rows[Paper.grade.state().i].sid==='%s' && Paper.grade.state().pages.length>0" % nxt, 20)
        time.sleep(0.5)
        c.eval("document.dispatchEvent(new KeyboardEvent('keydown', {key:'5'}))")
        time.sleep(3)
        rows, d = rows_of(tok, key, n1)
        check("キー 5 で評価だけ付く（赤が無いので返さない）", rows[nxt]["v"] == 5 and not rows[nxt]["returned"], (rows[nxt]["v"], rows[nxt]["returned"]))
        shot(c, "3-grade")

        print("\n答案用紙（問題ごと）")
        q2 = api("POST", "/api/quiz", {"key": key, "title": "漢字テスト（検査）", "dueAt": now - 30000}, tok=tok)["assignment"]
        n2 = q2["lesson"]["n"]
        trio = [s1, S2, S3]
        rows2, d2 = rows_of(tok, key, n2)
        tmpl = c.eval("Paper.sheets.tmplOf(1, 0)")
        html = c.eval("(function(){ var hd = {course:'小4β 国語', title:'漢字テスト', date:'2026/09/24'}; return %s.map(function(s){"
                      " return Paper.sheets.answerSheet({sid:s, label:'小4β'}, Paper.names.of(s), hd, %d, 0); }).join(''); })()" % (json.dumps(trio), tmpl))
        c.eval("document.getElementById('print').innerHTML = %s" % json.dumps(html))
        c.eval("Array.prototype.forEach.call(document.querySelectorAll('#print .box'), function(b, i){ var e = document.createElement('b'); e.textContent = '答' + (i%3); e.style.cssText = 'position:absolute;left:9mm;top:4mm;font-size:16pt'; b.appendChild(e); })")
        c.ws.call("Emulation.setEmulatedMedia", {"media": "print"})
        c.ws.call("Emulation.setDeviceMetricsOverride", {"width": 794, "height": 1123, "deviceScaleFactor": 2, "mobile": False})
        time.sleep(1)
        sheets = []
        for i in range(3):
            rect = c.eval("(function(){ var r = document.querySelectorAll('#print .pg')[%d].getBoundingClientRect(); return [r.left, r.top + window.scrollY, r.width, r.height]; })()" % i)
            data = c.ws.call("Page.captureScreenshot", {"format": "jpeg", "quality": 90, "captureBeyondViewport": True,
                                                         "clip": {"x": rect[0], "y": rect[1], "width": rect[2], "height": rect[3], "scale": 1}})["data"]
            sheets.append(data)
        c.ws.call("Emulation.setEmulatedMedia", {"media": ""})
        c.ws.call("Emulation.setDeviceMetricsOverride", {"width": 1366, "height": 1024, "deviceScaleFactor": 1, "mobile": False})
        c.eval("document.getElementById('print').innerHTML = ''")
        # 1枚を逆さにし、順番を入れかえる（複合機に逆さに入れた紙）
        flipped = c.eval("""(async function(){
            var img = new Image(); img.src = 'data:image/jpeg;base64,%s'; await img.decode();
            var cv = document.createElement('canvas'); cv.width = img.width; cv.height = img.height;
            var x = cv.getContext('2d'); x.translate(cv.width, cv.height); x.rotate(Math.PI); x.drawImage(img, 0, 0);
            return cv.toDataURL('image/jpeg', .9).split(',')[1]; })()""" % sheets[1], wait_promise=True)
        pdf2 = build_pdf("scan-sheets.pdf", [sheets[2], flipped, sheets[0]])
        c.eval("Paper.show('intake', {key:'%s'})" % key)
        c.wait_for("!!document.querySelector('.lrow[data-n=\"%d\"]')" % n2, 20)
        c.eval("document.querySelector('.lrow[data-n=\"%d\"]').click()" % n2)
        c.wait_for("!!document.getElementById('files')", 20)
        set_files(c, "#files", [pdf2])
        check("答案用紙を取り込む（順番ばらばら・1枚逆さ）", c.wait_for("!!document.querySelector('.sumline')", 120))
        s = c.eval("document.querySelector('.sumline .big').textContent")
        check("3人に3ページ", s == "3人に 3ページ", s)
        shot(c, "4-sheets")
        c.eval("document.getElementById('send').click()")
        c.wait_for("document.querySelector('h1') && /送りました|送れなかった/.test(document.querySelector('h1').textContent)", 120)
        rows2, d2 = rows_of(tok, key, n2)
        check("3人とも1枚ずつ入った", all(len(rows2[s]["files"]) == 1 for s in trio), [len(rows2[s]["files"]) for s in trio])
        white = c.eval("""(async function(){
            var b = await Paper.api.image('%s', '%s', '%s'), cv = await Paper.img.blobToCanvas(b);
            var geo = Paper.sheets.readSheet(cv), NB = Paper.sheets.NAMEBOX;
            var p0 = geo.px(NB.x + 4, NB.y + 4), p1 = geo.px(NB.x + NB.w - 4, NB.y + NB.h - 4);
            var d = cv.getContext('2d').getImageData(p0[0], p0[1], p1[0] - p0[0], p1[1] - p0[1]).data, dark = 0, n = 0;
            for(var i = 0; i < d.length; i += 4){ n++; if(d[i] < 150) dark++; }
            return {dark: dark / n, how: geo.how}; })()""" % (rows2[S2]["head"], S2, rows2[S2]["files"][0]), wait_promise=True)
        check("刷った名前の欄は白で消えて届く", white["dark"] < 0.002, white)
        check("逆さの紙も、四隅の目印で読める", white["how"] == "marks", white)
        c.eval("Paper.show('byq', {key:'%s', n:%d, name:'小4β 国語'})" % (key, n2))
        check("問題ごとの画面（3人ぶんの枠）", c.wait_for("document.querySelectorAll('.qgrid .qt').length===3", 60),
              c.eval("document.querySelector('#main').textContent.slice(0,200)"))
        shot(c, "5-byq")
        c.eval("document.querySelector('.qt[data-sid=\"%s\"]').click()" % S2)
        check("✕ を付けると残りの人数が減る", c.wait_for("/残りは◯（2人）/.test(document.getElementById('rest').textContent)", 10))
        for q in range(1, 11):
            c.wait_for("document.getElementById('rest') && document.querySelector('h1').textContent.indexOf('第%d問')>=0 && document.querySelectorAll('.qgrid .qt').length===3" % q, 30)
            c.eval("document.getElementById('rest').click()")
        check("最後に点数の一覧", c.wait_for("document.body.textContent.indexOf('点数を見て返す')>=0 && document.querySelectorAll('[data-v]').length===15", 20))
        sc = c.eval("Array.prototype.map.call(document.querySelectorAll('.lrow'), function(r){ return r.querySelector('.i').textContent; })")
        check("S2 は 9 / 10、ほかは 10 / 10", sorted(x.split("　")[0] for x in sc) == ["10 / 10", "10 / 10", "9 / 10"], sc)
        c.eval("document.querySelector('[data-v=\"5\"][data-sid=\"%s\"]').click()" % S2)
        time.sleep(4)
        rows2, d2 = rows_of(tok, key, n2)
        check("5 を押すと、評価 5・点数のひとこと・返した答案", rows2[S2]["v"] == 5 and rows2[S2]["note"] == "9 / 10" and rows2[S2]["returned"], rows2[S2])
        shot(c, "6-byq-sum")

        print("\n赤を入れた紙として返す・1人8ページ・返した答案を刷る")
        q3 = api("POST", "/api/quiz", {"key": key, "title": "検査の宿題（赤は紙）", "dueAt": now - 20000}, tok=tok)["assignment"]
        n3 = q3["lesson"]["n"]
        g4 = c.eval("(function(){ var G = __gen(), out = [G.cover('%s', '#E6B8B8'), G.page(51), G.cover('%s', '#C9E6B8')];"
                    " for(var i = 0; i < 8; i++) out.push(G.page(60 + i)); return out; })()" % (S2, S3))
        pdf4 = build_pdf("scan-marked.pdf", g4)
        c.eval("Paper.show('intake', {key:'%s'})" % key)
        c.wait_for("!!document.querySelector('.lrow[data-n=\"%d\"]')" % n3, 20)
        c.eval("document.querySelector('.lrow[data-n=\"%d\"]').click()" % n3)
        c.wait_for("!!document.getElementById('files')", 20)
        set_files(c, "#files", [pdf4])
        c.wait_for("!!document.querySelector('.sumline')", 120)
        check("2人に9ページ", c.eval("document.querySelector('.sumline .big').textContent") == "2人に 9ページ", c.eval("document.querySelector('.sumline .big').textContent"))
        c.eval("document.getElementById('marked').click()")
        check("「赤を入れた紙として返す」に切り替わる", c.wait_for("document.getElementById('marked') && document.getElementById('marked').textContent==='赤を入れた紙として返す'", 10))
        c.eval("document.getElementById('send').click()")
        c.wait_for("document.querySelector('h1') && /送りました|送れなかった/.test(document.querySelector('h1').textContent)", 120)
        rows3, d3 = rows_of(tok, key, n3)
        check("S2：出された紙1枚と、返した答案1枚（同じもの）", len(rows3[S2]["files"]) == 1 and len(rows3[S2]["returned"]) == 1, (rows3[S2]["files"], rows3[S2]["returned"]))
        check("S3：8ページは2枚ずつ並べて4枚（tubestudy の上限6枚に収める）", len(rows3[S3]["files"]) == 4 and len(rows3[S3]["returned"]) == 4, (rows3[S3]["files"], rows3[S3]["returned"]))
        check("枚数が合ったと言う", c.eval("document.body.textContent.indexOf('全員の枚数が合っていることを確かめました')>=0"))
        c.eval("window.print = function(){ window.__printed = (window.__printed || 0) + 1; }")
        c.eval("Paper.show('grade', {key:'%s', n:%d})" % (key, n3))
        c.wait_for("!!document.getElementById('printRet')", 30)
        c.eval("document.getElementById('printRet').click()")
        check("返した答案を番号順に刷る（5ページ・上に番号）", c.wait_for("window.__printed===1 && document.querySelectorAll('#print .pg.ret').length===5", 60),
              c.eval("[window.__printed, document.querySelectorAll('#print .pg.ret').length]"))
        check("刷る紙には、この端末の名前が出る（紙の上だけ）", c.eval("document.getElementById('print').textContent.indexOf('%s')>=0" % NAME))
        c.eval("document.getElementById('print').innerHTML=''")

        print("\nクラス替えのあとも番号シールが効く（move は tubestudy の命令。デモの写しにだけ当てる）")
        mv = os.path.join(W, "tmp", "move.csv")
        s3id = [a for a in json.load(open(os.path.join(ROOT, "schools", "london", "accounts.json"), encoding="utf-8")).items()
                if a[1].get("sid") == S3][0][0]
        open(mv, "w", encoding="utf-8").write("id,classId,seat\n%s,e4a,90\n" % s3id)
        env = dict(os.environ, MYACADY_ROOT=ROOT, PYTHONDONTWRITEBYTECODE="1")
        out = subprocess.run([sys.executable, os.path.join(W, "tube", "server", "tube_server.py"), "move", mv, "--school", "london", "--yes"],
                             capture_output=True, text=True, env=env)
        check("tubestudy の move で S3 を 小4α-90 へ", "移しました" in out.stdout, out.stdout[-300:] + out.stderr[-300:])
        g3 = c.eval("(function(){ var G = __gen(); return [G.cover('%s', '#C9E6B8'), G.page(77)]; })()" % S3)
        pdf3 = build_pdf("scan-after-move.pdf", g3)
        c.eval("Paper.show('intake', {key:'%s'})" % key)
        c.wait_for("!!document.querySelector('.lrow[data-n=\"%d\"]')" % n1, 20)
        c.eval("document.querySelector('.lrow[data-n=\"%d\"]').click()" % n1)
        c.wait_for("!!document.getElementById('files')", 20)
        set_files(c, "#files", [pdf3])
        c.wait_for("!!document.querySelector('.sumline')", 60)
        txt = c.eval("document.querySelector('.rrows').textContent")
        check("同じシール（sid）で S3 の行に入り、番号は今の 小4α-90 で出る", "小4α-90" in txt and "前に取り込んだ紙" in txt, txt[:300])
        check("前に取り込んだ紙があるので、既定では送らない（0人）", c.eval("document.querySelector('.sumline .big').textContent") == "0人に 0ページ",
              c.eval("document.querySelector('.sumline .big').textContent"))
        c.eval("window.confirm = function(){ return true; }; document.getElementById('quit').click()")
        out = subprocess.run([sys.executable, os.path.join(W, "tube", "server", "tube_server.py"), "move", "--list", "--school", "london"],
                             capture_output=True, text=True, env=env)
        batch = out.stdout.split()[0] if out.stdout.strip() else ""
        out = subprocess.run([sys.executable, os.path.join(W, "tube", "server", "tube_server.py"), "move", "--undo", batch, "--school", "london", "--yes"],
                             capture_output=True, text=True, env=env)
        check("move --undo で戻せる", "取り消しました" in out.stdout, out.stdout[-300:])

    print("\n名前")
    hits = []
    for base, dirs, files in os.walk(ROOT):
        for f in files:
            if f.endswith((".json", ".log")):
                p = os.path.join(base, f)
                try:
                    if NAME in open(p, encoding="utf-8", errors="ignore").read():
                        hits.append(p)
                except OSError:
                    pass
    check("この端末で入れた名前は tubestudy のどのファイルにも無い", not hits, hits)
    rl = open(os.path.join(W, "relay.log"), encoding="utf-8", errors="ignore").read()
    check("中継のログにも無い（口の名前と番号だけ）", NAME not in rl and S2 not in rl, rl[-300:])
    print("\n%s。（%d件）" % ("すべて通った" if not ng_n else "× %d件" % ng_n, ok_n + ng_n))
    return 1 if ng_n else 0


if __name__ == "__main__":
    sys.exit(main())
