import assert from "node:assert/strict";
import test from "node:test";

import { catalog } from "../src/trainer/dataset.js";
import { searchBirds } from "../src/trainer/search.js";

function hebrewTokens(latin) {
  const result = searchBirds(catalog, latin);
  const bird = result.birds.find((item) => item.latin === latin);
  assert.ok(bird, latin);
  return bird.tokens
    .filter((token) => token.kind === "hebrew" || token.kind === "hebrew_word")
    .map((token) => token.text);
}

test("hyphenated Hebrew names split without repeating the whole", () => {
  assert.deepEqual(hebrewTokens("Luscinia svecica"), [
    "כחול-החזה",
    "כחול",
    "החזה",
  ]);
});

test("spaced Hebrew names keep the whole and both words", () => {
  assert.deepEqual(hebrewTokens("Tarsiger cyanurus"), [
    "כחול הזנב",
    "כחול",
    "הזנב",
  ]);
});

test("a single-word Hebrew name appears once", () => {
  const bird = catalog.birds.find(
    (item) =>
      item.hebrew &&
      item.hebrew.split(/[-\s־‐-―]+/u).filter(Boolean).length ===
        1,
  );
  assert.ok(bird, "no single-word Hebrew name in the dataset");
  const tokens = hebrewTokens(bird.latin);
  assert.deepEqual(tokens, [bird.hebrew]);
});

test("a single-word English name is not repeated", () => {
  const result = searchBirds(catalog, "Luscinia svecica");
  const bird = result.birds.find((item) => item.latin === "Luscinia svecica");
  const english = bird.tokens.filter((token) => token.text === "Bluethroat");
  assert.equal(english.length, 1);
});
