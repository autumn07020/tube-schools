#!/bin/sh
# JS の構文検査。node が無い機械でも動くよう JavaScriptCore を使う。
# 括弧の閉じ忘れは目で追えない。**保存したら必ずこれを通す。**
cd "$(dirname "$0")/../.." || exit 1
bad=0
# **app/content も見る。** ここを見ていなかったせいで、生の改行が
# 入った教材ファイルが構文エラーのまま通り抜けた。読み込みは黙って
# 失敗し、その教材だけ「0問」になる ―― 画面には何も出ないので、
# 出題が来ないときにしか気づけない。
for f in app/js/*.js app/tools/*.js app/content/*.js app/content/*/*.js; do
  [ -f "$f" ] || continue
  if osascript -l JavaScript \
       -e "Function(\$.NSString.stringWithContentsOfFileEncodingError('$PWD/$f',4,null).js); 'ok'" \
       >/dev/null 2>&1; then :; else
    echo "構文エラー  $f"
    bad=$((bad+1))
  fi
done
[ "$bad" -eq 0 ] && echo "JS 構文 OK"
exit $bad
