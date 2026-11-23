import assert from "node:assert/strict";
import test from "node:test";

import { signToken } from "../src/core.js";
import worker from "../src/index.js";
import { catalog } from "../src/trainer/dataset.js";
import { FakeBucket } from "./support/fake-bucket.js";

const SECRET = "test-secret";
const SPECIES = "acrocephalus-agricola";
const ALL_STATUSES = [
  "regular",
  "introduced",
  "accidental",
  "historical",
  "extinct",
];

function makeEnv() {
  return {
    PROGRESS: new FakeBucket(),
    AUTH_SECRET: SECRET,
    ALLOWED_ORIGINS: "https://regevran.github.io",
    TOKEN_TTL_SECONDS: "3600",
  };
}

function tokenFor(username = "alice", scope = "profile") {
  return signToken(
    {
      u: username,
      s: scope,
      exp: Math.floor(Date.now() / 1000) + 3600,
    },
    SECRET,
  );
}

async function appRequest(env, token, path, { method = "GET", body } = {}) {
  const headers = { Authorization: `Bearer ${token}` };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const request = new Request(`https://worker.test${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const response = await worker.fetch(request, env);
  const text = await response.text();
  return {
    status: response.status,
    headers: response.headers,
    document: text ? JSON.parse(text) : null,
  };
}

function sessionBody(overrides = {}) {
  return {
    name: "Test session",
    filter: { search: SPECIES, statuses: ALL_STATUSES },
    settings: { active_cap: 1 },
    seed: 7,
    ...overrides,
  };
}

async function createSession(env, token, overrides = {}) {
  const response = await appRequest(env, token, "/app/sessions", {
    method: "POST",
    body: sessionBody(overrides),
  });
  assert.equal(response.status, 201);
  return response.document;
}

function sessionId(view) {
  return view.session.session_id;
}

function answerBody(view) {
  const current = view.current;
  const bird = catalog.bird(current.card.species_id);
  switch (current.type) {
    case "L":
      return { action: "advance" };
    case "E":
      return {
        action: "answer",
        choices: Object.fromEntries(
          current.card.rows.map((row) => [
            row.element_id,
            catalog.element(row.element_id).he,
          ]),
        ),
      };
    case "R": {
      const accepted = catalog.birdsWithHebrew(current.card.hebrew);
      return { action: "answer", choice: accepted[0].species_id };
    }
    case "C":
    case "F":
      return { action: "answer", response: bird.latin };
    default:
      throw new Error(`unsupported card type ${current.type}`);
  }
}

async function answer(env, token, view, body) {
  const response = await appRequest(
    env,
    token,
    `/app/sessions/${sessionId(view)}/answer`,
    {
      method: "POST",
      body: { card_uid: view.current.uid, ...body },
    },
  );
  assert.equal(response.status, 200);
  return response.document;
}

async function advanceTo(env, token, view, type) {
  while (view.current && view.current.type !== type) {
    view = (await answer(env, token, view, answerBody(view))).session;
  }
  assert.equal(view.current?.type, type);
  return view;
}

test("the app creates a profile lazily in the user's scope", async () => {
  const env = makeEnv();
  const token = await tokenFor();

  const response = await appRequest(env, token, "/app/profile");
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.equal(response.document.profile_id, "alice");
  assert.equal(response.document.global_counter, 0);
  assert.equal(response.document.passed_count, 0);
  assert.ok(!Object.hasOwn(response.document, "active_session_id"));

  assert.ok(env.PROGRESS.objects.has("users/alice/profile.json"));
  assert.ok(env.PROGRESS.objects.has("users/alice/sessions/default.json"));
});

test("old session pointers are removed from the profile", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  const view = await createSession(env, token);
  const id = sessionId(view);
  const key = "users/alice/profile.json";
  const object = await env.PROGRESS.get(key);
  const profile = await object.json();
  profile.open_session_id = id;
  profile.active_session_id = id;
  await env.PROGRESS.put(key, JSON.stringify(profile));

  const response = await appRequest(env, token, "/app/profile");
  assert.ok(!Object.hasOwn(response.document, "active_session_id"));

  const migrated = await (await env.PROGRESS.get(key)).json();
  assert.ok(!Object.hasOwn(migrated, "active_session_id"));
  assert.ok(!Object.hasOwn(migrated, "open_session_id"));
});

test("a session can be renamed and cleared without changing its id", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  const view = await createSession(env, token, { name: "Evening" });
  const id = sessionId(view);
  const queueSize = view.session.queue_size;

  let renamed = await appRequest(
    env,
    token,
    `/app/sessions/${id}/rename`,
    { method: "POST", body: { name: "Morning" } },
  );
  assert.equal(renamed.status, 200);
  assert.equal(renamed.document.session.session_id, id);
  assert.equal(renamed.document.session.name, "Morning");
  assert.equal(renamed.document.session.queue_size, queueSize);

  renamed = await appRequest(
    env,
    token,
    `/app/sessions/${id}/rename`,
    { method: "POST", body: { name: "MORNING" } },
  );
  assert.equal(renamed.status, 200);
  assert.equal(renamed.document.session.name, "MORNING");

  const cleared = await appRequest(
    env,
    token,
    `/app/sessions/${id}/rename`,
    { method: "POST", body: { name: null } },
  );
  assert.equal(cleared.status, 200);
  assert.equal(cleared.document.session.name, null);

  const profile = await appRequest(env, token, "/app/profile");
  assert.ok(!Object.hasOwn(profile.document, "active_session_id"));
});

test("rename enforces unique names and protects the default", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  const first = await createSession(env, token, { name: "Evening" });
  const second = await createSession(env, token, { name: "Morning" });
  const firstId = sessionId(first);
  const secondId = sessionId(second);

  const conflict = await appRequest(
    env,
    token,
    `/app/sessions/${firstId}/rename`,
    { method: "POST", body: { name: "  morning  " } },
  );
  assert.equal(conflict.status, 409);
  assert.equal(conflict.document.error, "session_name_taken");
  assert.match(
    conflict.document.message,
    new RegExp(
      `'morning'.*${secondId}.*'Morning'.*case-insensitive name collision`,
    ),
  );

  const selfCase = await appRequest(
    env,
    token,
    `/app/sessions/${firstId}/rename`,
    { method: "POST", body: { name: "EVENING" } },
  );
  assert.equal(selfCase.status, 200);
  assert.equal(selfCase.document.session.name, "EVENING");

  const defaultRename = await appRequest(
    env,
    token,
    "/app/sessions/default/rename",
    { method: "POST", body: { name: "home" } },
  );
  assert.equal(defaultRename.status, 409);
  assert.equal(defaultRename.document.error, "session_default");
  assert.match(defaultRename.document.message, /\(protected\)/);

  const missingName = await appRequest(
    env,
    token,
    `/app/sessions/${firstId}/rename`,
    { method: "POST", body: {} },
  );
  assert.equal(missingName.status, 400);
  assert.equal(missingName.document.error, "invalid_request");
});

test("session handles resolve in the Worker", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  const view = await createSession(env, token, { name: "Evening" });
  const id = sessionId(view);

  let resolved = await appRequest(env, token, "/app/sessions/resolve", {
    method: "POST",
    body: { handle: "evening" },
  });
  assert.equal(resolved.status, 200);
  assert.equal(resolved.document.session.session_id, id);
  assert.ok(!Object.hasOwn(resolved.document.session, "active"));

  resolved = await appRequest(env, token, "/app/sessions/resolve", {
    method: "POST",
    body: { handle: "EVENING", by_name: true },
  });
  assert.equal(resolved.status, 200);
  assert.equal(resolved.document.session.session_id, id);

  resolved = await appRequest(env, token, "/app/sessions/resolve", {
    method: "POST",
    body: { handle: id.toUpperCase() },
  });
  assert.equal(resolved.status, 200);
  assert.equal(resolved.document.session.session_id, id);

  resolved = await appRequest(env, token, "/app/sessions/resolve", {
    method: "POST",
    body: { handle: id.slice(0, 10).toUpperCase() },
  });
  assert.equal(resolved.status, 200);
  assert.equal(resolved.document.session.session_id, id);

  resolved = await appRequest(env, token, "/app/sessions/resolve", {
    method: "POST",
    body: { handle: "DEFAULT" },
  });
  assert.equal(resolved.status, 200);
  assert.equal(resolved.document.session.session_id, "default");
  assert.ok(!Object.hasOwn(resolved.document.session, "active"));

  const missing = await appRequest(env, token, "/app/sessions/resolve", {
    method: "POST",
    body: { handle: "nope" },
  });
  assert.equal(missing.status, 404);
  assert.equal(missing.document.error, "session_not_found");
  assert.match(missing.document.message, /no session matches 'nope'/);

  const empty = await appRequest(env, token, "/app/sessions/resolve", {
    method: "POST",
    body: { handle: "   " },
  });
  assert.equal(empty.status, 400);
  assert.equal(empty.document.error, "invalid_request");
});

test("session resolution reports ambiguous names and prefixes", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  const first = await createSession(env, token, { name: "First" });
  const second = await createSession(env, token, { name: "Second" });
  const firstId = sessionId(first);
  const secondId = sessionId(second);

  const secondKey = `users/alice/sessions/${secondId}.json`;
  const object = await env.PROGRESS.get(secondKey);
  const document = await object.json();
  document.name = "First";
  await env.PROGRESS.put(secondKey, JSON.stringify(document));

  const duplicateName = await appRequest(
    env,
    token,
    "/app/sessions/resolve",
    { method: "POST", body: { handle: "first" } },
  );
  assert.equal(duplicateName.status, 409);
  assert.equal(duplicateName.document.error, "session_ambiguous");
  assert.match(duplicateName.document.message, /session name 'first' is ambiguous/);
  assert.match(duplicateName.document.message, new RegExp(firstId));
  assert.match(duplicateName.document.message, new RegExp(secondId));

  const prefix = await appRequest(env, token, "/app/sessions/resolve", {
    method: "POST",
    body: { handle: secondId.slice(0, 8) },
  });
  assert.equal(prefix.status, 409);
  assert.equal(prefix.document.error, "session_ambiguous");
  assert.match(prefix.document.message, /session id prefix/);
});

test("sessions are independent and answering does not require selection", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  let first = await createSession(env, token, { name: "First" });
  const firstId = sessionId(first);
  const second = await createSession(env, token, { name: "Second" });
  const secondId = sessionId(second);

  const firstView = await appRequest(env, token, `/app/sessions/${firstId}`);
  assert.equal(firstView.status, 200);
  assert.ok(!Object.hasOwn(firstView.document.session, "active"));

  const answered = await appRequest(
    env,
    token,
    `/app/sessions/${firstId}/answer`,
    {
      method: "POST",
      body: { card_uid: first.current.uid, action: "advance" },
    },
  );
  assert.equal(answered.status, 200);
  assert.equal(answered.document.session.current.type, "E");

  const prepared = await appRequest(
    env,
    token,
    `/app/sessions/${secondId}/prepare`,
    { method: "POST" },
  );
  assert.equal(prepared.status, 200);
  assert.equal(prepared.document.session.session_id, secondId);
  assert.equal(prepared.document.current.type, "L");

  const openRoute = await appRequest(
    env,
    token,
    `/app/sessions/${secondId}/open`,
    { method: "POST" },
  );
  assert.equal(openRoute.status, 404);

  const profile = await appRequest(env, token, "/app/profile");
  assert.ok(!Object.hasOwn(profile.document, "active_session_id"));
});

test("card runs filter eligible birds in the Worker", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  const noHebrew = "butorides-striata";
  const noParts = "accipiter-gentilis";

  let response = await appRequest(env, token, "/app/cards/run", {
    method: "POST",
    body: { q: noHebrew, card_type: "R" },
  });
  assert.equal(response.status, 200);
  assert.deepEqual(response.document.birds, []);
  assert.equal(response.document.skipped, 1);
  assert.equal(response.document.skip_reason, "no Hebrew");

  response = await appRequest(env, token, "/app/cards/run", {
    method: "POST",
    body: { q: noParts, card_type: "E" },
  });
  assert.deepEqual(response.document.birds, []);
  assert.equal(response.document.skipped, 1);
  assert.equal(response.document.skip_reason, "no split elements");

  response = await appRequest(env, token, "/app/cards/run", {
    method: "POST",
    body: { q: noParts, card_type: "R" },
  });
  assert.equal(response.document.birds.length, 1);
  assert.equal(response.document.birds[0].species_id, noParts);
  assert.equal(response.document.skipped, 0);
  assert.equal(response.document.skip_reason, "");

  response = await appRequest(env, token, "/app/cards/run", {
    method: "POST",
    body: { q: noHebrew, card_type: "L" },
  });
  assert.equal(response.document.birds.length, 1);
  assert.equal(response.document.skipped, 0);

  const invalid = await appRequest(env, token, "/app/cards/run", {
    method: "POST",
    body: { q: noHebrew, card_type: "Z" },
  });
  assert.equal(invalid.status, 400);
  assert.equal(invalid.document.error, "unsupported_card");
});

test("a new profile starts with the protected all-birds default session", async () => {
  const env = makeEnv();
  const token = await tokenFor();

  const list = await appRequest(env, token, "/app/sessions");
  assert.equal(list.status, 200);
  assert.ok(!Object.hasOwn(list.document, "active_session_id"));
  assert.equal(list.document.sessions.length, 1);
  const [session] = list.document.sessions;
  assert.equal(session.session_id, "default");
  assert.equal(session.name, "default");
  assert.ok(!Object.hasOwn(session, "active"));
  assert.ok(session.initial_pool_size > 0);

  const object = await env.PROGRESS.get("users/alice/sessions/default.json");
  const document = await object.json();
  assert.equal(document.name, "default");
  assert.deepEqual(document.filter.statuses, []);

  const refused = await appRequest(env, token, "/app/sessions/default", {
    method: "DELETE",
  });
  assert.equal(refused.status, 409);
  assert.equal(refused.document.error, "session_default");
  assert.match(refused.document.message, /\(protected\)/);
});

test("a full L-E-R-C-F chain passes the bird", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  let view = await createSession(env, token);

  assert.equal(view.current.type, "L");
  assert.equal(view.current.card.species_id, SPECIES);
  assert.equal(view.session.pool_size, 0);

  let response = await answer(env, token, view, { action: "advance" });
  assert.equal(response.feedback, null);
  view = response.session;
  assert.equal(view.current.type, "E");

  response = await answer(env, token, view, answerBody(view));
  assert.equal(response.feedback.kind, "elements");
  assert.equal(response.feedback.correct, response.feedback.total);
  view = response.session;
  assert.equal(view.current.type, "R");

  response = await answer(env, token, view, answerBody(view));
  assert.equal(response.feedback.kind, "recognize");
  assert.equal(response.feedback.result.correct, true);
  view = response.session;
  assert.equal(view.current.type, "C");

  response = await answer(env, token, view, {
    action: "answer",
    response: "Acrocephalus agricola",
  });
  assert.equal(response.feedback.kind, "latin");
  assert.equal(response.feedback.result.outcome, "correct");
  view = response.session;
  assert.equal(view.current.type, "F");

  response = await answer(env, token, view, {
    action: "answer",
    response: "  acrocephalus   AGRICOLA ",
  });
  assert.equal(response.feedback.result.outcome, "correct");
  assert.equal(response.session.current, null);
  assert.equal(response.session.session.status, "completed");
  assert.equal(response.session.session.session_card_count, 5);

  const profile = await appRequest(env, token, "/app/profile");
  assert.equal(profile.document.passed_count, 1);
  assert.equal(profile.document.global_counter, 5);
});

test("a first wrong R answer is retried without consuming", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  let view = await createSession(env, token);
  view = await advanceTo(env, token, view, "R");

  const wrong = view.current.card.options.find(
    (option) => option.species_id !== SPECIES,
  );
  let response = await answer(env, token, view, {
    action: "answer",
    choice: wrong.species_id,
  });
  assert.equal(response.feedback.kind, "retry");
  assert.equal(response.feedback.chosen, wrong.latin);
  view = response.session;
  assert.equal(view.current.type, "R");
  assert.equal(view.current.attempt, 2);
  assert.equal(view.current.retry, true);
  assert.equal(view.session.session_card_count, 2);
  assert.equal(view.session.global_counter, 2);

  response = await answer(env, token, view, answerBody(view));
  assert.equal(response.feedback.kind, "recognize");
  assert.equal(response.feedback.result.correct, true);
  assert.equal(response.session.current.type, "C");
  assert.equal(response.session.session.session_card_count, 3);
});

test("a C near miss moves the card back instead of passing it", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  let view = await createSession(env, token);
  view = await advanceTo(env, token, view, "C");

  const response = await answer(env, token, view, {
    action: "answer",
    response: "Acrocephalus agricolo",
  });
  assert.equal(response.feedback.kind, "latin");
  assert.equal(response.feedback.result.outcome, "near_miss");
  view = response.session;
  assert.equal(view.current.type, "C");
  assert.equal(view.session.session_card_count, 4);

  const profile = await appRequest(env, token, "/app/profile");
  assert.equal(profile.document.passed_count, 0);
});

test("a second wrong F answer falls back to C", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  let view = await createSession(env, token);
  view = await advanceTo(env, token, view, "F");

  let response = await answer(env, token, view, {
    action: "answer",
    response: "Corvus corax",
  });
  assert.equal(response.feedback.kind, "retry");
  view = response.session;
  assert.equal(view.current.type, "F");
  assert.equal(view.current.attempt, 2);

  response = await answer(env, token, view, {
    action: "answer",
    response: "Corvus corax",
  });
  assert.equal(response.feedback.kind, "latin");
  assert.equal(response.feedback.result.outcome, "wrong");
  assert.equal(response.session.current.type, "C");

  const profile = await appRequest(env, token, "/app/profile");
  assert.equal(profile.document.passed_count, 0);
});

test("a card that is no longer current is rejected", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  const view = await createSession(env, token);

  const response = await appRequest(
    env,
    token,
    `/app/sessions/${sessionId(view)}/answer`,
    {
      method: "POST",
      body: { card_uid: "c_not-current", action: "advance" },
    },
  );
  assert.equal(response.status, 409);
  assert.equal(response.document.error, "stale_card");
});

test("sessions are listed without an active pointer and any can be deleted", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  const view = await createSession(env, token);
  const id = sessionId(view);

  let list = await appRequest(env, token, "/app/sessions");
  assert.equal(list.status, 200);
  assert.equal(list.document.sessions.length, 2);
  assert.equal(list.document.sessions[0].session_id, "default");
  assert.ok(!Object.hasOwn(list.document, "active_session_id"));
  assert.ok(
    list.document.sessions.every(
      (session) => !Object.hasOwn(session, "active"),
    ),
  );

  const closedRoute = await appRequest(
    env,
    token,
    `/app/sessions/${id}/close`,
    { method: "POST" },
  );
  assert.equal(closedRoute.status, 404);

  const deleted = await appRequest(env, token, `/app/sessions/${id}`, {
    method: "DELETE",
  });
  assert.equal(deleted.status, 204);

  list = await appRequest(env, token, "/app/sessions");
  assert.equal(list.document.sessions.length, 1);
  assert.equal(list.document.sessions[0].session_id, "default");

  const profile = await appRequest(env, token, "/app/profile");
  assert.ok(!Object.hasOwn(profile.document, "active_session_id"));
});

test("session names are unique and unnamed sessions are allowed", async () => {
  const env = makeEnv();
  const token = await tokenFor();

  await createSession(env, token, { name: "Morning" });
  const duplicate = await appRequest(env, token, "/app/sessions", {
    method: "POST",
    body: sessionBody({ name: "  morning  " }),
  });
  assert.equal(duplicate.status, 409);
  assert.equal(duplicate.document.error, "session_name_taken");
  assert.match(
    duplicate.document.message,
    /'morning'.*'Morning'.*case-insensitive name collision/,
  );

  const defaultDuplicate = await appRequest(env, token, "/app/sessions", {
    method: "POST",
    body: sessionBody({ name: "Default" }),
  });
  assert.equal(defaultDuplicate.status, 409);
  assert.equal(defaultDuplicate.document.error, "session_name_taken");

  const unnamed = await createSession(env, token, { name: null });
  assert.equal(unnamed.session.name, null);

  const unnamedAgain = await createSession(env, token, { name: null });
  assert.equal(unnamedAgain.session.name, null);
});

test("a filter with no eligible birds is rejected", async () => {
  const env = makeEnv();
  const token = await tokenFor();

  const response = await appRequest(env, token, "/app/sessions", {
    method: "POST",
    body: sessionBody({
      filter: { search: "butorides-striata", statuses: ALL_STATUSES },
    }),
  });
  assert.equal(response.status, 422);
  assert.equal(response.document.error, "empty_pool");
});

test("a test-scoped token keeps app state under tests", async () => {
  const env = makeEnv();
  const token = await tokenFor("tester", "tests");
  const view = await createSession(env, token);

  const keys = [...env.PROGRESS.objects.keys()];
  assert.ok(keys.includes("tests/profile.json"));
  assert.ok(keys.includes(`tests/sessions/${sessionId(view)}.json`));
  assert.equal(
    keys.filter((key) => key.startsWith("users/")).length,
    0,
  );

  const profile = await appRequest(env, token, "/app/profile");
  assert.equal(profile.document.profile_id, "tester");
  assert.ok(!env.PROGRESS.objects.has("users/tester/profile.json"));
});

test("seeded sessions are reproducible through the API", async () => {
  const env = makeEnv();
  const token = await tokenFor();
  const first = await createSession(env, token, { name: null });
  const second = await createSession(env, token, { name: null });

  assert.deepEqual(
    first.lookahead.map((item) => [item.type, item.hebrew]),
    second.lookahead.map((item) => [item.type, item.hebrew]),
  );
});
