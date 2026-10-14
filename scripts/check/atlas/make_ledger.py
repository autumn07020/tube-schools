# -*- coding: utf-8 -*-
"""02-画面台帳.md を、台帳（atlas.json）から作る。 python3 make_ledger.py <S>"""
import json, collections, sys
S = sys.argv[1]; A = S + "/atlas"
d = json.load(open(A + "/atlas.json")); items = d["items"]
out = ["# 画面台帳 ―― TUBE study のいまの全画面", "",
       "動いている実物から撮った **%d 画面・%d 枚**。番号（ID）は、機械（iPhone・パソコン・iPad）や見本の生徒が違っても、同じ画面なら同じ。" % (len(items), sum(len(x["files"]) for x in items)),
       "写しのファイルは `画面.nosync/` に、巻ごとの PDF は `本/` にある。「枚」は、下へ巻いた続きを含む枚数。", "",
       "番号の頭：**E** 入口と初回登録／**K** 時期で出る札／**S** 生徒／**T** 講師（T5xx は担当の少ない講師）／**A** 管理ページ／**P** 刷る紙／**N** 紙の宿題の道具", ""]
for vol, name in d["volumes"]:
    its = [x for x in items if x["vol"] == vol]
    out += ["## %s" % name, "", "PDF：`本/%s.pdf`" % name, ""]
    groups = collections.OrderedDict()
    for x in its: groups.setdefault(x["group"], []).append(x)
    for g, xs in groups.items():
        out += ["### %s" % g, "", "| 番号 | 画面 | 行き方 | 補足 | 枚 | 最初のファイル |", "|---|---|---|---|---|---|"]
        for x in xs:
            out.append("| `%s` | %s | %s | %s | %d | `%s` |" % (x["id"], x["title"].replace("|", "／"), x["how"].replace("|", "／"), (x["note"] or "").replace("|", "／"), len(x["files"]), x["files"][0]))
        out.append("")
open(A + "/out/02-画面台帳.md", "w", encoding="utf-8").write("\n".join(out) + "\n"); print("02-画面台帳.md", len(items), "画面")
