/* ============================================================
   マークシートを読む ―― 端末の中だけで
   ============================================================

   何をするか
   ----------
   カメラで撮った解答らんの写真から、塗ったマスを読み取る。

   **写真は端末の外に出さない。** サーバへ送らないし、保存もしない。
   読み取りが終わったら画像は捨てる。送らなければ、漏れることもない。

   なぜ文字認識をしないのか
   ------------------------
   手書きの文字をその場で読むには、外の認識サービスが要る。写真を
   外へ出すことになり、費用も通信も増える。

   だが **問題用紙はこちらが刷っている。** 決まった場所に決まった形の
   マスを置けば、読み取りは「どのマスが黒いか」を測るだけの話になる。
   これは計算だけでできる。学習も、外部の機械も要らない。

   手順
   ----
     1. 写真を扱いやすい大きさに縮める
     2. 明るさのむらを取り除く（部屋の影・紙の反り）
     3. 四隅の黒い正方形を見つける
     4. その4点から、紙の傾きと遠近を打ち消す変換を作る
     5. 決まった場所のマスの黒さを測り、いちばん黒いものを選ぶ

   読めなかったときは、読めなかったと言う。**当てずっぽうで丸を
   付けない** ―― まちがった採点は、採点しないより悪い。
   ============================================================ */
(function(global){
/* 小6以上は講師と同じ漢字で出す（TubeUI.jp）。TubeUI より先に読まれてもよいように。 */
function jp(kana, kanji){ var U = global.TubeUI; return (U && U.jp) ? U.jp(kana, kanji) : kana; }
"use strict";

/* 読み取りの大きさ。大きすぎると遅く、小さすぎるとマスがつぶれる。
   iPhone の写真（4032px）を 1200px に縮めても、5mm のマスは
   14px ほど残る ―― 黒さを測るには十分。 */
var WORK_W = 1200;

/* 塗ったと見なす線。
     ・いちばん黒いマスが、2番目より このぶん濃いこと
     ・かつ、紙の地の色より はっきり濃いこと
   両方を満たさなければ「無回答」にする。迷ったら選ばない。 */
var MIN_GAP = 0.10;
var MIN_DARK = 0.22;

/* ------------------------------------------------------------
   下ごしらえ
   ------------------------------------------------------------ */
function toGray(img, w, h){
  var c = document.createElement('canvas');
  c.width = w; c.height = h;
  var x = c.getContext('2d', {willReadFrequently:true});
  x.drawImage(img, 0, 0, w, h);
  var d = x.getImageData(0, 0, w, h).data;
  var g = new Float32Array(w * h);
  for(var i = 0, j = 0; i < d.length; i += 4, j++){
    /* 目に見える明るさに合わせる。単純な平均だと、赤い罫線が
       黒く出て、マークとまぎれる。 */
    g[j] = (0.299 * d[i] + 0.587 * d[i+1] + 0.114 * d[i+2]) / 255;
  }
  return g;
}

/* 明るさのむらを取る。
   紙の左半分だけ影になっている、という写真はふつうにある。
   全体で1つの線を引くと、影の側が丸ごと「黒い」になる。
   **まわりと比べて暗いかどうか**で見る。 */
function localMean(g, w, h, r){
  /* 積分画像を作って、どの大きさの窓でも同じ手間で平均を出す。 */
  var s = new Float64Array((w+1) * (h+1));
  for(var y = 0; y < h; y++){
    var run = 0;
    for(var x = 0; x < w; x++){
      run += g[y*w + x];
      s[(y+1)*(w+1) + (x+1)] = s[y*(w+1) + (x+1)] + run;
    }
  }
  return function(cx, cy, rr){
    rr = rr || r;
    var x0 = Math.max(0, cx-rr), y0 = Math.max(0, cy-rr);
    var x1 = Math.min(w, cx+rr+1), y1 = Math.min(h, cy+rr+1);
    var a = s[y1*(w+1) + x1] - s[y0*(w+1) + x1]
          - s[y1*(w+1) + x0] + s[y0*(w+1) + x0];
    var n = (x1-x0) * (y1-y0);
    return n ? a / n : 1;
  };
}

/* ------------------------------------------------------------
   四隅のマークを見つける
   ------------------------------------------------------------
   紙のどこにあるかは、おおよそ分かっている（四隅）。
   そこで **四隅それぞれの区画の中で、いちばん大きい黒いかたまり**を
   探す。画像ぜんぶを探すより速く、文字を取り違えることもない。 */
function findMarks(g, w, h){
  var mean = localMean(g, w, h, Math.round(Math.min(w,h) * 0.06));
  var dark = new Uint8Array(w * h);
  for(var y = 0; y < h; y++){
    for(var x = 0; x < w; x++){
      var i = y*w + x;
      /* まわりの平均より はっきり暗い画素だけを拾う */
      dark[i] = (g[i] < mean(x, y) - 0.18) ? 1 : 0;
    }
  }
  /* **紙のある場所を先に決める。**
     写真いっぱいに紙が写っているとは限らない。遠くから撮ると
     紙は真ん中の小さな四角になり、写真の四隅を探しても何も無い。
     実際、紙を端に寄せて小さく撮った写真で、位置合わせマークを
     1つも見つけられなかった。

     黒い画素はぜんぶ紙の上にある（机は一様な明るさで、局所平均より
     はっきり暗くはならない）。だから黒い画素の外接矩形が紙の範囲になる。
     そのうえで、**その矩形の四隅**を探す。 */
  var bx0 = w, by0 = h, bx1 = 0, by1 = 0, any = 0;
  for(var yy = 0; yy < h; yy++){
    for(var xx = 0; xx < w; xx++){
      if(!dark[yy*w + xx]) continue;
      any = 1;
      if(xx < bx0) bx0 = xx;
      if(xx > bx1) bx1 = xx;
      if(yy < by0) by0 = yy;
      if(yy > by1) by1 = yy;
    }
  }
  if(!any){ bx0 = 0; by0 = 0; bx1 = w - 1; by1 = h - 1; }
  /* すこし広げる ―― 外接矩形はマークの外縁で切れているので、
     ちょうどで切ると、かたまりが区画の境で分断される。 */
  var pad = Math.round(Math.min(w, h) * 0.02);
  bx0 = Math.max(0, bx0 - pad); by0 = Math.max(0, by0 - pad);
  bx1 = Math.min(w - 1, bx1 + pad); by1 = Math.min(h - 1, by1 + pad);
  var bw = bx1 - bx0 + 1, bh = by1 - by0 + 1;

  /* 四隅の区画。紙の3分の1ずつを見る。 */
  var qw = Math.max(8, Math.round(bw * 0.34));
  var qh = Math.max(8, Math.round(bh * 0.34));
  var quads = [
    [bx0, by0, bx0 + qw, by0 + qh],
    [bx1 - qw, by0, bx1, by0 + qh],
    [bx1 - qw, by1 - qh, bx1, by1],
    [bx0, by1 - qh, bx0 + qw, by1]
  ];
  var out = [];
  for(var q = 0; q < 4; q++){
    var got = biggestBlob(dark, w, h, quads[q]);
    if(!got) return null;
    out.push(got);
  }
  return out;
}

/* 区画の中でいちばん大きい黒いかたまりの重心。
   広がりを塗りつぶしながら数える（再帰にしない ―― 深くなると落ちる）。 */
function biggestBlob(dark, w, h, box){
  var x0 = box[0], y0 = box[1], x1 = box[2], y1 = box[3];
  var seen = new Uint8Array(w * h);
  var best = null;
  var stack = new Int32Array(1 << 18);
  for(var y = y0; y < y1; y++){
    for(var x = x0; x < x1; x++){
      var i0 = y*w + x;
      if(!dark[i0] || seen[i0]) continue;
      var sp = 0, n = 0, sx = 0, sy = 0;
      var bx0 = x, bx1 = x, by0 = y, by1 = y;
      stack[sp++] = i0; seen[i0] = 1;
      while(sp > 0 && n < 200000){
        var i = stack[--sp];
        var cy = (i / w) | 0, cx = i - cy*w;
        n++; sx += cx; sy += cy;
        if(cx < bx0) bx0 = cx; if(cx > bx1) bx1 = cx;
        if(cy < by0) by0 = cy; if(cy > by1) by1 = cy;
        var nb = [i-1, i+1, i-w, i+w];
        for(var k = 0; k < 4; k++){
          var j = nb[k];
          if(j < 0 || j >= w*h || seen[j] || !dark[j]) continue;
          var jy = (j / w) | 0, jx = j - jy*w;
          if(jx < x0 || jx >= x1 || jy < y0 || jy >= y1) continue;
          seen[j] = 1;
          if(sp < stack.length) stack[sp++] = j;
        }
      }
      /* 正方形に近いものだけを候補にする。
         罫線や影は細長いので、これで落ちる。 */
      var bw = bx1-bx0+1, bh = by1-by0+1;
      var fill = n / (bw*bh);
      var ratio = bw > bh ? bw/bh : bh/bw;
      if(n < 30 || fill < 0.55 || ratio > 1.9) continue;
      if(!best || n > best.n) best = {x:sx/n, y:sy/n, n:n, w:bw, h:bh};
    }
  }
  return best;
}

/* ------------------------------------------------------------
   遠近を打ち消す
   ------------------------------------------------------------
   紙を真上から撮ることはまず無い。斜めから撮った四角形を、
   もとの長方形へ戻す変換（射影変換）を4点から作る。
   8つの未知数の連立方程式を、そのまま解く。 */
function homography(src, dst){
  var A = [], b = [];
  for(var i = 0; i < 4; i++){
    var x = src[i][0], y = src[i][1], u = dst[i][0], v = dst[i][1];
    A.push([x, y, 1, 0, 0, 0, -u*x, -u*y]); b.push(u);
    A.push([0, 0, 0, x, y, 1, -v*x, -v*y]); b.push(v);
  }
  var m = solve(A, b);
  if(!m) return null;
  m.push(1);
  return m;
}

/* 掃き出し法。8×8なので、これで十分に速い。 */
function solve(A, b){
  var n = b.length;
  for(var i = 0; i < n; i++) A[i] = A[i].slice(), A[i].push(b[i]);
  for(var c = 0; c < n; c++){
    var piv = c;
    for(var r = c+1; r < n; r++)
      if(Math.abs(A[r][c]) > Math.abs(A[piv][c])) piv = r;
    if(Math.abs(A[piv][c]) < 1e-9) return null;
    var t = A[c]; A[c] = A[piv]; A[piv] = t;
    for(var r2 = 0; r2 < n; r2++){
      if(r2 === c) continue;
      var f = A[r2][c] / A[c][c];
      for(var k = c; k <= n; k++) A[r2][k] -= f * A[c][k];
    }
  }
  var out = [];
  for(var i2 = 0; i2 < n; i2++) out.push(A[i2][n] / A[i2][i2]);
  return out;
}

function apply(m, x, y){
  var d = m[6]*x + m[7]*y + m[8];
  return [(m[0]*x + m[1]*y + m[2]) / d, (m[3]*x + m[4]*y + m[5]) / d];
}

/* ------------------------------------------------------------
   読む
   ------------------------------------------------------------ */
/* マスの中心（位置合わせ四角形の中での 0〜1 の座標）。
   刷る側（server/prepsheet.py の SHEET）と同じ式で出す。
   **式を2か所に書かない** ―― 寸法はサーバから受け取る。 */
function bubbleAt(g, i, opt){
  var c = i % g.cols, r = (i / g.cols) | 0;
  var cw = g.gridW / g.cols, ch = g.gridH / g.rows;
  var x = g.gridX0 + cw * (c + g.bubX0 + g.bubDX * opt);
  var y = g.gridY0 + ch * (r + 0.5);
  return [x, y];
}

/* 写真1枚を読む。
   返すのは
     {ok:true, marks:[…], answers:[番号ごとの 0〜3 または -1], debug:{…}}
     {ok:false, why:"…"}                     読めなかった理由 */
function read(img, geom, count){
  var iw = img.naturalWidth || img.videoWidth || img.width;
  var ih = img.naturalHeight || img.videoHeight || img.height;
  if(!iw || !ih) return {ok:false, why:'写真が読めませんでした'};
  var w = Math.min(WORK_W, iw);
  var h = Math.round(ih * (w / iw));
  var g = toGray(img, w, h);

  var marks = findMarks(g, w, h);
  if(!marks) return {ok:false, why:jp('四すみの黒い四角が見つかりません','四隅の黒い四角が見つかりません')};

  /* 見つけた4点を、左上→右上→右下→左下 の順に並べ直す。 */
  marks.sort(function(a, b){ return a.y - b.y; });
  var top = marks.slice(0,2).sort(function(a,b){ return a.x-b.x; });
  var bot = marks.slice(2,4).sort(function(a,b){ return a.x-b.x; });
  var src = [[top[0].x, top[0].y], [top[1].x, top[1].y],
             [bot[1].x, bot[1].y], [bot[0].x, bot[0].y]];

  /* 4点が小さすぎる・つぶれているときは、写真が遠いか暗い。 */
  var side = Math.hypot(src[1][0]-src[0][0], src[1][1]-src[0][1]);
  if(side < w * 0.35) return {ok:false, why:jp('紙を もう少し大きく写してください','紙をもう少し大きく写してください')};

  var m = homography([[0,0],[1,0],[1,1],[0,1]], src);
  if(!m) return {ok:false, why:'紙の形が読み取れません'};

  var mean = localMean(g, w, h, Math.round(Math.min(w,h) * 0.05));
  var rr = Math.max(2, Math.round(side * geom.bubR * geom.gridW / geom.cols));

  var answers = [], conf = [];
  for(var i = 0; i < count; i++){
    var vals = [];
    for(var o = 0; o < geom.opts; o++){
      var uv = bubbleAt(geom, i, o);
      var p = apply(m, uv[0], uv[1]);
      var px = Math.round(p[0]), py = Math.round(p[1]);
      if(px < 0 || py < 0 || px >= w || py >= h){ vals.push(0); continue; }
      /* まわりの紙の色を基準に、どれだけ暗いか。
         0 = 紙と同じ、1 = 真っ黒。 */
      var paper = mean(px, py, rr * 4);
      var ink = mean(px, py, rr);
      vals.push(Math.max(0, paper - ink));
    }
    var order = vals.map(function(v, k){ return [v, k]; })
                    .sort(function(a, b){ return b[0] - a[0]; });
    var top1 = order[0], top2 = order[1] || [0,0];
    if(top1[0] < MIN_DARK || (top1[0] - top2[0]) < MIN_GAP){
      answers.push(-1);                 /* 迷ったら選ばない */
    }else{
      answers.push(top1[1]);
    }
    conf.push(Math.round((top1[0] - top2[0]) * 100) / 100);
  }
  return {ok:true, answers:answers, conf:conf,
          marks:src, size:[w, h]};
}

global.TubeOMR = {read:read, bubbleAt:bubbleAt, homography:homography,
                  apply:apply, WORK_W:WORK_W};

})(window);
