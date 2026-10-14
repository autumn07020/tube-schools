#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""履歴に入れてはいけないものが混ざっていないか調べる（鍵・合言葉・本物の束・講師の名字の表）。

    python3 scripts/check/secrets.py            # git に入るファイル全部（git が無ければ作業ツリー）
    python3 scripts/check/secrets.py a.py b.sh  # 指定したファイルだけ（pre-commit が使う）

見つけたら 1 で終わる。わざと置いてあるもの（検査用の束・検査用の合言葉）は ALLOW に書く。"""
import io, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# (正規表現, 何か, 見る拡張子（None は全部）)。検査コードの中の合言葉の文字列は、.json のデータだけを見ることで除く
RULES = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "秘密鍵", None),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS のアクセスキー", None),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), "GitHub のトークン", None),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "API の鍵", None),
    (re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b"), "Slack のトークン", None),
    (re.compile(r"\"password\"\s*:\s*\"[^\"]{4,}\""), "合言葉そのもの（JSON のデータ）", {".json"}),
    (re.compile(r"\"storedKey\"\s*:\s*\"[0-9a-f]{32,}\""), "合言葉の検証子（束）", {".json"}),
    (re.compile(r"--password\s+[\"']?(?!kensa-)[A-Za-z0-9-]{8,}"), "合言葉そのもの（コマンド）", None),
]
# 置いてよいもの：検査用の束（ハッシュだけ・本物ではない）と、検査の土台の合言葉（kensa-…）
ALLOW = {
    "scripts/check/flows/fixture-bundle.json",
}
NAME_RULES = [
    (re.compile(r"(^|/)合言葉の表\.nosync(/|$)"), "合言葉の表"),
    (re.compile(r"(^|/)demo-accounts\.json$"), "デモの口座（合言葉入り）"),
    (re.compile(r"(^|/)deploy/accounts/"), "本物の束"),
    (re.compile(r"(^|/)時間割の講師\.csv$"), "名字→ID の表"),
    (re.compile(r"(^|/)時間割\.(csv|json)$"), "講師の名字入りの時間割"),
    (re.compile(r"\.pem$"), "鍵"),
]
TEXT = {".py", ".js", ".sh", ".md", ".json", ".csv", ".txt", ".html", ".css", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".service", ".例", ""}

def tracked():
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, check=True).stdout
        return [p for p in out.decode("utf-8", "replace").split("\0") if p]
    except Exception:
        res = []
        for dp, dns, fns in os.walk(ROOT):
            dns[:] = [d for d in dns if d != ".git" and not d.endswith(".nosync")]
            for f in fns:
                res.append(os.path.relpath(os.path.join(dp, f), ROOT))
        return res

def main(argv):
    files = argv or tracked()
    bad = 0
    for rel in files:
        rel = rel.replace(os.sep, "/")
        for rx, why in NAME_RULES:
            if rx.search(rel):
                print("×  %s  （%s は履歴に入れない）" % (rel, why)); bad += 1
        if rel in ALLOW: continue
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p) or os.path.splitext(rel)[1].lower() not in TEXT: continue
        try:
            if os.path.getsize(p) > 4_000_000: continue
            s = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for rx, why, only in RULES:
            if only and os.path.splitext(rel)[1].lower() not in only: continue
            m = rx.search(s)
            if m:
                line = s.count("\n", 0, m.start()) + 1
                print("×  %s:%d  %s" % (rel, line, why)); bad += 1
    print("秘密の検出：%s（%d ファイル）" % ("× %d 件" % bad if bad else "なし", len(files)))
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
