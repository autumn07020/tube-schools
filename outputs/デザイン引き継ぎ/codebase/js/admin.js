/* ============================================================
   管理ページ ―― 席・講師・担当・生徒に出ているもの・報告

   決めごと
   --------
   1. **合言葉は、この端末の中で作る。** 乱数（crypto.getRandomValues）で作り、その場で
      サーバに置く値（js/scram.js の verifier。server/scram.py と同じ値）にして、
      それだけを送る。サーバは、作った合言葉を一度も受け取らない。入るときも送らない。
      作った合言葉は、画面に1回だけ出す（表にコピーしてもらう）。閉じたら、もう読めない。
   2. 操作は1つずつ、押したその場で保存する（保存ボタンを作らない）。返事に今の状態が
      付いてくるので、それで描き直す。画面が持っている古い一覧を送り返すことはしない。
   3. 合言葉（入ったままの印）は、この窓の中だけ（sessionStorage）。窓を閉じたら消える。
      30分さわらなければ、サーバの側でも切れる。
   4. 見出しは日本語だけ。いちばん上に「次にやること」を1つ。線は引かない。
   ============================================================ */
(function(){
"use strict";

var TOKEN_KEY = 'tube.admin.token';
var S = { tok:null, st:null, tab:'now', sheet:null, open:null, fresh:null, busy:false, cards:null, cardText:'',
          reports:null, repAll:false, msg:'', arm:null, words:null };

var GRADE = {e1:'小1',e2:'小2',e3:'小3',e4:'小4',e5:'小5',e6:'小6',j1:'中1',j2:'中2',j3:'中3'};
var SUBJ = {japanese:'国語', math:'数学', english:'英語', science:'理科', social:'社会'};
var USE = ['紙のまま','宿題を出す','写真で提出','添削まで','毎日テストまで'];
var WD = ['日','月','火','水','木','金','土'];
var NWORDS = {seat:3, teacher:4, admin:5};

function $(q){ return document.querySelector(q); }
function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
function ssGet(){ try{ return sessionStorage.getItem(TOKEN_KEY); }catch(e){ return null; } }
function ssSet(v){ try{ v ? sessionStorage.setItem(TOKEN_KEY, v) : sessionStorage.removeItem(TOKEN_KEY); }catch(e){} }
function subj(c){ return (c.subject === 'math' && /^e/.test(c.grade)) ? '算数' : (SUBJ[c.subject] || c.subject); }
function md(sec){ if(!sec) return ''; var d = new Date(sec * 1000); return (d.getMonth()+1) + '/' + d.getDate(); }
function mdw(iso){              /* 'YYYY-MM-DD' → 10/7（水）。端末の暦で作る（世界標準時にしない） */
  var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || ''); if(!m) return '';
  var d = new Date(+m[1], +m[2]-1, +m[3]); return (+m[2]) + '/' + (+m[3]) + '（' + WD[d.getDay()] + '）';
}
var toastT = null;
function toast(t){ var el = $('#toast'); el.textContent = t; el.classList.add('on');
  clearTimeout(toastT); toastT = setTimeout(function(){ el.classList.remove('on'); }, 4200); }

/* ---------- サーバ ---------- */
/* quiet＝画面が裏で回す取り直し。サーバは、これを「さわった」に数えない（さわらなければ30分で切れる、を効かせる）。 */
async function api(method, path, body, quiet){
  var h = {'Content-Type':'application/json'};
  if(S.tok) h['Authorization'] = 'Bearer ' + S.tok;
  if(quiet) h['X-Tube-Quiet'] = '1';
  var res;
  try{
    res = await fetch('/api' + path, {method:method, headers:h, cache:'no-store',
                                      body: body === undefined ? undefined : JSON.stringify(body)});
  }catch(e){ return {ok:false, status:0, data:{error:'サーバに繋がりません'}}; }
  var data = null; try{ data = await res.json(); }catch(e){ data = {}; }
  if(res.status === 401 && S.tok && path.indexOf('/login') !== 0){
    S.tok = null; ssSet(null); S.st = null; S.sheet = null; S.fresh = null; S.cards = null; S.cardText = '';
    S.msg = S.selfReset ? '合言葉を作り直しました。新しい合言葉で入り直してください。' : '時間がたったので、入り直してください。';
    S.selfReset = false; render();
  }
  return {ok:res.ok, status:res.status, data:data || {}};
}
function take(r){               /* 返事に付いてきた今の状態で描き直す */
  if(r.ok && r.data && r.data.state) S.st = r.data.state;
  if(!r.ok) toast((r.data && r.data.error) || 'できませんでした');
  return r.ok;
}
async function reload(force, quiet){
  var r = await api('GET', '/admin/state', undefined, quiet);
  if(!r.ok) return;
  if(force){ S.st = r.data; return render(); }
  /* 入力の途中（番号の欄・表の欄）を消さないよう、変わったときだけ描き直す。 */
  var same = S.st && JSON.stringify(Object.assign({}, S.st, {now:0})) === JSON.stringify(Object.assign({}, r.data, {now:0}));
  S.st = r.data;
  if(!same && !S.busy && !(S.sheet && (S.sheet.kind === 'csv' || S.sheet.kind === 'move' || S.sheet.kind === 'newclass' || S.sheet.kind === 'place')) && S.tab !== 'cards') render();
}

/* ---------- 合言葉を作る（この端末の中で） ---------- */
function canMake(){ return !!(window.crypto && crypto.getRandomValues && window.TextEncoder && window.TubeScram); }
/* n 件ぶんの合言葉と、サーバに置く値を作る。合言葉はこの端末から出ない（js/scram.js）。 */
async function makeMany(role, n, onStep){
  if(!canMake()) throw new Error('この端末では合言葉を作れません。新しいブラウザで開いてください。');
  var pws = [], vs = [];
  for(var i = 0; i < n; i++){
    var pw = await TubeScram.makePassword(NWORDS[role] || 3);
    pws.push(pw); vs.push(await TubeScram.verifier(pw));
    if(onStep) onStep(i + 1, n);
  }
  return {pws:pws, vs:vs};
}
/* 呼び名（この端末の中だけ。サーバへは送らない）。講師の ID だけでは、だれか分からないため。 */
var NAMES_KEY = 'tube.admin.names';
function names(){ try{ return JSON.parse(localStorage.getItem(NAMES_KEY)) || {}; }catch(e){ return {}; } }
function nameOf(id){ var n = names()[id]; return n ? String(n).slice(0, 20) : ''; }
function setName(id, v){
  var all = names(); v = String(v || '').trim().slice(0, 20);
  if(v) all[id] = v; else delete all[id];
  try{ localStorage.setItem(NAMES_KEY, JSON.stringify(all)); }catch(e){}
}
function who(id){ var n = nameOf(id); return n ? n + '（' + id + '）' : id; }
function linkOf(id, secret){ return location.origin + '/#k=' + id + '.' + secret; }
function claimWord(x){
  /* 引き換え待ち（オンラインで渡した。本人がまだ引き換えていない） */
  if(!x.claim) return '';
  return x.claim * 1000 > Date.now()
    ? '<span class="word warm">引き換え待ち（'+md(x.claim)+' まで）</span>'
    : '<span class="word warm">期限切れ（渡し直す）</span>';
}

/* ---------- 描く ---------- */
function render(){
  if(!S.tok || !S.st){ $('#top').innerHTML = ''; $('#layer').innerHTML = ''; $('#print').innerHTML = ''; return renderGate(); }
  var st = S.st, open = st.reports.open;
  var tabs = [['now','いまの様子'],['seats','生徒'],['staff','講師と担当'],['out','生徒に出ているもの'],['cards','カード'],['rep','報告']];
  $('#top').innerHTML =
    '<div class="bar"><span class="brand"><b>tube</b><i>study</i></span>'+
      '<span class="where">管理　'+esc(st.school.name)+(st.school.demo ? '（デモ）' : '')+'</span>'+
      '<span class="who"><span class="mono">'+esc(st.me)+'</span><button class="lnk" data-act="out">出る</button></span></div>'+
    '<div class="tabs">'+tabs.map(function(t){
      return '<button class="tab'+(S.tab === t[0] ? ' on' : '')+'" data-act="tab" data-v="'+t[0]+'">'+t[1]+
             (t[0] === 'rep' && open ? '<span class="n">'+open+'</span>' : '')+'</button>'; }).join('')+'</div>';
  var m = $('#main');
  m.innerHTML = ({now:viewNow, seats:viewSeats, staff:viewStaff, out:viewOut, cards:viewCards, rep:viewRep}[S.tab] || viewNow)();
  $('#layer').innerHTML = S.sheet ? sheetHtml() : '';
  $('#print').innerHTML = S.printJoin ? joinSheetHtml() : ((S.tab === 'cards' && S.cards && S.cards.length) ? cardsHtml(S.cards) : '');
}

function renderGate(){
  $('#main').innerHTML =
    '<div class="gate"><span class="brand"><b>tube</b><i>study</i></span>'+
    '<p class="sub">管理する人だけのページです</p>'+
    '<div class="card">'+
      '<label><span>ID</span><input id="gId" type="text" autocapitalize="none" autocorrect="off" autocomplete="username" spellcheck="false"></label>'+
      '<label><span>合言葉</span><input id="gPw" type="password" autocomplete="current-password"></label>'+
      '<button class="btn" id="gGo" data-act="login">入る</button>'+
      (S.msg ? '<div class="msg" role="alert">'+esc(S.msg)+'</div>' : '')+
    '</div>'+
    (canMake() ? '' : '<div class="msg">この端末では、席や合言葉を作れません。新しいブラウザで開いてください。</div>')+
    '</div>';
  var pw = $('#gPw'), id = $('#gId');
  pw.onkeydown = function(e){ if(e.key === 'Enter') doLogin(); };
  id.onkeydown = function(e){ if(e.key === 'Enter') pw.focus(); };
}

function seatCount(c){ var n = {live:0, spare:0, left:0, pending:0}; c.seats.forEach(function(s){ n[s.st] = (n[s.st] || 0) + 1; }); return n; }
function byGrade(list, gradeOf){
  var out = [], seen = {};
  list.forEach(function(x){ var g = gradeOf(x); if(!seen[g]){ seen[g] = {g:g, items:[]}; out.push(seen[g]); } seen[g].items.push(x); });
  /* 席のある学年を先に。まだ席の無い学年（小1〜小3 など）は下へ。 */
  var has = {}; S.st.classes.forEach(function(c){ if(c.seats.length) has[c.grade] = 1; });
  return out.filter(function(x){ return has[x.g]; }).concat(out.filter(function(x){ return !has[x.g]; }));
}

/* --- いまの様子 --- */
function viewNow(){
  var st = S.st, live = 0, all = 0, left = 0;
  st.classes.forEach(function(c){ var n = seatCount(c); live += n.live; all += n.live + n.spare; left += n.left; });
  var ts = st.teachers.filter(function(t){ return !t.left; });
  var tin = ts.filter(function(t){ return t.last; }).length;
  var idle = ts.filter(function(t){ return t.last && !t.keys.length && !t.all; });
  var used = st.courses.filter(function(c){ return c.use > 0 && c.active; });
  var noT = used.filter(function(c){ return !c.teachers.length; });
  var noPlan = used.filter(function(c){ return !c.lessons; });
  var hero;
  if(st.reports.open){
    hero = ['まだ見ていない報告が '+st.reports.open+'件あります', '生徒や講師からの知らせ、画面が拾ったエラー、入口の見張りです。', 'rep', '報告を見る'];
  }else if(noPlan.length){
    hero = ['使っているのに、授業計画がまだ無いコースが '+noPlan.length+'件あります', noPlan.slice(0,3).map(function(c){ return c.name; }).join('・')+'。担当の講師が「時間割」から予定を入れると、宿題が出はじめます。', 'out', '出ているものを見る'];
  }else if(noT.length){
    hero = ['使っているのに、講師の決まっていないコースが '+noT.length+'件あります', noT.slice(0,3).map(function(c){ return c.name; }).join('・'), 'staff', '担当を決める'];
  }else if(idle.length){
    hero = ['担当の決まっていない講師が '+idle.length+'人います', idle.map(function(t){ return t.id; }).join('・')+'。入ったあと、何も出ていない状態です。', 'staff', '担当を決める'];
  }else if(!live){
    hero = ['まだ、どの席も使われていません', 'カードを渡した席は、本人がはじめて入ったときに名簿に出ます。紙だけの生徒は「使う」を押します。', 'seats', '席を見る'];
  }else{
    hero = null;
  }
  var h = hero
    ? '<div class="hero"><div><div class="k">次にやること</div><div class="t">'+esc(hero[0])+'</div><div class="s">'+esc(hero[1])+'</div></div>'+
      '<button class="btn go" data-act="tab" data-v="'+hero[2]+'">'+hero[3]+'</button></div>'
    : '<div class="hero calm"><div><div class="k">次にやること</div><div class="t">いま、やることはありません</div>'+
      '<div class="s">席・担当・報告に、手を入れる所は見つかりませんでした。</div></div></div>';
  var by = [0,0,0,0,0]; st.courses.forEach(function(c){ if(c.active) by[c.use]++; });
  var tiles =
    tile('生徒', live, '人', (all > live ? '前に作った席（渡していない）'+(all - live)+'　' : '')+(left ? '在籍終了 '+left : (all > live ? '' : 'お名前は持ちません。ID だけで区別します')), 'seats')+
    tile('講師', ts.length, '人', '入ったことがある '+tin+'人', 'staff')+
    tile('使っているコース', used.length, '／'+st.courses.filter(function(c){ return c.active; }).length,
         '宿題を出す '+by[1]+'・写真で提出 '+by[2]+'・添削まで '+by[3]+'・毎日テストまで '+by[4], 'out')+
    tile('見ていない報告', st.reports.open, '件', 'これまでに '+st.reports.all+'件', 'rep');
  return h + '<div class="sect"><h2>いまの様子</h2></div><div class="grid">'+tiles+'</div>' + joinCard() + examsCard() + idleCard() + recentHtml();
}
/* 使われなくなった口座。3か月使われないと、記録ごと自動で消える（本番に切り替えた校舎だけ）。 */
function idleCard(){
  var d = S.st.idle;
  if(!d || !S.st.school || !S.st.school.live) return '';
  var soon = d.soon || [];
  return '<div class="sect"><h2>使われていない口座</h2></div><div class="card idle">'+
    '<p>'+Math.round(d.idleDays / 30)+'か月のあいだ一度も使われなかった ID は、記録と写真ごと自動で消えます（ID は空きに戻ります）。'+
    '残るのは、ID を外した数字だけです。'+(d.gone ? '　これまでに消えた口座 <b class="num">'+d.gone+'</b>' : '')+'</p>'+
    (soon.length ? '<div class="spares">'+soon.map(function(x){
      return '<span class="exchip"><span class="mono">'+esc(x.id)+'</span>　あと '+x.left+'日</span>';
    }).join('')+'</div><p class="small">続けて使う生徒なら、一度入ってもらえば消えません。</p>'
    : '<p class="small">2週間以内に消える口座は、ありません。</p>')+'</div>';
}
/* 組分けテストの日程。結果が出てから2週間、生徒のホームに「クラスはどちらになりましたか」が出る（本人が答える）。 */
function mdDay(iso){ var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || ''); return m ? (+m[2]) + '/' + (+m[3]) : (iso || ''); }
function examsCard(){
  var ex = S.st.exams || {items:[], resultDays:7, askDays:14};
  var today = new Date(), iso = today.getFullYear()+'-'+('0'+(today.getMonth()+1)).slice(-2)+'-'+('0'+today.getDate()).slice(-2);
  var ask = ex.ask;
  return '<div class="sect"><h2>組分けテストの日程</h2></div><div class="card exams">'+
    '<p>テストの '+ex.resultDays+'日後から '+ex.askDays+'日のあいだ、生徒のホームに「クラスはどちらになりましたか」が出ます。本人（保護者）が答えると、新しいクラスの宿題が届きます。</p>'+
    (ask ? '<p class="ex-ask"><span class="word live">いま聞いています</span>　'+mdDay(ask.exam)+' のテスト（'+mdDay(ask.fromDay)+'〜'+mdDay(ask.toDay)+'）　答えた <b>'+ask.answered+'</b>／'+ask.total+'人</p>' : '')+
    '<div class="spares ex-list">'+(ex.items.length ? ex.items.map(function(e){
      return '<span class="exchip'+(e.date < iso ? ' past' : '')+'">'+esc(e.date.replace(/-/g, '/'))+
        '<button class="lnk" data-act="examdel" data-v="'+esc(e.date)+'" aria-label="'+esc(e.date)+' を外す">外す</button></span>';
    }).join('') : '<span class="small">まだ入っていません。日程が無いあいだは、何も聞きません。</span>')+'</div>'+
    '<div class="tool"><label for="exDate">テストの日</label><input id="exDate" type="date"><button class="btn sm" data-act="examadd">足す</button>'+
    '<span style="flex:1"></span><label for="exDays">結果が出るまで</label><input id="exDays" type="number" min="0" max="21" value="'+ex.resultDays+'"><span>日</span>'+
    '<button class="btn sm soft" data-act="examdays">変える</button></div></div>' + yearCard();
}
/* 新年度のはじまり。この日の朝に、在籍の生徒全員の学年が1つ上がる（サーバが自分で流す。retire.roll）。 */
function yearCard(){
  var ex = S.st.exams || {};
  var ys = ex.yearStart || '', rl = ex.rolled, today = ex.today || '';
  var left = ys && today ? Math.round((new Date(ys + 'T00:00:00') - new Date(today + 'T00:00:00')) / 86400000) : 0;
  var tm = today ? new Date(new Date(today + 'T00:00:00').getTime() + 86400000) : null;
  var min = tm ? tm.getFullYear()+'-'+('0'+(tm.getMonth()+1)).slice(-2)+'-'+('0'+tm.getDate()).slice(-2) : '';
  return '<div class="sect"><h2>新年度のはじまり</h2></div><div class="card exams year">'+
    '<p>この日の朝に、在籍の生徒全員の学年が1つ上がります（小4α → 小5α）。中3は卒業になり、クラスから外れます。'+
    '小6 → 中1 はクラスの記号が変わるので、ホームで本人に聞きます。出してある宿題は、そのままです。</p>'+
    (ys ? '<p class="ex-ask"><span class="word live">入っています</span>　<span class="exchip">'+esc(ys.replace(/-/g, '/'))+
            '<button class="lnk" data-act="yeardel" aria-label="新年度のはじまりを外す">外す</button></span>　あと '+left+'日</p>'
        : '<p class="small">まだ入っていません。入れなければ、学年は変わりません。</p>')+
    (rl ? '<p class="small">この前の繰り上げ　'+esc(String(rl.date || '').replace(/-/g, '/'))+'　上がった '+(rl.up || 0)+'人・卒業 '+(rl.grad || 0)+'人・クラスを聞いた '+(rl.ask || 0)+'人'+
            (ex.yearWait ? '（まだ答えていない '+ex.yearWait+'人）' : '')+'</p>' : '')+
    '<div class="tool"><label for="yrDate">はじまりの日</label><input id="yrDate" type="date"'+(min ? ' min="'+min+'"' : '')+'>'+
    '<button class="btn sm soft" data-act="yearset">'+(ys ? '入れ直す' : '入れる')+'</button></div></div>';
}
function saveExams(items, days){
  api('PUT', '/admin/exams', {exams:items, resultDays:days}).then(function(r){
    if(!r.ok){ toast(r.data.error || 'できませんでした'); return; }
    S.st = r.data.state; render();
  });
}
/* 最近の動き（登録・クラスや科目の変更・在籍・入口の見張り）。だれの ID に、何が起きたか。 */
function recentHtml(){
  var rs = (S.st.recent || []).slice(0, 14);
  if(!rs.length) return '';
  return '<div class="sect"><h2>最近の動き</h2></div><div class="card recent">'+rs.map(function(r){
    var d = new Date(r.at * 1000);
    var when = (d.getMonth()+1)+'/'+d.getDate()+' '+('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2);
    return '<div class="rc"><span class="when num">'+when+'</span><span class="word'+(r.kind === '登録' ? ' live' : r.kind === '入口の見張り' ? ' warm' : '')+'">'+esc(r.kind)+'</span>'+
      '<span class="id mono">'+esc(r.id)+'</span><span class="tx">'+esc(r.text)+'</span></div>';
  }).join('')+'</div>';
}
/* 登録コード（初回登録の入口の札）。保護者は、この QR かコードから、自分で口座を作る。 */
function joinLink(){ return location.origin + '/#join=' + S.st.join.code; }
function joinCard(){
  var j = S.st.join || {code:''};
  if(!j.code){
    return '<div class="sect"><h2>登録コード</h2></div><div class="card join">'+
      '<p>保護者が自分で生徒の口座を作るための、入口の札です。まだ作っていません。</p>'+
      '<div class="tool"><button class="btn" data-act="joinnew">登録コードを作る</button></div></div>';
  }
  return '<div class="sect"><h2>登録コード</h2></div><div class="card join">'+
    '<div class="join-in"><div class="join-qr">'+TubeQR.svg(joinLink(), 148)+'</div>'+
    '<div class="join-tx"><div class="join-code mono">'+esc(j.code)+'</div>'+
      '<p>この QR（かコード）を、保護者に配ってください。開くと「登録する」から、学年・クラス・受講科目を選んで ID を受け取れます。お名前は集めません。</p>'+
      '<p class="small">作った日 '+md(j.at)+'　コードが塾の外に出たら、作り直してください（前のコードは、その場で使えなくなります。登録ずみの ID はそのまま）。</p>'+
      '<div class="tool"><button class="btn" data-act="joinprint">配る紙を刷る</button>'+
        '<button class="btn soft" data-act="joincopy">リンクをコピーする</button>'+
        armBtn('joinnew', '作り直す', '本当に作り直す', 'joinnew', '', '')+'</div></div></div></div>';
}
function joinSheetHtml(){
  return '<div class="jsheet"><div class="js-brand"><span class="brand"><b>tube</b><i>study</i></span></div>'+
    '<h1>tube study の登録のご案内</h1>'+
    '<p class="js-lead">宿題を確かめる・出す・先生の添削を受け取る。保護者の方が、下の QR から登録してください（3分ほど）。</p>'+
    '<div class="js-qr">'+TubeQR.svg(joinLink(), 300)+'</div>'+
    '<div class="js-code">登録コード　<b>'+esc(S.st.join.code)+'</b></div>'+
    '<ol><li>スマートフォンのカメラで QR を読み、開いたページで「登録する」。</li>'+
    '<li>学年・クラス・受講科目を選ぶ（ごきょうだいは続けて登録できます）。</li>'+
    '<li>画面に出る <b>生徒ID</b> をメモし、合言葉を作る。</li></ol>'+
    '<p class="js-note">お名前・メールアドレス・電話番号は要りません。QR が読めないときは '+esc(location.host)+' を開き、「登録する」で登録コードを入れてください。</p></div>';
}
function tile(k, v, unit, s, tab){
  return '<button class="card tile" data-act="tab" data-v="'+tab+'"><div class="k">'+k+'</div>'+
    '<div class="v">'+v+'<small>'+unit+'</small></div><div class="s">'+esc(s)+'</div></button>';
}

/* --- 生徒（クラスごと。保護者が招待コードから登録した ID が並ぶ） --- */
var SUBJ1 = {japanese:'国', math:'数', english:'英', science:'理', social:'社'};
function subjShort(subs, grade){
  return (subs || []).map(function(x){ return (x === 'math' && /^e/.test(grade || '')) ? '算' : (SUBJ1[x] || ''); }).join('');
}
function findSeat(id){
  var hit = null;
  S.st.classes.forEach(function(c){ c.seats.forEach(function(x){ if(x.id === id) hit = {c:c, s:x}; }); });
  /* クラスの決まっていない生徒（卒業・新しい学年のクラスを聞いている）は、クラスの紙に無い */
  if(!hit) (S.st.loose || []).forEach(function(x){ if(x.id === id) hit = {c:{id:'', grade:x.grade, name:''}, s:x, loose:true}; });
  return hit;
}
function viewSeats(){
  var st = S.st;
  var anySpare = st.classes.some(function(c){ return seatCount(c).spare > 0; });
  var h = '<div class="sect"><h2>生徒</h2><div class="key"><span><i class="live"></i>使っている</span>'+
    (anySpare ? '<span><i></i>渡していない</span>' : '')+'<span><i class="left"></i>在籍終了</span></div></div>'+
    '<div class="tool find"><label for="findId">ID でさがす</label><input id="findId" class="mono" autocapitalize="none" autocorrect="off" spellcheck="false" value="'+esc(S.findId || '')+'">'+
    '<button class="btn sm soft" data-act="find">さがす</button></div>';
  var none = [];
  byGrade(st.classes, function(c){ return c.grade; }).forEach(function(g){
    var have = g.items.filter(function(c){ return c.seats.length; });
    none = none.concat(g.items.filter(function(c){ return !c.seats.length; }));
    if(!have.length) return;
    var liveN = have.reduce(function(a, c){ return a + seatCount(c).live; }, 0);
    h += '<div class="sect"><h3>'+esc(GRADE[g.g] || g.g)+'</h3>'+
      (g.items.length > 1 && liveN ? '<div class="right"><button class="lnk" data-act="moveopen" data-v="'+esc(g.g)+'">クラス替え</button></div>' : '')+
      '</div><div class="grid">';
    have.forEach(function(c){
      var n = seatCount(c);
      h += '<button class="card cls" data-act="cls" data-v="'+esc(c.id)+'"><div class="nm">'+esc(c.name)+'</div>'+
        '<div class="ct"><b>'+n.live+'</b>'+(n.spare ? '／'+(n.live + n.spare)+'席' : '人')+'</div>'+
        '<div class="dots">'+c.seats.map(function(s){ return '<i class="'+(s.st === 'live' ? 'live' : s.st === 'left' ? 'left' : '')+'"></i>'; }).join('')+'</div></button>';
    });
    h += '</div>';
  });
  var loose = st.loose || [];
  if(loose.length){
    h += '<div class="sect"><h3>クラスの決まっていない生徒</h3></div><div class="card exams loose">'+
      '<p class="small">学年が上がって、新しいクラスをまだ答えていない生徒と、卒業した生徒です。本人がホームで答えると、クラスの紙に移ります。</p>'+
      '<div class="spares">'+loose.map(function(x){
        return '<span class="exchip" id="row-'+esc(x.id)+'">'+esc(x.id)+'<span class="lz">'+esc(GRADE[x.grade] || x.grade)+'・'+(x.st === 'grad' ? '卒業' : 'クラスを聞いています')+'</span>'+
          '<button class="lnk" data-act="place" data-id="'+esc(x.id)+'">変える</button></span>';
      }).join('')+'</div></div>';
  }
  h += '<div class="sect"><h3>生徒のいないクラス</h3>'+
    '<div class="right"><button class="lnk" data-act="classopen">クラスを足す</button></div></div><div class="spares">'+
    (none.length ? none.map(function(c){ return '<button class="btn sm soft" data-act="cls" data-v="'+esc(c.id)+'">'+esc(c.name)+'</button>'; }).join('')
                 : '<span class="small">ありません</span>')+'</div>';
  return h;
}

function freshHtml(){
  var f = S.fresh; if(!f) return '';
  var link = f.kind === 'link';
  return '<div class="fresh"><h3>'+esc(f.title)+'</h3>'+
    (link
      ? '<p class="small">このリンクを、本人に送ってください（メール・授業のチャットなど）。<b>1回だけ使えます。7日で切れます。</b>'+
        '本人が開くと、その端末の中で本物の合言葉が作られます（サーバにも、このリンクにも、合言葉は載りません）。'+
        '先に別の人が開くと、本人は引き換えられません ―― そのときは、もう一度ここで渡し直します。</p>'
      : '<p class="small">この合言葉が読めるのは、いまだけです。表にコピーしてから閉じてください（サーバにあるのは、確かめるための値だけです）。</p>')+
    '<table>'+f.rows.map(function(r){
      return '<tr><td>'+esc(r.label)+'</td><td class="mono">'+esc(r.id)+'</td><td class="pw'+(link ? ' lk' : '')+'">'+esc(link ? r.link : r.pw)+'</td></tr>'; }).join('')+'</table>'+
    '<div class="tool">'+(link ? '<button class="btn warm" data-act="copymsg">送る文をコピーする</button>' : '')+
    '<button class="btn '+(link ? 'soft' : 'warm')+'" data-act="copy">'+(link ? 'リンクだけコピーする' : '表をコピーする')+'</button>'+
    '<button class="btn soft" data-act="csv">CSV で保存する</button>'+
    (link || S.selfReset ? '' : '<button class="btn soft" data-act="tocards">カードにする</button>')+
    '<button class="lnk" data-act="freshx">コピーした（閉じる）</button></div></div>';
}

function sheetHtml(){
  var sh = S.sheet, body = '';
  if(sh.kind === 'cls') body = sheetClass(sh.id);
  if(sh.kind === 'teacher') body = sheetTeacher(sh.id);
  if(sh.kind === 'csv') body = sheetCsv();
  if(sh.kind === 'move') body = sheetMove();
  if(sh.kind === 'newclass') body = sheetNewClass();
  if(sh.kind === 'admin') body = sheetAdmin(sh.id);
  if(sh.kind === 'named') body = sheetNamed(sh.key);
  if(sh.kind === 'place') body = sheetPlace();
  return '<div class="shade" data-act="close"></div><div class="sheet" role="dialog" aria-modal="true">'+body+'</div>';
}

function seatRow(s){
  var word = s.st === 'live' ? '<span class="word live">使っている</span>' : s.st === 'left' ? '<span class="word">在籍終了</span>'
           : s.st === 'pending' ? '<span class="word warm">登録の途中</span>' : '<span class="word">渡していない</span>';
  if(s.st !== 'left' && s.st !== 'pending') word += claimWord(s);
  if(s.st === 'live' && (s.subjects || []).length) word += '<span class="subs">'+esc(subjShort(s.subjects, s.grade))+'</span>';
  var main = s.st === 'spare' ? '<button class="btn sm" data-act="state" data-v="live" data-id="'+s.id+'">使う</button>'
           : s.st === 'left' ? '<button class="btn sm soft" data-act="state" data-v="live" data-id="'+s.id+'">在籍に戻す</button>' : '';
  var more = '';
  if(S.open === s.id){
    more = '<div class="more">'+
      (s.st === 'pending' ? '<span class="small">合言葉を作っている途中です。1時間たっても作られなければ、自動で消えます。</span>' : '')+
      (s.st !== 'left' && s.st !== 'pending' ? pwBtns(s.id, 'seat', (s.seat === s.id ? s.id : s.seat+'番'), s.st === 'live' || !!s.claim) : '')+
      (s.st === 'live' ? '<button class="btn sm soft" data-act="place" data-id="'+s.id+'">学年・クラス・科目を変える</button>' : '')+
      (s.st === 'live' && !s.last ? armBtn('spare:'+s.id, '渡していないに戻す', '本当に戻す', 'state', 'spare', s.id) : '')+
      (s.st === 'live' ? armBtn('left:'+s.id, '在籍終了にする', '本当に在籍終了にする', 'state', 'left', s.id) : '')+
      (s.st === 'spare' ? armBtn('del:'+s.id, 'この席を消す', '本当に消す', 'del', '', s.id) : '')+
      '</div>';
  }
  return '<div class="row'+(s.st === 'left' ? ' left' : '')+(S.findId === s.id ? ' hit' : '')+'" id="row-'+esc(s.id)+'"><span class="no">'+esc(s.seat === s.id ? '' : s.seat)+'</span><span class="id mono">'+esc(s.id)+'</span>'+word+
    '<span class="grow small">'+(s.last ? '最後に入った日 '+md(s.last) : (s.st === 'live' ? 'まだ入っていません' : ''))+
      (s.claimed && !s.claim ? '　引き換えた日 '+md(s.claimed) : '')+'</span>'+
    '<span class="acts">'+main+'<button class="lnk" data-act="more" data-id="'+s.id+'">'+(S.open === s.id ? 'とじる' : 'ほか')+'</button></span>'+more+'</div>';
}
/* 学年・クラス・受講科目を、管理者が直す（本人の設定と同じ道。ID と合言葉は変わらない）。 */
function sheetPlace(){
  var sh = S.sheet, st = S.st;
  var grades = []; st.classes.forEach(function(c){ if(/^(e[4-6]|j[1-3])$/.test(c.grade) && grades.indexOf(c.grade) < 0) grades.push(c.grade); });
  var cls = st.classes.filter(function(c){ return c.grade === sh.grade; });
  var combos = (st.combos || {})[(sh.grade || 'e')[0]] || [];
  var okSub = combos.some(function(c){ return c.join(',') === (sh.subjects || []).join(','); });
  var pick = function(act, val, on, label){ return '<button class="btn sm '+(on ? '' : 'soft')+'" data-act="'+act+'" data-v="'+esc(val)+'" aria-pressed="'+on+'">'+esc(label)+'</button>'; };
  return '<div class="hd"><h2>'+esc(sh.id)+' の 学年・クラス・科目</h2><button class="x" data-act="pback">もどる</button></div>'+
    '<p class="small">本人（保護者）も、設定から同じことができます。変えると、届く宿題が変わります。ID と合言葉は変わりません。</p>'+
    '<div class="sect"><h3>学年</h3></div><div class="spares">'+grades.map(function(g){ return pick('pgrade', g, sh.grade === g, GRADE[g] || g); }).join('')+'</div>'+
    '<div class="sect"><h3>クラス</h3></div><div class="spares">'+(cls.length ? cls.map(function(c){ return pick('pclass', c.id, sh.classId === c.id, c.name); }).join('') : '<span class="small">この学年のクラスがありません</span>')+'</div>'+
    '<div class="sect"><h3>受講科目</h3></div><div class="spares">'+combos.map(function(c, i){
      return pick('psubj', i, c.join(',') === (sh.subjects || []).join(','), subjShort(c, sh.grade)); }).join('')+'</div>'+
    '<div class="tool"><button class="btn" data-act="psave"'+(sh.classId && okSub ? '' : ' disabled')+'>この内容に変える</button></div>';
}
function armBtn(key, label, sure, act, v, id, extra){
  var on = S.arm === key;
  return '<button class="btn sm '+(on ? 'arm' : 'soft')+'" data-act="'+(on ? act : 'arm')+'" data-key="'+key+'" data-v="'+v+'" data-id="'+id+'"'+(extra || '')+'>'+(on ? sure : label)+'</button>';
}
/* 「オンラインで渡す」「合言葉を作り直す」：押した瞬間に、前の合言葉と開いている画面が止まる。だから2度押し。
   まだ渡していない席（spare）は、止まるものが無いので1度でよい。 */
function pwBtns(id, role, label, used){
  var ex = ' data-role="'+role+'" data-label="'+esc(label)+'"';
  if(!used){
    return '<button class="btn sm soft" data-act="online" data-id="'+id+'"'+ex+'>オンラインで渡す</button>'+
           '<button class="btn sm soft" data-act="repw" data-id="'+id+'"'+ex+'>合言葉を作り直す</button>';
  }
  return armBtn('on:'+id, 'オンラインで渡す', '本当に渡し直す（いまの合言葉は使えなくなります）', 'online', '', id, ex)+
         armBtn('pw:'+id, '合言葉を作り直す', '本当に作り直す（いまの合言葉は使えなくなります）', 'repw', '', id, ex);
}

function sheetClass(cid){
  var c = S.st.classes.filter(function(x){ return x.id === cid; })[0];
  if(!c) return '';
  var n = seatCount(c), spare = c.seats.filter(function(s){ return s.st === 'spare'; });
  /* まとめて使う：1回目で数を見せ、2回目で使う（1回の押しまちがいで、30席が名簿に出ないように）。 */
  var upKey = 'upto:' + cid, upOn = S.arm === upKey;
  var upVal = (S.upto && S.upto[cid]) || (spare.length ? spare[spare.length-1].seat.replace(/^0/,'') : '');
  var upCnt = spare.filter(function(s){ return parseInt(s.seat, 10) <= (parseInt(upVal, 10) || 0); }).length;
  c.seats.forEach(function(x){ x.grade = c.grade; });
  return '<div class="hd"><h2>'+esc(c.name)+'</h2><span class="dim num">'+(n.spare ? n.live+'／'+(n.live + n.spare)+'席 使っている' : n.live+'人')+'</span><button class="x" data-act="close">とじる</button></div>'+
    freshHtml()+
    '<div class="tool">'+
      (spare.length ? '<span>1番から</span><input id="upto" type="number" min="1" max="99" value="'+esc(upVal)+'"><span>番までを</span>'+
        '<button class="btn sm'+(upOn ? ' arm' : '')+'" data-act="'+(upOn ? 'upto' : 'arm')+'" data-key="'+upKey+'" data-v="'+esc(cid)+'">'+(upOn ? upCnt+'席を 使う（もう一度 押す）' : 'まとめて使う')+'</button>' : '')+
    '</div>'+
    '<p class="small">保護者が登録コードから登録した生徒が、ここに並びます（ID・受講科目・最後に入った日）。お名前はありません。'+
      (spare.length ? '「渡していない」は、前に作った席です（試し運用のあいだだけ）。' : '')+'</p>'+
    '<div class="rows">'+(c.seats.length ? c.seats.map(seatRow).join('') : '<div class="empty">このクラスには、まだ生徒がいません。</div>')+'</div>'+
    (c.seats.length ? '' : '<div class="tool">'+armBtn('cdel:'+c.id, 'このクラスを消す', '本当に消す', 'classdel', c.id, '')+'</div>');
}

/* --- 講師と担当 --- */
function viewStaff(){
  var st = S.st;
  var h = '<div class="sect"><h2>講師と担当</h2><div class="right"><button class="btn sm soft" data-act="addteacher"'+(S.busy ? ' disabled' : '')+'>'+(S.busy ? esc(S.busy) : '講師を足す')+'</button></div></div>'+freshHtml();
  h += '<div class="grid">'+st.teachers.map(function(t){
    var cn = st.courses.filter(function(c){ return c.teachers.indexOf(t.id) >= 0; }).map(function(c){ return c.name; });
    return '<button class="card cls'+(t.left ? ' off' : '')+'" data-act="teacher" data-v="'+esc(t.id)+'">'+
      '<div class="nm">'+(nameOf(t.id) ? esc(nameOf(t.id))+' <span class="mono small">'+esc(t.id)+'</span>' : '<span class="mono">'+esc(t.id)+'</span>')+'</div>'+
      '<div class="ct"><b>'+t.keys.length+'</b>コース</div>'+
      (cn.length ? '<div class="small">'+esc(cn.slice(0, 3).join('・'))+(cn.length > 3 ? ' ほか'+(cn.length - 3) : '')+'</div>' : '')+
      '<div class="small" style="margin-top:8px">'+(t.left ? '在籍終了' : t.last ? '最後に入った日 '+md(t.last) : 'まだ入っていません')+'</div>'+
      (t.left ? '' : claimWord(t))+'</button>';
  }).join('')+'</div>';
  h += '<div class="sect"><h3>管理者</h3><span class="small">このページに入れる人。2人いると、1人が入れなくなっても続けられます。</span>'+
    '<div class="right"><button class="lnk" data-act="addadmin">管理者を足す</button></div></div><div class="grid">'+
    st.admins.map(function(a){
      return '<button class="card cls'+(a.left ? ' off' : '')+'" data-act="adminopen" data-v="'+esc(a.id)+'"><div class="nm mono">'+esc(a.id)+'</div>'+
        '<div class="small" style="margin-top:8px">'+(a.me ? 'いま入っている自分' : a.left ? '在籍終了' : a.last ? '最後に入った日 '+md(a.last) : 'まだ入っていません')+'</div></button>';
    }).join('')+'</div>';
  h += '<div class="sect"><h2>コースごとの担当</h2><div class="right"><button class="lnk" data-act="csvopen">コースの表を直す</button></div></div>'+
       '<p class="small">講師を選ぶと、その場で決まります。新しいコースは「紙のまま」で入り、担当の講師が「導入と進度」で使い始めます。</p>';
  var opts = st.teachers.filter(function(t){ return !t.left; });
  byGrade(st.courses.filter(function(c){ return c.active; }), function(c){ return c.grade; }).forEach(function(g){
    h += '<div class="sect"><h3>'+esc(GRADE[g.g] || g.g)+'</h3></div>'+
      '<div class="th"><span>コース</span><span>時間</span><span>講師</span></div><div class="tbl">';
    g.items.forEach(function(c){
      var rest = opts.filter(function(t){ return c.teachers.indexOf(t.id) < 0; });
      h += '<div class="tr"><span class="nm">'+esc(c.name)+
        (c.classes.length ? '' : '　<button class="lnk" data-act="named" data-key="'+esc(c.key)+'">指名 '+c.n+'人</button>')+
        '</span><span class="small num">'+esc(c.slots || '時間は未定')+'</span>'+
        '<span class="chips">'+c.teachers.map(function(id){ return '<button class="chipx" data-act="unassign" data-key="'+esc(c.key)+'" data-id="'+esc(id)+'">'+esc(who(id))+'</button>'; }).join('')+
        (rest.length ? '<select data-act="assign" data-key="'+esc(c.key)+'"><option value="">'+(c.teachers.length ? '講師を足す' : '講師を選ぶ')+'</option>'+
          rest.map(function(t){ return '<option value="'+esc(t.id)+'">'+esc(who(t.id))+'</option>'; }).join('')+'</select>' : '')+
        '</span></div>';
    });
    h += '</div>';
  });
  return h;
}

function sheetTeacher(id){
  var st = S.st, t = st.teachers.filter(function(x){ return x.id === id; })[0];
  if(!t) return '';
  var h = '<div class="hd"><h2 class="mono">'+esc(t.id)+'</h2><span class="dim">'+(t.left ? '在籍終了' : t.keys.length+'コース')+'</span><button class="x" data-act="close">とじる</button></div>'+
    freshHtml()+
    '<div class="tool"><span>呼び名</span><input id="nick" type="text" maxlength="20" style="width:200px" value="'+esc(nameOf(t.id))+'" data-id="'+esc(t.id)+'">'+
      '<span class="small">この端末の中だけに残ります（サーバへは送りません）。だれの ID かを見分けるために。</span></div>'+
    '<div class="tool">'+
      (t.left ? '<button class="btn sm soft" data-act="state" data-v="live" data-id="'+t.id+'">在籍に戻す</button>'
              : pwBtns(t.id, 'teacher', '講師', !!t.last || !!t.claim)+
                armBtn('left:'+t.id, '在籍終了にする', '本当に在籍終了にする（担当から外れます）', 'state', 'left', t.id)+
                (!t.last ? armBtn('del:'+t.id, '消す', '本当に消す', 'del', '', t.id) : ''))+
    '</div>';
  if(t.left) return h;
  var mine = st.courses.filter(function(c){ return c.active && c.teachers.indexOf(t.id) >= 0; });
  if(mine.length){
    h += '<div class="sect"><h3>受け持つ生徒</h3><span class="small">コースごとに、宿題を受け取る生徒の ID</span></div><div class="rows">'+mine.map(function(c){
      return '<div class="row"><span class="id" style="min-width:150px;font-weight:600">'+esc(c.name)+'</span><span class="num">'+c.n+'人</span>'+
        '<span class="grow small mono" style="word-break:break-all">'+(c.ids.length ? esc(c.ids.join(' ')) : 'まだ、在籍の生徒がいません')+'</span></div>'; }).join('')+'</div>';
  }
  h += '<div class="sect"><h3>担当のコース</h3><span class="small">押すと、その場で担当に付きます。もう一度押すと外れます。</span></div>';
  byGrade(st.courses.filter(function(c){ return c.active; }), function(c){ return c.grade; }).forEach(function(g){
    h += '<div class="sect"><h3>'+esc(GRADE[g.g] || g.g)+'</h3></div><div class="chips">'+g.items.map(function(c){
      var on = c.teachers.indexOf(t.id) >= 0;
      return '<button class="btn sm '+(on ? '' : 'soft')+'" data-act="toggle" data-key="'+esc(c.key)+'" data-id="'+esc(t.id)+'" data-on="'+(on ? '0' : '1')+'" aria-pressed="'+on+'">'+esc(c.name)+'</button>';
    }).join('')+'</div>';
  });
  return h;
}

function sheetCsv(){
  return '<div class="hd"><h2>コースの表を直す</h2><button class="x" data-act="close">とじる</button></div>'+
    '<p class="small">表計算に貼って直し、ここに貼り戻して「入れる」。1行でもおかしければ、何も入りません。消したいコースは、行を消さずに「期間」の終わりを入れます。講師の欄はログインID、指名は「クラス-番号」。名前は書きません。</p>'+
    '<textarea id="csvText" spellcheck="false">'+esc(S.sheet.text || '')+'</textarea>'+
    (S.sheet.err ? '<div class="msg">'+esc(S.sheet.err)+'</div>' : '')+
    '<div class="tool"><button class="btn" data-act="csvsave">入れる</button><button class="btn soft" data-act="csvcopy">表をコピーする</button></div>';
}

/* --- 生徒に出ているもの --- */
var SORDER = {japanese:0, math:1, english:2, science:3, social:4};
function bySubject(a, b){ return (SORDER[a.subject] - SORDER[b.subject]) || (a.name < b.name ? -1 : 1); }
function viewOut(){
  var st = S.st;
  var h = '<div class="sect"><h2>生徒に出ているもの</h2></div>'+
    '<p class="small">クラスごとに、どの教科が・どの段階まで・いま何件の宿題が出ているか。段階を変えるのは、担当の講師（「導入と進度」）です。</p>';
  byGrade(st.classes, function(c){ return c.grade; }).forEach(function(g){
    var body = '';
    g.items.forEach(function(c){
      var n = seatCount(c);
      var cs = st.courses.filter(function(x){ return x.active && x.classes.indexOf(c.id) >= 0; }).sort(bySubject);
      body += '<div class="sect" style="margin-top:16px"><span style="font-weight:600;font-size:18px">'+esc(c.name)+'</span><span class="small num">使っている席 '+n.live+'</span></div>'+outTable(cs, false);
    });
    var named = st.courses.filter(function(x){ return x.active && !x.classes.length && x.grade === g.g; }).sort(bySubject);
    if(named.length){
      body += '<div class="sect" style="margin-top:16px"><span style="font-weight:600;font-size:18px">指名のコース</span><span class="small">土特・必勝・オンラインなど</span></div>'+outTable(named, true);
    }
    h += '<div class="sect"><h3>'+esc(GRADE[g.g] || g.g)+'</h3></div>'+body;
  });
  return h;
}
function outTable(cs, named){
  /* アプリで出ているコースだけを行にする。紙のままのコースは、名前を1行にまとめる（並べても読む所が無い）。 */
  var on = cs.filter(function(c){ return c.use > 0; }), paper = cs.filter(function(c){ return c.use === 0; });
  var h = '';
  if(on.length){
    h += '<div class="th prov"><span>'+(named ? 'コース' : '教科')+'</span><span>段階</span><span>いま出ている宿題</span><span>次の授業</span><span>講師</span></div><div class="tbl">'+
      on.map(function(c){
        var last = c.last ? ('最近：'+c.last.title) : 'まだ出ていません';
        return '<div class="tr prov"><span class="nm">'+esc(named ? c.name : subj(c))+(named ? '' : '<span class="small" style="font-weight:400">　'+esc(c.name)+'</span>')+'</span>'+
          '<span><span class="word u'+c.use+'">'+USE[c.use]+'</span></span>'+
          '<span><b class="num">'+c.open+'</b>件<span class="small">（'+c.n+'人に）</span><div class="small">'+esc(last)+'</div></span>'+
          '<span class="small">'+(c.next ? esc(mdw(c.next.date))+'　'+esc(c.next.unit || '') : (c.lessons ? '予定の終わりまで出ました' : '<span class="word warm">授業計画がまだ</span>'))+'</span>'+
          '<span class="small">'+(c.teachers.length ? esc(c.teachers.map(who).join('・')) : '<span class="word warm">講師がまだ</span>')+'</span></div>';
      }).join('')+'</div>';
  }
  if(paper.length){
    h += '<div class="paperline"><span class="word">紙のまま</span><span class="small">'+paper.map(function(c){ return esc(named ? c.name : subj(c)); }).join('・')+'</span></div>';
  }
  if(!cs.length) h = '<div class="paperline"><span class="small">このクラスを受け持つコースが、まだありません。</span></div>';
  return h;
}

/* --- カード（切って配る。QR を読むと、そのまま入れる） --- */
function cardLabel(id){
  var st = S.st, out = '';
  st.classes.forEach(function(c){ c.seats.forEach(function(x){ if(x.id === id) out = c.name + ' ' + x.seat + '番'; }); });
  if(!out && st.teachers.some(function(t){ return t.id === id; })) out = '講師';
  if(!out && st.admins.some(function(t){ return t.id === id; })) out = '管理者';
  return out;
}
/* 表から貼った行（タブ区切り・カンマ区切り）から、ID と合言葉の組を拾う。 */
function parseCards(text){
  var out = [], seen = {};
  String(text || '').split(/\r?\n/).forEach(function(line){
    var cells = line.split(/\t|,/).map(function(c){ return c.trim(); });
    for(var i = 1; i < cells.length; i++){
      if(/^([a-z]{3,8}-){2,5}\d{4}$/i.test(cells[i]) && /^[a-z0-9][a-z0-9._-]{1,31}$/i.test(cells[i - 1])){
        var id = cells[i - 1].toLowerCase();
        if(!seen[id]){ seen[id] = 1; out.push({id:id, pw:cells[i].toLowerCase(), label:cardLabel(id)}); }
        break;
      }
    }
  });
  return out;
}
function cardsHtml(rows){
  var host = location.host;
  return '<div class="pcards">'+rows.map(function(r){
    var admin = r.label === '管理者';
    var qr = TubeQR.svg(admin ? location.origin + '/admin' : linkOf(r.id, r.pw), 110);
    return '<div class="pcard"><div class="pc-l">'+
      '<div class="pc-b"><span class="brand"><b>tube</b><i>study</i></span><span class="pc-lab">'+esc(r.label || '')+'</span></div>'+
      '<div class="pc-k">ID</div><div class="pc-v">'+esc(r.id)+'</div>'+
      /* 折り返すのは、線（-）のあとだけ。数字4桁の途中で折らない。 */
      '<div class="pc-k">あいことば</div><div class="pc-v pc-pw'+(r.pw.length > 26 ? ' long' : '')+'">'+esc(r.pw).replace(/-/g, '-<wbr>')+'</div>'+
      '<div class="pc-u">'+esc(host + (admin ? '/admin' : ''))+'</div></div>'+
      '<div class="pc-r">'+qr+'<div class="pc-h">'+(admin ? 'カメラで読むと<br>入口が開きます' : 'カメラで読むと<br>そのまま入れます')+'</div></div></div>';
  }).join('')+'</div>';
}
function viewCards(){
  var rows = S.cards || [];
  var h = '<div class="sect"><h2>カード</h2></div>'+
    '<p class="small">合言葉の表（スプレッドシート）から、配りたい行をコピーして、下に貼ってください。切って配るカードになります（A4 に 10枚）。'+
    '貼った合言葉は、この画面の中だけで使います（サーバへは送りません）。刷り終えたら「消す」を押してください。</p>'+
    '<textarea id="cardText" class="short" spellcheck="false" placeholder="01	we4a01	neko-yama-sora-4821">'+esc(S.cardText || '')+'</textarea>'+
    '<div class="tool"><button class="btn" data-act="cardmake">カードにする</button>'+
    (rows.length ? '<button class="btn warm" data-act="cardprint">刷る（'+rows.length+'枚）</button><button class="btn soft" data-act="cardclear">消す</button>' : '')+'</div>';
  if(rows.length){
    h += '<div class="sect"><h3>できあがり（'+rows.length+'枚）</h3><span class="small">カードの合言葉は、紙に刷るときだけ出ます。QR を読むと、入口が開いてそのまま入れます。</span></div>'+
      '<div class="cprev">'+cardsHtml(rows)+'</div>';
  }
  return h;
}

/* --- クラス替え --- */
function sheetMove(){
  var sh = S.sheet, st = S.st, g = sh.grade;
  var cls = st.classes.filter(function(c){ return c.grade === g; });
  var cname = {}; cls.forEach(function(c){ cname[c.id] = c.name; });
  var h = '<div class="hd"><h2>クラス替え（'+esc(GRADE[g] || g)+'）</h2><button class="x" data-act="close">とじる</button></div>';
  if(sh.done){
    h += '<div class="fresh"><h3>移しました（'+sh.done.moves.length+'人）</h3>'+
      '<p class="small">ID と合言葉は変わりません。記録もそのままです。先生の手元の名簿（対応表）も、同じように直してください。</p>'+
      '<table>'+sh.done.moves.map(function(m){ return '<tr><td class="mono">'+esc(m.id)+'</td><td>'+esc(cname[m.from.classId] || m.from.classId)+'-'+esc(m.from.seat)+'</td><td>→　'+esc(cname[m.to.classId] || m.to.classId)+'-'+esc(m.to.seat)+'</td></tr>'; }).join('')+'</table>'+
      '<div class="tool"><button class="btn warm" data-act="movecopy">表をコピーする</button><button class="lnk" data-act="moveback">つづけて替える</button></div></div>';
    return h;
  }
  if(sh.preview){
    var pv = sh.preview;
    h += '<p class="small">まだ移していません。よければ「移す」を押してください。ID・合言葉・記録は変わりません。</p><div class="rows">'+
      pv.moves.map(function(m){
        var w = [];
        if(m.hw.out) w.push('前のクラスの宿題から外す '+m.hw.out+'件');
        if(m.hw['in']) w.push('新しいクラスの宿題に足す '+m.hw['in']+'件');
        if(m.hw.keep) w.push('記録があるので残す '+m.hw.keep+'件');
        return '<div class="row"><span class="id mono">'+esc(m.id)+'</span><span>'+esc(cname[m.from.classId] || m.from.classId)+'-'+esc(m.from.seat)+'　→　<b>'+esc(cname[m.to.classId] || m.to.classId)+'-'+esc(m.to.seat)+'</b></span>'+
          '<span class="grow small">'+esc(w.join('・') || '宿題の付け替えなし')+'</span></div>';
      }).join('')+'</div>'+
      (pv.notes.length ? '<div class="msg">'+esc(pv.notes.join('\n'))+'</div>' : '')+
      '<div class="tool"><button class="btn" data-act="movego">移す（'+pv.moves.length+'人）</button><button class="btn soft" data-act="moveback">もどる</button></div>';
    return h;
  }
  var n = Object.keys(sh.pick).length;
  h += '<p class="small">行き先のクラスを選び、「確かめる」を押します。番号は、行き先で空いている番号（今の番号が空いていれば、今の番号）になります。</p>'+
    '<div class="tool"><button class="btn" data-act="movecheck"'+(n ? '' : ' disabled')+'>確かめる（'+n+'人）</button></div>';
  cls.forEach(function(c){
    var live = c.seats.filter(function(x){ return x.st === 'live'; });
    if(!live.length) return;
    h += '<div class="sect"><h3>'+esc(c.name)+'</h3><span class="small num">'+live.length+'人</span></div><div class="rows">'+
      live.map(function(x){
        var to = sh.pick[x.id] || c.id;
        return '<div class="row"><span class="no">'+esc(x.seat)+'</span><span class="id mono">'+esc(x.id)+'</span><span class="grow"></span>'+
          '<select data-act="movepick" data-id="'+esc(x.id)+'" data-from="'+esc(c.id)+'">'+cls.map(function(k){
            return '<option value="'+esc(k.id)+'"'+(k.id === to ? ' selected' : '')+'>'+(k.id === c.id ? 'このまま' : esc(k.name)+' へ')+'</option>'; }).join('')+'</select></div>';
      }).join('')+'</div>';
  });
  if(sh.batches && sh.batches.length){
    h += '<div class="sect"><h3>これまでのクラス替え</h3></div><div class="rows">'+sh.batches.map(function(b){
      var d = new Date(b.at * 1000);
      return '<div class="row"><span class="grow">'+(d.getMonth()+1)+'/'+d.getDate()+'　'+b.n+'人</span><span class="acts">'+
        armBtn('undo:'+b.batch, '取り消す', '本当に取り消す（前のクラスに戻す）', 'moveundo', b.batch, '')+'</span></div>'; }).join('')+'</div>';
  }
  return h;
}

/* --- クラスを足す --- */
function sheetNewClass(){
  var sh = S.sheet;
  return '<div class="hd"><h2>クラスを足す</h2><button class="x" data-act="close">とじる</button></div>'+
    '<p class="small">講習や、新しく分けたクラスを足します。足したあと、席を作り、「コースの表を直す」でコースに入れます。</p>'+
    '<div class="tool"><span>学年</span><select id="ncGrade">'+Object.keys(GRADE).map(function(g){ return '<option value="'+g+'"'+(sh.grade === g ? ' selected' : '')+'>'+GRADE[g]+'</option>'; }).join('')+'</select>'+
    '<span>記号（英小文字）</span><input id="ncTail" type="text" maxlength="6" style="width:110px" autocapitalize="none" spellcheck="false" value="'+esc(sh.tail || '')+'">'+
    '<span>名前</span><input id="ncName" type="text" maxlength="16" style="width:160px" value="'+esc(sh.name || '')+'" placeholder="小4S"></div>'+
    '<p class="small">ID は「学年＋記号」になります（小4 で記号 s なら e4s。席の ID は '+esc(S.st.school.code)+'e4s01 …）。あとから変えられません。</p>'+
    (sh.err ? '<div class="msg">'+esc(sh.err)+'</div>' : '')+
    '<div class="tool"><button class="btn" data-act="classadd">足す</button></div>';
}

/* --- 指名のコース（土特・必勝・オンラインなど）に入る生徒 --- */
function sheetNamed(key){
  var st = S.st, c = st.courses.filter(function(x){ return x.key === key; })[0];
  if(!c) return '';
  var h = '<div class="hd"><h2>'+esc(c.name)+'</h2><span class="dim">指名 '+c.n+'人</span><button class="x" data-act="close">とじる</button></div>'+
    '<p class="small">このコースの宿題を受け取る生徒を選びます。押すと、その場で入ります。もう一度押すと外れます（出したあとの宿題は残ります）。'+
    '並ぶのは、在籍の生徒だけです（まだ渡していない席は、先に「使う」にします）。</p>';
  var any = false;
  st.classes.filter(function(k){ return c.grades.indexOf(k.grade) >= 0; }).forEach(function(k){
    var live = k.seats.filter(function(x){ return x.st === 'live'; });
    if(!live.length) return;
    any = true;
    h += '<div class="sect"><h3>'+esc(k.name)+'</h3></div><div class="chips">'+live.map(function(x){
      var on = c.ids.indexOf(x.id) >= 0;
      return '<button class="btn sm '+(on ? '' : 'soft')+' mono" data-act="namedtoggle" data-key="'+esc(key)+'" data-id="'+esc(x.id)+'" data-on="'+(on ? '0' : '1')+'" aria-pressed="'+on+'">'+esc(x.seat)+'　'+esc(x.id)+'</button>';
    }).join('')+'</div>';
  });
  if(!any) h += '<div class="empty">この学年には、まだ在籍の生徒がいません。</div>';
  return h;
}

/* --- 管理者 --- */
function sheetAdmin(id){
  var a = S.st.admins.filter(function(x){ return x.id === id; })[0];
  if(!a) return '';
  return '<div class="hd"><h2 class="mono">'+esc(a.id)+'</h2><span class="dim">管理者'+(a.me ? '（自分）' : '')+'</span><button class="x" data-act="close">とじる</button></div>'+
    freshHtml()+
    '<div class="tool">'+
      (a.left ? '<button class="btn sm soft" data-act="state" data-v="live" data-id="'+a.id+'">在籍に戻す</button>'
              : armBtn('pw:'+a.id, '合言葉を作り直す', '本当に作り直す（いまの合言葉は使えなくなります）', 'repw', '', a.id, ' data-role="admin" data-label="管理者"')+
                (a.me ? '' : armBtn('left:'+a.id, '在籍終了にする', '本当に在籍終了にする', 'state', 'left', a.id)+
                             (!a.last ? armBtn('del:'+a.id, '消す', '本当に消す', 'del', '', a.id) : '')))+
    '</div>'+
    (a.me ? '<p class="small">自分の合言葉を作り直すと、新しい合言葉が1回だけ出ます。表に貼ってから閉じてください。</p>' : '');
}

/* --- 報告 --- */
function viewRep(){
  var h = '<div class="sect"><h2>報告</h2><div class="right seg"><button class="'+(S.repAll ? '' : 'on')+'" data-act="repf" data-v="0">見ていない</button><button class="'+(S.repAll ? 'on' : '')+'" data-act="repf" data-v="1">ぜんぶ</button></div></div>'+
    '<p class="small">生徒や講師が「うまく動かないとき」から書いたもの、画面が自分で拾ったエラー、入口の見張り（まちがった合言葉が続いて、しばらく入れなくした ID）が、ここに集まります。名前は入りません（役割・クラス・番号まで）。</p>';
  if(!S.reports){ loadReports(); return h + '<div class="empty">よみこんでいます</div>'; }
  var items = S.reports.filter(function(r){ return S.repAll || r.state !== 'done'; });
  if(!items.length) return h + '<div class="card empty">'+(S.repAll ? '報告は、まだありません。' : 'まだ見ていない報告は、ありません。')+'</div>';
  var cname = {}; S.st.classes.forEach(function(c){ cname[c.id] = c.name; });
  h += '<div class="grid wide">'+items.map(function(r){
    var whom = r.kind === 'guard' ? '' : r.role === 'teacher' ? '講師' : r.role === 'admin' ? '管理者' : ((cname[r.classId] || r.classId || '') + '-' + (r.seat || ''));
    var d = new Date((r.lastAt || r.at) * 1000);
    var when = (d.getMonth()+1)+'/'+d.getDate()+' '+('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2);
    return '<div class="card rep'+(r.state === 'done' ? ' done' : '')+'">'+
      '<div class="tx"><span class="word '+(r.kind === 'say' ? 'warm' : '')+'">'+(r.kind === 'error' ? '画面のエラー'+(r.n > 1 ? ' ×'+r.n : '') : r.kind === 'guard' ? '入口の見張り'+(r.n > 1 ? ' ×'+r.n : '') : '書いてくれた')+'</span>'+
        '<div style="margin-top:8px">'+esc(r.text)+'</div>'+
        '<div class="mt">'+(whom ? esc(whom)+'　' : '')+esc(VIEW_JP[r.view] || r.view || '')+'　'+when+'　'+esc(device(r.ua))+(r.note ? '　メモ：'+esc(r.note) : '')+'</div></div>'+
      '<button class="btn sm '+(r.state === 'done' ? 'soft' : '')+'" data-act="repdone" data-id="'+esc(r.id)+'" data-v="'+(r.state === 'done' ? 'open' : 'done')+'">'+(r.state === 'done' ? '見ていないに戻す' : '済みにする')+'</button></div>';
  }).join('')+'</div>';
  return h;
}
var VIEW_JP = {login:'入口', today:'ホーム', homework:'宿題', daily:'毎日テスト', record:'先生から', settings:'設定', parent:'保護者の方へ',
  hw:'今日やること', roster:'成績', progress:'導入と進度', check:'宿題チェック', mats:'教材をえらぶ', people:'名簿', admin:'記録の書き出し',
  apps:'導入の段階', report:'うまく動かないとき', login:'入口', newpw:'あたらしい合言葉', claim:'引き換え'};
function device(ua){
  ua = ua || '';
  var d = /iPhone/.test(ua) ? 'iPhone' : /iPad/.test(ua) ? 'iPad' : /Android/.test(ua) ? 'Android' : /Macintosh/.test(ua) ? 'Mac' : /Windows/.test(ua) ? 'Windows' : '';
  var b = /Edg\//.test(ua) ? 'Edge' : /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : /Firefox\//.test(ua) ? 'Firefox' : '';
  return (d + ' ' + b).trim();
}
async function loadReports(){
  var r = await api('GET', '/admin/reports');
  if(r.ok){ S.reports = r.data.items || []; if(S.tab === 'rep') render(); }
}

/* ---------- 操作 ---------- */
async function doLogin(){
  var id = ($('#gId').value || '').trim(), pw = $('#gPw').value || '';
  if(!id || !pw){ S.msg = (!id ? 'ID' : '合言葉') + 'が入っていません。'; render(); $(!id ? '#gId' : '#gPw').focus(); return; }
  $('#gGo').disabled = true; $('#gGo').textContent = '確かめています';
  /* 合言葉そのものは送らない（js/scram.js）。 */
  var r = await TubeScram.login(function(path, body){ return api('POST', path, body); }, id, pw, {admin:true});
  if(!r.ok){
    if(r.token){ S.tok = r.token; await api('POST', '/logout'); S.tok = null; }
    S.msg = r.error || '入れませんでした'; render(); return;
  }
  if(!r.data.profile || r.data.profile.role !== 'admin'){
    S.tok = r.data.token; await api('POST', '/logout'); S.tok = null;
    S.msg = 'このページは、管理する人だけが入れます。'; render(); return;
  }
  S.tok = r.data.token; ssSet(S.tok); S.msg = '';
  await reload(true);
}

function freshSet(title, rows, kind){
  /* リンクを続けて作ったときは、同じ札に足していく（まとめてコピーできるように）。 */
  if(kind === 'link' && S.fresh && S.fresh.kind === 'link'){ S.fresh.rows = S.fresh.rows.concat(rows); return; }
  S.fresh = {title:title, rows:rows, kind:kind || 'pw'};
}
function freshText(sep){
  var link = S.fresh.kind === 'link';
  return S.fresh.rows.map(function(r){ return [r.label, r.id, link ? r.link : r.pw].join(sep); }).join('\n');
}
/* オンラインで渡す：1回だけ使える言葉を作り、リンクにする。本人が開くと、その端末が本物の合言葉を作る。 */
async function issueLink(id, role, label){
  S.arm = null;
  try{
    var m = await makeMany(role === 'teacher' ? 'teacher' : 'seat', 1);
    var r = await api('POST', '/admin/accounts/'+encodeURIComponent(id)+'/password', {verifier:m.vs[0], claim:true});
    if(!r.ok){ toast(r.data.error || 'できませんでした'); return; }
    var lab = cardLabel(id) || label;
    freshSet('オンラインで渡すリンク', [{label:lab, id:id, pw:m.pws[0], link:linkOf(id, m.pws[0])}], 'link');
    S.open = null;
    await reload(true);
  }catch(e){ toast(e.message || String(e)); }
}
async function addAdmin(){
  try{
    S.busy = '作っています'; render();
    var m = await makeMany('admin', 1);
    var r = await api('POST', '/admin/admins', {verifiers:m.vs});
    S.busy = false;
    if(take(r)) freshSet('足した管理者', r.data.made.map(function(x, i){ return {label:'管理者', id:x.id, pw:m.pws[i]}; }));
  }catch(e){ S.busy = false; toast(e.message || String(e)); }
  render();
}
/* クラス替え */
function moveRows(){
  var sh = S.sheet;
  return Object.keys(sh.pick).map(function(id){ return {id:id, classId:sh.pick[id]}; });
}
async function moveCheck(apply){
  var sh = S.sheet, body = {rows: apply ? sh.preview.moves.map(function(m){ return {id:m.id, classId:m.to.classId, seat:m.to.seat}; }) : moveRows(), dry:!apply};
  var r = await api('POST', '/admin/moves', body);
  if(!r.ok){ toast(r.data.error || 'できませんでした'); return; }
  if(r.data.state) S.st = r.data.state;
  if(apply){ sh.done = {moves:r.data.moves, batch:r.data.batch}; sh.preview = null; sh.pick = {}; loadBatches(); }
  else{
    if(!r.data.moves.length){ toast('移る生徒はいません。'); return; }
    sh.preview = r.data;
  }
  render();
}
async function loadBatches(){
  var r = await api('GET', '/admin/moves');
  if(r.ok && S.sheet && S.sheet.kind === 'move'){ S.sheet.batches = r.data.items || []; render(); }
}
async function moveUndo(batch){
  var r = await api('POST', '/admin/moves/undo', {batch:batch, dry:false});
  S.arm = null;
  if(!r.ok){ toast(r.data.error || '取り消せませんでした'); render(); return; }
  if(r.data.state) S.st = r.data.state;
  toast('取り消しました（'+r.data.n+'人が前のクラスに戻りました）');
  loadBatches(); render();
}
async function classAdd(){
  var sh = S.sheet;
  sh.grade = $('#ncGrade').value; sh.tail = ($('#ncTail').value || '').trim().toLowerCase(); sh.name = ($('#ncName').value || '').trim();
  var r = await api('POST', '/admin/classes', {id:sh.grade + sh.tail, name:sh.name});
  if(!r.ok){ sh.err = r.data.error || '足せませんでした'; render(); return; }
  S.st = r.data.state; S.sheet = {kind:'cls', id:r.data.id}; render();
}
async function classDel(cid){
  var r = await api('DELETE', '/admin/classes/'+encodeURIComponent(cid));
  S.arm = null;
  if(take(r)) S.sheet = null;
  render();
}

async function addTeacher(){
  try{
    S.busy = '作っています'; render();
    var m = await makeMany('teacher', 1);
    var r = await api('POST', '/admin/teachers', {verifiers:m.vs});
    S.busy = false;
    if(take(r)) freshSet('足した講師', r.data.made.map(function(x, i){ return {label:'講師', id:x.id, pw:m.pws[i]}; }));
  }catch(e){ S.busy = false; toast(e.message || String(e)); }
  render();
}
async function rePw(id, role, label){
  S.arm = null;
  try{
    var me = id === S.st.me;
    var m = await makeMany(me ? 'admin' : role, 1);
    var r = await api('POST', '/admin/accounts/'+encodeURIComponent(id)+'/password', {verifier:m.vs[0]});
    if(!r.ok){ toast(r.data.error || 'できませんでした'); return; }
    freshSet('作り直した合言葉（前の合言葉は、もう使えません）', [{label:label, id:id, pw:m.pws[0]}]);
    S.open = null;
    if(me) S.selfReset = true;
    if(!me) await reload(true); else render();
  }catch(e){ toast(e.message || String(e)); }
}
async function setState(ids, want){
  var r = await api('POST', '/admin/accounts/state', {ids:ids, state:want});
  S.arm = null;
  if(take(r)){
    var sk = r.data.skipped || [];
    if(sk.length) toast(sk.length === 1 ? sk[0].why : (r.data.done.length+'件 変えました。'+sk.length+'件は変えていません（'+sk[0].why+'）'));
    var dr = r.data.dropped || {}, keys = Object.keys(dr).reduce(function(a, k){ return a.concat(dr[k]); }, []);
    if(keys.length) toast('担当から外しました：'+keys.length+'コース');
    if(S.sheet && S.sheet.kind === 'teacher' && want !== 'live') S.open = null;
  }
  render();
}
async function del(id){
  var r = await api('DELETE', '/admin/accounts/'+encodeURIComponent(id));
  S.arm = null; S.open = null;
  if(take(r) && S.sheet && S.sheet.kind === 'teacher') S.sheet = null;
  render();
}
async function assign(key, id, on){
  var r = await api('PUT', '/admin/courses/teacher', {key:key, id:id, on:on});
  take(r); render();
}

document.addEventListener('click', function(e){
  var t = e.target.closest('[data-act]'); if(!t || t.tagName === 'SELECT') return;
  var act = t.getAttribute('data-act'), v = t.getAttribute('data-v'), id = t.getAttribute('data-id'), key = t.getAttribute('data-key');
  if(t.disabled) return;
  if(act !== 'arm' && act !== 'state' && act !== 'del' && act !== 'moveundo' && act !== 'classdel' && act !== 'online' && act !== 'repw' && act !== 'upto' && act !== 'joinnew') S.arm = null;
  /* 合言葉を出しているあいだは、よそへ移らせない（移ると、もう読めない）。 */
  if(S.fresh && (act === 'tab' || act === 'cls' || act === 'teacher' || act === 'out' || act === 'csvopen' ||
                 act === 'moveopen' || act === 'classopen' || act === 'adminopen' || act === 'named')){
    toast((S.fresh.kind === 'link' ? 'リンク' : '合言葉')+'をコピーしてから「コピーした（閉じる）」を押してください。'); return;
  }
  /* カードのタブを離れるときは、貼った合言葉を消す（画面に残さない）。 */
  if(act === 'tab' && S.tab === 'cards' && v !== 'cards'){ S.cards = null; S.cardText = ''; }
  if(act === 'login') return doLogin();
  if(act === 'out'){ api('POST', '/logout').then(function(){ S.tok = null; ssSet(null); S.st = null; S.sheet = null; S.fresh = null; S.cards = null; S.cardText = ''; S.msg = ''; render(); }); return; }
  /* 開くたびに、今の状態を取り直す（ほかの窓や、生徒が入ったことで変わっている）。まず手元の控えで描き、届いたら描き直す。 */
  if(act === 'tab'){ S.tab = v; S.sheet = null; S.open = null; if(v === 'rep') S.reports = null; window.scrollTo(0, 0); render(); reload(); return; }
  if(act === 'cls'){ S.sheet = {kind:'cls', id:v}; S.open = null; render(); reload(); return; }
  if(act === 'teacher'){ S.sheet = {kind:'teacher', id:v}; S.open = null; render(); reload(); return; }
  if(act === 'close'){
    if(S.fresh){ toast((S.fresh.kind === 'link' ? 'リンク' : '合言葉')+'をコピーしてから「コピーした（閉じる）」を押してください。'); return; }
    S.sheet = null; S.open = null; return render();
  }
  if(act === 'more'){ S.open = S.open === id ? null : id; return render(); }
  if(act === 'arm'){
    /* まとめて使う：打った番号を覚えてから描き直す（描き直すと、欄がはじめの値に戻るため）。 */
    if(key.indexOf('upto:') === 0){ S.upto = S.upto || {}; S.upto[v] = ($('#upto') || {}).value || ''; }
    S.arm = key; render(); setTimeout(function(){ if(S.arm === key){ S.arm = null; render(); } }, 5000); return; }
  if(act === 'state') return setState([id], v);
  if(act === 'find'){
    var want = (($('#findId') || {}).value || '').trim().toLowerCase();
    S.findId = want;
    var hit = want ? findSeat(want) : null;
    if(!hit){ toast(want ? 'その ID の生徒は、いません。' : 'ID を入れてください。'); return render(); }
    S.sheet = hit.loose ? null : {kind:'cls', id:hit.c.id}; S.open = want; render();
    setTimeout(function(){ var el = document.getElementById('row-' + want); if(el && el.scrollIntoView) el.scrollIntoView({block:'center'}); }, 80);
    return;
  }
  if(act === 'place'){
    var hs = findSeat(id); if(!hs) return;
    S.sheet = {kind:'place', id:id, back:hs.c.id, grade:hs.c.grade, classId:hs.c.id, subjects:(hs.s.subjects || []).slice()};
    S.open = null; return render();
  }
  if(act === 'pgrade'){ if(S.sheet.grade !== v){ S.sheet.grade = v; S.sheet.classId = ''; } return render(); }
  if(act === 'pclass'){ S.sheet.classId = v; return render(); }
  if(act === 'psubj'){ S.sheet.subjects = (S.st.combos[S.sheet.grade[0]] || [])[+v].slice(); return render(); }
  if(act === 'pback'){ S.sheet = S.sheet.back ? {kind:'cls', id:S.sheet.back} : null; return render(); }
  if(act === 'psave'){
    var sh = S.sheet;
    api('PUT', '/admin/accounts/'+encodeURIComponent(sh.id)+'/placement', {grade:sh.grade, classId:sh.classId, subjects:sh.subjects}).then(function(r){
      if(!r.ok){ toast(r.data.error || 'できませんでした'); return; }
      S.st = r.data.state; S.sheet = {kind:'cls', id:sh.classId}; S.open = sh.id; S.findId = sh.id;
      toast((r.data.changed || []).length ? '変えました' : '変わるものは、ありませんでした'); render();
    });
    return;
  }
  if(act === 'del') return del(id);
  if(act === 'upto'){
    S.arm = null;
    var n = parseInt(($('#upto') || {}).value, 10) || 0;
    var c = S.st.classes.filter(function(x){ return x.id === v; })[0];
    var ids = c.seats.filter(function(s){ return s.st === 'spare' && parseInt(s.seat, 10) <= n; }).map(function(s){ return s.id; });
    if(!ids.length){ toast('その番号までに、渡していない席はありません。'); return; }
    return setState(ids, 'live');
  }
  if(act === 'addteacher') return addTeacher();
  if(act === 'addadmin') return addAdmin();
  if(act === 'adminopen'){ S.sheet = {kind:'admin', id:v}; S.open = null; return render(); }
  if(act === 'online') return issueLink(id, t.getAttribute('data-role'), t.getAttribute('data-label'));
  if(act === 'tocards'){
    S.cards = S.fresh.rows.map(function(r){ return {id:r.id, pw:r.pw, label:cardLabel(r.id) || r.label}; });
    S.fresh = null; S.sheet = null; S.tab = 'cards'; window.scrollTo(0, 0); return render();
  }
  if(act === 'cardmake'){
    S.cardText = ($('#cardText') || {}).value || '';
    var rows = parseCards(S.cardText);
    if(!rows.length){ toast('ID と合言葉の組が見つかりません。表の行（ID と合言葉の列）をコピーして貼ってください。'); return; }
    S.cards = rows; return render();
  }
  if(act === 'cardprint'){ window.print(); return; }
  if(act === 'joinnew'){
    S.arm = null;
    api('POST', '/admin/join/code', {}).then(function(r){
      if(!r.ok){ toast(r.data.error || 'できませんでした'); return; }
      S.st = r.data.state; toast('登録コードを作りました'); render();
    });
    return;
  }
  if(act === 'yearset' || act === 'yeardel'){
    var yv = act === 'yeardel' ? '' : (($('#yrDate') || {}).value || '');
    if(act === 'yearset' && !/^\d{4}-\d{2}-\d{2}$/.test(yv)){ toast('はじまりの日を選んでください。'); return; }
    api('PUT', '/admin/exams', {yearStart:yv}).then(function(r){
      if(!r.ok){ toast(r.data.error || 'できませんでした'); return; }
      S.st = r.data.state; toast(yv ? '入れました。その日の朝に、学年が上がります。' : '外しました。'); render();
    });
    return;
  }
  if(act === 'examadd' || act === 'examdel' || act === 'examdays'){
    var ex0 = S.st.exams || {items:[], resultDays:7};
    var list = ex0.items.map(function(e){ return {date:e.date, name:e.name}; });
    var days = ex0.resultDays;
    if(act === 'examadd'){
      var dv = ($('#exDate') || {}).value || '';
      if(!/^\d{4}-\d{2}-\d{2}$/.test(dv)){ toast('テストの日を選んでください。'); return; }
      if(list.some(function(e){ return e.date === dv; })){ toast('その日は、もう入っています。'); return; }
      list.push({date:dv});
    }
    if(act === 'examdel') list = list.filter(function(e){ return e.date !== v; });
    if(act === 'examdays'){
      days = parseInt(($('#exDays') || {}).value, 10);
      if(!(days >= 0 && days <= 21)){ toast('0〜21 の数で入れてください。'); return; }
    }
    return saveExams(list, days);
  }
  if(act === 'joinprint'){ S.printJoin = true; render(); setTimeout(function(){ window.print(); }, 60); return; }
  if(act === 'joincopy'){ (navigator.clipboard ? navigator.clipboard.writeText(joinLink()) : Promise.reject()).then(function(){ toast('リンクをコピーしました。'); }, function(){ toast('コピーできませんでした。'); }); return; }
  if(act === 'cardclear'){ S.cards = null; S.cardText = ''; return render(); }
  if(act === 'moveopen'){ S.sheet = {kind:'move', grade:v, pick:{}, preview:null, done:null, batches:null}; render(); loadBatches(); return; }
  if(act === 'movecheck') return moveCheck(false);
  if(act === 'movego') return moveCheck(true);
  if(act === 'moveback'){ S.sheet.preview = null; S.sheet.done = null; return render(); }
  if(act === 'moveundo') return moveUndo(v);
  if(act === 'movecopy'){
    var cn = {}; S.st.classes.forEach(function(c){ cn[c.id] = c.name; });
    var tx2 = S.sheet.done.moves.map(function(m){ return [m.id, (cn[m.from.classId] || m.from.classId)+'-'+m.from.seat, (cn[m.to.classId] || m.to.classId)+'-'+m.to.seat].join('\t'); }).join('\n');
    (navigator.clipboard ? navigator.clipboard.writeText(tx2) : Promise.reject()).then(function(){ toast('コピーしました。'); }, function(){ toast('コピーできませんでした。'); });
    return;
  }
  if(act === 'classopen'){ S.sheet = {kind:'newclass', grade:'e4', tail:'', name:''}; return render(); }
  if(act === 'classadd') return classAdd();
  if(act === 'classdel') return classDel(v);
  if(act === 'repw') return rePw(id, t.getAttribute('data-role'), t.getAttribute('data-label'));
  if(act === 'toggle') return assign(key, id, t.getAttribute('data-on') === '1');
  if(act === 'named'){ S.sheet = {kind:'named', key:key}; S.open = null; render(); reload(); return; }
  if(act === 'namedtoggle'){
    api('PUT', '/admin/courses/student', {key:key, id:id, on:t.getAttribute('data-on') === '1'}).then(function(r){ take(r); render(); });
    return;
  }
  if(act === 'unassign') return assign(key, id, false);
  if(act === 'copy'){
    var text = freshText('\t');
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(
      function(){ toast('コピーしました。表に貼ってください。'); },
      function(){ toast('コピーできませんでした。「CSV で保存する」を使ってください。'); });
    return;
  }
  if(act === 'csv'){
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['﻿' + freshText(',') + '\n'], {type:'text/csv'}));
    a.download = 'tubestudy-aikotoba.csv'; document.body.appendChild(a); a.click(); a.remove();
    return;
  }
  if(act === 'copymsg'){
    /* 本人（か保護者）に、そのまま送れる文。リンクは1回だけ・7日まで。 */
    var until = new Date(Date.now() + 7 * 86400000);
    var msg = S.fresh.rows.map(function(r){
      return 'TUBE study の入口です（ID：'+r.id+'）。\n'+
        '下のリンクを、お子さんが使う端末（スマホ・タブレット・パソコン）で開き、「はじめる」を押してください。\n'+
        'その端末で合言葉が作られ、画面に1回だけ出ます。紙に書きとめてから進んでください（次に入るときに使います）。\n'+
        'リンクは1回だけ使えます（'+(until.getMonth()+1)+'月'+until.getDate()+'日まで）。開いても入れないときは、もう一度送りますのでお知らせください。\n'+
        r.link;
    }).join('\n\n');
    (navigator.clipboard ? navigator.clipboard.writeText(msg) : Promise.reject()).then(
      function(){ toast('送る文をコピーしました。メールやチャットに貼ってください。'); },
      function(){ toast('コピーできませんでした。リンクを選んでコピーしてください。'); });
    return;
  }
  if(act === 'freshx'){ S.fresh = null; return render(); }
  if(act === 'csvopen'){
    api('GET', '/admin/courses/csv').then(function(r){ if(r.ok){ S.sheet = {kind:'csv', text:r.data.text}; render(); } else toast(r.data.error || '読めませんでした'); });
    return;
  }
  if(act === 'csvcopy'){
    var tx = ($('#csvText') || {}).value || '';
    (navigator.clipboard ? navigator.clipboard.writeText(tx) : Promise.reject()).then(function(){ toast('コピーしました。'); }, function(){ toast('コピーできませんでした。'); });
    return;
  }
  if(act === 'csvsave'){
    var text2 = ($('#csvText') || {}).value || '';
    /* 表計算から貼るとタブ区切りになる。カンマ区切りに直して送る。 */
    if(text2.indexOf('\t') >= 0 && text2.split('\n')[0].indexOf(',') < 0){
      text2 = text2.split('\n').map(function(line){ return line.split('\t').map(function(c){ return /[",\n]/.test(c) ? '"'+c.replace(/"/g, '""')+'"' : c; }).join(','); }).join('\n');
    }
    api('POST', '/admin/courses/csv', {text:text2}).then(function(r){
      if(r.ok){ S.st = r.data.state; S.sheet = null; toast('入れました：新しく '+r.data.made+'・直した '+r.data.changed+'・変わらない '+r.data.same); }
      else{ S.sheet.text = ($('#csvText') || {}).value || ''; S.sheet.err = r.data.error || '入りませんでした'; }
      render();
    });
    return;
  }
  if(act === 'repf'){ S.repAll = v === '1'; return render(); }
  if(act === 'repdone'){
    api('PUT', '/admin/reports/'+encodeURIComponent(id), {state:v}).then(function(r){
      if(r.ok){ S.reports = S.reports.map(function(x){ return x.id === id ? r.data.item : x; }); reload(true); } else toast(r.data.error || 'できませんでした');
    });
    return;
  }
});
document.addEventListener('change', function(e){
  var t = e.target;
  if(t.id === 'nick'){ setName(t.getAttribute('data-id'), t.value); toast('呼び名を、この端末に残しました。'); return; }
  if(t.tagName === 'SELECT' && t.getAttribute('data-act') === 'assign' && t.value){ assign(t.getAttribute('data-key'), t.value, true); }
  if(t.tagName === 'SELECT' && t.getAttribute('data-act') === 'movepick' && S.sheet && S.sheet.kind === 'move'){
    var id = t.getAttribute('data-id');
    if(t.value === t.getAttribute('data-from')) delete S.sheet.pick[id]; else S.sheet.pick[id] = t.value;
    render();
  }
});
document.addEventListener('keydown', function(e){
  if(e.key === 'Escape' && S.sheet && !S.fresh){ S.sheet = null; S.open = null; render(); }
});
/* 合言葉を出したまま、この頁を離れようとしたら止める。 */
window.addEventListener('beforeunload', function(e){ if(S.fresh){ e.preventDefault(); e.returnValue = ''; } });
document.addEventListener('visibilitychange', function(){ if(!document.hidden && S.tok && S.st && !S.busy && !S.fresh) reload(); });
/* 開いたままでも、30秒ごとに今の状態に合わせる（生徒が入って「使っている」が増える）。
   **この取り直しは、さわったことにしない**（この1分に押す・打つが無ければ）。数えると、開いたままの
   画面は いつまでも切れない。手元だけの作業（表を打つ・カードを切る）は、押す・打つで さわったことになる。 */
var lastAct = Date.now();
['click', 'keydown', 'input'].forEach(function(ev){ document.addEventListener(ev, function(){ lastAct = Date.now(); }, true); });
setInterval(function(){ if(!document.hidden && S.tok && S.st && !S.busy && !S.fresh) reload(false, Date.now() - lastAct > 60000); }, 30000);
/* 刷り終えたら（印刷の窓が閉じたら）、そのまま残っていることを知らせる。 */
window.addEventListener('afterprint', function(){ if(S.printJoin){ S.printJoin = false; render(); return; } if(S.cards && S.cards.length) toast('刷り終えたら「消す」を押してください（合言葉を画面に残さないため）。'); });

/* http で開かれたら https へ（手元の 127.0.0.1 などは除く） */
(function(){
  var h = location.hostname;
  if(location.protocol === 'http:' && !/^(localhost|127\.|\[::1\]|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(h) && !/\.(localhost|test)$/.test(h)){
    location.replace('https://' + location.host + location.pathname);
  }
})();

S.tok = ssGet();
if(S.tok) reload(true).then(function(){ if(!S.st) render(); }); else render();
window.TubeAdmin = {state:function(){ return S; }, parseCards:parseCards};
})();
