#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""番人：Claude のセッションが「絶対ダメ」を踏まないよう、道具を使う前に止める（.claude/settings.json の PreToolUse）。
文章の決まりを仕組みにする（knowledge/20-決まり/権限の線.md）：
  本番への SSH・scp・rsync／scripts/accounts/make.py／合言葉の表.nosync／../myenglish への変更／
  本番を変える deploy/*.sh の実行（読むのは通す）／~/myAcady/demo-accounts.json と deploy/accounts/ への書き込み／
  合言葉の表を読む道具（Read・Grep・Glob）。
標準入力の JSON（tool_name・tool_input）を読み、止めるときだけ permissionDecision: deny を出す。通すときは何も出さない。
手で確かめる：  echo '{"tool_name":"Bash","tool_input":{"command":"sh deploy/更新.sh"}}' | python3 .claude/hooks/guard.py"""
import json, re, sys

PROD = ("18.130.10.188", "tube-study.uk", "ubuntu@", "lightsail.pem")
REMOTE = re.compile(r"(^|[\s;&|(`])(ssh|scp|sftp|rsync)\b")
RUN_WITH_SH = re.compile(r"(^|[\s;&|(`])(sh|bash|zsh|source|\.)\s+(\S*/)?deploy/[^\s]+\.sh")      # sh deploy/更新.sh
RUN_DIRECT = re.compile(r"(^|[;&|(`]\s*)\.?/?(\S*/)?deploy/[^\s]+\.sh(\s|$)")                    # ./deploy/更新.sh
# 命令の位置（行の頭・; && || | ( ` $( のあと、sudo を挟んでも）に ssh・scp・sftp があるとき
CMD_SSH = re.compile(r"(^|[;&|(`]|\$\()\s*(sudo\s+)?(ssh|scp|sftp)\b")
READ_ONLY = re.compile(r"^\s*(cat|less|more|ls|grep|rg|head|tail|find|wc|diff|cmp|stat|file|du|open|git\s+(log|show|diff|status|blame))\b")

def deny(why):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": why}}, ensure_ascii=False))
    sys.exit(0)

def main():
    try:
        d = json.load(sys.stdin)
    except Exception:
        return
    tool = d.get("tool_name") or ""
    inp = d.get("tool_input") or {}
    if tool == "Bash":
        c = inp.get("command") or ""
        if REMOTE.search(c) and any(p in c for p in PROD):
            deny("本番サーバへの SSH・scp・rsync は絶対にしない（本番は読むだけ）。反映は本人が deploy/更新.sh を流す")
        if CMD_SSH.search(c):   # 命令として流すときだけ（grep ssh のような読むだけの命令は通す）
            deny("この仕事で Claude が SSH を使う場面は無い（本番は読むだけ・反映は本人）")
        if "accounts/make.py" in c and not READ_ONLY.match(c):   # 読むのは通す。流すのは止める
            deny("scripts/accounts/make.py は二度と流さない（表とサーバが食い違う）")
        if "合言葉の表" in c:
            deny("合言葉の表.nosync は読まない・送らない・写さない")
        if RUN_WITH_SH.search(c) or RUN_DIRECT.search(c):
            deny("deploy/ のスクリプトは本人が流す。Claude は命令文を渡すだけ")
        if "myenglish" in c and not READ_ONLY.match(c):
            deny("../myenglish/ は変更しない（読むだけなら cat・grep などで）")
        if "myAcady/demo-accounts.json" in c and not READ_ONLY.match(c):
            deny("~/myAcady/demo-accounts.json は読むだけ（書かない・写さない）")
        return
    p = str(inp.get("file_path") or inp.get("path") or inp.get("notebook_path") or "")
    pat = str(inp.get("pattern") or inp.get("glob") or "")
    if tool in ("Read", "Grep", "Glob"):   # 読む道具：合言葉の表だけを止める（ほかは通す）
        if "合言葉の表" in p or "合言葉の表" in pat:
            deny("合言葉の表.nosync は読まない・送らない・写さない")
        return
    if not p:
        return
    if "合言葉の表" in p:
        deny("合言葉の表.nosync には書かない")
    if "/myenglish/" in p or p.startswith("../myenglish"):
        deny("../myenglish/ は変更しない")
    if "myAcady/demo-accounts.json" in p:
        deny("~/myAcady/demo-accounts.json は読むだけ")
    if "/deploy/accounts/" in p or p.startswith("deploy/accounts/"):
        deny("本物の束（deploy/accounts/）は書き換えない")

if __name__ == "__main__":
    main()
