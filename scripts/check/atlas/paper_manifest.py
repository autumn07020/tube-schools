# -*- coding: utf-8 -*-
"""紙の宿題の道具の写し（その道具の検査が撮ったもの）を、台帳に入れる。 python3 paper_manifest.py <S> <tube-schools の場所>"""
import json, os, shutil, sys
S, SRC = sys.argv[1], sys.argv[2]; A = S + "/atlas"; D = SRC + "/紙の宿題/検査/作業.nosync/shots"
names = [("横-0-login", "入口（tubestudy の講師の ID で入る）"), ("横-1-home", "はじめの画面"), ("横-2-course", "取り込む：コースを選ぶ"), ("横-3-lesson", "取り込む：回を選ぶ"), ("横-4-files", "取り込む：PDF を選ぶ"),
         ("1-review", "取り込む：生徒ごとに分かれたページを確かめる"), ("2-sent", "取り込む：送ったあと"), ("横-5-grade", "採点する（一覧）"), ("3-grade", "採点する（ペンで赤・印を叩く・1〜5 を押すと返して次の子へ）"),
         ("5-byq", "問題ごとに採点する"), ("6-byq-sum", "問題ごとの集計"), ("4-sheets", "答案用紙を刷る"), ("横-6-names", "名前（この端末だけ）"), ("横-7-names-course", "名前：コース"), ("横-8-print", "番号シールを刷る"),
         ("横-9-print-course", "番号シール：コース"), ("横-10-help", "使い方"), ("縦-1-home", "はじめの画面（iPad たて）"), ("縦-5-grade", "採点する（iPad たて）")]
items = []
for n, t in names:
    src = "%s/%s.png" % (D, n)
    if not os.path.exists(src): continue
    shutil.copyfile(src, "%s/shots/紙の宿題-%s.png" % (A, n))
    items.append({"section": "紙の宿題", "key": n, "dev": "iPad", "files": ["紙の宿題-%s.png" % n], "title": "紙の宿題の道具：" + t, "how": "講師の iPad／Mac で、別の小さな道具（紙の宿題/web）を開く", "note": "", "persona": "講師（紙のノートを集めて、撮って、採点して返す）"})
json.dump(items, open(A + "/manifest-paper.json", "w"), ensure_ascii=False, indent=1); print("紙の宿題", len(items))
