#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""名字の検査（surnames.py）の仕組みを、作り物の名字で確かめる。本物の名字の表は使わない（GitHub でも流れる）。

    python3 scripts/check/test_surnames.py
"""
import io
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "surnames.py")
FAKE2, FAKE1 = "検査谷", "仮"          # 作り物の名字（2 字以上と 1 字）
ok = ng = 0


def run(args, csv_path, exc_path, cwd=None):
    env = dict(os.environ, TUBE_SURNAMES_CSV=csv_path, TUBE_SURNAMES_EXCEPT=exc_path)
    r = subprocess.run([sys.executable, TOOL] + args, capture_output=True, text=True, env=env, cwd=cwd)
    return r.returncode, r.stdout + r.stderr


def check(name, cond, out=""):
    global ok, ng
    if cond:
        ok += 1
        print("  OK  " + name)
    else:
        ng += 1
        print("  ×   " + name + "\n" + out)


def main():
    with tempfile.TemporaryDirectory() as d:
        csv_path = os.path.join(d, "講師.csv")
        exc_path = os.path.join(d, "例外.txt")
        io.open(csv_path, "w", encoding="utf-8").write("講師,ID\n%s,wt91\n%s,wt92\n" % (FAKE2, FAKE1))
        io.open(exc_path, "w", encoding="utf-8").write("# 例外\n大%s通\n" % FAKE2)

        def file_of(text, name="a.txt"):
            p = os.path.join(d, name)
            io.open(p, "w", encoding="utf-8").write(text)
            return p

        cases = [
            ("2 字以上の名字は止める", "これは%s先生の話\n" % FAKE2, 1, "wt91"),
            ("例外の言葉の中の名字は通す", "大%s通の話\n" % FAKE2, 0, None),
            ("例外の言葉と並んだ名字は止める", "大%s通と%s\n" % (FAKE2, FAKE2), 1, "wt91"),
            ("1 字の名字の普通の言葉は通す", "%s説を立てる\n" % FAKE1, 0, None),
            ("1 字の名字＋先生は止める", "%s先生に聞く\n" % FAKE1, 1, "wt92"),
            ("1 字の名字を括弧で囲むと止める", "担当（%s）\n" % FAKE1, 1, "wt92"),
            ("名字の無い文は通す", "wt91 と wt92 で書く\n", 0, None),
        ]
        for name, text, want, wid in cases:
            rc, out = run([file_of(text)], csv_path, exc_path)
            check(name, rc == want and (wid is None or wid in out) and FAKE2 not in out and FAKE1 + "先生" not in out, out)

        rc, out = run([file_of("1 行目\n2 行目 %s\n" % FAKE2)], csv_path, exc_path)
        check("行の番号を出す", rc == 1 and ":2 wt91" in out, out)

        p = os.path.join(d, "b.bin")
        open(p, "wb").write(b"\0\1" + FAKE2.encode("utf-8"))
        rc, out = run([p], csv_path, exc_path)
        check("文字でないファイルは読まない", rc == 0, out)

        rc, out = run(["--message", file_of("直した：%s の件\n# %s\n" % (FAKE2, FAKE1 + "先生"), "msg.txt")], csv_path, exc_path)
        check("commit の説明文の名字は止める", rc == 1 and "commit の説明文" in out and FAKE2 not in out, out)
        rc, out = run(["--message", file_of("直した：wt91 の件\n# %s先生\n" % FAKE1, "msg2.txt")], csv_path, exc_path)
        check("説明文の # の行（git の注）は数えない", rc == 0, out)

        sub = os.path.join(d, "下")
        os.makedirs(sub)
        io.open(os.path.join(sub, "r.txt"), "w", encoding="utf-8").write("%s先生\n" % FAKE2)
        rc, out = run(["r.txt"], csv_path, exc_path, cwd=sub)
        check("相対の道は今いる場所から読む", rc == 1 and "wt91" in out, out)
        rc, out = run([os.path.join(d, "無いファイル.txt")], csv_path, exc_path)
        check("名前を指定したファイルが無ければ × にする（黙って 0 件にしない）", rc == 1 and "読めなかった" in out, out)

        rc, out = run([file_of("%s先生\n" % FAKE2)], os.path.join(d, "無い.csv"), exc_path)
        check("名字の表が無いところでは流さずに通す", rc == 0 and "流していない" in out, out)

        # commit に入る中身（index）で調べる：手元のファイルを直しても、index の中身で判定する
        g = os.path.join(d, "repo")
        os.makedirs(g)
        subprocess.run(["git", "init", "-q", g], check=True)
        io.open(os.path.join(g, "c.txt"), "w", encoding="utf-8").write("%s先生\n" % FAKE2)
        subprocess.run(["git", "-C", g, "add", "c.txt"], check=True)
        io.open(os.path.join(g, "c.txt"), "w", encoding="utf-8").write("wt91\n")
        env = dict(os.environ, TUBE_SURNAMES_CSV=csv_path, TUBE_SURNAMES_EXCEPT=exc_path)
        tool_copy = os.path.join(g, "surnames.py")
        io.open(tool_copy, "w", encoding="utf-8").write(io.open(TOOL, encoding="utf-8").read())
        # 写しの ROOT はその 2 つ上になるので、index を読む場所を合わせるため scripts/check/ に置く
        sc = os.path.join(g, "scripts", "check")
        os.makedirs(sc)
        os.replace(tool_copy, os.path.join(sc, "surnames.py"))
        r = subprocess.run([sys.executable, os.path.join(sc, "surnames.py"), "--staged", "c.txt"],
                           capture_output=True, text=True, env=env)
        check("--staged は commit に入る中身で判定する", r.returncode == 1 and "c.txt:1 wt91" in r.stdout, r.stdout + r.stderr)

    print()
    if ng:
        print("× %d 件 失敗 / OK %d" % (ng, ok))
        return 1
    print("すべて通った。（%d 件）" % ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
