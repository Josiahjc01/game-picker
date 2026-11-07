import { DEFAULT_GENRE_CHOICES, defaultProfile, personalizeGame } from "./personalize.js";

const STORAGE_KEY = "game-picker-profile-v1";

const state = {
  games: [],
  filtered: [],
  selectedIndex: 0,
  active: null,
  profile: loadProfile(),
};

const els = {
  q: document.getElementById("q"),
  suggestions: document.getElementById("suggestions"),
  estimate: document.getElementById("estimate"),
  empty: document.getElementById("empty"),
  libCount: document.getElementById("lib-count"),
  cover: document.getElementById("cover"),
  title: document.getElementById("game-title"),
  meta: document.getElementById("game-meta"),
  hours: document.getElementById("hours"),
  baselineHours: document.getElementById("baseline-hours"),
  hoursDelta: document.getElementById("hours-delta"),
  baselineGradeLine: document.getElementById("baseline-grade-line"),
  grade: document.getElementById("grade"),
  score: document.getElementById("score"),
  bars: document.getElementById("bars"),
  caveat: document.getElementById("caveat"),
  sourcePill: document.getElementById("source-pill"),
  calendar: document.getElementById("calendar"),
  reasons: document.getElementById("reasons"),
  profileToggle: document.getElementById("profile-toggle"),
  profilePanel: document.getElementById("profile-panel"),
  profileSummary: document.getElementById("profile-summary"),
  likedGenres: document.getElementById("liked-genres"),
  dislikedGenres: document.getElementById("disliked-genres"),
  recentGenres: document.getElementById("recent-genres"),
  recentGames: document.getElementById("recent-games"),
  pacing: document.getElementById("pacing"),
  completionism: document.getElementById("completionism"),
  multiplayer: document.getElementById("multiplayer"),
  complexity: document.getElementById("complexity"),
  weeklyHours: document.getElementById("weekly-hours"),
  pacingLabel: document.getElementById("pacing-label"),
  completionLabel: document.getElementById("completion-label"),
  mpLabel: document.getElementById("mp-label"),
  complexityLabel: document.getElementById("complexity-label"),
  profileApply: document.getElementById("profile-apply"),
  profileReset: document.getElementById("profile-reset"),
};

function loadProfile() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultProfile();
    return { ...defaultProfile(), ...JSON.parse(raw) };
  } catch {
    return defaultProfile();
  }
}

function saveProfile(profile) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
}

function normalize(s) {
  return String(s || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "");
}

function searchGames(query) {
  const q = normalize(query).trim();
  if (!q) return [];
  const tokens = q.split(/\s+/).filter(Boolean);
  const scored = [];
  for (const game of state.games) {
    const name = normalize(game.name);
    if (!tokens.every((t) => name.includes(t))) continue;
    let score = 0;
    if (name === q) score += 200;
    if (name === q || name.startsWith(`${q} `) || name.startsWith(q)) {
      score += 80;
      score -= Math.max(0, name.length - q.length) * 1.5;
    }
    score += Math.max(0, 25 - name.indexOf(tokens[0]));
    score += Math.min(4, (game.peak_ccu || 0) / 200000);
    scored.push({ game, score });
  }
  scored.sort((a, b) => b.score - a.score || a.game.name.length - b.game.name.length);
  return scored.slice(0, 8).map((s) => s.game);
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatHours(h) {
  if (h >= 100) return `${Math.round(h)}h`;
  if (h >= 10) return `${h.toFixed(0)}h`;
  return `${h.toFixed(1)}h`;
}

function animateNumber(el, to, duration = 650) {
  const from = Number(el.dataset.value || 0);
  const start = performance.now();
  const delta = to - from;
  function frame(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    const value = from + delta * eased;
    el.textContent = value >= 100 ? Math.round(value).toString() : value.toFixed(1);
    if (t < 1) requestAnimationFrame(frame);
    else el.dataset.value = String(to);
  }
  requestAnimationFrame(frame);
}

function renderSuggestions() {
  const list = state.filtered;
  if (!list.length) {
    els.suggestions.hidden = true;
    els.suggestions.innerHTML = "";
    return;
  }
  els.suggestions.hidden = false;
  els.suggestions.innerHTML = list
    .map((g, i) => {
      const personalized = personalizeGame(g, state.profile);
      const img = g.header_image
        ? `<img src="${g.header_image}" alt="" loading="lazy" />`
        : `<span class="sg-ph"></span>`;
      const selected = i === state.selectedIndex ? ' aria-selected="true"' : "";
      return `<button type="button" class="suggestion" data-index="${i}" data-name="${escapeHtml(g.name)}"${selected}>
        ${img}
        <span><span class="sg-name">${escapeHtml(g.name)}</span>
        <span class="sg-sub">${escapeHtml((g.genres || []).slice(0, 2).join(" · ") || g.data_source)}</span></span>
        <span class="sg-hours">${formatHours(personalized.personalizedHours)}</span>
      </button>`;
    })
    .join("");
}

function renderEstimate(game) {
  state.active = game;
  els.empty.hidden = true;
  els.estimate.hidden = false;
  els.estimate.style.animation = "none";
  void els.estimate.offsetWidth;
  els.estimate.style.animation = "";

  const p = personalizeGame(game, state.profile);

  els.title.textContent = game.name;
  els.cover.src = game.header_image || "";
  els.cover.alt = game.header_image ? `${game.name} cover` : "";
  els.cover.style.opacity = game.header_image ? "1" : "0.35";

  const genres = (game.genres || []).slice(0, 3).join(" · ");
  els.meta.textContent = [genres, game.release_date].filter(Boolean).join(" · ");

  els.sourcePill.textContent =
    game.confidence === "high" ? "High confidence · factory sample" : "Steam signals · mixed confidence";
  els.sourcePill.className = `pill ${game.confidence === "high" ? "high" : "mixed"}`;

  els.hours.dataset.value = "0";
  els.hours.textContent = "0";
  animateNumber(els.hours, p.personalizedHours);
  els.baselineHours.textContent =
    p.baselineHours >= 100 ? Math.round(p.baselineHours).toString() : p.baselineHours.toFixed(1);

  const delta = p.personalizedHours - p.baselineHours;
  const sign = delta >= 0 ? "+" : "";
  const effectiveMult =
    p.baselineHours > 0 ? p.personalizedHours / p.baselineHours : p.hoursMultiplier;
  const capNote = p.calendarCapped ? " · calendar-capped" : "";
  els.hoursDelta.textContent = `${sign}${delta.toFixed(1)}h vs average · ×${effectiveMult.toFixed(2)} pref ×${p.hoursMultiplier.toFixed(2)}${capNote}`;
  els.baselineGradeLine.textContent = `Baseline grade ${p.baselineGrade} (${p.baselineAddictiveness.toFixed(1)})`;

  els.grade.textContent = p.personalizedGrade;
  els.score.textContent = `${p.personalizedAddictiveness.toFixed(1)} / 100`;

  els.calendar.innerHTML = `
    <span class="cal-pill">${p.calendarWeeks.toFixed(1)} weeks at ${state.profile.weeklyHours}h/wk</span>
    <span class="cal-pill">≈ ${p.calendarMonths.toFixed(1)} months</span>
    <span class="cal-pill">Interest horizon ${p.horizonWeeks.toFixed(0)}w${p.calendarCapped ? " · capped" : ""}</span>
  `;

  els.reasons.innerHTML = p.reasons.map((r) => `<p class="reason">${escapeHtml(r)}</p>`).join("");

  const order = ["depth", "intensity", "stickiness", "deep_hook", "popularity"];
  els.bars.innerHTML = order
    .map((key) => {
      const v = game.components?.[key] ?? 0;
      return `<div class="bar-row">
        <span>${key.replace("_", " ")}</span>
        <div class="bar-track"><div class="bar-fill" data-w="${Math.round(v * 100)}"></div></div>
        <strong>${Math.round(v * 100)}</strong>
      </div>`;
    })
    .join("");

  requestAnimationFrame(() => {
    els.bars.querySelectorAll(".bar-fill").forEach((el) => {
      el.style.width = `${el.dataset.w}%`;
    });
  });

  els.caveat.textContent = p.confidenceNote;
}

function selectGame(game) {
  if (!game) return;
  els.q.value = game.name;
  state.filtered = [];
  els.suggestions.hidden = true;
  els.suggestions.innerHTML = "";
  renderEstimate(game);
}

function selectIndex(i) {
  selectGame(state.filtered[i]);
}

function selectByName(name) {
  const game =
    state.filtered.find((g) => g.name === name) ||
    state.games.find((g) => g.name === name);
  selectGame(game);
}

window.gamePickerSelect = selectByName;
window.gamePickerProfile = () => state.profile;

function onQueryInput() {
  state.filtered = searchGames(els.q.value);
  state.selectedIndex = 0;
  renderSuggestions();
  if (!els.q.value.trim() && !state.active) {
    els.estimate.hidden = true;
    els.empty.hidden = false;
  }
}

els.q.addEventListener("input", onQueryInput);
els.q.addEventListener("keydown", (e) => {
  if (els.suggestions.hidden || !state.filtered.length) {
    if (e.key === "Enter" && state.filtered[0]) selectIndex(0);
    return;
  }
  if (e.key === "ArrowDown") {
    e.preventDefault();
    state.selectedIndex = (state.selectedIndex + 1) % state.filtered.length;
    renderSuggestions();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    state.selectedIndex =
      (state.selectedIndex - 1 + state.filtered.length) % state.filtered.length;
    renderSuggestions();
  } else if (e.key === "Enter") {
    e.preventDefault();
    selectIndex(state.selectedIndex);
  } else if (e.key === "Escape") {
    els.suggestions.hidden = true;
  }
});

els.suggestions.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-index]");
  if (!btn) return;
  selectIndex(Number(btn.dataset.index));
});

function genreUniverse() {
  const counts = new Map();
  for (const g of state.games) {
    for (const genre of g.genres || []) {
      counts.set(genre, (counts.get(genre) || 0) + 1);
    }
  }
  const fromLib = [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([name]) => name)
    .filter((name) => !/utilities|design|modeling|video production|audio production|photo editing|web publishing|software training|accounting|game development/i.test(name));
  const merged = [...DEFAULT_GENRE_CHOICES];
  for (const g of fromLib) {
    if (!merged.includes(g)) merged.push(g);
  }
  return merged.slice(0, 14);
}

function renderChipGroup(container, selected, mode) {
  const genres = genreUniverse();
  container.innerHTML = genres
    .map((g) => {
      const on = selected.includes(g);
      const avoid = mode === "avoid" ? " chip-avoid" : "";
      return `<button type="button" class="chip${avoid}" data-genre="${escapeHtml(g)}" aria-pressed="${on}">${escapeHtml(g)}</button>`;
    })
    .join("");
}

function bindChipGroup(container, key) {
  container.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-genre]");
    if (!btn) return;
    const genre = btn.dataset.genre;
    const list = new Set(state.profile[key]);
    if (list.has(genre)) list.delete(genre);
    else list.add(genre);
    state.profile[key] = [...list];
    btn.setAttribute("aria-pressed", list.has(genre) ? "true" : "false");
    saveProfile(state.profile);
    updateProfileSummary();
  });
}

function sliderWord(kind, v) {
  if (kind === "pacing") {
    if (v < 0.34) return "short sessions";
    if (v < 0.67) return "balanced";
    return "long grind";
  }
  if (kind === "completion") {
    if (v < 0.34) return "dabbler";
    if (v < 0.67) return "mixed";
    return "completionist";
  }
  if (kind === "mp") {
    if (v < 0.34) return "solo-first";
    if (v < 0.67) return "flexible";
    return "multiplayer-first";
  }
  if (v < 0.34) return "simple";
  if (v < 0.67) return "moderate";
  return "systems-heavy";
}

function syncProfileForm() {
  const p = state.profile;
  renderChipGroup(els.likedGenres, p.likedGenres, "like");
  renderChipGroup(els.dislikedGenres, p.dislikedGenres, "avoid");
  renderChipGroup(els.recentGenres, p.recentGenres, "recent");
  els.recentGames.value = p.recentGamesText || "";
  els.pacing.value = Math.round(p.pacing * 100);
  els.completionism.value = Math.round(p.completionism * 100);
  els.multiplayer.value = Math.round(p.multiplayerBias * 100);
  els.complexity.value = Math.round(p.complexityTolerance * 100);
  els.weeklyHours.value = p.weeklyHours;
  updateSliderLabels();
  updateProfileSummary();
}

function readProfileFromForm() {
  return {
    likedGenres: [...els.likedGenres.querySelectorAll('.chip[aria-pressed="true"]')].map(
      (b) => b.dataset.genre
    ),
    dislikedGenres: [...els.dislikedGenres.querySelectorAll('.chip[aria-pressed="true"]')].map(
      (b) => b.dataset.genre
    ),
    recentGenres: [...els.recentGenres.querySelectorAll('.chip[aria-pressed="true"]')].map(
      (b) => b.dataset.genre
    ),
    recentGamesText: els.recentGames.value.trim(),
    pacing: Number(els.pacing.value) / 100,
    completionism: Number(els.completionism.value) / 100,
    multiplayerBias: Number(els.multiplayer.value) / 100,
    complexityTolerance: Number(els.complexity.value) / 100,
    weeklyHours: Math.max(0.5, Number(els.weeklyHours.value) || 8),
  };
}

function updateSliderLabels() {
  const pacing = Number(els.pacing.value) / 100;
  const completion = Number(els.completionism.value) / 100;
  const mp = Number(els.multiplayer.value) / 100;
  const complexity = Number(els.complexity.value) / 100;
  els.pacingLabel.textContent = sliderWord("pacing", pacing);
  els.completionLabel.textContent = sliderWord("completion", completion);
  els.mpLabel.textContent = sliderWord("mp", mp);
  els.complexityLabel.textContent = sliderWord("complexity", complexity);
}

function updateProfileSummary() {
  const p = state.profile;
  const likes = p.likedGenres.slice(0, 2).join(", ") || "no likes set";
  els.profileSummary.textContent = `${likes} · ${p.weeklyHours}h/week`;
}

function applyProfile({ close = false } = {}) {
  state.profile = readProfileFromForm();
  saveProfile(state.profile);
  updateProfileSummary();
  if (state.active) renderEstimate(state.active);
  if (els.q.value.trim()) {
    state.filtered = searchGames(els.q.value);
    renderSuggestions();
  }
  if (close) {
    els.profilePanel.hidden = true;
    els.profileToggle.setAttribute("aria-expanded", "false");
  }
}

els.profileToggle.addEventListener("click", () => {
  const open = els.profilePanel.hidden;
  els.profilePanel.hidden = !open;
  els.profileToggle.setAttribute("aria-expanded", open ? "true" : "false");
  if (open) syncProfileForm();
});

els.profileApply.addEventListener("click", () => applyProfile({ close: true }));
els.profileReset.addEventListener("click", () => {
  state.profile = defaultProfile();
  saveProfile(state.profile);
  syncProfileForm();
  if (state.active) renderEstimate(state.active);
});

for (const el of [els.pacing, els.completionism, els.multiplayer, els.complexity]) {
  el.addEventListener("input", updateSliderLabels);
}

bindChipGroup(els.likedGenres, "likedGenres");
bindChipGroup(els.dislikedGenres, "dislikedGenres");
bindChipGroup(els.recentGenres, "recentGenres");

async function boot() {
  const res = await fetch("./games.json");
  if (!res.ok) throw new Error(`Failed to load games.json (${res.status})`);
  const payload = await res.json();
  state.games = payload.games || [];
  els.libCount.textContent = `${state.games.length.toLocaleString()} games loaded`;
  updateProfileSummary();

  const params = new URLSearchParams(location.search);
  const q = params.get("q");
  if (q) {
    els.q.value = q;
    state.filtered = searchGames(q);
    renderSuggestions();
    if (state.filtered[0]) selectIndex(0);
  } else {
    els.q.focus();
  }
}

boot().catch((err) => {
  els.libCount.textContent = "Failed to load library";
  els.empty.textContent = String(err);
  console.error(err);
});
