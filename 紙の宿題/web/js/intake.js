/* ============================================================
   取り込む：PDF を入れる → 生徒ごとに分ける → 確かめる → tubestudy に送る
   ============================================================
   決めごと
     ・分けるのは番号シール（表紙）・区切り紙・答案用紙の印だけ。**印の無いページを推測で誰かに付けない**
       （前の表紙の続き以外は「だれ？」に置く）。
     ・表紙と区切り紙は送らない（名前が書いてある）。答案用紙は刷った名前の欄を白で消してから送る。
     ・白紙は外す（戻せる）。同じページの二度撮りは印を付けるだけで、外すのは講師（黙って消さない）。
     ・**生徒が自分で出した写真・前に取り込んだ紙は、既定では上書きしない。** 置き換えるときは、
       前のものをこの端末に控えてから送る（元に戻せる）。
     ・送ったら tubestudy から読み直して、枚数が合ったことを確かめる（嘘をつかない）。
     ・送った取り込みは7日でこの端末から消す（答案を端末に溜めない）。
   ============================================================ */
(function(root){
"use strict";
var P = root.Paper, esc = P.esc;
var BLANK = 0.0015, KEEP_SENT_DAYS = 7, MAX_FILES = 6;
var urls = [];
function url(blob){ var u = URL.createObjectURL(blob); urls.push(u); return u; }
function dropUrls(){ urls.forEach(function(u){ URL.revokeObjectURL(u); }); urls = []; }

P.intake = {
  drafts: async function(){
    var all = await P.store.all("batches");
    return all.filter(function(b){ return b.status !== "sent" && (b.pageIds || []).length; })
              .sort(function(a, b){ return b.createdAt - a.createdAt; });
  },
  cleanup: async function(){
    var cut = Date.now() - KEEP_SENT_DAYS * 86400000, all = await P.store.all("batches");
    for(var i = 0; i < all.length; i++){
      var b = all[i];
      if((b.status === "sent" && (b.sentAt || 0) < cut) || (!(b.pageIds || []).length && b.createdAt < cut)) await dropBatch(b);
    }
    var hist = await P.store.all("history");
    for(i = 0; i < hist.length; i++) if((hist[i].at || 0) < Date.now() - 30 * 86400000) await P.store.del("history", hist[i].id);
  },
  assign: assign
};

async function dropBatch(b){
  for(var i = 0; i < (b.pageIds || []).length; i++) await P.store.del("pages", b.pageIds[i]);
  await P.store.del("batches", b.id);
}

P.views.intake = {render:async function(main, arg){
  arg = arg || {};
  dropUrls();
  if(arg.batch){
    var b = await P.store.get("batches", arg.batch);
    if(b) return (b.pageIds || []).length ? review(main, b) : filesStep(main, b);
  }
  var start = function(course){
    P.pickLesson(main, course, {lead:"どの回の宿題を取り込むか（期限が今にいちばん近い回を青で囲んであります）",
      onBack:function(){ P.show("intake"); }, onPick:function(n){ begin(main, course, n).catch(function(e){ P.failView(main, e); }); }})
     .catch(function(e){ P.failView(main, e); });
  };
  if(arg.key){
    var c = P.courses().filter(function(x){ return x.key === arg.key; })[0];
    if(c) return start(c);
  }
  P.pickCourse(main, {title:"取り込む", lead:"コースを選ぶ（今日の授業は黄色）", onCourse:start});
}};

async function begin(main, course, n){
  var d = await P.api.check(course.key, n);
  if(!d.lesson || d.lesson.n !== n) throw {error:"その回が見つかりません"};
  var b = {id:"b" + P.uid(), key:course.key, n:n, courseName:course.name, lesson:d.lesson, use:(d.course || {}).use,
           rows:d.rows || [], createdAt:Date.now(), status:"draft", pageIds:[], replace:{}, results:{}, errors:[]};
  await P.store.put("batches", b);
  filesStep(main, b);
}

/* ---------- PDF・写真を選ぶ ---------- */
function filesStep(main, b){
  main.innerHTML = '<h1>' + esc(b.courseName) + '</h1><p class="lead">' + esc(P.lessonName(b.lesson)) + '　' + b.rows.length + '人</p>' +
    '<label class="drop" id="drop"><div class="t">撮った PDF・写真を選ぶ</div>' +
    '<div class="muted">いくつでも。順番のとおりに並べます</div>' +
    '<span class="btn">選ぶ</span><input type="file" id="files" multiple accept="application/pdf,image/*,.pdf"></label>' +
    '<div class="card" id="prog" hidden><div id="progText">開いています…</div><div class="bar"><i id="progBar"></i></div></div>' +
    '<div class="card"><h2>撮り方</h2><ol class="steps">' +
      '<li>ノート：表紙（番号シール）→ 宿題のページ → 次の子の表紙 … と続けて撮る（iPad の「書類をスキャン」）。</li>' +
      '<li>プリント：区切り紙を一番上に重ねた束を、複合機でカラーかグレーの PDF に。</li>' +
      '<li>答案用紙（ここで刷ったもの）：順番はばらばらでかまいません。</li></ol></div>' +
    '<div class="gap"></div><button class="linkish" id="quit">この取り込みをやめる</button>';
  var inp = P.$("#files"), drop = P.$("#drop");
  inp.onchange = function(){ if(inp.files.length) run(main, b, Array.prototype.slice.call(inp.files)); };
  drop.addEventListener("dragover", function(e){ e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", function(){ drop.classList.remove("over"); });
  drop.addEventListener("drop", function(e){ e.preventDefault(); drop.classList.remove("over"); run(main, b, Array.prototype.slice.call(e.dataTransfer.files)); });
  P.$("#quit").onclick = async function(){ await dropBatch(b); P.show("home"); };
}

async function run(main, b, files){
  P.$("#prog").hidden = false;
  P.$("#drop").hidden = true;
  try { await addFiles(b, files, function(t, frac){ P.$("#progText").textContent = t; P.$("#progBar").style.width = Math.round(frac * 100) + "%"; }); }
  catch(e){ P.fail(e); }
  review(main, b);
}

/* テスト（自動検査）からも呼ぶ */
async function addFiles(b, files, progress){
  progress = progress || function(){};
  var order = (b.pageIds || []).length, errors = [];
  for(var fi = 0; fi < files.length; fi++){
    var f = files[fi], name = f.name || ("ファイル" + (fi + 1));
    try {
      if(f.type === "application/pdf" || /\.pdf$/i.test(name)){
        progress(name + " を開いています", fi / files.length);
        var ex = await root.PaperPDF.extract(new Uint8Array(await f.arrayBuffer()));
        ex.errors.forEach(function(er){ errors.push(name + " の " + er.page + "ページ目：" + er.error); });
        for(var i = 0; i < ex.pages.length; i++){
          progress(name + "　" + (i + 1) + " / " + ex.pages.length + " ページ", (fi + (i + 1) / ex.pages.length) / files.length);
          var cv = await P.img.fromPdfPage(ex.pages[i]);
          await addPage(b, cv, {file:name, page:ex.pages[i].index}, order++);
          await P.sleep(0);
        }
      } else if(/^image\//.test(f.type) || /\.(jpe?g|png|heic|heif)$/i.test(name)){
        progress(name, (fi + 1) / files.length);
        var cv2 = await P.img.fromFile(f);
        await addPage(b, cv2, {file:name, page:1}, order++);
      } else errors.push(name + "：PDF か写真ではありません");
    } catch(e){ errors.push(name + "：" + (e.message || e.error || "読めませんでした")); }
  }
  b.errors = (b.errors || []).concat(errors);
  var pages = await pagesOf(b);
  assign(b, pages);
  for(var k = 0; k < pages.length; k++) await P.store.put("pages", pages[k]);
  await P.store.put("batches", b);
  return {errors:errors, pages:pages.length};
}
P.intake.addFiles = addFiles;

function pickCode(codes){
  var t2 = codes.filter(function(c){ return c.type === 2; });
  return t2[0] || codes[0] || null;
}

async function addPage(b, cv, src, order){
  var gg = P.img.gray(cv, 1400), code = pickCode(root.PaperCode.find(gg.g, gg.w, gg.h));
  if(code && code.turns){
    cv = P.img.rotate(cv, code.turns);
    gg = P.img.gray(cv, 1400);
    code = pickCode(root.PaperCode.find(gg.g, gg.w, gg.h)) || code;
  }
  var masks = [];
  if(code && code.type === 2){ var m = P.sheets.nameMaskFromCode(code, gg.w, gg.h); if(m) masks.push(m); }
  var out = P.img.whiten(P.img.limit(cv, P.img.OUT_LONG));
  var rec = {id:b.id + "-" + ("000" + order).slice(-4), batchId:b.id, order:order, src:src,
             code:code ? {type:code.type, sid:code.sid, tmpl:code.tmpl, page:code.page} : null,
             masks:masks, ink:P.img.ink(out), hash:P.img.dhash(out),
             blob:await P.img.toBlob(out, 0.8), thumb:await P.img.toBlob(P.img.limit(out, P.img.THUMB), 0.7),
             w:out.width, h:out.height, include:true, hand:null, turn:0};
  cv.width = 0; out.width = 0;
  await P.store.put("pages", rec);
  b.pageIds.push(rec.id);
}

async function pagesOf(b){
  var out = [];
  for(var i = 0; i < b.pageIds.length; i++){ var p = await P.store.get("pages", b.pageIds[i]); if(p) out.push(p); }
  return out.sort(function(x, y){ return x.order - y.order; });
}

/* 生徒を決める：表紙（種類1）から次の表紙までは同じ生徒。答案用紙（種類2）はその紙の印。
   それ以外は決めない（だれ？）。講師が手で決めたもの（hand）はそのまま。 */
function assign(b, pages){
  var cur = null, prev = null;
  pages.sort(function(x, y){ return x.order - y.order; }).forEach(function(p){
    p.dup = false;
    if(p.code && p.code.type === 1){ cur = p.code.sid; p.kind = p.sendCover ? "page" : "cover"; p.auto = p.code.sid; }
    else if(p.code && p.code.type === 2){ p.kind = "sheet"; p.auto = p.code.sid; }
    else {
      p.kind = p.ink < BLANK && !p.keepBlank ? "blank" : "page";
      p.auto = cur;
      if(prev && prev.kind === "page" && p.kind === "page" && P.img.hamming(prev.hash, p.hash) <= 3) p.dup = true;
    }
    p.sid = p.hand ? p.hand : p.auto;
    prev = p;
  });
  b.pageCount = pages.filter(function(p){ return (p.kind === "page" || p.kind === "sheet") && p.include !== false; }).length;
  return pages;
}

function sendable(p){ return (p.kind === "page" || p.kind === "sheet") && p.include !== false && !!p.sid; }

/* ---------- 確かめる ---------- */
async function review(main, b){
  dropUrls();
  var pages = await pagesOf(b);
  assign(b, pages);
  var roster = {};
  b.rows.forEach(function(r){ roster[r.sid] = r; });
  var by = {}, who = [], stranger = [], off = [];
  pages.forEach(function(p){
    if(p.kind === "blank" || p.include === false){ off.push(p); return; }
    if(!p.sid){ if(p.kind !== "cover") who.push(p); return; }
    if(!roster[p.sid]){ stranger.push(p); return; }
    if(p.kind === "cover") return;                    // 表紙は下で別に出す（送らない）
    (by[p.sid] = by[p.sid] || []).push(p);
  });
  var sendRows = b.rows.filter(function(r){ return canSend(b, r, by[r.sid]); });
  var nPages = sendRows.reduce(function(s, r){ return s + by[r.sid].filter(sendable).length; }, 0);
  var thumb = function(p){
    var cls = "th" + (p.kind === "cover" ? " cover" : "") + (p.include === false || p.kind === "blank" ? " off" : "");
    var tag = p.kind === "cover" ? '<span class="tag">表紙（送らない）</span>' : p.kind === "sheet" ? '<span class="tag">答案用紙</span>' :
              p.dup ? '<span class="tag y">同じページ？</span>' : p.kind === "blank" ? '<span class="tag">白紙</span>' :
              p.hand ? '<span class="tag">手で決めた</span>' : "";
    return '<button class="' + cls + '" data-page="' + esc(p.id) + '"><img alt="" src="' + url(p.thumb) + '">' + tag +
           '<span class="cap">' + esc(p.src.file.replace(/\.pdf$/i, "")) + ' ' + p.src.page + '</span></button>';
  };
  var rowHtml = b.rows.map(function(r){
    var ps = by[r.sid] || [], covers = pages.filter(function(p){ return p.kind === "cover" && p.sid === r.sid; });
    var res = b.results[r.sid], chips = [], acts = "";
    var existing = (r.files || []).length;
    if(res && res.ok) chips.push('<span class="chip solid">送った ' + res.count + '枚' + (res.verified ? "（tubestudy で確かめました）" : "") + '</span>');
    else if(res && res.error) chips.push('<span class="chip yellow">送れなかった：' + esc(res.error) + '</span>');
    if(existing && !(res && res.ok)){
      chips.push('<span class="chip ' + (b.replace[r.sid] ? "yellow" : "") + '">' +
                 (r.origin === "teacher" ? "前に取り込んだ紙 " : "生徒が出した写真 ") + existing + '枚' + (b.replace[r.sid] ? "を置き換える" : "があるので送らない") + '</span>');
      if(ps.filter(sendable).length) acts = '<button class="btn2" data-replace="' + esc(r.sid) + '">' + (b.replace[r.sid] ? "置き換えない" : "置き換える") + '</button>' +
               (b.replace[r.sid] ? "" : '<span class="small muted">前のものは、この端末に控えてから置き換えます</span>');
    }
    if(!r.head) chips.push('<span class="chip">この回に紙の宿題がありません</span>');
    if(!ps.length && !existing) chips.push('<span class="chip">なし</span>');
    return '<div class="rrow' + (ps.length || existing ? "" : " off") + '"><div><div class="nm">' + P.who(r) + '</div>' +
           '<div class="st">' + chips.join("") + '</div>' + (acts ? '<div class="acts">' + acts + '</div>' : "") + '</div>' +
           '<div class="thumbs">' + covers.map(thumb).join("") + ps.map(thumb).join("") + '</div></div>';
  }).join("");
  var whoRow = who.length ? '<div class="rrow who"><div><div class="nm">だれ？</div><div class="st"><span class="chip yellow">' + who.length +
      'ページ（送りません）</span></div><div class="acts small muted">押して、だれの紙かを選ぶ</div></div><div class="thumbs">' + who.map(thumb).join("") + '</div></div>' : "";
  var strRow = stranger.length ? '<div class="rrow who"><div><div class="nm">この回にいない生徒の印</div><div class="st"><span class="chip yellow">' + stranger.length +
      'ページ（送りません）</span></div><div class="acts small muted">別の教科のノートかもしれません。押して選び直す</div></div><div class="thumbs">' + stranger.map(thumb).join("") + '</div></div>' : "";
  var offRow = off.length ? '<details class="card"><summary>外したページ（白紙・外したもの）' + off.length + '</summary><div class="gap"></div><div class="thumbs">' + off.map(thumb).join("") + '</div></details>' : "";
  var errs = (b.errors || []).length ? '<div class="notice">' + b.errors.map(esc).join("<br>") + '</div>' : "";
  main.innerHTML = '<h1>' + esc(b.courseName) + '</h1><p class="lead">' + esc(P.lessonName(b.lesson)) + '</p>' + errs +
    '<div class="sumline"><span class="big num">' + sendRows.length + '人に ' + nPages + 'ページ</span>' +
      (who.length ? '<span class="chip yellow">だれ？ ' + who.length + '</span>' : "") +
      '<span class="spacer"></span>' +
      ((b.use == null || b.use >= 3) ? '<button class="btn2' + (b.marked ? " on" : "") + '" id="marked">' + (b.marked ? "赤を入れた紙として返す" : "赤はまだ（これから採点）") + '</button>' : "") +
      '<button class="btn2" id="more">PDF・写真を足す</button>' +
      '<button class="btn" id="send"' + (sendRows.length ? "" : " disabled") + '>' + sendRows.length + '人ぶんを送る</button></div>' +
    (b.marked ? '<div class="notice">この紙はもう赤を入れてあるものとして、出された紙に入れると同時に、生徒と保護者の「先生から」に返します。評価（1〜5）は「採点する」で付けられます。</div><div class="gap"></div>' : "") +
    whoRow + strRow + '<div class="rrows">' + rowHtml + '</div>' + offRow +
    '<div class="gap"></div><button class="linkish" id="quit">この取り込みをやめる（この端末から消す）</button>';
  main.onclick = function(e){
    var t = e.target.closest("[data-page]");
    if(t){ pageSheet(main, b, pages.filter(function(p){ return p.id === t.dataset.page; })[0]); return; }
    var rp = e.target.closest("[data-replace]");
    if(rp){ b.replace[rp.dataset.replace] = !b.replace[rp.dataset.replace]; P.store.put("batches", b).then(function(){ review(main, b); }); }
  };
  P.$("#more").onclick = function(){ filesStep(main, b); };
  if(P.$("#marked")) P.$("#marked").onclick = async function(){ b.marked = !b.marked; await P.store.put("batches", b); review(main, b); };
  P.$("#send").onclick = function(){ send(main, b).catch(P.fail); };
  P.$("#quit").onclick = async function(){
    if(!confirm("この取り込みを、この端末から消します（tubestudy に送ったものは消えません）。よいですか。")) return;
    await dropBatch(b); P.show("home");
  };
}

function canSend(b, r, ps){
  if(!r.head || !ps || !ps.filter(sendable).length) return false;
  var res = b.results[r.sid];
  if(res && res.ok) return false;
  if((r.files || []).length && !b.replace[r.sid]) return false;
  return true;
}

/* ---------- 1枚を大きく：だれの紙？・外す・回す・名前の欄を消す ---------- */
function pageSheet(main, b, p){
  if(!p) return;
  var roster = b.rows;
  var body = P.sheet("ページ " + p.src.page + "（" + p.src.file + "）",
    '<div class="big-page" id="bp"><img alt="" src="' + url(p.blob) + '">' +
      (p.masks || []).map(function(m){ return '<div class="rect" style="left:' + m[0] * 100 + '%;top:' + m[1] * 100 + '%;width:' + m[2] * 100 + '%;height:' + m[3] * 100 + '%"></div>'; }).join("") +
    '</div>' +
    '<div class="row" style="margin-top:12px">' +
      '<button class="btn2" data-a="who">だれの紙？</button>' +
      (p.kind === "cover" ? '<button class="btn2" data-a="cover">この紙も送る</button>' : "") +
      (p.kind === "blank" ? '<button class="btn2" data-a="keep">白紙ではない（送る）</button>' : "") +
      '<button class="btn2" data-a="inc">' + (p.include === false ? "送る紙に戻す" : "外す") + '</button>' +
      '<button class="btn2" data-a="rot">右に回す</button>' +
      '<button class="btn2" data-a="mask">名前の欄を白で消す</button>' +
      ((p.masks || []).length ? '<button class="btn2" data-a="unmask">消す欄を取り消す</button><button class="btn2" data-a="maskall">同じ場所を、この取り込みの全ページに</button>' : "") +
    '</div><div id="whoList"></div><p class="small muted" id="mhint" hidden>名前の欄の上を、指かマウスでなぞって四角を作ります。</p>', {wide:true});
  var save = async function(){ var pages = await pagesOf(b); pages = pages.map(function(x){ return x.id === p.id ? p : x; }); assign(b, pages); await P.store.put("pages", p); await P.store.put("batches", b); };
  body.onclick = async function(e){
    var a = e.target.closest("[data-a]"), w = e.target.closest("[data-sid]");
    if(w){ p.hand = w.dataset.sid || null; if(!w.dataset.sid){ p.include = false; } else p.include = true; await save(); P.closeSheet(); review(main, b); return; }
    if(!a) return;
    var act = a.dataset.a;
    if(act === "who"){
      P.$("#whoList", body).innerHTML = '<div class="gap"></div><div class="pick-list">' + roster.map(function(r){
        return '<button class="btn2' + (p.sid === r.sid ? " on" : "") + '" data-sid="' + esc(r.sid) + '">' + P.who(r) + '</button>';
      }).join("") + '<button class="btn2" data-sid="">だれでもない（外す）</button></div>';
      return;
    }
    if(act === "cover"){ p.sendCover = true; p.include = true; }
    if(act === "keep"){ p.keepBlank = true; p.include = true; }
    if(act === "inc") p.include = p.include === false;
    if(act === "rot"){
      var cv = P.img.rotate(await P.img.blobToCanvas(p.blob), 1);
      p.masks = (p.masks || []).map(function(m){ return [1 - m[1] - m[3], m[0], m[3], m[2]]; });
      p.blob = await P.img.toBlob(cv, 0.8); p.thumb = await P.img.toBlob(P.img.limit(cv, P.img.THUMB), 0.7);
      p.w = cv.width; p.h = cv.height;
    }
    if(act === "unmask") p.masks = [];
    if(act === "maskall"){
      var m0 = p.masks[p.masks.length - 1], all = await pagesOf(b);
      for(var i = 0; i < all.length; i++){
        if(all[i].id === p.id || all[i].kind === "cover") continue;
        all[i].masks = (all[i].masks || []).concat([m0]);
        await P.store.put("pages", all[i]);
      }
      P.toast("同じ場所を、ほかの " + (all.length - 1) + "ページでも消します");
    }
    if(act === "mask"){ startMask(body, p, async function(){ await save(); pageSheet(main, b, p); }); return; }
    await save();
    P.closeSheet();
    review(main, b);
  };
}

function startMask(body, p, done){
  var bp = P.$("#bp", body), hint = P.$("#mhint", body), start = null, box = null;
  hint.hidden = false;
  var pos = function(e){ var r = bp.getBoundingClientRect(); return [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))]; };
  bp.onpointerdown = function(e){ e.preventDefault(); start = pos(e); box = document.createElement("div"); box.className = "rect"; bp.appendChild(box); bp.setPointerCapture(e.pointerId); };
  bp.onpointermove = function(e){
    if(!start) return;
    var q = pos(e), x = Math.min(start[0], q[0]), y = Math.min(start[1], q[1]), w = Math.abs(q[0] - start[0]), h = Math.abs(q[1] - start[1]);
    box.style.left = x * 100 + "%"; box.style.top = y * 100 + "%"; box.style.width = w * 100 + "%"; box.style.height = h * 100 + "%";
    box.dataset.r = JSON.stringify([x, y, w, h]);
  };
  bp.onpointerup = function(){
    if(!start) return;
    start = null;
    var r = box && box.dataset.r ? JSON.parse(box.dataset.r) : null;
    bp.onpointerdown = bp.onpointermove = bp.onpointerup = null;
    if(r && r[2] > 0.01 && r[3] > 0.005){ p.masks = (p.masks || []).concat([r]); done(); }
  };
}

/* ---------- 送る ---------- */
async function filesFor(ps){
  var cvs = [];
  for(var i = 0; i < ps.length; i++){
    var p = ps[i];
    if(!(p.masks || []).length && ps.length <= MAX_FILES){ cvs.push({blob:p.blob}); continue; }
    cvs.push({cv:P.img.mask(await P.img.blobToCanvas(p.blob), p.masks)});
  }
  if(cvs.length > MAX_FILES * 2) throw new Error("1人12ページまでです。分けて取り込んでください");
  if(cvs.length > MAX_FILES){
    var pairs = [];
    for(i = 0; i < cvs.length; i += 2){
      var a = cvs[i].cv || await P.img.blobToCanvas(cvs[i].blob), c2 = cvs[i + 1] ? (cvs[i + 1].cv || await P.img.blobToCanvas(cvs[i + 1].blob)) : null;
      pairs.push({cv:P.img.limit(P.img.side(a, c2), 2600)});
    }
    cvs = pairs;
  }
  var out = [];
  for(i = 0; i < cvs.length; i++){
    var bl = cvs[i].blob || await P.img.toBlob(cvs[i].cv, 0.8);
    out.push({type:"image/jpeg", b64:await P.b64(bl)});
  }
  return out;
}

async function send(main, b){
  var btn = P.$("#send");
  if(btn){ btn.disabled = true; btn.textContent = "送っています…"; }
  var d = await P.api.check(b.key, b.n);                // 送る直前に読み直す（クラス替え・生徒の提出）
  b.rows = d.rows || b.rows;
  var pages = await pagesOf(b);
  assign(b, pages);
  var by = {};
  pages.forEach(function(p){ if(sendable(p)) (by[p.sid] = by[p.sid] || []).push(p); });
  var todo = b.rows.filter(function(r){ return canSend(b, r, by[r.sid]); });
  for(var i = 0; i < todo.length; i++){
    var r = todo[i], ps = by[r.sid];
    if(btn) btn.textContent = "送っています " + (i + 1) + " / " + todo.length;
    try {
      if((r.files || []).length){                         // 置き換える前に、前のものを控える
        var keep = [];
        for(var k = 0; k < r.files.length; k++){
          try { keep.push({name:r.files[k], blob:await P.api.image(r.head, r.sid, r.files[k])}); } catch(e){}
        }
        await P.store.put("history", {id:"scan|" + r.head + "|" + r.sid + "|" + Date.now(), kind:"scan", aid:r.head, sid:r.sid,
                                      key:b.key, n:b.n, label:r.label, course:b.courseName, lesson:P.lessonName(b.lesson),
                                      at:Date.now(), origin:r.origin || "", files:keep});
      }
      var files = await filesFor(ps);
      await P.api.scan(r.head, r.sid, files);
      if(b.marked){
        if((r.returned || []).length){
          var prevRet = [];
          for(var q = 0; q < r.returned.length; q++){
            try { prevRet.push({name:r.returned[q], blob:await P.api.image(r.head, r.sid, r.returned[q])}); } catch(e){}
          }
          await P.store.put("history", {id:"grade|" + r.head + "|" + r.sid + "|" + Date.now(), kind:"grade", aid:r.head, sid:r.sid,
                                        key:b.key, n:b.n, label:r.label, course:b.courseName, lesson:P.lessonName(b.lesson),
                                        at:Date.now(), v:r.v == null ? null : r.v, note:r.note || "", returned:prevRet});
        }
        await P.api.giveBack(r.head, r.sid, files, r.note || "");
      }
      b.results[r.sid] = {ok:true, at:Date.now(), count:files.length, pages:ps.length, returned:!!b.marked};
    } catch(e){
      b.results[r.sid] = {ok:false, error:(e && (e.error || e.message)) || "送れませんでした"};
      if(e && e.status === 401){ await P.store.put("batches", b); throw e; }
    }
    await P.store.put("batches", b);
  }
  /* tubestudy から読み直して、枚数が合ったかを確かめる */
  try {
    var d2 = await P.api.check(b.key, b.n), got = {};
    (d2.rows || []).forEach(function(x){ got[x.sid] = x; });
    Object.keys(b.results).forEach(function(sid){
      var res = b.results[sid], x = got[sid];
      if(res.ok) res.verified = !!(x && (x.files || []).length === res.count && x.origin === "teacher");
    });
  } catch(e){}
  var left = b.rows.filter(function(r){ return canSend(b, r, by[r.sid]); }).length;
  b.status = left ? "partial" : "sent";
  if(!left) b.sentAt = Date.now();
  await P.store.put("batches", b);
  done(main, b);
}

function done(main, b){
  var ok = [], bad = [], unver = [];
  Object.keys(b.results).forEach(function(sid){
    var r = b.results[sid], row = b.rows.filter(function(x){ return x.sid === sid; })[0] || {sid:sid, label:sid};
    if(r.ok){ ok.push(row); if(!r.verified) unver.push(row); } else bad.push({row:row, error:r.error});
  });
  var pages = ok.reduce(function(s, row){ return s + (b.results[row.sid].pages || 0); }, 0);
  main.innerHTML = '<h1>' + (bad.length ? "送れなかった人がいます" : "送りました") + '</h1>' +
    '<p class="lead">' + esc(b.courseName) + '　' + esc(P.lessonName(b.lesson)) + '</p>' +
    '<div class="card"><div class="pwho num">' + ok.length + '人に ' + pages + 'ページ</div>' +
      (ok.length && !unver.length ? '<p class="ok">tubestudy から読み直して、全員の枚数が合っていることを確かめました。</p>' : "") +
      (unver.length ? '<p class="warn-text">tubestudy の枚数とまだ合っていない人：' + unver.map(function(r){ return P.who(r); }).join("、") + '</p>' : "") +
      (bad.length ? '<p class="warn-text">' + bad.map(function(x){ return P.who(x.row) + "：" + esc(x.error); }).join("<br>") + '</p><button class="btn2" id="again">もう一度送る</button>' : "") +
    '</div>' +
    '<div class="notice">撮った元の PDF は、答案の写しです。送り終えたら「ファイル」から消してください（この画面の中の写しは7日で消えます）。</div>' +
    '<div class="two"><button class="act" id="toGrade"><div class="t">この回を採点する</div><div class="s">対面の子もオンラインの子も、同じ列に並んでいます</div></button>' +
    '<button class="act" data-go="home"><div class="t">ホーム</div><div class="s">今日やること</div></button></div>';
  if(P.$("#again")) P.$("#again").onclick = function(){ review(main, b); };
  P.$("#toGrade").onclick = function(){ P.show("grade", {key:b.key, n:b.n}); };
}

})(window);
