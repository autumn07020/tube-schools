/* 点検用（スクラッチパッドのコピーだけに置く。本番には送らない）。
   押せる部品を1つずつ押し、何が起きたかを返す。 */
window.__AUD = (function(){
  var U = window.TubeUI, S = U.S;
  var errs = [];
  if(!window.__audHooked){
    window.__audHooked = true;
    window.addEventListener('error', function(e){ errs.push('error: ' + (e.message || e.type)); });
    window.addEventListener('unhandledrejection', function(e){
      var r = e.reason; errs.push('promise: ' + (r && (r.message || r)));
    });
    var ce = console.error;
    console.error = function(){
      errs.push('console: ' + [].slice.call(arguments).join(' '));
      return ce.apply(console, arguments);
    };
  }
  function h(s){ var x = 0; for(var i = 0; i < s.length; i++){ x = (x * 31 + s.charCodeAt(i)) | 0; } return x; }
  function sig(){
    var m = document.getElementById('main'), t = document.getElementById('toast');
    return [S.view, S.session ? 'S' : '', document.querySelectorAll('.sheet').length,
      h(m ? m.innerHTML : ''),
      h((document.getElementById('foot') || {}).innerHTML || '') + h((document.getElementById('chrome') || {}).innerHTML || ''),
      (t && t.classList.contains('on')) ? t.textContent : ''].join('|');
  }
  function key(el){
    var attrs = [].slice.call(el.attributes).filter(function(a){ return /^data-|^id$|^aria-label$/.test(a.name); })
      .map(function(a){ return a.name + '=' + a.value; }).join(',');
    return el.tagName.toLowerCase() + '|' + (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 36) + '|' + attrs;
  }
  function list(){
    /* 紙（.sheet）が開いているときは、いちばん上の紙の中だけ。下の画面は影で押せない。 */
    var sheets = document.querySelectorAll('.sheet');
    var root = sheets.length ? sheets[sheets.length - 1] : document;
    return [].slice.call(root.querySelectorAll('button, a[href], [role=button], label.hw-up, select'))
      .filter(function(el){ return el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden'; });
  }
  function sleep(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }
  function closeAll(){
    ['#fBack', '[data-subshut]', '[data-stushut]', '[data-shut]'].forEach(function(sel){
      var b = document.querySelector(sel);
      if(b && typeof b.onclick === 'function'){ try{ b.onclick(); }catch(e){} }
    });
  }
  function by(sel, re){
    return [].slice.call(document.querySelectorAll(sel)).filter(function(b){ return re.test(b.textContent); })[0];
  }
  var EX = 'ログアウト|取り消す|削除|消す|在籍終了|退塾|リセット|作り直|印刷|PDF|書き出す|ダウンロード';
  async function runD(prep, exclude, from, to, restore){
    var rs = restore ? new RegExp(restore) : null;
    var ex = new RegExp(exclude || EX);
    await prep(); await sleep(300);
    var keys = [];
    list().forEach(function(el){ var k = key(el); if(keys.indexOf(k) < 0) keys.push(k); });
    var total = keys.length;
    keys = keys.slice(from || 0, to == null ? keys.length : to);
    var out = ['（全' + total + '件のうち ' + (from || 0) + '〜' + ((from || 0) + keys.length) + '）'];
    for(var i = 0; i < keys.length; i++){
      var k = keys[i];
      var short = k.split('|').slice(0, 2).join('|');
      if(ex.test(k) || /^label\|/.test(k) || /^select\|/.test(k)){ out.push(short + ' => (押さない)'); continue; }
      await prep(); await sleep(220);
      var el = list().filter(function(e){ return key(e) === k; })[0];
      if(!el){ out.push(short + ' => (見つからない)'); continue; }
      var before = sig(); errs.length = 0;
      el.click(); await sleep(600);
      var after = sig(), b = before.split('|'), a = after.split('|');
      var eff = before === after ? 'none'
        : a[0] !== b[0] ? 'view:' + a[0]
        : a[1] !== b[1] ? 'session'
        : a[2] !== b[2] ? 'sheet:' + a[2]
        : (a[5] && a[5] !== b[5]) ? 'toast:' + a[5].slice(0, 24) : 'redraw';
      var t = (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 24);
      var d = [].slice.call(el.attributes).filter(function(x){ return /^data-/.test(x.name); })
        .map(function(x){ return x.name.slice(5) + '=' + x.value.slice(0, 10); }).join(',');
      var back = '';
      /* 切り替え部品は、効き目を見たあと押し戻す（後の部品の検査を崩さない）。 */
      if(rs && rs.test(k)){
        var base = function(x){ return (x.split('|').slice(2).join('|') || '').replace(/\|\d+(?=,|$)/g, ''); };
        var el2 = list().filter(function(e){ return base(key(e)) && base(key(e)) === base(k); })[0];
        if(el2){ el2.click(); await sleep(900); var nt = function(x){ return x.split('|').slice(0, 5).join('|'); }; back = nt(sig()) === nt(before) ? ' (戻した)' : ' (戻らない!)'; } else back = ' (戻せない)';
      }
      out.push(t + (d ? ' [' + d + ']' : '') + ' => ' + eff + back + (errs.length ? '  ERR ' + errs.slice(0, 2).join(' / ') : ''));
    }
    return out.join('\n');
  }
  return {runD: runD, sig: sig, list: list, key: key, sleep: sleep, closeAll: closeAll, by: by, errs: errs};
})();
