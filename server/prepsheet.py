#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""総復習テスト対策の紙 ―― 教科ごとに A4たて 数枚。

なぜ PDF を直接作らないか
------------------------
PDF を組む道具（reportlab など）を1つ増やすと、日本語のフォントを
サーバに置き、行分けを自分で書き、数式の上付き・下付きを自分で並べる
ことになる。**そこは本筋ではない。**

代わりに、印刷用の HTML を返す。ブラウザの「PDFにする」で
そのまま A4 の問題用紙になる。

  ・@page で A4たて・余白を指定してある
  ・段組は CSS の columns（2段）。行の途中で切れないようにしてある
  ・画面で見るとふつうの一覧、印刷すると本番と同じ形の問題用紙になる
  ・「解答らん」と「解答・解説」は別ページ（改ページを入れてある）

なぜ A3 1枚をやめたか
--------------------
本番の組み分けテストは **A4たて・1教科ずつ**である。
A3よこ1枚に5教科を詰めた紙は、練習にならない ―― 本番と紙の形が
違うと、時間配分の感覚がそのまま使えない。

1枚に収めるのをやめたことで、**「何問まで載るか」を見積もる計算が
まるごと要らなくなった。** 以前はここで1問あたりの高さを実測して
足し込んでいたが、教科によって外れ、3回作り直している。
いまの上限は「解答らんのマスの数」だけで、これは見積もりではなく
数えられる数である。

フォントは端末のものを使う。サーバにフォントを置かない ――
置いた瞬間、ライセンスと容量の話が始まる。

出すもの
--------
1枚目  問題（左右2段）
2枚目  解答と解説（同じ番号で引ける）
"""

import html
import re
import io
import os
import time

TIER_NAME = {"advanced": "上位編", "basic": "基本編"}

CSS = """
:root{ --ink:#111; --sub:#555; --line:#d8d8d8; --accent:#005BAC; }
*{ box-sizing:border-box }
html,body{ margin:0; padding:0; background:#f2f2f4; color:var(--ink);
  font-family:"Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic",
  "Noto Sans JP",sans-serif; }
/* 1枚 ＝ A4 1ページ。**画面と紙で、まったく同じ寸法にする。**

   紙の余白は @page ではなく、この padding で作る（@page は margin:0）。
   こうすると 1枚は どちらの媒体でも 210×297mm の箱のままになる。

   前は紙のときだけ「@page の余白12mm ＋ .sheet は padding:0」に
   切り替えていた。すると紙の上では箱が 186×273mm になり、

     ・割りつけを画面の寸法で決めているのに、紙では箱が小さい
       → 中身が入りきらず、ブラウザが縮めて刷る（字が小さくなる）
     ・**解答らんは中身がすべて絶対配置**なので、高さの指定を外すと
       高さ0にたたまれ、次の紙と重なって刷られる（実際に重なった）
     ・解答らんの位置合わせ四角形は「箱の端から12mm」で置いてあり、
       箱が縮むと、カメラが期待する場所とずれる

   寸法を1つにすれば、この3つは同時に消える。 */
.sheet{ background:#fff; width:210mm; min-height:297mm; margin:12px auto;
  padding:12mm; }
/* 割りつけ済みのページは、高さも A4 にそろえる（画面で1枚に見える）。 */
/* 割りつけ済みの1枚。高さは A4 ちょうどに固定する。
   縦に並べて、脚（TUBE study／何枚目）を下端に落とす。
   こうすると **脚の上端＝中身に使える高さ** になり、
   割りつけ側はそれを測るだけでよい（計算しない）。 */
.sheet.page{ height:297mm; min-height:297mm;
  display:flex; flex-direction:column }
/* **残りの高さいっぱいに広げる。** flex:0 0 auto のまま
   .cols2 に height:100% を書いていたので、100% が「ページ全体（297mm）」に
   なり、見出しのぶんだけ下にはみ出していた。実際、縦書きの本文が
   紙の下端を突き抜けて 次の紙に重なって刷られた。
   flex:1 1 auto なら「残り」に広がり、100% はその残りを指す。 */
.sheet.page .cols2{ flex:1 1 auto; min-height:0 }
.sheet.page .foot{ margin-top:0; flex:0 0 auto }

/* 段組み。**CSS の columns は使わない。**
   columns はページの割りつけをブラウザにまかせることになり、
   画面では1本の長い紙になり、紙のほうも browser まかせになる。
   実際、問題用紙が 694mm（A4 2.3枚分）の1枚ものとして出ていた。
   いまは app/js/sheet-print.js が実測して段と頁に配る。 */
.cols2{ display:flex; gap:8mm; align-items:flex-start }
.cols2 .col{ flex:1 1 0; min-width:0 }
.cols2 .col + .col{ border-left:.6pt solid var(--line); padding-left:8mm }
/* 続きのページの見出し。1ページ目の大きな見出しは くり返さない。 */
.rhead{ display:flex; justify-content:space-between; align-items:baseline;
  border-bottom:.8pt solid var(--line); padding-bottom:2mm; margin-bottom:3mm;
  font-size:9pt; color:var(--sub) }
.pno{ font-size:8.5pt; color:var(--sub); text-align:right; margin-top:3mm }
.head{ display:flex; align-items:flex-end; justify-content:space-between;
  gap:12mm; border-bottom:1.6pt solid var(--ink); padding-bottom:3mm; }
.h-l h1{ font-size:19pt; margin:0; letter-spacing:-.01em }
.h-l .sub{ font-size:9.5pt; color:var(--sub); margin-top:1.5mm }
.h-r{ text-align:right; font-size:9pt; color:var(--sub); line-height:1.7;
  white-space:nowrap; flex:none }
.h-r b{ color:var(--ink); font-size:11pt; white-space:nowrap }
.name{ margin-top:2mm; border:1pt solid var(--line); border-radius:2mm;
  padding:2mm 3mm; font-size:9pt; color:var(--sub); }
.name i{ font-style:normal; display:inline-block; min-width:38mm;
  border-bottom:.8pt solid var(--line); margin-left:2mm }

/* 段組。**A4たてでは2段**。
   1段 87mm・約20字。1段にすると1行が186mmになり、目が戻れない。
   ページをまたぐ段組みは、ブラウザが左段→右段→次ページの順に流す。 */
/* もとの流し込み。**ふだんは app/js/sheet-print.js が .cols2 に組み直す。**
   ここに残してあるのは、その JS が読めなかったときの逃げ道である
   （割りつけは崩れるが、刷れなくなるよりはよい）。 */
.cols{ columns:2; column-gap:8mm; column-rule:.6pt solid var(--line);
  margin-top:4mm }
.q{ break-inside:avoid; page-break-inside:avoid; margin:0 0 4.2mm;
  padding-left:9mm; position:relative; font-size:10pt; line-height:1.55 }
.q .no{ position:absolute; left:0; top:0; width:7.5mm; text-align:right;
  font-size:9pt; color:var(--accent); font-weight:600 }
/* 教科の1字。5教科の紙でだけ出る。問題文の頭に置き、地を薄く敷く。
   色分けはしない ―― 白黒で刷られたら見分けがつかなくなる。 */
.q .sj{ display:inline-block; min-width:4.4mm; padding:0 0.6mm;
  margin-right:1.2mm; text-align:center; font-size:7.5pt;
  border-radius:1mm; background:#EDEDF0; color:#333 }
.q .t{ display:block }
.q .ch{ margin-top:1.2mm; font-size:9pt; color:var(--sub); }
/* 図。**紙の上では黒い線。** 絵の色は currentColor なので、ここで決める。
   1問ぶんの幅は 88mm しかないので、絵は 46mm で頭打ちにする ――
   大きくすると1問で1段を使いきり、60問が紙に載らなくなる。 */
/* 答えを書く場所。**紙は解くための紙である。**
   選択肢だけ並べても、算数・数学は途中式を書くところが無いと解けない。
   高さは教科で変える ―― 数学はいちばん広く、暗記ものは1行ぶん。
   罫線は引かない（枠線は基本悪）。下端に細い線だけ置いて、
   「ここまでが1問」が分かるようにする。 */
.q .work{ display:block; margin-top:1.5mm; height:7mm;
  border-bottom:.4pt solid #e6e6e6 }
.q.s-math .work{ height:30mm }
.q.s-japanese .work{ height:8mm }
.q.s-science .work{ height:9mm }
.q.s-social .work{ height:8mm }
.q.s-english .work{ height:7mm }
/* 1段組みの紙（数学）。1問の幅いっぱいを 途中式に使えるようにする。 */
.cols2.one{ display:block }
.cols2.one .col + .col{ display:none }

/* ---- 縦書き（国語）----------------------------------------------
   国語の試験は 縦書きで出る。横書きで練習させると、
   本番で 目の動きが 変わってしまう。

   段組みは使わない。**縦書きでは、高さを決めれば 行は自然に左へ折り返す。**
   だから中身を1つの箱に入れ、高さを紙いっぱいにするだけでよい。
   割りつけ（app/js/sheet-print.js）は、横書きなら「高さ」、
   縦書きなら「幅」がはみ出したかを見る ―― 伸びる向きが90度ちがう。 */
.cols2.tate{ display:block; writing-mode:vertical-rl;
  text-orientation:upright; height:100% }
.cols2.tate .col{ height:100% }
/* ---- 国語は A4 よこ ------------------------------------------------
   縦書きは 行が上から下へ流れ、**行が左へ積み上がる**。
   だから必要なのは 紙の「はば」である。たてA4だと 186mm しかなく、
   1枚に4問しか入らない。よこA4なら 273mm 使えて、実際の国語の
   試験と同じ形になる（本文が右、設問が左へ続く）。

   解答らん（カメラで読む紙）は たてのまま。**そこは触らない** ――
   位置合わせの寸法を変えると、読み取りが総崩れになる。 */
.sheet.page.tate{ width:297mm; height:210mm; min-height:210mm; page:yoko }
.cols2.tate .col + .col{ display:none }
/* 縦の中で、**問題番号だけ**を横に組む（縦中横）。
   選択肢にもかけたら、選択肢の文まるごとが1文字ぶんに潰れて読めなくなった。
   かけてよいのは 2〜3桁の数字だけである。 */
.cols2.tate .no{ text-combine-upright:all; -webkit-text-combine:horizontal }
.cols2.tate .q{ padding-left:0; padding-top:9mm; margin:0 0 4mm 0 }
.cols2.tate .q .no{ position:absolute; top:0; left:auto; right:0;
  width:auto; text-align:center }
/* 選択肢は 続けて流す。**1つずつ行を変えない。**
   縦書きでは「行を変える」＝1行ぶん横に太る。4択を4行にすると
   1問で 20mm 太り、1枚に4問しか入らなくなる（実際そうなった）。 */
.cols2.tate .q .ch span{ display:inline; margin:0 0 1.5em 0 }
/* 縦のときの 書きこみ場所。**幅で持つ**（横書きの高さにあたる）。 */
.cols2.tate .q .work{ margin-top:0; margin-right:1.5mm;
  height:auto; width:5mm;
  border-bottom:0; border-left:.4pt solid #e6e6e6 }
/* ---- 縦書きの組版 ------------------------------------------------
   実際の国語の試験に合わせる。**詰めない。**

     本文   10.5pt ・ 行間 1.9 ・ 段落頭は 1字下げ
     設問   10pt   ・ 行間 1.8
     選択肢 9.5pt

   前は 8.5pt / 行間1.5 まで詰めていた。たてA4の 186mm に
   本文を押しこむための数字で、読ませる紙の値ではなかった。
   よこA4（273mm）にしたので、詰める理由が無くなっている。

   **入りきらないときに字を小さくするのは、CSS ではなく
   app/js/sheet-print.js が測ってから決める。**
   教材ごとに長さが違うので、CSS に1つの数字を書いても必ず外れる。 */
.cols2.tate .bun{ margin:0 2.4mm 0 2mm; font-size:10.5pt; line-height:1.9 }
.cols2.tate .bun p{ margin:0; text-indent:1em }
.cols2.tate .q{ font-size:10pt; line-height:1.8 }
.cols2.tate .q .ch{ font-size:9.5pt; line-height:1.9 }
/* 縦のときは 見出しと脚は 横書きのまま（読み手が探す場所なので）。 */
.sheet.page.tate .head, .sheet.page.tate .rhead,
.sheet.page.tate .foot, .sheet.page.tate .name{ writing-mode:horizontal-tb }

/* 長文の本文。読ませる文章なので行間を広げる。枠は付けない。 */
.q .bun{ display:block; margin:1.6mm 0 1.2mm; font-size:9pt;
  line-height:1.75; color:#000 }
.q .bun p{ margin:0 0 1mm; text-indent:1em }
.q .zu{ display:block; margin:1.4mm 0 0.6mm; color:#000; }
.q .zu svg{ width:46mm; height:auto; }
.q .ch span{ margin-right:3.5mm; white-space:nowrap }
.q .blank{ display:inline-block; min-width:26mm;
  border-bottom:.8pt solid var(--ink); margin-left:1mm }

.brk{ break-before:page; page-break-before:always }
.ans .q{ margin-bottom:3mm }
.ans .a{ font-weight:600 }
.ans .note{ display:block; font-size:8.6pt; color:var(--sub); margin-top:.8mm }
.foot{ margin-top:6mm; border-top:.6pt solid var(--line); padding-top:2mm;
  font-size:8pt; color:var(--sub); display:flex; justify-content:space-between }

/* ---- 解答欄（マークシート）---- */
/* 位置合わせマーク。**塗りつぶした正方形**。枠だと写真でつぶれる。
   中身はすべて絶対配置なので、**箱の大きさを必ず指定する**。
   指定を外すと高さ0にたたまれ、次の紙と重なって刷られる。 */
.sheet.mark{ position:relative; padding:0;
  width:210mm; height:297mm; min-height:297mm }
.mk{ position:absolute; background:#000 }
.mwrap{ position:absolute; left:0; top:0; right:0; bottom:0 }
.mhead{ position:absolute; left:12mm; top:24mm; right:12mm;
  display:flex; align-items:flex-end; justify-content:space-between;
  border-bottom:1.2pt solid var(--ink); padding-bottom:2mm }
.mhead h1{ font-size:14pt; margin:0; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis }
.mhead .sub{ font-size:9pt; color:var(--sub) }
.mname{ position:absolute; left:12mm; top:40mm; right:12mm;
  font-size:9pt; color:var(--sub) }
.mname i{ font-style:normal; display:inline-block; min-width:44mm;
  border-bottom:.8pt solid var(--line); margin:0 6mm 0 2mm }
/* 格子そのもの。位置は %（＝位置合わせ四角形の比）で置く。 */
.agrid{ position:absolute }
.acell{ position:absolute; display:flex; align-items:center; gap:1.6mm;
  font-size:8.5pt; color:var(--sub) }
.ano{ width:7mm; text-align:right; color:var(--ink); font-weight:600 }
.abub{ display:flex; gap:2.2mm }
.abub i{ display:block; width:5mm; height:5mm; border-radius:50%;
  border:.9pt solid #444 }
.mtip{ position:absolute; left:12mm; bottom:14mm; right:12mm;
  font-size:8pt; color:var(--sub) }

@media print{
  /* **余白は 0。** 余白は .sheet の padding が作る。
     ここで余白を付けると、紙の上でだけ箱が小さくなり、
     画面で決めた割りつけと合わなくなる（そのぶん縮めて刷られる）。 */
  @page{ size:A4 portrait; margin:0 }
  /* 国語の問題用紙だけ よこ向き。名前つきページで、その紙にだけ効かせる。 */
  @page yoko{ size:A4 landscape; margin:0 }
  html,body{ background:#fff }
  /* 大きさは画面と同じまま。**外さない。** 外すと解答らんが
     高さ0にたたまれ、次の紙と重なる。

     overflow:hidden は 0.1mm の丸めを止めるため。
     箱は 210mm ちょうどなのに 中身が 210.1mm と出て、
     その 0.1mm のせいで 1枚が 2ページに割れていた。
     中身は 12mm の余白の内側に収めてあるので、これで欠けることはない。 */
  .sheet{ margin:0; box-shadow:none; overflow:hidden }
  /* 1枚ごとに改ページ。**最初の1枚の前では改ページしない。** */
  .sheet + .sheet{ break-before:page; page-break-before:always }
  .noprint{ display:none }
}
.noprint{ max-width:210mm; margin:12px auto 0; font-size:13px; color:#444 }
.noprint button{ font:inherit; padding:9px 18px; border:0; border-radius:10px;
  background:#005BAC; color:#fff; margin-right:10px; cursor:pointer }
.noprint .tip{ display:block; margin-top:4px; color:#777; font-size:12px }
"""


# 何問まで紙に載せるか。
#
# **見積もりはしない。** 上限は「解答らんのマスの数」だけ ――
# 刷った問題には必ずマスが要るからである。ページの数はブラウザが決める。
#
# 以前はここに「1問あたり17.6mm」のような実測値を並べ、A3 1枚に
# 収まる問題数を計算していた。教科ごとに外れて3回作り直している。
# 数えられる数（マスの数）だけで決めれば、外れようがない。

# ------------------------------------------------------------------
# 解答欄（マークシート）の寸法
# ------------------------------------------------------------------
# **ここが唯一の出どころ。** 刷る側（この file）と読む側（app/js/omr.js）が
# 同じ数字を見ていないと、1マスもかみ合わない。読む側へは API で渡す
# （server が SHEET を返し、画面はそれを見る）。数字を2か所に書かない。
#
# 位置は「位置合わせマークの四角形」を 0〜1 に正規化して表す。
# 紙の大きさや、写真の傾き・遠近にかかわらず、この比だけで決まる。
SHEET = {
    # 4隅のマーク（黒い正方形）の中心。ページの端から14mm。
    "markMM": 8.0,
    "marginMM": 12.0,
    "pageMM": [210.0, 297.0],          # A4たて
    # 解答欄の並び
    "cols": 4,                          # 横に並ぶ「1問ぶん」の数
    "rows": 15,                         # 縦の段数（4×15 = 60問まで）
    "opts": 4,                          # 選択肢の数（ア〜エ）
    # 位置合わせ四角形の中での、解答欄の置き場所（0〜1）
    "gridX0": 0.045, "gridY0": 0.215,
    "gridW": 0.910, "gridH": 0.720,
    # 1問ぶんの中での、いちばん左のマスの中心と、マスの間隔（0〜1・列幅比）
    "bubX0": 0.34, "bubDX": 0.205,
    "bubR": 0.062,                      # マスの半径（列幅比）
}


def sheet_geometry():
    """読む側に渡す寸法。API がそのまま返す。"""
    return dict(SHEET)


def _marks():
    """4隅の位置合わせマーク。**塗りつぶした正方形**にする。

    枠や十字だと、写真の圧縮でつぶれたときに中心が定まらない。
    面で置けば、暗い画素のかたまりの重心がそのまま中心になる。
    """
    m = SHEET["marginMM"]
    w = SHEET["markMM"]
    W, H = SHEET["pageMM"]
    pos = [(m, m), (W - m - w, m), (W - m - w, H - m - w), (m, H - m - w)]
    return "".join(
        '<div class="mk" style="left:%.1fmm;top:%.1fmm;'
        'width:%.1fmm;height:%.1fmm"></div>' % (x, y, w, w) for x, y in pos)


def answer_grid(items):
    """解答欄。1問につき「番号 ＋ ア〜エ のマス」。

    問題のページとは別の紙にする。問題は高さがまちまちなので、
    同じ紙に置くと位置が問題文の長さで動く ―― **読む側から見つけられない**。
    解答欄だけを、決まった格子に並べる。
    """
    n = len(items)
    cols, rows = SHEET["cols"], SHEET["rows"]
    cells = []
    for i in range(min(n, cols * rows)):
        c, r = i % cols, i // cols
        opts = "".join('<i></i>' for _ in range(SHEET["opts"]))
        cells.append(
            '<div class="acell" style="left:%.4f%%;top:%.4f%%;'
            'width:%.4f%%;height:%.4f%%">'
            '<span class="ano">%d</span><span class="abub">%s</span></div>'
            % (c / cols * 100.0, r / rows * 100.0,
               1.0 / cols * 100.0, 1.0 / rows * 100.0, i + 1, opts))
    return "".join(cells)


def esc(t):
    return html.escape(str(t or ""))


# 解説に <b> などのタグが混ざっている教材がある（英語）。
# 紙では飾りを使わないので落とす。**残すと「&lt;b&gt;」と刷られる。**
_TAG = re.compile(r"<[^>]+>")


def plain(t):
    return _TAG.sub("", str(t or ""))


def _q_text(item):
    """問題文。空欄（___）はそのまま下線にする。"""
    t = esc(item.get("q"))
    return t.replace("___", '<i class="blank"></i>')


_FIGS = {}


def figures():
    """図。app/content/figures.js から読む。**紙にも同じ絵を出す。**

    画面だけに絵があって紙に無いと、「図のアの部分は？」という問題が
    紙では答えようがなくなる。刷る側と読む側で同じ絵を使う。
    """
    if _FIGS:
        return _FIGS
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "app", "content", "figures.js")
    try:
        src = io.open(path, encoding="utf-8").read()
    except OSError:
        return _FIGS
    for m in re.finditer(r'"([a-z0-9-]+)":"(.*?)",\n', src, re.S):
        _FIGS[m.group(1)] = m.group(2).replace('\\"', '"').replace("\\\\", "\\")
    return _FIGS


_BUN = {}


def readings():
    """長文読解の本文。app/content/readings.js から読む。"""
    if _BUN:
        return _BUN
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "app", "content", "readings.js")
    try:
        src = io.open(path, encoding="utf-8").read()
    except OSError:
        return _BUN
    for m in re.finditer(r'^"([a-z0-9-]+)":"(.*?)",$', src, re.M):
        _BUN[m.group(1)] = (m.group(2).replace("\\n", "\n")
                            .replace('\\"', '"').replace("\\\\", "\\"))
    return _BUN


def _bun(item, prev):
    """長文の本文。**同じ本文が続くときは、2度目からは刷らない。**

    設問は1問ずつ独立しているが、紙の上で同じ600字を何度も刷る理由はない。
    paper_items が同じ本文の設問をまとめてくれているので、
    先頭の1問にだけ本文を付ける。
    """
    name = item.get("bun") or ""
    if not name or name == prev:
        return ""
    t = readings().get(name)
    if not t:
        return ""
    # **段落頭の空白は落とす。** 1字下げは CSS が付ける。
    # 青空文庫の本文は各段落の頭に全角空白が入っているので、
    # そのまま出すと CSS の1字下げと合わさって **2マス下がる**。
    # 取り込む教材ごとに癖が違うので、出す側で必ずそろえる。
    return ('<div class="bun">%s</div>'
            % "".join("<p>%s</p>" % esc(p.lstrip("\u3000 \t"))
                      for p in t.split("\n") if p.strip()))


def _fig(item):
    """問題に付ける絵。無ければ何も出さない。"""
    f = figures().get(item.get("fig") or "")
    return ('<span class="zu">%s</span>' % f) if f else ""


# 選択肢に付ける記号。
#
# ふだんは ア イ ウ エ。ただし **選択肢の中身が ア〜エ のときは番号にする。**
# 図の問題では「あしが ついているのは どの部分？ ア／イ／ウ」のように、
# 答えそのものが ア〜エ になる。そこに ア〜エ の記号を付けると
#     ア ア   イ イ   ウ ウ   エ アとウ
# と並び、どちらが記号でどちらが答えか読めなくなる。紙で実際にそうなった。
_MARK = "アイウエオカキク"
_MARK_N = "①②③④⑤⑥⑦⑧"
_POS = set("アイウエオ")


def _choice_marks(opts):
    """この問題の選択肢に付ける記号。OMR の目印（_marks）とは別物。"""
    if any(len(str(o).strip()) == 1 and str(o).strip() in _POS for o in opts):
        return _MARK_N
    return _MARK


def _choices(item):
    """選択肢。答えを混ぜて、並びは問題ごとに決める（毎回同じ並び）。"""
    dis = [d for d in (item.get("dis") or []) if d]
    if not dis:
        return ""
    opts = [item.get("ans", "")] + dis
    # 並びは問題文から決める。刷り直しても同じ並びになる。
    k = sum(ord(c) for c in str(item.get("id") or item.get("q") or ""))
    opts = opts[k % len(opts):] + opts[:k % len(opts)]
    mark = _choice_marks(opts)
    return '<span class="ch">' + "".join(
        '<span>%s %s</span>' % (mark[i] if i < len(mark) else str(i + 1), esc(o))
        for i, o in enumerate(opts)) + "</span>"


def _ans_label(item):
    """解答欄に出す答え。選択肢があれば記号も添える。"""
    ans = esc(item.get("ans"))
    dis = [d for d in (item.get("dis") or []) if d]
    if not dis:
        return ans
    opts = [item.get("ans", "")] + dis
    k = sum(ord(c) for c in str(item.get("id") or item.get("q") or ""))
    opts = opts[k % len(opts):] + opts[:k % len(opts)]
    mark = _choice_marks(opts)
    try:
        i = opts.index(item.get("ans", ""))
    except ValueError:
        return ans
    return "%s（%s）" % (mark[i] if i < len(mark) else str(i + 1), ans)


def mark_sheet(title, sub, items):
    """解答欄のページ。カメラで読むのはこの紙。"""
    g = SHEET
    W, H = g["pageMM"]
    m, mw = g["marginMM"], g["markMM"]
    # 位置合わせ四角形（マークの中心どうし）の中での、格子の場所
    rx, ry = m + mw / 2.0, m + mw / 2.0
    rw, rh = W - 2 * rx, H - 2 * ry
    gx = rx + rw * g["gridX0"]
    gy = ry + rh * g["gridY0"]
    gw = rw * g["gridW"]
    gh = rh * g["gridH"]
    return (
        '<div class="sheet mark brk">' + _marks() +
        '<div class="mhead"><h1>%s ―― 解答らん</h1>'
        '<div class="sub">%s</div></div>'
        '<div class="mname">なまえ<i></i>クラス<i></i>日づけ<i></i></div>'
        '<div class="agrid" style="left:%.2fmm;top:%.2fmm;'
        'width:%.2fmm;height:%.2fmm">%s</div>'
        '<div class="mtip">えんぴつで、まるを ぬりつぶしてください。'
        'アプリの「カメラで丸つけ」で、この紙を撮ると自動で採点します。'
        '四すみの黒い四角が ぜんぶ写るように撮ってください。</div>'
        '</div>'
        % (esc(title), esc(sub), gx, gy, gw, gh, answer_grid(items)))


def build(title, sub, meta, items, with_answers=True, auto_print=False):
    """1枚ぶんの HTML。

    title  見出し（「小5 理科 総復習テスト対策」など）
    sub    そえ書き（範囲・版）
    meta   右上に出す行の並び [(名前, 値), …]
    items  問題の並び
    """
    # 教科が2つ以上まざる紙（5教科ぶん）では、問題ごとに教科を出す。
    # 1教科だけの紙では出さない ―― 見出しに書いてあるものを60回くり返さない。
    mixed = len(set(x.get("subject") or "" for x in items)) > 1
    # 長文は、同じ本文の設問をまとめて出す（本文は先頭で1回だけ）。
    parts, prev = [], ""
    for i, x in enumerate(items):
        # **本文は設問より先。** 実際の試験は 本文 → 問1 → 問2 の順で、
        # 設問を読んでから本文へ戻る形にはなっていない。
        parts.append(
            '<div class="q s-%s%s">%s<span class="no">%d</span>'
            '<span class="t">%s%s</span>%s%s<span class="work"></span></div>'
            % (esc(x.get("subject") or "x"),
               " haschou" if x.get("bun") and x.get("bun") != prev else "",
               _bun(x, prev), i + 1,
               ('<span class="sj">%s</span>' % esc(_sj(x))) if mixed else "",
               _q_text(x), _fig(x), _choices(x)))
        prev = x.get("bun") or ""
    qs = "".join(parts)

    ans = ""
    if with_answers:
        rows = "".join(
            '<div class="q"><span class="no">%d</span>'
            '<span class="t">%s<span class="a">%s</span>%s</span></div>'
            % (i + 1,
               ('<span class="sj">%s</span>' % esc(_sj(x))) if mixed else "",
               _ans_label(x),
               ('<span class="note">%s</span>' % esc(plain(x["note"])))
               if x.get("note") else "")
            for i, x in enumerate(items))
        ans = (
            '<div class="sheet brk ans" data-paged="1" data-title="%s ―― 解答と解説">'
            '<div class="head"><div class="h-l"><h1>%s ―― 解答と解説</h1>'
            '<div class="sub">%s</div></div></div>'
            '<div class="cols">%s</div>'
            '<div class="foot"><span>TUBE study</span>'
            '<span>%d問</span></div></div>'
            % (esc(title), esc(title), esc(sub), rows, len(items)))

    mrows = "".join("<div>%s <b>%s</b></div>" % (esc(a), esc(b)) for a, b in meta)
    return (
        "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>%s</title><style>%s</style></head><body>"
        '<div class="noprint"><button data-print="1">'
        'PDFにする</button>'
        'A4・たて・余白12mm。問題 → 解答らん（カメラで読む紙）→ 解答と解説 の順です。'
        '<span class="tip">出てきた画面で、送信先に「PDFに保存」を選んでください。'
        '　※ 解答らんの紙は、四すみの黒い四角ごと刷ってください。'
        '欠けるとカメラが読めません。</span></div>'
        '<div class="sheet" data-paged="1" data-layout="%s" data-title="%s">'
        '<div class="head"><div class="h-l"><h1>%s</h1>'
        '<div class="sub">%s</div></div><div class="h-r">%s</div></div>'
        '<div class="name">なまえ<i></i>　クラス<i></i></div>'
        '<div class="cols">%s</div>'
        '<div class="foot"><span>TUBE study</span><span>%d問</span></div>'
        "</div>%s%s%s</body></html>"
        % (esc(title), CSS,
           # 数学は1段組み（途中式に 幅いっぱいを使う）。
           # 国語は縦書き（本番の試験が縦書きなので、そろえる）。
           _layout(items),
           esc(title), esc(title), esc(sub), mrows, qs, len(items),
           mark_sheet(title, sub, items), ans,
           # 押したときの動きは app/js/sheet-print.js にある。
           # **ここに <script> を直に書いても動かない** ――
           # script-src 'self' なので、その場に書いた JS は実行されない。
           '<script src="/js/sheet-print.js"></script>'))


# 教科の頭の1字。5教科の紙では、問題ごとにこれを出す。
# 名前（「理科」）ではなく1字にするのは、A3の3段組では
# 1問あたりの横幅が 88mm しかなく、2字ぶんでも問題文を押し出すため。
SJ1 = {"japanese": "国", "math": "算", "english": "英",
       "science": "理", "social": "社"}


def _sj(x):
    return SJ1.get(x.get("subject") or "", "") or (x.get("subjectName") or "")[:1]


def _layout(items):
    """この紙の組み方。

        "tate" … 縦書き 1段（国語）。本番の試験が縦書きだから。
        "one"  … 横書き 1段（算数・数学）。途中式に幅いっぱいを使う。
        "two"  … 横書き 2段（その他）。1行が長すぎると目が戻れない。
    """
    subs = {x.get("subject") for x in items}
    if subs == {"japanese"}:
        return "tate"
    if subs == {"math"}:
        return "one"
    return "two"


def _group_by_bun(rows):
    """同じ長文の設問を、先に出てきた場所にまとめる。

    **順番を大きく変えない。** 本文の位置だけをそろえたいので、
    はじめて出てきた場所に、その本文の設問をまとめて置く。
    こうすると紙の上で本文が1回で済み、解く側も読み返さなくてよい。
    """
    out, seen = [], {}
    for x in rows:
        b = x.get("bun") or ""
        if not b:
            out.append(x)
            continue
        if b in seen:
            seen[b].append(x)
        else:
            seen[b] = [x]
            out.append(seen[b])
    flat = []
    for x in out:
        flat.extend(x) if isinstance(x, list) else flat.append(x)
    return flat


def paper_items(sets):
    """紙に刷る分だけを選ぶ。

    **選択肢のある問題だけ。** 用語（「〜とは？」）は書いて答えるので、
    マークシートでは採点できない。紙に載せて採点できないと、
    生徒は「読めませんでした」を何十個も見ることになる。
    用語はアプリの中で出す ―― そちらなら1問ずつ答え合わせできる。

    解答らんの升目（6×10＝60）を超える分も落とす。
    升目の無い問題を刷ると、その問題だけ永久に採点できない。
    """
    CAP = SHEET["cols"] * SHEET["rows"]

    # 教科ごとに分けてから、**順ぐりに1問ずつ**取る。
    #
    # 前は先頭からつなげて60問で切っていた。国語（漢字）は1学年118問あり、
    # 理科や社会の3倍近い。だから5教科の紙が **60問ぜんぶ漢字** になり、
    # 数学も理科も1問も載らなかった。刷った紙を見るまで気づけない。
    #
    # 順ぐりに取れば、少ない教科でも必ず載る。ある教科が尽きたら、
    # 残りは他の教科が引き取るので、60問の枠は無駄にならない。
    lanes = []
    for st in sets:
        got = [x for x in (st.get("items") or []) if x.get("dis")]
        if got:
            # どの教科の問題かを、問題そのものに書いておく。
            # 5教科の紙では、これが無いと何の問題か分からない。
            for x in got:
                x = dict(x)
                x["subject"] = st.get("subject") or ""
                x["subjectName"] = st.get("name") or ""
            lanes.append([dict(x, subject=st.get("subject") or "",
                               subjectName=st.get("name") or "") for x in got])

    out = []
    i = 0
    while len(out) < CAP and any(len(l) > i for l in lanes):
        for l in lanes:
            if i < len(l):
                out.append(l[i])
                if len(out) >= CAP:
                    break
        i += 1
    # 長文の設問は、本文ごとにまとめる（本文を1回しか刷らないため）。
    return _group_by_bun(out)


# 刷る紙の決まった文言。小6以上は漢字で刷る（アプリの jp() と同じ決まり）。
# 問題文には触れない ―― 置き換えるのは、ここに並べた見出し・記入欄・注意書きだけ。
KANJI_LABELS = (
    ("―― 解答らん</h1>", "―― 解答欄</h1>"),
    ("なまえ<i></i>クラス<i></i>日づけ<i></i>", "名前<i></i>クラス<i></i>日付<i></i>"),
    ("えんぴつで、まるを ぬりつぶしてください。", "鉛筆で、丸を塗りつぶしてください。"),
    ("四すみの黒い四角が ぜんぶ写るように撮ってください。",
     "四隅の黒い四角がすべて写るように撮ってください。"),
    ("A4・たて・余白12mm。問題 → 解答らん（カメラで読む紙）→ 解答と解説 の順です。",
     "A4・縦・余白12mm。問題 → 解答欄（カメラで読む紙）→ 解答と解説の順です。"),
    ("出てきた画面で、送信先に「PDFに保存」を選んでください。",
     "表示された画面で、送信先に「PDFに保存」を選んでください。"),
    ("　※ 解答らんの紙は、四すみの黒い四角ごと刷ってください。",
     "　※ 解答欄の紙は、四隅の黒い四角ごと印刷してください。"),
    ("なまえ<i></i>　クラス<i></i>", "名前<i></i>　クラス<i></i>"),
)


def _kanji_labels(html):
    for kana, kanji in KANJI_LABELS:
        html = html.replace(kana, kanji)
    return html


def for_prep(prep, subject_name, grade_name, sets, auto_print=False):
    """総復習テスト対策から1枚ぶんを組む。"""
    allitems = paper_items(sets)
    items = allitems
    exam = (prep or {}).get("exam") or {}
    kanji = str(grade_name).startswith(("小6", "小学6", "中"))
    meta = [
        ("組み分けテスト", exam.get("date", "")),
        ("あと", "%d日" % (prep or {}).get("left", 0)),
        ("版", TIER_NAME.get((prep or {}).get("tier"), "")),
        ("印刷日" if kanji else "刷った日", time.strftime("%Y-%m-%d")),
    ]
    title = "%s %s 総復習テスト対策" % (grade_name, subject_name)
    since = (prep or {}).get("since") or ""
    if kanji:
        sub = ("範囲: %s 以降に学習した内容" % since) if since else "範囲: 学期の初めから"
        sub += "　／　この紙は選択問題 %d問（用語などはアプリで）" % len(items)
    else:
        sub = ("範囲: %s 以降に習ったところ" % since) if since else "範囲: 学期のはじめから"
        sub += "　／　この紙は 選たく問題 %d問（用語などは アプリで）" % len(items)
    html = build(title, sub, meta, items, auto_print=auto_print)
    return _kanji_labels(html) if kanji else html
