/* ============================================================
   STORE ―― 生徒ごとに分割して保存する層
   ------------------------------------------------------------
   考え方はひとつだけ:

     「全員に共通するもの（教材）」と
     「その子だけのもの（進捗）」を、絶対に混ぜない。

   教材は content/ にあり、誰の端末でも同一で、書き換えない。
   保存するのは進捗だけで、これは1人あたり数十KBしかない。
   だから生徒ごとに独立した鍵に分けて置ける。

     tube.school.v1.roster        この端末にいる生徒の一覧（呼び名と学年）
     tube.school.v1.p.<sid>       生徒1人分の進捗。他の生徒とは別の鍵
     tube.school.v1.device        端末そのもののID

   鍵を分けてあるので:
     - 教室の共用iPadに複数人が同居できる
     - 1人分だけ書き出す／消す／サーバへ送る、が自然にできる
     - ある生徒のデータが壊れても他の生徒に波及しない

   保存の失敗については HANDOVER.md 5.1 を厳守している:
     - 書けるかどうかは try/catch ではなく実測（書いて読み返す）
     - 読み取りが空のときは書き込まない
     - 「遅い」を「空」と誤判定しない（再試行してから結論を出す）
     - 診断の所有者は restore() ひとつだけ。save() は結論を上書きしない
   ============================================================ */
(function(global){
"use strict";

var NS   = 'tube.school.v1';
var K_ROSTER = NS + '.roster';
var K_DEVICE = NS + '.device';
var K_MARK   = NS + '.seen';
var pkey = function(sid){ return NS + '.p.' + sid; };

/* restore() だけが書き換える診断結果。save() からは触らない。 */
var STATE = {
  durable: true,          // 記録が残ると信じてよいか
  kind: 'local',          // local | blocked | wiped | volatile | memory
  can: {},                // 各バックエンドの実測結果
  found: {},              // 起動時にどこにデータがあったか
  restoredFrom: null,
  idbOpened: false,
  recoveredOnRetry: false
};

var ready   = false;      // restore() 完了まで save() は何もしない
var hadData = false;      // 起動時に中身のある進捗を読めたか
var sync    = null;       // 同期トランスポート（null なら端末内だけ）
var idbTimer = {};        // 鍵ごとの遅延書き込みタイマー

/* 前回サーバへ送った時点の「項目ID -> 答えた回数」。
   これと今を比べて、変わった項目だけを送る。
   1問ごとに95KBの全文を送ると、外の回線ではセッション終盤が
   いちばん落ちやすくなる（送信の途中でタブが閉じられるため）。 */
var pushedSig = {};
var pushedHw  = {};

/* ------------------------------------------------------------
   バックエンド 3種。どれか1つ生き残ればデータは戻る。
   ------------------------------------------------------------ */
function lsGet(k){ try{ return localStorage.getItem(k); }catch(e){ return null; } }
function lsSet(k,v){ try{ localStorage.setItem(k,v); return true; }catch(e){ return false; } }
function lsDel(k){ try{ localStorage.removeItem(k); }catch(e){} }
function ssGet(k){ try{ return sessionStorage.getItem(k); }catch(e){ return null; } }
function ssSet(k,v){ try{ sessionStorage.setItem(k,v); return true; }catch(e){ return false; } }
function ssDel(k){ try{ sessionStorage.removeItem(k); }catch(e){} }

/* 「今この瞬間、実際に書けて読み返せるか」。
   try/catch で握りつぶすと、遮断されている状態と、まだ空の状態が
   区別できない。区別できないと警告が一度も出ないまま記録が消え続ける。 */
function probe(get){
  var api;
  try{ api = get(); if(!api) return 'missing'; }catch(e){ return 'blocked'; }
  try{
    var k = NS + '.__probe';
    api.setItem(k, '1');
    var ok = api.getItem(k) === '1';
    api.removeItem(k);
    return ok ? 'ok' : 'broken';
  }catch(e){ return 'blocked'; }
}

var IDB = null;
function idbOpen(){
  return new Promise(function(res){
    var done = false;
    var finish = function(v){ if(!done){ done = true; res(v); } };
    setTimeout(function(){ finish(null); }, 5000);
    try{
      var r = indexedDB.open('tube-school', 1);
      r.onupgradeneeded = function(){ try{ r.result.createObjectStore('kv'); }catch(e){} };
      r.onsuccess = function(){ finish(r.result); };
      r.onerror   = function(){ finish(null); };
      r.onblocked = function(){ finish(null); };
    }catch(e){ finish(null); }
  });
}
function idbGet(k){
  return new Promise(function(res){
    if(!IDB) return res(null);
    try{
      var rq = IDB.transaction('kv','readonly').objectStore('kv').get(k);
      rq.onsuccess = function(){ res(rq.result || null); };
      rq.onerror   = function(){ res(null); };
    }catch(e){ res(null); }
  });
}
function idbSet(k,v){
  try{ if(IDB) IDB.transaction('kv','readwrite').objectStore('kv').put(v,k); }catch(e){}
}
function idbDel(k){
  try{ if(IDB) IDB.transaction('kv','readwrite').objectStore('kv').delete(k); }catch(e){}
}

function parse(s){ try{ return s ? JSON.parse(s) : null; }catch(e){ return null; } }

/* 3箇所に書き、いちばん新しいものから復元する。
   同じタブのリロードなら localStorage が消えても sessionStorage が拾う。 */
/* localStorage と sessionStorage は同期で書く（落ちたときの保険はここ）。
   IndexedDB は1秒弱まとめる ―― 1問ごとに数十KBのトランザクションを
   張ると、古い端末で目に見えて遅くなる。

   遅延タイマーは必ず鍵ごとに持つ。ひとつを使い回すと、名簿を保存した
   瞬間に進捗の書き込みが取り消され、IndexedDB だけが古いまま残る。 */
function writeAll(k, s){
  var okLs = lsSet(k, s);
  var okSs = ssSet(k, s);
  clearTimeout(idbTimer[k]);
  idbTimer[k] = setTimeout(function(){ idbSet(k, s); }, 800);
  return {local:okLs, session:okSs};
}
async function readNewest(k){
  var found = {
    local:   parse(lsGet(k)),
    session: parse(ssGet(k)),
    idb:     parse(await idbGet(k))
  };
  var cands = Object.keys(found)
    .filter(function(x){ return found[x]; })
    .map(function(x){ return [x, found[x]]; });
  cands.sort(function(a,b){ return (b[1].savedAt||0) - (a[1].savedAt||0); });
  return {found:found, winner:cands[0] || null};
}

/* ------------------------------------------------------------
   進捗ブロブの形

   cards は [iv, ef, due, reps, lapse, seen] の配列に詰める。
   オブジェクトのままだと鍵名が1,400回繰り返されて倍近くになる。
   この形はそのまま同期の通信形式でもある（DESIGN.md 3章）。
   ------------------------------------------------------------ */
var CARD_FIELDS = ['iv','ef','due','reps','lapse','seen'];

function packCards(cards){
  var o = {};
  Object.keys(cards).forEach(function(id){
    var c = cards[id];
    o[id] = [c.iv, c.ef, c.due, c.reps, c.lapse, c.seen, c.known?1:0];
  });
  return o;
}
function unpackCards(raw){
  var o = {};
  if(!raw) return o;
  Object.keys(raw).forEach(function(id){
    var a = raw[id];
    if(Array.isArray(a)){
      o[id] = {iv:a[0], ef:a[1], due:a[2], reps:a[3], lapse:a[4], seen:a[5]};
      if(a[6]) o[id].known = 1;
    }else if(a && typeof a === 'object'){
      o[id] = a;                                  // 旧形式もそのまま読める
    }
  });
  return o;
}

function emptyProgress(sid, grade, classId){
  return {
    v:1, sid:sid, grade:grade, classId:classId,
    cards:{},
    hw:{},                                        // 宿題ID -> 達成状況
    streak:0, best:0, xp:0, lastDay:null,
    dayKey:null, newToday:0, sessDone:{},   // 種別 -> その日の新出数
    hist:{},                                      // 'YYYY-MM-DD' -> {n, ok}
    started:Date.now(), savedAt:0, rev:0
  };
}

function serialize(p){
  var out = {};
  Object.keys(p).forEach(function(k){ if(k!=='cards') out[k] = p[k]; });
  out.cards = packCards(p.cards||{});
  return out;
}
function deserialize(raw, sid, grade, classId){
  var p = emptyProgress(sid, grade, classId);
  if(!raw) return p;
  Object.keys(raw).forEach(function(k){ if(k!=='cards') p[k] = raw[k]; });
  p.cards = unpackCards(raw.cards);
  /* 科目コードを付ける前の記録（'v:reluctant:adj'）も読めるようにする。
     ここで読み替えないと、教材の作り替えで全員の進捗が消えたように見える。 */
  if(global.TubeContent && TubeContent.migrateId){
    var moved = {};
    Object.keys(p.cards).forEach(function(id){
      var nid = TubeContent.migrateId(id);
      moved[nid] = p.cards[id];
    });
    p.cards = moved;
  }
  /* 前の上限（400日）で「5ヶ月後」に飛ばされた札を、
     単元確認テストの周期（5週）の中に連れ戻す。理由は srs.js に書いた。 */
  if(global.TubeSRS && TubeSRS.fitToCycle) TubeSRS.fitToCycle(p.cards);
  p.sid = sid;                                    // 鍵が正。中身は信用しない
  return p;
}

/* ------------------------------------------------------------
   名簿（この端末にいる生徒）
   ------------------------------------------------------------ */
var roster = {students:[], active:null};

function loadRosterSync(){
  var r = parse(lsGet(K_ROSTER)) || parse(ssGet(K_ROSTER));
  if(r && Array.isArray(r.students)) roster = r;
  return roster;
}
/* 名簿が変わるたびに増える番号。講師画面はこれを見て手元の集計を
   捨てる ―― 生徒が自分の端末で参加したのに名簿に出てこない、という
   古い一覧を掴んだままの状態を防ぐ。 */
var rosterRev = 0;

function saveRoster(){
  if(!ready) return;
  rosterRev++;
  var s = JSON.stringify(roster);
  lsSet(K_ROSTER, s); ssSet(K_ROSTER, s); idbSet(K_ROSTER, s);
}

function newSid(){
  /* 端末内で一意ならよい。個人が特定できる情報は入れない。
     氏名は端末の名簿にしか置かず、同期するのは sid と進捗だけ。 */
  var s = '';
  var abc = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ';
  for(var i=0;i<8;i++) s += abc[(Math.random()*abc.length)|0];
  return s;
}

/* ------------------------------------------------------------
   起動
   ------------------------------------------------------------ */
async function boot(opts){
  opts = opts || {};
  sync = opts.sync || null;

  STATE.durable = true; STATE.kind = 'local';
  STATE.restoredFrom = null; STATE.recoveredOnRetry = false;
  STATE.can = {local:probe(function(){ return localStorage; }),
               session:probe(function(){ return sessionStorage; })};

  IDB = await idbOpen();
  STATE.idbOpened = !!IDB;

  if(STATE.can.local !== 'ok' && STATE.can.session !== 'ok'){
    STATE.durable = false;
    STATE.kind = STATE.idbOpened ? 'volatile' : 'blocked';
  }

  var r = await readNewest(K_ROSTER);
  if(r.winner && Array.isArray(r.winner[1].students)) roster = r.winner[1];

  var dev = parse(lsGet(K_DEVICE));
  if(!dev){
    dev = {id:newSid(), createdAt:Date.now()};
    lsSet(K_DEVICE, JSON.stringify(dev));
  }
  STATE.deviceId = dev.id;

  ready = true;
  lsSet(K_MARK,'1'); ssSet(K_MARK,'1'); idbSet(K_MARK,'1');
  saveRoster();
  return STATE;
}

/* ------------------------------------------------------------
   1人分の読み書き
   ------------------------------------------------------------ */
async function loadStudent(sid){
  var stu = roster.students.filter(function(s){ return s.sid===sid; })[0];
  if(!stu) return null;

  var k = pkey(sid);
  var r = await readNewest(k);
  STATE.found = {local:!!r.found.local, session:!!r.found.session, idb:!!r.found.idb};

  if(!r.winner){
    /* 空で返ってきた。ここで「新規」と決めつけない ―― 携帯の
       IndexedDB は初回オープンが単に遅いことがあり、それを「空」と
       扱うと、直後の日付処理が空の状態を本物の進捗に上書きする。 */
    var seen = !!(lsGet(K_MARK) || ssGet(K_MARK) || await idbGet(K_MARK));
    if(seen && stu.everSaved){
      for(var i=0; i<3 && !r.winner; i++){
        await new Promise(function(res){ setTimeout(res, 400*(i+1)); });
        if(!IDB) IDB = await idbOpen();
        r = await readNewest(k);
      }
      if(r.winner){ STATE.recoveredOnRetry = true; }
      else { STATE.durable = false; STATE.kind = 'wiped'; }
    }
  }

  var raw = r.winner ? r.winner[1] : null;
  if(r.winner) STATE.restoredFrom = r.winner[0];

  hadData = !!(raw && raw.cards && Object.keys(raw.cards).length);

  /* localStorage が空なのに他が生きていた＝この環境は localStorage を
     読み込みのたびに捨てている。動くが、いつ消えてもおかしくない。 */
  if(r.winner && STATE.can.local === 'ok' &&
     (!r.found.local || (r.found.local.savedAt||0) < (raw.savedAt||0))){
    STATE.durable = false; STATE.kind = 'volatile';
  }

  var p = deserialize(raw, sid, stu.grade, stu.classId);
  markPushed(p);             // ここまではサーバと同じ、とみなす
  if(raw) save(p);           // 生き残った1つを全バックエンドへ書き戻す
  return p;
}

/* いま送るべき差分を作る。送ったあとに sig を更新するのではなく、
   作った時点で更新する ―― 送信が失敗しても行列に残っており、
   二重に数えないため。 */
function buildDelta(p){
  var cards = {}, n = 0;
  var packed = packCards(p.cards || {});
  Object.keys(packed).forEach(function(id){
    var reps = packed[id][3];
    if(pushedSig[id] !== reps){
      cards[id] = packed[id];
      pushedSig[id] = reps;
      n++;
    }
  });
  var hw = {};
  Object.keys(p.hw || {}).forEach(function(aid){
    var rec = p.hw[aid];
    var sig = Object.keys(rec.done || {}).length + ':' + (rec.completedAt || 0);
    if(pushedHw[aid] !== sig){
      hw[aid] = rec;
      pushedHw[aid] = sig;
      n++;
    }
  });
  /* 今日と昨日の記録だけ送る。過去はもう変わらない。 */
  var hist = {}, k = TubeSRS.dayKey();
  var y = TubeSRS.dayKey(Date.now() - 864e5);
  [k, y].forEach(function(d){ if(p.hist && p.hist[d]) hist[d] = p.hist[d]; });

  return {mode:'delta', cards:cards, hw:hw, hist:hist, changed:n,
          meta:{streak:p.streak, best:p.best, xp:p.xp,
                grade:p.grade, classId:p.classId, sid:p.sid, v:p.v,
                /* 今週の目標（生徒が決める）。無ければ送らない（サーバは持っている値を保つ） */
                goal:p.goal || undefined}};
}

/* 読み込んだ直後の状態を「送信済み」として記憶する。
   これをしないと、起動のたびに全項目を送り直すことになる。 */
function markPushed(p){
  pushedSig = {}; pushedHw = {};
  var packed = packCards(p.cards || {});
  Object.keys(packed).forEach(function(id){ pushedSig[id] = packed[id][3]; });
  Object.keys(p.hw || {}).forEach(function(aid){
    var rec = p.hw[aid];
    pushedHw[aid] = Object.keys(rec.done || {}).length + ':' + (rec.completedAt || 0);
  });
}

/* 進捗を保存する。戻り値は必ず見ること ―― 黙って失敗しない。 */
function save(p){
  if(!ready)  return {ok:false, reason:'not-ready'};
  if(!p || !p.sid) return {ok:false, reason:'no-student'};

  /* 空を本物の上に書かない。restore() が踏みとどまっても、その直後の
     日付処理が空を保存して全滅させた実例がある（HANDOVER 5.1）。 */
  if(hadData && Object.keys(p.cards||{}).length === 0){
    return {ok:false, reason:'refused-empty'};
  }

  p.savedAt = Date.now();
  p.rev     = (p.rev||0) + 1;
  var wrote = writeAll(pkey(p.sid), JSON.stringify(serialize(p)));

  var stu = roster.students.filter(function(s){ return s.sid===p.sid; })[0];
  if(stu && !stu.everSaved){ stu.everSaved = true; saveRoster(); }

  if(Object.keys(p.cards||{}).length) hadData = true;

  /* save() は起動時の診断を上書きしない。'blocked' という精度の高い
     結論が、次の書き込みで曖昧な値に潰されるのを防ぐ。 */
  if(!wrote.local && !wrote.session && STATE.durable){
    STATE.durable = false; STATE.kind = 'memory';
  }
  if(sync && sync.push){
    var d = buildDelta(p);
    if(d.changed) sync.push(p.sid, d);
  }
  return {ok:(wrote.local || wrote.session), wrote:wrote};
}

/* ------------------------------------------------------------
   名簿の操作
   ------------------------------------------------------------ */
/* サーバから渡された素性で名簿に載せる。sid はサーバが決めたものを使う
   ―― 端末側で振り直すと、同じ生徒が端末ごとに別人になる。 */
function adoptStudent(profile){
  var cur = student(profile.sid);
  if(cur){
    cur.label = profile.label;
    cur.seat = profile.seat;
    cur.grade = profile.grade || profile.level;
    cur.classId = profile.classId;
    cur.role = profile.role || 'student';
    cur.subjects = profile.subjects || [];
    cur.appSubjects = profile.appSubjects;
    cur.paperSubjects = profile.paperSubjects || [];
    cur.useBySubject = profile.useBySubject;
  }else{
    cur = {sid:profile.sid, label:profile.label, seat:profile.seat,
           grade:profile.grade || profile.level,
           classId:profile.classId, role:profile.role || 'student',
           subjects:profile.subjects || [],
           appSubjects:profile.appSubjects, paperSubjects:profile.paperSubjects || [],
           useBySubject:profile.useBySubject,
           addedAt:Date.now(), everSaved:false, fromServer:true};
    roster.students.push(cur);
  }
  roster.active = cur.sid;
  saveRoster();
  return cur;
}

/* サーバ側の記録を取り込む。新しいほうを採る（HANDOVER 3.2）。
   loadStudent とは別にしてあるのは、端末内だけの経路を非同期の
   ネットワーク待ちで汚さないため ―― 圏外でも起動は速いままにする。 */
/* サーバの内容を取り込む。
   合流はサーバ側で済んでいるので、ここでは「サーバのほうが進んでいるか」
   だけを見ればよい。rev はサーバが増やす番号で、端末の時計に依存しない。 */
async function syncIn(p, force){
  if(!sync || !sync.pull) return {status:'off'};
  var remote = await sync.pull(p.sid);
  if(!remote || !remote.blob) return {status:'none'};
  if(!force && (remote.rev || 0) <= (p.serverRev || 0)) return {status:'local'};

  var fresh = deserialize(remote.blob, p.sid, p.grade, p.classId);
  Object.keys(p).forEach(function(k){ delete p[k]; });
  Object.keys(fresh).forEach(function(k){ p[k] = fresh[k]; });
  hadData = Object.keys(p.cards || {}).length > 0;
  markPushed(p);             // サーバから来たものは、送り返す必要がない
  writeAll(pkey(p.sid), JSON.stringify(serialize(p)));
  return {status:'pulled', cards:Object.keys(p.cards).length, rev:remote.rev};
}

/* サーバがいない端末内だけの運用で使う。ここで受け取る label は
   生徒が自分で入れた呼び名で、この端末から外へは出ない。 */
function addStudent(label, grade, classId){
  var stu = {sid:newSid(), label:label, grade:grade, classId:classId,
             addedAt:Date.now(), everSaved:false};
  roster.students.push(stu);
  roster.active = stu.sid;
  saveRoster();
  return stu;
}
function removeStudent(sid){
  roster.students = roster.students.filter(function(s){ return s.sid!==sid; });
  if(roster.active === sid) roster.active = null;
  var k = pkey(sid);
  lsDel(k); ssDel(k); idbDel(k);
  saveRoster();
}
function setActive(sid){ roster.active = sid; saveRoster(); }
function students(){ return roster.students.slice(); }
function student(sid){ return roster.students.filter(function(s){ return s.sid===sid; })[0] || null; }
function setGrade(sid, grade){
  var s = student(sid); if(!s) return;
  s.grade = grade; saveRoster();
}

/* すべての生徒の進捗をまとめて読む（講師画面用）。
   端末内にいる生徒しか見えない ―― これがサーバを立てる主な理由。 */
async function loadAll(){
  var out = [];
  for(var i=0;i<roster.students.length;i++){
    var s = roster.students[i];
    var r = await readNewest(pkey(s.sid));
    out.push({student:s, progress:deserialize(r.winner?r.winner[1]:null, s.sid, s.grade, s.classId)});
  }
  return out;
}

/* ------------------------------------------------------------
   持ち出し / 取り込み

   サーバがまだ無い段階で「端末を変えた」「先生に提出する」を成立させる
   ための経路。完全版はファイル、要約は手で入力できる短い文字列。
   ------------------------------------------------------------ */
function exportBundle(entries){
  return JSON.stringify({
    format:'tube-school-export', v:1,
    school:(global.TubeConfig ? TubeConfig.school() : {}),
    exportedAt:new Date().toISOString(),
    students:entries.map(function(e){
      return {profile:{sid:e.student.sid, label:e.student.label,
                       seat:e.student.seat,
                       grade:e.student.grade, classId:e.student.classId},
              progress:serialize(e.progress)};
    })
  }, null, 1);
}

function importBundle(text){
  var d = parse(text);
  if(!d || d.format !== 'tube-school-export') return {ok:false, reason:'format'};
  var added = 0, merged = 0;
  (d.students||[]).forEach(function(rec){
    var pr  = rec.profile || {};
    var cur = student(pr.sid);
    if(!cur){
      roster.students.push({sid:pr.sid, label:pr.label || pr.name, seat:pr.seat,
                            grade:pr.grade || pr.level,
                            classId:pr.classId, addedAt:Date.now(), everSaved:true});
      added++;
    }else{
      merged++;
    }
    /* 衝突は savedAt が新しい方を採用する。同じ生徒の複数端末しか
       想定していないので、これで足りる（HANDOVER 3.2）。 */
    var k = pkey(pr.sid);
    var here = parse(lsGet(k));
    var incoming = rec.progress || {};
    if(!here || (here.savedAt||0) < (incoming.savedAt||0)){
      writeAll(k, JSON.stringify(incoming));
    }
  });
  saveRoster();
  return {ok:true, added:added, merged:merged};
}

/* 提出用の短いコード。数値をbase36で連ね、末尾に検査文字を付ける。
   打ち間違いは弾けるが、改竄は防げない ―― 出欠の代わりであって
   成績ではない。厳密さが要るならサーバを立てる。 */
function summaryCode(stu, p, stats){
  var parts = [
    stu.sid,
    (stats.days14||0),
    (stats.answered||0),
    (stats.mature||0),
    (p.streak||0)
  ];
  var body = parts.map(function(x, i){
    return i===0 ? x : Number(x).toString(36).toUpperCase();
  }).join('-');
  var sum = 0;
  for(var i=0;i<body.length;i++) sum = (sum*31 + body.charCodeAt(i)) % 1296;
  return body + '-' + sum.toString(36).toUpperCase().padStart(2,'0');
}
function readSummaryCode(code){
  code = String(code||'').trim().toUpperCase();
  var i = code.lastIndexOf('-');
  if(i < 0) return null;
  var body = code.slice(0,i), chk = code.slice(i+1);
  var sum = 0;
  for(var j=0;j<body.length;j++) sum = (sum*31 + body.charCodeAt(j)) % 1296;
  if(sum.toString(36).toUpperCase().padStart(2,'0') !== chk) return null;
  var a = body.split('-');
  if(a.length < 5) return null;
  return {sid:a[0], days14:parseInt(a[1],36), answered:parseInt(a[2],36),
          mature:parseInt(a[3],36), streak:parseInt(a[4],36)};
}

/* ------------------------------------------------------------
   人間に読める保存状況。見えない失敗を報告可能にする唯一の手段。
   ------------------------------------------------------------ */
function report(){
  var f = STATE.found || {};
  var mark = function(k, label){ return label + (f[k] ? ' あり' : ' なし'); };
  var msg = {
    local:    '端末に保存されています。',
    volatile: 'この環境は保存を捨てることがあります。定期的に書き出してください。',
    blocked:  'この環境では保存が遮断されています。記録は残りません。',
    wiped:    '保存されていた記録が消去されていました。',
    memory:   '書き込みに失敗しました。このタブを閉じると記録が消えます。'
  }[STATE.kind] || '';
  return {
    kind:STATE.kind, durable:STATE.durable, message:msg,
    detail:[mark('local','通常'), mark('session','セッション'), mark('idb','IndexedDB')].join(' / ')
      + (STATE.restoredFrom ? '　復元元: ' + STATE.restoredFrom : '')
      + (STATE.recoveredOnRetry ? '（再試行で回復）' : ''),
    probes:STATE.can, idb:STATE.idbOpened, deviceId:STATE.deviceId
  };
}

global.TubeStore = {
  boot:boot, state:STATE, report:report,
  students:students, student:student, addStudent:addStudent,
  removeStudent:removeStudent, setActive:setActive, setGrade:setGrade,
  activeSid:function(){ return roster.active; },
  rosterRev:function(){ return rosterRev; },
  loadStudent:loadStudent, loadAll:loadAll, save:save,
  adoptStudent:adoptStudent, syncIn:syncIn,
  emptyProgress:emptyProgress, serialize:serialize, hydrate:deserialize,
  buildDelta:buildDelta, markPushed:markPushed,
  exportBundle:exportBundle, importBundle:importBundle,
  summaryCode:summaryCode, readSummaryCode:readSummaryCode,
  isReady:function(){ return ready; }
};

})(window);
