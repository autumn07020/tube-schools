#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""割合（2 単元目）。表（手順の列）だけを足して、つるかめ算と同じ解釈器・逆引き・検算・判別の数が回るかを確かめる。
問題：もとにする量 B・比べる量 C・割合 r（%）のうち 2 つが与えられ、残りを問う（asked = C / r / B）。
    python3 docs/変革/試作/tsurukame/wariai_engine.py
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tsurukame_engine import _ev  # 同じ式の評価器

# 問う量ごとに、正しい手順 R と誤りの型。変数：B（もと）・C（比べる）・r（%）
PROCS = {
    "C": {
        "R":  {"name": "比べる量＝もと×割合（小数に直す）", "steps": [("小数に", "p = r / 100"), ("比べる量", "C = B * p")], "answer": "C"},
        "E1": {"name": "% を小数に直さず掛ける", "steps": [("比べる量", "C = B * r")], "answer": "C"},
        "E2": {"name": "もとを割合で割る", "steps": [("小数に", "p = r / 100"), ("比べる量", "C = B / p")], "answer": "C"},
        "E3": {"name": "もとに割合を足す（増減と取り違え）", "steps": [("比べる量", "C = B + r")], "answer": "C"},
        "E4": {"name": "100 から引いた割合を掛ける（残りを答える）", "steps": [("小数に", "p = (100 - r) / 100"), ("比べる量", "C = B * p")], "answer": "C"},
    },
    "r": {
        "R":  {"name": "割合＝比べる量÷もと×100", "steps": [("割合", "p = C / B"), ("%", "r = p * 100")], "answer": "r"},
        "E1": {"name": "もとと比べる量を逆にする", "steps": [("割合", "p = B / C"), ("%", "r = p * 100")], "answer": "r"},
        "E2": {"name": "100 を掛け忘れる（小数のまま）", "steps": [("割合", "p = C / B")], "answer": "p"},
        "E3": {"name": "差を答える", "steps": [("差", "d = B - C")], "answer": "d"},
        "E4": {"name": "掛けてしまう", "steps": [("積", "p = C * B")], "answer": "p"},
    },
    "B": {
        "R":  {"name": "もと＝比べる量÷割合", "steps": [("小数に", "p = r / 100"), ("もと", "B = C / p")], "answer": "B"},
        "E1": {"name": "比べる量に割合を掛ける", "steps": [("小数に", "p = r / 100"), ("もと", "B = C * p")], "answer": "B"},
        "E2": {"name": "% を小数に直さず割る", "steps": [("もと", "B = C / r")], "answer": "B"},
        "E3": {"name": "比べる量をそのまま答える（もとと比べるの取り違え）", "steps": [("もと", "B = C")], "answer": "B"},
        "E4": {"name": "比べる量を 100−r で割る", "steps": [("小数に", "p = (100 - r) / 100"), ("もと", "B = C / p")], "answer": "B"},
    },
}

def run(asked, pid, B=None, C=None, r=None):
    p = PROCS[asked][pid]
    env = {k: v for k, v in (("B", B), ("C", C), ("r", r)) if v is not None}
    lines = []
    for label, step in p["steps"]:
        var, expr = [x.strip() for x in step.split("=", 1)]
        try:
            v = _ev(expr, env)
        except KeyError:
            v = None
        env[var] = v
        lines.append((label, step, v))
        if v is None:
            return None, lines
    return env.get(p["answer"]), lines

def truth(asked, B=None, C=None, r=None):
    if asked == "C": return B * r / 100
    if asked == "r": return C / B * 100
    return C / (r / 100)

def gen(k, seed=20261104):
    rnd = random.Random(seed); out = []
    rs = [5, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 75, 80, 120, 150]
    while len(out) < k:
        r = rnd.choice(rs); B = rnd.choice([20, 40, 50, 60, 80, 120, 150, 200, 250, 300, 400, 500, 600, 800, 1200])
        C = B * r / 100
        if C != int(C): continue
        asked = rnd.choice(["C", "r", "B"])
        given = {"C": {"B": B, "r": r}, "r": {"B": B, "C": int(C)}, "B": {"C": int(C), "r": r}}[asked]
        out.append((asked, given))
    return out

def main():
    probs = gen(200)
    bad = 0; explain = 0; wrong = 0; coll_correct = {}; coll_pair = {}
    for asked, given in probs:
        right = truth(asked, **given)
        rv, _ = run(asked, "R", **given)
        if rv is None or abs(rv - right) > 1e-9: bad += 1
        vals = {}
        for pid in PROCS[asked]:
            v, _ = run(asked, pid, **given)
            vals[pid] = None if v is None else round(v, 6)
        ids = [p for p in PROCS[asked] if p != "R"]
        for pid in ids:
            if vals[pid] is not None and abs(vals[pid] - right) < 1e-9:
                coll_correct[(asked, pid)] = coll_correct.get((asked, pid), 0) + 1
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                if vals[ids[i]] is not None and vals[ids[i]] == vals[ids[j]]:
                    coll_pair[(asked, ids[i], ids[j])] = coll_pair.get((asked, ids[i], ids[j]), 0) + 1
        for pid in ids:
            v = vals[pid]
            if v is None or abs(v - right) < 1e-9: continue
            wrong += 1
            if len([q for q in ids if vals[q] == v]) == 1: explain += 1
    rep = {"問題": len(probs), "検算で食い違い": bad,
           "答えだけで型が一意に引ける割合": round(explain / wrong, 3),
           "誤りの型が正しい答えと一致": {f"{a}:{p}": n for (a, p), n in coll_correct.items()},
           "型どうしが同じ答え": {f"{a}:{p}/{q}": n for (a, p, q), n in sorted(coll_pair.items(), key=lambda kv: -kv[1])[:6]}}
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    # 逆引きの例：200 円の 15% は？ 子どもの答え 3000 → E1（% を小数に直さない）
    for ans in (30, 3000, 215, 170):
        hits = [pid for pid in PROCS["C"] if (lambda v: v is not None and abs(v - ans) < 1e-9)(run("C", pid, B=200, r=15)[0])]
        print("もと200・15%・比べる量を問う 答え", ans, "→", hits)
    print("E1 を もと 50・8% で走らせる →", run("C", "E1", B=50, r=8))

if __name__ == "__main__":
    main()
