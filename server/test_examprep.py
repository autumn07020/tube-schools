#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""総復習テスト対策が、決めたとおりに動くかを確かめる。

なぜこの検査が要るか
--------------------
この仕組みは日付・記録・教材の3つに依存する。どれか1つが変わると
静かに壊れる ―― 画面には「対策なし」とだけ出て、誰も気づかない。

確かめるのは決めごとそのもの。

  ・組み分けテストの8日前から出る。それより前は出ない
  ・日程が入っていなければ出ない（無い日に向けて走らせない）
  ・直近の出来6割で 上位編／基本編 が分かれる
  ・1教科は1時間を超えない
  ・まちがえた問題は必ず先頭に戻る
  ・日が変わると並びが変わる（同じ日なら変わらない）
  ・紙はA3 1枚に収まる数で切れる

    python3 server/test_examprep.py
"""

import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/test-examprep"
os.environ["MYACADY_ROOT"] = ROOT
sys.path.insert(0, HERE)

shutil.rmtree(ROOT, ignore_errors=True)

import paths                                     # noqa: E402
import exams as E                                # noqa: E402
import examprep as P                             # noqa: E402
import lessons as L                              # noqa: E402
import prepsheet as S                            # noqa: E402

ok_n = ng_n = 0
DAY = 86400


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   %s" % name)
    else:
        ng_n += 1
        print("  ×    %s  %s" % (name, detail))


def setup(school="t1", exam_in_days=5):
    paths.ensure_dirs() if hasattr(paths, "ensure_dirs") else None
    d = paths.school_dir(school)
    os.makedirs(d, exist_ok=True)
    paths.save(paths.school_file(school, "school.json"),
               {"id": school, "name": "検査校"})
    when = time.time() + exam_in_days * DAY
    E.save(school, {"exams": [
        {"date": time.strftime("%Y-%m-%d", time.localtime(when - 35 * DAY))},
        {"date": time.strftime("%Y-%m-%d", time.localtime(when))},
    ], "prepDays": 8})
    return school


def main():
    print("組み分けテストの日程\n")
    s = setup("t1", exam_in_days=5)
    w = E.window(s)
    check("8日前の中に入っていれば窓が開く", bool(w), w)
    check("あと何日かが分かる", w and w["left"] == 5, w and w["left"])
    check("前回のテストが範囲のはじまりになる", bool(w and w["since"]), w)

    s2 = setup("t2", exam_in_days=20)
    check("まだ早ければ窓は開かない", E.window(s2) is None)

    E.save("t3", {"exams": []})
    paths.save(paths.school_file("t3", "school.json"), {"id": "t3"})
    check("日程が無ければ窓は開かない", E.window("t3") is None)

    print("\n5週の周期")
    check("第5回は総復習", L.is_review(5) and L.is_review(10))
    check("第4回は総復習ではない", not L.is_review(4) and not L.is_review(6))
    check("第7回は第2周", L.cycle_of(7) == 2, L.cycle_of(7))
    check("第7回の周は6〜10回", L.block_of(7) == (6, 10), L.block_of(7))

    print("\n教材を読む")
    items = P.pack_items("science", "e5")
    check("理科 小5 の問題が読める", len(items) > 50, len(items))
    check("問題文と答えが入っている",
          all(x.get("q") and x.get("ans") for x in items))
    check("単元名が入っている", any(x.get("unit") for x in items))
    mitems = P.pack_items("math", "j1")
    check("数学の解説が読める", any(x.get("note") for x in mitems),
          len([x for x in mitems if x.get("note")]))
    check("項目IDが画面側と同じ形",
          any(x["id"] == "sci:q:とけ残りを取り出すときに使う方法は" for x in items))

    print("\n難易度の分かれ方")
    check("6割以上は上位編", P.tier_for(0.6) == "advanced")
    check("6割未満は基本編", P.tier_for(0.59) == "basic")
    check("記録が無ければ基本編から", P.tier_for(None) == "basic")

    print("\n組み立て")
    hard = {x["id"]: (0.9 if i % 3 == 0 else 0.1)
            for i, x in enumerate(items)}
    a = P.build(s, "e5", "science", "advanced", [], "d1",
                units=[], hard=hard, items=items)
    b = P.build(s, "e5", "science", "basic", [], "d1",
                units=[], hard=hard, items=items)
    check("上位編が組める", a and a["n"] > 10, a and a["n"])
    check("1教科は1時間を超えない", a["minutes"] <= 60, a["minutes"])
    ha = sum(hard[x["id"]] for x in a["items"][:15]) / 15
    hb = sum(hard[x["id"]] for x in b["items"][:15]) / 15
    check("上位編のほうが先頭が難しい", ha > hb, "%.2f vs %.2f" % (ha, hb))

    wrong = [items[7]["id"], items[19]["id"]]
    c = P.build(s, "e5", "science", "basic", wrong, "d1",
                units=[], hard=hard, items=items)
    head = [x["id"] for x in c["items"][:2]]
    check("まちがえた問題が先頭に戻る", set(head) == set(wrong), head)
    check("戻した数が数えられている", c["carried"] == 2, c["carried"])

    d1 = P.build(s, "e5", "science", "basic", [], "2026-08-20",
                 units=[], hard=hard, items=items)
    d1b = P.build(s, "e5", "science", "basic", [], "2026-08-20",
                  units=[], hard=hard, items=items)
    d2 = P.build(s, "e5", "science", "basic", [], "2026-08-21",
                 units=[], hard=hard, items=items)
    check("同じ日なら同じ並び",
          [x["id"] for x in d1["items"]] == [x["id"] for x in d1b["items"]])
    check("日が変われば並びが変わる",
          [x["id"] for x in d1["items"]] != [x["id"] for x in d2["items"]])

    print("\n範囲のしぼり")
    got = P.in_scope(items, ["植物の発芽"])
    check("単元で絞れる", 0 < len(got) < len(items), len(got))
    check("合う単元が無ければ絞らない",
          len(P.in_scope(items, ["ありえない単元"])) == len(items))

    print("\n紙")
    sheet = S.for_prep({"exam": {"date": "2026-08-25"}, "left": 5,
                        "tier": "advanced", "since": "2026-07-21"},
                       "理科", "小5", [{"items": items}])
    n_on_sheet = sheet.count('<div class="q">')
    check("紙に問題が並ぶ", n_on_sheet > 20, n_on_sheet)
    check("解答のページがある", "brk ans" in sheet)
    check("A4たての指定が入っている", "size:A4 portrait" in sheet)
    check("2段組みになっている", "columns:2" in sheet)
    check("解答らんのページがある", 'class="sheet mark brk"' in sheet)
    # 刷った問題には必ずマスが要る。**マスの数が上限**で、これは数えられる。
    cap = S.SHEET["cols"] * S.SHEET["rows"]
    paper = S.paper_items([{"items": items, "subject": "science"}])
    check("マスの数を超えない", len(paper) <= cap, "%d問 / %dマス" % (len(paper), cap))
    check("マスの数だけ解答らんがある",
          sheet.count('class="acell"') == min(len(paper), cap),
          sheet.count('class="acell"'))
    # 四すみの位置合わせマークが4つ。1つでも欠けるとカメラが読めない。
    check("位置合わせマークが4つある", sheet.count('class="mk"') == 4)

    # 進度を保存しても、既定の教材のままの教科を「使わない」と読まない。
    # 前は packs が空の欄を「使わない」と読んでいたので、講師が進度を1度保存すると、
    # 既定の教材のままの教科（中1の数学・英語…）が学校じゅうで対策テストから消えた。
    import tube_server as T                      # noqa: E402
    cur = T.valid_curriculum({"plans": {
        "j1:math": {"enabled": True, "packs": []},
        "j1:english": {},
        "j1:social": {"enabled": False},
        "j1:japanese": {"enabled": True},
        "j1:science": {"enabled": True}}})
    check("保存で enabled の無い欄を「使わない」にしない",
          cur["plans"]["j1:english"]["enabled"] is True, cur["plans"]["j1:english"])
    check("保存で enabled:false はそのまま残る",
          cur["plans"]["j1:social"]["enabled"] is False)
    fp = paths.school_file("t9", "curriculum.json")
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    paths.save(fp, cur)
    subs = T.enabled_subjects("t9", "j1")
    check("packs が空・無い教科も使う教科として数える",
          "math" in subs and "english" in subs, subs)
    check("enabled:false の教科は数えない", "social" not in subs, subs)

    print()
    if ng_n:
        print("× %d件おちた" % ng_n)
        return 1
    print("すべて通った。（%d件）" % ok_n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
