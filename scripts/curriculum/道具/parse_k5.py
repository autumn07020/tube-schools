# 小5K6K：4倍(2通り)＋2倍(y無し→回数で合わせる)。回数の欠けは順に補う。→ JSON
import sys,os,re,json
sys.path.insert(0,os.path.dirname(__file__)); import bands as B
SP=sys.argv[1]; S3=sys.argv[2]; OUT=os.path.join(SP,"cur","out")
cell=re.compile(r"\[(\d\.\d\d)\]([^\[]+?)(?=\s\s\[|$)")
def norm(s): return re.sub(r"\s+","",s).replace("•","・")
bands={"n":(0.02,0.22),"u":(0.22,0.62),"t":(0.62,0.99)}
for pg in (3,4,5,6,7,8):
    pdf="小5K6Kカリキュラム"; base=os.path.join(SP,"cur","ocr4",pdf,"p%02d"%pg)
    a=B.band_rows(B.lines_of(base+".txt"),bands); b=B.band_rows(B.lines_of(base+".c.txt"),bands)
    for rows in (a,b):
        for r in rows:
            for k in bands:
                if k in r: r[k]=norm(r[k])
    rows=[r for r in B.merge(a,b,bands) if r.get("u") or r.get("n")]
    # 2倍の読み（回数つき）
    two={}
    for l in open(os.path.join(S3,"cur",pdf,"p%02d.txt"%pg),encoding="utf-8"):
        cs=[(float(x),t.strip()) for x,t in cell.findall(l.rstrip("\n"))]
        ns=[t for x,t in cs if 0.53<=x<0.6 and re.fullmatch(r"\d{1,2}",t)]
        us=[t for x,t in cs if 0.62<=x<0.84]; ts=[t for x,t in cs if 0.84<=x]
        if ns and us: two[int(ns[0])]={"u":norm(us[0]),"t":norm(ts[0]) if ts else ""}
    units=[]; expect=1
    for r in rows:
        u=r.get("u",""); n=r.get("n","")
        if "カリキュラム" in u or u.startswith("※") or u in("学習単元",): continue
        m=re.match(r"^(\d{1,2})",n); nn=int(m[1]) if m else None
        if nn is None:
            m2=re.match(r"^(\d{1,2})(.+)$",u)
            if m2 and 1<=int(m2[1])<=40: nn,u=int(m2[1]),m2[2]
        if nn is None: nn=expect
        if nn<expect: continue
        while expect<nn: units.append({"n":expect,"unit":"","test":"","gap":True}); expect+=1
        units.append({"n":nn,"unit":u,"test":r.get("t","")}); expect=nn+1
    for u in units:
        t=two.get(u["n"])
        if t:
            if not u["unit"]: u["unit"]=t["u"]; u["from2x"]=True
            if not u["test"]: u["test"]=t["t"]
    json.dump({"pdf":pdf,"page":pg,"units":units},open(os.path.join(OUT,f"{pdf}-p{pg:02d}.json"),"w"),ensure_ascii=False,indent=0)
    print(f"## p{pg:02d} {len(units)}回; 空:{[u['n'] for u in units if not u['unit']]}; 2倍から:{[u['n'] for u in units if u.get('from2x')]}; ⇄:{sum(1 for u in units if '⇄' in u['unit']+u['test'])}")
    for u in units:
        if u.get("from2x") or not u["unit"]: print("   ",u["n"],u["unit"],"|",u["test"])
