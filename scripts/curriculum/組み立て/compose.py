#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""カリキュラム/カリキュラム.json を組み立てる（第一信頼情報源）。

  python3 scripts/curriculum/組み立て/compose.py

出どころ：カリキュラム/ の 8 つの PDF。読み取り（OCR）→ 多数決と画像での確認 → 手直し（junior.py・elem.py・
kcourse.py・e6second.py・tests.py・london.py）→ この束ね。値は日本語、鍵は英語。
"""
import datetime as dt, json, os, re, sys
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
ROOT=os.path.abspath(os.path.join(HERE,"..","..",".."))
import junior as J, elem as E, kcourse as K, e6second as E6, tests as T, london as L, contents as CT
VERSION="2026-10-08"
def mon(d):
    x=dt.date(*map(int,d.split("-"))); return (x-dt.timedelta(days=x.weekday())).isoformat()
def sun2mon(d): return (dt.date(*map(int,d.split("-")))+dt.timedelta(days=1)).isoformat()

# ---- 小4・小5・小6前期 ----
def elementary():
    out={}
    meta={"e4":("小4","小4カリキュラム.pdf",[("first","前期","2月〜7月",3,(5,10,15,20)),("second","後期","9月〜1月",7,(5,10,15,19))]),
          "e5":("小5","小5カリキュラム.pdf",[("first","前期","2月〜7月",5,(5,10,15,20)),("second","後期","9月〜1月",10,(5,10,15,19))]),
          "e6":("小6","小6カリキュラム.pdf",[("first","前期","2月〜7月",5,(5,9,14,18))])}
    for g,(name,pdf,terms) in meta.items():
        gd={"name":name,"source":pdf,"terms":{}}
        for key,tname,months,page,rev in terms:
            subjects={}
            for ti in (0,1):
                for subj,units in E.table(pdf[:-4],page,ti).items(): subjects[subj]=units
            res,bad,miss=CT.extract(g,key)
            for subj,units in subjects.items():
                for u in units:
                    v=[x for b in res.get((u["n"],subj),[]) for x in b.split("■") if x]
                    if v: u["contents"]=v
                    if subj=="japanese":
                        w=[x for b in res.get((u["n"],"words"),[]) for x in b.split("■") if x]
                        if w: u["words_contents"]=w
            gd["terms"][key]={"name":tname,"months":months,"page":page,"count":len(subjects["math"]),"review":list(rev),"subjects":subjects,
                "contents_note":"contents（words_contents）は各回の詳しいページの「■学習内容」の見出し。1回読みで未校正（字の小さな落ちがありうる）。単元名と突き合わせて付けた。総合の回と、取れなかった回・教科には無い："+("、".join(f"第{n}回{({'japanese':'国語','words':'漢字とことば','math':'算数','social':'社会','science':'理科'})[s_]}" for n,s_ in sorted(miss)) or "なし")}
        out[g]=gd
    tests=T.all_tests()
    for g in ("e4","e5"): out[g]["tests"]=tests[g]
    # 小6 後期
    social=[{"n":n,"kai":kai,"unit":u,"check":c,"stats":s} for n,kai,u,c,s in E6.SOCIAL]
    science=[{"n":n,"kai":kai,"unit":u,"check":c,"check10":i+1} for i,(n,kai,u,c) in enumerate(E6.SCIENCE)]
    out["e6"]["terms"]["second"]={"name":"後期","months":"9月〜1月","pages":"11-18",
        "note":"後期は予習シリーズ6年下。社会・理科は授業回数と『予習シリーズの回数』の対応表（SS と SB・SA で同じ）。算数は『下N回』の名前と週別の予定。国語は週別の予定だけで、回の名前は原本に無い。",
        "social":social,"science":science,
        "math":{"kai":{str(k):v for k,v in E6.MATH_KAI.items()},"weekly":{"SS":E6.MATH_SS,"SB-SA":E6.MATH_SBSA},"pages":"13-14"},
        "japanese":{"weekly":{"SB-SA":E6.JAPANESE_SBSA},"note":E6.JAPANESE_SS_NOTE,"pages":"11-12"}}
    return out

# ---- 5K6K ----
def kcourses():
    out={"source":"小5K6Kカリキュラム.pdf","note":"回数は年間の通し番号（1〜36。英語1年目は1〜30）。講習会は別カリキュラム。","classes":{}}
    for pg,(cls,subj,n) in K.PAGES.items():
        c,s,units=K.units(pg)
        key={"5K":"5K","6K":"6K","1年目":"english-year1","6K2年目":"english-year2"}[cls]
        if subj=="english": out.setdefault("english",{})[ {"1年目":"year1","6K2年目":"year2"}[cls] ]={"page":pg,"class":cls,"units":units}
        else: out["classes"].setdefault(cls,{})[subj]={"page":pg,"units":units}
        g_raw=prose("小5K6Kカリキュラム",pg)
        if g_raw:
            (out["english"][{"1年目":"year1","6K2年目":"year2"}[cls]] if subj=="english" else out["classes"][cls][subj])["goals_raw"]=g_raw
    return out

# ---- 中学 ----
JPAGES={("中1カリキュラム",4):("j1","1T","english",120),("中1カリキュラム",5):("j1","1T","math",80),("中1カリキュラム",6):("j1","1R","math",80),
 ("中1カリキュラム",7):("j1","1T","japanese",80),("中1カリキュラム",8):("j1","1R","japanese",80),("中1カリキュラム",9):("j1","1rS","science",40),("中1カリキュラム",10):("j1","1rS","social",40),
 ("中2カリキュラム",5):("j2","2T","english",130),("中2カリキュラム",6):("j2","2T","math",130),("中2カリキュラム",7):("j2","2R1","math",100),("中2カリキュラム",8):("j2","2T","japanese",130),
 ("中2カリキュラム",9):("j2","2R","japanese",100),("中2カリキュラム",10):("j2","2rS","science",50),("中2カリキュラム",11):("j2","2rS","social",50),
 ("中3カリキュラム",5):("j3","3T","english",130),("中3カリキュラム",7):("j3","3T","math",130),("中3カリキュラム",8):("j3","3R1","math",100),("中3カリキュラム",9):("j3","3T","japanese",130),
 ("中3カリキュラム",10):("j3","3R1","japanese",100),("中3カリキュラム",11):("j3","3rST","science",50),("中3カリキュラム",12):("j3","3rST","social",50)}
def junior():
    out={"j1":{"name":"中1","source":"中1カリキュラム.pdf","classes":{}},"j2":{"name":"中2","source":"中2カリキュラム.pdf","classes":{}},"j3":{"name":"中3","source":"中3カリキュラム.pdf","classes":{}}}
    for (pdf,pg),(g,cls,subj,minutes) in JPAGES.items():
        terms=[]
        for term,rows in J.blocks(pdf,pg):
            us=[]
            for i,r in enumerate(rows):
                u={"n":i+1,"unit":r["unit"]}
                if subj in ("science","social"):
                    raw=" ／ ".join(x for x in (r.get("test"),r.get("prep")) if x)
                    if raw: u["tasks_raw"]=raw
                else:
                    if r.get("test"): u["test"]=r["test"]
                    if r.get("prep"): u["prep"]=r["prep"]
                us.append(u)
            terms.append({"term":term,"count":len(us),"units":us})
        d={"page":pg,"minutes":minutes,"terms":terms}
        if subj in ("science","social"):
            d["tasks_raw_note"]="tasks_raw（テスト・復習課題・予習課題の欄）は読み取りのまま。未校正なので、使う前に PDF の該当頁で確かめる。単元名（unit）は校正済み。"
        g_raw=prose(pdf,pg)
        if g_raw: d["goals_raw"]=g_raw
        if (pdf,pg)==("中3カリキュラム",7): d["note"]="数学3Tの表は p7。2学期は24回（週2回）。3月〜夏期の表は原本に無い。"
        if (pdf,pg)==("中1カリキュラム",4): d["note"]="中1準備講座と春期講習会は A（アドバンス）／R（レギュラー）で単元が違う（A：…｜R：…）。"
        out[g]["classes"].setdefault(cls,{})[subj]=d
    return out

def prose(pdf,pg):
    """頁の左半分の文（授業の目的・教材・授業進行・宿題の目安など）。読み取りのまま・未校正。"""
    f=os.path.join(HERE,"..","中間",f"{pdf}-p{pg:02d}-prose.json")
    try: d=json.load(open(f,encoding="utf-8"))
    except (OSError,ValueError): return None
    def key(k):
        k=re.sub(r"^[（(1【]","",k).strip("）)」】")
        if k.startswith("授業の目"): return "授業の目的"
        if k.endswith("題の目安"): return "宿題の目安"
        if "教材" in k or k in ("数材",): return "教材"
        return k
    sec={}
    for k,v in (d.get("sections") or {}).items():
        if v: sec[key(k)]=(sec.get(key(k),"")+v)
    if not sec: return None
    return {"status":"読み取りのまま・未校正（PDF の該当頁が正）","sections":sec}

# ---- ロンドン ----
def london():
    weeks=[]
    sun=dt.date(2026,8,23)
    for i in range(24):
        s=sun+dt.timedelta(days=7*i); d=lambda k:(s+dt.timedelta(days=k)).isoformat()
        w={"sunday":d(0),"monday":d(1),"weekdays":{"elementary":L.E_WED.get(d(3),""),"junior":L.J_WED.get(d(3),"")},
           "sat":{"elementary":L.E_SAT.get(d(6),""),"junior":L.J_SAT.get(d(6),"")},"sun":{"elementary":L.E_SUN.get(d(0),""),"junior":L.J_SUN.get(d(0),"")}}
        if d(1) in L.MON: w["mon"]=L.MON[d(1)]
        weeks.append(w)
    lesson={"e4":[],"e5":[],"e6":[],"junior":[]}
    for w in weeks:
        e=w["weekdays"]["elementary"]; j=w["weekdays"]["junior"]; m=w["monday"]
        if e.startswith("四谷大塚"):
            m45=re.search(r"小4[&～]小5第(\d+)回|小3[～&]小5第(\d+)回",e)
            if m45: n=m45[1] or m45[2]; lesson["e4"].append({"monday":m,"label":f"第{n}回"}); lesson["e5"].append({"monday":m,"label":f"第{n}回"})
            m6=re.search(r"小6第(\d+)回",e)
            if m6: lesson["e6"].append({"monday":m,"label":f"第{m6[1]}回"})
            elif "小6合" in e: lesson["e6"].append({"monday":m,"label":"合判対策"})
        if "通常授業" in j: lesson["junior"].append({"monday":m,"label":j})
    tests={"elementary":[{"date":d,"name":v} for d,v in sorted(L.E_SAT.items()) if v and v!="休校"]+[{"date":d,"name":v} for d,v in sorted(L.E_SUN.items())],
           "junior":[{"date":d,"name":v} for d,v in sorted(L.J_SAT.items()) if v and v!="休校"]+[{"date":d,"name":v} for d,v in sorted(L.J_SUN.items())]}
    for k in tests: tests[k].sort(key=lambda x:x["date"])
    return {"source":"後期日程表.pdf","status":"仮日程（原本の注）","weeks":weeks,"lesson_weeks":lesson,"tests":tests,
            "holidays":[{"from":a,"to":b,"what":c} for a,b,c in L.HOLIDAY_RANGES]+[{"from":"2027-01-25","to":"2027-01-29","what":"休校日（週の帯）"},{"from":"2027-02-01","to":"2027-02-05","what":"休校日（週の帯）"}],
            "notes":L.NOTES}

# ---- ロンドンのコース → 表 と、週に並べたシラバス ----
ELEM_CLASSES={"e4a":"e4","e4b":"e4","e4":"e4","e5a":"e5","e5b":"e5","e5":"e5","e6a":"e6","e6b":"e6","e6":"e6"}
JUNIOR_MAP={"j1t:math":("j1","1T"),"j1r:math":("j1","1R"),"j1tr:japanese":("j1","1T"),"j1tr:english":("j1","1T"),"j1:science":("j1","1rS"),"j1:social":("j1","1rS"),
 "j2t:japanese":("j2","2T"),"j2t:math":("j2","2T"),"j2r:japanese":("j2","2R"),"j2r:math":("j2","2R1"),"j2tr:english":("j2","2T"),"j2:science":("j2","2rS"),"j2:social":("j2","2rS"),
 "j3t:japanese":("j3","3T"),"j3t:math":("j3","3T"),"j3t:english":("j3","3T"),"j3r:japanese":("j3","3R1"),"j3r:math":("j3","3R1"),"j3r:english":("j3","3T"),"j3tr:english":("j3","3T"),"j3:science":("j3","3rST"),"j3:social":("j3","3rST"),
 "j1d:japanese":("j1","1R"),"j1d:math":("j1","1R"),"j2d:japanese":("j2","2R"),"j2d:math":("j2","2R1")}
K_MAP={"e5k:japanese":("5K","japanese"),"e6k:japanese":("6K","japanese"),"e6k:math":("6K","math")}
MAP_NOTES={"j1tr:japanese":"1T の表を使う（1R の表もある）。要確認。","j1d:japanese":"D クラスは R の表（2026-10-08 本人）","j1d:math":"D クラスは R の表（2026-10-08 本人）","j2d:japanese":"D クラスは R の表（2026-10-08 本人）","j2d:math":"D クラスは R の表（2026-10-08 本人）","j3r:english":"英語は 3T の表しかない。","j1tr:english":"英語は 1T の表しかない。"}
UNMAPPED={"e4:english":"原本に小4の英語の表が無い","e5:english":"原本に小5の英語の表が無い（5K/6K 英語は K クラス用）","e6:english":"同上","e5o:japanese":"小5O は原本に無い","e5o:social":"小5O は原本に無い","e4o:math":"小4O は原本に無い",
 "e6nanpro:japanese":"難プロは別","e6nanpro:math":"難プロは別","e6nanpro:science":"難プロは別","e6nanpro:social":"難プロは別",
 "e6doku:japanese":"土特は別","e6doku:math":"土特は別","e56bunpo:english":"文法講座は別","e56chobun:english":"長文講座は別","edoga:math":"動画講座は別","j2ttoku:math":"特訓は別","jdoga:math":"動画講座は別","j3doku:math":"土特は別","j3doku:japanese":"土特は別",
 "j3sokei:japanese":"早慶は別","j3sokei:math":"早慶は別","j3sokei:english":"早慶は別","j3o:english":"中3O は原本に無い","e1j:japanese":"小1〜小3は原本に無い","e1j:math":"同上","e2j:japanese":"同上","e2j:math":"同上","e3j:japanese":"同上","e3j:math":"同上","e3j:science":"同上","e3j:social":"同上"}
TIMING_J="9月通常授業①（8/31の週）＝本部の2学期①。以後は通常授業の週に1回ずつ（冬期講習会の回も順に）。2026-10-08 本人に確認。"
K_START={"6K":17,"5K":17}
TIMING_K="9月通常授業①（8/31の週）＝第17回、以後1週1回。6K は 2026-10-08 本人に確認（比の単元＝第17回「比①」から）。"
ALIGN_K5="5K は 6K と同じ年間カレンダーなので第17回からと置いた（本人に未確認）。"
COURSE_NAME={}
SUBJ_NAME={"japanese":"国語","math":"算数","english":"英語","science":"理科","social":"社会"}
def course_syllabi(elem,kc,jr,ldn,course_keys):
    out={}; classes={}
    lw=ldn["lesson_weeks"]
    for key in course_keys:
        cid,subj=key.split(":")
        sid=key.replace(":","-")+"-2026b"
        if key in UNMAPPED: classes[key]={"table":None,"note":UNMAPPED[key]}; continue
        if cid in ELEM_CLASSES and subj in ("japanese","math","science","social"):
            g=ELEM_CLASSES[cid]; units=[]
            if g in ("e4","e5"):
                tab={u["n"]:u for u in elem[g]["terms"]["second"]["subjects"][subj]}
                for w in lw[g]:
                    n=int(w["label"][1:-1]); u=tab.get(n)
                    if not u: continue
                    units.append({"label":w["label"],"topic":u["unit"],"review":bool(u.get("review")),"week":w["monday"]})
                src=f"{elem[g]['source']} p{elem[g]['terms']['second']['page']}（予習シリーズ{g[1]}年下）＋後期日程表"
                classes[key]={"table":f"elementary.{g}.terms.second.subjects.{subj}","timing":f"london.lesson_weeks.{g}"}
            else:
                sec=elem["e6"]["terms"]["second"]
                if subj=="social": kai={r["kai"]:r["unit"] for r in sec["social"] if r["kai"]}
                elif subj=="science": kai={r["kai"]:r["unit"] for r in sec["science"] if r["kai"]}
                elif subj=="math": kai={f"第{k}回":v for k,v in sec["math"]["kai"].items()}
                else: kai={}
                gk=0
                for w in lw["e6"]:
                    if w["label"]=="合判対策":
                        gk+=1; units.append({"label":"合判対策"+J.circ(gk),"topic":"合不合判定テスト対策","review":False,"week":w["monday"]})
                    else: units.append({"label":w["label"],"topic":kai.get(w["label"]) or f"予習シリーズ6年下 {w['label']}（単元名は原本に無い）","review":False,"week":w["monday"]})
                src="小6カリキュラム.pdf p11-18（予習シリーズ6年下）＋後期日程表"
                classes[key]={"table":f"elementary.e6.terms.second.{subj}","timing":"london.lesson_weeks.e6"}
            name=COURSE_NAME.get(key) or f"{elem[g]['name']} {SUBJ_NAME[subj]}"
            out[sid]={"id":sid,"name":name,"grade":g,"subject":subj,"materials":[],"provisional":False,"source":src,"perWeek":True,
                      "anchor":{"unit":units[0]["label"],"week":units[0]["week"]},"units":units}
            classes[key]["syllabus"]=sid; continue
        if key in K_MAP:
            cls,s=K_MAP[key]; tab=kc["classes"][cls][s]["units"]; units=[]
            for i,w in enumerate(lw["junior"]):
                n=K_START[cls]+i
                if n>len(tab): break
                u=tab[n-1]; units.append({"label":f"第{n}回","topic":u["unit"],"review":False,"week":w["monday"]})
            out[sid]={"id":sid,"name":COURSE_NAME.get(key) or f"小{cls} {SUBJ_NAME[s]}","grade":"e5" if cls=="5K" else "e6","subject":s,"materials":[],"provisional":False,
                      "source":f"小5K6Kカリキュラム.pdf p{kc['classes'][cls][s]['page']}＋後期日程表","perWeek":True,"timing":TIMING_K,**({"alignment":ALIGN_K5} if cls=="5K" else {}),
                      "anchor":{"unit":units[0]["label"],"week":units[0]["week"]},"units":units}
            classes[key]={"table":f"k.classes.{cls}.{s}","timing":"london.lesson_weeks.junior","syllabus":sid,"rule":TIMING_K,**({"alignment":ALIGN_K5} if cls=="5K" else {})}; continue
        if key in JUNIOR_MAP:
            g,cls=JUNIOR_MAP[key]; d=jr[g]["classes"][cls][subj]
            seq=[]
            for t in d["terms"]:
                if t["term"] in ("2学期","冬期講習会","3学期"):
                    for u in t["units"]: seq.append((t["term"],u))
            per=2 if (g,cls,subj)==("j3","3T","math") else 1
            units=[]; i=0
            for w in lw["junior"]:
                for _ in range(per):
                    if i>=len(seq): break
                    term,u=seq[i]; i+=1
                    short={"2学期":"2学期","冬期講習会":"冬期","3学期":"3学期"}[term]
                    units.append({"label":short+(J.circ(u["n"]) if u["n"]<=20 else str(u["n"])),"topic":u["unit"],"review":False,"week":w["monday"]})
            out[sid]={"id":sid,"name":COURSE_NAME.get(key) or f"{jr[g]['name']} {cls} {SUBJ_NAME[subj]}","grade":g,"subject":subj,"materials":[],"provisional":False,
                      "source":f"{jr[g]['source']} p{d['page']}（{cls}）＋後期日程表","perWeek":True,"timing":TIMING_J,
                      "anchor":{"unit":units[0]["label"],"week":units[0]["week"]},"units":units}
            classes[key]={"table":f"junior.{g}.classes.{cls}.{subj}","timing":"london.lesson_weeks.junior","syllabus":sid,"rule":TIMING_J}
            if key in MAP_NOTES: classes[key]["note"]=MAP_NOTES[key]
            continue
        classes[key]={"table":None,"note":"対応を決めていない"}
    return out,classes

def main():
    elem=elementary(); kc=kcourses(); jr=junior(); ldn=london()
    cb=json.load(open(os.path.join(ROOT,"scripts","check","flows","fixture-bundle.json"),encoding="utf-8"))["courses"]
    courses=[k for k,v in cb]
    global COURSE_NAME
    COURSE_NAME={k:v.get("name") for k,v in cb}
    syl,classes=course_syllabi(elem,kc,jr,ldn,courses)
    doc={"version":VERSION,"year":2026,"about":"早稲田アカデミー ロンドン校（TUBE study）のカリキュラムの第一信頼情報源。カリキュラム/ の PDF を機械で読み、画像で確かめて起こした。鍵は英語、値は日本語。作り方は scripts/curriculum/。",
         "sources":{"小4カリキュラム.pdf":{"pages":12,"used":{"2":"テスト日程","3":"前期の表","7":"後期の表"}},"小5カリキュラム.pdf":{"pages":15,"used":{"4":"テスト日程","5":"前期の表","10":"後期の表"}},
                    "小6カリキュラム.pdf":{"pages":19,"used":{"5":"前期の表","11-18":"後期の学習（国算社理・SS/SB・SA）"}},"小5K6Kカリキュラム.pdf":{"pages":9,"used":{"3-8":"国語・算数・英語の表"}},
                    "中1カリキュラム.pdf":{"pages":11,"used":{"4-10":"英数国理社の表"}},"中2カリキュラム.pdf":{"pages":12,"used":{"5-11":"英数国理社の表"}},"中3カリキュラム.pdf":{"pages":13,"used":{"5,7-12":"英数国理社の表"}},
                    "後期日程表.pdf":{"pages":2,"used":{"1":"2026年度後期行事カレンダー（p2 は空）"}}},
         "subjects":SUBJ_NAME,
         "elementary":elem,"k":kc,"junior":jr,
         "london":{"second_2026":ldn,"classes":classes,"syllabi":syl,
                   "notes":["classes：ロンドンの78コース（コースの鍵 クラス:教科）ごとに、どの表と、どの週の並びを使うか。table が null のコースは対応なし。",
                            "syllabi：表と日程表から週に並べたシラバス。サーバはこれをそのまま読む（server/syllabus.py）。perWeek＝1回は1週。",
                            "小学部の週は日程表の『第N回』そのもの。中学部と5K6Kの決まりは timing／rule（本人に確認済み）。alignment があるものだけ仮定を含む（いまは 5K）。"]}}
    os.makedirs(os.path.join(ROOT,"カリキュラム"),exist_ok=True)
    with open(os.path.join(ROOT,"カリキュラム","カリキュラム.json"),"w",encoding="utf-8") as f: json.dump(doc,f,ensure_ascii=False,indent=1)
    print("syllabi",len(syl),"classes",len(classes),"unmapped",sum(1 for v in classes.values() if not v.get("syllabus")))
    return doc
if __name__=="__main__": main()
