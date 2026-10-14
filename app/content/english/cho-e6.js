/* 長文読解 小6 ―― 長文を読んで答える。本文は content/readings.js

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
["Who walks around the pond in the morning?","Old people.","Office workers.|Children.|Teachers.","小6","第二段落の1文目。","長文を読む","","en-e6-park"],
["Why did people write letters to the town office?","Because they wanted to keep the park.","Because they wanted a car park.|Because the park was too big.|Because the station was far.","小6","第三段落。","長文を読む","","en-e6-park"],
["Where was the car park built in the end?","Behind the station.","In the park.|Near the pond.|It was not built.","小6","最終文。","長文を読む","","en-e6-park"],
];

TubeContent.register({
  id:      'english/cho-e6',
  subject: 'english',
  name:    '長文読解 小6',
  note:    '長文を読んで答える。本文は content/readings.js',
  bands:   ['小6'],
  T:T, Q:Q
});

})();
