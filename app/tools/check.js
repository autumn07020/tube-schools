/* ============================================================
   検査スクリプト
   ------------------------------------------------------------
   目視で済ませないための道具。CLAUDE.md「検証のしかた」を機械化した。

   使い方（アプリを開いた状態で、ブラウザのコンソールに貼る）:

     var s=document.createElement('script');
     s.src='tools/check.js'; document.head.appendChild(s);
     // 読み込み後
     await TubeCheck.all()

   サーバ運用中（ID/パスワードで入る形）のときは、検査用の資格を渡す:

     await TubeCheck.all({id:'j2a01', password:'…',
                          teacherId:'sensei', teacherPassword:'…'})

   落ちたら直す。通ってから配る。
   ============================================================ */
(function(global){
"use strict";

var errors = [];
window.addEventListener('error', function(e){ errors.push(String(e.message)); });
window.addEventListener('unhandledrejection', function(e){ errors.push('promise: '+e.reason); });

function fail(list, msg){ list.push(msg); }

var CRED = {};   // サーバ運用のときの検査用アカウント

function waitMs(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }

/* 画面の更新はクリックハンドラの中で同期的に終わる。だから出題を送る
   ループでは setTimeout を待つ必要がない ―― むしろ待ってはいけない。
   ブラウザは裏に回ったタブのタイマーを1秒に1回まで間引くので、
   1手ごとに setTimeout を挟むと1日分の走行に何十分もかかる。 */
function tick(){ return Promise.resolve(); }

/* 「何回まわったか」ではなく「いつまで待つか」で区切る。
   タイマーが間引かれても、待ち時間は実時間のまま変わらない。 */
async function until(test, ms){
  var deadline = Date.now() + (ms || 12000);
  while(Date.now() < deadline){
    if(test()) return true;
    await waitMs(80);
  }
  return test();
}

/* 学習セッションを必ず閉じる。
   セッション中は render() が画面遷移を握りつぶすので、開いたまま次の
   検査に進むと、以降の go() がすべて無視されて検査が止まる。 */
async function closeSession(){
  for(var i=0; i<3 && TubeUI.state().session; i++){
    var end = document.querySelector('#dEnd') || document.querySelector('#sQuit');
    if(end) end.click();
    await waitMs(150);
  }
  return !TubeUI.state().session;
}

/* 生徒として入る。サーバがいれば ID/パスワード、いなければクラスコード。 */
async function enterStudent(){
  await closeSession();
  var srv = TubeUI.state().server;
  TubeUI.go(srv ? 'login' : 'gate');
  await waitMs(60);
  if(srv){
    if(!CRED.id) throw new Error('サーバ運用中です。TubeCheck.all({id, password, …}) で資格を渡してください');
    if(!document.querySelector('#lId')) return false;
    document.querySelector('#lId').value = CRED.id;
    document.querySelector('#lPw').value = CRED.password;
    document.querySelector('#lGo').click();
  }else{
    if(!document.querySelector('#gCode')) return false;
    document.querySelector('#gCode').value = TubeConfig.classes()[0].code;
    document.querySelector('#gGo').click();
    await waitMs(60);
    var pick = document.querySelector('[data-sid]');
    if(pick){ pick.click(); }
    else{
      document.querySelector('#gSeat').value = '99';
      document.querySelector('#gAdd').click();
    }
  }
  await until(function(){ return TubeUI.state().view === 'today'; }, 15000);
  await waitMs(200);
  return TubeUI.state().view === 'today';
}

/* 講師として入る。 */
async function enterTeacher(){
  await closeSession();
  var srv = TubeUI.state().server;
  if(srv){
    var me = TubeUI.state();
    if(me.me || me.teacher){
      TubeUI.go(me.teacher ? 'admin' : 'settings'); await waitMs(120);
      var out = document.querySelector('#mOut') || document.querySelector('#aOut');
      if(out){ out.click(); await until(function(){ return !!document.querySelector('#lId'); }, 8000); }
    }
    TubeUI.go('login'); await waitMs(60);
    if(!document.querySelector('#lId')) return false;
    document.querySelector('#lId').value = CRED.teacherId;
    document.querySelector('#lPw').value = CRED.teacherPassword;
    document.querySelector('#lGo').click();
  }else{
    /* 講師の入口はサーバ経由だけになった。サーバがいなければ講師画面は無い。 */
    return false;
  }
  await until(function(){ return TubeUI.state().view === 'roster'; }, 15000);
  await until(function(){ return !!document.querySelector('table.roster, .empty'); }, 8000);
  await waitMs(300);
  return TubeUI.state().view === 'roster';
}

/* ------------------------------------------------------------
   1. 死んだボタン
   枠・影・角丸を持つ要素はすべて「押せる」の合図に見える。
   押せそうで押せないものを1つも残さない（HANDOVER 5.4）。
   ------------------------------------------------------------ */
function buttons(label){
  var bad = [], small = [];
  document.querySelectorAll('button').forEach(function(b){
    var live = !!b.onclick || b.disabled ||
               b.closest('[data-say]') === b || b.type === 'submit';
    if(!live) fail(bad, label + ' : ' + (b.id||b.className||b.textContent||'?').trim().slice(0,40));
    var r = b.getBoundingClientRect();
    /* ::after で当たり判定だけ広げている要素は .hit を付けてある。
       44 ちょうどを狙った要素がサブピクセルで 43.98 になることがあるので
       0.5px だけ許容する（丸めの差で毎回赤くなると検査を見なくなる）。 */
    if(r.width && (r.width < 43.5 || r.height < 43.5) && !b.classList.contains('hit')){
      small.push(label+' : '+(b.id||b.className).trim().slice(0,30)+
                 ' '+Math.round(r.width)+'x'+Math.round(r.height));
    }
  });
  /* select も操作要素。選んだ瞬間に動くものは onchange を持つ。
     送信時に読むだけの入力欄は data-input を付けて意図を明示する。 */
  document.querySelectorAll('select').forEach(function(s){
    if(!s.onchange && !s.hasAttribute('data-input')){
      fail(bad, label + ' : select#' + (s.id||'?'));
    }
  });
  return {dead:bad, small:small};
}

/* ------------------------------------------------------------
   2. 全画面を巡回して走査
   ------------------------------------------------------------ */
var hwSeen = false;
var hwCount = 0;
var subjCount = 0;

async function screens(){
  var dead = [], small = [];
  var take = function(name){
    var r = buttons(name);
    dead = dead.concat(r.dead); small = small.concat(r.small);
  };
  var wait = waitMs;

  /* 入口 */
  var srv = TubeUI.state().server;
  TubeUI.go(srv ? 'login' : 'gate'); await wait(60);
  take(srv ? 'login' : 'gate/code');
  if(!srv){
    document.querySelector('#gCode').value = TubeConfig.classes()[0].code;
    document.querySelector('#gGo').click(); await wait(60); take('gate/who');
  }

  /* 生徒画面 */
  await enterStudent();
  ['today','record','settings'].forEach(function(v){ TubeUI.go(v); take('student/'+v); });
  /* 宿題カードのボタンは today に出る。出ていることも確かめる */
  TubeUI.go('today');
  /* 出ていないこと自体は不具合ではない ―― その生徒に宿題が出ていない
     だけかもしれない。判定に使わず、事実として報告する。 */
  hwSeen = !!document.querySelector('[data-hw]');
  hwCount = (window.TubeHomework ? TubeHomework.all().length : 0);
  subjCount = (TubeUI.state().me ? TubeUI.state().me.subjects.length : 0);

  /* 講師画面 */
  await enterTeacher();
  take('teacher/roster');
  var row = document.querySelector('[data-row]');
  if(row){ row.click(); await wait(60); take('teacher/student'); }
  TubeUI.go('hw');
  await until(function(){ return !!document.querySelector('#hAdd, .empty'); }, 10000);
  take('teacher/hw');
  /* 宿題の明細（期限をのばす／取り消す）も開いて走査する */
  var row = document.querySelector('[data-open]');
  if(row){ row.click(); await waitMs(150); take('teacher/hw-detail'); }

  TubeUI.go('progress');
  await until(function(){ return !!document.querySelector('#pSave, .empty'); }, 10000);
  take('teacher/progress');
  TubeUI.go('admin'); await wait(200); take('teacher/admin');

  return {dead:dead, small:small, hwSeen:hwSeen, hwCount:hwCount, subjCount:subjCount};
}

/* ------------------------------------------------------------
   3. セッション通し ―― 1日分を無人で走らせる
   ------------------------------------------------------------ */
async function session(maxSteps){
  maxSteps = maxSteps || 1200;
  var wait = waitMs;
  var before = errors.length;

  if(!(await enterStudent())){
    return {steps:0, reachedDone:false, errors:['生徒として入れなかった']};
  }

  /* 今日のぶんが済んでいたら、追加学習の導線から走らせる。
     「終わっていたので検査しませんでした」で通してはいけない。 */
  /* 教科ごとにボタンが並ぶので、最初の1つで走らせる */
  var start = document.querySelector('[data-start]') || document.querySelector('[data-extra]');
  if(!start) return {steps:0, reachedDone:false,
                     errors:['今日の画面に開始ボタンが無い']};
  start.click();
  await wait(60);
  if(!document.querySelector('#sBody')){
    return {steps:0, reachedDone:false, errors:['セッションが始まらなかった']};
  }

  var steps = 0, seen = {vocab:0, prep:0, gram:0, done:0};
  while(steps++ < maxSteps){
    await tick();
    var body = document.querySelector('#sBody');
    if(!body) break;
    if(body.textContent.indexOf('おつかれさま') >= 0){ seen.done++; break; }

    /* 選択肢があれば選ぶ。なければ「答えを見る」→採点 */
    var opt = document.querySelector('#opts .opt:not([disabled])');
    var show = document.querySelector('#show') || document.querySelector('#gStart');
    var grade = document.querySelector('#sFoot [data-g]');
    var next = document.querySelector('#sFoot #nx');

    if(opt){ opt.click(); seen.prep++; continue; }
    if(show){ show.click(); seen.vocab++; continue; }
    if(grade){
      /* Again ばかり押すと終わらないので、たまにしか押さない */
      var all = document.querySelectorAll('#sFoot [data-g]');
      var pickG = all[Math.random() < 0.08 ? 0 : all.length-1];
      pickG.click(); continue;
    }
    if(next){ next.click(); seen.gram++; continue; }
    break;
  }

  var hitCap = steps >= maxSteps;
  await closeSession();
  await wait(150);
  return {steps:steps, reachedDone:!!seen.done, hitCap:hitCap,
          errors:errors.slice(before).concat(
            hitCap ? [''+maxSteps+'手で打ち切った（完走していない）'] : [])};
}

/* ------------------------------------------------------------
   4. 保存 ―― 6シナリオ
   HANDOVER 5.1。ここが通らないアプリは配ってはいけない。
   ------------------------------------------------------------ */
async function storage(){
  var out = [];
  var sid = TubeStore.activeSid() || (TubeStore.students()[0]||{}).sid;
  if(!sid) return [{name:'前提', ok:false, note:'生徒がいません。先に session() を回してください'}];
  var K = 'tube.school.v1.p.' + sid;

  var snapshot = localStorage.getItem(K);
  if(!snapshot) return [{name:'前提', ok:false, note:'進捗がまだ保存されていません'}];
  var cardCount = function(s){ var d = JSON.parse(s); return Object.keys(d.cards||{}).length; };
  var n0 = cardCount(snapshot);

  var reload = async function(){
    await TubeStore.boot({sync:null});
    return await TubeStore.loadStudent(sid);
  };

  /* (1) 通常の読み直し */
  var p = await reload();
  out.push({name:'通常リロード', ok:Object.keys(p.cards).length === n0,
            note:Object.keys(p.cards).length + ' / ' + n0});

  /* (2) localStorage だけ失効 ―― session/idb から戻り、volatile と報告する */
  localStorage.removeItem(K);
  p = await reload();
  out.push({name:'localStorageだけ失効',
            ok:Object.keys(p.cards).length === n0 && !TubeStore.report().durable,
            note:'kind=' + TubeStore.report().kind});

  /* (3) IndexedDB だけ生存 */
  localStorage.setItem(K, snapshot);
  await new Promise(function(r){ setTimeout(r, 900); });   // idb への遅延書き込みを待つ
  localStorage.removeItem(K); sessionStorage.removeItem(K);
  p = await reload();
  out.push({name:'IndexedDBだけ生存', ok:Object.keys(p.cards).length === n0,
            note:'復元元=' + TubeStore.state.restoredFrom});

  /* (4) IndexedDB 不通 */
  localStorage.setItem(K, snapshot); sessionStorage.setItem(K, snapshot);
  var realOpen = indexedDB.open;
  indexedDB.open = function(){ throw new Error('blocked'); };
  p = await reload();
  indexedDB.open = realOpen;
  out.push({name:'IndexedDB不通', ok:Object.keys(p.cards).length === n0,
            note:'idb=' + TubeStore.state.idbOpened});

  /* (5) 読み取りの一時失敗
     携帯の IndexedDB は初回オープンが単に遅いことがある。それを「空」と
     断じると、直後の日付処理が空を本物の上に書いて全滅する。
     3系統すべてを最初の1回だけ空振りさせ、再試行で戻ることを確かめる。 */
  localStorage.removeItem(K); sessionStorage.removeItem(K);   // idb だけに残す
  var realIdbGet = IDBObjectStore.prototype.get;
  var idbMisses = 0;
  IDBObjectStore.prototype.get = function(key){
    var rq = realIdbGet.call(this, key);
    if(key === K && idbMisses < 1){
      idbMisses++;
      /* 本物のリクエストの成功を待って、結果だけ空に見せる */
      Object.defineProperty(rq, 'result', {get:function(){ return undefined; }});
    }
    return rq;
  };
  p = await reload();
  IDBObjectStore.prototype.get = realIdbGet;
  out.push({name:'読み取りの一時失敗',
            ok:Object.keys(p.cards).length === n0 &&
               TubeStore.report().kind !== 'wiped' &&
               TubeStore.state.recoveredOnRetry === true,
            note:'kind=' + TubeStore.report().kind +
                 ' 再試行=' + TubeStore.state.recoveredOnRetry +
                 ' 件数=' + Object.keys(p.cards).length});

  /* (6) 空を本物の上に書かない */
  var blank = TubeStore.emptyProgress(sid, 'j2', 'j2a');
  var r = TubeStore.save(blank);
  var still = cardCount(localStorage.getItem(K) || '{}');
  out.push({name:'空の書き戻しを拒む',
            ok:(r.ok === false && r.reason === 'refused-empty' && still === n0),
            note:'reason=' + r.reason + ' 残=' + still});

  /* 後始末 */
  localStorage.setItem(K, snapshot); sessionStorage.setItem(K, snapshot);
  await reload();
  return out;
}

/* ------------------------------------------------------------
   5. まとめて
   ------------------------------------------------------------ */
async function all(cred){
  CRED = cred || {};
  errors.length = 0;
  var sess = await session();
  var scr  = await screens();
  var sto  = await storage();

  var lines = [];
  lines.push('― セッション通し ―');
  lines.push('  手数 ' + sess.steps + ' / 完走 ' + (sess.reachedDone ? 'した' : 'していない'));
  lines.push('― 教科 ―');
  lines.push('  この生徒に ' + scr.subjCount + ' 教科');
  lines.push('― 宿題カード ―');
  lines.push(scr.hwCount
    ? '  この生徒に' + scr.hwCount + '件出ている → 今日の画面に' +
      (scr.hwSeen ? '出ている' : '出ていない（不具合）')
    : '  この生徒には宿題が出ていない（カードが無いのは正しい）');
  lines.push('― 死んだボタン ―');
  lines.push(scr.dead.length ? '  ' + scr.dead.join('\n  ') : '  なし');
  lines.push('― タップ領域が44px未満 ―');
  lines.push(scr.small.length ? '  ' + scr.small.join('\n  ') : '  なし');
  lines.push('― 保存 ―');
  sto.forEach(function(s){ lines.push('  ' + (s.ok ? 'OK  ' : 'NG  ') + s.name + '　' + s.note); });
  lines.push('― JSエラー ―');
  lines.push(errors.length ? '  ' + errors.join('\n  ') : '  なし');

  var pass = !scr.dead.length && !scr.small.length && !errors.length &&
             sto.every(function(s){ return s.ok; }) && sess.reachedDone;
  console.log(lines.join('\n'));
  return {pass:pass, text:lines.join('\n'), dead:scr.dead, small:scr.small,
          storage:sto, errors:errors.slice(), session:sess};
}

global.TubeCheck = {buttons:buttons, screens:screens, session:session,
                    storage:storage, all:all, errors:errors,
                    creds:function(c){ CRED = c || {}; }};
console.log('TubeCheck 読み込み完了。 await TubeCheck.all()');

})(window);
