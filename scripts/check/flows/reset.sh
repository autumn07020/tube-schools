#!/bin/sh
# 流れの検査の土台を作り直して、サーバを 8949 で起こす。
#   sh reset.sh <作業の場所>        作業の場所/tube に、ソースの写しがあること
# 中身：架空のデモ校 london（seed＋demo_running。はじめの1回だけ作って demo-base に取っておく）
#       ＋ 本物に似せた校舎 waseaca-london（fixture-bundle.json＝検査用の束。ハッシュだけ。本物の束ではない）
#       ＋ 検査用の口座（合言葉はここに書いてあるとおり。この土台の中でしか通らない）
S="$1"; HERE="$(cd "$(dirname "$0")" && pwd)"
[ -d "$S/tube/server" ] || { echo "使い方: sh reset.sh <作業の場所>（その下に tube/ があること）"; exit 1; }
cd "$S/tube" || exit 1
pkill -f "tube_server.py serve --port 8949" 2>/dev/null; sleep 0.5
if [ ! -f "$S/demo-base/demo-accounts.json" ]; then
  rm -rf "$S/demo-base"; mkdir -p "$S/demo-base"
  MYACADY_FSYNC=0 MYACADY_ROOT="$S/demo-base" python3 server/tube_server.py seed --reset --empty --school london --name ロンドン校 > "$S/demo-base.log" 2>&1
  MYACADY_FSYNC=0 MYACADY_ROOT="$S/demo-base" python3 server/demo_running.py --school london >> "$S/demo-base.log" 2>&1 || { echo "× デモを作れません（$S/demo-base.log）"; exit 1; }
fi
rm -rf "$S/real" && cp -R "$S/demo-base" "$S/real"
export MYACADY_ROOT="$S/real" MYACADY_FSYNC=0
python3 server/tube_server.py bundle-import "$HERE/fixture-bundle.json" --yes | tail -1
python3 server/tube_server.py add wadmin99 A99 --admin --password "kensa-kanri-kensa-kanri-kensa-0000" --school waseaca-london >/dev/null
python3 server/tube_server.py add wt90 T90 --teacher --classes - --password "kensa-sensei-kensa-sensei-0000" --school waseaca-london >/dev/null
python3 server/tube_server.py add we4a20 20 --class e4a --level e4 --password "kensa-seito-kensa-0000" --school waseaca-london >/dev/null
python3 server/tube_server.py add we4a21 21 --class e4a --level e4 --password "kensa-seito-kensa-0021" --school waseaca-london >/dev/null
# 毎日テストを使っていないクラスの生徒（小3J。ためしのデモが段階 4 にするクラスの外。adm_flow2 が使う）
python3 server/tube_server.py add we3j21 21 --class e3j --level e3 --password "kensa-seito-kensa-0321" --school waseaca-london >/dev/null
# 前の形の席（まだ渡していない口座）を3つ。席を先に作る口は引退したので、検査の下ごしらえとして直に置く。
python3 - <<'PY'
import sys, secrets
sys.path.insert(0, "server")
import tube_server as T
for lid, seat in (("we4a22", "22"), ("we4a23", "23"), ("we4a24", "24")):
    T.add_account("waseaca-london", lid, None, seat, "seat", "e4", "e4a",
                  verifier={"alg": "scram-sha256", "iters": 600000, "salt": secrets.token_hex(16), "storedKey": secrets.token_hex(32), "serverKey": secrets.token_hex(32)})
PY
python3 server/tube_server.py school-trial --school waseaca-london --on
# 本番と同じ形に：時間割（コマ.csv）・担当（担当.csv）・見本の講師 wt03〜wt06（束には wt01・wt02 しか無い）・
# ためし運用のデモ（demo_trial.py：本人 wt01 の担当コース全部と、ほかの講師の見本1教科ずつ。ためし用の生徒 wd<クラス>91/92 を作る）。10-10
for t in wt03 wt04 wt05 wt06 wt07; do     # 担当.csv に wt07 もいる（1行でも講師が無いと何も入らない）
  python3 server/tube_server.py add "$t" "T${t#wt}" --teacher --classes - --password "kensa-sensei-kensa-sensei-0000" --school waseaca-london >/dev/null
done
python3 server/tube_server.py courses-slots カリキュラム/コマ.csv --school waseaca-london --yes > "$S/slots.log" 2>&1 || { echo "× 時間割を入れられません"; tail -3 "$S/slots.log"; }
python3 server/tube_server.py courses-teachers カリキュラム/担当.csv --school waseaca-london --yes > "$S/tantou.log" 2>&1 || { echo "× 担当を入れられません"; tail -3 "$S/tantou.log"; }
# ためしのデモが選ぶ席：クラスごとに 10（w<クラス>51〜60）。検査が決め打ちで使う席（we4a01〜03・we4a22〜24）は選ばせない（--keep）。
# 入口の生徒（trialPick）に、検査が使うクラス（j3r・e4b・e5b・e4a・j2r）の見本も足す（--pick-classes）。10-12
python3 - <<'PY'
import sys, secrets
sys.path.insert(0, "server")
import tube_server as T
school = "waseaca-london"
classes = sorted({a.get("classId") for a in T.accounts(school).values() if a.get("classId") and a.get("role") in ("student", "seat")})
db = T.accounts(school)
for cls in classes:
    for n in range(51, 61):
        lid = "w%s%d" % (cls, n)
        if lid in db: continue
        T.add_account(school, lid, None, str(n), "seat", T.gradeOfClass(school, cls) or "", cls,
                      verifier={"alg": "scram-sha256", "iters": 600000, "salt": secrets.token_hex(16), "storedKey": secrets.token_hex(32), "serverKey": secrets.token_hex(32)})
PY
python3 server/demo_trial.py --school waseaca-london --me wt01 --pick-classes j3r,e4b,e5b,e4a,j2r --keep we4a01,we4a02,we4a03,we4a20,we4a21,we4a22,we4a23,we4a24,we4b01,we4b02,we4b03,we3j21 > "$S/trial.log" 2>&1 || { echo "× ためしのデモを作れません"; tail -5 "$S/trial.log"; }
# 入口の一覧の先頭に、本物の形の校舎の講師（wt90・wt01・wt02）と 検査用の生徒 we4a20 を ID だけで足す
# （本番の deploy/ためしに見る.json と同じ形。10-10）。ためしのデモの生徒は school.json の trialPick からサーバが出す（10-12）。
python3 - "$S/real/demo-accounts.json" <<'PY'
import io, json, sys
p = sys.argv[1]
rows = json.load(io.open(p, encoding="utf-8"))
head = [{"id": "wt90", "role": "teacher", "label": "講師 wt90"},
        {"id": "we4a20", "role": "student", "note": "ためし用"},
        {"id": "wt01", "role": "teacher", "label": "講師 wt01"},
        {"id": "wt02", "role": "teacher", "label": "講師 wt02"}]
ids = {r["id"] for r in head}
rows = head + [r for r in rows if r.get("id") not in ids]
io.open(p, "w", encoding="utf-8").write(json.dumps(rows, ensure_ascii=False, indent=1))
PY
nohup python3 server/tube_server.py serve --port 8949 --demo --demo-file "$S/real/demo-accounts.json" > "$S/srv8949.log" 2>&1 &
sleep 2; curl -s http://127.0.0.1:8949/api/health; echo
