#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""絶対パスの一元管理。

**パスをここ以外で組み立てないこと。** 校舎が増えたとき、
パス組み立てが散らばっていると「ロンドンの画面にNYの生徒が出る」類の
事故が起きる。事故が起きてからでは、どこを見ればいいか分からなくなる。

配置
----
    $MYACADY_ROOT/                     既定は server/data（このMac）
                                       本番は /srv/myacady（AWS）
      index.json                       ログインIDがどの校舎か だけの対応表
      tokens.json                      ログイン中の合言葉（校舎をまたぐ）
      shared/                          全校舎共通の「原本」
        curriculum/<grade>.json        本部カリキュラム（ズレを測る基準）
        materials/                     既定の教材目録
      schools/<school>/                校舎ごと。ここから内側は独立
        school.json                    校舎の設定（表示名・時間帯・学年体系）
        accounts.json                  この校舎のアカウント
        roster.json                    名簿（学年・クラス・座席）
        curriculum.json                校舎の既定＋講師ごとの実施カリキュラム
        materials.json                 校舎の教材ライブラリと講師の採用状況
        assignments.json               宿題
        summary/<sid>.json             講師画面むけの要約（下記）
        progress/<sid>.json            生徒1人分の記録
        audit.log                      誰が何を見たか

**生徒の記録は schools/<school>/ の内側にしか置かない。** 校舎をまたぐのは
index.json（IDと校舎の対応）と tokens.json（セッション）だけで、
どちらにも個人情報は入らない。

要約（summary/）について
------------------------
講師画面が生徒全員分の progress を読むと、300名で20MBを超えて実用にならない。
そこで、進捗を書くたびに1人ぶんの要約だけを書いておく。講師はこれだけを読む。
1人あたり200バイト程度なので、2,000名でも400KB。

**置き場は生徒ごとに1ファイル**（summary/<sid>.json）。
理由は summary_dir() に書いた ―― 1つにまとめると、書くたびに全員ぶんを
読んで書き直すことになる。前の summary.json は、初めて起動したときに
自動で分けられる。

校舎IDについて
-------------
ディレクトリ名は ASCII の slug（london / ny / tokyo）にする。
「ロンドン校」のような日本語は school.json の表示名として持つ。
サーバ上のパスに非ASCIIを混ぜると、バックアップ・シェル・ログの
どこかで必ず文字化けの事故が出る。表示と保管を分けておく。
"""

import json
import os
import re
import threading

try:
    import fcntl
except ImportError:          # Windows など。1プロセスの中の鍵だけになる
    fcntl = None

HERE = os.path.dirname(os.path.abspath(__file__))

# 本番へ移すときに触るのはこの1行だけ。
#   このMac  … 既定（server/data）
#   AWS     … MYACADY_ROOT=/srv/myacady
ROOT = os.path.abspath(os.environ.get("MYACADY_ROOT") or os.path.join(HERE, "data"))

SHARED = os.path.join(ROOT, "shared")
SCHOOLS = os.path.join(ROOT, "schools")
INDEX = os.path.join(ROOT, "index.json")
TOKENS = os.path.join(ROOT, "tokens.json")

SAFE_SCHOOL = re.compile(r"^[a-z][a-z0-9-]{1,23}$")
SAFE_SID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class BadPath(ValueError):
    """校舎IDや生徒IDの形が不正。呼び出し側は 400 を返すこと。"""


# ------------------------------------------------------------------
# 校舎
# ------------------------------------------------------------------
def check_school(school):
    if not school or not SAFE_SCHOOL.match(school):
        raise BadPath("校舎IDの形が不正: %r" % (school,))
    return school


def check_sid(sid):
    if not sid or not SAFE_SID.match(sid):
        raise BadPath("生徒IDの形が不正: %r" % (sid,))
    return sid


def school_dir(school):
    return os.path.join(SCHOOLS, check_school(school))


def school_file(school, name):
    """校舎の中のファイル。name は固定の名前だけを受け付ける。"""
    allowed = {"school.json", "accounts.json", "roster.json", "curriculum.json",
               "materials.json", "assignments.json", "summary.json", "audit.log",
               "ratings.json", "lessons.json", "messages.json",
               # 組み分けテストの日程。総復習テスト対策がこれを見る。
               "exams.json",
               # 最後に刷った対策の紙（教科・版・時刻だけ）。
               # パソコンで刷ってスマホで撮る、をつなぐためのもの。
               "sheets.json",
               # 対策テストで落とした単元。**答案の画像は入らない。**
               "weak.json",
               # 出された宿題の目録（誰がいつ何枚出したか、評価、ひとこと）。
               # 画像そのものは submissions/ の下に別に置く。
               "submissions.json",
               # 特筆事項（講師だけが読む、生徒×教科の短いメモ）。名前は入れない。
               "notes.json",
               # 生徒ごとの宿題の決まり（personal.py）。sid と教材の呼び名だけ。
               "personal.json", "presets.json",
               # 塾内テストの点（scores.py）。sid と点数だけ。名前も表の文字も残さない。
               "scores.json",
               # 提案を出した・見送った記録（insight.py）。提案の出し方を改めるのに使う。
               "insight.json",
               # うまく動かないときの報告（利用者が書いたもの・画面が拾ったエラー）。名前は入れない。
               "reports.json"}
    if name not in allowed:
        raise BadPath("校舎ファイル名が不正: %r" % (name,))
    return os.path.join(school_dir(school), name)


def progress_dir(school):
    return os.path.join(school_dir(school), "progress")


def progress_path(school, sid):
    """生徒1人分の記録。校舎とIDの両方を検査してから組み立てる。

    check_sid を通しているので "../" は入り込めないが、
    念のため組み立てた結果が校舎の中に収まっているかも確かめる。
    パス検査は二重にしておく ―― 片方が将来ゆるめられても、もう片方が残る。
    """
    d = progress_dir(school)
    p = os.path.join(d, check_sid(sid) + ".json")
    if os.path.commonpath([os.path.abspath(p), os.path.abspath(d)]) != os.path.abspath(d):
        raise BadPath("校舎の外を指している: %r" % (sid,))
    return p



def summary_dir(school):
    """講師画面むけの要約を置く所。**生徒ごとに1ファイル。**

        <ROOT>/schools/<校舎>/summary/<sid>.json

    もとは summary.json 1つに全員ぶんを入れていた。生徒が1問答えるたび
    その全員ぶんを読んで書き直していたので、2,000名では書き込みだけで
    29ms、同期1回で36ms かかり、40人が同時に同期すると LOCK が
    1.4秒ふさがった。読むのは速いので、測るまで見えなかった。

    1人1ファイルなら書き込みは 0.1ms で、鍵もいらない
    （別の生徒どうしは、そもそも同じファイルに触らない）。
    """
    return os.path.join(school_dir(school), "summary")


def summary_path(school, sid):
    """生徒1人分の要約。progress_path と同じく二重に検査する。"""
    d = summary_dir(school)
    p = os.path.join(d, check_sid(sid) + ".json")
    if os.path.commonpath([os.path.abspath(p), os.path.abspath(d)]) != os.path.abspath(d):
        raise BadPath("校舎の外を指している: %r" % (sid,))
    return p


def submit_dir(school, sid=None):
    """出された宿題の画像を置く所。

        <ROOT>/schools/<校舎>/submissions/<sid>/<宿題ID>-<n>.<拡張子>

    **生徒の答案そのものである。** 進捗の記録よりずっと重い個人情報で、
    手書きの字も、書き込んだ名前も写る。だから
      ・置き場所を1か所に閉じる（ここ）
      ・退塾から6か月で、進捗と一緒に消える（purge が見る）
      ・読めるのは本人と、そのクラスの担当講師だけ（サーバで判定する）
    """
    d = os.path.join(school_dir(school), "submissions")
    if sid is None:
        return d
    p = os.path.join(d, check_sid(sid))
    if os.path.commonpath([os.path.abspath(p), os.path.abspath(d)]) != os.path.abspath(d):
        raise BadPath("校舎の外を指している: %r" % (sid,))
    return p


# まとめて書き換える前の控え（クラス替え move）。
#
#     <ROOT>/schools/<校舎>/backups/<印>/<校舎ファイル名>
#
# 取り消し（move --undo）は記録（acc["moves"]・宿題の moved）から戻す。控えはその道が
# 壊れていたときの最後の手段。**名簿のハッシュも入るので、長く置かない**（BACKUP_DAYS で消す。
# 退塾した生徒の記録を purge のあとまで残さないため）。
SAFE_STAMP = re.compile(r"^[a-z0-9-]{4,40}$")
BACKUP_DAYS = 60


def backups_dir(school):
    return os.path.join(school_dir(school), "backups")


def backup_path(school, stamp, name):
    """控えの置き場。印（stamp）の形と、ファイル名（school_file と同じ一覧）を確かめてから組み立てる。"""
    if not SAFE_STAMP.match(stamp or ""):
        raise BadPath("控えの印の形が不正: %r" % (stamp,))
    school_file(school, name)
    return os.path.join(backups_dir(school), stamp, name)


def prune_backups(school, days=BACKUP_DAYS, now=None):
    """古い控えを消す。消した印の一覧を返す。"""
    import shutil
    import time as _time
    d = backups_dir(school)
    if not os.path.isdir(d):
        return []
    cut = (now or _time.time()) - days * 86400
    gone = []
    for stamp in sorted(os.listdir(d)):
        p = os.path.join(d, stamp)
        if SAFE_STAMP.match(stamp) and os.path.isdir(p) and os.path.getmtime(p) < cut:
            shutil.rmtree(p, ignore_errors=True)
            gone.append(stamp)
    return gone


# 受け取ってよい形式。**これ以外は拒む。**
# HEIC は iPhone の既定だが、ブラウザで開けない端末があるので入れない
# （写真アプリから送るとき JPEG に変換されるので、実害はない）。
SUBMIT_KIND = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "application/pdf": "pdf",
}


def submit_file(school, sid, name):
    """1枚ぶんの置き場所。name は組み立て側が作る（利用者の文字は使わない）。"""
    if not re.match(r"^[A-Za-z0-9_-]{1,80}\.(jpg|png|pdf)$", name or ""):
        raise BadPath("ファイル名が不正: %r" % (name,))
    d = submit_dir(school, sid)
    p = os.path.join(d, name)
    if os.path.commonpath([os.path.abspath(p), os.path.abspath(d)]) != os.path.abspath(d):
        raise BadPath("置き場所の外を指している: %r" % (name,))
    return p

def shared_file(*parts):
    p = os.path.abspath(os.path.join(SHARED, *parts))
    if os.path.commonpath([p, os.path.abspath(SHARED)]) != os.path.abspath(SHARED):
        raise BadPath("shared の外を指している: %r" % (parts,))
    return p


def list_schools():
    """存在する校舎IDを並べる。school.json のあるものだけを校舎とみなす。"""
    if not os.path.isdir(SCHOOLS):
        return []
    out = []
    for name in sorted(os.listdir(SCHOOLS)):
        if SAFE_SCHOOL.match(name) and os.path.isfile(
                os.path.join(SCHOOLS, name, "school.json")):
            out.append(name)
    return out


def ensure_school(school):
    """校舎のディレクトリを作る。既にあれば何もしない。"""
    check_school(school)
    os.makedirs(progress_dir(school), exist_ok=True)
    return school_dir(school)


def ensure_root():
    os.makedirs(SCHOOLS, exist_ok=True)
    os.makedirs(os.path.join(SHARED, "curriculum"), exist_ok=True)
    os.makedirs(os.path.join(SHARED, "materials"), exist_ok=True)


# ------------------------------------------------------------------
# ログインIDから校舎を引く
# ------------------------------------------------------------------
# ------------------------------------------------------------------
# 鍵 ―― 「読んで、直して、書く」のあいだに、誰にも割り込ませない
# ------------------------------------------------------------------
class Guard(object):
    """このデータ置き場（ROOT）にひとつだけの鍵。**スレッドの間でも、プロセスの間でも効く。**

    前は、サーバの中に鍵が7つ（tube_server・lessons・messages・notes・personal・
    presets・scores）あり、どれも1つのプロセスの中でしか効かなかった。
    サーバが動いている横でコマンド（passwd・move・roster-import…）を流すと、
    両方が同じファイルを「読んで、直して、書く」ので、後から書いたほうが
    先に書いたほうを消す（コマンド同士の隙間）。

    ここでは、スレッドの鍵（何度でも入れる RLock）の内側で、ROOT/.lock に
    flock を掛ける。鍵は1つなので、取る順番の食い違いで固まることが無い。
    同じスレッドが重ねて入ってよい（深さを数え、いちばん外で外す）。
    """

    def __init__(self):
        self._t = threading.RLock()
        self._depth = 0
        self._fd = None

    def __enter__(self):
        self._t.acquire()
        try:
            if self._depth == 0 and fcntl is not None:
                try:
                    os.makedirs(ROOT, exist_ok=True)
                    self._fd = os.open(os.path.join(ROOT, ".lock"),
                                       os.O_RDWR | os.O_CREAT, 0o600)
                    fcntl.flock(self._fd, fcntl.LOCK_EX)
                except OSError:
                    # 置き場が読み取り専用など。プロセスの中の鍵だけで進む。
                    if self._fd is not None:
                        try:
                            os.close(self._fd)
                        except OSError:
                            pass
                    self._fd = None
            self._depth += 1
        except BaseException:
            self._t.release()
            raise
        return self

    def __exit__(self, *exc):
        try:
            self._depth -= 1
            if self._depth == 0 and self._fd is not None:
                fd, self._fd = self._fd, None
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)
        finally:
            self._t.release()
        return False

    # threading.Lock と同じ呼び方でも使えるように
    def acquire(self):
        self.__enter__()
        return True

    def release(self):
        self.__exit__(None, None, None)


GUARD = Guard()

# 書いた直後に電源が落ちても、前の中身か新しい中身のどちらかが必ず残るようにする
# （fsync してから名前を付け替える）。検査やデモの組み立てで遅いときは MYACADY_FSYNC=0。
FSYNC = os.environ.get("MYACADY_FSYNC", "1") != "0"


def _write_atomic(path, obj, **dump):
    """一時ファイルに書き、確かめてから、名前を付け替える。

    一時ファイルの名前は**書き手ごとに別**（プロセス番号＋スレッド番号）。
    前は `path + ".tmp"` の1つで、2人が同時に書くと同じ一時ファイルに
    混ざって書き、壊れた JSON が本物の名前に付け替えられる余地があった。
    """
    tmp = "%s.%d.%d.tmp" % (path, os.getpid(), threading.get_ident())
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1, **dump)
            f.flush()
            if FSYNC:
                os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


_SECRET = []


def secret():
    """この置き場だけの秘密（32バイト）。無ければ作る。ROOT/.secret（持ち主だけが読める）。

    個人の情報ではない。無いIDにも同じ形の返事をするための塩づくりに使う（tube_server.fake_salt）。
    """
    if _SECRET:
        return _SECRET[0]
    p = os.path.join(ROOT, ".secret")
    with GUARD:
        try:
            with open(p, "rb") as f:
                raw = f.read()
        except (IOError, OSError):
            raw = b""
        if len(raw) < 32:
            ensure_root()
            raw = os.urandom(32)
            tmp = "%s.%d.tmp" % (p, os.getpid())
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
            os.replace(tmp, p)
    _SECRET.append(raw)
    return raw


def read_index():
    """{ログインID: 校舎ID}。個人情報は入れない。"""
    try:
        with open(INDEX, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, ValueError):
        return {}


def write_index(idx):
    ensure_root()
    _write_atomic(INDEX, idx, sort_keys=True)


def school_of_login(login_id):
    return read_index().get(login_id)


def bind_login(login_id, school):
    """ログインIDを校舎に結びつける。既に別の校舎に使われていたら拒む。

    ここで弾いておかないと、同じIDが2校舎にできて
    「ログインはできるが自分の宿題が出てこない」という追いにくい不具合になる。
    """
    check_school(school)
    with GUARD:
        idx = read_index()
        cur = idx.get(login_id)
        if cur and cur != school:
            raise BadPath("ログインID %s は既に校舎 %s で使われている" % (login_id, cur))
        idx[login_id] = school
        write_index(idx)


def unbind_login(login_id):
    with GUARD:
        idx = read_index()
        if login_id in idx:
            del idx[login_id]
            write_index(idx)


# ------------------------------------------------------------------
# 読み書き（壊れないように別名で書いてから差し替える）
# ------------------------------------------------------------------
def load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, ValueError):
        return default


def save(path, obj):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    _write_atomic(path, obj)


if __name__ == "__main__":
    print("MYACADY_ROOT =", ROOT)
    schools = list_schools()
    if not schools:
        print("校舎はまだ1つもない。 python3 server/tube_server.py school-add london 'ロンドン校'")
    for s in schools:
        meta = load(school_file(s, "school.json"), {})
        acc = load(school_file(s, "accounts.json"), {})
        n = len([a for a in acc.values() if a.get("role") == "student"])
        print("  %-10s %-20s 生徒 %d名" % (s, meta.get("name", "?"), n))
