/* 紙がA4に収まっているかを、目ではなく数で確かめる。

   使い方 ―― 対策テストの紙を開いて、ブラウザの検査窓（コンソール）に
   この中身を貼る。何も出なければ合格。

   なぜ目で見ないか
   ----------------
   1枚が297mmを超えていても、画面では「少し長い紙」にしか見えない。
   刷ってはじめて2ページに割れていることが分かる。実際、
   問題用紙が694mm（A4 2.3枚分）の1枚ものとして出ていたのに、
   画面を見ているかぎり気づけなかった。

   何を見るか
   ----------
   ・1枚ごとの高さが 297mm を超えていないか（超えると刷って割れる）
   ・枚数が10枚を超えていないか
   ・段からはみ出した問題が無いか
   ・長文の本文が、同じ紙に2回出ていないか            */
(function(){
  var MM = 96 / 25.4, PAGE = 297, LIMIT = 10, bad = [];
  var sheets = document.querySelectorAll('.sheet');
  if(!sheets.length){ console.log('紙が見つかりません'); return; }

  Array.prototype.forEach.call(sheets, function(s, i){
    var h = Math.round(s.getBoundingClientRect().height / MM);
    if(h > PAGE + 1) bad.push((i + 1) + '枚目が ' + h + 'mm（A4は297mm）');
    Array.prototype.forEach.call(s.querySelectorAll('.col'), function(c){
      var ch = c.getBoundingClientRect().height;
      var box = s.getBoundingClientRect();
      if(c.getBoundingClientRect().bottom > box.bottom + 1){
        bad.push((i + 1) + '枚目の段が 紙からはみ出しています');
      }
    });
  });
  if(sheets.length > LIMIT) bad.push('全部で ' + sheets.length + '枚（上限 ' + LIMIT + '枚）');

  /* 長文が「下限まで詰めても入らない」ままになっていないか。
     入らない本文は、紙で調整する話ではなく **教材が長すぎる**。 */
  var tl = document.querySelectorAll('.bun[data-toolong]');
  if(tl.length) bad.push('長すぎて入らない本文 ' + tl.length + '本'
    + '（教材を短くしてください）');
  var fit = document.querySelectorAll('.bun[data-fit]');
  if(fit.length){
    var sizes = [];
    Array.prototype.forEach.call(fit, function(b){
      sizes.push(b.getAttribute('data-fit'));
    });
    console.log('・詰めた本文 ' + fit.length + '本 → ' + sizes.join(', ')
      + '（10.5pt が標準。下限は 8.5pt）');
  }

  var seen = {};
  Array.prototype.forEach.call(document.querySelectorAll('.bun'), function(b){
    var k = (b.textContent || '').slice(0, 40);
    if(seen[k]) bad.push('同じ長文が 2回 出ています: ' + k);
    seen[k] = 1;
  });

  if(bad.length){ bad.forEach(function(m){ console.warn('×  ' + m); }); }
  else console.log('OK  ' + sheets.length + '枚、すべて A4 に収まっています');
})();
