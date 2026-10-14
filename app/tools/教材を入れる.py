#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教材を CSV から入れる ―― 全教科・1つの口。

    python3 app/tools/教材を入れる.py 理科-小5.csv \\
        --id waseda/science-e5 --name '理科 小5' --subject science \\
        --band 小5 --source '自社教材' --yes

    （--yes を付けるまでは書き出さない。何が入るかだけ出す）

なぜ CSV か
-----------
いま入っている教材は、こちらで書き下ろした仮のものである。
本物（早稲田アカデミーの自社教材）が入ったら**丸ごと入れ替える**。
そのとき Python の生成スクリプトを教科ごとに書き直すのでは、
入れ替えのたびに人手が要る。

だから入口を1つにする。**表計算で作った CSV を1枚渡すだけ**にする。
出す側（教材を出す.py）と組みで使えば、

    出す → Excel で直す → 入れる

で往復できる。往復して中身が変わらないことは検査が見ている。

CSV の形
--------
1行が1問。列の名前は日本語でも英語でもよい。

    種別,問題,答え,誤答,単元,解説,例,例の訳,図

    種別   用語 か 選択。**省いてよい**（誤答があれば選択、無ければ用語）
    問題   用語なら表の言葉、選択なら問題文。**ここが項目IDのもと**
    答え   用語なら意味、選択なら正解
    誤答   選択のときだけ。| で区切って3つ
    単元   「電気の回路」など。**空にしないこと** ―― 5週の反復が効かなくなる
    解説   ひとこと。無くてよい
    例     例文。無くてよい
    例の訳 例文の訳。無くてよい
    図     app/content/figures.js の絵の名前。無くてよい

    種別,問題,答え,誤答,単元,解説,,,図
    用語,電流,回路を流れる電気の流れ,,電気の回路,,,,
    選択,豆電球を2つ直列につなぐと 明るさは？,暗くなる,明るくなる|変わらない|消える,電気の回路,電流が小さくなる,,,circuit-series

項目ID について ―― ここを変えると進捗が切れる
----------------------------------------------
IDは「問題」の列から作る。**同じ問題文なら同じID**なので、
問題文を変えずに答えや解説を直すぶんには、生徒の学習記録は残る。
問題文を書き換えると、その問題は「新しい問題」になる。
入れ替えのときに何件がIDごと変わるかは、書き出す前に出す。

著作権について ―― ここを間違えると事業が止まる
----------------------------------------------
入れてよいのは
  * 早稲田アカデミーが権利を持つ自社教材
  * ご自身で作成したデータ
のどちらかだけ。市販教材からの転記は入れない。
出どころは --source に必ず書く（教材ファイルの先頭に残る）。
"""

import argparse
import csv
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_content import Pack                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
CONTENT = os.path.join(APP, "content")
MANIFEST = os.path.join(CONTENT, "manifest.js")

# 列の名前。**日本語でも英語でもよい。**
# 学校から届く表の見出しは、こちらでは決められない。
COL = {
    "kind": ("種別", "型", "kind", "type"),
    "q":    ("問題", "表", "問", "front", "q", "question", "word", "見出し"),
    "a":    ("答え", "裏", "答", "back", "a", "ans", "answer", "意味", "ja"),
    "dis":  ("誤答", "誤り", "まちがい", "選択肢", "dis", "wrong"),
    "unit": ("単元", "範囲", "unit"),
    "note": ("解説", "ひとこと", "メモ", "note", "memo"),
    "ex":   ("例", "例文", "ex", "example"),
    "exja": ("例の訳", "例文訳", "訳", "exja"),
    "fig":  ("図", "fig", "figure", "絵"),
    # 帯は学年（小5・中1）。出す側が付けるので、入れる側も読む。
    # 列が無ければ --band を使う。
    "band": ("帯", "学年", "band", "level", "レベル", "難度"),
}
TERM = {"用語", "T", "t", "term", "ことば"}
QUIZ = {"選択", "Q", "q", "quiz", "4択", "四択", "問題"}


def pick(row, key):
    for name in COL[key]:
        for k in row:
            if k and k.strip().lower() == name.lower():
                return (row[k] or "").strip()
    return ""


def read_csv(path):
    """CSV を読む。BOM 付き（Excel が付ける）でも読めるようにする。"""
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f)]


def old_ids(pack_id):
    """いま入っている教材の項目ID。入れ替えで何件切れるかを数えるのに使う。"""
    sys.path.insert(0, os.path.join(os.path.dirname(APP), "server"))
    os.environ.setdefault("MYACADY_ROOT", "/tmp/tube-import-%d" % os.getpid())
    try:
        import examprep
    except ImportError:
        return None
    path = os.path.join(CONTENT, pack_id + ".js")
    if not os.path.exists(path):
        return set()
    src = io.open(path, encoding="utf-8").read()
    ids = set()
    for var, kind in (("T", "t"), ("Q", "q")):
        for body in examprep._sections(src, var):
            for r in examprep._rows(body):
                if r:
                    ids.add("%s:%s" % (kind, examprep._slug(r[0])))
    return ids


def upsert_manifest(pack_id, subject, name, bands, note, count):
    """目録に1行足す（すでにあれば数だけ直す）。

    **目録に載らない教材は、1問も出ない。** 忘れると気づけないので、
    手で足させない。
    """
    src = io.open(MANIFEST, encoding="utf-8").read()
    entry = ("""    { id:'%s', subject:'%s', file:'%s.js',
      name:'%s', items:%d,
      bands:[%s],
      note:'%s' },"""
             % (pack_id, subject, pack_id, name, count,
                ", ".join("'%s'" % b for b in bands), note.replace("'", "")))
    key = "{ id:'%s'," % pack_id
    i = src.find(key)
    if i >= 0:
        # すでにある。その行かたまり（次の "}," まで）を差し替える。
        start = src.rfind("\n", 0, i) + 1
        end = src.find("},", i) + 2
        src = src[:start] + entry.lstrip("\n") + src[end:]
    else:
        anchor = "  packs: ["
        j = src.index(anchor) + len(anchor)
        src = src[:j] + "\n" + entry + "\n" + src[j:]
    io.open(MANIFEST, "w", encoding="utf-8").write(src)


def main():
    ap = argparse.ArgumentParser(description="教材をCSVから入れる")
    ap.add_argument("csv")
    ap.add_argument("--id", required=True,
                    help="教材ID（例 waseda/science-e5）。content/ の下の道になる")
    ap.add_argument("--name", required=True, help="画面に出す名前（例 理科 小5）")
    ap.add_argument("--subject", required=True,
                    help="english / japanese / math / science / social")
    ap.add_argument("--band", default="", help="帯が空の行に使う値（例 小5）")
    ap.add_argument("--source", required=True, help="出どころ。教材の先頭に残る")
    ap.add_argument("--english", action="store_true",
                    help="英語の教材（本文に英単語が並ぶ）。字の検査をゆるめる")
    ap.add_argument("--yes", action="store_true", help="実際に書き出す")
    a = ap.parse_args()

    rows = read_csv(a.csv)
    if not rows:
        print("行がありません: %s" % a.csv)
        return 1

    before = old_ids(a.id)
    bands, items, bad = set(), [], []
    for n, r in enumerate(rows, 2):          # 2行目からがデータ
        q, ans = pick(r, "q"), pick(r, "a")
        if not q or not ans:
            bad.append((n, "問題か答えが空です"))
            continue
        dis = [x.strip() for x in pick(r, "dis").split("|") if x.strip()]
        kind = pick(r, "kind")
        if kind in TERM:
            k = "T"
        elif kind in QUIZ:
            k = "Q"
        else:
            k = "Q" if dis else "T"          # 種別が無ければ誤答の有無で決める
        if k == "Q" and not dis:
            bad.append((n, "選択なのに誤答がありません"))
            continue
        band = pick(r, "band") if pick(r, "band") else a.band
        if not band:
            bad.append((n, "帯（学年）がありません。--band を付けてください"))
            continue
        bands.add(band)
        items.append({"k": k, "q": q, "a": ans, "dis": dis, "band": band,
                      "unit": pick(r, "unit"), "note": pick(r, "note"),
                      "ex": pick(r, "ex"), "exja": pick(r, "exja"),
                      "fig": pick(r, "fig")})

    nou = [x for x in items if x["k"] == "Q" and not x["unit"]]
    print("%s から %d行" % (a.csv, len(rows)))
    print("  取り込める   %d（用語 %d / 選択 %d）"
          % (len(items), sum(1 for x in items if x["k"] == "T"),
             sum(1 for x in items if x["k"] == "Q")))
    print("  帯           %s" % "、".join(sorted(bands)))
    if nou:
        print("  ⚠ 単元が空の選択問題 %d件 ―― 5週の反復と苦手つぶしが効きません"
              % len(nou))
    for n, why in bad[:10]:
        print("  × %d行目 %s" % (n, why))
    if len(bad) > 10:
        print("  × ほか %d行" % (len(bad) - 10))

    if before is not None:
        new = set()
        for x in items:
            new.add("%s:%s" % (x["k"].lower(), _slug_of(x["q"])))
        gone, add = before - new, new - before
        if before:
            print("  入れ替え     残る %d / 消える %d / 新しい %d"
                  % (len(before & new), len(gone), len(add)))
            if gone:
                print("               消える分の学習記録は引き継げません")

    if not a.yes:
        print("\n  --yes を付けると書き出します。")
        return 0

    p = Pack(a.id, a.subject, a.name, sorted(bands),
             "出どころ: %s" % a.source, english=a.english)
    for x in items:
        if x["k"] == "T":
            p.T(x["q"], x["a"], x["band"], x["note"], x["ex"], x["exja"])
        else:
            p.Q(x["q"], x["a"], x["dis"], x["band"], x["note"],
                unit=x["unit"], fig=x["fig"])
    p.write()
    upsert_manifest(a.id, a.subject, a.name, sorted(bands),
                    "出どころ: %s" % a.source, len(items))
    print("\n  書き出しました: app/content/%s.js（目録にも入れました）" % a.id)
    print("  確かめる: python3 app/tools/check-content.py")
    return 0


def _slug_of(t):
    sys.path.insert(0, os.path.join(os.path.dirname(APP), "server"))
    os.environ.setdefault("MYACADY_ROOT", "/tmp/tube-import-%d" % os.getpid())
    import examprep
    return examprep._slug(t)


if __name__ == "__main__":
    sys.exit(main())
