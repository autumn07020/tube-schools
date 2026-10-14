#!/bin/sh
# Tube for Schools を動かしつづける。
#
# なぜ要るか
# ----------
# 講師に配ったURLが、ある日「サーバーが見つかりません」になった。
# 原因はサーバではなくトンネルで、10:06に切れたあと再接続に失敗し続け、
# **誰も気づかないまま半日止まっていた**。
#
# 落ちること自体は防げない（Quick Tunnel は無料で保証が無い）。
# 防ぐべきは「落ちたまま放置される」ことである。だからここでは
#   1. サーバとトンネルの両方を見張る
#   2. 死んでいたら すぐ入れ直す
#   3. いまのURLを必ず1つのファイルに書く（deploy/URL.txt）
# の3つだけをやる。
#
#     sh deploy/run.sh              動かす（画面を閉じても続く）
#     cat deploy/URL.txt            いまのURLを見る
#     sh deploy/run.sh stop         止める
#
# **URLは切れるたびに変わる。** 変わったら配り直しになるので、
# 本番では独自ドメイン（deploy/README.md）に移すこと。
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
PORT=${PORT:-8765}
CF=${CF:-/Users/aki/bin/cloudflared}
LOG=$HERE/log
URLFILE=$HERE/URL.txt
PIDFILE=$HERE/run.pid

mkdir -p "$LOG"

# いまのURLへ飛ぶだけのファイルを、プロジェクトの一番上に置く。
#
# URLは切れるたびに変わる。そのたびに配り直すのは続かない。
# ここは iCloud の中なので、**iPhone の「ファイル」からも同じものが開ける**。
# 講師には「このファイルをお気に入りに入れてください」と伝えれば、
# URLが変わっても各自が最新に飛べる。
#
# 根本の解決ではない（deploy/URLを固定する.md を参照）。
# ドメインを取るまでのあいだの、当座の受け皿である。
write_shortcut() {
  u="$1"
  [ -z "$u" ] && return 0
  cat > "$ROOT/いまのURL.html" <<HTML
<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>Tube for Schools をひらく</title>
<meta http-equiv="refresh" content="0; url=$u">
<style>body{font-family:-apple-system,"Hiragino Sans",sans-serif;
background:#FBFAF8;color:#17150F;margin:0;
display:flex;min-height:100vh;align-items:center;justify-content:center}
.b{text-align:center;padding:32px}
a{display:inline-block;margin-top:20px;padding:14px 28px;border-radius:14px;
background:#005BAC;color:#fff;text-decoration:none;font-size:17px}
p{color:#6B655D;font-size:14px;line-height:1.7}</style></head>
<body><div class="b">
<h1>Tube for Schools</h1>
<p>ひらいています…<br>ひらかないときは、下を押してください。</p>
<a href="$u">ひらく</a>
<p style="margin-top:24px;font-size:12px">
このファイルは、いまのURLへ飛ぶだけのものです。<br>
URLが変わっても、ここを開けば最新につながります。<br>
$(date '+%Y-%m-%d %H:%M') 時点</p>
</div></body></html>
HTML
}

stop() {
  [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null
  rm -f "$PIDFILE"
  pkill -f "tube_server.py serve" 2>/dev/null
  # 使い捨てと名前付きの両方を止める。前は使い捨ての形しか
  # 書いていなかったため、名前付きのトンネルが残り続けていた。
  pkill -f "cloudflared tunnel .*127.0.0.1:$PORT" 2>/dev/null
  echo "止めました。"
}

[ "${1:-}" = "stop" ] && { stop; exit 0; }

# サーバだけ入れ替える。**トンネルは触らない。**
#
# 直したものを反映するたびに run.sh を止めて起動し直していた。
# するとトンネルも張り直され、**配ったURLが毎回死ぬ**。
# 実際、直した直後に「サーバーに接続できない」と言われたのは
# Cloudflare が落ちたからではなく、こちらが入れ替えたからだった。
#
# トンネルは 127.0.0.1:8765 を見ているだけなので、
# その先のサーバを差し替えてもURLは変わらない。
[ "${1:-}" = "reload" ] && {
  pkill -f "tube_server.py serve" 2>/dev/null
  sleep 1
  DEMOFLAG=""
  [ "${DEMO:-1}" = "1" ] && DEMOFLAG="--demo"
  HOSTFLAG=""
  [ "${LAN:-0}" = "1" ] && HOSTFLAG="--host 0.0.0.0"
  (cd "$ROOT" && MYACADY_ROOT="${MYACADY_ROOT:-$HOME/myAcady}" \
     python3 server/tube_server.py serve --port "$PORT" $DEMOFLAG $HOSTFLAG \
     >> "$LOG/server.log" 2>&1) &
  sleep 3
  c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 \
      "http://127.0.0.1:$PORT/" 2>/dev/null)
  # 変数のあとに日本語が続くときは必ず ${} で囲む。
  # `${c}）` と書くと sh は全角の「）」まで変数名として読み、
  # 「unbound variable」で止まる。
  echo "$(date '+%F %T') サーバを入れ替えました（${c}）" >> "$LOG/watch.log"
  echo "サーバを入れ替えました（${c}）。URLは変わっていません:"
  cat "$URLFILE" 2>/dev/null
  exit 0
}

# **状態番号まで見ること。**
# curl は -f を付けないかぎり、HTTPエラーでも成功で返る。
# トンネルが切れたとき Cloudflare は 530 を返すので、
# 「curl が成功した＝生きている」と見なすと**永遠に直らない**
# （実際そうなっていて、切れたまま半日気づかなかった）。
ok_code() { case "$1" in 2*|3*) return 0 ;; *) return 1 ;; esac; }

alive_server() {
  c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
      "http://127.0.0.1:$PORT/" 2>/dev/null)
  ok_code "$c"
}
# トンネルが生きているか。
#
# **名前が引けないのは、トンネルの故障ではない。**
# macOS は新しいホスト名をしばらくキャッシュに入れず、
# dig では引けるのに curl が「解決できない」と言う。これを
# 故障とみなすと、生きているトンネルを捨てて張り直す連鎖になる
# （実際、200を返しているトンネルを何本も捨てていた）。
# 名前が引けないときは dig の答えで直接あたる。
# トンネルが生きているか。
#
# **外から叩いて確かめてはいけない。**
#
# 最初はURLに curl していた。ところがこのMacは、新しいホスト名を
# しばらく名前解決できない。すると 000 が返り、見張りは「死んだ」と
# 判断して張り直す。**張り直すとURLが変わる。** 変わった先もまた
# 名前解決できず、また張り直す ―― これを19本ぶん繰り返していた。
#
# ログにはっきり残っていた。
#     INF Initiating graceful shutdown due to signal terminated
# これは Cloudflare が切ったのではなく、**見張りが殺した跡**である。
#
# 生きているかどうかは、手元だけで分かる。
#   1. cloudflared のプロセスがいるか
#   2. そのログに「接続できた」があり、そのあと「あきらめた」が無いか
# 名前解決も、向こう側の応答も要らない。
alive_tunnel() {
  [ -s "$URLFILE" ] || return 1
  pgrep -f "cloudflared tunnel .*127.0.0.1:$PORT" >/dev/null 2>&1 || {
    echo "$(date '+%F %T') cloudflared がいません" >> "$LOG/watch.log"
    return 1
  }
  # 登録できたことが一度もなければ、まだ張れていない
  grep -q "Registered tunnel connection" "$LOG/tunnel.log" 2>/dev/null || {
    echo "$(date '+%F %T') まだ接続できていません" >> "$LOG/watch.log"
    return 1
  }
  # 最後の登録より後に「もう接続が無い」が出ていたら、あきらめている
  last_ok=$(grep -n "Registered tunnel connection" "$LOG/tunnel.log" \
            2>/dev/null | tail -1 | cut -d: -f1)
  last_ng=$(grep -n "no more connections active" "$LOG/tunnel.log" \
            2>/dev/null | tail -1 | cut -d: -f1)
  if [ -n "$last_ng" ] && [ "${last_ng:-0}" -gt "${last_ok:-0}" ]; then
    echo "$(date '+%F %T') 接続が切れたままです" >> "$LOG/watch.log"
    return 1
  fi
  return 0
}

start_server() {
  echo "$(date '+%F %T') サーバを起動します" >> "$LOG/watch.log"
  # DEMO=1 のときだけ、画面にデモ用の合言葉を出す。
  # 講師に見てもらう間は 1。本番の名簿を入れたら必ず 0 にすること
  # ―― URLを知っている人が誰でも入れる状態になる。
  DEMOFLAG=""
  [ "${DEMO:-1}" = "1" ] && DEMOFLAG="--demo"
  # LAN=1 のときだけ、同じWi-Fiの端末から入れるように口を開ける。
  # **暗号化されない。** 合言葉がそのまま無線に流れるので、
  # 本物の生徒の記録を入れたあとは使わないこと。
  HOSTFLAG=""
  [ "${LAN:-0}" = "1" ] && HOSTFLAG="--host 0.0.0.0"
  (cd "$ROOT" && MYACADY_ROOT="${MYACADY_ROOT:-$HOME/myAcady}" \
     python3 server/tube_server.py serve --port "$PORT" $DEMOFLAG $HOSTFLAG \
     >> "$LOG/server.log" 2>&1) &
  sleep 3
}

# 名前付きトンネル（CF_NAME を入れたとき）。
#
# **こちらはURLが変わらない。** 使い捨ての Quick Tunnel と違い、
# 自分のドメインに紐づいているので、切れても張り直しても同じ。
# 作り方は deploy/URLを固定する.md を見ること。
start_named() {
  echo "$(date '+%F %T') 名前付きトンネル $CF_NAME を張ります" >> "$LOG/watch.log"
  pkill -f "cloudflared tunnel .*run .*$CF_NAME" 2>/dev/null
  sleep 1
  [ -f "$LOG/tunnel.log" ] && cat "$LOG/tunnel.log" >> "$LOG/tunnel-old.log"
  : > "$LOG/tunnel.log"
  "$CF" tunnel --no-autoupdate --protocol http2 \
        run --url "http://127.0.0.1:$PORT" "$CF_NAME" \
        >> "$LOG/tunnel.log" 2>&1 &
  # 名前付きのURLは自分で決めたもの。ログから拾う必要がない。
  # CF_HOST を入れておけば、URL.txt と いまのURL.html もそこを指す。
  if [ -n "${CF_HOST:-}" ]; then
    echo "https://$CF_HOST" > "$URLFILE"
    write_shortcut "https://$CF_HOST"
  fi
  # つながるまで待つ（最大40秒）。ログに「登録できた」が出たら完了。
  j=0
  while [ $j -lt 20 ]; do
    grep -q "Registered tunnel connection" "$LOG/tunnel.log" 2>/dev/null && break
    sleep 2
    j=$((j+1))
  done
  if grep -q "Registered tunnel connection" "$LOG/tunnel.log" 2>/dev/null; then
    echo "$(date '+%F %T') つながりました（$((j*2))秒）" >> "$LOG/watch.log"
    return 0
  fi
  echo "$(date '+%F %T') 張れませんでした。ログ: $LOG/tunnel.log" >> "$LOG/watch.log"
  return 1
}

start_tunnel() {
  # 名前付きが指定されていれば、そちらを使う（URLが変わらない）
  if [ -n "${CF_NAME:-}" ]; then
    start_named
    return $?
  fi
  echo "$(date '+%F %T') トンネルを張り直します" >> "$LOG/watch.log"
  pkill -f "cloudflared tunnel --url http://127.0.0.1:$PORT" 2>/dev/null
  sleep 1
  # 前の記録を消さない。**なぜ切れたのかは、切れた側のログにしか無い。**
  # 消していたせいで、5分で切れる理由がずっと分からなかった。
  [ -f "$LOG/tunnel.log" ] && cat "$LOG/tunnel.log" >> "$LOG/tunnel-old.log"
  : > "$LOG/tunnel.log"
  # 接続は http2 にする。既定の QUIC(UDP) は、途中の機器や
  # 無線の具合で黙って落ちることがある。学校や家庭の回線では
  # UDP が絞られていることも多い。http2 は TCP なので通りやすい。
  "$CF" tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate \
        --protocol http2 --retries 10 \
        >> "$LOG/tunnel.log" 2>&1 &
  # URLが出るまで最大60秒待つ
  i=0
  while [ $i -lt 30 ]; do
    U=$(grep -o "https://[a-z0-9-]*\.trycloudflare\.com" "$LOG/tunnel.log" | head -1)
    if [ -n "$U" ]; then
      echo "$U" > "$URLFILE"
      echo "$(date '+%F %T') $U" >> "$LOG/url-history.log"
      write_shortcut "$U"
      # **URLが出てから、実際に繋がるまで少しかかる。**
      # 出た直後に見に行くと 000 が返り、張ったばかりのトンネルを
      # 捨ててまた張る、という無駄がおきる（ログにそう残っていた）。
      # 通るまで最大40秒だけ待つ。
      # 張れたことは、cloudflared のログで分かる。
      # ここで外から叩きに行くと、名前解決できないだけで
      # 「失敗」と受け取り、張ったばかりのものを捨ててしまう。
      j=0
      while [ $j -lt 20 ]; do
        grep -q "Registered tunnel connection" "$LOG/tunnel.log" 2>/dev/null && break
        sleep 2
        j=$((j+1))
      done
      if grep -q "Registered tunnel connection" "$LOG/tunnel.log" 2>/dev/null; then
        echo "$(date '+%F %T') つながりました（$((j*2))秒）" >> "$LOG/watch.log"
        return 0
      fi
      echo "$(date '+%F %T') 張れませんでした" >> "$LOG/watch.log"
      return 1
    fi
    sleep 2
    i=$((i+1))
  done
  echo "$(date '+%F %T') URLが出ませんでした" >> "$LOG/watch.log"
  return 1
}

# 張り直しの間隔をあける。
#
# **すぐ張り直してはいけない。** Quick Tunnel は作りすぎると
# 向こう側で断られ、張っても 000 のまま返ってくる。そこでまた
# 張り直すと、断られる → 張る → 断られる、の連鎖になる
# （実際そうなり、40秒待っても通らないトンネルを作り続けた）。
#
# 1回目は待たず、2回目以降は 2分・4分・8分…と最大30分まで下げる。
# 通ったら間隔は元に戻す。
BACKOFF=0
LAST_TRY=0

tunnel_retry() {
  now=$(date +%s)
  wait_for=$BACKOFF
  if [ $((now - LAST_TRY)) -lt "$wait_for" ]; then
    return 1                       # まだ待つ
  fi
  LAST_TRY=$now
  if start_tunnel; then
    BACKOFF=0
    return 0
  fi
  BACKOFF=$(( BACKOFF == 0 ? 120 : BACKOFF * 2 ))
  [ "$BACKOFF" -gt 1800 ] && BACKOFF=1800
  echo "$(date '+%F %T') つぎの張り直しまで ${BACKOFF}秒あけます" >> "$LOG/watch.log"
  return 1
}

watch_loop() {
  # 一度落ちてから直るまでを短くする。60秒ごとに見る。
  # 直したことは必ず watch.log に残す ―― 黙って直すと、
  # 「よく切れる」という事実そのものが見えなくなる。
  miss=0
  while :; do
    alive_server || start_server
    if alive_tunnel; then
      miss=0; BACKOFF=0
    else
      # 1回きりの取りこぼしでは張り直さない。2回続いたときだけ。
      miss=$((miss + 1))
      [ "$miss" -ge 2 ] && { tunnel_retry && miss=0; }
    fi
    sleep 60
  done
}

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "すでに動いています（PID $(cat "$PIDFILE")）"
  echo "いまのURL: $(cat "$URLFILE" 2>/dev/null || echo '不明')"
  exit 0
fi

alive_server || start_server
alive_tunnel || start_tunnel
watch_loop &
echo $! > "$PIDFILE"

echo "動かしはじめました。"
echo
if [ -n "${CF_NAME:-}" ]; then
  echo "  講師に配るURL   $(cat "$URLFILE" 2>/dev/null || echo "（$CF_NAME に割り当てたホスト名）")"
  echo "                  ★ これは変わりません。一度配れば配り直し不要です。"
else
  echo "  講師に配るURL   $(cat "$URLFILE" 2>/dev/null || echo '（取得中）')"
fi
if [ "${LAN:-0}" = "1" ]; then
  MYIP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
  [ -n "$MYIP" ] && echo "  同じWi-Fiから   http://$MYIP:$PORT/  （暗号化されません）"
fi
echo "  このMacから     http://127.0.0.1:$PORT/"
echo
echo "  いまのURL       cat deploy/URL.txt"
echo "  ようす          tail -f deploy/log/watch.log"
echo "  止める          sh deploy/run.sh stop"
echo
if [ -z "${CF_NAME:-}" ]; then
  echo "★ このURLは、トンネルが切れるたびに変わります。"
  echo "  変わったら講師全員に配り直しになります。"
  echo "  変わらないURLにする方法 → deploy/URLを固定する.md"
fi
if [ "${DEMO:-1}" = "1" ]; then
  echo
  echo "★ いまはデモの合言葉が画面に出ます（誰でも入れます）。"
  echo "  本番の名簿を入れたら DEMO=0 sh deploy/run.sh で動かしてください。"
fi
