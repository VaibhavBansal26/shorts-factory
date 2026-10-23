#!/bin/sh
# Container start: keep everything that changes (videos, db, music, clips, series memory, YouTube token) on the
# persistent disk mounted at $PERSIST_DIR, then run the web app.
set -e
P="${PERSIST_DIR:-/var/data}"
mkdir -p "$P/output" "$P/data" "$P/music" "$P/cache" "$P/clips" "$P/series"

link() {  # link <app path> <persistent path>
  if [ -d "$1" ] && [ ! -L "$1" ]; then cp -rn "$1"/. "$2"/ 2>/dev/null || true; rm -rf "$1"; fi
  ln -sfn "$2" "$1"
}
link output "$P/output"
link data "$P/data"
link series "$P/series"
link assets/music "$P/music"
link assets/cache "$P/cache"
link assets/clips "$P/clips"
ln -sfn "$P/library.yaml" assets/library.yaml

# YouTube credentials come from environment variables (do the one-time login on your own computer first)
[ -n "$YOUTUBE_CLIENT_SECRET_JSON" ] && printf '%s' "$YOUTUBE_CLIENT_SECRET_JSON" > client_secret.json
if [ -n "$YOUTUBE_TOKEN_JSON" ] && [ ! -f "$P/token.json" ]; then printf '%s' "$YOUTUBE_TOKEN_JSON" > "$P/token.json"; fi
[ -f "$P/token.json" ] && ln -sfn "$P/token.json" token.json

exec gunicorn -w 1 --threads 8 -t 900 -b "0.0.0.0:${PORT:-8765}" app:app
