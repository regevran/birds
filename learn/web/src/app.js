/* Browser client: reads the Worker; the Worker owns the data and the queue. */

const API_BASE = (
  document.querySelector('meta[name="birds-api"]')?.content ||
  "http://localhost:8787"
).replace(/\/+$/, "");
const MEDIA_VERSION =
  document.querySelector('meta[name="birds-media-version"]')?.content || "v1";
const TOKEN_KEY = "birds.token";
const SESSION_KEY = "birds.session";
const LOOKAHEAD = 7;

const CARD_NAMES = {
  L: "Learn",
  E: "Elements",
  R: "Recognize",
  C: "Construct",
  F: "Produce",
};

const state = {
  sessionId: null,
  view: null,
  search: { query: "", birds: [], elements: [], selected: null },
  selectedToken: null,
  searchRequest: 0,
};

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[char],
  );
}

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

async function api(path, { method = "GET", body } = {}) {
  const headers = {};
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }
  if (!response.ok) {
    const error = new Error(data?.message || `HTTP ${response.status}`);
    error.status = response.status;
    error.code = data?.error;
    throw error;
  }
  return data;
}

function showStatus(message) {
  const element = $("#status");
  element.textContent = message;
  element.classList.add("visible");
}

function clearStatus() {
  $("#status").classList.remove("visible");
}

function groupParts(parts, latin) {
  const words = String(latin ?? "").trim().split(/\s+/);
  const groups = [];
  let index = 0;
  for (const word of words) {
    const group = [];
    let length = 0;
    while (index < parts.length && length < word.length) {
      group.push(parts[index]);
      length += parts[index].latin.length;
      index += 1;
    }
    groups.push(group);
  }
  if (index < parts.length) {
    groups.push(parts.slice(index));
  }
  return groups;
}

function illustration(speciesId, alt) {
  if (!speciesId) {
    return "";
  }
  const file = encodeURIComponent(speciesId);
  const src =
    `${API_BASE}/media/illustrations/${encodeURIComponent(MEDIA_VERSION)}` +
    `/${file}.webp`;
  return `<img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}" loading="lazy" decoding="async">`;
}

function factline(view) {
  const parts = [view.order];
  if (view.status) {
    parts.push(view.status);
  }
  const categories = view.status_categories ?? [];
  if (categories.length > 0) {
    parts.push(categories.join(", "));
  }
  return parts.filter(Boolean).join(" · ");
}

function renderSession() {
  const view = state.view;
  const name = view?.session?.name ?? "default";
  $(".session-name").textContent = name;
  $("#context-source").textContent = name;
  const percent = view?.session?.percent_completed ?? 0;
  $("#progress-pct").textContent = `${percent}%`;
  $("#progress-fill").style.width = `${percent}%`;
  renderCard(view?.current);
  renderLookahead(view?.lookahead ?? []);
}

function renderCard(current) {
  const element = $("#card");
  if (!current) {
    element.className = "card";
    element.style.setProperty("--type", "var(--t-L)");
    element.innerHTML = `<div class="card-empty">Session complete.</div>`;
    return;
  }
  const type = current.type;
  element.style.setProperty("--type", `var(--t-${type})`);
  if (type !== "L") {
    element.className = "card";
    const bird = current.card ?? {};
    element.innerHTML = `
      <div class="card-placeholder">
        <span class="ph-type">${escapeHtml(CARD_NAMES[type] ?? type)}</span>
        <span class="ph-bird ltr">${escapeHtml(bird.latin ?? "")}</span>
        <span class="ph-note">Card face pending</span>
      </div>`;
    return;
  }

  element.className = "card lcard";
  const view = current.card;
  const groups = groupParts(view.parts, view.latin);
  element.innerHTML = `
    <div class="card-head">
      <div class="title-he-wrap"><span class="type-mark"></span><span class="card-title-he he">לימוד</span></div>
      <span class="card-title-en">Learn</span>
    </div>
    <div class="family-row">
      <span class="fam-he he">${escapeHtml(view.family_he ?? "")}</span>
      <span class="factline">${escapeHtml(factline(view))}</span>
      <span class="fam-en ltr">${escapeHtml(view.family)}</span>
    </div>
    <div class="card-main-l">
      <figure class="sticker">
        <div class="plate">${illustration(view.species_id, view.english ?? view.latin)}</div>
      </figure>
      <div class="content">
        <div class="latin-line">
          <button class="speak" type="button" aria-label="Speak the Latin name" disabled>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5v5h3.6L13 18V6L7.6 9.5H4z" fill="currentColor"/><path d="M16.2 8.6a4.6 4.6 0 0 1 0 6.8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>
          </button>
          <h1 class="latin"><span class="ltr">${escapeHtml(view.latin)}</span></h1>
        </div>
        <div class="name-pair">
          <span class="he">${escapeHtml(view.hebrew ?? "")}</span>
          <span class="sep">·</span>
          <span class="en-name ltr">${escapeHtml(view.english ?? "")}</span>
        </div>
        <div class="decomp" dir="ltr">
          ${groups
            .map(
              (group) => `
            <div class="word-group">
              ${group
                .map(
                  (part) => `
                <div class="part-col">
                  <span class="part">${escapeHtml(part.latin)}</span>
                  <span class="gloss">${escapeHtml(part.english)}</span>
                  <span class="gloss-he he">${escapeHtml(part.hebrew)}</span>
                  <span class="theme">(${escapeHtml(part.theme)})</span>
                </div>`,
                )
                .join("")}
            </div>`,
            )
            .join("")}
        </div>
      </div>
    </div>
    <div class="card-foot">
      <button class="next" id="next" type="button">Next <span class="arrow">→</span></button>
    </div>`;
  $("#next").addEventListener("click", next);
}

function renderLookahead(items) {
  const track = $("#la-track");
  track.innerHTML = "";
  items.forEach((item, index) => {
    if (index > 0) {
      const arrow = document.createElement("span");
      arrow.className = "la-arrow";
      arrow.textContent = "→";
      track.append(arrow);
    }
    const bird = document.createElement("span");
    bird.className = "la-bird";
    bird.style.setProperty("--type", `var(--t-${item.type})`);
    bird.textContent = item.hebrew ?? "";
    track.append(bird);
  });
}

let searchTimer = 0;

function clearSearch() {
  window.clearTimeout(searchTimer);
  state.searchRequest += 1;
  state.search = { query: "", birds: [], elements: [], selected: null };
  state.selectedToken = null;
  const input = $("#search-input");
  if (input.value !== "") {
    input.value = "";
  }
  renderEmptySearch();
}

function renderEmptySearch() {
  $("#results").innerHTML = `<div class="results-empty">Type to search birds.</div>`;
  $("#panel").innerHTML = "";
}

function onSearchInput(event) {
  window.clearTimeout(searchTimer);
  const query = event.target.value;
  if (query.trim() === "") {
    clearSearch();
    return;
  }
  searchTimer = window.setTimeout(() => {
    runSearch(query);
  }, 220);
}

async function runSearch(query) {
  clearStatus();
  const request = (state.searchRequest += 1);
  try {
    const data = await api("/app/birds", {
      method: "POST",
      body: { q: query },
    });
    if (request !== state.searchRequest) {
      return;
    }
    state.search = {
      query,
      birds: data.birds,
      elements: data.elements,
      selected: data.birds[0] ?? null,
    };
    state.selectedToken = state.search.selected?.tokens?.[0] ?? null;
    renderResults();
    renderPanel();
  } catch (error) {
    if (request === state.searchRequest) {
      showStatus(error.message);
    }
  }
}

function renderResults() {
  const container = $("#results");
  const birds = state.search.birds;
  if (birds.length === 0) {
    container.innerHTML = `<div class="results-empty">No birds match this search.</div>`;
    return;
  }
  const terms = String(state.search.query ?? "")
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  container.innerHTML = birds
    .map(
      (bird, index) => `
    <div class="result-row${bird === state.search.selected ? " selected" : ""}" data-index="${index}">
      <span class="r-latin ltr">${highlight(bird.latin, terms)}${matchNote(bird, terms)}</span>
      <span class="r-order ltr">${highlight(bird.order, terms)}</span>
      <span class="r-family-cell">
        <span class="r-family ltr">${highlight(bird.family, terms)}</span>
        <span class="r-family-he he">${highlight(bird.family_he, terms)}</span>
      </span>
      <span class="r-en ltr">${highlight(bird.english ?? "", terms)}</span>
      <span class="r-he he">${highlight(bird.hebrew ?? "", terms)}</span>
    </div>`,
    )
    .join("");
  for (const row of container.querySelectorAll(".result-row")) {
    row.addEventListener("click", () => {
      state.search.selected = birds[Number(row.dataset.index)];
      state.selectedToken = state.search.selected?.tokens?.[0] ?? null;
      renderResults();
      renderPanel();
    });
  }
}

/* A row that matched only on etymology or on the species id has nothing to
 * highlight; say why it is here. */
const DISPLAYED_FIELDS = new Set([
  "latin",
  "order",
  "family",
  "family_he",
  "english",
  "hebrew",
]);

function matchNote(bird, terms) {
  const visibleName = bird.matched.some(
    (match) =>
      match.kind === "name" &&
      match.texts.some((text) => DISPLAYED_FIELDS.has(text.field)),
  );
  if (visibleName) {
    return "";
  }
  const parts = [];
  for (const match of bird.matched) {
    if (match.kind === "name") {
      for (const text of match.texts) {
        parts.push(
          `<span class="why-label">${escapeHtml(text.field)}</span> ${highlight(text.text, terms)}`,
        );
      }
    } else if (match.kind === "element") {
      const texts = [
        ...new Set(match.texts.map((text) => text.text).filter(Boolean)),
      ];
      if (texts.length > 0) {
        parts.push(
          `<span class="why-label">element</span> ${highlight(texts.join(", "), terms)} <span class="why-id">(${escapeHtml(match.element_id)})</span>`,
        );
      }
    }
  }
  if (parts.length === 0) {
    return "";
  }
  return `<span class="r-why" dir="auto">${parts.join(" · ")}</span>`;
}

/* Mark every occurrence of the query terms, so a result explains itself. */
function highlight(value, terms) {
  const text = String(value ?? "");
  if (!text || terms.length === 0) {
    return escapeHtml(text);
  }
  const lowered = text.toLowerCase();
  const ranges = [];
  for (const term of terms) {
    let from = 0;
    let at = lowered.indexOf(term, from);
    while (at !== -1) {
      ranges.push({ start: at, end: at + term.length });
      from = at + term.length;
      at = lowered.indexOf(term, from);
    }
  }
  if (ranges.length === 0) {
    return escapeHtml(text);
  }
  ranges.sort((left, right) => left.start - right.start);
  const merged = [];
  for (const range of ranges) {
    const last = merged[merged.length - 1];
    if (last && range.start <= last.end) {
      last.end = Math.max(last.end, range.end);
    } else {
      merged.push({ ...range });
    }
  }
  let out = "";
  let cursor = 0;
  for (const range of merged) {
    out += escapeHtml(text.slice(cursor, range.start));
    out += `<mark class="match">${escapeHtml(text.slice(range.start, range.end))}</mark>`;
    cursor = range.end;
  }
  return out + escapeHtml(text.slice(cursor));
}

const PART_KINDS = new Set(["part"]);
const HEBREW_KINDS = new Set(["hebrew", "hebrew_word", "family_he"]);

function renderPanel() {
  const bird = state.search.selected;
  const panel = $("#panel");
  if (!bird) {
    panel.innerHTML = "";
    return;
  }
  const tokens = bird.tokens ?? [];
  if (!state.selectedToken && tokens.length > 0) {
    state.selectedToken = tokens[0];
  }
  const selected = state.selectedToken;
  panel.innerHTML = `
    <div class="panel-info">
      <span class="panel-kicker">selected bird</span>
      <div class="panel-latin ltr">${escapeHtml(bird.latin)}</div>
      <div class="panel-common"><span class="en ltr">${escapeHtml(bird.english ?? "")}</span> · <span class="he">${escapeHtml(bird.hebrew ?? "")}</span></div>
      <span class="panel-label panel-label--parts">parts</span>
      <div class="token-row">
        ${tokens
          .map((token, index) => {
            const classes = ["token"];
            if (PART_KINDS.has(token.kind)) {
              classes.push("token--part");
            }
            if (HEBREW_KINDS.has(token.kind)) {
              classes.push("he");
            }
            if (selected && token.kind === selected.kind && token.text === selected.text) {
              classes.push("selected");
            }
            return `<button class="${classes.join(" ")}" type="button" data-index="${index}">${escapeHtml(token.text)}</button>`;
          })
          .join("")}
      </div>
      <div class="panel-create">
        <span class="panel-label">create from <b class="sel-name">${escapeHtml(selected?.text ?? "—")}</b></span>
        <div class="create-grid">
          <button class="create-btn" type="button" disabled style="--type: var(--t-L)"><span class="dot"></span>Learn</button>
          <button class="create-btn" type="button" disabled style="--type: var(--t-E)"><span class="dot"></span>Elements</button>
          <button class="create-btn" type="button" disabled style="--type: var(--t-R)"><span class="dot"></span>Recognize</button>
          <button class="create-btn" type="button" disabled style="--type: var(--t-C)"><span class="dot"></span>Construct</button>
          <button class="create-btn" type="button" disabled style="--type: var(--t-F)"><span class="dot"></span>Produce</button>
          <button class="create-btn" type="button" disabled><span class="dot dot--neutral"></span>Session</button>
        </div>
      </div>
    </div>
    <figure class="panel-sticker">
      <div class="plate">${illustration(bird.species_id, bird.english ?? bird.latin)}</div>
    </figure>`;
  for (const button of panel.querySelectorAll(".token")) {
    button.addEventListener("click", () => {
      state.selectedToken = tokens[Number(button.dataset.index)];
      renderPanel();
    });
  }
}

async function next() {
  if (!state.view?.current) {
    return;
  }
  clearStatus();
  try {
    const result = await api(
      `/app/sessions/${encodeURIComponent(state.sessionId)}/answer?lookahead=${LOOKAHEAD}`,
      {
        method: "POST",
        body: {
          card_uid: state.view.current.uid,
          action: "advance",
        },
      },
    );
    state.view = result.session;
    renderSession();
  } catch (error) {
    showStatus(error.message);
  }
}

async function loadSession() {
  state.view = await api(
    `/app/sessions/${encodeURIComponent(state.sessionId)}?lookahead=${LOOKAHEAD}`,
  );
  renderSession();
}

async function boot() {
  renderEmptySearch();
  $("#search-input").addEventListener("input", onSearchInput);
  $("#search-input").addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      clearSearch();
    }
  });
  $("#search-clear").addEventListener("click", clearSearch);
  $("#binocular").addEventListener("click", () => {
    $("#lookahead").classList.toggle("collapsed");
  });
  if (!getToken()) {
    showStatus("No token. Set localStorage['birds.token'] and reload.");
    return;
  }
  try {
    const { sessions } = await api("/app/sessions");
    const stored = localStorage.getItem(SESSION_KEY);
    const selected =
      sessions.find((session) => session.session_id === stored) ??
      sessions.find((session) => session.session_id === "default") ??
      sessions[0];
    if (!selected) {
      throw new Error("No sessions available.");
    }
    state.sessionId = selected.session_id;
    localStorage.setItem(SESSION_KEY, state.sessionId);
    await loadSession();
  } catch (error) {
    showStatus(error.message);
  }
}

boot();
