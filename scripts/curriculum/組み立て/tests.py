# 小4・小5 のテスト日程（p02／p04）。表のとおり：日付のある行がテスト、無い行は範囲の欄の「回」。
import json,os,re,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); from clean import pick
OUT=os.environ.get("CUR_OUT") or os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","中間")
D=re.compile(r"^(\d{1,2})/(\d{1,2})（(.)）")
FILLED={("小5カリキュラム","前期","5/10"):"公開組分けテスト",("小4カリキュラム","後期","1/16"):"カリキュラムテスト",("小5カリキュラム","後期","9/12"):"カリキュラムテスト",("小5カリキュラム","後期","10/17"):"カリキュラムテスト",("小5カリキュラム","後期","12/5"):"カリキュラムテスト"}
def rows(pdf,pg,half):
    out=[]
    for r in json.load(open(f"{OUT}/{pdf}-p{pg:02d}-{half}-tests.json")):
        rng=[re.sub(r"\s+","",pick(x)) for x in r["r"] if "出題範囲" not in x and "出選" not in x]
        rng=[re.sub(r"(予習シリーズ\d年[上下])(第\d+回)",r"\1 \2",x).replace("*","＊") for x in rng]
        j=[]
        for x in rng:
            if j and re.search(r"年[上下]$",j[-1]) and x.startswith("第"): j[-1]=j[-1]+" "+x
            else: j.append(x)
        rng=j
        if r["d"]=="?":
            for x in rng: out.append({"range":x})
            continue
        m=D.match(r["d"]); mo,da=int(m[1]),int(m[2]); y=2027 if mo==1 else 2026
        name=r["n"].replace("カリキュラムテストカリキュラムテスト","カリキュラムテスト").replace("公開組分けテストカリキュラムテスト","公開組分けテスト")
        row={"date":f"{y}-{mo:02d}-{da:02d}","weekday":m[3],"test":name}
        key=(pdf,half,f"{mo}/{da}")
        if not name and key in FILLED: row["test"]=FILLED[key]; row["filled"]=True
        first=rng[:1]; rest=rng[1:]
        if first: row["range"]=first[0]
        if "range" not in row and out and "date" not in out[-1] and out[-1]["range"].endswith("＊"):
            row["range"]=out.pop()["range"]
        out.append(row)
        for x in rest: out.append({"range":x})
    return out
def all_tests():
    return {"e4":{"first":rows("小4カリキュラム",2,"前期"),"second":rows("小4カリキュラム",2,"後期"),"page":2,"note":"＊4月以降の公開組分けテストは、前の総合回の学習内容がおよそ3割出題されます。"},
            "e5":{"first":rows("小5カリキュラム",4,"前期"),"second":rows("小5カリキュラム",4,"後期"),"page":4}}
if __name__=="__main__":
    for g,t in all_tests().items():
        for h in ("first","second"):
            print(g,h,[(r.get("date","")[5:],r.get("test","")[:2],r.get("range","")[-4:]) for r in t[h] if "date" in r])
