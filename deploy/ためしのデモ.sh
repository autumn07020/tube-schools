#!/bin/sh
# 本番の本物の校舎（waseaca-london）に、ためし運用のデモを作る（server/demo_trial.py）。
#
#     sh deploy/ためしのデモ.sh              作る（前のためしのデータは先に消してから。何度流しても同じ。数分かかる）
#     sh deploy/ためしのデモ.sh clean        ためしのデータを消す（席だった口座は席に戻る。前の形の wd… は口座ごと消える）
#
# 作るもの（10-12）：今ある口座（席を先に）から**クラスごとに 5〜15 人**を無作為に選んで在籍の生徒にし、**全講師の全コース**に
# 授業計画・学期のはじめからの宿題・写真と評価・毎日テストの記録。講師ごとに 1 つ、きのう期限の提出箱に未評価の写真。
# 本人（ME=wt01）の算数・国語には返した添削・保護者のメッセージ・漢字テスト・作文、中3R 数学・小6K 算数には過去問。
# 入口の「ためしに見る」の生徒は、学年ごとに 2 人（サーバがそのまま出す。deploy/ためしに見る.json は講師だけ）。
# 作った宿題・計画・口座には demo の印が付き、clean で全部戻る。本番に切り替えるとき（本番切替.sh）は生徒ごと退避される。
#
# 先に `sh deploy/更新.sh`（コード）と `sh deploy/担当.sh`（担当）・`sh deploy/時間割.sh`（時間）を流しておくこと。
# サーバは止めない（作っている数分、ほかの書き込みは待つ）。
set -eu
HOST="${HOST:-18.130.10.188}"
SSHUSER="${SSHUSER:-ubuntu}"
KEY="${KEY:-$HOME/.ssh/lightsail.pem}"
SCHOOL="${SCHOOL:-waseaca-london}"
ME="${ME:-wt01}"
CF_HOST="${CF_HOST:-tube-study.uk}"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new $SSHUSER@$HOST"
RUN="sudo -u myacady env MYACADY_ROOT=/srv/myacady python3 /opt/myacady/server/demo_trial.py --school ${SCHOOL}"

MODE="${1:-build}"
if [ "$MODE" = "clean" ]; then
  shift
  echo "本番（${SCHOOL}）の、ためしのデータを消します（席だった口座は席に戻ります）。"
  printf "よろしいですか？ [y/N] "
  read ans
  case "$ans" in y|Y|yes) ;; *) echo "消しませんでした。"; exit 0 ;; esac
  $SSH "$RUN --clean ${1:-}"
  exit $?
fi

echo "本番（${SCHOOL}）に、ためし運用のデモを作ります（全講師の全コース。クラスごとに 5〜15 人を今ある口座から無作為に）。"
echo "前のためしのデータは先に消えます。選ばれた席は在籍の生徒になります（clean で席に戻ります）。数分かかります。"
printf "よろしいですか？ [y/N] "
read ans
case "$ans" in y|Y|yes) ;; *) echo "作りませんでした。"; exit 0 ;; esac
$SSH "$RUN --me ${ME}"

echo
echo "  https://${CF_HOST}/ の「ためしに見る」から、講師 wt01〜wt06 と、学年ごとに選ばれた生徒で入って確かめてください。"
echo "  戻すときは  sh deploy/ためしのデモ.sh clean"
