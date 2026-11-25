import assert from "node:assert/strict";
import test from "node:test";

import {
  HttpError,
  allowedOrigins,
  base64ToBytes,
  bytesToBase64,
  corsHeaders,
  derivePassword,
  isAllowedOrigin,
  logicalPath,
  normalizePath,
  normalizePrefix,
  normalizeUsername,
  physicalKey,
  revisionOf,
  scopeBase,
  signToken,
  verifyPassword,
  verifyToken,
} from "../src/core.js";

test("usernames are normalized and validated", () => {
  assert.equal(normalizeUsername("  Ran  "), "ran");
  assert.equal(normalizeUsername(null), "");
  assert.equal(scopeBase("profile", "ran"), "users/ran/");
  assert.throws(() => scopeBase("tests", "ran"), HttpError);
  assert.throws(() => scopeBase("profile", "../ran"), HttpError);
  assert.throws(() => scopeBase("nope", "ran"), HttpError);
});

test("paths reject traversal and empty segments", () => {
  assert.equal(normalizePath("profile.json"), "profile.json");
  assert.equal(
    normalizePath("sessions/2026-11-22-a.json"),
    "sessions/2026-11-22-a.json",
  );

  for (const bad of [
    "",
    "/profile.json",
    "../users/ran/profile.json",
    "sessions/../profile.json",
    "a//b",
    "a/./b",
    "a\\b",
    "a b",
    "a".repeat(513),
  ]) {
    assert.throws(() => normalizePath(bad), HttpError, bad);
  }
});

test("prefixes keep a trailing slash but reject traversal", () => {
  assert.equal(normalizePrefix(""), "");
  assert.equal(normalizePrefix("sessions"), "sessions");
  assert.equal(normalizePrefix("sessions/"), "sessions/");
  assert.throws(() => normalizePrefix("sessions/../"), HttpError);
});

test("physical and logical keys round-trip", () => {
  assert.equal(
    physicalKey("profile", "alice", "profile.json"),
    "users/alice/profile.json",
  );
  assert.equal(
    logicalPath("profile", "alice", "users/alice/sessions/a.json"),
    "sessions/a.json",
  );
  assert.equal(logicalPath("profile", "alice", "users/bob/x.json"), null);
  assert.throws(() => physicalKey("tests", "alice", "fixture.json"), HttpError);
});

test("revisions are opaque strings without optional quotes", () => {
  assert.equal(revisionOf('"abc"'), "abc");
  assert.equal(revisionOf("abc"), "abc");
});

test("tokens verify, expire and reject tampering", async () => {
  const secret = "test-secret";
  const token = await signToken(
    { u: "alice", s: "profile", exp: 1000 },
    secret,
  );

  const payload = await verifyToken(token, secret, { now: 999 });
  assert.equal(payload.u, "alice");
  assert.equal(payload.s, "profile");

  await assert.rejects(
    verifyToken(token, secret, { now: 1000 }),
    /token expired/,
  );
  await assert.rejects(
    verifyToken(token, "other-secret", { now: 999 }),
    /invalid token/,
  );

  const [body, signature] = token.split(".");
  const tampered = `${body}.${signature.slice(0, -1)}A`;
  await assert.rejects(
    verifyToken(tampered, secret, { now: 999 }),
    /invalid token/,
  );
});

test("the PBKDF2 vector matches the Python provisioner", async () => {
  const salt = new Uint8Array(16);
  for (let index = 0; index < salt.length; index += 1) {
    salt[index] = index;
  }
  const derived = await derivePassword(
    "correct horse battery staple",
    salt,
    1000,
  );
  assert.equal(
    bytesToBase64(derived),
    "ppsXnjrdPB4KryJ6DrOqKqhkWrhv7PbKAMF1Eml8cZ4=",
  );
  assert.equal(bytesToBase64(salt), "AAECAwQFBgcICQoLDA0ODw==");

  const entry = {
    iterations: 1000,
    salt: bytesToBase64(salt),
    hash: bytesToBase64(derived),
  };
  assert.equal(
    await verifyPassword("correct horse battery staple", entry),
    true,
  );
  assert.equal(await verifyPassword("wrong password", entry), false);
  assert.equal(await verifyPassword("anything", null), false);
  assert.equal(
    await verifyPassword("anything", { iterations: 0, salt: "", hash: "" }),
    false,
  );
});

test("base64 helpers round-trip binary data", () => {
  const bytes = Uint8Array.from([0, 1, 2, 250, 255]);
  assert.deepEqual(base64ToBytes(bytesToBase64(bytes)), bytes);
});

test("CORS allows the pages origin and any localhost port", () => {
  const configured = "https://regevran.github.io";
  assert.equal(allowedOrigins({}), "https://regevran.github.io");
  assert.equal(isAllowedOrigin("https://regevran.github.io", configured), true);
  assert.equal(isAllowedOrigin("http://localhost:8000", configured), true);
  assert.equal(isAllowedOrigin("http://localhost:9999", configured), true);
  assert.equal(isAllowedOrigin("http://127.0.0.1:8000", configured), true);
  assert.equal(isAllowedOrigin("https://evil.example", configured), false);
  assert.equal(isAllowedOrigin(null, configured), false);

  const headers = corsHeaders("https://regevran.github.io", configured);
  assert.equal(
    headers["Access-Control-Allow-Origin"],
    "https://regevran.github.io",
  );
  assert.match(headers["Access-Control-Expose-Headers"], /X-Revision/);
  assert.match(headers["Access-Control-Allow-Methods"], /POST/);
  assert.deepEqual(corsHeaders("https://evil.example", configured), {});
});
