#!/usr/bin/env bash
# ============================================================
# Tube for Schools ―― Lightsail 1台への配備
#
#   ./deploy.sh app.example.com 静的IP
#
# 何度流しても同じ結果になるように書いてある（冪等）。
# 設定を変えたら、もう一度これを流せばよい。
# ============================================================
set -euo pipefail

DOMAIN="${1:?使い方: ./deploy.sh app.example.com 静的IP}"
HOST="${2:?使い方: ./deploy.sh app.example.com 静的IP}"
USER="${SSH_USER:-ubuntu}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

say(){ printf "\n\033[1m%s\033[0m\n" "$*"; }

say "1/6  つながるか確かめる"
ssh -o ConnectTimeout=10 -o BatchMode=yes "$USER@$HOST" 'echo "  つながりました: $(hostname)"'

say "2/6  DNS がこのサーバを向いているか"
GOT="$(dig +short "$DOMAIN" | tail -1 || true)"
if [ "$GOT" != "$HOST" ]; then
  echo "  ⚠ $DOMAIN は $GOT を向いています（期待: ${HOST}）"
  echo "    このまま進めると TLS 証明書が取得できません。"
  read -r -p "    それでも続けますか？ [y/N] " a
  [ "$a" = "y" ] || exit 1
else
  echo "  OK ($GOT)"
fi

say "3/6  必要なものを入れる"
ssh "$USER@$HOST" 'sudo bash -s' <<'REMOTE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv rsync curl debian-keyring debian-archive-keyring apt-transport-https >/dev/null

# Caddy（TLS を自動で取り、更新もする）
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq && apt-get install -y -qq caddy >/dev/null
fi

# アプリ専用の利用者。root では動かさない。
id -u myacady >/dev/null 2>&1 || useradd --system --home /srv/myacady --shell /usr/sbin/nologin myacady
mkdir -p /opt/myacady /srv/myacady
chown -R myacady:myacady /srv/myacady
chmod 750 /srv/myacady
echo "  下ごしらえ 完了"
REMOTE

say "4/6  アプリを送る"
rsync -az --delete \
  --exclude '__pycache__' --exclude '*.pyc' --exclude 'data' --exclude 'data.bak-*' \
  --rsync-path='sudo rsync' \
  "$HERE/app" "$HERE/server" "$USER@$HOST:/opt/myacady/"
ssh "$USER@$HOST" 'sudo chown -R root:root /opt/myacady && echo "  転送 完了"'

say "5/6  サービスとして登録する"
ssh "$USER@$HOST" "sudo bash -s -- '$DOMAIN'" <<'REMOTE'
set -euo pipefail
DOMAIN="$1"

cat > /etc/systemd/system/myacady.service <<UNIT
[Unit]
Description=Tube for Schools
After=network.target

[Service]
Type=simple
User=myacady
Group=myacady
WorkingDirectory=/opt/myacady
Environment=MYACADY_ROOT=/srv/myacady
# 127.0.0.1 にしか口を開けない。外からは Caddy 経由でしか届かない。
# --demo は付けない（付けると合言葉が画面に出る）。
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
MemoryMax=1G

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/caddy/Caddyfile <<CADDY
${DOMAIN} {
	encode gzip
	reverse_proxy 127.0.0.1:8765
	# アプリ自身も同じ見出しを付けるが、手前でも付けておく。
	header {
		Strict-Transport-Security "max-age=31536000; includeSubDomains"
		X-Content-Type-Options "nosniff"
		Referrer-Policy "no-referrer"
		-Server
	}
	log {
		output file /var/log/caddy/access.log
		format json
	}
}
CADDY

systemctl daemon-reload
systemctl enable --now myacady >/dev/null
systemctl restart myacady
systemctl reload caddy 2>/dev/null || systemctl restart caddy
sleep 2
systemctl is-active --quiet myacady && echo "  myacady 稼働中" || { journalctl -u myacady -n 20 --no-pager; exit 1; }
REMOTE

say "6/6  外から見えるか"
sleep 3
CODE="$(curl -s -o /dev/null -w '%{http_code}' "https://$DOMAIN/api/health" || true)"
if [ "$CODE" = "200" ]; then
  echo "  OK  https://$DOMAIN/"
  curl -s "https://$DOMAIN/api/health"; echo
else
  echo "  ⚠ https://$DOMAIN/api/health が $CODE を返しました"
  echo "    証明書の取得に少し時間がかかることがあります。1分ほど待って:"
  echo "      curl https://$DOMAIN/api/health"
  echo "    それでも駄目なら: ssh $USER@$HOST 'sudo journalctl -u caddy -n 40'"
fi

cat <<DONE

つぎにやること

  ssh $USER@$HOST
  cd /opt/myacady
  sudo -u myacady MYACADY_ROOT=/srv/myacady python3 server/tube_server.py school-add london 'ロンドン校' --code l
  sudo -u myacady MYACADY_ROOT=/srv/myacady python3 server/tube_server.py roster-import 名簿.csv --school london --yes

バックアップ

  ./backup-setup.sh $HOST バケット名

DONE
