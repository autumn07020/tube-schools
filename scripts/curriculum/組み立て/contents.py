# 小4・小5・小6前期の各回の「学習内容」（■の見出し）を、詳しいページから取り出す。
# ●（単元）は校正済みの単元名と突き合わせて、どの教科のどの回かを確かめる（合わないものは捨てて数える）。
import difflib, json, os, re, sys
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import elem as E
from clean import clean
RD=os.path.join(HERE,"..","読み取り")
cell=re.compile(r"\[(\d\.\d\d)\]([^\[]+?)(?=\s\s\[|$)")
PAGES={ # (学年, 期): [(pdf, 頁, 半分 None/"L"/"R", ファイル)]
 ("e4","first"):[("小4カリキュラム",3,"R","3倍"),("小4カリキュラム",4,None,"3倍y"),("小4カリキュラム",5,None,"3倍y"),("小4カリキュラム",6,None,"3倍y"),("小4カリキュラム",7,"L","3倍")],
 ("e4","second"):[("小4カリキュラム",p,None,"3倍y") for p in (8,9,10,11)],
 ("e5","first"):[("小5カリキュラム",p,None,"3倍y") for p in (6,7,8,9)],
 ("e5","second"):[("小5カリキュラム",10,"R","3倍")]+[("小5カリキュラム",p,None,"3倍y") for p in (11,12,13,14)],
 ("e6","first"):[("小6カリキュラム",p,None,"3倍y") for p in (6,7,8,9)],
}
TERMPAGE={("e4","first"):("小4カリキュラム",3),("e4","second"):("小4カリキュラム",7),("e5","first"):("小5カリキュラム",5),("e5","second"):("小5カリキュラム",10),("e6","first"):("小6カリキュラム",5)}
def lines(f):
    out=[]
    for l in open(f,encoding="utf-8"):
        m=re.match(r"^\{([\d.]+)\}(.*)$",l.rstrip("\n"))
        if m: out.append((float(m[1]),[(float(x),t.strip()) for x,t in cell.findall(m[2])]))
    return out
def norm(s): return re.sub(r"[\s・／/（）()〈〉【】～〜\-ー－―]","",s)
def units_of(g,term):
    pdf,pg=TERMPAGE[(g,term)]; out={}
    for ti in (0,1):
        for subj,us in E.table(pdf,pg,ti).items():
            for u in us:
                if u.get("review"): continue
                out.setdefault(u["n"],[]).append((subj,u["unit"]))
                if subj=="japanese" and u.get("words"): out[u["n"]].append(("words",u["words"]))
    return out
def extract(g,term):
    known=units_of(g,term); res={}; bad=[]; cells_total=0
    for pdf,pg,half,kind in PAGES[(g,term)]:
        f=os.path.join(RD,kind,pdf,f"p{pg:02d}"+(".c.txt" if kind=="3倍" else ".txt"))
        L=lines(f)
        heads=[]; units=[]; bullets=[]
        for y,cs in L:
            for x,t in cs:
                h="L" if x<0.5 else "R"
                if half and h!=half: continue
                m=re.match(r"^第\s*(\d+)\s*回$",t)
                if m: heads.append((h,y,int(m[1]))); continue
                m=re.match(r"^[●◆•・]\s*(.+)$",t)
                if m and len(m[1])>=2: units.append({"h":h,"x":x,"y":y,"t":m[1]}); continue
                m=re.match(r"^(?:\d[）)])?\s*■\s*(.+)$",t)
                if m: bullets.append({"h":h,"x":x,"y":y,"t":m[1]}); continue
                # ●が読み取りで落ちた単元名（色の帯の上）。あとで回の単元名とよく合うものだけ使う
                tt=re.sub(r"^[※1Il|・\s]+","",t)
                if 3<=len(tt)<=40 and "。" not in tt: units.append({"h":h,"x":x,"y":y,"t":tt,"loose":True})
        def kai(h,y):
            c=[n for hh,yy,n in heads if hh==h and yy<=y+0.002]
            return max(((yy,n) for hh,yy,n in heads if hh==h and yy<=y+0.002),default=(0,None))[1]
        for u in units:
            n=kai(u["h"],u["y"]); u["n"]=n
            cand=known.get(n,[]); best=(0,None)
            for subj,name in cand:
                r=difflib.SequenceMatcher(None,norm(u["t"]),norm(name)).ratio()
                if r>best[0]: best=(r,(subj,name))
            u["match"]=best[1] if best[0]>=(0.75 if u.get("loose") else 0.6) else None
            if not u["match"] and not u.get("loose"): bad.append((pdf,pg,n,u["t"][:24],round(best[0],2)))
        units=[u for u in units if u.get("match") or not u.get("loose")]
        for b in bullets:
            n=kai(b["h"],b["y"])
            near=[u for u in units if u["n"]==n and u["h"]==b["h"] and u["y"]<=b["y"]+0.002 and u["x"]-0.03<=b["x"]<=u["x"]+0.14]
            if not near: continue
            u=max(near,key=lambda u:(u["y"],u["x"]))
            if u.get("match"):
                subj,name=u["match"]; res.setdefault((n,subj),[]).append(clean(b["t"]).strip("。"))
    miss=[(n,s) for n,lst in known.items() for s,_ in lst if (n,s) not in res]
    return res,bad,miss
if __name__=="__main__":
    for key in PAGES:
        res,bad,miss=extract(*key)
        print(key,"取れた",len(res),"合わない●",len(bad),"抜け",len(miss))
        for b in bad[:6]: print("   ●?",b)
        print("   抜け",miss[:12])
