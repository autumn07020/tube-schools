/* ============================================================
   画像の下ごしらえ（端末の中だけ）
   ============================================================
     ・PDF のページを組む（写真を行列どおりに貼り、ページの向きに回す）
     ・地を白くする（影・紙の黄ばみを取る。赤い字の色は残す）
     ・白紙（両面の裏）を見分ける
     ・縮める（長辺 2000px・JPEG）、回す、名前の欄を白で消す、赤と印を焼き込む
   **写真を縮めるときは createImageBitmap か canvas を通す**（tubestudy で blob: が CSP に
   止められて縮めずに送った失敗がある。ここの CSP は blob: を許しているが、同じ道にそろえる）。
   ============================================================ */
(function(root){
"use strict";
var P = root.Paper = root.Paper || {};
var OUT_LONG = 2000, OUT_Q = 0.8, THUMB = 260;

function canvas(w, h){ var c = document.createElement("canvas"); c.width = Math.max(1, Math.round(w)); c.height = Math.max(1, Math.round(h)); return c; }
function ctx(c){ return c.getContext("2d", {willReadFrequently:true}); }

async function bitmapOf(part){
  if(part.kind === "jpeg") return await createImageBitmap(new Blob([part.bytes], {type:"image/jpeg"}));
  if(part.kind === "raw") return await createImageBitmap(new ImageData(part.rgba, part.w, part.h));
  throw new Error("写真を読めませんでした");
}

/* PDF の1ページ → canvas */
async function fromPdfPage(pg){
  var bms = [], i;
  for(i = 0; i < pg.parts.length; i++) bms.push(await bitmapOf(pg.parts[i]));
  var minx = Infinity, maxx = -Infinity, miny = Infinity, maxy = -Infinity, s = 0;
  pg.parts.forEach(function(pt, k){
    var m = pt.ctm;
    [[0, 0], [1, 0], [1, 1], [0, 1]].forEach(function(uv){
      var x = m[0] * uv[0] + m[2] * uv[1] + m[4], y = m[1] * uv[0] + m[3] * uv[1] + m[5];
      minx = Math.min(minx, x); maxx = Math.max(maxx, x); miny = Math.min(miny, y); maxy = Math.max(maxy, y);
    });
    var len = Math.sqrt(m[0] * m[0] + m[1] * m[1]) || 1;
    s = Math.max(s, bms[k].width / len);
  });
  var W = (maxx - minx) * s, H = (maxy - miny) * s, cap = 3200 / Math.max(W, H);
  if(cap < 1){ s *= cap; W *= cap; H *= cap; }
  var c = canvas(W, H), x = ctx(c);
  x.fillStyle = "#fff"; x.fillRect(0, 0, c.width, c.height);
  pg.parts.forEach(function(pt, k){
    var m = pt.ctm, w = bms[k].width, h = bms[k].height;
    x.setTransform(s * m[0] / w, -s * m[1] / w, -s * m[2] / h, s * m[3] / h, s * (m[2] + m[4] - minx), s * (maxy - m[3] - m[5]));
    x.drawImage(bms[k], 0, 0);
  });
  x.setTransform(1, 0, 0, 1, 0, 0);
  bms.forEach(function(b){ if(b.close) b.close(); });
  var turns = (((pg.rot || 0) / 90) % 4 + 4) % 4;
  return turns ? rotate(c, turns) : c;
}

/* 写真のファイル → canvas（向きは写真の情報どおり） */
async function fromFile(file){
  var bm = await createImageBitmap(file);
  var c = canvas(bm.width, bm.height);
  ctx(c).drawImage(bm, 0, 0);
  if(bm.close) bm.close();
  return c;
}

function limit(c, long){
  var k = long / Math.max(c.width, c.height);
  if(k >= 1) return c;
  var o = canvas(c.width * k, c.height * k), x = ctx(o);
  x.imageSmoothingQuality = "high";
  x.drawImage(c, 0, 0, o.width, o.height);
  return o;
}

/* 灰色（0〜1）。長辺 long に縮めてから。 */
function gray(c, long){
  var s = long ? limit(c, long) : c, w = s.width, h = s.height;
  var d = ctx(s).getImageData(0, 0, w, h).data, g = new Float32Array(w * h);
  for(var i = 0, j = 0; j < g.length; i += 4, j++) g[j] = (0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]) / 255;
  return {g:g, w:w, h:h, scale:w / c.width};
}

function rotate(c, turns){
  turns = ((turns % 4) + 4) % 4;
  if(!turns) return c;
  var o = turns % 2 ? canvas(c.height, c.width) : canvas(c.width, c.height), x = ctx(o);
  x.translate(o.width / 2, o.height / 2);
  x.rotate(turns * Math.PI / 2);
  x.drawImage(c, -c.width / 2, -c.height / 2);
  return o;
}

/* 地を白くする：まわりのいちばん明るい所を「紙の色」とみなし、そこで割る。
   窓は長辺の 1/40 のマスを 3×3 で広げたもの（2cm 角ほど）。それより大きな黒い面は無い前提。 */
function whiten(c){
  var w = c.width, h = c.height, x = ctx(c), id = x.getImageData(0, 0, w, h), d = id.data;
  var cell = Math.max(8, Math.round(Math.max(w, h) / 40)), gw = Math.ceil(w / cell), gh = Math.ceil(h / cell);
  var mx = new Float32Array(gw * gh), gx, gy, px, py, i;
  for(py = 0; py < h; py += 2) for(px = 0; px < w; px += 2){
    i = (py * w + px) * 4;
    var L = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2], k = ((py / cell) | 0) * gw + ((px / cell) | 0);
    if(L > mx[k]) mx[k] = L;
  }
  var dil = new Float32Array(gw * gh);
  for(gy = 0; gy < gh; gy++) for(gx = 0; gx < gw; gx++){
    var m = 0;
    for(var dy = -1; dy <= 1; dy++) for(var dx = -1; dx <= 1; dx++){
      var yy = gy + dy, xx = gx + dx;
      if(yy >= 0 && yy < gh && xx >= 0 && xx < gw && mx[yy * gw + xx] > m) m = mx[yy * gw + xx];
    }
    dil[gy * gw + gx] = Math.max(m, 60);
  }
  var bg = new Float32Array(gw * gh);           // なめらかに（3×3 の平均）
  for(gy = 0; gy < gh; gy++) for(gx = 0; gx < gw; gx++){
    var s = 0, n = 0;
    for(dy = -1; dy <= 1; dy++) for(dx = -1; dx <= 1; dx++){
      yy = gy + dy; xx = gx + dx;
      if(yy >= 0 && yy < gh && xx >= 0 && xx < gw){ s += dil[yy * gw + xx]; n++; }
    }
    bg[gy * gw + gx] = s / n;
  }
  for(py = 0; py < h; py++){
    var fy = Math.min(gh - 1.001, Math.max(0, py / cell - 0.5)), y0 = fy | 0, ty = fy - y0;
    for(px = 0; px < w; px++){
      var fx = Math.min(gw - 1.001, Math.max(0, px / cell - 0.5)), x0 = fx | 0, tx = fx - x0;
      var b = bg[y0 * gw + x0] * (1 - tx) * (1 - ty) + bg[y0 * gw + x0 + 1] * tx * (1 - ty) +
              bg[(y0 + 1) * gw + x0] * (1 - tx) * ty + bg[(y0 + 1) * gw + x0 + 1] * tx * ty;
      var f = 255 / b;
      i = (py * w + px) * 4;
      for(var ch = 0; ch < 3; ch++){
        var v = d[i + ch] * f / 255;                       // 0〜1（紙の色が 1）
        v = (v - 0.06) / 0.86;                             // 少しだけ締める
        d[i + ch] = v <= 0 ? 0 : v >= 1 ? 255 : v * 255;
      }
    }
  }
  x.putImageData(id, 0, 0);
  return c;
}

/* 字の量（白くしたあとの暗い画素の割合。まわり 3% は数えない）。白紙は 0.0015 未満。 */
function ink(c){
  var gg = gray(c, 800), g = gg.g, w = gg.w, h = gg.h, n = 0, dark = 0;
  var mx = Math.round(w * 0.03), my = Math.round(h * 0.03);
  for(var y = my; y < h - my; y++) for(var x = mx; x < w - mx; x++){ n++; if(g[y * w + x] < 0.59) dark++; }
  return n ? dark / n : 0;
}

/* 似ている度合いを測る印（9×8 の差分ハッシュ。16進 16文字） */
function dhash(c){
  var s = canvas(9, 8), x = ctx(s);
  x.drawImage(c, 0, 0, 9, 8);
  var d = x.getImageData(0, 0, 9, 8).data, bits = "";
  for(var r = 0; r < 8; r++) for(var k = 0; k < 8; k++){
    var a = d[(r * 9 + k) * 4] + d[(r * 9 + k) * 4 + 1], b = d[(r * 9 + k + 1) * 4] + d[(r * 9 + k + 1) * 4 + 1];
    bits += a > b ? "1" : "0";
  }
  var hex = "";
  for(var i = 0; i < 64; i += 4) hex += parseInt(bits.substr(i, 4), 2).toString(16);
  return hex;
}
function hamming(a, b){
  if(!a || !b || a.length !== b.length) return 64;
  var n = 0;
  for(var i = 0; i < a.length; i++){ var v = parseInt(a[i], 16) ^ parseInt(b[i], 16); while(v){ n += v & 1; v >>= 1; } }
  return n;
}

function toBlob(c, q){
  return new Promise(function(res, rej){
    c.toBlob(function(b){ b ? res(b) : rej(new Error("画像にできませんでした")); }, "image/jpeg", q || OUT_Q);
  });
}

/* 名前の欄を白で消す。rects は [x, y, w, h]（0〜1。画像の幅と高さに対して） */
function mask(c, rects){
  if(!rects || !rects.length) return c;
  var x = ctx(c);
  x.fillStyle = "#fff";
  rects.forEach(function(r){ x.fillRect(r[0] * c.width, r[1] * c.height, r[2] * c.width, r[3] * c.height); });
  return c;
}

/* 2枚を横に並べて1枚に（1人6枚を超えたとき。tubestudy の上限） */
function side(a, b){
  var h = Math.max(a.height, b ? b.height : 0), gap = Math.round(h * 0.02);
  var o = canvas(a.width + (b ? gap + b.width : 0), h), x = ctx(o);
  x.fillStyle = "#fff"; x.fillRect(0, 0, o.width, o.height);
  x.drawImage(a, 0, 0);
  if(b) x.drawImage(b, a.width + gap, 0);
  return o;
}

/* ---------- 赤と印 ---------- */
/* items: [{t:"pen", c:"#d11", w:画素, p:[[x,y],…]} | {t:"stamp", k:"maru"|"batsu"|"sankaku"|"nijumaru"|"check", x, y, s}]
   座標は画像の画素（原寸）。 */
function drawItems(x, items, k){
  k = k || 1;
  items.forEach(function(it){
    if(it.t === "pen"){
      if(!it.p || !it.p.length) return;
      x.strokeStyle = it.c || "#D0021B"; x.lineWidth = (it.w || 4) * k; x.lineCap = "round"; x.lineJoin = "round";
      x.beginPath();
      x.moveTo(it.p[0][0] * k, it.p[0][1] * k);
      if(it.p.length === 1) x.lineTo(it.p[0][0] * k + 0.1, it.p[0][1] * k);
      for(var i = 1; i < it.p.length; i++) x.lineTo(it.p[i][0] * k, it.p[i][1] * k);
      x.stroke();
    } else if(it.t === "stamp") stamp(x, it.k, it.x * k, it.y * k, (it.s || 40) * k, it.c);
    else if(it.t === "text"){
      x.fillStyle = it.c || "#D0021B";
      x.font = "600 " + Math.round((it.s || 40) * k) + 'px -apple-system, "Hiragino Sans", "Yu Gothic UI", sans-serif';
      x.textBaseline = "middle";
      x.fillText(it.v, it.x * k, it.y * k);
    }
  });
}
function stamp(x, kind, cx, cy, s, color){
  x.save();
  x.strokeStyle = color || "#D0021B"; x.lineWidth = Math.max(2, s * 0.11); x.lineCap = "round"; x.lineJoin = "round";
  var r = s / 2;
  x.beginPath();
  if(kind === "maru" || kind === "nijumaru"){
    x.arc(cx, cy, r, 0, Math.PI * 2);
    if(kind === "nijumaru"){ x.moveTo(cx + r * 0.6, cy); x.arc(cx, cy, r * 0.6, 0, Math.PI * 2); }
  } else if(kind === "batsu"){
    x.moveTo(cx - r * 0.8, cy - r * 0.8); x.lineTo(cx + r * 0.8, cy + r * 0.8);
    x.moveTo(cx + r * 0.8, cy - r * 0.8); x.lineTo(cx - r * 0.8, cy + r * 0.8);
  } else if(kind === "sankaku"){
    x.moveTo(cx, cy - r); x.lineTo(cx + r * 0.9, cy + r * 0.62); x.lineTo(cx - r * 0.9, cy + r * 0.62); x.closePath();
  } else if(kind === "check"){
    x.moveTo(cx - r * 0.8, cy); x.lineTo(cx - r * 0.2, cy + r * 0.6); x.lineTo(cx + r * 0.9, cy - r * 0.8);
  }
  x.stroke();
  x.restore();
}
/* 原寸の画像に赤と印を焼き込んで、返す1枚にする */
function burn(c, items){
  var o = canvas(c.width, c.height), x = ctx(o);
  x.drawImage(c, 0, 0);
  drawItems(x, items || [], 1);
  return o;
}

async function blobToCanvas(blob){
  var bm = await createImageBitmap(blob);
  var c = canvas(bm.width, bm.height);
  ctx(c).drawImage(bm, 0, 0);
  if(bm.close) bm.close();
  return c;
}

P.img = {canvas:canvas, ctx:ctx, fromPdfPage:fromPdfPage, fromFile:fromFile, limit:limit, gray:gray, rotate:rotate,
         whiten:whiten, ink:ink, dhash:dhash, hamming:hamming, toBlob:toBlob, mask:mask, side:side,
         drawItems:drawItems, stamp:stamp, burn:burn, blobToCanvas:blobToCanvas, OUT_LONG:OUT_LONG, THUMB:THUMB};
})(window);
