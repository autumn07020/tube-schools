#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""長文読解 ―― 国語と英語。

    python3 app/tools/gen_choubun.py

なぜ足すか
----------
はじめに作った読解は 60〜150字で、実際のテストの長文には遠かった。
本人の指示は「一問一答ではなく、長文なども用意する」である。

本文はどこに置くか
------------------
**本文は共有し、設問だけを1問ずつにする。**

忘却曲線は項目ごとに独立しているので、設問は1問ずつ別の日に出る。
だからといって1問ごとに本文を抱えさせると、同じ600字が紙の上に
5回並ぶことになる。図（content/figures.js）と同じやり方にする ――
本文は content/readings.js に名前を付けて1つだけ置き、設問は
8列目でその名前を指す。

  ・画面 … その設問を出すとき、本文もいっしょに出す（1問で完結する）
  ・紙  … 同じ本文の設問をまとめて並べ、本文は先頭で1回だけ刷る

設問の作り方
------------
**本文に書いてあることだけを問う。**「筆者の気持ちを想像しなさい」は
4択にならない。指示語・接続語・言いかえ・理由・要旨・段落の役割 ――
読めば1つに決まるものだけにする。

誤答は「本文に書いてあるが、問いの答えではないもの」を混ぜる。
まったく無関係な文を置くと、本文を読まなくても消せてしまう。

典拠
----
本文・設問・誤答・解説はすべてここで書き下ろしている。
既存の作品からの引用はない（引用すると著作権の処理が必要になり、
教材の入れ替えができなくなる）。
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_content import Pack, report          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(os.path.dirname(HERE), "content")

BAND_CODE = {"小4": "e4", "小5": "e5", "小6": "e6",
             "中1": "j1", "中2": "j2", "中3": "j3"}


# ==================================================================
# 本文。名前 → 文章。
# ==================================================================
BUN = {}

BUN["ko-e4-ari"] = (
    "校ていの すみに、小さな アリの 行列が できていた。ぼくは しゃがんで "
    "しばらく 見ていた。アリたちは みんな 同じ 道を 通り、すれちがうたびに "
    "頭を 合わせている。まるで あいさつを しているようだ。\n"
    "先生に 聞くと、アリは 通った 道に においを つけて 歩くのだそうだ。"
    "えさを 見つけた アリが 巣へ 帰るとき、その においを たどれば、"
    "ほかの アリも 同じ 場所へ 行ける。頭を 合わせているのは、"
    "においや 食べ物の ことを 知らせ合っているのだと いう。\n"
    "小さな 体の どこにも 地図は ない。それでも アリたちは まよわない。"
    "ぼくは 帰り道、いつもの 曲がり角で 一度 立ち止まって みた。"
    "ここにも においが 残っていたら、ぼくは まよわずに 帰れるだろうか。")

BUN["ko-e5-mori"] = (
    "森に 雨が ふると、水は すぐに 川へ 流れこむわけでは ない。"
    "落ち葉や 土が スポンジのように 水を すいこみ、しばらく たくわえる。"
    "たくわえられた 水は、何日も かけて 少しずつ しみ出し、川へ 向かう。\n"
    "だから 森の ある 地域では、雨が やんでも 川の 水が 急に 減ることは "
    "ない。逆に 大雨の ときも、水が 一度に おし寄せないので、"
    "こう水が 起こりにくい。森は 「緑の ダム」と よばれることが ある。\n"
    "ところが 木を 切りすぎると、この はたらきは 失われる。"
    "雨は 土を けずりながら まっすぐ 川へ 流れ、川は にごり、"
    "少し 日照りが 続くだけで 水が 足りなくなる。"
    "森を 守ることは、遠く はなれた 町の 水を 守ることでも ある。")

BUN["ko-e6-chizu"] = (
    "地図は 世界を そのまま 写したものでは ない。丸い 地球を 平らな 紙に "
    "うつすとき、面積・形・きょり・方位の どれかは かならず ゆがむ。"
    "四つ すべてを 正しく 表す 地図は、原理として つくれない。\n"
    "たとえば、船の 航海に 使われてきた 地図は、方位が 正しく なるように "
    "つくられている。そのかわり 高い 緯度の 陸地は 実際より ずっと "
    "大きく えがかれる。北の 島国が 大陸ほどの 大きさに 見えるのは、"
    "その ためである。一方、面積を 正しく した 地図では、"
    "形が 横に つぶれて 見える。\n"
    "つまり 地図には かならず 目的が ある。何を 正しく 示したくて "
    "つくられたのかを 知らないまま 読むと、地図は かんたんに "
    "人を あやまらせる。地図を 読む 力とは、"
    "そこに 何が えがかれていないかに 気づく 力でも ある。")

BUN["ko-j1-jisho"] = (
    "辞書は 言葉の 意味を 決めているのではない。多くの人が 実際に 使っている "
    "意味を、あとから 書きとめているだけである。だから 辞書は 何年かごとに "
    "書きかえられる。新しい語が 加わり、使われなくなった語には "
    "「古い言い方」と 注が つく。\n"
    "この 順番を まちがえると、話が おかしくなる。「辞書に 載っていないから "
    "その 使い方は まちがいだ」と 言う人が いるが、それは "
    "地図に 載っていないから その 道は 存在しない、と 言うのに 似ている。"
    "道が 先に あり、地図は あとから ついてくる。\n"
    "もちろん、何でも 好きに 使ってよい という ことでは ない。"
    "言葉は 通じてはじめて 言葉である。多くの人が 共有していない 使い方は、"
    "相手に 届かない。辞書が 役に立つのは、"
    "「いま どこまでが 共有されているか」を 教えてくれる からである。")

BUN["ko-j2-kisoku"] = (
    "規則は 人を しばるために あるのではない。むしろ、規則が あるからこそ、"
    "その 内側では 自由に ふるまえる。\n"
    "スポーツを 考えれば わかりやすい。サッカーには 手を 使っては "
    "いけないという 規則が ある。一見 不自由に 見えるが、"
    "その 制限が あるからこそ、足だけで ボールを あつかう 技術が 生まれ、"
    "見る者を おどろかせる 場面が 生まれる。規則を すべて 取りはらえば、"
    "自由が 増えるのではなく、競技そのものが 成り立たなくなる。\n"
    "教室の 規則も 同じである。「人の 話を さえぎらない」という 一つの "
    "約束が あるだけで、口数の 少ない 人も 発言できるようになる。"
    "規則が 守っているのは、多数派の 都合ではなく、"
    "放っておけば 声を 出せない 側の 自由である。\n"
    "だから 規則を 見るときは、「何を 禁じているか」より "
    "「何を 可能に しているか」を たずねたほうが よい。"
    "可能に しているものが 何も 見あたらない 規則は、"
    "そのときこそ 見直されるべきである。")

BUN["ko-j3-kioku"] = (
    "記憶は 録画では ない。私たちは 思い出すたびに、記憶を 作り直している。"
    "脳は 出来事を そのまま しまっておくのではなく、"
    "断片を 手がかりに、そのつど 組み立て直す。\n"
    "この しくみには 利点が ある。すべてを そのまま 保存するには "
    "膨大な 容量が 必要になるし、状況が 変われば 意味も 変わる。"
    "組み立て直す 方式なら、新しく 知ったことを 過去の 経験に "
    "結びつけ直すことが できる。学ぶという ことは、"
    "本来 この 作り直しの ことである。\n"
    "一方で、この しくみは あやうさも かかえている。"
    "作り直すたびに、そのときの 気分や、あとから 聞いた 話が "
    "まぎれこむ。何度も 語られた 思い出ほど、"
    "語り手にとっては 鮮明になり、事実からは 遠ざかっていく ことが ある。\n"
    "だから 同じ 出来事の 記憶が、人によって 食いちがうのは "
    "異常では ない。どちらかが うそを ついていると 決めつける 前に、"
    "二人が それぞれ 別の 組み立てを したのだと 考えたほうが、"
    "たいていの 場合 事実に 近い。")

BUN["en-e6-park"] = (
    "Our town has a small park near the station. It is not very big, "
    "but many people go there every day.\n"
    "In the morning, old people walk around the pond. At noon, "
    "office workers eat lunch under the big tree. After school, "
    "children play football on the grass.\n"
    "Last year the town wanted to build a car park there. "
    "Many people wrote letters to the town office. They said the park "
    "was more important than a car park. In the end, the town kept "
    "the park and built the car park behind the station.")

BUN["en-j1-lunch"] = (
    "In Japan, most students eat lunch in their classroom. "
    "The food comes from a school kitchen, and the students carry it "
    "from the kitchen to the classroom themselves. They wear white "
    "coats and caps when they do this.\n"
    "After lunch, the students clean the classroom. In many countries "
    "this is done by cleaners, so foreign visitors are often surprised.\n"
    "Teachers say that carrying the food and cleaning the room are "
    "part of the lessons. Students learn to work together and to take "
    "care of the place they use every day.")

BUN["en-j2-plastic"] = (
    "Plastic is cheap, light and strong. That is why we use it for "
    "almost everything. But the same qualities cause a problem: "
    "plastic does not disappear.\n"
    "When plastic is thrown into the sea, waves and sunlight break it "
    "into very small pieces. These pieces are too small to collect, "
    "and fish eat them by mistake. In the end, some of the pieces "
    "may come back to our own tables.\n"
    "Some towns have started to act. Shops no longer give free bags, "
    "and drinks are sold in paper cups. In one town, the amount of "
    "plastic waste fell by twenty per cent in a single year. "
    "The change was small, but it showed that something can be done.")

BUN["en-j3-sleep"] = (
    "Many students believe that studying late at night is a sign of "
    "effort. Research suggests the opposite. While we sleep, the brain "
    "sorts what we have learned during the day and stores the parts "
    "that matter. If we cut our sleep, that work cannot be finished.\n"
    "In one study, two groups learned the same list of words. "
    "One group slept for eight hours; the other stayed awake and "
    "studied for two more hours. The next morning, the group that had "
    "slept remembered more words, although they had studied less.\n"
    "This does not mean that sleeping alone will teach us anything. "
    "The brain can only sort what has already been put in. "
    "Study and sleep are not enemies; they are two halves of the same "
    "process, and neither works well without the other.")


# ==================================================================
# 設問。 (本文, 問題文, 正解, 誤答3つ, ひとこと, 単元, 教科, 帯)
# ==================================================================
QUESTIONS = [
 ("ko-e4-ari", "アリが 同じ 道を 通れるのは なぜですか。",
  "通った道に においを つけているから",
  ("目が とても よいから", "先生が 教えたから", "地図を 持っているから"),
  "第二段落に 書いてある。", "長文を読む", "japanese", "小4"),
 ("ko-e4-ari", "アリが 頭を 合わせているのは 何のためだと 書かれていますか。",
  "においや 食べ物の ことを 知らせ合うため",
  ("あいさつを するため", "けんかを するため", "休むため"),
  "「まるで あいさつを しているようだ」は 見た目の たとえ。",
  "長文を読む", "japanese", "小4"),
 ("ko-e4-ari", "さいごの 段落で ぼくが 立ち止まったのは なぜですか。",
  "アリのように においで 帰れるかと 思ったから",
  ("道に まよったから", "アリを さがしたから", "つかれたから"),
  "直前の アリの 話と つないで 読む。", "長文を読む", "japanese", "小4"),

 ("ko-e5-mori", "森に ふった 雨は、すぐには どうならないと 書かれていますか。",
  "川へ 流れこまない",
  ("土に しみこまない", "空へ もどらない", "海へ 出ない"),
  "第一段落の 一文目。", "長文を読む", "japanese", "小5"),
 ("ko-e5-mori", "森が 「緑の ダム」と よばれるのは なぜですか。",
  "水を たくわえて 少しずつ 流すから",
  ("木が ダムの 材料に なるから", "川の 近くに あるから",
   "水を きれいに するから"),
  "第二段落。ダムと 同じ はたらきを している。", "長文を読む", "japanese", "小5"),
 ("ko-e5-mori", "木を 切りすぎると 起こることとして、書かれていないのは どれですか。",
  "海の 水が 減る",
  ("川が にごる", "こう水が 起こりやすくなる", "水が 足りなくなる"),
  "**書かれていないもの**を選ぶ問い。第三段落を たしかめる。",
  "長文を読む", "japanese", "小5"),

 ("ko-e6-chizu", "地図で 四つ すべてを 正しく 表せないのは なぜですか。",
  "丸い地球を 平らな紙に うつすから",
  ("紙が 小さいから", "地球が 大きいから", "測る 技術が 足りないから"),
  "第一段落。原理として つくれない、と ある。", "長文を読む", "japanese", "小6"),
 ("ko-e6-chizu", "航海に 使われてきた 地図の 特ちょうは どれですか。",
  "方位が 正しいが 高緯度が 大きく なる",
  ("面積が 正しいが 形が つぶれる", "きょりが すべて 正しい",
   "四つとも 正しい"),
  "第二段落の 前半。", "長文を読む", "japanese", "小6"),
 ("ko-e6-chizu", "筆者が 考える 「地図を 読む力」とは どんな 力ですか。",
  "えがかれていないものに 気づく力",
  ("記号を 覚える力", "方位を 正しく 測る力", "地図を 早く 見る力"),
  "最終文。", "長文を読む", "japanese", "小6"),

 ("ko-j1-jisho", "辞書が 書きかえられるのは なぜですか。",
  "人々が 使う 意味が 変わるから",
  ("まちがいが 多いから", "紙が いたむから", "出版社の 都合だから"),
  "第一段落。辞書は あとから 書きとめるもの。", "長文を読む", "japanese", "中1"),
 ("ko-j1-jisho", "地図の たとえで 筆者が 言いたいのは どれですか。",
  "実際の 使い方が 先で、辞書は あとから ついてくる",
  ("地図は 正確でない", "辞書は 必要ない", "道は 地図で 決まる"),
  "「道が 先に あり」と 言いかえてある。", "長文を読む", "japanese", "中1"),
 ("ko-j1-jisho", "筆者が 「何でも 好きに 使ってよい わけではない」と 言うのは "
  "なぜですか。",
  "多くの人と 共有されていない 使い方は 通じないから",
  ("辞書に 反するから", "正しい 日本語が あるから", "先生に しかられるから"),
  "第三段落。「言葉は 通じてはじめて 言葉」。", "長文を読む", "japanese", "中1"),

 ("ko-j2-kisoku", "筆者は 規則を どのようなものだと 考えていますか。",
  "内側での 自由を 可能に するもの",
  ("人を しばるもの", "多数派に 都合の よいもの", "無いほうが よいもの"),
  "第一段落と 最終段落。", "長文を読む", "japanese", "中2"),
 ("ko-j2-kisoku", "サッカーの 例は 何を 示すために 出されていますか。",
  "制限が あるからこそ 技術が 生まれること",
  ("スポーツが 楽しいこと", "手を 使うと 危ないこと",
   "規則は 減らすべきこと"),
  "例は 直前の 主張を 支えるために ある。", "長文を読む", "japanese", "中2"),
 ("ko-j2-kisoku", "「人の 話を さえぎらない」という 例で、規則が 守っているのは "
  "だれの 自由ですか。",
  "放っておけば 声を 出せない 側の自由",
  ("多数派の 自由", "先生の 自由", "話が 長い人の 自由"),
  "第三段落の 最後。", "長文を読む", "japanese", "中2"),
 ("ko-j2-kisoku", "筆者が すすめる 規則の 見方は どれですか。",
  "何を 可能に しているかを たずねる",
  ("何を 禁じているかを 数える", "だれが 作ったかを 調べる",
   "守る人の 数を 見る"),
  "最終段落。", "長文を読む", "japanese", "中2"),

 ("ko-j3-kioku", "筆者は 記憶を どのようなものだと 述べていますか。",
  "思い出すたびに 組み立て直されるもの",
  ("そのまま 保存されるもの", "時間とともに 消えるだけのもの",
   "録画のように 再生できるもの"),
  "第一段落。", "長文を読む", "japanese", "中3"),
 ("ko-j3-kioku", "作り直す しくみの 利点として 挙げられているのは どれですか。",
  "新しい 知識を 過去の 経験に 結びつけ直せること",
  ("忘れなくなること", "記憶が 正確になること", "思い出すのが 速くなること"),
  "第二段落。「学ぶ」と つないである。", "長文を読む", "japanese", "中3"),
 ("ko-j3-kioku", "「何度も 語られた 思い出ほど」の あとに 続く 内容は どれですか。",
  "鮮明になる 一方で 事実から 遠ざかること",
  ("正確になること", "忘れられること", "短くなること"),
  "第三段落。利点の 裏返しとして 書かれている。", "長文を読む", "japanese", "中3"),
 ("ko-j3-kioku", "記憶が 人によって 食いちがうとき、筆者は どう 考えるべきだと "
  "述べていますか。",
  "それぞれが 別の 組み立てを したと 考える",
  ("どちらかが うそを ついている", "どちらも まちがっている",
   "記録を 見れば 解決する"),
  "最終段落。", "長文を読む", "japanese", "中3"),

 ("en-e6-park", "Who walks around the pond in the morning?",
  "Old people.", ("Office workers.", "Children.", "Teachers."),
  "第二段落の1文目。", "長文を読む", "english", "小6"),
 ("en-e6-park", "Why did people write letters to the town office?",
  "Because they wanted to keep the park.",
  ("Because they wanted a car park.", "Because the park was too big.",
   "Because the station was far."),
  "第三段落。", "長文を読む", "english", "小6"),
 ("en-e6-park", "Where was the car park built in the end?",
  "Behind the station.", ("In the park.", "Near the pond.",
                          "It was not built."),
  "最終文。", "長文を読む", "english", "小6"),

 ("en-j1-lunch", "Who carries the food to the classroom?",
  "The students.", ("The teachers.", "The cooks.", "The visitors."),
  "第一段落。themselves が手がかり。", "長文を読む", "english", "中1"),
 ("en-j1-lunch", "Why are foreign visitors often surprised?",
  "Because students clean the classroom themselves.",
  ("Because the food is free.", "Because lunch is very long.",
   "Because students wear white coats."),
  "第二段落。", "長文を読む", "english", "中1"),
 ("en-j1-lunch", "What do teachers say about lunch and cleaning?",
  "They are part of the lessons.",
  ("They take too much time.", "They should be done by cleaners.",
   "They are not important."),
  "最終段落。", "長文を読む", "english", "中1"),

 ("en-j2-plastic", "What makes plastic useful and also a problem?",
  "It is strong and does not disappear.",
  ("It is expensive.", "It is heavy.", "It melts easily."),
  "第一段落。同じ性質が両方の理由になっている。", "長文を読む", "english", "中2"),
 ("en-j2-plastic", "Why do fish eat plastic?",
  "Because the pieces are very small.",
  ("Because plastic smells good.", "Because there is no other food.",
   "Because people feed them."),
  "第二段落。", "長文を読む", "english", "中2"),
 ("en-j2-plastic", "What happened in one town?",
  "Plastic waste fell by twenty per cent in a year.",
  ("Shops closed.", "Plastic waste doubled.", "Nothing changed."),
  "最終段落。", "長文を読む", "english", "中2"),
 ("en-j2-plastic", "What does the writer think about the change?",
  "It was small but showed that action is possible.",
  ("It was enough to solve the problem.", "It was useless.",
   "It was too expensive."),
  "最終文。", "長文を読む", "english", "中2"),

 ("en-j3-sleep", "What does the brain do while we sleep?",
  "It sorts and stores what we have learned.",
  ("It forgets everything.", "It studies new words.",
   "It stops working completely."),
  "第一段落。", "長文を読む", "english", "中3"),
 ("en-j3-sleep", "Which group remembered more words?",
  "The group that slept for eight hours.",
  ("The group that studied two more hours.", "Both groups equally.",
   "Neither group."),
  "第二段落。although が手がかり。", "長文を読む", "english", "中3"),
 ("en-j3-sleep", "What does the writer say about sleeping alone?",
  "It cannot teach us anything by itself.",
  ("It is better than studying.", "It is a waste of time.",
   "It replaces study."),
  "最終段落。", "長文を読む", "english", "中3"),
 ("en-j3-sleep", "What is the writer's main point?",
  "Study and sleep must go together.",
  ("Students should study late at night.", "Sleep is more important than study.",
   "Research is often wrong."),
  "最終文。", "長文を読む", "english", "中3"),
]


def esc(s):
    return (s.replace("\\", "\\\\").replace('"', '\\"')
             .replace("\r", " ").replace("\n", "\\n"))


def main():
    used = {q[0] for q in QUESTIONS}
    unknown = used - set(BUN)
    if unknown:
        raise ValueError("知らない本文を指しています: %s" % sorted(unknown))
    idle = set(BUN) - used
    if idle:
        raise ValueError("どの設問からも使われていない本文: %s" % sorted(idle))

    out = ["""/* 長文読解の本文。

   **このファイルは app/tools/gen_choubun.py が書き出したもの。**
   手で直さないこと。直すなら生成側を直して作り直す。

   本文は共有する。設問は教材の8列目で名前を指す。
   1問ごとに本文を抱えさせると、同じ600字が紙に何度も並ぶ。
   改行は \\n。画面と紙で段落に直して出す。 */
(function(global){
"use strict";
global.TubeReadings = {"""]
    for name in sorted(BUN):
        out.append('"%s":"%s",' % (name, esc(BUN[name])))
    out.append("};\n})(window);\n")
    path = os.path.join(CONTENT, "readings.js")
    io.open(path, "w", encoding="utf-8").write("\n".join(out))

    packs, built = {}, []
    for bun, q, ok, wrong, note, unit, subject, band in QUESTIONS:
        key = (subject, band)
        if key not in packs:
            packs[key] = Pack(
                "%s/cho-%s" % (subject, BAND_CODE[band]), subject,
                "長文読解 %s" % band, [band],
                "長文を読んで答える。本文は content/readings.js",
                english=(subject == "english"))
        packs[key].Q(q, ok, list(wrong), band, note, unit=unit, bun=bun)
    for key in sorted(packs):
        built.append(packs[key].write())
    report(built)
    n = sum(len(v) for v in BUN.values())
    print("\n  本文 %d本（合計 %d字）→ app/content/readings.js（%.1fKB）"
          % (len(BUN), n, os.path.getsize(path) / 1024.0))
    print("  1本あたり 平均 %d字" % (n / len(BUN)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
