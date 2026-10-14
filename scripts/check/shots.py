# -*- coding: utf-8 -*-
"""デモの画面を撮る。python3 shots.py [--base URL] [--accounts demo-accounts.json] [出力dir] [job名 …]"""
import argparse, json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Chrome

# 既定は expect.py と同じ。巡回の写し（8933）では両方を渡す ―― 置き場所を推し量らない。
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://127.0.0.1:8932")
ap.add_argument("--accounts", default=os.path.join(HERE, "..", "..", "demo-accounts.json"))
ap.add_argument("out", nargs="?", default="shots")
ap.add_argument("names", nargs="*")
ARGS = ap.parse_args()
BASE = ARGS.base.rstrip("/")
OUT = ARGS.out
os.makedirs(OUT, exist_ok=True)
ACC = {r["id"]: r for r in json.load(open(ARGS.accounts, encoding="utf-8"))}


def open_app(c, tries=5):
    """開く。手元のサーバは並列の読み込みで時々1本切る（ERR_CONNECTION_RESET）ので、部品が欠けていたら読み直す。"""
    for i in range(tries):
        c.goto(BASE + "/", wait=0.8)
        if c.wait_for("typeof TubeDesk !== 'undefined' && typeof TubeTeacher !== 'undefined' && typeof TubeStudent !== 'undefined' && (document.querySelector('#main')||{innerHTML:''}).innerHTML.length > 0", 8):
            return True
    return False


def login(c, lid):
    assert open_app(c), "app did not boot"
    # はじめての端末には「ようこそ」が出る。写しは入口（ログイン）から入るので、見たことにしておく。
    c.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1', '1');")
    assert open_app(c), "app did not boot (2)"
    assert c.wait_for("!!document.querySelector('#lId')"), "login form"
    a = ACC[lid]
    c.eval("document.querySelector('#lId').value=%s; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();"
           % (json.dumps(a["id"]), json.dumps(a["password"])))
    ok = c.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)')", 25)
    time.sleep(1.2)
    return ok


def view(c, v, wait=1.5):
    c.eval("(function(){ var b=document.querySelector('[data-tab=%s]'); if(b){ b.click(); return true; } return false; })()" % json.dumps(v))
    time.sleep(wait)


def errors(c):
    return c.eval("window.__errs ? window.__errs.length : 0")


JOBS = {}


def job(name):
    def deco(f):
        JOBS[name] = f
        return f
    return deco


@job("login")
def j_login(c):
    assert open_app(c)
    c.eval("localStorage.clear()")
    assert open_app(c)
    c.wait_for("!!document.querySelector('#demoOpen')", 10)
    c.eval("document.querySelector('#demoOpen').click()")
    time.sleep(1.0)
    c.shot(os.path.join(OUT, "login-sheet.png"))
    n = c.eval("document.querySelectorAll('.demo-pick').length")
    t = c.eval("[].slice.call(document.querySelectorAll('.demo-pick .t')).map(function(x){return x.textContent.trim()})")
    print("login sheet picks", n, t)


@job("t1")
def j_t1(c):
    assert login(c, "lteacher1")
    c.shot(os.path.join(OUT, "t1-today.png"))
    view(c, "progress", 2.5)
    c.shot(os.path.join(OUT, "t1-progress.png"), full=True)
    rows = c.eval("document.querySelectorAll('.use-row').length")
    print("t1 use rows", rows)


@job("t2")
def j_t2(c):
    assert login(c, "lteacher2")
    c.shot(os.path.join(OUT, "t2-today.png"))
    view(c, "progress", 2.5)
    c.shot(os.path.join(OUT, "t2-progress.png"), full=True)
    # はしご（role=radio）のある行だけ。選ばれた段が無い行は「まちまち」（まとめ行でコースの段がそろっていない）
    print("t2 levels", c.eval("[].slice.call(document.querySelectorAll('.use-row')).filter(function(r){return r.querySelector('.use-lad')}).map(function(r){return r.querySelector('.use-name b').textContent+':'+(r.querySelector('[role=radio][aria-checked=true]')||{title:'まちまち'}).title})"))
    # 宿題チェック：e4b:math（写真で提出＝2。添削の札は出ない）
    view(c, "hw", 2.0)
    opened = c.eval("(function(){ var b=[].slice.call(document.querySelectorAll('[data-dkcheck]')).filter(function(x){return /小4β 算数/.test(x.closest('.dk-task,.card,div').textContent)})[0]; if(!b) return null; b.click(); return b.dataset.dkcheck; })()")
    time.sleep(2.5)
    print("t2 check opened", opened)
    c.shot(os.path.join(OUT, "t2-check-e4bmath.png"))
    c.eval("(function(){ var cs=[].slice.call(document.querySelectorAll('.dk-cell')).filter(function(x){return x.querySelector('img')}); if(cs[0]) cs[0].click(); })()")
    time.sleep(1.5)
    c.shot(os.path.join(OUT, "t2-check-e4bmath-cell.png"), full=True)
    print("t2 fix panel", c.eval("!!document.querySelector('.dk-fix:not(.dk-fix-off)')"), "off note", c.eval("!!document.querySelector('.dk-fix-off')"))


@job("t4")
def j_t4(c):
    assert login(c, "lteacher4")
    view(c, "progress", 2.5)
    c.shot(os.path.join(OUT, "t4-progress.png"), full=True)
    view(c, "hw", 2.0)
    c.shot(os.path.join(OUT, "t4-today.png"), full=True)
    opened = c.eval("(function(){ var b=[].slice.call(document.querySelectorAll('[data-dkcheck]')).filter(function(x){return /社会/.test(x.closest('.dk-task,.card,div').textContent)})[0]; if(!b) return null; b.click(); return b.dataset.dkcheck; })()")
    time.sleep(2.5)
    print("t4 check opened", opened, "usenote", c.eval("!!document.querySelector('.dk-usenote')"))
    c.shot(os.path.join(OUT, "t4-check-social.png"), full=True)


@job("s-j3r01")
def j_s1(c):
    assert login(c, "lj3r01")
    c.shot(os.path.join(OUT, "s-j3r01-home.png"), full=True)
    view(c, "homework", 1.5)
    c.shot(os.path.join(OUT, "s-j3r01-hw.png"), full=True)
    print("j3r01 hw states", c.eval("[].slice.call(document.querySelectorAll('.hw-state')).map(function(x){return x.textContent})"))
    view(c, "daily", 1.5)
    c.shot(os.path.join(OUT, "s-j3r01-daily.png"), full=True)
    print("j3r01 daily subjects", c.eval("[].slice.call(document.querySelectorAll('.dcard .lbl')).map(function(x){return x.textContent})"))


@job("s-e4b01")
def j_s2(c):
    assert login(c, "le4b01")
    c.shot(os.path.join(OUT, "s-e4b01-home.png"), full=True)
    view(c, "daily", 1.5)
    print("e4b01 daily subjects", c.eval("[].slice.call(document.querySelectorAll('.dcard .lbl')).map(function(x){return x.textContent})"))
    c.shot(os.path.join(OUT, "s-e4b01-daily.png"), full=True)
    view(c, "homework", 1.5)
    c.shot(os.path.join(OUT, "s-e4b01-hw.png"), full=True)


@job("s-e5b01")
def j_s3(c):
    assert login(c, "le5b01")
    view(c, "daily", 1.5)
    print("e5b01 daily subjects", c.eval("[].slice.call(document.querySelectorAll('.dcard .lbl')).map(function(x){return x.textContent})"))
    view(c, "record", 1.5)
    c.shot(os.path.join(OUT, "s-e5b01-record.png"), full=True)


if __name__ == "__main__":
    names = ARGS.names or list(JOBS)
    for n in names:
        mobile = n.startswith("s-")
        with Chrome(width=390 if mobile else 1440, height=844 if mobile else 900, mobile=mobile) as c:
            c.eval("window.__errs=[]; window.addEventListener('error', function(e){ window.__errs.push(String(e.message)); });")
            try:
                JOBS[n](c)
                print("[%s] ok  js-errors=%s" % (n, errors(c)))
            except Exception as e:
                print("[%s] FAIL %s" % (n, e))
                c.shot(os.path.join(OUT, "fail-%s.png" % n))
