# 導入の段階 ―― スロースタート・部分導入のための設計（2026-09-23）

本導入（10日後）の前提は「使う講師だけ、使う教科だけ、使う深さだけ」。
そのためにコースごとの**段階**を作り、講師が自分でワンタッチで決められるようにした。

## 段階
0 紙のまま ／ 1 宿題を出す ／ 2 写真で提出 ／ 3 添削まで ／ 4 毎日テストまで（積み上げ）

## どこで決めるか
講師の「導入と進度」タブの上半分（右上メニュー「導入の段階」からも同じ）。
学年ごとの「まとめて」、教科ごとの「まとめて」、1コースずつ。押した瞬間に保存。何度でも戻せる。出した宿題も評価も消えない。

## どこに効くか
| 誰 | 効くこと |
|---|---|
| 生徒 | 1 未満：教科が出ない。2 未満：「出す」が無く「紙で先生に提出」。4 未満：毎日テストにその教科が出ない |
| 講師 | 2 未満：宿題チェックに「写真は使っていない」の断り。3 未満：添削の札が出ない（紙の取り込みだけ） |
| サーバ | 2 未満は写真を 400 で受けない。3 未満は添削の返却を 400。判定はサーバ（画面の出し分けは判定ではない） |

## 作ったもの
- server/courses.py `use_level` `use_flags`、server/lessons.py `set_use`（`set_app` は段階を保つ）
- server/tube_server.py `PUT /api/lessons/use`、生徒の `useBySubject`、写真・添削の門、`course_use_of`、待ち行列 128
- app/js/ui-teacher.js `adoptBlock` `useSeg` `setCourseUse`（導入と進度・導入の段階）
- app/js/ui-desk.js 添削の札の出し分け、app/js/ui-student.js `useLevelOf` `photoOk` `quizOn`
- app/css/app.css 段階の並び（`.use-seg`）と面のふち
- server/test_use.py（27件）、scripts/check/shots.py（画面）
- デモ：講師2〜4（`OTHER_TEACHERS`・`OTHER_TIMES`）、入口の4人

## 本導入までに（残り）
- [ ] 本番に `sh deploy/更新.sh`（demo-accounts.json が9人になる）
- [ ] 講師4人に「ためしに見る」で触ってもらい、段階の名前と説明の言い回しを直す
- [ ] Safari・Edge の目視（Chrome は shots.py で確認ずみ）
- [ ] 段階 1 のコースを紙で評価したい先生が出たら、宿題チェックへの入口（今日やること以外）を足す
