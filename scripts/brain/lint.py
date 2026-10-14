#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外部脳（knowledge/）の決まりを確かめる。
  ・INDEX.md に、knowledge/ の .md（INDEX と archive/ 以外）が全部載っていて、載っているものが全部ある
  ・各ファイルの先頭に name・description・updated（YYYY-MM-DD）・owner・status の表がある
  ・秘密らしい文字列が無い（scripts/check/secrets.py と同じ規則）
    python3 scripts/brain/lint.py            # 0 なら通った"""
import io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
K = os.path.join(ROOT, "knowledge")
sys.path.insert(0, os.path.join(ROOT, "scripts", "check"))
try:
    import secrets as sec   # scripts/check/secrets.py（標準ライブラリの secrets と同名。先頭に入れたのでこちらが勝つ）
    sec = sec if hasattr(sec, "RULES") else None
except Exception:
    sec = None

def files():
    out = []
    for dp, dns, fns in os.walk(K):
        dns[:] = [d for d in dns if d != "archive"]
        for f in fns:
            if f.endswith(".md") and f != "INDEX.md" and not f.startswith("_"):   # _全部.md などの写しは見ない
                out.append(os.path.relpath(os.path.join(dp, f), K))
    return sorted(out)

def main():
    bad = 0
    index = io.open(os.path.join(K, "INDEX.md"), encoding="utf-8").read()
    listed = set(re.findall(r"`((?:[0-9]{2}-[^`]+?\.md))`", index))
    actual = set(files())
    for f in sorted(actual - listed):
        print("×  INDEX に無い: %s" % f); bad += 1
    for f in sorted(listed - actual):
        print("×  INDEX にあるが実体が無い: %s" % f); bad += 1
    for f in sorted(actual | {"INDEX.md"}):
        p = os.path.join(K, f)
        s = io.open(p, encoding="utf-8").read()
        m = re.match(r"---\n(.*?)\n---\n", s, re.S)
        if not m:
            print("×  先頭の表が無い: %s" % f); bad += 1; continue
        head = m.group(1)
        for key in ("name", "description", "updated", "owner", "status"):
            if not re.search(r"^%s:\s*\S" % key, head, re.M):
                print("×  先頭の表に %s が無い: %s" % (key, f)); bad += 1
        d = re.search(r"^updated:\s*(\d{4}-\d{2}-\d{2})\s*$", head, re.M)
        if not d:
            print("×  updated が YYYY-MM-DD でない: %s" % f); bad += 1
        if sec:
            for rx, why, only in sec.RULES:
                if only and ".md" not in only: continue
                if rx.search(s):
                    print("×  %s: %s" % (why, f)); bad += 1
    print("知識の検査：%s（%d ファイル）" % ("× %d 件" % bad if bad else "通った", len(actual) + 1))
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
