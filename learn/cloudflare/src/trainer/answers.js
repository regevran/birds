/* Grade one answer against a card view.
 *
 * Session answers and stateless card practice share this function so their
 * feedback shapes and retry rules cannot drift.
 */

import {
  GradeError,
  gradeElements,
  gradeLatin,
  gradeRecognize,
} from "./grading.js";

export function gradeAnswer(
  catalog,
  speciesId,
  cardType,
  view,
  body,
  attempt = 1,
) {
  if (cardType === "E") {
    const results = gradeElements(catalog, view, body.choices ?? {});
    return {
      outcome: "graded",
      feedback: {
        kind: "elements",
        results,
        correct: results.filter((result) => result.correct).length,
        total: results.length,
      },
    };
  }

  if (cardType === "R") {
    if (typeof body.choice !== "string") {
      throw new GradeError("choice is required");
    }
    const result = gradeRecognize(catalog, view, body.choice);
    if (result.correct) {
      return {
        outcome: "correct",
        feedback: { kind: "recognize", result },
      };
    }
    if (attempt === 1) {
      return {
        outcome: "retry",
        feedback: {
          kind: "retry",
          chosen: result.chosen.latin,
          message: "wrong; try again",
        },
      };
    }
    return {
      outcome: "wrong",
      feedback: { kind: "recognize", result },
    };
  }

  if (cardType === "C" || cardType === "F") {
    if (typeof body.response !== "string") {
      throw new GradeError("response is required");
    }
    const bird = catalog.bird(speciesId);
    const result = gradeLatin(bird.latin, body.response);
    if (result.outcome === "correct") {
      return {
        outcome: "correct",
        feedback: { kind: "latin", result },
      };
    }
    if (result.outcome === "near_miss") {
      return {
        outcome: "near_miss",
        feedback: { kind: "latin", result },
      };
    }
    if (attempt === 1) {
      return {
        outcome: "retry",
        feedback: {
          kind: "retry",
          response: result.response,
          message: "wrong; try again",
        },
      };
    }
    return {
      outcome: "wrong",
      feedback: { kind: "latin", result },
    };
  }

  throw new GradeError(`${cardType} cards are not answered`);
}
