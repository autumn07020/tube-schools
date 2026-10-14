#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""genbank の雛形が「動く・決定的・答えが正しい」ことだけ確かめる。
アプリには import されない独立モジュールなので、検査も独立。"""
import re
from fractions import Fraction
import genbank as G

ok = 0
def check(c, m):
    global ok
    assert c, m; ok += 1

def as_frac(s):
    s = s.strip()
    return Fraction(*map(int, s.split("/"))) if "/" in s else Fraction(int(s))

# 決定的：同じ seed なら同じ問題、違う seed なら違う
a = G.generate("math", "e5", n=8, seed=7, difficulty=4)
check(a == G.generate("math", "e5", n=8, seed=7, difficulty=4), "同じ seed なら同じ出題")
check(a != G.generate("math", "e5", n=8, seed=8, difficulty=4), "違う seed なら違う")

# 算数（小学）：計算は非負で正しい、分数は既約で正しい、比は正
for it in G.generate("math", "e5", n=300, seed=1, difficulty=4):
    if it["unit"] == "計算":
        check(int(it["a"]) >= 0, "小学の計算は非負: %s" % it["q"])
        check(eval(it["q"].rstrip(" =")) == int(it["a"]), "計算が正しい: %s" % it["q"])
    elif it["unit"] == "分数の計算":
        body = it["q"].rstrip(" =")
        op = "+" if "+" in body else "-"
        l, r = body.split(op)
        val = as_frac(l) + as_frac(r) if op == "+" else as_frac(l) - as_frac(r)
        check(val == as_frac(it["a"]), "分数が正しい: %s -> %s" % (it["q"], it["a"]))
    elif it["unit"] == "比と割合":
        check(int(it["a"]) > 0, "比の答えは正: %s" % it["q"])
        m = re.search(r"を (\d+)：(\d+)", it["q"])
        check(m and int(m.group(1)) != int(m.group(2)), "比は相異なる: %s" % it["q"])

# 中学数学：一次方程式の解が実際に方程式を満たす
for it in G.generate("math", "j2", n=300, seed=2, difficulty=4):
    if it["unit"] == "一次方程式":
        x = int(it["a"].split("=")[1])
        m = re.match(r"(-?\d+)x ([+-]) (\d+) = (-?\d+)", it["q"])
        aa, sign, bb, cc = int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(4))
        lhs = aa * x + (bb if sign == "+" else -bb)
        check(lhs == cc, "一次方程式の解が正しい: %s x=%d" % (it["q"], x))

# 教材も生成器も無い教科は self-grade に倒れる
check(all(x.get("mode") == "self-grade" for x in G.generate("science", "j1", n=3, seed=1)),
      "理科は自己採点モードに倒れる")

# 英単語は選択肢が4つ、正解を含む
for it in G.generate("english", "j2", n=20, seed=3, difficulty=3):
    check(it["choices"] and len(it["choices"]) == 4 and it["a"] in it["choices"], "英単語は4択で正解を含む")

print("genbank: すべて通った。（%d件）" % ok)
