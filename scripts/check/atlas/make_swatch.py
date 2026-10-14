# -*- coding: utf-8 -*-
"""見本帳（色・面・角・影・文字の実物）を、いまの値そのままで HTML にする。第0巻の先頭に入る。"""
import json, sys
S = sys.argv[1]; A = S + "/atlas"
COL = [("bg", "#EFEFF3", "#000000", "地（ページ）"), ("surface", "#FFFFFF", "#151413", "札・紙の面"), ("surface2", "#ECECF0", "#242220", "一段くぼんだ面"), ("sunk", "#E4E4EA", "#1C1B19", "入力欄・灰のボタン・終わったもの"),
       ("line", "#E3E3E8", "#26231F", "表の罫だけ（区切りには使わない）"), ("text", "#1D1D1F", "#F5F2EE", "本文・見出し"), ("text2", "#6E6E73", "#98928B", "そえ書き"), ("text3", "#A1A1A6", "#5F5A55", "ラベル・注"),
       ("accent", "#005BAC", "#2E86D6", "青：進んでいる・選ばれている・押して先へ"), ("accent-soft", "#E7F0FA", "#0A1B2B", "青の地"), ("accent-dim", "#4A8BC7", "#1F5C94", "青の弱いもの"),
       ("accent2", "#F9B900", "#F9B900", "黄：今日・手を入れる所・達成（ロゴの study と同じ）"), ("accent2-fill", "#FBCF52", "#B88900", "黄の塗り（68% に薄めた）"), ("accent2-soft", "#FDEDBD", "#281E00", "黄の地（26% に薄めた）"),
       ("accent2-text", "#8A5A00", "#F6C13A", "黄の字（白地で読める深さ）"), ("accent2-line", "#EDBE45", "#8A6A12", "黄の線")]
SJ = [("国語", "226,74,108"), ("算数・数学", "0,91,172"), ("理科", "34,150,84"), ("社会", "240,170,0"), ("英語", "0,140,150")]
CARD = "0 0 0 1px rgba(23,21,15,.10)"
BG = "radial-gradient(75% 55% at 6% 0%, rgba(249,185,0,.16) 0%, rgba(249,185,0,0) 62%), radial-gradient(70% 55% at 100% 100%, rgba(0,91,172,.11) 0%, rgba(0,91,172,0) 64%), linear-gradient(#F2F4F8 0%, #F4F3F0 60%, #F6F3EC 100%)"
h = []
h.append("<div class='sheet land' style='padding:26px 34px'><div style='font-size:30px;font-weight:600;letter-spacing:-.03em'>見本帳 ―― いまの TUBE study の色・面・角・影・文字（実物の値。2026-10-04）</div>"
         "<div style='font-size:13px;color:#6e6e73;margin:4px 0 14px'>動いている画面の計算後の値（app/css/app.css の :root）。暗い配色は値だけあり、画面からは選べない。</div>"
         "<div style='display:grid;grid-template-columns:repeat(8,1fr);gap:10px'>")
for n, l, d, use in COL:
    h.append("<div style='font-size:11px;line-height:1.4'><div style='display:flex;height:64px;border-radius:12px;overflow:hidden;box-shadow:0 0 0 1px rgba(0,0,0,.12)'><i style='flex:1;background:%s'></i><i style='flex:1;background:%s'></i></div>"
             "<b style='font-family:ui-monospace,Menlo,monospace'>--%s</b><br>%s ／ <span style='color:#6e6e73'>暗 %s</span><br><span style='color:#444'>%s</span></div>" % (l, d, n, l, d, use))
h.append("</div><div style='display:flex;gap:16px;margin-top:18px'>")
for name, css, use in (("地（body::before）", BG, "左上に黄、右下に青のごく淡い光。札の光の向きと同じ"), ("--tint-blue", "linear-gradient(160deg,#DCE9F9 0%,#FFFFFF 70%)", "進む・押して先へ"),
                       ("--tint-warm", "linear-gradient(160deg,#FFF0C9 0%,#FFF8E8 26%,#FFFFFF 58%)", "手を入れる・祝う"), ("--tint-cool", "linear-gradient(180deg,#FFFFFF 0%,#E9F0F9 100%)", "図の札")):
    h.append("<div style='flex:1;font-size:11px'><div style='height:92px;border-radius:22px;background:%s;box-shadow:%s'></div><b style='font-family:ui-monospace,Menlo,monospace;display:block;margin-top:6px'>%s</b>%s</div>" % (css, CARD, name, use))
for name, rgb in SJ:
    h.append("<div style='flex:.6;font-size:11px'><div style='height:92px;border-radius:22px;background:linear-gradient(150deg, rgba(%s,.20) 0%%, rgba(%s,0) 62%%), #fff;box-shadow:%s'></div><b style='display:block;margin-top:6px'>教科の色：%s</b>rgb(%s) を薄く</div>" % (rgb, rgb, CARD, name, rgb))
h.append("</div><div style='display:flex;gap:26px;margin-top:20px;align-items:flex-end'>")
for r, use in ((6, "小さな札"), (8, "文字だけのボタン"), (10, "回数の丸"), (12, "入力欄"), (14, "ボタン --r"), (16, "行"), (18, "時間割のコマ"), (20, "講師の札 --r-lg"), (22, "札・カード"), (26, "紙"), (999, "カプセル")):
    h.append("<div style='font-size:11px;text-align:center'><div style='width:%dpx;height:76px;background:#fff;border-radius:%dpx;box-shadow:%s'></div>%spx<br><span style='color:#6e6e73'>%s</span></div>" % (150 if r == 999 else 96, r, CARD, r, use))
h.append("</div><div style='margin-top:14px;font-size:12px;color:#444'>画面に実際に出ている角は 14種（999・8・99・14・9・20・22・18・10・12・6・50%・24・16）。影は 17種。</div></div>")
# 2ページ目：文字と部品
h.append("<div class='sheet land' style='padding:26px 34px'><div style='font-size:30px;font-weight:600;letter-spacing:-.03em'>見本帳 ―― 文字・ボタン・影・動き</div><div style='display:flex;gap:40px;margin-top:14px'>"
         "<div style='flex:1.2;font-family:\"Hiragino Sans\",-apple-system,sans-serif'>")
for sz, w, ls, sample, use in ((34, 600, "-.035em", "今日やること", "節の見出し（広い画面）clamp(28px,3vw,34px)/600。左に青→黄の柱"), (26, 600, "-.035em", "今日やること", "節の見出し（iPhone）26/600"), (44, 300, "-.03em", "12", "大きな数字 40〜44/300（細く大きく。tnum）"),
                                (19, 500, "-.01em", "数学", "札の見出し 19/500"), (17, 400, "0", "新中学問題集 国語", "行の題 17/400"), (16, 400, "0", "定理の逆と反例が少し弱いので、その復習をアプリで10問だけ足します。", "本文 16/1.7"),
                                (14, 400, ".01em", "提出する", "ボタンの字 14〜15/400"), (13, 400, "0", "ノートの写真か PDF・6枚まで", "そえ書き 13（--text2）"), (11, 400, ".08em", "今週の宿題", "ラベル 11（--text3・字間 .08em）")):
    h.append("<div style='display:flex;align-items:baseline;gap:16px;margin:0 0 9px'><span style='font-size:%dpx;font-weight:%d;letter-spacing:%s;line-height:1.25;flex:none;max-width:520px'>%s</span><span style='font-size:11px;color:#6e6e73'>%s</span></div>" % (sz, w, ls, sample, use))
h.append("<div style='font-size:12px;color:#444;margin-top:10px;line-height:1.7'>書体は端末のもの（iOS は SF＋ヒラギノ角ゴ、Windows は Yu Gothic UI、Android は Noto Sans JP）。Web フォントは読まない。<br>画面に実際に出ている「大きさ／太さ」の組は <b>59種</b>（大きさだけで 27種。10〜44px、太さ 300〜800）。13px 以下が7割。いちばん多いのは 13/400・12/400・11/400。</div></div>"
         "<div style='flex:1;font-size:12px'>"
         "<div style='display:flex;gap:12px;align-items:center;margin-bottom:14px'><span style='background:#005BAC;color:#fff;border-radius:14px;padding:14px 34px;font-size:15px'>提出する</span><span style='background:#E4E4EA;border-radius:14px;padding:8px 16px;font-size:14px'>やめる</span>"
         "<span style='color:#005BAC;font-size:13px'>宿題を見る →</span><span style='background:#005BAC;color:#fff;border-radius:999px;padding:6px 14px;font-size:13px'>3日</span><span style='background:#E4E4EA;border-radius:999px;padding:6px 14px;font-size:13px'>5日</span>"
         "<span style='background:#FDEDBD;color:#8A5A00;border-radius:999px;padding:3px 10px;font-size:12px'>明日まで 10/5(月)</span><span style='background:#E7F0FA;color:#005BAC;border-radius:999px;padding:3px 10px;font-size:12px'>あと2日</span></div>"
         "<div style='display:flex;gap:16px'><div style='flex:1;height:150px;border-radius:22px;background:#fff;box-shadow:@CARD@;padding:14px 16px'><b>札の影 --card-shadow ＋ --card-hi</b><br>0 0 0 .5px rgba(23,21,15,.07)（髪の毛ほどの縁）, 0 1px 2px rgba(23,21,15,.07)（近い影）, 0 12px 30px -14px rgba(23,21,15,.32)（遠い影）＋ inset 0 1px 0 rgba(255,255,255,.9)（上辺の光）。<b>線は引かない。</b>実物は S01 の札。</div>"
         "<div style='flex:1;height:150px;border-radius:22px;background:#fff;box-shadow:0 0 0 1px rgba(23,21,15,.10);padding:14px 16px'><b>--shadow</b><br>0 1px 2px rgba(23,21,15,.05), 0 8px 24px -12px rgba(23,21,15,.16)。軽い影（古い部品に残る）</div></div>"
         "<div style='margin-top:16px;line-height:1.8'><b>押せる部品の高さ</b>：44px が主（169か所）。44px 未満も 110か所 残っている（40・38・34px が大半）。<br>"
         "<b>間隔</b>：格子の間 18px（--gap）、札の最小幅 300px（--tile）、ページの左右 20px（iPhone）、札の内側 18〜22px。<br>"
         "<b>動き</b>：transform と opacity だけ。主な曲線 cubic-bezier(.2,.8,.2,1)。<br>"
         "　画面の移り変わり＝フェードだけ（前の画面 0.5秒で薄れ、次が 0.7秒で浮かぶ。上下左右には動かさない）<br>"
         "　紙（重なる面）＝拡大しながら出る 0.55秒／縮みながら消える 0.35秒。暗がり 0.5秒／0.35秒<br>"
         "　押した反応＝沈んで戻る 0.45秒（宿題チェックの中だけ付けない）。乗せる反応 0.3秒（6% 大きく）<br>"
         "　ログインのあとの幕＝印が弾む 0.95秒 → 白い輪がほどけて右へ 0.7秒 → 明ける 0.9秒（計 約3秒）<br>"
         "　ようこそ・登録の完了＝印が弾む 1.05秒・輪 0.9秒・文字が1つずつ 0.55秒・点が飛ぶ 1.25秒<br>"
         "　prefers-reduced-motion では全部止める<br>"
         "<b>折り返し</b>：画面の幅ではなく入れ物の幅で決める（@container bento）。主な境目 520・620・840・900px。iPhone でも札は2列。本体の最大幅 1320px（講師の画面は止めない）。紙は 641px 以上で中央に浮かび（680px）、640px 以下で下から全幅。</div></div></div></div>".replace("@CARD@", CARD))
open(A + "/swatch.html", "w", encoding="utf-8").write("".join(h)); print("swatch ok")
