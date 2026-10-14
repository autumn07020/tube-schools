#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""入るときに、合言葉そのものを送らない（SCRAM-SHA-256 の考え方。RFC 5802）。

何を守るか
----------
前は、入るたびに合言葉を（TLS の中で）サーバへ送り、サーバが照合していた。
TLS をほどく所（Cloudflare）とサーバの中では、合言葉が平文になる。

ここでは、**合言葉は端末から出ない。** 端末は合言葉から鍵を作り、サーバが出した
使い捨ての数（nonce）に対する「証明」だけを送る。サーバは、保存してある値で証明を
確かめられるが、その値からは証明を作れない。

    SaltedPassword = PBKDF2-HMAC-SHA256(そろえた合言葉, salt, iters)      ← 端末だけが作れる
    ClientKey      = HMAC(SaltedPassword, "Client Key")
    StoredKey      = SHA256(ClientKey)                                     ← サーバが持つ
    ServerKey      = HMAC(SaltedPassword, "Server Key")                    ← サーバが持つ
    AuthMessage    = "tubestudy-scram-v1,<id>,<nonce>,<salt>,<iters>"
    証明（proof）  = ClientKey XOR HMAC(StoredKey, AuthMessage)            ← 端末が送る
    サーバの印     = HMAC(ServerKey, AuthMessage)                          ← サーバが返す（端末が確かめる）

* 途中で見ている人は、証明を見ても合言葉が分からず、同じ証明をもう一度使うこともできない
  （nonce は1回きり）。
* サーバの保存（StoredKey・ServerKey・salt）が漏れても、それだけでは入れない（ClientKey が要る）。
  合言葉を当てるには、1つ試すごとに PBKDF2 を 60万回まわす必要がある。
* サーバの印を端末が確かめるので、保存の値を持たない偽のサーバは「入れた」と言えない。

**できないこと（正直に）**：画面のプログラム（js）そのものを書き換えられる相手には効かない。
TLS と CSP（script-src 'self'）が、その前提を支えている。

ここは計算だけ（ファイルにもサーバにも触らない）。サーバ（tube_server）・手元の道具
（scripts/accounts/make.py）・検査が、みなここを使う。画面の側は app/js/scram.js。
**2つは同じ値を出さなければならない**（検査 test_admin が突き合わせる）。
"""

import hashlib
import hmac
import json
import re
import secrets
import unicodedata
import urllib.error
import urllib.request

ALG = "scram-sha256"
ITERS = 600000            # OWASP 2023 の目安（PBKDF2-HMAC-SHA256）。端末で約0.3〜1秒
TAG = "tubestudy-scram-v1"
HEX32 = re.compile(r"^[0-9a-f]{32}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def norm_pw(password):
    """合言葉を、鍵にする前の形にそろえる。

    全角→半角（NFKC）、大文字→小文字、空白と区切りの線（- ー － ‐ _ など）を取る。
    子どもの端末は先頭を大文字にしたり、全角で入れたり、線を入れなかったりする。
    そこで弾くと「カードのとおりに打ったのに入れない」になる。作る側は小文字と数字と線だけ
    なので、そろえても強さは変わらない。**画面の側（scram.js の norm）と同じであること。**
    """
    t = unicodedata.normalize("NFKC", str(password or "")).lower()
    return re.sub(r"[\s\-‐-―−ー－_]+", "", t)


def norm_id(login_id):
    return str(login_id or "").strip().lower()


def salted(password, salt_hex, iters=ITERS):
    return hashlib.pbkdf2_hmac("sha256", norm_pw(password).encode("utf-8"),
                               bytes.fromhex(salt_hex), int(iters))


def keys_from_salted(sp):
    """SaltedPassword（bytes）→ (StoredKey, ServerKey) の16進。"""
    client_key = hmac.new(sp, b"Client Key", hashlib.sha256).digest()
    stored = hashlib.sha256(client_key).hexdigest()
    server = hmac.new(sp, b"Server Key", hashlib.sha256).hexdigest()
    return stored, server


def make_verifier(password, salt=None, iters=ITERS):
    """合言葉から、サーバに置く値を作る。合言葉そのものは入らない。"""
    salt = salt or secrets.token_hex(16)
    stored, server = keys_from_salted(salted(password, salt, iters))
    return {"alg": ALG, "salt": salt, "iters": int(iters), "storedKey": stored, "serverKey": server}


def clean_verifier(v):
    """届いた値の形を確かめ、決まった欄だけを返す。おかしければ ValueError。"""
    if not isinstance(v, dict):
        raise ValueError("合言葉のハッシュがありません")
    if v.get("alg") != ALG:
        raise ValueError("合言葉のハッシュの方式が違います")
    salt, stored, server = (str(v.get(k) or "") for k in ("salt", "storedKey", "serverKey"))
    if not HEX32.match(salt) or not HEX64.match(stored) or not HEX64.match(server):
        raise ValueError("合言葉のハッシュの形が違います")
    if v.get("iters") != ITERS or isinstance(v.get("iters"), bool):
        raise ValueError("合言葉のハッシュの回数が違います")
    return {"alg": ALG, "salt": salt, "iters": ITERS, "storedKey": stored, "serverKey": server}


def auth_message(login_id, nonce, salt, iters):
    return ("%s,%s,%s,%s,%d" % (TAG, login_id, nonce, salt, int(iters))).encode("utf-8")


def _xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def client_proof(sp, auth):
    """端末が送る証明（16進）。sp は SaltedPassword。"""
    client_key = hmac.new(sp, b"Client Key", hashlib.sha256).digest()
    stored = hashlib.sha256(client_key).digest()
    sig = hmac.new(stored, auth, hashlib.sha256).digest()
    return _xor(client_key, sig).hex()


def verify_proof(stored_hex, auth, proof_hex):
    """サーバが証明を確かめる。保存の StoredKey だけで足りる。"""
    if not HEX64.match(str(proof_hex or "")) or not HEX64.match(str(stored_hex or "")):
        return False
    stored = bytes.fromhex(stored_hex)
    sig = hmac.new(stored, auth, hashlib.sha256).digest()
    client_key = _xor(bytes.fromhex(proof_hex), sig)
    return hmac.compare_digest(hashlib.sha256(client_key).digest(), stored)


def server_signature(server_hex, auth):
    return hmac.new(bytes.fromhex(server_hex), auth, hashlib.sha256).hexdigest()


# ------------------------------------------------------------------
# 検査や道具が入るための、小さな端末（画面の scram.js と同じ手順）
# ------------------------------------------------------------------
def _post(url, body, headers=None, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except ValueError:
            return e.code, {}


def login(base, login_id, password, admin=False, headers=None, timeout=30, post=None):
    """入る。(状態の数字, 返事) を返す。通れば返事に token と profile。

    base は "http://127.0.0.1:8932" の形（/api は付けない）。
    post を渡すと、送り方を差し替えられる（post(path, body) → (status, data)）。
    """
    post = post or (lambda path, body: _post(base.rstrip("/") + "/api" + path, body, headers, timeout))
    lid = norm_id(login_id)
    extra = {"admin": True} if admin else {}
    cnonce = secrets.token_urlsafe(18)
    st, d = post("/login/start", dict(extra, id=lid, cnonce=cnonce))
    if st != 200:
        return st, d
    salt, iters, nonce = d.get("salt"), d.get("iters"), d.get("nonce") or ""
    if not HEX32.match(str(salt or "")) or not isinstance(iters, int) or not (ITERS <= iters <= 5000000) \
            or not nonce.startswith(cnonce):
        return 0, {"error": "サーバの返事がおかしい"}
    sp = salted(password, salt, iters)
    auth = auth_message(lid, nonce, salt, iters)
    st, d = post("/login/finish", dict(extra, id=lid, nonce=nonce, proof=client_proof(sp, auth)))
    if st != 200:
        return st, d
    _stored, server = keys_from_salted(sp)
    if not hmac.compare_digest(str(d.get("serverSig") or ""), server_signature(server, auth)):
        return 0, {"error": "サーバを確かめられませんでした"}
    return st, d


if __name__ == "__main__":
    # RFC 6070 の PBKDF2-HMAC-SHA256 の既知の値と、往復の確かめ。
    assert hashlib.pbkdf2_hmac("sha256", b"password", b"salt", 1).hex() == \
        "120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b"
    v = make_verifier("Neko-Yama-Sora-4821", iters=ITERS)
    a = auth_message("we4a01", "abc", v["salt"], v["iters"])
    p = client_proof(salted("nekoyamasora4821", v["salt"]), a)
    assert verify_proof(v["storedKey"], a, p)
    assert not verify_proof(v["storedKey"], a + b"x", p)
    print("scram: OK")
