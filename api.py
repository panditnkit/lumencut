"""Authenticated LumenCut API, OAuth callbacks, and persistent publishing queue."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import json
import os
import secrets
import sqlite3
import threading
import time
import shutil
import importlib.util
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from engine import process_media

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("LUMENCUT_DATA_DIR", str(ROOT / "data"))).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
CLIP_DIR = DATA_DIR / "clips"
DB_PATH = DATA_DIR / "lumencut.sqlite3"
APP_SECRET = os.getenv("APP_SECRET", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "").rstrip("/")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_REDIRECT_URI = os.getenv("META_REDIRECT_URI", "")
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v22.0")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024 * 1024)))
MAX_VIDEO_SECONDS = int(os.getenv("MAX_VIDEO_SECONDS", "7200"))
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
BASIC_AUTH = HTTPBasic(auto_error=False)
SCHEDULER_STARTED = False
WORKER_STOP = threading.Event()

app = FastAPI(title="LumenCut API", version="1.0.0")
logger = logging.getLogger("lumencut")
allowed_origins = [
    item.strip()
    for item in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,https://panditnkit.github.io",
    ).split(",")
    if item.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@contextmanager
def _connect():
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _initialize() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    CLIP_DIR.mkdir(parents=True, exist_ok=True)
    with _connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                phase TEXT NOT NULL,
                error TEXT,
                clips_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS job_inputs (
                job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
                source_path TEXT NOT NULL,
                source_url TEXT,
                language TEXT NOT NULL,
                layout TEXT NOT NULL,
                caption_style TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS clips (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                transcript TEXT NOT NULL,
                start_seconds REAL NOT NULL,
                end_seconds REAL NOT NULL,
                score INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS accounts (
                platform TEXT PRIMARY KEY,
                encrypted_token TEXT NOT NULL,
                account_id TEXT NOT NULL,
                account_name TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS oauth_states (
                state TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS schedules (
                id TEXT PRIMARY KEY,
                clip_id TEXT NOT NULL REFERENCES clips(id),
                platform TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                title TEXT NOT NULL,
                caption TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'scheduled',
                error TEXT,
                remote_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS schedules_due ON schedules(status, scheduled_at);
            """
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_admin(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(BASIC_AUTH)],
) -> str:
    if not ADMIN_USERNAME or len(ADMIN_PASSWORD) < 16:
        raise HTTPException(503, "Configure an admin username and a password of at least 16 characters.")
    if (
        credentials is None
        or not hmac.compare_digest(credentials.username, ADMIN_USERNAME)
        or not hmac.compare_digest(credentials.password, ADMIN_PASSWORD)
    ):
        if len(APP_SECRET) < 32:
            raise HTTPException(503, "Public media signing is not configured.")
        raise HTTPException(
            401,
            "Admin sign-in required.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def _fernet() -> Fernet:
    if len(APP_SECRET) < 32:
        raise HTTPException(503, "Set APP_SECRET to at least 32 characters on the server.")
    key = base64.urlsafe_b64encode(hashlib.sha256(APP_SECRET.encode("utf-8")).digest())
    return Fernet(key)


def _save_account(platform: str, token: dict, account_id: str, name: str, metadata: dict) -> None:
    encrypted = _fernet().encrypt(json.dumps(token).encode("utf-8")).decode("ascii")
    with _connect() as db:
        db.execute(
            """INSERT INTO accounts(platform, encrypted_token, account_id, account_name, metadata_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(platform) DO UPDATE SET encrypted_token=excluded.encrypted_token,
                 account_id=excluded.account_id, account_name=excluded.account_name,
                 metadata_json=excluded.metadata_json, updated_at=excluded.updated_at""",
            (platform, encrypted, account_id, name, json.dumps(metadata), _utc_now()),
        )


def _account_token(platform: str) -> tuple[dict, sqlite3.Row]:
    with _connect() as db:
        row = db.execute("SELECT * FROM accounts WHERE platform=?", (platform,)).fetchone()
    if row is None:
        raise RuntimeError(f"{platform.title()} account is not connected.")
    try:
        token = json.loads(_fernet().decrypt(row["encrypted_token"].encode("ascii")))
    except InvalidToken as exc:
        raise RuntimeError("Stored account credentials cannot be decrypted; reconnect the account.") from exc
    return token, row


def _public_account_rows() -> dict:
    with _connect() as db:
        rows = db.execute("SELECT platform, account_id, account_name, updated_at FROM accounts").fetchall()
    result = {
        "youtube": {"connected": False},
        "instagram": {"connected": False},
    }
    for row in rows:
        result[row["platform"]] = {
            "connected": True,
            "id": row["account_id"],
            "name": row["account_name"],
            "updatedAt": row["updated_at"],
        }
    return result


def _take_oauth_state(state: str, platform: str) -> bool:
    with _connect() as db:
        row = db.execute(
            "SELECT created_at FROM oauth_states WHERE state=? AND platform=?",
            (state, platform),
        ).fetchone()
        if row is None:
            return False
        db.execute("DELETE FROM oauth_states WHERE state=?", (state,))
    return time.time() - row["created_at"] < 600


def _new_oauth_state(platform: str) -> str:
    value = secrets.token_urlsafe(32)
    with _connect() as db:
        db.execute("DELETE FROM oauth_states WHERE created_at < ?", (time.time() - 600,))
        db.execute(
            "INSERT INTO oauth_states(state, platform, created_at) VALUES (?, ?, ?)",
            (value, platform, time.time()),
        )
    return value


def _oauth_config(platform: str) -> tuple[str, str, str]:
    if platform == "youtube":
        config = (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI)
    else:
        config = (META_APP_ID, META_APP_SECRET, META_REDIRECT_URI)
    if not all(config):
        raise HTTPException(503, f"{platform.title()} OAuth is not configured on this server.")
    return config


def _exchange_token(url: str, values: dict, method: str = "post") -> dict:
    response = (
        requests.get(url, params=values, timeout=30)
        if method == "get"
        else requests.post(url, data=values, timeout=30)
    )
    if not response.ok:
        raise RuntimeError(f"OAuth provider rejected the request ({response.status_code}).")
    return response.json()


def _safe_clip(clip: sqlite3.Row) -> dict:
    return {
        "id": clip["id"],
        "jobId": clip["job_id"],
        "title": clip["title"],
        "transcript": clip["transcript"],
        "start": clip["start_seconds"],
        "end": clip["end_seconds"],
        "duration": round(clip["end_seconds"] - clip["start_seconds"]),
        "score": clip["score"],
        "downloadUrl": f"/api/clips/{clip['id']}/file",
    }


def _update_job(job_id: str, **values) -> None:
    columns = ", ".join(f"{key}=?" for key in values)
    with _connect() as db:
        db.execute(
            f"UPDATE jobs SET {columns}, updated_at=? WHERE id=?",
            (*values.values(), _utc_now(), job_id),
        )


def _process_job(
    job_id: str,
    source_path: Path,
    source_name: str,
    language: str,
    layout: str,
    caption_style: str,
    source_url: str | None,
) -> None:
    try:
        if source_url:
            _update_job(job_id, status="processing", progress=2, phase="Downloading the authorized video source")
            import yt_dlp

            def enforce_download_limit(info: dict) -> None:
                downloaded_size = info.get("downloaded_bytes", 0)
                total_size = info.get("total_bytes") or info.get("total_bytes_estimate") or 0
                if max(downloaded_size, total_size) > MAX_UPLOAD_BYTES:
                    raise RuntimeError("Downloaded video exceeds this server's upload limit.")

            download_template = f"{source_path}.%(ext)s"
            options = {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "outtmpl": download_template,
                "noplaylist": True,
                "max_filesize": MAX_UPLOAD_BYTES,
                "progress_hooks": [enforce_download_limit],
            }
            with yt_dlp.YoutubeDL(options) as downloader:
                downloader.download([source_url])
            downloaded = sorted(UPLOAD_DIR.glob(f"{source_path.name}.*"))
            if not downloaded:
                raise RuntimeError("The video downloader did not create an output file.")
            if downloaded[0].stat().st_size > MAX_UPLOAD_BYTES:
                raise RuntimeError("Downloaded video exceeds this server's upload limit.")
            downloaded[0].replace(source_path)
        _update_job(job_id, status="processing", progress=2, phase="Loading media and checking duration")
        rendered = process_media(
            source_path=source_path,
            job_id=job_id,
            output_dir=CLIP_DIR,
            language=language,
            layout=layout,
            caption_style=caption_style,
            max_seconds=MAX_VIDEO_SECONDS,
            update=lambda progress, phase: _update_job(
                job_id, status="processing", progress=progress, phase=phase
            ),
        )
        now = _utc_now()
        with _connect() as db:
            db.execute("DELETE FROM clips WHERE job_id=?", (job_id,))
            for item in rendered:
                db.execute(
                    """INSERT INTO clips(id, job_id, title, transcript, start_seconds, end_seconds,
                       score, file_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item["id"],
                        job_id,
                        item["title"],
                        item["transcript"],
                        item["start"],
                        item["end"],
                        item["score"],
                        item["file_path"],
                        now,
                    ),
                )
            db.execute(
                "UPDATE jobs SET status='completed', progress=100, phase='Clips ready', clips_json=?, updated_at=? WHERE id=?",
                (json.dumps([{k: v for k, v in item.items() if k != "file_path"} for item in rendered]), now, job_id),
            )
    except Exception as exc:
        logger.exception("Video processing failed for job %s", job_id)
        _update_job(job_id, status="failed", phase="Processing failed", error=str(exc)[:1000])
    finally:
        for temp_path in UPLOAD_DIR.glob(f"{source_path.name}*"):
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Could not remove temporary source file")
        with _connect() as db:
            db.execute("DELETE FROM job_inputs WHERE job_id=?", (job_id,))


def _job_worker() -> None:
    while not WORKER_STOP.is_set():
        try:
            with _connect() as db:
                job = db.execute(
                    """SELECT j.id, j.source_name, i.source_path, i.source_url, i.language,
                              i.layout, i.caption_style
                       FROM jobs j JOIN job_inputs i ON i.job_id=j.id
                       WHERE j.status='queued' ORDER BY j.created_at LIMIT 1"""
                ).fetchone()
                if job:
                    started = db.execute(
                        "UPDATE jobs SET status='processing', phase='Starting processor', updated_at=? WHERE id=? AND status='queued'",
                        (_utc_now(), job["id"]),
                    ).rowcount
                else:
                    started = 0
            if started:
                _process_job(
                    job["id"],
                    Path(job["source_path"]),
                    job["source_name"],
                    job["language"],
                    job["layout"],
                    job["caption_style"],
                    job["source_url"],
                )
            else:
                WORKER_STOP.wait(2)
        except Exception:
            logger.exception("LumenCut processing worker iteration failed")
            WORKER_STOP.wait(5)


def _youtube_credentials() -> tuple[Credentials, str]:
    token, account = _account_token("youtube")
    credentials = Credentials.from_authorized_user_info(token, YOUTUBE_SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(GoogleRequest())
        _save_account(
            "youtube",
            json.loads(credentials.to_json()),
            account["account_id"],
            account["account_name"],
            json.loads(account["metadata_json"]),
        )
    return credentials, account["account_id"]


def _publish_youtube(schedule: sqlite3.Row) -> str:
    credentials, _ = _youtube_credentials()
    service = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    media = MediaFileUpload(schedule["file_path"], mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    body = {
        "snippet": {
            "title": schedule["title"][:100],
            "description": schedule["caption"][:5000],
            "categoryId": "22",
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    result = service.videos().insert(part="snippet,status", body=body, media_body=media).execute()
    return result["id"]


def _signed_media_url(clip_id: str, scheduled_at: str, require_public: bool = True) -> str:
    if require_public and (
        not PUBLIC_API_URL
        or not PUBLIC_API_URL.startswith("https://")
    ):
        raise RuntimeError("Set PUBLIC_API_URL to the public HTTPS address of this backend for Instagram publishing.")
    scheduled = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00")).timestamp()
    expires = int(max(time.time() + 3600, scheduled + 86400))
    payload = f"{clip_id}:{expires}".encode("utf-8")
    signature = hmac.new(APP_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"{PUBLIC_API_URL}/api/public/media/{clip_id}?expires={expires}&signature={signature}" if PUBLIC_API_URL else (
        f"/api/public/media/{clip_id}?expires={expires}&signature={signature}"
    )


def _publish_instagram(schedule: sqlite3.Row) -> str:
    token, account = _account_token("instagram")
    metadata = json.loads(account["metadata_json"])
    if token.get("expires_at", 0) < time.time() + 86400:
        refresh = requests.get(
            f"https://graph.facebook.com/{META_GRAPH_VERSION}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "fb_exchange_token": token["access_token"],
            },
            timeout=30,
        )
        if not refresh.ok:
            raise RuntimeError(f"Instagram token refresh failed ({refresh.status_code}).")
        refreshed = refresh.json()
        token = {
            "access_token": refreshed["access_token"],
            "expires_at": int(time.time()) + int(refreshed.get("expires_in", 5_184_000)),
        }
        pages = requests.get(
            f"https://graph.facebook.com/{META_GRAPH_VERSION}/me/accounts",
            params={
                "fields": "id,access_token,instagram_business_account{id}",
                "access_token": token["access_token"],
            },
            timeout=30,
        )
        pages.raise_for_status()
        page = next(
            (
                item for item in pages.json().get("data", [])
                if item.get("id") == metadata.get("page_id")
            ),
            None,
        )
        if not page or not page.get("access_token"):
            raise RuntimeError("Meta no longer returns the connected Facebook Page; reconnect Instagram.")
        token["page_access_token"] = page["access_token"]
        _save_account(
            "instagram",
            token,
            account["account_id"],
            account["account_name"],
            metadata,
        )
    api_token = token.get("page_access_token", token["access_token"])
    media_url = _signed_media_url(schedule["clip_id"], schedule["scheduled_at"])
    base = f"https://graph.facebook.com/{META_GRAPH_VERSION}/{account['account_id']}"
    create = requests.post(
        f"{base}/media",
        data={
            "media_type": "REELS",
            "video_url": media_url,
            "caption": schedule["caption"][:2200],
            "access_token": api_token,
        },
        timeout=60,
    )
    if not create.ok:
        raise RuntimeError(f"Instagram container creation failed ({create.status_code}): {create.text[:400]}")
    container_id = create.json().get("id")
    if not container_id:
        raise RuntimeError("Instagram did not return a media container ID.")
    for _ in range(60):
        status = requests.get(
            f"https://graph.facebook.com/{META_GRAPH_VERSION}/{container_id}",
            params={"fields": "status_code", "access_token": api_token},
            timeout=30,
        )
        if not status.ok:
            raise RuntimeError(f"Instagram processing check failed ({status.status_code}).")
        code = status.json().get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram video processing returned {code}.")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram did not finish processing the Reel in time.")
    publish = requests.post(
        f"https://graph.facebook.com/{META_GRAPH_VERSION}/{account['account_id']}/media_publish",
        data={"creation_id": container_id, "access_token": api_token},
        timeout=60,
    )
    if not publish.ok:
        raise RuntimeError(f"Instagram publish failed ({publish.status_code}): {publish.text[:400]}")
    return publish.json().get("id", container_id)


def _publish_due_schedules() -> None:
    now = _utc_now()
    with _connect() as db:
        due = db.execute(
            """SELECT s.*, c.file_path FROM schedules s JOIN clips c ON c.id=s.clip_id
               WHERE s.status='scheduled' AND s.scheduled_at<=? ORDER BY s.scheduled_at LIMIT 10""",
            (now,),
        ).fetchall()
    for schedule in due:
        with _connect() as db:
            updated = db.execute(
                "UPDATE schedules SET status='publishing', updated_at=? WHERE id=? AND status='scheduled'",
                (_utc_now(), schedule["id"]),
            ).rowcount
        if not updated:
            continue
        try:
            remote_id = (
                _publish_youtube(schedule)
                if schedule["platform"] == "youtube"
                else _publish_instagram(schedule)
            )
            with _connect() as db:
                db.execute(
                    "UPDATE schedules SET status='published', remote_id=?, error=NULL, updated_at=? WHERE id=?",
                    (remote_id, _utc_now(), schedule["id"]),
                )
        except Exception as exc:
            with _connect() as db:
                db.execute(
                    "UPDATE schedules SET status='failed', error=?, updated_at=? WHERE id=?",
                    (str(exc)[:1000], _utc_now(), schedule["id"]),
                )


def _scheduler() -> None:
    while not WORKER_STOP.is_set():
        try:
            _publish_due_schedules()
        except Exception:
            logger.exception("LumenCut scheduler iteration failed")
        WORKER_STOP.wait(20)


@app.on_event("startup")
def startup() -> None:
    global SCHEDULER_STARTED
    _initialize()
    if not SCHEDULER_STARTED:
        WORKER_STOP.clear()
        with _connect() as db:
            interrupted = db.execute(
                """SELECT i.source_path FROM job_inputs i JOIN jobs j ON j.id=i.job_id
                   WHERE j.status='processing'"""
            ).fetchall()
            for item in interrupted:
                stale_path = Path(item["source_path"])
                if stale_path.parent.resolve() == UPLOAD_DIR.resolve():
                    for temp_path in UPLOAD_DIR.glob(f"{stale_path.name}*"):
                        try:
                            temp_path.unlink(missing_ok=True)
                        except OSError:
                            logger.exception("Could not remove interrupted upload")
            db.execute(
                """UPDATE jobs SET status='failed', phase='Worker stopped before completing the job',
                   error='The backend restarted while this job was processing. Submit the video again.',
                   updated_at=? WHERE status='processing'""",
                (_utc_now(),),
            )
            db.execute(
                """DELETE FROM job_inputs WHERE job_id IN
                   (SELECT id FROM jobs WHERE status='failed' AND phase='Worker stopped before completing the job')"""
            )
            db.execute(
                """UPDATE schedules SET status='failed',
                   error='The backend restarted during publishing. Check the platform before retrying.',
                   updated_at=? WHERE status='publishing'""",
                (_utc_now(),),
            )
        threading.Thread(target=_scheduler, name="lumencut-scheduler", daemon=True).start()
        threading.Thread(target=_job_worker, name="lumencut-worker", daemon=True).start()
        SCHEDULER_STARTED = True


@app.on_event("shutdown")
def shutdown() -> None:
    global SCHEDULER_STARTED
    WORKER_STOP.set()
    SCHEDULER_STARTED = False


@app.get("/")
def dashboard():
    return FileResponse(ROOT / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "lumencut"}


@app.get("/api/status")
def service_status():
    return {
        "ready": bool(ADMIN_USERNAME and len(ADMIN_PASSWORD) >= 16 and len(APP_SECRET) >= 32),
        "maxUploadBytes": MAX_UPLOAD_BYTES,
        "maxVideoSeconds": MAX_VIDEO_SECONDS,
        "tools": {
            "ffmpeg": bool(os.getenv("FFMPEG_PATH")) or shutil.which("ffmpeg") is not None,
            "whisper": importlib.util.find_spec("faster_whisper") is not None,
        },
        "oauth": {
            "youtube": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI),
            "instagram": bool(META_APP_ID and META_APP_SECRET and META_REDIRECT_URI),
        },
        "publicApiUrl": bool(PUBLIC_API_URL),
    }


@app.post("/api/auth/check")
def auth_check(_: Annotated[str, Depends(_require_admin)]):
    return {"authenticated": True}


@app.get("/api/accounts")
def accounts(_: Annotated[str, Depends(_require_admin)]):
    return _public_account_rows()


@app.get("/api/oauth/{platform}/start")
def oauth_start(platform: str, _: Annotated[str, Depends(_require_admin)]):
    if platform not in ("youtube", "instagram"):
        raise HTTPException(404, "Unsupported platform.")
    client_id, _, redirect_uri = _oauth_config(platform)
    state = _new_oauth_state(platform)
    if platform == "youtube":
        query = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(YOUTUBE_SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
        )
        return {"url": f"https://accounts.google.com/o/oauth2/v2/auth?{query}"}
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement",
            "state": state,
        }
    )
    return {"url": f"https://www.facebook.com/{META_GRAPH_VERSION}/dialog/oauth?{query}"}


@app.get("/api/oauth/youtube/callback")
def youtube_callback(code: str = "", state: str = "", error: str = ""):
    if error or not code or not _take_oauth_state(state, "youtube"):
        return RedirectResponse(f"{FRONTEND_URL}/?oauth_error=youtube")
    _, client_secret, redirect_uri = _oauth_config("youtube")
    try:
        token = _exchange_token(
            "https://oauth2.googleapis.com/token",
            {
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token.update(
            {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": client_secret,
                "scopes": YOUTUBE_SCOPES,
                "expiry": datetime.fromtimestamp(
                    time.time() + int(token.get("expires_in", 3600)), timezone.utc
                ).isoformat(),
            }
        )
        response = requests.get(
            "https://youtube.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true", "access_token": token["access_token"]},
            timeout=30,
        )
        response.raise_for_status()
        channel = response.json().get("items", [])[0]
        _save_account(
            "youtube",
            token,
            channel["id"],
            channel["snippet"].get("title", "YouTube channel"),
            {},
        )
        return RedirectResponse(f"{FRONTEND_URL}/?oauth_connected=youtube")
    except Exception:
        logger.exception("YouTube OAuth callback failed")
        return RedirectResponse(f"{FRONTEND_URL}/?oauth_error=youtube")


@app.get("/api/oauth/instagram/callback")
def instagram_callback(code: str = "", state: str = "", error: str = ""):
    if error or not code or not _take_oauth_state(state, "instagram"):
        return RedirectResponse(f"{FRONTEND_URL}/?oauth_error=instagram")
    _, app_secret, redirect_uri = _oauth_config("instagram")
    try:
        token = _exchange_token(
            f"https://graph.facebook.com/{META_GRAPH_VERSION}/oauth/access_token",
            {
                "client_id": META_APP_ID,
                "client_secret": app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            method="get",
        )
        short_lived_token = token["access_token"]
        long_lived_response = requests.get(
            f"https://graph.facebook.com/{META_GRAPH_VERSION}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": META_APP_ID,
                "client_secret": app_secret,
                "fb_exchange_token": short_lived_token,
            },
            timeout=30,
        )
        long_lived_response.raise_for_status()
        token = long_lived_response.json()
        access_token = token["access_token"]
        response = requests.get(
            f"https://graph.facebook.com/{META_GRAPH_VERSION}/me/accounts",
            params={
                "fields": "id,name,access_token,instagram_business_account{id,username}",
                "access_token": access_token,
            },
            timeout=30,
        )
        response.raise_for_status()
        pages = response.json().get("data", [])
        instagram = next(
            (
                (page, page.get("instagram_business_account"))
                for page in pages
                if page.get("instagram_business_account")
            ),
            None,
        )
        if not instagram:
            raise RuntimeError("No Instagram professional account linked to an authorized Facebook Page.")
        page, ig = instagram
        _save_account(
            "instagram",
            {
                "access_token": access_token,
                "page_access_token": page.get("access_token", access_token),
                "expires_at": int(time.time()) + int(token.get("expires_in", 5_184_000)),
            },
            ig["id"],
            ig.get("username", page.get("name", "Instagram account")),
            {"page_id": page["id"]},
        )
        return RedirectResponse(f"{FRONTEND_URL}/?oauth_connected=instagram")
    except Exception:
        logger.exception("Instagram OAuth callback failed")
        return RedirectResponse(f"{FRONTEND_URL}/?oauth_error=instagram")


@app.delete("/api/accounts/{platform}")
def disconnect_account(platform: str, _: Annotated[str, Depends(_require_admin)]):
    if platform not in ("youtube", "instagram"):
        raise HTTPException(404, "Unsupported platform.")
    with _connect() as db:
        db.execute("DELETE FROM accounts WHERE platform=?", (platform,))
    return {"disconnected": True}


@app.get("/api/jobs")
def list_jobs(_: Annotated[str, Depends(_require_admin)]):
    with _connect() as db:
        rows = db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 25").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/jobs", status_code=202)
async def create_job(
    _: Annotated[str, Depends(_require_admin)],
    file: Annotated[UploadFile | None, File()] = None,
    source_url: Annotated[str | None, Form()] = None,
    language: Annotated[str, Form()] = "auto",
    layout: Annotated[str, Form()] = "crop",
    caption_style: Annotated[str, Form()] = "neon-glow",
):
    if bool(file) == bool(source_url):
        raise HTTPException(400, "Provide one video file or one supported video URL.")
    if language not in {"auto", "en", "hi", "es"}:
        raise HTTPException(400, "Unsupported transcription language.")
    if layout not in {"crop", "blur"}:
        raise HTTPException(400, "Unsupported vertical layout.")
    if caption_style not in {"neon-glow", "hormozi", "cyber-yellow", "minimal"}:
        raise HTTPException(400, "Unsupported caption style.")
    job_id = secrets.token_urlsafe(16)
    source_path = UPLOAD_DIR / f"{job_id}.source"
    source_name = "video"
    if file:
        suffix = Path(file.filename or "video.mp4").suffix.lower()
        if suffix not in {".mp4", ".mov", ".mkv", ".webm", ".m4v"}:
            raise HTTPException(415, "Upload an MP4, MOV, MKV, WebM, or M4V video.")
        source_name = Path(file.filename or "video.mp4").name[:200]
        size = 0
        try:
            with source_path.open("wb") as target:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(413, "Video exceeds this server's upload limit.")
                    target.write(chunk)
        except Exception:
            source_path.unlink(missing_ok=True)
            raise
        if size == 0:
            source_path.unlink(missing_ok=True)
            raise HTTPException(400, "Uploaded video is empty.")
    else:
        source_name = source_url or ""
        if len(source_name) > 2048:
            raise HTTPException(400, "Video URL is too long.")
        try:
            from urllib.parse import urlparse

            parsed = urlparse(source_name)
            host = (parsed.hostname or "").lower()
            allowed = (
                host == "youtu.be"
                or host.endswith(".youtube.com")
                or host == "youtube.com"
                or host == "twitch.tv"
                or host.endswith(".twitch.tv")
                or host == "kick.com"
                or host.endswith(".kick.com")
            )
            if parsed.scheme != "https" or not allowed or parsed.username or parsed.password:
                raise ValueError
        except ValueError as exc:
            raise HTTPException(400, "Only HTTPS YouTube, Twitch, and Kick URLs are supported.") from exc
    now = _utc_now()
    with _connect() as db:
        db.execute(
            "INSERT INTO jobs(id, source_name, status, progress, phase, created_at, updated_at) VALUES (?, ?, 'queued', 0, 'Waiting for processor', ?, ?)",
            (job_id, source_name, now, now),
        )
        db.execute(
            """INSERT INTO job_inputs(job_id, source_path, source_url, language, layout, caption_style)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (job_id, str(source_path), source_url, language, layout, caption_style),
        )
    return {"id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, _: Annotated[str, Depends(_require_admin)]):
    with _connect() as db:
        job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if job is None:
            raise HTTPException(404, "Job not found.")
        clips = db.execute("SELECT * FROM clips WHERE job_id=? ORDER BY score DESC", (job_id,)).fetchall()
    result = dict(job)
    result["clips"] = [_safe_clip(clip) for clip in clips]
    del result["clips_json"]
    return result


@app.get("/api/clips/{clip_id}/file")
def download_clip(clip_id: str, _: Annotated[str, Depends(_require_admin)]):
    with _connect() as db:
        clip = db.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone()
    if clip is None or not Path(clip["file_path"]).is_file():
        raise HTTPException(404, "Clip file not found.")
    return FileResponse(
        clip["file_path"],
        media_type="video/mp4",
        filename=f"lumencut-{clip_id}.mp4",
    )


@app.get("/api/clips/{clip_id}/preview")
def preview_clip(clip_id: str, _: Annotated[str, Depends(_require_admin)]):
    with _connect() as db:
        clip = db.execute("SELECT id, file_path FROM clips WHERE id=?", (clip_id,)).fetchone()
    if clip is None or not Path(clip["file_path"]).is_file():
        raise HTTPException(404, "Clip file not found.")
    if len(APP_SECRET) < 32:
        raise HTTPException(503, "Configure APP_SECRET to sign clip previews.")
    return {
        "url": _signed_media_url(clip_id, _utc_now(), require_public=False),
    }


@app.get("/api/public/media/{clip_id}")
def public_media(
    clip_id: str,
    expires: int = Query(...),
    signature: str = Query(...),
):
    payload = f"{clip_id}:{expires}".encode("utf-8")
    expected = hmac.new(APP_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    if expires < time.time() or not hmac.compare_digest(signature, expected):
        raise HTTPException(403, "Media link is invalid or expired.")
    with _connect() as db:
        clip = db.execute("SELECT file_path FROM clips WHERE id=?", (clip_id,)).fetchone()
    if clip is None or not Path(clip["file_path"]).is_file():
        raise HTTPException(404, "Media not found.")
    return FileResponse(clip["file_path"], media_type="video/mp4")


@app.get("/api/schedules")
def list_schedules(_: Annotated[str, Depends(_require_admin)]):
    with _connect() as db:
        rows = db.execute(
            """SELECT s.*, c.title AS clip_title FROM schedules s
               JOIN clips c ON c.id=s.clip_id ORDER BY s.scheduled_at DESC LIMIT 100"""
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/schedules", status_code=201)
def create_schedule(payload: dict, _: Annotated[str, Depends(_require_admin)]):
    clip_id = str(payload.get("clipId", ""))
    platform = str(payload.get("platform", ""))
    title = str(payload.get("title", "")).strip()
    caption = str(payload.get("caption", "")).strip()
    scheduled_value = str(payload.get("scheduledAt", ""))
    if platform not in {"youtube", "instagram"}:
        raise HTTPException(400, "Choose YouTube or Instagram.")
    if not title or len(title) > 100 or not caption or len(caption) > (2200 if platform == "instagram" else 5000):
        raise HTTPException(400, "Title or caption is empty or too long for the selected platform.")
    try:
        scheduled = datetime.fromisoformat(scheduled_value.replace("Z", "+00:00"))
        if scheduled.tzinfo is None:
            raise ValueError
        scheduled = scheduled.astimezone(timezone.utc)
    except ValueError as exc:
        raise HTTPException(400, "Choose a valid date, time, and timezone.") from exc
    if scheduled.timestamp() < time.time() + 120:
        raise HTTPException(400, "Schedule the post at least two minutes in the future.")
    with _connect() as db:
        clip = db.execute("SELECT id FROM clips WHERE id=?", (clip_id,)).fetchone()
        account = db.execute("SELECT platform FROM accounts WHERE platform=?", (platform,)).fetchone()
    if clip is None:
        raise HTTPException(404, "Clip not found.")
    if account is None:
        raise HTTPException(409, f"Connect your {platform.title()} account before scheduling.")
    if platform == "instagram" and not PUBLIC_API_URL:
        raise HTTPException(503, "Instagram publishing needs the backend's public HTTPS URL.")
    schedule_id = secrets.token_urlsafe(16)
    now = _utc_now()
    with _connect() as db:
        db.execute(
            """INSERT INTO schedules(id, clip_id, platform, scheduled_at, title, caption, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'scheduled', ?, ?)""",
            (schedule_id, clip_id, platform, scheduled.isoformat(), title, caption, now, now),
        )
    return {"id": schedule_id, "status": "scheduled", "scheduledAt": scheduled.isoformat()}


@app.delete("/api/schedules/{schedule_id}")
def cancel_schedule(schedule_id: str, _: Annotated[str, Depends(_require_admin)]):
    with _connect() as db:
        changed = db.execute(
            "UPDATE schedules SET status='cancelled', updated_at=? WHERE id=? AND status='scheduled'",
            (_utc_now(), schedule_id),
        ).rowcount
    if not changed:
        raise HTTPException(409, "This post cannot be cancelled; it may already be publishing or complete.")
    return {"cancelled": True}


app.mount("/", StaticFiles(directory=ROOT), name="static")
