#!/bin/sh
# Tube for Schools を Lightsail へ移す。
#
#     sh deploy/aws.sh 静的IP
#
# ------------------------------------------------------------------
# なぜ Caddy を使わないのか
# ------------------------------------------------------------------
# deploy/deploy.sh は Caddy を入れて 80/443 を開ける作りだった。
# しかし、いまは Cloudflare のトンネルがもう動いている。
# **そのトンネルをこのサーバへ移すだけでよい。**
#
#   * DNSを触らない（tube-study.uk はすでにトンネルを指している）
#   * 証明書を扱わない（Cloudflare 側で自動、更新も自動）
#   * 外向きのポートを1つも開けない（SSH以外は閉じたまま）
#
# 開けた口は、いつか誰かに叩かれる。開けずに済むなら開けない。
#
# ------------------------------------------------------------------
# 切り替えの順番
# ------------------------------------------------------------------
# 同じトンネルをMacとサーバの両方から動かすと、Cloudflare は
# 両方に振り分ける。**記録が2か所に分かれる**ので、必ず
#   1. Macを止める → 2. 最後のデータを送る → 3. サーバで起こす
# の順にする。夜なら数分の停止で済む。
set -eu

HOST="${1:?使い方: sh deploy/aws.sh 静的IP}"
SSHUSER="${SSHUSER:-ubuntu}"
KEY="${KEY:-$HOME/.ssh/lightsail.pem}"
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
DATA="$HOME/myAcady"
CFDIR="$HOME/.cloudflared"
CF_HOST="${CF_HOST:-tube-study.uk}"

SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new $SSHUSER@$HOST"
say(){ printf "\n\033[1m%s\033[0m\n" "$*"; }

# ---- 0. 手元の確認 ----
say "0/8  手元を確かめます"
[ -f "$KEY" ] || { echo "  鍵がありません: $KEY"; echo "  Lightsail からダウンロードして chmod 400 してください"; exit 1; }
[ -d "$DATA/schools" ] || { echo "  記録がありません: $DATA/schools"; exit 1; }
TUNID=$(ls "$CFDIR" 2>/dev/null | grep '\.json$' | head -1 | sed 's/\.json$//')
[ -n "$TUNID" ] || { echo "  トンネルの資格ファイルがありません: $CFDIR"; exit 1; }
echo "  鍵        $KEY"
echo "  記録      ${DATA}（校舎 $(ls "$DATA/schools" | tr '\n' ' ')）"
echo "  トンネル  $TUNID"

$SSH 'echo "  つながりました: $(hostname) / $(lsb_release -ds 2>/dev/null || echo Linux)"'

# ---- 1. サーバの下ごしらえ ----
say "1/8  必要なものを入れます"
$SSH 'sudo bash -s' <<'REMOTE'
set -eu
export DEBIAN_FRONTEND=noninteractive

# スワップを1GB。
#
# アプリ自体は28MBしか使わないので 512MB の機械で足りる。
# ただし **apt が一時的に大きく膨らむ**。スワップの無い512MBだと、
# インストールの途中で OOM に殺されることがある。
# 保険として置いておく。速度のためではない。
if [ ! -f /swapfile ]; then
  fallocate -l 1G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=1024 status=none
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "  スワップ 1GB を用意しました"
fi

apt-get update -qq
apt-get install -y -qq python3 rsync curl ca-certificates >/dev/null

# cloudflared（Cloudflare の公式パッケージ）
if ! command -v cloudflared >/dev/null; then
  mkdir -p --mode=0755 /usr/share/keyrings
  curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
    | tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
  echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" \
    > /etc/apt/sources.list.d/cloudflared.list
  apt-get update -qq && apt-get install -y -qq cloudflared >/dev/null
fi

# アプリ専用の利用者。root では動かさない。
id -u myacady >/dev/null 2>&1 || \
  useradd --system --home /srv/myacady --shell /usr/sbin/nologin myacady
mkdir -p /opt/myacady /srv/myacady /etc/cloudflared
chown -R myacady:myacady /srv/myacady
chmod 750 /srv/myacady
echo "  python3 $(python3 -V 2>&1 | cut -d' ' -f2) / cloudflared $(cloudflared -v 2>&1 | head -1 | awk '{print $3}')"
REMOTE

# ---- 2. アプリを送る ----
say "2/8  アプリを送ります"
rsync -az --delete -e "ssh -i $KEY" \
  --exclude '__pycache__' --exclude '*.pyc' \
  --rsync-path='sudo rsync' \
  "$ROOT/app" "$ROOT/server" "$SSHUSER@$HOST:/opt/myacady/"
$SSH 'sudo chown -R root:root /opt/myacady && echo "  送りました"'

# ---- 3. Mac側を止める（記録が2か所に分かれないように） ----
say "3/8  Mac側を止めます（ここから数分だけ止まります）"
sh "$HERE/run.sh" stop >/dev/null 2>&1 || true
sleep 2
echo "  止めました"

# ---- 4. 記録を送る ----
say "4/8  記録を送ります"
rsync -az -e "ssh -i $KEY" --rsync-path='sudo rsync' \
  "$DATA"/ "$SSHUSER@$HOST:/srv/myacady/"
$SSH 'sudo chown -R myacady:myacady /srv/myacady && \
      echo "  校舎: $(ls /srv/myacady/schools | tr "\n" " ")" && \
      echo "  記録: $(ls /srv/myacady/schools/*/progress/*.json 2>/dev/null | wc -l) 件"'

# ---- 5. トンネルの資格を送る ----
say "5/8  トンネルの資格を送ります"
scp -q -i "$KEY" "$CFDIR/$TUNID.json" "$SSHUSER@$HOST:/tmp/tun.json"
$SSH "sudo bash -s -- '$TUNID' '$CF_HOST'" <<'REMOTE'
set -eu
TUNID="$1"; CF_HOST="$2"
mv /tmp/tun.json "/etc/cloudflared/$TUNID.json"
chmod 600 "/etc/cloudflared/$TUNID.json"
cat > /etc/cloudflared/config.yml <<CFG
tunnel: $TUNID
credentials-file: /etc/cloudflared/$TUNID.json
# 受けた通信は、この機械の中のサーバへ渡すだけ。
# 外向きのポートは1つも開けない。
ingress:
  - hostname: $CF_HOST
    service: http://127.0.0.1:8765
  - service: http_status:404
CFG
chmod 600 /etc/cloudflared/config.yml
echo "  置きました"
REMOTE

# ---- 6. サービスとして登録する ----
say "6/8  サービスにします（再起動しても勝手に立ち上がります）"
$SSH 'sudo bash -s' <<'REMOTE'
set -eu
cat > /etc/systemd/system/myacady.service <<'UNIT'
[Unit]
Description=Tube for Schools
After=network.target

[Service]
Type=simple
User=myacady
Group=myacady
WorkingDirectory=/opt/myacady
Environment=MYACADY_ROOT=/srv/myacady
# 127.0.0.1 にしか口を開けない。外からはトンネル経由でしか届かない。
# --demo は付けない。付けると合言葉が画面に出る。
ExecStart=/usr/bin/python3 /opt/myacady/server/tube_server.py serve --host 127.0.0.1 --port 8765
Restart=always
RestartSec=3

# 権限を絞る。破られたときに動ける範囲を小さくしておく。
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/myacady
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6
MemoryMax=384M

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/cloudflared.service <<'UNIT'
[Unit]
Description=Cloudflare Tunnel
After=network.target myacady.service
Wants=myacady.service

[Service]
Type=notify
ExecStart=/usr/bin/cloudflared --no-autoupdate --config /etc/cloudflared/config.yml tunnel run
Restart=always
RestartSec=5
User=root
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now myacady   >/dev/null
systemctl restart myacady
systemctl enable --now cloudflared >/dev/null
systemctl restart cloudflared
sleep 4
systemctl is-active --quiet myacady    && echo "  myacady    稼働中" || { journalctl -u myacady -n 20 --no-pager; exit 1; }
systemctl is-active --quiet cloudflared && echo "  cloudflared 稼働中" || { journalctl -u cloudflared -n 20 --no-pager; exit 1; }
REMOTE

# ---- 7. サーバの中から見えるか ----
say "7/8  サーバの中から確かめます"
$SSH 'curl -s --max-time 5 http://127.0.0.1:8765/api/health; echo'

# ---- 8. 外から見えるか ----
say "8/8  外から確かめます"
i=0
while [ $i -lt 20 ]; do
  c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
      "https://$CF_HOST/api/health" 2>/dev/null || true)
  case "$c" in
    2*) echo "  OK  https://$CF_HOST/  （${c}）"; break ;;
  esac
  printf "  待っています… %s\n" "${c:-応答なし}"
  sleep 5
  i=$((i+1))
done

say "まとめ"
curl -s --max-time 15 "https://$CF_HOST/api/health"; echo
echo
echo "  講師に配るURL   https://$CF_HOST/     （変わりません）"
echo "  記録の場所      サーバの /srv/myacady/"
echo "  Macは不要       閉じても止まりません"
echo
echo "  ようす          ssh -i $KEY $SSHUSER@$HOST 'systemctl status myacady'"
echo "  記録の書き出し  sh deploy/aws.sh-backup（次に作ります）"
echo
echo "★ デモの合言葉は出ません（--demo を付けていない）。"
echo "  本番の名簿を作るには、サーバで:"
echo "    ssh -i $KEY $SSHUSER@$HOST"
echo "    sudo -u myacady MYACADY_ROOT=/srv/myacady \\"
echo "      python3 /opt/myacady/server/tube_server.py roster-import 名簿.csv --school london --yes"
