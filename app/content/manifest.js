/* ============================================================
   教材の目録
   ------------------------------------------------------------
   「どの科目に、どの教材があるか」だけを書く。中身は書かない。

   教材を1つ足す手順は2つだけ:
     1. content/<科目>/<名前>.js を置く
     2. このファイルの packs に1行足す
   アプリ本体（js/）にもサーバにも手を入れない。

   ここに書いてあるものが、講師の「進度」画面で選べるようになる。
   実際にどの学年がどれを使うかは講師が画面で決める
   （保存先は server/data/curriculum.json）。
   ============================================================ */
(function(global){
"use strict";

global.TubeManifest = {

  /* ----------------------------------------------------------
     科目。増やすときはここに足し、content/ に同名のフォルダを作る。

     code は項目IDの先頭に付く短い記号（en / sci / soc）。
     これがあるので、英語の「law」と社会の「法」が別物として記録される。
     ★ 一度決めた code は変えないこと。変えると、その科目の進捗が
       すべて別人のものとして扱われる（IDが変わるため）。
     short は狭い画面で使う1文字。
     ---------------------------------------------------------- */
  subjects: [
    { id:'english', code:'en',  name:'英語', short:'英', order:1 },
    { id:'science', code:'sci', name:'理科', short:'理', order:2 },
    { id:'social',   code:'soc', name:'社会', short:'社', order:3 },
    { id:'math',     code:'mat', name:'数学', short:'数', order:4 },
    { id:'japanese', code:'jpn', name:'国語', short:'国', order:5 }
  ],

  /* ----------------------------------------------------------
     教材パック

     id     … 一意。'<科目>/<名前>' の形にする
     file   … content/ からの相対パス
     bands  … その教材の中の難度の帯。名前は教材ごとに自由でよい
              （英語はCEFR、理科・社会は「基礎/標準/発展」など）
              講師はこの帯を選んで「どこから始めるか」を決める
     items  … 目安の項目数。画面に出すだけで、実際の数は読み込み後に数える
     ---------------------------------------------------------- */
  packs: [
    /* **仮置きの教材である。** 中身は前身プロジェクト（IELTS B2→C1）の
       ものなので、中学生の学年にそのまま当たるわけではない。
       自社教材の単語データが入ったら、これを外して差し替える。
         python3 app/tools/import_words.py 単語.csv --id waseda/j1 …
       帯（A2〜C1）も CEFR のままで、学年とは対応していない。 */
    /* 学年別の英語。**既定はこちら。**
       core（下）は全学年が同じ1,134項目を見ていたうえ、単元が付いて
       いなかった。単元が空だと examprep.in_scope が絞れないので、
       5週の単元確認テスト対策と苦手単元の再テストが、英語だけ
       一度も効かない状態だった。**落ちないので気づけない穴**である。 */
    /* 文学の読解。**本文は宮沢賢治（1896-1933）。著作権は消滅している。**
       出どころは青空文庫。設問・選択肢・解説はこちらで書き下ろした
       （試験問題には著作権があるので、既存の問題は使わない）。 */
    { id:'japanese/kenji-e4', subject:'japanese', file:'japanese/kenji-e4.js',
      name:'文学の読解 小4', items:0,
      bands:['小4'],
      note:'宮沢賢治（青空文庫・著作権消滅）。本文は content/readings.js' },
    { id:'japanese/kenji-e5', subject:'japanese', file:'japanese/kenji-e5.js',
      name:'文学の読解 小5', items:0,
      bands:['小5'],
      note:'宮沢賢治（青空文庫・著作権消滅）。本文は content/readings.js' },
    { id:'japanese/kenji-e6', subject:'japanese', file:'japanese/kenji-e6.js',
      name:'文学の読解 小6', items:0,
      bands:['小6'],
      note:'宮沢賢治（青空文庫・著作権消滅）。本文は content/readings.js' },
    { id:'japanese/kenji-j1', subject:'japanese', file:'japanese/kenji-j1.js',
      name:'文学の読解 中1', items:0,
      bands:['中1'],
      note:'宮沢賢治（青空文庫・著作権消滅）。本文は content/readings.js' },
    { id:'japanese/kenji-j2', subject:'japanese', file:'japanese/kenji-j2.js',
      name:'文学の読解 中2', items:0,
      bands:['中2'],
      note:'宮沢賢治（青空文庫・著作権消滅）。本文は content/readings.js' },
    { id:'japanese/kenji-j3', subject:'japanese', file:'japanese/kenji-j3.js',
      name:'文学の読解 中3', items:0,
      bands:['中3'],
      note:'宮沢賢治（青空文庫・著作権消滅）。本文は content/readings.js' },

    /* 穴埋め（理科・社会）と 長文読解（国語・英語）。
       一問一答だけでは、実際のテストの形に届かない。
       長文の本文は content/readings.js に1つだけ置き、
       設問は8列目でその名前を指す ―― 同じ600字を何度も持たせない。 */
    { id:'science/ana-e4', subject:'science', file:'science/ana-e4.js',
      name:'穴埋め 理科 小4', items:0,
      bands:['小4'],
      note:'文の空欄を4択で埋める' },
    { id:'science/ana-e5', subject:'science', file:'science/ana-e5.js',
      name:'穴埋め 理科 小5', items:0,
      bands:['小5'],
      note:'文の空欄を4択で埋める' },
    { id:'science/ana-e6', subject:'science', file:'science/ana-e6.js',
      name:'穴埋め 理科 小6', items:0,
      bands:['小6'],
      note:'文の空欄を4択で埋める' },
    { id:'science/ana-j1', subject:'science', file:'science/ana-j1.js',
      name:'穴埋め 理科 中1', items:0,
      bands:['中1'],
      note:'文の空欄を4択で埋める' },
    { id:'science/ana-j2', subject:'science', file:'science/ana-j2.js',
      name:'穴埋め 理科 中2', items:0,
      bands:['中2'],
      note:'文の空欄を4択で埋める' },
    { id:'science/ana-j3', subject:'science', file:'science/ana-j3.js',
      name:'穴埋め 理科 中3', items:0,
      bands:['中3'],
      note:'文の空欄を4択で埋める' },
    { id:'social/ana-e4', subject:'social', file:'social/ana-e4.js',
      name:'穴埋め 社会 小4', items:0,
      bands:['小4'],
      note:'文の空欄を4択で埋める' },
    { id:'social/ana-e5', subject:'social', file:'social/ana-e5.js',
      name:'穴埋め 社会 小5', items:0,
      bands:['小5'],
      note:'文の空欄を4択で埋める' },
    { id:'social/ana-e6', subject:'social', file:'social/ana-e6.js',
      name:'穴埋め 社会 小6', items:0,
      bands:['小6'],
      note:'文の空欄を4択で埋める' },
    { id:'social/ana-j1', subject:'social', file:'social/ana-j1.js',
      name:'穴埋め 社会 中1', items:0,
      bands:['中1'],
      note:'文の空欄を4択で埋める' },
    { id:'social/ana-j2', subject:'social', file:'social/ana-j2.js',
      name:'穴埋め 社会 中2', items:0,
      bands:['中2'],
      note:'文の空欄を4択で埋める' },
    { id:'social/ana-j3', subject:'social', file:'social/ana-j3.js',
      name:'穴埋め 社会 中3', items:0,
      bands:['中3'],
      note:'文の空欄を4択で埋める' },
    { id:'japanese/cho-e4', subject:'japanese', file:'japanese/cho-e4.js',
      name:'長文読解 小4', items:0,
      bands:['小4'],
      note:'長文を読んで答える。本文は content/readings.js' },
    { id:'japanese/cho-e5', subject:'japanese', file:'japanese/cho-e5.js',
      name:'長文読解 小5', items:0,
      bands:['小5'],
      note:'長文を読んで答える。本文は content/readings.js' },
    { id:'japanese/cho-e6', subject:'japanese', file:'japanese/cho-e6.js',
      name:'長文読解 小6', items:0,
      bands:['小6'],
      note:'長文を読んで答える。本文は content/readings.js' },
    { id:'japanese/cho-j1', subject:'japanese', file:'japanese/cho-j1.js',
      name:'長文読解 中1', items:0,
      bands:['中1'],
      note:'長文を読んで答える。本文は content/readings.js' },
    { id:'japanese/cho-j2', subject:'japanese', file:'japanese/cho-j2.js',
      name:'長文読解 中2', items:0,
      bands:['中2'],
      note:'長文を読んで答える。本文は content/readings.js' },
    { id:'japanese/cho-j3', subject:'japanese', file:'japanese/cho-j3.js',
      name:'長文読解 中3', items:0,
      bands:['中3'],
      note:'長文を読んで答える。本文は content/readings.js' },
    { id:'english/cho-e6', subject:'english', file:'english/cho-e6.js',
      name:'長文読解 小6', items:0,
      bands:['小6'],
      note:'長文を読んで答える。本文は content/readings.js' },
    { id:'english/cho-j1', subject:'english', file:'english/cho-j1.js',
      name:'長文読解 中1', items:0,
      bands:['中1'],
      note:'長文を読んで答える。本文は content/readings.js' },
    { id:'english/cho-j2', subject:'english', file:'english/cho-j2.js',
      name:'長文読解 中2', items:0,
      bands:['中2'],
      note:'長文を読んで答える。本文は content/readings.js' },
    { id:'english/cho-j3', subject:'english', file:'english/cho-j3.js',
      name:'長文読解 中3', items:0,
      bands:['中3'],
      note:'長文を読んで答える。本文は content/readings.js' },

    /* 文章題（算数）と 読解（国語）。**一問一答だけでは組み分けテストに届かない。**
       算数は解説に解き方を書いてある。国語の文章は1問ずつ完結している
       （忘却曲線は項目ごとに独立しているので、1つの文章に何問もぶら下げると
       文章だけが読めない日ができる）。 */
    { id:'math/bun-e4', subject:'math', file:'math/bun-e4.js',
      name:'文章題 小4', items:8,
      bands:['小4'],
      note:'文章題。解説に解き方' },
    { id:'math/bun-e5', subject:'math', file:'math/bun-e5.js',
      name:'文章題 小5', items:8,
      bands:['小5'],
      note:'文章題。解説に解き方' },
    { id:'math/bun-e6', subject:'math', file:'math/bun-e6.js',
      name:'文章題 小6', items:8,
      bands:['小6'],
      note:'文章題。解説に解き方' },
    { id:'math/bun-j1', subject:'math', file:'math/bun-j1.js',
      name:'文章題 中1', items:8,
      bands:['中1'],
      note:'文章題。解説に解き方' },
    { id:'math/bun-j2', subject:'math', file:'math/bun-j2.js',
      name:'文章題 中2', items:8,
      bands:['中2'],
      note:'文章題。解説に解き方' },
    { id:'math/bun-j3', subject:'math', file:'math/bun-j3.js',
      name:'文章題 中3', items:8,
      bands:['中3'],
      note:'文章題。解説に解き方' },
    { id:'japanese/doku-e4', subject:'japanese', file:'japanese/doku-e4.js',
      name:'読解 小4', items:6,
      bands:['小4'],
      note:'短い文章を読んで答える' },
    { id:'japanese/doku-e5', subject:'japanese', file:'japanese/doku-e5.js',
      name:'読解 小5', items:6,
      bands:['小5'],
      note:'短い文章を読んで答える' },
    { id:'japanese/doku-e6', subject:'japanese', file:'japanese/doku-e6.js',
      name:'読解 小6', items:6,
      bands:['小6'],
      note:'短い文章を読んで答える' },
    { id:'japanese/doku-j1', subject:'japanese', file:'japanese/doku-j1.js',
      name:'読解 中1', items:6,
      bands:['中1'],
      note:'短い文章を読んで答える' },
    { id:'japanese/doku-j2', subject:'japanese', file:'japanese/doku-j2.js',
      name:'読解 中2', items:6,
      bands:['中2'],
      note:'短い文章を読んで答える' },
    { id:'japanese/doku-j3', subject:'japanese', file:'japanese/doku-j3.js',
      name:'読解 中3', items:6,
      bands:['中3'],
      note:'短い文章を読んで答える' },

    { id:'science/zu-j1', subject:'science', file:'science/zu-j1.js',
      name:'図の問題 中1', items:0,
      bands:['中1'],
      note:'図を見て答える。絵は content/figures.js' },
    { id:'science/zu-j2', subject:'science', file:'science/zu-j2.js',
      name:'図の問題 中2', items:0,
      bands:['中2'],
      note:'図を見て答える。絵は content/figures.js' },
    { id:'science/zu-j3', subject:'science', file:'science/zu-j3.js',
      name:'図の問題 中3', items:0,
      bands:['中3'],
      note:'図を見て答える。絵は content/figures.js' },
    { id:'social/zu-j2', subject:'social', file:'social/zu-j2.js',
      name:'図の問題 中2', items:0,
      bands:['中2'],
      note:'図を見て答える。絵は content/figures.js' },
    { id:'social/zu-j3', subject:'social', file:'social/zu-j3.js',
      name:'図の問題 中3', items:0,
      bands:['中3'],
      note:'図を見て答える。絵は content/figures.js' },

    /* 図を見て答える問題。**絵は content/figures.js が持つ。**
       教材は絵の名前だけを7列目に書き、同じ絵を何問でも使いまわす。
       画像ファイルではなく SVG なので、置き場も CSP も要らず、
       地下鉄の中でも出て、紙に刷ってもにじまない。 */
    { id:'science/zu-e4', subject:'science', file:'science/zu-e4.js',
      name:'図の問題 小4', items:13,
      bands:['小4'],
      note:'図を見て答える。絵は content/figures.js' },
    { id:'science/zu-e5', subject:'science', file:'science/zu-e5.js',
      name:'図の問題 小5', items:6,
      bands:['小5'],
      note:'図を見て答える。絵は content/figures.js' },
    { id:'science/zu-e6', subject:'science', file:'science/zu-e6.js',
      name:'図の問題 小6', items:11,
      bands:['小6'],
      note:'図を見て答える。絵は content/figures.js' },
    { id:'social/zu-e5', subject:'social', file:'social/zu-e5.js',
      name:'図の問題 小5', items:6,
      bands:['小5'],
      note:'図を見て答える。絵は content/figures.js' },

    { id:'english/e5', subject:'english', file:'english/e5.js',
      name:'英語 小5', items:93,
      bands:['小5'],
      note:'英→日・日→英・英語で書かれた4択・短い読解。単元つき' },
    { id:'english/e6', subject:'english', file:'english/e6.js',
      name:'英語 小6', items:88,
      bands:['小6'],
      note:'英→日・日→英・英語で書かれた4択・短い読解。単元つき' },
    { id:'english/j1', subject:'english', file:'english/j1.js',
      name:'英語 中1', items:88,
      bands:['中1'],
      note:'英→日・日→英・英語で書かれた4択・短い読解。単元つき' },
    { id:'english/j2', subject:'english', file:'english/j2.js',
      name:'英語 中2', items:88,
      bands:['中2'],
      note:'英→日・日→英・英語で書かれた4択・短い読解。単元つき' },
    { id:'english/j3', subject:'english', file:'english/j3.js',
      name:'英語 中3', items:88,
      bands:['中3'],
      note:'英→日・日→英・英語で書かれた4択・短い読解。単元つき' },

    { id:'english/core', subject:'english', file:'english/core.js',
      name:'英単語（仮）', items:1590,
      bands:['A2','B1','B2','C1'],
      provisional:'自社教材が入るまでの仮置きです。帯は CEFR で、学年とは別のものです。',
      note:'前身プロジェクト由来。英国綴り。単語・語法・文法' },

    { id:'japanese/kanji-e4', subject:'japanese', file:'japanese/kanji-e4.js',
      name:'漢字 小4', items:228,
      bands:['小4'],
      note:'学年別漢字配当表（内閣告示）の小4配当字から。熟語と意味は自作' },

    { id:'japanese/kanji-e5', subject:'japanese', file:'japanese/kanji-e5.js',
      name:'漢字 小5', items:234,
      bands:['小5'],
      note:'学年別漢字配当表（内閣告示）の小5配当字から。熟語と意味は自作' },

    { id:'japanese/kanji-e6', subject:'japanese', file:'japanese/kanji-e6.js',
      name:'漢字 小6', items:248,
      bands:['小6'],
      note:'学年別漢字配当表（内閣告示）の小6配当字から。熟語と意味は自作' },

    { id:'japanese/kanji-j1', subject:'japanese', file:'japanese/kanji-j1.js',
      name:'漢字 中1', items:236,
      bands:['中1'],
      note:'常用漢字表（内閣告示）の中学配当字から。熟語と意味は自作' },

    { id:'japanese/kanji-j2', subject:'japanese', file:'japanese/kanji-j2.js',
      name:'漢字 中2', items:236,
      bands:['中2'],
      note:'常用漢字表（内閣告示）の中学配当字から。熟語と意味は自作' },

    { id:'japanese/kanji-j3', subject:'japanese', file:'japanese/kanji-j3.js',
      name:'漢字 中3', items:240,
      bands:['中3'],
      note:'常用漢字表（内閣告示）の中学配当字から。熟語と意味は自作' },

    { id:'science/e4', subject:'science', file:'science/e4.js',
      name:'理科 小4', items:102,
      bands:['小4'],
      note:'電気・水のすがた・月と星・季節と生物。問題文と解説は自作' },

    { id:'science/e5', subject:'science', file:'science/e5.js',
      name:'理科 小5', items:101,
      bands:['小5'],
      note:'発芽・天気・流れる水・ふりこ・もののとけ方。問題文と解説は自作' },

    { id:'science/e6', subject:'science', file:'science/e6.js',
      name:'理科 小6', items:101,
      bands:['小6'],
      note:'燃焼・人の体・水よう液・てこ・土地。問題文と解説は自作' },

    { id:'science/j1n', subject:'science', file:'science/j1n.js',
      name:'理科 中1', items:103,
      bands:['中1'],
      note:'植物・気体・状態変化・光音力・大地。問題文と解説は自作' },

    { id:'science/j2', subject:'science', file:'science/j2.js',
      name:'理科 中2', items:114,
      bands:['中2'],
      note:'原子分子・化学変化・電流・動物・天気。問題文と解説は自作' },

    { id:'science/j3', subject:'science', file:'science/j3.js',
      name:'理科 中3', items:103,
      bands:['中3'],
      note:'運動・仕事・イオン・遺伝・天体。問題文と解説は自作' },

    { id:'social/e4', subject:'social', file:'social/e4.js',
      name:'社会 小4', items:120,
      bands:['小4'],
      note:'都道府県と県庁所在地・水道とごみ・安全と災害。問題文と解説は自作' },

    { id:'social/e5', subject:'social', file:'social/e5.js',
      name:'社会 小5', items:132,
      bands:['小5'],
      note:'国土と気候・農業と水産業・工業・情報・環境。問題文と解説は自作' },

    { id:'social/e6', subject:'social', file:'social/e6.js',
      name:'社会 小6', items:142,
      bands:['小6'],
      note:'歴史の流れ・政治のしくみ・国際。問題文と解説は自作' },

    { id:'social/j1s', subject:'social', file:'social/j1s.js',
      name:'社会 中1', items:131,
      bands:['中1'],
      note:'世界の地理。問題文と解説は自作' },

    { id:'social/j2', subject:'social', file:'social/j2.js',
      name:'社会 中2', items:136,
      bands:['中2'],
      note:'日本の地理と歴史。問題文と解説は自作' },

    { id:'social/j3', subject:'social', file:'social/j3.js',
      name:'社会 中3', items:140,
      bands:['中3'],
      note:'近現代史・政治・経済・国際。問題文と解説は自作' },

    { id:'math/e4', subject:'math', file:'math/e4.js',
      name:'小4 算数', items:52,
      bands:['小4'],
      note:'がい数・わり算・面積・小数と分数。問題と解説は自作' },

    { id:'math/e5', subject:'math', file:'math/e5.js',
      name:'小5 算数', items:51,
      bands:['小5'],
      note:'通分約分・割合・平均・面積と体積。問題と解説は自作' },

    { id:'math/e6', subject:'math', file:'math/e6.js',
      name:'小6 算数', items:46,
      bands:['小6'],
      note:'分数のかけわり・比・速さ・円・場合の数。問題と解説は自作' },

    { id:'math/j1', subject:'math', file:'math/j1.js',
      name:'数学 中1', items:76,
      bands:['中1'],
      note:'正負の数・文字式・方程式・比例・図形。問題と解説は自作' },

    { id:'math/j2', subject:'math', file:'math/j2.js',
      name:'数学 中2', items:50,
      bands:['中2'],
      note:'式の計算・連立方程式・一次関数・角度・確率。問題と解説は自作' },

    { id:'math/j3', subject:'math', file:'math/j3.js',
      name:'数学 中3', items:48,
      bands:['中3'],
      note:'展開因数分解・平方根・二次方程式・三平方。問題と解説は自作' },

    { id:'japanese/kaki-e4', subject:'japanese', file:'japanese/kaki-e4.js',
      name:'漢字の書き 小4', items:0,
      bands:['小4'],
      note:'文から漢字を書く。答えは大きく出る' },

    { id:'japanese/idiom-e4', subject:'japanese', file:'japanese/idiom-e4.js',
      name:'慣用句・ことわざ 小4', items:22,
      bands:['小4'],
      note:'意味を4択で選ぶ。取りちがえやすい意味を誤答にしてある' },

    { id:'japanese/kaki-e5', subject:'japanese', file:'japanese/kaki-e5.js',
      name:'漢字の書き 小5', items:0,
      bands:['小5'],
      note:'文から漢字を書く。答えは大きく出る' },

    { id:'japanese/idiom-e5', subject:'japanese', file:'japanese/idiom-e5.js',
      name:'慣用句・ことわざ 小5', items:22,
      bands:['小5'],
      note:'意味を4択で選ぶ。取りちがえやすい意味を誤答にしてある' },

    { id:'japanese/kaki-e6', subject:'japanese', file:'japanese/kaki-e6.js',
      name:'漢字の書き 小6', items:0,
      bands:['小6'],
      note:'文から漢字を書く。答えは大きく出る' },

    { id:'japanese/idiom-e6', subject:'japanese', file:'japanese/idiom-e6.js',
      name:'慣用句・ことわざ 小6', items:22,
      bands:['小6'],
      note:'意味を4択で選ぶ。取りちがえやすい意味を誤答にしてある' },

    { id:'japanese/kaki-j1', subject:'japanese', file:'japanese/kaki-j1.js',
      name:'漢字の書き 中1', items:0,
      bands:['中1'],
      note:'文から漢字を書く。答えは大きく出る' },

    { id:'japanese/idiom-j1', subject:'japanese', file:'japanese/idiom-j1.js',
      name:'慣用句・ことわざ 中1', items:22,
      bands:['中1'],
      note:'意味を4択で選ぶ。取りちがえやすい意味を誤答にしてある' },

    { id:'japanese/kaki-j2', subject:'japanese', file:'japanese/kaki-j2.js',
      name:'漢字の書き 中2', items:0,
      bands:['中2'],
      note:'文から漢字を書く。答えは大きく出る' },

    { id:'japanese/idiom-j2', subject:'japanese', file:'japanese/idiom-j2.js',
      name:'慣用句・ことわざ 中2', items:22,
      bands:['中2'],
      note:'意味を4択で選ぶ。取りちがえやすい意味を誤答にしてある' },

    { id:'japanese/kaki-j3', subject:'japanese', file:'japanese/kaki-j3.js',
      name:'漢字の書き 中3', items:0,
      bands:['中3'],
      note:'文から漢字を書く。答えは大きく出る' },

    { id:'japanese/idiom-j3', subject:'japanese', file:'japanese/idiom-j3.js',
      name:'慣用句・ことわざ 中3', items:22,
      bands:['中3'],
      note:'意味を4択で選ぶ。取りちがえやすい意味を誤答にしてある' },

    { id:'social/nengo-e6', subject:'social', file:'social/nengo-e6.js',
      name:'年号 小6', items:22,
      bands:['小6'],
      note:'できごとの年を4択で。誤答は近い年にしてある' },

    { id:'social/nengo-j1', subject:'social', file:'social/nengo-j1.js',
      name:'年号 中1', items:22,
      bands:['中1'],
      note:'できごとの年を4択で。誤答は近い年にしてある' },

    { id:'social/nengo-j2', subject:'social', file:'social/nengo-j2.js',
      name:'年号 中2', items:22,
      bands:['中2'],
      note:'できごとの年を4択で。誤答は近い年にしてある' },

    { id:'social/nengo-j3', subject:'social', file:'social/nengo-j3.js',
      name:'年号 中3', items:22,
      bands:['中3'],
      note:'できごとの年を4択で。誤答は近い年にしてある' },

    { id:'social/chiri-e4', subject:'social', file:'social/chiri-e4.js',
      name:'地理の基礎 小4', items:22,
      bands:['小4'],
      note:'地図記号・都道府県・国土のようす' },

    { id:'social/chiri-e5', subject:'social', file:'social/chiri-e5.js',
      name:'地理の基礎 小5', items:22,
      bands:['小5'],
      note:'地図記号・都道府県・国土のようす' }
  ],

  /* ----------------------------------------------------------
     冊子（宿題で「番号」で指すもの）

     アプリは番号と達成状況だけを持ち、中身は持たない。
     市販教材の語の選定・訳語・例文は編集著作物として保護されるため
     （HANDOVER.md 4章）。生徒は冊子を見て思い出し、自己採点する。

     mode ―― その教材を「どこで解くか」。**教材の性質であって、
     宿題ごとの指定ではない。** 漢字の書き取りは誰が出しても紙だし、
     単語帳は誰が出してもアプリで自己採点できる。
     ここに1度書いておけば、講師は今までどおり教材を選ぶだけでよく、
     生徒も何も入力しなくてよい。経路は教材について回る。

       'app'   … アプリで解いて自己採点できる。達成がそのまま記録に残る
       'paper' … 紙に書かないと解けない。アプリは達成を観測できない

     'paper' の宿題を「未提出」と数えないこと。アプリが見ていないだけで、
     やっていないとは限らない。紙でやっている生徒を怠けているように
     見せる画面を作ったら、その講師はもう使わない。
     ---------------------------------------------------------- */
  booklets: [
    /* My英単語帳。**冊子は無い。** 番号は、下の pack（english/core）に
       入っている単語の並び順そのものを指す。
       生徒は番号を紙で引くのではなく、アプリの中で意味を4択から選ぶ。

       前は「Vocabulary GRIT 2500」という冊子を引く作りだった。
       番号だけ出して「冊子で調べて、思い出せたか自分で押す」―― これは
       **アプリでやる意味がない。** 紙を見るなら紙だけでよい。 */
    { id:'myvocab', subject:'english', name:'My英単語帳',
      short:'単語帳', max:1616, mode:'app', pack:'english/core',
      note:'番号の語の意味を、4択で選ぶ。冊子は要らない' },

    { id:'kanji-write', subject:'japanese', name:'漢字 書き取り',
      short:'漢字書', max:2136, mode:'paper',
      note:'手で書かないと練習にならない。アプリは範囲を伝えるだけ' },

    { id:'keisan', subject:'math', name:'計算ドリル',
      short:'計算', max:600, mode:'paper',
      note:'途中式を書く。採点は先生がノートで行う' },

    { id:'wa-text', subject:'english', name:'塾テキスト（英語）',
      short:'テキスト', max:400, mode:'paper',
      note:'記述と和訳。ノートに解く' }
  ]
};

})(window);
