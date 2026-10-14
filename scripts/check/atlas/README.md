# 全画面の写し（アトラス）を撮る道具（2026-10-04）

Claude Design への引き継ぎ（`Claude outputs/デザイン引き継ぎ/`）のために作った。**動いている実物の全画面を、番号と行き方つきで撮り、巻ごとの PDF にする。**
デザインを直したあとに撮り直せば、前と後を同じ番号で並べて比べられる。

    S=/tmp/tube-atlas; mkdir -p $S
    rsync -a --exclude .DS_Store --exclude '*.nosync' "…/tube-schools/app" "…/tube-schools/server" "…/tube-schools/scripts" $S/tube/
    sh $S/tube/scripts/check/atlas/run.sh $S "…/tube-schools"

| 道具 | すること |
|---|---|
| `atlaslib.py` | 撮る道具。`Tour.cap(番号つきの名前, 題, 行き方, 補足)`。長い画面は下へ巻いて分ける。紙（重なる面）は中を巻く。`ATLAS_ONLY=01,04` で、その番号だけ撮る |
| `tour_student.py` | 生徒：4つのタブ → メニュー・紙・写真をためる・先生から・保護者の方へ・設定・カメラで丸つけ・毎日テスト（最後まで解く）・対策・にがてつぶし。`base`（タブだけ）・`dark`（暗い配色） |
| `tour_teacher.py` | 講師：宿題 → メッセージ・授業の紙・宿題チェック（写真／対面）・赤を入れる紙 → 成績とコース・生徒の紙・提案・宿題を変える／足す・取り込み → 導入と進度 → メニューの先。`sub`（ほかの講師の要所だけ） |
| `tour_entry.py` | 入口と初回登録：ようこそ・ログイン・幕・登録コード〜完了・登録した直後の空の画面 |
| `tour_admin.py` | 管理ページ：6つのタブと、押せる部品を1種類ずつ押して出てくる紙 |
| `tour_special.py` | 席の行・合言葉・リンク・カード・配る紙と、時期で出る札（組分けの申告・学年の繰り上げ・卒業・使われていない口座）。**校舎を本番に切り替える**ので最後に流す |
| `tour_print.py`・`paper_manifest.py` | 対策テストの紙面と、紙の宿題の道具の写し |
| `build_manifest.py` | 台帳を1つにまとめ、番号（S01・T04…）と巻を決める → `atlas.json` |
| `make_ledger.py`・`make_swatch.py`・`build_book.py` | 画面台帳（.md）・見本帳・巻ごとの PDF（`pdfpage.swift` は PDF のページを絵にして確かめる道具） |
| `crawl.py`・`stats.py`・`tokens.py`・`contact.py` | 探索（押せる部品を1種類ずつ押して、出てくる画面を洗い出す）・画面に出ている形を数える・実物の値を取り出す・べた焼き |

- 土台は `../flows/reset.sh`（デモ校 london＋検査用の校舎。サーバは 8949）。本物のデータには触れない。
- 画面を足したら、該当する `tour_*.py` に `t.cap(...)` を1行足す。番号は続きの数にする（前の番号を振り直さない）。
- PDF の中で、ぼかした影（box-shadow）は灰色の四角に化ける（プレビューの描き方）。見本帳では細い縁だけにしてある。
