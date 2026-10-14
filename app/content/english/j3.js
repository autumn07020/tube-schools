/* 英語 中3 ―― 英→日・日→英・英語の設問・短い読解の4つ。すべて単元つき

   **このファイルは app/tools/gen_content.py が書き出したもの。**
   手で直さないこと。直すなら生成側を直して作り直す。
   （手書きに戻すと他言語の字が混ざる。実際に35箇所まぎれ込んだ）

   T（用語）  [表, 裏, 帯, 解説, 例, 例の補足]
   Q（選択）  [問題文, 正解, 誤答(|区切り), 帯, 解説]  */
(function(){
"use strict";

var T = [
["ability（n）","能力","中3","形容詞は able。","She has the ability to lead others.","彼女には人を導く力がある。"],
["advantage（n）","利点","中3","反対は disadvantage。","Living here has many advantages.","ここに住むには多くの利点がある。"],
["condition（n）","状態、条件","中3","","The road is in bad condition.","その道は状態が悪い。"],
["effect（n）","影響、効果","中3","動詞の affect と混同しない。","The effect was greater than expected.","影響は予想より大きかった。"],
["evidence（n）","証拠","中3","数えられない。an evidence とは言わない。","There is no evidence for that.","それを裏づける証拠はない。"],
["purpose（n）","目的","中3","on purpose で「わざと」。","What is the purpose of this rule?","この規則の目的は何ですか。"],
["research（n）","研究、調査","中3","数えられない。researches とはあまり言わない。","He is doing research on plants.","彼は植物の研究をしている。"],
["solution（n）","解決策","中3","動詞は solve。","We are looking for a solution.","私たちは解決策をさがしている。"],
["source（n）","源、出どころ","中3","","The sun is a source of energy.","太陽はエネルギーの源だ。"],
["value（n）","価値","中3","","This old coin has great value.","この古い硬貨には大きな価値がある。"],
["available（adj）","利用できる、手に入る","中3","","The book is available at the library.","その本は図書館で借りられる。"],
["certain（adj）","確かな、ある〜","中3","","I am certain that he is right.","彼が正しいと確信している。"],
["efficient（adj）","効率のよい","中3","","This is an efficient way to study.","これは効率のよい勉強法だ。"],
["obvious（adj）","明らかな","中3","","The answer is obvious.","答えは明らかだ。"],
["particular（adj）","特定の、とくべつの","中3","in particular で「とくに」。","Do you have a particular reason?","特別な理由があるのですか。"],
["reliable（adj）","信頼できる","中3","動詞は rely。","He is a reliable friend.","彼は信頼できる友人だ。"],
["significant（adj）","重要な、著しい","中3","","There was a significant change.","著しい変化があった。"],
["sufficient（adj）","十分な","中3","enough よりかたい語。","We have sufficient food for a week.","1週間分の十分な食料がある。"],
["achieve（v）","達成する","中3","名詞は achievement。","She achieved her goal.","彼女は目標を達成した。"],
["affect（v）","影響を与える","中3","名詞の effect と混同しない。to は要らない。","The rain affected the game.","雨が試合に影響した。"],
["avoid（v）","避ける","中3","後ろは -ing。avoid to do は誤り。","Avoid using long sentences.","長い文を使うのは避けなさい。"],
["consider（v）","よく考える","中3","後ろは -ing。","We are considering moving to York.","ヨークへ引っ越すことを考えている。"],
["contain（v）","含む","中3","進行形にしない。","This drink contains sugar.","この飲み物には砂糖が含まれる。"],
["describe（v）","描写する、説明する","中3","describe me it とは言わない。","Describe the picture to your partner.","その絵を相手に説明しなさい。"],
["establish（v）","設立する、確立する","中3","","The school was established in 1890.","その学校は1890年に設立された。"],
["maintain（v）","維持する","中3","","It is hard to maintain this speed.","この速さを保つのは難しい。"],
["provide（v）","提供する","中3","provide sb with sth の形をとる。","They provided us with food.","彼らは私たちに食料を提供した。"],
["reduce（v）","減らす","中3","","We must reduce plastic waste.","プラスチックごみを減らさねばならない。"],
["require（v）","必要とする","中3","need よりかたい語。","This job requires patience.","この仕事には忍耐が必要だ。"],
["solve（v）","解決する、解く","中3","","Can you solve this problem?","この問題を解けますか。"],
["apparently（adv）","どうやら〜らしい","中3","","Apparently the shop is closed.","どうやら店は閉まっているらしい。"],
["gradually（adv）","だんだんと","中3","","The sky gradually became dark.","空がだんだん暗くなった。"],
["nearly（adv）","ほとんど、もう少しで","中3","","I nearly missed the train.","もう少しで電車に乗り遅れるところだった。"],
["recently（adv）","最近","中3","現在完了や過去形と使う。","I have recently moved here.","最近ここへ引っ越してきた。"],
["despite（prep）","〜にもかかわらず","中3","後ろは名詞。of は付けない。","Despite the rain, we went out.","雨にもかかわらず出かけた。"],
["unless（conj）","〜でない限り","中3","後ろに not を重ねない。","You will fail unless you practise.","練習しない限り失敗する。"],
];

var Q = [
["「能力」を英語で書くと？","ability","abilty|abillity|abiliti","中3","","関係代名詞"],
["「利点」を英語で書くと？","advantage","advantege|adventage|advantige","中3","","分詞"],
["「証拠」を英語で書くと？","evidence","evidense|evidance|avidence","中3","","受け身"],
["「目的」を英語で書くと？","purpose","perpose|purpouse|porpose","中3","","不定詞の応用"],
["「研究、調査」を英語で書くと？","research","reserch|researh|reasearch","中3","","受け身"],
["「解決策」を英語で書くと？","solution","soluton|solusion|solucion","中3","動詞は solve。","間接疑問"],
["「価値」を英語で書くと？","value","valu|varue|value_","中3","","関係代名詞"],
["「利用できる」を英語で書くと？","available","avaliable|availble|availabel","中3","","受け身"],
["「明らかな」を英語で書くと？","obvious","obvius|obviouse|abvious","中3","","間接疑問"],
["「信頼できる」を英語で書くと？","reliable","relyable|reliabel|relaible","中3","動詞は rely。","関係代名詞"],
["「重要な、著しい」を英語で書くと？","significant","significent|signifcant|signifikant","中3","","分詞"],
["「達成する」を英語で書くと？","achieve","acheive|achive|acheave","中3","i が e の前。","現在完了"],
["「影響を与える」を英語で書くと？","affect","effect|afect|affekt","中3","effect は名詞（影響）。","受け身"],
["「避ける」を英語で書くと？","avoid","avoide|aboid|avoyd","中3","","動名詞の応用"],
["「よく考える」を英語で書くと？","consider","concider|considar|consid","中3","","動名詞の応用"],
["「含む」を英語で書くと？","contain","contein|contian|conatin","中3","","受け身"],
["「設立する」を英語で書くと？","establish","estabilish|establich|istablish","中3","","受け身"],
["「維持する」を英語で書くと？","maintain","maintian|mantain|maintaine","中3","","現在完了"],
["「提供する」を英語で書くと？","provide","privide|provaide|provied","中3","","受け身"],
["「必要とする」を英語で書くと？","require","requier|requaire|recuire","中3","","受け身"],
["「解決する、解く」を英語で書くと？","solve","solv|sorve|solbe","中3","","間接疑問"],
["「最近」を英語で書くと？","recently","resently|recentley|rescently","中3","現在完了と一緒に使うことが多い。","現在完了"],
["「〜にもかかわらず」を英語で書くと？","despite","dispite|despit|desipte","中3","後ろは名詞。of は付けない。","分詞"],
["「〜でない限り」を英語で書くと？","unless","unles|onless|unlesse","中3","","仮定法への準備"],
["This bridge ___ in 1890.","was built","built|is building|has built","中3","橋は「建てられた」ので受け身。","受け身"],
["English ___ all over the world.","is spoken","speaks|is speaking|spoke","中3","","受け身"],
["The letter ___ yet.","has not arrived","did not arrive|is not arriving|not arrived","中3","yet は現在完了と使う。","現在完了"],
["I ___ him since 2020.","have known","know|knew|am knowing","中3","since があるので現在完了。","現在完了"],
["She ___ to Kyoto three times.","has been","has gone|went to|is going","中3","経験は have been to。have gone to は「行ってしまった」。","現在完了"],
["The girl ___ is singing is my sister.","who","which|whose|whom","中3","先行詞が人なので who。","関係代名詞"],
["This is the book ___ I bought yesterday.","which","who|what|whose","中3","先行詞がものなので which。","関係代名詞"],
["I know a boy ___ father is a pilot.","whose","who|which|who is","中3","「その子の父」なので whose。","関係代名詞"],
["The man ___ over there is my uncle.","standing","stands|stood|is standing","中3","名詞を後ろから説明する分詞。","分詞"],
["I found a window ___ by someone.","broken","breaking|broke|break","中3","「割られた窓」なので過去分詞。","分詞"],
["Do you know ___ she lives?","where","where does|where is|that where","中3","間接疑問の語順は「疑問詞＋主語＋動詞」。","間接疑問"],
["I do not know ___ he will come.","if","that|what|how","中3","「〜かどうか」は if。","間接疑問"],
["If I ___ a bird, I would fly to you.","were","am|will be|have been","中3","仮定法では were を使う。","仮定法"],
["I wish I ___ speak French.","could","can|will|am able","中3","","仮定法"],
["___ the rain, we went out.","Despite","Although|However|Because","中3","後ろが名詞なので Despite。","分詞"],
["You will fail ___ you practise.","unless","if|although|unless not","中3","unless は「〜でない限り」。","仮定法"],
["They provided us ___ food.","with","of|to|for","中3","","受け身"],
["The rain ___ the game.","affected","effected|affect to|was affect","中3","affect は動詞。effect は名詞。","受け身"],
["We are considering ___ to York.","moving","to move|move|moved","中3","","動名詞の応用"],
["This drink ___ sugar.","contains","is containing|contain|is contained","中3","contain は進行形にしない。","受け身"],
["Read. The bridge was built in 1890 and has been used ever since. It was repaired twice, in 1950 and in 2005. Question: How many times has the bridge been repaired?","Twice.","Once.|Three times.|Never.","中3","","読む"],
["Read. Many students think that studying abroad is expensive. However, some universities provide students with scholarships, so the real cost can be much lower. Question: What does the writer want to say?","Studying abroad may cost less than students think.","Studying abroad is always cheap.|Scholarships are difficult to get.|Students should not study abroad.","中3","","読む"],
["Read. The girl who won the race is only fourteen. She has trained every morning since she was nine. Question: How long has she trained?","For about five years.","For fourteen years.|For nine years.|Since last year.","中3","","読む"],
["Read. Unless we act now, the forest will disappear within twenty years. Question: What will happen if we do nothing?","The forest will disappear.","The forest will grow.|Nothing will change.|Trees will be planted.","中3","","読む"],
["Read. I do not know where he lives, but I know that he works in London. Question: What does the writer know about him?","That he works in London.","Where he lives.|His telephone number.|When he moved to London.","中3","","読む"],
["Read. Despite the heavy rain, the concert was held outdoors. About two thousand people came. Question: Where was the concert held?","Outdoors.","In a hall.|At a school.|It was cancelled.","中3","","読む"],
["Read. This machine is more efficient than the old one. It uses half the electricity and works twice as fast. Question: How much electricity does the new machine use?","Half of the old one.","Twice the old one.|The same as the old one.|None.","中3","","読む"],
];

TubeContent.register({
  id:      'english/j3',
  subject: 'english',
  name:    '英語 中3',
  note:    '英→日・日→英・英語の設問・短い読解の4つ。すべて単元つき',
  bands:   ['中3'],
  T:T, Q:Q
});

})();
