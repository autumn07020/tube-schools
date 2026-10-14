/* ============================================================
   講師の机 ―― 今日やること・宿題チェック・成績の診断
   ------------------------------------------------------------
   Claude outputs/PLAN-講師ページ改修.md の画面。

   宿題タブ   … 「今日やること」＝宿題チェック（写真の評価）だけ。
                全部終われば「今日はここまで」。
   宿題チェック … 別ページ。左に全員のマス、マウスを乗せた生徒のノートを右に大きく。
                ←→ ページ、↑↓ 前後の子、1〜5 評価、Enter 未評価の子へ。
   成績タブ   … 担当コースの札 → コース（提出・理解度の推移、度数分布、苦手の自動抽出）
                → 単元・生徒 → 個別の宿題（足す・置き換える・減らす・出さない）。

   ここは画面だけを持つ。数える規則はサーバ（server/insight.py）にある ――
   画面で数え直すと、2か所で違う数字が出る。
   ============================================================ */
(function(global){
"use strict";

function ui(){ return global.TubeUI; }
function S(){ return ui().S; }
function esc(s){ return ui().esc(s); }
function toast(t){ ui().toast(t); }
function srv(){ return S().srv; }
function render(){ ui().render(); }

var WD = ['日','月','火','水','木','金','土'];
/* 講師の画面の言葉。生徒の画面は ui-student.js の rateWord（数字は出さない）。 */
var WORD = {5:'よくできた', 4:'できた', 3:'もう少し', 2:'がんばろう', 1:'やり直し', 0:'出ていない'};
/* サーバの提案の種類。解き直し（redo・basic）は提案しなくなった ―― 足す宿題は講師のプリセットから選ぶ。 */
var KIND = {redo:'解き直し', app:'アプリで復習', lighten:'量を減らす', basic:'上位の宿題を基本に'};
function presetLine(pr){
  return pr.range === 'pages' ? (pr.text+' '+(pr.pages || '')).trim()
       : pr.range === 'app'   ? 'アプリの問題 '+(pr.count || 10)+'問'
       : pr.text+'（同じ回の範囲）';
}
var YELLOW = 70;

function md(t){ if(!t) return ''; var d = new Date(t); return (d.getMonth()+1)+'/'+d.getDate(); }
function mdS(s){ var p = String(s || '').split('-'); return p.length === 3 ? (+p[1])+'/'+(+p[2]) : ''; }
/* 次の授業の日付には曜日を添える（「9/29 火」。今日の見出しと同じ形）。日付だけだと今週か来週か一瞬迷う。 */
function mdSW(s){ var p = String(s || '').split('-'); return p.length === 3 ? mdS(s)+' '+WD[new Date(+p[0], +p[1]-1, +p[2]).getDay()] : ''; }
/* 呼び名の終わりの番号か ID。「小4α-07」→ 07、「小4α s-042」→ s-042（初回登録の口座は、呼び名が ID）。 */
function seatNo(label){
  var s = String(label || '');
  var m = /([a-z]-\d+)$/.exec(s);
  if(m) return m[1];                                   /* 本物：s-104 */
  /* デモ・席の口座（中2R-01）：合同コース（T・R・D）で「01」が3つ並ぶので、クラスの文字を残す → R-01 */
  var m2 = /^[小中]\d([^-]*)-(\d+)$/.exec(s);
  if(m2) return (m2[1] ? m2[1] + '-' : '') + m2[2];
  return s.split('-').pop();
}
function tone(v){ return (v === null || v === undefined) ? 'none' : (v < YELLOW ? 'y' : 'b'); }
function has(v){ return v !== null && v !== undefined; }
/* 授業の回の名前（教材の呼び名）。**回を n から直に組まない**（ui-core の unitName／unitText／unitTick）。 */
function uname(x){ return ui().unitName(x); }
function utext(x){ return ui().unitText(x); }
function ushort(x){ return uname(x) || (x && x.topic) || ''; }
/* 節の見出し。日本語だけ（ui-teacher の sectHead と同じ形）。right は組み済みの HTML。 */
function head(title, right){
  return '<div class="secthead gridbar t-full"><h2>'+esc(title)+'</h2>'+
    (right ? '<div class="wk num">'+right+'</div>' : '')+'</div>';
}
function todayLabel(){
  var d = new Date();
  return (d.getMonth()+1)+'/'+d.getDate()+' '+WD[d.getDay()];
}

/* ============================================================
   1. 今日やること（宿題タブのいちばん上）
   ============================================================ */
var today = undefined;       /* undefined=未取得 / null=取得中 / obj */

function loadToday(){
  if(today === null || !srv()) return;
  today = null;
  srv().today().then(function(got){
    today = got || {tasks:[], done:[], ratedToday:0};
    render();
  });
}

/* 今日のチェックの輪。**この画面で唯一の図**。
   今日おわった件 ÷（おわった件 ＋ 残りの件）―― 今日の手仕事がどこまで進んだか。
   途切れのない1本の弧（本人の指示。区切りの輪はやめた）。中に数は書かない ―― 右の
   「宿題チェック あと3件」で足りる（各コースの札に人数がある）。 */
function ringArc(total, done){
  var r = 52, c = 2 * Math.PI * r;
  total = Math.max(1, total|0); done = Math.max(0, Math.min(total, done|0));
  var v = c * done / total;
  return '<svg class="dk-ring" viewBox="0 0 120 120" aria-hidden="true">'+
    '<circle class="trk" cx="60" cy="60" r="'+r+'"></circle>'+
    (done ? '<circle class="val" cx="60" cy="60" r="'+r+'" transform="rotate(-90 60 60)" '+
              'stroke-dasharray="'+v.toFixed(1)+' '+(c - v).toFixed(1)+'"></circle>' : '')+
  '</svg>';
}
/* コースの鍵（j2r:math）から教科の id。 */
function sjOfKey(k){ return (k && k.indexOf(':') > 0) ? k.split(':')[1] : ''; }

/* 今日やること ―― 横に長い帯を並べない。輪の札（左）＋ チェックの札（右に格子）＋ 今日おわった（下に格子）。 */
function todayCard(){
  if(today === undefined) loadToday();
  var ico = ui().ico;
  if(!today){
    return '<div class="h-card h-full t-hero wait"><p class="tiny">今日のチェックをしらべています…</p></div>';
  }
  var t = today, left = t.tasks.length, done = t.done.length, rated = t.ratedToday || 0;
  var C1 = 2 * Math.PI * 42, frac = (left + done) ? done / (left + done) : 1;
  var ring = '<div class="t-ring"><svg viewBox="0 0 100 100" aria-hidden="true">'+
      '<circle cx="50" cy="50" r="42" fill="none" stroke="rgba(60,60,67,.10)" stroke-width="10"></circle>'+
      '<circle cx="50" cy="50" r="42" fill="none" stroke="'+(left ? '#0A6FC7' : '#F9B900')+'" stroke-width="10" stroke-linecap="round" stroke-dasharray="'+(C1 * frac).toFixed(1)+' '+C1.toFixed(1)+'"></circle></svg>'+
      '<div class="t-ringn num cu" data-len="'+String(left || '').length+'">'+(left ? left : '')+(left ? '' : '<svg class="t-ringchk" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>')+'</div></div>';
  /* 輪の札は、右の札の塊（.t-cards）と同じ行に置いて高さを合わせる（行またぎの --rows はやめた。10-11） */
  var hero = '<div class="h-card t-hero'+(left ? '' : ' fin')+'">'+ ring +
      '<div class="t-herotx">'+
        '<span class="h-lbl blue">'+ico('check', 20, 2.2)+'宿題チェック</span>'+
        (left ? '<span class="t-herobig">あと<span class="num cu">'+left+'</span>件</span>'
              : '<span class="t-herobig">今日はここまで</span><span class="t-herosub">おつかれさまでした</span>')+
        '<span class="t-herosub">今日つけた評価 <span class="t-hn"><span class="num">'+rated+'</span>件</span></span>'+
        '<span class="t-herosub">おわった <span class="t-hn"><span class="num">'+done+'</span>件</span></span>'+
      '</div>'+
    '</div>';
  var CR = 2 * Math.PI * 16;
  /* 札の数で密度を変える（10-11 本人：4段は多い）。
       電話      … 3件まで1列、4件以上は2列の小さな札
       iPad・細い窓 … 6件まで2列、7件以上は3列の小さな札
       PC        … 6件まで2列、7件以上は半分の札で4列（3段以内）
     12件を超えるぶんは「ほか N 件」の札1つにまとめ（押すと宿題チェックへ）。列は CSS（.t-cards.n3/.n6）が幅で決め、
     余った札が横に広がるのも CSS（折り返す flex）が行う。ここで「最後の1枚」を見分けない。 */
  var SHOW = (t.tasks.length > 12 ? 11 : 12), shown = t.tasks.slice(0, SHOW), rest = t.tasks.length - shown.length;   /* 「ほか」の札を入れて 12 枚まで（4列×3段） */
  var dense = shown.length > 6, tiles = shown.length + (rest > 0 ? 1 : 0), go = dense ? 'チェック' : 'チェックする';
  var cards = shown.map(function(x){
    var sj = sjOfKey(x.key), tot = x.submitted + (x.missing || 0), f = tot ? x.submitted / tot : 0;
    return '<button class="h-card t-check'+ui().sjClass(sj)+'" data-dkcheck="'+esc(x.key)+'|'+x.n+'">'+
      '<span class="t-ckhead"><span class="t-ckname">'+ui().subjIcon(sj, 20)+'<span class="t-cktx">'+esc(x.name)+'</span></span><span class="t-ckdue"><span class="num">'+esc(md(x.dueAt))+'</span>〆</span></span>'+
      '<span class="t-ckwhat">'+esc(utext(x))+'</span>'+
      '<span class="t-cknum"><span class="h-big"><b class="num cu">'+x.todo+'</b><span>人 未評価</span></span>'+
        '<svg viewBox="0 0 40 40" class="t-mini" aria-hidden="true"><circle cx="20" cy="20" r="16" fill="none" stroke="rgba(60,60,67,.12)" stroke-width="5"></circle>'+
        '<circle cx="20" cy="20" r="16" fill="none" stroke="#F9B900" stroke-width="5" stroke-linecap="round" stroke-dasharray="'+(CR * f).toFixed(1)+' '+CR.toFixed(1)+'"></circle></svg></span>'+
      '<span class="t-ckfoot"><span class="t-ckst">写真 <span class="num">'+x.submitted+'</span>人'+(x.missing ? '<span>未提出 <span class="num">'+x.missing+'</span>人</span>' : '')+'</span>'+
        '<span class="btn gold small t-ckgo">'+go+'</span></span>'+
    '</button>';
  }).join('');
  if(rest > 0){
    var nx = t.tasks[SHOW];
    cards += '<button class="h-card t-check t-more" data-dkcheck="'+esc(nx.key)+'|'+nx.n+'">'+
      '<span class="t-morebig">ほか <b class="num">'+rest+'</b>件</span><span class="t-moresub">宿題チェックで続きを見る →</span></button>';
  }
  /* n3：4枚以上（電話は2列） n6：7枚以上（小さな札。iPad 3列、PC 3列、広い PC 4列） n9：10枚以上（PC は4列でないと3段に収まらない） */
  cards = '<div class="t-cards'+(tiles > 3 ? ' n3' : '')+(tiles > 6 ? ' n6' : '')+(tiles > 9 ? ' n9' : '')+'" data-n="'+t.tasks.length+'">'+cards+'</div>';
  var fin = done
    ? '<div class="h-card h-full t-done"><span class="h-lbl grey">今日おわった <span class="num">'+done+'</span>件</span><div class="t-dgrid">'+ t.done.map(function(x){
        var sj = sjOfKey(x.key);
        return '<button class="t-drow'+ui().sjClass(sj)+'" data-dkcheck="'+esc(x.key)+'|'+x.n+'">'+
          '<span class="t-dok">'+ico('check', 14, 3)+'</span>'+
          '<span class="t-dn"><b>'+esc(x.name)+'</b><small>'+esc(utext(x))+'</small></span>'+
          '<span class="t-dc"><span class="num">'+x.ratedToday+'</span>人</span></button>';
      }).join('') +'</div></div>'
    : '';
  return hero + cards + fin;
}

function wireToday(m){
  m.querySelectorAll('[data-dkcheck]').forEach(function(b){
    b.onclick = function(){
      var p = b.dataset.dkcheck.split('|');
      openCheck(p[0], +p[1]);
    };
  });
}

/* 時間割のコマに添える「前回の単元の理解度」。**押す部品にしない**（コマ自体が押す部品のため）。 */
function slotUnd(key){
  if(over === undefined) loadOverview();
  if(!over || !over.courses) return '';
  var c = over.courses.filter(function(x){ return x.key === key; })[0];
  if(!c || !c.latest || !has(c.latest.und)) return '';
  var v = c.latest.und;
  return '<span class="dk-und '+tone(v)+'" title="'+esc(utext(c.latest))+' の理解度">前回 '+v+'%</span>';
}

/* ============================================================
   2. 宿題チェック（view = 'check'）
   ============================================================ */
var chk = {key:null, n:null, data:undefined, want:null, focus:null, page:0, mode:null, find:'', kind:null};
var hoverTimer = null;

function openCheck(key, n){
  chk.key = key; chk.n = n || null; chk.data = undefined; chk.want = null;
  chk.focus = null; chk.page = 0;
  ui().go('check', 'push');
}

function isTodo(r){ return r.files.length && !(r.v >= 1); }
/* 決まりのひとことへの、生徒の返事の状態（講師の画面の言葉） */
function ackWord(r){
  var a = r.ack || {};
  if(a.state === 'ok') return '生徒が確認'+(a.okAt ? ' '+md(a.okAt * 1000) : '')+(a.auto ? '（1週間で自動）' : '');
  if(a.state === 'asked') return '質問あり・返事まで止まっています';
  if(a.state === 'answered') return '返事ずみ・生徒の確認待ち';
  return '生徒の確認待ち';
}
function rowOf(sid){
  return ((chk.data && chk.data.rows) || []).filter(function(r){ return r.sid === sid; })[0] || null;
}

function loadCheck(){
  var want = chk.key + '|' + (chk.n || '');
  if(chk.want === want) return;
  chk.want = want;
  srv().check(chk.key, chk.n).then(function(got){
    if(chk.want !== want) return;          // 読み終わる前に別のコース・回へ移った
    chk.data = got || {error:true};
    if(got && got.lesson) chk.n = got.lesson.n;
    if(got && got.rows && !rowOf(chk.focus)){
      var first = got.rows.filter(isTodo)[0] ||
                  got.rows.filter(function(r){ return r.files.length; })[0] || got.rows[0];
      chk.focus = first ? first.sid : null;
      chk.page = 0;
    }
    render();
  });
}

function photo(r, i, name){
  var t = (srv() && srv().token) ? srv().token() : '';
  return '/api/submissions/' + encodeURIComponent(r.head) + '/' + encodeURIComponent(r.sid) + '/' +
    encodeURIComponent(name || r.files[i]) + '?t=' + encodeURIComponent(t);
}

function printUrl(r, which){
  var t = (srv() && srv().token) ? srv().token() : '';
  return '/api/submissions/' + encodeURIComponent(r.head) + '/' + encodeURIComponent(r.sid) + '/print?t=' + encodeURIComponent(t) +
    (which ? '&which=' + which : '');
}
/* 右に出すページ：ふだんは出したノート。「返した添削を見る」なら赤を入れた紙 */
function pagesOf(r){
  return (chk.showRet && (r.returned || []).length) ? r.returned : r.files;
}
function pdfUrl(r, which){
  var t = (srv() && srv().token) ? srv().token() : '';
  return '/api/submissions/' + encodeURIComponent(r.head) + '/' + encodeURIComponent(r.sid) + '/pdf?t=' + encodeURIComponent(t) +
    (which ? '&which=' + which : '');
}
var dkBusy = null;
/* 講師の写真も生徒と同じ道で縮めて JPEG に（photo.js） */
function dkPrepare(file){ return TubePhoto.prepare(file); }
async function dkUpload(kind, sid, list){
  var r = rowOf(sid); if(!r || !list || !list.length) return;
  if(list.length > 6) return toast('一度に6枚までです');
  /* ひとことは**描き直す前に**読む。render() が欄を作り直すので、あとで読むと書きかけが消える（実際そうなった）。
     欄が空なら、保存ずみのひとこと（r.note）を添える ―― 評価の返事で描き直された直後でも、書いたことばが落ちない */
  var note = (document.getElementById('dkNote') || {}).value || r.note || '';
  dkBusy = sid; render();
  var files = [];
  try{
    for(var i = 0; i < list.length; i++){ var f = await dkPrepare(list[i]); if(!f || !f.b64) throw new Error('read'); files.push(f); }
    if(files.reduce(function(n, f){ return n + f.b64.length; }, 0) > 11 * 1024 * 1024) throw new Error('大きすぎます。PDF は 6MB まで。枚数を減らしてください');
    var got = kind === 'scan' ? await srv().scanFor(r.head, sid, files) : await srv().returnFor(r.head, sid, files, note);
    if(!got || got.error) throw new Error((got && got.error) || '送れませんでした');
    toast(kind === 'scan' ? '紙を取り込みました。評価を付けてください' : '添削を返しました。生徒の「先生から」に出ます');
    chk.showRet = (kind === 'return'); chk.page = 0;
    chk.data = undefined; chk.want = null; loadCheck();
  }catch(e){ toast(e.message || '送れませんでした'); }
  finally{ dkBusy = null; render(); }
}

function recount(){
  var st = {n:0, submitted:0, rated:0, todo:0, missing:0};
  ((chk.data && chk.data.rows) || []).forEach(function(r){
    var rated = r.v >= 1;
    st.n++;
    if(r.files.length) st.submitted++;
    if(rated) st.rated++;
    if(r.files.length && !rated) st.todo++;
    if(!r.files.length && !rated) st.missing++;
  });
  chk.data.stats = st;
  return st;
}

/* 次のチェック（今日やることの並びで、いま見ている回の次） */
function nextTask(){
  if(today === undefined) loadToday();
  var ts = (today && today.tasks) || [];
  return ts.filter(function(x){ return !(x.key === chk.key && x.n === chk.n); })[0] || null;
}

function statsHtml(st){
  return '<span>提出 <b class="num">'+st.submitted+'</b><span class="num">/'+st.n+'</span>人</span>'+
    '<span>評価ずみ <b class="num">'+st.rated+'</b></span>'+
    '<span class="'+(st.todo ? 'warn' : 'ok')+'">未評価 <b class="num">'+st.todo+'</b></span>'+
    (st.missing ? '<span>未提出 <b class="num">'+st.missing+'</b></span>' : '');
}

function cellHtml(r){
  var on = chk.focus === r.sid;
  var rated = r.v >= 1;
  var cls = rated ? 's-rated' : (r.files.length ? 's-todo' : 's-none');
  var mark = rated ? '<b class="dk-v v'+r.v+'">'+r.v+'</b>'
           : r.files.length ? '<i class="dk-dot" aria-hidden="true"></i>'
           : '<span class="dk-dash">未提出</span>';
  var say = rated ? '評価 '+r.v+' '+WORD[r.v] : (r.files.length ? '未評価' : '未提出');
  return '<button role="option" aria-selected="'+(on ? 'true' : 'false')+'" class="dk-cell '+cls+(on ? ' focus' : '')+'" '+
      'data-dksid="'+esc(r.sid)+'" aria-label="'+esc(r.label)+' '+esc(say)+'">'+
    '<span class="dk-thumb">'+(r.files.length ? '<img loading="lazy" alt="" src="'+esc(photo(r, 0))+'">' : '')+'</span>'+
    '<span class="dk-cap"><span class="dk-no num">'+esc(seatNo(r.label))+'</span>'+(r.worry ? '<span class="dk-wtag">心配</span>' : '')+mark+'</span>'+
    (r.personal ? '<span class="dk-pers" title="この生徒だけの宿題があります">個別</span>' : '')+
  '</button>';
}

function viewerHtml(){
  var r = rowOf(chk.focus);
  if(!r) return '<div class="dk-vempty">左のマスにマウスを乗せると、ここにノートが大きく出ます</div>';
  var pages = pagesOf(r), showingRet = (pages !== r.files);
  var n = pages.length, i = Math.max(0, Math.min(chk.page, n - 1));
  var rate = '<div class="dk-rate" role="group" aria-label="評価（キーの1〜5）">'+ [1, 2, 3, 4, 5].map(function(v){
      return '<button class="dk-rb v'+v+(r.v === v ? ' on' : '')+'" data-dkrate="'+v+'" aria-pressed="'+(r.v === v)+'">'+
        '<b class="num">'+v+'</b><span>'+WORD[v]+'</span></button>';
    }).join('') +'</div>';
  var worryRow = '<div class="dk-worry"><button class="dk-wbtn'+(r.worry ? ' on' : '')+'" data-dkworry="1" aria-pressed="'+(!!r.worry)+'" title="「理解が心配」は生徒に見えません（キーの 9）"><i></i>理解が心配</button>'+
      '<span class="tiny">1〜4は取り組み、5は8割以上できたとき。「理解が心配」は生徒に見えません</span></div>';
  return '<div class="dk-vhead"><div class="dk-vname">'+esc(r.label)+
      (r.personal ? '<span class="dk-pers">この生徒だけの宿題あり</span>' : '')+'</div>'+
      (n ? '<div class="dk-vpage num">'+(showingRet ? '<b>返した添削</b> ' : '')+(i + 1)+' / '+n+'ページ</div>' : '')+'</div>'+
    '<div class="dk-vimg'+(showingRet ? ' ret' : '')+'">'+
      (n ? '<img alt="'+esc(r.label)+(showingRet ? ' に返した添削 ' : ' のノート ')+(i + 1)+'ページ目" src="'+esc(photo(r, i, pages[i]))+'">'+
           (n > 1 ? '<button class="dk-pg prev" data-dkpage="-1" aria-label="前のページ"'+(i <= 0 ? ' disabled' : '')+'>‹</button>'+
                    '<button class="dk-pg next" data-dkpage="1" aria-label="次のページ"'+(i >= n - 1 ? ' disabled' : '')+'>›</button>' : '')
         : '<p class="dk-nophoto">写真はまだ出ていません'+(r.v >= 1 ? '（評価はついています）' : '')+'</p>')+
    '</div>'+
    '<div class="dk-rateline">'+rate+worryRow+'</div>'+
    '<div class="dk-vfoot">'+
      '<label class="dk-note"><span class="lbl">ひとこと（生徒に届きます）</span>'+
        '<input id="dkNote" maxlength="200" value="'+esc(r.note || '')+'" '+
        'placeholder="例：途中の式が書けていて、よくわかります"'+(n ? '' : ' disabled')+'></label>'+
      (r.v >= 1 ? '<button class="lnk dk-clear" data-dkrate="clear">評価を消す</button>' : '')+
    '</div>'+
    fixHtml(r) +
    ((r.items || []).length ? '<div class="dk-items'+((r.personal || (r.items || []).some(function(it){ return it.extra || it.personal; })) ? ' has-extra' : '')+'"><span class="lbl">この生徒の宿題</span>'+ (r.items || []).map(function(it){
      return '<span class="dk-it'+(it.personal ? ' p' : '')+'">'+esc(it.title)+
        (it.personal ? '<em>この生徒だけ</em>' : it.extra ? '<em>上位</em>' : '')+'</span>';
    }).join('') +'</div>' : '')+
    '<div class="dk-keys">←→ ページ　↑↓ 前後の子　1〜5 評価　Enter 未評価の子へ　0 評価を消す</div>';
}

/* 添削の札 ―― 紙に赤を入れて返す道を、3段でそのまま並べる（1タッチずつ）。
     ① 印刷する（開くと印刷の窓が出る）
     ② 赤を入れて、撮る（選んだ瞬間に、いまの「ひとこと」と一緒に生徒へ返る）
     ③ 返した添削（何枚・いつ。右の画面に出して確かめられる）
   ふだんは写真を見ながら数字とひとことだけ。作文・漢字のとめはねなど、書いて返したいときにここを使う。 */
var USE_WORDS = ['紙のまま', '宿題を出す', '写真で提出', '添削まで', '毎日テストまで'];
function courseUse(){
  var c = chk.data && chk.data.course;
  return (c && typeof c.use === 'number') ? c.use : 4;
}
function phone(){ return !!(window.matchMedia && window.matchMedia('(max-width:699px)').matches); }
function fixHtml(r){
  var has = r.files.length, ret = (r.returned || []).length, busy = (dkBusy === r.sid);
  var scan = '<label class="dk-mini dk-up">'+(has ? '紙を取り込みなおす' : '紙を取り込む（対面の生徒）')+
      '<input type="file" accept="image/*,application/pdf" multiple data-dkscan="'+esc(r.sid)+'"'+(busy ? ' disabled' : '')+'></label>';
  /* 決定（2026-10-08）：講師の赤入れは iPad・パソコンだけ。iPhone では赤入れの欄を出さず、一言だけ。 */
  if(phone()){
    return '<div class="dk-fix dk-fix-off"><div class="dk-fix-h"><span class="lbl">添削</span>'+
      '<span class="tiny">赤を入れて返すのは iPad かパソコンで。この画面では評価とひとことを付けられます。</span></div>'+
      (ret ? '<div class="dk-fix-acts"><button class="dk-mini done" data-dkshow="'+(chk.showRet ? 'files' : 'returned')+'">'+(chk.showRet ? 'ノートに戻す' : '返した添削 '+ret+'枚を見る')+'</button></div>' : '')+
    '</div>';
  }
  /* 導入の段階が「添削まで」（3）より前のコースでは、赤を入れて返す道を出さない（紙の取り込みだけ残す）。 */
  if(courseUse() < 3){
    return '<div class="dk-fix dk-fix-off">'+
      '<div class="dk-fix-h"><span class="lbl">添削</span>'+
        '<span class="tiny">このコースは「'+USE_WORDS[courseUse()]+'」までの導入です。赤を入れて返すのは、導入と進度で「添削まで」にすると使えます。</span></div>'+
      '<div class="dk-fix-acts">'+scan+'</div>'+
    '</div>';
  }
  /* **全部が1画面に収まるように、ボタンは1行。** 前は「① 印刷する ② 赤を入れて返す ③ 生徒に届く」の3段で、
     右の紙が長くなり、PDF と取り込みは下にスクロールしないと押せなかった（2026-10-11 本人）。 */
  return '<div class="dk-fix">'+
    '<div class="dk-fix-h"><span class="lbl">添削（紙に赤を入れて返す）</span>'+
      (busy ? '<span class="dk-busy">送っています…</span>' : '')+
      (r.origin === 'teacher' ? '<span class="tiny">先生が取り込んだ紙</span>' : '')+
      (ret ? '<span class="tiny">返した添削 '+ret+'枚（'+esc(md((r.returnedAt || 0) * 1000))+'）</span>' : '')+'</div>'+
    '<div class="dk-fix-acts">'+
      (has ? '<button class="dk-mini pri" data-dkdraw="'+esc(r.sid)+'"'+(busy ? ' disabled' : '')+'>この画面で書く ✎</button>' : '')+
      '<label class="dk-mini">撮った写真を選ぶ<input type="file" accept="image/*,application/pdf" multiple data-dkreturn="'+esc(r.sid)+'"'+(busy ? ' disabled' : '')+'></label>'+
      (has ? '<a class="dk-mini" href="'+esc(printUrl(r, ''))+'" target="_blank" rel="noopener">印刷する</a>' : '')+
      (has ? '<a class="dk-mini" href="'+esc(pdfUrl(r, ''))+'" target="_blank" rel="noopener">PDF で保存</a>' : '')+
      scan+
      (ret ? '<button class="dk-mini done" data-dkshow="'+(chk.showRet ? 'files' : 'returned')+'">'+(chk.showRet ? 'ノートに戻す' : '返した添削を右に出す')+'</button>' : '')+
      (ret ? '<a class="dk-mini" href="'+esc(pdfUrl(r, 'returned'))+'" target="_blank" rel="noopener">返した添削を PDF で</a>' : '')+
    '</div>'+
  '</div>';
}

/* ---- この画面で赤を入れる（iPad・ペン・指・マウス） ----
   印刷して撮り直さなくても、出された写真の上にそのまま書いて返せる。
   chk.draw = {sid, page, strokes:{ページ番号:[{c,w,wpx,pts:[[x,y,圧]…]}…]}, color, width, busy}
   線は**写真の画素の座標**で持つ（画面の大きさが変わっても、返す紙は原寸で合成する）。 */
function openDraw(sid){
  var r = rowOf(sid); if(!r || !r.files.length) return;
  var finger = false; try{ finger = localStorage.getItem('tube.draw.finger') === '1'; }catch(e){}
  chk.draw = {sid:sid, page:0, strokes:{}, color:'#D62828', width:5, busy:false, penAt:0, finger:finger};
  render();
}
function drawSheet(){
  var d = chk.draw; if(!d) return '';
  var r = rowOf(d.sid); if(!r || !r.files.length){ chk.draw = null; return ''; }
  var n = r.files.length, i = Math.max(0, Math.min(d.page, n - 1));
  var cnt = function(k){ return (d.strokes[k] || []).length; };
  var written = Object.keys(d.strokes).filter(function(k){ return cnt(k); }).length;
  return '<div class="shade" data-dkdrawshut="1"></div>'+
    '<div class="sheet wide dk-draw" role="dialog" aria-modal="true" data-sk="draw|'+esc(d.sid)+'">'+
      '<div class="sh-top"><div><div class="sh-n">'+esc(r.label)+' の答案に赤を入れる</div>'+
        '<div class="sh-s">ペンや指でそのまま書けます。書き終えたら「返す」'+(n > 1 ? '　ページ '+(i + 1)+' / '+n : '')+'</div></div>'+
        '<button class="sh-x" data-dkdrawshut="1" aria-label="閉じる">&times;</button></div>'+
      '<div class="sh-body dk-draw-body">'+
        '<div class="dk-draw-tools">'+
          '<span class="dk-draw-pens" role="group" aria-label="色">'+[['#D62828', '赤'], ['#005BAC', '青']].map(function(c){
            return '<button class="dk-pen'+(d.color === c[0] ? ' on' : '')+'" data-dkpen="'+c[0]+'" style="--pen:'+c[0]+'" aria-pressed="'+(d.color === c[0])+'"><i></i>'+c[1]+'</button>'; }).join('')+'</span>'+
          '<span class="dk-draw-w" role="group" aria-label="太さ">'+[[3, '細'], [5, '中'], [9, '太']].map(function(w){
            return '<button class="dk-pw'+(d.width === w[0] ? ' on' : '')+'" data-dkpw="'+w[0]+'" aria-pressed="'+(d.width === w[0])+'"><i style="width:'+(w[0] * 2)+'px;height:'+(w[0] * 2)+'px"></i>'+w[1]+'</button>'; }).join('')+'</span>'+
          '<span class="dk-draw-sp"></span>'+
          '<button class="btn ghost small dk-finger'+(d.finger ? ' on' : '')+'" data-dkfinger="1" aria-pressed="'+(d.finger ? 'true' : 'false')+'" title="ペンかマウスで書きます。指で書くには入にしてください">指でも書く</button>'+
          '<button class="btn ghost small" data-dkundo="1"'+(cnt(i) ? '' : ' disabled')+'>ひとつ戻す</button>'+
          '<button class="btn ghost small" data-dkclear="1"'+(cnt(i) ? '' : ' disabled')+'>このページを消す</button>'+
        '</div>'+
        '<div class="dk-draw-stage">'+
          '<img class="dk-draw-img" alt="'+esc(r.label)+' のノート '+(i + 1)+'ページ目" src="'+esc(photo(r, i))+'" draggable="false">'+
          '<canvas class="dk-draw-cv" data-dkcv="'+i+'" aria-label="ここに書く"></canvas>'+
          (n > 1 ? '<button class="dk-pg prev" data-dkdrawpg="-1" aria-label="前のページ"'+(i <= 0 ? ' disabled' : '')+'>‹</button>'+
                   '<button class="dk-pg next" data-dkdrawpg="1" aria-label="次のページ"'+(i >= n - 1 ? ' disabled' : '')+'>›</button>' : '')+
        '</div>'+
        '<div class="dk-draw-foot">'+
          '<label class="dk-note"><span class="lbl">ひとこと（生徒に届きます）</span>'+
            '<input id="dkDrawNote" maxlength="200" value="'+esc(r.note || '')+'" placeholder="例：段落の分け方がよくなりました"></label>'+
          '<div class="dk-draw-acts"><span class="tiny" data-dkdrawn="1">'+written+' ページに書き込み'+(n > 1 ? '（全 '+n+' ページを返します）' : '')+'</span>'+
            '<button class="btn" data-dkdrawsend="1"'+(d.busy ? ' disabled' : '')+'>'+(d.busy ? '返しています…' : '返す')+'</button></div>'+
        '</div>'+
      '</div>'+
    '</div>';
}
function drawStroke(ctx, st, from, to){
  ctx.strokeStyle = st.c; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.lineWidth = st.wpx * (st.pen ? (0.55 + 0.9 * (to[2] || 0.5)) : 1);
  ctx.beginPath(); ctx.moveTo(from[0], from[1]); ctx.lineTo(to[0], to[1]); ctx.stroke();
}
function redrawStrokes(ctx, list){
  (list || []).forEach(function(st){
    var pts = st.pts;
    if(pts.length === 1){ drawStroke(ctx, st, pts[0], [pts[0][0] + 0.01, pts[0][1], pts[0][2]]); return; }
    for(var k = 1; k < pts.length; k++) drawStroke(ctx, st, pts[k - 1], pts[k]);
  });
}
function wireDraw(root){
  var d = chk.draw; if(!d) return;
  var r = rowOf(d.sid); if(!r) return;
  var sheet = root.querySelector('.dk-draw'); if(!sheet) return;
  var i = +sheet.querySelector('[data-dkcv]').dataset.dkcv;
  var cv = sheet.querySelector('canvas'), img = sheet.querySelector('.dk-draw-img'), ctx = cv.getContext('2d');
  var setup = function(){
    if(!img.naturalWidth) return;
    cv.width = img.naturalWidth; cv.height = img.naturalHeight;
    ctx.clearRect(0, 0, cv.width, cv.height);
    redrawStrokes(ctx, d.strokes[i]);
    cv.dataset.ready = '1';                  /* 写真の大きさに合わせてから書ける（Safari は読み込みが後から来る） */
  };
  if(img.complete && img.naturalWidth) setup(); else img.onload = setup;
  var refresh = function(){
    var has = (d.strokes[i] || []).length;
    sheet.querySelectorAll('[data-dkundo],[data-dkclear]').forEach(function(b){ b.disabled = !has; });
    var written = Object.keys(d.strokes).filter(function(k){ return (d.strokes[k] || []).length; }).length;
    var n = r.files.length, w = sheet.querySelector('[data-dkdrawn]');
    if(w) w.textContent = written+' ページに書き込み'+(n > 1 ? '（全 '+n+' ページを返します）' : '');
  };
  var active = null, cur = null, last = null;
  var pt = function(e){
    var rc = cv.getBoundingClientRect();
    return [(e.clientX - rc.left) * cv.width / rc.width, (e.clientY - rc.top) * cv.height / rc.height,
            (e.pointerType === 'pen' && e.pressure) ? e.pressure : 0.5];
  };
  cv.addEventListener('pointerdown', function(e){
    /* 書けるのはペン（Apple Pencil など）とマウスだけ。指（touch）は書かない ―― 手のひらが線になる（10-13 本人）。
       ペンの無い端末のために「指でも書く」を切り替えで置く（既定は切。端末ごとに覚える）。入にしていても、ペンで書いた直後の指は無視する */
    if(e.pointerType === 'touch' && (!d.finger || (d.penAt && Date.now() - d.penAt < 1500))) return;
    if(active !== null || !cv.width || !cv.dataset.ready) return;
    e.preventDefault();
    try{ cv.setPointerCapture(e.pointerId); }catch(err){}
    active = e.pointerId;
    if(e.pointerType === 'pen') d.penAt = Date.now();
    var rc = cv.getBoundingClientRect();
    cur = {c:d.color, w:d.width, wpx:d.width * cv.width / Math.max(1, rc.width), pen:e.pointerType === 'pen', pts:[pt(e)]};
    (d.strokes[i] = d.strokes[i] || []).push(cur);
    last = cur.pts[0];
    drawStroke(ctx, cur, last, [last[0] + 0.01, last[1], last[2]]);
  });
  cv.addEventListener('pointermove', function(e){
    if(e.pointerId !== active || !cur) return;
    e.preventDefault();
    var evs = (e.getCoalescedEvents ? e.getCoalescedEvents() : null) || [e];
    if(!evs.length) evs = [e];
    evs.forEach(function(ev){ var p = pt(ev); drawStroke(ctx, cur, last, p); cur.pts.push(p); last = p; });
  });
  var end = function(e){
    if(e.pointerId !== active) return;
    active = null; cur = null; last = null;
    if(d.penAt) d.penAt = Date.now();
    refresh();
  };
  cv.addEventListener('pointerup', end); cv.addEventListener('pointercancel', end);
  cv.addEventListener('lostpointercapture', function(){ if(active !== null){ active = null; cur = null; refresh(); } });
  sheet.querySelectorAll('[data-dkpen]').forEach(function(b){
    b.onclick = function(){ d.color = b.dataset.dkpen; sheet.querySelectorAll('[data-dkpen]').forEach(function(x){ var on = x === b; x.classList.toggle('on', on); x.setAttribute('aria-pressed', on); }); };
  });
  var fb = sheet.querySelector('[data-dkfinger]');
  if(fb) fb.onclick = function(){
    d.finger = !d.finger; fb.classList.toggle('on', d.finger); fb.setAttribute('aria-pressed', d.finger ? 'true' : 'false');
    try{ localStorage.setItem('tube.draw.finger', d.finger ? '1' : ''); }catch(err){}
    toast(d.finger ? '指でも書けるようにしました（手のひらが線になることがあります）' : 'ペンかマウスだけで書きます');
  };
  sheet.querySelectorAll('[data-dkpw]').forEach(function(b){
    b.onclick = function(){ d.width = +b.dataset.dkpw; sheet.querySelectorAll('[data-dkpw]').forEach(function(x){ var on = x === b; x.classList.toggle('on', on); x.setAttribute('aria-pressed', on); }); };
  });
  var undo = sheet.querySelector('[data-dkundo]');
  if(undo) undo.onclick = function(){ (d.strokes[i] || []).pop(); setup(); refresh(); };
  var clear = sheet.querySelector('[data-dkclear]');
  if(clear) clear.onclick = function(){ d.strokes[i] = []; setup(); refresh(); };
  sheet.querySelectorAll('[data-dkdrawpg]').forEach(function(b){
    b.onclick = function(){ d.page = Math.max(0, Math.min(r.files.length - 1, i + (+b.dataset.dkdrawpg))); render(); };
  });
  root.querySelectorAll('[data-dkdrawshut]').forEach(function(b){ b.onclick = function(){ chk.draw = null; render(); }; });
  var send = sheet.querySelector('[data-dkdrawsend]');
  if(send) send.onclick = function(){ sendDraw(sheet); };
}
/* 全ページを原寸で合成して JPEG にし、いまの「添削を返す」と同じ道で返す */
async function sendDraw(sheet){
  var d = chk.draw; if(!d || d.busy) return;
  var r = rowOf(d.sid); if(!r) return;
  var note = (sheet.querySelector('#dkDrawNote') || {}).value || r.note || '';
  d.busy = true; render();
  try{
    var files = [];
    for(var k = 0; k < r.files.length; k++){
      var im = await new Promise(function(res, rej){
        var x = new Image(); x.onload = function(){ res(x); }; x.onerror = function(){ rej(new Error('load')); }; x.src = photo(r, k);
      });
      var c = document.createElement('canvas'); c.width = im.naturalWidth; c.height = im.naturalHeight;
      var cx = c.getContext('2d'); cx.drawImage(im, 0, 0); redrawStrokes(cx, d.strokes[k]);
      var u = c.toDataURL('image/jpeg', 0.86);
      files.push({type:'image/jpeg', b64:u.slice(u.indexOf(',') + 1)});
    }
    if(files.reduce(function(n, f){ return n + f.b64.length; }, 0) > 11 * 1024 * 1024) throw new Error('大きすぎます。ページを減らしてください');
    var got = await srv().returnFor(r.head, d.sid, files, note);
    if(!got || got.error) throw new Error((got && got.error) || '返せませんでした');
    toast('添削を返しました。生徒の「先生から」に出ます');
    chk.draw = null; chk.showRet = true; chk.page = 0;
    chk.data = undefined; chk.want = null; loadCheck();
  }catch(e){ toast(e.message || '返せませんでした'); if(chk.draw) chk.draw.busy = false; }
  render();
}

/* ------------------------------------------------------------
   対面採点（なぞるだけ採点）―― 教室でノートを見ながら、ID の行をなぞって 1〜5 を付ける

   生徒は、ノートのページの上に自分の ID（s-042）を書いてくる。講師は、その ID の行の帯を
   指（かマウス）で左右になぞるだけ。離したところの数が付く。押すだけでも付く。
   写真の採点（上の viewCheck）と、同じ宿題・同じ評価（rateBundle）。画面だけが違う。
   ------------------------------------------------------------ */
function faceMode(){
  if(chk.mode) return chk.mode;
  return courseUse() < 2 ? 'face' : 'photo';      /* 写真の提出を使っていないコースは、はじめから対面 */
}
function modeTabs(){
  var md0 = faceMode();
  return '<div class="fc-modes" role="tablist" aria-label="採点のしかた">'+
    '<button role="tab" aria-selected="'+(md0 === 'photo')+'" class="'+(md0 === 'photo' ? 'on' : '')+'" data-fcmode="photo">写真で採点</button>'+
    '<button role="tab" aria-selected="'+(md0 === 'face')+'" class="'+(md0 === 'face' ? 'on' : '')+'" data-fcmode="face">対面で採点</button></div>';
}
function faceTrack(r, v){
  var val = (v === undefined) ? (r.v >= 1 ? r.v : 0) : v;
  return '<div class="fc-track v'+val+'" data-fctrack="'+esc(r.sid)+'" role="slider" tabindex="0" aria-label="'+esc(seatNo(r.label))+' の評価" '+
      'aria-valuemin="0" aria-valuemax="5" aria-valuenow="'+val+'" aria-valuetext="'+(val ? val+' '+WORD[val] : 'まだ')+'">'+
    [1, 2, 3, 4, 5].map(function(n){ return '<i class="'+(n <= val ? 'on' : '')+'"><b class="num">'+n+'</b></i>'; }).join('')+'</div>';
}
function faceRow(r){
  var val = r.v >= 1 ? r.v : 0;
  return '<div class="fc-row'+(val ? ' rated' : '')+'" data-fcrow="'+esc(r.sid)+'">'+
    '<span class="fc-id num">'+esc(seatNo(r.label))+'</span>'+
    faceTrack(r)+
    '<span class="fc-word">'+(val ? WORD[val] : (r.files.length ? '写真あり' : ''))+'</span>'+
    '<span class="fc-clear"><button class="dk-wmini'+(r.worry ? ' on' : '')+'" data-fcworry="'+esc(r.sid)+'" aria-pressed="'+(!!r.worry)+'">心配</button>'+
    (val ? '<button class="lnk" data-fcclear="'+esc(r.sid)+'">消す</button>' : '')+'</span>'+
  '</div>';
}
function faceRowsHtml(){
  var rows = chk.data.rows.slice().sort(function(a, b){ return seatNo(a.label) < seatNo(b.label) ? -1 : 1; });
  var q = String(chk.find || '').replace(/[^0-9a-z-]/gi, '').toLowerCase();
  var shown = q ? rows.filter(function(r){ return seatNo(r.label).toLowerCase().indexOf(q) >= 0; }) : rows;
  return shown.length ? shown.map(faceRow).join('') : '<div class="empty">その ID の生徒は、このコースにいません。</div>';
}
function faceHtml(){
  return '<div class="fc">'+
    '<div class="fc-tool"><label for="fcFind">ID でしぼる</label>'+
      '<input id="fcFind" class="num" inputmode="numeric" autocomplete="off" autocapitalize="none" maxlength="8" value="'+esc(chk.find || '')+'">'+
      '<span class="tiny">ノートの上の ID の数字を入れると、その生徒だけになります。帯を左右になぞると、離したところの数が付きます。</span></div>'+
    '<div class="fc-rows">'+faceRowsHtml()+'</div>'+
    '<div class="dk-legend tiny">'+[5, 4, 3, 2, 1].map(function(n){ return '<span><b class="dk-v v'+n+'">'+n+'</b> '+WORD[n]+'</span>'; }).join('')+'</div>'+
  '</div>';
}
function faceValue(track, x){
  var b = track.getBoundingClientRect();
  var v = Math.floor((x - b.left) / b.width * 5) + 1;
  return Math.max(1, Math.min(5, v));
}
function facePaint(track, v){
  track.className = 'fc-track v' + v;
  track.setAttribute('aria-valuenow', v);
  [].forEach.call(track.children, function(c, i){ c.classList.toggle('on', i < v); });
  var row = track.parentNode, w = row && row.querySelector('.fc-word');
  if(w) w.textContent = v ? WORD[v] : '';
}
function faceRate(r, v){
  var old = r.v;
  if(old === v) return;
  r.v = v;
  today = undefined;
  var m = document.getElementById('main');
  var row = m && m.querySelector('[data-fcrow="'+(window.CSS && CSS.escape ? CSS.escape(r.sid) : r.sid)+'"]');
  if(row){ var tmp = document.createElement('div'); tmp.innerHTML = faceRow(r); row.parentNode.replaceChild(tmp.firstChild, row); wireFace(m); }
  var st = document.getElementById('dkStats'); if(st) st.innerHTML = statsHtml(recount());
  srv().rateBundle(chk.data.course.key, chk.data.lesson.n, r.sid, v).then(function(res){
    if(res.ok){ over = undefined; ins.course = {}; stuCache = {}; sugCache = {}; return; }
    r.v = old; toast(res.error); render();
  });
}
function wireFace(m){
  m.querySelectorAll('[data-fcworry]').forEach(function(b){ b.onclick = function(){ worry(rowOf(b.dataset.fcworry)); }; });
  m.querySelectorAll('[data-fcmode]').forEach(function(b){
    b.onclick = function(){ chk.mode = b.dataset.fcmode; render(); };
  });
  var f = m.querySelector('#fcFind');
  if(f && !f._wired){
    f._wired = true;
    f.oninput = function(){
      /* 行だけを描き直す。入力欄はそのまま（打っている途中で、カーソルが飛ばない） */
      chk.find = f.value;
      var box = m.querySelector('.fc-rows');
      if(box){ box.innerHTML = faceRowsHtml(); wireFace(m); }
    };
  }
  m.querySelectorAll('[data-fctrack]').forEach(function(t){
    if(t._wired) return; t._wired = true;
    var r = rowOf(t.dataset.fctrack), live = null;
    t.addEventListener('pointerdown', function(e){
      if(e.button > 0) return;
      live = faceValue(t, e.clientX); facePaint(t, live);
      try{ t.setPointerCapture(e.pointerId); }catch(er){}
      e.preventDefault();
    });
    t.addEventListener('pointermove', function(e){
      if(live === null) return;
      var v = faceValue(t, e.clientX);
      if(v !== live){ live = v; facePaint(t, v); }
    });
    var end = function(e){
      if(live === null) return;
      var v = live; live = null;
      if(e.type === 'pointercancel'){ facePaint(t, r.v >= 1 ? r.v : 0); return; }
      if(e.clientX || e.clientY) v = faceValue(t, e.clientX);
      if(v === r.v) facePaint(t, v);
      faceRate(r, v);
    };
    t.addEventListener('pointerup', end);
    t.addEventListener('pointercancel', end);
    t.addEventListener('keydown', function(e){
      var cur = r.v >= 1 ? r.v : 0;
      if(e.key >= '1' && e.key <= '5'){ faceRate(r, +e.key); e.preventDefault(); }
      else if(e.key === 'ArrowRight' && cur < 5){ faceRate(r, cur + 1); e.preventDefault(); }
      else if(e.key === 'ArrowLeft' && cur > 1){ faceRate(r, cur - 1); e.preventDefault(); }
      else if(e.key === '0' || e.key === 'Backspace'){ faceRate(r, null); e.preventDefault(); }
    });
  });
  m.querySelectorAll('[data-fcclear]').forEach(function(b){
    b.onclick = function(){ var r = rowOf(b.dataset.fcclear); if(r) faceRate(r, null); };
  });
}

function viewCheck(m){
  bindKeys();
  var back = '<div class="dk-crumb t-full"><button class="backpill" data-dkback="1">'+ui().backIcon+'今日やること</button></div>';
  if(!chk.key){ return ui().go('hw', 'pop'); }
  if(chk.data === undefined) loadCheck();
  var d = chk.data;
  if(!d){
    m.innerHTML = back + '<div class="empty t-full">写真を読み込んでいます…</div>';
    return wireCheck(m);
  }
  if(d.error){
    m.innerHTML = back + '<div class="empty t-full">この宿題を読み込めませんでした。</div>';
    return wireCheck(m);
  }
  var L = d.lesson;
  var courseSel = '<label class="dk-pickc"><span class="lbl">コース</span><select id="dkCourse">'+
    (d.courses || []).map(function(c){
      return '<option value="'+esc(c.key)+'"'+(c.key === d.course.key ? ' selected' : '')+'>'+
        esc(c.name)+(c.todo ? '（未評価 '+c.todo+'）' : '')+'</option>';
    }).join('') +'</select></label>';
  /* 回の札を種類でしぼる：普段の宿題と、漢字テスト・計算テスト・作文・過去問の提出箱を別々に見る（2026-10-11 本人）。
     種類が2つ以上あるときだけ札を出す。いま見ている回は、しぼっても残す。 */
  /* 回の種類：授業計画の回は「宿題」（label は教材の呼び名「第6回」なので使わない）、提出箱はその種類（無ければ「提出箱」） */
  var kindOf = function(l){ return l.quiz ? (l.kind || '提出箱') : '宿題'; };
  var kinds = [];
  (d.lessons || []).forEach(function(l){ var k = kindOf(l); if(kinds.indexOf(k) < 0) kinds.push(k); });
  var shown = (d.lessons || []).filter(function(l){ return !chk.kind || kindOf(l) === chk.kind || (L && l.n === L.n); });
  var kindBar = kinds.length > 1
    ? '<div class="dk-kinds" role="group" aria-label="種類でしぼる">'+[['', 'すべて']].concat(kinds.map(function(k){ return [k, k]; })).map(function(kv){
        return '<button class="dk-kind'+((chk.kind || '') === kv[0] ? ' on' : '')+'" data-dkkind="'+esc(kv[0])+'" aria-pressed="'+((chk.kind || '') === kv[0])+'">'+esc(kv[1])+'</button>';
      }).join('')+'</div>'
    : '';
  var seg = (d.lessons || []).length
    ? '<div class="dk-seg"><span class="lbl">回</span>'+kindBar+'<div class="dk-segs" role="tablist" aria-label="何回目の宿題か">'+
      shown.map(function(l){
        var on = L && l.n === L.n;
        return '<button role="tab" aria-selected="'+(on ? 'true' : 'false')+'" class="dk-segb'+(on ? ' on' : '')+
          '" data-dkn="'+l.n+'"><b>'+esc(ushort(l))+'</b><span>'+esc(uname(l) ? l.topic : '')+(l.picked ? '（'+l.total+'人に）' : '')+'</span>'+
          (l.todo ? '<em class="num">'+l.todo+'</em>' : '<em class="ok" aria-label="評価ずみ">✓</em>')+'</button>';
      }).join('') +'</div></div>'
    : '';
  if(!L){
    m.innerHTML = back + '<div class="dk-check t-full"><div class="dk-sel">'+courseSel+'</div>'+
      '<div class="h-card empty">'+esc(d.course.name)+' には、期限が来た紙の宿題がまだありません。</div></div>';
    return wireCheck(m);
  }
  var st = d.stats || recount();
  var next = nextTask();
  var fin = !st.todo
    ? '<div class="dk-complete"><span><b>この回のチェックは完了です</b>'+
        (st.missing ? '（未提出 '+st.missing+'人。授業で声をかけましょう）' : '')+'</span>'+
      (next ? '<button class="btn small" data-dkcheck="'+esc(next.key)+'|'+next.n+'">次のチェック：'+esc(next.name)+' '+esc(ushort(next))+'（'+next.todo+'人）→</button>'
            : '<button class="btn small ghost" data-dkback="1">今日やることへ戻る</button>')+'</div>'
    : '';
  var sjid = sjOfKey(chk.key); ui().subject(sjid);
  /* 見本 T04：パンくずは見出しと同じ行、コースと回は次の1行、提出の数は左の紙の中。上を低くして、
     紙（写真・評価・ひとこと・添削）が下にスクロールせずに1画面に収まるように（2026-10-11 本人）。 */
  var legend = '<div class="dk-legend tiny"><span><i class="dk-dot"></i> 未評価</span><span><b class="dk-v v4">4</b> 評価ずみ</span>'+
        '<span class="dk-dash">未提出</span><span><span class="dk-pers">個別</span> この生徒だけの宿題あり</span></div>';
  m.innerHTML =
    '<div class="dk-head t-full'+ui().sjClass(sjid)+'"><div class="dk-headl"><button class="backpill" data-dkback="1">'+ui().backIcon+'今日やること</button>'+
      '<div class="dk-headt"><h1 class="dk-title">'+ui().subjIcon(sjid, 28, 2.2)+esc(d.course.name)+'<span class="dk-x">／</span>'+esc(utext(L))+'</h1>'+
      '<span class="dk-sub"><span class="num">'+esc(md(L.dueAt))+'</span>〆 の宿題チェック</span></div></div>'+modeTabs()+'</div>'+
    '<div class="dk-check t-full">'+
      '<div class="dk-sel">'+courseSel+seg+'</div>'+
      (courseUse() < 2 ? '<p class="tiny dk-usenote">写真の提出は使っていないコースです（「'+USE_WORDS[courseUse()]+'」までの導入）。紙で評価するなら、ノートを見てここで付けられます。</p>' : '')+
      (faceMode() === 'face' ? '<div class="dk-stats" id="dkStats">'+statsHtml(st)+'</div>' + faceHtml() + '</div>' : '')+
      (faceMode() === 'face' ? '' :
      fin+
      '<div class="dk-body">'+
        '<div class="dk-left">'+
          '<div class="dk-stats" id="dkStats">'+statsHtml(st)+'</div>'+
          '<div class="dk-grid" role="listbox" aria-label="生徒（マウスを乗せると右に大きく出ます）">'+
            d.rows.map(cellHtml).join('') +'</div>'+
          legend+
        '</div>'+
        '<aside class="dk-view" aria-live="polite">'+viewerHtml()+'</aside>'+
      '</div>'+
    '</div>') + (faceMode() === 'face' ? '' : drawSheet());
  wireCheck(m); wireFace(m);
  if(faceMode() !== 'face') wireDraw(m);
  fitCheck();
}

/* 左右を、画面の下まで（それ以上に伸ばさない）。右の紙は写真がその中で伸び縮みし、評価・ひとこと・添削は
   いつも見えている。生徒が多いときは左の格子だけがその中で動く。縦が足りない小さな窓では、今までどおり流す。 */
function fitCheck(){
  var body = document.querySelector('#main .dk-body');
  if(!body) return;
  var wide = !!(window.matchMedia && window.matchMedia('(min-width:700px)').matches);
  if(!wide){ body.style.height = ''; return; }
  var top = body.getBoundingClientRect().top + (window.scrollY || window.pageYOffset || 0);
  var h = window.innerHeight - top - 16;
  body.style.height = h >= 420 ? h + 'px' : '';
}
if(typeof window !== 'undefined') window.addEventListener('resize', function(){ fitCheck(); });

function narrow(){ return !!(window.matchMedia && window.matchMedia('(max-width:980px)').matches); }

/* 狭い画面ではノートがマスの上にある。選んだ子のノートを、いつも上端から見せる。 */
function showViewer(){
  var v = document.querySelector('.dk-view');
  if(v && v.scrollIntoView) v.scrollIntoView({block:'start', behavior:'smooth'});
}

function wireCell(c){
  var sid = c.dataset.dksid;
  c.onclick = function(){
    setFocus(sid, false);
    if(narrow()) showViewer();
  };
  c.onfocus = function(){ if(chk.focus !== sid) setFocus(sid, false); };
  /* **少し止まってから切り替える。** マスから右の評価ボタンへマウスを動かすと、
     途中のマスを横切る ―― すぐ切り替えると、押すつもりの子が別の子に変わってしまう。 */
  c.onmouseenter = function(){
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(function(){ if(chk.focus !== sid) setFocus(sid, false); }, 150);
  };
  c.onmouseleave = function(){ clearTimeout(hoverTimer); };
}

function wireViewer(root){
  root.querySelectorAll('[data-dkworry]').forEach(function(b){ b.onclick = function(){ worry(rowOf(chk.focus)); }; });
  root.querySelectorAll('[data-dkrate]').forEach(function(b){
    b.onclick = function(){
      var r = rowOf(chk.focus);
      if(!r) return;
      var v = b.dataset.dkrate === 'clear' ? null : +b.dataset.dkrate;
      rate(r, v);
      /* 狭い画面（マウスを乗せられない）では、押したら次の「未評価」の子へ進む。
         マスへ戻って選び直す手間を1人ぶんずつ省く。次の子のノートは上端から見せる（マスへは巻かない）。 */
      if(v !== null && narrow() && chk.data.rows.some(isTodo)) setTimeout(function(){ nextTodo(false); showViewer(); }, 350);
    };
  });
  root.querySelectorAll('[data-dkpage]').forEach(function(b){
    b.onclick = function(){ turn(+b.dataset.dkpage); };
  });
  var note = root.querySelector('#dkNote');
  if(note){
    note.onchange = function(){ saveNote(note.value); };
  }
  root.querySelectorAll('[data-dkshow]').forEach(function(b){
    b.onclick = function(){ chk.showRet = (b.dataset.dkshow === 'returned'); chk.page = 0; paintFocus(false); };
  });
  root.querySelectorAll('[data-dkdraw]').forEach(function(b){ b.onclick = function(){ openDraw(b.dataset.dkdraw); }; });
  root.querySelectorAll('[data-dkscan],[data-dkreturn]').forEach(function(x){
    x.onchange = function(){
      var list = Array.prototype.slice.call(x.files || []);
      x.value = '';
      dkUpload(x.dataset.dkscan ? 'scan' : 'return', x.dataset.dkscan || x.dataset.dkreturn, list);
    };
  });
  var img = root.querySelector('.dk-vimg img');
  if(img){
    img.onerror = function(){
      var box = root.querySelector('.dk-vimg');
      if(box) box.innerHTML = '<p class="dk-nophoto">写真を読み込めませんでした（通信を確かめてください）</p>';
    };
  }
}

function wireCheck(m){
  m.querySelectorAll('[data-dkback]').forEach(function(b){
    b.onclick = function(){ today = undefined; ui().go('hw', 'pop'); };
  });
  m.querySelectorAll('[data-dkcheck]').forEach(function(b){
    b.onclick = function(){ var p = b.dataset.dkcheck.split('|'); openCheck(p[0], +p[1]); };
  });
  var sel = m.querySelector('#dkCourse');
  if(sel) sel.onchange = function(){ openCheck(sel.value, null); };
  m.querySelectorAll('[data-dkn]').forEach(function(b){
    b.onclick = function(){ openCheck(chk.key, +b.dataset.dkn); };
  });
  m.querySelectorAll('[data-dkkind]').forEach(function(b){
    b.onclick = function(){ chk.kind = b.dataset.dkkind || null; ui().render(); };
  });
  m.querySelectorAll('.dk-cell').forEach(wireCell);
  var v = m.querySelector('.dk-view');
  if(v) wireViewer(v);
}

function paintFocus(scroll){
  var m = document.getElementById('main');
  if(!m) return;
  var v = m.querySelector('.dk-view');
  if(v){ v.innerHTML = viewerHtml(); wireViewer(v); }
  m.querySelectorAll('.dk-cell').forEach(function(c){
    var on = c.dataset.dksid === chk.focus;
    c.classList.toggle('focus', on);
    c.setAttribute('aria-selected', on ? 'true' : 'false');
    if(on && scroll && c.scrollIntoView) c.scrollIntoView({block:'nearest'});
  });
}

function paintRow(sid){
  var m = document.getElementById('main');
  var old = m && m.querySelector('.dk-cell[data-dksid="'+(window.CSS && CSS.escape ? CSS.escape(sid) : sid)+'"]');
  var r = rowOf(sid);
  if(!old || !r) return;
  var tmp = document.createElement('div');
  tmp.innerHTML = cellHtml(r);
  var nu = tmp.firstChild;
  old.parentNode.replaceChild(nu, old);
  wireCell(nu);
  var st = document.getElementById('dkStats');
  if(st) st.innerHTML = statsHtml(recount());
}

function setFocus(sid, scroll){
  chk.focus = sid;
  chk.page = 0;
  paintFocus(scroll);
}

function turn(d){
  var r = rowOf(chk.focus);
  if(!r || !pagesOf(r).length) return;
  var np = chk.page + d;
  if(np < 0 || np >= pagesOf(r).length) return;     // 端では止まる（次の子へは↓）
  chk.page = np;
  paintFocus(false);
}

function move(d){
  var rows = (chk.data && chk.data.rows) || [];
  if(!rows.length) return;
  var i = -1;
  for(var k = 0; k < rows.length; k++){ if(rows[k].sid === chk.focus){ i = k; break; } }
  var j = Math.max(0, Math.min(rows.length - 1, i + d));
  if(j !== i) setFocus(rows[j].sid, true);
}

function nextTodo(scroll){
  var rows = (chk.data && chk.data.rows) || [];
  var i = 0;
  for(var k = 0; k < rows.length; k++){ if(rows[k].sid === chk.focus){ i = k; break; } }
  for(var s = 1; s <= rows.length; s++){
    var r = rows[(i + s) % rows.length];
    if(isTodo(r)) return setFocus(r.sid, scroll !== false);
  }
  toast('未評価の写真は、この回にはもうありません');
}

function rate(r, v){
  var old = r.v;
  if(old === v) return;
  r.v = v;
  paintRow(r.sid);
  paintFocus(false);
  today = undefined;
  srv().rateBundle(chk.data.course.key, chk.data.lesson.n, r.sid, v).then(function(res){
    if(!res.ok){
      r.v = old;
      paintRow(r.sid); paintFocus(false);
      return toast(res.error);
    }
    over = undefined; ins.course = {}; stuCache = {}; sugCache = {};
    if(!chk.data) return;                          // 読み込み直しの最中（添削を返した直後など）
    var st = recount();
    if(!st.todo && v !== null) render();          // 完了の帯と「次のチェック」を出す
  });
}

/* 理解が心配 ―― 評価とは別の印。生徒には見えない。キーの 9。 */
function worry(r){
  if(!r) return;
  if(!(r.v >= 1)) return toast('先に 1〜5 の評価を付けてください');
  r.worry = !r.worry;
  paintRow(r.sid); paintFocus(false);
  srv().rateBundle(chk.data.course.key, chk.data.lesson.n, r.sid, undefined, undefined, r.worry).then(function(res){
    if(!res.ok){ r.worry = !r.worry; paintRow(r.sid); paintFocus(false); toast(res.error); return; }
    over = undefined; ins.course = {}; stuCache = {};
  });
}

function saveNote(text){
  var r = rowOf(chk.focus);
  if(!r || !r.files.length) return;
  if((r.note || '') === text) return;
  var old = r.note;
  r.note = text;
  srv().rateBundle(chk.data.course.key, chk.data.lesson.n, r.sid, undefined, text).then(function(res){
    if(!res.ok){ r.note = old; return toast(res.error); }
    toast('ひとことを残しました');
  });
}

var keysBound = false;
function bindKeys(){
  if(keysBound) return;
  keysBound = true;
  document.addEventListener('keydown', function(e){
    if(chk.draw) return;                     /* 赤を入れている最中は 1〜5 や矢印を効かせない */
    if(S().view !== 'check' || !chk.data || !chk.data.rows) return;
    var tag = (e.target && e.target.tagName) || '';
    if(tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'){
      if(e.key === 'Enter' && e.target.id === 'dkNote'){ e.preventDefault(); e.target.blur(); }
      if(e.key === 'Escape') e.target.blur();
      return;
    }
    if(e.metaKey || e.ctrlKey || e.altKey) return;
    var r = rowOf(chk.focus);
    if(e.key === 'ArrowRight' || e.key === 'ArrowLeft'){
      e.preventDefault();
      return turn(e.key === 'ArrowRight' ? 1 : -1);
    }
    if(e.key === 'ArrowDown' || e.key === 'ArrowUp'){
      e.preventDefault();
      return move(e.key === 'ArrowDown' ? 1 : -1);
    }
    if(/^[1-5]$/.test(e.key)){
      if(r){ e.preventDefault(); rate(r, +e.key); }
      return;
    }
    if(e.key === '9'){                        /* 理解が心配（講師だけの印） */
      if(r){ e.preventDefault(); worry(r); }
      return;
    }
    if(e.key === '0' || e.key === 'Backspace' || e.key === 'Delete'){
      if(r && r.v >= 1){ e.preventDefault(); rate(r, null); }
      return;
    }
    /* Enter は、何も押していないとき（本文）かマスの上でだけ「未評価の子へ」。
       ボタンの上の Enter は、そのボタンを押す（ふつうの動き）に任せる。 */
    if(e.key === 'Enter' && (e.target === document || e.target === document.body ||
                             /dk-cell/.test(e.target.className || ''))){
      e.preventDefault();
      nextTodo();
    }
  });
}

/* ============================================================
   3. 成績 ―― コースの診断
   ============================================================ */
var over = undefined;         /* 担当コースの札（/api/insight/overview） */
var ins = {mode:'all', key:null, n:null, thr:50, course:{}, sheet:null};
var stuCache = {}, sugCache = {};

function loadOverview(){
  if(over === null || !srv()) return;
  over = null;
  srv().insightOverview().then(function(got){ over = got || {courses:[], error:true}; render(); });
}
function loadCourse(key){
  if(ins.course[key] === null) return;
  ins.course[key] = null;
  srv().insightCourse(key).then(function(got){ ins.course[key] = got || {error:true}; render(); });
}
function forget(key){
  over = undefined; ins.course[key] = undefined; stuCache = {}; sugCache = {}; today = undefined;
}

function openCourse(key){
  ins.mode = 'course'; ins.key = key; ins.n = null; ins.sheet = null;
  ui().go('roster', 'pop');
}

/* コースの並びは1つだけ（名前の順）。札の列もカードも同じ並び ―― 見る場所を毎回変えない。 */
function sortedCourses(list){
  return (list || []).slice().sort(function(a, b){ return String(a.name).localeCompare(String(b.name), 'ja'); });
}
function chips(){
  var cs = sortedCourses(over && over.courses);
  return '<div class="t-chips t-full ik-chips" role="tablist" aria-label="コース">'+
    '<button class="t-chip" data-ikall="1" aria-pressed="'+(ins.mode === 'all' ? 'true' : 'false')+'">すべて</button>'+
    cs.map(function(c){
      var on = ins.mode === 'course' && ins.key === c.key;
      return '<button class="t-chip'+(c.flag ? ' flag' : '')+'" data-ikcourse="'+esc(c.key)+'" aria-pressed="'+
        (on ? 'true' : 'false')+'">'+esc(c.name)+(c.flag ? '<i class="t-chipdot"></i>' : '')+'</button>';
    }).join('') +'</div>';
}

function viewInsight(m){
  if(over === undefined) loadOverview();
  if(ins.mode === 'course' && ins.key) return courseView(m);
  allView(m);
}

/* ---- すべて ---- */
function allView(m){
  var h = ui().pageHead('成績', false);
  if(!over){
    m.innerHTML = h + '<div class="empty t-full">担当コースの理解度をしらべています…</div>';
    return wireInsight(m);
  }
  var cs = sortedCourses(over.courses);
  if(!cs.length){
    m.innerHTML = h + '<div class="empty t-full">担当しているコースがありません。</div>';
    return wireInsight(m);
  }
  var flagged = cs.filter(function(c){ return c.flag; });
  /* テコ入れ候補は並べ替えずに、名前だけを先に挙げる（押すとそのコースへ）。 */
  var lead = '<div class="ik-lead t-full">'+
    (flagged.length
      ? '<b>テコ入れ候補 <span class="num">'+flagged.length+'</span>コース</b><span class="ik-leadlist">'+ flagged.map(function(c){
          return '<button class="lnk" data-ikcourse="'+esc(c.key)+'">'+esc(c.name)+'</button>'; }).join('') +'</span>'
      : '<b>どのコースも、直近の単元は理解度70%以上です</b>')+
    '</div>';
  m.innerHTML = h + chips() + lead +
    '<div class="h-grid t-full ik-grid">'+ cs.map(courseCard).join('') +'</div>' + sheets();
  wireInsight(m);
}

/* 札1枚 ―― 大きな数（最新の単元の理解度）と直近の推移の折れ線を1行に。単元名は最新の1つだけ、図の下に。
   提出は輪、理解度50%以下は1人1点。**図に数字を振らない・横軸に第何回を書かない**（CLAUDE.md）。 */
var RECENT_N = 8;          /* 図に並べる単元の数（6週以上が見えるように） */
function courseCard(c){
  var V = global.TubeViz;
  var pts = V.series(c.units, 'und', RECENT_N), L = V.latestOf(pts);
  var sub = V.pct(c.sub), low = Math.max(0, +c.low50 || 0), total = Math.max(0, +c.students || 0);
  var say = c.name + '。' + (L ? V.unitText(L)+' の理解度 '+L.v+'%' : '理解度はまだありません') +
    '。提出 '+(sub === null ? 'なし' : sub+'%')+'。理解度50%以下 '+low+'人（'+total+'人中）'+(c.flag ? '。テコ入れ候補' : '');
  return '<button class="h-card ik-card'+(c.flag ? ' flag' : '')+ui().sjClass(sjOfKey(c.key))+'" data-ikcourse="'+esc(c.key)+'" aria-label="'+esc(say)+'">'+
    '<span class="ik-top"><span class="ik-name">'+ui().subjIcon(sjOfKey(c.key), 20)+esc(c.name)+'</span>'+
      (c.personal ? '<span class="ik-pers">個別 '+c.personal+'人</span>' : '')+
      (c.flag ? '<span class="ik-flag">テコ入れ候補</span>' : '')+'</span>'+
    '<span class="ik-mid">'+
      '<span class="ik-big"><span class="num ik-n '+V.tone(L && L.v)+'">'+(L ? L.v : '―')+'</span><i>%</i></span>'+
      V.lineChart({slots:RECENT_N, lines:[{pts:pts, cls:'und'}]})+
    '</span>'+
    '<span class="ik-unit">'+(L ? esc(L.topic || V.unitName(L)) : 'まだ根拠がありません')+'</span>'+
    '<span class="ik-facts">'+
      '<span class="ik-fact">'+V.ring(sub)+'<span>提出 <b class="num">'+(sub === null ? '―' : sub+'%')+'</b></span></span>'+
      '<span class="ik-fact">'+V.dots(total, low, 30)+'<span>50%以下</span></span>'+
    '</span>'+
  '</button>';
}

/* ---- コース ---- */
function courseView(m){
  var key = ins.key;
  if(ins.course[key] === undefined) loadCourse(key);
  var c = ins.course[key];
  var name = c && c.course ? c.course.name : (((over && over.courses) || []).filter(function(x){ return x.key === key; })[0] || {}).name || '';
  var top = '<div class="ik-back t-full"><button class="backpill" data-ikall="1">'+ui().backIcon+'すべてのコース</button></div>';
  var h = ui().pageHead('成績', false);
  if(!c){
    m.innerHTML = h + chips() + top + '<div class="empty t-full">'+esc(name)+' の理解度をしらべています…</div>';
    return wireInsight(m);
  }
  if(c.error){
    m.innerHTML = h + chips() + top + '<div class="empty t-full">このコースを読み込めませんでした。</div>';
    return wireInsight(m);
  }
  var units = (c.units || []).slice(-RECENT_N);
  var nsel = units.some(function(u){ return u.n === ins.n; }) ? ins.n : null;
  var stus = c.students || [];
  var nx = c.next || {};
  var sjid = sjOfKey(key);
  ui().subject(sjid);
  var intro = '<div class="ik-chead t-full'+ui().sjClass(sjid)+'">'+
    '<div><h3>'+ui().subjIcon(sjid, 28, 2.2)+esc(c.course.name)+'</h3>'+
      '<p class="tiny"><span class="num">'+stus.length+'</span>人 ・ 次の授業 '+esc(utext(nx))+
      (nx.date ? '（'+esc(mdSW(nx.date))+'）' : '')+'。個別の宿題は、この回から効きます</p></div>'+
    '<button class="btn small ghost" data-ikimport="1">テスト結果を取り込む</button></div>';

  /* 推移と分布は、広い画面では横に2枚（1枚ずつ横いっぱいでは間のびする）。単元の生徒ごとはその下。 */
  m.innerHTML = h + chips() + top + intro +
    '<div class="ik-pair t-full">'+ trendCard(units, nsel) + histCard(stus) +'</div>'+
    (nsel ? unitDetail(c, nsel) : '')+
    '<div class="ik-pair t-full">'+ lowCard(c, units) + boardCard(c) +'</div>'+
    heatCard(c, units) +
    stuCards(c, units) +
    testsCard(c) +
    sheets();
  wireInsight(m);
}

/* 推移（コースのページ）。理解度の折れ線と、提出率の点線を1枚に。点を押すと、その単元の生徒ごと。
   最新の値は**線の端**に名前つきで置く（図の下に数字の行を作らない）。下は最新の単元名と押し方だけ。 */
function trendCard(units, nsel){
  var V = global.TubeViz;
  var und = V.series(units, 'und', RECENT_N), sub = V.series(units, 'sub', RECENT_N);
  var L = V.latestOf(und);
  var focus = und.some(function(p){ return p.n === nsel; }) ? nsel : (L || {}).n;
  var chart = V.lineChart({slots:RECENT_N, ends:true, focus:focus,
    lines:[{pts:und, cls:'und', name:'理解度'}, {pts:sub, cls:'sub', name:'提出'}],
    point:function(p){
      return 'data-ikunit="'+p.n+'" aria-pressed="'+(nsel === p.n ? 'true' : 'false')+'" '+
        'aria-label="'+V.esc(V.unitText(p)+' 理解度 '+(p.v === null ? 'なし' : p.v+'%'))+'"';
    }});
  return '<div class="card ik-trend">'+
    '<div class="lbl">直近の単元の推移</div>'+
    chart+
    '<div class="ik-cap">'+(L ? '<b>'+esc(V.unitText(L))+'</b>' : '<span>まだ単元がありません</span>')+
      '<span class="tiny">点を押すと、その単元の生徒ごとが下に出ます</span></div>'+
  '</div>';
}

function histCard(stus){
  var vals = stus.map(function(s){ return s.avg; }).filter(has);
  var bins = [0,0,0,0,0,0,0,0,0,0];
  vals.forEach(function(v){ bins[Math.min(9, Math.floor(v / 10))]++; });
  var top = Math.max(1, Math.max.apply(null, bins));
  var thr = ins.thr;
  var below = vals.filter(function(v){ return v <= thr; }).length;
  return '<div class="card ik-hist">'+
    '<div class="ik-hh"><div class="lbl">生徒の理解度の分布（直近5単元の平均）</div>'+
      '<div class="ik-thr" role="group" aria-label="線"><span class="tiny">線</span>'+
      [40, 50, 60, 70].map(function(t){
        return '<button class="pick'+(t === thr ? ' on' : '')+'" data-ikthr="'+t+'" aria-pressed="'+(t === thr)+'">'+t+'%</button>';
      }).join('') +'</div></div>'+
    '<div class="ik-hbars">'+ bins.map(function(n, i){
      var lo = i * 10, low = (lo + 10) <= thr || (lo < thr && thr < lo + 10);
      return '<div class="ik-hb'+(low ? ' lo' : '')+'" title="'+lo+'〜'+(lo + 10)+'%：'+n+'人">'+
        '<span class="num">'+(n || '')+'</span><i style="height:'+(n ? Math.max(6, n / top * 100) : 0)+'%"></i></div>';
    }).join('') +'</div>'+
    /* 目盛りは 0・20・40・60・80・100。10ごとに書くと、狭い画面で 90 と 100 が重なる。 */
    '<div class="ik-hx">'+ bins.map(function(_n, i){ return '<span class="num">'+(i % 2 ? '' : i * 10)+'</span>'; }).join('') +
      '<span class="num">100</span></div>'+
    '<p class="ik-hsum"><b class="num">'+below+'人</b>が理解度'+thr+'%以下です'+
      (vals.length < stus.length ? '（根拠のない生徒 '+(stus.length - vals.length)+'人は数えていません）' : '')+'</p>'+
  '</div>';
}

function weakOf(s, units){
  return units.map(function(u){ return {u:u, c:(s.cells || {})[String(u.n)]}; })
    /* 総復習の回は単元ではない。苦手な単元に数えない（解き直しの先にもしない）。 */
    .filter(function(x){ return !x.u.review && x.c && has(x.c.u) && x.c.u < YELLOW; })
    .sort(function(a, b){ return a.c.u - b.c.u; });
}

function lowCard(c, units){
  var thr = ins.thr;
  var low = (c.students || []).filter(function(s){ return has(s.avg) && s.avg <= thr; })
    .sort(function(a, b){ return a.avg - b.avg; });
  var nx = c.next || {};
  if(!low.length){
    return '<div class="card ik-low"><div class="lbl">理解度が'+thr+'%以下の生徒</div>'+
      '<p class="tiny">いません。線を上げると、次に気にかけたい生徒が出ます。</p></div>';
  }
  return '<div class="card ik-low">'+
    '<div class="ik-lh"><div class="lbl">理解度が'+thr+'%以下の生徒 <span class="num">'+low.length+'</span>人<span class="tiny">苦手な単元（自動）</span></div>'+
      '<div class="ik-bulk"><button class="btn small" data-ikassign="low">宿題を変更する</button>'+
        '<span class="tiny">プリセットから選んで、'+esc(ushort(nx))+'の宿題と一緒に</span></div>'+
    '</div>'+
    low.map(function(s){
      var weak = weakOf(s, units).slice(0, 3);
      return '<div class="ik-lrow">'+
        '<button class="ik-lname" data-ikstu="'+esc(s.sid)+'">'+esc(s.label)+'</button>'+
        '<span class="ik-lavg num y">'+s.avg+'%</span>'+
        '<span class="ik-lweak">'+(weak.length ? weak.map(function(x){
            return '<button class="ik-wchip" data-iksug="'+esc(s.sid)+'|'+x.u.n+'">'+esc(utext(x.u))+
              ' <b class="num">'+x.c.u+'%</b></button>';
          }).join('') : '<span class="tiny">70%未満の単元はありません（全体に少しずつ低い）</span>')+'</span>'+
        (has(s.subRate) ? '<span class="ik-lsub tiny">提出 '+s.subRate+'%</span>' : '')+
        (s.rules ? '<span class="ik-rules" title="この生徒だけの宿題の決まり">決まり '+s.rules+'件</span>' : '')+
      '</div>';
    }).join('') +'</div>';
}

/* 個別の宿題 ―― **いま誰に何を出しているか**を、コースのページの1か所で答える。
   プリセットで出したものは、その名前で束ねる。決まりを止めるのは生徒の紙で。 */
function boardCard(c){
  var rows = c.board || [], groups = {}, order = [];
  rows.forEach(function(st){
    st.rules.forEach(function(r){
      var k = r.name || r.text;
      var g = groups[k];
      if(!g){ g = groups[k] = {name:k, text:r.text, span:r.span, preset:r.preset, stus:[]}; order.push(g); }
      /* ひとこと付きなら、生徒の返事の状態を札に添える（質問あり＝止まっている・確認待ち） */
      g.stus.push({sid:st.sid, label:st.label, ack:(r.msg ? ((r.ack || {}).state || 'open') : '')});
    });
  });
  return '<div class="card ik-board">'+
    '<div class="ik-lh"><div class="lbl">個別の宿題<span class="tiny">いま出しているもの'+(rows.length ? ' <span class="num">'+rows.length+'</span>人' : '')+'</span></div>'+
      '<button class="btn small ghost" data-ikassign="all">宿題を変更する</button></div>'+
    (order.length ? order.map(function(g){
      return '<div class="ik-bgrp">'+
        '<div class="ik-bg1"><b>'+esc(g.name)+'</b>'+
          (g.name !== g.text ? '<span class="tiny">'+esc(g.text)+'</span>' : '')+
          '<span class="tiny">'+esc(g.span)+'</span></div>'+
        '<div class="ik-bstus">'+ g.stus.map(function(st){
          var w = st.ack === 'asked' ? '質問あり' : (st.ack === 'open' || st.ack === 'answered') ? '確認待ち' : '';
          return '<button class="ik-bstu'+(w ? ' '+esc(st.ack) : '')+'" data-ikstu="'+esc(st.sid)+'">'+esc(st.label)+
            (w ? '<i>'+w+'</i>' : '')+'</button>';
        }).join('') +'</div>'+
      '</div>';
    }).join('') : '<p class="tiny">ありません。既定の宿題がそのまま出ています。生徒を押すと、その子だけの決まりを見られます。</p>')+
  '</div>';
}

function heatCard(c, units){
  var stus = (c.students || []).slice().sort(function(a, b){
    return (has(a.avg) ? a.avg : 999) - (has(b.avg) ? b.avg : 999); });
  return '<div class="card ik-heatc t-full"><div class="lbl">生徒 × 直近'+units.length+'単元（黄を押すと、その生徒への提案が出ます）</div>'+
    '<div class="ik-heatwrap"><table class="ik-heat"><thead><tr><th scope="col">生徒</th>'+
      units.map(function(u){
        return '<th scope="col"><button class="ik-hn" data-ikunit="'+u.n+'">'+esc(ushort(u))+'<span>'+esc(uname(u) ? u.topic : '')+'</span></button></th>';
      }).join('') +'<th scope="col">平均</th><th scope="col">提出</th></tr></thead><tbody>'+
      stus.map(function(s){
        return '<tr><th scope="row"><button class="ik-lname" data-ikstu="'+esc(s.sid)+'">'+esc(s.label)+'</button>'+
            (s.rules ? '<span class="ik-dotp" title="この生徒だけの宿題の決まりがあります"></span>' : '')+'</th>'+
          units.map(function(u){
            var cell = (s.cells || {})[String(u.n)];
            if(!cell || !has(cell.u)) return '<td class="none">―</td>';
            if(cell.u < YELLOW){
              return '<td class="y"><button data-iksug="'+esc(s.sid)+'|'+u.n+'" aria-label="'+esc(s.label)+
                ' '+esc(utext(u))+' '+cell.u+'% 提案を見る">'+cell.u+'</button></td>';
            }
            return '<td class="b">'+cell.u+'</td>';
          }).join('')+
          '<td class="avg '+tone(s.avg)+'">'+(has(s.avg) ? s.avg : '―')+'</td>'+
          '<td class="sub">'+(has(s.subRate) ? s.subRate+'%' : '―')+'</td></tr>';
      }).join('') +'</tbody></table></div></div>';
}

function evText(cell){
  var out = [];
  var ev = cell.ev || {};
  if(cell.v >= 1) out.push('宿題 '+WORD[cell.v]);
  else if(cell.v === 0) out.push('宿題 出ていない');
  if(has(ev.test)) out.push('テスト '+ev.test+'%');
  if(has(ev.daily)) out.push('毎日テスト '+ev.daily+'%');
  if(has(ev.prep)) out.push('対策 '+ev.prep+'%');
  return out.join(' ・ ') || '根拠なし';
}

function unitDetail(c, n){
  var u = (c.units || []).filter(function(x){ return x.n === n; })[0];
  if(!u) return '';
  var rows = (c.students || []).map(function(s){ return {s:s, c:(s.cells || {})[String(n)]}; })
    .filter(function(x){ return x.c; })
    .sort(function(a, b){ return (has(a.c.u) ? a.c.u : 999) - (has(b.c.u) ? b.c.u : 999); });
  return '<div class="card ik-unit t-full">'+
    '<div class="ik-uh"><div><div class="lbl">'+esc(utext(u))+' の生徒ごと</div>'+
      '<p class="tiny">理解度 '+(has(u.und) ? u.und+'%' : '―')+'（根拠のある'+u.undN+'人の平均）'+
      ' ・ 提出 '+(has(u.sub) ? u.sub+'%（'+u.subDone+'/'+u.subN+'人）' : '―')+'</p></div>'+
      '<button class="lnk" data-ikunit="0">閉じる</button></div>'+
    rows.map(function(x){
      var v = x.c.u;
      return '<div class="ik-urow">'+
        '<button class="ik-lname" data-ikstu="'+esc(x.s.sid)+'">'+esc(x.s.label)+'</button>'+
        '<span class="ik-ubar '+tone(v)+'"><i style="width:'+(has(v) ? v : 0)+'%"></i></span>'+
        '<span class="num ik-uv '+tone(v)+'">'+(has(v) ? v+'%' : '―')+'</span>'+
        '<span class="ik-ev tiny">'+esc(evText(x.c))+'</span>'+
        '<span class="ik-us2 tiny">'+(x.c.sub === true ? '提出' : x.c.sub === false ? '未提出' : '')+'</span>'+
        (has(v) && v < YELLOW ? '<button class="btn small ghost" data-iksug="'+esc(x.s.sid)+'|'+n+'">提案を見る</button>' : '<span></span>')+
      '</div>';
    }).join('') +'</div>';
}

/* 生徒ごとの札（見本 T09 27b）。平均を大きく、8単元は小さな棒、いちばん低い単元を1行。押すとその生徒の紙。 */
function stuCards(c, units){
  var stus = (c.students || []).slice().sort(function(a, b){ return (has(a.avg) ? a.avg : 999) - (has(b.avg) ? b.avg : 999); });
  if(!stus.length) return '';
  var thr = ins.thr;
  return '<div class="ik-stuh t-full"><span class="h-lbl">生徒ごと</span><span class="tiny">理解度の低い順・直近'+units.length+'単元（棒の黄は'+YELLOW+'%未満）。押すとその生徒の紙へ</span></div>'+
    '<div class="ik-stus t-full">'+ stus.map(function(s){
      var cells = units.map(function(u){ var cell = (s.cells || {})[String(u.n)]; return (cell && has(cell.u)) ? cell.u : null; });
      var worst = null;
      units.forEach(function(u, i){ if(cells[i] !== null && (worst === null || cells[i] < worst.v)) worst = {u:u, v:cells[i]}; });
      var low = has(s.avg) && s.avg <= thr;
      return '<button class="ik-stu'+(low ? ' low' : '')+'" data-ikstu="'+esc(s.sid)+'">'+
        '<span class="ik-stutop"><b>'+esc(s.label)+'</b>'+(s.worry ? '<span class="ik-worry">心配</span>' : '')+(s.rules ? '<span class="ik-pers">個別</span>' : '')+
          '<span class="tiny">提出 <span class="num">'+(has(s.subRate) ? s.subRate : '―')+'</span>%</span></span>'+
        '<span class="ik-stuavg'+(low ? ' y' : '')+'"><b class="num">'+(has(s.avg) ? s.avg : '―')+'</b><i>%</i></span>'+
        '<span class="ik-stubars">'+ cells.map(function(v){
          return '<i class="'+(v === null ? 'none' : v < YELLOW ? 'y' : '')+'" style="height:'+(v === null ? 8 : Math.max(8, v))+'%"></i>'; }).join('') +'</span>'+
        '<span class="ik-stuweak">'+(worst && worst.v < YELLOW ? '苦手：'+esc(ushort(worst.u))+' <b class="num">'+worst.v+'%</b>' : has(s.avg) ? 'どの単元も'+YELLOW+'%以上' : '根拠がまだありません')+'</span>'+
      '</button>';
    }).join('') +'</div>';
}

function testsCard(c){
  var ts = c.tests || [];
  return '<div class="card ik-tests t-full"><div class="ik-lh"><div class="lbl">取り込んだ塾内テスト</div>'+
      '<button class="btn small ghost" data-ikimport="1">取り込む</button></div>'+
    (ts.length ? ts.map(function(t){
      var armed = ins.armDel === t.id;
      return '<div class="ik-trow"><span><b>'+esc(t.name)+'</b> '+esc(mdS(t.date))+'</span>'+
        '<span class="tiny">'+t.n+'人 ・ '+t.cols.length+'列（'+esc(t.cols.map(function(x){ return x.label; }).join('・'))+'）</span>'+
        '<button class="lnk'+(armed ? ' warn' : '')+'" data-ikdel="'+esc(t.id)+'">'+(armed ? 'もう一度押すと消えます' : '消す')+'</button></div>';
    }).join('') : '<p class="tiny">まだありません。単元確認テストの点を入れると、理解度がテストの点も見て出るようになります。</p>')+
  '</div>';
}

/* ---- 紙（重ねて出すもの） ---- */
function sheets(){
  var sh = ins.sheet;
  if(!sh) return '';
  var body = sh.type === 'suggest' ? suggestSheet(sh)
           : sh.type === 'student' ? studentSheet(sh)
           : sh.type === 'change'  ? changeSheet(sh)
           : sh.type === 'rule'    ? ruleSheet(sh)
           : sh.type === 'import'  ? importSheet(sh)
           : sh.type === 'assign'  ? assignSheet(sh) : '';
  /* data-sk は紙の名札。同じ紙を描き直したときは、出てくる動きを繰り返さない（ui-core.js render）。 */
  var sk = ['ik', sh.type, sh.sid || '', sh.n || ''].join('|');
  return '<div class="shade" data-ikshut="1"></div>'+
    '<div class="sheet wide ik-sheet" role="dialog" aria-modal="true" data-sk="'+esc(sk)+'">'+ body +'</div>';
}
function sheetTop(title, sub){
  return '<div class="sh-top"><div><div class="sh-n">'+title+'</div>'+
    (sub ? '<div class="sh-s">'+sub+'</div>' : '')+'</div>'+
    '<button class="sh-x" data-ikshut="1" aria-label="とじる">&times;</button></div>';
}

function loadStudent(sid){
  var k = ins.key + '|' + sid;
  if(stuCache[k] === undefined){
    stuCache[k] = null;
    srv().insightStudent(ins.key, sid).then(function(g){ stuCache[k] = g || {error:true}; render(); });
  }
  return stuCache[k];
}

function suggestSheet(sh){
  var k = ins.key + '|' + sh.sid + '|' + sh.n;
  if(sugCache[k] === undefined){
    sugCache[k] = null;
    srv().insightSuggest(ins.key, sh.sid, sh.n).then(function(g){ sugCache[k] = g || {error:true}; render(); });
  }
  var g = sugCache[k];
  if(!g) return sheetTop('提案', '') + '<div class="sh-body"><p class="tiny">しらべています…</p></div>';
  if(g.error) return sheetTop('提案', '') + '<div class="sh-body"><p class="tiny">提案を読み込めませんでした。</p></div>';
  var c = ins.course[ins.key] || {}, presets = c.presets || [];
  var pre = sh.took
    ? '<div class="ik-sg done"><div class="ik-sgk">プリセットから</div>'+
        '<div class="ik-sgt">'+esc(sh.took)+'</div><div class="ik-ok">出しました ―― '+esc(g.nextName || ('第'+g.next+'回'))+'の宿題に（この回だけ）</div>'+
        '<button class="lnk" data-ikstu="'+esc(sh.sid)+'">この生徒の次の宿題を見る →</button></div>'
    : '<div class="ik-sg"><div class="ik-sgk">プリセットから足す</div>'+
        (presets.length
          ? '<div class="ik-opts">'+ presets.map(function(pr){
              return '<button class="ik-opt ik-pre" data-ikpre="'+esc(pr.id)+'"><b>'+esc(pr.name)+'</b><span>'+esc(presetLine(pr))+'</span></button>';
            }).join('') +'</div><div class="tiny ik-sgw">'+esc(g.nextName || ('第'+g.next+'回'))+'の宿題に、この回だけ。ずっと出すなら「宿題を足す」から</div>'
          : '<div class="tiny ik-sgw">このコースのプリセットがまだありません。</div>'+
            '<div class="ik-sga"><button class="btn small ghost" data-ikassign="'+esc(sh.sid)+'">プリセットを作って足す</button></div>')+
      '</div>';
  var list = (g.suggestions || []).filter(function(x, i){ return !(sh.skipped || {})[i]; });
  var body = pre + (list.length ? (g.suggestions || []).map(function(x, i){
    if((sh.skipped || {})[i]) return '';
    if(sh.taken === i){
      return '<div class="ik-sg done"><div class="ik-sgk">'+esc(KIND[x.kind] || x.kind)+'</div>'+
        '<div class="ik-sgt">'+esc(x.title)+'</div><div class="ik-ok">出しました ―― '+esc(x.span)+'</div>'+
        '<button class="lnk" data-ikstu="'+esc(sh.sid)+'">この生徒の次の宿題を見る →</button></div>';
    }
    return '<div class="ik-sg"><div class="ik-sgk">'+esc(KIND[x.kind] || x.kind)+'</div>'+
      '<div class="ik-sgt">'+esc(x.title)+'</div>'+
      '<div class="ik-sgs">'+esc(x.span)+'</div>'+
      '<div class="tiny ik-sgw">'+esc(x.why)+'</div>'+
      '<div class="ik-sga"><button class="btn small" data-iktake="'+i+'">この内容で出す</button>'+
        '<button class="btn small ghost" data-ikedit="'+i+'">書き換えて出す</button>'+
        '<button class="lnk" data-ikskip="'+i+'">見送る</button></div></div>';
  }).join('') : '');
  return sheetTop(esc(g.student.label)+' ／ '+esc(utext(g.unit)),
                  '次の授業（'+esc(g.nextName || ('第'+g.next+'回'))+'）の宿題と一緒に、この生徒だけに出ます') +
    '<div class="sh-body">'+ body +
      '<div class="ik-sgfoot"><button class="lnk" data-ikrule="'+esc(sh.sid)+'">提案とは別に、自分で宿題を変える →</button>'+
      '<button class="lnk" data-ikstu="'+esc(sh.sid)+'">この生徒の推移を見る</button></div>'+
    '</div>';
}

function studentSheet(sh){
  var g = loadStudent(sh.sid);
  if(!g) return sheetTop('生徒', '') + '<div class="sh-body"><p class="tiny">よみこんでいます…</p></div>';
  if(g.error) return sheetTop('生徒', '') + '<div class="sh-body"><p class="tiny">読み込めませんでした。</p></div>';
  var tr = g.trend || {units:[], months:[]};
  var units = (tr.units || []).slice(-12);
  var chart = '<div class="ik-strend">'+ units.map(function(u){
    return '<div class="ik-st"><span class="ik-cv num">'+(has(u.u) ? u.u : '―')+'</span>'+
      '<span class="ik-cb '+tone(u.u)+'"><i style="height:'+(has(u.u) ? Math.max(3, u.u) : 0)+'%"></i>'+
        (has(u.classU) ? '<b class="ik-mean" style="bottom:'+u.classU+'%" title="クラスの平均 '+u.classU+'%"></b>' : '')+'</span>'+
      '<span class="ik-cl">'+esc(ushort(u))+'</span></div>';
  }).join('') +'</div>';
  var months = (tr.months || []).map(function(x){
    return '<span class="ik-mo '+tone(x.u)+'">'+(+x.month.slice(5))+'月 <b class="num">'+x.u+'%</b></span>';
  }).join('');
  var table = '<table class="ik-ev2"><thead><tr><th>単元</th><th>宿題</th><th>テスト</th><th>毎日テスト</th><th>理解度</th><th></th></tr></thead><tbody>'+
    (tr.units || []).slice().reverse().map(function(u){
      var ev = u.ev || {};
      return '<tr><td>'+esc(utext(u))+'</td>'+
        '<td>'+(u.v >= 1 ? WORD[u.v] : u.v === 0 ? '出ていない' : '―')+'</td>'+
        '<td>'+(has(ev.test) ? ev.test+'%' : '―')+'</td>'+
        '<td>'+(has(ev.daily) ? ev.daily+'%' : '―')+'</td>'+
        '<td class="'+tone(u.u)+'"><b>'+(has(u.u) ? u.u+'%' : '―')+'</b></td>'+
        '<td>'+(has(u.u) && u.u < YELLOW ? '<button class="lnk" data-iksug="'+esc(sh.sid)+'|'+u.n+'">提案</button>' : '')+'</td></tr>';
    }).join('') +'</tbody></table>';
  var rules = g.rules || [];
  var live = rules.filter(function(r){ return r.live; });
  var ended = rules.filter(function(r){ return !r.live; });
  var nx = g.next;
  return sheetTop(esc(g.student.label)+' ／ '+esc(g.course.name),
                  '理解度（直近5単元） '+(has(tr.avg) ? tr.avg+'%' : '―')+' ・ 提出 '+(has(tr.subRate) ? tr.subRate+'%' : '―')) +
    '<div class="sh-body">'+
      '<div class="lbl">単元ごとの理解度（線はクラスの平均）</div>'+ chart +
      (months ? '<div class="ik-months"><span class="lbl">月ごと</span>'+months+'</div>' : '')+
      '<div class="ik-evwrap">'+table+'</div>'+
      '<div class="ik-rules2"><div class="ik-lh"><div class="lbl">この生徒だけの宿題の決まり</div>'+
        '<button class="btn small" data-ikrule="'+esc(sh.sid)+'">宿題を変える</button></div>'+
        (live.length ? live.map(function(r){
          return '<div class="ik-rrow"><span><b>'+esc(r.text)+'</b><span class="tiny">'+esc(r.span)+
            (r.note ? ' ・ '+esc(r.note) : '')+'</span>'+
            (r.msg ? '<span class="ik-rmsg">「'+esc(r.msg)+'」<span class="ik-ack '+esc((r.ack || {}).state || 'open')+'">'+esc(ackWord(r))+'</span></span>' : '')+'</span>'+
            '<button class="lnk" data-ikstop="'+esc(r.id)+'">止める</button></div>';
        }).join('') : '<p class="tiny">ありません。既定の宿題がそのまま出ます。</p>')+
        (ended.length ? '<details class="ik-ended"><summary>終わった決まり '+ended.length+'件</summary>'+
          ended.map(function(r){ return '<div class="tiny">'+esc(r.text)+'（'+esc(r.span)+'）</div>'; }).join('')+'</details>' : '')+
      '</div>'+
      (nx ? '<div class="ik-next"><div class="lbl">'+esc(ushort(nx))+'（'+esc(mdSW(nx.date))+'）のこの生徒の宿題</div>'+
          (nx.none ? '<p class="tiny">この生徒は、次の回の宿題の受け取り手に入っていません。</p>'
                   : nx.student.map(function(it){
                       return '<div class="ik-nit'+(it.personal ? ' p' : '')+'">'+esc(it.title)+
                         (it.personal ? '<em>この生徒だけ</em>' : it.extra ? '<em>上位</em>' : '')+
                         (!it.graded ? '<em class="g">出すだけ</em>' : '')+'</div>';
                     }).join(''))+'</div>' : '')+
    '</div>';
}

function ruleSheet(sh){
  var g = loadStudent(sh.sid);
  if(!g) return sheetTop('宿題を変える', '') + '<div class="sh-body"><p class="tiny">よみこんでいます…</p></div>';
  if(g.error || !g.next) return sheetTop('宿題を変える', '') +
    '<div class="sh-body"><p class="tiny">次の回の予定が無いため、変えられません（授業計画に回を足してください）。</p></div>';
  var nx = g.next, dr = sh.draft;
  var items = (nx.default || []);
  var pickI = dr.item;
  var step1 = '<div class="ik-step"><div class="ik-sl"><b>1</b> どの宿題を</div><div class="ik-opts">'+
    items.map(function(it, i){
      return '<button class="ik-opt'+(pickI === i ? ' on' : '')+'" data-ikritem="'+i+'" aria-pressed="'+(pickI === i)+'">'+
        esc(it.title)+(it.extra ? '<em>上位</em>' : '')+(!it.graded ? '<em class="g">出すだけ</em>' : '')+'</button>';
    }).join('')+
    '<button class="ik-opt add'+(pickI === 'add' ? ' on' : '')+'" data-ikritem="add" aria-pressed="'+(pickI === 'add')+'">＋ 新しく足す</button>'+
  '</div></div>';
  var step2 = '';
  if(pickI !== null && pickI !== undefined){
    var kinds = pickI === 'add' ? [] : [['drop', '出さない'], ['scale', '減らす'], ['swap', '置き換える']];
    var needText = pickI === 'add' || dr.kind === 'swap';
    step2 = '<div class="ik-step"><div class="ik-sl"><b>2</b> どう変える</div>'+
      (kinds.length ? '<div class="ik-opts">'+ kinds.map(function(k){
        return '<button class="ik-opt'+(dr.kind === k[0] ? ' on' : '')+'" data-ikrkind="'+k[0]+'" aria-pressed="'+(dr.kind === k[0])+'">'+k[1]+'</button>';
      }).join('') +'</div>' : '')+
      (dr.kind === 'scale' ? '<div class="ik-opts">'+ [[0.7, '3割へらす'], [0.5, '半分'], [0.3, '7割へらす']].map(function(f){
          return '<button class="ik-opt'+(dr.factor === f[0] ? ' on' : '')+'" data-ikrfac="'+f[0]+'">'+f[1]+'</button>';
        }).join('') +'</div>' : '')+
      (needText ? '<label class="field"><span class="lbl">'+(pickI === 'add' ? '足す宿題' : '代わりに出すもの')+'</span>'+
          '<input id="ikText" maxlength="60" value="'+esc(dr.text || '')+'" placeholder="例：予習シリーズ 練習問題"></label>'+
          '<label class="field"><span class="lbl">ページ・番号</span><select id="ikCopy">'+
            '<option value="">つけない（文だけ）</option>'+
            items.filter(function(it){ return it.source; }).map(function(it){
              return '<option value="'+esc(it.source)+'"'+(dr.copy === it.source ? ' selected' : '')+'>'+
                esc(it.base)+' と同じ範囲</option>';
            }).join('') +'</select></label>' : '')+
    '</div>';
  }
  var step3 = (pickI !== null && pickI !== undefined)
    ? '<div class="ik-step"><div class="ik-sl"><b>3</b> いつまで</div><div class="ik-opts">'+
        '<button class="ik-opt'+(dr.until === 'once' ? ' on' : '')+'" data-ikruntil="once">'+esc(ushort(nx))+'だけ</button>'+
        '<button class="ik-opt'+(dr.until === 'keep' ? ' on' : '')+'" data-ikruntil="keep">次に変えるまで、ずっと</button>'+
      '</div></div>'
    : '';
  return sheetTop(esc(g.student.label)+' の宿題を変える', esc(ushort(nx))+'（'+esc(mdSW(nx.date))+'）から効きます。出したあとの宿題は変わりません') +
    '<div class="sh-body">'+ step1 + step2 + step3 +
      (sh.error ? '<p class="warn tiny">'+esc(sh.error)+'</p>' : '')+
      '<div class="ik-next"><div class="lbl">いまの'+esc(ushort(nx))+'のこの生徒の宿題</div>'+
        (nx.student || []).map(function(it){
          return '<div class="ik-nit'+(it.personal ? ' p' : '')+'">'+esc(it.title)+(it.personal ? '<em>この生徒だけ</em>' : '')+'</div>';
        }).join('') +'</div>'+
      '<label class="field ik-msgf"><span class="lbl">生徒へのひとこと（「先生から」に出ます。生徒は「わかった」か「質問する」で返せます）</span>'+
        '<textarea id="ikMsg" rows="2" maxlength="200" placeholder="例：比の性質が弱いので、その復習をしましょう">'+esc(dr.msg || '')+'</textarea></label>'+
      '<div class="ik-sga"><button class="btn" data-iksave="1">保存する</button>'+
        '<button class="lnk" data-ikshut="1">やめる</button></div>'+
    '</div>';
}

function draftRule(sh, g){
  var dr = sh.draft, items = (g.next && g.next.default) || [];
  if(dr.item === null || dr.item === undefined) return {error:'どの宿題を変えるかを選んでください'};
  var rule = {until: dr.until === 'once' ? 'once' : null};
  if(dr.origin) rule.origin = dr.origin;
  if(dr.msg) rule.msg = dr.msg;
  if(dr.item === 'add'){
    rule.kind = 'add';
  }else{
    var it = items[dr.item];
    if(!dr.kind) return {error:'どう変えるかを選んでください'};
    rule.kind = dr.kind;
    rule.match = {source:it.source || '', text:it.base || ''};
    if(dr.kind === 'scale') rule.factor = dr.factor || 0.5;
  }
  if(rule.kind === 'add' || rule.kind === 'swap'){
    if(!dr.text) return {error:(rule.kind === 'add' ? '足す宿題' : '代わりに出すもの')+'を書いてください'};
    rule['with'] = {text:dr.text};
    if(dr.copy) rule['with'].copy = {source:dr.copy, n:null};
  }
  return {rule:rule};
}

function openRule(sid, fromSuggestion){
  var draft = {item:null, kind:null, factor:0.5, text:'', copy:'', until:'once'};
  if(fromSuggestion){
    var r = fromSuggestion.rule || {};
    draft.until = r.until === 'once' ? 'once' : 'keep';
    draft.origin = r.origin || null;
    draft.text = ((r['with'] || {}).text) || '';
    draft.copy = (((r['with'] || {}).copy) || {}).source || '';
    draft.kind = r.kind === 'add' ? null : r.kind;
    draft.factor = r.factor || 0.5;
    draft.item = r.kind === 'add' ? 'add' : null;
    draft.match = r.match || null;
  }
  if(!fromSuggestion) return openChange([sid], null);
  openChange([sid], fromSuggestion);
}

function importSheet(sh){
  var c = ins.course[ins.key] || {};
  var name = c.course ? c.course.name : '';
  if(sh.step !== 'preview'){
    return sheetTop('テスト結果を取り込む ／ '+esc(name), '1列目は席番号（'+esc(seatExample(c))+'）。名前の列は入れないでください') +
      '<div class="sh-body">'+
        '<div class="row" style="gap:12px">'+
          '<label class="field" style="flex:2"><span class="lbl">テストの名前</span>'+
            '<input id="ikTname" maxlength="40" value="'+esc(sh.name || '単元確認テスト')+'"></label>'+
          '<label class="field" style="flex:1"><span class="lbl">実施日</span>'+
            '<input id="ikTdate" type="date" value="'+esc(sh.date || isoToday())+'"></label>'+
        '</div>'+
        '<label class="field"><span class="lbl">表（Excel から貼り付けるか、CSV ファイルを選ぶ）</span>'+
          '<textarea id="ikText2" rows="8" placeholder="席番号,比例(20),一次関数(30)&#10;'+esc(seatExample(c))+',18,21">'+esc(sh.text || '')+'</textarea></label>'+
        '<input type="file" id="ikFile" accept=".csv,.tsv,.txt,text/csv,text/plain">'+
        '<p class="tiny" style="margin-top:10px">読める形：大問（単元）ごとの点／合計点だけ／設問ごとの ○×。満点は見出しの「比例(20)」か「満点」の行から読みます。</p>'+
        (sh.error ? '<p class="warn tiny">'+esc(sh.error)+'</p>' : '')+
        '<div class="ik-sga"><button class="btn" data-ikread="1">読み取る</button><button class="lnk" data-ikshut="1">やめる</button></div>'+
      '</div>';
  }
  var p = sh.preview;
  var kindWord = {units:'大問（単元）ごとの点', total:'合計点だけ', questions:'設問ごとの正誤'}[p.kind] || '分からない形';
  var date = sh.date || isoToday();
  var lessons = (p.lessons || []).filter(function(l){ return l.date && l.date <= date; }).slice(-8);
  return sheetTop('取り込む前に確かめる ／ '+esc(sh.name), esc(kindWord)+' ・ 席が合った '+p.matched+'人') +
    '<div class="sh-body">'+
      (p.errors && p.errors.length ? '<p class="warn">'+esc(p.errors.join(' '))+'</p>' : '')+
      (p.warnings && p.warnings.length ? '<p class="tiny">'+esc(p.warnings.join(' ／ '))+'</p>' : '')+
      (p.unmatched && p.unmatched.length ? '<p class="tiny warn">席が合わない行（取り込みません）：'+esc(p.unmatched.join('、'))+'</p>' : '')+
      '<div class="ik-cols">'+ (p.cols || []).map(function(col, i){
        var chosen = (sh.mapping && sh.mapping[i]) || col.lessons || [];
        return '<div class="ik-colrow"><div class="ik-coln"><b>'+esc(col.label)+'</b>'+
            (col.q ? '<span class="tiny">設問'+col.q+'問</span>' : '')+'</div>'+
          '<label class="ik-max"><span class="tiny">満点</span><input data-ikmax="'+i+'" inputmode="decimal" value="'+esc(has(col.max) ? col.max : ((sh.maxes || [])[i] || ''))+'"></label>'+
          '<div class="ik-les"><span class="tiny">どの単元の点か</span>'+ lessons.map(function(l){
            var on = chosen.indexOf(l.n) >= 0;
            return '<button class="ik-lchip'+(on ? ' on' : '')+'" data-ikmap="'+i+'|'+l.n+'" aria-pressed="'+on+'">'+esc(utext(l))+'</button>';
          }).join('') +'</div></div>';
      }).join('') +'</div>'+
      (sh.error ? '<p class="warn tiny">'+esc(sh.error)+'</p>' : '')+
      '<div class="ik-sga"><button class="btn" data-ikimp="1"'+((p.errors || []).length ? ' disabled' : '')+'>'+p.matched+'人ぶん取り込む</button>'+
        '<button class="lnk" data-ikback2="1">表を直す</button></div>'+
    '</div>';
}

/* 宿題を足す ―― プリセットを選び、生徒を選び、いつまでかを決めて、まとめて出す。
   1 プリセット（無ければ作る）→ 2 生徒（理解度の低い順。低い子は初めから選ばれている）→ 3 いつまで。 */
/* 宿題を変更する（見本 T12）―― 次の回の宿題を、選んだ生徒だけ変える。そのまま／減らす／置き換える／出さない。 */
function openChange(sids, pre){
  var sel = {}; (sids || []).forEach(function(x){ sel[x] = true; });
  ins.sheet = {type:'change', sel:sel, items:{}, until:'once', msg:'', pre:pre || null, more:false, busy:false, error:''};
  render();
}
function changeSheet(sh){
  var c = ins.course[ins.key] || {}, nx = c.next || {};
  var stus = (c.students || []).slice().sort(function(a, b){
    return (has(a.avg) ? a.avg : 999) - (has(b.avg) ? b.avg : 999) || String(a.label).localeCompare(String(b.label), 'ja'); });
  var first = Object.keys(sh.sel).filter(function(k){ return sh.sel[k]; })[0] || (stus[0] && stus[0].sid);
  var g = first ? loadStudent(first) : null;
  var items = (g && g.next && g.next.default) || [];
  if(sh.pre && !sh.preDone && items.length){
    var r = sh.pre.rule || {}, mt = r.match || {};
    items.forEach(function(it, i){ if(mt.source && it.source === mt.source || (mt.text && it.base === mt.text)) sh.items[i] = {kind:r.kind || 'scale', factor:r.factor || 0.5, text:((r['with'] || {}).text) || ''}; });
    sh.until = r.until === 'once' ? 'once' : 'keep'; sh.preDone = true;
  }
  var nSel = stus.filter(function(x){ return sh.sel[x.sid]; }).length;
  var shown = sh.more ? stus : stus.slice(0, 6);
  var chips = '<div class="ik-cstus">'+ shown.map(function(x){
      var on = !!sh.sel[x.sid];
      return '<button class="ik-cchip'+(on ? ' on' : '')+(has(x.avg) && x.avg <= ins.thr ? ' low' : '')+'" data-ikcs="'+esc(x.sid)+'" aria-pressed="'+on+'">'+(on ? ui().ico('check', 14, 3) : '')+esc(x.label)+'</button>';
    }).join('') + (stus.length > shown.length ? '<button class="lnk" data-ikcmore="1">ほか '+(stus.length - shown.length)+'人</button>' : '')+'</div>';
  var KINDS = [['keep', 'そのまま'], ['scale', '減らす'], ['swap', '置き換える'], ['drop', '出さない']];
  var rows = !g ? '<p class="tiny">よみこんでいます…</p>' : !items.length ? '<p class="tiny">次の回の宿題が、まだありません（授業計画に回を足してください）。</p>' :
    items.map(function(it, i){
      var st = sh.items[i] || {kind:'keep'};
      return '<div class="ik-citem">'+
        '<div class="ik-cit"><span class="ik-cin">'+esc(it.title)+'</span>'+(it.extra ? '<span class="ik-ctag">上位</span>' : '')+(!it.graded ? '<span class="ik-ctag g">出すだけ</span>' : '')+'</div>'+
        '<div class="ik-cseg" role="radiogroup" aria-label="変え方">'+ KINDS.map(function(k){
          return '<button role="radio" aria-checked="'+(st.kind === k[0])+'" class="'+(st.kind === k[0] ? 'on' : '')+'" data-ikck="'+i+'|'+k[0]+'">'+k[1]+'</button>'; }).join('') +'</div>'+
        (st.kind === 'scale' ? '<div class="ik-cfac"><span class="tiny">どれだけ</span>'+ [[0.3, '3割'], [0.5, '5割'], [0.7, '7割']].map(function(f){
            return '<button class="ik-cf'+((st.factor || 0.5) === f[0] ? ' on' : '')+'" data-ikcf="'+i+'|'+f[0]+'">'+f[1]+'</button>'; }).join('') +'<span class="tiny">に減らす</span></div>' : '')+
        (st.kind === 'swap' ? '<input class="ik-cin2" data-ikct="'+i+'" maxlength="60" value="'+esc(st.text || '')+'" placeholder="代わりに出すもの（例：予習シリーズ 練習問題）">' : '')+
      '</div>';
    }).join('');
  var nChg = Object.keys(sh.items).filter(function(k){ return sh.items[k] && sh.items[k].kind !== 'keep'; }).length;
  return sheetTop('宿題を変更する', esc(c.course ? c.course.name : '')+' ・ 次の授業（'+esc(ushort(nx) || '次の回')+(nx.date ? ' '+esc(mdSW(nx.date)) : '')+'）の宿題を、選んだ生徒だけ変えます')+
    '<div class="sh-body ik-change">'+
      '<div class="ik-cs"><span class="ik-csl">生徒（理解度の低い順）<span class="num">'+nSel+'</span>人</span>'+chips+'</div>'+
      '<div class="ik-cs"><span class="ik-csl">'+esc(ushort(nx) || '次の回')+'の宿題</span>'+rows+
        '<button class="ik-cadd" data-ikcpreset="1">'+ui().ico('plus', 18, 2.4)+'プリセットから足す</button></div>'+
      '<div class="ik-cs"><span class="ik-csl">いつまで</span><div class="ik-cuntil" role="radiogroup">'+
        '<button role="radio" aria-checked="'+(sh.until === 'once')+'" class="'+(sh.until === 'once' ? 'on' : '')+'" data-ikcu="once">'+esc(ushort(nx) || '次の回')+'だけ</button>'+
        '<button role="radio" aria-checked="'+(sh.until === 'keep')+'" class="'+(sh.until === 'keep' ? 'on' : '')+'" data-ikcu="keep">次に変えるまで、ずっと</button></div></div>'+
      '<label class="ik-cs"><span class="ik-csl">生徒へのひとこと（「先生から」に出ます）</span>'+
        '<textarea data-ikcmsg="1" rows="2" maxlength="200" placeholder="例：比の性質が弱いので、その復習をしましょう">'+esc(sh.msg || '')+'</textarea></label>'+
      (sh.error ? '<p class="warn tiny">'+esc(sh.error)+'</p>' : '')+
      '<div class="ik-cacts"><button class="btn ghost" data-ikshut="1">やめる</button>'+
        '<button class="btn" data-ikcgo="1"'+((!nSel || !nChg || sh.busy) ? ' disabled' : '')+'>'+(sh.busy ? '変えています…' : 'この内容に変える')+'</button></div>'+
    '</div>';
}
async function changeGo(sh){
  var c = ins.course[ins.key] || {};
  var first = Object.keys(sh.sel).filter(function(k){ return sh.sel[k]; })[0];
  var g = first ? loadStudent(first) : null;
  var items = (g && g.next && g.next.default) || [];
  var sids = Object.keys(sh.sel).filter(function(k){ return sh.sel[k]; });
  var n = 0, failed = [];
  sh.busy = true; render();
  for(var a = 0; a < sids.length; a++){
    for(var i = 0; i < items.length; i++){
      var st = sh.items[i]; if(!st || st.kind === 'keep') continue;
      var it = items[i];
      var rule = {kind:st.kind, until:(sh.until === 'once' ? 'once' : null), match:{source:it.source || '', text:it.base || ''}};
      if(st.kind === 'scale') rule.factor = st.factor || 0.5;
      if(st.kind === 'swap'){ if(!st.text){ failed.push('代わりに出すものが空です'); continue; } rule['with'] = {text:st.text}; }
      if(sh.msg) rule.msg = sh.msg;
      var r = await srv().putRule(ins.key, sids[a], rule);
      if(r && r.ok) n++; else failed.push((r && r.error) || '保存できませんでした');
    }
  }
  sh.busy = false;
  over = undefined; ins.course = {}; stuCache = {}; sugCache = {};
  if(!n){ sh.error = failed[0] || '変える内容がありません'; return render(); }
  ins.sheet = null;
  toast(n+'件を変えました'+(failed.length ? '（'+failed.length+'件は保存できませんでした）' : ''));
  render();
}

function assignSheet(sh){
  var c = ins.course[ins.key] || {}, presets = c.presets || [], nx = c.next || {};
  var units = (c.units || []).slice(-(c.recent || 5));
  if(sh.result){
    return sheetTop('出しました', '') + '<div class="sh-body"><p>'+esc(sh.result)+'</p>'+
      (sh.failed && sh.failed.length ? '<p class="warn tiny">'+esc(sh.failed.join(' ／ '))+'</p>' : '')+
      '<div class="ik-sga"><button class="btn" data-ikshut="1">閉じる</button></div></div>';
  }
  var cur = presets.filter(function(x){ return x.id === sh.preset; })[0] || null;
  var step1 = '<div class="ik-step"><div class="ik-sl"><b>1</b> どの宿題を（プリセット）</div>'+
    '<div class="ik-opts">'+ presets.map(function(pr){
      var on = sh.preset === pr.id;
      return '<button class="ik-opt ik-pre'+(on ? ' on' : '')+'" data-ikas-preset="'+esc(pr.id)+'" aria-pressed="'+on+'">'+
        '<b>'+esc(pr.name)+'</b><span>'+esc(presetLine(pr))+'</span></button>';
    }).join('') +
    '<button class="ik-opt add" data-ikpe-new="1">＋ 新しく作る</button></div>'+
    (cur ? '<div class="ik-sga"><button class="lnk" data-ikpe-edit="'+esc(cur.id)+'">「'+esc(cur.name)+'」を直す</button></div>' : '')+
    (!presets.length && !sh.edit
      ? '<div class="ik-tpl"><span class="tiny">雛形から作る：</span>'+
          '<button class="lnk" data-ikpe-new="dev">同じ教材の発展問題（同じ回）</button>'+
          '<button class="lnk" data-ikpe-new="app">アプリで復習 10問</button></div>' : '')+
    (sh.edit ? presetEditor(sh, c) : '')+
  '</div>';
  var stus = (c.students || []).slice().sort(function(a, b){
    return (has(a.avg) ? a.avg : 999) - (has(b.avg) ? b.avg : 999) || String(a.label).localeCompare(String(b.label), 'ja'); });
  var nSel = stus.filter(function(x){ return sh.sel[x.sid]; }).length;
  var step2 = '<div class="ik-step"><div class="ik-sl"><b>2</b> だれに <span class="tiny">'+nSel+'人</span>'+
      '<span class="ik-slx"><button class="lnk" data-ikas-all="1">全員</button><button class="lnk" data-ikas-none="1">はずす</button></span></div>'+
    '<div class="ik-stus">'+ stus.map(function(x){
      var on = !!sh.sel[x.sid], w = weakOf(x, units)[0];
      return '<button class="ik-stu'+(on ? ' on' : '')+'" data-ikas-stu="'+esc(x.sid)+'" aria-pressed="'+on+'">'+
        '<b>'+esc(x.label)+'</b>'+
        '<span class="num '+tone(x.avg)+'">'+(has(x.avg) ? x.avg+'%' : '―')+'</span>'+
        '<span class="tiny">'+(w ? esc(ushort(w.u))+' '+w.c.u+'%' : '')+'</span>'+
        (x.rules ? '<em title="この生徒だけの決まりがあります">個別</em>' : '')+
      '</button>';
    }).join('') +'</div></div>';
  var step3 = '<div class="ik-step"><div class="ik-sl"><b>3</b> いつまで</div><div class="ik-opts">'+
      '<button class="ik-opt'+(sh.until === 'once' ? ' on' : '')+'" data-ikas-until="once" aria-pressed="'+(sh.until === 'once')+'">'+esc(ushort(nx) || '次の回')+'だけ</button>'+
      '<button class="ik-opt'+(sh.until === 'keep' ? ' on' : '')+'" data-ikas-until="keep" aria-pressed="'+(sh.until === 'keep')+'">次に変えるまで、ずっと</button>'+
    '</div></div>';
  return sheetTop('宿題を足す ／ '+esc(c.course ? c.course.name : ''),
                  '次の授業（'+esc(ushort(nx) || '次の回')+(nx.date ? ' '+esc(mdSW(nx.date)) : '')+'）の宿題と一緒に、選んだ生徒だけに出ます') +
    '<div class="sh-body">'+ step1 + step2 + step3 +
      (sh.error ? '<p class="warn tiny">'+esc(sh.error)+'</p>' : '')+
      '<label class="field ik-msgf"><span class="lbl">生徒へのひとこと（選んだ全員の「先生から」に出ます）</span>'+
        '<textarea id="ikBulkMsg" rows="2" maxlength="200" placeholder="例：この単元が弱いので、その復習をしましょう">'+esc(sh.msg || '')+'</textarea></label>'+
      '<div class="ik-sga"><button class="btn" data-ikas-go="1"'+((!cur || !nSel) ? ' disabled' : '')+'>'+nSel+'人に出す</button>'+
        '<button class="lnk" data-ikshut="1">やめる</button></div>'+
    '</div>';
}

/* プリセットを作る・直す（宿題を足す紙の中）。 */
function presetEditor(sh, c){
  var e = sh.edit;
  var books = (global.TubeTeacher && c.course) ? TubeTeacher.booksOf({subject:c.course.subject, grade:c.course.grade, classId:c.course.classId}) : [];
  var ranges = [['same', '同じ回の範囲'], ['pages', '決まった範囲'], ['app', 'アプリの問題']];
  return '<div class="ik-pe">'+
    '<div class="lbl">'+(e.id ? 'プリセットを直す' : '新しいプリセット')+'</div>'+
    '<label class="field"><span class="lbl">名前（生徒の宿題にもこの名前で出ます）</span>'+
      '<input id="ikpeName" maxlength="30" value="'+esc(e.name || '')+'" placeholder="例：発展問題"></label>'+
    '<div class="ik-opts">'+ ranges.map(function(r){
      return '<button class="ik-opt'+(e.range === r[0] ? ' on' : '')+'" data-ikpe-range="'+r[0]+'" aria-pressed="'+(e.range === r[0])+'">'+r[1]+'</button>';
    }).join('') +'</div>'+
    (e.range !== 'app'
      ? '<label class="field"><span class="lbl">教材と段</span>'+
          '<input id="ikpeText" maxlength="60" value="'+esc(e.text || '')+'" placeholder="例：新中学問題集 発展問題"></label>'+
        '<label class="field"><span class="lbl">'+(e.range === 'same' ? '範囲を写す教材（授業計画にその教材の範囲があるとき）' : '教材（分かれば）')+'</span>'+
          '<select id="ikpeSrc"><option value="">えらばない</option>'+ books.map(function(r){
            return '<option value="'+esc(r.x.id)+'"'+(e.source === r.x.id ? ' selected' : '')+' data-name="'+esc(r.x.name)+'">'+esc(r.x.name)+(r.graded ? '' : '（出すだけ）')+'</option>';
          }).join('') +'</select></label>'
      : '')+
    (e.range === 'pages'
      ? '<label class="field"><span class="lbl">範囲</span><input id="ikpePages" maxlength="20" value="'+esc(e.pages || '')+'" placeholder="p.40-43"></label>' : '')+
    (e.range === 'app'
      ? '<label class="field"><span class="lbl">問題の数（その生徒の弱い単元から集めます）</span><input id="ikpeCount" inputmode="numeric" maxlength="2" value="'+esc(e.count || 10)+'"></label>' : '')+
    '<p class="tiny">同じ回の範囲：授業計画のその回に同じ教材の範囲があれば写します。無ければ回の名前を添えて出します。</p>'+
    (sh.editError ? '<p class="warn tiny">'+esc(sh.editError)+'</p>' : '')+
    '<div class="ik-sga"><button class="btn small" data-ikpe-save="1">保存する</button>'+
      (e.id ? '<button class="lnk warn" data-ikpe-del="'+esc(e.id)+'">消す</button>' : '')+
      '<button class="lnk" data-ikpe-cancel="1">やめる</button></div>'+
  '</div>';
}

function seatExample(c){
  var s = (c.students || [])[0];
  return s ? s.label : '中2R-01';
}
function isoToday(){
  var d = new Date();
  return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2, '0')+'-'+String(d.getDate()).padStart(2, '0');
}

/* ---- つなぎ込み ---- */
function wireInsight(m){
  m.querySelectorAll('[data-ikct]').forEach(function(x){ x.oninput = function(){ var sh = ins.sheet; if(!sh) return; sh.items[x.dataset.ikct] = Object.assign({}, sh.items[x.dataset.ikct] || {kind:'swap'}, {text:x.value}); }; });
  m.querySelectorAll('[data-ikcmsg]').forEach(function(x){ x.oninput = function(){ if(ins.sheet) ins.sheet.msg = x.value; }; });
  var on = function(sel, fn){ m.querySelectorAll(sel).forEach(function(b){ b.onclick = function(e){ fn(b, e); }; }); };
  on('[data-ikall]', function(){ ins.mode = 'all'; ins.key = null; ins.sheet = null; window.scrollTo(0, 0); render(); });
  on('[data-ikcourse]', function(b){ openCourse(b.dataset.ikcourse); });
  // 狭い画面で札が横送りのとき、選んでいるコースの札を見える位置へ（縦には動かさない）
  var row = m.querySelector('.ik-chips'), cur = row && row.querySelector('[aria-pressed="true"]');
  if(row && cur && row.scrollWidth > row.clientWidth){
    var rr = row.getBoundingClientRect(), cr = cur.getBoundingClientRect();
    if(cr.left < rr.left || cr.right > rr.right) row.scrollLeft += cr.left - rr.left - 16;
  }
  on('[data-ikunit]', function(b){
    ui().keepInPlace(b);
    var n = +b.dataset.ikunit;
    ins.n = (!n || ins.n === n) ? null : n;
    render();
  });
  on('[data-ikthr]', function(b){ ui().keepInPlace(b); ins.thr = +b.dataset.ikthr; render(); });
  on('[data-iksug]', function(b){
    var p = b.dataset.iksug.split('|');
    ins.sheet = {type:'suggest', sid:p[0], n:+p[1], skipped:{}, taken:null};
    render();
  });
  on('[data-ikstu]', function(b){ ins.sheet = {type:'student', sid:b.dataset.ikstu}; render(); });
  on('[data-ikrule]', function(b){ openChange([b.dataset.ikrule], null); });
  on('[data-ikassign]', function(b){
    var who = b.dataset.ikassign, c = ins.course[ins.key] || {};
    if(who === 'low') return openChange((c.students || []).filter(function(x){ return has(x.avg) && x.avg <= ins.thr; }).map(function(x){ return x.sid; }));
    if(who === 'all') return openChange([]);
    openAssign(who);
  });
  on('[data-ikcs]', function(b){ var sh = ins.sheet; sh.sel[b.dataset.ikcs] = !sh.sel[b.dataset.ikcs]; render(); });
  on('[data-ikcmore]', function(){ ins.sheet.more = true; render(); });
  on('[data-ikck]', function(b){ var p = b.dataset.ikck.split('|'), sh = ins.sheet; sh.items[p[0]] = Object.assign({}, sh.items[p[0]] || {}, {kind:p[1]}); if(p[1] === 'scale' && !sh.items[p[0]].factor) sh.items[p[0]].factor = 0.5; render(); });
  on('[data-ikcf]', function(b){ var p = b.dataset.ikcf.split('|'), sh = ins.sheet; sh.items[p[0]] = Object.assign({}, sh.items[p[0]] || {kind:'scale'}, {factor:+p[1]}); render(); });
  on('[data-ikcu]', function(b){ ins.sheet.until = b.dataset.ikcu; render(); });
  on('[data-ikcpreset]', function(){ var sel = ins.sheet.sel; openAssign('all'); if(ins.sheet){ ins.sheet.sel = Object.assign({}, sel); render(); } });
  on('[data-ikcgo]', function(){ changeGo(ins.sheet); });
  on('[data-ikshut]', function(){ ins.sheet = null; render(); });
  on('[data-ikimport]', function(){ ins.sheet = {type:'import', step:'input'}; render(); });
  on('[data-ikdel]', async function(b){
    var id = b.dataset.ikdel;
    if(ins.armDel !== id){ ins.armDel = id; return render(); }
    ins.armDel = null;
    var ok = await srv().scoresRemove(id);
    toast(ok ? 'テストを消しました' : '消せませんでした');
    forget(ins.key); render();
  });

  var sh = ins.sheet;
  if(!sh) return;
  var k = ins.key + '|' + sh.sid + '|' + sh.n;

  on('[data-iktake]', async function(b){
    var g = sugCache[k], x = g && g.suggestions[+b.dataset.iktake];
    if(!x) return;
    b.disabled = true; b.textContent = '出しています…';
    var r = await srv().putRule(ins.key, sh.sid, x.rule);
    if(!r.ok){ b.disabled = false; b.textContent = 'この内容で出す'; return toast(r.error); }
    sh.taken = +b.dataset.iktake;
    forget(ins.key);
    toast((g.nextName || ('第'+g.next+'回'))+'の宿題に入れました（この生徒だけ）');
    render();
  });
  on('[data-ikskip]', async function(b){
    var g = sugCache[k], i = +b.dataset.ikskip, x = g && g.suggestions[i];
    if(!x) return;
    sh.skipped = sh.skipped || {};
    sh.skipped[i] = true;
    render();
    await srv().insightFeedback({key:ins.key, sid:sh.sid, n:sh.n, kind:x.kind, action:'dismiss'});
  });
  on('[data-ikedit]', function(b){
    var g = sugCache[k], x = g && g.suggestions[+b.dataset.ikedit];
    if(x) openRule(sh.sid, x);
  });
  on('[data-ikpre]', async function(b){
    var g = sugCache[k];
    var c = ins.course[ins.key] || {}, pr = (c.presets || []).filter(function(x){ return x.id === b.dataset.ikpre; })[0];
    if(!g || !pr) return;
    b.disabled = true;
    var r = await srv().putRule(ins.key, sh.sid, null, {id:pr.id, until:'once', unit:(g.unit || {}).topic || ''});
    if(!r.ok){ b.disabled = false; return toast(r.error); }
    sh.took = pr.name;
    forget(ins.key);
    toast((g.nextName || ('第'+g.next+'回'))+'の宿題に入れました（この生徒だけ）');
    render();
  });
  on('[data-ikstop]', async function(b){
    var r = await srv().stopRule(ins.key, sh.sid, b.dataset.ikstop);
    if(!r.ok) return toast(r.error);
    toast('決まりを止めました。次の回から既定の宿題に戻ります');
    forget(ins.key); render();
  });

  if(sh.type === 'rule'){
    var dr = sh.draft;
    var keepText = function(){
      var t = m.querySelector('#ikText'), c = m.querySelector('#ikCopy'), g2 = m.querySelector('#ikMsg');
      if(t) dr.text = t.value.trim();
      if(c) dr.copy = c.value;
      if(g2) dr.msg = g2.value.trim();
    };
    on('[data-ikritem]', function(b){
      keepText();
      var v = b.dataset.ikritem;
      dr.item = v === 'add' ? 'add' : +v;
      if(dr.item === 'add') dr.kind = null;
      render();
    });
    on('[data-ikrkind]', function(b){ keepText(); dr.kind = b.dataset.ikrkind; render(); });
    on('[data-ikrfac]', function(b){ keepText(); dr.factor = +b.dataset.ikrfac; render(); });
    on('[data-ikruntil]', function(b){ keepText(); dr.until = b.dataset.ikruntil; render(); });
    on('[data-iksave]', async function(b){
      keepText();
      var g = stuCache[ins.key + '|' + sh.sid];
      var got = draftRule(sh, g || {});
      if(got.error){ sh.error = got.error; return render(); }
      b.disabled = true;
      var r = await srv().putRule(ins.key, sh.sid, got.rule);
      if(!r.ok){ b.disabled = false; sh.error = r.error; return render(); }
      forget(ins.key);
      toast('保存しました。'+(g.next ? ushort(g.next) : '次の回')+'の宿題から効きます');
      ins.sheet = {type:'student', sid:sh.sid};
      render();
    });
  }

  if(sh.type === 'assign'){
    var keepEdit = function(){
      var e = sh.edit; if(!e) return;
      var q = function(id){ return m.querySelector(id); };
      if(q('#ikpeName')) e.name = q('#ikpeName').value.trim();
      if(q('#ikpeText')) e.text = q('#ikpeText').value.trim();
      if(q('#ikpeSrc')) e.source = q('#ikpeSrc').value;
      if(q('#ikpePages')) e.pages = q('#ikpePages').value.trim();
      if(q('#ikpeCount')) e.count = +q('#ikpeCount').value || 10;
    };
    var keepMsg = function(){ var t = m.querySelector('#ikBulkMsg'); if(t) sh.msg = t.value.trim(); };
    m.querySelectorAll('#ikBulkMsg').forEach(function(t){ t.oninput = keepMsg; });
    on('[data-ikas-preset]', function(b){ keepEdit(); sh.preset = b.dataset.ikasPreset; render(); });
    on('[data-ikas-stu]', function(b){ keepEdit(); var id = b.dataset.ikasStu; if(sh.sel[id]) delete sh.sel[id]; else sh.sel[id] = true; render(); });
    on('[data-ikas-all]', function(){ keepEdit(); ((ins.course[ins.key] || {}).students || []).forEach(function(x){ sh.sel[x.sid] = true; }); render(); });
    on('[data-ikas-none]', function(){ keepEdit(); sh.sel = {}; render(); });
    on('[data-ikas-until]', function(b){ keepEdit(); sh.until = b.dataset.ikasUntil; render(); });
    on('[data-ikpe-new]', function(b){
      var c = ins.course[ins.key] || {};
      var books = (global.TubeTeacher && c.course) ? TubeTeacher.booksOf({subject:c.course.subject, grade:c.course.grade, classId:c.course.classId}) : [];
      var first = books.filter(function(r){ return r.on && r.graded; })[0] || books[0];
      var kind = b.dataset.ikpeNew;
      sh.edit = kind === 'dev' ? {name:'発展問題', text:(first ? first.x.name+' ' : '')+'発展問題', source:first ? first.x.id : '', range:'same'}
              : kind === 'app' ? {name:'アプリで復習', text:'', source:'', range:'app', count:10}
              : {name:'', text:'', source:'', range:'same', pages:'', count:10};
      sh.editError = null; render();
    });
    on('[data-ikpe-edit]', function(b){
      var c = ins.course[ins.key] || {}, pr = (c.presets || []).filter(function(x){ return x.id === b.dataset.ikpeEdit; })[0];
      if(pr){ sh.edit = Object.assign({}, pr); sh.editError = null; render(); }
    });
    on('[data-ikpe-range]', function(b){ keepEdit(); sh.edit.range = b.dataset.ikpeRange; render(); });
    on('[data-ikpe-cancel]', function(){ sh.edit = null; sh.editError = null; render(); });
    var src = m.querySelector('#ikpeSrc');
    if(src) src.onchange = function(){
      /* 教材を選んだら、教材と段の欄がまだ空なら教材名を入れておく（段は講師が足す） */
      var t = m.querySelector('#ikpeText'), o = src.options[src.selectedIndex];
      if(t && !t.value.trim() && o && o.dataset.name) t.value = o.dataset.name + ' ';
    };
    on('[data-ikpe-save]', async function(b){
      keepEdit();
      b.disabled = true;
      var r = await srv().putPreset(ins.key, sh.edit);
      if(!r.ok){ b.disabled = false; sh.editError = r.error; return render(); }
      var c = ins.course[ins.key];
      if(c) c.presets = r.data.presets;
      sh.preset = r.data.preset.id; sh.edit = null; sh.editError = null;
      toast('プリセットを保存しました');
      render();
    });
    on('[data-ikpe-del]', async function(b){
      var r = await srv().delPreset(ins.key, b.dataset.ikpeDel);
      if(!r.ok) return toast(r.error);
      var c = ins.course[ins.key];
      if(c) c.presets = r.data.presets;
      if(sh.preset === b.dataset.ikpeDel) sh.preset = null;
      sh.edit = null; toast('プリセットを消しました'); render();
    });
    on('[data-ikas-go]', async function(b){
      keepEdit();
      var c = ins.course[ins.key] || {}, units = (c.units || []).slice(-(c.recent || 5));
      var sids = Object.keys(sh.sel), unitOf = {};
      (c.students || []).forEach(function(x){
        if(!sh.sel[x.sid]) return;
        var w = weakOf(x, units)[0];
        unitOf[x.sid] = w ? (w.u.topic || '') : ((c.next || {}).topic || '');
      });
      if(!sh.preset || !sids.length) return;
      b.disabled = true; b.textContent = '出しています…';
      keepMsg();
      var r = await srv().personalBulk({key:ins.key, sids:sids, units:unitOf, preset:{id:sh.preset, until:sh.until}, msg:sh.msg || ''});
      if(!r.ok){ b.disabled = false; b.textContent = sids.length+'人に出す'; sh.error = r.error; return render(); }
      var pr = (c.presets || []).filter(function(x){ return x.id === sh.preset; })[0] || {name:''};
      sh.result = r.data.done.length+'人に「'+pr.name+'」を足しました（'+(ushort(c.next || {}) || '次の回')+'の宿題'+(sh.until === 'keep' ? 'から、次に変えるまで' : '')+'）';
      sh.failed = (r.data.failed || []).map(function(f){ return f.sid+'：'+f.error; });
      if(c) c.board = r.data.board;
      forget(ins.key);
      render();
    });
  }

  if(sh.type === 'import'){
    var file = m.querySelector('#ikFile');
    if(file) file.onchange = function(){
      var f = file.files && file.files[0];
      if(!f) return;
      if(f.size > 400000){ sh.error = 'ファイルが大きすぎます'; return render(); }
      var rd = new FileReader();
      rd.onload = function(){ sh.text = String(rd.result || ''); sh.error = null; render(); };
      rd.readAsText(f);
    };
    on('[data-ikread]', async function(b){
      sh.name = (m.querySelector('#ikTname') || {}).value || '';
      sh.date = (m.querySelector('#ikTdate') || {}).value || '';
      sh.text = (m.querySelector('#ikText2') || {}).value || '';
      if(!sh.text.trim()){ sh.error = '表を貼り付けてください'; return render(); }
      b.disabled = true; b.textContent = '読んでいます…';
      var r = await srv().scoresPreview(ins.key, sh.text, sh.date);
      if(!r.ok){ b.disabled = false; sh.error = r.error; return render(); }
      if((r.data.errors || []).length){ b.disabled = false; sh.error = r.data.errors.join(' '); return render(); }
      sh.preview = r.data; sh.step = 'preview'; sh.error = null;
      sh.mapping = (r.data.cols || []).map(function(c){ return (c.lessons || []).slice(); });
      sh.maxes = (r.data.cols || []).map(function(c){ return has(c.max) ? c.max : ''; });
      render();
    });
    var keepMax = function(){
      m.querySelectorAll('[data-ikmax]').forEach(function(inp){ sh.maxes[+inp.dataset.ikmax] = inp.value; });
    };
    on('[data-ikmap]', function(b){
      keepMax();
      var p = b.dataset.ikmap.split('|'), i = +p[0], n = +p[1];
      var cur = sh.mapping[i] || (sh.mapping[i] = []);
      var at = cur.indexOf(n);
      if(at >= 0) cur.splice(at, 1); else cur.push(n);
      render();
    });
    on('[data-ikback2]', function(){ keepMax(); sh.step = 'input'; render(); });
    on('[data-ikimp]', async function(b){
      keepMax();
      if(sh.mapping.some(function(x){ return !x.length; })){ sh.error = 'どの単元の点かを、すべての列で選んでください'; return render(); }
      b.disabled = true; b.textContent = '取り込んでいます…';
      var r = await srv().scoresImport({key:ins.key, name:sh.name, date:sh.date, text:sh.text,
                                       mapping:sh.mapping, maxes:sh.maxes});
      if(!r.ok){ b.disabled = false; sh.error = r.error; return render(); }
      forget(ins.key);
      ins.sheet = null;
      toast(r.data.test.n + '人ぶんの点を取り込みました');
      render();
    });
  }
}

/* 宿題を足す紙を開く。who … 'low'（理解度の低い生徒を選んでおく）／'all'（誰も選ばない）／生徒の sid */
function openAssign(who){
  var c = ins.course[ins.key] || {}, sel = {};
  if(who === 'low'){
    (c.students || []).forEach(function(s){ if(has(s.avg) && s.avg <= ins.thr) sel[s.sid] = true; });
  }else if(who && who !== 'all'){
    sel[who] = true;
  }
  var first = (c.presets || [])[0];
  ins.sheet = {type:'assign', sel:sel, preset:first ? first.id : null, until:'once', edit:null, error:null};
  render();
}

/* 成績タブをもう一度押したとき（TubeTeacher.home から呼ぶ） */
function home(){
  ins.mode = 'all'; ins.key = null; ins.n = null; ins.sheet = null; ins.armDel = null;
}

/* 前の人の控えを捨てる（ui-core がログイン・ログアウトで呼ぶ） */
function resetSession(){
  today = undefined; dkBusy = null;
  chk.key = null; chk.n = null; chk.data = undefined; chk.want = null; chk.focus = null; chk.page = 0; chk.showRet = false; chk.draw = null;
  ins.sheet = null; ins.key = null; ins.n = null;
}

global.TubeDesk = {
  resetSession:resetSession,
  todayCard:todayCard, wireToday:wireToday, slotUnd:slotUnd,
  openCheck:openCheck, viewCheck:viewCheck,
  /* 紙（提案・生徒・決まり・取り込み）を開いたまま描き直しても、紙の中の巻き位置を戻す。
     押すたびに先頭へ飛ぶと、長い紙の下のボタンを押した直後に、どこを見ていたか分からなくなる。 */
  viewInsight:function(m){
    var body = document.querySelector('.ik-sheet .sh-body');
    var keep = (body && ins.sheet) ? {type:ins.sheet.type, sid:ins.sheet.sid, y:body.scrollTop} : null;
    viewInsight(m);
    var nb = document.querySelector('.ik-sheet .sh-body');
    if(keep && nb && ins.sheet && ins.sheet.type === keep.type && ins.sheet.sid === keep.sid) nb.scrollTop = keep.y;
  },
  openCourse:openCourse, home:home,
  forgetAll:function(){ today = undefined; over = undefined; ins.course = {}; stuCache = {}; sugCache = {}; },
  wake:function(changed){
    if(changed && !(changed.submissions || changed.ratings || changed.assignments || changed.personal)) return;
    today = undefined; over = undefined; stuCache = {}; sugCache = {};
    if(chk.key && !dkBusy){ chk.want = null; loadCheck(); }
  }
};

})(window);
