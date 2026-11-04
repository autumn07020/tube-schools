#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""理科（直列・並列の回路）で、算数と同じ形が回るかの試作。
  子どもの頭の中の「決まり」（正しい模型と誤概念の模型）を、場面に当てて予測を出す小さな世界として持つ。
  子どもの誤答から誤概念を当て、その誤概念で別の場面を予測させ、実験の事実とぶつける（第 5 版 7 章）。
    python3 docs/変革/試作/tsurukame/rika_sim.py
"""
# 場面：電池 1 個に豆電球を つなぐ。問いは「明るさ」か「電流の大きさ」の比較。
# 模型＝決まりの集まり。場面を入れると答えを返す。
def model_correct(scene):
    if scene == "直列2個の1つ目と2つ目": return "同じ"
    if scene == "直列2個 対 1個": return "暗い"
    if scene == "並列2個 対 1個": return "同じ"
    if scene == "直列の豆電球を1つ外す": return "両方消える"
    if scene == "並列の豆電球を1つ外す": return "残りはつく"
    if scene == "電池の前後の電流": return "同じ"
def model_consumed(scene):      # 誤概念 M1：電流は豆電球で使われて減る
    if scene == "直列2個の1つ目と2つ目": return "2つ目が暗い"
    if scene == "直列2個 対 1個": return "暗い"
    if scene == "並列2個 対 1個": return "同じ"
    if scene == "直列の豆電球を1つ外す": return "両方消える"
    if scene == "並列の豆電球を1つ外す": return "残りはつく"
    if scene == "電池の前後の電流": return "戻る方が少ない"
def model_clash(scene):         # 誤概念 M2：電池の両端から電流が出て豆電球でぶつかる
    if scene == "直列2個の1つ目と2つ目": return "同じ"
    if scene == "直列2個 対 1個": return "同じ"
    if scene == "並列2個 対 1個": return "同じ"
    if scene == "直列の豆電球を1つ外す": return "残りはつく"
    if scene == "並列の豆電球を1つ外す": return "残りはつく"
    if scene == "電池の前後の電流": return "両方から出る"
def model_share(scene):         # 誤概念 M3：電池の電流は決まった量で、豆電球が分け合う（並列でも暗くなる）
    if scene == "直列2個の1つ目と2つ目": return "同じ"
    if scene == "直列2個 対 1個": return "暗い"
    if scene == "並列2個 対 1個": return "暗い"
    if scene == "直列の豆電球を1つ外す": return "両方消える"
    if scene == "並列の豆電球を1つ外す": return "残りはつく"
    if scene == "電池の前後の電流": return "同じ"

MODELS = {"R": ("正しい模型", model_correct), "M1": ("電流は使われて減る", model_consumed),
          "M2": ("両端から出てぶつかる", model_clash), "M3": ("決まった量を分け合う", model_share)}
SCENES = ["直列2個の1つ目と2つ目", "直列2個 対 1個", "並列2個 対 1個", "直列の豆電球を1つ外す", "並列の豆電球を1つ外す", "電池の前後の電流"]

def reverse_lookup(scene, answer):
    return [k for k, (_, f) in MODELS.items() if f(scene) == answer]

def discriminating(cands):
    """候補の模型が全部ちがう答えになる場面（判別の場面）。"""
    out = []
    for sc in SCENES:
        vals = [MODELS[k][1](sc) for k in cands + ["R"]]
        if len(set(vals)) == len(vals):
            out.append(sc)
    return out

def main():
    # 子どもがテストで「直列 2 個の 1 つ目と 2 つ目」に「2 つ目が暗い」と答えた
    hits = reverse_lookup("直列2個の1つ目と2つ目", "2つ目が暗い")
    print("誤答「2つ目が暗い」→ 当てた模型:", [(k, MODELS[k][0]) for k in hits])
    # その模型で別の場面を予測させる → 事実とぶつける
    for sc in SCENES:
        print(f"  M1 なら「{sc}」は → {MODELS['M1'][1](sc)}（事実：{model_correct(sc)}）" + ("  ← ここで崩れる" if MODELS['M1'][1](sc) != model_correct(sc) else ""))
    # 答えだけで一意に当たる割合（全場面 × 全誤概念）
    total = 0; uniq = 0
    for sc in SCENES:
        for k in ("M1", "M2", "M3"):
            a = MODELS[k][1](sc)
            if a == model_correct(sc): continue
            total += 1
            if len(reverse_lookup(sc, a)) == 1: uniq += 1
    print(f"誤答だけで誤概念が一意に当たる割合: {uniq}/{total} = {uniq/total:.2f}")
    print("M1 と M3 を見分ける場面:", discriminating(["M1", "M3"]))
    print("M2 と M3 を見分ける場面:", discriminating(["M2", "M3"]))

if __name__ == "__main__":
    main()
