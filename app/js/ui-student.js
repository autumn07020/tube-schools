/* ============================================================
   生徒の画面
   ------------------------------------------------------------
     ホーム      … いまやる1つ ＋ 今の自分（学年の中の今週の量・続いた日）＋ 教科ごと
     宿題        … 残りのまとめ ＋ まずこれから ＋ 教科ごとの宿題（紙／アプリ）
     毎日テスト  … 今日の毎日テスト ＋ 組み分けテスト対策（サーバが返したときだけ）
     学習        … 出題。単語・用語・選択・文法・宿題の番号
     きろく      … カレンダー ＋ 教科ごとの正答率（広い画面ではホームに合流）
     せってい    … 右上のメニューから。ほぞんの状態・書き出し・ログアウト

   コンピュータが苦手な人が使う前提。1画面に「つぎにやること」が
   1つだけ見えるようにし、押せるものは大きく、迷う分岐を作らない。
   ============================================================ */
(function(global){
"use strict";

var U = null;                       // TubeUI（起動後に入る）
function ui(){ return U || (U = global.TubeUI); }
/* 小6以上は講師と同じ漢字で出す（ui-core の jp）。小5以下は今のかなのまま。 */
function jp(kana, kanji){ return ui().jp(kana, kanji); }
function S(){ return ui().S; }
var $, esc, toast;

var pick = {fbSubject:null, hwFocus:null, hwOpen:{}, hwFinOpen:false, goalSheet:false};

function init(){
  var u = ui(); $ = u.$; esc = u.esc; toast = u.toast;
}

/* ============================================================
   宿題の取得（教科をまたいで1本の一覧になる）
   ============================================================ */
/* 宿題の一覧を1度でも受け取ったか。受け取る前に「宿題はありません」と言わない
   （ログインの直後に一瞬「無い」と出て、生徒が安心してしまう）。 */
var hwLoaded = false;
async function refreshHomework(){
  var s = S();
  if(!s.srv) return;
  var rows = await s.srv.assignments();
  if(!rows) return;                 // 圏外。前に取れたものを使い続ける
  TubeHomework.setAll(rows);
  hwLoaded = true;
  try{ localStorage.setItem('tube.school.v1.hw', JSON.stringify(rows)); }catch(e){}
  if(subs !== undefined) refreshSubs();
  if(!s.session) ui().render();
}
function loadCachedHomework(){
  try{
    var raw = localStorage.getItem('tube.school.v1.hw');
    if(raw){ TubeHomework.setAll(JSON.parse(raw) || []); hwLoaded = true; }
  }catch(e){}
}

/* ============================================================
   いまの宿題 ―― ホームと宿題のタブが、同じ数字を出すための1か所
   ------------------------------------------------------------
   数え方はここでしか決めない。2か所で数えると、ホームの「あと3件」と
   宿題のタブの「あと4件」が食い違い、どちらも信じられなくなる。

     のこり    アプリ … まだ全部は終えていない
               紙     … 写真を出していない（先生の評価も付いていない）
     おわった  アプリ … 全部終えた
               紙     … 写真を出した、または先生が1以上の評価を付けた
     （判定は TubeHomework.finished ひとつ）

   おわったものは「今週の分」だけ残す ―― 期限がまだ先か、7日以内に過ぎたもの。
   ただし間隔があいて復習が戻ってきたアプリの宿題は、古くても残す（たしかめる口）。
   紙の未提出は、期限から1週間で落とす（TubeHomework.active と同じ決まり）。

   週で分ける（weekOf）―― **月曜0時から日曜の終わりまでが1週**。
   学年の順位が毎週月曜に0へ戻るのと同じ区切りにする。
     this  今週の分 … 日曜までが期限。期限が過ぎて まだのものも ここに入れる
     next  来週の分 … 月曜から先が期限
     past  先週までが期限で、もう終わったもの（今週の数に入れない。終わった宿題にだけ出る）
   ============================================================ */
var WEEK = 7 * 864e5;

/* 今週の月曜0時と、来週の月曜0時。日付の足し引きは Date に任せる
   （864e5 を引くと、夏時間の切りかわる週に1時間ずれる）。 */
function weekStart(ts){
  var d = new Date(ts);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - (d.getDay() + 6) % 7);
  return d.getTime();
}
function nextWeekStart(ts){
  var d = new Date(weekStart(ts));
  d.setDate(d.getDate() + 7);
  return d.getTime();
}
function weekOf(a, done, now){
  if(a.dueAt && a.dueAt >= nextWeekStart(now)) return 'next';
  if(a.dueAt && a.dueAt < weekStart(now) && done) return 'past';
  return 'this';
}

function hwState(){
  var p = S().me.p, now = Date.now(), rows = [], seen = {}, plain = [];
  loadSubs();
  TubeHomework.all().forEach(function(a){
    var paper = a.route === 'paper';
    var old = a.dueAt && a.dueAt < now - WEEK;
    /* 「出すだけ」の紙（計算テキスト・漢字練習帳など）は数えない・押させない。
       教科の中に「やっておくもの」として添えるだけ。 */
    if(paper && a.graded === false){
      if(!(a.dueAt && a.dueAt < now)) plain.push(a);
      return;
    }
    /* 同じ授業回の紙は1つの束。代表（写真を出す先）の1行にする。 */
    var k = TubeHomework.bundleKey(a);
    if(k){
      if(seen[k]) return;
      seen[k] = 1;
      a = TubeHomework.head(a);
    }
    var done = TubeHomework.finished(p, a);
    /* 過去問は古くても残す（「今まで実施した過去問」の一覧になる。2026-10-11 本人）。 */
    if(old && (paper || (done && !TubeHomework.due(p, a).length)) && !isKakomon(a)) return;
    rows.push({a:a, paper:paper, done:done, sub:subjectOfHw(a), wk:weekOf(a, done, now)});
  });
  var left = rows.filter(function(r){ return !r.done; });
  /* 並び順は TubeHomework.todayQueue が決める
     （期限 → その子が後回しにしがちな教科 → 教科名）。ホームも宿題も同じ順。 */
  var queue = TubeHomework.todayQueue(p, left.map(function(r){ return r.a; }));
  /* 今週の分（終わったものも入れて数える）と、来週の分の残り。
     week.end は日曜の終わり（来週の月曜0時の 1ms 前）。 */
  var week = rows.filter(function(r){ return r.wk === 'this'; });
  var weekLeft = week.filter(function(r){ return !r.done; });
  return {rows:rows, left:left, done:rows.length - left.length,
          paperLeft:left.filter(function(r){ return r.paper; }).length,
          queue:queue, first:queue[0] || null, plain:plain,
          week:{total:week.length, done:week.length - weekLeft.length, left:weekLeft,
                end:nextWeekStart(now) - 1},
          later:left.filter(function(r){ return r.wk === 'next'; })};
}

/* 教科ごとにまとめる。並びは前からの 英・数・理・社・国、知らない教科は後ろ。 */
var SUBJ_ORDER = ['english', 'math', 'science', 'social', 'japanese'];
function homeworkBySubject(rows){
  var by = {}, out = [];
  rows.forEach(function(r){
    (by[r.sub.id] || (by[r.sub.id] = {sub:r.sub, rows:[]})).rows.push(r);
  });
  SUBJ_ORDER.forEach(function(k){ if(by[k]) out.push(by[k]); });
  Object.keys(by).forEach(function(k){ if(SUBJ_ORDER.indexOf(k) < 0) out.push(by[k]); });
  return out;
}

/* 紙の宿題の「何を」と「どこまで」。
   講師の書いた題名の終わりにある範囲（p.13-16 / No.1-50 / 1〜120）を、
   題名から外して分量として別に出す ―― 小さい画面で題名の終わりが切れても、
   どこまでやるかが必ず見えるように。読めなければ題名はそのまま、分量は出さない。
   **数を作らない。** 書いてある範囲を数え直すだけ。 */
var RANGE_END = /\s*(p\.?|No\.?)?\s*(\d+)\s*[-–—〜~]\s*(\d+)\s*$/i;
function paperParts(a){
  var t = String(a.title || ''), m = t.match(RANGE_END);
  var name = m ? t.slice(0, m.index).trim() : '';
  if(!m || !name || +m[3] < +m[2]) return {name:t, amount:''};
  var n = +m[3] - +m[2] + 1, page = /^p/i.test(m[1] || '');
  return {name:name,
          amount:(page ? 'p.' : (m[1] ? 'No.' : '')) + m[2] + '–' + m[3] +
                 '（' + n + (page ? 'ページ' : jp('もん', '問')) + '）'};
}

/* 束（授業1回ぶんの紙）の中身を1件ずつ。上乗せには「追加」を添える。 */
function bundleLines(a){
  var ms = a.route === 'paper' ? TubeHomework.mates(a) : [a];
  return ms.map(function(x){
    var pp = paperParts(x);
    return {name:pp.name, amount:pp.amount, extra:!!x.extra};
  });
}
/* 紙のままの教科（アプリを使っていないコース）。「宿題が消えた」と思わせないための1行。 */
function paperNote(){
  var ps = ((S().me || {}).paper) || [];
  if(!ps.length) return '';
  var names = ps.map(function(id){
    var sub = TubeContent.subject(id) || {name:id};
    return (id === 'math' && String((S().me || {}).grade || '').charAt(0) === 'e') ? '算数' : sub.name;
  });
  return '<p class="paper-note t-full">'+esc(names.join('・'))+jp('は 紙の宿題です（先生から 直接）', 'は紙の宿題です（先生から直接）')+'</p>';
}
/* 先生がこの子だけに足した宿題の印（サーバの personal）。生徒にも「自分だけの分」と分かるように。 */
function personalTag(a){
  return (a && a.personal && a.personal.length) ? '<span class="hw-lx p">'+jp('先生から ついか', '先生から追加')+'</span>' : '';
}
function linesHtml(a, cls){
  return '<div class="'+(cls || 'hw-lines')+'">'+ bundleLines(a).map(function(l){
    return '<div class="hw-line"><span class="hw-ln">'+esc(l.name)+'</span>'+
      (l.amount ? '<span class="hw-la">'+esc(l.amount)+'</span>' : '')+
      (l.extra ? '<span class="hw-lx">'+jp('ついか', '追加')+'</span>' : '')+'</div>';
  }).join('') +'</div>';
}
/* 「出すだけ」の宿題。提出も印も無い ―― 何をやっておくかだけを書く。 */
function plainHtml(list, now){
  if(!list.length) return '';
  return '<div class="hw-plain"><div class="hw-plain-h">'+
      jp('やっておくもの（出さなくて よい）', 'やっておくもの（提出なし）')+'</div>'+
    list.map(function(a){
      var pp = paperParts(a);
      return '<div class="hw-line"><span class="hw-ln">'+esc(pp.name)+'</span>'+
        (pp.amount ? '<span class="hw-la">'+esc(pp.amount)+'</span>' : '')+
        dueTag(a.dueAt, now)+'</div>';
    }).join('') +'</div>';
}
/* アプリの宿題の1行（紙の linesHtml と同じ形 ―― 題名と分量を並べる）。 */
function oneLine(name, amount){
  return '<div class="hw-lines"><div class="hw-line"><span class="hw-ln">'+esc(name)+'</span>'+
    (amount ? '<span class="hw-la">'+esc(amount)+'</span>' : '')+'</div></div>';
}

/* アプリの宿題の分量。today なら今日の分、そうでなければ残り全部。
   時間は1問0.4分の目安 ―― 前から「今日の分 N問・M分」に使っていた数。 */
function roughMin(n){ return Math.max(2, Math.round(n * 0.4)); }
function appAmount(p, a, today){
  var pc = TubeHomework.pace(p, a);
  var n = today ? pc.perDay : pc.left;
  if(!n) return '';
  return (today ? jp('きょうの分 ', '今日の分 ') : jp('あと ', 'あと')) + n + jp('もん', '問') +
         jp('・やく ', '・約') + roughMin(n) + '分';
}

/* どうやってやるか。**色だけで分けない。** 形の印（CSS で描いた紙と画面）と
   ことばを必ず添える。絵文字・記号の字は使わない。 */
/* short … 教科の中の行。ボタンの「提出する／始める」が やり方を言うので、印は「紙／アプリ」だけ。 */
function wayBadge(paper, short, photo){
  return paper
    ? '<span class="hw-way paper"><i></i>'+(short ? '紙' : photo === false ? jp('紙に書いて 先生に出す', '紙に書いて先生に提出')
                                                    : jp('紙に書いて 写真で出す', '紙に書いて写真で提出'))+'</span>'
    : '<span class="hw-way app"><i></i>'+(short ? 'アプリ' : jp('アプリで とく', 'アプリで解く'))+'</span>';
}

/* コースの導入の段階（サーバの useBySubject。0 紙のまま … 4 毎日テストまで）。
   印の無い古いサーバなら、ぜんぶ使える扱い。
     2 未満 … 写真の「出す」を置かない（紙で先生に直接）
     4 未満 … 毎日テストにその教科を出さない */
function useLevelOf(subId){
  var st = S().me && S().me.stu, u = st && st.useBySubject;
  return (u && typeof u[subId] === 'number') ? u[subId] : 4;
}
function photoOk(a){ return useLevelOf(subjectOfHw(a).id) >= 2; }
function quizOn(subId){ return useLevelOf(subId) >= 4; }
/* 毎日テストを使っている教科が1つでもあるか。無ければ、毎日テストのタブも札も入口も出さない
   （使えないものを並べない。導入の段階が 4 のコースができたら、そのとき出る）。 */
function dailyAny(){
  var me = S().me;
  return !!(me && (me.subjects || []).some(function(x){ return quizOn(x.subject.id); }));
}
/* 提出箱の種類（講師が出すときに選ぶ。tube_server.QUIZ_KINDS）。
   テスト（漢字・計算・英語）は「提出」のタブの上に、過去問は「過去問」のタブに分けて出す（2026-10-11 本人）。 */
var TEST_KINDS = ['漢字テスト', '計算テスト', '英語テスト'];
function isTest(a){ return !!(a && a.quiz && TEST_KINDS.indexOf(a.kind || '') >= 0); }
function isKakomon(a){ return !!(a && a.quiz && a.kind === '過去問'); }
/* 過去問のタブ：中3・小6（受験学年）。ほかの学年でも過去問が出ていれば出す。
   学年は me.grade（prepareStudent が作る。me.stu に level は無い ―― 前はそれを見ていて、新しい中3R の口座にタブが出なかった。10-12 本人）。
   小6K は高校受験に向けてゆっくり進む学年で、中学受験の過去問演習が無い（10-12 本人）→ 出ていなければタブも出さない。 */
function kakomonOn(){
  var me = S().me; if(!me) return false;
  var g = me.grade || (me.stu && me.stu.grade) || '', cid = String((me.stu && me.stu.classId) || '');
  if(g === 'j3' || (g === 'e6' && !/k$/i.test(cid))) return true;
  return TubeHomework.all().some(isKakomon);
}

/* その宿題の「次の1手」。アプリは始める、紙は写真を出す。
   **押せるものは必ず動く。** 写真を送る先（サーバ）が無いときと、送っている最中は、
   ボタンを置かずに状態だけを書く。 */
function hwAction(a, big){
  var cls = big ? 'btn' : 'btn small hw-go';
  if(a.route !== 'paper'){
    return '<button class="'+cls+'" data-hw="'+esc(a.id)+'">'+jp('はじめる', '始める')+'</button>';
  }
  if(upBusy === a.id) return '<span class="hw-state">'+esc(upWord)+'</span>';
  if(!photoOk(a))     return '<span class="hw-state">'+jp('紙で 先生に 出します', '紙で先生に提出')+'</span>';
  if(!S().srv)        return '<span class="hw-state">'+jp('まだ 出していません', '未提出')+'</span>';
  if(pending[a.id] && pending[a.id].length) return stageHtml(a);
  var many = TubeHomework.mates(a).length > 1;
  return '<label class="'+cls+' hw-up">'+(many ? jp('まとめて 出す', 'まとめて提出') : jp('出す', '提出する'))+
    '<input type="file" accept="image/*,application/pdf" multiple data-up="'+esc(a.id)+'"></label>';
}

/* ためた写真の札。**1枚撮るごとに送らない。** 撮る → たまる → もう1枚 or 送る。
   iPhone のカメラは1回に1枚しか返さないので、ここに置かないと見開き2枚が送れない。 */
function stageHtml(a){
  ui().subject(subjectOfHw(a).id);           /* 教科へ送るとき、色玉はその教科の色（decisions.md） */
  var list = pending[a.id] || [];
  return '<div class="up-stage" data-stage="'+esc(a.id)+'">'+
    '<div class="up-thumbs">'+ list.map(function(f, i){
      return '<span class="up-th">'+(f.url ? '<img alt="" src="'+f.url+'">' : '<i>PDF</i>')+
        '<button class="up-rm" data-uprm="'+esc(a.id)+'|'+i+'" aria-label="'+jp('この1まいを はずす', 'この1枚を外す')+'">'+ico('x', 14, 2.6)+'</button>'+
        '<b class="num">'+(i + 1)+'</b></span>';
    }).join('') +
    '<label class="up-add hw-up">'+ico('camera', 22, 2)+'<span>'+jp('もう1まい', 'もう1枚')+'</span>'+
      '<input type="file" accept="image/*" capture="environment" data-up="'+esc(a.id)+'"></label>'+
    '</div>'+
    '<p class="tiny up-note2"><button class="lnk" data-upcancel="'+esc(a.id)+'">'+jp('やめる', 'やめる')+'</button></p>'+
    '<div class="up-acts">'+
      '<label class="btn small ghost hw-up">'+jp('写真・PDFを えらぶ', '写真・PDFを選ぶ')+
        '<input type="file" accept="image/*,application/pdf" multiple data-up="'+esc(a.id)+'"></label>'+
      '<button class="btn small up-send" data-upsend="'+esc(a.id)+'"><b class="num">'+list.length+'</b>'+jp('まいを 送る', '枚を送る')+'</button>'+
    '</div>'+
    '<p class="tiny up-note"><span class="num">10</span>'+jp('まいまで。見開きは 2まい に分けて とると 読みやすい', '枚まで。見開きは2枚に分けて撮ると読みやすい')+'</p>'+
  '</div>';
}

/* 終わった宿題の状態（写真を出した紙は submitRow が言う）。 */
function doneState(a){
  return a.route === 'paper' ? jp('先生が 見ました', '確認済み') : jp('おわりました', '完了');
}

/* いちばん先にやる1件の中身。ホームの「いまやるなら これ」と
   宿題のタブの「まずこれから」で、同じ組み方・同じ1件を出す。 */
function firstBody(p, a, label, now){
  var paper = a.route === 'paper';
  var ls = paper ? bundleLines(a) : null;
  var pp = !paper ? {name:a.title, amount:appAmount(p, a, true)}
         : ls.length === 1 ? {name:ls[0].name, amount:ls[0].amount} : null;
  return '<div class="lbl">'+esc(label)+'</div>'+
    '<div class="subj">'+esc(subjectOfHw(a).name)+'</div>'+
    (pp ? '<div class="what">'+esc(pp.name)+'</div>'
        : '<div class="what">'+jp('この回の 宿題 ', 'この回の宿題 ')+ls.length+'件</div>'+ linesHtml(a, 'hw-lines big'))+
    '<div class="why">'+dueTag(a.dueAt, now)+wayBadge(paper, false, paper ? photoOk(a) : undefined)+
      (pp && pp.amount ? '<span>'+esc(pp.amount)+'</span>' : '')+personalTag(a)+'</div>'+
    hwAction(a, true)+
    (paper && S().srv && upBusy !== a.id && photoOk(a)
      ? '<div class="hw-hint">'+jp('ノートの 写真か PDF・10まいまで', 'ノートの写真かPDF・10枚まで')+'</div>' : '');
}

/* ============================================================
   ホームの札
   ============================================================ */
/* 今週の勉強量を、学年の中で比べる札。

   前は「学年のなか 100% ／ 上から 0% あたり」という輪を出していて、
   100 と 0 が同じ札に並び、何を言っているのか読めなかった。
   いまは **今週やった問題数** ひとつを、自分・真ん中・1位の3本で比べ、
   上に1行で「今週 学年で5位（32人中）」と言う。

   **順位の数字は、学年の上半分にいるときだけ出す。**
   CLAUDE.md「宿題と毎日テスト」―― 順位を出すと下位の子がやめる。
   下半分のときは、今週の問題数と「あと何問で真ん中か」だけを言う。

   数はすべて GET /rank の返事そのまま（n・place・week・mid・best）。
   /rank は1つ上の子の問題数を返さないので「あと何問で4位」は言えない。
   言えるのは真ん中と1位までの距離だけ。 */
function volumeTile(){
  var s = S();
  if(rank === undefined && s.srv){
    rank = null;
    s.srv.rank().then(function(got){
      rank = got || null;
      if(rank && !S().session) ui().render();
    });
  }
  if(!rank || rank.n < 2) return '';

  var me = rank.week || 0, mid = rank.mid || 0, best = rank.best || 0;
  var n = rank.n, place = rank.place || n;
  /* 札の見出し（lbl）が「今週解いた問題」と言うので、ここは位置か数だけ。数字は大きく細く。 */
  var head = (best > 0 && place <= Math.ceil(n / 2))
    ? jp('学年で ', '学年で') + '<span class="num">' + esc(String(place)) + '</span>位' +
      '<small>（' + esc(String(n)) + '人中）</small>'
    : '<span class="num">' + esc(String(me)) + '</span>' + jp('もん といた', '問解いた');
  var goal = !best      ? jp('今週は これから。1もん とけば 1位', '今週はこれから。1問解けば1位')
           : me >= best ? jp('1位を キープ', '1位をキープ')
           : me >= mid  ? jp('あと ', 'あと') + (best - me) + jp('もんで 1位', '問で1位')
           :              jp('あと ', 'あと') + (mid - me) + jp('もんで まんなか', '問で真ん中');

  var top = Math.max(me, best, 1);
  var bar = function(mine, v, label){
    var pct = Math.max(3, Math.round(v / top * 100));
    return '<div class="rk-row'+(mine ? ' mine' : '')+(pct < 30 ? ' short' : '')+'">'+
      '<span class="rk-bar"><i style="width:'+pct+'%"></i><span class="rk-k">'+label+'</span></span>'+
      '<span class="rk-v num">'+v+'</span></div>';
  };
  return '<div class="h-card h-6 h-rank">'+
    '<div class="h-row">'+hlbl('users', jp('今週 といた 問題', '今週解いた問題'))+'<span class="h-foot">'+jp('学年の 中で', '学年の中で')+'</span></div>'+
    '<div class="rk-head">'+head+'</div>'+
    '<div class="rk-goal">'+esc(goal)+'</div>'+
    '<div class="rk-bars">'+
      bar(true, me, jp('じぶん', '自分'))+
      bar(false, mid, jp('まんなか', '真ん中'))+
      bar(false, best, '1位')+
    '</div>'+
    '<div class="rk-foot">'+jp('毎週 月ようびに 0に もどります', '毎週月曜日に0に戻ります')+'</div>'+
  '</div>';
}

/* ============================================================
   自分の記録の札（2026-09-12 に足した4枚）
   ------------------------------------------------------------
   本人の指示：成績が伸びている実感と、宿題を出してきた実績が見えないと
   やる気が続かない。情報は増やさず、機能を足す。
     成績の伸び   … 講師の画面と同じ理解度（単元ごと）を教科ごとの折れ線で。数字は最新の1つ
     正答率       … 毎日テストの正答率（直近14日の折れ線、直近7日の数）
     今週の目標   … 毎日テストを週に何日やるか、自分で決める。輪で進み
     これまで     … 直近12週の「今週おわり」を1週1マスで
   数え方は cheer.js（strip・weekDays）と viz.js（series・lineChart）。ここは並べるだけ。
   ============================================================ */
var GROW_N = 8, ACC_DAYS = 14, STRIP_WEEKS = 12;
/* 図に置く点は、0% や 100% でも枠の端に乗らないように 18〜82 の帯へ写す（読む数字は元のまま）。
   上端に乗ると、点が札の上の数字に重なって「迷い点」に見える（本人の指摘）。 */
var PLOT_LO = 18, PLOT_HI = 82;
function plotPts(pts){ return pts.map(function(q){ return {n:q.n, v:q.v === null ? null : Math.round(PLOT_LO + q.v * (PLOT_HI - PLOT_LO) / 100)}; }); }

function loadGrowth(){
  var s = S();
  if(growth !== undefined || !s.srv) return;
  growth = null;
  s.srv.growth().then(function(g){
    growth = g || {courses:[]};
    if(!S().session) ui().render();
  });
}
function subjectNameOf(id, fallback){
  /* 学年で呼び名が違う（小学生は算数）。受けていない教科は来ない（サーバが絞る）。 */
  if(id === 'math' && String((S().me || {}).grade || '').charAt(0) === 'e') return '算数';
  var hit = ((S().me || {}).subjects || []).filter(function(x){ return x.subject && x.subject.id === id; })[0];
  if(hit) return hit.subject.name;
  /* サーバの伸びは name に教科の id を入れてくる（"english"）。英字だけの名前は使わない（10-10） */
  return (fallback && /[^\x00-\x7f]/.test(fallback)) ? fallback : subjName(id);
}
/* 伸びのことば。**いまの高さで3段**（本人：70%以上は素晴らしい。50〜69 は少しほめる、50未満は「がんばろう」）。
   上がっていればそれも言う。下がっても責めない。数字は生徒には出さない（保護者と講師だけ）。 */
function growWord(L, prev){
  if(!L) return jp('まだ これから', 'まだこれから');
  var up = !!(prev && L.v - prev.v >= 5);
  if(L.v >= 70) return up ? jp('上がった', '上がった') : jp('いい ちょうし', 'いい調子');
  if(L.v >= 50) return up ? jp('上がってきた', '上がってきた') : jp('いい かんじ', 'いい感じ');
  return up ? jp('のびてきた', '伸びてきた') : jp('がんばろう', 'がんばろう');
}
function growTone(L){ return !L ? '' : L.v >= 70 ? ' up' : L.v >= 50 ? ' mid' : ' low'; }
function growthTile(showPct){
  var s = S(), V = global.TubeViz;
  if(!s.srv) return '';
  loadGrowth();
  var body;
  if(growth === null){
    body = '<p class="gw-wait">'+jp('しらべています…', '調べています…')+'</p>';
  }else{
    var cs = (growth && growth.courses) || [];
    var rows = cs.map(function(c){
      var pts = V.series(c.units, 'u', GROW_N), L = V.latestOf(pts), prev = null;
      for(var i = pts.length - 1; i >= 0; i--){
        if(pts[i].v !== null && L && pts[i].n !== L.n){ prev = pts[i]; break; }
      }
      var d = (L && prev) ? L.v - prev.v : 0;
      return '<div class="gw-row'+(showPct ? '' : ' nopct')+ui().sjClass(c.subject)+'">'+
        '<span class="gw-sj">'+ui().subjIcon(c.subject, 18)+esc(subjectNameOf(c.subject, c.name))+'</span>'+
        '<span class="gw-line">'+V.lineChart({slots:GROW_N, join:true, lines:[{pts:plotPts(pts), cls:'und'}], guide:null,
            label:esc(subjectNameOf(c.subject, c.name))+' '+esc(growWord(L, prev))})+'</span>'+
        (showPct ? '<span class="gw-v num">'+(L ? L.v+'<i>%</i>' : '―')+'</span>' : '')+
        '<span class="gw-w'+growTone(L)+'">'+esc(growWord(L, prev))+(d >= 5 ? ' ↑' : '')+'</span>'+
      '</div>';
    }).join('');
    body = rows || '<p class="gw-wait">'+jp('先生の 評価や テストが たまると、ここに 出ます', '先生の評価やテストがたまると、ここに出ます')+'</p>';
  }
  return '<div class="h-card h-6 h-grow">'+
    hlbl('trend', jp('せいせきの のび', '成績の伸び'))+
    '<div class="gw-rows">'+body+'</div>'+
    '<span class="h-foot left">'+jp('先生の 評価・テスト・毎日テストから', '先生の評価・テスト・毎日テストから')+'</span>'+
  '</div>';
}
/* 毎日テストの正答率 ―― 直近14日の折れ線と、直近7日の数。 */
function accuracyTile(p){
  var V = global.TubeViz, hist = p.hist || {}, pts = [], ok = 0, n = 0;
  /* 直近14日のうち**やった日だけ**を並べる（やっていない日を空けると、線が切れて
     点が1つ浮いて見えた ―― 「86%」の下に迷い点が出ていた）。 */
  for(var d = ACC_DAYS - 1; d >= 0; d--){
    var h = hist[TubeSRS.dayKey(Date.now() - d * TubeSRS.DAY)];
    if(h && h.n) pts.push({n:ACC_DAYS - d, v:Math.max(0, Math.min(100, Math.round((h.ok || 0) / h.n * 100)))});   /* 記録が崩れていても 0〜100 に収める */
    if(d < 7 && h && h.n){ ok += h.ok || 0; n += h.n || 0; }
  }
  var rate = n ? Math.max(0, Math.min(100, Math.round(ok / n * 100))) : null;
  return '<button class="w w-acc" data-go="daily">'+
    '<span class="lbl">'+jp('毎日テストの 正かい率', '毎日テストの正答率')+'</span>'+
    '<span class="ac-big"><b class="num">'+(rate === null ? '―' : rate)+'</b><i>%</i>'+
      '<small>'+jp('直近7日', '直近7日')+'</small></span>'+
    '<span class="ac-line">'+V.lineChart({slots:Math.max(2, pts.length), lines:[{pts:plotPts(pts), cls:'und'}], guide:null,
        label:'直近14日の正答率'})+'</span>'+
    '<span class="ws">'+(n ? jp(n+'もん といた', n+'問解いた') : jp('きょう はじめよう', '今日始めよう'))+'</span>'+
  '</button>';
}
/* 大きな輪（講師の「宿題チェック」の輪と同じ形）。 */
/* 今週の目標の輪。達成したら内側にもう1本（二重の輪）で褒める。 */
function bigRing(frac, hit){
  var r = 50, c = 2 * Math.PI * r, on = Math.max(0, Math.min(1, frac));
  return '<svg class="gl-ring" viewBox="0 0 120 120" aria-hidden="true">'+
    '<circle class="trk" cx="60" cy="60" r="'+r+'"></circle>'+
    (on > 0 ? '<circle class="val" cx="60" cy="60" r="'+r+'" transform="rotate(-90 60 60)" stroke-dasharray="'+(c * on).toFixed(1)+' '+c.toFixed(1)+'"></circle>' : '')+
    (hit ? '<circle class="in" cx="60" cy="60" r="39"></circle>' : '')+
  '</svg>';
}
/* 今週の目標 ―― 毎日テストを週に何日。決めていなければ「きめる」の札。 */
/* 目標の既定は週3日、小6と中3は週5日（本人）。自分で変えたらそれ。 */
function goalDays(p){
  if(p.goal && p.goal.days > 0) return p.goal.days;
  var g = String((S().me || {}).grade || '');
  return (g === 'e6' || g === 'j3') ? 5 : 3;
}
function goalTile(p, now){
  var C = global.TubeCheer, V = global.TubeViz;
  var days = goalDays(p);
  var done = C.weekDays(p.hist || {}, now, TubeSRS.dayKey);
  var hit = done >= days;
  return '<button class="w w-goal'+(hit ? ' hit' : '')+'" data-goal="open">'+
    /* 見出しの右に目標の日数、輪の中はやった日数だけ（講師の宿題チェックの輪と同じ作り） */
    '<span class="lbl">'+jp('今週の もくひょう', '今週の目標')+'<b class="gl-goal num">'+days+jp('日', '日')+'</b></span>'+
    '<span class="gl-ringwrap">'+bigRing(Math.min(1, done / days), hit)+
      '<span class="gl-c"><b class="num">'+done+'</b></span></span>'+
    '<span class="ws">'+(hit ? jp('たっせい！', '達成！') : jp('あと ', 'あと')+(days - done)+jp('日', '日'))+'</span>'+
  '</button>';
}
/* これまでの実績 ―― 直近12週の「今週おわり」を1週1マス。 */
function stripTile(p, now){
  var C = global.TubeCheer;
  var list = C.rows({all:TubeHomework.all(), bundleKey:TubeHomework.bundleKey, head:TubeHomework.head});
  var fin = function(a){ return TubeHomework.finished(p, a); };
  var sp = C.strip(list, fin, now, STRIP_WEEKS), wk = C.weeks(list, fin, now);
  var fins = sp.filter(function(w){ return w.state === 'fin'; }).length;
  var had = sp.filter(function(w){ return w.state !== 'blank'; }).length;
  return '<div class="h-card h-6 h-strip">'+
    '<div class="h-row">'+hlbl('bars', jp('これまでの しゅくだい', 'これまでの宿題'))+'<span class="h-foot">'+jp('直近12週', '直近12週')+'</span></div>'+
    '<div class="h-striprow">'+
      '<span class="h-big"><b class="num cu">'+(wk.run >= 2 ? wk.run : fins)+'</b><span>'+(wk.run >= 2 ? jp('週 つづけて', '週つづけて') : jp('週 おわり', '週おわり'))+'</span></span>'+
      '<span class="h-bars c12" aria-label="'+jp('直近12週', '直近12週')+'">'+ sp.map(function(w){
        var h = w.state === 'fin' ? 100 : w.state === 'part' ? 55 : 14;
        return '<i class="'+(w.now ? 'now' : w.state === 'fin' ? 'on' : w.state === 'part' ? 'half' : '')+'" style="height:'+h+'%"></i>'; }).join('') +'</span>'+
    '</div>'+
    '<div class="h-ends"><span>12週前</span><span>今週</span></div>'+
  '</div>';
}
/* 目標を決める紙。 */
function goalSheet(p){
  var cur = goalDays(p);
  return '<div class="shade" data-goalshut="1"></div>'+
    '<div class="sheet" role="dialog" aria-modal="true" data-sk="goal">'+
      '<div class="sh-top"><div><div class="sh-n">'+jp('今週の もくひょう', '今週の目標')+'</div>'+
        '<div class="sh-s">'+jp('毎日テストを 週に 何日 やる？', '毎日テストを週に何日やる？')+'</div></div>'+
        '<button class="sh-x" data-goalshut="1" aria-label="'+jp('とじる','閉じる')+'">&times;</button></div>'+
      '<div class="sh-body"><div class="gl-opts">'+ [3, 5, 7].map(function(n){
          return '<button class="pick'+(cur === n ? ' on' : '')+'" data-goalpick="'+n+'" aria-pressed="'+(cur === n)+'">'+n+jp('日', '日')+'</button>';
        }).join('') +
      '</div><p class="tiny">'+jp('月曜から 日曜まで で 数えます。目標に とどいたら、札が 金色に なります',
                                  '月曜から日曜までで数えます。目標に届いたら、札が金色になります')+'</p></div>'+
    '</div>';
}

/* 続いている日 ―― 直近7日の縦棒（やりきった日は濃く）。押すと毎日テストへ。
   日数は streakOf（きろく・毎日テストと同じ計算）。
   alone … となりに学年の札が無いとき。行ぜんぶを使う。 */
function streakTile(p, alone){
  var hist = p.hist || {}, st = streakOf(hist);
  var bars = '', WD = ['日','月','火','水','木','金','土'];
  for(var d = 6; d >= 0; d--){
    var t = Date.now() - d * TubeSRS.DAY, h = hist[TubeSRS.dayKey(t)];
    bars += '<span class="wb"><i class="l'+(!h ? 0 : (h.done ? 2 : 1))+'"></i>'+
            '<span>'+WD[new Date(t).getDay()]+'</span></span>';
  }
  /* ほかの3枚と同じ組み方 ―― 左上に lbl、大きい数、図、下に行き先。 */
  return '<button class="w w-plain dtile w-run '+(alone ? 'wall' : 'wfill')+'" data-go="daily">'+
    '<span class="lbl">'+jp('つづけた 日', '続けた日')+'</span>'+
    '<span class="run-body">'+
      '<span class="wl">'+(st.run > 0
        ? '<span class="num">'+st.run+'</span>'+jp('日 れんぞく', '日連続')
        : jp('きょうから はじめよう', '今日から始めよう'))+'</span>'+
      '<span class="wbars">'+bars+'</span>'+
    '</span>'+
    '<span class="ws">'+jp('毎日テストへ →', '毎日テストへ →')+'</span>'+
  '</button>';
}

/* 今週の宿題 ―― ホームの札。押すと宿題のタブへ。中身は宿題のタブの札と同じ（weekBody）。 */
function hwTile(p, st, now){
  return '<button class="w hw-wk wfill'+(weekFin(st) ? ' fin' : '')+'" data-go="homework">'+
    weekBody(p, st, now, true)+'</button>';
}
function weekFin(st){ return st.week.total > 0 && !st.week.left.length; }

/* 今週の宿題の中身。「あとN件」と、今週の分を1件1コマの帯 ―― 埋まった帯の端が「今週おわり」。
     右上   … 今週の終わりの日（日曜）
     帯     … 今週の分の件数だけコマを並べ、終えた数だけ塗る（数を作らない）
     下     … 来週の分の残り。今週が0件のときは、先週の分をほめる（lastWeek）
   全部終えたら「今週おわり」に変わり、来週の分が次の的になる。 */
function weekBody(p, st, now, home){
  var w = st.week, n = w.left.length, fin = weekFin(st);
  var segs = '';
  for(var i = 0; i < w.total; i++) segs += '<i'+(i < w.done ? ' class="on"' : '')+'></i>';
  var foot = [];
  if(st.later.length){
    foot.push((fin ? jp('つぎは 来週の 分 ', '次は来週の分 ') : jp('来週の 分 ', '来週の分 ')) +
              st.later.length + '件');
  }
  if(home) foot.push(jp('宿題を 見る →', '宿題を見る →'));
  var lw = w.done ? '' : lastWeek(p, now);
  return '<span class="hw-wk-top"><span class="lbl">'+jp('今週の 宿題', '今週の宿題')+'</span>'+
      '<span class="hw-wk-end num">'+dueDate(w.end)+jp(' まで', 'まで')+'</span></span>'+
    (fin ? '<span class="hw-wk-big fin"><i class="hw-wk-ck"></i>'+jp('今週 おわり', '今週おわり')+'</span>'
         : '<span class="hw-wk-big">'+jp('あと', 'あと')+'<span class="num">'+n+'</span>件</span>')+
    '<span class="hw-wk-low">'+
      (w.total ? '<span class="hw-wk-track"><span class="hw-wk-segs">'+segs+'</span>'+
                 '<span class="num">'+w.done+'/'+w.total+'</span></span>' : '')+
      (foot.length ? '<span class="hw-wk-foot">'+ foot.map(function(t){
          return '<span>'+esc(t)+'</span>'; }).join('') +'</span>' : '')+
      (lw ? '<span class="hw-wk-foot">'+esc(lw)+'</span>' : '')+
    '</span>';
}

/* 先週の宿題 ―― 先週（月曜〜日曜）が期限だったもののうち、終えた数。
   **1件も終えていなければ出さない。** 「0 / 4」は責める数字にしかならない
   （紙でやって写真を出していないだけの子もいる）。 */
function lastWeek(p, now){
  var mon = weekStart(now), prev = weekStart(mon - 1);          /* 今週と先週の月曜 0時 */
  /* 束（授業1回ぶんの紙）で数える。「出すだけ」は数えない。 */
  var seen = {};
  var due = TubeHomework.all().filter(function(a){
    if(!(a.dueAt >= prev && a.dueAt < mon)) return false;
    if(a.route === 'paper' && a.graded === false) return false;
    var k = TubeHomework.bundleKey(a);
    if(!k) return true;
    if(seen[k]) return false;
    return (seen[k] = true);
  }).map(function(a){ return TubeHomework.head(a); });
  var done = due.filter(function(a){ return TubeHomework.finished(p, a); }).length;
  return done ? jp('先週の 宿題 ', '先週の宿題 ') + done + ' / ' + due.length + jp('件 おわり', '件完了') : '';
}

/* いまやるなら これ ―― 1つだけ。宿題が残っていれば宿題、無ければ毎日テスト。
   **押したら、その場で始まる。** 紙は写真を出す口が開き、アプリは出題が始まる。
   （前は紙の宿題に「おわった」を押させていた。押しても何も出さないので、
     やったかどうかが先生にも本人にも残らなかった。） */
function homeNext(p, st, now){
  var label = jp('いまやるなら これ', '今やるならこれ');
  if(!hwLoaded && !st.rows.length){
    return '<div class="next quiet w2 tile">'+
      '<div class="lbl">'+esc(label)+'</div>'+
      '<div class="what">'+jp('宿題を よみこんでいます…', '宿題を読み込んでいます…')+'</div>'+
    '</div>';
  }
  /* 「ほか N件」は置かない ―― 隣の「今週の宿題」の札が、週で区切った数を言う。 */
  if(st.first){
    return '<div class="next w-blue w2 tile">'+ firstBody(p, st.first, label, now) +'</div>';
  }
  var dp = dailyPick(p);
  if(dp.next){
    return '<div class="next w-blue w2 tile">'+
      '<div class="lbl">'+esc(label)+'</div>'+
      '<div class="subj">'+(st.rows.length ? jp('宿題は おわり。つぎは 毎日テスト', '宿題は完了。次は毎日テスト')
                                           : '毎日テスト')+'</div>'+
      '<div class="what">'+esc(dp.next.x.subject.name)+'</div>'+
      '<div class="why"><span>'+dp.next.left+jp('もん', '問')+jp('・やく ', '・約')+
        roughMin(dp.next.left)+'分</span></div>'+
      '<button class="btn" data-start="'+esc(dp.next.x.subject.id)+'">'+jp('はじめる', '始める')+'</button>'+
    '</div>';
  }
  return '<div class="next quiet w2 tile">'+
    '<div class="lbl">'+esc(label)+'</div>'+
    '<div class="subj">'+jp('きょうの分は おわり', '今日の分は終わり')+'</div>'+
    '<div class="what">'+(dp.rows.length
      ? jp('宿題も 毎日テストも おわりました。', '宿題も毎日テストも終わりました。')
      : jp('いま出ている宿題は ありません。', '今出ている宿題はありません。'))+'</div>'+
    (dp.any
      ? '<button class="btn" data-extra="'+esc(dp.any)+'">'+jp('もう少し やる', 'もう少しやる')+'</button>'
      : (dailyAny() ? '<button class="btn ghost" data-go="daily">毎日テストへ</button>' : ''))+
  '</div>';
}

/* 毎日テストの「次の1教科」。ホームと毎日テストのタブで同じものを指す。
   残っている教科のうち、**できが低い教科**から（前からの決まり。
   残りが多い教科ではなく、手薄な教科から声をかける）。
     rows … 教科ごとの {x, ac, pct, left}   left … 今日の残りの合計
     any  … 全部終わった日に「もう少しやる」を当てる教科（いちばん手薄な教科） */
function dailyPick(p){
  /* 毎日テストは、導入の段階が「毎日テストまで」（4）のコースの教科だけ。 */
  var rows = (S().me.subjects || []).filter(function(x){ return quizOn(x.subject.id); }).map(function(x){
    var pl = TubeSRS.plan(p, x.plan, x.order);
    /* ゲージは **やった分の中での正解率**。
       「覚えた項目 ÷ 単元ぜんぶ」だと、始めたばかりの生徒は必ず数%に
       なる。1週間まじめにやって 4% と出る画面では、続かない。 */
    var ac = TubeSRS.accuracy(p, x.order);
    return {x:x, ac:ac, pct:ac ? ac.pct : 0, left:pl.total};
  });
  var byPct = function(a, b){ return a.pct - b.pct; };
  var todo = rows.filter(function(r){ return r.left > 0; }).sort(byPct);
  var weakest = rows.slice().sort(byPct)[0];
  return {rows:rows, next:todo[0] || null,
          left:rows.reduce(function(n, r){ return n + r.left; }, 0),
          any:weakest ? weakest.x.subject.id : null};
}

/* 押せるものをまとめて結ぶ。ホーム・宿題・毎日テストで同じ口を使う ――
   画面ごとに書き分けると、片方だけ結び忘れて「押しても動かない」ができる。 */
function bindStarts(m){
  m.querySelectorAll('[data-hw]').forEach(function(x){
    x.onclick = function(){ startHomework(x.dataset.hw); };
  });
  m.querySelectorAll('[data-start]').forEach(function(x){
    x.onclick = function(){ startDaily(x.dataset.start); };
  });
  m.querySelectorAll('[data-extra]').forEach(function(x){
    x.onclick = function(){ startExtra(x.dataset.extra); };
  });
  m.querySelectorAll('[data-go]').forEach(function(x){
    x.onclick = function(){ ui().go(x.dataset.go, 'push'); };
  });
  bindUpload(m);
}

/* ------------------------------------------------------------
   宿題の教科
   ------------------------------------------------------------ */
function subjectOfHw(a){
  var id = (a.lesson && a.lesson.key && a.lesson.key.indexOf(':') > 0)
    ? a.lesson.key.split(':')[1]
    : ((TubeContent.booklet(a.source) || {}).subject || 'english');
  return TubeContent.subject(id) || {id:id, name:id, short:id};
}

/* ------------------------------------------------------------
   期限 ―― **形は1つ**。「あと4日」と「9/15(火)」を1枚の札に並べる。
   ホームの1件・まずこれから・教科の行・やっておくもの、どこでも dueTag を使う。
   ------------------------------------------------------------ */
var WDAY = ['日','月','火','水','木','金','土'];
/* 暦の上で何日先か（時刻は見ない）。夏時間の日でも round で整数に戻る。 */
function dayDiff(ts, now){
  var a = new Date(ts), b = new Date(now);
  a.setHours(0, 0, 0, 0); b.setHours(0, 0, 0, 0);
  return Math.round((a.getTime() - b.getTime()) / 864e5);
}
function dueDate(ts){
  var d = new Date(ts);
  return (d.getMonth() + 1) + '/' + d.getDate() + '(' + WDAY[d.getDay()] + ')';
}
function dueWord(ts, now){
  if(!ts) return '';
  var d = dayDiff(ts, now);
  /* 期限が過ぎたものは「すぎています」ではなく「さきに やろう」。
     過ぎたことは変えられないが、いまやることは選べる。 */
  return ts < now  ? jp('さきに やろう', '先に取り組もう')
       : d <= 0    ? jp('きょう まで', '今日まで')
       : d === 1   ? jp('あした まで', '明日まで')
       :             jp('あと ', 'あと') + d + '日';
}
/* 札の色は3段。now … 今日まで・先に取り組むもの（黄）／ week … 日曜までの今週の分（青）／
   later … 来週から（灰）。色だけに頼らず、ことばと日付を必ず書く。 */
function dueTag(ts, now){
  if(!ts) return '';
  var tone = (ts < now || dayDiff(ts, now) <= 0) ? 'now'
           : ts < nextWeekStart(now) ? 'week' : 'later';
  return '<span class="hw-due '+tone+'"><b>'+esc(dueWord(ts, now))+'</b>'+
    '<span class="num">'+dueDate(ts)+'</span></span>';
}

var rank = undefined;      /* 学年の中の位置。undefined=未取得 */
var growth = undefined;    /* 成績の伸び（GET /growth）。undefined=未取得、null=取りに行っている */
var prep = undefined;      /* 総復習テスト対策。undefined=未取得 / null=無し */
var prepFull = null;       /* 中身つき。始めるときだけ取りに行く */

/* パソコンで直前に刷った紙。**スマホで教科を聞き直さないため**に使う。

   生徒はパソコンで解いて、スマホで写真を撮る。そのとき
   「どの教科の紙ですか」と5つならべて選ばせるのは、要らない手間である ――
   数分前に同じアカウントが何を刷ったかは、サーバが知っている。

   undefined = まだ聞いていない / null = 無い / {subject, tier, at} */
var lastSheet = undefined;

function loadLastSheet(){
  if(lastSheet !== undefined) return;
  lastSheet = null;
  var s = S();
  if(!s.srv || !s.srv.lastSheet) return;
  s.srv.lastSheet().then(function(got){
    lastSheet = (got && got.subject) ? got : null;
    if(lastSheet && !S().session) ui().render();
  });
}

/* 組み分けテストが近いか。**毎日テストのタブを開いたときだけ**聞きに行く。
   返事は待たずに画面を描き、来たときに毎日テストを見ていれば描き直して差し込む。
   ほかの画面や出題中なら描き直さない（次に開いたときに出る）。
   **画面の側で対策を作り出さない。** 出すかどうかはサーバが日程から決める。 */
function loadPrep(){
  if(prep !== undefined) return;
  prep = null;
  var s = S();
  if(!s.srv) return;
  s.srv.prep().then(function(got){
    prep = got || null;
    if(prep && !S().session && S().view === 'daily') ui().render();
  });
}

/* 節の見出し。**日本語だけ**で、中身をそのまま言う短い名前にする
   （2026-09-11 本人：英語を添えてかっこつける必要はない）。講師の画面と同じ組み方 ――
   左に柱を立て、right（日付の区切りなど）があれば右端に置く（extra に gridbar）。
   名前は呼ぶ側で jp() に通す（小5以下はかな）。 */
function sectHead(title, extra, right){
  return '<div class="secthead '+(extra || '')+'">'+
    '<h2>'+esc(title)+'</h2>'+
    (right ? '<div class="wk num">'+esc(right)+'</div>' : '')+
  '</div>';
}

/* 先生から ―― 返ってきたものを、**教科ごとに1行**で見せる（「教科ごと」と同じ形）。

   **これが無いと、写真を出す意味が伝わらない。**
   出しっぱなしで何も返ってこないなら、次から出さなくなる。
   前は教科も日付も無い1枚の札に並べていて、「新中学問題集 p.30-33」が
   数学なのか理科なのか、いつの宿題なのかが分からなかった。
   1行には、その教科でいちばん新しい返事を1つだけ置く。全部は押した先で見る
   ―― 返事が何十件も並ぶと、読む前にやる気がなくなる。 */
function feedbackCard(p, bare){
  var jp = ui().jp;
  var items = returnedItems(p);
  if(!items.length) return '';
  var by = {}, order = [];
  items.forEach(function(x){
    var g = by[x.sub.id];
    if(!g){ g = by[x.sub.id] = {sub:x.sub, list:[]}; order.push(g); }
    g.list.push(x);
  });
  return (bare ? '<div class="lbl t-full ch-subs">'+jp('教科ごとの へんじ', '教科ごとの返事')+'</div>' : sectHead('先生から', 't-full'))+
    '<div class="sublist t-full">'+ order.map(function(g){
      var x = g.list[0];                       /* いちばん新しい返事 */
      var st = ['<span>'+esc(hwDay(x.a))+'</span>'];
      if(x.v !== null && x.v > 0) st.push(rateChip(x.v, x.prov));
      else if(x.s && !x.s.seen)   st.push('<span class="pap">'+esc(jp('まだ 見てもらっていません', '確認待ち'))+'</span>');
      if(g.list.length > 1)       st.push('<span class="pap">'+esc(jp('ほか ', 'ほか'))+(g.list.length - 1)+'件</span>');
      return '<button class="subrow fbsub" data-fbsub="'+esc(g.sub.id)+'">'+
        '<div class="nm">'+esc(g.sub.name)+'</div>'+
        '<div class="mid">'+
          '<div class="fbt">'+esc(x.a.title)+'</div>'+
          '<div class="st">'+st.join('')+'</div>'+
          (x.note ? '<div class="fbn">'+esc(x.note)+'</div>' : '')+
        '</div>'+
        '<div class="ar">›</div>'+
      '</button>';
    }).join('') +'</div>';
}

/* 返ってきたもの ＝ 先生が評価を付けた宿題（出ていない＝0 は除く）と、写真を出した宿題。
   新しい返事から順に並べる。 */
function returnedItems(p){
  loadSubs();
  var ms = function(t){ return !t ? 0 : (t < 1e12 ? t * 1000 : t); };
  var out = [];
  TubeHomework.sorted(p).forEach(function(a){
    /* 束は代表の1件だけ（同じ印が2〜3件並ばないように）。 */
    if(TubeHomework.bundleKey(a) && TubeHomework.head(a).id !== a.id) return;
    var sb = (subs || {})[a.id] || null;
    var v = (a.rated && typeof a.rated.v === 'number') ? a.rated.v : null;
    if(!sb && !(v !== null && v >= 1)) return;
    out.push({a:a, s:sb, v:v, prov:!!(a.rated && a.rated.provisional), note:(sb && sb.note) || '', sub:subjectOfHw(a),
              when:Math.max(ms(sb && (sb.seen || sb.at)), ms(a.rated && a.rated.at),
                            ms(a.assignedAt))});
  });
  /* **宿題の日付の新しい順。** 返事の時刻で並べると、まとめて評価した日に
     古い宿題が上に来て、「いつのものか」がかえって分からなくなる。 */
  return out.sort(function(x, y){
    return ms(y.a.assignedAt || y.a.dueAt) - ms(x.a.assignedAt || x.a.dueAt) ||
           y.when - x.when;
  });
}

/* いつの宿題か。出された日（授業の日）で言う。 */
function hwDay(a){
  var t = a.assignedAt || a.dueAt;
  if(!t) return '';
  var d = new Date(t);
  return (d.getMonth() + 1) + '/' + d.getDate() + ui().jp('の しゅくだい', 'の宿題');
}

/* 先生の評価（5段階）の言い方。**数字は生徒に見せない**（講師が決めた）。
   1や2が数字で並ぶと、下の子ほど見るのをやめる。言葉は前向きに寄せる。 */
/* 評価の札。prov は仮の評価（先生の評価が無いまま7日過ぎた紙の宿題は、仮に「できました」。薄く出す） */
function rateChip(v, prov){
  if(!(v > 0)) return '';
  return '<span class="rt v'+Math.min(5, Math.max(1, Math.round(v)))+(prov ? ' prov' : '')+'"'+
    (prov ? ' title="'+esc(jp('先生の ひょうかを まっています（かりの ひょうか）', '先生の評価待ち（仮の評価）'))+'"' : '')+'>'+
    (v >= 4 ? ico('star', 14, 2.2) : ico('check', 14, 2.2))+esc(rateWord(v))+(prov ? jp('（かり）', '（仮）') : '')+'</span>';
}
function rateWord(v){
  if(!(v > 0)) return ui().jp('でていません', '未提出');
  return v >= 5 ? jp('たいへん よくできました', '大変よくできました') : v >= 4 ? jp('よくできました', 'よくできました') : jp('みました', 'みました');
}

/* ============================================================
   ホーム ―― 宿題と毎日テストへの入口
   ------------------------------------------------------------
   小さく、前向きに。ここで答えるのは3つだけ。
     1. いま何をやるか（1つだけ。押せば始まる）
     2. 自分はいまどのあたりか（学年の中の今週の量・続いている日）
     3. 教科ごとに、あと何件で次は何か（中身は宿題のタブ）
   一覧はここに並べない。並べると、開くたびに「まだこれだけある」で終わる。
   ============================================================ */
/* 組分けの申告 ―― テストの結果で クラスが 変わる。塾は ID と名前を むすばないので、新しいクラスは 本人に 聞く。
   結果が出てから 2週間、ホームのいちばん上に 出る。答えると 消える（あとから 設定でも かえられる）。 */
function placeAskCard(){
  var s = S(), ask = s.me.placeAsk;
  if(!ask || !s.srv) return '';
  var reg = s.me.reg || {};
  var ks = TubeConfig.classes().filter(function(k){ return k.grade === reg.grade; });
  /* year … 学年が上がって、行き先のクラスが決まらなかった（小6→中1 は、クラスの記号が変わる）。答えるまで出る。 */
  var year = !!ask.year;
  if(ks.length < (year ? 1 : 2)) return '';
  var gname = (TubeConfig.grade(reg.grade) || {}).name || '';
  var chosen = pick.paClass || '';
  var md = /^\d{4}-(\d{2})-(\d{2})$/.exec(ask.toDay || '');
  return '<div class="panel t-full pa-card" id="paCard">'+
    '<div class="lbl">'+(year ? jp('あたらしい がくねん','新しい学年') : jp('くみわけテストの けっか','組分けテストの結果'))+'</div>'+
    '<h2 class="pa-h">'+(year ? esc(gname)+jp('の クラスを おしえて ください','のクラスを教えてください') : jp('クラスは どちらに なりましたか','クラスはどちらになりましたか'))+'</h2>'+
    '<div class="pa-tiles">'+ ks.map(function(k){
      var letter = k.name.replace(gname, '') || k.name;
      return '<button class="jn-tile jn-cls pa-tile" data-pa="'+esc(k.id)+'" aria-pressed="'+(chosen === k.id)+'">'+
        '<span class="jn-letter">'+esc(letter)+'</span><span class="jn-small">'+(k.id === reg.classId ? jp('いまの クラス','いまのクラス') : esc(k.name))+'</span></button>';
    }).join('') +'</div>'+
    /* 点数（任意）。入れると、先生が苦手をより正確につかめる（見本 K01 4d） */
    (!year ? (pick.paScores
      ? '<div class="pa-scores"><span class="h-lbl grey">'+jp('点数（にゅうりょくは にんい）','点数（任意）')+'</span><div class="pa-sgrid">'+ (s.me.subjects || []).map(function(x){
          var id = x.subject.id;
          return '<label class="pa-sf'+ui().sjClass(id)+'"><span class="pa-sl">'+ui().subjIcon(id, 16)+esc(x.subject.name)+'</span>'+
            '<span class="pa-si"><input inputmode="numeric" maxlength="3" data-pasc="'+esc(id)+'" value="'+esc((pick.paScoreVals || {})[id] || '')+'"><i>点</i></span></label>';
        }).join('') +'</div><p class="pa-note pa-left">'+jp('入れると、先生が あなたの にがてを より せいかくに つかめます。入れなくても だいじょうぶです。','入れると、先生があなたの苦手をより正確につかめます。入れなくても大丈夫です。')+'</p></div>'
      : '<button class="btn ghost pa-scbtn" id="paScores">'+jp('点数も 入れる（にんい）','点数も入れる（任意）')+'</button>') : '')+
    '<button class="btn" id="paGo"'+(chosen ? '' : ' disabled')+'>'+
      (chosen ? (year ? jp('この クラスに する','このクラスにする') : chosen === reg.classId ? jp('かわらない（これで きめる）','変わらない（これで決める）') : jp('この クラスに かえる','このクラスに変える')) : jp('クラスを えらぶ','クラスを選ぶ'))+'</button>'+
    '<p class="tiny pa-note">'+(md ? (+md[1])+'/'+(+md[2])+' まで。' : '')+jp('あとから「せってい」でも かえられます。','あとから「設定」でも変えられます。')+'</p>'+
    '</div>';
}
/* 卒業した生徒（学年の繰り上げで、中3がクラスから外れた）。記録は見られる。新しい宿題は届かない。 */
function gradCard(){
  if(!S().me.grad) return '';
  return '<div class="panel t-full pa-card" id="gradCard">'+
    '<div class="lbl">卒業</div>'+
    '<h2 class="pa-h">卒業おめでとうございます</h2>'+
    '<p class="pa-note pa-left">これまでの記録は、このまま見られます。新しい宿題は届きません。使わなくなって3か月たつと、記録は自動で消えます。</p>'+
    '</div>';
}
function bindPlaceAsk(m){
  var s = S(), ask = s.me.placeAsk;
  if(!ask) return;
  [].forEach.call(m.querySelectorAll('[data-pa]'), function(b){
    b.onclick = function(){ pick.paClass = b.getAttribute('data-pa'); ui().render(); };
  });
  var sb = m.querySelector('#paScores');
  if(sb) sb.onclick = function(){ pick.paScores = true; ui().keepInPlace(sb); ui().render(); };
  m.querySelectorAll('[data-pasc]').forEach(function(x){
    x.oninput = function(){ pick.paScoreVals = pick.paScoreVals || {}; pick.paScoreVals[x.dataset.pasc] = x.value.replace(/[^0-9]/g, '').slice(0, 3); };
  });
  var go = m.querySelector('#paGo');
  if(go) go.onclick = async function(){
    if(!pick.paClass || pick.paBusy) return;
    pick.paBusy = true; go.disabled = true;
    var scores = {};
    Object.keys(pick.paScoreVals || {}).forEach(function(k){ var v = parseInt(pick.paScoreVals[k], 10); if(v >= 0 && v <= 200) scores[k] = v; });
    var body = ask.year ? {classId:pick.paClass} : {classId:pick.paClass, exam:ask.exam};
    if(Object.keys(scores).length) body.scores = scores;
    var r = await s.srv.placement(body);
    pick.paBusy = false;
    if(!r.ok){ toast(r.error); go.disabled = false; return; }
    pick.paClass = null; pick.paScores = false; pick.paScoreVals = null;
    toast(jp('ありがとう。クラスを おぼえました','クラスを登録しました'));
    ui().signInServer(r.profile, {quiet:true, to:'today'});
  };
}
/* ============================================================
   ホームの札（2026-10-08 の見本 S01）。古い札（.w）は宿題のタブなどがまだ使う。
   ============================================================ */
function ico(n, sz, sw){ return ui().ico(n, sz, sw); }
function hlbl(icon, text, cls){ return '<span class="h-lbl'+(cls ? ' '+cls : '')+'">'+(icon ? ico(icon) : '')+esc(text)+'</span>'; }
/* 時間帯のあいさつ（短く・責めない） */
function greeting(){
  var hr = new Date().getHours();
  var k = hr < 5 ? 'night' : hr < 11 ? 'morning' : hr < 17 ? 'day' : hr < 22 ? 'evening' : 'night';
  return {morning: jp('おはよう ございます', 'おはようございます'), day: jp('きょうは べんきょう びより！', '今日は勉強日和！'),
          evening: jp('きょうも がんばろう', '今日もがんばろう'), night: jp('あとすこし、もうすこし！', 'あと少し、もうすこし！')}[k];
}
/* 輪。太さ 10。満ちたら金、7/7 は二重の輪 */
/* 輪の中の数字。桁が増えたら小さく（10-11 本人：「10/10」が輪からはみ出ていた。2桁以上を想定していない）。
   字の数（分子＋分母）を data-len に置き、paper.css が --rs で大きさを決める。 */
function ringC(num, den, cls){
  var len = String(num).length + String(den || '').replace(/<[^>]*>/g, '').length;
  return '<span class="h-ringc" data-len="'+len+'"><span class="h-ringv"><b class="num'+(cls === '' ? '' : ' cu')+'">'+num+'</b>'+
    (den ? '<small>'+den+'</small>' : '')+'</span></span>';
}
function ringSvg(frac, full){
  var r = 42, c = 2 * Math.PI * r, on = Math.max(0, Math.min(1, frac || 0));
  return '<svg viewBox="0 0 100 100" aria-hidden="true">'+
    '<circle cx="50" cy="50" r="'+r+'" fill="none" stroke="rgba(60,60,67,.12)" stroke-width="10"></circle>'+
    (on > 0 ? '<circle cx="50" cy="50" r="'+r+'" fill="none" stroke="'+(full ? '#F9B900' : '#0A6FC7')+'" stroke-width="10" stroke-linecap="round" stroke-dasharray="'+(c*on).toFixed(1)+' '+c.toFixed(1)+'"></circle>' : '')+
    (full ? '<circle cx="50" cy="50" r="31" fill="none" stroke="#F9B900" stroke-width="4"></circle>' : '')+
  '</svg>';
}
function dueLine(ts, now){
  if(!ts) return '';
  var d = dayDiff(ts, now), m = new Date(ts);
  var w = (ts < now || d <= 0) ? dueWord(ts, now) : '<span class="num">'+(m.getMonth()+1)+'/'+m.getDate()+'</span>（'+WDAY[m.getDay()]+'）'+jp('まで', 'まで');
  return '<span class="h-due">'+w+'<i class="h-arr">'+ico('chev', 14, 2.4)+'</i></span>';
}
/* 今やるならこれ ―― 1つだけ。宿題が残っていれば宿題、無ければ毎日テスト。 */
function heroCard(p, st, now){
  var label = jp('いまやるなら これ', '今やるならこれ');
  if(!hwLoaded && !st.rows.length){
    return '<div class="h-card h-6 h-hero"><span class="h-sub">'+esc(label)+'</span>'+
      '<div class="h-title">'+jp('宿題を よみこんでいます…', '宿題を読み込んでいます…')+'</div></div>';
  }
  if(st.first){
    var a = st.first, paper = a.route === 'paper', sj = subjectOfHw(a);
    var ls = paper ? bundleLines(a) : null;
    var pp = !paper ? {name:a.title, amount:appAmount(p, a, true)}
           : ls.length === 1 ? {name:ls[0].name, amount:ls[0].amount} : null;
    return '<div class="h-card h-6 h-hero'+ui().sjClass(sj.id)+'">'+
      '<div class="h-row"><span class="h-sj">'+ui().subjIcon(sj.id, 18)+esc(sj.name)+'</span>'+dueLine(a.dueAt, now)+'</div>'+
      '<span class="h-sub">'+esc(label)+'</span>'+
      '<div class="h-title">'+(pp ? esc(pp.name) : jp('この回の 宿題 ', 'この回の宿題 ')+ls.length+'件')+'</div>'+
      (pp ? (pp.amount ? '<div class="h-amount num">'+esc(pp.amount)+'</div>' : '') : linesHtml(a, 'hw-lines big'))+
      '<div class="h-way">'+ico(paper ? 'camera' : 'app', 18, 2)+
        (paper ? (photoOk(a) ? jp('紙に書いて 写真で出す', '紙に書いて写真で提出') : jp('紙に書いて 先生に出す', '紙に書いて先生に提出'))
               : jp('アプリで とく', 'アプリで解く'))+personalTag(a)+'</div>'+
      hwAction(a, true)+
      (paper && S().srv && upBusy !== a.id && photoOk(a)
        ? '<div class="h-hint">'+jp('ノートの 写真か PDF・10まいまで', 'ノートの写真かPDF・10枚まで')+'</div>' : '')+
    '</div>';
  }
  var dp = dailyPick(p);
  if(dp.next){
    var x = dp.next.x.subject;
    return '<div class="h-card h-6 h-hero'+ui().sjClass(x.id)+'">'+
      '<div class="h-row"><span class="h-sj">'+ui().subjIcon(x.id, 18)+esc(x.name)+'</span></div>'+
      '<span class="h-sub">'+esc(label)+'</span>'+
      '<div class="h-title">'+(st.rows.length ? jp('宿題は おわり。つぎは 毎日テスト', '宿題は完了。次は毎日テスト') : '毎日テスト')+'</div>'+
      '<div class="h-way">'+ico('app', 18, 2)+'<span class="num">'+dp.next.left+'</span>'+jp('もん', '問')+jp('・やく ', '・約')+roughMin(dp.next.left)+'分</div>'+
      '<button class="btn gold" data-start="'+esc(x.id)+'">'+jp('はじめる', '始める')+'</button>'+
    '</div>';
  }
  return '<div class="h-card h-6 h-hero">'+
    '<span class="h-sub">'+esc(label)+'</span>'+
    '<div class="h-title">'+jp('きょうの分は おわり', '今日の分は終わり')+'</div>'+
    '<div class="h-way">'+(dp.rows.length ? jp('宿題も 毎日テストも おわりました。', '宿題も毎日テストも終わりました。')
                                         : jp('いま出ている宿題は ありません。', '今出ている宿題はありません。'))+'</div>'+
    (dp.any ? '<button class="btn ghost" data-extra="'+esc(dp.any)+'">'+jp('もう少し やる', 'もう少しやる')+'</button>'
            : (dailyAny() ? '<button class="btn ghost" data-go="daily">毎日テストへ</button>' : ''))+
  '</div>';
}
/* 今週 ―― 今週の分の宿題を輪で。押すと宿題のタブへ。 */
function weekCard(p, st, now){
  var w = st.week, fin = weekFin(st), total = w.total, done = w.done;
  var foot = st.later.length ? (fin ? jp('つぎは 来週の分 ', '次は来週の分 ') : jp('来週の分 ', '来週の分 '))+st.later.length+'件'
           : (w.end ? dueDate(w.end)+jp(' まで', 'まで') : '');
  return '<button class="h-card h-3 h-ring" data-go="homework">'+
    hlbl('calendar', jp('今週', '今週'), 'blue')+
    '<span class="h-ringwrap">'+ringSvg(total ? done / total : 0, fin)+
      ringC(done, '/'+total)+'</span>'+
    '<span class="h-ringword'+(fin ? ' gold' : '')+'">'+
      (fin ? jp('今週 おわり', '今週おわり') : total ? jp('あと ', 'あと')+(total - done)+'件' : st.later.length ? jp('今週の分は ありません', '今週の分はありません') : jp('宿題は ありません', '宿題はありません'))+'</span>'+
    (foot ? '<span class="h-foot">'+esc(foot)+'</span>' : '')+
  '</button>';
}
/* 今週の目標 ―― 毎日テストを週に何日。札の上に小さな札が出て決める（S06）。 */
function goalCard(p, now){
  var C = global.TubeCheer, days = goalDays(p);
  var done = C.weekDays(p.hist || {}, now, TubeSRS.dayKey), hit = done >= days;
  var CR = 2 * Math.PI * 16;
  var pop = !pick.goalSheet ? '' :
    '<div class="h-pop" role="dialog" aria-label="'+esc(jp('今週の もくひょう', '今週の目標'))+'">'+
      '<div class="h-row"><div><div class="h-popt">'+jp('今週の もくひょう', '今週の目標')+'</div>'+
        '<div class="h-pops">'+jp('毎日テストを 週に 何日 やる？', '毎日テストを週に何日やる？')+'</div></div>'+
        '<button class="h-popx" data-goalshut="1" aria-label="'+esc(jp('とじる', '閉じる'))+'">'+ico('x', 18, 2.4)+'</button></div>'+
      '<div class="h-gopts">'+ [3, 5, 7].map(function(n){
        var on = n === days;
        return '<button class="h-gchoice'+(on ? ' on' : '')+'" data-goalpick="'+n+'" aria-pressed="'+on+'">'+
          '<svg viewBox="0 0 40 40" width="36" height="36" aria-hidden="true" style="transform:rotate(-90deg)"><circle cx="20" cy="20" r="16" fill="none" stroke="'+(on ? 'rgba(255,255,255,.3)' : 'rgba(60,60,67,.12)')+'" stroke-width="5"></circle>'+
          '<circle cx="20" cy="20" r="16" fill="none" stroke="'+(on ? '#fff' : '#0A6FC7')+'" stroke-width="5" stroke-linecap="round" stroke-dasharray="'+(CR*n/7).toFixed(1)+' '+CR.toFixed(1)+'"></circle></svg>'+
          '<span><b class="num">'+n+'</b>'+jp('日', '日')+'</span></button>';
      }).join('') +'</div>'+
      '<p class="h-popnote">'+jp('月曜から 日曜まで で 数えます。目標に とどいたら、札が 金色に なります', '月曜から日曜までで数えます。目標に届いたら、札が金色になります')+'</p>'+
    '</div>';
  return '<div class="h-card h-3 h-ring h-goal'+(hit ? ' hit' : '')+'">'+
    hlbl('target', jp('今週の もくひょう', '今週の目標'), 'blue')+
    '<span class="h-ringwrap">'+ringSvg(Math.min(1, done / days), hit)+
      ringC(done, '/'+days)+'</span>'+
    '<span class="h-ringword'+(hit ? ' gold' : '')+'">'+(hit ? jp('たっせい！', '達成！') : jp('あと ', 'あと')+(days - done)+jp('日', '日'))+'</span>'+
    '<button class="h-gbtn'+(pick.goalSheet ? ' on' : '')+'" data-goal="open" aria-expanded="'+(!!pick.goalSheet)+'"><span class="num">'+days+'</span>'+jp('日', '日')+ico('chev', 16, 2.4)+'</button>'+
    pop+
  '</div>';
}
/* 解いた問題数 ―― 毎日テストで解いた問題（直近7日・1日ごと）。％は出さない（2026-10-08）。 */
/* 続けた日 ―― 直近7日の棒（やりきった日は濃く）。押すと毎日テストへ。見本 S01 の「続けた日」。 */
function streakCard(p){
  var hist = p.hist || {}, st = streakOf(hist), bars = '', wd = '', WD = ['日','月','火','水','木','金','土'];
  for(var d = 6; d >= 0; d--){
    var t = Date.now() - d * TubeSRS.DAY, h = hist[TubeSRS.dayKey(t)];
    bars += '<i class="'+(!h ? '' : h.done ? 'on' : 'half')+'" style="height:'+(!h ? 14 : h.done ? 100 : 55)+'%"></i>';
    wd += '<span>'+WD[new Date(t).getDay()]+'</span>';
  }
  return '<button class="h-card h-3 h-streak" data-go="daily">'+
    hlbl('calendar', jp('つづけた 日', '続けた日'))+
    '<span class="h-big"><b class="num cu">'+st.run+'</b><span>'+jp('日 れんぞく', '日連続')+'</span></span>'+
    '<span class="h-bars c7">'+bars+'</span>'+
    '<span class="h-wd">'+wd+'</span>'+
    '<span class="h-foot left">'+jp('毎日テスト', '毎日テスト')+'</span>'+
  '</button>';
}

function solvedCard(p){
  var hist = p.hist || {}, vals = [], total = 0;
  for(var d = 6; d >= 0; d--){
    var h = hist[TubeSRS.dayKey(Date.now() - d * TubeSRS.DAY)], n = (h && h.n) || 0;
    vals.push(n); total += n;
  }
  var top = Math.max.apply(null, vals.concat([1]));
  return '<button class="h-card h-3 h-solved" data-go="daily">'+
    hlbl('check', jp('毎日テスト', '毎日テスト'))+
    '<span class="h-big"><b class="num cu">'+total+'</b><span>'+jp('もん といた', '問 解いた')+'</span></span>'+
    '<span class="h-bars c7">'+ vals.map(function(v, i){
      return '<i class="'+(i === 6 ? 'on' : '')+'" style="height:'+Math.max(6, Math.round(v / top * 100))+'%"></i>'; }).join('') +'</span>'+
    '<span class="h-foot left">'+jp('直近7日', '直近7日')+'</span>'+
  '</button>';
}

function bindGoal(m, p){
  m.querySelectorAll('[data-goal]').forEach(function(x){
    x.onclick = function(){ ui().keepInPlace(x); pick.goalSheet = !pick.goalSheet; ui().render(); };
  });
  m.querySelectorAll('[data-goalshut]').forEach(function(x){
    x.onclick = function(){ pick.goalSheet = false; ui().render(); };
  });
  m.querySelectorAll('[data-goalpick]').forEach(function(x){
    x.onclick = function(){
      var n = +x.dataset.goalpick;
      p.goal = {days:n, at:Date.now()};       /* 0 は「なし」。サーバはこれを消す合図として受ける */
      ui().persist();
      pick.goalSheet = false;
      ui().toast(n ? jp('今週の目標：毎日テストを '+n+'日', '今週の目標：毎日テストを'+n+'日') : jp('目標を なしに しました', '目標をなしにしました'));
      ui().render();
    };
  });
}

function viewToday(m){
  init();
  var s = S(), p = s.me.p;

  /* 先生からの返事を押したときは、その教科の中を見せる */
  if(pick.fbSubject) return viewFeedback(m, pick.fbSubject);

  var now = Date.now(), st = hwState(), html = '';

  if(!TubeStore.report().durable){
    html += '<button class="warnbar t-full" id="tDiag">'+
      jp('記録が消えることがある端末です。くわしく →','記録が消えることがある端末です。詳しく →')+'</button>';
  }

  /* 見本 S01：あいさつ（時間帯）＋日付の行、札は 2列（iPhone）／12列（iPad・PC）の格子 */
  var d = new Date(), WD = ['日','月','火','水','木','金','土'];
  html += '<div class="h-head t-full"><h1>'+esc(greeting())+'</h1>'+
    '<p class="h-date"><span class="num">'+(d.getMonth()+1)+'/'+d.getDate()+'</span>（'+WD[d.getDay()]+'）　'+jp('きょう やること', '今日やること')+'</p></div>';

  html += '<div class="h-grid t-full">'+
    gradCard() + placeAskCard() + noticeCards() +
    heroCard(p, st, now) + weekCard(p, st, now) + (dailyAny() ? goalCard(p, now) : '') +
    (paperNote() ? '<div class="h-note">'+paperNote()+'</div>' : '')+
    '<h2 class="h-h2">'+jp('じぶんの きろく', '自分の記録')+'</h2>'+
    growthTile() + stripTile(p, now) +
    (dailyAny() ? streakCard(p) + solvedCard(p) + volumeTile() : '')+
  '</div>';

  m.innerHTML = html + retSheet();
  bindNotices(m);
  bindPlaceAsk(m);
  var b;
  if((b = $('#tDiag'))) b.onclick = function(){ ui().go('settings', 'push'); };
  bindStarts(m);
  bindGoal(m, p);
  m.querySelectorAll('[data-fbsub]').forEach(function(x){
    x.onclick = function(){
      /* 開いた先は上から読む。**描く前に**上へ戻す ―― render() は同じ画面の
         スクロール位置を覚えて戻すので、描いたあとに戻しても元の位置に引き戻される。 */
      window.scrollTo(0, 0);
      pick.fbSubject = x.dataset.fbsub; ui().nav('push'); ui().render();
    };
  });
  /* 教科を押したら、宿題のタブのその教科へ（開いて、そこまで送る）。 */
  m.querySelectorAll('[data-hsub]').forEach(function(x){
    x.onclick = function(){ pick.hwFocus = x.dataset.hsub; ui().go('homework', 'push'); };
  });
}

/* ============================================================
   宿題のタブ
   ------------------------------------------------------------
   開いた瞬間に4つが分かること。
     1. どの教科の、何を（教材と範囲）
     2. どれから（まずこれから ―― 1件だけ大きく）
     3. どうやって（紙に書いて写真で提出／アプリで解く）
     4. あと どれだけ（いちばん上のまとめ）
   **一覧を長く見せない。** 教科ごとに3件まで出し、残りはたたむ。
   終わったものは、いちばん下にたたんでおく。
   ============================================================ */
var HW_CAP = 3;

/* ページの見出し（見本：34/700 の題と、その下に日付の行） */
function pageHead(title, sub){
  var d = new Date(), WD = ['日','月','火','水','木','金','土'];
  return '<div class="h-head t-full"><h1>'+esc(title)+'</h1>'+
    '<p class="h-date"><span class="num">'+(d.getMonth()+1)+'/'+d.getDate()+'</span>（'+WD[d.getDay()]+'）'+(sub ? '　'+esc(sub) : '')+'</p></div>';
}
/* 今週（宿題のタブ）―― 輪が左、ことばが右の横長の札 */
function weekWide(p, st, now){
  var w = st.week, fin = weekFin(st), total = w.total, done = w.done;
  var foot = st.later.length ? (fin ? jp('つぎは 来週の分 ', '次は来週の分 ') : jp('来週の分 ', '来週の分 '))+st.later.length+'件' : '';
  return '<div class="h-card h-6 h-weekwide">'+
    '<div class="h-row">'+hlbl('calendar', jp('今週', '今週'), 'blue')+
      (w.end ? '<span class="h-foot"><span class="num">'+dueDate(w.end)+'</span>'+jp(' まで', 'まで')+'</span>' : '')+'</div>'+
    '<div class="h-wwrow">'+
      '<span class="h-ringwrap small">'+ringSvg(total ? done / total : 0, fin)+
        ringC(done, '/'+total)+'</span>'+
      '<div class="h-wwtx">'+
        '<span class="h-wwbig'+(fin ? ' gold' : '')+'">'+(fin ? ico('check', 24, 2.2)+jp('今週 おわり', '今週おわり') : total ? jp('あと ', 'あと')+(total - done)+'件' : st.later.length ? jp('今週の分は ありません', '今週の分はありません') : jp('宿題は ありません', '宿題はありません'))+'</span>'+
        (foot ? '<span class="h-wwfoot">'+esc(foot)+'</span>' : '')+
      '</div>'+
    '</div>'+
  '</div>';
}

function viewHomework(m){
  init();
  var p = S().me.p, now = Date.now(), st = hwState();
  var d = new Date(), WD = ['日','月','火','水','木','金','土'];

  /* ホームの「教科ごと」から来たら、その教科を開いて そこまで送る。
     残りが無い教科なら、終わった宿題を開く。 */
  var focus = pick.hwFocus;
  pick.hwFocus = null;
  if(focus){
    if(st.left.some(function(r){ return r.sub.id === focus; })){
      pick.hwOpen['this:' + focus] = pick.hwOpen['next:' + focus] = true;
    }
    else { pick.hwFinOpen = true; focus = 'fin'; }
  }

  var html = pageHead(jp('ていしゅつ', '提出'), '');

  /* 上：テストの提出（漢字・計算・英語テストの提出箱）。下：いつもの宿題（2026-10-11 本人）。
     過去問は、過去問のタブがある生徒ではそちらに。 */
  var tests = st.rows.filter(function(r){ return isTest(r.a); });
  var usual = function(rows){ return rows.filter(function(r){ return !isTest(r.a) && !(kakomonOn() && isKakomon(r.a)); }); };
  html += testsSection(p, st, tests, now);

  if(!st.rows.length && !hwLoaded){
    html += '<div class="hw-empty t-full"><div class="hw-empty-t">'+
      jp('宿題を よみこんでいます…', '宿題を読み込んでいます…')+'</div></div>';
  }else if(!st.rows.length){
    /* 何も出ていない日。空を「壊れている」と読ませない。次に行ける所を1つ置く。 */
    html += '<div class="hw-empty t-full">'+
      '<div class="hw-empty-t">'+jp('いま出ている宿題は ありません', '今出ている宿題はありません')+'</div>'+
      (dailyAny()
        ? '<p>'+jp('新しく出されたら、ここに ならびます。そのあいだに 毎日テストで 力を のばそう。',
                   '新しく出されたら、ここに並びます。その間に毎日テストで力を伸ばそう。')+'</p>'+
          '<button class="btn small" data-go="daily">毎日テストへ</button>'
        : '<p>'+jp('新しく出されたら、ここに ならびます。', '新しく出されたら、ここに並びます。')+'</p>')+
    '</div>';
  }else{
    /* 上の段は**ホームとまったく同じ札**（同じ関数・同じ大きさ）。
       前は似て非なる札（.hw-first）を置いていて、ホームから来た人に「移った」と伝わらなかった
       （本人の指摘）。同じ札にし、画面の移り変わりは動き（右から入る）で伝える。 */
    html += '<div class="h-grid t-full">'+ heroCard(p, st, now) + weekWide(p, st, now) +
      (paperNote() ? '<div class="h-note">'+paperNote()+'</div>' : '') +'</div>';
    /* 今週の分 → 来週の分。見出しの境目が「ここまでで今週おわり」。
       今週の分が残っているあいだ、来週の分は控えめ（.later）。今週が済めば来週が主役に戻る。 */
    var thisG = homeworkBySubject(usual(st.week.left)), nextG = homeworkBySubject(usual(st.later));
    if(thisG.length){
      html += '<div class="h-sect t-full"><h2>今週</h2><span class="num">'+dueDate(st.week.end)+jp(' まで', 'まで')+'</span></div>'+
        '<div class="hw-secs t-full">'+ thisG.map(function(g){
          return hwSection(p, g, st, now, 'this');
        }).join('') +'</div>';
    }
    if(nextG.length){
      html += '<div class="h-sect t-full"><h2>来週</h2><span class="num">'+dueDate(st.week.end + 1)+jp(' から', 'から')+'</span></div>'+
        '<div class="hw-secs t-full'+(thisG.length ? ' later' : '')+'">'+ nextG.map(function(g){
          return hwSection(p, g, st, now, 'next');
        }).join('') +'</div>';
    }
    html += hwFinished(p, st);
  }

  html += retSheet();
  m.innerHTML = html;
  bindStarts(m);
  m.querySelectorAll('[data-hmore]').forEach(function(x){
    x.onclick = function(){
      var k = x.dataset.hmore;
      ui().keepInPlace(x.closest('[data-hs]'));
      pick.hwOpen[k] = !pick.hwOpen[k];
      ui().render();
    };
  });
  m.querySelectorAll('[data-hfin]').forEach(function(x){
    x.onclick = function(){
      ui().keepInPlace(x.closest('[data-hs]'));
      pick.hwFinOpen = !pick.hwFinOpen;
      ui().render();
    };
  });
  if(focus){
    var el = m.querySelector('[data-hs="'+focus+'"]');
    if(el){
      el.classList.add('focus');
      requestAnimationFrame(function(){
        window.scrollTo(0, Math.max(0, el.getBoundingClientRect().top + window.scrollY - 16));
      });
    }
  }
}


/* テストの提出 ―― 漢字・計算・英語テストの提出箱を、宿題とは別に上にまとめる。
   出していないものは出す口つき、出したものは状態（確認待ち・先生が見た・添削）を最近の3件まで。 */
function testsSection(p, st, tests, now){
  var open = tests.filter(function(r){ return !r.done; });
  var done = tests.filter(function(r){ return r.done; }).slice(0, 3);
  var body;
  if(!open.length && !done.length){
    body = '<div class="hw-row hw-row-empty">'+jp('いま 出ている テストは ありません', '今出ているテストはありません')+'</div>';
  }else{
    body = open.map(function(r){ return quizCard(p, r.a, now, r.a === st.first); }).join('')+
           done.map(function(r){ return finRow(p, r.a); }).join('');
  }
  return '<div class="h-sect t-full"><h2>'+jp('テストの ていしゅつ', 'テストの提出')+'</h2>'+
      (open.length ? '<span class="num">'+jp('あと ', 'あと')+open.length+'件</span>' : '')+'</div>'+
    '<div class="hw-secs t-full hw-tests">'+body+'</div>';
}
/* 提出箱1件の札（テスト・過去問）：種類の札、題、期限、出す口。同じ回の束は無い（提出箱は1件）。 */
function quizCard(p, a, now, isFirst){
  var sj = subjectOfHw(a);
  /* 見出しが種類なので、題からは種類を外す（「過去問 2025 都立共通 数学」→「2025 都立共通 数学」）。出す口は同じ ID。 */
  var title = String(a.title || '');
  if(a.kind && title.indexOf(a.kind) === 0) title = title.slice(a.kind.length).trim() || title;
  /* 行は hwRow と同じ2段だが、題は hwRow（束の題を ID から引く）を通さず、ここで組む。 */
  var row = '<div class="hw-row">'+oneLine(title, '')+
    '<div class="hw-row2"><div class="hw-meta">'+dueTag(a.dueAt, now)+wayBadge(true, true, photoOk(a))+'</div>'+
    '<div class="hw-act">'+(isFirst ? '<span class="hw-state">'+jp('上の カードから', '上のカードから')+'</span>' : hwAction(a, false))+'</div></div>'+
  '</div>';
  return '<section class="hw-sec hw-quiz'+ui().sjClass(sj.id)+'" data-hs="quiz:'+esc(a.id)+'">'+
    '<div class="hw-sechead"><span class="hw-secic">'+ui().subjIcon(sj.id, 20)+'</span><h3>'+esc(a.kind || jp('ていしゅつばこ', '提出箱'))+'</h3>'+
      '<span class="hw-secn">'+esc(sj.name)+'</span></div>'+
    row+
  '</section>';
}
/* 過去問（中3・小6）―― これから取り組む過去問と、出した過去問。ここから出す・添削を見る。
   過去問は講師が「提出箱（種類：過去問）」で出す。全員にも、選んだ生徒だけにも出せる。 */
/* 過去問の題から 年度・学校・教科 を読む（「過去問 2025 早稲田実業 数学」）。読めなければ題そのものを学校の名に。 */
function kkParse(a){
  var s = String(a.title || '');
  if(a.kind && s.indexOf(a.kind) === 0) s = s.slice(a.kind.length).trim() || s;
  var m = /^(\d{4})\s*(?:年度|年)?\s*(.*?)\s*(国語|算数|数学|理科|社会|英語)?$/.exec(s);
  if(!m) return {year:'', school:s, subject:''};
  return {year:m[1], school:(m[2] || '').trim() || s, subject:m[3] || ''};
}
/* 点数（出した過去問にだけ）。空欄で消す。書いたら その場で保存（確認ボタンは置かない） */
function kkScore(a){
  var got = (subs || {})[a.id] || {};
  var sc = (got.score === 0 || got.score) ? got.score : '', mx = got.max || '';
  return '<label class="kk-score'+(sc === '' ? '' : ' has')+'"><span class="kk-sl">'+jp('てんすう', '点数')+'</span>'+
    '<input type="number" inputmode="numeric" min="0" max="999" placeholder="—" value="'+esc(sc)+'" data-kkscore="'+esc(a.id)+'" aria-label="'+jp('てんすう', '点数')+'">'+
    '<i>/</i><input type="number" inputmode="numeric" min="1" max="999" placeholder="'+jp('まんてん', '満点')+'" value="'+esc(mx)+'" data-kkmax="'+esc(a.id)+'" aria-label="'+jp('まんてん', '満点')+'"></label>';
}
function viewKakomon(m){
  init();
  var p = S().me.p, now = Date.now(), st = hwState();
  var rows = st.rows.filter(function(r){ return isKakomon(r.a); });
  var todo = rows.filter(function(r){ return !r.done; }), done = rows.filter(function(r){ return r.done; });
  var html = pageHead('過去問', '');
  if(!rows.length){
    html += '<div class="hw-empty t-full"><div class="hw-empty-t">過去問はまだ出ていません</div>'+
      '<p>先生が出すと、ここに学校ごとの一覧が並びます。</p></div>';
  }else{
    /* 学校ごとに1枚。中は年度の新しい順。これからのものは期限と出す口、出したものは日・評価・点数（10-11 本人：
       「各学校ごとに何年をやってきたかがリスト化すると良い。点数の記録などもできると良い」）。 */
    var by = {}, order = [];
    rows.forEach(function(r){ var k = kkParse(r.a); r.k = k; if(!by[k.school]){ by[k.school] = []; order.push(k.school); } by[k.school].push(r); });
    var soon = function(name){ var ts = by[name].filter(function(r){ return !r.done; }).map(function(r){ return r.a.dueAt || 9e15; }); return ts.length ? Math.min.apply(null, ts) : 9e15; };
    order.sort(function(a, b){ return soon(a) - soon(b) || a.localeCompare(b, 'ja'); });
    html += '<div class="h-sect t-full"><h2>学校ごと</h2><span class="num">やった '+done.length+'本・これから '+todo.length+'本</span></div>'+
      '<div class="kk-schools t-full kk-list">'+ order.map(function(name){
        var list = by[name].slice().sort(function(x, y){ return (y.k.year || '').localeCompare(x.k.year || '') || (x.a.dueAt || 0) - (y.a.dueAt || 0); });
        var dn = list.filter(function(r){ return r.done; }).length;
        return '<section class="h-card kk-school">'+
          '<div class="kk-shead"><h3>'+esc(name)+'</h3><span class="kk-scnt num">'+dn+' / '+list.length+'本</span></div>'+
          list.map(function(r){
            var a = r.a, sj = subjectOfHw(a), v = (a.rated && a.rated.v >= 1) ? a.rated.v : 0;
            var got = (subs || {})[a.id];
            return '<div class="kk-row'+(r.done ? ' done' : ' todo')+ui().sjClass(sj.id)+'" data-kk="'+esc(a.id)+'">'+
              '<span class="kk-year num">'+esc(r.k.year || '—')+'</span>'+
              '<span class="kk-sj"><span class="h-sj">'+ui().subjIcon(sj.id, 16)+esc(r.k.subject || sj.name)+'</span></span>'+
              (r.done
                ? '<span class="kk-state">'+(got ? '<span class="kk-day num">'+esc(ui().fmtDate(got.at * 1000))+'</span>' : '')+rateChip(v, !!(a.rated && a.rated.provisional))+
                    (got && got.returned && (got.returned.files || []).length ? '<button class="lnk kk-ret" data-ret="'+esc(a.id)+'">添削を見る</button>' : '')+'</span>'+
                  kkScore(a)
                : '<span class="kk-state">'+dueTag(a.dueAt, now)+'</span><span class="kk-act">'+hwAction(a, false)+'</span>')+
            '</div>';
          }).join('')+
        '</section>';
      }).join('') +'</div>';
    html += '<p class="kk-how t-full">解いた答案を写真で出すと、先生が採点して、赤を入れた答案とひとことが「先生から」とここに返ってきます。点数は自分で書けます。</p>';
  }
  html += retSheet();
  m.innerHTML = html;
  bindStarts(m);
  m.querySelectorAll('[data-kkscore], [data-kkmax]').forEach(function(inp){
    inp.onchange = async function(){
      var aid = inp.dataset.kkscore || inp.dataset.kkmax, row = inp.closest('.kk-row');
      var sc = row.querySelector('[data-kkscore]').value, mx = row.querySelector('[data-kkmax]').value;
      var r = await S().srv.subScore(aid, sc === '' ? null : sc, mx === '' ? null : mx);
      if(!r.ok) return ui().toast(r.error);
      subs = subs || {}; subs[aid] = r.item; TubeHomework.setSubs(subs);
      ui().toast(sc === '' ? jp('てんすうを けしました', '点数を消しました') : jp('てんすうを ほぞんしました', '点数を保存しました'));
      ui().keepInPlace(row); ui().render();
    };
  });
}

/* まとめ ―― 今週の宿題の札（ホームと同じ中身）。宿題のタブでは押す先が無いので div。 */
function hwSummary(p, st, now){
  return '<div class="w hw-wk wfill'+(weekFin(st) ? ' fin' : '')+'">'+ weekBody(p, st, now, false) +'</div>';
}


/* 教科ひとつ ―― 教科名・あと何件。行は近い順に3件まで。
   wk … 'this'（今週の分）か 'next'（来週の分）。同じ教科が2つの週に出るので、開け閉めは週ごと。
   期限は見出しに書かない ―― 行ごとに同じ札（dueTag）があり、1件の教科では2度書くことになる。 */
function hwSection(p, g, st, now, wk){
  var id = g.sub.id, key = wk + ':' + id;
  var mine = g.rows.map(function(r){ return r.a; });
  var list = st.queue.filter(function(a){ return mine.indexOf(a) >= 0; });
  var open = !!pick.hwOpen[key];
  var show = open ? list : list.slice(0, HW_CAP);
  var plain = (st.plain || []).filter(function(a){
    return subjectOfHw(a).id === id && weekOf(a, false, now) === wk;
  });
  return '<section class="hw-sec'+ui().sjClass(id)+'" data-hs="'+esc(id)+'">'+
    '<div class="hw-sechead"><span class="hw-secic">'+ui().subjIcon(id, 20)+'</span><h3>'+esc(g.sub.name)+'</h3>'+
      '<span class="hw-secn">'+jp('あと', 'あと')+'<b class="num">'+list.length+'</b>件</span></div>'+
    show.map(function(a){ return hwRow(p, a, now, a === st.first); }).join('')+
    (list.length > HW_CAP
      ? '<button class="lnk hit hw-more" data-hmore="'+esc(key)+'">'+(open
          ? jp('たたむ', 'たたむ')
          : jp('ほか ', 'ほか')+(list.length - HW_CAP)+jp('件を 見る', '件を見る'))+'</button>'
      : '')+
    plainHtml(plain, now)+
  '</section>';
}

/* 宿題1件 ―― 何を（題名と分量）／いつまで・どうやって ＋ 押すもの1つ。
   2段に組む：上の段に題名、下の段に期限の札と押すもの。札の幅がどれだけ狭くても同じ形。 */
function hwRow(p, a, now, isFirst){
  var paper = a.route === 'paper';
  return '<div class="hw-row">'+
    (paper ? linesHtml(a) : oneLine(a.title, appAmount(p, a, false)))+
    '<div class="hw-row2"><div class="hw-meta">'+dueTag(a.dueAt, now)+wayBadge(paper, true, paper ? photoOk(a) : undefined)+personalTag(a)+'</div>'+
    /* 上の「まずこれから」と同じ1件は、ここでは押させない（同じボタンを2つ並べない）。 */
    '<div class="hw-act">'+(isFirst ? '<span class="hw-state">'+jp('上の カードから', '上のカードから')+'</span>'
                                     : hwAction(a, false))+'</div></div>'+
  '</div>';
}

/* おわった宿題 ―― たたんで置く。開くと状態（出した・先生が見た）と、
   出しなおす口・先生のひとこと・戻ってきた復習の「たしかめる」がある。 */
function hwFinished(p, st){
  var fin = st.rows.filter(function(r){ return r.done; });
  if(!fin.length) return '';
  var open = pick.hwFinOpen;
  return '<div class="hw-fin t-full" data-hs="fin">'+
    '<button class="hw-fintg" data-hfin="1" aria-expanded="'+(open ? 'true' : 'false')+'">'+
      '<span>'+jp('おわった宿題 ', '終わった宿題 ')+'<b class="num">'+fin.length+'</b>件</span>'+
      '<i class="h-arr'+(open ? ' open' : '')+'">'+ico('chev', 14, 2.4)+'</i></button>'+
    (open ? '<div class="hw-finrows">'+ fin.map(function(r){ return finRow(p, r.a); }).join('') +'</div>' : '')+
  '</div>';
}

function finRow(p, a){
  var paper = a.route === 'paper', sb = paper ? (subs || {})[a.id] : null;
  var again = !paper && TubeHomework.due(p, a).length > 0;   /* 間隔があいて戻ってきた番号 */
  var v = (a.rated && a.rated.v >= 1) ? a.rated.v : 0;
  var day = hwDay(a);
  /* 教科の中の行（hwRow）と同じ2段。出したあとの状態（submitRow）は下に行ぜんぶで。 */
  var sj = subjectOfHw(a);
  return '<div class="hw-row done'+ui().sjClass(sj.id)+'">'+
    '<div class="h-row"><span class="h-sj">'+ui().subjIcon(sj.id, 18)+esc(sj.name)+'</span>'+(day ? '<span class="h-foot">'+esc(day)+'</span>' : '')+'</div>'+
    (paper ? linesHtml(a) : oneLine(a.title, ''))+
    '<div class="hw-meta">'+wayBadge(paper, true)+
      (sb ? '' : '<span class="hw-st">'+esc(doneState(a))+'</span>')+
      rateChip(v, !!(a.rated && a.rated.provisional))+
    '</div>'+
    (again ? '<div class="hw-act"><button class="btn small ghost hw-go" data-hw="'+esc(a.id)+'">'+
               jp('たしかめる', '確認する')+'</button></div>' : '')+
    (sb ? '<div class="hw-sub">'+submitRow(a)+'</div>' : '')+
  '</div>';
}

/* 先生が返した添削の紙（写真・PDF）。宿題のタブと「先生から」の両方から開く。 */
function retSheet(){
  var aid = pick.retSheet; if(!aid) return '';
  loadSubs();
  var got = (subs || {})[aid], a = TubeHomework.byId(aid);
  var files = (got && got.returned && got.returned.files) || [];
  if(!files.length) return '';
  var i = Math.max(0, Math.min(pick.retPage || 0, files.length - 1)), f = files[i];
  var tok = (S().srv && S().srv.token) ? S().srv.token() : '';
  var src = '/api/submissions/'+encodeURIComponent(aid)+'/'+encodeURIComponent(S().me.stu.sid)+'/'+encodeURIComponent(f.name)+'?t='+encodeURIComponent(tok);
  return '<div class="shade" data-retshut="1"></div>'+
    '<div class="sheet wide ret-sheet" role="dialog" aria-modal="true" data-sk="ret|'+esc(aid)+'">'+
      '<div class="sh-top"><div><div class="sh-n">'+jp('先生が 直してくれた 答案', '添削された答案')+'</div>'+
        '<div class="sh-s">'+esc(a ? a.title : '')+(got.note ? '　'+esc(got.note) : '')+'</div></div>'+
        '<button class="sh-x" data-retshut="1" aria-label="'+jp('とじる','閉じる')+'">&times;</button></div>'+
      '<div class="sh-body ret-body">'+
        (f.kind === 'pdf'
          ? '<a class="btn small" href="'+esc(src)+'" target="_blank" rel="noopener">PDF を開く</a>'
          : '<img class="ret-img" alt="'+jp('直してくれた 答案', '添削された答案')+' '+(i+1)+'" src="'+esc(src)+'">')+
        (files.length > 1 ? '<div class="ret-nav"><button class="btn small ghost" data-retpage="-1"'+(i <= 0 ? ' disabled' : '')+'>‹ '+jp('まえ', '前')+'</button>'+
            '<span class="num">'+(i+1)+' / '+files.length+'</span>'+
            '<button class="btn small ghost" data-retpage="1"'+(i >= files.length - 1 ? ' disabled' : '')+'>'+jp('つぎ', '次')+' ›</button></div>' : '')+
      '</div></div>';
}

/* 先生から ―― ある教科で返ってきたものを、新しい順に全部（タブ「先生から」の教科の行を押した先）。
   1件 ＝ いつの宿題か・評価・（あれば）先生のことば。ことばは引用の形で大きく、評価だけの回は1行。
   「写真は確認済み」のような、生徒にとって意味の無い状態は書かない。
   見出しと一覧はどれも t-full ―― 前は柱に入れておらず、広い画面で戻る・教科名・一覧が3列に散った。 */
function viewFeedback(m, subId){
  var s = S(), p = s.me.p, jp = ui().jp;
  var sub = TubeContent.subject(subId) || {name:subId};
  var rows = returnedItems(p).filter(function(x){ return x.sub.id === subId; });
  ui().subject(subId);
  var first = rows.filter(function(x){ return x.note || (x.s && x.s.returned && (x.s.returned.files || []).length); })[0] || null;
  var rest = rows.filter(function(x){ return x !== first; });
  var files = (first && first.s && first.s.returned && first.s.returned.files) || [];
  m.innerHTML =
    '<div class="fb-back t-full"><button class="backpill" id="fBack">'+ui().backIcon+jp('先生から', '先生から')+'</button></div>'+
    '<div class="h-head fb-head t-full'+ui().sjClass(subId)+'"><h1 class="fb-h1">'+ui().subjIcon(subId, 34, 2.2)+esc(sub.name)+'</h1>'+
      '<span class="h-date">'+jp('先生からの へんじ ', '先生からの返事 ')+'<b class="num">'+rows.length+'</b>件</span></div>'+
    '<div class="h-grid t-full">'+
    (first
      ? '<div class="h-card h-full fb-first">'+
          '<div class="ch-intop"><span class="ch-day">'+esc(hwDay(first.a))+'</span>'+rateChip(first.v, first.prov)+
            (first.v === null && first.s && !first.s.seen ? '<span class="fb-wait">'+esc(jp('まだ 見てもらっていません', '確認待ち'))+'</span>' : '')+'</div>'+
          (first.note ? '<blockquote class="ch-quote big">'+esc(first.note)+'</blockquote>' : '')+
          '<span class="ch-title">'+esc(first.a.title)+'</span>'+
          (files.length ? '<button class="btn up-ret" data-ret="'+esc(first.a.id)+'">'+jp('先生の 赤を 見る', '添削された答案を見る')+'<span class="nobr">（<span class="num">'+files.length+'</span>'+jp('まい', '枚')+'）</span></button>' : '')+
        '</div>'
      : (rows.length ? '' : '<div class="h-card h-full"><p class="fb-empty">'+esc(jp('まだ ありません。', 'まだありません。'))+'</p></div>'))+
    (rest.length ? '<div class="fb-list h-full">'+ rest.map(function(x){
        var f2 = (x.s && x.s.returned && x.s.returned.files) || [];
        return '<div class="h-card fb-row">'+
          '<div class="fb-rowtx"><span class="ch-day">'+esc(hwDay(x.a))+'</span><span class="ch-title">'+esc(x.a.title)+'</span>'+
            (x.note ? '<span class="fb-note">'+esc(x.note)+'</span>' : '')+'</div>'+
          (x.v !== null && x.v > 0 ? rateChip(x.v, x.prov) : (x.s && !x.s.seen ? '<span class="fb-wait">'+esc(jp('かくにん まち', '確認待ち'))+'</span>' : ''))+
          (f2.length ? '<button class="h-arr up-ret" data-ret="'+esc(x.a.id)+'" aria-label="'+jp('答案を 見る', '答案を見る')+'">'+ico('chev', 14, 2.4)+'</button>' : '')+
        '</div>';
      }).join('') +'</div>' : '')+
    '</div>'+ retSheet();
  $('#fBack').onclick = function(){ pick.fbSubject = null; ui().nav('pop'); ui().render(); };
  bindUpload(m);
}

/* 写真を選んだら、そのまま送る。**「送る」ボタンを別に置かない** ――
   選んでから押すまでの1手で、出し忘れが起きる。 */
function bindUpload(m){
  m.querySelectorAll('[data-upsend]').forEach(function(b){ b.onclick = function(){ submitHw(b.dataset.upsend, null); }; });
  m.querySelectorAll('[data-upcancel]').forEach(function(b){ b.onclick = function(){ delete pending[b.dataset.upcancel]; ui().render(); }; });
  m.querySelectorAll('[data-uprm]').forEach(function(b){
    b.onclick = function(){
      var p = b.dataset.uprm.split('|'), list = pending[p[0]] || [];
      list.splice(+p[1], 1);
      if(!list.length) delete pending[p[0]];
      ui().render();
    };
  });
  m.querySelectorAll('[data-ret]').forEach(function(b){ b.onclick = function(){ pick.retSheet = b.dataset.ret; pick.retPage = 0; ui().render(); }; });
  m.querySelectorAll('[data-retshut]').forEach(function(b){ b.onclick = function(){ pick.retSheet = null; ui().render(); }; });
  m.querySelectorAll('[data-retpage]').forEach(function(b){ b.onclick = function(){ pick.retPage = Math.max(0, (pick.retPage || 0) + (+b.dataset.retpage)); ui().render(); }; });
  m.querySelectorAll('[data-up]').forEach(function(x){
    x.onchange = function(){
      /* **先に配列へ写してから空にする。** x.files をそのまま持っておくと、
         value を空にした時点で同じ一覧が空になる端末がある（Chromium で実測）。
         そうなると写真を選んでも何も送られず、「提出する」が押せないボタンになる。 */
      var list = Array.prototype.slice.call(x.files || []);
      x.value = '';                       // 同じ写真をもう一度選べるように
      submitHw(x.dataset.up, list);
    };
  });
}

/* ============================================================
   毎日テスト ―― 別のタブ。任意である。

   宿題と同じ画面に置くと、「どれが必ずやるものか」が分からなくなる。
   タブを分けることで、来た人はもう「やる気で来ている」ことになる。
   だからこの画面は、迷わせずに始められることだけを考える。
   ============================================================ */
/* その帯の名前を生徒に見せてよいか。

   仮置きの教材（いまは英語）は帯が CEFR で、学年とは別のものである。
   小5の画面に「A2」と出しても意味を持たないので、出さない。
   目録の provisional が付いている教材の帯は、すべてこれに当たる。 */
function readableBand(x, band){
  if(!band) return '';
  var packs = (x.plan && x.plan.packs) || [];
  var prov = TubeContent.packList(x.subject.id).filter(function(pk){
    return pk.provisional && packs.indexOf(pk.id) >= 0; });
  return prov.length ? '' : band;
}

/* ============================================================
   カメラで丸つけ
   ============================================================
   刷った解答らんを撮ると、その場で採点する。

   **写真は端末の外に出さない。** サーバへ送らないし、保存もしない。
   読み終わったら捨てる。送らなければ、漏れることもない。

   読めなかったときは、読めなかったと言う。当てずっぽうで丸を
   付けない ―― まちがった採点は、採点しないより悪い。
   ============================================================ */
var cam = null;      /* {stream, items, geom, subject, result} */
var camPick = false; /* 教科を選ばせている最中か */

function camClose(){
  if(cam && cam.stream){
    cam.stream.getTracks().forEach(function(t){ t.stop(); });
  }
  cam = null;
}

async function camOpen(subjectId){
  var s = S();
  if(!prepFull) prepFull = await s.srv.prepAll();
  if(!prepFull) return toast(jp('いま 対策は ありません','今は対策がありません'));
  var set = (prepFull.sets || []).filter(function(x){
    return x.subject === subjectId; })[0];
  if(!set || !(set.items || []).length) return toast(jp('この教科の問題は ありません','この教科の問題はありません'));
  /* **紙に刷った並びをサーバからもらう。**
     画面でもう一度絞ると、絞り方がずれた日に採点が総崩れになる。 */
  var order = (prepFull.paper || {})[subjectId] || null;
  var byId = {};
  set.items.forEach(function(x){ byId[x.id] = x; });
  var items = order ? order.map(function(id){ return byId[id]; }).filter(Boolean)
                    : set.items.filter(function(x){ return (x.dis||[]).length; });
  if(!items.length) return toast(jp('この教科は 紙で採点できる問題がありません','この教科には紙で採点できる問題がありません'));
  cam = {items:items, geom:prepFull.sheet || prepSheetGeom,
         subject:subjectId, result:null, stream:null, busy:false};
  ui().render();
  /* カメラを開く。断られたら、写真を選ぶほうへ落とす。 */
  try{
    cam.stream = await navigator.mediaDevices.getUserMedia(
      {video:{facingMode:{ideal:'environment'},
              width:{ideal:1920}, height:{ideal:1440}}});
    var v = document.getElementById('camV');
    if(v){ v.srcObject = cam.stream; await v.play(); }
  }catch(e){
    cam.noCam = true;
    ui().render();
  }
}

/* 寸法の控え。サーバから来なかったときだけ使う。
   **ふだんはサーバの値を使う** ―― 刷る側と同じ数字でなければ、
   1マスもかみ合わない。 */
var prepSheetGeom = {cols:4, rows:15, opts:4,
  gridX0:0.045, gridY0:0.215, gridW:0.91, gridH:0.72,
  bubX0:0.34, bubDX:0.205, bubR:0.062, markMM:8.0, marginMM:12.0,
  pageMM:[210, 297]};

function camGrade(img){
  if(!cam) return;
  var got = TubeOMR.read(img, cam.geom, cam.items.length);
  if(!got.ok){ cam.why = got.why; cam.result = null; ui().render(); return; }
  /* 答え合わせ。答えはアプリが持っている（サーバから来ている）。 */
  var rows = cam.items.map(function(it, i){
    var opts = camOptions(it);
    var pick = got.answers[i];
    var chosen = (pick >= 0 && pick < opts.length) ? opts[pick] : null;
    return {i:i, item:it, pick:pick, chosen:chosen,
            right: chosen !== null && chosen === it.ans,
            blank: chosen === null};
  });
  cam.result = {rows:rows,
    ok: rows.filter(function(r){ return r.right; }).length,
    blank: rows.filter(function(r){ return r.blank; }).length};
  cam.why = null;
  /* **読み終わったら写真を捨てる。** 持っておく理由がない。 */
  camClose2();

  /* 結果だけをサーバへ送る。**写真は送らない。**
     サーバは単元ごとの落とし数を数え、本番までの数日で
     「どこをやり直すか」を返せるようになる。 */
  var s = S();
  if(s.srv && s.srv.prepResult){
    s.srv.prepResult(cam.subject, rows.map(function(r){
      return {id:r.item.id, right:r.right, blank:r.blank};
    })).then(function(){
      prep = undefined; prepFull = null;   // 苦手を取り直す
      loadPrep();
    });
  }
  ui().render();
}

/* 読み取りが済んだら、カメラだけ止める（結果は残す）。 */
function camClose2(){
  if(cam && cam.stream){
    cam.stream.getTracks().forEach(function(t){ t.stop(); });
    cam.stream = null;
  }
}

/* 紙に刷った選択肢の並び。**刷る側と同じ順**にする。
   server/prepsheet.py の _choices と同じ式。ずれると採点が総崩れになる。 */
function camOptions(it){
  var dis = (it.dis || []).filter(Boolean);
  if(!dis.length) return [];
  var opts = [it.ans].concat(dis);
  var key = String(it.id || it.q || '');
  var k = 0;
  for(var i = 0; i < key.length; i++) k += key.charCodeAt(i);
  k = k % opts.length;
  return opts.slice(k).concat(opts.slice(0, k));
}

/* どの教科を丸つけするか。2教科以上あるときだけ出す。 */
function camPickSheet(){
  if(!camPick || !prep) return '';
  return '<div class="shade" data-camshut="1"></div>'+
    '<div class="sheet" role="dialog" aria-modal="true">'+
      '<div class="sh-top"><div><div class="sh-n">'+jp('どの教科を 丸つけする？','どの教科を丸つけしますか？')+'</div>'+
        '<div class="sh-s">'+jp('刷った解答らんの教科を えらんでください','印刷した解答欄の教科を選んでください')+'</div></div>'+
        '<button class="sh-x" data-camshut="1" aria-label="'+jp('とじる','閉じる')+'">&times;</button>'+
      '</div>'+
      '<div class="sh-body">'+ (prep.sets || []).slice().sort(function(a, b){
        /* 直前に刷った教科を先頭に上げる。目で探す手間をなくす。 */
        var k = (lastSheet || {}).subject;
        return (b.subject === k ? 1 : 0) - (a.subject === k ? 1 : 0);
      }).map(function(x){
        var mine = lastSheet && lastSheet.subject === x.subject;
        return '<button class="shrow'+(mine ? ' on' : '')+'" '+
            'data-campick="'+esc(x.subject)+'">'+
          '<span class="sht">'+esc(subjName(x.subject))+
            (mine ? '<i class="tag">'+jp('さっき刷った紙','先ほど印刷した紙')+'</i>' : '')+'</span>'+
          '<span class="shn num">'+x.n+'<i>問</i></span>'+
        '</button>'; }).join('') +'</div>'+
    '</div>';
}

/* カメラの紙。撮る前・撮ったあと・読めなかったとき の3つ。 */
function camSheet(){
  if(!cam) return '';
  var head = function(t2, s2){
    return '<div class="sh-top"><div><div class="sh-n">'+esc(t2)+'</div>'+
      '<div class="sh-s">'+esc(s2||'')+'</div></div>'+
      '<button class="sh-x" data-camshut="1" aria-label="'+jp('とじる','閉じる')+'">&times;</button>'+
    '</div>'; };

  /* ---- 結果 ---- */
  if(cam.result){
    var r = cam.result;
    /* **読めなかった分と、まちがえた分を分ける。**
       塗り忘れを「まちがい」に混ぜると、解説を読む意味がない。 */
    var wrong = r.rows.filter(function(x){ return !x.right && !x.blank; });
    return '<div class="shade" data-camshut="1"></div>'+
      '<div class="sheet wide" role="dialog" aria-modal="true">'+
        head(jp('丸つけ できました','丸つけが終わりました'),
             r.ok+' / '+r.rows.length+jp('問 せいかい','問正解')+
             (r.blank ? '　（'+r.blank+jp('問は 塗られていませんでした）','問は塗られていませんでした）') : ''))+
        '<div class="sh-body">'+
          '<div class="qmarks">'+ r.rows.map(function(x){
            return '<button class="mkq '+(x.blank ? 'bl' : x.right ? 'ok' : 'ng')+
              '" data-camq="'+x.i+'">'+
              '<span class="mno">'+(x.i+1)+'</span>'+
              '<span class="msign">'+(x.blank ? '?' : x.right ? '○' : '×')+'</span>'+
            '</button>'; }).join('') +'</div>'+
          (r.blank
            ? '<p class="tiny" style="margin-top:14px">'+
              r.blank+jp('問は マスが塗られていませんでした。','問はマスが塗られていませんでした。')+
              jp('ぬりつぶしが うすいと 読めないことがあります。','塗りつぶしが薄いと読み取れないことがあります。')+'</p>' : '')+
          (wrong.length
            ? '<div class="lact-t" style="margin-top:18px">'+
              jp('まちがえたところ　','間違えた所　')+wrong.length+'問</div>'+
              '<div class="wklist">'+ wrong.map(function(x){
                var it = x.item;
                return '<div class="wrongq">'+
                  '<div class="wq"><b>'+(x.i+1)+'</b>'+esc(it.q)+'</div>'+
                  '<div class="wa">'+jp('こたえ　','答え　')+'<b>'+esc(it.ans)+'</b>'+
                    (x.chosen ? '　<s>'+esc(x.chosen)+'</s>' : jp('　（むかいとう）','　（無回答）'))+
                  '</div>'+
                  (it.note ? '<div class="wn">'+esc(String(it.note)
                      .replace(/<[^>]+>/g, ''))+'</div>' : '')+
                '</div>'; }).join('') +'</div>'
            : '<p class="tiny" style="margin-top:18px">'+
              jp('まちがいは ありませんでした。','間違いはありませんでした。')+'</p>')+
          '<div class="row" style="gap:10px; margin-top:18px">'+
            '<button class="btn small" data-camagain="1">'+jp('もう一度 撮る','撮り直す')+'</button>'+
            '<button class="lnk" data-camshut="1">'+jp('とじる','閉じる')+'</button>'+
          '</div>'+
        '</div>'+
      '</div>';
  }

  /* ---- 撮る ---- */
  var body;
  if(cam.noCam){
    body = '<p class="tiny">'+jp('カメラを つかえませんでした。','カメラを使えませんでした。')+
      jp('写真をえらんでください。','写真を選んでください。')+'</p>'+
      '<label class="btn small camfile">'+jp('写真をえらぶ','写真を選ぶ')+
        '<input type="file" accept="image/*" capture="environment" '+
        'id="camF" hidden></label>';
  }else{
    body = '<div class="camwrap"><video id="camV" playsinline muted></video>'+
      '<div class="camguide"><i></i><i></i><i></i><i></i></div></div>'+
      '<div class="row" style="gap:10px; margin-top:14px">'+
        '<button class="btn small" data-camshot="1">撮る</button>'+
        '<label class="lnk camfile">'+jp('写真をえらぶ','写真を選ぶ')+
          '<input type="file" accept="image/*" id="camF" hidden></label>'+
      '</div>';
  }
  return '<div class="shade" data-camshut="1"></div>'+
    '<div class="sheet wide" role="dialog" aria-modal="true">'+
      head('カメラで丸つけ',
           jp('解答らんの紙を、四すみの黒い四角が ぜんぶ写るように撮ってください','解答欄の紙を、四隅の黒い四角がすべて写るように撮ってください'))+
      '<div class="sh-body">'+
        (cam.why ? '<p class="camwhy">'+esc(cam.why)+'</p>' : '')+
        body+
        '<p class="tiny" style="margin-top:14px">'+
          jp('写真は この端末の中だけで読みます。','写真はこの端末の中だけで読み取ります。')+
          jp('サーバへ送ることも、のこすこともありません。','サーバへ送ることも、保存することもありません。')+'</p>'+
      '</div>'+
    '</div>';
}

/* 総復習テスト対策 ―― 毎日テストのいちばん上。

   組み分けテストの8日前から出る。ふだんの毎日テストより量が多く、
   1教科1時間ぶん。**それだけの山が来ていることを、まず伝える。**
   ここを小さく出すと、いつもの毎日テストと同じに見えて素通りされる。 */
function prepCard(){
  if(!prep) return '';
  var left = prep.left;
  var when = left === 0 ? jp('きょうが本番です','今日が本番です')
           : left === 1 ? jp('あした が本番','明日が本番')
           : 'あと ' + left + '日';
  /* 1教科に2つの入口 ―― アプリで解く／紙にする。
     紙は **教科ごと**にしか作らない。本番が1教科ずつだからである。
     行そのものを押せる button にすると、中に button を置けない
     （入れ子のボタンは押し分けられない）。行は div にして、
     中に2つの押せるものを並べる。 */
  var rows = (prep.sets || []).map(function(x){
    /* 解き終わった教科は「やった」にする。**行そのものは変えない** ――
       青い札の並びが崩れると、どこまで進んだかが読みにくくなる。
       にがての中身は、この札の下に別の札で出す。 */
    var sc = x.score;
    return '<div class="prow3'+(sc ? ' done' : '')+'">'+
      '<span class="pn3">'+esc(subjName(x.subject))+'</span>'+
      '<span class="pq3">'+(sc ? sc.ok+' / '+sc.n : x.n+jp('もん','問'))+'</span>'+
      '<span class="pm3">'+(sc ? Math.round(sc.ok/sc.n*100)+'%'
                              : x.minutes+'分')+'</span>'+
      /* **紙の数はアプリの数と違う。** 紙に載るのは選択肢のある問題だけで、
         解答らんのマスが上限。片方だけ書くと、刷ったときに数が合わない。 */
      '<button class="pbtn" data-prepsheet="'+esc(x.subject)+'">'+jp('紙にする','紙に印刷')+
        (x.paperN ? '<i>'+x.paperN+jp('もん','問')+'</i>' : '')+'</button>'+
      (sc
        ? '<span class="pbtn did">'+jp('やった','完了')+'</span>'
        : '<button class="pbtn go" data-prep="'+esc(x.subject)+'">'+jp('やる →','解く →')+'</button>')+
    '</div>';
  }).join('');
  return '<div class="h-card h-6 prep">'+
    '<div class="prep-top">'+
      '<div><div class="prep-l">組み分けテスト対策</div>'+
        '<div class="prep-n">'+esc(when)+'</div>'+
        '<div class="prep-s">'+esc(prep.exam.date)+' ・ '+
          esc(prep.tierName)+' ・ <span class="nobr">ぜんぶで '+prep.minutes+'分</span></div></div>'+
      '<div class="prep-b">'+esc(prep.tierName)+'</div>'+
    '</div>'+
    '<div class="prep-rows">'+rows+'</div>'+
    '<div class="prep-acts">'+
      '<button class="lnk prep-print" data-camopen="1">'+
        'カメラで丸つけ</button>'+
    '</div>'+
    handoff()+
  '</div>'+ weakCard();
}

/* にがてつぶし ―― 対策の札の**下**に置く別の札。

   青い札の中に混ぜると、教科の並びが途切れて「どこまで進んだか」が
   読みにくくなる。上は「何をやるか」、下は「どこを直すか」で分ける。

   単元は **横に並べる。** 縦の箇条書きにすると、3単元で札が
   対策そのものより大きくなり、主客が入れ替わる。 */
function weakCard(){
  var got = (prep.sets || []).filter(function(x){
    return x.score && (x.weak || []).length;
  });
  if(!got.length) return '';

  var rows = got.map(function(x){
    var todo = (x.weak || []).filter(function(w){ return !w.fixed; });
    var done = (x.weak || []).filter(function(w){ return w.fixed; });
    var chips = todo.map(function(w){
      return '<span class="wchip">'+esc(w.unit)+
        '<i>'+w.w+'/'+w.n+'</i></span>';
    }).join('') + done.map(function(w){
      return '<span class="wchip ok">'+esc(w.unit)+'<i>済</i></span>';
    }).join('');
    /* やり直す所は1行にまとめる。教材の言葉は講師が書いたまま。 */
    var hw = (x.review || []).filter(function(r){ return r.hw; })
      .map(function(r){ return r.hw; }).join('　／　');
    return '<div class="wrow">'+
      '<span class="wsub">'+esc(subjName(x.subject))+'</span>'+
      '<span class="wchips">'+chips+'</span>'+
      (todo.length
        ? '<button class="pbtn go" data-retest="'+esc(x.subject)+'">'+
            '再テスト →</button>'
        : '<span class="pbtn did">'+jp('やっつけた','克服')+'</span>')+
      (hw ? '<span class="whw">やり直す ― '+esc(hw)+'</span>' : '')+
    '</div>';
  }).join('');

  return '<div class="h-card h-6 weak">'+
    '<div class="wk-l">'+jp('にがてつぶし','苦手つぶし')+'<span>テストで落とした単元</span></div>'+
    rows +
  '</div>';
}

/* パソコンで解いて、スマホで撮る ―― その渡し方。

   紙はパソコンから刷る。撮るのはスマホ。この2台をつなぐのに
   **合言葉もQRコードも作らない。** 同じアカウントで入っているのだから、
   「さっき何を刷ったか」はサーバに聞けば分かる。
   聞かなくて済むものを聞く画面は、それだけで手間である。

   2台で同時に入っていて構わない ―― ログインのたびに別の合言葉が
   発行され、先に入ったほうも切れない（server/tube_server.py の login）。

   狭い画面では出さない。**いま手に持っている機械に
   「スマホでひらいてください」と書いても意味がない。** */
function handoff(){
  if(!ui().isWide()) return '';
  var got = lastSheet && lastSheet.subject
    ? jp('さっき刷った ','先ほど印刷した') + subjName(lastSheet.subject) + jp(' の紙を おぼえています。','の紙を覚えています。')
      + jp('スマホでは 教科を えらばなくて だいじょうぶです。','スマホでは教科を選ばなくて大丈夫です。')
    : jp('刷った紙は アプリが おぼえます。スマホでは 教科を えらぶ必要が ありません。','印刷した紙はアプリが覚えます。スマホで教科を選ぶ必要はありません。');
  return '<div class="hand">'+
    '<div class="hand-l">'+jp('解きおわったら ―― スマホで丸つけ','解き終わったら ―― スマホで丸つけ')+'</div>'+
    '<ol class="hand-s">'+
      '<li>スマホで <b>tube-study.uk</b> '+jp('をひらく（同じ合言葉で入れます）','を開く（同じ合言葉で入れます）')+'</li>'+
      '<li><b>毎日テスト</b> → <b>カメラで丸つけ</b> '+jp('をおす','を押す')+'</li>'+
      '<li><b>'+jp('2枚目の解答らん','2枚目の解答欄')+'</b>を、まっすぐ撮る</li>'+
    '</ol>'+
    '<div class="hand-n">'+esc(got)+'　'+
      jp('写真は この端末から出ません。読みおわったら すぐ消えます。','写真はこの端末から出ません。読み終わったらすぐ消えます。')+'</div>'+
  '</div>';
}

/* 教科の名前。講師の画面と同じ言い方にそろえる。 */
var SUBJ_JA = {japanese:'国語', math:'数学', english:'英語', science:'理科', social:'社会'};
function subjName(id){
  var s = TubeContent.subject(id);
  if(s && s.name) return s.name;
  /* 教材の無い教科（小学生の英語など）は表から。id をそのまま出さない（10-10「english」と出ていた） */
  if(id === 'math' && String((S().me || {}).grade || '').charAt(0) === 'e') return '算数';
  return SUBJ_JA[id] || id;
}

/* 今日の毎日テスト ―― このタブの主役。1つだけ大きく出す。
   前は教科の行と小さな札の下に「きょうは これ」が埋もれていて、
   毎日テストそのものが目に入らなかった。

   始めるのは「残っている教科のうち、できが低い教科」から（dailyPick）。
   組み分けテスト対策が出ている間は、対策の札が主役なので、こちらは淡くする
   （前と同じ見え方）。 */
/* 続けた記録 ―― 直近4週（月〜日）のカレンダー。やりきった日は濃く、途中まで は薄く。
   毎日テストは、まちがえた問題を集めて自分だけの問題集にする根幹の仕組み。続けている形を見せる。 */
function dailyCalendar(p){
  var hist = p.hist || {}, st = streakOf(hist), now = Date.now();
  var mon = global.TubeCheer.monday(now), cells = '', month = 0;
  var start = mon - 21 * TubeSRS.DAY;
  for(var i = 0; i < 28; i++){
    var t = start + i * TubeSRS.DAY, k = TubeSRS.dayKey(t), h = hist[k];
    var d = new Date(t), future = t > now + TubeSRS.DAY / 2;
    var cls = future ? 'future' : (h && h.n) ? (h.done ? 'done' : 'part') : 'none';
    if(TubeSRS.dayKey(now) === k) cls += ' today';
    cells += '<i class="'+cls+'" title="'+(d.getMonth()+1)+'/'+d.getDate()+'">'+
      (d.getDate() === 1 || i === 0 ? '<b>'+(d.getMonth()+1)+'/'+d.getDate()+'</b>' : '<b>'+d.getDate()+'</b>')+'</i>';
    if(h && h.n && (now - t) < 30 * TubeSRS.DAY && d.getMonth() === new Date(now).getMonth()) month++;
  }
  return '<div class="h-card h-6 d-cal">'+
    '<div class="h-row">'+hlbl('bars', jp('つづけた きろく', '続けた記録'))+'<span class="h-foot">'+jp('今月 ', '今月 ')+'<span class="num">'+month+'</span>'+jp('日', '日')+'</span></div>'+
    '<span class="h-big"><b class="num cu">'+st.run+'</b><span>'+jp('日 れんぞく', '日連続')+'</span>'+
      (st.best > st.run ? '<small>'+jp('いちばん長く ', '最長 ')+st.best+jp('日', '日')+'</small>' : '')+'</span>'+
    '<span class="cal-wd">'+['月','火','水','木','金','土','日'].map(function(x){ return '<i>'+x+'</i>'; }).join('')+'</span>'+
    '<span class="cal-grid">'+cells+'</span>'+
    '<span class="h-foot left">'+jp('まちがえた 問題は、あなただけの 問題集に たまります', 'まちがえた問題は、あなただけの問題集にたまります')+'</span>'+
  '</div>';
}
/* 日替わりの一言（ことわざ・格言。出どころのあるものは添える）。目立たせない ―― 札の外に1行。 */
var QUOTES = [
  ['継続は力なり', '住岡夜晃'], ['千里の道も一歩から', '老子'], ['塵も積もれば山となる', 'ことわざ'],
  ['石の上にも三年', 'ことわざ'], ['ローマは一日にして成らず', 'ことわざ'], ['学問に王道なし', 'ユークリッド'],
  ['習うより慣れよ', 'ことわざ'], ['初心忘るべからず', '世阿弥'], ['急がば回れ', 'ことわざ'],
  ['今日できることを明日に延ばすな', 'フランクリン'], ['天才とは1%のひらめきと99%の努力である', 'エジソン'],
  ['少年老い易く学成り難し', '朱熹'], ['為せば成る、為さねば成らぬ何事も', '上杉鷹山'], ['七転び八起き', 'ことわざ'],
  ['雨だれ石を穿つ', 'ことわざ'], ['知は力なり', 'ベーコン'], ['学びて時にこれを習う、また説ばしからずや', '孔子'],
  ['好きこそものの上手なれ', 'ことわざ'], ['百聞は一見に如かず', 'ことわざ'], ['失敗は成功のもと', 'ことわざ'],
  ['一日一善', 'ことわざ'], ['井の中の蛙、大海を知らず', 'ことわざ'], ['温故知新', '孔子'],
  ['人事を尽くして天命を待つ', 'ことわざ'], ['負けるが勝ち', 'ことわざ'], ['能ある鷹は爪を隠す', 'ことわざ'],
  ['蒔かぬ種は生えぬ', 'ことわざ'], ['思い立ったが吉日', 'ことわざ'], ['光陰矢の如し', 'ことわざ'],
  ['読書百遍、意おのずから通ず', 'ことわざ'], ['まちがえた問題こそ、伸びしろ', ''], ['昨日の自分より、一問多く', ''],
  ['速さより、毎日', ''], ['今日の10分が、来週の自信になる', ''], ['覚えるより、思い出す練習', '']
];
function dailyQuote(){
  var day = Math.floor((Date.now() + new Date().getTimezoneOffset() * -60000) / 864e5);
  var q = QUOTES[day % QUOTES.length];
  return '<p class="dq h-full">「'+esc(q[0])+'」'+(q[1] ? '<span>― '+esc(q[1])+'</span>' : '')+'</p>';
}
function dailyHero(p, dp){
  if(!dp.rows.length) return '';
  var hist = p.hist || {}, st = streakOf(hist), dots = '';
  for(var d = 6; d >= 0; d--){
    dots += '<i class="'+(hist[TubeSRS.dayKey(Date.now() - d * TubeSRS.DAY)] ? 'on' : '')+'"></i>';
  }
  var act7 = 0;
  for(var e = 6; e >= 0; e--){ if(hist[TubeSRS.dayKey(Date.now() - e * TubeSRS.DAY)]) act7++; }
  var dn = new Date(), WDS = ['日','月','火','水','木','金','土'];
  var head = '<div class="h-row"><span class="h-lbl blue">'+jp('きょうの 毎日テスト', '今日の毎日テスト')+'</span>'+
      '<span class="h-foot"><span class="num">'+(dn.getMonth()+1)+'/'+dn.getDate()+'</span>（'+WDS[dn.getDay()]+'）</span></div>';
  var ringCol = '<div class="d-ringcol"><span class="h-ringwrap small">'+ringSvg(act7 / 7, act7 >= 7)+
      ringC(act7, '/7')+'</span>'+
      '<span class="d-run">'+(st.run > 0 ? '<span class="num">'+st.run+'</span>'+jp('日 れんぞく', '日連続') : jp('きょうから', '今日から'))+'</span></div>';
  var names = dp.rows.map(function(r){ return r.x.subject.name; }).join('・');

  if(!dp.next){
    return '<div class="h-card h-6 d-hero done">'+ head +
      '<div class="d-herorow">'+ringCol+'<div class="d-herotx">'+
        '<div class="d-title">'+jp('きょうの分は おわりました', '今日の分は終わりました')+'</div>'+
        '<div class="d-sub"><span>'+esc(names)+'</span><span>'+jp('やった分が そのまま 力に なります', '解いた分がそのまま力になります')+'</span></div>'+
      '</div></div>'+
      '<button class="btn ghost" data-extra="'+esc(dp.any)+'">'+jp('もう少し やる', 'もう少しやる')+'（'+esc(subjName(dp.any))+jp(' を もう10もん', 'をもう10問')+'）</button>'+
    '</div>';
  }

  /* **大きく出すのは「いま始める1教科ぶん」だけ。** 今日の合計（200問を
     超える日もある）を大きく見せると、始める前に気持ちが折れる。 */
  var started = !!hist[TubeSRS.dayKey()];
  var others = dp.rows.filter(function(r){ return r.left > 0 && r !== dp.next; }).length;
  var sid = dp.next.x.subject.id;
  return '<div class="h-card h-6 d-hero'+ui().sjClass(sid)+'">'+ head +
    '<div class="d-herorow">'+ringCol+'<div class="d-herotx">'+
      '<span class="h-sj big">'+ui().subjIcon(sid, 20)+esc(dp.next.x.subject.name)+'</span>'+
      '<span class="h-big"><b class="num cu">'+dp.next.left+'</b><span>'+jp('もん', '問')+'</span>'+
        '<small>'+jp('やく ', '約')+'<span class="num">'+roughMin(dp.next.left)+'</span>分</small></span>'+
    '</div></div>'+
    '<div class="d-sub"><span>'+(started
      ? jp('とちゅうまで できています', '途中まで進んでいます')
      : jp('きょうは これから', '今日はこれから'))+'</span>'+
      (others ? '<span>'+jp('ほかの 教科は そのあとで（'+others+'教科）', 'ほかの教科はその後で（'+others+'教科）')+'</span>' : '')+
    '</div>'+
    '<button class="btn" data-start="'+esc(sid)+'">'+jp('はじめる', '始める')+'</button>'+
  '</div>';
}

function viewDaily(m){
  init();
  var s = S(), p = s.me.p;
  /* 言い方でやる気は変わる。
       「やらなくてもOK」は、やらない理由をこちらから渡している。
       「おぼえるだけの問題です」も、価値を自分から下げている。
       伝えるべきは「やった分がそのまま力になる」ことだけ。 */

  /* 組み分けテスト対策と、直前に刷った紙。**このタブを開いたときだけ**聞きに行き、
     返事は待たずに描く ―― 来たら loadPrep が描き直して、対策の札を差し込む。
     ホームと宿題のタブでは聞かない（どちらにも対策は出さない）。 */
  loadPrep();
  loadLastSheet();

  var dp = dailyPick(p);
  var html = pageHead('毎日テスト', '')+
    camPickSheet()+ camSheet()+
    '<div class="h-grid t-full">'+
    /* 対策は、サーバが返してきたときだけ出る（prep が null なら空）。
       出ている間は前と同じく いちばん上。画面の側で作り出さない。 */
    prepCard()+
    dailyHero(p, dp);

  /* 教科ごとに1行。**箱にしない。**
     2科の子も5科の子も、同じ形で並ぶようにする。
     上の札で始める教科も、ほかの教科も、ここから選べる。 */
  if(dp.rows.length){
    /* 教科は札の格子（ホームの札と同じ形。行を端から端まで伸ばさない）。押すとその教科を始める。 */
    html += '<div class="d-tiles n'+dp.rows.length+'">'+ dp.rows.map(function(r){
      var done = r.left === 0, id = r.x.subject.id;
      return '<button class="h-card d-tile'+(done ? ' done' : '')+ui().sjClass(id)+'" data-'+(done ? 'extra' : 'start')+'="'+esc(id)+'">'+
        '<span class="h-sj">'+ui().subjIcon(id, 18)+esc(r.x.subject.name)+'</span>'+
        (done ? '<span class="h-big"><b class="d-ok">'+ico('check', 34, 2.4)+'</b></span>'
              : '<span class="h-big"><b class="num cu">'+r.left+'</b><span>'+jp('もん', '問')+'</span></span>')+
        '<span class="d-tfoot"><span class="h-foot left">'+(done ? jp('もう10もん', 'もう10問') : jp('やく ', '約')+'<span class="num">'+roughMin(r.left)+'</span>'+jp('分', '分'))+'</span>'+
          '<span class="d-go" aria-hidden="true">'+ico('chev', 18, 2.6)+'</span></span>'+
      '</button>';
    }).join('') +'</div>';
    html += dailyCalendar(p) + dailyQuote() + '</div>';
  }else if((s.me.subjects || []).length){
    /* 教科はあるが、どのコースも「毎日テストまで」の導入になっていない。 */
    html += '<div class="h-card h-full hw-none">'+jp('毎日テストは、まだ 使っていません。','毎日テストは、まだ使っていません。')+'<br>'+
            jp('先生が 使いはじめると、ここに 出ます。','先生が使い始めると、ここに出ます。')+'</div></div>';
  }else{
    html += '<div class="h-card h-full hw-none">'+jp('まだ教材がわりあてられていません。','まだ教材が割り当てられていません。')+'<br>'+
            jp('先生に 聞いてください。','先生に聞いてください。')+'</div></div>';
  }

  m.innerHTML = html;
  bindStarts(m);
  m.querySelectorAll('[data-test]').forEach(function(x){
    x.onclick = function(){ startUnitTest(x.dataset.test); };
  });
  m.querySelectorAll('[data-prep]').forEach(function(x){
    x.onclick = function(){ startPrep(x.dataset.prep, x); };
  });
  m.querySelectorAll('[data-camopen]').forEach(function(x){
    x.onclick = function(){
      /* どの教科を採点するか。**聞かずに済むなら聞かない。**
         ① パソコンで直前に刷った紙があれば、それ
         ② 対策が1教科しか出ていなければ、それ
         ③ それ以外のときだけ、選んでもらう */
      var sets = (prep && prep.sets) || [];
      var known = lastSheet && lastSheet.subject;
      if(known && sets.some(function(y){ return y.subject === known; })){
        return camOpen(known);
      }
      if(sets.length === 1) return camOpen(sets[0].subject);
      camPick = true; ui().render();
    };
  });
  m.querySelectorAll('[data-campick]').forEach(function(x){
    x.onclick = function(){ camPick = false; camOpen(x.dataset.campick); };
  });
  m.querySelectorAll('[data-camshut]').forEach(function(x){
    x.onclick = function(){ camClose(); camPick = false; ui().render(); };
  });
  m.querySelectorAll('[data-camagain]').forEach(function(x){
    x.onclick = function(){
      var sub = cam && cam.subject;
      camClose(); if(sub) camOpen(sub);
    };
  });
  m.querySelectorAll('[data-camshot]').forEach(function(x){
    x.onclick = function(){
      var v = document.getElementById('camV');
      if(!v || !v.videoWidth) return toast('カメラの準備ができていません');
      x.disabled = true;
      var c = document.createElement('canvas');
      c.width = v.videoWidth; c.height = v.videoHeight;
      c.getContext('2d').drawImage(v, 0, 0);
      camGrade(c);
    };
  });
  var cf = document.getElementById('camF');
  if(cf) cf.onchange = function(){
    var f = cf.files && cf.files[0];
    if(!f) return;
    /* **blob: の URL は使わない。**
       端末や設定によっては blob: を画像として開けない
       （この検査に使った環境でも開けなかった）。
       中身をそのまま読み込む道のほうが、どこでも通る。 */
    var fr = new FileReader();
    fr.onload = function(){
      var img = new Image();
      img.onload = function(){ camGrade(img); };
      img.onerror = function(){
        if(cam) cam.why = jp('写真が ひらけませんでした','写真を開けませんでした');
        ui().render();
      };
      img.src = fr.result;
    };
    fr.onerror = function(){
      if(cam) cam.why = jp('写真が よみこめませんでした','写真を読み込めませんでした');
      ui().render();
    };
    fr.readAsDataURL(f);
  };
  m.querySelectorAll('[data-retest]').forEach(function(x){
    x.onclick = function(){ startRetest(x.dataset.retest, x); };
  });
  m.querySelectorAll('[data-prepsheet]').forEach(function(x){
    x.onclick = function(){
      /* 紙は別の窓で開く。印刷して戻ってきたときに、
         いまやっているところを失わないため。 */
      var t = (S().srv && S().srv.token && S().srv.token()) || '';
      /* 教科は必ず付ける。**混ぜた紙は作らない** ―― 本番が1教科ずつで、
         時間も教科ごとに区切られているからである。 */
      window.open('/api/assignments/prep/sheet?t=' + encodeURIComponent(t) +
                  '&subject=' + encodeURIComponent(x.dataset.prepsheet),
                  '_blank');
    };
  });
}

/* 総復習テスト対策を始める。**中身はここで初めて取りに行く。**
   一覧に5教科×100問を載せると、開くだけで200KBを超える。 */
async function startPrep(subjectId, btn){
  if(btn){ btn.disabled = true; }
  if(!prepFull) prepFull = await S().srv.prepAll();
  if(btn){ btn.disabled = false; }
  if(!prepFull) return toast(jp('いま 対策は ありません','今は対策がありません'));
  var set = (prepFull.sets || []).filter(function(x){
    return x.subject === subjectId; })[0];
  if(!set || !(set.items || []).length) return toast(jp('この教科の問題は ありません','この教科の問題はありません'));
  /* サーバが組んだ並びをそのまま出す。
     まちがえた問題が先頭に来るように並べてある。 */
  var q = set.items.map(function(it){
    var got = TubeContent.get(it.id);
    if(got){ var o = {}; for(var k in got) o[k] = got[k]; return o; }
    /* 教材が読み込まれていない場合は、サーバが渡した中身で出す。 */
    return {id:it.id, t:(it.dis && it.dis.length) ? 'quiz' : 'term',
            subject:it.subject, q:it.q, ans:it.ans, dis:it.dis || [],
            note:it.note || '', front:it.q, back:it.ans};
  });
  begin(q, {kind:'prep', subject:{id:subjectId, name:subjName(subjectId)}});
}

/* 苦手単元の再テスト。**紙にはしない。**
   直したいのは数単元ぶんで、刷るほどの量にならないうえ、
   その場で答え合わせできるほうが早く直る。
   出し方は毎日テストとまったく同じ ―― 4択を順に押していく。 */
async function startRetest(subjectId, btn){
  if(btn) btn.disabled = true;
  var got = await S().srv.retest(subjectId);
  if(btn) btn.disabled = false;
  if(!got || !(got.items || []).length){
    return toast(jp('いま 再テストする単元は ありません','今は再テストする単元がありません'));
  }
  var q = got.items.map(function(it){
    var have = TubeContent.get(it.id);
    if(have){ var o = {}; for(var k in have) o[k] = have[k]; return o; }
    return {id:it.id, t:'quiz', subject:it.subject, q:it.q, ans:it.ans,
            dis:it.dis || [], note:it.note || '', front:it.q, back:it.ans};
  });
  begin(q, {kind:'retest', subject:{id:subjectId, name:subjName(subjectId)},
            units:got.units});
}

/* ============================================================
   ノートの宿題を、写真で出す
   ============================================================
   紙の宿題は、アプリからは達成が見えない。見えないものは
   「未提出」にも数えられないし、褒めることもできない。
   **紙でちゃんとやっている生徒ほど、何もしていないように見える。**
   写真1枚でそこがつながる。

   写真は base64 にして送る。**端末に残さない** ―― 送ったら捨てる。
   ============================================================ */
var subs = undefined;     /* {宿題ID: {at, files, seen, note}} */

/* ------------------------------------------------------------
   宿題の変更のお知らせ ―― 先生が「この生徒だけの宿題」を変えたときの、ひとこと。
   突然宿題が変わると生徒も保護者も驚くので、理由が先に届く。重要なので、返事の口が2つある：
     わかった  → 消える（先生に「確認した」と伝わる）。押さなくても1週間で同じ
     質問する  → 先生に質問が届き、返事が来るまでこの変更は止まる（先生の画面にも出る）
   ------------------------------------------------------------ */
var notices = undefined;      /* [{id,key,subject,course,msg,text,span,at,state,question,answer,...}] */
var ntAsk = {};               /* お知らせID → 書きかけの質問（欄を開いているとき） */
function loadNotices(force){
  if(notices !== undefined && !force) return;
  if(notices === undefined) notices = null;
  var s = S(); if(!s.srv || !s.srv.notices) return;
  s.srv.notices().then(function(got){ if(!got) return; notices = got; if(!S().session) ui().render(); });
}
function ntSubj(id){
  var hit = (S().me.subjects || []).filter(function(x){ return x.subject && x.subject.id === id; })[0];
  return hit ? hit.subject.name : '';
}
function noticeCards(side){
  loadNotices();
  var list = notices || [];
  if(!list.length) return '';
  return list.map(function(n){
    var day = ui().fmtDate((n.at || 0) * 1000);
    /* 見本 S04：題は「宿題の追加」か「宿題の変更」。決まりの種類（add／drop・scale・swap）から引く。無ければ文から */
    if(n.kind === 'drop' || n.kind === 'scale' || n.kind === 'swap') n.kind = 'change';
    if(!n.kind) n.kind = /足す$|を足す|追加/.test(n.text || '') ? 'add' : 'change';
    var title = n.kind === 'change' ? jp('しゅくだいの へんこう', '宿題の変更') : n.kind === 'add' ? jp('しゅくだいの ついか', '宿題の追加') : jp('しゅくだいの おしらせ', '宿題のお知らせ');
    var body = '<div class="nt-head"><span class="nt-ic">'+ico(n.kind === 'change' ? 'edit' : 'plus', 22, 2.2)+'</span>'+
        (side ? '<span class="nt-tt">' : '')+
        '<span class="nt-t">'+esc(title)+'</span><span class="nt-day num">'+esc(day)+'</span>'+(side ? '</span>' : '')+'</div>'+
      '<div class="nt-body"><p class="nt-what"><span class="ch-sj'+ui().sjClass(n.subject)+'">'+esc(ntSubj(n.subject))+'</span>'+jp('の ', 'の ')+esc(n.text)+'</p>'+
        (n.span ? '<p class="nt-span">'+esc(n.span)+'</p>' : '')+'</div>'+
      (n.msg ? '<p class="nt-msg">「'+esc(n.msg)+'」</p>' : '');
    var act = '';
    if(n.state === 'asked'){
      act = '<div class="nt-wait">'+jp('しつもんを おくりました。先生の へんじを まっています（この へんこうは へんじまで とまっています）',
                                        '質問を送りました。先生の返事を待っています（この変更は返事まで止まっています）')+'</div>'+
            (n.question ? '<p class="nt-q">'+esc(n.question)+'</p>' : '');
    }else{
      if(n.state === 'answered' && n.answer) act += '<div class="nt-ans"><span class="lbl">'+jp('先生の へんじ', '先生の返事')+'</span><p>'+esc(n.answer)+'</p></div>';
      if(ntAsk[n.id] !== undefined){
        act += '<div class="nt-form"><textarea data-ntta="'+esc(n.id)+'" rows="3" maxlength="400" placeholder="'+esc(jp('しつもんを かく', '質問を書く'))+'">'+esc(ntAsk[n.id])+'</textarea>'+
          '<div class="nt-acts nt-formacts"><button class="btn small ghost" data-ntcancel="'+esc(n.id)+'">'+jp('やめる', 'やめる')+'</button>'+
          '<button class="btn small" data-ntsend="'+esc(n.id)+'|'+esc(n.key)+'">'+jp('おくる', '送る')+'</button></div></div>';
      }else{
        act += '<div class="nt-acts"><button class="btn small" data-ntok="'+esc(n.id)+'|'+esc(n.key)+'">'+jp('わかった', 'わかった')+'</button>'+
          '<button class="btn small ghost" data-ntask="'+esc(n.id)+'">'+jp('しつもんする', '質問する')+'</button></div>';
      }
    }
    return '<div class="nt t-full'+(n.state === 'asked' ? ' asked' : '')+(side ? ' side' : '')+'" data-nt="'+esc(n.id)+'">'+body+act+'</div>';
  }).join('');
}
function bindNotices(m){
  m.querySelectorAll('[data-ntok]').forEach(function(b){ b.onclick = async function(){
    var p = b.dataset.ntok.split('|'); b.disabled = true;
    var r = await S().srv.ackNotice(p[0], p[1], 'ok');
    if(!r.ok){ b.disabled = false; return toast(r.error); }
    notices = r.notices; toast(jp('先生に つたえました', '先生に伝えました')); ui().render();
  }; });
  m.querySelectorAll('[data-ntask]').forEach(function(b){ b.onclick = function(){ ntAsk[b.dataset.ntask] = ''; ui().keepInPlace(b.closest('.nt')); ui().render(); }; });
  m.querySelectorAll('[data-ntcancel]').forEach(function(b){ b.onclick = function(){ delete ntAsk[b.dataset.ntcancel]; ui().keepInPlace(b.closest('.nt')); ui().render(); }; });
  m.querySelectorAll('[data-ntta]').forEach(function(t){ t.oninput = function(){ ntAsk[t.dataset.ntta] = t.value; }; });
  m.querySelectorAll('[data-ntsend]').forEach(function(b){ b.onclick = async function(){
    var p = b.dataset.ntsend.split('|'), text = (ntAsk[p[0]] || '').trim();
    if(!text) return toast(jp('しつもんを かいてください', '質問を書いてください'));
    b.disabled = true;
    var r = await S().srv.ackNotice(p[0], p[1], 'ask', text);
    if(!r.ok){ b.disabled = false; return toast(r.error); }
    delete ntAsk[p[0]]; notices = r.notices; toast(jp('先生に おくりました', '先生に送りました')); ui().render();
  }; });
}
var upBusy = null;        /* いま送っている宿題ID */
var upWord = '';          /* 送っている間の言葉（「2/4まい…」） */
var pending = {};         /* 宿題ID → ためた写真 [{file, url}] */
var UP_MAX_TOTAL = 11 * 1024 * 1024;   /* 1回に送れる本文（サーバの MAX_UPLOAD 12MB より少し小さく） */

/* 別の端末で出した・先生が返した、を取り込む。送っている最中は触らない。 */
function refreshSubs(){
  var s = S();
  if(!s.srv || !s.srv.mySubs || upBusy) return;
  s.srv.mySubs().then(function(got){
    if(!got || upBusy) return;
    subs = got;
    TubeHomework.setSubs(subs);
    if(!S().session) ui().render();
  });
}
function wake(changed){
  if(!changed || changed.submissions || changed.ratings) refreshSubs();
  if(!changed || changed.assignments) refreshHomework();
  if(!changed || changed.personal || changed.messages) loadNotices(true);
}
function loadSubs(){
  if(subs !== undefined) return;
  subs = null;
  var s = S();
  if(!s.srv || !s.srv.mySubs) return;
  s.srv.mySubs().then(function(got){
    subs = got || {};
    /* 紙の宿題が「おわった」かどうかは、写真を出したかで決まる。宿題の側にも渡す。 */
    TubeHomework.setSubs(subs);
    if(!S().session) ui().render();
  });
}

/* 写真は**縮めて JPEG にしてから**送る（photo.js。講師の取り込みも同じ道）。 */
function prepareFile(file){ return TubePhoto.prepare(file); }

/* 選んだ写真を**ためる**（送らない）。読めない写真はここで言う。 */
async function stageFiles(aid, list){
  var cur = pending[aid] || [];
  if(cur.length + list.length > 10) return toast(jp('いちどに 10まいまでです','一度に10枚までです'));
  upBusy = aid; upWord = jp('写真を よんでいます…', '写真を読んでいます…'); ui().render();
  try{
    for(var i = 0; i < list.length; i++){
      var f = await prepareFile(list[i]);
      if(!f || !f.b64) throw new Error('empty');
      cur.push(f);
    }
    pending[aid] = cur;
  }catch(e){ toast(jp('写真を よめませんでした','写真を読み込めませんでした')); }
  finally{ upBusy = null; upWord = ''; ui().render(); }
}
async function submitHw(aid, list){
  /* list が来たら（古い呼び方）まず ためる。送るのは「N枚を送る」を押したとき。 */
  if(list && list.length) return stageFiles(aid, list);
  var files = pending[aid] || [];
  if(!files.length) return;
  var total = files.reduce(function(n, f){ return n + (f.b64 || '').length; }, 0);
  if(total > UP_MAX_TOTAL) return toast(jp('おおきすぎます。PDF は 6MB まで、まいすうを へらして ください', '大きすぎます。PDF は 6MB まで。枚数を減らしてください'));
  upBusy = aid; upWord = files.length+jp('まいを おくっています…', '枚を送っています…'); ui().render();
  var got;
  try{
    got = await S().srv.submitHw(aid, files.map(function(f){ return {type:f.type, b64:f.b64}; }));
  }catch(e){ got = {error:jp('つうしんに しっぱいしました','通信に失敗しました')}; }
  finally{ upBusy = null; upWord = ''; }
  if(!got || got.error){
    ui().render();
    return toast((got && got.error) || jp('おくれませんでした','送信できませんでした'));
  }
  delete pending[aid];
  subs = subs || {};
  subs[aid] = got.sub;
  TubeHomework.setSubs(subs);
  /* 出した宿題は「おわった宿題」へ移る。どこへ行ったかが分かるように言う。 */
  toast(jp('出しました。先生が 見たら「おわった宿題」に 印が つきます',
           '提出しました。先生が確認すると「終わった宿題」に印が付きます'));
  ui().render();
}

/* 出したあとの状態。先生が見たか・ひとこと・出しなおす口 をここに置く。
   まだ出していなければ何も返さない ―― 出す口は hwAction（宿題のタブとホーム）。 */
function submitRow(a){
  loadSubs();
  var got = (subs || {})[a.id];
  if(upBusy === a.id){
    return '<div class="upl busy">'+esc(upWord || jp('おくっています…','送信しています…'))+'</div>';
  }
  if(pending[a.id] && pending[a.id].length) return stageHtml(a);      /* 出しなおすときも、ためてから送る */
  if(!got) return '';
  var when = ui().fmtDate(got.at * 1000);
  return '<div class="upl done'+(got.seen ? ' seen' : '')+'">'+
    '<div class="up-l">'+
      (got.seen ? '<b class="up-ck">'+jp('✓ 先生が 見ました','✓ 確認済み')+'</b>'
                : '<b>'+jp('出しました・先生の かくにん まち','提出済み・確認待ち')+'</b>')+
      '<span>'+esc(when)+'　'+(got.pruned ? jp('写真は ほぞんきかんを すぎました', '写真は保存期間を過ぎました')
                                        : (got.files||[]).length+jp('まい','枚'))+'</span>'+
    '</div>'+
    (got.note ? '<p class="up-note">'+esc(got.note)+'</p>' : '')+
    (got.returned && (got.returned.files || []).length
      ? '<button class="btn small up-ret" data-ret="'+esc(a.id)+'">'+jp('先生の 赤を 見る', '添削された答案を見る')+
          '（'+got.returned.files.length+jp('まい', '枚')+'）</button>' : '')+
    '<label class="upl-again">'+
      '<input type="file" accept="image/*,application/pdf" multiple '+
        'data-up="'+esc(a.id)+'">'+
      '<span>'+jp('出しなおす','再提出する')+'</span>'+
    '</label>'+
  '</div>';
}

/* （ここにあった hwCardPaper / hwCard と、教科の中の一覧 viewSubject は消した。
   紙の宿題を見て出すのは、宿題のタブ（viewHomework）とホームの1件だけである。） */

function subjectOf(id){
  return S().me.subjects.filter(function(x){ return x.subject.id === id; })[0];
}

function startDaily(subjectId){
  var x = subjectOf(subjectId); if(!x) return;
  var q = TubeSRS.buildQueue(S().me.p, x.plan, x.order);
  begin(q, {kind:'daily', subject:x});
}
function startExtra(subjectId){
  var x = subjectOf(subjectId); if(!x) return;
  var q = TubeSRS.newCards(S().me.p, x.order, null, 10);
  if(!q.length) return toast(jp('この教科の教材は ぜんぶ出しおわりました','この教科の教材はすべて出し終わりました'));
  begin(q, {kind:'extra', subject:x});
}
async function startHomework(aid){
  var a = TubeHomework.byId(aid);
  if(!a) return toast(jp('この宿題は とりけされたようです','この宿題は取り消されたようです'));
  /* 番号のうしろに単語が入っている教材（My英単語帳）は、
     **その教材を読んでから始める。** 読む前に始めると、語が引けず
     「番号を冊子でひいて」という古い画面に落ちる。 */
  var b = TubeContent.booklet(a.source);
  if(b && b.pack && !TubeContent.isLoaded(b.pack)){
    await TubeContent.loadPacks([b.pack]);
  }
  var q = TubeHomework.queue(S().me.p, a);
  if(!q.length) return toast(jp('いま やるぶんは ありません','今は解く分がありません'));
  begin(q, {kind:'hw', hw:a});
}

/* 単元確認テスト ―― すでに出した項目からランダムに選んで並べる。
   採点は記録に残すが、間隔（次にいつ出るか）は動かさない。
   テストのたびに復習の予定が崩れると、毎日の分量が読めなくなるため。 */
function startUnitTest(subjectId){
  var x = subjectOf(subjectId); if(!x) return;
  var p = S().me.p;
  var seen = x.order.filter(function(c){ return p.cards[c.id]; });
  var pool = seen.length >= 10 ? seen : x.order;
  if(!pool.length) return toast(jp('まだ 出題できる教材が ありません','まだ出題できる教材がありません'));
  var n = Math.min(10, pool.length);
  begin(ui().shuffle(pool).slice(0, n),
        {kind:'test', subject:x, right:0, asked:0});
}

function begin(queue, meta){
  if(!queue.length) return toast(jp('出すもんだいが ありません','出題できる問題がありません'));
  var s = S();
  s.session = Object.assign({queue:queue, i:0, total:queue.length,
                             right:0, wrong:0, started:Date.now()}, meta);
  ui().render();
}

function endSession(){
  var s = S(), p = s.me.p;
  var k = TubeSRS.dayKey();
  var h = p.hist[k] || (p.hist[k] = {n:0, ok:0});
  if(s.session && s.session.kind === 'daily'){
    var left = s.me.subjects.reduce(function(n, x){
      return n + TubeSRS.plan(p, x.plan, x.order).total; }, 0);
    if(left === 0) h.done = 1;
  }
  /* 再テストが終わったら、結果をサーバへ。よくできていれば
     その単元は「対策ずみ」になり、対策の札から消える。
     **消えることが目に見えるのが、この機能のいちばんの値打ち**である。 */
  if(s.session && s.session.kind === 'retest' && s.srv && s.srv.retestDone){
    var sub = (s.session.subject || {}).id;
    var units = s.session.units || [];
    var tot = (s.session.queue || []).length;
    var right = s.session.right || 0;
    s.srv.retestDone(sub, units, right, tot).then(function(got){
      if(got && got.fixed){
        toast(got.fixed + jp('単元 やっつけました','単元を克服しました'));
        prep = undefined; prepFull = null;
        loadPrep();
      }
    });
  }
  ui().persist();
  /* 始めた画面へ戻る。ホームから始めたらホーム、宿題のタブなら宿題。
     （出題のあいだも S.view は始めた画面のまま残っている） */
  var back = s.view;
  s.session = null;
  ui().go(back || 'daily');
}
function advance(){ S().session.i++; nextCard(); }

/* ============================================================
   出題
   ============================================================ */
function renderSession(){
  init();
  var s = S();
  $('#chrome').innerHTML =
    '<div class="sbar"><button class="btn small ghost hit" id="sQuit">やめる</button>'+
    '<div class="meter"><i id="sBar" style="width:0%"></i></div>'+
    '<div class="num" id="sCount">0 / 0</div></div>';
  $('#main').innerHTML = '<div id="sBody"></div>';
  $('#foot').innerHTML = '<footer class="sfoot" id="sFoot"></footer>';
  $('#sQuit').onclick = endSession;
  var sj = s.session && s.session.subject, q0 = s.session && s.session.queue && s.session.queue[0];
  ui().subject((typeof sj === 'string' ? sj : (sj && sj.id)) || (q0 && q0.subject) || null);   /* 色玉はその教科の色 */
  nextCard();
}

function nextCard(){
  var s = S();
  if(!s.session) return;
  if(s.session.i >= s.session.queue.length) return showDone();
  $('#sBar').style.width = (s.session.i / s.session.total * 100).toFixed(1) + '%';
  $('#sCount').textContent = s.session.i + ' / ' + s.session.total;
  var c = s.session.queue[s.session.i];
  if(c.t === 'hw')         cardHomework(c);
  else if(c.t === 'vocab') cardVocab(c);
  else if(c.t === 'term')  cardTerm(c);
  else if(c.t === 'quiz' || c.t === 'prep') cardChoice(c);
  else if(c.t === 'gram')  cardGram(c);
  else                     cardTerm(c);
}

function tag(c, extra){
  var sub = TubeContent.subject(c.subject || 'english');
  /* 帯の名前は、生徒が読んで意味のあるものだけ。仮置きの教材は
     帯が CEFR（A2〜C1）で、学年とは別のものなので出さない。 */
  var pk = c.pack ? TubeContent.packInfo(c.pack) : null;
  var band = (pk && pk.provisional) ? '' : (c.band || '');
  return '<div class="qtag">'+
         '<span class="qt-sj'+ui().sjClass(sub.id || c.subject || 'english')+'">'+ui().subjIcon(sub.id || c.subject || 'english', 16)+esc(sub.name || sub.short)+'</span>'+
         '<span class="qt-chip">'+esc(TubeContent.trackName(c.t))+'</span>'+
         (band ? '<span class="qt-chip">'+esc(band)+'</span>' : '')+
         (extra ? '<span class="qt-chip">'+extra+'</span>' : '')+'</div>';
}

/* 採点のボタン。テストのときは間隔を動かさない。 */
function gradeBar(c, labels){
  var s = S();
  var L = labels || [[1,jp('もういちど','もう一度')],[2,jp('むずかしい','難しい')],[3,'できた'],[4,jp('かんたん','簡単')]];
  $('#sFoot').innerHTML = '<div class="grades" style="grid-template-columns:repeat('+
    L.length+',1fr)">'+ L.map(function(g){
      return '<button class="grade g'+g[0]+'" data-g="'+g[0]+'"><b>'+g[1]+'</b>'+
             (s.session.kind === 'test' ? '' :
              '<span>'+jp('つぎは ', '次は')+TubeSRS.nextIv(s.me.p, c.id, g[0])+jp('後', '後')+'</span>')+'</button>';
    }).join('') +'</div>';
  $('#sFoot').querySelectorAll('.grade').forEach(function(b){
    b.onclick = function(){ applyGrade(c, +b.dataset.g); };
  });
}

function applyGrade(c, g){
  var s = S(), p = s.me.p;
  if(s.session.kind === 'test'){
    /* テストは記録だけ。次にいつ出るかは動かさない。 */
    s.session.asked++;
    if(g >= 3) s.session.right++;
    var k = TubeSRS.dayKey();
    var h = p.hist[k] || (p.hist[k] = {n:0, ok:0});
    h.n++; if(g >= 3) h.ok++;
    ui().persist();
    if(g >= 3) s.session.rightCount = (s.session.rightCount||0)+1;
    return advance();
  }
  if(!p.cards[c.id]){
    p.newToday = (p.newToday||0) + 1;
    if(!p.sessDone) p.sessDone = {};
    p.sessDone[c.t] = (p.sessDone[c.t]||0) + 1;
  }
  TubeSRS.grade(p, c.id, g);
  /* にがて集めの札は、宿題の進み具合にも数える。
     ここで数えないと、10問ぜんぶ答えても「あと10」のまま残る。 */
  if(c.hwOf) TubeHomework.mark(p, c.hwOf, c.hwKey, g);
  ui().persist();
  if(g === 1){ s.session.wrong++; s.session.queue.push(c); s.session.total++; }
  else s.session.right++;
  advance();
}

/* ---- 用語（全科目） ---- */
function cardTerm(c){
  /* 漢字の書き取りだけ、答えを大きく出す。
     **見分けはパック名でする。** 教材の形（列）は変えない ――
     形を変えると、いまある5千項目すべてが影響を受ける。
     パック名に kaki が入っているものだけが、この道を通る。 */
  var kaki = String(c.pack || '').indexOf('kaki') >= 0;
  $('#sBody').innerHTML = '<div class="qcard fade">'+tag(c)+
    '<div class="headword'+(kaki ? ' kaki-q' : '')+'">'+
      esc(c.front || c.head || '')+'</div>'+
    '<div id="rev"></div></div>';
  $('#sFoot').innerHTML = '<button class="btn" id="show">'+
    (kaki ? '答えの漢字を見る' : jp('こたえを見る','答えを見る'))+'</button>';
  $('#show').onclick = function(){
    $('#rev').innerHTML = '<div class="reveal'+(kaki ? ' kaki' : '')+'">'+
      '<div class="def-ja">'+esc(c.back || c.ja || '')+'</div>'+
      (c.ex ? '<div class="ex"><div class="ex-en">'+esc(c.ex)+'</div>'+
        (c.exSub ? '<div class="ex-ja">'+esc(c.exSub)+'</div>' : '')+'</div>' : '')+
      (c.note ? '<div class="note">'+c.note+'</div>' : '')+
    '</div>';
    gradeBar(c);
  };
}

/* ---- 単語（英語） ---- */
function cardVocab(c){
  var s = S();
  var mode = TubeSRS.vocabMode(s.me.p, c.id, TubeConfig.mature());
  var head;
  if(mode === 'produce'){
    head = '<div class="prompt">'+esc(c.ja)+'</div>'+
           '<div class="prompt-ja">'+jp('…を あらわす英語は？（','…を表す英語は？（')+esc(c.pos)+'）</div>';
  }else if(mode === 'cloze'){
    var stem = c.head.split(' ')[0].replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
    var GAP = '';
    head = '<div class="cloze">'+
      esc(c.ex).replace(new RegExp('\\b'+stem+"[a-z']*", 'i'), GAP)
               .replace(GAP,'<u></u>')+'</div>'+
      '<div class="prompt-ja" style="margin-top:10px">'+esc(c.ja)+'</div>';
  }else{
    head = '<div class="row"><div style="flex:1;min-width:0">'+
             '<div class="headword">'+esc(c.head)+
             '<span class="pos">'+esc(c.pos)+'</span></div></div>'+
           speakBtn(c.head)+'</div>';
  }
  $('#sBody').innerHTML = '<div class="qcard fade">'+
    tag(c, mode==='produce'?'思い出す':mode==='cloze'?'文の中':'')+head+
    '<div id="rev"></div></div>';
  $('#sFoot').innerHTML = '<button class="btn" id="show">'+jp('こたえを見る','答えを見る')+'</button>'+
    (!S().me.p.cards[c.id] ? '<button class="known" id="known">'+jp('この単語は もう知っている','この単語はもう知っている')+'</button>' : '');
  bindSay($('#sBody'));
  $('#show').onclick = function(){ revealVocab(c, mode); };
  var k = $('#known');
  if(k) k.onclick = function(){
    TubeSRS.markKnown(S().me.p, c.id);
    S().me.p.newToday = (S().me.p.newToday||0)+1;
    ui().persist(); toast(jp('出題のかんかくを のばしました','出題の間隔を延ばしました')); advance();
  };
}

function revealVocab(c, mode){
  var synRaw = TubeContent.syn(c.head), syn = '';
  if(synRaw){
    var half = synRaw.split('|');
    var chips = function(list, cls){
      return list.split('·').map(function(w){ return w.trim(); }).filter(Boolean)
        .map(function(w){ return '<button class="syn '+cls+'" data-say="'+esc(w)+'">'+esc(w)+'</button>'; })
        .join('');
    };
    syn = '<div class="synbox">'+
      (half[0] && half[0].trim() ? '<div class="synline"><em>≈</em><div class="synchips">'+chips(half[0],'')+'</div></div>' : '')+
      (half[1] && half[1].trim() ? '<div class="synline"><em>↔</em><div class="synchips">'+chips(half[1],'ant')+'</div></div>' : '')+
    '</div>';
  }
  $('#rev').innerHTML = '<div class="reveal">'+
    (mode !== 'recog' ? '<div class="row"><div class="headword" style="flex:1;font-size:28px">'+
      esc(c.head)+'<span class="pos">'+esc(c.pos)+'</span></div>'+speakBtn(c.head)+'</div>' : '')+
    (mode !== 'produce' ? '<div class="def-ja">'+esc(c.ja)+'</div>' : '')+
    '<div class="def-en">'+esc(c.en)+'</div>'+
    '<div class="ex"><div class="ex-en">'+hl(c.ex, c.head)+'</div>'+
      (c.exJa ? '<div class="ex-ja">'+esc(c.exJa)+'</div>' : '')+
      '<div style="margin-top:10px">'+speakBtn(c.ex)+'</div></div>'+
    (c.coll && c.coll.length ? '<div class="colls">'+c.coll.map(function(x){
        return '<button class="coll" data-say="'+esc(x.replace(/\b(sth|sb)\b/g,''))+'">'+esc(x)+'</button>';
      }).join('')+'</div>' : '')+
    syn + (c.note ? '<div class="note">'+c.note+'</div>' : '')+
  '</div>';
  bindSay($('#rev'));
  gradeBar(c);
  if(mode !== 'recog') speak(c.head);
}

/* ---- 選択問題（語法・一問一答） ---- */
/* 図。**教材が名前で指し、絵は content/figures.js が持つ。**

   ここだけ esc を通さずに差し込む。差し込むのは自分たちで生成した
   SVG だけで、生成のときに使ってよいタグと属性を名指しで検査している
   （app/tools/gen_figures.py の check_svg）。
   知らない名前なら**何も出さない** ―― 「図を見て答えなさい」と書いて
   あるのに図が無い、がいちばん困る形なので、そのときは問題ごと出さない
   ようにしたいところだが、教材の取り込み順で一時的に図が無いことも
   あるため、ここでは空にとどめる。取りこぼしは検査が見ている。 */
function figure(c){
  var f = c.fig && window.TubeFigures && TubeFigures[c.fig];
  return f ? '<div class="zu">' + f + '</div>' : '';
}

/* 長文読解の本文。**設問は名前で指し、本文は1つだけ置いてある。**
   1問ごとに本文を抱えさせると、同じ600字が何度も並ぶ。
   改行（\n）は段落に直す。本文は esc を通す ―― 図とちがって
   ただの文章なので、markup として差し込む理由がない。 */
function reading(c){
  var t = c.bun && window.TubeReadings && TubeReadings[c.bun];
  if(!t) return '';
  /* 段落頭の空白は落とす。1字下げは CSS が付ける ――
     そのまま出すと 2マス下がる（青空文庫の本文は頭に全角空白がある）。 */
  return '<div class="bun">' + String(t).split('\n')
    .filter(function(p){ return p.trim(); })
    .map(function(p){
      return '<p>' + esc(p.replace(/^[\u3000\s]+/, '')) + '</p>';
    }).join('') + '</div>';
}

function cardChoice(c){
  var opts = ui().shuffle([c.ans].concat(c.dis || [])).slice(0,4);
  if(opts.indexOf(c.ans) < 0){ opts[0] = c.ans; opts = ui().shuffle(opts); }
  var stem = c.pat || c.q || '';
  $('#sBody').innerHTML = '<div class="qcard fade">'+tag(c)+
    reading(c)+figure(c)+
    '<div class="cloze">'+esc(stem).replace('___','<u></u>')+'</div>'+
    (c.ja ? '<div class="prompt-ja" style="margin-top:10px">'+esc(c.ja)+'</div>' : '')+
    '<div class="opts" id="opts">'+ opts.map(function(o){
        return '<button class="opt" data-o="'+esc(o)+'">'+esc(o)+'</button>';
      }).join('') +'</div><div id="rev"></div></div>';
  $('#sFoot').innerHTML = '';
  $('#opts').querySelectorAll('.opt').forEach(function(b){
    b.onclick = function(){ answerChoice(c, b); };
  });
}

function answerChoice(c, btn){
  var s = S();
  var ok = btn.dataset.o === c.ans;
  $('#opts').querySelectorAll('.opt').forEach(function(b){
    b.disabled = true;
    if(b.dataset.o === c.ans) b.classList.add('right');
    else if(b === btn) b.classList.add('wrong');
  });
  $('#rev').innerHTML = '<div class="reveal">'+
    (c.ex ? '<div class="ex"><div class="ex-en">'+hl(c.ex, c.ans)+'</div>'+
      '<div style="margin-top:10px">'+speakBtn(c.ex)+'</div></div>' : '')+
    (c.note ? '<div class="note">'+c.note+'</div>' : '')+'</div>';
  bindSay($('#rev'));
  /* 正誤が出ているので、4段階は押させない。手数を増やすと続かない。 */
  if(ok) gradeBar(c, [[3,jp('せいかい','正解')],[4,jp('かんたん','簡単')]]);
  else   gradeBar(c, [[1,jp('おぼえなおす','覚え直す')]]);
  if(c.ex) speak(c.ex);
}

/* ---- 文法（説明 → 演習） ---- */
function cardGram(c){
  if(S().me.p.cards[c.id]) return drillGram(c, 0, 0);
  $('#sBody').innerHTML = '<div class="qcard fade">'+tag(c)+
    '<div class="headword" style="font-size:24px">'+esc(c.head)+'</div>'+
    '<div class="prompt-ja">'+esc(c.ja)+'</div>'+
    '<div class="rulebox">'+c.rule+'</div>'+
    ((c.forms||[]).length ? '<div class="forms">'+c.forms.map(function(f){
        return '<div><div class="fl">'+esc(f[0])+'</div><div class="fe">'+esc(f[1])+
               '</div><div class="fj">'+esc(f[2])+'</div></div>';
      }).join('')+'</div>' : '')+
  '</div>';
  $('#sFoot').innerHTML = '<button class="btn" id="gStart">'+jp('もんだいへ（','問題へ（')+
    (c.qs||[]).length+jp('もん）','問）')+'</button>';
  $('#gStart').onclick = function(){ drillGram(c, 0, 0); };
}

function drillGram(c, qi, correct){
  var qs = c.qs || [];
  if(qi >= qs.length) return finishGram(c, correct, qs.length);
  var q = qs[qi];
  var opts = ui().shuffle(String(q[2]).split('|'));
  $('#sBody').innerHTML = '<div class="qcard fade">'+tag(c, (qi+1)+' / '+qs.length)+
    '<div class="cloze">'+esc(q[0]).replace('___','<u></u>')+'</div>'+
    '<div class="opts" id="opts">'+ opts.map(function(o){
        return '<button class="opt" data-o="'+esc(o)+'">'+esc(o)+'</button>';
      }).join('') +'</div><div id="rev"></div></div>';
  $('#sFoot').innerHTML = '';
  $('#opts').querySelectorAll('.opt').forEach(function(b){
    b.onclick = function(){
      var ok = b.dataset.o === q[1];
      $('#opts').querySelectorAll('.opt').forEach(function(x){
        x.disabled = true;
        if(x.dataset.o === q[1]) x.classList.add('right');
        else if(x === b) x.classList.add('wrong');
      });
      $('#rev').innerHTML = '<div class="reveal"><div class="note">'+q[3]+'</div></div>';
      $('#sFoot').innerHTML = '<button class="btn" id="nx">'+
        (qi+1 >= qs.length ? jp('おわり','終わり') : jp('つぎ','次へ'))+'</button>';
      $('#nx').onclick = function(){ drillGram(c, qi+1, correct + (ok?1:0)); };
    };
  });
}

function finishGram(c, correct, total){
  var ratio = total ? correct/total : 1;
  var g = ratio >= 1 ? 4 : ratio >= 0.67 ? 3 : ratio >= 0.34 ? 2 : 1;
  $('#sBody').innerHTML = '<div class="qcard fade">'+tag(c)+
    '<div class="headword" style="font-size:24px">'+correct+' / '+total+'</div></div>';
  $('#sFoot').innerHTML = '<button class="btn" id="nx">'+jp('つぎへ','次へ')+'</button>';
  $('#nx').onclick = function(){ applyGrade(c, g); };
}

/* ---- 宿題（冊子の番号） ---- */
/* My英単語帳の1語。意味を4択から選ぶ。

   自己採点（「おぼえた」を自分で押す）にしない。**押すだけなら誰でも
   押せる**ので、記録が事実と離れていく。選ばせれば、合っていたかどうかが
   アプリの側で分かり、まちがえた語がそのまま「にがて」に残る。 */
/* 品詞。教材は英語の略号（n, v, adj）で持っている。
   **小学生の画面に n とだけ出さない。** 読めない字は無いのと同じ。 */
var POS_JA = {n:'名詞', v:'動詞', adj:'形容詞', adv:'副詞',
              prep:'前置詞', conj:'接続詞', phr:jp('ひとまとまりの言い方','フレーズ'),
              idiom:jp('言いまわし','イディオム'), pron:'代名詞', det:'限定詞'};

function cardHwVocab(item, src, pick){
  var it = pick.item;
  var opts = ui().shuffle([pick.ans].concat(pick.dis));
  $('#sBody').innerHTML = '<div class="qcard fade">'+
    '<div class="qtag"><i></i>'+jp('しゅくだい','宿題')+'<em>'+esc(src.name || src.short)+'</em>'+
      '<em>No.'+item.no+'</em></div>'+
    '<div class="headword" style="margin-top:12px">'+esc(it.head)+'</div>'+
    '<div class="prompt-ja">'+esc(POS_JA[it.pos] || it.pos)+
      jp('　いみは どれ？','　意味はどれ？')+'</div>'+
  '</div>';
  $('#sFoot').innerHTML = '<div class="opts">'+ opts.map(function(o, i){
    return '<button class="opt" data-o="'+i+'">'+esc(o)+'</button>';
  }).join('') +'</div>';

  $('#sFoot').querySelectorAll('.opt').forEach(function(b, i){
    b.onclick = function(){
      var right = opts[i] === pick.ans;
      $('#sFoot').querySelectorAll('.opt').forEach(function(x, k){
        x.disabled = true;
        if(opts[k] === pick.ans) x.classList.add('ok');
        else if(k === i) x.classList.add('ng');
      });
      /* 合っていれば「おぼえた」、まちがえたら「まだ」として記録する。
         SRS の間隔も、この結果で動く。 */
      var s = S();
      TubeHomework.grade(s.me.p, item.a, item.key, right ? 3 : 1);
      ui().persist();
      if(right) s.session.right++;
      else { s.session.wrong++; s.session.queue.push(item); s.session.total++; }
      /* 答えのあとに、例文と意味を短く出す。**まちがえた語ほど要る。** */
      $('#sBody').innerHTML += '<div class="qcard fade" style="margin-top:10px">'+
        '<div class="prompt-ja">'+esc(it.ja)+'</div>'+
        (it.ex ? '<div class="cloze" style="margin-top:8px">'+esc(it.ex)+'</div>' : '')+
        (it.exJa ? '<div class="tiny" style="margin-top:4px">'+esc(it.exJa)+'</div>' : '')+
      '</div>';
      setTimeout(advance, right ? 550 : 1600);
    };
  });
}

function cardHomework(item){
  var a = item.a, src = TubeContent.booklet(a.source);

  /* 番号のうしろに単語が入っている教材（My英単語帳）は、
     **その場で4択にする。** 番号だけ出して「冊子で引いて、思い出せたか
     自分で押す」のは、アプリでやる意味がない ―― 紙を見るなら紙だけでよい。 */
  var pick = TubeContent.bookletChoices
    ? TubeContent.bookletChoices(a.source, item.no) : null;
  if(pick && pick.dis.length >= 3) return cardHwVocab(item, src, pick);

  var known = !!S().me.p.cards[item.id];
  $('#sBody').innerHTML = '<div class="qcard hw-card fade">'+
    '<div class="qtag"><i></i>'+jp('しゅくだい','宿題')+'<em>'+esc(src.name || src.short)+'</em>'+
      (known ? '<em>'+jp('たしかめ','確認')+'</em>' : '')+'</div>'+
    '<div class="hw-no"><span class="lbl">No.</span>'+
      '<span class="num">'+item.no+'</span></div>'+
    '<p class="prompt-ja" style="margin-top:14px">'+
      jp('この ばんごうを 冊子で ひいて、','この番号を冊子で引いて、')+
      jp('いみを思い出してから こたえてください。','意味を思い出してから答えてください。')+'</p></div>';
  var L = [[1,'まだ'],[3,jp('おぼえた','覚えた')],[4,jp('かんたん','簡単')]];
  $('#sFoot').innerHTML = '<div class="grades" style="grid-template-columns:repeat(3,1fr)">'+
    L.map(function(g){
      return '<button class="grade g'+g[0]+'" data-g="'+g[0]+'"><b>'+g[1]+'</b>'+
             '<span>'+TubeSRS.nextIv(S().me.p, item.id, g[0])+'</span></button>';
    }).join('')+'</div>';
  $('#sFoot').querySelectorAll('.grade').forEach(function(b){
    b.onclick = function(){
      var g = +b.dataset.g, s = S();
      TubeHomework.grade(s.me.p, a, item.key, g);
      ui().persist();
      if(g === 1){ s.session.wrong++; s.session.queue.push(item); s.session.total++; }
      else s.session.right++;
      advance();
    };
  });
}

function showDone(){
  var s = S();
  var mins = Math.max(1, Math.round((Date.now() - s.session.started)/60000));
  var tail = '';
  if(s.session.kind === 'test'){
    tail = '<p class="tiny" style="margin-top:20px">'+jp('たしかめテストは','確認テストは')+
           jp('つぎの出題にはひびきません。まちがえたところを','次の出題には影響しません。間違えた所を')+
           jp('もういちど見ておきましょう。','もう一度見ておきましょう。')+'</p>';
  }else if(s.session.kind === 'hw'){
    var pc = TubeHomework.pace(s.me.p, s.session.hw);
    tail = pc.finished
      ? '<p class="tiny" style="margin-top:20px">'+esc(s.session.hw.title)+
        jp(' を ぜんぶ おわりました。先生の画面にもうつります。','をすべて終えました。先生の画面にも表示されます。')+'</p>'
      : '<p class="tiny" style="margin-top:20px">'+jp('のこり ','残り ')+pc.left+'　·　'+
        TubeHomework.dueLabel(s.session.hw)+'</p>';
  }
  $('#sBody').innerHTML = '<div class="qcard fade done-card">'+
    '<div class="done-lbl">'+jp('おつかれさま','お疲れさまでした')+'</div>'+
    '<span class="h-ringwrap big">'+ringSvg(s.session.total ? s.session.right / s.session.total : 0, false)+
      ringC(s.session.right, jp('もん','問'), '')+'</span>'+
    '<div class="done-sub"><span class="num">'+s.session.total+'</span>'+jp('もん中','問中')+'<i>·</i><span class="num">'+mins+'</span>'+jp('ふん','分')+'</div>'+ tail +'</div>';
  $('#sFoot').innerHTML = '<button class="btn" id="dEnd">'+jp('もどる','戻る')+'</button>';
  $('#dEnd').onclick = endSession;
}

/* ============================================================
   きろく ―― カレンダーと、これまでの提出
   ============================================================ */
/* 続き具合をひとつの関数で出す。

   前はここと毎日テストの2か所に別々の計算があり、答えが食い違っていた
   ―― 同じ生徒が「毎日テスト 3日」「きろく 0日」と出ていた。
   きろくのほうは、きょうまだやっていないと必ず 0 になる書き方だった。

   決まりは1つ。**きょう未実施は「途切れた」ではない。**
   まだ1日が終わっていないのに連続を切ると、朝ひらいた生徒に
   「0日」と告げることになる。
     run   … いま続いている日数
     best  … これまででいちばん長い連続
     week  … この7日でやった日数
     days  … 記録のある日数、total … これまでの問題数  */
function streakOf(hist){
  hist = hist || {};
  var days = 0, total = 0;
  Object.keys(hist).forEach(function(k){ days++; total += (hist[k].n || 0); });

  var run = 0;
  for(var i = 0; i < 400; i++){
    if(hist[TubeSRS.dayKey(Date.now() - i*TubeSRS.DAY)]) run++;
    else if(i > 0) break;               // きょう(i=0)の欠けは見のがす
  }

  var best = 0, cur = 0;
  var keys = Object.keys(hist).sort();
  for(var j = 0; j < keys.length; j++){
    if(j && dayGap(keys[j-1], keys[j]) === 1) cur++;
    else cur = 1;
    if(cur > best) best = cur;
  }

  var week = 0;
  for(var q = 0; q < 7; q++){
    if(hist[TubeSRS.dayKey(Date.now() - q*TubeSRS.DAY)]) week++;
  }
  return {run:run, best:Math.max(best, run), week:week, days:days, total:total};
}

/* 日付キー2つの間隔（日）。'2026-08-17' の形だけを受ける。 */
function dayGap(a, b){
  var pa = a.split('-'), pb = b.split('-');
  var ta = Date.UTC(+pa[0], +pa[1]-1, +pa[2]);
  var tb = Date.UTC(+pb[0], +pb[1]-1, +pb[2]);
  return Math.round((tb - ta) / 86400000);
}

/* ============================================================
   先生から ―― 先生のことばと、がんばりの積み上げ
   ------------------------------------------------------------
   前はここが「きろく」だった（連続日数・カレンダー・正答率の表）。数字が並ぶだけで
   やる気にもつながらず、読まれていなかった。本人の判断で作り直し、「先生から」と1つにした。

   講師の手間は増やさない（本人の判断）。**すでにあるもの**だけで、
   「先生が見てくれている」「積み上がっている」が伝わるようにする。
     1. 先生のことば ―― **いちばん前向きな**ひとことを大きく（cheer.words）。直す所のことば
        （もう少し・がんばろう）は大きく出さない ―― 教科の返事の中で読む。前のほめことばも読み返せる
     2. 積み上げ ―― よくできました・終えた週・終わった宿題・続けた日。次の節目まで。
        **0の札は出さない**（「0回 あと1回で1回」は意味が無い）。
        7日のうちに節目を越えた札はお祝いの形にし、いちばん上にも1行で言う
     3. 教科ごとの返事 ―― 押すと、その教科の返事の一覧
   数え方は cheer.js（DOM に触らない関数・検査つき）。ここは並べるだけ。
   ============================================================ */
function cheerData(p, now){
  loadSubs();
  var C = global.TubeCheer;
  var list = C.rows({all:TubeHomework.all(), bundleKey:TubeHomework.bundleKey, head:TubeHomework.head});
  var fin = function(a){ return TubeHomework.finished(p, a); };
  var pr = C.praise(list), wk = C.weeks(list, fin, now), st = streakOf(p.hist || {});
  return {
    words: C.words(list, subs || {}, 6, now),
    tiles: [
      {key:'great', n:pr.great.length, label:jp('たいへん よくできました', '大変よくできました'), unit:'回', hit:C.crossed(pr.great, now)},
      {key:'weeks', n:wk.done, label:jp('今週 おわり', '今週おわり'), unit:'週', hit:C.crossed(wk.times, now),
       sub:wk.run >= 2 ? wk.run + jp('週 つづけて', '週つづけて') : ''},
      {key:'hw', n:list.filter(fin).length, label:jp('おわった 宿題', '終わった宿題'), unit:'件', hit:null},
      {key:'days', n:st.run, label:jp('つづけた 日', '続けた日'), unit:'日',
       hit:(st.run > 0 && C.STEPS.indexOf(st.run) >= 0) ? st.run : null,
       sub:st.best > st.run ? jp('いちばん 長く ', '最長 ') + st.best + '日' : ''}
    ].filter(function(t){ return t.n > 0; })
  };
}

/* 積み上げの札1枚。節目を越えたばかりならお祝いの形、そうでなければ次の節目までの輪。
   お祝いの印は、いまの数が節目そのものなら「達成！」だけ ―― 数は上に大きく出ている（同じ数を2度書かない）。
   節目を越えてさらに進んでいれば（6回で「5回達成」）、節目の数も書く。 */
function cheerTile(t){
  var m = global.TubeCheer.milestone(t.n), gold = t.key === 'great' || !!t.hit;
  return '<div class="h-card ch-tile'+(t.hit ? ' hit' : '')+'">'+
    '<span class="ch-l'+(t.key === 'great' ? ' gold' : '')+'">'+esc(t.label)+'</span>'+
    '<span class="h-ringwrap mini">'+ringSvg(t.hit ? 1 : m.frac, gold)+
      ringC(t.n, esc(t.unit))+'</span>'+
    (t.hit
      ? '<span class="ch-hit">'+(t.hit === t.n ? '' : t.hit+esc(t.unit)+' ')+jp('たっせい！', '達成！')+'</span>'
      : '<span class="ch-next">'+jp('あと ', 'あと')+m.left+esc(t.unit)+jp('で ', 'で')+m.next+esc(t.unit)+(t.sub ? '<br>'+esc(t.sub) : '')+'</span>')+
  '</div>';
}

/* 先生のことば。いちばん前向きなひとことを大きく、その次の2つを小さく（並びは cheer.words）。 */
function wordsCard(ws){
  var head = '<span class="ch-l">'+jp('先生の ことば', '先生のことば')+'</span>';
  if(!ws.length){
    return '<div class="ch-words empty">'+head+
      '<p>'+jp('先生からの ことばが とどくと、ここに 出ます', '先生からのことばが届くと、ここに出ます')+'</p></div>';
  }
  var x = ws[0];
  var retN = (x.s && x.s.returned && x.s.returned.files) ? x.s.returned.files.length : 0;
  return '<div class="ch-words">'+head+
    '<p class="ch-q">'+esc(x.text)+'</p>'+
    '<span class="ch-meta"><span class="ch-sj">'+esc(subjectOfHw(x.a).name)+'</span>'+
      '<span>'+esc(hwDay(x.a))+'</span>'+rateChip(x.v, !!(x.a.rated && x.a.rated.provisional))+'</span>'+
    (retN ? '<button class="btn small up-ret" data-ret="'+esc(x.a.id)+'">'+jp('先生の 赤を 見る', '添削された答案を見る')+'<span class="nobr">（'+retN+jp('まい', '枚')+'）</span></button>' : '')+
    (ws.length > 1 ? '<div class="ch-more">'+ ws.slice(1, 3).map(function(y){
        return '<div class="ch-mq"><span class="ch-sj">'+esc(subjectOfHw(y.a).name)+'</span>'+
          '<span class="ch-mt">'+esc(y.text)+'</span></div>';
      }).join('') +'</div>' : '')+
  '</div>';
}

/* 先生からの節ぜんぶ（タブ「先生から」と、広い画面のホーム）。
   home … ホームの中に置くとき。「続けた日」は上の「自分の記録」の札と同じなので出さない（同じ数字を2か所に書かない）。 */
/* 返ってきたもの ―― まだ見ていない返事（評価・ことば・添削）。見たら、教科の返事にしまわれる。1週間後は自動でしまわれる。 */
function inboxItems(p){
  var seen = p.fbSeen || {}, now = Date.now();
  return returnedItems(p).filter(function(x){
    var has = !!x.note || !!(x.s && x.s.returned && (x.s.returned.files || []).length);   /* 評価だけの宿題は出さない（教科ごとの返事で見える）。10-10 */
    return has && !seen[x.a.id] && (now - x.when) < 7 * 864e5;
  });
}
function inboxCards(p){
  var items = inboxItems(p);
  if(!items.length) return '';
  return '<div class="ch-inbox h-full">'+
    '<span class="ch-inl">'+jp('かえってきたもの ', '返ってきたもの ')+'<b class="num">'+items.length+'</b>件</span>'+
    items.map(function(x){
      var files = (x.s && x.s.returned && x.s.returned.files) || [];
      return '<div class="h-card ch-in'+ui().sjClass(x.sub.id)+'">'+
        '<div class="ch-intop"><span class="h-sj">'+ui().subjIcon(x.sub.id, 18)+esc(x.sub.name)+'</span>'+
          '<span class="ch-day">'+esc(hwDay(x.a))+'</span>'+rateChip(x.v, x.prov)+
          '<span class="ch-new">'+jp('しんちゃく', '新着')+'</span></div>'+
        (x.note ? '<blockquote class="ch-quote">'+esc(x.note)+'</blockquote>' : '')+
        '<span class="ch-title">'+esc(x.a.title)+'</span>'+
        '<div class="ch-inact">'+
          (files.length
            ? '<button class="btn up-ret" data-ret="'+esc(x.a.id)+'" data-fbseen="'+esc(x.a.id)+'">'+jp('先生の 赤を 見る', '添削された答案を見る')+'<span class="nobr">（<span class="num">'+files.length+'</span>'+jp('まい', '枚')+'）</span></button>'
            : '<button class="btn ghost" data-fbseen="'+esc(x.a.id)+'">'+jp('ことばを 見た', 'ことばを見た')+'</button>')+
          '<span class="ch-infoot">'+jp('見たら ', '見たら ')+esc(x.sub.name)+jp('の へんじに しまわれます（1週間後に 自動で しまわれます）', 'の返事にしまわれます（1週間後に自動でしまわれます）')+'</span>'+
        '</div>'+
      '</div>';
    }).join('')+
  '</div>';
}
/* 教科ごとの返事 ―― 直近4週の印（金＝大変よくできました・薄い金＝よくできました・灰＝見ました）と件数。押すとその教科へ。 */
function subjectTabs(p){
  var items = returnedItems(p), now = Date.now();
  var by = {}, order = [];
  items.forEach(function(x){
    var g = by[x.sub.id]; if(!g){ g = by[x.sub.id] = {sub:x.sub, list:[]}; order.push(g); }
    g.list.push(x);
  });
  if(!order.length) return '';
  var mon = weekStart(now), weeks = [3, 2, 1, 0].map(function(i){ return mon - i * 7 * 864e5; });
  return '<div class="h-sect h-full"><h2>'+jp('教科ごとの へんじ', '教科ごとの返事')+'</h2><span>'+jp('直近 ', '直近')+'<span class="num">4</span>週</span></div>'+
    '<div class="ch-subs h-full">'+ order.map(function(g){
      var dots = weeks.map(function(w){
        var best = 0, dw = new Date(w);
        g.list.forEach(function(x){ var t = x.a.assignedAt || x.a.dueAt || 0; if(t >= w && t < w + 7 * 864e5) best = Math.max(best, x.v || 1); });
        return '<span class="ch-dot"><i class="'+(best >= 5 ? 'g' : best >= 4 ? 'lg' : best > 0 ? 'ok' : '')+'"></i>'+
          '<small class="num">'+(dw.getMonth()+1)+'/'+dw.getDate()+'</small></span>';
      }).join('');
      return '<button class="h-card ch-sub'+ui().sjClass(g.sub.id)+'" data-fbsub="'+esc(g.sub.id)+'" aria-label="'+esc(g.sub.name)+' '+g.list.length+'件">'+
        '<span class="ch-subl"><span class="ch-subic">'+ui().subjIcon(g.sub.id, 22)+'</span>'+
        '<span class="ch-subn">'+esc(g.sub.name)+'</span></span>'+
        '<span class="ch-dots">'+dots+'</span>'+
        '<span class="ch-subgo">'+ico('chev', 16, 2.4)+'</span>'+
      '</button>';
    }).join('') +'</div>'+
    '<div class="ch-legend h-full"><span><i class="g"></i>'+jp('たいへん よくできました', '大変よくできました')+'</span><span><i class="lg"></i>'+jp('よくできました', 'よくできました')+'</span><span><i class="ok"></i>'+jp('みました', 'みました')+'</span></div>';
}

function cheerSection(p, now, home){
  var d = cheerData(p, now);
  var tiles = home ? d.tiles.filter(function(t){ return t.key !== 'days'; }) : d.tiles;
  var hits = tiles.filter(function(t){ return t.hit; });
  return pageHead(jp('先生から', '先生から'), '')+
    '<div class="h-grid t-full">'+ noticeCards(true) + inboxCards(p) +
    (hits.length ? '<div class="ch-banner h-full">'+ico('star', 22, 2.2)+'<span>'+ hits.map(function(h){
        return '<span class="nobr">'+esc(h.label)+' <b class="num">'+h.hit+'</b>'+esc(h.unit)+jp(' たっせい！', ' 達成！')+'</span>'; }).join('') +'</span></div>' : '')+
    (tiles.length ? '<div class="ch-tiles h-full n'+tiles.length+'">'+ tiles.map(cheerTile).join('') +'</div>' : '')+
    subjectTabs(p)+
  '</div>';
}

/* 電話のホーム。先生のことば（か、お祝い）を1枚だけ。押すとタブ「先生から」へ。 */
/* タブ「先生から」（電話）。教科の行を押したら、その教科の返事を上から。 */
function viewRecord(m){
  init();
  if(pick.fbSubject) return viewFeedback(m, pick.fbSubject);
  var p = S().me.p;
  m.innerHTML = cheerSection(p, Date.now(), false) + retSheet();
  bindStarts(m);
  bindUpload(m);
  bindNotices(m);
  m.querySelectorAll('[data-fbsub]').forEach(function(x){
    x.onclick = function(){ window.scrollTo(0, 0); pick.fbSubject = x.dataset.fbsub; ui().nav('push'); ui().render(); };
  });
  /* 見た ―― 教科の返事にしまう（この端末の記録。サーバにも同じ記録を送る） */
  m.querySelectorAll('[data-fbseen]').forEach(function(x){
    x.addEventListener('click', function(){
      var id = x.dataset.fbseen;
      p.fbSeen = p.fbSeen || {}; p.fbSeen[id] = Date.now();
      ui().persist();
      if(!x.classList.contains('up-ret')) ui().render();
    });
  });
}

/* ============================================================
   保護者の方へ ―― 生徒のアプリの中の入口（右上のメニュー。本人の判断で合言葉なし）。
   お子さんの記録は**％つき**（生徒には出さない数字をここで）、先生へのメッセージは
   教科を選んでその教科の担当講師へ。返事もここで読む。
   ============================================================ */
var msgs;                       /* {items:[...]}。undefined＝まだ、null＝取りにいっている */
var mgDraft = {subject:'', text:'', busy:false, error:''};
function loadMsgs(){
  var s = S();
  if(msgs !== undefined || !s.srv) return;
  msgs = null;
  s.srv.messages().then(function(g){ msgs = g || {items:[]}; if(!S().session) ui().render(); });
}
function mgDay(t){ var d = new Date((t || 0) * 1000); return (d.getMonth()+1)+'/'+d.getDate(); }
function viewParent(m){
  init();
  var s = S(), p = s.me.p, now = Date.now();
  loadMsgs();
  var subs = (s.me.subjects || []).map(function(x){ return {id:x.subject.id, name:subjectNameOf(x.subject.id, x.subject.name)}; });
  if(!mgDraft.subject && subs.length) mgDraft.subject = subs[0].id;
  var list = (msgs && msgs.items) || [];
  var html = '<div class="h-head t-full"><h1>保護者の方へ</h1>'+
    '<p class="pa-lead">お子さんの記録（数字つき）と、先生へのメッセージです。お子さんの画面には数字を出していません ―― ここは保護者の方が見る所です。</p></div>'+
    '<div class="h-grid t-full">'+ growthTile(true) +
      (dailyAny() ? '<div class="h-card h-3 pa-acc">'+accuracyTile(p)+'</div>' + goalCard(p, now) : '') + stripTile(p, now) +'</div>'+
    '<h2 class="h-h2 t-full" style="margin-top:30px">先生へのメッセージ</h2>'+
    '<div class="h-grid t-full pa-msgs">'+
    '<div class="h-card h-6 pa-form">'+
      '<span class="h-lbl grey">先生へ（要望・相談など）</span>'+
      (subs.length ? '<div class="pa-subs">'+ subs.map(function(x){
          return '<button class="pa-chip'+(mgDraft.subject === x.id ? ' on' : '')+'" data-mgsub="'+esc(x.id)+'" aria-pressed="'+(mgDraft.subject === x.id)+'">'+ui().subjIcon(x.id, 16)+esc(x.name)+'の先生へ</button>';
        }).join('') +'</div>' : '<p class="tiny">アプリを使っている教科がありません。</p>')+
      '<textarea id="mgText" rows="4" maxlength="1000" aria-label="先生へ（要望・相談など）" placeholder="例：家では計算を急いで解いて途中の式を飛ばしがちです。授業でも一言いただけると助かります。">'+esc(mgDraft.text)+'</textarea>'+
      (mgDraft.error ? '<p class="warn tiny">'+esc(mgDraft.error)+'</p>' : '')+
      '<button class="btn" id="mgSend"'+(mgDraft.busy || !subs.length ? ' disabled' : '')+'>'+(mgDraft.busy ? '送っています…' : '先生に送る')+'</button>'+
      '<span class="h-foot left">担当の先生だけが読めます。返事はこの下に届きます。</span>'+
    '</div>'+
    (msgs === null ? '<p class="tiny h-6">よみこんでいます…</p>'
     : list.length ? list.map(function(x){
         var rs = x.replies || [];
         return '<div class="h-card h-6 mg-item'+(rs.length && !(x.seen || {}).parent ? ' fresh' : '')+ui().sjClass(x.subject)+'">'+
           '<div class="h-row"><span class="h-sj">'+ui().subjIcon(x.subject, 18)+esc(subjectNameOf(x.subject, x.subject))+'の先生へ</span><span class="h-foot num">'+esc(mgDay(x.at))+'</span></div>'+
           '<p class="mg-text">'+esc(x.text)+'</p>'+
           (rs.length ? rs.map(function(r){
               return '<div class="mg-reply"><span class="mg-rl">先生からの返事　<span class="num">'+esc(mgDay(r.at))+'</span></span><p>'+esc(r.text)+'</p></div>';
             }).join('') : '<p class="tiny mg-wait">先生が読むと、返事がここに届きます</p>')+
         '</div>';
       }).join('')
     : '<p class="tiny h-6">まだメッセージはありません。</p>')+
    '</div>';
  m.innerHTML = html;
  bindStarts(m);
  bindGoal(m, p);
  m.querySelectorAll('[data-mgsub]').forEach(function(b){
    b.onclick = function(){ mgDraft.subject = b.dataset.mgsub; mgDraft.text = ($('#mgText') || {}).value || ''; ui().keepInPlace(b); ui().render(); };
  });
  var ta = $('#mgText');
  if(ta) ta.oninput = function(){ mgDraft.text = ta.value; };
  var send = $('#mgSend');
  if(send) send.onclick = async function(){
    var text = (($('#mgText') || {}).value || '').trim();
    if(!text){ mgDraft.error = '本文を書いてください'; return ui().render(); }
    mgDraft.busy = true; mgDraft.error = ''; ui().render();
    var r = await s.srv.messagePost(mgDraft.subject, text);
    mgDraft.busy = false;
    if(!r.ok){ mgDraft.error = r.error; return ui().render(); }
    mgDraft.text = ''; msgs = undefined;
    ui().toast('先生に送りました');
    ui().render();
  };
  /* 返事を読んだら既読に（講師の画面の「未読」が消える） */
  list.forEach(function(x){ if((x.replies || []).length && !(x.seen || {}).parent){ x.seen = x.seen || {}; x.seen.parent = true; s.srv.messageSeen(x.id); } });
}

/* 登録してある受講科目の名前（紙のままの教科も入る）。登録が無い口座（前の形）は、アプリで使う教科。 */
function regSubjects(s){
  var reg = s.me.reg || {}, JP = {japanese:'国語', math:'数学', english:'英語', science:'理科', social:'社会'};
  if((reg.subjects || []).length){
    return reg.subjects.map(function(x){ return (x === 'math' && /^e/.test(reg.grade || '')) ? '算数' : (JP[x] || x); });
  }
  return s.me.subjects.map(function(x){ return x.subject.name; });
}
function viewSettings(m){
  init();
  var s = S(), rep = TubeStore.report(), p = s.me.p;
  var cls = (TubeConfig.classOf(s.me.stu.classId) || {name:s.me.stu.classId || ''}).name;
  var subsReg = regSubjects(s), er = pick.erase || '';
  var retN = 0; Object.keys(subs || {}).forEach(function(k){ var g = subs[k]; if(g && g.returned && g.returned.files) retN += g.returned.files.length; });
  m.innerHTML =
    '<div class="h-head t-full"><h1>'+jp('せってい', '設定')+'</h1></div>'+
    '<div class="h-grid t-full st-grid">'+
    '<div class="h-card h-6"><span class="h-lbl grey">'+jp('ほぞんの状態','保存の状態')+'</span>'+
      '<div class="st-ok"><span class="st-okic'+(rep.durable ? '' : ' warn')+'">'+ico(rep.durable ? 'check' : 'bell', 20, 2.4)+'</span><span class="st-okt">'+esc(rep.message)+'</span></div>'+
      '<p class="st-p">'+(s.srv ? jp('サーバにも ほぞんされています。','サーバにも保存されています。')+
                 (s.srv.pending() ? jp('送信まち ','送信待ち ')+s.srv.pending()+'件' : jp('送信まちは ありません。','送信待ちはありません。'))
               : jp('この端末の中だけに ほぞんされています。','この端末の中だけに保存されています。'))+'</p>'+
      '<p class="st-mono">'+esc(rep.detail)+'</p>'+
      '<button class="btn ghost st-btn" id="mExport">'+jp('じぶんのきろくを 書き出す','自分の記録を書き出す')+'</button></div>'+
    '<div class="h-card h-6"><span class="h-lbl grey">'+jp('クラスと ならっている教科','クラスと受講科目')+'</span>'+
      '<span class="st-cls num">'+esc(cls)+'</span>'+
      (subsReg.length ? '<div class="st-subs">'+ subsReg.map(function(nm){
          var id = ({'国語':'japanese','算数':'math','数学':'math','英語':'english','理科':'science','社会':'social'})[nm] || '';
          return '<span class="st-chip'+(id ? ui().sjClass(id) : '')+'">'+(id ? ui().subjIcon(id, 16) : '')+esc(nm)+'</span>';
        }).join('') +'</div>' : '<p class="st-p">'+jp('まだ ありません。','まだありません。')+'</p>')+
      (s.srv ? '<button class="btn ghost st-btn" id="mPlace">'+jp('クラス・教科を かえる','クラス・受講科目を変える')+'</button>'+
               '<p class="st-note">'+jp('じゅくとの けいやくが かわったとき、まちがえて とうろくしたときに。','塾との契約が変わったとき、まちがえて登録したときに。')+'</p>' : '')+
    '</div>'+
    (s.srv && s.srv.eraseReturned ? '<div class="h-card h-6'+(er === 'ask' ? ' st-danger' : '')+'"><span class="h-lbl grey">'+jp('てんさくの データ','添削のデータ')+'</span>'+
      (er === 'ask'
        ? '<p class="st-warn">'+jp('てんさくされた 答案 ','添削された答案 ')+'<span class="num">'+retN+'</span>'+jp('まいを 消します。もとに もどせません。','枚を消します。元に戻せません。')+'</p>'+
          '<p class="st-p">'+jp('先生からの へんじの 画面でも、見られなく なります。','先生からの返事の画面でも、見られなくなります。')+'</p>'+
          '<div class="st-2"><button class="btn" id="mEraseGo">'+jp('消す','消す')+'</button><button class="btn ghost" id="mEraseNo">'+jp('やめる','やめる')+'</button></div>'
        : '<p class="st-p">'+jp('先生が てんさくした 答案を、すべて 消せます。消したあとは、もとに もどせません。','先生が添削した答案を、すべて消せます。消したあとは、もとに戻せません。')+'</p>'+
          '<button class="btn ghost st-btn" id="mErase"'+(retN ? '' : ' disabled')+'>'+jp('てんさくされた 答案を すべて 消す','添削された答案をすべて消す')+(retN ? '（<span class="num">'+retN+'</span>'+jp('まい','枚')+'）' : '')+'</button>')+
      '</div>' : '')+
    '<div class="h-card h-6"><span class="h-lbl grey">ログアウト</span>'+
      '<p class="st-p">'+jp('ほかの人が つかうときは おしてください。','ほかの人が使うときは押してください。')+'</p>'+
      '<button class="btn gold st-btn" id="mOut">'+(s.srv ? 'ログアウト' : jp('べつのコードで入りなおす','別のコードで入り直す'))+'</button></div>'+
    '</div>';

  $('#mExport').onclick = function(){
    downloadText(TubeStore.exportBundle([{student:s.me.stu, progress:s.me.p}]),
      'tube-' + s.me.stu.label + '-' + TubeSRS.dayKey() + '.json');
  };
  $('#mOut').onclick = function(){ ui().signOut(); };
  if($('#mPlace')) $('#mPlace').onclick = function(){ TubeJoin.openPlace(); };
  if($('#mErase')) $('#mErase').onclick = function(){ pick.erase = 'ask'; ui().render(); };
  if($('#mEraseNo')) $('#mEraseNo').onclick = function(){ pick.erase = ''; ui().render(); };
  if($('#mEraseGo')) $('#mEraseGo').onclick = async function(){
    $('#mEraseGo').disabled = true;
    var r = await s.srv.eraseReturned();
    pick.erase = '';
    if(!r || !r.ok){ ui().toast((r && r.error) || jp('消せませんでした','消せませんでした')); return ui().render(); }
    subs = undefined; loadSubs();
    ui().toast(jp('てんさくの データを 消しました','添削のデータを消しました'));
    ui().render();
  };
}

function downloadText(text, name){
  try{
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], {type:'application/json'}));
    a.download = name; a.click();
    setTimeout(function(){ URL.revokeObjectURL(a.href); }, 1000);
    toast('書き出しました');
  }catch(e){ toast('書き出せませんでした'); }
}

/* ============================================================
   音声・小道具
   ============================================================ */
var voice = null;
function pickVoice(){
  if(!global.speechSynthesis) return;
  var want = TubeConfig.voice();
  var vs = speechSynthesis.getVoices();
  voice = vs.filter(function(v){ return v.lang === want; })[0]
       || vs.filter(function(v){ return v.lang.indexOf(want.slice(0,2)) === 0; })[0] || null;
}
if(global.speechSynthesis){ pickVoice(); speechSynthesis.onvoiceschanged = pickVoice; }

function speak(text){
  if(!global.speechSynthesis) return;
  try{
    speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.lang = TubeConfig.voice(); u.rate = .9;
    if(voice) u.voice = voice;
    speechSynthesis.speak(u);
  }catch(e){}
}
function speakBtn(text){
  return '<button class="speak" data-say="'+ui().esc(text)+'" aria-label="'+jp('はつおんを聞く','発音を聞く')+'">&#9654;</button>';
}
function bindSay(root){
  (root||document).querySelectorAll('[data-say]').forEach(function(b){
    b.onclick = function(){ speak(b.dataset.say); };
  });
}
function hl(sentence, head){
  var stem = String(head).split(' ')[0].replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  var re = new RegExp('\\b(' + stem + "[a-z']*)", 'i');
  var out = ui().esc(sentence);
  return out.match(re) ? out.replace(re, '<b>$1</b>') : out;
}

/* 同じ画面で講師と生徒を行き来しても、前の人の控えが次の人に出ないように。
   お知らせ（notices）が前の生徒のまま残り、小5の子に中2のお知らせが出た（09-13）。
   ログイン・ログアウトのたびに ui-core から呼ばれる。 */
function resetSession(){
  notices = undefined; ntAsk = {};
  subs = undefined; pending = {}; upBusy = null; upWord = '';
  msgs = undefined; mgDraft = {subject:'', text:'', busy:false, error:''};
  rank = undefined; growth = undefined; prep = undefined; prepFull = null; lastSheet = undefined;
  hwLoaded = false;
  pick.fbSubject = null; pick.hwFocus = null; pick.hwOpen = {}; pick.hwFinOpen = false; pick.goalSheet = false;
  pick.retSheet = null; pick.retPage = 0;
  try{ TubeHomework.setSubs({}); }catch(e){}
}

global.TubeStudent = {
  resetSession:resetSession,
  /* タブを押しなおしたとき：先生からの返事の詳しい画面・開いた「終わった宿題」を閉じる。 */
  home:function(){ pick.fbSubject = null; pick.hwFocus = null; pick.hwFinOpen = false; },
  dailyOn:dailyAny, kakomonOn:kakomonOn,
  viewToday:viewToday, viewHomework:viewHomework, viewDaily:viewDaily, viewKakomon:viewKakomon,
  viewRecord:viewRecord, viewSettings:viewSettings, viewParent:viewParent,
  renderSession:renderSession, endSession:endSession,
  refreshHomework:refreshHomework, loadCachedHomework:loadCachedHomework, wake:wake,
  startDaily:startDaily, startHomework:startHomework, startUnitTest:startUnitTest
};

})(window);
