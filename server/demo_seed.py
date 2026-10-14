#!/usr/bin/env python3
"""
デモの見せ場をつくる
------------------------------------------------------------------
    python3 server/demo_seed.py

講師に見せるときに「空っぽの画面」を見せないための道具。
次を用意する。

  * 全学年に複数教科の進度を割り当てる
  * 教科をまたいで宿題を数件出す（終わったもの・遅れているもの混在）
  * 生徒18名に、まちまちの学習履歴を入れる
    （毎日やっている子／週2の子／止まっている子）

★ 入るのは架空の記録だけ。氏名は一切扱わない。
★ 何度でも実行してよい。実行するたびに作り直す。
"""

import io
import json
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "app")
DATA = os.path.join(HERE, "data")
DAY = 86400000

random.seed(20260815)          # 毎回同じ絵になるように固定する


def slug(s):
    """content.js の slug() と同じ規則。IDがずれると別項目になる。"""
    s = s.lower()
    s = re.sub(r"[^a-z0-9぀-ヿ一-鿿]+", "-", s)
    return s.strip("-")


def load_json(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except (IOError, ValueError):
        return d


def save_json(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(o, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ------------------------------------------------------------------
# 教材から、実際に存在する項目IDを拾う
# ------------------------------------------------------------------
def item_ids():
    """科目コード -> [項目ID]。教材ファイルを直接読んで作る。
    でたらめなIDを入れると、講師画面の「定着」が0のままになる。"""
    man = io.open(os.path.join(APP, "content/manifest.js"), encoding="utf-8").read()
    codes = dict(re.findall(r"id:'(\w+)',\s*code:'(\w+)'", man))
    packs = re.findall(r"id:'([\w/\-]+)',\s*subject:'(\w+)',\s*file:'([\w/\-.]+)'", man)

    out = {}
    for pid, subject, rel in packs:
        code = codes.get(subject, subject)
        src = io.open(os.path.join(APP, "content", rel), encoding="utf-8").read()
        ids = []
        # 英語の単語 V: ["head","pos",...]
        for head, pos in re.findall(r'^\["([^"]+)","([^"]+)","(?:A2|B1|B2|C1)"', src, re.M):
            ids.append("%s:v:%s:%s" % (code, slug(head), slug(pos)))
        # T / Q（全科目共通）
        if "V.push" not in src:
            for line in src.split("\n"):
                t = line.strip()
                if not t.startswith('["'):
                    continue
                parts = re.findall(r'"((?:[^"\\]|\\.)*)"', t)
                if len(parts) < 2:
                    continue
                # 3つめか4つめが帯なら T、答えの並びがあれば Q
                if len(parts) > 2 and "|" in parts[2]:
                    ids.append("%s:q:%s" % (code, slug(parts[0])))
                else:
                    ids.append("%s:t:%s" % (code, slug(parts[0])))
        out.setdefault(pid, []).extend(ids)
    return out


# ------------------------------------------------------------------
# 1. 進度 ―― 全学年に複数教科
# ------------------------------------------------------------------
def build_curriculum():
    """学年とクラスだけを書く。**教材の割り当ては書かない。**

    以前はここに学年×教科の教材一覧を持っていた。それが
    app/curriculum.js と二重管理になり、片方だけ古くなった
    （japanese/kanji-e や social/j1-geo など、もう無い教材を
    指したまま残っていた）。指した先が無くても落ちないので、
    その教科の画面が空になるだけで、誰も気づけない。

    いまは app/js/config.js が欄ごとに既定へ重ねるので、
    サーバは「変えたい欄だけ」書けばよい。教材の差し替えは
    app/curriculum.js の1か所で済む。
    """
    cur = load_json(os.path.join(DATA, "curriculum.json"), {})
    cur["v"] = 2
    cur.setdefault("grades", [
        {"id": "e4", "name": "小4", "order": 1}, {"id": "e5", "name": "小5", "order": 2},
        {"id": "e6", "name": "小6", "order": 3}, {"id": "j1", "name": "中1", "order": 4},
        {"id": "j2", "name": "中2", "order": 5}, {"id": "j3", "name": "中3", "order": 6}])
    cur.setdefault("classes", [
        {"id": "e5a", "name": "小5 A", "grade": "e5", "code": "LDN-E5A"},
        {"id": "e6a", "name": "小6 A", "grade": "e6", "code": "LDN-E6A"},
        {"id": "j1a", "name": "中1 A", "grade": "j1", "code": "LDN-J1A"},
        {"id": "j2a", "name": "中2 A", "grade": "j2", "code": "LDN-J2A"},
        {"id": "j3a", "name": "中3 A", "grade": "j3", "code": "LDN-J3A"},
        {"id": "j3b", "name": "中3 B", "grade": "j3", "code": "LDN-J3B"}])
    # plans は書かない（理由は上の説明）。すでに古いものが入っていたら消す。
    cur.pop("plans", None)
    save_json(os.path.join(DATA, "curriculum.json"), cur)
    # 架空の記録を作る側には、学年×教科の一覧だけ渡す。
    # **既定（app/curriculum.js）から読む。** ここで持ち直さない。
    return default_plans()


def default_plans():
    """app/curriculum.js の進度を読む。**既定はここにしか無い。**

    JavaScript を動かさずに、必要な欄（packs と bands）だけ取り出す。
    サーバは Linux で動くので、ブラウザや osascript には頼れない。
    形が変わって読めなくなったら空を返す ―― そのときは
    app/tools/check-content.py が「進度が教材を指していない」と言う。
    """
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "app", "curriculum.js")
    try:
        src = io.open(path, encoding="utf-8").read()
    except OSError:
        return {}
    out = {}
    for m in re.finditer(
            r"'([a-z0-9]+:[a-z]+)':\s*\{([^}]*?)packs:\s*\[([^\]]*)\]"
            r"(?:[^}]*?bands:\s*\[([^\]]*)\])?", src, re.S):
        key, head, packs, bands = m.groups()
        if "enabled:false" in (head or "").replace(" ", ""):
            continue
        out[key] = {
            "enabled": True,
            "packs": re.findall(r"'([^']+)'", packs or ""),
            "bands": re.findall(r"'([^']+)'", bands or ""),
        }
    return out


# ------------------------------------------------------------------
# 2. 宿題 ―― 教科をまたいで、状態もまちまちに
# ------------------------------------------------------------------
def build_assignments():
    now = int(time.time() * 1000)
    hw = {
        "demo_j2_grit": {
            "id": "demo_j2_grit", "title": "My英単語帳 No.1000–1050", "source": "myvocab",
            "from": 1000, "to": 1050, "classId": "j2a", "students": [],
            "assignedAt": now - 4 * DAY, "dueAt": now + 3 * DAY,
            "note": "小テストは金曜"},
        "demo_j3_grit": {
            "id": "demo_j3_grit", "title": "My英単語帳 No.1500–1560", "source": "myvocab",
            "from": 1500, "to": 1560, "classId": "j3a", "students": [],
            "assignedAt": now - 9 * DAY, "dueAt": now - 1 * DAY,
            "note": "期限を過ぎています"},
        "demo_j1_grit": {
            "id": "demo_j1_grit", "title": "My英単語帳 No.1–40（復習）", "source": "myvocab",
            "from": 1, "to": 40, "classId": "j1a", "students": [],
            "assignedAt": now - 1 * DAY, "dueAt": now + 6 * DAY, "note": ""},
    }
    save_json(os.path.join(DATA, "assignments.json"), hw)
    return hw


# ------------------------------------------------------------------
# 3. 学習履歴 ―― 続けている子・週2の子・止まっている子
# ------------------------------------------------------------------
PROFILES = [
    ("毎日", 14, 0.75, 0.92),
    ("週3",   7, 0.45, 0.80),
    ("週1",   3, 0.20, 0.70),
    ("停止",  1, 0.06, 0.60),
]


def build_progress(plans, ids):
    accounts = load_json(os.path.join(DATA, "accounts.json"), {})
    hw = load_json(os.path.join(DATA, "assignments.json"), {})
    now = int(time.time() * 1000)
    made = 0

    for login, acc in sorted(accounts.items()):
        if acc.get("role") != "student":
            continue
        grade = acc.get("classId", "")[:2]
        grade = {"e5": "e5", "e6": "e6", "j1": "j1", "j2": "j2", "j3": "j3"}.get(
            acc.get("classId", "")[:2], "j1")
        label, days, share, acc_rate = PROFILES[made % len(PROFILES)]

        pool = []
        for key, plan in plans.items():
            if not key.startswith(grade + ":") or not plan["enabled"]:
                continue
            for pk in plan["packs"]:
                pool += ids.get(pk, [])
        pool = list(dict.fromkeys(pool))
        random.shuffle(pool)
        take = pool[:int(len(pool) * share)]

        cards, hist = {}, {}
        for cid in take:
            good = random.random() < acc_rate
            iv = random.choice([25, 30, 45]) if good else random.choice([1, 2, 4])
            cards[cid] = [iv, 2.5, now + iv * DAY,
                          random.randint(1, 5), 0 if good else random.randint(3, 5),
                          now - random.randint(0, 6) * DAY, 0]
        for d in range(days):
            k = time.strftime("%Y-%m-%d", time.localtime((now - d * DAY) / 1000))
            n = random.randint(8, 34)
            hist[k] = {"n": n, "ok": int(n * acc_rate),
                       "done": 1 if random.random() < 0.55 else 0}

        p_hw = {}
        for aid, a in hw.items():
            if a["classId"] != acc.get("classId"):
                continue
            total = a["to"] - a["from"] + 1
            done_n = int(total * min(1.0, share + random.uniform(-0.15, 0.35)))
            done = {str(a["from"] + i): 1 for i in range(max(0, done_n))}
            p_hw[aid] = {"done": done,
                         "startedAt": now - 2 * DAY if done else None,
                         "completedAt": now - DAY if len(done) >= total else None}

        blob = {"v": 1, "sid": acc["sid"], "grade": grade,
                "classId": acc.get("classId"), "cards": cards, "hw": p_hw,
                "hist": hist, "streak": days, "best": max(days, 5),
                "xp": len(cards) * 4, "lastDay": None, "dayKey": None,
                "newToday": 0, "sessDone": {}, "started": now - 30 * DAY,
                "savedAt": now, "rev": 1}
        save_json(os.path.join(DATA, "progress", acc["sid"] + ".json"),
                  {"sid": acc["sid"], "rev": 1, "savedAt": now,
                   "blob": blob, "updated": int(time.time())})
        made += 1
        print("  %-8s %-6s %-4s 項目%4d  履歴%2d日  宿題%d件" %
              (login, acc.get("classId"), label, len(cards), len(hist), len(p_hw)))
    return made


def main():
    print("デモの見せ場をつくります（架空の記録のみ）\n")
    ids = item_ids()
    print("教材から拾った項目:", {k: len(v) for k, v in ids.items()}, "\n")
    plans = build_curriculum()
    print("進度: %d件（学年 × 教科）" % len(plans))
    hw = build_assignments()
    print("宿題: %d件\n" % len(hw))
    n = build_progress(plans, ids)
    print("\n生徒 %d名ぶんの履歴を作りました。" % n)
    print("サーバを再起動しなくても、次のログインから反映されます。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
