# 中学の【カリキュラム】表（カレンダー｜回｜学習単元｜テスト）。
import sys,os,re
sys.path.insert(0,os.path.dirname(__file__)); import bands as B
SP=sys.argv[1]
def header(lines):
    for y,cs in lines:
        xs={t:x for x,t in cs}
        u=[x for x,t in cs if "学習単元" in t or t.startswith("授業内容")]
        te=[x for x,t in cs if t=="テスト" or t.endswith("テスト") and x>0.7]
        ca=[x for x,t in cs if "カレンダー" in t]
        if u: return y,(ca[0] if ca else u[0]-0.14),u[0],(te[0] if te else None)
    return None
for spec in sys.argv[2:]:
    pdf,pg=spec.split(":"); pg=int(pg)
    base=os.path.join(SP,"cur","ocr3",pdf,"p%02d"%pg)
    lines=B.lines_of(base+".txt")
    h=header(lines)
    if not h: print("## no header",spec); continue
    y0,xc,xu,xt=h
    bands={"ki":(xc-0.02,xu-0.05),"n":(xu-0.05,xu-0.012),"u":(xu-0.012,(xt-0.03) if xt else 0.99)}
    if xt: bands["t"]=(xt-0.03,0.995)
    rows=B.read(SP,pdf,pg,bands,ylo=y0+0.004)
    title=[t for y,cs in lines for x,t in cs if y<0.12 and x<0.5][:3]
    print(f"## {pdf} p{pg:02d} {' / '.join(title)} 単元x={xu:.2f} テストx={xt}")
    for r in rows:
        if "u" not in r and "ki" not in r: continue
        n=r.get("n","")
        print(f"{r['y']:.3f} {('【'+r['ki']+'】') if r.get('ki') else ''}{n:>3}| {r.get('u','')} | {r.get('t','')}"[:170])
