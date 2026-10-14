#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python の標準ライブラリと同じ名前の .py が無いことを確かめる。

2026-10-14、秘密の検査を scripts/check/secrets.py という名前で置いたら、scripts/check を読み込む流れ（adm_flow*・expect.py）で
標準の secrets が隠れ、scram.py の secrets.token_urlsafe が無いと落ちた。同じ名前を二度と置かないための不変条件。

    python3 scripts/check/stdlib_shadow.py     # 0 なら通った"""
import os, subprocess, sys, sysconfig

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def stdlib_names():
    names = set(sys.builtin_module_names)
    names |= set(getattr(sys, "stdlib_module_names", ()))          # 3.10 から
    d = sysconfig.get_paths()["stdlib"]
    for f in os.listdir(d):
        if f.endswith(".py"):
            names.add(f[:-3])
        elif os.path.isfile(os.path.join(d, f, "__init__.py")):
            names.add(f)
    dyn = os.path.join(d, "lib-dynload")
    if os.path.isdir(dyn):
        names |= {f.split(".")[0] for f in os.listdir(dyn)}
    names |= {"graphlib", "zoneinfo", "tomllib"}                    # 手元の 3.9 に無い新しい標準
    return names

def main():
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "*.py"],
                             cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8", "replace")
        files = [f for f in out.split("\0") if f]
    except Exception:
        files = [os.path.relpath(os.path.join(dp, f), ROOT) for dp, _, fs in os.walk(ROOT) for f in fs if f.endswith(".py")]
    std = stdlib_names()
    bad = [f for f in files if os.path.basename(f)[:-3] in std]
    for f in bad:
        print("×  %s は標準ライブラリの %s と同じ名前（同じ置き場から読み込む道具で標準のほうが隠れる）" % (f, os.path.basename(f)[:-3]))
    print("名前のぶつかり：%s（%d ファイル）" % ("× %d 件" % len(bad) if bad else "なし", len(files)))
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
