#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本部カリキュラムとのズレを測る。

何のためか
----------
教材と進度は、校舎ごと・講師ごとに変えられるようにしてある。
そうしないと現場で使えないからである。しかしその自由は、
**「本部のカリキュラムからどれだけ離れたか」が誰にも見えない**
という代償を伴う。学期末になって初めて2単元遅れていたと分かる、
という形で表面化する。

そこで、本部の週別カリキュラムを基準として置き、
講師の実施状況との差をいつでも出せるようにする。

    <ROOT>/shared/curriculum/<学年>.json      本部の基準（全校舎共通）
    <ROOT>/schools/<校舎>/curriculum.json     講師の実施（done に記録）

基準の形
--------
    {
      "grade": "j1",
      "name": "中1",
      "source": "早稲田アカデミー 本部カリキュラム",
      "year": 2026,
      "weeks": [
        {"w": 1,  "from": "2026-04-06", "units": [
            {"subject": "science", "unit": "植物のなかま"},
            {"subject": "social",  "unit": "世界のすがた"}]},
        ...
      ]
    }

**この基準データは本部から受け取るもので、こちらで作らない。**
形式（Excel / PDF / 紙）が分かれば import-reference で取り込む。
無いあいだは空のまま置いておけばよく、そのときズレは「不明」と表示される
―― 0（ズレ無し）とは区別すること。基準が無いのに「ズレ無し」と出したら、
それは嘘になる。
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                    # noqa: E402
import curriculum_source as SOURCE              # noqa: E402


def reference_path(grade):
    return paths.shared_file("curriculum", "%s.json" % grade)


def load_reference(grade):
    """取り込んだ基準（shared/curriculum）を優先し、無ければ原本（カリキュラム/カリキュラム.json）から。
    **仮の印（provisional）の付いた取り込みは、原本がある学年では使わない** ―― 前のデモが置いた仮の基準が
    shared に残っていても、原本を隠さない。"""
    try:
        got = paths.load(reference_path(grade), None)
    except paths.BadPath:
        got = None
    if got is None or got.get("provisional"):
        src = SOURCE.reference(grade)
        if src is not None:
            return src
    return got


def save_reference(grade, data):
    paths.save(reference_path(grade), data)


def list_references():
    d = os.path.join(paths.SHARED, "curriculum")
    ids = set()
    if os.path.isdir(d):
        ids |= {f[:-5] for f in os.listdir(d) if f.endswith(".json")}
    ids |= {g for g in ("e4", "e5", "e6", "j1", "j2", "j3") if SOURCE.reference(g)}
    return sorted(ids)


def week_of(ref, when=None):
    """基準のうち、いま何週目にあたるか。日付が無ければ None。"""
    when = when or time.time()
    cur = None
    for wk in (ref.get("weeks") or []):
        d = wk.get("from")
        if not d:
            continue
        try:
            t = time.mktime(time.strptime(d, "%Y-%m-%d"))
        except ValueError:
            continue
        if t <= when:
            cur = wk.get("w")
    return cur


def drift(grade, plans, when=None):
    """本部の基準と、講師の実施状況との差。

    plans は curriculum.json の plans（`<学年>:<科目>` → {done:[単元名], ...}）。

    返すもの
        status   'ok' … 基準があり比較できた
                 'no-reference' … 本部の基準が入っていない（ズレは不明）
        weeks    予定より何週ぶん進んでいるか（マイナスは遅れ）
        missing  基準にあるのに、まだ実施していない単元
        extra    基準に無いのに実施した単元
    """
    ref = load_reference(grade)
    if not ref or not ref.get("weeks"):
        # **「ズレ無し」と答えないこと。** 基準が無いのだから分からない。
        return {"status": "no-reference", "grade": grade,
                "message": "本部カリキュラムがまだ入っていません。"
                           "ズレは判定できません。"}

    now_week = week_of(ref, when)
    if now_week is None:
        return {"status": "no-reference", "grade": grade,
                "message": "本部カリキュラムに日付が入っていません。"}

    # 基準：いまの週までに終わっているはずの単元
    expected = []
    for wk in ref["weeks"]:
        if (wk.get("w") or 0) <= now_week:
            for u in (wk.get("units") or []):
                expected.append((u.get("subject", ""), u.get("unit", "")))

    # 実施：講師が done に入れた単元
    done = set()
    for key, plan in (plans or {}).items():
        if not key.startswith(grade + ":"):
            continue
        subject = key.split(":", 1)[1]
        for u in (plan.get("done") or []):
            done.add((subject, str(u)))

    exp_set = set(expected)
    missing = [u for u in expected if u not in done]
    extra = sorted(done - exp_set)

    # 進み・遅れを週で表す。
    #
    # 「最初に未完了の週で止める」やり方だと、**1単元飛ばしただけで
    # 何週も遅れて見える**（実際に、社会の1単元を残しただけで5週遅れと出た）。
    # 現場では単元を入れ替えたり飛ばしたりするのが普通なので、
    # その測り方は使えない ―― 講師が数字を信用しなくなる。
    #
    # 累積の達成率で見る。9割そろっていれば、その週までは進んだとみなす。
    reached = 0
    seen_n = done_n = 0
    for wk in ref["weeks"]:
        units = [(u.get("subject", ""), u.get("unit", "")) for u in (wk.get("units") or [])]
        if not units:
            continue
        seen_n += len(units)
        done_n += len([1 for u in units if u in done])
        if seen_n and (done_n / seen_n) >= 0.9:
            reached = wk.get("w") or reached
        if (wk.get("w") or 0) >= now_week:
            break
    weeks = reached - now_week

    # **教科ごとの進み・遅れ。単元の数で数える。**
    #
    # 学年でひとつの数字にまとめると、算数が2つ先に進んでいて社会が
    # 2つ遅れていても「±0」と出る。手を入れる先が見えない。
    # 講師が持っているのは教科なので、教科ごとに出す。
    per = {}
    for sub, unit in expected:
        e = per.setdefault(sub, {"expected": 0, "done": 0, "missing": []})
        e["expected"] += 1
        if (sub, unit) in done:
            e["done"] += 1
        else:
            e["missing"].append(unit)
    # 基準より先に進んだ分（基準にはまだ出てこない単元）も数える。
    for sub, unit in done:
        if (sub, unit) not in exp_set:
            per.setdefault(sub, {"expected": 0, "done": 0, "missing": []})
            per[sub]["done"] = per[sub].get("done", 0)
            per[sub]["ahead"] = per[sub].get("ahead", 0) + 1
    subjects = []
    for sub, e in sorted(per.items()):
        behind = e["expected"] - e["done"]
        subjects.append({
            "subject": sub,
            "expected": e["expected"],
            "done": e["done"],
            # プラスなら先に進んでいる、マイナスなら遅れている（単元の数）
            "delta": e.get("ahead", 0) - behind,
            "missing": e["missing"][:6],
        })

    return {
        "status": "ok",
        "grade": grade,
        "name": ref.get("name", grade),
        "source": ref.get("source", ""),
        "provisional": bool(ref.get("provisional")),
        "week": now_week,
        "reached": reached,
        "weeks": weeks,
        "subjects": subjects,
        "missing": [{"subject": s, "unit": u} for s, u in missing],
        "extra": [{"subject": s, "unit": u} for s, u in extra],
    }


# ------------------------------------------------------------------
# 取り込み
# ------------------------------------------------------------------
def import_csv(grade, path, name=None, source="", year=None):
    """本部カリキュラムをCSVから取り込む。

        week,from,subject,unit
        1,2026-04-06,science,植物のなかま
        1,2026-04-06,social,世界のすがた
        2,2026-04-13,science,植物のからだ

    Excel から「CSV（UTF-8）」で書き出せばこの形になる。
    PDFや紙しかない場合は、この4列に手で写すのがいちばん早い。
    """
    import csv as _csv
    weeks = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in _csv.DictReader(f):
            try:
                w = int((r.get("week") or r.get("週") or "").strip())
            except (TypeError, ValueError):
                continue
            unit = (r.get("unit") or r.get("単元") or "").strip()
            subject = (r.get("subject") or r.get("教科") or "").strip()
            if not unit or not subject:
                continue
            wk = weeks.setdefault(w, {"w": w, "from": (r.get("from") or "").strip(),
                                      "units": []})
            wk["units"].append({"subject": subject, "unit": unit})
    data = {
        "grade": grade,
        "name": name or grade,
        "source": source or "本部カリキュラム",
        "year": year or time.localtime().tm_year,
        "importedAt": int(time.time()),
        "weeks": [weeks[k] for k in sorted(weeks)],
    }
    save_reference(grade, data)
    return data


if __name__ == "__main__":
    print("MYACADY_ROOT =", paths.ROOT)
    refs = list_references()
    if not refs:
        print("\n本部カリキュラムはまだ入っていません。")
        print("取り込むには:")
        print("  python3 server/tube_server.py import-reference j1 中1カリキュラム.csv --name 中1")
        sys.exit(0)
    for g in refs:
        ref = load_reference(g)
        n = sum(len(w.get("units") or []) for w in (ref.get("weeks") or []))
        print("  %-6s %-8s %2d週 / %3d単元  （%s）"
              % (g, ref.get("name", ""), len(ref.get("weeks") or []), n,
                 ref.get("source", "")))
