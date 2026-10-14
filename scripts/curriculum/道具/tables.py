# 予習シリーズ型（小4・小5・小6）の「第N回」表を OCR 行から抜く。
# 使い方: tables.py <pNN.txt> ...  → ブロックごとに 回・列(x)・文字 を出す
import re,sys
cell=re.compile(r"\[(\d\.\d\d)\]([^\[]+?)(?=\s\s\[|$)")
kai=re.compile(r"^第(\d+)回$")
for path in sys.argv[1:]:
    rows=[[(float(x),t.strip()) for x,t in cell.findall(l.rstrip("\n"))] for l in open(path,encoding="utf-8")]
    blocks=[]   # [{x0, rows:[(n,[(dx,text)])]}]
    for r in rows:
        for i,(x,t) in enumerate(r):
            m=kai.match(t)
            if not m: continue
            n=int(m[1])
            cells=[(round(x2-x,2),t2) for x2,t2 in r[i+1:] if x< x2 < x+0.42]
            if not blocks or n<=blocks[-1]["rows"][-1][0] or abs(blocks[-1]["x0"]-x)>0.03:
                blocks.append({"x0":x,"rows":[]})
            blocks[-1]["rows"].append((n,cells))
    # 1〜2行の孤立ブロック（右ページの見出し「第N回」）は捨てる
    for b in blocks:
        if len(b["rows"])<4: continue
        xs=sorted({dx for n,c in b["rows"] for dx,t in c})
        print(f"## {path.split('/')[-2]}/{path.split('/')[-1]} x0={b['x0']:.2f} rows={len(b['rows'])} dx={xs}")
        for n,c in b["rows"]:
            print(f"{n:>2} "+"  ".join(f"{dx}:{t}" for dx,t in c))
