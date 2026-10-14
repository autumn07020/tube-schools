#!/bin/sh
# 本物の校舎（waseaca-london）に、ためし用の生徒を作る。講師が自分の担当コースで「出す→見る→採点→返る」を試すため。
#
#     sh deploy/デモ生徒.sh            クラスごとに 2 人（席 91・92。ID は wd<クラス>91 / wd<クラス>92）
#     sh deploy/デモ生徒.sh e4a j3r    そのクラスだけ
#
# 合言葉はこの Mac で作って、この画面に 1 回だけ出す（サーバには確かめる値だけが残る）。控えは本人が取る。
# 本物の生徒（s-xxx）とは ID の形が違うので見分けがつく。席の番号 91・92 は本物では使わない。
# 消すときは、管理ページの「生徒」でその ID を在籍終了にするか、サーバで `tube_server.py rm <id>`。
set -eu
HOST="${HOST:-18.130.10.188}"
SSHUSER="${SSHUSER:-ubuntu}"
KEY="${KEY:-$HOME/.ssh/lightsail.pem}"
SCHOOL="${SCHOOL:-waseaca-london}"
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new $SSHUSER@$HOST"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# 1. クラスの一覧（時間割にあるクラス）→ 作る生徒の表（id,seat,class,level,password）
python3 - "$ROOT" "$TMP/list.csv" "$@" <<'PY'
import csv, io, json, secrets, sys
root, out = sys.argv[1], sys.argv[2]; only = set(sys.argv[3:])
rows = list(csv.reader(io.open(root + "/カリキュラム/コマ.csv", encoding="utf-8-sig")))
cls = sorted({c for r in rows[1:] for c in (r[5] or "").split()})
if only:
    bad = [c for c in only if c not in cls]
    if bad: sys.exit("× 時間割に無いクラス: " + " ".join(bad))
    cls = [c for c in cls if c in only]
words = json.load(io.open(root + "/app/words.json", encoding="utf-8"))
words = words if isinstance(words, list) else (words.get("words") or [])
def pw():
    return "-".join(secrets.choice(words) for _ in range(3)) + "-" + "%04d" % secrets.randbelow(10000)
with io.open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    for c in cls:
        for seat in ("91", "92"):
            w.writerow(["wd%s%s" % (c, seat), seat, c, c[:2], pw()])
print("作る生徒 %d 人（クラス %d）" % (len(cls) * 2, len(cls)))
PY

# 2. サーバで流す台本（add を並べる。席がふさがっていれば add が断る）
{
  echo 'set -u'
  echo 'cd /opt/myacady'
  while IFS=, read -r id seat cls level pw; do
    printf 'sudo -u myacady env MYACADY_ROOT=/srv/myacady python3 server/tube_server.py add %s %s --class %s --level %s --password %s --school %s >/dev/null 2>&1 && echo "  作った %s（%s-%s）" || echo "  × %s は作れませんでした（もうある・席がふさがっている など）"\n' "$id" "$seat" "$cls" "$level" "$pw" "$SCHOOL" "$id" "$cls" "$seat" "$id"
  done < "$TMP/list.csv"
} > "$TMP/run.sh"

echo "本番（${SCHOOL}）に、ためし用の生徒を作ります。"
printf "よろしいですか？ [y/N] "
read ans
case "$ans" in y|Y|yes) ;; *) echo "作りませんでした。"; exit 0 ;; esac

scp -q -i "$KEY" "$TMP/run.sh" "$SSHUSER@$HOST:/tmp/tube-demo-students.sh"
$SSH 'sh /tmp/tube-demo-students.sh; rm -f /tmp/tube-demo-students.sh'

# 3. 合言葉はここに 1 回だけ出す
echo
echo "ID と合言葉（この画面にだけ出ます。控えを取ってください）"
echo "----------------------------------------------"
while IFS=, read -r id seat cls level pw; do
  printf "  %-12s %s-%s   %s\n" "$id" "$cls" "$seat" "$pw"
done < "$TMP/list.csv"
echo "----------------------------------------------"
echo "生徒の入口 https://tube-study.uk/ に ID と合言葉で入れます。講師は自分の担当コースの時間割から提出箱を出して試せます。"
