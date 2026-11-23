/* Latin input normalization shared by grading and the session API. */

export function normalizeLatin(text) {
  return String(text ?? "")
    .normalize("NFC")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
}
