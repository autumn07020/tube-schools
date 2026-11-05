#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""暦に合わせた単元（小 5 算数 12-14「濃さと比」・01-11「いろいろな速さ」）の表。
批評 第 5 回：試す週に習う単元の表で始める。つるかめ算の機械（同じ式の評価器）に表を足すだけで回るかを確かめる。
    python3 docs/変革/試作/tsurukame/koyomi_engine.py
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tsurukame_engine import _ev

# ---- 濃さ（食塩水）。変数：s 食塩, w 水, t 食塩水(= s + w), p 濃度(%)。問う量：p / s / t
NOSA = {
    "p": {  # 食塩 s と水 w から濃度
        "R":  {"name": "濃度＝食塩÷食塩水×100", "steps": [("食塩水", "t = s + w"), ("割合", "q = s / t"), ("%", "p = q * 100")], "answer": "p"},
        "E1": {"name": "水で割る（食塩水でなく）", "steps": [("割合", "q = s / w"), ("%", "p = q * 100")], "answer": "p"},
        "E2": {"name": "×100 を忘れる", "steps": [("食塩水", "t = s + w"), ("割合", "q = s / t")], "answer": "q"},
        "E3": {"name": "食塩水÷食塩にする（逆）", "steps": [("食塩水", "t = s + w"), ("逆", "q = t / s")], "answer": "q"},
        "E4": {"name": "食塩÷水の差を答える", "steps": [("差", "d = w - s")], "answer": "d"},
    },
    "s": {  # 食塩水 t と濃度 p から食塩
        "R":  {"name": "食塩＝食塩水×濃度÷100", "steps": [("小数に", "q = p / 100"), ("食塩", "s = t * q")], "answer": "s"},
        "E1": {"name": "% を小数に直さず掛ける", "steps": [("食塩", "s = t * p")], "answer": "s"},
        "E2": {"name": "食塩水を濃度で割る", "steps": [("小数に", "q = p / 100"), ("食塩", "s = t / q")], "answer": "s"},
        "E3": {"name": "水の量を答える（食塩水−食塩）", "steps": [("小数に", "q = p / 100"), ("食塩", "s = t * q"), ("水", "w = t - s")], "answer": "w"},
    },
    "t": {  # 食塩 s と濃度 p から食塩水
        "R":  {"name": "食塩水＝食塩÷濃度", "steps": [("小数に", "q = p / 100"), ("食塩水", "t = s / q")], "answer": "t"},
        "E1": {"name": "食塩に濃度を掛ける", "steps": [("小数に", "q = p / 100"), ("食塩水", "t = s * q")], "answer": "t"},
        "E2": {"name": "水の量を答える（食塩水−食塩）", "steps": [("小数に", "q = p / 100"), ("食塩水", "t = s / q"), ("水", "w = t - s")], "answer": "w"},
        "E3": {"name": "% を小数に直さず割る", "steps": [("食塩水", "t = s / p")], "answer": "t"},
    },
}
def nosa_truth(asked, **g):
    if asked == "p": return g["s"] / (g["s"] + g["w"]) * 100
    if asked == "s": return g["t"] * g["p"] / 100
    return g["s"] / (g["p"] / 100)
def nosa_gen(k, seed=5):
    rnd = random.Random(seed); out = []
    while len(out) < k:
        p = rnd.choice([4, 5, 8, 10, 12, 15, 20, 25]); t = rnd.choice([100, 150, 200, 250, 300, 400, 500, 600, 800])
        s = t * p / 100
        if s != int(s): continue
        s = int(s); w = t - s
        asked = rnd.choice(["p", "s", "t"])
        given = {"p": {"s": s, "w": w}, "s": {"t": t, "p": p}, "t": {"s": s, "p": p}}[asked]
        out.append((asked, given))
    return out

# ---- 速さ。変数：d 距離(km), h 時間(時間), m 時間(分), v 時速(km/時), u 分速(km/分)。問う量：v / d / h
HAYASA = {
    "v": {  # 距離 d と 分 m から時速
        "R":  {"name": "時速＝距離÷（分÷60）", "steps": [("時間に", "h = m / 60"), ("時速", "v = d / h")], "answer": "v"},
        "E1": {"name": "分のまま割る（単位を直さない）", "steps": [("分速のつもり", "v = d / m")], "answer": "v"},
        "E2": {"name": "60 を掛けて時間にする（逆の換算）", "steps": [("時間に", "h = m * 60"), ("時速", "v = d / h")], "answer": "v"},
        "E3": {"name": "時間÷距離（逆）", "steps": [("時間に", "h = m / 60"), ("逆", "v = h / d")], "answer": "v"},
    },
    "d": {  # 時速 v と 分 m から距離
        "R":  {"name": "距離＝時速×（分÷60）", "steps": [("時間に", "h = m / 60"), ("距離", "d = v * h")], "answer": "d"},
        "E1": {"name": "分のまま掛ける", "steps": [("距離", "d = v * m")], "answer": "d"},
        "E2": {"name": "割ってしまう", "steps": [("時間に", "h = m / 60"), ("距離", "d = v / h")], "answer": "d"},
        "E3": {"name": "60 を掛けて時間にする（逆の換算）", "steps": [("時間に", "h = m * 60"), ("距離", "d = v * h")], "answer": "d"},
    },
    "h": {  # 距離 d と 時速 v から 分
        "R":  {"name": "分＝距離÷時速×60", "steps": [("時間", "h = d / v"), ("分に", "m = h * 60")], "answer": "m"},
        "E1": {"name": "60 を掛け忘れる（時間のまま）", "steps": [("時間", "h = d / v")], "answer": "h"},
        "E2": {"name": "時速÷距離（逆）", "steps": [("逆", "h = v / d"), ("分に", "m = h * 60")], "answer": "m"},
        "E3": {"name": "掛けてしまう", "steps": [("積", "h = d * v"), ("分に", "m = h * 60")], "answer": "m"},
    },
}
def hayasa_truth(asked, **g):
    if asked == "v": return g["d"] / (g["m"] / 60)
    if asked == "d": return g["v"] * g["m"] / 60
    return g["d"] / g["v"] * 60
def hayasa_gen(k, seed=6):
    rnd = random.Random(seed); out = []
    while len(out) < k:
        v = rnd.choice([3, 4, 5, 6, 12, 15, 18, 20, 24, 30, 36, 40, 45, 60, 72, 90]); m = rnd.choice([5, 10, 12, 15, 20, 24, 30, 36, 40, 45, 48, 50, 90, 120])
        d = v * m / 60
        if d != int(d): continue
        d = int(d); asked = rnd.choice(["v", "d", "h"])
        given = {"v": {"d": d, "m": m}, "d": {"v": v, "m": m}, "h": {"d": d, "v": v}}[asked]
        out.append((asked, given))
    return out

def run(table, asked, pid, **g):
    p = table[asked][pid]; env = dict(g); lines = []
    for label, step in p["steps"]:
        var, expr = [x.strip() for x in step.split("=", 1)]
        try: v = _ev(expr, env)
        except KeyError: v = None
        env[var] = v; lines.append((label, step, v))
        if v is None: return None, lines
    return env.get(p["answer"]), lines

def analyze(name, table, truth, probs):
    bad = 0; explain = 0; wrong = 0; coll = {}
    for asked, g in probs:
        right = truth(asked, **g)
        rv, _ = run(table, asked, "R", **g)
        if rv is None or abs(rv - right) > 1e-9: bad += 1
        ids = [q for q in table[asked] if q != "R"]
        vals = {q: (lambda v: None if v is None else round(v, 6))(run(table, asked, q, **g)[0]) for q in table[asked]}
        for q in ids:
            v = vals[q]
            if v is None or abs(v - right) < 1e-9:
                if v is not None: coll[(asked, q)] = coll.get((asked, q), 0) + 1
                continue
            wrong += 1
            if len([x for x in ids if vals[x] == v]) == 1: explain += 1
    print(f"{name}：問題 {len(probs)}・検算の食い違い {bad}・答えだけで型が一意 {explain/wrong:.3f}・正しい答えと一致する誤り {dict((f'{a}:{q}', n) for (a, q), n in coll.items())}")

def main():
    analyze("濃さと比（12-14）", NOSA, nosa_truth, nosa_gen(200))
    analyze("いろいろな速さ（01-11）", HAYASA, hayasa_truth, hayasa_gen(200))
    # 逆引きの例：食塩 20 g・水 180 g の濃度を 11.1 と答えた → E1（水で割った）
    for ans in (10, 11.111111, 0.1, 160):
        hits = [q for q in NOSA["p"] if (lambda v: v is not None and abs(v - ans) < 1e-3)(run(NOSA, "p", q, s=20, w=180)[0])]
        print("食塩 20・水 180・濃度を問う 答え", ans, "→", hits)
    print("時速 36 km で 20 分 の距離を 720 と答えた →", [q for q in HAYASA["d"] if (lambda v: v is not None and abs(v - 720) < 1e-6)(run(HAYASA, "d", q, v=36, m=20)[0])])

if __name__ == "__main__":
    main()
