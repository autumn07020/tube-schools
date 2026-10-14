/* ============================================================
   答案用紙を問題ごとに採点する（ここで刷った答案用紙だけ）
   ============================================================
     ・四隅の目印で位置を合わせ（見つからなければ印の4隅で）、同じ問題の枠だけを全員分並べる
     ・違う答えにだけ ✕ を叩き、「残りは◯」を1回押す → 次の問題
     ・最後に、点数を横に出して 1〜5 を押す（**点数から評価を作らない**）→ 枠の横に◯✕、上に点数を
       焼き込んで返す（段階3以上）・評価を付ける
     ・◯✕はこの端末に保存する（途中でやめても続きから）
   ============================================================ */
(function(root){
"use strict";
var P = root.Paper, esc = P.esc;
var WORD = {5:"よくできた", 4:"できた", 3:"もう少し", 2:"がんばろう", 1:"やり直し"};
var Q = null;
var urls = [];
function url(b){ var u = URL.createObjectURL(b); urls.push(u); return u; }

P.views.byq = {render:async function(main, arg){
  urls.forEach(function(u){ URL.revokeObjectURL(u); }); urls = [];
  document.removeEventListener("keydown", onKey);
  main.innerHTML = '<h1>' + esc(arg.name || arg.key) + '</h1><div class="card"><div id="bq">答案用紙を読んでいます…</div><div class="bar"><i id="bqBar"></i></div></div>';
  var d = await P.api.check(arg.key, arg.n);
  Q = {key:arg.key, n:arg.n, name:arg.name || arg.key, lesson:d.lesson, use:(d.course || {}).use == null ? 4 : d.course.use,
       rows:d.rows || [], sheets:{}, tmpl:null, q:1, marks:{}, main:main, busy:false, stray:[]};
  var saved = await P.store.get("marks", "byq|" + Q.key + "|" + Q.n);
  if(saved) Q.marks = saved.marks || {};
  var withFiles = Q.rows.filter(function(r){ return (r.files || []).length; }), tcount = {};
  for(var i = 0; i < withFiles.length; i++){
    var r = withFiles[i];
    P.$("#bq").textContent = "答案用紙を読んでいます " + (i + 1) + " / " + withFiles.length;
    P.$("#bqBar").style.width = Math.round((i + 1) / withFiles.length * 100) + "%";
    var list = [];
    for(var k = 0; k < r.files.length; k++){
      try {
        var cv = P.img.limit(await P.img.blobToCanvas(await P.api.image(r.head, r.sid, r.files[k])), 2400);
        var geo = P.sheets.readSheet(cv);
        list.push({file:r.files[k], cv:cv, geo:geo});
        if(geo){
          if(geo.code.sid !== r.sid) Q.stray.push(r);
          tcount[geo.code.tmpl] = (tcount[geo.code.tmpl] || 0) + 1;
        }
      } catch(e){}
    }
    Q.sheets[r.sid] = list;
  }
  var best = Object.keys(tcount).sort(function(a, b){ return tcount[b] - tcount[a]; })[0];
  if(best == null){ main.innerHTML = '<h1>' + esc(Q.name) + '</h1><div class="card">この回には、ここで刷った答案用紙が見つかりませんでした。</div>'; return; }
  Q.tmpl = +best;
  Q.layout = P.sheets.layout(Q.tmpl);
  document.addEventListener("keydown", onKey);
  drawQuestion();
}};

function students(){
  return Q.rows.filter(function(r){ return (Q.sheets[r.sid] || []).some(function(s){ return s.geo && s.geo.code.tmpl === Q.tmpl; }); });
}
function sheetFor(r, page){
  return (Q.sheets[r.sid] || []).filter(function(s){ return s.geo && s.geo.code.tmpl === Q.tmpl && s.geo.code.page === page; })[0];
}
function box(q){ return Q.layout.boxes[q - 1]; }

/* 枠を切り出す（写った向きのまま、4隅を写した外接の四角） */
function crop(s, b){
  var pts = [[b.x - 1, b.y - 1], [b.x + b.w + 1, b.y - 1], [b.x + b.w + 1, b.y + b.h + 1], [b.x - 1, b.y + b.h + 1]].map(function(p){ return s.geo.px(p[0], p[1]); });
  var xs = pts.map(function(p){ return p[0]; }), ys = pts.map(function(p){ return p[1]; });
  var x0 = Math.max(0, Math.min.apply(null, xs)), y0 = Math.max(0, Math.min.apply(null, ys));
  var x1 = Math.min(s.cv.width, Math.max.apply(null, xs)), y1 = Math.min(s.cv.height, Math.max.apply(null, ys));
  var w = Math.max(1, x1 - x0), h = Math.max(1, y1 - y0), k = Math.min(1, 520 / w);
  var o = P.img.canvas(w * k, h * k);
  P.img.ctx(o).drawImage(s.cv, x0, y0, w, h, 0, 0, o.width, o.height);
  return o;
}

function mark(sid, q){ return (Q.marks[sid] || {})[q] || null; }
function setMark(sid, q, v){ (Q.marks[sid] = Q.marks[sid] || {})[q] = v; save(); }
var st = null;
function save(){ clearTimeout(st); st = setTimeout(function(){ P.store.put("marks", {id:"byq|" + Q.key + "|" + Q.n, marks:Q.marks, at:Date.now()}); }, 200); }

async function drawQuestion(){
  var main = Q.main, b = box(Q.q), rows = students();
  var tiles = [];
  for(var i = 0; i < rows.length; i++){
    var s = sheetFor(rows[i], b.page);
    if(!s) continue;
    var c = crop(s, b), m = mark(rows[i].sid, Q.q);
    tiles.push('<button class="qt ' + (m === "x" ? "x" : m === "o" ? "o" : "") + '" data-sid="' + esc(rows[i].sid) + '">' +
               '<img alt="" src="' + url(await P.img.toBlob(c, 0.8)) + '"><div class="cap">' + P.who(rows[i]) + '</div>' +
               '<span class="m">' + (m === "x" ? "✕" : m === "o" ? "◯" : "") + '</span></button>');
  }
  var left = rows.filter(function(r){ return sheetFor(r, b.page) && !mark(r.sid, Q.q); }).length;
  main.innerHTML = '<div class="row"><h1 style="margin-right:auto">' + esc(Q.name) + '　第' + Q.q + '問 <span class="muted num">/ ' + Q.layout.count + '</span></h1>' +
      '<button class="btn2" data-q="-1"' + (Q.q > 1 ? "" : " disabled") + '>前の問題</button>' +
      '<button class="btn2" data-q="1"' + (Q.q < Q.layout.count ? "" : " disabled") + '>次の問題</button>' +
      '<button class="btn" id="rest">' + (left ? "残りは◯（" + left + "人）" : "次の問題") + '</button></div>' +
    '<p class="lead">違う答えにだけ ✕ を押す（もう一度押すと取り消す）。' + (Q.stray.length ? '<span class="warn-text">　別の生徒の印の紙が混ざっています：' + Q.stray.map(function(r){ return P.who(r); }).join("、") + '</span>' : "") + '</p>' +
    '<div class="qgrid">' + tiles.join("") + '</div>' +
    '<div class="gap"></div><div class="row"><button class="btn2" id="toSum">点数を見て返す</button><span class="spacer"></span>' +
    '<button class="linkish" id="toPages">1人ずつの採点にもどる</button></div>';
  main.onclick = function(e){
    var t = e.target.closest("[data-sid]");
    if(t){ var sid = t.dataset.sid, m = mark(sid, Q.q); setMark(sid, Q.q, m === "x" ? null : "x"); tileState(t, mark(sid, Q.q)); updateRest(); return; }
    var nav = e.target.closest("[data-q]");
    if(nav){ Q.q = Math.max(1, Math.min(Q.layout.count, Q.q + (+nav.dataset.q))); drawQuestion(); return; }
  };
  P.$("#rest").onclick = function(){
    students().forEach(function(r){ if(sheetFor(r, box(Q.q).page) && !mark(r.sid, Q.q)) setMark(r.sid, Q.q, "o"); });
    if(Q.q < Q.layout.count){ Q.q++; drawQuestion(); } else summary();
  };
  P.$("#toSum").onclick = summary;
  P.$("#toPages").onclick = function(){ P.show("grade", {key:Q.key, n:Q.n}); };
}
function tileState(t, m){
  t.classList.toggle("x", m === "x"); t.classList.toggle("o", m === "o");
  t.querySelector(".m").textContent = m === "x" ? "✕" : m === "o" ? "◯" : "";
}
function updateRest(){
  var b = box(Q.q), left = students().filter(function(r){ return sheetFor(r, b.page) && !mark(r.sid, Q.q); }).length;
  P.$("#rest").textContent = left ? "残りは◯（" + left + "人）" : "次の問題";
}

function score(sid){
  var ok = 0, done = 0;
  for(var q = 1; q <= Q.layout.count; q++){ var m = mark(sid, q); if(m){ done++; if(m === "o") ok++; } }
  return {ok:ok, done:done};
}

function summary(){
  var rows = students(), main = Q.main;
  main.innerHTML = '<div class="row"><h1 style="margin-right:auto">' + esc(Q.name) + '　点数を見て返す</h1><button class="btn2" id="backQ">問題ごとにもどる</button></div>' +
    '<p class="lead">点数は横に出すだけです。1〜5 を押すと、' + (Q.use >= 3 ? "枠の横に◯✕・上に点数を入れた答案を返し、" : "") + '評価を付けます。</p>' +
    '<div class="lrows">' + rows.map(function(r){
      var s = score(r.sid);
      return '<div class="lrow" data-row="' + esc(r.sid) + '"><div><div class="n">' + P.who(r) + '</div>' +
             '<div class="i num">' + s.ok + ' / ' + Q.layout.count + (s.done < Q.layout.count ? '　<span class="warn-text">まだ付けていない問題 ' + (Q.layout.count - s.done) + '</span>' : "") +
             (r.v ? '　いまの評価 ' + r.v : "") + '</div></div>' +
             '<div class="r"><div class="rates" style="min-width:320px">' + [5, 4, 3, 2, 1].map(function(v){
               return '<button data-v="' + v + '" data-sid="' + esc(r.sid) + '" class="' + (r.v === v ? "on" : "") + '"><b>' + v + '</b><span>' + WORD[v] + '</span></button>';
             }).join("") + '</div></div></div>';
    }).join("") + '</div>';
  P.$("#backQ").onclick = function(){ drawQuestion(); };
  main.onclick = function(e){
    var b = e.target.closest("[data-v]");
    if(b) give(b.dataset.sid, +b.dataset.v, b);
  };
}

async function give(sid, v, btn){
  if(Q.busy) return;
  var r = Q.rows.filter(function(x){ return x.sid === sid; })[0];
  if(!r) return;
  Q.busy = true;
  try {
    var s = score(sid), note = s.ok + " / " + Q.layout.count;
    if(Q.use >= 3){
      /* 前に返した答案を控える（採点の画面の「前に戻す」と同じ控え） */
      var prev = {id:"grade|" + r.head + "|" + r.sid + "|" + Date.now(), kind:"grade", aid:r.head, sid:r.sid, key:Q.key, n:Q.n,
                  label:r.label, course:Q.name, lesson:P.lessonName(Q.lesson),
                  at:Date.now(), v:r.v == null ? null : r.v, note:r.note || "", returned:[]};
      for(var k = 0; k < (r.returned || []).length; k++){
        try { prev.returned.push({name:r.returned[k], blob:await P.api.image(r.head, r.sid, r.returned[k])}); } catch(e){}
      }
      await P.store.put("history", prev);
      var files = [];
      var list = Q.sheets[sid] || [];
      for(var i = 0; i < list.length; i++){
        var sh = list[i], items = [];
        if(sh.geo && sh.geo.code.tmpl === Q.tmpl){
          var L = Q.layout;
          L.boxes.filter(function(b){ return b.page === sh.geo.code.page; }).forEach(function(b){
            var m = mark(sid, b.q);
            if(!m) return;
            var sz = Math.min(b.h * 0.8, 12), c = sh.geo.px(b.x + b.w - sz * 0.75, b.y + b.h / 2), c2 = sh.geo.px(b.x + b.w - sz * 0.75 + sz, b.y + b.h / 2);
            var spx = Math.abs(c2[0] - c[0]);
            items.push({t:"stamp", k:m === "o" ? "maru" : "batsu", x:c[0], y:c[1], s:spx});
          });
          if(sh.geo.code.page === 0){
            var tp = sh.geo.px(P.sheets.AREA.x, 44), tp2 = sh.geo.px(P.sheets.AREA.x + 8, 44);
            items.push({t:"text", v:s.ok + " / " + L.count, x:tp[0], y:tp[1], s:Math.abs(tp2[0] - tp[0])});
          }
        }
        var out = P.img.burn(sh.cv, items);
        files.push({type:"image/jpeg", b64:await P.b64(await P.img.toBlob(out, 0.85))});
      }
      if(files.length){
        var got = await P.api.giveBack(r.head, r.sid, files.slice(0, 6), note);
        r.returned = ((got.sub || {}).returned || {}).files ? got.sub.returned.files.map(function(f){ return f.name; }) : r.returned;
      }
    }
    await P.api.rate(Q.key, Q.n, sid, v, note);
    r.v = v; r.note = note;
    P.toast(r.label + "：" + note + "・" + v + "（" + WORD[v] + "）" + (Q.use >= 3 ? "。返しました" : ""));
    var row = btn.closest(".lrow");
    P.$$("[data-v]", row).forEach(function(b){ b.classList.toggle("on", +b.dataset.v === v); });
  } catch(e){ P.fail(e); }
  finally { Q.busy = false; }
}

function onKey(e){
  if(!Q || P.state.view !== "byq") return;
  if(e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
  if(e.key === "ArrowRight" && Q.q < Q.layout.count){ Q.q++; drawQuestion(); }
  else if(e.key === "ArrowLeft" && Q.q > 1){ Q.q--; drawQuestion(); }
}

P.byq = {state:function(){ return Q; }};
})(window);
