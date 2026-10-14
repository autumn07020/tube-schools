/* ============================================================
   講師の画面
   ------------------------------------------------------------
     生徒  … 担当クラスの一覧。続いているか・定着・つまずき
     宿題  … 出す／のばす／取り消す。3手で終わるように作る
     進度  … 学年 × 教科 ごとに、使う教材と1日の量を変える
     管理  … 記録の受け渡し・保存の状態

   講師8人がそれぞれ担当分だけを見る。担当外のクラスは
   画面に出ないし、サーバも返さない（判定はサーバ側）。

   コンピュータが苦手な人が使う前提。数字は入力欄ではなく
   ＋／− のボタンで動かし、保存は1つのボタンにまとめる。
   ============================================================ */
(function(global){
"use strict";

var U = null;
function ui(){ return U || (U = global.TubeUI); }
function S(){ return ui().S; }
var $, esc, toast;
function init(){ var u = ui(); $ = u.$; esc = u.esc; toast = u.toast; }

var rows = null;        // 担当クラスの生徒（サーバから）
var hwRows = null;      // 宿題（サーバから）
var err = null;
var pick = {classId:'all', gradeId:null, subjectId:null, openHw:null,
            sheet:null, stu:null, sugg:null, bookCls:null,
            /* どの束を開いているか。「おわり」は既定で畳む。 */
            hwGrp:null};

/* その講師が見てよいクラス */
function classesOf(profile){
  var all = TubeConfig.classes();
  var allow = profile.classes || [];
  if(allow.indexOf('*') >= 0) return all;
  return all.filter(function(k){ return allow.indexOf(k.id) >= 0; });
}
function myClasses(){ return S().teacher ? S().teacher.classes : []; }
function myGrades(){
  var seen = {}, out = [];
  myClasses().forEach(function(k){ if(!seen[k.grade]){ seen[k.grade]=1; out.push(k.grade); } });
  return out;
}

/* ログイン直後。担当学年で使う教材だけ読み込む。 */
async function afterLogin(){
  rows = null; hwRows = null; err = null;
  pick = {classId:'all', gradeId:myGrades()[0] || null, subjectId:null, openHw:null};
  await TubeContent.loadPacks(TubeConfig.packsForGrades(myGrades()));
}

/* ------------------------------------------------------------
   データの取得
   ------------------------------------------------------------ */
/* 一覧はサーバが作った要約だけを読む。生徒の記録そのものは取りに行かない。

   以前はここで担当生徒の記録を丸ごと受け取っていた。50名で1.3MB、
   300名なら20MBを超え、実際には開けない画面になっていた。
   いまサーバが返すのは1人あたり200バイト程度の要約で、50名で14KB。

   個票を開いたときだけ、その1人の記録を取りに行く（openStudent）。
   速いだけでなく、監査の意味でも正しい ―― 講師が実際に開いた生徒だけが
   audit.log に残る。一覧を眺めただけで全員を「閲覧した」ことにしない。 */
async function loadRows(){
  var s = S();
  if(!s.srv){ rows = []; err = '講師の画面はサーバが要ります'; return; }
  var got = await s.srv.classAll();
  if(got === null){ rows = []; err = 'サーバから名簿を取得できませんでした'; return; }
  err = null;
  rows = got.map(function(r){
    var gradeId = r.grade || r.profile.grade || TubeConfig.gradeOfClass(r.profile.classId);
    return {
      stu:{sid:r.profile.sid, label:ui().labelOf(r.profile), seat:r.profile.seat,
           grade:gradeId, classId:r.profile.classId},
      sum:{
        n:      r.n      || 0,
        mature: r.mature || 0,
        stuck:  r.stuck  || 0,
        /* 理解度のもと。答えた回数のうち、何回できたか。
           ここに写し忘れると、画面は全員「まだ記録なし」になる。 */
        answered: r.answered || 0,
        correct:  r.correct  || 0,
        touched:  r.touched  || 0,
        recent: r.recent || '',
        /* 直近7回の宿題を出したか（1と0）と、直近7日で毎日テストを
           終えた日数。**ここに写し忘れると画面は全員0になる。**
           実際そうなって「毎日テスト実施 0/104」と出た。 */
        hw7:    r.hw7    || [],
        daily7: r.daily7 || 0,
        due:    r.due    || 0,
        overdue:r.overdue|| 0,
        paperDue:r.paperDue || 0,
        /* 紙の評価。付いていなければ 0。0 は「悪い」ではなく「無い」。
           画面はこれが 0 のとき、何も描かないこと。 */
        rated:  r.rated  || 0,
        low:    r.low    || 0,
        streak: r.streak || 0,
        /* アプリで解く宿題の割合。紙が中心の生徒はここが低くなる。
           低いこと自体は悪いことではない ―― 数字を割り引いて読む合図。 */
        share:  (typeof r.share === 'number') ? r.share : 1
      },
      p:null, subjects:null       /* 個票を開いたときに埋める */
    };
  });
}

/* 個票。ここで初めて、その生徒1人分の記録を取りに行く。

   **毎回取り直す。** 一度読んだら使い回していたため、
   生徒が家でやったぶんが画面に出ず「更新されない」状態になっていた。
   1人分は数十KBなので、開くたびに取っても支障はない。 */
async function openStudent(r){
  var s = S();
  var remote = await s.srv.pull(r.stu.sid);
  var gradeId = r.stu.grade;
  r.subjects = TubeConfig.subjectsFor(gradeId).map(function(x){
    return {subject:x.subject, plan:x.plan, order:TubeContent.orderFor(x.plan)};
  });
  r.p = TubeStore.hydrate((remote && remote.blob) || null,
                          r.stu.sid, gradeId, r.stu.classId);
  var all = [];
  r.subjects.forEach(function(x){ all = all.concat(x.order); });
  r.s = TubeSRS.summary(r.p, all, TubeConfig.mature(), TubeConfig.stuckLapses());
  r.notes = (await s.srv.notes(r.stu.sid)) || {};
  return r;
}

/* 要約の recent は「きょうから14日ぶんを1文字ずつ並べた文字列」。
   左端がきょう。'.' は何もしていない日、'1'〜'9' はやった量。

   前は {"2026-08-07": 17, …} という辞書で、日付キーだけで1人180バイト
   あった。300名だと 54KB がキーの文字で埋まる。画面が使うのは
   「その日やったか」と「14日で何日か」だけなので、位置で表す。

   recentFrom（左端の日付）はサーバが決める。端末の時計がずれていても、
   並びは動かない。 */
function dayOn(sum, back){
  var r = sum.recent || '';
  return r.charAt(back) && r.charAt(back) !== '.';
}

/* 直近 span 日のうち、実際に手をつけた日数。 */
function activeDays(sum, span){
  var n = 0;
  for(var d = 0; d < span; d++) if(dayOn(sum, d)) n++;
  return n;
}
/* 宿題の一覧を裏で取り直す。**画面は消さない**（「よみこんでいます」に戻すと、
   開いていた紙が一瞬消え、どこを見ていたか分からなくなる）。 */
function refreshHw(){
  var s = S();
  if(!s.srv) return;
  s.srv.assignments().then(function(got){ if(got){ hwRows = got; ui().render(); } });
}

async function loadHw(){
  var s = S();
  if(!s.srv){ hwRows = []; return; }
  hwRows = (await s.srv.assignments()) || [];
}
function filtered(){
  return (rows||[]).filter(function(r){
    return pick.classId === 'all' || r.stu.classId === pick.classId;
  });
}

function classPicker(id){
  var ks = myClasses();
  return '<select id="'+id+'" class="field" style="margin:0 0 14px">'+
    (ks.length > 1 ? '<option value="all">担当クラス すべて</option>' : '')+
    ks.map(function(k){
      return '<option value="'+k.id+'"'+(pick.classId===k.id?' selected':'')+'>'+
             esc(k.name)+'</option>'; }).join('')+'</select>';
}

/* ============================================================
   今週の格子 ―― 講師の宿題タブの主役

   この画面の値打ちは **空のマスを見せること** にある。
   出してあるものを並べるのは確認にしかならないが、
   出していないマスは行動につながる。紙の管理では見えない情報である。

   格子を開いた時点で、授業日が過ぎた回の宿題はサーバ側で
   すでに発行されている（毎週の作業をゼロにするための作り）。
   ============================================================ */
var grid = undefined;        /* undefined=未取得 / null=取得中 / obj=取得済み */
var openKey = null;          /* 掘り下げて見ている 学年:教科 */
var lplan = null;

/* 宿題の画面で見せる「これからの予定」。学年×教科ごとにためる。
   格子は今週ぶんしか返さないので、先の予定はここで別に取る。 */
var planCache = {};        /* "e4:math" → 予定 / null=取得中 */
/* 毎日テストの中身。クラスを変えると取り直す。 */
var dsets = undefined, dailyCls = null;
/* 総復習テスト対策（講師の見本）。版は講師が切り替えられる。 */
var tprep = undefined, tprepTier = 'advanced';
/* 教材の呼び名。校舎の一覧から引く。 */
function bookName(id){
  var m = ((mat && mat.materials) || []).filter(function(x){ return x.id === id; })[0];
  return (m && (m.short || m.name)) || id;
}
/* にがてを集めて出すときの問題数。既定は10問 ―― 1日で終わる量。 */
var autoCount = 10;
function autoN(){ return Math.max(5, Math.min(40, autoCount)); }

var SUBJ_SHORT = {english:'英語', science:'理科', social:'社会',
                  math:'数学', japanese:'国語'};

function subjName(id){
  var s = TubeContent.subject(id);
  return (s && s.name) || SUBJ_SHORT[id] || id;
}

/* 節の見出し。**日本語だけ**で、中身をそのまま言う短い名前にする
   （2026-09-11 本人：英語を添えてかっこつける必要はない）。講師の画面は漢字で書く。
   right（日付の区切りなど）があれば右端に置く（extra に gridbar）。 */
function sectHead(title, extra, right){
  return '<div class="secthead '+(extra || '')+'">'+
    '<h2>'+esc(title)+'</h2>'+
    (right ? '<div class="wk num">'+esc(right)+'</div>' : '')+
  '</div>';
}

/* コマの右上に置く1文字。算・国・社・理・英・数。

   コマの中で「何の教科か」は、名前を読まなくても分かってほしい。
   1文字だけを大きく右上に置くと、学年（左上）と場所が競合しない。 */
function subjInitial(grade, sub){
  return subjNameFor(grade, sub).charAt(0);
}

/* 学年に合った教科名。小学校では算数、中学校では数学。
   同じ math だが、画面に「小4 数学」と出ると別の教科に見える。 */
function subjNameFor(grade, sub){
  if(sub === 'math' && String(grade || '').charAt(0) === 'e') return '算数';
  return subjName(sub);
}
function slotSubj(sl){
  var cls = TubeConfig.classOf(sl.classId) || {};
  return subjNameFor(cls.grade || sl.grade, sl.subject);
}

/* 宿題の1行。1回に複数のブロック（Sirius21・Jack21）があるときは「｜」でつなぐ。
   サーバの lessons.hw_text と同じ形。 */
function hwText(hw){
  hw = hw || {};
  if(hw.items && hw.items.length)
    return hw.items.map(function(x){ return x.text || ''; }).join('｜');
  return hw.text || '';
}

/* 担当コースの一覧（鍵ごとに1つ）。時間割のコマから作る。
   鍵はコースなら「コースID:教科」、旧来の担当なら「学年:教科」。
   **画面はこの鍵だけで引く。** 学年 × 教科で引くと、中3数学の
   3R と土特のように、同じ学年・教科に並ぶコースを選び分けられない。 */
function myCourses(){
  var seen = {}, out = [];
  mySlots().forEach(function(sl){
    if(!sl.key || seen[sl.key]) return;
    seen[sl.key] = 1;
    out.push({key:sl.key, classId:sl.classId, subject:sl.subject,
              grade:sl.grade || (TubeConfig.classOf(sl.classId) || {}).grade || '',
              name:courseName(sl), app:sl.app !== false,
              /* 導入の段階（0 紙のまま … 4 毎日テストまで）。印の無い古いサーバなら app から */
              use:(typeof sl.use === 'number') ? sl.use : (sl.app !== false ? 4 : 0)});
  });
  return out;
}
/* アプリを使うコースだけ（成績・進度・今日やること）。紙のままのコースは時間割にだけ残る。 */
function appCourses(){ return myCourses().filter(function(c){ return c.app; }); }
function courseApp(key){
  var c = myCourses().filter(function(x){ return x.key === key; })[0];
  return c ? c.app : true;
}
function courseName(sl){
  if(sl.name) return sl.name;
  var cls = TubeConfig.classOf(sl.classId) || {name:sl.classId};
  return cls.name + ' ' + slotSubj(sl);
}
function sheetName(key, cid){
  var c = myCourses().filter(function(x){ return x.key === key; })[0];
  if(c) return c.name;
  var cls = TubeConfig.classOf(cid) || {name:cid};
  return cls.name + ' ' + slotSubj({classId:cid, subject:String(key).split(':')[1]});
}
function slotLabel(sl){
  if(sl.name) return sl.name;          /* コースは名前を持つ（「中2TR 英語」） */
  var cls = TubeConfig.classOf(sl.classId) || {name:sl.classId};
  var g   = TubeConfig.grade(cls.grade || '') || {};
  var tail = g.name ? String(cls.name || '').replace(g.name, '') : '';
  return slotSubj(sl) + tail;
}

function loadGrid(){
  var s = S();
  grid = null;
  s.srv.lessonGrid().then(function(got){
    grid = got || {grid:[], published:[]};
    if((grid.published || []).length){
      toast(grid.published.length + '件の宿題を出しました');
      hwRows = null; rows = null;
    }
    ui().render();
  });
}

/* ============================================================
   今週の時間割 ―― 講師のトップ

   講師は学年をまるごとではなく、**あるクラスのある1教科**を持つ。
   多い人で14コマ。それを学年×教科の表で出すと、
   持っていないマスばかりの大きな空表になり、自分のコマを探すのに
   目が泳ぐ。

   だから「曜日 × その日のコマ」で並べる。**先生の手帳と同じ形**である。
   月曜の欄を見れば、その日に自分が何をするかだけが見える。

   1コマの札に載せるのは3つだけ。
     クラス名（小4β）… いちばん大きく。探すときの手がかり
     教科           … 小さく添える
     いまの状態     … 出した／授業まえ／採点する n

   時刻は出さない。校舎ごとに違ううえ、必要なのは順番だけである。
   ============================================================ */
/* 曜日は日本語の1文字（見出しと同じく、英語で飾らない）。 */
var DAYS = [
  {n:1, label:'月'}, {n:2, label:'火'}, {n:3, label:'水'},
  {n:4, label:'木'}, {n:5, label:'金'}, {n:6, label:'土'}
];

/* 担当のコマ。サーバが profile.assign に入れて返す。 */
function mySlots(){
  var t = S().teacher;
  return (t && t.profile && t.profile.assign) || [];
}

/* そのコマ（クラス×教科）の、いまの様子を格子から引く。 */
function slotState(slot){
  /* **コマの鍵でマスを引く。** サーバが鍵ごとの「今週のマス」（grid.cells）を返す。
     コースは1つの学年・教科にいくつも並ぶ（中3数学なら 3T・3R・土特）ので、
     学年 × 教科の格子では引けない。 */
  var cells = (grid && grid.cells) || {};
  var c = slot.key ? cells[slot.key] : null;
  if(!c) return null;
  /* 数字（手が要る件数・前回の提出）は、クラス（コース）ごとのものに差し替える。
     小4αと小4βを混ぜると、小4βだけを持つ講師の棒に小4αの数字が出る
     （棒を押して開いた一覧が空になったのはこれが原因だった）。 */
  var pr = ((grid && grid.pairs) || {})[slot.classId + '|' + slot.subject];
  return Object.assign({}, c, {late:(pr && pr.late) || 0, last:(pr && pr.last) || null});
}

/* 曜日に添える日（数字だけ）。grid.from はその週の月曜（「2026-09-07」）。 */
function weekDate(from, n){
  var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(from || ''));
  return m ? new Date(+m[1], +m[2] - 1, +m[3] + n - 1).getDate() : '';
}
/* 「2026-09-07」を「9/7」にする（Today の見出しの「9/11 金」と同じ書き方）。 */
function monthDay(s){
  var m = /^\d{4}-(\d{2})-(\d{2})/.exec(String(s || ''));
  return m ? (+m[1]) + '/' + (+m[2]) : String(s || '');
}
/* コマの名前を「クラス」と「教科」に分ける。コース名は末尾に教科が付く
   （「中3 土特（RD特） 数学」→「中3 土特（RD特）」と「数学」）。
   付いていなければ、名前をそのまま上の行に置く。 */
function slotParts(sl){
  var name = courseName(sl), subj = slotSubj(sl);
  var head = (subj && name.length > subj.length && name.slice(-subj.length) === subj)
    ? name.slice(0, -subj.length).trim() : name;
  return {head:head || name, subj:subj};
}

function weekCard(){
  if(grid === null || grid === undefined){
    return '<div class="empty">よみこんでいます…</div>';
  }
  var slots = mySlots();
  if(!slots.length){
    return sectHead('時間割', 'gridbar')+
      '<div class="empty">担当がまだ登録されていません。<br>'+
      '教室長に「クラスと教科」を登録してもらってください。</div>';
  }

  /* 曜日ごとに分ける。曜日の決まっていないコマは最後にまとめる。 */
  var byDay = {}, loose = [];
  slots.forEach(function(sl){
    if(sl.day >= 1 && sl.day <= 6) (byDay[sl.day] = byDay[sl.day] || []).push(sl);
    else loose.push(sl);
  });

  var today = new Date().getDay();          /* 0=日 … 6=土 */
  /* 1日に並ぶコマの最大数。これが格子の段（または列）の数になる ――
     月曜の2コマ目と木曜の2コマ目が、どの幅でも同じ線に乗る（app.css の lane:timetable）。 */
  var most = 1;
  /* 曜日を行にしたときの行の高さ。コマのある日は 1fr（札の高さをそろえる）、
     授業の無い日は中身の高さ（空の大きな帯を作らない）。 */
  var rows = DAYS.map(function(d){ return (byDay[d.n] || []).length ? '1fr' : 'auto'; }).join(' ');
  var cols = DAYS.map(function(d){
    var list = (byDay[d.n] || []).slice().sort(function(a, b){
      return String(a.start || '').localeCompare(String(b.start || '')) ||
             (a.period || 0) - (b.period || 0); });
    if(list.length > most) most = list.length;
    var cards = list.map(function(sl){
      var c = slotState(sl);
      var st = c ? c.state : 'off';
      var cell = (c && c.cell) || {};
      /* 週2回のコースは、同じ週に回が2つある。このコマの曜日の回を出す（火は例題56-57、木は例題58-59）。 */
      var mine = (cell.week || []).filter(function(x){
        var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(x.date || '');
        return m && new Date(+m[1], +m[2] - 1, +m[3]).getDay() === sl.day;
      })[0];
      if(mine) cell = Object.assign({}, cell, mine);
      /* コマに書くのは「いつ・どのクラスの何を・何回目に何をやるか」と前回の理解度だけ。
         クラスと教科は**別の行**にする。1行に詰めると、長いコース名
         （「中3 土特（RD特） 数学」）だけが折り返して、札の高さがそろわない。 */
      var n = cell.n || null;
      var topic = cell.topic || '';
      var p = slotParts(sl), paper = sl.app === false;
      return '<button class="slot s-'+esc(paper ? 'paper' : st)+(paper ? ' paper' : '')+ui().sjClass(sl.subject)+'" '+
          'data-slot="'+esc(sl.classId)+'|'+esc(sl.subject)+'|'+esc(sl.key || '')+'">'+
        '<span class="sl-in">'+
          (sl.start ? '<span class="tm num">'+esc(sl.start)+'</span>' : '')+
          (paper ? '<span class="sl-paper">紙</span>' : '')+
          '<span class="cls"><span class="cn">'+esc(p.head)+'</span> '+
            '<span class="sj">'+esc(p.subj)+'</span></span>'+
          ((n || topic)
            ? '<span class="les">'+(ui().unitName(cell) ? '<span class="no">'+esc(ui().unitName(cell))+'</span> ' : '')+esc(topic)+'</span>'
            : '')+
          /* 前回の単元の理解度（成績タブと同じ数字）。70%未満は黄。授業の冒頭で復習する目安 */
          TubeDesk.slotUnd(sl.key)+
        '</span>'+
      '</button>';
    }).join('');
    var date = weekDate(grid.from, d.n);
    return '<div class="daycol'+(d.n === today ? ' today' : (today >= 1 && d.n < today) ? ' past' : '')+'">'+
      '<div class="dayhead"><span class="d">'+d.label+'</span>'+
        (date ? '<span class="dt num">'+date+'</span>' : '')+'</div>'+
      (cards || '<div class="dayempty">授業なし</div>')+
    '</div>';
  }).join('');

  /* 見出しは secthead に揃える ―― 左の柱まで同じにしないと、
     3つの節のうちここだけ別の部品に見える。 */
  return sectHead('時間割', 'gridbar t-full',
      grid.from && grid.to ? monthDay(grid.from)+' 〜 '+monthDay(grid.to) : '')+
    '<div class="week t-full" style="--n:'+most+'; --rows:'+rows+'">'+cols+'</div>'+
    (loose.length
      ? '<div class="loose t-full"><span class="lbl">曜日みてい</span>'+
        loose.map(function(sl){
          var cls = TubeConfig.classOf(sl.classId) || {name:sl.classId};
          return '<button class="pick" data-slot="'+esc(sl.classId)+'|'+
                 esc(sl.subject)+'|'+esc(sl.key || '')+'">'+
                 esc(courseName(sl))+'</button>'; }).join('')+'</div>'
      : '');
}

/* 呼び名を変えずに残す。中で使っている箇所が多いため。 */
function gridCard(){ return weekCard(); }

/* ------------------------------------------------------------
   掘り下げ ―― その学年×教科の授業計画

   コマ単位の予定が並ぶ。発行済み・これから・遅れの区別が付く。
   「1コマずらす」がここにある。遅れることを前提にしてある。
   ------------------------------------------------------------ */
/* 予定の1行に足す「上位:」の文。上乗せの無い回は空。 */
function topText(l){
  var top = (l.extraHw || {}).top;
  if(!top) return '';
  var its = top.items || (top.text ? [top] : []);
  return its.map(function(x){ return '｜上位:' + (x.text || ''); }).join('');
}

/* 上位の生徒を選ぶ札。コースで、受け取る生徒がいるときだけ出す。
   押しても描き直さない（保存するまでは札の見た目だけ変える）。 */
function topCard(isCourse){
  var rs = (lplan && lplan._receivers) || [];
  if(!isCourse || !rs.length) return '';
  var ex = (lplan.extra || []).filter(function(e){ return e.id === 'top'; })[0] || {};
  var on = {};
  (ex.students || []).forEach(function(s){ on[s] = 1; });
  return '<div class="card"><div class="lbl">上位の生徒</div>'+
    '<p class="tiny" style="margin:8px 0 12px">'+
      '予定に「上位:」で書いた宿題は、ここで選んだ生徒にだけ出ます。'+
      '選び直すと、これから出す回から変わります。</p>'+
    '<div class="picks">'+ rs.map(function(r){
      return '<button class="pick" data-top="'+esc(r.sid)+'" aria-pressed="'+
        (on[r.sid] ? 'true' : 'false')+'">'+
        esc(((TubeConfig.classOf(r.classId) || {}).name || r.classId)+'-'+r.seat)+
        '</button>'; }).join('') +'</div>'+
    '<button class="btn ghost small" id="pTop" style="margin-top:12px">この指名で保存する</button>'+
  '</div>';
}


function planView(m, key){
  var s = S();
  if(lplan === null){
    m.innerHTML = '<div class="empty">よみこんでいます…</div>';
    /* 読み終わる前に別の予定へ移ったら、古い結果は捨てる（違うコースの予定を出さない）。 */
    s.srv.lessonPlan(key).then(function(got){ if(openKey !== key || lplan !== null) return; lplan = got || {}; ui().render(); });
    return;
  }
  var g = key.split(':')[0], sub = key.split(':')[1];
  /* コース（teachers の欄がある計画）は、日付をコースの時間割から振る。
     曜日と期限は画面で選ばせない ―― 選ばせると時間割と食い違う。 */
  var isCourse = Array.isArray(lplan.teachers);
  var ls = lplan.lessons || [];
  /* 日付はこの端末の暦で比べる（toISOString は世界標準時。夏のロンドンでは夜0時台に1日ずれる）。 */
  var today = (function(d){ return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); })(new Date());
  var nextI = -1;
  for(var i=0;i<ls.length;i++){ if(!ls[i].published){ nextI = i; break; } }

  m.innerHTML =
    '<button class="btn ghost small" id="pBack">今週の宿題へもどる</button>'+
    '<div class="gridbar" style="margin-top:14px">'+
      '<h2 style="font-size:22px">'+esc(lplan.name ||
        ((TubeConfig.grade(g) || {name:g}).name + ' ' + subjNameFor(g, sub)))+'</h2>'+
      '<div class="wk">全'+ls.length+'回</div></div>'+
    (ls.length
      ? '<div class="hwlist">'+ ls.map(function(l, i){
          var st = l.published ? '出した'
                 : (l.date && l.date < today) ? 'これから' : '予定';
          return '<div class="lrow'+(l.published?' done':'')+(i===nextI?' next':'')+'">'+
            '<div class="no"><b>'+esc(l.review ? '総' : (ui().unitTick(l) || l.n))+'</b>'+esc((l.date||'').slice(5))+'</div>'+
            '<div class="mid"><div class="topic">'+esc(l.topic||'（未設定）')+'</div>'+
              (hwText(l.hw)
                ? '<div class="hwtxt">'+esc(hwText(l.hw))+'</div>'
                : '<div class="hwtxt">宿題なし</div>')+'</div>'+
            '<div class="st">'+st+'</div></div>';
        }).join('') +'</div>'
      : '<div class="hw-none">まだ予定が入っていません。<br>'+
        '下から、学期ぶんをまとめて入れられます。</div>')+

    (nextI >= 0
      ? '<div class="card" style="margin-top:16px">'+
          '<div class="lbl">授業が遅れたとき</div>'+
          '<p class="tiny" style="margin:8px 0 12px">'+
            esc(ui().unitName(ls[nextI]) || ls[nextI].topic || '')+'から、まとめて後ろにずらします。'+
            '<b>すでに出した宿題は動きません。</b></p>'+
          '<div class="row" style="gap:8px">'+
            '<button class="btn ghost small" data-shift="1">1コマ ずらす</button>'+
            '<button class="btn ghost small" data-shift="2">2コマ</button>'+
          '</div></div>'
      : '')+

    '<div class="card"><div class="lbl">学期ぶんの予定を入れる</div>'+
      '<p class="tiny" style="margin:8px 0 12px">'+
        '1行に1回ぶん。「単元｜宿題」の形で、改行して並べてください。'+
        '宿題が2つ以上あるときは「単元｜宿題｜宿題」と続けます。'+
        (isCourse ? '日付はこのコースの時間割から自動で振ります。'+
                    '上位の生徒だけに足す宿題は「上位:」を付けて続けます（例：比｜p.12-15｜上位:発展 p.20）。'
                  : '日付は開始日と曜日から自動で振ります。')+'</p>'+
      '<div class="row" style="gap:12px">'+
        '<label class="field" style="flex:1"><span class="lbl">開始日</span>'+
          '<input id="pStart" type="date" value="'+esc(lplan.start||'')+'"></label>'+
        (isCourse ? '' :
        '<label class="field" style="flex:1"><span class="lbl">曜日</span>'+
          '<select id="pWd">'+ ['日','月','火','水','木','金','土'].map(function(w,i){
            return '<option value="'+i+'"'+(i===(lplan.weekday||0)?' selected':'')+'>'+w+'</option>';
          }).join('') +'</select></label>'+
        '<label class="field" style="flex:1"><span class="lbl">期限（日後）</span>'+
          '<input id="pDue" inputmode="numeric" value="'+(lplan.dueDays||7)+'"></label>')+
      '</div>'+
      '<textarea id="pRows" style="min-height:150px">'+
        esc(ls.map(function(l){
          return (l.topic||'') + '｜' + hwText(l.hw) + topText(l); }).join('\n'))+
      '</textarea>'+
      '<button class="btn" id="pSave" style="margin-top:12px">この予定で保存する</button>'+
    '</div>'+
    topCard(isCourse);

  var b;
  if((b = $('#pBack'))) b.onclick = function(){ openKey = null; lplan = null; ui().render(); };
  m.querySelectorAll('[data-shift]').forEach(function(x){
    x.onclick = async function(){
      var r = await S().srv.shiftLessons(key, ls[nextI].n, +x.dataset.shift);
      if(!r){ return toast('ずらせませんでした'); }
      toast((r.moved||0)+'回ぶん ずらしました');
      lplan = null; grid = undefined; ui().render();
    };
  });
  m.querySelectorAll('[data-top]').forEach(function(x){
    x.onclick = function(){
      x.setAttribute('aria-pressed', x.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
    };
  });
  if((b = $('#pTop'))) b.onclick = async function(){
    var sids = [].map.call(m.querySelectorAll('[data-top][aria-pressed="true"]'),
                           function(x){ return x.dataset.top; });
    var r = await S().srv.setExtra(key, sids);
    if(!r.ok) return toast(r.error);
    toast('上位を'+sids.length+'人にしました');
    lplan = null; ui().render();
  };
  if((b = $('#pSave'))) b.onclick = async function(){
    var lines = $('#pRows').value.split(/\r?\n/).map(function(t){ return t.trim(); })
                  .filter(Boolean);
    if(!lines.length) return toast('予定が空です');
    var body = {
      start: $('#pStart').value,
      weekday: $('#pWd') ? +$('#pWd').value : 0,
      dueDays: $('#pDue') ? (+$('#pDue').value || 7) : 7,
      classId: (myClasses()[0]||{}).id || '',
      rows: lines.map(function(t){
        var pa = t.split(/[｜|]/).map(function(x){ return x.trim(); });
        var hws = [], tops = [];
        pa.slice(1).forEach(function(x){
          var mk = x.match(/^上位\s*[:：]\s*(.*)$/);
          if(mk){ if(mk[1]) tops.push(mk[1]); } else if(x){ hws.push(x); }
        });
        /* 宿題が2つ以上なら、ブロックに分けて送る（1ブロック＝1宿題）。
           「上位:」の分は、上位の生徒にだけ出す上乗せとして別に送る。 */
        var block = function(list){
          return list.length > 1 ? {items:list.map(function(x){ return {text:x}; })}
                                 : {text:list[0] || ''}; };
        var row = {topic:pa[0] || '', hw:block(hws)};
        if(tops.length) row.extraHw = {top:block(tops)};
        return row;
      })
    };
    var r = await S().srv.setLessons(key, body);
    if(!r.ok) return toast(r.error);
    toast(lines.length + '回ぶん 保存しました');
    lplan = null; grid = undefined; ui().render();
  };
}

/* ============================================================
   生徒
   ============================================================ */
/* 成績タブ ＝ コースの診断（app/js/ui-desk.js）。
   前は在籍クラスごとの棒と「気にかけたい生徒」を並べていた。担当外のクラスまで並び、
   どのクラスにテコ入れが要るか、誰に何をすればよいかが読めなかった。
   担当コース単位で「単元の理解度・提出率 → 生徒 → 個別の宿題」に作り直した。 */
function viewRoster(m){
  init();
  return TubeDesk.viewInsight(m);
}

/* ============================================================
   宿題タブ ―― 今日やること（宿題チェック）と、今週の時間割
   ============================================================
   上から「今日やること」（js/ui-desk.js。数えるのはサーバの /api/today）、
   その下に今週の時間割。コマを押すと授業の紙（予定・ずらす・止める・にがて）。

   前はこの下に、提出の棒・採点の束・今後の予定・手で出す欄を毎回組み立てていたが、
   画面には出していなかった（描かないものを毎回数えていた）。2026-09-11 に外した。
   **採点は宿題チェックのページ（view = 'check'）でだけ行う。** 入口を2つにしない。 */
function viewHomework(m){
  init();
  /* 学期ぶんの予定を開いているときは、そちらを描く。 */
  if(openKey) return planView(m, openKey);
  /* 格子（今週の時間割）はまだ取っていなければ取りに行く。
     このとき、授業日が過ぎた回の宿題がサーバ側で自動発行される。 */
  if(grid === undefined) loadGrid();
  if(!S().srv){ m.innerHTML = '<div class="empty">宿題はサーバが要ります。</div>'; return; }
  var sheet = (pick.sheet && pick.sheet.mode === 'lesson') ? lessonSheet(pick.sheet) : '';
  m.innerHTML = TubeDesk.todayCard() + inboxCard() + gridCard() + sheet;
  TubeDesk.wireToday(m);
  wireInbox(m);
  wireLesson(m);
}

/* 保護者からのメッセージ ―― 担当コースの生徒のぶんだけ（サーバが絞る）。未読を先に。
   返事はその場で書く。宛先の講師は教科の担当（本人の判断）。 */
var inbox;                   /* {items:[...], unread:n} */
var qzTitle = '';            /* 提出箱の名前（書きかけ） */
var mgReply = {};            /* id → 書きかけ */
function loadInbox(){
  if(inbox !== undefined || !S().srv) return;
  inbox = null;
  S().srv.messagesInbox().then(function(g){ inbox = g || {items:[]}; ui().render(); });
}
function inboxCard(){
  loadInbox();
  if(!inbox) return '';
  var items = inbox.items || [], acks = inbox.acks || [];
  if(!items.length && !acks.length) return '';
  var unread = items.filter(function(x){ return !(x.seen || {}).teacher; }).length;
  /* 宿題の変更のお知らせへの返事：生徒が「わかった」（1週間で自動も）／質問が来て止まっているもの */
  var ackHtml = acks.length ? '<div class="mg-acks"><div class="lbl">宿題の変更のお知らせ</div>'+ acks.map(function(a){
      return '<div class="mg-ack'+(a.state === 'asked' ? ' q' : '')+'"><b>'+esc(a.label)+'</b><span class="mg-sj">'+esc(a.course)+'</span>'+
        (a.state === 'asked'
          ? '<span>質問あり：'+esc(a.question || '')+'</span><span class="tiny">返事は上のメッセージから。返すまで、この変更は止まっています</span>'
          : '<span>「わかった」'+(a.auto ? '（1週間で自動）' : '')+' <span class="tiny num">'+esc(mgDayT(a.okAt))+'</span></span><span class="tiny">'+esc(a.text)+'</span>')+
      '</div>';
    }).join('') +'</div>' : '';
  return '<div class="card mg-box t-full">'+
    '<div class="ik-lh"><div class="lbl">'+(items.length ? (items.some(function(x){ return x.from === 'student'; }) ? '保護者・生徒からのメッセージ ' : '保護者からのメッセージ ')+items.length+'件'+(unread ? ' ・ <b class="mg-un">未読 '+unread+'</b>' : '') : '宿題の変更のお知らせ')+'</div></div>'+
    (items.length ? '<div class="mg-grid">'+ items.slice(0, 12).map(function(x){
      var rs = x.replies || [], open = mgReply[x.id] !== undefined;
      return '<div class="mg-row'+((x.seen || {}).teacher ? '' : ' fresh')+'" data-mgid="'+esc(x.id)+'">'+
        '<div class="mg-head"><b>'+esc(x.label || x.sid)+'</b>'+(x.from === 'student' ? '<span class="mg-tag">生徒から・宿題の変更について</span>' : '')+
          '<span class="mg-sj">'+esc(subjName(x.subject))+'</span><span class="tiny num">'+esc(mgDayT(x.at))+'</span></div>'+
        '<p class="mg-text">'+esc(x.text)+'</p>'+
        rs.map(function(r){ return '<div class="mg-reply"><span class="mg-rl">返事 <span class="num">'+esc(mgDayT(r.at))+'</span></span><p>'+esc(r.text)+'</p></div>'; }).join('')+
        (open
          ? '<div class="mg-form"><textarea data-mgta="'+esc(x.id)+'" rows="3" maxlength="600" placeholder="返事を書く">'+esc(mgReply[x.id] || '')+'</textarea>'+
              '<div class="ik-sga"><button class="btn small" data-mgsend="'+esc(x.id)+'">返事を送る</button><button class="lnk" data-mgcancel="'+esc(x.id)+'">やめる</button></div></div>'
          : '<div class="ik-sga"><button class="lnk" data-mgopen="'+esc(x.id)+'">'+(rs.length ? 'さらに返事を書く' : '返事を書く')+'</button>'+
              (!(x.seen || {}).teacher ? '<button class="lnk" data-mgseen="'+esc(x.id)+'">読んだ</button>' : '')+'</div>')+
      '</div>';
    }).join('') +'</div>' : '')+ ackHtml +
  '</div>';
}
function mgDayT(t){ var d = new Date((t || 0) * 1000); return (d.getMonth()+1)+'/'+d.getDate(); }
function wireInbox(m){
  var on = function(sel, fn){ m.querySelectorAll(sel).forEach(function(b){ b.onclick = function(){ fn(b); }; }); };
  on('[data-mgopen]', function(b){ mgReply[b.dataset.mgopen] = ''; ui().keepInPlace(b.closest('.mg-row')); ui().render(); });
  on('[data-mgcancel]', function(b){ delete mgReply[b.dataset.mgcancel]; ui().keepInPlace(b.closest('.mg-row')); ui().render(); });
  m.querySelectorAll('[data-mgta]').forEach(function(t){ t.oninput = function(){ mgReply[t.dataset.mgta] = t.value; }; });
  on('[data-mgseen]', async function(b){
    var id = b.dataset.mgseen;
    await S().srv.messageSeen(id);
    (inbox.items || []).forEach(function(x){ if(x.id === id){ x.seen = x.seen || {}; x.seen.teacher = true; } });
    ui().keepInPlace(b.closest('.mg-row')); ui().render();
  });
  on('[data-mgsend]', async function(b){
    var id = b.dataset.mgsend, text = (mgReply[id] || '').trim();
    if(!text) return ui().toast('返事を書いてください');
    b.disabled = true; b.textContent = '送っています…';
    var r = await S().srv.messageReply(id, text);
    if(!r.ok){ b.disabled = false; b.textContent = '返事を送る'; return ui().toast(r.error); }
    delete mgReply[id];
    (inbox.items || []).forEach(function(x, i){ if(x.id === id) inbox.items[i] = r.item; });
    ui().toast('返事を送りました');
    ui().render();
  });
}


/* 時間割のコマを押すと出る紙 ―― その枠の授業の並び。

   前は別ページへ飛んでいた。押すたびに画面が入れ替わり、
   戻ると時間割の位置を見失う。前後3回ずつだけを紙に出す。
   いま出す回に色が付いていて、そこから
     ・宿題を前後に1回ずらす
     ・宿題を止める
     ・にがてを集めて新しく出す
   が、その場でできる。 */
function lessonSheet(sh){
  var key = sh.key, cid = sh.classId;
  var cls = TubeConfig.classOf(cid) || {name:cid};
  if(planCache[key] === undefined){
    planCache[key] = null;
    S().srv.lessonPlan(key).then(function(got){
      planCache[key] = got || {lessons:[]}; ui().render();
    });
  }
  var pl = planCache[key];
  var head = '<div class="sh-top">'+
      '<div><div class="sh-n">'+esc(sheetName(key, cid))+'</div>'+
        '<div class="sh-s">授業の予定と、出す宿題</div></div>'+
      '<button class="sh-x" data-shut="1" aria-label="とじる">&times;</button>'+
    '</div>';
  if(pl === null){
    return '<div class="shade" data-shut="1"></div>'+
      '<div class="sheet wide" role="dialog" aria-modal="true" data-sk="lesson|'+esc(key)+'">'+head+
      '<div class="sh-body"><p class="tiny">よみこんでいます…</p></div></div>';
  }

  /* 紙のままのコース：予定は見せず、使い始める入口だけ。 */
  if(!courseApp(key)){
    return '<div class="shade" data-shut="1"></div>'+
      '<div class="sheet" role="dialog" aria-modal="true" data-sk="lesson|'+esc(key)+'">'+head+
        '<div class="sh-body ap-start">'+
          '<p><b>このコースは、まだアプリを使っていません。</b></p>'+
          '<p class="tiny">使い始めると、授業計画の宿題がこのクラスの生徒に出て、毎日テストと成績・進度がこのコースでも動きます。'+
            'それまでは、生徒の画面にこの教科は出ません（「紙の宿題」と1行だけ出ます）。</p>'+
          '<div class="ik-sga"><button class="btn" data-appon="'+esc(key)+'">このコースでアプリを使い始める</button>'+
            '<button class="lnk" data-shut="1">まだ紙のまま</button></div>'+
        '</div></div>';
  }
  var ls = (pl.lessons || []).slice().sort(function(a,b){
    return (a.n||0)-(b.n||0); });
  /* **いま出す回**＝まだ出していない いちばん早い回。
     全部出し終えていれば、最後に出した回。 */
  var atI = -1;
  for(var i = 0; i < ls.length; i++){ if(!ls[i].published){ atI = i; break; } }
  if(atI < 0) atI = ls.length - 1;
  /* 前後3回ずつ。端では反対側を足して、いつも同じ数に見せる。 */
  var lo = Math.max(0, Math.min(atI - 3, ls.length - 7));
  var win = ls.slice(Math.max(0, lo), Math.max(0, lo) + 7);

  var rows = win.map(function(l){
    var now = l.n === (ls[atI] || {}).n;
    var out = !!l.published;
    return '<div class="lrow2'+(now?' now':'')+(out?' out':'')+'">'+
      '<span class="pno"><b>'+esc(l.review ? '総' : (ui().unitTick(l) || l.n))+'</b>'+
        esc((l.date||'').slice(5).replace('-','/'))+'</span>'+
      '<span class="pmid"><span class="ptopic">'+
        esc(l.topic || '（単元未設定）')+'</span>'+
        '<span class="phw'+(hwText(l.hw)?'':' none')+'">'+
        esc(hwText(l.hw) || '宿題がまだ入っていません')+'</span></span>'+
      '<span class="lst">'+(out ? '出した' : now ? 'これを出す' : '')+'</span>'+
    '</div>';
  }).join('');

  var cur = ls[atI] || {};
  var n = autoN();
  return '<div class="shade" data-shut="1"></div>'+
    '<div class="sheet wide" role="dialog" aria-modal="true" data-sk="lesson|'+esc(key)+'">'+head+
      '<div class="sh-body">'+
        '<div class="lrows">'+ (rows || '<p class="tiny">予定がありません。</p>') +'</div>'+
        '<p class="lplan"><button class="lnk" data-planpage="'+esc(key)+'">学期ぶんの予定を見る・直す（上位の生徒の指名もここ） →</button></p>'+
        (ls.length
          ? '<div class="lacts">'+
              '<div class="lact-t">'+esc(ui().unitName(cur) || cur.topic || '')+'から、まとめてずらす</div>'+
              '<div class="row" style="gap:8px">'+
                '<button class="btn ghost small" data-lshift="-1">← 1回まえへ</button>'+
                '<button class="btn ghost small" data-lshift="1">1回あとへ →</button>'+
                (hwText(cur.hw)
                  ? '<button class="btn ghost small" data-lstop="'+(cur.n||0)+'">'+
                    'この回の宿題を止める</button>' : '')+
              '</div>'+
              '<div class="lact-t" style="margin-top:18px">提出箱を作る（授業内の小テストなど）</div>'+
              '<p class="tiny">紙のテストや作文を、このコースの生徒全員に「写真で出す」箱として出します。'+
                'オンラインの生徒は写真で、対面の生徒は回収した紙を先生が宿題チェックから取り込みます。'+
                '評価・ひとこと・添削を返すのは宿題と同じです。</p>'+
              '<div class="row qz-form" style="gap:8px; align-items:center; flex-wrap:wrap">'+
                '<input id="qzTitle" maxlength="60" placeholder="例：漢字テスト 第3回" value="'+esc(qzTitle || '')+'">'+
                '<select id="qzDue"><option value="3">3日後まで</option><option value="7" selected>7日後まで</option><option value="14">14日後まで</option></select>'+
                '<button class="btn small" data-quiz="'+esc(key)+'">提出箱を出す</button>'+
              '</div>'+
              '<div class="lact-t" style="margin-top:18px">'+
                'にがてを集めて、新しく出す</div>'+
              '<p class="tiny">この'+esc(cls.name)+'の生徒が'+
                '実際にまちがえた番号を、多い順に集めます。</p>'+
              '<div class="row" style="gap:10px; align-items:center">'+
                '<div class="stepper">'+
                  '<button class="stp" data-autod="-5" aria-label="へらす">−</button>'+
                  '<span class="stpn num">'+n+'</span>'+
                  '<button class="stp" data-autod="5" aria-label="ふやす">＋</button>'+
                '</div>'+
                '<button class="btn small" data-automk="1">'+n+'問 作る</button>'+
              '</div>'+
            '</div>'
          : '')+
      '</div>'+
    '</div>';
}

/* コースでアプリを使う／使わないを切り替える（サーバに書き、手元の担当（assign）にも写す）。 */
async function setCourseApp(key, on, btn){
  if(btn){ btn.disabled = true; btn.textContent = '切り替えています…'; }
  var r = await S().srv.setCourseApp(key, on);
  if(!r.ok){ if(btn){ btn.disabled = false; } return ui().toast(r.error); }
  var t = S().teacher;
  if(t && t.profile && Array.isArray(r.data.assign)) t.profile.assign = r.data.assign;
  else mySlots().forEach(function(sl){ if(sl.key === key) sl.app = !!on; });
  if(window.TubeDesk) TubeDesk.forgetAll();
  grid = undefined; drift = undefined;
  pick.sheet = null;
  ui().toast(on ? 'このコースでアプリを使い始めました。授業計画の宿題が次の授業日から出ます' : 'このコースは紙のままにしました');
  ui().render();
}

/* ============================================================
   導入 ―― コースごとの段階。ワンタッチで切り替える（09-23 本人）

     0 紙のまま       時間割にだけ出る
     1 宿題を出す     授業計画の宿題が生徒の画面に出る。提出は紙で先生に直接。評価は宿題チェックで
     2 写真で提出     生徒がノートの写真で出せる
     3 添削まで       写真に赤を入れて返せる
     4 毎日テストまで 毎日テストもこのコースで動く

   段階は積み上げ。学年ごと・教科ごとにまとめても、1コースずつでも、押した瞬間に保存する。
   スロースタート・部分導入のための画面 ―― 使わない講師には何も要求しない。
   ============================================================ */
var USE_WORDS = ['紙のまま', '宿題を出す', '写真で提出', '添削まで', '毎日テストまで'];
var USE_DESC = ['時間割にだけ出ます', '授業計画の宿題が生徒に出ます。提出と評価は紙のまま',
                '生徒がノートの写真で出せます', '写真に赤を入れて返せます', '毎日テストもこのコースで動きます'];
var SUBJ_ORDER = ['japanese', 'math', 'english', 'science', 'social'];
function useOf(c){ return typeof c.use === 'number' ? c.use : (c.app ? 4 : 0); }
/* はしご ―― 5段。今の段階までを塗る（「上の段階は下を含む」を形で言う）。押した段が新しい段階。
   言葉は列の見出しに1回だけ。行の右端に今の段階の言葉を1つ。cur が -1 は「まちまち」（まとめての行）。 */
function useLadder(keys, cur, label){
  var k = esc(keys.join(','));
  return '<div class="use-lad" role="radiogroup" aria-label="'+esc(label)+'">'+ USE_WORDS.map(function(w, i){
    var cls = 'use-st u'+i+(cur === i ? ' cur' : (i >= 1 && i < cur ? ' on' : ''));
    return '<button type="button" role="radio" aria-checked="'+(cur === i ? 'true' : 'false')+'" class="'+cls+'"'+
           ' title="'+w+'" aria-label="'+esc(label)+'を「'+w+'」にする" data-use="'+k+'|'+i+'"><span>'+(i === 0 ? '紙' : i)+'</span></button>';
  }).join('') +'</div>';
}
function useWord(lv){
  return '<span class="use-word'+(lv < 0 ? ' mix' : ' u'+lv)+'">'+(lv < 0 ? 'まちまち' : USE_WORDS[lv])+'</span>';
}
function useHead(){
  return '<div class="use-hd"><div class="use-c1"></div>'+
    '<div class="use-lad hd">'+ USE_WORDS.map(function(w, i){
      return '<div class="use-st hd u'+i+'"><b>'+w+'</b><i>'+esc(USE_DESC[i])+'</i></div>';
    }).join('') +'</div><div class="use-c3"></div></div>';
}
function sameUse(rows){ var lv = rows.map(useOf); return lv.every(function(x){ return x === lv[0]; }) ? lv[0] : -1; }
function adoptBlock(){
  var gorder = TubeConfig.grades().map(function(g){ return g.id; });
  var cs = myCourses().slice().sort(function(a, b){
    var d = gorder.indexOf(a.grade) - gorder.indexOf(b.grade);
    if(d) return d;
    d = SUBJ_ORDER.indexOf(a.subject) - SUBJ_ORDER.indexOf(b.subject);
    return d || String(a.name).localeCompare(String(b.name), 'ja');
  });
  if(!cs.length) return '<div class="empty t-full">担当しているコースがありません。</div>';
  var on = cs.filter(function(c){ return useOf(c) > 0; }).length;
  var groups = {}, subjects = {};
  cs.forEach(function(c){
    (groups[c.grade] = groups[c.grade] || []).push(c);
    (subjects[c.subject] = subjects[c.subject] || []).push(c);
  });
  var gids = Object.keys(groups).sort(function(a, b){ return gorder.indexOf(a) - gorder.indexOf(b); });
  var sids = Object.keys(subjects).sort(function(a, b){ return SUBJ_ORDER.indexOf(a) - SUBJ_ORDER.indexOf(b); });
  var row = function(name, sub, keys, cur, label, grp){
    return '<div class="use-row'+(grp ? ' grp' : '')+'"><div class="use-name"><b>'+esc(name)+'</b>'+
      (sub ? '<span class="tiny">'+esc(sub)+'</span>' : '')+'</div>'+
      useLadder(keys, cur, label)+ useWord(cur) +'</div>';
  };
  return '<div class="use-wrap t-full">'+
    '<div class="use-lead"><b>'+on+' / '+cs.length+' コースで使っています</b>'+
      '<span>押した段までが動きます（上の段は下を含みます）。押した瞬間に保存され、いつでも戻せます。出した宿題も評価も消えません。</span></div>'+
    useHead()+
    gids.map(function(g){
      var rows = groups[g], gname = gradeNameOf(g);
      return '<section class="use-grp">'+
        row(gname, rows.length+'コース ・ まとめて', rows.map(function(c){ return c.key; }), sameUse(rows), gname+'をまとめて', true)+
        rows.map(function(c){ return row(c.name, '', [c.key], useOf(c), c.name, false); }).join('')+
      '</section>';
    }).join('')+
    (sids.length > 1 && cs.length > 2
      ? '<section class="use-grp">'+
        '<div class="use-row grp"><div class="use-name"><b>教科でまとめて</b><span class="tiny">担当の全学年に効きます</span></div><div></div><div></div></div>'+
        sids.map(function(s){
          var rows = subjects[s], nm = subjNameFor((rows[0] || {}).grade, s);
          return row(nm, rows.length+'コース', rows.map(function(c){ return c.key; }), sameUse(rows), nm+'をまとめて', false);
        }).join('')+'</section>'
      : '')+
  '</div>';
}
function wireAdopt(m){
  m.querySelectorAll('[data-use]').forEach(function(b){
    b.onclick = function(){
      var pa = b.dataset.use.split('|');
      setCourseUse(pa[0].split(','), +pa[1], b);
    };
  });
}
/* 段階を変える（サーバに書き、手元の担当（assign）にも写す）。 */
async function setCourseUse(keys, level, btn){
  if(btn) btn.disabled = true;
  var r = await S().srv.setCourseUse(keys, level);
  if(!r.ok){ if(btn) btn.disabled = false; return ui().toast(r.error); }
  var t = S().teacher;
  if(t && t.profile && Array.isArray(r.data.assign)) t.profile.assign = r.data.assign;
  else mySlots().forEach(function(sl){ if(keys.indexOf(sl.key) >= 0){ sl.use = level; sl.app = level > 0; } });
  if(window.TubeDesk) TubeDesk.forgetAll();
  grid = undefined; drift = undefined;
  pick.sheet = null;
  ui().toast((keys.length > 1 ? keys.length+'コースを' : '')+'「'+USE_WORDS[level]+'」にしました'+
             (level > 0 ? '。次の授業日から宿題が出ます' : ''));
  ui().render();
}

/* 導入の段階 ―― 右上のメニューから。導入と進度のタブの上半分と同じもの。 */
function viewApps(m){
  init();
  m.innerHTML = sectHead('導入の段階', 't-full') + adoptBlock();
  wireAdopt(m);
}

/* 時間割のコマと、授業の紙の中のボタン。 */
function wireLesson(m){
  m.querySelectorAll('[data-appon]').forEach(function(b){
    b.onclick = function(){ setCourseApp(b.dataset.appon, true, b); };
  });
  m.querySelectorAll('[data-planpage]').forEach(function(b){
    b.onclick = function(){ openKey = b.dataset.planpage; lplan = null; pick.sheet = null; ui().render(); };
  });
  /* コマを押すと、その授業の紙を開く。別ページへ飛ばさない ―― 時間割は後ろに残る。 */
  m.querySelectorAll('.slot[data-slot]').forEach(function(b){
    b.onclick = function(){
      var pa = b.dataset.slot.split('|');
      /* 鍵はコマが持っている（コースID:教科 か 学年:教科）。 */
      if(!pa[2]) return;
      /* 別ページへ飛ばさない。紙で開く ―― 時間割は後ろに残る。 */
      pick.sheet = {mode:'lesson', key:pa[2], classId:pa[0]};
      ui().render();
    };
  });
  m.querySelectorAll('[data-shut]').forEach(function(b){
    b.onclick = function(){ pick.sheet = null; ui().render(); };
  });
  /* ---- 授業の紙の中のボタン ---- */
  m.querySelectorAll('[data-lshift]').forEach(function(b){
    b.onclick = async function(){
      var sh = pick.sheet; if(!sh) return;
      var pl = planCache[sh.key] || {};
      var ls = (pl.lessons || []).slice().sort(function(x,y){
        return (x.n||0)-(y.n||0); });
      var at = (ls.filter(function(l){ return !l.published; })[0] || {}).n;
      if(!at) return toast('ずらせる回がありません');
      var by = +b.dataset.lshift;
      b.disabled = true;
      /* **前へ戻すのも「ずらす」で通す。** 別の入口を作ると、
         出した宿題を動かさない決まりが2か所に散らばる。 */
      var r = await S().srv.shiftLessons(sh.key, at, by);
      b.disabled = false;
      if(!r) return toast('ずらせませんでした');
      planCache[sh.key] = undefined; grid = undefined; refreshHw();
      toast(by > 0 ? '1回ぶん あとへずらしました' : '1回ぶん まえへ戻しました');
      ui().render();
    };
  });
  m.querySelectorAll('[data-lstop]').forEach(function(b){
    b.onclick = async function(){
      var sh = pick.sheet; if(!sh) return;
      if(b.dataset.armed !== '1'){
        b.dataset.armed = '1'; b.textContent = 'もう一度おすと止めます'; return;
      }
      b.disabled = true;
      var r = await S().srv.editLesson(sh.key, +b.dataset.lstop, null, '', true);
      b.disabled = false;
      if(!r.ok) return toast(r.error);
      planCache[sh.key] = undefined; grid = undefined;
      toast('この回の宿題を止めました');
      ui().render();
    };
  });
  m.querySelectorAll('[data-autod]').forEach(function(b){
    b.onclick = function(){
      autoCount = Math.max(5, Math.min(40, autoN() + (+b.dataset.autod)));
      ui().render();
    };
  });
  var qt = m.querySelector('#qzTitle');
  if(qt) qt.oninput = function(){ qzTitle = qt.value; };
  m.querySelectorAll('[data-quiz]').forEach(function(b){
    b.onclick = async function(){
      var title = ((m.querySelector('#qzTitle') || {}).value || '').trim();
      if(!title) return toast('提出箱の名前を入れてください（例：漢字テスト 第3回）');
      var days = +((m.querySelector('#qzDue') || {}).value || 7);
      b.disabled = true; b.textContent = '出しています…';
      var r = await S().srv.createQuiz(b.dataset.quiz, title, Date.now() + days * 864e5);
      b.disabled = false; b.textContent = '提出箱を出す';
      if(!r.ok) return toast(r.error);
      qzTitle = '';
      refreshHw(); grid = undefined; pick.sheet = null;
      if(window.TubeDesk) TubeDesk.forgetAll();
      toast('提出箱「'+title+'」を出しました。生徒の宿題に出ます');
      ui().render();
    };
  });
  m.querySelectorAll('[data-automk]').forEach(function(b){
    b.onclick = async function(){
      var sh = pick.sheet; if(!sh) return;
      b.disabled = true; b.textContent = '作っています…';
      var r = await S().srv.autoAssignment(sh.classId, sh.key.split(':')[1],
                                           autoN(), Date.now() + 7*864e5);
      b.disabled = false;
      if(!r.ok){ b.textContent = autoN()+'問 作る'; return toast(r.error); }
      refreshHw(); grid = undefined; pick.sheet = null;
      toast('にがて'+autoN()+'問を出しました');
      ui().render();
    };
  });
}

/* ============================================================
   進度 ―― 学年 × 教科 ごとに、使う教材と1日の量
   ============================================================ */
/* ------------------------------------------------------------
   本部カリキュラムとの進み方

   教材も進度も校舎ごと・講師ごとに変えられるようにしてある。
   そうしないと現場で使えない。ただしその自由には代償があって、
   **「本部からどれだけ離れたか」が誰にも見えなくなる。**
   学期末に「2単元遅れていた」と気づく、という形で表面化する。

   基準が入っていないときは「ズレ無し」と描かないこと。
   分からないものを 0 と出したら、それは嘘になる。
   ------------------------------------------------------------ */
var drift = undefined;      /* undefined=未取得 / null=取得中 / [] =取得済み */

/* ------------------------------------------------------------
   進度タブ ―― 成績タブと同じ組み方

     すべて … 担当コースの札。1枚に3つだけ載せる
              本部基準との差（数そのものを大きく）・毎日テスト・使用教材
     コース … そのコースの 本部基準との差／毎日テスト／使用教材

   **横棒は使わない。** 差は「−1 単元」という数で読む。
   棒の長さで ±3 を表すと、仮の基準なのに精密な計測に見える。

   毎日テストは **学年の設定**（保存すると学年の全員に効く）。
   どの学年のどのクラスに効くかを、札と保存の帯の両方に書く。
   保存していない変更があるときだけ、画面の下に保存の帯を出す。
   ------------------------------------------------------------ */
var pEdits = {};      /* 保存していない毎日テストの変更。"学年:教科" → 1 */
var packMore = {};    /* 出どころで、ほかの学年の教材も出しているか。"学年:教科" → true */
var capHit = {};      /* ＋を押しても1日の持ち時間で増えなかった。"学年:教科:種別" → true */
var matWait = false;  /* 教材の一覧を取りに行っている最中 */

function gradeNameOf(g){ return (TubeConfig.grade(g) || {}).name || g || ''; }

/* 学年の設定が効く範囲。「小4（小4α・小4β・小4K）」 */
function gradeScope(g){
  var ks = TubeConfig.classes().filter(function(k){ return k.grade === g; })
    .map(function(k){ return k.name; });
  return gradeNameOf(g) + (ks.length ? '（' + ks.join('・') + '）' : '');
}

/* 担当コース。成績タブのコースの札と同じ並び（名前順）。 */
function progCourses(){
  return appCourses().slice().sort(function(a, b){
    return String(a.name).localeCompare(String(b.name), 'ja'); });
}

/* 組み分けテスト対策と印刷に使うクラス。
   学年まとめのコース（中1 理科 の "j1"）はクラスの表に無いので、
   その学年の担当クラスの先頭を使う ―― 対策は学年ごとに決まる。 */
function prepClass(c){
  if(TubeConfig.classOf(c.classId)) return c.classId;
  var k = myClasses().filter(function(x){ return x.grade === c.grade; })[0] ||
          TubeConfig.classes().filter(function(x){ return x.grade === c.grade; })[0];
  return k ? k.id : c.classId;
}

/* そのコースの、本部基準との差。
   基準が無いときは 0 と描かない（分からないものを「ズレ無し」と出さない）。 */
function paceOf(c){
  if(!drift) return {st:'wait'};
  /* 教材の予定（シラバス）があるコースは、コースごとの進み具合を使う（学年の本部基準より細かい）。 */
  var cp = drift.courses && drift.courses[c.key];
  if(cp && cp.status === 'ok'){
    var ut = function(u){ return ui().unitText(u); };
    return {st:'ok', syllabus:true, delta:cp.delta, expected:cp.expected, done:cp.done,
            prov:!!cp.provisional, source:cp.source || '',
            missing:(cp.missing || []).map(ut), extra:(cp.extra || []).map(ut),
            next:cp.next ? ut(cp.next) : '', rail:cp.rail || null, current:cp.current || null};
  }
  var d = drift.filter(function(x){ return x.grade === c.grade; })[0];
  if(!d || d.status !== 'ok')
    return {st:'none', msg:(d && d.message) || '本部基準が入っていません'};
  var x = (d.subjects || []).filter(function(s){ return s.subject === c.subject; })[0];
  if(!x) return {st:'none', msg:'この教科は本部基準にありません', prov:!!d.provisional};
  return {st:'ok', delta:x.delta, week:d.week, expected:x.expected, done:x.done,
          prov:!!d.provisional, source:d.source || '',
          missing:x.missing || [],
          extra:(d.extra || []).filter(function(e){ return e.subject === c.subject; })
                               .map(function(e){ return e.unit; })};
}
function deltaText(n){ return n === 0 ? '±0' : (n > 0 ? '+' + n : '−' + (-n)); }
function paceTone(p){ return p.st !== 'ok' ? 'none' : (p.delta < 0 ? 'y' : 'b'); }

/* そのコースの教科の冊子。並びは校舎の一覧のまま ――
   押すたびに行が入れ替わると、いま押した行を見失う。
   このクラスでは使わない版（基本編／応用編のもう片方）は、うすく最後に置く。 */
function booksOf(c){
  if(!mat) return null;
  var ad = mat.adopted;               /* null は「まだ選んでいない」＝ぜんぶ使う */
  var rows = (mat.materials || []).filter(function(x){
    var g = x.grades;
    return x.subject === c.subject && (!g || !g.length || g.indexOf(c.grade) >= 0);
  }).map(function(x){
    return {x:x,
            mine: !x.classes || !x.classes.length || x.classes.indexOf(c.classId) >= 0,
            on: ad === null || ad.indexOf(x.id) >= 0,
            graded: x.graded !== false};
  });
  return rows.filter(function(r){ return r.mine; })
             .concat(rows.filter(function(r){ return !r.mine; }));
}
function bookOn(id){
  return !!mat && (mat.adopted === null || (mat.adopted || []).indexOf(id) >= 0);
}

function fmtQ(v){ return (v % 1) ? v.toFixed(1) : String(v); }
function mdOf(s){ var p = String(s || '').split('-'); return p.length === 3 ? (+p[1]) + '/' + (+p[2]) : String(s || ''); }
function dailyLine(pl){
  var ts = TubeContent.tracksOf(pl.packs || []);
  return ts.map(function(t){
    return TubeContent.trackName(t) + ' ' + fmtQ((pl.daily || {})[t] || 0);
  }).join(' ・ ');
}

function progHead(){
  return sectHead('導入と進度', 'gridbar t-full');
}

/* 成績タブと同じ札の列。遅れているコースに黄の点。 */
function progChips(cs, key){
  return '<div class="picks t-full pg-chips" aria-label="コース">'+
    '<button class="pick" data-pgall="1" aria-pressed="'+(key ? 'false' : 'true')+'">すべて</button>'+
    cs.map(function(c){
      var p = paceOf(c);
      return '<button class="pick'+(p.st === 'ok' && p.delta < 0 ? ' flag' : '')+
        '" data-pgcourse="'+esc(c.key)+'" aria-pressed="'+(c.key === key ? 'true' : 'false')+'">'+
        esc(c.name)+'</button>';
    }).join('') +'</div>';
}

/* ---- すべて ---- */
function progAll(cs){
  if(!drift || !mat)
    return '<div class="empty t-full">担当コースの進度をしらべています…</div>';
  if(!cs.length)
    return '<div class="empty t-full">担当しているコースがありません。</div>';
  var ps = {};
  cs.forEach(function(c){ ps[c.key] = paceOf(c); });
  var late = cs.filter(function(c){ return ps[c.key].st === 'ok' && ps[c.key].delta < 0; }).length;
  var ref = drift.filter(function(d){ return d.status === 'ok'; })[0] || null;
  var syl = null;
  cs.forEach(function(c){ var p = ps[c.key]; if(p.syllabus){ syl = syl || {prov:false}; if(p.prov) syl.prov = true; } });
  var base = syl ? '予定' : '本部基準';
  /* 並びは札の列と同じ（名前の順）。遅れているコースは印と色で示し、並べ替えない ―― 見る場所を毎回変えない。 */
  var order = cs;
  return '<div class="pg-lead t-full">'+
      (late ? '<b>'+base+'より遅れているコース '+late+'</b>'
            : '<b>どのコースも'+base+'どおりか、先に進んでいます</b>')+
      (syl ? '<span>'+(syl.prov ? '<i class="pg-tag y">仮の予定</i>' : '')+'教材の予定のうち、今週までの単元の数で比べています</span>'
       : ref ? '<span>'+(ref.provisional ? '<i class="pg-tag y">仮の基準</i>' : '')+
          '第'+ref.week+'週までの単元数で比べています'+
          (ref.provisional || !ref.source ? '' : '（'+esc(ref.source)+'）')+'</span>' : '')+
      /* 四角の凡例。札の中の単元の列と冊子は、これが無いと何か分からない。 */
      '<span class="pg-key">'+global.TubeViz.railKey()+global.TubeViz.booksKey()+'</span>'+
    '</div>'+
    '<div class="pg-grid t-full">'+ order.map(function(c){ return progCard(c, ps[c.key]); }).join('') +'</div>';
}

function progCard(c, p){
  var V = global.TubeViz;
  var pl = TubeConfig.plan(c.grade, c.subject);
  var used = (booksOf(c) || []).filter(function(r){ return r.mine && r.on; });
  var st = paceWord(p);
  var cur = p.current ? V.unitText(p.current) : '';
  var on = !!(pl && pl.enabled);
  var tracks = on ? TubeContent.tracksOf(pl.packs || []) : [];
  var daily = !on ? '<span class="pg-off">使わない</span>'
            : tracks.length ? tracks.map(function(t){
                return '<span class="pg-chip">'+esc(TubeContent.trackName(t))+' <b class="num">'+fmtQ((pl.daily || {})[t] || 0)+'</b></span>';
              }).join('')
            : '<span class="pg-off">出どころなし</span>';
  var plain = used.filter(function(r){ return !r.graded; }).length;
  var say = c.name+'。'+st.text+(cur ? '。今週 '+cur : '')+'。毎日テスト '+(on ? (dailyLine(pl) || '出どころなし') : '使わない')+
    '。使用教材 '+used.length+'冊（出すだけ '+plain+'）';
  return '<button class="pg-card'+(st.cls === 'y' ? ' flag' : '')+ui().sjClass(c.subject)+'" data-pgcourse="'+esc(c.key)+'" aria-label="'+esc(say)+'">'+
    '<span class="pg-top"><span class="pg-name">'+esc(c.name)+'</span>'+
      (pEdits[c.grade+':'+c.subject] ? '<span class="pg-tag y">未保存</span>' : '')+
      '<span class="pg-st '+st.cls+'">'+esc(st.text)+'</span></span>'+
    /* 行はどれも「見出し＋中身」。単元の列の右に今週の単元名を置く（大きい四角＝この名前、と結びつく）。
       冊子の右には冊数（四角を数えさせない）。 */
    '<span class="pg-row"><span class="pg-rl">単元</span><span class="pg-rv">'+(p.rail ? V.rail(p.rail) : '')+
      '<span class="pg-cur">'+(cur ? esc(cur) : '<span class="pg-off">'+esc(p.msg || '予定の単元がありません')+'</span>')+'</span></span></span>'+
    '<span class="pg-row"><span class="pg-rl">毎日テスト</span><span class="pg-rv">'+daily+'</span></span>'+
    '<span class="pg-row"><span class="pg-rl">教材</span><span class="pg-rv">'+
      V.books(used.map(function(r){ return {name:r.x.name, graded:r.graded}; }))+
      (used.length ? '<span class="pg-bc">'+used.length+'冊'+(plain ? '（出すだけ '+plain+'）' : '')+'</span>' : '')+'</span></span>'+
  '</button>';
}

/* 進み具合のことば。数字は遅れ・先行の単元数だけ。 */
function paceWord(p){
  return p.st !== 'ok' ? {cls:'none', text:(p.st === 'wait' ? 'しらべています' : '基準なし')}
       : p.delta < 0 ? {cls:'y', text:(-p.delta)+'単元おくれ'}
       : p.delta > 0 ? {cls:'b', text:p.delta+'単元先行'}
       :               {cls:'ok', text:'予定どおり'};
}

/* ---- コース ---- */
function progCourse(c){
  return '<div class="pg-back t-full"><button class="lnk" data-pgall="1">← すべてのコース</button></div>'+
    '<div class="pg-chead t-full"><h3>'+esc(c.name)+'</h3></div>'+
    prepCard(c)+
    '<div class="pg-body t-full">'+ paceCard(c) + dailyCard(c) + bookCard(c) +'</div>';
}

/* 予定との差（コースのページ）。ことばと単元の列を大きく、今週・次・未実施を名前で。 */
function paceCard(c){
  var V = global.TubeViz;
  var p = paceOf(c), st = paceWord(p);
  var h = '<section class="pg-panel pg-pace'+(st.cls === 'y' ? ' flag' : '')+'">'+
    '<div class="pg-ph"><h4>'+(p.syllabus ? '教材の予定との差' : '本部基準との差')+'</h4>'+
      (p.prov ? '<span class="pg-tag y">'+(p.syllabus ? '仮の予定' : '仮の基準')+'</span>' : '')+'</div>';
  if(p.st !== 'ok') return h + '<p class="pg-wait">'+esc(p.st === 'wait' ? 'しらべています…' : (p.msg || '基準がありません'))+'</p></section>';
  return h +
    '<div class="pg-st big '+st.cls+'">'+esc(st.text)+'</div>'+
    (p.rail ? V.rail(p.rail) + '<div class="pg-keyrow">'+V.railKey()+'</div>' : '')+
    '<dl class="pg-dl">'+
      (p.current ? '<dt>今週</dt><dd>'+esc(V.unitText(p.current))+'</dd>' : '')+
      (p.next ? '<dt>次</dt><dd>'+esc(p.next)+'</dd>' : '')+
      (p.missing.length ? '<dt class="y">未実施</dt><dd>'+esc(p.missing.join('・'))+'</dd>' : '')+
      (p.extra.length ? '<dt>先行</dt><dd>'+esc(p.extra.join('・'))+'</dd>' : '')+
    '</dl>'+
    (p.prov ? '<p class="pg-src">'+(p.syllabus ? '本部の表・教材の目次が入ると、予定もこの数字も変わります'
                                                : '本部の表が入ると、この数字は変わります')+'</p>'
            : (p.source ? '<p class="pg-src">基準：'+esc(p.source)+'</p>' : ''))+
  '</section>';
}

/* 毎日テスト。**学年の設定。** 今週の出題 → 1日の量 → 出どころ の順に置く。
   何を出すかは記録が決める。講師が触るのは 使うか・量・出どころ の3つだけ。 */
function dailyCard(c){
  var g = c.grade, sub = c.subject, ek = g + ':' + sub;
  var pl = TubeConfig.plan(g, sub);
  var on = !!(pl && pl.enabled);
  var h = '<section class="pg-panel pg-daily'+(on ? '' : ' off')+'">'+
    '<div class="pg-ph"><h4>毎日テスト</h4>'+
      (pEdits[ek] ? '<span class="pg-tag y">未保存</span>' : '')+
      '<button class="pg-sw" role="switch" aria-checked="'+(on ? 'true' : 'false')+'" data-toggle="'+esc(sub)+'">'+
        '<span>'+(on ? '使用する' : '使用しない')+'</span><i aria-hidden="true"></i></button>'+
    '</div>'+
    '<p class="pg-scope">'+esc(gradeScope(g))+'の設定</p>';
  if(!on) return h + '</section>';

  /* 今週なにが出るか。返事に行が無い教科は「出題なし」（しらべ中のまま止めない）。 */
  var sets = (dailyCls === c.key) ? dsets : undefined;
  var setsHtml = (sets === undefined || sets === null)
    ? '<p class="pg-wait">しらべています…</p>'
    : !sets.length
      ? '<div class="pg-none">今週の出題はまだありません</div>'
      : '<div class="pg-sets">'+ sets.map(function(st){
          var body = st.kind === 'week'
            ? (st.n ? esc(bookName(st.source))+' '+esc(st.from)+'–'+esc(st.to)+' から <b class="num">'+esc(st.n)+'</b>問'
                    : 'ノートの教材の回（アプリの問題なし）')
            : '<b class="num">'+esc(st.n)+'</b>問 ・ 生徒ごとに違う';
          return '<div class="pg-set k-'+esc(st.kind)+'"><span class="pg-st">'+esc(st.title)+'</span>'+
            '<span class="pg-sb">'+(st.unit ? esc(st.unit)+' ・ ' : '')+body+'</span></div>';
        }).join('') +'</div>';

  var chosen = pl.packs || [];
  var tracks = TubeContent.tracksOf(chosen);
  var capped = tracks.some(function(t){ return capHit[ek + ':' + t]; });
  var amount = !tracks.length ? '' :
    '<div class="pg-sl">1日の量</div><div class="pg-steps">'+ tracks.map(function(t){
      var v = (pl.daily || {})[t] || 0, nm = TubeContent.trackName(t);
      return '<div class="pg-step"><span class="pg-stl">'+esc(nm)+'</span>'+
        '<button class="pg-stp" data-daily="'+esc(sub)+'|'+esc(t)+'|-1" aria-label="'+esc(nm)+'を減らす"'+
          (v <= 0 ? ' disabled' : '')+'>−</button>'+
        '<span class="pg-sv"><b class="num">'+fmtQ(v)+'</b><i>問</i></span>'+
        '<button class="pg-stp" data-daily="'+esc(sub)+'|'+esc(t)+'|1" aria-label="'+esc(nm)+'を増やす"'+
          (v >= 50 || capHit[ek + ':' + t] ? ' disabled' : '')+'>＋</button>'+
      '</div>';
    }).join('') +'</div>'+
    (capped ? '<p class="pg-cap">1日の持ち時間の上限です</p>' : '');

  /* 出どころ。**この学年の教材だけを出す。** 全学年ぶん（国語なら36）を並べると、
     どれを使っているのか読めない。選んである教材は学年に関係なく出す。 */
  var packs = TubeContent.packList(sub);
  var gname = gradeNameOf(g);
  var gnames = TubeConfig.grades().map(function(x){ return x.name; });
  var near = function(pk){
    var b = pk.bands || [];
    return chosen.indexOf(pk.id) >= 0 || !b.length || b.indexOf(gname) >= 0 ||
           !b.some(function(n){ return gnames.indexOf(n) >= 0; });
  };
  var hidden = packs.filter(function(pk){ return !near(pk); }).length;
  var shown = packs.filter(function(pk){ return packMore[ek] || near(pk); });
  var src = !packs.length ? '' :
    '<div class="pg-sl">出どころ</div>'+
    '<div class="picks pg-packs">'+ shown.map(function(pk){
      var sel = chosen.indexOf(pk.id) >= 0;
      /* 最後の1つは外せない。空にすると既定の教材に戻り、押した札が消えずに増えて見える。 */
      var only = sel && chosen.length === 1;
      return '<button class="pick" data-pack="'+esc(sub)+'|'+esc(pk.id)+'" aria-pressed="'+(sel ? 'true' : 'false')+'"'+
        (only ? ' disabled title="出どころは1つ以上"' : '')+'>'+esc(pk.name)+'</button>';
    }).join('') +'</div>'+
    (hidden ? '<button class="lnk pg-more" data-pgmore="'+esc(ek)+'">'+
      (packMore[ek] ? 'ほかの学年の教材をしまう' : 'ほかの学年の教材 '+hidden)+'</button>' : '');

  return h +
    '<div class="pg-sl">今週の出題</div>'+ setsHtml +
    amount + src +
  '</section>';
}

/* 使用教材。1冊に1つの切り替え ―― 採点する／出すだけ／使わない。
   使うか使わないかはこの講師の一覧だけ、採点するかは校舎の全講師に効く。 */
function bookCard(c){
  var rows = booksOf(c);
  var cls = TubeConfig.classOf(c.classId);
  var h = '<section class="pg-panel pg-books"><div class="pg-ph"><h4>使用教材</h4>'+
    '<span class="pg-tag">'+esc(cls ? cls.name : gradeNameOf(c.grade))+'</span></div>';
  if(!rows) return h + '<p class="pg-wait">しらべています…</p></section>';
  if(!rows.length) return h + '<div class="pg-none">この教科の教材は登録されていません</div></section>';
  return h + '<div class="pg-brows">'+ rows.map(function(r){
    var x = r.x;
    var mode = x.mode === 'app' ? 'アプリ' : 'ノート';
    if(!r.mine)
      return '<div class="pg-brow other"><span class="pg-bn"><span>'+esc(x.name)+'</span>'+
        '<span class="pg-bm">ほかのクラス用</span></span></div>';
    var st = !r.on ? 'off' : (r.graded ? 'graded' : 'plain');
    return '<div class="pg-brow'+(r.on ? '' : ' off')+'">'+
      '<span class="pg-bn"><span>'+esc(x.name)+'</span><span class="pg-bm">'+mode+'</span></span>'+
      '<span class="pg-seg" role="group" aria-label="'+esc(x.name)+'">'+
        '<button class="g" data-graded="'+esc(x.id)+'|1" aria-pressed="'+(st === 'graded')+'">採点する</button>'+
        '<button data-graded="'+esc(x.id)+'|0" aria-pressed="'+(st === 'plain')+'">出すだけ</button>'+
        '<button class="n" data-book="'+esc(x.id)+'" aria-pressed="'+(st === 'off')+'">使わない</button>'+
      '</span></div>';
  }).join('') +'</div>'+
  '<p class="pg-src">採点する／出すだけ は校舎の全講師で共通です</p></section>';
}

/* 組み分けテスト対策。近いときだけ、コースの先頭に出す。
   **講師にも同じものが見えていないと、生徒に説明できない。**
   出す版は生徒ごとに決まる。ここで選ぶのは印刷する見本の版。 */
function prepCard(c){
  if(!tprep) return '';
  return '<section class="pg-prep t-full">'+
    '<div class="pg-prep-top">'+
      '<div class="pg-prep-when">'+
        '<span class="pg-prep-l">組み分けテスト対策</span>'+
        '<span class="pg-prep-n"><i>あと</i><b class="num">'+esc(tprep.left)+'</b><i>日</i></span>'+
        '<span class="pg-prep-s">'+esc(mdOf(tprep.exam && tprep.exam.date))+' ・ 1教科60分 ・ 合計 '+esc(tprep.minutes)+'分</span>'+
      '</div>'+
      '<div class="pg-prep-tier"><span class="pg-ul">見本の版</span><span class="pg-seg">'+
        ['advanced', 'basic'].map(function(t){
          return '<button data-ptier="'+t+'" aria-pressed="'+(tprepTier === t ? 'true' : 'false')+'">'+
            (t === 'advanced' ? '上位編' : '基本編')+'</button>'; }).join('')+
      '</span></div>'+
    '</div>'+
    '<div class="pg-prows">'+ (tprep.sets || []).map(function(x){
      return '<button class="pg-prow'+(x.subject === c.subject ? ' me' : '')+'" data-psheet="'+esc(x.subject)+'">'+
        '<span class="pg-pn">'+esc(subjNameFor(c.grade, x.subject))+'</span>'+
        '<span class="pg-pq">アプリ '+esc(x.n)+'問 ・ '+esc(x.minutes)+'分</span>'+
        '<span class="pg-pgo">紙に印刷 '+esc(x.paperN || 0)+'問 →</span>'+
      '</button>';
    }).join('') +'</div>'+
  '</section>';
}

/* 保存の帯。**変更があるときだけ出す。** 何がどこに効くかを帯に書く。 */
function saveBar(){
  if(!TubeConfig.isDirty()) return '';
  var byG = {}, order = [];
  Object.keys(pEdits).forEach(function(k){
    var a = k.split(':');
    if(!byG[a[0]]){ byG[a[0]] = []; order.push(a[0]); }
    byG[a[0]].push(subjNameFor(a[0], a[1]));
  });
  var what = order.length
    ? order.map(function(g){ return gradeScope(g)+' '+byG[g].join('・'); }).join('、')+' の毎日テスト'
    : '毎日テストの設定';
  return '<div class="pg-save t-full">'+
    '<span class="pg-sdot" aria-hidden="true"></span>'+
    '<span class="pg-stext"><b>未保存</b><span>'+esc(what)+'</span></span>'+
    '<button class="btn" id="pSave">保存して反映</button>'+
  '</div>';
}

/* 開いているコースの 今週の出題 と 組み分けテスト対策 を取りに行く。
   dailyCls には「いま dsets を持っているコースの鍵」を入れる。 */
function loadCourseProgress(c){
  if(dailyCls !== c.key){ dailyCls = c.key; dsets = undefined; tprep = undefined; }
  var key = c.key;
  pick.bookCls = prepClass(c);
  if(dsets === undefined){
    dsets = null;
    S().srv.dailySets(c.classId, c.subject).then(function(rs){
      if(dailyCls !== key) return;
      /* 出題の無い教科は、返事に行そのものが無い。**無ければ空。**
         行を待ち続けると「しらべています…」のまま止まる（前はそうなっていた）。 */
      var got = [];
      (rs || []).forEach(function(r){ if(r && r.subject === c.subject) got = r.sets || []; });
      dsets = got;
      ui().render();
    });
  }
  if(tprep === undefined && pick.bookCls){
    tprep = null;
    S().srv.prepFor(pick.bookCls, tprepTier).then(function(got){
      if(dailyCls !== key) return;
      tprep = got || null;
      ui().render();
    });
  }
}

/* 冊子を使う／使わない。**校舎からは消さない** ―― 消えるのはこの講師の一覧からだけ。 */
async function adoptBook(id, want){
  var all = (mat.materials || []).map(function(x){ return x.id; });
  var ad = mat.adopted === null ? all.slice() : (mat.adopted || []).slice();
  var i = ad.indexOf(id);
  if(want && i < 0) ad.push(id);
  if(!want && i >= 0) ad.splice(i, 1);
  mat.adopted = ad;
  ui().render();
  var ok = await S().srv.adoptMaterials(ad);
  if(!ok){ mat = null; toast('保存できませんでした'); ui().render(); }
  return ok;
}

function viewProgress(m){
  init();
  var s = S();
  if(!s.srv){ m.innerHTML = '<div class="empty t-full">進度の変更はサーバが要ります。</div>'; return; }

  /* 本部カリキュラムとの差。開いたときに1回だけ取りに行く。 */
  if(drift === undefined){
    drift = null;
    s.srv.drift().then(function(got){ drift = got || []; ui().render(); });
  }
  /* 冊子の一覧。取りに行っている間は、描き直しでもう一度頼まない。 */
  if(!mat && !matWait){
    matWait = true;
    s.srv.materialsAll().then(function(got){
      matWait = false;
      mat = got || {materials:[], adopted:null};
      ui().render();
    });
  }

  var cs = progCourses();
  var c = cs.filter(function(k){ return k.key === pick.progKey; })[0] || null;
  if(!c) pick.progKey = null;
  if(c) loadCourseProgress(c);

  /* 上半分は導入（コースごとの段階・ワンタッチ）、下半分は進度と教材。コースを選んでいる間は進度だけ。 */
  m.innerHTML = progHead() +
    (c ? '' : adoptBlock() + '<div class="pg-sub t-full"><h3>進度と教材</h3></div>') +
    progChips(cs, c ? c.key : null) +
    (c ? progCourse(c) : progAll(cs)) + saveBar();
  if(!c) wireAdopt(m);
  wireProgress(m, c);
}

function wireProgress(m, c){
  /* 狭い画面では札の列が横に流れる。選んでいる札を見える所へ。 */
  var row = m.querySelector('.pg-chips'), cur = row && row.querySelector('[aria-pressed="true"]');
  if(row && cur && row.scrollWidth > row.clientWidth)
    row.scrollLeft += cur.getBoundingClientRect().left - row.getBoundingClientRect().left - 20;

  m.querySelectorAll('[data-pgall]').forEach(function(b){
    b.onclick = function(){ pick.progKey = null; window.scrollTo(0, 0); ui().render(); };
  });
  m.querySelectorAll('[data-pgcourse]').forEach(function(b){
    b.onclick = function(){ pick.progKey = b.dataset.pgcourse; window.scrollTo(0, 0); ui().render(); };
  });

  var save = m.querySelector('#pSave');
  if(save) save.onclick = async function(){
    save.disabled = true;
    var r = await S().srv.putCurriculum(TubeConfig.snapshot());
    if(!r.ok){ save.disabled = false; return toast(r.error || '保存できませんでした'); }
    TubeConfig.adopt(r.curriculum);
    TubeConfig.markSaved();
    pEdits = {}; capHit = {};
    dsets = undefined;          /* 1日の量が変わると、今週の出題の問題数も変わる */
    rows = null;
    toast('保存しました。生徒の画面に反映されます');
    ui().render();
  };

  if(!c) return;
  var g = c.grade;
  var edited = function(sid){
    var ek = g + ':' + sid;
    pEdits[ek] = 1;
    Object.keys(capHit).forEach(function(k){ if(k.indexOf(ek + ':') === 0) delete capHit[k]; });
  };

  m.querySelectorAll('[data-toggle]').forEach(function(b){
    b.onclick = function(){
      var sid = b.dataset.toggle, cur = TubeConfig.plan(g, sid);
      TubeConfig.setPlan(g, sid, {enabled: !(cur && cur.enabled)});
      edited(sid);
      ui().render();
    };
  });
  m.querySelectorAll('[data-pack]').forEach(function(b){
    b.onclick = async function(){
      var a = b.dataset.pack.split('|'), sid = a[0], pid = a[1];
      var cur = TubeConfig.plan(g, sid) || {packs:[], bands:[], tracks:[], daily:{}};
      var packs = (cur.packs || []).slice();
      var i = packs.indexOf(pid);
      if(i >= 0) packs.splice(i, 1); else packs.push(pid);
      if(!packs.length) return;       /* 最後の1つは外さない（札も押せなくしてある） */
      await TubeContent.loadPacks(packs);
      /* 教材を変えたら、帯と種別はその教材にあるものへ寄せ直す。
         古い帯が残ると「0問」になって理由が分からなくなる。 */
      var bands = TubeContent.bandsOf(packs);
      var tracks = TubeContent.tracksOf(packs);
      var daily = {};
      tracks.forEach(function(t){ daily[t] = (cur.daily || {})[t] || (t === 'gram' ? 0.5 : 6); });
      TubeConfig.setPlan(g, sid, {packs:packs, bands:bands, tracks:tracks, daily:daily});
      edited(sid);
      ui().render();
    };
  });
  m.querySelectorAll('[data-daily]').forEach(function(b){
    b.onclick = function(){
      var a = b.dataset.daily.split('|'), sid = a[0], t = a[1], d = +a[2];
      var before = TubeConfig.plan(g, sid);
      var wasDirty = TubeConfig.isDirty();
      var daily = Object.assign({}, before.daily);
      var step = (t === 'gram') ? 0.5 : 1;
      daily[t] = Math.max(0, Math.min(50, (daily[t] || 0) + d * step));
      TubeConfig.setPlan(g, sid, {daily:daily});
      /* 1日の持ち時間を越える量は、plan() が全体を縮めて収める。
         そのままだと＋を押しても数が増えない（ほかの種別が減ることさえある）。
         **押す前の量に戻し、＋を止めて上限だと示す。** */
      var after = TubeConfig.plan(g, sid).daily;
      var kept = Object.keys(daily).every(function(k){ return (after[k] || 0) === (daily[k] || 0); });
      if(d > 0 && !kept){
        TubeConfig.setPlan(g, sid, {daily:before.daily});
        if(!wasDirty) TubeConfig.markSaved();
        capHit[g + ':' + sid + ':' + t] = true;
      } else {
        edited(sid);
      }
      ui().render();
    };
  });
  m.querySelectorAll('[data-pgmore]').forEach(function(b){
    b.onclick = function(){ var k = b.dataset.pgmore; packMore[k] = !packMore[k]; ui().render(); };
  });

  /* 使わない。すでに使っていなければ何もしない（選ばれている段）。 */
  m.querySelectorAll('[data-book]').forEach(function(b){
    b.onclick = function(){
      var id = b.dataset.book;
      if(bookOn(id)) adoptBook(id, false);
    };
  });
  /* 採点する／出すだけ。使っていない冊子なら、先に使う側へ戻す。
     **採点するかは校舎の原本に書く** ―― 全講師に効く。 */
  m.querySelectorAll('[data-graded]').forEach(function(b){
    b.onclick = async function(){
      var pa = b.dataset.graded.split('|'), id = pa[0], on = pa[1] === '1';
      if(!mat) return;
      if(!bookOn(id) && !(await adoptBook(id, true))) return;
      var row = ((mat && mat.materials) || []).filter(function(x){ return x.id === id; })[0];
      if(!row || (row.graded !== false) === on) return;
      row.graded = on;
      ui().render();
      var ok = await S().srv.setGraded(id, on);
      if(!ok){ mat = null; toast('保存できませんでした'); ui().render(); }
      else toast(on ? '採点する宿題にしました' : '出すだけの宿題にしました');
    };
  });

  m.querySelectorAll('[data-ptier]').forEach(function(b){
    b.onclick = function(){
      if(tprepTier === b.dataset.ptier) return;
      tprepTier = b.dataset.ptier; tprep = undefined; ui().render();
    };
  });
  m.querySelectorAll('[data-psheet]').forEach(function(b){
    b.onclick = function(){
      var t = (S().srv && S().srv.token && S().srv.token()) || '';
      window.open('/api/assignments/prep/sheet?classId='+
        encodeURIComponent(pick.bookCls || '')+'&subject='+
        encodeURIComponent(b.dataset.psheet)+'&tier='+
        encodeURIComponent(tprepTier)+'&t='+encodeURIComponent(t), '_blank');
    };
  });
}

/* ============================================================
   管理
   ============================================================ */
function viewAdmin(m){
  init();
  var s = S(), rep = TubeStore.report(), d = TubeContent.diagnostics();
  m.innerHTML =
    '<div class="card"><div class="lbl">担当</div>'+
      '<div class="picks" style="margin-top:10px">'+ myClasses().map(function(k){
        return '<span class="pick" aria-pressed="true">'+esc(k.name)+'</span>';
      }).join('') +'</div>'+
      '<p class="tiny" style="margin-top:10px">担当外のクラスは表示されず、'+
        'サーバからも返りません。担当を変えるにはMac側で:<br>'+
        '<code>python3 tube_server.py add … --teacher --classes j1a,j2a</code></p></div>'+

    '<div class="card"><div class="lbl">記録の受け渡し</div>'+
      '<button class="btn ghost small" id="aExp" style="width:100%;margin-top:12px">'+
        'この端末の記録を書き出す</button></div>'+

    '<div class="card"><div class="lbl">教材</div>'+
      '<p class="tiny" style="margin-top:8px">'+
        d.packs.map(function(p){
          var sub = TubeContent.subject(p.subject);
          return esc(sub.name)+' / '+esc(p.name);
        }).join('<br>') +'</p>'+
      '<p class="tiny" style="margin-top:10px">読み込み済み '+d.items+'項目。'+
        '教材を足すには content/ に置いて manifest.js に1行足します。</p></div>'+

    '<div class="card"><div class="lbl">保存</div>'+
      '<p class="tiny" style="margin-top:8px">'+esc(rep.message)+'</p>'+
      '<p class="tiny">'+(s.srv ? '同期先 '+esc(s.srv.base) : 'サーバなし')+'</p></div>'+

    '<div class="card"><button class="btn ghost small" id="aOut" style="width:100%">'+
      'ログアウト</button></div>';

  $('#aExp').onclick = async function(){
    var all = await TubeStore.loadAll();
    if(!all.length) return toast('書き出す記録がありません');
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([TubeStore.exportBundle(all)],
                                          {type:'application/json'}));
    a.download = 'tube-' + TubeSRS.dayKey() + '.json'; a.click();
    toast('書き出しました');
  };
  $('#aOut').onclick = function(){ ui().signOut(); };
}

/* ============================================================
   教材管理

   原本は校舎が持ち、講師は「自分が使うもの」だけを選ぶ。
   講師が外しても校舎からは消えない ―― 消えるのは自分の一覧からだけ。
   1人が誤って消して、他の講師が宿題を出せなくなる事故を防ぐ。
   ============================================================ */
var mat = null;       /* {materials:[...], adopted:[...]|null} */
var matForm = null;

function viewMaterials(m){
  init();
  if(!mat){
    m.innerHTML = '<div class="empty">よみこんでいます…</div>';
    var s = S();
    if(!s.srv){ mat = {materials:[], adopted:null}; return ui().render(); }
    s.srv.materialsAll().then(function(got){
      mat = got || {materials:[], adopted:null}; ui().render();
    });
    return;
  }
  var all = mat.materials || [];
  /* adopted が null は「まだ選んでいない」＝ぜんぶ使う。
     初めて開いた講師の画面が空だと、故障だと思われる。 */
  var mine = mat.adopted;
  var isOn = function(id){ return mine === null || mine.indexOf(id) >= 0; };
  var f = matForm || (matForm = {open:false, id:'', name:'', max:'', mode:'paper',
                                 subject:'english', msg:''});

  m.innerHTML =
    '<div class="card"><div class="lbl">使う教材をえらぶ</div>'+
      '<p class="tiny" style="margin:8px 0 2px">'+
        'ここで外しても、校舎の教材は消えません。'+
        '<b>あなたの画面から見えなくなるだけ</b>です。</p>'+
      '<div class="ratelist">'+ all.map(function(x){
        var on = isOn(x.id);
        return '<div class="raterow">'+
          '<div class="who">'+esc(x.name)+
            '<div class="tiny">'+(x.mode === 'paper' ? 'ノートで解く' : 'アプリで解く')+
            (x.max ? '　'+x.max+'問' : '')+'</div></div>'+
          '<div class="marks">'+
            '<button class="mk'+(on?' on':'')+'" data-mat="'+esc(x.id)+'" '+
              'aria-label="'+(on?'使う':'使わない')+'">'+(on?'✓':'')+'</button>'+
          '</div></div>';
      }).join('') +'</div>'+
      (all.length ? '' : '<p class="tiny" style="margin-top:8px">教材がありません。</p>')+
    '</div>'+

    /* 見出しは開いているときだけ出す。閉じているときは
       「教材を足す」というボタンが1つあれば足りる ――
       見出しとボタンで同じ言葉が2回並んでいた。 */
    '<div class="card">'+ (f.open ? '<div class="lbl">教材を足す</div>' : '')+
      (f.open
        ? '<label class="field"><span class="lbl">名前</span>'+
            '<input id="mName" value="'+esc(f.name)+'" placeholder=""></label>'+
          '<label class="field"><span class="lbl">よびだし名（英小文字と数字）</span>'+
            '<input id="mId" value="'+esc(f.id)+'"></label>'+
          '<label class="field"><span class="lbl">ぜんぶで何問</span>'+
            '<input id="mMax" inputmode="numeric" value="'+esc(f.max)+'"></label>'+
          '<div class="lbl" style="margin-bottom:6px">どこで解くか</div>'+
          '<div class="row" style="gap:8px;margin-bottom:14px">'+
            '<button class="btn small'+(f.mode==='paper'?'':' ghost')+'" data-mode="paper">'+
              'ノートで解く</button>'+
            '<button class="btn small'+(f.mode==='app'?'':' ghost')+'" data-mode="app">'+
              'アプリで解く</button></div>'+
          '<p class="tiny" style="margin-bottom:12px">'+
            'ノートで解く教材は、アプリが提出を見ません。'+
            '出したあと、ノートを見て4段階で記録できます。</p>'+
          (f.msg ? '<p class="tiny" style="color:var(--accent)">'+esc(f.msg)+'</p>' : '')+
          '<button class="btn" id="mAdd">これを足す</button>'+
          '<button class="btn ghost small" id="mCancel" style="width:100%;margin-top:10px">'+
            'やめる</button>'
        : '<button class="btn ghost" id="mOpen" style="margin-top:10px">'+
            '教材を足す</button>')+
    '</div>';

  m.querySelectorAll('[data-mat]').forEach(function(b){
    b.onclick = async function(){
      var id = b.dataset.mat;
      var cur = (mine === null) ? all.map(function(x){ return x.id; }) : mine.slice();
      var i = cur.indexOf(id);
      if(i >= 0) cur.splice(i,1); else cur.push(id);
      mat.adopted = cur; ui().render();
      var ok = await S().srv.adoptMaterials(cur);
      if(!ok){ mat = null; toast('保存できませんでした'); ui().render(); }
    };
  });
  var b;
  if((b = $('#mOpen'))) b.onclick = function(){ f.open = true; ui().render(); };
  if((b = $('#mCancel'))) b.onclick = function(){ matForm = null; ui().render(); };
  m.querySelectorAll('[data-mode]').forEach(function(x){
    x.onclick = function(){ keepMat(); f.mode = x.dataset.mode; ui().render(); };
  });
  function keepMat(){
    if($('#mName')) f.name = $('#mName').value;
    if($('#mId'))   f.id   = $('#mId').value;
    if($('#mMax'))  f.max  = $('#mMax').value;
  }
  if((b = $('#mAdd'))) b.onclick = async function(){
    keepMat();
    var r = await S().srv.addMaterial({id:f.id.trim().toLowerCase(), name:f.name.trim(),
                                       max:+f.max, mode:f.mode, subject:f.subject,
                                       short:f.name.trim().slice(0,8)});
    if(!r.ok){ f.msg = r.error; return ui().render(); }
    matForm = null; mat = null; toast('教材を足しました'); ui().render();
  };
}

/* ============================================================
   生徒管理 ―― 名簿の一括登録

   氏名は受け取らない。クラスと出席番号だけ。
   誰がどの番号かは、先生の手元の名簿にしかない状態を保つ。
   ============================================================ */
var bulk = null;

function viewRosterAdmin(m){
  init();
  var b = bulk || (bulk = {classId:(myClasses()[0]||{}).id || '', from:1, to:10,
                           made:[], running:false, done:0, total:0, msg:''});
  var ks = myClasses();

  m.innerHTML =
    '<div class="card"><div class="lbl">名簿をまとめて登録</div>'+
      '<p class="tiny" style="margin:8px 0 14px">'+
        '<b>氏名は入れません。</b>クラスと出席番号だけで作ります。'+
        'だれがどの番号かは、先生のお手元の名簿で管理してください。</p>'+
      '<label class="field"><span class="lbl">クラス</span>'+
        '<select id="bCls">'+ ks.map(function(k){
          return '<option value="'+k.id+'"'+(b.classId===k.id?' selected':'')+'>'+
                 esc(k.name)+'</option>'; }).join('') +'</select></label>'+
      '<div class="row" style="gap:12px">'+
        '<label class="field" style="flex:1"><span class="lbl">出席番号 から</span>'+
          '<input id="bFrom" inputmode="numeric" value="'+b.from+'"></label>'+
        '<label class="field" style="flex:1"><span class="lbl">まで</span>'+
          '<input id="bTo" inputmode="numeric" value="'+b.to+'"></label>'+
      '</div>'+
      (b.msg ? '<p class="tiny" style="color:var(--accent)">'+esc(b.msg)+'</p>' : '')+
      (b.running
        ? '<div class="meter" style="margin:6px 0 10px"><i style="width:'+
            (b.total ? (b.done/b.total*100).toFixed(0) : 0)+'%"></i></div>'+
          '<p class="tiny">'+b.done+' / '+b.total+'名 …そのままお待ちください</p>'
        : '<button class="btn" id="bGo">この人数ぶん つくる</button>')+
    '</div>'+

    (b.made.length
      ? '<div class="card"><div class="lbl">できたID と あいことば</div>'+
          '<p class="tiny" style="margin:8px 0 10px">'+
            '<b>この画面を閉じると、もう見られません。</b>'+
            '印刷するか、書き写してから閉じてください。</p>'+
          '<div class="ratelist">'+ b.made.map(function(x){
            return '<div class="raterow"><div class="who">'+esc(x.classId)+'-'+esc(x.seat)+
              '</div><div class="tiny num">'+esc(x.id)+'　'+esc(x.password)+'</div></div>';
          }).join('') +'</div>'+
          '<button class="btn ghost small" id="bCsv" style="width:100%;margin-top:12px">'+
            'ファイルに書き出す</button>'+
        '</div>'
      : '')+

    '<div class="card"><div class="lbl">200名をこえるとき</div>'+
      '<p class="tiny" style="margin-top:8px">'+
        '画面からは一度に'+25+'名ずつ作ります。校舎ぜんぶを一度に作るときは、'+
        'CSVを用意して、サーバで次を実行してください。</p>'+
      '<p class="tiny num" style="margin-top:8px">'+
        'python3 server/tube_server.py roster-import 名簿.csv --school ' +
        esc((S().teacher.profile||{}).school || '') + ' --yes</p>'+
    '</div>';

  var keep = function(){
    b.classId = $('#bCls').value;
    b.from = +$('#bFrom').value || 1;
    b.to = +$('#bTo').value || 1;
  };
  $('#bCls').onchange = keep;
  $('#bFrom').oninput = keep;
  $('#bTo').oninput = keep;
  var g;
  if((g = $('#bGo'))) g.onclick = async function(){
    keep();
    var n = b.to - b.from + 1;
    if(n < 1){ b.msg = '番号の順が逆です'; return ui().render(); }
    if(n > 200){ b.msg = '一度に作れるのは200名までです'; return ui().render(); }
    b.msg = ''; b.running = true; b.done = 0; b.total = n; b.made = [];
    ui().render();
    /* 25名ずつに分けて送る。1件あたり0.16秒かかるので、
       まとめて送ると途中で切れる。分ければ進み具合も出せる。 */
    for(var i = b.from; i <= b.to; i += 25){
      /* **あいことばは、この端末が作る。** サーバへ送るのは、確かめるための値（verifier）だけ。
         サーバは あいことばを作らないし、返さない（js/scram.js）。 */
      var send = [], pws = {};
      for(var k = i; k <= Math.min(i+24, b.to); k++){
        var seat = ('0'+k).slice(-2);
        var pw = await TubeScram.makePassword(3);
        pws[b.classId + '|' + seat] = pw;
        send.push({classId:b.classId, seat:seat, grade:TubeConfig.gradeOfClass(b.classId),
                   verifier:await TubeScram.verifier(pw)});
      }
      var r = await S().srv.rosterBulk(send);
      if(!r){ b.msg = 'サーバに繋がりませんでした'; break; }
      (r.made || []).forEach(function(x){ x.password = pws[x.classId + '|' + x.seat]; });
      b.made = b.made.concat(r.made || []);
      (r.skipped || []).forEach(function(x){
        if(!b.msg) b.msg = x.seat+'番: '+x.why; });
      b.done = b.made.length; ui().render();
    }
    /* 名簿の控え（この部品の rows）を捨てる。送る行は別の名前（send）にしてある。 */
    b.running = false; rows = null; ui().render();
  };
  if((g = $('#bCsv'))) g.onclick = function(){
    var csv = 'id,password,classId,seat\n' + bulk.made.map(function(x){
      return [x.id, x.password, x.classId, x.seat].join(','); }).join('\n');
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'}));
    a.download = 'roster-' + TubeSRS.dayKey() + '.csv'; a.click();
    toast('書き出しました。配布後は削除してください');
  };
}

/* 前の講師（や生徒）の控えを捨てる（ui-core がログイン・ログアウトで呼ぶ） */
function resetSession(){
  inbox = undefined; mgReply = {}; tprep = undefined; pEdits = {};
}

global.TubeTeacher = {
  resetSession:resetSession,
  classesOf:classesOf, afterLogin:afterLogin,
  /* コースの教科の冊子（成績タブの「宿題を足す」がプリセットの教材を選ぶのに使う） */
  booksOf:function(c){ return booksOf(c) || []; },
  viewRoster:viewRoster, viewHomework:viewHomework,
  /* 宿題チェックのページ（ui-desk.js）。宿題タブの中の1枚 */
  viewCheck:function(m){ init(); return TubeDesk.viewCheck(m); },
  viewProgress:viewProgress, viewAdmin:viewAdmin, viewApps:viewApps,
  viewMaterials:viewMaterials, viewRosterAdmin:viewRosterAdmin,
  /* タブを押しなおしたとき。えらんだクラスや教科は残し、開いている紙と下の階だけ閉じる。 */
  home:function(){ if(window.TubeDesk) TubeDesk.home();
                   openKey = null; lplan = null;
                   pick.sheet = null; pick.stu = null; pick.sugg = null; pick.openHw = null; },
  reload:function(){ rows = null; hwRows = null; mat = null; inbox = undefined;
                     drift = undefined; grid = undefined;
                     openKey = null; lplan = null; },
  /* 見張り（ui-core watchNow）から。変わった台帳ぶんだけ取り直し、開いている画面は保つ。 */
  wake:function(changed){
    if(!changed || changed.assignments){ hwRows = null; grid = undefined; refreshHw(); }
    if(!changed || changed.messages || changed.personal){ inbox = undefined; loadInbox(); }
    if(window.TubeDesk && TubeDesk.wake) TubeDesk.wake(changed);
    ui().render();
  }
};

})(window);
