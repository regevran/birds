import assert from "node:assert/strict";
import test from "node:test";

import {
  DataError,
  catalog,
} from "../src/trainer/dataset.js";

test("the bundled dataset has the expected size and version", () => {
  assert.equal(catalog.birds.length, 565);
  assert.match(catalog.dataVersion, /^sha256:[0-9a-f]{64}$/);
});

test("bird entities expose names, status and parts", () => {
  const bird = catalog.bird("acrocephalus-agricola");
  assert.equal(bird.latin, "Acrocephalus agricola");
  assert.equal(bird.hebrew, "קנית אורז");
  assert.equal(bird.family, "Acrocephalidae");
  assert.equal(bird.family_he, "קניתיים");
  assert.equal(bird.order, "Passeriformes");
  assert.equal(bird.status, "A");
  assert.deepEqual(bird.status_categories, ["accidental"]);
  assert.equal(bird.has_hebrew, true);
  assert.equal(bird.has_parts, true);
  assert.deepEqual(bird.genus_parts, [
    { latin: "Acro", element_id: "acro" },
    { latin: "cephalus", element_id: "cephalus" },
  ]);
  assert.deepEqual(bird.epithet_parts, [
    { latin: "agri", element_id: "agri" },
    { latin: "cola", element_id: "cola" },
  ]);
});

test("unsplit and no-Hebrew birds are marked correctly", () => {
  const merula = catalog.bird("turdus-merula");
  assert.equal(merula.has_parts, false);
  assert.equal(merula.has_hebrew, true);
  assert.deepEqual(merula.genus_parts, []);

  const striata = catalog.bird("butorides-striata");
  assert.equal(striata.has_hebrew, false);
  assert.equal(striata.hebrew, "");
  assert.ok(striata.flags.includes("no-hebrew"));
});

test("element and split lookups use the shared etymology", () => {
  const element = catalog.element("acro");
  assert.equal(element.he, "פסגה");
  assert.equal(element.theme, "Shape");
  assert.equal(element.en, "summit, peak");

  assert.deepEqual(catalog.partsFor("Acrocephalus"), [
    { latin: "Acro", element_id: "acro" },
    { latin: "cephalus", element_id: "cephalus" },
  ]);
  assert.deepEqual(catalog.partsFor("not-a-word"), []);
  assert.throws(() => catalog.element("not-an-element"), DataError);
  assert.throws(() => catalog.bird("not-a-bird"), DataError);
});

test("taxonomic and Hebrew indexes are built", () => {
  assert.ok(
    catalog.family("Acrocephalidae").some(
      (bird) => bird.species_id === "acrocephalus-agricola",
    ),
  );
  assert.ok(
    catalog.order("Passeriformes").some(
      (bird) => bird.species_id === "acrocephalus-agricola",
    ),
  );
  assert.ok(
    catalog.genus("Acrocephalus").some(
      (bird) => bird.species_id === "acrocephalus-agricola",
    ),
  );
  assert.equal(catalog.birdsWithHebrew("קנית אורז").length, 1);
  assert.equal(catalog.birdsWithHebrew("no such name").length, 0);
});

test("form and whole-name indexes are available", () => {
  assert.ok(catalog.elementsForForm("cephala").length > 0);
  const whole = catalog.wholeNames.get("Thalasseus");
  assert.ok(whole);
  assert.equal(typeof whole.en, "string");
});

test("the status index uses categories, not raw statuses", () => {
  const accidental = catalog.byStatus.get("accidental");
  assert.ok(accidental.length > 0);
  assert.ok(
    accidental.some(
      (bird) => bird.species_id === "acrocephalus-agricola",
    ),
  );
});
