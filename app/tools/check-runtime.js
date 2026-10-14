/* ============================================================
   実行時の検査 ―― 「読み込んだのに使われていない」を捕まえる

   ブラウザの開発者コンソールに貼りつけて実行する。
   （サーバを立てて、生徒か講師で入った状態で）

   なぜ要るか
   ----------
   教材を作り直したとき、**18パック2847問がまるごとアプリから
   見えていなかった。** ファイルは読み込まれ、目録にも載り、
   check-content.py も「指摘0件」と言う。それでも出題は0件だった。
   TubeContent.register() を呼んでおらず、独自のグローバル変数に
   書いていただけだったため。

   ファイルを見る検査では、この種の不具合は原理的に捕まえられない。
   実際に動かして、DECK に入っているかを見るしかない。
   ============================================================ */
(function(){
"use strict";

var fails = [];
function check(name, ok, detail){
  console.log((ok ? "OK   " : "×    ") + name + (ok ? "" : "  ← " + detail));
  if(!ok) fails.push(name);
}

console.log("実行時の検査\n" + "=".repeat(52));

/* ---- 1. 目録に載っている教材が、本当に出題に使えるか ---- */
console.log("\n目録と実体");
var listed = TubeContent.packList ? TubeContent.packList() : [];
var deck = TubeContent.all();
var inDeck = {};
deck.forEach(function(c){ inDeck[c.pack] = (inDeck[c.pack]||0) + 1; });

var loadedIds = Object.keys(inDeck);
check("DECK に1枚でも入っている", deck.length > 0, deck.length);

/* いま読み込まれているはずの教材（この生徒の学年ぶん）だけを見る */
var S = window.TubeUI && TubeUI.S;
var want = [];
if(S && S.me){
  (S.me.subjects||[]).forEach(function(x){ want = want.concat(x.plan.packs||[]); });
}else if(S && S.teacher){
  want = loadedIds.slice();
}
want.forEach(function(pid){
  check("教材 " + pid + " が出題に使える",
        (inDeck[pid]||0) > 0,
        "読み込まれているが DECK に0枚。TubeContent.register() を呼んでいますか");
});

/* ---- 2. 進度が指す教材に、実際に出題対象があるか ---- */
console.log("\n進度と出題対象");
if(S && S.me){
  (S.me.subjects||[]).forEach(function(x){
    var n = (x.order||[]).length;
    check(x.subject.name + " に出題対象がある", n > 0,
          "0項目。帯（" + (x.plan.bands||[]).join("・") +
          "）が教材の帯と一致していない可能性");
  });
}

/* ---- 3. 死んだボタン ---- */
console.log("\n画面");
var dead = [].slice.call(document.querySelectorAll("button")).filter(function(b){
  if(b.disabled) return false;
  if(b.onclick) return false;
  return !b.dataset || Object.keys(b.dataset).length === 0;
}).filter(function(b){ return !b.closest("nav") && !b.id; });
check("押せそうで押せないボタンが無い", dead.length === 0,
      dead.map(function(b){ return b.textContent.trim().slice(0,16); }).join(" / "));

/* ---- 4. タップ領域 ---- */
var small = [].slice.call(document.querySelectorAll("button")).filter(function(b){
  var r = b.getBoundingClientRect();
  if(!r.width || !r.height) return false;
  return Math.min(r.width, r.height) < 44 && !b.classList.contains("hit");
});
check("タップ領域が44px以上", small.length === 0,
      small.map(function(b){
        var r = b.getBoundingClientRect();
        return b.textContent.trim().slice(0,12) + " " +
               Math.round(r.width) + "x" + Math.round(r.height);
      }).join(" / "));

/* ---- 5. 保存が効いているか ---- */
console.log("\n保存");
var rep = TubeStore.report();
check("記録が保存できる状態", rep.durable, rep.message);

console.log("\n" + "=".repeat(52));
if(fails.length){
  console.log("× " + fails.length + "件おちた: " + fails.join(" / "));
}else{
  console.log("すべて通った。");
}
return fails.length;
})();
