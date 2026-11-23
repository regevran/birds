/* Bird and element-meaning search for the text client.
 *
 * Every whitespace-separated term must match, case-insensitively. A term may
 * match the bird's identity fields (id, Latin, English, Hebrew, family, Hebrew
 * family, order) or any etymology element of its name (element id, display,
 * English gloss, Hebrew gloss, forms). Bird results keep the name matches
 * first, then element-only matches, each in family/genus/Latin order.
 *
 * Each bird and element carries `matched`: the text that satisfied each term,
 * so a client can show why a result was returned. Name "matches on the row's
 * own fields" are still reported; the client decides what to display.
 */

const NAME_FIELDS = [
  "species_id",
  "latin",
  "english",
  "hebrew",
  "family",
  "family_he",
  "order",
];

export function searchBirds(catalog, query) {
  const terms = String(query ?? "")
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);

  if (terms.length === 0) {
    return {
      birds: catalog.birds
        .slice()
        .sort(compareBirds)
        .map((bird) => publicBird(bird, [])),
      elements: [],
    };
  }

  const records = [];
  for (const bird of catalog.birds) {
    const nameFields = NAME_FIELDS.map((field) => ({
      field,
      value: bird[field],
    }));
    const nameText = nameFields
      .map(({ value }) => String(value ?? "").toLowerCase())
      .join(" ");

    const elementFieldsById = new Map();
    for (const elementId of birdElementIds(bird)) {
      const element = catalog.elements.get(elementId);
      if (element) {
        elementFieldsById.set(elementId, elementFields(element));
      }
    }

    const nameHits = [];
    const elementHits = new Map();
    let nameMatched = false;
    let matchedAllTerms = true;

    for (const term of terms) {
      let termMatched = false;
      if (nameText.includes(term)) {
        nameMatched = true;
        termMatched = true;
        addHit(nameHits, firstHit(term, nameFields));
      }
      for (const [elementId, fields] of elementFieldsById) {
        const hit = firstHit(term, fields);
        if (hit) {
          termMatched = true;
          let hits = elementHits.get(elementId);
          if (!hits) {
            hits = [];
            elementHits.set(elementId, hits);
          }
          addHit(hits, hit);
        }
      }
      if (!termMatched) {
        matchedAllTerms = false;
        break;
      }
    }
    if (!matchedAllTerms) {
      continue;
    }

    const matched = [];
    if (nameMatched) {
      matched.push({ kind: "name", texts: nameHits });
    }
    for (const [elementId, texts] of elementHits) {
      matched.push({ kind: "element", element_id: elementId, texts });
    }
    records.push({ bird, nameMatched, matched });
  }

  records.sort((left, right) => {
    if (left.nameMatched !== right.nameMatched) {
      return left.nameMatched ? -1 : 1;
    }
    return compareBirds(left.bird, right.bird);
  });

  return {
    birds: records.map(({ bird, matched }) => publicBird(bird, matched)),
    elements: matchingElements(catalog, terms),
  };
}

function matchingElements(catalog, terms) {
  const counts = elementBirdCounts(catalog);
  const found = [];
  for (const element of catalog.elements.values()) {
    const fields = elementFields(element);
    const texts = [];
    let matchedAllTerms = true;
    for (const term of terms) {
      const hit = firstHit(term, fields);
      if (!hit) {
        matchedAllTerms = false;
        break;
      }
      addHit(texts, hit);
    }
    if (!matchedAllTerms) {
      continue;
    }
    found.push({
      element_id: element.element_id,
      en: element.en,
      he: element.he,
      theme: element.theme,
      origin: element.origin,
      bird_count: counts.get(element.element_id) ?? 0,
      matched: texts,
    });
  }
  found.sort((left, right) =>
    left.element_id < right.element_id
      ? -1
      : left.element_id > right.element_id
        ? 1
        : 0,
  );
  return found;
}

function elementBirdCounts(catalog) {
  const counts = new Map();
  for (const bird of catalog.birds) {
    for (const elementId of birdElementIds(bird)) {
      counts.set(elementId, (counts.get(elementId) ?? 0) + 1);
    }
  }
  return counts;
}

function birdElementIds(bird) {
  return new Set(
    [...bird.genus_parts, ...bird.epithet_parts].map((part) => part.element_id),
  );
}

function elementFields(element) {
  return [
    { field: "element_id", value: element.element_id },
    { field: "display", value: element.display },
    { field: "en", value: element.en },
    { field: "he", value: element.he },
    ...element.forms.map((value) => ({ field: "form", value })),
  ];
}

/* Return the first field whose value contains the term.  The field order is
 * the display priority: an id hit needs no gloss, a gloss hit does. */
function firstHit(term, fields) {
  for (const { field, value } of fields) {
    if (value && String(value).toLowerCase().includes(term)) {
      return { field, text: value };
    }
  }
  return null;
}

function addHit(hits, hit) {
  if (
    hit &&
    !hits.some((item) => item.field === hit.field && item.text === hit.text)
  ) {
    hits.push(hit);
  }
}

function compareBirds(left, right) {
  if (left.family_order !== right.family_order) {
    return left.family_order - right.family_order;
  }
  if (left.genus !== right.genus) {
    return left.genus < right.genus ? -1 : 1;
  }
  if (left.latin !== right.latin) {
    return left.latin < right.latin ? -1 : 1;
  }
  return 0;
}

function publicBird(bird, matched) {
  return {
    species_id: bird.species_id,
    latin: bird.latin,
    english: bird.english,
    hebrew: bird.hebrew,
    family: bird.family,
    family_he: bird.family_he,
    order: bird.order,
    status: bird.status,
    status_categories: [...bird.status_categories],
    has_hebrew: bird.has_hebrew,
    has_parts: bird.has_parts,
    matched,
  };
}
