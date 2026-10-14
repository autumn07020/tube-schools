# 小5K・6K（国語・算数・英語）。parse_k5 の出力＋手直し。英語は「単元＋単語テストの範囲」を分ける。
import json,os,re,sys
sys.path.insert(0,os.path.dirname(__file__)); from clean import clean
OUT=os.environ.get("CUR_OUT") or os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","中間")
PAGES={3:("5K","japanese",36),4:("6K","japanese",36),5:("5K","math",36),6:("6K","math",36),7:("1年目","english",30),8:("6K2年目","english",36)}
FIX={(7,1):("アルファベット／単語／文のルール",None),(8,1):("時制①",None),(7,2):("be動詞①","1～25"),(3,13):("表現に気をつけて読もう","4級その7・8"),(4,13):("表現に気を付けて文章を読もう","2級その7・8"),(4,17):("ザ★作文ステップ2",None),(4,20):("文学文章の読み方",None),(3,22):("文学文章（1）",None),
 (3,7):("文章構成に気をつけて要旨をとらえよう",None),(6,4):("分数のかけ算",None),(8,2):("時制②",None)}
def units(pg):
    d=json.load(open(f"{OUT}/小5K6Kカリキュラム-p{pg:02d}.json")); cls,subj,n=PAGES[pg]
    out=[]
    for u in d["units"]:
        if u["n"]>n: break
        unit=clean(u["unit"]).replace("/","／"); test=clean(u.get("test",""))
        if (pg,u["n"]) in FIX:
            a,b=FIX[(pg,u["n"])]; unit=clean(a) if a else unit; test=b if b is not None else test
        row={"n":u["n"],"unit":unit}
        if subj=="english":
            m=re.match(r"^(.*?)(\d+～\d+)$",unit)
            if m: row["unit"]=m[1]; row["words"]=m[2]
            if test: row["basic_words"]=test
        else:
            if test: row["check"]=test
        if u.get("gap") and not unit: row["unit"]="？（読めず）"
        out.append(row)
    return cls,subj,out
if __name__=="__main__":
    for pg in PAGES:
        cls,subj,us=units(pg)
        print(f"## p{pg} {cls} {subj} {len(us)}回; 要確認:{[u['n'] for u in us if '？' in u['unit'] or '⇄' in u['unit']]}")
        print("   "+"／".join(f"{u['n']}{u['unit']}" for u in us))
