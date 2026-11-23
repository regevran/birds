import assert from "node:assert/strict";
import test from "node:test";

import { catalog } from "../src/trainer/dataset.js";
import {
  activeCount,
  assertCurrent,
  completionPercent,
  consume,
  createProfile,
  createSession,
  currentCard,
  markRetry,
  matchesFilter,
  refill,
  sessionView,
} from "../src/trainer/scheduler.js";

const NOW = () => new Date("2026-11-22T12:00:00Z");

function idFactory() {
  let counter = 0;
  return () => {
    counter += 1;
    return `c_${String(counter).padStart(12, "0")}`;
  };
}

function profile() {
  return createProfile({
    profileId: "test",
    name: "Test",
    now: NOW,
  });
}

const ALL_STATUSES = [
  "regular",
  "introduced",
  "accidental",
  "historical",
  "extinct",
];

function sessionFor(speciesId, options = {}) {
  const owner = options.profile ?? profile();
  const session = createSession(catalog, owner, {
    name: "Test session",
    filter: { search: speciesId, statuses: ALL_STATUSES },
    settings: { active_cap: 1 },
    seed: 7,
    sessionId: "s1",
    uid: idFactory(),
    now: NOW,
    ...options,
  });
  return { profile: owner, session };
}

function isolate(session, types) {
  const cards = types.map((type) =>
    session.queue.find((card) => card.type === type),
  );
  session.queue = cards.filter(Boolean);
  session.pool = [];
  session.status = "active";
  return session;
}

test("session search filters stay names-only", () => {
  const filter = {
    families: [],
    orders: [],
    genera: [],
    statuses: ALL_STATUSES,
    search: "summit",
  };
  const bird = catalog.bird("acrocephalus-agricola");
  assert.equal(matchesFilter(bird, filter), false);
  assert.equal(
    matchesFilter(bird, { ...filter, search: "acrocephalus" }),
    true,
  );
});

test("profile and session creation fill the active cap", () => {  const owner = profile();
  const session = createSession(catalog, owner, {
    filter: { search: "cormorant", statuses: ALL_STATUSES },
    settings: { active_cap: 2 },
    seed: 7,
    sessionId: "s1",
    uid: idFactory(),
    now: NOW,
  });

  assert.equal(session.initial_pool_size, 2);
  assert.equal(session.pool.length, 0);
  assert.equal(activeCount(session), 2);
  assert.ok(session.queue.length >= 9);
  assert.equal(new Set(session.queue.map((card) => card.uid)).size, session.queue.length);
  assert.equal(session.status, "active");

  const species = [...new Set(session.queue.map((card) => card.species_id))];
  assert.equal(species.length, 2);
  for (const speciesId of species) {
    const types = session.queue
      .filter((card) => card.species_id === speciesId)
      .map((card) => card.type);
    const bird = catalog.bird(speciesId);
    const expected = bird.has_parts
      ? ["L", "E", "R", "C", "F"]
      : ["L", "R", "C", "F"];
    assert.deepEqual(types, expected);
  }
});

test("the same seed produces the same initial queue", () => {
  const first = createSession(catalog, profile(), {
    filter: { search: "cormorant", statuses: ALL_STATUSES },
    settings: { active_cap: 2 },
    seed: 7,
    sessionId: "a",
    uid: idFactory(),
    now: NOW,
  });
  const second = createSession(catalog, profile(), {
    filter: { search: "cormorant", statuses: ALL_STATUSES },
    settings: { active_cap: 2 },
    seed: 7,
    sessionId: "b",
    uid: idFactory(),
    now: NOW,
  });
  assert.deepEqual(
    first.queue.map((card) => [card.species_id, card.type, card.seed]),
    second.queue.map((card) => [card.species_id, card.type, card.seed]),
  );
});

test("eligibility excludes no-Hebrew and passed birds", () => {
  const empty = createSession(catalog, profile(), {
    filter: { search: "butorides-striata", statuses: ALL_STATUSES },
    seed: 1,
    sessionId: "s1",
    now: NOW,
  });
  assert.equal(empty.status, "completed");
  assert.equal(empty.queue.length, 0);
  assert.equal(empty.initial_pool_size, 0);

  const owner = profile();
  owner.passed["acrocephalus-agricola"] = { latin: { level: 1 } };
  const passed = createSession(catalog, owner, {
    filter: { search: "paddyfield", statuses: ALL_STATUSES },
    seed: 1,
    sessionId: "s2",
    now: NOW,
  });
  assert.equal(passed.initial_pool_size, 0);
  assert.equal(passed.status, "completed");
});

test("filters use status categories and AND semantics", () => {
  const agricola = catalog.bird("acrocephalus-agricola");
  assert.equal(
    matchesFilter(agricola, {
      families: [],
      orders: [],
      genera: [],
      statuses: ["regular", "introduced"],
      search: "",
    }),
    false,
  );
  assert.equal(
    matchesFilter(agricola, {
      families: ["Acrocephalidae"],
      orders: [],
      genera: [],
      statuses: ["accidental"],
      search: "paddyfield",
    }),
    true,
  );
  assert.equal(
    matchesFilter(agricola, {
      families: ["Wrong"],
      orders: [],
      genera: [],
      statuses: ["accidental"],
      search: "",
    }),
    false,
  );
});

test("session views expose the current card and a safe lookahead", () => {
  const { profile: owner, session } = sessionFor(
    "acrocephalus-agricola",
    { settings: { active_cap: 1 } },
  );
  const view = sessionView(catalog, owner, session);
  assert.equal(view.current.uid, session.queue[0].uid);
  assert.equal(view.current.type, session.queue[0].type);
  assert.equal(view.current.card.card_type, session.queue[0].type);
  assert.ok(view.lookahead.length <= 5);
  for (const item of view.lookahead) {
    assert.deepEqual(Object.keys(item).sort(), [
      "hebrew",
      "is_review",
      "out_of_scope",
      "type",
    ]);
  }
});

test("completion percent follows learned birds", () => {
  const owner = profile();
  const session = createSession(catalog, owner, {
    filter: { search: "cormorant", statuses: ALL_STATUSES },
    settings: { active_cap: 2 },
    seed: 7,
    sessionId: "s1",
    uid: idFactory(),
    now: NOW,
  });
  assert.equal(completionPercent(session), 0);

  const learned = session.queue[0].species_id;
  session.queue = session.queue.filter(
    (card) => card.species_id !== learned,
  );
  assert.equal(completionPercent(session), 50);

  session.queue = [];
  assert.equal(completionPercent(session), 100);
});

test("L and E advance one card and one counter", () => {
  const { profile: owner, session } = sessionFor(
    "acrocephalus-agricola",
  );
  isolate(session, ["L", "E"]);
  const result = consume(catalog, owner, session, "advance");
  assert.equal(result.card.type, "L");
  assert.equal(owner.global_counter, 1);
  assert.equal(session.session_card_count, 1);
  assert.equal(currentCard(session).type, "E");
});

test("R correct keeps the bird's later chain", () => {
  const { profile: owner, session } = sessionFor(
    "acrocephalus-agricola",
  );
  isolate(session, ["R", "C", "F"]);
  consume(catalog, owner, session, "correct");
  assert.equal(owner.global_counter, 1);
  assert.deepEqual(
    session.queue.map((card) => card.type),
    ["C", "F"],
  );
});

test("R second wrong inserts the L fallback chain", () => {
  const { profile: owner, session } = sessionFor(
    "acrocephalus-agricola",
  );
  isolate(session, ["R", "C", "F"]);
  const other = {
    ...session.queue[0],
    uid: "c_other",
    species_id: "turdus-merula",
    type: "L",
  };
  isolate(session, ["R", "C", "F"]);
  session.queue.push(other);
  consume(catalog, owner, session, "wrong");
  assert.equal(owner.global_counter, 1);
  assert.deepEqual(
    session.queue.map((card) => card.type),
    ["L", "L", "R", "C", "F"],
  );
  assert.equal(new Set(session.queue.map((card) => card.uid)).size, 5);
  const fallback = session.queue.find(
    (card) => card.uid !== "c_other" && card.type === "L",
  );
  assert.equal(fallback.attempt, 1);
});

test("C near miss moves the card and its chain forward", () => {
  const { profile: owner, session } = sessionFor(
    "acrocephalus-agricola",
  );
  isolate(session, ["C", "F"]);
  const other = {
    ...session.queue[0],
    uid: "c_other",
    species_id: "turdus-merula",
    type: "L",
  };
  session.queue.push(other);
  consume(catalog, owner, session, "near_miss");
  assert.equal(owner.global_counter, 1);
  assert.deepEqual(
    session.queue.map((card) => card.type),
    ["L", "C", "F"],
  );
  assert.equal(session.queue[0].uid, "c_other");
});

test("F correct passes the bird and schedules V1", () => {
  const { profile: owner, session } = sessionFor(
    "acrocephalus-agricola",
  );
  isolate(session, ["F"]);
  const result = consume(catalog, owner, session, "correct");
  assert.equal(result.passed, true);
  assert.equal(owner.global_counter, 1);
  const entry = owner.passed["acrocephalus-agricola"].latin;
  assert.equal(entry.level, 1);
  assert.equal(entry.due_at, 21);
  assert.equal(entry.mastered, false);
  assert.equal(entry.last_result, "correct");
  assert.equal(session.status, "completed");
});

test("F second wrong inserts C before F and does not pass", () => {
  const { profile: owner, session } = sessionFor(
    "acrocephalus-agricola",
  );
  isolate(session, ["F"]);
  consume(catalog, owner, session, "wrong");
  assert.equal(owner.global_counter, 1);
  assert.deepEqual(
    session.queue.map((card) => card.type),
    ["C", "F"],
  );
  assert.equal(owner.passed["acrocephalus-agricola"], undefined);
});

test("a retry marks the current card without consuming it", () => {
  const { profile: owner, session } = sessionFor(
    "acrocephalus-agricola",
  );
  isolate(session, ["R", "C", "F"]);
  const card = markRetry(session);
  assert.equal(card.attempt, 2);
  assert.equal(card.retry, true);
  assert.equal(owner.global_counter, 0);
  assert.equal(session.session_card_count, 0);
  assert.equal(currentCard(session).uid, card.uid);
});

test("stale card ids are rejected", () => {
  const { session } = sessionFor("acrocephalus-agricola");
  assert.throws(() => assertCurrent(session, "nope"), /not current/);
  assert.equal(
    assertCurrent(session, session.queue[0].uid).uid,
    session.queue[0].uid,
  );
});

test("refill pulls a bird when an active slot frees", () => {
  const { profile: owner, session } = sessionFor(
    "acrocephalus-agricola",
  );
  session.pool = ["turdus-merula"];
  session.settings.active_cap = 2;
  refill(catalog, owner, session);
  assert.equal(activeCount(session), 2);
  assert.equal(session.pool.length, 0);
  assert.ok(
    session.queue.some((card) => card.species_id === "turdus-merula"),
  );
});
