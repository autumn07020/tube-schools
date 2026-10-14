#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紙の宿題の画面を、iPad の横（1180×820）と縦（820×1180）で撮る（目で確かめるため）。
あわせて、押せそうなのに押せない物（44px 未満のボタン・中身の無いボタン）を数える。

    sh 紙の宿題/検査/デモ.sh start ; python3 紙の宿題/検査/e2e.py ; python3 紙の宿題/検査/shots.py
写真は 紙の宿題/検査/作業.nosync/shots/ に出る。
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(HERE, "作業.nosync")
os.environ["TMPDIR"] = os.path.join(W, "tmp")
sys.path.insert(0, HERE)
from cdp import Chrome  # noqa: E402

RELAY = "http://127.0.0.1:8941"
OUT = os.path.join(W, "shots")
os.makedirs(OUT, exist_ok=True)
acc = {a["id"]: a for a in json.load(open(os.path.join(W, "demo", "demo-accounts.json"), encoding="utf-8"))}

SMALL = r"""(function(){
  var bad = [];
  document.querySelectorAll('#main button, #main label.btn2, header button').forEach(function(b){
    if(b.offsetParent === null) return;
    var r = b.getBoundingClientRect();
    if(r.height < 36 || r.width < 36) bad.push((b.textContent || b.getAttribute('aria-label') || '?').trim().slice(0, 20) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
    if(!(b.textContent || '').trim() && !b.getAttribute('aria-label') && !b.querySelector('img')) bad.push('中身の無いボタン');
  });
  return bad;
})()"""


def main():
    for tag, (w, h) in [("横", (1180, 820)), ("縦", (820, 1180))]:
        with Chrome(width=w, height=h, scale=1) as c:
            c.goto(RELAY + "/", wait=1.2)
            c.shot(os.path.join(OUT, "%s-0-login.png" % tag))
            c.eval("document.getElementById('lid').value='lteacher1';document.getElementById('lpw').value='%s';document.getElementById('lgo').click();"
                   % acc["lteacher1"]["password"])
            c.wait_for("document.querySelector('h1') && document.querySelector('h1').textContent==='今日やること'", 20)
            time.sleep(0.8)
            steps = [
                ("1-home", "Paper.show('home')", "document.querySelectorAll('.act').length===2"),
                ("2-course", "Paper.show('intake')", "document.querySelectorAll('.ccard').length>0"),
                ("3-lesson", "document.querySelector('.ccard[data-key=\"e4b:japanese\"]').click()", "document.querySelectorAll('.lrow').length>0"),
                ("4-files", "document.querySelector('.lrow').click()", "!!document.getElementById('files')"),
                ("5-grade", "Paper.api.check('e4b:japanese').then(function(d){ var l = d.lessons.filter(function(x){ return x.submitted; })[0]; Paper.show('grade', {key:'e4b:japanese', n:l.n}); })", "!!document.querySelector('#stage canvas')"),
                ("6-names", "Paper.show('names')", "document.querySelectorAll('.ccard').length>0"),
                ("7-names-course", "document.querySelector('.ccard[data-key=\"e4b:japanese\"]').click()", "!!document.querySelector('.tbl')"),
                ("8-print", "Paper.show('print', {kind:'ans'})", "document.querySelectorAll('.ccard').length>0"),
                ("9-print-course", "document.querySelector('.ccard[data-key=\"e4b:japanese\"]').click()", "!!document.getElementById('pgo')"),
                ("10-help", "Paper.show('help')", "!!document.querySelector('.helpbox')"),
            ]
            for name, js, ready in steps:
                try:
                    c.eval(js)
                except RuntimeError as e:
                    print("  %s %s: %s" % (tag, name, e))
                    continue
                okk = c.wait_for(ready, 30)
                time.sleep(0.7)
                c.shot(os.path.join(OUT, "%s-%s.png" % (tag, name)), full=True)
                bad = c.eval(SMALL)
                print("  %s %-16s %s%s" % (tag, name, "OK" if okk else "× 出ない", ("  小さい/空のボタン: " + ", ".join(bad)) if bad else ""))
    print("写真: %s" % OUT)


if __name__ == "__main__":
    main()
