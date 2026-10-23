#!/usr/bin/env python3
"""Local web UI: create shorts, preview them, deploy to YouTube manually, manage music/clips, schedules.

    python app.py            # http://127.0.0.1:8765

Nothing is published unless you press "Deploy" or create a schedule with auto-deploy turned on.
"""
import json
import os
import shutil
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from src import config, db, formats, media, music, pipeline
from src.config import ROOT

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


def start_job(title: str, fn) -> str:
    jid = uuid.uuid4().hex[:8]
    job = {"id": jid, "title": title, "status": "queued", "log": "", "started": time.time(), "result": None}
    JOBS[jid] = job

    def runner():
        threading.current_thread().job = job
        with JOB_LOCK:
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


def yt_ready() -> bool:
    return (ROOT / "token.json").exists()


def list_videos():
    con = db.connect()
    vids = []
    for d in sorted(OUT.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        sj = d / "script.json"
        if not sj.exists():
            continue
        s = json.loads(sj.read_text())
        row = con.execute("SELECT video_id FROM used WHERE folder=?", (str(d),)).fetchone()
        vids.append({
            "folder": d.name, "title": s["title"], "format": s["format"],
            "label": formats.FORMATS[s["format"]]["label"], "source": s["source"],
            "has_video": (d / "video.mp4").exists(), "video_id": row[0] if row else None,
            "scenes": [{"narration": x["narration"], "visual": (x.get("visual") or {}).get("type", "none")}
                       for x in s["scenes"]],
        })
    return vids


def load_schedules():
    return json.loads(SCHEDULES.read_text()) if SCHEDULES.exists() else []


def save_schedules(items):
    SCHEDULES.parent.mkdir(exist_ok=True)
    SCHEDULES.write_text(json.dumps(items, indent=2))


# ---------- API ----------
@app.get("/api/status")
def status():
    return jsonify(anthropic_key=have_key(), youtube_authorised=yt_ready(),
                   pexels_key=bool(os.getenv("PEXELS_API_KEY")),
                   music_tracks=len(music.tracks(cfg)), library_clips=len(media.load_library()),
                   formats=[{"id": k, "label": v["label"]} for k, v in formats.FORMATS.items()],
                   channel=cfg["channel"]["name"], privacy=cfg["youtube"]["privacy"])


@app.get("/api/videos")
def videos():
    return jsonify(list_videos())


@app.get("/api/jobs")
def jobs():
    return jsonify(sorted(JOBS.values(), key=lambda j: -j["started"])[:10])


@app.post("/api/generate")
def generate():
    b = request.json
    mock = bool(b.get("mock")) or not have_key()
    n = max(1, min(int(b.get("n", 1)), 10))
    fmt = b.get("format") or None
    src = b.get("source") or None
    jid = start_job(f"Generate {n} ({fmt or 'auto'}{', canned script' if mock else ''})",
                    lambda: pipeline.run(cfg, n, fmt, False, None, mock, src))
    return jsonify(job=jid)


@app.post("/api/render-script")
def render_script():
    script = request.json
    for k in ("format", "title", "source", "scenes"):
        if k not in script:
            return jsonify(error=f"missing '{k}'"), 400
    if script["format"] not in formats.FORMATS:
        return jsonify(error="unknown format"), 400
    return jsonify(job=start_job(f"Render '{script['title']}'", lambda: pipeline.render_script(cfg, script)[0].name))


@app.post("/api/publish")
def publish():
    b = request.json
    folder = OUT / secure_filename(b["folder"])
    if not (folder / "video.mp4").exists():
        return jsonify(error="no video"), 404
    if not yt_ready():
        return jsonify(error="YouTube not authorised yet. Run: python main.py auth"), 400

    def go():
        from src import youtube
        script = json.loads((folder / "script.json").read_text())
        vid = youtube.upload(folder / "video.mp4", script, cfg, b.get("privacy") or None)
        db.set_video_id(db.connect(), str(folder), vid)
        return vid

    return jsonify(job=start_job(f"Deploy {folder.name}", go))


@app.delete("/api/videos/<name>")
def delete_video(name):
    d = OUT / secure_filename(name)
    if d.is_dir() and d.parent == OUT:
        shutil.rmtree(d)
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
        "description": form.get("description", ""), "credit": form.get("credit", "")})
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
        time.sleep(20)


@app.get("/")
def index():
    return (ROOT / "ui.html").read_text()


if __name__ == "__main__":
    threading.Thread(target=scheduler_loop, daemon=True).start()
    app.run("127.0.0.1", 8765, threaded=True)
