#!/bin/sh
# 直したものをサーバへ反映する。毎日これ1つ。
#
#     sh deploy/更新.sh
#
# ------------------------------------------------------------------
# 何をして、何をしないか
# ------------------------------------------------------------------
# する   … app/ と server/ と カリキュラム/（JSON と文書だけ。PDF と時間割（講師の名字が入る）は送らない）をサーバへ送り、サービスを入れ替える
# しない … **生徒の記録には一切触らない**
#
# 記録はサーバの /srv/myacady/ にあり、この作業では読みも書きもしない。
# 更新のたびにデータを送る作りにすると、いつか手元の古いもので
# その日の記録を上書きする。送るのはコードだけにする。
#
# ------------------------------------------------------------------
# 「ためしに見る」について
# ------------------------------------------------------------------
# DEMO=1（既定）… 入口の「ためしに見る」を開ける。並ぶ口座は deploy/ためしに見る.json（ID だけ。
#                 本物の講師 wt01〜wt06 と、ためし用の生徒 4人）。ボタンは ID だけで入る（合言葉は要らない）。
#                 **誰でもその講師として入れる**ので、試し運用（TRIAL=1、〜10/15）のあいだだけ。
#                 本物の校舎が試し運用でなくなると、ふつうの入口には出ない（デモの入口 /demo には出る）。
# DEMO=0        … 止める（/demo も閉じる）。
#
#     DEMO=0 sh deploy/更新.sh
set -eu

HOST="${HOST:-18.130.10.188}"
SSHUSER="${SSHUSER:-ubuntu}"
KEY="${KEY:-$HOME/.ssh/lightsail.pem}"
CF_HOST="${CF_HOST:-tube-study.uk}"
DEMO="${DEMO:-1}"
# TRIAL … 試し運用の印（本番に切り替える 10/15 までは 1）。付いているあいだ、その校舎は「まだ本物でない」と数え、
#          ふつうの入口にも「ためしに見る」を出す。本番に切り替えた校舎には、もう付かない（サーバが断る）。
TRIAL="${TRIAL:-1}"
TRIAL_SCHOOL="${TRIAL_SCHOOL:-waseaca-london}"
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
cd "$ROOT"     # どこから流しても同じ（手元の検査は置き場を基準に探す）

SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new $SSHUSER@$HOST"
say(){ printf "\n\033[1m%s\033[0m\n" "$*"; }

# ---- 1. 送る前に、手元で壊れていないか見る ----
say "1/4  手元を検査します"
python3 "$ROOT/app/tools/check-source.py" >/dev/null 2>&1 \
  && echo "  ソース  問題なし" || { echo "  ⚠ ソースに指摘があります。中止します"; \
     python3 "$ROOT/app/tools/check-source.py" | tail -20; exit 1; }
python3 -c "
import ast, io, sys, glob
for f in glob.glob('$ROOT/server/*.py'):
    try: ast.parse(io.open(f, encoding='utf-8').read())
    except SyntaxError as e: print('  ⚠ %s: %s' % (f.split('/')[-1], e)); sys.exit(1)
print('  Python  構文OK')
" || exit 1

# ---- 2. アプリを送る ----
say "2/4  送ります"
# --delay-updates … 送り終えてから、まとめて置き換える。送っている数秒のあいだに開いた人が、
# 新しい js と古い js の混ざった画面を受け取らないようにする。
rsync -az --delete --delay-updates -e "ssh -i $KEY" \
  --exclude '__pycache__' --exclude '*.pyc' \
  --exclude '/server/data' --exclude '/server/data.bak*' \
  --exclude '/カリキュラム/*.pdf' --exclude '/カリキュラム/*.nosync' --exclude '/カリキュラム/時間割*' --exclude '/カリキュラム/*講師*' \
  --rsync-path='sudo rsync' \
  "$ROOT/app" "$ROOT/server" "$ROOT/カリキュラム" "$SSHUSER@$HOST:/opt/myacady/"
$SSH 'sudo chown -R root:root /opt/myacady'
echo "  送りました"

# 「ためしに見る」に並ぶ口座の一覧（ID だけ。合言葉は入っていない）。
# deploy/ためしに見る.json があればそれ。無ければ、前からの ~/myAcady/demo-accounts.json（架空のデモ校の一覧）。
DEMO_LIST="${ROOT}/deploy/ためしに見る.json"
[ -f "${DEMO_LIST}" ] || DEMO_LIST="${HOME}/myAcady/demo-accounts.json"
if [ "$DEMO" = "1" ] && [ -f "${DEMO_LIST}" ]; then
  if grep -q '"password"' "${DEMO_LIST}" && [ "${DEMO_LIST}" = "${ROOT}/deploy/ためしに見る.json" ]; then
    echo "  ⚠ deploy/ためしに見る.json に password の欄があります。置きません（ID だけにしてください）。"
  else
    scp -q -i "$KEY" "${DEMO_LIST}" "$SSHUSER@$HOST:/tmp/demo.json"
    $SSH 'sudo mv /tmp/demo.json /srv/myacady/demo-accounts.json && \
          sudo chown myacady:myacady /srv/myacady/demo-accounts.json'
    echo "  「ためしに見る」の一覧も置きました（$(basename "${DEMO_LIST}")）"
  fi
fi

# ---- 3. 入れ替える ----
say "3/4  入れ替えます"
$SSH "sudo bash -s -- '$DEMO'" <<'REMOTE'
set -eu
DEMO="$1"
if [ "$DEMO" = "1" ]; then
  FLAG=" --demo"
else
  FLAG=""
  rm -f /srv/myacady/demo-accounts.json
fi
sed -i "s|^ExecStart=.*|ExecStart=/usr/bin/python3 /opt/myacady/server/tube_server.py serve --host 127.0.0.1 --port 8765${FLAG}|" \
  /etc/systemd/system/myacady.service
systemctl daemon-reload
systemctl restart myacady
sleep 3
systemctl is-active --quiet myacady || { journalctl -u myacady -n 20 --no-pager; exit 1; }
echo "  myacady 稼働中（デモ: ${DEMO}）"
REMOTE

# ---- 3.5 席・講師・管理者の束（あれば入れる。入っているのは ID と、合言葉のハッシュだけ） ----
#
# 束は手元で作る（python3 scripts/accounts/make.py）。合言葉そのものは束に入っていない。
# 何度流しても同じ結果になる ―― すでにある口座・コースには触らない。
BUNDLE_NG=""
for B in "$ROOT"/deploy/accounts/*.bundle.json; do
  [ -f "$B" ] || continue
  N=$(basename "$B")
  # 念のため、送る前に「合言葉らしきものが入っていない」ことを確かめる。
  if grep -q '"password"' "$B"; then echo "  ⚠ $N に password の欄があります。送りません。"; BUNDLE_NG="$BUNDLE_NG $N"; continue; fi
  say "束を入れます: $N"
  scp -q -i "$KEY" "$B" "$SSHUSER@$HOST:/tmp/tube-bundle.json"
  # 入れられなかったら、黙って先へ進まない（前は、あと片づけの rm の成否しか見ていなかった）。
  if $SSH 'sudo chown myacady:myacady /tmp/tube-bundle.json && \
        sudo -u myacady env MYACADY_ROOT=/srv/myacady python3 /opt/myacady/server/tube_server.py bundle-import /tmp/tube-bundle.json --yes; \
        rc=$?; sudo rm -f /tmp/tube-bundle.json; exit $rc'; then
    :
  else
    echo "  ⚠ 束を入れられませんでした: ${N}（上のメッセージを見てください）"
    BUNDLE_NG="$BUNDLE_NG $N"
  fi
done
if [ "$TRIAL" = "1" ]; then
  $SSH "sudo -u myacady env MYACADY_ROOT=/srv/myacady python3 /opt/myacady/server/tube_server.py school-trial --school '$TRIAL_SCHOOL' --on" 2>/dev/null | sed 's/^/  /' || true
elif [ "$TRIAL" = "0" ]; then
  $SSH "sudo -u myacady env MYACADY_ROOT=/srv/myacady python3 /opt/myacady/server/tube_server.py school-trial --school '$TRIAL_SCHOOL' --off" 2>/dev/null | sed 's/^/  /' || true
fi
REAL=$($SSH 'sudo -u myacady env MYACADY_ROOT=/srv/myacady python3 /opt/myacady/server/tube_server.py schools --real-count' 2>/dev/null | tail -1 || echo 0)
case "$REAL" in ''|*[!0-9]*) REAL=0 ;; esac

# ---- 4. 外から確かめる ----
say "4/4  外から確かめます"
i=0
while [ $i -lt 12 ]; do
  c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
      "https://$CF_HOST/api/health" 2>/dev/null || true)
  case "$c" in 2*) break ;; esac
  printf "  待っています… %s\n" "${c:-応答なし}"
  sleep 4
  i=$((i+1))
done
curl -s --max-time 15 "https://$CF_HOST/api/health"; echo

# ---- 5. デモのデータが、いまのコードより古くないか ----
#
# コードだけ送っても、架空データは古い作り方のまま残る。
# 「直したはずなのに画面が変わらない」のはたいていこれ。
# **デモは反映のたびに、保存時の状態に戻す**（担当講師の決定, 2026-09-11）。
# 触ってみた印やメモが残ったままだと、次に見た人には何が起きたのか分からず、
# 不具合も再現できない。作り方は決まっている（生徒の ID はログインIDから、
# 宿題の ID は中身から決まる）ので、戻すと毎回同じデータが「今週」に合わせてできる。
# 戻したくないときだけ RESET=0 で流す。本物の校舎は、目印が無いので戻さない。
#
# 戻すあいだもサーバは止めない（別の置き場で作ってから入れ替える。デモを作り直す.sh）。
# 本物の校舎を使っていても、生徒と講師は入れたまま。作っている数分、少し重くなる。
if [ "$DEMO" = "1" ] && [ "${RESET:-1}" = "1" ]; then
  say "デモを保存時の状態に戻します（数分かかります。サーバは止めません）"
  sh "$HERE/デモを作り直す.sh" </dev/null || echo "  ⚠ 戻せませんでした（上のメッセージを見てください）"
fi

echo
echo "  https://$CF_HOST/"
FRONT=$(curl -s --max-time 15 "https://$CF_HOST/api/health" 2>/dev/null | grep -c '"demo": true' || true)
[ "$REAL" -gt 0 ] && echo "  管理ページ  https://$CF_HOST/admin"
if [ "$DEMO" = "1" ]; then
  if [ "${FRONT:-0}" -gt 0 ]; then
    echo "  ★ ふつうの入口に「ためしに見る」が出ています（試し運用中）。デモの入口 https://$CF_HOST/demo からも入れます。"
  else
    echo "  デモの入口  https://$CF_HOST/demo   （ふつうの入口には「ためしに見る」を出していません。デモごと止めるなら DEMO=0）"
  fi
fi
if [ -n "$BUNDLE_NG" ]; then
  echo
  echo "  ⚠ 席の束が入っていません:$BUNDLE_NG"
  echo "    コードは反映ずみです。カードの ID では、まだ入れません。上の × を直してから、もう一度流してください。"
  exit 1
fi
true
