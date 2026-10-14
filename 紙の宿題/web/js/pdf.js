/* ============================================================
   PDF の中の写真を、ページの順に取り出す（描画しない。端末の中だけ）
   ============================================================

   スキャンの PDF（校舎の複合機・iPad の「書類をスキャン」）は、ほとんどが「1ページ＝写真1枚」。
   PDF を描く部品（数 MB）を持たずに、写真そのもの（JPEG）を取り出せば足りる。

   読むもの
     ・ページの木（/Catalog → /Pages → /Kids）。圧縮されたオブジェクト（/ObjStm）も読む
     ・ページの /Resources の /XObject（入れ子の /Form も）と、中身の命令（cm・Do）で
       どの写真を・どの向きで貼ったか。ページの /Rotate
     ・写真の形：DCTDecode（JPEG）、FlateDecode（生の画素。予測子つきも）
   読まないもの（そう言う）
     ・CCITT・JBIG2・JPEG2000（白黒の高圧縮）。複合機の設定を「カラーかグレー」にしてもらう

   返すもの：pages = [{parts:[{kind:"jpeg", bytes} | {kind:"raw", w, h, rgba}], turns, w, h}]
     turns … 画像を右に何回（90°ずつ）回せば、ページの見た目の向きになるか
   ============================================================ */
(function(root){
"use strict";

function latin1(bytes, a, b){
  var out = [], CH = 8192;
  for(var i = a; i < b; i += CH) out.push(String.fromCharCode.apply(null, bytes.subarray(i, Math.min(b, i + CH))));
  return out.join("");
}

async function inflate(bytes){
  if(typeof DecompressionStream === "undefined") throw new Error("この端末のブラウザでは PDF の圧縮を解けません（新しい Safari か Chrome で開いてください）");
  var ds = new DecompressionStream("deflate");
  var stream = new Blob([bytes]).stream().pipeThrough(ds);
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/* ---------- 字句と値 ---------- */
var WS = /[\x00\t\n\f\r ]/, DELIM = /[()<>\[\]{}\/%]/;

function Parser(s, pos){ this.s = s; this.p = pos || 0; }
Parser.prototype.skip = function(){
  var s = this.s;
  while(this.p < s.length){
    var c = s[this.p];
    if(WS.test(c)) this.p++;
    else if(c === "%"){ while(this.p < s.length && s[this.p] !== "\n" && s[this.p] !== "\r") this.p++; }
    else break;
  }
};
Parser.prototype.value = function(){
  this.skip();
  var s = this.s, c = s[this.p];
  if(c === undefined) return undefined;
  if(c === "<" && s[this.p + 1] === "<"){
    this.p += 2;
    var d = {};
    for(;;){
      this.skip();
      if(s[this.p] === ">" && s[this.p + 1] === ">"){ this.p += 2; break; }
      if(this.p >= s.length) break;
      var k = this.value();
      if(!k || k.name === undefined) { this.p++; continue; }
      d[k.name] = this.value();
    }
    return {dict:d};
  }
  if(c === "["){
    this.p++;
    var a = [];
    for(;;){
      this.skip();
      if(s[this.p] === "]"){ this.p++; break; }
      if(this.p >= s.length) break;
      a.push(this.value());
    }
    return {arr:a};
  }
  if(c === "/"){
    var j = this.p + 1;
    while(j < s.length && !WS.test(s[j]) && !DELIM.test(s[j])) j++;
    var nm = s.slice(this.p + 1, j).replace(/#([0-9A-Fa-f]{2})/g, function(_, h){ return String.fromCharCode(parseInt(h, 16)); });
    this.p = j;
    return {name:nm};
  }
  if(c === "("){
    var depth = 1, j2 = this.p + 1, str = "";
    while(j2 < s.length && depth){
      var ch = s[j2];
      if(ch === "\\"){ str += s[j2 + 1] || ""; j2 += 2; continue; }
      if(ch === "(") depth++;
      else if(ch === ")"){ depth--; if(!depth) break; }
      str += ch; j2++;
    }
    this.p = j2 + 1;
    return {str:str};
  }
  if(c === "<"){
    var e = s.indexOf(">", this.p);
    var hex = s.slice(this.p + 1, e).replace(/\s+/g, "");
    this.p = e + 1;
    var out = "";
    for(var i = 0; i < hex.length; i += 2) out += String.fromCharCode(parseInt((hex[i] + (hex[i + 1] || "0")), 16));
    return {str:out};
  }
  var m = /^[+-]?(\d+\.?\d*|\.\d+)/.exec(s.slice(this.p, this.p + 32));
  if(m){
    this.p += m[0].length;
    var num = parseFloat(m[0]);
    /* 「12 0 R」は参照 */
    var save = this.p, m2 = /^\s+(\d+)\s+R(?![A-Za-z])/.exec(s.slice(this.p, this.p + 24));
    if(m2 && /^\d+$/.test(m[0])){ this.p = save + m2[0].length; return {ref:num}; }
    return num;
  }
  var j3 = this.p;
  while(j3 < s.length && !WS.test(s[j3]) && !DELIM.test(s[j3])) j3++;
  var word = s.slice(this.p, j3);
  this.p = j3 === this.p ? this.p + 1 : j3;
  if(word === "true") return true;
  if(word === "false") return false;
  if(word === "null") return null;
  return {op:word};
};

/* ---------- 文書 ---------- */
function Doc(bytes){
  this.bytes = bytes;
  this.text = latin1(bytes, 0, bytes.length);
  this.objs = {};         // 番号 → {at:位置} か {inline:文字列}
  this.cache = {};
  /* 前から順に「N G obj」を拾う。ストリームの中身（写真のバイト）は飛ばす
     ―― 写真の中に偶然「12 0 obj」が並んでも、取り違えないように。 */
  var t = this.text, re = /(\d+)\s+(\d+)\s+obj\b/g, m;
  while((m = re.exec(t))){
    var at = m.index + m[0].length;
    this.objs[+m[1]] = {at:at};
    var eo = t.indexOf("endobj", at), st = t.indexOf("stream", at);
    if(st >= 0 && (eo < 0 || st < eo)){
      var es = t.indexOf("endstream", st + 6);
      if(es > 0) re.lastIndex = es + 9;
    } else if(eo > 0) re.lastIndex = eo + 6;
  }
}
Doc.prototype.load = async function(){
  /* 圧縮されたオブジェクト（/ObjStm）を開く。ストリームそのものはこの中に入らない。 */
  var nums = Object.keys(this.objs);
  for(var i = 0; i < nums.length; i++){
    var o = this.objs[nums[i]];
    if(o.inline !== undefined) continue;
    var head = this.text.slice(o.at, o.at + 400);
    if(!/\/Type\s*\/ObjStm/.test(head)) continue;
    var v = this.get(+nums[i]);
    if(!v || !v.stream) continue;
    var data;
    try { data = await this.decode(v); } catch(e){ continue; }
    var txt = latin1(data, 0, data.length), n = +(v.dict.N || 0), first = +(v.dict.First || 0);
    var hp = new Parser(txt, 0), pairs = [];
    for(var k = 0; k < n; k++){ var a = hp.value(), b = hp.value(); pairs.push([a, b]); }
    for(k = 0; k < pairs.length; k++){
      var start = first + pairs[k][1], end = k + 1 < pairs.length ? first + pairs[k + 1][1] : txt.length;
      if(!this.objs[pairs[k][0]] || this.objs[pairs[k][0]].inline !== undefined) this.objs[pairs[k][0]] = {inline:txt.slice(start, end)};
    }
  }
};
Doc.prototype.get = function(num){
  if(this.cache[num] !== undefined) return this.cache[num];
  var o = this.objs[num];
  if(!o) return null;
  var out;
  if(o.inline !== undefined){ out = new Parser(o.inline, 0).value(); }
  else {
    var p = new Parser(this.text, o.at), v = p.value();
    out = v;
    if(v && v.dict){
      p.skip();
      if(this.text.substr(p.p, 6) === "stream"){
        var at = p.p + 6;
        if(this.text[at] === "\r") at++;
        if(this.text[at] === "\n") at++;
        var len = this.resolve(v.dict.Length), end = -1;
        if(typeof len === "number" && /^\s*endstream/.test(this.text.substr(at + len, 20))) end = at + len;
        else { end = this.text.indexOf("endstream", at); while(end > at && /[\r\n]/.test(this.text[end - 1])) end--; }
        out = {dict:v.dict, stream:[at, end]};
      }
    }
  }
  this.cache[num] = out;
  return out;
};
Doc.prototype.resolve = function(v){
  var n = 0;
  while(v && v.ref !== undefined && n++ < 20) v = this.get(v.ref);
  return v;
};
Doc.prototype.raw = function(v){ return this.bytes.subarray(v.stream[0], v.stream[1]); };
Doc.prototype.filters = function(d){
  var f = this.resolve(d.Filter);
  if(!f) return [];
  if(f.name) return [f.name];
  return (f.arr || []).map(function(x){ return x && x.name; });
};
/* ストリームを解く（Flate だけ。ほかの形はそのまま返さずに投げる） */
Doc.prototype.decode = async function(v){
  var fs = this.filters(v.dict), data = this.raw(v);
  for(var i = 0; i < fs.length; i++){
    if(fs[i] === "FlateDecode" || fs[i] === "Fl") data = await inflate(data);
    else throw new Error("filter:" + fs[i]);
  }
  return data;
};

/* ---------- ページ ---------- */
Doc.prototype.pages = function(){
  var self = this, out = [];
  var cat = null;
  Object.keys(this.objs).forEach(function(n){
    if(cat) return;
    var v = self.get(+n);
    if(v && v.dict && v.dict.Type && v.dict.Type.name === "Catalog") cat = v.dict;
  });
  function walk(node, inh, depth){
    if(!node || depth > 30) return;
    var d = node.dict || node;
    var res = d.Resources !== undefined ? d.Resources : inh.res;
    var rot = d.Rotate !== undefined ? self.resolve(d.Rotate) : inh.rot;
    var box = d.MediaBox !== undefined ? self.resolve(d.MediaBox) : inh.box;
    var type = d.Type && d.Type.name;
    if(type === "Pages" || (d.Kids && type !== "Page")){
      var kids = self.resolve(d.Kids);
      ((kids && kids.arr) || []).forEach(function(k){ walk(self.resolve(k), {res:res, rot:rot, box:box}, depth + 1); });
    } else out.push({dict:d, res:res, rot:+rot || 0, box:box});
  }
  if(cat) walk(this.resolve(cat.Pages), {res:null, rot:0, box:null}, 0);
  if(!out.length){
    Object.keys(this.objs).map(Number).sort(function(a, b){ return self.objs[a].at - self.objs[b].at || a - b; }).forEach(function(n){
      var v = self.get(n);
      if(v && v.dict && v.dict.Type && v.dict.Type.name === "Page") out.push({dict:v.dict, res:v.dict.Resources, rot:+self.resolve(v.dict.Rotate) || 0, box:v.dict.MediaBox});
    });
  }
  return out;
};

function mul(a, b){   // [a b c d e f] の掛け算（a を先に、b を後に）
  return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3], a[2] * b[0] + a[3] * b[2],
          a[2] * b[1] + a[3] * b[3], a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]];
}

/* ページの中身（1つか、配列）を1本の文字列にする */
Doc.prototype.contentText = async function(contents){
  var c = this.resolve(contents), parts = [];
  if(!c) return "";
  var list = c.arr ? c.arr : [contents];
  for(var i = 0; i < list.length; i++){
    var s = this.resolve(list[i]);
    if(s && s.stream){ try { var d = await this.decode(s); parts.push(latin1(d, 0, d.length)); } catch(e){} }
  }
  return parts.join("\n");
};

/* 中身の命令を読み、貼った写真と、そのときの行列を集める。形（Form）の中にも入る。 */
Doc.prototype.draws = async function(text, res, ctm, depth, out){
  if(depth > 6) return;
  var R = this.resolve(res), xo = R && R.dict ? this.resolve(R.dict.XObject) : null;
  var xmap = (xo && xo.dict) || {};
  var p = new Parser(text, 0), stack = [], cur = ctm.slice(), args = [];
  while(p.p < text.length){
    var v = p.value();
    if(v === undefined) break;
    if(v && v.op !== undefined){
      var op = v.op;
      if(op === "q") stack.push(cur.slice());
      else if(op === "Q") cur = stack.pop() || ctm.slice();
      else if(op === "cm" && args.length >= 6) cur = mul(args.slice(-6).map(Number), cur);
      else if(op === "BI"){ var e = text.indexOf("EI", p.p); p.p = e < 0 ? text.length : e + 2; }
      else if(op === "Do" && args.length && args[args.length - 1] && args[args.length - 1].name !== undefined){
        var x = this.resolve(xmap[args[args.length - 1].name]);
        if(x && x.dict){
          var st = x.dict.Subtype && x.dict.Subtype.name;
          if(st === "Image") out.push({img:x, ctm:cur.slice()});
          else if(st === "Form" && x.stream){
            var fm = this.resolve(x.dict.Matrix), m2 = fm && fm.arr ? fm.arr.map(Number) : [1, 0, 0, 1, 0, 0];
            var ft = "";
            try { var fd = await this.decode(x); ft = latin1(fd, 0, fd.length); } catch(err){ ft = ""; }
            await this.draws(ft, x.dict.Resources || res, mul(m2, cur), depth + 1, out);
          }
        }
      }
      args = [];
    } else args.push(v);
  }
};

/* 写真1枚を、取り出せる形にする */
Doc.prototype.image = async function(x){
  var d = x.dict, fs = this.filters(d);
  var w = +this.resolve(d.Width), h = +this.resolve(d.Height);
  if(fs.length && fs[fs.length - 1] === "DCTDecode"){
    var data = this.raw(x);
    for(var i = 0; i < fs.length - 1; i++){
      if(fs[i] === "FlateDecode") data = await inflate(data); else throw new Error("filter:" + fs[i]);
    }
    return {kind:"jpeg", bytes:data, w:w, h:h};
  }
  if(!fs.length || fs.every(function(f){ return f === "FlateDecode"; })){
    var raw = fs.length ? await this.decode(x) : this.raw(x);
    var bpc = +this.resolve(d.BitsPerComponent) || 8;
    var cs = this.resolve(d.ColorSpace), comps = 1, lookup = null;
    var csn = cs && (cs.name || (cs.arr && cs.arr[0] && cs.arr[0].name));
    if(csn === "DeviceRGB" || csn === "CalRGB") comps = 3;
    else if(csn === "DeviceCMYK") comps = 4;
    else if(csn === "ICCBased"){ var icc = this.resolve(cs.arr[1]); comps = +((icc && icc.dict && this.resolve(icc.dict.N)) || 3); }
    else if(csn === "Indexed"){
      var lk = this.resolve(cs.arr[3]);
      var lkd = lk && lk.stream ? await this.decode(lk) : null;
      lookup = lk && lk.str !== undefined ? lk.str : (lkd ? latin1(lkd, 0, lkd.length) : "");
      var base = this.resolve(cs.arr[1]);
      lookup = {s:lookup, n:(base && base.name === "DeviceGray") ? 1 : 3};
    }
    var dp = this.resolve(d.DecodeParms);
    if(dp && dp.arr) dp = this.resolve(dp.arr[0]);
    var pred = dp && dp.dict ? +(this.resolve(dp.dict.Predictor) || 1) : 1;
    var ncomp = lookup ? 1 : comps;
    var rowBytes = Math.ceil(w * ncomp * bpc / 8);
    if(pred >= 10) raw = unpredict(raw, rowBytes, Math.max(1, Math.ceil(ncomp * bpc / 8)), h);
    var rgba = new Uint8ClampedArray(w * h * 4);
    for(var y = 0; y < h; y++){
      for(var xx = 0; xx < w; xx++){
        var o = (y * w + xx) * 4, r, g, b;
        if(bpc === 8){
          var at = y * rowBytes + xx * ncomp;
          if(lookup){ var ix = raw[at] * lookup.n; r = lookup.s.charCodeAt(ix); g = lookup.n === 3 ? lookup.s.charCodeAt(ix + 1) : r; b = lookup.n === 3 ? lookup.s.charCodeAt(ix + 2) : r; }
          else if(ncomp === 1){ r = g = b = raw[at]; }
          else if(ncomp === 3){ r = raw[at]; g = raw[at + 1]; b = raw[at + 2]; }
          else { var k = raw[at + 3]; r = 255 - Math.min(255, raw[at] + k); g = 255 - Math.min(255, raw[at + 1] + k); b = 255 - Math.min(255, raw[at + 2] + k); }
        } else if(bpc === 1 && ncomp === 1 && !lookup){
          var bit = (raw[y * rowBytes + (xx >> 3)] >> (7 - (xx & 7))) & 1;
          r = g = b = bit ? 255 : 0;
          var dec = this.resolve(d.Decode);
          if(dec && dec.arr && +dec.arr[0] === 1){ r = g = b = 255 - r; }
        } else throw new Error("bits:" + bpc);
        rgba[o] = r; rgba[o + 1] = g; rgba[o + 2] = b; rgba[o + 3] = 255;
      }
    }
    return {kind:"raw", w:w, h:h, rgba:rgba};
  }
  throw new Error("filter:" + fs.join(","));
};

function unpredict(data, rowBytes, bpp, h){
  var out = new Uint8Array(rowBytes * h), prev = new Uint8Array(rowBytes), p = 0;
  for(var y = 0; y < h; y++){
    var type = data[p++], row = data.subarray(p, p + rowBytes); p += rowBytes;
    var cur = out.subarray(y * rowBytes, (y + 1) * rowBytes);
    for(var i = 0; i < rowBytes; i++){
      var a = i >= bpp ? cur[i - bpp] : 0, b = prev[i], c = i >= bpp ? prev[i - bpp] : 0, x = row[i] || 0, v;
      if(type === 1) v = x + a;
      else if(type === 2) v = x + b;
      else if(type === 3) v = x + ((a + b) >> 1);
      else if(type === 4){ var pa = Math.abs(b - c), pb = Math.abs(a - c), pc = Math.abs(a + b - 2 * c); v = x + ((pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c)); }
      else v = x;
      cur[i] = v & 255;
    }
    prev = cur;
  }
  return out;
}

/* 行列から、写真を何回右に回せばページの向きになるか（ページの /Rotate も足す） */
function turnsOf(ctm, rot){
  var deg = Math.atan2(ctm[1], ctm[0]) * 180 / Math.PI;     // 写真の横の向き（PDF は左回りが正）
  var q = Math.round((-deg + (rot || 0)) / 90);
  return ((q % 4) + 4) % 4;
}

/* 入口。bytes は Uint8Array。返す {pages, errors} */
async function extract(bytes){
  if(latin1(bytes, 0, Math.min(1024, bytes.length)).indexOf("%PDF") < 0) throw new Error("PDF ではありません");
  var doc = new Doc(bytes);
  await doc.load();
  var pages = doc.pages(), out = [], errors = [];
  for(var i = 0; i < pages.length; i++){
    var pg = pages[i], found = [];
    try { await doc.draws(await doc.contentText(pg.dict.Contents), pg.res, [1, 0, 0, 1, 0, 0], 0, found); }
    catch(e){ errors.push({page:i + 1, error:String(e.message || e)}); }
    if(!found.length){
      /* 命令が読めなくても、Resources にある写真を拾う（向きは分からないので 0） */
      var r = doc.resolve(pg.res), xo = r && r.dict ? doc.resolve(r.dict.XObject) : null;
      Object.keys((xo && xo.dict) || {}).forEach(function(k){
        var x = doc.resolve(xo.dict[k]);
        if(x && x.dict && x.dict.Subtype && x.dict.Subtype.name === "Image") found.push({img:x, ctm:[1, 0, 0, 1, 0, 0]});
      });
    }
    /* 小さな写真（ロゴ・透かし・マスク）は外し、大きいものだけ */
    var big = found.filter(function(f){ return (+doc.resolve(f.img.dict.Width) || 0) * (+doc.resolve(f.img.dict.Height) || 0) >= 200 * 200; });
    if(!big.length){ errors.push({page:i + 1, error:"写真がありません"}); continue; }
    var parts = [];
    for(var k = 0; k < big.length; k++){
      try {
        var im = await doc.image(big[k].img);
        im.ctm = big[k].ctm;
        parts.push(im);
      } catch(e){ errors.push({page:i + 1, error:/filter:|bits:/.test(String(e.message)) ? "この形の写真は読めません（" + String(e.message).replace(/^(filter|bits):/, "") + "）" : String(e.message || e)}); }
    }
    if(!parts.length) continue;
    var box = doc.resolve(pg.box), bx = box && box.arr ? box.arr.map(function(v){ return +doc.resolve(v); }) : null;
    out.push({index:i + 1, parts:parts, turns:turnsOf(parts[0].ctm, pg.rot), rot:pg.rot, box:bx});
  }
  return {pages:out, errors:errors, count:pages.length};
}

root.PaperPDF = {extract:extract, turnsOf:turnsOf, _Parser:Parser, _inflate:inflate};
})(typeof window !== "undefined" ? window : this);
