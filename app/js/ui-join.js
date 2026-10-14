/* ============================================================
   初回登録 ―― 招待コードから来た保護者が、生徒の口座を自分で作る

   設計は Claude outputs/設計-初回登録と匿名の口座.md。画面の文言は、ここが原本。
   サーバの口は server/join.py（/api/join/check・/api/join・/api/join/finish）。

   段（J.step）：
     welcome  ようこそ（大きな銘の動き）。「登録する」「ログイン」
     code     登録コードを入れる（QR から来た人は飛ばす）
     intro    できること（約45秒の動画。右下に「スキップ」）
     form     学年 → クラス → 受講科目（1枚の中で、選ぶと次が下に現れる）。「2人目を登録する」
     confirm  確かめる（生徒の一覧・大事なこと・利用規約）
     ids      ID と合言葉
     done     完了。「はじめる」

   **動画の差し替えは JOIN_INTRO の1行（か、app/media/intro.mp4 を置き換えるだけ）。**
   合言葉は端末の中で鍵にして、確かめるための値だけを送る（js/scram.js）。
   ============================================================ */
(function(global){
"use strict";

/* 「できること」の動画。差し替えるときは、この場所のファイルを置き換える（名前を変えるなら、ここも）。
   3 つの比（10-12 本人：縦版・横版、スマホ・iPad・PC の比でそれぞれ全画面で美しく）：電話は縦 9:19.5、iPad は縦 3:4、PC は横 16:9。
   見ている端末の形で選ぶ（scripts/video/intro.py が作る intro-phone／intro-ipad／intro-pc.mp4）。無ければ intro.mp4。 */
function introKind(){
  /* 動画は画面を覆う（object-fit:cover）ので、見ている画面の比に最も近い 1 本を選ぶ＝切れる端が最も少ない。
     端末の種類ではなく比で選ぶ（iPad の横向きは 16:9、半分の幅の PC の窓は 3:4、など） */
  var w = window.innerWidth || 390, h = window.innerHeight || 844, r = w / h;
  var cand = {phone: 1080 / 2340, ipad: 3 / 4, pc: 16 / 9}, best = 'phone', bc = 2;
  for(var k in cand){ var c = 1 - Math.min(r, cand[k]) / Math.max(r, cand[k]); if(c < bc){ bc = c; best = k; } }
  return best;
}
var JOIN_INTRO = {kind: introKind(), src: 'media/intro-' + introKind() + '.mp4', fallback: 'media/intro.mp4', pauseAfter: 900};
var WELCOMED_KEY = 'tube.welcomed.v1';
var MAX_KIDS = 4;
var MIN_PW = 8;
var GRADE_JP = {e4:'小4', e5:'小5', e6:'小6', j1:'中1', j2:'中2', j3:'中3'};
var SUBJ_JP = {japanese:'国語', math:'数学', english:'英語', science:'理科', social:'社会'};

var J = null;
function ui(){ return global.TubeUI; }
function S(){ return ui().S; }
function $(sel){ return document.querySelector(sel); }
function esc(s){ return ui().esc(s); }
function lsGet(k){ try{ return localStorage.getItem(k); }catch(e){ return null; } }
function lsSet(k, v){ try{ localStorage.setItem(k, v); }catch(e){} }

function newKid(){ return {grade:'', classId:'', subjects:null}; }
function reset(code){
  J = {step:'welcome', code:code || '', info:null, kids:[newKid()], made:null, pw:'', busy:false, msg:'',
       terms:false, reveal:'', played:false, from:''};
}
function welcomed(){ return !!lsGet(WELCOMED_KEY); }
function markWelcomed(){ lsSet(WELCOMED_KEY, '1'); }

/* 入口：はじめてこの端末で開いた（か、招待の QR で来た）。 */
function open(code){
  reset(code);
  markWelcomed();
  ui().go('join');
}
/* ふつうの入口の「初回登録する」から。ようこその動きは見せず、すぐ先へ。 */
function start(){
  reset('');
  J.from = 'login';
  J.step = 'code';
  ui().go('join');
}
function leaveToLogin(){ J = null; ui().go('login'); }

function subjText(subs, grade){
  return (subs || []).map(function(s){ return (s === 'math' && /^e/.test(grade || '')) ? '算数' : SUBJ_JP[s]; }).join('・');
}
function className(cid){
  var c = (J.info && J.info.classes || []).filter(function(k){ return k.id === cid; })[0];
  return c ? c.name : cid;
}
function kidLine(k){ return className(k.classId) + '　' + subjText(k.subjects, k.grade); }
function kidDone(k){ return !!(k.grade && k.classId && k.subjects); }
function nth(i){ return (i + 1) + '人目'; }

/* ------------------------------------------------------------
   描く
   ------------------------------------------------------------ */
function view(m){
  if(!J) reset('');
  var h = '';
  if(J.step === 'welcome') h = viewWelcome();
  else if(J.step === 'code') h = viewCode();
  else if(J.step === 'intro') h = viewIntro();
  else if(J.step === 'form') h = viewForm();
  else if(J.step === 'confirm') h = viewConfirm();
  else if(J.step === 'ids') h = viewIds();
  else h = viewDone();
  m.innerHTML = '<div class="jn jn-' + J.step + '">' + h + '</div>';
  bind(m);
}
function to(step){ J.step = step; J.msg = ''; J.reveal = ''; window.scrollTo(0, 0); ui().render(); }

/* 銘（アイコン）。動かすために、部品を分けて置く（icon.svg と同じ形）。 */
function markSvg(cls){
  return '<svg class="jn-mark ' + (cls || '') + '" viewBox="0 0 180 180" aria-hidden="true">'+
    '<defs><linearGradient id="jnG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0A6FC7"/><stop offset="1" stop-color="#004E93"/></linearGradient></defs>'+
    '<rect class="jm-sq" width="180" height="180" rx="40" fill="url(#jnG)"/>'+
    '<circle class="jm-ring" cx="90" cy="96" r="40" fill="none" stroke="#fff" stroke-width="13" stroke-linecap="round" transform="rotate(-90 90 96)"/>'+
    '<rect class="jm-bar" x="34" y="45" width="112" height="14" rx="7" fill="#F9B900"/></svg>';
}
/* はじける粒（青・黄・白）。位置は決め打ち ―― 毎回同じ形に開く。 */
var BURST = [[-128,-86,'b',10],[-96,-140,'y',14],[-34,-168,'w',8],[40,-170,'y',10],[104,-134,'b',14],[140,-76,'y',8],
             [156,-6,'b',10],[132,70,'y',12],[-150,-12,'y',12],[-134,62,'b',8],[-70,-52,'w',6],[78,-58,'w',6],
             [-52,120,'y',9],[60,124,'b',9],[0,-206,'b',7],[0,150,'w',7]];
function burstHtml(){
  return '<div class="jn-burst" aria-hidden="true">' + BURST.map(function(b, i){
    return '<i class="jb jb-' + b[2] + '" style="--dx:' + b[0] + 'px;--dy:' + b[1] + 'px;--sz:' + b[3] + 'px;--d:' + (i * 28) + 'ms"></i>';
  }).join('') + '</div>';
}
function wordHtml(){
  var a = 'tube'.split('').map(function(c, i){ return '<b style="--i:' + i + '">' + c + '</b>'; }).join('');
  var b = 'study'.split('').map(function(c, i){ return '<i style="--i:' + (i + 4) + '">' + c + '</i>'; }).join('');
  return '<div class="jn-word" aria-label="tube study">' + a + b + '</div>';
}

function viewWelcome(){
  return '<div class="jn-stage">'+
      '<div class="jn-logo">' + burstHtml() + markSvg('jm-in') + '</div>'+
      wordHtml()+
      '<h1 class="jn-hello"><span class="jn-bw"><b>tube</b><i>study</i></span> にようこそ！</h1>'+
      '<p class="jn-sub">宿題を確かめる・出す・先生の添削を受け取る。<br>ぜんぶ、ここで。</p>'+
    '</div>'+
    '<div class="jn-actions jn-rise">'+
      '<button class="btn jn-big" id="jnGo">登録する</button>'+
      '<button class="btn ghost jn-big" id="jnLogin">ログイン</button>'+
      '<p class="tiny jn-note">はじめての方は「登録する」。ID をお持ちの方は「ログイン」。</p>'+
      '<div id="jnMsg" class="loginmsg' + (J.msg ? ' on' : '') + '" role="alert">' + esc(J.msg) + '</div>'+
    '</div>';
}

/* 登録コードの欄：1 文字ずつの枠（見た目）の上に、透明な 1 つの入力欄を重ねる。
   字送り（letter-spacing）で 1 つの欄を枠に合わせる作りは、字が枠の右に寄って 6 文字目が切れた（10-12 本人の写し）。
   枠は見た目だけ。打つ・貼る・キーボード・Enter は入力欄そのもの。字は枠の真ん中（flex）なので書体や幅に依らない */
function codeClean(s){ return String(s || '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6); }
function codeBox(){
  var v = codeClean(J.code), cells = '';
  for(var i = 0; i < 6; i++) cells += '<span class="jn-cell' + (i === Math.min(v.length, 5) ? ' cur' : '') + '">' + esc(v.charAt(i)) + '</span>';
  return '<div class="jn-codebox" id="jnCodeBox">'+
      '<input id="jnCode" class="jn-code" inputmode="latin" autocapitalize="characters" autocorrect="off" autocomplete="off" spellcheck="false" maxlength="8" value="' + esc(v) + '" aria-label="登録コード">'+
      '<div class="jn-cells" aria-hidden="true">' + cells + '</div>'+
    '</div>';
}
function paintCode(inp){
  var v = codeClean(inp.value); if(inp.value !== v) inp.value = v;
  J.code = v;
  var cells = document.querySelectorAll('#jnCodeBox .jn-cell'), cur = Math.min(v.length, 5);
  for(var i = 0; i < cells.length; i++){ cells[i].textContent = v.charAt(i); cells[i].classList.toggle('cur', i === cur); }
}

function viewCode(){
  return '<div class="jn-formhead"><span class="jn-brandsm">' + markSvg('') + '<span class="jn-bw"><b>tube</b><i>study</i></span></span></div>'+
    '<div class="jn-card card jn-rise">'+
      '<h1>登録コードを入れてください</h1>'+
      '<p class="tiny">塾からのお知らせ（紙・メール）にある 6文字です。QR から開いた方は、入れなくて大丈夫です。</p>'+
      codeBox()+
      '<div id="jnMsg" class="loginmsg' + (J.msg ? ' on' : '') + '" role="alert">' + esc(J.msg) + '</div>'+
      '<button class="btn jn-big" id="jnCodeGo">' + (J.busy ? '確かめています…' : '次へ') + '</button>'+
      '<button class="btn ghost" id="jnBack">戻る</button>'+
    '</div>';
}

function viewIntro(){
  /* 全画面（10-12 本人：PC・iPad・iPhone とも窓になっていた。画面占有率 100%）：画面に固定して覆い、動画は端まで（object-fit:cover）。
     比は今の画面で選び直す（開いてから向きが変わっていることがある）。動画の中に題と地があるので、見出しは置かない。帯は下に重ねる */
  JOIN_INTRO.kind = introKind(); JOIN_INTRO.src = 'media/intro-' + JOIN_INTRO.kind + '.mp4';
  return '<div class="jn-full" id="jnFull">'+
      '<video id="jnVideo" class="jn-fullv" src="' + esc(JOIN_INTRO.src) + '" playsinline webkit-playsinline muted autoplay preload="auto"></video>'+
      '<div class="jn-vfoot jn-fullbar"><span class="tiny">約45秒</span><button class="jn-sound" id="jnSound" type="button">音を出す</button><button class="btn small jn-skip" id="jnSkip">スキップ</button></div>'+
    '</div>';
}

function gradeTiles(k, i){
  var gs = (J.info && J.info.grades) || Object.keys(GRADE_JP);
  return '<div class="jn-tiles jn-g6">' + gs.map(function(g){
    return '<button class="jn-tile" data-act="grade" data-i="' + i + '" data-v="' + g + '" aria-pressed="' + (k.grade === g) + '">' + GRADE_JP[g] + '</button>';
  }).join('') + '</div>';
}
function classTiles(k, i){
  var ks = (J.info.classes || []).filter(function(c){ return c.grade === k.grade; });
  if(!ks.length) return '<p class="tiny">この学年のクラスが、まだありません。塾にお知らせください。</p>';
  return '<div class="jn-tiles jn-g3">' + ks.map(function(c){
    var letter = c.name.replace(GRADE_JP[k.grade] || '', '') || c.name;
    return '<button class="jn-tile jn-cls" data-act="class" data-i="' + i + '" data-v="' + esc(c.id) + '" aria-pressed="' + (k.classId === c.id) + '">'+
      '<span class="jn-letter">' + esc(letter) + '</span><span class="jn-small">' + esc(c.name) + '</span></button>';
  }).join('') + '</div>';
}
function comboRows(k, i){
  var cs = (J.info.combos || {})[(k.grade || 'e')[0]] || [];
  return '<div class="jn-rows">' + cs.map(function(c, n){
    var on = k.subjects && k.subjects.join(',') === c.join(',');
    return '<button class="jn-row" data-act="subj" data-i="' + i + '" data-v="' + n + '" aria-pressed="' + on + '">'+
      '<span>' + esc(subjText(c, k.grade)) + '</span><span class="jn-n">' + c.length + '科目</span></button>';
  }).join('') + '</div>';
}
function viewForm(){
  var many = J.kids.length > 1;
  var h = '';
  J.kids.forEach(function(k, i){
    var rv = function(key){ return J.reveal === key + i ? ' jn-new' : ''; };
    h += '<section class="jn-kid" id="jnKid' + i + '">'+
      (many ? '<div class="jn-kidhead"><span class="jn-nth">' + nth(i) + '</span>'+
        (i > 0 ? '<button class="lnk" data-act="drop" data-i="' + i + '">この生徒をやめる</button>' : '') + '</div>' : '')+
      '<div class="jn-q" id="jnQg' + i + '"><h1>' + (i === 0 ? '登録する生徒様の<wbr>学年を選んでください' : nth(i) + 'の<wbr>学年を選んでください') + '</h1>' + gradeTiles(k, i) + '</div>'+
      (k.grade ? '<div class="jn-q' + rv('c') + '" id="jnQc' + i + '"><h1>クラスを選んでください</h1>' + classTiles(k, i) + '</div>' : '')+
      (k.grade && k.classId ? '<div class="jn-q' + rv('s') + '" id="jnQs' + i + '"><h1>受講科目数を教えてください</h1>' + comboRows(k, i) + '</div>' : '')+
      '</section>';
  });
  var all = J.kids.every(kidDone);
  h += '<div class="jn-formfoot' + (J.reveal.indexOf('f') === 0 ? ' jn-new' : '') + '" id="jnFoot">'+
    (all && J.kids.length < MAX_KIDS ? '<button class="btn ghost jn-add" data-act="add">' + (J.kids.length + 1) + '人目を登録する</button>' : '')+
    (all ? '<div class="jn-two"><button class="btn ghost" data-act="formback">戻る</button>'+
           '<button class="btn" data-act="next">次へ</button></div>'
         : '<div class="jn-one"><button class="lnk" data-act="formback">戻る</button></div>')+
    '</div>';
  return '<div class="jn-formhead"><span class="jn-brandsm">' + markSvg('') + '<span class="jn-bw"><b>tube</b><i>study</i></span></span>' + (many ? '' : '<span class="jn-nth">1人目</span>') + '</div>' + h;
}

function viewConfirm(){
  var T = global.TubeTerms || {points:[], full:[]};
  return '<div class="jn-rise">'+
    '<h1 class="jn-h">この内容で登録します</h1>'+
    '<div class="jn-list">' + J.kids.map(function(k, i){
      return '<div class="jn-item"><span class="jn-nth">' + (J.kids.length > 1 ? nth(i) : '生徒') + '</span>'+
        '<span class="jn-cl">' + esc(className(k.classId)) + '</span><span class="jn-sb">' + esc(subjText(k.subjects, k.grade)) + '</span></div>';
    }).join('') + '</div>'+
    '<h2 class="jn-h2">大事なこと</h2>'+
    '<div class="jn-points">' + T.points.map(function(p){
      return '<div class="jn-point"><b>' + esc(p[0]) + '</b><p>' + esc(p[1]) + '</p></div>';
    }).join('') + '</div>'+
    '<button class="lnk jn-termsbtn" data-act="terms" aria-expanded="' + J.terms + '">' + (J.terms ? '利用規約を とじる' : '利用規約（全文）を読む') + '</button>'+
    (J.terms ? '<div class="jn-terms">' + T.full.map(function(sec){
      return '<h3>' + esc(sec[0]) + '</h3>' + sec[1].map(function(p){ return '<p>' + esc(p) + '</p>'; }).join('');
    }).join('') + '</div>' : '')+
    '<p class="tiny jn-agree">「アカウントを作成する」を押すと、利用規約に同意したことになります。<b>保護者の方が押してください。</b></p>'+
    '<div id="jnMsg" class="loginmsg' + (J.msg ? ' on' : '') + '" role="alert">' + esc(J.msg) + '</div>'+
    '<div class="jn-two"><button class="btn ghost" data-act="fix">修正する</button>'+
    '<button class="btn" data-act="create"' + (J.busy ? ' disabled' : '') + '>' + (J.busy ? '作成しています…' : 'アカウントを作成する') + '</button></div>'+
    '</div>';
}

function sameKids(){
  var seen = {}, dup = false;
  (J.made || []).forEach(function(m){
    var key = m.classId + '|' + (m.subjects || []).join(',');
    if(seen[key]) dup = true;
    seen[key] = 1;
  });
  return dup;
}
function viewIds(){
  var many = J.made.length > 1;
  var head = many
    ? '<h1 class="jn-h">生徒IDができました</h1>'+
      '<div class="jn-idlist">' + J.made.map(function(m){
        return '<div class="jn-idrow"><span class="jn-idwho">' + esc(className(m.classId)) + '<small>' + esc(subjText(m.subjects, m.grade)) + '</small></span>'+
          '<span class="jn-id num">' + esc(m.id) + '</span></div>';
      }).join('') + '</div>'+
      (sameKids() ? '<p class="jn-twin">同じクラスのお子さまが います。<b>どちらが どの ID を使うか、いま ご家庭で 決めてください。</b>（1人に1つの ID です）</p>' : '')
    : '<p class="jn-lead">あなたの生徒IDは</p><div class="jn-idone num">' + esc(J.made[0].id) + '</div><p class="jn-lead">です</p>';
  return '<div class="jn-rise">' + head+
    '<div class="jn-memo"><b>ID は必ずメモをとってください。</b><span>ID が分かれば、合言葉を忘れても塾で作り直せます。ID を忘れると、だれの記録かを確かめる方法がありません。</span></div>'+
    '<form id="jnForm" class="card jn-pwcard" autocomplete="on" novalidate>'+
      '<h2>合言葉を作ってください</h2>'+
      '<p class="tiny">' + MIN_PW + '文字以上。' + (many ? 'ごきょうだいで同じ合言葉を使います。' : '') + 'この端末（iPhone・パソコン）に保存しておくと、次からは打たずに入れます。</p>'+
      '<input class="jn-hideuser" type="text" name="username" autocomplete="username" value="' + esc(J.made[0].id) + '" readonly tabindex="-1" aria-hidden="true">'+
      '<label class="field"><span class="lbl">合言葉</span>'+
        '<input id="jnPw" name="password" type="password" autocomplete="new-password" autocapitalize="none" autocorrect="off" spellcheck="false" minlength="' + MIN_PW + '"></label>'+
      '<button class="lnk" id="jnShow" type="button">合言葉を見えるようにする</button>'+
      '<div id="jnMsg" class="loginmsg' + (J.msg ? ' on' : '') + '" role="alert">' + esc(J.msg) + '</div>'+
      '<button class="btn jn-big" id="jnPwGo" type="submit"' + (J.busy ? ' disabled' : '') + '>' + (J.busy ? '登録しています…' : 'この合言葉で登録する') + '</button>'+
    '</form></div>';
}

function viewDone(){
  var many = J.made.length > 1;
  return '<div class="jn-stage jn-donestage">'+
      '<div class="jn-logo">' + burstHtml() + markSvg('jm-in') + '</div>'+
      '<h1 class="jn-hello">登録が完了しました！</h1>'+
      '<p class="jn-sub">' + (many ? 'どちらで はじめますか。' : 'ID は ' + esc(J.made[0].id) + ' です。') + '</p>'+
    '</div>'+
    '<div class="jn-actions jn-rise' + (many ? ' jn-starts' : '') + '">'+
      J.made.map(function(m, i){
        return '<div class="jn-start">' + (many ? '<span class="jn-id num">' + esc(m.id) + '</span><span class="tiny">' + esc(className(m.classId)) + '</span>' : '')+
          '<button class="btn jn-big" data-act="begin" data-i="' + i + '"' + (J.busy ? ' disabled' : '') + '>はじめる</button></div>';
      }).join('')+
      '<div id="jnMsg" class="loginmsg' + (J.msg ? ' on' : '') + '" role="alert">' + esc(J.msg) + '</div>'+
    '</div>';
}

/* ------------------------------------------------------------
   動かす
   ------------------------------------------------------------ */
function showMsg(t){ J.msg = t || ''; var el = $('#jnMsg'); if(el){ el.textContent = J.msg; el.classList.toggle('on', !!J.msg); } }

async function checkCode(next){
  if(J.busy) return;
  var code = (J.code || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  if(code.length < 6){ J.step = 'code'; J.msg = code ? '登録コードは 6文字です。' : ''; return ui().render(); }
  J.busy = true; ui().render();
  var r = await S().srv.joinCheck(code);
  J.busy = false;
  if(!r.ok){ J.step = 'code'; J.msg = r.error; return ui().render(); }
  J.code = code; J.info = r.data; J.msg = '';
  to(next || 'intro');
}

function reveal(key, id){
  J.reveal = key;
  ui().render();
  var el = document.getElementById(id);
  if(el && el.scrollIntoView){
    setTimeout(function(){ try{ el.scrollIntoView({behavior:'smooth', block:'center'}); }catch(e){ el.scrollIntoView(); } }, 60);
  }
}

async function createAccounts(){
  if(J.busy) return;
  J.busy = true; ui().render();
  var r = await S().srv.joinNew({code:J.code, agree:true,
    students:J.kids.map(function(k){ return {grade:k.grade, classId:k.classId, subjects:k.subjects}; })});
  J.busy = false;
  if(!r.ok){ J.msg = r.error; return ui().render(); }
  J.made = r.data.made;
  to('ids');
}

async function setPassword(){
  if(J.busy) return;
  var pw = ($('#jnPw') || {}).value || '';
  if(TubeScram.norm(pw).length < MIN_PW){ return showMsg('合言葉は ' + MIN_PW + '文字以上にしてください（空白と - は数えません）。'); }
  J.busy = true; J.pw = pw; J.msg = '';
  var mm = $('#jnMsg'); if(mm){ mm.textContent = ''; mm.classList.remove('on'); }     /* 前の注意（短すぎる、など）を残さない */
  var go = $('#jnPwGo'); if(go){ go.disabled = true; go.textContent = '登録しています…'; }
  try{
    var items = [];
    for(var i = 0; i < J.made.length; i++){
      items.push({id:J.made[i].id, setup:J.made[i].setup, verifier:await TubeScram.verifier(pw)});
    }
    var r = await S().srv.joinFinish({items:items});
    J.busy = false;
    if(!r.ok){
      J.msg = r.error;
      if(r.status === 410){ J.made = null; J.pw = ''; return to('confirm'); }     /* 時間切れ。確かめる画面から作り直す */
      return ui().render();
    }
  }catch(e){ J.busy = false; J.msg = 'この端末では合言葉を作れませんでした。新しいブラウザで開いてください。'; return ui().render(); }
  /* 端末のパスワード保存に入れてもらう（対応しているブラウザだけ。Safari は、入るときに聞く）。 */
  try{
    if(global.PasswordCredential && navigator.credentials && navigator.credentials.store){
      navigator.credentials.store(new global.PasswordCredential({id:J.made[0].id, password:pw, name:'tube study ' + J.made[0].id}));
    }
  }catch(e){}
  J.made.forEach(function(m){ delete m.setup; });
  to('done');
}

async function begin(i){
  if(J.busy) return;
  var m = J.made[i];
  J.busy = true; ui().render();
  if(S().srv.token()){ try{ await S().srv.logout(); }catch(e){} }
  var r = await S().srv.login(m.id, J.pw);
  if(!r.ok){ J.busy = false; J.msg = r.error || '入れませんでした。ログインから、ID と合言葉で入ってください。'; return ui().render(); }
  J = null;                                   /* 合言葉を持ったままにしない */
  return ui().signInServer(r.profile);
}

function bind(m){
  var b;
  if((b = $('#jnGo'))) b.onclick = function(){ if(J.code) return checkCode('intro'); to('code'); };
  if((b = $('#jnLogin'))) b.onclick = leaveToLogin;
  if((b = $('#jnBack'))) b.onclick = function(){ if(J.from === 'login') return leaveToLogin(); to('welcome'); };
  var inp = $('#jnCode');                                         /* b は下で付け替わるので、閉包には別の名で持つ */
  if(inp){
    inp.oninput = function(){ paintCode(inp); };
    inp.onkeydown = function(e){ if(e.key === 'Enter'){ paintCode(inp); checkCode('intro'); } };
    inp.onfocus = function(){ var x = $('#jnCodeBox'); if(x) x.classList.add('focus'); };
    inp.onblur = function(){ var x = $('#jnCodeBox'); if(x) x.classList.remove('focus'); };
    if(!J.busy) setTimeout(function(){ try{ inp.focus(); }catch(e){} }, 350);
  }
  if((b = $('#jnCodeGo'))) b.onclick = function(){ J.code = ($('#jnCode') || {}).value || ''; checkCode('intro'); };
  /* ようこその動きは、押せば最後の形へ */
  var st = m.querySelector('.jn-welcome');
  if(st) st.addEventListener('pointerdown', function(){ st.classList.add('jn-fast'); }, {once:true});

  var v = $('#jnVideo');
  if(v){
    var ended = false;
    var next = function(wait){ if(ended) return; ended = true; setTimeout(function(){ if(J && J.step === 'intro') to('form'); }, wait); };
    v.addEventListener('ended', function(){ next(JOIN_INTRO.pauseAfter); });
    v.addEventListener('error', function(){                             /* 読めなければ、元の 1 本に替える。それも無ければ飛ばして先へ */
      if(JOIN_INTRO.fallback && v.getAttribute('src') !== JOIN_INTRO.fallback){ v.setAttribute('src', JOIN_INTRO.fallback); var q = v.play && v.play(); if(q && q.catch) q.catch(function(){}); return; }
      next(0);
    });
    var p = v.play && v.play(); if(p && p.catch) p.catch(function(){});
    $('#jnSkip').onclick = function(){ try{ v.pause(); }catch(e){} next(0); };
    $('#jnSound').onclick = function(){
      v.muted = !v.muted; $('#jnSound').textContent = v.muted ? '音を出す' : '音を消す';
      if(!v.muted){ var q = v.play(); if(q && q.catch) q.catch(function(){}); }
    };
  }

  [].forEach.call(m.querySelectorAll('[data-act]'), function(el){
    el.onclick = function(){
      var act = el.getAttribute('data-act'), i = +el.getAttribute('data-i'), val = el.getAttribute('data-v');
      var k = J.kids[i];
      if(act === 'grade'){
        if(k.grade !== val){ k.grade = val; k.classId = ''; k.subjects = null; }
        return reveal('c' + i, 'jnQc' + i);
      }
      if(act === 'class'){ k.classId = val; return reveal('s' + i, 'jnQs' + i); }
      if(act === 'subj'){
        k.subjects = ((J.info.combos || {})[k.grade[0]] || [])[+val].slice();
        return reveal('f', 'jnFoot');
      }
      if(act === 'add'){ J.kids.push(newKid()); return reveal('g' + (J.kids.length - 1), 'jnKid' + (J.kids.length - 1)); }
      if(act === 'drop'){ J.kids.splice(i, 1); J.reveal = ''; return ui().render(); }
      if(act === 'formback'){ return to(J.from === 'login' ? 'code' : 'welcome'); }
      if(act === 'next'){ if(J.kids.every(kidDone)) to('confirm'); return; }
      if(act === 'fix'){ return to('form'); }
      if(act === 'terms'){ J.terms = !J.terms; return ui().render(); }
      if(act === 'create'){ return createAccounts(); }
      if(act === 'begin'){ return begin(i); }
    };
  });

  var f = $('#jnForm');
  if(f){
    f.addEventListener('submit', function(e){ e.preventDefault(); setPassword(); });
    $('#jnShow').onclick = function(){
      var p = $('#jnPw'), on = p.type === 'password';
      p.type = on ? 'text' : 'password';
      $('#jnShow').textContent = on ? '合言葉をかくす' : '合言葉を見えるようにする';
      p.focus();
    };
  }
}

/* ------------------------------------------------------------
   設定から、学年・クラス・受講科目を変える（自己申告。情報は ID に集まる。どの端末でも同じ）
   ------------------------------------------------------------ */
var P = null;
async function openPlace(){
  var r = await S().srv.placementInfo();
  if(!r.ok){ ui().toast(r.error); return; }
  P = {info:r.data, grade:r.data.now.grade, classId:r.data.now.classId, subjects:(r.data.now.subjects || []).slice(), busy:false, msg:''};
  ui().go('place');
}
function placeChanged(){
  var n = P.info.now;
  return P.grade !== n.grade || P.classId !== n.classId || P.subjects.join(',') !== (n.subjects || []).join(',');
}
function viewPlace(m){
  if(!P){ return ui().go('settings'); }
  J = J || {info:P.info};                          /* 並べる部品（tiles）は、登録の画面と同じものを使う */
  var keep = J.info; J.info = P.info;
  var k = {grade:P.grade, classId:P.classId, subjects:P.subjects.length ? P.subjects : null};
  var ok = !!(k.grade && k.classId && k.subjects) && placeChanged();
  m.innerHTML = '<div class="jn jn-place"><div class="jn-rise">'+
    '<h1 class="jn-h">クラスと受講科目を変える</h1>'+
    '<p class="tiny jn-pnote">塾との契約が変わったとき、まちがえて登録したときに。変えると、届く宿題が変わります。ID と合言葉は変わりません。</p>'+
    '<div class="jn-kid">'+
      '<div class="jn-q"><h2 class="jn-ph">学年</h2>' + gradeTiles(k, 0) + '</div>'+
      (k.grade ? '<div class="jn-q"><h2 class="jn-ph">クラス</h2>' + classTiles(k, 0) + '</div>' : '')+
      (k.grade && k.classId ? '<div class="jn-q"><h2 class="jn-ph">受講科目</h2>' + comboRows(k, 0) + '</div>' : '')+
    '</div>'+
    '<div id="jnMsg" class="loginmsg' + (P.msg ? ' on' : '') + '" role="alert">' + esc(P.msg) + '</div>'+
    '<div class="jn-two jn-pfoot"><button class="btn ghost" id="plNo">やめる</button>'+
    '<button class="btn" id="plGo"' + (ok && !P.busy ? '' : ' disabled') + '>' + (P.busy ? '変えています…' : 'この内容に変える') + '</button></div>'+
    '</div></div>';
  J.info = keep; if(J && !J.step) J = null;
  [].forEach.call(m.querySelectorAll('[data-act]'), function(el){
    el.onclick = function(){
      var act = el.getAttribute('data-act'), val = el.getAttribute('data-v');
      if(act === 'grade'){ if(P.grade !== val){ P.grade = val; P.classId = ''; P.subjects = []; } }
      if(act === 'class'){ P.classId = val; }
      if(act === 'subj'){ P.subjects = ((P.info.combos || {})[P.grade[0]] || [])[+val].slice(); }
      P.msg = ''; ui().render();
    };
  });
  $('#plNo').onclick = function(){ P = null; ui().go('settings'); };
  $('#plGo').onclick = async function(){
    if(P.busy) return;
    P.busy = true; ui().render();
    var r = await S().srv.placement({grade:P.grade, classId:P.classId, subjects:P.subjects});
    if(!r.ok){ P.busy = false; P.msg = r.error; return ui().render(); }
    P = null;
    ui().toast('変えました');
    return ui().signInServer(r.profile, {quiet:true, to:'settings'});
  };
}

/* 作りかけのまま離れようとしたら止める（ID を見たあと・合言葉を作る前）。 */
global.addEventListener('beforeunload', function(e){
  if(J && J.step === 'ids'){ e.preventDefault(); e.returnValue = ''; }
});

global.TubeJoin = {
  view:view, open:open, start:start, welcomed:welcomed, markWelcomed:markWelcomed,
  openPlace:openPlace, viewPlace:viewPlace,
  state:function(){ return J; }, INTRO:JOIN_INTRO
};
})(window);
