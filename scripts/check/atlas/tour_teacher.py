# -*- coding: utf-8 -*-
"""講師の画面を撮る。 python3 tour_teacher.py <S> <persona> <dev> [full|main|sub]"""
import json, os, sys, time
from atlaslib import *
LID, DV = sys.argv[2], sys.argv[3]; MODE = sys.argv[4] if len(sys.argv) > 4 else "full"
WHO = ACC[LID]["label"]
with Chrome(port=int(os.environ.get("ATLAS_PORT", "9880")), **DEV[DV]) as c:
    t = Tour(c, DV, "講師-" + LID, LID, WHO)
    assert t.login(LID), "login"
    t.cap("01宿題", "宿題（今日やること・時間割・メッセージ）", "入ると最初に出る。タブ「宿題」", "左上の濃い札が画面に1つのワンポイント（宿題チェック あと○件）。右に今日チェックする回の札（教科の色）", segs=5)
    if MODE == "sub":
        # ほかの講師：導入の段階の違い（紙のまま／写真で提出／添削まで）が出る所だけ
        if t.click_text("[data-dkcheck]", "提出箱") or t.click("[data-dkcheck]"):
            t.cap("02宿題チェック", "宿題チェック（写真で採点）", "今日やることの札 →「チェックする →」", segs=2)
            if t.click("[data-dkshow]"): t.cap("03返した添削", "宿題チェック：返した添削を見ているところ", "添削の札 →「返した添削 n枚」", segs=1)
        t.reload(); t.tab("progress"); t.cap("04導入と進度", "導入と進度", "タブ「導入と進度」", segs=3)
        t.save("teacher-%s-%s" % (LID, DV)); sys.exit(0)
    if t.click("[data-mgopen]"): t.cap("02メッセージに返事", "保護者・生徒からのメッセージに返事を書く", "宿題 → メッセージの札 →「返事を書く」", focus="[data-mgta], [data-mgsend]")
    t.reload(); t.tab("hw")
    if t.click("[data-slot]"):
        t.cap("03授業の紙", "授業の予定と、出す宿題（紙）", "時間割のコマを押す", "前後の回・宿題・1回ずらす／止める・提出箱を出す・にがて10問", layer=True, segs=3)
    # 宿題チェック
    t.reload(); t.tab("hw")
    if t.click("[data-dkcheck]", wait=1.8):
        t.cap("04宿題チェック-写真", "宿題チェック（写真で採点）", "今日やることの札 →「チェックする →」", "左に全員のマス、右に大きな答案と 1〜5 の評価・ひとこと・添削の札。キーの 1〜5 でも付く", segs=3)
        if t.click("[data-dksid]", nth=2): t.cap("05宿題チェック-別の生徒", "宿題チェック：マスを押して別の生徒へ", "左のマスを押す", segs=1)
        if t.click("[data-dkdraw]", wait=1.6): t.cap("06赤を入れる", "この画面で赤を入れる（紙）", "添削の札 →「この画面で書く ✎」", "写真の上に赤・青で書く。太さ3段・ひとつ戻す・ページ送り・返す", layer=True, segs=1)
        t.reload(); t.tab("hw"); t.click("[data-dkcheck]", wait=1.8)
        if t.click("[data-fcmode=face]"): t.cap("07宿題チェック-対面", "宿題チェック（対面で採点。帯をなぞる）", "「対面で採点」", "生徒の ID の行。帯を左右になぞって離したところの数が付く", segs=2)
    # 成績
    t.reload(); t.tab("roster"); t.cap("08成績", "成績（すべてのコース）", "タブ「成績」", "上にコースの札の列、下にコースごとのカード（理解度の推移と分布）", segs=4)
    if t.click("[data-ikcourse]", wait=1.8):
        t.cap("09成績-コース", "成績 → コースのページ", "コースの札を押す", "推移と分布の図／生徒ごとの理解度／個別の宿題／テスト", segs=7)
        if t.click("[data-ikstu]", wait=1.5):
            t.cap("10生徒の紙", "生徒の紙（理解度・根拠・この生徒の宿題）", "コースのページ → 生徒の行", layer=True, segs=3)
            if t.click("[data-iksug]", wait=1.3): t.cap("11提案の紙", "提案の紙（この生徒に足す宿題の提案）", "生徒の紙 →「提案」", layer=True, segs=2)
        t.reload(); t.tab("roster"); t.click("[data-ikcourse]", wait=1.8)
        if t.click("[data-ikstu]", wait=1.5) and t.click("[data-ikrule]", wait=1.3): t.cap("12宿題を変える紙", "この生徒だけ宿題を変える紙", "生徒の紙 →「宿題を変える」", layer=True, segs=3)
        t.reload(); t.tab("roster"); t.click("[data-ikcourse]", wait=1.8)
        if t.click("[data-ikassign]", wait=1.4):
            t.cap("13宿題を足す紙", "宿題を足す紙（プリセットから選んで、まとめて出す）", "コースのページ →「1人に宿題を足す」", layer=True, segs=3)
            if t.click("[data-ikpe-new]", wait=1.0): t.cap("14プリセットを作る", "宿題プリセットを新しく作る", "宿題を足す紙 →「＋ 新しく作る」", layer=True, segs=2)
        t.reload(); t.tab("roster"); t.click("[data-ikcourse]", wait=1.8)
        if t.click("[data-ikimport]", wait=1.4): t.cap("15テストを取り込む紙", "テスト結果を取り込む紙", "コースのページ →「テスト結果を取り込む」", layer=True, segs=2)
    # 導入と進度
    t.reload(); t.tab("progress"); t.cap("16導入と進度", "導入と進度（すべてのコース）", "タブ「導入と進度」", "コースごとの導入の段階（はしご）と、進度・毎日テスト・教材", segs=6)
    if t.click("[data-pgcourse]", wait=1.8):
        t.cap("17進度-コース", "導入と進度 → コースのページ", "コースの札を押す", "授業計画・予定との差・毎日テストの調整・使用教材", segs=8)
    # メニューから行く画面
    t.reload(); t.click("#hMenu"); t.cap("18メニュー", "メニュー", "右上の「･･･」", segs=1)
    t.reload(); t.go("apps"); t.cap("19導入の段階", "導入の段階（コースごとに、紙のまま〜毎日テストまで）", "メニュー →「導入の段階」", segs=4)
    t.go("mats"); t.cap("20教材をえらぶ", "教材をえらぶ", "メニュー →「教材をえらぶ」", segs=3)
    if t.click("#mOpen"): t.cap("21教材を足す", "教材を足す", "教材をえらぶ →「教材を足す」", segs=2)
    t.reload(); t.go("admin"); t.cap("22記録の書き出し", "記録の書き出し", "メニュー →「記録の書き出し」", segs=2)
    t.go("report"); t.cap("23うまく動かないとき", "うまく動かないとき（報告）", "メニュー →「うまく動かないとき」", segs=1)
    t.save("teacher-%s-%s" % (LID, DV))
