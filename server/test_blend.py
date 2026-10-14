#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紙とアプリの併走が正しく数えられるかを確かめる。

守りたい性質はひとつ ――
**紙でちゃんとやっている生徒を、不真面目に見せないこと。**

これが崩れると、導入した講師が最初の一週間で使うのをやめる。
画面を見ても気づけない（紙の生徒の数字が低いのは一見もっともらしい）ので、
機械で押さえておく。

    python3 server/test_blend.py
"""

import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/myacady-blend-test"
sys.path.insert(0, HERE)
os.environ["MYACADY_ROOT"] = ROOT
shutil.rmtree(ROOT, ignore_errors=True)

import paths            # noqa: E402
import tube_server as T  # noqa: E402

SCHOOL = "london"
paths.ensure_school(SCHOOL)
paths.save(paths.school_file(SCHOOL, "school.json"),
           {"id": SCHOOL, "name": "ロンドン校", "code": "l"})

fails = []


def check(name, ok, detail=""):
    print("  %s %s%s" % ("OK  " if ok else "×   ", name, "" if ok else "  ← " + str(detail)))
    if not ok:
        fails.append(name)


NOW = int(time.time())
FUTURE = (NOW + 86400 * 3) * 1000
PAST = (NOW - 86400 * 3) * 1000


def asg(src, lo, hi, due):
    return {"id": "a%s%d" % (src, lo), "source": src, "from": lo, "to": hi,
            "dueAt": due, "route": T.route_of(SCHOOL, src)}


print("紙とアプリの併走\n")

print("経路は教材から決まる（宿題ごとに指定させない）")
check("単語帳はアプリ", T.route_of(SCHOOL, "myvocab") == "app")
check("漢字の書き取りは紙", T.route_of(SCHOOL, "kanji-write") == "paper")
check("計算ドリルは紙", T.route_of(SCHOOL, "keisan") == "paper")
# 台帳に無い教材は紙として扱う。アプリ扱いにすると、押した先に中身の無い
# 「やる」ボタンが出る（GRIT を台帳に載せ忘れたときがこれ）。
check("台帳に無い教材は紙扱い", T.route_of(SCHOOL, "nazo-no-kyouzai") == "paper")
check("アプリの教材（pack のID）はアプリ", T.route_of(SCHOOL, "english/core") == "app")

print("\n画面から送られてきた経路を信じない")
rec = T.valid_assignment(SCHOOL, {
    "title": "漢字 1-100", "source": "kanji-write", "from": 1, "to": 100,
    "classId": "j2r", "dueAt": FUTURE,
    "route": "app",           # ← 嘘の申告
})
check("嘘の route は上書きされる", rec["route"] == "paper", rec["route"])
check("宿題には kind が付く", rec.get("kind") == "hw", rec.get("kind"))

print("\n紙9割の生徒と、アプリ10割の生徒（どちらもアプリでは何もしていない）")
NOTHING = {"cards": {}, "hw": {}, "hist": {}}
# アプリ10割：単語帳だけ。うち1件は期限切れ
a10 = [asg("myvocab", 1, 50, FUTURE), asg("myvocab", 51, 100, PAST)]
# 紙9割：漢字・計算・テキストが中心。単語帳が少しだけ
p90 = [asg("kanji-write", 1, 200, FUTURE), asg("keisan", 1, 250, FUTURE),
       asg("wa-text", 1, 100, FUTURE), asg("myvocab", 1, 50, FUTURE)]

s10 = T.summarise_one(NOTHING, a10)
s90 = T.summarise_one(NOTHING, p90)

check("アプリ10割の生徒は share=100%", s10["share"] == 1.0, s10["share"])
check("紙9割の生徒は share が1割前後", s90["share"] < 0.15, s90["share"])
check("紙の宿題は「未提出」に数えない", s90["due"] == 1, s90["due"])
check("紙の宿題は「期限切れ」に数えない", s90["overdue"] == 0, s90["overdue"])
check("紙で出ている件数は別に数える", s90["paperDue"] == 3, s90["paperDue"])

print("\n★ 紙の生徒が「気にかけたい生徒」に並ばないこと")
# 講師画面は overdue>0 か、share>0.5 かつ活動が少ない場合だけ挙げる。
flagged_90 = s90["overdue"] > 0 or (s90["share"] > 0.5)
flagged_10 = s10["overdue"] > 0
check("紙9割の生徒は挙がらない", not flagged_90,
      "share=%.2f overdue=%d" % (s90["share"], s90["overdue"]))
check("アプリ10割で期限切れの生徒は挙がる", flagged_10)

print("\n紙の宿題は期限から1週間で画面から落ちる（永久に残さない）")
old = asg("kanji-write", 1, 50, (NOW - 86400 * 10) * 1000)
s_old = T.summarise_one(NOTHING, [old])
check("期限切れの紙は paperDue に数えない", s_old["paperDue"] == 0, s_old["paperDue"])

print("\nアプリの宿題を進めたら達成率に出る")
done = {"cards": {}, "hist": {},
        "hw": {"amyvocab1": {"done": {str(i): 1 for i in range(25)}}}}
s = T.summarise_one(done, [asg("myvocab", 1, 50, FUTURE)])
check("50問中25問で達成率50%", abs(s["hwDone"] - 0.5) < 0.02, s["hwDone"])

print("\n紙の宿題の4段階評価（任意の機能）")
PAPER = [asg("kanji-write", 1, 100, FUTURE), asg("keisan", 1, 80, FUTURE)]
aid0, aid1 = PAPER[0]["id"], PAPER[1]["id"]

# ① 誰も評価をつけていない生徒
none_ = T.summarise_one(NOTHING, PAPER, rated={})
# ② 「よくできた」がついた生徒
good = T.summarise_one(NOTHING, PAPER, rated={aid0: {"v": 3}})
# ③ 「もうすこし」がついた生徒
low = T.summarise_one(NOTHING, PAPER, rated={aid0: {"v": 1}})
# ④ 「出ていない」がついた生徒
none_sub = T.summarise_one(NOTHING, PAPER, rated={aid0: {"v": 0}})

check("未評価は rated=0", none_["rated"] == 0, none_["rated"])
check("未評価は low=0（悪い印を立てない）", none_["low"] == 0, none_["low"])
check("◎ は rated に数え、low には数えない",
      good["rated"] == 1 and good["low"] == 0, good)
check("△ は low に数える", low["low"] == 1, low)
check("✕ は low に数える", none_sub["low"] == 1, none_sub)

print("\n★ 未評価の生徒が、評価済みの生徒より不利にならないこと")
# 講師画面が「きにかけたい生徒」に挙げる条件（ui-teacher.js と同じ判定）
def flagged(s):
    return s["low"] > 0 or s["overdue"] > 0
check("未評価の生徒は挙がらない", not flagged(none_), none_)
check("◎ の生徒も挙がらない", not flagged(good), good)
check("△ の生徒だけ挙がる", flagged(low), low)
check("未評価と◎で、挙がるか否かが同じ",
      flagged(none_) == flagged(good))
check("評価をつけても share は変わらない（構造の数字）",
      none_["share"] == good["share"] == low["share"],
      (none_["share"], good["share"], low["share"]))

print("\n2件の紙のうち1件だけ評価しても、残り1件は無かったことにならない")
half = T.summarise_one(NOTHING, PAPER, rated={aid0: {"v": 2}})
check("評価は1件、紙で出ているのは2件",
      half["rated"] == 1 and half["paperDue"] == 2, half)

print()
if fails:
    print("× %d件おちた: %s" % (len(fails), " / ".join(fails)))
    sys.exit(1)
print("すべて通った。")
