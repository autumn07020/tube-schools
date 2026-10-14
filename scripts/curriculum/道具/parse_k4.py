# 小5K6K の【カリキュラム】表（回数｜学習単元｜確認テスト）右半分4倍
import sys,os,re
sys.path.insert(0,os.path.dirname(__file__)); import bands as B
SP=sys.argv[1]
def norm(s): return re.sub(r"\s+","",s).replace("•","・")
bands={"n":(0.02,0.22),"u":(0.22,0.62),"t":(0.62,0.99)}
for spec in sys.argv[2:]:
    pdf,pg=spec.split(":"); pg=int(pg)
    base=os.path.join(SP,"cur","ocr4",pdf,"p%02d"%pg)
    a=B.band_rows(B.lines_of(base+".txt"),bands); b=B.band_rows(B.lines_of(base+".c.txt"),bands)
    for rows in (a,b):
        for r in rows:
            for k in bands:
                if k in r: r[k]=norm(r[k])
    rows=B.merge(a,b,bands)
    print(f"## {pdf} p{pg:02d}")
    i=0
    for r in rows:
        if not (r.get("u") or r.get("n")): continue
        print(f"{r.get('n',''):>3}|{r.get('u','')}|{r.get('t','')}"[:110])
