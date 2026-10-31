#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""組み分けテストの日程。

何のためか
----------
早稲田アカデミーは **5週ごと**に塾内テスト（組み分けテスト）がある。
α と β、T と R の入れ替えがここで決まるので、生徒にとっては
学期でいちばん大きな山である。

授業計画はこの5週に合わせて組まれる ―― 4回が新しい内容、
5回目が総復習。そして本番の8日前から「総復習テスト対策」が出る。

    <ROOT>/schools/<校舎>/exams.json

        {"exams": [{"date": "2026-08-29", "name": "組み分けテスト"}, …],
         "prepDays": 8}

**日付は校舎が持つ。こちらで作らない。** 本部から来た日程を入れる。
入っていなければ「次のテストは無い」として扱い、対策も出さない ――
無い日程を推測して出すと、まちがった日に向けて生徒が走る。

なお、5週ごとという規則はあくまで既定であって、行事で動く。
規則から日付を計算するのではなく、**入っている日付を読む**。
"""

import datetime
import time

import paths
import curriculum_source as SOURCE

DAY = 86400


def _midnight(ymd, n=0):
    """ymd（"YYYY-MM-DD"）の n 日あとの 0 時。**日は暦で足す。**
    秒（n×DAY）で足すと、夏時間の切り替え（3 月・10 月の終わりの日曜）をまたいだときに
    23 時や 1 時になり、画面の日付が 1 日ずれる（2026-10-31、聞く時期が 10-30 でなく 10-29 からと出た）。"""
    d = datetime.date(*map(int, ymd.split("-"))) + datetime.timedelta(days=int(n))
    return time.mktime((d.year, d.month, d.day, 0, 0, 0, 0, 0, -1))
# 本番の何日前から対策を出すか。**2週間**。
# 8日では、5週ぶんの範囲を1教科50分で回すのに足りない
# （5教科 × 50分 = 1日4時間強。8日では他の宿題と両立しない）。
DEFAULT_PREP_DAYS = 14
# 組分けの申告（2026-10-01）。テストの結果で α⇄β・T⇄R が入れ替わる。塾は ID と名前を結ばないので、
# 新しいクラスは本人（保護者）に聞く。**テストの RESULT_DAYS 日後から ASK_DAYS 日のあいだ**、生徒の画面に
# 「クラスは どちらに なりましたか」を出す。日数は exams.json の resultDays で校舎ごとに変えられる。
DEFAULT_RESULT_DAYS = 7
ASK_DAYS = 14
MAX_EXAMS = 40


def _file(school):
    return paths.school_file(school, "exams.json")


def load(school):
    try:
        return paths.load(_file(school), {}) or {}
    except paths.BadPath:
        return {}


def save(school, data):
    paths.save(_file(school), data)


def all_exams(school, dept=None):
    """日付の早い順。壊れた行は落とす。
    exams.json に日程が**一度も入っていなければ**（鍵が無い）、原本の日程表（小学部の組分け・月例）を既定にする。
    管理ページで全部外した（"exams": []）ときは、外したとおり空にする ―― 外したものを勝手に戻さない。

    dept（"elementary"／"junior"）を渡すと、その部のテストだけ。部の印の無い行（管理ページで入れたもの）は全員に当てる。
    dept が None なら全部（管理ページの一覧）。"""
    out = []
    data = load(school)
    rows = data["exams"] if isinstance(data.get("exams"), list) else SOURCE.default_exams()
    for e in rows:
        d = str((e or {}).get("date") or "")[:10]
        if len(d) != 10:
            continue
        try:
            time.strptime(d, "%Y-%m-%d")
        except ValueError:
            continue
        dp = str(e.get("dept") or "")
        if dept is not None and dp and dp != dept:
            continue
        row = {"date": d, "name": str(e.get("name") or "組み分けテスト")[:40]}
        if dp:
            row["dept"] = dp
        out.append(row)
    out.sort(key=lambda x: x["date"])
    return out


def result_days(school):
    try:
        n = int(load(school).get("resultDays", DEFAULT_RESULT_DAYS))
    except (TypeError, ValueError):
        n = DEFAULT_RESULT_DAYS
    return max(0, min(21, n))


def placement_window(school, when=None, dept=None):
    """いま「組分けの結果、クラスはどちらに？」を聞く時期か。

    返すのは None か {"exam": {date, name}, "from": 時刻, "to": 時刻, "fromDay": "YYYY-MM-DD", "toDay": "YYYY-MM-DD"}。
    from は結果が出る日（テストの日＋resultDays）の 0時、to は聞く最後の日の終わり。
    聞くのは、結果が出たいちばん新しいテスト1つについてだけ。
    """
    now = when or time.time()
    rd = result_days(school)
    for e in reversed(all_exams(school, dept)):
        try:
            time.strptime(e["date"], "%Y-%m-%d")
        except ValueError:
            continue
        start = _midnight(e["date"], rd)
        end = _midnight(e["date"], rd + ASK_DAYS)
        if start <= now < end:
            return {"exam": e, "from": int(start), "to": int(end),
                    "fromDay": time.strftime("%Y-%m-%d", time.localtime(start)),
                    "toDay": time.strftime("%Y-%m-%d", time.localtime(end - 1))}
        if now >= end:
            break                       # それより古いテストは、もう聞かない
    return None


def set_exams(school, rows, result_days_=None):
    """日程を入れ替える（管理ページから）。形がおかしければ ValueError。prepDays はそのまま。"""
    if not isinstance(rows, list) or len(rows) > MAX_EXAMS:
        raise ValueError("日程は %d 件までです" % MAX_EXAMS)
    out, seen = [], set()
    for r in rows:
        d = str((r or {}).get("date") if isinstance(r, dict) else r or "")[:10]
        try:
            time.strptime(d, "%Y-%m-%d")
        except ValueError:
            raise ValueError("日付の形が違います: %r（2026-10-17 の形）" % d)
        if d in seen:
            continue
        seen.add(d)
        name = str((r.get("name") if isinstance(r, dict) else "") or "組み分けテスト")[:40]
        row = {"date": d, "name": name}
        dp = str(r.get("dept") or "") if isinstance(r, dict) else ""
        if dp in ("elementary", "junior"):
            row["dept"] = dp            # 原本の日程は部の印を持つ。保存し直しても落とさない
        out.append(row)
    out.sort(key=lambda x: x["date"])
    data = dict(load(school))
    data["exams"] = out
    if result_days_ is not None:
        if isinstance(result_days_, bool) or not isinstance(result_days_, int) or not 0 <= result_days_ <= 21:
            raise ValueError("結果が出るまでの日数は 0〜21 で")
        data["resultDays"] = result_days_
    save(school, data)
    return out


def year_start(school):
    """新年度のはじまり（"YYYY-MM-DD"）。入っていなければ ""。この日の朝に、全員の学年が1つ上がる（retire.roll）。"""
    d = str(load(school).get("yearStart") or "")[:10]
    try:
        time.strptime(d, "%Y-%m-%d")
    except ValueError:
        return ""
    return d


def set_year_start(school, date, when=None):
    """新年度のはじまりを入れる（管理ページから）。空なら外す。**きょうと過去の日は入れられない**
    （入れた瞬間に全員の学年が上がるのを防ぐ。少なくとも1日、気づく時間がある）。"""
    d = str(date or "").strip()[:10]
    data = dict(load(school))
    if not d:
        data.pop("yearStart", None)
        save(school, data)
        return ""
    try:
        time.strptime(d, "%Y-%m-%d")
    except ValueError:
        raise ValueError("日付の形が違います: %r（2027-02-06 の形）" % d)
    if d <= time.strftime("%Y-%m-%d", time.localtime(when or time.time())):
        raise ValueError("新年度のはじまりは、あした以降の日にしてください")
    data["yearStart"] = d
    save(school, data)
    return d


def prep_days(school):
    try:
        n = int(load(school).get("prepDays") or DEFAULT_PREP_DAYS)
    except (TypeError, ValueError):
        n = DEFAULT_PREP_DAYS
    return max(1, min(30, n))


def next_exam(school, when=None, dept=None):
    """次の組み分けテスト。もう無ければ None。

    当日も「次」に含める ―― 朝に開いた生徒に、その日のテストを
    「もう終わった」と見せない。
    """
    today = time.strftime("%Y-%m-%d", time.localtime(when or time.time()))
    for e in all_exams(school, dept):
        if e["date"] >= today:
            return e
    return None


def prev_exam(school, when=None, dept=None):
    """直前に終わった組み分けテスト。まだ1回も無ければ None。

    総復習の範囲は「前のテストの次の日から、次のテストまで」。
    学期のはじめから毎回ぜんぶを出し直すと、回を追うごとに量が増える。
    """
    today = time.strftime("%Y-%m-%d", time.localtime(when or time.time()))
    got = None
    for e in all_exams(school, dept):
        if e["date"] < today:
            got = e
    return got


def window(school, when=None, dept=None):
    """いま「総復習テスト対策」を出す時期か。

    返すのは
        None                        … 出さない（日程が無い／まだ早い）
        {"exam": …, "from": …, "left": n, "since": …}

    left は本番まであと何日か（当日は 0）。
    since は範囲のはじまり（前回のテストの翌日、無ければ空）。
    """
    now = when or time.time()
    e = next_exam(school, now, dept)
    if not e:
        return None
    return window_for(school, e, now, dept)


def window_for(school, e, now, dept=None):
    """組み分けテスト e に向けた対策の時期か。返す形は window と同じ。

    ふだんは window が次の本番を渡す。デモの見本の生徒にだけ、
    本物の日程とは別の e を渡す（tube_server.demo_exam_window）。
    """
    try:
        t = time.mktime(time.strptime(e["date"], "%Y-%m-%d"))
    except ValueError:
        return None
    days = prep_days(school)
    start = _midnight(e["date"], -days)
    if now < start:
        return None                     # まだ早い。ふだんの毎日テストのまま
    # **日数は日付どうしで数える。** 時刻の引き算で数えると、
    # 昼に開いたときだけ1日少なく出る（テスト当日の朝が「あと0日」、
    # 5日後の昼が「あと4日」になった）。生徒が数える日数と合わせる。
    d0 = time.strptime(time.strftime("%Y-%m-%d", time.localtime(now)), "%Y-%m-%d")
    left = int(round((t - time.mktime(d0)) / DAY))
    prev = prev_exam(school, now, dept)
    return {
        "exam": e,
        "from": time.strftime("%Y-%m-%d", time.localtime(start)),
        "left": max(0, left),
        "since": prev["date"] if prev else "",
    }
