/* 長文読解 中1 ―― 長文を読んで答える。本文は content/readings.js

   **このファイルは app/tools/gen_content.py が書き出したもの。**
   手で直さないこと。直すなら生成側を直して作り直す。
   （手書きに戻すと他言語の字が混ざる。実際に35箇所まぎれ込んだ）

   T（用語）  [表, 裏, 帯, 解説, 例, 例の補足]
   Q（選択）  [問題文, 正解, 誤答(|区切り), 帯, 解説]  */
(function(){
"use strict";

var T = [
];

var Q = [
["Who carries the food to the classroom?","The students.","The teachers.|The cooks.|The visitors.","中1","第一段落。themselves が手がかり。","長文を読む","","en-j1-lunch"],
["Why are foreign visitors often surprised?","Because students clean the classroom themselves.","Because the food is free.|Because lunch is very long.|Because students wear white coats.","中1","第二段落。","長文を読む","","en-j1-lunch"],
["What do teachers say about lunch and cleaning?","They are part of the lessons.","They take too much time.|They should be done by cleaners.|They are not important.","中1","最終段落。","長文を読む","","en-j1-lunch"],
];

TubeContent.register({
  id:      'english/cho-j1',
  subject: 'english',
  name:    '長文読解 中1',
  note:    '長文を読んで答える。本文は content/readings.js',
  bands:   ['中1'],
  T:T, Q:Q
});

})();
