#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""講師の名字が Git に入らないようにする（2026-10-14 の決まり。knowledge/20-決まり/権限の線.md）。

    python3 scripts/check/surnames.py                    … Git が追っているファイル全部
    python3 scripts/check/surnames.py ファイル…           … 手元のファイル
    python3 scripts/check/surnames.py --staged ファイル…  … commit に入る中身（index）で（pre-commit）
    python3 scripts/check/surnames.py --message ファイル  … commit の説明文（commit-msg）

・名字の表 `カリキュラム/時間割の講師.csv`（手元だけ）が無いところ（GitHub・雲）では流さずに 0 で終わる。
・名字そのものは画面に出さない。出すのはファイル・行・講師の ID・件数だけ。
・2 字以上の名字はどこに出ても数える。1 字の名字は、名字として使う形（〜先生・＝〜・「〜」・（〜）・〜 wt）だけ数える。
・名字を含む別の言葉（歴史上の人名など）は、手元だけの `カリキュラム/時間割の講師_例外.txt` に 1 行 1 語で書く。
  例外の言葉も名字の字を明かすので、Git にも文書にも書かない（10-14 に作業記録へ書いて履歴ごと消した）。
・仕組みの確かめは scripts/check/test_surnames.py（作り物の名字で。GitHub でも流れる）。
"""
import csv
import io
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CSV = os.environ.get("TUBE_SURNAMES_CSV") or os.path.join(ROOT, "カリキュラム", "時間割の講師.csv")
EXC = os.environ.get("TUBE_SURNAMES_EXCEPT") or os.path.join(ROOT, "カリキュラム", "時間割の講師_例外.txt")
ONE_FORMS = ("{}先生", "＝{}", "「{}」", "（{}）", "{} wt")
BINARY_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".mp4", ".mov", ".m4a", ".mp3",
              ".pdf", ".docx", ".pptx", ".xlsx", ".zip", ".woff", ".woff2", ".ttf", ".otf")


def load():
    """[(名字, ID)] と例外の言葉。名字の表が無ければ None。"""
    if not os.path.exists(CSV):
        return None
    with io.open(CSV, encoding="utf-8-sig", newline="") as f:
        rows = [((r.get("講師") or "").strip(), (r.get("ID") or "").strip()) for r in csv.DictReader(f)]
    names = [(n, i or "?") for n, i in rows if n]
    exc = []
    if os.path.exists(EXC):
        with io.open(EXC, encoding="utf-8") as f:
            exc = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    return names, exc


def hits(text, names, exc):
    """[(行, ID, 種類)]。例外の言葉の中にある名字は数えない。"""
    spans = []
    for w in exc:
        k = text.find(w)
        while k >= 0:
            spans.append((k, k + len(w)))
            k = text.find(w, k + 1)
    out = []
    for n, i in names:
        pats = [n] if len(n) >= 2 else [f.format(n) for f in ONE_FORMS]
        for p in pats:
            k = text.find(p)
            while k >= 0:
                at = k + p.index(n)
                if not any(a <= at and at + len(n) <= b for a, b in spans):
                    out.append((text.count("\n", 0, k) + 1, i, "2 字以上" if len(n) >= 2 else "1 字の名字の形"))
                k = text.find(p, k + 1)
    return out


def read(path, staged):
    """文字のファイルなら中身、文字でなければ None、見つからなければ False。"""
    if path.lower().endswith(BINARY_EXT):
        return None
    if staged:
        r = subprocess.run(["git", "-C", ROOT, "show", ":" + path], capture_output=True)
        if r.returncode != 0:
            return None
        data = r.stdout
    else:
        # 相対の道は、今いる場所から探し、無ければ置き場の根から（pre-commit は根から流れる）。2026-10-20 に根からだけ探して 0 件と黙った
        full = path if os.path.isabs(path) or os.path.isfile(path) else os.path.join(ROOT, path)
        if not os.path.isfile(full):
            return False
        with open(full, "rb") as f:
            data = f.read()
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", "ignore")


def main(argv):
    loaded = load()
    if loaded is None:
        print("名字の検査：名字の表が無いので流していない（名字の表がある手元の Mac だけで流れる）")
        return 0
    names, exc = loaded
    found = []
    if argv[:1] == ["--message"]:
        with io.open(argv[1], encoding="utf-8", errors="ignore") as f:
            text = "\n".join(l for l in f.read().split("\n") if not l.startswith("#"))
        found = [("（commit の説明文）", h) for h in hits(text, names, exc)]
        n_files = 1
    else:
        staged = argv[:1] == ["--staged"]
        files = argv[1:] if staged else argv
        explicit = bool(files)      # 名前を指定したときだけ、見つからないファイルを × にする
        if not files:
            out = subprocess.run(["git", "-C", ROOT, "ls-files", "-z"], capture_output=True).stdout
            files = [f for f in out.decode("utf-8").split("\0") if f]
        n_files = 0
        missing = []
        for f in files:
            text = read(f, staged)
            if text is False:
                if explicit:
                    missing.append(f)
                continue
            if text is None:
                continue
            n_files += 1
            found += [(f, h) for h in hits(text, names, exc)]
    if argv[:1] != ["--message"] and missing:
        print("× 名字の検査：読めなかったファイルが %d 個（例 %s）" % (len(missing), missing[0]))
        return 1
    if not found:
        print("名字の検査：なし（%d ファイル）" % n_files)
        return 0
    for f, (line, i, kind) in found:
        print("× %s:%d %s の名字（%s）" % (f, line, i, kind))
    print("× 講師の名字が %d 件（名字は画面に出していない。ログインID で書き直す）" % len(found))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
