import assert from "node:assert/strict";
import test from "node:test";

import { catalog } from "../src/trainer/dataset.js";
import { ViewError, cardView } from "../src/trainer/views.js";

function view(speciesId, cardType, seed = 0) {
  return cardView(
    catalog,
    { species_id: speciesId, card_type: cardType },
    seed,
  );
}

test("L view exposes names, parts, bridge and whole names", () => {
  const learn = view("acrocephalus-agricola", "L");
  assert.equal(learn.card_type, "L");
  assert.equal(learn.latin, "Acrocephalus agricola");
  assert.deepEqual(
    learn.parts.map((part) => part.latin),
    ["Acro", "cephalus", "agri", "cola"],
  );
  assert.deepEqual(
    learn.parts.map((part) => part.element_id),
    ["acro", "cephalus", "agri", "cola"],
  );
  assert.ok(learn.parts.every((part) => part.english));
  assert.ok(Array.isArray(learn.bridge));
  assert.ok(Array.isArray(learn.whole_names));

  const merula = view("turdus-merula", "L");
  assert.deepEqual(merula.parts, []);
});

test("E view has one row per element with same-theme options", () => {
  const elements = view("acrocephalus-agricola", "E");
  assert.deepEqual(
    elements.rows.map((row) => row.element_id),
    ["acro", "cephalus", "agri", "cola"],
  );
  for (const row of elements.rows) {
    const correct = catalog.element(row.element_id).he;
    assert.ok(row.options.includes(correct));
    assert.equal(row.options.length, new Set(row.options).size);
    assert.ok(row.options.length >= 2);
    assert.ok(row.options.length <= 5);
    const themeGlosses = new Set(
      [...catalog.elements.values()]
        .filter((element) => element.theme === row.theme)
        .map((element) => element.he),
    );
    assert.ok(row.options.every((option) => themeGlosses.has(option)));
  }

  const again = view("acrocephalus-agricola", "E", 7);
  const same = view("acrocephalus-agricola", "E", 7);
  assert.deepEqual(
    again.rows.map((row) => row.options),
    same.rows.map((row) => row.options),
  );
  assert.throws(() => view("turdus-merula", "E"), ViewError);
});

test("R view uses taxonomic distractors and is seeded", () => {
  const recognize = view("acrocephalus-agricola", "R");
  assert.equal(recognize.hebrew, "קנית אורז");
  assert.equal(recognize.options.length, 5);
  const latins = recognize.options.map((option) => option.latin);
  assert.equal(latins.length, new Set(latins).size);
  assert.ok(latins.includes("Acrocephalus agricola"));
  for (const option of recognize.options) {
    const bird = catalog.bird(option.species_id);
    assert.equal(option.latin, bird.latin);
    assert.equal(bird.genus, "Acrocephalus");
  }

  assert.deepEqual(
    view("acrocephalus-agricola", "R", 7).options,
    view("acrocephalus-agricola", "R", 7).options,
  );
  assert.throws(() => view("butorides-striata", "R"), ViewError);
});

test("the shared Hebrew name includes both Oenanthe species", () => {
  const recognize = view("oenanthe-lugens", "R");
  const latins = new Set(
    recognize.options.map((option) => option.latin),
  );
  assert.ok(latins.has("Oenanthe lugens"));
  assert.ok(latins.has("Oenanthe warriae"));
  assert.equal(recognize.options.length, 5);
});

test("C view concatenates split and unsplit word shapes", () => {
  const construct = view("acrocephalus-agricola", "C");
  assert.deepEqual(construct.genus_parts, [
    { hebrew: "פסגה", first_letter: "A", length: 4 },
    { hebrew: "ראש", first_letter: "c", length: 8 },
  ]);
  assert.deepEqual(construct.epithet_parts, [
    { hebrew: "שדה", first_letter: "a", length: 4 },
    { hebrew: "שוכן", first_letter: "c", length: 4 },
  ]);

  const merula = view("turdus-merula", "C");
  assert.deepEqual(merula.genus_parts, [
    { hebrew: "", first_letter: "T", length: 6 },
  ]);
  assert.deepEqual(merula.epithet_parts, [
    { hebrew: "", first_letter: "m", length: 6 },
  ]);
});

test("F view has only the Hebrew prompt", () => {
  const produce = view("acrocephalus-agricola", "F");
  assert.deepEqual(produce, {
    card_type: "F",
    species_id: "acrocephalus-agricola",
    family: "Acrocephalidae",
    hebrew: "קנית אורז",
  });
  assert.throws(() => view("butorides-striata", "F"), ViewError);
});

test("V and unknown card types are rejected", () => {
  assert.throws(() => view("acrocephalus-agricola", "V"), ViewError);
  assert.throws(() => view("acrocephalus-agricola", "X"), ViewError);
  assert.throws(() => view("no-such-bird", "L"), /bird/);
});
