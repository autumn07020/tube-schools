/* ============================================================
   教材の登録と取り出し
   ------------------------------------------------------------
   content/manifest.js が「どの科目にどの教材があるか」を持ち、
   content/<科目>/*.js が中身を持つ。このファイルはそれを畳んで、
   「この学年のこの科目では、どの項目を、どの順に出すか」を返す。

   ★ 項目IDは中身から作り、先頭に科目コードを付ける。
        en:v:reluctant:adj      英語・単語
        sci:t:光合成            理科・用語
        soc:q:経度15度の…       社会・選択問題
     配列の位置を使うと、教材の途中に1つ挿し込んだ瞬間に
     全生徒の進捗がズレる（HANDOVER 5.2）。
     科目コードを付けるのは、科目をまたいだ同名の項目を
     別物として扱うため。

   ★ 教材を足すのに、このファイルを触る必要はない。
     content/<科目>/ に .js を置き、manifest.js に1行足すだけ。
   ============================================================ */
(function(global){
"use strict";

var packs   = {};       // packId -> {id, subject, name, counts, bands}
var DECK    = [];
var BY_ID   = {};
var SYN     = {};
var dupes   = [];
var loaded  = {};       // packId -> true（二重読み込みを防ぐ）

function manifest(){ return global.TubeManifest || {subjects:[], packs:[], booklets:[]}; }

function subject(id){
  return manifest().subjects.filter(function(s){ return s.id === id; })[0]
      || {id:id, code:id, name:id, short:id};
}
function packInfo(id){
  return manifest().packs.filter(function(p){ return p.id === id; })[0] || null;
}
function booklet(id){
  return manifest().booklets.filter(function(b){ return b.id === id; })[0]
      || {id:id, name:id, short:id, max:9999};
}

/* 項目IDのもと。**server/examprep.py の _slug と同じ規則。**

   ★ 片方だけ直すと、サーバと画面で項目IDが食い違い、
     「にがて」も「対策」も静かに0件になる。必ず両方直すこと。
     一致は app/tools/こわれ方の検査.py が見張っている。 */
function slug(s){
  /* 全角を半角にそろえてから削る。そろえないと「ＡＢＣ」がまるごと
     落ちて空になり、そういう見出しどうしが全部ぶつかる。 */
  var t = String(s).normalize('NFKC').toLowerCase();
  var out = t.replace(/[^a-z0-9぀-ヿ一-鿿]+/g, '-').replace(/^-|-$/g, '');
  if(out) return out;
  /* 削った結果が空なら、元の文字列から短い指紋を作る。
     IDは読めなくてよいが、ぶつかってはいけない。 */
  var h = 0;
  for(var i = 0; i < t.length; i++){
    h = ((h << 5) - h + t.charCodeAt(i)) | 0;
  }
  return 'x' + (h >>> 0).toString(16);
}

function add(card){
  if(BY_ID[card.id]){ dupes.push(card.id); return; }
  card.seq = DECK.length;          // 登録順 = 教える順
  BY_ID[card.id] = card;
  DECK.push(card);
}

/* ------------------------------------------------------------
   パックの登録。content/<科目>/*.js の末尾から呼ばれる。

   英語だけが使う型（V/P/G/B）と、全科目で使える型（T/Q）がある。
   新しい科目を足すときは T と Q だけで書けばよい。
   ------------------------------------------------------------ */
function register(pack){
  var sub  = subject(pack.subject);
  var code = sub.code;
  var pid  = pack.id;
  if(loaded[pid]) return;
  loaded[pid] = true;

  var rec = {id:pid, subject:pack.subject, name:pack.name || pid,
             note:pack.note || '', bands:pack.bands || [], counts:{}};
  packs[pid] = rec;

  var n0 = DECK.length;
  var mark = function(kind){ rec.counts[kind] = DECK.length - n0; n0 = DECK.length; };

  /* ---- 全科目で使える型 ---- */
  /* T: [表, 裏, 帯, 解説, 例, 例の補足] */
  (pack.T || []).forEach(function(r){
    add({ id:code+':t:'+slug(r[0]), t:'term', pack:pid, subject:pack.subject,
          band:r[2] || '', front:r[0], back:r[1] || '',
          note:r[3] || '', ex:r[4] || '', exSub:r[5] || '' });
  });
  mark('term');

  /* Q: [問題文, 正解, 誤答(|), 帯, 解説, 単元, 図, 読解文] */
  (pack.Q || []).forEach(function(r){
    add({ id:code+':q:'+slug(r[0]), t:'quiz', pack:pid, subject:pack.subject,
          band:r[3] || '', q:r[0], ans:r[1],
          dis:String(r[2] || '').split('|').filter(Boolean),
          note:r[4] || '', unit:r[5] || '',
          /* 7列目は図の名前。絵そのものは content/figures.js にある。
             ここでは名前だけ持つ ―― 同じ絵を何問でも使いまわせる。 */
          fig:r[6] || '',
          /* 8列目は読解文の名前。本文は content/readings.js にある。
             1つの長文を何問でも共有する。 */
          bun:r[7] || '' });
  });
  mark('quiz');

  /* ---- 英語だけが使う型 ---- */
  /* V: [見出し, 品詞, 帯, 訳, 英義, 例文, 連語(|), 解説, 例文訳] */
  (pack.V || []).forEach(function(r){
    add({ id:code+':v:'+slug(r[0])+':'+slug(r[1]), t:'vocab', pack:pid,
          subject:pack.subject, band:r[2], head:r[0], pos:r[1],
          ja:r[3], en:r[4], ex:r[5],
          coll:r[6] ? r[6].split('|') : [], note:r[7] || '', exJa:r[8] || '' });
  });
  mark('vocab');

  /* P: [型(___), 答, 誤答(|), 帯, 例文, 訳, 解説] */
  (pack.P || []).forEach(function(r){
    add({ id:code+':p:'+slug(r[0])+':'+slug(r[1]), t:'prep', pack:pid,
          subject:pack.subject, band:r[3], pat:r[0], ans:r[1],
          dis:r[2].split('|'), ex:r[4], ja:r[5], note:r[6] || '' });
  });
  mark('prep');

  (pack.G || []).forEach(function(g){
    add({ id:code+':g:'+slug(g.t), t:'gram', pack:pid, subject:pack.subject,
          band:g.cefr || g.band, head:g.t, ja:g.ja, rule:g.rule,
          forms:g.forms || [], qs:g.q || [] });
  });
  mark('gram');

  (pack.B || []).forEach(function(r){
    add({ id:code+':b:'+slug(r[0]), t:'brit', pack:pid, subject:pack.subject,
          band:'B1', head:r[0], ja:r[1], en:r[2], ex:r[3], note:r[4] || '' });
  });
  mark('brit');

  /* 類義語は見出し語で引く別テーブル。語彙タプルとは独立に足せる。 */
  var s = pack.SYN || {};
  Object.keys(s).forEach(function(k){ if(!(k in SYN)) SYN[k] = s[k]; });
}

/* ------------------------------------------------------------
   必要なパックだけを読み込む

   その生徒の学年・科目で使うものだけを取りにいく。全科目ぶんを
   最初に読むと、英語しか使わない小学生にも理科の教材が届く。
   ------------------------------------------------------------ */
function loadPacks(ids){
  var want = (ids || []).filter(function(id){ return !loaded[id] && packInfo(id); });
  if(!want.length) return Promise.resolve([]);
  return Promise.all(want.map(function(id){
    var info = packInfo(id);
    return new Promise(function(res){
      var el = document.createElement('script');
      el.src = 'content/' + info.file;
      el.onload  = function(){ res({id:id, ok:true}); };
      /* 読めなかったことを黙って飲まない。教材が1つ欠けたまま
         「今日の問題は0問です」と出るのが、いちばん分かりにくい壊れ方。 */
      el.onerror = function(){ res({id:id, ok:false}); };
      document.head.appendChild(el);
    });
  }));
}

/* ------------------------------------------------------------
   進度（plan）にもとづく取り出し

   plan = { subject, packs[], bands[], tracks[], exclude[] }
   bands は「取り組む順」。難度の順である必要はない。
   ------------------------------------------------------------ */
function orderFor(plan){
  if(!plan) return [];
  var bandIndex = {};
  (plan.bands || []).forEach(function(b, i){ bandIndex[b] = i; });
  var okPack = {};
  (plan.packs || []).forEach(function(p){ okPack[p] = true; });
  var okTrack = {};
  (plan.tracks || []).forEach(function(t){ okTrack[t] = true; });
  var blocked = {};
  (plan.exclude || []).forEach(function(id){ blocked[id] = true; });
  var anyBand = !(plan.bands || []).length;

  return DECK.filter(function(c){
      return okPack[c.pack] && okTrack[c.t] && !blocked[c.id] &&
             (anyBand || (c.band in bandIndex));
    })
    .sort(function(a, b){
      var d = anyBand ? 0 : (bandIndex[a.band] - bandIndex[b.band]);
      return d || (a.seq - b.seq);
    });
}

function countsFor(plan){
  var o = {total:0};
  orderFor(plan).forEach(function(c){ o[c.t] = (o[c.t] || 0) + 1; o.total++; });
  return o;
}

/* パックが実際に持っている帯（進度画面の選択肢に出す） */
function bandsOf(packIds){
  var seen = {}, out = [];
  DECK.forEach(function(c){
    if((packIds || []).indexOf(c.pack) < 0) return;
    if(c.band && !seen[c.band]){ seen[c.band] = 1; out.push(c.band); }
  });
  return out;
}
function tracksOf(packIds){
  var seen = {}, out = [];
  DECK.forEach(function(c){
    if((packIds || []).indexOf(c.pack) < 0) return;
    if(!seen[c.t]){ seen[c.t] = 1; out.push(c.t); }
  });
  /* **並びを固定する。** DECK は教材を読み終えた順に伸びるので、そのままだと
     開くたびに「用語・一問一答」と「一問一答・用語」が入れ替わっていた。 */
  return out.sort();
}

/* 古い形式の進捗を読めるようにする。
   科目コードを付ける前は 'v:reluctant:adj' のような形だった。 */
function migrateId(id){
  if(id.indexOf(':') < 0) return id;
  if(/^(en|sci|soc):/.test(id)) return id;
  if(/^(v|p|g|b):/.test(id))    return 'en:' + id;
  if(/^myvocab:/.test(id))      return 'en:' + id;
  return id;
}

var TRACK_JA = {vocab:'単語', prep:'語法', gram:'文法', brit:'英国表現',
                term:'用語', quiz:'一問一答', hw:'宿題'};

/* ============================================================
   単語帳の番号 ―― My英単語帳
   ============================================================
   冊子は無い。**番号は、教材に入っている単語の並び順そのもの**を指す。
   1番はファイルの1語目、50番は50語目。

   前は「番号だけ出して、冊子で引いて、思い出せたか自分で押す」
   作りだった。紙を見るなら紙だけでよく、アプリでやる意味がなかった。
   いまは番号から語を引き、意味を4択で選ばせる。

   並び順は教材ファイルの順である。**教材を差し替えたら番号もずれる。**
   差し替えるときは、宿題の番号も一緒に振り直すこと。
   ============================================================ */
var VOCAB_ORDER = {};       // packId -> [card, …]（V の並び順）

function vocabList(packId){
  if(VOCAB_ORDER[packId]) return VOCAB_ORDER[packId];
  var out = DECK.filter(function(c){
    return c.t === 'vocab' && c.pack === packId;
  });
  /* **空のときは覚えない。** 教材はあとから読み込まれる。
     読み込む前に一度呼ばれると、空のまま覚えてしまい、
     そのあと何度呼んでも0語のままになる。 */
  if(out.length) VOCAB_ORDER[packId] = out;
  return out;
}

/* 冊子の n 番の語。無ければ null。 */
function bookletItem(bookletId, n){
  var b = booklet(bookletId);
  if(!b || !b.pack) return null;
  var rows = vocabList(b.pack);
  var i = (Number(n) || 0) - 1;
  return (i >= 0 && i < rows.length) ? rows[i] : null;
}

/* その語の意味を4択にする。**誤答は同じ教材の他の語の意味から取る。**
   よそから持ってくると「明らかに畑ちがい」の選択肢になり、
   読まなくても消せてしまう。 */
function bookletChoices(bookletId, n){
  var it = bookletItem(bookletId, n);
  if(!it) return null;
  var b = booklet(bookletId);
  var rows = vocabList(b.pack);
  var i = (Number(n) || 0) - 1;
  var out = [], step = Math.max(7, Math.floor(rows.length / 17)), j = i;
  while(out.length < 3 && rows.length > 4){
    j = (j + step) % rows.length;
    if(j === i){ j = (j + 1) % rows.length; }
    var ja = rows[j].ja;
    if(ja && ja !== it.ja && out.indexOf(ja) < 0) out.push(ja);
  }
  return {item:it, ans:it.ja, dis:out};
}

global.TubeContent = {
  register:register, loadPacks:loadPacks,
  get:      function(id){ return BY_ID[id] || null; },
  all:      function(){ return DECK; },
  syn:      function(head){ return SYN[head] || ''; },
  orderFor:orderFor, countsFor:countsFor,
  bandsOf:bandsOf, tracksOf:tracksOf,
  subject:subject, packInfo:packInfo, booklet:booklet,
  bookletItem:bookletItem, bookletChoices:bookletChoices,
  subjects: function(){ return (manifest().subjects || []).slice()
                          .sort(function(a,b){ return (a.order||0)-(b.order||0); }); },
  packList: function(subjectId){
    return (manifest().packs || []).filter(function(p){
      return !subjectId || p.subject === subjectId; });
  },
  booklets: function(subjectId){
    return (manifest().booklets || []).filter(function(b){
      return !subjectId || b.subject === subjectId; });
  },
  isLoaded: function(id){ return !!loaded[id]; },
  migrateId:migrateId, trackName:function(t){ return TRACK_JA[t] || t; },
  slug:slug,
  diagnostics: function(){
    return {packs:Object.keys(packs).map(function(k){ return packs[k]; }),
            items:DECK.length, synonyms:Object.keys(SYN).length, dupes:dupes};
  }
};

})(window);
