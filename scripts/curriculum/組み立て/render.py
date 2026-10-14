#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""カリキュラム/カリキュラム.json → カリキュラム/カリキュラム.md（読む用。JSON が元で、こちらは写し）。"""
import json,os,sys
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,"..","..",".."))
d=json.load(open(os.path.join(ROOT,"カリキュラム","カリキュラム.json"),encoding="utf-8"))
o=[]; P=o.append
P(f"# カリキュラム（読む用） 版 {d['version']}\n\n元は `カリキュラム.json`。この文書はそこから機械で出した写し（`scripts/curriculum/組み立て/render.py`）。\n")
S=d["subjects"]
P("## 小4・小5・小6（予習シリーズ）\n")
for g,gd in d["elementary"].items():
    for tk,t in gd["terms"].items():
        if "subjects" not in t: continue
        P(f"### {gd['name']} {t['name']}（{t['months']}・全{t['count']}回・{gd['source']} p{t['page']}）\n")
        subs=t["subjects"]; P("| 回 | 国語（読解） | 漢字とことば | 算数 | 社会 | 理科 |\n|---|---|---|---|---|---|")
        for i in range(t["count"]):
            row=[subs[k][i]["unit"] if k in subs and i<len(subs[k]) else "" for k in ("japanese","math","social","science")]
            w=subs["japanese"][i].get("words","") if i<len(subs["japanese"]) else ""
            P(f"| 第{i+1}回 | {row[0]} | {w} | {row[1]} | {row[2]} | {row[3]} |")
        P("")
        P(f"#### {gd['name']} {t['name']} 各回の学習内容\n\n{t.get('contents_note','')}\n")
        for i in range(t["count"]):
            parts=[]
            for k,nm in (("japanese","国語"),("words","漢字とことば"),("math","算数"),("social","社会"),("science","理科")):
                src=subs["japanese" if k=="words" else k][i] if i<len(subs["japanese" if k=="words" else k]) else {}
                v=src.get("words_contents" if k=="words" else "contents")
                if v: parts.append(f"{nm}：{'・'.join(v)}")
            if parts: P(f"- 第{i+1}回　"+"　／　".join(parts))
        P("")
    if "tests" in gd:
        for tk,name in (("first","前期"),("second","後期")):
            P(f"### {gd['name']} テスト日程 {name}（p{gd['tests']['page']}）\n\n| 実施日 | テスト | 範囲 |\n|---|---|---|")
            for r in gd["tests"][tk]:
                P(f"| {r.get('date','')}{'（'+r['weekday']+'）' if r.get('weekday') else ''} | {r.get('test','')}{'（表に無く補った）' if r.get('filled') else ''} | {r.get('range','')} |")
            P("")
sec=d["elementary"]["e6"]["terms"]["second"]
P(f"### 小6 後期（p{sec['pages']}）\n\n{sec['note']}\n\n#### 社会\n\n| 授業 | 予習シリーズ | 学習内容 | ポイントチェック | 統計Book |\n|---|---|---|---|---|")
for r in sec["social"]: P(f"| {r['n']} | {r['kai']} | {r['unit']} | {r['check']} | {r['stats']} |")
P("\n#### 理科\n\n| 授業 | 予習シリーズ | 学習内容 | マスターテキスト確認テスト | チェックテスト10 |\n|---|---|---|---|---|")
for r in sec["science"]: P(f"| {r['n']} | {r['kai']} | {r['unit']} | {r['check']} | {r['check10']} |")
P("\n#### 算数（下N回の名前）\n\n"+"／".join(f"第{k}回 {v}" for k,v in sec["math"]["kai"].items())+"\n")
for cls,rows in sec["math"]["weekly"].items():
    P(f"#### 算数 週別（{cls}）\n\n| 月 | 週 | 授業① | 授業② |\n|---|---|---|---|")
    for r in rows: P(f"| {r['month']} | {r['week']} | {r['lesson1']} | {r['lesson2']} |")
    P("")
for cls,rows in sec["japanese"]["weekly"].items():
    P(f"#### 国語 週別（{cls}）\n\n| 月 | 週 | 授業① | 授業② |\n|---|---|---|---|")
    for r in rows: P(f"| {r['month']} | {r['week']} | {r['lesson1']} | {r['lesson2']} |")
    P(f"\n{sec['japanese']['note']}\n")
P("## 小5K・小6K\n")
for cls,subs in d["k"]["classes"].items():
    for subj,t in subs.items():
        P(f"### {cls} {S[subj]}（p{t['page']}）\n\n| 回 | 学習単元 | 確認テスト |\n|---|---|---|")
        for u in t["units"]: P(f"| {u['n']} | {u['unit']} | {u.get('check','')} |")
        P("")
for yk,t in d["k"]["english"].items():
    P(f"### 英語 {t['class']}（p{t['page']}）\n\n| 回 | 学習単元 | 単語テスト | Basic Words |\n|---|---|---|---|")
    for u in t["units"]: P(f"| {u['n']} | {u['unit']} | {u.get('words','')} | {u.get('basic_words','')} |")
    P("")
P("## 中1・中2・中3\n")
for g,gd in d["junior"].items():
    for cls,subs in gd["classes"].items():
        for subj,t in subs.items():
            P(f"### {gd['name']} {cls} {S[subj]}（{gd['source']} p{t['page']}・1回{t['minutes']}分）\n")
            if t.get("note"): P(t["note"]+"\n")
            P("| 期 | 回 | 学習単元 | テスト／課題 |\n|---|---|---|---|")
            for term in t["terms"]:
                for u in term["units"]: P(f"| {term['term']} | {u['n']} | {u['unit']} | {u.get('test','')}{(' ／ 予習：'+u['prep']) if u.get('prep') else ''} |")
            P("")
L=d["london"]["second_2026"]
P(f"## ロンドン校 2026年度後期行事カレンダー（{L['source']}・{L['status']}）\n\n| 日曜 | 月〜金の帯（小学部） | 月〜金の帯（中学部） | 土（小学部） | 土（中学部） | 日 | 月 |\n|---|---|---|---|---|---|---|")
for w in L["weeks"]:
    sun=" / ".join(x for x in (w["sun"]["elementary"],w["sun"]["junior"]) if x)
    P(f"| {w['sunday']} | {w['weekdays']['elementary']} | {w['weekdays']['junior']} | {w['sat']['elementary']} | {w['sat']['junior']} | {sun} | {w.get('mon','')} |")
P("\n"+"\n".join("- "+n for n in L["notes"])+"\n")
P("## ロンドンのコースと表の対応\n\n| コース | 使う表 | シラバス | 注 |\n|---|---|---|---|")
for k,c in d["london"]["classes"].items(): P(f"| {k} | {c.get('table') or '―'} | {c.get('syllabus','')} | {c.get('note','')}{(' '+c['alignment']) if c.get('alignment') else ''} |")
P("")
open(os.path.join(ROOT,"カリキュラム","カリキュラム.md"),"w",encoding="utf-8").write("\n".join(o))
print("md", len("\n".join(o)))
