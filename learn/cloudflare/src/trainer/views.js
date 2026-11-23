/* Pure card views for the Worker session API.
 *
 * The JSON shapes intentionally match the Python dataclasses so the text
 * client can deserialize them and reuse its renderers.
 */

import { seededRandom, shuffle } from "./random.js";

export class ViewError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "ViewError";
    this.code = code;
  }
}

const OPTION_COUNT = 5;

export function cardView(catalog, descriptor, seed = 0) {
  const bird = catalog.bird(descriptor.species_id);
  switch (descriptor.card_type) {
    case "L":
      return learnView(catalog, bird);
    case "E":
      return elementsView(catalog, bird, seed);
    case "R":
      return recognizeView(catalog, bird, seed);
    case "C":
      return constructView(catalog, bird);
    case "F":
      return produceView(bird);
    default:
      throw new ViewError(
        "unsupported_card",
        `card type ${descriptor.card_type} is not implemented`,
      );
  }
}

function learnParts(bird, catalog) {
  return [...bird.genus_parts, ...bird.epithet_parts].map((part) => {
    const element = catalog.element(part.element_id);
    return {
      latin: part.latin,
      element_id: part.element_id,
      english: element.en,
      hebrew: element.he,
      theme: element.theme,
    };
  });
}

function bridge(bird, parts) {
  if (!bird.hebrew) {
    return [];
  }
  const matches = [];
  const seen = new Set();
  for (const part of parts) {
    if (!part.hebrew || !bird.hebrew.includes(part.hebrew)) {
      continue;
    }
    const key = `${part.hebrew}|${part.latin}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    matches.push({
      hebrew: part.hebrew,
      latin: part.latin,
      english: part.english,
    });
  }
  return matches;
}

function wholeNames(bird, catalog) {
  const notes = [];
  for (const word of [bird.genus, bird.epithet]) {
    const whole = catalog.wholeNames.get(word);
    if (whole) {
      notes.push({
        word,
        english: whole.en,
        hebrew: whole.he,
        source: whole.source,
      });
    }
  }
  return notes;
}

function learnView(catalog, bird) {
  const parts = learnParts(bird, catalog);
  return {
    card_type: "L",
    species_id: bird.species_id,
    latin: bird.latin,
    english: bird.english,
    hebrew: bird.hebrew,
    family: bird.family,
    family_he: bird.family_he,
    order: bird.order,
    status: bird.status,
    status_categories: bird.status_categories,
    parts,
    bridge: bridge(bird, parts),
    whole_names: wholeNames(bird, catalog),
  };
}

function elementOptions(catalog, element, seed) {
  const sameTheme = [...catalog.elements.values()]
    .filter(
      (other) =>
        other.theme === element.theme &&
        other.element_id !== element.element_id,
    )
    .sort((left, right) =>
      left.element_id < right.element_id ? -1 : 1,
    );

  const distractors = [];
  const seen = new Set([element.he]);
  for (const other of sameTheme) {
    if (seen.has(other.he)) {
      continue;
    }
    seen.add(other.he);
    distractors.push(other.he);
  }

  const next = seededRandom(`${seed}:${element.element_id}`);
  const chosen = shuffle(distractors, next).slice(0, OPTION_COUNT - 1);
  return shuffle([element.he, ...chosen], next);
}

function elementsView(catalog, bird, seed) {
  const parts = learnParts(bird, catalog);
  if (parts.length === 0) {
    throw new ViewError(
      "no_split_elements",
      `${bird.latin} has no split elements`,
    );
  }

  const order = [];
  const latinForms = new Map();
  for (const part of parts) {
    if (!latinForms.has(part.element_id)) {
      order.push(part.element_id);
      latinForms.set(part.element_id, []);
    }
    latinForms.get(part.element_id).push(part.latin);
  }

  return {
    card_type: "E",
    species_id: bird.species_id,
    family: bird.family,
    latin: bird.latin,
    rows: order.map((elementId) => {
      const element = catalog.element(elementId);
      return {
        element_id: elementId,
        latin_forms: latinForms.get(elementId),
        theme: element.theme,
        options: elementOptions(catalog, element, seed),
      };
    }),
  };
}

function recognizeView(catalog, bird, seed) {
  if (!bird.hebrew) {
    throw new ViewError(
      "no_hebrew",
      `${bird.latin} has no Hebrew name`,
    );
  }

  const accepted = catalog.birdsWithHebrew(bird.hebrew);
  const acceptedIds = new Set(accepted.map((other) => other.species_id));
  const wanted = Math.max(0, OPTION_COUNT - accepted.length);
  const next = seededRandom(`${seed}:${bird.species_id}:R`);

  const distractors = [];
  const seen = new Set(acceptedIds);
  const tiers = [
    catalog.genus(bird.genus),
    catalog.family(bird.family),
    catalog.order(bird.order),
    catalog.birds,
  ];
  if (wanted > 0) {
    for (const tier of tiers) {
      const candidates = shuffle(
        [...tier].sort((left, right) =>
          left.species_id < right.species_id ? -1 : 1,
        ),
        next,
      );
      for (const other of candidates) {
        if (seen.has(other.species_id)) {
          continue;
        }
        seen.add(other.species_id);
        distractors.push({
          latin: other.latin,
          species_id: other.species_id,
        });
        if (distractors.length === wanted) {
          break;
        }
      }
      if (distractors.length === wanted) {
        break;
      }
    }
  }

  const options = [
    ...accepted.map((other) => ({
      latin: other.latin,
      species_id: other.species_id,
    })),
    ...distractors,
  ];
  return {
    card_type: "R",
    species_id: bird.species_id,
    family: bird.family,
    hebrew: bird.hebrew,
    options: shuffle(options, next),
  };
}

function constructParts(word, parts, catalog) {
  if (parts.length === 0) {
    return [
      {
        hebrew: "",
        first_letter: word.charAt(0),
        length: word.length,
      },
    ];
  }
  return parts.map((part) => ({
    hebrew: catalog.element(part.element_id).he,
    first_letter: part.latin.charAt(0),
    length: part.latin.length,
  }));
}

function constructView(catalog, bird) {
  if (!bird.hebrew) {
    throw new ViewError(
      "no_hebrew",
      `${bird.latin} has no Hebrew name`,
    );
  }
  return {
    card_type: "C",
    species_id: bird.species_id,
    family: bird.family,
    hebrew: bird.hebrew,
    genus_parts: constructParts(
      bird.genus,
      bird.genus_parts,
      catalog,
    ),
    epithet_parts: constructParts(
      bird.epithet,
      bird.epithet_parts,
      catalog,
    ),
  };
}

function produceView(bird) {
  if (!bird.hebrew) {
    throw new ViewError(
      "no_hebrew",
      `${bird.latin} has no Hebrew name`,
    );
  }
  return {
    card_type: "F",
    species_id: bird.species_id,
    family: bird.family,
    hebrew: bird.hebrew,
  };
}

export { OPTION_COUNT };
