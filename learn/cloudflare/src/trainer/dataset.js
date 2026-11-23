/* Dataset entities and indexes for the Worker.
 *
 * The data itself is generated from data/out by build_worker_data.py. The
 * Python loader remains the validator; this module trusts that validated data
 * and builds the indexes the card and scheduler layers need.
 */

import {
  dataVersion as generatedVersion,
  etymology as rawEtymology,
  species as rawSpecies,
} from "../generated/data.js";

const STATUS_CATEGORIES = Object.freeze({
  "": ["regular"],
  I: ["introduced"],
  A: ["accidental"],
  Ex: ["historical"],
  "Ex/A": ["historical", "accidental"],
  X: ["extinct"],
});

export class DataError extends Error {
  constructor(message) {
    super(message);
    this.name = "DataError";
  }
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function requireArray(value, where) {
  if (!Array.isArray(value)) {
    throw new DataError(`${where} must be an array`);
  }
  return value;
}

function requireObject(value, where) {
  if (!isObject(value)) {
    throw new DataError(`${where} must be an object`);
  }
  return value;
}

function requireText(value, where) {
  if (typeof value !== "string" || value.length === 0) {
    throw new DataError(`${where} must be a non-empty string`);
  }
  return value;
}

function optionalText(value, where) {
  if (typeof value !== "string") {
    throw new DataError(`${where} must be a string`);
  }
  return value;
}

function groupBy(birds, key) {
  const groups = new Map();
  for (const bird of birds) {
    const name = key(bird);
    const group = groups.get(name);
    if (group) {
      group.push(bird);
    } else {
      groups.set(name, [bird]);
    }
  }
  return groups;
}

function groupStatus(birds) {
  const groups = new Map();
  for (const bird of birds) {
    for (const category of bird.status_categories) {
      const group = groups.get(category);
      if (group) {
        group.push(bird);
      } else {
        groups.set(category, [bird]);
      }
    }
  }
  return groups;
}

function groupHebrew(birds) {
  const groups = new Map();
  for (const bird of birds) {
    if (!bird.hebrew) {
      continue;
    }
    const group = groups.get(bird.hebrew);
    if (group) {
      group.push(bird);
    } else {
      groups.set(bird.hebrew, [bird]);
    }
  }
  return groups;
}

function groupElementsByForm(elements) {
  const groups = new Map();
  for (const element of elements.values()) {
    for (const form of element.forms) {
      const key = form.toLowerCase();
      const group = groups.get(key);
      if (!group) {
        groups.set(key, [element]);
      } else if (!group.includes(element)) {
        group.push(element);
      }
    }
  }
  return groups;
}

function loadEtymology(raw) {
  const source = requireObject(raw, "etymology");
  for (const key of ["elements", "splits", "whole_names", "themes"]) {
    if (!(key in source)) {
      throw new DataError(`etymology: missing key ${key}`);
    }
  }

  const themes = requireArray(source.themes, "etymology.themes").map(
    (theme, index) => requireText(theme, `etymology.themes[${index}]`),
  );

  const elements = new Map();
  for (const [elementId, entry] of Object.entries(
    requireObject(source.elements, "etymology.elements"),
  )) {
    const where = `element ${elementId}`;
    const record = requireObject(entry, where);
    elements.set(elementId, {
      element_id: elementId,
      en: requireText(record.en, `${where}.en`),
      he: requireText(record.he, `${where}.he`),
      origin: requireText(record.origin, `${where}.origin`),
      theme: requireText(record.theme, `${where}.theme`),
      display: requireText(record.display, `${where}.display`),
      forms: requireArray(record.forms, `${where}.forms`).map((form, index) =>
        requireText(form, `${where}.forms[${index}]`),
      ),
    });
  }
  if (elements.size === 0) {
    throw new DataError("etymology.elements must not be empty");
  }

  const splits = new Map();
  for (const [word, rawParts] of Object.entries(
    requireObject(source.splits, "etymology.splits"),
  )) {
    const parts = requireArray(rawParts, `split ${word}`).map(
      (part, index) => {
        requireArray(part, `split ${word}[${index}]`);
        if (part.length !== 2) {
          throw new DataError(
            `split ${word}[${index}] must be [latin, element_id]`,
          );
        }
        const latin = requireText(part[0], `split ${word}[${index}].latin`);
        const elementId = requireText(
          part[1],
          `split ${word}[${index}].element_id`,
        );
        if (!elements.has(elementId)) {
          throw new DataError(
            `split ${word}[${index}]: unknown element ${elementId}`,
          );
        }
        return { latin, element_id: elementId };
      },
    );
    splits.set(word, parts);
  }

  const wholeNames = new Map();
  for (const [word, entry] of Object.entries(
    requireObject(source.whole_names, "etymology.whole_names"),
  )) {
    const record = requireObject(entry, `whole name ${word}`);
    wholeNames.set(word, {
      en: requireText(record.en, `whole name ${word}.en`),
      he: requireText(record.he, `whole name ${word}.he`),
      source: requireText(record.source, `whole name ${word}.source`),
    });
  }

  return { elements, splits, wholeNames, themes };
}

function buildBird(record, index, splits) {
  const where = `species[${index}]`;
  const source = requireObject(record, where);
  const latin = requireText(source.latin, `${where}.latin`);
  const genus = requireText(source.genus, `${where}.genus`);
  const epithet = requireText(source.epithet, `${where}.epithet`);
  const status = optionalText(source.status, `${where}.status`);
  const categories = STATUS_CATEGORIES[status];
  if (!categories) {
    throw new DataError(`${where}.status ${status} is not known`);
  }
  const genusParts = splits.get(genus) ?? [];
  const epithetParts = splits.get(epithet) ?? [];

  return {
    species_id: `${genus.toLowerCase()}-${epithet.toLowerCase()}`,
    latin,
    genus,
    epithet,
    english: requireText(source.english, `${where}.english`),
    hebrew: optionalText(source.hebrew, `${where}.hebrew`),
    family: requireText(source.family, `${where}.family`),
    family_he: optionalText(source.family_he, `${where}.family_he`),
    family_order: Number(source.family_order),
    order: requireText(source.order, `${where}.order`),
    status,
    status_categories: categories,
    flags: requireArray(source.flags, `${where}.flags`),
    genus_parts: genusParts,
    epithet_parts: epithetParts,
    has_hebrew: Boolean(source.hebrew),
    has_parts: genusParts.length > 0 || epithetParts.length > 0,
  };
}

export function loadCatalog(
  species = rawSpecies,
  etymology = rawEtymology,
  version = generatedVersion,
) {
  const records = requireArray(species, "species");
  if (records.length === 0) {
    throw new DataError("species must not be empty");
  }
  const { elements, splits, wholeNames, themes } =
    loadEtymology(etymology);
  const birds = records.map((record, index) =>
    buildBird(record, index, splits),
  );

  const byId = new Map();
  const byLatin = new Map();
  for (const bird of birds) {
    if (byId.has(bird.species_id)) {
      throw new DataError(`duplicate species id ${bird.species_id}`);
    }
    if (byLatin.has(bird.latin)) {
      throw new DataError(`duplicate Latin name ${bird.latin}`);
    }
    byId.set(bird.species_id, bird);
    byLatin.set(bird.latin, bird);
  }

  return new Catalog({
    birds,
    byId,
    byFamily: groupBy(birds, (bird) => bird.family),
    byOrder: groupBy(birds, (bird) => bird.order),
    byGenus: groupBy(birds, (bird) => bird.genus),
    byHebrew: groupHebrew(birds),
    byStatus: groupStatus(birds),
    elements,
    elementsByForm: groupElementsByForm(elements),
    splits,
    wholeNames,
    themes,
    dataVersion: version,
  });
}

export class Catalog {
  constructor(fields) {
    Object.assign(this, fields);
  }

  bird(speciesId) {
    const bird = this.byId.get(speciesId);
    if (!bird) {
      throw new DataError(`bird ${speciesId}`);
    }
    return bird;
  }

  element(elementId) {
    const element = this.elements.get(elementId);
    if (!element) {
      throw new DataError(`element ${elementId}`);
    }
    return element;
  }

  partsFor(word) {
    return this.splits.get(word) ?? [];
  }

  family(name) {
    return this.byFamily.get(name) ?? [];
  }

  order(name) {
    return this.byOrder.get(name) ?? [];
  }

  genus(name) {
    return this.byGenus.get(name) ?? [];
  }

  birdsWithHebrew(hebrew) {
    return this.byHebrew.get(hebrew) ?? [];
  }

  elementsForForm(form) {
    return this.elementsByForm.get(form.toLowerCase()) ?? [];
  }
}

export const catalog = loadCatalog();

export { STATUS_CATEGORIES };
