#!/bin/sh
# サーバのデモ用データを、いまのコードで作り直す。
#
#     sh deploy/デモを作り直す.sh
#
# ------------------------------------------------------------------
# いつ流すか
# ------------------------------------------------------------------
# 更新.sh が反映のたびに流す（デモを保存時の状態に戻す）。手で流すのは、
# コードを送らずにデモだけを戻したいとき。作り方は決まっているので、
# 何度流しても同じデータが「今週」に合わせてできる（ID も同じ）。
#
# ------------------------------------------------------------------
# ★ 消えるもの
# ------------------------------------------------------------------
# london 校舎（架空のデモ）の **記録は全部作り直し**になる。
# 本物の校舎（waseaca-london など。school.json に "demo" の目印が無い）には触らない。
# サーバは止めない（別の置き場で作ってから入れ替える）。作っている数分、サーバは少し重くなる。
#
# ------------------------------------------------------------------
# 合言葉について
# ------------------------------------------------------------------
# 作り直すと、london の全員の合言葉が新しくなる（demo_running.py が決まった値に戻す。
# 手元の検査 expect.py --accounts deploy/demo-accounts.json がその合言葉で入る）。
# 入口の「ためしに見る」は合言葉を使わない（ID だけで入る。一覧は deploy/ためしに見る.json）ので、
# 作り直しても入れなくなることはない。demo-swap は、その一覧を london の口座で上書きしない。
set -eu

HOST="${HOST:-18.130.10.188}"
SSHUSER="${SSHUSER:-ubuntu}"
KEY="${KEY:-$HOME/.ssh/lightsail.pem}"
SCHOOL="${SCHOOL:-london}"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new $SSHUSER@$HOST"

printf "\n\033[1m%s の架空データを作り直します\033[0m\n" "$SCHOOL"
printf "本番の名簿が入っているなら、いま Ctrl-C で止めてください。\n\n"

$SSH "sudo bash -s -- '$SCHOOL'" <<'REMOTE'
set -eu
S="$1"
R=/srv/myacady
B="$R/.demo-build"
RUN="sudo -u myacady env MYACADY_ROOT=$R python3"
RUN_B="sudo -u myacady env MYACADY_ROOT=$B python3"
# **架空のデモの校舎だけを戻す。** 本物の名簿が入った校舎を消さないように、
# 目印（school.json の "demo": true か、入口の架空アカウント lteacher1）を確かめる。
# （入れ替えの命令 demo-swap も、同じことをもう一度確かめる。）
J="$R/schools/$S/school.json"; A="$R/schools/$S/accounts.json"
if [ -f "$J" ] && ! grep -q '"demo": *true' "$J" && ! grep -q '"lteacher1"' "$A" 2>/dev/null; then
  echo "  ⚠ $S は架空のデモの校舎ではありません。戻しません。"
  exit 1
fi

# **サーバは止めない。** 別の置き場（${B}）で作り終えてから、校舎のフォルダを入れ替える。
# 前は、動いている置き場の中で消して作り直していたので、そのあいだ（数分）サーバを止めていた。
# 本物の校舎を使い始めると、その数分は生徒と講師が入れない時間になる。
rm -rf "$B"
sudo -u myacady mkdir -p "$B"
trap 'rm -rf "$B"' EXIT

echo "1/3  別の置き場で、アカウントとクラスを作ります"
$RUN_B /opt/myacady/server/tube_server.py seed --reset --empty --school "$S" --name ロンドン校 | tail -2

echo "2/3  授業・宿題・生徒の記録を作ります"
$RUN_B /opt/myacady/server/demo_running.py --school "$S" | tail -8

echo "3/3  入れ替えます（サーバは動いたまま）"
$RUN /opt/myacady/server/tube_server.py demo-swap --from "$B" --school "$S" --yes
systemctl is-active --quiet myacady && echo "  myacady 稼働中"
REMOTE

# ---- 4/4 意味の検査（手元から本番へ。読むだけ。scripts/check/expect.py） ----
# 作り直すたびに、画面の目的から決めた不変条件と「前回との差」を確かめる。
# 通らなければ ×。数が減っていたら、理由を言えるまで次に進まない（CLAUDE.md「検査」）。
echo
echo "4/4  意味の検査（scripts/check/expect.py → 本番。読むだけ）"
ROOT=$(cd "$(dirname "$0")/.." && pwd)
if command -v python3 >/dev/null 2>&1; then
  OUT=$(mktemp)
  if python3 "$ROOT/scripts/check/expect.py" --base "https://${CF_HOST:-tube-study.uk}" \
       --accounts "$ROOT/deploy/demo-accounts.json" \
       --ledger "$ROOT/scripts/check/ledger-production.json" >"$OUT" 2>&1; then
    grep -v "^  OK" "$OUT" | grep -v "^$" | tail -4
  else
    grep -v "^  OK" "$OUT" | grep -v "^$" | tail -30
    echo "  ⚠ 意味の検査に通っていません。上の × を見てください（デモは作り直してあります）"
    rm -f "$OUT"; exit 1
  fi
  rm -f "$OUT"
else
  echo "  python3 が無いので飛ばしました"
fi

echo
echo "  https://tube-study.uk/demo"
echo "  ★ 「ためしに見る」で、そのまま入れます。"
echo "    （本物の校舎が無いあいだは、ふつうの入口 https://tube-study.uk/ にも出ます）"
