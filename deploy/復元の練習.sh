#!/bin/sh
# 復元の練習 ―― S3 の控え（tar.gz）を手元の Mac に戻し、動かして、「戻せた」と言える条件を機械で確かめる。
#
#   sh deploy/復元の練習.sh <控えの tar.gz>                  # 手元にある控え（aws s3 cp で取ったもの）
#   sh deploy/復元の練習.sh s3://<バケット>/<日付>.tar.gz     # S3 から取る（aws CLI と本人の鍵が要る）
#
#   KEEP=1      終わっても手元のサーバを止めない（画面で見る：http://127.0.0.1:8960）
#   PORT=8960   手元のサーバの口
#   CLASS=j3r LEVEL=j3   「新しい口座」を入れるクラス（アプリを使っていて、今週の宿題があるクラス）
#   ACCOUNTS=deploy/demo-accounts.json   意味の検査（expect.py）が入るデモ校の口座（手元だけのファイル）
#
# 本番には触れない（読むことすらしない）。復元先は <置き場>/復元.nosync/<日付時刻>/（Git にも iCloud にも入らない）。
# 戻した中身には本物の口座の検証子が入っている。練習が終わったら消す（最後に命令を出す）。
# 段取りと「戻せたと言える条件」は knowledge/40-運用/復元の練習.md。
set -u
HERE=$(cd "$(dirname "$0")" && pwd); ROOT_DIR=${TUBE_ROOT:-$(dirname "$HERE")}; cd "$ROOT_DIR" || exit 1   # TUBE_ROOT は検査で別の場所から流すとき
SRC="${1:?使い方: sh deploy/復元の練習.sh <控えの tar.gz か s3://…/日付.tar.gz>}"
PORT=${PORT:-8960}; CLASS=${CLASS:-j3r}; LEVEL=${LEVEL:-j3}; KEEP=${KEEP:-0}
ACCOUNTS=${ACCOUNTS:-deploy/demo-accounts.json}
STAMP=$(date +%Y%m%d-%H%M%S); DIR="$ROOT_DIR/復元.nosync/$STAMP"; ROOT="$DIR/myacady"
mkdir -p "$DIR"
T0=$(date +%s); step_t=$T0
say(){ printf '\n\033[1m%s\033[0m\n' "$*"; }
lap(){ now=$(date +%s); printf '   （%d 秒）\n' $((now - step_t)); step_t=$now; }
NG=0; fail(){ echo "   × $*"; NG=$((NG+1)); }
SRV=""
stop_srv(){ [ -n "$SRV" ] && kill "$SRV" 2>/dev/null; SRV=""; }

# ---- 1. 取る ----
say "1. 控えを取る"
case "$SRC" in
  s3://*) command -v aws >/dev/null || { echo "aws CLI が無い（brew install awscli）"; exit 2; }
          aws s3 cp "$SRC" "$DIR/控え.tar.gz" --only-show-errors || { echo "S3 から取れなかった（鍵・バケット名・日付を確かめる）"; exit 2; } ;;
  *)      [ -f "$SRC" ] || { echo "無い: $SRC"; exit 2; }; cp "$SRC" "$DIR/控え.tar.gz" ;;
esac
SIZE=$(du -h "$DIR/控え.tar.gz" | cut -f1); echo "   $SRC → $SIZE"; lap

# ---- 2. 展開 ----
say "2. 展開する（$DIR）"
tar -xzf "$DIR/控え.tar.gz" -C "$DIR" || { echo "展開できない（壊れた控え？）"; exit 3; }
[ -d "$ROOT/schools" ] || { echo "展開したが myacady/schools が無い（控えの形が違う）"; ls "$DIR"; exit 3; }
lap

# ---- 3. 中身（読むだけ） ----
say "3. 中身を数える（読むだけ）"
python3 - "$ROOT" <<'PY' || NG=$((NG+1))
import glob, json, os, sys, time
root = sys.argv[1]; now = time.time()
def jl(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d
idx = jl(os.path.join(root, "index.json"), {}) or {}
print("   index.json: %d 件の ID" % len(idx))
print("   demo-accounts.json: %s" % ("ある" if os.path.exists(os.path.join(root, "demo-accounts.json")) else "無い"))
newest = 0
for sd in sorted(glob.glob(os.path.join(root, "schools", "*"))):
    s = os.path.basename(sd)
    if s.startswith("."): continue
    acc = jl(os.path.join(sd, "accounts.json"), {}) or {}
    by = {}
    for a in acc.values(): by[a.get("role")] = by.get(a.get("role"), 0) + 1
    asg = jl(os.path.join(sd, "assignments.json"), {}) or {}
    subs = jl(os.path.join(sd, "submissions.json"), {}) or {}
    nsub = sum(len(v) for v in subs.values()) if isinstance(subs, dict) else 0
    meta = jl(os.path.join(sd, "school.json"), {}) or {}
    last = 0
    try:
        with open(os.path.join(sd, "audit.log"), "rb") as f:
            f.seek(0, 2); n = f.tell(); f.seek(max(0, n - 4000)); tail = f.read().decode("utf-8", "ignore").strip().split("\n")
            last = int((json.loads(tail[-1]) or {}).get("ts") or 0)
    except Exception: pass
    newest = max(newest, last)
    flag = "デモ" if meta.get("demo") else ("本番" if meta.get("live") else ("ためし運用" if meta.get("trial") else ""))
    print("   %-16s %s  口座 %s  宿題 %d  提出 %d  最後の記録 %s" % (
        s, flag, " ".join("%s %d" % kv for kv in sorted(by.items())), len(asg), nsub,
        time.strftime("%m-%d %H:%M", time.localtime(last)) if last else "-"))
if newest:
    print("   控えの新しさ：最後の記録から %.1f 時間" % ((now - newest) / 3600))
PY
lap

# ---- 4. 起動 ----
say "4. 戻した置き場でサーバを起こす（127.0.0.1:$PORT。本番とは別物）"
DEMOF="$ROOT/demo-accounts.json"; [ -f "$DEMOF" ] || DEMOF="$ACCOUNTS"
MYACADY_ROOT="$ROOT" MYACADY_FSYNC=0 python3 server/tube_server.py serve --host 127.0.0.1 --port "$PORT" --demo --demo-file "$DEMOF" > "$DIR/serve.log" 2>&1 &
SRV=$!
i=0; until curl -s -o /dev/null "http://127.0.0.1:$PORT/api/health"; do i=$((i+1)); [ $i -gt 40 ] && { fail "20 秒待っても起きない（$DIR/serve.log）"; tail -5 "$DIR/serve.log"; stop_srv; exit 4; }; sleep 0.5; done
echo "   health: $(curl -s "http://127.0.0.1:$PORT/api/health" | cut -c1-120)"; lap

# ---- 5. 検査 1：意味の検査（本番の控えの数と突き合わせる） ----
say "5. 意味の検査（expect.py。前回の本番の数 scripts/check/ledger-production.json と比べる）"
cp scripts/check/ledger-production.json "$DIR/ledger.json"
if [ -f "$ACCOUNTS" ]; then
  python3 scripts/check/expect.py --base "http://127.0.0.1:$PORT" --accounts "$ACCOUNTS" --ledger "$DIR/ledger.json" > "$DIR/expect.log" 2>&1; rc=$?
else
  echo "   $ACCOUNTS が無い（手元だけのファイル）。門の検査だけ流す"
  echo '[]' > "$DIR/accounts-none.json"
  python3 scripts/check/expect.py --base "http://127.0.0.1:$PORT" --accounts "$DIR/accounts-none.json" --ledger "$DIR/ledger.json" > "$DIR/expect.log" 2>&1; rc=$?
fi
EXPECT=$(tail -1 "$DIR/expect.log" | cut -c1-100); echo "   $EXPECT"
[ "$rc" = 0 ] || { fail "expect.py が通らない（$DIR/expect.log の × と △ を読む）"; grep -E '^\s*(×|△)' "$DIR/expect.log" | head -8; }
lap

# ---- 6. 検査 2：戻せたと言える条件 ―― 新しく作った口座に、今週の宿題が見える ----
say "6. 戻した置き場に新しい口座を作り、今週の宿題が見えるか（クラス $CLASS）"
NEWID="wfk$(date +%m%d%H%M)"; NEWPW="fukugen-renshu-$(date +%H%M)-0000"
MYACADY_ROOT="$ROOT" MYACADY_FSYNC=0 python3 server/tube_server.py add "$NEWID" 97 --class "$CLASS" --level "$LEVEL" --password "$NEWPW" --school waseaca-london > "$DIR/add.log" 2>&1 \
  || { fail "口座を作れない（$DIR/add.log）"; cat "$DIR/add.log" | tail -3; }
python3 - "http://127.0.0.1:$PORT" "$NEWID" "$NEWPW" <<'PY' || NG=$((NG+1))
import json, sys, time, urllib.request
sys.path.insert(0, "server"); import scram
base, lid, pw = sys.argv[1:4]
st, body = scram.login(base, lid, pw)
if st != 200 or not isinstance(body, dict) or not body.get("token"):
    print("   × 新しい口座で入れない:", st, str(body)[:120]); sys.exit(1)
tok = body["token"]
def get(p):
    r = urllib.request.Request(base + "/api" + p, headers={"Authorization": "Bearer " + tok})
    return json.loads(urllib.request.urlopen(r, timeout=60).read().decode())
me = get("/me"); rows = (get("/assignments") or {}).get("assignments") or []
now = time.time() * 1000
opened = [a for a in rows if int(a.get("dueAt") or 0) >= now]
subj = sorted({a.get("subject") or "?" for a in opened})
print("   %s（%s）で入れた。宿題 %d 件、期限前 %d 件（%s）" % (lid, me.get("classId") or me.get("grade") or "", len(rows), len(opened), "・".join(subj)))
if not opened:
    print("   × 期限前の宿題が 1 件も無い（戻せたと言えない：join_open_homework が効いていないか、控えが古い）"); sys.exit(1)
print("   OK 新しい口座に今週の宿題が見える")
PY
lap

# ---- 7. まとめ ----
T1=$(date +%s)
say "まとめ"
echo "   控え: $SRC（$SIZE）  戻した場所: $DIR"
echo "   意味の検査: $EXPECT"
echo "   新しい口座: $NEWID（クラス $CLASS）"
echo "   かかった時間: $(( (T1 - T0) / 60 )) 分 $(( (T1 - T0) % 60 )) 秒   通らなかった段: $NG"
echo
echo "   記録に写す行（knowledge/40-運用/復元の練習.md の表）："
echo "   | $(date +%Y-%m-%d) | $(basename "$SRC") | $SIZE | $EXPECT | 新しい口座 $([ "$NG" = 0 ] && echo OK || echo NG) | $(( (T1 - T0) / 60 )) 分 | 本人 |"
echo
if [ "$KEEP" = 1 ]; then
  echo "   KEEP=1：手元のサーバは動いたまま（http://127.0.0.1:$PORT/demo）。止めるには  kill $SRV"
else
  stop_srv
fi
echo "   終わったら消す（本物の口座の検証子が入っている）：  rm -rf \"$DIR\""
[ "$NG" = 0 ]
