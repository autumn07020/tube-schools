#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""席・講師・管理者の ID と合言葉を、**この Mac の中で**作る。

    python3 scripts/accounts/make.py                 # ロンドン校。小4〜中3の17クラス×30席、講師10、管理者1
    python3 scripts/accounts/make.py --dry           # 何ができるかだけ見る（何も書かない）

できるもの（2つ）
----------------
    合言葉の表.nosync/tubestudy-合言葉の表-<校舎>.xlsx
        ID と合言葉の表。**合言葉が読めるのは、この表だけ。** Google スプレッドシートに
        取り込んで使う（drive.google.com →「新規」→「ファイルのアップロード」→ 開く）。
        取り込んだら、この Mac に残った .xlsx は消してよい。
        フォルダの名前が .nosync で終わっているのは、iCloud に写させないため（名前を変えないこと）。
    deploy/accounts/<校舎>.bundle.json
        サーバに入れる束。**入っているのは ID と、合言葉のハッシュだけ**（合言葉は入っていない）。
        `sh deploy/更新.sh` が送り、サーバの `bundle-import` が入れる。

考え方
------
* 合言葉は、ここで乱数から作って、表に書き、ハッシュにして束に書く。画面にも記録にも出さない。
  サーバが受け取るのはハッシュだけなので、サーバを丸ごと読まれても合言葉は分からない。
* 束に入るのは、入るときの「証明」を確かめるための値（server/scram.py の storedKey・serverKey・salt）。
  合言葉も、合言葉から作る鍵（SaltedPassword）も入らない。束を読まれても、それだけでは入れない。
  入るときも、合言葉は端末から出ない（端末が証明だけを送る）。
* 合言葉は `neko-yama-sora-4821` の形（app/words.json の 256語から。生徒 3語、講師 4語、管理者 5語）。
  線（-）や大文字・全角で打っても入れる（サーバがそろえる）。
* **同じ校舎で2度は作らない。** 作り直すと、表の合言葉とサーバのハッシュが食い違う。
  あとから席や講師を足すのは、管理ページ（/admin）から。

氏名は扱わない。表にも、名前を書く列は作らない（だれがどの番号かは、先生の手元の名簿で）。
"""

import argparse
import datetime
import hashlib
import io
import json
import os
import re
import secrets
import sys
import zipfile
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
APP = os.path.join(ROOT, "app")

sys.path.insert(0, os.path.join(ROOT, "server"))
import scram                                     # noqa: E402  サーバと同じ計算（合言葉のそろえ方・置く値）

WORDS_BY_ROLE = {"seat": 3, "teacher": 4, "admin": 5}
GRADE_JP = {"e1": "小1", "e2": "小2", "e3": "小3", "e4": "小4", "e5": "小5", "e6": "小6",
            "j1": "中1", "j2": "中2", "j3": "中3"}


def words():
    with io.open(os.path.join(APP, "words.json"), encoding="utf-8") as f:
        ws = json.load(f)["words"]
    assert len(set(ws)) >= 128, "app/words.json のことばが少なすぎます"
    return ws


def make_password(ws, role):
    n = WORDS_BY_ROLE[role]
    return "%s-%04d" % ("-".join(secrets.choice(ws) for _ in range(n)), secrets.randbelow(10000))


def verifier(password):
    """サーバに置く値。合言葉そのものは入らない（server/scram.py）。"""
    return scram.make_verifier(password)


def upgrade_bundle(path):
    """09-30 に作った束（v1。hash つき）を、いまの形（v2）に書き直す。合言葉は要らない。

    v1 の hash は SCRAM の SaltedPassword そのもので、それだけで入れてしまう値。
    ここで storedKey・serverKey に直し、hash を捨てる。合言葉の表はそのまま使える。
    """
    with io.open(path, encoding="utf-8") as f:
        b = json.load(f)
    n = 0
    for a in b.get("accounts") or []:
        if a.get("alg") == "pbkdf2-600k" and "hash" in a:
            stored, server = scram.keys_from_salted(bytes.fromhex(a.pop("hash")))
            a.update({"alg": scram.ALG, "iters": scram.ITERS, "storedKey": stored, "serverKey": server})
            n += 1
        scram.clean_verifier(a)
    b["v"] = 2
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(b, f, ensure_ascii=False, indent=0)
    os.replace(tmp, path)
    raw = io.open(path, encoding="utf-8").read()
    assert '"hash"' not in raw and '"password"' not in raw
    print("束を書き直しました（%d件を新しい形に）: %s" % (n, path))
    return 0


def class_table():
    """在籍クラス。app/curriculum.js の classes が原本（サーバの class_table と同じ所を読む）。"""
    src = io.open(os.path.join(APP, "curriculum.js"), encoding="utf-8").read()
    m = re.search(r"classes:\s*\[(.*?)\n\s*\]", src, re.S)
    out = []
    for row in re.findall(r"\{([^}]*)\}", m.group(1) if m else ""):
        d = dict(re.findall(r"(\w+):\s*'([^']*)'", row))
        if d.get("id"):
            out.append(d)
    return out


# ------------------------------------------------------------------
# 表（.xlsx）。外の部品を使わずに書く ―― 合言葉を扱う道具に、よそのコードを入れない。
# ------------------------------------------------------------------
def _col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _sheet_xml(rows, widths, freeze=1):
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">']
    if freeze:
        out.append('<sheetViews><sheetView workbookViewId="0"><pane ySplit="%d" topLeftCell="A%d" '
                   'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>' % (freeze, freeze + 1))
    out.append("<cols>%s</cols>" % "".join(
        '<col min="%d" max="%d" width="%s" customWidth="1"/>' % (i + 1, i + 1, w) for i, w in enumerate(widths)))
    out.append("<sheetData>")
    for r, row in enumerate(rows, 1):
        cells = []
        for c, cell in enumerate(row):
            if cell is None or cell == "":
                continue
            text, style = (cell if isinstance(cell, tuple) else (cell, 0))
            cells.append('<c r="%s%d" s="%d" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>'
                         % (_col(c), r, style, escape(str(text))))
        out.append('<row r="%d">%s</row>' % (r, "".join(cells)))
    out.append("</sheetData></worksheet>")
    return "".join(out)


STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
          '<fonts count="3">'
          '<font><sz val="12"/><name val="Arial"/></font>'
          '<font><b/><sz val="12"/><name val="Arial"/></font>'
          '<font><sz val="13"/><name val="Courier New"/></font>'
          '</fonts>'
          '<fills count="3"><fill><patternFill patternType="none"/></fill>'
          '<fill><patternFill patternType="gray125"/></fill>'
          '<fill><patternFill patternType="solid"><fgColor rgb="FFE7F0FA"/><bgColor indexed="64"/></patternFill></fill>'
          '</fills>'
          '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
          '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
          '<cellXfs count="4">'
          '<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
          '<xf numFmtId="49" fontId="1" fillId="2" borderId="0" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1"/>'
          '<xf numFmtId="49" fontId="2" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyFont="1"/>'
          '<xf numFmtId="49" fontId="1" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyFont="1"/>'
          '</cellXfs></styleSheet>')


def write_xlsx(path, sheets):
    """sheets = [(名前, rows, widths)]。rows の各マスは 文字 か (文字, 様式)。様式 1=見出し 2=等幅 3=太字。"""
    names = []
    for name, _, _ in sheets:
        n = re.sub(r"[\[\]:*?/\\]", " ", name)[:31]
        assert n not in names, "同じ名前のシート: %s" % n
        names.append(n)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   + "".join('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1)
                             for i in range(len(sheets)))
                   + '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   '</Relationships>')
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (escape(n, {'"': "&quot;"}), i + 1, i + 1)
                             for i, n in enumerate(names))
                   + '</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i + 1, i + 1)
                             for i in range(len(sheets)))
                   + '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' % (len(sheets) + 1)
                   + '</Relationships>')
        z.writestr("xl/styles.xml", STYLES)
        for i, (_, rows, widths) in enumerate(sheets):
            z.writestr("xl/worksheets/sheet%d.xml" % (i + 1), _sheet_xml(rows, widths))


# ------------------------------------------------------------------
def course_frames():
    """コースの枠と教材台帳（SEED-ロンドン校 3章・4章・1章）。講師は入れない（管理ページで決める）。"""
    os.environ.setdefault("MYACADY_ROOT", os.path.join(ROOT, "server", "data"))
    import courses as C
    import demo_running as D
    times = {c["key"]: c for c in D.KEN_COURSES}
    out = []
    for cid, sub, name, grades, classes in D.FRAMES:
        key = "%s:%s" % (cid, sub)
        d = {"name": name, "grade": grades[0], "subject": sub, "teachers": [], "slots": [],
             "classes": list(classes or []), "students": [],
             "unit": "lesson", "weekday": 0, "from": "", "to": ""}
        if len(grades) > 1:
            d["grades"] = list(grades)
        k = times.get(key)
        if k:
            d["slots"] = C.parse_slots(k["time"])
            if k.get("unit"):
                d["unit"], d["weekday"] = "week", C.DAY[k["unit"]]
        out.append([key, d])
    mats = {mid: {"name": n, "subject": s, "grades": g, "mode": "paper", **({} if graded else {"graded": False})}
            for mid, (n, s, g, graded) in D.SEED_MATERIALS.items()}
    return out, mats


def main():
    ap = argparse.ArgumentParser(description="席・講師・管理者の ID と合言葉を、この Mac の中で作る")
    ap.add_argument("--school", default="waseaca-london", help="校舎ID（英小文字・数字・-）")
    ap.add_argument("--name", default="ロンドン校", help="画面に出す校舎の名前")
    ap.add_argument("--code", default="w", help="ログインIDの頭に付く英小文字1〜2文字")
    ap.add_argument("--per-class", type=int, default=30, help="1クラスの席の数")
    ap.add_argument("--teachers", type=int, default=10)
    ap.add_argument("--admins", type=int, default=1)
    ap.add_argument("--grades", default="e4,e5,e6,j1,j2,j3",
                    help="席を作る学年（小1〜小3は、DPIA を直してから。SEED-ロンドン校 B14）")
    ap.add_argument("--no-courses", action="store_true", help="コースの枠と教材台帳を束に入れない")
    ap.add_argument("--out", default=ROOT, help="書き出す所（既定はこの作業場所の一番上）")
    ap.add_argument("--dry", action="store_true", help="何ができるかだけ言う（何も書かない）")
    ap.add_argument("--upgrade-bundle", action="store_true",
                    help="すでにある束（09-30 の形）を、いまの形に書き直す。合言葉の表はそのまま")
    a = ap.parse_args()
    if a.upgrade_bundle:
        return upgrade_bundle(os.path.join(a.out, "deploy", "accounts", a.school + ".bundle.json"))

    if not re.match(r"^[a-z][a-z0-9-]{1,23}$", a.school) or not re.match(r"^[a-z]{1,2}$", a.code):
        print("× 校舎IDかコードの形が違います")
        return 1
    if not (1 <= a.per_class <= 60 and 0 <= a.teachers <= 40 and 1 <= a.admins <= 3):
        print("× 数が範囲の外です（席 1〜60、講師 0〜40、管理者 1〜3）")
        return 1
    grades = [g for g in a.grades.split(",") if g]
    classes = [c for c in class_table() if c.get("grade") in grades]
    if not classes:
        print("× クラスがありません")
        return 1

    bundle_path = os.path.join(a.out, "deploy", "accounts", a.school + ".bundle.json")
    # **フォルダの名前を .nosync で終える。** この作業場所は iCloud Drive の中にある。ふつうの名前だと、
    # 合言葉そのものが Apple のサーバと、ほかの端末に写される。.nosync で終わるフォルダは写されない。
    sheet_dir = os.path.join(a.out, "合言葉の表.nosync")
    sheet_path = os.path.join(sheet_dir, "tubestudy-合言葉の表-%s.xlsx" % a.school)
    n_seats = len(classes) * a.per_class
    print("校舎 %s（%s）コード %s" % (a.school, a.name, a.code))
    print("  クラス %d（%s）× %d席 ＝ %d席 ／ 講師 %d ／ 管理者 %d"
          % (len(classes), "・".join(c["name"] for c in classes), a.per_class, n_seats, a.teachers, a.admins))
    print("  表   %s" % sheet_path)
    print("  束   %s" % bundle_path)
    if a.dry:
        return 0
    old_sheet = os.path.join(a.out, "合言葉の表", os.path.basename(sheet_path))
    for p in (bundle_path, sheet_path, old_sheet):
        if os.path.exists(p):
            print("× すでにあります: %s" % p)
            print("  作り直すと、表の合言葉とサーバのハッシュが食い違います。")
            print("  席や講師を足すのは、管理ページ（/admin）から。")
            return 1

    ws = words()
    accounts, sheets = [], []
    today = datetime.date.today().isoformat()

    staff = [[("講師と管理者", 3)], [],
             [("役割", 1), ("ID", 1), ("合言葉", 1), ("渡した日", 1), ("メモ（名前は書かない）", 1)]]
    for i in range(1, a.admins + 1):
        lid = "%sadmin%02d" % (a.code, i)
        pw = make_password(ws, "admin")
        accounts.append(dict(verifier(pw), id=lid, role="admin", seat="A%02d" % i, classId="", level=""))
        staff.append(["管理者", (lid, 2), (pw, 2)])
    for i in range(1, a.teachers + 1):
        lid = "%st%02d" % (a.code, i)
        pw = make_password(ws, "teacher")
        accounts.append(dict(verifier(pw), id=lid, role="teacher", seat="T%02d" % i, classId="", level=""))
        staff.append(["講師", (lid, 2), (pw, 2)])
        sys.stdout.write("\r  講師 %d/%d" % (i, a.teachers))
        sys.stdout.flush()
    staff += [[], ["管理者は https://tube-study.uk/admin から入ります。講師は、ふつうの入口から。"]]

    done = 0
    class_sheets = []
    for c in classes:
        rows = [[("%s（%s）" % (c["name"], GRADE_JP.get(c["grade"], c["grade"])), 3)], [],
                [("番号", 1), ("ID", 1), ("合言葉", 1), ("渡した日", 1), ("メモ（名前は書かない）", 1)]]
        for i in range(1, a.per_class + 1):
            seat = "%02d" % i
            lid = "%s%s%s" % (a.code, c["id"], seat)
            pw = make_password(ws, "seat")
            accounts.append(dict(verifier(pw), id=lid, role="seat", seat=seat,
                                 classId=c["id"], level=c["grade"]))
            rows.append([seat, (lid, 2), (pw, 2)])
            done += 1
            if done % 10 == 0:
                sys.stdout.write("\r  席 %d/%d        " % (done, n_seats))
                sys.stdout.flush()
        class_sheets.append((c["name"], rows, [8, 14, 30, 14, 34]))
    print("\r  席 %d/%d ／ 講師 %d ／ 管理者 %d        " % (done, n_seats, a.teachers, a.admins))

    guide = [
        [("TUBE study ―― ID と合言葉の表", 3)], [],
        ["校舎", "%s（%s）" % (a.name, a.school)],
        ["作った日", today],
        ["入っているもの", "小4〜中3 の %d クラス × %d席、講師 %d、管理者 %d" % (len(classes), a.per_class, a.teachers, a.admins)],
        [],
        [("使い方", 3)],
        ["1", "クラスのタブを開き、上から順に1人に1行ずつ渡します（ID と 合言葉）。"],
        ["2", "番号が、そのまま出席番号になります（小4α の 07 番 → 画面では「小4α-07」）。"],
        ["3", "渡した席は、本人がはじめて入ったときに名簿に出ます。紙だけの生徒は、管理ページで「使う」を押します。"],
        ["4", "合言葉は、線（-）を入れなくても、大文字でも入れます。"],
        ["5", "なくしたときは、管理ページの「合言葉を作り直す」。前の合言葉は、その場で使えなくなります。"],
        [],
        [("守ること", 3)],
        ["・", "この表に、生徒や講師の名前を書かない。だれがどの番号かは、先生の手元の名簿で。"],
        ["・", "この表を読めるのは、管理する人だけにする（共有は「制限付き」のまま）。"],
        ["・", "サーバにあるのは ID と、合言葉を確かめるための値だけ。合言葉が読めるのは、この表だけです。入るときも、合言葉は端末から出ません。"],
        ["・", "渡していない席は、名簿にも宿題にも出ません。その合言葉を知っているのは、この表を読める人だけです。"],
    ]
    sheets.append(("はじめに", guide, [16, 90]))
    sheets.append(("講師と管理者", staff, [10, 14, 44, 14, 34]))
    sheets += class_sheets

    bundle = {"kind": "tubestudy-accounts", "v": 2, "made": today,
              "school": {"id": a.school, "name": a.name, "code": a.code, "tz": "Europe/London"},
              "accounts": accounts}
    if not a.no_courses:
        bundle["courses"], bundle["materials"] = course_frames()

    os.makedirs(os.path.dirname(bundle_path), exist_ok=True)
    os.makedirs(sheet_dir, exist_ok=True)
    write_xlsx(sheet_path, sheets)
    os.chmod(sheet_path, 0o600)
    with io.open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=0)
    # 束に合言葉が紛れていないことを、書いたものを読み直して確かめる。
    raw = io.open(bundle_path, encoding="utf-8").read()
    assert '"password"' not in raw and '"hash"' not in raw and not re.search(r"[a-z]{3,8}-[a-z]{3,8}-[a-z]{3,8}-\d{4}", raw), "束に合言葉が入っている"
    print("できました。")
    print("  1. 表を Google スプレッドシートに取り込む（drive.google.com →「新規」→「ファイルのアップロード」→ 開く）")
    print("  2. sh deploy/更新.sh  （束を送って入れます。入るのは ID と、証明を確かめる値だけ）")
    print("  3. https://tube-study.uk/admin に、表の「講師と管理者」タブの「管理者」の行（%sadmin01）で入る" % a.code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
