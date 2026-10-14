#!/bin/sh
# tubestudy のデモを、作業フォルダ（作業.nosync）の写しで動かす／止める。原本には触らない。本番にはつながない。
#     sh 紙の宿題/検査/デモ.sh start     # 写して、デモを作り直し、8935 で動かす（紙の宿題の中継は 8941）
#     sh 紙の宿題/検査/デモ.sh stop
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(cd "$HERE/../.." && pwd)
W="$HERE/作業.nosync"
D="$W/demo"
PORT="${PORT:-8935}"
RPORT="${RPORT:-8941}"
mkdir -p "$W/tmp"
TMPDIR="$W/tmp"; export TMPDIR
stop(){
  for pid in $(pgrep -f "tube_server.py serve --port $PORT"); do kill "$pid"; done
  for pid in $(pgrep -f "relay.py --port $RPORT"); do kill "$pid"; done
}
case "${1:-start}" in
  stop) stop; echo "止めました"; exit 0;;
esac
stop
rsync -a --delete --exclude ".DS_Store" --exclude "__pycache__" "$SRC/app" "$SRC/server" "$SRC/demo-accounts.json" "$W/tube/" || exit 1
cd "$W/tube" || exit 1
rm -rf "$D"; mkdir -p "$D"
MYACADY_ROOT="$D" python3 server/tube_server.py seed --reset >"$W/demo_seed.log" 2>&1
MYACADY_ROOT="$D" python3 server/demo_running.py --school london >"$W/demo_build.log" 2>&1 || { echo "デモを作れませんでした（$W/demo_build.log）"; exit 1; }
MYACADY_ROOT="$D" nohup python3 server/tube_server.py serve --port "$PORT" --demo --demo-file "$D/demo-accounts.json" >"$W/srv.log" 2>&1 &
nohup python3 "$HERE/../relay.py" --port "$RPORT" --tube "http://127.0.0.1:$PORT" >"$W/relay.log" 2>&1 &
sleep 3
curl -s "http://127.0.0.1:$PORT/api/health" >/dev/null && curl -s "http://127.0.0.1:$RPORT/health" >/dev/null || { echo "起きません"; exit 1; }
echo "tubestudy のデモ http://127.0.0.1:$PORT ・ 紙の宿題 http://127.0.0.1:$RPORT"
