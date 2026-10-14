#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""単一校舎の古い配置を、校舎ごとの配置へ移す。

    server/data/accounts.json          →  <ROOT>/schools/<校舎>/accounts.json
    server/data/progress/<sid>.json    →  <ROOT>/schools/<校舎>/progress/<sid>.json
    server/data/assignments.json       →  <ROOT>/schools/<校舎>/assignments.json
    server/data/curriculum.json        →  <ROOT>/schools/<校舎>/curriculum.json

使い方

    python3 server/migrate_to_schools.py --school london --name 'ロンドン校' --code l
    python3 server/migrate_to_schools.py --school london --name 'ロンドン校' --code l --yes

**--yes を付けるまで、何も書き換えない。** 先に何が起きるかを表示する。
元のファイルは消さない（data.bak- に退避してから、新しい場所へ複製する）。
移行が失敗しても、元に戻せる状態を残しておくため。

ログインIDの頭に校舎コードを付けるかどうか
------------------------------------------
既定では **付けない**。いま使っているIDをそのまま残す。
2校舎目を作るときに衝突したら、そのとき --prefix を付けて移行し直す。
最初の1校舎しか無いうちにIDを変えると、配ったカードが全部無駄になる。
"""

import argparse
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                            # noqa: E402
import tube_server as T                                 # noqa: E402

OLD = os.path.join(HERE, "data")


def main():
    ap = argparse.ArgumentParser(description="単一校舎の配置を校舎ごとの配置へ移す")
    ap.add_argument("--school", required=True, help="移す先の校舎ID（london など）")
    ap.add_argument("--name", required=True, help="校舎の表示名（ロンドン校 など）")
    ap.add_argument("--code", help="ログインIDの頭に付く1〜2文字。既定はIDの頭文字")
    ap.add_argument("--tz", default="Europe/London")
    ap.add_argument("--prefix", action="store_true",
                    help="既存のログインIDの頭に校舎コードを付ける（配ったカードが変わる）")
    ap.add_argument("--yes", action="store_true", help="実際に書き換える")
    a = ap.parse_args()

    school = a.school
    code = (a.code or school[:1]).lower()
    paths.check_school(school)

    if not os.path.isdir(OLD):
        print("移すものがありません: %s" % OLD)
        return 1
    if os.path.abspath(OLD) == os.path.abspath(paths.ROOT):
        print("移行先が移行元と同じです。MYACADY_ROOT を別の場所にしてください。")
        print("  いまの MYACADY_ROOT = %s" % paths.ROOT)
        return 1

    acc = T.load_json(os.path.join(OLD, "accounts.json"), {})
    asg = T.load_json(os.path.join(OLD, "assignments.json"), {})
    cur = T.load_json(os.path.join(OLD, "curriculum.json"), {})
    prog_dir = os.path.join(OLD, "progress")
    progs = sorted(f for f in os.listdir(prog_dir)) if os.path.isdir(prog_dir) else []

    print("移行元  %s" % OLD)
    print("移行先  %s" % paths.school_dir(school))
    print()
    print("  アカウント   %d件（生徒 %d / 講師 %d）"
          % (len(acc),
             len([x for x in acc.values() if x.get("role") == "student"]),
             len([x for x in acc.values() if x.get("role") == "teacher"])))
    print("  進捗         %d件" % len(progs))
    print("  宿題         %d件" % len(asg))
    print("  進度         %s" % ("あり" if cur else "なし"))
    print()

    # ID の衝突を先に確かめる。移行の途中で気づくと中途半端な状態になる。
    idx = paths.read_index()
    rename = {}
    clash = []
    for lid in acc:
        new = (code + lid) if a.prefix else lid
        rename[lid] = new
        other = idx.get(new)
        if other and other != school:
            clash.append((lid, new, other))
    if clash:
        print("× ログインIDが他の校舎とぶつかります。--prefix を付けて移行してください。")
        for lid, new, other in clash[:10]:
            print("    %s → %s は校舎 %s が使用中" % (lid, new, other))
        return 1

    if a.prefix:
        print("  ログインIDの頭に「%s」を付けます。例: %s → %s"
              % (code, list(acc)[0] if acc else "j2a01",
                 rename.get(list(acc)[0], "") if acc else code + "j2a01"))
        print("  ※ 生徒に配ったカードのIDが変わります。刷り直しが要ります。")
        print()

    if not a.yes:
        print("実際に移すには --yes を付けてください。")
        return 0

    # --- 退避 ---
    bak = OLD + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
    shutil.copytree(OLD, bak)
    print("退避しました: %s" % bak)

    # --- 校舎を作る ---
    paths.ensure_school(school)
    if not os.path.isfile(paths.school_file(school, "school.json")):
        paths.save(paths.school_file(school, "school.json"),
                   {"id": school, "name": a.name, "code": code, "tz": a.tz,
                    "created": int(time.time())})

    # --- アカウント（IDの付け替えを含む）---
    new_acc = {}
    for lid, rec in acc.items():
        new_acc[rename[lid]] = rec
        paths.bind_login(rename[lid], school)
    paths.save(paths.school_file(school, "accounts.json"), new_acc)

    # --- 進捗（sid は変えない。進捗は sid に紐づいていて、IDには紐づかない）---
    n = 0
    for f in progs:
        if not f.endswith(".json"):
            continue
        src = os.path.join(prog_dir, f)
        shutil.copy2(src, os.path.join(paths.progress_dir(school), f))
        n += 1

    paths.save(paths.school_file(school, "assignments.json"), asg)
    if cur:
        paths.save(paths.school_file(school, "curriculum.json"), cur)

    # --- 講師画面むけの要約を作る ---
    out = {}
    asg_list = list(asg.values())
    for rec in new_acc.values():
        if rec.get("role") != "student":
            continue
        sid = rec["sid"]
        p = paths.load(paths.progress_path(school, sid), None) or {}
        mine = [x for x in asg_list if sid in T.students_for(school, x)]
        out[sid] = T.summarise_one(p.get("blob") or {}, mine)
    paths.save(paths.school_file(school, "summary.json"), out)

    print()
    print("移しました。")
    print("  アカウント %d件 / 進捗 %d件 / 宿題 %d件 / 要約 %d件"
          % (len(new_acc), n, len(asg), len(out)))
    print()
    print("確かめる:")
    print("  python3 server/tube_server.py schools")
    print("  python3 server/tube_server.py list --school %s" % school)
    print()
    print("問題が無いことを確かめてから、%s を消してください。" % bak)
    return 0


if __name__ == "__main__":
    sys.exit(main())
