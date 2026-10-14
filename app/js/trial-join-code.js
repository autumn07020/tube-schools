/* ためし運用のあいだだけ：初回登録の「登録コード」の欄に、有効なコードを先に入れておく。
   （2026-10-12 本人：保護者・生徒向けの 45 秒の動画で、画面の操作をそのまま見せるため）

   消し方：本番に切り替えるとき、index.html のこの script の 1 行と、このファイルを消すだけ。
   ほかのコードはこのファイルを何も参照していないし、ここからも ui-join.js の中身には触れない（欄の id と input の出来事だけ）。
   コードはサーバが /api/demo に joinCode として出す（試し運用の印のある校舎だけ。本番に切り替えると null）。
   無ければ何もしない。 */
(function(){
  var code = null;
  function fill(){
    var inp = document.getElementById('jnCode');
    if(!inp || !code || inp.value) return;
    inp.value = code;
    inp.dispatchEvent(new Event('input', {bubbles:true}));
  }
  function start(){
    try{
      fetch('api/demo', {credentials:'same-origin'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(d){
        code = (d && d.joinCode) ? String(d.joinCode) : null;
        if(code){ fill(); setInterval(fill, 400); }
      }).catch(function(){});
    }catch(e){}
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
