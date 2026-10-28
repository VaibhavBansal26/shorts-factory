"""Upload to YouTube via the Data API v3 (OAuth, resumable upload)."""
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .config import ROOT

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
UPLOAD_ONLY = ["https://www.googleapis.com/auth/youtube.upload"]  # the first channel was connected with just this
CLIENT_SECRET = ROOT / "client_secret.json"
TOKEN = ROOT / "token.json"


def _service(token: Path | None = None):
    token = Path(token) if token else TOKEN
    creds = None
    if token.exists():
        creds = Credentials.from_authorized_user_file(token)  # keeps whatever scopes it was granted
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET.exists():
                raise SystemExit(
                    "client_secret.json not found. Create an OAuth 'Desktop app' client in Google Cloud "
                    "(YouTube Data API v3 enabled) and save it next to config.yaml. See README."
                )
            creds = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES).run_local_server(port=0)
        token.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def authorize(token: Path | None = None) -> str:
    """Sign in (opens Google's page) and save the token. Returns the channel title when the grant allows reading it."""
    svc = _service(token)
    try:
        items = svc.channels().list(part="snippet", mine=True).execute().get("items", [])
        return items[0]["snippet"]["title"] if items else ""
    except Exception:  # the first channel's token may only allow uploads
        return ""


def build_metadata(script: dict, cfg: dict) -> dict:
    yt = cfg["youtube"]
    src = script.get("source", {})
    seo = script.get("seo") or {}
    title = (seo.get("title") or script["title"]).strip()
    hashtags = list(seo.get("hashtags") or [])
    hashtags = (hashtags + [t for t in yt["default_hashtags"] if t.lower() not in (h.lower() for h in hashtags)]
                if not hashtags else hashtags)
    if "#shorts" not in (h.lower() for h in hashtags):
        hashtags.append("#Shorts")
    body = (seo.get("description") or script.get("description", "")).strip()
    parts = [body]
    if src.get("url"):
        parts.append(f"Source: {src['title']} — {src['name']}\n{src['url']}")
    if script.get("media_credits"):
        parts.append(f"Clips/images: {', '.join(script['media_credits'])}")
    parts.append("Voiceover is AI-generated. Opinions are my own.")
    parts.append(" ".join(hashtags[:6]))
    tags = [t.lstrip("#") for t in hashtags] + [t for t in seo.get("tags", [])] + script.get("tags", [])
    seen, uniq = set(), []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            uniq.append(t)
    return {
        "snippet": {
            "title": title[:100],
            "description": "\n\n".join(p for p in parts if p)[:4900],
            "tags": uniq[:30],
            "categoryId": yt["category_id"],
        },
        "status": {
            "privacyStatus": yt["privacy"],
            "selfDeclaredMadeForKids": yt["made_for_kids"],
            "containsSyntheticMedia": yt.get("contains_synthetic_media", False),
        },
    }


def upload(video: Path, script: dict, cfg: dict, privacy: str | None = None, token: Path | None = None) -> str:
    from . import seo
    seo.ensure(cfg, script)  # videos made before this feature get their metadata written now
    body = build_metadata(script, cfg)
    if privacy:
        body["status"]["privacyStatus"] = privacy
    req = _service(token).videos().insert(
        part="snippet,status", body=body, media_body=MediaFileUpload(str(video), chunksize=-1, resumable=True)
    )
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  upload {int(status.progress() * 100)}%")
    vid = resp["id"]
    print(f"  uploaded: https://youtube.com/shorts/{vid} ({body['status']['privacyStatus']})")
    return vid
