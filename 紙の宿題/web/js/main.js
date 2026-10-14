/* ============================================================
   起動・ログイン・ホーム・コースと回を選ぶ・刷る・名前・使い方
   ============================================================ */
(function(root){
"use strict";
var P = root.Paper;
var esc = P.esc;

/* ---------- ログイン ---------- */
P.views.login = {render:function(main){
  P.$("#logout").hidden = true;
  P.$("#whoami").textContent = "";
  main.innerHTML =
    '<div class="login card">' +
      '<h1>紙の宿題</h1>' +
      '<p class="lead">tubestudy の講師の ID とパスワードで入ります。</p>' +
      '<label class="field"><span>ID</span><input id="lid" autocomplete="username" autocapitalize="off" spellcheck="false"></label>' +
      '<label class="field"><span>パスワード</span><input id="lpw" type="password" autocomplete="current-password"></label>' +
      '<div class="gap"></div><button class="btn big wide" id="lgo">入る</button>' +
      '<p class="small muted" style="margin-top:14px">ここで入れた ID とパスワードは、tubestudy に取り次ぐだけで、この画面の置き場には残りません。</p>' +
    '</div>';
  var go = async function(){
    var id = P.$("#lid").value.trim(), pw = P.$("#lpw").value;
    if(!id || !pw){ P.toast("ID とパスワードを入れてください", true); return; }
    P.$("#lgo").disabled = true;
    try {
      var prof = await P.api.login(id, pw);
      if(prof.role !== "teacher"){ await P.api.logout(); P.toast("講師の ID で入ってください", true); return; }
      P.state.profile = prof;
      afterLogin();
      P.show("home");
    } catch(e){ P.fail(e); }
    finally { var b = P.$("#lgo"); if(b) b.disabled = false; }
  };
  P.$("#lgo").onclick = go;
  P.$("#lpw").onkeydown = function(e){ if(e.key === "Enter") go(); };
  setTimeout(function(){ var i = P.$("#lid"); if(i) i.focus(); }, 50);
}};

function afterLogin(){
  var p = P.state.profile || {};
  P.$("#whoami").textContent = "講師" + (p.schoolName ? "（" + p.schoolName + "）" : "");
  P.$("#logout").hidden = false;
}

/* ---------- ホーム ---------- */
P.views.home = {render:async function(main){
  var drafts = await P.intake.drafts();
  var courses = P.courses(), near = courses.filter(function(c){ return c.near; })[0];
  var today = null;
  try { today = await P.api.today(); } catch(e){ if(e.status === 401) throw e; }
  var task = today && (today.tasks || [])[0];
  var next;
  if(drafts.length){
    var d = drafts[0];
    next = '<button class="next" data-draft="' + esc(d.id) + '"><div class="k">送っていない取り込みがあります</div>' +
           '<div class="t">' + esc(d.courseName) + '　' + esc(P.lessonName(d.lesson)) + '</div>' +
           '<div class="s">' + (d.pageCount || 0) + 'ページ　確かめて送る</div></button>';
  } else if(near){
    next = '<button class="next" data-intake="' + esc(near.key) + '"><div class="k">今日の授業</div>' +
           '<div class="t">' + esc(near.name) + '（' + esc(near.today) + '）の宿題を取り込む</div>' +
           '<div class="s">集めたノートを表紙から続けて撮り、PDF を入れる</div></button>';
  } else if(task && task.todo){
    next = '<button class="next" data-grade="' + esc(task.key) + '" data-n="' + task.n + '"><div class="k">宿題チェック</div>' +
           '<div class="t">' + esc(task.name) + '　' + esc(P.lessonName(task)) + '</div>' +
           '<div class="s">採点　あと' + task.todo + '人</div></button>';
  } else next = "";
  var gradeHint = task && task.todo ? "いちばん古い回：" + esc(task.name) + "　あと" + task.todo + "人" : "ページを順に見て、赤と◯✕と数字を入れる";
  main.innerHTML =
    '<h1>今日やること</h1>' +
    (P.store.ok ? "" : '<div class="notice">この端末では、途中の取り込みを保存できません（プライベートブラウズなど）。閉じると消えます。</div>') +
    next +
    '<div class="two">' +
      '<button class="act" data-go="intake"><div class="t">取り込む</div><div class="s">撮った PDF を入れて、生徒ごとに分けて tubestudy に送る</div></button>' +
      '<button class="act" data-go="grade"><div class="t">採点する</div><div class="s">' + gradeHint + '</div></button>' +
    '</div>' +
    '<div class="more">' +
      '<button class="btn2" data-go="print" data-kind="label">番号シールを刷る</button>' +
      '<button class="btn2" data-go="print" data-kind="sep">区切り紙を刷る</button>' +
      '<button class="btn2" data-go="print" data-kind="ans">答案用紙を刷る</button>' +
      '<button class="btn2" data-go="names">名前（この端末だけ）</button>' +
      '<button class="btn2" data-go="history">控えから戻す</button>' +
      '<button class="btn2" data-go="help">使い方</button>' +
    '</div>';
  main.onclick = function(e){
    var b = e.target.closest("button");
    if(!b) return;
    if(b.dataset.draft) P.show("intake", {batch:b.dataset.draft});
    else if(b.dataset.intake) P.show("intake", {key:b.dataset.intake});
    else if(b.dataset.grade) P.show("grade", {key:b.dataset.grade, n:+b.dataset.n});
    else if(b.dataset.go === "print") P.show("print", {kind:b.dataset.kind});
  };
}};

/* ---------- コースと回を選ぶ（取り込む・採点する・刷る） ---------- */
P.pickCourse = function(main, opt){
  var list = P.courses().filter(function(c){ return c.use >= (opt.minUse || 1); });
  var paper = P.courses().length - list.length;
  main.innerHTML = '<h1>' + esc(opt.title) + '</h1><p class="lead">' + esc(opt.lead || "コースを選ぶ") + '</p>' +
    (list.length ? '<div class="cgrid">' + list.map(function(c){
      return '<button class="ccard' + (c.today ? " today" : "") + (c.near ? " now" : "") + '" data-key="' + esc(c.key) + '">' +
             '<div class="n">' + esc(c.name) + '</div>' +
             '<div class="i">' + (c.today ? "今日 " + esc(c.today) : esc(slotText(c))) + (c.use < 3 && opt.showUse ? "　" + esc(P.USE_WORD[c.use]) : "") + '</div></button>';
    }).join("") + '</div>' : '<div class="card">tubestudy で「使う」にしているコースがありません。</div>') +
    (paper ? '<p class="small muted" style="margin-top:14px">紙のままのコース（' + paper + '）は出していません。tubestudy の「導入と進度」で 1 以上にすると出ます。</p>' : '');
  main.onclick = function(e){
    var b = e.target.closest("[data-key]");
    if(b) opt.onCourse(list.filter(function(c){ return c.key === b.dataset.key; })[0]);
  };
};
var WDN = ["", "月", "火", "水", "木", "金", "土"];
function slotText(c){
  var s = c.slots.filter(function(x){ return x.day; })[0];
  return s ? WDN[s.day] + " " + (s.start || "") : "";
}

/* 回を選ぶ。期限の来た回（新しい順）に、期限前の次の回と、この端末で作った提出箱を足す。 */
P.pickLesson = async function(main, course, opt){
  main.innerHTML = '<h1>' + esc(course.name) + '</h1><p class="lead">読んでいます…</p>';
  var d = await P.api.check(course.key), items = (d.lessons || []).slice();
  var seen = {};
  items.forEach(function(l){ seen[l.n] = 1; });
  var maxN = items.filter(function(l){ return l.n < 900; }).reduce(function(m, l){ return Math.max(m, l.n); }, 0);
  for(var k = 1; k <= 2; k++){
    var cand = maxN + k;
    try {
      var d2 = await P.api.check(course.key, cand);
      /* 期限がこれから来る回だけ（授業の前に集めたとき）。過ぎた古い回は足さない（一覧は新しい4回まで） */
      if(d2.lesson && d2.lesson.n === cand && !seen[cand] && (d2.lesson.dueAt || 0) > Date.now()){
        seen[cand] = 1;
        items.push(Object.assign({}, d2.lesson, {future:true, total:(d2.stats || {}).n, submitted:(d2.stats || {}).submitted, todo:(d2.stats || {}).todo}));
      }
    } catch(e){}
  }
  var quizzes = ((await P.store.kv("quizzes", [])) || []).filter(function(q){ return q.key === course.key && !seen[q.n]; });
  for(var i = 0; i < quizzes.length; i++){
    try {
      var d3 = await P.api.check(course.key, quizzes[i].n);
      if(d3.lesson && d3.lesson.n === quizzes[i].n){
        seen[quizzes[i].n] = 1;
        items.push(Object.assign({}, d3.lesson, {future:(d3.lesson.dueAt || 0) > Date.now(), total:(d3.stats || {}).n, submitted:(d3.stats || {}).submitted, todo:(d3.stats || {}).todo}));
      }
    } catch(e){}
  }
  /* いちばん近い回（期限が今にいちばん近いもの）を青く囲む */
  var now = Date.now(), best = null;
  items.forEach(function(l){ var gap = Math.abs((l.dueAt || 0) - now); if(!best || gap < best.gap) best = {n:l.n, gap:gap}; });
  items.sort(function(a, b){ return (b.dueAt || 0) - (a.dueAt || 0); });
  main.innerHTML = '<h1>' + esc(course.name) + '</h1><p class="lead">' + esc(opt.lead || "回を選ぶ") + '</p>' +
    (items.length ? '<div class="lrows">' + items.map(function(l){
      var info = l.dueAt ? "期限 " + P.md(l.dueAt) + " " + P.hm(l.dueAt) : "";
      var r = (l.total != null ? "出した " + (l.submitted || 0) + "/" + l.total + "人" : "") + (l.todo ? "　未評価 " + l.todo : "");
      return '<button class="lrow' + (best && best.n === l.n ? " best" : "") + '" data-n="' + l.n + '">' +
             '<div><div class="n">' + esc(P.lessonName(l)) + (l.future ? ' <span class="chip">期限前</span>' : '') + '</div>' +
             '<div class="i">' + esc(info) + '</div></div><div class="r num">' + esc(r) + '</div></button>';
    }).join("") + '</div>' : '<div class="card">紙の宿題の回がまだありません（tubestudy で宿題が出ると、ここに出ます）。</div>') +
    '<div class="gap"></div><button class="linkish" data-back="1">ほかのコースを選ぶ</button>';
  main.onclick = function(e){
    if(e.target.closest("[data-back]")){ opt.onBack(); return; }
    var b = e.target.closest("[data-n]");
    if(b) opt.onPick(+b.dataset.n);
  };
};

/* ---------- 刷る ---------- */
P.views.print = {render:function(main, arg){
  arg = arg || {};
  var kind = arg.kind || "label";
  var title = {label:"番号シールを刷る", sep:"区切り紙を刷る", ans:"答案用紙を刷る"}[kind];
  P.pickCourse(main, {title:title, lead:"コースを選ぶ", onCourse:function(c){ printFor(main, kind, c).catch(function(e){ P.failView(main, e); }); }});
}};

async function rosterOf(course){
  var d = await P.api.check(course.key);
  if(!d.rows || !d.rows.length){
    var n = (d.lessons || [])[0];
    if(!n) return [];
  }
  return (d.rows || []).map(function(r){ return {sid:r.sid, label:r.label}; });
}

async function printFor(main, kind, course){
  main.innerHTML = '<h1>' + esc(course.name) + '</h1><p class="lead">読んでいます…</p>';
  var rows = await rosterOf(course);
  var ok = rows.filter(function(r){ return root.PaperCode.canEncode(r.sid); });
  var head = '<h1>' + esc(course.name) + '</h1>';
  if(!rows.length){ main.innerHTML = head + '<div class="card">このコースの生徒が分かりません（紙の宿題の回がまだありません）。</div>'; return; }
  var list = '<div class="card"><div class="row"><h2>刷る生徒</h2><span class="spacer"></span><button class="linkish" data-all="1">全員</button><button class="linkish" data-none="1">だれも</button></div>' +
    '<div class="pick-list">' + ok.map(function(r){
      return '<label class="btn2 on" data-sid="' + esc(r.sid) + '"><input type="checkbox" checked hidden>' + P.who(r) + '</label>';
    }).join("") + '</div></div>';
  var extra = "";
  if(kind === "label") extra = '<p class="lead">A4 の 70×37mm のシール（24枚・余白なし）に、1人1枚。ノート・冊子の<b>表紙</b>に1枚貼る。' +
    '印刷は Mac から、倍率「100%」・余白「なし」で（iPad からだと余白が付いて、シールの枠からずれることがあります）。まず普通の紙に1枚刷って、シール紙に重ねて確かめてください。</p>';
  if(kind === "sep") extra = '<p class="lead">プリントを複合機に通すとき、自分の紙の一番上に重ねる紙。1人1枚。くり返し使えます。</p>';
  if(kind === "ans"){
    extra = '<p class="lead">問題文は刷りません（答えの枠だけ）。名前はこの端末の対応表から刷り、送るときに白で消します。</p>' +
      '<div class="card"><label class="field"><span>題名</span><input id="aTitle" value="小テスト"></label>' +
      '<label class="field"><span>問題の数</span><select id="aCount">' + P.sheets.COUNTS.map(function(n, i){ return '<option value="' + i + '"' + (n === 10 ? " selected" : "") + '>' + n + '問</option>'; }).join("") + '</select></label>' +
      '<label class="field"><span>答えの枠</span><select id="aSize">' + P.sheets.SIZES.map(function(s, i){ return '<option value="' + i + '">' + esc(s.name) + '</option>'; }).join("") + '</select></label>' +
      '<label class="field"><span>tubestudy の回</span><select id="aWhere"><option value="quiz">提出箱を新しく作る（オンラインの子も写真で出せる）</option><option value="none">作らない（あとで回を選んで取り込む）</option></select></label>' +
      '<p class="small muted" id="aInfo"></p></div>';
  }
  main.innerHTML = head + extra + list + '<div class="gap"></div><button class="btn big" id="pgo">刷る</button>';
  var info = function(){
    if(kind !== "ans") return;
    var L = P.sheets.layout(P.sheets.tmplOf(+P.$("#aCount").value, +P.$("#aSize").value));
    P.$("#aInfo").textContent = "1人 " + L.pages + "枚（1枚に " + L.per + "問まで）";
  };
  if(kind === "ans"){ P.$("#aCount").onchange = info; P.$("#aSize").onchange = info; info(); }
  main.onclick = function(e){
    var lab = e.target.closest("label[data-sid]");
    if(lab){ e.preventDefault(); lab.classList.toggle("on"); return; }
    if(e.target.closest("[data-all]")) P.$$("label[data-sid]").forEach(function(l){ l.classList.add("on"); });
    if(e.target.closest("[data-none]")) P.$$("label[data-sid]").forEach(function(l){ l.classList.remove("on"); });
  };
  P.$("#pgo").onclick = async function(){
    var pick = P.$$("label[data-sid].on").map(function(l){ return l.dataset.sid; });
    var chosen = ok.filter(function(r){ return pick.indexOf(r.sid) >= 0; });
    if(!chosen.length){ P.toast("刷る生徒を選んでください", true); return; }
    var html = "";
    if(kind === "label") chosen.forEach(function(r){ html += P.sheets.stickerSheet(r, P.names.of(r.sid)); });
    else if(kind === "sep") chosen.forEach(function(r){ html += P.sheets.separator(r, P.names.of(r.sid)); });
    else {
      var tmpl = P.sheets.tmplOf(+P.$("#aCount").value, +P.$("#aSize").value), L = P.sheets.layout(tmpl);
      var t = P.$("#aTitle").value.trim() || "小テスト";
      if(P.$("#aWhere").value === "quiz"){
        try {
          var end = new Date(); end.setHours(23, 59, 0, 0);
          var got = await P.api.quiz(course.key, t, end.getTime());
          var n = got.assignment && got.assignment.lesson && got.assignment.lesson.n;
          var qs = (await P.store.kv("quizzes", [])) || [];
          qs.push({key:course.key, n:n, title:t, at:Date.now(), tmpl:tmpl});
          await P.store.setKv("quizzes", qs.slice(-60));
          P.toast("tubestudy に提出箱「" + t + "」を作りました");
        } catch(err){ P.fail(err); return; }
      }
      var hd = {course:course.name, title:t, date:P.todayIso().replace(/-/g, "/")};
      chosen.forEach(function(r){ for(var pg = 0; pg < L.pages; pg++) html += P.sheets.answerSheet(r, P.names.of(r.sid), hd, tmpl, pg); });
    }
    P.sheets.printHtml(html);
  };
}

/* ---------- 名前（この端末だけ） ---------- */
P.views.names = {render:function(main){
  P.pickCourse(main, {title:"名前（この端末だけ）", lead:"名前はこの端末の中にだけ置き、画面と、ここで刷る紙にだけ出します。tubestudy にも中継にも送りません。コースを選ぶ", onCourse:function(c){ namesFor(main, c).catch(function(e){ P.failView(main, e); }); }});
}};
async function namesFor(main, course){
  main.innerHTML = '<h1>' + esc(course.name) + '</h1><p class="lead">読んでいます…</p>';
  var rows = await rosterOf(course);
  main.innerHTML = '<h1>' + esc(course.name) + '</h1>' +
    '<p class="lead">名前は sid（生徒ごとに変わらない印）に結びます。クラス替えで番号が変わっても、名前はそのまま付いていきます。</p>' +
    '<div class="card"><table class="tbl">' + rows.map(function(r){
      return '<tr><td>' + esc(r.label) + '</td><td><input data-sid="' + esc(r.sid) + '" value="' + esc(P.names.of(r.sid)) + '" placeholder="名前" autocomplete="off"></td></tr>';
    }).join("") + '</table></div>' +
    '<div class="card"><h2>まとめて貼る</h2><p class="small muted">1行に「小4β-07,山田 花子」の形（番号は今の番号）。対応表の書き出しから写せます。</p>' +
    '<label class="field"><textarea id="nPaste" placeholder="小4β-07,山田 花子"></textarea></label>' +
    '<div class="row" style="margin-top:10px"><button class="btn2" id="nApply">貼った名前を入れる</button><span class="spacer"></span>' +
    '<button class="btn2" id="nExport">この端末の名前をファイルに書き出す</button><button class="btn2" id="nImport">ファイルから読む</button>' +
    '<input type="file" id="nFile" accept=".json" hidden></div></div>' +
    '<div class="card"><button class="btn2 danger" id="nClear">この端末の名前を全部消す</button></div>';
  P.$$("input[data-sid]").forEach(function(inp){
    inp.onchange = function(){ var v = inp.value.trim(); if(v) P.names.map[inp.dataset.sid] = v; else delete P.names.map[inp.dataset.sid]; P.names.save(); P.toast("入れました（この端末だけ）"); };
  });
  P.$("#nApply").onclick = function(){
    var by = {}, n = 0, miss = [];
    rows.forEach(function(r){ by[r.label.replace(/\s+/g, "")] = r.sid; });
    P.$("#nPaste").value.split(/\r?\n/).forEach(function(line){
      var c = line.split(/[,\t]/);
      if(c.length < 2) return;
      var sid = by[c[0].trim().replace(/\s+/g, "")];
      if(sid && c[1].trim()){ P.names.map[sid] = c[1].trim(); n++; } else if(c[0].trim()) miss.push(c[0].trim());
    });
    P.names.save();
    P.toast(n + "人の名前を入れました" + (miss.length ? "（見つからない番号 " + miss.length + "）" : ""), !!miss.length);
    namesFor(main, course);
  };
  P.$("#nExport").onclick = function(){
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify({kind:"paper-names", savedAt:new Date().toISOString(), names:P.names.map}, null, 1)], {type:"application/json"}));
    a.download = "名前-" + P.todayIso() + ".json";
    a.click();
  };
  P.$("#nImport").onclick = function(){ P.$("#nFile").click(); };
  P.$("#nFile").onchange = function(e){
    var f = e.target.files[0];
    if(!f) return;
    var fr = new FileReader();
    fr.onload = function(){
      try {
        var d = JSON.parse(fr.result);
        if(!d || d.kind !== "paper-names" || typeof d.names !== "object") throw new Error("形がちがいます");
        Object.keys(d.names).forEach(function(k){ P.names.map[k] = String(d.names[k]); });
        P.names.save(); P.toast("読みました"); namesFor(main, course);
      } catch(err){ P.toast("読めませんでした: " + err.message, true); }
    };
    fr.readAsText(f);
  };
  P.$("#nClear").onclick = function(){
    if(!confirm("この端末の名前を全部消します（tubestudy には何も起きません）。よいですか。")) return;
    P.names.map = {}; P.names.save(); namesFor(main, course);
  };
}

/* ---------- 控えから戻す（この端末に控えた、置き換える前の写真・前の評価と答案） ---------- */
P.views.history = {render:async function(main){
  var all = (await P.store.all("history")).sort(function(a, b){ return b.at - a.at; });
  var when = function(ms){ var d = new Date(ms); return P.md(ms) + " " + P.hm(ms); };
  main.innerHTML = '<h1>控えから戻す</h1>' +
    '<p class="lead">置き換える前の写真と、付け直す前の評価・返した答案を、この端末に30日控えています。押すと tubestudy に戻します。</p>' +
    (all.length ? '<div class="lrows">' + all.map(function(h){
      var what = h.kind === "scan"
        ? (h.origin === "teacher" ? "前に取り込んだ紙 " : "生徒が出した写真 ") + h.files.length + "枚"
        : "評価 " + (h.v ? h.v : "なし") + (h.returned && h.returned.length ? "・返した答案 " + h.returned.length + "枚" : "");
      return '<div class="lrow"><div><div class="n">' + P.who({sid:h.sid, label:h.label || h.sid}) + '</div>' +
             '<div class="i">' + esc((h.course || h.key || "") + "　" + (h.lesson || ("第" + h.n + "回"))) + '　' + esc(when(h.at)) + '</div>' +
             '<div class="i">' + esc(what) + '</div></div>' +
             '<div class="r row"><button class="btn2" data-see="' + esc(h.id) + '">見る</button>' +
             '<button class="btn2" data-back="' + esc(h.id) + '">tubestudy に戻す</button></div></div>';
    }).join("") + '</div>' : '<div class="card">控えはありません。</div>');
  main.onclick = async function(e){
    var b = e.target.closest("[data-see],[data-back]");
    if(!b) return;
    var h = all.filter(function(x){ return x.id === (b.dataset.see || b.dataset.back); })[0];
    if(!h) return;
    var files = h.kind === "scan" ? h.files : (h.returned || []);
    if(b.dataset.see){
      P.sheet("控え", files.length ? files.map(function(f){ return '<img alt="" style="width:100%;border-radius:10px;margin-bottom:10px" src="' + URL.createObjectURL(f.blob) + '">'; }).join("")
                                  : '<p>画像の控えはありません（評価だけ）。</p>', {wide:true});
      return;
    }
    var msg = h.kind === "scan"
      ? "この写真 " + files.length + "枚を、いまの取り込みと置き換えて tubestudy に戻します（先生の取り込みとして入ります）。よいですか。"
      : "評価を「" + (h.v || "なし") + "」に" + (files.length ? "、返した答案を控えの " + files.length + "枚に" : "") + "戻します。よいですか。";
    if(!confirm(msg)) return;
    try {
      var up = [];
      for(var i = 0; i < files.length; i++) up.push({type:files[i].blob.type || "image/jpeg", b64:await P.b64(files[i].blob)});
      if(h.kind === "scan") await P.api.scan(h.aid, h.sid, up);
      else {
        if(up.length) await P.api.giveBack(h.aid, h.sid, up, h.note);
        await P.api.rate(h.key, h.n, h.sid, h.v == null ? null : h.v, h.note);
      }
      await P.store.del("history", h.id);
      P.toast("tubestudy に戻しました");
      P.show("history");
    } catch(err){ P.fail(err); }
  };
}};

/* ---------- 使い方 ---------- */
P.views.help = {render:function(main){
  main.innerHTML = '<h1>使い方</h1><div class="card helpbox">' +
    '<h2>はじめに1回</h2><ol>' +
      '<li>「番号シールを刷る」で、生徒ごとにシールを刷る。ノート・冊子の<b>表紙</b>に1枚貼る（新しいノートにしたら、また1枚）。</li>' +
      '<li>名前で見たいときは「名前（この端末だけ）」に入れる。名前はこの端末から出ません。</li></ol>' +
    '<h2>授業のたびに</h2><ol>' +
      '<li>集めたノートを、iPad の「ファイル」か「メモ」の<b>書類をスキャン</b>で、表紙→宿題のページ→次の子の表紙…と続けて撮る（黒い下敷きの上だと四隅がよく取れます）。保存先は「この iPad 内」に。</li>' +
      '<li>「取り込む」→ コース → 回 → 撮った PDF を選ぶ。</li>' +
      '<li>生徒ごとに分かれたページを見て、「〇人ぶんを送る」。ノートはその場で返せます。</li>' +
      '<li>送り終えたら、撮った元の PDF を消す。</li></ol>' +
    '<h2>採点</h2><ol>' +
      '<li>「採点する」→ 回を選ぶ。対面の子もオンラインの子も同じ列に並びます。</li>' +
      '<li>ペン（iPad）で赤を入れる。◯・✕・△・◎ は選んでから答案を軽く叩く。数は自動で数えます。</li>' +
      '<li>1〜5 を押すと、評価とひとことが付き、赤を入れた答案が生徒と保護者の「先生から」に返り、次の子に進みます。</li></ol>' +
    '<h2>プリント・小テスト</h2><ol>' +
      '<li>区切り紙（1人1枚）を、自分のプリントの一番上に重ねて出してもらう。束のまま複合機でカラーかグレーの PDF にする。</li>' +
      '<li>「答案用紙を刷る」で刷った紙は、順番がばらばらでもそのまま入れられ、「問題ごと」に全員の答えを並べて採点できます。</li></ol>' +
    '<h2>家で撮って出すとき（生徒・保護者）</h2><ol>' +
      '<li>iPhone なら「メモ」→ カメラ → 書類をスキャン で撮ると、まっすぐで読みやすくなります。</li>' +
      '<li>tubestudy の宿題の画面から、いつもどおり写真（か PDF）で出す。先生の採点の列に、教室で集めた紙と同じように並びます。</li></ol>' +
    '<h2>まちがえたら</h2><ol>' +
      '<li>送る前なら、ページを押して「だれの紙？」で直す・外す。</li>' +
      '<li>評価を付け直すときは、その子に戻って別の数字を押す。返した答案は差し替わり、前のものはこの端末に控えが残ります。</li></ol>' +
    '</div>';
}};

/* ---------- 起動 ---------- */
document.addEventListener("click", function(e){
  var g = e.target.closest("[data-go]");
  if(!g || g.closest("#main")) {
    if(g && g.closest("#main") && ["intake", "grade", "names", "help", "home", "history"].indexOf(g.dataset.go) >= 0) P.show(g.dataset.go);
    return;
  }
  P.show(g.dataset.go);
});
P.$("#logout").onclick = async function(){
  await P.api.logout();
  P.state.profile = null;
  P.show("login");
};

(async function boot(){
  await P.store.open();
  await P.names.load();
  try { await P.intake.cleanup(); } catch(e){}
  if(P.api.token){
    try {
      var d = await P.api.me();
      if(d.profile && d.profile.role === "teacher"){ P.state.profile = d.profile; afterLogin(); }
      else P.api.setToken(null);
    } catch(e){ P.api.setToken(null); }
  }
  P.show(P.state.profile ? "home" : "login");
})();
})(window);
