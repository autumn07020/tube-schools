#!/bin/sh
# 紙の宿題を、この Mac で動かす（本番の tubestudy につなぐ）。止めるときは control + C。
#
#     sh 紙の宿題/起動.sh          # この Mac の Safari で開く： http://127.0.0.1:8940
#     sh 紙の宿題/起動.sh ipad     # 同じ Wi-Fi の iPad からも開く（家の Wi-Fi で試すときだけ。下の注意）
#
# 注意：ipad のときは、iPad とこの Mac のあいだを http:// で話す（合言葉が暗号化されない）。
#       校舎の Wi-Fi では使わない。校舎では README の「置き方」（HTTPS）で動かす。
cd "$(dirname "$0")" || exit 1
TUBE="${TUBE:-https://tube-study.uk}"
PORT="${PORT:-8940}"
if [ "${1:-}" = "ipad" ]; then
  NAME=$(scutil --get LocalHostName 2>/dev/null || hostname)
  echo "iPad の Safari で開く： http://$NAME.local:$PORT"
  exec python3 relay.py --tube "$TUBE" --host 0.0.0.0 --port "$PORT"
fi
echo "この Mac の Safari で開く： http://127.0.0.1:$PORT"
exec python3 relay.py --tube "$TUBE" --port "$PORT"
