/** Fair personalization — keep in sync with game_picker/personalize.py */

export const DEFAULT_GENRE_CHOICES = [
  "Action",
  "Adventure",
  "Casual",
  "Indie",
  "RPG",
  "Racing",
  "Simulation",
  "Sports",
  "Strategy",
  "Massively Multiplayer",
  "Free To Play",
];

const COMPLEX_GENRES = new Set([
  "Strategy",
  "Simulation",
  "RPG",
  "Massively Multiplayer",
  "Early Access",
]);
const LIGHT_GENRES = new Set(["Casual", "Adventure", "Racing", "Sports", "Indie"]);

export function defaultProfile() {
  return {
    likedGenres: [],
    dislikedGenres: [],
    recentGenres: [],
    recentGamesText: "",
    pacing: 0.5,
    completionism: 0.5,
    multiplayerBias: 0.35,
    complexityTolerance: 0.55,
    weeklyHours: 8,
  };
}

function clamp(x, lo, hi) {
  return Math.max(lo, Math.min(hi, x));
}

function normName(s) {
  return String(s || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function genreSet(game) {
  return new Set((game.genres || []).map(String));
}

function overlapRatio(list, set) {
  if (!list.length) return 0;
  let hits = 0;
  for (const x of list) if (set.has(x)) hits += 1;
  return hits / list.length;
}

function recentGameNames(profile) {
  return String(profile.recentGamesText || "")
    .replace(/\n/g, ",")
    .split(/[,;/|]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function gameComplexity(game) {
  const genres = genreSet(game);
  let base = 0.55;
  const hasComplex = [...genres].some((g) => COMPLEX_GENRES.has(g));
  const hasLight = [...genres].some((g) => LIGHT_GENRES.has(g));
  if (hasComplex && ![...genres].every((g) => LIGHT_GENRES.has(g))) base = 0.75;
  else if (hasLight && !hasComplex) base = 0.3;
  else if (!genres.size) base = 0.5;
  const depth = Number(game.components?.depth || 0);
  return clamp(0.65 * base + 0.35 * depth, 0, 1);
}

function gameMultiplayerScore(game) {
  const cats = game.categories || [];
  const genres = genreSet(game);
  const hasMp =
    cats.some((c) => /multi-player|multiplayer|co-op/i.test(c)) ||
    genres.has("Massively Multiplayer");
  const hasSp = cats.includes("Single-player");
  if (hasMp && !hasSp) return 1;
  if (hasMp && hasSp) return 0.55;
  if (hasSp) return 0.15;
  return 0.4;
}

function gradeFromScore(score) {
  if (score >= 85) return "S";
  if (score >= 75) return "A";
  if (score >= 65) return "B";
  if (score >= 50) return "C";
  if (score >= 35) return "D";
  return "F";
}

export function personalizeGame(game, profile) {
  const p = { ...defaultProfile(), ...profile };
  const baselineHours = Number(game.estimated_avg_player_hours || 0);
  const baselineAdd = Number(game.addictiveness || 0);
  const baselineGrade = game.grade || gradeFromScore(baselineAdd);
  const genres = genreSet(game);
  const reasons = [];

  const liked = overlapRatio(p.likedGenres, genres);
  let disliked = 0;
  if (p.dislikedGenres.length && genres.size) {
    disliked = [...genres].filter((g) => p.dislikedGenres.includes(g)).length / genres.size;
  }
  const recentG = overlapRatio(p.recentGenres, genres);
  const nameN = normName(game.name);
  const exactRecent = recentGameNames(p).some((r) => {
    const rn = normName(r);
    return rn && (nameN === rn || nameN.includes(rn) || rn.includes(nameN));
  });

  let affinity = 0.5 * liked - 0.55 * disliked + 0.25 * recentG;
  if (exactRecent) {
    affinity += 0.08;
    reasons.push("Recently played / in rotation (small familiarity boost)");
  }
  if (liked > 0) reasons.push(`Liked-genre overlap ${Math.round(liked * 100)}%`);
  if (disliked > 0) reasons.push(`Disliked-genre overlap ${Math.round(disliked * 100)}% (penalty)`);
  if (recentG > 0 && !exactRecent) {
    reasons.push(`Matches recent genre mix (${Math.round(recentG * 100)}%)`);
  }
  if (!genres.size) {
    affinity *= 0.85;
    reasons.push("Thin genre metadata — muted affinity signal");
  }
  affinity = clamp(affinity, -1, 1);
  if (!reasons.length) reasons.push("Neutral genre fit (no strong likes/dislikes matched)");

  const complexity = gameComplexity(game);
  const mp = gameMultiplayerScore(game);
  const depth = Number(game.components?.depth || 0.5);
  const pacingFit = 1 - Math.abs(p.pacing - depth);
  const complexityFit = 1 - Math.abs(p.complexityTolerance - complexity);
  const mpFit = 1 - Math.abs(p.multiplayerBias - mp);

  let hoursMult =
    1.0 +
    0.35 * affinity +
    0.15 * (pacingFit - 0.5) * 2 +
    0.12 * (complexityFit - 0.5) * 2 +
    0.1 * (mpFit - 0.5) * 2 +
    0.1 * (p.completionism - 0.5) * 2;
  hoursMult = clamp(hoursMult, 0.5, 1.55);
  const hPref = baselineHours * hoursMult;

  const affinity01 = (affinity + 1) / 2;
  let horizon = 6 + 10 * (baselineAdd / 100) * (0.45 + 0.55 * affinity01);
  horizon *= 0.9 + 0.4 * p.completionism;
  horizon = clamp(horizon, 4, 26);

  const calendarCap = Math.max(0.5, p.weeklyHours) * horizon;
  const calendarCapped = hPref > calendarCap + 1e-6;
  let hYou = Math.min(hPref, calendarCap);
  hYou = Math.round(Math.max(0.5, hYou) * 10) / 10;

  if (calendarCapped) {
    reasons.push(
      `Weekly free time caps engagement at ~${p.weeklyHours}h × ${Math.round(horizon)}w horizon`
    );
  }
  if (hoursMult >= 1.08) reasons.push(`Preference uplift ×${hoursMult.toFixed(2)}`);
  else if (hoursMult <= 0.92) reasons.push(`Preference downshift ×${hoursMult.toFixed(2)}`);

  let aYou =
    baselineAdd + 16 * affinity + 5 * (complexityFit - 0.5) * 2 + 4 * (pacingFit - 0.5) * 2;
  aYou = Math.round(clamp(aYou, 0, 100) * 10) / 10;
  const grade = gradeFromScore(aYou);
  const weeks = hYou / Math.max(p.weeklyHours, 0.5);
  const months = weeks / 4.345;

  let confidenceNote =
    game.confidence === "high"
      ? "High-confidence baseline (factory sample), then fair preference multipliers."
      : "Mixed-confidence Steam baseline (some proxied fields); personalization is deterministic but inherits that uncertainty.";
  if (!genres.size) confidenceNote += " Thin genre tags on this title — affinity is muted.";

  return {
    game: game.name,
    baselineHours,
    baselineAddictiveness: baselineAdd,
    baselineGrade,
    personalizedHours: hYou,
    personalizedAddictiveness: aYou,
    personalizedGrade: grade,
    hoursMultiplier: Math.round(hoursMult * 1000) / 1000,
    affinity: Math.round(affinity * 1000) / 1000,
    pacingFit: Math.round(pacingFit * 1000) / 1000,
    complexityFit: Math.round(complexityFit * 1000) / 1000,
    multiplayerFit: Math.round(mpFit * 1000) / 1000,
    calendarWeeks: Math.round(weeks * 10) / 10,
    calendarMonths: Math.round(months * 10) / 10,
    horizonWeeks: Math.round(horizon * 10) / 10,
    calendarCapped,
    reasons: reasons.slice(0, 6),
    confidenceNote,
  };
}
