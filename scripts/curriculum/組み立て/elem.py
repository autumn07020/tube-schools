# 小4・小5・小6 の予習シリーズ型の表（前期・後期）。parse_e の出力＋手直し。
import json,os,re,sys
sys.path.insert(0,os.path.dirname(__file__)); from clean import clean
OUT=os.environ.get("CUR_OUT") or os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","中間")
# (pdf,page,表番号) → 教科の列
LAYOUT={("小4カリキュラム",3,0):("japanese","words"),("小4カリキュラム",3,1):("math","social","science"),
 ("小4カリキュラム",7,0):("japanese","words"),("小4カリキュラム",7,1):("math","social","science"),
 ("小5カリキュラム",5,0):("japanese","words"),("小5カリキュラム",5,1):("math","social","science"),
 ("小5カリキュラム",10,0):("japanese","words"),("小5カリキュラム",10,1):("math","social","science"),
 ("小6カリキュラム",5,0):("japanese","words","math"),("小6カリキュラム",5,1):("social","science")}
FIX={ # (pdf,page,表,回,列) → 文字
 ("小4カリキュラム",3,0,11,1):"文を読む①―主語・述語を読む／和語③",("小4カリキュラム",3,0,12,1):"文を読む②―修飾・被修飾関係を読む／ことわざ①",
 ("小4カリキュラム",3,0,13,1):"文を読む③―主語・述語・修飾語の復習／類義語",("小4カリキュラム",3,0,14,1):"文を読む④―分けて〈関係〉を考える／対義語",
 ("小4カリキュラム",7,0,4,1):"単語の学習④副詞・文の基本型／四字の熟語",("小4カリキュラム",7,1,17,1):"食べ物は日本でつくられる？～日本の農業（6）～",("小4カリキュラム",7,1,17,2):"水溶液の分類",
 ("小5カリキュラム",5,1,1,1):"魚はどこから？～日本の水産業～",("小5カリキュラム",5,1,1,2):"季節と生物",
 ("小5カリキュラム",5,1,11,0):"場合の数―ならべ方―",("小5カリキュラム",5,1,12,0):"場合の数―組み合わせ方―",
 ("小5カリキュラム",10,0,7,1):"単語の学習②助詞／慣用句②",("小5カリキュラム",10,0,8,1):"文語的表現①／同音異字・同音異義語",("小5カリキュラム",10,0,9,1):"文語的表現②／同訓異字",
 ("小5カリキュラム",10,0,16,1):"文と文の関係③因果関係／故事成語",("小5カリキュラム",10,0,17,1):"文と文の関係④抽象と具体／四季の言葉（秋・冬）",
 ("小5カリキュラム",10,1,2,0):"平面図形と比―相似の利用―",("小5カリキュラム",10,1,3,0):"平面図形と比―辺の比と面積比―",("小5カリキュラム",10,1,8,0):"平面図形と比―まとめと応用―",
 ("小5カリキュラム",10,1,4,1):"平安時代",("小5カリキュラム",10,1,7,0):"旅人算と比",("小5カリキュラム",10,1,12,1):"江戸時代（3）",
 ("小6カリキュラム",5,0,11,1):"対比の関係②比べる／慣用句③",("小6カリキュラム",5,0,11,2):"立体図形（1）",("小6カリキュラム",5,0,3,0):"説明文・論説文（1）／自然と環境",
 ("小6カリキュラム",5,0,4,1):"細部の文脈②接続関係／四字の熟語①",("小6カリキュラム",5,0,12,1):"因果関係①順接・理由説明／三字の熟語②",("小6カリキュラム",5,0,18,2):"総合",
 ("小6カリキュラム",5,1,6,1):"恒星・惑星",("小6カリキュラム",5,1,8,1):"燃焼・熱",
}
REVIEW_N={("小4カリキュラム",3):(5,10,15,20),("小4カリキュラム",7):(5,10,15,19),("小5カリキュラム",5):(5,10,15,20),("小5カリキュラム",10):(5,10,15,19),("小6カリキュラム",5):(5,9,14,18)}
def table(pdf,pg,ti):
    d=json.load(open(f"{OUT}/{pdf}-p{pg:02d}-e.json"))
    t=d["tables"][ti]; cols=LAYOUT[(pdf,pg,ti)]; rev=REVIEW_N[(pdf,pg)]
    out={c:[] for c in cols if c!="words"}
    ns=sorted(int(k) for k in t["rows"])
    for n in range(1,max(ns)+1):
        cells=t["rows"].get(str(n),[""]*len(cols))
        vals=[clean(c).replace("/","／") for c in cells]+[""]*(len(cols)-len(cells))
        for i,c in enumerate(cols):
            if (pdf,pg,ti,n,i) in FIX: vals[i]=FIX[(pdf,pg,ti,n,i)]
        if n in rev:
            vals=["総合" if c!="words" else "" for c in cols]
        row={}
        for i,c in enumerate(cols): row[c]=vals[i]
        for c in cols:
            if c=="words": continue
            u={"n":n,"unit":row[c]}
            if c=="japanese": u["words"]=row.get("words","")
            if n in rev: u["review"]=True
            out[c].append(u)
    return out
def check():
    for key,cols in LAYOUT.items():
        t=table(*key)
        for c,us in t.items():
            empties=[u["n"] for u in us if not u["unit"]]; conf=[u["n"] for u in us if "⇄" in u["unit"]+u.get("words","")]
            print(f"{key} {c}: {len(us)}回 空{empties} ⇄{conf}")
            print("   "+"／".join((u["unit"]+("｜"+u["words"] if u.get("words") else "")) for u in us))
if __name__=="__main__": check()
