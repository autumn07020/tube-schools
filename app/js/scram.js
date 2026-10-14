/* ============================================================
   入るときに、合言葉そのものを送らない（SCRAM-SHA-256 の考え方）

   サーバの server/scram.py と**同じ値**を出す。手順と「何を守るか」はそちらの頭書きに。

     1. POST /login/start  {id, cnonce}        → {salt, iters, nonce}
     2. 合言葉から鍵を作る（PBKDF2-HMAC-SHA256・60万回。この端末の中で）
     3. POST /login/finish {id, nonce, proof}  → {token, profile, serverSig}
     4. サーバの印（serverSig）を確かめる

   計算はブラウザの WebCrypto を使う。使えない開き方（http で LAN の IP を開いた検査など）
   では、下の自前の SHA-256 で同じ計算をする（遅いが、同じ値になる）。
   ============================================================ */
(function(global){
"use strict";

var TAG = 'tubestudy-scram-v1';
var ITERS = 600000;
var enc = new TextEncoder();

function hex(u8){ var s = ''; for(var i = 0; i < u8.length; i++) s += (u8[i] < 16 ? '0' : '') + u8[i].toString(16); return s; }
function unhex(h){ var u = new Uint8Array(h.length / 2); for(var i = 0; i < u.length; i++) u[i] = parseInt(h.substr(i * 2, 2), 16); return u; }
function xor(a, b){ var u = new Uint8Array(a.length); for(var i = 0; i < a.length; i++) u[i] = a[i] ^ b[i]; return u; }
function subtle(){ return (global.crypto && global.crypto.subtle) || null; }

/* サーバの norm_pw と同じ：全角→半角、大文字→小文字、空白と区切りの線を取る。 */
function norm(pw){
  var t = String(pw == null ? '' : pw);
  if(t.normalize) t = t.normalize('NFKC');
  return t.toLowerCase().replace(/[\s\-‐-―−ー－_]+/g, '');
}
function normId(id){ return String(id == null ? '' : id).trim().toLowerCase(); }

/* ---------- 自前の SHA-256（WebCrypto が使えないときだけ） ---------- */
var K = new Uint32Array([
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
var W = new Uint32Array(64);
/* 1ブロック（16語）を state（8語）に混ぜる。 */
function compress(st, blk){
  var a = st[0], b = st[1], c = st[2], d = st[3], e = st[4], f = st[5], g = st[6], h = st[7], i, t1, t2, x;
  for(i = 0; i < 16; i++) W[i] = blk[i];
  for(i = 16; i < 64; i++){
    x = W[i - 15]; t1 = ((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3);
    x = W[i - 2];  t2 = ((x >>> 17) | (x << 15)) ^ ((x >>> 19) | (x << 13)) ^ (x >>> 10);
    W[i] = (W[i - 16] + t1 + W[i - 7] + t2) | 0;
  }
  for(i = 0; i < 64; i++){
    t1 = (h + (((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))) + ((e & f) ^ (~e & g)) + K[i] + W[i]) | 0;
    t2 = ((((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))) + ((a & b) ^ (a & c) ^ (b & c))) | 0;
    h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
  }
  st[0] = (st[0] + a) | 0; st[1] = (st[1] + b) | 0; st[2] = (st[2] + c) | 0; st[3] = (st[3] + d) | 0;
  st[4] = (st[4] + e) | 0; st[5] = (st[5] + f) | 0; st[6] = (st[6] + g) | 0; st[7] = (st[7] + h) | 0;
}
var IV = [0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
function sha256js(bytes, init, already){
  /* init があれば、その state から続ける（already は、もう混ぜたバイト数）。 */
  var st = new Int32Array(init || IV), n = bytes.length, total = n + (already || 0);
  var padded = new Uint8Array(((n + 9 + 63) >> 6) << 6);
  padded.set(bytes); padded[n] = 0x80;
  var dv = new DataView(padded.buffer);
  dv.setUint32(padded.length - 8, Math.floor(total / 0x20000000), false);
  dv.setUint32(padded.length - 4, (total << 3) >>> 0, false);
  var blk = new Uint32Array(16);
  for(var off = 0; off < padded.length; off += 64){
    for(var i = 0; i < 16; i++) blk[i] = dv.getUint32(off + i * 4, false);
    compress(st, blk);
  }
  return st;
}
function stBytes(st){ var u = new Uint8Array(32), dv = new DataView(u.buffer); for(var i = 0; i < 8; i++) dv.setInt32(i * 4, st[i], false); return u; }
function hmacPads(key){
  if(key.length > 64) key = stBytes(sha256js(key));
  var ip = new Uint8Array(64), op = new Uint8Array(64);
  for(var i = 0; i < 64; i++){ var k = key[i] || 0; ip[i] = k ^ 0x36; op[i] = k ^ 0x5c; }
  /* 鍵の1ブロックを先に混ぜておく（PBKDF2 の60万回で、毎回やり直さない）。 */
  var si = new Int32Array(IV), so = new Int32Array(IV), b = new Uint32Array(16), dv;
  dv = new DataView(ip.buffer); for(i = 0; i < 16; i++) b[i] = dv.getUint32(i * 4, false); compress(si, b);
  dv = new DataView(op.buffer); for(i = 0; i < 16; i++) b[i] = dv.getUint32(i * 4, false); compress(so, b);
  return {i:si, o:so};
}
function hmacJs(key, msg){
  var p = hmacPads(key);
  return stBytes(sha256js(stBytes(sha256js(msg, p.i, 64)), p.o, 64));
}
async function pbkdf2Js(pw, salt, iters){
  var p = hmacPads(pw);
  var first = new Uint8Array(salt.length + 4); first.set(salt); first[salt.length + 3] = 1;
  var u = sha256js(stBytes(sha256js(first, p.i, 64)), p.o, 64);
  var out = new Int32Array(u);
  /* 2回目からは、32バイトの入力が1ブロックに収まる。ブロックを直に組んで回す。 */
  var blk = new Uint32Array(16), st = new Int32Array(8), j, k;
  for(var n = 1; n < iters; n++){
    for(j = 0; j < 8; j++) blk[j] = u[j];
    blk[8] = 0x80000000; for(j = 9; j < 15; j++) blk[j] = 0; blk[15] = (64 + 32) * 8;
    for(j = 0; j < 8; j++) st[j] = p.i[j];
    compress(st, blk);
    for(j = 0; j < 8; j++) blk[j] = st[j];
    for(j = 0; j < 8; j++) st[j] = p.o[j];
    compress(st, blk);
    for(j = 0; j < 8; j++){ u[j] = st[j]; out[j] ^= st[j]; }
    if((n & 0x3fff) === 0) await new Promise(function(r){ setTimeout(r, 0); });   /* 画面を固めない */
  }
  return stBytes(out);
}

/* ---------- WebCrypto か、自前か ---------- */
async function sha256(bytes){
  var s = subtle();
  return s ? new Uint8Array(await s.digest('SHA-256', bytes)) : stBytes(sha256js(bytes));
}
async function hmac(key, msg){
  var s = subtle();
  if(!s) return hmacJs(key, msg);
  var k = await s.importKey('raw', key, {name:'HMAC', hash:'SHA-256'}, false, ['sign']);
  return new Uint8Array(await s.sign('HMAC', k, msg));
}
async function pbkdf2(pw, salt, iters){
  var s = subtle();
  if(!s) return pbkdf2Js(pw, salt, iters);
  var k = await s.importKey('raw', pw, 'PBKDF2', false, ['deriveBits']);
  return new Uint8Array(await s.deriveBits({name:'PBKDF2', hash:'SHA-256', salt:salt, iterations:iters}, k, 256));
}
function randomBytes(n){
  var u = new Uint8Array(n);
  if(global.crypto && global.crypto.getRandomValues) global.crypto.getRandomValues(u);
  else throw new Error('この端末では乱数を作れません');
  return u;
}
function b64url(u){
  var s = ''; for(var i = 0; i < u.length; i++) s += String.fromCharCode(u[i]);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function salted(pw, saltHex, iters){ return pbkdf2(enc.encode(norm(pw)), unhex(saltHex), iters); }
async function keys(sp){
  var clientKey = await hmac(sp, enc.encode('Client Key'));
  return {clientKey:clientKey, storedKey:await sha256(clientKey), serverKey:await hmac(sp, enc.encode('Server Key'))};
}
function authMessage(id, nonce, salt, iters){ return enc.encode([TAG, id, nonce, salt, String(iters)].join(',')); }

/* サーバに置く値を作る（管理ページが席や講師を足すとき）。合言葉そのものは入らない。 */
async function verifier(pw){
  var salt = hex(randomBytes(16));
  var k = await keys(await salted(pw, salt, ITERS));
  return {alg:'scram-sha256', salt:salt, iters:ITERS, storedKey:hex(k.storedKey), serverKey:hex(k.serverKey)};
}

/* 入る。post(path, body) は {ok, status, data} を返す関数。
   返すのは {ok:true, data:{token, profile}} か {ok:false, status, error}。 */
async function login(post, id, pw, extra){
  extra = extra || {};
  var lid = normId(id);
  var cnonce = b64url(randomBytes(18));
  var r = await post('/login/start', Object.assign({}, extra, {id:lid, cnonce:cnonce}));
  if(!r.ok) return {ok:false, status:r.status, error:(r.data && r.data.error) || 'ログインできません'};
  var d = r.data || {};
  if(!/^[0-9a-f]{32}$/.test(d.salt || '') || typeof d.iters !== 'number' || d.iters < ITERS || d.iters > 5000000 ||
     String(d.nonce || '').indexOf(cnonce) !== 0){
    return {ok:false, status:0, error:'サーバの返事がおかしいので、入るのをやめました'};
  }
  var sp = await salted(pw, d.salt, d.iters);
  var k = await keys(sp);
  var auth = authMessage(lid, d.nonce, d.salt, d.iters);
  var proof = xor(k.clientKey, await hmac(k.storedKey, auth));
  r = await post('/login/finish', Object.assign({}, extra, {id:lid, nonce:d.nonce, proof:hex(proof)}));
  if(!r.ok) return {ok:false, status:r.status, error:(r.data && r.data.error) || 'ログインできません'};
  var want = hex(await hmac(k.serverKey, auth));
  if(!r.data || r.data.serverSig !== want){
    return {ok:false, status:0, error:'サーバを確かめられませんでした。もう一度ためしてください', token:(r.data || {}).token};
  }
  return {ok:true, status:200, data:r.data};
}

/* ---------- 合言葉を作る（この端末の中で。neko-yama-sora-4821 の形） ---------- */
function rnd(n){                /* 0 以上 n 未満。偏りが出ないよう、はみ出た乱数は捨てる */
  var lim = Math.floor(4294967296 / n) * n, a = new Uint32Array(1);
  do{ global.crypto.getRandomValues(a); }while(a[0] >= lim);
  return a[0] % n;
}
var wordList = null;
async function words(){
  if(wordList) return wordList;
  var res = await fetch('/words.json', {cache:'no-cache'});
  var ws = ((await res.json()) || {}).words || [];
  if(ws.length < 128) throw new Error('ことばの表が読めません');
  wordList = ws; return ws;
}
/* n 語＋4桁。ことばの表（/words.json）から無作為に選ぶ。 */
async function makePassword(n){
  var ws = await words(), out = [];
  for(var i = 0; i < (n || 3); i++) out.push(ws[rnd(ws.length)]);
  return out.join('-') + '-' + ('000' + rnd(10000)).slice(-4);
}

global.TubeScram = {
  login:login, verifier:verifier, norm:norm, ITERS:ITERS, makePassword:makePassword, rnd:rnd,
  /* 検査用：自前の計算と WebCrypto の計算が同じ値になるかを突き合わせる */
  _js:{sha256:function(b){ return stBytes(sha256js(b)); }, hmac:hmacJs, pbkdf2:pbkdf2Js},
  _wc:{sha256:sha256, hmac:hmac, pbkdf2:pbkdf2}, _hex:hex, _unhex:unhex, _salted:salted, _keys:keys, _auth:authMessage
};
})(typeof window !== 'undefined' ? window : this);
