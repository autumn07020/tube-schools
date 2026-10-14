#!/bin/sh
# 紙の宿題の検査を一度に回す（原本の tubestudy には触らない。本番にはつながない）。
#     sh 紙の宿題/検査/全部.sh          # 紙の宿題の検査（約5分）
#     TUBE=1 sh 紙の宿題/検査/全部.sh   # tubestudy の検査一式も（さらに約6分）
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$HERE/.." || exit 1
export PYTHONDONTWRITEBYTECODE=1
fail=0
run(){ name="$1"; shift; out=$("$@" 2>&1); last=$(printf "%s\n" "$out" | tail -1); printf "%-10s %s\n" "$name" "$last";
       printf "%s\n" "$last" | grep -q "すべて通った\|JS 構文 OK\|失敗 0 件" || { fail=$((fail+1)); printf "%s\n" "$out" | grep "×" | head -8; }; }
run "構文と印" sh 検査/js検査.sh
run "中継" python3 検査/test_relay.py
sh 検査/デモ.sh start >/dev/null 2>&1 || { echo "デモが起きません"; exit 1; }
run "PDF" python3 検査/pdf_test.py
run "画面から" python3 検査/e2e.py
run "対応表" python3 検査/roster_tool_test.py
sh 検査/デモ.sh stop >/dev/null 2>&1
if [ "${TUBE:-0}" = "1" ]; then run "tubestudy" sh 検査/tubestudy検査.sh; fi
echo "== 失敗 $fail 件 =="
exit $fail
