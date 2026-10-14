#!/usr/bin/env bash
# ============================================================
# 毎日のバックアップを仕掛ける
#
#   ./backup-setup.sh 静的IP バケット名
#
# 鍵をサーバのファイルに置かない。IAMロールで権限を渡す。
# キーをファイルに置くと、サーバが破られたときバックアップまで消される。
# ============================================================
set -euo pipefail

HOST="${1:?使い方: ./backup-setup.sh 静的IP バケット名}"
BUCKET="${2:?使い方: ./backup-setup.sh 静的IP バケット名}"
USER="${SSH_USER:-ubuntu}"

cat <<NOTE

事前に、AWS の画面で次を済ませてください（5分）。

 1. S3 でバケットを作る: ${BUCKET}
      リージョン    London (eu-west-2)
      公開アクセス  すべてブロック（既定のまま）
      バージョニング 有効にする  ← 消されても戻せる
      ライフサイクル 30日で削除

 2. Lightsail の画面で、このインスタンスに IAM ロールを付ける
      権限は下の1つだけ。他は付けない。

    {
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Action": ["s3:PutObject"],
        "Resource": "arn:aws:s3:::${BUCKET}/*"
      }]
    }

    PutObject だけにしてあるのは、サーバが破られても
    **過去のバックアップを読むことも消すこともできない**ようにするため。

NOTE
read -r -p "済んだら Enter（やめるなら Ctrl+C）"

ssh "$USER@$HOST" "sudo bash -s -- '$BUCKET'" <<'REMOTE'
set -euo pipefail
BUCKET="$1"

command -v aws >/dev/null || {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq && apt-get install -y -qq awscli >/dev/null
}

cat > /usr/local/bin/myacady-backup <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
STAMP="\$(date -u +%Y%m%d-%H%M%S)"
OUT="/tmp/myacady-\${STAMP}.tar.gz"

# 書き込み中のファイルを掴まないよう、一瞬止めてから取る。
# 止まるのは1秒未満。生徒の端末は行列に積むので、学習は途切れない。
systemctl stop myacady
tar -czf "\$OUT" -C /srv myacady
systemctl start myacady

aws s3 cp "\$OUT" "s3://${BUCKET}/\${STAMP}.tar.gz" --only-show-errors
rm -f "\$OUT"
logger -t myacady-backup "backup done: \${STAMP}"
SCRIPT
chmod 700 /usr/local/bin/myacady-backup

cat > /etc/systemd/system/myacady-backup.service <<UNIT
[Unit]
Description=Tube for Schools backup to S3

[Service]
Type=oneshot
ExecStart=/usr/local/bin/myacady-backup
UNIT

cat > /etc/systemd/system/myacady-backup.timer <<UNIT
[Unit]
Description=Tube for Schools backup (daily 03:00)

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now myacady-backup.timer >/dev/null
echo "  仕掛けました。次回: $(systemctl list-timers myacady-backup.timer --no-pager | sed -n 2p | awk '{print $1, $2}')"
REMOTE

cat <<DONE

いますぐ1回とってみる（動作確認）

  ssh $USER@$HOST 'sudo systemctl start myacady-backup && sudo journalctl -t myacady-backup -n 3'

戻すとき

  aws s3 cp s3://${BUCKET}/日付.tar.gz .
  ssh $USER@$HOST 'sudo systemctl stop myacady'
  scp 日付.tar.gz $USER@$HOST:/tmp/
  ssh $USER@$HOST 'sudo tar -xzf /tmp/日付.tar.gz -C /srv && sudo systemctl start myacady'

  ★ 復元は年に一度でも試しておくこと。
    試したことのないバックアップは、バックアップではありません。

DONE
