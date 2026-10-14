/* ============================================================
   HOMEWORK ―― 先生が出した宿題を、生徒の側でどう扱うか
   ------------------------------------------------------------
   宿題は「どの冊子の、何番から何番までを、いつまでに」という指示。
   アプリは単語そのものを持たない（curriculum.js の sources を参照）。
   生徒は冊子を見て思い出し、ここで自己採点する。

   達成状況は生徒の進捗ブロブの中（p.hw）に入れてある。別テーブルに
   しないのは、既にある保存と同期の経路にそのまま乗せるため ――
   宿題のためだけに新しい保存の道を作ると、そこだけ消える。

     p.hw = {
       "a1f2e3d4": {
         done:  {"1000":1, "1003":1},   覚えた番号
         startedAt:  1785…,
         completedAt: null | 1785…      全部終えた時刻
       }
     }

   番号は SRS にも載る（項目IDは "myvocab:1024"）。一度覚えた番号も
   間隔をあけて戻ってくるので、宿題が「一度やって終わり」にならない。
   ただし戻ってくる先は宿題の中だけで、ふだんの学習には混ざらない。
   ============================================================ */
(function(global){
/* 小6以上は講師と同じ漢字で出す（TubeUI.jp）。TubeUI より先に読まれてもよいように。 */
function jp(kana, kanji){ var U = global.TubeUI; return (U && U.jp) ? U.jp(kana, kanji) : kana; }
"use strict";

var list = [];          // サーバから来た宿題（生徒には自分宛のものだけ届く）

var DAY = 864e5;

function setAll(rows){ list = rows || []; }
function all(){ return list.slice(); }
function byId(id){
  return list.filter(function(a){ return a.id === id; })[0] || null;
}
/* 冊子の情報は content/manifest.js が持つ。宿題はそこを引くだけ。 */
function source(id){ return TubeContent.booklet(id); }

/* 対象となる番号の並び。

   ふつうは from から to まで。ただし**とびとびの宿題**もある ――
   「苦手なところだけ10問」は番号が連続しない。その場合は
   items にその番号だけが入っている。 */
function keysOf(a){
  if(a.items && a.items.length) return a.items.map(String);
  var out = [];
  for(var n = a.from; n <= a.to; n++) out.push(String(n));
  return out;
}
/* 1問の呼び名。

   ふつうは 教材ID + 番号（"english/core:12"）。
   ただし**にがて集め**の宿題は、番号ではなく項目そのものを指す
   （"jpn:t:懸垂"）。その場合は key がすでに呼び名になっている。 */
function isPicked(a){ return !!(a.items && a.items.length && isNaN(a.items[0])); }
function itemId(a, key){ return isPicked(a) ? key : a.source + ':' + key; }
function total(a){
  if(a.items && a.items.length) return a.items.length;
  return Math.max(0, a.to - a.from + 1);
}

function slot(p, a){
  if(!p.hw) p.hw = {};
  if(!p.hw[a.id]) p.hw[a.id] = {done:{}, startedAt:null, completedAt:null};
  if(!p.hw[a.id].done) p.hw[a.id].done = {};
  return p.hw[a.id];
}

/* ------------------------------------------------------------
   期限まわり
   ------------------------------------------------------------ */
function daysLeft(a){
  /* 残り日数は「今日を含めてあと何日あるか」。期限当日は1日と数える。
     0日と出すと、まだ間に合う生徒に「もう終わり」と見える。 */
  var ms = a.dueAt - Date.now();
  if(ms <= 0) return 0;
  return Math.max(1, Math.ceil(ms / DAY));
}
function overdue(a){ return Date.now() > a.dueAt; }

/* 期限のことば。

   **責める言い方をしない。** 導入して数か月は、講師も生徒も
   運用が固まらない。そこで「期限切れ」「未提出」と並べると、
   うまくいっていないことばかりが目に入り、続かなくなる。
   伝えるべきは「どれから手を付けるか」だけである。 */
function dueLabel(a){
  var d = daysLeft(a);
  if(overdue(a)) return jp('さきに やろう','先に取り組もう');
  if(d <= 1) return '今日まで';
  if(d === 2) return '明日まで';
  return 'あと' + d + '日';
}

function dateLabel(ts){
  var d = new Date(ts);
  return (d.getMonth()+1) + '/' + d.getDate();
}

/* ------------------------------------------------------------
   進み具合とペース配分
   ここが生徒を動かす唯一の仕掛け。飾りは足さない ――
   「あと何語を、あと何日で、だから今日は何語」だけを、正確に出す。
   ------------------------------------------------------------ */
function progress(p, a){
  var s = slot(p, a);
  var tot = total(a);
  var done = 0;
  keysOf(a).forEach(function(k){ if(s.done[k]) done++; });
  return {
    total: tot, done: done, left: Math.max(0, tot - done),
    pct: tot ? (done / tot * 100) : 0,
    completedAt: s.completedAt, startedAt: s.startedAt,
    finished: !!s.completedAt
  };
}

function pace(p, a){
  var pr = progress(p, a);
  var d  = daysLeft(a);
  var over = overdue(a);

  /* 今日の目安。残りを残り日数で割るだけだが、下限を置く。
     「1日2語」と出すと、その2語すら開かない日が続く。 */
  var perDay = 0;
  if(!pr.finished && pr.left > 0){
    perDay = over ? pr.left
           : Math.max(TubeConfig.hwMinPerDay(), Math.ceil(pr.left / Math.max(1, d)));
    perDay = Math.min(perDay, pr.left);
  }

  /* 出された日から期限までを直線で割って、今日までに終わっているべき数。
     これより下なら遅れている。締切の前日に気づかせない。 */
  var span = Math.max(1, a.dueAt - (a.assignedAt || a.dueAt - 7*DAY));
  var past = Math.min(1, Math.max(0, (Date.now() - (a.assignedAt || 0)) / span));
  var expected = Math.round(pr.total * past);
  var behind = !pr.finished && !over && (pr.done < expected - Math.max(2, pr.total*0.08));

  return {
    left: pr.left, done: pr.done, total: pr.total, pct: pr.pct,
    daysLeft: d, overdue: over, perDay: perDay,
    expected: expected, behind: behind, finished: pr.finished
  };
}

/* ------------------------------------------------------------
   出題
   ------------------------------------------------------------ */
/* まだ覚えていない番号。宿題の本体。 */
function fresh(p, a, n){
  var s = slot(p, a), out = [];
  var ks = keysOf(a);
  for(var i = 0; i < ks.length && out.length < n; i++){
    if(!s.done[ks[i]]) out.push(ks[i]);
  }
  return out;
}

/* 覚えたことにしたが、間隔があいて戻ってきた番号。 */
function due(p, a){
  var s = slot(p, a), now = Date.now(), out = [];
  keysOf(a).forEach(function(key){
    if(!s.done[key]) return;
    var c = p.cards[itemId(a, key)];
    if(c && c.due <= now) out.push(key);
  });
  return out;
}

/* 今日ぶんの並び。復習を先に出して、そのあと新しい番号。
   逆にすると、疲れたころに復習が残って捨てられる。 */
function queue(p, a){
  var pc = pace(p, a);
  var rev = due(p, a);
  var nw  = fresh(p, a, pc.perDay);
  return rev.concat(nw).map(function(key){
    /* **にがて集めは、冊子の番号ではなく項目そのもの。**
       もとの札をそのまま出す。番号として出すと
       「No.0 を冊子でひいて」という、誰にも引けない問いになる
       （実際そう出た）。札が見つからないときだけ番号の形に落ちる。 */
    if(isPicked(a) && window.TubeContent){
      var it = TubeContent.get(key);
      if(it){
        var o = {};
        for(var k in it) o[k] = it[k];
        o.hwOf = a;              /* この札がどの宿題の分か */
        o.hwKey = key;
        return o;
      }
    }
    return {t:'hw', key:key, id:itemId(a, key),
            no:isPicked(a) ? 0 : Number(key), a:a};
  });
}

/* ------------------------------------------------------------
   採点
   g: 1 まだ / 3 覚えた / 4 かんたん
   「まだ」の番号は done にしない ―― 押しただけで宿題が終わっては
   意味がない。覚え直すまで残る。
   ------------------------------------------------------------ */
function grade(p, a, key, g){
  TubeSRS.grade(p, itemId(a, key), g);
  mark(p, a, key, g);
}

/* 宿題の進み具合だけを記録する。**札の間隔は動かさない。**
   にがて集めの札は、ふつうの札としてすでに採点されている。
   ここでもう一度 SRS を回すと、1回答えただけで2回ぶん進む。 */
function mark(p, a, key, g){
  var s = slot(p, a);
  if(!s.startedAt) s.startedAt = Date.now();
  if(g >= 3) s.done[key] = 1;
  else delete s.done[key];
  recompute(p, a);
}

/* 全部終えたか。終えた瞬間だけ記録し、あとから範囲が広がったら外す。 */
function recompute(p, a){
  var s = slot(p, a);
  var pr = progress(p, a);
  if(pr.done >= pr.total && pr.total > 0){
    if(!s.completedAt) s.completedAt = Date.now();
  }else{
    s.completedAt = null;
  }
  return s;
}

/* 今日この宿題で何問答えたか（画面に出す用） */
function todayCount(p, a){
  var s = slot(p, a), n = 0, k = TubeSRS.dayKey();
  keysOf(a).forEach(function(key){
    var c = p.cards[itemId(a, key)];
    if(c && c.seen && TubeSRS.dayKey(c.seen) === k) n++;
  });
  return n;
}

/* 表に出す順。期限が近いものを上に、終わったものを下に。 */
function sorted(p){
  return all().sort(function(x, y){
    var fx = progress(p, x).finished ? 1 : 0;
    var fy = progress(p, y).finished ? 1 : 0;
    return (fx - fy) || (x.dueAt - y.dueAt);
  });
}

/* ------------------------------------------------------------
   紙の宿題が「おわった」か

   ノートの宿題は、アプリからは解いたかどうかが見えない。
   見えるのは2つだけ ―― **写真を出した**か、**講師が1以上の評価を付けた**か。
   どちらも無いものを「おわった」にしない。

   （前は生徒が自分で「おわった」を押せた。押しても何も残らないので、
     やったかどうかが先生にも本人にも分からなかった。いまは押すのは「提出する」。）

   写真を出したかは、画面が /submissions/mine から取って setSubs で渡す。
   宿題の側でサーバに聞きに行かない（聞き方を2か所に持たない）。
   ------------------------------------------------------------ */
var subs = {};         // {宿題ID: {at(秒), files, seen, note}}
function setSubs(m){ subs = m || {}; }

/* ------------------------------------------------------------
   授業1回ぶんの紙の宿題は、1つの束（写真は1回、先生の印も1つ）。

   1回の授業から紙の宿題が2〜3件出る（予習シリーズと演習問題集、上位の上乗せ）。
   1件ずつ写真を出させると週に10回以上の提出になり、続かない。
   束の鍵は「コース#回」。写真を出す先（代表）は、上乗せでない件のうち
   ID のいちばん小さいもの ―― 講師のチェック表（ui-teacher.js paperOf）も同じ決まり。
   「出すだけ」の宿題（graded:false）は束に入れない（出さない・印も付けない）。
   ------------------------------------------------------------ */
function bundleKey(a){
  var ls = (a && a.lesson) || {};
  return (a && a.route === 'paper' && a.graded !== false && ls.key) ? ls.key + '#' + ls.n : '';
}
function mates(a){
  var k = bundleKey(a);
  if(!k) return [a];
  return list.filter(function(x){ return bundleKey(x) === k; }).sort(function(x, y){
    return (x.extra ? 1 : 0) - (y.extra ? 1 : 0) || (x.id < y.id ? -1 : x.id > y.id ? 1 : 0);
  });
}
function head(a){
  var ms = mates(a);
  return ms.filter(function(x){ return !x.extra; })[0] || ms[0] || a;
}

function paperDone(p, a){
  var h = head(a);
  return !!(subs[h.id] || subs[a.id] || (a.rated && a.rated.v >= 1));
}

/* 終わったか。紙は paperDone、アプリは全部の番号を終えたか。**判定はここだけ。** */
function finished(p, a){
  return a.route === 'paper' ? paperDone(p, a) : progress(p, a).finished;
}

/* ------------------------------------------------------------
   後回しにしがちな教科

   同じ日が期限の宿題が3つ並んだとき、どれから出すか。
   **その子が いつも遅れる教科を先に出す。**
   得意な教科から出すと、苦手な教科が毎回いちばん後ろに回り、
   いつまでも手が付かない。積み残しはそこに溜まる。

   数え方は「期限が過ぎた宿題のうち、期限までに終わらなかった割合」。
   1件で決めつけないよう、少ないうちは 0.5（ふつう）に寄せる。
   ------------------------------------------------------------ */
function tendency(p){
  var now = Date.now(), by = {};
  all().forEach(function(a){
    if(!a.dueAt || a.dueAt > now) return;        // まだ期限が来ていない
    var s = subjectKey(a);
    var g = by[s] || (by[s] = {n:0, late:0});
    g.n++;
    var rec = (p.hw || {})[a.id] || {};
    var fin = finished(p, a);
    var sb = subs[a.id];
    var at = rec.completedAt || (sb && sb.at ? (sb.at < 1e12 ? sb.at * 1000 : sb.at) : 0);
    if(!fin || (at && at > a.dueAt)) g.late++;
  });
  var out = {};
  Object.keys(by).forEach(function(k){
    out[k] = (by[k].late + 1) / (by[k].n + 2);   // 少ないうちは 0.5 寄り
  });
  return out;
}

function subjectKey(a){
  return (a.lesson && a.lesson.key && a.lesson.key.indexOf(':') > 0)
    ? a.lesson.key.split(':')[1]
    : ((a.source && (global.TubeContent
        ? (TubeContent.booklet(a.source) || {}).subject : '')) || '?');
}

/* きょうやる順。**ランダムにしない。順に出す。**

   1. 期限が過ぎている／近いものが先（動かせない事実なので、これが一番）
   2. 同じ日が期限なら、**後回しにしがちな教科**を先に
   3. それも同じなら 教科名で固定（開くたびに順が変わらないように）

   期限を「日」でまとめてから 傾向を見るのが要点。秒まで見て並べると、
   期限がわずかに違うだけで傾向が効かなくなる。 */
function todayQueue(p, list){
  var now = Date.now(), DAY = 86400000, tend = tendency(p);
  var can = (list || []).filter(function(a){ return !finished(p, a); });
  return can.sort(function(x, y){
    var bx = Math.floor(((x.dueAt || 0) - now) / DAY);
    var by2 = Math.floor(((y.dueAt || 0) - now) / DAY);
    if(bx !== by2) return bx - by2;
    var tx = tend[subjectKey(x)] || 0.5, ty = tend[subjectKey(y)] || 0.5;
    if(tx !== ty) return ty - tx;                // 遅れがちな教科が先
    var sx = subjectKey(x), sy = subjectKey(y);
    if(sx !== sy) return sx < sy ? -1 : 1;
    return (x.id < y.id) ? -1 : 1;
  });
}

/* 手を付ける必要があるもの（未完了、または復習が来ているもの）。 */
/* いま画面に出す宿題。

   紙の宿題は「おわった」状態にならない ―― アプリは達成を観測しないので、
   終わったかどうかを知りようがない。そのままにすると、3か月前の宿題が
   ずっと画面に残り、生徒は一覧を見なくなる。
   期限から1週間たったら落とす。時間だけが手がかりになる。 */
var PAPER_GRACE = 7 * 24 * 60 * 60 * 1000;

function active(p){
  var now = Date.now();
  return sorted(p).filter(function(a){
    if(a.route === 'paper') return !a.dueAt || (now - a.dueAt) < PAPER_GRACE;
    var pr = progress(p, a);
    if(!pr.finished) return true;
    return due(p, a).length > 0;
  });
}

global.TubeHomework = {
  setAll:setAll, all:all, byId:byId, source:source,
  keysOf:keysOf, itemId:itemId, total:total,
  progress:progress, pace:pace, queue:queue, grade:grade, mark:mark,
  recompute:recompute, fresh:fresh, due:due, todayCount:todayCount,
  sorted:sorted, active:active,
  todayQueue:todayQueue, tendency:tendency, subjectKey:subjectKey,
  paperDone:paperDone, finished:finished, setSubs:setSubs,
  bundleKey:bundleKey, mates:mates, head:head,
  daysLeft:daysLeft, overdue:overdue, dueLabel:dueLabel, dateLabel:dateLabel
};

})(window);
