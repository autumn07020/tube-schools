/* ============================================================
   採点する：ページを順に出す → 赤・◯✕ → 1〜5 を押せば、返して次の子へ
   ============================================================
   決めごと
     ・対面の子（講師が取り込んだ紙）もオンラインの子（家から出した写真）も、同じ列・同じ見た目。
     ・◯✕は数えて横に出すだけ。**1〜5 は講師が押す**（数から評価を作らない）。
     ・1〜5 を押した瞬間に：赤と印があれば焼き込んで返す（段階3以上）→ 評価とひとことを付ける → 次の子。
       確かめる窓は出さない。まちがえたら戻って押し直す（返した答案は差し替わる）。
     ・返し直す前の答案・前の評価は、この端末に控える（「前に戻す」で戻せる）。
     ・赤と印は、描くたびにこの端末に保存する（閉じても消えない）。
   ============================================================ */
(function(root){
"use strict";
var P = root.Paper, esc = P.esc;
var WORD = {5:"よくできた", 4:"できた", 3:"もう少し", 2:"がんばろう", 1:"やり直し"};
var STAMPS = [["maru", "◯"], ["batsu", "✕"], ["sankaku", "△"], ["nijumaru", "◎"]];
var DEFAULT_CHIPS = ["よくできました", "字をていねいに", "途中の式を書こう", "見直しをしよう", "やり直してもう一度出そう"];
var G = null;
var urls = [];

P.views.grade = {render:async function(main, arg){
  arg = arg || {};
  detachKeys();
  var start = function(course){
    P.pickLesson(main, course, {lead:"どの回を採点するか", onBack:function(){ P.show("grade"); },
      onPick:function(n){ open(main, course, n).catch(function(e){ P.failView(main, e); }); }})
     .catch(function(e){ P.failView(main, e); });
  };
  if(arg.key){
    var c = P.courses().filter(function(x){ return x.key === arg.key; })[0] || {key:arg.key, name:arg.key, use:4};
    if(arg.n != null) return open(main, c, arg.n);
    return start(c);
  }
  P.pickCourse(main, {title:"採点する", lead:"コースを選ぶ", showUse:true, onCourse:start});
}};

async function open(main, course, n){
  var d = await P.api.check(course.key, n);
  if(!d.lesson || d.lesson.n !== n) throw {error:"その回が見つかりません"};
  var chips = (await P.store.kv("chips", null)) || DEFAULT_CHIPS.slice();
  G = {course:course, key:course.key, n:n, lesson:d.lesson, use:(d.course || {}).use == null ? 4 : d.course.use,
       rows:d.rows || [], i:0, page:0, pages:[], items:{}, tool:"pen", zoom:1, finger:false, busy:false,
       cache:{}, chips:chips, main:main};
  var first = G.rows.findIndex(function(r){ return (r.files || []).length && (r.v == null || r.v < 1); });
  if(first < 0) first = G.rows.findIndex(function(r){ return (r.files || []).length; });
  G.i = Math.max(0, first);
  layout(main);
  attachKeys();
  await load(G.i);
}

function cur(){ return G.rows[G.i]; }
function pageKey(pg){ return pg.key; }
function marksId(r){ return (r.head || "") + "|" + r.sid; }

/* ---------- 画面の骨組み ---------- */
function layout(main){
  var toolBtns = '<div class="tools t5"><button class="txtb on" data-tool="pen">ペン</button>' +
    STAMPS.map(function(s){ return '<button data-tool="' + s[0] + '" aria-label="' + s[0] + '">' + s[1] + '</button>'; }).join("") + '</div>' +
    '<div class="tools t3"><button class="txtb" data-undo="1">ひとつ戻す</button><button class="txtb" data-clear="1">このページを消す</button><button class="txtb" data-finger="1">指で書く</button></div>';
  main.innerHTML =
    '<div class="row"><h1 style="margin-right:auto">' + esc(G.course.name) + '　' + esc(P.lessonName(G.lesson)) + '</h1>' +
      '<button class="btn2" data-zoom="-1">縮小</button><button class="btn2" data-zoom="1">拡大</button><button class="btn2" data-zoom="0">幅に合わせる</button></div>' +
    '<div class="mk-wrap"><div class="stage" id="stage"><div class="none">読んでいます…</div></div>' +
    '<div class="panel">' +
      '<div class="card"><div class="pwho" id="pwho"></div><div class="small muted" id="pinfo"></div><div class="dots" id="dots"></div></div>' +
      (G.use >= 3 ? '<div class="card"><div id="tools">' + toolBtns + '</div><div class="tally" id="tally" style="margin-top:8px"></div></div>'
                  : '<div class="card small muted">このコースは「' + esc(P.USE_WORD[G.use] || "") + '」の段階なので、赤を入れて返すことはできません（tubestudy の「導入と進度」で 3 にすると返せます）。評価とひとことは付けられます。</div>') +
      '<div class="card"><div class="small muted" style="margin-bottom:6px">押すと、' + (G.use >= 3 ? "赤を返して、" : "") + '評価とひとことを付けて次の子へ</div>' +
        '<div class="rates" id="rates">' + [5, 4, 3, 2, 1].map(function(v){ return '<button data-rate="' + v + '"><b>' + v + '</b><span>' + WORD[v] + '</span></button>'; }).join("") + '</div>' +
        '<textarea class="note" id="note" maxlength="200" placeholder="ひとこと（なくてもよい）" style="margin-top:10px"></textarea>' +
        '<div class="chips" id="chips" style="margin-top:8px"></div>' +
        '<div class="row" style="margin-top:8px"><button class="linkish small" id="back" hidden>前に戻す（この子の前の評価と答案）</button><span class="spacer"></span><button class="linkish small" id="editChips">ひとことの札を直す</button></div></div>' +
      '<div class="pnav"><button class="btn2" data-move="-1">前の子</button><button class="btn2" data-move="1">付けずに次へ</button></div>' +
      '<div class="card" id="byqCard" hidden><button class="btn2" id="toByq" style="width:100%">答案用紙を問題ごとに採点する</button></div>' +
      '<div class="card"><div class="small muted" style="margin-bottom:6px">この回の生徒</div><div class="queue" id="queue"></div>' +
        '<button class="linkish small" id="printRet">返した答案を番号順に刷る（対面の子に紙でも返すとき）</button></div>' +
    '</div></div>';
  drawChips();
  main.onclick = onClick;
  P.$("#note").oninput = function(){ saveMarks(); };
  P.$("#editChips").onclick = editChips;
  P.$("#back").onclick = goBack;
  P.$("#toByq").onclick = function(){ P.show("byq", {key:G.key, n:G.n, name:G.course.name}); };
  P.$("#printRet").onclick = function(){ printReturned().catch(P.fail); };
}

function drawChips(){
  P.$("#chips").innerHTML = G.chips.map(function(c, i){ return '<button data-chip="' + i + '">' + esc(c) + '</button>'; }).join("");
}

function drawQueue(){
  P.$("#queue").innerHTML = G.rows.map(function(r, i){
    var has = (r.files || []).length, done = r.v != null && r.v >= 1;
    return '<button class="' + (i === G.i ? "cur" : done ? "done" : !has ? "none" : "") + '" data-go-row="' + i + '">' +
           esc(P.names.of(r.sid) || r.label) + (done ? " " + r.v : "") + '</button>';
  }).join("");
}

function onClick(e){
  var t = e.target.closest("button");
  if(!t || G.busy) return;
  if(t.dataset.tool){ G.tool = t.dataset.tool; P.$$("#tools [data-tool]").forEach(function(b){ b.classList.toggle("on", b === t); }); return; }
  if(t.dataset.undo){ var it = G.items[pageKey(G.pages[G.page])] || []; it.pop(); redraw(); saveMarks(); return; }
  if(t.dataset.clear){ G.items[pageKey(G.pages[G.page])] = []; redraw(); saveMarks(); return; }
  if(t.dataset.finger){ G.finger = !G.finger; t.classList.toggle("on", G.finger); return; }
  if(t.dataset.rate){ rate(+t.dataset.rate); return; }
  if(t.dataset.move){ go(G.i + (+t.dataset.move)); return; }
  if(t.dataset.goRow){ go(+t.dataset.goRow); return; }
  if(t.dataset.page){ G.page = +t.dataset.page; show(); return; }
  if(t.dataset.zoom !== undefined){ var z = +t.dataset.zoom; G.zoom = z === 0 ? 1 : Math.max(0.6, Math.min(3, G.zoom * (z > 0 ? 1.25 : 0.8))); show(); return; }
  if(t.dataset.chip !== undefined){
    var n = P.$("#note"), c = G.chips[+t.dataset.chip];
    n.value = n.value ? (n.value.replace(/[。\s]*$/, "") + "。" + c) : c;
    saveMarks();
  }
}

/* ---------- 読む ---------- */
async function pagesFor(r){
  var out = [];
  for(var i = 0; i < (r.files || []).length; i++){
    var name = r.files[i], blob = await P.api.image(r.head, r.sid, name);
    if(/\.pdf$/i.test(name)){
      var ex = await root.PaperPDF.extract(new Uint8Array(await blob.arrayBuffer()));
      for(var k = 0; k < ex.pages.length; k++){
        var cv = P.img.limit(await P.img.fromPdfPage(ex.pages[k]), 2400);
        out.push({key:name + "#" + (k + 1), cv:r.origin === "teacher" ? cv : P.img.whiten(cv)});
      }
    } else {
      var c2 = P.img.limit(await P.img.blobToCanvas(blob), 2400);
      out.push({key:name, cv:r.origin === "teacher" ? c2 : P.img.whiten(c2)});
    }
  }
  return out;
}
function prefetch(i){
  var r = G.rows[i];
  if(!r || !(r.files || []).length || G.cache[r.sid]) return;
  G.cache[r.sid] = pagesFor(r).catch(function(){ delete G.cache[r.sid]; return null; });
}

async function load(i){
  G.i = i;
  var r = cur(), mine = G.i;
  G.page = 0; G.pages = []; G.items = {};
  P.$("#pwho").innerHTML = P.who(r);
  P.$("#pinfo").textContent = (i + 1) + "人目 / " + G.rows.length + "人" + (r.v ? "　いまの評価 " + r.v + "（" + WORD[r.v] + "）" : "") +
    ((r.returned || []).length ? "　返した答案 " + r.returned.length + "枚" : "");
  P.$("#note").value = r.note || "";
  P.$$("#rates button").forEach(function(b){ b.classList.toggle("on", +b.dataset.rate === r.v); });
  drawQueue();
  var saved = await P.store.get("marks", marksId(r));
  if(saved){ G.items = saved.items || {}; if(saved.note != null && saved.at > (r.ratedAt || 0) * 1000) P.$("#note").value = saved.note; }
  var hist = await historyOf(r);
  P.$("#back").hidden = !hist;
  var stage = P.$("#stage");
  if(!(r.files || []).length){
    stage.innerHTML = '<div class="none">' + (r.pruned ? "写真は保存期間を過ぎました" : "まだ出ていません") + '</div>';
    P.$("#dots").innerHTML = ""; tally();
    prefetch(i + 1);
    return;
  }
  stage.innerHTML = '<div class="none">読んでいます…</div>';
  prefetch(i);
  var pages = await G.cache[r.sid];
  if(mine !== G.i) return;                            // 読んでいる間に別の子へ移った
  if(!pages){ stage.innerHTML = '<div class="none">答案を読めませんでした。回線を確かめて、もう一度この子を押してください。</div>'; delete G.cache[r.sid]; return; }
  G.pages = pages;
  P.$("#dots").innerHTML = pages.length > 1 ? pages.map(function(p, k){ return '<button data-page="' + k + '">' + (k + 1) + '</button>'; }).join("") : "";
  show();
  prefetch(i + 1);
  var hasSheet = pages.some(function(p){ var gg = P.img.gray(p.cv, 900); return root.PaperCode.find(gg.g, gg.w, gg.h).some(function(c){ return c.type === 2; }); });
  P.$("#byqCard").hidden = !hasSheet;
}

/* ---------- 描く ---------- */
function show(){
  var stage = P.$("#stage"), pg = G.pages[G.page];
  if(!pg) return;
  P.$$("#dots button").forEach(function(b){ b.classList.toggle("on", +b.dataset.page === G.page); });
  var cssW = Math.max(200, (stage.clientWidth - 24) * G.zoom), k = cssW / pg.cv.width, cssH = pg.cv.height * k;
  var dpr = Math.min(2, window.devicePixelRatio || 1);
  var cv = stage.querySelector("canvas");
  if(!cv){ stage.innerHTML = ""; cv = document.createElement("canvas"); stage.appendChild(cv); wire(cv); }
  cv.style.width = cssW + "px"; cv.style.height = cssH + "px";
  cv.width = Math.round(cssW * dpr); cv.height = Math.round(cssH * dpr);
  G.k = cv.width / pg.cv.width;
  redraw();
}
function redraw(){
  var cv = P.$("#stage canvas"), pg = G.pages[G.page];
  if(!cv || !pg) return;
  var x = cv.getContext("2d");
  x.setTransform(1, 0, 0, 1, 0, 0);
  x.drawImage(pg.cv, 0, 0, cv.width, cv.height);
  P.img.drawItems(x, G.items[pageKey(pg)] || [], G.k);
  tally();
}
function tally(){
  var el = P.$("#tally");
  if(!el) return;
  var n = {maru:0, batsu:0, sankaku:0, nijumaru:0};
  Object.keys(G.items).forEach(function(k){ (G.items[k] || []).forEach(function(it){ if(it.t === "stamp" && n[it.k] != null) n[it.k]++; }); });
  var ok = n.maru + n.nijumaru, all = ok + n.batsu + n.sankaku;
  el.innerHTML = all ? '◯ <b>' + ok + '</b>　✕ <b>' + n.batsu + '</b>' + (n.sankaku ? '　△ <b>' + n.sankaku + '</b>' : "") + '　<span class="num">（' + ok + ' / ' + all + '）</span>' : "◯✕ はまだありません";
}

/* ペン（とマウス）で書く。指はふつう、答案を動かすだけ（「指で書く」を押したときだけ書く）。
   ペンで書いたあと 1.5秒は指を無視する（手のひら除け。tubestudy の「この画面で書く」と同じ）。 */
function wire(cv){
  var drawing = null, pan = null, penAt = 0, active = null;
  var stage = P.$("#stage");
  var pt = function(e){ var r = cv.getBoundingClientRect(); var s = G.pages[G.page].cv.width / r.width; return [(e.clientX - r.left) * s, (e.clientY - r.top) * s]; };
  cv.addEventListener("pointerdown", function(e){
    if(!G.pages[G.page] || active !== null) return;
    if(e.pointerType === "touch" && Date.now() - penAt < 1500) return;
    e.preventDefault();
    try { cv.setPointerCapture(e.pointerId); } catch(err){}
    active = e.pointerId;
    if(e.pointerType === "touch" && !G.finger || G.use < 3){
      pan = {x:e.clientX, y:e.clientY, l:stage.scrollLeft, t:stage.scrollTop};
      return;
    }
    if(e.pointerType === "pen") penAt = Date.now();
    var p = pt(e), W = G.pages[G.page].cv.width;
    if(G.tool === "pen") drawing = {t:"pen", c:"#D0021B", w:Math.max(3, W / 450), p:[p]};
    else drawing = {t:"stamp", k:G.tool, x:p[0], y:p[1], s:Math.max(30, W / 26)};
  });
  cv.addEventListener("pointermove", function(e){
    if(e.pointerId !== active) return;
    e.preventDefault();
    if(pan){ stage.scrollLeft = pan.l - (e.clientX - pan.x); stage.scrollTop = pan.t - (e.clientY - pan.y); return; }
    if(!drawing || drawing.t !== "pen") return;
    if(e.pointerType === "pen") penAt = Date.now();
    var p = pt(e), l = drawing.p[drawing.p.length - 1];
    if(Math.abs(p[0] - l[0]) + Math.abs(p[1] - l[1]) < 1.5) return;
    drawing.p.push(p);
    P.img.drawItems(cv.getContext("2d"), [{t:"pen", c:drawing.c, w:drawing.w, p:[l, p]}], G.k);
  });
  var end = function(e){
    if(e.pointerId !== active) return;
    active = null;
    if(pan){ pan = null; return; }
    if(!drawing) return;
    var key = pageKey(G.pages[G.page]);
    if(drawing.t === "stamp"){ var p = pt(e); drawing.x = p[0]; drawing.y = p[1]; }
    (G.items[key] = G.items[key] || []).push(drawing);
    drawing = null;
    redraw();
    saveMarks();
  };
  cv.addEventListener("pointerup", end);
  cv.addEventListener("pointercancel", function(e){ if(e.pointerId === active){ active = null; pan = null; drawing = null; redraw(); } });
}

var saveTimer = null;
function saveMarks(){
  clearTimeout(saveTimer);
  var r = cur();
  saveTimer = setTimeout(function(){
    P.store.put("marks", {id:marksId(r), aid:r.head, sid:r.sid, key:G.key, n:G.n, items:G.items, note:P.$("#note") ? P.$("#note").value : "", at:Date.now()});
  }, 250);
}

/* ---------- 付ける・返す ---------- */
function hasMarks(){ return Object.keys(G.items).some(function(k){ return (G.items[k] || []).length; }); }

async function burnFiles(){
  var cvs = G.pages.map(function(pg){ return P.img.burn(pg.cv, G.items[pageKey(pg)] || []); });
  if(cvs.length > 6){
    var pairs = [];
    for(var i = 0; i < cvs.length; i += 2) pairs.push(P.img.limit(P.img.side(cvs[i], cvs[i + 1] || null), 2600));
    cvs = pairs;
  }
  var out = [];
  for(i = 0; i < cvs.length; i++) out.push({type:"image/jpeg", b64:await P.b64(await P.img.toBlob(cvs[i], 0.85))});
  return out;
}

async function historyOf(r){
  var all = await P.store.all("history");
  return all.filter(function(h){ return h.kind === "grade" && h.aid === r.head && h.sid === r.sid; })
            .sort(function(a, b){ return b.at - a.at; })[0] || null;
}

async function rate(v){
  var r = cur();
  if(!r || G.busy) return;
  if(!(r.files || []).length && !confirm("この子はまだ出していません。それでも評価を付けますか。")) return;
  G.busy = true;
  var note = P.$("#note").value.trim();
  var marked = hasMarks() && G.use >= 3 && G.pages.length;
  try {
    /* 前の評価・前に返した答案を控える（前に戻す） */
    var prev = {id:"grade|" + r.head + "|" + r.sid + "|" + Date.now(), kind:"grade", aid:r.head, sid:r.sid, key:G.key, n:G.n,
                label:r.label, course:G.course.name, lesson:P.lessonName(G.lesson),
                at:Date.now(), v:r.v == null ? null : r.v, note:r.note || "", returned:[]};
    if(marked && (r.returned || []).length){
      for(var k = 0; k < r.returned.length; k++){
        try { prev.returned.push({name:r.returned[k], blob:await P.api.image(r.head, r.sid, r.returned[k])}); } catch(e){}
      }
    }
    await P.store.put("history", prev);
    if(marked){
      var files = await burnFiles();
      var got = await P.api.giveBack(r.head, r.sid, files, note);
      r.returned = ((got.sub || {}).returned || {}).files ? got.sub.returned.files.map(function(f){ return f.name; }) : r.returned;
    }
    await P.api.rate(G.key, G.n, r.sid, v, note);
    r.v = v; r.note = note; r.ratedAt = Date.now() / 1000;
    await P.store.put("marks", {id:marksId(r), aid:r.head, sid:r.sid, key:G.key, n:G.n, items:G.items, note:note, v:v, at:Date.now(), returnedAt:marked ? Date.now() : null});
    P.toast(r.label + "：" + v + "（" + WORD[v] + "）" + (marked ? "。赤を入れた答案を返しました" : ""));
    var nx = nextIndex(G.i);
    G.busy = false;
    if(nx >= 0) await load(nx); else { drawQueue(); P.toast("この回は全員おわりました"); }
  } catch(e){ G.busy = false; P.fail(e); }
}

function nextIndex(i){
  for(var k = i + 1; k < G.rows.length; k++) if((G.rows[k].files || []).length && (G.rows[k].v == null || G.rows[k].v < 1)) return k;
  for(k = 0; k < i; k++) if((G.rows[k].files || []).length && (G.rows[k].v == null || G.rows[k].v < 1)) return k;
  return -1;
}

function go(i){
  if(i < 0 || i >= G.rows.length) return;
  load(i).catch(P.fail);
}

/* 前に戻す：控えた前の評価（と、前に返した答案）に戻す */
async function goBack(){
  var r = cur(), h = await historyOf(r);
  if(!h || G.busy) return;
  if(!confirm("この子を、前の評価" + (h.v ? "（" + h.v + "）" : "（なし）") + (h.returned.length ? "と前に返した答案" : "") + "に戻します。よいですか。")) return;
  G.busy = true;
  try {
    if(h.returned.length){
      var files = [];
      for(var i = 0; i < h.returned.length; i++) files.push({type:h.returned[i].blob.type || "image/jpeg", b64:await P.b64(h.returned[i].blob)});
      await P.api.giveBack(r.head, r.sid, files, h.note);
    }
    await P.api.rate(G.key, G.n, r.sid, h.v == null ? null : h.v, h.note);
    r.v = h.v; r.note = h.note;
    await P.store.del("history", h.id);
    P.toast("前に戻しました" + (h.returned.length ? "" : "（返した答案は、tubestudy の側ではそのままです）"));
    G.busy = false;
    await load(G.i);
  } catch(e){ G.busy = false; P.fail(e); }
}

function editChips(){
  var body = P.sheet("ひとことの札", '<p class="small muted">1行に1つ。押すと、ひとことの欄に足されます。</p>' +
    '<label class="field"><textarea id="chipText">' + esc(G.chips.join("\n")) + '</textarea></label>' +
    '<div class="gap"></div><button class="btn" id="chipSave">決める</button>');
  P.$("#chipSave", body).onclick = function(){
    G.chips = P.$("#chipText", body).value.split(/\r?\n/).map(function(s){ return s.trim(); }).filter(Boolean).slice(0, 12);
    P.store.setKv("chips", G.chips);
    drawChips();
    P.closeSheet();
  };
}

/* 返した答案を、番号の順に A4 で刷る（1枚に1ページ。上に番号と名前（この端末の名前）） */
async function printReturned(){
  var d = await P.api.check(G.key, G.n), rows = (d.rows || []).filter(function(r){ return (r.returned || []).length; });
  if(!rows.length){ P.toast("まだ返した答案がありません", true); return; }
  P.toast("答案を読んでいます（" + rows.length + "人）");
  var html = "";
  for(var i = 0; i < rows.length; i++){
    var r = rows[i];
    for(var k = 0; k < r.returned.length; k++){
      var blob = await P.api.image(r.head, r.sid, r.returned[k]);
      var src = await new Promise(function(res){ var fr = new FileReader(); fr.onload = function(){ res(fr.result); }; fr.readAsDataURL(blob); });
      html += '<section class="pg ret"><div class="ret-h">' + esc(P.names.of(r.sid) || "") + '　' + esc(r.label) + '　' + esc(G.course.name) + '　' +
              esc(P.lessonName(G.lesson)) + (r.returned.length > 1 ? '　' + (k + 1) + '/' + r.returned.length : '') + '</div>' +
              '<img alt="" src="' + src + '"></section>';
    }
  }
  P.sheets.printHtml(html);
}

/* ---------- キー：1〜5・←→ ページ・↑↓ 子・z ひとつ戻す ---------- */
function onKey(e){
  if(!G || P.state.view !== "grade" || G.busy) return;
  if(e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
  if(/^[1-5]$/.test(e.key)){ e.preventDefault(); rate(+e.key); }
  else if(e.key === "ArrowRight" && G.page < G.pages.length - 1){ G.page++; show(); }
  else if(e.key === "ArrowLeft" && G.page > 0){ G.page--; show(); }
  else if(e.key === "ArrowDown"){ e.preventDefault(); go(G.i + 1); }
  else if(e.key === "ArrowUp"){ e.preventDefault(); go(G.i - 1); }
  else if(e.key === "z" && G.pages[G.page]){ (G.items[pageKey(G.pages[G.page])] || []).pop(); redraw(); saveMarks(); }
}
function attachKeys(){ document.addEventListener("keydown", onKey); window.addEventListener("resize", onResize); }
function detachKeys(){ document.removeEventListener("keydown", onKey); window.removeEventListener("resize", onResize); }
var rz = null;
function onResize(){ clearTimeout(rz); rz = setTimeout(function(){ if(G && P.state.view === "grade") show(); }, 150); }

P.grade = {state:function(){ return G; }, rate:rate, go:go};
})(window);
