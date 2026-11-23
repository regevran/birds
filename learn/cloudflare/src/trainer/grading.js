/* Answer grading for the Worker session API.
 *
 * The result shapes match the Python dataclasses so the text client can
 * reuse its existing feedback renderers: snake_case keys, arrays for tuples.
 */

import { normalizeLatin } from "./normalize.js";

export class GradeError extends Error {
  constructor(message) {
    super(message);
    this.name = "GradeError";
    this.code = "invalid_request";
  }
}

export function gradeElements(catalog, view, choices) {
  const expectedIds = view.rows.map((row) => row.element_id);
  const given = new Set(Object.keys(choices ?? {}));
  const missing = expectedIds.filter((id) => !given.has(id));
  if (missing.length > 0) {
    throw new GradeError(`missing choices for: ${missing.join(", ")}`);
  }
  const extra = [...given].filter((id) => !expectedIds.includes(id));
  if (extra.length > 0) {
    throw new GradeError(`choices for unknown elements: ${extra.join(", ")}`);
  }

  return view.rows.map((row) => {
    const chosen = choices[row.element_id];
    if (!row.options.includes(chosen)) {
      throw new GradeError(
        `${JSON.stringify(chosen)} is not an option for element ` +
          JSON.stringify(row.element_id),
      );
    }
    const expected = catalog.element(row.element_id).he;
    return {
      element_id: row.element_id,
      chosen,
      expected,
      correct: chosen === expected,
    };
  });
}

export function gradeRecognize(catalog, view, chosenSpeciesId) {
  const chosen = view.options.find(
    (option) => option.species_id === chosenSpeciesId,
  );
  if (!chosen) {
    throw new GradeError(
      `${JSON.stringify(chosenSpeciesId)} is not an option for species ` +
        JSON.stringify(view.species_id),
    );
  }
  const acceptedBirds = catalog.birdsWithHebrew(view.hebrew);
  const acceptedIds = new Set(acceptedBirds.map((bird) => bird.species_id));
  return {
    chosen: { latin: chosen.latin, species_id: chosen.species_id },
    accepted: acceptedBirds.map((bird) => bird.latin),
    correct: acceptedIds.has(chosenSpeciesId),
  };
}

export function gradeLatin(expected, response) {
  const normalizedExpected = normalizeLatin(expected);
  const normalizedResponse = normalizeLatin(response);
  const expectedWords = normalizedExpected
    ? normalizedExpected.split(" ")
    : [];
  const responseWords = normalizedResponse
    ? normalizedResponse.split(" ")
    : [];

  const words = [];
  if (expectedWords.length === responseWords.length) {
    for (let index = 0; index < expectedWords.length; index += 1) {
      const expectedWord = expectedWords[index];
      const responseWord = responseWords[index];
      const distance = damerauLevenshtein(expectedWord, responseWord);
      words.push({
        expected: expectedWord,
        response: responseWord,
        status: wordStatus(expectedWord, responseWord, distance),
        distance,
      });
    }
  } else {
    for (let index = 0; index < expectedWords.length; index += 1) {
      const expectedWord = expectedWords[index];
      const responseWord = responseWords[index] ?? "";
      if (responseWord) {
        const distance = damerauLevenshtein(expectedWord, responseWord);
        words.push({
          expected: expectedWord,
          response: responseWord,
          status: wordStatus(expectedWord, responseWord, distance),
          distance,
        });
      } else {
        words.push({
          expected: expectedWord,
          response: "",
          status: "wrong",
          distance: expectedWord.length,
        });
      }
    }
  }

  const genusOk = words.length > 0 && words[0].status === "correct";
  const epithetOk = words.length > 1 && words[1].status === "correct";

  let distance;
  let outcome;
  if (expectedWords.length !== responseWords.length) {
    distance = damerauLevenshtein(normalizedExpected, normalizedResponse);
    outcome = "wrong";
  } else {
    distance = words.reduce((total, word) => total + word.distance, 0);
    const firstLettersMatch = words
      .filter((word) => word.expected && word.response)
      .every((word) => word.expected[0] === word.response[0]);
    if (distance === 0) {
      outcome = "correct";
    } else if (distance <= 2 && firstLettersMatch) {
      outcome = "near_miss";
    } else {
      outcome = "wrong";
    }
  }

  return {
    response: normalizedResponse,
    expected,
    outcome,
    genus_ok: genusOk,
    epithet_ok: epithetOk,
    distance,
    words,
  };
}

export function wordStatus(expected, response, distance) {
  if (expected === response) {
    return "correct";
  }
  if (
    distance <= 2 &&
    expected.length > 0 &&
    response.length > 0 &&
    expected[0] === response[0]
  ) {
    return "almost";
  }
  return "wrong";
}

export function damerauLevenshtein(left, right) {
  const leftChars = Array.from(left);
  const rightChars = Array.from(right);
  if (leftChars.length === 0) {
    return rightChars.length;
  }
  if (rightChars.length === 0) {
    return leftChars.length;
  }

  let beforePrevious = new Array(rightChars.length + 1).fill(0);
  let previous = Array.from(
    { length: rightChars.length + 1 },
    (_, index) => index,
  );

  for (let leftIndex = 1; leftIndex <= leftChars.length; leftIndex += 1) {
    const leftChar = leftChars[leftIndex - 1];
    const current = new Array(rightChars.length + 1).fill(0);
    current[0] = leftIndex;
    for (
      let rightIndex = 1;
      rightIndex <= rightChars.length;
      rightIndex += 1
    ) {
      const rightChar = rightChars[rightIndex - 1];
      const cost = leftChar === rightChar ? 0 : 1;
      current[rightIndex] = Math.min(
        current[rightIndex - 1] + 1,
        previous[rightIndex] + 1,
        previous[rightIndex - 1] + cost,
      );
      if (
        leftIndex > 1 &&
        rightIndex > 1 &&
        leftChar === rightChars[rightIndex - 2] &&
        leftChars[leftIndex - 2] === rightChar
      ) {
        current[rightIndex] = Math.min(
          current[rightIndex],
          beforePrevious[rightIndex - 2] + 1,
        );
      }
    }
    beforePrevious = previous;
    previous = current;
  }
  return previous[rightChars.length];
}

export { normalizeLatin };
