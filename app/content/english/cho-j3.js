/* 長文読解 中3 ―― 長文を読んで答える。本文は content/readings.js

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
["What does the brain do while we sleep?","It sorts and stores what we have learned.","It forgets everything.|It studies new words.|It stops working completely.","中3","第一段落。","長文を読む","","en-j3-sleep"],
["Which group remembered more words?","The group that slept for eight hours.","The group that studied two more hours.|Both groups equally.|Neither group.","中3","第二段落。although が手がかり。","長文を読む","","en-j3-sleep"],
["What does the writer say about sleeping alone?","It cannot teach us anything by itself.","It is better than studying.|It is a waste of time.|It replaces study.","中3","最終段落。","長文を読む","","en-j3-sleep"],
["What is the writer's main point?","Study and sleep must go together.","Students should study late at night.|Sleep is more important than study.|Research is often wrong.","中3","最終文。","長文を読む","","en-j3-sleep"],
];

TubeContent.register({
  id:      'english/cho-j3',
  subject: 'english',
  name:    '長文読解 中3',
  note:    '長文を読んで答える。本文は content/readings.js',
  bands:   ['中3'],
  T:T, Q:Q
});

})();
