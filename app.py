#!/usr/bin/env python3
"""Local web UI: create shorts, preview them, deploy to YouTube manually, manage music/clips, schedules.

    python app.py            # http://127.0.0.1:8765

Nothing is published unless you press "Deploy" or create a schedule with auto-deploy turned on.
"""
import contextlib
import json
import os
import shutil
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from src import channels, config, db, formats, media, music, pipeline, prefs, suggest
from src.config import CODE, ROOT

cfg = config.load()
app = Flask(__name__)
OUT = ROOT / "output"
SCHEDULES = ROOT / "data" / "schedules.json"
JOBS: dict[str, dict] = {}
JOB_LOCK = threading.Lock()  # one render at a time


# ---------- job runner with per-thread log capture ----------
class _Tee:
    def __init__(self, orig):
        self.orig = orig

    def write(self, s):
        job = getattr(threading.current_thread(), "job", None)
        if job is not None:
            job["log"] += s
        return self.orig.write(s)

    def flush(self):
        self.orig.flush()


sys.stdout = _Tee(sys.stdout)


def start_job(title: str, fn, exclusive: bool = True, key: str | None = None) -> str:
    """exclusive jobs (renders) run one at a time; key de-duplicates a job that is already queued or running."""
    if key:
        live = next((j for j in JOBS.values() if j.get("key") == key and j["status"] in ("queued", "running")), None)
        if live:
            return live["id"]
    jid = uuid.uuid4().hex[:8]
    job = {"id": jid, "title": title, "status": "queued", "log": "", "started": time.time(), "result": None, "key": key}
    JOBS[jid] = job

    def runner():
        threading.current_thread().job = job
        with (JOB_LOCK if exclusive else contextlib.nullcontext()):
            if job.get("cancel"):  # closed while still queued
                job["status"] = "failed"
                job["log"] += "cancelled\n"
                return
            job["status"] = "running"
            try:
                job["result"] = fn()
                job["status"] = "done"
            except BaseException as e:  # noqa: BLE001 (SystemExit from youtube auth too)
                print(f"✗ {e}")
                job["status"] = "failed"

    threading.Thread(target=runner, daemon=True).start()
    return jid


# ---------- helpers ----------
def have_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def yt_ready(cid: str | None = None) -> bool:
    return channels.token_path(cid or "main").exists()


def list_videos():
    con = db.connect()
    vids = []
    for d in sorted(OUT.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        sj = d / "script.json"
        if not sj.exists():
            continue
        s = json.loads(sj.read_text())
        vid_id = db.video_id_for(con, str(d))
        vids.append({
            "folder": d.name, "title": s["title"], "format": s["format"], "channel_id": s.get("channel_id", "main"),
            "channel": channels.get(cfg, s.get("channel_id", "main"))["name"],
            "label": formats.FORMATS[s["format"]]["label"], "source": s["source"],
            "has_video": (d / "video.mp4").exists(), "video_id": vid_id,
            "accent": "#%02x%02x%02x" % formats.FORMATS[s["format"]]["accent"], "seo": s.get("seo"),
            "description": s.get("description", ""), "characters": s.get("characters", []),
            "scenes": [{"narration": x["narration"], "subtitle": x.get("subtitle"), "speaker": x.get("speaker"),
                        "headline": x.get("headline", ""), "visual": (x.get("visual") or {}).get("type", "none")}
                       for x in s["scenes"]],
        })
    return vids


def load_schedules():
    return json.loads(SCHEDULES.read_text()) if SCHEDULES.exists() else []


def save_schedules(items):
    SCHEDULES.parent.mkdir(exist_ok=True)
    SCHEDULES.write_text(json.dumps(items, indent=2))


# ---------- password gate (set APP_PASSWORD when the app is reachable from the internet) ----------
@app.before_request
def gate():
    pw = os.getenv("APP_PASSWORD")
    if not pw or request.path == "/healthz":
        return None
    import hmac
    auth = request.authorization
    if auth and hmac.compare_digest((auth.password or "").encode(), pw.encode()):
        return None
    return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="Shorts Factory"'})


@app.get("/healthz")
def healthz():
    return "ok"


# ---------- API ----------
@app.get("/api/status")
def status():
    return jsonify(anthropic_key=have_key(), youtube_authorised=yt_ready(prefs.load()["channel"]),
                   pexels_key=bool(os.getenv("PEXELS_API_KEY")), eleven_key=bool(os.getenv("ELEVENLABS_API_KEY")),
                   music_tracks=len(music.tracks(cfg)), library_clips=len(media.load_library()),
                   formats=[{"id": k, "label": v["label"], "blurb": v.get("blurb", ""), "theme": v.get("theme", "default"),
                             "accent": "#%02x%02x%02x" % v["accent"]} for k, v in formats.FORMATS.items()
                            if not v.get("needs_upload")],
                   logo=cfg["channel"]["logo"], handle=cfg["channel"]["handle"],
                   client_secret=(ROOT / "client_secret.json").exists(), desktop=os.getenv("SF_DESKTOP") == "1",
                   channel=channels.apply(cfg)["channel"]["name"], main_name=cfg["channel"]["name"], main_handle=cfg["channel"]["handle"], privacy=cfg["youtube"]["privacy"],
                   channels=channels.all_channels(cfg), active_channel=prefs.load()["channel"],
                   accent=prefs.load()["accent"], narrator=prefs.load()["narrator"])


@app.get("/api/videos")
def videos():
    return jsonify(list_videos())


@app.post("/api/jobs/<jid>/cancel")
def job_cancel(jid):
    j = JOBS.get(jid)
    if j and j["status"] == "queued":
        j["cancel"] = True
    return jsonify(ok=True)


@app.get("/api/jobs")
def jobs():
    return jsonify(sorted(JOBS.values(), key=lambda j: -j["started"])[:10])


_CAND = {"t": 0, "items": []}


@app.get("/api/candidates")
def candidates():
    if request.args.get("refresh") or time.time() - _CAND["t"] > 600 or not _CAND["items"]:
        from src import sources
        _CAND["items"] = sources.ranked(cfg, 20)
        _CAND["t"] = time.time()
    return jsonify([{"title": i.title, "source": i.source, "url": i.url, "kind": i.kind,
                     "age_days": round((time.time() - i.published) / 86400, 1)} for i in _CAND["items"]])


@app.post("/api/generate")
def generate():
    b = request.json
    jc = channels.apply(cfg)
    mock = bool(b.get("mock")) or not have_key()
    n = max(1, min(int(b.get("n", 1)), 10))
    fmt = b.get("format") or None
    src = b.get("source") or None
    if b.get("url"):  # make a short from one specific item (candidates list or a suggestion)
        item = next((i for i in _CAND["items"] if i.url == b["url"]), None)
        if not item:
            from src.sources import Item
            hit = next((x["item"] for x in suggest.load().get("ideas", []) if x["url"] == b["url"]), None)
            item = Item(**hit) if hit else None
        if not item:
            return jsonify(error="item expired, refresh the list"), 404
        f = formats.pick_format(cfg, fmt)
        return jsonify(job=start_job(f"{f}: {item.title[:50]}",
                                     lambda: pipeline.make_from_item(jc, item, f, mock)[0].name))
    jid = start_job(f"Generate {n} ({fmt or 'auto'}{', canned script' if mock else ''})",
                    lambda: pipeline.run(jc, n, fmt, False, None, mock, src))
    return jsonify(job=jid)


@app.post("/api/remix")
def remix_upload():
    from src import remix
    jc = channels.apply(cfg)
    f = request.files.get("file")
    form = request.form
    if not f:
        return jsonify(error="choose a video file"), 400
    if form.get("rights") != "true":
        return jsonify(error="Please confirm you own this clip or have the rights to use it."), 400
    up = ROOT / "data" / "uploads"
    up.mkdir(parents=True, exist_ok=True)
    dest = up / f"{uuid.uuid4().hex[:6]}_{secure_filename(f.filename)}"
    f.save(dest)
    args = dict(hint=form.get("hint", ""), voices=form.get("voices", "two"),
                memes=max(0, min(int(form.get("memes", 2) or 2), 3)), music=form.get("music", "auto"),
                topic=form.get("topic") or "AI agents, hallucinations and prompting, explained like a friendly argument")
    return jsonify(job=start_job(f"Remix {f.filename}", lambda: remix.make(jc, dest, **args)[0].name))


@app.post("/api/studio/script")
def studio_script():
    from src import studio
    b = request.json or {}
    try:
        return jsonify({**studio.write_script(cfg, b.get("topic", ""), b.get("avoid", "")), "mock": not have_key()})
    except Exception as e:
        return jsonify(error=f"Could not write the script: {e}"), 500


@app.post("/api/studio/build")
def studio_build():
    from src import studio
    jc = channels.apply(cfg)
    f, form = request.files.get("file"), request.form
    if not f:
        return jsonify(error="choose your recording"), 400
    try:
        script = json.loads(form.get("script", ""))
        assert script["beats"]
    except Exception:
        return jsonify(error="write a script first"), 400
    up = ROOT / "data" / "uploads"
    up.mkdir(parents=True, exist_ok=True)
    dest = up / f"{uuid.uuid4().hex[:6]}_{secure_filename(f.filename)}"
    f.save(dest)
    fx = {"left": 0.15, "center": 0.5, "right": 0.85}.get(form.get("face", "center"), 0.5)
    return jsonify(job=start_job(f"Studio: {script.get('title', 'reel')[:40]}",
                                 lambda: studio.make(jc, script, dest, form.get("music", "auto"), fx,
                                                     form.get("bg", "none") if form.get("bg") in ("none", "blur", "studio", "clean") else "none",
                                                     form.get("polish") == "true")[0].name))


@app.get("/api/misc/categories")
def misc_categories():
    from src import misc
    return jsonify([{"id": k, "label": v} for k, v in misc.CATEGORIES.items()])


@app.get("/api/misc/options")
def misc_options():
    from src import misc
    return jsonify(languages=[{"id": k, "label": v} for k, v in misc.LANGUAGES.items()],
                   audiences=[{"id": k, "label": v} for k, v in misc.AUDIENCES.items()])


@app.post("/api/misc/ideas")
def misc_ideas():
    from src import misc
    if not have_key():
        return jsonify(error="Add your Claude API key in Setup to get topic ideas"), 400
    b = request.json or {}
    try:
        return jsonify(misc.ideas(cfg, b.get("category", "general_knowledge"), b.get("avoid", ""),
                                  b.get("language", "en"), b.get("audience", "global")))
    except Exception as e:
        return jsonify(error=f"Could not get ideas: {e}"), 500


@app.post("/api/misc/make")
def misc_make():
    """Faceless (Claude writes it) or, when a video is attached, a dub of your clip in this topic area."""
    from src import misc
    jc = channels.apply(cfg)
    form = request.form if request.files or request.form else (request.json or {})
    category, topic = form.get("category", "general_knowledge"), (form.get("topic") or "").strip()
    language = form.get("language", "en") if form.get("language") in misc.LANGUAGES else "en"
    audience = form.get("audience", "global") if form.get("audience") in misc.AUDIENCES else "global"
    f = request.files.get("file")
    if not have_key():
        return jsonify(error="Misc reels need your Claude API key. Add it in Setup."), 400
    if not f and not topic:
        return jsonify(error="Type a topic or pick one of the ideas"), 400
    if f:
        if form.get("rights") != "true":
            return jsonify(error="Please confirm you own this clip or have the rights to use it."), 400
        up = ROOT / "data" / "uploads"
        up.mkdir(parents=True, exist_ok=True)
        dest = up / f"{uuid.uuid4().hex[:6]}_{secure_filename(f.filename)}"
        f.save(dest)
        args = dict(hint=form.get("hint", ""), voices=form.get("voices", "two"),
                    memes=max(0, min(int(form.get("memes", 2) or 2), 3)), music=form.get("music", "auto"),
                    language=language, audience=audience)
        return jsonify(job=start_job(f"Misc clip: {topic[:40] or f.filename}",
                                     lambda: misc.make_with_clip(jc, dest, category, topic, **args)[0].name))
    return jsonify(job=start_job(f"Misc: {topic[:50]}", lambda: misc.make_faceless(jc, category, topic, language, audience)[0].name))


@app.post("/api/render-script")
def render_script():
    script = request.json
    for k in ("format", "title", "source", "scenes"):
        if k not in script:
            return jsonify(error=f"missing '{k}'"), 400
    if script["format"] not in formats.FORMATS:
        return jsonify(error="unknown format"), 400
    return jsonify(job=start_job(f"Render '{script['title']}'", lambda: pipeline.render_script(channels.apply(cfg), script)[0].name))


@app.post("/api/seo")
def seo_write():
    from src import seo
    if not have_key():
        return jsonify(error="Add your Claude API key in Setup first"), 400
    folder = OUT / secure_filename(request.json["folder"])
    sj = folder / "script.json"
    script = json.loads(sj.read_text())
    try:
        result = seo.ensure(cfg, script, force=True)
    except Exception as e:
        return jsonify(error=str(e)), 500
    if not result:
        return jsonify(error="Could not write metadata, try again"), 500
    sj.write_text(json.dumps(script, indent=2))
    return jsonify(result)


@app.post("/api/publish")
def publish():
    b = request.json
    folder = OUT / secure_filename(b["folder"])
    meta = b.get("meta")
    if meta:  # the owner's edits in the Deploy window win over the generated text
        from src import seo as _seo
        sj = folder / "script.json"
        script = json.loads(sj.read_text())
        old = script.get("seo", {})
        script["seo"] = {"title": meta.get("title") or old.get("title", script["title"]),
                         "description": meta.get("description", old.get("description", "")),
                         "hashtags": _seo.clean_hashtags((meta.get("hashtags") or "").replace(",", " ").split())
                         or old.get("hashtags", []),
                         "tags": old.get("tags", [])}
        sj.write_text(json.dumps(script, indent=2))
    if not (folder / "video.mp4").exists():
        return jsonify(error="no video"), 404
    script0 = json.loads((folder / "script.json").read_text())
    cid = b.get("channel") or script0.get("channel_id") or "main"
    if not yt_ready(cid):
        return jsonify(error=f"“{channels.get(cfg, cid)['name']}” isn't connected to YouTube yet. Connect it in Setup."), 400

    def go():
        from src import youtube
        script = json.loads((folder / "script.json").read_text())
        script["channel_id"] = cid  # remember where it was posted
        (folder / "script.json").write_text(json.dumps(script, indent=2))
        vid = youtube.upload(folder / "video.mp4", script, channels.apply(cfg, cid), b.get("privacy") or None,
                             channels.token_path(cid))
        db.set_video_id(db.connect(), str(folder), vid)
        return vid

    return jsonify(job=start_job(f"Deploy {folder.name}", go))


@app.delete("/api/videos/<name>")
def delete_video(name):
    d = OUT / secure_filename(name)
    if d.is_dir() and d.parent == OUT:
        shutil.rmtree(d)
    return jsonify(ok=True)


@app.get("/thumb/<name>.jpg")
def thumb(name):
    d = OUT / secure_filename(name)
    t = d / "thumb.jpg"
    if not t.exists() and (d / "video.mp4").exists():
        import subprocess
        from src.ff import FFMPEG
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", "1.2", "-i", str(d / "video.mp4"),
                        "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "4", str(t)])
    return send_from_directory(d, "thumb.jpg")


@app.post("/api/open")
def open_local():
    """Desktop only: open a video in the default player or reveal it in Finder."""
    if os.getenv("SF_DESKTOP") != "1":
        return jsonify(error="Only available in the desktop app"), 400
    from src.osopen import open_path
    f = OUT / secure_filename(request.json["folder"]) / "video.mp4"
    open_path(f, bool(request.json.get("reveal")))
    return jsonify(ok=True)


@app.get("/download/<folder>.mp4")
def download(folder):
    """Web: serve the video as an attachment named after its title."""
    d = OUT / secure_filename(folder)
    try:
        name = secure_filename(json.loads((d / "script.json").read_text())["title"]) or folder
    except Exception:
        name = folder
    return send_from_directory(d, "video.mp4", as_attachment=True, download_name=f"{name}.mp4")


@app.post("/api/save")
def save_local():
    """Desktop: the native window ignores download links, so copy the file into ~/Downloads and reveal it."""
    if os.getenv("SF_DESKTOP") != "1":
        return jsonify(error="Only available in the desktop app"), 400
    import subprocess
    folder = secure_filename(request.json["folder"])
    try:
        name = secure_filename(json.loads((OUT / folder / "script.json").read_text())["title"]) or folder
    except Exception:
        name = folder
    dest_dir = Path.home() / "Downloads"
    dest = dest_dir / f"{name}.mp4"
    n = 1
    while dest.exists():
        n += 1
        dest = dest_dir / f"{name}-{n}.mp4"
    shutil.copy2(OUT / folder / "video.mp4", dest)
    from src.osopen import open_path
    open_path(dest, True)
    return jsonify(ok=True, path=str(dest))


@app.get("/api/suggestions")
def suggestions_get():
    s = suggest.load()
    return jsonify(ideas=s.get("ideas", []), generated_at=s.get("generated_at"), frequency=suggest.prefs()["frequency"],
                   stale=suggest.is_stale(), running=suggest.RUNNING.is_set(), has_key=have_key())


@app.post("/api/suggestions/refresh")
def suggestions_refresh():
    if not have_key():
        return jsonify(error="Add your Claude API key in Setup to get suggestions"), 400
    return jsonify(started=suggest.refresh_async(cfg))


@app.post("/api/prefs")
def prefs_set():
    suggest.set_frequency((request.json or {}).get("frequency", "daily"))
    return jsonify(ok=True)


@app.get("/output/<path:p>")
def output_file(p):
    return send_from_directory(OUT, p, conditional=True)


@app.get("/api/music")
def music_list():
    return jsonify([{"mood": m, "name": p.name} for m, p in music.tracks(cfg)])


@app.post("/api/music")
def music_upload():
    f = request.files["file"]
    tmp = ROOT / "data" / secure_filename(f.filename)
    tmp.parent.mkdir(exist_ok=True)
    f.save(tmp)
    try:
        music.add(cfg, str(tmp), request.form.get("mood", "any"))
    finally:
        tmp.unlink(missing_ok=True)
    return jsonify(ok=True)


@app.get("/music/<mood>/<path:name>")
def music_file(mood, name):
    return send_from_directory(Path(music._root(cfg)) / secure_filename(mood), name)


@app.post("/api/music/sigma")
def music_sigma():
    from src import sigma_bgm
    return jsonify(job=start_job("Synthesize sigma BGM", lambda: [p.name for p in sigma_bgm.ensure(cfg)]))


@app.post("/api/settings")
def settings():
    import re
    b = request.json
    text = (ROOT / "config.yaml").read_text()
    for key, val in (("name", b.get("name")), ("handle", b.get("handle"))):
        if val:
            val = val.replace('"', "").strip()
            text = re.sub(rf'^(  {key}: ).*$', lambda m: f'{m.group(1)}"{val}"', text, count=1, flags=re.M)
    (ROOT / "config.yaml").write_text(text)
    cfg.update(config.load())
    return jsonify(ok=True)


def _set_env_file(key: str, value: str):
    """Persist a secret in <data dir>/.env and apply it to the running process."""
    f = ROOT / ".env"
    lines = [l for l in (f.read_text().splitlines() if f.exists() else []) if not l.startswith(key + "=")]
    lines.append(f"{key}={value.strip()}")
    f.write_text("\n".join(lines) + "\n")
    try:
        f.chmod(0o600)
    except OSError:
        pass
    os.environ[key] = value.strip()


@app.post("/api/secrets")
def secrets():
    b = request.json or {}
    for field, env in (("anthropic_key", "ANTHROPIC_API_KEY"), ("pexels_key", "PEXELS_API_KEY"),
                       ("eleven_key", "ELEVENLABS_API_KEY")):
        if b.get(field, "").strip():
            _set_env_file(env, b[field])
    return jsonify(ok=True)


@app.post("/api/youtube/client-secret")
def yt_client_secret():
    f = request.files["file"]
    data = f.read()
    try:
        j = json.loads(data)
        assert "installed" in j or "web" in j
    except Exception:
        return jsonify(error="That doesn't look like a Google OAuth client file (client_secret.json)."), 400
    (ROOT / "client_secret.json").write_bytes(data)
    return jsonify(ok=True)


@app.post("/api/youtube/connect")
def yt_connect():
    """Opens Google's sign-in page in the browser on this computer (desktop app / local use only)."""
    from src import youtube

    cid = (request.json or {}).get("channel") or "main"

    def go():
        title = youtube.authorize(channels.token_path(cid))
        ch = channels.get(cfg, cid)
        if title and cid != "main" and not ch.get("name"):
            channels.update(cid, name=title)
        return f"connected {title}".strip()

    # the sign-in waits for you in the browser, so it must not block renders, and clicking twice reuses the same job
    return jsonify(job=start_job(f"Connect YouTube: {channels.get(cfg, cid)['name']} (finish in the browser window)", go,
                                 exclusive=False, key=f"connect:{cid}"))


@app.post("/api/youtube/web_start")
def yt_web_start():
    from src import youtube
    cid = (request.json or {}).get("channel") or "main"
    try:
        return jsonify(url=youtube.web_start(cid))
    except Exception as e:
        return jsonify(error=str(e)), 400


@app.post("/api/youtube/web_finish")
def yt_web_finish():
    from src import youtube
    d = request.json or {}
    cid = d.get("channel") or "main"
    try:
        title = youtube.web_finish(cid, d.get("url", ""), channels.token_path(cid))
    except Exception as e:
        return jsonify(error=f"Sign-in failed: {e}"), 400
    ch = channels.get(cfg, cid)
    if title and cid != "main" and not ch.get("name"):
        channels.update(cid, name=title)
    return jsonify(ok=True, title=title)


@app.get("/api/voice")
def voice_get():
    return jsonify(prefs.load())


@app.post("/api/voice")
def voice_set():
    return jsonify(prefs.save(**{k: v for k, v in (request.json or {}).items() if k in ("accent", "narrator")}))


@app.get("/api/channels")
def channels_list():
    return jsonify(channels=channels.all_channels(cfg), active=prefs.load()["channel"])


@app.post("/api/channels")
def channels_add():
    b = request.json or {}
    if not (b.get("name") or "").strip():
        return jsonify(error="Give the channel a name"), 400
    return jsonify(channels.add(b["name"], b.get("handle", ""), b.get("about", "")))


@app.post("/api/channels/active")
def channels_active():
    cid = (request.json or {}).get("id", "main")
    if cid not in [c["id"] for c in channels.all_channels(cfg)]:
        return jsonify(error="unknown channel"), 404
    return jsonify(prefs.save(channel=cid))


@app.post("/api/channels/<cid>")
def channels_update(cid):
    b = request.json or {}
    if cid == "main":
        return jsonify(error="Edit the main channel under Channel identity"), 400
    channels.update(cid, name=b.get("name"), handle=b.get("handle"), about=b.get("about"))
    return jsonify(ok=True)


@app.delete("/api/channels/<cid>")
def channels_delete(cid):
    if cid == "main":
        return jsonify(error="The main channel can't be removed"), 400
    channels.remove(cid)
    if prefs.load()["channel"] == cid:
        prefs.save(channel="main")
    return jsonify(ok=True)


@app.post("/api/channels/<cid>/logo")
def channels_logo(cid):
    f = request.files["file"]
    rel = f"assets/logos/{secure_filename(cid)}.png"
    dest = ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    f.save(dest)
    if cid != "main":
        channels.update(cid, logo=rel)
    return jsonify(ok=True)


@app.get("/api/channels/<cid>/logo.png")
def channels_logo_file(cid):
    ch = channels.get(cfg, cid)
    p = ROOT / (ch.get("logo") or cfg["channel"]["logo"])
    return send_from_directory(p.parent, p.name)


@app.post("/api/logo")
def logo():
    f = request.files["file"]
    dest = ROOT / cfg["channel"]["logo"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    f.save(dest)
    return jsonify(ok=True)


@app.get("/logo.png")
def logo_file():
    return send_from_directory(ROOT / Path(cfg["channel"]["logo"]).parent, Path(cfg["channel"]["logo"]).name)


@app.get("/api/library")
def library_list():
    return jsonify(media.load_library())


@app.post("/api/library")
def library_upload():
    f = request.files["file"]
    dest = ROOT / "assets" / "clips" / secure_filename(f.filename)
    dest.parent.mkdir(parents=True, exist_ok=True)
    f.save(dest)
    form = request.form
    media.add_library({
        "id": form.get("id") or dest.stem, "kind": form.get("kind", "clip"), "file": str(dest.relative_to(ROOT)),
        "start": float(form.get("start") or 0), "duration": float(form.get("duration") or 6),
        "tags": [t.strip() for t in form.get("tags", "").split(",") if t.strip()],
        "description": form.get("description", ""), "series": form.get("series", ""),
        "credit": form.get("credit") or form.get("series", "")})
    return jsonify(ok=True)


@app.get("/api/schedules")
def schedules_list():
    return jsonify(load_schedules())


@app.post("/api/schedules")
def schedules_create():
    b = request.json
    item = {
        "id": uuid.uuid4().hex[:6], "name": b.get("name") or "Schedule", "time": b.get("time", "09:00"),
        "days": b.get("days", [0, 1, 2, 3, 4, 5, 6]), "count": int(b.get("count", 3)),
        "formats": b.get("formats") or [], "auto_deploy": bool(b.get("auto_deploy")),
        "privacy": b.get("privacy") or cfg["youtube"]["privacy"], "enabled": True, "last_run": None,
    }
    if item["auto_deploy"] and not yt_ready():
        return jsonify(error="Auto-deploy needs YouTube authorised first (python main.py auth)."), 400
    save_schedules(load_schedules() + [item])
    return jsonify(item)


@app.post("/api/schedules/<sid>/toggle")
def schedules_toggle(sid):
    items = load_schedules()
    for s in items:
        if s["id"] == sid:
            s["enabled"] = not s["enabled"]
    save_schedules(items)
    return jsonify(ok=True)


@app.delete("/api/schedules/<sid>")
def schedules_delete(sid):
    save_schedules([s for s in load_schedules() if s["id"] != sid])
    return jsonify(ok=True)


def scheduler_loop():
    """Only runs while this server is up. Fires each enabled schedule once per day at its time."""
    while True:
        now = datetime.now()
        items = load_schedules()
        changed = False
        for s in items:
            if not s["enabled"] or now.weekday() not in s["days"] or s["last_run"] == str(now.date()):
                continue
            if now.strftime("%H:%M") >= s["time"]:
                s["last_run"], changed = str(now.date()), True
                mock = not have_key()
                start_job(f"Schedule '{s['name']}'", lambda s=s, mock=mock: pipeline.run(
                    cfg, s["count"], None, s["auto_deploy"] and yt_ready(), s["privacy"], mock, None,
                    s["formats"] or None))
        if changed:
            save_schedules(items)
        if have_key() and suggest.is_stale():  # new ideas daily or weekly, whichever the user picked
            suggest.refresh_async(cfg)
        time.sleep(20)


@app.get("/")
def index():
    return (CODE / "ui.html").read_text()


if __name__ != "__main__":  # running under gunicorn
    threading.Thread(target=scheduler_loop, daemon=True).start()

if __name__ == "__main__":
    threading.Thread(target=scheduler_loop, daemon=True).start()
    app.run("127.0.0.1", 8765, threaded=True)
