document.addEventListener("DOMContentLoaded", () => {
  const $ = (selector) => document.querySelector(selector);
  const apiBase = (window.LUMENCUT_API_URL || (
    ["localhost", "127.0.0.1"].includes(location.hostname) ? location.origin : ""
  )).replace(/\/+$/, "");
  const authKey = "lumencut-admin-basic";
  const loginPanel = $("#admin-panel");
  const statusNotice = $("#setup-status");
  const urlInput = $("#video-url");
  const fileInput = $("#video-file");
  const generateButton = $("#generate-btn");
  const generateLabel = generateButton.querySelector(".btn-text");
  const progressContainer = $("#progress-container");
  const progressFill = $("#progress-bar-fill");
  const progressPercent = $("#progress-percent");
  const progressPhase = $("#progress-phase");
  const clipsList = $("#clips-list");
  const queueGrid = $("#queue-grid");
  const scheduleModal = $("#schedule-modal");
  const modalTitle = $("#modal-clip-title");
  const modalCaption = $("#modal-clip-caption");
  const accounts = { youtube: { connected: false }, instagram: { connected: false } };
  let selectedClip = null;
  let previewUrl = null;
  let selectedSource = "url";
  let jobPollTimer = null;

  function authHeader(credentials = sessionStorage.getItem(authKey)) {
    return credentials ? `Basic ${credentials}` : "";
  }

  async function api(path, options = {}) {
    if (!apiBase) throw new Error("Hosted backend URL is not set in config.js.");
    const headers = new Headers(options.headers || {});
    const authorization = authHeader();
    if (authorization) headers.set("Authorization", authorization);
    if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const response = await fetch(`${apiBase}${path}`, { ...options, headers });
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json")
      ? await response.json()
      : await response.text();
    if (!response.ok) {
      if (response.status === 401) {
        sessionStorage.removeItem(authKey);
        updateLoginState(false);
      }
      const message = typeof payload === "object" && payload ? payload.detail : payload;
      throw new Error(message || `Request failed (${response.status}).`);
    }
    return payload;
  }

  function showToast(message, icon = "ℹ️") {
    $("#toast-msg").textContent = message;
    $(".toast-icon").textContent = icon;
    $("#toast-notice").classList.add("show");
    window.setTimeout(() => $("#toast-notice").classList.remove("show"), 4000);
  }

  function setStatus(message, kind = "info") {
    statusNotice.textContent = message;
    statusNotice.dataset.kind = kind;
  }

  function updateLoginState(isLoggedIn) {
    $("#admin-username").hidden = isLoggedIn;
    $("#admin-password").hidden = isLoggedIn;
    $("#admin-login-submit").hidden = isLoggedIn;
    $("#admin-logout-btn").hidden = !isLoggedIn;
    $("#admin-login-btn").textContent = isLoggedIn ? "Admin Signed In" : "Admin Login";
    loginPanel.classList.toggle("signed-in", isLoggedIn);
    if (isLoggedIn) {
      $("#admin-username").value = "";
      $("#admin-password").value = "";
    }
  }

  async function checkBackend() {
    if (!apiBase) {
      setStatus("Public frontend is online, but no hosted API URL is configured yet. Set window.LUMENCUT_API_URL in config.js after deploying the backend.", "warning");
      $("#admin-login-submit").disabled = true;
      return;
    }
    try {
      const health = await api("/api/status");
      if (!health.ready) {
        setStatus("Backend is reachable but not ready. An administrator must configure login credentials and APP_SECRET on the server.", "warning");
      } else {
        const missing = [];
        if (!health.tools.ffmpeg) missing.push("FFmpeg");
        if (!health.tools.whisper) missing.push("Whisper");
        setStatus(
          missing.length
            ? `Backend setup incomplete: install ${missing.join(" and ")} before processing videos.`
            : "Backend is online. Sign in as administrator to process videos and manage accounts.",
          missing.length ? "warning" : "ready",
        );
      }
    } catch (error) {
      setStatus(`Backend unavailable: ${error.message}`, "error");
    }
  }

  function syncPlatformCheckbox(checkboxId, boxId) {
    const checkbox = $(checkboxId);
    const box = $(boxId);
    if (checkbox.disabled) return;
    checkbox.checked = !checkbox.checked;
    box.classList.toggle("selected", checkbox.checked);
  }

  function renderAccounts(data) {
    for (const platform of ["youtube", "instagram"]) {
      accounts[platform] = data[platform] || { connected: false };
      const isYoutube = platform === "youtube";
      const card = $(isYoutube ? "#yt-channel-card" : "#ig-channel-card");
      const button = $(isYoutube ? "#yt-toggle-btn" : "#ig-toggle-btn");
      const name = $(isYoutube ? "#yt-channel-name" : "#ig-channel-name");
      const state = card.querySelector(".channel-status");
      const connected = accounts[platform].connected;
      card.classList.toggle("connected", connected);
      state.className = connected ? "channel-status status-live" : "channel-status";
      state.textContent = connected ? "● Connected" : "Not connected";
      name.textContent = connected
        ? accounts[platform].name
        : (isYoutube ? "YouTube account" : "Instagram professional account");
      button.textContent = connected ? "Disconnect" : "Connect";
      button.onclick = () => toggleAccount(platform);
    }
  }

  async function toggleAccount(platform) {
    try {
      if (accounts[platform].connected) {
        if (!window.confirm(`Disconnect the ${platform} account from LumenCut?`)) return;
        await api(`/api/accounts/${platform}`, { method: "DELETE" });
        showToast(`${platform} account disconnected.`);
        await refreshAccounts();
        return;
      }
      const result = await api(`/api/oauth/${platform}/start`);
      window.location.assign(result.url);
    } catch (error) {
      showToast(error.message, "⚠️");
    }
  }

  async function refreshAccounts() {
    renderAccounts(await api("/api/accounts"));
  }

  function updateProgress(progress, phase) {
    progressFill.style.width = `${Math.max(0, Math.min(100, progress))}%`;
    progressPercent.textContent = `${progress}%`;
    progressPhase.textContent = phase;
    const stepNumber = progress < 5 ? 1 : progress < 25 ? 2 : progress < 35 ? 3 : progress < 95 ? 4 : 5;
    document.querySelectorAll(".pipeline-steps .step").forEach((step, index) => {
      step.classList.toggle("step-active", index === stepNumber - 1);
      step.classList.toggle("step-done", index < stepNumber - 1);
    });
  }

  async function generateClips() {
    if (!sessionStorage.getItem(authKey)) {
      showToast("Admin sign-in karein pehle.", "🔐");
      loginPanel.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const form = new FormData();
    if (selectedSource === "file") {
      if (!fileInput.files || !fileInput.files[0]) {
        showToast("Pehle video file select karein.", "⚠️");
        fileInput.click();
        return;
      }
      form.append("file", fileInput.files[0]);
    } else {
      const sourceUrl = urlInput.value.trim();
      if (!sourceUrl) {
        showToast("Video URL paste karein.", "⚠️");
        urlInput.focus();
        return;
      }
      form.append("source_url", sourceUrl);
    }
    form.append("language", $("#language-select").value);
    form.append("layout", $("#layout-mode").value);
    form.append("caption_style", $("#caption-style").value);
    generateButton.disabled = true;
    generateLabel.textContent = "Uploading…";
    progressContainer.style.display = "block";
    updateProgress(1, "Sending video to the backend");
    try {
      const job = await api("/api/jobs", { method: "POST", body: form });
      generateLabel.textContent = "Processing…";
      pollJob(job.id);
    } catch (error) {
      generateButton.disabled = false;
      generateLabel.textContent = "Generate Clips";
      updateProgress(0, error.message);
      showToast(error.message, "⚠️");
    }
  }

  function pollJob(jobId) {
    window.clearTimeout(jobPollTimer);
    const poll = async () => {
      try {
        const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
        updateProgress(job.progress || 0, job.phase || job.status);
        if (job.status === "completed") {
          updateProgress(100, "Clips ready");
          document.querySelectorAll(".pipeline-steps .step").forEach((step) => step.classList.add("step-done"));
          generateButton.disabled = false;
          generateLabel.textContent = "Generate Clips";
          renderClips(job.clips || []);
          showToast(`${job.clips.length} real clip(s) ready.`, "✅");
          $("#results-dashboard").scrollIntoView({ behavior: "smooth", block: "start" });
          return;
        }
        if (job.status === "failed") {
          generateButton.disabled = false;
          generateLabel.textContent = "Generate Clips";
          updateProgress(job.progress || 0, `Processing failed: ${job.error || "Unknown error"}`);
          showToast(job.error || "Video processing failed.", "⚠️");
          return;
        }
        jobPollTimer = window.setTimeout(poll, 1800);
      } catch (error) {
        generateButton.disabled = false;
        generateLabel.textContent = "Generate Clips";
        updateProgress(0, `Could not read processing status: ${error.message}`);
      }
    };
    poll();
  }

  function makeButton(text, className, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = text;
    button.addEventListener("click", onClick);
    return button;
  }

  async function downloadClip(clip) {
    try {
      const response = await fetch(`${apiBase}${clip.downloadUrl}`, {
        headers: { Authorization: authHeader() },
      });
      if (!response.ok) throw new Error("Could not download this clip.");
      const blobUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = `lumencut-${clip.id}.mp4`;
      link.click();
      URL.revokeObjectURL(blobUrl);
    } catch (error) {
      showToast(error.message, "⚠️");
    }
  }

  async function selectClip(clip, card) {
    selectedClip = clip;
    clipsList.querySelectorAll(".clip-card").forEach((item) => item.classList.remove("active"));
    card.classList.add("active");
    $("#clips-count").textContent = `${clipsList.querySelectorAll(".clip-card").length} Ready`;
    $("#modal-trigger-btn").disabled = false;
    $("#export-single-btn").disabled = false;
    $("#toggle-play-btn").disabled = false;
    const preview = await api(`/api/clips/${encodeURIComponent(clip.id)}/preview`);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = preview.url.startsWith("/") ? `${apiBase}${preview.url}` : preview.url;
    const screen = $("#phone-screen");
    const placeholder = $("#preview-placeholder");
    if (placeholder) placeholder.remove();
    let video = $("#clip-preview-video");
    if (!video) {
      video = document.createElement("video");
      video.id = "clip-preview-video";
      video.className = "clip-preview-video";
      video.controls = true;
      video.playsInline = true;
      screen.prepend(video);
    }
    video.src = previewUrl;
    $("#caption-text").textContent = clip.transcript;
    $("#captions-overlay").style.zIndex = "3";
    $("#toggle-play-btn").textContent = "Play preview";
  }

  function renderClips(clips) {
    clipsList.replaceChildren();
    if (!clips.length) {
      clipsList.innerHTML = '<div class="empty-state">No speech highlights were found.</div>';
      return;
    }
    clips.forEach((clip) => {
      const card = document.createElement("div");
      card.className = "clip-card";
      const thumb = document.createElement("div");
      thumb.className = "clip-thumb";
      const background = document.createElement("div");
      background.className = "thumb-preview";
      const score = document.createElement("span");
      score.className = "virality-score";
      score.textContent = `${clip.score}/100`;
      const duration = document.createElement("span");
      duration.className = "duration-badge";
      duration.textContent = `${Math.floor(clip.duration / 60)}:${String(clip.duration % 60).padStart(2, "0")}`;
      thumb.append(background, score, duration);

      const details = document.createElement("div");
      details.className = "clip-details";
      const title = document.createElement("h4");
      title.className = "clip-title";
      title.textContent = clip.title;
      const transcript = document.createElement("p");
      transcript.className = "clip-hook";
      transcript.textContent = `Transcript: ${clip.transcript}`;
      const tags = document.createElement("div");
      tags.className = "clip-tags";
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = `${clip.start.toFixed(1)}s – ${clip.end.toFixed(1)}s`;
      tags.append(tag);
      details.append(title, transcript, tags);

      const actions = document.createElement("div");
      actions.className = "clip-actions";
      actions.append(
        makeButton("Schedule", "btn-mini-schedule", () => openScheduleModal(clip)),
        makeButton("Download MP4", "btn-icon", () => downloadClip(clip)),
      );
      card.append(thumb, details, actions);
      card.addEventListener("click", () => selectClip(clip, card).catch((error) => showToast(error.message, "⚠️")));
      actions.querySelector(".btn-mini-schedule").addEventListener("click", (event) => {
        event.stopPropagation();
      });
      actions.querySelector(".btn-icon").addEventListener("click", (event) => {
        event.stopPropagation();
      });
      clipsList.append(card);
    });
    clipsList.querySelector(".clip-card").click();
  }

  function openScheduleModal(clip) {
    if (!sessionStorage.getItem(authKey)) {
      showToast("Admin sign-in karein pehle.", "🔐");
      return;
    }
    selectedClip = clip;
    modalTitle.value = clip.title.slice(0, 100);
    modalCaption.value = clip.transcript;
    $("#modal-yt-check").checked = false;
    $("#modal-ig-check").checked = false;
    $("#modal-yt-check").disabled = !accounts.youtube.connected;
    $("#modal-ig-check").disabled = !accounts.instagram.connected;
    $("#modal-yt-box").classList.remove("selected");
    $("#modal-ig-box").classList.remove("selected");
    $("#modal-yt-box").classList.toggle("disabled", !accounts.youtube.connected);
    $("#modal-ig-box").classList.toggle("disabled", !accounts.instagram.connected);
    $("#modal-yt-box").title = accounts.youtube.connected ? "" : "Connect YouTube before scheduling";
    $("#modal-ig-box").title = accounts.instagram.connected ? "" : "Connect Instagram before scheduling";
    const publishAt = new Date(Date.now() + 10 * 60 * 1000);
    publishAt.setMinutes(Math.ceil(publishAt.getMinutes() / 5) * 5, 0, 0);
    $("#schedule-date").value = [
      publishAt.getFullYear(),
      String(publishAt.getMonth() + 1).padStart(2, "0"),
      String(publishAt.getDate()).padStart(2, "0"),
    ].join("-");
    $("#schedule-time").value = `${String(publishAt.getHours()).padStart(2, "0")}:${String(publishAt.getMinutes()).padStart(2, "0")}`;
    $("#trending-pills-preview").replaceChildren();
    scheduleModal.classList.add("open");
  }

  function renderQueue(items) {
    queueGrid.replaceChildren();
    queueGrid.hidden = false;
    if (!items.length) {
      queueGrid.innerHTML = '<div class="empty-state">No scheduled posts yet.</div>';
      return;
    }
    items.forEach((item) => {
      const card = document.createElement("div");
      card.className = "queue-card";
      const top = document.createElement("div");
      top.className = "queue-top";
      const platform = document.createElement("div");
      platform.className = "target-platforms";
      const pill = document.createElement("span");
      pill.className = `platform-pill ${item.platform === "youtube" ? "pill-yt" : "pill-ig"}`;
      pill.textContent = item.platform === "youtube" ? "▶ YouTube Shorts" : "📸 Instagram Reels";
      platform.append(pill);
      const date = document.createElement("span");
      date.className = "queue-time";
      date.textContent = new Date(item.scheduled_at).toLocaleString();
      top.append(platform, date);
      const title = document.createElement("h4");
      title.className = "queue-title";
      title.textContent = item.title;
      const caption = document.createElement("p");
      caption.className = "queue-caption";
      caption.textContent = item.caption;
      const footer = document.createElement("div");
      footer.className = "queue-footer";
      const status = document.createElement("span");
      status.className = "queue-status-badge";
      status.textContent = item.status;
      footer.append(status);
      if (item.error) {
        const error = document.createElement("span");
        error.className = "queue-error";
        error.textContent = item.error;
        footer.append(error);
      }
      if (item.status === "scheduled") {
        footer.append(makeButton("Cancel", "btn-icon", async () => {
          try {
            await api(`/api/schedules/${encodeURIComponent(item.id)}`, { method: "DELETE" });
            await refreshQueue();
          } catch (error) {
            showToast(error.message, "⚠️");
          }
        }));
      }
      card.append(top, title, caption, footer);
      queueGrid.append(card);
    });
  }

  async function refreshQueue() {
    renderQueue(await api("/api/schedules"));
  }

  async function loadRecentClips() {
    const jobs = await api("/api/jobs");
    const completed = jobs.find((job) => job.status === "completed");
    if (completed) {
      const job = await api(`/api/jobs/${encodeURIComponent(completed.id)}`);
      renderClips(job.clips || []);
    } else {
      clipsList.innerHTML = '<div class="empty-state">Your real clips will appear here after a video is processed.</div>';
    }
  }

  async function loadAdminData() {
    await refreshAccounts();
    await Promise.all([loadRecentClips(), refreshQueue()]);
  }

  async function signIn() {
    const username = $("#admin-username").value;
    const password = $("#admin-password").value;
    if (!username || !password) {
      showToast("Username aur password dono required hain.", "⚠️");
      return;
    }
    const encoded = btoa(unescape(encodeURIComponent(`${username}:${password}`)));
    try {
      await api("/api/auth/check", {
        method: "POST",
        headers: { Authorization: `Basic ${encoded}` },
      });
      sessionStorage.setItem(authKey, encoded);
      updateLoginState(true);
      await loadAdminData();
      setStatus("Admin signed in. Review clips and scheduled posts before publishing.", "ready");
      showToast("Signed in as administrator.", "✅");
    } catch (error) {
      sessionStorage.removeItem(authKey);
      updateLoginState(false);
      showToast(error.message, "⚠️");
    }
  }

  $("#admin-login-btn").addEventListener("click", () => {
    loginPanel.scrollIntoView({ behavior: "smooth", block: "center" });
    $("#admin-username").focus();
  });
  $("#admin-login-submit").addEventListener("click", signIn);
  $("#admin-password").addEventListener("keydown", (event) => {
    if (event.key === "Enter") signIn();
  });
  $("#admin-logout-btn").addEventListener("click", () => {
    sessionStorage.removeItem(authKey);
    updateLoginState(false);
    renderAccounts({ youtube: { connected: false }, instagram: { connected: false } });
    renderQueue([]);
    clipsList.innerHTML = '<div class="empty-state">Sign in to load your clips.</div>';
    setStatus("Signed out. Your password is cleared from this browser tab.", "info");
  });

  $("#nav-connect-btn").addEventListener("click", () => {
    document.querySelector(".social-channels-bar").scrollIntoView({ behavior: "smooth", block: "center" });
  });
  generateButton.addEventListener("click", generateClips);
  $("#clear-btn").addEventListener("click", () => {
    urlInput.value = "";
    urlInput.focus();
  });
  $("#export-single-btn").addEventListener("click", () => selectedClip && downloadClip(selectedClip));
  $("#modal-trigger-btn").addEventListener("click", () => selectedClip && openScheduleModal(selectedClip));
  $("#toggle-play-btn").addEventListener("click", () => {
    const video = $("#clip-preview-video");
    if (!video) return;
    if (video.paused) video.play();
    else video.pause();
    $("#toggle-play-btn").textContent = video.paused ? "Play preview" : "Pause preview";
  });

  document.querySelectorAll(".tab-btn").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      selectedSource = button.dataset.tab;
      const uploading = selectedSource === "upload";
      urlInput.hidden = uploading;
      fileInput.hidden = !uploading;
      $("#clear-btn").hidden = uploading;
      $("#source-help").textContent = uploading
        ? "Upload an MP4, MOV, MKV, WebM, or M4V file. Server upload limit applies."
        : "Supported links: YouTube, Twitch, and Kick. Use only media you own or are authorized to process.";
    });
  });
  $("#modal-yt-box").addEventListener("click", (event) => {
    event.preventDefault();
    syncPlatformCheckbox("#modal-yt-check", "#modal-yt-box");
  });
  $("#modal-ig-box").addEventListener("click", (event) => {
    event.preventDefault();
    syncPlatformCheckbox("#modal-ig-check", "#modal-ig-box");
  });
  $("#generate-hashtags-btn").addEventListener("click", () => {
    if (selectedClip) {
      modalCaption.value = selectedClip.transcript;
      showToast("Transcript copied to caption. Review it before publishing.", "ℹ️");
    }
  });
  $("#modal-close-btn").addEventListener("click", () => scheduleModal.classList.remove("open"));
  $("#modal-cancel-btn").addEventListener("click", () => scheduleModal.classList.remove("open"));
  scheduleModal.addEventListener("click", (event) => {
    if (event.target === scheduleModal) scheduleModal.classList.remove("open");
  });

  $("#confirm-schedule-btn").addEventListener("click", async () => {
    if (!selectedClip) return;
    const selectedPlatforms = [
      ["youtube", $("#modal-yt-check").checked],
      ["instagram", $("#modal-ig-check").checked],
    ].filter(([, selected]) => selected).map(([platform]) => platform);
    if (!selectedPlatforms.length) {
      showToast("Select at least one platform.", "⚠️");
      return;
    }
    if (selectedPlatforms.some((platform) => !accounts[platform].connected)) {
      showToast("Connect each selected account before scheduling.", "⚠️");
      return;
    }
    const localDateTime = new Date(`${$("#schedule-date").value}T${$("#schedule-time").value}`);
    if (!Number.isFinite(localDateTime.getTime()) || localDateTime.getTime() < Date.now() + 120000) {
      showToast("Choose a future date and time at least two minutes from now.", "⚠️");
      return;
    }
    const button = $("#confirm-schedule-btn");
    button.disabled = true;
    const payloadBase = {
      clipId: selectedClip.id,
      title: modalTitle.value.trim(),
      caption: modalCaption.value.trim(),
      scheduledAt: localDateTime.toISOString(),
    };
    if (!payloadBase.title || !payloadBase.caption) {
      button.disabled = false;
      showToast("Title and caption are required.", "⚠️");
      return;
    }
    if (selectedPlatforms.includes("instagram") && payloadBase.caption.length > 2200) {
      button.disabled = false;
      showToast("Instagram caption must be 2,200 characters or fewer.", "⚠️");
      return;
    }
    const outcomes = await Promise.allSettled(selectedPlatforms.map((platform) =>
      api("/api/schedules", {
        method: "POST",
        body: JSON.stringify({ ...payloadBase, platform }),
      })
    ));
    button.disabled = false;
    const succeeded = outcomes.filter((outcome) => outcome.status === "fulfilled").length;
    const failed = outcomes.filter((outcome) => outcome.status === "rejected");
    if (succeeded) {
      scheduleModal.classList.remove("open");
      await refreshQueue();
      $("#scheduler-section").scrollIntoView({ behavior: "smooth" });
      showToast(`${succeeded} post(s) scheduled.`, "✅");
    }
    if (failed.length) showToast(failed.map((outcome) => outcome.reason.message).join(" "), "⚠️");
  });

  $("#admin-logout-btn").hidden = true;
  checkBackend();
  const query = new URLSearchParams(location.search);
  if (query.has("oauth_connected")) showToast(`${query.get("oauth_connected")} account connected.`, "✅");
  if (query.has("oauth_error")) showToast(`${query.get("oauth_error")} authorization failed; check backend setup and platform permissions.`, "⚠️");
  if (query.has("oauth_connected") || query.has("oauth_error")) history.replaceState(null, "", location.pathname);
  if (sessionStorage.getItem(authKey)) {
    updateLoginState(true);
    api("/api/auth/check", { method: "POST" })
      .then(loadAdminData)
    .catch(() => {
      sessionStorage.removeItem(authKey);
      updateLoginState(false);
    });
  } else {
    renderQueue([]);
    clipsList.innerHTML = '<div class="empty-state">Sign in to load your clips.</div>';
  }
});
