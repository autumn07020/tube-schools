#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ソースに他言語の字がまぎれていないか調べる。

**教材の検査（check-content.py）は app/content/ しか見ていない。**
そのため画面の文字列に「すぐ반映されます」（ハングルの반）が入り、
実際に講師の画面に出ていた。指摘されるまで気づけなかった。

ここでは JS・CSS・HTML・Python の全部を見る。
記号（× ★ − ⚠ · ✓ ①）は意図して使っているので通し、
**別の文字体系**だけを弾く。

    python3 app/tools/check-source.py
"""
import glob, io, os, re, sys, unicodedata

# 弾く文字体系。日本語の文章に出てきたら、まず混入である。
BLOCKS = [
    (0x0400, 0x04FF, "キリル文字"),
    (0x0370, 0x03FF, "ギリシャ文字"),
    (0x0530, 0x058F, "アルメニア文字"),
    (0x0590, 0x05FF, "ヘブライ文字"),
    (0x0600, 0x06FF, "アラビア文字"),
    (0x0900, 0x097F, "デーヴァナーガリー"),
    (0x0E00, 0x0E7F, "タイ文字"),
    (0x1100, 0x11FF, "ハングル字母"),
    (0xAC00, 0xD7AF, "ハングル"),
    (0x3130, 0x318F, "ハングル互換字母"),
]
# 目印として意図的に使っている私用領域文字（穴埋めの目印）。ここだけ許す。
ALLOW_PUA = {0xE000}

# 使ってよい例外の字。
#   α β … 教室のクラス名（小4α、小6β）。塾で実際に使う呼び方なので、
#          勝手に「A」「B」へ置き換えない。講師と生徒が混乱する。
# ここに足すときは、**画面に出す言葉として本当に必要か**を確かめること。
# 「なんとなく格好いいから」で足すと、検査が意味を失う。
#   π …… 円周率。算数・数学の教材と、その生成器に出る。
#          「3.14」で置き換えると中1のおうぎ形が答えられなくなる
#          （答えが 6π のような形で出るため）。
ALLOW_CHARS = {0x03B1, 0x03B2, 0x03C0}

def scan(path):
    out = []
    for ln, line in enumerate(io.open(path, encoding="utf-8"), 1):
        for ch in line:
            cp = ord(ch)
            # 例外はいちばん先に外す。あとで外すと、
            # ブロック照合のほうで先に拾われてしまう。
            if cp in ALLOW_CHARS:
                continue
            for lo, hi, name in BLOCKS:
                if lo <= cp <= hi:
                    out.append((ln, ch, cp, name, line.strip()[:70]))
            if 0xE000 <= cp <= 0xF8FF and cp not in ALLOW_PUA:
                out.append((ln, ch, cp, "私用領域", line.strip()[:70]))
    return out

def check_grid(text, name):
    """CSS の格子で、列を直に指していないか。

    **なぜ検査するか。**
    画面の幅で列の数が変わる作りにしてある（2列と3列）。そこに
    `grid-column: 3 / -1` のような**絶対の列番号**を書くと、
    2列しかない幅では存在しない3列目が勝手に作られ、
    札が重なって表示が壊れる。

    実際、1024〜1439px の幅で「英・国・社」とカレンダーが
    重なった。幅を変えたときだけ出るので、作っている最中は気づかない。

    直し方は簡単で、`span 2` のように**いくつ分か**で書く。
    こちらは列が何本あっても、はみ出さずに折り返す。
    """
    out = []
    allowed_line = 0
    guard = 0          # いま @container の min-width の中にいるか（入れ子の深さ）
    depth = 0

    # 「列の数が決まっている格子」を先に拾う。
    #   .wgrid{ … grid-template-columns:repeat(2, 1fr) … }
    # のように **土台で何列かを書いてある**格子は、その本数までなら
    # またいでよい。存在しない列を指すことがないからである。
    fixed = {}
    for blk in re.finditer(r"(\.[A-Za-z0-9_-]+)[^{]*\{([^}]*)\}", text):
        cols = re.search(r"grid-template-columns\s*:\s*repeat\(\s*(\d+)",
                         blk.group(2))
        if cols:
            cls = blk.group(1)
            fixed[cls] = max(fixed.get(cls, 0), int(cols.group(1)))
    for i, line in enumerate(text.split("\n"), 1):
        st = line.strip()
        if st.startswith(("/*", "*", "//")):
            continue
        # 「この幅より広いとき」を確かめている中では、列をまたいでよい。
        # 列が何本あるかが分かっている場所だからである。
        if re.search(r"@container[^{]*min-width", st):
            guard = depth + 1
        depth += st.count("{") - st.count("}")
        if guard and depth < guard:
            guard = 0
        # 土台（.t-full / .t-wide / .t-hero）の定義だけは列を書いてよい。
        # ここが唯一、列を知っている場所である。
        if re.search(r"\.t-(full|wide|hero|one)\s*\{", st):
            allowed_line = i
        # 1 / -1（先頭の線から最後の線まで）は、列が何本でも成り立つ。
        # 危ないのは 3 / -1 のような **途中の線を名指しする**書き方である。
        if re.search(r"grid-column\s*:\s*1\s*/\s*-1", line):
            continue
        m = re.search(r"grid-column\s*:\s*(?:(\d+)\s*/|span\s+(\d+))", line)
        # span N は「N個ぶん」なので、列が足りていれば壊れない。
        # 通すのは次の2つだけ。**絶対の列番号は、どこでも通さない。**
        #   ① 幅を確かめた（@container min-width）中にある
        #   ② 列の数を土台で決めてある格子の中で、その本数に収まっている
        if m and m.group(2) and guard:
            continue
        if m and m.group(2):
            n = int(m.group(2))
            head = re.match(r"\s*(\.[A-Za-z0-9_-]+)", st)
            if head and fixed.get(head.group(1), 0) >= n:
                continue
        if m and i != allowed_line:
            out.append((i, "列を直に指しています。土台の t-full / t-wide / "
                           "t-one を使ってください: " + st[:52]))
        m2 = re.search(r"grid-row\s*:\s*(\d+)\s*/", line)
        if m2 and int(m2.group(1)) > 1:
            out.append((i, "行番号を直に書いています: " + st[:56]))
    return out



def check_sheet_geometry():
    """解答らんの寸法が、刷る側と読む側で食いちがっていないか。

    **ここがずれると、採点が静かに全滅する。** 画面は何も言わず、
    ただ全部の答えを取りちがえる。実際に一度ずらした ――
    A3よこ6×10 から A4たて4×15 に変えたとき、読む側の写しを
    直し忘れた。刷った紙は正しく、読み取りだけが間違う。

    出どころは server/prepsheet.py の SHEET ひとつ。
    写しは2つある（画面の控えと、検査ページ）。ここで突き合わせる。
    """
    import ast
    out = []
    try:
        src = io.open("server/prepsheet.py", encoding="utf-8").read()
        blk = src.split("SHEET = {")[1]
        d, i = 1, 0
        while i < len(blk) and d:
            if blk[i] == "{":
                d += 1
            elif blk[i] == "}":
                d -= 1
            i += 1
        sheet = ast.literal_eval("{" + blk[:i])
    except Exception as e:
        return [("server/prepsheet.py", 0, "SHEET を読めません: %s" % e)]

    keys = ["cols", "rows", "opts", "gridX0", "gridY0", "gridW", "gridH",
            "bubX0", "bubDX", "bubR"]
    for path, var in [("app/js/ui-student.js", "prepSheetGeom"),
                      ("app/tools/test-omr.js", "G")]:
        try:
            txt = io.open(path, encoding="utf-8").read()
        except OSError:
            continue
        i = txt.find("var %s = {" % var)
        if i < 0:
            out.append((path, 0, "%s が見あたりません" % var))
            continue
        body = txt[i:txt.index("};", i)]
        for k in keys:
            m = re.search(r"\b%s\s*:\s*([0-9.]+)" % k, body)
            if not m:
                out.append((path, txt[:i].count("\n") + 1,
                            "%s に %s がありません" % (var, k)))
                continue
            if abs(float(m.group(1)) - float(sheet[k])) > 1e-9:
                out.append((path, txt[:i].count("\n") + 1,
                            "%s の %s が %s。server/prepsheet.py は %s"
                            % (var, k, m.group(1), sheet[k])))
    return out


def check_dup_class(text, name):
    """同じ名前のクラスを、**別の並べ方**で2度定義していないか。

    2度やられている。
      .marks  講師の評価ボタン（display:flex）と、カメラ採点の結果
              （display:grid）。あとに書いた格子が勝ち、評価ボタンが
              横1列から縦1列に化けた。
      .pact   講師の Upcoming（display:grid）と、対策の行のボタン。

    どちらも画面のまったく別の場所で、見ただけでは結びつかない。
    気づくのは「関係ないはずの所が崩れた」と言われたときである。

    **同じクラスを2度書くこと自体は正しい。** 枠を外す、色を変える、
    幅ごとに詰める ―― どれもふつうのCSSである。
    危ないのは **display が食い違う**ときだけ。それは同じ名前を
    別の並べ方の物に使っている証拠になる。
    """
    out = []
    disp = {}
    for m in re.finditer(r"(?m)^\s*((?:\.[A-Za-z][\w-]*\s*,\s*)*\.[A-Za-z][\w-]*)"
                         r"\s*\{([^}]*)\}", text):
        d = re.search(r"(?<![-\w])display\s*:\s*([a-z-]+)", m.group(2))
        if not d:
            continue
        ln = text[:m.start()].count("\n") + 1
        for cls in [c.strip() for c in m.group(1).split(",")]:
            prev = disp.get(cls)
            if prev and prev[0] != d.group(1):
                out.append((ln, "%s は %d行目で display:%s、ここで display:%s。"
                               "別の物なら別の名前にしてください"
                               % (cls, prev[1], prev[0], d.group(1))))
            elif not prev:
                disp[cls] = (d.group(1), ln)
    return out

# 同じ言葉のあとの数は、同じ単位で出す（2026-09-28：今日やることの輪の札で、
# 残りがあるときは「今日つけた評価 23件」、終わったときは「今日つけた評価 3人」だった）。
# 'ことば '+x+'単位' の形だけを見る。2字の言葉（「あと3日」「あと5件」）は意味が広いので見ない。
UNIT_PAT = re.compile(r"([一-龥ぁ-んァ-ヶー]{3,12}) ?'\s*\+\s*[A-Za-z_$][\w$.]*\s*\+\s*'(人|件|回|枚|問|日|分)")


def check_units(files):
    seen = {}
    for f in files:
        if not f.endswith(".js"):
            continue
        for ln, line in enumerate(io.open(f, encoding="utf-8"), 1):
            for m in UNIT_PAT.finditer(line):
                seen.setdefault(m.group(1), {}).setdefault(m.group(2), []).append("%s:%d" % (f, ln))
    return [(lab, us) for lab, us in sorted(seen.items()) if len(us) > 1]


def main():
    # 置き場（app/tools の2つ上）に移ってから探す。どこから呼ばれても同じ物を見る
    # （2026-10-10：別の場所から 更新.sh を流すと 0 ファイルを見て「指摘 1件」で止まった）。
    os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    files = []
    for pat in ("app/**/*.js", "app/**/*.css", "app/**/*.html",
                "server/*.py", "app/tools/*.py", "roster-tool/*.html"):
        files += glob.glob(pat, recursive=True)
    # 検査ツール自身は対象から外す。中に「弾く字」の見本を書いてあるので、
    # 入れると自分を指摘し続ける。**誤報だらけの検査は誰も見なくなる。**
    # それは検査が無いより危ない（通ったつもりになる）。
    SKIP = ("check-source.py", "check-content.py")
    files = sorted(f for f in files
                   if "/content/" not in f and not f.endswith(SKIP))
    bad = 0
    print("ソースの検査 ―― 他言語の字\n" + "=" * 54)
    for f in files:
        for ln, ch, cp, name, ctx in scan(f):
            bad += 1
            print("  × %s:%d  %r U+%04X（%s）" % (f, ln, ch, cp, name))
            print("      …%s" % ctx)
    print("=" * 54)

    # 格子の検査。幅を変えたときだけ壊れる種類の間違いを、
    # 目で見つけるのは無理なので機械に探させる。
    print("\nCSSの格子 ―― 列番号の直書き\n" + "=" * 54)
    for f in [x for x in files if x.endswith(".css")]:
        try:
            text = io.open(f, encoding="utf-8").read()
        except (IOError, OSError):
            continue
        for ln, msg in check_grid(text, f):
            bad += 1
            print("  × %s:%d  %s" % (f, ln, msg))
    print("=" * 54)

    print("\nCSS ―― 同じ名前を別の物に使っていないか\n" + "=" * 54)
    for f in files:
        if not f.endswith(".css"):
            continue
        try:
            text = io.open(f, encoding="utf-8").read()
        except (IOError, OSError):
            continue
        for ln, msg in check_dup_class(text, f):
            bad += 1
            print("  × %s:%d  %s" % (f, ln, msg))
    print("=" * 54)

    print("\n解答らんの寸法 ―― 刷る側と読む側\n" + "=" * 54)
    for path, ln, msg in check_sheet_geometry():
        bad += 1
        print("  × %s:%d  %s" % (path, ln, msg))
    print("=" * 54)

    print("\n数の単位 ―― 同じ言葉に同じ単位\n" + "=" * 54)
    for lab, us in check_units(files):
        bad += 1
        print("  × 「%s」の単位が %s" % (lab, " ／ ".join("%s（%s）" % (u, ", ".join(v)) for u, v in sorted(us.items()))))
    print("=" * 54)

    print("%d ファイル / 指摘 %d件" % (len(files), bad))
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
