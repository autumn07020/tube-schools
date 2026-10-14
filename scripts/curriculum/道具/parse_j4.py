# 中学の【カリキュラム】表（右半分を4倍で読んだもの）。帯: 期(0.02-0.14) 回(0.14-0.225) 単元(0.225-0.54) テスト(0.54-0.99)
import sys,os,re
sys.path.insert(0,os.path.dirname(__file__)); import bands as B
SP=sys.argv[1]
def norm(s):
    s=re.sub(r"\s+","",s); s=s.replace("〜","～").replace("~","～").replace("•","・").replace("．",".").replace("，","、")
    return s
def read(pdf,pg,bands):
    base=os.path.join(SP,"cur","ocr4",pdf,"p%02d"%pg)
    a=B.band_rows(B.lines_of(base+".txt"),bands); b=B.band_rows(B.lines_of(base+".c.txt"),bands)
    for rows in (a,b):
        for r in rows:
            for k in bands:
                if k in r: r[k]=norm(r[k])
    return B.merge(a,b,bands)
bands={"ki":(0.02,0.14),"n":(0.14,0.225),"u":(0.225,0.54),"t":(0.54,0.99)}
for spec in sys.argv[2:]:
    pdf,pg=spec.split(":"); pg=int(pg)
    rows=read(pdf,pg,bands)
    print(f"## {pdf} p{pg:02d}")
    for r in rows:
        if r["y"]<0.03: continue
        if not (r.get("u") or r.get("ki") or r.get("n")): continue
        n=r.get("n","")
        # 回の番号が単元に食い込んだとき
        u=r.get("u","")
        m=re.match(r"^([①-⑳]|\d{1,2})(.*)$",n)
        if m and m[2]: n,u=m[1],m[2]+u
        ki=("【"+r["ki"]+"】") if r.get("ki") else ""
        print(f"{ki}{n:>2}|{u}|{r.get('t','')}"[:150])
