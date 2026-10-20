#!/bin/sh
# 流れの検査を、ブラウザごとに全部流す。GitHub の「画面の流れ」（.github/workflows/flows.yml）もこれを呼ぶ（2026-10-20）。
#   sh run.sh <作業の場所> [chrome edge webkit]      （既定は chrome だけ。1つのブラウザで 80 分ほど：流れごとの reset.sh がためしのデモを 4 分かけて作る。10-12）
#   FLOWS="adm_flow6 adm_flow13" sh run.sh <作業の場所>   （流す台本を選ぶ。既定は adm_flow*.py の全部）
# 流れごとに土台を作り直す（reset.sh）。結果は 作業の場所/flows-out/<ブラウザ>-<名前>.out と 作業の場所/結果.md、写しは 作業の場所/shots*/。
# サーバの検査（server/test_*.py）や巡回と同時に流さない（重いと、待ち時間切れで × になる）。
S="$1"; shift; HERE="$(cd "$(dirname "$0")" && pwd)"
[ -d "$S/tube/server" ] || { echo "使い方: sh run.sh <作業の場所> [chrome edge webkit]"; exit 1; }
[ $# -gt 0 ] || set -- chrome
NAMES=${FLOWS:-$(cd "$HERE" && ls adm_flow*.py | sed 's/\.py$//')}   # 台本の名前（道に空白があっても崩れないよう、名前で回す）
for n in $NAMES; do [ -f "$HERE/$n.py" ] || { echo "× 台本が無い: $n"; exit 1; }; done
mkdir -p "$S/flows-out"; fail=0; : > "$S/結果.md"
for b in "$@"; do
  for n in $NAMES; do
    f="$HERE/$n.py"
    sh "$HERE/reset.sh" "$S" > "$S/flows-out/$b-$n.reset.log" 2>&1 || tail -5 "$S/flows-out/$b-$n.reset.log"
    TUBE_BROWSER=$b python3 "$f" "$S" > "$S/flows-out/$b-$n.out" 2>&1
    last=$(tail -1 "$S/flows-out/$b-$n.out" | cut -c1-80)
    case "$last" in すべて通った*) ;; *) fail=$((fail+1)); tail -15 "$S/flows-out/$b-$n.out";; esac
    echo "$b $n: $last"; echo "- $b $n：$last" >> "$S/結果.md"
  done
done
pkill -f "tube_server.py serve --port 8949" 2>/dev/null
echo "== 失敗 $fail 件 =="
[ "$fail" = 0 ]
