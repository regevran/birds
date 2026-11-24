/* Session API on top of the scheduler and the private R2 store. */

import {
  HttpError,
  jsonResponse,
  readJson,
  revisionOf,
  scopeBase,
} from "./core.js";
import { gradeAnswer } from "./trainer/answers.js";
import { catalog } from "./trainer/dataset.js";
import { GradeError } from "./trainer/grading.js";
import { searchBirds } from "./trainer/search.js";
import {
  SchedulerError,
  activeCapOf,
  assertCurrent,
  cardFor,
  consume,
  completionPercent,
  createProfile,
  createSession,
  createdFromOf,
  markRetry,
  prunePassed,
  sessionView,
} from "./trainer/scheduler.js";
import { ViewError, cardView } from "./trainer/views.js";

function requireObjectBody(body) {
  if (body === null || typeof body !== "object" || Array.isArray(body)) {
    throw new HttpError(400, "invalid_request", "a JSON object body is required");
  }
  return body;
}

function profileKey(identity) {
  return `${scopeBase(identity.scope, identity.username)}profile.json`;
}

function sessionKey(identity, sessionId) {
  return `${scopeBase(
    identity.scope,
    identity.username,
  )}sessions/${sessionId}.json`;
}

function sessionsPrefix(identity) {
  return `${scopeBase(identity.scope, identity.username)}sessions/`;
}

const DEFAULT_SESSION_ID = "default";
const DEFAULT_SESSION_NAME = "default";

function sessionNameKey(name) {
  return typeof name === "string" ? name.trim().toLowerCase() : null;
}

function requestSessionName(value) {
  if (value === undefined || value === null) {
    return null;
  }
  if (typeof value !== "string") {
    throw new HttpError(400, "invalid_request", "name must be a string");
  }
  const name = value.trim();
  if (!name) {
    throw new HttpError(400, "invalid_request", "name must not be empty");
  }
  return name;
}

function isDefaultSession(session) {
  return (
    session.session_id === DEFAULT_SESSION_ID ||
    sessionNameKey(session.name) === DEFAULT_SESSION_NAME
  );
}

function sessionLabel(session) {
  return session.name
    ? `${session.session_id} '${session.name}'`
    : session.session_id;
}

function duplicateNameMessage(name, existing) {
  return (
    `session name '${name}' is taken by: ${sessionLabel(existing.document)} ` +
    "(case-insensitive name collision)"
  );
}

async function readJsonObject(bucket, key) {
  const object = await bucket.get(key);
  if (!object) {
    return null;
  }
  const document = await object.json();
  return { document, revision: revisionOf(object.etag) };
}

async function writeJsonObject(bucket, key, document, revision) {
  const bytes = new TextEncoder().encode(
    JSON.stringify(document, null, 2) + "\n",
  );
  const options = { httpMetadata: { contentType: "application/json" } };
  if (revision) {
    options.onlyIf = { etagMatches: revision };
  }
  const result = await bucket.put(key, bytes, options);
  if (result === null || result === undefined) {
    throw new HttpError(
      412,
      "revision_conflict",
      "state changed; reload the session",
    );
  }
  return revisionOf(result.etag);
}

async function loadProfile(env, identity) {
  const key = profileKey(identity);
  const existing = await readJsonObject(env.PROGRESS, key);
  if (existing) {
    return existing;
  }
  const document = createProfile({
    profileId: identity.username,
    name: identity.username,
  });
  document.updated_at = new Date().toISOString();
  const revision = await writeJsonObject(
    env.PROGRESS,
    key,
    document,
  );
  return { document, revision };
}

async function loadSession(env, identity, sessionId) {
  const object = await readJsonObject(
    env.PROGRESS,
    sessionKey(identity, sessionId),
  );
  if (!object) {
    throw new HttpError(404, "session_not_found", "session not found");
  }
  return object;
}

async function listKeys(bucket, prefix) {
  const keys = [];
  let cursor;
  do {
    const page = await bucket.list({ prefix, cursor, limit: 1000 });
    keys.push(...page.objects.map((object) => object.key));
    cursor = page.truncated ? page.cursor : undefined;
  } while (cursor);
  return keys;
}

async function loadSessions(env, identity) {
  const keys = await listKeys(env.PROGRESS, sessionsPrefix(identity));
  const sessions = [];
  for (const key of keys) {
    const object = await readJsonObject(env.PROGRESS, key);
    if (object) {
      sessions.push(object);
    }
  }
  return sessions;
}

async function ensureDefaultSession(env, identity, profile) {
  let defaultSession = await readJsonObject(
    env.PROGRESS,
    sessionKey(identity, DEFAULT_SESSION_ID),
  );
  if (!defaultSession) {
    const document = createSession(catalog, profile.document, {
      name: DEFAULT_SESSION_NAME,
      filter: { statuses: [] },
      settings: {},
      sessionId: DEFAULT_SESSION_ID,
    });
    const revision = await writeJsonObject(
      env.PROGRESS,
      sessionKey(identity, DEFAULT_SESSION_ID),
      document,
    );
    defaultSession = { document, revision };
  }

  let changed = false;
  // Session selection is client-local; remove old profile pointers.
  for (const field of ["active_session_id", "open_session_id"]) {
    if (Object.hasOwn(profile.document, field)) {
      delete profile.document[field];
      changed = true;
    }
  }
  if (changed) {
    profile.document.updated_at = new Date().toISOString();
    profile.revision = await writeJsonObject(
      env.PROGRESS,
      profileKey(identity),
      profile.document,
      profile.revision,
    );
  }
  return defaultSession;
}

function profileSummary(profile) {
  return {
    profile_id: profile.profile_id,
    name: profile.name,
    global_counter: profile.global_counter,
    passed_count: Object.keys(profile.passed).length,
    settings: profile.settings,
    created_at: profile.created_at,
    updated_at: profile.updated_at,
  };
}

function sessionSummary(session) {
  return {
    session_id: session.session_id,
    name: session.name,
    status: session.status,
    session_card_count: session.session_card_count,
    percent_completed: completionPercent(session),
    initial_pool_size: session.initial_pool_size,
    queue_size: session.queue.length,
    pool_size: session.pool.length,
    created_from: createdFromOf(session),
    active_cap: activeCapOf(session),
    created_at: session.created_at,
    updated_at: session.updated_at,
  };
}

function mapError(error) {
  if (error instanceof HttpError) {
    return error;
  }
  if (error instanceof GradeError || error instanceof ViewError) {
    return new HttpError(400, error.code ?? "invalid_request", error.message);
  }
  if (error instanceof SchedulerError) {
    const status =
      error.code === "stale_card" ||
      error.code === "no_current_card"
        ? 409
        : 400;
    return new HttpError(status, error.code, error.message);
  }
  return error;
}

export async function handleApp(request, env, url, cors, identity) {
  try {
    return await routeApp(request, env, url, cors, identity);
  } catch (error) {
    throw mapError(error);
  }
}

async function routeApp(request, env, url, cors, identity) {
  const method = request.method;

  if (url.pathname === "/app/birds") {
    if (method !== "POST") {
      throw new HttpError(405, "method_not_allowed", "method not allowed");
    }
    return await searchRequest(request, cors);
  }

  if (url.pathname === "/app/cards") {
    if (method !== "POST") {
      throw new HttpError(405, "method_not_allowed", "method not allowed");
    }
    return await cardViewRequest(request, cors);
  }

  if (url.pathname === "/app/cards/answer") {
    if (method !== "POST") {
      throw new HttpError(405, "method_not_allowed", "method not allowed");
    }
    return await cardAnswerRequest(request, cors);
  }

  if (url.pathname === "/app/cards/run") {
    if (method !== "POST") {
      throw new HttpError(405, "method_not_allowed", "method not allowed");
    }
    return await cardRunRequest(request, cors);
  }

  if (url.pathname === "/app/profile") {
    if (method !== "GET") {
      throw new HttpError(405, "method_not_allowed", "method not allowed");
    }
    const profile = await loadProfile(env, identity);
    await ensureDefaultSession(env, identity, profile);
    return jsonResponse(profileSummary(profile.document), 200, cors);
  }

  if (url.pathname === "/app/sessions") {
    if (method === "GET") {
      return await listSessions(env, identity, cors);
    }
    if (method === "POST") {
      return await createSessionRequest(env, identity, request, cors);
    }
    throw new HttpError(405, "method_not_allowed", "method not allowed");
  }

  if (url.pathname === "/app/sessions/resolve") {
    if (method !== "POST") {
      throw new HttpError(405, "method_not_allowed", "method not allowed");
    }
    return await resolveSessionRequest(env, identity, request, cors);
  }

  const match = url.pathname.match(
    /^\/app\/sessions\/([A-Za-z0-9_-]+)(?:\/(prepare|answer|rename))?$/,
  );
  if (!match) {
    throw new HttpError(404, "not_found", "not found");
  }
  const [, sessionId, action] = match;
  const lookahead = viewLimit(url);

  if (!action) {
    if (method === "GET") {
      const profile = await loadProfile(env, identity);
      const session = await loadSession(env, identity, sessionId);
      return jsonResponse(
        sessionView(catalog, profile.document, session.document, lookahead),
        200,
        cors,
      );
    }
    if (method === "DELETE") {
      return await deleteSession(env, identity, sessionId, cors);
    }
    throw new HttpError(405, "method_not_allowed", "method not allowed");
  }

  if (action === "prepare") {
    if (method !== "POST") {
      throw new HttpError(405, "method_not_allowed", "method not allowed");
    }
    return await prepareSession(env, identity, sessionId, lookahead, cors);
  }

  if (action === "rename") {
    if (method !== "POST") {
      throw new HttpError(405, "method_not_allowed", "method not allowed");
    }
    return await renameSession(
      env,
      identity,
      sessionId,
      request,
      lookahead,
      cors,
    );
  }

  if (action === "answer") {
    if (method !== "POST") {
      throw new HttpError(405, "method_not_allowed", "method not allowed");
    }
    return await answerRequest(
      env,
      identity,
      sessionId,
      request,
      lookahead,
      cors,
    );
  }

  throw new HttpError(404, "not_found", "not found");
}

async function searchRequest(request, cors) {
  const body = requireObjectBody(await readJson(request));
  const query = body.q ?? "";
  if (typeof query !== "string") {
    throw new HttpError(400, "invalid_request", "q must be a string");
  }
  const { birds, elements } = searchBirds(catalog, query);
  return jsonResponse(
    { birds, elements, count: birds.length },
    200,
    cors,
  );
}

function viewLimit(url) {
  const raw = url.searchParams.get("lookahead");
  if (raw === null || raw === "") {
    return undefined;
  }
  const limit = Number(raw);
  if (!Number.isInteger(limit) || limit < 1 || limit > 20) {
    throw new HttpError(400, "invalid_request", "lookahead must be 1..20");
  }
  return limit;
}

async function cardViewRequest(request, cors) {
  const body = requireObjectBody(await readJson(request));
  const { speciesId, cardType, seed } = cardRequestFields(body);
  const card = cardView(
    catalog,
    { species_id: speciesId, card_type: cardType },
    seed,
  );
  return jsonResponse({ card }, 200, cors);
}

async function cardAnswerRequest(request, cors) {
  const body = requireObjectBody(await readJson(request));
  const { speciesId, cardType, seed } = cardRequestFields(body);
  if (cardType === "L") {
    throw new HttpError(
      400,
      "not_answerable",
      "L cards are not answered",
    );
  }
  const attempt = parseAttempt(body.attempt);
  const view = cardView(
    catalog,
    { species_id: speciesId, card_type: cardType },
    seed,
  );
  const { feedback } = gradeAnswer(
    catalog,
    speciesId,
    cardType,
    view,
    body,
    attempt,
  );
  return jsonResponse({ feedback }, 200, cors);
}

async function cardRunRequest(request, cors) {
  const body = requireObjectBody(await readJson(request));
  const query = body.q ?? "";
  if (typeof query !== "string") {
    throw new HttpError(400, "invalid_request", "q must be a string");
  }
  const rawType = body.card_type;
  if (typeof rawType !== "string" || !rawType.trim()) {
    throw new HttpError(400, "invalid_request", "card_type is required");
  }
  const cardType = rawType.trim().toUpperCase();
  if (!CARD_TYPES.has(cardType)) {
    throw new HttpError(
      400,
      "unsupported_card",
      `card type ${cardType} is not implemented`,
    );
  }
  const { birds } = searchBirds(catalog, query);
  const eligible = [];
  let skipped = 0;
  for (const bird of birds) {
    if (cardRequiresHebrew(cardType) && !bird.has_hebrew) {
      skipped += 1;
      continue;
    }
    if (cardType === "E" && !bird.has_parts) {
      skipped += 1;
      continue;
    }
    eligible.push(bird);
  }
  return jsonResponse(
    {
      birds: eligible,
      skipped,
      skip_reason: skipped > 0 ? cardSkipReason(cardType) : "",
    },
    200,
    cors,
  );
}

function cardRequiresHebrew(cardType) {
  return cardType === "R" || cardType === "C" || cardType === "F";
}

function cardSkipReason(cardType) {
  if (cardType === "E") {
    return "no split elements";
  }
  if (cardRequiresHebrew(cardType)) {
    return "no Hebrew";
  }
  return "";
}

const CARD_TYPES = new Set(["L", "E", "R", "C", "F"]);

function cardRequestFields(body) {
  const rawSpecies = body.species_id;
  if (typeof rawSpecies !== "string" || !rawSpecies.trim()) {
    throw new HttpError(400, "invalid_request", "species_id is required");
  }
  const speciesId = rawSpecies.trim();
  if (!catalog.byId.has(speciesId)) {
    throw new HttpError(404, "bird_not_found", "bird not found");
  }

  const rawType = body.card_type;
  if (typeof rawType !== "string" || !rawType.trim()) {
    throw new HttpError(400, "invalid_request", "card_type is required");
  }
  const cardType = rawType.trim().toUpperCase();
  if (!CARD_TYPES.has(cardType)) {
    throw new HttpError(
      400,
      "unsupported_card",
      `card type ${cardType} is not implemented`,
    );
  }

  return { speciesId, cardType, seed: parseSeed(body.seed) };
}

function parseSeed(value) {
  if (value === undefined || value === null) {
    return 0;
  }
  if (!Number.isInteger(value) || value < 0) {
    throw new HttpError(
      400,
      "invalid_request",
      "seed must be a non-negative integer",
    );
  }
  return value;
}

function parseAttempt(value) {
  if (value === undefined || value === null) {
    return 1;
  }
  if (value !== 1 && value !== 2) {
    throw new HttpError(
      400,
      "invalid_request",
      "attempt must be 1 or 2",
    );
  }
  return value;
}

function ambiguityError(subject, entries, advice) {
  const lines = entries.map(({ document }) => `  ${sessionLabel(document)}`);
  return new HttpError(
    409,
    "session_ambiguous",
    `${subject}; ${advice}:\n${lines.join("\n")}`,
  );
}

async function resolveSessionRequest(env, identity, request, cors) {
  const body = requireObjectBody(await readJson(request));
  if (typeof body.handle !== "string" || !body.handle.trim()) {
    throw new HttpError(400, "invalid_request", "handle is required");
  }
  if (body.by_name !== undefined && typeof body.by_name !== "boolean") {
    throw new HttpError(400, "invalid_request", "by_name must be a boolean");
  }
  const handle = body.handle.trim();
  const byName = body.by_name === true;
  const wanted = handle.toLowerCase();
  const profile = await loadProfile(env, identity);
  await ensureDefaultSession(env, identity, profile);
  const sessions = await loadSessions(env, identity);

  const bySessionName = sessions.filter(
    ({ document }) => sessionNameKey(document.name) === wanted,
  );
  if (byName) {
    if (bySessionName.length === 0) {
      throw new HttpError(
        404,
        "session_not_found",
        `no session named '${handle}'`,
      );
    }
    if (bySessionName.length > 1) {
      throw ambiguityError(
        `session name '${handle}' is ambiguous`,
        bySessionName,
        "use an id",
      );
    }
    return jsonResponse(
      { session: sessionSummary(bySessionName[0].document) },
      200,
      cors,
    );
  }

  if (bySessionName.length > 1) {
    throw ambiguityError(
      `session name '${handle}' is ambiguous`,
      bySessionName,
      "use an id",
    );
  }
  if (bySessionName.length === 1) {
    return jsonResponse(
      { session: sessionSummary(bySessionName[0].document) },
      200,
      cors,
    );
  }

  const exactId = sessions.filter(
    ({ document }) => document.session_id.toLowerCase() === wanted,
  );
  if (exactId.length > 1) {
    throw ambiguityError(
      `session id '${handle}' is ambiguous`,
      exactId,
      "use a different id",
    );
  }
  if (exactId.length === 1) {
    return jsonResponse(
      { session: sessionSummary(exactId[0].document) },
      200,
      cors,
    );
  }

  const byPrefix = sessions.filter(({ document }) =>
    document.session_id.toLowerCase().startsWith(wanted),
  );
  if (byPrefix.length === 0) {
    throw new HttpError(
      404,
      "session_not_found",
      `no session matches '${handle}'`,
    );
  }
  if (byPrefix.length > 1) {
    throw ambiguityError(
      `session id prefix '${handle}' is ambiguous`,
      byPrefix,
      "use a longer prefix or an id",
    );
  }
  return jsonResponse(
    { session: sessionSummary(byPrefix[0].document) },
    200,
    cors,
  );
}

async function listSessions(env, identity, cors) {
  const profile = await loadProfile(env, identity);
  await ensureDefaultSession(env, identity, profile);
  const entries = await loadSessions(env, identity);
  const sessions = entries.map(({ document }) => sessionSummary(document));
  sessions.sort((left, right) => {
    const leftDefault = left.session_id === DEFAULT_SESSION_ID ? 0 : 1;
    const rightDefault = right.session_id === DEFAULT_SESSION_ID ? 0 : 1;
    if (leftDefault !== rightDefault) {
      return leftDefault - rightDefault;
    }
    return left.session_id.localeCompare(right.session_id);
  });
  return jsonResponse({ sessions }, 200, cors);
}

async function createSessionRequest(env, identity, request, cors) {
  const body = requireObjectBody(await readJson(request));
  const name = requestSessionName(body.name);
  let seed;
  if (body.seed !== undefined) {
    seed = Number(body.seed);
    if (!Number.isInteger(seed) || seed < 0) {
      throw new HttpError(400, "invalid_request", "seed must be an integer");
    }
  }
  const profile = await loadProfile(env, identity);
  await ensureDefaultSession(env, identity, profile);

  if (name !== null) {
    const wanted = name.toLowerCase();
    const existing = (await loadSessions(env, identity)).find(
      ({ document }) => sessionNameKey(document.name) === wanted,
    );
    if (existing) {
      throw new HttpError(
        409,
        "session_name_taken",
        duplicateNameMessage(name, existing),
      );
    }
  }

  const session = createSession(catalog, profile.document, {
    name,
    filter: body.filter,
    settings: body.settings ?? profile.document.settings,
    seed,
  });

  if (session.queue.length === 0) {
    throw new HttpError(
      422,
      "empty_pool",
      "no eligible birds match this filter",
    );
  }

  await writeJsonObject(
    env.PROGRESS,
    sessionKey(identity, session.session_id),
    session,
  );
  return jsonResponse(
    sessionView(catalog, profile.document, session),
    201,
    cors,
  );
}

async function prepareSession(env, identity, sessionId, lookahead, cors) {
  const profile = await loadProfile(env, identity);
  await ensureDefaultSession(env, identity, profile);
  const session = await loadSession(env, identity, sessionId);
  prunePassed(catalog, profile.document, session.document);
  session.document.updated_at = new Date().toISOString();
  await writeJsonObject(
    env.PROGRESS,
    sessionKey(identity, sessionId),
    session.document,
    session.revision,
  );
  return jsonResponse(
    sessionView(catalog, profile.document, session.document, lookahead),
    200,
    cors,
  );
}

async function renameSession(env, identity, sessionId, request, lookahead, cors) {
  const body = requireObjectBody(await readJson(request));
  if (!Object.hasOwn(body, "name")) {
    throw new HttpError(
      400,
      "invalid_request",
      "name is required (use null to clear it)",
    );
  }
  const name = body.name === null ? null : requestSessionName(body.name);
  const profile = await loadProfile(env, identity);
  await ensureDefaultSession(env, identity, profile);
  const session = await loadSession(env, identity, sessionId);
  if (isDefaultSession(session.document)) {
    throw new HttpError(
      409,
      "session_default",
      `the default session cannot be renamed: ${sessionLabel(session.document)} (protected)`,
    );
  }
  if (name !== null) {
    const wanted = name.toLowerCase();
    const existing = (await loadSessions(env, identity)).find(
      ({ document }) =>
        document.session_id !== sessionId &&
        sessionNameKey(document.name) === wanted,
    );
    if (existing) {
      throw new HttpError(
        409,
        "session_name_taken",
        duplicateNameMessage(name, existing),
      );
    }
  }
  session.document.name = name;
  session.document.updated_at = new Date().toISOString();
  await writeJsonObject(
    env.PROGRESS,
    sessionKey(identity, sessionId),
    session.document,
    session.revision,
  );
  return jsonResponse(
    sessionView(catalog, profile.document, session.document, lookahead),
    200,
    cors,
  );
}

async function deleteSession(env, identity, sessionId, cors) {
  const profile = await loadProfile(env, identity);
  await ensureDefaultSession(env, identity, profile);
  const session = await loadSession(env, identity, sessionId);
  if (isDefaultSession(session.document)) {
    throw new HttpError(
      409,
      "session_default",
      `the default session cannot be deleted: ${sessionLabel(session.document)} (protected)`,
    );
  }
  await env.PROGRESS.delete(sessionKey(identity, sessionId));
  return new Response(null, { status: 204, headers: cors });
}

async function answerRequest(env, identity, sessionId, request, lookahead, cors) {
  const body = requireObjectBody(await readJson(request));
  const profile = await loadProfile(env, identity);
  const session = await loadSession(env, identity, sessionId);
  const card = assertCurrent(session.document, String(body.card_uid ?? ""));
  const view = cardFor(catalog, card);
  const action = String(body.action ?? "");

  let feedback = null;

  if (card.type === "L") {
    requireAction(action, "advance");
    consume(catalog, profile.document, session.document, "advance");
  } else {
    requireAction(action, "answer");
    const graded = gradeAnswer(
      catalog,
      card.species_id,
      card.type,
      view,
      body,
      card.attempt,
    );
    feedback = graded.feedback;
    if (graded.outcome === "correct") {
      consume(catalog, profile.document, session.document, "correct");
    } else if (graded.outcome === "near_miss") {
      consume(catalog, profile.document, session.document, "near_miss");
    } else if (graded.outcome === "retry") {
      markRetry(session.document);
    } else if (graded.outcome === "wrong") {
      consume(catalog, profile.document, session.document, "wrong");
    } else if (graded.outcome === "graded") {
      consume(catalog, profile.document, session.document, "advance");
    } else {
      throw new HttpError(
        500,
        "invalid_outcome",
        "grading returned an unknown outcome",
      );
    }
  }

  profile.document.updated_at = new Date().toISOString();
  await writeJsonObject(
    env.PROGRESS,
    sessionKey(identity, sessionId),
    session.document,
    session.revision,
  );
  await writeJsonObject(
    env.PROGRESS,
    profileKey(identity),
    profile.document,
    profile.revision,
  );

  return jsonResponse(
    {
      feedback,
      session: sessionView(
        catalog,
        profile.document,
        session.document,
        lookahead,
      ),
    },
    200,
    cors,
  );
}

function requireAction(actual, expected) {
  if (actual !== expected) {
    throw new HttpError(
      400,
      "invalid_action",
      `expected action ${JSON.stringify(expected)}`,
    );
  }
}
