#!/bin/sh
# 時間割（カリキュラム/コマ.csv）の「時間」だけを、本番のコース表に入れる。
#
#     sh deploy/時間割.sh
#
# 講師・受ける生徒・授業計画・使う印には触らない（server/courses.py の set_slots）。
# まだ無いコースは、講師なし・紙のままで作る（講師は管理ページの「講師と担当」で）。
# 入れる前に、時間が変わるコースと新しく作るコースを出して、入れてよいか聞く。
#
# 直すとき：カリキュラム/時間割.csv を直す（表計算で開ける）→ これを流す（元の CSV から作り直してから送る）。
# 先に一度 `sh deploy/更新.sh` でサーバのコードを新しくしておくこと（courses-slots が無いと止まる）。
set -eu
HOST="${HOST:-18.130.10.188}"
SSHUSER="${SSHUSER:-ubuntu}"
KEY="${KEY:-$HOME/.ssh/lightsail.pem}"
SCHOOL="${SCHOOL:-waseaca-london}"
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
F="$ROOT/カリキュラム/コマ.csv"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new $SSHUSER@$HOST"

python3 "$ROOT/scripts/curriculum/時間割/build.py" | head -1     # 元の CSV（時間割.csv）から作り直す
[ -f "$F" ] || { echo "× $F がありません"; exit 1; }
# 念のため、講師名が混じっていないことを確かめる（コマ.csv は id・教科・名前・学年・時間・クラスだけ）
head -1 "$F" | grep -q "講師" && { echo "× コマ.csv に講師の列があります。送りません。"; exit 1; }

scp -q -i "$KEY" "$F" "$SSHUSER@$HOST:/tmp/tube-koma.csv"
$SSH 'sudo chown myacady:myacady /tmp/tube-koma.csv'
RUN="sudo -u myacady env MYACADY_ROOT=/srv/myacady python3 /opt/myacady/server/tube_server.py courses-slots /tmp/tube-koma.csv --school $SCHOOL"
if ! $SSH "$RUN"; then
  $SSH 'sudo rm -f /tmp/tube-koma.csv'
  echo "× 入れられません（上のメッセージ）。courses-slots が無いと言われたら、先に sh deploy/更新.sh を流してください。"
  exit 1
fi
printf "\nこのとおり入れますか？ [y/N] "
read ans
rc=0
case "$ans" in
  y|Y|yes) $SSH "$RUN --yes" || rc=$? ;;
  *) echo "入れませんでした（何も変えていません）。" ;;
esac
$SSH 'sudo rm -f /tmp/tube-koma.csv'
exit $rc
