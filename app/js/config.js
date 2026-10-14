/* ============================================================
   進度の取り扱い
   ------------------------------------------------------------
   進度（学年 × 科目ごとに、何を・どれだけ）は2か所から来る。

     1. サーバ（server/data/curriculum.json）… 講師が画面で変えたもの
     2. app/curriculum.js …………………………… 工場出荷時の既定値

   サーバのものがあればそれを使い、無ければ既定値を使う。
   両方あるときはサーバが勝つ。「講師が画面で変えたのに反映されない」
   ということが起きないよう、優先順位はここ1か所で決める。

   画面もエンジンも、進度を直接読まずに必ずここを通す。
   ============================================================ */
(function(global){
"use strict";

var DEF  = global.TubeCurriculum || {};
var live = null;          // サーバから来たもの
var dirty = false;        // 講師が編集して未保存か

function base(){ return live || DEF; }

/* ------------------------------------------------------------
   学年・クラス
   ------------------------------------------------------------ */
/* サーバの表が空なら既定を使う。空の配列は「0件」ではなく「まだ無い」。 */
function listOf(name){
  var b = base()[name];
  return ((b && b.length) ? b : (DEF[name] || [])).slice();
}
function grades(){
  return listOf('grades')
    .sort(function(a,b){ return (a.order||0) - (b.order||0); });
}
function grade(id){
  return grades().filter(function(g){ return g.id === id; })[0]
      || {id:id, name:id, order:99};
}
function classes(){ return listOf('classes'); }
function classOf(id){
  return classes().filter(function(k){ return k.id === id; })[0] || null;
}
/* クラスから学年を引く。アカウントは classId を持つので、こちらが正。 */
function gradeOfClass(classId){
  var k = classOf(classId);
  return k ? k.grade : null;
}

/* ------------------------------------------------------------
   進度
   ------------------------------------------------------------ */
function planKey(gradeId, subjectId){ return gradeId + ':' + subjectId; }

function plans(){ return base().plans || DEF.plans || {}; }

/* ------------------------------------------------------------
   1日の量 ―― **学年で変える。**

   前は全学年ほぼ同じで、上限まで出ると小4で149分、中3で222分あった。
   小4に中3と同じ量を出すのは、続かない以前に、机に向かえる時間ではない。

   狙いは「単元確認テストのための毎日の反復」なので、
   1日で嫌にならない長さに収める。

     小4 20分 → 小5 32分 → 小6 45分   （小学生は45分を上限）
     中1 50分 → 中2 55分 → 中3 60分   （中学生でまた傾斜をつける）

   **数ではなく時間で決める。** 1問の重さが教科でちがうため
   （数学の1問は70秒、英語は30秒）。同じ「12問」でも、
   数学は14分、英語は6分になってしまう。

   ★ この表は server/examprep.py にも同じものがある。
     ここに置くのは、**電波の無い地下鉄の中でも量が決まる**必要が
     あるため。片方だけ直すと画面とサーバで食い違う ――
     一致は app/tools/こわれ方の検査.py が見張っている。
   ------------------------------------------------------------ */
var DAILY_MIN = {e4:20, e5:32, e6:45, j1:50, j2:55, j3:60};
var DAILY_MIN_DEF = 30;

/* 新しく覚える分にあてる割合。残りは復習。
   新出を厚くすると札が増えすぎて、翌週以降の復習が破綻する。 */
var NEW_SHARE = 0.35;

/* 1問にかかる秒数。**アプリで解くときの時間。**
   server/examprep.py の SEC_PER / APP_SEC と同じ表。

   紙で解く時間（examprep.SUBJECT_SEC）は別に持っている ――
   紙は途中式を書き、消しゴムを使い、読み返すぶん遅い。
   1つの表で両方をまかなうと、どちらかが必ず外れる。 */
var SEC_PER     = {quiz:45, term:30};
var SUBJECT_SEC = {math:    {quiz:70, term:40},
                   english: {quiz:30, term:25},
                   japanese:{quiz:35, term:25}};
var DEFAULT_SEC = 40;

function secOf(subjectId, track){
  var per = SUBJECT_SEC[subjectId] || SEC_PER;
  var t = (track === 'quiz') ? 'quiz' : 'term';
  return per[t] || SEC_PER[t] || DEFAULT_SEC;
}

/* その学年で生徒に出ている科目の数。**plan() を呼ばずに数える** ――
   plan() の中から呼ぶので、呼び返すと止まらなくなる。 */
function enabledCount(gradeId){
  /* **既定の教材も見る。** サーバの進度には「使う・使わない」だけが入り、
     教材（packs）は既定にしか無いことがある。サーバの分だけで数えると 0 になり、
     1教科に1日ぶんの時間を全部わたしていた（中3で1日241問になっていた）。 */
  var ps = plans(), def = DEF.plans || {}, n = 0, seen = {};
  Object.keys(ps).concat(Object.keys(def)).forEach(function(k){
    if(seen[k] || k.indexOf(gradeId + ':') !== 0) return;
    seen[k] = 1;
    if(TAKING && TAKING.indexOf(k.slice(gradeId.length + 1)) < 0) return;
    var p = ps[k] || {}, d = def[k] || {};
    if(p.enabled === false) return;
    if((p.packs || []).length || (d.packs || []).length) n++;
  });
  return n || 1;
}

/* その生徒の受講科目（国英／国数英…）。サーバの profile.subjects から入る。
   **受講していない教科の毎日テストは出さない。** 1日の持ち時間は学年のまま
   なので、受講する教科が少ない生徒ほど1教科に使える時間が長くなる。
   空（受講科目の登録が無い生徒・講師の画面）は全教科。 */
var TAKING = null;
function setTaking(list){ TAKING = (list && list.length) ? list.slice() : null; }

/* 進度に書いてある量を、その学年の持ち時間に収める。

   **進度に何が書いてあっても超えさせない。** ここで削らないと、
   教科を1つ「使う」に切り替えるたびに1日の量が増え続ける ――
   増えたことは誰にも見えず、生徒の画面にだけ出る。 */
function fit(pl){
  var per = (DAILY_MIN[pl.grade] || DAILY_MIN_DEF) * 60 / enabledCount(pl.grade);
  var newSec = per * NEW_SHARE, revSec = per - per * NEW_SHARE;

  var tracks = pl.tracks.length ? pl.tracks : Object.keys(pl.daily);
  var want = 0;
  tracks.forEach(function(t){ want += (pl.daily[t] || 0) * secOf(pl.subject, t); });
  if(want > newSec && want > 0){
    var k = newSec / want, d = {};
    tracks.forEach(function(t){
      var v = (pl.daily[t] || 0) * k;
      d[t] = v < 1 ? Math.round(v * 10) / 10 : Math.round(v);
    });
    /* ぜんぶ0になったら、先頭の種別だけ残す ――
       0問の日が続くと、その教科は無いのと同じになる。 */
    if(!tracks.some(function(t){ return d[t] > 0; })) d[tracks[0]] = 1;
    pl.daily = d;
  }
  var cap = Math.floor(revSec / secOf(pl.subject, 'term'));
  pl.maxRev = Math.max(5, Math.min(pl.maxRev, cap));
  return pl;
}

/* その学年・その科目の進度。

   **既定（app/curriculum.js）に、サーバの分を重ねて返す。**
   前は「サーバに plans があれば既定を丸ごと無視」だった。
   ところがサーバ側の plans には、講師が選んだ教材だけでなく
   「実施ずみの単元（done）」も入る。done を書いただけの科目は
   packs が空のまま既定を上書きし、**その科目が 0問になる**。
   実際、デモの curriculum.json が古い教材名を持ったまま残っていて、
   足したはずの教材が1つも出なかった。

   欄ごとに重ねれば、サーバは「変えたい欄だけ」書けばよくなる。
   教材の差し替えも、app/curriculum.js の1か所で済む。 */
function plan(gradeId, subjectId){
  var key = planKey(gradeId, subjectId);
  var def = (DEF.plans || {})[key];
  var live = (base().plans || {})[key];
  if(!def && !live) return null;
  var p = {};
  [def, live].forEach(function(src){
    if(!src) return;
    Object.keys(src).forEach(function(k){
      /* 空の配列で既定を消さない。**「まだ選んでいない」と
         「使わない」は別**である。使わないなら enabled:false を書く。 */
      var v = src[k];
      if(Array.isArray(v) && !v.length && Array.isArray(p[k]) && p[k].length) return;
      p[k] = v;
    });
  });
  /* subject を持たせて返す ―― 呼び出し側が鍵を分解しなくて済む */
  return fit({
    grade:gradeId, subject:subjectId,
    enabled: p.enabled !== false,
    packs:  p.packs  || [],
    bands:  p.bands  || [],
    tracks: p.tracks || [],
    daily:  Object.assign({}, p.daily || {}),
    maxRev: p.maxRev == null ? 100 : p.maxRev,
    note:   p.note   || ''
  });
}

/* その学年で「いま生徒に出ている」科目。順番は manifest の order。 */
function subjectsFor(gradeId){
  var out = [];
  TubeContent.subjects().forEach(function(s){
    if(TAKING && TAKING.indexOf(s.id) < 0) return;
    var p = plan(gradeId, s.id);
    if(p && p.enabled && p.packs.length) out.push({subject:s, plan:p});
  });
  return out;
}

/* 準備中も含めた全組み合わせ（講師の進度画面で使う） */
function allPlansFor(gradeId){
  return TubeContent.subjects().map(function(s){
    return {subject:s, plan:plan(gradeId, s.id)};
  });
}

/* その生徒が読み込むべき教材。必要なものだけ取りにいく。 */
function packsFor(gradeId){
  var seen = {}, out = [];
  subjectsFor(gradeId).forEach(function(x){
    x.plan.packs.forEach(function(p){ if(!seen[p]){ seen[p] = 1; out.push(p); } });
  });
  return out;
}
/* 講師は担当クラスの学年ぶんを見るので、まとめて読む */
function packsForGrades(gradeIds){
  var seen = {}, out = [];
  (gradeIds||[]).forEach(function(g){
    packsFor(g).forEach(function(p){ if(!seen[p]){ seen[p] = 1; out.push(p); } });
  });
  return out;
}

/* ------------------------------------------------------------
   編集（講師の進度画面から呼ばれる）
   ------------------------------------------------------------ */
function snapshot(){
  /* 既定値をもとに、いま有効な内容を1つの塊にして返す。
     サーバへ送るのはこの形。部分更新にしないのは、
     「消したはずの進度が残る」事故を避けるため。 */
  var b = base();
  return {
    v: 2,
    grades:  JSON.parse(JSON.stringify(b.grades  || DEF.grades  || [])),
    classes: JSON.parse(JSON.stringify(b.classes || DEF.classes || [])),
    plans:   JSON.parse(JSON.stringify(b.plans   || DEF.plans   || {}))
  };
}

function setPlan(gradeId, subjectId, patch){
  if(!live) live = snapshot();
  var k = planKey(gradeId, subjectId);
  var cur = live.plans[k] || {enabled:false, packs:[], bands:[], tracks:[],
                              daily:{}, maxRev:100};
  live.plans[k] = Object.assign({}, cur, patch);
  dirty = true;
  return live.plans[k];
}
function removePlan(gradeId, subjectId){
  if(!live) live = snapshot();
  delete live.plans[planKey(gradeId, subjectId)];
  dirty = true;
}

function adopt(fromServer){
  if(fromServer && fromServer.plans && Object.keys(fromServer.plans).length){
    live = fromServer;
    dirty = false;
    return true;
  }
  return false;
}

global.TubeConfig = {
  /* 読み取り */
  school:   function(){ return DEF.school || {id:'', name:''}; },
  /* ログインで判明した所属校舎を覚える。表示にしか使わない ――
     どの校舎のデータを読むかはサーバが合言葉から決めるので、
     ここを書き換えても他校舎は見えない。 */
  setSchool:function(id, name){
    if(id) DEF.school = {id:String(id).slice(0,24), name:String(name||id).slice(0,40)};
  },
  grades:grades, grade:grade,
  classes:classes, classOf:classOf, gradeOfClass:gradeOfClass, setTaking:setTaking,
  plan:plan, plans:plans, planKey:planKey,
  subjectsFor:subjectsFor, allPlansFor:allPlansFor,
  packsFor:packsFor, packsForGrades:packsForGrades,
  /* 設定値 */
  sync:     function(){ return DEF.sync; },
  voice:    function(){ return DEF.voice || 'en-GB'; },
  mature:   function(){ return DEF.mature || 21; },
  stuckLapses: function(){ return DEF.stuckLapses || 3; },
  hwMinPerDay: function(){ return DEF.hwMinPerDay || 5; },
  /* 編集 */
  adopt:adopt, snapshot:snapshot, setPlan:setPlan, removePlan:removePlan,
  isDirty:  function(){ return dirty; },
  markSaved:function(){ dirty = false; },
  fromServer:function(){ return !!live; }
};

})(window);
