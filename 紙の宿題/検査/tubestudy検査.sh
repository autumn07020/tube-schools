#!/bin/sh
# tubestudy の検査を、原本に触らずに一式回す（巡回の patrol.sh と同じ中身。置き場だけ違う）。
#
#     sh 紙の宿題/検査/tubestudy検査.sh          # 原本を写して、検査を全部
#     KEEP=1 sh 紙の宿題/検査/tubestudy検査.sh   # 終わってもデモのサーバを止めない（紙の宿題の検査に使う）
#
# 作業場は この横の 作業.nosync/（iCloud に同期しない）。本番には一切つながない。
# 意味の検査の ledger は写しを使う（原本の ledger-local.json を書き換えない）。
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(cd "$HERE/../.." && pwd)
W="$HERE/作業.nosync"
D="$W/demo"
PORT="${PORT:-8935}"
LOG="$W/check.log"
mkdir -p "$W"
: > "$LOG"
say(){ printf "%s\n" "$*"; }

say "== tubestudy の検査 $(date '+%Y-%m-%d %H:%M') =="
rsync -a --delete --exclude ".DS_Store" --exclude "__pycache__" "$SRC/app" "$SRC/server" "$SRC/demo-accounts.json" "$SRC/scripts" "$W/tube/" 2>>"$LOG" || { say "写せませんでした"; exit 1; }
[ -f "$W/ledger-local.json" ] || cp "$SRC/scripts/check/ledger-local.json" "$W/ledger-local.json"
cd "$W/tube" || exit 1
# 検査の仮の置き場は /tmp に決め打ちしてある。tube-schools の外に出ないよう、**写しの中だけ**差し替える。
mkdir -p "$W/tmp"
TMPDIR="$W/tmp"; export TMPDIR
for f in server/test_*.py app/tools/*.py; do
  grep -q '"/tmp' "$f" && sed -i '' "s|\"/tmp|\"$W/tmp|g" "$f"
done

r1=$(sh app/tools/js構文.sh 2>&1 | tail -1)
r2=$(python3 app/tools/check-source.py 2>&1 | tail -1)
say "構文  $r1 / ソース $r2"

fail=0
for t in server/test_*.py; do
  n=$(basename "$t" .py)
  if python3 "$t" >"$W/$n.log" 2>&1; then
    say "OK   $n  $(tail -1 "$W/$n.log")"
  else
    fail=$((fail+1)); say "×    $n  $(grep -m3 '×' "$W/$n.log" | tr '\n' ' ')"
  fi
done

for pid in $(pgrep -f "tube_server.py serve --port $PORT"); do kill "$pid"; done
rm -rf "$D"; mkdir -p "$D"
MYACADY_ROOT="$D" python3 server/tube_server.py seed --reset >>"$LOG" 2>&1
MYACADY_ROOT="$D" python3 server/demo_running.py --school london >"$W/demo_build.log" 2>&1 || { say "デモを作れませんでした"; fail=$((fail+1)); }
say "デモ  $(grep -m1 '出した宿題' "$W/demo_build.log" | sed 's/^ *//')"
MYACADY_ROOT="$D" nohup python3 server/tube_server.py serve --port "$PORT" --demo --demo-file "$D/demo-accounts.json" >"$W/srv.log" 2>&1 &
SRVPID=$!
sleep 3
curl -s "http://127.0.0.1:$PORT/api/health" >/dev/null || { say "サーバが起きません"; fail=$((fail+1)); }

say "攻撃  $(ATTACK_BASE=http://127.0.0.1:$PORT python3 server/attack.py 2>&1 | tail -1)"
python3 scripts/check/expect.py --base "http://127.0.0.1:$PORT" --accounts "$D/demo-accounts.json" \
  --ledger "$W/ledger-local.json" >"$W/expect-local.log" 2>&1
e=$?
say "意味（手元） $(tail -1 "$W/expect-local.log")"
[ "$e" -ne 0 ] && { fail=$((fail+1)); grep -v "^  OK" "$W/expect-local.log" | grep "×\|→" | head -12; }
if [ "${KEEP:-0}" = "1" ]; then
  say "デモのサーバは動かしたまま: http://127.0.0.1:$PORT （pid $SRVPID）"
else
  kill "$SRVPID" 2>/dev/null; wait "$SRVPID" 2>/dev/null
fi
say "== 失敗 $fail 件 =="
exit $fail
