#!/usr/bin/env python3
"""Shorts Factory CLI.

  python main.py sources                      # preview today's candidates
  python main.py run --n 3                    # make 3 videos (no upload)
  python main.py run --n 3 --publish          # make + upload to YouTube
  python main.py run --format research_opinion --n 1
  python main.py run --mock --n 1             # no API key needed: canned script, real voice + render
  python app.py                               # web UI at http://127.0.0.1:8765
  python main.py render examples/meme_titus.json   # render a hand-written script
  python main.py auth                         # one-time YouTube login
  python main.py upload output/<folder>       # upload an already-rendered video
  python main.py music add song.mp3 --mood upbeat    # add background music (moods: calm chill upbeat tense funny any)
  python main.py music list
  python main.py library add clip.mp4 --id sv-pied-piper --kind clip --start 12 --duration 6 \\
        --tags startup,scaling --desc "Founders panic as servers crash" --credit "Silicon Valley (HBO)"
  python main.py library list
"""
import argparse
import json
from pathlib import Path

from src import config


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sources")
    sub.add_parser("auth")
    r = sub.add_parser("run")
    r.add_argument("--n", type=int, default=1)
    r.add_argument("--format")
    r.add_argument("--source", help="only pick items whose source name contains this")
    r.add_argument("--publish", action="store_true")
    r.add_argument("--privacy", choices=["private", "unlisted", "public"])
    r.add_argument("--mock", action="store_true")
    m = sub.add_parser("music")
    m.add_argument("action", choices=["add", "list"])
    m.add_argument("file", nargs="?")
    m.add_argument("--mood", default="any")
    lb = sub.add_parser("library")
    lb.add_argument("action", choices=["add", "list"])
    lb.add_argument("file", nargs="?")
    lb.add_argument("--id")
    lb.add_argument("--kind", choices=["clip", "image", "meme"], default="clip")
    lb.add_argument("--start", type=float, default=0)
    lb.add_argument("--duration", type=float, default=6)
    lb.add_argument("--tags", default="")
    lb.add_argument("--desc", default="")
    lb.add_argument("--credit", default="")
    lb.add_argument("--no-copy", action="store_true", help="reference the file where it is (for big local episode files)")
    lb.add_argument("--series", default="", help="show/film title, shown to Claude and credited")
    sr = sub.add_parser("series")
    sr.add_argument("action", choices=["list", "episode"])
    sr.add_argument("id", nargs="?")
    sr.add_argument("--source")
    rx = sub.add_parser("remix")
    rx.add_argument("clip")
    rx.add_argument("--hint", default="")
    rx.add_argument("--voices", choices=["two", "one"], default="two")
    rx.add_argument("--memes", type=int, default=2)
    rx.add_argument("--music", default="auto", help="auto | none | a track file name from the library")
    rs = sub.add_parser("render")
    rs.add_argument("script", help="script JSON, e.g. examples/meme_titus.json")
    u = sub.add_parser("upload")
    u.add_argument("folder")
    u.add_argument("--privacy", choices=["private", "unlisted", "public"])
    a = ap.parse_args()
    cfg = config.load()

    if a.cmd == "sources":
        from src import sources
        for i in sources.pick(cfg, 15):
            print(f"{i.score:5.2f}  {i.source:24} {i.title[:80]}")
    elif a.cmd == "music":
        from src import music
        if a.action == "add":
            print("added", music.add(cfg, a.file, a.mood))
        else:
            for mood, p in music.tracks(cfg):
                print(f"{mood:8} {p.name}")
    elif a.cmd == "library":
        import shutil
        from src import media
        from src.config import ROOT
        if a.action == "add":
            src = Path(a.file).expanduser()
            dest = ROOT / "assets" / "clips" / src.name
            if a.no_copy:
                dest = src.resolve()
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
            media.add_library({
                "id": a.id or src.stem, "kind": a.kind, "file": str(dest) if a.no_copy else str(dest.relative_to(ROOT)),
                "start": a.start, "duration": a.duration, "tags": [t for t in a.tags.split(",") if t],
                "description": a.desc, "credit": a.credit or a.series, "series": a.series})
            print("added", a.id or src.stem)
        else:
            for i in media.load_library():
                print(f"{i['id']:24} {i.get('kind', 'clip'):6} {i.get('description', '')}")
    elif a.cmd == "remix":
        from src import remix
        remix.make(cfg, a.clip, a.hint, a.voices, a.memes, a.music)
    elif a.cmd == "series":
        from src import series
        if a.action == "list":
            for b in series.list_all():
                print(f"{b['id']:24} {b['title']} · {len(b['episodes'])} episodes")
        else:
            series.make_episode(cfg, a.id, source=a.source)
    elif a.cmd == "render":
        from src import pipeline
        pipeline.render_script(cfg, json.loads(Path(a.script).read_text()))
    elif a.cmd == "auth":
        from src import youtube
        youtube.authorize()
    elif a.cmd == "run":
        from src import pipeline
        pipeline.run(cfg, a.n, a.format, a.publish, a.privacy, a.mock, a.source)
    elif a.cmd == "upload":
        from src import youtube
        folder = Path(a.folder)
        script = json.loads((folder / "script.json").read_text())
        youtube.upload(folder / "video.mp4", script, cfg, a.privacy)


if __name__ == "__main__":
    main()
