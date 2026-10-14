#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教材を CSV に出す ―― 表計算で直すため。

    python3 app/tools/教材を出す.py                    # ぜんぶ出す
    python3 app/tools/教材を出す.py science/e5          # 1つだけ
    python3 app/tools/教材を出す.py --out ~/Desktop/教材

出したものは **そのまま 教材を入れる.py に戻せる**。

    出す → Excel で直す → 入れる

往復して中身が変わらないことは app/tools/こわれ方の検査.py が見ている。
往復できないと「入れ替えやすい」とは言えない ――
出した形と入れる形がちがうと、毎回 手で直すことになる。

列は 教材を入れる.py と同じ。
    種別,問題,答え,誤答,単元,解説,例,例の訳,図,帯
"""

import argparse
import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
CONTENT = os.path.join(APP, "content")
sys.path.insert(0, os.path.join(os.path.dirname(APP), "server"))
os.environ.setdefault("MYACADY_ROOT", "/tmp/tube-export-%d" % os.getpid())

import examprep                                # noqa: E402

HEAD = ["種別", "問題", "答え", "誤答", "単元", "解説", "例", "例の訳", "図", "帯"]


def rows_of(path):
    """1つの教材ファイルから、CSVの行を作る。"""
    src = io.open(path, encoding="utf-8").read()
    out = []
    # T（用語）  [表, 裏, 帯, 解説, 例, 例の補足]
    for body in examprep._sections(src, "T"):
        for r in examprep._rows(body):
            if len(r) < 2:
                continue
            r = list(r) + [""] * (6 - len(r))
            out.append(["用語", r[0], r[1], "", "", r[3], r[4], r[5], "", r[2]])
    # Q（選択）  [問題文, 正解, 誤答(|), 帯, 解説, 単元, 図]
    for body in examprep._sections(src, "Q"):
        for r in examprep._rows(body):
            if len(r) < 2:
                continue
            r = list(r) + [""] * (7 - len(r))
            # 5列しかない古い教材は、5列目が解説か単元かを見分ける
            if len(examprep._rows(body)[0]) > 5:
                note, unit = r[4], r[5]
            else:
                note = r[4] if examprep._is_note(r[4]) else ""
                unit = "" if examprep._is_note(r[4]) else r[4]
            out.append(["選択", r[0], r[1], r[2], unit, note, "", "", r[6], r[3]])
    return out


def main():
    ap = argparse.ArgumentParser(description="教材をCSVに出す")
    ap.add_argument("pack", nargs="?", default="",
                    help="教材ID（例 science/e5）。省くとぜんぶ")
    ap.add_argument("--out", default="", help="出す先のフォルダ（既定は 教材CSV/）")
    a = ap.parse_args()

    out_dir = a.out or os.path.join(os.path.dirname(APP), "教材CSV")
    os.makedirs(out_dir, exist_ok=True)

    targets = []
    for sub in sorted(os.listdir(CONTENT)):
        d = os.path.join(CONTENT, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".js"):
                pid = "%s/%s" % (sub, f[:-3])
                if not a.pack or pid == a.pack:
                    targets.append((pid, os.path.join(d, f)))
    if not targets:
        print("見つかりません: %s" % (a.pack or "(なし)"))
        return 1

    total = 0
    for pid, path in targets:
        rows = rows_of(path)
        if not rows:
            continue
        name = pid.replace("/", "-") + ".csv"
        with io.open(os.path.join(out_dir, name), "w",
                     encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(HEAD)
            w.writerows(rows)
        total += len(rows)
        print("  %-28s %4d行 → %s" % (pid, len(rows), name))
    print("\n  合計 %d行 → %s" % (total, out_dir))
    print("  直したら: python3 app/tools/教材を入れる.py <CSV> --id … --yes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
