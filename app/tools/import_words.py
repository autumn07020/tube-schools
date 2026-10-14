#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自社教材の英単語データを取り込む。

    python3 app/tools/import_words.py 単語.csv --id waseda/j1 --name '英単語 中1' --band 中1

CSVの列（見出し行は日本語でも英語でもよい）

    word,ja,pos,band,note,audio
    reluctant,気が進まない,adj,中1,be reluctant to do の形で使う,reluctant.mp3

    word   … 英語。**これが項目IDのもとになる**（変えると進捗が切れる）
    ja     … 日本語の意味
    pos    … 品詞（n / v / adj / adv / conj）。無くてよい
    band   … 難度の帯。無ければ --band の値
    note   … ひとこと解説。無くてよい
    audio  … 音声ファイル名。app/content/audio/ に置く。無くてよい

出るカード
    英→日（意味を答える）と 日→英（つづりを答える）の**両方**を作る。
    どちらの向きも要る、というのがご要望だった。

    * 英→日 … 表 reluctant ／ 裏 気が進まない
    * 日→英 … 表 気が進まない ／ 裏 reluctant

    項目IDは向きごとに別にする。「見て分かる」と「書ける」は
    別の能力なので、同じ項目として進捗を混ぜると復習の予定が狂う。

著作権について ―― ここを間違えると事業が止まる
----------------------------------------------
**市販の単語帳から語の選定・訳語・例文を写さないこと。**
語の並べ方と訳語の当て方は編集著作物として保護される。
GRIT 2500 は「番号で指す」までにとどめ、中身は入れない
（宿題としては出せる。確認テストのみ、という運用）。

このスクリプトに入れてよいのは
  * 早稲田アカデミーが権利を持つ自社教材
  * ご自身で作成したデータ
のどちらかだけである。取り込むときに出どころを --source で必ず書く。
"""

import argparse
import csv
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_content import bad_chars              # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(os.path.dirname(HERE), "content")

COL = {
    "word": ("word", "英語", "単語", "en"),
    "ja":   ("ja", "日本語", "意味", "訳"),
    "pos":  ("pos", "品詞"),
    "band": ("band", "帯", "レベル", "難度"),
    "note": ("note", "解説", "メモ"),
    "audio": ("audio", "音声", "音"),
}
POS_OK = {"n", "v", "adj", "adv", "conj", "prep", "phr", ""}
WORD_RE = re.compile(r"^[A-Za-z][A-Za-z '\-]{0,39}$")


def pick(row, key):
    for name in COL[key]:
        for k in row:
            if k and k.strip().lower() == name.lower():
                return (row[k] or "").strip()
    return ""


def slug(word):
    return re.sub(r"[^a-z0-9]+", "-", word.lower()).strip("-")


def read(path, default_band):
    rows, problems = [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for i, r in enumerate(csv.DictReader(f), 2):
            w = pick(r, "word")
            ja = pick(r, "ja")
            if not w and not ja:
                continue
            if not WORD_RE.match(w):
                problems.append((i, "英語の形が正しくありません: %r" % w[:24]))
                continue
            if not ja:
                problems.append((i, "日本語の意味が空です: %s" % w))
                continue
            pos = pick(r, "pos").lower()
            if pos not in POS_OK:
                problems.append((i, "知らない品詞です: %r" % pos[:12]))
                continue
            band = pick(r, "band") or default_band
            note = pick(r, "note")
            audio = pick(r, "audio")
            bad = bad_chars(ja + note)
            if bad:
                problems.append((i, "使えない字が入っています: %s" % (bad[:3],)))
                continue
            if audio and not re.match(r"^[\w.\-]{1,60}$", audio):
                problems.append((i, "音声ファイル名が正しくありません: %r" % audio[:24]))
                continue
            rows.append({"w": w, "ja": ja, "pos": pos, "band": band,
                         "note": note, "audio": audio})
    return rows, problems


def write(pack_id, subject, name, rows, source, note):
    path = os.path.join(CONTENT, pack_id + ".js")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    def esc(s):
        return s.replace("\\", "\\\\").replace('"', '\\"')

    bands = []
    for r in rows:
        if r["band"] not in bands:
            bands.append(r["band"])

    out = []
    out.append("/* %s ―― %s" % (name, note))
    out.append("")
    out.append("   **このファイルは app/tools/import_words.py が書き出したもの。**")
    out.append("   手で直さないこと。CSVを直して取り込み直す。")
    out.append("")
    out.append("   出どころ: %s" % source)
    out.append("")
    out.append("   V（英→日）  [英語, 日本語, 帯, 解説, 品詞, 音声]")
    out.append("   W（日→英）  [日本語, 英語, 帯, 解説, 品詞, 音声]")
    out.append("")
    out.append("   向きごとに別の項目として扱う。「見て分かる」と「書ける」は")
    out.append("   別の能力なので、進捗を混ぜると復習の予定が狂う。  */")
    out.append("(function(){")
    out.append('"use strict";')
    out.append("")
    for kind, label in (("V", "英→日"), ("W", "日→英")):
        out.append("/* %s */" % label)
        out.append("var %s = [" % kind)
        for r in rows:
            front, back = (r["w"], r["ja"]) if kind == "V" else (r["ja"], r["w"])
            out.append('["%s","%s","%s","%s","%s","%s"],'
                       % (esc(front), esc(back), esc(r["band"]),
                          esc(r["note"]), esc(r["pos"]), esc(r["audio"])))
        out.append("];")
        out.append("")
    out.append("TubeContent.register({")
    out.append("  id:      '%s'," % pack_id)
    out.append("  subject: '%s'," % subject)
    out.append("  name:    '%s'," % esc(name).replace("'", "\\'"))
    out.append("  note:    '%s'," % esc(note).replace("'", "\\'"))
    out.append("  bands:   [%s]," % ",".join("'%s'" % b for b in bands))
    out.append("  V:V, W:W")
    out.append("});")
    out.append("")
    out.append("})();")
    io.open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
    return path, bands


def main():
    ap = argparse.ArgumentParser(description="自社教材の英単語データを取り込む")
    ap.add_argument("csv")
    ap.add_argument("--id", required=True, help="教材ID（例 waseda/j1）")
    ap.add_argument("--name", required=True, help="画面に出す名前")
    ap.add_argument("--band", default="標準", help="帯が空の行に使う値")
    ap.add_argument("--subject", default="english")
    ap.add_argument("--source", required=True,
                    help="出どころ。'早稲田アカデミー自社教材' など。**必須**")
    ap.add_argument("--yes", action="store_true", help="実際に書き出す")
    a = ap.parse_args()

    if not re.match(r"^[a-z0-9][\w/\-]{1,39}$", a.id):
        print("教材IDは英小文字・数字・/ - _ で2〜40文字にしてください")
        return 1

    rows, problems = read(a.csv, a.band)
    print("読みました: %s" % a.csv)
    print("  使える行   %d" % len(rows))
    print("  はじいた行 %d" % len(problems))
    for ln, why in problems[:12]:
        print("    %d行目: %s" % (ln, why))
    if len(problems) > 12:
        print("    …ほか %d件" % (len(problems) - 12))
    if not rows:
        print("\n取り込める行がありません。")
        return 1

    bands = []
    for r in rows:
        if r["band"] not in bands:
            bands.append(r["band"])
    n_audio = len([1 for r in rows if r["audio"]])
    print()
    print("  帯      %s" % "・".join(bands))
    print("  音声    %d件" % n_audio)
    print("  カード  %d枚（英→日 %d ＋ 日→英 %d）" % (len(rows) * 2, len(rows), len(rows)))
    print("  見本    %s → %s" % (rows[0]["w"], rows[0]["ja"]))

    if not a.yes:
        print("\n実際に書き出すには --yes を付けてください。")
        return 0

    path, bands = write(a.id, a.subject, a.name, rows, a.source,
                        "自社教材から取り込み。英→日と日→英の両方")
    print("\n書き出しました: %s" % path)
    print("\nつぎに、目録（app/content/manifest.js）の packs に1行足してください:")
    print("""
    { id:'%s', subject:'%s', file:'%s.js',
      name:'%s', items:%d,
      bands:[%s],
      note:'%s' },
""" % (a.id, a.subject, a.id, a.name, len(rows) * 2,
       ",".join("'%s'" % b for b in bands), a.source))
    if n_audio:
        print("音声ファイルは app/content/audio/ に置いてください（%d件）。" % n_audio)
    print("最後に検査を通すこと:  python3 app/tools/check-content.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
