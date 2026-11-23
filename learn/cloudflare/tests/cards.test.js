import assert from "node:assert/strict";
import test from "node:test";

import { signToken } from "../src/core.js";
import worker from "../src/index.js";
import { catalog } from "../src/trainer/dataset.js";
import { FakeBucket } from "./support/fake-bucket.js";

const SECRET = "test-secret";
const SPECIES = "acrocephalus-agricola";

function makeEnv() {
  return {
    PROGRESS: new FakeBucket(),
    AUTH_SECRET: SECRET,
    ALLOWED_ORIGINS: "https://regevran.github.io",
  };
}

async function token() {
  return signToken(
    {
      u: "alice",
      s: "profile",
      exp: Math.floor(Date.now() / 1000) + 3600,
    },
    SECRET,
  );
}

async function post(env, auth, path, body) {
  const response = await worker.fetch(
    new Request(`https://worker.test${path}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${auth}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body ?? {}),
    }),
    env,
  );
  const text = await response.text();
  return {
    status: response.status,
    document: text ? JSON.parse(text) : null,
  };
}

async function card(env, auth, cardType, seed = 7) {
  const response = await post(env, auth, "/app/cards", {
    species_id: SPECIES,
    card_type: cardType,
    seed,
  });
  assert.equal(response.status, 200);
  return response.document.card;
}

async function answer(env, auth, cardType, body) {
  return await post(env, auth, "/app/cards/answer", {
    species_id: SPECIES,
    card_type: cardType,
    seed: 7,
    ...body,
  });
}

test("bird search keeps the text-client matching rules", async () => {
  const env = makeEnv();
  const auth = await token();

  const one = await post(env, auth, "/app/birds", {
    q: "PADDYFIELD warbler",
  });
  assert.equal(one.status, 200);
  assert.equal(one.document.count, 1);
  const bird = one.document.birds[0];
  assert.equal(bird.species_id, SPECIES);
  assert.equal(bird.latin, "Acrocephalus agricola");
  assert.equal(bird.has_hebrew, true);
  assert.equal(bird.has_parts, true);
  assert.ok(Array.isArray(bird.status_categories));

  const all = await post(env, auth, "/app/birds", {});
  assert.equal(all.document.count, catalog.birds.length);
  assert.equal(all.document.birds.length, catalog.birds.length);

  const none = await post(env, auth, "/app/birds", {
    q: "paddyfield goose",
  });
  assert.equal(none.document.count, 0);
  assert.deepEqual(none.document.birds, []);

  const bad = await post(env, auth, "/app/birds", { q: 3 });
  assert.equal(bad.status, 400);
});

test("search also matches element meanings and reports why", async () => {
  const env = makeEnv();
  const auth = await token();

  const response = await post(env, auth, "/app/birds", { q: "summit" });
  assert.equal(response.status, 200);
  assert.equal(response.document.count, 10);
  const bird = response.document.birds.find(
    (item) => item.species_id === SPECIES,
  );
  assert.deepEqual(bird.matched, [
    {
      kind: "element",
      element_id: "acro",
      texts: [{ field: "en", text: "summit, peak" }],
    },
  ]);
  assert.deepEqual(
    response.document.elements.map((element) => element.element_id),
    ["acro"],
  );
  assert.equal(response.document.elements[0].en, "summit, peak");
  assert.equal(response.document.elements[0].he, "פסגה");
  assert.equal(response.document.elements[0].bird_count, 10);
});

test("Hebrew gloss search reports the Hebrew match text", async () => {
  const env = makeEnv();
  const auth = await token();

  const response = await post(env, auth, "/app/birds", { q: "חגב" });
  assert.equal(response.status, 200);
  assert.deepEqual(
    response.document.elements.map((element) => element.element_id),
    ["acrido", "locust"],
  );
  const myna = response.document.birds.find(
    (bird) => bird.species_id === "acridotheres-tristis",
  );
  assert.deepEqual(myna.matched, [
    {
      kind: "element",
      element_id: "acrido",
      texts: [{ field: "he", text: "חגב" }],
    },
  ]);
});

test("name matches come before element-only matches", async () => {
  const env = makeEnv();
  const auth = await token();

  const response = await post(env, auth, "/app/birds", { q: "locust" });
  const named = response.document.birds.map((bird) =>
    bird.matched.some((match) => match.kind === "name"),
  );
  const firstElementOnly = named.indexOf(false);
  assert.ok(firstElementOnly > 0);
  assert.ok(named.slice(firstElementOnly).every((value) => !value));
  const myna = response.document.birds.find(
    (bird) => bird.species_id === "acridotheres-tristis",
  );
  assert.deepEqual(myna.matched, [
    {
      kind: "element",
      element_id: "acrido",
      texts: [{ field: "en", text: "locust" }],
    },
  ]);
});

test("a bird can match through several elements", async () => {
  const env = makeEnv();
  const auth = await token();

  const response = await post(env, auth, "/app/birds", {
    q: "white head",
  });
  assert.deepEqual(response.document.elements, []);
  const goose = response.document.birds.find(
    (bird) => bird.species_id === "anser-albifrons",
  );
  const elementIds = goose.matched
    .filter((match) => match.kind === "element")
    .map((match) => match.element_id);
  assert.deepEqual(elementIds, ["alb", "frons"]);
});

test("an empty search lists every bird without match reasons", async () => {
  const env = makeEnv();
  const auth = await token();

  const response = await post(env, auth, "/app/birds", {});
  assert.deepEqual(response.document.elements, []);
  assert.ok(
    response.document.birds.every((bird) => bird.matched.length === 0),
  );
});

test("card views expose prompts and options but not answers", async () => {
  const env = makeEnv();
  const auth = await token();

  const learn = await card(env, auth, "L");
  assert.equal(learn.latin, "Acrocephalus agricola");

  const elements = await card(env, auth, "E");
  assert.equal(elements.family, "Acrocephalidae");
  for (const row of elements.rows) {
    assert.equal("expected" in row, false);
    assert.equal("correct" in row, false);
  }

  const recognize = await card(env, auth, "R");
  assert.equal(recognize.family, "Acrocephalidae");
  for (const option of recognize.options) {
    assert.deepEqual(Object.keys(option).sort(), ["latin", "species_id"]);
  }

  const construct = await card(env, auth, "C");
  assert.equal(construct.family, "Acrocephalidae");
  assert.equal("latin" in construct, false);
  assert.ok(construct.genus_parts.length > 0);

  const produce = await card(env, auth, "F");
  assert.deepEqual(Object.keys(produce).sort(), [
    "card_type",
    "family",
    "hebrew",
    "species_id",
  ]);
  assert.equal(produce.card_type, "F");
  assert.equal(produce.family, "Acrocephalidae");
});

test("card requests validate species, type, seed and method", async () => {
  const env = makeEnv();
  const auth = await token();

  let response = await post(env, auth, "/app/cards", {
    species_id: "not-a-bird",
    card_type: "F",
  });
  assert.equal(response.status, 404);
  assert.equal(response.document.error, "bird_not_found");

  response = await post(env, auth, "/app/cards", {
    species_id: SPECIES,
    card_type: "V",
  });
  assert.equal(response.status, 400);
  assert.equal(response.document.error, "unsupported_card");

  response = await post(env, auth, "/app/cards", {
    species_id: SPECIES,
    card_type: "f",
    seed: -1,
  });
  assert.equal(response.status, 400);

  response = await post(env, auth, "/app/cards", {
    species_id: SPECIES,
    card_type: "f",
  });
  assert.equal(response.status, 200);
  assert.equal(response.document.card.card_type, "F");

  const get = await worker.fetch(
    new Request("https://worker.test/app/cards", {
      method: "GET",
      headers: { Authorization: `Bearer ${auth}` },
    }),
    env,
  );
  assert.equal(get.status, 405);

  const anonymous = await worker.fetch(
    new Request("https://worker.test/app/cards", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }),
    env,
  );
  assert.equal(anonymous.status, 401);
});

test("element answers are graded in one pass", async () => {
  const env = makeEnv();
  const auth = await token();
  const view = await card(env, auth, "E");

  const correct = Object.fromEntries(
    view.rows.map((row) => [
      row.element_id,
      catalog.element(row.element_id).he,
    ]),
  );
  const response = await answer(env, auth, "E", { choices: correct });
  assert.equal(response.status, 200);
  assert.equal(response.document.feedback.kind, "elements");
  assert.equal(
    response.document.feedback.correct,
    response.document.feedback.total,
  );

  const wrong = await answer(env, auth, "E", {
    choices: Object.fromEntries(
      view.rows.map((row) => [row.element_id, row.options[0]]),
    ),
  });
  assert.equal(wrong.status, 200);
  for (const result of wrong.document.feedback.results) {
    assert.equal(typeof result.expected, "string");
  }
});

test("recognize answers retry once and then reveal", async () => {
  const env = makeEnv();
  const auth = await token();
  const view = await card(env, auth, "R");
  const correct = catalog.birdsWithHebrew(view.hebrew)[0].species_id;
  const wrong = view.options.find(
    (option) => option.species_id !== correct,
  ).species_id;

  let response = await answer(env, auth, "R", {
    choice: wrong,
    attempt: 1,
  });
  assert.equal(response.status, 200);
  assert.equal(response.document.feedback.kind, "retry");
  assert.equal("accepted" in response.document.feedback, false);

  response = await answer(env, auth, "R", {
    choice: wrong,
    attempt: 2,
  });
  assert.equal(response.document.feedback.kind, "recognize");
  assert.equal(response.document.feedback.result.correct, false);
  assert.equal(
    response.document.feedback.result.accepted[0],
    "Acrocephalus agricola",
  );

  response = await answer(env, auth, "R", {
    choice: correct,
    attempt: 1,
  });
  assert.equal(response.document.feedback.result.correct, true);
});

test("typed answers handle near misses and the two-attempt flow", async () => {
  const env = makeEnv();
  const auth = await token();

  let response = await answer(env, auth, "C", {
    response: "Acrocephalus agricolo",
  });
  assert.equal(response.status, 200);
  assert.equal(response.document.feedback.kind, "latin");
  assert.equal(response.document.feedback.result.outcome, "near_miss");

  response = await answer(env, auth, "F", {
    response: "Corvus corax",
    attempt: 1,
  });
  assert.equal(response.document.feedback.kind, "retry");
  assert.equal("expected" in response.document.feedback, false);

  response = await answer(env, auth, "F", {
    response: "Corvus corax",
    attempt: 2,
  });
  assert.equal(response.document.feedback.kind, "latin");
  assert.equal(response.document.feedback.result.outcome, "wrong");
  assert.equal(
    response.document.feedback.result.expected,
    "Acrocephalus agricola",
  );

  response = await answer(env, auth, "F", {
    response: "  acrocephalus   AGRICOLA ",
  });
  assert.equal(response.document.feedback.result.outcome, "correct");
});

test("stateless grading validates its inputs", async () => {
  const env = makeEnv();
  const auth = await token();

  let response = await answer(env, auth, "L", {});
  assert.equal(response.status, 400);
  assert.equal(response.document.error, "not_answerable");

  response = await answer(env, auth, "F", {
    response: "Acrocephalus agricola",
    attempt: 3,
  });
  assert.equal(response.status, 400);

  response = await answer(env, auth, "R", { attempt: 1 });
  assert.equal(response.status, 400);
  assert.equal(response.document.error, "invalid_request");

  response = await answer(env, auth, "F", { attempt: 1 });
  assert.equal(response.status, 400);
});
