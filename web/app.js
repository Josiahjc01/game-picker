const state = {
  games: [],
  filtered: [],
  selectedIndex: 0,
  active: null,
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
  grade: document.getElementById("grade"),
  score: document.getElementById("score"),
  bars: document.getElementById("bars"),
  caveat: document.getElementById("caveat"),
  sourcePill: document.getElementById("source-pill"),
};

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
    // Prefer the base title over DLC/expansions when the query is a prefix.
    if (name === q || name.startsWith(`${q} `) || name.startsWith(q)) {
      score += 80;
      score -= Math.max(0, name.length - q.length) * 1.5;
    }
    score += Math.max(0, 25 - name.indexOf(tokens[0]));
    // Weak popularity tie-breaker only.
    score += Math.min(4, (game.peak_ccu || 0) / 200000);
    scored.push({ game, score });
  }
  scored.sort((a, b) => b.score - a.score || a.game.name.length - b.game.name.length);
  return scored.slice(0, 8).map((s) => s.game);
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
      const img = g.header_image
        ? `<img src="${g.header_image}" alt="" loading="lazy" />`
        : `<span class="sg-ph"></span>`;
      const selected = i === state.selectedIndex ? ' aria-selected="true"' : "";
      return `<button type="button" class="suggestion" data-index="${i}" data-name="${escapeHtml(g.name)}"${selected}>
        ${img}
        <span><span class="sg-name">${escapeHtml(g.name)}</span>
        <span class="sg-sub">${escapeHtml((g.genres || []).slice(0, 2).join(" · ") || g.data_source)}</span></span>
        <span class="sg-hours">${formatHours(g.estimated_avg_player_hours)}</span>
      </button>`;
    })
    .join("");
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

function renderEstimate(game) {
  state.active = game;
  els.empty.hidden = true;
  els.estimate.hidden = false;
  // Retrigger entrance animation on each selection.
  els.estimate.style.animation = "none";
  // force reflow
  void els.estimate.offsetWidth;
  els.estimate.style.animation = "";

  els.title.textContent = game.name;
  els.cover.src = game.header_image || "";
  els.cover.alt = game.header_image ? `${game.name} cover` : "";
  els.cover.style.opacity = game.header_image ? "1" : "0.35";

  const genres = (game.genres || []).slice(0, 3).join(" · ");
  els.meta.textContent = [genres, game.release_date].filter(Boolean).join(" · ");

  els.sourcePill.textContent =
    game.confidence === "high" ? "High confidence · factory sample" : "Steam signals · mixed confidence";
  els.sourcePill.className = `pill ${game.confidence === "high" ? "high" : "mixed"}`;

  // Reset number animation baseline when switching games so the value always updates.
  els.hours.dataset.value = "0";
  els.hours.textContent = "0";
  animateNumber(els.hours, game.estimated_avg_player_hours);
  els.grade.textContent = game.grade;
  els.score.textContent = `${game.addictiveness.toFixed(1)} / 100`;

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

  els.caveat.textContent =
    game.data_source === "factory_reviews"
      ? "Hours blend age-adjusted median/mean from the factory-game reviewer sample."
      : "Hours come from SteamSpy-style owner medians/averages; stickiness & 100h+ share are proxied (see README).";
}

function onQueryInput() {
  state.filtered = searchGames(els.q.value);
  state.selectedIndex = 0;
  renderSuggestions();
  if (!els.q.value.trim() && !state.active) {
    els.estimate.hidden = true;
    els.empty.hidden = false;
  }
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

// Expose for demos / console debugging.
window.gamePickerSelect = selectByName;

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
    state.selectedIndex = (state.selectedIndex - 1 + state.filtered.length) % state.filtered.length;
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

async function boot() {
  const res = await fetch("./games.json");
  if (!res.ok) throw new Error(`Failed to load games.json (${res.status})`);
  const payload = await res.json();
  state.games = payload.games || [];
  els.libCount.textContent = `${state.games.length.toLocaleString()} games loaded`;

  // Deep-link ?q=
  const params = new URLSearchParams(location.search);
  const q = params.get("q");
  if (q) {
    els.q.value = q;
    state.filtered = searchGames(q);
    renderSuggestions();
    if (state.filtered[0]) selectIndex(0);
  }

  els.q.focus();
}

boot().catch((err) => {
  els.libCount.textContent = "Failed to load library";
  els.empty.textContent = String(err);
  console.error(err);
});
