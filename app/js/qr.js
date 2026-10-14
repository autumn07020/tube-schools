/* ============================================================
   QR コードを作る（カードに刷る。読むと入口が開き、そのまま入れる）

   外の部品を使わない（合言葉を扱う画面に、よそのコードを入れない）。
   8ビットのバイト列・誤り訂正 M・型番 1〜10（213バイトまで）。入口の番地＋ID＋合言葉は 80バイトほど。
   DOM に触らない純粋な関数だけ。検査は app/tools/test-qr.sh（作った模様を、macOS の読み取りで読み直す）。

     TubeQR.matrix(text) → [[0/1,…],…]（1＝黒。まわりの余白は入っていない）
     TubeQR.svg(text, px) → '<svg …>'（余白 4 マスつき）
   ============================================================ */
(function(global){
"use strict";

var ECC_M    = [0, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26];   /* 1ブロックあたりの訂正語の数 */
var BLOCKS_M = [0,  1,  1,  1,  2,  2,  4,  4,  4,  5,  5];   /* ブロックの数 */
var ALIGN = [[], [], [6,18], [6,22], [6,26], [6,30], [6,34], [6,22,38], [6,24,42], [6,26,46], [6,28,50]];

function utf8(text){
  var s = unescape(encodeURIComponent(String(text))), out = [];
  for(var i = 0; i < s.length; i++) out.push(s.charCodeAt(i));
  return out;
}
function rawModules(v){
  var r = (16 * v + 128) * v + 64;
  if(v >= 2){ var n = Math.floor(v / 7) + 2; r -= (25 * n - 10) * n - 55; if(v >= 7) r -= 36; }
  return r;
}
function dataCodewords(v){ return Math.floor(rawModules(v) / 8) - ECC_M[v] * BLOCKS_M[v]; }

/* ガロア体 GF(2^8)（0x11D）の掛け算と、リード・ソロモンの余り */
function mul(x, y){
  var z = 0;
  for(var i = 7; i >= 0; i--){ z = (z << 1) ^ ((z >>> 7) * 0x11D); z ^= ((y >>> i) & 1) * x; }
  return z & 0xFF;
}
function rsDivisor(degree){
  var res = [], i, j, root = 1;
  for(i = 0; i < degree - 1; i++) res.push(0);
  res.push(1);
  for(i = 0; i < degree; i++){
    for(j = 0; j < res.length; j++){
      res[j] = mul(res[j], root);
      if(j + 1 < res.length) res[j] ^= res[j + 1];
    }
    root = mul(root, 2);
  }
  return res;
}
function rsRemainder(data, div){
  var res = div.map(function(){ return 0; });
  data.forEach(function(b){
    var f = b ^ res.shift();
    res.push(0);
    for(var i = 0; i < div.length; i++) res[i] ^= mul(div[i], f);
  });
  return res;
}

function codewords(bytes, v){
  var cap = dataCodewords(v), bits = [], i;
  function put(val, len){ for(var k = len - 1; k >= 0; k--) bits.push((val >>> k) & 1); }
  put(4, 4);                                   /* バイトの型 */
  put(bytes.length, v <= 9 ? 8 : 16);
  bytes.forEach(function(b){ put(b, 8); });
  put(0, Math.min(4, cap * 8 - bits.length));  /* 終わりの印 */
  put(0, (8 - bits.length % 8) % 8);
  for(var pad = 0xEC; bits.length < cap * 8; pad ^= 0xEC ^ 0x11) put(pad, 8);
  var data = [];
  for(i = 0; i < bits.length; i += 8){
    var b = 0; for(var k = 0; k < 8; k++) b = (b << 1) | bits[i + k];
    data.push(b);
  }
  /* ブロックに分け、訂正語を付け、1語ずつ交互に並べる */
  var nb = BLOCKS_M[v], ecl = ECC_M[v], raw = Math.floor(rawModules(v) / 8);
  var nShort = nb - raw % nb, shortLen = Math.floor(raw / nb), div = rsDivisor(ecl), blocks = [], k2 = 0;
  for(i = 0; i < nb; i++){
    var dat = data.slice(k2, k2 + shortLen - ecl + (i < nShort ? 0 : 1));
    k2 += dat.length;
    var ecc = rsRemainder(dat, div);
    if(i < nShort) dat.push(0);
    blocks.push(dat.concat(ecc));
  }
  var out = [];
  for(i = 0; i < blocks[0].length; i++){
    for(var j = 0; j < nb; j++){
      if(i !== shortLen - ecl || j >= nShort) out.push(blocks[j][i]);
    }
  }
  return out;
}

function build(bytes, v){
  var size = v * 4 + 17, mod = [], fn = [], x, y, i;
  for(y = 0; y < size; y++){ mod.push([]); fn.push([]); for(x = 0; x < size; x++){ mod[y].push(0); fn[y].push(0); } }
  function setF(xx, yy, dark){ mod[yy][xx] = dark ? 1 : 0; fn[yy][xx] = 1; }
  function bit(val, k){ return ((val >>> k) & 1) !== 0; }
  function finder(cx, cy){
    for(var dy = -4; dy <= 4; dy++) for(var dx = -4; dx <= 4; dx++){
      var d = Math.max(Math.abs(dx), Math.abs(dy)), xx = cx + dx, yy = cy + dy;
      if(xx >= 0 && xx < size && yy >= 0 && yy < size) setF(xx, yy, d !== 2 && d !== 4);
    }
  }
  function format(mask){
    var data = mask, rem = data, k;          /* 誤り訂正 M は 00 */
    for(k = 0; k < 10; k++) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
    var bits = ((data << 10) | rem) ^ 0x5412;
    for(k = 0; k <= 5; k++) setF(8, k, bit(bits, k));
    setF(8, 7, bit(bits, 6)); setF(8, 8, bit(bits, 7)); setF(7, 8, bit(bits, 8));
    for(k = 9; k < 15; k++) setF(14 - k, 8, bit(bits, k));
    for(k = 0; k < 8; k++) setF(size - 1 - k, 8, bit(bits, k));
    for(k = 8; k < 15; k++) setF(8, size - 15 + k, bit(bits, k));
    setF(8, size - 8, true);
  }
  for(i = 0; i < size; i++){ setF(6, i, i % 2 === 0); setF(i, 6, i % 2 === 0); }
  finder(3, 3); finder(size - 4, 3); finder(3, size - 4);
  var al = ALIGN[v], n = al.length;
  for(i = 0; i < n; i++) for(var j = 0; j < n; j++){
    if((i === 0 && j === 0) || (i === 0 && j === n - 1) || (i === n - 1 && j === 0)) continue;
    for(var dy = -2; dy <= 2; dy++) for(var dx = -2; dx <= 2; dx++)
      setF(al[i] + dx, al[j] + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
  }
  format(0);
  if(v >= 7){
    var rem = v;
    for(i = 0; i < 12; i++) rem = (rem << 1) ^ ((rem >>> 11) * 0x1F25);
    var vb = (v << 12) | rem;
    for(i = 0; i < 18; i++){
      var a = size - 11 + i % 3, b = Math.floor(i / 3);
      setF(a, b, bit(vb, i)); setF(b, a, bit(vb, i));
    }
  }
  /* 語を置く（右下から、2列ずつ上下に折り返す。縦の目盛りの列は飛ばす） */
  var cw = codewords(bytes, v), idx = 0;
  for(var right = size - 1; right >= 1; right -= 2){
    if(right === 6) right = 5;
    for(var vert = 0; vert < size; vert++){
      for(var jj = 0; jj < 2; jj++){
        x = right - jj;
        var up = ((right + 1) & 2) === 0;
        y = up ? size - 1 - vert : vert;
        if(!fn[y][x] && idx < cw.length * 8){ mod[y][x] = (cw[idx >>> 3] >>> (7 - (idx & 7))) & 1; idx++; }
      }
    }
  }
  function maskAt(m, xx, yy){
    switch(m){
      case 0: return (xx + yy) % 2 === 0;
      case 1: return yy % 2 === 0;
      case 2: return xx % 3 === 0;
      case 3: return (xx + yy) % 3 === 0;
      case 4: return (Math.floor(xx / 3) + Math.floor(yy / 2)) % 2 === 0;
      case 5: return xx * yy % 2 + xx * yy % 3 === 0;
      case 6: return (xx * yy % 2 + xx * yy % 3) % 2 === 0;
      default: return ((xx + yy) % 2 + xx * yy % 3) % 2 === 0;
    }
  }
  function apply(m){ for(var yy = 0; yy < size; yy++) for(var xx = 0; xx < size; xx++) if(!fn[yy][xx] && maskAt(m, xx, yy)) mod[yy][xx] ^= 1; }
  function penalty(){
    var p = 0, xx, yy, run, col, dark = 0;
    for(yy = 0; yy < size; yy++){
      for(var dir = 0; dir < 2; dir++){
        run = 0; col = -1;
        var hist = '';
        for(xx = 0; xx < size; xx++){
          var c = dir ? mod[xx][yy] : mod[yy][xx];
          hist += c;
          if(c === col){ run++; if(run === 5) p += 3; else if(run > 5) p++; }
          else{ col = c; run = 1; }
        }
        /* 目印（1:1:3:1:1）に似た並び */
        var at = -1;
        while((at = hist.indexOf('10111010000', at + 1)) >= 0) p += 40;
        at = -1;
        while((at = hist.indexOf('00001011101', at + 1)) >= 0) p += 40;
      }
    }
    for(yy = 0; yy < size - 1; yy++) for(xx = 0; xx < size - 1; xx++){
      var c0 = mod[yy][xx];
      if(c0 === mod[yy][xx + 1] && c0 === mod[yy + 1][xx] && c0 === mod[yy + 1][xx + 1]) p += 3;
    }
    for(yy = 0; yy < size; yy++) for(xx = 0; xx < size; xx++) dark += mod[yy][xx];
    var total = size * size;
    p += (Math.ceil(Math.abs(dark * 20 - total * 10) / total) - 1) * 10;
    return p;
  }
  var best = 0, bestP = Infinity;
  for(var m = 0; m < 8; m++){
    apply(m); format(m);
    var pp = penalty();
    if(pp < bestP){ bestP = pp; best = m; }
    apply(m);                                   /* もとに戻す */
  }
  apply(best); format(best);
  return mod;
}

function matrix(text){
  var bytes = utf8(text), v;
  for(v = 1; v <= 10; v++){
    if(bytes.length <= dataCodewords(v) - (v <= 9 ? 2 : 3)) break;
  }
  if(v > 10) throw new Error('QR に入りきりません（' + bytes.length + 'バイト）');
  return build(bytes, v);
}

function svg(text, px){
  var m = matrix(text), n = m.length, q = 4, d = '', x, y;
  for(y = 0; y < n; y++) for(x = 0; x < n; x++) if(m[y][x]) d += 'M' + (x + q) + ' ' + (y + q) + 'h1v1h-1z';
  var s = n + q * 2;
  return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + s + ' ' + s + '" width="' + (px || 120) + '" height="' + (px || 120) +
    '" shape-rendering="crispEdges" role="img" aria-label="QR"><rect width="' + s + '" height="' + s + '" fill="#fff"/><path d="' + d + '" fill="#000"/></svg>';
}

global.TubeQR = {matrix:matrix, svg:svg};
})(typeof window !== 'undefined' ? window : this);
