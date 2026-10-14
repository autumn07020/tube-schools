# tube-study.uk を使えるようにする

## まず、思い違いを1つ直します

**Cloudflare にデータは移りません。**

Cloudflare Registrar で買ったのは「名前」だけです。写真や書類を
預ける場所ではなく、住所を登録しただけの状態です。
生徒の記録は、いまも **このMacの中** にあります。

    /tmp/myacady-migrate/schools/london/    ← 試用中のいまの場所
      accounts.json      IDと合言葉（ハッシュ）
      progress/*.json    生徒ひとりずつの記録
      assignments.json   出した宿題
      lessons.json       授業計画

Cloudflare がするのは **道案内だけ** です。
`tube-study.uk` に来た人を、このMacの中のサーバへ運びます。
中身を見たり預かったりはしません。

### 「Cloudflareだけで完結」できるか

**できません。** アプリを動かす場所が別に要ります。選べるのは2つです。

| | 動かす場所 | 費用 | Macを閉じたら | 用意 |
|---|---|---|---|---|
| **A** | このMac | **0円** | 止まる | 20分 |
| **B** | AWS Lightsail | 月$5〜7 | 動き続ける | 40分 |

Cloudflare Workers で完結させる道もありますが、サーバを
Python から JavaScript へ、記録の保管を JSON ファイルから
D1 へ、**全部書き直し**になります。いま採りません。

**今日はAで動かし、落ち着いたらBに移します。**
移るときドメインはそのままです。Aの作業は捨てになりません。

---

## A. 今日やること（20分・費用0円）

### 1. Cloudflare とこのMacをつなぐ

    /Users/aki/bin/cloudflared tunnel login

ブラウザが開きます。**tube-study.uk を選んで許可**してください。
`~/.cloudflared/cert.pem` が作られます。

> これはご自身のアカウントの認証なので、私は代行できません。

### 2. トンネルを1本つくる

    /Users/aki/bin/cloudflared tunnel create tube

「Created tunnel tube with id …」と出れば成功です。

### 3. 名前を割り当てる

    /Users/aki/bin/cloudflared tunnel route dns tube tube-study.uk

**`www` も足しておくこと。**

    /Users/aki/bin/cloudflared tunnel route dns tube www.tube-study.uk

足さないと `www.tube-study.uk` は **名前解決そのものが失敗**する。
資料のQRやリンクは `https://tube-study.uk` を指しているので問題ないが、
人が手で打つときや、住所欄が気をきかせて `www.` を足したときに、
「URLが死んでいる」という形で出る。実際そう言われた。

これで `tube-study.uk` がこのトンネルを指します。
Cloudflare の DNS 画面に CNAME が1行足されます。

### 4. 動かす

    cd ~/Projects/tube-schools
    MYACADY_ROOT=/tmp/myacady-migrate CF_NAME=tube CF_HOST=tube-study.uk \
      sh deploy/run.sh

    講師に配るURL   https://tube-study.uk
                    ★ これは変わりません。

証明書は Cloudflare 側で自動です。何もしません。

### 5. 確かめる

    curl -s https://tube-study.uk/api/health

`{"ok": true, …}` が返れば完了です。

---

## Aのときに知っておくこと

**Macが起きているあいだだけ動きます。**

    システム設定 → バッテリー →
      「ディスプレイがオフのときにMacを自動でスリープさせない」を入

蓋を閉じると止まります。電源につないだまま開いておいてください。

**記録は /tmp にあります。** いまは試用なのでここですが、
**Macを再起動すると消えます。** 本番の名簿を入れる前に移してください。

    mkdir -p ~/myAcady
    cp -R /tmp/myacady-migrate/* ~/myAcady/
    # 以後 MYACADY_ROOT を付けずに起動すれば ~/myAcady を使います

**デモの合言葉が画面に出ています。** 誰でも入れる状態です。
本番の名簿を入れたら必ず

    DEMO=0 CF_NAME=tube CF_HOST=tube-study.uk sh deploy/run.sh

---

## B. あとでやること（AWS へ移す）

急ぎません。Aで講師の確認が済んでから、落ち着いてやってください。

### なぜ移すのか

  * Macを閉じても止まらない
  * 停電・引っ越し・端末の買い替えに影響されない
  * 校舎が増えたとき、時差をまたいで使える

### 移し方（3手）

    # 1. 記録をまるごと持っていく（データベースが無いので、これだけ）
    rsync -az ~/myAcady/ ubuntu@静的IP:/srv/myacady/

    # 2. 配備（Caddy が証明書を自動取得）
    ./deploy/deploy.sh tube-study.uk 静的IP

    # 3. Mac側を止める
    sh deploy/run.sh stop

Lightsail の作り方は `deploy/README.md` にあります。
大きさは実測から **1GB / 40GB SSD** で足ります（サーバのメモリ
使用量は28MB、10校舎3,000名でも通信は月8.7GB）。

### 移したあとのドメイン

`tube-study.uk` はそのままです。DNS を静的IPに向け替えるだけで、
**講師に配ったURLは変わりません。**

---

## 校舎が増えたとき

サブドメインで足せます。ドメインは1つで済みます。

    tube-study.uk           ロンドン校（いま）
    ny.tube-study.uk        NY校
    tokyo.tube-study.uk     東京校

`cloudflared tunnel route dns tube ny.tube-study.uk` を足すだけです。

---

## 困ったとき

| 症状 | 見るところ |
|---|---|
| `tube-study.uk` が開かない | `tail -20 deploy/log/tunnel.log` |
| 証明書のエラー | DNSの浸透待ち。5〜10分おいて再度 |
| 「サーバが見つかりません」 | `sh deploy/run.sh` が動いているか |
| 直したものが出ない | `sh deploy/run.sh reload`（URLは変わりません） |
| ようすを見る | `tail -f deploy/log/watch.log` |
