/* 図の部品（app/js/viz.js）の検査。ブラウザ無しで動く（リポジトリの一番上で実行）。
     /System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc app/tools/test-viz.js */
var window = this;
load('app/js/viz.js');
var V = window.TubeViz, N = 0, BAD = 0;
function ok(c, name, d){ N++; if(!c){ BAD++; print('  × ' + name + (d !== undefined ? '  ' + d : '')); } }
function count(s, re){ return (String(s).match(re) || []).length; }

ok(V.unitName({n:3}) === '第3回', '呼び名が無ければ第n回');
ok(V.unitName({n:3, label:''}) === '', '空の呼び名は空');
ok(V.unitText({n:3, label:'', topic:'平面図形'}) === '平面図形', '呼び名の無い教材は単元名だけ');
ok(V.unitText({n:9, label:'5章-3', topic:'直角三角形'}) === '5章-3 直角三角形', '呼び名と単元名');
ok(V.unitTick({label:'5章-3'}) === '5-3' && V.unitTick({label:'例題56-57'}) === '56' &&
   V.unitTick({label:'上 第20回'}) === '20' && V.unitTick({n:6}) === '6', '短い番号');
ok(V.unitName(null) === '' && V.unitText(undefined) === '' && V.unitTick({}) === '', '無い入力でも落ちない');

ok(V.pct(120) === 100 && V.pct(-5) === 0 && V.pct('80') === null && V.pct(NaN) === null && V.pct(69.6) === 70, '0〜100 の整数に');
ok(V.tone(69) === 'y' && V.tone(70) === 'b' && V.tone(null) === 'none', '70% で色が変わる');

var units = [{n:5, topic:'e', und:80}, {n:1, topic:'a', und:60}, {n:3, topic:'総復習', review:true, und:10},
             {n:2, topic:'b', und:null}, {n:4, topic:'d', und:75}, {n:6, topic:'f', und:65}, {n:7, topic:'g', und:90}];
var s = V.series(units, 'und', 5);
ok(s.length === 5 && s[0].n === 2 && s[4].n === 7, '総復習を除き、回の順で最後の5つ', JSON.stringify(s.map(function(p){ return p.n; })));
ok(s[0].v === null && s[4].v === 90, '値の無い回は null');
ok(V.series(undefined, 'und').length === 0 && V.series([null, 1, 'x', {n:'a'}], 'und').length === 0, '崩れた入力は捨てる');
ok(V.latestOf(s).n === 7 && V.latestOf([{n:1, v:null}]) === null && V.latestOf(null) === null, '最新は値のある最後の点');

var h = V.lineChart({slots:5, lines:[{pts:s, cls:'und'}]});
ok(count(h, /class="vz-p /g) === 4, '値のある点だけ置く', count(h, /class="vz-p /g));
ok(count(h, / now"/g) === 1 && h.indexOf('vz-p b now') > 0, '濃い点は最新の1つ');
ok(count(h, /class="vz-stroke/g) === 1 && h.indexOf('vz-guide') > 0 && h.indexOf('aria-hidden="true"') > 0, '線・目安・読み上げない');
ok(h.indexOf('>80<') < 0 && h.indexOf('第') < 0, '点に数字も回も書かない');
var gap = V.lineChart({slots:5, lines:[{pts:[{n:1, v:50}, {n:2, v:null}, {n:3, v:70}, {n:4, v:80}], cls:'und'}]});
ok(count(gap, /class="vz-stroke/g) === 1 && count(gap, /class="vz-p /g) === 3, '値の無い回で線を切る（1点の切れ端は線にしない）');
var three = V.lineChart({slots:5, lines:[{pts:[{n:1, v:50}, {n:2, v:60}, {n:3, v:70}], cls:'und'}]});
ok(three.indexOf('left:50.00%') > 0 && three.indexOf('left:90.00%') > 0, '少ない回は右に寄せる');
ok(V.lineChart({lines:[{pts:[]}]}).indexOf('vz-empty') > 0 && V.lineChart({}).indexOf('vz-empty') > 0 &&
   V.lineChart({lines:[{pts:[{n:1, v:null}]}]}).indexOf('vz-empty') > 0, '値が無ければ空の図');
ok(V.lineChart({slots:5, lines:[{pts:s, cls:'und'}]}) === h, '同じ入力には同じ HTML');
var pr = V.lineChart({slots:5, lines:[{pts:s, cls:'und'}, {pts:V.series(units, 'sub', 5), cls:'sub'}],
                      focus:4, point:function(p){ return 'data-ikunit="'+p.n+'"'; }});
ok(count(pr, /<button class="vz-p/g) === 4 && pr.indexOf('role="img"') < 0 && pr.indexOf('data-ikunit="4"') > 0, '押せる点は button');
ok(pr.indexOf('vz-p b now" style="left:30.00%') > 0, 'focus の点を濃く（n=4 は2つ目の枠）');
ok(V.lineChart({slots:5, label:'<b>"x"</b>', lines:[{pts:s}]}).indexOf('<b>') < 0, '読み上げ文を逃がす');
ok(V.lineChart({slots:5, guide:null, lines:[{pts:s}]}).indexOf('vz-guide') < 0, '目安を出さない指定');

var en = V.lineChart({slots:5, ends:true, lines:[{pts:s, cls:'und', name:'理解度'}, {pts:[{n:6, v:100}, {n:7, v:100}], cls:'sub', name:'提出'}]});
ok(en.indexOf('vz-wrap') > 0 && count(en, /class="vz-end /g) === 2 && en.indexOf('理解度 <b class="num b">90%</b>') > 0 &&
   en.indexOf('提出 <b class="num b">100%</b>') > 0, '線の端に名前と最新の値', en);
ok(en.indexOf('bottom:100.0%') > 0 && en.indexOf('bottom:85.0%') > 0, '近い2つの札は離す');
ok(h.indexOf('vz-wrap') < 0 && V.lineChart({slots:5, ends:true, lines:[{pts:[{n:1, v:null}]}]}).indexOf('vz-end') < 0, 'ends 無し・値無しでは端の札を出さない');
ok(count(V.railKey(), /vz-ki/g) === 4 && V.railKey().indexOf('今週') > 0 && count(V.booksKey(), /vz-ki/g) === 2 &&
   V.booksKey().indexOf('class="p"') > 0, '凡例は同じ四角で');
ok(V.ring(null).indexOf('class="v"') < 0 && V.ring(0).indexOf('class="v"') < 0 && V.ring(100).indexOf('class="v"') > 0, '輪');
var d = V.dots(8, 1);
ok(count(d, /<i/g) === 8 && count(d, /class="y"/g) === 1, '1人1点');
ok(V.dots(40, 3, 30).indexOf('3</b>/40人') > 0, '多いクラスは数で');
ok(count(V.dots(3, 9), /class="y"/g) === 3 && V.dots(0, 0).indexOf('none') > 0 && count(V.dots(-2, -1), /<i/g) === 0 &&
   count(V.dots('x', null), /<i/g) === 0, '数の崩れに耐える');
var r = V.rail([{state:'done', label:'5章-2', topic:'定理'}, {state:'late', now:true, label:'5章-3', topic:'<x>'}, {state:'???'}]);
ok(r.indexOf('class="late now"') > 0 && r.indexOf('class="todo"') > 0 && r.indexOf('<x>') < 0, '単元の列');
ok(V.rail(null) === '' && V.rail([]) === '' && V.books(null).indexOf('なし') > 0, '無い入力');
ok(count(V.books([{name:'A', graded:true}, {name:'B', graded:false}, {}]), /class="p"/g) === 1, '出すだけは線だけの冊子');

print(BAD ? ('×が' + BAD + '件（' + N + '件中）') : ('すべて通った。（' + N + '件）'));
