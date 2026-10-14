#!/bin/sh
# 巡回の機械的な部分を1回で回し、**短い要約だけ**を出す（巡回のセッションがトークンを使わずに済むように）。
#
#     sh scripts/check/patrol.sh            # 手元にデモを作り直し、検査を全部走らせる
#     PROD=0 sh scripts/check/patrol.sh     # 本番（読むだけ）を省く
#     KEEP=1 sh scripts/check/patrol.sh     # 終わってもデモを動かしたまま（shots.py で画面を撮るとき。撮る行を最後に出す）
#     SRC=<tube-schools> sh <写し>/patrol.sh # 直した patrol.sh の写しを、iCloud の中身に対して回す（写す前の確かめ）
#
# 止まる終わり方：3＝止める合図がある、4＝Mac が電池で蓋が閉じている（眠るので完走しない。2026-09-26〜27 に3回誤診した）。
# 出す行はおおよそ 40 行。細かい出力は $W/patrol.log に残す。
# 本番には GET しかしない（デモの合言葉でのログインまで。反映・SSH は絶対にしない）。
set -u
SRC="${SRC:-$(cd "$(dirname "$0")/../.." && pwd)}"
W="${W:-/tmp/tube-patrol}"
D="$W/demo"
PORT="${PORT:-8933}"
PROD="${PROD:-1}"
KEEP="${KEEP:-0}"
LOG="$W/patrol.log"
STOP="$SRC/巡回を止める.txt"

if [ -f "$STOP" ]; then
  echo "止める合図（巡回を止める.txt）があります。何もしません。"
  exit 3
fi
# 電池で蓋が閉じた Mac は約15分に20秒しか起きない。デモの段が終わらず、巡回が黙って止まる。
batt=$(pmset -g batt 2>/dev/null)
lid=$(ioreg -r -k AppleClamshellState -d 4 2>/dev/null | grep -c '"AppleClamshellState" = Yes')
case "$batt" in *"Battery Power"*) power="電池 $(printf "%s" "$batt" | grep -o '[0-9]*%' | head -1)" ;; *) power="電源" ;; esac
[ "$lid" -gt 0 ] && lidw="閉" || lidw="開"
if [ "$power" != "電源" ] && [ "$lidw" = "閉" ]; then
  echo "Mac が電池で蓋が閉じています（$power）。眠るので巡回は完走しません。何もしません。"
  exit 4
fi
mkdir -p "$W"
: > "$LOG"
say(){ printf "%s\n" "$*"; }
# 蓋が開いていても、電池では1分触らないと眠る（pmset sleep 1）。この巡回が終わるまで眠らせない。
# 電源で蓋が閉じた Mac は「暗い目覚め」（DarkWake。約15分に30秒）の中で呼ばれる。-i だけでは眠りへ戻り、
# 8分の巡回に1時間かかった（2026-09-29）。-s は電源につながっている間だけ、眠りへ戻るのを止める。
# どちらも巡回が終わると外れる。設定（pmset）は変えない。
caffeinate -is -w $$ 2>/dev/null &
wake=$(pmset -g log 2>/dev/null | grep -E ' (Sleep|Wake|DarkWake)  ' | tail -1 | awk '{print $4}')
case "$wake" in DarkWake|Sleep) wakew="暗い目覚めの中" ;; Wake) wakew="起きている" ;; *) wakew="目覚めは不明" ;; esac

say "== 巡回 $(date '+%Y-%m-%d %H:%M') =="
say "Mac   $power ／ 蓋 $lidw ／ $wakew ／ 巡回の間は眠らせない（caffeinate -is）"
# ---- 1. 写す（iCloud → 作業用） ----
rsync -a --delete --exclude ".DS_Store" --exclude "__pycache__" --exclude "/カリキュラム/*.pdf" "$SRC/app" "$SRC/server" "$SRC/カリキュラム" "$SRC/demo-accounts.json" "$SRC/scripts" "$W/tube/" 2>>"$LOG" || { say "写せませんでした（rsync）"; exit 1; }
cd "$W/tube" || exit 1

# ---- 2. 構文・ソース ----
r1=$(sh app/tools/js構文.sh 2>&1 | tail -1)
r2=$(python3 app/tools/check-source.py 2>&1 | tail -1)
say "構文  $r1 / ソース $r2"

# ---- 3. サーバの検査（要約行だけ） ----
fail=0
for t in server/test_*.py; do
  n=$(basename "$t" .py)
  if python3 "$t" >"$W/$n.log" 2>&1; then
    say "OK   $n  $(tail -1 "$W/$n.log")"
  else
    fail=$((fail+1)); say "×    $n  $(grep -m3 '×' "$W/$n.log" | tr '\n' ' ')"
  fi
done

# ---- 4. デモを作り直して起動（8933） ----
for pid in $(pgrep -f "tube_server.py serve --port $PORT"); do kill "$pid"; done
rm -rf "$D"; mkdir -p "$D"
MYACADY_ROOT="$D" python3 server/tube_server.py seed --reset >>"$LOG" 2>&1
MYACADY_ROOT="$D" python3 server/demo_running.py --school london >"$W/demo_build.log" 2>&1 || { say "デモを作れませんでした（$W/demo_build.log）"; fail=$((fail+1)); }
say "デモ  $(grep -m1 '出した宿題' "$W/demo_build.log" | sed 's/^ *//')"
MYACADY_ROOT="$D" nohup python3 server/tube_server.py serve --port "$PORT" --demo --demo-file "$D/demo-accounts.json" >"$W/srv.log" 2>&1 &
SRVPID=$!
sleep 3
curl -s "http://127.0.0.1:$PORT/api/health" >/dev/null || { say "サーバが起きません"; fail=$((fail+1)); }

# ---- 5. 自己攻撃・意味の検査（手元） ----
say "攻撃  $(ATTACK_BASE=http://127.0.0.1:$PORT python3 server/attack.py 2>&1 | tail -1)"
python3 "$SRC/scripts/check/expect.py" --base "http://127.0.0.1:$PORT" --accounts "$D/demo-accounts.json" \
  --ledger "$SRC/scripts/check/ledger-local.json" >"$W/expect-local.log" 2>&1
e=$?
say "意味（手元） $(tail -1 "$W/expect-local.log")"
[ "$e" -ne 0 ] && { fail=$((fail+1)); grep -v "^  OK" "$W/expect-local.log" | grep "×\|→" | head -12; }
if [ "$KEEP" = "1" ]; then
  say "デモは $PORT で動いたまま（止める：kill $SRVPID）"
  say "撮る  python3 \"$W/tube/scripts/check/shots.py\" --base http://127.0.0.1:$PORT --accounts \"$D/demo-accounts.json\" \"$W/shots\" [job名 …]"
else
  kill "$SRVPID" 2>/dev/null; wait "$SRVPID" 2>/dev/null
fi

# ---- 6. 本番（読むだけ。許可 A） ----
if [ "$PROD" = "1" ]; then
  python3 "$SRC/scripts/check/expect.py" --base "https://tube-study.uk" --accounts "$SRC/deploy/demo-accounts.json" \
    --ledger "$SRC/scripts/check/ledger-production.json" >"$W/expect-prod.log" 2>&1
  e=$?
  say "意味（本番） $(tail -1 "$W/expect-prod.log")"
  [ "$e" -ne 0 ] && { fail=$((fail+1)); grep -v "^  OK" "$W/expect-prod.log" | grep "×\|→" | head -12; }
fi

# ---- 7. 手元と本番のコードが同じか（iCloud と本番の app のハッシュは取れないので、反映日だけ） ----
say "iCloud の最終更新  $(find "$SRC/app" "$SRC/server" -type f -newer "$SRC/scripts/check/ledger-local.json" 2>/dev/null | grep -v .DS_Store | wc -l | tr -d ' ') ファイルが前回の巡回より新しい"

say "== 失敗 $fail 件 =="
exit $fail
