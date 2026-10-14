/* ============================================================
   刷るもの：番号シール・区切り紙・答案用紙（と、答案用紙の升目の位置）
   ============================================================
     ・番号シール   A4 に 70×37mm のシール 24枚（3列×8行・余白なし）。1人に1枚。ノート・冊子の表紙に貼る。
                    **表紙は送らない**（名前が書いてあるので）。印の中身は sid だけ（組み分けで変わらない）。
     ・区切り紙     A4 に大きな印。プリントを複合機に通すとき、自分の紙の一番上に重ねる。これも送らない。
     ・答案用紙     四隅の目印・印（sid・用紙の型・ページ）・答えの枠。**問題文は刷らない**（教材を写さない）。
                    名前はこの端末の中の対応表から刷ってよい（紙の上だけ）。送るときは名前の欄を必ず白で消す。
   印刷は「実際のサイズ（100%）」で。拡大・縮小すると答案用紙の位置がずれる（目印で合わせ直すが、欄が切れる）。
   ============================================================ */
(function(root){
"use strict";
var P = root.Paper = root.Paper || {};
var C = root.PaperCode;

/* ---------- 答案用紙の型（印の 8ビット） ---------- */
var COUNTS = [5, 10, 15, 20, 25, 30, 40, 50];
var SIZES = [
  {name:"小（1字・数字）", w:30, h:20, cols:5, gap:6},
  {name:"中（語句）", w:84, h:16, cols:2, gap:5},
  {name:"大（式・短文）", w:178, h:24, cols:1, gap:6},
  {name:"記述", w:178, h:66, cols:1, gap:8}
];
var PAGE = {w:210, h:297};
var AREA = {x:16, y:52, w:178, h:226};
var MARK = 7;                                            // 四隅の目印（黒い正方形）の一辺
var MARKS = [[8, 8], [195, 8], [195, 282], [8, 282]];    // 目印の左上（mm）
var MARK_C = MARKS.map(function(m){ return [m[0] + MARK / 2, m[1] + MARK / 2]; });
var CODE = {x:156, y:15, s:22};                          // 印（白い余白つき）の位置と大きさ（右上の目印の探し場所と重ねない）
var NAMEBOX = {x:78, y:13, w:74, h:30};                  // 番号と名前を刷る所（送るときに白で消す）

function tmplOf(ci, si){ return (ci & 7) | ((si & 3) << 3); }
function layout(tmpl){
  var ci = tmpl & 7, si = (tmpl >> 3) & 3, count = COUNTS[ci], sz = SIZES[si];
  var gapX = sz.cols > 1 ? (AREA.w - sz.cols * sz.w) / (sz.cols - 1) : 0;
  var rows = Math.floor((AREA.h + sz.gap) / (sz.h + sz.gap)), per = rows * sz.cols;
  var pages = Math.ceil(count / per), boxes = [];
  for(var q = 1; q <= count; q++){
    var k = (q - 1) % per, r = Math.floor(k / sz.cols), c = k % sz.cols;
    boxes.push({q:q, page:Math.floor((q - 1) / per), x:AREA.x + c * (sz.w + gapX), y:AREA.y + r * (sz.h + sz.gap), w:sz.w, h:sz.h});
  }
  return {tmpl:tmpl, count:count, size:sz, sizeIndex:si, countIndex:ci, pages:pages, per:per, boxes:boxes};
}

/* 印の外枠の4隅（mm）。SVG は 15マス（外に1マスの余白）で CODE.s mm。枠はマス 1〜14。 */
function codeCornersMm(){
  var m = CODE.s / 15, x0 = CODE.x + m, y0 = CODE.y + m, x1 = CODE.x + 14 * m, y1 = CODE.y + 14 * m;
  return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
}

/* ---------- 刷る ---------- */
function printHtml(html, landscape){
  var el = P.$("#print");
  el.innerHTML = html;
  el.className = landscape ? "land" : "";
  var done = function(){ el.innerHTML = ""; window.removeEventListener("afterprint", done); };
  window.addEventListener("afterprint", done);
  setTimeout(function(){ window.print(); }, 60);
}

function stickerSheet(row, name){
  var p = {type:1, sid:row.sid}, cells = "";
  for(var i = 0; i < 24; i++){
    cells += '<div class="lab"><div class="lab-code">' + C.svg(p, "番号シール") + '</div>' +
             '<div class="lab-txt"><div class="lab-who">' + P.esc(name || "") + '</div>' +
             '<div class="lab-id">' + P.esc(row.label) + '</div><div class="lab-hint">表紙に貼る</div></div></div>';
  }
  return '<section class="pg labels">' + cells + '</section>';
}
function separator(row, name){
  return '<section class="pg sep"><div class="sep-code">' + C.svg({type:1, sid:row.sid}, "区切り紙") + '</div>' +
         '<div class="sep-who">' + P.esc(name || row.label) + '</div>' +
         (name ? '<div class="sep-id">' + P.esc(row.label) + '</div>' : '') +
         '<p class="sep-hint">この紙を、自分のプリントの一番上に重ねて出す。<br>この紙は送りません（取り込むと、ここから下がこの人の紙になります）。</p></section>';
}
function answerSheet(row, name, head, tmpl, page){
  var L = layout(tmpl), out = '<section class="pg ans">';
  MARKS.forEach(function(m){ out += '<div class="mk" style="left:' + m[0] + 'mm;top:' + m[1] + 'mm;width:' + MARK + 'mm;height:' + MARK + 'mm"></div>'; });
  out += '<div class="ans-code" style="left:' + CODE.x + 'mm;top:' + CODE.y + 'mm;width:' + CODE.s + 'mm;height:' + CODE.s + 'mm">' +
         C.svg({type:2, sid:row.sid, tmpl:tmpl, page:page}, "答案用紙") + '</div>';
  out += '<div class="ans-head" style="left:18mm;top:15mm;width:58mm">' +
         '<div class="ans-course">' + P.esc(head.course) + '</div><div class="ans-title">' + P.esc(head.title) + '</div>' +
         '<div class="ans-date">' + P.esc(head.date) + (L.pages > 1 ? '　' + (page + 1) + '/' + L.pages + '枚' : '') + '</div></div>';
  out += '<div class="ans-name" style="left:' + NAMEBOX.x + 'mm;top:' + NAMEBOX.y + 'mm;width:' + NAMEBOX.w + 'mm;height:' + NAMEBOX.h + 'mm">' +
         '<div class="ans-id">' + P.esc(row.label) + '</div><div class="ans-who">' + P.esc(name || "") + '</div></div>';
  L.boxes.filter(function(b){ return b.page === page; }).forEach(function(b){
    out += '<div class="box" style="left:' + b.x + 'mm;top:' + b.y + 'mm;width:' + b.w + 'mm;height:' + b.h + 'mm"><span>' + b.q + '</span></div>';
  });
  return out + '</section>';
}

/* ---------- 答案用紙を読む（採点のとき） ---------- */
/* 四隅の目印を探す：隅の区画の中の、いちばん大きな黒いかたまりの重心（omr.js と同じ考え） */
function findMarks(gg){
  var g = gg.g, w = gg.w, h = gg.h, bin = C.binarize(g, w, h), out = [];
  var rx = Math.round(w * 0.14), ry = Math.round(h * 0.11);
  var regions = [[0, 0], [w - rx, 0], [w - rx, h - ry], [0, h - ry]];
  for(var k = 0; k < 4; k++){
    var x0 = regions[k][0], y0 = regions[k][1], seen = new Uint8Array(rx * ry), best = null;
    for(var yy = 0; yy < ry; yy++) for(var xx = 0; xx < rx; xx++){
      var X = x0 + xx, Y = y0 + yy;
      if(seen[yy * rx + xx] || !bin[Y * w + X]) continue;
      var st = [[xx, yy]], n = 0, sx = 0, sy = 0, minx = xx, maxx = xx, miny = yy, maxy = yy;
      seen[yy * rx + xx] = 1;
      while(st.length){
        var p = st.pop(), px = p[0], py = p[1];
        n++; sx += px; sy += py;
        if(px < minx) minx = px; if(px > maxx) maxx = px; if(py < miny) miny = py; if(py > maxy) maxy = py;
        [[1, 0], [-1, 0], [0, 1], [0, -1]].forEach(function(d){
          var nx = px + d[0], ny = py + d[1];
          if(nx < 0 || ny < 0 || nx >= rx || ny >= ry || seen[ny * rx + nx] || !bin[(y0 + ny) * w + x0 + nx]) return;
          seen[ny * rx + nx] = 1; st.push([nx, ny]);
        });
      }
      var bw = maxx - minx + 1, bh = maxy - miny + 1;
      if(bw < 6 || bh < 6 || bw / bh > 1.6 || bh / bw > 1.6 || n / (bw * bh) < 0.6) continue;
      if(!best || n > best.n) best = {n:n, x:x0 + sx / n, y:y0 + sy / n};
    }
    if(!best) return null;
    out.push([best.x, best.y]);
  }
  return out;
}

/* 答案用紙の1枚から：印・mm → 画素の変換。読めなければ null。 */
function readSheet(cv){
  var gg = P.img.gray(cv, 1600), codes = C.find(gg.g, gg.w, gg.h).filter(function(c){ return c.type === 2; });
  if(!codes.length) return null;
  var code = codes[0], H = null, how = "marks";
  var mk = findMarks(gg);
  if(mk) H = C.homography(MARK_C, mk);
  if(!H){ H = C.homography(codeCornersMm(), code.corners); how = "code"; }
  if(!H) return null;
  var k = 1 / gg.scale;
  return {code:code, how:how, layout:layout(code.tmpl),
          px:function(x, y){ var q = C.apply(H, x, y); return [q[0] * k, q[1] * k]; }};
}

/* 名前の欄（刷った名前）を白で消す矩形（0〜1）。印の位置から組む（目印を探さなくても出せる）。 */
function nameMaskFromCode(code, gw, gh){
  var H = C.homography(codeCornersMm(), code.corners);
  if(!H) return null;
  var pts = [[NAMEBOX.x - 2, NAMEBOX.y - 2], [NAMEBOX.x + NAMEBOX.w + 2, NAMEBOX.y - 2],
             [NAMEBOX.x + NAMEBOX.w + 2, NAMEBOX.y + NAMEBOX.h + 2], [NAMEBOX.x - 2, NAMEBOX.y + NAMEBOX.h + 2]].map(function(p){ return C.apply(H, p[0], p[1]); });
  var xs = pts.map(function(p){ return p[0]; }), ys = pts.map(function(p){ return p[1]; });
  var x0 = Math.max(0, Math.min.apply(null, xs)), y0 = Math.max(0, Math.min.apply(null, ys));
  var x1 = Math.min(gw, Math.max.apply(null, xs)), y1 = Math.min(gh, Math.max.apply(null, ys));
  if(x1 <= x0 || y1 <= y0) return null;
  return [x0 / gw, y0 / gh, (x1 - x0) / gw, (y1 - y0) / gh];
}

P.sheets = {COUNTS:COUNTS, SIZES:SIZES, PAGE:PAGE, AREA:AREA, MARK_C:MARK_C, CODE:CODE, NAMEBOX:NAMEBOX,
            tmplOf:tmplOf, layout:layout, codeCornersMm:codeCornersMm, printHtml:printHtml,
            stickerSheet:stickerSheet, separator:separator, answerSheet:answerSheet,
            findMarks:findMarks, readSheet:readSheet, nameMaskFromCode:nameMaskFromCode};
})(window);
