#!/bin/sh
# 毎日これ1つ。
#
#     sh deploy/毎日.sh
#
# 何度打っても壊れません。状態を見て、必要なことだけをします。
#   動いていなければ  → 起動する
#   動いていれば      → サーバだけ入れ替える（URLは変わらない）
#
# ------------------------------------------------------------------
# 覚えておくこと（これだけ）
# ------------------------------------------------------------------
# * **教材・名簿・宿題を足しただけなら、これを打つ必要はありません。**
#   app/content/ や画面のファイルは、開かれるたびに読み直されます。
#   ブラウザを再読み込みするだけで出ます。
#
# * server/*.py を直したときだけ、これを打ってください。
#
# * URLは変わりません。https://tube-study.uk のまま。
#
# ------------------------------------------------------------------
# 記録の置き場所について
# ------------------------------------------------------------------
# 記録は ~/myAcady にあります。**/tmp には置きません。**
# /tmp は Mac を再起動すると消えるためです（試用中はそこでした）。
#
# 初回だけ、/tmp にある試用のデータを ~/myAcady へ写します。
# **2回目以降は写しません。** 写すと、その日ぶんの生徒の記録が
# 古いもので上書きされてしまいます。ここは絶対に上書きしないこと。
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
DATA="$HOME/myAcady"
OLD=/tmp/myacady-migrate

CF_NAME=${CF_NAME:-tube}
CF_HOST=${CF_HOST:-tube-study.uk}
export CF_NAME CF_HOST
export MYACADY_ROOT="$DATA"

say(){ printf "\n\033[1m%s\033[0m\n" "$*"; }

# ---- 1. 置き場所を用意する（初回だけ写す） ----
#
# **「入れ物があるか」で判定してはいけない。**
# 前の実行で空の schools/ だけが作られていると、それを見て
# 「もう写してある」と判断し、写さないまま起動する。
# 実際そうなり、サーバは校舎0件で立ち上がっていた。
# 中に校舎が1つでもあるかどうかで判定する。
if [ -z "$(ls "$DATA/schools" 2>/dev/null)" ]; then
  mkdir -p "$DATA"
  if [ -d "$OLD/schools" ]; then
    say "初回です。試用のデータを $DATA へ写します"
    cp -R "$OLD"/. "$DATA"/
    echo "  写しました:"
    ls "$DATA" | sed 's/^/    /'
  else
    say "$DATA を作りました（中身は空）"
    echo "  名簿を入れるには:"
    echo "    python3 server/tube_server.py school-add london 'ロンドン校'"
  fi
else
  # **ここで cp をしてはいけない。** 毎日の実行で古いものが被さり、
  # その日の生徒の記録が消える。
  n=$(ls "$DATA/schools" 2>/dev/null | wc -l | tr -d ' ')
  # 変数のあとに日本語が続くときは必ず ${} で囲む。
  # `${n}）` と書くと、sh は全角の「）」まで変数名の一部として読み、
  # 「unbound variable」で止まる（実際そうなった）。
  say "記録は $DATA にあります（校舎 ${n}）"
fi

# ---- 2. 使い捨てトンネルが残っていたら、先に片づける ----
#
# 試用中は使い捨てトンネル（*.trycloudflare.com）で動かしていた。
# それが生きたまま名前付きに切り替えようとすると、見張りは
# 「トンネルは動いている」と判断して張り替えず、**ドメインに
# 何も繋がらない**。切り替えの初回だけ、まるごと止める。
if ! pgrep -f "cloudflared tunnel .*run .*$CF_NAME" >/dev/null 2>&1; then
  if pgrep -f "cloudflared tunnel" >/dev/null 2>&1; then
    say "使い捨てトンネルが動いています。名前付きに切り替えます"
    sh "$HERE/run.sh" stop
    sleep 2
  fi
fi

# ---- 3. 動いているか見て、起動か入れ替えか決める ----
if pgrep -f "cloudflared tunnel .*run .*$CF_NAME" >/dev/null 2>&1 &&
   curl -s -o /dev/null --max-time 5 "http://127.0.0.1:${PORT:-8765}/" 2>/dev/null; then
  say "動いています。サーバだけ入れ替えます（URLは変わりません）"
  sh "$HERE/run.sh" reload
else
  say "起動します"
  sh "$HERE/run.sh"
fi

# ---- 4. 外から通るか確かめる ----
say "外から確かめます"
i=0
while [ $i -lt 10 ]; do
  c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
      "https://$CF_HOST/api/health" 2>/dev/null)
  case "$c" in
    2*) echo "  OK  https://$CF_HOST/  （${c}）"; break ;;
  esac
  sleep 3
  i=$((i+1))
done
case "${c:-}" in
  2*) ;;
  *)
    echo "  ⚠ https://$CF_HOST/api/health が「${c:-応答なし}」を返しました"
    echo
    echo "  見るところ:"
    echo "    tail -20 deploy/log/tunnel.log     トンネルの様子"
    echo "    tail -20 deploy/log/server.log     サーバの様子"
    echo "    /Users/aki/bin/cloudflared tunnel list"
    echo
    echo "  DNSを割り当てていないときは、これを1度だけ:"
    echo "    /Users/aki/bin/cloudflared tunnel route dns $CF_NAME $CF_HOST"
    ;;
esac

say "まとめ"
echo "  講師に配るURL   https://$CF_HOST/     （ずっと同じ）"
echo "  記録の置き場所  $DATA"
echo "  次に直したら    sh deploy/毎日.sh"
echo
echo "  ★ いまはデモの合言葉が画面に出ます（URLを知れば誰でも入れます）。"
echo "    本番の名簿を入れたら:  DEMO=0 sh deploy/毎日.sh"
