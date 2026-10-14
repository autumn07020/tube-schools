/* 起動だけ。
   index.html に <script>…</script> と直接書くと、自分で掛けた CSP
   （script-src 'self'）に弾かれる。緩めるのではなく、ファイルに出す。 */
TubeUI.boot();
