/* 写真の下ごしらえ ―― 生徒が出すときも、講師が取り込む・返すときも、同じ1か所。

   長辺 1600px・JPEG 画質 0.82 に縮めてから送る（1枚 300〜600KB）。
   iPhone の写真はそのままだと 3〜5MB で、6枚でサーバの上限（8MB）を超え、
   HEIC はサーバが受け取れない ―― 「送信しています」のまま止まる原因はここだった。

   **blob: の URL は使わない。** この画面の決まり（CSP）は img-src に blob: を許していない。
   createObjectURL で Image に読ませると必ず失敗し、縮めずに元のまま送ってしまう（実際そうなった）。
   1) createImageBitmap（向きも直す）  2) FileReader の data: URL の Image  の順に読む。
   PDF はそのまま。読めない形は元のまま送り、サーバの返事（400）に任せる。 */
(function(global){
'use strict';

var MAX_EDGE = 1600, QUALITY = 0.82;

function readDataUrl(file){
  return new Promise(function(done, fail){
    var r = new FileReader();
    r.onerror = function(){ fail(new Error('read')); };
    r.onload = function(){ done(String(r.result || '')); };
    r.readAsDataURL(file);
  });
}
function isPdf(file){ return file.type === 'application/pdf' || /\.pdf$/i.test(file.name || ''); }
function looksImage(file){
  return /^image\//.test(file.type || '') || /\.(heic|heif|jpe?g|png|gif|webp|bmp|tiff?)$/i.test(file.name || '');
}
function decode(file){
  var first = global.createImageBitmap
    ? Promise.resolve().then(function(){ return global.createImageBitmap(file, {imageOrientation:'from-image'}); })
    : Promise.reject(new Error('no-bitmap'));
  return first.catch(function(){
    return readDataUrl(file).then(function(u){
      return new Promise(function(done, fail){
        var img = new Image();
        img.onload = function(){ done(img); };
        img.onerror = function(){ fail(new Error('decode')); };
        img.src = u;
      });
    });
  });
}
function toJpeg(src){
  var w = src.naturalWidth || src.width, h = src.naturalHeight || src.height;
  if(!w || !h) throw new Error('size');
  var k = Math.min(1, MAX_EDGE / Math.max(w, h));
  var c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(w * k)); c.height = Math.max(1, Math.round(h * k));
  c.getContext('2d').drawImage(src, 0, 0, c.width, c.height);
  if(src.close) src.close();
  var t = c.toDataURL('image/jpeg', QUALITY);
  return {type:'image/jpeg', b64:t.slice(t.indexOf(',') + 1), url:t, w:c.width, h:c.height};
}
/* 1枚ぶん → {type, b64, url}。url は札に出す小さな写し（PDF・縮められない形は空） */
async function prepare(file){
  if(isPdf(file)){
    var u = await readDataUrl(file);
    return {type:'application/pdf', b64:u.slice(u.indexOf(',') + 1), url:''};
  }
  if(looksImage(file)){
    try{ return toJpeg(await decode(file)); }catch(e){}
  }
  var raw = await readDataUrl(file);
  return {type:file.type || 'image/jpeg', b64:raw.slice(raw.indexOf(',') + 1), url:''};
}
/* 何枚かまとめて。1枚でも読めなければ Error（どれが読めないかは言わない ―― 撮り直せば済む） */
async function prepareAll(list){
  var out = [];
  for(var i = 0; i < list.length; i++){
    var f = await prepare(list[i]);
    if(!f || !f.b64) throw new Error('empty');
    out.push(f);
  }
  return out;
}

global.TubePhoto = {prepare:prepare, prepareAll:prepareAll, readDataUrl:readDataUrl, MAX_EDGE:MAX_EDGE, QUALITY:QUALITY};
})(window);
