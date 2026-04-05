const audio = document.getElementById("audioPlayer");
const playPauseBtn = document.getElementById("playPauseBtn");
const playIcon = document.getElementById("playIcon");
const pauseIcon = document.getElementById("pauseIcon");
const rewindBtn = document.getElementById("rewindBtn");
const forwardBtn = document.getElementById("forwardBtn");
const speedBtn = document.getElementById("speedBtn");
const speedLabel = document.getElementById("speedLabel");
const seekBar = document.getElementById("seekBar");
const currentTimeEl = document.getElementById("currentTime");
const durationEl = document.getElementById("duration");
const nowPlaying = document.getElementById("nowPlaying");
const playerTitle = document.getElementById("playerTitle");
const playerCategory = document.getElementById("playerCategory");
const artDay = document.getElementById("artDay");
const artTech = document.getElementById("artTech");
const equalizer = document.getElementById("equalizer");
const episodeList = document.getElementById("episodeList");
const statusBanner = document.getElementById("statusBanner");
const statusText = document.getElementById("statusText");
const urlInput = document.getElementById("urlInput");
const episodeTitleInput = document.getElementById("episodeTitle");
const addUrlsBtn = document.getElementById("addUrlsBtn");
const queueSection = document.getElementById("queueSection");
const queueCount = document.getElementById("queueCount");
const queueList = document.getElementById("queueList");
const generateFromQueue = document.getElementById("generateFromQueue");
const summaryModal = document.getElementById("summaryModal");
const closeSummary = document.getElementById("closeSummary");
const summaryContent = document.getElementById("summaryContent");

const SPEEDS = [0.75, 1, 1.25, 1.5, 1.75, 2];
const HISTORY_TTL_MS = 7 * 24 * 60 * 60 * 1000;
const SAVE_INTERVAL_MS = 3000;
let speedIndex = 1;
let currentEpisode = null;
let pollInterval = null;
let saveProgressTimer = null;
let pendingSeek = null;
let pendingPlay = false;

// ── localStorage helpers (7-day TTL) ──

function historyGet(key) {
  try {
    const raw = localStorage.getItem(`tdp_${key}`);
    if (!raw) return null;
    const obj = JSON.parse(raw);
    if (obj._expires && Date.now() > obj._expires) {
      localStorage.removeItem(`tdp_${key}`);
      return null;
    }
    return obj.value;
  } catch { return null; }
}

function historySet(key, value) {
  try {
    localStorage.setItem(`tdp_${key}`, JSON.stringify({
      value,
      _expires: Date.now() + HISTORY_TTL_MS,
    }));
  } catch { /* quota exceeded */ }
}

function getProgress(filename) {
  const all = historyGet("progress") || {};
  return all[filename] || null;
}

function saveProgress(filename, currentTime, duration) {
  const all = historyGet("progress") || {};
  all[filename] = { t: currentTime, d: duration, at: Date.now() };
  historySet("progress", all);
}

function markListened(filename) {
  const list = historyGet("listened") || [];
  if (!list.includes(filename)) {
    list.push(filename);
    historySet("listened", list);
  }
}

function isListened(filename) {
  return (historyGet("listened") || []).includes(filename);
}

function cacheEpisodes(episodes) {
  historySet("episodes_cache", episodes);
}

function getCachedEpisodes() {
  return historyGet("episodes_cache") || [];
}

function saveLastPlaying(ep) {
  historySet("last_playing", { filename: ep.filename, technology: ep.technology, day_number: ep.day_number });
}

function getLastPlaying() {
  return historyGet("last_playing");
}

// ── Formatting ──

function formatTime(s) {
  if (!s || isNaN(s)) return "0:00";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function progressPercent(filename) {
  const p = getProgress(filename);
  if (!p || !p.d) return 0;
  return Math.round((p.t / p.d) * 100);
}

// ── Player ──

function playEpisode(ep) {
  currentEpisode = ep;
  saveLastPlaying(ep);
  nowPlaying.classList.remove("hidden");
  playerTitle.textContent = ep.technology;
  playerCategory.textContent = `Episode ${ep.day_number}`;
  artDay.textContent = `Episode ${ep.day_number}`;
  artTech.textContent = ep.technology;
  document.getElementById("artBg").style.background =
    "linear-gradient(135deg, #1a4f3a 0%, #0f172a 100%)";
  document.querySelectorAll(".episode-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.filename === ep.filename);
  });

  statusBanner.classList.add("hidden");

  const saved = getProgress(ep.filename);
  pendingSeek = (saved && saved.t > 5) ? saved.t : null;
  pendingPlay = true;

  audio.src = `/audio/${ep.filename}`;
  audio.load();

  if (saveProgressTimer) clearInterval(saveProgressTimer);
  saveProgressTimer = setInterval(() => {
    if (currentEpisode && audio.duration && !audio.paused) {
      saveProgress(currentEpisode.filename, audio.currentTime, audio.duration);
    }
  }, SAVE_INTERVAL_MS);

  if ("mediaSession" in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: ep.technology, artist: "Tech Deep Dive", album: `Episode ${ep.day_number}`,
    });
    navigator.mediaSession.setActionHandler("play", () => audio.play());
    navigator.mediaSession.setActionHandler("pause", () => audio.pause());
    navigator.mediaSession.setActionHandler("seekbackward", () => { audio.currentTime = Math.max(0, audio.currentTime - 15); });
    navigator.mediaSession.setActionHandler("seekforward", () => { audio.currentTime += 30; });
  }
}

function loadEpisodeWithoutPlaying(ep) {
  currentEpisode = ep;
  nowPlaying.classList.remove("hidden");
  playerTitle.textContent = ep.technology;
  playerCategory.textContent = `Episode ${ep.day_number}`;
  artDay.textContent = `Episode ${ep.day_number}`;
  artTech.textContent = ep.technology;
  document.getElementById("artBg").style.background =
    "linear-gradient(135deg, #1a4f3a 0%, #0f172a 100%)";

  const saved = getProgress(ep.filename);
  pendingSeek = (saved && saved.t > 5) ? saved.t : null;
  pendingPlay = false;

  audio.src = `/audio/${ep.filename}`;
  audio.load();
}

audio.addEventListener("loadedmetadata", () => {
  durationEl.textContent = formatTime(audio.duration);

  if (pendingSeek !== null && audio.duration) {
    audio.currentTime = Math.min(pendingSeek, audio.duration - 1);
    pendingSeek = null;
  }

  if (pendingPlay) {
    pendingPlay = false;
    const p = audio.play();
    if (p !== undefined) {
      p.catch((err) => {
        console.warn("Auto-play blocked, tap play to start:", err.message);
      });
    }
  }
});

audio.addEventListener("error", () => {
  const err = audio.error;
  const codes = { 1: "Aborted", 2: "Network error", 3: "Decode error", 4: "Source not supported" };
  const msg = codes[err?.code] || "Unknown audio error";
  console.error("Audio error:", msg, err);

  let userMsg = `Audio error: ${msg}.`;
  if (currentEpisode && currentEpisode._cached) {
    userMsg = "This episode's audio is no longer on the server (it was cleared on restart). Generate it again or use the download if you saved it.";
  } else {
    userMsg += " Try downloading the file instead.";
  }
  statusBanner.classList.remove("hidden");
  statusBanner.classList.add("error");
  statusText.textContent = userMsg;
});

audio.addEventListener("ended", () => {
  if (currentEpisode) {
    markListened(currentEpisode.filename);
    saveProgress(currentEpisode.filename, audio.duration, audio.duration);
    renderEpisodeList(getCachedEpisodes());
  }
});

audio.addEventListener("pause", () => {
  playIcon.classList.remove("hidden");
  pauseIcon.classList.add("hidden");
  equalizer.classList.remove("playing");
  if (currentEpisode && audio.duration) {
    saveProgress(currentEpisode.filename, audio.currentTime, audio.duration);
  }
});

function showSummaries(ep) {
  if (!ep.summaries || !ep.summaries.length) {
    summaryContent.innerHTML = '<p class="empty-state">No summaries available for this episode.</p>';
  } else {
    summaryContent.innerHTML = ep.summaries.map((s) => `
      <div class="summary-card">
        <div class="summary-header">
          <h3>${s.title}</h3>
          <a href="${s.url}" target="_blank" class="summary-link">${s.domain}</a>
        </div>
        <p class="summary-text">${s.summary}</p>
        ${s.key_points && s.key_points.length ? `
          <div class="summary-points">
            <h4>Key Takeaways</h4>
            <ul>${s.key_points.map(p => `<li>${p}</li>`).join("")}</ul>
          </div>` : ""}
        ${s.architecture_details ? `
          <div class="summary-arch">
            <h4>Architecture</h4>
            <p>${s.architecture_details}</p>
          </div>` : ""}
        ${s.use_cases && s.use_cases.length ? `
          <div class="summary-uses">
            <h4>Use Cases</h4>
            <ul>${s.use_cases.map(u => `<li>${u}</li>`).join("")}</ul>
          </div>` : ""}
      </div>`).join("");
  }
  summaryModal.classList.remove("hidden");
}

// Player controls
playPauseBtn.addEventListener("click", () => {
  if (!audio.src || audio.src === location.href) return;
  if (audio.paused) {
    audio.play().catch(() => {});
  } else {
    audio.pause();
  }
});
audio.addEventListener("play", () => {
  playIcon.classList.add("hidden");
  pauseIcon.classList.remove("hidden");
  equalizer.classList.add("playing");
  if (!saveProgressTimer) {
    saveProgressTimer = setInterval(() => {
      if (currentEpisode && audio.duration && !audio.paused) {
        saveProgress(currentEpisode.filename, audio.currentTime, audio.duration);
      }
    }, SAVE_INTERVAL_MS);
  }
});
audio.addEventListener("timeupdate", () => {
  if (!audio.duration) return;
  seekBar.value = (audio.currentTime / audio.duration) * 100;
  currentTimeEl.textContent = formatTime(audio.currentTime);
});
seekBar.addEventListener("input", () => { if (audio.duration) audio.currentTime = (seekBar.value / 100) * audio.duration; });
rewindBtn.addEventListener("click", () => { audio.currentTime = Math.max(0, audio.currentTime - 15); });
forwardBtn.addEventListener("click", () => { audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 30); });
speedBtn.addEventListener("click", () => {
  speedIndex = (speedIndex + 1) % SPEEDS.length;
  audio.playbackRate = SPEEDS[speedIndex];
  speedLabel.textContent = SPEEDS[speedIndex] === 1 ? "1x" : `${SPEEDS[speedIndex]}x`;
});

// URL Queue
addUrlsBtn.addEventListener("click", async () => {
  const text = urlInput.value.trim();
  if (!text) return;
  const urls = text.split("\n").map(u => u.trim()).filter(u => u);
  if (!urls.length) return;
  addUrlsBtn.disabled = true;
  try {
    const resp = await fetch("/api/queue/add", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
    });
    const data = await resp.json();
    urlInput.value = "";
    renderQueue(data.videos);
  } catch (err) { console.error(err); } finally { addUrlsBtn.disabled = false; }
});

function renderQueue(videos) {
  if (!videos || !videos.length) { queueSection.classList.add("hidden"); return; }
  queueSection.classList.remove("hidden");
  const pending = videos.filter(v => v.status === "pending");
  queueCount.textContent = `${pending.length} source${pending.length !== 1 ? "s" : ""} queued`;
  generateFromQueue.disabled = pending.length === 0;
  queueList.innerHTML = videos.map(v => `
    <div class="queue-item">
      <span class="queue-item-title">${v.title || v.url}</span>
      <span class="queue-item-status ${v.status}">${v.status}</span>
      ${v.status === "pending" ? `<button class="queue-remove" onclick="removeFromQueue('${encodeURIComponent(v.url)}')" title="Remove">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>` : ""}
    </div>`).join("");
}

async function removeFromQueue(encodedUrl) {
  try {
    const resp = await fetch(`/api/queue/${encodedUrl}`, { method: "DELETE" });
    const data = await resp.json();
    renderQueue(data.videos);
  } catch (err) { console.error(err); }
}

generateFromQueue.addEventListener("click", async () => {
  generateFromQueue.disabled = true;
  const title = episodeTitleInput.value.trim() || "Tech Deep Dive Episode";
  try {
    await fetch("/api/generate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    statusBanner.classList.remove("hidden", "error");
    statusText.textContent = "Generating podcast... This takes a few minutes.";
    if (!pollInterval) pollInterval = setInterval(loadEpisodes, 10000);
  } catch (err) { console.error(err); }
});

// ── Episode rendering with progress ──

function renderEpisodeList(episodes) {
  if (!episodes.length) {
    episodeList.innerHTML = '<div class="empty-state"><p>No episodes yet. Add blog/doc URLs above and click "Generate Podcast".</p></div>';
    return;
  }
  episodeList.innerHTML = episodes.map((ep) => {
    const isActive = currentEpisode && currentEpisode.filename === ep.filename;
    const pct = progressPercent(ep.filename);
    const listened = isListened(ep.filename);
    const progressLabel = listened ? "Listened" : pct > 0 ? `${pct}% played` : "";
    const isCachedOnly = ep._cached === true;

    return `
    <div class="episode-item ${isActive ? "active" : ""} ${listened ? "listened" : ""}" data-filename="${ep.filename}">
      <div class="episode-number" onclick='playEpisode(${JSON.stringify(ep).replace(/'/g, "&#39;")})'>${ep.day_number}</div>
      <div class="episode-info" onclick='playEpisode(${JSON.stringify(ep).replace(/'/g, "&#39;")})'>
        <h3>${ep.technology}${isCachedOnly ? ' <span class="cached-badge">cached</span>' : ""}</h3>
        <div class="episode-meta">
          <span>${ep.date}</span><span class="dot"></span>
          <span>${ep.sources_used || ep.videos_used || 0} sources</span>
          ${progressLabel ? `<span class="dot"></span><span class="progress-label ${listened ? "done" : ""}">${progressLabel}</span>` : ""}
        </div>
        ${pct > 0 && !listened ? `<div class="episode-progress-bar"><div class="episode-progress-fill" style="width:${pct}%"></div></div>` : ""}
      </div>
      <button class="summary-btn" onclick='showSummaries(${JSON.stringify(ep).replace(/'/g, "&#39;")})' title="View Summaries">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
        </svg>
      </button>
      ${!isCachedOnly ? `<a class="download-btn" href="/download/${ep.filename}" title="Download" onclick="event.stopPropagation()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
      </a>` : ""}
      <div class="episode-play-icon" onclick='playEpisode(${JSON.stringify(ep).replace(/'/g, "&#39;")})'>
        <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
      </div>
    </div>`;
  }).join("");
}

// ── Load episodes (merge server + cache) ──

async function loadEpisodes() {
  try {
    const resp = await fetch("/api/episodes");
    const data = await resp.json();
    if (data.generating) {
      statusBanner.classList.remove("hidden", "error");
      statusText.textContent = "Generating podcast... This takes a few minutes.";
      if (!pollInterval) pollInterval = setInterval(loadEpisodes, 10000);
    } else if (data.generation_error) {
      statusBanner.classList.remove("hidden"); statusBanner.classList.add("error");
      statusText.textContent = `Error: ${data.generation_error}`;
      if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
      generateFromQueue.disabled = false;
    } else {
      if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
      generateFromQueue.disabled = false; loadQueue();

      const prevCount = getCachedEpisodes().length;
      const newCount = (data.episodes || []).length;
      if (newCount > prevCount && newCount > 0) {
        statusBanner.classList.remove("hidden", "error");
        statusBanner.classList.add("success");
        const latest = data.episodes[data.episodes.length - 1];
        statusText.innerHTML = `Episode ready! <a href="/download/${latest.filename}" class="download-prompt">Download to keep a permanent copy</a>`;
        setTimeout(() => statusBanner.classList.add("hidden"), 30000);
      } else {
        statusBanner.classList.add("hidden");
      }
    }

    const serverEps = data.episodes || [];
    const cached = getCachedEpisodes();

    const serverFiles = new Set(serverEps.map(e => e.filename));
    const merged = [...serverEps];
    for (const ce of cached) {
      if (!serverFiles.has(ce.filename)) {
        const copy = Object.assign({}, ce);
        copy._cached = true;
        merged.push(copy);
      }
    }
    cacheEpisodes(merged);
    renderEpisodeList(merged);
  } catch {
    const cached = getCachedEpisodes();
    if (cached.length) {
      renderEpisodeList(cached);
    } else {
      episodeList.innerHTML = '<div class="empty-state"><p>Could not load episodes.</p></div>';
    }
  }
}

async function loadQueue() {
  try {
    const resp = await fetch("/api/queue");
    renderQueue((await resp.json()).videos);
  } catch (err) { console.error(err); }
}

// ── Restore last session ──

function restoreSession() {
  const last = getLastPlaying();
  if (!last) return;
  const episodes = getCachedEpisodes();
  const ep = episodes.find(e => e.filename === last.filename);
  if (ep) {
    loadEpisodeWithoutPlaying(ep);
  }
}

// Summary modal
closeSummary.addEventListener("click", () => { summaryModal.classList.add("hidden"); });
summaryModal.addEventListener("click", (e) => { if (e.target === summaryModal) summaryModal.classList.add("hidden"); });

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});

loadEpisodes().then(() => restoreSession());
loadQueue();
