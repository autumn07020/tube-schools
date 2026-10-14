/* ============================================================
   SYNC ―― サーバとのやりとり
   ------------------------------------------------------------
   サーバがあるかどうかは、起動時に /api/health を叩いて確かめる。

     繋がる  → ID とパスワードで入る。記録はサーバに残る
     繋がらない → クラスコードと名前で入る。記録は端末の中だけ

   同じアプリのまま両方で動くので、サーバを止めても生徒の手元は
   壊れない。止まっている間の学習は端末に溜まり、次に繋がったとき
   まとめて送られる（通学の電車内を想定している）。

   ------------------------------------------------------------
   サーバに求める仕様（server/tube_server.py が実装している）

     GET  {base}/health         -> {ok:true}
     POST {base}/login/start    <- {id, cnonce}        -> {salt, iters, nonce}
     POST {base}/login/finish   <- {id, nonce, proof}  -> {token, profile, serverSig}
                                （合言葉そのものは送らない。js/scram.js）
     POST {base}/logout
     GET  {base}/me             -> {profile}
     GET  {base}/p/{sid}        -> {rev, savedAt, blob} / 404
     PUT  {base}/p/{sid}        <- {mode:'delta', cards, hw, hist, meta}
                                   サーバが項目ごとに合流し、新しい版を返す
     GET  {base}/p/{sid}/head   -> {rev, savedAt, serverTime}  安い見張り用
     GET  {base}/curriculum     -> {curriculum:{grades, classes, plans}}
     PUT  {base}/curriculum     <- {curriculum:{…}}                    講師のみ
     GET  {base}/class          -> {students:[{profile, savedAt, blob}]}  講師のみ

   「生徒は自分の分だけ、講師は担当クラスだけ」の判定はサーバが行う。
   ここでは一切判定しない ―― クライアントの判定は判定ではない。
   ============================================================ */
(function(global){
/* 小6以上は講師と同じ漢字で出す（TubeUI.jp）。TubeUI より先に読まれてもよいように。 */
function jp(kana, kanji){ var U = global.TubeUI; return (U && U.jp) ? U.jp(kana, kanji) : kana; }
"use strict";

var TOKEN_KEY = 'tube.school.v1.token';
var WHO_KEY = 'tube.school.v1.who';     /* いま入っている ID（合言葉ではない）。届いたリンクの ID と見くらべる */
var QUEUE_KEY = 'tube.school.v1.outbox';

function lsGet(k){ try{ return localStorage.getItem(k); }catch(e){ return null; } }
function lsSet(k,v){ try{ localStorage.setItem(k,v); }catch(e){} }
function lsDel(k){ try{ localStorage.removeItem(k); }catch(e){} }

function readQueue(){
  try{ return JSON.parse(lsGet(QUEUE_KEY)) || {}; }catch(e){ return {}; }
}
function writeQueue(q){ lsSet(QUEUE_KEY, JSON.stringify(q)); }

function http(cfg){
  var base = String(cfg.base || '/api').replace(/\/$/,'');
  var token = lsGet(TOKEN_KEY) || null;
  var flushing = false;
  var last = {at:0, ok:null};
  var lastRev = {};        // sid -> 直近にサーバが返した版

  function headers(){
    var h = {'Content-Type':'application/json'};
    if(token) h['Authorization'] = 'Bearer ' + token;
    return h;
  }

  async function call(method, path, body){
    var res = await fetch(base + path, {
      method: method, headers: headers(),
      body: body === undefined ? undefined : JSON.stringify(body)
    });
    var data = null;
    try{ data = await res.json(); }catch(e){}
    return {status:res.status, ok:res.ok, data:data};
  }

  /* 送信待ち。圏外でも解けて、繋がったときに送られる。

     行列は1件ずつ「送る直前に読み直し、送れたら読み直して消す」。
     まとめて読んでまとめて書き戻すと、送信中に増えた新しい保存が
     古い控えで上書きされて消える ―― セッション終盤の数問がいつも
     サーバに届かない、という形で出る。 */
  async function flushOnce(){
    var ids = Object.keys(readQueue());
    var sent = 0;
    for(var i=0; i<ids.length; i++){
      var sid = ids[i];
      var item = readQueue()[sid];
      if(!item) continue;
      var r;
      try{
        r = await call('PUT', '/p/' + encodeURIComponent(sid), item);
      }catch(e){
        last = {at:Date.now(), ok:false};   // 圏外。次の機会に。
        return {sent:sent, stop:true};
      }
      if(r.status === 401){
        token = null; lsDel(TOKEN_KEY);      // 期限切れ。入り直してもらう
        return {sent:sent, stop:true};
      }
      if(r.status === 403){
        /* いまログインしている人とは別の生徒のぶん。消してはいけない。
           共用端末では、その子が次に入ったときに送られる。 */
        continue;
      }
      if(!r.ok){ return {sent:sent, stop:true}; }

      /* サーバが項目単位で合流したので、送った分は用済み。
         送信中に増えたぶんだけを残す（行列を読み直して差を取る）。 */
      var q = readQueue();
      var now = q[sid];
      if(now){
        var still = {mode:'delta', cards:{}, hw:{}, hist:now.hist, meta:now.meta};
        var grew = false;
        Object.keys(now.cards || {}).forEach(function(k){
          if(!item.cards || item.cards[k] !== now.cards[k]){ still.cards[k] = now.cards[k]; grew = true; }
        });
        Object.keys(now.hw || {}).forEach(function(k){
          if(!item.hw || item.hw[k] !== now.hw[k]){ still.hw[k] = now.hw[k]; grew = true; }
        });
        if(grew) q[sid] = still; else delete q[sid];
        writeQueue(q);
      }
      sent++;
      lastRev[sid] = (r.data && r.data.rev) || 0;
      last = {at:Date.now(), ok:true};
    }
    return {sent:sent, stop:false};
  }

  async function flush(){
    if(flushing || !token) return;
    flushing = true;
    try{
      /* 送信中に増えたぶんを取りこぼさないよう、進んだら もう一周。
         回数を区切るのは、書き込みが止まらない端末で回り続けないため。 */
      for(var pass=0; pass<5; pass++){
        var r = await flushOnce();
        if(r.stop || !r.sent) break;
        if(!Object.keys(readQueue()).length) break;
      }
    }finally{
      flushing = false;
    }
  }

  window.addEventListener('online', flush);

  return {
    name:'http',
    base:base,

    /* サーバがそこにいるか。落ちていても例外にしない。 */
    probe:async function(){
      try{
        var res = await fetch(base + '/health', {cache:'no-store'});
        if(!res.ok) return null;
        return await res.json();
      }catch(e){ return null; }
    },

    token:function(){ return token; },

    /* デモ起動のときだけ答えが返る。本番では 404。 */
    demoAccounts:async function(){
      try{
        var res = await fetch(base + '/demo', {cache:'no-store'});
        if(!res.ok) return null;
        return (await res.json()).accounts || null;
      }catch(e){ return null; }
    },

    /* 「ためしに見る」のボタンで入る。送るのは ID だけ（合言葉は無い）。デモ起動のサーバだけが答える。 */
    demoEnter:async function(id){
      var who = String(id || '').trim().toLowerCase();
      try{
        var r = await call('POST', '/demo/enter', {id:who});
        if(!r.ok || !r.data || !r.data.token){
          return {ok:false, error:(r.data && r.data.error) || 'いまは入れません'};
        }
        token = r.data.token;
        lsSet(TOKEN_KEY, token);
        lsSet(WHO_KEY, who);
        return {ok:true, profile:r.data.profile};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },

    /* 入る。**合言葉そのものは送らない**（js/scram.js。端末の中で鍵にして、証明だけを送る）。 */
    login:async function(id, password){
      try{
        var r = await TubeScram.login(function(path, body){ return call('POST', path, body); }, id, password);
        if(!r.ok){
          /* サーバの印が合わなかったときは、受け取った合言葉（入った印）を使わずに捨てる。 */
          if(r.token){ try{ token = r.token; await call('POST', '/logout'); }catch(e){} token = null; }
          return {ok:false, error:r.error || 'ログインできません'};
        }
        if(r.data.claim){
          /* 引き換えの言葉で入った（オンラインで渡された席）。**まだ引き換えない。**
             画面が「この端末ではじめる」を押してもらってから、claim() を呼ぶ ―― リンクを開いただけ
             （保護者が先に見た・メールの検査が開いた）で、1回きりの引き換えを使い切らないように。 */
          return {ok:true, claim:true, id:String(id).trim().toLowerCase(), claimToken:r.data.token, words:r.data.words || 3};
        }
        token = r.data.token;
        lsSet(TOKEN_KEY, token);
        lsSet(WHO_KEY, String(id).trim().toLowerCase());
        return {ok:true, profile:r.data.profile};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },

    /* 引き換える。**ここで、この端末が本物の合言葉を作る。** 届けるのは、その値（verifier）だけ。
       引き換えの言葉は、これで使えなくなる。返すのは {ok, newPassword, id, profile（入り直せたとき）}。
       引き換えは済んだのに入り直しに失敗したときも、作った合言葉は必ず返す（画面に出して、書きとめてもらう）。 */
    claim:async function(id, claimToken, words){
      var pw;
      try{
        pw = await TubeScram.makePassword(words || 3);
        var keep = token; token = claimToken;
        var c = await call('POST', '/claim', {verifier: await TubeScram.verifier(pw)});
        token = keep;
        if(!c.ok) return {ok:false, error:(c.data && c.data.error) || '引き換えられませんでした'};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
      try{
        var again = await TubeScram.login(function(path, body){ return call('POST', path, body); }, id, pw);
        if(again.ok){
          token = again.data.token;
          lsSet(TOKEN_KEY, token);
          lsSet(WHO_KEY, String(id).trim().toLowerCase());
          return {ok:true, newPassword:pw, id:id, profile:again.data.profile};
        }
      }catch(e){}
      return {ok:true, newPassword:pw, id:id, profile:null};
    },

    /* いま入っている ID（分からなければ空）。 */
    who:function(){ return token ? (lsGet(WHO_KEY) || '') : ''; },

    /* 保存してある合言葉がまだ通るか。通れば入り直さなくてよい。 */
    me:async function(){
      if(!token) return null;
      try{
        var r = await call('GET', '/me');
        if(r.ok) return r.data.profile;
        if(r.status === 401){ token = null; lsDel(TOKEN_KEY); }
        return null;
      }catch(e){ return null; }
    },

    /* 出る前に送りきる。ここで待たないと、最後にやったぶんが
       サーバに届かないまま端末を離れることになる。
       行列は消さない ―― 送れずに残ったものは、次に入ったときに送る。 */
    logout:async function(){
      try{ await flush(); }catch(e){}
      try{ if(token) await call('POST', '/logout'); }catch(e){}
      token = null;
      lsDel(TOKEN_KEY);
      lsDel(WHO_KEY);
    },

    /* 保存のたびに呼ばれる。行列に積んでから送る ―― 送信の成否と
       端末への保存を切り離しておかないと、圏外で学習が止まる。

       送るのは差分だけ。圏外で溜まったぶんは、行列の中で
       足し合わせていく（同じ項目は新しいほうが残る）。 */
    push:function(sid, delta){
      if(!token) return;
      var q = readQueue();
      var cur = q[sid];
      if(cur && cur.mode === 'delta'){
        Object.assign(cur.cards, delta.cards || {});
        Object.assign(cur.hw,    delta.hw || {});
        Object.assign(cur.hist,  delta.hist || {});
        cur.meta = delta.meta || cur.meta;
      }else{
        q[sid] = {mode:'delta', cards:delta.cards || {}, hw:delta.hw || {},
                  hist:delta.hist || {}, meta:delta.meta || {}};
      }
      writeQueue(q);
      flush();
    },

    /* 他の端末で変わっていないかを、安く見張る。
       進捗の全文（最大95KB）ではなく、番号だけを取る。 */
    head:async function(sid){
      if(!token) return null;
      try{
        var r = await call('GET', '/p/' + encodeURIComponent(sid) + '/head');
        return r.ok ? r.data : null;
      }catch(e){ return null; }
    },

    pull:async function(sid){
      if(!token) return null;
      try{
        var r = await call('GET', '/p/' + encodeURIComponent(sid));
        if(!r.ok) return null;
        return r.data;              // {rev, savedAt, blob}
      }catch(e){ return null; }
    },

    /* ---- 進度（学年 × 科目ごとの分量と範囲）----
       生徒は読むだけ。書けるのは講師だけで、判定はサーバ側。 */
    curriculum:async function(){
      try{
        var r = await call('GET', '/curriculum');
        if(!r.ok) return null;
        var c = r.data.curriculum;
        return (c && c.plans && Object.keys(c.plans).length) ? c : null;
      }catch(e){ return null; }
    },
    putCurriculum:async function(cur){
      try{
        var r = await call('PUT', '/curriculum', {curriculum:cur});
        return r.ok ? {ok:true, curriculum:r.data.curriculum}
                    : {ok:false, error:(r.data && r.data.error) || '保存できませんでした'};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },

    /* ---- 宿題 ----
       生徒には自分宛のものだけが返る。誰に出ているかの判定はサーバ側。 */
    assignments:async function(){
      try{
        var r = await call('GET', '/assignments');
        if(!r.ok) return null;
        return r.data.assignments || [];
      }catch(e){ return null; }
    },
    createAssignment:async function(rec){
      try{
        var r = await call('POST', '/assignments', rec);
        return r.ok ? {ok:true, assignment:r.data.assignment}
                    : {ok:false, error:(r.data && r.data.error) || '作れませんでした'};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    /* 総復習テスト対策。組み分けテストの8日前から出る。
       一覧は軽いほう（問題は持たない）。始めるときに full=1 で取る。 */
    prep:async function(full){
      try{ var r = await call('GET','/assignments/prep'+(full?'?full=1':''));
           return r.ok ? (r.data.prep || null) : null; }catch(e){ return null; }
    },
    /* 中身つき。**寸法と、紙に刷った並びも一緒に受け取る。**
       カメラの採点は、この3つが揃っていないと動かない。 */
    prepAll:async function(){
      try{
        var r = await call('GET','/assignments/prep?full=1');
        if(!r.ok || !r.data.prep) return null;
        var out = r.data.prep;
        out.sheet = r.data.sheet;
        out.paper = r.data.paper || {};
        return out;
      }catch(e){ return null; }
    },
    /* 学年の中で、自分がどのあたりか。順位ではなく「上から何割」。 */
    /* ---- ノートの宿題を写真で出す ---- */

    /* 出す。写真は base64 にして送る。**1回で10枚まで。** */
    submitHw:async function(aid, files){
      try{ var r = await call('POST','/submissions/'+encodeURIComponent(aid),
                              {files:files});
           return r.ok ? r.data : {error:(r.data && r.data.error) || jp('だめでした','送信できませんでした')};
      }catch(e){ return {error:jp('つうしんに しっぱいしました','通信に失敗しました')}; }
    },
    /* 宿題の変更のお知らせ（先生のひとこと付き）。わかった／質問する で返す */
    /* 返した添削を、本人がぜんぶ消す（設定の「添削のデータ」）。 */
    eraseReturned:async function(){
      try{ var r = await call('DELETE','/me/returned'); return r.ok ? {ok:true, n:r.data.n} : {ok:false, error:(r.data&&r.data.error)||jp('けせませんでした','消せませんでした')}; }
      catch(e){ return {ok:false, error:jp('つうしんに しっぱいしました','通信に失敗しました')}; }
    },
    notices:async function(){
      try{ var r = await call('GET','/notices'); return r.ok ? (r.data.notices || []) : null; }catch(e){ return null; }
    },
    ackNotice:async function(id, key, action, text){
      try{ var r = await call('POST','/notices/'+encodeURIComponent(id)+'/ack', {key:key, action:action, text:text || ''});
           return r.ok ? {ok:true, notices:r.data.notices || []} : {ok:false, error:(r.data && r.data.error) || jp('おくれませんでした','送れませんでした')}; }
      catch(e){ return {ok:false, error:jp('つうしんに しっぱいしました','通信に失敗しました')}; }
    },
    /* 版：台帳が最後に変わった時刻（数十バイト）。変わっていたら本体を取りに行く */
    rev:async function(){
      try{ var r = await call('GET','/rev'); return r.ok ? r.data : null; }catch(e){ return null; }
    },
    /* 講師：対面の生徒の紙を取り込む（scan）／添削した答案を返す（return）。生徒の写真と同じ形で送る */
    scanFor:async function(aid, sid, files){
      try{ var r = await call('POST','/submissions/'+encodeURIComponent(aid)+'/'+encodeURIComponent(sid)+'/scan', {files:files});
           return r.ok ? r.data : {error:(r.data && r.data.error) || '取り込めませんでした'}; }
      catch(e){ return {error:'通信に失敗しました'}; }
    },
    returnFor:async function(aid, sid, files, note){
      try{ var r = await call('POST','/submissions/'+encodeURIComponent(aid)+'/'+encodeURIComponent(sid)+'/return', {files:files, note:note});
           return r.ok ? r.data : {error:(r.data && r.data.error) || '返せませんでした'}; }
      catch(e){ return {error:'通信に失敗しました'}; }
    },
    /* 講師：提出箱（授業内の小テストなど）を作る */
    createQuiz:async function(key, title, dueAt, kind, students){
      try{ var body = {key:key, title:title, dueAt:dueAt, kind:kind || ''};
           if(students) body.students = students;
           var r = await call('POST','/quiz', body);
           return r.ok ? {ok:true, assignment:r.data.assignment} : {ok:false, error:(r.data && r.data.error) || '作れませんでした'}; }
      catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },

    /* 講師：提出箱を「選んだ生徒だけ」に出すための、コースの生徒の一覧 */
    quizWho:async function(key){
      try{ var r = await call('GET','/quiz/who?key='+encodeURIComponent(key));
           return r.ok ? {ok:true, students:(r.data && r.data.students) || []} : {ok:false, error:(r.data && r.data.error) || '読めませんでした'}; }
      catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },

    /* 自分が出したもの。{宿題ID: {at, files, seen, note}} */
    /* 出した過去問の点数（生徒の自己申告）。score・max は数字か空（空で消す） */
    subScore:async function(aid, score, max){
      try{ var r = await call('PUT','/submissions/'+encodeURIComponent(aid)+'/score', {score:score, max:max});
           return r.ok ? {ok:true, item:r.data.item} : {ok:false, error:(r.data && r.data.error) || '保存できませんでした'}; }
      catch(e){ return {ok:false, error:'つながりませんでした'}; }
    },
    mySubs:async function(){
      try{ var r = await call('GET','/submissions/mine');
           return r.ok ? (r.data.mine || {}) : null; }catch(e){ return null; }
    },

    /* 講師：その宿題に出ているもの */
    subsOf:async function(aid){
      try{ var r = await call('GET','/submissions/'+encodeURIComponent(aid));
           return r.ok ? (r.data.subs || {}) : null; }catch(e){ return null; }
    },

    /* 講師：見ました＋ひとこと */
    markSeen:async function(aid, sid, note){
      try{ var r = await call('PUT','/submissions/'+encodeURIComponent(aid)+
                              '/'+encodeURIComponent(sid)+'/seen', {note:note});
           return r.ok ? r.data : null; }catch(e){ return null; }
    },

    /* 対策テストの丸つけの結果を送る。**写真は送らない。**
       送るのは「どの問題が合っていたか」だけで、サーバはそこから
       単元ごとの落とし数を数える。 */
    prepResult:async function(subject, rows){
      try{ var r = await call('POST','/assignments/prep/result',
                              {subject:subject, rows:rows});
           return r.ok ? r.data : null; }catch(e){ return null; }
    },

    /* 苦手単元の再テスト。落とした単元だけを集めた4択。 */
    retest:async function(subject){
      try{ var r = await call('GET','/assignments/prep/retest?subject='+
                              encodeURIComponent(subject));
           return r.ok ? r.data : null; }catch(e){ return null; }
    },

    /* 再テストが終わった。よくできていれば「対策ずみ」になる。 */
    retestDone:async function(subject, units, ok, n){
      try{ var r = await call('POST','/assignments/prep/retest',
                              {subject:subject, units:units, ok:ok, n:n});
           return r.ok ? r.data : null; }catch(e){ return null; }
    },

    /* 直前にパソコンで刷った紙。スマホで教科を選ばせないために使う。 */
    lastSheet:async function(){
      try{ var r = await call('GET','/assignments/prep/last');
           return r.ok ? (r.data || null) : null; }catch(e){ return null; }
    },

    rank:async function(){
      try{ var r = await call('GET','/rank');
           return r.ok ? r.data : null; }catch(e){ return null; }
    },
    /* 総復習テスト対策（講師）。クラスの見本を、版を指定して見る。 */
    prepFor:async function(classId, tier){
      var q = '?classId='+encodeURIComponent(classId||'')+
              '&tier='+encodeURIComponent(tier||'');
      try{ var r = await call('GET','/assignments/prep'+q);
           return r.ok ? (r.data.prep || null) : null; }catch(e){ return null; }
    },
    /* 毎日テスト。今週のたしかめ と にがてつぶし の2本。
       講師は クラス×教科 を指定、生徒は自分の分がぜんぶ返る。 */
    dailySets:async function(classId, subject){
      var q = classId ? ('?classId='+encodeURIComponent(classId)+
                         '&subject='+encodeURIComponent(subject||'')) : '';
      try{ var r = await call('GET','/assignments/daily'+q);
           return r.ok ? (r.data.daily || []) : []; }catch(e){ return []; }
    },
    /* 確認テストの案。半分以上がまちがえた枠だけが返る。 */
    suggestions:async function(){
      try{ var r = await call('GET','/assignments/suggest');
           return r.ok ? (r.data.suggestions || []) : []; }catch(e){ return []; }
    },
    takeSuggestion:async function(classId, subject, dueAt){
      try{
        var r = await call('POST','/assignments/suggest',
                           {classId:classId, subject:subject, dueAt:dueAt});
        return r.ok ? {ok:true, assignment:r.data.assignment}
                    : {ok:false, error:(r.data && r.data.error) || '出せませんでした'};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    /* 苦手なところだけを集めて宿題にする。何を出すかは server が決める。 */
    autoAssignment:async function(classId, subject, count, dueAt){
      try{
        var r = await call('POST', '/assignments/auto',
                           {classId:classId, subject:subject,
                            count:count, dueAt:dueAt});
        return r.ok ? {ok:true, assignment:r.data.assignment}
                    : {ok:false, error:(r.data && r.data.error) || '作れませんでした'};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    updateAssignment:async function(id, rec){
      try{
        var r = await call('PUT', '/assignments/' + encodeURIComponent(id), rec);
        return r.ok ? {ok:true, assignment:r.data.assignment}
                    : {ok:false, error:(r.data && r.data.error) || '更新できませんでした'};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    deleteAssignment:async function(id){
      try{
        var r = await call('DELETE', '/assignments/' + encodeURIComponent(id));
        return r.ok ? {ok:true} : {ok:false, error:(r.data && r.data.error) || '消せませんでした'};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },

    /* 名簿の一覧。
       校舎名・役割は全員で同じなので、返事の外側に1回だけ入っている
       （30人ぶん同じ文字を送らないため）。ここで各行に戻す。 */
    classAll:async function(){
      try{
        var r = await call('GET', '/class');
        if(!r.ok) return null;
        var rows = r.data.students || [];
        rows.forEach(function(x){
          x.profile = x.profile || {};
          x.profile.school     = r.data.school || '';
          x.profile.schoolName = r.data.schoolName || '';
          x.profile.role       = r.data.role || 'student';
        });
        return rows;
      }catch(e){ return null; }
    },

    /* 紙の宿題の評価。講師だけが使う。
       未評価の生徒はそもそも返ってこない（欠けているのではなく、無い）。 */
    ratings:async function(aid){
      try{
        var r = await call('GET', '/ratings/' + encodeURIComponent(aid));
        return r.ok ? (r.data.ratings || {}) : null;
      }catch(e){ return null; }
    },
    /* v が null なら取り消し（押し間違いの復旧）。0（出ていない）とは違う。 */
    rate:async function(aid, sid, v){
      var path = '/ratings/' + encodeURIComponent(aid) + '/' + encodeURIComponent(sid);
      try{
        var r = (v === null) ? await call('DELETE', path)
                             : await call('PUT', path, {v:v});
        return !!r.ok;
      }catch(e){ return false; }
    },

    /* 教材。校舎の原本と、自分が使うと決めたもの。 */
    materialsAll:async function(){
      try{ var r = await call('GET','/materials');
           return r.ok ? r.data : null; }catch(e){ return null; }
    },
    /* 教材ごとに「採点する／出すだけ」を切り替える。 */
    setGraded:async function(id, graded){
      try{ var r = await call('PUT','/materials/graded',{id:id, graded:graded});
           return !!r.ok; }catch(e){ return false; }
    },
    /* course を渡すと、そのコースだけの選び直し（見本 T20）。無ければ講師の一覧。 */
    adoptMaterials:async function(ids, course){
      try{ var r = await call('PUT','/materials/adopted', course ? {ids:ids, course:course} : {ids:ids});
           return !!r.ok; }catch(e){ return false; }
    },
    addMaterial:async function(m){
      try{ var r = await call('POST','/materials',m);
           return r.ok ? {ok:true} : {ok:false, error:(r.data&&r.data.error)||'足せません'};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    /* うまく動かないときの報告（人が書いたもの・画面が拾ったエラー）。名前は送らない。 */
    /* 初回登録（招待コードから、保護者が口座を作る。server/join.py）。入る前の口なので、印は要らない。 */
    joinCheck:async function(code){
      try{ var r = await call('POST','/join/check', {code:code});
           return r.ok ? {ok:true, data:r.data} : {ok:false, status:r.status, error:(r.data&&r.data.error)||'確かめられませんでした'};
      }catch(e){ return {ok:false, status:0, error:'サーバに繋がりません'}; }
    },
    joinNew:async function(body){
      try{ var r = await call('POST','/join', body);
           return r.ok ? {ok:true, data:r.data} : {ok:false, status:r.status, error:(r.data&&r.data.error)||'作成できませんでした'};
      }catch(e){ return {ok:false, status:0, error:'サーバに繋がりません'}; }
    },
    joinFinish:async function(body){
      try{ var r = await call('POST','/join/finish', body);
           return r.ok ? {ok:true, data:r.data} : {ok:false, status:r.status, error:(r.data&&r.data.error)||'登録できませんでした'};
      }catch(e){ return {ok:false, status:0, error:'サーバに繋がりません'}; }
    },
    /* 設定：学年・クラス・受講科目（自己申告。ID に集まる）。選べるものを取る／変える。 */
    placementInfo:async function(){
      try{ var r = await call('GET','/me/placement');
           return r.ok ? {ok:true, data:r.data} : {ok:false, error:(r.data&&r.data.error)||'読めませんでした'};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    placement:async function(body){
      try{ var r = await call('PUT','/me/placement', body);
           return r.ok ? {ok:true, profile:r.data.profile, changed:r.data.changed} : {ok:false, status:r.status, error:(r.data&&r.data.error)||'変えられませんでした'};
      }catch(e){ return {ok:false, status:0, error:'サーバに繋がりません'}; }
    },
    report:async function(body){
      try{ var r = await call('POST','/report', body);
           return r.ok ? {ok:true} : {ok:false, error:(r.data&&r.data.error)||'送れませんでした'};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    /* 名簿の一括登録。25名ずつ送る（1件0.16秒かかるため）。 */
    rosterBulk:async function(rows){
      try{ var r = await call('POST','/roster/bulk',{rows:rows});
           return r.ok ? r.data : null; }catch(e){ return null; }
    },

    /* 本部カリキュラムとのズレ。基準が無ければ status:'no-reference'。 */
    drift:async function(){
      try{ var r = await call('GET','/curriculum/drift');
           if(!r.ok) return null;
           /* 学年ごとの本部基準（配列）に、コースごとの進み具合（教材の予定があるコース）を添える。 */
           var out = r.data.drift || [];
           out.courses = r.data.courses || {};
           return out; }catch(e){ return null; }
    },
    markDone:async function(key, unit, off){
      try{ var r = await call('PUT','/curriculum/done',{key:key, unit:unit, off:!!off});
           return !!r.ok; }catch(e){ return false; }
    },

    /* 授業計画。格子を開くと、出すべき宿題はサーバ側で自動発行される。 */
    lessonGrid:async function(){
      try{ var r = await call('GET','/lessons/grid');
           return r.ok ? r.data : null; }catch(e){ return null; }
    },
    lessonPlan:async function(key){
      try{ var r = await call('GET','/lessons/'+encodeURIComponent(key));
           if(!r.ok) return null;
           /* 上位を選ぶ札のための、受け取る生徒（席だけ）。計画そのものではない。 */
           var p = r.data.plan || {};
           if(r.data.receivers) p._receivers = r.data.receivers;
           return p; }catch(e){ return null; }
    },
    /* 1回ぶんだけ直す／足す。学期ぶんを入れ直させないための口。 */
    editLesson:async function(key, n, topic, text, stop){
      try{ var r = await call('PUT','/lessons/'+encodeURIComponent(key)+'/row',
                              {n:n, topic:topic, text:text, stop:!!stop});
           return r.ok ? {ok:true, lesson:r.data.lesson}
                       : {ok:false, error:(r.data&&r.data.error)||'なおせませんでした'};
      }catch(e){ return {ok:false, error:'つながりませんでした'}; }
    },
    addLesson:async function(key, topic, text){
      try{ var r = await call('POST','/lessons/'+encodeURIComponent(key)+'/row',
                              {topic:topic, text:text});
           return r.ok ? {ok:true, lesson:r.data.lesson}
                       : {ok:false, error:(r.data&&r.data.error)||'足せませんでした'};
      }catch(e){ return {ok:false, error:'つながりませんでした'}; }
    },
    setLessons:async function(key, body){
      try{ var r = await call('PUT','/lessons/'+encodeURIComponent(key), body);
           return r.ok ? {ok:true, lessons:r.data.lessons}
                       : {ok:false, error:(r.data&&r.data.error)||'保存できません'};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    /* 上位（上乗せの宿題を受け取る生徒）を選ぶ。 */
    setExtra:async function(key, sids){
      try{ var r = await call('PUT','/lessons/'+encodeURIComponent(key)+'/extra',
                              {students:sids});
           return r.ok ? {ok:true, extra:r.data.extra}
                       : {ok:false, error:(r.data&&r.data.error)||'保存できません'};
      }catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    /* 特筆事項（講師だけ）。 */
    notes:async function(sid){
      try{ var r = await call('GET','/notes/'+encodeURIComponent(sid));
           return r.ok ? (r.data.notes||{}) : null; }catch(e){ return null; }
    },
    saveNote:async function(sid, subject, text){
      try{ var r = await call('PUT','/notes/'+encodeURIComponent(sid),
                              {subject:subject, text:text});
           return r.ok ? (r.data.notes||{}) : null; }catch(e){ return null; }
    },
    /* 保護者への連絡の書き出し（講師×週）。名前も宛先も入らない。 */
    outbox:async function(week){
      try{ var r = await call('GET','/hw/outbox?week='+encodeURIComponent(week));
           return r.ok ? r.data : null; }catch(e){ return null; }
    },
    shiftLessons:async function(key, at, by){
      try{ var r = await call('POST','/lessons/'+encodeURIComponent(key)+'/shift',
                              {at:at, by:by});
           return r.ok ? r.data : null; }catch(e){ return null; }
    },

    /* ---- 講師の机（Claude outputs/PLAN-講師ページ改修.md）----
       今日やること・宿題チェック・成績の診断・生徒ごとの宿題・塾内テスト。
       読み取りは null、書き込みは {ok, error} を返す（画面がそのまま言葉を出せるように）。 */
    today:async function(){
      try{ var r = await call('GET','/today'); return r.ok ? r.data : null; }catch(e){ return null; }
    },
    check:async function(key, n){
      try{ var r = await call('GET','/check?key='+encodeURIComponent(key)+
                              (n ? '&n='+encodeURIComponent(n) : ''));
           return r.ok ? r.data : null; }catch(e){ return null; }
    },
    /* 束の全件に同じ評価（1〜5）。v が null なら消す。note を渡すと、ひとことも残す。 */
    rateBundle:async function(key, n, sid, v, note, worry){
      try{ var body = {key:key, n:n, sid:sid};
           if(v !== undefined) body.v = v;                 /* v を付けなければ、評価には触らない */
           if(note !== undefined) body.note = note;
           if(worry !== undefined) body.worry = !!worry;   /* 理解が心配（講師だけの印） */
           var r = await call('PUT','/check/rate', body);
           return r.ok ? {ok:true} : {ok:false, error:(r.data&&r.data.error)||'保存できませんでした'};
      }catch(e){ return {ok:false, error:'つながりませんでした'}; }
    },
    insightOverview:async function(){
      try{ var r = await call('GET','/insight/overview'); return r.ok ? r.data : null; }catch(e){ return null; }
    },
    insightCourse:async function(key){
      try{ var r = await call('GET','/insight/course?key='+encodeURIComponent(key));
           return r.ok ? r.data : null; }catch(e){ return null; }
    },
    insightStudent:async function(key, sid){
      try{ var r = await call('GET','/insight/student?key='+encodeURIComponent(key)+
                              '&sid='+encodeURIComponent(sid));
           return r.ok ? r.data : null; }catch(e){ return null; }
    },
    insightSuggest:async function(key, sid, n){
      try{ var r = await call('GET','/insight/suggest?key='+encodeURIComponent(key)+
                              '&sid='+encodeURIComponent(sid)+'&n='+encodeURIComponent(n));
           return r.ok ? r.data : null; }catch(e){ return null; }
    },
    /* 提案を見送った（出したは putRule の中でサーバが残す）。 */
    insightFeedback:async function(body){
      try{ var r = await call('POST','/insight/feedback', body); return !!r.ok; }catch(e){ return false; }
    },
    /* 保護者から講師へのメッセージ（生徒の入口＝自分の分、講師＝担当コースの受信箱） */
    messages:async function(){ try{ var r = await call('GET','/messages'); return r.ok ? r.data : null; }catch(e){ return null; } },
    messagePost:async function(subject, text){
      try{ var r = await call('POST','/messages', {subject:subject, text:text});
           return r.ok ? {ok:true, item:r.data.item} : {ok:false, error:(r.data && r.data.error) || '送れませんでした'}; }
      catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    messageSeen:async function(id){ try{ await call('PUT','/messages/'+encodeURIComponent(id)+'/seen'); }catch(e){} },
    messagesInbox:async function(){ try{ var r = await call('GET','/messages'); return r.ok ? r.data : null; }catch(e){ return null; } },
    messageReply:async function(id, text){
      try{ var r = await call('POST','/messages/'+encodeURIComponent(id)+'/reply', {text:text});
           return r.ok ? {ok:true, item:r.data.item} : {ok:false, error:(r.data && r.data.error) || '返せませんでした'}; }
      catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    /* コースでアプリを使う／使わない（講師。自分の担当だけ） */
    setCourseApp:async function(key, on){
      try{ var r = await call('PUT','/lessons/app', {key:key, app:!!on});
           return r.ok ? {ok:true, data:r.data} : {ok:false, error:(r.data && r.data.error) || '切り替えられませんでした'}; }
      catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    /* コースの導入の段階（0 紙のまま … 4 毎日テストまで）。1件でも、まとめてでも同じ口。 */
    setCourseUse:async function(keys, level){
      try{ var r = await call('PUT','/lessons/use', {keys:[].concat(keys), level:level});
           return r.ok ? {ok:true, data:r.data} : {ok:false, error:(r.data && r.data.error) || '切り替えられませんでした'}; }
      catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    /* 成績の伸び（生徒。講師の理解度と同じ数。自分の分だけ） */
    growth:async function(){
      try{ var r = await call('GET','/growth'); return r.ok ? r.data : null; }catch(e){ return null; }
    },
    /* 宿題プリセット（コースごと）。足す宿題の型。 */
    presetsOf:async function(key){
      try{ var r = await call('GET','/presets?key='+encodeURIComponent(key)); return r.ok ? r.data : null; }catch(e){ return null; }
    },
    putPreset:async function(key, preset){
      try{ var r = await call('POST','/presets', {key:key, preset:preset});
           return r.ok ? {ok:true, data:r.data} : {ok:false, error:(r.data && r.data.error) || '保存できませんでした'}; }
      catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    delPreset:async function(key, id){
      try{ var r = await call('DELETE','/presets?key='+encodeURIComponent(key)+'&id='+encodeURIComponent(id));
           return r.ok ? {ok:true, data:r.data} : {ok:false, error:(r.data && r.data.error) || '消せませんでした'}; }
      catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    /* 個別の宿題の一覧（いま誰に何を出しているか）と、選んだ生徒にまとめて出す。 */
    personalBoard:async function(key){
      try{ var r = await call('GET','/personal/board?key='+encodeURIComponent(key)); return r.ok ? r.data : null; }catch(e){ return null; }
    },
    personalBulk:async function(body){
      try{ var r = await call('POST','/personal/bulk', body);
           return r.ok ? {ok:true, data:r.data} : {ok:false, error:(r.data && r.data.error) || '出せませんでした'}; }
      catch(e){ return {ok:false, error:'サーバに繋がりません'}; }
    },
    personalRules:async function(key, sid){
      try{ var r = await call('GET','/personal?key='+encodeURIComponent(key)+'&sid='+encodeURIComponent(sid));
           return r.ok ? r.data : null; }catch(e){ return null; }
    },
    putRule:async function(key, sid, rule, preset){
      try{ var r = await call('POST','/personal', {key:key, sid:sid, rule:rule || {}, preset:preset || null, msg:(rule && rule.msg) || ''});
           return r.ok ? {ok:true, data:r.data}
                       : {ok:false, error:(r.data&&r.data.error)||'保存できませんでした'};
      }catch(e){ return {ok:false, error:'つながりませんでした'}; }
    },
    stopRule:async function(key, sid, id){
      try{ var r = await call('DELETE','/personal?key='+encodeURIComponent(key)+
                              '&sid='+encodeURIComponent(sid)+'&id='+encodeURIComponent(id));
           return r.ok ? {ok:true, data:r.data}
                       : {ok:false, error:(r.data&&r.data.error)||'止められませんでした'};
      }catch(e){ return {ok:false, error:'つながりませんでした'}; }
    },
    scoresOf:async function(key){
      try{ var r = await call('GET','/scores?key='+encodeURIComponent(key));
           return r.ok ? (r.data.tests||[]) : null; }catch(e){ return null; }
    },
    scoresPreview:async function(key, text, date){
      try{ var r = await call('POST','/scores/preview', {key:key, text:text, date:date});
           return r.ok ? {ok:true, data:r.data}
                       : {ok:false, error:(r.data&&r.data.error)||'読めませんでした'};
      }catch(e){ return {ok:false, error:'つながりませんでした'}; }
    },
    scoresImport:async function(body){
      try{ var r = await call('POST','/scores', body);
           return r.ok ? {ok:true, data:r.data}
                       : {ok:false, error:(r.data&&r.data.error)||'取り込めませんでした'};
      }catch(e){ return {ok:false, error:'つながりませんでした'}; }
    },
    scoresRemove:async function(id){
      try{ var r = await call('DELETE','/scores/'+encodeURIComponent(id)); return !!r.ok; }
      catch(e){ return false; }
    },

    pending:function(){ return Object.keys(readQueue()).length; },
    revOf:function(sid){ return lastRev[sid] || 0; },
    lastSync:function(){ return last; },
    flush:flush
  };
}

global.TubeSync = {http:http};

})(window);
