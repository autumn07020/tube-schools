#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""段 2「自分の解き方を部品で組んで走らせる」の試作。
  部品の箱（正しい部品と、誤りの型から作った部品が混ざった有限の札）から、子どもが並べた手順を
  (1) その子自身の問題で走らせ、子どもの答えを再現できるか（本当にその子の手順か）を確かめ、
  (2) 再現できたら、別の数と端の場合で走らせて、崩れる数（反例）を探して見せる。
  正しい手順はどこにも出ない（子どもが組み上げるまで）。
    python3 docs/変革/試作/tsurukame/compose_sim.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tsurukame_engine import _ev, brute

# 部品の箱（つるかめ算）。札＝(見出し, 式)。正しい部品も誤りの部品も混ざる。
TILES = {
    "a2": ("全部鶴の足", "a = 2*n"), "a4": ("全部亀の足", "a = 4*n"),
    "d1": ("実際−仮定", "d = L - a"), "d2": ("仮定−実際", "d = a - L"),
    "t2": ("差÷2", "t = d / 2"), "t4": ("差÷4", "t = d / 4"), "tn": ("差÷頭", "t = d / n"), "td": ("差そのまま", "t = d"),
    "c": ("頭−亀", "c = n - t"), "ans_t": ("答え＝亀", "ans = t"), "ans_c": ("答え＝鶴", "ans = c"), "ans_d": ("答え＝差", "ans = d"),
}

def run_tiles(seq, n, L):
    env = {"n": n, "L": L}; lines = []
    for tid in seq:
        label, step = TILES[tid]
        var, expr = [x.strip() for x in step.split("=", 1)]
        try:
            v = _ev(expr, env)
        except KeyError:
            return None, lines + [(label, step, "（まだ出ていない数を使った）")]
        env[var] = v; lines.append((label, step, v))
        if v is None:
            return None, lines
    return env.get("ans"), lines

def reproduces(seq, own):
    """own = [(n, L, asked, 子どもの答え)]。子どもの答えを全部再現できるか。"""
    for n, L, asked, ans in own:
        v, _ = run_tiles(seq, n, L)
        if v is None or abs(v - ans) > 1e-9:
            return False
    return True

def counterexample(seq, asked="crane", tries=300, seed=3):
    """崩れる数を探す：答えが整数でない・負・頭を超える・正解と違う、のどれか。端の場合を先に試す。"""
    cands = [(6, 24), (6, 12), (5, 20), (7, 14)]  # 全部亀・全部鶴
    rnd = random.Random(seed)
    for _ in range(tries):
        n = rnd.randint(3, 30); t = rnd.randint(1, n - 1); cands.append((n, 2 * (n - t) + 4 * t))
    for n, L in cands:
        v, lines = run_tiles(seq, n, L)
        right = brute(n, L, asked)
        why = None
        if v is None: why = "途中で止まる"
        elif v != int(v): why = "整数にならない"
        elif v < 0: why = "負になる"
        elif v > n: why = "頭の数を超える"
        elif right is not None and abs(v - right) > 1e-9: why = "数え上げと合わない"
        if why:
            return (n, L, v, right, why, lines)
    return None

def main():
    # 子どもが紙で解いた 2 問（頭 10・足 28 → 4 と答えた／頭 8・足 20 → 2 と答えた）：E2 の間違い方（亀を答える）
    own = [(10, 28, "crane", 4), (8, 20, "crane", 2)]
    # 逆引きで当てた型 E2 の並びを最初に置く → 子どもが「はい」
    seq = ["a2", "d1", "t2", "c", "ans_t"]
    print("並べた手順:", [TILES[t][0] for t in seq])
    print("自分の答えを再現できるか:", reproduces(seq, own))
    ce = counterexample(seq)
    if ce:
        n, L, v, right, why, lines = ce
        print(f"崩れる数: 頭 {n}・足 {L} → この手順だと {v}（{why}。数え上げの鶴は {right}）")
        for label, step, val in lines:
            print("   ", label, step, "=", val)
    # 子どもが最後の札を「答え＝鶴」に入れ替える
    seq2 = ["a2", "d1", "t2", "c", "ans_c"]
    print("入れ替え後 再現:", reproduces(seq2, own), "（自分の前の答えは再現できなくなる＝前の答えが間違いだったと自分で分かる）")
    print("入れ替え後 反例:", counterexample(seq2))
    # 当てずっぽうの並び（部品 5 枚）が端の場合をすべて通る確率
    ids = list(TILES); rnd = random.Random(1); ok = 0; N = 2000
    for _ in range(N):
        s = [rnd.choice(ids) for _ in range(5)]
        if counterexample(s) is None and reproduces(s, own) is False and run_tiles(s, 10, 28)[0] == brute(10, 28):
            ok += 1
    print(f"当てずっぽうの 5 枚が反例なしで通る確率（2000 回）: {ok / N:.4f}")

if __name__ == "__main__":
    main()
