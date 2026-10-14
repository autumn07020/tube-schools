/* ============================================================
   がんばりの積み上げと、先生のことば（TubeCheer）
   ------------------------------------------------------------
   **DOM に触らない純粋な関数だけ。** 入力は宿題の一覧（TubeHomework の形）と
   提出の記録（submissions）と、「終わったか」を答える関数。落ちず、
   同じ入力には同じ結果を返す。検査は app/tools/test-cheer.js（JavaScriptCore）。

   講師の手間は増やさない（本人の判断）。**すでにあるものだけ**で作る：
     5段階の評価（a.rated の v と at）／先生のひとこと（提出の note）／
     宿題が終わったか／毎日テストを続けた日
   ============================================================ */
(function(global){
'use strict';

var DAY = 864e5;
/* 節目。はじめは近く、だんだん遠く ―― 始めたばかりの子にも1つ目がすぐ来る。 */
var STEPS = [1, 3, 5, 10, 15, 20, 30, 40, 50, 75, 100, 150, 200, 300, 500, 750, 1000];

/* 秒でもミリ秒でも受ける。無い・崩れていれば 0。 */
function ms(t){
  t = Number(t);
  if(!isFinite(t) || t <= 0) return 0;
  return t < 1e12 ? t * 1000 : t;
}

/* いまの数と、ひとつ前・次の節目。1000 を越えたら 500 ごと。 */
function milestone(count, steps){
  steps = (Array.isArray(steps) && steps.length) ? steps : STEPS;
  count = Math.max(0, Math.floor(Number(count) || 0));
  var prev = 0, next = null;
  for(var i = 0; i < steps.length; i++){
    if(steps[i] <= count) prev = steps[i];
    else { next = steps[i]; break; }
  }
  if(next === null){
    var last = steps[steps.length - 1];
    prev = last + Math.floor((count - last) / 500) * 500;
    next = prev + 500;
  }
  return {count:count, prev:prev, next:next, left:next - count,
          frac:(next > prev) ? (count - prev) / (next - prev) : 0};
}

/* この期間（既定7日）に越えた節目のうち、いちばん大きいもの。無ければ null。
   times … その数が1つ増えた時刻の並び（ミリ秒・秒どちらでも） */
function crossed(times, now, windowMs, steps){
  steps = (Array.isArray(steps) && steps.length) ? steps : STEPS;
  now = ms(now);
  if(!now) return null;
  windowMs = windowMs || 7 * DAY;
  var ts = (Array.isArray(times) ? times : []).map(ms).filter(function(t){ return t && t <= now; });
  var before = ts.filter(function(t){ return t <= now - windowMs; }).length;
  var after = ts.length;
  var hit = null;
  steps.forEach(function(s){ if(before < s && s <= after) hit = s; });
  return hit;
}

/* 数える宿題の並び（宿題のタブと同じ数え方）。束は代表の1件、「出すだけ」の紙は数えない。
   hw … {all:[宿題], bundleKey:function(a), head:function(a)}（無い関数は使わない） */
function rows(hw){
  hw = hw || {};
  var seen = {}, out = [];
  (Array.isArray(hw.all) ? hw.all : []).forEach(function(a){
    if(!a || typeof a !== 'object' || !a.id) return;
    if(a.route === 'paper' && a.graded === false) return;
    var k = typeof hw.bundleKey === 'function' ? hw.bundleKey(a) : null;
    if(k){
      if(seen[k]) return;
      seen[k] = 1;
      a = (typeof hw.head === 'function' && hw.head(a)) || a;
    }
    out.push(a);
  });
  return out;
}

/* 先生の評価を数える。great … よくできました（5）、good … できました以上（4〜5）。
   それぞれ、付いた時刻の並び（節目を越えた時期を出すため）。 */
function praise(list){
  var great = [], good = [];
  (Array.isArray(list) ? list : []).forEach(function(a){
    var r = a && a.rated;
    var v = (r && typeof r.v === 'number') ? r.v : null;
    if(v === null) return;
    var t = ms(r.at) || ms(a.assignedAt) || ms(a.dueAt);
    if(v >= 5) great.push(t);
    if(v >= 4) good.push(t);
  });
  return {great:great, good:good};
}

function monday(t){
  var d = new Date(t);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - (d.getDay() + 6) % 7);
  return d.getTime();
}

/* 週（月曜〜日曜）ごとに、その週が期限の宿題がぜんぶ終わったか。
     done  … 終えた週の数（今週も、終わっていれば数える）
     run   … 続けて終えた週。今週がまだ途中なら、数えずに先週から数える（切らない）
     times … 終えた週の時刻（その週の終わり。今週は now）
   宿題の無い週（休み）は並びに入らないので、続きは切れない。 */
function weeks(list, finished, now){
  now = ms(now);
  var by = {};
  (Array.isArray(list) ? list : []).forEach(function(a){
    var due = ms(a && a.dueAt);
    if(!due) return;
    var m = monday(due);
    var w = by[m] || (by[m] = {mon:m, total:0, done:0});
    w.total++;
    if(typeof finished === 'function' && finished(a)) w.done++;
  });
  var cur = now ? monday(now) : 0;
  var ws = Object.keys(by).map(Number).sort(function(a, b){ return a - b; })
    .map(function(k){ return by[k]; })
    .filter(function(w){ return !cur || w.mon <= cur; });
  ws.forEach(function(w){ w.fin = w.total > 0 && w.done === w.total; });
  var run = 0;
  for(var i = ws.length - 1; i >= 0; i--){
    if(ws[i].mon === cur && !ws[i].fin) continue;
    if(ws[i].fin) run++; else break;
  }
  return {done:ws.filter(function(w){ return w.fin; }).length, run:run,
          times:ws.filter(function(w){ return w.fin; }).map(function(w){
            return Math.min(now || Infinity, w.mon + 7 * DAY - 1); }),
          list:ws};
}

/* これまでの実績の帯 ―― 直近 count 週（今週を右端に）を1週1マスで。
     state  fin   … その週の分をぜんぶ終えた
            part  … 一部だけ終えた
            none  … 出ていたが終えていない
            blank … 宿題の無かった週（休みなど）
     now    今週
   数え方は weeks() と同じ（期限の週で束ね、終わったかは finished が答える）。 */
function strip(list, finished, now, count){
  now = ms(now);
  if(!now) return [];
  count = Math.max(1, Math.floor(count || 12));
  var by = {};
  (Array.isArray(list) ? list : []).forEach(function(a){
    var due = ms(a && a.dueAt);
    if(!due) return;
    var m = monday(due);
    var w = by[m] || (by[m] = {total:0, done:0});
    w.total++;
    if(typeof finished === 'function' && finished(a)) w.done++;
  });
  var cur = monday(now), out = [];
  for(var i = count - 1; i >= 0; i--){
    var mon = monday(cur - i * 7 * DAY);      /* 夏時間の切り替えをまたいでも月曜に丸める */
    var w = by[mon];
    out.push({mon:mon, now:i === 0, total:w ? w.total : 0, done:w ? w.done : 0,
              state:!w ? 'blank' : (w.done === w.total ? 'fin' : w.done > 0 ? 'part' : 'none')});
  }
  return out;
}

/* 今週（月曜〜今日）に毎日テストをやった日の数。hist は {日付の鍵: {n, ok}}、
   dayKey(ms) は日付の鍵を返す関数（TubeSRS.dayKey）。 */
function weekDays(hist, now, dayKey){
  now = ms(now);
  if(!now || typeof dayKey !== 'function') return 0;
  var mon = monday(now), n = 0;
  for(var t = mon; t <= now; t += DAY){
    var h = hist && hist[dayKey(t)];
    if(h && (h.n || h.done)) n++;
  }
  return n;
}

/* 先生のことば（提出に付いたひとこと）。**前向きなものだけ、前向きな順**に limit 件。
     前向き … 評価が4以上（できました・よくできました）か、評価の無い提出のひとこと。
              3以下（もう少し・がんばろう・やり直し）のひとことは入れない ――
              「字をもう少し大きく」が大きく出ると、やる気が下がる（本人）。直す所は教科の返事の中で読む
     順     … 評価の高い順、同じなら新しい順（評価の無いものは「できました」の下）
     now    … あれば直近5週（35日）の中から選ぶ。その間に1つも無ければ、それより前も見る */
var POSITIVE = 4;
function words(list, subs, limit, now){
  var out = [];
  (Array.isArray(list) ? list : []).forEach(function(a){
    var s = subs && a && subs[a.id];
    var text = (s && typeof s.note === 'string') ? s.note.trim() : '';
    if(!text) return;
    var v = (a.rated && typeof a.rated.v === 'number') ? a.rated.v : null;
    if(v !== null && v < POSITIVE) return;
    out.push({id:a.id, text:text, title:String(a.title || ''), v:v, s:s,
              at:ms(s.seen) || ms(a.rated && a.rated.at) || ms(s.at) || ms(a.assignedAt), a:a});
  });
  now = ms(now);
  if(now){
    var recent = out.filter(function(x){ return x.at >= now - 35 * DAY; });
    if(recent.length) out = recent;
  }
  var rank = function(x){ return x.v === null ? POSITIVE - 0.5 : x.v; };
  out.sort(function(x, y){ return rank(y) - rank(x) || y.at - x.at; });
  return out.slice(0, Math.max(1, limit || 20));
}

global.TubeCheer = {STEPS:STEPS, POSITIVE:POSITIVE, ms:ms, milestone:milestone, crossed:crossed,
                    rows:rows, praise:praise, weeks:weeks, strip:strip, weekDays:weekDays,
                    words:words, monday:monday};
})(typeof window !== 'undefined' ? window : this);
