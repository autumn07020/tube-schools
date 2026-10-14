/* 印刷用の紙（/api/submissions/<宿題>/<生徒>/print）。写真が全部読めたら、印刷の窓を開く。
   CSP が inline の script を許していないので、ここに置く。 */
(function(){
  'use strict';
  function go(){ setTimeout(function(){ window.print(); }, 250); }
  var imgs = [].slice.call(document.images);
  Promise.all(imgs.map(function(im){ return (im.decode ? im.decode() : Promise.resolve()).catch(function(){}); })).then(go, go);
})();
