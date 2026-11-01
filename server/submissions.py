#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ノートの宿題を、写真で出す。

流れ
----
    生徒  ノートに解く → 家で写真を撮る → 宿題のページから出す
    講師  「出された宿題」から中身を見る → 4段階で評価 → ひとこと返す
    生徒  「見ました」の印と、先生のひとことが一覧に出る

なぜ作るか
----------
紙の宿題は、アプリからは達成が見えない。見えないものは
「未提出」にも数えられないし、褒めることもできない。
**紙でちゃんとやっている生徒ほど、システム上は何もしていないように見える。**
写真1枚でそこがつながる。

置くもの
--------
    <ROOT>/schools/<校舎>/submissions.json      目録（誰がいつ何枚、評価、ひとこと）
    <ROOT>/schools/<校舎>/submissions/<sid>/…   画像そのもの

目録の1件

    {"<宿題ID>": {"<sid>": {
        "at": 受け取った時刻,
        "files": [{"name": …, "kind": "jpg", "bytes": …}, …],
        "seen": 講師が見た時刻（0なら まだ）,
        "by": 見た講師のsid,
        "note": 講師のひとこと,
    }}}

**評価（4段階）は ratings.json のまま**にする。すでに提出率も
「気にかける生徒」もそこを見ている。二重に持つと必ず食い違う。

消えかた
--------
退塾から6か月で、進捗の記録と一緒に消える（tube_server.py の purge）。
答案は進捗よりも重い個人情報なので、**残す理由がない限り残さない。**
"""

import io
import os
import time

import paths

# 1枚の上限と、1回に出せる枚数。
#
# iPhone の写真は 2〜4MB。ノート見開き4枚で 16MB になる。
# 上限を切らないと、1人の生徒が校舎の空き容量を使い切れてしまう。
MAX_BYTES = 6 * 1024 * 1024
MAX_FILES = 10          # 1回で10枚まで（2026-10-08 の見本）
KEEP_DAYS = 180          # 写真を置いておく日数（prune-photos の既定）。評価・ひとことは残る
GRADED_KEEP_DAYS = 7     # 採点（先生が見た）から、答案の写真を置いておく日数（2026-10-08）。返した添削は生徒が消すか退塾まで残す


def _index_path(school):
    return paths.school_file(school, "submissions.json")


def _locked(fn):
    """台帳を読んで書き戻す関数は、鍵（paths.GUARD）の中で通す。
    2 本の要求が重なると、あとから書いた方が先の変更を消す（10-26 #13：評価の PUT がひとことを消した）。"""
    def run(*a, **k):
        with paths.GUARD:
            return fn(*a, **k)
    run.__name__, run.__doc__ = fn.__name__, fn.__doc__
    return run


def load(school):
    try:
        return paths.load(_index_path(school), {}) or {}
    except paths.BadPath:
        return {}


def save(school, db):
    paths.save(_index_path(school), db)


def of_assignment(school, aid, db=None):
    """その宿題に出ているもの。{sid: 1件}"""
    db = load(school) if db is None else db
    return (db.get(aid) or {})


def of_student(school, sid, db=None):
    """その生徒が出したもの。{宿題ID: 1件}"""
    db = load(school) if db is None else db
    out = {}
    for aid, per in db.items():
        got = (per or {}).get(sid)
        if got:
            out[aid] = got
    return out


@_locked
def put(school, aid, sid, files, now=None):
    """出す。now … 出した時刻（秒）。省略で「いま」。デモが過去の日付で作るときだけ渡す。

    **同じ宿題に出し直したら、前のものは消す。**

    出し直しは よくある（暗くて読めなかった、1枚撮り忘れた）。
    古い写真を残しておく理由がない ―― 講師が見るのは最後の1組だけで、
    残せば残すほど、消し忘れた個人情報が積もる。

    files は [{"kind": "jpg"|"png"|"pdf", "data": bytes}, …]。
    """
    files = list(files or [])[:MAX_FILES]
    if not files:
        raise ValueError("ファイルがありません")

    db = load(school)
    per = db.setdefault(aid, {})
    old = per.get(sid) or {}
    _remove_files(school, sid, old.get("files") or [])

    saved = []
    d = paths.submit_dir(school, sid)
    os.makedirs(d, exist_ok=True)
    for i, f in enumerate(files):
        data = f.get("data") or b""
        if not data or len(data) > MAX_BYTES:
            raise ValueError("大きすぎるか、空のファイルがあります")
        kind = f.get("kind")
        if kind not in ("jpg", "png", "pdf"):
            raise ValueError("受け取れない形式です")
        name = "%s-%d.%s" % (_safe(aid), i + 1, kind)
        p = paths.submit_file(school, sid, name)
        with io.open(p, "wb") as fh:
            fh.write(data)
        saved.append({"name": name, "kind": kind, "bytes": len(data)})

    per[sid] = {
        "at": int(now if now is not None else time.time()),
        "files": saved,
        # 出し直したら「見ました」は消える。**前の写真を見た印である。**
        "seen": 0, "by": "", "note": "",
    }
    # 先生が返した添削は残す。**先生の仕事は生徒の出し直しで消えない。**
    if old.get("returned"):
        per[sid]["returned"] = old["returned"]
    save(school, db)
    return per[sid]


def _write_files(school, sid, aid, files, tag=""):
    """ファイルを置いて、目録に書く形を返す。tag は名前に挟む印（返す答案は "r"）。"""
    files = list(files or [])[:MAX_FILES]
    if not files:
        raise ValueError("ファイルがありません")
    saved = []
    d = paths.submit_dir(school, sid)
    os.makedirs(d, exist_ok=True)
    for i, f in enumerate(files):
        data = f.get("data") or b""
        if not data or len(data) > MAX_BYTES:
            raise ValueError("大きすぎるか、空のファイルがあります")
        kind = f.get("kind")
        if kind not in ("jpg", "png", "pdf"):
            raise ValueError("受け取れない形式です")
        name = "%s-%s%d.%s" % (_safe(aid), tag, i + 1, kind)
        p = paths.submit_file(school, sid, name)
        with io.open(p, "wb") as fh:
            fh.write(data)
        saved.append({"name": name, "kind": kind, "bytes": len(data)})
    return saved


@_locked
def put_by_teacher(school, aid, sid, files, by):
    """講師が、対面の生徒の紙を取り込む（回収した答案をスキャン／撮影）。
    生徒が出したのと同じ場所に入り、そのまま評価できる。**見た印も付く**（講師の手にある紙）。
    返した答案（returned）があれば残す。"""
    db = load(school)
    per = db.setdefault(aid, {})
    old = per.get(sid) or {}
    _remove_files(school, sid, old.get("files") or [])
    saved = _write_files(school, sid, aid, files)
    now = int(time.time())
    per[sid] = dict(old, at=now, files=saved, seen=now, by=by, note=old.get("note") or "", origin="teacher")
    save(school, db)
    return per[sid]


@_locked
def put_return(school, aid, sid, files, by, note=None, now=None):
    """講師が添削した答案を返す（赤を入れた紙を撮る／スキャンした PDF）。
    生徒の画面の「先生から」に出る。返し直したら前のものは消す。"""
    db = load(school)
    per = db.setdefault(aid, {})
    got = per.get(sid)
    if not got:
        # 出していない生徒にも返せる（対面で回収した紙など）。空の提出として作る。
        got = per[sid] = {"at": int(time.time()), "files": [], "seen": 0, "by": "", "note": ""}
    _remove_files(school, sid, (got.get("returned") or {}).get("files") or [])
    saved = _write_files(school, sid, aid, files, tag="r")
    now = int(now if now is not None else time.time())
    got["returned"] = {"at": now, "files": saved, "by": by}
    got["seen"] = now
    got["by"] = by
    if note is not None:
        got["note"] = str(note or "")[:400]
    save(school, db)
    return got


@_locked
def prune(school, days=KEEP_DAYS, dry=False, now=None, graded_days=None):
    """古い答案の写真を消す。**台帳の行は残す**（出した・評価・ひとことは記録として要る）。

    300名が週3枚出すと写真は週 300MB ほど増える。評価が済んで半年たった写真を
    講師が開くことはまず無い。消した行には pruned（消した時刻）を置き、
    画面では「写真は保存期間を過ぎました」と出す（出していない扱いにはしない）。
    返した添削も同じく消す。
    """
    now = now or time.time()
    cut = now - days * 86400
    db = load(school)
    n_rows = n_files = 0
    for aid, per in db.items():
        for sid, got in (per or {}).items():
            if not got or got.get("pruned"):
                continue
            at = max(int(got.get("at") or 0), int((got.get("returned") or {}).get("at") or 0))
            if at >= cut:
                # 採点（先生が見た）から graded_days 日たった答案の写真だけ消す。返した添削・評価・ひとことは残す
                seen = int(got.get("seen") or 0)
                if graded_days and got.get("files") and seen and seen < now - graded_days * 86400:
                    n_rows += 1
                    n_files += len(got["files"])
                    if not dry:
                        _remove_files(school, sid, got["files"])
                        got["pruned"] = int(now)
                        got["files"] = []
                continue
            files = all_files(got)
            if not files:
                continue
            n_rows += 1
            n_files += len(files)
            if dry:
                continue
            _remove_files(school, sid, files)
            got["pruned"] = int(now)
            got["files"] = []
            if got.get("returned"):
                got["returned"] = dict(got["returned"], files=[])
    if not dry:
        save(school, db)
    return {"rows": n_rows, "files": n_files}


def all_files(got):
    """1件の、出した答案と返した答案の全ファイル（名前で引くとき用）。"""
    return list((got or {}).get("files") or []) + list(((got or {}).get("returned") or {}).get("files") or [])


@_locked
def mark_seen(school, aid, sid, by, note=None, now=None):
    """講師が見た。ひとことを添えられる。now は見た時刻（秒）。省略で「いま」。
    note が None なら、ひとことには触らない（評価だけの保存が、同時に届いたひとことを消さない）。"""
    db = load(school)
    got = (db.get(aid) or {}).get(sid)
    if not got:
        return None
    got["seen"] = int(now if now is not None else time.time())
    got["by"] = by
    if note is not None:
        got["note"] = str(note or "")[:400]
    save(school, db)
    return got


@_locked
def put_score(school, aid, sid, score, max_=None):
    """過去問の点数（生徒が自分で書く。2026-10-11 本人「点数の記録などもできると良い」）。出したものにだけ添える。
    score が None なら消す。max_ は満点（無ければ None）。"""
    db = load(school)
    got = (db.get(aid) or {}).get(sid)
    if not got:
        return None
    if score is None:
        got.pop("score", None); got.pop("max", None)
    else:
        got["score"] = int(score)
        if max_:
            got["max"] = int(max_)
        else:
            got.pop("max", None)
    save(school, db)
    return got


@_locked
def erase_returned(school, sid):
    """その生徒に返した添削（赤を入れた答案）を、ぜんぶ消す。本人が設定から消す（2026-10-08）。評価・ひとことは残る。"""
    db = load(school)
    n = 0
    for aid, per in db.items():
        got = (per or {}).get(sid)
        if not got or not (got.get("returned") or {}).get("files"):
            continue
        _remove_files(school, sid, got["returned"].get("files") or [])
        got["returned"] = dict(got["returned"], files=[], erased=int(time.time()))
        n += 1
    if n:
        save(school, db)
    return n


@_locked
def drop_student(school, sid):
    """その生徒の答案を、目録ごと消す。退塾の整理で呼ぶ。"""
    db = load(school)
    n = 0
    for aid in list(db.keys()):
        if sid in (db[aid] or {}):
            _remove_files(school, sid, all_files(db[aid][sid]))
            db[aid].pop(sid, None)
            n += 1
            if not db[aid]:
                db.pop(aid, None)
    if n:
        save(school, db)
    # 空になった置き場所も片づける
    try:
        d = paths.submit_dir(school, sid)
        if os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)
    except OSError:
        pass
    return n


def _remove_files(school, sid, files):
    for f in files or []:
        try:
            os.remove(paths.submit_file(school, sid, f.get("name") or ""))
        except (OSError, paths.BadPath):
            pass


def _safe(aid):
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in str(aid))[:60]
