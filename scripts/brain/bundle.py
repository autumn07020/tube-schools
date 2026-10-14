#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外部脳（knowledge/）を 1 本の Markdown にまとめる（ChatGPT の Project・NotebookLM・Google Drive に写すため）。
    python3 scripts/brain/bundle.py [出力先]      既定は knowledge/_全部.md（.gitignore 済み）
INDEX → 各ファイルの順。archive/ は入れない。"""
import io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
K = os.path.join(ROOT, "knowledge")

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(K, "_全部.md")
    index = io.open(os.path.join(K, "INDEX.md"), encoding="utf-8").read()
    order = re.findall(r"`((?:[0-9]{2}-[^`]+?\.md))`", index)
    parts = ["# TUBE study 外部脳（まとめ）\n\n原本は Git の knowledge/。これは写し。\n\n", index, "\n\n"]
    for rel in order:
        p = os.path.join(K, rel)
        if not os.path.isfile(p): continue
        s = io.open(p, encoding="utf-8").read()
        parts.append("\n\n---\n\n<!-- %s -->\n\n" % rel)
        parts.append(s)
    io.open(out, "w", encoding="utf-8").write("".join(parts))
    print("書いた: %s（%d ファイル・%d 文字）" % (out, len(order), sum(len(x) for x in parts)))

if __name__ == "__main__":
    main()
