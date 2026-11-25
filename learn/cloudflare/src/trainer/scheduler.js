/* Profile/session state and the pure queue scheduler.
 *
 * A session keeps three ordered structures:
 *   pending  per-bird groups of card specs not yet in the queue
 *   queue    materialised unseen cards; queue[0] is the frontier
 *   history  completed cards in timeline order
 *
 * A live answer consumes queue[0] into history. A correct redo of a history
 * card records only; a wrong redo truncates the timeline after that card and
 * pours every invalidated card back into pending. There is no passing or
 * review-level state: a bird may appear again in a later session.
 *
 * This module owns the transition rules. It mutates the session and profile
 * documents, like a small in-memory state machine; the Worker loads them from
 * R2, calls one function, and saves them back.
 */

import { hashSeed, randomInt, seededRandom, shuffle } from "./random.js";
import { cardView } from "./views.js";

export const SCHEMA_VERSION = 2;
export const APP_VERSION = "0.1.0";
export const DEFAULT_SETTINGS = Object.freeze({
  active_cap: 7,
  lookahead_target: 50,
  out_of_scope_reviews: true,
  show_bridge: true,
});
export const DEFAULT_FILTER = Object.freeze({
  families: [],
  orders: [],
  genera: [],
  statuses: ["regular", "introduced"],
  search: "",
});

const CHAIN_WITH_PARTS = ["L", "E", "R", "C", "F"];
const CHAIN_WITHOUT_PARTS = ["L", "R", "C", "F"];
const FALLBACK = { R: "L", C: "R", F: "C" };
const LOOKAHEAD = 5;
const HISTORY_TAIL = 12;

export class SchedulerError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "SchedulerError";
    this.code = code;
  }
}

function nowIso(now = () => new Date()) {
  return now().toISOString();
}

function newCardUid() {
  const bytes = new Uint8Array(6);
  crypto.getRandomValues(bytes);
  return (
    "c_" +
    [...bytes]
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("")
  );
}

function newSeed() {
  const value = new Uint32Array(1);
  crypto.getRandomValues(value);
  return value[0] % 1_000_000_000;
}

function newSessionId(now = () => new Date()) {
  const stamp = now()
    .toISOString()
    .replace(/[-:]/g, "")
    .replace("T", "-")
    .slice(0, 13);
  const bytes = new Uint8Array(2);
  crypto.getRandomValues(bytes);
  return (
    stamp +
    "-" +
    [...bytes]
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("")
  );
}

function normalizedSettings(settings = {}) {
  const merged = { ...DEFAULT_SETTINGS, ...(settings ?? {}) };
  const cap = Number(merged.active_cap);
  if (!Number.isInteger(cap) || cap < 1) {
    throw new SchedulerError("invalid_settings", "active_cap must be positive");
  }
  return {
    active_cap: cap,
    lookahead_target: Number(merged.lookahead_target) || 50,
    out_of_scope_reviews: Boolean(merged.out_of_scope_reviews),
    show_bridge: Boolean(merged.show_bridge),
  };
}

function normalizedFilter(filter = {}) {
  filter = filter ?? {};
  return {
    families: [...(filter.families ?? [])],
    orders: [...(filter.orders ?? [])],
    genera: [...(filter.genera ?? [])],
    statuses: [...(filter.statuses ?? DEFAULT_FILTER.statuses)],
    search: String(filter.search ?? ""),
  };
}

/* The session's provenance, e.g. 'search "acrocephalus-agricola" · status:
 * accidental'. Stored at creation as a string, so a future custom series can
 * set its own origin without the clients knowing its structure.
 */
export function formatCreatedFrom(filter = {}) {
  const normalized = normalizedFilter(filter);
  const parts = [];
  const search = normalized.search.trim();
  if (search) {
    parts.push(`search "${search}"`);
  }
  if (normalized.families.length > 0) {
    parts.push(`family: ${normalized.families.join(", ")}`);
  }
  if (normalized.orders.length > 0) {
    parts.push(`order: ${normalized.orders.join(", ")}`);
  }
  if (normalized.genera.length > 0) {
    parts.push(`genus: ${normalized.genera.join(", ")}`);
  }
  const defaultStatuses = new Set(DEFAULT_FILTER.statuses);
  const sameAsDefault =
    normalized.statuses.length === DEFAULT_FILTER.statuses.length &&
    normalized.statuses.every((status) => defaultStatuses.has(status));
  if (normalized.statuses.length > 0 && !sameAsDefault) {
    parts.push(`status: ${normalized.statuses.join(", ")}`);
  }
  return parts.join(" · ");
}

export function activeCapOf(session) {
  return session.settings?.active_cap ?? DEFAULT_SETTINGS.active_cap;
}

export function createProfile({
  profileId,
  name = profileId,
  settings = {},
  now = () => new Date(),
} = {}) {
  if (!profileId) {
    throw new SchedulerError("invalid_profile", "profile_id is required");
  }
  const stamp = nowIso(now);
  return {
    schema_version: SCHEMA_VERSION,
    app_version: APP_VERSION,
    profile_id: profileId,
    name,
    created_at: stamp,
    updated_at: stamp,
    settings: normalizedSettings(settings),
    global_counter: 0,
  };
}

export function matchesFilter(bird, filter) {
  if (filter.families.length > 0 && !filter.families.includes(bird.family)) {
    return false;
  }
  if (filter.orders.length > 0 && !filter.orders.includes(bird.order)) {
    return false;
  }
  if (filter.genera.length > 0 && !filter.genera.includes(bird.genus)) {
    return false;
  }
  if (
    filter.statuses.length > 0 &&
    !filter.statuses.some((status) =>
      bird.status_categories.includes(status),
    )
  ) {
    return false;
  }
  const terms = filter.search.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length > 0) {
    const haystack = [
      bird.species_id,
      bird.latin,
      bird.english,
      bird.hebrew,
      bird.family,
      bird.family_he,
      bird.order,
    ]
      .join(" ")
      .toLowerCase();
    if (!terms.every((term) => haystack.includes(term))) {
      return false;
    }
  }
  return true;
}

export function eligibleBirds(catalog, filter) {
  return catalog.birds.filter(
    (bird) => bird.has_hebrew && matchesFilter(bird, filter),
  );
}

export function activeCount(session) {
  return new Set(session.queue.map((card) => card.species_id)).size;
}

export function completionPercent(session) {
  const total = Number(session.initial_pool_size) || 0;
  if (total <= 0) {
    return session.queue.length === 0 && session.pending.length === 0 ? 100 : 0;
  }
  const done = total - session.pending.length - activeCount(session);
  return Math.max(0, Math.min(100, Math.floor((done / total) * 100)));
}

export function currentCard(session) {
  return session.queue[0] ?? null;
}

function cardSeed(sessionSeed, counter, speciesId, type, index) {
  return (
    hashSeed(`${sessionSeed}:${counter}:${speciesId}:${type}:${index}`) %
    1_000_000_000
  );
}

function chainSpecs(bird) {
  const types = bird.has_parts ? CHAIN_WITH_PARTS : CHAIN_WITHOUT_PARTS;
  return types.map((type) => ({ type }));
}

function cardSpec(card) {
  return {
    type: card.type,
    attempt: card.attempt,
    retry: card.retry,
    hint_level: card.hint_level,
  };
}

function buildCards(session, profile, group, { uid = newCardUid } = {}) {
  return group.cards.map((spec, index) => ({
    uid: uid(),
    species_id: group.species_id,
    type: spec.type,
    attempt: spec.attempt ?? 1,
    seed: cardSeed(
      session.seed,
      profile.global_counter,
      group.species_id,
      spec.type,
      index,
    ),
    hint_level: spec.hint_level ?? 0,
    retry: Boolean(spec.retry),
    revealed: false,
  }));
}

function interleaveChains(chains, next) {
  const remaining = chains.map((chain) => [...chain]);
  const result = [];
  while (remaining.some((chain) => chain.length > 0)) {
    const index = Math.floor(next() * remaining.length);
    if (remaining[index].length === 0) {
      continue;
    }
    result.push(remaining[index].shift());
  }
  return result;
}

function setStatus(session) {
  session.status =
    session.queue.length === 0 && session.pending.length === 0
      ? "completed"
      : "active";
}

function initialFill(catalog, profile, session, options = {}) {
  const chains = [];
  while (
    chains.length < session.settings.active_cap &&
    session.pending.length > 0
  ) {
    const group = session.pending.shift();
    chains.push(buildCards(session, profile, group, options));
  }
  session.queue = interleaveChains(
    chains,
    seededRandom(`${session.seed}:initial`),
  );
  setStatus(session);
}

function insertChain(session, chain, next) {
  if (chain.length === 0) {
    return;
  }
  if (session.queue.length === 0) {
    session.queue.push(...chain);
    return;
  }

  const existing = session.queue;
  const head = Math.min(existing.length, randomInt(next, 5, 12));
  const result = existing.slice(0, head);
  result.push(chain[0]);
  let queueIndex = head;
  let chainIndex = 1;
  while (queueIndex < existing.length || chainIndex < chain.length) {
    if (chainIndex >= chain.length) {
      result.push(existing[queueIndex]);
      queueIndex += 1;
    } else if (queueIndex >= existing.length) {
      result.push(chain[chainIndex]);
      chainIndex += 1;
    } else if (next() < 0.5) {
      result.push(existing[queueIndex]);
      queueIndex += 1;
    } else {
      result.push(chain[chainIndex]);
      chainIndex += 1;
    }
  }
  session.queue = result;
}

function reinsertAhead(session, cards, next) {
  if (cards.length === 0) {
    return;
  }
  let position = Math.min(
    session.queue.length,
    randomInt(next, 30, 50),
  );
  session.queue.splice(position, 0, cards[0]);
  position += 1;
  for (let index = 1; index < cards.length; index += 1) {
    position = Math.min(
      session.queue.length,
      position + randomInt(next, 2, 8),
    );
    session.queue.splice(position, 0, cards[index]);
    position += 1;
  }
}

function takeLaterCards(session, speciesId) {
  const later = session.queue.filter(
    (card) => card.species_id === speciesId,
  );
  session.queue = session.queue.filter(
    (card) => card.species_id !== speciesId,
  );
  return later;
}

function hardFailChain(card, uid = newCardUid) {
  const fallback = FALLBACK[card.type];
  if (!fallback) {
    return [];
  }
  const fresh = {
    ...card,
    uid: uid(),
    type: fallback,
    attempt: 1,
    retry: false,
    revealed: false,
    seed: hashSeed(`${card.seed}:${fallback}`) % 1_000_000_000,
  };
  return [fresh];
}

export function refill(catalog, profile, session, options = {}) {
  const next = seededRandom(
    `${session.seed}:refill:${profile.global_counter}:${session.queue.length}`,
  );
  while (
    activeCount(session) < session.settings.active_cap &&
    session.pending.length > 0
  ) {
    const group = session.pending.shift();
    insertChain(session, buildCards(session, profile, group, options), next);
  }
  setStatus(session);
}

export function createSession(
  catalog,
  profile,
  {
    name = null,
    filter = {},
    settings = {},
    seed = newSeed(),
    sessionId: id = newSessionId(),
    uid,
    now = () => new Date(),
  } = {},
) {
  const normalized = normalizedFilter(filter);
  const chosenSettings = normalizedSettings(settings);
  const chosenSeed = Number.isInteger(seed) ? seed : newSeed();
  const eligible = eligibleBirds(catalog, normalized);
  const groups = eligible.map((bird) => ({
    species_id: bird.species_id,
    cards: chainSpecs(bird),
  }));
  const pending = shuffle(groups, seededRandom(`${chosenSeed}:pool`));
  const stamp = nowIso(now);
  const session = {
    schema_version: SCHEMA_VERSION,
    app_version: APP_VERSION,
    session_id: id,
    profile_id: profile.profile_id,
    name,
    created_at: stamp,
    updated_at: stamp,
    data_version: catalog.dataVersion,
    skill: "he_to_latin",
    status: "active",
    filter: normalized,
    created_from: formatCreatedFrom(normalized), // e.g. 'search "acrocephalus-agricola" · status: accidental'
    settings: chosenSettings,
    seed: chosenSeed,
    initial_pool_size: eligible.length,
    pending,
    queue: [],
    history: [],
    session_card_count: 0,
    paused_review: null,
  };
  initialFill(catalog, profile, session, { uid });
  return session;
}

export function consume(
  catalog,
  profile,
  session,
  result,
  { now = () => new Date(), uid } = {},
) {
  const card = session.queue.shift();
  if (!card) {
    throw new SchedulerError("no_current_card", "the queue is empty");
  }
  profile.global_counter += 1;
  const stamp = nowIso(now);

  if (result === "near_miss") {
    const later = takeLaterCards(session, card.species_id);
    const retryCard = {
      ...card,
      uid: uid ? uid() : newCardUid(),
    };
    reinsertAhead(
      session,
      [retryCard, ...later],
      seededRandom(`${session.seed}:soft:${profile.global_counter}`),
    );
  } else if (result === "wrong" || result === "revealed") {
    const later = takeLaterCards(session, card.species_id);
    const fallback = hardFailChain(card, uid);
    const failed = {
      ...card,
      uid: uid ? uid() : newCardUid(),
      attempt: 1,
      retry: false,
      revealed: false,
      seed: hashSeed(`${card.seed}:failed`) % 1_000_000_000,
    };
    reinsertAhead(
      session,
      [...fallback, failed, ...later],
      seededRandom(`${session.seed}:hard:${profile.global_counter}`),
    );
  } else if (result !== "advance" && result !== "correct") {
    throw new SchedulerError(
      "invalid_result",
      `unknown result ${JSON.stringify(result)}`,
    );
  }

  refill(catalog, profile, session, { uid });
  session.history.push({ card, result, at: stamp });
  session.session_card_count = session.history.length;
  session.updated_at = stamp;
  profile.updated_at = stamp;
  return { card };
}

export function markRetry(session, { now = () => new Date() } = {}) {
  const card = currentCard(session);
  if (!card) {
    throw new SchedulerError("no_current_card", "the queue is empty");
  }
  card.attempt = 2;
  card.retry = true;
  session.updated_at = nowIso(now);
  return card;
}

export function assertCurrent(session, cardUid) {
  const card = currentCard(session);
  if (!card || card.uid !== cardUid) {
    throw new SchedulerError(
      "stale_card",
      "the submitted card is not current",
    );
  }
  return card;
}

/* Where does a submitted uid live? The answer endpoint decides from this,
 * never from a client-declared mode. */
export function classifyCard(session, cardUid) {
  const current = currentCard(session);
  if (current && current.uid === cardUid) {
    return { kind: "current", card: current };
  }
  const index = session.history.findIndex(
    (entry) => entry.card.uid === cardUid,
  );
  if (index >= 0) {
    return { kind: "history", index, card: session.history[index].card };
  }
  if (session.queue.some((card) => card.uid === cardUid)) {
    return { kind: "future" };
  }
  return { kind: "missing" };
}

/* Redo a completed card. Only a wrong answer changes the plan: it truncates
 * the timeline after the card, pours the invalidated cards back into pending,
 * and applies the usual failure retry. Everything else records only. */
export function redo(
  catalog,
  profile,
  session,
  cardUid,
  result,
  { now = () => new Date(), uid } = {},
) {
  const index = session.history.findIndex(
    (entry) => entry.card.uid === cardUid,
  );
  if (index < 0) {
    throw new SchedulerError(
      "stale_card",
      "the submitted card is not in the history",
    );
  }
  const stamp = nowIso(now);

  if (result !== "wrong") {
    session.history[index].result = result;
    session.history[index].at = stamp;
    session.updated_at = stamp;
    profile.updated_at = stamp;
    return { card: session.history[index].card, invalidated: 0 };
  }

  const redone = session.history[index];
  const tail = session.history.slice(index + 1);
  const planned = session.queue;
  const invalidated = tail.length + planned.length;

  session.history = session.history.slice(0, index + 1);
  session.history[index].result = "wrong";
  session.history[index].at = stamp;
  session.queue = [];
  session.session_card_count = session.history.length;

  const buffers = new Map();
  const add = (card) => {
    let cards = buffers.get(card.species_id);
    if (!cards) {
      cards = [];
      buffers.set(card.species_id, cards);
    }
    cards.push(cardSpec(card));
  };
  for (const entry of tail) {
    add(entry.card);
  }
  for (const card of planned) {
    add(card);
  }
  for (const [speciesId, cards] of buffers) {
    const group = session.pending.find(
      (item) => item.species_id === speciesId,
    );
    if (group) {
      group.cards.push(...cards);
    } else {
      session.pending.push({ species_id: speciesId, cards });
    }
  }

  profile.global_counter += 1;

  // Keep the redone bird's remaining cards for its retry batch, and let
  // refill fill the active window with the other returned birds.
  const speciesId = redone.card.species_id;
  const groupIndex = session.pending.findIndex(
    (item) => item.species_id === speciesId,
  );
  const group =
    groupIndex >= 0
      ? session.pending.splice(groupIndex, 1)[0]
      : { species_id: speciesId, cards: [] };
  refill(catalog, profile, session, { uid });

  const fallback = hardFailChain(redone.card, uid);
  const failed = {
    ...redone.card,
    uid: uid ? uid() : newCardUid(),
    attempt: 1,
    retry: false,
    revealed: false,
    seed: hashSeed(`${redone.card.seed}:failed`) % 1_000_000_000,
  };
  const later = buildCards(session, profile, group, { uid });
  reinsertAhead(
    session,
    [...fallback, failed, ...later],
    seededRandom(`${session.seed}:hard:${profile.global_counter}`),
  );
  refill(catalog, profile, session, { uid });

  session.session_card_count = session.history.length;
  session.updated_at = stamp;
  profile.updated_at = stamp;
  return { card: redone.card, invalidated };
}

export function cardFor(catalog, card) {
  return cardView(
    catalog,
    { species_id: card.species_id, card_type: card.type },
    card.seed,
  );
}

export function lookahead(catalog, session, limit = LOOKAHEAD) {
  return session.queue.slice(1, 1 + limit).map((card) => {
    const bird = catalog.bird(card.species_id);
    return {
      type: card.type,
      hebrew: bird.hebrew,
      is_review: false,
      out_of_scope: false,
    };
  });
}

function historyEntryView(catalog, entry, index) {
  return {
    index,
    result: entry.result,
    at: entry.at,
    uid: entry.card.uid,
    type: entry.card.type,
    card: cardFor(catalog, entry.card),
  };
}

export function historyView(
  catalog,
  session,
  { before = session.history.length, limit = 20 } = {},
) {
  const end = Math.max(0, Math.min(session.history.length, before));
  const start = Math.max(0, end - limit);
  return {
    start,
    end,
    history_size: session.history.length,
    entries: session.history
      .slice(start, end)
      .map((entry, offset) =>
        historyEntryView(catalog, entry, start + offset),
      ),
  };
}

export function sessionView(catalog, profile, session, limit = LOOKAHEAD) {
  const card = currentCard(session);
  return {
    session: {
      session_id: session.session_id,
      name: session.name,
      status: session.status,
      session_card_count: session.session_card_count,
      percent_completed: completionPercent(session),
      global_counter: profile.global_counter,
      initial_pool_size: session.initial_pool_size,
      pending_size: session.pending.length,
      queue_size: session.queue.length,
      history_size: session.history.length,
      created_from: session.created_from || null,
      active_cap: activeCapOf(session),
    },
    current: card
      ? {
          uid: card.uid,
          type: card.type,
          attempt: card.attempt,
          retry: card.retry,
          revealed: card.revealed,
          card: cardFor(catalog, card),
        }
      : null,
    lookahead: card ? lookahead(catalog, session, limit) : [],
    history_tail: session.history
      .slice(-HISTORY_TAIL)
      .map((entry, offset) =>
        historyEntryView(
          catalog,
          entry,
          session.history.length - Math.min(HISTORY_TAIL, session.history.length) + offset,
        ),
      ),
  };
}

export { LOOKAHEAD };
