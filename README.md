# LumenCut

LumenCut turns an authorized video into up to three short vertical clips. It uses open-source Whisper speech recognition for transcripts, ranks speech windows with a simple heuristic, renders 9:16 MP4 files and burned-in captions with FFmpeg, and includes a persistent YouTube/Instagram publishing queue.

**Important:** The existing GitHub Pages site is a static frontend. Real clipping and publishing need this backend on a computer or a separately hosted server. Social account connection works only after Google and Meta developer apps are configured. Never put API secrets or access tokens in `config.js`, frontend code, GitHub Pages, or a chat message.

## What the clipper does (and does not do)

- Accepts MP4, MOV, MKV, WebM, and M4V uploads, or HTTPS YouTube, Twitch, and Kick URLs supported by `yt-dlp`.
- Transcribes speech with `faster-whisper`; first use downloads the configured Whisper model.
- Ranks up to three non-overlapping 45-second speech windows using transcript density, emphasis words, and punctuation. The score is a heuristic, not a virality prediction.
- Creates center-cropped or blurred-background 1080x1920 MP4 clips and burns in the recognized transcript.
- Supports YouTube and Instagram OAuth, reviewable post text, a persistent queue, and scheduled uploads when the backend, accounts, API permissions, and public HTTPS URLs are configured.

LumenCut does not currently detect faces, inspect stream chat, find live trending tags, write creative marketing copy, or guarantee views. Check the transcript, crop, title, caption, and destination before posting. Only process or publish videos you own or have permission to use, and follow each source platform's terms.

## Windows par chalaana

Requirements for the **local AI backend**: Python 3.11 or 3.12 x64, FFmpeg (including `ffprobe` and the `subtitles` filter), aur packages/model download karne ke liye internet. Windows ARM par native ARM Python supported nahi hai; `setup_lumencut.bat` x64 Python launcher (`py -3.11-64` ya `py -3.12-64`) use karne ki koshish karega. Windows x64 emulation par real transcription/rendering smoke-tested hai, lekin speed device par depend karegi. Agar x64 Python installed na ho to dashboard-only mode ke liye hosted backend use karein.

1. `.env.example` ki copy bana kar uska naam `.env` rakhein. Isme apna `ADMIN_USERNAME`, kam-se-kam 16 characters ka unique `ADMIN_PASSWORD`, aur kam-se-kam 32 characters ka random `APP_SECRET` set karein. `.env` private rakhein; GitHub par upload na karein. Random secret banane ke liye PowerShell mein `python -c "import secrets; print(secrets.token_urlsafe(48))"` chala sakte hain.
2. Is folder mein Command Prompt khol kar:

   ```bat
   setup_lumencut.bat
   ```

3. Setup complete hone ke baad `start_lumencut.bat` chalaayein. Browser mein `http://localhost:3000` khulega; `.env` wale admin username/password se sign in karein.
4. Apna video upload karein ya supported HTTPS video link paste karein. Language, vertical layout aur caption style chunein, phir **Generate Clips** dabayein. Pehli baar Whisper model download hoga, isliye processing mein waqt lag sakta hai.
5. Bana hua clip preview ya download karein. Post karne se pehle account connect hona chahiye. Title/caption check karein, platform chunein, future date/time set karein aur confirm karein.

Default processing CPU-intensive hai. `WHISPER_MODEL`, `WHISPER_DEVICE`, ya `WHISPER_COMPUTE_TYPE` tabhi badlein jab server us model/device ko support karta ho. SQLite database aur generated clips `data/` mein hote hain—folder ka backup private jagah rakhein. Upload ke baad source video delete hoti hai; generated clips aur job history rehti hai.

## Admin ke roop mein kaise use karein

1. `start_lumencut.bat` chala kar **Admin Login** mein `.env` ke credentials se sign in karein.
2. Apna/authorized video upload karein. Private ya protected video links supported nahi hain. Uploads aur video links dono ke liye server ki 2 GB file limit lagu hai.
3. Language aur crop/blur layout chunein, phir **Generate Clips** dabayein. Progress backend job ka hai; koi error aaye to wahi screen par dikhega.
4. Clip select karke preview karein ya MP4 download karein. Account connect karne ke baad **Schedule** kholein, title/caption edit karein, platform aur future date/time chunein, phir **Confirm** dabayein. Har platform ka alag queue item banta hai.
5. **Scheduled Posts** mein status dekhein: `scheduled`, `publishing`, `published`, `cancelled`, ya `failed`. Publish shuru hone se pehle scheduled item cancel kiya ja sakta hai. Failed item ka platform error padhein.
6. Kaam ke baad **Sign out** karein. Channel hataane ke liye account card par **Disconnect** dabayein.

Instagram/YouTube connect karne ke liye admin sign-in akela kaafi nahi: neeche Google/Meta developer setup aur unki permissions bhi chahiye.

## Configure YouTube and Instagram

Social credentials belong on the backend, never in the browser or repository.

### YouTube

1. In Google Cloud Console, create/select a project and enable **YouTube Data API v3**.
2. Configure the OAuth consent screen and create an OAuth **Web application** client.
3. Add the exact backend callback URL, for example `https://YOUR-API-HOST/api/oauth/youtube/callback`, to Authorized redirect URIs.
4. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` in the backend secret manager (or private local `.env`).
5. Add the same redirect URL to the Google project, complete any test-user/verification requirements, and check API quota. Videos are uploaded as public when their scheduled time arrives.

### Instagram Reels

1. Use a Meta developer app with Facebook Login and the Instagram Graph API. The Instagram account must be professional (Creator or Business) and linked to a Facebook Page.
2. Request the required `instagram_basic`, `instagram_content_publish`, `pages_show_list`, and `pages_read_engagement` permissions. Meta may require app review/live-mode approval.
3. Add the exact callback `https://YOUR-API-HOST/api/oauth/instagram/callback` to the Meta app.
4. Set `META_APP_ID`, `META_APP_SECRET`, and `META_REDIRECT_URI` only in the backend secret manager.
5. Set `PUBLIC_API_URL` to the backend's public HTTPS origin. Meta must be able to fetch a scheduled clip from the temporary signed media URL at publish time.
6. The Instagram account must remain listed under the connected Facebook user with its page access token. If Meta no longer returns that page during token renewal, reconnect the account before scheduling more posts.

Third-party API quotas, account eligibility, review, hosting, storage, compute, and bandwidth can have limits or costs. A successful OAuth connection is not a guarantee that every post will be accepted.

## Deploy the backend

The included `Dockerfile` and `compose.yaml` are a starting point for a Docker-capable host.

1. Choose a provider that supports persistent disk, sufficient CPU/RAM, long-running background work, and HTTPS. A GPU is optional; CPU transcription is slower.
2. On the host, create `.env` from `.env.example`; set unique admin credentials, a random `APP_SECRET`, Google/Meta secrets, and:
   - `HOST=0.0.0.0`
   - `FRONTEND_URL=https://panditnkit.github.io/lumencut`
   - `PUBLIC_API_URL=https://YOUR-API-HOST`
   - `CORS_ORIGINS=https://panditnkit.github.io`
   - OAuth callback URLs using the same API host
3. Keep the mounted `/app/data` volume persistent and private. The current scheduler and SQLite setup are intended for one backend instance; do not scale it horizontally without moving the queue/database and scheduler to shared services.
4. Build/run with `docker compose up --build -d`. Check `https://YOUR-API-HOST/api/health` and `/api/status`. Put secrets in the provider's secret manager instead of checking `.env` into Git.
5. To connect the GitHub Pages frontend to this backend, set `window.LUMENCUT_API_URL` in `config.js` to the backend origin (for example `https://YOUR-API-HOST`) and deploy the public-safe frontend change. This value is an API address, **not** a credential.

The public frontend currently has no backend URL configured. The published GitHub Pages URL therefore cannot process videos or publish posts until an administrator deploys and configures the backend and updates `config.js`.

## Tests

```bat
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

For production, terminate TLS at the hosting provider, use persistent storage, rotate OAuth credentials if exposed, and keep only the required administrators in control of the backend credentials.
