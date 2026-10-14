#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""毎日テストの自動出題（教材データが無くても成立させるための雛形）。

    ★ このモジュールは、いまのアプリ・デモには一切つながっていない。★
    どこからも import されず、サーバの経路にも入っていない。part 3 の
    「教材データを置けない場合でも、上位難関校を目指す生徒に紛い物でない
     出題ができる」ことを、動く形で示すための独立した雛形である。

なぜ要るか
----------
現状の毎日テストは自社作成の content/*.js（正誤問題データ）に依存する。
早稲田アカデミーとの契約上、この教材データを置けない可能性がある。
その場合でも、宿題チェック・添削・提出管理・理解度は教材の中身を必要と
しないのでそのまま動く。**毎日テストだけ**が出題データを要る。

そこで出題を2つの道でまかなう。

  (A) ページ指示＋自己採点
      講師が「演習問題集 p.34-36」と指示し、生徒は紙で解いて
      正誤だけをアプリに記録する。SRS はこの正誤で回る。
      → 出題データは要らない。genbank は関与しない。

  (B) パブリックドメイン／自動生成
      計算・数の性質・比・速さ（算数/数学）、教育漢字（PD の学年別配当）、
      頻度リストの英単語 …… を **プログラムで生成**する。
      市販教材の文面を複製しないので権利の問題が無く、難易度を
      パラメータで上げられるので難関校対策にも耐える。

設計の約束
----------
* 決定的（seed を固定すれば同じ問題が出る）。SRS の「同じ種なら同じ並び」と揃える。
* 生成器は答えも一緒に返す（自動採点できる）。
* 乱数以外の外部依存を持たない（標準ライブラリだけ）。ネットワークも読まない。
* 返す形は 1問 = {"q": 問題文, "a": 答え, "choices": [...]|None, "unit": 単元, "level": 難度}

出題の入口
----------
    generate(subject, grade, unit, n=10, seed=0, difficulty=3) -> [item, ...]

difficulty は 1〜5。3 が学年相当、4〜5 が難関校の上乗せ。
"""
import random

# ------------------------------------------------------------------
# 算数・数学 ―― 生成器の集まり。単元ごとに1つ。
# どれも「答えが整数・約分済みなど、きれいに出る」ように制約をかけて作る
# （自動生成にありがちな「答えが 7.3333… の問題」を避ける）。
# ------------------------------------------------------------------

def _g_arith(rng, diff):
    """四則。桁と項数を難度で上げる。"""
    n = 2 + diff // 2
    hi = 10 ** (1 + diff)
    nums = [rng.randint(2, hi) for _ in range(n)]
    expr = str(nums[0]); val = nums[0]
    for x in nums[1:]:
        op = rng.choice("+-")
        if op == "-" and val - x < 0:      # 途中でマイナスにしない（小学算数の範囲）
            op = "+"
        expr += " %s %d" % (op, x)
        val = val + x if op == "+" else val - x
    return {"q": expr + " =", "a": str(val), "choices": None, "unit": "計算", "level": diff}

def _g_fraction(rng, diff):
    """分数の加減。約分した既約分数で答える。"""
    from math import gcd
    d1 = rng.randint(2, 3 + diff); d2 = rng.randint(2, 3 + diff)
    n1 = rng.randint(1, d1 - 1); n2 = rng.randint(1, d2 - 1)
    op = rng.choice("+-")
    num = n1 * d2 + n2 * d1 if op == "+" else n1 * d2 - n2 * d1
    den = d1 * d2
    g = gcd(abs(num) or 1, den)
    a = "%d/%d" % (num // g, den // g) if den // g != 1 else str(num // g)
    return {"q": "%d/%d %s %d/%d =" % (n1, d1, op, n2, d2), "a": a,
            "choices": None, "unit": "分数の計算", "level": diff}

def _g_ratio(rng, diff):
    """比と割合（中学受験の定番）。相異なる比で、割り切れる全体量にして整数解にする。"""
    a_ratio = rng.randint(2, 5)
    b_ratio = rng.choice([x for x in range(2, 7) if x != a_ratio])
    unit_v = rng.randint(4, 8 + diff * 3)
    total = (a_ratio + b_ratio) * unit_v
    ans = a_ratio * unit_v
    return {"q": "%d を %d：%d の比で分けます。%d の側はいくつですか。" % (total, a_ratio, b_ratio, a_ratio),
            "a": str(ans), "choices": None, "unit": "比と割合", "level": diff}

def _g_speed(rng, diff):
    """速さ（きれいな整数になる距離・時間で作る）。"""
    speed = rng.choice([40, 50, 60, 72, 80, 90]) + diff * 4
    hours = rng.randint(2, 3 + diff)
    dist = speed * hours
    which = rng.choice(["dist", "time", "speed"])
    if which == "dist":
        return {"q": "時速 %dkm で %d時間 進むと何 km ですか。" % (speed, hours),
                "a": str(dist), "choices": None, "unit": "速さ", "level": diff}
    if which == "time":
        return {"q": "%dkm を 時速 %dkm で進むと何時間かかりますか。" % (dist, speed),
                "a": str(hours), "choices": None, "unit": "速さ", "level": diff}
    return {"q": "%dkm を %d時間 で進むときの時速は何 km ですか。" % (dist, hours),
            "a": str(speed), "choices": None, "unit": "速さ", "level": diff}

def _g_numtheory(rng, diff):
    """数の性質（最大公約数・最小公倍数）。難関校の頻出。"""
    from math import gcd
    a = rng.randint(6, 20 + diff * 8); b = rng.randint(6, 20 + diff * 8)
    if rng.random() < 0.5:
        return {"q": "%d と %d の最大公約数は？" % (a, b), "a": str(gcd(a, b)),
                "choices": None, "unit": "数の性質", "level": diff}
    lcm = a * b // gcd(a, b)
    return {"q": "%d と %d の最小公倍数は？" % (a, b), "a": str(lcm),
            "choices": None, "unit": "数の性質", "level": diff}

def _g_linear(rng, diff):
    """一次方程式（中学）。整数解になる係数で作る。"""
    x = rng.randint(-9 - diff, 9 + diff)
    a = rng.randint(2, 4 + diff); b = rng.randint(-9, 9)
    c = a * x + b
    return {"q": "%dx %s %d = %d を解きなさい。" % (a, "+" if b >= 0 else "-", abs(b), c),
            "a": "x=%d" % x, "choices": None, "unit": "一次方程式", "level": diff}

# 学年帯 → 使える生成器。小学＝算数、中学＝数学。
_MATH_ELEM = [_g_arith, _g_fraction, _g_ratio, _g_speed, _g_numtheory]
_MATH_JHS = [_g_arith, _g_fraction, _g_numtheory, _g_linear]

# ------------------------------------------------------------------
# 漢字・英単語 ―― PD（学年別配当漢字／頻度語）を差し込む口だけ用意する。
# 実データ（教育漢字1026字・英頻度リスト）は権利フリーなので、
# 契約が固まった段階で data/pd/ に置いて読み込む。ここでは形を示す小さな見本。
# ------------------------------------------------------------------
_KANJI_SAMPLE = [("花", "はな"), ("空", "そら"), ("池", "いけ"), ("計算", "けいさん")]
_VOCAB_SAMPLE = [("increase", "増える"), ("decide", "決める"), ("although", "〜だけれども"),
                 ("require", "必要とする"), ("reduce", "減らす"), ("although2", "しかしながら"),
                 ("gather", "集める"), ("avoid", "避ける")]

def _g_kanji(rng, diff, bank):
    w, yomi = rng.choice(bank)
    return {"q": "「%s」の読みをひらがなで。" % w, "a": yomi, "choices": None,
            "unit": "漢字の読み", "level": diff}

def _g_vocab(rng, diff, bank):
    en, ja = rng.choice(bank)
    # 難度が高いほど、選択肢を近い意味で紛らわしくする（雛形では単純化）
    wrong = [x[1] for x in bank if x[1] != ja]
    rng.shuffle(wrong)
    choices = [ja] + wrong[:3]
    while len(choices) < 4:                 # 見本の語彙が少ないときの保険
        choices.append("―")
    rng.shuffle(choices)
    return {"q": "%s の意味は？" % en, "a": ja, "choices": choices,
            "unit": "英単語", "level": diff}

# ------------------------------------------------------------------
# 入口
# ------------------------------------------------------------------
def generate(subject, grade, unit=None, n=10, seed=0, difficulty=3):
    """出題を n 問つくる。seed を固定すれば毎回同じ（採点・復習と揃う）。"""
    rng = random.Random("%s|%s|%s|%d|%d" % (subject, grade, unit or "", seed, difficulty))
    diff = max(1, min(5, int(difficulty)))
    is_jhs = str(grade).startswith(("j", "中"))
    out = []
    for _ in range(max(1, int(n))):
        if subject in ("math", "算数", "数学"):
            gen = rng.choice(_MATH_JHS if is_jhs else _MATH_ELEM)
            out.append(gen(rng, diff))
        elif subject in ("japanese", "国語"):
            out.append(_g_kanji(rng, diff, _KANJI_SAMPLE))
        elif subject in ("english", "英語"):
            out.append(_g_vocab(rng, diff, _VOCAB_SAMPLE))
        else:
            # 教材も生成器も無い教科は「ページ指示＋自己採点」に倒す合図を返す
            out.append({"q": None, "a": None, "choices": None,
                        "unit": unit or subject, "level": diff, "mode": "self-grade"})
    return out


if __name__ == "__main__":
    import json, sys
    subj = sys.argv[1] if len(sys.argv) > 1 else "math"
    grade = sys.argv[2] if len(sys.argv) > 2 else "e5"
    diff = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    for it in generate(subj, grade, n=6, seed=1, difficulty=diff):
        print(json.dumps(it, ensure_ascii=False))
