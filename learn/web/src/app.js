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
  history: new Map(),
  frontier: 0,
  cursor: 0,
  lookaheadCollapsed: false,
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

function renderSession({ shift = 0 } = {}) {
  const view = state.view;
  const name = view?.session?.name ?? "default";
  $(".session-name").textContent = name;
  $("#context-source").textContent = name;
  const percent = view?.session?.percent_completed ?? 0;
  $("#progress-pct").textContent = `${percent}%`;
  $("#progress-fill").style.width = `${percent}%`;
  renderCard(focusedEntry());
  renderTimeline({ shift });
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
    renderFace(element, type, current.card);
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

/* Thin functional faces for E/R/C/F. They carry content and submit the real
 * Worker answer shapes; visual design follows later. */
function faceTitle(type) {
  return `<h2>${escapeHtml(CARD_NAMES[type] ?? type)}</h2>`;
}

function latinInput(name, label) {
  return `<p><label>${escapeHtml(label)} <input name="${name}" type="text" dir="ltr" autocomplete="off" autocapitalize="none" spellcheck="false"></label></p>`;
}

function hintList(parts) {
  return parts
    .map((part) => {
      const hint = `${part.first_letter}… (${part.length})`;
      return part.hebrew
        ? `<span class="ltr">${escapeHtml(hint)}</span> <span class="he">${escapeHtml(part.hebrew)}</span>`
        : `<span class="ltr">${escapeHtml(hint)}</span>`;
    })
    .join(" · ");
}

function faceMessage(feedback) {
  if (!feedback) {
    return "";
  }
  if (feedback.kind === "elements") {
    return `Elements: ${feedback.correct}/${feedback.total} correct`;
  }
  if (feedback.kind === "retry") {
    return feedback.message;
  }
  if (feedback.kind === "recognize") {
    return feedback.result.correct
      ? "Correct"
      : `Wrong — accepted: ${feedback.result.accepted.join(", ")}`;
  }
  if (feedback.kind === "latin") {
    if (feedback.result.outcome === "correct") {
      return "Correct";
    }
    const label = feedback.result.outcome === "near_miss" ? "Near miss" : "Wrong";
    return `${label} — ${feedback.result.expected}`;
  }
  return "";
}

function renderFace(element, type, view) {
  let form = "";
  if (type === "E") {
    form = `
      <p class="ltr">${escapeHtml(view.latin ?? "")}</p>
      <form id="face-form">
        ${view.rows
          .map(
            (row) => `
          <div>
            <span class="ltr">${escapeHtml(row.latin_forms.join(" / "))}</span>
            <select name="${escapeHtml(row.element_id)}">
              <option value="">—</option>
              ${row.options
                .map(
                  (option) =>
                    `<option value="${escapeHtml(option)}">${escapeHtml(option)}</option>`,
                )
                .join("")}
            </select>
          </div>`,
          )
          .join("")}
        <p><button type="submit">Check</button></p>
      </form>`;
  } else if (type === "R") {
    form = `
      <p class="he">${escapeHtml(view.hebrew ?? "")}</p>
      <p>${escapeHtml(view.family ?? "")}</p>
      <form id="face-form">
        ${view.options
          .map(
            (option) => `
          <div>
            <label>
              <input type="radio" name="choice" value="${escapeHtml(option.species_id)}">
              <span class="ltr">${escapeHtml(option.latin)}</span>
            </label>
          </div>`,
          )
          .join("")}
        <p><button type="submit">Check</button></p>
      </form>`;
  } else if (type === "C") {
    form = `
      <p class="he">${escapeHtml(view.hebrew ?? "")}</p>
      <p>Genus: ${hintList(view.genus_parts)}</p>
      <p>Epithet: ${hintList(view.epithet_parts)}</p>
      <form id="face-form">
        ${latinInput("response", "Latin name")}
        <p><button type="submit">Check</button></p>
      </form>`;
  } else {
    form = `
      <p class="he">${escapeHtml(view.hebrew ?? "")}</p>
      <form id="face-form">
        ${latinInput("response", "Latin name")}
        <p><button type="submit">Check</button></p>
      </form>`;
  }
  element.innerHTML = `${faceTitle(type)}${form}`;
  $("#face-form").addEventListener("submit", submitFace);
  const input = element.querySelector('input[name="response"]');
  if (input) {
    input.focus();
  }
}

async function submitFace(event) {
  event.preventDefault();
  const current = focusedEntry();
  if (!current) {
    return;
  }
  const form = event.currentTarget;
  const body = { card_uid: current.uid, action: "answer" };
  if (current.type === "E") {
    body.choices = {};
    for (const row of current.card.rows) {
      const select = form.elements.namedItem(row.element_id);
      if (!select || !select.value) {
        showStatus("Choose an answer for every element.");
        return;
      }
      body.choices[row.element_id] = select.value;
    }
  } else if (current.type === "R") {
    const choice = form.querySelector('input[name="choice"]:checked');
    if (!choice) {
      showStatus("Choose an answer.");
      return;
    }
    body.choice = choice.value;
  } else {
    const response = form.elements.namedItem("response").value.trim();
    if (!response) {
      showStatus("Type the Latin name.");
      return;
    }
    body.response = response;
  }

  clearStatus();
  try {
    const result = await api(
      `/app/sessions/${encodeURIComponent(state.sessionId)}/answer?lookahead=${LOOKAHEAD}`,
      { method: "POST", body },
    );
    applyAnswer(result, current);
  } catch (error) {
    showStatus(error.message);
  }
}

function maxCursor() {
  if (!state.view) {
    return 0;
  }
  return state.view.current
    ? state.frontier
    : Math.max(0, state.frontier - 1);
}

function currentEntry() {
  const current = state.view?.current;
  if (!current) {
    return null;
  }
  return {
    index: state.frontier,
    kind: "current",
    type: current.type,
    hebrew: current.hebrew,
    uid: current.uid,
    card: current.card,
    attempt: current.attempt,
    retry: current.retry,
  };
}

function focusedEntry() {
  if (!state.view) {
    return null;
  }
  if (state.cursor === state.frontier) {
    return currentEntry();
  }
  return state.history.get(state.cursor) ?? null;
}

function timelineEntry(index) {
  if (index < 0) {
    return null;
  }
  if (index < state.frontier) {
    return state.history.get(index) ?? null;
  }
  if (index === state.frontier) {
    return currentEntry();
  }
  const item = state.view?.lookahead?.[index - state.frontier - 1];
  if (!item) {
    return null;
  }
  return { index, kind: "future", type: item.type, hebrew: item.hebrew };
}

function syncTimeline({ follow = false, reset = false } = {}) {
  const view = state.view;
  if (!view) {
    return;
  }
  if (reset) {
    state.history.clear();
  }
  state.frontier = view.session.history_size;
  for (const entry of view.history_tail ?? []) {
    state.history.set(entry.index, { ...entry, kind: "history" });
  }
  for (const index of [...state.history.keys()]) {
    if (index >= state.frontier) {
      state.history.delete(index);
    }
  }
  const max = maxCursor();
  state.cursor = follow
    ? max
    : Math.max(0, Math.min(state.cursor, max));
}

async function loadOlderHistory() {
  const loaded = [...state.history.keys()];
  if (loaded.length === 0) {
    return;
  }
  const earliest = Math.min(...loaded);
  if (earliest <= 0) {
    return;
  }
  const data = await api(
    `/app/sessions/${encodeURIComponent(state.sessionId)}/history` +
      `?before=${earliest}&limit=12`,
  );
  for (const entry of data.entries ?? []) {
    state.history.set(entry.index, { ...entry, kind: "history" });
  }
}

async function stepCursor(delta) {
  const target = state.cursor + delta;
  if (target < 0 || target > maxCursor()) {
    return;
  }
  if (delta < 0) {
    const loaded = [...state.history.keys()];
    const earliest = loaded.length ? Math.min(...loaded) : 0;
    if (target - 3 < earliest && earliest > 0) {
      try {
        await loadOlderHistory();
      } catch (error) {
        showStatus(error.message);
        return;
      }
    }
  }
  state.cursor = target;
  renderSession({ shift: delta });
}

function timelineCard(entry, index, distance = 0) {
  if (!entry) {
    return "";
  }
  const kind = entry.kind ?? "history";
  const depth = Math.min(Math.abs(distance), 3);
  const type = escapeHtml(entry.type);
  const name = escapeHtml(entry.hebrew ?? "");
  const label = escapeHtml(`${entry.type} · ${entry.hebrew ?? ""}`);
  return (
    `<span class="timeline-card timeline-card--${kind} timeline-card--d${depth}" ` +
    `data-index="${index}" style="--type: var(--t-${type})" title="${label}">` +
    `<span class="timeline-letter">(${type})</span>` +
    `<span class="timeline-name he">${name}</span></span>`
  );
}

function timelineCell(index, entry) {
  return (
    `<span class="timeline-cell" data-index="${index}">` +
    `${timelineCard(entry, index, index - state.cursor)}</span>`
  );
}

function stepIcon(direction) {
  const path = direction === "prev" ? "M15 5 8 12l7 7" : "M9 5l7 7-7 7";
  return (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
    `<path d="${path}"/></svg>`
  );
}

function monocularIcon() {
  // Angled field scope: eyepiece up-left, tapered body, objective ring.
  return (
    '<svg class="monocular" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" ' +
    'stroke-linejoin="round">' +
    '<rect x="-3.4" y="-1.4" width="6.8" height="2.8" rx="1" ' +
    'transform="translate(4.6 9.4) rotate(45)"/>' +
    '<path d="M5.2 9.9 L17.3 7.9 Q18.6 7.8 18.6 9.1 V14.9 ' +
    'Q18.6 16.2 17.3 16.1 L5.2 14.1 Q4.1 13.9 4.1 12.9 V11.1 ' +
    'Q4.1 10.1 5.2 9.9 Z" fill="var(--bg)"/>' +
    '<ellipse cx="18.6" cy="12" rx="1.9" ry="4.6"/>' +
    '<path d="M10.8 9 V15"/>' +
    '</svg>'
  );
}

const REDUCED_MOTION =
  window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
const TIMELINE_SHIFT_MS = 300;
const TIMELINE_SHIFT_EASING = "cubic-bezier(.22,.61,.36,1)";

function renderTimeline({ shift = 0 } = {}) {
  const container = $("#timeline");
  if (!container || !state.view) {
    return;
  }
  const collapsed = state.lookaheadCollapsed;
  const animate =
    shift !== 0 &&
    !collapsed &&
    !REDUCED_MOTION &&
    container.querySelector(".timeline-cell") !== null;
  const containerRect = container.getBoundingClientRect();
  let pitch = 0;
  const previous = new Map();
  if (animate) {
    const cells = container.querySelectorAll(".timeline-cell");
    if (cells.length >= 2) {
      pitch =
        cells[1].getBoundingClientRect().left -
        cells[0].getBoundingClientRect().left;
    }
    for (const node of container.querySelectorAll(".timeline-card[data-index]")) {
      previous.set(Number(node.dataset.index), {
        rect: node.getBoundingClientRect(),
        node,
        side: node.closest(".timeline-cell") !== null,
      });
    }
  }
  const left = [-3, -2, -1]
    .map((offset) => timelineCell(state.cursor + offset, timelineEntry(state.cursor + offset)))
    .join("");
  const right = [1, 2, 3]
    .map((offset) => timelineCell(state.cursor + offset, timelineEntry(state.cursor + offset)))
    .join("");
  const focus = timelineEntry(state.cursor);
  const canPrev = state.cursor > 0;
  const canNext = state.cursor < maxCursor();
  const lensBody = collapsed
    ? monocularIcon()
    : timelineCard(focus, state.cursor, 0);
  container.classList.toggle("is-collapsed", collapsed);
  container.innerHTML = `
    ${left}
    <span class="timeline-center">
      <button class="timeline-step" id="timeline-prev" type="button" aria-label="Previous card" ${canPrev ? "" : "disabled"}>${stepIcon("prev")}</button>
      <button class="lens${collapsed ? " lens--collapsed" : ""}" id="timeline-lens" type="button" aria-expanded="${!collapsed}" title="${collapsed ? "Expand look-ahead" : "Collapse look-ahead"}" style="--type: var(--t-${escapeHtml(focus?.type ?? "L")})">
        ${lensBody}
      </button>
      <button class="timeline-step" id="timeline-next" type="button" aria-label="Next card" ${canNext ? "" : "disabled"}>${stepIcon("next")}</button>
    </span>
    ${right}
  `;
  $("#timeline-prev").addEventListener("click", () => stepCursor(-1));
  $("#timeline-next").addEventListener("click", () => stepCursor(1));
  $("#timeline-lens").addEventListener("click", () => {
    state.lookaheadCollapsed = !state.lookaheadCollapsed;
    renderTimeline();
  });
  if (!animate || pitch <= 0) {
    return;
  }
  // FLIP: every card that is still visible starts at its old position and
  // size; new ones enter one slot off the edge; the card that left the window
  // slides out and fades. The centre slot does not move, so the strip reads
  // as sliding and growing/shrinking behind the focus.
  const seen = new Set();
  for (const node of container.querySelectorAll(".timeline-card[data-index]")) {
    const index = Number(node.dataset.index);
    seen.add(index);
    const rect = node.getBoundingClientRect();
    const old = previous.get(index);
    let dx = shift * pitch;
    let scale = "";
    if (old) {
      dx =
        old.rect.left + old.rect.width / 2 -
        (rect.left + rect.width / 2);
      const sx = old.rect.width / rect.width;
      const sy = old.rect.height / rect.height;
      if (Math.abs(sx - 1) > 0.01 || Math.abs(sy - 1) > 0.01) {
        scale = ` scale(${sx}, ${sy})`;
      }
    }
    node.animate(
      [
        { transform: `translateX(${dx}px)${scale}` },
        { transform: "none" },
      ],
      { duration: TIMELINE_SHIFT_MS, easing: TIMELINE_SHIFT_EASING },
    );
  }
  for (const [index, old] of previous) {
    if (seen.has(index) || !old.side) {
      continue;
    }
    const clone = old.node.cloneNode(true);
    Object.assign(clone.style, {
      position: "absolute",
      left: `${old.rect.left - containerRect.left}px`,
      top: `${old.rect.top - containerRect.top}px`,
      width: `${old.rect.width}px`,
      height: `${old.rect.height}px`,
      margin: "0",
      pointerEvents: "none",
    });
    container.appendChild(clone);
    const animation = clone.animate(
      [
        { transform: "translateX(0)", opacity: getComputedStyle(clone).opacity },
        { transform: `translateX(${-shift * pitch}px)`, opacity: 0 },
      ],
      { duration: TIMELINE_SHIFT_MS, easing: TIMELINE_SHIFT_EASING },
    );
    animation.addEventListener("finish", () => clone.remove());
  }
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

function applyAnswer(result, submitted) {
  const wasFrontier = submitted.index === state.frontier;
  const previousFrontier = state.frontier;
  state.view = result.session;
  syncTimeline({ follow: wasFrontier });
  const shift = state.frontier > previousFrontier ? 1 : 0;
  renderSession({ shift });
  const message = faceMessage(result.feedback);
  if (message) {
    showStatus(message);
  }
}

async function next() {
  const focus = focusedEntry();
  if (!focus || focus.type !== "L") {
    return;
  }
  clearStatus();
  try {
    const result = await api(
      `/app/sessions/${encodeURIComponent(state.sessionId)}/answer?lookahead=${LOOKAHEAD}`,
      {
        method: "POST",
        body: {
          card_uid: focus.uid,
          action: "advance",
        },
      },
    );
    applyAnswer(result, focus);
  } catch (error) {
    showStatus(error.message);
  }
}

async function loadSession() {
  state.view = await api(
    `/app/sessions/${encodeURIComponent(state.sessionId)}?lookahead=${LOOKAHEAD}`,
  );
  syncTimeline({ follow: true, reset: true });
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
