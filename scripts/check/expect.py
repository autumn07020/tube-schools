#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""意味の検査 ―― 画面が「何のためにあるか」から決めた不変条件を、動いているサーバに当てる。

    python3 expect.py [--base http://127.0.0.1:8932] [--accounts …/demo-accounts.json]
                      [--ledger …/ledger.json] [--ui] [--strict]

「壊れていないか」ではなく「嘘をついていないか」を見る（Claude outputs/検査の思考法-意味で確かめる.md）。
  ・講師：成績のコース＝使っているコース全部。次の授業は今日以降。人数は受け取る生徒。理解度は 0〜100
  ・講師：今日やることは、写真を使う段階（2 以上）のコースだけ。期限は過ぎている
  ・講師：宿題チェックの人数＝その回の受け取り手。添削の可否は段階どおり
  ・生徒：教科の印（アプリ／紙／段階）が食い違わない。宿題は使っている教科だけ。写真は段階 2 以上だけ
  ・前回より数が 25% 以上減っていない（ledger.json）―― 「なぜこんなに減っている」を機械が先に言う
  ・--ui：Chrome で画面の数と API の数を突き合わせる（cdp.py）
"""
import argparse
import re
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "server"))
import scram                                     # noqa: E402  入る手順

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "tubestudy-expect/1 (scripts/check/expect.py)"
ok_n = ng_n = warn_n = 0
LOG = []
USE = {}   # 講師 id → {コースの key: 段階}（API の /me）。画面のはしごと突き合わせる（--ui）


def check(name, cond, detail="", why=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   %s" % name)
    else:
        ng_n += 1
        print("  ×    %s  %s" % (name, detail if detail != "" else ""))
        if why:
            print("       目的: %s" % why)
    LOG.append((name, bool(cond)))


def warn(msg):
    global warn_n
    warn_n += 1
    print("  △    %s" % msg)


class Api:
    def __init__(self, base):
        self.base = base.rstrip("/")

    def call(self, method, path, token=None, body=None):
        req = urllib.request.Request(self.base + "/api" + path, method=method)
        req.add_header("User-Agent", UA)          # Cloudflare の縁は Python 既定の名乗りを 403 で返す
        if token:
            req.add_header("Authorization", "Bearer " + token)
        if body is not None:
            req.add_header("Content-Type", "application/json")
            req.data = json.dumps(body).encode()
        try:
            r = urllib.request.urlopen(req, timeout=30)
            return r.status, json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode() or "{}")
            except ValueError:
                return e.code, {}

    def login(self, lid, pw):
        # 合言葉そのものは送らない（server/scram.py の手順）。
        st, b = scram.login(self.base, lid, pw, post=lambda path, body: self.call("POST", path, body=body))
        return b.get("token") if st == 200 else None

    def get(self, path, token):
        st, b = self.call("GET", path, token)
        return b if st == 200 else None


def today_str():
    return time.strftime("%Y-%m-%d")


# ------------------------------------------------------------------ 講師
def teacher_checks(api, acc, metrics):
    lid = acc["id"]
    print("\n講師 %s（%s）" % (lid, acc.get("label", "")))
    tok = api.login(lid, acc["password"])
    check("入れる", bool(tok), why="入口の合言葉一覧とサーバの合言葉が同じ")
    if not tok:
        return
    me = api.get("/me", tok) or {}
    prof = me.get("profile") or {}
    assign = prof.get("assign") or []
    courses = {}
    for s in assign:
        if s.get("key") and s["key"] not in courses:
            courses[s["key"]] = {"use": s.get("use", 4 if s.get("app", True) else 0), "app": s.get("app", True), "name": s.get("name")}
    using = {k for k, c in courses.items() if c["use"] >= 1}
    USE[lid] = {k: c["use"] for k, c in courses.items()}
    check("担当コースが1つ以上ある", len(courses) > 0, len(courses), "担当が無い講師には何も出ない")
    check("段階（use）と使う印（app）が食い違わない",
          all((c["use"] >= 1) == bool(c["app"]) for c in courses.values()),
          {k: (c["use"], c["app"]) for k, c in courses.items() if (c["use"] >= 1) != bool(c["app"])})

    ov = api.get("/insight/overview", tok) or {}
    rows = ov.get("courses") or []
    keys = {r.get("key") for r in rows}
    check("成績の「すべて」に、使っているコースが全部ある（多くも少なくもない）", keys == using,
          {"成績だけ": sorted(keys - using), "担当だけ": sorted(using - keys)},
          "成績は、使っているコースの全部を1枚ずつ。紙のままのコースは出さない")
    td = today_str()
    for r in rows:
        nm = r.get("name") or r.get("key")
        units = r.get("units") or []
        check("%s：生徒が1人以上" % nm, (r.get("students") or 0) >= 1, r.get("students"), "受け取る生徒が0人のコースは成績に出さない")
        ns = [u.get("n") for u in units if isinstance(u.get("n"), int)]
        check("%s：単元は回の順" % nm, ns == sorted(ns), ns)
        und = [u.get("und") for u in units if u.get("und") is not None]
        check("%s：理解度は 0〜100" % nm, all(0 <= x <= 100 for x in und), und)
        lt = r.get("latest") or {}
        check("%s：最新の単元は、単元の並びの中にある" % nm, (not lt) or lt.get("n") in ns, (lt.get("n"), ns))
        check("%s：個別の宿題の人数 ≤ 生徒数" % nm, (r.get("personal") or 0) <= (r.get("students") or 0), (r.get("personal"), r.get("students")))
        # コースの画面
        d = api.get("/insight/course?key=%s" % urllib.request.quote(r.get("key") or ""), tok) or {}
        nx = d.get("next") or {}
        check("%s：次の授業は今日以降（%s）" % (nm, nx.get("date") or "―"),
              (not nx.get("date")) or nx.get("date") >= td, nx.get("date"),
              "「次の授業」は次に出す回。過ぎた回・出さない回を指すと、個別の宿題の効き始めも狂う（09-23 の不具合）")
        check("%s：コースの画面の人数 ＝ すべての札の人数" % nm, len(d.get("students") or []) == (r.get("students") or 0),
              (len(d.get("students") or []), r.get("students")))
        cu = (d.get("units") or [])
        check("%s：コースの画面の単元は日付の順" % nm,
              [u.get("date") for u in cu if u.get("date")] == sorted(u.get("date") for u in cu if u.get("date")),
              [u.get("date") for u in cu][:8])
        for st in d.get("students") or []:
            if st.get("avg") is not None and not (0 <= st["avg"] <= 100):
                check("%s：%s の平均が 0〜100" % (nm, st.get("label")), False, st.get("avg"))
        metrics["%s.%s.students" % (lid, r.get("key"))] = r.get("students") or 0
        metrics["%s.%s.units" % (lid, r.get("key"))] = len(units)
    metrics["%s.overview.courses" % lid] = len(rows)

    tdy = api.get("/today", tok) or {}
    tasks = tdy.get("tasks") or []
    now_ms = time.time() * 1000
    for t in tasks:
        nm = t.get("name") or t.get("key")
        c = courses.get(t.get("key"), {})
        check("今日やること「%s」は、写真を使う段階（2以上）のコース" % nm, c.get("use", 4) >= 2, c.get("use"),
              "段階 1（宿題を出す）は提出も評価も紙のまま。今日やることには出ない")
        check("今日やること「%s」の期限は過ぎている" % nm, (t.get("dueAt") or 0) <= now_ms, t.get("dueAt"))
        check("今日やること「%s」：未評価 ≤ 写真 ≤ 人数" % nm,
              0 <= (t.get("todo") or 0) <= (t.get("submitted") or 0) <= (t.get("total") or 0),
              (t.get("todo"), t.get("submitted"), t.get("total")))
        ck = api.get("/check?key=%s&n=%s" % (urllib.request.quote(t.get("key") or ""), t.get("n")), tok) or {}
        stt = ck.get("stats") or {}
        check("宿題チェック「%s」の人数 ＝ 今日やることの人数" % nm, stt.get("n") == t.get("total"), (stt.get("n"), t.get("total")))
        check("宿題チェック「%s」に段階（use）が届く" % nm, isinstance((ck.get("course") or {}).get("use"), int), ck.get("course"))
    # 今日やることの外に、期限が来た未評価が残っていない（09-28 の問い：朝 5件 → 夜 3件は隠れた仕事ではないか）。
    # 宿題チェック（/check）は新しい 12 回まで返す。今日やることも同じ 12 回のうち、未評価の残る回は古くても出す（10-11）。
    # ここに残れば、講師には見えない仕事。
    shown = {(t.get("key"), t.get("n")): (t.get("todo") or 0) for t in tasks}
    hidden, listed = 0, None
    for key, c in courses.items():
        ck = api.get("/check?key=%s" % urllib.request.quote(key), tok) or {}
        if listed is None:
            listed = {x.get("key"): (x.get("todo") or 0) for x in ck.get("courses") or []}
        nm = c.get("name") or key
        left = [(l.get("n"), l.get("todo")) for l in ck.get("lessons") or []
                if (key, l.get("n")) not in shown and (l.get("todo") or 0) > 0]
        hidden += len(left)
        check("「%s」：今日やることに出ていない回に、期限が来た未評価が残っていない" % nm, not left, left,
              "今日やることは新しい3回まで。それより前に未評価が残ると、講師には見えない仕事になる")
        if listed is not None and key in listed:
            mine_todo = sum(v for (k, _n), v in shown.items() if k == key)
            check("「%s」：宿題チェックのコース一覧の未評価 ＝ 今日やることの未評価の合計" % nm,
                  listed[key] == mine_todo, (listed[key], mine_todo))
    metrics["%s.hidden.todo" % lid] = hidden
    metrics["%s.today.tasks" % lid] = len(tasks)
    check("今日つけた評価は 0 以上", (tdy.get("ratedToday") or 0) >= 0)


# ------------------------------------------------------------------ 生徒
def student_checks(api, acc, metrics):
    lid = acc["id"]
    print("\n生徒 %s（%s）" % (lid, acc.get("label", "")))
    tok = api.login(lid, acc["password"])
    check("入れる", bool(tok))
    if not tok:
        return
    me = api.get("/me", tok) or {}
    prof = me.get("profile") or {}
    subs = prof.get("subjects") or []
    app_s = prof.get("appSubjects")
    paper = prof.get("paperSubjects") or []
    use = prof.get("useBySubject") or {}
    if not subs:
        # 受講科目が名簿に無い生徒は、在籍クラスのコースの教科ぜんぶを受講とみなす（サーバの決まり）。
        # 5科の子は同じだが、国数だけの子まで5科になる ―― 名簿の取り込みで受講科目が落ちていないかを見る。
        warn("%s：受講科目が名簿に無い（コースの教科ぜんぶを受講とみなしている）" % lid)
        subs = sorted(set(app_s or []) | set(paper))
    if app_s is not None:
        check("アプリの教科 ＋ 紙の教科 ＝ 受講科目", set(app_s) | set(paper) == set(subs) and not (set(app_s) & set(paper)),
              {"app": app_s, "paper": paper, "subjects": subs},
              "教科は必ずどちらか一方。両方に出る・どちらにも無い教科があると、宿題が消えるか二重に出る")
        check("段階の印は受講科目ぜんぶにある", set(use) == set(subs), {"use": use, "subjects": subs})
        check("段階 1 以上の教科 ＝ アプリの教科", {s for s, v in use.items() if v >= 1} == set(app_s), {"use": use, "app": app_s})
        check("段階は 0〜4", all(isinstance(v, int) and 0 <= v <= 4 for v in use.values()), use)
    asg = api.get("/assignments", tok) or {}
    items = asg.get("assignments") if isinstance(asg, dict) else asg
    items = items or []
    subj_of = lambda a: a.get("subject") or (((a.get("lesson") or {}).get("key") or "").split(":") + [""])[1]
    bad_sub = [a.get("id") for a in items if app_s is not None and subj_of(a) and subj_of(a) not in app_s]
    check("宿題は、アプリを使っている教科のものだけ（%d件）" % len(items), not bad_sub, bad_sub[:5],
          "紙のままの教科の宿題が生徒の画面に出ると、「出していない子」に見える")
    now_ms = time.time() * 1000
    old = [a.get("id") for a in items if a.get("dueAt") and a["dueAt"] < now_ms - 400 * 86400000]
    check("1年より古い宿題は残っていない", not old, old[:5])
    mine = api.get("/submissions/mine", tok) or {}
    mine = mine.get("mine") if isinstance(mine, dict) else mine
    by_id = {a.get("id"): a for a in items}
    bad_ph = []
    aids = list(mine.keys()) if isinstance(mine, dict) else [(x.get("aid") or x.get("id")) for x in (mine or []) if isinstance(x, dict)]
    for aid in aids:
        a = by_id.get(aid)
        if a and use and use.get(subj_of(a), 4) < 2:
            bad_ph.append(aid)
    check("写真の提出は、段階 2 以上の教科だけ", not bad_ph, bad_ph[:5],
          "サーバが 2 未満を 400 で止めている。ここに出たら門が壊れている")
    metrics["%s.assignments" % lid] = len(items)
    metrics["%s.appSubjects" % lid] = len(app_s or subs)
    metrics["%s.quizSubjects" % lid] = len([s for s, v in use.items() if v >= 4]) if use else len(app_s or subs)


# ------------------------------------------------------------------ 前回との差
def gate_checks(api, accounts):
    """門の検査（2026-09-30。お金をいただいて運用する前に）。

    目的：合言葉と席は、決まった人・決まった道でしか動かない。
      ・管理の口（席・講師・担当を作り変える）は、講師にも生徒にも未ログインにも開かない
      ・https で動いている所では、http で来た人を https へ送る（合言葉を暗号なしで流さない）
        ―― 本番は 09-30 まで http のまま 200 を返していた（Cloudflare の設定任せで、サーバは見ていなかった）
    読むだけ。何も変えない。
    """
    print("\n門（管理の口・https）")
    st, _ = api.call("GET", "/admin/state")
    check("管理の口は、未ログインに 401", st == 401, st, "席・講師・担当を作り変える口は管理者だけ")
    for acc in accounts:
        if acc.get("role") not in ("teacher", "student") or not acc.get("password"):
            continue
        tok = api.login(acc["id"], acc["password"])
        if not tok:
            continue
        st, _ = api.call("GET", "/admin/state", tok)
        check("管理の口は、%s（%s）に 403" % ("講師" if acc["role"] == "teacher" else "生徒", acc["id"]), st == 403, st,
              "席・講師・担当を作り変える口は管理者だけ")
        if acc["role"] == "student":
            break
    if api.base.startswith("https://"):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        url = "http://" + api.base[len("https://"):] + "/"
        try:
            r = urllib.request.build_opener(NoRedirect).open(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20)
            code, loc = r.status, r.headers.get("Location") or ""
        except urllib.error.HTTPError as e:
            code, loc = e.code, e.headers.get("Location") or ""
        except Exception as e:                      # noqa: BLE001
            code, loc = 0, str(e)
        check("http で来た人は https へ送られる", code in (301, 302, 307, 308) and loc.startswith("https://"), (code, loc[:60]),
              "http のまま入口が開くと、合言葉が暗号なしで流れる")
        try:
            r = urllib.request.urlopen(urllib.request.Request(api.base + "/", headers={"User-Agent": UA}), timeout=20)
            hsts = r.headers.get("Strict-Transport-Security") or ""
        except Exception:                           # noqa: BLE001
            hsts = ""
        m = re.search(r"max-age=(\d+)", hsts)
        check("以後も https で開かせる（HSTS が 180日以上）", bool(m) and int(m.group(1)) >= 15552000, hsts or "無し",
              "1日だけだと、翌日に http で開いた人がまた暗号なしで流す")


def ledger_checks(path, metrics):
    print("\n前回との差（%s）" % path)
    prev = {}
    if os.path.exists(path):
        try:
            prev = json.load(open(path, encoding="utf-8")).get("metrics") or {}
        except ValueError:
            prev = {}
    if not prev:
        warn("前回の控えが無い。今回の数を控えました（次回から比べます）")
    drops = []
    for k, v in metrics.items():
        p = prev.get(k)
        if isinstance(p, (int, float)) and p > 0:
            if v == 0 or v < p * 0.75:
                drops.append((k, p, v))
    check("前回より 25% 以上減った数が無い", not drops,
          "\n         ".join("%s: %s → %s" % d for d in drops),
          "減るのは、日付が進んだか、出し方が変わったか、壊れたか。理由を言えるまで写さない")
    json.dump({"at": time.strftime("%Y-%m-%d %H:%M"), "metrics": metrics}, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ 画面と API の突き合わせ（任意）
def ui_checks(base, accounts, metrics):
    print("\n画面と API（Chrome）")
    try:
        sys.path.insert(0, HERE)
        from cdp import Chrome
    except Exception as e:
        warn("cdp.py が読めない: %s" % e)
        return
    acc = {a["id"]: a for a in accounts}

    def open_app(c):
        for _ in range(5):
            c.goto(base + "/", wait=0.8)
            if c.wait_for("typeof TubeDesk !== 'undefined' && typeof TubeStudent !== 'undefined' && (document.querySelector('#main')||{innerHTML:''}).innerHTML.length > 0", 8):
                return True
        return False

    def login(c, lid):
        if not open_app(c):
            return False
        # はじめての端末には「ようこそ」が出る。検査は入口（ログイン）から入るので、見たことにしておく。
        c.eval("localStorage.clear(); sessionStorage.clear(); localStorage.setItem('tube.welcomed.v1', '1');")
        if not open_app(c) or not c.wait_for("!!document.querySelector('#lId')", 15):
            return False
        a = acc[lid]
        c.eval("document.querySelector('#lId').value=%s; document.querySelector('#lPw').value=%s; document.querySelector('#lGo').click();"
               % (json.dumps(a["id"]), json.dumps(a["password"])))
        ok = c.wait_for("!document.querySelector('#lId') && !document.querySelector('#welcome:not(.out)')", 40)
        time.sleep(1.2)
        return ok

    def tab(c, v, wait=2.5):
        c.eval("(function(){ var b=document.querySelector('[data-tab=%s]'); if(b) b.click(); })()" % json.dumps(v))
        time.sleep(wait)

    teachers = [a for a in accounts if a.get("role") == "teacher"][:1]
    students = [a for a in accounts if a.get("role") == "student"][:2]
    for a in teachers:
        with Chrome(width=1440, height=900) as c:
            if not login(c, a["id"]):
                check("%s：画面から入れる" % a["id"], False)
                continue
            tab(c, "roster", 3.0)
            n_ui = c.eval("document.querySelectorAll('.ik-card').length")
            n_api = metrics.get("%s.overview.courses" % a["id"])
            check("%s：成績の札の数（画面 %s）＝ API（%s）" % (a["id"], n_ui, n_api), n_ui == n_api)
            tab(c, "progress", 3.0)
            n_rows = c.eval("document.querySelectorAll('.use-grp .use-row').length")
            check("%s：導入の段階の行がある（%s）" % (a["id"], n_rows), (n_rows or 0) >= 1)
            # はしご：押された段（aria-checked）＝ API の段階。まとめの行は、段がそろうときだけその段、そろわないときは段なしで「まちまち」。
            lads = c.eval("[].slice.call(document.querySelectorAll('.use-row')).map(function(r){"
                          " var bs=[].slice.call(r.querySelectorAll('.use-lad[role=radiogroup] [role=radio]')); if(!bs.length) return null;"
                          " var on=bs.filter(function(b){return b.getAttribute('aria-checked')==='true'}), w=r.querySelector('.use-word');"
                          " return {keys:bs[0].dataset.use.split('|')[0].split(','), on:on.map(function(b){return +b.dataset.use.split('|')[1]}),"
                          " title:on.map(function(b){return b.title}), word:w?w.textContent:''};}).filter(Boolean)") or []
            use = USE.get(a["id"]) or {}
            bad = []
            for r in lads:
                lv = sorted({use.get(k) for k in r["keys"]}, key=str)
                want = lv if len(lv) == 1 and lv[0] is not None else []
                word = r["title"][0] if r["on"] else "まちまち"
                if r["on"] != want or r["word"] != word:
                    bad.append({"keys": r["keys"], "画面": r["on"], "API": [use.get(k) for k in r["keys"]], "言葉": r["word"]})
            check("%s：はしごの段 ＝ API の段階（%s 行）" % (a["id"], len(lads)), bool(lads) and not bad, bad,
                  "押した段が保存と違えば、講師は自分のコースで何が起きるかを見誤る")
            own = {r["keys"][0] for r in lads if len(r["keys"]) == 1}
            check("%s：担当コースそれぞれに自分のはしご（%s / %s）" % (a["id"], len(own & set(use)), len(use)),
                  set(use) <= own, sorted(set(use) - own))
            errs = c.eval("(window.__errs||[]).length")
            check("%s：JS のエラー 0" % a["id"], not errs, errs)
    for a in students:
        with Chrome(width=390, height=844, mobile=True) as c:
            if not login(c, a["id"]):
                check("%s：画面から入れる" % a["id"], False)
                continue
            tab(c, "daily", 2.0)
            n_ui = c.eval("document.querySelectorAll('.dcard').length")
            n_api = metrics.get("%s.quizSubjects" % a["id"])
            check("%s：毎日テストの教科（画面 %s）≤ 段階 4 の教科（%s）" % (a["id"], n_ui, n_api), (n_ui or 0) <= (n_api or 0),
                  why="段階 4 未満の教科に毎日テストを出さない")
            tab(c, "homework", 2.0)
            paper_btn = c.eval("[].slice.call(document.querySelectorAll('.hw-state')).map(function(x){return x.textContent})")
            check("%s：宿題の状態文が読める" % a["id"], isinstance(paper_btn, list), paper_btn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8932")
    ap.add_argument("--accounts", default=os.path.join(HERE, "..", "..", "demo-accounts.json"))
    ap.add_argument("--ledger", default=os.path.join(HERE, "ledger.json"))
    ap.add_argument("--ui", action="store_true")
    ap.add_argument("--strict", action="store_true", help="△ も失敗にする")
    a = ap.parse_args()
    api = Api(a.base)
    try:
        urllib.request.urlopen(urllib.request.Request(a.base + "/api/health", headers={"User-Agent": UA}), timeout=10)
    except Exception as e:
        print("サーバが応えません: %s" % e)
        sys.exit(2)
    accounts = json.load(open(a.accounts, encoding="utf-8"))
    # 入口の一覧の ID だけの行（「ためしに見る」は ID で入る。本物の講師・ためし用の生徒）は、合言葉で入るこの検査からは外す。
    accounts = [x for x in accounts if isinstance(x, dict) and x.get("password")]
    metrics = {}
    for acc in accounts:
        if acc.get("role") == "teacher":
            teacher_checks(api, acc, metrics)
    for acc in accounts:
        if acc.get("role") == "student":
            student_checks(api, acc, metrics)
    gate_checks(api, accounts)
    if a.ui:
        ui_checks(a.base, accounts, metrics)
    ledger_checks(a.ledger, metrics)
    print()
    if ng_n or (a.strict and warn_n):
        print("× %d件 失敗 / △ %d / OK %d" % (ng_n, warn_n, ok_n))
        sys.exit(1)
    print("すべて通った。（%d件、△ %d）" % (ok_n, warn_n))


if __name__ == "__main__":
    main()
