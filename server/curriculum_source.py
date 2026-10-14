#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""カリキュラムの原本 ―― カリキュラム/カリキュラム.json を読む1本の口。

本部のカリキュラム（小4〜中3）とロンドン校の後期日程表から起こした第一信頼情報源
（作り方は scripts/curriculum/）。サーバはここからだけ読む。ここに無いものは「無い」と答える。

  <repo>/カリキュラム/カリキュラム.json      （本番は /opt/myacady/カリキュラム/カリキュラム.json）
  環境変数 TUBE_CURRICULUM で場所を変えられる（検査用）。

出すもの
  syllabus(sid)          … london.syllabi の1本（週に並べた単元。perWeek）
  syllabus_ids()         … その id の一覧
  course_syllabus_id(key)… コース（クラス:教科）に対応するシラバスの id。無ければ ""
  skip_dates(key)        … そのコースの「授業の無い週」の日付（休校・ハーフターム・冬期講習会）
  default_exams()        … 小学部の組分け・月例の日付（exams.json が空のときの既定）
  reference(grade)       … 学年の本部基準（reference_curriculum の形）。シラバスの週からつくる
"""
import datetime as _dt
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.environ.get("TUBE_CURRICULUM") or os.path.join(os.path.dirname(HERE), "カリキュラム", "カリキュラム.json")

_cache = {"mtime": None, "doc": None}


def load():
    """原本。無い・壊れているときは None（嘘の空表を返さない）。"""
    try:
        mt = os.path.getmtime(PATH)
    except OSError:
        return None
    if _cache["mtime"] != mt:
        try:
            with open(PATH, encoding="utf-8") as f:
                _cache["doc"] = json.load(f)
        except (OSError, ValueError):
            _cache["doc"] = None
        _cache["mtime"] = mt
    return _cache["doc"]


def _london():
    d = load()
    return (d or {}).get("london") or {}


def syllabus_ids():
    return sorted((_london().get("syllabi") or {}).keys())


def syllabus(sid):
    got = (_london().get("syllabi") or {}).get(sid)
    return json.loads(json.dumps(got)) if isinstance(got, dict) else None


def course_syllabus_id(key):
    c = (_london().get("classes") or {}).get(key) or {}
    return str(c.get("syllabus") or "")


def course_note(key):
    c = (_london().get("classes") or {}).get(key) or {}
    return str(c.get("note") or "")


def _dept(key):
    cid = key.split(":", 1)[0]
    if cid.startswith("e4"):
        return "e4"
    if cid.startswith("e5") and not cid.endswith("k"):
        return "e5"
    if cid.startswith("e6") and not cid.endswith("k"):
        return "e6"
    return "junior"


def skip_dates(key):
    """授業の無い週（原本の日程表に授業の記載が無い週）の7日ぶんの日付。"""
    cal = (_london().get("second_2026") or {})
    weeks = cal.get("weeks") or []
    lesson = {w.get("monday") for w in ((cal.get("lesson_weeks") or {}).get(_dept(key)) or [])}
    out = set()
    if not weeks or not lesson:
        return out
    mons = [w.get("monday") for w in weeks if w.get("monday")]
    lo, hi = min(lesson), max(lesson)
    for m in mons:
        if lo <= m <= hi and m not in lesson:
            d = _dt.date(*map(int, m.split("-")))
            for k in range(7):
                out.add((d + _dt.timedelta(days=k)).isoformat())
    return out


def term_start():
    """後期の最初の授業の週の月曜（日程表の授業の週のうち、いちばん早いもの）。無ければ ""。"""
    lw = ((_london().get("second_2026") or {}).get("lesson_weeks") or {})
    mons = [w.get("monday") for ws in lw.values() for w in (ws or []) if w.get("monday")]
    return min(mons) if mons else ""


def dept_of(level, class_id=""):
    """生徒の部。日程表は「小学部（小1〜小3、小4S〜小6S）」と「中学部（5K6K、中1〜中3）」に分かれる。
    5K・6K（e5k・e6k）は中学部。小4K（e4k）は日程表のどちらにも無いので ""（部の印の付いたテストは当てない）。"""
    cid = str(class_id or "")
    lv = str(level or "")
    if cid in ("e5k", "e6k") or lv.startswith("j"):
        return "junior"
    if cid.endswith("k"):
        return ""
    if lv.startswith("e"):
        return "elementary"
    return ""


def default_exams():
    """小学部の組分け・月例（日程表の土曜）。exams.json に日程が一度も入っていないときの既定。
    **小学部だけのテスト**なので dept を付ける（中学部・5K6K の生徒には当てない）。"""
    cal = (_london().get("second_2026") or {})
    out = []
    for e in ((cal.get("tests") or {}).get("elementary") or []):
        if "組分け" in str(e.get("name") or ""):
            out.append({"date": e["date"], "name": "組分け・月例", "dept": "elementary"})
    return out


def reference(grade):
    """学年の本部基準（reference_curriculum の形）。同じ学年のシラバスの週を束ねる。無ければ None。"""
    syl = _london().get("syllabi") or {}
    classes = _london().get("classes") or {}
    by_week = {}
    seen = set()
    for key, c in classes.items():
        sid = c.get("syllabus")
        d = syl.get(sid) if sid else None
        if not d or d.get("grade") != grade:
            continue
        subj = d.get("subject")
        if subj in seen:
            continue
        seen.add(subj)
        for u in d.get("units") or []:
            if u.get("week") and u.get("topic"):
                by_week.setdefault(u["week"], []).append({"subject": subj, "unit": u["topic"]})
    if not by_week:
        return None
    weeks = [{"w": i + 1, "from": m, "units": by_week[m]} for i, m in enumerate(sorted(by_week))]
    doc = load() or {}
    return {"grade": grade, "name": grade, "source": "カリキュラム/カリキュラム.json（本部の表＋後期日程表）",
            "provisional": False, "year": doc.get("year"), "weeks": weeks}
