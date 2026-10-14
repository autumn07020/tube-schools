#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""コース ―― 1つの授業を、1件にまとめて持つ。

    <ROOT>/schools/<校舎>/lessons.json の plans["<コースID>:<教科>"]

考え方は3つだけ（Claude outputs/PLAN-宿題と配達.md 1章）
------------------------------------------------------
    在籍クラス  生徒の classId。1人1つ
    コース      ここ。講師・時間割・受ける生徒・宿題の予定を1件にぜんぶ書く
    受講科目    生徒の subjects。無ければ全教科

合同（中2理科）も、指名（土特・早慶必勝・オンライン）も、講習も、
**ぜんぶコース1種類で書く。** 種類ごとの特別な処理を作らない。
授業が増えたり講習が入ったりしても、CSV の行を足すだけで済むようにするため。

1件の形
-------
    定義（教室長が CSV で入れる。講師の画面からは変わらない）
        name grade grades subject teachers slots classes students
        unit weekday from to
    授業計画（講師が画面で直す。lessons.py が扱う）
        start skip lessons weekly weeklyAt extra

**teachers の欄があるものをコースとみなす。** 空の配列でもよい（講師の
決まっていない枠）。欄の無いものは旧来の「学年:教科」の計画で、ここでは扱わない。

日付の計算は datetime.date で行う
--------------------------------
時刻に86400秒を足して日付を進めると、夏時間が終わる日に1日ずれる
（10月の最終日曜の後、23時になって前の日の日付に落ちる）。
日付だけで数えればこの問題は起きない。時刻が要るのは期限だけ。
"""

import csv
import datetime as _dt
import io
import os
import re
import time

import paths
import lessons as L

# 定義の欄。**ここに無い欄は CSV から入らない。** 足すときはここに足す。
DEF_KEYS = ("name", "grade", "grades", "subject", "teachers", "slots",
            "classes", "students", "unit", "weekday", "from", "to")

COURSE_ID = re.compile(r"^[a-z0-9_-]{1,16}$")
CLASS_ID = re.compile(r"^[a-z0-9_-]{1,24}$")
GRADE_ID = re.compile(r"^[ej][1-9]$")
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

SUBJECTS = ("japanese", "math", "english", "science", "social")
# CSV の「教科」欄の呼び方。算数と数学はどちらも math。
SUBJECT_WORD = {"国語": "japanese", "算数": "math", "数学": "math",
                "英語": "english", "理科": "science", "社会": "social"}
SUBJECT_OUT = {"japanese": "国語", "math": "数学", "english": "英語",
               "science": "理科", "social": "社会"}
ELEMENTARY = ("e1", "e2", "e3", "e4", "e5", "e6")
# 名簿の「受講科目」欄。国英／国数英／国数／国数英理社 のように頭文字で書く。
SUBJECT_INITIAL = {"国": "japanese", "算": "math", "数": "math",
                   "英": "english", "理": "science", "社": "social"}
DAY = {"月": 1, "火": 2, "水": 3, "木": 4, "金": 5, "土": 6, "日": 7}
DAY_LABEL = {v: k for k, v in DAY.items()}

HEAD = ["id", "教科", "名前", "学年", "講師", "時間", "クラス", "指名", "単位", "期間"]


# ------------------------------------------------------------------
# 読む
# ------------------------------------------------------------------
def is_course(p):
    return isinstance(p, dict) and isinstance(p.get("teachers"), list)


def app_on(p):
    """このコースでアプリを使うか（宿題を出す・毎日テスト・成績・進度が動く）。

    しばらくは使うクラスと使わないクラスが混在する（2026-09-12 本人。半年以上）。
    **講師がコースごとに決める**（lessons.set_app）。CSV で新しく登録したコースは
    「使わない」で入る（courses-import）。印の無い古いコースは使う扱い ―― 動いている
    ものを止めない。"""
    return isinstance(p, dict) and p.get("app") is not False


def app_courses(school):
    return {k: p for k, p in all_courses(school).items() if app_on(p)}


# 導入の段階（2026-09-23 本人：スロースタート・部分導入に最適化する）。
#   0 紙のまま       時間割にだけ出る。生徒の画面には出ない（app False と同じ）
#   1 宿題を出す     授業計画の宿題が生徒の画面に出る。提出と評価は紙のまま（今日やることには出ない）
#   2 写真で提出     生徒がノートの写真で出せる。宿題チェックに並ぶ
#   3 添削まで       写真に赤を入れて返せる（iPad・印刷）
#   4 毎日テストまで 毎日テスト（苦手から自動で出る問題）がこのコースでも動く
# 段階は積み上げ（上の段階は下を含む）。**印の無い古いコースは 4**（動いているものを止めない）。
USE_LEVELS = (0, 1, 2, 3, 4)
USE_WORDS = {0: "紙のまま", 1: "宿題を出す", 2: "写真で提出", 3: "添削まで", 4: "毎日テストまで"}


def use_level(p):
    """このコースの導入の段階 0〜4。app が False なら段階に関わらず 0。"""
    if not isinstance(p, dict) or p.get("app") is False:
        return 0
    u = p.get("use")
    if isinstance(u, int) and not isinstance(u, bool) and 0 <= u <= 4:
        return u
    return 4


def use_flags(p):
    """段階を、画面とサーバが見る4つの印に開く。"""
    u = use_level(p)
    return {"hw": u >= 1, "photo": u >= 2, "correct": u >= 3, "quiz": u >= 4}


_CACHE = {}


def all_courses(school):
    """{鍵: コース}。**読むだけに使うこと**（返す辞書は控えを共有している）。

    講師の権限は宿題1件ごとに引くので、そのたびにファイルを読むと
    一覧1回で数百回読むことになる。更新時刻と大きさが同じ間は控えを返す。
    """
    path = L._file(school)
    try:
        st = os.stat(path)
    except OSError:
        return {}
    sig = (st.st_mtime_ns, st.st_size)
    got = _CACHE.get(school)
    if got and got[0] == sig:
        return got[1]
    plans = (paths.load(path, {}) or {}).get("plans") or {}
    out = {k: p for k, p in plans.items() if is_course(p)}
    _CACHE[school] = (sig, out)
    return out


def course_id(key):
    """鍵「<コースID>:<教科>」の前半。コースから出した宿題の classId に入る。"""
    return str(key).split(":", 1)[0]


def today():
    return time.strftime("%Y-%m-%d")


def active(p, day=None):
    """期間の中か。from・to が空なら常設。"""
    d = day or today()
    return (not p.get("from") or p["from"] <= d) and \
           (not p.get("to") or d <= p["to"])


def accounts_of(school):
    return paths.load(paths.school_file(school, "accounts.json"), {}) or {}


# ------------------------------------------------------------------
# 講師の担当（PLAN 規則1）
# ------------------------------------------------------------------
def of_teacher(school, sid):
    return {k: p for k, p in all_courses(school).items()
            if sid and sid in (p.get("teachers") or [])}


def pairs_of(school, sid):
    """担当コースから (ID, 教科) の組を作る。

    宿題の一覧や生徒の記録の権限は、いまも「クラス × 教科」の組で
    判定している（tube_server.can_see）。コースはその組を**足すだけ**で、
    判定の仕組みは変えない。足すのはコースID自身（コースから出した
    宿題の classId）と、コースの在籍クラス。
    """
    out = []
    for key, p in sorted(of_teacher(school, sid).items()):
        sub = p.get("subject") or ""
        for cid in [course_id(key)] + list(p.get("classes") or []):
            if (cid, sub) not in out:
                out.append((cid, sub))
    return out


def named_of(school, sid):
    """担当コースで指名されている生徒。在籍クラスが別でも記録を読んでよい。"""
    out = set()
    for p in of_teacher(school, sid).values():
        out |= set(p.get("students") or [])
    return out


def slots_of(school, sid):
    """時間割。1行＝1コマ。曜日・開始時刻の順。period はその日の何コマ目か。"""
    rows = []
    for key, p in of_teacher(school, sid).items():
        if not active(p):
            continue
        # 時刻の決まっていないコース（CSV の時間が空・枠だけのコース）も1行出す（day 0）。
        # 出さないと、講師の画面の「担当コース」（導入の段階・成績・進度）から消える。
        for s in (p.get("slots") or [{"day": 0, "start": "", "end": ""}]):
            rows.append({"key": key, "classId": course_id(key),
                         "subject": p.get("subject") or "",
                         "name": p.get("name") or key,
                         "grade": p.get("grade") or "",
                         "app": app_on(p),
                         "use": use_level(p),
                         "day": int(s.get("day") or 0),
                         "start": s.get("start") or "",
                         "end": s.get("end") or ""})
    rows.sort(key=lambda r: (r["day"] or 9, r["start"]))
    n = {}
    for r in rows:
        n[r["day"]] = n.get(r["day"], 0) + 1
        r["period"] = n[r["day"]]
    return rows


# ------------------------------------------------------------------
# 受け取る生徒（PLAN 規則2・4）
# ------------------------------------------------------------------
def receivers(school, p, db=None):
    """このコースの宿題を受け取る生徒の sid。**出す時点で1回だけ呼ぶ。**

    指名（students）があればそれ。無ければ在籍クラス（classes）の生徒のうち、
    受講科目にその教科がある生徒。受講科目を持たない生徒は全教科とみなす。
    在籍が終わった生徒は入れない。
    """
    db = accounts_of(school) if db is None else db
    live = {a.get("sid"): a for a in db.values()
            if a.get("role") == "student" and not a.get("leftAt") and a.get("sid")}
    if p.get("students"):
        return sorted(s for s in p["students"] if s in live)
    classes = set(p.get("classes") or [])
    sub = p.get("subject")
    return sorted(sid for sid, a in live.items()
                  if a.get("classId") in classes
                  and (not a.get("subjects") or sub in a["subjects"]))


def key_for(school, class_id, subject, grade):
    """その在籍クラスのその教科の授業計画の鍵。

    在籍クラスが入っているコースのうち、クラスの数が少ないもの
    （中3T の英語なら「中3T 英語」を「中3TR 英語」より先に）。
    指名のコースは上乗せなので選ばない。
    **コースが無ければ旧来の「学年:教科」を返す**（古い形を読むのはここだけ）。
    """
    got = sorted((len(p.get("classes") or []), k)
                 for k, p in all_courses(school).items()
                 if p.get("subject") == subject and active(p)
                 and class_id in (p.get("classes") or []))
    if got:
        return got[0][1]
    return "%s:%s" % (grade, subject)


def parse_subjects(text):
    """「国数英理社」→ ["japanese", "math", "english", "science", "social"]。"""
    out = []
    for ch in re.sub(r"[\s　]", "", str(text or "")):
        s = SUBJECT_INITIAL.get(ch)
        if not s:
            raise ValueError("受講科目に知らない字があります: %r（国数英理社で書く）" % ch)
        if s not in out:
            out.append(s)
    return out


def subjects_text(subs):
    """parse_subjects の逆。数学は「数」で書く。"""
    rev = {"japanese": "国", "math": "数", "english": "英",
           "science": "理", "social": "社"}
    return "".join(rev[s] for s in SUBJECTS if s in (subs or []))


# ------------------------------------------------------------------
# 日付（PLAN 規則3・5）
# ------------------------------------------------------------------
def _date(d):
    return _dt.date(*map(int, d.split("-")))


def weekdays(p):
    """授業のある曜日（1=月 … 7=日）。1回＝1週のコースは基準の曜日だけ。"""
    if p.get("unit") == "week":
        return [int(p.get("weekday") or 1)]
    return sorted({int(s.get("day") or 0) for s in (p.get("slots") or [])
                   if s.get("day")})


def dates(p, start, count, skip=None):
    """start から、授業のある曜日を count 個並べる。skip の日は飛ばす。"""
    days = weekdays(p)
    if not days or not DATE.match(start or "") or count <= 0:
        return []
    skip = set(skip or [])
    x, out = _date(start), []
    for _ in range(3700):
        if len(out) >= count:
            break
        s = x.isoformat()
        if x.isoweekday() in days and s not in skip:
            out.append(s)
        x += _dt.timedelta(days=1)
    return out


def step(p, d, n):
    """日付 d から、授業のある曜日を n 個ぶん動かす（負なら前へ）。

    週2回のコースで1コマずらすと火→木になる。7日ずつ動かすと1週間飛ぶ。
    """
    days = weekdays(p)
    if not days or not n or not DATE.match(d or ""):
        return d
    x, k = _date(d), 0
    one = _dt.timedelta(days=1 if n > 0 else -1)
    while k < abs(n):
        x += one
        if x.isoweekday() in days:
            k += 1
    return x.isoformat()


def is_review(p, d):
    """総復習の回か。start の週を第1週として、5週ごと。**回の数では数えない。**

    cycleStart があればそちらを起点にする。シラバス（教材の並び）から作った計画は、
    教材の総復習が第5週に来るように起点を持つ（syllabus.cycle_start）。予定の始まり（start）と
    周期の起点は別の物 ―― 夏の前から予定を入れても、周期はずれない。"""
    st = p.get("cycleStart") or p.get("start") or ""
    if not (DATE.match(st) and DATE.match(d or "")):
        return False
    a, b = _date(st), _date(d)
    a -= _dt.timedelta(days=a.weekday())
    b -= _dt.timedelta(days=b.weekday())
    week = (b - a).days // 7 + 1
    return week > 0 and week % L.CYCLE == 0


def due_ms(p, rows, l):
    """期限。次の回の日付の、その曜日の授業開始時刻。

    次の回が無ければ7日後。その曜日に授業の枠が無ければ 23:59。
    小5β（月曜にまとめて出す）なら次の月曜、中3（毎授業で見る）なら次の授業になる。
    """
    d = l.get("date") or ""
    later = sorted(x.get("date") for x in rows if (x.get("date") or "") > d)
    nd = later[0] if later else (_date(d) + _dt.timedelta(days=7)).isoformat()
    wd = _date(nd).isoweekday()
    hm = "23:59"
    for s in (p.get("slots") or []):
        if int(s.get("day") or 0) == wd and HHMM.match(s.get("start") or ""):
            hm = s["start"]
            break
    y, m, dd = map(int, nd.split("-"))
    hh, mm = map(int, hm.split(":"))
    return int(time.mktime((y, m, dd, hh, mm, 0, 0, 0, -1)) * 1000)


def iso_week(d):
    y, w, _ = _date(d).isocalendar()
    return "%d-W%02d" % (y, w)


def weekly_range(w):
    """毎週固定の分の、次の範囲 (はじめ, おわり)。wrap を超えたら1に戻る。"""
    stp = max(1, int(w.get("step") or 1))
    at = max(0, int(w.get("at") or 0))
    wrap = max(0, int(w.get("wrap") or 0))
    lo = at + 1
    if wrap and lo > wrap:
        lo = 1
    hi = lo + stp - 1
    if wrap and hi > wrap:
        hi = wrap
    return lo, hi


# ------------------------------------------------------------------
# CSV（教室長が入れる。出して直して入れ直すと、元に戻る）
# ------------------------------------------------------------------
def parse_slots(text):
    """「月16:40-18:10 木16:40-18:10」→ [{"day":1,"start":"16:40","end":"18:10"}, …]"""
    out = []
    for part in str(text or "").split():
        m = re.match(r"^([月火水木金土日])(\d{1,2}:\d{2})[-‐–〜~](\d{1,2}:\d{2})$", part)
        if not m:
            raise ValueError("時間の書き方が違います: %r（例 月16:40-18:10）" % part)
        st, en = m.group(2).zfill(5), m.group(3).zfill(5)
        if not (HHMM.match(st) and HHMM.match(en)) or en <= st:
            raise ValueError("時刻が正しくありません: %r" % part)
        out.append({"day": DAY[m.group(1)], "start": st, "end": en})
    return out


def slots_text(slots):
    return " ".join("%s%s-%s" % (DAY_LABEL.get(int(s.get("day") or 0), "?"),
                                 s.get("start", ""), s.get("end", ""))
                    for s in (slots or []))


def parse_row(r, db, known_classes):
    """CSV の1行を (鍵, 定義) にする。おかしければ ValueError。

    db は accounts.json、known_classes は在籍クラスIDの集合。
    **講師はログインID、指名は「在籍クラス-出席番号」で書かせる** ―― 氏名を書く欄を作らない。
    """
    def col(name):
        return str(r.get(name) or "").strip()

    cid = col("id")
    if not COURSE_ID.match(cid):
        raise ValueError("id は英小文字・数字・- _ で16文字まで: %r" % cid)
    word = col("教科")
    sub = SUBJECT_WORD.get(word) or (word if word in SUBJECTS else "")
    if not sub:
        raise ValueError("教科が分かりません: %r（国語・算数・数学・英語・理科・社会）" % word)
    grades = col("学年").split()
    if not grades or not all(GRADE_ID.match(g) for g in grades):
        raise ValueError("学年は e1〜e6・j1〜j3 を空白区切りで: %r" % col("学年"))

    teachers = []
    for lid in col("講師").split():
        a = db.get(lid.lower())
        if not a or a.get("role") != "teacher":
            raise ValueError("講師のログインIDが見つかりません: %r" % lid)
        if a["sid"] not in teachers:
            teachers.append(a["sid"])

    classes = col("クラス").split()
    for c in classes:
        if c not in known_classes:
            raise ValueError("在籍クラスが見つかりません: %r" % c)

    students = []
    if col("指名"):
        by_seat = {(a.get("classId"), a.get("seat")): a.get("sid")
                   for a in db.values() if a.get("role") == "student"}
        for tok in col("指名").split():
            if "-" not in tok:
                raise ValueError("指名は「在籍クラス-出席番号」で書く: %r" % tok)
            c, seat = tok.rsplit("-", 1)
            sid = by_seat.get((c, seat))
            if not sid:
                raise ValueError("指名の生徒が見つかりません: %r" % tok)
            if sid not in students:
                students.append(sid)
    if classes and students:
        raise ValueError("クラスと指名は、どちらか一方だけ書く: %s" % cid)

    unit, weekday = "lesson", 0
    u = col("単位")
    if u.startswith("週"):
        m = re.match(r"^週[:：]([月火水木金土日])$", u)
        if not m:
            raise ValueError("単位は「授業」か「週:月」の形: %r" % u)
        unit, weekday = "week", DAY[m.group(1)]
    elif u not in ("", "授業"):
        raise ValueError("単位は「授業」か「週:月」の形: %r" % u)

    frm = to = ""
    if col("期間"):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})?\s*[〜～~]\s*(\d{4}-\d{2}-\d{2})?$", col("期間"))
        if not m:
            raise ValueError("期間は「2027-07-20〜2027-08-25」の形: %r" % col("期間"))
        frm, to = m.group(1) or "", m.group(2) or ""

    d = {"name": col("名前") or cid, "grade": grades[0], "subject": sub,
         "teachers": teachers, "slots": parse_slots(col("時間")),
         "classes": classes, "students": students,
         "unit": unit, "weekday": weekday, "from": frm, "to": to}
    if len(grades) > 1:
        d["grades"] = grades
    return "%s:%s" % (cid, sub), d


def read_csv(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if rows and not all(h in rows[0] for h in HEAD):
        raise ValueError("CSV の見出しが違います。必要な列: %s" % ",".join(HEAD))
    return rows


def upsert(school, rows, new_app=None):
    """定義を入れる。(作った数, 直した数) を返す。

    new_app  新しく作るコースの「アプリを使う」印。CSV の取り込み（courses-import）は False で入れ、
             講師が選んで使い始める。None なら印を置かない（印の無いコースは使う扱い。検査やデモの組み立て用）。

    **授業計画（lessons・weekly・extra など）には触らない。**
    **CSV に無いコースは消さない。** やめるときは期間の終わりを入れる ――
    消すと、出した宿題の行き先（lesson.key）が宙に浮く。
    """
    with L.paths_lock():
        data = L.load(school)
        plans = data.setdefault("plans", {})
        made = changed = 0
        for key, d in rows:
            p = plans.get(key)
            if p is None:
                plans[key] = dict(d, lessons=[]) if new_app is None else dict(d, lessons=[], app=bool(new_app))
                made += 1
                continue
            before = {k: p.get(k) for k in DEF_KEYS}
            for k in DEF_KEYS:
                if k in d:
                    p[k] = d[k]
                else:
                    p.pop(k, None)
            if before != {k: p.get(k) for k in DEF_KEYS}:
                changed += 1
        L.save(school, data)
    return made, changed


def export_rows(school, db=None):
    """CSV の行（見出しを除く）。講師はログインID、指名は「在籍クラス-出席番号」。"""
    db = accounts_of(school) if db is None else db
    by_sid = {a.get("sid"): (lid, a) for lid, a in db.items() if a.get("sid")}
    rows = []
    for key, p in sorted(all_courses(school).items()):
        grades = p.get("grades") or [p.get("grade") or ""]
        sub = p.get("subject") or ""
        word = SUBJECT_OUT.get(sub, sub)
        if sub == "math" and grades[0] in ELEMENTARY:
            word = "算数"
        teachers = " ".join(by_sid[s][0] for s in (p.get("teachers") or [])
                            if s in by_sid)
        named = " ".join("%s-%s" % (by_sid[s][1].get("classId"), by_sid[s][1].get("seat"))
                         for s in (p.get("students") or []) if s in by_sid)
        unit = ("週:%s" % DAY_LABEL.get(int(p.get("weekday") or 1), "月")
                if p.get("unit") == "week" else "授業")
        period = ("%s〜%s" % (p.get("from") or "", p.get("to") or "")
                  if (p.get("from") or p.get("to")) else "")
        rows.append([course_id(key), word, p.get("name") or "", " ".join(grades),
                     teachers, slots_text(p.get("slots")),
                     " ".join(p.get("classes") or []), named, unit, period])
    return rows


def write_csv(school, path, db=None):
    rows = export_rows(school, db)
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        w.writerows(rows)
    return len(rows)


# ------------------------------------------------------------------
# 時間割（時間だけを入れ替える）―― カリキュラム/コマ.csv（scripts/curriculum/時間割/ が作る）
# ------------------------------------------------------------------
SLOT_HEAD = ["id", "教科", "名前", "学年", "時間", "クラス"]


def parse_slot_row(r, known_classes):
    """時間割の1行を (鍵, 定義の一部) にする。おかしければ ValueError。

    **講師と指名の欄は無い。** 時間割から入れるのは時間（コマ）だけで、講師・指名・授業計画は
    管理ページで決めたものをそのまま残すため。名前・学年・クラスは、まだ無いコースを作るときだけ使う。
    """
    def col(name):
        return str(r.get(name) or "").strip()

    cid = col("id")
    if not COURSE_ID.match(cid):
        raise ValueError("id は英小文字・数字・- _ で16文字まで: %r" % cid)
    word = col("教科")
    sub = SUBJECT_WORD.get(word) or (word if word in SUBJECTS else "")
    if not sub:
        raise ValueError("教科が分かりません: %r（国語・算数・数学・英語・理科・社会）" % word)
    grades = col("学年").split()
    if not grades or not all(GRADE_ID.match(g) for g in grades):
        raise ValueError("学年は e1〜e6・j1〜j3 を空白区切りで: %r" % col("学年"))
    classes = col("クラス").split()
    for c in classes:
        if c not in known_classes:
            raise ValueError("在籍クラスが見つかりません: %r" % c)
    d = {"name": col("名前") or cid, "grade": grades[0], "subject": sub,
         "slots": parse_slots(col("時間")), "classes": classes}
    if len(grades) > 1:
        d["grades"] = grades
    return "%s:%s" % (cid, sub), d


def read_slot_csv(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("行がありません")
    if not all(h in rows[0] for h in SLOT_HEAD):
        raise ValueError("CSV の見出しが違います。必要な列: %s" % ",".join(SLOT_HEAD))
    return rows


def set_slots(school, rows):
    """時間（コマ）だけを入れ替える。(作った数, 直した数, 変わらない数) を返す。

      すでにあるコース … slots だけを書き換える。講師・クラス・指名・期間・授業計画・使う印には触らない
      まだ無いコース   … 新しく作る。講師なし・受ける生徒はクラスだけ・紙のまま（app False）。講師は管理ページで
      表に無いコース   … 触らない（時間割から消えた授業は、管理ページで期間の終わりを入れる）

    **1件でもコースでない計画（旧来の「学年:教科」）に当たれば、何も書かない。**
    """
    with L.paths_lock():
        data = L.load(school)
        plans = data.setdefault("plans", {})
        for key, _d in rows:
            if key in plans and not is_course(plans[key]):
                raise ValueError("コースではない計画があります（先にコース表で入れてください）: %s" % key)
        made = changed = same = 0
        for key, d in rows:
            p = plans.get(key)
            if p is None:
                p = {"name": d["name"], "grade": d["grade"], "subject": d["subject"],
                     "teachers": [], "slots": d["slots"], "classes": list(d.get("classes") or []),
                     "students": [], "unit": "lesson", "weekday": 0, "from": "", "to": "",
                     "lessons": [], "app": False}
                if d.get("grades"):
                    p["grades"] = list(d["grades"])
                plans[key] = p
                made += 1
            elif (p.get("slots") or []) == d["slots"]:
                same += 1
            else:
                p["slots"] = d["slots"]
                changed += 1
        L.save(school, data)
    return made, changed, same


# ------------------------------------------------------------------
# 担当（講師だけを入れ替える）―― カリキュラム/担当.csv（scripts/curriculum/時間割/build.py が作る。ログインIDだけ）
# ------------------------------------------------------------------
TEACHER_HEAD = ["id", "教科", "講師"]


def read_teacher_csv(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("行がありません")
    if not all(h in rows[0] for h in TEACHER_HEAD):
        raise ValueError("CSV の見出しが違います。必要な列: %s" % ",".join(TEACHER_HEAD))
    return rows


def parse_teacher_row(r, db):
    """担当の1行を (鍵, 講師の sid の並び) にする。おかしければ ValueError。

    講師の欄はログインID（空白区切り）。空なら触らない（None）。「-」なら講師なしにする（[]）。
    講師でない口座・在籍終了の講師は入れない（管理ページの admin.set_teacher と同じ決まり）。
    """
    def col(name):
        return str(r.get(name) or "").strip()

    cid = col("id")
    if not COURSE_ID.match(cid):
        raise ValueError("id は英小文字・数字・- _ で16文字まで: %r" % cid)
    word = col("教科")
    sub = SUBJECT_WORD.get(word) or (word if word in SUBJECTS else "")
    if not sub:
        raise ValueError("教科が分かりません: %r（国語・算数・数学・英語・理科・社会）" % word)
    key = "%s:%s" % (cid, sub)
    t = col("講師")
    if not t:
        return key, None
    if t == "-":
        return key, []
    sids = []
    for lid in t.split():
        a = db.get(lid)
        if not a or a.get("role") != "teacher" or not a.get("sid"):
            raise ValueError("講師のIDが見つかりません: %s" % lid)
        if a.get("leftAt"):
            raise ValueError("在籍終了の講師は、担当にできません: %s" % lid)
        if a["sid"] not in sids:
            sids.append(a["sid"])
    return key, sids


def set_teachers(school, rows):
    """講師だけを入れ替える。(直した数, 変わらない数) を返す。rows は (鍵, sid の並び)。触らない行（None）は渡さない。

      すでにあるコース … teachers だけを書き換える。時間・クラス・指名・期間・授業計画・使う印には触らない
      無いコース       … 作らない（先に時間割（courses-slots）で作る）

    **1件でも無いコース・コースでない計画に当たれば、何も書かない。**
    """
    with L.paths_lock():
        data = L.load(school)
        plans = data.setdefault("plans", {})
        for key, _s in rows:
            if key not in plans:
                raise ValueError("コースがありません（先に時間割で作ってください）: %s" % key)
            if not is_course(plans[key]):
                raise ValueError("コースではない計画があります（先にコース表で入れてください）: %s" % key)
        changed = same = 0
        for key, sids in rows:
            p = plans[key]
            if list(p.get("teachers") or []) == list(sids):
                same += 1
            else:
                p["teachers"] = list(sids)
                changed += 1
        if changed:
            L.save(school, data)
    return changed, same
