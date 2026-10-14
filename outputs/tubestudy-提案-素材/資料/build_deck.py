# -*- coding: utf-8 -*-
"""tubestudy 提案の資料（16:9・14枚）。python-pptx で組む。Google スライドに取り込んで直せる形。

体裁の決まり
  ・文は自分で行に切る（jp）。箱の端まで詰めず、句読点のあとで折る。「。」だけの行を作らない
  ・箇条書きは1つずつ別の箱に置く（段落の流れに頼らない。Google スライドで重なった）
  ・箱の幅は文字数の2割増し。字体は Noto Sans JP（Google スライドにある）
"""
import os, sys
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
SH = os.path.join(os.path.dirname(HERE), "promo", "shots")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "tubestudy-提案.pptx")

FONT = "Noto Sans JP"
NAVY = RGBColor(0x0F, 0x3F, 0x73)
BLUE = RGBColor(0x00, 0x4E, 0x93)
BLUE2 = RGBColor(0x0A, 0x6F, 0xC7)
YEL = RGBColor(0xF9, 0xB9, 0x00)
INK = RGBColor(0x17, 0x15, 0x0F)
INK2 = RGBColor(0x5B, 0x5A, 0x55)
INK3 = RGBColor(0x8A, 0x89, 0x84)
PAPER = RGBColor(0xFF, 0xFF, 0xFF)
TINT = RGBColor(0xF2, 0xF4, 0xF8)
TINT2 = RGBColor(0xE8, 0xEE, 0xF7)
LINE = RGBColor(0xD9, 0xDD, 0xE5)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
ICE = RGBColor(0xCA, 0xDC, 0xFC)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


# ---------------------------------------------------------------- 文を行に切る
NO_START = "、。」）】,.!?！？ー"
NO_END = "「（【"


def cap(w, pt):
    """幅 w インチ・pt の字で、1行に置ける全角の字数（両側の余白 0.1in と 5% の余裕を引く）"""
    return max(4, int((w - 0.2) * 72 / pt * 0.95))


def jp(text, n):
    """text を n 字までの行に切る。改行は「、。」）」のあとを優先。「\\n」はそのまま行を分ける。"""
    out = []
    for para in text.split("\n"):
        cur = ""
        i = 0
        while i < len(para):
            cur += para[i]
            i += 1
            if len(cur) >= n:
                # 次の字が行頭に置けない字なら、もう1字だけ足す
                while i < len(para) and para[i] in NO_START:
                    cur += para[i]
                    i += 1
                j = -1
                for k in range(len(cur) - 1, int(n * 0.45), -1):
                    if cur[k - 1] in "、。」）" and k < len(cur):
                        j = k
                        break
                if j <= 0:
                    j = len(cur)
                    if cur[j - 1] in NO_END:
                        j -= 1
                out.append(cur[:j])
                cur = cur[j:]
        if cur:
            out.append(cur)
    return out


# ---------------------------------------------------------------- 部品
def set_font(run, size, bold=False, color=INK, name=FONT):
    f = run.font
    f.name = name
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rPr, qn(tag))
        el.set("typeface", name)


def text(slide, x, y, w, h, lines, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.15, margin=0):
    """lines … [ [(文字, サイズ, 太字, 色), …], … ] 1行が1段落。文字列だけなら (文字, 18, False, INK)"""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(margin)
    first = True
    for line in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        p.line_spacing = spacing
        runs = line if isinstance(line, list) else [line]
        for r in runs:
            if isinstance(r, str):
                r = (r, 18, False, INK)
            s, size, bold, color = (list(r) + [None] * 4)[:4]
            run = p.add_run()
            run.text = s
            set_font(run, size or 18, bool(bold), color or INK)
    return tb


def para(slide, x, y, w, s, size, color=INK2, bold=False, spacing=1.35, align=PP_ALIGN.LEFT):
    """文を切って置く。高さ（インチ）を返す"""
    lines = jp(s, cap(w, size))
    h = len(lines) * size / 72.0 * spacing + 0.08
    text(slide, x, y, w, h, [[(l, size, bold, color)] for l in lines], align=align, spacing=spacing)
    return h


def rect(slide, x, y, w, h, fill, line=None, radius=None, shape=None):
    sp = slide.shapes.add_shape(shape or (MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE),
                                Inches(x), Inches(y), Inches(w), Inches(h))
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(0.75)
    if radius is not None and sp.adjustments:
        sp.adjustments[0] = radius
    sp.shadow.inherit = False
    sp.text_frame.text = ""
    return sp


def round_pic(pic, adj=0.04):
    spPr = pic._element.spPr
    geom = spPr.find(qn("a:prstGeom"))
    geom.set("prst", "roundRect")
    av = geom.find(qn("a:avLst"))
    if av is None:
        av = etree.SubElement(geom, qn("a:avLst"))
    for c in list(av):
        av.remove(c)
    g = etree.SubElement(av, qn("a:gd"))
    g.set("name", "adj"); g.set("fmla", "val %d" % int(adj * 50000))


def screen(slide, path, x, y, w, crop_bottom=0.0, border=True, adj=0.03, crop_top=0.0):
    pic = slide.shapes.add_picture(os.path.join(SH, path), Inches(x), Inches(y), width=Inches(w))
    if crop_bottom or crop_top:
        pic.crop_bottom = crop_bottom
        pic.crop_top = crop_top
        pic.height = int(pic.height * (1 - crop_bottom - crop_top))
    round_pic(pic, adj)
    if border:
        pic.line.color.rgb = LINE
        pic.line.width = Pt(0.75)
    return pic


def phone(slide, path, x, y, w, crop_bottom=0.0, crop_top=0.0):
    pad = w * 0.035
    pic = slide.shapes.add_picture(os.path.join(SH, path), Inches(x + pad), Inches(y + pad), width=Inches(w - 2 * pad))
    if crop_bottom or crop_top:
        pic.crop_bottom = crop_bottom
        pic.crop_top = crop_top
        pic.height = int(pic.height * (1 - crop_bottom - crop_top))
    h = Emu(pic.height).inches + 2 * pad
    bezel = rect(slide, x, y, w, h, RGBColor(0x11, 0x11, 0x11), radius=0.12)
    sp = bezel._element; sp.getparent().remove(sp)
    pic._element.addprevious(sp)
    round_pic(pic, 0.09)
    return h


def mark(slide, x, y, size):
    box = rect(slide, x, y, size, size, BLUE, radius=0.24)
    rect(slide, x + size * 0.19, y + size * 0.25, size * 0.62, size * 0.078, YEL, radius=0.5)
    ring_d = size * 0.44
    o = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x + (size - ring_d) / 2), Inches(y + size * 0.53 - ring_d / 2 + size * 0.02), Inches(ring_d), Inches(ring_d))
    o.fill.background()
    o.line.color.rgb = WHITE
    o.line.width = Pt(size * 5.2)
    o.shadow.inherit = False
    return box


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


def page(slide, n):
    text(slide, 12.3, 7.05, 0.8, 0.3, [[(str(n), 10, False, INK3)]], align=PP_ALIGN.RIGHT)


def title(slide, s, sub=None, y=0.55):
    text(slide, 0.7, y, 12, 0.9, [[(s, 34, True, INK)]], spacing=1.1)
    if sub:
        text(slide, 0.72, y + 0.82, 11.8, 0.5, [[(sub, 15, False, INK2)]])


def items(slide, x, y, w, rows, size=16, gap=0.26):
    """(見出し, 説明) を1つずつ別の箱に。重ならないよう高さを数えて置く"""
    for h, d in rows:
        hh = para(slide, x, y, w, h, size, INK, bold=True, spacing=1.2)
        y += hh + 0.02
        dh = para(slide, x, y, w, d, size - 3, INK2, spacing=1.35)
        y += dh + gap
    return y


def num_circle(slide, x, y, d, n, fill=BLUE):
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    c.fill.solid(); c.fill.fore_color.rgb = fill; c.line.fill.background(); c.shadow.inherit = False
    tf = c.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = str(n); set_font(r, int(d * 22), True, WHITE)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    return c


def bg(slide, color):
    f = slide.background.fill
    f.solid(); f.fore_color.rgb = color


def pill(slide, x, y, w, h, s, size=14):
    rect(slide, x, y, w, h, TINT2, radius=0.5)
    text(slide, x, y, w, h, [[(s, size, True, BLUE)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def arrow(slide, x, y, w, h, size=16):
    text(slide, x, y, w, h, [[("→", size, True, INK3)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


n = 0


def new(bgc=PAPER):
    global n
    n += 1
    s = prs.slides.add_slide(BLANK); bg(s, bgc)
    if bgc == PAPER:
        page(s, n)
    return s


# ============================ 1 表紙 ============================
s = new(NAVY)
mark(s, 0.9, 1.35, 1.35)
text(s, 2.55, 1.42, 6, 1.2, [[("tube", 44, True, WHITE), ("study", 44, True, YEL)]], spacing=1.0)
text(s, 0.9, 3.15, 11.5, 1.6, [[("宿題と成績を、仕組みにする。", 44, True, WHITE)]], spacing=1.15)
text(s, 0.92, 4.35, 11, 0.6, [[("講師の時間を授業へ。一人ひとりに向き合う「仕組み」を、ロンドン校から。", 18, False, ICE)]])
text(s, 0.92, 6.35, 8, 0.5, [[("早稲田アカデミー ロンドン校 への提案　　秋 建太郎　　2026年9月", 12, False, RGBColor(0xA9, 0xBE, 0xDD))]])
notes(s, "本日は、ロンドン校の宿題チェックと成績管理を「仕組み」にするサービス、tubestudy のご提案です。5分ほどお時間をください。")

# ============================ 2 いまの課題 ============================
s = new()
title(s, "いま、講師の時間はどこへ消えているか", "授業という、いちばん大切なところに時間がのこりにくい")
cards = [("宿題チェック", "紙の山を1枚ずつ。\n見落としとチェック忘れ。\n「見たかどうか」を\n思い出す時間。"),
         ("成績管理", "数十人の得意・苦手を、\n暗記とベテランの勘で。\n人が変わると、\n引き継ぎが大変。"),
         ("保護者対応", "提出したか、どこが弱いか。\n電話とメールで、\n一人一人に何度も。")]
for i, (h, d) in enumerate(cards):
    x = 0.7 + i * 4.05
    rect(s, x, 2.1, 3.75, 3.5, TINT, radius=0.08)
    num_circle(s, x + 0.35, 2.45, 0.55, i + 1)
    text(s, x + 0.35, 3.2, 3.1, 0.6, [[(h, 22, True, INK)]])
    para(s, x + 0.35, 3.85, 3.1, d, 14, INK2, spacing=1.45)
text(s, 0.7, 6.0, 12, 0.5, [[("生徒が増えるほど、この時間も増える。", 20, True, BLUE)]])
text(s, 0.72, 6.5, 12, 0.5, [[("マンパワーで支えることは、持続可能とはいいにくい。", 16, False, INK2)]])
notes(s, "まず現状です。宿題チェックは紙の山を1枚ずつで、見落としやチェック忘れが起きます。成績の把握は暗記とベテランの勘に頼りがちで、人が変わると引き継ぎが大変です。保護者には一人一人に何度も。生徒が増えるほど、この時間は増えます。")

# ============================ 3 目的 ============================
s = new()
title(s, "目的は3つ")
goals = [("講師の時間を、授業へ", "宿題チェック・成績管理の負担を軽くし、\nいちばん大切な授業にリソースを投下できるように。"),
         ("一人ひとりに、本当に向き合う「仕組み」", "得意・苦手・提出・先生のことばが生徒ごとに残り、\n誰が担当しても同じ質で向き合える。"),
         ("マンパワーではなく、仕組みで生徒数を支える", "人を増やさずに、コンスタントに生徒を\n受け入れられる土台をつくる。")]
for i, (h, d) in enumerate(goals):
    y = 1.85 + i * 1.55
    num_circle(s, 0.75, y + 0.05, 0.62, i + 1, YEL if i == 1 else BLUE)
    text(s, 1.6, y - 0.02, 7.8, 0.6, [[(h, 24, True, INK)]])
    para(s, 1.62, y + 0.55, 7.6, d, 14, INK2)
rect(s, 9.55, 1.7, 3.1, 4.9, TINT, radius=0.08)
mark(s, 10.35, 2.35, 1.5)
text(s, 9.55, 4.15, 3.1, 0.6, [[("tube", 26, True, BLUE), ("study", 26, True, YEL)]], align=PP_ALIGN.CENTER, spacing=1.0)
para(s, 9.8, 4.85, 2.6, "講師はパソコン、\n生徒と保護者はスマホ。\n1つのアプリで、\n紙のクラスと併走できる。", 12, INK2, align=PP_ALIGN.CENTER)
notes(s, "目的は3つです。講師の時間を授業へ。一人ひとりに本当に向き合う仕組み。そして、人ではなく仕組みで生徒数を支えること。tubestudy は講師がパソコン、生徒と保護者がスマホで使う1つのアプリで、紙のクラスと併走しながら入れられます。")

# ============================ 4 全体像 ============================
s = new()
title(s, "全体像：紙の宿題は、写真で行き来する", "講師はパソコンで評価、生徒はスマホで撮って送る。保護者は同じアプリの中に入口がある")
screen(s, "t-home.png", 0.7, 1.9, 6.3, crop_bottom=0.35)
phone(s, "s-home.png", 7.55, 1.8, 2.0, crop_bottom=0.35)
phone(s, "s-parent.png", 10.2, 1.8, 2.0, crop_bottom=0.35)
text(s, 0.7, 4.7, 6.3, 0.4, [[("講師：今日やること → 宿題チェック → 評価・添削", 14, True, INK)]])
para(s, 7.55, 4.7, 2.4, "生徒：撮って送る。\n先生のことばが届く", 12, INK, bold=True, spacing=1.3)
para(s, 10.2, 4.7, 2.9, "保護者：提出・評価・伸びを、\nいつでも", 12, INK, bold=True, spacing=1.3)
for i, t in enumerate(["出す", "写真で提出", "評価・添削を返す", "先生から／保護者へ"]):
    x = 0.7 + i * 3.1
    pill(s, x, 5.55, 2.75, 0.6, t)
    if i < 3:
        arrow(s, x + 2.75, 5.55, 0.35, 0.6)
rect(s, 0.7, 6.35, 11.9, 0.55, TINT, radius=0.08)
text(s, 0.7, 6.35, 11.9, 0.55, [[("宿題のほとんどは紙のまま。", 13, True, INK), ("　英単語や漢字など、アプリでできる暗記系の宿題もあり、紙の宿題をアプリで補強できる。", 13, False, INK2)]],
     align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "全体像です。講師が宿題を出すと、生徒はノートを写真に撮って送ります。講師はパソコンで評価し、赤を入れた紙を返せます。その結果は生徒の「先生から」と、保護者の画面に届きます。宿題のほとんどは紙のままですが、英単語や漢字のような暗記系はアプリでもでき、紙を補強できます。")

# ============================ 5 講師① 簡便さ ============================
s = new()
title(s, "講師①　宿題チェックの簡便さ", "見るべき宿題が、いちばん上に")
screen(s, "t-home.png", 0.7, 2.0, 7.6, crop_bottom=0.3)
items(s, 8.75, 2.05, 4.0, [
    ("見るべき回だけが「今日やること」", "期限が来て、写真が出ていて、\n評価がまだ。その回だけが上に並ぶ。"),
    ("未評価の人数がひと目で", "輪と数字。開く前から、\nあと何人かが分かる。"),
    ("保護者のメッセージも同じ画面に", "返事もここから。"),
], size=16)
notes(s, "講師の画面です。開いた瞬間に、見るべき宿題だけが「今日やること」として上に並びます。未評価の人数が輪で見えるので、あと何人かで迷いません。保護者からのメッセージも同じ画面に届きます。")

# ============================ 6 なぞるだけ ============================
s = new()
title(s, "なぞるだけで、評価がつく", "マスに乗せると大きく出て、1〜5 を押すだけ。印刷して赤を入れ、PDF で返す")
screen(s, "t-check-09.png", 0.7, 2.0, 8.4, crop_bottom=0.02)
items(s, 9.5, 2.05, 3.3, [
    ("乗せると、右に大きく", "クラス全員のノートが並ぶ。\n矢印をなぞるだけ。"),
    ("1〜5 を押す", "キーの1〜5でも。\n束の全件に同じ評価。"),
    ("PDF で開く（印刷）", "赤を入れて撮り直し、\n「添削を返す」で生徒へ。"),
    ("対面の生徒の紙も取り込める", "回収した紙をスキャンして、\n同じ画面で。"),
], size=16)
notes(s, "宿題チェックの画面です。クラス全員のノートがマスで並び、マウスをなぞると右に大きく出ます。評価は1〜5を押すだけ。印刷して赤を入れ、撮り直して「添削を返す」で生徒に届きます。対面の生徒の紙も同じ画面で扱えます。")

# ============================ 7 確実さ ============================
s = new()
title(s, "講師②　確実さ", "チェックし忘れがなくなり、どこが間違いかまで残る")
screen(s, "t-check-quiz.png", 0.7, 2.0, 7.0, crop_bottom=0.02)
phone(s, "s-ret.png", 8.1, 1.9, 2.05, crop_bottom=0.25)
items(s, 10.45, 2.05, 2.5, [
    ("忘れない", "未評価は数で残り、\n翌日も「今日やること」に\n出続ける。"),
    ("どこが違うかが残る", "赤を入れた答案と、ひとこと。\n生徒は「添削された答案」を\n開ける。"),
    ("小テストも提出箱で", "漢字・計算・英単語。\nオンラインの子は写真、\n対面の子は先生が取り込む。"),
], size=14)
notes(s, "確実さです。未評価は数で残り、翌日も「今日やること」に出続けるので、チェック忘れが起きません。赤を入れた答案とひとことが生徒に届き、どこが間違っていたかが記録として残ります。授業内の小テストも提出箱として同じ道で回せます。")

# ============================ 8 パーソナライズ ============================
s = new()
title(s, "講師③　パーソナライズ", "苦手な単元・問題が生徒ごとにたまり、毎日テストで苦手をつぶす")
screen(s, "t-insight.png", 0.7, 2.0, 7.9, crop_bottom=0.06)
phone(s, "s-prep-daily-full.png", 8.95, 1.9, 1.95, crop_top=0.33, crop_bottom=0.49)
items(s, 11.05, 2.05, 2.0, [
    ("理解度", "単元ごと、\n生徒ごとに蓄積。"),
    ("苦手つぶし", "テストで落とした\n単元を、毎日テスト\nで再テスト。"),
    ("提案", "50%以下の生徒に\n「1人に宿題を足す」。\nプリセットから\n柔軟に。"),
], size=13)
notes(s, "パーソナライズです。単元ごとの理解度が生徒単位でたまり、生徒のスマホには苦手な単元から毎日テストが出ます。講師の画面には理解度が低い生徒と苦手単元が提案として出るので、そこからプリセットで宿題を柔軟に足せます。")

# ============================ 9 成績管理の仕組み化 ============================
s = new()
title(s, "成績管理の仕組み化", "暗記やベテランに頼らず、数十人を1人単位で厳密に")
screen(s, "t-insight-full.png", 0.7, 2.0, 7.2, crop_top=0.535, crop_bottom=0.115)
phone(s, "s-prep-daily-full.png", 9.6, 1.9, 2.3, crop_bottom=0.6)
text(s, 0.7, 5.85, 8.3, 0.4, [[("生徒 × 単元の理解度が、1人単位で残る。", 15, True, INK)]])
para(s, 0.72, 6.25, 8.3, "黄色を押すと、その生徒への提案。塾内テストの結果も取り込める。\n担当が変わっても、積み上げが消えない。", 13, INK2, spacing=1.3)
text(s, 9.6, 5.85, 3.5, 0.4, [[("組み分けテスト対策は、自動で。", 15, True, INK)]])
para(s, 9.62, 6.25, 3.3, "苦手から問題を作り、紙に印刷、\nカメラで丸つけ。", 13, INK2, spacing=1.3)
notes(s, "成績管理です。生徒と単元の理解度が1人単位で残り、塾内テストの結果も取り込めます。黄色を押せばその生徒への提案が出て、宿題を調整できます。組み分けテスト対策の問題も苦手から自動で作れます。担当が変わっても、積み上げが消えません。")

# ============================ 10 生徒にとって ============================
s = new()
title(s, "生徒にとって：宿題が軽くなり、続けたくなる", "自分だけの問題集が、毎日すこしずつ育つ")
cols = [("s-home-full.png", 0.075, 0.675, "宿題が、ひと目で", "今日やること・今週・来週が並ぶ。\n撮って送るだけで「出した」が残る。"),
        ("s-daily-full.png", 0.60, 0.04, "続けたくなる", "続けた記録と、日替わりの一言。\n先生からの評価とことばが、そのまま届く。"),
        ("s-prep-daily-full.png", 0.19, 0.49, "自分だけの問題集", "まちがえた問題がたまり、\n毎日テストと組み分け対策に出てくる。")]
for i, (img, ct, cb, h, d) in enumerate(cols):
    x = 0.7 + i * 4.15
    phone(s, img, x + 0.75, 1.85, 2.4, crop_top=ct, crop_bottom=cb)
    text(s, x, 5.3, 3.9, 0.45, [[(h, 17, True, INK)]])
    para(s, x, 5.75, 3.9, d, 12, INK2, spacing=1.4)
notes(s, "生徒にとっては、宿題がひと目で分かり、撮って送るだけで「出した」が残ります。続けた記録や日替わりの一言、先生からの評価とことばが届くので、続けたくなります。そしてまちがえた問題がたまって、毎日テストと組み分け対策に出てくる。自分だけの問題集が育ちます。")

# ============================ 11 保護者 ============================
s = new()
title(s, "保護者へ提供する安心感", "成績・提出・先生のことばをリアルタイムで。質問も写真も、アプリの中で")
phone(s, "s-parent.png", 0.9, 1.95, 2.35, crop_bottom=0.2)
phone(s, "s-fb-math.png", 3.65, 1.95, 2.35, crop_bottom=0.2)
phone(s, "s-ret.png", 6.4, 1.95, 2.35, crop_bottom=0.2)
items(s, 9.3, 2.05, 3.6, [
    ("いつでも確認", "成績の伸び（％つき）、提出状況、\n先生からのフィードバック。"),
    ("質問も宿題添付も、簡単", "教科を選んで先生に送る。\n写真は撮って送るだけ。"),
    ("向き合っている、が伝わる", "赤を入れた答案と、ひとことが\n手元に残る。"),
], size=15)
notes(s, "保護者です。お子さんの成績の伸び、提出状況、先生のフィードバックをリアルタイムで確認できます。質問も宿題の写真も、アプリの中で簡単に。赤を入れた答案とひとことが手元に残るので、「一人ひとりに向き合っている」ことがそのまま伝わります。")

# ============================ 12 簡単さ ============================
s = new()
title(s, "あっと驚く簡単さ", "覚えることがない。紙のクラスと、そのまま併走できる")
big = [("1回", "評価は、押すだけ", "なぞって、1〜5。\n束の全件に同じ評価が入る。"),
       ("撮って送る", "写真の提出", "撮る → たまる → 送る。\n見開きも2枚で。\nパソコンとスマホを\n行き来しても常に最新。"),
       ("コースごと", "導入は選べる", "講師が「使う」クラスを選ぶ。\n紙のままのクラスと\n半年以上混在して動く。")]
for i, (nm, h, d) in enumerate(big):
    x = 0.7 + i * 3.1
    rect(s, x, 2.05, 2.85, 3.7, TINT, radius=0.08)
    text(s, x + 0.2, 2.3, 2.55, 0.8, [[(nm, 30, True, BLUE)]])
    text(s, x + 0.2, 3.3, 2.55, 0.5, [[(h, 17, True, INK)]])
    para(s, x + 0.2, 3.85, 2.55, d, 12, INK2, spacing=1.4)
phone(s, "s-stage.png", 10.35, 1.95, 2.3, crop_bottom=0.25)
notes(s, "簡単さです。評価は押すだけ。写真は撮って送るだけで、パソコンとスマホを行き来しても常に最新です。導入はコースごとに選べるので、紙のままのクラスと併走しながら少しずつ広げられます。")

# ============================ 13 進め方 ============================
s = new()
title(s, "進め方：ロンドン校で、小さく始める", "年内に試して、結果で判断していただく")
steps = [("試験導入（年内）", "ロンドン校の一部コースで、紙と併走。\n講師の手間と、生徒・保護者の反応を\n確かめる。"),
         ("本導入（2027年1月〜）", "手応えがあれば、1月からロンドン校の\n全コースへ。成績管理と保護者対応まで\n仕組みに乗せる。")]
for i, (h, d) in enumerate(steps):
    x = 0.7 + i * 6.2
    num_circle(s, x, 2.3, 0.8, i + 1, BLUE if i == 0 else BLUE2)
    text(s, x, 3.35, 5.4, 0.6, [[(h, 22, True, INK)]])
    para(s, x, 3.95, 5.4, d, 14, INK2, spacing=1.4)
    if i == 0:
        arrow(s, x + 5.5, 2.3, 0.6, 0.8, size=22)
rect(s, 0.7, 5.95, 11.9, 0.9, TINT2, radius=0.08)
text(s, 0.7, 5.95, 11.9, 0.9, [[("導入に必要なのは、講師のパソコンと、生徒のスマホだけ。名簿はCSVで取り込み、記録は校舎ごとに分けて保管。", 14, False, INK)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "進め方です。まず年内、ロンドン校の一部コースで紙と併走しながら試験導入させてください。手応えがあれば、来年1月からロンドン校の全コースで本導入。成績管理と保護者対応まで仕組みに乗せます。")

# ============================ 14 最後に ============================
s = new(NAVY)
text(s, 0.9, 1.7, 11.5, 1.6, [[("先生の時間を、授業へ。", 48, True, WHITE)]])
text(s, 0.92, 3.1, 11.5, 1.0, [[("一人ひとりに向き合う「仕組み」を、ロンドン校から。", 22, False, ICE)]])
rect(s, 0.9, 4.45, 7.4, 1.1, RGBColor(0x1A, 0x4F, 0x86), radius=0.08)
text(s, 1.2, 4.45, 6.9, 1.1, [[("まず、年内の試験導入をご検討ください。", 20, True, WHITE)]], anchor=MSO_ANCHOR.MIDDLE)
mark(s, 11.15, 4.4, 1.2)
text(s, 0.92, 6.35, 9, 0.5, [[("秋 建太郎　　条件・時期は別途ご相談させてください", 12, False, RGBColor(0xA9, 0xBE, 0xDD))]])
notes(s, "最後に。先生の時間を授業へ。一人ひとりに向き合う仕組みを、ロンドン校から。まずは年内の試験導入をご検討ください。条件や時期は別途ご相談させてください。ありがとうございました。")

prs.save(OUT)
print("saved", OUT, "slides", len(prs.slides))
