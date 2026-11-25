import assert from "node:assert/strict";
import test from "node:test";

import worker from "../src/index.js";
import {
  bytesToBase64,
  derivePassword,
  verifyToken,
} from "../src/core.js";
import { FakeBucket } from "./support/fake-bucket.js";

function makeEnv() {
  return {
    PROGRESS: new FakeBucket(),
    AUTH_SECRET: "test-secret",
    ALLOWED_ORIGINS: "https://regevran.github.io",
    TOKEN_TTL_SECONDS: "3600",
  };
}

async function userEntry(password, saltByte, scope = "profile") {
  const salt = new Uint8Array(16).fill(saltByte);
  const derived = await derivePassword(password, salt, 1000);
  return {
    iterations: 1000,
    salt: bytesToBase64(salt),
    hash: bytesToBase64(derived),
    scope,
  };
}

async function seedUsers(env) {
  const users = {
    alice: await userEntry("alice-password", 1),
    bob: await userEntry("bob-password", 2),
    tester: await userEntry("tester-password", 3, "tests"),
  };
  await env.PROGRESS.put("users.json", JSON.stringify({ users }));
}

function request(path, { method = "GET", token, body, headers = {} } = {}) {
  const init = { method, headers: { ...headers } };
  if (token) {
    init.headers.Authorization = `Bearer ${token}`;
  }
  if (body !== undefined) {
    init.body = typeof body === "string" ? body : JSON.stringify(body);
    init.headers["Content-Type"] = "application/json";
  }
  return new Request(`https://worker.test${path}`, init);
}

async function login(env, username, password) {
  const response = await worker.fetch(
    request("/login", { method: "POST", body: { username, password } }),
    env,
  );
  return { response, data: await response.json() };
}

async function tokenFor(env, username, password) {
  const { response, data } = await login(env, username, password);
  assert.equal(response.status, 200);
  return data.token;
}

test("health is public", async () => {
  const env = makeEnv();
  const response = await worker.fetch(request("/health"), env);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    ok: true,
    service: "birds-progress",
  });
});

test("login returns a verifiable token", async () => {
  const env = makeEnv();
  await seedUsers(env);

  const { response, data } = await login(
    env,
    "alice",
    "alice-password",
  );
  assert.equal(response.status, 200);
  assert.equal(data.username, "alice");
  assert.equal(data.scope, "profile");

  const payload = await verifyToken(data.token, env.AUTH_SECRET);
  assert.equal(payload.u, "alice");
  assert.equal(payload.s, "profile");
});

test("login rejects wrong, unknown and incomplete credentials", async () => {
  const env = makeEnv();
  await seedUsers(env);

  const wrong = await login(env, "alice", "nope");
  assert.equal(wrong.response.status, 401);
  assert.equal(wrong.data.error, "invalid_credentials");

  const unknown = await login(env, "nobody", "nope");
  assert.equal(unknown.response.status, 401);
  assert.equal(unknown.data.error, "invalid_credentials");

  const missing = await worker.fetch(
    request("/login", { method: "POST", body: { username: "alice" } }),
    env,
  );
  assert.equal(missing.status, 400);
  assert.equal((await missing.json()).error, "invalid_request");
});

test("login fails cleanly without a provisioned users file", async () => {
  const env = makeEnv();
  const { response, data } = await login(env, "alice", "alice-password");
  assert.equal(response.status, 500);
  assert.equal(data.error, "users_missing");
});

test("file routes require a token", async () => {
  const env = makeEnv();
  await seedUsers(env);
  const response = await worker.fetch(request("/fs/profile.json"), env);
  assert.equal(response.status, 401);
  assert.equal((await response.json()).error, "unauthorized");
});

test("profile files round-trip under the user prefix", async () => {
  const env = makeEnv();
  await seedUsers(env);
  const token = await tokenFor(env, "alice", "alice-password");

  const created = await worker.fetch(
    request("/fs/profile.json", {
      method: "PUT",
      token,
      body: { revision: 1 },
    }),
    env,
  );
  assert.equal(created.status, 200);
  const createdBody = await created.json();
  assert.equal(createdBody.path, "profile.json");
  assert.match(createdBody.revision, /^rev-/);
  assert.equal(env.PROGRESS.objects.has("users/alice/profile.json"), true);

  const session = await worker.fetch(
    request("/fs/sessions/s1.json", {
      method: "PUT",
      token,
      body: { queue: [] },
    }),
    env,
  );
  assert.equal(session.status, 200);

  const fetched = await worker.fetch(
    request("/fs/profile.json", { token }),
    env,
  );
  assert.equal(fetched.status, 200);
  assert.equal(fetched.headers.get("X-Revision"), createdBody.revision);
  assert.match(fetched.headers.get("ETag"), /^"rev-/);
  assert.deepEqual(await fetched.json(), { revision: 1 });

  const rootList = await worker.fetch(
    request("/fs?prefix=", { token }),
    env,
  );
  const rootBody = await rootList.json();
  assert.deepEqual(
    rootBody.objects.map((object) => object.path),
    ["profile.json", "sessions/s1.json"],
  );

  const sessionList = await worker.fetch(
    request("/fs?prefix=sessions/", { token }),
    env,
  );
  const sessionBody = await sessionList.json();
  assert.deepEqual(
    sessionBody.objects.map((object) => object.path),
    ["sessions/s1.json"],
  );
});

test("If-Match enforces revisions", async () => {
  const env = makeEnv();
  await seedUsers(env);
  const token = await tokenFor(env, "alice", "alice-password");

  const first = await worker.fetch(
    request("/fs/profile.json", {
      method: "PUT",
      token,
      body: { revision: 1 },
    }),
    env,
  );
  const firstBody = await first.json();

  const second = await worker.fetch(
    request("/fs/profile.json", {
      method: "PUT",
      token,
      body: { revision: 2 },
      headers: { "If-Match": firstBody.revision },
    }),
    env,
  );
  assert.equal(second.status, 200);
  const secondBody = await second.json();
  assert.notEqual(secondBody.revision, firstBody.revision);

  const stale = await worker.fetch(
    request("/fs/profile.json", {
      method: "PUT",
      token,
      body: { revision: 3 },
      headers: { "If-Match": firstBody.revision },
    }),
    env,
  );
  assert.equal(stale.status, 412);
  assert.equal((await stale.json()).error, "revision_conflict");
});

test("delete removes the file", async () => {
  const env = makeEnv();
  await seedUsers(env);
  const token = await tokenFor(env, "alice", "alice-password");

  await worker.fetch(
    request("/fs/profile.json", {
      method: "PUT",
      token,
      body: { revision: 1 },
    }),
    env,
  );

  const deleted = await worker.fetch(
    request("/fs/profile.json", { method: "DELETE", token }),
    env,
  );
  assert.equal(deleted.status, 204);

  const missing = await worker.fetch(
    request("/fs/profile.json", { token }),
    env,
  );
  assert.equal(missing.status, 404);
});

test("users cannot escape their prefix", async () => {
  const env = makeEnv();
  await seedUsers(env);
  const alice = await tokenFor(env, "alice", "alice-password");
  const bob = await tokenFor(env, "bob", "bob-password");

  await worker.fetch(
    request("/fs/profile.json", {
      method: "PUT",
      token: alice,
      body: { owner: "alice" },
    }),
    env,
  );

  const probe = await worker.fetch(
    request("/fs/%252e%252e/alice/profile.json", { token: bob }),
    env,
  );
  assert.equal(probe.status, 400);

  const bobProfile = await worker.fetch(
    request("/fs/profile.json", { token: bob }),
    env,
  );
  assert.equal(bobProfile.status, 404);
});

test("CORS allows the configured origin and rejects others", async () => {
  const env = makeEnv();
  await seedUsers(env);
  const token = await tokenFor(env, "alice", "alice-password");

  const preflight = await worker.fetch(
    request("/fs/profile.json", {
      method: "OPTIONS",
      headers: { Origin: "https://regevran.github.io" },
    }),
    env,
  );
  assert.equal(preflight.status, 204);
  assert.equal(
    preflight.headers.get("Access-Control-Allow-Origin"),
    "https://regevran.github.io",
  );
  assert.match(
    preflight.headers.get("Access-Control-Allow-Methods"),
    /POST/,
  );

  const allowed = await worker.fetch(
    request("/fs/profile.json", {
      token,
      headers: { Origin: "https://regevran.github.io" },
    }),
    env,
  );
  assert.equal(
    allowed.headers.get("Access-Control-Allow-Origin"),
    "https://regevran.github.io",
  );

  const rejected = await worker.fetch(
    request("/fs/profile.json", {
      token,
      headers: { Origin: "https://evil.example" },
    }),
    env,
  );
  assert.equal(rejected.status, 403);
  assert.equal((await rejected.json()).error, "forbidden_origin");
});

test("bodies are capped at one megabyte", async () => {
  const env = makeEnv();
  await seedUsers(env);
  const token = await tokenFor(env, "alice", "alice-password");

  const tooLarge = new Uint8Array(1024 * 1024 + 1);
  const response = await worker.fetch(
    new Request("https://worker.test/fs/big.bin", {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/octet-stream",
      },
      body: tooLarge,
    }),
    env,
  );
  assert.equal(response.status, 413);
});

test("unknown routes and methods fail cleanly", async () => {
  const env = makeEnv();
  await seedUsers(env);
  const token = await tokenFor(env, "alice", "alice-password");

  const missing = await worker.fetch(request("/nope"), env);
  assert.equal(missing.status, 404);

  const badMethod = await worker.fetch(
    request("/fs", { method: "POST", token, body: {} }),
    env,
  );
  assert.equal(badMethod.status, 405);
});
