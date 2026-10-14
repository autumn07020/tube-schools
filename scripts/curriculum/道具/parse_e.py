# 予習シリーズ型の「第N回」表を、3通りの読み取り（3倍・3倍補正・2倍）から多数決で起こす。
import re,sys,os,json
cell=re.compile(r"\[(\d\.\d\d)\]([^\[]+?)(?=\s\s\[|$)")
kai=re.compile(r"^第(\d+)回$")
def rows_of(path):
    out=[]
    for l in open(path,encoding="utf-8"):
        l=re.sub(r"^\{[\d.]+\}","",l.rstrip("\n"))
        out.append([(float(x),t.strip()) for x,t in cell.findall(l)])
    return out
def blocks_of(rows):
    blocks=[]
    for r in rows:
        for i,(x,t) in enumerate(r):
            m=kai.match(t)
            if not m: continue
            n=int(m[1])
            cells=[(x2-x,t2) for x2,t2 in r[i+1:] if x< x2 < x+0.42]
            if not blocks or n<=blocks[-1]["rows"][-1][0] or abs(blocks[-1]["x0"]-x)>0.03:
                blocks.append({"x0":x,"rows":[]})
            blocks[-1]["rows"].append((n,cells))
    return [b for b in blocks if len(b["rows"])>=4]
def columns(b, ncol):
    # 列の位置：x の差を ncol 個に丸める（最初の列は dx<0.1）
    xs=sorted(dx for n,c in b["rows"] for dx,t in c)
    cl=[]
    for x in xs:
        if not cl or x-cl[-1][-1]>0.035: cl.append([x])
        else: cl[-1].append(x)
    cents=[sum(c)/len(c) for c in cl]
    return cents
def table(b, cents):
    t={}
    for n,c in b["rows"]:
        row={}
        for dx,s in c:
            k=min(range(len(cents)),key=lambda i:abs(cents[i]-dx))
            row[k]=(row.get(k,"")+s)
        t[n]=row
    return t
def vote(vals):
    vals=[v for v in vals if v]
    if not vals: return ""
    for v in vals:
        if vals.count(v)>=2: return v
    return " ⇄ ".join(dict.fromkeys(vals))
def main(pdf,page):
    global allt
    base=os.path.join(SP,"cur","ocr3",pdf,"p%02d"%page)
    srcs=[base+".txt", base+".c.txt", os.path.join(S3,"cur",pdf,"p%02d.txt"%page)]
    bl=[blocks_of(rows_of(p)) for p in srcs]
    nb=max(len(b) for b in bl)
    allt=[]
    for bi in range(nb):
        bs=[b[bi] for b in bl if bi<len(b)]
        ref=bs[0]; cents=columns(ref,0)
        ncol=len(cents)
        tabs=[table(b,columns(b,0)) for b in bs]
        ns=sorted({n for t in tabs for n in t})
        print(f"## {pdf} p{page:02d} 表{bi+1} 列{ncol} 回{min(ns)}〜{max(ns)} ({len(ns)}行) x0={ref['x0']:.2f}")
        tab={}
        for n in ns:
            cells=[vote([t.get(n,{}).get(k,"") for t in tabs]) for k in range(ncol)]
            print(f"{n:>2}| "+" | ".join(cells)); tab[n]=cells
        allt.append({"ncol":ncol,"x0":ref["x0"],"rows":tab})
    json.dump({"pdf":pdf,"page":page,"tables":allt},open(os.path.join(SP,"cur","out",f"{pdf}-p{page:02d}-e.json"),"w"),ensure_ascii=False)
SP=sys.argv[1]; S3=sys.argv[2]
import os
for spec in sys.argv[3:]:
    pdf,pg=spec.split(":"); main(pdf,int(pg))
