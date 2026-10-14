# -*- coding: utf-8 -*-
"""撮った写しの台帳を1つにまとめ、画面の番号（ID）と巻を決める。 → atlas.json と 02-画面台帳.md"""
import json, os, re, sys, collections
S = sys.argv[1]; A = S + "/atlas"
def load(n):
    p = "%s/manifest-%s.json" % (A, n)
    return json.load(open(p)) if os.path.exists(p) else []
PERSONA_NOTE = {"lj2r01": "中2R・5教科（見本の主役）", "le4b01": "小4β（かな多めの表記・漢字テストと記述を写真で）", "le5b01": "小5β（上位の宿題あり）", "lj3r01": "中3R（土特あり）", "lj1d03": "中1D（国数だけ・組み分けテスト対策）",
                "lteacher1": "講師1（12コース・毎日テストまで）", "lteacher2": "講師2（小4・小5。添削まで）", "lteacher3": "講師3（中1・中2。紙のまま〜毎日テスト）", "lteacher4": "講師4（中3）"}
ADMIN_TITLES = {"21生徒-classopen": "クラスを足す紙", "22生徒-cls": "クラスの紙（席・生徒の一覧）", "23生徒-moveopen": "クラス替えの紙", "31講師と担当-addadmin": "管理者を足す（新しい合言葉が、この1回だけ出る）",
                "32講師と担当-addteacher": "講師を足す（新しい合言葉が、この1回だけ出る）", "33講師と担当-adminopen": "管理者の札を開く", "34講師と担当-assign": "コースごとの担当：講師を選ぶ",
                "35講師と担当-csvopen": "コースの表を直す紙", "36講師と担当-named": "指名の紙（このコースを受ける生徒を選ぶ）", "36講師と担当-named-namedtoggle": "指名の紙：生徒を選んだところ",
                "37講師と担当-teacher": "講師の札を開く（担当コース・最後に入った日・合言葉）", "37講師と担当-teacher-online": "講師にオンラインで渡す（1回だけ使えるリンク）", "37講師と担当-teacher-toggle": "講師の担当コースを切り替える"}
VOLS = [("1", "第1巻 入口と初回登録・時期で出る札"), ("2", "第2巻 生徒（iPhone）"), ("3", "第3巻 生徒（パソコン・iPad）"), ("4", "第4巻 講師（パソコン）"), ("5", "第5巻 講師（iPhone・iPad）"), ("6", "第6巻 管理ページ・刷る紙・紙の宿題の道具")]
groups = []   # (巻, 見出し, 接頭辞, items)
def add(vol, head, prefix, items, tag=""):
    items = [dict(x, tag=tag) for x in items]
    if items: groups.append((vol, head, prefix, items))
ent_p = [x for x in load("entry-P") if not x["key"].startswith("26")]; ent_d = [x for x in load("entry-D") if not x["key"].startswith("26")]
sp_p = load("special-P")
add("1", "入口と初回登録（iPhone）", "E", ent_p + [x for x in sp_p if x["section"] == "入口"])
add("1", "入口と初回登録（パソコン）", "E", ent_d)
add("1", "時期で出る札（組分けの申告・学年の繰り上げ・卒業）", "K", [x for x in sp_p if x["section"] == "時期の札"])
for lid in ("lj2r01", "le4b01", "lj1d03", "le5b01", "lj3r01"):
    add("2", "生徒：" + PERSONA_NOTE[lid] + "（iPhone）", "S", load("student-%s-P" % lid), tag=lid)
add("2", "生徒：暗い配色（CSS に値だけある。いまは切り替える場所が無い）", "S", load("student-lj2r01-P-dark"), tag="lj2r01")
add("3", "生徒：" + PERSONA_NOTE["lj2r01"] + "（パソコン）", "S", load("student-lj2r01-D"), tag="lj2r01")
add("3", "生徒：" + PERSONA_NOTE["le4b01"] + "（パソコン）", "S", load("student-le4b01-D"), tag="le4b01")
add("3", "生徒：" + PERSONA_NOTE["lj2r01"] + "（iPad）", "S", load("student-lj2r01-T"), tag="lj2r01")
add("4", "講師：" + PERSONA_NOTE["lteacher1"] + "（パソコン）", "T", load("teacher-lteacher1-D"), tag="lteacher1")
for lid in ("lteacher2", "lteacher3", "lteacher4"):
    its = load("teacher-%s-D" % lid)
    for x in its: x["key"] = "5" + x["key"]          # ほかの講師は 50 番台（T501…）
    add("4", "講師：" + PERSONA_NOTE[lid] + "（パソコン。導入の段階の違い）", "T", its, tag=lid)
add("5", "講師：" + PERSONA_NOTE["lteacher1"] + "（iPhone）", "T", load("teacher-lteacher1-P"), tag="lteacher1")
add("5", "講師：" + PERSONA_NOTE["lteacher1"] + "（iPad）", "T", load("teacher-lteacher1-T"), tag="lteacher1")
adm = load("admin-D")
for x in adm:
    if x["key"] in ADMIN_TITLES: x["title"] = "管理ページ：" + ADMIN_TITLES[x["key"]]
adm = sorted(adm + load("special-D"), key=lambda x: x["key"])
add("6", "管理ページ（パソコン）", "A", adm)
add("6", "管理ページ（iPhone。タブごとの全体だけ）", "A", load("admin-P"))
add("6", "刷る紙（組み分けテスト対策の A4）", "P", load("print"))
add("6", "紙の宿題の道具（別の小さな道具。iPad）", "N", load("paper"))
out = []
for vol, head, prefix, items in groups:
    for it in items:
        m = re.match(r"^(暗-|\d+)", it["key"])
        num = m.group(1) if m else ""
        rest = it["key"][len(num):].strip("-")
        if prefix == "A":
            parts = rest.split("-"); extra = "-".join(parts[1:]) if len(parts) > 1 and re.match(r"^[a-z]", parts[1] or "") else ""
            sid = "A" + num + ("-" + extra if extra else "")
        elif prefix in ("P", "N"):
            sid = prefix + "-" + it["key"]
        else:
            sid = prefix + num.replace("暗-", "暗") + (("-" + rest.split("-")[-1]) if (prefix in ("S",) and num == "18" and "-" in it["key"]) else "")
            if num == "暗-": sid = prefix + "暗-" + rest
        files = [f for f in it["files"] if os.path.exists(A + "/shots/" + f)]
        if not files: continue
        out.append({"id": sid, "vol": vol, "group": head, "dev": it["dev"], "persona": it.get("tag") or "", "who": it.get("persona") or "", "title": it["title"], "how": it["how"], "note": it.get("note") or "", "files": files})
# 同じ巻・同じ組で ID が重なったら a,b,c を付ける
seen = collections.Counter()
for x in out:
    k = (x["group"], x["id"]); seen[k] += 1
    if seen[k] > 1: x["id"] += "abcdefgh"[seen[k] - 2]
json.dump({"volumes": VOLS, "items": out}, open(A + "/atlas.json", "w"), ensure_ascii=False, indent=1)
print("項目 %d ／ 写し %d枚" % (len(out), sum(len(x["files"]) for x in out)))
for v, name in VOLS:
    its = [x for x in out if x["vol"] == v]; print("  %s  %d項目 %d枚" % (name, len(its), sum(len(x["files"]) for x in its)))
ids = collections.Counter((x["group"], x["id"]) for x in out); print("重なった ID:", [k for k, n in ids.items() if n > 1][:5])
