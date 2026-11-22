# LumenCut ⚡
### AI Stream Highlights Clipper & Automated Social Publisher
> **Turn 2-Hour Livestreams into Viral 9:16 Shorts/Reels & Automatically Post them to Instagram & YouTube on Schedule.**

[![Live Demo](https://img.shields.io/badge/Demo-Live_Website-00f2fe?style=for-the-badge)](index.html)
[![Auto Publisher](https://img.shields.io/badge/Auto_Post-Instagram_%26_YouTube-ff007a?style=for-the-badge)](#)
[![License](https://img.shields.io/badge/License-MIT-00ff87?style=for-the-badge)](LICENSE)

---

## 🌟 What is LumenCut?

**LumenCut** is an all-in-one AI short-form content machine designed for streamers, gamers, and YouTubers. Unlike ordinary clippers that only export video files to your desktop, LumenCut:
1. **Finds Peak Hype Moments:** Scans volume spikes, screaming/laughter reactions, and live chat activity in YouTube, Twitch, and Kick streams.
2. **Auto-Frames to 9:16:** YOLO-based facecam tracker splits screen into facecam (top) and gameplay/screen (bottom).
3. **Animated Captions:** MrBeast / Hormozi bouncing word-by-word subtitles with **Hinglish**, Hindi, and 52+ languages.
4. **Automated Social Publisher:** Connect your YouTube channel and Instagram account, pick a publish date/time, and LumenCut will **automatically upload and publish your clips as YouTube Shorts and Instagram Reels** during your peak audience hours!

---

## 📱 How Auto-Posting Works (Zero Third-Party Cost)

LumenCut uses the official, free developer APIs provided by Google and Meta:

### 1. YouTube Shorts Auto-Publish (YouTube Data API v3)
* Uses OAuth 2.0 to authenticate your YouTube channel.
* Uploads video with title, description, and hashtags (`#Shorts`) directly into your channel as `public` or `unlisted`.
* Allows scheduled publishing via the `publishAt` parameter.

### 2. Instagram Reels Auto-Publish (Meta Instagram Graph API)
* Uses the **Instagram Content Publishing API** for Creator / Business accounts.
* Two-step publishing:
  1. Upload video container (`media_type=REELS`, `video_url`, `caption`).
  2. Publish container (`media_publish`).
* Automatic hashtag placement and reel cover frame selection.

---

## 🚀 Quick Setup & Local Launch

### 1. Launch the Web App & Interactive Console
Simply run the included launcher in Windows:
```bash
# Double-click start_lumencut.bat, or run via terminal:
python server.py
```
Open **[http://localhost:3000](http://localhost:3000)** in your browser.

---

## 📋 How to List & Host LumenCut

1. **Host on GitHub Pages (Free):**
   * Push this `lumencut` directory to GitHub.
   * Go to **Settings > Pages > Deploy from branch `main`**.
   * Your site is live at `https://<username>.github.io/lumencut/`!
2. **Submit to Product Hunt & AI Directories:**
   * Submit to **Product Hunt**, **Toolify.ai**, **Futurepedia**, and **There's An AI For That**.
   * Pitch: *"Free, local alternative to OpusClip that also auto-posts your clips to Instagram & YouTube Shorts."*
3. **Streamer Community Sharing:**
   * Share on Reddit (`r/Streamers`, `r/Twitch`, `r/ContentCreators`) showing how streamers save $30/mo and 4 hours of daily manual posting.

---

## 🎨 Design System & Luxury Aesthetic
- **Theme:** Piano Black Gloss & Luminous Emerald Green (`#00ff87` / `#10b981`)
- **Aesthetic:** Minimalist Luxury (similar to Apple, Linear & Porsche Design)
- **Sheen:** Liquid glass specular highlights with `backdrop-filter: blur(24px)`
- **Typography:** High-contrast crisp Syne (Display) & Plus Jakarta Sans (Body)
- **Complete Walkthrough:** Built-in 5-step "How to Use" guide directly on the homepage.
   * Share on Reddit (`r/Streamers`, `r/Twitch`, `r/ContentCreators`) showing how streamers save $30/mo and 4 hours of daily manual posting.
