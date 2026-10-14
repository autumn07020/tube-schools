# 画面の自動検査の道具（2026-09-23。09-28 に expect.py・patrol.sh・控えを足した）

一時領域（/private/tmp の scratchpad）は数日で消えるので、道具はここに置く。

- `expect.py` …… 意味の検査。動いているデモに不変条件を当て、前回の数の控えと比べる。`--base` と `--ledger` を必ず付ける。
  控えの `講師.hidden.todo` は、今日やることに出ていない回に残った未評価の数。0 でなければ、講師に見えない仕事がある（09-30）。
- `patrol.sh` …… 巡回の検査を1本で回し、要約だけを出す（デモは 8933）。使い方と終わり方（3・4）は先頭の注。
- `ledger-local.json`・`ledger-production.json` …… 前回の数の控え（手元・本番）。patrol.sh が expect.py に渡して書く。
  `ledger.json` は `--ledger` を付けずに回したときの控えで、09-24 から動いていない。比べる相手にしない。
- `cdp.py` …… Chrome を裏で動かして、画面を撮る・JS を走らせる（外部ライブラリなし。websocket を自前で実装）。
  **`TUBE_BROWSER=edge`** で Edge、**`TUBE_BROWSER=webkit`** で Safari と同じエンジンに切り替わる（10-01）。expect.py も流れの検査も、そのまま流せる。
- `atlas/` …… **全画面の写し**（番号と行き方つきで撮り、巻ごとの PDF にする。Claude Design への引き継ぎと、作り直しの前後の比べに使う。`atlas/README.md`）
- `flows/` …… **流れの検査**（画面を実際に押す台本と、その土台。`flows/README.md`。⑥ 宿題の往復 adm_flow12、⑦ ためし運用のデモ adm_flow13、⑧ 今日やることの札の密度 adm_flow14、⑨ ずれの検査 adm_flow15、⑩ 初回登録の枠と全画面の動画 adm_flow16。土台 reset.sh は本物の形の校舎に時間割・担当・ためしのデモ（demo_trial.py）まで入れる）。`sh flows/run.sh <作業の場所> chrome edge webkit`。
- `wk.swift`・`wk.py` …… **Safari と同じ WebKit** を、画面の外の窓で直に動かす（cdp.Chrome と同じ形：goto・eval・shot・wait_for）。
  はじめの1回だけ `swiftc` で組み立てる（数秒。置き場は一時領域）。本人の Safari・履歴・クッキーには触れない（保存しないデータ置き場）。
  ページのエラー・CSP 違反は `window.__wkerrs`（`page_errors()`）。写しに `backdrop-filter` のぼかしは写らない（下の文字が透けて見えるのは写しだけ）。
  **確かめられないもの**：Safari のアプリの部品（合言葉を保存する吹き出し・Face ID の自動入力・タブバー）と、iPhone の指。
  Safari のアプリそのものを動かすには、Safari の設定 →「デベロッパ」→「リモートオートメーションを許可」が要る（本人が入れる。こちらからは変えない）。
- `shots.py` …… デモ（既定 127.0.0.1:8932。`--base` で変える）に「ためしに見る」の9人で入り、講師の 導入と進度・宿題チェック、生徒の 宿題・毎日テスト を撮って、段階が効いているかを印字する。

## 使い方
    # 1. 作業用に写して、デモを作り、8932 で起動する
    W=/tmp/tube; rsync -a --exclude .DS_Store "…/tube-schools/app" "…/tube-schools/server" "…/tube-schools/demo-accounts.json" $W/
    cd $W && MYACADY_ROOT=/tmp/tube-demo python3 server/tube_server.py seed --reset
    MYACADY_ROOT=/tmp/tube-demo python3 server/demo_running.py --school london
    MYACADY_ROOT=/tmp/tube-demo python3 server/tube_server.py serve --port 8932 --demo --demo-file /tmp/tube-demo/demo-accounts.json &
    # 2. 撮る（アカウントは既定で tube-schools/demo-accounts.json。デモを作った所の写しを渡すのが確実）
    python3 shots.py --accounts /tmp/tube-demo/demo-accounts.json shots            # 全部
    python3 shots.py --accounts /tmp/tube-demo/demo-accounts.json shots t2 s-j3r01  # 名前を指定

    # 巡回から撮るとき：KEEP=1 で patrol.sh を回すと、デモ（8933）を止めずに終わり、そのまま流せる撮る行を最後に出す
    KEEP=1 PROD=0 W=… sh scripts/check/patrol.sh

## 不変条件を足したら、壊して確かめる
1. 作業用の写し（`$W/tube`）の該当の1行を壊す。iCloud は触らない。
2. **置き換えた数を見る**（`grep -c`）。sed は 0 件でも黙って終わり、検査が「通った」と見える（09-28）。
3. 検査を回して × になるのを見る。ならなければ、その不変条件は何も捕まえていない。
4. 写しを戻し、○ に戻るのを見てから iCloud へ写す。

## 知っておくこと
- **サーバの検査（server/test_*.py）は、置き場が決まった名前**（`/tmp/test-admin` など）。同じ検査を2つ同時に流すと、互いの口座と印を壊して × になる
  （10-01、巡回と手の検査が重なって test_admin が 2件 ×。単独で流すと ○）。巡回が動いているあいだは、手で流さない。
- 8932 には前のセッションのデモが動いたままのことがある（09-23 に起動したものが 09-28 も動いていた）。
  `--base` を付けずに expect.py・shots.py を回すと、古いコードのデモを見る。先に `lsof -nP -iTCP:8932 -sTCP:LISTEN` と起動日を見る。
- 手元の Python のサーバは、部品の並列読み込みで接続を切ることがあった（待ち行列 5）。`tube_server.py serve` は 128 に広げた。
  それでも欠けたら `open_app` が読み直す。
- サーバの検査は `python3 server/test_use.py`（導入の段階）ほか、CLAUDE.md の一覧。
- **`ledger-local.json`（手元の控え）は patrol.sh のデモの形**（`seed --reset`＝seed の検査用口座が入ったまま）。流れの検査の reset.sh は `seed --reset --empty` なので、
  そのデモに控えを当てると `lteacher3.j1tr:english.students 17→8`・`lteacher4.j3:social.students 18→9` と「減った」に見える（seed の中3T 9 人・中1R 3 人などが無いだけ。10-08）。
  控えと比べるときは patrol.sh と同じ作り方のデモで。流れのデモで expect.py を回すなら `--ledger` に別の控えを渡す。
