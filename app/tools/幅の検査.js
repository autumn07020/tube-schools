/* 幅ごとの崩れを、目ではなく数で見つける。

   使い方 ―― ブラウザの検査窓（コンソール）にこの中身を貼る。
   何も出なければ合格。

   なぜ目で見ないか
   ----------------
   崩れは「ある幅でだけ」出る。作っている最中の幅では出ないので、
   画面を見ている限り気づけない。実際、1024〜1439px でだけ
   カレンダーと教科の帯が重なっていたことがある。

   iframe に並べて見ることはできない ―― このアプリは
   frame-ancestors 'none' を返している（クリックジャッキング除け）。
   代わりに **入れ物の幅を直に変える**。折り返しは全部 @container で
   書いてあるので、入れ物を細くすれば細い画面と同じ見え方になる。 */
(function(){
  var WIDTHS = [390, 430, 520, 560, 620, 700, 834, 900, 1024, 1280, 1600, 2000];
  var m = document.querySelector('#main');
  if(!m){ console.log('#main が無い'); return; }
  var keep = m.style.width, bad = [];

  /* 最後の行の右にどれだけ空きが残るか。20px を超えたら歯抜け。
     歯抜けは「そこにまだ何かあるはず」と読まれる。 */
  function gapOf(g){
    var gr = g.getBoundingClientRect();
    var ks = [].map.call(g.children, function(c){ return c.getBoundingClientRect(); });
    if(!ks.length) return 0;
    var lastTop = Math.max.apply(null, ks.map(function(k){ return k.top; }));
    var row = ks.filter(function(k){ return Math.abs(k.top - lastTop) < 2; });
    return Math.round(gr.right - Math.max.apply(null, row.map(function(k){ return k.right; })));
  }

  /* ① 本体が「中身の幅」まで縮んでいないか。
     #app は縦の flex で、main は横いっぱいに伸ばされている。
     そこへ margin:auto を足すと伸長が止まり、画面が縦の細い帯になる。
     一度これで全ページを壊した。**幅を測って気づけるようにしておく。** */
  (function(){
    var app = document.querySelector('#app');
    if(!app) return;
    var avail = Math.min(1320, app.getBoundingClientRect().width - 148);
    var got = m.getBoundingClientRect().width;
    if(avail > 0 && got < avail - 4){
      bad.push('本体が ' + Math.round(got) + 'px しかない（' +
               Math.round(avail) + 'px あるはず）。' +
               'main に width:100% があるか確かめること');
    }
  })();

  WIDTHS.forEach(function(w){
    m.style.width = w + 'px';
    document.querySelectorAll('.wgrid, .wgrid4, .sublist, .cells').forEach(function(g){
      var d = gapOf(g);
      if(d > 20) bad.push(w + 'px  ' + g.className.split(' ')[0] + ' の右に ' + d + 'px の空き');
    });
    if(m.scrollWidth > w + 1) bad.push(w + 'px  横にはみ出している（' + m.scrollWidth + 'px）');
  });
  m.style.width = keep;

  if(bad.length) bad.forEach(function(x){ console.log('×  ' + x); });
  else console.log('○  ' + WIDTHS.length + 'つの幅、すべて歯抜けもはみ出しも無し');
})();
