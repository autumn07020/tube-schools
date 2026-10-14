/* マークシート読み取りの検査。test-omr.html から読み込む。
   **ページの中に script を直接書かない** ―― 環境によっては
   インラインの script が止められ、検査が黙って走らなくなる。 */
/* 刷る側（server/prepsheet.py の SHEET）と同じ寸法。
   **ここがずれたら検査の意味がない。** サーバを変えたらここも直す。 */
var G = {cols:4, rows:15, opts:4,
  gridX0:0.045, gridY0:0.215, gridW:0.91, gridH:0.72,
  bubX0:0.34, bubDX:0.205, bubR:0.062, markMM:8.0, marginMM:12.0,
  pageMM:[210,297]};

/* 解答らんの紙を絵にする。picks[i] が塗るマス（-1 は塗らない）。 */
function drawSheet(n, picks, opt){
  opt = opt || {};
  /* 紙の形は G.pageMM から出す。**数字を直に書かない** ――
     A3よこ から A4たて に変えたとき、ここに 420 と書いてあったせいで
     余白とマークが半分の大きさになり、検査が丸ごと嘘をついた。 */
  var PW = G.pageMM[0], PH = G.pageMM[1];
  var W = 1100, H = Math.round(W * PH / PW);
  var c = document.createElement('canvas'); c.width=W; c.height=H;
  var x = c.getContext('2d');
  x.fillStyle = '#fff'; x.fillRect(0,0,W,H);
  var m = G.marginMM/PW*W, s = G.markMM/PW*W;
  [[m,m],[W-m-s,m],[W-m-s,H-m-s],[m,H-m-s]].forEach(function(p){
    x.fillStyle='#000'; x.fillRect(p[0],p[1],s,s); });
  var rx=m+s/2, ry=m+s/2, rw=W-2*rx, rh=H-2*ry;
  var rr = Math.max(3, Math.round(rw*G.bubR*G.gridW/G.cols));
  for(var i=0;i<n;i++){
    for(var o=0;o<G.opts;o++){
      var uv = TubeOMR.bubbleAt(G, i, o);
      var px = rx+rw*uv[0], py = ry+rh*uv[1];
      x.beginPath(); x.arc(px,py,rr,0,7);
      x.strokeStyle='#444'; x.lineWidth=1.2; x.stroke();
      if(picks[i] === o){
        /* かすれ: うすく塗った場合も試す */
        x.fillStyle = opt.faint ? 'rgba(20,20,20,0.55)' : '#111';
        x.fill();
      }
    }
  }
  return c;
}

/* 撮った写真らしく歪める。机・傾き・遠近・影。 */
function shoot(src, o){
  /* 机の上の写真。**紙より大きく取る。** 紙がはみ出すと四すみが切れ、
     読めないのは当たり前になる ―― それでは何も試したことにならない。 */
  var W = Math.round(src.width * 1.36), H = Math.round(src.height * 1.22);
  var c=document.createElement('canvas'); c.width=W; c.height=H;
  var x=c.getContext('2d');
  x.fillStyle = o.desk || '#8d8d92'; x.fillRect(0,0,W,H);
  x.save();
  x.translate(W/2 + (o.dx||0), H/2 + (o.dy||0));
  x.rotate((o.rot||0)*Math.PI/180);
  x.transform(1, o.skew||0, o.skew2||0, 1, 0, 0);
  var sc = o.scale || 0.82;
  x.drawImage(src, -src.width*sc/2, -src.height*sc/2, src.width*sc, src.height*sc);
  x.restore();
  if(o.shade){
    var g = x.createLinearGradient(0,0,W,H);
    g.addColorStop(0,'rgba(0,0,0,0)');
    g.addColorStop(1,'rgba(0,0,0,'+(o.shade)+')');
    x.fillStyle=g; x.fillRect(0,0,W,H);
  }
  return c;
}

var CASES = [
  ['まっすぐ',              {scale:0.86}],
  ['少し傾き（4度）',        {rot:4, scale:0.84}],
  ['大きく傾き（-9度）',     {rot:-9, scale:0.8}],
  ['影あり',                {rot:2, scale:0.82, shade:0.45}],
  ['斜めから（遠近）',       {rot:3, scale:0.8, skew:0.07, skew2:0.05}],
  ['遠近＋影',              {rot:-5, scale:0.78, skew:-0.08, skew2:0.05, shade:0.4}],
  ['はしに寄っている',       {rot:2, scale:0.74, dx:-140, dy:80}],
  ['うすく塗った',           {scale:0.84, faint:true}],
  ['暗い机',                {scale:0.84, desk:'#3a3a3e'}]
];

var n = 44;
var picks = [];
for(var i=0;i<n;i++) picks.push((i*3)%4);
picks[5] = -1; picks[19] = -1;          /* 2問は塗らない */

var tb = document.querySelector('#t tbody');
var pass = 0;
CASES.forEach(function(cs, idx){
  var sheet = drawSheet(n, picks, cs[1]);
  var img = shoot(sheet, cs[1]);
  if(idx === 5) {   /* 1つだけ見本を出す */
    var pk = document.getElementById('peek');
    pk.width = img.width/3; pk.height = img.height/3;
    pk.getContext('2d').drawImage(img, 0, 0, pk.width, pk.height);
  }
  var got = TubeOMR.read(img, G, n);
  var tr = document.createElement('tr');
  var okN = 0, bad = 0;
  if(got.ok){
    for(var i2=0;i2<n;i2++){
      if(got.answers[i2] === picks[i2]) okN++;
      else bad++;
    }
  }
  var good = got.ok && bad === 0;
  if(good) pass++;
  tr.innerHTML = '<td>'+cs[0]+'</td>'+
    '<td>'+(got.ok ? okN+' / '+n : '―')+'</td>'+
    '<td class="'+(good?'ok':'ng')+'">'+
      (good ? 'ぜんぶ一致' : (got.ok ? (bad+'問ちがう') : ('読めず: '+got.why)))+
    '</td>';
  tb.appendChild(tr);
});
document.getElementById('sum').textContent =
  pass === CASES.length
    ? 'すべて通った。（' + CASES.length + '通り）'
    : '× ' + (CASES.length - pass) + '通りで ずれた';
document.getElementById('sum').className = pass === CASES.length ? 'ok' : 'ng';
