# カリキュラムの取り込み（2026-10-08）

`カリキュラム/` の 8 つの PDF（本部のカリキュラム・ロンドンの後期日程表）から、
第一信頼情報源 `カリキュラム/カリキュラム.json` と読む用の `カリキュラム.md` を作る道具一式。中身と決めたことは `カリキュラム/README.md`。

## 作り直す
    python3 scripts/curriculum/組み立て/compose.py     # → カリキュラム/カリキュラム.json
    python3 scripts/curriculum/組み立て/render.py      # → カリキュラム/カリキュラム.md
    python3 server/test_syllabus.py                    # 原本・シラバス・日程の不変条件

## 置いてあるもの
- 道具/ … PDF を読む道具（macOS）。`crop.swift`（範囲を切って PNG）、`ocrpng.swift`（Vision で読む。行ごとに y と x）、`ocr.swift`（最初の2倍読み）。
  `parse_e.py`（小4〜6 の第N回の表・3通りの読みの多数決）、`parse_j5.py`（中学の【カリキュラム】表→期ごと）、`parse_k5.py`（5K6K）、`parse_e6b.py`（小6後期）、`parse_tests.py`（小4・小5のテスト日程）、`grid.py`（日程表の格子）、`bands.py`（帯で列を切る）。
- 読み取り/ … OCR の生の文字（2倍＝全頁、3倍＝全頁、4倍右半分＝中学・K の表）。未校正。
- 中間/ … 表ごとの JSON（parse_* の出力）。組み立てはここを読む（環境変数 `CUR_OUT` で場所を変えられる）。
- 組み立て/ … **校正済み**の組み立て。
  - `junior.py` … 中学 21 頁。期の回数（SIZES）・行の手直し（ROWFIX）・単元名の手直し（UNITFIX）・手で起こした頁（HAND：中3 理科3rST・数学3T）。`junior_check.txt` が全ブロックの確認の出力。
  - `elem.py` … 小4・小5（前期・後期）、小6前期。FIX は画像で確かめた直し。総合の回（REVIEW_N）。
  - `kcourse.py` … 5K/6K 国算英。`e6second.py` … 小6後期（社理の回表・算数の下N回・週別の予定を手で起こした）。
  - `tests.py` … 小4・小5のテスト日程。`london.py` … ロンドン後期日程表（画像で確かめた。週の帯）。
  - `clean.py` … OCR の癖の置き換え（安全なものだけ）と「A ⇄ B」の選び方。
  - `compose.py` … 束ねて JSON に。ロンドンの78コース→表の対応（ELEM_CLASSES・K_MAP・JUNIOR_MAP・UNMAPPED）と、週に並べたシラバス（london.syllabi）もここ。
  - `render.py` … JSON → Markdown。
- 旧仮置き/ … 2026-10-08 に外した `server/syllabus/` の仮置き12本（記録として残す。サーバは読まない）。

## 直すとき
- 単元名の誤りは、該当の手直し（UNITFIX／FIX／HAND）に足して compose.py を回す。JSON を手で直さない。
- 新しい日程表（前期など）が来たら、`london.py` に足し、compose.py の lesson_weeks の取り出しを合わせる。
- 対応の無いコース（UNMAPPED）を決めたら、compose.py の対応表に足す。
