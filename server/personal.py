#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生徒ひとりずつの宿題 ―― 「決まり」で持つ。

なぜ「決まり」で持つか
----------------------
講師の頼みはこうだった。

    小4αの既定は「教科書の基本問題＋演習問題集の基本問題＋計算テキスト」。
    この生徒だけ、計算テキストの量を減らす／なしにする。あるいは代わりに
    教科書の練習問題も出す。**次に変えるまで、ずっとそのまま**にしたい。

1回ずつの宿題を手で直させると、毎週同じ直しを繰り返すことになり、紙より遅い。
そこで「この生徒には、この教材をこう変える」という決まりを1度だけ書き、
授業日に宿題を出すとき（tube_server.publish_courses）に既定の宿題へ当てはめる。

**出したあとの宿題は変えない。** 決まりは、まだ出していない回にだけ効く。
出した宿題を書き換えると、生徒がもう撮った写真や付いた評価と食い違う。

置き場所
--------
    <ROOT>/schools/<校舎>/personal.json
    {"rules": {"<コースの鍵>": {"<sid>": [決まり, …]}}}

決まり1つ
---------
    {"id": "r1a2b3c4",
     "kind": "drop" | "scale" | "swap" | "add",
     "match": {"source": "keisan-yos", "text": "計算テキスト"},
         drop/scale/swap が対象を探す手がかり。source（教材ID）と
         text（範囲を外した呼び名の頭）の**両方があれば両方**で合わせる
     "factor": 0.5,                   scale の倍率（0.1〜0.9）
     "with": {"text": "予習シリーズ 練習問題",
              "copy": {"source": "yos-e4-math", "n": null},
              "app": {"unit": "単位量あたり", "count": 10}},
         swap/add で出すもの。copy があれば、その教材の範囲（ページ）を写す
         （n は第何回の範囲か。null は同じ回）。app はアプリの問題（単元から集める）
     "from": 8, "until": null,        第8回から。until が null なら次に変えるまでずっと
     "note": "", "by": "<講師のsid>", "at": 秒,
     "origin": {"kind": "redo", "n": 7}}   提案から作ったとき、その種類と単元

    drop   … 対象の宿題を、この生徒には出さない
    scale  … 対象の範囲を減らす（43-49 を 0.5 倍 → 43-46）
    swap   … 対象の代わりに with を出す（対象がその回に無ければ何もしない）
    add    … with を足す
"""

import math
import re
import secrets
import threading
import time

import paths

KINDS = ("drop", "scale", "swap", "add")
KIND_WORD = {"drop": "出さない", "scale": "減らす", "swap": "置き換える", "add": "足す"}
MAX_RULES = 12              # 1人・1コースあたり。決まりが増えすぎると誰も読めない
RID = re.compile(r"^r[0-9a-f]{8}$")
SAFE_SID = re.compile(r"^[A-Za-z0-9]{4,32}$")

# 範囲（43-49、p.30-33、43–49）。区切りの字はいろいろ来る。
RANGE = re.compile(r"(\d+)\s*([-‐－–〜~ー])\s*(\d+)")

_LOCK = paths.GUARD          # 置き場にひとつだけの鍵（スレッドにもプロセスにも効く。paths.Guard）


# ------------------------------------------------------------------
# 保管
# ------------------------------------------------------------------
def _file(school):
    return paths.school_file(school, "personal.json")


def load(school):
    d = paths.load(_file(school), {}) or {}
    if not isinstance(d.get("rules"), dict):
        d["rules"] = {}
    return d


def save(school, d):
    paths.save(_file(school), d)


def rules_of(school, key, sid=None, data=None):
    """コースの決まり。sid を渡せばその生徒の分（list）、無ければ {sid: [...]}。"""
    d = data if data is not None else load(school)
    per = (d.get("rules") or {}).get(key) or {}
    if sid is not None:
        return [dict(r) for r in (per.get(sid) or [])]
    return {s: [dict(r) for r in (v or [])] for s, v in per.items()}


def active(rule, n):
    """第 n 回に効くか。生徒が「質問する」を押した決まりは、先生が答えるまで効かない（変更は一旦止まる）。"""
    if (rule.get("ack") or {}).get("state") == "asked":
        return False
    try:
        n = int(n)
        lo = int(rule.get("from") or 0)
    except (TypeError, ValueError):
        return False
    hi = rule.get("until")
    if hi is None:
        return n >= lo
    try:
        return lo <= n <= int(hi)
    except (TypeError, ValueError):
        return False


# ------------------------------------------------------------------
# 宿題の文を読む・直す
# ------------------------------------------------------------------
def _norm(t):
    return re.sub(r"[\s　]+", "", str(t or ""))


def base_text(title):
    """「計算テキスト 43-49」→「計算テキスト」、「予習シリーズ 基本問題 p.22-23」→「予習シリーズ 基本問題」。

    範囲とページの記号を外した、教材と種類の呼び名。決まりはこれで宿題を探す。"""
    t = RANGE.sub("", str(title or ""))
    t = re.sub(r"[（(][^）)]*[)）]\s*$", "", t.strip())     # 末尾の（7もん）など
    t = re.sub(r"\s*[pPｐＰ]\s*[.．]?\s*$", "", t.strip())  # 残った p.
    return t.strip()


def matches(m, item):
    """決まりの match が、この宿題を指しているか。"""
    m = m or {}
    src = str(m.get("source") or "")
    txt = _norm(m.get("text"))
    if src and (item.get("source") or "") != src:
        return False
    if txt and not _norm(base_text(item.get("title"))).startswith(txt):
        return False
    return bool(src or txt)


def is_page(title):
    """範囲がページ（p.30-33）か、番号（43-49）か。"""
    return bool(re.search(r"[pPｐＰ]\s*[.．]?\s*\d+\s*[-‐－–〜~ー]\s*\d+", str(title or "")))


def _replace_range(title, lo, hi, nlo, nhi):
    """文の中の範囲を差し替える。同じ数の範囲があればそれを、無ければ最後の範囲を。"""
    t = str(title or "")
    found = list(RANGE.finditer(t))
    if not found:
        return (t + " %d-%d" % (nlo, nhi)).strip()
    pick = [x for x in found if int(x.group(1)) == lo and int(x.group(3)) == hi]
    x = (pick or found)[-1]
    return t[:x.start()] + "%d%s%d" % (nlo, x.group(2), nhi) + t[x.end():]


def scaled(item, factor):
    """範囲を倍率で減らした1件。範囲が無い宿題は、文に割合を添えるだけにする。"""
    try:
        f = float(factor)
    except (TypeError, ValueError):
        f = 0.5
    f = min(0.9, max(0.1, f))
    out = dict(item)
    lo, hi = int(item.get("from") or 0), int(item.get("to") or 0)
    if lo >= 1 and hi >= lo:
        k = max(1, int(math.ceil((hi - lo + 1) * f - 1e-9)))
        nhi = lo + k - 1
        out.update({"from": lo, "to": nhi,
                    "title": _replace_range(item.get("title"), lo, hi, lo, nhi)})
    else:
        word = "半分" if abs(f - 0.5) < 1e-6 else "%d割" % int(round(f * 10))
        out["title"] = "%s（%s）" % (str(item.get("title") or "").strip(), word)
    return out


def made_item(w, lookup, n, unit_name=None):
    """with から出す1件（{title, source, from, to} か {title, app}）。作れなければ None。

    lookup(source, n) は、第 n 回にその教材が出るときの (from, to, title) か None。
    unit_name は回の名前（「第4回 相似の利用」）。範囲を写す先が無いときに文へ添える ――
    「新中学問題集 発展問題」だけでは、生徒にどの回の分か伝わらない。"""
    w = w or {}
    text = str(w.get("text") or "").strip()[:60]
    app = w.get("app") or None
    if app and app.get("unit"):
        cnt = int(app.get("count") or 10)
        cnt = max(3, min(30, cnt))
        unit = str(app["unit"])[:40]
        return {"title": text or ("%s の復習 %d問" % (unit, cnt)),
                "app": {"unit": unit, "count": cnt}}
    if not text:
        return None
    cp = w.get("copy") or {}
    src = str(w.get("source") or "")[:40]
    lo = hi = 0
    title = text
    if cp.get("source"):
        got = lookup(str(cp["source"]), cp.get("n") if cp.get("n") is not None else n)
        if got:
            lo, hi, ctitle = got
            src = src or str(cp["source"])
            if lo and hi:
                title = "%s %s%d-%d" % (text, "p." if is_page(ctitle) else "", lo, hi)
        if not (lo and hi) and unit_name and not RANGE.search(text):
            title = "%s（%s）" % (text, str(unit_name)[:30])
    return {"title": title, "source": src, "from": lo, "to": hi}


# ------------------------------------------------------------------
# 当てはめる（発行のとき）
# ------------------------------------------------------------------
def apply(recs, rules_by_sid, n, lookup, make, unit_name=None):
    """既定の宿題（recs）に、生徒ごとの決まりを当てはめる。

    recs          この回に出す既定の宿題。students に受け取る生徒が入っている
    rules_by_sid  {sid: [決まり…]}（効かない回の決まりが混ざっていてよい）
    n             第何回か
    lookup        (source, n) → (from, to, title) か None
    make          (item, sid, rule_ids) → 宿題1件（dict）か None
    unit_name     回の名前。範囲を写せない「足す」に添える（made_item）

    戻り値は「生徒を抜いた既定」＋「生徒ひとりずつの宿題」。
    **受け取る生徒が0人になった既定の宿題は落とす**（students が空の宿題は、
    読むときにクラス全員に化けるため ―― tube_server.students_for）。
    recs そのものは書き換えない。
    """
    out = [dict(r, students=list(r.get("students") or [])) for r in recs if r]
    made = []
    for sid in sorted(rules_by_sid or {}):
        rules = [r for r in (rules_by_sid.get(sid) or []) if active(r, n)]
        if not rules:
            continue
        mine = [r for r in out if sid in r["students"]]
        if not mine:
            continue                        # この回の宿題を受け取らない生徒
        items = [{"rec": r, "title": r.get("title"), "source": r.get("source"),
                  "from": r.get("from"), "to": r.get("to"), "extra": r.get("extra"),
                  "gone": False, "changed": False, "rules": []} for r in mine]
        added = []
        rules.sort(key=lambda x: (int(x.get("from") or 0), int(x.get("at") or 0)))
        for rule in rules:
            kind = rule.get("kind")
            if kind == "add":
                it = made_item(rule.get("with"), lookup, n, unit_name)
                if it:
                    it["rules"] = [rule.get("id")]
                    added.append(it)
                continue
            hits = [it for it in items if not it["gone"] and matches(rule.get("match"), it)]
            for it in hits:
                it["rules"].append(rule.get("id"))
                if kind == "drop" or kind == "swap":
                    it["gone"] = True
                elif kind == "scale":
                    it.update({k: v for k, v in scaled(it, rule.get("factor")).items()
                               if k in ("title", "from", "to")})
                    it["changed"] = True
            if kind == "swap" and hits:
                it = made_item(rule.get("with"), lookup, n, unit_name)
                if it:
                    it["rules"] = [rule.get("id")]
                    added.append(it)
        for it in items:
            if it["gone"] or it["changed"]:
                it["rec"]["students"].remove(sid)
            if it["changed"] and not it["gone"]:
                rec = make(it, sid, it["rules"])
                if rec:
                    made.append(rec)
        for it in added:
            rec = make(it, sid, it["rules"])
            if rec:
                made.append(rec)
    return [r for r in out if r["students"]] + made


def student_items(recs, sid):
    """当てはめたあとの、その生徒の宿題の文（画面の「次の回のこの生徒の宿題」）。"""
    return [r for r in recs if sid in (r.get("students") or [])]


# ------------------------------------------------------------------
# 決まりを書く・止める
# ------------------------------------------------------------------
def clean_rule(d, next_n, by, now=None):
    """画面から来た決まりを確かめて、保存してよい形にする。"""
    if not isinstance(d, dict):
        raise ValueError("形式が違います")
    kind = str(d.get("kind") or "")
    if kind not in KINDS:
        raise ValueError("変え方（出さない・減らす・置き換える・足す）を選んでください")
    rid = str(d.get("id") or "")
    out = {"id": rid if RID.match(rid) else "r" + secrets.token_hex(4), "kind": kind}

    if kind in ("drop", "scale", "swap"):
        m = d.get("match") or {}
        src = str(m.get("source") or "").strip()[:40]
        txt = str(m.get("text") or "").strip()[:40]
        if not (src or txt):
            raise ValueError("どの宿題を変えるかを選んでください")
        out["match"] = {"source": src, "text": txt}
    if kind == "scale":
        try:
            f = float(d.get("factor"))
        except (TypeError, ValueError):
            raise ValueError("減らす割合を選んでください")
        if not 0.1 <= f <= 0.9:
            raise ValueError("減らす割合は1割〜9割にしてください")
        out["factor"] = round(f, 2)
    if kind in ("swap", "add"):
        w = d.get("with") or {}
        text = str(w.get("text") or "").strip()[:60]
        wo = {"text": text}
        cp = w.get("copy") or {}
        if cp.get("source"):
            cn = cp.get("n")
            try:
                cn = None if cn in (None, "") else int(cn)
            except (TypeError, ValueError):
                cn = None
            wo["copy"] = {"source": str(cp["source"])[:40], "n": cn}
        app = w.get("app") or {}
        if app.get("unit"):
            try:
                cnt = int(app.get("count") or 10)
            except (TypeError, ValueError):
                cnt = 10
            wo["app"] = {"unit": str(app["unit"]).strip()[:40], "count": max(3, min(30, cnt))}
        if not text and not wo.get("app"):
            raise ValueError("代わりに出すもの（足すもの）を書いてください")
        out["with"] = wo

    try:
        next_n = int(next_n)
    except (TypeError, ValueError):
        next_n = 1
    try:
        fr = int(d.get("from") or next_n)
    except (TypeError, ValueError):
        fr = next_n
    # **出した回には効かせない。** 過去の回を指しても、次の回からにする。
    fr = max(fr, next_n)
    until = d.get("until")
    if until in (None, "", "keep"):
        until = None
    elif until == "once":
        until = fr
    else:
        try:
            until = int(until)
        except (TypeError, ValueError):
            raise ValueError("期間が読めません")
        if until < fr:
            raise ValueError("期間の終わりが始まりより前です")
    origin = d.get("origin") or {}
    out.update({
        "from": fr, "until": until,
        "note": str(d.get("note") or "").strip()[:120],
        # 生徒へのひとこと（「先生から」に出る）。書いたら「わかった／質問する」の返事を待つ札（ack）ができる
        "msg": str(d.get("msg") or "").strip()[:MSG_MAX],
        "by": by, "at": int(now or time.time()),
    })
    if out["msg"]:
        old = d.get("ack") if isinstance(d.get("ack"), dict) else None
        out["ack"] = dict(old) if old and old.get("state") else {"state": "open", "at": out.get("at") or int(now or time.time())}
    if origin.get("kind"):
        try:
            on = int(origin.get("n")) if origin.get("n") is not None else None
        except (TypeError, ValueError):
            on = None
        out["origin"] = {"kind": str(origin["kind"])[:16], "n": on}
        # プリセットから作った決まりは、その id と名前を持つ（「誰に何を出しているか」の束ね）
        if origin.get("preset"):
            out["origin"]["preset"] = str(origin["preset"])[:12]
            out["origin"]["name"] = str(origin.get("name") or "")[:30]
    return out


def put_rule(school, key, sid, d, by, next_n, now=None):
    """決まりを1つ保存する（同じ ID なら差し替え）。保存した決まりを返す。"""
    if not SAFE_SID.match(str(sid or "")):
        raise ValueError("生徒が分かりません")
    rule = clean_rule(d, next_n, by, now)
    with _LOCK:
        data = load(school)
        per = data["rules"].setdefault(key, {})
        lst = [r for r in (per.get(sid) or []) if r.get("id") != rule["id"]]
        live = [r for r in lst if r.get("until") is None or int(r.get("until")) >= int(next_n)]
        if len(live) >= MAX_RULES:
            raise ValueError("この生徒の決まりが多すぎます（%d件まで）。使っていないものを止めてください"
                             % MAX_RULES)
        lst.append(rule)
        per[sid] = lst
        save(school, data)
    return rule


def stop_rule(school, key, sid, rid, next_n):
    """決まりを止める。まだ1回も効いていなければ消し、効いたことがあれば記録を残して終わらせる。"""
    with _LOCK:
        data = load(school)
        per = (data.get("rules") or {}).get(key) or {}
        lst = per.get(sid) or []
        hit = [r for r in lst if r.get("id") == rid]
        if not hit:
            return False
        r = hit[0]
        last = int(next_n) - 1
        if int(r.get("from") or 0) > last:
            lst = [x for x in lst if x.get("id") != rid]
        else:
            r["until"] = last if r.get("until") is None else min(int(r["until"]), last)
            r["stoppedAt"] = int(time.time())
        if lst:
            per[sid] = lst
        else:
            per.pop(sid, None)
        if not per:
            data["rules"].pop(key, None)
        save(school, data)
    return True


def drop_student(school, sid):
    """退塾した生徒の決まりを消す（進捗の記録を消すときに一緒に呼ぶ）。"""
    with _LOCK:
        data = load(school)
        changed = False
        for key in list(data["rules"].keys()):
            if sid in data["rules"][key]:
                data["rules"][key].pop(sid, None)
                changed = True
            if not data["rules"][key]:
                data["rules"].pop(key, None)
        if changed:
            save(school, data)
    return changed


# ------------------------------------------------------------------
# 生徒へのひとことと、その返事（わかった／質問する）
#
#   ack = {"state": "open" | "asked" | "answered" | "ok",
#          "at": 出した時刻, "okAt": わかったの時刻, "auto": 1週間で自動, "askedAt", "question", "msgId",
#          "answer", "answeredAt", "by"}
#   open → ok        生徒が「わかった」。または ACK_DAYS 過ぎたら自動で ok（auto）
#   open → asked     生徒が「質問する」。決まりは先生が答えるまで効かない（active）
#   asked → answered 先生が受信箱で返事した（メッセージ msgId への返事）。決まりは再び効く
#   answered → ok    生徒が「わかった」（または ACK_DAYS）
# ------------------------------------------------------------------
MSG_MAX = 200
ACK_DAYS = 7


def _find(data, key, sid, rid):
    for r in ((data.get("rules") or {}).get(key) or {}).get(sid) or []:
        if r.get("id") == rid:
            return r
    return None


def ack_rule(school, key, sid, rid, action, text="", now=None, msg_id=None):
    """生徒の返事。action は 'ok' か 'ask'。決まりを返す（無ければ None）。"""
    now = int(now or time.time())
    with _LOCK:
        data = load(school)
        r = _find(data, key, sid, rid)
        if not r or not r.get("msg"):
            return None
        ack = r.setdefault("ack", {"state": "open", "at": r.get("at") or now})
        if action == "ok":
            ack.update({"state": "ok", "okAt": now, "auto": False})
        elif action == "ask":
            if ack.get("state") not in ("open", "answered"):
                return None
            ack.update({"state": "asked", "askedAt": now, "question": str(text or "").strip()[:400], "msgId": msg_id})
        else:
            return None
        save(school, data)
        return dict(r)


def answer_by_msg(school, mid, text, by, now=None):
    """先生が受信箱で返事した。その質問（msgId）の決まりを answered にして、再び効くようにする。"""
    if not mid:
        return None
    now = int(now or time.time())
    with _LOCK:
        data = load(school)
        for key, per in (data.get("rules") or {}).items():
            for sid, lst in per.items():
                for r in lst:
                    ack = r.get("ack") or {}
                    if ack.get("state") == "asked" and ack.get("msgId") == mid:
                        ack.update({"state": "answered", "answer": str(text or "").strip()[:600],
                                    "answeredAt": now, "by": str(by or "")[:40]})
                        save(school, data)
                        return dict(r)
    return None


def expire_acks(school, now=None):
    """出してから ACK_DAYS 過ぎた open / answered は、自動で「わかった」扱いにする。変えた数を返す。"""
    now = int(now or time.time())
    n = 0
    with _LOCK:
        data = load(school)
        for key, per in (data.get("rules") or {}).items():
            for sid, lst in per.items():
                for r in lst:
                    ack = r.get("ack") or {}
                    if ack.get("state") in ("open", "answered"):
                        base = ack.get("answeredAt") if ack.get("state") == "answered" else ack.get("at")
                        if base and now - int(base) >= ACK_DAYS * 86400:
                            ack.update({"state": "ok", "okAt": now, "auto": True})
                            n += 1
        if n:
            save(school, data)
    return n


def notices_of(school, sid, now=None):
    """生徒に見せるお知らせ：ひとこと付きで、まだ「わかった」になっていない決まり。[(key, rule), …] 新しい順。"""
    expire_acks(school, now)
    out = []
    data = load(school)
    for key, per in (data.get("rules") or {}).items():
        for r in per.get(sid) or []:
            ack = r.get("ack") or {}
            if r.get("msg") and ack.get("state") in ("open", "asked", "answered"):
                out.append((key, dict(r)))
    out.sort(key=lambda kr: -(kr[1].get("at") or 0))
    return out


def acks_recent(school, keys, now=None, days=ACK_DAYS):
    """講師に知らせる分：担当コースで、最近「わかった」になった決まりと、質問が来て止まっている決まり。"""
    expire_acks(school, now)
    now = int(now or time.time())
    out = []
    data = load(school)
    for key, per in (data.get("rules") or {}).items():
        if keys is not None and key not in keys:
            continue
        for sid, lst in per.items():
            for r in lst:
                ack = r.get("ack") or {}
                if not r.get("msg"):
                    continue
                if ack.get("state") == "ok" and now - int(ack.get("okAt") or 0) <= days * 86400:
                    out.append((key, sid, dict(r)))
                elif ack.get("state") == "asked":
                    out.append((key, sid, dict(r)))
    out.sort(key=lambda t: -((t[2].get("ack") or {}).get("okAt") or (t[2].get("ack") or {}).get("askedAt") or 0))
    return out


def describe(rule, names=None):
    """決まりを1行の言葉にする（講師の画面）。"""
    k = rule.get("kind")
    m = rule.get("match") or {}
    target = m.get("text") or m.get("source") or ""
    w = rule.get("with") or {}
    what = w.get("text") or ((w.get("app") or {}).get("unit", "") + " の復習")
    if k == "drop":
        s = "%s を出さない" % target
    elif k == "scale":
        s = "%s を%d割に減らす" % (target, int(round(float(rule.get("factor") or 0.5) * 10)))
    elif k == "swap":
        s = "%s の代わりに %s" % (target, what)
    else:
        s = "%s を足す" % what
    fr, un = rule.get("from"), rule.get("until")
    # 回の名前は names（回の番号 → 教材の呼び名。lessons.unit_name）から。無ければ「第n回」。
    def nm(k):
        try:
            v = (names or {}).get(int(k))
        except (TypeError, ValueError):
            v = None
        return v or ("第%s回" % k)
    if un is None:
        span = "%sから、次に変えるまで" % nm(fr)
    elif un == fr:
        span = "%sだけ" % nm(fr)
    elif names:
        span = "%s〜%s" % (nm(fr), nm(un))
    else:
        span = "第%s〜%s回" % (fr, un)
    return s, span
