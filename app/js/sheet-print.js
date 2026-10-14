/* 問題用紙 ―― A4 への割りつけと「PDFにする」。

   **インラインの onclick は使えない。**
   このアプリは script-src 'self' を返しているので、HTML に直接書いた
   onclick は実行されない。実際、押しても何も起きないという形で出た
   （画面には何のエラーも出ない ―― CSP は黙って落とす）。
   だから別ファイルにして、src で読み込む。

   ------------------------------------------------------------------
   なぜ割りつけを JavaScript でやるか
   ------------------------------------------------------------------
   前は CSS の columns:2 に流し込み、ページの切れ目はブラウザに
   まかせていた。その結果、

     ・画面では 694mm（A4 2.3枚分）の**1本の長い紙**になっていた
     ・紙のほうも、段組みをページにまたがせる処理はブラウザごとに
       ちがう。Safari と Chrome で同じ結果になる保証がない

   問題の高さは中身で変わる（図のある問題は3倍の高さになる）ので、
   サーバ側で「1問17mm」のように見積もると必ず外れる。実際、
   その見積もりで3回作り直している。

   だから **実際に置いてみて、はみ出したら次へ送る**。
   ブラウザ自身が出した高さを使うので、どのブラウザでも
   画面で見えているとおりに刷れる。

   割りつけができなかったとき（この JS が読めなかったときも含めて）は、
   もとの1枚もののまま出る。**刷れなくなるよりはよい。** */
(function(){
  "use strict";

  var MM = 96 / 25.4;                 // 1mm が何 px か（CSS の基準）
  var PAGE_H = 297 * MM;              // A4 たての高さ
  var MARGIN = 12 * MM;               // @page の余白と同じ
  var USABLE = PAGE_H - MARGIN * 2;   // 中身に使える高さ 273mm

  function el(tag, cls){
    var e = document.createElement(tag);
    if(cls) e.className = cls;
    return e;
  }

  /* 1枚ぶんの入れもの。1ページ目だけ、もとの大きな見出しを持つ。
     脚（TUBE study／何枚目）は**どのページにも付ける** ――
     付けておけば、その上端がそのまま「中身に使える高さ」になる。 */
  function newPage(title, first, footText, layout){
    var p = el('div', 'sheet page' + (layout === 'tate' ? ' tate' : ''));
    if(!first){
      var h = el('div', 'rhead');
      var a = el('span'); a.textContent = title || '';
      var b = el('span'); b.className = 'pn';
      h.appendChild(a); h.appendChild(b);
      p.appendChild(h);
    }
    /* 組み方。tate は縦書き1段（国語）、one は横書き1段（数学）、
       それ以外は横書き2段。 */
    var cls = 'cols2' + (layout === 'one' ? ' one'
                       : layout === 'tate' ? ' tate' : '');
    var cols = el('div', cls);
    cols.appendChild(el('div', 'col'));
    if(layout === 'two') cols.appendChild(el('div', 'col'));
    p.appendChild(cols);
    var f = el('div', 'foot');
    var l = el('span'); l.textContent = footText || 'TUBE study';
    var r = el('span'); r.className = 'pn';
    f.appendChild(l); f.appendChild(r);
    p.appendChild(f);
    return p;
  }

  function paginate(sheet){
    var flow = sheet.querySelector('.cols');
    if(!flow) return [];
    var items = Array.prototype.slice.call(flow.children);
    if(!items.length) return [];

    var title = sheet.getAttribute('data-title') || '';
    var layout = sheet.getAttribute('data-layout') || 'two';
    var tate = layout === 'tate';
    var oldFoot = sheet.querySelector('.foot');
    var footText = oldFoot ? (oldFoot.firstChild &&
                              oldFoot.firstChild.textContent) : '';
    /* 1ページ目に残す見出し。**もとの順のまま**移す
       （前は逆順に差し込んでいて、脚が先頭に来ていた）。 */
    var head = [];
    Array.prototype.forEach.call(sheet.children, function(c){
      if(c === flow || c === oldFoot) return;
      head.push(c);
    });

    var pages = [], page = null, cols = null, ci = 0, avail = 0;
    var parent = sheet.parentNode;
    var anchor = sheet.nextSibling;

    function pushPage(first){
      page = newPage(title, first, footText, layout);
      if(first){
        var before = page.firstChild;
        head.forEach(function(c){ page.insertBefore(c, before); });
      }
      pages.push(page);
      parent.insertBefore(page, anchor);
      cols = page.querySelectorAll('.col');
      ci = 0;
      /* **その場で測る。計算しない。**
         横書きは 脚の上端までが 中身の場所。1ページ目は大きな見出しが
         ある分だけ短くなる ―― それも測れる。
         縦書きは **伸びる向きが90度ちがう**。行は上から下へ流れ、
         はみ出すと 左へ折り返す。だから見るのは 高さではなく幅。 */
      var box = page.querySelector('.cols2').getBoundingClientRect();
      if(tate){
        avail = box.width - 2;
      }else{
        avail = page.querySelector('.foot').getBoundingClientRect().top
                - box.top - 2;
      }
    }
    pushPage(true);

    /* 1問ずつ置いて、段からはみ出したら次の段・次のページへ送る。
       **置いてから測る。** 図のある問題は3倍の高さになるので、
       置く前に見積もっても当たらない（実際3回作り直している）。 */
    for(var i = 0; i < items.length; i++){
      var q = items[i];
      cols[ci].appendChild(q);
      if(fits(cols[ci], avail, tate)) continue;
      /* **その段の1問目なら、送らない。**
         送っても入る場所は無いのに、送ると空のページが1枚できる。
         実際、長文が入りきらず 1枚目が まるごと白紙になった。
         代わりに、その1問の中の長文だけを 詰めて入れる。 */
      if(cols[ci].children.length <= 1){ shrink(q, cols[ci], avail, tate); continue; }
      cols[ci].removeChild(q);
      ci++;
      if(ci >= cols.length) pushPage(false);
      cols[ci].appendChild(q);
      if(!fits(cols[ci], avail, tate)) shrink(q, cols[ci], avail, tate);
    }
    parent.removeChild(sheet);
    return pages;
  }

  function fits(col, avail, tate){
    return (tate ? col.scrollWidth : col.scrollHeight) <= avail;
  }

  /* 入りきらない長文を、**測りながら**必要なぶんだけ詰める。

     ------------------------------------------------------------------
     なぜ CSS に数字を書かないか
     ------------------------------------------------------------------
     教材は入れ替わる。いま入っている「やまなし」に合わせて 8.5pt と
     書くと、次に入る 1500字の本文では入りきらず、逆に 300字の本文では
     無意味に小さくなる。**教材ごとに長さが違うので、1つの数字は必ず外れる。**

     だから紙は「読める組版」（10.5pt・行間1.9）から始めて、
     入らなかったときだけ 1段ずつ落とす。落とす順は
     行間 → 字の大きさ で、**行間から先に詰める** ―― 字を小さくするより
     行間を詰めるほうが、読みやすさの減り方が小さい。

     下限（8.5pt・行間1.45）より下げない。そこまで詰めても入らない本文は
     **教材が長すぎる**のであって、紙で調整する話ではない。
     そのときは詰めるのをやめ、app/tools/紙の検査.js が知らせる。 */
  var STEPS = [
    {size:'10.5pt', lh:'1.9'},
    {size:'10.5pt', lh:'1.7'},
    {size:'10pt',   lh:'1.7'},
    {size:'9.5pt',  lh:'1.6'},
    {size:'9pt',    lh:'1.5'},
    {size:'8.5pt',  lh:'1.45'}
  ];

  function shrink(q, col, avail, tate){
    var bun = q.querySelector && q.querySelector('.bun');
    if(!bun) return false;
    for(var i = 1; i < STEPS.length; i++){
      bun.style.fontSize = STEPS[i].size;
      bun.style.lineHeight = STEPS[i].lh;
      if(fits(col, avail, tate)){
        bun.setAttribute('data-fit', STEPS[i].size);
        return true;
      }
    }
    /* 下限まで詰めても入らない。**そこで止める。**
       これ以上小さくすると読めない紙になる。印を残して、検査に拾わせる。 */
    bun.setAttribute('data-toolong', '1');
    return false;
  }

  function run(){
    var sheets = document.querySelectorAll('.sheet[data-paged="1"]');
    if(!sheets.length) return;
    var made = [];
    Array.prototype.forEach.call(sheets, function(s){
      try{ made = made.concat(paginate(s)); }
      catch(e){ /* 割りつけできなければ、もとのまま出す */ }
    });
    /* 何枚目かを入れる。**枚数は刷る前に見えていたほうがよい。** */
    var all = document.querySelectorAll('.sheet');
    var n = all.length;
    Array.prototype.forEach.call(all, function(s, i){
      Array.prototype.forEach.call(s.querySelectorAll('.pn'), function(pn){
        pn.textContent = (i + 1) + ' / ' + n;
      });
    });
  }

  function go(){ try{ window.print(); }catch(e){} }

  document.addEventListener('click', function(ev){
    var b = ev.target.closest && ev.target.closest('[data-print]');
    if(b){ ev.preventDefault(); go(); }
  });

  /* 割りつけは、絵や字がそろってから。**刷る前に必ず終わらせる。** */
  function ready(fn){
    if(document.readyState === 'complete') fn();
    else addEventListener('load', fn);
  }
  ready(function(){
    run();
    if(/[?&]print=1(&|$)/.test(location.search)) setTimeout(go, 400);
  });
  /* 押したときにまだ割りつけ前だったら、そこで済ませてから刷る。 */
  addEventListener('beforeprint', function(){ run(); });
})();
