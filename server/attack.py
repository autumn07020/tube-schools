#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自己攻撃。8932 のデモサーバに対して、侵入できる所を探す。
各項目は「守れていれば PASS、破れたら FAIL」で出す。"""
import json, urllib.request, urllib.error, sys
import os
BASE = os.environ.get("ATTACK_BASE", "http://127.0.0.1:8932")
def req(method, path, tok=None, body=None, raw=False):
    url = BASE + path
    data = None; hdr = {}
    if body is not None:
        data = json.dumps(body).encode(); hdr["Content-Type"]="application/json"
    if tok: hdr["Authorization"] = "Bearer " + tok
    r = urllib.request.Request(url, data=data, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            b = resp.read()
            return resp.status, (b if raw else b.decode("utf-8","replace"))
    except urllib.error.HTTPError as e:
        b = e.read()
        return e.code, (b if raw else b.decode("utf-8","replace"))
    except Exception as e:
        return 0, str(e)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scram   # 入る手順（合言葉そのものは送らない）
def login(lid, pw, admin=False):
    st, body = scram.login(BASE, lid, pw, admin=admin)
    if st==200:
        return body
    return None
P=F=0
def check(ok, name, detail=""):
    global P,F
    if ok: P+=1; print("  PASS  "+name)
    else:  F+=1; print("  FAIL  "+name+("  <<< "+detail if detail else ""))

print("=== 1. 静的配信（一覧・ドットファイル・拡張子なし）===")
st,b = req("GET","/content/"); check(st==404 or "Directory listing" not in b, "ディレクトリ一覧が出ない (/content/)", "%s"%st)
st,b = req("GET","/content/math/"); check(st==404 or "Directory listing" not in b, "ディレクトリ一覧が出ない (/content/math/)", "%s"%st)
st,b = req("GET","/js/"); check(st==404 or "Directory listing" not in b, "ディレクトリ一覧が出ない (/js/)", "%s"%st)
st,b = req("GET","/content/.DS_Store", raw=True); check(st==404, ".DS_Store が出ない", "%s"%st)
st,b = req("GET","/.DS_Store", raw=True); check(st==404, "ルートの .DS_Store が出ない", "%s"%st)

print("=== 2. 認証なしでの API アクセス ===")
for path in ("/api/me","/api/class","/api/p/ABCD1234","/api/growth","/api/messages"):
    st,b = req("GET",path); check(st==401, "未ログインで 401 (%s)"%path, "%s"%st)

print("=== 3. ログインして、他人の記録を読めるか（IDOR）===")
# デモの合言葉
teacher = login("lteacher1","lantern-4821")
s1 = login("lj2r01","harbor-3157")   # 中2R-01
check(bool(s1), "生徒がログインできる", "login failed")
if s1:
    mysid = s1["profile"].get("sid")
    tok = s1["token"]
    # 自分は読める
    st,b = req("GET","/api/p/%s"%mysid, tok=tok); check(st in (200,404), "自分の記録は読める(%s)"%st)
    # 他人のsidを総当たり的に少し試す（存在する別sidを講師の名簿から得る）
    if teacher:
        st,cb = req("GET","/api/class", tok=teacher["token"])
        others=[]
        if st==200:
            cbj=json.loads(cb); rows=cbj.get("students") if isinstance(cbj,dict) else cbj
            for row in (rows or []):
                sid=row.get("sid")
                if sid and sid!=mysid: others.append(sid)
        tgt = others[0] if others else "AAAA1111"
        st,b = req("GET","/api/p/%s"%tgt, tok=tok); check(st==403, "他の生徒の記録は 403 (%s)"%st, b[:80])
        st,b = req("GET","/api/p/%s/head"%tgt, tok=tok); check(st==403, "他の生徒の見出しも 403 (%s)"%st)
        # 生徒が講師専用ルートを叩く
        st,b = req("GET","/api/class", tok=tok); check(st==403, "生徒は名簿を読めない(%s)"%st)
        # 他人の答案画像
        st,b = req("GET","/api/submissions/xxxx/%s/foo.jpg"%tgt, tok=tok); check(st in (403,400,404), "他人の答案画像は読めない(%s)"%st)

print("=== 4. 教材データが未ログインで丸ごと落とせるか（著作権・情報漏れ）===")
st,b = req("GET","/content/manifest.js"); 
check(st==200, "manifest は今は公開（part3 で要対処）(%s)"%st, "現状 200: 未ログインで教材が取れる")

print("=== 5. 管理の口（席・講師・担当を作り変える口）に、管理者でない人が入れるか ===")
st,b = req("GET","/api/admin/state"); check(st==401, "未ログインで 401 (/api/admin/state)", "%s"%st)
st,b = req("GET","/api/admin/reports"); check(st==401, "未ログインで 401 (/api/admin/reports)", "%s"%st)
for who, acc in (("講師", teacher), ("生徒", s1)):
    if not acc: continue
    tk = acc["token"]
    st,b = req("GET","/api/admin/state", tok=tk); check(st==403, "%sは管理の口を読めない(%s)"%(who,st), b[:80])
    st,b = req("POST","/api/admin/seats", tok=tk, body={"classId":"e4a","verifiers":[{"alg":"scram-sha256","iters":600000,"salt":"0"*32,"storedKey":"0"*64,"serverKey":"0"*64}]}); check(st==403, "%sは席を足せない(%s)"%(who,st))
    st,b = req("POST","/api/admin/accounts/state", tok=tk, body={"ids":["lteacher2"],"state":"left"}); check(st==403, "%sは在籍を終わらせられない(%s)"%(who,st))
    st,b = req("POST","/api/admin/accounts/lteacher2/password", tok=tk, body={"verifier":{"alg":"scram-sha256","iters":600000,"salt":"0"*32,"storedKey":"0"*64,"serverKey":"0"*64}}); check(st==403, "%sは他人の合言葉を作り直せない(%s)"%(who,st))
    st,b = req("PUT","/api/admin/courses/teacher", tok=tk, body={"key":"e4a:math","id":"lteacher2","on":True}); check(st==403, "%sは担当を変えられない(%s)"%(who,st))
# 「管理者として入る」の印を付けても、役割は変わらない
j = login("lteacher1","lantern-4821",admin=True)
if j:
    check(j["profile"].get("role")=="teacher", "印を付けて入っても講師のまま")
    st,b = req("GET","/api/admin/state", tok=j["token"]); check(st==403, "印を付けて入っても管理の口は 403(%s)"%st)
# http で来た口は、合言葉を受けない（中継の見出しを付けて）
st, b = scram.login(BASE, "lteacher1", "lantern-4821", headers={"CF-Visitor":'{"scheme":"http"}'})
check(st==400, "http で来たログインは受けない(%s)"%st)
# 前の口（合言葉そのものを送る形）は閉じてある。送っても入れない。
st,b = req("POST","/api/login",body={"id":"lteacher1","password":"lantern-4821"}); check(st==400, "合言葉そのものを送る口は閉じている(%s)"%st)
# 入る手順：同じ証明を2度使えない・無いIDにも同じ形の返事
import secrets as _sec
cn = _sec.token_urlsafe(18)
st,b = req("POST","/api/login/start",body={"id":"lteacher1","cnonce":cn}); d1 = json.loads(b) if st==200 else {}
st,b = req("POST","/api/login/start",body={"id":"nai-no-hito","cnonce":cn}); d2 = json.loads(b) if st==200 else {}
check(bool(d1) and bool(d2) and set(d1)==set(d2) and len(d1.get("salt",""))==len(d2.get("salt",""))==32 and d1.get("iters")==d2.get("iters"), "無いIDにも、あるIDと同じ形の返事（あるかどうかを教えない）")
st,b = req("POST","/api/login/start",body={"id":"nai-no-hito","cnonce":cn}); d3 = json.loads(b) if st==200 else {}
check(d2.get("salt")==d3.get("salt"), "無いIDの塩は、何度聞いても同じ")
if d1:
    sp = scram.salted("lantern-4821", d1["salt"], d1["iters"]); au = scram.auth_message("lteacher1", d1["nonce"], d1["salt"], d1["iters"])
    body = {"id":"lteacher1","nonce":d1["nonce"],"proof":scram.client_proof(sp, au)}
    st1,_ = req("POST","/api/login/finish",body=body); st2,_ = req("POST","/api/login/finish",body=body)
    check(st1==200 and st2==401, "同じ証明は2度使えない(%s,%s)"%(st1,st2))
st,b = req("POST","/api/login/start",body={"id":"lteacher1","cnonce":"x"}); check(st==400, "形のおかしい nonce は受けない(%s)"%st)
# 報告の口に大きなもの・印つきの文を送っても、切って文字として置くだけ
if s1:
    st,b = req("POST","/api/report", tok=s1["token"], body={"kind":"error","text":"<script>alert(1)</script>"+"x"*20000,"view":"v"*500,"ctx":{"a":"b"*5000}})
    check(st==200, "報告は受ける（長さは切る）(%s)"%st)
st,b = req("POST","/api/report", body={"text":"x"}); check(st==401, "未ログインは報告できない(%s)"%st)
# 設定で学年・クラス・科目を変える口：未ログインは 401、講師は 403、生徒でも無いクラス・決まった組でない科目は 400
st,b = req("PUT","/api/me/placement", body={"classId":"j3t"}); check(st==401, "未ログインは設定を変えられない(%s)"%st)
if teacher:
    st,b = req("PUT","/api/me/placement", tok=teacher["token"], body={"classId":"j3t"}); check(st==403, "講師は生徒の設定の口を使えない(%s)"%st)
if s1:
    st,b = req("PUT","/api/me/placement", tok=s1["token"], body={"classId":"nai9z"}); check(st==400, "無いクラスには変えられない(%s)"%st)
    st,b = req("PUT","/api/me/placement", tok=s1["token"], body={"subjects":["math"]}); check(st==400, "決まった組でない科目には変えられない(%s)"%st)
st,b = req("PUT","/api/admin/roster", body={"rows":[]}); check(st in (401,404), "引退した口（Excel 同期）は無い(%s)"%st)

print("=== 5b. 初回登録の口（入る前の口。だれでも呼べる）===")
def jreq(path, body, ip):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "CF-Connecting-IP": ip}, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)
st,b = jreq("/api/join/check", {"code": "ZZZZZZ"}, "203.0.113.90"); check(st==403 and "school" not in b, "でたらめな登録コードは通らない(%s)"%st, b[:80])
st,b = jreq("/api/join", {"code": "ZZZZZZ", "agree": True, "students": [{"grade":"e4","classId":"e4a","subjects":["japanese","math"]}]}, "203.0.113.90"); check(st==403, "コードが無ければ口座を作れない(%s)"%st, b[:80])
st,b = jreq("/api/join/finish", {"items": [{"id": "lteacher1", "setup": "x", "verifier": {"alg":"scram-sha256","iters":600000,"salt":"0"*32,"storedKey":"0"*64,"serverKey":"0"*64}}]}, "203.0.113.90")
check(st==410 and bool(login("lteacher1","lantern-4821")), "登録の口から、ある口座の合言葉を置き換えられない(%s)"%st, b[:80])
codes = [jreq("/api/join/check", {"code": "ZZZZ%02d" % i}, "203.0.113.91")[0] for i in range(22)]
check(codes.count(403) == 20 and codes[-1] == 429, "登録コードの総当たりは 20回で止まる(%s)" % codes[-3:])
st,b = jreq("/api/join/check", {"code": "ZZZZZZ"}, "203.0.113.92"); check(st==403, "よその相手は、その上限に巻き込まれない(%s)"%st)

print("=== 6. 入口を止める攻撃（締め出し・埋める・落とす・送り先のすり替え）===")
# よその人が、人のIDに何度もまちがえる。前は 8回で本人まで 15分入れなくなった。
YOSO = {"CF-Connecting-IP": "203.0.113.77"}
codes = [scram.login(BASE, "lteacher1", "chigau-aikotoba-%04d" % i, headers=YOSO)[0] for i in range(10)]
check(codes.count(401) == 8 and codes[-1] == 429, "よその相手からの試しは 8回で止まる(%s)" % codes)
check(bool(login("lteacher1", "lantern-4821")), "そのあいだも、本人は入れる（よその人に締め出されない）")
# 始めるだけを大量に送る。前は、覚える数の上限まで埋めると、誰も入れなくなった。
for i in range(600):
    req("POST", "/api/login/start", body={"id": "lteacher%d" % (i % 9), "cnonce": _sec.token_urlsafe(18)})
check(bool(login("lteacher1", "lantern-4821")), "始めるだけを 600本送られても、入れる")
# 深すぎる入れ子の本文
def raw_post(path, blob):
    r = urllib.request.Request(BASE + path, data=blob, headers={"Content-Type": "application/json"}, method="POST")
    try:
        return urllib.request.urlopen(r, timeout=15).status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return 0
st = raw_post("/api/login/start", b"[" * 200000)
st2, _ = req("GET", "/api/health")
check(st == 400 and st2 == 200, "深すぎる入れ子の本文でも落ちない(%s,%s)" % (st, st2))
# 辞書でない本文（配列・文字列）。前は、そのまま .get を呼んで、その接続が落ちた。
sts = [raw_post("/api/login/start", b) for b in (b"[1]", b'"x"', b"7")] + [raw_post("/api/login/finish", b"[1]")]
check(all(x in (400, 401) for x in sts), "辞書でない本文でも落ちない(%s)" % sts)
# 入る前の口に、大きな本文を何本も同時に送る（前は、12MB を読んでから断っていた）
import threading as _th, time as _tm
big = b'{"id":"' + b"a" * (3 * 1024 * 1024) + b'","cnonce":"' + b"c" * 24 + b'"}'
got = []
def _big():
    try:
        got.append(raw_post("/api/login/start", big))
    except Exception:
        got.append(0)
t0 = _tm.time()
ths = [_th.Thread(target=_big) for _ in range(6)]
[t.start() for t in ths]; [t.join() for t in ths]
st2, _ = req("GET", "/api/health")
check(all(x in (400, 0) for x in got) and st2 == 200 and _tm.time() - t0 < 20, "入る前の口は、大きな本文を読まずに断る(%s, %.1f秒)" % (got, _tm.time() - t0))
# https へ送るときの送り先を、見出しですり替える
import http.client as _hc, urllib.parse as _up
u = _up.urlparse(BASE)
c = _hc.HTTPConnection(u.hostname, u.port, timeout=15)
c.request("GET", "/", headers={"CF-Visitor": '{"scheme":"http"}', "X-Forwarded-Host": "evil.example", "Host": "tube-study.uk"})
r = c.getresponse(); loc = r.getheader("Location") or ""; r.read(); c.close()
check(r.status == 301 and loc == "https://tube-study.uk/", "送り先は Host だけから作る（X-Forwarded-Host は使わない）(%s %s)" % (r.status, loc))

print("\n=== 結果: PASS %d / FAIL %d ==="%(P,F))
sys.exit(1 if F else 0)
