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
const scheduleBtn = document.getElementById("scheduleBtn");
const scheduleModal = document.getElementById("scheduleModal");
const closeSchedule = document.getElementById("closeSchedule");
const scheduleList = document.getElementById("scheduleList");
const generateBtn = document.getElementById("generateBtn");

const SPEEDS = [0.75, 1, 1.25, 1.5, 1.75, 2];
let speedIndex = 1;
let currentEpisode = null;
let pollInterval = null;

const CATEGORY_GRADIENTS = {
  Databases: "linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%)",
  "Big Data": "linear-gradient(135deg, #1a4731 0%, #0f172a 100%)",
  "Stream Processing": "linear-gradient(135deg, #3b1a4f 0%, #0f172a 100%)",
  Messaging: "linear-gradient(135deg, #4a1a1a 0%, #0f172a 100%)",
  Search: "linear-gradient(135deg, #1a3a4f 0%, #0f172a 100%)",
  Analytics: "linear-gradient(135deg, #3a3a1a 0%, #0f172a 100%)",
  "Query Engine": "linear-gradient(135deg, #1a4f4f 0%, #0f172a 100%)",
  "In-Memory Format": "linear-gradient(135deg, #2a1a4f 0%, #0f172a 100%)",
  "Table Format": "linear-gradient(135deg, #1a2a4f 0%, #0f172a 100%)",
  Orchestration: "linear-gradient(135deg, #4f3a1a 0%, #0f172a 100%)",
  default: "linear-gradient(135deg, #1e3a5f 0%, #0f172a 50%, #1a1a2e 100%)",
};

function formatTime(s) {
  if (!s || isNaN(s)) return "0:00";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function playEpisode(ep) {
  currentEpisode = ep;
  audio.src = `/audio/${ep.filename}`;
  audio.play();

  nowPlaying.classList.remove("hidden");
  playerTitle.textContent = `Day ${ep.day_number}: ${ep.technology}`;
  playerCategory.textContent = ep.category;
  artDay.textContent = `Day ${ep.day_number}`;
  artTech.textContent = ep.technology;

  const artBg = document.getElementById("artBg");
  artBg.style.background = CATEGORY_GRADIENTS[ep.category] || CATEGORY_GRADIENTS.default;

  document.querySelectorAll(".episode-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.filename === ep.filename);
  });

  if ("mediaSession" in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: `Day ${ep.day_number}: ${ep.technology}`,
      artist: "Tech Deep Dive",
      album: ep.category,
    });
    navigator.mediaSession.setActionHandler("play", () => audio.play());
    navigator.mediaSession.setActionHandler("pause", () => audio.pause());
    navigator.mediaSession.setActionHandler("seekbackward", () => { audio.currentTime = Math.max(0, audio.currentTime - 15); });
    navigator.mediaSession.setActionHandler("seekforward", () => { audio.currentTime += 30; });
  }
}

// Player controls
playPauseBtn.addEventListener("click", () => {
  if (!audio.src) return;
  if (audio.paused) audio.play();
  else audio.pause();
});

audio.addEventListener("play", () => {
  playIcon.classList.add("hidden");
  pauseIcon.classList.remove("hidden");
  equalizer.classList.add("playing");
});

audio.addEventListener("pause", () => {
  playIcon.classList.remove("hidden");
  pauseIcon.classList.add("hidden");
  equalizer.classList.remove("playing");
});

audio.addEventListener("timeupdate", () => {
  if (!audio.duration) return;
  const pct = (audio.currentTime / audio.duration) * 100;
  seekBar.value = pct;
  currentTimeEl.textContent = formatTime(audio.currentTime);
});

audio.addEventListener("loadedmetadata", () => {
  durationEl.textContent = formatTime(audio.duration);
});

seekBar.addEventListener("input", () => {
  if (!audio.duration) return;
  audio.currentTime = (seekBar.value / 100) * audio.duration;
});

rewindBtn.addEventListener("click", () => {
  audio.currentTime = Math.max(0, audio.currentTime - 15);
});

forwardBtn.addEventListener("click", () => {
  audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 30);
});

speedBtn.addEventListener("click", () => {
  speedIndex = (speedIndex + 1) % SPEEDS.length;
  const speed = SPEEDS[speedIndex];
  audio.playbackRate = speed;
  speedLabel.textContent = speed === 1 ? "1x" : `${speed}x`;
});

// Load episodes
async function loadEpisodes() {
  try {
    const resp = await fetch("/api/episodes");
    const data = await resp.json();

    if (data.generating) {
      statusBanner.classList.remove("hidden", "error");
      statusText.textContent = "Generating today's episode... This may take a few minutes.";
      if (!pollInterval) {
        pollInterval = setInterval(loadEpisodes, 10000);
      }
    } else if (data.generation_error) {
      statusBanner.classList.remove("hidden");
      statusBanner.classList.add("error");
      statusText.textContent = `Generation error: ${data.generation_error}`;
      if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
    } else {
      statusBanner.classList.add("hidden");
      if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
    }

    const episodes = data.episodes || [];
    if (episodes.length === 0) {
      episodeList.innerHTML = `
        <div class="empty-state">
          <p>No episodes yet.</p>
          <p>Click "Generate New" or wait for auto-generation to complete.</p>
        </div>`;
      return;
    }

    episodeList.innerHTML = episodes
      .map((ep) => {
        const isActive = currentEpisode && currentEpisode.filename === ep.filename;
        return `
        <div class="episode-item ${isActive ? "active" : ""}"
             data-filename="${ep.filename}"
             onclick='playEpisode(${JSON.stringify(ep).replace(/'/g, "&#39;")})'>
          <div class="episode-number">${ep.day_number}</div>
          <div class="episode-info">
            <h3>${ep.technology}</h3>
            <div class="episode-meta">
              <span>${ep.category}</span>
              <span class="dot"></span>
              <span>${ep.date}</span>
              <span class="dot"></span>
              <span>${ep.videos_used} sources</span>
            </div>
          </div>
          <div class="episode-play-icon">
            <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          </div>
        </div>`;
      })
      .join("");
  } catch (err) {
    episodeList.innerHTML = `
      <div class="empty-state">
        <p>Could not load episodes. Is the server running?</p>
      </div>`;
  }
}

// Generate new episode
generateBtn.addEventListener("click", async () => {
  generateBtn.disabled = true;
  try {
    await fetch("/api/generate", { method: "POST" });
    statusBanner.classList.remove("hidden", "error");
    statusText.textContent = "Generating new episode... This may take a few minutes.";
    if (!pollInterval) {
      pollInterval = setInterval(loadEpisodes, 10000);
    }
  } catch (err) {
    console.error("Generate request failed", err);
  } finally {
    setTimeout(() => { generateBtn.disabled = false; }, 5000);
  }
});

// Schedule modal
scheduleBtn.addEventListener("click", async () => {
  scheduleModal.classList.remove("hidden");
  try {
    const resp = await fetch("/api/schedule");
    const data = await resp.json();
    scheduleList.innerHTML = (data.schedule || [])
      .map((item) => `
        <div class="schedule-item ${item.is_today ? "today" : ""}">
          <span class="schedule-day">Day ${item.day}</span>
          <span class="schedule-name">${item.name}</span>
          <span class="schedule-category">${item.category}</span>
          ${item.is_today ? '<span class="today-badge">Today</span>' : ""}
        </div>`)
      .join("");
  } catch (err) {
    scheduleList.innerHTML = '<p class="empty-state">Could not load schedule</p>';
  }
});

closeSchedule.addEventListener("click", () => {
  scheduleModal.classList.add("hidden");
});

scheduleModal.addEventListener("click", (e) => {
  if (e.target === scheduleModal) scheduleModal.classList.add("hidden");
});

// Register service worker for PWA
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

// Initial load
loadEpisodes();
