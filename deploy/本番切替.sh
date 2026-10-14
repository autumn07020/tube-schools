#!/bin/sh
# 本番に切り替える ―― 試し運用のあいだの生徒（配った席・試しに登録された口座）を退避し、名簿を空にする。
#
#     sh deploy/本番切替.sh
#
# ------------------------------------------------------------------
# 何をして、何をしないか
# ------------------------------------------------------------------
# する   … サーバで go-live：生徒の口座と記録を、前の校舎ごと退避（消さない）／講師・管理者・クラス・コース・
#           授業計画・教材は残す／試し運用の印を外す（ふつうの入口の「ためしに見る」が消え、デモは /demo へ）／
#           **招待コードを作り直す** → デモ（架空の校舎）を作り直す → 外から確かめる
# しない … コードは送らない（コードは 更新.sh）。サーバは止めない。
#
# このあと、管理ページの「いまの様子」→「登録コード」の紙を刷って配る。保護者が、そこから自分で登録する。
# 1回だけのもの（切り替えずみの校舎では、何もせずに止まる）。
set -eu

HOST="${HOST:-18.130.10.188}"
SSHUSER="${SSHUSER:-ubuntu}"
KEY="${KEY:-$HOME/.ssh/lightsail.pem}"
CF_HOST="${CF_HOST:-tube-study.uk}"
SCHOOL="${SCHOOL:-waseaca-london}"
HERE=$(cd "$(dirname "$0")" && pwd)
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new $SSHUSER@$HOST"
RUN="sudo -u myacady env MYACADY_ROOT=/srv/myacady python3 /opt/myacady/server/tube_server.py"
say(){ printf "\n\033[1m%s\033[0m\n" "$*"; }

say "本番に切り替えます：$SCHOOL"
$SSH "$RUN go-live --school '$SCHOOL'" || { echo "  ⚠ 切り替えられません（上のメッセージを見てください。何も変わっていません）"; exit 1; }
echo
echo "  いまの生徒（試し運用の席・試しに登録された口座）と、その記録は退避されます（消えません）。"
echo "  講師・管理者・クラス・コース・授業計画・教材は残ります。出ていた宿題は消え、次の授業日にまた出ます。"
printf "  進めますか？ [y/N] "
read -r ANS
[ "$ANS" = "y" ] || { echo "やめました。"; exit 0; }

say "1/3  切り替えます（サーバは止めません）"
if $SSH "$RUN go-live --school '$SCHOOL' --yes"; then
  echo "  切り替えました"
else
  echo "  ⚠ 切り替えられませんでした（上のメッセージを見てください）"
  exit 1
fi

say "2/3  デモを作り直します（「ためしに入る」。サーバは止めません）"
sh "$HERE/デモを作り直す.sh" </dev/null || echo "  ⚠ デモを作り直せませんでした（上のメッセージを見てください。本番への切り替えは済んでいます）"

say "3/3  外から確かめます"
curl -s --max-time 15 "https://$CF_HOST/api/health"; echo
echo
echo "  次に："
echo "    ・管理ページ https://$CF_HOST/admin →「いまの様子」→「登録コード」→「配る紙を刷る」（新しいコードです）"
echo "    ・保護者が QR から登録する（お名前は集めません）"
echo "    ・これからの反映は TRIAL=0 を付けなくて大丈夫です（切り替えた校舎には、試し運用の印は付きません）"
