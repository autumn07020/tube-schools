#!/bin/sh
# 担当（カリキュラム/担当.csv）の「講師」だけを、本番のコース表に入れる。
#
#     sh deploy/担当.sh
#
# 時間・受ける生徒・授業計画・使う印には触らない（server/courses.py の set_teachers）。
# 無いコースは作らない（先に sh deploy/時間割.sh）。
# 担当.csv は build.py が、時間割.csv（講師の名字入り）と 時間割の講師.csv（名字→ログインID）から作る。
# 本番へ送るのはログインIDだけ。講師の列に ID 以外の文字（名字など）があれば送らない。
# 入れる前に、担当が変わるコースを出して、入れてよいか聞く。何度流しても同じ。
#
# 直すとき：カリキュラム/時間割.csv の講師の欄か、時間割の講師.csv の名字→ID を直す → これを流す。
# 先に一度 `sh deploy/更新.sh` でサーバのコードを新しくしておくこと（courses-teachers が無いと止まる）。
set -eu
HOST="${HOST:-18.130.10.188}"
SSHUSER="${SSHUSER:-ubuntu}"
KEY="${KEY:-$HOME/.ssh/lightsail.pem}"
SCHOOL="${SCHOOL:-waseaca-london}"
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
F="$ROOT/カリキュラム/担当.csv"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new $SSHUSER@$HOST"

python3 "$ROOT/scripts/curriculum/時間割/build.py" | head -2     # 元の CSV から作り直す
[ -f "$F" ] || { echo "× $F がありません"; exit 1; }
# 見出しは id,教科,講師（先頭の BOM と改行は除いて比べる。sh の tr は 8進の多バイトを落とせなかった。10-10）
python3 -c 'import io,sys; h=io.open(sys.argv[1],encoding="utf-8-sig").readline().strip(); sys.exit(0 if h=="id,教科,講師" else 1)' "$F" || { echo "× 担当.csv の見出しが違います（id,教科,講師）。送りません。"; exit 1; }
# 講師の列はログインIDだけ（名字が混じっていないことを確かめる）
if tail -n +2 "$F" | cut -d, -f3 | tr -d '\r' | grep -q '[^a-zA-Z0-9_ -]'; then
  echo "× 担当.csv の講師の列に ID 以外の文字があります。送りません。"; exit 1
fi

scp -q -i "$KEY" "$F" "$SSHUSER@$HOST:/tmp/tube-tantou.csv"
$SSH 'sudo chown myacady:myacady /tmp/tube-tantou.csv'
RUN="sudo -u myacady env MYACADY_ROOT=/srv/myacady python3 /opt/myacady/server/tube_server.py courses-teachers /tmp/tube-tantou.csv --school $SCHOOL"
if ! $SSH "$RUN"; then
  $SSH 'sudo rm -f /tmp/tube-tantou.csv'
  echo "× 入れられません（上のメッセージ）。courses-teachers が無いと言われたら、先に sh deploy/更新.sh を流してください。"
  exit 1
fi
printf "\nこのとおり入れますか？ [y/N] "
read ans
rc=0
case "$ans" in
  y|Y|yes) $SSH "$RUN --yes" || rc=$? ;;
  *) echo "入れませんでした（何も変えていません）。" ;;
esac
$SSH 'sudo rm -f /tmp/tube-tantou.csv'
exit $rc
