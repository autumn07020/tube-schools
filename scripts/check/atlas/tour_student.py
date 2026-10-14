# -*- coding: utf-8 -*-
"""生徒の画面を撮る。 python3 tour_student.py <S> <persona> <dev> [full|base]"""
import glob, json, os, sys, time
from atlaslib import *
LID, DV = sys.argv[2], sys.argv[3]; MODE = sys.argv[4] if len(sys.argv) > 4 else "full"
WHO = ACC[LID]["label"]
with Chrome(port=int(os.environ.get('ATLAS_PORT', '9860')), **DEV[DV]) as c:
    t = Tour(c, DV, "生徒-" + LID, LID, "生徒 " + WHO)
    assert t.login(LID), "login"
    if MODE == "dark":
        t.ev("document.documentElement.setAttribute('data-theme','dark')"); time.sleep(0.6)
        for tb, nm in (("today", "ホーム"), ("homework", "宿題"), ("daily", "毎日テスト"), ("record", "先生から")):
            t.tab(tb); t.ev("document.documentElement.setAttribute('data-theme','dark')"); time.sleep(0.5)
            t.cap("暗-" + nm, nm + "（暗い配色。いまは切り替える場所が無い）", "CSS に値だけある（:root[data-theme=dark]）。画面からは選べない", segs=2)
        t.save("student-%s-%s-dark" % (LID, DV)); sys.exit(0)
    t.cap("01ホーム", "ホーム（今日やること・自分の記録）", "入ると最初に出る。下のタブ「ホーム」", "上から：先生からのお知らせ／いまやるならこれ／今週の宿題／自分の記録の札", segs=5)
    t.tab("homework"); t.cap("02宿題", "宿題（今週・来週・教科ごと）", "下のタブ「宿題」", "上の2枚はホームと同じ札。教科の札は教科の色（薄いグラデーション）", segs=5)
    t.tab("daily"); t.cap("03毎日テスト", "毎日テスト（教科の札・組み分けテスト対策・続けた記録）", "下のタブ「毎日テスト」", segs=5)
    t.tab("record"); t.cap("04先生から", "先生から（先生のことば・積み上げ・教科ごとの返事）", "下のタブ「先生から」", segs=5)
    if MODE == "base":
        t.save("student-%s-%s" % (LID, DV)); sys.exit(0)
    # --- 重なり（紙）と、その先の画面
    t.tab("today"); t.click("#hMenu"); t.cap("05メニュー", "メニュー", "右上の「･･･」", "保護者の方へ／設定／うまく動かないとき／ログアウト（確かめは画面の中で）")
    t.reload(); t.tab("today")
    if t.click("[data-goal]"): t.cap("06今週の目標の紙", "今週の目標を決める紙", "ホーム →「今週の目標」の札", layer=True)
    t.reload(); t.tab("homework")
    if t.click("[data-hfin]"): t.cap("07終わった宿題", "宿題（終わった宿題を開いたところ）", "宿題 →「終わった宿題 n件 ›」", segs=3)
    # 写真をためる（紙の宿題を写真で出す）
    t.reload(); t.tab("homework")
    pics = sorted(glob.glob(S + "/real/schools/london/submissions/*/*.png"))[:2]
    try:
        if pics and t.has("[data-up]") and attach_files(c, "[data-up]", pics):
            time.sleep(2.5); t.ev("(function(){ var e=document.querySelector('[data-stage]'); if(e) e.scrollIntoView({block:'center'}); })()")
            if t.has("[data-stage]"):
                time.sleep(0.5); p = os.path.join(OUT, "%s-08写真をためる-%s.png" % (t.section, DV)); c.shot(p)
                t.items.append({"section": t.section, "key": "08写真をためる", "dev": DV, "files": [os.path.basename(p)], "title": "紙の宿題を写真で出す（ためてから送る）", "how": "宿題 → 紙の宿題の行の「写真で出す」→ 撮る／選ぶ", "note": "撮った写真が札にたまる。×で外す・もう1枚撮る・「n枚を送る」。送るのはボタンを押したときだけ", "persona": t.who})
                print("  cap 写真をためる", flush=True)
    except Exception as e: print("  ! upload", e)
    # 先生から → 教科のページ・添削された答案
    t.reload(); t.tab("record")
    if t.click("[data-fbsub]"): t.cap("09教科の返事", "先生から → 教科のページ（1件ずつの返事）", "先生から → 教科の行", segs=3)
    t.reload(); t.tab("record")
    if t.click("[data-ret]"): t.cap("10添削された答案", "添削された答案を見る紙", "先生から →「添削された答案を見る（n枚）」", layer=True)
    t.reload(); t.tab("record")
    if t.click("[data-ntask]"): t.cap("11お知らせに質問", "宿題の変更のお知らせ →「質問する」", "先生から（ホームにも）の青い縁の札 →「質問する」", segs=1)
    # 保護者の方へ・設定・報告
    t.reload(); t.go("parent"); t.cap("12保護者の方へ", "保護者の方へ（％つきの記録・先生へのメッセージ）", "メニュー →「保護者の方へ」", "生徒の画面には％を出さない。数字は保護者と講師だけ", segs=5)
    t.go("settings"); t.cap("13設定", "設定", "メニュー →「設定」", segs=3)
    if t.click("#mPlace"): t.cap("14クラスを変える", "クラス・受講科目を変える", "設定 →「クラス・受講科目を変える」", "初回登録と同じ部品（学年→クラス→受講科目）", segs=3)
    t.reload(); t.go("report"); t.cap("15うまく動かないとき", "うまく動かないとき（報告）", "メニュー →「うまく動かないとき」", segs=2)
    # カメラで丸つけ
    t.reload(); t.tab("daily")
    if t.click("[data-camopen]"):
        t.cap("16カメラで丸つけ-教科", "カメラで丸つけ：教科を選ぶ紙", "毎日テスト →「カメラで丸つけ」", layer=True)
        if t.click("[data-campick]"): t.cap("17カメラで丸つけ-撮る", "カメラで丸つけ：解答らんを撮る紙", "教科を選ぶ", layer=True)
    # 毎日テスト（解いている最中）
    ST = "JSON.stringify({show:!!document.querySelector('#show'), g:document.querySelectorAll('[data-g]').length, o:[].map.call(document.querySelectorAll('[data-o]'),function(b){return b.className+'|'+b.innerText;}), nx:!!document.querySelector('#nx'), gs:!!document.querySelector('#gStart'), end:!!document.querySelector('#dEnd'), q:((document.querySelector('#sBody')||{}).innerText||'').slice(0,60)})"
    def walk(prefix, label, how, limit=160):
        got, memo = set(), {}
        for i in range(limit):
            st = json.loads(t.ev(ST))
            if st["end"]:
                t.cap(prefix + "-5おわり", label + "：終わったところ（お疲れさまでした）", "最後の問題まで答える", segs=1); return True
            if not (st["show"] or st["g"] or st["o"] or st["nx"] or st["gs"]): time.sleep(0.6); continue
            if st["g"]:
                wrong = any("wrong" in x for x in st["o"]); card = not st["o"]
                key = "card2" if card else ("wrong" if wrong else "right")
                if key not in got:
                    got.add(key)
                    if card: t.cap(prefix + "-2用語の答え", label + "：用語カードの答え（自分で4段階を付ける）", "「答えを見る」", "次に出る時期（1分・1日・4日…）がボタンに書いてある", segs=1)
                    elif wrong: t.cap(prefix + "-4まちがい", label + "：4択をまちがえたとき（正解と解説。覚え直す）", "ちがう選択肢を押す", segs=1)
                    else: t.cap(prefix + "-3正解", label + "：4択に正解したとき", "正しい選択肢を押す", segs=1)
                t.click("[data-g]:last-child", wait=0.55)
            elif st["show"]:
                if "card1" not in got: got.add("card1"); t.cap(prefix + "-1用語", label + "：用語カード（思い出してから答えを見る）", how, "上に「やめる」と進みの帯", segs=1)
                t.click("#show", wait=0.5)
            elif st["o"]:
                if "q" not in got: got.add("q"); t.cap(prefix + "-0問題", label + "：4択の問題", how, segs=1)
                want = memo.get(st["q"])
                if want: t.click_text("[data-o]", want, wait=0.6)
                else:
                    # 見本として、はじめの2問のうち1問はわざとまちがえる
                    t.click("[data-o]", nth=(1 if "wrong" not in got and len(memo) == 1 else 0), wait=0.7)
                    st2 = json.loads(t.ev(ST)); r = [x.split("|", 1)[1] for x in st2["o"] if "right" in x]
                    if r: memo[st["q"]] = r[0]
            elif st["gs"]: t.click("#gStart", wait=0.6)
            elif st["nx"]: t.click("#nx", wait=0.5)
        return False
    t.reload(); t.tab("daily")
    if t.click("[data-start]", wait=1.8):
        if not walk("18テスト", "毎日テスト", "毎日テスト → 教科の札（か「始める」）"): print("  ! session did not end")
        if t.has("#dEnd"): t.click("#dEnd", wait=1.5)
        t.tab("daily"); t.cap("19テストのあと", "毎日テスト（1教科を終えたあとのタブ）", "終わって「戻る」", segs=2)
    # 組み分けテスト対策・にがてつぶし
    t.reload(); t.tab("daily")
    if t.click("[data-prep]", wait=2.0):
        t.cap("21対策テスト-問題", "組み分けテスト対策：解いているところ", "毎日テスト → 対策の札の「解く →」", "1教科50分ぶん。ふだんの毎日テストと同じ出し方", segs=1)
        t.click("#sQuit", wait=1.2)
    t.reload(); t.tab("daily")
    if t.click("[data-retest]", wait=2.0):
        t.cap("22にがてつぶし-再テスト", "にがてつぶし：再テスト", "毎日テスト → にがてつぶしの「再テスト →」", segs=1)
        t.click("#sQuit", wait=1.2)
    t.save("student-%s-%s" % (LID, DV))
