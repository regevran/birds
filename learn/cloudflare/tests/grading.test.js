import assert from "node:assert/strict";
import test from "node:test";

import { catalog } from "../src/trainer/dataset.js";
import {
  GradeError,
  damerauLevenshtein,
  gradeElements,
  gradeLatin,
  gradeRecognize,
} from "../src/trainer/grading.js";
import { normalizeLatin } from "../src/trainer/normalize.js";

test("Latin normalization does NFC, whitespace collapse and casefold", () => {
  assert.equal(
    normalizeLatin("  ACROCEPHALUS   AGRICOLA  "),
    "acrocephalus agricola",
  );
  assert.equal(
    normalizeLatin("Acro\tcephalus\nagricola"),
    "acro cephalus agricola",
  );
  assert.equal(normalizeLatin("Acro cephalus"), "acro cephalus");
  assert.equal(normalizeLatin("é"), "é");
  assert.equal(normalizeLatin("é"), "é");
});

function elementView(bird) {
  const ids = [
    ...new Set(
      [...bird.genus_parts, ...bird.epithet_parts].map(
        (part) => part.element_id,
      ),
    ),
  ];
  return {
    card_type: "E",
    species_id: bird.species_id,
    latin: bird.latin,
    rows: ids.map((id) => {
      const element = catalog.element(id);
      return {
        element_id: id,
        latin_forms: [],
        theme: element.theme,
        options: [element.he, "not the answer"],
      };
    }),
  };
}

test("element grading accepts correct choices and reports wrong ones", () => {
  const bird = catalog.bird("acrocephalus-agricola");
  const view = elementView(bird);
  const correct = Object.fromEntries(
    view.rows.map((row) => [row.element_id, catalog.element(row.element_id).he]),
  );

  const results = gradeElements(catalog, view, correct);
  assert.equal(results.length, view.rows.length);
  assert.ok(results.every((result) => result.correct));

  const first = view.rows[0];
  const wrong = { ...correct, [first.element_id]: "not the answer" };
  const wrongResults = gradeElements(catalog, view, wrong);
  assert.equal(wrongResults[0].correct, false);
  assert.equal(wrongResults[0].expected, catalog.element(first.element_id).he);
});

test("element grading validates choices", () => {
  const view = elementView(catalog.bird("acrocephalus-agricola"));
  const correct = Object.fromEntries(
    view.rows.map((row) => [row.element_id, catalog.element(row.element_id).he]),
  );
  const missing = { ...correct };
  delete missing[view.rows[0].element_id];
  assert.throws(() => gradeElements(catalog, view, missing), GradeError);
  assert.throws(
    () => gradeElements(catalog, view, { ...correct, nope: "x" }),
    GradeError,
  );
  assert.throws(
    () =>
      gradeElements(catalog, view, {
        ...correct,
        [view.rows[0].element_id]: "not an option",
      }),
    GradeError,
  );
});

test("shared glosses are accepted by gloss, not by owner", () => {
  const byGloss = new Map();
  for (const element of catalog.elements.values()) {
    const group = byGloss.get(element.he) ?? [];
    group.push(element);
    byGloss.set(element.he, group);
  }
  const pair = [...byGloss.values()].find((group) => group.length > 1);
  assert.ok(pair);
  const element = pair[0];
  const view = {
    card_type: "E",
    species_id: "test-test",
    latin: "Test test",
    rows: [
      {
        element_id: element.element_id,
        latin_forms: ["Test"],
        theme: element.theme,
        options: [element.he, "other"],
      },
    ],
  };
  const results = gradeElements(catalog, view, {
    [element.element_id]: element.he,
  });
  assert.equal(results[0].correct, true);
});

test("recognize grading accepts the matching species", () => {
  const bird = catalog.bird("acrocephalus-agricola");
  const view = {
    card_type: "R",
    species_id: bird.species_id,
    hebrew: bird.hebrew,
    options: [
      { latin: bird.latin, species_id: bird.species_id },
      { latin: "Turdus merula", species_id: "turdus-merula" },
    ],
  };
  const result = gradeRecognize(catalog, view, bird.species_id);
  assert.equal(result.correct, true);
  assert.deepEqual(result.accepted, ["Acrocephalus agricola"]);
  assert.equal(result.chosen.species_id, bird.species_id);

  const wrong = gradeRecognize(catalog, view, "turdus-merula");
  assert.equal(wrong.correct, false);
  assert.throws(
    () => gradeRecognize(catalog, view, "no-such-bird"),
    GradeError,
  );
});

test("the shared Hebrew name accepts either Oenanthe", () => {
  const bird = catalog.bird("oenanthe-lugens");
  const other = catalog.bird("oenanthe-warriae");
  assert.equal(bird.hebrew, other.hebrew);
  const view = {
    card_type: "R",
    species_id: bird.species_id,
    hebrew: bird.hebrew,
    options: [
      { latin: bird.latin, species_id: bird.species_id },
      { latin: other.latin, species_id: other.species_id },
    ],
  };
  const result = gradeRecognize(catalog, view, other.species_id);
  assert.equal(result.correct, true);
  assert.deepEqual(
    new Set(result.accepted),
    new Set(["Oenanthe lugens", "Oenanthe warriae"]),
  );
});

test("Damerau-Levenshtein counts a transposition as one edit", () => {
  assert.equal(damerauLevenshtein("agricloa", "agricola"), 1);
  assert.equal(damerauLevenshtein("agrikola", "agricola"), 1);
  assert.equal(damerauLevenshtein("", "abc"), 3);
  assert.equal(damerauLevenshtein("abc", ""), 3);
});

test("Latin grading matches the Python cases", () => {
  const expected = "Acrocephalus agricola";

  const correct = gradeLatin(
    expected,
    "  ACROCEPHALUS   AGRICOLA  ",
  );
  assert.equal(correct.outcome, "correct");
  assert.equal(correct.distance, 0);
  assert.equal(correct.genus_ok, true);
  assert.equal(correct.epithet_ok, true);
  assert.equal(correct.expected, expected);

  const typo = gradeLatin(expected, "Acrocephalus agrikola");
  assert.equal(typo.outcome, "near_miss");
  assert.equal(typo.distance, 1);
  assert.equal(typo.genus_ok, true);
  assert.equal(typo.epithet_ok, false);

  const transposition = gradeLatin(
    expected,
    "Acrocephalus agricloa",
  );
  assert.equal(transposition.outcome, "near_miss");
  assert.equal(transposition.distance, 1);

  const genusTypo = gradeLatin(
    expected,
    "Acrocefalus agricola",
  );
  assert.equal(genusTypo.outcome, "near_miss");
  assert.equal(genusTypo.distance, 2);
  assert.equal(genusTypo.genus_ok, false);
  assert.equal(genusTypo.epithet_ok, true);

  const firstLetter = gradeLatin(
    expected,
    "Acrocephalus egricola",
  );
  assert.equal(firstLetter.outcome, "wrong");
  assert.equal(firstLetter.distance, 1);

  assert.equal(
    gradeLatin(expected, "Acrocephalus").outcome,
    "wrong",
  );
  assert.equal(
    gradeLatin(expected, "Turdus merula").outcome,
    "wrong",
  );

  const accent = gradeLatin(
    expected,
    "Acrocephalus agricóla",
  );
  assert.equal(accent.outcome, "near_miss");
  assert.equal(accent.distance, 1);

  const firstAccent = gradeLatin(
    expected,
    "Acrocephalus ágricola",
  );
  assert.equal(firstAccent.outcome, "wrong");
});
