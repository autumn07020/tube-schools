/* ============================================================
   図の部品（TubeViz）―― 成績・進度・時間割で使う
   ------------------------------------------------------------
   **DOM に触らない純粋な関数だけを置く。** 入力はサーバの返事そのまま
   （値が無い・形が崩れている・数が多い、を前提にする）。落ちず、
   同じ入力には同じ HTML を返す。

   なぜ分けたか
     図の不具合は「データの形」と「描き方」のどちらかにある。ここに集めれば
     ブラウザ無しで確かめられる（app/tools/test-viz.js、JavaScriptCore で動く）。
     画面の側は、ここが返す HTML を置いて、押す口を結ぶだけにする。

   決まり（CLAUDE.md「画面の決まり」）
     - 図の点や棒に数字を振らない。数字は大きな1つと、読み出しの1行だけ
     - 横軸に第何回を書かない。いちばん新しい点だけ濃く、単元名は図の下に1回
     - 総復習の回は単元ではないので、推移に入れない
   ============================================================ */
(function(global){
'use strict';

var YELLOW = 70;

function esc(s){
  return String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c];
  });
}
/* 0〜100 の整数。数でないもの・無いものは null（0 とは区別する）。 */
function pct(v){
  return (typeof v === 'number' && isFinite(v)) ? Math.max(0, Math.min(100, Math.round(v))) : null;
}
function tone(v){ v = pct(v); return v === null ? 'none' : (v < YELLOW ? 'y' : 'b'); }

/* ---- 授業の回の名前（教材の呼び名。無ければ「第n回」） ---- */
function unitName(x){
  if(!x) return '';
  if(x.label !== undefined && x.label !== null) return String(x.label);
  return x.n ? '第'+x.n+'回' : '';
}
function unitText(x){
  if(!x) return '';
  return [unitName(x), x.topic || ''].filter(function(t){ return t; }).join(' ');
}
/* 丸などに置く短い番号（第6回→6、上 第20回→20、5章-3→5-3、例題56-57→56）。 */
function unitTick(x){
  var s = unitName(x);
  if(!s) return '';
  var m = /(\d+)章-(\d+)/.exec(s);
  if(m) return m[1]+'-'+m[2];
  m = /(\d+)(?:-\d+)?\D*$/.exec(s);
  return m ? m[1] : s;
}

/* ---- 推移 ---- */
/* 単元の並び → 点 [{n, label, topic, v}]。総復習を除き、回の順（n）で、最後の count 個。 */
function series(units, field, count){
  var out = [];
  (Array.isArray(units) ? units : []).forEach(function(u){
    if(!u || typeof u !== 'object' || u.review) return;
    var n = Number(u.n);
    if(!isFinite(n)) return;
    out.push({n:n, label:(u.label === undefined ? null : u.label), topic:String(u.topic || ''), v:pct(u[field])});
  });
  out.sort(function(a, b){ return a.n - b.n; });
  return out.slice(-Math.max(1, count || 5));
}
/* 最新（値のある最後の点）。 */
function latestOf(pts){
  for(var i = (pts || []).length - 1; i >= 0; i--) if(pts[i] && pts[i].v !== null) return pts[i];
  return null;
}

/* 折れ線。枠（slots）に右寄せで置く ―― どの図でも「右端が最新」。
     lines  [{pts, cls}]  1本目が主（面と点を置く）、2本目以降は線だけ
     focus  濃く出す点の n（無ければ最新）
     guide  目安の線（既定 70）。null で出さない
     point  function(pt) → 属性の文字列。渡すと点が button になる（押せる図）
     label  図の読み上げ文（押せない図だけ。無ければ読み上げない）
     ends   true なら線の右端に「名前 最新の値%」を置く（lines[].name）。図の下に数字の行を作らない */
function lineChart(opts){
  opts = opts || {};
  var slots = Math.max(2, Math.floor(opts.slots || 5));
  var lines = (opts.lines || []).filter(function(l){ return l && Array.isArray(l.pts); });
  var main = lines.length ? lines[0].pts.slice(-slots) : [];
  var press = typeof opts.point === 'function';
  var guide = opts.guide === null ? null : pct(opts.guide === undefined ? YELLOW : opts.guide);
  if(!main.some(function(p){ return p && p.v !== null; })){
    return '<div class="vz-line vz-empty"'+(opts.label ? ' role="img" aria-label="'+esc(opts.label)+'"' : ' aria-hidden="true"')+'></div>';
  }
  var focus = (opts.focus !== undefined && opts.focus !== null) ? opts.focus : latestOf(main).n;
  /* **横の位置は回の番号（n）で決める。** 線ごとに自分の点の数で右寄せすると、
     提出の点が3つ・理解度が5つのとき、同じ回の点が別の列に来て「ずれて」見えた。
     全部の線の n を集めて1つの並びにし、どの線も同じ n は同じ列に置く（右端が最新）。 */
  var ns = [];
  lines.forEach(function(l){ l.pts.slice(-slots).forEach(function(p){ if(p && ns.indexOf(p.n) < 0) ns.push(p.n); }); });
  ns.sort(function(a, b){ return a - b; });
  ns = ns.slice(-slots);
  function xOfN(n){ var i = ns.indexOf(n); return (slots - ns.length + i + 0.5) / slots * 100; }
  function segments(pts){
    var segs = [], cur = [];
    pts.forEach(function(p){
      if(!p || p.v === null || ns.indexOf(p.n) < 0){ if(cur.length) segs.push(cur); cur = []; return; }
      cur.push([xOfN(p.n), 100 - p.v]);
    });
    if(cur.length) segs.push(cur);
    return segs.filter(function(sg){ return sg.length > 1; });
  }
  var svg = '';
  lines.forEach(function(l, k){
    var cls = esc(l.cls || ('l' + k));
    segments(l.pts.slice(-slots)).forEach(function(sg){
      var d = sg.map(function(q, i){ return (i ? 'L' : 'M')+q[0].toFixed(2)+' '+q[1].toFixed(2); }).join(' ');
      if(k === 0){
        svg += '<path class="vz-area '+cls+'" d="'+d+' L'+sg[sg.length-1][0].toFixed(2)+' 100 L'+sg[0][0].toFixed(2)+' 100 Z"></path>';
      }
      svg += '<path class="vz-stroke '+cls+'" vector-effect="non-scaling-stroke" d="'+d+'"></path>';
    });
  });
  var dots = main.map(function(p){
    if(!p || p.v === null || ns.indexOf(p.n) < 0) return '';
    var cls = 'vz-p '+tone(p.v)+(p.n === focus ? ' now' : '');
    var style = 'left:'+xOfN(p.n).toFixed(2)+'%;bottom:'+p.v+'%';
    return press ? '<button class="'+cls+'" style="'+style+'" '+opts.point(p)+'></button>'
                 : '<i class="'+cls+'" style="'+style+'"></i>';
  }).join('');
  var aria = press ? '' : (opts.label ? ' role="img" aria-label="'+esc(opts.label)+'"' : ' aria-hidden="true"');
  var out = '<div class="vz-line'+(press ? ' vz-press' : '')+'"'+aria+'>'+
    (guide === null ? '' : '<i class="vz-guide" style="bottom:'+guide+'%"></i>')+
    '<svg class="vz-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">'+svg+'</svg>'+
    dots+'</div>';
  if(!opts.ends) return out;
  return '<div class="vz-wrap">'+out+'<div class="vz-ends">'+endLabels(lines, slots)+'</div></div>';
}
/* 線の端の札：名前と最新の値。線の高さに合わせて置き、2本が近いときは下の線の札を下へずらす
   （札1つぶん＝図の高さの15%）。いちばん下が枠を出るなら、全部を同じだけ上げる。 */
function endLabels(lines, slots){
  var ls = [];
  lines.forEach(function(l, k){
    var p = latestOf(l.pts.slice(-slots));
    if(!p) return;
    ls.push({cls:esc(l.cls || ('l' + k)), name:esc(l.name || ''), v:p.v, y:p.v});
  });
  ls.sort(function(a, b){ return b.v - a.v; });
  var GAP = 15;
  for(var i = 1; i < ls.length; i++) if(ls[i - 1].y - ls[i].y < GAP) ls[i].y = ls[i - 1].y - GAP;
  var lift = ls.length ? Math.max(0, -ls[ls.length - 1].y) : 0;
  return ls.map(function(l){
    return '<span class="vz-end '+l.cls+'" style="bottom:'+Math.min(100, l.y + lift).toFixed(1)+'%"><i></i>'+l.name+
      ' <b class="num '+tone(l.v)+'">'+l.v+'%</b></span>';
  }).join('');
}

/* ---- 小さな図 ---- */
/* 割合の輪（提出率など）。値が無ければ輪の地だけ。 */
function ring(v){
  v = pct(v);
  var c = 2 * Math.PI * 8;
  return '<svg class="vz-ring" viewBox="0 0 20 20" aria-hidden="true"><circle class="t" cx="10" cy="10" r="8"></circle>'+
    (v ? '<circle class="v" cx="10" cy="10" r="8" transform="rotate(-90 10 10)" stroke-dasharray="'+
         (c * v / 100).toFixed(2)+' '+c.toFixed(2)+'"></circle>' : '')+'</svg>';
}
/* 1人1つの点。marked 人を黄に。max を超えるクラスは点をやめて「marked/total人」。 */
function dots(total, marked, max){
  total = Math.max(0, Math.floor(Number(total) || 0));
  marked = Math.max(0, Math.min(total, Math.floor(Number(marked) || 0)));
  max = Math.max(1, max || 30);
  if(!total) return '<span class="vz-dots none"></span>';
  if(total > max) return '<span class="vz-count"><b class="num">'+marked+'</b>/'+total+'人</span>';
  var s = '';
  for(var i = 0; i < total; i++) s += i < marked ? '<i class="y"></i>' : '<i></i>';
  return '<span class="vz-dots" aria-label="'+total+'人中'+marked+'人">'+s+'</span>';
}
/* 単元の列（進度）。items は syllabus.pace の rail（state: done / late / todo、now、ahead）。 */
var RAIL = {done:1, late:1, todo:1};
function rail(items){
  if(!Array.isArray(items) || !items.length) return '';
  return '<span class="vz-rail">'+ items.map(function(it){
    it = it || {};
    var st = RAIL[it.state] ? it.state : 'todo';
    return '<i class="'+st+(it.now ? ' now' : '')+(it.ahead ? ' ahead' : '')+'" title="'+esc(unitText(it))+'"></i>';
  }).join('') +'</span>';
}
/* 凡例。単元の列と冊子の四角が何を指すかを、同じ四角で1行に（四角だけでは分からない）。 */
function railKey(){
  return '<span class="vz-key">'+[['done', '済み'], ['late', 'おくれ'], ['todo', 'これから'], ['done now', '今週']].map(function(x){
    return '<span class="vz-ki"><span class="vz-rail"><i class="'+x[0]+'"></i></span>'+x[1]+'</span>';
  }).join('')+'</span>';
}
function booksKey(){
  return '<span class="vz-key">'+[['g', '採点する'], ['p', '出すだけ']].map(function(x){
    return '<span class="vz-ki"><span class="vz-books"><i class="'+x[0]+'"></i></span>'+x[1]+'</span>';
  }).join('')+'</span>';
}
/* 教材の冊子。塗り＝採点する、線だけ＝出すだけ。名前は title に。 */
function books(list){
  if(!Array.isArray(list) || !list.length) return '<span class="vz-books none">なし</span>';
  return '<span class="vz-books">'+ list.map(function(b){
    b = b || {};
    var plain = b.graded === false;
    return '<i class="'+(plain ? 'p' : 'g')+'" title="'+esc((b.name || '')+(plain ? '（出すだけ）' : ''))+'"></i>';
  }).join('') +'</span>';
}

global.TubeViz = {
  YELLOW:YELLOW, esc:esc, pct:pct, tone:tone,
  unitName:unitName, unitText:unitText, unitTick:unitTick,
  series:series, latestOf:latestOf, lineChart:lineChart,
  ring:ring, dots:dots, rail:rail, books:books, railKey:railKey, booksKey:booksKey
};
})(typeof window !== 'undefined' ? window : this);
