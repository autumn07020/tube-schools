#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""戻りの日の予定と「消える条件」の試作（第 5 版 3 章・4 章）。
  × は、入れた日の 2 日後と 7 日後に戻る（戻りの日）。判別の数の問題を、選択肢なしで、2 回続けて正解したら消える。
  外したら、その × は 2 日後にまた戻る（間隔は 2 → 7 → 14 日）。1 回に戻る問題は 2〜4 問、新しい × は 3 件まで。
  ここでは、ある子の 3 週間を模擬して、1 回の問題数と、消えるまでの日数の分布を出す（正答率を仮に 7 割として）。
    python3 docs/変革/試作/tsurukame/schedule_sim.py
"""
import random

GAPS = [2, 7, 14]          # 戻る間隔（日）
NEED = 2                   # 続けて正解の回数
PER_SESSION_MAX = 4        # 1 回に戻る問題の上限
NEW_MAX = 3                # 1 回に新しく入れる × の上限

def simulate(days=21, sessions_per_week=3, p_correct=0.7, new_per_week=4, seed=7):
    rnd = random.Random(seed)
    xs = []            # dict(id, due, streak, gap_i, cleared_day)
    session_days = sorted({d for d in range(days) if d % 7 in (0, 2, 4)})[:days * sessions_per_week // 7 + 1]
    inbox = 0; nid = 0; per_session = []; cleared = []
    for d in range(days):
        if d % 7 == 0:
            inbox += new_per_week          # 1 週間に塾で付く × の数（仮）
        if d not in session_days:
            continue
        # 新しく入れる（3 件まで）
        k = min(NEW_MAX, inbox); inbox -= k
        for _ in range(k):
            nid += 1
            xs.append({"id": nid, "due": d + GAPS[0], "streak": 0, "gap_i": 0, "cleared": None, "born": d})
        # 戻りの問題（期限の来た × を古い順に、上限まで）
        due = [x for x in xs if x["cleared"] is None and x["due"] <= d]
        due.sort(key=lambda x: x["due"])
        todo = due[:PER_SESSION_MAX]
        for x in todo:
            if rnd.random() < p_correct:
                x["streak"] += 1
                if x["streak"] >= NEED:
                    x["cleared"] = d; cleared.append(d - x["born"]); continue
                x["gap_i"] = min(x["gap_i"] + 1, len(GAPS) - 1)
            else:
                x["streak"] = 0; x["gap_i"] = 0
            x["due"] = d + GAPS[x["gap_i"]]
        per_session.append((d, k, len(todo), len(due) - len(todo)))
    remain = [x for x in xs if x["cleared"] is None]
    return per_session, cleared, len(xs), len(remain)

def main():
    for p in (0.5, 0.7, 0.9):
        ps, cleared, total, remain = simulate(p_correct=p)
        avg_q = sum(a + b for _, a, b, _ in ps) / len(ps)
        backlog = max(c for _, _, _, c in ps)
        med = sorted(cleared)[len(cleared) // 2] if cleared else None
        print(f"正答率 {p:.1f}：3 週間で × {total} 件、消えた {len(cleared)} 件（中央値 {med} 日で消える）、残り {remain}、1 回の問題数の平均 {avg_q:.1f}、積み残しの最大 {backlog}")
    ps, _, _, _ = simulate()
    print("1 回ごと（日, 新しい ×, 戻りの問題, 積み残し）:", ps)

if __name__ == "__main__":
    main()
