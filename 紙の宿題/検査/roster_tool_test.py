#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""先生の手元の対応表（roster-tool/対応表.html）の「5. クラス替え」を、Chrome で動かして確かめる。
通信をしない道具なので、ファイルをそのまま開く。

  ・id,classId,seat を貼ると、ID で生徒を探してクラスと番号だけを書き換える（氏名・あいことばはそのまま）
  ・fromClass,fromSeat,classId,seat でも指せる。入れ替え（同じ貼り付けの中）は通る
  ・同じ席に2人になるなら、何も書き換えない。氏名の列があれば拒む。無いクラスは拒む
  ・「いまの書き換えを取り消す」で元に戻る

    python3 紙の宿題/検査/roster_tool_test.py
"""
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(HERE, "作業.nosync")
os.makedirs(os.path.join(W, "tmp"), exist_ok=True)
os.environ["TMPDIR"] = os.path.join(W, "tmp")
sys.path.insert(0, HERE)
from cdp import Chrome  # noqa: E402

TOOL = os.path.abspath(os.path.join(HERE, "..", "..", "roster-tool", "対応表.html"))
ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   %s" % name)
    else:
        ng_n += 1
        print("  ×    %s  %s" % (name, detail))


ROWS = "rows.map(function(r){ return [r.id, r.classId, r.seat, r.name || '', (r.moves || []).length]; })"


def main():
    with Chrome(width=1100, height=900, scale=1) as c:
        c.goto("file://" + urllib.parse.quote(TOOL), wait=1.0)
        c.eval("window.__alerts = []; window.alert = function(m){ window.__alerts.push(String(m)); };")
        c.eval("document.getElementById('fPaste').value = 'id,password,classId,seat\\nle4a01,p1,e4a,01\\nle4a02,p2,e4a,02\\nle4b01,p3,e4b,01\\nle4b02,p4,e4b,02';"
               "document.getElementById('bPaste').click();")
        c.eval("rows[1].name = '山田 花子';")
        check("4人が入った", c.eval("rows.length") == 4)
        c.eval("document.getElementById('fMove').value = 'id,classId,seat\\nle4a02,e4b,01\\nle4b01,e4a,02'; document.getElementById('bMove').click();")
        r = c.eval(ROWS)
        check("入れ替え（同じ貼り付けの中）：α-02 と β-01", r[1][1:3] == ["e4b", "01"] and r[2][1:3] == ["e4a", "02"], r)
        check("氏名はそのまま・前の席を残す", r[1][3] == "山田 花子" and r[1][4] == 1, r)
        check("「取り消す」が出る", c.eval("!document.getElementById('bMoveUndo').hidden"))
        c.eval("document.getElementById('bMoveUndo').click()")
        r = c.eval(ROWS)
        check("取り消すと元に戻る", r[1][1:3] == ["e4a", "02"] and r[2][1:3] == ["e4b", "01"] and r[1][4] == 0, r)
        c.eval("document.getElementById('fMove').value = 'fromClass,fromSeat,classId,seat\\ne4a,01,e4b,05'; document.getElementById('bMove').click();")
        r = c.eval(ROWS)
        check("今の席（fromClass,fromSeat）でも指せる", r[0][1:3] == ["e4b", "05"], r)
        n0 = len(c.eval("window.__alerts"))
        c.eval("document.getElementById('fMove').value = 'id,classId,seat\\nle4a02,e4b,02'; document.getElementById('bMove').click();")
        r = c.eval(ROWS)
        al = c.eval("window.__alerts")
        check("同じ席に2人になるなら書き換えない（知らせる）", r[1][1:3] == ["e4a", "02"] and len(al) == n0 + 1 and "同じ席" in al[-1], (r, al[-1:]))
        c.eval("document.getElementById('fMove').value = 'id,氏名,classId,seat\\nle4a02,山田,e4b,09'; document.getElementById('bMove').click();")
        al = c.eval("window.__alerts")
        check("氏名の列を拒む", "氏名の列" in al[-1] and c.eval(ROWS)[1][1:3] == ["e4a", "02"], al[-1:])
        c.eval("document.getElementById('fMove').value = 'id,classId,seat\\nle4a02,zz9,09'; document.getElementById('bMove').click();")
        al = c.eval("window.__alerts")
        check("無いクラスは拒む", "ありません" in al[-1] and c.eval(ROWS)[1][1:3] == ["e4a", "02"], al[-1:])
        c.eval("document.getElementById('fMove').value = 'id,classId,seat\\nnobody,e4a,07'; document.getElementById('bMove').click();")
        check("名簿に無い行は、見つからないと言う", "見つからない" in c.eval("document.getElementById('moveSum').textContent"))
        check("通信をしない（fetch・XMLHttpRequest を使っていない）",
              "fetch(" not in open(TOOL, encoding="utf-8").read() and "XMLHttpRequest" not in open(TOOL, encoding="utf-8").read().split("<script>")[1].replace("fetch も XMLHttpRequest も使わない", ""))
    print("\n%s。（%d件）" % ("すべて通った" if not ng_n else "× %d件" % ng_n, ok_n + ng_n))
    return 1 if ng_n else 0


if __name__ == "__main__":
    sys.exit(main())
