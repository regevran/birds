/* Cloudflare Worker: authenticated file storage for trainer progress.
 *
 * The Worker is deliberately a file store, not a trainer API.  The Python
 * client and the browser client decide what profile.json and session files
 * mean; this module only authenticates, scopes paths and reads/writes R2.
 */

import {
  DEFAULT_TOKEN_TTL_SECONDS,
  HttpError,
  MAX_LOGIN_BYTES,
  allowedOrigins,
  bearerToken,
  checkOrigin,
  corsHeaders,
  dummyPasswordCheck,
  errorResponse,
  isValidUsername,
  jsonResponse,
  normalizePath,
  normalizePrefix,
  normalizeUsername,
  physicalKey,
  readBody,
  readJson,
  revisionOf,
  scopeBase,
  signToken,
  verifyPassword,
  verifyToken,
} from "./core.js";

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin");
    const cors = corsHeaders(origin, allowedOrigins(env));
    try {
      checkOrigin(request, env);

      if (request.method === "OPTIONS") {
        return new Response(null, { status: 204, headers: cors });
      }

      const url = new URL(request.url);

      if (url.pathname === "/health" && request.method === "GET") {
        return jsonResponse(
          { ok: true, service: "birds-progress" },
          200,
          cors,
        );
      }

      if (url.pathname === "/login") {
        if (request.method !== "POST") {
          throw new HttpError(405, "method_not_allowed", "method not allowed");
        }
        return await handleLogin(request, env, cors);
      }

      if (url.pathname === "/fs") {
        if (request.method !== "GET") {
          throw new HttpError(405, "method_not_allowed", "method not allowed");
        }
        return await handleList(request, env, cors);
      }

      if (url.pathname.startsWith("/fs/")) {
        const path = decodePath(url);
        if (request.method === "GET") {
          return await handleGet(path, request, env, cors);
        }
        if (request.method === "PUT") {
          return await handlePut(path, request, env, cors);
        }
        if (request.method === "DELETE") {
          return await handleDelete(path, request, env, cors);
        }
        throw new HttpError(405, "method_not_allowed", "method not allowed");
      }

      throw new HttpError(404, "not_found", "not found");
    } catch (error) {
      if (!(error instanceof HttpError)) {
        console.error(error);
      }
      return errorResponse(error, cors);
    }
  },
};

function decodePath(url) {
  try {
    return decodeURIComponent(url.pathname.slice("/fs/".length));
  } catch {
    throw new HttpError(400, "invalid_path", "invalid path");
  }
}

async function handleLogin(request, env, cors) {
  const body = await readJson(request, MAX_LOGIN_BYTES);
  const username = normalizeUsername(body?.username);
  const password = String(body?.password ?? "");

  if (!username || !password) {
    throw new HttpError(
      400,
      "invalid_request",
      "username and password are required",
    );
  }

  const users = await loadUsers(env.PROGRESS);
  const entry = users[username];

  if (
    !isValidUsername(username) ||
    entry === undefined ||
    entry.disabled === true
  ) {
    await dummyPasswordCheck(password);
    throw new HttpError(401, "invalid_credentials", "invalid username or password");
  }

  const matches = await verifyPassword(password, entry);
  if (!matches) {
    throw new HttpError(401, "invalid_credentials", "invalid username or password");
  }

  const scope = entry.scope === "tests" ? "tests" : "profile";
  const now = Math.floor(Date.now() / 1000);
  const ttl = tokenTtl(env);
  const expires = now + ttl;
  const token = await signToken(
    { u: username, s: scope, exp: expires },
    env.AUTH_SECRET,
  );

  return jsonResponse(
    {
      token,
      username,
      scope,
      expires_at: new Date(expires * 1000).toISOString(),
    },
    200,
    cors,
  );
}

function tokenTtl(env) {
  const configured = Number(env?.TOKEN_TTL_SECONDS);
  return Number.isInteger(configured) && configured > 0
    ? configured
    : DEFAULT_TOKEN_TTL_SECONDS;
}

async function loadUsers(bucket) {
  const object = await bucket.get("users.json");
  if (!object) {
    throw new HttpError(
      500,
      "users_missing",
      "users.json is not provisioned",
    );
  }
  let document;
  try {
    document = await object.json();
  } catch {
    throw new HttpError(500, "users_invalid", "users.json is not valid JSON");
  }
  if (
    document === null ||
    typeof document !== "object" ||
    document.users === null ||
    typeof document.users !== "object" ||
    Array.isArray(document.users)
  ) {
    throw new HttpError(500, "users_invalid", "users.json has no users map");
  }
  return document.users;
}

async function authenticate(request, env) {
  if (!env.AUTH_SECRET) {
    throw new HttpError(500, "server_misconfigured", "missing AUTH_SECRET");
  }
  const payload = await verifyToken(
    bearerToken(request),
    env.AUTH_SECRET,
  );
  return { username: payload.u, scope: payload.s };
}

async function handleList(request, env, cors) {
  const identity = await authenticate(request, env);
  const url = new URL(request.url);
  const prefix = normalizePrefix(url.searchParams.get("prefix") ?? "");
  const limit = listLimit(url.searchParams.get("limit"));
  const cursor = url.searchParams.get("cursor") ?? undefined;
  const base = scopeBase(identity.scope, identity.username);

  const result = await env.PROGRESS.list({
    prefix: base + prefix,
    limit,
    cursor,
  });

  const objects = [];
  for (const object of result.objects) {
    if (!object.key.startsWith(base)) {
      continue;
    }
    objects.push({
      path: object.key.slice(base.length),
      size: object.size,
      revision: revisionOf(object.etag),
      uploaded: uploadedAt(object.uploaded),
    });
  }

  return jsonResponse(
    {
      objects,
      truncated: Boolean(result.truncated),
      cursor: result.cursor ?? null,
    },
    200,
    cors,
  );
}

function listLimit(value) {
  const parsed = Number(value ?? 100);
  if (!Number.isFinite(parsed)) {
    return 100;
  }
  return Math.min(1000, Math.max(1, Math.trunc(parsed)));
}

function uploadedAt(value) {
  if (value instanceof Date) {
    return value.toISOString();
  }
  return value ?? null;
}

async function handleGet(path, request, env, cors) {
  const identity = await authenticate(request, env);
  const key = physicalKey(identity.scope, identity.username, path);
  const object = await env.PROGRESS.get(key);
  if (!object) {
    throw new HttpError(404, "not_found", "file not found");
  }

  const data = await object.arrayBuffer();
  const revision = revisionOf(object.etag);
  return new Response(data, {
    status: 200,
    headers: {
      ...cors,
      "Content-Type": contentTypeFor(path),
      "Content-Length": String(data.byteLength),
      "Cache-Control": "no-store",
      ETag: `"${revision}"`,
      "X-Revision": revision,
    },
  });
}

async function handlePut(path, request, env, cors) {
  const identity = await authenticate(request, env);
  const key = physicalKey(identity.scope, identity.username, path);
  const data = await readBody(request);

  const options = {
    httpMetadata: { contentType: contentTypeFor(path) },
  };
  const ifMatch = request.headers.get("If-Match");
  if (ifMatch) {
    options.onlyIf = { etagMatches: revisionOf(ifMatch) };
  }

  const result = await env.PROGRESS.put(key, data, options);
  if (result === null || result === undefined) {
    throw new HttpError(412, "revision_conflict", "revision conflict");
  }

  return jsonResponse(
    {
      path,
      revision: revisionOf(result.etag),
      size: result.size ?? data.byteLength,
    },
    200,
    cors,
  );
}

async function handleDelete(path, request, env, cors) {
  const identity = await authenticate(request, env);
  const key = physicalKey(identity.scope, identity.username, path);
  await env.PROGRESS.delete(key);
  return new Response(null, { status: 204, headers: cors });
}

function contentTypeFor(path) {
  if (path.endsWith(".json")) {
    return "application/json; charset=utf-8";
  }
  if (path.endsWith(".txt")) {
    return "text/plain; charset=utf-8";
  }
  return "application/octet-stream";
}
