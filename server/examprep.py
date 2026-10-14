#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""総復習テスト対策 ―― 組み分けテストに向けた、毎日の総ざらい。

何のためか
----------
組み分けテストは5週ごとにあり、α/β・T/R の入れ替えがここで決まる。
生徒にとって学期でいちばん大きな山なので、**本番の8日前から**
ふだんの毎日テストの上に「総復習テスト対策」を出す。

    ・範囲は「前回のテストの翌日から、いまの回まで」に習ったところ全部
    ・量はふだんの毎日テストの3倍ほど。ただし **1教科1時間を超えない**
    ・難易度は2つ。上位編 と 基本編
        直近1か月の宿題の出来が6割以上 … 上位編
        それ未満                       … 基本編
    ・まちがえた問題は翌日以降の対策に**必ず**戻ってくる

設計の要点
----------
**この仕組みはデモ用の作りものではない。** 実際の教材と実際の記録が
入っても、同じ道を通る。そのために次の3つを守っている。

1. 日付を決め打ちしない。組み分けテストの日は exams.json から読む。
   入っていなければ対策は出ない（無い日程に向けて走らせない）。

2. 範囲は **授業計画の単元名** で決める。教材の中の単元名と一致すれば
   そこだけを引く。一致しなければ、その学年の教材ぜんぶから引く ――
   狭められないだけで、動きは止まらない。

3. 難易度は **教材の難易度**（基本編／応用編）で分ける。教材に難易度が
   付いていなければ、記録から測った「まちがえられやすさ」で分ける。
   どちらも無ければ全部から出す。嘘の難易度を作らない。

問題の中身は app/content/*/*.js が持っている。ここではそれを読んで、
1問ずつの形（問題文・答え・解説）まで組み立てる。PDFにもこれを使う。
"""

import io
import os
import random
import re
import unicodedata
import time

import paths
import exams as E
import lessons as L

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(os.path.dirname(HERE), "app", "content")

# 教科コード。app/content/manifest.js と同じ。
CODE = {"english": "en", "science": "sci", "social": "soc",
        "math": "mat", "japanese": "jpn"}

# 1問にかかる時間の目安（秒）。実測ではなく設計値。
#   選択問題は読んで選ぶまで、用語は思い出すまで。
# **ここを大きくしすぎると量が減り、小さすぎると終わらない。**
SEC_PER = {"quiz": 45, "term": 30}
DEFAULT_SEC = 40

# 1問にかかる時間は **教科で違う**。
#
# 理科・社会の一問一答は思い出すだけなので45秒でよい。
# 数学は途中の計算がある ―― 連立方程式を解いて選ぶのに45秒は短い。
# 同じ45秒で見積もったせいで、数学だけ「50問で34分」と出て、
# 本番と同じ50分にならなかった。**足りないのは問題数ではなく秒数**である。
#
# 数を増やして50分に届かせるのは筋が悪い。50分で60問解く数学のテストは
# 本番に無く、それでは時間配分の練習にならない。
# ★ 紙で解くときの時間で決めている。**アプリより遅い。**
#   紙は途中式を書き、消しゴムを使い、問題文を読み返す。
#   前は「数学の1問 70秒」としていて、50分で 36問が並んだ。
#   中2が 連立方程式や 一次関数を 1問70秒で解くことはない。
#   実際の 中学校の 定期テスト・高校入試は、50分で 小問 20〜25問である。
SUBJECT_SEC = {
    # 途中式を書く。1問 2分半。50分で 20問。
    "math":     {"quiz": 150, "term": 60},
    # 長文は 1問 1分半。漢字・語句は速い。
    "japanese": {"quiz": 90,  "term": 30},
    # 一問一答は思い出すだけ。図や穴埋めは少し長い。
    "science":  {"quiz": 75,  "term": 40},
    "social":   {"quiz": 75,  "term": 40},
    # 語の意味・文法。読解だけ長いが、平均でならす。
    "english":  {"quiz": 60,  "term": 30},
}


def sec_of(x):
    """その1問にかける秒数。教科ごとの表があればそちらを使う。"""
    per = SUBJECT_SEC.get(x.get("subject") or "", SEC_PER)
    return per.get(x.get("t"), SEC_PER.get(x.get("t"), DEFAULT_SEC))

# 1教科あたりの量（秒）。**本番と同じ50分**。
# 組み分けテストが1教科50分なので、対策も同じ長さにする。
# 本番より長くしても短くしても、時間の感覚が身につかない。
CAP_SEC = 50 * 60
# ふだんの毎日テストの目安（1教科20分ぶん）。対策はこの3倍を狙うが、
# 上の50分で頭打ちになる。
BASE_SEC = 20 * 60
PREP_MULT = 3

# ------------------------------------------------------------------
# 1日の毎日テストにかけてよい時間（分）。**学年で変える。**
#
# 前は全学年ほぼ同じで、上限まで出ると小4で149分、中3で222分だった。
# 小4に中3と同じ量を出すのは、続かない以前に、机に向かえる時間ではない。
#
# 狙いは「単元確認テストのための毎日の反復」なので、
# 1日で嫌にならない長さに収める。
#
#   小4 20分 → 小5 32分 → 小6 45分   （小学生は45分を上限）
#   中1 50分 → 中2 55分 → 中3 60分   （中学生でまた傾斜をつける）
#
# **数ではなく時間で決める。** 1問の重さが教科でちがうため
# （数学の1問は70秒、英語は30秒）。同じ「12問」でも、
# 数学は14分、英語は6分になってしまう。
#
# ★ この表は app/js/config.js にも同じものがある（端末の中だけで
#   1日の量を決めるため。オフラインでも動く必要がある）。
#   片方だけ直すと画面とサーバで量が食い違う。
#   一致は app/tools/こわれ方の検査.py が見張っている。
DAILY_MIN = {"e4": 20, "e5": 32, "e6": 45,
             "j1": 50, "j2": 55, "j3": 60}
DAILY_MIN_DEFAULT = 30

# 新しく覚える分にあてる割合。残りは復習。
# 新出を厚くすると札が増えすぎて、翌週以降の復習が破綻する。
NEW_SHARE = 0.35


# アプリで解くときの時間。**紙より速い。**
#
# 紙は途中式を書き、消しゴムを使い、問題文を読み返す（SUBJECT_SEC）。
# アプリは選択肢を押すだけで、書く手間も 見直しも無い。
# 同じ表で両方をまかなうと、どちらかが必ず外れる ――
# 紙に合わせると毎日テストが数問になり、アプリに合わせると
# 50分の紙に 36問 並ぶ（実際そうなっていた）。
#
# ★ この表は app/js/config.js にも同じものがある（端末の中だけで
#   1日の量を決めるため）。片方だけ直すと画面とサーバで量が食い違う。
#   一致は app/tools/こわれ方の検査.py が見張っている。
APP_SEC = {
    "math":     {"quiz": 70, "term": 40},   # 計算がある
    "english":  {"quiz": 30, "term": 25},   # 語の意味。速い
    "japanese": {"quiz": 35, "term": 25},   # 漢字の読み。速い
}


def daily_sec(grade, subject_count):
    """その学年の1教科あたり、1日に使ってよい秒数（新出, 復習）。"""
    per = DAILY_MIN.get(grade, DAILY_MIN_DEFAULT) * 60.0 / max(1, subject_count)
    return per * NEW_SHARE, per * (1.0 - NEW_SHARE)


def fit_count(subject, kind, sec):
    """その秒数に入る問数。**アプリで解く時間で数える。**"""
    per = APP_SEC.get(subject) or SEC_PER
    one = per.get(kind, SEC_PER.get(kind, DEFAULT_SEC))
    return max(1, int(sec / one)) if one else 1


# 上位編に回す割合。難易度が教材から取れないときに使う。
# **まちがえられやすい上位3分の1**を上位編、残りを基本編とする。
HARD_SHARE = 0.34

_CACHE = {}


# ------------------------------------------------------------------
# 教材を読む
# ------------------------------------------------------------------
# 画面側（app/js/content.js の slug）とまったく同じ規則。
#
#   小文字にして、英数字とかな・漢字**以外**をぜんぶ「-」に潰し、
#   前後の「-」を落とす。
#
# **ここが1文字でもずれると、記録の項目IDと突き合わせできない。**
# 実際ずれていて、「まちがえた問題を翌日に戻す」が1問も戻らなかった
# （句読点や「？」を落としていなかった）。
_SLUG_KEEP = re.compile(r"[^a-z0-9\u3040-\u30ff\u4e00-\u9fff]+")


def _slug(t):
    """app/js/content.js の slug と**同じ規則**。IDを一致させるために必要。

    ★ 片方だけ直すと、サーバと画面で項目IDが食い違い、
      「にがて」も「対策」も静かに0件になる。必ず両方直すこと。
      一致は app/tools/こわれ方の検査.py が見張っている。

    全角は半角にそろえてから削る（NFKC）。そろえないと「ＡＢＣ」が
    まるごと落ちて空のIDになり、そういう見出しどうしが全部ぶつかる。
    削った結果が空になるときは、元の文字列の短い指紋を使う ――
    IDは読めなくてよいが、**ぶつかってはいけない**。
    """
    t = unicodedata.normalize("NFKC", str(t)).lower()
    out = _SLUG_KEEP.sub("-", t).strip("-")
    if out:
        return out
    # **画面側とまったく同じ計算にする。** 別の計算にすると、
    # ここに落ちた項目だけサーバと画面でIDが食い違う。
    # （JavaScript の 32bit 演算をそのまま写している）
    h = 0
    for ch in t:
        h = ((h << 5) - h + ord(ch)) & 0xFFFFFFFF
    return "x" + format(h, "x")


GRADE_IN_NAME = re.compile(r"(e[456]|j[123])")


def _has_grade(base):
    """教材の名前に学年が入っているか。core のように入っていないものは
    全学年で使う教材である。"""
    return bool(GRADE_IN_NAME.search(base))


def _rows(text):
    """`["…","…"]` の並びを、文字列の列にほどく。

    教材は2つの書き方が混ざっている。

        var Q = [ ["…","…"], … ];        並びをそのまま書く形
        var Q = []; Q.push( ["…","…"], … );   あとから足す形

    どちらも中身は同じ `[...]` の並びなので、**かたまり単位で拾う**。
    行で切ると、1問が2行に折り返してあるもの（数学に多い）を落とす。

    JSON としては読めない ―― 末尾のカンマや行コメントが入るため。
    """
    out = []
    for m in re.finditer(r"\[(?:\s*\"(?:[^\"\\\\]|\\\\.)*\"\s*,?)+\]", text):
        cells = re.findall(r'"((?:[^"\\\\]|\\\\.)*)"', m.group(0))
        if len(cells) >= 2:
            out.append([c.replace('\\"', '"') for c in cells])
    return out


def _sections(src, name):
    """その配列に属する部分を、まとめて返す。

    `var Q = [ … ];` の中身と、`Q.push( … );` の中身の両方。
    """
    out = []
    m = re.search(r"var\s+" + name + r"\s*=\s*\[(.*?)\n\];", src, re.S)
    if m:
        out.append(m.group(1))
    for m in re.finditer(name + r"\.push\((.*?)\n\);", src, re.S):
        out.append(m.group(1))
    return out


# 5列目が「単元名」か「解説」かを見分ける。
#
# 教科によって、同じ位置に別のものが入っている。
#   理科・社会 … ["問題","答","誤答","小5","植物の発芽"]      ← 単元
#   数学       … ["問題","答","誤答","基礎","絶対値は距離…"]  ← 解説
#
# 目録に書いてある列の意味はあてにならない（どちらも「解説」と書いてある）。
# **中身の形で見分ける。** 解説は文なので句点で終わるか、長い。
# 単元は名詞のひとかたまりで、短い。

def _rows_all(src, var):
    """その種類の節（V や Q）を、ぜんぶつなげて行で返す。

    誤答を「同じ教材の他の語」から作るとき、節ごとに区切って見ると
    節が小さい教材（10語しかない節など）で候補が足りなくなる。
    """
    out = []
    for body in _sections(src, var):
        out += _rows(body)
    return out


def _is_note(t):
    t = (t or "").strip()
    return bool(t) and ("。" in t or len(t) > 14)


def pack_items(subject, grade, dedupe=True):
    """その教科・学年の問題を、1問ずつの形で返す。

    返す1問
        {"id", "t":"quiz"|"term", "subject", "unit",
         "q": 問題文, "ans": 答え, "dis": [誤答…], "note": 解説}

    用語（T）は「表→裏」を問う形にそろえる。PDFにも同じ形で並ぶ。
    """
    ck = (subject, grade)
    if dedupe and ck in _CACHE:
        return _CACHE[ck]
    code = CODE.get(subject)
    out = []
    d = os.path.join(CONTENT_DIR, subject)
    if code and os.path.isdir(d):
        names = [n for n in sorted(os.listdir(d)) if n.endswith(".js")]
        # **学年別の教材があるなら、そちらだけを使う。**
        #
        # 前は「名前に学年が入っていない教材は全学年で使う」だった。
        # そのため英語では、学年別のパック（88問）に加えて
        # english/core（IELTS B2〜C1 の1,134問・単元なし）が
        # 小5から中3まで全学年に混ざり、9割が学年外の語彙になっていた。
        # 小4にいたっては、英語の授業が無いのに "accommodation" が
        # 対策テストに並んでいた。
        #
        # 学年別に整備した教科では、その学年の教材が無ければ**出さない**。
        # 中途半端に別の学年のものを出すより、出さないほうがよい。
        graded = [n for n in names if _has_grade(n[:-3])]
        if graded:
            names = [n for n in graded if grade in n[:-3]]
        for name in names:
            base = name[:-3]
            src = io.open(os.path.join(d, name), encoding="utf-8").read()
            for body in _sections(src, "Q"):
                for r in _rows(body):
                    if len(r) < 2:
                        continue
                    # 6列目があれば、それが単元名（解説と分けて持っている）。
                    # 5列しかない古い教材だけ、「。が入っていれば解説」という
                    # 当てずっぽうで見分ける。**この当てずっぽうは外れる** ――
                    # 数学の解説が時間割の単元名として表に出たことがある。
                    # 新しく教材を作るときは必ず6列目を書くこと。
                    fifth = r[4] if len(r) > 4 else ""
                    if len(r) > 5:
                        unit, note = r[5], fifth
                    else:
                        unit = "" if _is_note(fifth) else fifth
                        note = fifth if _is_note(fifth) else ""
                    out.append({
                        "id": "%s:q:%s" % (code, _slug(r[0])),
                        "t": "quiz", "subject": subject, "pack": base,
                        "unit": unit,
                        # 7列目は図の名前。図そのものは content/figures.js。
                        # ここでは名前だけ渡す ―― 絵は画面と紙が引く。
                        "fig": r[6] if len(r) > 6 else "",
                        # 8列目は読解文の名前。本文は content/readings.js。
                        # **1つの長文を、何問でも共有する。** 本文を問題ごとに
                        # 抱えると、同じ800字が5回並ぶ紙になる。
                        "bun": r[7] if len(r) > 7 else "",
                        "band": r[3] if len(r) > 3 else "",
                        "q": r[0], "ans": r[1],
                        "dis": [x for x in str(r[2] if len(r) > 2 else "").split("|") if x],
                        "note": note,
                    })
            # V（英単語）… 見出し語から意味を問う形にそろえる。
            #
            # 誤答は **同じ教材の中の、他の語の意味**から取る。
            # 前は誤答を作っていなかったので、英語だけ紙に刷れなかった
            # （選択肢の無い問題はマークシートで採点できないため落ちる）。
            # 5教科の紙のはずが4教科しか載っていない、という形で出ていた。
            #
            # よその教材から持ってくると「明らかに畑ちがい」の選択肢になり、
            # 読まなくても消せてしまう。同じ教材の中から取れば、
            # どれも同じ学年・同じ難しさの語の意味になる。
            vrows = [r for r in _rows_all(src, "V") if len(r) >= 4]
            means = [str(r[3]).strip() for r in vrows if str(r[3]).strip()]
            for i, r in enumerate(vrows):
                ans = str(r[3]).strip()
                # 一定の間をあけて3つ取る。隣どうしだと、教材の並び順が
                # 意味の近い語で固まっているとき、紛らわしすぎる。
                dis, step = [], max(7, len(means) // 17)
                j = i
                while len(dis) < 3 and len(means) > 4:
                    j = (j + step) % len(means)
                    if j == i:
                        j = (j + 1) % len(means)
                    cand = means[j]
                    if cand != ans and cand not in dis:
                        dis.append(cand)
                out.append({
                    "id": "%s:v:%s:%s" % (code, _slug(r[0]), _slug(r[1])),
                    "t": "term", "subject": subject, "pack": base,
                    "unit": "", "band": r[2] if len(r) > 2 else "",
                    "q": "%s（%s）の意味は？" % (r[0], r[1]), "ans": ans,
                    "dis": dis,
                    "note": r[7] if len(r) > 7 else "",
                })
            for body in _sections(src, "T"):
                for r in _rows(body):
                    if len(r) < 2:
                        continue
                    note = r[3] if len(r) > 3 else ""
                    out.append({
                        "id": "%s:t:%s" % (code, _slug(r[0])),
                        "t": "term", "subject": subject, "pack": base,
                        "unit": "", "band": r[2] if len(r) > 2 else "",
                        "q": "「%s」とは？" % r[0], "ans": r[1], "dis": [],
                        "note": note if _is_note(note) else "",
                    })
    # **同じIDを2つ持たない。画面と同じ規則でそろえる。**
    #
    # 画面（app/js/content.js の add）は、同じIDが来たら
    # **先に読んだほうを残して、あとは捨てる**。サーバがそろえないと、
    # 同じ項目についてサーバと画面が別の答えを持つことになる ――
    # 刷った紙の正解と、アプリの正解が食い違う。
    #
    # 実際 english/core には同じ語が2〜3回入っており、そのうち52件は
    # 訳がちがう（maintain＝「保守する」と「維持する、主張する」）。
    # 教材そのものの直しは別途だが、**食い違いだけは先に止める。**
    if not dedupe:
        # 落とす前。検査（app/tools/check-content.py）が
        # 「何が落とされたか」を数えるために使う。控えには入れない。
        return out
    seen, uniq = set(), []
    for x in out:
        if x["id"] in seen:
            continue
        seen.add(x["id"])
        uniq.append(x)
    out = uniq
    _CACHE[ck] = out
    return out


# ------------------------------------------------------------------
# 範囲を決める
# ------------------------------------------------------------------
def units_in_range(school, grade, subject, since_date):
    """前回のテストの翌日から、いまの回までに習った単元。

    since_date が空なら、学期のはじめから。
    授業計画に日付が入っていない回は数えない（いつやったか分からない）。
    """
    key = "%s:%s" % (grade, subject)
    pl = L.plan(school, key) or {}
    today = time.strftime("%Y-%m-%d")
    out = []
    for l in sorted((pl.get("lessons") or []), key=lambda x: x.get("n") or 0):
        d = l.get("date") or ""
        if not d or d > today:
            continue
        if since_date and d <= since_date:
            continue
        t = (l.get("topic") or "").strip()
        # 総復習の回そのものは単元ではない。中身は前の4回にある。
        if l.get("review") or t.startswith("総復習"):
            continue
        if t:
            out.append(t)
    return out


def in_scope(items, units):
    """単元名で絞る。名前が1つも合わなければ、絞らずに全部返す。

    **合わないことを失敗にしない。** 漢字や英単語のように単元を
    持たない教材もあるし、校舎が独自の単元名を使うこともある。
    そこで対策が出なくなるより、範囲が広いほうがまだよい。
    """
    if not units:
        return items
    want = set(units)
    got = [x for x in items if x.get("unit") and x["unit"] in want]
    return got if got else items


# ------------------------------------------------------------------
# 難易度
# ------------------------------------------------------------------
def hardness(school, grade, subject, items, accounts, progress_of):
    """1問ごとの「まちがえられやすさ」。0〜1。

    その学年の生徒が実際にどれだけまちがえたかで測る。
    記録が無い問題は 0.5（どちらとも言えない）に置く ――
    0 にすると、まだ誰も解いていない問題が全部「やさしい」に回る。
    """
    sids = [a["sid"] for a in accounts
            if a.get("role") == "student" and (a.get("level") or "") == grade
            and not a.get("leftAt")]
    seen, bad = {}, {}
    pre = CODE.get(subject, "") + ":"
    for sid in sids:
        cards = progress_of(sid)
        for cid, c in (cards or {}).items():
            if not cid.startswith(pre):
                continue
            if not isinstance(c, list) or len(c) < 6:
                continue
            seen[cid] = seen.get(cid, 0) + 1
            if c[4] or 0:
                bad[cid] = bad.get(cid, 0) + 1
    out = {}
    for x in items:
        n = seen.get(x["id"], 0)
        out[x["id"]] = (bad.get(x["id"], 0) / n) if n else 0.5
    return out


def split_by_level(school, items, materials):
    """教材の難易度で、上位編と基本編に分ける。

    教材（materials.json）に level が付いていれば、それに従う。
        level = "advanced" … 応用編。上位編にだけ入る
        level = "basic"    … 基本編。基本編にだけ入る
    付いていなければ、どちらにも入れる（あとで記録の難しさで分ける）。

    アプリの中の教材は pack ごとに登録されるので、pack が分かる
    問題だけがここで分かれる。分からないものは両方に入る。
    """
    adv, bas = [], []
    lv = {}
    for mid, m in (materials or {}).items():
        if m.get("level") in ("advanced", "basic"):
            lv[mid] = m["level"]
    if not lv:
        return None                      # 教材に難易度が無い
    for x in items:
        l = lv.get(x.get("pack") or "")
        if l == "advanced":
            adv.append(x)
        elif l == "basic":
            bas.append(x)
        else:
            adv.append(x)
            bas.append(x)
    return {"advanced": adv, "basic": bas}


# ------------------------------------------------------------------
# 組み立て
# ------------------------------------------------------------------
def target_count(items, seconds):
    """その秒数に収まる問題数。1問ずつ足していって、越えたら止める。"""
    n = 0
    used = 0
    for x in items:
        c = sec_of(x)
        if used + c > seconds:
            break
        used += c
        n += 1
    return max(1, n), used


def build(school, grade, subject, tier, wrong_ids, day_key,
          units=None, materials=None, hard=None, items=None):
    """1教科ぶんの対策を組む。

    tier       "advanced"（上位編）／"basic"（基本編）
    wrong_ids  その生徒が前に落とした問題。**必ず先頭に入れる**
    day_key    その日の種。同じ日に開き直しても同じ問題が出る
    """
    allitems = items if items is not None else pack_items(subject, grade)
    if not allitems:
        return None
    items = in_scope(allitems, units or [])

    split = split_by_level(school, items, materials)
    pool = items
    if split:
        pool = split.get(tier) or items
    elif hard:
        # 教材に難易度が無いときは、記録から測った難しさで分ける。
        rows = sorted(items, key=lambda x: -hard.get(x["id"], 0.5))
        cut = max(1, int(len(rows) * HARD_SHARE))
        pool = rows[:cut] if tier == "advanced" else rows[cut:]
        if not pool:
            pool = items

    # 1. まちがえた問題を先に。**必ず入れる。**
    by_id = {x["id"]: x for x in items}
    first = [by_id[i] for i in (wrong_ids or []) if i in by_id]

    # 2. 残りは、その日の種で混ぜて取る。日が変われば並びも変わる。
    seed = "%s|%s|%s|%s" % (school, grade, subject, day_key)
    have = {y["id"] for y in first}

    # **長文は必ず1本入れる。範囲の外から取る。**
    #
    # 長文の設問は数が少ない（国語 中3 で 294問中4問）ので、
    # ただ混ぜるだけでは紙にも毎日テストにも ほとんど出てこない。
    # 実際のテストで配点が大きいのは長文なので、出ないままでは
    # 対策にならない。
    #
    # ★ **allitems から取ること。** 読解の単元（「長文を読む」）は
    #   授業で習う単元ではないので、範囲（units）で絞ると消える。
    #   実際、範囲つきで刷った紙には長文が1問も載っていなかった ――
    #   漢字の読みばかり27問が並び、読解が丸ごと落ちていた。
    #   読解は「どの単元をやったか」に関係なく必要である。
    #
    # 本文1本ぶんの設問を、まちがえた問題の次に置く。
    # どの本文にするかは その日の種で決める（日ごとに変わる）。
    bunned = {}
    for x in allitems:
        if x.get("bun") and x["id"] not in have:
            bunned.setdefault(x["bun"], []).append(x)
    if bunned:
        names = sorted(bunned)
        pick = names[random.Random(seed + "|bun").randrange(len(names))]
        first = first + bunned[pick]
        have |= {x["id"] for x in bunned[pick]}

    rest = [x for x in pool if x["id"] not in have]
    random.Random(seed).shuffle(rest)

    want_sec = min(CAP_SEC, BASE_SEC * PREP_MULT)

    # **足りなければ範囲を広げる。**
    # 前回のテストからの単元だけでは、教材によっては4分ぶんしか
    # 集まらない。4分で終わる「総復習」は総復習ではない。
    # 狭い順に足していく ―― まず範囲内、次に学年ぜんぶ。
    def secs(rows):
        return sum(sec_of(x) for x in rows)

    if secs(first + rest) < want_sec:
        have |= {x["id"] for x in rest}
        extra = [x for x in allitems if x["id"] not in have]
        random.Random(seed + "|wide").shuffle(extra)
        rest = rest + extra

    # **広げても、版のちがいは残す。**
    # 教材の数がまだ少ないと、60分ぶんを集めるのに学年ぜんぶを
    # 使うことになり、上位編と基本編の中身がほとんど同じになる。
    # そこで並び順を版で変える ―― 上位編はまちがえられやすいものから、
    # 基本編はやさしいものから。取る数は同じでも、前半に来る問題が変わる。
    if hard:
        rest.sort(key=lambda x: hard.get(x["id"], 0.5),
                  reverse=(tier == "advanced"))

    picked = first + rest
    n, used = target_count(picked, want_sec)
    picked = picked[:n]
    return {
        "subject": subject, "tier": tier,
        "items": picked,
        "n": len(picked),
        "minutes": int(round(used / 60.0)),
        "carried": len(first),
        "scoped": bool(units),
    }


def tier_for(accuracy):
    """直近の出来から、どちらの版を出すか。

    6割以上なら上位編。それ未満は基本編。
    記録が無い生徒（accuracy が None）は基本編から始める ――
    いきなり上位編を出して手が止まるより、そのほうがよい。
    """
    if accuracy is None:
        return "basic"
    return "advanced" if accuracy >= 0.6 else "basic"


TIER_NAME = {"advanced": "上位編", "basic": "基本編"}


# ------------------------------------------------------------------
# 生徒1人ぶんを組む
# ------------------------------------------------------------------
def for_student(school, grade, subjects, sid, cards, accuracy,
                accounts=None, progress_of=None, materials=None, when=None, win=None, dept=None):
    """その生徒の総復習テスト対策。教科ごとに1本ずつ。

    出る時期でなければ None を返す ―― 画面はそのとき何も出さない。

    cards     その生徒の記録（項目ID → [iv, ef, due, reps, lapse, seen, known]）
    accuracy  直近の出来（0〜1）。難易度を決めるのに使う。無ければ None
    """
    win = win or E.window(school, when, dept)
    if not win:
        return None
    tier = tier_for(accuracy)
    day = time.strftime("%Y-%m-%d", time.localtime(when or time.time()))

    # まちがえた問題。**翌日以降に必ず戻ってくる。**
    wrong = []
    for cid, c in (cards or {}).items():
        if isinstance(c, list) and len(c) > 4 and (c[4] or 0):
            wrong.append((cid, c[4], int(c[5] or 0) if len(c) > 5 else 0))
    wrong.sort(key=lambda r: (-r[1], -r[2]))
    wrong_ids = [r[0] for r in wrong]

    sets = []
    for sub in subjects:
        items = pack_items(sub, grade)
        if not items:
            continue
        units = units_in_range(school, grade, sub, win.get("since") or "")
        hard = None
        if accounts is not None and progress_of is not None:
            hard = hardness(school, grade, sub, items, accounts, progress_of)
        got = build(school, grade, sub, tier, wrong_ids, day,
                    units=units, materials=materials, hard=hard, items=items)
        if got:
            sets.append(got)
    if not sets:
        return None
    return {
        "exam": win["exam"], "left": win["left"], "since": win.get("since") or "",
        "tier": tier, "tierName": TIER_NAME[tier],
        "sets": sets,
        "minutes": sum(x["minutes"] for x in sets),
    }


def light(prep):
    """画面の一覧に出すぶんだけ。問題そのものは持たせない。

    1回の応答に5教科×80問を載せると 200KB を超える。
    一覧では「何問・何分」だけを見せ、始めたときに中身を取りに行く。
    """
    if not prep:
        return None
    out = dict(prep)
    out["sets"] = [{k: v for k, v in x.items() if k != "items"}
                   for x in prep["sets"]]
    return out


# 一覧に残す欄。items だけを外し、あとは通す ――
# 苦手（weak）ややり直す所（review）は一覧に出すものなので、
# ここで落とすと画面に何も出なくなる。
