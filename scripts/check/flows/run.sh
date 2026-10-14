#!/bin/sh
# 流れの検査を、ブラウザごとに全部流す。
#   sh run.sh <作業の場所> [chrome edge webkit]      （既定は chrome だけ。1つのブラウザで 80 分ほど：流れごとの reset.sh がためしのデモを 4 分かけて作る。10-12）
# 流れごとに土台を作り直す（reset.sh）。結果は 作業の場所/flows-out/<ブラウザ>-<名前>.out、写しは 作業の場所/shots*/。
# サーバの検査（server/test_*.py）や巡回と同時に流さない（重いと、待ち時間切れで × になる）。
S="$1"; shift; HERE="$(cd "$(dirname "$0")" && pwd)"
[ -d "$S/tube/server" ] || { echo "使い方: sh run.sh <作業の場所> [chrome edge webkit]"; exit 1; }
[ $# -gt 0 ] || set -- chrome
mkdir -p "$S/flows-out"; fail=0
for b in "$@"; do
  for f in "$HERE"/adm_flow*.py; do
    n=$(basename "$f" .py)
    sh "$HERE/reset.sh" "$S" > /dev/null 2>&1
    TUBE_BROWSER=$b python3 "$f" "$S" > "$S/flows-out/$b-$n.out" 2>&1
    last=$(tail -1 "$S/flows-out/$b-$n.out" | cut -c1-80)
    case "$last" in すべて通った*) ;; *) fail=$((fail+1));; esac
    echo "$b $n: $last"
  done
done
pkill -f "tube_server.py serve --port 8949" 2>/dev/null
echo "== 失敗 $fail 件 =="
[ "$fail" = 0 ]
