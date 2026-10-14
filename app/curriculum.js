/* ============================================================
   進度の既定値
   ------------------------------------------------------------
   ★ ふだんはこのファイルを触りません。

   学年ごと・科目ごとの分量や範囲は、**講師が画面から変えます**
   （講師 → 進度タブ）。変えた内容はサーバの
   server/data/curriculum.json に保存され、全生徒に即反映されます。

   このファイルが使われるのは次の2つのときだけです。

     1. サーバをまだ一度も起動していないとき（初期値として取り込まれる）
     2. サーバに繋がらないとき（端末内だけで動く非常時の既定値）

   つまりここは「工場出荷時の設定」です。恒久的な変更は画面から行い、
   ここを書き換えるのは、新しい学校で最初から立ち上げるときだけです。
   ============================================================ */
(function(global){
"use strict";

global.TubeCurriculum = {

  v: 2,
  /* サーバに繋がるまでは、どの校舎かは分からない。
     校舎名はログイン後に profile.schoolName から入る（config.setSchool）。 */
  school: { id:'', name:'早稲田アカデミー' },

  /* ----------------------------------------------------------
     学年。小1〜中3。
     id は進捗や進度の鍵になるので、一度決めたら変えないこと。
     ---------------------------------------------------------- */
  grades: [
    { id:'e1', name:'小1', order:1 },
    { id:'e2', name:'小2', order:2 },
    { id:'e3', name:'小3', order:3 },
    { id:'e4', name:'小4', order:4 },
    { id:'e5', name:'小5', order:5 },
    { id:'e6', name:'小6', order:6 },
    { id:'j1', name:'中1', order:7 },
    { id:'j2', name:'中2', order:8 },
    { id:'j3', name:'中3', order:9 }
  ],

  /* ----------------------------------------------------------
     在籍クラス。生徒はどれか1つに属し、そこから学年が決まる。
     code はサーバに繋がらないときの入口で使う。

     **在籍クラスはこの20件だけ。** ID は生徒のログインIDに入るので、
     あとから変えない。合同（中2理科）・指名（土特・必勝）・講習は
     在籍クラスではなく「コース」で書く（server/courses.py、
     Claude outputs/SEED-ロンドン校.md 2・3章）。

       小1〜小3  J
       小4〜小6  α・β（中学受験。成績で分ける）／K（中学受験をしない子のサポート）
       中1〜中3  T・R ／ D（土曜。中3 は D が無く、代わりに土特）

     名前に α/β/R を使うのは教室の呼び方に合わせたもの。
     画面にはそのまま出す ―― 講師と生徒が普段そう呼んでいる。
     ---------------------------------------------------------- */
  classes: [
    { id:'e1j', name:'小1J', grade:'e1', code:'LDN-E1J' },
    { id:'e2j', name:'小2J', grade:'e2', code:'LDN-E2J' },
    { id:'e3j', name:'小3J', grade:'e3', code:'LDN-E3J' },
    { id:'e4a', name:'小4α', grade:'e4', code:'LDN-E4A' },
    { id:'e4b', name:'小4β', grade:'e4', code:'LDN-E4B' },
    { id:'e4k', name:'小4K', grade:'e4', code:'LDN-E4K' },
    { id:'e5a', name:'小5α', grade:'e5', code:'LDN-E5A' },
    { id:'e5b', name:'小5β', grade:'e5', code:'LDN-E5B' },
    { id:'e5k', name:'小5K', grade:'e5', code:'LDN-E5K' },
    { id:'e6a', name:'小6α', grade:'e6', code:'LDN-E6A' },
    { id:'e6b', name:'小6β', grade:'e6', code:'LDN-E6B' },
    { id:'e6k', name:'小6K', grade:'e6', code:'LDN-E6K' },
    { id:'j1t', name:'中1T', grade:'j1', code:'LDN-J1T' },
    { id:'j1r', name:'中1R', grade:'j1', code:'LDN-J1R' },
    { id:'j1d', name:'中1D', grade:'j1', code:'LDN-J1D' },
    { id:'j2t', name:'中2T', grade:'j2', code:'LDN-J2T' },
    { id:'j2r', name:'中2R', grade:'j2', code:'LDN-J2R' },
    { id:'j2d', name:'中2D', grade:'j2', code:'LDN-J2D' },
    { id:'j3t', name:'中3T', grade:'j3', code:'LDN-J3T' },
    { id:'j3r', name:'中3R', grade:'j3', code:'LDN-J3R' }
  ],

  /* ----------------------------------------------------------
     進度 ―― 「学年 × 科目」ごとに、何を・どれだけ

     鍵は '<学年>:<科目>'。ここに無い組み合わせは「その学年では
     その科目をやらない」という意味になる。

     packs   … 使う教材（content/manifest.js の id）
     bands   … 取り組む順。難度の順である必要はない
     tracks  … 出題する種別。教材が持っているものだけ選べる
                英語 vocab/prep/gram、他科目 term/quiz
     daily   … 1日の新出量。0.5 は「1日おきに1つ」
     maxRev  … 1日の復習の上限。ここで頭打ちにしないと数週間で破綻する
     enabled … false なら生徒の画面に出ない（準備中の科目）

     ▼ 分量について
       **ここに書いた数は「希望」であって、そのまま出るわけではない。**
       app/js/config.js の fit() が、学年ごとの1日の持ち時間
       （小4 20分 … 小6 45分 / 中1 50分 … 中3 60分）に収まるよう
       削ってから生徒に出す。教科を1つ「使う」に切り替えても、
       1日の合計は増えない ―― 1教科あたりの取り分が減るだけである。

       だからここの数を増やしても、生徒の1日は長くならない。
       長さを変えたいときは config.js の DAILY_MIN を直すこと
       （server/examprep.py にも同じ表がある。両方直す）。
     ---------------------------------------------------------- */
  plans: {
    /* 英語。**学年別のパックに差し替えた。**
       前は全学年が english/core（IELTS B2〜C1の1,134項目）を見ていた。
       小5に "accommodation" が出るうえ、単元が付いていないため
       5週の対策も苦手単元の再テストも、英語だけ一度も効かなかった。
       core は目録に残してあるので、上級者には講師が足せる。 */
    'e5:english': { enabled:true, packs:['english/e5'], bands:['小5'],
                    tracks:['term','quiz'], daily:{term:6, quiz:6}, maxRev:60 },
    'e6:english': { enabled:true, packs:['english/e6', 'english/cho-e6'], bands:['小6'],
                    tracks:['term','quiz'], daily:{term:6, quiz:6}, maxRev:60 },
    'j1:english': { enabled:true, packs:['english/j1', 'english/cho-j1'], bands:['中1'],
                    tracks:['term','quiz'], daily:{term:7, quiz:7}, maxRev:70 },
    'j2:english': { enabled:true, packs:['english/j2', 'english/cho-j2'], bands:['中2'],
                    tracks:['term','quiz'], daily:{term:7, quiz:7}, maxRev:70 },
    'j3:english': { enabled:true, packs:['english/j3', 'english/cho-j3'], bands:['中3'],
                    tracks:['term','quiz'], daily:{term:8, quiz:8}, maxRev:80 },

    /* 理科・社会・国語（漢字）は教材を入れてあるが、既定では止めてある。
       講師が画面から「使う」に切り替えると、その学年の生徒に出る。

       ★ **既定は「使う」にしてある。**
         以前はここが enabled:false で、新しい校舎を作ると
         英語しか出なかった。教材は5千項目あるのに、国語も算数も
         理科も社会も一問も出ない ―― しかもエラーは出ない。
         デモだけが curriculum.json で全教科を有効にしていたので、
         デモを見ているかぎり気づけなかった。
         使わない教科は、講師が進度の画面で外せる。

       ★ 教材IDは学年ごとに違う。ここを別の学年のIDにすると、
         その学年の生徒には**何も出ない**（エラーも出ない）。
         app/tools/check-content.py が食い違いを見張っている。 */
    /* 算数・数学。**ここが丸ごと抜けていた。**
       教材は 323問あるのに、進度に項目が無いため、どの学年でも
       1問も出なかった。デモは curriculum.json で直接 j1:math などを
       書いていたので、デモを見ているかぎり気づけなかった。

       計算問題は「式を見て解く→答えと解き方が出る」形なので、
       毎日テストでは quiz を多めにする。 */
    'e4:math':     { enabled:true, packs:['math/e4', 'math/bun-e4'], bands:['小4'],
                    tracks:['term','quiz'], daily:{term:5, quiz:5}, maxRev:60 },
    'e5:math':     { enabled:true, packs:['math/e5', 'math/bun-e5'], bands:['小5'],
                    tracks:['term','quiz'], daily:{term:5, quiz:5}, maxRev:60 },
    'e6:math':     { enabled:true, packs:['math/e6', 'math/bun-e6'], bands:['小6'],
                    tracks:['term','quiz'], daily:{term:5, quiz:5}, maxRev:60 },
    'j1:math':     { enabled:true, packs:['math/j1', 'math/bun-j1'], bands:['中1'],
                    tracks:['term','quiz'], daily:{term:5, quiz:5}, maxRev:60 },
    'j2:math':     { enabled:true, packs:['math/j2', 'math/bun-j2'], bands:['中2'],
                    tracks:['term','quiz'], daily:{term:5, quiz:5}, maxRev:60 },
    'j3:math':     { enabled:true, packs:['math/j3', 'math/bun-j3'], bands:['中3'],
                    tracks:['term','quiz'], daily:{term:5, quiz:5}, maxRev:60 },
    'e4:science':  { enabled:true, packs:['science/e4', 'science/zu-e4', 'science/ana-e4'], bands:['小4'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'e4:social':   { enabled:true, packs:['social/e4', 'social/chiri-e4', 'social/ana-e4'], bands:['小4'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'e4:japanese': { enabled:true, packs:['japanese/kanji-e4', 'japanese/kaki-e4', 'japanese/idiom-e4', 'japanese/doku-e4', 'japanese/cho-e4', 'japanese/kenji-e4'], bands:['小4'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'e5:science':  { enabled:true, packs:['science/e5', 'science/zu-e5', 'science/ana-e5'], bands:['小5'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'e5:social':   { enabled:true, packs:['social/e5', 'social/chiri-e5', 'social/zu-e5', 'social/ana-e5'], bands:['小5'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'e5:japanese': { enabled:true, packs:['japanese/kanji-e5', 'japanese/kaki-e5', 'japanese/idiom-e5', 'japanese/doku-e5', 'japanese/cho-e5', 'japanese/kenji-e5'], bands:['小5'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'e6:science':  { enabled:true, packs:['science/e6', 'science/zu-e6', 'science/ana-e6'], bands:['小6'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'e6:social':   { enabled:true, packs:['social/e6', 'social/nengo-e6', 'social/ana-e6'], bands:['小6'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'e6:japanese': { enabled:true, packs:['japanese/kanji-e6', 'japanese/kaki-e6', 'japanese/idiom-e6', 'japanese/doku-e6', 'japanese/cho-e6', 'japanese/kenji-e6'], bands:['小6'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'j1:science':  { enabled:true, packs:['science/j1n', 'science/ana-j1', 'science/zu-j1'], bands:['中1'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'j1:social':   { enabled:true, packs:['social/j1s', 'social/nengo-j1', 'social/ana-j1'], bands:['中1'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'j1:japanese': { enabled:true, packs:['japanese/kanji-j1', 'japanese/kaki-j1', 'japanese/idiom-j1', 'japanese/doku-j1', 'japanese/cho-j1', 'japanese/kenji-j1'], bands:['中1'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'j2:science':  { enabled:true, packs:['science/j2', 'science/ana-j2', 'science/zu-j2'], bands:['中2'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'j2:social':   { enabled:true, packs:['social/j2', 'social/nengo-j2', 'social/ana-j2', 'social/zu-j2'], bands:['中2'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'j2:japanese': { enabled:true, packs:['japanese/kanji-j2', 'japanese/kaki-j2', 'japanese/idiom-j2', 'japanese/doku-j2', 'japanese/cho-j2', 'japanese/kenji-j2'], bands:['中2'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'j3:science':  { enabled:true, packs:['science/j3', 'science/ana-j3', 'science/zu-j3'], bands:['中3'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'j3:social':   { enabled:true, packs:['social/j3', 'social/nengo-j3', 'social/ana-j3', 'social/zu-j3'], bands:['中3'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 },
    'j3:japanese': { enabled:true, packs:['japanese/kanji-j3', 'japanese/kaki-j3', 'japanese/idiom-j3', 'japanese/doku-j3', 'japanese/cho-j3', 'japanese/kenji-j3'], bands:['中3'],
                    tracks:['term','quiz'], daily:{term:6, quiz:3}, maxRev:60 }
  },

  /* ----------------------------------------------------------
     同期先。起動時にここへ /health を投げてサーバの有無を確かめる。

       いる   → IDとパスワードで入る。記録も進度もサーバから来る
       いない → クラスコードで入る。記録は端末の中だけ、進度はこの既定値

     VPSへ移すときに変えるのはこの1行だけ。
     ---------------------------------------------------------- */
  sync: { base: '/api' },

  /* 音声の言語。教材が英国英語なので既定は en-GB。 */
  voice: 'en-GB',

  /* 宿題の1日の目安の下限。期限まで日数があっても1日1語では終わらない。 */
  hwMinPerDay: 5,

  /* 「定着」とみなす間隔（日）。Anki の mature と同じ考え方。 */
  mature: 21,

  /* 講師画面の「つまずき」に出す下限。 */
  stuckLapses: 3
};

})(window);
