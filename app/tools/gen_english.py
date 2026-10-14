#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""英語 ―― 学年別の教材（小5〜中3）。

    python3 app/tools/gen_english.py

なぜ作り直すか
--------------
これまで英語は english/core 1つだけで、小5から中3まで**全学年が
まったく同じ1,134項目**を見ていた。しかも中身は前身プロジェクト
（IELTS の B2〜C1）の語彙で、小5に "accommodation" が出ていた。

さらに深刻だったのは、core の項目に**単元が付いていない**こと。
単元が空だと examprep.in_scope が絞れないので、

  ・5週ごとの単元確認テスト対策で、英語だけ範囲が効かない
  ・苦手単元の再テストに、英語だけ一度も出てこない

という穴が開いていた。**落ちないので気づけない**穴である。
ここで作る教材はすべて単元付きにする。

4つの形
-------
本人の指示は「EN→JA と JA→EN の両方／英語で書かれた4択／短い読解文」。
そのまま4つの形で作る。

  1. T  英→日   afford  →「〜する余裕がある」（読んで意味が分かる）
  2. Q  日→英  「借りる」を英語で書くと？ → borrow（書ける・言える）
  3. Q  英語の設問  I ___ to school every day. → go / goes / going / went
        **設問そのものを英語で書く。** 日本語で「正しいものを選べ」と
        書いてしまうと、日本語を読む練習にしかならない。
  4. Q  短文読解  2〜3文＋設問1つ。

読解を**1問ずつ完結**させているのは、忘却曲線が項目ごとに独立して
いるためである。1つの文章に5問ぶら下げると、そのうち1問だけが
「今日出る」日に、文章が読めない問題だけが画面に出る。

単元の名前
----------
中学校の教科書の並び（be動詞・一般動詞・過去形…）に合わせる。
講師が授業計画に書く単元名と一致していないと、
「今週やった所」で絞れない。

典拠
----
英語の語・文法規則は事実であり、事実に著作権はない。
**例文・設問・誤答・解説・読解文はすべてここで書き下ろしている。**
市販教材からの転記はない（CLAUDE.md 絶対に守ること 6）。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_content import Pack, report          # noqa: E402


BAND_CODE = {"小5": "e5", "小6": "e6", "中1": "j1", "中2": "j2", "中3": "j3"}


# ==================================================================
# 1. 英→日（T）。 [単語, 品詞, 意味, ひとこと, 例文, 例文の訳]
#
# 品詞を出すのは、run（走る／経営する）のように品詞で意味が変わる語が
# あるため。ひとことには、日本語話者がつまずく所だけを書く。
# ==================================================================
WORDS = {
"小5": [
 ("apple", "n", "りんご", "", "I eat an apple every morning.", "毎朝りんごを1つ食べる。"),
 ("book", "n", "本", "", "This book is very old.", "この本はとても古い。"),
 ("school", "n", "学校", "", "Our school is near the station.", "私たちの学校は駅の近くだ。"),
 ("teacher", "n", "先生", "", "She is a music teacher.", "彼女は音楽の先生だ。"),
 ("friend", "n", "友だち", "", "Tom is my best friend.", "トムは私の親友だ。"),
 ("family", "n", "家族", "", "My family has four people.", "私の家族は4人だ。"),
 ("water", "n", "水", "数えられないので a water とは言わない。",
  "Please give me some water.", "水をください。"),
 ("dog", "n", "犬", "", "The dog is sleeping.", "その犬は眠っている。"),
 ("cat", "n", "ねこ", "", "My cat likes fish.", "うちのねこは魚が好きだ。"),
 ("bird", "n", "鳥", "", "A bird is singing.", "鳥が鳴いている。"),
 ("red", "adj", "赤い", "", "I have a red bag.", "私は赤いかばんを持っている。"),
 ("blue", "adj", "青い", "", "The sky is blue today.", "今日は空が青い。"),
 ("big", "adj", "大きい", "", "That is a big house.", "あれは大きな家だ。"),
 ("small", "adj", "小さい", "", "I have a small dog.", "私は小さな犬を飼っている。"),
 ("new", "adj", "新しい", "", "This is my new bike.", "これは私の新しい自転車だ。"),
 ("old", "adj", "古い、年をとった", "", "My grandfather is old.", "祖父は年をとっている。"),
 ("happy", "adj", "うれしい、幸せな", "", "I am happy today.", "今日はうれしい。"),
 ("go", "v", "行く", "", "I go to school at eight.", "私は8時に学校へ行く。"),
 ("come", "v", "来る", "go は話し手から離れる、come は近づく。",
  "Please come to my house.", "私の家に来てください。"),
 ("eat", "v", "食べる", "", "We eat lunch at noon.", "私たちは正午に昼食を食べる。"),
 ("drink", "v", "飲む", "", "I drink milk every day.", "私は毎日牛乳を飲む。"),
 ("run", "v", "走る", "", "He can run fast.", "彼は速く走れる。"),
 ("play", "v", "（スポーツを）する、遊ぶ", "楽器には the が付く（play the piano）。",
  "They play soccer after school.", "彼らは放課後サッカーをする。"),
 ("study", "v", "勉強する", "", "I study English every day.", "私は毎日英語を勉強する。"),
 ("like", "v", "好きだ", "", "I like music.", "私は音楽が好きだ。"),
 ("have", "v", "持っている", "", "I have two brothers.", "私には兄弟が2人いる。"),
 ("see", "v", "見える、会う", "", "I can see the sea.", "海が見える。"),
 ("read", "v", "読む", "過去形も read（発音だけ変わる）。",
  "She reads a book at night.", "彼女は夜に本を読む。"),
 ("write", "v", "書く", "", "Write your name here.", "ここに名前を書いてください。"),
 ("Monday", "n", "月曜日", "曜日はいつも大文字で始める。",
  "We have music on Monday.", "月曜日には音楽がある。"),
 ("morning", "n", "朝、午前", "", "I get up early in the morning.", "私は朝早く起きる。"),
 ("night", "n", "夜", "", "I read at night.", "私は夜に本を読む。"),
 ("one", "n", "1", "", "I have one sister.", "私には姉が1人いる。"),
 ("three", "n", "3", "", "There are three apples.", "りんごが3つある。"),
 ("many", "adj", "たくさんの", "数えられる名詞に使う。much は数えられない名詞。",
  "There are many books here.", "ここには本がたくさんある。"),
 ("very", "adv", "とても", "", "This cake is very good.", "このケーキはとてもおいしい。"),
 ("here", "adv", "ここに", "", "Come here, please.", "こちらへ来てください。"),
 ("today", "adv", "今日", "", "It is cold today.", "今日は寒い。"),
 ("and", "conj", "そして、と", "", "I like cats and dogs.", "私はねこと犬が好きだ。"),
 ("but", "conj", "しかし", "", "I am tired but happy.", "疲れているがうれしい。"),
],
"小6": [
 ("breakfast", "n", "朝食", "食事名に the は付けない（have breakfast）。",
  "I have breakfast at seven.", "私は7時に朝食をとる。"),
 ("station", "n", "駅", "", "The station is over there.", "駅は向こうにある。"),
 ("hospital", "n", "病院", "", "My mother works at a hospital.", "母は病院で働いている。"),
 ("library", "n", "図書館", "", "We study at the library.", "私たちは図書館で勉強する。"),
 ("country", "n", "国", "複数形は countries（y を i に）。",
  "Japan is a beautiful country.", "日本は美しい国だ。"),
 ("city", "n", "都市", "", "London is a big city.", "ロンドンは大きな都市だ。"),
 ("season", "n", "季節", "", "Spring is my favourite season.", "春は私の好きな季節だ。"),
 ("weather", "n", "天気", "数えられない。a weather とは言わない。",
  "The weather is nice today.", "今日は天気がよい。"),
 ("dream", "n", "夢", "", "My dream is to be a doctor.", "私の夢は医者になることだ。"),
 ("subject", "n", "教科", "", "My favourite subject is science.", "私の好きな教科は理科だ。"),
 ("beautiful", "adj", "美しい", "", "That flower is beautiful.", "あの花は美しい。"),
 ("famous", "adj", "有名な", "", "He is a famous singer.", "彼は有名な歌手だ。"),
 ("difficult", "adj", "むずかしい", "", "This question is difficult.", "この問題はむずかしい。"),
 ("easy", "adj", "やさしい、簡単な", "", "The test was easy.", "そのテストは簡単だった。"),
 ("busy", "adj", "いそがしい", "", "My father is busy today.", "父は今日いそがしい。"),
 ("kind", "adj", "親切な", "名詞では「種類」。",
  "She is kind to everyone.", "彼女はだれにでも親切だ。"),
 ("enjoy", "v", "楽しむ", "後ろは -ing。enjoy to play とは言わない。",
  "We enjoy playing tennis.", "私たちはテニスを楽しむ。"),
 ("visit", "v", "訪れる", "", "I visit my aunt every summer.", "私は毎年夏におばを訪ねる。"),
 ("help", "v", "手伝う、助ける", "", "Can you help me?", "手伝ってくれますか。"),
 ("make", "v", "作る", "", "She makes cakes on Sunday.", "彼女は日曜日にケーキを作る。"),
 ("want", "v", "ほしい", "want to do で「〜したい」。",
  "I want a new bag.", "私は新しいかばんがほしい。"),
 ("need", "v", "必要とする", "", "We need more time.", "もっと時間が必要だ。"),
 ("start", "v", "始める、始まる", "", "The class starts at nine.", "授業は9時に始まる。"),
 ("finish", "v", "終える", "後ろは -ing。",
  "I finished reading the book.", "私はその本を読み終えた。"),
 ("live", "v", "住む", "住む場所には in を使う。",
  "They live in Osaka.", "彼らは大阪に住んでいる。"),
 ("know", "v", "知っている", "進行形にしない。",
  "I know his name.", "私は彼の名前を知っている。"),
 ("think", "v", "思う、考える", "", "I think it is true.", "私はそれは本当だと思う。"),
 ("understand", "v", "理解する", "", "I understand your idea.", "あなたの考えは分かる。"),
 ("always", "adv", "いつも", "be動詞の後、一般動詞の前に置く。",
  "He is always late.", "彼はいつも遅刻する。"),
 ("sometimes", "adv", "ときどき", "", "I sometimes walk to school.", "私はときどき歩いて学校へ行く。"),
 ("never", "adv", "一度も〜ない", "それだけで否定になる。not を重ねない。",
  "She never eats meat.", "彼女は肉を一切食べない。"),
 ("together", "adv", "いっしょに", "", "Let us sing together.", "いっしょに歌おう。"),
 ("because", "conj", "なぜなら", "", "I stayed home because it rained.", "雨が降ったので家にいた。"),
 ("before", "prep", "〜の前に", "", "Wash your hands before lunch.", "昼食の前に手を洗いなさい。"),
 ("after", "prep", "〜のあとに", "", "We play after school.", "私たちは放課後に遊ぶ。"),
 ("between", "prep", "〜の間に", "2つのものの間。3つ以上は among。",
  "The shop is between the bank and the park.", "店は銀行と公園の間にある。"),
],
"中1": [
 ("answer", "n", "答え", "動詞では「答える」。前置詞は要らない。",
  "Your answer is correct.", "あなたの答えは正しい。"),
 ("question", "n", "質問", "", "May I ask a question?", "質問してもいいですか。"),
 ("world", "n", "世界", "", "He wants to travel around the world.", "彼は世界中を旅したい。"),
 ("problem", "n", "問題、困ったこと", "試験の問題は question。",
  "We solved the problem.", "私たちはその問題を解決した。"),
 ("idea", "n", "考え、思いつき", "", "That is a good idea.", "それはよい考えだ。"),
 ("place", "n", "場所", "", "This is a quiet place.", "ここは静かな場所だ。"),
 ("future", "n", "未来", "", "Think about your future.", "自分の将来を考えなさい。"),
 ("language", "n", "言語", "", "English is a world language.", "英語は世界の言語だ。"),
 ("member", "n", "一員、部員", "", "I am a member of the tennis club.", "私はテニス部の部員だ。"),
 ("holiday", "n", "休日", "", "We have a holiday tomorrow.", "明日は休日だ。"),
 ("careful", "adj", "注意深い", "be careful of で「〜に気をつける」。",
  "Be careful with the knife.", "ナイフに気をつけて。"),
 ("different", "adj", "ちがう", "比べる相手には from を使う。",
  "My idea is different from yours.", "私の考えはあなたのとちがう。"),
 ("important", "adj", "大切な", "", "Sleep is important for children.", "睡眠は子どもに大切だ。"),
 ("interesting", "adj", "おもしろい", "人が「興味がある」は interested。",
  "This story is interesting.", "この話はおもしろい。"),
 ("quiet", "adj", "静かな", "", "Please be quiet in the library.", "図書館では静かにしてください。"),
 ("ready", "adj", "用意ができた", "", "Are you ready to go?", "行く準備はできましたか。"),
 ("bring", "v", "持ってくる", "take は持っていく。方向が逆。",
  "Bring your notebook tomorrow.", "明日ノートを持ってきなさい。"),
 ("take", "v", "取る、（時間が）かかる", "",
  "It takes ten minutes by bus.", "バスで10分かかる。"),
 ("choose", "v", "選ぶ", "過去形は chose。",
  "Choose one from these three.", "この3つから1つ選びなさい。"),
 ("stay", "v", "とどまる、泊まる", "", "I stayed at my uncle's house.", "私はおじの家に泊まった。"),
 ("wait", "v", "待つ", "待つ相手には for。wait me とは言わない。",
  "Wait for me at the gate.", "門のところで待っていて。"),
 ("arrive", "v", "着く", "大きな場所には in、狭い場所には at。",
  "We arrived at the station at six.", "私たちは6時に駅に着いた。"),
 ("belong", "v", "所属する", "belong to の形で使う。進行形にしない。",
  "I belong to the brass band.", "私は吹奏楽部に入っている。"),
 ("borrow", "v", "借りる", "lend は貸す。逆にしない。",
  "May I borrow your pen?", "ペンを借りてもいいですか。"),
 ("carry", "v", "運ぶ", "", "He carried the heavy box.", "彼は重い箱を運んだ。"),
 ("decide", "v", "決める", "後ろは to do。",
  "She decided to study abroad.", "彼女は留学することを決めた。"),
 ("explain", "v", "説明する", "説明する相手には to。explain me とは言わない。",
  "Please explain this to me.", "これを私に説明してください。"),
 ("invite", "v", "招く", "", "They invited us to the party.", "彼らは私たちをパーティーに招いた。"),
 ("practise", "v", "練習する", "英国式の綴り。米国式は practice。",
  "We practise the piano every day.", "私たちは毎日ピアノを練習する。"),
 ("remember", "v", "思い出す、覚えている", "",
  "I remember his face.", "私は彼の顔を覚えている。"),
 ("almost", "adv", "ほとんど", "", "It is almost seven.", "もうすぐ7時だ。"),
 ("early", "adv", "早く", "時刻が早い。速さが速いのは fast。",
  "He gets up early.", "彼は早く起きる。"),
 ("enough", "adv", "十分に", "形容詞の**後ろ**に置く（old enough）。",
  "This room is big enough.", "この部屋は十分に広い。"),
 ("perhaps", "adv", "たぶん", "", "Perhaps she is at home.", "たぶん彼女は家にいる。"),
 ("during", "prep", "〜の間ずっと", "後ろは名詞。while の後ろは文。",
  "I read three books during the holiday.", "休みの間に3冊読んだ。"),
 ("without", "prep", "〜なしで", "", "He left without a word.", "彼は何も言わずに去った。"),
],
"中2": [
 ("chance", "n", "機会", "", "This is a good chance for you.", "これは君にとってよい機会だ。"),
 ("choice", "n", "選択", "動詞は choose。",
  "You have two choices.", "選択肢は2つある。"),
 ("difference", "n", "ちがい", "", "There is no difference between them.", "その2つに違いはない。"),
 ("experience", "n", "経験", "", "She has a lot of experience.", "彼女は経験が豊富だ。"),
 ("opinion", "n", "意見", "in my opinion で「私の考えでは」。",
  "Tell me your opinion.", "あなたの意見を聞かせて。"),
 ("reason", "n", "理由", "", "Tell me the reason for your absence.", "欠席の理由を教えて。"),
 ("result", "n", "結果", "", "The result was better than we expected.", "結果は予想よりよかった。"),
 ("society", "n", "社会", "", "Society is changing quickly.", "社会は急速に変わっている。"),
 ("environment", "n", "環境", "the をつけて使うことが多い。",
  "We must protect the environment.", "私たちは環境を守らなければならない。"),
 ("technology", "n", "科学技術", "", "Technology changes our lives.", "科学技術は生活を変える。"),
 ("common", "adj", "共通の、よくある", "",
  "This is a common mistake.", "これはよくあるまちがいだ。"),
 ("dangerous", "adj", "危険な", "", "Swimming here is dangerous.", "ここで泳ぐのは危険だ。"),
 ("expensive", "adj", "高価な", "値段が高いのは high price ではなく expensive。",
  "This watch is too expensive.", "この時計は高すぎる。"),
 ("foreign", "adj", "外国の", "g は発音しない。",
  "He studies a foreign language.", "彼は外国語を勉強している。"),
 ("necessary", "adj", "必要な", "",
  "It is necessary to book a seat.", "座席を予約する必要がある。"),
 ("possible", "adj", "可能な", "反対は impossible。",
  "Is it possible to change the date?", "日付を変えることは可能ですか。"),
 ("similar", "adj", "似ている", "似ている相手には to。",
  "Your bag is similar to mine.", "君のかばんは私のと似ている。"),
 ("useful", "adj", "役に立つ", "", "This map is very useful.", "この地図はとても役に立つ。"),
 ("agree", "v", "同意する", "同意する相手には with。",
  "I agree with you.", "私はあなたに賛成だ。"),
 ("appear", "v", "現れる、〜に見える", "",
  "A rainbow appeared in the sky.", "空に虹が現れた。"),
 ("continue", "v", "続ける", "", "He continued to speak.", "彼は話し続けた。"),
 ("depend", "v", "たよる、次第だ", "depend on の形で使う。",
  "It depends on the weather.", "それは天気次第だ。"),
 ("develop", "v", "発展させる、成長する", "",
  "The town developed quickly.", "その町は急速に発展した。"),
 ("expect", "v", "予期する", "「期待する」より「〜だろうと思う」。",
  "I expect he will come.", "彼は来るだろうと思う。"),
 ("improve", "v", "上達する、改善する", "",
  "My English improved a lot.", "私の英語はとても上達した。"),
 ("increase", "v", "増える、増やす", "反対は decrease。",
  "The number of visitors increased.", "訪問者の数が増えた。"),
 ("prepare", "v", "準備する", "prepare for で「〜に備える」。",
  "We prepared for the exam.", "私たちは試験の準備をした。"),
 ("realise", "v", "気づく", "英国式の綴り。米国式は realize。",
  "I realised my mistake.", "私は自分のまちがいに気づいた。"),
 ("succeed", "v", "成功する", "名詞は success。",
  "She succeeded in the test.", "彼女はテストで成功した。"),
 ("suggest", "v", "提案する", "後ろは -ing か that の文。to do は使わない。",
  "He suggested going by train.", "彼は電車で行こうと提案した。"),
 ("clearly", "adv", "はっきりと", "", "Please speak clearly.", "はっきり話してください。"),
 ("finally", "adv", "ついに、最後に", "", "Finally we reached the top.", "ついに頂上に着いた。"),
 ("probably", "adv", "おそらく", "perhaps より確からしい。",
  "He will probably win.", "彼はおそらく勝つだろう。"),
 ("suddenly", "adv", "突然", "", "Suddenly the light went out.", "突然明かりが消えた。"),
 ("although", "conj", "〜だけれども", "but と同時には使わない。",
  "Although it rained, we went out.", "雨が降ったけれど出かけた。"),
 ("while", "conj", "〜する間に", "後ろは文。during の後ろは名詞。",
  "He called while I was cooking.", "料理をしている間に彼が電話してきた。"),
],
"中3": [
 ("ability", "n", "能力", "形容詞は able。",
  "She has the ability to lead others.", "彼女には人を導く力がある。"),
 ("advantage", "n", "利点", "反対は disadvantage。",
  "Living here has many advantages.", "ここに住むには多くの利点がある。"),
 ("condition", "n", "状態、条件", "",
  "The road is in bad condition.", "その道は状態が悪い。"),
 ("effect", "n", "影響、効果", "動詞の affect と混同しない。",
  "The effect was greater than expected.", "影響は予想より大きかった。"),
 ("evidence", "n", "証拠", "数えられない。an evidence とは言わない。",
  "There is no evidence for that.", "それを裏づける証拠はない。"),
 ("purpose", "n", "目的", "on purpose で「わざと」。",
  "What is the purpose of this rule?", "この規則の目的は何ですか。"),
 ("research", "n", "研究、調査", "数えられない。researches とはあまり言わない。",
  "He is doing research on plants.", "彼は植物の研究をしている。"),
 ("solution", "n", "解決策", "動詞は solve。",
  "We are looking for a solution.", "私たちは解決策をさがしている。"),
 ("source", "n", "源、出どころ", "",
  "The sun is a source of energy.", "太陽はエネルギーの源だ。"),
 ("value", "n", "価値", "", "This old coin has great value.", "この古い硬貨には大きな価値がある。"),
 ("available", "adj", "利用できる、手に入る", "",
  "The book is available at the library.", "その本は図書館で借りられる。"),
 ("certain", "adj", "確かな、ある〜", "",
  "I am certain that he is right.", "彼が正しいと確信している。"),
 ("efficient", "adj", "効率のよい", "",
  "This is an efficient way to study.", "これは効率のよい勉強法だ。"),
 ("obvious", "adj", "明らかな", "", "The answer is obvious.", "答えは明らかだ。"),
 ("particular", "adj", "特定の、とくべつの", "in particular で「とくに」。",
  "Do you have a particular reason?", "特別な理由があるのですか。"),
 ("reliable", "adj", "信頼できる", "動詞は rely。",
  "He is a reliable friend.", "彼は信頼できる友人だ。"),
 ("significant", "adj", "重要な、著しい", "",
  "There was a significant change.", "著しい変化があった。"),
 ("sufficient", "adj", "十分な", "enough よりかたい語。",
  "We have sufficient food for a week.", "1週間分の十分な食料がある。"),
 ("achieve", "v", "達成する", "名詞は achievement。",
  "She achieved her goal.", "彼女は目標を達成した。"),
 ("affect", "v", "影響を与える", "名詞の effect と混同しない。to は要らない。",
  "The rain affected the game.", "雨が試合に影響した。"),
 ("avoid", "v", "避ける", "後ろは -ing。avoid to do は誤り。",
  "Avoid using long sentences.", "長い文を使うのは避けなさい。"),
 ("consider", "v", "よく考える", "後ろは -ing。",
  "We are considering moving to York.", "ヨークへ引っ越すことを考えている。"),
 ("contain", "v", "含む", "進行形にしない。",
  "This drink contains sugar.", "この飲み物には砂糖が含まれる。"),
 ("describe", "v", "描写する、説明する", "describe me it とは言わない。",
  "Describe the picture to your partner.", "その絵を相手に説明しなさい。"),
 ("establish", "v", "設立する、確立する", "",
  "The school was established in 1890.", "その学校は1890年に設立された。"),
 ("maintain", "v", "維持する", "",
  "It is hard to maintain this speed.", "この速さを保つのは難しい。"),
 ("provide", "v", "提供する", "provide sb with sth の形をとる。",
  "They provided us with food.", "彼らは私たちに食料を提供した。"),
 ("reduce", "v", "減らす", "",
  "We must reduce plastic waste.", "プラスチックごみを減らさねばならない。"),
 ("require", "v", "必要とする", "need よりかたい語。",
  "This job requires patience.", "この仕事には忍耐が必要だ。"),
 ("solve", "v", "解決する、解く", "",
  "Can you solve this problem?", "この問題を解けますか。"),
 ("apparently", "adv", "どうやら〜らしい", "",
  "Apparently the shop is closed.", "どうやら店は閉まっているらしい。"),
 ("gradually", "adv", "だんだんと", "",
  "The sky gradually became dark.", "空がだんだん暗くなった。"),
 ("nearly", "adv", "ほとんど、もう少しで", "",
  "I nearly missed the train.", "もう少しで電車に乗り遅れるところだった。"),
 ("recently", "adv", "最近", "現在完了や過去形と使う。",
  "I have recently moved here.", "最近ここへ引っ越してきた。"),
 ("despite", "prep", "〜にもかかわらず", "後ろは名詞。of は付けない。",
  "Despite the rain, we went out.", "雨にもかかわらず出かけた。"),
 ("unless", "conj", "〜でない限り", "後ろに not を重ねない。",
  "You will fail unless you practise.", "練習しない限り失敗する。"),
]}


# ==================================================================
# 2. 日→英（Q）。 [日本語, 正解, 誤答3つ, ひとこと, 単元]
#
# 誤答は **その語と本当に取りちがえる語**を置く。
# まったく関係のない語を並べると、意味を知らなくても消せてしまう。
# ==================================================================
JA2EN = {
"小5": [
 ("「走る」を英語で書くと？", "run", ("runs", "ran", "running"),
  "辞書に載っている形（原形）で答える。", "動作のことば"),
 ("「食べる」を英語で書くと？", "eat", ("ate", "eating", "eaten"), "", "動作のことば"),
 ("「本」を英語で書くと？", "book", ("look", "cook", "boot"),
  "つづりの似た語に注意。", "身のまわりのことば"),
 ("「学校」を英語で書くと？", "school", ("scool", "shool", "schoole"),
  "ch のつづりに注意。", "身のまわりのことば"),
 ("「先生」を英語で書くと？", "teacher", ("teach", "teecher", "teachar"),
  "teach（教える）＋er（人）。", "身のまわりのことば"),
 ("「友だち」を英語で書くと？", "friend", ("freind", "frend", "friendo"),
  "i が e の前。fri-end と切って覚える。", "身のまわりのことば"),
 ("「水」を英語で書くと？", "water", ("wader", "watar", "whater"), "", "身のまわりのことば"),
 ("「赤い」を英語で書くと？", "red", ("read", "rad", "reed"),
  "read（読む）と混同しない。", "色と形"),
 ("「青い」を英語で書くと？", "blue", ("blu", "bleu", "bule"), "", "色と形"),
 ("「大きい」を英語で書くと？", "big", ("bag", "beg", "bigg"), "", "色と形"),
 ("「新しい」を英語で書くと？", "new", ("knew", "nuw", "niw"),
  "knew（know の過去形）と同じ発音。", "色と形"),
 ("「うれしい」を英語で書くと？", "happy", ("hapy", "happi", "heppy"),
  "p を2つ重ねる。", "気持ちのことば"),
 ("「行く」を英語で書くと？", "go", ("goes", "went", "going"), "", "動作のことば"),
 ("「来る」を英語で書くと？", "come", ("came", "coming", "comu"), "", "動作のことば"),
 ("「飲む」を英語で書くと？", "drink", ("drank", "drinking", "drunk"), "", "動作のことば"),
 ("「勉強する」を英語で書くと？", "study", ("studys", "studied", "studing"), "", "動作のことば"),
 ("「好きだ」を英語で書くと？", "like", ("likes", "liked", "liking"), "", "動作のことば"),
 ("「書く」を英語で書くと？", "write", ("right", "rite", "wright"),
  "right（正しい）と同じ発音。", "動作のことば"),
 ("「月曜日」を英語で書くと？", "Monday", ("monday", "Munday", "Mondey"),
  "曜日はいつも大文字で始める。", "数とようび"),
 ("「朝、午前」を英語で書くと？", "morning", ("moaning", "mourning", "morninng"), "", "数とようび"),
 ("「3」を英語で書くと？", "three", ("tree", "thre", "third"),
  "tree（木）と混同しない。third は「3番目」。", "数とようび"),
 ("「とても」を英語で書くと？", "very", ("berry", "vary", "verry"), "", "身のまわりのことば"),
 ("「ここに」を英語で書くと？", "here", ("hear", "heer", "hier"),
  "hear（聞く）と同じ発音。", "身のまわりのことば"),
 ("「そして、と」を英語で書くと？", "and", ("but", "or", "so"), "", "身のまわりのことば"),
 ("「しかし」を英語で書くと？", "but", ("and", "so", "because"), "", "身のまわりのことば"),
],
"小6": [
 ("「朝食」を英語で書くと？", "breakfast", ("breakfirst", "brekfast", "breakfast time"),
  "break（やぶる）＋fast（断食）。", "学校生活のことば"),
 ("「駅」を英語で書くと？", "station", ("stasion", "staition", "statoin"), "", "身のまわりのことば"),
 ("「図書館」を英語で書くと？", "library", ("liblary", "libary", "librery"),
  "l と r をまちがえやすい。", "身のまわりのことば"),
 ("「国」を英語で書くと？", "country", ("contry", "countly", "coutry"), "", "身のまわりのことば"),
 ("「天気」を英語で書くと？", "weather", ("wether", "whether", "weathar"),
  "whether（〜かどうか）と同じ発音。", "身のまわりのことば"),
 ("「教科」を英語で書くと？", "subject", ("subjekt", "sabject", "subjuct"), "", "学校生活のことば"),
 ("「美しい」を英語で書くと？", "beautiful", ("beatiful", "beautifull", "buautiful"),
  "beau-ti-ful と3つに切る。", "ようすを表すことば"),
 ("「むずかしい」を英語で書くと？", "difficult", ("dificult", "difficalt", "difficulty"),
  "difficulty は名詞（むずかしさ）。", "ようすを表すことば"),
 ("「いそがしい」を英語で書くと？", "busy", ("bussy", "bisy", "buzy"), "", "ようすを表すことば"),
 ("「親切な」を英語で書くと？", "kind", ("kaind", "kined", "kindly"),
  "kindly は副詞。", "ようすを表すことば"),
 ("「楽しむ」を英語で書くと？", "enjoy", ("injoy", "enjoi", "enjoyed"), "", "一般動詞"),
 ("「訪れる」を英語で書くと？", "visit", ("bisit", "vizit", "visitt"), "", "一般動詞"),
 ("「手伝う」を英語で書くと？", "help", ("herp", "healp", "helpe"), "", "一般動詞"),
 ("「ほしい」を英語で書くと？", "want", ("wont", "whant", "wanto"),
  "won't（will not）と混同しない。", "一般動詞"),
 ("「必要とする」を英語で書くと？", "need", ("nead", "knead", "neid"), "", "一般動詞"),
 ("「終える」を英語で書くと？", "finish", ("finnish", "finsh", "fenish"), "", "一般動詞"),
 ("「住む」を英語で書くと？", "live", ("leave", "liv", "life"),
  "leave（去る）、life（生活）と区別する。", "一般動詞"),
 ("「知っている」を英語で書くと？", "know", ("now", "no", "knouw"),
  "now（今）と同じ発音ではない。k は読まない。", "一般動詞"),
 ("「思う、考える」を英語で書くと？", "think", ("thing", "sink", "thinck"),
  "thing（もの）と1字ちがい。", "一般動詞"),
 ("「いつも」を英語で書くと？", "always", ("allways", "alway", "olways"), "", "ひんどを表すことば"),
 ("「ときどき」を英語で書くと？", "sometimes", ("sometime", "some times", "somtimes"),
  "sometime（いつか）とは別の語。", "ひんどを表すことば"),
 ("「一度も〜ない」を英語で書くと？", "never", ("ever", "nevar", "not ever"), "", "ひんどを表すことば"),
 ("「なぜなら」を英語で書くと？", "because", ("becose", "becouse", "becuase"), "", "せつぞくのことば"),
 ("「〜の間に（2つのものの）」を英語で書くと？", "between", ("among", "betwen", "beetween"),
  "3つ以上の間は among。", "前置詞"),
],
"中1": [
 ("「答え」を英語で書くと？", "answer", ("anser", "ansewr", "answar"),
  "w は読まないが書く。", "一般動詞"),
 ("「質問」を英語で書くと？", "question", ("questoin", "quesion", "questien"), "", "疑問詞"),
 ("「問題、困ったこと」を英語で書くと？", "problem", ("ploblem", "probrem", "problum"),
  "試験の問題は question。", "一般動詞"),
 ("「考え、思いつき」を英語で書くと？", "idea", ("aidea", "idia", "ideea"), "", "一般動詞"),
 ("「場所」を英語で書くと？", "place", ("prace", "plase", "plece"), "", "be動詞"),
 ("「言語」を英語で書くと？", "language", ("langage", "languege", "langauge"), "", "一般動詞"),
 ("「注意深い」を英語で書くと？", "careful", ("carefull", "carful", "carefuly"),
  "-ful の l は1つ。", "be動詞"),
 ("「ちがう」を英語で書くと？", "different", ("diffrent", "diferent", "differrent"), "", "be動詞"),
 ("「大切な」を英語で書くと？", "important", ("inportant", "importent", "importante"), "", "be動詞"),
 ("「おもしろい」を英語で書くと？", "interesting", ("intresting", "interested", "interestting"),
  "人が興味を持つのは interested。", "be動詞"),
 ("「持ってくる」を英語で書くと？", "bring", ("take", "bling", "bringu"),
  "take は持っていく。", "一般動詞"),
 ("「選ぶ」を英語で書くと？", "choose", ("chose", "choise", "chuse"),
  "chose は過去形。", "一般動詞"),
 ("「待つ」を英語で書くと？", "wait", ("weit", "wate", "waite"), "", "一般動詞"),
 ("「着く」を英語で書くと？", "arrive", ("arive", "arrave", "ariive"),
  "r を2つ重ねる。", "一般動詞"),
 ("「借りる」を英語で書くと？", "borrow", ("lend", "borow", "barrow"),
  "lend は貸す。逆にしない。", "一般動詞"),
 ("「運ぶ」を英語で書くと？", "carry", ("cary", "carrie", "kerry"), "", "一般動詞"),
 ("「決める」を英語で書くと？", "decide", ("deside", "deside", "decid"), "", "一般動詞"),
 ("「説明する」を英語で書くと？", "explain", ("explane", "expalin", "exprain"), "", "一般動詞"),
 ("「招く」を英語で書くと？", "invite", ("invaite", "invaite", "envite"), "", "一般動詞"),
 ("「思い出す、覚えている」を英語で書くと？", "remember", ("rememver", "remenber", "remembar"), "", "一般動詞"),
 ("「早く（時刻が）」を英語で書くと？", "early", ("fast", "erly", "earlly"),
  "速さが速いのは fast。", "3人称単数のs"),
 ("「十分に」を英語で書くと？", "enough", ("enouph", "enogh", "inough"),
  "gh は読まない。", "be動詞"),
 ("「〜の間ずっと」を英語で書くと？", "during", ("while", "dueing", "durring"),
  "後ろが名詞なら during、文なら while。", "前置詞"),
 ("「〜なしで」を英語で書くと？", "without", ("with out", "withought", "witout"), "", "前置詞"),
],
"中2": [
 ("「機会」を英語で書くと？", "chance", ("chanse", "chence", "chanche"), "", "不定詞"),
 ("「ちがい」を英語で書くと？", "difference", ("different", "diffrence", "differance"),
  "different は形容詞。", "比較"),
 ("「経験」を英語で書くと？", "experience", ("expirience", "experiance", "experince"), "", "現在完了への準備"),
 ("「意見」を英語で書くと？", "opinion", ("opinon", "opinien", "openion"), "", "接続詞"),
 ("「理由」を英語で書くと？", "reason", ("reeson", "raison", "resson"), "", "接続詞"),
 ("「結果」を英語で書くと？", "result", ("rezult", "resalt", "reslut"), "", "接続詞"),
 ("「環境」を英語で書くと？", "environment", ("enviroment", "envirenment", "environmant"),
  "n を落としやすい。en-viron-ment。", "動名詞"),
 ("「危険な」を英語で書くと？", "dangerous", ("dangeres", "dangerus", "dangerouse"), "", "比較"),
 ("「高価な」を英語で書くと？", "expensive", ("expencive", "expensiv", "expansive"), "", "比較"),
 ("「外国の」を英語で書くと？", "foreign", ("forein", "foriegn", "forign"),
  "g は読まないが書く。", "比較"),
 ("「必要な」を英語で書くと？", "necessary", ("neccessary", "necesary", "nessesary"),
  "c は1つ、s は2つ。", "不定詞"),
 ("「似ている」を英語で書くと？", "similar", ("simular", "similer", "simmilar"), "", "比較"),
 ("「同意する」を英語で書くと？", "agree", ("agri", "aggree", "agrre"), "", "接続詞"),
 ("「続ける」を英語で書くと？", "continue", ("contineu", "continew", "conitnue"), "", "動名詞"),
 ("「発展させる」を英語で書くと？", "develop", ("developp", "devellop", "divelop"),
  "最後に e は付かない。", "過去形"),
 ("「上達する」を英語で書くと？", "improve", ("inprove", "improv", "improove"), "", "比較"),
 ("「増える」を英語で書くと？", "increase", ("incries", "increse", "encrease"), "", "過去形"),
 ("「準備する」を英語で書くと？", "prepare", ("prepear", "preapre", "priepare"), "", "不定詞"),
 ("「成功する」を英語で書くと？", "succeed", ("succed", "sucseed", "succeeed"),
  "名詞は success。", "不定詞"),
 ("「提案する」を英語で書くと？", "suggest", ("sugest", "suggeset", "sugjest"), "", "動名詞"),
 ("「ついに、最後に」を英語で書くと？", "finally", ("finaly", "finalley", "fainally"), "", "過去形"),
 ("「おそらく」を英語で書くと？", "probably", ("probable", "probaly", "propably"),
  "probable は形容詞。", "未来形"),
 ("「突然」を英語で書くと？", "suddenly", ("sudenly", "suddenley", "saddenly"), "", "過去進行形"),
 ("「〜だけれども」を英語で書くと？", "although", ("altough", "allthough", "althogh"),
  "but と一緒には使わない。", "接続詞"),
],
"中3": [
 ("「能力」を英語で書くと？", "ability", ("abilty", "abillity", "abiliti"), "", "関係代名詞"),
 ("「利点」を英語で書くと？", "advantage", ("advantege", "adventage", "advantige"), "", "分詞"),
 ("「証拠」を英語で書くと？", "evidence", ("evidense", "evidance", "avidence"), "", "受け身"),
 ("「目的」を英語で書くと？", "purpose", ("perpose", "purpouse", "porpose"), "", "不定詞の応用"),
 ("「研究、調査」を英語で書くと？", "research", ("reserch", "researh", "reasearch"), "", "受け身"),
 ("「解決策」を英語で書くと？", "solution", ("soluton", "solusion", "solucion"),
  "動詞は solve。", "間接疑問"),
 ("「価値」を英語で書くと？", "value", ("valu", "varue", "value_"), "", "関係代名詞"),
 ("「利用できる」を英語で書くと？", "available", ("avaliable", "availble", "availabel"), "", "受け身"),
 ("「明らかな」を英語で書くと？", "obvious", ("obvius", "obviouse", "abvious"), "", "間接疑問"),
 ("「信頼できる」を英語で書くと？", "reliable", ("relyable", "reliabel", "relaible"),
  "動詞は rely。", "関係代名詞"),
 ("「重要な、著しい」を英語で書くと？", "significant", ("significent", "signifcant", "signifikant"), "", "分詞"),
 ("「達成する」を英語で書くと？", "achieve", ("acheive", "achive", "acheave"),
  "i が e の前。", "現在完了"),
 ("「影響を与える」を英語で書くと？", "affect", ("effect", "afect", "affekt"),
  "effect は名詞（影響）。", "受け身"),
 ("「避ける」を英語で書くと？", "avoid", ("avoide", "aboid", "avoyd"), "", "動名詞の応用"),
 ("「よく考える」を英語で書くと？", "consider", ("concider", "considar", "consid"), "", "動名詞の応用"),
 ("「含む」を英語で書くと？", "contain", ("contein", "contian", "conatin"), "", "受け身"),
 ("「設立する」を英語で書くと？", "establish", ("estabilish", "establich", "istablish"), "", "受け身"),
 ("「維持する」を英語で書くと？", "maintain", ("maintian", "mantain", "maintaine"), "", "現在完了"),
 ("「提供する」を英語で書くと？", "provide", ("privide", "provaide", "provied"), "", "受け身"),
 ("「必要とする」を英語で書くと？", "require", ("requier", "requaire", "recuire"), "", "受け身"),
 ("「解決する、解く」を英語で書くと？", "solve", ("solv", "sorve", "solbe"), "", "間接疑問"),
 ("「最近」を英語で書くと？", "recently", ("resently", "recentley", "rescently"),
  "現在完了と一緒に使うことが多い。", "現在完了"),
 ("「〜にもかかわらず」を英語で書くと？", "despite", ("dispite", "despit", "desipte"),
  "後ろは名詞。of は付けない。", "分詞"),
 ("「〜でない限り」を英語で書くと？", "unless", ("unles", "onless", "unlesse"), "", "仮定法への準備"),
]}


# ==================================================================
# 3. 英語で書かれた4択（Q）。 [設問, 正解, 誤答3つ, ひとこと, 単元]
#
# **設問そのものを英語で書く。** 日本語で「正しいものを選べ」と
# 書いてしまうと、読む練習にならない。
# 誤答は **日本語話者が実際にやるまちがい**を置く。
# ==================================================================
GRAMMAR = {
"小5": [
 ("I ___ a dog.", "have", ("has", "am", "are"),
  "I には have。has は he / she / it に使う。", "一般動詞"),
 ("She ___ my sister.", "is", ("am", "are", "be"),
  "she には is。", "be動詞"),
 ("They ___ students.", "are", ("is", "am", "be"), "", "be動詞"),
 ("This ___ my book.", "is", ("are", "am", "be"), "", "be動詞"),
 ("I ___ to school every day.", "go", ("goes", "going", "went"),
  "I が主語のときは s を付けない。", "一般動詞"),
 ("Look at ___ bird!", "that", ("those", "them", "they"),
  "bird は1つなので that。", "身のまわりのことば"),
 ("I have two ___.", "cats", ("cat", "cates", "catz"),
  "2つ以上なので s を付ける。", "身のまわりのことば"),
 ("What ___ is it? It is red.", "colour", ("color of", "colours", "coloured"),
  "英国式の綴りは colour。", "色と形"),
 ("___ you like music?", "Do", ("Are", "Is", "Does"),
  "一般動詞の疑問文は Do。", "一般動詞"),
 ("I ___ like natto.", "do not", ("am not", "is not", "not"),
  "一般動詞の否定は do not。", "一般動詞"),
 ("How ___ apples do you have?", "many", ("much", "long", "old"),
  "数えられる名詞には many。", "数とようび"),
 ("It is ___ Monday today.", "", ("a", "the", "an"),
  "曜日の前に冠詞は付けない。空らんのままが正しい。", "数とようび"),
 ("I get up ___ six.", "at", ("in", "on", "to"),
  "時刻には at、曜日には on、月や年には in。", "数とようび"),
 ("We play soccer ___ Sunday.", "on", ("at", "in", "of"), "", "数とようび"),
 ("She is ___ old woman.", "an", ("a", "the", "one"),
  "母音の音で始まる語の前は an。", "身のまわりのことば"),
 ("Tom and I ___ good friends.", "are", ("is", "am", "be"),
  "2人なので are。", "be動詞"),
 ("___ is your name?", "What", ("Who", "Where", "When"), "", "疑問詞"),
 ("___ are you from?", "Where", ("What", "Who", "How"), "", "疑問詞"),
 ("I can ___ fast.", "run", ("runs", "running", "ran"),
  "can の後ろは原形。", "動作のことば"),
 ("Let us ___ together.", "sing", ("sings", "sang", "singing"),
  "Let us の後ろは原形。", "動作のことば"),
],
"小6": [
 ("He ___ tennis every Saturday.", "plays", ("play", "playing", "played"),
  "he が主語なので s を付ける。", "一般動詞"),
 ("___ she like dogs?", "Does", ("Do", "Is", "Are"),
  "she の疑問文は Does。動詞は原形に戻す。", "一般動詞"),
 ("She does not ___ milk.", "drink", ("drinks", "drank", "drinking"),
  "does の後ろは原形。", "一般動詞"),
 ("My father ___ a teacher.", "is", ("are", "am", "be"), "", "be動詞"),
 ("These books ___ mine.", "are", ("is", "am", "was"),
  "These は複数。", "代名詞"),
 ("This bag is ___.", "hers", ("her", "she", "hers'"),
  "「彼女のもの」は hers。her は「彼女の」。", "代名詞"),
 ("I know ___.", "him", ("he", "his", "he is"),
  "動詞の後ろは目的格。", "代名詞"),
 ("___ is your favourite subject?", "What", ("Who", "Which of", "How"), "", "疑問文"),
 ("___ do you go to school?", "How", ("What", "Who", "Whose"),
  "手段をたずねるのは How。", "疑問文"),
 ("I enjoy ___ books.", "reading", ("read", "to read", "reads"),
  "enjoy の後ろは -ing。", "一般動詞"),
 ("I want ___ a doctor.", "to be", ("be", "being", "am"),
  "want の後ろは to do。", "一般動詞"),
 ("He is always ___ at school.", "kind", ("kindly", "kindness", "kinder"),
  "be動詞の後ろは形容詞。", "ようすを表すことば"),
 ("She lives ___ Osaka.", "in", ("at", "on", "to"),
  "都市には in。", "前置詞"),
 ("We finished ___ lunch.", "eating", ("eat", "to eat", "eaten"),
  "finish の後ろは -ing。", "一般動詞"),
 ("I ___ go to bed early.", "always", ("am always", "always am", "be always"),
  "一般動詞の前に置く。", "ひんどを表すことば"),
 ("He is ___ late.", "never", ("not never", "never not", "no never"),
  "never だけで否定になる。", "ひんどを表すことば"),
 ("I stayed home ___ it rained.", "because", ("so", "but", "or"), "", "せつぞくのことば"),
 ("Wash your hands ___ lunch.", "before", ("ago", "front", "early"), "", "前置詞"),
 ("The shop is ___ the bank and the park.", "between", ("among", "into", "through"),
  "2つのものの間は between。", "前置詞"),
 ("There ___ many books in this room.", "are", ("is", "have", "has"),
  "books は複数なので are。", "be動詞"),
],
"中1": [
 ("She ___ to music now.", "is listening", ("listens", "listen", "listened"),
  "now があるので現在進行形。", "現在進行形"),
 ("They ___ soccer at three yesterday.", "were playing", ("are playing", "play", "plays"),
  "過去の一点なので過去進行形。", "現在進行形"),
 ("He ___ not have a bike.", "does", ("do", "is", "are"),
  "he なので does。", "3人称単数のs"),
 ("My brother ___ English very well.", "speaks", ("speak", "speaking", "is speak"), "", "3人称単数のs"),
 ("___ does she study?", "Where", ("What", "Who", "Whose"),
  "場所をたずねる。", "疑問詞"),
 ("___ bag is this?", "Whose", ("Who", "Who is", "Which"),
  "持ち主をたずねるのは Whose。", "疑問詞"),
 ("I have three ___.", "boxes", ("boxs", "box", "boxies"),
  "x で終わる語は es を付ける。", "複数形"),
 ("There are many ___ in the garden.", "leaves", ("leafs", "leafes", "leaf"),
  "f を v に変えて es。", "複数形"),
 ("I ___ swim when I was five.", "could", ("can", "am able", "could to"),
  "過去の能力は could。", "助動詞can"),
 ("___ I use your pen?", "May", ("Do", "Am", "Are"),
  "許可を求める言い方。", "助動詞can"),
 ("Wait ___ me at the gate.", "for", ("to", "at", "on"),
  "wait for が決まった形。", "一般動詞"),
 ("We arrived ___ the station at six.", "at", ("to", "in to", "on"),
  "狭い場所には at。", "一般動詞"),
 ("Please explain this ___ me.", "to", ("for", "at", "with"),
  "explain me とは言わない。", "一般動詞"),
 ("She decided ___ abroad.", "to study", ("studying", "study", "studied"),
  "decide の後ろは to do。", "一般動詞"),
 ("My idea is different ___ yours.", "from", ("with", "to", "of"), "", "be動詞"),
 ("This room is big ___.", "enough", ("enough big", "too", "very"),
  "enough は形容詞の後ろ。", "be動詞"),
 ("I read three books ___ the holiday.", "during", ("while", "when", "for during"),
  "後ろが名詞なので during。", "前置詞"),
 ("He left ___ a word.", "without", ("with no", "not", "no"), "", "前置詞"),
 ("She is good ___ playing the piano.", "at", ("in", "on", "for"), "", "現在進行形"),
 ("Look! It ___ outside.", "is raining", ("rains", "rained", "rain"),
  "Look! があるので今の話。", "現在進行形"),
],
"中2": [
 ("I ___ to London last year.", "went", ("go", "have gone", "was going"),
  "last year は過去の一点。", "過去形"),
 ("She ___ her homework when I called.", "was doing", ("did", "does", "has done"),
  "電話したときの進行中。", "過去進行形"),
 ("It ___ rain tomorrow.", "will", ("is", "does", "was"), "", "未来形"),
 ("We ___ visit the museum next week.", "are going to", ("go to", "will to", "are go to"),
  "be going to の形。", "未来形"),
 ("I want ___ English harder.", "to study", ("studying", "study", "studied"), "", "不定詞"),
 ("He came here ___ his friend.", "to see", ("seeing", "for see", "see"),
  "目的を表す不定詞。", "不定詞"),
 ("It is important ___ every day.", "to practise", ("practising", "practise", "practised"), "", "不定詞"),
 ("He suggested ___ by train.", "going", ("to go", "go", "went"),
  "suggest の後ろは -ing。", "動名詞"),
 ("Avoid ___ long sentences.", "using", ("to use", "use", "used"), "", "動名詞"),
 ("This book is ___ than that one.", "easier", ("more easy", "easyer", "easiest"),
  "y を i に変えて er。", "比較"),
 ("She is the ___ student in her class.", "tallest", ("taller", "most tall", "tall"), "", "比較"),
 ("This watch is ___ expensive than mine.", "more", ("much", "very", "most"),
  "長い形容詞は more。", "比較"),
 ("My bag is similar ___ yours.", "to", ("with", "as", "from"), "", "比較"),
 ("___ it rained, we went out.", "Although", ("But", "However", "Despite"),
  "後ろに文が続くので Although。", "接続詞"),
 ("He called ___ I was cooking.", "while", ("during", "for", "at"),
  "後ろが文なので while。", "接続詞"),
 ("I agree ___ you.", "with", ("to", "on", "for"), "", "接続詞"),
 ("It depends ___ the weather.", "on", ("of", "to", "with"), "", "接続詞"),
 ("We prepared ___ the exam.", "for", ("to", "at", "of"), "", "不定詞"),
 ("You ___ finish it today.", "must", ("must to", "have", "are must"),
  "must の後ろは原形。", "助動詞"),
 ("You ___ not run in the corridor.", "must", ("do", "are", "have"),
  "must not で強い禁止。", "助動詞"),
],
"中3": [
 ("This bridge ___ in 1890.", "was built", ("built", "is building", "has built"),
  "橋は「建てられた」ので受け身。", "受け身"),
 ("English ___ all over the world.", "is spoken", ("speaks", "is speaking", "spoke"), "", "受け身"),
 ("The letter ___ yet.", "has not arrived", ("did not arrive", "is not arriving", "not arrived"),
  "yet は現在完了と使う。", "現在完了"),
 ("I ___ him since 2020.", "have known", ("know", "knew", "am knowing"),
  "since があるので現在完了。", "現在完了"),
 ("She ___ to Kyoto three times.", "has been", ("has gone", "went to", "is going"),
  "経験は have been to。have gone to は「行ってしまった」。", "現在完了"),
 ("The girl ___ is singing is my sister.", "who", ("which", "whose", "whom"),
  "先行詞が人なので who。", "関係代名詞"),
 ("This is the book ___ I bought yesterday.", "which", ("who", "what", "whose"),
  "先行詞がものなので which。", "関係代名詞"),
 ("I know a boy ___ father is a pilot.", "whose", ("who", "which", "who is"),
  "「その子の父」なので whose。", "関係代名詞"),
 ("The man ___ over there is my uncle.", "standing", ("stands", "stood", "is standing"),
  "名詞を後ろから説明する分詞。", "分詞"),
 ("I found a window ___ by someone.", "broken", ("breaking", "broke", "break"),
  "「割られた窓」なので過去分詞。", "分詞"),
 ("Do you know ___ she lives?", "where", ("where does", "where is", "that where"),
  "間接疑問の語順は「疑問詞＋主語＋動詞」。", "間接疑問"),
 ("I do not know ___ he will come.", "if", ("that", "what", "how"),
  "「〜かどうか」は if。", "間接疑問"),
 ("If I ___ a bird, I would fly to you.", "were", ("am", "will be", "have been"),
  "仮定法では were を使う。", "仮定法"),
 ("I wish I ___ speak French.", "could", ("can", "will", "am able"), "", "仮定法"),
 ("___ the rain, we went out.", "Despite", ("Although", "However", "Because"),
  "後ろが名詞なので Despite。", "分詞"),
 ("You will fail ___ you practise.", "unless", ("if", "although", "unless not"),
  "unless は「〜でない限り」。", "仮定法"),
 ("They provided us ___ food.", "with", ("of", "to", "for"), "", "受け身"),
 ("The rain ___ the game.", "affected", ("effected", "affect to", "was affect"),
  "affect は動詞。effect は名詞。", "受け身"),
 ("We are considering ___ to York.", "moving", ("to move", "move", "moved"), "", "動名詞の応用"),
 ("This drink ___ sugar.", "contains", ("is containing", "contain", "is contained"),
  "contain は進行形にしない。", "受け身"),
]}


# ==================================================================
# 4. 短い読解（Q）。 [文章＋設問, 正解, 誤答3つ, ひとこと, 単元]
#
# **1問ずつ完結させる。** 忘却曲線は項目ごとに独立しているので、
# 1つの文章に何問もぶら下げると、文章だけが出ない日ができる。
# ==================================================================
READING = {
"小5": [
 ("Read. Tom gets up at six. He goes to school by bus. "
  "Question: How does Tom go to school?",
  "By bus.", ("By train.", "By bike.", "On foot."), "", "読む"),
 ("Read. Ann has a cat. Its name is Mimi. It is white. "
  "Question: What colour is Mimi?",
  "White.", ("Black.", "Brown.", "Grey."), "", "読む"),
 ("Read. We have music on Monday and science on Friday. "
  "Question: When do we have science?",
  "On Friday.", ("On Monday.", "On Sunday.", "On Tuesday."), "", "読む"),
 ("Read. My father is a cook. He makes cakes every day. "
  "Question: What does my father make?",
  "Cakes.", ("Bread.", "Pizza.", "Soup."), "", "読む"),
 ("Read. It is rainy today. I stay home and read a book. "
  "Question: What do I do today?",
  "I read a book.", ("I play outside.", "I go to school.", "I run in the park."),
  "", "読む"),
 ("Read. Ken has three dogs and one cat. "
  "Question: How many dogs does Ken have?",
  "Three.", ("One.", "Four.", "Two."), "", "読む"),
 ("Read. The shop opens at nine and closes at six. "
  "Question: What time does the shop close?",
  "At six.", ("At nine.", "At seven.", "At eight."), "", "読む"),
 ("Read. Emi likes apples, but she does not like oranges. "
  "Question: What does Emi like?",
  "Apples.", ("Oranges.", "Both.", "Neither."), "", "読む"),
],
"小6": [
 ("Read. Ken lives in Osaka with his family. He has a sister and a dog. "
  "Every Sunday they walk in the park. "
  "Question: What do they do on Sunday?",
  "They walk in the park.", ("They stay home.", "They go to school.",
                             "They visit Osaka."), "", "読む"),
 ("Read. Our school festival is in October. Students sing and dance. "
  "Many parents come to watch. "
  "Question: Who comes to watch the festival?",
  "Many parents.", ("Only teachers.", "No one.", "Students from Osaka."), "", "読む"),
 ("Read. Mary wants to be a nurse because she likes helping people. "
  "She studies science hard. "
  "Question: Why does Mary study science hard?",
  "Because she wants to be a nurse.",
  ("Because she likes reading.", "Because her father is a doctor.",
   "Because she has a test tomorrow."), "", "読む"),
 ("Read. The library opens at ten. It closes at five on Saturday. "
  "It is closed on Sunday. "
  "Question: When is the library closed?",
  "On Sunday.", ("On Saturday.", "At ten.", "Every day."), "", "読む"),
 ("Read. Yuki was tired, so she went to bed early. She slept for ten hours. "
  "Question: Why did Yuki go to bed early?",
  "Because she was tired.", ("Because it was cold.", "Because she was hungry.",
                             "Because she had a test."), "", "読む"),
 ("Read. In winter it snows a lot in this town. Children make snowmen. "
  "Question: What do children make in winter?",
  "Snowmen.", ("Cakes.", "Kites.", "Boats."), "", "読む"),
 ("Read. Tom's birthday is in May. His sister's birthday is in June. "
  "Question: When is Tom's birthday?",
  "In May.", ("In June.", "In July.", "In March."), "", "読む"),
 ("Read. We went to the zoo, but it was closed. We went to the park instead. "
  "Question: Where did we go in the end?",
  "To the park.", ("To the zoo.", "To school.", "Home."), "", "読む"),
],
"中1": [
 ("Read. Sam is a member of the tennis club. He practises after school "
  "every day except Wednesday. On Wednesday he helps at his father's shop. "
  "Question: What does Sam do on Wednesday?",
  "He helps at his father's shop.",
  ("He practises tennis.", "He stays at school.", "He visits his uncle."),
  "", "読む"),
 ("Read. Our class went to a farm last week. We saw twenty cows and "
  "many chickens. The farmer explained how to milk a cow. "
  "Question: Who explained how to milk a cow?",
  "The farmer.", ("Our teacher.", "A student.", "Sam's father."), "", "読む"),
 ("Read. Ken wanted to buy a new bike, but it was too expensive. "
  "He decided to save money for six months. "
  "Question: Why did Ken decide to save money?",
  "Because the bike was too expensive.",
  ("Because he lost his bike.", "Because his father told him to.",
   "Because he wanted a new bag."), "", "読む"),
 ("Read. The train leaves at 7:15. It takes forty minutes to the city. "
  "Question: What time does the train arrive in the city?",
  "At 7:55.", ("At 7:15.", "At 8:15.", "At 7:40."),
  "40分後なので 7:55。", "読む"),
 ("Read. Emi is learning the piano. She practises for thirty minutes "
  "every morning before school. "
  "Question: When does Emi practise the piano?",
  "Before school in the morning.",
  ("After school.", "At night.", "Only on Sunday."), "", "読む"),
 ("Read. It was raining, so the game was cancelled. The players went home. "
  "Question: Why was the game cancelled?",
  "Because it was raining.", ("Because the players were tired.",
                              "Because it was late.", "Because nobody came."),
  "", "読む"),
 ("Read. Our school has 480 students. About half of them come by bus. "
  "Question: About how many students come by bus?",
  "About 240.", ("About 480.", "About 120.", "About 80."), "", "読む"),
 ("Read. Mr Green is from Canada. He has taught English here for three years. "
  "Question: How long has Mr Green taught here?",
  "For three years.", ("Since Canada.", "For three months.", "Since last year."),
  "", "読む"),
],
"中2": [
 ("Read. Last summer Yuki stayed with a host family in Sydney. "
  "At first she could not understand fast English, but after two weeks "
  "she began to enjoy talking with them. "
  "Question: What happened after two weeks?",
  "She began to enjoy talking with them.",
  ("She went back to Japan.", "She stopped speaking English.",
   "She moved to another family."), "", "読む"),
 ("Read. Our town started a plan to reduce plastic waste. Shops stopped "
  "giving free bags. As a result, the amount of waste decreased by 20%. "
  "Question: What was the result of the plan?",
  "The waste decreased by 20%.",
  ("The waste increased.", "Shops closed.", "Nothing changed."), "", "読む"),
 ("Read. Ken is taller than his brother, but his brother is stronger. "
  "Question: Who is stronger?",
  "Ken's brother.", ("Ken.", "Both are the same.", "We do not know."), "", "読む"),
 ("Read. The museum is free for children under twelve. Adults pay five pounds. "
  "Question: How much does a ten-year-old pay?",
  "Nothing.", ("Five pounds.", "Two pounds.", "Ten pounds."), "", "読む"),
 ("Read. Although it was very cold, we decided to walk to the station. "
  "It took us twenty minutes. "
  "Question: How did they go to the station?",
  "They walked.", ("By bus.", "By taxi.", "By train."), "", "読む"),
 ("Read. Emi practises the violin every day because she wants to join "
  "the school orchestra next year. "
  "Question: Why does Emi practise every day?",
  "Because she wants to join the orchestra.",
  ("Because her teacher told her to.", "Because she has a concert tomorrow.",
   "Because she likes the violin more than sport."), "", "読む"),
 ("Read. If it rains tomorrow, the sports day will be held on Monday. "
  "Question: When will the sports day be held if it rains?",
  "On Monday.", ("Tomorrow.", "On Sunday.", "It will be cancelled."), "", "読む"),
 ("Read. Tom finished his homework and then watched television for an hour. "
  "Question: What did Tom do first?",
  "He finished his homework.", ("He watched television.", "He went to bed.",
                                "He called his friend."), "", "読む"),
],
"中3": [

 ("Read. The bridge was built in 1890 and has been used ever since. "
  "It was repaired twice, in 1950 and in 2005. "
  "Question: How many times has the bridge been repaired?",
  "Twice.", ("Once.", "Three times.", "Never."), "", "読む"),
 ("Read. Many students think that studying abroad is expensive. "
  "However, some universities provide students with scholarships, "
  "so the real cost can be much lower. "
  "Question: What does the writer want to say?",
  "Studying abroad may cost less than students think.",
  ("Studying abroad is always cheap.", "Scholarships are difficult to get.",
   "Students should not study abroad."), "", "読む"),
 ("Read. The girl who won the race is only fourteen. She has trained "
  "every morning since she was nine. "
  "Question: How long has she trained?",
  "For about five years.", ("For fourteen years.", "For nine years.",
                            "Since last year."), "", "読む"),
 ("Read. Unless we act now, the forest will disappear within twenty years. "
  "Question: What will happen if we do nothing?",
  "The forest will disappear.", ("The forest will grow.",
                                 "Nothing will change.", "Trees will be planted."),
  "", "読む"),
 ("Read. I do not know where he lives, but I know that he works in London. "
  "Question: What does the writer know about him?",
  "That he works in London.", ("Where he lives.", "His telephone number.",
                               "When he moved to London."), "", "読む"),
 ("Read. Despite the heavy rain, the concert was held outdoors. "
  "About two thousand people came. "
  "Question: Where was the concert held?",
  "Outdoors.", ("In a hall.", "At a school.", "It was cancelled."), "", "読む"),
 ("Read. This machine is more efficient than the old one. It uses half "
  "the electricity and works twice as fast. "
  "Question: How much electricity does the new machine use?",
  "Half of the old one.", ("Twice the old one.", "The same as the old one.",
                           "None."), "", "読む"),
]}


def main():
    built = []
    for band in ("小5", "小6", "中1", "中2", "中3"):
        code = BAND_CODE[band]
        p = Pack("english/" + code, "english", "英語 %s" % band, [band],
                 "英→日・日→英・英語の設問・短い読解の4つ。すべて単元つき",
                 english=True)

        # 1. 英→日。単語そのものを表にする。
        for head, pos, ja, note, ex, ex_ja in WORDS[band]:
            p.T("%s（%s）" % (head, pos), ja, band, note, ex, ex_ja)

        # 2. 日→英
        for q, ok, wrong, note, unit in JA2EN[band]:
            p.Q(q, ok, list(wrong), band, note, unit=unit)

        # 3. 英語で書かれた4択
        for q, ok, wrong, note, unit in GRAMMAR[band]:
            # 空らんが答えになる問題は「（何も入れない）」と書く。
            # 空文字のままだと裏が空になり、書き出しで止まる。
            p.Q(q, ok or "（何も入れない）", list(wrong), band, note, unit=unit)

        # 4. 短い読解
        for q, ok, wrong, note, unit in READING[band]:
            p.Q(q, ok, list(wrong), band, note, unit=unit)

        built.append(p.write())

    report(built)
    return 0


if __name__ == "__main__":
    sys.exit(main())
