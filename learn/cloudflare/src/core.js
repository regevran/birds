/* Pure helpers for the progress Worker: paths, tokens, passwords, CORS.
 *
 * Nothing in this module touches R2 or routes HTTP; that keeps the security
 * sensitive pieces small and testable with Node's built-in test runner.
 */

const encoder = new TextEncoder();
const decoder = new TextDecoder();

export const DEFAULT_ITERATIONS = 1000;
export const DEFAULT_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60;
export const MAX_BODY_BYTES = 1024 * 1024;
export const MAX_LOGIN_BYTES = 8 * 1024;
export const SCOPES = new Set(["profile"]);

export class HttpError extends Error {
  constructor(status, code, message) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.code = code;
  }
}

export function jsonResponse(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      ...headers,
    },
  });
}

export function errorResponse(error, headers = {}) {
  if (error instanceof HttpError) {
    return jsonResponse(
      { error: error.code, message: error.message },
      error.status,
      headers,
    );
  }
  return jsonResponse(
    { error: "internal_error", message: "internal error" },
    500,
    headers,
  );
}

/* ---------------------------------------------------------------- base64 */

export function bytesToBase64(bytes) {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

export function base64ToBytes(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

export function bytesToBase64Url(bytes) {
  return bytesToBase64(bytes)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

export function base64UrlToBytes(value) {
  const padded = String(value).replace(/-/g, "+").replace(/_/g, "/");
  const remainder = padded.length % 4;
  return base64ToBytes(
    remainder === 0 ? padded : padded + "=".repeat(4 - remainder),
  );
}

export function equalBytes(left, right) {
  if (left.length !== right.length) {
    return false;
  }
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left[index] ^ right[index];
  }
  return difference === 0;
}

/* ------------------------------------------------------------------ paths */

export function normalizeUsername(value) {
  return String(value ?? "").trim().toLowerCase();
}

export function isValidUsername(name) {
  return /^[a-z0-9][a-z0-9_-]{0,63}$/.test(String(name));
}

export function normalizePath(value) {
  const raw = String(value ?? "");
  if (raw.length === 0) {
    throw new HttpError(400, "invalid_path", "path is required");
  }
  if (raw.length > 512) {
    throw new HttpError(400, "invalid_path", "path is too long");
  }
  if (raw.startsWith("/")) {
    throw new HttpError(400, "invalid_path", "path must be relative");
  }
  if (!/^[A-Za-z0-9._/-]+$/.test(raw)) {
    throw new HttpError(400, "invalid_path", "path has invalid characters");
  }
  const segments = raw.split("/");
  for (const segment of segments) {
    if (segment === "" || segment === "." || segment === "..") {
      throw new HttpError(400, "invalid_path", "path has invalid segments");
    }
  }
  return segments.join("/");
}

export function normalizePrefix(value) {
  const raw = String(value ?? "");
  if (raw === "") {
    return "";
  }
  const trailingSlash = raw.endsWith("/");
  const trimmed = trailingSlash ? raw.replace(/\/+$/g, "") : raw;
  if (trimmed === "") {
    return "";
  }
  const normalized = normalizePath(trimmed);
  return trailingSlash ? `${normalized}/` : normalized;
}

export function scopeBase(scope, username) {
  if (scope !== "profile" || !isValidUsername(username)) {
    throw new HttpError(401, "unauthorized", "invalid token");
  }
  return `users/${username}/`;
}

export function physicalKey(scope, username, path) {
  return scopeBase(scope, username) + normalizePath(path);
}

export function logicalPath(scope, username, key) {
  const base = scopeBase(scope, username);
  return key.startsWith(base) ? key.slice(base.length) : null;
}

export function revisionOf(etag) {
  return String(etag ?? "").replace(/^"(.*)"$/, "$1");
}

/* ------------------------------------------------------------------ tokens */

async function hmacSha256(secret, message) {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return new Uint8Array(
    await crypto.subtle.sign("HMAC", key, encoder.encode(message)),
  );
}

export async function signToken(payload, secret) {
  if (!secret) {
    throw new HttpError(500, "server_misconfigured", "missing secret");
  }
  const body = bytesToBase64Url(encoder.encode(JSON.stringify(payload)));
  const signature = bytesToBase64Url(await hmacSha256(secret, body));
  return `${body}.${signature}`;
}

export async function verifyToken(
  token,
  secret,
  { now = Math.floor(Date.now() / 1000) } = {},
) {
  if (!secret) {
    throw new HttpError(500, "server_misconfigured", "missing secret");
  }
  const parts = String(token ?? "").split(".");
  if (parts.length !== 2 || !parts[0] || !parts[1]) {
    throw new HttpError(401, "unauthorized", "invalid token");
  }
  const [body, signature] = parts;
  let expected;
  let supplied;
  let payload;
  try {
    expected = await hmacSha256(secret, body);
    supplied = base64UrlToBytes(signature);
    payload = JSON.parse(decoder.decode(base64UrlToBytes(body)));
  } catch {
    throw new HttpError(401, "unauthorized", "invalid token");
  }
  if (!equalBytes(expected, supplied)) {
    throw new HttpError(401, "unauthorized", "invalid token");
  }
  if (
    payload === null ||
    typeof payload !== "object" ||
    !isValidUsername(payload.u) ||
    !SCOPES.has(payload.s) ||
    !Number.isInteger(payload.exp)
  ) {
    throw new HttpError(401, "unauthorized", "invalid token");
  }
  if (payload.exp <= now) {
    throw new HttpError(401, "token_expired", "token expired");
  }
  return payload;
}

export function bearerToken(request) {
  const header = request.headers.get("Authorization") ?? "";
  if (!header.startsWith("Bearer ")) {
    throw new HttpError(401, "unauthorized", "missing token");
  }
  const token = header.slice("Bearer ".length).trim();
  if (!token) {
    throw new HttpError(401, "unauthorized", "missing token");
  }
  return token;
}

/* ---------------------------------------------------------------- passwords */

export async function derivePassword(password, salt, iterations) {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt, iterations, hash: "SHA-256" },
    key,
    256,
  );
  return new Uint8Array(bits);
}

export async function verifyPassword(
  password,
  entry,
  defaultIterations = DEFAULT_ITERATIONS,
) {
  try {
    if (entry === null || typeof entry !== "object") {
      return false;
    }
    const iterations = Number(entry.iterations ?? defaultIterations);
    if (
      !Number.isInteger(iterations) ||
      iterations < 1 ||
      iterations > 1_000_000
    ) {
      return false;
    }
    const salt = base64ToBytes(String(entry.salt ?? ""));
    const expected = base64ToBytes(String(entry.hash ?? ""));
    if (salt.length < 8 || expected.length !== 32) {
      return false;
    }
    const actual = await derivePassword(password, salt, iterations);
    return equalBytes(actual, expected);
  } catch {
    return false;
  }
}

export async function dummyPasswordCheck(password) {
  try {
    await derivePassword(
      String(password ?? ""),
      new Uint8Array(16),
      DEFAULT_ITERATIONS,
    );
  } catch {
    /* ignore: the caller always returns the same generic failure */
  }
}

/* ------------------------------------------------------------------- body */

export async function readBody(request, maxBytes = MAX_BODY_BYTES) {
  const declared = Number(request.headers.get("Content-Length") ?? 0);
  if (declared > maxBytes) {
    throw new HttpError(413, "payload_too_large", "body is too large");
  }
  const buffer = await request.arrayBuffer();
  if (buffer.byteLength > maxBytes) {
    throw new HttpError(413, "payload_too_large", "body is too large");
  }
  return new Uint8Array(buffer);
}

export async function readJson(request, maxBytes = MAX_BODY_BYTES) {
  const bytes = await readBody(request, maxBytes);
  try {
    return JSON.parse(decoder.decode(bytes));
  } catch {
    throw new HttpError(400, "invalid_json", "invalid JSON body");
  }
}

/* ------------------------------------------------------------------- CORS */

export function allowedOrigins(env) {
  const configured = String(env?.ALLOWED_ORIGINS ?? "").trim();
  return configured || "https://regevran.github.io";
}

export function isAllowedOrigin(origin, configured) {
  if (!origin) {
    return false;
  }
  const listed = String(configured ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  if (listed.includes(origin)) {
    return true;
  }
  return /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin);
}

export function corsHeaders(origin, configured) {
  if (!origin || !isAllowedOrigin(origin, configured)) {
    return {};
  }
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type, If-Match",
    "Access-Control-Expose-Headers": "ETag, X-Revision",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

export function checkOrigin(request, env) {
  const origin = request.headers.get("Origin");
  if (origin && !isAllowedOrigin(origin, allowedOrigins(env))) {
    throw new HttpError(403, "forbidden_origin", "origin not allowed");
  }
}
