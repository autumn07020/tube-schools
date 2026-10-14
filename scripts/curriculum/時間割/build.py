#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""時間割の元 カリキュラム/時間割.csv（表計算で直せる。講師の名字入り・本番へ送らない）から、
  カリキュラム/時間割.json   … 機械が読む形（本番へ送らない）
  カリキュラム/コマ.csv      … システムへ入れる時間だけの表（講師名なし。deploy/時間割.sh が courses-slots で入れる）
  カリキュラム/担当.csv      … システムへ入れる講師だけの表（名字ではなくログインID。名字→ID は カリキュラム/時間割の講師.csv。deploy/担当.sh が courses-teachers で入れる）
  Claude outputs/時間割の確認.html … 照らし合わせ用のカレンダー
を作る。直すときは CSV を直して、これを流すだけ。
    python3 scripts/curriculum/時間割/build.py
"""
import csv, html, io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(ROOT, "カリキュラム", "時間割.csv")
IDS = os.path.join(ROOT, "カリキュラム", "時間割の講師.csv")   # 名字 → ログインID。名字が入るので本番へも Git へも入れない（手元だけ）
ME_ID = "wt01"   # 本人。名字はコードに書かず IDS から引く（2026-10-14）
def _surname_of():
    """ログインID → 名字（時間割の講師.csv）。"""
    with io.open(IDS, encoding="utf-8-sig", newline="") as f:
        return {(r.get("ID") or "").strip(): (r.get("講師") or "").strip() for r in csv.DictReader(f)
                if (r.get("ID") or "").strip() and (r.get("講師") or "").strip()}
DAYS = "月火水木金土"
class T:   # 決まりごと（以前の data.py の頭）
    PERIODS = {0: ("15:00", "16:30", "Zoom専用"), 1: ("16:40", "18:10", ""), 2: ("18:20", "19:50", ""), 3: ("20:10", "21:40", "")}
    ROOMS = {"A": 20, "B": 18, "C": 8, "D": 22, "E": 15}
    ME = _surname_of().get(ME_ID, ME_ID)   # 本人の名字（時間割.csv の講師の欄と同じ字）
# まだコース表に無いコース（時間割から新しく作る）。id・教科の呼び方・名前・学年・クラス
NEW = {"e5k:math": ("e5k", "算数", "小5K 算数", "e5", "e5k"), "j3rcatch:math": ("j3rcatch", "数学", "中3R キャッチアップ講座", "j3", ""),
       "e4o:japanese": ("e4o", "国語", "小4 オンライン 国語", "e4", ""), "e6o:social": ("e6o", "社会", "小6 オンライン 社会", "e6", ""),
       "e6o:english": ("e6o", "英語", "小6 オンライン 英語", "e6", "")}
SUBJ = {"japanese": "国語", "math": "数学", "english": "英語", "science": "理科", "social": "社会"}
def read_src():
    with io.open(SRC, encoding="utf-8-sig", newline="") as f:
        rs = list(csv.DictReader(f))
    active, removed = [], []
    for r in rs:
        flags = (r.get("印") or "").split()
        x = (r["曜日"], r["教室"], r["開始"], r["終了"], r["授業"], r["講師"], r.get("コース") or "", " ".join(f for f in flags if f != "外した"), r.get("注") or "")
        (removed if "外した" in flags else active).append(x)
    return active, removed
T.SLOTS, T.REMOVED = read_src()
T.REMOVED = [(d, r, a, b, lb, t, c, n) for d, r, a, b, lb, t, c, _f, n in T.REMOVED]
T.ONLY_PHOTO2 = []
T.QUESTIONS = []
def mins(t): h, m = t.split(":"); return int(h) * 60 + int(m)
def rows():
    out = []
    for d, r, a, b, label, teacher, course, flags, note in T.SLOTS:
        out.append({"day": d, "room": r, "from": a, "to": b, "label": label, "teacher": teacher,
                    "mine": teacher == T.ME, "courses": [c for c in course.split() if c], "flags": flags.split(), "note": note})
    return out
def clashes(rs):
    out = []
    for i, x in enumerate(rs):
        for y in rs[i + 1:]:
            if x["day"] != y["day"] or not (mins(x["from"]) < mins(y["to"]) and mins(y["from"]) < mins(x["to"])):
                continue
            if x["room"] == y["room"] and x["room"] != "?":
                out.append(("教室", x, y))
            if x["teacher"] == y["teacher"] and x["teacher"] not in ("?", ""):
                out.append(("講師", x, y))
    return out
def diff_vs_0930(rs):
    b = json.load(open(os.path.join(ROOT, "deploy", "accounts", "waseaca-london.bundle.json"), encoding="utf-8"))
    W = "月火水木金土日"; out = []
    for key, c in b["courses"]:
        old = sorted((W[s["day"] - 1], s.get("start", ""), s.get("end", "")) for s in (c.get("slots") or []))
        if not old: continue
        new = sorted((x["day"], x["from"], x["to"], x["teacher"]) for x in rs if key in x["courses"])
        mine_new = [n for n in new if n[3] == T.ME]
        same = [o for o in old if any(o == n[:3] and n[3] == T.ME for n in new)]
        if len(same) == len(old) and len(mine_new) == len(old):
            out.append((c.get("name", key), "変わらない", " ・".join(f"{d} {a}〜{e}" for d, a, e in old)))
        else:
            out.append((c.get("name", key), "9/30：" + "・".join(f"{d} {a}〜{e}" for d, a, e in old),
                        "いま：" + ("・".join(f"{d} {a}〜{e}（{t}）" for d, a, e, t in new) or "無し")))
    return out
def write_json(rs):
    doc = {"version": "2026-10-08", "about": "ロンドン校の時間割。本人が共有した写真2枚から起こした（scripts/curriculum/時間割/）。講師の名字が入るので本番へは送らない。",
           "sources": {"photo1": "教室案内（月〜金・教室A〜E・0〜3コマ）。月〜金はこれが正", "photo2": "講師の割り当て表（月〜土）。講師名と土曜はこちら"},
           "periods": {str(k): {"from": a, "to": b, "note": n} for k, (a, b, n) in T.PERIODS.items()},
           "rooms": T.ROOMS, "me": T.ME, "slots": rs,
           "only_photo2": [dict(zip(("day", "room", "from", "to", "label", "teacher", "course"), x)) for x in T.ONLY_PHOTO2],
           "removed": [dict(zip(("day", "room", "from", "to", "label", "teacher", "course", "why"), x)) for x in T.REMOVED],
           "questions": T.QUESTIONS}
    with open(os.path.join(ROOT, "カリキュラム", "時間割.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
# 色は講師ごと（2 枚目の写しの色）。鍵はログインID、名字は IDS から引く
COLOR_BY_ID = {"wt06": "#8EC0E4", "wt05": "#BFD0B0", "wt01": "#F5A93E", "wt03": "#F6E46A", "wt04": "#C9C9CB", "wt02": "#C3AEE6", "wt07": "#F7C1CC", "?": "#FFFFFF"}
COLOR = {_surname_of().get(i, i): c for i, c in COLOR_BY_ID.items()}
def esc(s): return html.escape(str(s))
def tags(fl): return "".join('<span class="tag t%s">%s</span>' % (esc(f), esc(f)) for f in fl)
def day_html(d, rs):
    items = [x for x in rs if x["day"] == d]
    lo = 600 if d == "土" else 900; hi = 1120 if d == "土" else 1310
    ppm = 0.9; H = int((hi - lo) * ppm)
    ticks = "".join(f'<div class="tick" style="top:{int((m - lo) * ppm)}px">{m // 60}:{m % 60:02d}</div>' for m in range(lo, hi + 1, 30))
    lines = "".join(f'<div class="hl" style="top:{int((m - lo) * ppm)}px"></div>' for m in range(lo, hi + 1, 30))
    cols = ""
    rooms = "ABCDE" + ("?" if any(x["room"] == "?" for x in items) else "")
    for r in rooms:
        blocks = ""
        for x in items:
            if x["room"] != r: continue
            top = int((mins(x["from"]) - lo) * ppm); h = int((mins(x["to"]) - mins(x["from"])) * ppm) - 2
            cls = "b" + (" me" if x["mine"] else "") + (" unk" if x["teacher"] == "?" else "")
            tg = tags(x["flags"])
            blocks += (f'<div class="{cls}" style="top:{top}px;height:{h}px;background:{COLOR.get(x["teacher"], "#eee")}">'
                       f'<div class="lb">{esc(x["label"])}</div><div class="tm">{esc(x["from"])}〜{esc(x["to"])}</div>'
                       f'<div class="tc">{"あなた" if x["mine"] else esc(x["teacher"])}</div>{tg}</div>')
        head = f'{r}教室<span>{T.ROOMS[r]}席</span>' if r in T.ROOMS else '教室未定'
        cols += f'<div class="col"><div class="rh">{head}</div><div class="cb" style="height:{H}px">{lines}{blocks}</div></div>'
    notes = [x for x in items if x["note"] or x["flags"]]
    nl = "".join(f'<li><b>{esc(x["room"])} {esc(x["from"])}〜{esc(x["to"])} {esc(x["label"])}</b>'
                 f'{tags(x["flags"])} {esc(x["note"])}</li>' for x in notes)
    extra = [x for x in T.ONLY_PHOTO2 if x[0] == d]
    el = "".join(f'<li><b>{esc(r)} {esc(a)}〜{esc(b)} {esc(lb)}</b>（{esc(t)}）</li>' for _, r, a, b, lb, t, _c in extra)
    rm = [x for x in T.REMOVED if x[0] == d]
    rl = "".join(f'<li><s>{esc(r)} {esc(a)}〜{esc(b)} {esc(lb)}</s> {esc(w)}</li>' for _, r, a, b, lb, t, _c, w in rm)
    return (f'<section class="day"><h2>{d}曜日</h2><div class="grid" style="grid-template-columns:52px repeat({len(rooms)},minmax(118px,1fr))"><div class="axis"><div class="rh">&nbsp;</div><div class="cb" style="height:{H}px">{ticks}</div></div>{cols}</div>'
            + (f'<h3>この曜日の注</h3><ul class="notes">{nl}</ul>' if nl else "")
            + (f'<h3>2枚目にだけある授業（時間割には入れていない）</h3><ul class="notes">{el}</ul>' if el else "")
            + (f'<h3>外したもの</h3><ul class="notes">{rl}</ul>' if rl else "") + "</section>")
def koma_html():
    out, missing, changed = getattr(T, "KOMA", ([], [], []))
    if not out: return ""
    new = "".join(f"<li>{esc(n)}（{esc(k)}）：{esc(s)}</li>" for k, n, o, s, isnew in changed if isnew)
    chg = "".join(f"<tr><td>{esc(n)}</td><td>{esc(o) or '（無し）'}</td><td>{esc(s)}</td></tr>" for k, n, o, s, isnew in changed if not isnew and o != s)
    mis = "".join(f"<li>{esc(n)}（{esc(k)}）</li>" for k, n in missing)
    return (f'<div class="card"><h2>システムへ入れるもの（コマ.csv・{len(out)}コース）</h2>'
            f'<p class="lead" style="margin:0 0 8px">入れるのは時間だけです。講師・受ける生徒・授業計画は変えません。</p>'
            + (f"<h3>新しく作るコース（講師なし・紙のまま。講師は管理ページで）</h3><ul>{new}</ul>" if new else "")
            + (f"<h3>9/30 のコース表から時間が変わる・入るコース</h3><table><tr><th>コース</th><th>9/30</th><th>入れる時間</th></tr>{chg}</table>" if chg else "")
            + (f"<h3>コース表にあるが時間割に無いコース（触らない）</h3><ul>{mis}</ul>" if mis else "") + "</div>")
def write_html(rs):
    mine = [x for x in rs if x["mine"]]
    mine_rows = "".join(f'<tr><td>{esc(x["day"])}</td><td>{esc(x["from"])}〜{esc(x["to"])}</td><td>{esc(x["room"])}</td><td>{esc(x["label"])}'
                        f'{tags(x["flags"])}</td></tr>'
                        for x in sorted(mine, key=lambda x: (DAYS.index(x["day"]), x["from"])))
    cl0 = clashes(rs)
    qs = [f'{k}が重なる：{x["day"]} {x["from"]}〜 {x["label"]}（{x["teacher"]}）と {y["label"]}（{y["teacher"]}）' for k, x, y in cl0]
    qs += [f'{x["day"]} {x["room"]} {x["from"]}〜 {x["label"]}：{x["note"]}' for x in rs if "要確認" in x["flags"]]
    q = "".join(f"<li>{esc(s)}</li>" for s in qs) or "<li>いまは、ありません。</li>"
    dv = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>" for a, b, c in diff_vs_0930(rs))
    cl = clashes(rs)
    cll = "".join(f'<li>{esc(k)}が重なる：{esc(x["day"])} {esc(x["room"])} {esc(x["from"])}〜{esc(x["to"])} {esc(x["label"])}（{esc(x["teacher"])}） と '
                  f'{esc(y["room"])} {esc(y["from"])}〜{esc(y["to"])} {esc(y["label"])}（{esc(y["teacher"])}）</li>' for k, x, y in cl) or "<li>重なりは見つかりませんでした。</li>"
    legend = "".join(f'<span class="lg"><i style="background:{c}"></i>{("あなた（" + esc(T.ME) + "）") if t == T.ME else ("講師不明" if t == "?" else esc(t))}</span>' for t, c in COLOR.items())
    days = "".join(day_html(d, rs) for d in DAYS)
    page = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>時間割の確認</title><style>
:root{{--bg:#F4F4F6;--card:#fff;--text:#1D1D1F;--sub:#6E6E73;--line:#E3E3E8}}
body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 -apple-system,"Hiragino Sans","Yu Gothic",sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 64px}}
h1{{font-size:26px;margin:0 0 4px}} .lead{{color:var(--sub);margin:0 0 20px}}
.card{{background:var(--card);border-radius:18px;padding:18px 20px;margin:0 0 18px;box-shadow:0 1px 2px rgba(0,0,0,.06)}}
.card h2{{font-size:18px;margin:0 0 10px}} table{{border-collapse:collapse;width:100%}} td,th{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);font-size:14px;vertical-align:top}}
ol li,ul li{{margin:4px 0}} .lg{{display:inline-flex;align-items:center;gap:6px;margin:4px 14px 4px 0;font-size:14px}} .lg i{{width:16px;height:16px;border-radius:4px;border:1px solid #aaa;display:inline-block}}
section.day{{background:var(--card);border-radius:18px;padding:18px 16px;margin:0 0 18px}} section.day h2{{margin:0 0 10px;font-size:20px}} section.day h3{{font-size:15px;margin:14px 0 4px}}
.grid{{display:grid;grid-template-columns:52px repeat(5,minmax(118px,1fr));gap:6px;overflow-x:auto}}
.rh{{font-weight:600;font-size:14px;height:30px}} .rh span{{color:var(--sub);font-weight:400;font-size:12px;margin-left:4px}}
.cb{{position:relative;background:#FAFAFB;border-radius:10px}} .axis .cb{{background:none}}
.tick{{position:absolute;left:0;font-size:12px;color:var(--sub);transform:translateY(-8px)}} .hl{{position:absolute;left:0;right:0;border-top:1px dashed #E6E6EA}}
.b{{position:absolute;left:3px;right:3px;border-radius:9px;padding:4px 7px;overflow:hidden;border:1px solid rgba(0,0,0,.12);box-sizing:border-box}}
.b.me{{border:3px solid #C0570B}} .b.unk{{border:2px dashed #C0392B}}
.lb{{font-weight:700;font-size:13px;line-height:1.3}} .tm,.tc{{font-size:12px;line-height:1.3}} .tc{{font-weight:600}}
.tag{{display:inline-block;font-size:11px;line-height:1;padding:3px 6px;border-radius:6px;margin:3px 3px 0 0;background:#E8E8ED;color:#1D1D1F;font-weight:600}}
.t要確認{{background:#C0392B;color:#fff}} .t訂正{{background:#005BAC;color:#fff}} .t新規{{background:#138A48;color:#fff}} .t担当変更,.t時間変更{{background:#B86400;color:#fff}} .t仮{{background:#6E6E73;color:#fff}}
.notes{{margin:0;padding-left:20px;font-size:14px}}
@media (max-width:700px){{h1{{font-size:22px}}}}
</style></head><body><main>
<h1>時間割の確認</h1><p class="lead">2026-10-08 にいただいた写真2枚から起こしました。月〜金は1枚目（教室案内）、講師名と土曜は2枚目（講師の割り当て表）です。太い橙の枠があなたの授業、赤い点線は講師が分からない授業です。</p>
<div class="card"><h2>あなたの授業</h2><table><tr><th>曜日</th><th>時間</th><th>教室</th><th>授業</th></tr>{mine_rows}</table></div>
<div class="card"><h2>確かめてほしいこと</h2><ol>{q}</ol></div>
<div class="card"><h2>9/30 のコース表との違い（あなたの担当だった12コース）</h2><table><tr><th>コース</th><th></th><th></th></tr>{dv}</table></div>
<div class="card"><h2>時間・教室の重なり（機械で調べた）</h2><ul>{cll}</ul></div>
{koma_html()}
<div class="card"><h2>色</h2>{legend}<p class="lead" style="margin:8px 0 0">色は2枚目の講師ごとの色に合わせました。</p></div>
{days}
</main></body></html>"""
    os.makedirs(os.path.join(ROOT, "Claude outputs"), exist_ok=True)
    with open(os.path.join(ROOT, "Claude outputs", "時間割の確認.html"), "w", encoding="utf-8") as f:
        f.write(page)
def bundle_courses():
    b = json.load(open(os.path.join(ROOT, "deploy", "accounts", "waseaca-london.bundle.json"), encoding="utf-8"))
    return dict(b["courses"])
def koma(rs):
    """コースごとの時間（id,教科,名前,学年,時間,クラス）。講師名は入れない。"""
    bc = bundle_courses(); W = {d: i + 1 for i, d in enumerate("月火水木金土日")}
    by = {}
    for x in rs:
        for c in x["courses"]:
            by.setdefault(c, set()).add((W[x["day"]], x["from"], x["to"]))
    out, unknown = [], []
    for key in sorted(by):
        cid, sub = key.split(":")
        sl = " ".join(f'{"月火水木金土日"[d - 1]}{a}-{b}' for d, a, b in sorted(by[key]))
        if key in bc:
            c = bc[key]; gr = c.get("grades") or [c.get("grade")]
            word = "算数" if sub == "math" and gr[0].startswith("e") else SUBJ[sub]
            out.append([cid, word, c.get("name") or cid, " ".join(gr), sl, " ".join(c.get("classes") or [])])
        elif key in NEW:
            i, word, name, g, cl = NEW[key]; out.append([i, word, name, g, sl, cl])
        else:
            unknown.append(key)
    if unknown:
        raise SystemExit("× コース表にも NEW にも無いコース: %s（build.py の NEW に足す）" % " ".join(unknown))
    with io.open(os.path.join(ROOT, "カリキュラム", "コマ.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "教科", "名前", "学年", "時間", "クラス"]); w.writerows(out)
    missing = sorted((k, v.get("name") or k) for k, v in bc.items() if k not in by)
    changed = []
    for row in out:
        key = "%s:%s" % (row[0], {"国語": "japanese", "算数": "math", "数学": "math", "英語": "english", "理科": "science", "社会": "social"}[row[1]])
        old = " ".join(f'{"月火水木金土日"[s["day"] - 1]}{s["start"]}-{s["end"]}' for s in (bc.get(key, {}).get("slots") or []))
        changed.append((key, row[2], old, row[4], key not in bc))
    return out, missing, changed
def teacher_ids():
    with io.open(IDS, encoding="utf-8-sig", newline="") as f:
        rs = list(csv.DictReader(f))
    return {(r.get("講師") or "").strip(): (r.get("ID") or "").strip() for r in rs
            if (r.get("講師") or "").strip() and (r.get("ID") or "").strip()}
def tantou(rs):
    """コースごとの講師（id,教科,講師）。講師はログインIDだけ。名字は 時間割の講師.csv で引く（無ければ止まる）。"""
    ids = teacher_ids(); by = {}; unknown = set()
    for x in rs:
        t = x["teacher"]
        if t in ("", "?"):
            continue
        if t not in ids:
            unknown.add(t); continue
        for c in x["courses"]:
            by.setdefault(c, [])
            if ids[t] not in by[c]:
                by[c].append(ids[t])
    if unknown:
        raise SystemExit("× 時間割の講師.csv に無い講師: %s（名字と ID の行を足す）" % "・".join(sorted(unknown)))
    out = []
    for key in sorted(by):
        cid, sub = key.split(":")
        word = "算数" if sub == "math" and cid.startswith("e") else SUBJ[sub]
        out.append([cid, word, " ".join(by[key])])
    with io.open(os.path.join(ROOT, "カリキュラム", "担当.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "教科", "講師"]); w.writerows(out)
    return out
if __name__ == "__main__":
    rs = rows(); write_json(rs)
    out, missing, changed = koma(rs)
    tt = tantou(rs)
    print("担当.csv", len(tt), "コース（講師", len(set(i for r in tt for i in r[2].split())), "人）")
    T.KOMA = (out, missing, changed)
    write_html(rs)
    print("コマ.csv", len(out), "コース（新しく作る", sum(1 for c in changed if c[4]), "）／時間割に無いコース", len(missing))
    print("授業", len(rs), "あなた", sum(1 for x in rs if x["mine"]), "重なり", len(clashes(rs)))
    for k, x, y in clashes(rs): print(" ", k, x["day"], x["room"], x["label"], x["from"], "／", y["room"], y["label"], y["from"])
    for a, b, c in diff_vs_0930(rs): print("  ", a, "|", b, "|", c)
