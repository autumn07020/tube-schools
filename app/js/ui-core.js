/* ============================================================
   画面の土台 ―― 共通部品・画面の振り分け・入口
   ------------------------------------------------------------
   ファイルの分け方

     ui-core.js     ここ。共通部品、画面の振り分け、ログイン
     ui-student.js  生徒の画面（きょう・学習・きろく・せってい）
     ui-teacher.js  講師の画面（名簿・宿題・進度・管理）

   学習の判断は srs.js、保存は store.js、進度は config.js。
   このファイルはそれらを呼ぶだけで、自分では決めない。
   ============================================================ */
(function(global){
"use strict";

/* ------------------------------------------------------------
   小道具
   ------------------------------------------------------------ */
var $ = function(s){ return document.querySelector(s); };
var $$ = function(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); };

function esc(s){
  return String(s == null ? '' : s).replace(/[&<>"]/g, function(m){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m];
  });
}
/* ------------------------------------------------------------
   見た目の作り直し（2026-10-08）：タブとメニューの印（1本線の SVG）、小さな札（メニュー）、教科の色、数字の増え
   ------------------------------------------------------------ */
var SVG_O = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">';
/* 背景の色玉の大きさは CSS（paper.css 段2）が 100lvh で決める。前は JS が innerHeight から --tile を決め直していたが、
   iPhone の Safari はアドレス欄が縮むたびに innerHeight が変わり、背景が描き直されて一瞬白く抜けた（10-12）。 */

var TAB_ICONS = {
  today:    SVG_O+'<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
  homework: SVG_O+'<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/></svg>',
  daily:    SVG_O+'<path d="M21.801 10A10 10 0 1 1 17 3.335"/><path d="m9 11 3 3L22 4"/></svg>',
  record:   SVG_O+'<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  hw:       SVG_O+'<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/></svg>',
  roster:   SVG_O+'<path d="M16 7h6v6"/><path d="m22 7-8.5 8.5-5-5L2 17"/></svg>',
  progress: SVG_O+'<path d="M3 20h5v-5h5v-5h5V5h3"/></svg>',
  /* 過去問（中3・小6）：紙の束 */
  kakomon:  SVG_O+'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h8"/></svg>'
};
var MENU_ICONS = {
  apps:     SVG_O+'<path d="M3 20h5v-5h5v-5h5V5h3"/></svg>',
  people:   SVG_O+'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
  mats:     TAB_ICONS.homework,
  admin:    SVG_O+'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/></svg>',
  parent:   SVG_O+'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
  settings: SVG_O+'<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/></svg>',
  report:   SVG_O+'<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>',
  out:      SVG_O+'<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/></svg>'
};
/* 教科の印（1本線の SVG。見本 T01 の SUBJ）と、札の見出しに添える小さな印 */
var SUBJ_PATH = {
  english:  'M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20M2 12h20',
  math:     'M5 7c3 0 4.5 2.5 7 5s4 5 7 5M19 7c-3 0-4.5 2.5-7 5s-4 5-7 5',
  science:  'M14 2v6a2 2 0 0 0 .245.96l5.51 10.08A2 2 0 0 1 18 22H6a2 2 0 0 1-1.755-2.96l5.51-10.08A2 2 0 0 0 10 8V2M6.453 15h11.094M8.5 2h7',
  social:   'M10 18v-7M11.12 2.198a2 2 0 0 1 1.76.006l7.866 3.847c.476.233.31.949-.22.949H3.474c-.53 0-.695-.716-.22-.949zM14 18v-7M18 18v-7M3 22h18M6 18v-7',
  japanese: 'M12 20h9M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.855.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z'
};
function subjIcon(id, size, sw){
  var d = SUBJ_PATH[id]; if(!d) return '';
  return '<svg class="sj-ico" viewBox="0 0 24 24" width="'+(size||18)+'" height="'+(size||18)+'" fill="none" stroke="currentColor" stroke-width="'+(sw||2.2)+'" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="'+d+'"/></svg>';
}
var ICO_PATH = {
  calendar:'<path d="M8 2v4M16 2v4M3 10h18"/><rect x="3" y="4" width="18" height="18" rx="2"/>',
  target:'<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
  trend:'<path d="M16 7h6v6"/><path d="m22 7-8.5 8.5-5-5L2 17"/>',
  bars:'<path d="M3 3v18h18"/><path d="M8 17V9M13 17V5M18 17v-3"/>',
  check:'<path d="M21.801 10A10 10 0 1 1 17 3.335"/><path d="m9 11 3 3L22 4"/>',
  users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  edit:'<path d="M12 20h9"/><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.855.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z"/>',
  camera:'<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
  app:'<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/>',
  chev:'<path d="m9 18 6-6-6-6"/>', chevl:'<path d="m15 18-6-6 6-6"/>',
  flag:'<path d="M4 22V4a1 1 0 0 1 1-1h11.5a.5.5 0 0 1 .4.8L14 8l2.9 4.2a.5.5 0 0 1-.4.8H5"/>',
  bell:'<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  msg:'<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  photo:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
  x:'<path d="M18 6 6 18M6 6l12 12"/>',
  star:'<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/>',
  clock:'<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  book:'<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
  file:'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
  pen:'<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/>'
};
function ico(name, size, sw){
  return '<svg viewBox="0 0 24 24" width="'+(size||18)+'" height="'+(size||18)+'" fill="none" stroke="currentColor" stroke-width="'+(sw||2.2)+'" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(ICO_PATH[name]||'')+'</svg>';
}
var DOTS_ICON = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/><circle cx="5" cy="12" r="1.7"/></svg>';
var BACK_ICON = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6"/></svg>';
/* 小さな札（メニュー）を閉じる */
/* ページの見出し（34/700 の題と、日付の行）。sub が無ければ今日の日付だけ。right に字を渡すと右端に置く。 */
function pageHead(title, sub, right){
  var d = new Date(), WD = ['日','月','火','水','木','金','土'];
  return '<div class="h-head t-full"><div class="h-headrow"><h1>'+esc(title)+'</h1>'+
    (right ? '<span class="h-date">'+right+'</span>' : '')+'</div>'+
    (sub !== false ? '<p class="h-date"><span class="num">'+(d.getMonth()+1)+'/'+d.getDate()+'</span>（'+WD[d.getDay()]+'）'+(sub ? '　'+esc(sub) : '')+'</p>' : '')+'</div>';
}
function closePop(){ var w = document.getElementById('popwrap'); if(w) w.remove(); }
/* 教科のページ：色玉を5つともその教科の色にする。描き直しのたびに外し、教科の画面が自分で付ける。 */
function setSubject(id){
  if(id) document.documentElement.setAttribute('data-subject', id);
  else document.documentElement.removeAttribute('data-subject');
}
/* 大きな数字（.cu）は 0 から 600ms で増える。画面が変わったときだけ。 */
function countUp(root){
  /* 桁の数を data-len に置く（「120 問」「10/10」が枠からはみ出ていた。paper.css が桁で字を小さくする。10-12） */
  [].forEach.call(root.querySelectorAll('.cu'), function(el){
    var s = (el.textContent || '').trim();
    if(/^\d+(\.\d+)?$/.test(s)) el.setAttribute('data-len', String(s.split('.')[0].length));
  });
  if(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  [].forEach.call(root.querySelectorAll('.cu'), function(el){
    var txt = (el.textContent || '').trim();
    if(!/^\d+(\.\d+)?$/.test(txt)) return;
    var n = parseFloat(txt), dec = (txt.split('.')[1] || '').length, t0 = performance.now();
    if(!(n > 0)) return;
    el.textContent = (0).toFixed(dec);
    (function step(now){
      var pr = Math.min(1, (now - t0) / 600), e = 1 - Math.pow(1 - pr, 3);
      el.textContent = (n * e).toFixed(dec);
      if(pr < 1) requestAnimationFrame(step);
    })(t0);
  });
}

function toast(m){
  var t = $('#toast');
  t.textContent = m; t.classList.add('on');
  clearTimeout(t._t);
  t._t = setTimeout(function(){ t.classList.remove('on'); }, 2200);
}
function shuffle(a){
  a = a.slice();
  for(var i=a.length-1; i>0; i--){ var j=(Math.random()*(i+1))|0; var t=a[i]; a[i]=a[j]; a[j]=t; }
  return a;
}
/* 授業の回の名前（教材の呼び名。無ければ「第n回」）。決まりは viz.js の1か所だけに置き、ここは渡すだけ。 */
function unitName(x){ return TubeViz.unitName(x); }
function unitTick(x){ return TubeViz.unitTick(x); }
function unitText(x){ return TubeViz.unitText(x); }

function fmtDate(ts){
  var d = new Date(ts);
  return (d.getMonth()+1) + '/' + d.getDate();
}
function dateInput(ts){
  var d = new Date(ts);
  return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+
         String(d.getDate()).padStart(2,'0');
}

/* ------------------------------------------------------------
   いまの状態
   ------------------------------------------------------------ */
var S = {
  view: 'login',        // login | gate | today（ホーム）| homework | daily | record | settings
                        // roster | hw | progress | admin
  me: null,             // 生徒 {stu, p, grade, subjects:[{subject, plan, order}]}
  teacher: null,        // 講師 {profile, classes:[]}
  session: null,        // 学習中のセッション
  srv: null,            // サーバ（無ければ null）
  demo: false,          // デモ起動か（ログイン画面にボタンを出すかの判断）
  gate: {step:'code', klass:null}
};

/* 生徒が入れる画面と、講師が入れる画面 */
var STUDENT_VIEWS = {today:1, homework:1, daily:1, kakomon:1, record:1, settings:1, parent:1, place:1};
/* どちらの役でも入れる画面（うまく動かないときの報告）。入っていなければ入口へ。 */
var COMMON_VIEWS = {report:1};
/* 人が最後に押した（触れた・Enter を押した）時刻。これから 0.7 秒のうちの描き直しは「人が変えた画面」なので、
   前の画面の写しを薄れさせて次を浮かばせる（データが届いただけの描き直しには動きを付けない ―― ちらつくため）。 */
var lastPointerAt = 0;
var TEACHER_VIEWS = {roster:1, hw:1, check:1, progress:1, mats:1, people:1, admin:1, apps:1, msgs:1};

/* 画面を移る。dir は移り方 ―― 'fade'（タブ。ふわっと）、'push'（札から先へ。右から）、
   'pop'（もどる。左から）。同じ画面の描き直しでは動かない（render の navDir）。 */
/* 教科の色（薄いグラデーション）の札。講師の今日やること・時間割・成績のコースの札、生徒の宿題の教科の札に付ける。
   国語＝赤とピンクの間・数学（算数）＝青・理科＝緑・社会＝黄・英語＝緑と青の間（app.css の .sj-*）。
   知らない教科には付けない（地の白のまま）。 */
var SJ_TINT = {japanese:1, math:1, science:1, social:1, english:1};
function sjClass(id){ return SJ_TINT[id] ? ' sjt sj-'+id : ''; }

function go(v, dir){
  if(v === 'gate'){ S.gate = {step:'code', klass:null}; }
  /* 動きは**フェードだけ**（本人：上下・左右に動くのは気持ち悪い）。dir は受けるが使わない。 */
  if(S.view !== v) S.navDir = 'fade';
  S.view = v;
  window.scrollTo(0, 0);
  render();
}
/* 同じ画面の中で「先へ／もどる」をするとき（先生からの教科の中など）に、次の描き直しへ動きを付ける。 */
function nav(dir){ S.navDir = 'fade'; }

/* ------------------------------------------------------------
   描画の入口
   ------------------------------------------------------------ */
/* いま見ている画面の名前。これが変わらない間は、描き直しても
   同じ場所を見ていたいはず。 */
var lastView = null;

/* 幕（All aboard!）の輪がほどける 0.7秒だけ、描き直しを待たせる。
   輪のほどけは SVG の線を毎コマ描き直す動き（GPU に任せられない）。そこへホームの描画が重なると、
   Mac でも iPhone でも必ずカクつく ―― 前は幕の途中（1.7秒）でホームを描いていたので、毎回そうなっていた。
   いまはホームを幕が不透明なうちに先に描き、ほどける間は何も描かず、明けるとき（GPU の不透明度）に描き直す。 */
var holdRender = false, renderPending = false;
function holdRendering(on){
  holdRender = !!on;
  if(!on && renderPending){ renderPending = false; render(); }
}

function render(){
  if(holdRender){ renderPending = true; return; }
  /* **描き直しで、見ている場所を失わない。**

     画面は innerHTML をまるごと入れ替えて作る。そのため学年の札を
     押しただけで巻き戸が先頭に戻り、押すたびにページの上へ飛んでいた。
     同じ画面を描き直すときは、位置を持って帰る。 */
  var keepY = (lastView === S.view && !S.session) ? window.scrollY : null;

  /* 入っていない人が中の画面を描こうとしたら入口へ戻す。
     素通しにすると me.stu を読んだところで落ちる。 */
  if(STUDENT_VIEWS[S.view] && !S.me)      S.view = S.srv ? 'login' : 'gate';
  if(TEACHER_VIEWS[S.view] && !S.teacher) S.view = S.srv ? 'login' : 'gate';
  if(COMMON_VIEWS[S.view] && !S.me && !S.teacher) S.view = S.srv ? 'login' : 'gate';
  /* 毎日テストを使っていない生徒が、毎日テストの画面に来たら（前回の続き・古い札）ホームへ。 */
  if(S.view === 'daily' && S.me && !S.session && !TubeStudent.dailyOn()) S.view = 'today';
  if(S.view === 'kakomon' && S.me && !S.session && !TubeStudent.kakomonOn()) S.view = 'today';

  document.body.className = 'screen-' + (S.session ? 'session' : S.view);
  if(S.session){
    /* **出題中は土台（.bento）を外す。**
       ここで外さずに返していたため、格子の1マス（56px）の中に
       問題文が入り、1文字ずつ縦に折り返していた。
       土台を外す行はこの下にあり、そこまで届いていなかった。 */
    $('#main').className = '';
    lastView = S.view;
    return TubeStudent.renderSession();
  }

  /* **同じ紙を描き直すとき、出てくる動きを繰り返さない。**
     画面は丸ごと入れ替えるので、開いている紙（.sheet）も作り直され、
     紙の中の札を押すたびに、ふわっと出てくる動きが毎回走っていた（ちらつく）。
     名札（data-sk）が描き直す前と同じ紙は、動きを止めて置く。 */
  var openSheets = {};
  [].forEach.call(document.querySelectorAll('#main .sheet[data-sk]'), function(x){
    openSheets[x.getAttribute('data-sk')] = 1; });

  var m = $('#main');
  /* **前の画面の写しを重ねて薄れさせる**（iOS・macOS の切り替え。本人：ページ遷移に動きが無い）。
     次の画面は nav-* で浮かび上がり、前の画面は写し（ghost）が薄れながら少し縮む。
     紙（sheet）は、消えるときも縮みながら薄れる（sheetClones → sheetExit）。 */
  var inCheck = (lastView === 'check' && S.view === 'check');           /* 宿題チェックの中は今のまま */
  var byUser = (Date.now() - lastPointerAt) < 700;
  var motion = !S.session && !inCheck && !!m.childNodes.length && (!!S.navDir || byUser);
  var ghost = motion ? ghostOf(m) : null;
  var oldSheetClones = sheetClones(m);
  renderHeader();
  /* 本体はいつも同じ土台（.bento）。札の大きさは各画面が
     t-full / t-wide / t-one で宣言する。列の数は幅から自動で決まるので、
     画面ごとに列番号を書かない ―― そこが壊れの元だった。
     出題中と入口だけは1本の柱にするので、土台を外す。 */
  var flat = (S.session || S.view === 'login' || S.view === 'gate' || S.view === 'newpw' || S.view === 'claim' || S.view === 'cardask' || S.view === 'join' || S.view === 'place');
  m.className = flat ? '' : 'bento';
  closePop(); setSubject(null);
  if(S.view === 'login')          viewLogin(m);
  else if(S.view === 'gate')      viewGate(m);
  else if(S.view === 'today')     TubeStudent.viewToday(m);
  /* 宿題のタブ。講師の宿題（'hw'）とは別の名前にしてある ―― 同じ名前だと、
     入っていない側の画面へ振り分けられて落ちる。 */
  else if(S.view === 'homework')  TubeStudent.viewHomework(m);
  else if(S.view === 'daily')     TubeStudent.viewDaily(m);
  else if(S.view === 'kakomon')   TubeStudent.viewKakomon(m);
  /* 広い画面では、先生から（前のきろく）はホームの中にある。
     直リンクや前回の続きで 'record' に来たら、そちらへ送る。 */
  else if(S.view === 'record')    TubeStudent.viewRecord(m);
  else if(S.view === 'settings')  TubeStudent.viewSettings(m);
  else if(S.view === 'parent')    TubeStudent.viewParent(m);
  else if(S.view === 'roster')    TubeTeacher.viewRoster(m);
  else if(S.view === 'hw')        TubeTeacher.viewHomework(m);
  else if(S.view === 'msgs')      TubeTeacher.viewMessages(m);
  /* 宿題チェックのページ。宿題タブの中の1枚なので、タブは「宿題」のまま光らせる。 */
  else if(S.view === 'check')     TubeTeacher.viewCheck(m);
  else if(S.view === 'progress')  TubeTeacher.viewProgress(m);
  else if(S.view === 'mats')      TubeTeacher.viewMaterials(m);
  else if(S.view === 'people')    TubeTeacher.viewRosterAdmin(m);
  else if(S.view === 'admin')     TubeTeacher.viewAdmin(m);
  else if(S.view === 'apps')      TubeTeacher.viewApps(m);
  else if(S.view === 'report')    viewReport(m);
  else if(S.view === 'newpw')     viewNewPw(m);
  else if(S.view === 'claim')     viewClaim(m);
  else if(S.view === 'cardask')   viewCardAsk(m);
  else if(S.view === 'join')      TubeJoin.view(m);
  else if(S.view === 'place')     TubeJoin.viewPlace(m);
  renderNav();
  if(lastView !== S.view) countUp(m);
  [].forEach.call(m.querySelectorAll('.sheet[data-sk]'), function(x){
    if(!openSheets[x.getAttribute('data-sk')]) return;
    x.style.animation = 'none';
    var sh = x.previousElementSibling;
    if(sh && sh.classList.contains('shade')) sh.style.animation = 'none';
  });
  /* 画面が変わったときだけ、中身をふわっと（または右／左から）出す。
     動くのは #main の直下の札ぜんぶ（紙と暗がりは除く）。#main そのものを動かすと、
     動いている 0.3 秒のあいだ position:fixed の紙が #main を基準に置かれてずれる。 */
  if(motion){
    m.classList.remove('fade-in');
    void m.offsetWidth;                       /* 同じ動きを続けて出すために、いちど切る */
    m.classList.add('fade-in');
  }
  S.navDir = null;
  sheetExit(oldSheetClones, m);

  /* 位置を戻す。**中身を置いたあとの高さで**戻さないと、
     まだ短い画面に対して長い位置を指すことになり、上に落ちる。 */
  lastView = S.view;
  if(keepY !== null){
    /* **押した札を、押したときと同じ高さに置きなおす。**

       ただ scrollY を戻すだけでは足りない。学年を変えると上の
       予定の行数が変わり、札そのものが数十px動く ―― 巻き位置は
       同じでも、目には「ガクッ」と見える。
       目印にした札が画面のどこに居たかを覚えておき、そこへ戻す。 */
    var y = keepY;
    if(anchor && anchor.sel){
      var el = document.querySelector(anchor.sel);
      if(el) y = Math.max(0, el.getBoundingClientRect().top + window.scrollY - anchor.top);
    }
    window.scrollTo(0, y);
    requestAnimationFrame(function(){ window.scrollTo(0, y); });
  }
  anchor = null;
}

/* 描き直しのあいだ、位置の目印にする札。
   押した本人が動かないように、押す側から渡してもらう。 */
/* 前の画面の写し。#main を丸ごと写し、同じ位置に固定して重ねる。動きが終われば消す。
   写しは押せない（pointer-events:none）。紙と暗がりは写しから外す（紙は別に消える）。 */
function ghostOf(m){
  try{
    var r = m.getBoundingClientRect();
    var g = m.cloneNode(true);
    g.removeAttribute('id');
    g.className = m.className.replace('fade-in', '') + ' mainghost';    /* .ghost は白いボタンの名前なので使わない */
    [].forEach.call(g.querySelectorAll('.shade, .sheet, [id]'), function(x){
      if(x.classList.contains('shade') || x.classList.contains('sheet')) x.remove(); else x.removeAttribute('id');
    });
    g.style.cssText = 'position:fixed;left:'+r.left+'px;top:'+r.top+'px;width:'+r.width+'px;height:'+
      Math.max(0, Math.min(r.height, window.innerHeight - r.top))+'px;overflow:hidden;pointer-events:none;z-index:60;margin:0;box-sizing:border-box';
    /* 写しは1枚だけ。押した直後にデータが届いて続けて描き直すと、写しが重なって濃くなる（実際そうなった） */
    [].forEach.call(m.parentNode.querySelectorAll('.mainghost'), function(x){ x.remove(); });
    m.parentNode.appendChild(g);
    setTimeout(function(){ if(g.parentNode) g.remove(); }, 800);
    return g;
  }catch(e){ return null; }
}
/* 開いている紙の写し（消える動きのため）。名札（data-sk）で、次の画面に同じ紙が無ければ消える動きを出す。 */
function sheetClones(m){
  return [].map.call(m.querySelectorAll('.sheet[data-sk]'), function(x){
    var sh = x.previousElementSibling;
    return {sk:x.getAttribute('data-sk'), sheet:x.cloneNode(true),
            shade:(sh && sh.classList.contains('shade')) ? sh.cloneNode(true) : null};
  });
}
function sheetExit(clones, m){
  if(!clones || !clones.length) return;
  var still = {};
  [].forEach.call(m.querySelectorAll('.sheet[data-sk]'), function(x){ still[x.getAttribute('data-sk')] = 1; });
  clones.forEach(function(c){
    if(still[c.sk]) return;
    var box = document.createElement('div');
    box.className = 'leaving';
    /* 描き直しで止めていた動き（style.animation='none'）を写しから外す ―― 残すと消える動きが効かず、
       暗がりが 0.4 秒そのまま残って「一瞬暗くなる」ように見えた。 */
    c.sheet.style.animation = ''; if(c.shade) c.shade.style.animation = '';
    [].forEach.call(c.sheet.querySelectorAll('[id]'), function(x){ x.removeAttribute('id'); });
    if(c.shade) box.appendChild(c.shade);
    box.appendChild(c.sheet);
    document.body.appendChild(box);
    setTimeout(function(){ if(box.parentNode) box.remove(); }, 450);
  });
}

var anchor = null;
function keepInPlace(el){
  if(!el) return;
  var sel = el.dataset.hg ? '[data-hg="'+el.dataset.hg+'"]'
          : el.dataset.hs ? '[data-hs="'+el.dataset.hs+'"]'
          : el.dataset.hgrp ? '[data-hgrp="'+el.dataset.hgrp+'"]'
          : null;
  if(sel) anchor = {sel:sel, top:el.getBoundingClientRect().top};
}

/* 校舎の呼び名を英語で1語にする。「ロンドン校」→「for London」。
   校舎IDから引く ―― 名前を英訳しようとすると校舎が増えたときに崩れる。 */
var SCHOOL_EN = {london:'London', tokyo:'Tokyo', singapore:'Singapore',
                 newyork:'New York', shanghai:'Shanghai', taipei:'Taipei',
                 hongkong:'Hong Kong', bangkok:'Bangkok', sydney:'Sydney',
                 losangeles:'Los Angeles', frankfurt:'Frankfurt'};
function schoolTag(){
  var sc = TubeConfig.school();
  var en = SCHOOL_EN[sc.id];
  return 'for ' + (en || (sc.name || '').replace(/校$/, ''));
}

function renderHeader(){
  var right = '';
  if(S.teacher){
    /* 担当クラスの一覧はここに出さない。7つ並ぶと銘より長くなり、
       ヘッダの主役が入れ替わる。担当は下の時間割にぜんぶ出ている。 */
    right = '<div class="who">'+esc(S.teacher.label || '講師')+'</div>';
  }else if(S.me){
    right = '<div class="who">'+esc(S.me.stu.label)+'</div>';
  }
  /* 右上はメニュー1つ。ログアウトはその中に置く。
     以前は講師の「管理」タブの中だけにあり、タブを組み直したときに
     一緒に消えて、入ったら二度と出られない状態になっていた。
     出口は必ずヘッダから2手で届く場所に置くこと。 */
  $('#chrome').innerHTML =
    /* 銘は枠いっぱいまで大きく取る。校舎は「for London」として
       銘の右に添える ―― 下に置くとヘッダが2段になって背が伸びる。 */
    /* 印は銘の左に置く。**すでにある icon.svg をそのまま使う** ――
       ホーム画面に並ぶ印と、画面の中の印が違うと、別のアプリに見える。 */
    '<header><div class="brand">'+
      '<img class="mark" src="icon.svg" alt="">'+
      '<b>tube</b><i>study</i>'+
      (TubeConfig.school().id
        ? '<span class="forwhere">'+esc(schoolTag())+'</span>' : '')+
    '</div>'+right+
    /* 右上はメニュー1つにまとめる。
       明暗の切り替えは凍結した ―― 2つ保つと色を足すたびに検査が倍になり、
       実際にコントラストの取り違え（1.07:1）は暗いほうで起きた。 */
    ((S.me || S.teacher)
      ? '<button class="signout hit" id="hMenu" aria-label="メニュー">'+DOTS_ICON+'</button>'
      : '')+
    '</header>';
  var mn = $('#hMenu');
  if(mn) mn.onclick = openMenu;
}

/* ------------------------------------------------------------
   あたらしい合言葉 ―― 引き換えの言葉（先生から届いたリンク）で入ったあと、1回だけ見せる

   この合言葉は、いまこの端末が作った。サーバにあるのは、確かめるための値だけで、
   先生も読めない。ここで書きとめてもらう（ほかの端末から入るときに使う）。
   ------------------------------------------------------------ */
/* 先生から届いたリンクで来た。**押してもらってから**引き換える（開いただけでは、1回きりを使わない）。
   まだ学年が分からない（引き換えの印は、役割もクラスも持たない）ので、小4にも保護者にも読める書き方にする。 */
function viewClaim(m){
  var c = S.claim;
  if(!c){ return go('login'); }
  m.innerHTML =
    '<div class="lg"><div class="lg-body">'+
      '<div class="card lg-card np-card">'+
        '<h1>ここで はじめる</h1>'+
        '<p class="tiny">ボタンを おすと、この スマホ・パソコンの中で、あなたの あいことばを 作ります。'+
          '<b>できるのは 1回だけ</b>です。じぶんが つかう スマホ・パソコンで おしてください。</p>'+
        '<div class="np-row"><span class="lbl">ID</span><span class="np-v num">'+esc(c.id)+'</span></div>'+
        '<button class="btn" id="clGo">はじめる</button>'+
        '<button class="btn ghost" id="clNo">いまは やめておく</button>'+
        '<div id="clMsg" class="loginmsg" role="alert"></div>'+
      '</div>'+
    '</div></div>';
  var busy = false;
  $('#clNo').onclick = function(){ S.claim = null; go('login'); };
  $('#clGo').onclick = async function(){
    if(busy) return;
    busy = true; $('#clGo').textContent = 'あいことばを 作っています…';
    var r = await S.srv.claim(c.id, c.token, c.words);
    busy = false;
    if(!r.ok){
      var el = $('#clMsg'); $('#clGo').textContent = 'はじめる';
      if(el){ el.textContent = r.error + '　先生に「もう一度 送ってください」と つたえてください。'; el.classList.add('on'); }
      return;
    }
    S.claim = null;
    S.newPw = {id:r.id, pw:r.newPassword, profile:r.profile};
    go('newpw');
  };
}

/* べつの ID で入っている画面に、リンクや QR が届いた。**聞いてから**入りなおす。
   聞かずに入りなおすと、人から送られたリンクを開いただけで、気づかないまま その人の ID に
   すりかわる（そのあとの提出が、その人の記録になる）。 */
function viewCardAsk(m){
  var a = S.cardAsk;
  if(!a){ return go(S.me ? 'today' : (S.teacher ? 'hw' : 'login')); }
  m.innerHTML =
    '<div class="lg"><div class="lg-body">'+
      '<div class="card lg-card np-card">'+
        '<h1>ID を かえますか</h1>'+
        '<p class="tiny">この画面は、いま べつの ID で 入っています。とどいた ID で 入りなおすと、いまの ID からは 出ます。</p>'+
        (a.who ? '<div class="np-row"><span class="lbl">いまの ID</span><span class="np-v num">'+esc(a.who)+'</span></div>' : '')+
        '<div class="np-row"><span class="lbl">とどいた ID</span><span class="np-v num">'+esc(a.card.id)+'</span></div>'+
        '<button class="btn" id="caGo">とどいた ID で 入りなおす</button>'+
        '<button class="btn ghost" id="caNo">いまのまま つづける</button>'+
      '</div>'+
    '</div></div>';
  $('#caGo').onclick = function(){ S.cardAsk = null; CARD = a.card; cardLogin(true); };
  /* いまのまま：番地の # はもう消してある。読み込み直せば、いまの ID のまま ふつうに始まる。 */
  $('#caNo').onclick = function(){ S.cardAsk = null; location.reload(); };
}

/* あたらしい合言葉。この端末が作った。サーバにあるのは、確かめるための値だけで、先生も読めない。
   ここで書きとめてもらう（ほかの端末から入るとき・14日たって入り直すときに使う）。
   **読み込み直すと、もう出せない。** 離れようとしたら止め、ボタンは2度押しにする。 */
function viewNewPw(m){
  var n = S.newPw;
  if(!n){ return go(S.me ? 'today' : (S.teacher ? 'hw' : 'login')); }
  m.innerHTML =
    '<div class="lg"><div class="lg-body">'+
      '<div class="card lg-card np-card">'+
        '<h1>あなたの あいことば</h1>'+
        '<p class="tiny">いま、この スマホ・パソコンが 作りました。先生も 読めません。'+
          'つぎに 入るとき（ほかの スマホ・パソコンで 入るとき）に つかいます。</p>'+
        '<div class="np-row"><span class="lbl">ID</span><span class="np-v num">'+esc(n.id)+'</span></div>'+
        /* 折り返すのは、線（-）のあとだけ。数字4桁の途中で折らない。 */
        '<div class="np-row"><span class="lbl">あいことば</span><span class="np-v np-pw">'+esc(n.pw).replace(/-/g, '-<wbr>')+'</span></div>'+
        '<p class="tiny"><b>この画面は、もう一度は 出せません。</b>紙に 書くか、画面を しゃしんに とってから、下の ボタンを おしてください。</p>'+
        '<button class="btn'+(n.sure ? ' np-sure' : '')+'" id="npGo">'+(n.sure ? 'はい、書きとめました。はじめる' : '書きとめた')+'</button>'+
        (n.sure ? '<p class="tiny">ほんとうに 書きとめましたか。おすと、この画面は とじます。</p>' : '')+
      '</div>'+
    '</div></div>';
  $('#npGo').onclick = async function(){
    if(!n.sure){ n.sure = true; return render(); }
    var prof = n.profile, id = n.id; S.newPw = null;
    if(prof) return signInServer(prof);
    /* 引き換えは済んだが、入り直せなかった（回線など）。書きとめた合言葉で、入口から入ってもらう。 */
    S.cardMsg = 'あいことばは できています。書きとめた あいことばで 入ってください。'; S.cardId = id;
    go('login');
  };
}
window.addEventListener('beforeunload', function(e){ if(S.newPw){ e.preventDefault(); e.returnValue = ''; } });

/* ------------------------------------------------------------
   うまく動かないとき ―― 何が起きたかを書いて送る（管理ページの「報告」に集まる）

   名前は送らない（だれかは、役割とクラスと番号まで）。送るのは文と、どの画面から来たか、
   画面の幅だけ。画面が自分で拾ったエラーも同じ口へ送る（reportError）。
   ------------------------------------------------------------ */
var reportFrom = '';
/* 講師には漢字で。生徒には学年に合わせて（jp）。 */
function rj(kana, kanji){ return S.teacher ? kanji : jp(kana, kanji); }
var reportDraft = '';
function viewReport(m){
  m.innerHTML =
    '<div class="h-card t-full rp-card">'+
      '<h1>'+esc(rj('うまく うごかないとき','うまく動かないとき'))+'</h1>'+
      '<p class="rp-lead">'+esc(rj('なにを したら、どう なったかを 書いてください。作った人に とどきます。名前は 書かなくて だいじょうぶです。',
                               '何をしたら、どうなったかを書いてください。作った人に届きます。名前は書かなくて大丈夫です。'))+'</p>'+
      '<textarea id="rpText" rows="6" maxlength="1000" aria-label="'+esc(rj('うまく うごかないとき','うまく動かないとき'))+'">'+esc(reportDraft)+'</textarea>'+
      '<div class="rp-acts"><button class="btn ghost" id="rpBack">'+esc(rj('もどる','戻る'))+'</button>'+
        '<button class="btn" id="rpSend">'+esc(rj('おくる','送る'))+'</button></div>'+
    '</div>';
  var ta = $('#rpText');
  ta.oninput = function(){ reportDraft = ta.value; };
  var back = function(){ go((reportFrom && reportFrom !== 'report') ? reportFrom : (S.teacher ? 'hw' : 'today')); };
  $('#rpBack').onclick = back;
  var busy = false;
  $('#rpSend').onclick = async function(){
    if(busy) return;
    var text = (ta.value || '').trim();
    if(!text){ toast(rj('なにが おきたかを 書いてください','何が起きたかを書いてください')); ta.focus(); return; }
    busy = true; $('#rpSend').textContent = rj('おくっています','送っています');
    var r = await S.srv.report({text:text, view:reportFrom || '', ctx:{w:String(window.innerWidth), h:String(window.innerHeight)}});
    busy = false;
    if(!r.ok){ var b = $('#rpSend'); if(b) b.textContent = rj('おくる','送る'); return toast(r.error); }
    reportDraft = '';
    toast(rj('おくりました。ありがとう。','送りました。ありがとうございます。'));
    back();
  };
}
/* 画面が自分で拾ったエラー。1回開いているあいだに 5件まで、同じ文は1回だけ。入っているときだけ送る。 */
var errSent = {}, errCount = 0;
function reportError(text){
  try{
    text = String(text || '').slice(0, 400);
    if(!text || errSent[text] || errCount >= 5) return;
    if(!S.srv || !S.srv.token || !S.srv.token() || !(S.me || S.teacher)) return;
    errSent[text] = 1; errCount++;
    S.srv.report({kind:'error', text:text, view:S.view || '', ctx:{w:String(window.innerWidth)}});
  }catch(e){}
}
function watchErrors(){
  window.addEventListener('error', function(e){
    if(!e || !e.message) return;
    reportError(e.message + ' @' + String(e.filename || '').split('/').pop().split('?')[0] + ':' + (e.lineno || 0));
  });
  window.addEventListener('unhandledrejection', function(e){
    var r = e && e.reason;
    reportError('約束の失敗: ' + String((r && (r.stack || r.message)) || r).slice(0, 300));
  });
}
/* http で開かれたら https へ（手元の 127.0.0.1・LAN は除く）。合言葉を暗号なしで流さない。 */
function toHttps(){
  var h = location.hostname;
  if(location.protocol === 'http:' && !/^(localhost|127\.|\[::1\]|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(h) && !/\.(localhost|test)$/.test(h) && !/trycloudflare\.com$/.test(h)){
    location.replace('https://' + location.host + location.pathname + location.search);
    return true;
  }
  return false;
}

/* ------------------------------------------------------------
   右上のメニュー

   ふだん使わないもの（名簿登録・書き出し・ログアウト）をここに集める。
   下のタブは「毎日ひらくもの」だけにしておきたい ――
   タブが5つも6つもあると、どれが主役か分からなくなる。
   ------------------------------------------------------------ */
function openMenu(){
  var items = [];
  if(S.teacher){
    items.push(['apps',   '導入の段階', 'コースごとに、紙のまま〜毎日テストまでを決めます']);
    /* 管理者のいる校舎では、席（IDとあいことば）は管理ページで作る。入口を2つにしない。 */
    if(!(S.teacher.profile && S.teacher.profile.managed)) items.push(['people', '名簿を登録する', '生徒のIDとあいことばを作ります']);
    items.push(['mats',   '教材をえらぶ',   '自分が使う教材を決めます']);
    items.push(['admin',  '記録の書き出し', 'バックアップを取ります']);
  }else if(S.me){
    items.push(['parent',   jp('ほごしゃの方へ','保護者の方へ'), 'お子さんの記録（％つき）と、先生へのメッセージ']);
    items.push(['settings', jp('せってい','設定'), '記録の書き出しなど']);
  }
  if(S.srv && (S.teacher || S.me)){
    items.push(['report', rj('うまく うごかないとき','うまく動かないとき'), rj('なにが おきたかを、作った人に 知らせます','何が起きたかを、作った人に知らせます')]);
  }
  reportFrom = S.view;
  /* 右上の「…」から出る小さな札（S05／T18）。画面を入れ替えない。外を押すと閉じる。 */
  closePop();
  var wrap = document.createElement('div'); wrap.id = 'popwrap'; wrap.className = 'popwrap';
  wrap.innerHTML =
    '<div class="pop" role="dialog" aria-label="メニュー">'+
      items.map(function(it){
        return '<button class="pop-it" data-go="'+it[0]+'"><span class="ic">'+(MENU_ICONS[it[0]] || '')+'</span>'+
          '<span class="tx"><b>'+esc(it[1])+'</b><small>'+esc(it[2])+'</small></span></button>';
      }).join('')+
      '<button class="pop-it out" id="mOut"><span class="ic">'+MENU_ICONS.out+'</span>'+
        '<span class="tx"><b>ログアウト</b><small>'+(S.teacher ? '共用のパソコンでは必ず押してください'
                                                       : 'ほかの人が使うときは押してください')+'</small></span></button>'+
    '</div>';
  document.body.appendChild(wrap);
  wrap.addEventListener('click', function(e){ if(e.target === wrap) closePop(); });
  wrap.querySelectorAll('[data-go]').forEach(function(b){
    b.onclick = function(){ var v = b.dataset.go; closePop(); go(v); };
  });
  /* 確かめは札の中で取る（confirm() は埋め込みの画面で黙って false を返すことがある） */
  $('#mOut').onclick = function(){
    var b = $('#mOut');
    b.outerHTML =
      '<div class="pop-ask">'+
        '<b>'+jp('ほんとうに ログアウトしますか','本当にログアウトしますか')+'</b>'+
        '<small>'+jp('つぎに入るとき、IDとあいことばが要ります。','次にログインするときは、IDと合言葉が必要です。')+'</small>'+
        '<div class="row" style="gap:8px;margin-top:10px">'+
          '<button class="btn small" id="mOutYes">ログアウトする</button>'+
          '<button class="btn ghost small" id="mOutNo">やめる</button>'+
        '</div>'+
      '</div>';
    $('#mOutYes').onclick = function(){ closePop(); signOut(); };
    $('#mOutNo').onclick  = function(){ openMenu(); };
  };
}

/* 画面が広いか。**判定はここだけ。**
   あちこちで window.innerWidth を見ると、CSS の区切り（1024px）と
   食い違ったときに、タブは3つなのに中身は4つ、という状態になる。
   CSS と同じ問い合わせを使って、必ず一致させる。 */
var WIDE = null;
function isWide(){
  if(!WIDE) WIDE = window.matchMedia('(min-width:1024px)');
  return WIDE.matches;
}

/* 幅が変わったら描き直す。
   パソコンでは「きろく」をホームに合流させるので、
   きろくを開いたままウィンドウを広げると、行き場のない画面が残る。 */
function watchWidth(){
  if(!WIDE) isWide();
  var was = isWide();
  var on = function(){
    var now = isWide();
    if(now === was) return;          /* またいでいなければ何もしない */
    was = now;
    /* 広げたとき、きろくはホームに合流している。
       そのままだと行き場のない画面が残るので、ホームへ送る。 */
    if(now && S.view === 'record') S.view = 'today';
    render();
  };
  if(WIDE.addEventListener) WIDE.addEventListener('change', on);
  else if(WIDE.addListener) WIDE.addListener(on);
  /* matchMedia の通知だけに頼らない。
     端末や埋め込みの画面では、幅が変わっても change が届かないことが
     ある（実機で、375→1440 に広げても届かなかった）。
     resize でも見る。連続して来るので、落ち着いてから1回だけ動かす。 */
  var t = null;
  window.addEventListener('resize', function(){
    clearTimeout(t);
    t = setTimeout(on, 150);
  });
}

var bounceTab = null;
function renderNav(){
  var f = $('#foot');
  if(S.view === 'gate' || S.view === 'login' || S.view === 'newpw' || S.view === 'claim' || S.view === 'cardask' || S.view === 'join' || S.view === 'place'){ f.innerHTML = ''; return; }
  var tabs = S.teacher
    /* 講師の5つ。求められている「宿題・成績・カリキュラム・生徒・教材」に
       そのまま対応する。設定と書き出しは「せいと」の中に置いた ――
       タブを6つ並べると、iPhoneでは文字が潰れて読めなくなる。 */
    /* 講師のタブは「毎日ひらくもの」だけ。
       名簿登録・教材えらび・書き出しは右上のメニューへ移した ――
       毎日使わないものをタブに置くと、主役が埋もれる。 */
    ? [['hw','宿題'],['roster','成績'],['progress','導入と進度']]
    /* 生徒は ホーム・宿題・毎日テスト（狭い画面では 先生から も）。**電話で4つまで。**
       5つ並べると、iPhone では字が潰れて読めなくなる。
       宿題と毎日テストは別のタブにする ―― 同じ画面に混ぜると
       「どれが必ずやるものか」が分からなくなり、任意のほうを宿題だと思って安心してしまう。
       設定は毎日ひらくものではないので、右上のメニューに置く（openMenu）。
       パソコンでは「先生から」をホームに合流させる ―― 広い画面で分けると、
       どちらも下半分が空く。 */
    /* 幅を問わず4つ。「先生から」は毎日テストの次（本人：ホームは今日やることと自分の記録の2つだけ）。 */
    /* 「宿題」は「提出」に（2026-10-11 本人：上に漢字・計算テストの提出、下にいつもの宿題）。
       過去問のタブは 中3・小6（受験学年）だけ。電話では5つになるが、本人の求めで置く。 */
    : [['today',jp('ホーム','ホーム')],['homework',jp('ていしゅつ','提出')]]
        /* 毎日テストのタブは、使っている教科があるときだけ（導入の段階が 4 のコース）。 */
        .concat(TubeStudent.dailyOn() ? [['daily','毎日テスト']] : [])
        .concat(TubeStudent.kakomonOn() ? [['kakomon','過去問']] : [])
        .concat([['record',jp('先生から','先生から')]]);
  f.innerHTML = '<nav>' +
    '<div class="nav-brand"><img class="mark" src="icon.svg" alt=""><span class="brand"><b>tube</b><i>study</i></span></div>' +
    tabs.map(function(t){
      var cur = (S.view===t[0] || (t[0]==='hw' && (S.view==='check' || S.view==='msgs')));
      return '<button data-tab="'+t[0]+'"'+(cur ? ' aria-current="page"' : '')+(bounceTab===t[0] ? ' class="bounce"' : '')+'>'+
             (TAB_ICONS[t[0]] || '')+'<span>'+t[1]+'</span></button>';
    }).join('') + '</nav>';
  f.querySelectorAll('[data-tab]').forEach(function(b){
    /* 今いるタブをもう一度押したら、そのタブのいちばん上へ（開いていた紙や予定を閉じる）。
       ほかのタブへ移るときは、戻ってきたとき同じ場所が見えるように何も閉じない。 */
    b.onclick = function(){
      /* 押したタブの印がはずむ（4c）。描き直しで作り直されるので、名前で覚えておく */
      bounceTab = b.dataset.tab;
      setTimeout(function(){ bounceTab = null; var x = $('#foot .bounce'); if(x) x.classList.remove('bounce'); }, 450);
      if(S.view === b.dataset.tab){
        if(window.TubeTeacher && window.TubeTeacher.home) window.TubeTeacher.home();
        if(window.TubeStudent && window.TubeStudent.home) window.TubeStudent.home();
      }
      go(b.dataset.tab);
    };
  });
}

/* ------------------------------------------------------------
   入口A ―― サーバがいるとき。IDとパスワード。
   ------------------------------------------------------------ */
/* 入口の動き ―― 端末で1日に1回だけ（本人の判断）。
   アイコンと銘が画面の真ん中に現れ、上へ移ってログインの札が出る。押せば飛ばせる。 */
var INTRO_KEY = 'tube.intro';
function introToday(){
  var d = new Date();
  return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();
}
/* 入口の動きは**毎回**（本人：すごくいいから毎回）。動きを減らす設定の端末だけ出さない。 */
function wantIntro(){
  try{
    if(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  }catch(e){}
  return true;
}
function markIntro(){ try{ localStorage.setItem(INTRO_KEY, introToday()); }catch(e){} }

/* 入ったあとの演出 ―― ID と合言葉を入れてホームへ移るとき（本人：ここにこそしっかり動きを）。
   印が弾んで出て銘が続き、そのあいだにホームを描き、幕がゆっくり明ける。約1.4秒。 */
function playWelcome(label){
  return new Promise(function(done){
    if(!wantIntro()){ return done(); }
    var old = $('#welcome'); if(old) old.remove();
    var el = document.createElement('div');
    el.id = 'welcome';
    /* 印は SVG で描く（icon.svg と同じ形）。白い輪だけ別の部品にして、最後に**ほどけて右へ消える**。
       影は角丸の箱の box-shadow（filter だと薄れるときに四角い枠が見えた）。 */
    el.innerHTML = '<div class="wc-in"><span class="wc-mark">'+
      '<svg viewBox="0 0 180 180" aria-hidden="true">'+
        '<defs><linearGradient id="wcg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0A6FC7"/><stop offset="1" stop-color="#004E93"/></linearGradient></defs>'+
        '<rect width="180" height="180" rx="40" fill="url(#wcg)"/>'+
        '<rect x="34" y="45" width="112" height="14" rx="7" fill="#F9B900"/>'+
        '<g class="wc-fly"><circle class="wc-ring" cx="90" cy="96" r="40" fill="none" stroke="#FFFFFF" stroke-width="13" stroke-linecap="round" transform="rotate(-90 90 96)"/></g>'+
      '</svg></span>'+
      '<div class="lg-word"><span class="brand"><b>tube</b><i>study</i></span>'+
      '<span class="wc-who">All aboard!</span>'+(label ? '<span class="wc-id">'+esc(label)+'</span>' : '')+'</div></div>';
    document.body.appendChild(el);
    /* 順番が肝心：ホームは幕が不透明なうちに描く（0.45秒。印の弾みは GPU の動きなので止まらない）。
       輪がほどける 1.5〜2.2秒は主スレッドを空けておく（描き直しは待たせる）。
       幕が明ける（不透明度＝GPU）ときに、待たせた描き直しを流す。 */
    setTimeout(done, 450);
    setTimeout(function(){ holdRendering(true); }, 1000);
    setTimeout(function(){ el.classList.add('unwind'); }, 1100);   /* 輪がほどけて右へ */
    setTimeout(function(){ el.classList.add('out'); holdRendering(false); }, 1650);
    setTimeout(function(){ if(el.parentNode) el.remove(); }, 2400);
  });
}

var demoList = null;        /* 「ためしに見る」の一覧（講師 wt01〜 と ためし用の生徒）。1度だけ取りにいく */
var demoBusy = false;       /* ボタンを押して、入っている途中 */

function viewLogin(m){
  /* 銘は上の帯ではなく、ここに大きく置く（上の帯は login では隠す）。
     並びは中央1列：銘 → ログインの札 → ためしに見る（デモのときだけ）→ 添え書き。 */
  var school = TubeConfig.school();
  m.innerHTML =
    '<div class="lg" id="lg">'+
      '<div class="lg-brand" id="lgBrand">'+
        '<img class="lg-mark" src="icon.svg" alt="">'+
        '<div class="lg-word"><span class="brand"><b>tube</b><i>study</i></span>'+
          (school.id ? '<span class="lg-for">'+esc(schoolTag())+'</span>' : '')+'</div>'+
      '</div>'+
      '<div class="lg-body" id="lgBody">'+
        '<div class="card lg-card">'+
          '<h1>ログイン</h1>'+
          '<p class="tiny">ID と あいことば を入れてください。</p>'+
          /* 見本を placeholder に書かない。薄いグレーの文字は「入力済み」に見え、実際にそう読み違えられた。 */
          '<label class="field"><span class="lbl">ID</span>'+
            '<input id="lId" autocapitalize="none" autocorrect="off" autocomplete="username" spellcheck="false"></label>'+
          '<label class="field"><span class="lbl">あいことば（線 - は入れなくても入れます）</span>'+
            '<input id="lPw" type="password" autocapitalize="none" autocorrect="off" spellcheck="false" autocomplete="current-password"></label>'+
          /* 長いローマ字を伏せ字のまま打つと、打ちまちがいに気づけない。見えるようにできる。 */
          '<button class="lnk lg-show" id="lShow" type="button">あいことばを 見えるようにする</button>'+
          '<button class="btn" id="lGo">はいる</button>'+
          '<div id="lMsg" class="loginmsg" role="alert"></div>'+
        '</div>'+
        '<div id="demoBox"></div>'+
        '<p class="tiny lg-help">ID や あいことばを 忘れたら、塾に 聞いてください。</p>'+
        (S.srv && location.pathname !== '/demo' ? '<button class="lnk lg-join" id="lJoin" type="button">初回登録する</button>' : '')+
      '</div>'+
    '</div>'+
    (S.demoSheet ? demoSheet() : '');

  var busy = false;
  var submit = async function(){
    if(busy) return;
    var id = ($('#lId').value||'').trim();
    var pw = $('#lPw').value || '';
    if(!id || !pw){
      /* どちらが空かを言い、その欄に飛ばす。「入れてください」だけだと
         入っているつもりの人には何のことか分からない。 */
      var miss = !id ? 'ID' : 'あいことば';
      showMsg(miss + 'が入っていません。カードの ' + miss + ' を入れてください。');
      ($(!id ? '#lId' : '#lPw')).focus();
      return;
    }
    busy = true;
    $('#lGo').textContent = 'かくにんしています…';
    /* 教材の読み込みで数秒かかることがある。無言で止まると
       「壊れた」と思われて二度押しされるので、経過を出す。 */
    var tick = setTimeout(function(){
      var g = $('#lGo'); if(g) g.textContent = 'きょうざいを よみこんでいます…';
    }, 1500);
    var r = await S.srv.login(id, pw);
    if(!r.ok){
      busy = false; clearTimeout(tick);
      var g2 = $('#lGo'); if(g2) g2.textContent = 'はいる';
      showMsg(r.error);
      if($('#lPw')){ $('#lPw').value = ''; $('#lPw').focus(); }
      return;
    }
    S.demoSheet = false;
    clearTimeout(tick);
    busy = false;
    /* 引き換えの言葉で入った：「この端末ではじめる」を押してもらってから、引き換える。 */
    if(r.claim){ S.claim = {id:r.id, token:r.claimToken, words:r.words}; return go('claim'); }
    await signInServer(r.profile);
  };
  $('#lGo').onclick = submit;
  if($('#lJoin')) $('#lJoin').onclick = function(){ TubeJoin.start(); };
  $('#lShow').onclick = function(){
    var f = $('#lPw'), on = f.type === 'password';
    f.type = on ? 'text' : 'password';
    $('#lShow').textContent = on ? 'あいことばを かくす' : 'あいことばを 見えるようにする';
    f.focus();
  };
  /* カードの QR・リンクで来て、入れなかったとき：理由を出し、ID は入れておく。 */
  if(S.cardBusy){ $('#lGo').textContent = 'かくにんしています…'; $('#lGo').disabled = true; }
  if(S.cardMsg){ showMsg(S.cardMsg); if(S.cardId) $('#lId').value = S.cardId; S.cardMsg = ''; S.cardId = ''; }
  $('#lPw').onkeydown = function(e){ if(e.key === 'Enter') submit(); };
  $('#lId').onkeydown = function(e){ if(e.key === 'Enter') $('#lPw').focus(); };
  renderDemoButtons();
  runIntro(m);
}

/* 銘の動き（FLIP）：置き場所は普通の流れのまま、最初だけ画面の真ん中へずらして置き、
   アイコンが弾んで出て銘が続き、そのあと元の場所へ滑らせる。札はそのあとで浮かび上がる。
   画面を押せば、その場で最後の形へ。 */
function runIntro(m){
  var lg = $('#lg'), br = $('#lgBrand');
  if(!lg || !br) return;
  if(S.introDone || !wantIntro()){
    lg.classList.add('lg-ready', 'lg-quick');
    return;
  }
  S.introDone = true;
  markIntro();
  lg.classList.add('lg-intro');
  var r = br.getBoundingClientRect();
  var dy = Math.max(0, window.innerHeight / 2 - (r.top + r.height / 2));
  br.style.transition = 'none';
  br.style.transform = 'translateY(' + Math.round(dy) + 'px) scale(1.12)';
  void br.offsetWidth;
  var done = false;
  var land = function(){
    if(done) return;
    done = true;
    clearTimeout(t1);
    br.style.transition = '';
    br.style.transform = '';
    lg.classList.remove('lg-intro');
    lg.classList.add('lg-ready');
  };
  var t1 = setTimeout(land, 1450);
  lg.addEventListener('pointerdown', land, {once:true});
}

function showMsg(text){
  var el = $('#lMsg');
  if(!el) return;
  el.textContent = text;
  el.classList.add('on');
}

/* ------------------------------------------------------------
   デモ用の入口 ―― ボタン1つ（ためしに見る）にたたみ、押すと役を選ぶ紙が開く（本人の判断）。

   サーバを --demo で起動したときだけ出る。合言葉は画面に出るので、
   出してよいと明示されたときにしか取りにいかない。
   ------------------------------------------------------------ */
var WHAT = {
  student: {t:'生徒として見る', d:'宿題・毎日テスト・きろく'},
  teacher: {t:'講師として見る', d:'宿題を出す・成績・進度'}
};
/* **生徒の札は、クラスで見分けがつくようにする。**
   札の字は「中2」「小5」のように学年だけ（クラス名の頭）。受講教科を下に、
   一言（上位の宿題あり など）は題の横に小さく添える。 */
function pickOf(a){
  var note = a.note || '';
  if(a.role === 'teacher'){
    /* 講師は本物の口座（wt01〜）が並ぶ（10-10 本人）。札は一覧の見出し、下の行は担当クラスの名前とコースの数
       （サーバが classes・courses に入れる）。氏名は持っていないので、本人は自分の ID と担当で見分ける。 */
    var cls = a.classes || [];
    var d = cls[0] === '*' ? '全部のクラスを見る' : cls.slice(0, 4).join('・') + (cls.length > 4 ? ' ほか' : '');
    if(a.courses) d = (d ? d + '　' : '') + '担当 ' + a.courses + ' コース';
    /* 札の名は「講師」、ID（wt01・t-001）は薄いグレーの添え（10-13 本人：ID が黒い太字で出ていて不自然） */
    var m = String(a.label || '').match(/^(講師)\s+(\S+)$/);
    return {chip:'師', t:m ? m[1] : (a.label || WHAT.teacher.t), note:m ? m[2] : '',
            d:d || note || WHAT.teacher.d};
  }
  if(a.className){
    var g = String(a.className).match(/^[小中高]\d/);
    return {chip:g ? g[0] : '生', t:a.className + ' の生徒', note:note,
            d:(a.subjects || []).join('・')};
  }
  var w = WHAT[a.role] || {t:a.label, d:''};
  return {chip:'生', t:w.t, d:w.d, note:''};
}
function demoSheet(){
  var list = demoList || [];
  return '<div class="shade" data-demoshut="1"></div>'+
    '<div class="sheet lg-sheet" role="dialog" aria-modal="true" data-sk="demo">'+
      '<div class="sh-top"><div><div class="sh-n">ためしに見る</div>'+
        '<div class="sh-s">押すとそのまま入れます（合言葉はいりません）。講師は本物の担当のまま、生徒はためし用の口座です。実在の生徒は入っていません。</div></div>'+
        '<button class="sh-x" data-demoshut="1" aria-label="とじる">&times;</button></div>'+
      '<div class="sh-body"><div class="demo-picks">'+ list.map(function(a, i){
        var w = pickOf(a);
        return '<button class="demo-pick" data-demo="'+i+'" data-demoid="'+esc(a.id)+'">'+
               '<span class="chip">'+esc(w.chip)+'</span>'+
               '<span class="t">'+esc(w.t)+
                 (w.note ? ' <span class="demo-note">'+esc(w.note)+'</span>' : '')+'</span>'+
               '<span class="d">'+esc(w.d)+'</span></button>';
      }).join('') +'</div></div>'+
    '</div>';
}
async function renderDemoButtons(){
  var box = $('#demoBox');
  if(!box || !S.srv || !S.demo) return;
  if(!demoList){
    var list = await S.srv.demoAccounts();
    if(!list || !list.length) return;
    demoList = list;
  }
  if(!$('#demoBox')) return;                 // 画面が変わっていたら何もしない
  $('#demoBox').innerHTML = '<button class="btn ghost lg-demo" id="demoOpen">ためしに見る</button>';
  $('#demoOpen').onclick = function(){ S.demoSheet = true; render(); };
  $$('[data-demoshut]').forEach(function(x){ x.onclick = function(){ S.demoSheet = false; render(); }; });
  $$('[data-demo]').forEach(function(b){
    /* ID だけをサーバに送って入る（合言葉は画面に来ない）。失敗は札の下に短く出す。 */
    b.onclick = async function(){
      var a = demoList[+b.dataset.demo];
      if(!a || demoBusy) return;
      demoBusy = true;
      b.classList.add('busy');
      var r = await S.srv.demoEnter(a.id);
      demoBusy = false;
      if(!r.ok){
        b.classList.remove('busy');
        toast(r.error || 'いまは入れません');
        return;
      }
      S.demoSheet = false;
      await signInServer(r.profile);
    };
  });
}

function viewGate(m){
  if(S.gate.step === 'code'){
    m.innerHTML =
      '<div class="card" style="margin-top:24px">'+
        '<div class="lbl">はじめに</div>'+
        '<h1 style="font-size:26px;margin:8px 0 14px">クラスのコード</h1>'+
        '<p class="tiny" style="margin-bottom:18px">先生からわたされたコードを'+
          '入れてください。同じ端末を何人かで使うときも、'+
          'それぞれ自分の出席番号で入ります。</p>'+
        '<label class="field"><span class="lbl">クラスコード</span>'+
          '<input id="gCode" autocapitalize="characters" autocomplete="off" '+
                 'spellcheck="false" placeholder="LDN-J2A"></label>'+
        '<button class="btn" id="gGo">つぎへ</button>'+
      '</div>';
    var submit = function(){
      var v = ($('#gCode').value||'').trim().toUpperCase();
      if(!v) return toast('コードを入れてください');
      var k = TubeConfig.classes().filter(function(x){
        return String(x.code||'').toUpperCase() === v; })[0];
      if(!k) return toast('そのコードのクラスが見つかりません');
      S.gate.klass = k; S.gate.step = 'who'; render();
    };
    $('#gGo').onclick = submit;
    $('#gCode').onkeydown = function(e){ if(e.key === 'Enter') submit(); };
    return;
  }

  var k = S.gate.klass;
  var here = TubeStore.students().filter(function(s){ return s.classId === k.id; });
  m.innerHTML =
    '<div class="card" style="margin-top:24px">'+
      '<div class="lbl">'+esc(k.name)+'</div>'+
      '<h1 style="font-size:26px;margin:8px 0 16px">じぶんをえらぶ</h1>'+
      (here.length
        ? '<div style="display:grid;gap:8px;margin-bottom:18px">'+
            here.map(function(s){
              return '<button class="opt" data-sid="'+s.sid+'">'+esc(s.label)+'</button>';
            }).join('')+'</div>'
        : '<p class="tiny" style="margin-bottom:18px">この端末にはまだ誰もいません。</p>')+
      '<label class="field"><span class="lbl">はじめての人は出席番号</span>'+
        '<input id="gSeat" inputmode="numeric" autocomplete="off" '+
               'maxlength="8" placeholder="07"></label>'+
      '<button class="btn" id="gAdd">この番号ではじめる</button>'+
      '<button class="btn ghost small" id="gBack" style="width:100%;margin-top:10px">'+
        'コードを入れなおす</button>'+
    '</div>';

  m.querySelectorAll('[data-sid]').forEach(function(b){
    b.onclick = function(){ signInLocal(b.dataset.sid); };
  });
  $('#gAdd').onclick = function(){
    var seat = ($('#gSeat').value||'').trim();
    if(!seat) return toast('出席番号を入れてください');
    if(!/^[A-Za-z0-9]{1,8}$/.test(seat)) return toast('番号は英数字だけで入れてください');
    var label = k.name.replace(/\s+/g,'') + '-' + seat;
    var dup = here.filter(function(s){ return s.label === label; })[0];
    if(dup) return signInLocal(dup.sid);
    var stu = TubeStore.addStudent(label, k.grade, k.id);
    signInLocal(stu.sid);
  };
  $('#gBack').onclick = function(){ S.gate.step = 'code'; render(); };
}

/* ------------------------------------------------------------
   入室のあと ―― その生徒に必要な教材だけを読み込む
   ------------------------------------------------------------ */
async function prepareStudent(stu, p){
  var gradeId = stu.grade || TubeConfig.gradeOfClass(stu.classId) || 'j1';
  /* 受講科目で教科を絞る（教材の読み込みも、毎日テストも）。
     **アプリを使うコースの教科だけ**（サーバの appSubjects。無い古いサーバなら受講科目ぜんぶ）。
     紙のままの教科（paperSubjects）は画面に1行だけ添える（ui-student の paperNote）。 */
  var taking = Array.isArray(stu.appSubjects) ? stu.appSubjects : stu.subjects;
  /* 受けている教科が全部まだ紙のとき：空の並びは「絞らない」の意味になるので、
     どの教科にも当たらない印を入れて、アプリの教科を0にする（紙の1行だけが出る）。 */
  if(Array.isArray(stu.appSubjects) && !stu.appSubjects.length && (stu.paperSubjects || []).length) taking = ['__paper__'];
  TubeConfig.setTaking(taking);
  await TubeContent.loadPacks(TubeConfig.packsFor(gradeId));
  var subjects = TubeConfig.subjectsFor(gradeId).map(function(x){
    return {subject:x.subject, plan:x.plan, order:TubeContent.orderFor(x.plan)};
  });
  return {stu:stu, p:p, grade:gradeId, subjects:subjects, paper:stu.paperSubjects || []};
}

async function signInLocal(sid){
  var p = await TubeStore.loadStudent(sid);
  if(!p) return toast('よみこめませんでした');
  var stu = TubeStore.student(sid);
  TubeStore.setActive(sid);
  S.me = await prepareStudent(stu, p);
  S.teacher = null;
  TubeSRS.rollDay(S.me.p);
  persist();
  go('today');
}

/* opts.quiet … 幕（All aboard!）を出さない（設定でクラスや科目を変えたあとの入りなおし）。opts.to … 着く画面。 */
async function signInServer(profile, opts){
  /* どの校舎の人かは、サーバが合言葉から決めて profile に入れてくる。
     画面に出すためだけに覚える。ここを書き換えても他校舎は見えない。 */
  if(profile.school) TubeConfig.setSchool(profile.school, profile.schoolName);
  resetModules();                       /* 前の人の控えを持ち込まない */

  /* 進度は必ずサーバから取り直してから画面を作る。
     これを起動時だけにしていたため、**新しくログインした人には
     講師が設定した教科が出ない**という不具合が出た（既定値のまま
     画面を組んでしまう）。入室の経路は1本にまとめる。 */
  if(S.srv){
    var cur = await S.srv.curriculum();
    if(cur) TubeConfig.adopt(cur);
  }
  if(profile.role === 'teacher'){
    S.me = null;
    TubeConfig.setTaking(null);           /* 講師の画面は全教科 */
    S.teacher = {
      profile: profile,
      label: '講師 ' + (profile.seat || ''),
      classes: TubeTeacher.classesOf(profile)
    };
    await TubeTeacher.afterLogin();
    /* 講師の着地は宿題。いちばん大事なのは宿題管理と進捗管理で、
       開いた瞬間に「今週どこが出ていないか」が見える状態にする。 */
    await playWelcome(S.teacher.label);
    return go('hw');
  }
  profile = Object.assign({}, profile, {label: labelOf(profile),
                                        grade: profile.grade || profile.level});
  var stu = TubeStore.adoptStudent(profile);
  var p = await TubeStore.loadStudent(stu.sid);
  var r = await TubeStore.syncIn(p, true);
  var h = await S.srv.head(stu.sid);
  if(h) p.serverRev = h.rev;
  S.me = await prepareStudent(stu, p);
  /* 登録してある学年・クラス・受講科目（サーバの口座のとおり）。設定の画面が出す。
     S.me.subjects は「アプリで使う教科」だけなので、紙のままの教科は入っていない。 */
  S.me.reg = {grade: profile.level || profile.grade || '', classId: profile.classId || '', subjects: (profile.subjects || []).slice()};
  /* 組分けの申告（テストの結果が出てから2週間）。ホームのいちばん上に「クラスは どちらに なりましたか」を出す。 */
  S.me.placeAsk = profile.placeAsk || null;
  /* 卒業（学年の繰り上げで、中3がクラスから外れた）。ホームのいちばん上に、ひとこと出す。 */
  S.me.grad = !!profile.grad;
  S.teacher = null;
  TubeSRS.rollDay(S.me.p);
  persist();
  if(r.status === 'pulled') toast(jp('サーバからきろくをよみこみました','サーバから記録を読み込みました'));
  if(!(opts && opts.quiet)) await playWelcome(S.me.stu.label);
  go((opts && opts.to) || 'today');
  TubeStudent.refreshHomework();
}

/* 画面に出す呼び名。氏名は持たないので、クラスと出席番号から組む。 */
function labelOf(x){
  if(!x) return '';
  if(x.label) return x.label;
  var k = TubeConfig.classOf(x.classId);
  /* 初回登録の口座は、呼び名（seat）が ID そのもの（s-042）。線でつながず「小4α s-042」。 */
  var sep = /^[a-z]-\d+$/.test(x.seat || '') ? ' ' : '-';
  return (k ? k.name.replace(/\s+/g,'') : (x.classId||'')) + sep + (x.seat || '??');
}

/* 画面ごとの控え（お知らせ・提出・受信箱・今日やること…）を捨てる。
   同じ画面で講師と生徒を行き来すると、前の人の控えが次の人に出た（09-13）。 */
function resetModules(){
  [window.TubeStudent, window.TubeDesk, window.TubeTeacher].forEach(function(mod){
    if(mod && mod.resetSession){ try{ mod.resetSession(); }catch(e){} }
  });
}

async function signOut(){
  if(S.srv) await S.srv.logout();
  S.me = null; S.teacher = null;
  resetModules();
  go(S.srv ? 'login' : 'gate');
}

function persist(){
  if(!S.me) return;
  var r = TubeStore.save(S.me.p);
  if(!r.ok && r.reason !== 'not-ready'){
    toast(jp('ほぞんできていません。せっていをみてください','保存できていません。設定を確認してください'));
  }
}

/* ------------------------------------------------------------
   起動
   ------------------------------------------------------------ */
/* 押した反応 ―― **すべての押せるもの**に同じ動き（本人：主タブだけでなく全ボタンに）。
   指を置いた瞬間（pointerdown）に is-press を付け、CSS の press-pop（沈んで戻る）が走る。
   押した先で画面が描き直されても、沈む動きの前半は見えるので「効いた」と分かる。
   宿題チェックのページの中（.screen-check）は今のまま ―― 1〜5 を連打する所に動きを足さない。 */
var PRESS_SEL = 'button, label.btn, a.btn, .pick, .subrow, .slot, .menuitem, .demo-pick, .ik-opt, .ik-stu, .ik-bstu, .ik-wchip';
function watchPress(){
  document.addEventListener('keydown', function(e){ if(e.key === 'Enter' || e.key === ' ') lastPointerAt = Date.now(); }, {passive:true});
  /* click も数える（捕捉の段。押す部品の onclick より先に走る）―― キーボードや読み上げの操作、検査の道具の click でも動きが付く */
  document.addEventListener('click', function(){ lastPointerAt = Date.now(); }, true);
  document.addEventListener('pointerdown', function(e){
    lastPointerAt = Date.now();
    if(document.body.classList.contains('screen-check')) return;
    var b = e.target && e.target.closest ? e.target.closest(PRESS_SEL) : null;
    if(!b || b.disabled) return;
    b.classList.remove('is-press');
    void b.offsetWidth;
    b.classList.add('is-press');
    b.addEventListener('animationend', function(){ b.classList.remove('is-press'); }, {once:true});
  }, {passive:true});
}

/* カードの QR・先生から届いたリンク：https://…/#k=<ID>.<合言葉か、引き換えの言葉>
   # から後ろはサーバへ送られない。読んだら、すぐに番地から消す（履歴や共有に残さない）。 */
var CARD = null, JOINCODE = null;
function readCard(){
  try{
    /* 招待の QR：https://…/#join=<登録コード>。読んだら、番地から消す。 */
    var j = /^#join=([A-Za-z0-9]{4,12})$/.exec(location.hash || '');
    if(j){ JOINCODE = j[1].toUpperCase(); if(history.replaceState) history.replaceState(null, '', location.pathname + location.search); return; }
    var m = /^#k=([A-Za-z0-9._-]{2,32})\.(.{4,80})$/.exec(decodeURIComponent(location.hash || ''));
    if(location.hash && history.replaceState) history.replaceState(null, '', location.pathname + location.search);
    if(m) CARD = {id:m[1].toLowerCase(), secret:m[2]};
  }catch(e){}
}

/* カードの QR・先生から届いたリンクで来た。
   返す true＝いまの人のまま、ふつうに続けてよい（同じ ID だった）。それ以外は、ここで画面を出した。
     ・だれも入っていない          → その ID で入る
     ・同じ ID で もう入っている    → 何もしない（入りなおさない）
     ・べつの ID で入っている       → 聞く（viewCardAsk）。sure＝聞いたあと */
async function cardLogin(sure){
  var card = CARD; CARD = null;
  if(!card || !S.srv) return;
  if(!sure && S.srv.token()){
    S.cardBusy = true;
    await S.srv.me();          /* 印が切れていれば、ここで捨てられる（token() が空になる） */
    S.cardBusy = false;
    /* 印が生きているあいだは、聞く。**me が繋がらずに落ちただけのときも聞く**（印は残っている。
       聞かずに進むと、電波の悪い一瞬に届いたリンクで、聞かれないまま すりかわる）。 */
    if(S.srv.token()){
      if(S.srv.who() === card.id) return true;
      S.cardAsk = {card:card, who:S.srv.who()};
      go('cardask');
      return false;
    }
  }
  S.cardBusy = true;
  if(S.session){ try{ endSessionQuietly(); }catch(e){} }
  if(S.srv.token()) await S.srv.logout();
  S.me = null; S.teacher = null; S.newPw = null;
  resetModules();
  go('login');
  var cr = await S.srv.login(card.id, card.secret);
  S.cardBusy = false;
  if(cr.ok){
    if(cr.claim){ S.claim = {id:cr.id, token:cr.claimToken, words:cr.words}; return go('claim'); }
    return signInServer(cr.profile);
  }
  S.cardMsg = cr.error || 'ログインできません';
  S.cardId = card.id;
  return go('login');
}
function endSessionQuietly(){ S.session = null; }

async function boot(){
  if(toHttps()) return;  /* http で来たら https へ */
  readCard();
  watchErrors();         /* 画面が拾ったエラーを、管理ページの報告へ */
  watchWidth();          /* 幅が変わったら描き直す */
  watchPress();          /* 押した反応 */
  try{
    /* テーマは明るい1つに固定した（暗いほうは凍結）。
       以前に暗いを選んだ人が暗いまま残らないよう、保存も読まない。 */
  }catch(e){}

  /* サーバがいるか確かめる。いなくても生徒の手元は動き続ける。 */
  var cfg = TubeConfig.sync();
  if(cfg){
    var probe = TubeSync.http(cfg);
    var health = await probe.probe();
    /* 「ためしに見る」：本物の校舎があるときは、ふつうの入口には出さない。デモの入口（/demo）で出す。 */
    if(health){ S.srv = probe; S.demo = !!health.demo || (!!health.demoPage && location.pathname === '/demo'); }
  }
  TubeStudent.loadCachedHomework();
  await TubeStore.boot({sync: S.srv});

  /* 開いたままの画面に、あとからリンクや QR の番地が来たとき（ページは読み込み直されない）。 */
  window.addEventListener('hashchange', function(){
    readCard();
    if(JOINCODE && S.srv){ var c0 = JOINCODE; JOINCODE = null; return TubeJoin.open(c0); }
    if(CARD && S.srv && !S.cardBusy) cardLogin();
  });
  /* 招待の QR で来た：入っていても いなくても、ようこそ（登録）から。 */
  if(S.srv && JOINCODE && location.pathname !== '/demo'){ var c1 = JOINCODE; JOINCODE = null; return TubeJoin.open(c1); }
  if(S.srv && CARD){ if(!(await cardLogin())) return; }
  if(S.srv){
    var prof = await S.srv.me();
    if(prof){
      /* 進度をサーバから取り直してから画面を作る。
         先に画面を作ると、古い分量で「きょうの分」が出てしまう。 */
      var cur = await S.srv.curriculum();
      if(cur) TubeConfig.adopt(cur);
      return signInServer(prof);
    }
    /* この端末ではじめて開いた：ようこそ（「登録する」「ログイン」）から。2度目からは、ふつうの入口。
       デモの入口（/demo）では出さない。 */
    if(location.pathname !== '/demo' && window.TubeJoin && !TubeJoin.welcomed()) return TubeJoin.open('');
    return go('login');
  }

  var sid = TubeStore.activeSid();
  if(sid && TubeStore.student(sid)) await signInLocal(sid);
  else go('gate');

  /* 画面に戻ってきたら、他の端末の学習を取り込む。
     「別の端末を開いたら最新になっている」を、これで成立させる。
     常時つなぎっぱなしにはしない ―― 子どもの回線と電池のため。 */
  document.addEventListener('visibilitychange', function(){
    if(document.visibilityState !== 'visible' || S.session) return;
    if(S.me){
      if(TubeSRS.rollDay(S.me.p)) persist();
      TubeStudent.refreshHomework();
      pullIfChanged();
      render();
    }
    watchNow();
  });
  window.addEventListener('online', function(){ pullIfChanged(); watchNow(); });
  setInterval(function(){ if(document.visibilityState === 'visible') watchNow(); }, WATCH_MS);
}

/* 見張り ―― パソコンとスマホを行き来しても「開いたら最新」。
   台帳の版（数十バイト）を見て、変わっていたときだけ本体を取り直す。
   生徒：写真・宿題。講師：宿題チェック・出した宿題・メッセージ。
   置いたままの画面でも、スマホで出した写真が 30秒以内にパソコンの宿題チェックに現れる。 */
var WATCH_MS = 25000, watchRev = null, watching = false;
async function watchNow(){
  if(!S.srv || !S.srv.rev || S.session || watching) return;
  if(!(S.me || S.teacher)) return;
  watching = true;
  try{
    var r = await S.srv.rev();
    if(!r) return;
    var key = JSON.stringify(r);
    if(watchRev === null){ watchRev = key; return; }
    if(key === watchRev) return;
    var was = JSON.parse(watchRev); watchRev = key;
    var changed = {};
    Object.keys(r).forEach(function(k){ if(r[k] !== was[k]) changed[k] = true; });
    if(S.me && window.TubeStudent && TubeStudent.wake) TubeStudent.wake(changed);
    if(S.teacher && window.TubeTeacher && TubeTeacher.wake) TubeTeacher.wake(changed);
  }finally{ watching = false; }
}

/* サーバ側の版だけを見て、変わっていたら本体を取りにいく。
   見張りは数十バイト、本体は最大95KB。毎回全部取ると回線を食う。 */
var pulling = false;
async function pullIfChanged(){
  if(!S.srv || !S.me || S.session || pulling) return;
  pulling = true;
  try{
    var h = await S.srv.head(S.me.stu.sid);
    if(!h) return;
    if((h.rev || 0) <= (S.me.p.serverRev || 0)) return;
    var r = await TubeStore.syncIn(S.me.p, true);
    if(r.status === 'pulled'){
      S.me.p.serverRev = h.rev;
      TubeSRS.rollDay(S.me.p);
      if(!S.session) render();
    }
  }finally{ pulling = false; }
}

/* ------------------------------------------------------------
   公開するもの
   ------------------------------------------------------------ */
/* 学年で表記を切り替える。**小6以上（e6・j1〜j3）は講師と同じ漢字の表記**、
   小5以下はかな多めの表記（「正かい率」→「正答率」）。
   生徒向けの文言を足すときは、必ず jp('かな', '漢字') の両方を書く。
   講師の画面は漢字の表記だけなので、この関数を通さない。 */
var KANJI_GRADES = {e6:1, j1:1, j2:1, j3:1};
function jp(kana, kanji){
  var g = S.me && S.me.grade;
  return KANJI_GRADES[g] ? kanji : kana;
}

global.TubeUI = {
  subject: setSubject, icons: TAB_ICONS, backIcon: BACK_ICON, countUp: countUp, subjIcon: subjIcon, ico: ico, pageHead: pageHead,
  S:S, $:$, $$:$$, esc:esc, toast:toast, shuffle:shuffle, jp:jp,
  fmtDate:fmtDate, dateInput:dateInput, labelOf:labelOf, unitName:unitName, unitText:unitText, unitTick:unitTick,
  sjClass:sjClass,
  go:go, nav:nav, render:render, persist:persist, signOut:signOut, pullIfChanged:pullIfChanged, watchNow:watchNow,
  isWide:isWide, keepInPlace:keepInPlace,
  signInLocal:signInLocal, signInServer:signInServer, boot:boot,
  /* 検査スクリプトが状態を覗くための窓 */
  state:function(){
    return {view:S.view, session:!!S.session, teacher:!!S.teacher,
            me:S.me, server:!!S.srv, pending:S.srv ? S.srv.pending() : 0};
  },
  server:function(){ return S.srv; }
};

})(window);
