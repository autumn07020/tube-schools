# ロンドン校 ―― 在籍クラス・コース・教材台帳

デモと初期投入に使うデータ。読む相手は Claude Code。
出典は担当講師の申告と時間割（2026-09-09〜10）。**設計は `PLAN-宿題と配達.md`。**

> **実在の生徒の氏名・連絡先を入れない**（`SECURITY.md`）。生徒は出席番号だけの架空データにする。
> **ほかの講師の氏名も入れない。** コースの講師欄は、講師アカウントを作ったときにログインIDで入れる。

---

## 0. 決まったこと（回答の記録）

| 問い | 答え | 反映先 |
|---|---|---|
| A1 | 小4国語βの「計算テキスト」は誤り。「漢字とことば」で週10語と文法1ページ（同じ冊子） | 4章 `e4b:japanese` |
| A2 | 基礎力強化プリントは小4・小5の算数だけ | 4章 |
| A3・A4 | 小5算数βの予習シリーズ・演習問題集は小5下 | 1章 |
| A5・B1 | RD特＝土曜の「中3 土特 数学」。同じ教材（上位校の数学 レギュラー）で、苦手や重要な所を講師が毎回選ぶ | 4章 `j3doku:math` |
| A6・B13 | GRIT はアプリで解かせたいが発行元は外部。当面は範囲だけ出す（出すだけ）。予習シリーズ・新中学問題集などは四谷大塚の教材。毎日テストと対策テストには早稲アカ自社の教材が使える | 1章、PLAN 10章 |
| A7 | 小4〜小6に α・β・K、中1〜中3に T・R、中3に選抜の必勝（国数英）。全部の枠を作り、デモには担当講師の分だけ写す | 2・3・5章 |
| A7 | 小1〜小3の J クラス（国数）も枠を作る | 2・3章 |
| A8・B8 | 小5βは月木の週2授業で1回。宿題は月曜にまとめて出し、月曜に見る | 4章 `unit: week` |
| A8・B9 | 中3は各授業で宿題を見る。総復習は5週に1回。中3はこの時期、苦手の解消から過去問（生徒ごとに違う）へ移る | 4章、PLAN 10章 |
| A9・B11・B12・C3 | 受講科目は生徒ごと（国英／国数英／国数／国数英理社）。名簿 CSV の列で入れる。受講している教科だけ宿題と毎日テストを出す。D の生徒も契約していれば平日の合同コマに出る | PLAN 規則2 |
| B1 | 5K 算数は無くなった。土特の時刻は枠の位置（16:00〜17:10）が正しい | 3・4章 |
| B2・C1 | S＝小学生、O＝オンライン。オンラインは時差の大きい生徒向けで宿題あり。オンラインだけに在籍するわけではない（土特の生徒や、その曜日だけ学校と重なる生徒も出る） | 3章（指名のコース） |
| B3 | 小3 の J には理科・社会もある | 3章 |
| B4 | 理科・社会などは各学年の K・D・R・T・α・β 合同（小学生の英語 4S・5S・6S も同じ扱いにした） | 3章 |
| B5 | 火曜16:40 のコマは 5S 英語 | 3章 |
| B6 | 中3 に D は無く、代わりに土特 | 2・3章 |
| B7 | 早慶必勝・小6難プロは塾内テストで優秀だった生徒だけ。土特と特別講座は生徒・保護者・講師の了承で参加 | 3章（指名） |
| B10・C4 | 漢字とことばは採点する（当面は人の手で ◎○△✕）。計算テキスト・計算ピラミッド・漢字練習帳は当面「出すだけ」。生徒は解き直して写真で出し、講師が4段階で評価する。苦手の記録は主に毎日テストの正誤で貯め、講師が特筆事項を書けるようにする | 1章、PLAN S12 |
| B14 | 小1〜小3は枠だけ。実在のアカウントは DPIA を直してから | PLAN 10章 |
| C2 | 「中学 数動画」「小学 算動画」も枠に入れる（担当講師の画面で見られるように） | 3章 |
| C5 | ID は2章・3章の表で確定。授業の増減や講習で柔軟に足し引きできること | PLAN 2章 CSV |

**時間割の読み取りで確かめたのは、担当講師のコマだけ**（4章）。ほかの講師のコマの曜日・時刻は入れていない（PLAN Q1）。

---

## 1. 教材台帳（`materials.json` の `items`）

`mode` は解く場所、`graded` は採点するか。どちらも教材の性質として持ち、宿題ごとに指定させない。
`subject` と `grades` は必ず入れる ―― 無いと手で出した宿題の教科が決まらず、講師の一覧から消える。

```jsonc
{
 "yos-e4-math":   {"name":"予習シリーズ 小4下 算数",           "subject":"math",     "grades":["e4"], "mode":"paper"},
 "yos-e4-jpn":    {"name":"予習シリーズ 小4下 国語",           "subject":"japanese", "grades":["e4"], "mode":"paper"},
 "yos-e5-math":   {"name":"予習シリーズ 小5下 算数",           "subject":"math",     "grades":["e5"], "mode":"paper"},
 "enshu-e4-math": {"name":"演習問題集 小4下 算数",             "subject":"math",     "grades":["e4"], "mode":"paper"},
 "enshu-e4-jpn":  {"name":"演習問題集 小4下 国語",             "subject":"japanese", "grades":["e4"], "mode":"paper"},
 "enshu-e5-math": {"name":"演習問題集 小5下 算数",             "subject":"math",     "grades":["e5"], "mode":"paper"},
 "keisan-yos":    {"name":"計算テキスト（予習シリーズ）",       "subject":"math",     "grades":["e4","e5"], "mode":"paper", "graded":false},
 "kiso-print":    {"name":"基礎力強化プリント",                "subject":"math",     "grades":["e4","e5"], "mode":"paper"},
 "kanji-kotoba":  {"name":"漢字とことば",                     "subject":"japanese", "grades":["e4"], "mode":"paper"},
 "shin-e6-math":  {"name":"新小学問題集 小6 算数",             "subject":"math",     "grades":["e6"], "mode":"paper"},
 "pyramid":       {"name":"計算ピラミッド",                   "subject":"math",     "grades":["e6"], "mode":"paper", "graded":false},
 "shin-j1-jpn":   {"name":"新中学問題集 中1 国語",             "subject":"japanese", "grades":["j1"], "mode":"paper"},
 "shin-j1-sci":   {"name":"新中学問題集 中1 理科",             "subject":"science",  "grades":["j1"], "mode":"paper"},
 "shin-j2-jpn":   {"name":"新中学問題集 中2 国語",             "subject":"japanese", "grades":["j2"], "mode":"paper"},
 "shin-j2-sci":   {"name":"新中学問題集 中2 理科",             "subject":"science",  "grades":["j2"], "mode":"paper"},
 "shin-j2-math":  {"name":"新中学問題集 中2 数学",             "subject":"math",     "grades":["j2"], "mode":"paper"},
 "enshu-j2-math": {"name":"演習問題集 中2 数学",               "subject":"math",     "grades":["j2"], "mode":"paper"},
 "kanji-note":    {"name":"漢字練習帳",                       "subject":"japanese", "grades":["j1","j2"], "mode":"paper", "graded":false},
 "sirius-j2":     {"name":"Sirius21 中2",                    "subject":"english",  "grades":["j2"], "mode":"paper"},
 "jack21":        {"name":"Jack21",                          "subject":"english",  "grades":["j2"], "mode":"paper"},
 "grit2500":      {"name":"Vocabulary GRIT 2500",            "subject":"english",  "grades":["j1","j2","j3"], "mode":"paper", "graded":false},
 "joui-reg":      {"name":"上位校の数学 レギュラー",           "subject":"math",     "grades":["j3"], "mode":"paper"},
 "joui-adv":      {"name":"上位校の数学 アドバンス",           "subject":"math",     "grades":["j3"], "mode":"paper"},
 "joui-reg-test": {"name":"上位校の数学 レギュラー 確認テスト", "subject":"math",     "grades":["j3"], "mode":"paper"}
}
```

`grit2500` は `mode:"paper"`。アプリの冊子（`manifest.js` の `booklets`）には無い。**アプリ扱いにすると、押した先に中身が無い。**

---

## 2. 在籍クラス（`curriculum.json` の `classes[]`）

生徒の `classId` になるのはこの20件だけ。ID は生徒のログインIDに入るので、**あとから変えない。**

| ID | 名前 | 学年 | | ID | 名前 | 学年 |
|---|---|---|---|---|---|---|
| `e1j` | 小1J | e1 | | `j1t` | 中1T | j1 |
| `e2j` | 小2J | e2 | | `j1r` | 中1R | j1 |
| `e3j` | 小3J | e3 | | `j1d` | 中1D | j1 |
| `e4a` | 小4α | e4 | | `j2t` | 中2T | j2 |
| `e4b` | 小4β | e4 | | `j2r` | 中2R | j2 |
| `e4k` | 小4K | e4 | | `j2d` | 中2D | j2 |
| `e5a` | 小5α | e5 | | `j3t` | 中3T | j3 |
| `e5b` | 小5β | e5 | | `j3r` | 中3R | j3 |
| `e5k` | 小5K | e5 | | | | |
| `e6a` | 小6α | e6 | | | | |
| `e6b` | 小6β | e6 | | | | |
| `e6k` | 小6K | e6 | | | | |

学年は e1〜e3 を足して `e1 e2 e3 e4 e5 e6 j1 j2 j3`。

---

## 3. コース（全部の枠）

鍵は `<ID>:<教科>`。受ける生徒は `classes`（在籍クラス。受講科目で絞る）か、指名（`students`）。
★は担当講師のコース（4章）。ほかは講師・曜日・時刻を空のまま作る。

### 小1〜小3

| 鍵 | 名前 | 受ける生徒 |
|---|---|---|
| `e1j:japanese` `e1j:math` | 小1J 国語・算数 | e1j |
| `e2j:japanese` `e2j:math` | 小2J 国語・算数 | e2j |
| `e3j:japanese` `e3j:math` `e3j:science` `e3j:social` | 小3J 国語・算数・理科・社会 | e3j |

### 小4

| 鍵 | 名前 | 受ける生徒 |
|---|---|---|
| `e4a:japanese` | 小4α 国語 | e4a |
| ★`e4a:math` | 小4α 算数 | e4a |
| ★`e4b:japanese` | 小4β 国語 | e4b |
| `e4b:math` | 小4β 算数 | e4b |
| `e4:english` `e4:science` `e4:social` | 小4 英語・理科・社会 | e4a e4b e4k |
| `e4o:math` | 小4 オンライン 算数 | 指名 |

### 小5

| 鍵 | 名前 | 受ける生徒 |
|---|---|---|
| `e5a:japanese` `e5a:math` | 小5α 国語・算数 | e5a |
| `e5b:japanese` | 小5β 国語 | e5b |
| ★`e5b:math` | 小5β 算数 | e5b |
| `e5k:japanese` | 小5K 国語 | e5k |
| `e5:english` `e5:science` `e5:social` | 小5 英語・理科・社会 | e5a e5b e5k |
| `e5o:japanese` `e5o:social` | 小5 オンライン 国語・社会 | 指名 |

### 小6

| 鍵 | 名前 | 受ける生徒 |
|---|---|---|
| `e6a:japanese` `e6a:math` | 小6α 国語・算数 | e6a |
| `e6b:japanese` `e6b:math` | 小6β 国語・算数 | e6b |
| `e6k:japanese` | 小6K 国語 | e6k |
| ★`e6k:math` | 小6K 算数 | e6k |
| `e6:english` `e6:science` `e6:social` | 小6 英語・理科・社会 | e6a e6b e6k |
| `e6nanpro:japanese` `e6nanpro:math` `e6nanpro:science` `e6nanpro:social` | 小6 難プロ | 指名 |
| `e6doku:japanese` `e6doku:math` | 小6 土特 | 指名 |

### 小学生の特講・動画

| 鍵 | 名前 | 学年 | 受ける生徒 |
|---|---|---|---|
| `e56bunpo:english` | 中受英語 文法特講（5・6年） | e5 e6 | 指名 |
| `e56chobun:english` | 中受英語 長文特講（5・6年） | e5 e6 | 指名 |
| `edoga:math` | 小学 算数動画 | e1〜e6 | 指名 |

### 中1

| 鍵 | 名前 | 受ける生徒 |
|---|---|---|
| `j1t:math` | 中1T 数学 | j1t |
| `j1r:math` | 中1R 数学 | j1r |
| `j1tr:japanese` | 中1TR 国語 | j1t j1r（D は土曜に国語がある） |
| `j1tr:english` | 中1TR 英語 | j1t j1r j1d |
| ★`j1:science` | 中1 理科 | j1t j1r j1d |
| `j1:social` | 中1 社会 | j1t j1r j1d |
| ★`j1d:japanese` | 中1D 国語 | j1d |
| `j1d:math` | 中1D 数学 | j1d |

### 中2

| 鍵 | 名前 | 受ける生徒 |
|---|---|---|
| `j2t:japanese` `j2t:math` | 中2T 国語・数学 | j2t |
| `j2r:japanese` | 中2R 国語 | j2r |
| ★`j2r:math` | 中2R 数学 | j2r |
| ★`j2tr:english` | 中2TR 英語 | j2t j2r j2d |
| ★`j2:science` | 中2 理科 | j2t j2r j2d |
| `j2:social` | 中2 社会 | j2t j2r j2d |
| ★`j2d:japanese` | 中2D 国語 | j2d |
| `j2d:math` | 中2D 数学 | j2d |
| `j2ttoku:math` | 中2T 数学特講 | 指名 |

### 中3

| 鍵 | 名前 | 受ける生徒 |
|---|---|---|
| `j3t:japanese` `j3t:math` `j3t:english` | 中3T 国語・数学・英語 | j3t |
| `j3r:japanese` `j3r:english` | 中3R 国語・英語 | j3r |
| ★`j3r:math` | 中3R 数学 | j3r |
| `j3tr:english` | 中3TR 英語 | j3t j3r |
| `j3:science` `j3:social` | 中3 理科・社会 | j3t j3r |
| ★`j3doku:math` | 中3 土特（RD特） 数学 | 指名 |
| `j3doku:japanese` | 中3 土特 国語 | 指名 |
| `j3sokei:japanese` `j3sokei:math` `j3sokei:english` | 中3 早慶必勝 | 指名 |
| `j3o:english` | 中3 オンライン 英語 | 指名 |

### 中学生の動画

| 鍵 | 名前 | 学年 | 受ける生徒 |
|---|---|---|---|
| `jdoga:math` | 中学 数学動画 | j1〜j3 | 指名 |

---

## 4. 担当講師の12コース（週14コマ）

分量は1回ぶん。p はページ。範囲の番号はデモでは架空に振る。

| 鍵 | 時間 | 1回の単位 | 回ごとの宿題（1行＝1ブロック） | 毎週 | 上乗せ |
|---|---|---|---|---|---|
| `e4a:math` | 水 18:20-19:50 | 授業 | 予習シリーズ 小4下 算数 基本問題 2p `yos-e4-math`／演習問題集 小4下 算数 基本問題＋トレーニング 4p `enshu-e4-math` | 計算テキスト 7p `keisan-yos` | 上位：基礎力強化プリント 4p `kiso-print` |
| `e4b:japanese` | 水 16:40-18:10 | 授業 | 予習シリーズ 小4下 国語 基本問題 2p `yos-e4-jpn`／演習問題集 小4下 国語 基本問題＋トレーニング 4p `enshu-e4-jpn` | 漢字とことば 漢字10語・文法1p `kanji-kotoba`（2件） | ― |
| `e5b:math` | 月 16:40-18:10、木 16:40-18:10 | **週（月曜）** | 予習シリーズ 小5下 算数 基本問題 2p `yos-e5-math`／演習問題集 小5下 算数 基本問題＋トレーニング 4p `enshu-e5-math` | 計算テキスト 7p `keisan-yos` | 上位：基礎力強化プリント 4p `kiso-print` |
| `e6k:math` | 月 18:20-19:20 | 授業 | 新小学問題集 小6 算数 標準問題 2p `shin-e6-math` | 計算ピラミッド 3p `pyramid` | ― |
| `j1:science` | 木 20:40-21:40 | 授業 | 新中学問題集 中1 理科 基本問題＋練習問題 4p `shin-j1-sci` | ― | ― |
| `j1d:japanese` | 土 14:20-15:50 | 授業 | 新中学問題集 中1 国語 大問2 3p `shin-j1-jpn` | 漢字練習帳 50語 `kanji-note` | ― |
| `j2d:japanese` | 土 12:40-14:10 | 授業 | 新中学問題集 中2 国語 大問2 3p `shin-j2-jpn` | 漢字練習帳 50語 `kanji-note` | ― |
| `j2:science` | 月 19:30-20:30 | 授業 | 新中学問題集 中2 理科 基本問題＋練習問題 4p `shin-j2-sci` | ― | ― |
| `j2tr:english` | 火 16:40-18:10 | 授業 | Sirius21 練成問題・発展問題 2〜3p `sirius-j2`／Jack21 練成問題・発展問題 4p `jack21` | GRIT 100単語＋連語25語 `grit2500`（step 125、wrap 2500） | ― |
| `j2r:math` | 火 20:10-21:40 | 授業 | 新中学問題集 中2 数学 4p `shin-j2-math` | ― | 上位：演習問題集 中2 数学 4p `enshu-j2-math` |
| `j3r:math` | 火 18:20-19:50、木 18:20-19:50 | **授業ごと** | 上位校の数学 レギュラー 例題3題（予習） `joui-reg`／アドバンス 1p `joui-adv`／レギュラー 確認テスト 2p `joui-reg-test`（どれも目安） | ― | ― |
| `j3doku:math` | 土 16:00-17:10 | 授業ごと | 上位校の数学 レギュラー 例題（復習。毎回講師が選ぶ） `joui-reg` | ― | ― |

---

## 5. デモ

- 講師アカウントは担当講師1人ぶん。ログイン画面の表示は「講師（12コース）」とし、氏名を出さない
- **ほかのコースは枠だけ**（講師・時間・計画・宿題なし）
- 生徒は架空の出席番号だけ。受講科目は実際のパック（国英／国数英／国数／国数英理社）から選ぶ
- 人数は申告どおり。コースごとに次の人数になるよう、在籍クラスと受講科目を割り振る

| 鍵 | 受ける生徒 | 在籍と受講科目（デモ） |
|---|---|---|
| `e4a:math` | 15名 | e4a 15名 |
| `e4b:japanese` | 15名 | e4b 15名 |
| `e5b:math` | 15名 | e5b 15名 |
| `e6k:math` | 10名 | e6k 10名 |
| `j1:science` | 8名 | j1t 3・j1r 3（国数英理社）、j1d 2（国数英理社） |
| `j1d:japanese` | 5名 | j1d 5名（上の2名＋国数3名） |
| `j2d:japanese` | 3名 | j2d 3名（国数英理社1・国数英2） |
| `j2:science` | 8名 | j2t 2・j2r 5・j2d 1（国数英理社） |
| `j2tr:english` | 20名 | j2t 2・j2r 15（国数英理社5・国数英10）・j2d 3 |
| `j2r:math` | 20名 | j2r 20名（上の15名＋国数5） |
| `j3r:math` | 15名 | j3r 15名 |
| `j3doku:math` | 10名 | j3r-01〜10 を指名 |

上位（extra）はデモでは `e4a:math`・`e5b:math`・`j2r:math` に各3名（架空）。

---

## 6. 著作権（`IP.md` と `CLAUDE.md` の再掲）

ここに並べたのは**教材の名前と、ページの範囲だけ**である。

- **中身を持たない。** 見出し語・訳語・問題文・選択肢を `materials.json` にも `app/content/` にも入れない
- `grit2500` は範囲だけを伝える。GRIT の語の並びや番号をアプリに写さない
- 市販教材のページを PDF 化して配らない

**この線を越えると、システムの前提が変わる。** 越えたくなったら人に聞くこと。
