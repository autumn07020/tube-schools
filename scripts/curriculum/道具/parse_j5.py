# 中学の【カリキュラム】表 → JSON。列は x の山から決める。4倍(補正なし/あり)＋3倍全頁を y で突き合わせて多数決。
# 期のブロックは、期の見出しの y と各ブロックの中心 y が合うように DP で切る。
import sys,os,re,json
sys.path.insert(0,os.path.dirname(__file__)); import bands as B
SP=sys.argv[1]; OUT=os.path.join(SP,"cur","out"); os.makedirs(OUT,exist_ok=True)
CIRC={chr(0x2460+i):i+1 for i in range(20)}
def norm(s):
    s=re.sub(r"\s+","",s); s=s.replace("〜","～").replace("~","～").replace("•","・").replace("．",".").replace("，","、").replace("•","・")
    return s
def peaks(lines):
    h={}
    for y,cs in lines:
        for x,t in cs: h[round(x*40)/40]=h.get(round(x*40)/40,0)+1
    ps=[]
    for x in sorted(h):
        if h[x]>=6:
            if ps and x-ps[-1][-1]<=0.051: ps[-1].append(x)
            else: ps.append([x])
    return [min(p) for p in ps]
def mkbands(ps):
    right=[p for p in ps if p>=0.40]
    t_edge=(right[0]-0.02) if right else 0.99
    p_edge=next((p-0.02 for p in right if p>=t_edge+0.09),None)
    b={"ki":(0.0,0.135),"n":(0.135,0.205),"u":(0.205,t_edge)}
    if right: b["t"]=(t_edge,p_edge if p_edge else 0.995)
    if p_edge: b["p"]=(p_edge,0.995)
    return b
def numof(s):
    s=s.strip()
    m=re.match(r"^[（(]?([①-⑳]|\d{1,2})[）)]?",s)
    if not m: return None,s
    v=m[1]; n=CIRC.get(v) or int(v); return n,s[m.end():]
def vote(vals):
    vals=[v for v in vals if v]
    if not vals: return ""
    for v in vals:
        if vals.count(v)>=2: return v
    return " ⇄ ".join(dict.fromkeys(vals))
def merge3(a,b,c,bands,tol=0.007):
    rows=[]
    def near(rs,y): 
        j=min(range(len(rs)),key=lambda i:abs(rs[i]["y"]-y),default=None)
        return rs[j] if j is not None and abs(rs[j]["y"]-y)<tol else {}
    for r in a:
        rb,rc=near(b,r["y"]),near(c,r["y"])
        m={"y":r["y"]}
        for k in bands: m[k]=vote([r.get(k,""),rb.get(k,""),rc.get(k,"")])
        rows.append(m)
    return rows
LABELS=[("準備講座",("準備講座","中1","アドバンス","レギュラー","クラス")),("3月",("3月",)),("春期講習会",("春期",)),("1学期",("1学期","1字期")),("夏期講習会",("夏期",)),("2学期",("2学期",)),("冬期講習会",("冬期",)),("3学期",("3学期","3字期"))]
def labels_of(rows):
    found={}
    pend=None
    for r in rows:
        k=r.get("ki","")
        if not k or k.startswith("※") or r["y"]>0.9: continue
        for name,keys in LABELS:
            if any(x in k for x in keys):
                found.setdefault(name,[]).append(r["y"]); pend=name; break
        else:
            if "講習会" in k and pend and pend.endswith("講習会"): found[pend].append(r["y"])
    order=[n for n,_ in LABELS if n in found]
    return [(n,sum(found[n])/len(found[n])) for n in order]
FIXED={"準備講座":6,"1学期":11,"2学期":12,"3学期":6}
def split_blocks(units,labels,fixed=None):
    fixed=dict(FIXED,**(fixed or {}))
    names=[n for n,_ in labels]
    if not names: return [("?",units)]
    N=len(units); var=[n for n in names if n not in fixed]
    rest=N-sum(fixed[n] for n in names if n in fixed)
    if rest<len(var): return [("?",units)]
    import itertools
    best=None
    rng=range(1,rest+1) if var else [()]
    for combo in (itertools.product(rng,repeat=len(var)) if var else [()]):
        if var and sum(combo)!=rest: continue
        sizes=[]; vi=0
        for n in names:
            if n in fixed: sizes.append(fixed[n])
            else: sizes.append(combo[vi]); vi+=1
        score=0; i=0
        for n,sz in zip(names,sizes):
            for k in range(sz):
                on=units[i+k].get("n")
                if on==k+1: score+=1
                elif on is not None and on!=k+1: score-=1
            i+=sz
        if best is None or score>best[0]: best=(score,sizes)
    sizes=best[1]; out=[]; i=0
    for n,sz in zip(names,sizes): out.append((n,units[i:i+sz])); i+=sz
    return out
FIX={("中3カリキュラム",7):{"2学期":24,"3学期":11}}
INSERT={("中2カリキュラム",5):[("命令文",  "？（春期講習会②・読めず）")]}
def page(pdf,pg):
    base4=os.path.join(SP,"cur","ocr4",pdf,"p%02d"%pg); base3=os.path.join(SP,"cur","ocr3",pdf,"p%02d"%pg)
    la=B.lines_of(base4+".txt"); lb=B.lines_of(base4+".c.txt")
    lc=[((y-0.08)/0.90,[((x-0.5)/0.5,t) for x,t in cs if x>=0.5]) for y,cs in B.lines_of(base3+".txt")]
    bands=mkbands(peaks(la))
    def rows(lines):
        rs=B.band_rows(lines,bands)
        for r in rs:
            for k in bands:
                if k in r: r[k]=norm(r[k])
        return rs
    rows_=merge3(rows(la),rows(lb),rows(lc),bands)
    units=[]
    for r in rows_:
        if r["y"]<0.03: continue
        u=r.get("u",""); n,rest=numof(r.get("n",""))
        if n is None:
            mk=re.search(r"([①-⑳]|\d{1,2})[）)]?$",r.get("ki",""))
            if mk: n=CIRC.get(mk[1]) or int(mk[1])
        if n is None and u: n2,rest2=numof(u); 
        else: n2=None
        if n is None and n2 is not None and rest2: n,u=n2,rest2
        elif rest: u=rest+u
        if not u and not r.get("t") and not r.get("p"): continue
        if re.match(r"^[学宇字][習沓資番賀][单単]元|^：?学習単元|^テスト$|^復習課題|^予習課題|^\d{1,2}$",u) or "カリキュラムは予定" in u or "講習会を実施" in u: continue
        if not u: continue
        h=len(u)//2
        if len(u)%2==0 and u[:h]==u[h:]: u=u[:h]
        units.append({"y":round(r["y"],3),"n":n,"unit":u,"test":r.get("t",""),"prep":r.get("p","")})
    units=[u for u in units if not re.fullmatch(r"[①-⑳\d（）()｜|.．]+|[A-Za-z]",u["unit"])]
    dd=[]
    for u in units:
        if dd and abs(u["y"]-dd[-1]["y"])<0.012 and re.sub(r"[⇄ ）)]","",u["unit"])==re.sub(r"[⇄ ）)]","",dd[-1]["unit"]): continue
        dd.append(u)
    units=dd
    for after,ins in INSERT.get((pdf,pg),[]):
        k=next((i for i,u in enumerate(units) if u["unit"].startswith(after)),None)
        if k is not None: units.insert(k+1,{"y":units[k]["y"]+0.001,"n":None,"unit":ins,"test":"","prep":""})
    if (pdf,pg)==("中1カリキュラム",4):
        merged=[]
        for u in units:
            t=u["unit"]
            if t.startswith("R") and merged and merged[-1]["unit"].startswith("A"):
                merged[-1]["unit"]=merged[-1]["unit"]+"｜"+t; merged[-1]["n"]=merged[-1]["n"] or u["n"]
                if not merged[-1]["test"]: merged[-1]["test"]=u["test"]
                continue
            merged.append(u)
        units=merged
    labels=labels_of(rows_)
    fixed=FIX.get((pdf,pg))
    blocks=split_blocks(units,labels,fixed)
    out=[]
    for name,us in blocks:
        for i,u in enumerate(us):
            out.append({"term":name,"n":i+1,"ocr_n":u["n"],"unit":u["unit"],"test":u["test"],"prep":u["prep"]})
    junk=[u["unit"][:30] for u in units if len(u["unit"])<3 or re.search(r"^[（(）)｜|]+$",u["unit"])]
    if junk: print("  ごみ候補:",junk)
    json.dump({"pdf":pdf,"page":pg,"bands":bands,"labels":labels,"units":out},open(os.path.join(OUT,f"{pdf}-p{pg:02d}.json"),"w"),ensure_ascii=False,indent=0)
    print(f"## {pdf} p{pg:02d} bands={ {k:(round(a,2),round(b,2)) for k,(a,b) in bands.items()} }")
    for name,us in blocks:
        bad=sum(1 for i,u in enumerate(us) if u["n"] not in (None,i+1))
        print(f"  {name:<6}{len(us):>3}回  {us[0]['unit'][:22]} … {us[-1]['unit'][:22]}  番号不一致{bad}")
for spec in sys.argv[2:]:
    pdf,pg=spec.split(":"); page(pdf,int(pg))
