#!/bin/sh
# 全画面の写し（アトラス）を撮り直して、台帳と本（PDF）を作る。40分ほど。
#   sh run.sh <作業の場所 S> <tube-schools の場所>
# S/tube に、ソースの写し（app・server・scripts）があること。iCloud の上では流さない（遅い）。
#   S=/tmp/tube-atlas; mkdir -p $S; rsync -a --exclude .DS_Store --exclude '*.nosync' "…/tube-schools/app" "…/tube-schools/server" "…/tube-schools/scripts" $S/tube/
# 出来るもの：S/atlas/shots/（PNG）・S/atlas/atlas.json（台帳）・S/atlas/out/本/（PDF）・S/atlas/out/02-画面台帳.md
# 2026-10-04 は、下と同じ順に手で流した（この1本を通しで流したことは、まだ無い）。
S="$1"; SRC="$2"; HERE="$(cd "$(dirname "$0")" && pwd)"
[ -d "$S/tube/server" ] && [ -d "$SRC/app" ] || { echo "使い方: sh run.sh <作業の場所> <tube-schools の場所>"; exit 1; }
export ATLAS_S="$S"; mkdir -p "$S/atlas/out"; cd "$HERE" || exit 1
rm -rf "$S/demo-base"                                   # デモを今日の日付で作り直す
sh "$S/tube/scripts/check/flows/reset.sh" "$S" | tail -1
# 生徒（iPhone・パソコン・iPad・暗い配色）
ATLAS_PORT=9861 python3 tour_student.py "$S" lj2r01 P
ATLAS_PORT=9861 python3 tour_student.py "$S" lj2r01 D
ATLAS_PORT=9861 python3 tour_student.py "$S" le4b01 P
ATLAS_PORT=9861 python3 tour_student.py "$S" le4b01 D base
ATLAS_ONLY=01,02,03,04,21,22 ATLAS_PORT=9861 python3 tour_student.py "$S" lj1d03 P
ATLAS_PORT=9861 python3 tour_student.py "$S" le5b01 P base
ATLAS_PORT=9861 python3 tour_student.py "$S" lj3r01 P base
ATLAS_PORT=9861 python3 tour_student.py "$S" lj2r01 P dark
ATLAS_PORT=9861 python3 tour_student.py "$S" lj2r01 T base
# 講師
ATLAS_PORT=9881 python3 tour_teacher.py "$S" lteacher1 D
ATLAS_PORT=9881 python3 tour_teacher.py "$S" lteacher1 P
ATLAS_ONLY=01,04,07,08,09,16,17 ATLAS_PORT=9881 python3 tour_teacher.py "$S" lteacher1 T
for l in lteacher2 lteacher3 lteacher4; do ATLAS_PORT=9881 python3 tour_teacher.py "$S" $l D sub; done
# 入口と初回登録・管理ページ・時期で出る札（この順。tour_special は校舎を本番に切り替えるので最後）
ATLAS_PORT=9891 python3 tour_entry.py "$S" P
ATLAS_PORT=9891 python3 tour_entry.py "$S" D
ATLAS_PORT=9895 python3 tour_admin.py "$S" D
python3 tour_special.py "$S"
ATLAS_PORT=9895 python3 tour_admin.py "$S" P pages
python3 tour_print.py "$S"
python3 paper_manifest.py "$S" "$SRC"
# 台帳・見本帳・本
python3 build_manifest.py "$S" && python3 make_ledger.py "$S" && python3 make_swatch.py "$S" && python3 build_book.py "$S"
pkill -f "tube_server.py serve --port 8949" 2>/dev/null
echo "できました：$S/atlas/out/"
