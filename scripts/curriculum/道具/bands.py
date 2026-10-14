# 帯（x の範囲）で列を切る表の読み取り。3倍の読み取り（補正なし／あり）を y で突き合わせる。
import re,os
cell=re.compile(r"\[(\d\.\d\d)\]([^\[]+?)(?=\s\s\[|$)")
CIRC={chr(0x2460+i):i+1 for i in range(20)}
def lines_of(path):
    out=[]
    for l in open(path,encoding="utf-8"):
        m=re.match(r"^\{([\d.]+)\}(.*)$",l.rstrip("\n"))
        if not m: continue
        out.append((float(m[1]),[(float(x),t.strip()) for x,t in cell.findall(m[2])]))
    return out
def band_rows(lines,bands,ylo=0,yhi=1):
    rows=[]
    for y,cs in lines:
        if not (ylo<=y<=yhi): continue
        r={"y":y}
        for name,(lo,hi) in bands.items():
            txt=" ".join(t for x,t in cs if lo<=x<hi)
            if txt: r[name]=txt
        if len(r)>1: rows.append(r)
    return rows
def merge(a,b,bands,tol=0.007):
    """a を基準に b を y で突き合わせ、違う所は 'A ⇄ B'。b にしか無い行は足す。"""
    out=[];used=set()
    for r in a:
        j=min(range(len(b)),key=lambda i:abs(b[i]["y"]-r["y"]),default=None)
        m=dict(r)
        if j is not None and abs(b[j]["y"]-r["y"])<tol and j not in used:
            used.add(j)
            for k in bands:
                va,vb=r.get(k,""),b[j].get(k,"")
                if va!=vb: m[k]=va if not vb else (vb if not va else f"{va} ⇄ {vb}")
        out.append(m)
    for i,r in enumerate(b):
        if i not in used: out.append(dict(r,only="corr"))
    out.sort(key=lambda r:r["y"]); return out
def read(sp,pdf,page,bands,ylo=0,yhi=1):
    base=os.path.join(sp,"cur","ocr3",pdf,"p%02d"%page)
    a=band_rows(lines_of(base+".txt"),bands,ylo,yhi); b=band_rows(lines_of(base+".c.txt"),bands,ylo,yhi)
    return merge(a,b,bands)
def num(s):
    """回の番号：①〜⑳・数字。読めなければ None。"""
    s=s.strip()
    if s in CIRC: return CIRC[s]
    m=re.match(r"^(\d{1,2})$",s)
    return int(m[1]) if m else None
