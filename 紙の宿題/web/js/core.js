/* ============================================================
   土台：画面の切り替え・知らせ・紙（ポップアップ）・tubestudy との通信・端末の中の保存
   ============================================================
   決まり
     ・通信の相手は同じ住所の中継（relay.py）だけ。中継は tubestudy の決まった口だけを通す。
     ・**名前（端末の中の対応表）は、どの通信にも入れない。** 送る関数は sid と画像とひとことしか受け取らない。
     ・保存できるかは、起動したときに実際に書いて読んで確かめる（プライベートブラウズでは保存できない）。
   ============================================================ */
(function(root){
"use strict";
var P = root.Paper = root.Paper || {};

/* ---------- 小さな道具 ---------- */
P.$ = function(s, el){ return (el || document).querySelector(s); };
P.$$ = function(s, el){ return Array.prototype.slice.call((el || document).querySelectorAll(s)); };
P.esc = function(s){
  return String(s == null ? "" : s).replace(/[&<>"']/g, function(m){
    return {"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[m];
  });
};
P.sleep = function(ms){ return new Promise(function(r){ setTimeout(r, ms); }); };
P.pad2 = function(n){ return ("0" + n).slice(-2); };
var WD = ["日", "月", "火", "水", "木", "金", "土"];
P.md = function(ms){                        // 9/24（木）
  if(!ms) return "";
  var d = new Date(ms);
  return (d.getMonth() + 1) + "/" + d.getDate() + "（" + WD[d.getDay()] + "）";
};
P.mdIso = function(iso){                    // "2026-09-24" → 9/24（木）（端末の暦で組む）
  var p = String(iso || "").split("-");
  if(p.length !== 3) return "";
  var d = new Date(+p[0], +p[1] - 1, +p[2]);
  return (+p[1]) + "/" + (+p[2]) + "（" + WD[d.getDay()] + "）";
};
P.hm = function(ms){ var d = new Date(ms); return d.getHours() + ":" + P.pad2(d.getMinutes()); };
P.todayIso = function(){ var d = new Date(); return d.getFullYear() + "-" + P.pad2(d.getMonth() + 1) + "-" + P.pad2(d.getDate()); };
P.uid = function(){ return Date.now().toString(36) + Math.random().toString(36).slice(2, 8); };

/* ---------- 知らせ（下に出て消える） ---------- */
var toastTimer = null;
P.toast = function(text, warn){
  var t = P.$("#toast");
  t.textContent = text;
  t.className = "toast on" + (warn ? " warn" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function(){ t.className = "toast" + (warn ? " warn" : ""); }, warn ? 5200 : 2800);
};

/* ---------- 紙（ページを移さずに出す。閉じる道は × と暗がりの2つ） ---------- */
P.sheet = function(title, body, opt){
  opt = opt || {};
  P.closeSheet(true);
  var wrap = document.createElement("div");
  wrap.className = "sheet-wrap";
  wrap.innerHTML = '<div class="sheet-dim" data-close="1"></div>' +
    '<div class="sheet' + (opt.wide ? " wide" : "") + '" role="dialog" aria-modal="true" aria-label="' + P.esc(title) + '">' +
      '<div class="sheet-top"><h2>' + P.esc(title) + '</h2><button class="x" data-close="1" aria-label="閉じる">×</button></div>' +
      '<div class="sheet-body">' + body + '</div></div>';
  document.body.appendChild(wrap);
  requestAnimationFrame(function(){ wrap.classList.add("on"); });
  wrap.addEventListener("click", function(e){
    if(e.target.closest("[data-close]")){ P.closeSheet(); if(opt.onClose) opt.onClose(); }
  });
  return wrap.querySelector(".sheet-body");
};
P.closeSheet = function(now){
  P.$$(".sheet-wrap").forEach(function(w){
    if(now){ w.remove(); return; }
    w.classList.remove("on");
    setTimeout(function(){ w.remove(); }, 260);
  });
};

/* ---------- 画面の切り替え（フェードだけ） ---------- */
P.views = {};
P.state = {view:null, arg:null};
P.show = function(name, arg){
  var v = P.views[name];
  if(!v) return;
  P.closeSheet(true);
  var main = P.$("#main");
  main.classList.remove("in");
  P.state.view = name; P.state.arg = arg;
  var mine = (P.showSeq = (P.showSeq || 0) + 1);
  var done = function(){
    if(mine !== P.showSeq) return;                         // 遅れて届いた結果で別の画面を描かない
    requestAnimationFrame(function(){ main.classList.add("in"); });
    window.scrollTo(0, 0);
    P.$("#home").hidden = name === "home" || name === "login";
  };
  Promise.resolve(v.render(main, arg)).then(done).catch(function(e){
    if(e && e.status === 401){ P.fail(e); return; }
    if(mine !== P.showSeq) return;
    P.failView(main, e);                                    // 白い画面のままにしない
    done();
  });
};
/* 画面の途中で失敗したとき：理由と、戻る道を出す（白い画面や「読んでいます…」のまま止めない） */
P.failView = function(main, e){
  if(e && e.status === 401){ P.fail(e); return; }
  main.innerHTML = '<h1>開けませんでした</h1><div class="card"><p>' + P.esc((e && (e.error || e.message)) || "うまくいきませんでした") + '</p>' +
    '<p class="small muted">回線を確かめて、もう一度。続くときは、ホームからやり直してください（途中の取り込みはこの端末に残っています）。</p>' +
    '<div class="row"><button class="btn" data-go="home">ホームへ</button></div></div>';
  if(root.console) console.error(e);
};
P.fail = function(e){
  if(e && e.status === 401){ P.api.setToken(null); P.toast("もう一度ログインしてください（合言葉の期限）", true); P.show("login"); return; }
  P.toast((e && (e.error || e.message)) || "うまくいきませんでした", true);
  if(root.console) console.error(e);
};

/* ---------- tubestudy との通信（中継を通す） ---------- */
function readToken(){ try { return localStorage.getItem("paper.token"); } catch(e){ return null; } }
P.api = {
  token: readToken(),
  setToken: function(t){ this.token = t; try { if(t) localStorage.setItem("paper.token", t); else localStorage.removeItem("paper.token"); } catch(e){} },
  call: async function(method, path, body){
    var opt = {method:method, headers:{}};
    if(this.token) opt.headers.Authorization = "Bearer " + this.token;
    if(body !== undefined){ opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
    var r;
    try { r = await fetch(path, opt); }
    catch(e){ throw {status:0, error:"回線がつながっていません。つながったら、もう一度"}; }
    var data = null;
    try { data = await r.json(); } catch(e){ data = null; }
    if(!r.ok) throw {status:r.status, error:(data && data.error) || ("うまくいきませんでした（" + r.status + "）")};
    return data;
  },
  blob: async function(path){
    var r;
    try { r = await fetch(path, {headers:this.token ? {Authorization:"Bearer " + this.token} : {}}); }
    catch(e){ throw {status:0, error:"回線がつながっていません"}; }
    if(!r.ok) throw {status:r.status, error:"答案を読めませんでした（" + r.status + "）"};
    return await r.blob();
  },
  /* 入る。**合言葉そのものは送らない**（js/scram.js。tubestudy の app/js/scram.js と同じもの）。 */
  login: async function(id, pw){
    var self = this;
    var r = await TubeScram.login(async function(path, body){
      try { return {ok:true, status:200, data:await self.call("POST", "/api" + path, body)}; }
      catch(e){ return {ok:false, status:e.status || 0, data:{error:e.error}}; }
    }, id, pw);
    if(!r.ok) throw {status:r.status, error:r.error || "入れませんでした"};
    if(r.data.claim){
      /* 管理者から届いた「1回だけ使える言葉」。ここでは引き換えない（引き換えは tubestudy の入口で）。
         受け取った印はその場で返し、持たない。 */
      this.setToken(r.data.token);
      try { await this.call("POST", "/api/logout"); } catch(e){}
      this.setToken(null);
      /* 401 にすると、画面は「もう一度ログインしてください（合言葉の期限）」に言い換えてしまう（P.fail）。 */
      throw {status:400, error:"これは、はじめの1回だけ使う言葉です。先に tubestudy の入口で開いて、自分の合言葉を受け取ってください。"};
    }
    this.setToken(r.data.token);
    return r.data.profile;
  },
  me: function(){ return this.call("GET", "/api/me"); },
  today: function(){ return this.call("GET", "/api/today"); },
  check: function(key, n){ return this.call("GET", "/api/check?key=" + encodeURIComponent(key) + (n != null ? "&n=" + n : "")); },
  image: function(aid, sid, name){ return this.blob("/api/submissions/" + encodeURIComponent(aid) + "/" + encodeURIComponent(sid) + "/" + encodeURIComponent(name)); },
  /* 送る：sid・画像・ひとことだけ。名前を入れる引数は無い。 */
  scan: function(aid, sid, files){ return this.call("POST", "/api/submissions/" + encodeURIComponent(aid) + "/" + encodeURIComponent(sid) + "/scan", {files:files}); },
  giveBack: function(aid, sid, files, note){ return this.call("POST", "/api/submissions/" + encodeURIComponent(aid) + "/" + encodeURIComponent(sid) + "/return", {files:files, note:note}); },
  rate: function(key, n, sid, v, note){
    var b = {key:key, n:n, sid:sid};
    if(v !== undefined) b.v = v;
    if(note !== undefined) b.note = note;
    return this.call("PUT", "/api/check/rate", b);
  },
  quiz: function(key, title, dueAt){ return this.call("POST", "/api/quiz", {key:key, title:title, dueAt:dueAt}); },
  logout: function(){ var t = this; return this.call("POST", "/api/logout").catch(function(){}).then(function(){ t.setToken(null); }); }
};

/* Blob → base64（送るとき） */
P.b64 = function(blob){
  return new Promise(function(res, rej){
    var fr = new FileReader();
    fr.onload = function(){ res(String(fr.result).split(",")[1] || ""); };
    fr.onerror = function(){ rej(fr.error); };
    fr.readAsDataURL(blob);
  });
};

/* ---------- 端末の中の保存（IndexedDB） ---------- */
var DB_NAME = "paper-homework", DB_VER = 1, STORES = ["kv", "batches", "pages", "marks", "history", "outbox"];
var mem = {};                                  // 保存できない端末では、ここに置く（閉じたら消える）
P.store = {
  ok: false, db: null,
  open: function(){
    var self = this;
    return new Promise(function(res){
      var req;
      try { req = indexedDB.open(DB_NAME, DB_VER); } catch(e){ return res(false); }
      req.onupgradeneeded = function(){
        var db = req.result;
        STORES.forEach(function(s){ if(!db.objectStoreNames.contains(s)) db.createObjectStore(s, {keyPath:"id"}); });
      };
      req.onsuccess = function(){ self.db = req.result; res(true); };
      req.onerror = function(){ res(false); };
      req.onblocked = function(){ res(false); };
    }).then(async function(okOpen){
      if(!okOpen) return (self.ok = false);
      /* 実際に書いて読んで確かめる */
      try {
        await self.put("kv", {id:"probe", at:Date.now()});
        var got = await self.get("kv", "probe");
        self.ok = !!(got && got.at);
      } catch(e){ self.ok = false; }
      return self.ok;
    });
  },
  _tx: function(store, mode){ return this.db.transaction(store, mode).objectStore(store); },
  get: function(store, id){
    if(!this.db) return Promise.resolve((mem[store] || {})[id]);
    var self = this;
    return new Promise(function(res, rej){ var r = self._tx(store, "readonly").get(id); r.onsuccess = function(){ res(r.result); }; r.onerror = function(){ rej(r.error); }; });
  },
  put: function(store, val){
    if(!this.db){ (mem[store] = mem[store] || {})[val.id] = val; return Promise.resolve(val); }
    var self = this;
    return new Promise(function(res, rej){ var r = self._tx(store, "readwrite").put(val); r.onsuccess = function(){ res(val); }; r.onerror = function(){ rej(r.error); }; });
  },
  del: function(store, id){
    if(!this.db){ delete (mem[store] || {})[id]; return Promise.resolve(); }
    var self = this;
    return new Promise(function(res, rej){ var r = self._tx(store, "readwrite").delete(id); r.onsuccess = function(){ res(); }; r.onerror = function(){ rej(r.error); }; });
  },
  all: function(store){
    if(!this.db) return Promise.resolve(Object.keys(mem[store] || {}).map(function(k){ return mem[store][k]; }));
    var self = this;
    return new Promise(function(res, rej){ var r = self._tx(store, "readonly").getAll(); r.onsuccess = function(){ res(r.result || []); }; r.onerror = function(){ rej(r.error); }; });
  },
  kv: async function(id, fallback){ var v = await this.get("kv", id); return v ? v.value : fallback; },
  setKv: function(id, value){ return this.put("kv", {id:id, value:value}); }
};

/* ---------- 端末の中の名前（sid → 名前）。通信には一切入れない ---------- */
P.names = {
  map: {},
  load: async function(){ this.map = (await P.store.kv("names", {})) || {}; return this.map; },
  save: function(){ return P.store.setKv("names", this.map); },
  of: function(sid){ return this.map[sid] || ""; }
};
/* 画面に出す呼び名：名前があれば「名前（小4β-07）」、無ければ「小4β-07」 */
P.who = function(row){
  var n = P.names.of(row.sid);
  return n ? P.esc(n) + '<span class="sub">' + P.esc(row.label) + '</span>' : P.esc(row.label);
};

/* ---------- 講師のコース（/api/me の assign から） ---------- */
P.courses = function(){
  var prof = P.state.profile || {}, by = {}, list = [];
  (prof.assign || []).forEach(function(s){
    if(!s.key || s.key.indexOf(":") < 0 || s.app === false) return;
    var c = by[s.key];
    if(!c){ c = by[s.key] = {key:s.key, name:s.name || s.key, subject:s.subject, use:s.use == null ? 4 : s.use, slots:[]}; list.push(c); }
    c.slots.push({day:s.day, start:s.start || "", end:s.end || ""});
  });
  var now = new Date(), wd = now.getDay() === 0 ? 7 : now.getDay(), hm = P.pad2(now.getHours()) + ":" + P.pad2(now.getMinutes());
  list.forEach(function(c){
    var today = c.slots.filter(function(s){ return s.day === wd; });
    c.today = today.length ? today[0].start : "";
    /* 今か直前の授業（始まって3時間以内、始まる30分前から） */
    c.near = today.some(function(s){
      if(!s.start) return false;
      var m = toMin(s.start), n = toMin(hm);
      return n >= m - 30 && n <= m + 180;
    });
  });
  list.sort(function(a, b){
    return (b.near - a.near) || ((b.today ? 1 : 0) - (a.today ? 1 : 0)) || (a.today < b.today ? -1 : a.today > b.today ? 1 : 0) ||
           (a.name < b.name ? -1 : a.name > b.name ? 1 : 0);
  });
  return list;
};
function toMin(s){ var p = String(s).split(":"); return (+p[0]) * 60 + (+p[1] || 0); }
P.USE_WORD = {0:"紙のまま", 1:"宿題を出す", 2:"写真で提出", 3:"添削まで", 4:"毎日テストまで"};

/* 回の呼び名：「第12回 分数のたし算」／提出箱は題名 */
P.lessonName = function(l){
  if(!l) return "";
  if(l.label === "提出箱" || (l.n >= 900)) return "提出箱 " + (l.topic || "");
  var n = l.label && l.label !== String(l.n) ? l.label : "第" + l.n + "回";
  return n + (l.topic ? "　" + l.topic : "");
};

})(window);
