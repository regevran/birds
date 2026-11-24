/* Profile/session state and the pure queue scheduler.
 *
 * This module owns the transition rules. It mutates the passed session and
 * profile documents, like a small in-memory state machine; the Worker loads
 * them from R2, calls one function, and saves them back.
 */

import { hashSeed, randomInt, seededRandom, shuffle } from "./random.js";
import { cardView } from "./views.js";

export const SCHEMA_VERSION = 1;
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

/* `created_from` for old sessions that predate the stored field. */
export function createdFromOf(session) {
  const text =
    session.created_from ?? formatCreatedFrom(session.filter ?? {});
  return text || null;
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
    passed: {},
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

export function eligibleBirds(catalog, filter, profile) {
  return catalog.birds.filter(
    (bird) =>
      bird.has_hebrew &&
      !Object.hasOwn(profile.passed, bird.species_id) &&
      matchesFilter(bird, filter),
  );
}

export function activeCount(session) {
  return new Set(session.queue.map((card) => card.species_id)).size;
}

export function completionPercent(session) {
  const total = Number(session.initial_pool_size) || 0;
  if (total <= 0) {
    return session.queue.length === 0 && session.pool.length === 0 ? 100 : 0;
  }
  const done = total - session.pool.length - activeCount(session);
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

function buildChain(session, profile, bird, { uid = newCardUid } = {}) {
  const types = bird.has_parts ? CHAIN_WITH_PARTS : CHAIN_WITHOUT_PARTS;
  return types.map((type, index) => ({
    uid: uid(),
    species_id: bird.species_id,
    type,
    attempt: 1,
    seed: cardSeed(
      session.seed,
      profile.global_counter,
      bird.species_id,
      type,
      index,
    ),
    hint_level: 0,
    retry: false,
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

function initialFill(catalog, profile, session, options = {}) {
  const chains = [];
  while (
    chains.length < session.settings.active_cap &&
    session.pool.length > 0
  ) {
    const speciesId = session.pool.shift();
    const bird = catalog.bird(speciesId);
    chains.push(buildChain(session, profile, bird, options));
  }
  session.queue = interleaveChains(
    chains,
    seededRandom(`${session.seed}:initial`),
  );
  session.status =
    session.queue.length === 0 && session.pool.length === 0
      ? "completed"
      : "active";
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

export function refill(catalog, profile, session, options = {}) {
  const next = seededRandom(
    `${session.seed}:refill:${profile.global_counter}:${session.queue.length}`,
  );
  while (
    activeCount(session) < session.settings.active_cap &&
    session.pool.length > 0
  ) {
    const speciesId = session.pool.shift();
    const bird = catalog.bird(speciesId);
    insertChain(session, buildChain(session, profile, bird, options), next);
  }
  session.status =
    session.queue.length === 0 && session.pool.length === 0
      ? "completed"
      : "active";
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
  const eligible = eligibleBirds(catalog, normalized, profile);
  const pool = shuffle(
    eligible.map((bird) => bird.species_id),
    seededRandom(`${chosenSeed}:pool`),
  );
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
    pool,
    queue: [],
    session_card_count: 0,
    paused_review: null,
  };
  initialFill(catalog, profile, session, { uid });
  return session;
}

function passBird(profile, session, bird, stamp) {
  profile.passed[bird.species_id] = {
    latin: {
      level: 1,
      due_at: profile.global_counter + 20,
      mastered: false,
      last_result: "correct",
      last_at: stamp,
      last_session_id: session.session_id,
    },
  };
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
  const bird = catalog.bird(card.species_id);
  profile.global_counter += 1;
  session.session_card_count += 1;
  const stamp = nowIso(now);

  if (result === "advance" || result === "correct") {
    if (card.type === "F") {
      passBird(profile, session, bird, stamp);
      takeLaterCards(session, card.species_id);
    }
  } else if (result === "near_miss") {
    const later = takeLaterCards(session, card.species_id);
    reinsertAhead(
      session,
      [card, ...later],
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
  } else {
    throw new SchedulerError(
      "invalid_result",
      `unknown result ${JSON.stringify(result)}`,
    );
  }

  refill(catalog, profile, session, { uid });
  session.updated_at = stamp;
  profile.updated_at = stamp;
  return { card, passed: card.type === "F" && result === "correct" };
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

export function prunePassed(catalog, profile, session, options = {}) {
  const passed = new Set(Object.keys(profile.passed));
  session.pool = session.pool.filter(
    (speciesId) => !passed.has(speciesId),
  );
  session.queue = session.queue.filter(
    (card) => !passed.has(card.species_id),
  );
  refill(catalog, profile, session, options);
  return session;
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
      pool_size: session.pool.length,
      queue_size: session.queue.length,
      created_from: createdFromOf(session),
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
  };
}

export { LOOKAHEAD };
