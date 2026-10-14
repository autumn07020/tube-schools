#!/usr/bin/env python3
"""
教材の検査
------------------------------------------------------------------
    python3 app/tools/check-content.py

content/ の教材をすべて読み、次を機械的に確かめる。

  1. 目録（manifest.js）に書いてあるファイルが実在するか
  2. 実在するファイルが目録に載っているか（載せ忘れは「0問」の原因になる）
  3. 項目の中に、日本語・英語以外の文字が紛れ込んでいないか
  4. 表（見出し）や裏（意味）が空の行が無いか
  5. 同じ見出しが重複していないか
  6. 帯の名前が、目録に書いた bands と食い違っていないか

3 が入っているのは、教材を書くときに他言語の断片が混ざる事故が
実際に起きたため。目で読むと見落とすので、必ずここを通す。

落ちた行は「直すべき行」であって、勝手に消さない。
どこが悪いかを出すだけにしてある。
"""

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(os.path.dirname(HERE), "content")
APP = os.path.dirname(HERE)

# 検査するのは「壊れているか」だけ。書き方の好みは見ない。
#
# 発音記号（ˈəɪ）、数学記号（− ² π）、通貨（£）、○× は正しい教材の一部なので
# 通す。最初はこれらまで弾いてしまい、161件のうち大半が誤検出だった。
# 検査が誤報だらけになると、人は検査を見なくなる ―― そのほうが危険。
#
# 実際に起きた事故は「別の言語の断片が紛れ込む」ことだったので、そこを狙う。
FOREIGN = re.compile(r"[Ѐ-ӿ가-힯؀-ۿ฀-๿\u0e00-\u0e7f]")


def rows_of(src):
    """[ "…", "…", … ] の形の行を、雑に取り出す。
    完全なJSパーサは要らない。1行1項目で書く約束にしてあるため。"""
    out = []
    for i, line in enumerate(src.split("\n"), 1):
        s = line.strip().rstrip(",")
        # 引用符はどちらでもよい。生成器は ' を、手書きのものは " を使う。
        # ここを片方だけにしていたため、生成した教材が**1行も検査されずに
        # 素通りしていた**（0項目と出るのに指摘も出ない、という形で現れる）。
        if s.startswith("[") and s.endswith("]") and s[1:2] in ("'", '"'):
            q = s[1]
            parts = re.findall(r"%s((?:[^%s\\]|\\.)*)%s" % (q, q, q), s)
            out.append((i, parts))
    return out



def check_curriculum(pack_ids):
    """進度（app/curriculum.js）が、実在する教材を指しているか。

    **これが無いと気づけない。** 教材の名前を変えたり消したりしたとき、
    進度の側は古い名前を指したまま残る。エラーは出ない。
    その学年の生徒の画面が、ただ空になるだけである。
    実際に、教材を作り直したときに6件が切れていた。
    """
    path = os.path.join(APP, "curriculum.js")
    if not os.path.isfile(path):
        return []
    src = io.open(path, encoding="utf-8").read()
    out = []
    for m in re.finditer(r"'([a-z0-9]+:[a-z]+)':\s*\{[^}]*?packs:\[([^\]]*)\]", src, re.S):
        key = m.group(1)
        for pid in re.findall(r"'([^']+)'", m.group(2)):
            if pid not in pack_ids:
                out.append("進度 %s が、存在しない教材を指しています: %s" % (key, pid))
    return out

def check_pack(path, declared_bands):
    src = io.open(path, encoding="utf-8").read()
    # T / Q だけで書かれた教材か（英語パックは V/P/G/B も使うため形が違う）
    simple = ("V.push" not in src and "var V" not in src)
    problems = []
    heads = {}
    bands_seen = set()

    for lineno, parts in rows_of(src):
        if not parts:
            continue
        head = parts[0].strip()
        back = parts[1].strip() if len(parts) > 1 else ""
        # 帯の位置は型によって違う（T は3つめ、Q は4つめ）。
        # 位置を決め打ちにすると、選択肢の一覧を帯と読み違える。
        band = ""
        for idx in (2, 3):
            if len(parts) > idx and parts[idx].strip() in (declared_bands or []):
                band = parts[idx].strip()
                break

        joined = " ".join(parts)
        if FOREIGN.search(joined):
            bad = "".join(dict.fromkeys(FOREIGN.findall(joined)))[:8]
            problems.append((lineno, "別の言語の文字が混じっています: %s" % bad))

        # 空欄の検査は T/Q だけの教材に限る。英語パックの文法項目には
        # 表の続きを表す意図的な空欄（forms の2行目以降）があるため。
        if simple:
            if not head:
                problems.append((lineno, "見出し（1つめ）が空です"))
            if not back:
                problems.append((lineno, "意味・答え（2つめ）が空です"))

        # 重複は、帯の位置が決まっている教材（T/Q だけの科目）でのみ見る。
        # 英語パックは行の形が5通りあり、素朴に数えると誤報になる。
        if simple and head:
            if head in heads:
                problems.append((lineno, "%d行目と見出しが同じです: %s" % (heads[head], head)))
            heads[head] = lineno
        if simple and band:
            bands_seen.add(band)

    if simple and declared_bands:
        extra = bands_seen - set(declared_bands)
        if extra:
            problems.append((0, "目録に無い帯を使っています: %s" % "、".join(sorted(extra))))
        unused = set(declared_bands) - bands_seen
        if unused:
            problems.append((0, "目録にあるのに1問も無い帯: %s" % "、".join(sorted(unused))))

    return len(heads) or sum(1 for _ in rows_of(src)), problems



def _raw_items(sub, g):
    """重複を落とす**前**の項目。何が落とされたかを数えるのに使う。"""
    import examprep
    return examprep.pack_items(sub, g, dedupe=False)

def check_english_dup():
    """英語パックの単語表（V）で、同じ見出しが二度出ていないか。

    英語の教材は1ファイルに5通りの行の形（単語・文法・口語…）が
    混ざるので、上の「見出しが同じです」は英語を見送っている。
    その隙間に **79語・87行の重複**が入り込み、そのうち52語は
    意味まで違っていた（restore ← 修復する ／ 修復する、回復させる）。

    重複しても画面は落ちない。先に読んだほうが勝ち、あとは黙って
    捨てられる。だから**捨てられたほうの意味で覚えた生徒**が、
    いつまでも正解にならない ―― これも気づけない壊れ方である。

    ここでは単語表（V）の行だけを、見出しと品詞の組で見る。
    行の形が1通りに決まっているので、誤報にならない。
    """
    out = []
    d = os.path.join(os.path.dirname(HERE), "content", "english")
    if not os.path.isdir(d):
        return out
    for name in sorted(os.listdir(d)):
        if not name.endswith(".js"):
            continue
        seen = {}
        path = os.path.join(d, name)
        for n, line in enumerate(io.open(path, encoding="utf-8"), 1):
            t = line.strip().rstrip(",")
            if not (t.startswith('["') and t.endswith("]")):
                continue
            try:
                row = json.loads(t)
            except ValueError:
                continue
            # 単語表の行だけ。[見出し, 品詞, 帯, 意味, …]
            if len(row) < 4 or not isinstance(row[0], str):
                continue
            key = (row[0].lower(), row[1])
            if key in seen:
                out.append("english/%s  %d行目と見出しが同じです: %s (%s)"
                           % (name[:-3], seen[key], row[0], row[1]))
            else:
                seen[key] = n
    return out


def check_figures():
    """図の名前が、教材と絵で食い違っていないか。

    教材のQ行の7列目は絵の名前で、絵そのものは content/figures.js にある。
    名前がずれると「図のアの部分は？」という問題が、**図なしで**出る。
    落ちないし、エラーも出ない。生徒には答えようがない。

    逆に、どの問題からも指されていない絵は、ただ端末を重くするだけ。
    """
    out = []
    fig_path = os.path.join(os.path.dirname(HERE), "content", "figures.js")
    if not os.path.exists(fig_path):
        return out
    src = io.open(fig_path, encoding="utf-8").read()
    have = set(re.findall(r'^"([a-z0-9-]+)":"', src, re.M))
    if not have:
        return ["content/figures.js から絵を1枚も読めません"]

    # index.html が読み込んでいるか。読まれなければ絵は永久に出ない。
    idx = os.path.join(os.path.dirname(HERE), "index.html")
    if os.path.exists(idx):
        if "content/figures.js" not in io.open(idx, encoding="utf-8").read():
            out.append("index.html が content/figures.js を読み込んでいません")

    used = set()
    for root, _d, files in os.walk(os.path.join(os.path.dirname(HERE), "content")):
        for f in files:
            # 教材ではない置き場（絵・長文の本文）は数えない。
            if not f.endswith(".js") or f in ("manifest.js", "figures.js",
                                              "readings.js"):
                continue
            body = io.open(os.path.join(root, f), encoding="utf-8").read()
            # **Q の行だけ見る。** 英語パックの V 行は9列あり、
            # 7列目に "queue-jumping" のような連語が入る。
            # ファイル全体を走査すると、それを図の名前と読みちがえる。
            i = body.find("var Q = [")
            if i < 0:
                continue
            body = body[i:body.find("];", i)]
            for row in re.findall(r'^\[".*\]', body, re.M):
                cells = re.findall(r'"((?:[^"\\]|\\.)*)"', row)
                if len(cells) >= 7 and re.fullmatch(r"[a-z0-9-]+", cells[6]):
                    used.add(cells[6])
                    if cells[6] not in have:
                        out.append("%s が知らない図を指しています: %s"
                                   % (f[:-3], cells[6]))
    for name in sorted(have - used):
        out.append("図 %s は どの問題からも使われていません" % name)
    return out


def check_readings():
    """長文の本文が、教材と本文置き場で食い違っていないか。

    教材のQ行の8列目は本文の名前で、本文は content/readings.js にある。
    名前がずれると「次の文章を読みなさい」という設問が **本文なしで**出る。
    落ちないし、エラーも出ない。生徒には答えようがない。
    """
    out = []
    app = os.path.dirname(HERE)
    path = os.path.join(app, "content", "readings.js")
    if not os.path.exists(path):
        return out
    src = io.open(path, encoding="utf-8").read()
    have = set(re.findall(r'^"([a-z0-9-]+)":"', src, re.M))
    if not have:
        return ["content/readings.js から本文を1つも読めません"]
    idx = os.path.join(app, "index.html")
    if os.path.exists(idx):
        if "content/readings.js" not in io.open(idx, encoding="utf-8").read():
            out.append("index.html が content/readings.js を読み込んでいません")
    used = set()
    for root, _d, files in os.walk(os.path.join(app, "content")):
        for f in files:
            if not f.endswith(".js") or f in ("manifest.js", "figures.js",
                                              "readings.js"):
                continue
            body = io.open(os.path.join(root, f), encoding="utf-8").read()
            i = body.find("var Q = [")
            if i < 0:
                continue
            body = body[i:body.find("];", i)]
            for row in re.findall(r'^\[".*\]', body, re.M):
                cells = re.findall(r'"((?:[^"\\]|\\.)*)"', row)
                if len(cells) >= 8 and cells[7]:
                    used.add(cells[7])
                    if cells[7] not in have:
                        out.append("%s が知らない本文を指しています: %s"
                                   % (f[:-3], cells[7]))
    for name in sorted(have - used):
        out.append("本文 %s は どの設問からも使われていません" % name)
    return out


def check_id_clash():
    """**教材をまたいで、項目IDがぶつかっていないか。**

    IDは「教科コード:種類:見出しを簡単にした文字列」で作る。
    簡単にする過程で記号は落ちるので、
        (−2)²  と  (−2)³   → どちらも  mat:q:2-
    のように、**別の問題が同じIDになる**ことがある。
    そうなると、片方に答えたときもう片方の記録が動く。
    画面にはエラーが出ない ―― 気づくのは、覚えたはずの問題が
    いつまでも「にがて」に残るときである（実際に3件あった）。

    1つのファイルの中の重複は上の検査が見ている。ここが見るのは
    **同じ教科・同じ学年に読み込まれる教材どうし**のぶつかりである。
    """
    import collections
    # HERE は app/tools。server は2つ上の階層にある。
    # ここを1階層まちがえると import が静かに失敗し、検査そのものが
    # 何も見ないまま「指摘0件」を返す ―― 実際そうなった。
    repo = os.path.dirname(os.path.dirname(HERE))
    sys.path.insert(0, os.path.join(repo, "server"))
    os.environ.setdefault("MYACADY_ROOT", "/tmp/tube-check-%d" % os.getpid())
    try:
        import examprep
    except ImportError as e:
        return ["教材の検査そのものが動いていない（%s）" % e]
    out = []
    for sub in ("japanese", "math", "science", "social", "english"):
        for g in ("e4", "e5", "e6", "j1", "j2", "j3"):
            try:
                items = examprep.pack_items(sub, g)
            except Exception:                    # noqa: BLE001
                continue
            # pack_items は画面と同じ規則で重複を落とすので、
            # ここでは **落とす前** を見る（落とされた事実こそ知りたい）。
            seen = collections.defaultdict(list)
            for x in _raw_items(sub, g):
                seen[x["id"]].append(x)
            for iid, g2 in seen.items():
                if len(g2) < 2:
                    continue
                ans = {x.get("ans") or "" for x in g2}
                if len(ans) > 1:
                    out.append("%s %s  同じIDで答えがちがう %s ← %s"
                               % (sub, g, iid,
                                  " / ".join(sorted(ans)[:2])))
    return out

def main():
    man = io.open(os.path.join(CONTENT, "manifest.js"), encoding="utf-8").read()
    declared = re.findall(
        r"id:'([\w/\-]+)',\s*subject:'(\w+)',\s*file:'([\w/\-.]+)'"
        r"[^}]*?bands:\[([^\]]*)\]", man, re.S)

    listed_files = set()
    total_items = 0
    total_problems = 0

    print("教材の検査\n" + "=" * 56)
    for pid, subject, rel, bands_raw in declared:
        bands = re.findall(r"'([^']+)'", bands_raw)
        path = os.path.join(CONTENT, rel)
        listed_files.add(os.path.normpath(path))
        if not os.path.exists(path):
            print("  ✗ %-24s ファイルがありません: content/%s" % (pid, rel))
            total_problems += 1
            continue
        n, problems = check_pack(path, bands)
        total_items += n
        mark = "  " if not problems else "✗ "
        print("%s%-24s %3d項目  帯 %s" % (mark, pid, n, "・".join(bands)))
        for lineno, msg in problems:
            where = ("%s:%d" % (rel, lineno)) if lineno else rel
            print("      %s  %s" % (where, msg))
        total_problems += len(problems)

    # 目録に載っていないファイル
    for root, _dirs, files in os.walk(CONTENT):
        for f in files:
            # manifest.js は目録そのもの。
            # figures.js は教材ではなく、教材が名前で引く絵の置き場
            # （どの学年でも使うので index.html が先に読む）。
            # 教材ではない置き場（絵・長文の本文）は数えない。
            if not f.endswith(".js") or f in ("manifest.js", "figures.js",
                                              "readings.js"):
                continue
            p = os.path.normpath(os.path.join(root, f))
            if p not in listed_files:
                rel = os.path.relpath(p, CONTENT)
                print("  ✗ content/%s が目録（manifest.js）に載っていません" % rel)
                print("      → packs に1行足してください。載せないと出題されません")
                total_problems += 1

    # 進度が実在する教材を指しているか
    for msg in check_curriculum({d[0] for d in declared}):
        print("  ✗ %s" % msg)
        print("      → 教材の名前を変えたら、app/curriculum.js も直すこと")
        total_problems += 1

    # 長文の本文
    for line in check_readings():
        print("  ✗ %s" % line)
        print("      → 教材の8列目と content/readings.js の名前をそろえること")
        total_problems += 1

    # 図の名前
    for line in check_figures():
        print("  ✗ %s" % line)
        print("      → 教材の7列目と content/figures.js の名前をそろえること")
        total_problems += 1

    # 英語の単語表の重複
    for line in check_english_dup():
        print("  ✗ %s" % line)
        print("      → どちらかを消すこと。残すのは意味と例が濃いほう")
        total_problems += 1

    # 教材をまたいだIDのぶつかり
    for line in check_id_clash():
        print("  ✗ %s" % line)
        print("      → 記号だけが違う問題文にしない。言葉で書き分けること")
        total_problems += 1

    print("=" * 56)
    print("合計 %d項目 / 指摘 %d件" % (total_items, total_problems))
    return 1 if total_problems else 0


if __name__ == "__main__":
    sys.exit(main())
