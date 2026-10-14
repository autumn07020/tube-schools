# 小4・小5のテスト日程表（p02/p04）：左＝前期、右＝後期。実施日｜テスト｜範囲
import sys,os,re
sys.path.insert(0,os.path.dirname(__file__)); import bands as B
SP=sys.argv[1]
D=re.compile(r"^(\d{1,2})/(\d{1,2})（(.)）")
for pdf,pg,ylo in (("小4カリキュラム",2,0.5),("小5カリキュラム",4,0.5)):
    for half,(xd,xn,xr) in (("前期",(0.53,0.575,0.64)),("後期",(0.75,0.79,0.86))):
        bands={"d":(xd,xn),"n":(xn,xr),"r":(xr,xr+0.11)}
        rows=B.read(SP,pdf,pg,bands,ylo,0.95)
        print(f"## {pdf} p{pg:02d} {half}")
        cur=None; out=[]
        for r in rows:
            if r.get("d") and D.match(r["d"]):
                cur={"d":r["d"],"n":r.get("n",""),"r":[r["r"]] if r.get("r") else [],"y":r["y"]}; out.append(cur)
            elif r.get("r"):
                # 近い日付の行へ（前後 0.016）
                near=min(out,key=lambda c:abs(c["y"]-r["y"]),default=None)
                if near and abs(near["y"]-r["y"])<0.016: near["r"].append(r["r"])
                else: out.append({"d":"?","n":r.get("n",""),"r":[r["r"]],"y":r["y"]})
            elif r.get("n") and cur: cur["n"]+=r["n"]
        for c in out: print(f"{c['d']:<10}{c['n']:<12}{' '.join(c['r'])}")
        import json
        json.dump(out,open(os.path.join(SP,"cur","out",f"{pdf}-p{pg:02d}-{half}-tests.json"),"w"),ensure_ascii=False)
