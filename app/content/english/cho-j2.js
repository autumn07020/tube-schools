/* 長文読解 中2 ―― 長文を読んで答える。本文は content/readings.js

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
["What makes plastic useful and also a problem?","It is strong and does not disappear.","It is expensive.|It is heavy.|It melts easily.","中2","第一段落。同じ性質が両方の理由になっている。","長文を読む","","en-j2-plastic"],
["Why do fish eat plastic?","Because the pieces are very small.","Because plastic smells good.|Because there is no other food.|Because people feed them.","中2","第二段落。","長文を読む","","en-j2-plastic"],
["What happened in one town?","Plastic waste fell by twenty per cent in a year.","Shops closed.|Plastic waste doubled.|Nothing changed.","中2","最終段落。","長文を読む","","en-j2-plastic"],
["What does the writer think about the change?","It was small but showed that action is possible.","It was enough to solve the problem.|It was useless.|It was too expensive.","中2","最終文。","長文を読む","","en-j2-plastic"],
];

TubeContent.register({
  id:      'english/cho-j2',
  subject: 'english',
  name:    '長文読解 中2',
  note:    '長文を読んで答える。本文は content/readings.js',
  bands:   ['中2'],
  T:T, Q:Q
});

})();
