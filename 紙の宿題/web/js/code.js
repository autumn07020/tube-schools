/* ============================================================
   番号シールの印 ―― 刷る・読む（端末の中だけ。画面にも通信にも触らない純粋な関数）
   ============================================================

   形（13×13 のマス。外に1マスの白い余白）
     ・外周1マス：黒い枠（見つけるための印）
     ・その内側1マス：白いすき間（枠と中身がくっつかないように）
     ・中の 9×9 = 81 マス：中身（黒＝1）

   中身（81ビット）
     0-1   種類   1 = 生徒（ノートの表紙・区切り紙に貼る。**その紙は送らない**）
                  2 = 答案用紙（こちらで刷った紙。**その紙を送る**）
     2-41  sid    8文字 × 5ビット（tubestudy の sid の文字 23456789ABCDEFGHJKLMNPQRSTUVWXYZ）
     42-49 用紙の型（答案用紙だけ。問題の数と枠の大きさ）
     50-52 ページ（答案用紙だけ）
     53-64 予備（すべて 0。読むときに 0 でなければ捨てる）
     65-80 CRC-16（0-64 の検算）

   なぜ QR にしないか：自分で刷って平らなまま読むので、QR の誤り訂正は要らない。
   枠を見つけ、4方向を試し、検算（CRC）と予備の 0 が合ったものだけを信じる。
   **読めなければ読めないと言う。当てずっぽうで生徒を決めない**（tubestudy の omr.js と同じ決まり）。
   ============================================================ */
(function(root){
"use strict";
var ALPH = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ";
var M = 13, D = 9, NB = 81;

function crc16(bits, n){
  var crc = 0xFFFF;
  for(var i = 0; i < n; i++){
    var top = (crc >> 15) & 1;
    crc = (crc << 1) & 0xFFFF;
    if(top ^ bits[i]) crc ^= 0x1021;
  }
  return crc;
}
function put(bits, at, v, n){ for(var i = 0; i < n; i++) bits[at + i] = (v >> (n - 1 - i)) & 1; }
function get(bits, at, n){ var v = 0; for(var i = 0; i < n; i++) v = (v << 1) | bits[at + i]; return v; }

function canEncode(sid){
  sid = String(sid || "");
  if(sid.length !== 8) return false;
  for(var i = 0; i < 8; i++) if(ALPH.indexOf(sid[i]) < 0) return false;
  return true;
}

/* 中身 → 81ビット。sid が形に合わなければ null。 */
function bitsOf(p){
  if(!canEncode(p.sid)) return null;
  var b = new Array(NB); for(var i = 0; i < NB; i++) b[i] = 0;
  put(b, 0, p.type & 3, 2);
  for(var k = 0; k < 8; k++) put(b, 2 + k * 5, ALPH.indexOf(p.sid[k]), 5);
  put(b, 42, (p.tmpl || 0) & 255, 8);
  put(b, 50, (p.page || 0) & 7, 3);
  put(b, 65, crc16(b, 65), 16);
  return b;
}

/* 81ビット → 中身。検算が合わなければ null。 */
function parse(b){
  if(crc16(b, 65) !== get(b, 65, 16)) return null;
  if(get(b, 53, 12) !== 0) return null;
  var type = get(b, 0, 2);
  if(type !== 1 && type !== 2) return null;
  var sid = "";
  for(var k = 0; k < 8; k++) sid += ALPH[get(b, 2 + k * 5, 5)];
  return {type:type, sid:sid, tmpl:get(b, 42, 8), page:get(b, 50, 3)};
}

/* 13×13 の行列（1＝黒） */
function matrix(p){
  var b = bitsOf(p);
  if(!b) return null;
  var m = [];
  for(var r = 0; r < M; r++){
    var row = [];
    for(var c = 0; c < M; c++){
      var v;
      if(r === 0 || c === 0 || r === M - 1 || c === M - 1) v = 1;
      else if(r === 1 || c === 1 || r === M - 2 || c === M - 2) v = 0;
      else v = b[(r - 2) * D + (c - 2)];
      row.push(v);
    }
    m.push(row);
  }
  return m;
}

/* 刷るための SVG（外に1マスの白い余白つき。単位はマス。大きさは呼ぶ側の CSS で決める）。 */
function svg(p, label){
  var m = matrix(p);
  if(!m) return "";
  var s = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + (M + 2) + ' ' + (M + 2) +
          '" shape-rendering="crispEdges"' + (label ? ' aria-label="' + label + '"' : '') + '>' +
          '<rect width="' + (M + 2) + '" height="' + (M + 2) + '" fill="#fff"/><path fill="#000" d="';
  for(var r = 0; r < M; r++) for(var c = 0; c < M; c++){
    if(m[r][c]) s += "M" + (c + 1) + " " + (r + 1) + "h1v1h-1z";
  }
  return s + '"/></svg>';
}

/* ---------- 読む ---------- */

/* 射影変換：単位の4点 → 画像の4点。src/dst は [[x,y]×4]。 */
function homography(src, dst){
  var A = [], bb = [];
  for(var i = 0; i < 4; i++){
    var x = src[i][0], y = src[i][1], u = dst[i][0], v = dst[i][1];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); bb.push(u);
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); bb.push(v);
  }
  var h = solve(A, bb);
  if(!h) return null;
  h.push(1);
  return h;
}
function solve(A, b){
  var n = b.length, i, j, k;
  for(i = 0; i < n; i++) A[i] = A[i].concat([b[i]]);
  for(i = 0; i < n; i++){
    var mx = i;
    for(j = i + 1; j < n; j++) if(Math.abs(A[j][i]) > Math.abs(A[mx][i])) mx = j;
    if(Math.abs(A[mx][i]) < 1e-12) return null;
    var t = A[i]; A[i] = A[mx]; A[mx] = t;
    for(j = 0; j < n; j++){
      if(j === i) continue;
      var f = A[j][i] / A[i][i];
      for(k = i; k <= n; k++) A[j][k] -= f * A[i][k];
    }
  }
  var out = [];
  for(i = 0; i < n; i++) out.push(A[i][n] / A[i][i]);
  return out;
}
function apply(h, x, y){
  var w = h[6] * x + h[7] * y + h[8];
  return [(h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w];
}
function sample(g, w, hgt, x, y){
  if(x < 0 || y < 0 || x > w - 1 || y > hgt - 1) return 1;
  var x0 = Math.floor(x), y0 = Math.floor(y), x1 = Math.min(x0 + 1, w - 1), y1 = Math.min(y0 + 1, hgt - 1);
  var fx = x - x0, fy = y - y0;
  return g[y0 * w + x0] * (1 - fx) * (1 - fy) + g[y0 * w + x1] * fx * (1 - fy) +
         g[y1 * w + x0] * (1 - fx) * fy + g[y1 * w + x1] * fx * fy;
}
/* マス (r, c) の中ほどの明るさ（5点の平均） */
function cell(g, w, hgt, h, r, c){
  var s = 0, d = [[0, 0], [-.22, 0], [.22, 0], [0, -.22], [0, .22]];
  for(var i = 0; i < 5; i++){
    var p = apply(h, c + .5 + d[i][0], r + .5 + d[i][1]);
    s += sample(g, w, hgt, p[0], p[1]);
  }
  return s / 5;
}
function rotCW(m){
  var n = m.length, o = [];
  for(var i = 0; i < n; i++){ o.push([]); for(var j = 0; j < n; j++) o[i].push(m[n - 1 - j][i]); }
  return o;
}

/* 4隅（左上・右上・右下・左下）から読む。返す {type, sid, tmpl, page, turns, corners, size} か null。
   turns … 印をまっすぐにするには、画像を右に何回（90°ずつ）回せばよいか。 */
function readAt(g, w, hgt, corners){
  var h = homography([[0, 0], [M, 0], [M, M], [0, M]], corners);
  if(!h) return null;
  var blk = 0, wht = 0, nb = 0, nw = 0, r, c;
  for(var k = 0; k < M; k++){
    [[0, k], [M - 1, k], [k, 0], [k, M - 1]].forEach(function(p){ blk += cell(g, w, hgt, h, p[0], p[1]); nb++; });
  }
  for(k = 1; k < M - 1; k++){
    [[1, k], [M - 2, k], [k, 1], [k, M - 2]].forEach(function(p){ wht += cell(g, w, hgt, h, p[0], p[1]); nw++; });
  }
  blk /= nb; wht /= nw;
  if(wht - blk < 0.22) return null;                  // 枠とすき間の差が小さい＝印ではない
  var mid = (blk + wht) / 2, obs = [];
  for(r = 0; r < D; r++){
    obs.push([]);
    for(c = 0; c < D; c++) obs[r].push(cell(g, w, hgt, h, r + 2, c + 2) < mid ? 1 : 0);
  }
  var cand = obs;
  for(var t = 0; t < 4; t++){
    var bits = [];
    for(r = 0; r < D; r++) for(c = 0; c < D; c++) bits.push(cand[r][c]);
    var p = parse(bits);
    if(p){
      var dx = corners[1][0] - corners[0][0], dy = corners[1][1] - corners[0][1];
      p.turns = t; p.corners = corners; p.size = Math.sqrt(dx * dx + dy * dy); p.contrast = wht - blk;
      return p;
    }
    cand = rotCW(cand);
  }
  return null;
}

/* 暗い画素の2値（大きな窓の平均より暗く、しかも 0.55 より暗い）。窓は画像の短辺の 1/8。 */
function binarize(g, w, hgt){
  var r = Math.max(8, Math.round(Math.min(w, hgt) / 8));
  var W = w + 1, s = new Float64Array(W * (hgt + 1)), x, y;
  for(y = 0; y < hgt; y++){
    var run = 0;
    for(x = 0; x < w; x++){ run += g[y * w + x]; s[(y + 1) * W + x + 1] = s[y * W + x + 1] + run; }
  }
  var out = new Uint8Array(w * hgt);
  for(y = 0; y < hgt; y++){
    var y0 = Math.max(0, y - r), y1 = Math.min(hgt, y + r + 1);
    for(x = 0; x < w; x++){
      var x0 = Math.max(0, x - r), x1 = Math.min(w, x + r + 1);
      var mean = (s[y1 * W + x1] - s[y0 * W + x1] - s[y1 * W + x0] + s[y0 * W + x0]) / ((x1 - x0) * (y1 - y0));
      var v = g[y * w + x];
      out[y * w + x] = (v < mean - 0.12 && v < 0.55) ? 1 : 0;
    }
  }
  return out;
}

/* 暗いかたまり（4方向につながったもの）に番号を振り、枠らしいものを返す。 */
function rings(bin, w, hgt){
  var lab = new Int32Array(w * hgt), parent = [0], x, y, i;
  function find(a){ while(parent[a] !== a){ parent[a] = parent[parent[a]]; a = parent[a]; } return a; }
  for(y = 0; y < hgt; y++) for(x = 0; x < w; x++){
    i = y * w + x;
    if(!bin[i]) continue;
    var up = y > 0 ? lab[i - w] : 0, lf = x > 0 ? lab[i - 1] : 0;
    if(up && lf){
      var a = find(up), b = find(lf);
      lab[i] = Math.min(a, b);
      if(a !== b) parent[Math.max(a, b)] = Math.min(a, b);
    }else if(up || lf) lab[i] = up || lf;
    else { lab[i] = parent.length; parent.push(parent.length); }
  }
  var st = {};
  for(y = 0; y < hgt; y++) for(x = 0; x < w; x++){
    i = y * w + x;
    if(!lab[i]) continue;
    var L = lab[i] = find(lab[i]);
    var s = st[L];
    if(!s) s = st[L] = {n:0, x0:x, x1:x, y0:y, y1:y, tl:[x, y, x + y], br:[x, y, x + y], tr:[x, y, x - y], bl:[x, y, x - y]};
    s.n++;
    if(x < s.x0) s.x0 = x; if(x > s.x1) s.x1 = x; if(y < s.y0) s.y0 = y; if(y > s.y1) s.y1 = y;
    if(x + y < s.tl[2]) s.tl = [x, y, x + y];
    if(x + y > s.br[2]) s.br = [x, y, x + y];
    if(x - y > s.tr[2]) s.tr = [x, y, x - y];
    if(x - y < s.bl[2]) s.bl = [x, y, x - y];
  }
  var out = [];
  Object.keys(st).forEach(function(k){
    var s = st[k], bw = s.x1 - s.x0 + 1, bh = s.y1 - s.y0 + 1;
    if(bw < 26 || bh < 26 || bw > w * 0.95 || bh > hgt * 0.95) return;
    var asp = bw / bh;
    if(asp < 0.5 || asp > 2) return;
    var fill = s.n / (bw * bh);
    if(fill < 0.1 || fill > 0.55) return;
    var cx = Math.round((s.x0 + s.x1) / 2), cy = Math.round((s.y0 + s.y1) / 2);
    if(lab[cy * w + cx] === +k) return;              // 真ん中が同じかたまり＝穴が無い
    out.push({corners:[[s.tl[0], s.tl[1]], [s.tr[0] + 1, s.tr[1]], [s.br[0] + 1, s.br[1] + 1], [s.bl[0], s.bl[1] + 1]],
              area:bw * bh});
  });
  out.sort(function(a, b){ return b.area - a.area; });
  return out;
}

/* 灰色の画像（0〜1 の Float32Array, 幅, 高さ）から印を探して読む。見つかった全部（大きい順）。 */
function find(g, w, hgt, limit){
  var bin = binarize(g, w, hgt);
  var cands = rings(bin, w, hgt).slice(0, limit || 40);
  var out = [];
  for(var i = 0; i < cands.length; i++){
    var p = readAt(g, w, hgt, cands[i].corners);
    if(p && !out.some(function(q){ return q.sid === p.sid && q.type === p.type &&
        Math.abs(q.corners[0][0] - p.corners[0][0]) < 4 && Math.abs(q.corners[0][1] - p.corners[0][1]) < 4; })) out.push(p);
  }
  return out;
}

root.PaperCode = {ALPH:ALPH, MODULES:M, canEncode:canEncode, bitsOf:bitsOf, parse:parse, matrix:matrix, svg:svg,
                  find:find, readAt:readAt, homography:homography, apply:apply, crc16:crc16, binarize:binarize};
})(typeof window !== "undefined" ? window : this);
