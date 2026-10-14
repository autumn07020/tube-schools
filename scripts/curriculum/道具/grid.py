import re,sys,datetime as dt
cell=re.compile(r"\[(\d\.\d\d)\]([^\[]+?)(?=\s\s\[|$)")
dre=re.compile(r"(\d{1,2})/(\d{1,2})")
rows=[[(float(x),t.strip()) for x,t in cell.findall(l.rstrip("\n"))] for l in open(sys.argv[1],encoding="utf-8")]
xs=sorted(x for r in rows for x,t in r if dre.fullmatch(t))
cols=[]
for x in xs:
    if not cols or x-cols[-1][-1]>0.02: cols.append([x])
    else: cols[-1].append(x)
cols=[sum(c)/len(c) for c in cols]; assert len(cols)==24,len(cols)
def wk(x):
    c=[i for i,cx in enumerate(cols) if cx<=x+0.012]; return c[-1] if c else 0
start=dt.date(2026,8,23); WD="日月火水木金土"
tables=[];cur=None;bad=[]
for r in rows:
    lab=[t for x,t in r if x<0.09 and t in WD]
    if not lab:
        if cur is not None: cur["loose"].append(r)
        continue
    wd=WD.index(lab[0])
    if wd==0 or cur is None: cur={"days":{}, "loose":[]}; tables.append(cur)
    ev={}
    for x,t in r:
        if x<0.09: continue
        parts=t.split()
        for p in parts:
            m=dre.fullmatch(p)
            if m:
                i=wk(x); exp=start+dt.timedelta(days=7*i+wd)
                if (exp.month,exp.day)!=(int(m[1]),int(m[2])): bad.append((lab[0],i,p,exp.strftime("%-m/%-d")))
            else:
                ev.setdefault(wk(x),[]).append(p)
        if not any(dre.fullmatch(p) for p in parts):
            ev.setdefault(wk(x),[]).append(t) if False else None
    cur["days"][wd]=ev
print("date mismatches:",bad)
for ti,tb in enumerate(tables):
    print("=== table",ti, "loose:",[[(x,t) for x,t in r] for r in tb["loose"]])
    for i in range(24):
        d=start+dt.timedelta(days=7*i)
        items=[]
        for wd in range(7):
            e=tb["days"].get(wd,{}).get(i)
            if e: items.append(f"{WD[wd]}:{'/'.join(e)}")
        if items: print(f"{d:%m/%d}", " ".join(items))
