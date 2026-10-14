#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""授業計画 ―― このシステムのいちばん中心にある考え方。

なぜこの形にしたか
------------------
講師が毎週やっている仕事は「今週の宿題を決めて伝える」である。
アプリがその作業を**毎週もう一度やらせる**なら、紙のほうが速い。
それでは絶対に使われない。

そこで、順序を逆にする。

    学期のはじめに、コマ単位の予定を数ヶ月分いちど入れる
      → 授業日が来たら、その回の宿題が**自動で**生徒に出る
      → 講師の毎週の作業は ゼロ

現実には授業は遅れる。だから「ずらす」を1タップにする。

    第7回で1コマ遅れた → shift(key, 7, 1)
      → 第7回以降の予定日が全部1週ずれる
      → まだ出していない宿題の予定日も一緒にずれる

これが無いと、遅れた瞬間に予定表が嘘になり、講師は使うのをやめる。
**遅れることを前提に作る。** 遅れないことを前提にした計画表は必ず捨てられる。

保管の形
--------
    schools/<校舎>/lessons.json
    {
      "plans": {
        "j1:math": {
          "teacher": "<講師のsid>",
          "classId": "j1a",
          "weekday": 3,                     授業の曜日（0=日 … 6=土）
          "dueDays": 7,                     宿題の期限（授業日から何日後）
          "lessons": [
            {"n": 1, "date": "2026-04-08",
             "topic": "正負の数",
             "hw": {"text": "トレーニング1-3と基本問題",
                    "source": "keisan", "from": 1, "to": 40},
             "published": "a1b2c3d4",        出した宿題のID（出すまでは無い）
             "doneAt": 1712500000},          授業を実施した時刻
            ...
          ]
        }
      }
    }

hw.text が要点である。「トレーニング1-3と基本問題」のように、
**講師がふだん黒板に書いている言葉のまま**入れられるようにする。
番号の範囲（source/from/to）は、付けられるときだけ付ける。
付いていれば進捗を追えるが、無くても宿題としては成立する。
ここを「教材を登録しないと出せない」作りにすると、
現実の宿題の大半がアプリの外に残る。
"""

import os
import re
import sys
import time
import datetime as _dt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                    # noqa: E402

DAY = 86400
SAFE_KEY = None          # tube_server の PLAN_KEY を使う（重複定義しない）


def _file(school):
    return paths.school_file(school, "lessons.json")


def load(school):
    return paths.load(_file(school), {}) or {}


def save(school, data):
    paths.save(_file(school), data)


def plans(school):
    return (load(school).get("plans") or {})


def plan(school, key):
    return plans(school).get(key) or {}


# ------------------------------------------------------------------
# 予定を作る
# ------------------------------------------------------------------
def build_dates(start, weekday, count, skip=None):
    """授業日を並べる。start 以降の、指定曜日の日付を count 個。

    weekday は 0=日 … 6=土（画面の選択肢と同じ）。
    skip には長期休暇の日付（YYYY-MM-DD）を入れる。その週は飛ばす。

    **日付は日付のまま数える。** 前は時刻に7日ぶんの秒を足していて、
    夏時間が終わる10月末を越えると23時になり、前の日の日付に落ちていた。
    また曜日を time の数え方（0=月）で比べていたので、画面で「月」を
    選ぶと火曜に入っていた。
    """
    skip = set(skip or [])
    try:
        x = _dt.date(*map(int, str(start).split("-")))
    except (TypeError, ValueError):
        return []
    while x.isoweekday() % 7 != int(weekday) % 7:
        x += _dt.timedelta(days=1)
    out = []
    while len(out) < count:
        d = x.isoformat()
        if d not in skip:
            out.append(d)
        x += _dt.timedelta(days=7)
    return out


def _add_days(d, n):
    return (_dt.date(*map(int, d.split("-"))) + _dt.timedelta(days=n)).isoformat()


# ------------------------------------------------------------------
# 5週の周期
# ------------------------------------------------------------------
# 早稲田アカデミーは5週ごとに組み分けテストがある。授業もそれに
# 合わせて回る ―― **4回が新しい内容、5回目が総復習**。
#
# この規則を1か所に置く。画面にも、宿題の自動発行にも、
# 総復習テスト対策にも同じ数字が要るので、散らばらせない。
CYCLE = 5                      # 1周は5回
REVIEW_AT = 0                  # 周のうち、この余りの回が総復習（5, 10, 15…）


def is_review(n):
    """その回は総復習か。第5回・第10回・… が総復習。"""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return False
    return n > 0 and n % CYCLE == REVIEW_AT


def cycle_of(n):
    """その回は第何周めか（1から数える）。"""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return 0
    return (max(1, n) - 1) // CYCLE + 1


def block_of(n):
    """その回が属する周の、最初と最後の回。第7回なら (6, 10)。"""
    c = cycle_of(n)
    return ((c - 1) * CYCLE + 1, c * CYCLE)


def unit_label(l):
    """教材での呼び名。シラバスから作った回は label（空のこともある）、それ以外は「第n回」。"""
    l = l or {}
    if l.get("label") is not None:
        return str(l.get("label") or "")
    try:
        return "第%d回" % int(l.get("n") or 0)
    except (TypeError, ValueError):
        return ""


def unit_text(l):
    """呼び名と単元名（「第3回 相似と比」「5章-3 直角三角形」、呼び名の無い教材は「平面図形」）。"""
    return " ".join(x for x in (unit_label(l), str((l or {}).get("topic") or "")) if x)


def unit_name(l):
    """短い名前。呼び名があれば呼び名、無ければ単元名。"""
    return unit_label(l) or str((l or {}).get("topic") or "")


def unit_note(l):
    """出す宿題に添える一文（「第3回（相似と比）の宿題です。」）。"""
    lb, t = unit_label(l), str((l or {}).get("topic") or "")
    return "%sの宿題です。" % (("%s（%s）" % (lb, t)) if (lb and t) else (lb or t or "この回"))


def set_plan(school, key, teacher_sid, class_id, weekday, start,
             rows, due_days=7, skip=None):
    """コマ単位の予定をまとめて入れる。

    rows は [{"topic": "...", "hw": {...}}, ...] の並び。
    日付は自動で振る ―― 講師に日付を1つずつ入力させない。
    ここが手間の分かれ目になる。

      コース（teachers の欄がある計画）… 授業のある曜日（courses.dates）
      旧来の計画                         … start と weekday

    **総復習** の印も付ける。組み分けテストが5週ごとにあるので、
    授業もその周期で回る。コースは週で数える（週2回のコースでも5週に1回）。
    旧来の計画は5回ごと。印は画面と、総復習テスト対策の範囲決めに使う。

    **コースの定義（講師・時間割・受ける生徒）はここで書き換えない。**
    画面から届くのは予定だけ。定義は教室長が CSV で入れる。
    """
    with paths_lock():
        data = load(school)
        p = (data.setdefault("plans", {})).setdefault(key, {})
        course = isinstance(p.get("teachers"), list)
        # **入れ直しで日付を振り直さない。** 開始日（旧来は曜日も）が同じなら、
        # ある回の日付はそのまま使う ―― 「ずらす」で動かした分が戻らないように。
        # 増えた回だけ、最後の回の次の授業日から振る。開始日を変えたときは
        # 振り直すが、出した回までの日付は動かさない。
        # 休みの日（skip）は、送られてこなければ前のものを使う。
        skip = skip or p.get("skip") or []
        old_ls = sorted((p.get("lessons") or []), key=lambda x: x.get("n") or 0)
        if old_ls and p.get("start") == start and (
                course or int(p.get("weekday", 0) or 0) == weekday):
            keep = [x.get("date") or "" for x in old_ls][:len(rows)]
            last = old_ls[-1].get("date") or ""
        else:
            upto = max([x.get("n") or 0 for x in old_ls if x.get("published")] or [0])
            keep = [x.get("date") or "" for x in old_ls][:min(upto, len(rows))]
            last = keep[-1] if keep else ""
        more = max(len(rows) - len(keep), 0)
        if course:
            import courses as C                   # 循環 import を避けてここで読む
            view = dict(p, start=start)
            first = max(start, C.step(view, last, 1) or start) if last else start
            dates = keep + C.dates(view, first, more, skip)
        else:
            first = max(start, _add_days(last, 7)) if last else start
            dates = keep + build_dates(first, weekday, more, skip)
        lessons = []
        for i, r in enumerate(rows):
            n = i + 1
            d = dates[i] if i < len(dates) else ""
            row = {
                "n": n,
                "date": d,
                "topic": str(r.get("topic", ""))[:60],
                "hw": _clean_hw(r.get("hw")),
                # 総復習の回。取り込んだ表が別の周期でも、
                # 行そのものに review が入っていればそれを優先する。
                # **行が真偽を持っていればそれに従う**（シラバスが決める。暦では決めない）。
                # 持っていなければ暦で決める（コースは5週ごと、旧来は5回ごと）。
                "review": r["review"] if isinstance(r.get("review"), bool) else (
                    True if r.get("review") else (C.is_review(view, d) if course else is_review(n))),
            }
            # 教材での呼び名（第3回／5章-3／例題56-57）と、シラバスの何番目の単元か。
            # シラバスから作った行だけが持つ。呼び名の無い教材もあるので、空でも鍵は置く。
            if "label" in r:
                row["label"] = str(r.get("label") or "").strip()[:24]
            if isinstance(r.get("unit"), int) and not isinstance(r.get("unit"), bool):
                row["unit"] = r["unit"]
            # 上乗せ（上位）の分。{"top": 宿題}。無い回には鍵を置かない。
            ex_hw = _clean_extra(r.get("extraHw"))
            if ex_hw:
                row["extraHw"] = ex_hw
            lessons.append(row)
        # 既に出した宿題の記録は残す。予定を入れ直しても、
        # 出したものが「出していない」に戻ってはいけない。
        old = {l.get("n"): l for l in (p.get("lessons") or [])}
        for l in lessons:
            o = old.get(l["n"]) or {}
            for k in ("published", "publishedIds", "publishedAt", "doneAt"):
                if o.get(k):
                    l[k] = o[k]
        if course:
            p.update({"start": start,
                      "skip": [str(x)[:10] for x in (skip or [])],
                      "lessons": lessons, "updatedAt": int(time.time())})
        else:
            p.update({"teacher": teacher_sid, "classId": class_id,
                      "weekday": int(weekday) % 7, "dueDays": int(due_days or 7),
                      "start": start, "lessons": lessons,
                      "cycle": CYCLE,
                      "updatedAt": int(time.time())})
        save(school, data)
    return lessons


# 宿題の文から番号の範囲を読み取る。
#
# 講師は「My英単語帳 No.1-50 と テキストp.8-11」のように書く。
# 範囲が読めればアプリで1問ずつ出せるし、読めなければ出せない。
# **読めないものを「アプリで解ける」ことにしてはいけない。**
# 実際、範囲が無いまま出したため、生徒の画面に
# 「NO. 0 の 0 ばんを見て」と表示されていた。
RANGE = re.compile(
    r"(?:no\.?\s*|№\s*|第?)?(\d{1,5})\s*(?:[-〜~ー–—]|から)\s*(\d{1,5})",
    re.I)


def parse_range(text):
    """文から (はじめ, おわり) を読む。読めなければ None。

    ページ番号（p.8-11）は拾わない ―― 冊子の問題番号とは別物で、
    混ぜると「8番から11番」という誤った出題になる。
    """
    if not text:
        return None
    # p.8-11 / p8-11 のような書き方は、番号ではなくページなので外す
    cleaned = re.sub(r"[pP]\s*\.?\s*\d+\s*[-〜~ー–—]\s*\d+", " ", text)
    m = RANGE.search(cleaned)
    if not m:
        return None
    lo, hi = int(m.group(1)), int(m.group(2))
    if lo < 1 or hi < lo or hi - lo > 500:
        return None
    return (lo, hi)


def _clean_item(hw):
    """宿題のブロック1つ。{text, source, from, to} だけを残す。"""
    if not isinstance(hw, dict):
        return {}
    out = {"text": str(hw.get("text", ""))[:120]}
    src = str(hw.get("source", ""))[:40]
    if src:
        out["source"] = src
    for k in ("from", "to"):
        try:
            v = int(hw.get(k))
        except (TypeError, ValueError):
            continue
        if 1 <= v <= 100000:
            out[k] = v
    if out.get("from") and out.get("to") and out["to"] < out["from"]:
        out.pop("to")
    return out


def _clean_hw(hw):
    """1回ぶんの宿題。**ブロックが複数あるときは items に並べる。**

    中2英語なら Sirius21 と Jack21 の2つ。1つにまとめると、教材ごとに
    決まる route（紙かアプリか）と graded（採点するか）が片方で嘘になる。
    前はここが text/source/from/to しか通さず、items は保存で消えていた。
    items の無い旧形式は、そのまま1ブロックとして残す。
    """
    if not isinstance(hw, dict):
        return {}
    if isinstance(hw.get("items"), list):
        items = [_clean_item(x) for x in hw["items"][:8]]
        items = [x for x in items if x.get("text") or x.get("source")]
        return {"items": items} if items else {}
    return _clean_item(hw)


def hw_items(hw):
    """宿題のブロックの並び。items の無い旧形式は、それ自体を1つとみなす。"""
    if not isinstance(hw, dict):
        return []
    if isinstance(hw.get("items"), list):
        return [x for x in hw["items"]
                if isinstance(x, dict) and (x.get("text") or x.get("source"))]
    return [hw] if (hw.get("text") or hw.get("source")) else []


def hw_text(hw):
    """画面に出す1行。ブロックは「｜」でつなぐ。"""
    return "｜".join(x.get("text") or "" for x in hw_items(hw))


# ------------------------------------------------------------------
# ずらす ―― これが無いと計画表は使われない
# ------------------------------------------------------------------
def shift(school, key, from_n, by_lessons=1):
    """第 from_n 回以降を by_lessons コマぶん動かす。正なら後ろ、負なら前。

    **すでに出した宿題はずらさない。** 出したものは生徒の手元にあり、
    期限も伝わっている。あとから動かすと約束を破ることになる。
    ずれるのは、まだ出していない回だけ。

    前へ戻すときは、**出した回より前には行かせない。** 行かせると
    「まだ出していない第8回」が「出した第7回」より前の日付になり、
    予定表の順番と日付の順番が食い違う。

    コースは授業のある曜日の並びで動かす（週2回なら火→木）。
    旧来の計画は1週ずつ。前は7日ずつ動かしていて、週2回のコースで
    「1コマずらす」と1週間飛んでいた。
    """
    with paths_lock():
        data = load(school)
        p = (data.get("plans") or {}).get(key)
        if not p:
            return None
        lessons = p.get("lessons") or []
        course = isinstance(p.get("teachers"), list)
        if course:
            import courses as C

        def moved(d):
            if course:
                return C.step(p, d, by_lessons)
            return _add_days(d, 7 * by_lessons)

        # ずらす対象（まだ出していない、from_n 以降）
        targets = [l for l in lessons
                   if (l.get("n") or 0) >= from_n and not l.get("published")]
        if not targets:
            return {"moved": 0, "reason": "ずらす回がありません（すべて発行済み）"}
        if by_lessons < 0:
            # 出した回のうち、いちばん後ろの日付。ここより前には出さない。
            done = [l.get("date") for l in lessons
                    if l.get("published") and l.get("date")]
            floor = max(done) if done else None
            try:
                first = moved(targets[0]["date"]) if targets[0].get("date") else ""
            except ValueError:
                first = ""
            if floor and first and first <= floor:
                return {"moved": 0,
                        "reason": "これ以上まえには戻せません（出した回に重なります）"}
        for l in targets:
            d = l.get("date")
            if not d:
                continue
            try:
                l["date"] = moved(d)
            except ValueError:
                continue
        p["shiftedAt"] = int(time.time())
        save(school, data)
        return {"moved": len(targets), "by": by_lessons,
                "firstDate": targets[0].get("date")}


def insert_blank(school, key, at_n, topic="（予備）"):
    """第 at_n 回の位置に空のコマを差し込み、以降を1つ後ろへ。

    「今日は復習にあてた」「テストを挟んだ」ときに使う。
    予定表が現実とずれたまま放置されるのを防ぐのが目的。
    """
    with paths_lock():
        data = load(school)
        p = (data.get("plans") or {}).get(key)
        if not p:
            return None
        lessons = p.get("lessons") or []
        out, moved = [], 0
        for l in lessons:
            if (l.get("n") or 0) == at_n:
                out.append({"n": at_n, "date": l.get("date"),
                            "topic": topic, "hw": {}})
            if (l.get("n") or 0) >= at_n:
                if l.get("published"):
                    # 発行済みはそのまま。番号だけ繰り下げる
                    l = dict(l)
                l["n"] = (l.get("n") or 0) + 1
                moved += 1
            out.append(l)
        # 日付を付け直す。差し込んだ回は元の第 at_n 回の日付を使い、後ろの回は
        # **1コマずつ後ろの日付**へ送る（start から振り直すと「ずらす」の分が
        # 戻ってしまう）。いちばん後ろの回だけ、次の授業日を足す。
        # 出した回の日付は動かさない。
        old = [x.get("date") or "" for x in lessons]
        last = old[-1] if old else ""
        if isinstance(p.get("teachers"), list):
            import courses as C
            nxt = (C.step(p, last, 1) or "") if last else ""
        else:
            nxt = _add_days(last, 7) if last else ""
        seq = old + [nxt]
        for l in out:
            n = l.get("n") or 0
            if n > at_n and not l.get("published") and n - 1 < len(seq):
                l["date"] = seq[n - 1]
        p["lessons"] = out
        save(school, data)
        return {"inserted": at_n, "moved": moved}


# ------------------------------------------------------------------
# 自動で宿題を出す
# ------------------------------------------------------------------
# 自動発行の窓。授業日から STALE_DAYS 日を過ぎた回は、もう出さない。
#
# これが無いと、学期の予定をあとから入力したときに
# **過去の回が全部まとめて生徒に出る**（実際に9件どっと出た）。
# 古い回は履歴であって宿題ではない。出したければ講師が手で出す。
STALE_DAYS = 10


def due_to_publish(school, when=None):
    """授業日が来て、まだ宿題を出していない回を拾う。

    講師の操作を待たない。授業日が過ぎたら出す ―― これが
    「毎週の作業ゼロ」の実体である。
    実施していない授業の分が出てしまう場合は、shift で下げる。

    ただし古すぎる回は出さない（STALE_DAYS）。
    """
    when = when or time.time()
    out = []
    for key, p in (plans(school) or {}).items():
        if isinstance(p.get("teachers"), list):
            continue          # コースは tube_server の publish_courses が出す
        for l in (p.get("lessons") or []):
            if l.get("published"):
                continue
            if not hw_items(l.get("hw")):
                continue          # 宿題を予定していない回
            d = l.get("date")
            if not d:
                continue
            try:
                t = time.mktime(time.strptime(d, "%Y-%m-%d"))
            except ValueError:
                continue
            if t <= when and (when - t) <= STALE_DAYS * DAY:
                out.append({"key": key, "plan": p, "lesson": l})
    return out


# 予定の文で、上位の生徒にだけ出す分の印。「比｜p.12-15｜上位:発展 p.20」
TOP_MARK = re.compile(r"^上位\s*[:：]\s*(.*)$")
EXTRA_ID = re.compile(r"^[a-z0-9_-]{1,16}$")


def _one_or_items(items):
    """ブロックが1つならそのまま、2つ以上なら {"items": [...]}（8つまで）。"""
    return {"items": items[:8]} if len(items) > 1 else (items[0] if items else {})


def _clean_extra(extra):
    """回ごとの上乗せ {"top": 宿題}。鍵の形が違うもの・中身の無いものは捨てる。"""
    out = {}
    for k, v in (extra.items() if isinstance(extra, dict) else []):
        hw = _clean_hw(v)
        if EXTRA_ID.match(str(k)) and hw_items(hw):
            out[k] = hw
    return out


def set_extra(school, key, ex_id, name, students):
    """上乗せの宿題を受け取る生徒（指名）を置き換える。計画の extra を返す。

    何を上乗せするかは各回の extraHw（予定の「上位:」）。ここで変わるのは
    **誰が受け取るか**だけで、すでに出した宿題は動かない。
    """
    with paths_lock():
        data = load(school)
        p = (data.get("plans") or {}).get(key)
        if p is None:
            return None
        rest = [e for e in (p.get("extra") or []) if e.get("id") != ex_id]
        p["extra"] = rest + [{"id": ex_id, "name": name, "students": list(students)}]
        save(school, data)
        return p["extra"]


def edit(school, key, n, topic=None, hw_text=None, stop=False):
    """1回ぶんの単元名と宿題の文を書き換える。

    学期ぶんをまとめて入れ直させるのは重い。**1行だけ直したい**という
    のがふだんの用事である（範囲を1ページ増やす、単元名の誤字を直す）。

    すでに出した回も直せる。ただし直るのは**予定の文だけ**で、
    生徒の手元に届いた宿題そのものは動かない。出したものを
    あとから書き換えると、約束が変わったことに誰も気づけない。

    直せたら、その回を返す。無ければ None。
    """
    with paths_lock():
        data = load(school)
        p = (data.get("plans") or {}).get(key)
        if not p:
            return None
        for l in (p.get("lessons") or []):
            if (l.get("n") or 0) != n:
                continue
            if topic is not None:
                l["topic"] = str(topic)[:60]
            if hw_text is not None:
                # **番号は文から読み直す。**
                # 文だけ直して番号が古いままだと、出したときに
                # 別の範囲が生徒に届く。教材の名前は出すときに
                # 文から引き直すので、ここでは持たない。
                # ブロックが複数なら「｜」で区切って書く（Sirius21｜Jack21）。
                # 「上位:」で始まる分は、上乗せ（上位の生徒だけ）に入れる。
                # 書いていなければ上乗せには触らない（1行の直しで消さない）。
                items, tops = [], []
                for t in re.split(r"[｜|\n]", str(hw_text)):
                    t = t.strip()[:120]
                    top = TOP_MARK.match(t)
                    if top:
                        t = top.group(1).strip()
                    if not t:
                        continue
                    it = {"text": t}
                    got = parse_range(t)
                    if got:
                        it["from"], it["to"] = got
                    (tops if top else items).append(_clean_item(it))
                l["hw"] = _one_or_items(items)
                if tops:
                    l["extraHw"] = dict(l.get("extraHw") or {}, top=_one_or_items(tops))
            if stop:
                # 「この回の宿題を止める」。上乗せも消し、出す日に印だけ付ける。
                l["hw"] = {}
                l.pop("extraHw", None)
                l["stopped"] = True
            elif hw_items(l.get("hw")):
                l.pop("stopped", None)
            l["editedAt"] = int(time.time())
            save(school, data)
            return l
    return None


def add(school, key, topic="（予備）", hw_text=""):
    """予定の末尾に1回ぶん足す。

    日付は、直前の回から同じ間隔（ふだんは1週間）だけ後ろに置く。
    予定が空なら足せない ―― 何曜日にやるのかが分からないため。
    """
    with paths_lock():
        data = load(school)
        p = (data.get("plans") or {}).get(key)
        ls = (p or {}).get("lessons") or []
        if not p or not ls:
            return None
        last = ls[-1]
        try:
            t = time.mktime(time.strptime(last["date"], "%Y-%m-%d"))
        except (KeyError, ValueError):
            return None
        step = DAY * 7
        if len(ls) >= 2:
            try:
                t0 = time.mktime(time.strptime(ls[-2]["date"], "%Y-%m-%d"))
                if t - t0 > 0:
                    step = t - t0
            except (KeyError, ValueError):
                pass
        row = {"n": (last.get("n") or len(ls)) + 1,
               "date": time.strftime("%Y-%m-%d", time.localtime(t + step)),
               "topic": str(topic)[:60],
               "hw": _clean_hw({"text": str(hw_text)[:120]})}
        got = parse_range(row["hw"].get("text", ""))
        if got:
            row["hw"]["from"], row["hw"]["to"] = got
        ls.append(row)
        save(school, data)
        return row


def mark_published(school, key, n, assignment_id):
    """出した印を付ける。assignment_id は1件のIDか、IDの並び。

    1回から複数の宿題が出る（ブロックごと・上乗せ・毎週固定）。
    published には先頭の1件、publishedIds に全部を残す。
    """
    ids = assignment_id if isinstance(assignment_id, list) else [assignment_id]
    ids = [str(x) for x in ids if x]
    if not ids:
        return False
    with paths_lock():
        data = load(school)
        p = (data.get("plans") or {}).get(key)
        if not p:
            return False
        for l in (p.get("lessons") or []):
            if (l.get("n") or 0) == n:
                l["published"] = ids[0]
                if len(ids) > 1:
                    l["publishedIds"] = ids
                l["publishedAt"] = int(time.time())
                save(school, data)
                return True
    return False


# ------------------------------------------------------------------
# 今週の格子（学年 × 教科）
# ------------------------------------------------------------------
def week_grid(school, grades, subjects, when=None, enabled=None):
    """今週、どの学年のどの教科に何が出ているかの格子。

    **空のマスを見せることが目的である。** 出してあるものを並べるのは
    確認にしかならないが、出していないマスは行動につながる。
    紙の管理では絶対に見えない情報で、ここがこの画面の値打ち。
    """
    when = when or time.time()
    lt = time.localtime(when)
    # 週の始まり（月曜）
    start = when - ((lt.tm_wday) * DAY) - (lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec)
    end = start + 7 * DAY
    ps = plans(school)

    cells = {}
    # いま出ている（＝生徒がやっている）最後の回も一緒に返す。
    #
    # 週のはじめは、まだ授業をしていない教科のほうが多い。そのとき
    # 格子が「授業まえ」だけになり、**いま生徒が何をやっているのかが
    # 画面から消える**。講師が管理したいのはそちらである。
    live = {}
    for key, p in ps.items():
        for l in (p.get("lessons") or []):
            d = l.get("date")
            if not d:
                continue
            try:
                t = time.mktime(time.strptime(d, "%Y-%m-%d"))
            except ValueError:
                continue
            if start <= t < end:
                cells[key] = {
                    "n": l.get("n"), "date": d, "topic": l.get("topic", ""), "label": l.get("label"),
                    "hw": l.get("hw") or {},
                    "published": bool(l.get("published")),
                }
            elif t < start and l.get("published"):
                prev = live.get(key)
                if not prev or (l.get("n") or 0) > (prev.get("n") or 0):
                    live[key] = {"n": l.get("n"), "date": d,
                                 "topic": l.get("topic", ""), "label": l.get("label"),
                                 "hw": l.get("hw") or {}}

    grid = []
    for g in grades:
        row = {"grade": g, "cells": []}
        for s in subjects:
            key = "%s:%s" % (g, s)
            c = cells.get(key)
            # その学年でその教科を履修していなければ、マスを作らない。
            # 履修していない教科に「出てない」と警告を出すと、
            # 画面が警告で埋まって、本当の出し忘れが埋もれる。
            if enabled is not None and key not in enabled:
                row["cells"].append({"key": key, "subject": s,
                                     "state": "off", "cell": None})
                continue
            row["cells"].append({
                "key": key, "subject": s,
                "state": ("out" if (c and c["published"])
                          else "planned" if c else "missing"),
                "cell": c,
                # 今週ぶんがまだなら、いま出ている回を添える
                "live": (live.get(key) if not (c and c["published"]) else None),
                # 手が要る件数。呼ぶ側（tube_server）が入れる。
                "late": 0,
            })
        grid.append(row)
    return {"from": time.strftime("%Y-%m-%d", time.localtime(start)),
            "to": time.strftime("%Y-%m-%d", time.localtime(end - DAY)),
            "grid": grid}



def week_cells(school, keys, when=None):
    """鍵ごとの「今週のマス」。{鍵: {"key", "subject", "state", "cell", "live"}}。

    week_grid は「学年 × 教科」の格子を作る。コースは1つの学年・教科に
    いくつも並ぶ（中3数学なら 3T・3R・土特）ので、格子では置き場が無い。
    こちらは鍵をそのまま使う ―― 画面の時間割は、コマの鍵でここを引く。

    週2回のコースは、今週まだ出していない回があればそれを、
    全部出していれば最後に出した回をマスにする。
    """
    when = when or time.time()
    day = _dt.date.fromtimestamp(when)
    mon = day - _dt.timedelta(days=day.weekday())
    start, end = mon.isoformat(), (mon + _dt.timedelta(days=7)).isoformat()
    ps = plans(school)
    out = {}
    for key in keys:
        p = ps.get(key) or {}
        cell = live = None
        wk = []
        for l in sorted((p.get("lessons") or []), key=lambda x: x.get("date") or ""):
            d = l.get("date") or ""
            if not d:
                continue
            row = {"n": l.get("n"), "date": d, "topic": l.get("topic", ""), "label": l.get("label"),
                   "hw": l.get("hw") or {}, "published": bool(l.get("published"))}
            if start <= d < end:
                wk.append({"n": l.get("n"), "date": d, "topic": l.get("topic", ""), "label": l.get("label")})
                if cell is None or cell["published"]:
                    cell = row
            elif d < start and l.get("published"):
                live = dict(row)
        # 週2回のコースは、同じ週に回が2つある。時間割のコマがその曜日の回を出せるように、週の回を添える。
        if cell is not None and len(wk) > 1:
            cell["week"] = wk
        state = "out" if (cell and cell["published"]) else ("planned" if cell else "missing")
        out[key] = {"key": key, "subject": p.get("subject") or str(key).split(":", 1)[-1],
                    "state": state, "cell": cell, "app": p.get("app") is not False,
                    "live": live if state != "out" else None}
    return out


def set_use(school, key, level, by=""):
    """コースの導入の段階（courses.use_level）を決める。0 は紙のまま（app False）。
    いつ・誰が決めたかを残す。出した宿題はそのまま（消さない）。
    1 以上にすると、次の授業日から授業計画の宿題が出る。"""
    level = int(level)
    if level < 0 or level > 4:
        raise ValueError("段階は 0〜4")
    with paths_lock():
        data = load(school)
        p = (data.get("plans") or {}).get(key)
        if not p:
            return None
        p["use"] = level
        p["app"] = level > 0
        p["appAt"] = int(time.time())
        p["appBy"] = str(by or "")[:40]
        save(school, data)
    return p


def set_app(school, key, on, by=""):
    """コースでアプリを使う／使わないを切り替える（courses.app_on）。いつ・誰が決めたかを残す。
    出した宿題はそのまま（消さない）。使い始めると、次の授業日から授業計画の宿題が出る。
    段階（use）は消さない ―― 使わない → 使う で、前の段階に戻る（無ければ 4）。"""
    with paths_lock():
        data = load(school)
        p = (data.get("plans") or {}).get(key)
        if not p:
            return None
        prev = p.get("use")
        if on:
            p["use"] = prev if (isinstance(prev, int) and not isinstance(prev, bool) and 0 < prev <= 4) else 4
        p["app"] = bool(on)
        p["appAt"] = int(time.time())
        p["appBy"] = str(by or "")[:40]
        save(school, data)
    return p


def advance_weekly(school, key, at_by_id, week):
    """毎週固定の分を出したあとで、進んだ位置（at）と出した週（weeklyAt）を書く。

    **同じ週に二度出さない**ための印。位置は weekly[].id で引く ――
    配列の位置で覚えると、並べ替えたときに別の教材の位置が進む。
    """
    with paths_lock():
        data = load(school)
        p = (data.get("plans") or {}).get(key)
        if not p:
            return False
        for w in (p.get("weekly") or []):
            if w.get("id") in at_by_id:
                w["at"] = int(at_by_id[w["id"]])
        p["weeklyAt"] = week
        save(school, data)
    return True

# ------------------------------------------------------------------
# 排他。tube_server の LOCK を借りず、ここだけで閉じる。
# ------------------------------------------------------------------
import threading                                # noqa: E402
_LOCK = paths.GUARD          # 置き場にひとつだけの鍵（スレッドにもプロセスにも効く。paths.Guard）


def paths_lock():
    return _LOCK


if __name__ == "__main__":
    print("MYACADY_ROOT =", paths.ROOT)
    for s in paths.list_schools():
        ps = plans(s)
        print("\n校舎 %s ―― 授業計画 %d件" % (s, len(ps)))
        for key, p in sorted(ps.items()):
            ls = p.get("lessons") or []
            pub = len([1 for l in ls if l.get("published")])
            print("  %-12s %2d回（発行済み %d）曜日=%s 期限=%d日後"
                  % (key, len(ls), pub, p.get("weekday"), p.get("dueDays", 7)))
