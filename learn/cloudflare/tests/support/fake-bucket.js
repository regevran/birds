/* In-memory R2 binding stub used by the Worker tests.
 *
 * It implements only the methods the Worker calls: get, put (with onlyIf),
 * delete and list. It is a binding stub, not a second progress store.
 */

export class FakeBucket {
  constructor() {
    this.objects = new Map();
    this.counter = 0;
  }

  async get(key) {
    const object = this.objects.get(key);
    if (!object) {
      return null;
    }
    return {
      key,
      etag: object.etag,
      size: object.size,
      uploaded: object.uploaded,
      arrayBuffer: async () => object.bytes.slice().buffer,
      text: async () => new TextDecoder().decode(object.bytes),
      json: async () => JSON.parse(new TextDecoder().decode(object.bytes)),
    };
  }

  async put(key, value, options = {}) {
    const condition = options.onlyIf;
    if (condition && condition.etagMatches !== undefined) {
      const current = this.objects.get(key);
      if (!current || current.etag !== condition.etagMatches) {
        return null;
      }
    }
    const bytes =
      typeof value === "string"
        ? new TextEncoder().encode(value)
        : new Uint8Array(value);
    this.counter += 1;
    const etag = `rev-${this.counter}`;
    this.objects.set(key, {
      bytes,
      etag,
      size: bytes.byteLength,
      uploaded: new Date(0),
    });
    return { key, etag, size: bytes.byteLength };
  }

  async delete(key) {
    this.objects.delete(key);
  }

  async list({ prefix = "", limit = 1000, cursor } = {}) {
    const keys = [...this.objects.keys()]
      .filter((key) => key.startsWith(prefix))
      .sort();
    const start = cursor ? Number(cursor) : 0;
    const page = keys.slice(start, start + limit);
    return {
      objects: page.map((key) => {
        const object = this.objects.get(key);
        return {
          key,
          size: object.size,
          etag: object.etag,
          uploaded: object.uploaded,
        };
      }),
      truncated: start + limit < keys.length,
      cursor:
        start + limit < keys.length ? String(start + limit) : undefined,
    };
  }
}
