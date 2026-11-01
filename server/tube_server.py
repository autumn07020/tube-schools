#!/usr/bin/env python3
"""
Tube for Schools — 仮サーバ

このMacの上で動く、試用のためのサーバ。標準ライブラリだけで書いてある
（インストール不要）。app/ を配信しつつ、/api で認証と進捗の保管を行う。

    python3 tube_server.py seed      テスト用アカウントを作る
    python3 tube_server.py serve     サーバを起動する
    python3 tube_server.py list      アカウント一覧
    python3 tube_server.py add       アカウントを1つ足す
    python3 tube_server.py passwd    パスワードを付け替える
    python3 tube_server.py rm        アカウントを消す
    python3 tube_server.py move      クラス替え（組み分けのあと。記録はそのまま。--undo で戻せる）

------------------------------------------------------------------
これは「仮」であることの意味 ―― 本番に持ち込む前に必ず読むこと
------------------------------------------------------------------
* 既定で 127.0.0.1 にしか口を開けない。このMacの中からしか繋がらない
* TLS が無い。--host を変えて外に開くと、パスワードが平文で流れる
* 本物の生徒の氏名や記録をここに入れない。動作確認のための道具である

保管の形（生徒ごとに1ファイル。これがそのまま「個人で分割して保存」の実体）

    server/data/accounts.json          ID・パスワードハッシュ・所属
    server/data/tokens.json            ログイン中の合言葉
    server/data/assignments.json       宿題の指示（範囲・期限・対象）
    server/data/progress/<sid>.json    生徒1人分の進捗（宿題の達成もここ）

バックアップは data/ をコピーするだけでよい。

------------------------------------------------------------------
宿題について
------------------------------------------------------------------
サーバが持つのは「どの冊子の、何番から何番までを、誰に、いつまで」だけ。
単語そのもの（見出し語・訳語）は持たない。市販教材の語の選定・訳語は
編集著作物として保護されるため、番号で指す方式にしてある。
生徒は冊子を見て思い出し、アプリで自己採点する。
"""

import argparse
import base64
import binascii
import functools
import gzip
import io
import hashlib
import hmac
import json
import math
import os
import re
import shutil
import secrets
import sys
import threading
import time
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

import paths
import lessons
import courses
import weak
import submissions as SUB
import notes as NOTES
import ratescale                                # 紙の宿題の評価（5段階）
import personal as PERSONAL                     # 生徒ごとの宿題の決まり
import messages as MESSAGES                     # 保護者から講師へのメッセージ
import pdfout                                   # 答案を A4 の PDF に（印刷して赤を入れる）
import presets as PRESETS                       # 講師が登録する「足す宿題の型」
import syllabus as SYLLABUS                   # noqa: E402
import curriculum_source as SOURCE            # noqa: E402
import scores as SCORES                         # 塾内テストの点
import insight as INSIGHT                       # 理解度と提案
import outbox as OUTBOX
import admin as ADMIN                           # 管理ページの口（席・講師・担当・報告）
import join as JOIN                             # 初回登録（招待コードから、保護者が口座を作る）
import scram as SCRAM                           # 入るときに合言葉そのものを送らない（計算だけ）
import retire as RETIRE                         # 3か月使われない口座の破棄（毎日の片づけ）
import exams as examcal                         # noqa: E402
import examprep                                 # noqa: E402

# 苦手単元の再テストの上限。**1回で終わる量にする。**
# 苦手をぜんぶ並べると60問になり、本番前の数日で終わらない。
# 終わらない課題は、やらない課題と同じである。
RETEST_MAX = 20
import prepsheet                                # noqa: E402
import reference_curriculum as refcur
from paths import BadPath

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(os.path.dirname(HERE), "app")
DATA = paths.ROOT
MAX_RANGE = 500        # 1つの宿題で出せる番号の上限。桁を打ち間違えたときの歯止め

# 「定着した」とみなす復習間隔と、「つまずいている」とみなす失敗回数。
# クライアント（app/curriculum.js）と同じ値にしておくこと。
# ここを変えたら rebuild-summary を走らせる。
# 要約に持たせる直近の日数。画面の点は7つだが、
# 「14日で何日やったか」を出すので14日ぶん要る。
RECENT_DAYS = 14

MATURE_DAYS = 21
STUCK_LAPSES = 3

# ------------------------------------------------------------------
# 教材の「解く場所」
#
# 併走（紙9割の生徒とアプリ10割の生徒が同居する状態）を、
# **講師にも生徒にも追加の入力をさせずに**成立させるための要。
#
# 経路は宿題ごとに指定させない。教材の性質として1度だけ決める。
# 漢字の書き取りは誰が出しても紙だし、単語帳は誰が出してもアプリで解ける。
# 講師は今までどおり教材を選ぶだけでよく、生徒は何も入力しない。
#
# app/content/manifest.js の booklets と同じ内容を持つ。
# 経路はサーバが決める ―― 画面から送られてきた route を信じない。
# 信じると、打ち間違いや古い画面のせいで、紙の宿題が「未提出」に化ける。
# ------------------------------------------------------------------
# 教科を必ず入れておく。subject_of_assignment がここを読むのに
# 入っていなかったので、手で出した宿題の教科がいつも空だった。
BUILTIN_MATERIALS = {
    "myvocab":     {"mode": "app",   "name": "My英単語帳",
                    "short": "単語帳", "subject": "english",
                    "alias": ["英単語帳", "単語帳", "My英単語帳"]},
    "kanji-write": {"mode": "paper", "name": "漢字 書き取り",
                    "short": "漢字書", "subject": "japanese",
                    "alias": ["漢字の書き取り", "漢字ドリル"]},
    "keisan":      {"mode": "paper", "name": "計算ドリル",
                    "short": "計算ド", "subject": "math",
                    "alias": ["計算ドリル"]},
    "wa-text":     {"mode": "paper", "name": "塾テキスト（英語）",
                    "short": "テキスト", "subject": "english",
                    "alias": ["塾テキスト"]},
}


def subject_of_source(school, src):
    """教材IDから教科を引く。

    アプリの中の教材は "english/core" のように **教科/名前** の形で
    並んでいる（app/content/manifest.js）。斜線の前が教科である。
    校舎で登録した教材は subject を持っている。
    """
    if "/" in src:
        return src.split("/")[0]
    m = (materials(school).get(src) or BUILTIN_MATERIALS.get(src) or {})
    return m.get("subject") or ""


def source_and_range(school, text):
    """宿題の文から (教材ID, はじめ, おわり) を読む。

    講師には教材IDを選ばせない ―― 手間を増やさないため。
    そのかわり、いつも書いている文（「My英単語帳 No.1-50 と テキストp.8-11」）
    から機械が読む。

    **教材名の直後にある番号だけを拾う。** 文中の最初の数字を拾うと
    「My英単語帳 No.1-50 と テキストp.8-11」から 8-11 を取ることがあり、
    生徒には別の範囲が出てしまう。

    どの教材か分からなければ ('', 0, 0) を返す。
    呼ぶ側はそれを紙の宿題として扱うこと ―― 素性の分からないものに
    「やる」ボタンを出すと、押した先が「NO.0 の 0ばん」になる。
    """
    if not text:
        return ("", 0, 0)
    table = dict(BUILTIN_MATERIALS)
    for mid, m in (materials(school) or {}).items():
        table.setdefault(mid, {})
        table[mid] = dict(table[mid], **{k: v for k, v in m.items() if v})
    best = None
    for mid, m in table.items():
        names = [mid, m.get("name") or "", m.get("short") or ""]
        names += list(m.get("alias") or [])
        for nm in names:
            # 2文字までの名は使わない。「計算」は理科の「計算問題1-6」にも
            # 当たってしまい、別の教材の宿題に計算ドリルの名が付く。
            if not nm or len(nm) < 3:
                continue
            at = text.lower().find(nm.lower())
            if at < 0:
                continue
            got = lessons.parse_range(text[at + len(nm):at + len(nm) + 40])
            if not got:
                continue
            # 同じ文に複数出てきたら、先に書いてあるほうを主とみなす
            if best is None or at < best[0]:
                best = (at, mid, got[0], got[1])
    if best is None:
        return ("", 0, 0)
    return (best[1], best[2], best[3])


BULK_MAX = 25          # 1回の一括登録で作れる人数。ハッシュ化に0.16秒/件かかる


def subject_ids():
    """教科IDの並び。app/content/manifest.js を典拠にする。
    サーバ側に二重に持たない ―― 二重に持つと必ず食い違う。"""
    try:
        with open(os.path.join(APP_DIR, "content", "manifest.js"),
                  encoding="utf-8") as f:
            src = f.read()
        m = re.search(r"subjects:\s*\[(.*?)\]", src, re.S)
        if m:
            return re.findall(r"id:'(\w+)'", m.group(1))
    except (IOError, OSError):
        pass
    return ["english", "science", "social", "math", "japanese"]


def gradeOfClass(school, class_id):
    """クラスIDから学年を引く。進度に登録が無ければ、IDの頭を学年とみなす。"""
    for c in (curriculum(school).get("classes") or []):
        if c.get("id") == class_id:
            return c.get("grade") or ""
    m = re.match(r"^([a-z]+\d+)", class_id or "")
    return m.group(1) if m else ""


def materials_file(school):
    return paths.load(paths.school_file(school, "materials.json"), {})


def materials(school):
    """校舎の教材一覧。校舎が足したものが既定に重なる。

    **原本は校舎が持つ。** 講師が消しても校舎から消えない ――
    消えるのは「その講師の一覧から」だけ（下の adopted を参照）。
    講師が誤って消して、他の講師の宿題が出せなくなる事故を防ぐ。
    """
    out = {mid: dict(m) for mid, m in BUILTIN_MATERIALS.items()}
    for mid, m in (materials_file(school).get("items") or {}).items():
        if isinstance(m, dict):
            out[str(mid)[:40]] = m
    return out


def adopted(school, teacher_sid):
    """その講師が「使う」と決めた教材のID。

    空（一度も選んでいない）なら、校舎の全教材を返す。
    初めて開いた講師の画面が空っぽだと、故障だと思われるため。"""
    f = materials_file(school)
    picked = ((f.get("adopted") or {}).get(teacher_sid))
    if not picked:
        return None                      # None は「ぜんぶ」の意
    return [str(x)[:40] for x in picked][:80]


def set_adopted(school, teacher_sid, ids):
    with LOCK:
        f = materials_file(school)
        f.setdefault("items", {})
        f.setdefault("adopted", {})
        f["adopted"][teacher_sid] = [str(x)[:40] for x in (ids or [])][:80]
        paths.save(paths.school_file(school, "materials.json"), f)


def adopted_by_course(school, teacher_sid):
    """コースごとに選び直した教材（2026-10-08 の見本 T20）。コースの鍵 → ID の列。
    無いコースは講師の一覧（adopted）に従う。"""
    f = materials_file(school)
    d = ((f.get("adoptedByCourse") or {}).get(teacher_sid)) or {}
    return {str(k)[:40]: [str(x)[:40] for x in (v or [])][:80]
            for k, v in d.items() if isinstance(v, list)}


def set_adopted_course(school, teacher_sid, course, ids):
    with LOCK:
        f = materials_file(school)
        f.setdefault("items", {})
        f.setdefault("adoptedByCourse", {}).setdefault(teacher_sid, {})
        f["adoptedByCourse"][teacher_sid][str(course)[:40]] = [str(x)[:40] for x in (ids or [])][:80]
        paths.save(paths.school_file(school, "materials.json"), f)


# ------------------------------------------------------------------
# 紙の宿題の評価
#
# 講師がノートを見て4段階でつける。**任意である。**
# 全学年・全教科で採用されるわけではないし、同じ講師でも
# つける週とつけない週がある。それで困らない作りにする。
#
# 生徒の記録（progress）とは別のファイルに置く。理由は2つ。
#   1. 生徒が書くもの（やった事実）と、講師が書くもの（見立て）を混ぜない
#   2. 講師に生徒の記録への書き込み権を与えずに済む
#
# **「未評価」を状態として持たない。** 無いものは無い、として扱う。
# 未評価に印を付けると、3人つけた裏で残り27人が「欠けている」ように見え、
# 評価する講師ほど自分のクラスが悪く見える。それでは誰もつけなくなる。
# ------------------------------------------------------------------
# 評価は5段階（ratescale.py）。前の4段階（0〜3）で付けたものは、読むときに読み替える。
RATING_LEVELS = ratescale.LEVELS
# 「がんばろう」以下（と、出ていない）を、気にかける合図とみなす。
RATING_LOW = ratescale.LOW


def ratings(school):
    return paths.load(paths.school_file(school, "ratings.json"), {})


def save_ratings(school, db):
    paths.save(paths.school_file(school, "ratings.json"), db)


def ratings_for_student(school, sid, db=None):
    """その生徒に付いている評価を、宿題IDごとに返す。"""
    db = ratings(school) if db is None else db
    out = {}
    for aid, per in db.items():
        r = (per or {}).get(sid)
        if r:
            out[aid] = r
    return out


def graded_of(school, source):
    """その教材の宿題は、採点するか。

    **既定は採点する。** 出したものは見る、が基本である。
    ただし教材によっては「出すだけ」でよいものがある ――
    計算ドリルや漢字の書き取りのように、毎回やることが決まっていて、
    1枚ずつ評価を付ける値打ちがないもの。

    出すだけにすると、その宿題は
      ・講師の「採点する」の束に入らない
      ・提出率の計算にも入らない（観測していないので数えない）
    という扱いになる。**数えないものを 0% と出さない**ためである。
    """
    m = materials(school).get(source) or {}
    return m.get("graded") is not False


def route_of(school, source):
    """その教材はどこで解くか。

    アプリの中の教材は、source に pack のID（"english/core" のように斜線入り）か、
    冊子の目録（BUILTIN_MATERIALS）のIDが入る。校舎の教材台帳にあれば、その mode。
    **どれでもない教材は紙とみなす。** 前は「知らなければアプリ」で、
    台帳に載せ忘れた市販教材（GRIT など）に「やる」ボタンが出て、
    押した先に中身が無かった。
    """
    m = materials(school).get(source)
    if m:
        return "paper" if m.get("mode") == "paper" else "app"
    return "app" if "/" in str(source or "") else "paper"

# 校舎を指定せずに動かしたときの既定。CLI と移行スクリプトが使う。
# サーバの処理系では **必ずアカウントから校舎を引く**。ここは使わない。
DEFAULT_SCHOOL = os.environ.get("MYACADY_SCHOOL", "london")

# 時刻は校舎の時間帯で数える（授業の開始時刻が宿題の期限になるため）。
# 本番の機械が UTC だと、夏時間のあいだ期限が1時間ずれる。
# いまは校舎がロンドン1つなので、プロセス全体を Europe/London にそろえる。
# 時間帯の違う校舎を足すときは、ここを校舎ごとの計算に直すこと。
if not os.environ.get("TZ"):
    os.environ["TZ"] = "Europe/London"
    time.tzset()

# デモ用の合言葉を画面に出してよいか。--demo を付けたときだけ真になる。
# 本番では付けないので /api/demo は 404 を返し、画面にもボタンが出ない。
DEMO = {"on": False, "accounts": []}

# 合言葉の寿命。講師を極端に短くしてあるのは、講師の合言葉ひとつで
# クラス全員の記録が読めるから ―― 事故ったときの被害範囲が違う。
TOKEN_TTL = {"student": 60 * 60 * 24 * 14,   # 14日
             "teacher": 60 * 60 * 12,        # 12時間
             # 管理者は、席と講師と担当を作り変えられる。いちばん短くする。
             "admin": 60 * 60 * 8}           # 8時間
# 管理者の合言葉は、触らないまま置くと 30分で切れる（開いたままの画面を、あとから来た人に使わせない）。
ADMIN_IDLE = 30 * 60
# 引き換え（オンラインの生徒に、合言葉そのものを送らずに席を渡す）。
#   管理者が「1回だけ使える言葉」を作って送る → 生徒がそれで入る → 生徒の端末が本物の合言葉を作り、
#   その値（scram の verifier）だけを届ける → 引き換えの言葉は、そこで使えなくなる。
# 引き換えの言葉で入った印（token）は、引き換える口（/api/claim）にしか使えず、30分で切れる。
CLAIM_DAYS = 7                 # 引き換えの言葉が使える日数
CLAIM_TOKEN_TTL = 30 * 60
# 役割。seat は「まだ誰にも渡していない席」（中身は生徒と同じ形。はじめて入ったとき、
# または管理者が「使う」を押したときに student になる）。**生徒を数える所は role == "student" で
# 数えているので、seat は名簿にも宿題の受け取り手にも成績にも出ない**（30席ぶんの幽霊を作らない）。
ROLES = ("student", "teacher", "seat", "admin")
# 置き場にひとつだけの鍵（スレッドにもプロセスにも効く。paths.Guard）。
# サーバが動いている横でコマンドを流しても、「読んで・直して・書く」が重ならない。
LOCK = paths.GUARD
# 自動発行の鍵。講師の格子と生徒の一覧が同時に開くと、同じ回を二度出す。
PUBLISH_LOCK = threading.Lock()

SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,31}$")
SAFE_SID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
# 呼び名（seat）。初回登録の口座は ID そのもの（s-042）なので、線（-）も通す。
SAFE_SEAT = re.compile(r"^[A-Za-z0-9-]{1,8}$")


# ------------------------------------------------------------------
# 保管
# ------------------------------------------------------------------
# ------------------------------------------------------------------
# 保管の入口
#
# 校舎をまたぐ読み書きを構造的に起こせなくするため、
# 生徒に関わるものは **すべて school を第1引数に取る**。
# 引数を省略できるようにはしないこと ―― 省略できると、いつか省略される。
# ------------------------------------------------------------------
def ensure_dirs(school=None):
    paths.ensure_root()
    if school:
        paths.ensure_school(school)


load_json = paths.load
save_json = paths.save


def accounts(school):
    return paths.load(paths.school_file(school, "accounts.json"), {})


def save_accounts(school, db):
    paths.save(paths.school_file(school, "accounts.json"), db)


def assignments(school):
    return paths.load(paths.school_file(school, "assignments.json"), {})


def save_assignments(school, db):
    paths.save(paths.school_file(school, "assignments.json"), db)


def school_meta(school):
    return paths.load(paths.school_file(school, "school.json"), {})


def school_name(school):
    return school_meta(school).get("name") or school


def school_code(school):
    """ログインIDの頭に付ける1〜2文字。校舎をまたいでIDを一意にするためのもの。

    ロンドン校の中2Aの1番なら `lj2a01`。6文字なので小4でも打てる。
    ここを校舎名や氏名に由来させないこと ―― IDから人が割れてはいけない。"""
    return school_meta(school).get("code") or school[:1]


def tokens():
    """合言葉は校舎をまたぐ。中身はログインIDと校舎IDだけで、個人情報は無い。"""
    return paths.load(paths.TOKENS, {})


def save_tokens(store):
    paths.save(paths.TOKENS, store)


def token_key(tok):
    """合言葉そのものはファイルに書かない。tokens.json が漏れても、
    そこに書いてある文字列では成りすませないようにする。"""
    return hashlib.sha256(tok.encode("utf-8")).hexdigest()


def audit(school, actor, action, target="", extra=""):
    """誰がいつ何を見たか。個人情報を扱うなら、これが無いと
    「見ていない」も「見た」も証明できない。追記しかしない。
    校舎ごとに分ける ―― 監査記録も校舎の外に出さない。"""
    try:
        paths.ensure_school(school)
        with open(paths.school_file(school, "audit.log"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": int(time.time()), "actor": actor,
                                "action": action, "target": target,
                                "extra": extra}, ensure_ascii=False) + "\n")
    except (IOError, BadPath):
        pass


def progress_path(school, sid):
    return paths.progress_path(school, sid)


# ------------------------------------------------------------------
# 講師画面むけの要約
#
# 講師が担当生徒の progress を全部読むと、300名で20MBを超えて実用にならない。
# （SPEC.md に「250名で23MB」と実測が残っている。これがその対処）
# 進捗を書くたびに、その1人ぶんの要約だけを summary/<sid>.json に書いておく。
# 1人あたり200バイト程度なので、300名でも60KB で済む。
#
# 要約は progress から**いつでも作り直せる**派生データである。
# 壊れたら rebuild-summary で作り直せばよく、原本ではない。
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# 最後に刷った紙
# ------------------------------------------------------------------
# パソコンで刷って、スマホで撮る。この2台をつなぐのに、合言葉も
# QRコードも要らない ―― **同じアカウントなのだから、聞けばよい。**
#
# 置くのは教科と版と時刻、そして**刷った問題の並び**だけ。
# 答案の画像は関わらない。
#
# 並びまでおぼえるのは、読むときに組み直させないためである。
# 対策の並びは examprep.build がその日の種で混ぜ、まちがえた問題を
# 先頭に入れ、校舎全体の難しさで並べ替えて決まる。つまり
# **刷ってから撮るまでのあいだに、本人が1問答えただけでも、
# 同級生が答えただけでも、日付が変わっただけでも、別の並びになる。**
# ずれた並びで採点すると、点数が狂うだけでは済まない ――
# 読み取り結果は問題IDごとにサーバへ送られるので、
# **見てもいない単元に「まちがえた」が積もり、苦手の蓄積が汚れる。**
SHEET_TTL = 6 * 3600        # 6時間。それより前のものは「今のではない」


def sheet_memo_path(school):
    return paths.school_file(school, "sheets.json")


def remember_sheet(school, sid, subject, tier, ids=None):
    with LOCK:
        db = paths.load(sheet_memo_path(school), {}) or {}
        now = int(time.time())
        cap = prepsheet.SHEET["cols"] * prepsheet.SHEET["rows"]
        db[sid] = {"subject": subject or "", "tier": tier, "at": now,
                   "ids": [str(i) for i in (ids or [])][:cap]}
        # 古い分は捨てる。ためておく意味がないうえ、
        # 何百人ぶんもたまると読み書きが重くなる。
        for k in [k for k, v in db.items()
                  if now - int((v or {}).get("at") or 0) > SHEET_TTL]:
            db.pop(k, None)
        paths.save(sheet_memo_path(school), db)


def last_sheet(school, sid):
    v = (paths.load(sheet_memo_path(school), {}) or {}).get(sid) or {}
    if not v or int(time.time()) - int(v.get("at") or 0) > SHEET_TTL:
        return None
    return v


def apply_sheet_memo(school, sid, grade, got, paper):
    """**刷った紙が先。** 読むときに問題を組み直さない。

    カメラの採点は paper[教科] の並びでおこなう。その並びを毎回
    組み直すと、刷った紙とかみ合わない（なぜかは SHEET_TTL の所に書いた）。
    だから、おぼえておいた並びでそっくり置き換える。

    紙にあってアプリの組み立てに無い問題は、**足してから**返す。
    足さないと画面側が id を引けずに落とし、問題数がずれて
    1問目から全部ずれる ―― いちばん気づきにくい壊れ方である。

    教材が入れ替わって1問でも見つからないときは、何もしない。
    **ずれた紙で採点するより、採点できないほうがましである。**
    """
    memo = last_sheet(school, sid) or {}
    ids = memo.get("ids") or []
    sub = memo.get("subject") or ""
    if not ids or sub not in paper:
        return paper
    st = None
    for x in (got.get("sets") or []):
        if x.get("subject") == sub:
            st = x
            break
    if st is None:
        return paper
    have = {x["id"] for x in (st.get("items") or [])}
    miss = [i for i in ids if i not in have]
    if miss:
        pool = {x["id"]: x for x in examprep.pack_items(sub, grade)}
        if any(i not in pool for i in miss):
            return paper
        st["items"] = list(st.get("items") or []) + [pool[i] for i in miss]
        st["n"] = len(st["items"])
        st["minutes"] = int(round(
            sum(examprep.sec_of(x) for x in st["items"]) / 60.0))
        got["minutes"] = sum(x.get("minutes") or 0 for x in got["sets"])
    paper[sub] = list(ids)
    return paper


# 要約の控え。**変わったファイルだけ読み直す。**
#
# 生徒ごとに分けたぶん、講師が全員ぶんを読むときは 2,000回ファイルを
# 開くことになる（測ったら 54ms）。毎回それをやる理由はない ――
# 一覧を取り直して、日付か大きさが変わったものだけ読み直せばよい。
_SUMM = {}                                  # 校舎 → {"stat": {...}, "rows": {...}}


def ensure_summary_dir(school):
    """1つだった要約を、生徒ごとに分ける。**起動後1回だけ走る。**

    そろってから見えるように、別の名前で作ってから置き換える。
    途中で落ちても、中途半端な置き場が残らない。
    """
    d = paths.summary_dir(school)
    if os.path.isdir(d):
        return d
    with LOCK:
        if os.path.isdir(d):
            return d
        old = paths.load(paths.school_file(school, "summary.json"), {}) or {}
        tmp = d + ".new"
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp, exist_ok=True)
        for sid, row in (old or {}).items():
            try:
                paths.save(os.path.join(tmp, paths.check_sid(sid) + ".json"), row)
            except paths.BadPath:
                continue
        os.rename(tmp, d)
        sys.stderr.write("  要約を生徒ごとに分けました: %s（%d名）\n"
                         % (school, len(old or {})))
    return d


def summary(school):
    """全員ぶんの要約。**変わったぶんだけ読み直す。**"""
    d = ensure_summary_dir(school)
    c = _SUMM.get(school) or {"stat": {}, "rows": {}}
    stat, rows = c["stat"], c["rows"]
    now = {}
    try:
        for e in os.scandir(d):
            if e.name.endswith(".json"):
                st = e.stat()
                now[e.name] = (st.st_mtime_ns, st.st_size)
    except OSError:
        return dict(rows)
    for name, key in now.items():
        if stat.get(name) != key:
            rows[name[:-5]] = paths.load(os.path.join(d, name), {}) or {}
    for name in stat:
        if name not in now:
            rows.pop(name[:-5], None)
    _SUMM[school] = {"stat": now, "rows": rows}
    return dict(rows)


def drop_summary(school, sid):
    """退塾した生徒の要約を消す。"""
    try:
        os.remove(paths.summary_path(school, sid))
    except (OSError, paths.BadPath):
        pass


def summarise_one(rec, asg_for_student, now=None, rated=None):
    """生徒1人分の記録から、講師が見たい数字だけを取り出す。

    ここでいちばん大事なのは share（アプリで解く割合）である。

    紙9割・アプリ1割の生徒は、アプリの数字だけ見ると
    「ほとんど何もしていない子」に見える。**紙でちゃんとやっている生徒ほど、
    システム上は不真面目に見える。** 導入初期にこれが起きたら、
    その講師は二度と使わない。

    そこで、出された宿題のうち何割がアプリで解ける教材だったかを数え、
    数字に必ず添える。誰にも入力させずに出せる ―― 講師が教材を選んだ時点で、
    その宿題がアプリで観測できるかどうかは決まっているからである。

    紙の宿題は due にも overdue にも数えない。
    アプリが見ていないだけで、やっていないとは限らない。
    """
    now = now or int(time.time())
    rec = rec or {}
    cards = rec.get("cards") or {}
    hw = rec.get("hw") or {}
    hist = rec.get("hist") or {}

    # 講師の画面が出す3つの数（定着・つまずき・最後にやった日）は、
    # ここで1度だけ数える。講師が画面を開くたびに全員分を数え直さない。
    # 記録の1枚は [iv, ef, due, reps, lapse, seen, known]（app/js/store.js）
    last = mature = stuck = 0
    answered = correct = touched = 0
    for c in cards.values():
        if not isinstance(c, list) or len(c) < 6:
            continue
        if (c[0] or 0) >= MATURE_DAYS:
            mature += 1
        if len(c) > 4 and (c[4] or 0) >= STUCK_LAPSES:
            stuck += 1
        last = max(last, int(c[5] or 0))
        # 正答率のもと。**答えた分だけを分母にする。**
        # 「定着した項目 ÷ 単元ぜんぶ」だと、始めて2週間の生徒は
        # 間隔が21日に届かないので必ず 0% と出る。
        reps = int(c[3] or 0) if len(c) > 3 else 0
        if reps:
            touched += 1
            answered += reps
            correct += max(0, reps - (int(c[4] or 0) if len(c) > 4 else 0))
    # 直近14日、やった日を1文字ずつ並べた文字列。左端がきょう。
    #   '.' … 何もしていない   '1'〜'9' … その日に解いた量（9で頭打ち）
    #
    # 前は {"2026-08-07": 17, …} という辞書だった。日付キーだけで
    # 1人180バイトあり、300名で 54KB がキーの文字で埋まる。
    # 画面が使うのは「その日やったか」と「直近14日で何日やったか」の
    # 2つだけなので、位置で表す。
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    recent = []
    daily7 = 0
    week = 0
    for d in range(RECENT_DAYS):
        k = time.strftime("%Y-%m-%d", time.localtime(now - d * 86400))
        day = hist.get(k) or {}
        n = int(day.get("n") or 0)
        recent.append("." if not n else str(min(9, max(1, n // 5 + 1))))
        if d < 7:
            # 直近7日に解いた **problem の実数**。recent は 9 で頭打ちに
            # 潰してあるので、そこからは復元できない。競い合いに使う数は
            # 丸めずに持つ ―― 「180問と182問」の差が見えないと勝負にならない。
            week += n
            if day.get("done"):
                daily7 += 1
    recent = "".join(recent)

    rated = rated or {}
    # 直近7回の宿題を、期限の古い順に並べて「出したか」を1と0で持つ。
    # 期限がまだ来ていないものは数えない ―― 出していなくて当たり前。
    hw7 = []
    past = sorted([a for a in (asg_for_student or [])
                   if (a.get("dueAt") or 0) / 1000.0 <= now],
                  key=lambda a: a.get("dueAt") or 0)[-7:]
    for a in past:
        st = hw.get(a["id"]) or {}
        if (a.get("route") or "app") == "paper":
            # 紙は評価が付いていれば「出した」。アプリからは見えない。
            hw7.append(1 if (rated or {}).get(a["id"]) else 0)
        else:
            hw7.append(1 if st.get("completedAt") else 0)

    due = overdue = paper_due = 0
    app_items = paper_items = app_done = 0
    paper_rated = paper_low = 0
    for a in (asg_for_student or []):
        st = hw.get(a["id"]) or {}
        n = max(1, int(a.get("to", 0)) - int(a.get("from", 0)) + 1)
        deadline = int(a.get("dueAt") or 0) / 1000.0

        if (a.get("route") or "app") == "paper":
            # 紙の宿題。アプリは達成を観測できないので、
            # 「未提出」にも「期限切れ」にも数えない。数だけ持っておく。
            paper_items += n
            if deadline and deadline > now:
                paper_due += 1
            # 講師が評価をつけていれば、それが唯一の観測点になる。
            # **つけていない場合に不利にしない。** 何も足さないだけ。
            r = rated.get(a["id"])
            if ratescale.value(r) is not None:
                paper_rated += 1
                if ratescale.is_low(r):
                    paper_low += 1
            continue

        app_items += n
        app_done += min(n, len(st.get("done") or {}))
        if not st.get("completedAt"):
            due += 1
            if deadline and deadline < now:
                overdue += 1

    total_items = app_items + paper_items
    # アプリで解ける宿題の割合。1.0 ならアプリ10割、0.1 なら紙9割。
    share = (app_items / total_items) if total_items else 1.0
    # アプリで出した宿題を、どこまで終えているか。
    hw_done = (app_done / app_items) if app_items else 1.0

    return {
        "last": last,               # 最後に何かを解いた時刻
        "n": len(cards),            # 手をつけた項目の総数
        "mature": mature,           # 定着（間隔が0日以上）
        "stuck": stuck,             # つまずき（0回以上まちがえた）
        # 正答率。答えた回数のうち、何回できたか。
        # answered が 0 なら「まだ何もしていない」―― 0% ではない。
        "answered": answered,
        "correct": correct,
        "touched": touched,
        "recent": recent,           # 直近14日。左端がきょう。'.'は何もしていない日
        # 直近7回の宿題を、出したかどうか。左が古く、右がいちばん新しい。
        # 「その日にアプリを開いたか」ではなく **宿題を出したか** を見る。
        # 講師が知りたいのはそちらで、開いただけの日は何も言っていない。
        "hw7": hw7,
        # 直近7日のうち、**毎日テストを終えた日**が何日あるか。
        # hist[日].done は、毎日テストを最後までやった日にだけ立つ
        # （app/js/ui-student.js の endSession）。開いただけの日は立たない。
        "daily7": daily7,
        # 直近7日に解いた問題の実数。学年の中で競うのはこれ。
        # **通算ではなく1週間で切る。** 通算だと、去年から通っている子に
        # 4月入会の子が一生追いつけず、競い合いとして死ぬ。
        # 毎週0に戻るので、今週がんばれば今週勝てる。
        "week": week,
        "recentFrom": today,        # 左端の日付（端末の日付がずれても読める）
        "due": due,                 # 未提出（アプリで解く宿題のみ）
        "overdue": overdue,         # 期限切れ（同上）
        "paperDue": paper_due,      # 紙で出ている宿題の件数。達成は分からない
        # 紙の評価。付いていなければ 0。0 は「悪い」ではなく「無い」。
        # 画面はこれが 0 のとき、何も描かないこと。
        "rated": paper_rated,
        "low": paper_low,           # 「もうすこし」以下が付いた件数
        "streak": int(rec.get("streak") or 0),
        # share が小さいほど、この生徒の学習はアプリの外で起きている。
        # 数字を読むときの割引率として、必ず画面に添えること。
        "share": round(share, 3),
        "hwDone": round(hw_done, 3),
        "grade": rec.get("grade") or "",
        "class": rec.get("classId") or "",
    }


def update_summary(school, sid, rec, asg_for_student=None):
    """1人ぶんだけ書く。**全員ぶんを読まないし、書かない。**

    鍵をかけないのは、生徒どうしが同じファイルに触らないからである。
    同じ生徒が二重に同期しても、書き込みは丸ごと入れ替え（tmp を作って
    置き換える）なので、途中の状態が見えることはない。
    """
    ensure_summary_dir(school)
    paths.save(paths.summary_path(school, sid),
               summarise_one(rec, asg_for_student,
                             rated=ratings_for_student(school, sid)))


# ------------------------------------------------------------------
# 進捗の合流（マージ）
#
# 以前は「ブロブ丸ごと、savedAt が新しいほうが勝つ」だった。これだと
# スマホで圏外のまま20問解いている間に保護者PCが同期すると、
# スマホが戻ったときに20問が**両方から消えた**。実際に起きる。
#
# 進捗は「項目ごとの独立した記録の集まり」なので、項目単位で合流できる。
# 判定に時刻を使わない ―― 子どもの端末は時計がずれる。
# 代わりに reps（その項目に何回答えたか）を使う。reps は端末の中でしか
# 増えず、減ることがないので、時計が狂っていても順序が壊れない。
# ------------------------------------------------------------------
def _card_wins(a, b):
    """a のほうが新しければ True。a, b は [iv, ef, due, reps, lapse, seen, known]"""
    if not b:
        return True
    if not a:
        return False
    ra = a[3] if len(a) > 3 else 0
    rb = b[3] if len(b) > 3 else 0
    if ra != rb:
        return ra > rb
    # 同じ回数なら、あとに触ったほう。ここだけは時刻に頼るが、
    # 「同じ回数まで進んだ2つ」の間の選択なので、外れても被害が小さい。
    return (a[5] if len(a) > 5 else 0) >= (b[5] if len(b) > 5 else 0)


# 縮めて返す画面のファイル。画像（png・jpg）はもう縮んでいるので通さない。
STATIC_TYPES = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
                ".svg": "image/svg+xml", ".json": "application/json; charset=utf-8",
                ".html": "text/html; charset=utf-8", ".txt": "text/plain; charset=utf-8"}
# 動画（初回登録の「できること」）。縮めない・覚えない。iPhone の Safari は、範囲つきの求め（Range）に
# 206 で答えない動画を再生しない。
MEDIA_TYPES = {".mp4": "video/mp4"}
_STATIC_CACHE = {}


def merge_progress(stored, incoming):
    """保存済みと、届いた分を合流する。どちらの学習も捨てない。"""
    out = dict(stored or {})
    out.setdefault("cards", {})
    out.setdefault("hw", {})
    out.setdefault("hist", {})

    stats = {"cards": 0, "hw": 0}

    for cid, card in (incoming.get("cards") or {}).items():
        if not isinstance(card, list):
            continue
        if _card_wins(card, out["cards"].get(cid)):
            out["cards"][cid] = card
            stats["cards"] += 1

    for aid, rec in (incoming.get("hw") or {}).items():
        if not isinstance(rec, dict):
            continue
        cur = out["hw"].get(aid) or {}
        done = dict(cur.get("done") or {})
        # 「覚えた番号」は足し算で合流する。どちらかの端末でやった番号は
        # やったことにする ―― 消す方向に倒すと努力が消える。
        done.update(rec.get("done") or {})
        fin = [t for t in (cur.get("completedAt"), rec.get("completedAt")) if t]
        out["hw"][aid] = {
            "done": done,
            "startedAt": min([t for t in (cur.get("startedAt"), rec.get("startedAt")) if t] or [None]) or None,
            "completedAt": min(fin) if fin else None,
        }
        stats["hw"] += 1

    for day, h in (incoming.get("hist") or {}).items():
        if not isinstance(h, dict):
            continue
        cur = out["hist"].get(day) or {}
        out["hist"][day] = {
            "n":  max(cur.get("n", 0),  h.get("n", 0)),
            "ok": max(cur.get("ok", 0), h.get("ok", 0)),
            "done": 1 if (cur.get("done") or h.get("done")) else 0,
        }

    meta = incoming.get("meta") or {}
    for k in ("streak", "best", "xp"):
        out[k] = max(out.get(k, 0) or 0, meta.get(k, 0) or 0)
    for k in ("grade", "classId", "v", "sid"):
        if meta.get(k):
            out[k] = meta[k]
    # 今週の目標（生徒が自分で決める。毎日テストを週に何日やるか）。
    # days が 0 なら「目標なし」―― 消す方向もここで受ける。
    g = meta.get("goal")
    if isinstance(g, dict):
        try:
            days = int(g.get("days") or 0)
        except (TypeError, ValueError):
            days = 0
        if days > 0:
            out["goal"] = {"days": max(1, min(7, days)), "at": int(g.get("at") or 0)}
        else:
            out.pop("goal", None)
    return out, stats


_CUR_FIXED = set()


def pack_exists(pid):
    p = os.path.join(APP_DIR, "content", str(pid) + ".js")
    return os.path.isfile(p)


def drop_missing_packs(cur):
    """もう無い教材を指している欄を落とす。**落とすと既定に戻る。**

    教材を作り直したり名前を変えたりすると、進度の側は古い名前を
    指したまま残る。指した先が無くても落ちない ―― その教科の画面が
    空になるだけで、エラーも出ない。**気づけない壊れ方**である。

    実際、デモの進度が japanese/kanji-e・science/j1・social/j1-geo という
    もう無い教材を指したまま残っていて、そのうえ既定を丸ごと
    上書きしていたので、足したはずの教材が1問も出ない状態だった。

    講師が選んだ教材のうち **実在するもの**は残す。
    全部消えた欄は packs ごと外す ―― 空の一覧を残すと
    「使わない」と読まれて、やはり0問になる。
    """
    plans = (cur or {}).get("plans") or {}
    changed = False
    for key, v in list(plans.items()):
        packs = (v or {}).get("packs")
        if not isinstance(packs, list) or not packs:
            continue
        live = [p for p in packs if pack_exists(p)]
        if live == packs:
            continue
        changed = True
        if live:
            v["packs"] = live
        else:
            v.pop("packs", None)
            v.pop("bands", None)     # 帯は教材のもの。教材を外したら一緒に外す
        if not v:
            plans.pop(key, None)
    return changed


def curriculum(school):
    """進度（学年 × 科目ごとの分量と範囲）。講師が画面から書き換える。

    ファイルが無いうちは空を返す。クライアントは app/curriculum.js の
    既定値を使い、講師が最初に保存した時点でここに実体ができる。
    既定値の置き場所を2箇所に持たないための作り。"""
    cur = paths.load(paths.school_file(school, "curriculum.json"), {})
    # 起動後1回だけ、もう無い教材への参照を掃除する。
    if school not in _CUR_FIXED:
        _CUR_FIXED.add(school)
        try:
            if drop_missing_packs(cur):
                save_curriculum(school, cur)
                sys.stderr.write("  進度から、もう無い教材への参照を外しました:"
                                 " %s\n" % school)
        except (IOError, OSError, paths.BadPath):
            pass
    return cur


def save_curriculum(school, rec):
    paths.save(paths.school_file(school, "curriculum.json"), rec)


# ------------------------------------------------------------------
# 進度の検証
#
# 講師は信用してよい相手だが、**画面から届く JSON は信用しない**。
# 合言葉が盗まれた場合、ここが最後の砦になる。
# 想定外の鍵・桁・型は落とし、通ったものだけを保存する。
# ------------------------------------------------------------------
PLAN_KEY = re.compile(r"^[a-z0-9_-]{1,16}:[a-z0-9_-]{1,24}$")
WRITE_DENIED = "この授業計画は、担当している講師しか直せません"
ID_RE    = re.compile(r"^[A-Za-z0-9_\-/]{1,64}$")
TRACKS   = {"vocab", "prep", "gram", "brit", "term", "quiz"}
MAX_PLANS = 200
MAX_BODY  = 256 * 1024


def _clean_str(v, n):
    return str(v)[:n].strip()


def _clean_list(v, n, each, pattern=None):
    out = []
    for x in (v or [])[:n]:
        t = _clean_str(x, each)
        if not t:
            continue
        if pattern and not pattern.match(t):
            raise ValueError("使えない文字が入っています: %r" % t[:20])
        out.append(t)
    return out


def teacher_pairs(acc):
    """その講師が受け持つ「クラス × 教科」の組。

    **これがこのシステムの前提である。**
    講師は学年をまるごと持たない。あるクラスの、ある1教科だけを持つ。
    実際の受け持ちはこういう形になる。

        小4β 算数 ／ 小5 理科 ／ 小6α 算数
        中1 理科 ／ 中1R 数学 ／ 中2R 数学 ／ 中2R 英語

    学年で権限を切ると、中2Rの英語の先生に中2Rの数学の記録まで
    見えてしまう。**見えてよい理由が無いものは見せない。**

    返すのは [(クラスID, 教科ID), …]。
    教室長など全部を見る人は None（＝制限なし）。

    アカウントには assign を入れる。

        "assign": [["e4b","math"], ["e5","science"], …]

    まだ assign が無い古いアカウントは、classes から
    「そのクラスの全教科」とみなす ―― 移行の途中で誰も締め出さない。
    """
    if "*" in (acc.get("classes") or []):
        return None
    pairs = acc.get("assign")
    if "assign" in acc and isinstance(pairs, list):
        out = [(str(a[0]), str(a[1])) for a in pairs if len(a) >= 2]
    else:
        # 古い形。クラスだけが入っている。
        out = []
        for cid in (acc.get("classes") or []):
            for sub in subject_ids():
                out.append((cid, sub))
    # **コースの担当を足す**（PLAN-宿題と配達 規則1）。足すだけで、上は変えない。
    # コースしか持たない講師は assign を空の配列で持つこと ―― 持たないと
    # 上の古い形に落ちて、classes のクラスの全教科が見えてしまう。
    if acc.get("school") and acc.get("sid"):
        for pr in courses.pairs_of(acc["school"], acc["sid"]):
            if pr not in out:
                out.append(pr)
    return out


def teacher_slots(acc):
    """担当を時間割の形で返す。

        [{"classId":"j1r", "subject":"math", "day":1, "period":1}, …]

        day    1=月 … 6=土（0 は曜日が決まっていない）
        period その日の何コマ目か（1から）

    講師は多い人で14コマほど持つ。曜日と順番が分かれば、
    画面に週の時間割としてそのまま並べられる。
    **時刻は持たない。** 何時からかは校舎ごとに違ううえ、
    画面で必要なのは「その日の何番目か」だけである。
    """
    pairs = acc.get("assign") or []
    school = acc.get("school") or ""
    tbl = class_table(school) if school else {}
    out = []
    for i, a in enumerate(pairs):
        if len(a) < 2:
            continue
        g = (tbl.get(str(a[0])) or {}).get("grade") or ""
        out.append({
            "classId": str(a[0]), "subject": str(a[1]),
            "day": int(a[2]) if len(a) > 2 and str(a[2]).isdigit() else 0,
            "period": int(a[3]) if len(a) > 3 and str(a[3]).isdigit() else i + 1,
            # 画面が格子のマスを引く鍵。旧形式は「学年:教科」。
            "key": ("%s:%s" % (g, a[1])) if g else "",
            "app": True,
        })
    # コースのコマを足す。こちらは時刻（start / end）とコース名を持つ。
    if school and acc.get("sid"):
        out += courses.slots_of(school, acc["sid"])
    out.sort(key=lambda x: (x["day"] or 9, x.get("start") or "", x["period"]))
    return out


def teacher_classes(acc):
    """担当するクラスID。重複は畳む。None は全部。"""
    pairs = teacher_pairs(acc)
    if pairs is None:
        return None
    out = []
    for cid, _ in pairs:
        if cid not in out:
            out.append(cid)
    return out


def teacher_subjects(acc, class_id):
    """そのクラスで、この講師が受け持つ教科。"""
    pairs = teacher_pairs(acc)
    if pairs is None:
        return list(subject_ids())
    return [sub for cid, sub in pairs if cid == class_id]


def can_see(acc, class_id, subject=None):
    """このクラス（と教科）を見てよいか。

    教科を渡さないときは「そのクラスに何か担当がある」で判定する。
    名簿のように、教科をまたいで生徒の一覧を出す画面で使う。
    """
    pairs = teacher_pairs(acc)
    if pairs is None:
        return True
    for cid, sub in pairs:
        if cid != class_id:
            continue
        if subject is None or sub == subject:
            return True
    return False


def taught_classes(school, grade, subject, fallback=""):
    """その学年その教科を、実際に**どのクラスで**やっているか。

    授業計画（進度）は「学年 × 教科」でひとつ持つ。だが宿題は
    クラスごとに出さないといけない。小4αと小4βは同じ範囲を
    進んでいても、別のクラスであり、提出状況も別に見る。

    前は計画に書いてある classId ひとつにだけ出していた。その結果、
    小4βの算数を持つ講師の画面には、小4αに出した宿題の提出状況が
    出ていた。しかも棒を押して開いた一覧は空だった ―― 小4βには
    1件も出していなかったからである。

    誰かが担当しているクラスすべてに出す。担当が誰も居なければ、
    計画に書いてあるクラスに出す（従来どおり）。
    """
    tbl = class_table(school)
    got = []
    for acc in accounts(school).values():
        if acc.get("role") != "teacher":
            continue
        for pair in (acc.get("assign") or []):
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                continue
            cid, sub = pair[0], pair[1]
            if sub != subject or cid in got:
                continue
            if (tbl.get(cid) or {}).get("grade") == grade:
                got.append(cid)
    if got:
        got.sort()
        return got
    return [fallback] if fallback else []


def class_table(school):
    """クラスID → クラス定義。

    校舎の進度（curriculum.json）に入っていればそれを使う。
    **入っていないときは app/curriculum.js から読む。**

    サーバ側に写しを持たないのが原則だが、クラスの学年だけは
    権限の判定に要る。ここが引けないと teacher_grades が
    クラスIDをそのまま学年として返し、担当が1件も無いことになる
    （実際、格子が空になった）。読めなければ空を返し、
    呼ぶ側が「分からない」として扱えるようにする。
    """
    cur = curriculum(school)
    rows = cur.get("classes") or []
    if rows:
        return {c["id"]: c for c in rows if c.get("id")}
    try:
        src = io.open(os.path.join(APP_DIR, "curriculum.js"),
                      encoding="utf-8").read()
    except (IOError, OSError):
        return {}
    out = {}
    m = re.search(r"classes:\s*\[(.*?)\n\s*\]", src, re.S)
    if not m:
        return {}
    for row in re.finditer(r"\{([^{}]*)\}", m.group(1)):
        f = dict(re.findall(r"(\w+)\s*:\s*'([^']*)'", row.group(1)))
        if f.get("id"):
            out[f["id"]] = f
    return out


def may_touch(school, acc, a, subject=None):
    """講師がその宿題を見て・採点して・取り消してよいか。

    **コースの宿題は、そのコースの講師だけ。** 在籍クラスと教科の組で
    判定すると、合同コース（小5の理科など）の講師に、同じ ID の別コース
    （小5β 算数など）の宿題まで通ってしまう。コースでない宿題は今までどおり。
    """
    key = (a.get("lesson") or {}).get("key") or ""
    p = courses.all_courses(school).get(key) if key else None
    if p is not None:
        return teacher_classes(acc) is None or acc["sid"] in (p.get("teachers") or [])
    return can_see(acc, a.get("classId"), subject)


def subject_of_assignment(a):
    """その宿題がどの教科か。

    授業計画から出したものは lesson.key（"j2:science" の形）に入る。
    手で出したものは教材から引く。どちらでも分からなければ空。
    """
    if a.get("subject"):
        return a["subject"]
    key = ((a.get("lesson") or {}).get("key") or "")
    if ":" in key:
        return key.split(":")[1]
    src = a.get("source") or ""
    m = BUILTIN_MATERIALS.get(src) or {}
    return m.get("subject") or ""


def teacher_grades(acc):
    """その講師が担当する学年。担当クラスから引く。"""
    allowed = teacher_classes(acc)
    if allowed is None:
        return None                      # 全学年（教室長など）
    by_id = class_table(acc["school"])
    if not by_id:
        # まだサーバに進度が無いときは、アカウントの所属を頼りにする
        return {acc.get("classId", "")}
    out = set()
    for cid in allowed:
        k = by_id.get(cid)
        if k and k.get("grade"):
            out.add(k["grade"])
    return out


def merge_curriculum(stored, incoming, acc):
    """担当している学年の進度だけを差し替える。

    進度は1つの文書なので、そのまま保存させると
    中1の講師が中3の分量を書き換えられてしまう（実際に通ってしまった）。
    担当外の行は、送られてきても **保存済みのほうを残す**。
    学年とクラスの一覧も、全体を見る権限がある人だけが変えられる。"""
    grades = teacher_grades(acc)
    out = dict(stored) if stored else {}
    out["v"] = 2

    if grades is None:
        # 全体を見る権限。そのまま採用してよい。
        return incoming, set(incoming.get("plans", {}).keys())

    # 学年・クラスの一覧は担当講師には触らせない
    out["grades"] = stored.get("grades") or incoming.get("grades") or []
    out["classes"] = stored.get("classes") or incoming.get("classes") or []

    plans = dict(stored.get("plans") or {})
    touched = set()
    mine = {k for k in list(plans.keys()) + list(incoming.get("plans", {}).keys())
            if k.split(":")[0] in grades}
    for k in mine:
        if k in incoming.get("plans", {}):
            plans[k] = incoming["plans"][k]
            touched.add(k)
        else:
            plans.pop(k, None)           # 担当学年から消したのは意図とみなす
            touched.add(k)
    out["plans"] = plans
    if not touched:
        raise ValueError("担当していない学年の進度は変更できません")
    return out, touched


def valid_curriculum(d):
    if not isinstance(d, dict):
        raise ValueError("形式が違います")
    out = {"v": 2}

    out["grades"] = []
    for g in (d.get("grades") or [])[:20]:
        gid = _clean_str(g.get("id", ""), 16)
        if not gid or not ID_RE.match(gid):
            raise ValueError("学年IDが不正です")
        out["grades"].append({"id": gid,
                              "name": _clean_str(g.get("name", gid), 24),
                              "order": int(g.get("order", 0) or 0)})

    out["classes"] = []
    for c in (d.get("classes") or [])[:60]:
        cid = _clean_str(c.get("id", ""), 24)
        if not cid or not ID_RE.match(cid):
            raise ValueError("クラスIDが不正です")
        out["classes"].append({"id": cid,
                               "name": _clean_str(c.get("name", cid), 32),
                               "grade": _clean_str(c.get("grade", ""), 16),
                               "code": _clean_str(c.get("code", ""), 32)})

    plans = d.get("plans") or {}
    if not isinstance(plans, dict):
        raise ValueError("進度の形式が違います")
    if len(plans) > MAX_PLANS:
        raise ValueError("進度が多すぎます（上限%d）" % MAX_PLANS)
    out["plans"] = {}
    for key, p in plans.items():
        k = _clean_str(key, 48)
        if not PLAN_KEY.match(k):
            raise ValueError("進度の鍵は「学年:科目」の形にしてください: %r" % k[:20])
        if not isinstance(p, dict):
            raise ValueError("進度の中身が違います: %s" % k)
        daily = {}
        for tk, tv in (p.get("daily") or {}).items():
            t = _clean_str(tk, 16)
            if t not in TRACKS:
                raise ValueError("知らない出題種別です: %r" % t[:16])
            try:
                n = float(tv)
            except (TypeError, ValueError):
                raise ValueError("1日の量は数字で入れてください")
            if not (0 <= n <= 100):
                raise ValueError("1日の量は 0〜100 にしてください")
            daily[t] = n
        tracks = _clean_list(p.get("tracks"), 8, 16)
        for t in tracks:
            if t not in TRACKS:
                raise ValueError("知らない出題種別です: %r" % t[:16])
        try:
            mx = int(p.get("maxRev", 100) or 0)
        except (TypeError, ValueError):
            raise ValueError("復習の上限は数字で入れてください")
        out["plans"][k] = {
            # 書いていない＝使う（画面の plan() は enabled !== false を「使う」と読む）。
            # bool() にすると、enabled の無い欄を保存しただけで「使わない」に化ける。
            "enabled": p.get("enabled") is not False,
            "packs":  _clean_list(p.get("packs"), 20, 64, ID_RE),
            "bands":  _clean_list(p.get("bands"), 20, 32),
            "tracks": tracks,
            "daily":  daily,
            "maxRev": max(0, min(1000, mx)),
            "note":   _clean_str(p.get("note", ""), 200),
        }
    return out


# ------------------------------------------------------------------
# 宿題
# ------------------------------------------------------------------
def students_for(school, a, cache=None):
    """この宿題が誰に出ているか。個別指定があればそれが優先、
    無ければクラス全員。

    在籍が終わった生徒には出さない。出すと「未提出」に数えられ、
    退塾した子がいつまでも講師の画面に残る。
    """
    by, db = roster_of(school, cache)
    picked = a.get("students") or []
    if picked:
        want = set(picked)
        live = set()
        for sids in by.values():
            live |= set(sids)
        return sorted(s for s in want if s in live)
    return list(by.get(a.get("classId")) or [])


def hw_cache():
    """1回のリクエストの中だけ生きる控え。

    講師が宿題タブを開くと、宿題1件ごとに「誰がどこまでやったか」を数える。
    数えるたびに **名簿ぜんぶと、生徒全員の進捗ファイル** を読み直していた。

    実測（app/tools/規模の監査.py、生徒2000名・宿題360件）
        名簿の読み直し   625KB × 360回 = 225MB
        進捗の読み直し    23KB × 2万回 = 460MB
        画面が出るまで   2.9秒

    中身は1回のリクエストの間ずっと同じなので、1度読めばよい。
    **リクエストをまたいで持ち越さない** ―― 持ち越すと、
    さっき採点した結果が反映されない画面ができる。
    """
    return {"blobs": {}, "db": None, "byclass": None, "ratings": None, "subs": None}


def ratings_cached(school, cache=None):
    """評価の台帳。控えがあれば1回のリクエストで1度しか読まない。

    宿題の一覧は宿題1件ごとに評価と写真の台帳を読んでいた（245件で 493回、0.74秒）。
    台帳は1回のリクエストの間ずっと同じなので、1度でよい。"""
    if cache is None:
        return ratings(school)
    if cache.get("ratings") is None:
        cache["ratings"] = ratings(school)
    return cache["ratings"]


def subs_cached(school, cache=None):
    """写真の台帳（ratings_cached と同じ理由）。"""
    if cache is None:
        return SUB.load(school)
    if cache.get("subs") is None:
        cache["subs"] = SUB.load(school)
    return cache["subs"]


def blob_of(school, sid, cache=None):
    """生徒1人の進捗の中身。控えがあれば1度しか読まない。"""
    if cache is None:
        rec = paths.load(progress_path(school, sid), None) or {}
        return rec.get("blob") or {}
    got = cache["blobs"]
    if sid not in got:
        rec = paths.load(progress_path(school, sid), None) or {}
        got[sid] = rec.get("blob") or {}
    return got[sid]


def roster_of(school, cache=None):
    """クラスID → その クラスの生徒のsid。控えがあれば1度しか作らない。"""
    if cache is not None and cache.get("byclass") is not None:
        return cache["byclass"], cache["db"]
    db = accounts(school)
    by = {}
    for x in db.values():
        if x.get("role") != "student" or x.get("leftAt"):
            continue
        by.setdefault(x.get("classId"), []).append(x["sid"])
    for k in by:
        by[k].sort()
    if cache is not None:
        cache["byclass"], cache["db"] = by, db
    return by, db


def hw_state(school, sid, aid, cache=None):
    """その生徒の、その宿題の達成状況。進捗ブロブの中に入っている。"""
    hw = (blob_of(school, sid, cache).get("hw") or {}).get(aid) or {}
    return {"done": len(hw.get("done") or {}),
            "completedAt": hw.get("completedAt"),
            "startedAt": hw.get("startedAt")}


def hw_summary(school, a, cache=None):
    """誰がどこまで終えたか。

    紙の宿題では達成を数えない。アプリは見ていないので、数えたら嘘になる。
    件数と「ノートで確認してください」だけを返す。"""
    sids = students_for(school, a, cache)
    # とびとびの番号を持つ宿題は、その件数がそのまま総数。
    total = (len(a["items"]) if a.get("items")
             else max(0, int(a.get("to", 0)) - int(a.get("from", 0)) + 1))
    if (a.get("route") or "app") == "paper":
        # 紙。達成は数えない。講師が評価をつけていれば、その分だけ返す。
        # 未評価の生徒は rows に載せない ―― 「欠けている」ではなく「無い」。
        per = ratings_cached(school, cache).get(a["id"]) or {}
        rows = [{"sid": sid, "v": ratescale.value(per[sid]), "at": per[sid].get("at")}
                for sid in sids if sid in per]
        # 出ている写真の数も返す。**一覧に出さないと気づけない。**
        # 開いて初めて分かる作りだと、写真が来ていること自体を
        # 知らないまま何日も過ぎる。
        subs = SUB.of_assignment(school, a["id"], subs_cached(school, cache))
        got = [subs[x] for x in sids if x in subs]
        return {"assigned": len(sids), "route": "paper", "total": total,
                "completed": None, "started": None,
                "rated": len(rows), "rows": rows,
                "subs": len(got),
                "unseen": len([x for x in got if not x.get("seen")])}
    rows, finished, started = [], 0, 0
    for sid in sids:
        st = hw_state(school, sid, a["id"], cache)
        if st["completedAt"]:
            finished += 1
        if st["done"]:
            started += 1
        rows.append({"sid": sid, "done": st["done"],
                     "completedAt": st["completedAt"]})
    return {"assigned": len(sids), "route": "app", "completed": finished,
            "started": started, "total": total, "rows": rows}


# 教科のコード。記録の札はこの文字で始まる（app/content/manifest.js）。
SUBJECT_CODE = {"english": "en", "science": "sci", "social": "soc",
                "math": "mat", "japanese": "jpn"}

# 画面に出す名前。学年で呼び方が変わるものは grade を渡す。
SUBJECT_NAME = {"english": "英語", "science": "理科", "social": "社会",
                "math": "数学", "japanese": "国語"}
GRADE_NAME = {"e4": "小4", "e5": "小5", "e6": "小6",
              "j1": "中1", "j2": "中2", "j3": "中3"}


def subject_name(sub, grade=""):
    """教科の呼び名。小学校の math は算数。"""
    if sub == "math" and str(grade).startswith("e"):
        return "算数"
    return SUBJECT_NAME.get(sub, sub or "")


def grade_name(grade):
    return GRADE_NAME.get(grade, grade or "")


def booklet_name(school, src):
    """教材の呼び名。分からなければIDをそのまま返す。"""
    m = materials(school).get(src) or {}
    return str(m.get("short") or m.get("name") or src)


def weak_tally(school, class_id, subject):
    """そのクラスで、項目ごとに **何人がまちがえたか** を数える。

    返すのは (人数, {項目: [まちがえた人数, 最後にさわった時刻]})。

    札の呼び名は「教科コード:種類:見出し」（例 jpn:t:懸垂）、
    中身は [iv, ef, due, reps, lapse, seen, known]（app/js/store.js）。
    lapse が1回でもあれば、その子はそこでつまずいた。
    """
    code = SUBJECT_CODE.get(subject)
    if not code:
        return 0, {}
    sids = [a["sid"] for a in accounts(school).values()
            if a.get("role") == "student" and a.get("classId") == class_id
            and not a.get("leftAt")]
    if not sids:
        return 0, {}
    pre = code + ":"
    tally = {}
    for sid in sids:
        rec = paths.load(progress_path(school, sid), None) or {}
        cards = ((rec.get("blob") or {}).get("cards") or {})
        for cid, c in cards.items():
            if not cid.startswith(pre):
                continue
            if not isinstance(c, list) or len(c) < 6 or not (c[4] or 0):
                continue
            e = tally.setdefault(cid, [0, 0])
            e[0] += 1
            e[1] = max(e[1], int(c[5] or 0))
    return len(sids), tally


# ------------------------------------------------------------------
# 毎日テスト ―― 毎週、2本を自動で組む
# ------------------------------------------------------------------
# **講師に中身を考えさせない。** 何を出すかは記録が知っている。
#
#   1. 今週のたしかめ … 今週の授業でやったところ
#      授業計画の「いま出している回」の宿題の範囲から取る。
#      授業でやった直後に、同じ所をもう一度たしかめる。
#
#   2. にがてつぶし … それより前の回で、まちがえたところ
#      その生徒がつまずいた項目から取る。人によって中身が違う。
#
# 教科書（Textbooks）で選んだ教材の中からしか出さない。
# 使っていない冊子の番号を出しても、生徒は引けない。
# 毎日テストの問数は **学年の持ち時間から決める**（examprep.DAILY_MIN）。
# 前はここが 12問・8問の固定で、小4も中3も同じ量だった。
# 5教科ぶん出すと、小4でも1日70分を超えていた。
DAILY_WEEK_MAX = 12        # 今週のたしかめ。持ち時間が余ってもここまで
DAILY_WEAK_MAX = 8         # にがてつぶし


def enabled_subjects(school, grade):
    """その学年で生徒に出ている教科。**講師が進度で外した教科は出さない。**

    進度がまだ保存されていない校舎では、既定（app/curriculum.js）が
    サーバに無いので、教材のある教科をそのまま使う。
    教材が1問も無い教科は、そもそも出しようがないので落とす ――
    英語の授業が無い小4に、英語の対策テストを出さないのはここである。

    **使わないのは enabled が false のときだけ。** packs が空・無いのは
    「既定の教材のまま」で、画面（app/js/config.js の plan()）と同じ読み方をする。
    前は空を「使わない」と読んでいたので、講師が進度を1度保存すると、
    既定の教材のままの教科（中1の数学・英語・理科・社会）が学校じゅうで
    対策テストから消え、毎日テストの問数の割り方も変わっていた。
    """
    plans = (curriculum(school) or {}).get("plans") or {}
    subs = []
    for sub in sorted(SUBJECT_CODE):
        v = plans.get("%s:%s" % (grade, sub))
        if v is not None:
            if v.get("enabled") is False:
                continue
        elif plans:
            # 進度はあるが、この教科の欄が無い ＝ 使っていない
            continue
        if examprep.pack_items(sub, grade):
            subs.append(sub)
    return subs


def daily_n(school, grade, subject):
    """今週のたしかめ／にがてつぶし に出す問数。

    **学年の持ち時間を教科の数で割る。** 1問の重さは教科でちがうので、
    秒数から問数に直す（数学の1問は70秒、英語は30秒）。
    """
    new_sec, rev_sec = examprep.daily_sec(
        grade, len(enabled_subjects(school, grade)) or len(SUBJECT_CODE))
    return (min(DAILY_WEEK_MAX, examprep.fit_count(subject, "term", new_sec)),
            min(DAILY_WEAK_MAX, examprep.fit_count(subject, "quiz", rev_sec)))



# 紙の宿題の評価を、毎日テストに効かせるまでの日数。
# **古い評価まで効かせない。** 5週前に △ が付いた単元を今も出し続けると、
# 直したあとも出続けることになり、直した手ごたえが消える。
RATING_FRESH_DAYS = 35


def low_rated_units(school, sid, subject, now=None):
    """紙の宿題で「もうすこし」以下が付いた単元。新しい順。

    紙の宿題はアプリからは達成が見えないので、SRS の記録には
    何も残らない。**講師が付けた評価だけが、その単元の唯一の観測点**である。
    ここを毎日テストにつなげないと、ノートで苦戦したことが
    次の日以降どこにも活きない。
    """
    now = now or time.time()
    since = now - RATING_FRESH_DAYS * 86400
    mine = ratings_for_student(school, sid)
    if not mine:
        return []
    asg = assignments(school)
    plans = lessons.load(school).get("plans") or {}
    out = []
    for aid, r in mine.items():
        if not ratescale.is_low(r):
            continue
        if (r.get("at") or 0) < since:
            continue
        a = asg.get(aid)
        if not a or subject_of_assignment(a) != subject:
            continue
        les = a.get("lesson") or {}
        plan = plans.get(les.get("key") or "") or {}
        for l in (plan.get("lessons") or []):
            if l.get("n") == les.get("n") and l.get("topic"):
                out.append((r.get("at") or 0, l["topic"]))
                break
    out.sort(reverse=True)
    seen, names = set(), []
    for _at, u in out:
        if u not in seen:
            seen.add(u)
            names.append(u)
    return names


def daily_sets(school, class_id, subject, sid=None):
    """その枠の毎日テスト2本。画面はこれを見て出す。

    返すのは
        [{"kind":"week"|"weak", "title":…, "source":…,
          "from":…, "to":…, "items":[…], "n":…}, …]

    今週のたしかめは範囲（教材＋番号）で、にがてつぶしは項目の並びで返す。
    どちらも空になることがある ―― 授業がまだ無い週、記録が無い生徒。
    """
    tbl = class_table(school)
    grade = (tbl.get(class_id) or {}).get("grade") or ""
    week_n, weak_n = daily_n(school, grade, subject)
    out = []

    # 1. 今週のたしかめ。授業計画のいまの回から。
    key = "%s:%s" % (grade, subject)
    pl = lessons.plan(school, key) or {}
    ls = sorted((pl.get("lessons") or []), key=lambda l: l.get("n") or 0)
    cur = None
    for l in ls:
        if l.get("published"):
            cur = l                      # 出した中でいちばん新しい回
    if cur:
        hw = cur.get("hw") or {}
        src = hw.get("source") or ""
        lo, hi = int(hw.get("from") or 0), int(hw.get("to") or 0)
        if src and lo and hi and route_of(school, src) == "app":
            n = min(week_n, hi - lo + 1)
            out.append({"kind": "week", "title": "今週のたしかめ",
                        "unit": cur.get("topic", ""), "n": n,
                        "source": src, "from": lo, "to": hi})
        else:
            # アプリで解けない教材の週は、範囲では出せない。
            # 単元名だけ返して、画面には「ノートで復習」と出させる。
            out.append({"kind": "week", "title": "今週のたしかめ",
                        "unit": cur.get("topic", ""), "n": 0,
                        "source": src, "from": lo, "to": hi})

    # 2. にがてつぶし。その生徒の記録から。
    #
    # **紙の宿題の評価も混ぜる。** ノートで「もうすこし」が付いた単元は、
    # アプリの記録には何も残らない ―― そこを拾わないと、紙で苦戦した
    # ことが次の日以降どこにも活きない。
    hint = ""
    if sid:
        items = weak_for_student(school, sid, subject, weak_n)
        units = low_rated_units(school, sid, subject)
        if units:
            have = set(items)
            add = [x["id"] for x in examprep.pack_items(subject, grade)
                   if (x.get("unit") or "") in units and x["id"] not in have]
            # 評価から来たぶんを **先に**置く。講師が見て付けた印なので、
            # アプリの中の記録より確かな観測である。
            items = (add[:weak_n] + items)[:weak_n]
            hint = units[0]
    else:
        items = weak_items(school, class_id, subject, weak_n)
    if items:
        out.append({"kind": "weak", "title": "にがてつぶし",
                    "unit": hint, "n": len(items), "items": items})
    return out


def weak_for_student(school, sid, subject, count):
    """その生徒がつまずいている項目を、まちがえた回数の多い順に。"""
    code = SUBJECT_CODE.get(subject)
    if not code:
        return []
    rec = paths.load(progress_path(school, sid), None) or {}
    cards = ((rec.get("blob") or {}).get("cards") or {})
    pre = code + ":"
    rows = []
    for cid, c in cards.items():
        if not cid.startswith(pre):
            continue
        if not isinstance(c, list) or len(c) < 6 or not (c[4] or 0):
            continue
        rows.append((cid, c[4], int(c[5] or 0)))
    rows.sort(key=lambda r: (-r[1], -r[2], r[0]))
    return [r[0] for r in rows[:count]]


# 提案を出す線。**半分以上がまちがえた項目**だけを拾う。
# ここを下げると、毎週どのクラスにも提案が出て、ただの雑音になる。
SUGGEST_SHARE = 0.5
SUGGEST_MIN = 10          # これだけ集まらなければ提案しない
SUGGEST_MAX = 15          # 1回のテストはこれまで


def suggestions_for(acc, school, limit=2):
    """担当している枠を見て、確認テストの案を作る。

    **毎週すべてのクラスに出す前提ではない。**
    半分以上がまちがえた項目が10個たまった枠だけを挙げる。
    そういう枠は週に2〜3個しか出ない ―― それでいい。
    毎週12件出てきたら、講師は1件も見なくなる。

    出すのは、いちばん困っている2件まで。**1週間に手が回るのは
    それくらい**である。5件並べても、講師は1件もやらない。
    """
    pairs = teacher_pairs(acc)
    if pairs is None:
        tbl = class_table(school)
        pairs = [(cid, sub) for cid in tbl for sub in SUBJECT_CODE]
    # **もう出した枠は、提案しない。**
    # つまずきの記録は出しただけでは消えないので、そのままだと
    # 出した直後にまた同じ案が並ぶ。2週間は出し直さない。
    recent = set()
    since = (time.time() - 14 * 86400) * 1000
    for a in assignments(school).values():
        if a.get("pick") != "suggest":
            continue
        if (a.get("assignedAt") or 0) < since:
            continue
        recent.add((a.get("classId"), subject_of_assignment(a)))
    out = []
    for cid, sub in pairs:
        if (cid, sub) in recent:
            continue
        n, tally = weak_tally(school, cid, sub)
        if not n:
            continue
        need = max(2, int(math.ceil(n * SUGGEST_SHARE)))
        rows = [(k, v[0], v[1]) for k, v in tally.items() if v[0] >= need]
        if len(rows) < SUGGEST_MIN:
            continue
        rows.sort(key=lambda r: (-r[1], -r[2], r[0]))
        rows = rows[:SUGGEST_MAX]
        out.append({
            "id": "sg-%s-%s" % (cid, sub),
            "classId": cid, "subject": sub,
            "students": n,
            # まちがえた人数がいちばん多い項目の割合。並べ替えに使う。
            "worst": int(round(rows[0][1] * 100.0 / n)),
            "items": [{"id": r[0], "wrong": r[1],
                       "pct": int(round(r[1] * 100.0 / n))} for r in rows],
        })
    out.sort(key=lambda x: (-x["worst"], -len(x["items"])))
    return out[:limit]


def weak_items(school, class_id, subject, count):
    """そのクラスが実際につまずいている項目を、多い順に集める。

    講師に「どこを出すか」を考えさせない。**生徒の記録が知っている。**

    記録の形
    --------
    1枚の札の呼び名は「教科コード:種類:見出し」（例 jpn:t:懸垂）。
    中身は [iv, ef, due, reps, lapse, seen, known] の並び
    （app/js/store.js の packCards と同じ）。
    lapse が1回でもあれば、その子はそこでつまずいた。

    数え方
    ------
    クラスの何人がつまずいたかを項目ごとに足し、多い順に取る。
    同じ人数なら、**最近さわった項目**を先に ―― 半年前より先週。

    返すのは [項目の呼び名, …]。記録が無ければ []。
    """
    code = SUBJECT_CODE.get(subject)
    if not code:
        return []
    sids = [a["sid"] for a in accounts(school).values()
            if a.get("role") == "student" and a.get("classId") == class_id]
    if not sids:
        return []
    pre = code + ":"
    tally = {}          # 項目 → [つまずいた人数, 最後にさわった時刻]
    for sid in sids:
        rec = paths.load(progress_path(school, sid), None) or {}
        cards = ((rec.get("blob") or {}).get("cards") or {})
        for cid, c in cards.items():
            if not cid.startswith(pre):
                continue
            if not isinstance(c, list) or len(c) < 6:
                continue
            if not (c[4] or 0):
                continue
            e = tally.setdefault(cid, [0, 0])
            e[0] += 1
            e[1] = max(e[1], int(c[5] or 0))
    if not tally:
        return []
    rows = sorted(tally.items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0]))
    return [k for k, _ in rows[:count]]


def valid_assignment(school, d, existing=None, paper_ok=False):
    """作成・更新の中身を確かめて、保存してよい形に整える。

    **授業計画から出す宿題も、ここを通す**（paper_ok=True）。前は自動発行だけが
    ここを通らず、graded を書いていなかった ―― 出すだけの教材（計算・漢字）まで
    提出率の分母に入っていた。paper_ok のときだけ、教材や範囲の分からない
    紙の宿題（「漢字練習帳 50語」）を許し、紙として番号なしで出す。
    """
    out = dict(existing or {})
    title = str(d.get("title", "")).strip()
    src = str(d.get("source", "")).strip()
    if not title:
        raise ValueError("題名を入れてください")
    if not src and not paper_ok:
        raise ValueError("教材を選んでください")

    # **出す中身は2通りある。**
    #   1. 教材の何番から何番まで（ふつうの宿題）
    #   2. 項目そのものを並べたもの（にがて集め）
    # 2 のときは番号が無い。先に見分けてから番号を読む ―― 逆にすると
    # 項目で出す宿題が「番号は数字で」と弾かれる。
    items = d.get("items")
    lo = hi = None
    if items is not None:
        if not items:
            raise ValueError("出す中身がありません")
        if len(items) > MAX_RANGE:
            raise ValueError("1つの宿題は%d問までにしてください（いまは%d問）"
                             % (MAX_RANGE, len(items)))
        if all(str(x).isdigit() for x in items):
            items = sorted(set(int(x) for x in items if 1 <= int(x) <= 100000))
            if not items:
                raise ValueError("出す番号がありません")
            lo, hi = items[0], items[-1]
        else:
            items = [str(x)[:120] for x in items]
            lo, hi = 1, len(items)
        out["items"] = items
    else:
        out.pop("items", None)
        try:
            lo = int(d.get("from"))
            hi = int(d.get("to"))
        except (TypeError, ValueError):
            if not paper_ok:
                raise ValueError("番号は数字で入れてください")
            lo = hi = 0
        if paper_ok and not (src and lo >= 1 and hi >= lo):
            lo = hi = 0                      # 範囲の分からない紙の宿題
        elif lo < 1 or hi < lo:
            raise ValueError("番号の範囲が逆になっています")
        elif hi - lo + 1 > MAX_RANGE:
            raise ValueError("1つの宿題は%d語までにしてください（いまは%d語）"
                             % (MAX_RANGE, hi - lo + 1))
    try:
        due = int(d.get("dueAt"))
    except (TypeError, ValueError):
        raise ValueError("期限を入れてください")

    picked = [str(x) for x in (d.get("students") or [])]
    class_id = str(d.get("classId", "")).strip()
    if not picked and not class_id:
        raise ValueError("クラスか生徒のどちらかを指定してください")

    out.update({
        "title": title[:80], "source": src[:40],
        "from": lo, "to": hi,
        "classId": class_id, "students": picked,
        "dueAt": due, "note": str(d.get("note", ""))[:200],
        # 宿題は必須。毎日テストは宿題ではないのでここには来ない
        # （毎日テストはSRSから自動で組まれ、保存もされない）。
        "kind": "hw",
        # 経路は教材から引く。画面から送られてきた値は使わない。
        # 信じると、古い画面や打ち間違いで紙の宿題が「未提出」に化ける。
        "route": (route_of(school, src[:40]) if (src and lo and hi) else "paper"),
        # 採点するかどうかも教材から引く。画面からの値は使わない。
        "graded": graded_of(school, src[:40]),
    })

    # **どの教科の宿題かを必ず残す。**
    # 講師は「クラスの1教科」だけを担当するので、教科が分からない
    # 宿題は誰のものか決められない。残さないと、中2Rの英語の先生に
    # 中2Rの数学の宿題まで見えてしまう（実際そうなった）。
    lesson = d.get("lesson")
    if isinstance(lesson, dict):
        key = str(lesson.get("key", ""))[:48]
        if PLAN_KEY.match(key):
            out["lesson"] = {"key": key, "n": lesson.get("n")}
    if not out.get("subject"):
        sub = str(d.get("subject", "")).strip()
        if sub not in subject_ids():
            sub = subject_of_assignment(out)
        if sub:
            out["subject"] = sub
    return out


# ------------------------------------------------------------------
# コースの宿題を出す（PLAN-宿題と配達 規則3・4）
# ------------------------------------------------------------------
def _course_hw(school, key, p, l, it, who, due, note, salt=""):
    """コースから出す宿題1件。**手で出す宿題と同じ検査（valid_assignment）を通す。**"""
    title = (it.get("text") or l.get("topic") or "宿題").strip()
    src = it.get("source") or ""
    lo, hi = int(it.get("from") or 0), int(it.get("to") or 0)
    if not (src and lo and hi):
        # 教材と番号を文から読む。講師に選ばせない（手間を増やさない）。
        gsrc, glo, ghi = source_and_range(school, title)
        src = src or gsrc
        if not (lo and hi):
            lo, hi = glo, ghi
    d = {"title": title, "source": src, "from": lo, "to": hi,
         "classId": courses.course_id(key), "students": list(who),
         "dueAt": due, "note": note, "subject": p.get("subject") or "",
         "lesson": {"key": key, "n": l.get("n")}}
    try:
        rec = valid_assignment(school, d, paper_ok=True)
    except ValueError:
        return None
    # **ID は中身から決める。** 同じコース・同じ回・同じ文の宿題は、作り直しても同じ ID。
    # デモを戻したあとも「あの宿題」を同じ ID で追える（デバッグのしやすさ）。
    seed = "%s|%s|%s|%s" % (key, l.get("n"), title, note)
    if salt:
        seed += "|" + salt              # 生徒だけの宿題（personal）は、生徒ごとに別の ID
    rec.update({"id": "a" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:9],
                "createdBy": "plan", "assignedAt": int(time.time() * 1000)})
    return rec


def _due_lesson(p, today, now, passed=()):
    """まだ出していない回のうち、出す時が来たいちばん古いもの。無ければ None。

    passed は、この呼び出しで見送った回（宿題がまだ入っていない回）。
    コースの期間（from〜to）は、今日ではなく**その回の日付**で見る
    （期間の最後の回を、期間が過ぎた翌日にも出せるように）。
    """
    for l in sorted((p.get("lessons") or []), key=lambda x: x.get("date") or ""):
        d = l.get("date") or ""
        if l.get("published") or not d or d > today or l.get("n") in passed:
            continue
        if not courses.active(p, d):
            continue
        try:
            t = time.mktime(time.strptime(d, "%Y-%m-%d"))
        except ValueError:
            continue
        # 古すぎる回は出さない。あとから予定を入れたとき、過去の回が
        # まとめて生徒に出ないように（lessons.STALE_DAYS の説明）。
        if now - t > lessons.STALE_DAYS * 86400:
            continue
        return l
    return None


# ------------------------------------------------------------------
# その回に出す既定の宿題（生徒ごとの決まりを当てる前）
# ------------------------------------------------------------------
def lesson_recs(school, key, p, l, who, due, note):
    """その回に出す既定の宿題を組む。**保存はしない。**

    返す (宿題の一覧, その回の宿題と上乗せ, 毎週の分を進める位置)。
    発行（publish_courses）と、講師の画面の「次の回のこの生徒の宿題」が同じものを使う ――
    2か所で組むと、画面の見本と実際に出る宿題が食い違う。

      1回の宿題のブロック（hw.items）ごとに1件
      上乗せ（extra）は、その回の受け取り手に入っている指名の生徒にだけ
      毎週固定（weekly）は、その週の最初の回を出すときに1件ずつ
    """
    recs = [_course_hw(school, key, p, l, it, who, due, note)
            for it in lessons.hw_items(l.get("hw"))]
    for ex in (p.get("extra") or []):
        named = [s for s in (ex.get("students") or []) if s in who]
        items = lessons.hw_items((l.get("extraHw") or {}).get(ex.get("id")))
        for it in (items if named else []):
            r = _course_hw(school, key, p, l, it, named, due,
                           "%s（%s）" % (note, ex.get("name") or ""))
            if r:
                # 上乗せの印。保護者への連絡で「（追加）」と書くのに使う。
                r["extra"] = str(ex.get("id") or "")[:16]
            recs.append(r)
    own = [r for r in recs if r]      # その回の宿題と上乗せ（毎週の分は含まない）
    week = courses.iso_week(l["date"])
    advanced = {}
    if p.get("weeklyAt") != week:
        for w in (p.get("weekly") or []):
            if not w.get("id"):
                continue             # 位置を覚える鍵が無いものは出さない
            lo, hi = courses.weekly_range(w)
            rng = ("%d" % lo) if lo == hi else ("%d-%d" % (lo, hi))
            rec = _course_hw(school, key, p, l,
                             {"text": "%s %s" % (w.get("text") or "", rng),
                              "source": w.get("source") or "",
                              "from": lo, "to": hi},
                             who, due, "毎週の分です。")
            recs.append(rec)
            if rec:
                advanced[w["id"]] = hi
    return [r for r in recs if r], own, advanced


# ------------------------------------------------------------------
# 生徒ごとの宿題（personal.py）を、発行のときに当てる
# ------------------------------------------------------------------
_UNIT_ITEMS = {}


def _unit_rows(subject, grade):
    ck = (subject, grade)
    if ck not in _UNIT_ITEMS:
        try:
            _UNIT_ITEMS[ck] = [(it["id"], it.get("unit") or "")
                               for it in examprep.pack_items(subject, grade) if it.get("unit")]
        except (IOError, OSError, ValueError, KeyError):
            _UNIT_ITEMS[ck] = []
    return _UNIT_ITEMS[ck]


def unit_items(subject, grade, unit):
    """アプリの問題のうち、単元名が合うもの（ID の並び）。"""
    if not unit:
        return []
    return [i for i, u in _unit_rows(subject, grade) if INSIGHT.unit_match(u, unit)]


def unit_index(subject, grade):
    """{問題ID: 単元名}（理解度の「毎日テスト」の根拠に使う）。"""
    return dict(_unit_rows(subject, grade))


def _lesson_item_range(school, les, source):
    """その回の宿題（上乗せも含む）のうち、その教材の範囲 (from, to, 文)。無ければ None。"""
    its = list(lessons.hw_items((les or {}).get("hw")))
    for v in ((les or {}).get("extraHw") or {}).values():
        its += list(lessons.hw_items(v))
    for it in its:
        src = it.get("source") or ""
        lo, hi = int(it.get("from") or 0), int(it.get("to") or 0)
        if not src or not (lo and hi):
            gsrc, glo, ghi = source_and_range(school, it.get("text") or "")
            src = src or gsrc
            if not (lo and hi):
                lo, hi = glo, ghi
        if src == source and lo and hi:
            return (int(lo), int(hi), it.get("text") or "")
    return None


def apply_personal(school, key, p, l, recs, due, note):
    """生徒ごとの決まりを、この回の宿題に当てる。決まりが無ければそのまま返す。"""
    rules = PERSONAL.rules_of(school, key)
    if not rules:
        return recs
    n = int(l.get("n") or 0)
    by_n = {}
    for x in (p.get("lessons") or []):
        try:
            by_n[int(x.get("n"))] = x
        except (TypeError, ValueError):
            continue

    def lookup(source, ln):
        try:
            ln = int(ln)
        except (TypeError, ValueError):
            ln = n
        if ln == n:
            for r in recs:
                if r.get("source") == source and r.get("from") and r.get("to"):
                    return (int(r["from"]), int(r["to"]), r.get("title") or "")
        return _lesson_item_range(school, by_n.get(ln), source)

    def make(item, sid, rule_ids):
        ids = [x for x in rule_ids if x]
        if item.get("app"):
            got = unit_items(p.get("subject") or "", p.get("grade") or "", item["app"].get("unit"))
            got = got[:int(item["app"].get("count") or 10)]
            if not got:
                return None
            try:
                rec = valid_assignment(school, {
                    "title": item.get("title") or "復習", "source": "unit", "items": got,
                    "classId": courses.course_id(key), "students": [sid], "dueAt": due,
                    "note": note, "subject": p.get("subject") or "",
                    "lesson": {"key": key, "n": n}})
            except ValueError:
                return None
            rec["route"] = "app"          # 問題を直接指す宿題は、必ずアプリで解ける
            seed = "%s|%s|%s|%s|%s" % (key, n, rec["title"], note, sid)
            rec.update({"id": "a" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:9],
                        "createdBy": "plan", "assignedAt": int(time.time() * 1000)})
        else:
            rec = _course_hw(school, key, p, l,
                             {"text": item.get("title") or "", "source": item.get("source") or "",
                              "from": item.get("from") or 0, "to": item.get("to") or 0},
                             [sid], due, note, salt=sid)
            if not rec:
                return None
            if item.get("extra"):
                rec["extra"] = item["extra"]
        rec["personal"] = ids
        return rec

    return PERSONAL.apply(recs, rules, n, lookup, make,
                          unit_name=lessons.unit_text(l))


# ------------------------------------------------------------------
# 講師の机 ―― 今日やること・宿題チェック・成績の診断（PLAN-講師ページ改修）
# ------------------------------------------------------------------
def course_use_of(school, a):
    """宿題 a を出したコースの導入の印（courses.use_flags）。コースから出ていない古い宿題は、ぜんぶ使える扱い。"""
    key = str(((a or {}).get("lesson") or {}).get("key") or "")
    try:
        p = courses.all_courses(school).get(key) if key else None
    except (IOError, OSError, BadPath):
        p = None
    return courses.use_flags(p) if p else {"hw": True, "photo": True, "correct": True, "quiz": True}


def desk_courses(school, acc):
    """その講師が見てよいコース。全部を見る講師（'*'）は全コース。
    **アプリを使うコースだけ**（紙のままのコースは時間割にだけ出る）。"""
    if teacher_classes(acc) is None:
        allc = dict(courses.all_courses(school))
    else:
        allc = courses.of_teacher(school, acc["sid"])
    return {k: p for k, p in allc.items() if courses.app_on(p)}


def desk_labels(school, at=None):
    """sid → 「中2R-01」。画面と同じ組み方（app/js/ui-core.js labelOf）。

    at（時刻・秒）を渡すと、**その時刻にいたクラスと席**で組む（クラス替えをさかのぼる。class_at）。
    塾内テストの表はテストの日の席で書かれているので、取り込むときはテストの日で合わせる。"""
    cls = class_table(school)
    out = {}
    for a in accounts(school).values():
        if a.get("role") != "student" or not a.get("sid"):
            continue
        cid, seat = class_at(a, at) if at is not None else (a.get("classId"), seat_of(a))
        name = re.sub(r"\s+", "", (cls.get(cid) or {}).get("name") or cid or "")
        out[a["sid"]] = seat_label(name, seat)
    return out


# ------------------------------------------------------------------
# クラス替え（組み分けテストのたびに α⇄β・T⇄R が入れ替わる）
#
# 生徒は同じアカウントのまま（sid・ログインID・合言葉・記録は変わらない）、
# classId と seat だけが変わる。前のクラスと席は acc["moves"] に日付つきで残す
# （cmd_move。取り消しは move --undo）。画面の「中2R-07」は今のクラスで組むが、
# **テストの日の席で書かれた表**や、**前のクラスでの記録**は、ここから引く。
# ------------------------------------------------------------------
def class_at(acc, t):
    """その時刻に acc がいたクラスと席 (classId, seat)。t より後のクラス替えを新しい順に巻き戻す。"""
    cid, seat = acc.get("classId") or "", seat_of(acc)
    for m in sorted(acc.get("moves") or [], key=lambda m: m.get("at") or 0, reverse=True):
        if (m.get("at") or 0) <= t:
            break
        f = m.get("from") or {}
        cid, seat = f.get("classId") or cid, f.get("seat") or seat
    return cid, seat


def moved_out(acc, classes):
    """クラス替えで、このクラスの集まり（コースの classes）から出ていった生徒か。"""
    classes = set(classes or [])
    if not classes or acc.get("classId") in classes:
        return False
    return any(((m.get("from") or {}).get("classId") in classes) for m in acc.get("moves") or [])


def move_edges(acc, classes):
    """このクラスの集まりから最後に出た日・最後に入った日（"YYYY-MM-DD"。無ければ None）。"""
    classes = set(classes or [])
    out_d = in_d = None
    for m in sorted(acc.get("moves") or [], key=lambda m: m.get("at") or 0):
        f = (m.get("from") or {}).get("classId") in classes
        t = (m.get("to") or {}).get("classId") in classes
        d = time.strftime("%Y-%m-%d", time.localtime(m.get("at") or 0))
        if f and not t:
            out_d = d
        elif t and not f:
            in_d = d
    return out_d, in_d


def course_asgs(asg_db, key):
    return [a for a in asg_db.values() if (a.get("lesson") or {}).get("key") == key]


def desk_roster(school, p, asgs, labels, keep=None):
    """そのコースの生徒（いまの受け取り手と、出した宿題に入っている生徒）。在籍中だけ。

    **クラス替えで出ていった生徒は入れない**（前の宿題に名前が残っていても、もうこのクラスの生徒ではない。
    入れると成績の人数が学期ごとに膨らむ）。その生徒の前の宿題は、宿題チェックの回の行には残る
    （check_rows は宿題の受け取り手から組む）。keep に入れた sid だけは残す（本人の成績の伸びなど）。"""
    db = accounts(school)
    live = {a.get("sid") for a in db.values()
            if a.get("role") == "student" and not a.get("leftAt") and a.get("sid")}
    gone = set()
    if not p.get("students"):
        gone = {a.get("sid") for a in db.values()
                if a.get("role") == "student" and moved_out(a, p.get("classes"))} - set(keep or ())
    sids = {s for s in courses.receivers(school, p, db) if s in live}
    for a in asgs:
        sids |= {s for s in (a.get("students") or []) if s in live and s not in gone}
    return sorted([{"sid": x, "label": labels.get(x, x)} for x in sids],
                  key=lambda r: r["label"])


def score_roster(school, key, p, date):
    """塾内テストの表を合わせる相手（席の文字 → 生徒）。**テストの日のクラスと席**で組む。

    組み分けテストの結果は、テストを受けた日のクラスと席（「小4α-07」）で書かれてくる。
    取り込むのがクラス替えのあとだと、今の席で合わせれば別の生徒に点が入る（嘘の成績になる）。
    クラス替えの無い生徒は、今までと同じ（今の席＝テストの日の席）。"""
    try:
        t = time.mktime(time.strptime(str(date)[:10] + " 12:00", "%Y-%m-%d %H:%M"))
    except ValueError:
        t = time.time()
    db = accounts(school)
    keep, later = set(), set()
    if not p.get("students"):
        cls = set(p.get("classes") or [])
        for a in db.values():
            if a.get("role") != "student" or not a.get("moves"):
                continue
            then = class_at(a, t)[0] in cls
            if then and moved_out(a, cls):
                keep.add(a.get("sid"))                 # テストのあとで出ていった生徒は合わせる
            elif not then and a.get("classId") in cls:
                later.add(a.get("sid"))                # テストのあとで入ってきた生徒は合わせない
    roster = desk_roster(school, p, course_asgs(assignments(school), key),
                         desk_labels(school, at=t), keep=keep)
    return [r for r in roster if r["sid"] not in later]


def next_lesson_of(p, now=None):
    """次に出す回 ―― まだ出していない回のうち、**これから出せる**いちばん前のもの。

    前は「出していない回のいちばん前」だったので、学期の途中で使い始めたコースや、
    古すぎて出さない回（lessons.STALE_DAYS。_due_lesson と同じ決まり）が残っていると、
    7月の回が「次の授業」になり、個別の宿題の「この回から効きます」もそこを指した
    （2026-09-23 に成績の画面で発覚）。出せない回は次の回にしない。"""
    now = now or time.time()
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    ls = []
    for l in p.get("lessons") or []:
        try:
            ls.append((int(l.get("n")), l))
        except (TypeError, ValueError):
            continue
    ls.sort(key=lambda x: x[0])
    for _n, l in ls:
        if l.get("published"):
            continue
        d = l.get("date") or ""
        if d and d < today:
            try:
                t = time.mktime(time.strptime(d, "%Y-%m-%d"))
            except ValueError:
                continue
            if now - t > lessons.STALE_DAYS * 86400:
                continue                      # もう出さない回。次の回ではない
        return l
    return None


def next_n_of(p):
    l = next_lesson_of(p)
    if l:
        return int(l["n"])
    ns = []
    for x in p.get("lessons") or []:
        try:
            ns.append(int(x.get("n")))
        except (TypeError, ValueError):
            continue
    return (max(ns) + 1) if ns else 1


def insight_ctx(school, key, p, asg_db, labels, rt, sb, weak_db, sc_db, cache, keep=None):
    """理解度を組むのに要るものを、1コースぶん集める（insight.course_matrix に渡す）。
    keep … クラス替えで出ていっても残す生徒（本人の成績の伸びを組むとき）。"""
    asgs = course_asgs(asg_db, key)
    roster = desk_roster(school, p, asgs, labels, keep=keep)
    sub = p.get("subject") or ""
    return {"plan": p, "asgs": asgs, "ratings": rt, "subs": sb,
            "tests": SCORES.tests_of(school, key, sc_db),
            "blobs": {r["sid"]: blob_of(school, r["sid"], cache) for r in roster},
            "unit_of": unit_index(sub, p.get("grade") or ""),
            "weak": {r["sid"]: (((weak_db.get(r["sid"]) or {}).get(sub) or {}).get("units") or {})
                     for r in roster},
            "roster": roster}


def _desk_load(school):
    return {"asg": assignments(school), "rt": ratings(school), "sb": SUB.load(school),
            "weak": weak.load(school), "sc": SCORES.load(school), "labels": desk_labels(school),
            "cache": hw_cache()}


def insight_log(school):
    d = paths.load(paths.school_file(school, "insight.json"), {}) or {}
    return d.get("log") or []


INSIGHT_LOG_MAX = 3000


def insight_note(school, entry):
    """提案を出した・見送ったを残す（提案の順番を講師に合わせるため）。"""
    with LOCK:
        f = paths.school_file(school, "insight.json")
        d = paths.load(f, {}) or {}
        log = (d.get("log") or []) + [entry]
        d["log"] = log[-INSIGHT_LOG_MAX:]
        paths.save(f, d)


def _paper_due(by, nowms, sb=None):
    """紙で採点する宿題がある回のうち、期限が来た回 ―― か、**期限の前でも写真がもう出ている回**。新しい順。

    前は期限が来た回だけだった。提出箱（既定の期限は7日後）に生徒が写真を出しても、講師の
    「今日やること」にも宿題チェックの回の一覧にも7日間出ず、「出したのに先生に届かない」に
    見えた（2026-10-10 本人の実演で発覚）。写真が1枚でも出ていれば、その回は見られる。"""
    def paper(it):
        return any((a.get("route") or "app") == "paper" and a.get("graded") is not False for a in it)
    def arrived(it):
        return bool(sb) and any((sb.get(a.get("id")) or {}) for a in it)
    return sorted([n for n, it in by.items()
                   if paper(it) and (0 < INSIGHT.due_of(it) <= nowms or arrived(it))], reverse=True)


HW_KEEP_DAYS = 365     # 宿題の一覧に出す既定の期間（?all=1 で全部）
MAX_UPLOAD = 20 * 1024 * 1024   # 1回の送信の本文の上限（写真10枚・PDF 6MB を base64 で）
QUIZ_N0 = 900          # 提出箱（授業内の小テストなど）の回の番号はここから。授業計画の回とぶつからない


def _lesson_row(p, n, items=None):
    """回の行。提出箱（QUIZ_N0 以上）は授業計画に無いので、代表の宿題の題名で名乗る。"""
    for l in p.get("lessons") or []:
        try:
            if int(l.get("n")) == n:
                return l
        except (TypeError, ValueError):
            continue
    if n is not None and n >= QUIZ_N0 and items:
        head = sorted(items, key=lambda a: a.get("id") or "")[0]
        kind = str(head.get("kind") or "")
        topic = head.get("title") or "小テスト"
        if kind and topic.startswith(kind):
            topic = topic[len(kind):].strip()     # 名札が種類なので、題からは外す（「漢字テスト 第3回」→ 第3回）
        return {"n": n, "topic": topic, "label": kind or "提出箱", "kind": kind, "quiz": True,
                "picked": bool(head.get("picked")),
                "date": time.strftime("%Y-%m-%d", time.localtime((head.get("assignedAt") or 0) / 1000.0))}
    return {}


QUIZ_KINDS = ("漢字テスト", "計算テスト", "英語テスト", "作文", "過去問")


def make_quiz(school, key, p, title, due_ms, by, kind=None, students=None):
    """提出箱を作る：コースの生徒に、紙で出す1件（採点する）。授業計画の回とは別の番号（QUIZ_N0〜）。

    授業内の小テスト（漢字・計算・英単語）を、オンラインの生徒は写真で出し、対面の生徒は講師が
    回収した紙を取り込む。あとは宿題チェックと同じ道（評価・ひとこと・添削を返す）。

    kind     … 種類（QUIZ_KINDS）。回の名札になり、今日やること・宿題チェックで宿題と見分けがつく。
               題に入っていなければ頭に付ける（「第3回」→「漢字テスト 第3回」）。無ければ名札は「提出箱」。
    students … 渡すと、コースの生徒のうちその生徒だけに出す（追加の宿題・過去問の添削・やり直しなど）。
               2026-10-11 本人：「追加宿題とか別々の宿題を出した生徒はどうなるの」「漢字テスト・計算テスト・
               作文添削・英語テスト・過去問添削をそれぞれ別にしないと」。"""
    kind = str(kind or "").strip()[:20]
    if kind and kind not in QUIZ_KINDS:
        raise ValueError("種類が違います")
    title = str(title or "").strip()[:60]
    if kind and kind not in title:
        title = (kind + " " + title).strip()[:60]
    title = title or "小テスト"
    who = courses.receivers(school, p)
    if students is not None:
        want = {str(s) for s in students}
        who = [s for s in who if s in want]
        if not who:
            raise ValueError("選んだ生徒が、このコースにいません")
    if not who:
        raise ValueError("このコースには生徒がいません")
    used = [int((a.get("lesson") or {}).get("n") or 0) for a in course_asgs(assignments(school), key)
            if int((a.get("lesson") or {}).get("n") or 0) >= QUIZ_N0]
    n = (max(used) + 1) if used else QUIZ_N0
    d = {"title": title, "source": "", "classId": courses.course_id(key), "students": list(who),
         "dueAt": int(due_ms), "note": "提出箱：写真で出してください（対面の人は先生が回収します）",
         "subject": p.get("subject") or "", "lesson": {"key": key, "n": n, "quiz": True}}
    rec = valid_assignment(school, d, paper_ok=True)
    rec.update({"id": "a" + secrets.token_hex(4), "createdBy": by, "assignedAt": int(time.time() * 1000),
                "route": "paper", "graded": True, "quiz": True, "kind": kind,
                # valid_assignment は lesson を {key, n} に整える。提出箱の印はここで戻す
                "lesson": {"key": key, "n": n, "quiz": True}})
    if students is not None:
        rec["picked"] = True                 # 選んだ生徒だけ（クラス全員ではない）
    with LOCK:
        db = assignments(school)
        db[rec["id"]] = rec
        save_assignments(school, db)
    return rec


def desk_today(school, acc, mine, now=None):
    """今日やること（宿題チェック）と、今日おわったもの。

    チェックが要る回 ＝ 期限が来て、写真は出ているのに評価がまだの生徒がいる回。
    コースごとに新しい 12 回まで見る（宿題チェックの回の札と同じ範囲）。**未評価が残っている回は、古くても出す** ――
    前は新しい3回だけで、4回目より前の未評価は講師に見えない仕事になっていた（2026-10-11、本番の意味の検査で発覚。
    回の札を 12 回にしたら、隠れていた未評価が見えた）。"""
    now = now or time.time()
    nowms = now * 1000
    D = _desk_load(school)
    tasks, done, rated_today = [], [], 0
    for key, p in mine.items():
        by = INSIGHT.lesson_bundles(course_asgs(D["asg"], key))
        for i, n in enumerate(_paper_due(by, nowms, D["sb"])[:12]):
            rows, st = INSIGHT.check_rows(by[n], [], D["rt"], D["sb"], {})
            if not st["n"]:
                continue
            today_n = INSIGHT.rated_today(rows, now)
            if i >= 3 and not st["todo"]:
                continue                     # 古い回は、未評価が残っているときだけ（終わった回は新しい3回ぶん）
            rated_today += today_n
            l = _lesson_row(p, n, by[n])
            row = {"key": key, "name": p.get("name") or key, "n": n,
                   "topic": l.get("topic") or "", "label": l.get("label"), "date": l.get("date") or "",
                   "dueAt": INSIGHT.due_of(by[n]), "ratedToday": today_n,
                   # 数の n（人数）は total に移す。そのまま重ねると「第何回」の n が人数で消える。
                   "total": st["n"], "submitted": st["submitted"], "rated": st["rated"],
                   "todo": st["todo"], "missing": st["missing"]}
            if st["todo"]:
                tasks.append(row)
            elif today_n:
                done.append(row)
    tasks.sort(key=lambda x: (x["dueAt"], x["name"]))
    done.sort(key=lambda x: (x["dueAt"], x["name"]))
    return {"tasks": tasks, "done": done, "ratedToday": rated_today,
            "today": INSIGHT.today_of(now)}


def desk_check(school, acc, mine, key, n=None, now=None):
    """宿題チェックのページ。その回の全員と、切り替え用のコース・回。"""
    p = mine[key]
    nowms = (now or time.time()) * 1000
    D = _desk_load(school)
    by = INSIGHT.lesson_bundles(course_asgs(D["asg"], key))
    ns = _paper_due(by, nowms, D["sb"])
    lessons_out = []
    for m in ns[:12]:                      # 回の札。種類（漢字テスト・計算テスト…）でしぼれるように、4回より前も並べる
        _rows, st = INSIGHT.check_rows(by[m], [], D["rt"], D["sb"], {})
        l = _lesson_row(p, m, by[m])
        lessons_out.append({"n": m, "topic": l.get("topic") or "", "label": l.get("label"), "kind": l.get("kind") or "",
                            "quiz": bool(l.get("quiz")), "picked": bool(l.get("picked")), "date": l.get("date") or "",
                            "dueAt": INSIGHT.due_of(by[m]), "todo": st["todo"], "rated": st["rated"],
                            "submitted": st["submitted"], "total": st["n"]})
    if n is None or n not in by:
        todo = [x for x in lessons_out if x["todo"]]
        n = todo[0]["n"] if todo else (lessons_out[0]["n"] if lessons_out else None)
    courses_out = []
    for k2, p2 in sorted(mine.items(), key=lambda kv: (kv[1].get("name") or kv[0])):
        by2 = INSIGHT.lesson_bundles(course_asgs(D["asg"], k2))
        todo = 0
        for m in _paper_due(by2, nowms, D["sb"])[:12]:       # 今日やること（desk_today）と同じ範囲で数える
            todo += INSIGHT.check_rows(by2[m], [], D["rt"], D["sb"], {})[1]["todo"]
        courses_out.append({"key": k2, "name": p2.get("name") or k2, "todo": todo})
    head = {"key": key, "name": p.get("name") or key, "subject": p.get("subject") or "",
            "grade": p.get("grade") or "", "use": courses.use_level(p)}
    if n is None:
        return {"course": head, "lesson": None, "lessons": [], "courses": courses_out,
                "rows": [], "stats": None}
    roster = [{"sid": x, "label": y} for x, y in D["labels"].items()]
    rows, st = INSIGHT.check_rows(by[n], roster, D["rt"], D["sb"], {})
    l = _lesson_row(p, n, by[n])
    return {"course": head,
            "lesson": {"n": n, "topic": l.get("topic") or "", "label": l.get("label"), "kind": l.get("kind") or "",
                       "quiz": bool(l.get("quiz")), "picked": bool(l.get("picked")), "date": l.get("date") or "",
                       "dueAt": INSIGHT.due_of(by[n])},
            "lessons": lessons_out, "courses": courses_out, "rows": rows, "stats": st}


def desk_rate(school, acc, mine, d):
    """宿題チェックの評価。**束の全件に同じ評価**を入れ、写真は「見た」にする。v が null なら消す。"""
    key = str(d.get("key") or "")[:48]
    p = mine.get(key)
    if p is None:
        raise PermissionError("担当外のコースです")
    try:
        n = int(d.get("n"))
    except (TypeError, ValueError):
        raise ValueError("何回目の宿題かが分かりません")
    sid = str(d.get("sid") or "")
    if not SAFE_SID.match(sid):
        raise ValueError("生徒が分かりません")
    touch = "v" in d                 # v の鍵が無いときは、ひとことだけ（評価に触らない）
    v = d.get("v")
    if v is not None:
        try:
            v = int(v)
        except (TypeError, ValueError):
            raise ValueError("評価は1〜5で入れてください")
        if not ratescale.valid(v):
            raise ValueError("評価は1〜5で入れてください")
    items = [a for a in course_asgs(assignments(school), key)
             if (a.get("lesson") or {}).get("n") == n]
    b = INSIGHT.student_bundle(items, sid)
    if not b["paper"]:
        raise ValueError("この生徒に、この回の紙の宿題はありません")
    if touch:
        with LOCK:
            db = ratings(school)
            for a in b["paper"]:
                per = db.setdefault(a["id"], {})
                if v is None:
                    per.pop(sid, None)
                    if not per:
                        db.pop(a["id"], None)
                else:
                    per[sid] = ratescale.record(v, acc["sid"])
            save_ratings(school, db)
    # 理解が心配（講師だけの印。評価と一緒でも、あとからでも付けられる。生徒の画面には出ない）
    worry = d.get("worry")
    if worry is not None:
        with LOCK:
            db = ratings(school)
            for a in b["paper"]:
                per = db.get(a["id"]) or {}
                if sid in per:
                    per[sid]["worry"] = bool(worry)
            save_ratings(school, db)
    note = d.get("note")
    if b["head"]:
        subs = SUB.of_assignment(school, b["head"]["id"])
        if sid in subs and ((touch and v is not None) or note is not None):
            # ひとことの無い評価は、ひとことに触らない（読んでから書くと、同時に届いたひとことを消す。#13）
            SUB.mark_seen(school, b["head"]["id"], sid, acc["sid"],
                          (str(note)[:200] if note is not None else None))
    audit(school, acc["sid"], "rate_bundle", "%s#%d" % (key, n), sid)
    try:
        blob = (paths.load(progress_path(school, sid), None) or {}).get("blob") or {}
        c = hw_cache()
        mine_asg = [x for x in assignments(school).values() if sid in students_for(school, x, c)]
        update_summary(school, sid, blob, mine_asg)
    except (IOError, BadPath, KeyError):
        pass
    return {"ok": True, "v": v, "targets": [a["id"] for a in b["paper"]]}


def desk_overview(school, acc, mine):
    """成績の「すべて」：担当コースの札。テコ入れ候補を先に。"""
    D = _desk_load(school)
    rows = []
    for key, p in mine.items():
        ctx = insight_ctx(school, key, p, D["asg"], D["labels"], D["rt"], D["sb"], D["weak"],
                          D["sc"], D["cache"])
        m = INSIGHT.course_matrix(ctx)
        row = INSIGHT.overview_row({"key": key, "name": p.get("name") or key,
                                    "grade": p.get("grade") or "",
                                    "subject": p.get("subject") or ""}, m)
        # 個別の宿題を持つ生徒の数（札に「個別 3人」と出す）
        nn = next_n_of(p)
        row["personal"] = len([sid for sid, rs in PERSONAL.rules_of(school, key).items()
                               if any(r.get("until") is None or int(r.get("until")) >= nn for r in rs)])
        rows.append(row)
    rows.sort(key=lambda r: (0 if r["flag"] else 1,
                             (r["latest"] or {}).get("und", 999) if r["latest"] else 999,
                             r["name"] or ""))
    return {"courses": rows, "yellow": INSIGHT.YELLOW, "recent": INSIGHT.RECENT}


def score_summary(t):
    return {"id": t.get("id"), "name": t.get("name"), "date": t.get("date"), "kind": t.get("kind"),
            "cols": [{"label": c.get("label"), "max": c.get("max"), "lessons": c.get("lessons") or []}
                     for c in (t.get("cols") or [])],
            "n": len(t.get("rows") or {})}


def desk_course(school, acc, mine, key):
    """成績のコース：単元・生徒・テスト・次の回。"""
    p = mine[key]
    D = _desk_load(school)
    ctx = insight_ctx(school, key, p, D["asg"], D["labels"], D["rt"], D["sb"], D["weak"],
                      D["sc"], D["cache"])
    m = INSIGHT.course_matrix(ctx)
    nn = next_n_of(p)
    rules = PERSONAL.rules_of(school, key)
    nxt = next_lesson_of(p) or {}
    students = []
    for x in m["students"]:
        live = [r for r in rules.get(x["sid"], [])
                if r.get("until") is None or int(r.get("until")) >= nn]
        students.append({"sid": x["sid"], "label": x["label"], "avg": x["avg"],
                         "subRate": x["subRate"], "missed": x["missed"], "rules": len(live),
                         "cells": {str(k): v for k, v in x["cells"].items()}})
    return {"course": {"key": key, "name": p.get("name") or key, "subject": p.get("subject") or "",
                       "grade": p.get("grade") or ""},
            "units": m["units"], "students": students,
            "yellow": INSIGHT.YELLOW, "recent": INSIGHT.RECENT,
            "next": {"n": nn, "date": nxt.get("date") or "", "topic": nxt.get("topic") or "",
                     "label": nxt.get("label")},
            "tests": [score_summary(t) for t in ctx["tests"]],
            "weekly": [{"id": w.get("id"), "text": w.get("text") or "", "source": w.get("source") or ""}
                       for w in (p.get("weekly") or [])],
            "presets": PRESETS.list_of(school, key),
            "board": desk_board(school, key, p)}


def desk_board(school, key, p):
    """コースの「個別の宿題」の一覧：いま効いている決まりを持つ生徒と、その決まり。

    「今、誰に何の宿題を出しているか」をここ1か所で答える（本人の指示）。
    決まりがプリセットから作られていれば、その名前（origin.name）で束ねられる。"""
    nn = next_n_of(p)
    names = unit_names(p)
    labels = desk_labels(school)
    # クラス替えで出ていった生徒の決まりは、このコースではもう効かない（受け取り手でない）。
    # 「いま効いている」の一覧に出さない。決まりそのものは消さない（戻ってきたら、また効く）。
    gone = set()
    if not p.get("students"):
        gone = {a.get("sid") for a in accounts(school).values()
                if a.get("role") == "student" and moved_out(a, p.get("classes"))}
    out = []
    for sid, rules in PERSONAL.rules_of(school, key).items():
        if sid in gone:
            continue
        live = []
        for r in rules:
            if not (r.get("until") is None or int(r.get("until")) >= nn):
                continue
            what, span = PERSONAL.describe(r, names)
            og = r.get("origin") or {}
            live.append({"id": r.get("id"), "kind": r.get("kind"), "text": what, "span": span,
                         "preset": og.get("preset") or "", "name": og.get("name") or "",
                         # 生徒へのひとことと、その返事（わかった／質問あり）。一覧に「」で出す
                         "msg": r.get("msg") or "", "ack": r.get("ack") or None})
        if live:
            out.append({"sid": sid, "label": labels.get(sid, sid), "rules": live})
    out.sort(key=lambda x: x["label"])
    return out


_GROWTH = {}                 # (校舎, sid) → (時刻, 返事)。ホームを開くたびに全コースを数え直さない
GROWTH_TTL = 120


def student_growth(school, sid, now=None):
    """生徒の「成績の伸び」：受けているコースごとの、単元ごとの理解度（講師の画面と同じ数）。

    講師と生徒が**同じ数字**で話せるように、insight.course_matrix をそのまま使う。
    名前は出さない（自分の分だけ）。クラスの平均も渡さない ―― 比べさせるためではなく、
    自分が伸びているかを見せるための数。"""
    now = now or time.time()
    hit = _GROWTH.get((school, sid))
    if hit and now - hit[0] < GROWTH_TTL:
        return hit[1]
    D = _desk_load(school)
    db_acc = accounts(school)
    out = []
    try:
        plans = courses.all_courses(school)
    except (IOError, OSError, BadPath):
        plans = {}
    # 受けている教科（アプリの教科）だけ。アプリを使わないコース（紙）は入れない。
    acc0 = [a for a in db_acc.values() if a.get("sid") == sid]
    subs_on = None
    if acc0:
        try:
            subs_on = profile_of(dict(acc0[0], school=school)).get("appSubjects")
        except (IOError, OSError, BadPath, TypeError, ValueError):
            subs_on = None
    by_sub = {}
    for key in sorted(plans):
        p = plans[key]
        if not courses.app_on(p):
            continue
        sub = p.get("subject") or ""
        if subs_on is not None and sub not in subs_on:
            continue
        try:
            who = courses.receivers(school, p, db_acc)
        except (IOError, OSError, BadPath, KeyError, ValueError):
            continue
        keep = None
        if sid not in who:
            # クラス替えで出ていったコースも、そこで出た宿題があれば入れる。
            # 入れないと、移った月に「成績の伸び」から前のクラスの単元がまるごと消える（伸びが縮んで見える）。
            if not (acc0 and not p.get("students") and moved_out(acc0[0], p.get("classes"))
                    and any(sid in (a.get("students") or []) for a in course_asgs(D["asg"], key))):
                continue
            keep = {sid}
        ctx = insight_ctx(school, key, p, D["asg"], D["labels"], D["rt"], D["sb"], D["weak"],
                          D["sc"], D["cache"], keep=keep)
        m = INSIGHT.course_matrix(ctx)
        tr = INSIGHT.student_trend(m, sid, p.get("lessons"))
        review = {u["n"]: bool(u.get("review")) for u in m["units"]}
        units = [{"n": u["n"], "label": u.get("label"), "topic": u["topic"], "date": u.get("date"),
                  "u": u["u"], "review": review.get(u["n"], False), "key": key} for u in tr["units"]]
        # クラス替えの日で切る：出ていったコースは移る前の単元だけ、入ったコースは移る前の空の単元を落とす。
        # （同じ単元が両方のクラスにあるので、切らないと空きの点が混ざって線が途切れる）
        if acc0 and not p.get("students"):
            out_d, in_d = move_edges(acc0[0], p.get("classes"))
            if keep and out_d:
                units = [u for u in units if (u.get("date") or "") < out_d]
            elif in_d:
                units = [u for u in units if (u.get("date") or "") >= in_d or u.get("u") is not None]
        g = by_sub.setdefault(sub, {"key": key, "keys": [], "name": sub, "subject": sub,
                                    "grade": p.get("grade") or "", "units": [], "avg": None, "subRate": None,
                                    "rated": -1})
        g["keys"].append(key)
        g["units"] += units
        rated = len([u for u in units if u.get("u") is not None])
        if rated > g["rated"]:
            g.update({"rated": rated, "key": key, "avg": tr.get("avg"), "subRate": tr.get("subRate")})
    # **教科ごとに1行。** 同じ教科のコースが2つあれば（学年のコースとクラスのコース）、単元を日付でつないで1本にする。
    # 同じ日・同じ単元の重なりは1つに。番号 n は日付順に振り直す（図は n の順で並べる）。
    for sub, g in sorted(by_sub.items()):
        seen = set()
        merged = []
        for u in sorted(g["units"], key=lambda x: (x.get("date") or "", x.get("n") or 0)):
            k = (u.get("date") or "", u.get("topic") or "")
            if k in seen:
                continue
            seen.add(k)
            merged.append(u)
        merged = merged[-8:]
        for i, u in enumerate(merged):
            u["n"] = i + 1
        g.pop("rated", None)
        g["units"] = merged
        out.append(g)
    data = {"courses": out}
    if len(_GROWTH) > 2000:
        _GROWTH.clear()
    _GROWTH[(school, sid)] = (now, data)
    return data


def preview_for(school, key, p, sid):
    """次の回（まだ出していない回）の、その生徒の宿題。既定と、決まりを当てたあと。"""
    l = next_lesson_of(p)
    if not l or not l.get("date"):
        return None
    who = courses.receivers(school, p)
    base = {"n": int(l["n"]), "date": l.get("date") or "", "topic": l.get("topic") or "", "label": l.get("label")}
    if sid not in who:
        base.update({"default": [], "student": [], "none": True})
        return base
    due = courses.due_ms(p, p.get("lessons") or [], l)
    note = lessons.unit_note(l)
    recs, _own, _adv = lesson_recs(school, key, p, l, who, due, note)
    after = apply_personal(school, key, p, l, recs, due, note)

    def fmt(r):
        return {"title": r.get("title") or "", "source": r.get("source") or "",
                "base": PERSONAL.base_text(r.get("title")), "route": r.get("route") or "app",
                "extra": bool(r.get("extra")), "personal": bool(r.get("personal")),
                "graded": r.get("graded") is not False}
    base.update({"default": [fmt(r) for r in recs if sid in (r.get("students") or [])],
                 "student": [fmt(r) for r in after if sid in (r.get("students") or [])]})
    return base


def unit_names(p):
    """回の番号 → 画面での名前（教材の呼び名。呼び名の無い教材は単元名）。"""
    out = {}
    for l in p.get("lessons") or []:
        try:
            out[int(l.get("n"))] = lessons.unit_name(l)
        except (TypeError, ValueError):
            continue
    return out


def course_schedule(p, syl, key=""):
    """シラバスの単元を、このコースの授業日に並べる（syllabus.schedule に授業日の出し方を渡す）。
    授業の無い週（原本の日程表：休校・ハーフターム・冬期講習会）は飛ばす。"""
    skip = SOURCE.skip_dates(key) if key else set()

    def dates_of(start, count):
        return courses.dates(dict(p, start=start), start, count, skip)
    return SYLLABUS.schedule(syl, dates_of)


def desk_paces(school, acc):
    """担当コースごとの、教材の予定（シラバス）に対する進み具合。シラバスのあるコースだけ。"""
    today = time.strftime("%Y-%m-%d")
    out = {}
    for key, p in desk_courses(school, acc).items():
        syl = SYLLABUS.of_course(key, p)
        if not syl:
            continue
        sch = course_schedule(p, syl, key)
        if sch:
            out[key] = SYLLABUS.pace(syl, sch, p.get("lessons") or [], today,
                                     linked=(p.get("syllabus") == syl["id"]))
    return out


def desk_rules(school, key, p, sid):
    nn = next_n_of(p)
    names = unit_names(p)
    out = []
    for r in PERSONAL.rules_of(school, key, sid):
        what, span = PERSONAL.describe(r, names)
        live = r.get("until") is None or int(r.get("until")) >= nn
        out.append(dict(r, text=what, span=span, live=live))
    out.sort(key=lambda r: (0 if r["live"] else 1, -(r.get("at") or 0)))
    return out


def desk_student(school, acc, mine, key, sid):
    """成績の生徒：単元ごと・月ごとの推移、宿題の決まり、次の回の宿題。"""
    p = mine[key]
    D = _desk_load(school)
    ctx = insight_ctx(school, key, p, D["asg"], D["labels"], D["rt"], D["sb"], D["weak"],
                      D["sc"], D["cache"])
    if sid not in {r["sid"] for r in ctx["roster"]}:
        raise PermissionError("このコースの生徒ではありません")
    m = INSIGHT.course_matrix(ctx)
    own = [a for a in accounts(school).values() if a.get("sid") == sid]
    return {"student": {"sid": sid, "label": D["labels"].get(sid, sid),
                        "selfScores": ((own[0].get("selfScores") or []) if own else [])[-3:]},
            "course": {"key": key, "name": p.get("name") or key},
            "trend": INSIGHT.student_trend(m, sid, p.get("lessons")),
            "rules": desk_rules(school, key, p, sid),
            "next": preview_for(school, key, p, sid),
            "yellow": INSIGHT.YELLOW}


def desk_suggest(school, acc, mine, key, sid, n):
    p = mine[key]
    D = _desk_load(school)
    ctx = insight_ctx(school, key, p, D["asg"], D["labels"], D["rt"], D["sb"], D["weak"],
                      D["sc"], D["cache"])
    if sid not in {r["sid"] for r in ctx["roster"]}:
        raise PermissionError("このコースの生徒ではありません")
    m = INSIGHT.course_matrix(ctx)
    topic = _lesson_row(p, n).get("topic") or ""
    cnt = len(unit_items(p.get("subject") or "", p.get("grade") or "", topic))
    nn = next_n_of(p)
    names = unit_names(p)
    sg = INSIGHT.suggest(ctx, m, sid, n, nn, acc["sid"], log=insight_log(school),
                         weekly=p.get("weekly") or [], unit_items=cnt, names=names)
    return {"suggestions": sg, "next": nn,
            "nextName": names.get(nn) or (("第%d回" % nn) if isinstance(nn, int) else ""),
            "student": {"sid": sid, "label": D["labels"].get(sid, sid)},
            "unit": {"n": n, "topic": topic, "label": _lesson_row(p, n).get("label")}}


def publish_courses(school, actor="system", now=None):
    """コースの、授業日が来た回の宿題を出す。**何度呼んでも同じ結果になる。**

    講師が格子を開いたときと、生徒が宿題の一覧を開いたときに呼ぶ
    （呼ぶ側で PUBLISH_LOCK を持つこと）。出した回には印を付けるので二度出さない。

      1回の宿題のブロック（hw.items）ごとに1件
      上乗せ（extra）は、その回の受け取り手に入っている指名の生徒にだけ
      毎週固定（weekly）は、その週の最初の回を出すときに1件ずつ

    **受け取る生徒は、出すこの時点で宿題に書き込む。** あとで名簿や
    受講科目を直しても、出した宿題は変わらない。0人なら出さない ――
    students が空の宿題は、読むときにクラス全員に化ける（students_for）。
    """
    now = now or time.time()
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    made = []
    try:
        keys = [k for k, p in courses.all_courses(school).items()
                if courses.app_on(p) and _due_lesson(p, today, now)]
    except (IOError, OSError, BadPath):
        return made
    db_acc = accounts(school) if keys else {}
    for key in sorted(keys):
        # 1回出すごとに読み直す（毎週固定の位置と、出した印が変わるため）
        passed = set()
        for _ in range(60):
            p = lessons.plan(school, key)
            l = _due_lesson(p, today, now, passed)
            if not l:
                break
            if l.get("stopped"):
                # 講師が「この回の宿題を止める」を押した回。上乗せも毎週の分も出さない。
                lessons.mark_published(school, key, l.get("n"), ["-"])
                continue
            who = courses.receivers(school, p, db_acc)
            if not who:
                break                        # 0人のコースは出さない（印も付けない）
            rows = p.get("lessons") or []
            due = courses.due_ms(p, rows, l)
            note = lessons.unit_note(l)
            recs, own, advanced = lesson_recs(school, key, p, l, who, due, note)
            week = courses.iso_week(l["date"])
            # 生徒ごとの宿題の決まり（personal.py）。**出すこのときにだけ当てる。**
            # 出したあとの宿題には当てない（写真・評価と食い違うため）。
            recs = apply_personal(school, key, p, l, recs, due, note)
            if not recs:
                # 宿題がまだ入っていない回。**印は付けずに**先へ。授業日の夕方に
                # 入れても、次に呼ばれたときに出る。出さない回は講師が「止める」。
                passed.add(l.get("n"))
                continue
            with LOCK:
                db = assignments(school)
                for r in recs:
                    if r["id"] in db:           # 同じ中身の宿題がもう出ている（まれ）。別の ID にする
                        r["id"] = "a" + secrets.token_hex(5)
                    db[r["id"]] = r
                save_assignments(school, db)
            ids = [r["id"] for r in recs]
            if own:
                lessons.mark_published(school, key, l.get("n"), ids)
            else:
                # 毎週固定の分だけが出た。回の宿題はまだ無いので印は付けない
                # （毎週の分は weeklyAt で二度出さない）。
                passed.add(l.get("n"))
            if advanced:
                lessons.advance_weekly(school, key, advanced, week)
            for r in recs:
                audit(school, actor, "auto_publish", r["id"], r["title"][:40])
            made.append({"key": key, "n": l.get("n"), "title": recs[0]["title"],
                         "id": ids[0], "count": len(ids)})
    return made


# ------------------------------------------------------------------
# 合言葉 ―― サーバは、合言葉そのものを受け取らない（作るときも、入るときも）
# ------------------------------------------------------------------
# 前は、入るたびに合言葉を（TLS の中で）受け取り、scrypt / pbkdf2 のハッシュと照合していた。
# いまは SCRAM（server/scram.py・app/js/scram.js）。サーバが持つのは
#     alg="scram-sha256"・salt・iters・storedKey・serverKey
# だけで、端末は「証明」を送る。保存の値が漏れても、それだけでは入れない。
#
# 古い形の口座（"hash" を持つもの）は、もう入れない。
#   ・alg が "pbkdf2-600k" のもの（09-30 の束・管理ページが作ったもの）は、hash が
#     SCRAM の SaltedPassword そのものなので、合言葉なしで新しい形に直せる（upgrade_legacy）。
#   ・それより古いもの（scrypt・pbkdf2 20万回）は、合言葉が要る。作り直す（passwd・デモの作り直し）。


def upgrade_legacy(school):
    """古い形の口座を、直せるものだけ新しい形にする。(直した数, 直せずに残った数) を返す。"""
    fixed = left = 0
    with LOCK:
        db = accounts(school)
        for a in db.values():
            if a.get("alg") == SCRAM.ALG and a.get("storedKey"):
                continue
            h, salt = str(a.get("hash") or ""), str(a.get("salt") or "")
            if a.get("alg") == "pbkdf2-600k" and SCRAM.HEX64.match(h) and SCRAM.HEX32.match(salt):
                stored, server = SCRAM.keys_from_salted(bytes.fromhex(h))
                a.pop("hash", None)
                a.update({"alg": SCRAM.ALG, "iters": SCRAM.ITERS, "storedKey": stored, "serverKey": server})
                fixed += 1
            else:
                left += 1
        if fixed:
            save_accounts(school, db)
    return fixed, left


WORDS = ["river", "maple", "candle", "harbour", "meadow", "lantern", "pebble",
         "willow", "cobalt", "cedar", "amber", "thistle", "marble", "otter",
         "quartz", "juniper", "saffron", "walnut", "beacon", "clover",
         "anchor", "bramble", "copper", "dahlia", "ember", "fennel",
         "granite", "hazel", "indigo", "kestrel", "linnet", "mulberry",
         "nutmeg", "opal", "poplar", "rowan", "sorrel", "tulip",
         "verbena", "yarrow"]

# 合言葉に使うことば。**app/words.json が原本**（管理ページも同じ表から作る。二重に持たない）。
# ローマ字で読める短いことば 256語（neko・yama・sora…）。小4でもカードを見て打てる。
_PW_WORDS = []


def pw_words():
    if not _PW_WORDS:
        try:
            with io.open(os.path.join(APP_DIR, "words.json"), encoding="utf-8") as f:
                got = [w for w in (json.load(f).get("words") or [])
                       if isinstance(w, str) and re.match(r"^[a-z]{3,8}$", w)]
        except (IOError, OSError, ValueError, AttributeError):
            got = []
        _PW_WORDS.extend(got if len(set(got)) >= 128 else WORDS)
    return _PW_WORDS


# ことばの数。生徒 3語（256^3 × 1万 ≒ 2^37）、講師 4語（2^45）、管理者 5語（2^53）。
PW_WORDS_BY_ROLE = {"student": 3, "seat": 3, "teacher": 4, "admin": 5}


def make_password(role="student"):
    """読み上げられて、iPhoneでも打ちやすく、総当たりに耐える形（neko-yama-sora-4821）。

    前は「単語1つ＋4桁」（40万通り）だった。1つのIDに15分で8回しか試せなくても、
    IDが規則的（we4a01…）なので、500席に同時に当てられると1日で1席は開く計算になる。
    ハッシュの表が漏れたときは、1席あたり数秒で割れる。
    **強さを、試行制限ではなく合言葉そのものに持たせる。** 3語＋4桁で約1,700億通り。
    ことばの表は公開（app/words.json）。強さは「表から無作為に選ぶ」ことだけに依る。
    """
    ws = pw_words()
    n = PW_WORDS_BY_ROLE.get(role, 3)
    return "%s-%04d" % ("-".join(secrets.choice(ws) for _ in range(n)), secrets.randbelow(10000))


# 合言葉のそろえ方と、届いた値の形の確かめは scram.py に1つだけ（画面の scram.js と同じ）。
norm_pw = SCRAM.norm_pw
clean_verifier = SCRAM.clean_verifier
VERIFIER_ALG = SCRAM.ALG


# ------------------------------------------------------------------
# ログインの試行制限
#
# 127.0.0.1 だけで動かしているうちは要らない。しかし --host で外に
# 出した瞬間、これが無いとパスワードは「時間さえかければ open」になる。
# 記録はメモリ上だけ。サーバを再起動すれば消える（それでよい）。
# ------------------------------------------------------------------
FAILS = {}
FAIL_WINDOW = 15 * 60      # この秒数のあいだの失敗を数える
# 数え方は3つ（2026-09-30、第三者の検査から）。
#   ID×相手 … 同じ相手（IP）が、同じIDに 8回まで。ふつうの打ちまちがいは、ここで止まる。
#   ID      … どの相手からでも、同じIDに 300回まで。相手を次々に変えて当て続ける手口の上限
#             （1日で約3万回。合言葉は 2^37 通り以上あるので、当たらない）。
#   相手    … 同じ相手から、IDを変えながら 200回まで。
# 前は「同じIDに 8回」を相手を問わずに数えていたので、**よその人が8回まちがえるだけで、
# 本人が（正しい合言葉でも）15分入れなくなった。** 講師や管理者の ID は規則的なので、狙って止められた。
# **教室の Wi-Fi は全員が同じ相手に見える**ので、相手ごとの上限は広くしてある
# （合言葉そのものを強くしたので、ここは広くしてよい）。
MAX_PER_ID = 8             # 同じ相手から、同じIDへ
MAX_PER_ID_ALL = 300       # どの相手からでも、同じIDへ
MAX_PER_IP = 200           # 同じ相手から
FAIL_LOCK = threading.Lock()      # 数えるだけの鍵。ファイルの鍵（LOCK）とは別（中で LOCK を取らない）

# 入る手順の nonce（1回きりの数）。**サーバは、始めた分を覚えない**（覚えるのは、通った分だけ）。
#   nonce = <端末の cnonce> . <時刻> . <印>      印 = HMAC(置き場の秘密, ID|cnonce|時刻|salt|iters)
# 前は、始めた分（start）を全部メモリに覚えていた。上限（2万件）まで start だけを送り続けると、
# 関係のない人まで「混み合っています」で入れなくなった。いまは start で何も覚えないので、埋められない。
# 続き（finish）で印と時刻（2分）を確かめ、通った nonce だけを2分間覚えて、同じ証明の使い回しを止める。
# 印には salt が入っているので、始めたあとで合言葉が作り直されたら（salt が変わる）、続きは通らない。
NONCE_TTL = 120
USED = {}                  # 通った nonce → 期限。同じ証明を2度使わせない
# 起こすたびに変わる数。nonce の印に混ぜる。USED はメモリの中だけなので、混ぜないと
# 「通った証明を控えておき、サーバが起き直した直後（2分以内）にもう一度送る」が通った
# （2026-09-30、第三者の検査で見つかった。反映のたびにサーバは起き直す）。
BOOT = secrets.token_hex(8)


def _recent(key, now):
    hits = [t for t in FAILS.get(key, []) if now - t < FAIL_WINDOW]
    if hits:
        FAILS[key] = hits
    else:
        FAILS.pop(key, None)
    return hits


def ip_bucket(ip):
    """数えるときの「相手」。IPv6 は先頭の 64ビットでまとめる。

    IPv6 では、1軒の家・1台の端末が 2^64 個の番地を持つ。番地ごとに数えると、
    番地を変えるだけで「同じ相手から 8回」をいくらでも越えられる。"""
    if ":" in ip:
        try:
            import ipaddress
            return str(ipaddress.ip_network(ip.split("%")[0] + "/64", strict=False).network_address) + "/64"
        except ValueError:
            return ip
    return ip


def _fail_keys(login_id, ip):
    ip = ip_bucket(ip)
    return (("idip:%s|%s" % (login_id, ip), MAX_PER_ID),
            ("id:" + login_id, MAX_PER_ID_ALL),
            ("ip:" + ip, MAX_PER_IP))


def login_reserve(login_id, ip):
    """いま試させてよいかを確かめ、よければ**その場で1回ぶん数える**。

    だめなら (待つ秒数, None, どの上限か)。よければ (0, 印, "")。印は、通ったときに消す1回ぶん。
    どの上限か＝"idip"（同じ相手×同じID）・"id"（どの相手からでも同じID）・"ip"（同じ相手）。

    前は「確かめる」と「失敗を数える」が別々で、あいだに合言葉の照合があった。
    同じIDに 1,000本を同時に送ると、どれも「まだ 0回」を見て通り、8回の上限が効かない
    （確かめてから使うまでの隙間）。確かめた鍵の中で先に数えておけば、同時に来ても
    9本目からは通らない。通った1回は login_ok が消す。
    """
    now = time.time()
    with FAIL_LOCK:
        if len(FAILS) > 5000:                       # 名乗られたIDの数だけ増える。古いものを捨てる
            for k in list(FAILS.keys()):
                _recent(k, now)
        keys = _fail_keys(login_id, ip)
        for key, cap in keys:
            hits = _recent(key, now)
            if len(hits) >= cap:
                return int(FAIL_WINDOW - (now - min(hits))) + 1, None, key.split(":", 1)[0]
        for key, _cap in keys:
            FAILS.setdefault(key, []).append(now)
    return 0, now, ""


def login_blocked(login_id, ip):
    """いま試させてよいか（数えない）。だめなら (あと何秒待つべきか, どの上限か)。よければ (0, "")。"""
    now = time.time()
    with FAIL_LOCK:
        for key, cap in _fail_keys(login_id, ip):
            hits = _recent(key, now)
            if len(hits) >= cap:
                return int(FAIL_WINDOW - (now - min(hits))) + 1, key.split(":", 1)[0]
    return 0, ""


def login_failed(login_id, ip):
    now = time.time()
    with FAIL_LOCK:
        for key, _cap in _fail_keys(login_id, ip):
            FAILS.setdefault(key, []).append(now)


def login_ok(login_id, ip, stamp=None):
    """通った。その相手からそのIDへの失敗は忘れる。**ほかの数は、この1回ぶんだけ戻す。**

    前は相手の失敗も全部忘れていた。自分の席を1つ持っている人が、他人のIDを試す合間に
    自分の席へ入り直せば、相手ごとの上限が何度でも 0 に戻った。
    """
    with FAIL_LOCK:
        FAILS.pop("idip:%s|%s" % (login_id, ip_bucket(ip)), None)
        for key in ("id:" + login_id, "ip:" + ip_bucket(ip)):
            hits = FAILS.get(key)
            if hits and stamp is not None and stamp in hits:
                hits.remove(stamp)
                if not hits:
                    FAILS.pop(key, None)


def login_unreserve(login_id, ip, stamp):
    """数えた1回ぶんを、そのまま戻す（合言葉を試したわけではなかったとき）。ほかの失敗は消さない。"""
    with FAIL_LOCK:
        for key, _cap in _fail_keys(login_id, ip):
            hits = FAILS.get(key)
            if hits and stamp in hits:
                hits.remove(stamp)
                if not hits:
                    FAILS.pop(key, None)


# 締め出したことを、管理ページの「報告」に知らせる。同じIDは1時間に1回。
# 枠は **校舎ごと・上限の種類ごと** に1時間20件（知らせそのものを、ファイルを書かせ続ける道具にさせない）。
#   "idip" … 同じ相手から同じIDに8回。その相手からだけ、15分入れない（本人の打ちまちがいは、たいていこれ）
#   "id"   … あちこちから同じIDに300回。どこからも入れない（ねらわれている）
# 相手（IP）の上限に当たったときは知らせない ―― 止まったのは その相手で、ID ではない。
# 種類ごとに枠を分けるのは、8回ずつ20個のIDをたたくだけで「どこからも入れない」の知らせまで
# 止められないようにするため（2026-09-30、第三者の検査で見つかった）。
ALERTED = {}
ALERT_GAP = 3600
ALERT_MAX = 20


def login_alert(login_id, which):
    """このIDを、しばらく入れなくした。本人が困る前に、管理者が気づけるようにする。

    **あるIDかどうかを先に確かめる。** 先に枠を数えると、無いIDを20個たたくだけで、
    そのあとの本物の知らせを1時間止められた。
    """
    if which not in ("idip", "id"):
        return False
    try:
        school, acc = login_account(login_id)
    except (IOError, OSError, ValueError):
        return False
    if not school or not acc or acc.get("leftAt"):
        return False
    now = time.time()
    me = (school, which, login_id)
    with FAIL_LOCK:
        for k in [k for k, t in ALERTED.items() if now - t > ALERT_GAP]:
            ALERTED.pop(k, None)
        if me in ALERTED or len([k for k in ALERTED if k[:2] == me[:2]]) >= ALERT_MAX:
            return False
        ALERTED[me] = now
    try:
        ADMIN.add_guard(sys.modules[__name__], school, acc, login_id, everywhere=(which == "id"))
        audit(school, "", "login_locked", login_id, which)
        return True
    except (BadPath, ValueError, IOError, OSError):
        return False


def nonce_make(login_id, cnonce, salt, iters):
    ts = "%x" % int(time.time())
    mac = hmac.new(paths.secret(), ("nonce|%s|%s|%s|%s|%s|%d" % (BOOT, login_id, cnonce, ts, salt, int(iters))).encode("utf-8"),
                   hashlib.sha256).hexdigest()[:40]
    return "%s.%s.%s" % (cnonce, ts, mac)


def nonce_check(nonce, login_id, salt, iters):
    """続き（finish）で、nonce が「このIDに、この salt で、2分以内に、このサーバが出したもの」かを確かめる。"""
    parts = str(nonce or "").split(".")
    if len(parts) != 3 or not re.match(r"^[A-Za-z0-9_-]{16,64}$", parts[0]) or not re.match(r"^[0-9a-f]{1,12}$", parts[1]):
        return False
    try:
        ts = int(parts[1], 16)
    except ValueError:
        return False
    if not (0 <= time.time() - ts <= NONCE_TTL):
        return False
    want = hmac.new(paths.secret(), ("nonce|%s|%s|%s|%s|%s|%d" % (BOOT, login_id, parts[0], parts[1], salt, int(iters))).encode("utf-8"),
                    hashlib.sha256).hexdigest()[:40]
    return hmac.compare_digest(want, parts[2])


def nonce_use(nonce):
    """通った nonce を覚える。もう使われていたら False（同じ証明の使い回し）。"""
    now = time.time()
    with FAIL_LOCK:
        if len(USED) > 2000:
            for k in [k for k, exp in USED.items() if exp < now]:
                USED.pop(k, None)
        if USED.get(nonce, 0) >= now:
            return False
        USED[nonce] = now + NONCE_TTL + 5
    return True


def fake_salt(login_id):
    """無いID（や、もう入れない古い口座）にも、あるIDと同じ形の返事をするための塩。
    同じIDにはいつも同じ値（毎回変わると、無いことが分かる）。置き場の秘密から作る。"""
    return hmac.new(paths.secret(), ("salt|" + login_id).encode("utf-8"), hashlib.sha256).hexdigest()[:32]


_CODES = {"at": 0.0, "map": {}}


def school_for_prefix(login_id):
    """ID の頭（校舎コード）から、その ID が入るはずの校舎。無ければ None。1分だけ覚える。"""
    now = time.time()
    if now - _CODES["at"] > 60:
        m = {}
        for sc in paths.list_schools():
            try:
                m[school_code(sc)] = sc
            except (BadPath, IOError, OSError, ValueError):
                pass
        _CODES["map"], _CODES["at"] = m, now
    m = _CODES["map"]
    return m.get(login_id[:2]) or m.get(login_id[:1])


def login_account(login_id):
    """入る手順のための口座読み。(校舎, 口座 or None)。

    **無いIDでも、そのIDが入るはずの校舎（ID の頭の校舎コード）の口座の表を1回読む。**
    読まないと、返事の速さで「そのIDがあるかどうか」が分かる（ある ID 1.35ms・無い ID 0.54ms と測られた）。
    前は「どこかの校舎」を読んでいたので、校舎が2つ（本物とデモ）で大きさが違うと、やはり分かった
    （本物の校舎の ID 0.73ms・無い ID 0.33ms。2026-09-30、2回目の第三者の検査）。
    """
    ok = bool(SAFE_ID.match(login_id))
    guess = school_for_prefix(login_id) if ok else None
    school = paths.school_of_login(login_id) if ok else None
    try:
        if school:
            return school, accounts(school).get(login_id)
        if not guess:
            ss = paths.list_schools()
            guess = ss[0] if ss else None
        if guess:
            accounts(guess).get(login_id)
    except BadPath:
        pass
    return None, None


def make_sid():
    abc = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"   # 紛らわしい 0/O/1/I を外す
    return "".join(secrets.choice(abc) for _ in range(8))


# ------------------------------------------------------------------
# アカウント操作
# ------------------------------------------------------------------
def add_account(school, login_id, password, seat, role="student",
                level="j2", class_id="j2a", classes=None, subjects=None, verifier=None):
    """氏名は受け取らない。持つのは出席番号（`07`）だけ。

    講師の画面には「中2A-07」と出る。誰かは先生が手元の名簿で分かる。
    こうしておくと、このサーバが破られても流出するのは
    「ある番号が単語を51語やった」という事実だけになる。

    ログインIDは校舎をまたいで一意にする。同じIDが2校舎にできると
    「ログインはできるが自分の宿題が出てこない」という追いにくい壊れ方をする。
    先に索引を押さえてから、校舎のファイルに書く。

    verifier（scram.make_verifier の形）を渡すと、合言葉そのものは受け取らずに作る
    （管理ページ・手元の道具。clean_verifier が形を確かめる）。
    password を渡したとき（コマンド・デモ・検査）は、ここで同じ形に作る。保存するのは同じもの。

    **ハッシュの計算（0.2秒）は鍵の外、確かめて書くのは鍵の中。**
    前は「読む → 計算 → 書く」で、計算のあいだに別の人が足した席を、古い控えで上書きして消せた。
    """
    paths.check_school(school)
    login_id = login_id.strip().lower()
    if not SAFE_ID.match(login_id):
        raise ValueError("IDは英小文字・数字・. _ - で2〜32文字にしてください: %r" % login_id)
    if role not in ROLES:
        raise ValueError("役割が違います: %r" % (role,))
    seat = str(seat).strip()
    if not SAFE_SEAT.match(seat):
        raise ValueError("出席番号は英数字1〜8文字にしてください: %r" % seat)
    if role == "teacher" and classes == ["-"]:
        # コースだけを受け持つ講師。クラスの教科は見ず、担当コースの生徒だけを見る。
        classes = []
        course_only = True
    elif role == "teacher" and not classes:
        raise ValueError("講師には担当クラスを指定してください（--classes。コースだけなら --classes -）")
    else:
        course_only = False
    if verifier is not None:
        ver = clean_verifier(verifier)
    else:
        if len(norm_pw(password)) < 6:
            raise ValueError("パスワードは6文字以上にしてください")
        ver = SCRAM.make_verifier(password)
    rec = {
        "sid": make_sid(),
        "seat": seat,
        "role": role,
        "level": level,
        "classId": class_id,
        "classes": classes or [],
        "created": int(time.time()),
    }
    rec.update(ver)
    if role == "admin":
        rec["level"], rec["classId"], rec["classes"] = "", "", []
    if course_only:
        # コースしか持たない講師は assign を空の配列で持つ（持たないと、古い形に落ちて
        # classes のクラスの全教科が見える。teacher_pairs の説明）。
        rec["assign"] = []
    # 受講科目（国英／国数英…）。無い生徒は全教科とみなす（PLAN 規則2）。
    if subjects is not None:
        rec["subjects"] = [x for x in subjects if x in SUBJECT_CODE]
    with LOCK:
        other = paths.school_of_login(login_id)
        if other and other != school:
            raise ValueError("そのIDは校舎 %s ですでに使われています: %s" % (other, login_id))
        db = accounts(school)
        if login_id in db:
            raise ValueError("そのIDはすでにあります: %s" % login_id)
        # sid は記録の鍵。万に一つ重なると、2人の記録が1つのファイルに混ざる。
        used = {a.get("sid") for a in db.values()}
        while rec["sid"] in used:
            rec["sid"] = make_sid()
        db[login_id] = rec
        paths.bind_login(login_id, school)
        try:
            save_accounts(school, db)
        except BaseException:
            paths.unbind_login(login_id)      # 索引だけ残さない
            raise
    return rec


def touch_used(school, login_id, now=None):
    """「使った日」を口座に書く。呼ぶ側が日付を見てから呼ぶ（1日に1回で足りる）。書いた口座を返す。"""
    with LOCK:
        db = accounts(school)
        a = db.get(login_id)
        if not a:
            return None
        a["used"] = int(now or time.time())
        save_accounts(school, db)
        return a


def housekeep_once(dry=False):
    """毎日の片づけを1回：登録しかけの口座（1時間）と、3か月使われない口座。校舎ごとの結果を返す。"""
    me = sys.modules[__name__]
    out = {}
    for sc in paths.list_schools():
        try:
            n = 0
            if not dry:
                with LOCK:
                    n = JOIN.sweep(me, sc)
            # 学年の繰り上げ（新年度のはじまりの日に、1回だけ）。dry なら、その日かどうかだけ。
            rolled = RETIRE.roll_due(me, sc) if dry else RETIRE.roll(me, sc)
            # 答案の写真：採点から1週間で消す（返した添削は残す）。半年たったものは全部消す（2026-10-08）
            pruned = SUB.prune(sc, days=SUB.KEEP_DAYS, dry=dry, graded_days=SUB.GRADED_KEEP_DAYS)
            out[sc] = {"pending": n, "retired": RETIRE.run(me, sc, dry=dry), "rolled": rolled, "pruned": pruned}
        except Exception as e:                       # 1校のまちがいで、ほかの校舎の片づけを止めない
            out[sc] = {"error": "%s: %s" % (type(e).__name__, e)}
    return out


HOUSEKEEP_EVERY = 3600


def housekeeping():
    """裏で1時間に1回、片づけを流す（serve が起こす）。起動の1分後から。"""
    time.sleep(60)
    while True:
        try:
            housekeep_once()
        except Exception:
            pass
        time.sleep(HOUSEKEEP_EVERY)


def cmd_housekeep(args):
    """片づけを今すぐ1回流す。--dry なら、消すはずの ID を見せるだけ。"""
    res = housekeep_once(dry=args.dry)
    for sc in sorted(res):
        r = res[sc]
        if r.get("error"):
            print("  %-16s × %s" % (sc, r["error"]))
            continue
        ids = r.get("retired") or []
        print("  %-16s %s %d件%s" % (sc, "3か月使われていない口座（消すはずのもの）" if args.dry else "破棄した口座",
                                    len(ids), ("　" + "・".join(ids[:20])) if ids else ""))
        if r.get("rolled"):
            print("  %-16s %s" % ("", ("きょうは学年を繰り上げる日です（%s）" % r["rolled"]) if args.dry else
                                  "学年を繰り上げました：上がった %(up)d・卒業 %(grad)d・クラスを聞く %(ask)d" % r["rolled"]))
    if args.dry:
        print("\n見ただけです。何も消していません（本番に切り替えた校舎だけが対象。サーバは1時間ごとに自分で流します）。")
    return 0


def revoke_tokens(login_id):
    """その人の合言葉（入ったままの画面）を全部無効にする。**呼ぶ側で LOCK を持つこと。**"""
    store = tokens()
    gone = [t for t, r in store.items() if r.get("loginId") == login_id]
    for t in gone:
        store.pop(t)          # 鍵はハッシュ。中身の loginId で引く
    if gone:
        save_tokens(store)
    return len(gone)


def free_seat(db, class_id, want, me=None):
    """そのクラスで空いている出席番号。want が空いていれば want、だめなら次の空き（2桁）。

    同じクラスに同じ番号が2人いると、塾内テストを席番号で合わせたとき別の生徒に点が入る。

    **まだ渡していない席（seat）と、在籍を終えた生徒の番号も「使っている」と数える。**
    カードには番号が刷ってある。クラス替えで来た生徒が先にその番号を取ると、あとでカードを
    受け取った子（や、戻ってきた子）の番号がずれて、「カードは 05 なのに画面は 31」になる
    （2026-09-30、第三者の検査から）。me は自分のID（自分の番号は、自分には空いている）。
    """
    taken = {a.get("seat") for lid, a in db.items()
             if lid != me and a.get("role") in ("student", "seat")
             and a.get("classId") == class_id}
    if want and want not in taken:
        return want
    for i in range(1, 100):
        s2 = "%02d" % i
        if s2 not in taken:
            return s2
    return want


def join_open_homework(school, login_ids, now=None):
    """在籍になったばかりの生徒を、**まだ期限の来ていない宿題**の受け取り手に足す。足した数を返す。

    宿題の受け取り手は、出す時点で宿題に書き込む（publish_courses）。だから、授業日のあとで
    カードを受け取って初めて入った子・「使う」にした子・リンクを引き換えた子は、そのままだと
    次の回まで「いま出ている宿題は ありません」になり、講師の宿題チェックにも出ない
    （2026-09-30、第三者の検査で見つかった）。

    決まりは、クラス替えで入ってきた生徒と同じ（move_transfers の "in"）：
      ・在籍クラスで受けるコースだけ（指名のコースは、指名されたときに決まる）
      ・受講科目が決まっている生徒は、その教科だけ
      ・期限の過ぎた宿題・上乗せ・個別・「選んだ生徒だけ」の提出箱には足さない
      ・**クラス全員に出した提出箱（過去問・小テスト）には足す**（2026-10-12 本人：新しく作った中3R の口座に過去問が無かった。
        提出箱は出す時点の受け取り手を書き込むので、あとから入った子は足さないと一生見えない）
    **呼ぶ側で LOCK を持つこと。** 口座（accounts.json）を書いたあとで呼ぶ。
    """
    now = now or time.time()
    nowms = now * 1000
    db = accounts(school)
    plans = courses.all_courses(school)
    asg = assignments(school)
    n = 0
    for lid in login_ids:
        a = db.get(lid) or {}
        if a.get("role") != "student" or a.get("leftAt") or not a.get("sid"):
            continue
        sid, subj, cid = a["sid"], a.get("subjects"), a.get("classId")
        for aid, x in asg.items():
            if not isinstance(x, dict) or int(x.get("dueAt") or 0) <= nowms:
                continue
            p = plans.get((x.get("lesson") or {}).get("key") or "")
            if not p or p.get("students"):
                continue
            if cid not in (p.get("classes") or []) or (subj and p.get("subject") not in subj):
                continue
            studs = x.get("students")
            if not studs or sid in studs:
                continue                      # 空（クラス全員に出ている）か、もう入っている
            if x.get("extra") or x.get("personal") or x.get("picked"):
                continue                  # 上乗せ・個別・「選んだ生徒だけ」の提出箱は、指名で決まる
            # ためし運用のデモの宿題（demo_trial.py の demo の印）にも足す。**新しい口座が、その日のうちに
            # 今の宿題を見られること**が先（2026-10-10 本人：新しく作った中3R の口座に宿題が出なかった）。
            # 片づけ（--clean）は、本物の生徒の記録が付いた宿題を消さずに残す。
            studs.append(sid)
            x.setdefault("joined", []).append({"sid": sid, "at": int(now)})
            n += 1
    if n:
        save_assignments(school, asg)
    return n


def leave_open_homework(school, login_ids, now=None):
    """クラスや受講科目が変わった生徒を、**もう受けないコースの・期限前の**宿題の受け取り手から外す。外した数を返す。

    記録（写真・評価・アプリの達成）のある宿題からは外さない（クラス替えの "keep" と同じ）。
    外して受け取り手が0人になる宿題は、ほかの人の記録が無ければ消す（空の受け取り手は「クラス全員」に化けるため）。
    足す側は join_open_homework。**呼ぶ側で LOCK を持つこと。**
    """
    now = now or time.time()
    nowms = now * 1000
    db = accounts(school)
    plans = courses.all_courses(school)
    asg = assignments(school)
    subs_db, rt = SUB.load(school), ratings(school)
    n = 0
    for lid in login_ids:
        a = db.get(lid) or {}
        sid, subj, cid = a.get("sid"), a.get("subjects"), a.get("classId")
        if not sid:
            continue
        hw = (blob_of(school, sid) or {}).get("hw") or {}
        for aid in list(asg.keys()):
            x = asg.get(aid)
            if not isinstance(x, dict) or int(x.get("dueAt") or 0) <= nowms:
                continue
            studs = x.get("students") or []
            if sid not in studs:
                continue
            p = plans.get((x.get("lesson") or {}).get("key") or "")
            if not p or p.get("students"):
                continue                  # 指名のコースは、指名で決まる
            if cid in (p.get("classes") or []) and (not subj or p.get("subject") in subj):
                continue                  # まだ受けている（科目の指定が無い生徒は全教科）
            if _has_record(subs_db, rt, hw, aid, sid):
                continue
            studs.remove(sid)
            if x.get("joined"):
                x["joined"] = [j for j in x["joined"] if j.get("sid") != sid]
            x.setdefault("moved", []).append({"sid": sid, "op": "out", "batch": "subjects", "at": int(now)})
            n += 1
            if not studs and not (subs_db.get(aid) or rt.get(aid)):
                asg.pop(aid)
    if n:
        save_assignments(school, asg)
    return n


def activate_seat(db, login_id, by=""):
    """まだ渡していない席（seat）を、在籍の生徒（student）にする。変えたら True。db を直すだけ（保存は呼ぶ側）。"""
    a = db.get(login_id)
    if not a or a.get("role") != "seat":
        return False
    a["seat"] = free_seat(db, a.get("classId"), a.get("seat"), me=login_id)
    a["role"] = "student"
    a["usedAt"] = int(time.time())
    if by:
        a["usedBy"] = by
    return True


def school_managed(school):
    """管理者（admin）のいる校舎か。いる校舎では、席を作るのは管理ページだけにする。"""
    try:
        return any(a.get("role") == "admin" and not a.get("leftAt") for a in accounts(school).values())
    except BadPath:
        return False


def seat_of(acc):
    """古い形式（氏名を持っていたころ）も読めるようにしておく。
    移行は anonymise コマンドで行う。"""
    return acc.get("seat") or acc.get("name") or "??"


def seat_label(class_name, seat):
    """画面の呼び名。番号なら「小4α-07」、初回登録の口座（seat が ID）なら「小4α s-042」。"""
    seat = str(seat or "")
    if re.match(r"^[a-z]-\d+$", seat):
        return ("%s %s" % (class_name, seat)).strip()
    return "%s-%s" % (class_name, seat)


def profile_of(acc):
    """クライアントに渡してよい部分だけ。
    塩もハッシュも、そして氏名も外に出さない ―― そもそも持っていない。
    画面に出す「中2A-07」は、classId と seat からクライアント側で組む。"""
    school = acc.get("school", "")
    out = {
        "sid": acc["sid"], "seat": seat_of(acc), "role": acc["role"],
        "level": acc["level"], "classId": acc["classId"],
        # 講師の担当クラスは、旧 assign とコースから引く（teacher_classes）。
        # アカウントの classes は名簿の索引で、コースの担当は入っていない。
        "classes": ((["*"] if teacher_classes(acc) is None else teacher_classes(acc))
                    if acc.get("role") == "teacher" else acc.get("classes", [])),
        "school": school, "schoolName": school_name(school) if school else "",
        # 講師の担当。画面はこれで週の時間割を描く。
        # 生徒のアカウントには入らない（assign を持たないため空）。
        "assign": teacher_slots(acc) if acc.get("role") == "teacher" else [],
        # 受講科目。生徒の画面は、ここに無い教科の毎日テストを出さない。
        "subjects": acc.get("subjects") or [],
    }
    if acc.get("role") == "student" and school:
        # 組分けの申告：テストの結果が出てから2週間、「クラスは どちらに なりましたか」を聞く（まだ答えていない生徒に）。
        try:
            ask = JOIN.place_ask(sys.modules[__name__], school, acc)
        except (BadPath, IOError, OSError, ValueError):
            ask = None
        if ask:
            out["placeAsk"] = ask
        if acc.get("grad"):
            out["grad"] = True                   # 卒業（学年の繰り上げで、中3がクラスから外れた）
    # 管理者のいる校舎か。いる校舎では、席（IDと合言葉）は管理ページで作る（講師の画面に入口を出さない）。
    if acc.get("role") == "teacher" and school and school_managed(school):
        out["managed"] = True
    # 生徒：受講科目のうち、アプリを使うコースの教科と、紙のままの教科。
    # 画面はアプリの教科だけを出し、紙の教科は「紙の宿題」と1行添える。
    if acc.get("role") == "student" and school:
        on, off = [], []
        try:
            allc = courses.all_courses(school)
            cid = acc.get("classId") or ""
            subs = list(acc.get("subjects") or [])
            if not subs:
                # 受講科目が名簿に無い生徒は、在籍クラスを含むコースの教科を受講科目とみなす
                subs = sorted({p.get("subject") for p in allc.values()
                               if p.get("subject") and cid in (p.get("classes") or []) and courses.active(p)})
            use = {}
            for sub in subs:
                k = courses.key_for(school, cid, sub, acc.get("level") or "")
                (on if (k in allc and courses.app_on(allc[k])) else off).append(sub)
                use[sub] = courses.use_level(allc[k]) if k in allc else 0
        except (IOError, OSError, BadPath, TypeError, ValueError):
            on, off, use = list(acc.get("subjects") or []), [], {}
        # 教科の手がかりが1つも無ければ（コースの無い校舎）、印を置かない ―― 画面は今までどおり学年の全教科
        if on or off:
            out["appSubjects"], out["paperSubjects"] = on, off
            # 教科ごとの導入の段階（courses.use_level）。画面は 2 未満なら写真の「出す」を出さず、
            # 4 未満なら毎日テストにその教科を出さない。
            out["useBySubject"] = use
    return out


def find_by_sid(school, sid):
    for login_id, acc in accounts(school).items():
        if acc["sid"] == sid:
            return login_id, acc
    return None, None


# ------------------------------------------------------------------
# HTTP
# ------------------------------------------------------------------
LOGIN_BODY_MAX = 4096      # 入る手順の本文は 1KB に満たない（ID・nonce・証明）


class Handler(SimpleHTTPRequestHandler):

    server_version = "TubeSchools/0.1"
    # 何も送ってこない接続を、いつまでも待たない（1本の読み書きが60秒止まったら切る）。
    timeout = 60

    # ---- 下ごしらえ ----
    def log_message(self, fmt, *args):
        """画面に出すのは経路だけ。内部IDは伏せる ―― 端末を人に見せた
        ときや、ログを貼って相談したときに漏れる経路を減らす。
        誰が何を見たかは audit.log のほうに残る。"""
        if self.path.startswith("/api/"):
            # **問い合わせ（?…）は落とす。**
            # 印刷の紙と、出された答案の画像は、見出しに合言葉を入れられない
            # ので ?t= で渡している。そのまま書き出すと、画面を人に見せた
            # ときや、ログを貼って相談したときに合言葉ごと漏れる。
            path = re.sub(r"/(p|assignments|submissions)/[^/?]+", r"/\1/…",
                          self.path.split("?")[0])
            sys.stderr.write("  %s %s\n" % (self.command, path))

    def end_headers(self):
        # API の返事は端末にも間の機械にも残さない（個人の記録を含む）。
        # 画面のファイル（js・css）は **no-cache** ―― 毎回サーバに確かめるが、
        # 変わっていなければ 304 で済み、本体（合わせて 900KB）を送り直さない。
        # 前は no-store で、開くたびに全部を送り直していた（遅さの主因）。
        # 直したものはすぐ出る（ETag が変わる）。
        api = self.path.startswith("/api/")
        self.send_header("Cache-Control", "no-store" if api else "no-cache")

        # 外部を一切参照しないアプリなので、CSPは 'self' で閉じきれる。
        # 万一どこかに文字列を差し込まれても、外へ送り出す先が無い。
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; "
                         "script-src 'self'; "
                         "style-src 'self' 'unsafe-inline'; "   # 属性のstyleを使っている
                         "img-src 'self' data:; "
                         "font-src 'self' data:; "              # 書体を埋め込んである
                         "connect-src 'self'; "
                         "form-action 'none'; "
                         "base-uri 'none'; "
                         "frame-ancestors 'none'")
        # 枠の中に置かせない。埋め込み枠だと Safari が保存を遮断して
        # 記録が静かに消える（HANDOVER 5.1）。防御と可用性が一致する例。
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy",
                         "geolocation=(), camera=(), microphone=(), payment=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        # 中継がHTTPSで受けているときだけ、以後もHTTPSを強制する。
        # LANで http のまま試すこともあるので、無条件には付けない
        # （付けると、その端末はもうhttpで開けなくなる）。
        if self.headers.get("X-Forwarded-Proto") == "https":
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        SimpleHTTPRequestHandler.end_headers(self)

    def reply(self, code, obj):
        """返事を返す。相手が対応していれば圧縮する。

        JSON は同じ鍵が何度も出てくるので、よく縮む。実測で

            宿題の一覧  21,838 → 2,798 バイト（7.8倍）
            名簿         4,670 →   889 バイト（5.3倍）
            自分の記録  14,575 → 3,892 バイト（3.7倍）

        全体で 5.3倍。**これは通信料に直接効く。** 300名の校舎で
        月あたり数GBの差になり、借りるサーバの選び方まで変わる。
        電波の弱い場所で開くときの待ち時間も、そのぶん短くなる。

        小さいものは圧縮しない。1KB未満だと、縮む量より
        ヘッダと処理の手間のほうが大きい。
        """
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        enc = None
        if len(body) >= 1024:
            accept = (self.headers.get("Accept-Encoding") or "").lower()
            if "gzip" in accept:
                try:
                    body = gzip.compress(body, 6)
                    enc = "gzip"
                except (OSError, ValueError):
                    enc = None
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if enc:
            self.send_header("Content-Encoding", enc)
            # 中身が同じでも圧縮の有無で別物になる。間の機械に
            # 取り違えさせない。
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def reply_html(self, code, text):
        """印刷用の紙を返す。JSON ではないので別に持つ。"""
        body = text.encode("utf-8")
        enc = None
        if len(body) >= 1024:
            if "gzip" in (self.headers.get("Accept-Encoding") or "").lower():
                try:
                    body = gzip.compress(body, 6)
                    enc = "gzip"
                except (OSError, ValueError):
                    enc = None
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if enc:
            self.send_header("Content-Encoding", enc)
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        # 印刷用の紙は名簿の中身を含む。間の機械に持たせない。
        self.send_header("Cache-Control", "no-store, private")
        self.end_headers()
        self.wfile.write(body)

    def reply_bytes(self, code, raw, mime):
        """答案の画像やPDFを、そのまま返す。

        安全のための頭書き（nosniff・CSP・no-store）は end_headers が
        まとめて付ける。**ここで no-store が効くのは都合がよい** ――
        答案は個人情報なので、間の機械にも端末にも残さない。

        Content-Disposition は inline。ダウンロードさせるのではなく、
        画面の中で見てもらう。
        """
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Content-Disposition", "inline")
        self.end_headers()
        self.wfile.write(raw)

    def body_json(self, limit=None):
        """本文を読む。**返すのは辞書だけ**（配列や文字列は、形のおかしい本文として None）。

        limit … 受ける大きさの上限。入る前の口（/api/login/*）は 4KB ―― だれでも送れる口で
        12MB を読んでから断ると、同時に何本か送るだけでメモリを食いつぶせる（2026-09-30、
        2回目の第三者の検査：4本で 57MB → 453MB）。
        """
        try:
            n = int(self.headers.get("Content-Length") or 0)
            # 進捗ブロブは1人分で最大95KB。写真は縮めて JPEG にしてから来る（6枚で 5MB ほど）。
            # PDF は1つ 6MB まで受けるので base64 で 8MB を超える。上限は 12MB。
            if n <= 0 or n > (limit or MAX_UPLOAD):
                return None
            d = json.loads(self.rfile.read(n).decode("utf-8"))
            return d if isinstance(d, dict) else None
        except (ValueError, UnicodeDecodeError, RecursionError, OSError):
            # 深すぎる入れ子（RecursionError）・途中で止まった送信（OSError）も、形のおかしい本文として扱う
            return None

    def peer_ip(self):
        """相手のIPアドレス。

        トンネル（Cloudflare Tunnel 等）の後ろに置くと、通信は
        すべて 127.0.0.1 から来ているように見える。そのまま試行制限に
        使うと、**全利用者が1つの枠を共有する**ことになり、
        誰かが30回まちがえた時点で全員が締め出される。

        中継が付けたヘッダを信じてよいのは、直接の相手が
        自分自身（loopback）のときだけ。外から来た接続が名乗る
        ヘッダを信じると、いくらでも身元を偽れる。"""
        direct = self.client_address[0]
        if direct in ("127.0.0.1", "::1"):
            fwd = (self.headers.get("CF-Connecting-IP")
                   or self.headers.get("X-Forwarded-For") or "")
            first = fwd.split(",")[0].strip()
            if first and len(first) <= 45:
                return first
        return direct

    def auth(self):
        """Bearer トークンから今のアカウントを引く。無ければ None。

        返すアカウントには必ず school が入っている。以後の処理は
        **この school だけ**を使ってファイルを読む。リクエストが名乗った
        校舎は一切見ない ―― 見た瞬間に、他校舎の生徒を読める穴になる。
        """
        head = self.headers.get("Authorization") or ""
        tok = ""
        if head.startswith("Bearer "):
            tok = head[7:].strip()
        else:
            # **印刷用の紙だけ、URL で合言葉を受ける。**
            # 新しい窓で開くので、ヘッダを付けられない。
            # 受けるのはこの1つの道だけにして、返事は no-store にしてある。
            # （合言葉が履歴に残るのを避けたいが、印刷の窓を作る道が
            #   ほかに無い。範囲を紙に限ることで被害を閉じ込める。）
            # 見出しに合言葉を入れられない経路だけ、問い合わせから読む。
            #   /prep/sheet     …… 別の窓で開く印刷用の紙
            #   /submissions/…  …… <img> で開く答案の画像
            # どちらも <img> や window.open で開くもので、こちらから
            # 見出しを付けられない。**ログには残さない**（log_message）。
            p0 = (self.path or "").split("?")[0]
            if "/prep/sheet" in p0 or p0.startswith("/api/submissions/"):
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                tok = (q.get("t") or [""])[0].strip()
        if not tok:
            return None
        key = token_key(tok)
        with LOCK:
            store = tokens()
            rec = store.get(key)
            if not rec:
                return None
            ttl = TOKEN_TTL.get(rec.get("role", "student"), TOKEN_TTL["student"])
            if rec.get("claim"):
                ttl = CLAIM_TOKEN_TTL
            now = time.time()
            idle = rec.get("role") == "admin" and now - rec.get("seen", rec["issued"]) > ADMIN_IDLE
            if now - rec["issued"] > ttl or idle:
                store.pop(key, None)
                save_tokens(store)
                return None
            # 画面が裏で回す取り直し（管理ページの30秒ごと。見出し X-Tube-Quiet: 1）は、
            # **さわったことにしない。** 数えると、開いたままの画面は30分たっても切れない
            # （2026-09-30、第三者の検査で見つかった。切れるのは8時間の上限だけになっていた）。
            quiet = self.headers.get("X-Tube-Quiet") == "1"
            if rec.get("role") == "admin" and not quiet and now - rec.get("seen", 0) > 60:
                rec["seen"] = int(now)             # 1分に1回だけ書く
                save_tokens(store)
        school = rec.get("school")
        if not school:
            return None
        try:
            acc = accounts(school).get(rec["loginId"])
        except BadPath:
            return None
        if not acc:
            return None
        if acc.get("role") != rec.get("role"):
            return None          # 役割が変わったら、その合言葉は通さない
        if acc.get("leftAt"):
            return None          # 在籍が終わったら、開いていた画面もそこで止まる
        # 索引と食い違っていたら通さない。校舎の付け替えの途中や、
        # 索引が壊れているときに、間違った校舎のデータを見せないため。
        if paths.school_of_login(rec["loginId"]) != school:
            return None
        # 引き換えの言葉で入った印は、その口座がまだ「引き換え待ち」のあいだだけ生きる。
        # ふつうの印は、口座が引き換え待ちに変わったら（管理者が渡し直したら）止まる。
        if bool(rec.get("claim")) != bool(acc.get("claim")):
            return None
        # 「使った日」を口座に書く（1日に1回だけ）。3か月使われない口座は、記録ごと破棄する（retire.py）。
        if acc.get("role") == "student" and int(acc.get("used") or 0) // 86400 != int(time.time()) // 86400:
            acc = touch_used(school, rec["loginId"]) or acc
        acc = dict(acc)
        acc["school"] = school
        acc["loginId"] = rec["loginId"]
        acc["_claim"] = bool(rec.get("claim"))
        return acc

    def plain_http(self):
        """中継（Cloudflare → Caddy）の向こうで、相手が http で開いているか。

        手元で直接 http://127.0.0.1 を開くとき（中継の見出しが無い）は False。
        Caddy は X-Forwarded-Proto を自分の受けた形（https）で上書きするので、
        相手が実際に使った形は Cloudflare の CF-Visitor で見る。
        """
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            return False
        vis = self.headers.get("CF-Visitor") or ""
        if '"scheme":"http"' in vis.replace(" ", ""):
            return True
        return (self.headers.get("X-Forwarded-Proto") or "").lower() == "http"

    def to_https(self):
        """http で来た人を https へ送る。合言葉を暗号なしで流させない。"""
        # 送り先は Host だけから作る（X-Forwarded-Host は、付けた人の言うなりになる）。
        host = (self.headers.get("Host") or "").strip().lower()
        if not re.match(r"^[a-z0-9.-]{1,100}(:\d{1,5})?$", host):
            return self.reply(400, {"error": "https で開いてください"})
        self.send_response(301)
        self.send_header("Location", "https://" + host + (self.path if self.path.startswith("/") else "/"))
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---- 経路 ----
    def do_GET(self):
        if self.path.split("?")[0].startswith("/api/"):
            return self.api("GET")
        if self.plain_http():
            return self.to_https()
        clean = self.path.split("?")[0]
        if clean in ("/", "/index.html"):
            return self.serve_index()
        # 管理ページ（席・講師・担当・報告）。入口とは別のページ。
        if clean in ("/admin", "/admin/", "/admin.html"):
            return self.serve_index("admin.html")
        # デモの入口。入口と同じページで、「ためしに見る」が出る（--demo で起動しているときだけ）。
        if clean == "/demo":
            return self.serve_index()
        return self.serve_static()

    def serve_static(self):
        """画面のファイル（js・css・svg）。**縮めて、覚えて、変わっていなければ 304。**

        SimpleHTTPRequestHandler は圧縮しないので、app.css（200KB）や
        ui-student.js（120KB）がそのまま流れていた。gzip で 4〜5分の1になる。
        縮めた結果は（ファイル・更新時刻・大きさ）を鍵に覚える ―― 300人が
        同時に開いても、縮める仕事は1回だけ。
        """
        # ドット始まりの名前（.DS_Store・.git など）は一切出さない。
        # また、ディレクトリ一覧・拡張子の無いファイル・許可リスト外の拡張子は
        # すべて 404 にする ―― SimpleHTTPRequestHandler に落とすと一覧や
        # .DS_Store が漏れる（2026-09-13 の自己攻撃で確認）。
        clean = urllib.parse.urlparse(self.path).path
        if any(seg.startswith(".") for seg in clean.split("/") if seg):
            return self.reply(404, {"error": "not-found"})
        path = self.translate_path(self.path)
        ext = os.path.splitext(path)[1].lower()
        if ext in MEDIA_TYPES and os.path.isfile(path):
            return self.serve_media(path, MEDIA_TYPES[ext])
        ctype = STATIC_TYPES.get(ext)
        if not ctype or not os.path.isfile(path):
            return self.reply(404, {"error": "not-found"})
        try:
            st = os.stat(path)
        except OSError:
            return self.reply(404, {"error": "not-found"})
        etag = '"%x-%x"' % (int(st.st_mtime), st.st_size)
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return
        key = (path, etag)
        got = _STATIC_CACHE.get(key)
        if got is None:
            try:
                with open(path, "rb") as f:
                    body = f.read()
            except OSError:
                return self.reply(404, {"error": "not-found"})
            gz = None
            if len(body) >= 1024:
                try:
                    gz = gzip.compress(body, 6)
                except (OSError, ValueError):
                    gz = None
            if len(_STATIC_CACHE) > 300:
                _STATIC_CACHE.clear()
            got = _STATIC_CACHE[key] = (body, gz)
        body, gz = got
        enc = None
        if gz and "gzip" in (self.headers.get("Accept-Encoding") or "").lower():
            body, enc = gz, "gzip"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        if enc:
            self.send_header("Content-Encoding", enc)
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", etag)
        self.send_header("Last-Modified", self.date_time_string(st.st_mtime))
        self.end_headers()
        self.wfile.write(body)

    def serve_media(self, path, ctype):
        """動画。範囲つきの求め（Range: bytes=a-b）に 206 で答える。1回に送るのは 2MB まで。"""
        try:
            size = os.path.getsize(path)
        except OSError:
            return self.reply(404, {"error": "not-found"})
        start, end, status = 0, size - 1, 200
        m = re.match(r"^bytes=(\d*)-(\d*)$", (self.headers.get("Range") or "").strip())
        if m and (m.group(1) or m.group(2)):
            try:
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                else:
                    start = max(0, size - int(m.group(2)))
            except ValueError:
                start, end = 0, size - 1
            if start >= size or start > end:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % size)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            end = min(end, size - 1, start + 2 * 1024 * 1024 - 1)
            status = 206
        try:
            with open(path, "rb") as f:
                f.seek(start)
                body = f.read(end - start + 1)
        except OSError:
            return self.reply(404, {"error": "not-found"})
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        if status == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def serve_index(self, name="index.html"):
        """入口の頁。js と css の呼び出しに版番号を付けて返す。

        **これが無いと、直したものが講師の画面に出ない。**
        Cache-Control: no-store を返しているのに、Cloudflare の縁と
        ブラウザの両方が古い .js を持ち続けた。実際、直した画面が
        出ず「編集が消えた」と勘違いして半日探した。

        番号はファイルの更新時刻から作る。中身が変われば番号が変わり、
        変わらなければ同じ番号のまま（毎回読み直させない）。
        """
        try:
            path = os.path.join(APP_DIR, name)
            html = io.open(path, encoding="utf-8").read()
        except (IOError, OSError):
            return self.reply(404, {"error": "not-found"})

        def stamp(m):
            rel = m.group(2)
            f = os.path.join(APP_DIR, rel.lstrip("/"))
            try:
                v = int(os.path.getmtime(f))
            except (IOError, OSError):
                return m.group(0)
            return "%s%s?v=%d%s" % (m.group(1), rel, v, m.group(3))

        html = re.sub(r'(src=")([^"?]+\.js)(")', stamp, html)
        html = re.sub(r'(href=")([^"?]+\.css)(")', stamp, html)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        if self.path.split("?")[0].startswith("/api/"):
            return self.reply(405, {"error": "method"})
        return SimpleHTTPRequestHandler.do_HEAD(self)

    def do_POST(self):
        return self.api("POST")

    def do_PUT(self):
        return self.api("PUT")

    def do_DELETE(self):
        return self.api("DELETE")

    def api(self, method):
        path = self.path.split("?")[0]
        if not path.startswith("/api/"):
            return self.reply(404, {"error": "not-found"})
        # 経路の各節はURLエンコードされて届く。必ずほどく。
        # ほどかないと "j1:math" が "j1%3Amath" のまま来て、
        # 鍵の照合に落ちる（授業計画の一覧が空になった）。
        parts = [urllib.parse.unquote(p) for p in path[5:].split("/") if p]

        # http で来た口は、生存確認のほかは受けない（合言葉も記録も、暗号なしでは流さない）。
        if self.plain_http() and parts != ["health"]:
            return self.reply(400, {"error": "https で開いてください"})

        # --- 生存確認。クライアントはこれでサーバの有無を見分ける ---
        # 校舎の数だけ答え、どの校舎に誰がいるかは答えない。
        if method == "GET" and parts == ["health"]:
            # demo     … ふつうの入口に「ためしに見る」を出してよいか。**本物の校舎があるときは出さない**
            #             （小4が押して、架空の講師の画面に入ってしまう）。
            # demoPage … デモの入口（/demo）では出してよいか。
            # 試し運用中（school.json の trial）の校舎は、まだ本物に数えない ―― 10/15 までは
            # 配った口座もデモなので、ふつうの入口に「ためしに見る」を出す。
            real = DEMO["on"] and any(not is_demo_school(s2) and not school_meta(s2).get("trial")
                                      for s2 in paths.list_schools())
            return self.reply(200, {"ok": True,
                                    "schools": len(paths.list_schools()),
                                    "demo": DEMO["on"] and not real,
                                    "demoPage": DEMO["on"]})

        # --- デモ用の入室ボタン ---
        # 合言葉を画面に出すのだから、出してよいと明示されたときだけ答える。
        # 本番の起動には --demo を付けない。付け忘れても危険側に倒れない。
        if method == "GET" and parts == ["demo"]:
            if not DEMO["on"]:
                return self.reply(404, {"error": "not-found"})
            return self.reply(200, {"accounts": demo_list(), "joinCode": trial_join_code()})

        # 「ためしに見る」のボタンで入る：一覧にある口座に、**ID だけで**入った印を出す（合言葉は送らないし置いてもいない）。
        # 一覧には本物の講師（wt01〜）も並ぶので、--demo で動いているあいだは誰でもその講師として入れる。
        # 試し運用（TRIAL）の期間だけのもの。管理者には入れない。引き換え前の席・在籍の終わった口座にも入れない。
        if method == "POST" and parts == ["demo", "enter"]:
            if not DEMO["on"]:
                return self.reply(404, {"error": "not-found"})
            data = self.body_json(LOGIN_BODY_MAX) or {}
            login_id = SCRAM.norm_id(data.get("id"))[:64]
            ip = self.peer_ip()
            if not any(a["id"] == login_id for a in demo_accounts()):
                return self.reply(404, {"error": "この口座は、ためしの入口に出ていません。"})
            # 入る口と同じ上限で数える（ボタンを機械で連打して、入った印を山ほど作らせない）。
            wait, stamp, _which = login_reserve(login_id, ip)
            if wait:
                return self.reply(429, {"error": "試行が多すぎます。%d分ほど待ってから試してください。"
                                        % max(1, wait // 60)})
            school = paths.school_of_login(login_id)
            tok = secrets.token_urlsafe(32)
            now = int(time.time())
            born = False
            with LOCK:
                db = accounts(school) if school else {}
                cur = db.get(login_id)
                if (not cur or cur.get("leftAt") or cur.get("claim")
                        or cur.get("role") not in ("student", "teacher")):
                    cur = None
                else:
                    born = activate_seat(db, login_id, by="demo")
                    cur["lastLogin"] = now
                    save_accounts(school, db)
                    if cur.get("role") == "student":
                        join_open_homework(school, [login_id], now)    # 入るたびに（上の入る口と同じ）
                    store = tokens()
                    for k in [k for k, r in store.items()
                              if now - r["issued"] > (CLAIM_TOKEN_TTL if r.get("claim")
                                                      else TOKEN_TTL.get(r.get("role", "student"), 0))]:
                        store.pop(k)
                    store[token_key(tok)] = {"loginId": login_id, "sid": cur["sid"], "role": cur["role"],
                                             "school": school, "issued": now, "seen": now}
                    save_tokens(store)
            if cur is None:
                login_unreserve(login_id, ip, stamp)
                return self.reply(404, {"error": "この口座には、いま入れません。"})
            login_ok(login_id, ip, stamp)
            audit(school, login_id, "demo_login", "", ip)
            acc = dict(cur); acc["school"] = school
            return self.reply(200, {"token": tok, "profile": profile_of(acc)})

        # --- ログイン（合言葉そのものは受け取らない。server/scram.py） ---
        #
        #   POST /api/login/start   {id, cnonce}        → {salt, iters, nonce}
        #   POST /api/login/finish  {id, nonce, proof}  → {token, profile, serverSig}
        #
        # 前の口（POST /api/login {id, password}）は閉じた。古い画面が合言葉を送ってきても、
        # 読まずに「読み込み直してください」と返す。
        if method == "POST" and parts == ["login"]:
            return self.reply(400, {"error": "画面が古くなっています。ページを読み込み直してから、もう一度入ってください。"})

        # --- 初回登録（招待コードから、保護者が口座を作る。join.py）---
        if method == "POST" and parts and parts[0] == "join" and len(parts) <= 2:
            d = self.body_json(8192) or {}
            ip = self.peer_ip()
            try:
                if parts == ["join", "check"]:
                    return self.reply(200, JOIN.check(sys.modules[__name__], d.get("code"), ip_bucket(ip)))
                if parts == ["join"]:
                    return self.reply(200, JOIN.create(sys.modules[__name__], d, ip_bucket(ip)))
                if parts == ["join", "finish"]:
                    return self.reply(200, JOIN.finish(sys.modules[__name__], d, ip_bucket(ip)))
            except JOIN.JoinError as e:
                return self.reply(e.status, {"error": str(e)})
            except (ValueError, BadPath) as e:
                return self.reply(400, {"error": str(e)})
            return self.reply(404, {"error": "not-found"})

        if method == "POST" and parts == ["login", "start"]:
            data = self.body_json(LOGIN_BODY_MAX) or {}
            login_id = SCRAM.norm_id(data.get("id"))[:64]
            cnonce = str(data.get("cnonce") or "")
            if not re.match(r"^[A-Za-z0-9_-]{16,64}$", cnonce):
                return self.reply(400, {"error": "bad-nonce"})
            ip = self.peer_ip()
            slot_id = login_id if SAFE_ID.match(login_id) else "?"
            wait, which = login_blocked(slot_id, ip)
            if wait:
                if slot_id != "?":
                    login_alert(login_id, which)   # 管理ページの「報告」に（同じIDは1時間に1回）
                return self.reply(429, {
                    "error": "試行が多すぎます。%d分ほど待ってから試してください。"
                             % max(1, wait // 60)})
            # どの校舎のIDかは索引で引く。生徒に校舎を選ばせない
            # ―― 小学生に「あなたはロンドン校です」を選ばせる画面は作らない。
            school, acc = login_account(login_id)
            real = bool(acc and not acc.get("leftAt") and acc.get("alg") == SCRAM.ALG and acc.get("storedKey"))
            # 無いID・在籍終了・古い形の口座にも、同じ形の返事をする（あるかどうかを教えない）。
            salt = acc["salt"] if real else fake_salt(login_id)
            iters = int(acc.get("iters") or SCRAM.ITERS) if real else SCRAM.ITERS
            # 何も覚えない（nonce に印を付けて返すだけ）。start を送り続けても、ほかの人の入口は埋まらない。
            return self.reply(200, {"salt": salt, "iters": iters, "nonce": nonce_make(login_id, cnonce, salt, iters)})

        if method == "POST" and parts == ["login", "finish"]:
            data = self.body_json(LOGIN_BODY_MAX) or {}
            login_id = SCRAM.norm_id(data.get("id"))[:64]
            proof = str(data.get("proof") or "")[:64]
            nonce = str(data.get("nonce") or "")[:200]
            ip = self.peer_ip()
            # 確かめると数えるを1つに（login_reserve）。形のおかしいIDは1つの枠にまとめる
            # （名乗られた文字列の数だけ枠を作らせない）。
            slot_id = login_id if SAFE_ID.match(login_id) else "?"
            wait, stamp, which = login_reserve(slot_id, ip)
            if wait:
                if slot_id != "?":
                    login_alert(login_id, which)   # 管理ページの「報告」に（同じIDは1時間に1回）
                return self.reply(429, {
                    "error": "試行が多すぎます。%d分ほど待ってから試してください。"
                             % max(1, wait // 60)})
            school, acc = login_account(login_id)
            real = bool(acc and not acc.get("leftAt") and acc.get("alg") == SCRAM.ALG and acc.get("storedKey"))
            salt = acc["salt"] if real else fake_salt(login_id)
            iters = int(acc.get("iters") or SCRAM.ITERS) if real else SCRAM.ITERS
            # nonce は、このIDに・この salt で・2分以内に、このサーバが出したものか。
            # 始めたあとで合言葉が作り直されていたら（salt が変わる）、ここで通らない。
            if not nonce_check(nonce, login_id, salt, iters):
                login_unreserve(slot_id, ip, stamp)   # 合言葉を試したわけではない。この1回は数えない
                return self.reply(401, {"error": "時間がたちました。もう一度入ってください。"})
            pend = {"salt": salt, "iters": iters, "real": real}
            if not real:
                acc = None
            # 在籍が終わったアカウントは通さない。
            # **合言葉を消すだけでは止まらない。** 本人はカードを持っていて、
            # 同じ合言葉でもう一度入れてしまう（実際に入れた）。
            # ここで弾かないと、退塾後も記録が増え続ける。
            if acc and (acc.get("leftAt") or acc.get("alg") != SCRAM.ALG or acc.get("salt") != pend["salt"]):
                acc = None
            # 引き換えの言葉は、期限を過ぎたら使えない（渡し直してもらう）。
            if acc and acc.get("claim") and time.time() > int((acc.get("claim") or {}).get("exp") or 0):
                acc = None
            # 管理者は、管理ページからだけ入る（ふつうの入口は管理者を知らない）。
            if acc and acc.get("role") == "admin" and data.get("admin") is not True:
                acc = None
            auth_msg = SCRAM.auth_message(login_id, nonce, pend["salt"], pend["iters"])
            # 無いIDでも、同じ計算をして同じ返事をする。
            stored = acc["storedKey"] if acc else hashlib.sha256(b"none|" + login_id.encode("utf-8")).hexdigest()
            ok = SCRAM.verify_proof(stored, auth_msg, proof) and bool(acc)
            # 通った証明は、1回きり（同じ nonce の証明を、もう一度送っても入れない）。
            if ok and not nonce_use(nonce):
                ok = False
            if not ok:
                time.sleep(0.3)
                return self.reply(401, {"error": "IDかパスワードが違います"})
            snap = (acc["salt"], acc["storedKey"])

            tok = secrets.token_urlsafe(32)
            now = int(time.time())
            with LOCK:
                # **証明を確かめたあとに変わっていないかを、書く鍵の中で確かめ直す。**
                # あいだに管理者が合言葉を作り直したり在籍を終えたりすると、
                # 古い合言葉で入った画面が残ってしまう。
                db = accounts(school)
                cur = db.get(login_id)
                if (not cur or cur.get("leftAt")
                        or (cur.get("salt"), cur.get("storedKey")) != snap
                        or cur.get("role") not in ROLES):
                    cur = None
                else:
                    claiming = bool(cur.get("claim"))
                    born = False
                    if not claiming:
                        # まだ渡していない席に、カードを持った本人が入った。ここで在籍の生徒になる。
                        born = activate_seat(db, login_id, by="login")
                        cur["lastLogin"] = now
                        save_accounts(school, db)
                        if cur.get("role") == "student":
                            # いま出ている宿題（期限前）に、この子を足す。入ったその日から宿題が見える。
                            # **使い始めた日だけでなく、入るたびに。** 使い始めたあとで講師が「使う」にしたコースや、
                            # ためし運用のデモで出した宿題にも、次に入ったときに足される（もう入っていれば何もしない）。
                            join_open_homework(school, [login_id], now)
                    store = tokens()
                    # ついでに期限切れを掃除する。放っておくと際限なく溜まる。
                    for k in [k for k, r in store.items()
                              if now - r["issued"] > (CLAIM_TOKEN_TTL if r.get("claim")
                                                      else TOKEN_TTL.get(r.get("role", "student"), 0))]:
                        store.pop(k)
                    store[token_key(tok)] = {"loginId": login_id, "sid": cur["sid"],
                                             "role": cur["role"], "school": school,
                                             "issued": now, "seen": now}
                    if claiming:
                        # 引き換えの言葉で入った。この印は、引き換える口にしか使えない（下の門）。
                        store[token_key(tok)]["claim"] = True
                    save_tokens(store)
            if cur is None:
                time.sleep(0.3)
                return self.reply(401, {"error": "IDかパスワードが違います"})
            login_ok(slot_id, ip, stamp)
            sig = SCRAM.server_signature(cur["serverKey"], auth_msg)
            if claiming:
                audit(school, login_id, "claim_open", login_id, ip)
                # 役割もクラスも返さない。端末は、ここから本物の合言葉を作って /api/claim へ届ける。
                return self.reply(200, {"token": tok, "claim": True, "serverSig": sig,
                                        "words": PW_WORDS_BY_ROLE.get(cur.get("role"), 3)})
            if born:
                audit(school, login_id, "seat_used", login_id, "はじめて入った")
            audit(school, login_id, "login", "", ip)
            acc = dict(cur); acc["school"] = school
            # サーバの印。端末はこれを確かめる（保存の値を持たない偽のサーバは、これを作れない）。
            return self.reply(200, {"token": tok, "profile": profile_of(acc), "serverSig": sig})

        # --- ここから先はログインが要る ---
        acc = self.auth()
        if not acc:
            return self.reply(401, {"error": "unauthorized"})
        # 以後のファイル操作は、すべてこの school に閉じる。
        # リクエストが名乗ってくる校舎は決して使わないこと。
        school = acc["school"]

        # **引き換えの言葉で入った印は、引き換える口だけ。** 記録も宿題も読めない。
        if acc.get("_claim"):
            if method == "POST" and parts == ["claim"]:
                d = self.body_json() or {}
                try:
                    ADMIN.claim(sys.modules[__name__], school, acc, d.get("verifier"))
                except ValueError as e:
                    return self.reply(400, {"error": str(e)})
                return self.reply(200, {"ok": True})
            if not (method == "POST" and parts == ["logout"]):
                return self.reply(403, {"error": "forbidden"})

        # **管理者は、管理の口だけ。** 講師や生徒の口には入れない（答案も記録も読めない）。
        # 下のほうには「生徒でなければ講師」と読む所があるので、ここで先に分ける。
        if acc["role"] == "admin" and not (
                (parts and parts[0] == "admin") or parts in (["logout"], ["me"], ["report"])):
            return self.reply(403, {"error": "forbidden"})
        if parts and parts[0] == "admin":
            if acc["role"] != "admin":
                return self.reply(403, {"error": "forbidden"})
            return ADMIN.handle(sys.modules[__name__], self, method, parts[1:], acc)

        # --- うまく動かないときの報告（だれでも。名前は入れない）---
        if method == "POST" and parts == ["report"]:
            d = self.body_json() or {}
            try:
                it = ADMIN.add_report(sys.modules[__name__], school, acc, d,
                                      self.headers.get("User-Agent") or "")
            except ValueError as e:
                return self.reply(400, {"error": str(e)})
            return self.reply(200, {"ok": True, "id": it and it.get("id")})

        if method == "POST" and parts == ["logout"]:
            tok = (self.headers.get("Authorization") or "")[7:].strip()
            with LOCK:
                store = tokens()
                store.pop(token_key(tok), None)
                save_tokens(store)
            return self.reply(200, {"ok": True})

        if method == "GET" and parts == ["me"]:
            return self.reply(200, {"profile": profile_of(acc)})

        # --- 設定：学年・クラス・受講科目を、本人（保護者）が変える。自己申告なので、まちがえたらすぐ直せる ---
        # 情報は端末でなく ID に集まる（どの端末で入っても同じ）。1日に 6回まで。
        # 添削のデータを消す（本人の設定から。返した添削の写真だけ。評価・ひとことは残る）
        if method == "DELETE" and parts == ["me", "returned"]:
            if acc["role"] != "student" or acc.get("_claim"):
                return self.reply(403, {"error": "forbidden"})
            n = SUB.erase_returned(school, acc["sid"])
            audit(school, acc["loginId"], "erase_returned", "", "%d件" % n)
            return self.reply(200, {"ok": True, "n": n})
        if method == "GET" and parts == ["me", "placement"]:
            if acc["role"] != "student" or acc.get("_claim"):
                return self.reply(403, {"error": "forbidden"})
            return self.reply(200, {"grades": list(JOIN.GRADES), "classes": JOIN._class_rows(sys.modules[__name__], school),
                                    "combos": {k: [list(x) for x in v] for k, v in JOIN.COMBOS.items()},
                                    "now": {"grade": acc.get("level") or "", "classId": acc.get("classId") or "",
                                            "subjects": acc.get("subjects") or []}})
        if method == "PUT" and parts == ["me", "placement"]:
            if acc["role"] != "student" or acc.get("_claim"):
                return self.reply(403, {"error": "forbidden"})
            d = self.body_json(4096) or {}
            try:
                what = JOIN.set_placement(sys.modules[__name__], school, acc["loginId"],
                                          grade=d.get("grade"), class_id=d.get("classId"), subjects=d.get("subjects"), by="self",
                                          exam=str(d.get("exam") or "")[:10] or None)
            except JOIN.JoinError as e:
                return self.reply(e.status, {"error": str(e)})
            # 点数（任意。組分け・必修テストのあとに本人が入れる。入れた人ほど苦手を正確に出せる）
            sc = d.get("scores")
            if isinstance(sc, dict) and sc:
                clean = {}
                for k, v in list(sc.items())[:6]:
                    try:
                        iv = int(v)
                    except (TypeError, ValueError):
                        continue
                    if re.match(r"^[a-z]{2,16}$", str(k)) and 0 <= iv <= 200:
                        clean[str(k)] = iv
                if clean:
                    with LOCK:
                        db = accounts(school)
                        a = db.get(acc["loginId"])
                        if a is not None:
                            rows = [r for r in (a.get("selfScores") or []) if isinstance(r, dict)]
                            rows.append({"exam": str(d.get("exam") or "")[:10], "at": int(time.time()), "scores": clean})
                            a["selfScores"] = rows[-12:]
                            save_accounts(school, db)
            fresh = dict(accounts(school)[acc["loginId"]])
            fresh["school"], fresh["loginId"] = school, acc["loginId"]
            return self.reply(200, {"profile": profile_of(fresh), "changed": what})

        # --- 今週の勉強量を、同じ学年の中で比べる ---
        #
        # 比べるのは点数ではなく **やった量**。
        # 生まれつきの差ではなく、自分で動かせるものを見せる。
        #
        # **1週間で切る。** 通算で比べると、去年から通っている子に
        # 4月入会の子は一生追いつけない。追いつけない競争は競争ではなく、
        # ただの身分の掲示になる。毎週0に戻れば、今週がんばれば今週勝てる。
        #
        # 返すのは「自分・学年のまんなか・学年の1番」の3つの数。
        # 順位そのものは出さない ―― 「20人中18位」は続ける気を折る。
        # 目標に要るのは「あと何問で真ん中か」であって、18という数ではない。
        # --- 成績の伸び（自分の分だけ。講師の理解度と同じ数） ---
        # --- 保護者から講師へのメッセージ（生徒のアプリの「保護者の方へ」から。宛先は教科の担当講師） ---
        # --- 宿題の変更のお知らせ（生徒）：講師のひとこと付きの決まり。「わかった」か「質問する」で返す ---
        if parts and parts[0] == "notices":
            if acc["role"] != "student":
                return self.reply(403, {"error": "forbidden"})
            plans_n = courses.all_courses(school)

            def notice_row(key, r):
                p = plans_n.get(key) or {}
                what, span = PERSONAL.describe(r, unit_names(p))
                ack = r.get("ack") or {}
                return {"id": r["id"], "key": key, "subject": p.get("subject") or "", "course": p.get("name") or key,
                        "msg": r.get("msg") or "", "text": what, "span": span, "at": r.get("at"),
                        "state": ack.get("state"), "question": ack.get("question"), "askedAt": ack.get("askedAt"),
                        "answer": ack.get("answer"), "answeredAt": ack.get("answeredAt"),
                        "until": int(r.get("at") or 0) + PERSONAL.ACK_DAYS * 86400}

            def notice_list():
                return [notice_row(k, r) for k, r in PERSONAL.notices_of(school, acc["sid"])]

            if method == "GET" and len(parts) == 1:
                return self.reply(200, {"notices": notice_list()})
            if method == "POST" and len(parts) == 3 and parts[2] == "ack":
                d = self.body_json() or {}
                key = str(d.get("key") or "")[:48]
                rid = parts[1][:16]
                action = str(d.get("action") or "")
                if action not in ("ok", "ask"):
                    return self.reply(400, {"error": "bad-action"})
                msg_id = None
                if action == "ask":
                    text = str(d.get("text") or "").strip()
                    if not text:
                        return self.reply(400, {"error": "質問を書いてください"})
                    p = plans_n.get(key) or {}
                    try:
                        it = MESSAGES.post(school, acc["sid"], p.get("subject") or "", key,
                                           "【宿題の変更について質問】" + text, sender="student")
                    except ValueError as e:
                        return self.reply(400, {"error": str(e)})
                    msg_id = it["id"]
                r = PERSONAL.ack_rule(school, key, acc["sid"], rid, action, d.get("text"), msg_id=msg_id)
                if not r:
                    return self.reply(404, {"error": "そのお知らせはありません"})
                audit(school, acc["sid"], "notice_" + action, rid, key)
                return self.reply(200, {"notice": notice_row(key, r), "notices": notice_list()})

        if parts and parts[0] == "messages":
            if acc["role"] == "student":
                if method == "GET" and len(parts) == 1:
                    return self.reply(200, {"items": MESSAGES.of_student(school, acc["sid"])})
                if method == "POST" and len(parts) == 1:
                    d = self.body_json() or {}
                    sub = str(d.get("subject") or "")[:24]
                    try:
                        key = courses.key_for(school, acc.get("classId") or "", sub, acc.get("level") or "")
                        plan = courses.all_courses(school).get(key)
                    except (IOError, OSError, BadPath):
                        plan = None
                    if not plan or not courses.app_on(plan):
                        return self.reply(400, {"error": "その教科は、いまはアプリを使っていません"})
                    try:
                        it = MESSAGES.post(school, acc["sid"], sub, key, d.get("text"))
                    except ValueError as e:
                        return self.reply(400, {"error": str(e)})
                    audit(school, acc["sid"], "message", key, it["id"])
                    return self.reply(200, {"item": it})
                if method == "PUT" and len(parts) == 3 and parts[2] == "seen":
                    try:
                        it = MESSAGES.mark_seen(school, parts[1][:16], "parent", sid=acc["sid"])
                    except PermissionError as e:
                        return self.reply(403, {"error": str(e)})
                    return self.reply(200 if it else 404, {"item": it} if it else {"error": "not-found"})
                return self.reply(404, {"error": "not-found"})
            if acc["role"] == "teacher":
                keys = None if teacher_classes(acc) is None else set(desk_courses(school, acc))
                if method == "GET" and len(parts) == 1:
                    labels = desk_labels(school)
                    items = [dict(x, label=labels.get(x.get("sid"), "")) for x in MESSAGES.inbox(school, keys)]
                    plans_a = courses.all_courses(school)
                    acks = []
                    for key, sid, r in PERSONAL.acks_recent(school, keys):
                        p = plans_a.get(key) or {}
                        what, span = PERSONAL.describe(r, unit_names(p))
                        ack = r.get("ack") or {}
                        acks.append({"id": r["id"], "key": key, "sid": sid, "label": labels.get(sid, sid),
                                     "course": p.get("name") or key, "text": what, "msg": r.get("msg") or "",
                                     "state": ack.get("state"), "okAt": ack.get("okAt"), "auto": bool(ack.get("auto")),
                                     "askedAt": ack.get("askedAt"), "question": ack.get("question"), "msgId": ack.get("msgId")})
                    return self.reply(200, {"items": items, "acks": acks,
                                            "unread": len([x for x in items if not (x.get("seen") or {}).get("teacher")])})
                if method == "POST" and len(parts) == 3 and parts[2] == "reply":
                    d = self.body_json() or {}
                    try:
                        it = MESSAGES.reply(school, parts[1][:16], acc["sid"], d.get("text"), keys)
                        if it:
                            PERSONAL.answer_by_msg(school, it["id"], d.get("text"), acc["sid"])
                    except ValueError as e:
                        return self.reply(400, {"error": str(e)})
                    except PermissionError as e:
                        return self.reply(403, {"error": str(e)})
                    if not it:
                        return self.reply(404, {"error": "not-found"})
                    audit(school, acc["sid"], "message_reply", it.get("key", ""), it["id"])
                    return self.reply(200, {"item": it})
                if method == "PUT" and len(parts) == 3 and parts[2] == "seen":
                    try:
                        it = MESSAGES.mark_seen(school, parts[1][:16], "teacher", keys=keys)
                    except PermissionError as e:
                        return self.reply(403, {"error": str(e)})
                    return self.reply(200 if it else 404, {"item": it} if it else {"error": "not-found"})
            return self.reply(404, {"error": "not-found"})

        if method == "GET" and parts == ["growth"]:
            if acc["role"] != "student":
                return self.reply(403, {"error": "forbidden"})
            return self.reply(200, student_growth(school, acc["sid"]))

        if method == "GET" and parts == ["rank"]:
            if acc["role"] != "student":
                return self.reply(403, {"error": "forbidden"})
            grade = acc.get("level") or ""
            sums = summary(school)
            peers = []
            for a2 in accounts(school).values():
                if a2.get("role") != "student" or a2.get("leftAt"):
                    continue
                if (a2.get("level") or "") != grade:
                    continue
                peers.append(int((sums.get(a2["sid"]) or {}).get("week") or 0))
            me = int((sums.get(acc["sid"]) or {}).get("week") or 0)
            peers.sort(reverse=True)
            n = len(peers)
            place = 1 + len([x for x in peers if x > me])
            # まんなか＝中央値。平均だと、1人の猛烈な生徒が引き上げてしまい、
            # 半数以上が「へいきん以下」と出る。それは目標として働かない。
            mid = peers[n // 2] if n else 0
            return self.reply(200, {
                "n": n, "place": place,
                "week": me,             # 自分が今週やった問題数
                "mid": mid,             # 学年のまんなか
                "best": peers[0] if peers else 0,   # 学年の1番
                # 上から何％の位置か。1位なら100。ピラミッドの段に使う。
                "top": int(round((n - place) * 100.0 / max(1, n - 1))) if n > 1 else 100,
            })

        # --- 進捗 1人分 ---
        if len(parts) == 2 and parts[0] == "p":
            sid = parts[1]
            if not SAFE_SID.match(sid):
                return self.reply(400, {"error": "bad-sid"})
            # 生徒は自分の分だけ。講師は担当クラスの生徒を読めるが書けない。
            # この判定はサーバでしか意味を持たない（画面側の判定は判定ではない）。
            mine = (sid == acc["sid"])
            if method == "GET":
                if not (mine or self.may_read(acc, sid)):
                    return self.reply(403, {"error": "forbidden"})
                if not mine:
                    audit(school, acc["sid"], "read_progress", sid)
                rec = paths.load(progress_path(school, sid), None)
                if not rec:
                    return self.reply(404, {"error": "no-progress"})
                return self.reply(200, rec)
            if method == "PUT":
                if not mine:
                    return self.reply(403, {"error": "自分の記録しか書き込めません"})
                data = self.body_json()
                if not data:
                    return self.reply(400, {"error": "bad-body"})
                with LOCK:
                    cur = paths.load(progress_path(school, sid), None) or {}
                    base = cur.get("blob") or {}
                    if data.get("mode") == "delta":
                        # 届いた分だけを合流する。全文は送られてこない。
                        blob, stats = merge_progress(base, data)
                    else:
                        # 旧い形（全文）。中身を合流の入力として扱えば、
                        # 古い端末が新しい記録を踏み潰すことがなくなる。
                        blob, stats = merge_progress(base, {
                            "cards": (data.get("blob") or {}).get("cards") or {},
                            "hw":    (data.get("blob") or {}).get("hw") or {},
                            "hist":  (data.get("blob") or {}).get("hist") or {},
                            "meta":  data.get("blob") or {}})
                    # 時刻はサーバが決める。端末の時計は信用しない。
                    now = int(time.time() * 1000)
                    rec = {"sid": sid, "rev": (cur.get("rev") or 0) + 1,
                           "savedAt": now, "blob": blob,
                           "updated": int(time.time())}
                    save_json(progress_path(school, sid), rec)
                # 講師画面むけの要約を、この1人ぶんだけ更新する。
                # LOCK の外でやる ―― 要約は作り直せる派生データなので、
                # ここで失敗しても原本は無事。原本の保存を待たせない。
                try:
                    # **控えを1つ作って回す。** これが無いと、宿題1件ごとに
                    # 名簿ぜんぶ（生徒2000名で625KB）を読み直す。
                    # ここは生徒が同期するたびに通る、いちばん頻度の高い経路。
                    c = hw_cache()
                    mine_asg = [a for a in assignments(school).values()
                                if sid in students_for(school, a, c)]
                    update_summary(school, sid, blob, mine_asg)
                except (IOError, BadPath, KeyError):
                    pass
                return self.reply(200, {"ok": True, "rev": rec["rev"],
                                        "savedAt": now, "merged": stats})

        # --- 進捗の見出しだけ（他端末の変更を安く見張る）---
        if method == "GET" and len(parts) == 3 and parts[0] == "p" and parts[2] == "head":
            sid = parts[1]
            if not SAFE_SID.match(sid):
                return self.reply(400, {"error": "bad-sid"})
            if not (sid == acc["sid"] or self.may_read(acc, sid)):
                return self.reply(403, {"error": "forbidden"})
            rec = paths.load(progress_path(school, sid), None) or {}
            return self.reply(200, {"rev": rec.get("rev", 0),
                                    "savedAt": rec.get("savedAt", 0),
                                    "serverTime": int(time.time() * 1000)})

        # --- 授業計画（コマ単位）と、そこから自動で出る宿題 ---
        #
        # 講師の毎週の作業をゼロにするための中心。
        # 学期はじめに数ヶ月分いちど入れたら、授業日が来た回の宿題が
        # 自動で生徒に出る。遅れたら shift で1タップ下げる。
        if parts and parts[0] == "lessons":
            if acc["role"] != "teacher":
                return self.reply(403, {"error": "forbidden"})
            # コースの導入の段階（0 紙のまま … 4 毎日テストまで）。担当コースだけ。
            # 1件（key）でも、まとめて（keys）でも同じ道。ワンタッチで学年・教科ごとに切り替えるため。
            if method == "PUT" and parts == ["lessons", "use"]:
                d = self.body_json() or {}
                keys = [str(k)[:48] for k in (d.get("keys") or ([d.get("key")] if d.get("key") else []))]
                try:
                    level = int(d.get("level"))
                except (TypeError, ValueError):
                    return self.reply(400, {"error": "段階は 0〜4"})
                if level < 0 or level > 4:
                    return self.reply(400, {"error": "段階は 0〜4"})
                mine = (dict(courses.all_courses(school)) if teacher_classes(acc) is None
                        else courses.of_teacher(school, acc["sid"]))
                bad = [k for k in keys if k not in mine]
                if not keys or bad:
                    return self.reply(403, {"error": "担当外のコースです"})
                out = {}
                for k in keys:
                    p = lessons.set_use(school, k, level, acc["sid"])
                    out[k] = courses.use_level(p)
                    audit(school, acc["sid"], "course_use", k, str(level))
                return self.reply(200, {"use": out, "level": level,
                                        "assign": teacher_slots(dict(acc, school=school))})
            # コースでアプリを使う／使わない（担当コースだけ）。
            if method == "PUT" and parts == ["lessons", "app"]:
                d = self.body_json() or {}
                key = str(d.get("key") or "")[:48]
                mine = (dict(courses.all_courses(school)) if teacher_classes(acc) is None
                        else courses.of_teacher(school, acc["sid"]))
                if key not in mine:
                    return self.reply(403, {"error": "担当外のコースです"})
                p = lessons.set_app(school, key, bool(d.get("app")), acc["sid"])
                audit(school, acc["sid"], "course_app", key, "on" if d.get("app") else "off")
                return self.reply(200, {"key": key, "app": courses.app_on(p),
                                        "assign": teacher_slots(dict(acc, school=school))})
            allowed = teacher_classes(acc) or []
            pairs = teacher_pairs(acc)
            grades = teacher_grades(acc)
            # 担当を「学年:教科」の集合にしておく。格子はこの集合だけを出す。
            cur_cls = class_table(school)
            mine_keys = None
            if pairs is not None:
                mine_keys = set()
                for cid, sub in pairs:
                    g = (cur_cls.get(cid) or {}).get("grade")
                    if g:
                        mine_keys.add("%s:%s" % (g, sub))

            if mine_keys is not None:
                # 担当コースの鍵（コースID:教科）も足す。
                mine_keys |= set(courses.of_teacher(school, acc["sid"]).keys())

            def may(key):
                # **教科まで見る。** 学年だけで通すと、中2Rの英語の先生の
                # 格子に中2の数学まで並ぶ。自分が出す予定のないマスが
                # 「出てない」と赤く見えるのは、いちばん困る誤報である。
                return mine_keys is None or key in mine_keys

            def may_write(key, class_id=""):
                """その計画を書き換えてよいか。**読めることと直せることは別。**

                同じ学年・同じ教科を別の講師が持つ（小5α算数と小5β算数）。
                学年で通すと、後から保存した講師が前の講師の計画を
                丸ごと置き換える。コースは teachers にいる講師だけ、
                旧来の計画は保存済みの classId を担当している講師だけが直せる。
                """
                p0 = lessons.plan(school, key)
                if pairs is None:
                    return True
                if not p0:
                    # 新しい計画（旧来の「学年:教科」）は、送られてきたクラスが
                    # その学年で、そのクラスのその教科を受け持つ講師だけが作れる。
                    # クラスを確かめないと、どのクラスあてにでも自動で宿題が出る。
                    g, sub = key.split(":", 1)
                    return (bool(class_id) and (cur_cls.get(class_id) or {}).get("grade") == g
                            and can_see(acc, class_id, sub))
                if courses.is_course(p0):
                    return acc["sid"] in (p0.get("teachers") or [])
                cid0 = p0.get("classId") or ""
                # クラスの無い古い計画は、全部を見る講師（教室長）だけが直せる。
                return bool(cid0) and can_see(acc, cid0, key.split(":", 1)[1])

            # 今週の格子（学年 × 教科）。空のマスを見せるのが目的。
            if method == "GET" and parts == ["lessons", "grid"]:
                cur = curriculum(school)
                gs = [g.get("id") for g in (cur.get("grades") or []) if g.get("id")]
                if not gs:
                    gs = sorted({k.split(":")[0] for k in (cur.get("plans") or {})})
                if grades is not None:
                    gs = [g for g in gs if g in grades]
                subs = subject_ids()
                # その学年で「使う」に設定されている教科だけを対象にする。
                # 履修していない教科に警告を出すと、本当の出し忘れが埋もれる。
                enabled = {k for k, v in (cur.get("plans") or {}).items()
                           if v.get("enabled")}
                # **担当していないマスは、そもそも出さない。**
                # 学年だけで絞ると、中2Rの数学の先生の格子に
                # 中2の国語まで並ぶ。自分が出す予定のないマスが
                # 「出てない」と見えるのがいちばん困る。
                if mine_keys is not None:
                    enabled = {k for k in enabled if k in mine_keys}
                out = lessons.week_grid(school, gs, subs, enabled=enabled)
                # 各マスに「見てあげる」件数を入れる。
                # 期限が過ぎて、まだ全員ぶんを見ていない宿題の数。
                # 画面ではこれが唯一の赤信号になるので、ここで数える。
                asg = list(assignments(school).values())
                nowms = time.time() * 1000
                by_key = {}
                gcache = hw_cache()             # 宿題1件ごとに台帳を読み直さない
                for a in asg:
                    sm = hw_summary(school, a, gcache)
                    n = sm.get("assigned") or 0
                    got = (sm.get("rated") or 0) if (a.get("route") == "paper") \
                        else (sm.get("completed") or 0)
                    if n and got >= n:
                        continue                    # 見終わっている
                    if (a.get("dueAt") or 0) >= nowms:
                        continue                    # まだ期限前
                    g = (class_table(school).get(a.get("classId")) or {}).get("grade")
                    sub = subject_of_assignment(a)
                    if g and sub:
                        k = "%s:%s" % (g, sub)
                        by_key[k] = by_key.get(k, 0) + 1
                # **前回の宿題の提出状況。** この画面でいちばん見たい数字。
                # いま出ている（＝いちばん新しく出した）宿題について、
                # 何人が終えたか。紙は評価が付いた人数を提出とみなす
                # ―― アプリからは提出が見えないので、それが唯一の観測点。
                last = {}
                for a in asg:
                    g = (class_table(school).get(a.get("classId")) or {}).get("grade")
                    sub = subject_of_assignment(a)
                    if not (g and sub):
                        continue
                    # **「前回」は、期限が来たもののうちいちばん新しいもの。**
                    # まだ期限前のものを前回とみなすと、誰も出していない
                    # のが当たり前なので 0% が並ぶ（実際そうなった）。
                    if (a.get("dueAt") or 0) > nowms:
                        continue
                    k = "%s:%s" % (g, sub)
                    cur = last.get(k)
                    if cur and (cur.get("dueAt") or 0) >= (a.get("dueAt") or 0):
                        continue
                    sm = hw_summary(school, a, gcache)
                    n = sm.get("assigned") or 0
                    got = (sm.get("rated") or 0) if (a.get("route") == "paper") \
                        else (sm.get("completed") or 0)
                    last[k] = {
                        "dueAt": a.get("dueAt"), "title": a.get("title", ""),
                        "n": n, "done": min(got, n),
                        "pct": int(round(got * 100.0 / n)) if n else 0,
                        "paper": a.get("route") == "paper",
                        "classId": a.get("classId"),
                    }
                for row in out.get("grid", []):
                    for c in row.get("cells", []):
                        c["late"] = by_key.get(c.get("key"), 0)
                        c["last"] = last.get(c.get("key"))
                # **クラスごとの数字も別に返す。**
                #
                # 上の格子は「学年 × 教科」で数えている。だが講師が持って
                # いるのは学年ではなく **クラス**である。小4αと小4βを
                # 一緒に数えると、小4βだけを持つ講師の画面に、小4αの
                # 提出状況が出る ―― 実際そうなっていて、棒を押して開いた
                # 一覧が空になった（小4βには1件も出していなかった）。
                # 画面の棒はこちらを見る。
                # まだ出していない回を、この場で出してしまう（自動発行）
                out["published"] = [x for x in (self.auto_publish(school, acc) or [])
                                    if not x.get("key") or may(x["key"])]
                asg = list(assignments(school).values())
                if pairs is not None:
                    # ほかの講師の宿題の題名と提出率は送らない。
                    asg = [a for a in asg
                           if may_touch(school, acc, a, subject_of_assignment(a) or None)]
                out["pairs"] = self.grid_pairs(school, asg, nowms)
                # **コマの鍵ごとのマス。** 画面の時間割はこれだけを見る。
                # 旧来の「学年:教科」もコースも、同じ形で引ける。
                keys = [sl.get("key") for sl in teacher_slots(acc) if sl.get("key")]
                if pairs is None:
                    keys = list((lessons.plans(school) or {}).keys())
                out["cells"] = lessons.week_cells(school, keys)
                return self.reply(200, out)

            # ある学年×教科の予定をまとめて読む／入れる
            if len(parts) == 2 and PLAN_KEY.match(parts[1]):
                key = parts[1]
                if not may(key):
                    return self.reply(403, {"error": "担当していない学年です"})
                if method == "GET":
                    p0 = lessons.plan(school, key)
                    got = {"plan": p0}
                    if courses.is_course(p0):
                        # 上位を選ぶ札のために、受け取る生徒を席で渡す（名前は無い）。
                        db0 = accounts(school)
                        by_sid = {a["sid"]: a for a in db0.values()}
                        got["receivers"] = sorted(
                            ({"sid": s, "classId": by_sid[s].get("classId") or "",
                              "seat": seat_of(by_sid[s])}
                             for s in courses.receivers(school, p0, db0) if s in by_sid),
                            key=lambda x: (x["classId"], x["seat"]))
                    return self.reply(200, got)
                if method == "PUT":
                    d = self.body_json() or {}
                    if not may_write(key, str(d.get("classId", ""))[:24]):
                        return self.reply(409, {"error": WRITE_DENIED})
                    rows = d.get("rows")
                    if not isinstance(rows, list) or not rows:
                        return self.reply(400, {"error": "予定が空です"})
                    if len(rows) > 60:
                        return self.reply(400, {"error": "1度に入れられるのは60回までです"})
                    try:
                        weekday = int(d.get("weekday", 0))
                        due_days = int(d.get("dueDays", 7))
                    except (TypeError, ValueError):
                        return self.reply(400, {"error": "曜日と期限は数字で入れてください"})
                    start = str(d.get("start", ""))[:10]
                    if not re.match(r"^\d{4}-\d{2}-\d{2}$", start):
                        return self.reply(400, {"error": "開始日を YYYY-MM-DD で入れてください"})
                    ls = lessons.set_plan(
                        school, key, acc["sid"], str(d.get("classId", ""))[:24],
                        weekday, start, rows, due_days,
                        skip=[str(x)[:10] for x in (d.get("skip") or [])][:40])
                    audit(school, acc["sid"], "set_lessons", key, "%d回" % len(ls))
                    return self.reply(200, {"lessons": ls})

            # 上位（上乗せの宿題を受け取る生徒）を選ぶ。コースだけ。
            # 何を上乗せするかは予定の「上位:」、誰に出すかはここで決める。
            if len(parts) == 3 and parts[2] == "extra" and method == "PUT":
                key = parts[1]
                if not PLAN_KEY.match(key):
                    return self.reply(400, {"error": "bad-key"})
                if not may(key):
                    return self.reply(403, {"error": "担当していない学年です"})
                if not may_write(key):
                    return self.reply(409, {"error": WRITE_DENIED})
                p0 = lessons.plan(school, key)
                if not courses.is_course(p0):
                    return self.reply(400, {"error": "上位を選べるのはコースだけです"})
                d = self.body_json() or {}
                asked = d.get("students")
                if not isinstance(asked, list):
                    return self.reply(400, {"error": "生徒の一覧がありません"})
                who = set(courses.receivers(school, p0, accounts(school)))
                picked = [s for s in dict.fromkeys(asked) if s in who][:40]
                ex = lessons.set_extra(school, key, "top", "上位", picked)
                audit(school, acc["sid"], "set_extra", key, "%d名" % len(picked))
                return self.reply(200, {"extra": ex})

            # 1回ぶんを直す／足す。
            # 学期ぶんを入れ直させない ―― ふだんの用事は「1行だけ直す」。
            if len(parts) == 3 and parts[2] == "row" and method in ("PUT", "POST"):
                key = parts[1]
                if not PLAN_KEY.match(key):
                    return self.reply(400, {"error": "bad-key"})
                if not may(key):
                    return self.reply(403, {"error": "担当していない学年です"})
                if not may_write(key):
                    return self.reply(409, {"error": WRITE_DENIED})
                d = self.body_json() or {}
                topic = d.get("topic")
                text = d.get("text")
                if method == "POST":
                    row = lessons.add(school, key,
                                      str(topic or "（予備）")[:60],
                                      str(text or "")[:120])
                    if row is None:
                        return self.reply(400, {
                            "error": "予定がまだありません。先に学期ぶんを入れてください"})
                    audit(school, acc["sid"], "add_lesson", key,
                          "第%d回" % (row.get("n") or 0))
                    return self.reply(200, {"lesson": row})
                try:
                    n = int(d.get("n"))
                except (TypeError, ValueError):
                    return self.reply(400, {"error": "何回目かを指定してください"})
                row = lessons.edit(school, key, n,
                                   None if topic is None else str(topic)[:60],
                                   None if text is None else str(text)[:120],
                                   stop=bool(d.get("stop")))
                if row is None:
                    return self.reply(404, {"error": "その回はありません"})
                audit(school, acc["sid"], "edit_lesson", key, "第%d回" % n)
                return self.reply(200, {"lesson": row})

            # ずらす。遅れることを前提にした操作。
            if method == "POST" and len(parts) == 3 and parts[2] in ("shift", "insert"):
                key = parts[1]
                if not PLAN_KEY.match(key):
                    return self.reply(400, {"error": "bad-key"})
                if not may(key):
                    return self.reply(403, {"error": "担当していない学年です"})
                if not may_write(key):
                    return self.reply(409, {"error": WRITE_DENIED})
                d = self.body_json() or {}
                try:
                    at = int(d.get("at"))
                except (TypeError, ValueError):
                    return self.reply(400, {"error": "何回目からずらすかを指定してください"})
                if parts[2] == "shift":
                    try:
                        by = int(d.get("by", 1))
                    except (TypeError, ValueError):
                        by = 1
                    # **前へ戻すのも同じ口で通す。**
                    # 授業が予定より早く進むこともある。後ろへしか
                    # 動かせないと、そのとき予定表を捨てるしかない。
                    if by == 0 or abs(by) > 8:
                        return self.reply(400, {
                            "error": "ずらせるのは前後8コマまでです"})
                    r = lessons.shift(school, key, at, by)
                else:
                    r = lessons.insert_blank(school, key, at,
                                             str(d.get("topic", "（予備）"))[:60])
                if r is None:
                    return self.reply(404, {"error": "その予定はありません"})
                audit(school, acc["sid"], "shift_lessons", key, json.dumps(r))
                return self.reply(200, r)
            return self.reply(404, {"error": "not-found"})

        # --- 本部カリキュラムとのズレ ---
        #
        # 基準が入っていないときは **「ズレ無し」と答えない**。
        # 分からないものを 0 と答えると、それは嘘になる。
        if method == "GET" and parts == ["curriculum", "drift"]:
            if acc["role"] != "teacher":
                return self.reply(403, {"error": "forbidden"})
            cur = curriculum(school)
            plans = cur.get("plans") or {}
            grades = teacher_grades(acc)
            if grades is None:
                grades = {g.get("id") for g in (cur.get("grades") or []) if g.get("id")}
            out = [refcur.drift(g, plans) for g in sorted(grades) if g]
            # コースごとの進み具合（シラバスのあるコース）。学年の基準より細かいので、画面はこちらを先に使う。
            return self.reply(200, {"drift": out, "courses": desk_paces(school, acc)})

        # 講師が「この単元は終わった」と記録する。1タップぶんの操作。
        if method == "PUT" and parts == ["curriculum", "done"]:
            if acc["role"] != "teacher":
                return self.reply(403, {"error": "forbidden"})
            d = self.body_json() or {}
            key = str(d.get("key", ""))[:48]
            unit = str(d.get("unit", ""))[:60].strip()
            if not PLAN_KEY.match(key) or not unit:
                return self.reply(400, {"error": "学年と単元を指定してください"})
            # key は "j2:science" の形。学年ではなく、
            # **その学年のその教科**を担当しているかで判る。
            g_key, s_key = (key.split(":") + [""])[:2]
            pairs = teacher_pairs(acc)
            if pairs is not None:
                cur_cls = class_table(school)
                ok = any((cur_cls.get(cid) or {}).get("grade") == g_key and sub == s_key
                         for cid, sub in pairs)
                if not ok:
                    return self.reply(403, {"error": "担当していない教科です"})
            with LOCK:
                cur = curriculum(school)
                plan = (cur.setdefault("plans", {})).setdefault(key, {})
                done = list(plan.get("done") or [])
                if d.get("off"):
                    done = [x for x in done if x != unit]
                elif unit not in done:
                    done.append(unit)
                plan["done"] = done[:400]
                cur["updatedAt"] = int(time.time() * 1000)
                save_curriculum(school, cur)
            audit(school, acc["sid"], "curriculum_done", key, unit)
            return self.reply(200, {"done": plan["done"]})

        # --- 進度（学年 × 科目ごとの分量と範囲）---
        if parts and parts[0] == "curriculum":
            if method == "GET" and len(parts) == 1:
                cur = curriculum(school)
                if acc["role"] != "teacher" and cur.get("classes"):
                    # 生徒にクラスの合言葉を渡さない。進度だけあればよい。
                    # **クラス表の無い校舎では欄ごと送らない。** 空の配列を送ると、
                    # 画面は「クラスが0件」と受け取り、既定のクラス表を使わなくなる
                    # （生徒の名前が「中2R-01」でなく「j2r-01」と出ていた）。
                    cur = dict(cur)
                    cur["classes"] = [{k: v for k, v in c.items() if k != "code"}
                                      for c in cur.get("classes", [])]
                return self.reply(200, {"curriculum": cur})

            if method == "PUT" and len(parts) == 1:
                if acc["role"] != "teacher":
                    return self.reply(403, {"error": "forbidden"})
                d = self.body_json()
                if d is None:
                    return self.reply(400, {"error": "bad-body"})
                try:
                    rec = valid_curriculum(d.get("curriculum") or d)
                except ValueError as e:
                    return self.reply(400, {"error": str(e)})
                with LOCK:
                    stored = curriculum(school)
                    try:
                        rec, touched = merge_curriculum(stored, rec, acc)
                    except ValueError as e:
                        return self.reply(403, {"error": str(e)})
                    rec["updatedAt"] = int(time.time() * 1000)
                    rec["updatedBy"] = acc["sid"]
                    save_curriculum(school, rec)
                audit(school, acc["sid"], "update_curriculum", ",".join(sorted(touched)),
                      "%d件の進度" % len(rec.get("plans", {})))
                return self.reply(200, {"curriculum": rec})
            return self.reply(404, {"error": "not-found"})

        # --- 名簿の一括登録（講師だけ）---
        #
        # 氏名は受け取らない。受け取るのは「学年・クラス・出席番号」だけ。
        # 誰がどの番号かは、先生の手元の名簿にしかない状態を保つ。
        #
        # 1回に作れるのは BULK_MAX 件まで。パスワードのハッシュ化に
        # 1件あたり0.16秒かかるので、300件を1リクエストで作ると
        # 50秒かかって切断される（実測）。画面側が分けて送る。
        if method == "POST" and parts == ["roster", "bulk"]:
            if acc["role"] != "teacher":
                return self.reply(403, {"error": "forbidden"})
            # 管理者のいる校舎では、席は管理ページで作る（合言葉はそこで作り、サーバにはハッシュだけが届く）。
            # 入口を2つにすると、同じ番号の席が2つの作り方でぶつかる。
            if school_managed(school):
                return self.reply(400, {"error": "この校舎では、席は管理ページで作ります。管理する人に伝えてください。"})
            allowed = teacher_classes(acc)
            d = self.body_json() or {}
            rows = d.get("rows")
            if not isinstance(rows, list) or not rows:
                return self.reply(400, {"error": "登録する行がありません"})
            if len(rows) > BULK_MAX:
                return self.reply(400, {
                    "error": "1回に登録できるのは%d名までです（%d名 送られました）"
                             % (BULK_MAX, len(rows))})
            code = school_code(school)
            made, skipped = [], []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                cid = str(r.get("classId", "")).strip()[:24]
                seat = str(r.get("seat", "")).strip()[:8]
                grade = str(r.get("grade", "")).strip()[:16]
                subs = None
                if r.get("subjects") not in (None, ""):
                    try:
                        raw = r.get("subjects")
                        subs = (courses.parse_subjects(raw) if isinstance(raw, str)
                                else [x for x in raw if x in SUBJECT_CODE])
                    except (ValueError, TypeError) as e:
                        skipped.append({"seat": seat, "classId": cid, "why": str(e)})
                        continue
                if allowed is not None and cid not in allowed:
                    skipped.append({"seat": seat, "classId": cid,
                                    "why": "担当外のクラスです"})
                    continue
                if not cid or not SAFE_SEAT.match(seat):
                    skipped.append({"seat": seat, "classId": cid,
                                    "why": "クラスか出席番号の形が正しくありません"})
                    continue
                login_id = "%s%s%s" % (code, cid, seat)
                if not isinstance(r.get("verifier"), dict):
                    skipped.append({"seat": seat, "classId": cid,
                                    "why": "画面が古くなっています。ページを読み込み直してください"})
                    continue
                # **合言葉は、講師の端末が作る。** 届くのは確かめるための値（verifier）だけで、
                # サーバは合言葉を作らないし、返さない（前は、ここで作って平文で返していた）。
                try:
                    add_account(school, login_id, None, seat, "student",
                                grade or gradeOfClass(school, cid), cid, subjects=subs,
                                verifier=r.get("verifier"))
                except ValueError as e:
                    skipped.append({"seat": seat, "classId": cid, "why": str(e)})
                    continue
                made.append({"id": login_id, "classId": cid, "seat": seat})
            if made:
                audit(school, acc["sid"], "roster_bulk", "",
                      "%d名を登録" % len(made))
            return self.reply(200, {"made": made, "skipped": skipped})

        # --- 紙の宿題の評価（講師だけ）---
        #
        # 任意の機能である。つけない講師・つけない週があってよい。
        # 未評価は「欠けている」ではなく「無い」。省いて返す。
        # ============================================================
        # ノートの宿題を、写真で出す
        # ============================================================
        #   POST   /api/submissions/<宿題ID>          生徒が出す
        #   GET    /api/submissions/<宿題ID>          その宿題に出ているもの（講師）
        #   GET    /api/submissions/mine              自分が出したもの（生徒）
        #   GET    /api/submissions/<宿題ID>/<sid>/<名前>   画像そのもの
        #   PUT    /api/submissions/<宿題ID>/<sid>/seen     見ました＋ひとこと（講師）
        #
        # **答案は個人情報である。** 読めるのは本人と、そのクラスの
        # 担当講師だけ。ここで必ずサーバ側で確かめる。
        # --- 版：写真・宿題・メッセージ・評価の台帳が最後に変わった時刻。
        #     パソコンとスマホを行き来しても「開いたら最新」を、これで成立させる。
        #     数十バイトなので 20〜30秒ごとに見に来てもよい。本体は変わったときだけ取る。 ---
        if method == "GET" and parts == ["rev"]:
            out = {}
            for name in ("submissions.json", "assignments.json", "messages.json", "ratings.json", "personal.json"):
                try:
                    out[name.split(".")[0]] = int(os.stat(paths.school_file(school, name)).st_mtime * 1000)
                except OSError:
                    out[name.split(".")[0]] = 0
            return self.reply(200, out)

        if parts and parts[0] == "submissions":

            # --- 生徒: 自分が出したものの一覧 ---
            if method == "GET" and parts == ["submissions", "mine"]:
                if acc["role"] != "student":
                    return self.reply(403, {"error": "forbidden"})
                return self.reply(200,
                                  {"mine": SUB.of_student(school, acc["sid"])})

            # --- 生徒: 出した過去問の点数（自己申告。0〜999、満点は任意。空で消す） ---
            if method == "PUT" and len(parts) == 3 and parts[2] == "score":
                if acc["role"] != "student":
                    return self.reply(403, {"error": "forbidden"})
                data = self.body_json() or {}
                def _num(v):
                    if v is None or v == "":
                        return None
                    try:
                        n = int(v)
                    except (TypeError, ValueError):
                        raise ValueError("数字で書いてください")
                    if n < 0 or n > 999:
                        raise ValueError("0〜999 で書いてください")
                    return n
                try:
                    score, mx = _num(data.get("score")), _num(data.get("max"))
                except ValueError as e:
                    return self.reply(400, {"error": str(e)})
                if score is not None and mx and score > mx:
                    return self.reply(400, {"error": "点数が満点を超えています"})
                got = SUB.put_score(school, parts[1], acc["sid"], score, mx)
                if not got:
                    return self.reply(404, {"error": "まだ出していません"})
                return self.reply(200, {"ok": True, "item": got})

            # --- 生徒: 出す ---
            if method == "POST" and len(parts) == 2:
                if acc["role"] != "student":
                    return self.reply(403, {"error": "forbidden"})
                aid = parts[1]
                a = assignments(school).get(aid)
                if not a:
                    return self.reply(404, {"error": "no-assignment"})
                if acc["sid"] not in students_for(school, a):
                    return self.reply(403, {"error": "自分の宿題ではありません"})
                # 導入の段階が「写真で提出」（2）より前のコースは、写真を受けない（紙で先生に直接）。
                if not course_use_of(school, a)["photo"]:
                    return self.reply(400, {"error": "この宿題は、紙で先生に出してください"})
                data = self.body_json()
                if not data:
                    return self.reply(413, {"error": "写真が大きすぎます。"
                                                     "1枚ずつ出してみてください"})
                files = []
                for f in (data.get("files") or [])[:SUB.MAX_FILES]:
                    kind = paths.SUBMIT_KIND.get(str((f or {}).get("type") or ""))
                    if not kind:
                        return self.reply(400,
                            {"error": "写真（JPEG・PNG）かPDFだけ出せます"})
                    try:
                        raw = base64.b64decode(str(f.get("b64") or ""),
                                               validate=True)
                    except (ValueError, binascii.Error):
                        return self.reply(400, {"error": "写真を読めませんでした"})
                    files.append({"kind": kind, "data": raw})
                try:
                    got = SUB.put(school, aid, acc["sid"], files)
                except (ValueError, paths.BadPath) as e:
                    return self.reply(400, {"error": str(e)})
                audit(school, acc["sid"], "submit_hw", acc["sid"],
                      "%s %d枚" % (aid, len(files)))
                return self.reply(200, {"ok": True, "sub": got})

            # ここから先は講師。担当クラスの宿題だけを見る。
            def owns_sub(aid):
                a = assignments(school).get(aid)
                if not a:
                    return None
                sub = subject_of_assignment(a)
                if not may_touch(school, acc, a, sub or None):
                    return False
                return a

            # --- 講師: その宿題に出ているもの ---
            if method == "GET" and len(parts) == 2:
                if acc["role"] != "teacher":
                    return self.reply(403, {"error": "forbidden"})
                a = owns_sub(parts[1])
                if a is None:
                    return self.reply(404, {"error": "no-assignment"})
                if a is False:
                    return self.reply(403, {"error": "担当外のクラスです"})
                return self.reply(200,
                                  {"subs": SUB.of_assignment(school, parts[1])})

            # --- 印刷用の紙（講師）：この生徒の全ページを A4 に1枚ずつ。開くと印刷の窓が出る ---
            #     PDF より1タッチ少ない（保存せずにそのまま印刷）。赤を入れたら撮って「添削を返す」。
            if method == "GET" and len(parts) == 4 and parts[3] == "print":
                aid, sid = parts[1], parts[2]
                if acc["role"] != "teacher" or not SAFE_SID.match(sid):
                    return self.reply(403, {"error": "forbidden"})
                a = owns_sub(aid)
                if a is None:
                    return self.reply(404, {"error": "no-assignment"})
                if a is False:
                    return self.reply(403, {"error": "担当外のクラスです"})
                got = (SUB.of_assignment(school, aid) or {}).get(sid) or {}
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                which = (q.get("which") or [""])[0]
                tok = (q.get("t") or [""])[0]
                files = (got.get("returned") or {}).get("files") if which == "returned" else got.get("files")
                files = [f for f in (files or []) if f.get("kind") in ("jpg", "png")]
                label = desk_labels(school).get(sid, sid)
                title = a.get("title") or ""
                due = time.strftime("%-m/%-d", time.localtime((a.get("dueAt") or 0) / 1000.0)) if a.get("dueAt") else ""
                esc_ = lambda x: str(x).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
                pages = "".join(
                    '<section class="pg"><img alt="%d ページ目" src="/api/submissions/%s/%s/%s?t=%s"></section>'
                    % (i + 1, urllib.parse.quote(aid), urllib.parse.quote(sid), urllib.parse.quote(f["name"]), urllib.parse.quote(tok))
                    for i, f in enumerate(files))
                html = ("<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
                        "<title>%s %s</title>"
                        "<style>@page{size:A4;margin:10mm} html,body{margin:0;background:#fff;color:#17150F;font-family:-apple-system,'Hiragino Sans',sans-serif}"
                        ".ph{font-size:11pt;padding:6mm 8mm 0;display:flex;justify-content:space-between;color:#333}"
                        ".pg{height:268mm;display:flex;align-items:flex-start;justify-content:center;padding:4mm 8mm;box-sizing:border-box;page-break-after:always}"
                        ".pg img{max-width:100%%;max-height:100%%;object-fit:contain}"
                        ".pf{font-size:9pt;color:#777;padding:0 8mm 6mm} @media screen{body{background:#eee} .pg{background:#fff;margin:8px auto;width:210mm;box-shadow:0 2px 12px rgba(0,0,0,.15)}}</style>"
                        "<script src=\"/js/print.js\" defer></script></head><body>"
                        "<div class=\"ph\"><b>%s</b><span>%s%s</span><span>tubestudy</span></div>%s"
                        "<div class=\"pf\">赤を入れたら、宿題チェックの「赤を入れて、撮る」で返せます。</div></body></html>"
                        % (esc_(label), esc_(title), esc_(label), esc_(title), ("　" + esc_(due) + "〆") if due else "", pages or "<p class=\"pg\">写真はまだありません</p>"))
                audit(school, acc["sid"], "print_submission", sid, aid)
                return self.reply_html(200, html)

            # --- 答案を A4 の PDF に（印刷して赤を入れる）。生徒は自分の分、講師は担当の分 ---
            if method == "GET" and len(parts) == 4 and parts[3] == "pdf":
                aid, sid = parts[1], parts[2]
                if not SAFE_SID.match(sid):
                    return self.reply(400, {"error": "bad-sid"})
                if acc["role"] == "student":
                    if sid != acc["sid"]:
                        return self.reply(403, {"error": "forbidden"})
                else:
                    a = owns_sub(aid)
                    if a is None:
                        return self.reply(404, {"error": "no-assignment"})
                    if a is False:
                        return self.reply(403, {"error": "担当外のクラスです"})
                got = (SUB.of_assignment(school, aid) or {}).get(sid) or {}
                which = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("which") or [""])[0]
                files = (got.get("returned") or {}).get("files") if which == "returned" else got.get("files")
                files = files or []
                imgs = []
                for f in files:
                    try:
                        with io.open(paths.submit_file(school, sid, f.get("name") or ""), "rb") as fh:
                            raw = fh.read()
                    except (OSError, paths.BadPath):
                        continue
                    if f.get("kind") == "pdf":
                        if len(files) == 1:
                            return self.reply_bytes(200, raw, "application/pdf")
                        continue
                    imgs.append((f.get("kind"), raw))
                try:
                    pdf = pdfout.build(imgs)
                except ValueError as e:
                    return self.reply(404, {"error": str(e)})
                if acc["role"] == "teacher":
                    audit(school, acc["sid"], "print_submission", sid, aid)
                return self.reply_bytes(200, pdf, "application/pdf")

            # --- 画像そのもの ---
            if method == "GET" and len(parts) == 4:
                aid, sid, name = parts[1], parts[2], parts[3]
                if not SAFE_SID.match(sid):
                    return self.reply(400, {"error": "bad-sid"})
                if acc["role"] == "student":
                    if sid != acc["sid"]:
                        return self.reply(403, {"error": "forbidden"})
                else:
                    a = owns_sub(aid)
                    if a is None:
                        return self.reply(404, {"error": "no-assignment"})
                    if a is False:
                        return self.reply(403, {"error": "担当外のクラスです"})
                got = (SUB.of_assignment(school, aid) or {}).get(sid) or {}
                hit = [f for f in SUB.all_files(got) if f.get("name") == name]
                if not hit:
                    return self.reply(404, {"error": "no-file"})
                try:
                    p = paths.submit_file(school, sid, name)
                    with io.open(p, "rb") as fh:
                        raw = fh.read()
                except (OSError, paths.BadPath):
                    return self.reply(404, {"error": "no-file"})
                if acc["role"] == "teacher":
                    audit(school, acc["sid"], "read_submission", sid, aid)
                mime = {"jpg": "image/jpeg", "png": "image/png",
                        "pdf": "application/pdf"}[hit[0]["kind"]]
                return self.reply_bytes(200, raw, mime)

            # --- 講師: 対面の生徒の紙を取り込む（scan）／ 添削した答案を返す（return） ---
            if method == "POST" and len(parts) == 4 and parts[3] in ("scan", "return"):
                if acc["role"] != "teacher":
                    return self.reply(403, {"error": "forbidden"})
                aid, sid = parts[1], parts[2]
                if not SAFE_SID.match(sid):
                    return self.reply(400, {"error": "bad-sid"})
                a = owns_sub(aid)
                if a is None:
                    return self.reply(404, {"error": "no-assignment"})
                if a is False:
                    return self.reply(403, {"error": "担当外のクラスです"})
                if sid not in students_for(school, a):
                    return self.reply(403, {"error": "この宿題の生徒ではありません"})
                # 添削を返すのは、導入の段階が「添削まで」（3）以上のコースだけ。取り込み（scan）は 1 以上で使える。
                if parts[3] == "return" and not course_use_of(school, a)["correct"]:
                    return self.reply(400, {"error": "このコースでは添削を使っていません（導入と進度で「添削まで」にすると使えます）"})
                data = self.body_json()
                if not data:
                    return self.reply(413, {"error": "ファイルが大きすぎます。1枚ずつ取り込んでみてください"})
                files = []
                for f in (data.get("files") or [])[:SUB.MAX_FILES]:
                    kind = paths.SUBMIT_KIND.get(str((f or {}).get("type") or ""))
                    if not kind:
                        return self.reply(400, {"error": "写真（JPEG・PNG）かPDFだけ取り込めます"})
                    try:
                        raw = base64.b64decode(str(f.get("b64") or ""), validate=True)
                    except (ValueError, binascii.Error):
                        return self.reply(400, {"error": "ファイルを読めませんでした"})
                    files.append({"kind": kind, "data": raw})
                try:
                    if parts[3] == "scan":
                        got = SUB.put_by_teacher(school, aid, sid, files, acc["sid"])
                    else:
                        got = SUB.put_return(school, aid, sid, files, acc["sid"], data.get("note"))
                except (ValueError, paths.BadPath) as e:
                    return self.reply(400, {"error": str(e)})
                audit(school, acc["sid"], "scan_submission" if parts[3] == "scan" else "return_submission",
                      sid, "%s %d枚" % (aid, len(files)))
                return self.reply(200, {"ok": True, "sub": got})

            # --- 講師: 見ました＋ひとこと ---
            if method == "PUT" and len(parts) == 4 and parts[3] == "seen":
                if acc["role"] != "teacher":
                    return self.reply(403, {"error": "forbidden"})
                aid, sid = parts[1], parts[2]
                if not SAFE_SID.match(sid):
                    return self.reply(400, {"error": "bad-sid"})
                a = owns_sub(aid)
                if a is None:
                    return self.reply(404, {"error": "no-assignment"})
                if a is False:
                    return self.reply(403, {"error": "担当外のクラスです"})
                data = self.body_json() or {}
                got = SUB.mark_seen(school, aid, sid, acc["sid"],
                                    data.get("note") or "")
                if not got:
                    return self.reply(404, {"error": "no-submission"})
                audit(school, acc["sid"], "seen_submission", sid, aid)
                return self.reply(200, {"ok": True, "sub": got})

            return self.reply(404, {"error": "no-route"})

        if parts and parts[0] == "ratings":
            if acc["role"] != "teacher":
                return self.reply(403, {"error": "forbidden"})
            def owns(aid):
                a = assignments(school).get(aid)
                if not a:
                    return None
                # 出した本人の教科だけ。ほかの教科の宿題は、
                # 同じクラスでも書き換えさせない。
                sub = subject_of_assignment(a)
                if not may_touch(school, acc, a, sub or None):
                    return False
                return a

            if method == "GET" and len(parts) == 2:
                a = owns(parts[1])
                if a is None:
                    return self.reply(404, {"error": "no-assignment"})
                if a is False:
                    return self.reply(403, {"error": "担当外のクラスです"})
                per = ratings(school).get(parts[1]) or {}
                # 評価が付いている生徒だけを返す。付いていない生徒は載せない。
                return self.reply(200, {"ratings": per})

            if len(parts) == 3 and method in ("PUT", "DELETE"):
                aid, sid = parts[1], parts[2]
                if not SAFE_SID.match(sid):
                    return self.reply(400, {"error": "bad-sid"})
                a = owns(aid)
                if a is None:
                    return self.reply(404, {"error": "no-assignment"})
                if a is False:
                    return self.reply(403, {"error": "担当外のクラスです"})
                if sid not in students_for(school, a):
                    return self.reply(403, {"error": "この宿題の対象ではありません"})
                with LOCK:
                    db = ratings(school)
                    per = db.setdefault(aid, {})
                    if method == "DELETE":
                        # 押し間違いの取り消し。0（出ていない）とは違う。
                        per.pop(sid, None)
                        if not per:
                            db.pop(aid, None)
                    else:
                        d = self.body_json() or {}
                        try:
                            v = int(d.get("v"))
                        except (TypeError, ValueError):
                            return self.reply(400, {"error": "評価は0〜5で入れてください"})
                        if not ratescale.valid(v):
                            return self.reply(400, {"error": "評価は0〜5で入れてください"})
                        per[sid] = ratescale.record(v, acc["sid"])
                    save_ratings(school, db)
                audit(school, acc["sid"], "rate_paper", aid, sid)
                # 要約に反映しておく。講師の一覧が次に開いたとき最新になる。
                try:
                    blob = (paths.load(progress_path(school, sid), None) or {}).get("blob") or {}
                    c = hw_cache()          # 名簿を宿題ごとに読み直さない
                    mine = [x for x in assignments(school).values()
                            if sid in students_for(school, x, c)]
                    update_summary(school, sid, blob, mine)
                except (IOError, BadPath, KeyError):
                    pass
                return self.reply(200, {"ok": True})
            return self.reply(404, {"error": "not-found"})

        # --- 講師の机：今日やること・宿題チェック・成績の診断・生徒ごとの宿題・塾内テスト ---
        # （Claude outputs/PLAN-講師ページ改修.md）。講師だけ、自分のコースだけ。
        if parts and parts[0] in ("today", "check", "insight", "personal", "scores", "presets", "quiz"):
            if acc["role"] != "teacher":
                return self.reply(403, {"error": "forbidden"})
            return self.teacher_desk(school, acc, method, parts)

        # --- 教材（どこで解くか を含む）---
        # 生徒の画面も、紙の宿題を「やるべきこと」ではなく
        # 「ノートでやる」と出し分けるために、これを読む。
        if parts and parts[0] == "materials":
            lib = materials(school)
            if method == "GET" and len(parts) == 1:
                mine = adopted(school, acc["sid"]) if acc["role"] == "teacher" else None
                return self.reply(200, {
                    # 校舎が持っている全教材（原本）
                    "materials": [dict(m, id=mid) for mid, m in sorted(lib.items())],
                    # そのうち、この講師が使うと決めたもの。null は「ぜんぶ」
                    "adopted": mine,
                    # コースごとに選び直したもの（コースの鍵 → ID）。無いコースは adopted
                    "adoptedByCourse": adopted_by_course(school, acc["sid"]) if acc["role"] == "teacher" else {},
                })

            # 講師が「自分が使う教材」を選び直す。
            # 校舎の原本には触らない ―― 消えるのは自分の一覧からだけ。
            # 教材ごとに「採点する／出すだけ」を切り替える。
            # 校舎の原本を書き換えるので、全講師に効く ―― 計算ドリルを
            # 採点しないのは校舎の方針であって、講師ごとの好みではない。
            if method == "PUT" and parts == ["materials", "graded"]:
                if acc["role"] != "teacher":
                    return self.reply(403, {"error": "forbidden"})
                d = self.body_json() or {}
                mid = str(d.get("id", ""))[:40]
                if mid not in lib:
                    return self.reply(400, {"error": "その教材はありません"})
                on = bool(d.get("graded"))
                f = materials_file(school)
                items = f.setdefault("items", {})
                m = dict(items.get(mid) or lib.get(mid) or {})
                m["graded"] = on
                items[mid] = m
                paths.save(paths.school_file(school, "materials.json"), f)
                audit(school, acc["sid"], "material_graded", mid,
                      "採点する" if on else "出すだけ")
                return self.reply(200, {"ok": True, "graded": on})

            if method == "PUT" and parts == ["materials", "adopted"]:
                if acc["role"] != "teacher":
                    return self.reply(403, {"error": "forbidden"})
                d = self.body_json() or {}
                ids = d.get("ids")
                if not isinstance(ids, list):
                    return self.reply(400, {"error": "bad-body"})
                unknown = [x for x in ids if x not in lib]
                if unknown:
                    return self.reply(400, {
                        "error": "校舎にない教材です: %s" % ", ".join(map(str, unknown[:3]))})
                course = str(d.get("course") or "")[:40]
                if course:
                    # コースごと（見本 T20）。ほかのコースと校舎の教材はそのまま
                    set_adopted_course(school, acc["sid"], course, ids)
                    audit(school, acc["sid"], "adopt_materials", course, "%d件" % len(ids))
                    return self.reply(200, {"adopted": ids, "course": course})
                set_adopted(school, acc["sid"], ids)
                audit(school, acc["sid"], "adopt_materials", "", "%d件" % len(ids))
                return self.reply(200, {"adopted": ids})

            # 校舎の教材を1つ足す（講師が自分の冊子を登録する）。
            if method == "POST" and len(parts) == 1:
                if acc["role"] != "teacher":
                    return self.reply(403, {"error": "forbidden"})
                d = self.body_json() or {}
                mid = str(d.get("id", "")).strip().lower()[:40]
                if not re.match(r"^[a-z0-9][a-z0-9_-]{1,39}$", mid):
                    return self.reply(400, {
                        "error": "教材のIDは英小文字・数字・_ - で2〜40文字にしてください"})
                if mid in lib:
                    return self.reply(400, {"error": "そのIDの教材はすでにあります"})
                name = str(d.get("name", "")).strip()[:60]
                if not name:
                    return self.reply(400, {"error": "教材の名前を入れてください"})
                try:
                    mx = int(d.get("max") or 0)
                except (TypeError, ValueError):
                    return self.reply(400, {"error": "問題数は数字で入れてください"})
                if not (1 <= mx <= 20000):
                    return self.reply(400, {"error": "問題数は1〜20000で入れてください"})
                mode = "paper" if d.get("mode") == "paper" else "app"
                # 学年（2つ以上なら「学年共通」の1冊）と別名（さがすときだけ使う）。見本 T20
                grades = [str(g)[:8] for g in (d.get("grades") or []) if str(g).strip()][:8] if isinstance(d.get("grades"), list) else []
                alias = [str(a).strip()[:40] for a in (d.get("alias") or []) if str(a).strip()][:6] if isinstance(d.get("alias"), list) else []
                with LOCK:
                    f = materials_file(school)
                    item = {
                        "name": name, "short": str(d.get("short", ""))[:12] or name[:8],
                        "subject": str(d.get("subject", ""))[:16] or "english",
                        "max": mx, "mode": mode,
                        "addedBy": acc["sid"], "addedAt": int(time.time()),
                    }
                    if grades:
                        item["grades"] = grades
                    if alias:
                        item["alias"] = alias
                    f.setdefault("items", {})[mid] = item
                    paths.save(paths.school_file(school, "materials.json"), f)
                audit(school, acc["sid"], "add_material", mid, name)
                return self.reply(200, {"ok": True, "id": mid})
            return self.reply(404, {"error": "not-found"})

        # --- 宿題の下書き（講師のカリキュラムから自動で組む）---
        #
        # 講師が毎週ゼロから宿題を打つのは続かない。進度に「今週はここ」と
        # 入っているなら、それをそのまま宿題の形にして出しておき、
        # 講師は確認して押すだけにする。直したいときだけ直す。
        if method == "POST" and parts == ["assignments", "draft"]:
            if acc["role"] != "teacher":
                return self.reply(403, {"error": "forbidden"})
            d = self.body_json() or {}
            try:
                due = int(d.get("dueAt"))
            except (TypeError, ValueError):
                return self.reply(400, {"error": "期限を入れてください"})
            allowed = teacher_classes(acc)
            cur = curriculum(school)
            by_id = {c["id"]: c for c in (cur.get("classes") or [])}
            mats = materials(school)
            out = []
            for cid in ([c["id"] for c in cur.get("classes", [])]
                        if allowed is None else allowed):
                k = by_id.get(cid)
                if not k:
                    continue
                for key, plan in (cur.get("plans") or {}).items():
                    if not key.startswith((k.get("grade") or "") + ":"):
                        continue
                    if not plan.get("enabled"):
                        continue
                    for src in (plan.get("packs") or [])[:4]:
                        m = mats.get(src) or {}
                        lo = int(plan.get("next", {}).get(src, 1) or 1)
                        step = int(sum((plan.get("daily") or {}).values()) or 10) * 7
                        hi = lo + max(1, step) - 1
                        out.append({
                            "title": "%s No.%d-%d" % (m.get("name", src), lo, hi),
                            "source": src, "from": lo, "to": hi,
                            "classId": cid, "students": [], "dueAt": due,
                            "route": route_of(school, src),
                            "note": "進度から自動で作りました。直せます。",
                        })
            return self.reply(200, {"draft": out[:40]})

        # --- 宿題 ---
        # 保護者への連絡のための書き出し（講師×週）。名前も宛先も入らない。
        # 名前と宛先は、校舎の対応表が手元で重ねる（outbox.py の説明）。
        if method == "GET" and parts == ["hw", "outbox"]:
            if acc["role"] != "teacher":
                return self.reply(403, {"error": "forbidden"})
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            week = (q.get("week") or [""])[0] or OUTBOX.week_of()
            try:
                OUTBOX.week_days(week)
            except ValueError as e:
                return self.reply(400, {"error": str(e)})
            with PUBLISH_LOCK:
                publish_courses(school, "system")
            got = OUTBOX.build(week, acc["sid"], courses.of_teacher(school, acc["sid"]),
                               assignments(school), accounts(school), seat_of=seat_of)
            audit(school, acc["sid"], "hw_outbox", week, "%d名" % len(got["students"]))
            return self.reply(200, got)

        # 特筆事項（講師だけ）。生徒×教科の短いメモ。生徒には返さない。
        if len(parts) == 2 and parts[0] == "notes" and method in ("GET", "PUT"):
            sid = parts[1]
            if not SAFE_SID.match(sid):
                return self.reply(400, {"error": "bad-sid"})
            if acc["role"] != "teacher" or not self.may_read(acc, sid):
                return self.reply(403, {"error": "forbidden"})
            if method == "GET":
                return self.reply(200, {"notes": NOTES.of_student(school, sid)})
            d = self.body_json() or {}
            try:
                got = NOTES.put(school, sid, d.get("subject"), d.get("text"), acc["sid"])
            except ValueError as e:
                return self.reply(400, {"error": str(e)})
            audit(school, acc["sid"], "put_note", sid, str(d.get("subject") or ""))
            return self.reply(200, {"notes": got})

        if parts and parts[0] == "assignments":
            teacher = (acc["role"] == "teacher")
            allowed = teacher_classes(acc)
            blobs = hw_cache()          # このリクエストの間の控え（名簿・進捗・評価・写真）

            def visible(a):
                if teacher:
                    # **教科まで見る。** クラスだけで判定すると、
                    # 中2Rの英語の先生に中2Rの数学の宿題まで見えてしまう。
                    # 教科が分からない宿題（手で出した古いもの）は、
                    # そのクラスの担当なら見せる ―― 隠すと復旧できない。
                    sub = subject_of_assignment(a)
                    return may_touch(school, acc, a, sub or None)
                return acc["sid"] in students_for(school, a, blobs)

            if method == "GET" and len(parts) == 1:
                # 授業日が来たコースの宿題を、ここでも出す（何度呼んでも同じ）。
                # 講師が格子を開くのを待つと、誰も開かない週に宿題が出ない。
                with PUBLISH_LOCK:
                    publish_courses(school, "system")
                out = []
                # 紙の宿題を出したかどうかは、講師が付けた評価でしか分からない。
                # 評価があるものを「おくれ」と出すと、ノートで出した子に
                # 嘘をつくことになる ―― 生徒にも渡しておく。
                mine_rated = ({} if teacher
                              else ratings_for_student(school, acc["sid"]))
                # **進捗の読み込みを1人1回にする。**
                # ここは宿題1件ごとに全員ぶんを数えるので、控えが無いと
                # 生徒2000名・宿題360件で4万回ディスクを読む。
                # 講師の評価が無いまま期限から7日過ぎた紙の宿題（写真は出ている）は、仮に4（できた）で渡す。
                # 「付け忘れ＝最低評価」を防ぐ（本人）。束（同じ回）は代表の写真で見る。講師の画面は未評価のまま。
                prov_memo = {}
                if not teacher:
                    by_kn = {}
                    for x in assignments(school).values():
                        ls = x.get("lesson") or {}
                        if ls.get("key"):
                            by_kn.setdefault((ls["key"], ls.get("n")), []).append(x)
                    subs_all = subs_cached(school, blobs)
                    nowms = time.time() * 1000

                def prov_of(a):
                    if (a.get("route") or "app") != "paper" or a.get("graded") is False:
                        return None
                    ls = a.get("lesson") or {}
                    k = (ls.get("key"), ls.get("n")) if ls.get("key") else ("", a["id"])
                    if k not in prov_memo:
                        items = (by_kn.get(k) if ls.get("key") else None) or [a]
                        b = INSIGHT.student_bundle(items, acc["sid"])
                        st = INSIGHT.student_state(b, acc["sid"], {}, subs_all, {}, nowms)
                        due = INSIGHT.due_of(b["paper"]) if b["paper"] else 0
                        prov_memo[k] = ({"v": INSIGHT.PROVISIONAL_V, "provisional": True,
                                         "at": int(due / 1000) + INSIGHT.PROVISIONAL_DAYS * 86400}
                                        if st.get("prov") else None)
                    return prov_memo[k]

                # 古い宿題は既定で出さない（1年より前）。台帳は年々増えるが、画面に要るのは今年度ぶん。
                # ?all=1 で全部（記録の書き出しなど）。
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                since = 0 if (q.get("all") or [""])[0] == "1" else int((time.time() - HW_KEEP_DAYS * 86400) * 1000)
                for aid, a in assignments(school).items():
                    if since and max(int(a.get("dueAt") or 0), int(a.get("assignedAt") or 0)) < since:
                        continue
                    if not visible(a):
                        continue
                    row = dict(a)
                    if teacher:
                        # 講師には誰がどこまで終えたかを付ける
                        row["summary"] = hw_summary(school, a, blobs)
                    elif aid in mine_rated:
                        # 5段階に読み替えて渡す。前の4段階（0〜3）の評価を
                        # そのまま渡すと、生徒の画面で違う言葉になる。
                        r = mine_rated[aid]
                        row["rated"] = {"v": ratescale.value(r), "at": r.get("at")}
                    elif prov_of(a):
                        row["rated"] = dict(prov_of(a))
                    out.append(row)
                out.sort(key=lambda x: x.get("dueAt") or 0)
                return self.reply(200, {"assignments": out})

            # 総復習テスト対策の紙。A3 1枚・左右2段。
            #
            #   GET /api/assignments/prep/sheet?subject=science[&sid=…][&tier=…]
            #
            # 返すのは HTML。ブラウザの「PDFとして保存」で1枚になる。
            # PDF を組む道具は入れない ―― 日本語のフォントを置き、
            # 行分けを自分で書くことになり、本筋から外れる。
            if method == "GET" and parts[:2] == ["assignments", "prep"] \
                    and len(parts) == 3 and parts[2] == "sheet":
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                sub = (q.get("subject") or [""])[0][:24]
                tier = (q.get("tier") or [""])[0][:12]
                if acc["role"] == "student":
                    sid, grade = acc["sid"], acc.get("level") or ""
                else:
                    sid = (q.get("sid") or [""])[0][:32]
                    if sid:
                        _, tgt = find_by_sid(school, sid)
                        if not tgt or not self.may_read(acc, sid):
                            return self.reply(403, {"error": "担当外です"})
                        grade = tgt.get("level") or ""
                    else:
                        cid = (q.get("classId") or [""])[0][:24]
                        # **教科までは問わない。** この紙には生徒の情報が
                        # 1つも入らない（問題と解答らんだけ）。
                        # 算数を持つ講師が、同じクラスの英語の紙を見て
                        # 生徒に説明できないほうが困る。
                        # 生徒を名指し（?sid=）するときだけ、厳しく見る。
                        if not can_see(acc, cid, None):
                            return self.reply(403, {"error": "担当外のクラスです"})
                        grade = (class_table(school).get(cid) or {}).get("grade") or ""
                got = self.prep_for(school, grade, sid, tier)
                if not got:
                    return self.reply_html(200,
                        "<!doctype html><meta charset=utf-8>"
                        "<p style='font-family:sans-serif;padding:40px'>" +
                        ("今は" if grade in ("e6", "j1", "j2", "j3") else "いまは") +
                        "総復習テスト対策の時期ではありません。</p>")
                # **教科を混ぜた紙は作らない。**
                # 本番の組み分けテストは1教科ずつ・A4たてで、時間も
                # 教科ごとに区切られている。5教科を1枚に混ぜた紙は、
                # 時間配分の練習にならない。
                if not sub:
                    return self.reply_html(400,
                        "<!doctype html><meta charset=utf-8>"
                        "<p style='font-family:sans-serif;padding:40px'>"
                        "教科をえらんでください。"
                        "アプリの毎日テストで、教科ごとに「紙にする」を押せます。</p>")
                sets = [x for x in got["sets"] if x["subject"] == sub]
                if not sets:
                    return self.reply(404, {"error": "その教科はありません"})
                audit(school, acc["sid"], "prep_sheet",
                      sid or grade, "%s %s" % (sub or "全教科", got["tier"]))
                # **刷った紙をおぼえておく。**
                #
                # 生徒はパソコンで解いて、スマホで写真を撮る。そのとき
                # スマホ側で「どの教科の紙ですか」と聞き直すのは無駄である
                # ―― 同じアカウントが数分前に何を刷ったかは分かっている。
                #
                # おぼえるのは「教科・版・時刻」だけ。答案そのものは
                # どこにも送らないし、置かない（カメラの読み取りは端末の中で終わる）。
                if acc["role"] == "student":
                    remember_sheet(school, acc["sid"], sub,
                                   got.get("tier") or "",
                                   [i["id"] for i in prepsheet.paper_items(sets)])
                name = subject_name(sub, grade)
                gname = grade_name(grade)
                return self.reply_html(200,
                    prepsheet.for_prep(got, name, gname, sets,
                        auto_print=(q.get("print") or ["0"])[0] == "1"))

            # --- 対策テストの結果を受け取る ---
            #
            #   POST /api/assignments/prep/result
            #     {"subject": "english",
            #      "rows": [{"id": …, "right": true, "blank": false}, …]}
            #
            # **答案の画像は受け取らない。** 送られてくるのは、端末の中で
            # 読み終わったあとの「どの問題が合っていたか」だけ。
            # サーバに置くのは、そこから数えた単元ごとの落とし数である。
            if (method == "POST" and len(parts) == 3
                    and parts[1] == "prep" and parts[2] == "result"):
                if acc["role"] != "student":
                    return self.reply(403, {"error": "forbidden"})
                data = self.body_json() or {}
                sub = str(data.get("subject") or "")[:24]
                rows = data.get("rows") or []
                if not sub or not isinstance(rows, list):
                    return self.reply(400, {"error": "bad-body"})
                grade = acc.get("level") or ""
                # 問題IDから単元を引く。**画面から送られた単元は使わない** ――
                # 送る側を信じると、いくらでも書き換えられる。
                byid = {x["id"]: x for x in examprep.pack_items(sub, grade)}
                got = []
                for r in rows[:400]:
                    if not isinstance(r, dict):
                        continue
                    it = byid.get(str(r.get("id") or ""))
                    got.append({
                        "unit": (it or {}).get("unit") or "",
                        "right": bool(r.get("right")),
                        "blank": bool(r.get("blank")),
                    })
                weak.record(school, acc["sid"], sub, got)
                audit(school, acc["sid"], "prep_result", acc["sid"],
                      "%s %d問" % (sub, len(got)))
                return self.reply(200, {"ok": True,
                                        "weak": weak.weak_units(school,
                                                                acc["sid"], sub)})

            # --- 苦手単元の再テスト ---
            #
            #   GET /api/assignments/prep/retest?subject=english
            #
            # 落とした単元だけを集めた4択。紙にはしない ―― 直したいのは
            # 数単元ぶんで、刷るほどの量にならないうえ、その場で
            # 答え合わせできるほうが早く直る。
            if (method == "GET" and len(parts) == 3
                    and parts[1] == "prep" and parts[2] == "retest"):
                if acc["role"] != "student":
                    return self.reply(403, {"error": "forbidden"})
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                sub = (q.get("subject") or [""])[0][:24]
                grade = acc.get("level") or ""
                wk = [x for x in weak.weak_units(school, acc["sid"], sub)
                      if not x["fixed"]]
                if not sub or not wk:
                    return self.reply(200, {"items": [], "units": []})
                names = [x["unit"] for x in wk]
                pool = [x for x in examprep.pack_items(sub, grade)
                        if (x.get("unit") or "") in names and x.get("dis")]
                # 苦手の重い単元から順に、多めに取る。
                heavy = {x["unit"]: x["w"] for x in wk}
                pool.sort(key=lambda x: -heavy.get(x.get("unit") or "", 0))
                # 中身をそのまま返す。**一覧用に削らない** ――
                # 再テストはその場で解くので、選択肢と解説が要る。
                items = pool[:RETEST_MAX]
                return self.reply(200, {"items": items, "units": names})

            # --- 苦手単元の再テストが終わった ---
            #
            #   POST /api/assignments/prep/retest  {"subject", "units", "ok", "n"}
            if (method == "POST" and len(parts) == 3
                    and parts[1] == "prep" and parts[2] == "retest"):
                if acc["role"] != "student":
                    return self.reply(403, {"error": "forbidden"})
                data = self.body_json() or {}
                sub = str(data.get("subject") or "")[:24]
                units = [str(u)[:40] for u in (data.get("units") or [])][:20]
                n = max(0, int(data.get("n") or 0))
                ok = max(0, min(n, int(data.get("ok") or 0)))
                fixed = weak.mark_fixed(school, acc["sid"], sub, units,
                                        (ok / float(n)) if n else 0.0)
                return self.reply(200, {"ok": True, "fixed": fixed})

            # 直前にパソコンで刷った紙は何か。
            #
            #   GET /api/assignments/prep/last  ->  {subject, tier, at} または {}
            #
            # スマホでカメラを開いたとき、教科を選ばせずに済ませるためだけの
            # もの。**自分の分しか返さない。** 講師にも返さない ――
            # 誰がいつ何を刷ったかは、この用途には要らない。
            if (method == "GET" and len(parts) == 3
                    and parts[1] == "prep" and parts[2] == "last"):
                if acc["role"] != "student":
                    return self.reply(403, {"error": "forbidden"})
                v = last_sheet(school, acc["sid"]) or {}
                # 並びは返さない。使うのはサーバ側だけで、
                # スマホに送っても大きくなるだけである。
                return self.reply(200, {k: v[k] for k in v if k != "ids"})

            # 総復習テスト対策 ―― 組み分けテストの8日前から。
            #
            #   GET /api/assignments/prep          一覧（何問・何分）
            #   GET /api/assignments/prep?full=1   中身つき（始めるとき）
            #
            # 講師は ?sid= で生徒を、?classId=&tier= で見本を見られる。
            if method == "GET" and len(parts) == 2 and parts[1] == "prep":
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                full = (q.get("full") or ["0"])[0] == "1"
                if acc["role"] == "student":
                    sid, grade = acc["sid"], acc.get("level") or ""
                else:
                    sid = (q.get("sid") or [""])[0][:32]
                    if sid:
                        _, tgt = find_by_sid(school, sid)
                        if not tgt or not self.may_read(acc, sid):
                            return self.reply(403, {"error": "担当外です"})
                        grade = tgt.get("level") or ""
                    else:
                        cid = (q.get("classId") or [""])[0][:24]
                        if not can_see(acc, cid):
                            return self.reply(403, {"error": "担当外です"})
                        grade = (class_table(school).get(cid) or {}).get("grade") or ""
                got = self.prep_for(school, grade, sid,
                                    (q.get("tier") or [""])[0])
                # 解き終わった教科には、苦手と やり直す所を添える。
                # **数字だけ返しても、次の行動にならない。**
                if got and sid:
                    self.add_weak(school, sid, grade, got)
                # 紙に載る数を添える。
                # **アプリの数と紙の数は違う。** 紙に載せられるのは
                # 選択肢のある問題だけで、解答らんのマス（60）が上限。
                # 画面に「120もん」とだけ出して、刷ったら36問だったので、
                # どちらが本当なのか分からなくなっていた。両方書く。
                # ★ 数えるのは、並びを置き換える**前**。
                #   「いま刷ったら何問になるか」を出したいので、
                #   前に刷った紙のぶんを足したあとで数えてはいけない。
                for st in (got or {}).get("sets") or []:
                    st["paperN"] = len(prepsheet.paper_items([st]))
                paper = ({} if not (got and full) else {
                    x["subject"]: [i["id"] for i in prepsheet.paper_items([x])]
                    for x in got["sets"]})
                # **刷った紙が先。** 生徒が自分の紙を撮るときだけ効かせる。
                if paper and acc["role"] == "student":
                    paper = apply_sheet_memo(school, acc["sid"], grade,
                                             got, paper)
                return self.reply(200, {
                    "prep": got if full else examprep.light(got),
                    # 解答らんの寸法。**刷る側と読む側で同じ数字を使う。**
                    # 画面はこれを見てマスの位置を出す（式を2か所に書かない）。
                    "sheet": prepsheet.sheet_geometry(),
                    # 紙に刷った問題の並び。**カメラの採点はこれを見る。**
                    # 画面側でもう一度絞ると、絞り方がずれた日に総崩れになる。
                    "paper": paper})

            # 毎日テスト。今週のたしかめ と にがてつぶし の2本。
            if method == "GET" and len(parts) == 2 and parts[1] == "daily":
                if acc["role"] == "student":
                    cid = acc.get("classId") or ""
                    subs = sorted(SUBJECT_CODE)
                    sid = acc["sid"]
                else:
                    q = urllib.parse.parse_qs(
                        urllib.parse.urlparse(self.path).query)
                    cid = (q.get("classId") or [""])[0][:24]
                    subs = [(q.get("subject") or [""])[0][:24]]
                    sid = None
                    if not can_see(acc, cid, subs[0]):
                        return self.reply(403, {"error": "担当外です"})
                out = []
                for sub in subs:
                    if not sub:
                        continue
                    got = daily_sets(school, cid, sub, sid)
                    if got:
                        out.append({"subject": sub, "sets": got})
                return self.reply(200, {"daily": out})

            # ここから先は講師だけ。生徒は自分宛の宿題を書き換えられない。
            if not teacher:
                return self.reply(403, {"error": "forbidden"})

            # 確認テストの案。**押すまで何も出さない。**
            if method == "GET" and len(parts) == 2 and parts[1] == "suggest":
                return self.reply(200, {
                    "suggestions": suggestions_for(acc, school)})

            # 案をそのまま宿題にする。
            if method == "POST" and len(parts) == 2 and parts[1] == "suggest":
                d = self.body_json() or {}
                cid = str(d.get("classId", ""))[:24]
                sub = str(d.get("subject", ""))[:24]
                if not can_see(acc, cid, sub):
                    return self.reply(403, {"error": "担当外です"})
                got = [x for x in suggestions_for(acc, school, limit=20)
                       if x["classId"] == cid and x["subject"] == sub]
                if not got:
                    return self.reply(400, {"error": "その案はもうありません"})
                items = [i["id"] for i in got[0]["items"]]
                try:
                    due = int(d.get("dueAt"))
                except (TypeError, ValueError):
                    due = int((time.time() + 7 * 86400) * 1000)
                rec = valid_assignment(school, {
                    "title": "たしかめテスト %d問" % len(items),
                    "source": "weak", "items": items,
                    "classId": cid, "students": [], "dueAt": due,
                    "note": "クラスの半分以上がまちがえたところを集めました。",
                    "subject": sub,
                    "lesson": {"key": (class_table(school).get(cid) or {})
                               .get("grade", "") + ":" + sub},
                })
                rec["route"] = "app"
                rec["pick"] = "suggest"
                rec["id"] = "a" + secrets.token_hex(4)
                rec["createdBy"] = acc["sid"]
                rec["assignedAt"] = int(time.time() * 1000)
                with LOCK:
                    db = assignments(school)
                    db[rec["id"]] = rec
                    save_assignments(school, db)
                audit(school, acc["sid"], "suggest_assign", rec["id"],
                      "%s %s %d問" % (cid, sub, len(items)))
                return self.reply(200, {"assignment": rec})

            # **苦手なところだけを集めて宿題にする。**
            #
            #     POST /api/assignments/auto
            #     {classId, subject, count, dueAt}
            #
            # 何を出すかを講師に考えさせない。クラスの生徒が実際に
            # つまずいた番号を数え、多い順に count 件を出す。
            if method == "POST" and len(parts) == 2 and parts[1] == "auto":
                d = self.body_json() or {}
                cid = str(d.get("classId", ""))[:24]
                sub = str(d.get("subject", ""))[:24]
                try:
                    count = int(d.get("count") or 10)
                except (TypeError, ValueError):
                    count = 10
                count = max(1, min(60, count))
                if not can_see(acc, cid, sub):
                    return self.reply(403, {"error": "担当外です"})
                items = weak_items(school, cid, sub, count)
                if not items:
                    return self.reply(400, {
                        "error": "まだ、つまずきの記録がありません"})
                try:
                    due = int(d.get("dueAt"))
                except (TypeError, ValueError):
                    due = int((time.time() + 7 * 86400) * 1000)
                rec = valid_assignment(school, {
                    "title": "にがてな%d問" % len(items),
                    # 教材はひとつに決まらない ―― 項目そのものを指す。
                    "source": "weak", "items": items,
                    "classId": cid, "students": [], "dueAt": due,
                    "note": "みんながつまずいたところを集めました。",
                    "subject": sub,
                    "lesson": {"key": (class_table(school).get(cid) or {})
                               .get("grade", "") + ":" + sub},
                })
                # 項目を直接指す宿題は、必ずアプリで解ける。
                rec["route"] = "app"
                rec["pick"] = "weak"
                rec["id"] = "a" + secrets.token_hex(4)
                rec["createdBy"] = acc["sid"]
                rec["assignedAt"] = int(time.time() * 1000)
                with LOCK:
                    db = assignments(school)
                    db[rec["id"]] = rec
                    save_assignments(school, db)
                audit(school, acc["sid"], "auto_assign", rec["id"],
                      "%s %s %d問" % (cid, sub, len(items)))
                return self.reply(200, {"assignment": rec})

            if method == "POST" and len(parts) == 1:
                d = self.body_json() or {}
                try:
                    rec = valid_assignment(school, d)
                except ValueError as e:
                    return self.reply(400, {"error": str(e)})
                if allowed is not None and rec["classId"] not in allowed:
                    return self.reply(403, {"error": "担当外のクラスです"})
                rec["id"] = "a" + secrets.token_hex(4)
                rec["createdBy"] = acc["sid"]
                rec["assignedAt"] = int(time.time() * 1000)
                with LOCK:
                    db = assignments(school)
                    db[rec["id"]] = rec
                    save_assignments(school, db)
                audit(school, acc["sid"], "create_assignment", rec["id"], rec["title"])
                return self.reply(200, {"assignment": rec})

            if len(parts) == 2:
                aid = parts[1]
                with LOCK:
                    db = assignments(school)
                    cur = db.get(aid)
                    if not cur:
                        return self.reply(404, {"error": "no-assignment"})
                    # **教科まで見る。** クラスだけで判定すると、
                    # 同じクラスの別教科の宿題を消せてしまう。
                    # 中2Rの数学の先生が、中2Rの英語の宿題を
                    # 取り消せる状態になっていた。
                    if not may_touch(school, acc, cur,
                                     subject_of_assignment(cur) or None):
                        return self.reply(403, {"error": "担当外の宿題です"})
                    if method == "PUT":
                        d = self.body_json() or {}
                        try:
                            rec = valid_assignment(school, d, cur,
                                                   paper_ok=(cur.get("createdBy") == "plan"))
                        except ValueError as e:
                            return self.reply(400, {"error": str(e)})
                        db[aid] = rec
                        save_assignments(school, db)
                        audit(school, acc["sid"], "update_assignment", aid)
                        return self.reply(200, {"assignment": rec})
                    if method == "DELETE":
                        # 出した生徒（写真）や評価のある箱・宿題は消さない ―― 写真と評価が宙に浮く（2026-10-12、提出箱を消す口を講師の画面に付けたとき）
                        if SUB.load(school).get(aid) or ratings(school).get(aid):
                            return self.reply(409, {"error": "出した生徒がいるので消せません"})
                        db.pop(aid, None)
                        save_assignments(school, db)
                        audit(school, acc["sid"], "delete_assignment", aid)
                        # 生徒側の達成記録はあえて消さない。取り消しても
                        # 「やった事実」は残す ―― 誤操作で努力を消さないため。
                        return self.reply(200, {"ok": True})
            return self.reply(404, {"error": "not-found"})

        # --- 講師: 担当クラスの全員（要約だけ）---
        #
        # 以前はここで生徒全員の進捗ブロブを丸ごと返していた。
        # 250名で23MB になり、実際には開かない画面になっていた（SPEC.md）。
        # いまは要約の該当分だけを返す。2,000名でも1人200バイト。
        # 1人分の中身が要るときは /api/p/<sid> を個別に取りに行く。
        if method == "GET" and parts and parts[0] == "class":
            if acc["role"] != "teacher":
                return self.reply(403, {"error": "forbidden"})
            allowed = teacher_classes(acc)
            audit(school, acc["sid"], "read_class",
                  ",".join(allowed) if allowed is not None else "*")
            sums = summary(school)
            out = []
            for login_id, a in sorted(accounts(school).items()):
                if a["role"] != "student":
                    continue
                if a.get("leftAt"):
                    continue          # 在籍終了。名簿には出さない
                if allowed is not None and a["classId"] not in allowed:
                    continue
                # **1人ぶんの行に、全員で同じものを入れない。**
                # 校舎名・役割・担当クラスは30人ぶん同じ文字を送ることになり、
                # 300名では 27KB がその繰り返しで埋まる。
                # 共通のものは返事の外側に1回だけ置く。
                row = {"profile": {"sid": a["sid"], "seat": seat_of(a),
                                   "level": a["level"], "classId": a["classId"]}}
                # 要約は派生データなので、作りを変えたあとは古い形が残る。
                # 既定の形に重ねてから返す ―― 欠けた鍵を外に出さない。
                # （実際、rated を足した直後に古い行が素通りして
                #   クライアントで KeyError になった）
                base = summarise_one({}, [])
                base.update(sums.get(a["sid"]) or {})
                row.update(base)
                out.append(row)
            return self.reply(200, {"students": out, "summary": True,
                                    # 全員に共通のもの。行には入れない。
                                    "school": school,
                                    "schoolName": school_name(school),
                                    "role": "student"})

        return self.reply(404, {"error": "not-found"})


    def teacher_desk(self, school, acc, method, parts):
        """講師の机（今日やること・宿題チェック・成績の診断・生徒ごとの宿題・塾内テスト）。

        **自分のコースだけ。** 生徒を指すものは、そのコースの生徒かを必ず確かめる。"""
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

        def arg(k, n=48):
            return (q.get(k) or [""])[0][:n]

        mine = desk_courses(school, acc)
        head = parts[0]
        sub = parts[1] if len(parts) > 1 else ""
        # 授業日の過ぎた回を、読む前に出しておく（格子と同じ鍵）。
        #
        # 出すのが格子・控えを開いたときだけだと、成績や今日やることから
        # 入った日は、出していない過ぎた回が「次の授業 10/5」のまま残った
        # （2026-10-07、本番デモ。今日は 10/7）。
        if method == "GET" and head in ("today", "check", "insight"):
            self.auto_publish(school, acc)
        try:
            if head == "today" and method == "GET" and len(parts) == 1:
                return self.reply(200, desk_today(school, acc, mine))

            if head == "quiz" and method == "GET" and sub == "who" and len(parts) == 2:
                # 提出箱を「選んだ生徒だけ」に出すための、このコースの生徒の一覧（sid と席の呼び名）
                key = arg("key")
                if key not in mine:
                    return self.reply(403, {"error": "担当外のコースです"})
                labels = desk_labels(school)
                who = courses.receivers(school, mine[key])
                return self.reply(200, {"students": [{"sid": s, "label": labels.get(s, s)}
                                                     for s in sorted(who, key=lambda s: labels.get(s, s))]})

            if head == "quiz" and method == "POST" and len(parts) == 1:
                d = self.body_json() or {}
                key = str(d.get("key") or "")[:48]
                if key not in mine:
                    return self.reply(403, {"error": "担当外のコースです"})
                picked = d.get("students")
                if picked is not None:
                    if not isinstance(picked, list) or len(picked) > 500 or not all(isinstance(x, str) and len(x) <= 40 for x in picked):
                        return self.reply(400, {"error": "生徒の選び方がおかしいです"})
                try:
                    due = int(d.get("dueAt") or 0) or int((time.time() + 7 * 86400) * 1000)
                    rec = make_quiz(school, key, mine[key], d.get("title"), due, acc["sid"],
                                    kind=d.get("kind"), students=picked)
                except (TypeError, ValueError) as e:
                    return self.reply(400, {"error": str(e)})
                hw_cache_clear() if "hw_cache_clear" in globals() else None
                audit(school, acc["sid"], "create_quiz", rec["id"], rec["title"])
                return self.reply(200, {"assignment": rec})

            if head == "check":
                if method == "GET" and len(parts) == 1:
                    key = arg("key")
                    if key not in mine:
                        return self.reply(403, {"error": "担当外のコースです"})
                    n = arg("n", 6)
                    return self.reply(200, desk_check(school, acc, mine, key,
                                                      int(n) if n.isdigit() else None))
                if method == "PUT" and sub == "rate" and len(parts) == 2:
                    d = self.body_json() or {}
                    return self.reply(200, desk_rate(school, acc, mine, d))

            if head == "insight":
                if method == "GET" and sub == "overview":
                    return self.reply(200, desk_overview(school, acc, mine))
                if method == "POST" and sub == "feedback":
                    d = self.body_json() or {}
                    key = str(d.get("key") or "")[:48]
                    if key not in mine:
                        return self.reply(403, {"error": "担当外のコースです"})
                    act = str(d.get("action") or "")
                    kind = str(d.get("kind") or "")
                    if act not in ("accept", "dismiss") or kind not in INSIGHT.KIND_WORD:
                        return self.reply(400, {"error": "形式が違います"})
                    try:
                        n = int(d.get("n"))
                    except (TypeError, ValueError):
                        n = None
                    insight_note(school, {"by": acc["sid"], "key": key,
                                          "sid": str(d.get("sid") or "")[:40], "n": n,
                                          "kind": kind, "action": act, "at": int(time.time())})
                    return self.reply(200, {"ok": True})
                key = arg("key")
                if key not in mine:
                    return self.reply(403, {"error": "担当外のコースです"})
                if method == "GET" and sub == "course":
                    return self.reply(200, desk_course(school, acc, mine, key))
                if method == "GET" and sub == "student":
                    audit(school, acc["sid"], "read_insight", key, arg("sid", 40))
                    return self.reply(200, desk_student(school, acc, mine, key, arg("sid", 40)))
                if method == "GET" and sub == "suggest":
                    n = arg("n", 6)
                    if not n.isdigit():
                        return self.reply(400, {"error": "単元が分かりません"})
                    return self.reply(200, desk_suggest(school, acc, mine, key, arg("sid", 40), int(n)))

            if head == "presets" and len(parts) == 1:
                if method == "GET":
                    key = arg("key")
                    if key not in mine:
                        return self.reply(403, {"error": "担当外のコースです"})
                    return self.reply(200, {"presets": PRESETS.list_of(school, key)})
                if method == "POST":
                    d = self.body_json() or {}
                    key = str(d.get("key") or "")[:48]
                    if key not in mine:
                        return self.reply(403, {"error": "担当外のコースです"})
                    pr = PRESETS.put(school, key, d.get("preset") or {}, acc["sid"])
                    audit(school, acc["sid"], "preset_put", key, pr["id"])
                    return self.reply(200, {"preset": pr, "presets": PRESETS.list_of(school, key)})
                if method == "DELETE":
                    key, pid = arg("key"), arg("id", 12)
                    if key not in mine:
                        return self.reply(403, {"error": "担当外のコースです"})
                    if not PRESETS.remove(school, key, pid):
                        return self.reply(404, {"error": "そのプリセットはありません"})
                    audit(school, acc["sid"], "preset_del", key, pid)
                    return self.reply(200, {"presets": PRESETS.list_of(school, key)})

            if head == "personal" and sub == "board" and method == "GET" and len(parts) == 2:
                key = arg("key")
                if key not in mine:
                    return self.reply(403, {"error": "担当外のコースです"})
                return self.reply(200, {"students": desk_board(school, key, mine[key])})

            if head == "personal" and sub == "bulk" and method == "POST" and len(parts) == 2:
                # 選んだ生徒にまとめて出す。1人ずつの往復にしない（40人で40回は遅い）。
                d = self.body_json() or {}
                key = str(d.get("key") or "")[:48]
                if key not in mine:
                    return self.reply(403, {"error": "担当外のコースです"})
                p = mine[key]
                roster = {r["sid"] for r in desk_roster(school, p, course_asgs(assignments(school), key), {})}
                nn = next_n_of(p)
                pr = d.get("preset") or {}
                preset = PRESETS.find(school, key, str(pr.get("id") or "")[:12]) if pr.get("id") else None
                if pr.get("id") and not preset:
                    return self.reply(404, {"error": "そのプリセットはありません"})
                until = "once" if pr.get("until") == "once" else None
                units = d.get("units") if isinstance(d.get("units"), dict) else {}
                msg = str(d.get("msg") or "")[:PERSONAL.MSG_MAX]                  # 生徒へのひとこと（全員に同じ文）
                done, failed = [], []
                for sid in list(d.get("sids") or [])[:80]:
                    sid = str(sid)[:40]
                    if sid not in roster:
                        failed.append({"sid": sid, "error": "このコースの生徒ではありません"})
                        continue
                    try:
                        rd = (PRESETS.rule_of(preset, until, nn, str(units.get(sid) or ""))
                              if preset else dict(d.get("rule") or {}))
                        if msg:
                            rd["msg"] = msg
                        rule = PERSONAL.put_rule(school, key, sid, rd, acc["sid"], nn)
                        audit(school, acc["sid"], "personal_rule", "%s|%s" % (key, sid),
                              "%s %s" % (rule["id"], rule["kind"]))
                        done.append(sid)
                    except ValueError as e:
                        failed.append({"sid": sid, "error": str(e)})
                return self.reply(200, {"done": done, "failed": failed,
                                        "board": desk_board(school, key, p)})

            if head == "personal":
                if method == "GET" and len(parts) == 1:
                    key, sid = arg("key"), arg("sid", 40)
                    if key not in mine:
                        return self.reply(403, {"error": "担当外のコースです"})
                    p = mine[key]
                    roster = desk_roster(school, p, course_asgs(assignments(school), key), {})
                    if sid not in {r["sid"] for r in roster}:
                        return self.reply(403, {"error": "このコースの生徒ではありません"})
                    return self.reply(200, {"rules": desk_rules(school, key, p, sid),
                                            "next": preview_for(school, key, p, sid)})
                if method in ("POST", "DELETE") and len(parts) == 1:
                    d = (self.body_json() or {}) if method == "POST" else {}
                    key = str(d.get("key") or arg("key"))[:48]
                    sid = str(d.get("sid") or arg("sid", 40))[:40]
                    if key not in mine:
                        return self.reply(403, {"error": "担当外のコースです"})
                    p = mine[key]
                    roster = desk_roster(school, p, course_asgs(assignments(school), key), {})
                    if sid not in {r["sid"] for r in roster}:
                        return self.reply(403, {"error": "このコースの生徒ではありません"})
                    nn = next_n_of(p)
                    if method == "POST":
                        rd = d.get("rule") or {}
                        pr = d.get("preset") or {}
                        if pr.get("id"):
                            # プリセットから出す。決まりの形はサーバが作る（画面で組まない）。
                            preset = PRESETS.find(school, key, str(pr["id"])[:12])
                            if not preset:
                                return self.reply(404, {"error": "そのプリセットはありません"})
                            rd = PRESETS.rule_of(preset, "once" if pr.get("until") == "once" else None,
                                                 nn, str(pr.get("unit") or ""))
                        if d.get("msg"):
                            rd["msg"] = str(d.get("msg"))[:PERSONAL.MSG_MAX]      # 生徒へのひとこと
                        rule = PERSONAL.put_rule(school, key, sid, rd, acc["sid"], nn)
                        audit(school, acc["sid"], "personal_rule", "%s|%s" % (key, sid), "%s %s" % (rule["id"], rule["kind"]))
                        if (rule.get("origin") or {}).get("kind") in INSIGHT.KIND_WORD:
                            insight_note(school, {"by": acc["sid"], "key": key, "sid": sid,
                                                  "n": rule["origin"].get("n"),
                                                  "kind": rule["origin"]["kind"], "action": "accept",
                                                  "at": int(time.time())})
                    else:
                        rid = arg("id", 16)
                        if not PERSONAL.stop_rule(school, key, sid, rid, nn):
                            return self.reply(404, {"error": "その決まりはありません"})
                        audit(school, acc["sid"], "personal_stop", "%s|%s" % (key, sid), rid)
                        rule = None
                    return self.reply(200, {"rule": rule, "rules": desk_rules(school, key, p, sid),
                                            "next": preview_for(school, key, p, sid)})

            if head == "scores":
                if method == "GET" and len(parts) == 1:
                    key = arg("key")
                    if key not in mine:
                        return self.reply(403, {"error": "担当外のコースです"})
                    return self.reply(200, {"tests": [score_summary(t) for t in SCORES.tests_of(school, key)]})
                if method == "POST" and len(parts) <= 2 and sub in ("", "preview"):
                    d = self.body_json() or {}
                    key = str(d.get("key") or "")[:48]
                    if key not in mine:
                        return self.reply(403, {"error": "担当外のコースです"})
                    text = str(d.get("text") or "")
                    if len(text) > 400000:
                        return self.reply(400, {"error": "表が大きすぎます"})
                    p = mine[key]
                    parsed = SCORES.parse(text)
                    date = str(d.get("date") or INSIGHT.today_of())[:10]
                    roster = score_roster(school, key, p, date)
                    got, miss = SCORES.match_seats(parsed, roster)
                    if sub == "preview":
                        mapping = SCORES.auto_map(parsed, p.get("lessons") or [], date)
                        return self.reply(200, {
                            "kind": parsed["kind"], "errors": parsed["errors"],
                            "warnings": parsed["warnings"],
                            "cols": [{"label": c["label"], "max": c["max"], "q": c.get("q") or 0,
                                      "lessons": mapping[i] if i < len(mapping) else []}
                                     for i, c in enumerate(parsed["cols"])],
                            "rows": len(parsed["rows"]), "matched": len(got), "unmatched": miss[:30],
                            "lessons": [{"n": l.get("n"), "topic": l.get("topic") or "",
                                         "label": l.get("label"), "date": l.get("date") or ""}
                                        for l in (p.get("lessons") or []) if l.get("date")]})
                    rec = SCORES.build(key, d.get("name"), date, parsed, got, d.get("mapping"),
                                       d.get("maxes"), acc["sid"])
                    tid = SCORES.put(school, rec)
                    audit(school, acc["sid"], "import_scores", tid,
                          "%s %s %d人" % (key, rec["name"], len(rec["rows"])))
                    return self.reply(200, {"id": tid, "test": score_summary(dict(rec, id=tid)),
                                            "unmatched": miss[:30]})
                if method == "DELETE" and len(parts) == 2:
                    tid = parts[1][:16]
                    t = (SCORES.load(school).get("tests") or {}).get(tid)
                    if not t:
                        return self.reply(404, {"error": "そのテストはありません"})
                    if t.get("key") not in mine:
                        return self.reply(403, {"error": "担当外のコースです"})
                    SCORES.remove(school, tid)
                    audit(school, acc["sid"], "remove_scores", tid, t.get("key") or "")
                    return self.reply(200, {"ok": True})
        except PermissionError as e:
            return self.reply(403, {"error": str(e)})
        except ValueError as e:
            return self.reply(400, {"error": str(e)})
        return self.reply(404, {"error": "not-found"})

    def add_weak(self, school, sid, grade, prep):
        """対策の結果から、教科ごとに「次にやること」を足す。

        足すのは3つ。
            score   その教科の対策テストの点（解いていなければ無し）
            weak    落とした単元（直せたものは fixed=1）
            review  やり直す所 ―― **授業計画の宿題の文をそのまま引く**

        「教科書のここからここ」を、こちらで作らない。講師が黒板に
        書いた言葉（トレーニング10-12 と 基本問題p.14-17）が残って
        いるので、それを引く。言い換えると別のものになる。
        """
        plans = lessons.load(school)
        for st in prep.get("sets") or []:
            sub = st.get("subject")
            sc = weak.score(school, sid, sub)
            if not sc:
                continue
            wk = weak.weak_units(school, sid, sub)
            st["score"] = sc
            st["weak"] = wk
            todo = [x["unit"] for x in wk if not x["fixed"]]
            plan = (plans.get("plans") or {}).get("%s:%s" % (grade, sub)) or {}
            st["review"] = weak.advice(plan, todo)
            st["retest"] = len(todo)

    def prep_for(self, school, grade, sid, tier=""):
        """総復習テスト対策を1人ぶん組む。

        生徒の記録・直近の出来・教材・学年ぜんぶの難しさを集めて渡す。
        sid が空なら（講師が見本を見るとき）記録なしで組む。
        """
        if not grade:
            return None
        # **講師が使っている教科だけ。** 前は5教科決め打ちだったので、
        # 英語の授業が無い小4にも英語の対策テストが出ていた。
        subs = enabled_subjects(school, grade) or sorted(examprep.CODE)
        cards, acc_rate = {}, None
        dept = SOURCE.dept_of(grade)
        if sid:
            # **受けている教科だけ。** 毎日テストと同じ決まり（S4）。
            # 国語・数学だけ取っている生徒に5教科ぶん（248分）を並べると、
            # やらなくてよい量まで背負わせることになる。受講科目が無い生徒は今までどおり。
            _, me = find_by_sid(school, sid)
            dept = SOURCE.dept_of((me or {}).get("level") or grade, (me or {}).get("classId"))
            taking = (me or {}).get("subjects") or []
            if taking:
                subs = [x for x in subs if x in taking] or subs
            rec = paths.load(progress_path(school, sid), None) or {}
            cards = ((rec.get("blob") or {}).get("cards") or {})
            sm = summary(school).get(sid) or {}
            ans = int(sm.get("answered") or 0)
            if ans:
                acc_rate = (int(sm.get("correct") or 0)) / float(ans)
        if tier in ("advanced", "basic"):
            # 講師が版を指定したときは、それに従う（見本づくり）。
            acc_rate = 1.0 if tier == "advanced" else 0.0

        db = list(accounts(school).values())
        cache = {}

        def progress_of(s2):
            if s2 not in cache:
                r = paths.load(progress_path(school, s2), None) or {}
                cache[s2] = ((r.get("blob") or {}).get("cards") or {})
            return cache[s2]

        return examprep.for_student(
            school, grade, subs, sid, cards, acc_rate,
            accounts=db, progress_of=progress_of,
            materials=materials(school), win=demo_exam_window(school, sid, grade), dept=dept)

    def grid_pairs(self, school, asg, nowms):
        """クラス × 教科 ごとの「前回の提出状況」と「手が要る件数」。

        学年ではなくクラスで数える。講師が担当しているのはクラスだから。
        返す形は {"e4b|math": {"late": 3, "last": {...}}, ...}。
        コースから出した宿題は classId にコースIDが入るので、{"j2tr|english": …}。

        「前回」は、**期限がすでに来たもののうち、いちばん新しいもの**。
        期限前のものを前回とみなすと、まだ誰も出していないのが当たり前
        なので、0% ばかりが並ぶ。

        **同じ回の宿題は1つに束ねて数える。** 1回から Sirius21 と Jack21 の
        2件が出ると、期限が同じなので、前は先に見た1件の数字だけが
        「前回」になっていた。束ねた率は、ブロックごとの率を人数で重ねたもの。
        """
        groups = {}
        blobs = hw_cache()               # 名簿と進捗は1回だけ読む（上と同じ理由）
        for a in asg:
            cid = a.get("classId")
            sub = subject_of_assignment(a)
            if not (cid and sub):
                continue
            # **「出すだけ」は提出率に数えない。**
            # 観測していないものを分母に入れると、ちゃんとやっている
            # クラスほど提出率が下がる。
            if a.get("graded") is False:
                continue
            k = "%s|%s" % (cid, sub)
            les = a.get("lesson") or {}
            g = (k, les.get("key"), les.get("n")) if les.get("key") else (k, a.get("id"), None)
            sm = hw_summary(school, a, blobs)
            n = sm.get("assigned") or 0
            got = (sm.get("rated") or 0) if (a.get("route") == "paper") \
                else (sm.get("completed") or 0)
            e = groups.setdefault(g, {"k": k, "id": a.get("id"), "dueAt": a.get("dueAt") or 0,
                                      "title": a.get("title", ""), "n": 0, "sn": 0, "sg": 0,
                                      "paper": a.get("route") == "paper", "classId": cid})
            e["n"] = max(e["n"], n)
            e["sn"] += n
            e["sg"] += min(got, n)
            e["dueAt"] = max(e["dueAt"], a.get("dueAt") or 0)
        out = {}
        for e in groups.values():
            rec = out.setdefault(e["k"], {"late": 0, "last": None})
            pct = (e["sg"] * 1.0 / e["sn"]) if e["sn"] else 0
            due = e["dueAt"]
            if due <= nowms and e["sg"] < e["sn"]:
                rec["late"] += 1
            if due > nowms:
                continue
            cur = rec["last"]
            if cur and (cur.get("dueAt") or 0) >= due:
                continue
            rec["last"] = {
                "id": e["id"], "dueAt": due, "title": e["title"],
                "n": e["n"], "done": int(round(pct * e["n"])),
                "pct": int(round(pct * 100)),
                "paper": e["paper"], "classId": e["classId"],
            }
        return out

    def auto_publish(self, school, acc):
        """授業日が過ぎた回の宿題を出す。コースと、旧来の計画の両方。

        2つが同時に走ると同じ回を二度出すので、1本の鍵でくくる。
        """
        with PUBLISH_LOCK:
            made = publish_courses(school, acc.get("sid") or "system")
            made += self.auto_publish_legacy(school, acc)
        return made

    def auto_publish_legacy(self, school, acc):
        """旧来の「学年:教科」の計画について、授業日が過ぎた回の宿題を出す。

        **凍結している。** 新しい処理はコース（publish_courses）に書く。
        デモを作り直して旧計画が無くなったら、この関数ごと消す。

        **講師の操作を待たない。** これが「毎週の作業ゼロ」の実体である。
        講師が格子の画面を開いた時点で、出すべきものは出ている。

        実施していない授業の分まで出てしまう場合は、講師が shift で下げる。
        「出しすぎ」は取り消せるが、「出し忘れ」は取り返せない ――
        だから出す側に倒す。
        """
        made = []
        try:
            todo = lessons.due_to_publish(school)
        except (IOError, BadPath):
            return made
        grades = teacher_grades(acc)
        for x in todo:
            key, p, l = x["key"], x["plan"], x["lesson"]
            grade = key.split(":")[0]
            if grades is not None and grade not in grades:
                continue
            hw = l.get("hw") or {}
            title = lessons.hw_text(hw) or l.get("topic") or "宿題"
            # 教材と番号を文から読む。講師に選ばせない（手間を増やさない）。
            src = hw.get("source", "")
            lo, hi = int(hw.get("from") or 0), int(hw.get("to") or 0)
            if not (src and lo and hi):
                gsrc, glo, ghi = source_and_range(school, title)
                src = src or gsrc
                if not (lo and hi):
                    lo, hi = glo, ghi
            # 期限は授業日から dueDays 日後の 23:59
            try:
                t = time.mktime(time.strptime(l["date"], "%Y-%m-%d"))
            except (KeyError, ValueError):
                continue
            due = int((t + int(p.get("dueDays", 7)) * 86400 + 86399) * 1000)
            # **担当されているクラス全部に出す。**
            # 計画は学年でひとつだが、宿題と提出状況はクラスごと。
            targets = taught_classes(school, grade, key.split(":")[1],
                                     p.get("classId", ""))
            if not targets:
                continue
            first = None
            for cid in targets:
                rec = {
                    "id": "a" + secrets.token_hex(4),
                    "title": title[:80],
                    "source": src,
                    "from": lo, "to": hi,
                    "classId": cid,
                    "students": [],
                    "dueAt": due,
                    "note": lessons.unit_note(l),
                    "kind": "hw",
                    # 教材か番号のどちらかが読めないものは、アプリで解けない。
                    # 紙と同じ扱いにする ―― 解けないものに「やる」ボタンを
                    # 出すと、押した先が「NO.0 の 0ばん」になる（実際になった）。
                    "route": (route_of(school, src) if (src and lo and hi)
                              else "paper"),
                    "graded": graded_of(school, src),
                    "lesson": {"key": key, "n": l.get("n")},
                    "createdBy": "plan",
                    "assignedAt": int(time.time() * 1000),
                }
                with LOCK:
                    db = assignments(school)
                    db[rec["id"]] = rec
                    save_assignments(school, db)
                first = first or rec
                audit(school, acc["sid"], "auto_publish", rec["id"], title[:40])
            lessons.mark_published(school, key, l.get("n"), first["id"])
            made.append({"key": key, "n": l.get("n"), "title": first["title"],
                         "id": first["id"]})
        return made

    def may_read(self, acc, sid):
        if acc["role"] != "teacher":
            return False
        # 自分の校舎の中からしか探さない。他校舎の sid は「居ない」と同じ。
        _, target = find_by_sid(acc["school"], sid)
        if not target:
            return False
        # そのクラスに担当が1つでもあれば、生徒の記録は読める。
        # 教科ごとに切ると、担任でなくても見るべき「気になる子」の
        # 判断ができなくなる。読めるのはクラス単位、書けるのは無し。
        if can_see(acc, target.get("classId")):
            return True
        # 指名のコース（土特・必勝など）の生徒は、在籍クラスが別でも読める。
        return target.get("sid") in courses.named_of(acc["school"], acc["sid"])


# ------------------------------------------------------------------
# コマンド
# ------------------------------------------------------------------
# 出席番号だけ。氏名は最初から作らない。
# クラスは「学年 × コース × 習熟度」。app/curriculum.js と同じ並びにする。
# 人数は実際の教室に近づける。
# 3名だと提出率が 0 / 33 / 67 / 100% しか出ず、円グラフが嘘くさい。
# 合同クラスは多め、習熟度別は少なめにしてある。
SEED_CLASSES = [
    ("e4a", "e4", "小4α", 12), ("e4b", "e4", "小4β", 10),
    ("e5",  "e5", "小5",  18),
    # 小6の中受組は、教科によって合同（小6）と上位（小6α）に分かれる。
    ("e6",  "e6", "小6",   8), ("e6a", "e6", "小6α", 14),
    ("e6b", "e6", "小6β", 11),
    ("j1",  "j1", "中1",  20), ("j1r", "j1", "中1R", 12),
    ("j2",  "j2", "中2",  19), ("j2r", "j2", "中2R", 13),
    # 高校受験組の上位は、中3ではTと呼ぶ（中1・中2はR）。
    ("j3",  "j3", "中3",  22), ("j3t", "j3", "中3T",  9),
]

# 講師8人。それぞれ担当クラスだけが見える。
# '*'（全クラス）を配らないのは、合言葉が1つ漏れたときの被害範囲を
# 担当分に閉じ込めるため。教室長だけ全体を見たい場合は
#   python3 tube_server.py add kyomu T0 --teacher --classes '*'
# 担当は「クラス:教科」の組で持つ。**学年をまるごと持つ講師はいない。**
# 実際の受け持ちは学年も教科もまたぐ。たとえば1人の講師が
#   小4β 算数 ／ 小5 理科 ／ 小6α 算数 ／ 中1 理科 ／
#   中1R 数学 ／ 中2R 数学 ／ 中2R 英語
# のように持つ。ここではその形をそのまま入れる。
# 形は [クラス, 教科, 曜日, 時限]。曜日は 1=月 … 6=土。
# 時限は「その日の何コマ目か」。時刻は持たない ―― 校舎ごとに違ううえ、
# 画面に要るのは順番だけである。
SEED_TEACHERS = [
    ("teacher1", [["j1r", "math",     1, 1], ["j2r", "math",    1, 2],
                  ["e4b", "math",     2, 1], ["e5",  "japanese", 2, 2],
                  ["e5",  "science",  3, 1], ["j2r", "english",  3, 2],
                  ["j1",  "science",  4, 1], ["j3t", "japanese", 4, 2],
                  ["j3t", "math",     5, 1], ["e6",  "science",  5, 2],
                  ["e6a", "math",     6, 1], ["e6a", "japanese", 6, 2]]),
    ("teacher2", [["e4a", "math", 1, 1], ["e6b", "math", 2, 1],
                  ["j2", "math", 4, 1], ["j3", "math", 6, 1]]),
    ("teacher3", [["j1", "english", 1, 1], ["j1r", "english", 2, 1],
                  ["j2", "english", 3, 1], ["j3", "english", 4, 1],
                  ["j3t", "english", 6, 1]]),
    ("teacher4", [["j2", "science", 1, 1], ["j2", "social", 1, 2],
                  ["j2r", "science", 3, 1], ["j2r", "social", 3, 2],
                  ["j3", "science", 6, 1]]),
    ("teacher5", [["e4a", "japanese", 1, 1], ["e4b", "japanese", 2, 1],
                  ["e5", "japanese", 3, 1], ["e6a", "japanese", 4, 1],
                  ["e6b", "japanese", 6, 1]]),
    # いちばん多い人。14コマでも読めるかを、この人で確かめる。
    ("teacher6", [["j1", "japanese", 1, 1], ["j1r", "japanese", 1, 2],
                  ["j2", "japanese", 2, 1], ["j2r", "japanese", 2, 2],
                  ["j3", "japanese", 3, 1], ["j3t", "japanese", 3, 2],
                  ["e4a", "japanese", 4, 1], ["e4b", "japanese", 4, 2],
                  ["e5", "japanese", 5, 1], ["e6a", "japanese", 5, 2],
                  ["e6b", "japanese", 6, 1], ["j1", "social", 6, 2],
                  ["j2", "social", 2, 3], ["j3", "social", 4, 3]]),
    ("teacher7", [["e4a", "science", 1, 1], ["e4b", "science", 2, 1],
                  ["e6a", "science", 3, 1], ["e6b", "science", 4, 1],
                  ["e5", "social", 6, 1], ["e6a", "social", 6, 2]]),
    ("teacher8", [["j3", "social", 1, 1], ["j3t", "social", 2, 1],
                  ["j1", "social", 3, 1], ["j1r", "social", 4, 1],
                  ["j3t", "math", 6, 1]]),
]


def cmd_seed(args):
    school = args.school
    if args.reset and os.path.isdir(paths.school_dir(school)):
        # **本物の校舎（管理者がいて、デモの目印が無い）は、ここでは消さない。**
        # 1行のまちがいで、配った席と記録が全部消える。どうしても消すときは、フォルダを手で動かす。
        try:
            real = school_managed(school) and not is_demo_school(school)
        except (BadPath, IOError, OSError, ValueError):
            real = False
        if real:
            print("× 校舎 %s は本物です（管理者がいます）。seed --reset では消しません。" % school)
            return 1
        import shutil
        shutil.rmtree(paths.school_dir(school))
        for lid, sc in list(paths.read_index().items()):
            if sc == school:
                paths.unbind_login(lid)
        print("校舎 %s のデータを消しました\n" % school)
    ensure_dirs(school)
    if not os.path.isfile(paths.school_file(school, "school.json")):
        paths.save(paths.school_file(school, "school.json"),
                   {"id": school, "name": args.name or school,
                    "code": school[:1], "tz": "Europe/London"})
    if getattr(args, "empty", False):
        # 空の校舎だけ作る。アカウントはデモの作成（demo_running.py）が
        # 実データ（Claude outputs/SEED-ロンドン校.md）から作る。
        print("校舎 %s を空で用意しました（アカウントは作っていません）" % school)
        return
    code = school_code(school)
    made = []
    for class_id, level, class_name, count in SEED_CLASSES:
        for i in range(1, count + 1):
            login_id = "%s%s%02d" % (code, class_id, i)
            if login_id in accounts(school):
                continue
            pw = make_password()
            seat = "%02d" % i
            add_account(school, login_id, pw, seat, "student", level, class_id)
            made.append((login_id, pw, "%s-%s" % (class_name.replace(" ", ""), seat)))
    for i, (tid0, pairs) in enumerate(SEED_TEACHERS, 1):
        tid = code + tid0
        if tid in accounts(school):
            continue
        pw = make_password()
        klasses = []
        # 1行は [クラス, 教科, 曜日, 時限]。曜日と時限は無いこともあるので、
        # 決め打ちで2つに展開しない。
        for row in pairs:
            cid = row[0]
            if cid not in klasses:
                klasses.append(cid)
        add_account(school, tid, pw, "T%d" % i, "teacher",
                    "j2", klasses[0], classes=klasses)
        # 担当は「クラス:教科」で持つ。classes は名簿を引くための索引。
        with LOCK:
            db = accounts(school)
            db[tid]["assign"] = [list(x) for x in pairs]
            save_accounts(school, db)
        made.append((tid, pw, "講師%d（%d件の担当）" % (i, len(pairs))))

    if not made:
        print("すでにアカウントがあります。作り直すなら --reset を付けてください。")
        return
    print("テスト用アカウントを作りました。\n")
    print("  %-9s %-14s %s" % ("ID", "パスワード", "画面での表示"))
    print("  " + "-" * 46)
    for row in made:
        print("  %-9s %-14s %s" % row)
    print("\n  パスワードはいま一度だけ表示されます（保存されているのはハッシュのみ）。")
    print("  忘れたときは  python3 tube_server.py passwd <ID>")
    print("\n  氏名は保存していません。誰がどのIDかは、先生の手元の名簿で管理してください。")


# 曜日の書き方。画面にも CLI にも、この呼び方で通す。
DAY_NAMES = {"月": 1, "火": 2, "水": 3, "木": 4, "金": 5, "土": 6, "日": 7,
             "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 7}
DAY_LABEL = {1: "月", 2: "火", 3: "水", 4: "木", 5: "金", 6: "土", 7: "日"}


def parse_assign(text):
    """「e4b:math,e5:science」を [(クラス, 教科), …] にする。

    講師は学年をまるごとではなく、**あるクラスのある1教科**を持つ。
    ここを取り違えると、担当外の生徒の記録が見えてしまう。
    知らない教科は弾く ―― 打ち間違いを黙って通すと、
    権限が無いのに通ってしまう組み合わせが生まれる。
    """
    known = set(subject_ids())
    out = []
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError("「クラス:教科」の形で書いてください: %r" % part[:24])
        bits = part.split(":")
        cid = bits[0].strip()
        sub = bits[1].strip() if len(bits) > 1 else ""
        if not cid or sub not in known:
            raise ValueError("知らない教科です: %r（使えるのは %s）"
                             % (sub[:16], "・".join(sorted(known))))
        # 3つめ以降は曜日と時限。「j2r:math:月:2」のように書ける。
        day = DAY_NAMES.get(bits[2].strip(), 0) if len(bits) > 2 else 0
        try:
            period = int(bits[3]) if len(bits) > 3 else 0
        except ValueError:
            period = 0
        row = [cid, sub, day, period or (len(out) + 1)]
        if row[:2] not in [r[:2] for r in out]:
            out.append(row)
    return out


def cmd_add(args):
    pw = args.password or make_password()
    klasses = []
    assign = []
    if args.teacher:
        if args.assign:
            try:
                assign = parse_assign(args.assign)
            except ValueError as e:
                print(e)
                return 1
            klasses = []
            # 1行は [クラス, 教科, 曜日, 時限]。長さは揃わないので、
            # 決め打ちで2つに展開しない（ここで2度つまずいた）。
            for row in assign:
                if row[0] not in klasses:
                    klasses.append(row[0])
        else:
            klasses = [x.strip() for x in (args.classes or "").split(",") if x.strip()]
        if not klasses:
            print("講師には担当が要ります。どちらかを指定してください:")
            print("  --assign e4b:math,e5:science,j2r:english   （推奨。教科まで決める）")
            print("  --classes j1a,j2a                          （そのクラスの全教科）")
            print("  --classes '*'                              （全部を見る。教室長など）")
            print("  --classes -                                （コースだけを受け持つ）")
            return 1
    if getattr(args, "admin", False):
        pw = args.password or make_password("admin")
        add_account(args.school, args.id, pw, args.seat, "admin", "", "")
        print("管理者を作りました: %s / %s" % (args.id, pw))
        print("  入口は /admin 。ふつうの入口からは入れません。")
        return 0
    if not args.teacher:
        # 同じクラスの同じ番号に、在籍中の生徒がもういれば作らない（クラス替えで移ってきた生徒など）。
        # 作ると「小4β-07」が2人になり、塾内テストの席で合わせられなくなる。
        seat0 = str(args.seat).strip()
        held = sorted(lid for lid, a in accounts(args.school).items()
                      if a.get("role") == "student" and not a.get("leftAt")
                      and a.get("classId") == args.klass and seat_of(a) == seat0)
        if held:
            print("その席（%s の %s 番）には、在籍中の生徒がいます: %s" % (args.klass, seat0, ", ".join(held)))
            print("  番号を変えるか、クラス替え（move）で先に席を空けてください。")
            return 1
    acc = add_account(args.school, args.id, pw, args.seat,
                      "teacher" if args.teacher else "student",
                      args.level, args.klass, classes=klasses)
    if not args.teacher:
        with LOCK:
            join_open_homework(args.school, [args.id])      # いま出ている宿題（期限前）に足す。入ったその日から宿題が見える
    if assign:
        with LOCK:
            db = accounts(args.school)
            db[args.id]["assign"] = assign
            save_accounts(args.school, db)
    print("作りました: %s / %s" % (args.id, pw))
    if args.teacher:
        if assign:
            print("  講師。担当:")
            for row in assign:
                cid, sub = row[0], row[1]
                d = DAY_LABEL.get(row[2] if len(row) > 2 else 0, "―")
                pr = row[3] if len(row) > 3 else ""
                print("    %s%s限  %-6s %s" % (d, pr, cid, sub))
        else:
            print("  講師。担当クラス: %s（全教科）" % ",".join(klasses))
    else:
        print("  %s の %s番" % (args.klass, args.seat))
    print("  氏名は保存していません。手元の名簿で対応づけてください。")


def cmd_list(args):
    db = accounts(args.school)
    if not db:
        print("校舎 %s にアカウントがありません。 "
              "python3 tube_server.py seed --school %s" % (args.school, args.school))
        return
    if args.csv:
        print("id,seat,role,level,classId,sid,savedAt")
        for k, a in sorted(db.items()):
            rec = paths.load(progress_path(args.school, a["sid"]), None) or {}
            print("%s,%s,%s,%s,%s,%s,%s" % (k, seat_of(a), a["role"], a["level"],
                                            a["classId"], a["sid"],
                                            rec.get("savedAt", "")))
        return
    print("  %-9s %-6s %-8s %-7s %-9s %s" %
          ("ID", "番号", "役割", "学年", "内部ID", "保存された進捗"))
    print("  " + "-" * 64)
    for k, a in sorted(db.items()):
        rec = paths.load(progress_path(args.school, a["sid"]), None)
        if rec:
            cards = len((rec.get("blob") or {}).get("cards") or {})
            # updated が無い記録もある（デモが直に書いたものなど）。
            # 一覧を見ようとしただけで落ちるのは割に合わない。
            up = rec.get("updated") or rec.get("savedAt")
            when = (time.strftime("%m/%d %H:%M", time.localtime(up))
                    if isinstance(up, (int, float)) and up else "—")
            note = "%d項目  %s" % (cards, when)
        else:
            note = "—"
        print("  %-9s %-6s %-8s %-7s %-9s %s" %
              (k, seat_of(a), a["role"], a["level"], a["sid"], note))


def _set_password(db, login_id, pw, ver=None):
    """合言葉を付け替える（db を直すだけ。保存は呼ぶ側）。ver を渡せば、計算ずみの値を置く。"""
    a = db[login_id]
    a.pop("hash", None)
    a.pop("claim", None)          # 引き換え待ちだった席も、ふつうの合言葉に戻る
    a.update(ver or SCRAM.make_verifier(pw))
    a["pwAt"] = int(time.time())
    # 付け替えたら、その人の合言葉は全部無効にする
    with LOCK:
        revoke_tokens(login_id)


def cmd_passwd(args):
    """合言葉を付け替える。**ハッシュの計算は鍵の外、確かめて書くのは鍵の中**（動いているサーバの横で流せる）。"""
    school = args.school
    if args.all:
        # デモや手元の試しで、全員ぶんを作り直すための道。
        # **管理者のいる本物の校舎では使わない。** 配ったカードが全部使えなくなり、合言葉が
        # サーバの画面に平文で並ぶ（合言葉は管理ページで、端末の中で作る）。
        if school_managed(school) and not is_demo_school(school):
            print("この校舎には管理者がいます。全員ぶんの作り直しは、ここではしません。")
            print("（配ったカードが全部使えなくなります。1人ずつ、管理ページの「席と合言葉」で作り直してください）")
            return 1
        rows = []
        for login_id, a in sorted(accounts(school).items()):
            pw = make_password(a.get("role"))
            rows.append((login_id, pw, SCRAM.make_verifier(pw)))
        out = []
        with LOCK:
            db = accounts(school)
            for login_id, pw, ver in rows:
                if login_id not in db:
                    continue                      # 計算のあいだに消えた
                _set_password(db, login_id, pw, ver)
                a = db[login_id]
                who = ("講師 " + seat_of(a)) if a["role"] == "teacher" else \
                      ("%s-%s" % (a.get("classId", ""), seat_of(a)))
                out.append((login_id, pw, who))
            save_accounts(school, db)
        print("全員のパスワードを作り直しました。いま一度だけ表示されます。\n")
        print("  %-9s %-26s %s" % ("ID", "パスワード", "画面での表示"))
        print("  " + "-" * 52)
        for r in out:
            print("  %-9s %-26s %s" % r)
        print("\n  進捗は消えていません。全員ログインし直しになります。")
        return

    if not args.id:
        print("IDを指定するか、--all を付けてください。")
        return 1
    a = accounts(school).get(args.id)
    if not a:
        print("そのIDはありません: %s" % args.id)
        return 1
    pw = args.password or make_password(a.get("role"))
    if len(norm_pw(pw)) < 6:
        print("パスワードは6文字以上にしてください")
        return 1
    ver = SCRAM.make_verifier(pw)
    with LOCK:
        db = accounts(school)
        if args.id not in db:
            print("そのIDはありません: %s" % args.id)
            return 1
        _set_password(db, args.id, pw, ver)
        save_accounts(school, db)
    print("付け替えました: %s / %s" % (args.id, pw))


def cmd_rm(args):
    db = accounts(args.school)
    acc = db.pop(args.id, None)
    if not acc:
        print("そのIDはありません: %s" % args.id)
        return 1
    save_accounts(args.school, db)
    paths.unbind_login(args.id)
    if args.purge:
        try:
            os.remove(progress_path(args.school, acc["sid"]))
            print("進捗も消しました。")
        except OSError:
            pass
    print("消しました: %s（進捗は %s）" %
          (args.id, "削除済み" if args.purge else "data/progress に残しています"))


def cmd_anonymise(args):
    """氏名を持っていた古いアカウントから、氏名を消して出席番号に置き換える。

    進捗は消えない（進捗は内部IDに紐づいていて、氏名には紐づいていない）。
    実行前に、どのIDが誰だったかを手元の名簿に控えておくこと ――
    ここで消したら、アプリ側からはもう分からなくなる。それが狙いである。"""
    db = accounts(args.school)
    if not db:
        print("アカウントがありません。")
        return 1

    named = {k: a for k, a in db.items() if a.get("name") and not a.get("seat")}
    if not named:
        print("氏名を持っているアカウントはありません。すでに番号だけです。")
        return

    # 実行前に対応表を出す。これを控えないと復元できない。
    print("次のように置き換えます。**この対応表を先に控えてください。**\n")
    print("  %-9s %-12s %s" % ("ID", "いまの氏名", "これから"))
    print("  " + "-" * 44)
    counters = {}
    plan = []
    for k in sorted(named, key=lambda x: (db[x]["classId"], x)):
        a = db[k]
        cid = a["classId"]
        counters[cid] = counters.get(cid, 0) + 1
        seat = "%02d" % counters[cid] if a["role"] == "student" else "T%d" % counters[cid]
        plan.append((k, a["name"], seat))
        print("  %-9s %-12s %s の %s番" % (k, a["name"], cid, seat))

    if not args.yes:
        print("\n  実行するには --yes を付けてください。")
        print("    python3 tube_server.py anonymise --yes")
        return

    for k, _old, seat in plan:
        db[k]["seat"] = seat
        db[k].pop("name", None)
    save_accounts(args.school, db)
    audit(args.school, "cli", "anonymise", "", "%d件" % len(plan))
    print("\n  氏名を削除しました（%d件）。進捗は残っています。" % len(plan))


def parse_due(text):
    """YYYY-MM-DD をその日の終わり（23:59）として読む。
    「8月7日まで」と言われたら、7日いっぱいが期限のはずだから。"""
    try:
        t = time.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise ValueError("期限は 2026-08-07 の形で入れてください")
    return int(time.mktime((t.tm_year, t.tm_mon, t.tm_mday,
                            23, 59, 59, 0, 0, -1)) * 1000)


def cmd_hw(args):
    db = assignments(args.school)

    if args.hwcmd == "list":
        if not db:
            print("宿題はまだありません。")
            return
        for aid, a in sorted(db.items(), key=lambda kv: kv[1].get("dueAt", 0)):
            s = hw_summary(args.school, a)
            due = time.strftime("%m/%d", time.localtime(a["dueAt"] / 1000))
            who = ("生徒%d名を個別指定" % len(a["students"])) if a["students"] \
                else ("クラス " + a["classId"])
            print("  %s  %s" % (aid, a["title"]))
            print("      No.%d-%d / 期限 %s / %s" % (a["from"], a["to"], due, who))
            # 紙の宿題は達成を数えていない（completed が None）。
            # そのまま %d に渡すと落ちる。数えていないものは数えていないと書く。
            if s.get("route") == "paper":
                print("      ノートでやる宿題　%d人に出題　評価ずみ %d人"
                      % (s["assigned"], s.get("rated") or 0))
            else:
                print("      完了 %d / %d人　着手 %d人" %
                      (s["completed"], s["assigned"], s["started"]))
            for r in s["rows"]:
                lid, acc = find_by_sid(args.school, r["sid"])
                if s.get("route") == "paper":
                    mark = RATING_LEVELS.get(r.get("v"), "?")
                else:
                    mark = "済" if r["completedAt"] else ("%d/%d" % (r["done"], s["total"]))
                print("        %-9s %-6s %s" % (lid or "?", seat_of(acc or {}), mark))
        return

    if args.hwcmd == "rm":
        if args.id not in db:
            print("その宿題はありません: %s" % args.id)
            return 1
        title = db.pop(args.id)["title"]
        save_assignments(args.school, db)
        print("取り消しました: %s（生徒側の達成記録は残します）" % title)
        return

    # add
    picked = []
    if args.students:
        acc_db = accounts(args.school)
        for lid in [x.strip() for x in args.students.split(",") if x.strip()]:
            if lid not in acc_db:
                print("そのIDはありません: %s" % lid)
                return 1
            picked.append(acc_db[lid]["sid"])
    try:
        rec = valid_assignment(args.school, {
            "title": args.title, "source": args.source,
            "from": args.lo, "to": args.hi,
            "classId": args.klass or "", "students": picked,
            "dueAt": parse_due(args.due), "note": args.note or "",
        })
    except ValueError as e:
        print("作れません: %s" % e)
        return 1
    rec["id"] = "a" + secrets.token_hex(4)
    rec["createdBy"] = "cli"
    rec["assignedAt"] = int(time.time() * 1000)
    db[rec["id"]] = rec
    save_assignments(args.school, db)
    n = len(students_for(args.school, rec))
    print("出しました: %s（No.%d-%d・%d語）" %
          (rec["title"], rec["from"], rec["to"], rec["to"] - rec["from"] + 1))
    print("  期限 %s / 対象 %d名 / ID %s" % (args.due, n, rec["id"]))
    if n == 0:
        print("  ※ 対象が0名です。クラスIDか生徒IDを確かめてください。")


def cmd_courses_import(args):
    """コースを CSV から入れる。**1行でもおかしければ、何も入れない。**

        id,教科,名前,学年,講師,時間,クラス,指名,単位,期間

    授業計画（予定・宿題）には触らない。CSV に無いコースは消さない。
    講習を足すのも、授業が増えたときもこれ。形は server/courses.py の parse_row。
    """
    school = args.school
    db = accounts(school)
    known = set(class_table(school).keys())
    try:
        rows = courses.read_csv(args.file)
    except (IOError, OSError, ValueError) as e:
        print("× %s" % e)
        return 1
    parsed, bad, seen = [], [], set()
    for i, r in enumerate(rows, 2):
        try:
            key, d = courses.parse_row(r, db, known)
        except ValueError as e:
            bad.append("  %d行目: %s" % (i, e))
            continue
        if key in seen:
            bad.append("  %d行目: 同じコースが2回あります: %s" % (i, key))
            continue
        seen.add(key)
        parsed.append((key, d))
    if bad:
        print("× 直してから入れ直してください（何も入れていません）")
        print("\n".join(bad[:30]))
        return 1
    print("校舎 %s（%s）に %d件のコースを入れます。"
          % (school, school_name(school), len(parsed)))
    if not args.yes:
        print("実行するには --yes を付けてください。")
        return 0
    made, changed = courses.upsert(school, parsed, new_app=False)   # 新しいコースは講師が選ぶまで紙のまま
    audit(school, "cli", "courses_import", "",
          "made=%d changed=%d" % (made, changed))
    print("作った %d件 / 直した %d件 / 変わらない %d件"
          % (made, changed, len(parsed) - made - changed))
    return 0


def cmd_courses_slots(args):
    """時間割（カリキュラム/コマ.csv）の時間だけを入れる。**1行でもおかしければ、何も入れない。**

        id,教科,名前,学年,時間,クラス

    講師・指名・授業計画には触らない（courses.set_slots）。まだ無いコースは講師なし・紙のままで作る。
    """
    school = args.school
    known = set(class_table(school).keys())
    try:
        rows = courses.read_slot_csv(args.file)
    except (IOError, OSError, ValueError) as e:
        print("× %s" % e)
        return 1
    parsed, bad, seen = [], [], set()
    for i, r in enumerate(rows, 2):
        try:
            key, d = courses.parse_slot_row(r, known)
        except ValueError as e:
            bad.append("  %d行目: %s" % (i, e))
            continue
        if key in seen:
            bad.append("  %d行目: 同じコースが2回あります: %s" % (i, key))
            continue
        seen.add(key)
        parsed.append((key, d))
    if bad:
        print("× 直してから入れ直してください（何も入れていません）")
        print("\n".join(bad[:30]))
        return 1
    cur = courses.all_courses(school)
    new = [(k, d) for k, d in parsed if k not in cur]
    diff = [(k, d) for k, d in parsed if k in cur and (cur[k].get("slots") or []) != d["slots"]]
    print("校舎 %s（%s）の時間割：%d件（時間が変わる %d件・新しいコース %d件）"
          % (school, school_name(school), len(parsed), len(diff), len(new)))
    for k, d in new:
        print("  新しく作る   %-20s %s  %s" % (k, d["name"], courses.slots_text(d["slots"])))
    for k, d in diff:
        print("  時間が変わる %-20s %s → %s" % (k, courses.slots_text(cur[k].get("slots")) or "（無し）",
                                                courses.slots_text(d["slots"])))
    if not args.yes:
        print("実行するには --yes を付けてください。")
        return 0
    try:
        made, changed, same = courses.set_slots(school, parsed)
    except ValueError as e:
        print("× %s（何も入れていません）" % e)
        return 1
    audit(school, "cli", "courses_slots", "", "made=%d changed=%d" % (made, changed))
    print("作った %d件 / 時間を直した %d件 / 変わらない %d件" % (made, changed, same))
    return 0


def cmd_courses_teachers(args):
    """担当（カリキュラム/担当.csv）の講師だけを入れる。**1行でもおかしければ、何も入れない。**

        id,教科,講師      講師はログインID（空白区切り）。空は触らない。「-」は講師なし

    時間・指名・授業計画・使う印には触らない（courses.set_teachers）。無いコースは作らない（先に courses-slots）。
    """
    school = args.school
    db = accounts(school)
    try:
        rows = courses.read_teacher_csv(args.file)
    except (IOError, OSError, ValueError) as e:
        print("× %s" % e)
        return 1
    parsed, bad, seen = [], [], set()
    for i, r in enumerate(rows, 2):
        try:
            key, sids = courses.parse_teacher_row(r, db)
        except ValueError as e:
            bad.append("  %d行目: %s" % (i, e))
            continue
        if key in seen:
            bad.append("  %d行目: 同じコースが2回あります: %s" % (i, key))
            continue
        seen.add(key)
        if sids is not None:
            parsed.append((key, sids))
    cur = courses.all_courses(school)
    for key, _s in parsed:
        if key not in cur:
            bad.append("  コースがありません（先に sh deploy/時間割.sh）: %s" % key)
    if bad:
        print("× 直してから入れ直してください（何も入れていません）")
        print("\n".join(bad[:30]))
        return 1
    by_sid = {a.get("sid"): lid for lid, a in db.items() if a.get("sid")}

    def names(sids):
        return " ".join(by_sid.get(s, "?") for s in sids) or "（無し）"
    diff = [(k, s) for k, s in parsed if list(cur[k].get("teachers") or []) != list(s)]
    print("校舎 %s（%s）の担当：%d件（担当が変わる %d件・変わらない %d件）"
          % (school, school_name(school), len(parsed), len(diff), len(parsed) - len(diff)))
    for k, s in diff:
        print("  担当が変わる %-20s %s  %s → %s" % (k, cur[k].get("name") or "", names(cur[k].get("teachers") or []), names(s)))
    if not args.yes:
        print("実行するには --yes を付けてください。")
        return 0
    try:
        changed, same = courses.set_teachers(school, parsed)
    except ValueError as e:
        print("× %s（何も入れていません）" % e)
        return 1
    audit(school, "cli", "courses_teachers", "", "changed=%d" % changed)
    print("担当を直した %d件 / 変わらない %d件" % (changed, same))
    return 0


def cmd_courses_export(args):
    """コースを CSV に出す。表計算で直して courses-import で戻せる。"""
    out = args.out or ("courses-%s-%s.csv"
                       % (args.school, time.strftime("%Y%m%d-%H%M%S")))
    n = courses.write_csv(args.school, out)
    print("%d件のコースを書き出しました: %s" % (n, out))
    return 0


def lan_ip():
    """生徒が実際に打つアドレス。外に繋ぎにはいかず、経路だけを見る。"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 1))     # 予約アドレス。通信は起きない
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


SUBJECT_JP = (("japanese", "国語"), ("math", "数学"), ("english", "英語"),
              ("science", "理科"), ("social", "社会"))


def demo_list():
    """デモの入口に出す一覧。**生徒には学年・クラス・受講教科を添える。**

    「生徒として見る」が5つ並んでも、どれが何の生徒か分からないため。
    デモの架空のアカウントにだけ使う（本物の名簿はここを通らない）。
    """
    out = []
    for a in demo_accounts():
        row = {k: v for k, v in a.items() if k != "password"}     # 合言葉は、あっても出さない
        school = paths.school_of_login(a["id"])
        acc = accounts(school).get(a["id"]) if school else None
        if acc and acc.get("role") == "student":
            c = class_table(school).get(acc.get("classId")) or {}
            grade = acc.get("level") or c.get("grade") or ""
            base = enabled_subjects(school, grade) or [s for s, _ in SUBJECT_JP]
            taking = acc.get("subjects") or base
            row["className"] = c.get("name") or acc.get("classId") or ""
            row["subjects"] = [("算数" if s == "math" and grade.startswith("e") else w)
                               for s, w in SUBJECT_JP if s in base and s in taking]
        elif acc and acc.get("role") == "teacher":
            # 講師は「どのクラスを持つ人か」で見分ける：担当クラスの名前と、コースの数。
            # 本物の講師（wt01〜）が並ぶので、ID だけでは本人も見分けにくい。氏名は持っていない。
            tbl = class_table(school)
            cids = teacher_classes(dict(acc, school=school))
            names = []
            for cid in (cids or []):
                nm = (tbl.get(cid) or {}).get("name")
                if nm and nm not in names:
                    names.append(nm)
            row["classes"] = ["*"] if cids is None else names
            row["courses"] = len(courses.of_teacher(school, acc.get("sid")))
        out.append(row)
    return out


def demo_exam_window(school, sid, grade=""):
    """組み分けテスト対策の見本の生徒の窓（デモだけ）。それ以外は None。

    本物の日程は動かさない。見本の生徒（examDemoDays を持つデモの架空の
    アカウント）にだけ、「本番まであと N 日」の窓を毎日作り直して渡す。
    --demo で起動していないサーバでは効かない。

    講師がクラスの見本を見るとき（sid が空）は、同じ学年の見本の生徒の窓を使う。
    **生徒に見えている対策が講師に見えないと、デモで説明も印刷もできない。**
    """
    if not DEMO["on"]:
        return None
    if sid:
        _, acc = find_by_sid(school, sid)
    elif grade:
        acc = next((a for a in accounts(school).values()
                    if a.get("role") == "student" and a.get("level") == grade
                    and isinstance(a.get("examDemoDays"), int)), None)
    else:
        return None
    days = (acc or {}).get("examDemoDays")
    if not isinstance(days, int) or not 0 <= days <= examcal.prep_days(school):
        return None
    now = time.time()
    date = time.strftime("%Y-%m-%d", time.localtime(now + days * 86400))
    return examcal.window_for(school, {"date": date, "name": "組み分けテスト（見本）"}, now)


def trial_pick_rows():
    """試し運用の校舎で、demo_trial.py が無作為に選んで school.json の trialPick に置いた生徒（ID だけ）。
    本番の生徒の中から学年ごとに数名（2026-10-12 本人）。試し運用の印が外れたら出ない。"""
    out = []
    try:
        for s in paths.list_schools():
            meta = school_meta(s)
            if not meta.get("trial") or is_demo_school(s):
                continue
            for lid in (meta.get("trialPick") or [])[:24]:
                lid = SCRAM.norm_id(str(lid))[:32]
                if lid:
                    out.append({"id": lid, "label": lid, "role": "student", "note": "本番の生徒から無作為に"})
    except Exception:
        return []
    return out


def demo_accounts():
    """「ためしに見る」に出す口座：deploy/ためしに見る.json の口座 ＋ 試し運用の校舎の trialPick。"""
    seen = set()
    out = []
    for a in list(DEMO["accounts"]) + trial_pick_rows():
        if a["id"] in seen:
            continue
        seen.add(a["id"])
        out.append(a)
    return out


def trial_join_code():
    """試し運用の校舎の登録コード（初回登録の欄に先に入れておくため。app/js/trial-join-code.js）。本番に切り替えたら None。"""
    try:
        for s in paths.list_schools():
            meta = school_meta(s)
            if meta.get("trial") and not is_demo_school(s) and (meta.get("join") or {}).get("code"):
                return str(meta["join"]["code"])
    except Exception:
        return None
    return None


def load_demo_accounts(path):
    """「ためしに見る」に出す口座の一覧（ID・見出し・一言）を読み込む。

    **合言葉は要らない。** ボタンは POST /api/demo/enter に ID だけを送り、サーバが
    この一覧にある口座にだけ入った印を出す（2026-10-10：本物の校舎の講師 wt01〜wt06 と
    ためし用の生徒を入口に出す。本物の合言葉は平文でどこにも置かない）。
    古い形（password の欄がある）も読めるが、合言葉は覚えないし /api/demo にも出さない。
    出すのは16件まで。本番の一覧は deploy/ためしに見る.json（更新.sh が置く）。
    """
    rows = load_json(path, [])
    out = []
    seen = set()
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        lid = SCRAM.norm_id(r["id"])[:32]
        if not lid or lid in seen:
            continue
        seen.add(lid)
        out.append({"id": lid,
                    "label": str(r.get("label") or lid)[:40],
                    "role": "teacher" if r.get("role") == "teacher" else "student",
                    "note": str(r.get("note", ""))[:40]})
        if len(out) >= 16:
            break
    return out


def demo_list_is_only(school, path=None):
    """<ROOT>/demo-accounts.json が、その校舎の口座だけを並べているか（無い・空も True）。

    デモを作り直す（demo-swap）とき、入口の一覧を写してよいかの判定。本物の校舎の講師や
    ためし用の生徒を並べた一覧を、架空の口座の一覧で上書きしない。
    """
    rows = paths.load(path or os.path.join(paths.ROOT, "demo-accounts.json"), []) or []
    if not isinstance(rows, list):
        return True
    idx = paths.read_index()
    for r in rows:
        lid = SCRAM.norm_id(r.get("id")) if isinstance(r, dict) else ""
        if lid and idx.get(lid) not in (None, school):
            return False
    return True


def warm_prep():
    """対策テストの問題の束（examprep.pack_items）を先に読んでおく。

    束は1回読めば覚えておける（examprep._CACHE）が、1人目の生徒が開いたときに
    教材ファイル百数十本を読み込むと、その生徒を長く待たせる
    （2026-09-10、iCloud 上の開発機で18秒）。起動したら裏で読んでおく。
    """
    for grade in ("e4", "e5", "e6", "j1", "j2", "j3"):
        for sub in sorted(examprep.CODE):
            try:
                examprep.pack_items(sub, grade)
            except Exception:
                pass


def cmd_serve(args):
    ensure_dirs()
    if args.demo:
        path = args.demo_file or os.path.join(paths.ROOT, "demo-accounts.json")
        DEMO["accounts"] = load_demo_accounts(path)
        DEMO["on"] = bool(DEMO["accounts"])
        if not DEMO["on"]:
            print("※ --demo を付けましたが %s が読めません。" % path)
            print("  デモ用のボタンは出ません。\n")
    threading.Thread(target=warm_prep, daemon=True).start()
    threading.Thread(target=housekeeping, daemon=True).start()
    schools = paths.list_schools()
    # 古い形の口座を、直せるものだけ新しい形（scram）にする。直せないものは、入れないまま残る。
    for sc in schools:
        try:
            fixed, left = upgrade_legacy(sc)
        except (IOError, OSError, BadPath, ValueError):
            continue
        if fixed:
            print("校舎 %s：古い形の口座 %d件を、新しい形に直しました。" % (sc, fixed))
        if left:
            print("※ 校舎 %s：古い形の口座が %d件あります。このままでは入れません。" % (sc, left))
            print("   デモなら作り直す（seed --reset → demo_running.py）。本物なら passwd か、管理ページの「合言葉を作り直す」。")
    if not schools:
        print("校舎がありません。先に:  python3 tube_server.py seed\n")
    handler = functools.partial(Handler, directory=APP_DIR)
    # 待ち行列を広げる（既定 5）。iPad の Safari や Chrome は部品を6本以上並列に取りに来るので、
    # 既定のままだと溢れた接続が切られ（ERR_CONNECTION_RESET）、画面が白いまま止まることがある。
    class _Server(ThreadingHTTPServer):
        request_queue_size = 128
        daemon_threads = True
        allow_reuse_address = True
    httpd = _Server((args.host, args.port), handler)
    local_only = args.host in ("127.0.0.1", "localhost")

    print("Tube for Schools — 仮サーバ")
    print("  配信元    %s" % APP_DIR)
    print("  保管先    %s" % paths.ROOT)
    for sc in schools:
        db = accounts(sc)
        print("  校舎      %-10s %-18s 生徒%d名 講師%d名"
              % (sc, school_name(sc),
                 len([a for a in db.values() if a["role"] == "student"]),
                 len([a for a in db.values() if a["role"] == "teacher"])))
    if DEMO["on"]:
        print("  ★ デモ用の入室ボタンを %d件 出します（合言葉が画面に出ます）"
              % len(DEMO["accounts"]))
    print()
    print("  このMacから      http://127.0.0.1:%d/" % args.port)
    if local_only:
        print("  ほかの端末から   繋がりません（--host 0.0.0.0 を付けると開きます）")
    else:
        ip = lan_ip()
        if ip:
            print("  ほかの端末から   http://%s:%d/" % (ip, args.port))
            print("                   ↑ 同じWi-Fi／テザリングに繋いだ端末で開く")
        else:
            print("  ほかの端末から   このMacのIPアドレス:%d" % args.port)
        print()
        print("  ※ 同じネットワークにいる全員から見えます。カフェや学校の")
        print("     共用Wi-Fiでは、無関係な人にも届きます。")
        print("  ※ TLSが無いので、パスワードは暗号化されずに流れます。")
        print("     試用のためのものです。本物の生徒データを入れないでください。")
        print("  ※ 外に出す前に  python3 tube_server.py passwd --all")
    print("\n  Macがスリープすると止まります。防ぐには別の窓で:")
    print("    caffeinate -di")
    print("\n  止めるときは Ctrl+C\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n止めました。")


def is_demo_school(school):
    """架空のデモの校舎か。目印は school.json の "demo": true（demo_running.py が付ける）。
    目印が付く前に作られたデモ（入口の架空アカウント lteacher1 がいる）もデモとみなす。"""
    if school_meta(school).get("demo"):
        return True
    return (school_code(school) + "teacher1") in accounts(school)


def cmd_schools(args):
    """校舎の一覧。どこに何があるかを最初に確かめるための入口。"""
    ss = paths.list_schools()
    if getattr(args, "real_count", False):
        # 本物の校舎（デモでないもの）の数だけを出す。反映の道具（更新.sh）が見る。
        print(len([s for s in ss if not is_demo_school(s)]))
        return 0
    print("保管先  %s" % paths.ROOT)
    if not ss:
        print("\n校舎がまだありません。作るには:")
        print("  python3 tube_server.py school-add london 'ロンドン校'")
        return
    print()
    print("  %-16s %-18s %-6s %-8s %-6s %-6s %s" % ("ID", "表示名", "生徒", "空き席", "講師", "管理", "宿題"))
    print("  " + "-" * 72)
    for s in ss:
        db = accounts(s)
        print("  %-16s %-18s %-6d %-8d %-6d %-6d %d"
              % (s, school_name(s) + ("（デモ）" if is_demo_school(s) else ""),
                 len([a for a in db.values() if a["role"] == "student"]),
                 len([a for a in db.values() if a["role"] == "seat"]),
                 len([a for a in db.values() if a["role"] == "teacher"]),
                 len([a for a in db.values() if a["role"] == "admin"]),
                 len(assignments(s))))


def cmd_go_live(args):
    """本番に切り替える：試し運用のあいだの生徒（配った席・試しに登録された口座）を退避し、まっさらな名簿にする。

        python3 tube_server.py go-live --school <校舎> --yes     （sh deploy/本番切替.sh が流す）

    残すもの：school.json（試し運用の印を外し、本番の印を付け、**招待コードを作り直す**）・curriculum.json（クラス）・
    materials.json・presets.json・lessons.json（コースと授業計画。指名の生徒と「出した印」は外す）・
    講師と管理者の口座（同じ ID・同じ合言葉で続けて入れる）。
    残さないもの：生徒の口座・進捗・提出・評価・宿題・成績・メッセージ・報告・監査（前の校舎ごと
    schools/.old-<校舎>-<日時>/ に退避する。消さない）。
    このあと、保護者が新しい招待コードから登録する。サーバは止めない。
    """
    school = paths.check_school(args.school)
    if not os.path.isfile(paths.school_file(school, "school.json")):
        print("× 校舎 %s がありません" % school)
        return 1
    if is_demo_school(school):
        print("× 校舎 %s は架空のデモです（デモは デモを作り直す.sh で）" % school)
        return 1
    meta = dict(school_meta(school))
    if meta.get("live") and not args.again:
        print("× 校舎 %s は、もう本番に切り替えてあります。もう一度まっさらにするなら --again（生徒の記録が退避されます）。" % school)
        return 1
    old = accounts(school)
    staff = {lid: a for lid, a in old.items() if a.get("role") in ("teacher", "admin")}
    n_students = len([a for a in old.values() if a.get("role") in ("student", "seat")])
    if not any(a.get("role") == "admin" and not a.get("leftAt") for a in staff.values()):
        print("× 管理者がいません。切り替えると、だれも管理ページに入れなくなります。")
        return 1
    print("校舎 %s（%s）を本番に切り替えます：いまの生徒・席 %d を退避し、名簿を空にします。講師・管理者 %d はそのまま。"
          % (school, school_name(school), n_students, len(staff)))
    print("  前の校舎は schools/.old-%s-<日時>/ に退避します（消しません）。招待コードは作り直します。" % school)
    if not args.yes:
        print("実行するには --yes を付けてください。")
        return 0
    build_root = os.path.join(paths.ROOT, ".replace-build")
    build = os.path.join(build_root, "schools", school)
    shutil.rmtree(build_root, ignore_errors=True)
    os.makedirs(build, exist_ok=True)
    now = int(time.time())
    with LOCK:
        cur = paths.school_dir(school)
        for name in ("curriculum.json", "materials.json", "presets.json"):
            src = os.path.join(cur, name)
            if os.path.isfile(src):
                shutil.copyfile(src, os.path.join(build, name))
        meta = dict(school_meta(school))
        meta.pop("trial", None)
        meta["live"] = True
        meta["liveAt"] = now
        meta["join"] = {"code": "".join(secrets.choice(JOIN.CODE_ABC) for _ in range(JOIN.CODE_LEN)), "at": now, "by": "go-live"}
        paths.save(os.path.join(build, "school.json"), meta)
        # コースと授業計画。指名の生徒・上乗せの生徒・「出した印」は外す（出した宿題は残らない）。
        ls = paths.load(os.path.join(cur, "lessons.json"), None)
        if isinstance(ls, dict):
            for key, pl in (ls.get("plans") or {}).items():
                if not isinstance(pl, dict):
                    continue
                pl["students"] = []
                for ex in pl.get("extra") or []:
                    if isinstance(ex, dict):
                        ex["students"] = []
                for l in pl.get("lessons") or []:
                    for k in ("published", "publishedIds", "publishedAt", "doneAt"):
                        l.pop(k, None)
            paths.save(os.path.join(build, "lessons.json"), ls)
        db = {lid: dict(a) for lid, a in staff.items()}
        paths.save(os.path.join(build, "accounts.json"), db)
        with open(os.path.join(build, "audit.log"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now, "actor": "cli", "action": "go_live", "target": "",
                                "extra": "退避した生徒・席 %d／講師と管理者 %d" % (n_students, len(staff))}, ensure_ascii=False) + "\n")
        trash = os.path.join(paths.SCHOOLS, ".old-%s-%s" % (school, time.strftime("%Y%m%d-%H%M%S", time.localtime(now))))
        os.rename(cur, trash)
        os.rename(build, cur)
        idx = {k: v for k, v in paths.read_index().items() if v != school}
        for k in db:
            idx[k] = school
        paths.write_index(idx)
        # 入ったままの画面：講師・管理者は続く。前の生徒の印は閉じる。
        store = tokens()
        gone = [t for t, r in store.items() if r.get("school") == school
                and (r.get("loginId") not in db or db[r["loginId"]].get("sid") != r.get("sid"))]
        for t in gone:
            store.pop(t)
        if gone:
            save_tokens(store)
    shutil.rmtree(build_root, ignore_errors=True)
    print("切り替えました：名簿は空・講師と管理者 %d。前の校舎は %s" % (len(staff), trash))
    print("  招待コード（新しいもの）は、管理ページの「いまの様子」→「登録コード」に出ています。刷って配ってください。")
    print("  講師の担当・授業計画・教材はそのまま。出ていた宿題は消えたので、次の授業日にまた出ます。")
    return 0


def cmd_school_trial(args):
    """試し運用の印を付ける・外す。付いているあいだ、その校舎は「まだ本物でない」と数える
    （ふつうの入口に「ためしに見る」を出す）。**本番に切り替えた校舎（live）には、もう付けられない。**"""
    school = paths.check_school(args.school)
    if not os.path.isfile(paths.school_file(school, "school.json")):
        print("× 校舎 %s がありません" % school)
        return 1
    with LOCK:
        meta = dict(school_meta(school))
        if args.on:
            if meta.get("live"):
                print("校舎 %s は本番に切り替えずみです。試し運用には戻しません。" % school)
                return 0
            meta["trial"] = True
        else:
            meta.pop("trial", None)
        paths.save(paths.school_file(school, "school.json"), meta)
    print("校舎 %s：試し運用 %s" % (school, "入" if meta.get("trial") else "切"))
    return 0


def cmd_demo_swap(args):
    """別の置き場で作り終えたデモの校舎を、**サーバを止めずに**入れ替える。

        MYACADY_ROOT=/srv/myacady/.demo-build python3 tube_server.py seed --reset --empty --school london …
        MYACADY_ROOT=/srv/myacady/.demo-build python3 demo_running.py --school london
        MYACADY_ROOT=/srv/myacady python3 tube_server.py demo-swap --from /srv/myacady/.demo-build --school london --yes

    前は、動いている置き場の中でデモを消して作り直していたので、そのあいだ（数分）サーバを止めていた。
    本物の校舎を使い始めると、その数分は生徒と講師が入れない時間になる。
    ここでは、作り終えた校舎のフォルダを名前の付け替えで入れ替える（鍵の中で、一瞬）。

    **入れ替えてよいのは、デモの校舎だけ。** 行き先に本物の校舎があれば、何もしない。
    """
    school = paths.check_school(args.school)
    src_root = os.path.abspath(args.src)
    src = os.path.join(src_root, "schools", school)
    meta = paths.load(os.path.join(src, "school.json"), {}) or {}
    if not meta.get("demo"):
        print("× %s は、デモの校舎ではありません（school.json に demo の目印が無い）。" % src)
        return 1
    if os.path.abspath(src_root) == os.path.abspath(paths.ROOT):
        print("× 同じ置き場です。別の置き場で作ってから入れ替えてください。")
        return 1
    if os.stat(src_root).st_dev != os.stat(paths.ROOT).st_dev:
        print("× 別のディスクにあります。名前の付け替えで入れ替えられません（同じ置き場の下に作ってください）。")
        return 1
    dst = paths.school_dir(school)
    if os.path.isdir(dst) and os.path.isfile(paths.school_file(school, "school.json")) and not is_demo_school(school):
        print("× 校舎 %s は架空のデモではありません。入れ替えません。" % school)
        return 1
    # 新しいデモの ID は、作り終えた校舎の口座そのものから読む（索引は、前に作ったときの残りを持つことがある）。
    new_ids = sorted((paths.load(os.path.join(src, "accounts.json"), {}) or {}).keys())
    clash = sorted(k for k in new_ids if (paths.school_of_login(k) or school) != school)
    if clash:
        print("× 新しいデモのIDが、ほかの校舎で使われています: %s" % ", ".join(clash[:8]))
        return 1
    print("校舎 %s（デモ）を入れ替えます：口座 %d" % (school, len(new_ids)))
    if not args.yes:
        print("実行するには --yes を付けてください。")
        return 0
    trash = os.path.join(paths.SCHOOLS, ".old-%s-%d" % (school, int(time.time())))
    with LOCK:
        os.makedirs(paths.SCHOOLS, exist_ok=True)
        if os.path.isdir(dst):
            os.rename(dst, trash)
        os.rename(src, dst)
        idx = {k: v for k, v in paths.read_index().items() if v != school}
        for k in new_ids:
            idx[k] = school
        paths.write_index(idx)
        # 入ったままの画面（合言葉）：同じIDが新しいデモにもあれば続く（sid はIDから決まる）。無いものは閉じる。
        have = paths.load(paths.school_file(school, "accounts.json"), {}) or {}
        store = tokens()
        gone = [t for t, r in store.items() if r.get("school") == school
                and (r.get("loginId") not in have or have[r["loginId"]].get("sid") != r.get("sid"))]
        for t in gone:
            store.pop(t)
        if gone:
            save_tokens(store)
        # 入口の一覧と、共通の仮の基準（shared/）を写す。
        # **入口の一覧は、このデモの校舎の口座だけを並べているときにしか写さない。**
        # 本物の校舎の講師・ためし用の生徒を並べた一覧（deploy/ためしに見る.json）を、
        # デモを作り直すたびに架空の口座で上書きしない（2026-10-10）。
        for name in ("demo-accounts.json",):
            sp = os.path.join(src_root, name)
            if os.path.isfile(sp):
                if not demo_list_is_only(school):
                    print("  入口の一覧（%s）は、ほかの校舎の口座を並べているので写しません。" % name)
                    continue
                shutil.copyfile(sp, os.path.join(paths.ROOT, name + ".new"))
                os.replace(os.path.join(paths.ROOT, name + ".new"), os.path.join(paths.ROOT, name))
        sshared = os.path.join(src_root, "shared")
        if os.path.isdir(sshared):
            for base, _dirs, files in os.walk(sshared):
                rel = os.path.relpath(base, sshared)
                for f in files:
                    d2 = os.path.join(paths.SHARED, rel)
                    os.makedirs(d2, exist_ok=True)
                    shutil.copyfile(os.path.join(base, f), os.path.join(d2, f + ".new"))
                    os.replace(os.path.join(d2, f + ".new"), os.path.join(d2, f))
    shutil.rmtree(trash, ignore_errors=True)
    # 作った側の置き場に残った索引（この校舎の分）を消す。次に作るとき、前の ID を引きずらない。
    try:
        sip = os.path.join(src_root, "index.json")
        left = {k: v for k, v in (paths.load(sip, {}) or {}).items() if v != school}
        with io.open(sip, "w", encoding="utf-8") as f:
            json.dump(left, f)
    except (IOError, OSError):
        pass
    # 前に途中で止まった入れ替えの残りも掃除する。
    for name in os.listdir(paths.SCHOOLS):
        if name.startswith(".old-"):
            shutil.rmtree(os.path.join(paths.SCHOOLS, name), ignore_errors=True)
    audit(school, "cli", "demo_swap", "", "accounts=%d" % len(new_ids))
    print("入れ替えました。サーバは動いたままです。")
    return 0


def cmd_bundle_import(args):
    """手元で作った席・講師・管理者の束を入れる（ハッシュだけ。合言葉は入っていない）。

        python3 scripts/accounts/make.py            手元で作る（合言葉の表と、束）
        python3 server/tube_server.py bundle-import deploy/accounts/<校舎>.bundle.json --yes

    何度流しても同じ結果になる（すでにある口座・コースには触らない）。
    """
    try:
        with io.open(args.file, encoding="utf-8") as f:
            bundle = json.load(f)
    except (IOError, OSError, ValueError) as e:
        print("× 読めません: %s" % e)
        return 1
    try:
        return ADMIN.import_bundle(sys.modules[__name__], bundle, yes=args.yes)
    except (ValueError, BadPath) as e:
        print("× %s" % e)
        return 1


def cmd_school_add(args):
    school = args.id
    try:
        paths.check_school(school)
    except BadPath as e:
        print("校舎IDは英小文字・数字・- で2〜24文字にしてください（例 london, ny, tokyo）")
        return 1
    if os.path.isfile(paths.school_file(school, "school.json")):
        print("すでにあります: %s（%s）" % (school, school_name(school)))
        return 1
    paths.ensure_school(school)
    code = (args.code or school[:1]).lower()
    if not re.match(r"^[a-z]{1,2}$", code):
        print("校舎コードは英小文字1〜2文字にしてください（例 l, ny, t）")
        return 1
    for other in paths.list_schools():
        if school_code(other) == code:
            print("その校舎コードは %s が使っています: %s" % (other, code))
            return 1
    paths.save(paths.school_file(school, "school.json"), {
        "id": school,
        "name": args.name,
        "code": code,
        "tz": args.tz,
        "created": int(time.time()),
    })
    # 既定のカリキュラムと教材は shared から引き継ぐ。
    # 引き継いだあとは校舎の持ち物なので、自由に書き換えてよい。
    print("校舎を作りました: %s（%s / %s）" % (school, args.name, args.tz))
    print("  ログインIDの頭に付く校舎コード: %s  （例 %sj2a01）" % (code, code))
    print("  %s" % paths.school_dir(school))
    print("\n  テスト用アカウントを入れるなら:")
    print("    python3 tube_server.py seed --school %s" % school)


def cmd_roster_import(args):
    """名簿をCSVから一括で登録する。200〜300名の初回登録はこれで行う。

    CSVの列は「クラス,出席番号」と、あれば「受講科目」（国数英理社の頭文字）。
    **氏名の列を作らない。**
    氏名を1度でもファイルに書くと、それはどこかにコピーされて残る。
    誰がどの番号かは、先生の手元の名簿にしかない状態を保つ。

        classId,seat
        j2a,01
        j2a,02

    学年はクラスIDから引く（進度に登録があればそれを使う）。
    作ったIDとパスワードはCSVで書き出す。**これを印刷して配ったら消すこと。**
    """
    school = args.school
    import csv as _csv
    rows, bad = [], []
    with open(args.file, newline="", encoding="utf-8-sig") as f:
        reader = _csv.DictReader(f)
        # 受講科目の列（国英／国数英／国数／国数英理社）。**列が無い CSV は全教科。**
        # 列があって空欄の行は入力漏れなので、1行でもあれば何も登録しない。
        subcol = next((h for h in (reader.fieldnames or [])
                       if h and h.strip() in ("subjects", "受講科目")), None)
        for i, r in enumerate(reader, 2):
            for key in r:
                if key and key.strip().lower() in ("name", "氏名", "名前"):
                    print("× CSVに氏名の列があります（%s）。" % key)
                    print("  氏名はこのシステムに入れません。列ごと消してから実行してください。")
                    return 1
            cid = (r.get("classId") or r.get("class") or "").strip()
            seat = (r.get("seat") or r.get("no") or "").strip()
            if not (cid and seat):
                continue
            subs = None
            if subcol:
                try:
                    subs = courses.parse_subjects(r.get(subcol))
                except ValueError as e:
                    bad.append("  %d行目: %s" % (i, e))
                    continue
                if not subs:
                    bad.append("  %d行目: 受講科目が空です（%s %s）" % (i, cid, seat))
                    continue
            rows.append((cid, seat, subs))
    if bad:
        print("× 直してから入れ直してください（何も登録していません）")
        print("\n".join(bad[:30]))
        return 1
    if not rows:
        print("読める行がありませんでした。列は classId,seat（と受講科目）です。")
        return 1

    code = school_code(school)
    print("校舎 %s（%s）に %d名を登録します。" % (school, school_name(school), len(rows)))
    print("  ログインIDの形: %s + クラス + 出席番号（例 %s%s%s）"
          % (code, code, rows[0][0], rows[0][1]))
    if not args.yes:
        print("\n実行するには --yes を付けてください。")
        return 0

    made, skipped = [], []
    t0 = time.time()
    # クラス替え（move）のあとは、ログインIDの「クラス＋番号」と、今のクラスと席が食い違う。
    #   ・その席に、移ってきた別の生徒がいる → 入れない（同じ「小4β-07」が2人になる）
    #   ・そのIDの生徒は移って、席は空いている → 入れない（古い名簿を流し直したのかもしれない。
    #     新しい生徒なら add で別のIDを付ける。推測で作らない）
    db0 = accounts(school)
    held = {(a.get("classId") or "", seat_of(a)): lid for lid, a in db0.items()
            if a.get("role") == "student" and not a.get("leftAt")}
    cls0 = class_table(school)
    for i, (cid, seat, subs) in enumerate(rows, 1):
        login_id = "%s%s%s" % (code, cid, seat)
        who = held.get((cid, seat))
        if who and who != login_id:
            skipped.append((login_id, "その席（%s）には、クラス替えで移ってきた生徒（%s）がいます"
                            % (_class_label(cls0, cid, seat), who)))
            continue
        old = db0.get(login_id)
        if old and not who and old.get("moves") and not old.get("leftAt"):
            skipped.append((login_id, "このIDの生徒はクラス替えで %s に移りました。この席に新しい生徒を入れるなら "
                            "add で別のID（例 %sb）を付けてください"
                            % (_class_label(cls0, old.get("classId"), seat_of(old)), login_id)))
            continue
        pw = make_password()
        try:
            add_account(school, login_id, pw, seat, "student",
                        gradeOfClass(school, cid), cid, subjects=subs)
            made.append((login_id, pw, cid, seat))
        except ValueError as e:
            skipped.append((login_id, str(e)))
        if i % 25 == 0:
            print("  %d / %d …（%.0f秒）" % (i, len(rows), time.time() - t0))

    out = args.out or ("roster-%s-%s.csv" % (school, time.strftime("%Y%m%d-%H%M%S")))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["id", "password", "classId", "seat"])
        w.writerows(made)
    print("\n登録 %d名 / とばした %d名（%.0f秒）" % (len(made), len(skipped), time.time() - t0))
    for lid, why in skipped[:10]:
        print("  とばした: %s … %s" % (lid, why))
    print("\nIDとパスワードを書き出しました: %s" % out)
    print("  **このファイルはパスワードを平文で持っています。**")
    print("  印刷して配ったら、必ず消してください。")
    print("  忘れたときは作り直せます: python3 tube_server.py passwd <ID> --school %s" % school)
    return 0


# ------------------------------------------------------------------
# クラス替え（組み分けテストのたびに α⇄β・T⇄R が入れ替わる）
#
#     python3 server/tube_server.py move 移動.csv --school london          # 確かめるだけ
#     python3 server/tube_server.py move 移動.csv --school london --yes    # 移す
#     python3 server/tube_server.py move --list --school london            # これまでのクラス替え
#     python3 server/tube_server.py move --undo m20261103-1830 --school london --yes   # 取り消す
#
# CSV の列は id,classId,seat（id はログインID。先生の手元の対応表にある）か、
# fromClass,fromSeat,classId,seat（いまの席 → 新しい席）。**氏名の列は拒む。**
#
# 変えるもの
#   ・アカウントの classId と seat。前の席は acc["moves"] に日付と番号（batch）つきで残す
#   ・まだ期限の来ていない宿題の受け取り手：出ていくコースの宿題から外し（写真・評価・アプリの記録が
#     ある宿題は外さない）、入るコースの宿題に足す（上乗せ・個別・提出箱は足さない）。
#     外した・足したは宿題の moved に残す（取り消しに使う）
# 変えないもの
#   ・sid・ログインID・パスワード・進捗・写真・評価（すべて同じ生徒のまま）
#   ・期限の過ぎた宿題（出したあとの記録は書き換えない）・指名のコース・個別の決まり（前のコースに残る）
# 取り消せること
#   ・move --undo <番号>：記録から戻す。書き換える前の accounts.json と assignments.json は
#     <校舎>/backups/<番号>/ にも置く（60日で消す）
# ------------------------------------------------------------------
def _class_label(cls, cid, seat):
    return seat_label(re.sub(r"\s+", "", (cls.get(cid) or {}).get("name") or cid or ""), seat)


def move_rows(school, path):
    """クラス替えの CSV を読む。返す ([(行, ログインID, classId, seat)], [まちがい])。"""
    import csv as _csv
    db = accounts(school)
    at_seat = {(a.get("classId") or "", seat_of(a)): lid for lid, a in db.items()
               if a.get("role") == "student" and not a.get("leftAt")}
    rows, bad = [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = _csv.DictReader(f)
        for h in reader.fieldnames or []:
            if h and h.strip().lower() in ("name", "氏名", "名前"):
                raise ValueError("CSVに氏名の列があります（%s）。氏名はこのシステムに入れません。列ごと消してください" % h)
        for i, r in enumerate(reader, 2):
            r = {(k or "").strip(): (v or "").strip() for k, v in r.items() if k}
            lid = (r.get("id") or r.get("loginId") or "").lower()
            cid = r.get("classId") or r.get("class") or ""
            seat = r.get("seat") or r.get("no") or ""
            fc, fs = r.get("fromClass") or "", r.get("fromSeat") or ""
            if not (lid or cid or seat or fc or fs):
                continue
            if not lid and fc and fs:
                lid = at_seat.get((fc, fs)) or ""
                if not lid:
                    bad.append("  %d行目: いま %s の %s 番に生徒がいません" % (i, fc, fs))
                    continue
            if not (lid and cid and seat):
                bad.append("  %d行目: id（か fromClass,fromSeat）と classId・seat が要ります" % i)
                continue
            rows.append((i, lid, cid, seat))
    return rows, bad


def move_plan(school, rows, now=None, transfer=True):
    """クラス替えの計画（書かない）。返す (計画, まちがい)。"""
    now = now or time.time()
    db = accounts(school)
    cls = class_table(school)
    errors, moves, same, seen = [], [], 0, set()
    # まだ渡していない席と、在籍を終えた生徒の番号（カードに刷ってある）。そこへ移すと、
    # あとでカードを受け取った子・戻ってきた子の、カードと画面の番号がずれる。
    held = {(x.get("classId") or "", seat_of(x)): k for k, x in db.items()
            if x.get("role") == "seat" or (x.get("role") == "student" and x.get("leftAt"))}
    for i, lid, cid, seat in rows:
        a = db.get(lid)
        if not a or a.get("role") != "student":
            errors.append("  %d行目: 生徒のIDがありません: %s" % (i, lid))
            continue
        if a.get("leftAt"):
            errors.append("  %d行目: 在籍が終わった生徒です: %s" % (i, lid))
            continue
        if lid in seen:
            errors.append("  %d行目: 同じ生徒が2回あります: %s" % (i, lid))
            continue
        seen.add(lid)
        if cls and cid not in cls:
            errors.append("  %d行目: クラス %s はありません" % (i, cid))
            continue
        if not SAFE_SEAT.match(seat):
            errors.append("  %d行目: 出席番号は英数字1〜8文字にしてください: %r" % (i, seat))
            continue
        g = (cls.get(cid) or {}).get("grade")
        if g and a.get("level") and g != a.get("level"):
            errors.append("  %d行目: 学年が変わります（%s → %s）。クラス替えは同じ学年の中だけです: %s"
                          % (i, a.get("level"), g, lid))
            continue
        frm = (a.get("classId") or "", seat_of(a))
        if frm == (cid, seat):
            same += 1
            continue
        if (cid, seat) in held:
            errors.append("  %d行目: %s は、まだ渡していない席か、在籍を終えた生徒（%s）の番号です。別の番号にしてください: %s"
                          % (i, _class_label(cls, cid, seat), held[(cid, seat)], lid))
            continue
        moves.append({"id": lid, "sid": a.get("sid"), "from": frm, "to": (cid, seat)})
    # 移したあとの全員で、同じ席に2人いないか（入れ替えは同じ CSV の中でなら通る）
    to_of = {m["id"]: m["to"] for m in moves}
    after = {}
    for lid, a in db.items():
        if a.get("role") != "student" or a.get("leftAt"):
            continue
        pos = to_of.get(lid) or (a.get("classId") or "", seat_of(a))
        after.setdefault(pos, []).append(lid)
    for pos, ids in sorted(after.items()):
        if len(ids) > 1:
            errors.append("  %s に %d人が重なります: %s" % (_class_label(cls, *pos), len(ids), ", ".join(sorted(ids))))
    plan = {"moves": moves, "same": same, "transfers": [], "notes": []}
    if transfer and moves and not errors:
        plan["transfers"], plan["notes"] = move_transfers(school, moves, now)
    return plan, errors


def _has_record(subs, rt, hw, aid, sid):
    """その宿題に、その生徒の記録（写真・評価・アプリの達成）があるか。あれば受け取り手から外さない。"""
    return bool(((subs.get(aid) or {}).get(sid)) or ((rt.get(aid) or {}).get(sid)) or (hw or {}).get(aid))


def move_transfers(school, moves, now):
    """まだ期限の来ていない宿題の付け替え。返す ([(宿題ID, sid, "out"|"in"|"keep", コース)], [知らせ])。"""
    nowms = now * 1000
    plans = courses.all_courses(school)
    asg = assignments(school)
    subs, rt = SUB.load(school), ratings(school)
    db = accounts(school)
    by_sid = {a.get("sid"): a for a in db.values() if a.get("sid")}
    cls = class_table(school)
    out, notes = [], []
    for m in moves:
        sid = m["sid"]
        a = by_sid.get(sid) or {}
        subj = a.get("subjects")
        hw = (blob_of(school, sid) or {}).get("hw") or {}

        def takes(p, cid):
            return (not p.get("students") and cid in (p.get("classes") or [])
                    and (not subj or p.get("subject") in subj))
        for aid, x in sorted(asg.items()):
            if int(x.get("dueAt") or 0) <= nowms:
                continue                            # 期限の過ぎた宿題は書き換えない
            key = (x.get("lesson") or {}).get("key") or ""
            p = plans.get(key)
            if not p or p.get("students"):
                continue                            # 指名のコースはクラス替えと関係しない
            before, after = takes(p, m["from"][0]), takes(p, m["to"][0])
            studs = x.get("students") or []
            if sid in studs and before and not after:
                out.append((aid, sid, "keep" if _has_record(subs, rt, hw, aid, sid) else "out", key))
            elif sid not in studs and after and not before:
                if x.get("extra") or x.get("personal") or x.get("quiz") or (x.get("lesson") or {}).get("quiz"):
                    continue                        # 上乗せ・個別・提出箱は、その時の生徒に向けたもの
                out.append((aid, sid, "in", key))
        # 前のコースに残るもの（個別の決まり・上位の指名）。移った先では効かない。戻れば また効く
        for key, p in sorted(plans.items()):
            if not (takes(p, m["from"][0]) and not takes(p, m["to"][0])):
                continue
            if PERSONAL.rules_of(school, key).get(sid):
                notes.append("  %s（%s）: %s の個別の決まりが残っています（移った先では効きません。戻れば また効きます）"
                             % (m["id"], _class_label(cls, *m["to"]), p.get("name") or key))
            if any(sid in (ex.get("students") or []) for ex in p.get("extra") or []):
                notes.append("  %s（%s）: %s の上位に選ばれたままです（移った先では効きません）"
                             % (m["id"], _class_label(cls, *m["to"]), p.get("name") or key))
    return out, notes


def move_apply(school, plan, batch, now=None):
    """計画どおりに書く。書く前の accounts.json と assignments.json を控えに置く。"""
    now = int(now or time.time())
    with LOCK:
        for name in ("accounts.json", "assignments.json"):
            src = paths.school_file(school, name)
            if os.path.exists(src):
                dst = paths.backup_path(school, batch, name)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with io.open(src, "rb") as fi, io.open(dst, "wb") as fo:
                    fo.write(fi.read())
        db = accounts(school)
        for m in plan["moves"]:
            acc = db[m["id"]]
            acc.setdefault("moves", []).append({
                "at": now, "batch": batch,
                "from": {"classId": m["from"][0], "seat": m["from"][1]},
                "to": {"classId": m["to"][0], "seat": m["to"][1]}})
            acc["classId"], acc["seat"] = m["to"]
        save_accounts(school, db)
        if plan["transfers"]:
            asg = assignments(school)
            for aid, sid, op, _key in plan["transfers"]:
                x = asg.get(aid)
                if not x or op == "keep":
                    continue
                st = x.setdefault("students", [])
                if op == "out" and sid in st:
                    st.remove(sid)
                elif op == "in" and sid not in st:
                    st.append(sid)
                else:
                    continue
                x.setdefault("moved", []).append({"sid": sid, "op": op, "batch": batch, "at": now})
            save_assignments(school, asg)
    for m in plan["moves"]:
        audit(school, "cli", "move", m["sid"], "%s/%s→%s/%s %s" % (m["from"] + m["to"] + (batch,)))
    paths.prune_backups(school)


def move_batches(school):
    """これまでのクラス替え。{番号: {"at", "n", "undone"}}"""
    out = {}
    for a in accounts(school).values():
        for m in a.get("moves") or []:
            b = out.setdefault(m.get("batch") or "?", {"at": m.get("at") or 0, "n": 0})
            b["n"] += 1
            b["at"] = min(b["at"], m.get("at") or 0)
    return out


def move_undo(school, batch, apply=False):
    """そのクラス替えを取り消す。返す (戻す人数, まちがい, 知らせ)。

    戻せるのは「そのあと別のクラス替えで動いていない」生徒だけ（動いていたら、先に新しい方を取り消す）。
    足した宿題は、そこに記録が付いていたら外さない（生徒の仕事を消さない）。"""
    db = accounts(school)
    cls = class_table(school)
    back, errors, notes = [], [], []
    for lid, a in sorted(db.items()):
        ms = a.get("moves") or []
        mine = [m for m in ms if m.get("batch") == batch]
        if not mine:
            continue
        m = mine[-1]
        to, fr = m.get("to") or {}, m.get("from") or {}
        if ms[-1] is not m or (a.get("classId"), seat_of(a)) != (to.get("classId"), to.get("seat")):
            errors.append("  %s: このあと別のクラス替えで動いています。新しい方から取り消してください" % lid)
            continue
        back.append((lid, (fr.get("classId"), fr.get("seat"))))
    if not back and not errors:
        errors.append("  その番号のクラス替えはありません: %s" % batch)
    to_of = dict(back)
    after = {}
    for lid, a in db.items():
        if a.get("role") != "student" or a.get("leftAt"):
            continue
        pos = to_of.get(lid) or (a.get("classId") or "", seat_of(a))
        after.setdefault(pos, []).append(lid)
    for pos, ids in sorted(after.items()):
        if len(ids) > 1:
            errors.append("  戻すと %s に %d人が重なります: %s" % (_class_label(cls, *pos), len(ids), ", ".join(sorted(ids))))
    if errors or not apply:
        return len(back), errors, notes
    asg = assignments(school)
    subs, rt = SUB.load(school), ratings(school)
    with LOCK:
        for name in ("accounts.json", "assignments.json"):
            src = paths.school_file(school, name)
            if os.path.exists(src):
                dst = paths.backup_path(school, "undo-" + batch, name)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with io.open(src, "rb") as fi, io.open(dst, "wb") as fo:
                    fo.write(fi.read())
        db = accounts(school)
        for lid, (cid, seat) in back:
            acc = db[lid]
            acc["classId"], acc["seat"] = cid, seat
            acc["moves"] = [m for m in acc.get("moves") or [] if m.get("batch") != batch]
            if not acc["moves"]:
                acc.pop("moves")
        save_accounts(school, db)
        touched = False
        for aid, x in asg.items():
            ent = [e for e in x.get("moved") or [] if e.get("batch") == batch]
            if not ent:
                continue
            st = x.setdefault("students", [])
            for e in ent:
                sid = e.get("sid")
                if e.get("op") == "out" and sid not in st:
                    st.append(sid)
                elif e.get("op") == "in" and sid in st:
                    hw = (blob_of(school, sid) or {}).get("hw") or {}
                    if _has_record(subs, rt, hw, aid, sid):
                        notes.append("  %s: 足した宿題 %s に記録があるので、受け取り手に残しました" % (sid, aid))
                        continue
                    st.remove(sid)
            x["moved"] = [e for e in x.get("moved") or [] if e.get("batch") != batch]
            if not x["moved"]:
                x.pop("moved")
            touched = True
        if touched:
            save_assignments(school, asg)
    for lid, _pos in back:
        audit(school, "cli", "move_undo", lid, batch)
    return len(back), errors, notes


def cmd_move(args):
    """クラス替え。確かめる → --yes で移す → 取り消すなら --undo。"""
    school = args.school
    cls = class_table(school)
    if args.list:
        bs = move_batches(school)
        if not bs:
            print("クラス替えの記録はありません。")
        for b, v in sorted(bs.items(), key=lambda kv: kv[1]["at"]):
            print("  %s  %s  %d名" % (b, time.strftime("%Y-%m-%d %H:%M", time.localtime(v["at"])), v["n"]))
        return 0
    if args.undo:
        n, errors, notes = move_undo(school, args.undo, apply=args.yes)
        if errors:
            print("× 取り消せません（何も変えていません）")
            print("\n".join(errors[:30]))
            return 1
        if not args.yes:
            print("%s を取り消すと、%d名が前のクラスと席に戻ります。宿題の付け替えも戻します。" % (args.undo, n))
            print("\n実行するには --yes を付けてください。")
            return 0
        print("取り消しました: %s（%d名）" % (args.undo, n))
        if notes:
            print("\n".join(notes))
        return 0
    if not args.file:
        print("CSV を指定してください（列は id,classId,seat）。一覧は --list、取り消しは --undo <番号>。")
        return 1
    try:
        rows, bad = move_rows(school, args.file)
    except ValueError as e:
        print("× %s" % e)
        return 1
    if bad:
        print("× 直してから入れ直してください（何も変えていません）")
        print("\n".join(bad[:30]))
        return 1
    now = time.time()
    plan, errors = move_plan(school, rows, now, transfer=not args.keep_homework)
    if errors:
        print("× 直してから入れ直してください（何も変えていません）")
        print("\n".join(errors[:30]))
        return 1
    if not plan["moves"]:
        print("移る生徒はいません（%d名は今と同じクラスと席です）。" % plan["same"])
        return 0
    tr = {}
    for aid, sid, op, key in plan["transfers"]:
        tr.setdefault(sid, {"out": 0, "in": 0, "keep": 0})[op] += 1
    print("校舎 %s（%s）：クラス替え %d名（今と同じ %d名）" % (school, school_name(school), len(plan["moves"]), plan["same"]))
    for m in plan["moves"]:
        t = tr.get(m["sid"]) or {"out": 0, "in": 0, "keep": 0}
        what = []
        if t["out"]:
            what.append("前のクラスの宿題から外す %d件" % t["out"])
        if t["in"]:
            what.append("新しいクラスの宿題に足す %d件" % t["in"])
        if t["keep"]:
            what.append("記録があるので残す %d件" % t["keep"])
        print("  %-10s %s → %s   %s" % (m["id"], _class_label(cls, *m["from"]), _class_label(cls, *m["to"]),
                                        "・".join(what) or "宿題の付け替えなし"))
    if plan["notes"]:
        print("\n知っておくこと（そのまま残ります）")
        print("\n".join(plan["notes"][:40]))
    if not args.yes:
        print("\n実行するには --yes を付けてください。ログインID・パスワード・記録は変わりません。")
        return 0
    batch = "m" + time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    move_apply(school, plan, batch, now)
    print("\n移しました。番号: %s" % batch)
    print("  取り消すなら: python3 server/tube_server.py move --undo %s --school %s --yes" % (batch, school))
    print("  先生の手元の対応表（roster-tool/対応表.html）にも、同じ CSV を「クラス替え」に貼ってください。")
    return 0


# ------------------------------------------------------------------
# 在籍終了と、その後の削除
#
# UK GDPR 5条(1)(e)（保存期間の制限）。必要な期間を過ぎたら消す。
# 本システムの方針は **退塾から6か月**。
#
# 2段階にしてあるのは、間違いを取り返せるようにするため。
#   1. archive … ログインを止める。記録は残る（誤操作なら戻せる）
#   2. purge   … 6か月たった記録を実際に消す（戻せない）
#
# 即時削除にしないのは、退塾の登録を打ち間違えたときに
# その生徒の記録が永久に失われるのを避けるため。
# ------------------------------------------------------------------
RETENTION_DAYS = 183          # 退塾から6か月


def cmd_archive(args):
    """生徒の在籍を終える。ログインは止まるが、記録は残る。"""
    school = args.school
    db = accounts(school)
    acc = db.get(args.id)
    if not acc:
        print("そのIDはありません: %s" % args.id)
        return 1
    if acc.get("role") != "student":
        print("生徒のアカウントではありません: %s" % args.id)
        return 1
    if acc.get("leftAt") and not args.undo:
        print("すでに在籍終了です: %s（%s）"
              % (args.id, time.strftime("%Y-%m-%d", time.localtime(acc["leftAt"]))))
        return 0
    with LOCK:
        db = accounts(school)
        if args.undo:
            db[args.id].pop("leftAt", None)
            save_accounts(school, db)
            print("在籍終了を取り消しました: %s" % args.id)
        else:
            db[args.id]["leftAt"] = int(time.time())
            save_accounts(school, db)
            # 合言葉を無効にする。以後ログインできない。
            store = tokens()
            for t in [t for t, r in store.items() if r["loginId"] == args.id]:
                store.pop(t)
            save_tokens(store)
            when = time.time() + RETENTION_DAYS * 86400
            print("在籍終了にしました: %s" % args.id)
            print("  ログインは止まりました。記録は残っています。")
            print("  %s に削除の対象になります（退塾から6か月）。"
                  % time.strftime("%Y-%m-%d", time.localtime(when)))
            print("  取り消すなら: archive %s --undo --school %s" % (args.id, school))
    audit(school, "cli", "archive" if not args.undo else "unarchive", args.id)
    return 0


def cmd_purge(args):
    """退塾から6か月を過ぎた記録を消す。**戻せない。**"""
    school = args.school
    now = time.time()
    cutoff = now - RETENTION_DAYS * 86400
    db = accounts(school)
    due = []
    for lid, a in sorted(db.items()):
        left = a.get("leftAt")
        if a.get("role") == "student" and left and left <= cutoff:
            days = int((now - left) / 86400)
            due.append((lid, a, days))

    if not due:
        n_left = len([1 for a in db.values() if a.get("leftAt")])
        print("削除の対象はありません。")
        if n_left:
            print("  在籍終了 %d名。いずれも退塾から6か月に達していません。" % n_left)
        return 0

    print("退塾から6か月を過ぎた記録が %d件あります。\n" % len(due))
    print("  %-10s %-8s %-8s %s" % ("ID", "クラス", "経過", "記録"))
    print("  " + "-" * 46)
    for lid, a, days in due:
        rec = paths.load(progress_path(school, a["sid"]), None) or {}
        n = len((rec.get("blob") or {}).get("cards") or {})
        print("  %-10s %-8s %4d日 %6d項目" % (lid, a.get("classId",""), days, n))

    if not args.yes:
        print("\n実際に消すには --yes を付けてください。**戻せません。**")
        return 0

    gone = 0
    with LOCK:
        db = accounts(school)
        for lid, _a, _d in due:
            a = db.get(lid)
            if not a:
                continue
            # 消す中身は、3か月使われない口座の破棄と同じ1か所（retire.erase）。答案の写真・評価・点・
            # 特筆事項・連絡・宿題の受け取り手・入ったままの印まで。
            RETIRE.erase(sys.modules[__name__], school, lid, a, db)
            gone += 1
        save_accounts(school, db)
    audit(school, "cli", "purge", "", "%d件" % gone)
    print("\n%d件を削除しました。" % gone)
    print("  監査記録（audit.log）には「消した事実」だけが残ります。")
    print("  ★ バックアップにはまだ残っています。S3の保持期間（30日）を過ぎると消えます。")
    return 0


def cmd_prune_photos(args):
    """古い答案の写真を消す（台帳の評価・ひとことは残す）。月に1度、運営が流す。"""
    school = args.school
    r = SUB.prune(school, days=args.days, dry=args.dry)
    print("校舎 %s（%s）：%d日より前の写真 %s" % (school, school_name(school), args.days,
                                              "（数えるだけ）" if args.dry else ""))
    print("  対象の行    %d件（出した記録・評価・ひとことは残る）" % r["rows"])
    print("  消した写真  %d枚" % r["files"] if not args.dry else "  消す写真    %d枚" % r["files"])
    if not args.dry:
        audit(school, "cli", "prune_photos", "", "%d日 %d件 %d枚" % (args.days, r["rows"], r["files"]))


def cmd_retention(args):
    """保持期間の状況を一覧する。DPIA の裏づけとして出せる形にする。"""
    school = args.school
    now = time.time()
    db = accounts(school)
    active = [a for a in db.values() if a.get("role") == "student" and not a.get("leftAt")]
    left = [(lid, a) for lid, a in db.items()
            if a.get("role") == "student" and a.get("leftAt")]
    due = [x for x in left if now - x[1]["leftAt"] > RETENTION_DAYS * 86400]

    print("校舎 %s（%s）の保持状況\n" % (school, school_name(school)))
    print("  方針      退塾から6か月（%d日）で削除" % RETENTION_DAYS)
    print("  在籍中    %d名" % len(active))
    print("  在籍終了  %d名" % len(left))
    print("  削除対象  %d名" % len(due))
    if left:
        print("\n  %-10s %-8s %-12s %s" % ("ID", "クラス", "退塾", "削除予定"))
        print("  " + "-" * 48)
        for lid, a in sorted(left, key=lambda x: x[1]["leftAt"]):
            t = a["leftAt"]
            when = t + RETENTION_DAYS * 86400
            mark = " ← 対象" if now > when else ""
            print("  %-10s %-8s %-12s %s%s"
                  % (lid, a.get("classId", ""),
                     time.strftime("%Y-%m-%d", time.localtime(t)),
                     time.strftime("%Y-%m-%d", time.localtime(when)), mark))
    if due:
        print("\n  消すには: python3 server/tube_server.py purge --school %s --yes" % school)
    return 0


def cmd_import_reference(args):
    """本部カリキュラムを取り込む。全校舎で共通の基準になる。"""
    try:
        data = refcur.import_csv(args.grade, args.file, name=args.name,
                                 source=args.source or "本部カリキュラム")
    except IOError as e:
        print("読めません: %s" % e)
        return 1
    n = sum(len(w.get("units") or []) for w in data["weeks"])
    print("取り込みました: %s（%s）" % (args.grade, data["name"]))
    print("  %d週 / %d単元" % (len(data["weeks"]), n))
    print("  %s" % refcur.reference_path(args.grade))
    print("\n  これは **全校舎の共通の基準** になります。")
    print("  各校舎の実施状況との差は、講師画面の「進度」に出ます。")
    return 0


def cmd_reference(args):
    refs = refcur.list_references()
    if not refs:
        print("本部カリキュラムはまだ入っていません。")
        print("  python3 server/tube_server.py import-reference j1 表.csv --name 中1")
        print("\n  列は week,from,subject,unit の4つ。")
        print("  Excel から「CSV（UTF-8）」で書き出せばこの形になります。")
        return 0
    print("本部カリキュラム（%s）\n" % os.path.join(paths.SHARED, "curriculum"))
    for g in refs:
        ref = refcur.load_reference(g)
        n = sum(len(w.get("units") or []) for w in (ref.get("weeks") or []))
        print("  %-6s %-8s %2d週 / %3d単元" % (g, ref.get("name",""),
                                              len(ref.get("weeks") or []), n))
    return 0


def cmd_syllabus_import(args):
    """教材の単元の並び（シラバス）を JSON から取り込む。同じ id は置き換える（仮置きより優先）。

    **形が崩れていたら置かない。** 崩れたシラバスを置くと、そのコースの予定が組めなくなる。
    """
    try:
        with open(args.file, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        print("読めません:", e)
        return 1
    errs = SYLLABUS.problems(d)
    if errs:
        print("取り込めません（形の誤り）:")
        for e in errs:
            print("  -", e)
        return 1
    SYLLABUS.save(d)
    print("取り込みました: %s（%s） 単元 %d  %s" % (d["id"], d.get("name", ""), len(d["units"]),
          "仮置き" if d.get("provisional") else "本物"))
    return 0


def cmd_syllabus(args):
    """シラバスの一覧と形の検査（取り込んだもの・原本・仮置き）。"""
    ids = set(SYLLABUS.seeds())
    print("  原本: %s（%s）" % (SOURCE.PATH, "読めます" if SOURCE.load() else "**読めません**"))
    d = os.path.join(paths.SHARED, "syllabus")
    if os.path.isdir(d):
        ids |= {f[:-5] for f in os.listdir(d) if f.endswith(".json")}
    bad = 0
    for sid in sorted(ids):
        got = SYLLABUS.load(sid)
        if not got:
            bad += 1
            print("  × %s（形が崩れていて使えません）" % sid)
            continue
        print("  %-20s %-16s 単元 %2d  起点 %s（%s の週）  %s" % (
            sid, got.get("name", ""), len(got["units"]), got["anchor"]["unit"], got["anchor"]["week"],
            "仮置き" if got.get("provisional") else ("原本" if SOURCE.syllabus(sid) else "本物")))
    return 1 if bad else 0


def cmd_drift(args):
    """いまのズレを表示する。講師画面に出るのと同じ計算。"""
    cur = curriculum(args.school)
    plans = cur.get("plans") or {}
    grades = sorted({g.get("id") for g in (cur.get("grades") or []) if g.get("id")}
                    or {k.split(":")[0] for k in plans})
    if not grades:
        print("学年がありません。")
        return 0
    print("校舎 %s（%s）の、本部カリキュラムとのズレ\n" % (args.school, school_name(args.school)))
    for g in grades:
        d = refcur.drift(g, plans)
        if d["status"] != "ok":
            print("  %-5s 判定できません ―― %s" % (g, d.get("message","")))
            continue
        sign = "進み" if d["weeks"] > 0 else ("遅れ" if d["weeks"] < 0 else "予定どおり")
        print("  %-5s 第%d週  実施は第%d週まで  %s%s"
              % (g, d["week"], d["reached"], sign,
                 "" if d["weeks"] == 0 else " %d週" % abs(d["weeks"])))
        for u in d["missing"][:6]:
            print("        未実施: %s / %s" % (u["subject"], u["unit"]))
        if len(d["missing"]) > 6:
            print("        ほか %d単元" % (len(d["missing"]) - 6))
    return 0


def cmd_fix_curriculum(args):
    """保存済みの進度が、消えた教材を指していないか調べて直す。

    教材の名前を変えたり作り直したりすると、講師が保存した進度は
    古い名前を指したまま残る。**エラーは出ない。**
    その学年・その教科の生徒の画面が、ただ空になるだけである。
    実際に、教材を学年ごとに作り直したときに6件が切れた。

    app/content/manifest.js にある教材IDと突き合わせ、
    無いものを --map で指定した対応に置き換える。
    """
    school = args.school
    man = os.path.join(APP_DIR, "content", "manifest.js")
    try:
        with open(man, encoding="utf-8") as f:
            src = f.read()
    except IOError:
        print("目録が読めません: %s" % man)
        return 1
    known = set(re.findall(r"id:'([\w/\-]+)'", src))

    mapping = {}
    for pair in (args.map or "").split(","):
        if ":" in pair:
            old, new = pair.split(":", 1)
            mapping[old.strip()] = new.strip()

    # 教材ごとの帯も読む。教材を差し替えると帯の名前も変わることがあり、
    # **packs だけ直しても出題されない**（帯が1つも一致しないため、
    # 対象の項目が0件になる）。実際にこれで「カードは出るが0問」になった。
    pack_bands = {}
    for m in re.finditer(r"id:'([\w/\-]+)'.*?bands:\[([^\]]*)\]", src, re.S):
        pack_bands[m.group(1)] = re.findall(r"'([^']+)'", m.group(2))

    cur = curriculum(school)
    plans = cur.get("plans") or {}
    broken, fixed, rebanded = [], [], []
    for key, plan in plans.items():
        packs = plan.get("packs") or []
        out = []
        for pid in packs:
            if pid in known:
                out.append(pid)
                continue
            # 対応表にあればそれを、無ければ「同じ科目で学年が合うもの」を探す
            new = mapping.get(pid)
            if not new:
                grade = key.split(":")[0]
                subject = pid.split("/")[0]
                cands = [k for k in known
                         if k.startswith(subject + "/") and grade in k]
                new = cands[0] if len(cands) == 1 else None
            if new:
                out.append(new)
                fixed.append((key, pid, new))
            else:
                broken.append((key, pid))
        plan["packs"] = out

        # 帯の突き合わせ。1つも一致しないなら、その教材の帯に置き換える。
        want = set(plan.get("bands") or [])
        have = set()
        for pid in out:
            have |= set(pack_bands.get(pid) or [])
        if want and have and not (want & have):
            plan["bands"] = sorted(have)
            rebanded.append((key, sorted(want), sorted(have)))

    if not fixed and not broken and not rebanded:
        print("校舎 %s の進度に、切れている参照はありません。" % school)
        return 0

    for key, old, new in fixed:
        print("  %-14s %s → %s" % (key, old, new))
    for key, old in broken:
        print("  %-14s %s → 対応先が決められません（--map で指定してください）" % (key, old))
    for key, was, now in rebanded:
        print("  %-14s 帯 %s → %s" % (key, "・".join(was), "・".join(now)))

    if not args.yes:
        print("\n実際に直すには --yes を付けてください。")
        return 0
    cur["plans"] = plans
    save_curriculum(school, cur)
    print("\n直しました（教材 %d件 / 帯 %d件）。生徒は次に開いたときから出題されます。"
          % (len(fixed), len(rebanded)))
    return 1 if broken else 0


def cmd_rebuild_summary(args):
    """要約（summary/）を progress から作り直す。

    要約は派生データなので、いつでもこれで復旧できる。
    移行の直後と、要約の作りを変えたあとに走らせる。"""
    school = args.school
    db = accounts(school)
    asg = list(assignments(school).values())
    rdb = ratings(school)
    # 作り直しは**そろってから見せる**。別の名前で作って、最後に置き換える。
    d = paths.summary_dir(school)
    tmp = d + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    n = 0
    cache = hw_cache()
    for a in db.values():
        if a["role"] != "student":
            continue
        sid = a["sid"]
        rec = paths.load(progress_path(school, sid), None) or {}
        mine = [x for x in asg if sid in students_for(school, x, cache)]
        paths.save(os.path.join(tmp, paths.check_sid(sid) + ".json"),
                   summarise_one(rec.get("blob") or {}, mine,
                                 rated=ratings_for_student(school, sid, rdb)))
        n += 1
    shutil.rmtree(d, ignore_errors=True)
    os.rename(tmp, d)
    _SUMM.pop(school, None)
    print("要約を作り直しました: %s（%d名）" % (school, n))


def main():
    ap = argparse.ArgumentParser(description="Tube for Schools 仮サーバ")
    sub = ap.add_subparsers(dest="cmd")

    def school_arg(p):
        p.add_argument("--school", default=DEFAULT_SCHOOL,
                       help="対象の校舎ID（既定 %s）。環境変数 MYACADY_SCHOOL でも指定できる"
                            % DEFAULT_SCHOOL)
        return p

    p = sub.add_parser("schools", help="校舎の一覧")
    p.add_argument("--real-count", dest="real_count", action="store_true",
                   help="本物の校舎（デモでないもの）の数だけを出す")
    p.set_defaults(fn=cmd_schools)

    p = school_arg(sub.add_parser("school-trial", help="試し運用の印（付いているあいだ、ふつうの入口に「ためしに見る」を出す）"))
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--on", action="store_true")
    g.add_argument("--off", action="store_true")
    p.set_defaults(fn=cmd_school_trial)

    p = sub.add_parser("demo-swap", help="別の置き場で作り終えたデモの校舎を、サーバを止めずに入れ替える")
    p.add_argument("--from", dest="src", required=True, help="作り終えた置き場（同じディスクの上）")
    p.add_argument("--school", default=DEFAULT_SCHOOL)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(fn=cmd_demo_swap)

    p = school_arg(sub.add_parser("go-live", help="本番に切り替える：試し運用の生徒を退避して名簿を空にする（講師・コース・授業計画は残す）"))
    p.add_argument("--yes", action="store_true")
    p.add_argument("--again", action="store_true", help="切り替えずみの校舎を、もう一度まっさらにする")
    p.set_defaults(fn=cmd_go_live)

    p = sub.add_parser("bundle-import", help="手元で作った席・講師・管理者の束を入れる（ハッシュだけ）")
    p.add_argument("file")
    p.add_argument("--yes", action="store_true", help="確かめたうえで入れる")
    p.set_defaults(fn=cmd_bundle_import)

    p = sub.add_parser("school-add", help="校舎を作る")
    p.add_argument("id", help="英小文字の短い名前（london / ny / tokyo）")
    p.add_argument("name", help="画面に出す名前（ロンドン校 など）")
    p.add_argument("--tz", default="Europe/London", help="時間帯（Asia/Tokyo など）")
    p.add_argument("--code", help="ログインIDの頭に付く1〜2文字（既定はIDの頭文字）")
    p.set_defaults(fn=cmd_school_add)

    p = school_arg(sub.add_parser("archive", help="生徒の在籍を終える（記録は残す）"))
    p.add_argument("id")
    p.add_argument("--undo", action="store_true", help="在籍終了を取り消す")
    p.set_defaults(fn=cmd_archive)

    p = school_arg(sub.add_parser("prune-photos", help="古い答案の写真を消す（台帳の評価・ひとことは残す）"))
    p.add_argument("--days", type=int, default=SUB.KEEP_DAYS, help="この日数より前に出した写真を消す（既定 %d）" % SUB.KEEP_DAYS)
    p.add_argument("--dry", action="store_true", help="消さずに数だけ")
    p.set_defaults(fn=cmd_prune_photos)
    p = school_arg(sub.add_parser("retention", help="保持期間の状況を一覧する"))
    p.set_defaults(fn=cmd_retention)

    p = sub.add_parser("housekeep", help="毎日の片づけを今すぐ1回（3か月使われない口座の破棄。--dry で見るだけ）")
    p.add_argument("--dry", action="store_true")
    p.set_defaults(fn=cmd_housekeep)

    p = school_arg(sub.add_parser("purge", help="退塾から6か月を過ぎた記録を消す"))
    p.add_argument("--yes", action="store_true", help="実際に消す（戻せない）")
    p.set_defaults(fn=cmd_purge)

    p = sub.add_parser("import-reference", help="本部カリキュラムをCSVから取り込む")
    p.add_argument("grade", help="学年ID（e4 / j1 など）")
    p.add_argument("file", help="列は week,from,subject,unit")
    p.add_argument("--name", help="画面に出す名前（中1 など）")
    p.add_argument("--source", help="出どころ（既定「本部カリキュラム」）")
    p.set_defaults(fn=cmd_import_reference)

    p = sub.add_parser("reference", help="取り込んである本部カリキュラムの一覧")
    p.set_defaults(fn=cmd_reference)

    p = sub.add_parser("syllabus-import", help="教材の単元の並び（シラバス）をJSONから取り込む（同じidは置き換え）")
    p.add_argument("file", help="server/syllabus/ の仮置きと同じ形の JSON")
    p.set_defaults(fn=cmd_syllabus_import)

    p = sub.add_parser("syllabus", help="シラバスの一覧と形の検査")
    p.set_defaults(fn=cmd_syllabus)

    p = school_arg(sub.add_parser("drift", help="本部カリキュラムとのズレを表示する"))
    p.set_defaults(fn=cmd_drift)

    p = school_arg(sub.add_parser("fix-curriculum",
                                  help="進度が指す教材が消えていないか調べて直す"))
    p.add_argument("--map", help="対応を明示する。例 science/j1:science/j1n,social/j1-geo:social/j1s")
    p.add_argument("--yes", action="store_true", help="実際に直す")
    p.set_defaults(fn=cmd_fix_curriculum)

    p = school_arg(sub.add_parser("rebuild-summary", help="講師画面むけの要約を作り直す"))
    p.set_defaults(fn=cmd_rebuild_summary)

    p = school_arg(sub.add_parser("roster-import", help="名簿をCSVから一括登録する"))
    p.add_argument("file", help="列は classId,seat のみ。氏名の列は作らない")
    p.add_argument("--out", help="IDとパスワードの書き出し先。既定は roster-<校舎>-<日時>.csv")
    p.add_argument("--yes", action="store_true", help="実際に登録する")
    p.set_defaults(fn=cmd_roster_import)

    p = school_arg(sub.add_parser("move", help="クラス替え（組み分けのあと。記録はそのまま、クラスと席だけ移す）"))
    p.add_argument("file", nargs="?", help="列は id,classId,seat（id はログインID）か fromClass,fromSeat,classId,seat。氏名の列は作らない")
    p.add_argument("--yes", action="store_true", help="実際に移す（付けなければ確かめるだけ）")
    p.add_argument("--keep-homework", action="store_true", help="まだ期限の来ていない宿題の受け取り手を付け替えない")
    p.add_argument("--list", action="store_true", help="これまでのクラス替えの一覧（番号）")
    p.add_argument("--undo", metavar="番号", help="そのクラス替えを取り消す（--yes で実行）")
    p.set_defaults(fn=cmd_move)

    p = school_arg(sub.add_parser("courses-import",
                                  help="コースをCSVから入れる（授業の追加・講習も）"))
    p.add_argument("file", help="列は id,教科,名前,学年,講師,時間,クラス,指名,単位,期間")
    p.add_argument("--yes", action="store_true", help="実際に入れる")
    p.set_defaults(fn=cmd_courses_import)

    p = school_arg(sub.add_parser("courses-slots",
                                  help="時間割の時間だけを入れる（講師・指名・授業計画には触らない）"))
    p.add_argument("file", help="列は id,教科,名前,学年,時間,クラス（カリキュラム/コマ.csv）")
    p.add_argument("--yes", action="store_true", help="実際に入れる")
    p.set_defaults(fn=cmd_courses_slots)

    p = school_arg(sub.add_parser("courses-teachers",
                                  help="担当の講師だけを入れる（時間・指名・授業計画には触らない）"))
    p.add_argument("file", help="列は id,教科,講師（カリキュラム/担当.csv。講師はログインID）")
    p.add_argument("--yes", action="store_true", help="実際に入れる")
    p.set_defaults(fn=cmd_courses_teachers)

    p = school_arg(sub.add_parser("courses-export", help="コースをCSVに出す"))
    p.add_argument("--out", help="書き出し先。既定は courses-<校舎>-<日時>.csv")
    p.set_defaults(fn=cmd_courses_export)

    p = sub.add_parser("serve", help="サーバを起動する")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1",
                   help="既定はこのMacの中だけ。LANに開くなら 0.0.0.0")
    p.add_argument("--demo", action="store_true",
                   help="ログイン画面にデモ用の入室ボタンを出す（本番では付けない）")
    p.add_argument("--demo-file", dest="demo_file",
                   help="デモ用アカウントの一覧。既定は data/demo-accounts.json")
    p.set_defaults(fn=cmd_serve)

    p = school_arg(sub.add_parser("seed", help="テスト用アカウントを一括で作る"))
    p.add_argument("--reset", action="store_true", help="その校舎のデータを消してから作る")
    p.add_argument("--empty", action="store_true",
                   help="校舎だけ作り、検査用のアカウントは作らない（デモの作り直しで使う）")
    p.add_argument("--name", help="校舎の表示名（初回だけ使う）")
    p.set_defaults(fn=cmd_seed)

    p = school_arg(sub.add_parser("add", help="アカウントを1つ足す"))
    p.add_argument("id")
    p.add_argument("seat", help="出席番号（例 07）。氏名は保存しない")
    p.add_argument("--password")
    p.add_argument("--level", default="j2")
    p.add_argument("--class", dest="klass", default="j2a")
    p.add_argument("--teacher", action="store_true")
    p.add_argument("--admin", action="store_true",
                   help="管理者（/admin から入る。席・講師・担当を作り変えられる）")
    p.add_argument("--classes", help="講師の担当クラス。カンマ区切り（例 j1a,j2a）")
    p.add_argument("--assign",
                   help="講師の担当。「クラス:教科:曜日:時限」をカンマ区切り。"
                        "曜日と時限は省ける。"
                        "例 j1r:math:月:1,j2r:math:月:2,e5:science:水:1")
    p.set_defaults(fn=cmd_add)

    p = school_arg(sub.add_parser("list", help="アカウントと進捗の一覧"))
    p.add_argument("--csv", action="store_true")
    p.set_defaults(fn=cmd_list)

    p = school_arg(sub.add_parser("passwd", help="パスワードを付け替える"))
    p.add_argument("id", nargs="?")
    p.add_argument("password", nargs="?")
    p.add_argument("--all", action="store_true",
                   help="全員ぶんを作り直して一覧表示（外に出す前に一度）")
    p.set_defaults(fn=cmd_passwd)

    p = school_arg(sub.add_parser("rm", help="アカウントを消す"))
    p.add_argument("id")
    p.add_argument("--purge", action="store_true", help="進捗も消す")
    p.set_defaults(fn=cmd_rm)

    p = school_arg(sub.add_parser("anonymise", help="古いアカウントから氏名を消して出席番号にする"))
    p.add_argument("--yes", action="store_true", help="対応表を控えたうえで実行する")
    p.set_defaults(fn=cmd_anonymise)

    p = school_arg(sub.add_parser("hw", help="宿題を出す・見る・取り消す"))
    hw = p.add_subparsers(dest="hwcmd")

    q = hw.add_parser("add", help="宿題を出す")
    q.add_argument("title", help='例: "My英単語帳 No.1000-1050"')
    q.add_argument("--source", default="myvocab", help="教材ID（curriculum.js の sources）")
    q.add_argument("--from", dest="lo", type=int, required=True)
    q.add_argument("--to", dest="hi", type=int, required=True)
    q.add_argument("--class", dest="klass", help="クラス一括のとき")
    q.add_argument("--students", help="個別に出すとき。IDをカンマ区切り（例 j2a01,j2a03）")
    q.add_argument("--due", required=True, help="2026-08-07 の形")
    q.add_argument("--note", help="ひとこと")

    q = hw.add_parser("list", help="宿題と達成状況")
    q = hw.add_parser("rm", help="宿題を取り消す")
    q.add_argument("id")
    p.set_defaults(fn=cmd_hw)

    args = ap.parse_args()
    if not getattr(args, "fn", None):
        ap.print_help()
        return 0
    # **サーバが動いている横で流してよいように、コマンドも同じ鍵を持つ。**
    # 鍵は重ねて入れるので、中の関数が自分で取っても固まらない。
    # 長く動くもの（serve）と、1件ごとに自分で鍵を取るもの（合言葉のハッシュを何百件も
    # 計算する seed・roster-import・bundle-import）は、全体では持たない ―― 持つと、その間
    # サーバの書き込みが全部止まる。
    if args.cmd in ("serve", "seed", "roster-import", "bundle-import", "demo-swap", "passwd", "schools", "list",
                    "reference", "syllabus", "drift", "courses-export"):
        return args.fn(args) or 0
    with LOCK:
        return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
