# 小6 後期：社会・理科（p15-18 月｜授業回数｜予習シリーズ回｜学習内容｜確認テスト2列）と 国語・算数（p11-14 週別）
import sys,os
sys.path.insert(0,os.path.dirname(__file__)); import bands as B
SP=sys.argv[1]
import json
def show(pdf,pg,bands,cols,ylo,yhi):
    rows=B.read(SP,pdf,pg,bands,ylo,yhi)
    json.dump({"pdf":pdf,"page":pg,"rows":[{k:v for k,v in r.items() if k!="only"} for r in rows]},open(os.path.join(SP,"cur","out",f"{pdf}-p{pg:02d}-e6b.json"),"w"),ensure_ascii=False)
    print(f"## {pdf} p{pg:02d}")
    for r in rows:
        if not any(r.get(c) for c in cols): continue
        print(" | ".join(f"{r.get(c,'')}" for c in ["m"]+cols)[:190])
for pg in (15,16,17,18):
    show("小6カリキュラム",pg,{"m":(0.02,0.047),"n":(0.047,0.09),"k":(0.09,0.14),"u":(0.14,0.245),"t1":(0.245,0.36),"t2":(0.36,0.5)},["n","k","u","t1","t2"],0.29,0.95)
for pg in (11,12):
    show("小6カリキュラム",pg,{"m":(0.02,0.055),"w":(0.055,0.1),"aa":(0.1,0.2),"ab":(0.2,0.3),"ba":(0.3,0.385),"bb":(0.385,0.5)},["w","aa","ab","ba","bb"],0.29,0.72)
for pg in (13,14):
    show("小6カリキュラム",pg,{"m":(0.02,0.055),"w":(0.055,0.1),"a":(0.1,0.3),"b":(0.3,0.5)},["w","a","b"],0.29,0.72)
