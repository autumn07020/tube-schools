# 中学・K の左半分（授業の目的・教材）を未校正のまま拾う（3倍・補正あり）
import sys,os,re,json
sys.path.insert(0,os.path.dirname(__file__)); import bands as B
SP=sys.argv[1]; OUT=os.path.join(SP,"cur","out")
def grab(pdf,pg):
    lines=B.lines_of(os.path.join(SP,"cur","ocr3",pdf,"p%02d.c.txt"%pg))
    left=[]
    for y,cs in lines:
        t="".join(t for x,t in sorted(cs) if x<0.5)
        if t: left.append((y,t))
    head=" ".join(t for y,t in left[:3])[:60]
    sec={}; cur=None
    for y,t in left:
        m=re.match(r"^【(.+?)】(.*)$",t)
        if m: cur=m[1]; sec[cur]=[m[2]] if m[2] else []; continue
        if cur: sec[cur].append(t)
    out={k:"".join(v) for k,v in sec.items()}
    json.dump({"pdf":pdf,"page":pg,"head":head,"sections":out},open(os.path.join(OUT,f"{pdf}-p{pg:02d}-prose.json"),"w"),ensure_ascii=False)
    print(f"{pdf} p{pg:02d} {head[:28]!r} 節:{[(k,len(v)) for k,v in out.items()]}")
for spec in sys.argv[2:]:
    pdf,pg=spec.split(":"); grab(pdf,int(pg))
