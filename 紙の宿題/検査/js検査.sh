#!/bin/sh
# 紙の宿題の JS：構文（全部）と、印の読み書き（code.js）を JavaScriptCore で確かめる。node は要らない。
#     sh 紙の宿題/検査/js検査.sh
# jsc は日本語のパスを読めないので、フォルダに入ってから ASCII の相対パスで渡す。
cd "$(dirname "$0")/../web/js" || exit 1
JSC=/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc
bad=0
for f in *.js; do
  if "$JSC" -e "new Function(read('$f'));" >/dev/null 2>&1; then :; else
    echo "構文エラー  $f"; "$JSC" -e "new Function(read('$f'));" 2>&1 | head -3
    bad=$((bad+1))
  fi
done
[ "$bad" -eq 0 ] && echo "JS 構文 OK（$(ls *.js | wc -l | tr -d ' ') ファイル）"
cd ../../検査 || exit 1
out=$("$JSC" ../web/js/code.js code_test.js 2>&1)
echo "$out" | grep "×"
echo "印  $(echo "$out" | tail -1)"
echo "$out" | tail -1 | grep -q "すべて通った" || bad=$((bad+1))
exit $bad
