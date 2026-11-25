import assert from "node:assert/strict";
import test from "node:test";

import { catalog } from "../src/trainer/dataset.js";
import {
  activeCapOf,
  activeCount,
  assertCurrent,
  classifyCard,
  completionPercent,
  consume,
  createProfile,
  createSession,
  currentCard,
  formatCreatedFrom,
  historyView,
  markRetry,
  matchesFilter,
  redo,
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
  session.pending = [];
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
  assert.equal(session.pending.length, 0);
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

test("eligibility excludes no-Hebrew birds", () => {
  const empty = createSession(catalog, profile(), {
    filter: { search: "butorides-striata", statuses: ALL_STATUSES },
    seed: 1,
    sessionId: "s1",
    now: NOW,
  });
  assert.equal(empty.status, "completed");
  assert.equal(empty.queue.length, 0);
  assert.equal(empty.initial_pool_size, 0);

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
  assert.equal(
    view.current.hebrew,
    catalog.bird(session.queue[0].species_id).hebrew,
  );
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

test("F correct completes the chain without passing the bird", () => {
  const { profile: owner, session } = sessionFor(
    "acrocephalus-agricola",
  );
  isolate(session, ["F"]);
  const result = consume(catalog, owner, session, "correct");
  assert.equal(result.card.type, "F");
  assert.equal(owner.global_counter, 1);
  assert.equal(owner.passed, undefined);
  assert.equal(session.history.length, 1);
  assert.equal(session.history[0].result, "correct");
  assert.equal(session.status, "completed");
});

test("F second wrong inserts C before F", () => {
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
  session.pending = [{ species_id: "turdus-merula", cards: [{ type: "L" }] }];
  session.settings.active_cap = 2;
  refill(catalog, owner, session);
  assert.equal(activeCount(session), 2);
  assert.equal(session.pending.length, 0);
  assert.ok(
    session.queue.some((card) => card.species_id === "turdus-merula"),
  );
});

test("created_from is the Worker-formatted search and criteria", () => {
  assert.equal(
    formatCreatedFrom({ search: "acrocephalus-agricola" }),
    'search "acrocephalus-agricola"',
  );
  assert.equal(
    formatCreatedFrom({
      search: "acro",
      families: ["Acrocephalidae"],
      statuses: ["accidental"],
    }),
    'search "acro" · family: Acrocephalidae · status: accidental',
  );
  assert.equal(formatCreatedFrom({ statuses: [] }), "");
  assert.equal(formatCreatedFrom({}), "");
  assert.equal(
    formatCreatedFrom({ search: "acro", statuses: ["introduced", "regular"] }),
    'search "acro"',
  );
});

test("a session stores its origin and active cap", () => {
  const owner = profile();
  const session = createSession(catalog, owner, {
    name: "Test session",
    filter: { search: "acro", statuses: ["accidental"] },
    settings: { active_cap: 2 },
    seed: 7,
    sessionId: "s1",
    uid: idFactory(),
    now: NOW,
  });
  assert.equal(session.created_from, 'search "acro" · status: accidental');
  assert.equal(activeCapOf(session), 2);
  const view = sessionView(catalog, owner, session);
  assert.equal(
    view.session.created_from,
    'search "acro" · status: accidental',
  );
  assert.equal(view.session.active_cap, 2);
});

test("the default session has no origin and the default cap", () => {
  const owner = profile();
  const session = createSession(catalog, owner, {
    filter: { statuses: [] },
    settings: {},
    sessionId: "default",
    uid: idFactory(),
    now: NOW,
  });
  assert.equal(session.created_from, "");
  assert.equal(sessionView(catalog, owner, session).session.created_from, null);
  assert.equal(activeCapOf(session), 7);
});

test("cards classify as current, future, history or missing", () => {
  const { profile: owner, session } = sessionFor("acrocephalus-agricola");
  const head = session.queue[0];
  const ahead = session.queue[1];
  assert.equal(classifyCard(session, head.uid).kind, "current");
  assert.equal(classifyCard(session, ahead.uid).kind, "future");
  assert.equal(classifyCard(session, "nope").kind, "missing");
  consume(catalog, owner, session, "advance");
  assert.equal(classifyCard(session, head.uid).kind, "history");
});

test("a correct redo records without changing the future", () => {
  const { profile: owner, session } = sessionFor("acrocephalus-agricola");
  isolate(session, ["L", "E"]);
  consume(catalog, owner, session, "advance");
  const queueBefore = session.queue.map((card) => card.uid);
  const counterBefore = owner.global_counter;
  const pendingBefore = session.pending.length;
  redo(catalog, owner, session, session.history[0].card.uid, "correct");
  assert.equal(session.history[0].result, "correct");
  assert.deepEqual(session.queue.map((card) => card.uid), queueBefore);
  assert.equal(session.pending.length, pendingBefore);
  assert.equal(owner.global_counter, counterBefore);
});

test("a wrong redo truncates, pours cards back and retries", () => {
  const { profile: owner, session } = sessionFor("acrocephalus-agricola");
  isolate(session, ["L", "E", "R", "C", "F"]);
  consume(catalog, owner, session, "advance");
  consume(catalog, owner, session, "advance");
  const other = {
    ...session.queue[0],
    uid: "c_other",
    species_id: "turdus-merula",
    type: "L",
  };
  session.queue.push(other);
  const redone = session.history[1].card.uid;
  const result = redo(catalog, owner, session, redone, "wrong");

  assert.equal(result.invalidated, 4);
  assert.equal(session.history.length, 2);
  assert.equal(session.history[1].result, "wrong");
  assert.equal(session.session_card_count, 2);
  assert.equal(session.pending.length, 0);
  assert.deepEqual(
    session.queue.map((card) => card.type).sort(),
    ["C", "E", "F", "L", "R"],
  );
  assert.ok(
    session.queue.some((card) => card.species_id === "turdus-merula"),
  );
  assert.equal(
    new Set(session.queue.map((card) => card.uid)).size,
    session.queue.length,
  );
  assert.ok(!session.queue.some((card) => card.uid === redone));
});

test("history windows page backwards", () => {
  const { profile: owner, session } = sessionFor("acrocephalus-agricola");
  isolate(session, ["L", "E", "R", "C", "F"]);
  for (let index = 0; index < 3; index += 1) {
    consume(catalog, owner, session, "advance");
  }
  const view = sessionView(catalog, owner, session);
  assert.equal(view.session.history_size, 3);
  assert.equal(view.history_tail.length, 3);
  for (const entry of view.history_tail) {
    assert.equal(
      entry.hebrew,
      catalog.bird(entry.card.species_id).hebrew,
    );
  }
  const page = historyView(catalog, session, { before: 2, limit: 1 });
  assert.equal(page.start, 1);
  assert.equal(page.end, 2);
  assert.equal(page.entries.length, 1);
  assert.equal(page.entries[0].index, 1);
  assert.equal(page.entries[0].result, "advance");
  assert.ok(page.entries[0].hebrew);
});
