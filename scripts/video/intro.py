# -*- coding: utf-8 -*-
"""初回登録の「できること」の動画（45 秒）を、本物の画面の写しから作る。保護者と生徒に向けて。

    python3 scripts/video/intro.py <作業の場所> [--base http://127.0.0.1:8951] [--student wj3r03] [--out app/media] [--only phone]

  3 つの比で作る（2026-10-12 本人「縦版、横版で作り、スマホ,ipad,pcの比でそれぞれ全画面で美しく表示」）：
    phone  1080×2340（縦。iPhone）   ipad  1536×2048（縦 3:4）   pc  1920×1080（横 16:9）
  中身（本人「宿題の提出、管理がもっと簡単に。授業内小テストや過去問の提出、添削も簡単に。プライバシーも安心（個人情報を
  一切入れない）。実際の画面の操作を見せながら。音楽ももっと楽しげに」）：
    1 題   2 宿題を写真で出す（押す→出した）  3 先生から（評価・ひとこと・赤入れ）  4 テストと過去問（点数）
    5 今週・毎日テスト・記録   6 プライバシー（登録は ID と合言葉だけ）   7 おわり
  画面は Chrome（scripts/check/cdp.py）で撮る。登録コードは管理者（wadmin99）の口で作る。音は numpy で作る（明るい長調、120 BPM）。
  絵は PIL で組み、ffmpeg（imageio-ffmpeg の同梱）で H.264＋AAC に。
"""
import argparse, io, json, math, os, struct, subprocess, sys, time, urllib.request, wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "check"))
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_B = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
FONT_R = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
PAPER = (235, 231, 223)
INK = (29, 29, 31)
GREY = (110, 110, 115)
BLUE = (10, 111, 199)
GOLD = (249, 185, 0)
FPS = 30
FORMATS = {"phone": (1080, 2340, 390, 844, 3, True), "ipad": (1536, 2048, 768, 1024, 2, False), "pc": (1920, 1080, 1920, 1080, 1, False)}


def font(path, size):
    return ImageFont.truetype(path, size, index=0)


# ------------------------------------------------------------ 画面を撮る
def api(base, method, path, tok=None, body=None):
    req = urllib.request.Request(base + "/api" + path, method=method, data=(json.dumps(body).encode() if body is not None else None),
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + tok} if tok else {})})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.code}


def note_png(w=560, h=760):
    """ノートの写真らしい絵（罫線と手書き風の線）。動画の「出す」操作に使う。"""
    im = Image.new("RGB", (w, h), (251, 250, 246)); d = ImageDraw.Draw(im)
    import random
    rnd = random.Random(12)
    for y in range(60, h - 30, 34): d.line([(30, y), (w - 30, y)], fill=(205, 212, 222), width=2)
    for y in range(60, h - 60, 34):
        if rnd.random() < 0.75:
            x0 = 40 + rnd.randint(0, 120); x1 = x0 + rnd.randint(120, w - x0 - 60)
            d.line([(x0, y - 8), (x1, y - 10 + rnd.randint(-3, 3))], fill=(40, 42, 50), width=4)
    buf = io.BytesIO(); im.save(buf, "PNG"); return buf.getvalue()


def prepare(base, student):
    """撮る前に：wt01 が中3R 数学に開いている計算テストを 1 つ出す（テストの提出の場面）。
    生徒がホームの宿題に写真を 1 枚出す（出した状態の場面）。どちらも本物の口で。"""
    tok_t = (api(base, "POST", "/demo/enter", None, {"id": "wt01"}) or {}).get("token")
    tok_s = (api(base, "POST", "/demo/enter", None, {"id": student}) or {}).get("token")
    if not tok_s:
        return None
    asg = (api(base, "GET", "/assignments", tok_s) or {}).get("assignments") or []
    now = time.time() * 1000
    if tok_t and not any(a.get("quiz") and a.get("kind") == "計算テスト" and int(a.get("dueAt") or 0) > now for a in asg):
        api(base, "POST", "/quiz", tok_t, {"key": "j3r:math", "title": "第2回", "dueAt": int(now + 3 * 86400 * 1000), "kind": "計算テスト"})   # 全員に（students は付けない）
    return True


def submit_photo(base, student, aid):
    import base64
    tok_s = (api(base, "POST", "/demo/enter", None, {"id": student}) or {}).get("token")
    if tok_s and aid:
        api(base, "POST", "/submissions/" + aid, tok_s, {"files": [{"type": "image/png", "b64": base64.b64encode(note_png()).decode()}]})


def attach_files(c, selector, paths):
    """<input type=file> に手元のファイルを選ばせる（scripts/check/atlas/atlaslib.py と同じ。土台の口座の表に依存しないよう写した）。"""
    doc = c.ws.call("DOM.getDocument", {})
    node = c.ws.call("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": selector})
    if not node.get("nodeId"):
        return False
    c.ws.call("DOM.setFileInputFiles", {"nodeId": node["nodeId"], "files": paths})
    return True


def capture(base, student, fmt, outdir, student2=None):
    """1 つの比の画面を全部撮る。{名前: (png の道, 押す位置 or None)} を返す。
    student は過去問のある生徒（中3）、student2 はテストの提出箱のある生徒（小4。無ければ student）。"""
    from cdp import Chrome
    W, H, cw, ch, scale, mobile = FORMATS[fmt]
    shots = {}
    def shot(c, name, tap_sel=None, wait=1.2):
        time.sleep(wait)
        c.eval("(function(){ var s=document.createElement('style'); s.id='nomo'; s.textContent='*,*::before,*::after{animation:none !important; transition:none !important} #toast{display:none !important}'; document.head.appendChild(s); })()")
        tap = None
        if tap_sel:
            r = json.loads(c.eval("JSON.stringify((function(){ var e=document.querySelector(%s); if(!e) return null; var r=e.getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; })())" % json.dumps(tap_sel)))
            tap = (r[0] * scale, r[1] * scale) if r else None
        p = os.path.join(outdir, "%s-%s.png" % (fmt, name))
        c.shot(p); shots[name] = (p, tap)
        c.eval("(function(){ var s=document.getElementById('nomo'); if(s) s.remove(); })()")
    def enter(c, lid):
        c.goto(base + "/demo", wait=0.8); c.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1','1');")
        c.goto("about:blank", wait=0.2); c.goto(base + "/demo", wait=1.0)
        c.wait_for("!!document.querySelector('#demoOpen')", 20); c.eval("document.querySelector('#demoOpen').click()"); time.sleep(0.8)
        c.eval("document.querySelector('[data-demoid=%s]').click()" % json.dumps(lid)); c.wait_for("!document.querySelector('#lId')", 40); time.sleep(2.0)
    prepare(base, student)
    with Chrome(width=cw, height=ch, scale=scale, mobile=mobile, port=9401 + list(FORMATS).index(fmt)) as c:
        enter(c, student)
        c.eval("TubeUI.go('today')"); shot(c, "home", tap_sel=".h-card .btn.hw-go, .h-card [data-hw]", wait=2.2)
        # 押したあと：本物の口で写真を 1 枚選ぶ（<input type=file> に入れる）→「ためる」札に写真が並び「1枚を送る」が出る。それを撮って、送る
        pic = os.path.join(outdir, "note-%s.png" % fmt)
        with open(pic, "wb") as f: f.write(note_png())
        aid = c.eval("(function(){ var i=document.querySelector('.h-card input[data-up]'); return i ? i.getAttribute('data-up') : null; })()")
        if aid and attach_files(c, '.h-card input[data-up=%s]' % json.dumps(aid), [pic]):
            c.wait_for("document.querySelectorAll('[data-stage=%s] .up-th').length >= 1" % json.dumps(aid), 8); time.sleep(0.6)
            shot(c, "submitted", tap_sel="[data-upsend=%s]" % json.dumps(aid), wait=0.4)
            c.eval("(function(){ var b=document.querySelector('[data-upsend=%s]'); if(b) b.click(); })()" % json.dumps(aid)); time.sleep(3.0)
        c.eval("TubeUI.go('homework')"); time.sleep(2.0); c.eval("window.scrollTo(0,0)"); shot(c, "tests", wait=0.6)
        c.eval("TubeUI.go('record')"); time.sleep(1.5); c.eval("window.scrollTo(0,0)"); shot(c, "teacher")          # 「先生から」のタブ
        c.eval("(function(){ var b=document.querySelector('[data-ret]'); if(b){ b.scrollIntoView({block:'center'}); } })()"); time.sleep(0.4)
        if c.eval("!!document.querySelector('[data-ret]')"):
            c.eval("document.querySelector('[data-ret]').click()"); time.sleep(1.5); shot(c, "returned")
            c.eval("(function(){ var b=document.querySelector('[data-retshut]'); if(b) b.click(); })()"); time.sleep(0.5)
        c.eval("TubeUI.go('kakomon')"); time.sleep(1.5)
        c.eval("(function(){ var e=document.querySelector('.kk-row.done'); if(e) e.scrollIntoView({block:'center'}); })()"); shot(c, "kakomon")
        c.eval("TubeUI.go('daily')"); time.sleep(1.5); c.eval("window.scrollTo(0,0)"); shot(c, "daily")
        c.eval("TubeUI.go('parent')"); time.sleep(1.5); c.eval("window.scrollTo(0,0)"); shot(c, "record")          # 「保護者の方へ」（成績の伸び）

        # 登録（はじめての端末）：ようこそ → コード（先に入っている）→ 学年・クラス（名前の欄は無い）
        c.goto(base + "/", wait=0.6); c.eval("localStorage.clear(); sessionStorage.clear();"); c.goto("about:blank", wait=0.2); c.goto(base + "/#join", wait=1.5)
        shot(c, "welcome", wait=1.0)
        if c.eval("!!document.querySelector('#jnGo')"):
            c.eval("document.querySelector('#jnGo').click()"); time.sleep(1.2); shot(c, "code", tap_sel="#jnCodeGo")
            if c.eval("!!document.querySelector('#jnCodeGo') && (document.querySelector('#jnCode')||{}).value"):
                c.eval("document.querySelector('#jnCodeGo').click()"); time.sleep(2.0)
                if c.eval("!!document.querySelector('#jnSkip')"): c.eval("document.querySelector('#jnSkip').click()"); time.sleep(1.2)
                shot(c, "form")
    return shots


# ------------------------------------------------------------ 絵を組む
def blobs_bg(W, H, t):
    """紙色の地に、5 教科の色の玉（アプリの背景と同じ気分。ゆっくり動く）。"""
    small = (max(1, W // 8), max(1, H // 8))
    im = Image.new("RGB", small, PAPER)
    d = ImageDraw.Draw(im, "RGBA")
    cols = [(214, 61, 36), (10, 111, 224), (242, 160, 0), (22, 163, 74), (139, 92, 246)]
    pos = [(0.16, 0.14), (0.86, 0.28), (0.46, 0.50), (0.14, 0.72), (0.82, 0.88)]
    for i, (c, (px, py)) in enumerate(zip(cols, pos)):
        x = px * small[0] + math.sin(t * 0.6 + i) * small[0] * 0.03
        y = (py - 0.06 * math.sin(t * 0.5 + i * 1.3)) * small[1]
        r = small[0] * 0.34
        d.ellipse([x - r, y - r * 0.55, x + r, y + r * 0.55], fill=c + (int(255 * 0.30),))
    im = im.filter(ImageFilter.GaussianBlur(small[0] * 0.18))
    return im.resize((W, H), Image.BILINEAR)


def rounded_shot(img, box_w, box_h, radius):
    """写しを枠に収め（contain）、角を丸める。"""
    im = img.convert("RGB")
    s = min(box_w / im.width, box_h / im.height)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=radius, fill=255)
    return im, mask


def paste_card(frame, im, mask, x, y):
    sh = Image.new("RGBA", (im.width + 80, im.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([40, 52, im.width + 40, im.height + 52], radius=40, fill=(23, 21, 15, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(22))
    frame.alpha_composite(sh, (x - 40, y - 40))
    frame.paste(im, (x, y), mask)


def wrap(draw, text, fnt, maxw):
    """幅に収まるように折る。折る所は、できるだけ空白か読点の直後（「ひと目／で」のように語の途中で割らない）。"""
    out, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=fnt) > maxw and cur:
            cut = max(cur.rfind(" "), cur.rfind("、"))
            if 0 < cut < len(cur) - 1 and cut >= len(cur) // 3:
                out.append(cur[:cut + 1].rstrip()); cur = cur[cut + 1:] + ch
            else:
                out.append(cur); cur = ch
        else:
            cur += ch
    if cur: out.append(cur)
    return out


CAP_H = {"phone": 360, "ipad": 380}            # 電話・iPad：写しの下に取る見出しの場所（px）
PC_SPLIT = 0.32                                 # PC：安全な余白の内側の左 32% が見出し、右が写し
# 安全な余白（左右, 上下）。画面では動画が端まで覆う（object-fit:cover）ので、見ている画面の比が動画と違う分だけ端が切れる。
# 字と写しはこの内側にだけ置く：電話は上下 10%（Safari の帯つきの iPhone で上下 8% ずつ切れる）、PC は左右 15%（iPad 横向きで左右 10〜12% ずつ切れる）。10-12
SAFE = {"phone": (80, 240), "ipad": (110, 200), "pc": (290, 110)}

def caption(frame, lines, sub, fmt, alpha=1.0):
    """見出しと添え書き。電話・iPad は写しの下（写しに被せない）、PC は左の列（縦の真ん中）。字は紙色の地に直に。"""
    W, H = frame.size
    big = font(FONT_B, {"phone": 62, "ipad": 68, "pc": 50}[fmt])
    sm = font(FONT_R, {"phone": 36, "ipad": 40, "pc": 30}[fmt])
    sx, sy = SAFE[fmt]
    maxw = {"phone": W - 2 * sx, "ipad": W - 2 * sx, "pc": int((W - 2 * sx) * PC_SPLIT) - 40}[fmt]
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ls = []
    for ln in lines: ls += wrap(d, ln, big, maxw)
    ss = wrap(d, sub, sm, maxw) if sub else []
    lh, sh_ = int(big.size * 1.35), int(sm.size * 1.55)
    h = lh * len(ls) + (sh_ * len(ss) + 18 if ss else 0)
    if fmt == "pc":
        x0, y0 = sx, (H - h) / 2 - 20
        for x in ls:
            d.text((x0, y0), x, font=big, fill=INK + (int(255 * alpha),)); y0 += lh
        if ss: y0 += 18
        for x in ss:
            d.text((x0, y0), x, font=sm, fill=GREY + (int(255 * alpha),)); y0 += sh_
    else:
        y0 = H - sy - CAP_H[fmt] + (CAP_H[fmt] - h) / 2
        for x in ls:
            d.text(((W - d.textlength(x, font=big)) / 2, y0), x, font=big, fill=INK + (int(255 * alpha),)); y0 += lh
        if ss: y0 += 18
        for x in ss:
            d.text(((W - d.textlength(x, font=sm)) / 2, y0), x, font=sm, fill=GREY + (int(255 * alpha),)); y0 += sh_
    frame.alpha_composite(layer)


# ------------------------------------------------------------ 印（本物のロゴ）と、前の紹介動画と同じ現れ方
# app/icon.svg：青の角丸（#0A6FC7→#004E93、rx 40/180）・黄色の棒（34,45 112×14 rx7）・白い輪（中心 90,96 半径 40、太さ 13）。
# 現れ方は Claude outputs/tubestudy-提案-素材/紹介動画/promo2.html の drawLogo と同じ時間：
#   印 … 0〜0.35 秒で濃く、0〜0.9 秒で 40px 下から弾んで（back）上がり 0.55→1 に。
#   輪 … 0.5〜1.5 秒で、上から時計回りに描かれる（ease-out）。
#   銘 … 1.2〜1.9 秒で 30px 下から。添え書き … 1.9〜2.5 秒で 16px 下から。
BRAND_B = "/System/Library/Fonts/Avenir Next.ttc"       # tube ＝ Demi Bold（index 2）・study ＝ Medium（index 5）。アプリの .brand と同じ
BLUE_INK = (0, 78, 147)

def lin(u, a, b): return max(0.0, min(1.0, (u - a) / (b - a)))
def eo(x): return 1 - (1 - x) ** 3
def eio(x): return 4 * x * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2
def back(x):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2

def icon_image(size, ring_p, ss=4):
    """印を size px で描く（ss 倍で描いて縮める）。ring_p は輪の描かれた割合（0〜1）。"""
    S = size * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # 縦のグラデーション → 角丸で切り抜く
    grad = Image.new("RGBA", (S, S))
    top, bot = (10, 111, 199), (0, 78, 147)
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        f = y / max(1, S - 1)
        gd.line([(0, y), (S, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * f) for i in range(3)) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 40 / 180), fill=255)
    im.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(im)
    k = S / 180.0
    d.rounded_rectangle([34 * k, 45 * k, (34 + 112) * k, (45 + 14) * k], radius=7 * k, fill=(249, 185, 0, 255))
    if ring_p > 0:
        # 輪は icon.svg と同じ：半径 40 の線の真ん中、太さ 13（PIL の arc は枠の内側に太さを取るので、枠は半径 r + w/2）。
        # 端の丸は線の真ん中（半径 r）に置く。描き終わった輪に端の丸は付けない（10-12 本人：白い輪の上に出っ張りが出ていた。
        # 前は枠を半径 r にしていたので帯が内側に寄り、半径 r の端の丸が帯の外へはみ出していた）
        cx, cy, r, w = 90 * k, 96 * k, 40 * k, 13 * k
        ro = r + w / 2
        if ring_p >= 1.0:
            d.ellipse([cx - ro, cy - ro, cx + ro, cy + ro], outline=(255, 255, 255, 255), width=int(round(w)))
        else:
            a0, a1 = -90, -90 + 360 * ring_p
            d.arc([cx - ro, cy - ro, cx + ro, cy + ro], start=a0, end=a1, fill=(255, 255, 255, 255), width=int(round(w)))
            for a in (a0, a1):                            # 丸い端（線の真ん中に）
                ex, ey = cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))
                d.ellipse([ex - w / 2, ey - w / 2, ex + w / 2, ey + w / 2], fill=(255, 255, 255, 255))
    return im.resize((size, size), Image.LANCZOS)

def paste_alpha_scaled(frame, im, cx, cy, scale, alpha):
    if alpha <= 0 or scale <= 0: return
    w = max(1, int(im.width * scale)); h = max(1, int(im.height * scale))
    s = im.resize((w, h), Image.LANCZOS)
    if alpha < 1:
        a = s.split()[3].point(lambda v: int(v * alpha)); s.putalpha(a)
    frame.alpha_composite(s, (int(cx - w / 2), int(cy - h / 2)))

def logo_card(W, H, fmt, t, u, text, sub, fade_q=0.0):
    """最初と最後の札。u は札の中の秒。text は銘の下の 1 行、sub はその下の小さな 1 行。"""
    frame = blobs_bg(W, H, t).convert("RGBA")
    size = {"phone": 236, "ipad": 256, "pc": 200}[fmt]
    cx, cy = W / 2, H * ({"phone": 0.40, "ipad": 0.40, "pc": 0.42}[fmt]) - size * 0.1
    o = lin(u, 0, .35); pop = back(lin(u, 0, .9)); dy = (1 - eo(lin(u, 0, .9))) * 40 * (W / 1080.0)
    sc = .55 + .45 * pop
    ring_p = eo(lin(u, .5, 1.5))
    q = eio(fade_q) if fade_q > 0 else 0.0
    o_mark = o * (1 - q); sc *= (1 - .06 * q)
    # 影（lg-mark の 0 18px 34px rgba(0,78,147,.30)）
    if o_mark > 0:
        sh = Image.new("RGBA", (int(size * sc) + 160, int(size * sc) + 160), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([80, 98, 80 + int(size * sc), 98 + int(size * sc)], radius=int(size * sc * 40 / 180), fill=(0, 78, 147, int(76 * o_mark)))
        sh = sh.filter(ImageFilter.GaussianBlur(17))
        frame.alpha_composite(sh, (int(cx - sh.width / 2), int(cy + dy - sh.height / 2 + 8)))
    paste_alpha_scaled(frame, icon_image(size, ring_p), cx, cy + dy, sc, o_mark)
    d = ImageDraw.Draw(frame)
    # 銘：tube（濃い青・Demi Bold）＋ study（黄・Medium）
    fb = font(BRAND_B, {"phone": 92, "ipad": 100, "pc": 84}[fmt]); fb.set_variation_by_name if False else None
    fb2 = ImageFont.truetype(BRAND_B, {"phone": 92, "ipad": 100, "pc": 84}[fmt], index=5)
    fb1 = ImageFont.truetype(BRAND_B, {"phone": 92, "ipad": 100, "pc": 84}[fmt], index=2)
    ow = eo(lin(u, 1.2, 1.9)) * (1 - q); wy = (1 - eo(lin(u, 1.2, 1.9))) * 30
    w1, w2 = d.textlength("tube", font=fb1), d.textlength("study", font=fb2)
    y0 = cy + size * 0.55 + 36 + wy
    if ow > 0:
        x = W / 2 - (w1 + w2) / 2
        d.text((x, y0), "tube", font=fb1, fill=BLUE_INK + (int(255 * ow),))
        d.text((x + w1, y0), "study", font=fb2, fill=(249, 185, 0, int(255 * ow)))
    # 添え書き（2 行）
    ot = eo(lin(u, 1.9, 2.5)) * (1 - q); ty = (1 - eo(lin(u, 1.9, 2.5))) * 16
    sm = font(FONT_B, {"phone": 44, "ipad": 48, "pc": 40}[fmt]); sm2 = font(FONT_R, {"phone": 36, "ipad": 40, "pc": 32}[fmt])
    if ot > 0:
        yy = y0 + fb1.size * 1.45 + ty
        tw = d.textlength(text, font=sm); d.text((W / 2 - tw / 2, yy), text, font=sm, fill=INK + (int(255 * ot),))
        if sub:
            tw2 = d.textlength(sub, font=sm2); d.text((W / 2 - tw2 / 2, yy + sm.size * 1.6), sub, font=sm2, fill=GREY + (int(255 * ot),))
    return frame


def privacy_card(W, H, fmt, t, prog):
    """前の紹介動画の S8 と同じ：小さな前置き → 大きな一行 → 2 行の説明 → 3 つの札（氏名なし／戻せない形／消える）。
    本人（10-12）「セキュリティの観点のページは前の方がずっとわかりやすかった。その部分だけ前の部分を援用」。"""
    frame = blobs_bg(W, H, t).convert("RGBA")
    d = ImageDraw.Draw(frame)
    ph = (fmt == "phone"); pc = (fmt == "pc")
    f_kk = font(FONT_B, {"phone": 34, "ipad": 36, "pc": 30}[fmt])
    f_big = font(FONT_B, {"phone": 72, "ipad": 84, "pc": 88}[fmt])
    f_sm = font(FONT_R, {"phone": 34, "ipad": 38, "pc": 32}[fmt])
    f_t1 = font(FONT_B, {"phone": 40, "ipad": 42, "pc": 36}[fmt]); f_t2 = font(FONT_R, {"phone": 28, "ipad": 30, "pc": 26}[fmt])
    maxw = W - 2 * SAFE[fmt][0]
    big = wrap(d, "サーバに、氏名はありません。", f_big, maxw)
    small = ["あるのは「番号の子が、こう学んだ」だけ。", "番号が誰かは、塾の手元の名簿にしか無い。"]
    tiles = [("氏名なし", "出席番号だけ"), ("戻せない形", "パスワードも合言葉も"), ("消える", "写真は180日、退塾で全部")]
    # 現れ方：前置きと大きな字（0〜0.6）、説明（0.3〜0.9）、札は 1 つずつ（0.6〜1.5）
    def ao(a0, a1): return eo(lin(prog, a0, a1))
    lh_big = int(f_big.size * 1.3)
    h_text = f_kk.size + 26 + lh_big * len(big) + 30 + int(f_sm.size * 1.6) * 2
    tile_h = {"phone": 128, "ipad": 136, "pc": 124}[fmt]
    if ph or fmt == "ipad":
        h_tiles = 3 * tile_h + 2 * 18 if ph else tile_h
    else:
        h_tiles = tile_h
    total = h_text + 56 + h_tiles
    y = (H - total) / 2 - (40 if ph else 20)
    o1 = ao(0, 0.3)
    tw = d.textlength("でも、これも大事にしています", font=f_kk)
    d.text((W / 2 - tw / 2, y + (1 - o1) * 16), "でも、これも大事にしています", font=f_kk, fill=BLUE_INK + (int(255 * o1),))
    y += f_kk.size + 26
    o2 = ao(0.1, 0.6)
    for ln in big:
        tw = d.textlength(ln, font=f_big); d.text((W / 2 - tw / 2, y + (1 - o2) * 24), ln, font=f_big, fill=INK + (int(255 * o2),)); y += lh_big
    y += 30
    o3 = ao(0.3, 0.9)
    for ln in small:
        tw = d.textlength(ln, font=f_sm); d.text((W / 2 - tw / 2, y + (1 - o3) * 16), ln, font=f_sm, fill=GREY + (int(255 * o3),)); y += int(f_sm.size * 1.6)
    y += 56
    # 札
    if ph:
        tw_ = min(W - 160, 760); xs = [(W - tw_) / 2] * 3; ys = [y + i * (tile_h + 18) for i in range(3)]; tws = [tw_] * 3
    else:
        gap = 28; tw_ = min(int((maxw - 2 * gap) / 3), 440); x0 = W / 2 - (3 * tw_ + 2 * gap) / 2
        xs = [x0 + i * (tw_ + gap) for i in range(3)]; ys = [y] * 3; tws = [tw_] * 3
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
    for i, (t1, t2) in enumerate(tiles):
        o = ao(0.55 + 0.2 * i, 0.85 + 0.2 * i)
        if o <= 0: continue
        x, yy, w_ = xs[i], ys[i] + (1 - o) * 20, tws[i]
        sh = Image.new("RGBA", (int(w_) + 80, tile_h + 80), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([40, 56, 40 + int(w_), 56 + tile_h], radius=26, fill=(23, 21, 15, int(50 * o)))
        frame.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)), (int(x - 40), int(yy - 40)))
        ld.rounded_rectangle([x, yy, x + w_, yy + tile_h], radius=26, fill=(255, 255, 255, int(255 * o)))
        t1w = ld.textlength(t1, font=f_t1); t2w = ld.textlength(t2, font=f_t2)
        ld.text((x + w_ / 2 - t1w / 2, yy + tile_h / 2 - f_t1.size * 0.95), t1, font=f_t1, fill=INK + (int(255 * o),))
        ld.text((x + w_ / 2 - t2w / 2, yy + tile_h / 2 + 8), t2, font=f_t2, fill=GREY + (int(255 * o),))
    frame.alpha_composite(layer)
    return frame


def title_card(W, H, fmt, t, text, sub, prog, dur=4.0, fade_end=True):
    """prog（0〜1）を秒に戻して logo_card へ。終わりの札は最後の 0.5 秒で薄れる。"""
    u = prog * dur
    q = lin(u, dur - 0.5, dur) if fade_end else 0.0
    return logo_card(W, H, fmt, t, u, text, sub, q)


def scene_frame(W, H, fmt, t, img, tap, zoom, lines, sub, ripple_t):
    frame = blobs_bg(W, H, t).convert("RGBA")
    sx, sy = SAFE[fmt]
    if fmt == "pc":
        cw_ = W - 2 * sx; colw = int(cw_ * PC_SPLIT)          # 安全な余白の内側を、左の列（見出し）と右の写しに分ける
        bw, bh = (W - 200) - (sx + colw + 40), H - 2 * sy      # 写しの右端だけは余白 200（iPad 横向きで写しの端が 2% ほど切れるが、字は切れない）
        im, mask = rounded_shot(img, bw, bh, 32)
        im = im.resize((int(im.width * zoom), int(im.height * zoom)), Image.BILINEAR); mask = mask.resize(im.size, Image.BILINEAR)
        x, y = int(sx + colw + 40 + (bw - im.width) / 2), int((H - im.height) / 2)
    else:
        bw, bh = W - 2 * sx, H - 2 * sy - CAP_H[fmt]
        im, mask = rounded_shot(img, bw, bh, 56)
        im = im.resize((int(im.width * zoom), int(im.height * zoom)), Image.BILINEAR); mask = mask.resize(im.size, Image.BILINEAR)
        x, y = int((W - im.width) / 2), int(sy + (bh - im.height) / 2)
    paste_card(frame, im, mask, x, y)
    if tap and ripple_t is not None and 0 <= ripple_t < 0.9:
        sx, sy = tap
        s = im.width / img.width
        cx, cy = x + sx * s, y + sy * s
        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
        rr = 30 + ripple_t * 160; a = int(190 * (1 - ripple_t))
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=BLUE + (a,), width=10)
        d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=BLUE + (int(200 * (1 - ripple_t * 0.5)),))
        frame.alpha_composite(layer)
    caption(frame, lines, sub, fmt)
    return frame


# ------------------------------------------------------------ 音
# 前の紹介動画（Claude outputs/tubestudy-提案-素材/紹介動画/music4.py）と同じ作り：96 BPM、C–G–Am–F を回し、場面ごとに層が増えて
# 頂点へ、プライバシーの場面で打楽器を抜いて静かに、最後の印で大きく温かい和音。印の効果音（ぽこん・輪・銘）も同じ時刻。
# 本人（10-12）「展開がない。前と同じような雰囲気に。にぎやかさを足して、電子音感を極力減らす」→ 鐘・爪弾き・丸いパッド・ベースだけ
# （鋸波の合唱とノイズの上昇音は使わない。ハイハットは小さく、代わりにシェイカーと手拍子でにぎやかに）。
SR = 44100

def _env(n, a, d, s_, r):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    e = np.ones(n); a_n = min(a_n, n)
    if a_n: e[:a_n] = np.linspace(0, 1, a_n, endpoint=False)
    if d_n and a_n + d_n <= n: e[a_n:a_n + d_n] = np.linspace(1, s_, d_n); e[a_n + d_n:] = s_
    elif a_n < n: e[a_n:] = s_
    r_n = min(r_n, n)
    if r_n: e[-r_n:] *= np.linspace(1, 0, r_n)
    return e

def _midi(m): return 440.0 * 2 ** ((m - 69) / 12.0)

def _pluck(f, dur=0.5, vel=1.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    w = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * 2 * f * tt + 0.3) + 0.12 * np.sin(2 * np.pi * 3 * f * tt)
         + 0.08 * np.sin(2 * np.pi * f * 1.004 * tt))
    return w * np.exp(-tt / 0.2) * (1 - np.exp(-tt / 0.003)) * 0.22 * vel

def _bell(f, dur=1.2, vel=1.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    w = np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * 2.0 * f * tt) * np.exp(-tt / 0.3) + 0.25 * np.sin(2 * np.pi * 3.01 * f * tt) * np.exp(-tt / 0.15)
    return w * np.exp(-tt / 0.45) * (1 - np.exp(-tt / 0.003)) * 0.18 * vel

def _pad(freqs, dur, vel=1.0, attack=0.9, pump=None, rnd=None):
    n = int(dur * SR); tt = np.arange(n) / SR
    w = np.zeros(n)
    for f in freqs:
        for det in (0.0, 0.0025, -0.0025):
            w += np.sin(2 * np.pi * f * (1 + det) * tt + (rnd.rand() if rnd is not None else 0) * 6.28)
        w += 0.35 * np.sin(2 * np.pi * 2 * f * tt) + 0.12 * np.sin(2 * np.pi * 3 * f * tt)
    w /= (len(freqs) * 3.5)
    w *= 1 + 0.08 * np.sin(2 * np.pi * 0.35 * tt)
    en = _env(n, attack, 0.3, 0.85, min(0.6, dur / 3))
    if pump:
        ph = (tt % pump) / pump
        en = en * (0.55 + 0.45 * np.clip(ph * 4, 0, 1))
    return w * en * 0.20 * vel

def _bass(f, dur=0.6, vel=1.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    w = np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt) * np.exp(-tt / 0.25)
    return w * _env(n, 0.006, 0.15, 0.7, 0.12) * 0.30 * vel

def _kick(vel=1.0, rnd=None):
    n = int(0.3 * SR); tt = np.arange(n) / SR
    f = 44 + 95 * np.exp(-tt / 0.042); ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-tt / 0.13) * 0.62 * vel

def _clap(vel=1.0, rnd=None):
    n = int(0.12 * SR); out = np.zeros(n)
    for k, d in enumerate((0.0, 0.011, 0.022)):
        x = rnd.randn(n)
        x = np.convolve(x, np.ones(5) / 5, mode="same") - np.convolve(x, np.ones(40) / 40, mode="same")
        en = np.exp(-np.arange(n) / SR / (0.03 + 0.012 * k)); i0 = int(d * SR)
        out[i0:] += (x * en)[:n - i0]
    return out * 0.15 * vel

def _shaker(vel=1.0, rnd=None):
    n = int(0.07 * SR); x = rnd.randn(n); x = x - np.concatenate([[0], x[:-1]])
    return x * np.exp(-np.arange(n) / SR / 0.018) * 0.035 * vel

def _hat(vel=1.0, rnd=None):
    n = int(0.035 * SR); x = rnd.randn(n); x = x - np.concatenate([[0], x[:-1]]); x = x - np.concatenate([[0], x[:-1]])
    return x * np.exp(-np.arange(n) / SR / 0.012) * 0.03 * vel

def _rim(vel=1.0, rnd=None):
    n = int(0.03 * SR); x = rnd.randn(n)
    x = np.convolve(x, np.ones(3) / 3, mode="same") - np.convolve(x, np.ones(12) / 12, mode="same")
    return x * np.exp(-np.arange(n) / SR / 0.007) * 0.10 * vel

def _pokon(vel=1.0):
    n = int(0.36 * SR); tt = np.arange(n) / SR
    f1 = 330 + (760 - 330) * np.clip(tt / 0.055, 0, 1); ph1 = 2 * np.pi * np.cumsum(f1) / SR
    po = np.sin(ph1) * np.exp(-tt / 0.05) * (1 - np.exp(-tt / 0.002))
    t2 = np.clip(tt - 0.05, 0, None); f2 = 1046.5 * (1 - 0.06 * np.clip(t2 / 0.12, 0, 1)); ph2 = 2 * np.pi * np.cumsum(f2) / SR
    kon = (np.sin(ph2) + 0.4 * np.sin(2 * ph2) * np.exp(-t2 / 0.05)) * np.exp(-t2 / 0.11) * (tt >= 0.05) * (1 - np.exp(-t2 / 0.002))
    return (po * 0.9 + kon * 0.7) * 0.55 * vel

def _whirr(dur=0.95, vel=1.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = 520 * (1.0 + 1.9 * (tt / dur) ** 0.8); ph = 2 * np.pi * np.cumsum(f) / SR
    trem = 0.55 + 0.45 * np.sin(2 * np.pi * (14 + 10 * tt / dur) * tt)
    tone = (np.sin(ph) + 0.3 * np.sin(2 * ph)) * trem
    return tone * np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 0.7 * 0.10 * vel

def _shimmer(vel=1.0):
    out = np.zeros(int(0.9 * SR))
    for i, m in enumerate((84, 88, 91, 96)):
        s_ = _bell(_midi(m), 0.7, 0.35); i0 = int(i * 0.045 * SR); out[i0:i0 + len(s_)] += s_[:len(out) - i0]
    return out * vel

def music(seconds, scenes=None, sr=SR):
    """scenes は (秒数, 種類, …) の並び。種類 title の最初と最後、privacy の場面で音の表情を変える。ステレオ 2×n の int16 を返す。"""
    N = int(seconds * sr); L = np.zeros(N); Rr = np.zeros(N)
    rnd = np.random.RandomState(11)
    def put(sig, t0, pan=0.0, gain=1.0):
        i0 = int(t0 * sr)
        if i0 >= N or i0 < 0: return
        seg = sig[:N - i0] * gain
        L[i0:i0 + len(seg)] += seg * np.sqrt(0.5 * (1 - pan)); Rr[i0:i0 + len(seg)] += seg * np.sqrt(0.5 * (1 + pan))
    # 場面の境目
    starts, acc = [], 0.0
    for sc in (scenes or []): starts.append(acc); acc += sc[0]
    n_sc = len(scenes or [])
    t_first_end = (scenes[0][0] if scenes else 4.0)
    final = starts[-1] if scenes else seconds - 4.0          # 最後の印の札の始まり
    def kind_at(tm):
        i = max([k for k, st in enumerate(starts) if st <= tm + 1e-6] or [0])
        return (scenes[i][1], scenes[i][2] if len(scenes[i]) > 2 else None, i)
    BPM = 96.0; BEAT = 60.0 / BPM; BAR = 4 * BEAT
    T0 = t_first_end - BEAT                                    # 最初の札の終わり少し前から刻みが入る
    # 印の効果音（最初の札）：ぽこん 0.50・輪 0.53・銘 1.22（前の動画と同じ）
    for t0 in (0.5, final + 0.5): put(_pokon(1.0), t0)
    for t0 in (0.53, final + 0.53): put(_whirr(0.95, 1.0), t0, pan=0.1)
    for t0 in (1.22, final + 1.22): put(_shimmer(0.8), t0, pan=0.2)
    put(_pad([_midi(m) for m in (48, 55, 62, 64)], T0 + 0.4, 0.45, attack=1.4, rnd=rnd), 0.25)
    prog = [("C", [60, 64, 67, 71]), ("G", [55, 59, 62, 66]), ("Am", [57, 60, 64, 67]), ("F", [53, 57, 60, 64])]
    pad_v = {"C": [48, 55, 64, 67], "G": [43, 55, 59, 62], "Am": [45, 52, 60, 64], "F": [41, 53, 57, 60]}
    bass_n = {"C": 36, "G": 31, "Am": 33, "F": 29}
    nbars = int((final - T0) / BAR) + 1
    for bar in range(nbars):
        tb = T0 + bar * BAR
        if tb >= final - 0.2: break
        name, tones = prog[bar % 4]
        if bar >= nbars - 2: name, tones = (("F", [53, 57, 60, 64]) if bar == nbars - 2 else ("G", [55, 59, 62, 67]))   # IV–V で持ち上げ
        kind, key, si = kind_at(tb + 0.01)
        quiet = (key == "privacy")
        # 層：場面が進むほど増える（2 → 7）。最後の 1 場面は頂点
        stage = 2 + int(5 * (si - 1) / max(1, n_sc - 3)) if si >= 1 else 2
        stage = max(2, min(7, stage))
        vel = {2: 0.86, 3: 0.9, 4: 0.94, 5: 0.97, 6: 1.0, 7: 1.0}[stage]
        put(_pad([_midi(m) for m in pad_v[name]], BAR + 0.4, (1.15 if quiet else 0.85) * (0.6 if quiet else vel), attack=(1.0 if quiet else 0.2), pump=(None if quiet else BEAT), rnd=rnd), tb)
        if quiet:
            put(_bass(_midi(bass_n[name]), 2.4, 0.5), tb)
            for beat, m in {"C": [(0, 79), (2, 76)], "G": [(0, 74), (2, 71)], "Am": [(0, 76), (2, 72)], "F": [(0, 72), (2, 76)]}[name]:
                put(_bell(_midi(m), 1.8, 0.6), tb + beat * BEAT, pan=0.1)
            put(_pluck(_midi(tones[0] + 12), 0.8, 0.3), tb + 3 * BEAT, pan=0.2)
            continue
        for k in range(4): put(_kick(0.9 if k % 2 == 0 else 0.75, rnd), tb + k * BEAT)
        if stage >= 3:
            for k in (1, 3): put(_clap(0.85 if stage < 7 else 1.0, rnd), tb + k * BEAT)
        for k in range(8): put(_hat(0.8 if k % 2 == 0 else 0.5, rnd), tb + k * BEAT / 2, pan=-0.25)
        if stage >= 4:
            for k in range(16): put(_shaker(0.8 if k % 4 == 2 else 0.4, rnd), tb + k * BEAT / 4, pan=0.35)
        root = bass_n[name]
        for k in range(8):
            up = (k % 2 == 1) and stage >= 3
            put(_bass(_midi(root + (12 if up else 0)), 0.32, 0.9 if k % 2 == 0 else 0.7), tb + k * BEAT / 2)
        arp = tones + [tones[0] + 12, tones[1] + 12, tones[2] + 12, tones[1] + 12]
        div = 4 if stage >= 4 else 2
        for k in range(4 * div):
            m = arp[k % len(arp)]
            v = (0.85 if k % 2 == 0 else 0.55) * (0.8 + 0.2 * min(1, (stage - 2) / 5.0)) * (0.8 if div == 4 else 1.0)
            put(_pluck(_midi(m), 0.45, v), tb + k * BEAT / div, pan=(-0.35 if k % 2 == 0 else 0.35))
        motif = {"C": [(0, 79), (1, 76), (2, 72), (3, 74)], "G": [(0, 74), (2, 71), (3, 74)],
                 "Am": [(0, 76), (1, 72), (2, 69), (3, 71)], "F": [(0, 72), (2, 76), (3, 77)]}[name]
        if stage >= 3:
            for beat, m in motif:
                put(_bell(_midi(m), 1.1, 0.75 if stage < 6 else 0.85), tb + beat * BEAT, pan=0.15)
                if stage >= 6: put(_bell(_midi(m + 4 if (m % 12) in (0, 5, 7) else m + 3), 1.0, 0.35), tb + beat * BEAT, pan=-0.15)
        if stage >= 7:
            for k, m in enumerate((tones[3] + 12, tones[2] + 12, tones[3] + 12, tones[1] + 12)):
                put(_pluck(_midi(m), 0.4, 0.42), tb + (k + 0.5) * BEAT, pan=0.45)
            put(_rim(0.6, rnd), tb + 2.5 * BEAT, pan=-0.2)
    # 最後の印：大きく温かい C（パッド＋鐘の分散＋ベース）→ 終わりの 1.2 秒で消える
    put(_kick(0.8, rnd), final); put(_clap(0.6, rnd), final)
    put(_bass(_midi(36), 2.6, 0.9), final)
    put(_pad([_midi(m) for m in (48, 55, 60, 64, 67, 74)], 3.4, 1.0, attack=0.06, rnd=rnd), final)
    put(_pad([_midi(m) for m in (60, 64, 67, 74, 79)], 3.0, 0.8, attack=0.05, rnd=rnd), final)
    for k, m in enumerate((72, 76, 79, 84, 88)): put(_bell(_midi(m), 2.2, 0.55), final + 0.06 * k, pan=(-0.4 + 0.2 * k))
    put(_bell(_midi(91), 1.8, 0.45), final + 2 * BEAT, pan=0.1)
    put(_bell(_midi(96), 1.6, 0.3), final + 3 * BEAT, pan=-0.1)
    mix = np.stack([L, Rr])
    tt = np.arange(N) / sr
    mix *= np.clip(tt / 0.15, 0, 1) * np.clip((seconds - tt) / 1.2, 0, 1)
    peak = max(1e-6, np.abs(mix).max())
    mix = mix / peak * 0.89
    mix = np.tanh(mix * 1.2) / np.tanh(1.2)
    mix = mix / max(1e-6, np.abs(mix).max()) * 0.92
    return (mix * 32767).astype(np.int16), sr


def write_wav(path, pcm, sr):
    """pcm は 2×n（ステレオ）か n（モノ）の int16。"""
    with wave.open(path, "wb") as w:
        if pcm.ndim == 2:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(np.stack([pcm[0], pcm[1]], axis=1).tobytes())
        else:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())


# ------------------------------------------------------------ 組み立て
def scenes_for(shots):
    """(秒数, 種類, 写し, 見出し, 添え書き)。写しが無いものは飛ばして、前の場面を少し伸ばす。"""
    S = [
        (4.0, "title", None, "宿題が、もっとかんたんに。", "保護者・生徒のみなさんへ"),
        (4.5, "shot", "home", ["今日の宿題が、ひと目で"], "ホームに「今やるならこれ」が 1 つ。迷いません", "tap"),
        (4.5, "shot", "submitted", ["ノートを撮って、出すだけ"], "写真を選んで「送る」だけ。確認待ちは「先生から」に", "tap"),
        (4.5, "shot", "teacher", ["先生の評価と ひとことが届く"], "「先生から」に、評価・ひとこと・赤入れがそのまま"),
        (4.0, "shot", "returned", ["赤を入れた答案も、そのまま"], "紙を持ち帰らなくても、添削が手元に"),
        (4.0, "shot", "tests", ["漢字テスト・計算テストも"], "授業内の小テストは「テストの提出」から"),
        (4.5, "shot", "kakomon", ["過去問は学校ごとに"], "やった年度と これから。点数も自分で記録"),
        (4.0, "shot", "daily", ["毎日テストで、定着"], "数分の毎日テスト。連続日が増えていきます"),
        (3.5, "shot", "record", ["保護者の方には、伸びが見える"], "教科ごとの成績の伸びと、今週の目標"),
        (5.0, "card", "privacy", [], ""),
        (4.0, "title", None, "さあ、はじめましょう。", "登録コードを入れて、次へ"),
    ]
    out = []
    for sc in S:
        if sc[1] == "shot" and sc[2] not in shots:
            if out: out[-1] = (out[-1][0] + sc[0] * 0.5,) + out[-1][1:]
            continue
        out.append(sc)
    total = sum(s[0] for s in out)
    k = 45.0 / total
    return [(s[0] * k,) + s[1:] for s in out]


def preview(fmt, shots, outdir):
    """場面ごとに 1 コマ（真ん中）を png に。"""
    os.makedirs(outdir, exist_ok=True)
    W, H = FORMATS[fmt][:2]
    scenes = scenes_for(shots)
    imgs = {k: Image.open(v[0]) for k, v in shots.items()}
    acc = 0.0
    for i, sc in enumerate(scenes):
        t = acc + sc[0] * 0.5; prog = 0.5
        if sc[1] == "title":
            fr = title_card(W, H, fmt, t, sc[3], sc[4], prog, dur=sc[0], fade_end=(i == len(scenes) - 1))
        elif sc[1] == "card":
            fr = privacy_card(W, H, fmt, t, 1.0)
        else:
            tap = shots[sc[2]][1] if len(sc) > 5 else None
            fr = scene_frame(W, H, fmt, t, imgs[sc[2]], tap, 1.02, sc[3], sc[4], 0.3 if tap else None)
        fr.convert("RGB").save(os.path.join(outdir, "%s-%02d.png" % (fmt, i)))
        acc += sc[0]
    print("  見本 %d 枚 → %s" % (len(scenes), outdir))


def render(fmt, shots, out_path, ffmpeg):
    W, H = FORMATS[fmt][:2]
    scenes = scenes_for(shots)
    imgs = {k: Image.open(v[0]) for k, v in shots.items()}
    total = sum(s[0] for s in scenes)
    nframes = int(round(total * FPS))
    wav = out_path + ".wav"
    pcm, sr = music(total, scenes); write_wav(wav, pcm, sr)
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "128k", "-shortest", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    XF = 0.5                                   # 場面の重なり（秒）
    starts = []; acc = 0.0
    for s in scenes: starts.append(acc); acc += s[0]
    def frame_of(i, t):
        sc = scenes[i]; local = t - starts[i]; prog = local / sc[0]
        if sc[1] == "title":
            return title_card(W, H, fmt, t, sc[3], sc[4], prog, dur=sc[0], fade_end=(i == len(scenes) - 1))
        if sc[1] == "card":
            return privacy_card(W, H, fmt, t, local / 1.6)
        img = imgs[sc[2]]; tap = shots[sc[2]][1] if len(sc) > 5 else None
        zoom = 1.0 + 0.035 * prog
        rip = (local - 0.9) if tap else None
        return scene_frame(W, H, fmt, t, img, tap, zoom, sc[3], sc[4], rip)
    for f in range(nframes):
        t = f / FPS
        i = max(k for k, st in enumerate(starts) if st <= t + 1e-6)
        fr = frame_of(i, t)
        local = t - starts[i]
        if i > 0 and local < XF:                 # 前の場面から溶け込む
            prev = frame_of(i - 1, t)
            fr = Image.blend(prev, fr, local / XF)
        proc.stdin.write(fr.convert("RGB").tobytes())
        if f % 150 == 0: print("  %s %3d%%" % (fmt, 100 * f // nframes), flush=True)
    proc.stdin.close(); proc.wait()
    os.remove(wav)
    return nframes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--base", default="http://127.0.0.1:8951")
    ap.add_argument("--student", default="")
    ap.add_argument("--out", default=os.path.join(ROOT, "app", "media"))
    ap.add_argument("--only", default="")
    ap.add_argument("--admin", default="wadmin99:kensa-kanri-kensa-kanri-kensa-0000", help="登録コードを作る管理者（検査の土台の口座）")
    ap.add_argument("--preview", action="store_true", help="動画を作らず、場面ごとの 1 コマを png で出す（見て確かめる用）")
    ap.add_argument("--root", default="", help="撮る相手のサーバの置き場（school.json の trialPick を読む。既定は <作業の場所>/vreal、無ければ /real）")
    a = ap.parse_args()
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    shots_dir = os.path.join(a.work, "video-shots"); os.makedirs(shots_dir, exist_ok=True); os.makedirs(a.out, exist_ok=True)
    student, student2 = a.student, ""
    root = a.root or (os.path.join(a.work, "vreal") if os.path.isdir(os.path.join(a.work, "vreal")) else os.path.join(a.work, "real"))
    meta = json.load(open(os.path.join(root, "schools", "waseaca-london", "school.json")))
    acc = json.load(open(os.path.join(root, "schools", "waseaca-london", "accounts.json")))
    picks = meta.get("trialPick") or []
    if not student:
        student = next((l for l in picks if (acc.get(l) or {}).get("classId") == "j3r"), (picks or [""])[0])
    student2 = next((l for l in picks if (acc.get(l) or {}).get("classId") == "e4b"), None)
    # 登録コード（無ければ管理者の口で作る → trial-join-code.js が欄に入れる）
    if a.admin and ":" in a.admin:
        try:
            sys.path.insert(0, os.path.join(ROOT, "server"))
            import scram
            r = api(a.base, "GET", "/demo")
            if not (r or {}).get("joinCode"):
                st, d = scram.login(a.base, *a.admin.split(":", 1), admin=True)
                made = api(a.base, "POST", "/admin/join/code", d.get("token"), {})
                print("  登録コード: %s" % (((made or {}).get("join") or {}).get("code") or made))
        except Exception as e:
            print("  登録コード: 作れませんでした（%s）。コードの画面は空のまま撮ります" % e)
    for fmt in [f for f in FORMATS if not a.only or f in a.only.split(",")]:
        print("撮る: %s（生徒 %s）" % (fmt, student), flush=True)
        shots = capture(a.base, student, fmt, shots_dir, student2)
        print("  写し %d 枚: %s" % (len(shots), " ".join(sorted(shots))), flush=True)
        out = os.path.join(a.out, "intro-%s.mp4" % fmt)
        if a.preview:
            preview(fmt, shots, os.path.join(a.work, "video-preview")); continue
        n = render(fmt, shots, out, ffmpeg)
        print("  → %s（%d コマ・%.1f MB）" % (out, n, os.path.getsize(out) / 1e6), flush=True)


if __name__ == "__main__":
    main()
