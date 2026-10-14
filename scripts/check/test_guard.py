#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""番人（.claude/hooks/guard.py）が、止めるべきものを止め、読むだけのものを通すことを確かめる。
.claude/settings.json に書いた命令文そのもので流す（hook が実際に呼ばれる形と同じ）。

    python3 scripts/check/test_guard.py     # 0 なら通った

2026-10-14：最初の番人は「ssh」という字を含むだけで止め、grep ssh のような読むだけの命令まで止めていた。"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CASES = [
    ("allow", "Bash", {"command": "ls -la"}),
    ("allow", "Bash", {"command": "cat deploy/更新.sh | head"}),
    ("allow", "Bash", {"command": "curl -s https://tube-study.uk/api/health"}),
    ("allow", "Bash", {"command": "cat ~/myAcady/demo-accounts.json"}),
    ("allow", "Bash", {"command": "grep -n ssh deploy/更新.sh"}),
    ("allow", "Bash", {"command": "grep -rn 'scp ' deploy"}),
    ("allow", "Bash", {"command": "cat scripts/accounts/make.py | head"}),
    ("allow", "Bash", {"command": "git log --oneline -- scripts/accounts/make.py"}),
    ("allow", "Bash", {"command": "python3 server/test_trial.py"}),
    ("deny", "Bash", {"command": "ssh -i ~/.ssh/lightsail.pem ubuntu@18.130.10.188 ls"}),
    ("deny", "Bash", {"command": "cd x && ssh host"}),
    ("deny", "Bash", {"command": "echo $(ssh host date)"}),
    ("deny", "Bash", {"command": "sudo ssh host"}),
    ("deny", "Bash", {"command": "scp a host:/tmp"}),
    ("deny", "Bash", {"command": "rsync -a app/ ubuntu@18.130.10.188:/opt/myacady/"}),
    ("deny", "Bash", {"command": "sh deploy/更新.sh"}),
    ("deny", "Bash", {"command": "DEMO=0 sh deploy/更新.sh"}),
    ("deny", "Bash", {"command": "cd x && sh deploy/ためしのデモ.sh"}),
    ("deny", "Bash", {"command": "./deploy/本番切替.sh"}),
    ("deny", "Bash", {"command": "python3 scripts/accounts/make.py"}),
    ("deny", "Bash", {"command": "cd /x && python3 scripts/accounts/make.py --school w"}),
    ("deny", "Bash", {"command": "cat 合言葉の表.nosync/a.xlsx"}),
    ("deny", "Bash", {"command": "echo hi > ../myenglish/x.txt"}),
    ("deny", "Bash", {"command": "cp a ~/myAcady/demo-accounts.json"}),
    ("deny", "Bash", {"command": "git push origin main"}),
    ("deny", "Bash", {"command": "cd x && git push origin HEAD:main"}),
    ("deny", "Bash", {"command": "git push -f origin code/fix-1"}),
    ("deny", "Bash", {"command": "git push --force-with-lease origin code/fix-1"}),
    ("allow", "Bash", {"command": "git push -u origin code/fix-1"}),
    ("allow", "Bash", {"command": "git log --oneline -5"}),
    ("allow", "Bash", {"command": "grep -n 'git push' docs/体制の始め方.md"}),
    ("allow", "Write", {"file_path": "/Users/aki/Projects/tube-schools/knowledge/INDEX.md"}),
    ("deny", "Write", {"file_path": "/x/tube-schools/合言葉の表.nosync/a.xlsx"}),
    ("deny", "Edit", {"file_path": "/x/CloudDocs/myenglish/a.md"}),
    ("deny", "Write", {"file_path": "/Users/aki/Projects/tube-schools/deploy/accounts/w.bundle.json"}),
    ("allow", "Read", {"file_path": "/Users/aki/Projects/tube-schools/server/paths.py"}),
    ("allow", "Read", {"file_path": "/Users/aki/myAcady/demo-accounts.json"}),
    ("deny", "Read", {"file_path": "/x/tube-schools/合言葉の表.nosync/t.xlsx"}),
    ("deny", "Grep", {"pattern": "s-0", "path": "/x/合言葉の表.nosync"}),
    ("deny", "Glob", {"pattern": "合言葉の表*/**"}),
    ("allow", "Glob", {"pattern": "server/*.py"}),
]

def main():
    st = json.load(open(os.path.join(ROOT, ".claude", "settings.json"), encoding="utf-8"))
    cmds = {h["matcher"]: h["hooks"][0]["command"] for h in st["hooks"]["PreToolUse"]}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=ROOT)
    bad = 0
    for want, tool, ti in CASES:
        m = next(k for k in cmds if tool in k.split("|"))
        out = subprocess.run(["bash", "-c", cmds[m]], input=json.dumps({"tool_name": tool, "tool_input": ti}),
                             capture_output=True, text=True, env=env, cwd=ROOT).stdout
        got = "deny" if '"deny"' in out else "allow"
        if got != want:
            bad += 1; print("×  %s を %s にすべきところ %s：%s" % (tool, want, got, ti))
    print("番人の検査：%s（%d 例）" % ("× %d 件" % bad if bad else "すべて通った", len(CASES)))
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
