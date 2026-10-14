/* ============================================================
   SRS ENGINE  (SM-2)
   ------------------------------------------------------------
   前身プロジェクトで実証済みのものをそのまま移植した。DOMには触らない。
   状態は引数で受け取り、引数を書き換えて返す ―― 画面と切り離してあるので
   検証スクリプトから1日分を無人で走らせられる。
   ============================================================ */
(function(global){
"use strict";

var DAY = 864e5;

/* ------------------------------------------------------------
   間隔の上限 ―― **単元確認テストの周期に合わせる。**

   もとは前身プロジェクト（IELTS の単語帳）からの移植で、上限が
   400日だった。何年もかけて語彙を保つならそれでよい。
   だが TUBE study が狙うのは **5週ごとの単元確認テスト**である。
   「むずかしい 3.8ヶ月」と「わかった 5ヶ月」は、どちらもテストを
   何回も飛び越える。生徒にとって選ぶ意味が無いし、そもそも
   テストの前に出てこない。**忘却曲線に乗せる先が違っていた。**

   そこで上限を、テストの周期の中に収める。

     むずかしい … 1週間  … 同じ週のうちにもう一度
     できた     … 3週間  … テストの前にもう一度（＝定着の目安21日）
     かんたん   … 5週間  … 次の周まで（次のテストの範囲へ持ち越す）

   上限を**ボタンごとに変える**のは、伸びきった札で3つが同じ数字に
   ならないようにするためでもある。1つの上限にすると、どれを押しても
   「35日」と出て、また選ぶ意味が無くなる（いま起きているのと同じこと）。

   35 の出どころは server/lessons.py の CYCLE = 5（週1回×5回で1周）。
   周期を変えるときは両方を直すこと ―― 検査が食い違いを見張っている。
   ------------------------------------------------------------ */
var CYCLE_DAYS = 35;
var MAX_IV = {2: 7, 3: 21, 4: CYCLE_DAYS};

/* ------------------------------------------------------------
   採点  g: 1 Again / 2 Hard / 3 Good / 4 Easy
   ------------------------------------------------------------ */
function grade(p, id, g){
  var c = p.cards[id];
  var fresh = !c;
  if(!c) c = p.cards[id] = {iv:0, ef:2.5, due:0, reps:0, lapse:0, seen:0};
  c.reps++; c.seen = Date.now();

  if(g === 1){
    c.lapse++;
    c.ef  = Math.max(1.3, c.ef - 0.20);
    c.iv  = fresh ? 0 : 1;
    c.due = Date.now() + (fresh ? 60e3 : 10*60e3);   // 今のセッション内 / 10分後
  }else{
    if(fresh)         c.iv = (g===4) ? 4 : 1;
    else if(c.iv===0) c.iv = (g===2) ? 1 : (g===3) ? 2 : 4;
    else              c.iv = Math.max(c.iv+1, Math.round(
                        c.iv * (g===2 ? 1.2 : g===3 ? c.ef : c.ef*1.32)));
    c.ef  = Math.min(3.2, Math.max(1.3, c.ef + (g===2 ? -0.15 : g===3 ? 0 : 0.15)));
    c.iv  = Math.min(c.iv, MAX_IV[g] || CYCLE_DAYS);
    c.due = Date.now() + c.iv*DAY;
  }

  bumpXp(p, g===1 ? 2 : 4);
  var k = dayKey();
  var h = p.hist[k] || (p.hist[k] = {n:0, ok:0});
  h.n++; if(g > 1) h.ok++;
  return c;
}

/* 「もう知っている」。既知語を捨てるための導線。次の周まで飛ばす。
   ここも周期を超えない ―― 超えるとテスト範囲から丸ごと外れる。 */
function markKnown(p, id){
  p.cards[id] = {iv:CYCLE_DAYS, ef:2.8, due:Date.now()+CYCLE_DAYS*DAY,
                 reps:1, lapse:0,
                 seen:Date.now(), known:1};
  bumpXp(p, 1);
  var k = dayKey();
  var h = p.hist[k] || (p.hist[k] = {n:0, ok:0});
  h.n++; h.ok++;
}

function bumpXp(p, n){
  p.xp = (p.xp||0) + n;
  var k = dayKey();
  if(p.lastDay !== k){
    p.lastDay = k;
    p.streak = (p.streak||0) + 1;
    if(p.streak > (p.best||0)) p.best = p.streak;
  }
}

/* 次にどれだけ先送りされるかの予告。ボタンに出す。 */
function nextIv(p, id, g){
  var c = p.cards[id];
  if(g === 1) return c ? '10分' : '1分';
  var iv;
  if(!c)             iv = (g===4) ? 4 : 1;
  else if(c.iv===0)  iv = (g===2) ? 1 : (g===3) ? 2 : 4;
  else               iv = Math.max(c.iv+1, Math.round(
                       c.iv * (g===2 ? 1.2 : g===3 ? c.ef : c.ef*1.32)));
  return ivLabel(Math.min(iv, MAX_IV[g] || CYCLE_DAYS));
}
/* 上限が5週なので、月や年は出てこない。日と週だけで書く。 */
function ivLabel(iv){
  if(iv < 1)   return '10分';
  if(iv < 14)  return iv + '日';
  return Math.round(iv / 7) + '週間';
}

/* 前の上限（400日）で先へ飛ばされた札を、周期の中に連れ戻す。

   直しても、すでに「5ヶ月後」に置かれた札はそのまま5ヶ月出てこない。
   古い記録を持っている生徒だけ、直したはずのものが直らない ――
   いちばん気づきにくい形なので、読み込むときに一度ならす。

   **同じ日にまとめて戻さない。** 何百枚も一度に出てくると、
   その日だけ終わらない量になって、続かなくなる。札ごとに散らす
   （端末をまたいでも同じ日になるよう、乱数ではなく札の名前から決める）。 */
function fitToCycle(cards){
  var now = Date.now(), moved = 0;
  Object.keys(cards || {}).forEach(function(id){
    var c = cards[id];
    if(!c || (c.iv || 0) <= CYCLE_DAYS) return;
    c.iv = CYCLE_DAYS;
    var h = 0;
    for(var i = 0; i < id.length; i++){
      h = ((h << 5) - h + id.charCodeAt(i)) | 0;
    }
    c.due = Math.min(c.due || Infinity, now + (1 + (h >>> 0) % CYCLE_DAYS) * DAY);
    moved++;
  });
  return moved;
}

/* ------------------------------------------------------------
   日付。午前4時で区切る（夜更かしの学習は前日に数える）。
   ------------------------------------------------------------ */
function dayKey(d){
  d = new Date(d || Date.now());
  d.setHours(d.getHours() - 4);
  return d.getFullYear() + '-' +
         String(d.getMonth()+1).padStart(2,'0') + '-' +
         String(d.getDate()).padStart(2,'0');
}

function rollDay(p){
  var k = dayKey();
  if(p.dayKey === k) return false;
  /* 連続日数は「昨日やったか」で判定する。飛んだら0に戻す。 */
  if(p.dayKey){
    var y = dayKey(Date.now() - DAY);
    if(p.dayKey !== y) p.streak = 0;
  }
  p.dayKey   = k;
  p.newToday = 0;
  p.sessDone = {};        // 種別 -> その日に出した新出の数
  return true;
}

/* ------------------------------------------------------------
   出題対象の選択
   order … TubeContent.orderFor(level) が返す、そのレベルの教材
   ------------------------------------------------------------ */
function dueCards(p, order){
  var now = Date.now();
  var inLevel = {};
  order.forEach(function(c){ inLevel[c.id] = c; });
  return Object.keys(p.cards)
    .filter(function(id){ return inLevel[id] && p.cards[id].due <= now; })
    .map(function(id){ return inLevel[id]; })
    .sort(function(a,b){ return p.cards[a.id].due - p.cards[b.id].due; });
}

function newCards(p, order, track, n){
  var out = [];
  for(var i=0; i<order.length && out.length<n; i++){
    var c = order[i];
    if(p.cards[c.id]) continue;
    if(track && c.t !== track) continue;
    out.push(c);
  }
  return out;
}

/* 1日の割り当て。1未満は「1日おきに1つ」の意味。
   文法のように、1つ入れたらその日は寝かせたい種別のために用意してある。 */
function quota(rate){
  if(!rate) return 0;
  if(rate >= 1) return Math.round(rate);
  return Math.floor((Date.now() - 4*36e5)/DAY) % 2 === 0 ? 1 : 0;
}

/* その日に出す分の内訳。
   cfg は TubeConfig.plan() が返すもの（daily / maxRev / tracks）。
   種別を決め打ちにしないので、科目が増えてもここは変えなくてよい。 */
function plan(p, cfg, order){
  rollDay(p);
  var d = cfg.daily || {};
  var tracks = cfg.tracks || Object.keys(d);
  var due = dueCards(p, order);
  var dueBy = {};
  due.forEach(function(c){ dueBy[c.t] = (dueBy[c.t]||0) + 1; });

  if(!p.sessDone) p.sessDone = {};
  var fresh = {}, freshN = 0;
  tracks.forEach(function(t){
    var want = quota(d[t] || 0) - (p.sessDone[t] || 0);
    fresh[t] = newCards(p, order, t, Math.max(0, want));
    freshN += fresh[t].length;
  });

  var cap = cfg.maxRev == null ? 160 : cfg.maxRev;
  var rev = Math.min(due.length, cap);
  return {
    due:due, dueBy:dueBy, fresh:fresh, tracks:tracks,
    reviews:rev, freshCount:freshN,
    total:rev + freshN,
    overflow:Math.max(0, due.length - cap)
  };
}

/* 復習の中に新出を等間隔で差し込む。新出だけを固めて出すと、
   後半が単調な復習だけになって離脱する。 */
function buildQueue(p, cfg, order){
  var pl = plan(p, cfg, order);
  var rev = pl.due.slice(0, cfg.maxRev == null ? 160 : cfg.maxRev);
  var fresh = [];
  var pools = pl.tracks.map(function(t){ return (pl.fresh[t] || []).slice(); });
  var i = 0;
  while(pools.length && pools.some(function(x){ return x.length; })){
    var q = pools[i % pools.length];
    if(q.length) fresh.push(q.shift());
    i++;
  }
  var out = [];
  var step = fresh.length ? Math.max(1, Math.floor(rev.length/(fresh.length+1))) : 1;
  var fi = 0;
  rev.forEach(function(c, idx){
    out.push(c);
    if(fi < fresh.length && (idx+1) % step === 0) out.push(fresh[fi++]);
  });
  while(fi < fresh.length) out.push(fresh[fi++]);
  return out;
}

/* ------------------------------------------------------------
   出題形式の自動切替
   定着するほど問い方を難しくする。丸暗記を防ぐための仕掛け。
   ------------------------------------------------------------ */
function vocabMode(p, id, mature){
  var c = p.cards[id];
  if(!c || c.iv < 7)     return 'recog';      // 英語 → 意味
  if(c.iv < (mature||21)) return 'cloze';     // 例文の穴埋め
  return 'produce';                           // 日本語 → 英語を思い出す
}

/* ------------------------------------------------------------
   集計（生徒の進み具合・講師ダッシュボード）
   ------------------------------------------------------------ */
function isMature(p, id, mature){
  var c = p.cards[id];
  return !!(c && c.iv >= (mature||21));
}

function bandStats(p, order, mature){
  var o = {};
  order.forEach(function(c){
    var b = o[c.band] || (o[c.band] = {tot:0, mat:0, lrn:0, t:{}});
    b.tot++;
    var s = p.cards[c.id];
    if(s && s.iv >= (mature||21)) b.mat++;
    else if(s) b.lrn++;
  });
  return o;
}

/* レベルメーター。自己申告値でクランプすると次の帯を8割固めるまで
   針が1ミリも動かず「壊れている」と受け取られる（HANDOVER 5.6）。
   帯の定着度で連続的に駆動し、1項目ごとに前進させる。 */
var ARRIVE = 0.80;
function levelPos(p, cfg, order, mature){
  var bs = bandStats(p, order, mature);
  var bands = cfg.bands || [];
  var pos = 0;
  for(var i=0;i<bands.length;i++){
    var b = bs[bands[i]];
    if(!b || !b.tot) continue;
    var held = b.mat / b.tot;
    if(held >= ARRIVE){ pos = i + 1; }
    else { pos = i + (held / ARRIVE); break; }
  }
  /* 項目の数でも返す。pos/of は「難度の帯のどこまで来たか」なので、
     画面に「おぼえた」として出すと 0.107/1 のような数字になる
     （帯が1つの科目で実際にそう出た）。
     生徒に見せるのは、覚えた項目数と全体の数のほうである。 */
  var mat = 0, tot = 0;
  order.forEach(function(c){
    tot++;
    var st = p.cards[c.id];
    if(st && st.iv >= (mature || 21)) mat++;
  });
  return {pos:pos, of:bands.length, bands:bs,
          mature:mat, total:tot,
          band:bands[Math.min(bands.length-1, Math.floor(pos))] || bands[0]};
}

/* 正答率 ―― その時点までに答えた分の中での出来。

   「覚えた項目 ÷ 単元ぜんぶ」を出すと、始めたばかりの生徒は
   必ず数%になる。1週間まじめにやっても 4% と出る画面では、
   続ける気にならない。**分母は、手をつけた分だけにする。**

   1枚の項目について
     reps  … 答えた回数
     lapse … そのうち「まだ」だった回数
   なので、正解は reps - lapse。これを教科ぶん足し合わせる。

   まだ1問も答えていなければ null を返す。0% とは出さない
   ―― 何もしていないことと、やって間違えたことは違う。 */
function accuracy(p, order){
  var ans = 0, ok = 0, items = 0;
  (order || []).forEach(function(c){
    var s = p.cards[c.id];
    if(!s || !s.reps) return;
    items++;
    ans += s.reps;
    ok  += Math.max(0, s.reps - (s.lapse || 0));
  });
  if(!ans) return null;
  return {pct: Math.round(ok / ans * 100), ok: ok, answered: ans, items: items};
}


function summary(p, order, mature, stuckLapses){
  var answered = 0, days = {}, mat = 0, lrn = 0, stuck = [];
  Object.keys(p.hist||{}).forEach(function(k){
    answered += (p.hist[k].n || 0);
    days[k] = true;
  });
  order.forEach(function(c){
    var s = p.cards[c.id];
    if(!s) return;
    if(s.iv >= (mature||21)) mat++; else lrn++;
    if((s.lapse||0) >= (stuckLapses||3)) stuck.push({id:c.id, lapse:s.lapse, card:c});
  });
  /* 直近14日のうち何日やったか。継続はこの数字がすべて。 */
  var days14 = 0;
  for(var i=0;i<14;i++){
    if(p.hist[dayKey(Date.now() - i*DAY)]) days14++;
  }
  return {answered:answered, totalDays:Object.keys(days).length, days14:days14,
          mature:mat, learning:lrn, seen:mat+lrn, total:order.length,
          stuck:stuck.sort(function(a,b){ return b.lapse - a.lapse; }),
          streak:p.streak||0, best:p.best||0};
}

/* 新出の在庫が何日で尽きるか。尽きる前に教材を足す判断のため。 */
function stockDays(p, cfg, order){
  var d = cfg.daily || {};
  var tracks = cfg.tracks || Object.keys(d);
  var left = {}, per = {}, unseen = 0;
  tracks.forEach(function(t){ left[t] = 0; });
  order.forEach(function(c){
    if(!p.cards[c.id] && (c.t in left)){ left[c.t]++; unseen++; }
  });
  tracks.forEach(function(t){
    per[t] = d[t] > 0 ? Math.floor(left[t]/d[t]) : Infinity;
  });
  var days = tracks.length ? Math.min.apply(null, tracks.map(function(t){ return per[t]; }))
                           : Infinity;
  return {left:left, per:per, days:days, unseen:unseen,
          bottleneck:tracks.filter(function(t){ return per[t] === days; })[0]};
}

global.TubeSRS = {
  quota:quota,
  grade:grade, markKnown:markKnown, nextIv:nextIv, ivLabel:ivLabel,
  fitToCycle:fitToCycle, CYCLE_DAYS:CYCLE_DAYS, MAX_IV:MAX_IV,
  dayKey:dayKey, rollDay:rollDay, plan:plan, buildQueue:buildQueue,
  dueCards:dueCards, newCards:newCards, vocabMode:vocabMode,
  isMature:isMature, bandStats:bandStats, levelPos:levelPos,
  summary:summary, accuracy:accuracy, stockDays:stockDays, DAY:DAY
};

})(window);
