#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""規模の監査 ―― 実データの量で本当に動くかを、測って確かめる。

    python3 app/tools/規模の監査.py            # 既定 2000名
    python3 app/tools/規模の監査.py 500        # 名数を変える

なぜ読むだけで済ませないか
--------------------------
「重そう」は当てにならない。**実際に大きくして測る。**
デモは168名・教材5千項目で軽々と動くが、本番はその10倍以上になる。
その差は読んでいるだけでは見えない。

ここで作るのは架空の校舎（scale-test）で、london には一切触らない。
測り終えたら消す。
"""

import io
import json
import os
import random
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "server"))

N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
SCHOOL = "scaletest"

# 測る前に、保管先を使い捨ての場所へ向ける。**本物のデータに触らない。**
TMP = os.path.join("/tmp", "tube-scale-%d" % os.getpid())
os.environ["MYACADY_ROOT"] = TMP

import paths                                    # noqa: E402
import tube_server as T                         # noqa: E402
import examprep                                 # noqa: E402


def ms(t):
    return "%.0fms" % (t * 1000)


def timed(fn, *a, **kw):
    t0 = time.time()
    out = fn(*a, **kw)
    return time.time() - t0, out


def sizeof(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def kb(n):
    return "%.1fKB" % (n / 1024.0)


# ------------------------------------------------------------------
def build():
    """N名の校舎を作る。形は本物と同じにする（要約・進捗・宿題）。"""
    os.makedirs(paths.school_dir(SCHOOL), exist_ok=True)
    os.makedirs(paths.progress_dir(SCHOOL), exist_ok=True)
    paths.save(paths.school_file(SCHOOL, "school.json"),
               {"name": "規模テスト", "code": "s"})

    rnd = random.Random(1)
    grades = ["e4", "e5", "e6", "j1", "j2", "j3"]
    subs = ["english", "japanese", "math", "science", "social"]

    # クラスは1学年6クラス。1クラス およそ N/36 名。
    classes = {}
    for g in grades:
        for k in range(6):
            classes["%s%d" % (g, k)] = {"grade": g, "name": "%s-%d" % (g, k)}
    paths.save(paths.school_file(SCHOOL, "roster.json"), {"classes": classes})

    db = {}
    cls_ids = sorted(classes)
    for i in range(N):
        lid = "s%05d" % i
        cid = cls_ids[i % len(cls_ids)]
        db[lid] = {"sid": "S%07d" % i, "seat": "%03d" % (i % 40),
                   "role": "student", "level": classes[cid]["grade"],
                   "classId": cid, "classes": [],
                   "alg": "scram-sha256", "salt": "0" * 32, "iters": 600000, "storedKey": "0" * 64, "serverKey": "0" * 64,
                   "created": int(time.time())}
    # 講師は40名。1人12枠。
    for t in range(40):
        pairs = []
        for k in range(12):
            pairs.append([cls_ids[(t * 12 + k) % len(cls_ids)],
                          subs[k % len(subs)], 1, 1])
        db["t%03d" % t] = {"sid": "T%07d" % t, "seat": "T%d" % t,
                           "role": "teacher", "level": "j2",
                           "classId": cls_ids[t % len(cls_ids)],
                           "classes": [], "assign": pairs,
                           "alg": "scram-sha256", "salt": "0" * 32, "iters": 600000,
                           "storedKey": "0" * 64, "serverKey": "0" * 64, "created": int(time.time())}
    paths.save(paths.school_file(SCHOOL, "accounts.json"), db)

    # 宿題。1学年1教科あたり 30回ぶん（1年ぶん）。
    now = time.time() * 1000
    asg = {}
    for cid in cls_ids:
        g = classes[cid]["grade"]
        for sub in subs:
            for n in range(1, 31):
                aid = "a-%s-%s-%02d" % (cid, sub, n)
                asg[aid] = {
                    "id": aid, "title": "%s 第%d回" % (sub, n),
                    "source": "myvocab" if sub == "english" else "keisan",
                    "from": 1, "to": 30, "classId": cid, "students": [],
                    "dueAt": int(now - (30 - n) * 7 * 86400000),
                    "kind": "hw", "route": "paper" if n % 2 else "app",
                    "lesson": {"key": "%s:%s" % (g, sub), "n": n},
                    "createdBy": "demo", "assignedAt": int(now - 30 * 86400000),
                }
    paths.save(paths.school_file(SCHOOL, "assignments.json"), asg)

    # 進捗と要約。1人 120項目・宿題30件ぶん。
    for i in range(N):
        sid = "S%07d" % i
        cards = {}
        for k in range(120):
            cards["sci:t:x%d" % k] = [rnd.choice([1, 7, 21]), 2.5, 0,
                                      rnd.randint(1, 8), rnd.randint(0, 3),
                                      int(time.time()) - k * 3600, 1]
        hw = {}
        for aid in list(asg)[:30]:
            hw[aid] = {"done": {str(v): 1 for v in range(1, 20)},
                       "startedAt": int(now), "completedAt": int(now)}
        hist = {}
        for d in range(30):
            k = time.strftime("%Y-%m-%d", time.localtime(time.time() - d * 86400))
            hist[k] = {"n": rnd.randint(5, 25), "ok": rnd.randint(3, 20),
                       "done": 1}
        blob = {"cards": cards, "hw": hw, "hist": hist,
                "grade": db["s%05d" % i]["level"],
                "classId": db["s%05d" % i]["classId"], "streak": 5}
        paths.save(paths.progress_path(SCHOOL, sid),
                   {"sid": sid, "rev": 3, "savedAt": int(now), "blob": blob})
        paths.save(paths.summary_path(SCHOOL, sid),
                   T.summarise_one(blob, [], rated={}))

    # 合言葉。1人1台＋講師。
    store = {}
    for i in range(N + 40):
        store["%064d" % i] = {"loginId": "s%05d" % i, "sid": "S%07d" % i,
                              "role": "student", "school": SCHOOL,
                              "issued": int(time.time())}
    paths.save(paths.TOKENS, store)
    return db, asg, classes


def main():
    if os.path.isdir(TMP):
        shutil.rmtree(TMP)
    print("規模の監査 ―― 生徒 %d名 で測る" % N)
    print("保管先 %s（測り終えたら消す）\n" % TMP)

    t, (db, asg, classes) = timed(build)
    print("  下ごしらえ %s" % ms(t))

    sd = paths.school_dir(SCHOOL)
    print("\n■ ファイルの大きさ")
    for name in ("accounts.json", "assignments.json"):
        print("    %-20s %10s" % (name, kb(sizeof(os.path.join(sd, name)))))
    summ = sum(sizeof(os.path.join(sd, "summary", f))
               for f in os.listdir(os.path.join(sd, "summary")))
    print("    %-20s %10s（%d件）" % ("summary/ 合計", kb(summ), N))
    print("    %-20s %10s" % ("tokens.json", kb(sizeof(paths.TOKENS))))
    prog = sum(sizeof(os.path.join(sd, "progress", f))
               for f in os.listdir(os.path.join(sd, "progress")))
    print("    %-20s %10s（%d件）" % ("progress/ 合計", kb(prog), N))

    print("\n■ 毎リクエストで通る所")
    t, _ = timed(T.tokens)
    print("    合言葉の表を読む            %8s   ← 認証のたびに1回" % ms(t))
    t, _ = timed(T.accounts, SCHOOL)
    print("    アカウントを読む            %8s   ← 認証のたびに1回" % ms(t))
    T._SUMM.pop(SCHOOL, None)
    t, _ = timed(T.summary, SCHOOL)
    print("    要約を読む（1回目）         %8s   ← 全員ぶん読み込む" % ms(t))
    t, _ = timed(T.summary, SCHOOL)
    print("    要約を読む（2回目）         %8s   ← 変わった分だけ" % ms(t))

    print("\n■ 生徒が1問答えるたびに通る所")
    sid = "S0000001"
    rec = paths.load(paths.progress_path(SCHOOL, sid), None) or {}
    blob = rec.get("blob") or {}
    mine = [a for a in asg.values() if a["classId"] == db["s00001"]["classId"]]
    # 同期まるごと（担当宿題の割り出し＋要約の書き直し）を測る
    t0 = time.time()
    mine_old = [a for a in asg.values() if sid in T.students_for(SCHOOL, a)]
    t_pick_old = time.time() - t0
    t0 = time.time()
    c = T.hw_cache()
    mine_new = [a for a in asg.values() if sid in T.students_for(SCHOOL, a, c)]
    t_pick_new = time.time() - t0
    print("    宿題の割り出し 控えなし     %8s（%d件）" % (ms(t_pick_old), len(mine_old)))
    print("    宿題の割り出し 控えあり     %8s   ← %.0f倍 速い"
          % (ms(t_pick_new), (t_pick_old / t_pick_new) if t_pick_new else 0))
    # **1回目は測らない。** 初回だけ評価の表を読み込むので、
    # そのぶんが要約の書き込みに見えてしまう（16ms に見えていた）。
    T.summary(SCHOOL)
    T.update_summary(SCHOOL, "S0000002", blob, mine_new)
    t, _ = timed(T.update_summary, SCHOOL, sid, blob, mine_new)
    print("    要約の書き直し              %8s   ← 1人ぶんだけ書く" % ms(t))
    print("      → 同期まるごと 約%s ／ 40人同時なら 約%s"
          % (ms(t_pick_new + t), ms((t_pick_new + t) * 40)))

    print("\n■ 講師が画面を開くたびに通る所")
    t, out = timed(T.hw_summary, SCHOOL, list(asg.values())[0])
    print("    宿題1件の集計               %8s（対象 %d名）"
          % (ms(t), out.get("assigned") or 0))
    teach = dict(db["t000"], school=SCHOOL)
    pairs = T.teacher_pairs(teach)
    mine_a = [a for a in asg.values()
              if (a.get("classId"), T.subject_of_assignment(a)) in set(pairs)]
    print("    担当の宿題                  %8d件" % len(mine_a))
    # **画面まるごとの時間で測る。** 部品ごとの時間は当てにならない。
    t0 = time.time()
    for a in mine_a:
        T.hw_summary(SCHOOL, a)              # 控えなし（前のやり方）
    t_old = time.time() - t0
    t0 = time.time()
    blobs = T.hw_cache()
    for a in mine_a:
        T.hw_summary(SCHOOL, a, blobs)       # 控えあり（いまのやり方）
    t_new = time.time() - t0
    print("    担当%d件ぜんぶ 控えなし     %8s" % (len(mine_a), ms(t_old)))
    print("    担当%d件ぜんぶ 控えあり     %8s   ← %.0f倍 速い"
          % (len(mine_a), ms(t_new), (t_old / t_new) if t_new else 0))
    print("      読んだ進捗ファイル          %8d件（控えあり）" % len(blobs["blobs"]))

    print("\n■ 教材の読み込み")
    examprep._CACHE.clear()
    t, items = timed(examprep.pack_items, "japanese", "e4")
    print("    国語 小4（1回目）           %8s  %d問" % (ms(t), len(items)))
    t, items = timed(examprep.pack_items, "japanese", "e4")
    print("    国語 小4（2回目・控えあり） %8s" % ms(t))

    print("\n■ 毎日テストの組み立て")
    cid = sorted(classes)[0]
    t, sets = timed(T.daily_sets, SCHOOL, cid, "japanese", sid)
    print("    1人ぶん                     %8s  %d本" % (ms(t), len(sets)))

    print("\n■ 対策テストの組み立て（1教科）")
    t, got = timed(examprep.build, SCHOOL, "e4", "japanese", "advanced",
                   [], "2026-08-22", units=[], materials={}, hard=None)
    print("    1人ぶん                     %8s  %s問"
          % (ms(t), len(got["items"]) if got else 0))

    shutil.rmtree(TMP, ignore_errors=True)
    print("\n消しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
