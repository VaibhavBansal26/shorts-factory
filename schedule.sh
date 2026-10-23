#!/bin/bash
# ./schedule.sh install [hour] [count] | remove
DIR="$(cd "$(dirname "$0")" && pwd)"
TAG="# shorts-factory"
case "$1" in
  install)
    for f in .env client_secret.json token.json; do
      [ -f "$DIR/$f" ] || { echo "Missing $f: finish setup first (see README)"; exit 1; }
    done
    LINE="0 ${2:-9} * * * cd \"$DIR\" && .venv/bin/python main.py run --n ${3:-3} --publish >> data/cron.log 2>&1 $TAG"
    (crontab -l 2>/dev/null | grep -v "$TAG"; echo "$LINE") | crontab -
    echo "Installed: $LINE" ;;
  remove)
    crontab -l 2>/dev/null | grep -v "$TAG" | crontab -
    echo "Removed" ;;
  *) echo "usage: $0 install [hour] [count] | remove" ;;
esac
