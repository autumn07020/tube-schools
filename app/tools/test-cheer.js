/* がんばりの積み上げと先生のことば（app/js/cheer.js）の検査。ブラウザ無しで動く（リポジトリの一番上で）。
     /System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc app/tools/test-cheer.js */
var window = this;
load('app/js/cheer.js');
var C = window.TubeCheer, N = 0, BAD = 0, DAY = 864e5;
function ok(c, name, d){ N++; if(!c){ BAD++; print('  × ' + name + (d !== undefined ? '  ' + d : '')); } }
function J(x){ return JSON.stringify(x); }

var m = C.milestone(0);
ok(m.prev === 0 && m.next === 1 && m.left === 1, 'はじめの節目は1', J(m));
m = C.milestone(12);
ok(m.prev === 10 && m.next === 15 && m.left === 3 && Math.abs(m.frac - 0.4) < 1e-9, '12 は 10 と 15 のあいだ', J(m));
ok(C.milestone(1).next === 3 && C.milestone(3).next === 5, '1 の次は3、3 の次は5');
m = C.milestone(1234);
ok(m.prev === 1000 && m.next === 1500, '1000 を越えたら 500 ごと', J(m));
ok(C.milestone(-3).count === 0 && C.milestone('x').count === 0 && C.milestone(null).next === 1, '崩れた数は0');

var now = new Date(2026, 8, 11, 12).getTime();          /* 2026-09-11（金）12時 */
ok(C.crossed([now - 10 * DAY, now - 2 * DAY, now - DAY], now) === 3, '7日のうちに 1→3 を越えた');
ok(C.crossed([now - 10 * DAY, now - 9 * DAY, now - 8 * DAY], now) === null, '越えたのが7日より前なら出さない');
ok(C.crossed([(now - DAY) / 1000], now) === 1, '秒の時刻も受ける');
ok(C.crossed([now + DAY], now) === null && C.crossed(null, now) === null && C.crossed([now], 0) === null, 'これから先・無い入力');

var hw = {
  all:[{id:'a1', route:'paper', lesson:{key:'k', n:1}}, {id:'a2', route:'paper', lesson:{key:'k', n:1}},
       {id:'p', route:'paper', graded:false}, {id:'x', route:'app'}, null, {title:'no id'}],
  bundleKey:function(a){ return a.lesson ? a.lesson.key + '#' + a.lesson.n : null; },
  head:function(a){ return a.id === 'a2' ? {id:'a1', route:'paper'} : a; }
};
var rs = C.rows(hw);
ok(rs.length === 2 && rs[0].id === 'a1' && rs[1].id === 'x', '束は1件、出すだけと崩れた行は数えない', J(rs.map(function(a){ return a.id; })));
ok(C.rows(null).length === 0 && C.rows({all:'x'}).length === 0, '無い入力');

var pr = C.praise([{rated:{v:5, at:now}}, {rated:{v:4, at:now / 1000}}, {rated:{v:3}}, {rated:{v:0}}, {}, null]);
ok(pr.great.length === 1 && pr.good.length === 2 && pr.good[1] === now, 'よくできました1・できました以上2（秒の時刻も）', J(pr));

function due(daysAgo){ return now - daysAgo * DAY; }
var list = [{id:'w1', dueAt:due(0)}, {id:'l1', dueAt:due(6)}, {id:'l2', dueAt:due(5)},
            {id:'o1', dueAt:due(13)}, {id:'q1', dueAt:due(20)}, {id:'f1', dueAt:due(-10)}];
var fin = {l1:1, l2:1, q1:1};
var w = C.weeks(list, function(a){ return !!fin[a.id]; }, now);
ok(w.done === 2 && w.run === 1, '終えた週2・続けて1（2週前が途中で切れる。今週は途中なので数えない）', J({done:w.done, run:w.run}));
ok(w.list.length === 4 && !w.list.some(function(x){ return x.mon > now; }), '来週より先の週は入れない');
fin.w1 = 1; fin.o1 = 1;
w = C.weeks(list, function(a){ return !!fin[a.id]; }, now);
ok(w.done === 4 && w.run === 4 && w.times.length === 4, '今週も終えれば数える', J({done:w.done, run:w.run}));
ok(C.weeks(null, null, now).done === 0 && C.weeks([{id:'z'}], null, now).list.length === 0, '期限の無い宿題・無い入力');

var subs = {s1:{note:'  見直しの跡があってよいです。 ', seen:now - DAY}, s2:{note:''}, s3:{note:'ていねい', at:(now - 3 * DAY) / 1000},
            s4:{note:'字をもう少し大きく', seen:now}};
var ws = C.words([{id:'s1', title:'英語', rated:{v:5}}, {id:'s2'}, {id:'s3', title:'数学'}, {id:'s9'}, {id:'s4', rated:{v:3}}], subs, 5);
ok(ws.length === 2 && ws[0].id === 's1' && ws[0].text === '見直しの跡があってよいです。' && ws[0].v === 5 && ws[1].id === 's3',
   '先生のことば：前向きなものだけ（空と、3以下の評価のものは出さない）', J(ws.map(function(x){ return [x.id, x.text]; })));
ws = C.words([{id:'n', rated:{v:4}}, {id:'o', rated:{v:5}}, {id:'u'}],
             {n:{note:'できました', seen:now}, o:{note:'この調子', seen:now - 2 * DAY}, u:{note:'評価なし', seen:now}}, 5, now);
ok(ws.map(function(x){ return x.id; }).join(',') === 'o,n,u', '評価の高い順、評価の無いものは「できました」の下', J(ws.map(function(x){ return x.id; })));
ws = C.words([{id:'old', rated:{v:5}}, {id:'new', rated:{v:4}}], {old:{note:'昔のほめ', seen:now - 60 * DAY}, new:{note:'最近', seen:now - DAY}}, 5, now);
ok(ws.length === 1 && ws[0].id === 'new', '5週より前のことばは、直近にあれば使わない', J(ws.map(function(x){ return x.id; })));
ws = C.words([{id:'old', rated:{v:5}}], {old:{note:'昔のほめ', seen:now - 60 * DAY}}, 5, now);
ok(ws.length === 1 && ws[0].id === 'old', '直近に1つも無ければ、前のものを使う');
ok(C.words(null, null).length === 0 && C.words([{id:'a'}], null).length === 0, '無い入力');

var sp = C.strip(list, function(a){ return !!fin[a.id]; }, now, 6);
ok(sp.length === 6 && sp[5].now && sp[5].state === 'fin' && sp[4].state === 'fin' && sp[3].state === 'fin' && sp[2].state === 'fin' &&
   sp[1].state === 'blank' && sp[0].state === 'blank',
   '実績の帯：右端が今週、宿題の無い週は blank', J(sp.map(function(w){ return w.state; })));
fin.l2 = 0;
sp = C.strip(list, function(a){ return !!fin[a.id]; }, now, 6);
ok(sp[4].state === 'part' && sp[4].done === 1 && sp[4].total === 2, '一部だけ終えた週は part', J(sp[4]));
ok(C.strip(null, null, now, 3).every(function(w){ return w.state === 'blank'; }) && C.strip(list, null, 0).length === 0, '無い入力');
var dk = function(t){ var d = new Date(t); return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate(); };
var hist = {}; hist[dk(now)] = {n:5, ok:4}; hist[dk(now - 2 * DAY)] = {n:3, ok:3}; hist[dk(now - 9 * DAY)] = {n:9, ok:9}; hist[dk(now - DAY)] = {n:0};
ok(C.weekDays(hist, now, dk) === 2, '今週（月曜〜今日）にやった日の数。0問の日と先週は数えない', C.weekDays(hist, now, dk));
ok(C.weekDays(null, now, dk) === 0 && C.weekDays(hist, 0, dk) === 0, '無い入力');

print(BAD ? ('×が' + BAD + '件（' + N + '件中）') : ('すべて通った。（' + N + '件）'));
