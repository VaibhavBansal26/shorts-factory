"""Upload to YouTube via the Data API v3 (OAuth, resumable upload)."""
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .config import ROOT

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET = ROOT / "client_secret.json"
TOKEN = ROOT / "token.json"


def _service():
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
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
        TOKEN.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def authorize():
    _service()
    print("YouTube authorised; token saved to token.json")


def build_metadata(script: dict, cfg: dict) -> dict:
    yt = cfg["youtube"]
    src = script["source"]
    tags = yt["default_hashtags"]
    title = script["title"]
    if "#Shorts" not in title:
        title = f"{title[:88]} #Shorts"
    desc = (
        f"{script['description']}\n\n"
        f"Source: {src['title']} — {src['name']}\n{src['url']}\n\n"
        + (f"Clips/images: {', '.join(script['media_credits'])}\n\n" if script.get("media_credits") else "")
        + f"Voiceover is AI-generated. Opinions are my own.\n\n{' '.join(tags)}"
    )
    return {
        "snippet": {
            "title": title[:100],
            "description": desc[:4900],
            "tags": [t.lstrip("#") for t in tags] + script.get("tags", []),
            "categoryId": yt["category_id"],
        },
        "status": {
            "privacyStatus": yt["privacy"],
            "selfDeclaredMadeForKids": yt["made_for_kids"],
            "containsSyntheticMedia": yt.get("contains_synthetic_media", False),
        },
    }


def upload(video: Path, script: dict, cfg: dict, privacy: str | None = None) -> str:
    body = build_metadata(script, cfg)
    if privacy:
        body["status"]["privacyStatus"] = privacy
    req = _service().videos().insert(
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
