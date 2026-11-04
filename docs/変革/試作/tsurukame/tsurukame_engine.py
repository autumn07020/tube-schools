#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""つるかめ算の「解き方を走らせる」試作（第 5 版 段 1 の機械の部分。子どもに触れずに出せる数を出す）。

  正しい手順 R と、誤りの型 E1〜E8 を「手順」として持ち、同じ解釈器で走らせる。
  ・逆引き：問題の数と子どもの答えから、その答えになる型を引く
  ・検算：類題 200 問で、正しい手順の答えを数え上げ（総当たり）と突き合わせる
  ・ぶつかり：誤りの型どうし・正しい答えと同じ答えになる割合
  ・判別の数：残っている型の候補が全部ちがう答えになる数（反例）を探す
  ・端の場合：全部が亀／全部が鶴／足が奇数 で各型がどう崩れるか

    python3 docs/変革/試作/tsurukame/tsurukame_engine.py
"""
import json
import random
import os

CRANE, TURTLE = 2, 4
HERE = os.path.dirname(os.path.abspath(__file__))

# 手順＝op の列。各 op は (名前, 式)。式は前の変数を使える小さな算術。解釈器は eval を使わず自前で評価する。
# 変数：n（頭）、L（足）。問われる量 asked は "crane" か "turtle"。
PROCS = {
    "R":  {"name": "正しい手順（全部鶴と仮定）", "steps": [
        ("仮定の足", "a = 2*n"), ("差", "d = L - a"), ("亀", "t = d / (4-2)"), ("鶴", "c = n - t")], "answer": "asked"},
    "E1": {"name": "割る数を 4 にする（片方の足の数で割る）", "steps": [
        ("仮定の足", "a = 2*n"), ("差", "d = L - a"), ("亀", "t = d / 4"), ("鶴", "c = n - t")], "answer": "asked"},
    "E2": {"name": "亀の数を答える（問われた量の取り違え）", "steps": [
        ("仮定の足", "a = 2*n"), ("差", "d = L - a"), ("亀", "t = d / (4-2)"), ("鶴", "c = n - t")], "answer": "turtle"},
    "E3": {"name": "引く向きが逆（仮定の足 − 実際の足）", "steps": [
        ("仮定の足", "a = 2*n"), ("差", "d = a - L"), ("亀", "t = d / (4-2)"), ("鶴", "c = n - t")], "answer": "asked"},
    "E4": {"name": "頭から引くのを忘れる（差÷2 を答える）", "steps": [
        ("仮定の足", "a = 2*n"), ("差", "d = L - a"), ("亀", "t = d / (4-2)")], "answer": "t"},
    "E5": {"name": "差を割らない（差をそのまま亀とする）", "steps": [
        ("仮定の足", "a = 2*n"), ("差", "d = L - a"), ("亀", "t = d"), ("鶴", "c = n - t")], "answer": "asked"},
    "E6": {"name": "全部亀と仮定したのに 4−2 の向きを取り違える（鶴を亀と答える）", "steps": [
        ("仮定の足", "a = 4*n"), ("差", "d = a - L"), ("鶴", "c = d / (4-2)"), ("亀", "t = n - c")], "answer": "swap"},
    "E7": {"name": "頭で割る（差÷頭）", "steps": [
        ("仮定の足", "a = 2*n"), ("差", "d = L - a"), ("亀", "t = d / n"), ("鶴", "c = n - t")], "answer": "asked"},
    "E8": {"name": "足を頭で割って平均の足にして止まる", "steps": [
        ("平均", "m = L / n")], "answer": "m"},
}

def _ev(expr, env):
    """小さな式の評価（+ - * / と括弧、変数、整数）。eval は使わない。"""
    tokens = []
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch.isspace():
            i += 1
        elif ch.isdigit():
            j = i
            while j < len(expr) and expr[j].isdigit():
                j += 1
            tokens.append(("num", int(expr[i:j]))); i = j
        elif ch.isalpha():
            tokens.append(("var", ch)); i += 1
        else:
            tokens.append(("op", ch)); i += 1
    pos = [0]
    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None
    def take():
        t = tokens[pos[0]]; pos[0] += 1; return t
    def atom():
        t = take()
        if t[0] == "num": return t[1]
        if t[0] == "var":
            if t[1] not in env: raise KeyError(t[1])
            return env[t[1]]
        if t == ("op", "("):
            v = add(); take(); return v
        if t == ("op", "-"): return -atom()
        raise ValueError(expr)
    def mul():
        v = atom()
        while peek() in (("op", "*"), ("op", "/")):
            o = take()[1]; w = atom()
            v = v * w if o == "*" else (None if w == 0 else v / w)
            if v is None: return None
        return v
    def add():
        v = mul()
        while peek() in (("op", "+"), ("op", "-")):
            o = take()[1]; w = mul()
            if v is None or w is None: return None
            v = v + w if o == "+" else v - w
        return v
    return add()

def run(proc_id, n, L, asked="crane"):
    """手順を走らせる。戻り：(答え, 行の一覧)。答えは float か None（割れない・定義できない）。"""
    p = PROCS[proc_id]
    env = {"n": n, "L": L}
    lines = []
    for label, step in p["steps"]:
        var, expr = [s.strip() for s in step.split("=", 1)]
        v = _ev(expr, env)
        env[var] = v
        lines.append((label, step, v))
        if v is None:
            return None, lines
    a = p["answer"]
    if a == "asked":
        out = env.get("c") if asked == "crane" else env.get("t")
    elif a == "turtle":
        out = env.get("t")
    elif a == "swap":
        out = env.get("t") if asked == "crane" else env.get("c")
    else:
        out = env.get(a)
    return out, lines

def brute(n, L, asked="crane"):
    """数え上げ。解が 1 つなら整数、無ければ None。"""
    sols = [(c, n - c) for c in range(n + 1) if 2 * c + 4 * (n - c) == L]
    if len(sols) != 1:
        return None
    c, t = sols[0]
    return c if asked == "crane" else t

def valid_problem(n, L):
    return brute(n, L) is not None

def gen_problems(k, seed=20261104, nmin=3, nmax=30):
    rnd = random.Random(seed)
    out = []
    while len(out) < k:
        n = rnd.randint(nmin, nmax)
        t = rnd.randint(1, n - 1)          # 端の場合は別に扱う（全部鶴・全部亀を除く）
        L = 2 * (n - t) + 4 * t
        asked = rnd.choice(["crane", "turtle"])
        out.append((n, L, asked))
    return out

def reverse_lookup(n, L, asked, answer):
    """子どもの答えになる型を引く（R を含む）。"""
    hits = []
    for pid in PROCS:
        v, _ = run(pid, n, L, asked)
        if v is not None and abs(v - answer) < 1e-9:
            hits.append(pid)
    return hits

def discriminating(cands, asked=None, tries=400, seed=1):
    """候補の型が全部ちがう答えになる（しかも正しい答えとも違う）問題を探す。asked が None なら問う量も変えて探す。"""
    rnd = random.Random(seed)
    for _ in range(tries):
        n = rnd.randint(4, 30); t = rnd.randint(1, n - 1); L = 2 * (n - t) + 4 * t
        ask = asked or rnd.choice(["crane", "turtle"])
        vals = {}
        ok = True
        for pid in cands + ["R"]:
            v, _ = run(pid, n, L, ask)
            key = None if v is None else round(v, 6)
            if key in vals.values():
                ok = False; break
            vals[pid] = key
        if ok:
            return (n, L, ask, vals)
    return None

def main():
    probs = gen_problems(200)
    # 1. 検算：R の答え＝数え上げ
    bad = [(n, L, a) for (n, L, a) in probs if run("R", n, L, a)[0] != brute(n, L, a)]
    # 2. 誤りの型の答えの分布と、ぶつかり
    coll_correct = {pid: 0 for pid in PROCS if pid != "R"}   # 誤りの型が正しい答えと一致
    coll_pair = {}                                            # 型どうしが同じ答え
    explain = 0; total_wrong = 0
    for (n, L, a) in probs:
        right = brute(n, L, a)
        vals = {}
        for pid in PROCS:
            v, _ = run(pid, n, L, a)
            vals[pid] = None if v is None else round(v, 6)
        for pid in coll_correct:
            if vals[pid] is not None and vals[pid] == right:
                coll_correct[pid] += 1
        ids = [p for p in PROCS if p != "R"]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                if vals[ids[i]] is not None and vals[ids[i]] == vals[ids[j]]:
                    coll_pair[(ids[i], ids[j])] = coll_pair.get((ids[i], ids[j]), 0) + 1
        # 「子どもが型どおりに間違えた」と仮定して、答えだけから型を一意に引けるか
        for pid in ids:
            v = vals[pid]
            if v is None or v == right:
                continue
            total_wrong += 1
            hits = [q for q in ids if vals[q] == v]
            if len(hits) == 1:
                explain += 1
    # 3. 判別の数
    disc = {}
    for pair in [["E1", "E2"], ["E2", "E4"], ["E1", "E7"], ["E3", "E5"], ["E1", "E2", "E4", "E7"]]:
        disc[",".join(pair)] = discriminating(pair)
    # 4. 端の場合
    edge = {}
    for label, (n, L) in {"全部が亀": (6, 24), "全部が鶴": (6, 12), "足が奇数": (6, 15)}.items():
        edge[label] = {pid: run(pid, n, L, "crane")[0] for pid in PROCS}
    rep = {
        "問題": len(probs), "検算で食い違い": len(bad),
        "誤りの型が正しい答えと一致（200 問中）": coll_correct,
        "型どうしが同じ答え（200 問中、上位）": sorted(coll_pair.items(), key=lambda kv: -kv[1])[:8],
        "答えだけで型が一意に引ける割合": round(explain / total_wrong, 3) if total_wrong else None,
        "判別の数の例": disc, "端の場合": edge,
    }
    print(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
    # つるかめ算の例（第 4 版 4.5）：頭 10・足 28・答え 4 → 逆引き
    print("逆引き 頭10 足28 鶴を問う 答え4 →", reverse_lookup(10, 28, "crane", 4))
    print("逆引き 頭10 足28 鶴を問う 答え6 →", reverse_lookup(10, 28, "crane", 6))
    print("逆引き 頭10 足28 鶴を問う 答え8 →", reverse_lookup(10, 28, "crane", 8))
    v, lines = run("E2", 12, 32, "crane")
    print("E2 を 頭12 足32 で走らせる →", v, lines)

if __name__ == "__main__":
    main()
