#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教材を生成する共通の土台。

**JS を直接手で書かないこと。** 以前この作業で、キリル文字・ハングル・
英単語の断片が35箇所まぎれ込んだ。目で追える量ではないし、
まぎれ込んだ字は画面では小さくて気づけない。
ここで検証を通したデータからだけ書き出す。

典拠について（著作権）
--------------------
* 学年別漢字配当表・常用漢字表は **内閣告示**。著作権法13条により
  著作権の目的とならない。字種の一覧はそのまま使える。
* 事実（元素記号・県庁所在地・年号など）に著作権はない。
* **熟語の選定・問題文・解説・意味の説明はすべて自作する。**
  市販教材からの転記はしない（CLAUDE.md 絶対に守ること 6）。
* Wikipedia（CC BY-SA）は継承条件が事業と衝突するので使わない。

カードの形（README.md と同じ）
    T（用語）  [表, 裏, 帯, 解説, 例, 例の補足]
    Q（選択）  [問題文, 正解, 誤答(|区切り), 帯, 解説]
"""

import io
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(os.path.dirname(HERE), "content")

# 日本語の教材に出てよい文字。ここを通らない字が1つでもあれば書き出さない。
#   ひらがな・カタカナ・漢字・長音・句読点・英数字・ごく限られた記号
OK_RANGES = [
    (0x3005, 0x3006),   # 々 〆
    (0x3040, 0x30FF),   # かな
    (0x3400, 0x4DBF),   # 漢字拡張A
    (0x4E00, 0x9FFF),   # 漢字
    (0xFF01, 0xFF60),   # 全角英数記号
    (0x2010, 0x201F),   # ダッシュ・引用符
    (0x2190, 0x21FF),   # 矢印
    (0x25A0, 0x25FF),   # ○△□
    (0x3000, 0x303F),   # 全角空白・括弧・句読点
]
OK_ASCII = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789 .,:;!?()[]{}+-*/=<>%&'\"#_|~^$@\\\n\t")

# 算数・数学で使う記号。**一覧で持つ。範囲では持たない。**
# 範囲（たとえばギリシャ文字ぜんぶ）を開けると、π のつもりで
# ギリシャ語の単語が丸ごと通ってしまう。要るものだけを名指しする。
OK_MATH = set(
    "×÷−±≠≒≦≧≪≫∞"      # 四則と大小
    "²³√π°"                # 累乗・平方根・円周率・角度
    "△∠∽≡∥⊥○□"          # 図形
    "‥…／："              # 区切り
    "℃"                    # 理科の温度。「度」と書き分ける教科書に合わせる
)


# ASCII の連なりで、教材に出てよいもの。
# 化学式・単位・略語だけを通し、それ以外の英単語は混入とみなす。
# （実際 "water を熱したとき" という行が素通りした。字の検査だけでは足りない）
OK_WORDS = {
    # 元素と化学式
    "H", "He", "Li", "C", "N", "O", "Na", "Mg", "Al", "S", "Cl", "K", "Ca",
    "Fe", "Cu", "Zn", "Ag", "Ba", "H2O", "CO2", "CO", "O2", "N2", "H2",
    "NaCl", "HCl", "NaOH", "CuO", "MgO", "Ag2O", "FeS", "CaCO3", "H2SO4",
    # 単位・記号
    "g", "kg", "mg", "m", "cm", "mm", "km", "mL", "L", "N", "J", "W", "V",
    "A", "Pa", "hPa", "pH", "cal", "km2", "m2", "cm3", "m3",
    # 学習で使う略語
    "BTB", "DNA", "RNA", "ATP", "PC", "AI", "IC", "LED", "GPS", "SDGs",
    "P", "S", "X", "Y", "Z",
    # 社会で名前として出てくる国際機関・条約の略称
    "ASEAN", "EU", "NAFTA", "OPEC", "ODA", "NGO", "NPO", "WTO", "WHO",
    "UNESCO", "UNICEF", "IMF", "APEC", "TPP", "GDP", "GNP", "ICT",
    "PKO", "NATO", "UNHCR", "NPT", "COP", "JICA", "JAXA",
}
# 数学の文字。**1文字だけ**を通す。
# 「x²+bx+c」「底辺 a、高さ h」のような書き方は数学では避けられない。
# 語まるごとで照合しているので、water の w だけが通ることはない ――
# water は water という1語として拾われ、ここに無いので止まる。
OK_WORDS |= set("abcdefghijklmnopqrstuvwxyz")
OK_WORDS |= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
# 数学で「かけ算の記号を省いた」書き方。**一覧で持つ。**
# 「2文字までなら通す」にすると the, is, at のような英単語が素通りする。
OK_WORDS |= {
    "ax", "bx", "cx", "ay", "by", "ab", "bc", "ca", "xy", "yz", "zx",
    "ax2", "bx2", "abc", "ABC", "DEF", "PQR",     # 三角形の頂点にも使う
    "ad", "bc", "cd", "ac", "bd",                 # 比例式 a:b=c:d の内項外項
}
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")


def bad_words(text):
    """英単語の混入を拾う。化学式・単位・略語は通す。"""
    out = []
    for w in WORD_RE.findall(text):
        if w in OK_WORDS or w.upper() in OK_WORDS:
            continue
        out.append(w)
    return out


def bad_chars(text):
    """使ってはいけない字を拾う。他言語の混入をここで止める。"""
    out = []
    for ch in text:
        if ch in OK_ASCII or ch in OK_MATH:
            continue
        cp = ord(ch)
        if any(lo <= cp <= hi for lo, hi in OK_RANGES):
            continue
        out.append((ch, "U+%04X" % cp, unicodedata.name(ch, "?")))
    return out


class Pack(object):
    """1つの教材ファイル。足していって、最後に書き出す。"""

    def __init__(self, pack_id, subject, name, bands, note, english=False):
        # english=True にすると「英単語がまぎれている」検査だけ外す。
        # **英語の教材では英単語が本文である。**
        # 字の検査（キリル文字・ハングルなど）は外さない ――
        # まぎれ込むのはそちらで、英単語ではない。
        self.english = english
        self.id = pack_id
        self.subject = subject
        self.name = name
        self.bands = bands
        self.note = note
        self.rows = []
        self.seen = set()
        # いま作っている単元。p.unit = "がい数" のように立てておくと、
        # そのあとの p.Q すべてに付く。1問ずつ書かなくてよい。
        self.unit = ""

    def T(self, front, back, band, note="", ex="", ex2=""):
        self._add("T", [front, back, band, note, ex, ex2], band_at=2)

    def Q(self, q, ok, wrong, band, note="", unit=None, fig="", bun=""):
        """選択問題。

        unit を渡すと **6列目**に単元名を書く。
            [問題文, 正解, 誤答, 帯, 解説, 単元]

        なぜ列を増やしたか ―― もとは5列目が「解説 か 単元名 の
        どちらか」だった。読む側は「。が入っていれば解説」という
        当てずっぽうで見分けていて、実際に外れた。数学の解説
        「両方を最大公約数 6 でわる。」が **時間割の単元名**として
        画面に出ていた。1つの列に2つの意味を持たせたのが誤りだった。

        5列のままの教材（理科・社会・国語）はそのまま動く。
        """
        if isinstance(wrong, (list, tuple)):
            wrong = "|".join(wrong)
        u = self.unit if unit is None else unit
        cells = [q, ok, wrong, band, note]
        # 7列目は図の名前（content/figures.js の鍵）。
        # 図があるのに単元が無いと列がずれるので、単元は空でも置く。
        # 6列目 単元 / 7列目 図 / 8列目 読解文。
        # 後ろの列だけ使うときも、前の列は空で置く（位置がずれる）。
        if u or fig or bun:
            cells.append(u)
        if fig or bun:
            cells.append(fig)
        if bun:
            cells.append(bun)
        self._add("Q", cells, band_at=3)

    def _add(self, kind, cells, band_at=2):
        key = (kind, cells[0])
        if key in self.seen:
            raise ValueError("同じ問題が2つあります: %s" % cells[0][:30])
        self.seen.add(key)
        for c in cells:
            if not isinstance(c, str):
                raise ValueError("文字列でない値: %r（%s）" % (c, cells[0][:20]))
        if not cells[0].strip() or not cells[1].strip():
            raise ValueError("表か裏が空です: %r" % (cells[:2],))
        if self.bands and cells[band_at] not in self.bands:
            raise ValueError("知らない帯です: %r（%s に無い）"
                             % (cells[band_at], self.bands))
        joined = "".join(cells)
        bad = bad_chars(joined)
        if bad:
            raise ValueError("使えない字が入っています: %s  ← %s"
                             % (bad[:4], cells[0][:24]))
        # 連結してから走査すると、"120g" と "100g" がつながって
        # "g100g" という語に見える。セルごと・区切りごとに見る。
        #
        # 正解そのものが化学式や記号のとき（「酸素の元素記号は？」など）は、
        # 誤答にも作りものの記号を置く必要がある。そこだけ英字を許す。
        symbolic = kind == "Q" and bool(WORD_RE.fullmatch(cells[1].strip()))
        if self.english:
            self.rows.append((kind, cells))
            return
        eng = []
        for i, c in enumerate(cells):
            if symbolic and i in (1, 2):
                continue
            # 7列目は図、8列目は読解文の名前（鍵であって中身ではない）。
            if kind == "Q" and i in (6, 7):
                continue
            for seg in c.split("|"):
                eng += bad_words(seg)
        if eng:
            raise ValueError("英単語がまぎれています: %s  ← %s"
                             % (eng[:4], cells[0][:24]))
        self.rows.append((kind, cells))

    def write(self):
        if len(self.rows) < 1:
            raise ValueError("%s は空です" % self.id)
        path = os.path.join(CONTENT, self.id + ".js")
        os.makedirs(os.path.dirname(path), exist_ok=True)

        def esc(s):
            # 既存の教材にそろえて二重引用符で書く。
            # **改行を必ず潰す。** 生の改行を書くと JavaScript の文字列が
            # そこで切れ、教材ファイルが構文エラーになる。読み込みは
            # 黙って失敗し、その教材だけ「0問」として出る ――
            # 画面にはエラーが出ないので、気づくのは出題が来ないときである。
            return (s.replace("\\", "\\\\").replace('"', '\\"')
                     .replace("\r", " ").replace("\n", " "))

        lines = []
        lines.append("/* %s ―― %s" % (self.name, self.note))
        lines.append("")
        lines.append("   **このファイルは app/tools/gen_content.py が書き出したもの。**")
        lines.append("   手で直さないこと。直すなら生成側を直して作り直す。")
        lines.append("   （手書きに戻すと他言語の字が混ざる。実際に35箇所まぎれ込んだ）")
        lines.append("")
        lines.append("   T（用語）  [表, 裏, 帯, 解説, 例, 例の補足]")
        lines.append("   Q（選択）  [問題文, 正解, 誤答(|区切り), 帯, 解説]  */")
        # ★ 必ず TubeContent.register() を呼ぶこと。
        #   ここを独自のグローバル変数に書き出していたため、
        #   **18パック2847問がまるごとアプリから見えなかった。**
        #   ファイルは読み込まれ、目録も検査も通るのに、出題が0件になる。
        #   ファイルを見ているだけでは絶対に気づけない種類の不具合だった。
        lines.append("(function(){")
        lines.append('"use strict";')
        lines.append("")
        lines.append("var T = [")
        for kind, c in self.rows:
            if kind == "T":
                lines.append('["%s","%s","%s","%s","%s","%s"],'
                             % tuple(esc(x) for x in c))
        lines.append("];")
        lines.append("")
        lines.append("var Q = [")
        for kind, c in self.rows:
            if kind == "Q":
                lines.append("[%s],"
                             % ",".join('"%s"' % esc(x) for x in c))
        lines.append("];")
        lines.append("")
        lines.append("TubeContent.register({")
        lines.append("  id:      '%s'," % self.id)
        lines.append("  subject: '%s'," % self.subject)
        lines.append("  name:    '%s'," % esc(self.name).replace("'", "\\'"))
        lines.append("  note:    '%s'," % esc(self.note).replace("'", "\\'"))
        lines.append("  bands:   [%s]," % ",".join("'%s'" % b for b in self.bands))
        lines.append("  T:T, Q:Q")
        lines.append("});")
        lines.append("")
        lines.append("})();")
        io.open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        nT = len([1 for k, _ in self.rows if k == "T"])
        nQ = len(self.rows) - nT
        return {"id": self.id, "subject": self.subject, "name": self.name,
                "bands": self.bands, "note": self.note,
                "items": len(self.rows), "T": nT, "Q": nQ,
                "file": self.id + ".js"}


def report(built):
    print("書き出しました\n")
    print("  %-26s %-6s %5s %5s %5s" % ("教材", "教科", "合計", "用語", "選択"))
    print("  " + "-" * 56)
    total = 0
    for b in built:
        print("  %-26s %-6s %5d %5d %5d"
              % (b["id"], b["subject"], b["items"], b["T"], b["Q"]))
        total += b["items"]
    print("  " + "-" * 56)
    print("  %-26s %-6s %5d" % ("合計", "", total))
    return total
