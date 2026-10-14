/* 印（code.js）の検査。jsc で動かす（画面も通信も使わない）。
     sh 紙の宿題/検査/js検査.sh
   合成した画像（大きさ・向き・傾き・ゆがみ・雑音・色の付いた表紙）で、読めること・読み違えないことを確かめる。 */
var ok = 0, ng = 0;
function check(name, cond, detail){
  if(cond){ ok++; print("  OK   " + name); } else { ng++; print("  ×    " + name + "  " + (detail === undefined ? "" : JSON.stringify(detail))); }
}
var C = this.PaperCode;

/* 乱数（決まった種）。検査が毎回同じになるように。 */
var seed = 12345;
function rnd(){ seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; }

/* 画像を作る：地の明るさ bg、シールの白い台（台の大きさは印の 1.4 倍）、印を h（マス→画素）で描く。 */
function render(w, h, p, H, opt){
  opt = opt || {};
  var g = new Float32Array(w * h), m = C.matrix(p), inv = invert(H);
  for(var y = 0; y < h; y++) for(var x = 0; x < w; x++){
    var acc = 0;
    for(var sy = 0; sy < 2; sy++) for(var sx = 0; sx < 2; sx++){
      var q = C.apply(inv, x + .25 + sx * .5, y + .25 + sy * .5), u = q[0], v = q[1], val;
      if(u >= -3 && v >= -3 && u < 16 && v < 16) val = 0.93;          // シールの白い台
      else val = opt.bg === undefined ? 0.95 : opt.bg;
      if(u >= 0 && v >= 0 && u < 13 && v < 13 && m[Math.floor(v)][Math.floor(u)]) val = 0.08;
      acc += val;
    }
    var n = (rnd() - .5) * (opt.noise || 0);
    g[y * w + x] = Math.max(0, Math.min(1, acc / 4 + n));
  }
  if(opt.text){                                                       // 手書きらしい線と四角
    for(var k = 0; k < opt.text; k++){
      var x0 = Math.floor(rnd() * w), y0 = Math.floor(rnd() * h), len = 20 + Math.floor(rnd() * 60);
      for(var t = 0; t < len; t++){ var xx = x0 + t, yy = y0 + Math.floor(t * rnd() * .3); if(xx < w && yy < h) g[yy * w + xx] = 0.3; }
    }
  }
  return g;
}
function invert(H){
  /* 3×3 の逆行列 */
  var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7], i = H[8];
  var A = e * i - f * h, B = -(d * i - f * g), Cc = d * h - e * g;
  var det = a * A + b * B + c * Cc;
  var r = [A, -(b * i - c * h), b * f - c * e, B, a * i - c * g, -(a * f - c * d), Cc, -(a * h - b * g), a * e - b * d];
  return r.map(function(v){ return v / det; });
}
/* マスの座標 → 画像：中心 (cx,cy)、1マス s 画素、回転 deg、遠近 k */
function place(cx, cy, s, deg, k){
  var t = deg * Math.PI / 180, co = Math.cos(t), si = Math.sin(t), half = 6.5 * s;
  function pt(u, v){ var x = (u - 6.5) * s, y = (v - 6.5) * s; return [cx + x * co - y * si, cy + x * si + y * co]; }
  var dst = [pt(0, 0), pt(13, 0), pt(13, 13), pt(0, 13)];
  if(k){ dst[1][0] += k * half; dst[2][0] -= k * half * .5; }
  return C.homography([[0, 0], [13, 0], [13, 13], [0, 13]], dst);
}

print("\n中身の出し入れ");
var P = {type:1, sid:"K7M2QRPT"};
var b = C.bitsOf(P);
check("81ビット", b && b.length === 81);
var back = C.parse(b);
check("戻せる", back && back.sid === "K7M2QRPT" && back.type === 1);
b[10] ^= 1;
check("1ビット違えば捨てる（検算）", C.parse(b) === null);
check("形の合わない sid は作らない", C.bitsOf({type:1, sid:"STU00001"}) === null && !C.canEncode("abc"));
var A = {type:2, sid:"ZZ23XY45", tmpl:0x1B, page:3};
var ba = C.parse(C.bitsOf(A));
check("答案用紙の型とページも戻る", ba && ba.tmpl === 0x1B && ba.page === 3 && ba.type === 2, ba);
check("SVG が出る", C.svg(P).indexOf("<svg") === 0);

print("\n画像から読む");
var cases = [
  ["1マス 4画素・まっすぐ", 360, 300, place(180, 150, 4, 0, 0), {}],
  ["1マス 7画素・右に 90°", 400, 400, place(200, 200, 7, 90, 0), {}],
  ["1マス 7画素・逆さ", 400, 400, place(200, 200, 7, 180, 0), {}],
  ["1マス 7画素・左に 90°", 400, 400, place(200, 200, 7, 270, 0), {}],
  ["1マス 8画素・12° 傾き", 400, 400, place(200, 200, 8, 12, 0), {}],
  ["1マス 8画素・-15° 傾き", 400, 400, place(200, 200, 8, -15, 0), {}],
  ["1マス 9画素・遠近", 420, 420, place(210, 210, 9, 3, 0.08), {}],
  ["1マス 30画素（区切り紙の大きな印）", 700, 700, place(350, 350, 30, 0, 0), {}],
  ["紺の表紙の上のシール", 420, 420, place(210, 210, 8, 5, 0), {bg:0.25}],
  ["雑音と手書きの線", 500, 500, place(260, 240, 8, -6, 0), {noise:0.12, text:80}],
];
var turnsWant = [0, 3, 2, 1, 0, 0, 0, 0, 0, 0];
cases.forEach(function(cs, i){
  var g = render(cs[1], cs[2], P, cs[3], cs[4]);
  var got = C.find(g, cs[1], cs[2]);
  check(cs[0], got.length === 1 && got[0].sid === "K7M2QRPT" && got[0].type === 1 && got[0].turns === turnsWant[i],
        got.map(function(x){ return [x.sid, x.turns]; }));
});

print("\n読み違えない");
var empty = new Float32Array(300 * 300); for(var i = 0; i < empty.length; i++) empty[i] = 0.95;
check("白紙からは何も出ない", C.find(empty, 300, 300).length === 0);
/* 四角い枠（答えの欄）がたくさんある紙 */
var W = 600, H = 600, boxes = new Float32Array(W * H);
for(i = 0; i < boxes.length; i++) boxes[i] = 0.95;
for(var bx = 0; bx < 5; bx++) for(var by = 0; by < 5; by++){
  var x0 = 20 + bx * 115, y0 = 20 + by * 115, s = 90;
  for(var t = 0; t < s; t++){
    for(var th = 0; th < 5; th++){
      boxes[(y0 + th) * W + x0 + t] = 0.1; boxes[(y0 + s - th) * W + x0 + t] = 0.1;
      boxes[(y0 + t) * W + x0 + th] = 0.1; boxes[(y0 + t) * W + x0 + s - th] = 0.1;
    }
  }
  for(var k = 0; k < 400; k++){ var xx = x0 + 12 + Math.floor(rnd() * 66), yy = y0 + 12 + Math.floor(rnd() * 66); boxes[yy * W + xx] = 0.2; }
}
check("枠の多い紙（25個）からは何も出ない", C.find(boxes, W, H).length === 0);
/* 1ビットだけ違う印 */
var bad = C.matrix(P); bad[5][6] ^= 1;
var H2 = place(200, 200, 8, 0, 0), g2 = new Float32Array(400 * 400), inv2 = invert(H2);
for(var y = 0; y < 400; y++) for(var x = 0; x < 400; x++){
  var q = C.apply(inv2, x + .5, y + .5), u = q[0], v = q[1];
  g2[y * 400 + x] = (u >= 0 && v >= 0 && u < 13 && v < 13 && bad[Math.floor(v)][Math.floor(u)]) ? 0.08 : 0.95;
}
check("1マス汚れた印は読まない（当てずっぽうにしない）", C.find(g2, 400, 400).length === 0);

print("\n2つの印（区切り紙に大小）");
var two = render(700, 400, {type:1, sid:"ABCDEFGH"}, place(180, 200, 8, 0, 0), {});
var P2 = render(700, 400, {type:2, sid:"23456789", tmpl:5, page:1}, place(520, 200, 6, 0, 0), {});
for(i = 0; i < two.length; i++) two[i] = Math.min(two[i], P2[i]);
var got2 = C.find(two, 700, 400);
check("2つとも読める", got2.length === 2 && got2.some(function(x){ return x.sid === "ABCDEFGH"; }) &&
      got2.some(function(x){ return x.sid === "23456789" && x.type === 2 && x.tmpl === 5 && x.page === 1; }),
      got2.map(function(x){ return x.sid; }));

print("\n" + (ng ? "× " + ng + "件" : "すべて通った") + "。（" + (ok + ng) + "件）");
